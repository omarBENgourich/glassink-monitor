# broker — MQTT transport

**Composant :** Eclipse Mosquitto 2.0
**Rôle :** acheminer les messages MQTT.

## What it does

Receives everything Litmus Edge publishes and hands it to whoever subscribed. It does **not** collect, store or transform anything — that is handled by `ingestion/` and `storage/`.

Mosquitto rather than EMQX because the line produces under 200 events/hour on a single line. EMQX would be clustering and a management UI we have no use for.

## Topics

Telemetry, Sparkplug B:

```
spBv1.0/<SITE_ID>/DDATA/<edge_node>/<PRINTER_ID>
```

Discrete events, plain JSON:

```
sgx/<site>/<line>/printer/<printer_id>/event
sgx/<site>/<line>/printer/<printer_id>/marking
```

Sparkplug B is used for telemetry because its birth/death certificates (NBIRTH/NDEATH) give free "printer node offline" detection, which serves the live-state goal directly. A plain-MQTT design would need a heartbeat topic and custom timeout logic to get the same thing.

## Files

| File | Purpose |
|---|---|
| `config/mosquitto.conf` | Development config. Anonymous access, plaintext. |
| `config/mosquitto.conf.production.example` | Production template: TLS, credentials, ACLs. |

## Security note

The dev config allows anonymous connections. That is safe **only** because `docker-compose.yml` binds the broker to `127.0.0.1`, so it is unreachable from the network.

If you change that binding to expose the broker, switch to the production config first. On a site with no IT/OT firewall (README §10), an open broker on the plant network is a real exposure, not a theoretical one.

## Checking it works

```bash
# Subscribe to everything
docker compose exec broker mosquitto_sub -h localhost -t '#' -v

# Publish a test message from another terminal
docker compose exec broker mosquitto_pub -h localhost -t 'sgx/test' -m 'hello'
```
