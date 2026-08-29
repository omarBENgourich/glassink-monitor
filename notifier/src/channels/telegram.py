"""Telegram Bot API.

Official, free, no ban risk, and roughly fifteen minutes to set up:
  1. Message @BotFather, /newbot, keep the token.
  2. Add the bot to a group (or message it directly).
  3. Read the chat id from
     https://api.telegram.org/bot<TOKEN>/getUpdates
  4. Put TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID in .env.

Recommended channel for the prototype.
"""
import json
import logging
import os
import urllib.request

log = logging.getLogger("notifier.telegram")

API = "https://api.telegram.org/bot{token}/sendMessage"


def configured() -> bool:
    return bool(os.getenv("TELEGRAM_BOT_TOKEN") and os.getenv("TELEGRAM_CHAT_ID"))


def send(title: str, lines: list[str]) -> None:
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    chat_id = os.environ["TELEGRAM_CHAT_ID"]

    text = f"*{title}*\n" + "\n".join(f"• {line}" for line in lines)
    body = json.dumps({
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "Markdown",
        "disable_web_page_preview": True,
    }).encode()

    request = urllib.request.Request(
        API.format(token=token),
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=10) as response:
        if response.status != 200:
            raise RuntimeError(f"telegram returned {response.status}")
    log.info("sent to telegram chat %s", chat_id)
