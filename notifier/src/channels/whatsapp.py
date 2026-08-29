"""WhatsApp via open-wa — DEMO ONLY.

open-wa (https://www.open-wa.org/) drives WhatsApp Web through browser
automation using a real phone number's session. It is not an official API.

Before enabling this, understand what it costs:
  * It is against WhatsApp's terms of service. The number can be banned with
    no warning and no appeal.
  * It breaks when WhatsApp changes WhatsApp Web, without notice. An alerting
    channel that dies silently is worse than having no alerting channel.
  * It needs a QR-code login from a real phone and a persistent browser session
    on the server. On a plant network with no firewall (README §10) that is an
    always-on attack surface holding somebody's personal WhatsApp session.
  * No corporate IT department at this scale will approve it for production.

Good for a presentation. Not the production answer. The official route is the
WhatsApp Business Cloud API: free tier, Meta-supported, but it needs business
verification, a dedicated number and pre-approved message templates.

Assumes an open-wa EASY API server is running separately:
    npx @open-wa/wa-automate --api-host 0.0.0.0 --port 8085 --key <KEY>
"""
import json
import logging
import os
import urllib.request

log = logging.getLogger("notifier.whatsapp")


def configured() -> bool:
    return bool(os.getenv("OPENWA_URL") and os.getenv("OPENWA_CHAT_ID"))


def send(title: str, lines: list[str]) -> None:
    url = os.environ["OPENWA_URL"].rstrip("/") + "/sendText"
    chat_id = os.environ["OPENWA_CHAT_ID"]     # e.g. 33612345678@c.us
    key = os.getenv("OPENWA_API_KEY", "")

    text = f"*{title}*\n" + "\n".join(f"- {line}" for line in lines)

    headers = {"Content-Type": "application/json"}
    if key:
        headers["api_key"] = key

    request = urllib.request.Request(
        url,
        data=json.dumps({"args": {"to": chat_id, "content": text}}).encode(),
        headers=headers,
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=15) as response:
        if response.status != 200:
            raise RuntimeError(f"open-wa returned {response.status}")
    log.info("sent to whatsapp %s", chat_id)
