"""Configuration, all from environment variables."""
import os


def _f(name: str, default: float) -> float:
    return float(os.getenv(name, default))


def _i(name: str, default: int) -> int:
    return int(os.getenv(name, default))


# --- connection --------------------------------------------------------------
MQTT_HOST = os.getenv("MQTT_HOST", "localhost")
MQTT_PORT = _i("MQTT_PORT", 1883)

# --- asset identity ----------------------------------------------------------
SITE_ID = os.getenv("SITE_ID", "SaintGobain_SiteX")
LINE_ID = os.getenv("LINE_ID", "L1")
PRINTER_ID = os.getenv("PRINTER_ID", "CIJ_Printer_L1")
VENDOR = os.getenv("PRINTER_VENDOR", "Markem-Imaje")
MODEL = os.getenv("PRINTER_MODEL", "9450c")

# --- pacing ------------------------------------------------------------------
PUBLISH_INTERVAL_S = _f("PUBLISH_INTERVAL_S", 5.0)

# Simulated time runs faster than real time, otherwise a demo shows nothing:
# ink drains at 0.8 %/hour, so at 1x you would watch for a day to see anything.
# At 60x, one real minute is one simulated hour.
TIME_ACCEL = _f("TIME_ACCEL", 60.0)

# --- process parameters ------------------------------------------------------
# Confirmed: under 200 glasses/hour on one line.
GLASSES_PER_HOUR = _f("GLASSES_PER_HOUR", 180.0)

# Consumable burn rates, % of a full cartridge per simulated hour.
INK_RATE_PRINTING = _f("INK_RATE_PRINTING", 0.8)
SOLVENT_RATE_PRINTING = _f("SOLVENT_RATE_PRINTING", 1.2)
# A CIJ jet left running still evaporates solvent with no production at all.
SOLVENT_RATE_IDLE_JET_ON = _f("SOLVENT_RATE_IDLE_JET_ON", 0.4)

# Markem-Imaje 94xx fluid system. The supplied site study documents 800 mL
# external cartridges and 1.075 L internal tanks. Tank height remains a
# calibration value until a real 9450c payload is available.
EXTERNAL_CARTRIDGE_ML = _f("EXTERNAL_CARTRIDGE_ML", 800.0)
INTERNAL_TANK_ML = _f("INTERNAL_TANK_ML", 1075.0)
INTERNAL_TANK_FULL_MM = _f("INTERNAL_TANK_FULL_MM", 100.0)
INTERNAL_RESERVE_HOURS = _f("INTERNAL_RESERVE_HOURS", 24.0)

VISCOSITY_SETPOINT = _f("VISCOSITY_SETPOINT", 4.2)
VISCOSITY_BAND = _f("VISCOSITY_BAND", 0.3)

HEAD_PRESSURE_SETPOINT = _f("HEAD_PRESSURE_SETPOINT", 3.0)
HEAD_TEMP_SETPOINT = _f("HEAD_TEMP_SETPOINT", 38.0)
CABINET_TEMP_SETPOINT = _f("CABINET_TEMP_SETPOINT", 25.0)
MOTOR_SPEED_RPM = _f("MOTOR_SPEED_RPM", 3000.0)

# Operator refills at this level.
REFILL_THRESHOLD_PCT = _f("REFILL_THRESHOLD_PCT", 15.0)

# Vendor figure, still unconfirmed (README §11).
SHELF_LIFE_AFTER_OPEN_DAYS = _i("SHELF_LIFE_AFTER_OPEN_DAYS", 90)

# --- order-driven demand -----------------------------------------------------
# Production is 24/5 but the machine idles when no client order calls for that
# glass. These are simulated hours.
ORDER_RUN_MIN_H = _f("ORDER_RUN_MIN_H", 2.0)
ORDER_RUN_MAX_H = _f("ORDER_RUN_MAX_H", 8.0)
ORDER_GAP_MIN_H = _f("ORDER_GAP_MIN_H", 0.5)
ORDER_GAP_MAX_H = _f("ORDER_GAP_MAX_H", 3.0)

# --- faults ------------------------------------------------------------------
MEAN_HOURS_BETWEEN_FAULTS = _f("MEAN_HOURS_BETWEEN_FAULTS", 8.0)

# Occasionally stop publishing entirely, to exercise the "node offline" alert.
DROPOUT_PROBABILITY = _f("DROPOUT_PROBABILITY", 0.002)
DROPOUT_DURATION_S = _f("DROPOUT_DURATION_S", 180.0)

# --- topics ------------------------------------------------------------------
BASE_TOPIC = f"sgx/{SITE_ID}/{LINE_ID}/printer/{PRINTER_ID}"
TOPIC_TELEMETRY = f"{BASE_TOPIC}/telemetry"
TOPIC_EVENT = f"{BASE_TOPIC}/event"
TOPIC_MARKING = f"{BASE_TOPIC}/marking"
