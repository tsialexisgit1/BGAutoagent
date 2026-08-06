"""Money handling.

Every monetary amount in this package is a :class:`decimal.Decimal`, never a
float. Floats cannot represent 0.10 exactly; the error is invisible on one
figure and accumulates across a landed-cost calculation with a dozen terms. On
a margin of a few hundred euros per vehicle, that is not acceptable.
"""

from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from typing import Union

Amount = Decimal

CENT = Decimal("0.01")


def euro(value: Union[str, int, Decimal]) -> Decimal:
    """Build a monetary amount.

    Accepts str, int or Decimal — deliberately not float, so that a float
    cannot enter the calculation by accident through this door.
    """
    if isinstance(value, float):  # pragma: no cover - guarded by typing too
        raise TypeError(
            "refusing a float for a monetary amount; pass a string such as "
            'euro("15200.00")'
        )
    return Decimal(value)


def round_money(value: Decimal) -> Decimal:
    """Round to the cent, half up — the convention used on invoices."""
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


def pct(value: Union[str, int, Decimal]) -> Decimal:
    """Build a percentage as a fraction: pct("7.5") -> Decimal('0.075')."""
    return Decimal(value) / Decimal(100)


def format_eur(value: Decimal) -> str:
    """Render an amount the way it is written in Belgium and Greece."""
    rounded = round_money(value)
    whole, _, frac = str(abs(rounded)).partition(".")
    groups = []
    while len(whole) > 3:
        groups.insert(0, whole[-3:])
        whole = whole[:-3]
    groups.insert(0, whole)
    sign = "-" if rounded < 0 else ""
    return "{}{},{} €".format(sign, " ".join(groups), (frac + "00")[:2])
