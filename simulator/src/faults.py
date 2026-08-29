"""Fault injection.

Codes and descriptions are in the style of a Markem-Imaje 9000-series CIJ. They
are plausible rather than authoritative — the real code list comes with the tag
list (README §11). What matters for the platform is the shape: a code, a
description, a duration, and whether the line was demanding prints at the time.
"""
import random

# code, description, mean duration in simulated minutes, weight
FAULT_CATALOGUE = [
    ("E-042", "Ink pressure out of range", 7, 20),
    ("E-051", "Ink viscosity out of range", 12, 15),
    ("E-073", "Nozzle partially blocked", 18, 12),
    ("E-088", "Gutter fault, ink not returning", 25, 8),
    ("E-067", "Printhead cover open", 3, 18),
    ("E-095", "Print trigger missed", 4, 15),
    ("E-110", "Charge electrode contaminated", 30, 6),
    ("E-121", "Pump pressure low", 45, 3),
    ("E-134", "Ambient temperature out of range", 20, 3),
]

# Faults that stop production until somebody intervenes.
BLOCKING_FAULTS = {
    "E-001": "Ink cartridge empty",
    "E-002": "Solvent cartridge empty",
    "E-101": "Consumable past use-by date",
}

_WEIGHTS = [f[3] for f in FAULT_CATALOGUE]


def sample_fault() -> tuple[str, str, float]:
    """Pick a random fault. Returns (code, description, duration_hours)."""
    code, description, mean_min, _ = random.choices(FAULT_CATALOGUE, _WEIGHTS)[0]
    # Exponential: most faults are short, occasionally one drags on.
    duration_min = max(1.0, random.expovariate(1.0 / mean_min))
    return code, description, duration_min / 60.0


def should_fault(dt_h: float, mean_hours_between: float) -> bool:
    """Poisson arrival over dt_h simulated hours."""
    if mean_hours_between <= 0:
        return False
    return random.random() < (dt_h / mean_hours_between)
