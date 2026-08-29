"""Turn a Grafana webhook payload into sentences a human can act on.

These messages reach people on a factory floor, sometimes at 3am. One sentence,
plain language, machine name first. Not a JSON dump, not a metric name.
"""


def _pick_value(alert: dict) -> str:
    values = alert.get("values") or {}
    if not values:
        return ""
    # Grafana names query stages A, B, C... The last one is normally the
    # thresholded value, which is the number worth showing.
    key = sorted(values)[-1]
    value = values[key]
    if isinstance(value, (int, float)):
        return f"{value:.1f}".rstrip("0").rstrip(".")
    return str(value)


def _query_value(alert: dict, ref: str = "A") -> str:
    value = (alert.get("values") or {}).get(ref)
    if isinstance(value, (int, float)):
        return f"{value:.1f}".rstrip("0").rstrip(".")
    return str(value) if value is not None else ""


def _fallback_body(alert: dict, name: str, labels: dict) -> str:
    """Build useful text when Grafana leaves annotation templates unresolved."""
    fluid = labels.get("consumable_type", "consumable")
    value = _query_value(alert)

    if name in ("Consommable bientôt épuisé", "Consumable running out"):
        return f"{fluid} sera épuisé dans environ {value or '?'} heures"
    if name in ("Niveau de consommable bas", "Consumable level low"):
        return f"{fluid} : niveau à {value or '?'}%"
    if name in ("Consommable proche de l’expiration", "Consumable expiring"):
        return f"Le lot de {fluid} expire dans {value or '?'} jours"
    if name in ("Consommable expiré", "Consumable past use-by date"):
        return f"Le lot de {fluid} a expiré depuis {value or '?'} jours"
    if name in ("Viscosité de l’encre hors plage", "Ink viscosity out of band"):
        return f"L’écart de viscosité est de {value or '?'} par rapport à la consigne"
    if name in ("Aucune donnée de l’imprimante", "No data from the printer"):
        return f"Aucune télémétrie depuis {value or '?'} secondes"
    if name in (
        "Imprimante arrêtée malgré une demande d’impression",
        "Printer stopped while the line needs prints",
    ):
        return (
            "L’imprimante ne fonctionne pas alors que la ligne "
            "demande des impressions"
        )

    return f"{name}{f' ({value})' if value else ''}"


def format_alert(alert: dict) -> str:
    labels = alert.get("labels") or {}
    annotations = alert.get("annotations") or {}

    printer = (labels.get("printer_id")
               or labels.get("printer")
               or "printer")
    name = labels.get("alertname", "Alert")
    status = alert.get("status", "firing")

    summary = annotations.get("summary") or annotations.get("description")
    # Grafana can preserve the literal template when a no-data alert resolves
    # and the former label set is no longer available. Never forward braces to
    # the person receiving the alert.
    if summary and "{{" not in summary and "}}" not in summary:
        body = summary
    else:
        body = _fallback_body(alert, name, labels)

    if status == "resolved":
        return f"{printer} : RÉSOLU - {body}"
    return f"{printer} : {body}"


def format_payload(payload: dict) -> tuple[str, list[str]]:
    """Returns (title, [one line per alert])."""
    alerts = payload.get("alerts") or []
    lines = [format_alert(a) for a in alerts]

    status = payload.get("status", "firing")
    firing = sum(1 for a in alerts if a.get("status") == "firing")

    if status == "resolved":
        title = "Résolu"
    elif firing > 1:
        title = f"{firing} alertes actives"
    else:
        title = "Alerte"

    if not lines:
        lines = [payload.get("message") or "aucun détail disponible"]

    return title, lines
