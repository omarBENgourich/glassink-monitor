# notifier — alert delivery

**Composant :** service HTTP Python 3.12
**Rôle :** recevoir le webhook Grafana et diffuser les alertes.

## Why a service instead of Grafana's built-in contact points

Grafana can send email and Teams natively. It cannot send WhatsApp, and the production channel is not decided yet (README §11, question 4).

Keeping one webhook in Grafana and doing the fan-out here means **changing channel later changes this service, not the alert rules**. The alert logic — the valuable part — stays untouched.

```
Grafana alert ──webhook──> notifier ──> [ console | telegram | email | teams | whatsapp ]
```

Channels are selected with `NOTIFY_CHANNELS` in `.env`, comma-separated.

## Channel options

| Channel | Cost | Effort | Production-viable | Notes |
|---|---|---|---|---|
| `console` | — | none | no | Default. Logs to stdout, for development. |
| `telegram` | free | ~15 min | yes | Official Bot API, no ban risk. **Best for the prototype.** |
| `email` | free | ~15 min | yes | Boring, universal, works at 3am. |
| `teams` | included | ~30 min | yes | Saint-Gobain almost certainly runs Teams. **Most likely production answer** — confirm before building anything else. |
| `whatsapp` | free | ~1 hour | **no** | open-wa. Demo only, see below. |

## On open-wa

[open-wa](https://www.open-wa.org/) works and is genuinely free, but be clear about what it is: **browser automation of WhatsApp Web**, driving a real phone number's session. It is not an official API.

- Against WhatsApp's terms of service. The number can be banned with no warning and no appeal.
- Breaks when WhatsApp changes WhatsApp Web, without notice. **An alerting channel that dies silently is worse than none.**
- Requires QR-code login from a real phone and a persistent browser session on the server — on a plant network with no firewall (README §10), that is an always-on attack surface holding someone's personal WhatsApp session.
- No corporate IT department at this scale will approve it for production.

**Verdict:** good demo, bad answer. If you want WhatsApp delivery in the internship presentation, build it — behind this abstraction, and present it as one adapter among several, not as the production channel.

The official alternative is the **WhatsApp Business Cloud API**: free tier, Meta-supported, but needs business verification, a dedicated number and pre-approved message templates for outbound messages. Heavy for an internship, correct for production.

## Endpoints

| Endpoint | Purpose |
|---|---|
| `GET /health` | Liveness and enabled-channel list |
| `POST /webhook` | Grafana webhook receiver |
| `POST /test` | Sends a fixed test message through configured channels |

## Alert payload

Grafana posts its standard webhook body. The notifier needs to extract, at minimum:

- alert name and severity
- printer ID
- current value versus threshold
- whether the line was demanding prints (so idle-no-order never pages anyone)
- a link back to the relevant dashboard

## Files

```
notifier/
├── Dockerfile
└── src/
    ├── main.py            HTTP endpoint, /webhook + /health
    ├── formatting.py      Grafana payload -> human sentence
    └── channels/
        ├── console.py
        ├── telegram.py
        ├── email.py
        ├── teams.py
        └── whatsapp.py    open-wa bridge, demo only
```

No third-party Python packages are used. HTTP, SMTP, and webhook calls use the
standard library, reducing the patching surface on the plant network.

## Test it

```bash
curl http://localhost:8080/health
curl -X POST http://localhost:8080/test
docker compose logs --tail=10 notifier
```

## Rule for every channel

Messages go to humans on a factory floor at 3am. One sentence, plain language, the machine name first.

> `CIJ_Printer_L1: solvent will run out in about 5 hours (41% left, dropping 8%/h).`

Not a JSON dump, not a metric name, not a stack trace.
