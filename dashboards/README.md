# dashboards — visualisation and alerting

**Composant :** Grafana 11
**Rôle :** tableaux de bord et moteur d'alertes.

## Access

<http://localhost:3000> — credentials from `.env` (`GRAFANA_ADMIN_USER` / `GRAFANA_ADMIN_PASSWORD`).

The InfluxDB 2.x Flux datasource is provisioned automatically and marked as the default.

## Layout

```
dashboards/
├── provisioning/
│   ├── datasources/influxdb.yml      auto-configured Flux datasource
│   └── dashboards/dashboards.yml     loads JSON from definitions/
└── definitions/                      dashboard JSON, version-controlled
```

Dashboards are files, not database rows. Edit in the browser while building, then **export the JSON back into `definitions/`** — otherwise the change is lost when the container restarts.

## The three dashboards

One per audience. Building one dashboard for everyone produces something nobody uses.

### 1. Operator — `operator.json`

Readable from across the room. Almost no text.

- Printer state as one large coloured tile
- Ink and solvent as gauges, each with **hours remaining**, not just a percentage
- Current fault in plain language, or nothing at all
- Nothing else. Resist adding anything else.

### 2. Maintenance — `maintenance.json`

The working view.

- Consumable levels with consumption trend and predicted empty time
- **Consumable status table**: level, hours-to-empty, days-to-expiry, and which clock wins
- Viscosity against setpoint, with the acceptable band shaded
- Head pressure and temperature
- Hours since last service; filter and pump hours remaining
- Fault log, newest first
- Fault Pareto over 30 days

### 3. Management — `management.json`

Summary only, no raw telemetry.

- Availability per day and per week — **demand-gated**
- Total downtime, trending
- Top five fault causes by lost time
- Glasses marked per shift

## Alert rules

| Alert | Condition | To |
|---|---|---|
| Ink low | level < 20% **or** `hours_to_empty` < 8 | maintenance |
| Solvent low | level < 20% **or** `hours_to_empty` < 8 | maintenance |
| Consumable expiring | expiry-limited and fewer than 14 days left | maintenance |
| Consumable expired | days-to-expiry below zero | maintenance + quality |
| Viscosity drift | outside setpoint band > 15 min | maintenance |
| Head temperature | outside operating band | maintenance |
| Printer fault | fault active > 2 min **while demanding** | operators + maintenance |
| Printer stopped | stopped > 5 min **while demanding** | operators |
| Node offline | no data for 2 min | engineering |
| Service due | filter or pump hours below threshold | maintenance |

### The rule behind the rules

Every downtime condition is gated on the `classification` tag written by Node-RED. `idle_no_order` never pages an operator.

Production is order-driven with no shift calendar. An alert that wakes someone at 3am because there was no client order is an alert that gets muted — and once muted, the real one is missed too. This is the difference between a system people trust and a system people ignore.

## Delivery

Alerts go to a **single webhook contact point** pointing at the `notifier/` service, which fans out to Telegram, email, Teams or WhatsApp. See `../notifier/README.md` for why.

## Verify

From the project root:

```bash
python3 dashboards/verify.py
```

This confirms that all three dashboards are provisioned, executes all 23 Flux
panel queries, and evaluates the complete A/B/C query chain of all seven alerts.
