# simulator — synthetic CIJ printer

**Composant :** Python 3.12 et paho-mqtt
**Rôle :** publier une télémétrie réaliste de Markem-Imaje 9450c sans accès au site.

## Principe

Le simulateur remplace la sortie MQTT de Litmus Edge pendant les essais locaux.
Il permet de valider l'ingestion, le stockage, les tableaux de bord et les
alertes sans connexion à la ligne de production.

Le raccordement réel consiste ensuite à mapper les tags Litmus Edge sur ce
contrat de télémétrie.

## Comportements reproduits

Le scénario couvre aussi les périodes sans commande et les défauts.

| Behaviour | Why it matters |
|---|---|
| **Order-driven idle gaps** | Production is 24/5 but the machine stops when no client order calls for that glass. If the simulator always produces, the demand-gating logic (README §7.1) is never tested and false alarms surface for the first time on the real line. |
| Ink and solvent draining at a realistic rate, with **refill jumps** | Exercises Node-RED's rolling depletion forecast and its reset after refill. |
| **Refills carry a batch code and a use-by date** | Exercises the expiry clock and the consumable history in InfluxDB. |
| Solvent consumed **even when idle with the jet on** | A CIJ jet left running still evaporates solvent. If consumption is tied only to print count, the forecast is wrong during idle periods. |
| Viscosity noise plus slow drift | Drives the viscosity-drift alert. |
| Injected faults with codes and durations | Drives fault Pareto, MTBF, downtime. |
| State machine: `shutdown → warmup → running → stopped/fault` | Real CIJ printers do not jump straight to running; warmup takes minutes. |
| Occasional **node death** (stop publishing) | Tests the Sparkplug NDEATH / no-data alert. |

## Paramètres initiaux

Les capacités et les codes natifs proviennent de l'étude de la Markem-Imaje
9450c réalisée sur le site. Les débits restent réglables jusqu'à leur mesure sur
la ligne.

| Parameter | Value | Note |
|---|---|---|
| Throughput | ~180 glasses/hour | Under 200/hour, one line — confirmed. |
| Publish interval | 5 s | Adjust once the Litmus Edge publish rate is known. |
| External cartridge | 800 mL | Ink and additive cartridge capacity documented for the 94xx. |
| Internal tank | 1.075 L | Internal ink and additive reserve. |
| Internal reserve | approximately 24 h | Operating reserve documented for empty external cartridges. |
| Ink consumption | ~0.8 %/hour while printing | |
| Solvent consumption | ~1.2 %/hour printing, ~0.4 %/hour jet-on-idle | Evaporation continues without printing. |
| Viscosity setpoint | 4.2 (vendor units) | Band ±0.3. |
| Order gaps | 0-3 hours, several times per day | The behaviour that breaks naive availability. |
| Fault rate | ~1 per 8 hours | Mostly short; occasional long one. |
| Fluid shelf life | 12 months sealed, 90 days after opening | Configurable operating assumption. |

## Signaux 94xx ajoutés

En complément des champs utilisés par Grafana, la télémétrie publie les états
natifs du jet et de l'impression ainsi que les paramètres de la réponse 94xx :

- `jet_status_code` : 0 arrêt, 1 démarrage, 7 jet actif ;
- `printing_status_code` : 0 pause, 1 impression, 2 non prête ;
- vitesse et consigne moteur en tr/min ;
- pression et consigne par pas de 10 mbar ;
- viscosité en dixièmes de seconde ;
- températures électronique, encre et tête ;
- niveaux des réservoirs en mm et quantité interne en mL ;
- consommation totale d'additif et autonomie d'encre.

## Start it

```bash
docker compose --profile phase2 up -d simulator
```

## Topics published

```
sgx/<SITE_ID>/<LINE_ID>/printer/<PRINTER_ID>/telemetry
sgx/<SITE_ID>/<LINE_ID>/printer/<PRINTER_ID>/event
sgx/<SITE_ID>/<LINE_ID>/printer/<PRINTER_ID>/marking
```

Payload shapes are documented in `../ingestion/README.md`.

The prototype publishes plain JSON plus an MQTT last-will event. The real Litmus
feed may use Sparkplug B protobuf. That conversion belongs at the ingestion
boundary and does not change the database or dashboards.

Every payload includes a unique `message_id`. An exact MQTT QoS 1 replay keeps
the same measurement, tags, and timestamp, so InfluxDB overwrites the point
rather than creating a duplicate.

## Files

```
simulator/
├── Dockerfile
├── requirements.txt
└── src/
    ├── main.py          entry point and publish loop
    ├── printer.py       CIJ state machine and consumable physics
    ├── orders.py        order-driven demand signal with idle gaps
    ├── faults.py        fault injection with realistic codes
    └── config.py        environment-driven parameters
```

`TIME_ACCEL=60` makes one real minute represent one simulated hour so a short
demonstration exercises consumption, order gaps, refills, and faults.
