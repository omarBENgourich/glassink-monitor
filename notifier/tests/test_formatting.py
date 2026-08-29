import unittest

from src.formatting import format_alert, format_payload


class FormattingTests(unittest.TestCase):
    def test_firing_alert_starts_with_printer(self):
        alert = {
            "status": "firing",
            "labels": {
                "alertname": "Consumable expiring",
                "printer_id": "CIJ_Printer_L1",
            },
            "annotations": {"summary": "solvent expires in 5 days"},
        }

        self.assertEqual(
            format_alert(alert),
            "CIJ_Printer_L1 : solvent expires in 5 days",
        )

    def test_resolved_alert_is_explicit(self):
        alert = {
            "status": "resolved",
            "labels": {"printer_id": "CIJ_Printer_L1"},
            "annotations": {"summary": "printer is online"},
        }

        self.assertEqual(
            format_alert(alert),
            "CIJ_Printer_L1 : RÉSOLU - printer is online",
        )

    def test_payload_groups_multiple_alerts(self):
        payload = {
            "status": "firing",
            "alerts": [
                {"status": "firing", "labels": {"alertname": "A"}},
                {"status": "firing", "labels": {"alertname": "B"}},
            ],
        }

        title, lines = format_payload(payload)

        self.assertEqual(title, "2 alertes actives")
        self.assertEqual(len(lines), 2)

    def test_unresolved_grafana_template_is_never_forwarded(self):
        alert = {
            "status": "resolved",
            "labels": {
                "alertname": "Consommable proche de l’expiration",
                "printer_id": "CIJ_Printer_L1",
                "consumable_type": "Solvant",
            },
            "annotations": {
                "summary": (
                    "{{ $labels.consumable_type }} batch expires in "
                    "{{ printf \"%.0f\" $values.A.Value }} days"
                )
            },
            "values": {"A": 5, "C": 0},
        }

        message = format_alert(alert)

        self.assertEqual(
            message,
            "CIJ_Printer_L1 : RÉSOLU - Le lot de Solvant expire dans 5 jours",
        )
        self.assertNotIn("{{", message)


if __name__ == "__main__":
    unittest.main()
