"""Webhook receiver.

Grafana posts every alert here. This service decides where it goes, so changing
channel later means changing this file — not rebuilding the alert rules, which
are the part with the actual engineering in them.

Endpoints:
    POST /webhook   Grafana unified-alerting payload
    POST /test      send a fake alert through the configured channels
    GET  /health    liveness
"""
import json
import logging
import os
import signal
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from . import channels
from .formatting import format_payload

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s %(message)s",
)
log = logging.getLogger("notifier")

PORT = int(os.getenv("NOTIFIER_PORT", 8080))
MAX_BODY = 1_000_000


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):  # quieter than the default access log
        log.debug(fmt, *args)

    def _reply(self, code: int, body: dict) -> None:
        raw = json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self):
        if self.path.rstrip("/") in ("/health", ""):
            self._reply(200, {"status": "ok", "channels": channels.enabled()})
        else:
            self._reply(404, {"error": "not found"})

    def do_POST(self):
        path = self.path.rstrip("/")

        if path == "/test":
            title, lines = "Test", [
                "CIJ_Printer_L1 : le solvant sera épuisé dans environ 5 heures "
                "(41 % restant, baisse de 8 %/h)."
            ]
            results = channels.dispatch(title, lines)
            self._reply(200, {"sent": results})
            return

        if path != "/webhook":
            self._reply(404, {"error": "not found"})
            return

        length = int(self.headers.get("Content-Length") or 0)
        if length <= 0 or length > MAX_BODY:
            self._reply(400, {"error": "missing or oversized body"})
            return

        try:
            payload = json.loads(self.rfile.read(length))
        except json.JSONDecodeError:
            self._reply(400, {"error": "invalid json"})
            return

        title, lines = format_payload(payload)
        results = channels.dispatch(title, lines)
        self._reply(200, {"sent": results})


def main() -> int:
    server = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)

    def stop(signum, frame):
        log.info("signal %s received, shutting down", signum)
        # shutdown() must run outside the serve_forever() thread or it
        # deadlocks while waiting for that same thread to return.
        threading.Thread(target=server.shutdown, daemon=True).start()

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)

    log.info("listening on :%d, channels=%s", PORT, channels.enabled())
    server.serve_forever()
    server.server_close()
    log.info("stopped")
    return 0


if __name__ == "__main__":
    sys.exit(main())
