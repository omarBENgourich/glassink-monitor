# ingestion - Node-RED MQTT to InfluxDB

**Composant :** Node-RED 4.1.10
**Rôle :** ingestion authentifiée entre MQTT et InfluxDB 2.x.

## Access

<http://localhost:1880>

Credentials come from `.env`:

```text
NODE_RED_ADMIN_USER
NODE_RED_ADMIN_PASSWORD
```

The editor is loopback-bound. `GET /health` remains unauthenticated for Docker
and operations monitoring.

## Flows

`flows.json` contains four tabs:

| Tab | Input | Output |
|---|---|---|
| `01 - Télémétrie` | `.../telemetry` | `printer_telemetry` |
| `02 - Événements` | `.../event` | `printer_event` |
| `03 - Marquages` | `.../marking` | `marking_event` |
| `04 - Supervision` | InfluxDB health probe and catches | `/health` + dead letter |

Each data flow stays visible:

```text
MQTT in -> validation + line protocol -> InfluxDB API v2 -> counter
                                      \-> error -> dead-letter topic
```

`line_protocol.js` is shared by the three validation functions. It escapes tag,
field, and string values and builds authenticated writes without storing the
InfluxDB token in `flows.json`.

## Derived Values

The telemetry flow adds the values used directly by Grafana:

- `classification`: `producing`, `downtime`, `idle_jet_on`, or
  `idle_no_order`;
- rolling ink and solvent consumption rates;
- `*_hours_to_empty`, `*_action_days`, and `*_expiry_limited`.

A refill jump resets the rolling depletion rate. The demand signal determines
whether a stopped printer is downtime or normal order-driven idle.

## Delivery Guarantee

MQTT QoS 1 may replay a message. InfluxDB identifies a point by measurement,
tag set, and timestamp, so an exact replay overwrites the same point instead of
adding a duplicate. The simulator keeps the source timestamp unchanged on a
retry.

InfluxDB writes each point independently. A connection failure may therefore
leave part of a multi-message MQTT burst written. Retrying the burst remains
safe point by point because an exact replay replaces the original point.

Invalid payloads are published to `sgx/system/dead-letter` with the original
topic, error, and payload.

## Configuration

Node-RED reads only environment variables:

```text
MQTT_HOST MQTT_PORT
INFLUXDB_URL INFLUXDB_ORG INFLUXDB_BUCKET INFLUXDB_TOKEN
NODE_RED_ADMIN_USER NODE_RED_ADMIN_PASSWORD NODE_RED_CREDENTIAL_SECRET
```

## Start And Verify

```bash
make phase3
curl -fsS http://localhost:1880/health
make verify
```

The health response includes InfluxDB status and in-process counters. Counters
reset when Node-RED restarts; the points in InfluxDB remain authoritative.

## Site Cutover

The simulator publishes plain JSON. Map a real Litmus Edge payload in the three
validation functions. If Litmus publishes Sparkplug B protobuf, add its decoder
before validation; the Influx measurements and Grafana queries remain unchanged.
