"""Channel registry.

Adding a channel means adding a module with a send(title, lines) function and
listing it here. Grafana never has to know which one is in use.
"""
import logging
import os

from . import console, email, teams, telegram, whatsapp

log = logging.getLogger("notifier.channels")

_REGISTRY = {
    "console": console,
    "telegram": telegram,
    "email": email,
    "teams": teams,
    "whatsapp": whatsapp,
}


def enabled() -> list[str]:
    raw = os.getenv("NOTIFY_CHANNELS", "console")
    names = [n.strip().lower() for n in raw.split(",") if n.strip()]
    valid = []
    for name in names:
        if name not in _REGISTRY:
            log.warning("unknown channel %r, ignored", name)
            continue
        module = _REGISTRY[name]
        if not module.configured():
            log.warning("channel %r is listed but not configured, ignored", name)
            continue
        valid.append(name)
    return valid or ["console"]


def dispatch(title: str, lines: list[str]) -> dict:
    results = {}
    for name in enabled():
        try:
            _REGISTRY[name].send(title, lines)
            results[name] = "ok"
        except Exception as exc:
            log.exception("channel %s failed", name)
            results[name] = f"error: {exc}"
    return results
