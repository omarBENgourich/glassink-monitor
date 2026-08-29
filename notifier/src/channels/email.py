"""SMTP email.

Boring, universal, and it still works at 3am when nothing else does. Worth
enabling alongside whichever chat channel is chosen.
"""
import logging
import os
import smtplib
from email.message import EmailMessage

log = logging.getLogger("notifier.email")


def configured() -> bool:
    return bool(os.getenv("SMTP_HOST") and os.getenv("SMTP_TO"))


def send(title: str, lines: list[str]) -> None:
    host = os.environ["SMTP_HOST"]
    port = int(os.getenv("SMTP_PORT", 587))
    user = os.getenv("SMTP_USER")
    password = os.getenv("SMTP_PASSWORD")
    recipients = [r.strip() for r in os.environ["SMTP_TO"].split(",") if r.strip()]

    message = EmailMessage()
    message["Subject"] = f"[Printer] {title}"
    message["From"] = user or "printer-monitoring@localhost"
    message["To"] = ", ".join(recipients)
    message.set_content("\n".join(lines))

    with smtplib.SMTP(host, port, timeout=15) as smtp:
        smtp.ehlo()
        if smtp.has_extn("starttls"):
            smtp.starttls()
            smtp.ehlo()
        if user and password:
            smtp.login(user, password)
        smtp.send_message(message)

    log.info("sent email to %s", recipients)
