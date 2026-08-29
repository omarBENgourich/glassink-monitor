"""Order-driven demand signal.

Production is 24/5, but the printer is idle whenever no client order calls for
that glass. There is no shift calendar to key off, so availability has to be
measured against this signal instead of wall-clock time (README §7.1).

Reproducing the gaps matters: if the simulator always produces, the
demand-gating logic is never exercised and false alarms would first appear on
the real line.
"""
import random

from . import config


class OrderGenerator:
    """Alternates between 'an order is running' and 'nothing to make'."""

    def __init__(self) -> None:
        self.demanding = True
        self._remaining_h = random.uniform(
            config.ORDER_RUN_MIN_H, config.ORDER_RUN_MAX_H
        )
        self.product_ref = self._new_product_ref()

    @staticmethod
    def _new_product_ref() -> str:
        # Windscreen references, roughly in the style used for automotive glass.
        return f"WS-{random.randint(1000, 9999)}-{random.choice('ABCDEF')}"

    def step(self, dt_h: float) -> bool:
        """Advance by dt_h simulated hours. Returns True if the state flipped."""
        self._remaining_h -= dt_h
        if self._remaining_h > 0:
            return False

        self.demanding = not self.demanding
        if self.demanding:
            self._remaining_h = random.uniform(
                config.ORDER_RUN_MIN_H, config.ORDER_RUN_MAX_H
            )
            self.product_ref = self._new_product_ref()
        else:
            self._remaining_h = random.uniform(
                config.ORDER_GAP_MIN_H, config.ORDER_GAP_MAX_H
            )
        return True
