"""Microsoft Teams incoming webhook.

Most likely production answer: a company this size already runs Teams, so
there is no new tool to get approved and no new account for anyone to manage.

Setup: in the target Teams channel, Connectors -> Incoming Webhook -> copy the
URL into TEAMS_WEBHOOK_URL.
"""
import json
import logging
import os
import urllib.request

log = logging.getLogger("notifier.teams")


def configured() -> bool:
    return bool(os.getenv("TEAMS_WEBHOOK_URL"))


def send(title: str, lines: list[str]) -> None:
    url = os.environ["TEAMS_WEBHOOK_URL"]

    card = {
        "@type": "MessageCard",
        "@context": "https://schema.org/extensions",
        "summary": title,
        "themeColor": "D93F3F" if "RESOLVED" not in " ".join(lines) else "2EB886",
        "title": title,
        "text": "\n\n".join(lines),
    }

    request = urllib.request.Request(
        url,
        data=json.dumps(card).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=10) as response:
        if response.status not in (200, 202):
            raise RuntimeError(f"teams returned {response.status}")
    log.info("sent to teams")
