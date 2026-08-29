"""CIJ printer model: state machine, consumable physics, print quality.

Deliberately reproduces the awkward cases, not a clean run:
  * idle gaps driven by orders, not by a schedule
  * solvent evaporating while the jet idles with no production
  * a starting solvent batch that is already near its effective expiry
  * refill batches that occasionally expire before they can be used up
"""
import datetime as dt
import random

from . import config, faults
from .orders import OrderGenerator

STATE_SHUTDOWN = "shutdown"
STATE_WARMUP = "warmup"
STATE_RUNNING = "running"
STATE_STOPPED = "stopped"
STATE_FAULT = "fault"

# Numeric encoding keeps the MQTT telemetry fields stable for InfluxDB. Event
# points still carry the human-readable state transitions.
STATE_CODE = {
    STATE_SHUTDOWN: 0,
    STATE_WARMUP: 1,
    STATE_RUNNING: 2,
    STATE_STOPPED: 3,
    STATE_FAULT: 4,
}

# Native 94xx status values documented in the supplied site study. The
# platform state code above remains stable because dashboards already depend on
# it; these fields reproduce the printer protocol alongside it.
JET_STATUS_CODE = {
    STATE_SHUTDOWN: 0,  # jet stopped
    STATE_WARMUP: 1,    # jet starting
    STATE_RUNNING: 7,   # jet running
    STATE_STOPPED: 0,
    STATE_FAULT: 0,
}

WARMUP_HOURS = 0.1  # ~6 simulated minutes, CIJ printers do not start instantly


class Consumable:
    """One fitted ink or solvent batch."""

    def __init__(self, kind: str, level: float, expires_in_days: int,
                 opened_days_ago: int = 0):
        today = dt.date.today()
        self.kind = kind
        self.level = level
        self.part_number = "MI-1234-Q" if kind == "ink" else "MI-9876-S"
        self.batch_code = f"LOT-{random.choice('ABCDEFGH')}{random.randint(10, 99)}"
        self.expires_on = today + dt.timedelta(days=expires_in_days)
        self.manufactured_on = self.expires_on - dt.timedelta(days=365)
        self.opened_on = today - dt.timedelta(days=opened_days_ago)
        self.shelf_life_after_open_days = config.SHELF_LIFE_AFTER_OPEN_DAYS
        self.volume_ml = config.EXTERNAL_CARTRIDGE_ML

    @property
    def effective_expiry(self) -> dt.date:
        """Opened fluid degrades faster than the printed use-by date implies."""
        return min(
            self.expires_on,
            self.opened_on + dt.timedelta(days=self.shelf_life_after_open_days),
        )

    @property
    def expired(self) -> bool:
        return self.effective_expiry <= dt.date.today()

    def payload(self) -> dict:
        return {
            "consumable_type": self.kind,
            "part_number": self.part_number,
            "batch_code": self.batch_code,
            "manufactured_on": self.manufactured_on.isoformat(),
            "expires_on": self.expires_on.isoformat(),
            "opened_on": self.opened_on.isoformat(),
            "shelf_life_after_open_days": self.shelf_life_after_open_days,
            "volume_ml": self.volume_ml,
        }


def _new_batch(kind: str) -> Consumable:
    """A fresh cartridge. Sometimes one that will expire before it is used up."""
    if random.random() < 0.15:
        # Old stock off the shelf. Drives pct_likely_wasted in the database.
        return Consumable(kind, 100.0, expires_in_days=random.randint(20, 45))
    return Consumable(kind, 100.0, expires_in_days=random.randint(300, 500))


class CIJPrinter:
    def __init__(self) -> None:
        self.state = STATE_SHUTDOWN
        self.orders = OrderGenerator()

        # Ink is fresh. Solvent was opened 85 days ago against a 90-day
        # after-open life, so its effective expiry is ~5 days away even though
        # the bottle says two months. This exercises the expiry alert almost
        # immediately, which is the point.
        self.ink = Consumable("ink", 78.0, expires_in_days=180, opened_days_ago=12)
        self.solvent = Consumable("solvent", 64.0, expires_in_days=55,
                                  opened_days_ago=85)

        self.viscosity = config.VISCOSITY_SETPOINT
        self._viscosity_drift = 0.0
        self.print_count = 184_200
        self.jet_run_hours = 4_180.0
        self.pump_run_hours = 9_640.0
        self.filter_hours_remaining = 610.0
        self.cover_open = False
        self.total_additive_consumption_cc = 12_480.0

        self._warmup_left = 0.0
        self._fault_left = 0.0
        self._fault_code: str | None = None
        self._fault_desc: str | None = None
        self._blocking = False
        self._serial = 0
        self._marking_debt = 0.0

        self.events: list[dict] = []

    # -- helpers --------------------------------------------------------------
    @property
    def demanding(self) -> bool:
        return self.orders.demanding

    @property
    def producing(self) -> bool:
        return self.state == STATE_RUNNING and self.demanding

    @property
    def jet_running(self) -> bool:
        return self.state in (STATE_RUNNING, STATE_WARMUP)

    def _emit(self, event_type: str, **fields) -> None:
        self.events.append({
            "event_type": event_type,
            "demanding": self.demanding,
            **fields,
        })

    def _set_state(self, new_state: str) -> None:
        if new_state == self.state:
            return
        self._emit("state_change", from_state=self.state, to_state=new_state)
        self.state = new_state

    # -- main step ------------------------------------------------------------
    def step(self, dt_h: float) -> None:
        """Advance the model by dt_h simulated hours."""
        if self.orders.step(dt_h):
            self._emit(
                "operator",
                code="ORDER_START" if self.demanding else "ORDER_END",
                description=(
                    f"Order {self.orders.product_ref} started"
                    if self.demanding else "No order queued"
                ),
            )

        self._step_consumables(dt_h)
        self._step_state(dt_h)
        self._step_process(dt_h)

    # -- consumables ----------------------------------------------------------
    def _step_consumables(self, dt_h: float) -> None:
        solvent_before = self.solvent.level
        if self.producing:
            self.ink.level -= config.INK_RATE_PRINTING * dt_h
            self.solvent.level -= config.SOLVENT_RATE_PRINTING * dt_h
        elif self.state == STATE_RUNNING:
            # Jet on, nothing to print. Solvent still evaporates — this is why
            # consumption cannot be derived from print count alone.
            self.solvent.level -= config.SOLVENT_RATE_IDLE_JET_ON * dt_h

        self.ink.level = max(0.0, self.ink.level)
        self.solvent.level = max(0.0, self.solvent.level)
        self.total_additive_consumption_cc += max(
            0.0,
            solvent_before - self.solvent.level,
        ) * config.EXTERNAL_CARTRIDGE_ML / 100.0

        for name in ("ink", "solvent"):
            c: Consumable = getattr(self, name)
            if c.level <= config.REFILL_THRESHOLD_PCT or c.expired:
                self._refill(name, expired=c.expired and c.level > config.REFILL_THRESHOLD_PCT)

    def _refill(self, name: str, expired: bool) -> None:
        old: Consumable = getattr(self, name)
        new = _new_batch(name)
        setattr(self, name, new)
        self._emit(
            "refill",
            code="REFILL_EXPIRED" if expired else "REFILL_LOW",
            description=(
                f"{name} batch {old.batch_code} replaced "
                f"({'past use-by date' if expired else f'{old.level:.0f}% remaining'})"
            ),
            **new.payload(),
        )
        if name == "ink":
            self.filter_hours_remaining = max(0.0, self.filter_hours_remaining - 5)

    # -- state machine --------------------------------------------------------
    def _step_state(self, dt_h: float) -> None:
        # Blocking conditions first: these override everything else.
        if self.ink.level <= 0.01:
            self._enter_fault("E-001", faults.BLOCKING_FAULTS["E-001"], blocking=True)
            return
        if self.solvent.level <= 0.01:
            self._enter_fault("E-002", faults.BLOCKING_FAULTS["E-002"], blocking=True)
            return

        if self.state == STATE_FAULT:
            self._fault_left -= dt_h
            if self._fault_left <= 0 and not self._blocking:
                self._close_fault()
                self._set_state(STATE_RUNNING)
            elif self._blocking:
                # Cleared by the refill in _step_consumables on the next tick.
                self._blocking = False
                self._close_fault()
                self._set_state(STATE_WARMUP)
                self._warmup_left = WARMUP_HOURS
            return

        if self.state == STATE_SHUTDOWN:
            self._set_state(STATE_WARMUP)
            self._warmup_left = WARMUP_HOURS
            return

        if self.state == STATE_WARMUP:
            self._warmup_left -= dt_h
            if self._warmup_left <= 0:
                self._set_state(STATE_RUNNING)
            return

        if self.state == STATE_STOPPED:
            # Restarted as soon as there is something to print again.
            if self.demanding:
                self._set_state(STATE_WARMUP)
                self._warmup_left = WARMUP_HOURS
            return

        # Running.
        if faults.should_fault(dt_h, config.MEAN_HOURS_BETWEEN_FAULTS):
            code, desc, duration = faults.sample_fault()
            self._enter_fault(code, desc, duration_h=duration)
            return

        if not self.demanding and random.random() < dt_h * 0.35:
            # Sometimes the operator shuts the printer down during a long gap;
            # the rest of the time the jet is left running. Both are normal, and
            # the database must classify them differently from downtime.
            self._set_state(STATE_STOPPED)

    def _enter_fault(self, code: str, desc: str, duration_h: float = 0.0,
                     blocking: bool = False) -> None:
        if self.state == STATE_FAULT:
            return
        self._set_state(STATE_FAULT)
        self._fault_code, self._fault_desc = code, desc
        self._fault_left = duration_h
        self._blocking = blocking
        self._fault_started_h = 0.0
        self._emit("fault", code=code, description=desc,
                   duration_s=int(duration_h * 3600) if duration_h else None)

    def _close_fault(self) -> None:
        self._fault_code = self._fault_desc = None

    # -- process variables ----------------------------------------------------
    def _step_process(self, dt_h: float) -> None:
        # Viscosity wanders, and is pulled back toward setpoint by the printer's
        # own solvent addition — unless it is faulted.
        self._viscosity_drift += random.gauss(0, 0.02) * dt_h
        self._viscosity_drift *= 0.98
        pull = 0.0 if self.state == STATE_FAULT else -0.4 * (
            self.viscosity - config.VISCOSITY_SETPOINT
        ) * dt_h
        self.viscosity += self._viscosity_drift + pull + random.gauss(0, 0.01)

        if self.jet_running:
            self.jet_run_hours += dt_h
            self.pump_run_hours += dt_h
            self.filter_hours_remaining = max(0.0, self.filter_hours_remaining - dt_h)

        self.cover_open = self._fault_code == "E-067"

    # -- outputs --------------------------------------------------------------
    def telemetry(self) -> dict:
        viscosity_error = abs(self.viscosity - config.VISCOSITY_SETPOINT)
        pressure_bar = (
            config.HEAD_PRESSURE_SETPOINT
            + viscosity_error * 0.5
            + random.gauss(0, 0.03)
        )
        head_temperature = (
            config.HEAD_TEMP_SETPOINT + random.gauss(0, 0.4)
            + (2.5 if self.state == STATE_FAULT else 0.0)
        )
        ink_rate_ml_h = (
            config.INK_RATE_PRINTING * config.EXTERNAL_CARTRIDGE_ML / 100.0
        )
        time_left_ink_h = (
            self.ink.level * config.EXTERNAL_CARTRIDGE_ML / 100.0 / ink_rate_ml_h
            if ink_rate_ml_h > 0 else 0.0
        )
        printing_status = 1 if self.producing else (0 if self.jet_running else 2)
        return {
            "printer_state_code": STATE_CODE[self.state],
            "jet_status_code": JET_STATUS_CODE[self.state],
            "printing_status_code": printing_status,
            "jet_running": 1 if self.jet_running else 0,
            "line_demanding": 1 if self.demanding else 0,
            "ink_level": round(self.ink.level, 2),
            "solvent_level": round(self.solvent.level, 2),
            "ink_viscosity": round(self.viscosity, 3),
            "head_pressure": round(pressure_bar, 3),
            "head_temperature": round(head_temperature, 2),
            "cabinet_temperature": round(
                config.CABINET_TEMP_SETPOINT + random.gauss(0, 1.2), 2),
            "electronic_temperature": round(
                config.CABINET_TEMP_SETPOINT + 5.0 + random.gauss(0, 0.6), 2),
            "ink_temperature": round(head_temperature - 1.5, 2),
            "printhead_cover_open": 1 if self.cover_open else 0,
            "print_count": self.print_count,
            "jet_run_hours": round(self.jet_run_hours, 2),
            "pump_run_hours": round(self.pump_run_hours, 2),
            "filter_hours_remaining": round(self.filter_hours_remaining, 1),
            "ink_days_to_expiry": (self.ink.effective_expiry - dt.date.today()).days,
            "solvent_days_to_expiry": (
                self.solvent.effective_expiry - dt.date.today()).days,
            # Native-style 94xx operating values from the 84-byte parameter
            # response documented in the site study.
            "motor_speed_rpm": round(
                config.MOTOR_SPEED_RPM + random.gauss(0, 8.0)
                if self.jet_running else 0.0, 1),
            "motor_speed_target_rpm": config.MOTOR_SPEED_RPM,
            "pressure_10mbar": round(pressure_bar * 100),
            "pressure_target_10mbar": round(
                config.HEAD_PRESSURE_SETPOINT * 100),
            "viscosity_tenth_second": round(self.viscosity * 10),
            "ink_tank_level_mm": round(
                self.ink.level * config.INTERNAL_TANK_FULL_MM / 100.0, 1),
            "additive_tank_level_mm": round(
                self.solvent.level * config.INTERNAL_TANK_FULL_MM / 100.0, 1),
            "ink_internal_tank_ml": round(
                self.ink.level * config.INTERNAL_TANK_ML / 100.0, 1),
            "additive_internal_tank_ml": round(
                self.solvent.level * config.INTERNAL_TANK_ML / 100.0, 1),
            "external_cartridge_capacity_ml": config.EXTERNAL_CARTRIDGE_ML,
            "internal_tank_capacity_ml": config.INTERNAL_TANK_ML,
            "internal_reserve_hours": config.INTERNAL_RESERVE_HOURS,
            "current_tube_level_mm": round(
                45.0 + random.gauss(0, 0.4) if self.jet_running else 0.0, 1),
            "total_additive_consumption_cc": round(
                self.total_additive_consumption_cc, 1),
            "time_left_ink_tenth_hours": round(time_left_ink_h * 10),
            "average_ink_consumption_cc_per_tenth_hour": round(
                ink_rate_ml_h / 10.0, 3),
            "viscosity_management_state": 0,
            "ink_autonomy_display": 1,
            "additive_cartridge_absent": 0,
            "additive_pump_pressure_tenth_bar": round(pressure_bar * 10),
            "ink_circuit_solenoid_state": 1 if self.jet_running else 0,
            "head_solenoid_state": 1 if self.jet_running else 0,
        }

    def markings(self, dt_h: float) -> list[dict]:
        """Glasses marked during this interval."""
        if not self.producing:
            return []

        self._marking_debt += config.GLASSES_PER_HOUR * dt_h
        count = int(self._marking_debt)
        self._marking_debt -= count

        out = []
        for _ in range(count):
            self._serial += 1
            self.print_count += 1
            out.append(self._one_marking())
        return out

    def _one_marking(self) -> dict:
        stamp = dt.date.today().strftime("%y%m%d")
        dmc = f"SGX{config.LINE_ID}{stamp}{self._serial:06d}"

        # Print quality degrades with viscosity error and with old fluid — the
        # correlation that makes the telemetry-plus-traceability join worth
        # having in one database.
        error = abs(self.viscosity - config.VISCOSITY_SETPOINT)
        penalty = min(0.35, error / config.VISCOSITY_BAND * 0.15)
        if self.ink.expired:
            penalty += 0.25

        print_ok = random.random() > 0.002
        roll = random.random() + penalty
        if roll < 0.85:
            grade = "A"
        elif roll < 0.95:
            grade = "B"
        elif roll < 0.99:
            grade = "C"
        elif roll < 1.05:
            grade = "D"
        else:
            grade = "F"

        return {
            "dmc": dmc,
            "product_ref": self.orders.product_ref,
            "print_ok": print_ok,
            "verify_ok": print_ok and grade in ("A", "B", "C"),
            "verify_grade": grade,
        }

    def fitted_consumable_events(self) -> list[dict]:
        """Announce the batches already in the machine at startup.

        Without this the consumable table stays empty until the first refill,
        so expiry is unknown for hours. A real printer reports its fitted
        cartridges on connection; this is the equivalent.
        """
        out = []
        for name in ("ink", "solvent"):
            c: Consumable = getattr(self, name)
            out.append({
                "event_type": "refill",
                "demanding": self.demanding,
                "code": "FITTED",
                "description": f"{name} batch {c.batch_code} in service at startup",
                **c.payload(),
            })
        return out

    def drain_events(self) -> list[dict]:
        out, self.events = self.events, []
        return out
