"""Log to stdout. Default channel, and the one used during development."""
import logging

log = logging.getLogger("notifier.console")


def configured() -> bool:
    return True


def send(title: str, lines: list[str]) -> None:
    log.warning("[%s]", title)
    for line in lines:
        log.warning("    %s", line)
