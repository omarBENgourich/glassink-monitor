import datetime as dt
import unittest
from unittest.mock import patch

from src import config
from src.printer import (
    CIJPrinter,
    Consumable,
    JET_STATUS_CODE,
    STATE_RUNNING,
    STATE_WARMUP,
)


class ConsumableTests(unittest.TestCase):
    def test_effective_expiry_uses_earlier_opened_date(self):
        batch = Consumable(
            "solvent",
            level=80,
            expires_in_days=180,
            opened_days_ago=85,
        )

        self.assertEqual(
            batch.effective_expiry,
            dt.date.today() + dt.timedelta(days=5),
        )

    def test_idle_jet_consumes_solvent_but_not_ink(self):
        printer = CIJPrinter()
        printer.state = STATE_RUNNING
        printer.orders.demanding = False
        ink_before = printer.ink.level
        solvent_before = printer.solvent.level

        with patch.object(config, "SOLVENT_RATE_IDLE_JET_ON", 0.4):
            printer._step_consumables(1.0)

        self.assertEqual(printer.ink.level, ink_before)
        self.assertAlmostEqual(printer.solvent.level, solvent_before - 0.4)

    def test_94xx_fluid_capacities_match_site_study(self):
        batch = Consumable("ink", level=100, expires_in_days=180)

        self.assertEqual(batch.volume_ml, 800.0)
        self.assertEqual(config.INTERNAL_TANK_ML, 1075.0)

    def test_94xx_native_status_and_operating_fields(self):
        printer = CIJPrinter()
        printer.state = STATE_RUNNING
        printer.orders.demanding = True
        metrics = printer.telemetry()

        self.assertEqual(metrics["jet_status_code"], JET_STATUS_CODE[STATE_RUNNING])
        self.assertEqual(metrics["printing_status_code"], 1)
        self.assertEqual(metrics["external_cartridge_capacity_ml"], 800.0)
        self.assertEqual(metrics["internal_tank_capacity_ml"], 1075.0)
        self.assertIn("pressure_10mbar", metrics)
        self.assertIn("viscosity_tenth_second", metrics)

        printer.state = STATE_WARMUP
        self.assertEqual(printer.telemetry()["jet_status_code"], 1)


class ProductionTests(unittest.TestCase):
    def test_no_marking_without_demand(self):
        printer = CIJPrinter()
        printer.state = STATE_RUNNING
        printer.orders.demanding = False

        self.assertEqual(printer.markings(1.0), [])

    def test_marking_count_follows_throughput(self):
        printer = CIJPrinter()
        printer.state = STATE_RUNNING
        printer.orders.demanding = True

        with patch.object(config, "GLASSES_PER_HOUR", 180.0):
            markings = printer.markings(0.5)

        self.assertEqual(len(markings), 90)
        self.assertTrue(all("dmc" in item for item in markings))
        self.assertTrue(all("verify_grade" in item for item in markings))


if __name__ == "__main__":
    unittest.main()
