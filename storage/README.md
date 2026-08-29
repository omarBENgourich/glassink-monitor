# storage - InfluxDB 2.x

**Composant :** InfluxDB 2.7
**Rôle :** historiser la télémétrie, les événements et les marquages DMC.

## Data Model

One organization and one bucket are initialized by Compose:

```text
organization: saint-gobain
bucket:       printer_monitoring
```

| Measurement | Tags | Fields |
|---|---|---|
| `printer_telemetry` | printer, line, classification | raw metrics plus depletion and expiry forecasts |
| `printer_event` | printer, event type, code, consumable | descriptions, durations, batch metadata |
| `marking_event` | printer, line, product, grade | DMC, print result, verification result |

The bucket has infinite retention in the prototype (`INFLUXDB_RETENTION=0`). A
site retention value should replace it before production if storage policy
requires one.

## Access

The API and UI are loopback-bound at <http://localhost:8086>. Credentials and
the API token live in `.env` and are not committed.

```bash
make influx
```

## Duplicate Handling

InfluxDB overwrites a point with the same measurement, tag set, and timestamp.
That makes exact MQTT QoS 1 replay idempotent without a high-cardinality
`message_id` tag. It is point-level idempotence, not a transaction across
measurements.

## Reset

```bash
make reset-influx
```

This deletes only the two InfluxDB volumes, initializes a fresh bucket, and
restarts Grafana so its datasource reconnects.
