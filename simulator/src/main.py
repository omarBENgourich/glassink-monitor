"""Publish loop.

Physics advances TIME_ACCEL times faster than real time so a demo shows
something within minutes. Timestamps are real, so everything downstream — the
6-hour slope window, the retention policies, Grafana's time picker — behaves
normally. Only the rates are compressed.
"""
import json
import logging
import random
import signal
import sys
import time
import uuid

import paho.mqtt.client as mqtt

from . import config
from .printer import CIJPrinter

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s %(message)s",
)
log = logging.getLogger("simulator")

_running = True


def _stop(signum, frame):
    global _running
    _running = False
    log.info("signal %s received, shutting down", signum)


def now_ms() -> int:
    return int(time.time() * 1000)


def identified(payload: dict) -> dict:
    """Return a publishable payload with a unique MQTT idempotency key."""
    return {**payload, "message_id": uuid.uuid4().hex}


def build_client() -> mqtt.Client:
    client = mqtt.Client(
        mqtt.CallbackAPIVersion.VERSION2,
        client_id=f"simulator-{config.PRINTER_ID}",
    )
    # Last will: if the simulator dies, subscribers find out immediately rather
    # than waiting for a data-gap timeout. This is the plain-MQTT stand-in for
    # a Sparkplug NDEATH certificate.
    client.will_set(
        config.TOPIC_EVENT,
        json.dumps(identified({
            "ts": now_ms(),
            "printer_id": config.PRINTER_ID,
            "event_type": "state_change",
            "to_state": "shutdown",
            "description": "simulator connection lost",
        })),
        qos=1,
        retain=False,
    )
    return client


def publish_birth(client: mqtt.Client) -> None:
    """Announce the asset so the consumer can create the printer row."""
    client.publish(
        config.TOPIC_EVENT,
        json.dumps(identified({
            "ts": now_ms(),
            "printer_id": config.PRINTER_ID,
            "line_id": config.LINE_ID,
            "site_id": config.SITE_ID,
            "vendor": config.VENDOR,
            "model": config.MODEL,
            "event_type": "birth",
            "description": "simulator started",
        })),
        qos=1,
    )


def main() -> int:
    signal.signal(signal.SIGTERM, _stop)
    signal.signal(signal.SIGINT, _stop)

    client = build_client()
    for attempt in range(1, 31):
        try:
            client.connect(config.MQTT_HOST, config.MQTT_PORT, keepalive=60)
            break
        except OSError as exc:
            log.warning("broker not reachable (%s), retry %d/30", exc, attempt)
            time.sleep(2)
    else:
        log.error("giving up connecting to %s:%s", config.MQTT_HOST, config.MQTT_PORT)
        return 1

    client.loop_start()
    publish_birth(client)

    printer = CIJPrinter()

    # Register the cartridges already fitted, so expiry is known from the
    # first sample rather than from the first refill.
    for event in printer.fitted_consumable_events():
        client.publish(
            config.TOPIC_EVENT,
            json.dumps(identified({
                "ts": now_ms(),
                "printer_id": config.PRINTER_ID,
                "line_id": config.LINE_ID,
                **event,
            })),
            qos=1,
        )

    interval = config.PUBLISH_INTERVAL_S
    dt_h = interval * config.TIME_ACCEL / 3600.0

    log.info(
        "publishing to %s every %.1fs  (1 real second = %.0f simulated seconds)",
        config.BASE_TOPIC, interval, config.TIME_ACCEL,
    )

    dropout_until = 0.0

    while _running:
        cycle_start = time.time()
        printer.step(dt_h)

        # Occasionally go silent, to exercise the "no data" alert.
        if time.time() < dropout_until:
            time.sleep(max(0.0, interval - (time.time() - cycle_start)))
            continue
        if random.random() < config.DROPOUT_PROBABILITY:
            dropout_until = time.time() + config.DROPOUT_DURATION_S
            log.warning("simulating a %.0fs publishing dropout",
                        config.DROPOUT_DURATION_S)
            continue

        ts = now_ms()

        client.publish(
            config.TOPIC_TELEMETRY,
            json.dumps(identified({
                "ts": ts,
                "printer_id": config.PRINTER_ID,
                "line_id": config.LINE_ID,
                "metrics": printer.telemetry(),
            })),
            qos=1,
        )

        for event in printer.drain_events():
            client.publish(
                config.TOPIC_EVENT,
                json.dumps(identified({
                    "ts": ts,
                    "printer_id": config.PRINTER_ID,
                    "line_id": config.LINE_ID,
                    **event,
                })),
                qos=1,
            )
            log.info("event  %-13s %s", event["event_type"],
                     event.get("description") or event.get("to_state", ""))

        markings = printer.markings(dt_h)
        for i, marking in enumerate(markings):
            client.publish(
                config.TOPIC_MARKING,
                json.dumps(identified({
                    "marked_at": ts + i,
                    "printer_id": config.PRINTER_ID,
                    "line_id": config.LINE_ID,
                    **marking,
                })),
                qos=1,
            )

        log.info(
            "state=%-8s demand=%-5s ink=%5.1f%% solvent=%5.1f%% "
            "visc=%.2f marked=%d",
            printer.state, printer.demanding, printer.ink.level,
            printer.solvent.level, printer.viscosity, len(markings),
        )

        elapsed = time.time() - cycle_start
        time.sleep(max(0.0, interval - elapsed))

    client.loop_stop()
    client.disconnect()
    log.info("stopped")
    return 0


if __name__ == "__main__":
    sys.exit(main())
