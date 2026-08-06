"""Greek registration tax (τέλος ταξινόμησης).

Two things make this module different from a lookup table.

**It is keyed on the projected registration date, not the purchase date.** A car
bought in December and registered in January pays January's rate. That gap is
exactly what destroys a margin everyone assumed was locked in, so the date is a
required argument rather than a default of "today".

**It reports which rule version it used.** When the law changes you must be able
to say under which rule a past decision was taken.

Reliability of what is encoded here: see docs/greece-registration-tax.md. The
depreciation table is ESTIMATED (secondary source reproducing decision
ΔΕΦΚΦ 1192035 ΕΞ 2017, ΦΕΚ Β' 4618/28.12.2017). The base rate is INDICATIVE —
a single visible knob standing in for a table we have not recovered, which is
why any decision resting on it comes out non-decisional.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Dict, List, Optional, Tuple

from .money import pct, round_money
from .reliability import Ledger, Reliability
from .vehicle import BodyType, Powertrain, Vehicle

# --- Age depreciation -----------------------------------------------------
#
# Percentage reduction of the taxable value, by half-year of age and by body
# type. Higher percentage means a lower taxable base, so less tax.
#
# Source: decision ΔΕΦΚΦ 1192035 ΕΞ 2017 (ΦΕΚ Β' 4618/28.12.2017), in force
# since 7 January 2018, reproduced from a Greek secondary source.
# NOT YET CONFIRMED as still current — verification number one.

_DEPRECIATION: Dict[BodyType, List[Tuple[str, str]]] = {}

_TABLE_ROWS: List[Tuple[str, str, str, str, str, str, str]] = [
    # age,  suv,   hatch, saloon, cabrio, coupe, mpv
    ("0.5", "11", "9", "15", "11", "12", "9"),
    ("1.0", "22", "19", "30", "22", "25", "19"),
    ("1.5", "25", "24", "33", "26", "25", "23"),
    ("2.0", "29", "28", "36", "30", "29", "27"),
    ("2.5", "35", "32", "40", "33", "32", "33"),
    ("3.0", "37", "37", "43", "36", "36", "36"),
    ("3.5", "44", "43", "50", "42", "41", "43"),
    ("4.0", "50", "49", "57", "48", "47", "49"),
    ("4.5", "56", "55", "64", "54", "53", "55"),
    ("5.0", "62", "61", "72", "60", "59", "61"),
    ("5.5", "66", "64", "74", "64", "63", "64"),
    ("6.0", "68", "67", "76", "67", "66", "67"),
    ("6.5", "71", "70", "78", "69", "68", "70"),
    ("7.0", "73", "72", "80", "72", "71", "72"),
    ("7.5", "75", "74", "81", "74", "73", "75"),
    ("8.0", "77", "76", "83", "76", "75", "77"),
    ("8.5", "79", "78", "84", "78", "77", "78"),
    ("9.0", "80", "80", "85", "79", "79", "80"),
    ("9.5", "82", "81", "86", "81", "80", "82"),
    ("10.0", "83", "83", "87", "82", "82", "83"),
    ("10.5", "84", "83", "88", "83", "83", "84"),
    ("11.0", "85", "84", "89", "84", "84", "85"),
    ("11.5", "86", "85", "89", "85", "85", "86"),
    ("12.0", "87", "86", "90", "86", "86", "87"),
    ("12.5", "88", "87", "90", "87", "87", "88"),
    ("13.0", "88", "88", "90", "88", "87", "89"),
    ("13.5", "89", "89", "91", "88", "88", "89"),
    ("14.0", "90", "89", "91", "89", "89", "90"),
    ("14.5", "90", "90", "91", "89", "89", "91"),
    ("15.0", "90", "90", "91", "90", "89", "91"),
    ("15.5", "90", "90", "91", "90", "89", "91"),
    ("16.0", "95", "95", "95", "95", "95", "95"),
]

_COLUMN_ORDER = [
    BodyType.SUV_4X4,
    BodyType.HATCHBACK,
    BodyType.SALOON,
    BodyType.CABRIOLET,
    BodyType.COUPE_ROADSTER,
    BodyType.MPV,
]

for _row in _TABLE_ROWS:
    _age = _row[0]
    for _idx, _body in enumerate(_COLUMN_ORDER):
        _DEPRECIATION.setdefault(_body, []).append((_age, _row[_idx + 1]))


def age_depreciation(body_type: BodyType, age_years: Decimal) -> Decimal:
    """Reduction of taxable value for a vehicle's age, as a fraction.

    The table is graduated in half-years. A vehicle between two steps takes the
    step it has actually reached — being one day short of three years does not
    earn the three-year reduction.
    """
    rows = _DEPRECIATION[body_type]
    applicable = Decimal("0")
    for age_str, pct_str in rows:
        if age_years >= Decimal(age_str):
            applicable = pct(pct_str)
        else:
            break
    return applicable


# --- Hybrid relief, which changes on 1 January 2027 -----------------------


@dataclass(frozen=True)
class HybridRelief:
    version: str
    valid_from: date
    valid_until: Optional[date]

    def reduction_for(self, vehicle: Vehicle) -> Decimal:
        raise NotImplementedError


@dataclass(frozen=True)
class HybridReliefUntil2026(HybridRelief):
    """Until 31/12/2026: 75% relief, reserved for hybrids at or under 50 g/km."""

    def reduction_for(self, vehicle: Vehicle) -> Decimal:
        if vehicle.powertrain not in (Powertrain.HYBRID, Powertrain.PLUGIN_HYBRID):
            return Decimal("0")
        return pct("75") if vehicle.co2_wltp <= 50 else Decimal("0")


@dataclass(frozen=True)
class HybridReliefFrom2027(HybridRelief):
    """From 01/01/2027: a flat 50% for every hybrid.

    The efficient ones therefore see their tax double, which is the whole point
    of computing at the registration date.
    """

    def reduction_for(self, vehicle: Vehicle) -> Decimal:
        if vehicle.powertrain not in (Powertrain.HYBRID, Powertrain.PLUGIN_HYBRID):
            return Decimal("0")
        return pct("50")


_HYBRID_RULES: List[HybridRelief] = [
    HybridReliefUntil2026(
        version="hybrid-relief-2018",
        valid_from=date(2018, 1, 1),
        valid_until=date(2026, 12, 31),
    ),
    HybridReliefFrom2027(
        version="hybrid-relief-2027",
        valid_from=date(2027, 1, 1),
        valid_until=None,
    ),
]


def hybrid_rule_at(moment: date) -> HybridRelief:
    for rule in _HYBRID_RULES:
        if rule.valid_from <= moment and (rule.valid_until is None or moment <= rule.valid_until):
            return rule
    raise ValueError("no hybrid relief rule covers {}".format(moment))


def next_rule_change_after(moment: date) -> Optional[date]:
    """The next date on which the hybrid rule changes, if any.

    Used to warn that a deal is only profitable if registration happens before
    a given day.
    """
    upcoming = [r.valid_from for r in _HYBRID_RULES if r.valid_from > moment]
    return min(upcoming) if upcoming else None


# --- CO2 adjustment -------------------------------------------------------

_CO2_BANDS: List[Tuple[Optional[int], Optional[int], str]] = [
    (None, 130, "-5"),
    (156, 182, "10"),
    (182, 208, "20"),
    (208, 234, "30"),
    (234, 260, "40"),
    (260, 325, "60"),
    (325, None, "100"),
]


def co2_adjustment(co2_wltp: int) -> Decimal:
    """Adjustment to the base rate, as a fraction. Zero between 130 and 156.

    The 130–156 band does not appear in the sources consulted; treated as
    neutral, and flagged as missing in the documentation.
    """
    for low, high, adj in _CO2_BANDS:
        if low is None and co2_wltp <= high:  # type: ignore[operator]
            return pct(adj)
        if high is None and co2_wltp > low:  # type: ignore[operator]
            return pct(adj)
        if low is not None and high is not None and low < co2_wltp <= high:
            return pct(adj)
    return Decimal("0")


# --- The calculation ------------------------------------------------------


@dataclass(frozen=True)
class TaxAssumptions:
    """The knobs standing in for tables we have not recovered.

    ``base_rate`` replaces the official table by engine size and Euro standard.
    One visible, adjustable knob is more honest than a fabricated table: nobody
    forgets a knob is provisional.
    """

    base_rate: Decimal
    base_rate_reliability: Reliability = Reliability.INDICATIVE


@dataclass(frozen=True)
class TaxResult:
    taxable_value: Decimal
    registration_tax: Decimal
    age_reduction: Decimal
    co2_adjustment: Decimal
    hybrid_reduction: Decimal
    rule_version: str
    registration_date: date
    ledger: Ledger


def registration_tax(
    vehicle: Vehicle,
    *,
    registration_date: date,
    pre_tax_retail_value: Decimal,
    assumptions: TaxAssumptions,
    transport_and_insurance: Decimal = Decimal("0"),
) -> TaxResult:
    """Greek registration tax at a given registration date.

    ``registration_date`` has no default on purpose: the caller must state when
    the car will actually be registered, because that is what the rate depends
    on.
    """
    ledger = Ledger()

    age = vehicle.age_years_at(registration_date)
    reduction = age_depreciation(vehicle.body_type, age)
    ledger.record(
        "dépréciation par âge",
        Reliability.ESTIMATED,
        "ΔΕΦΚΦ 1192035 ΕΞ 2017 (table 2017, à confirmer)",
    )
    # Mileage compounds with age in the official rules; we do not have that
    # table, so a high-mileage car is over-taxed by this approximation.
    ledger.record("dépréciation kilométrique", Reliability.MISSING, "table non retrouvée")

    taxable = pre_tax_retail_value * (Decimal("1") - reduction) + transport_and_insurance

    adj = co2_adjustment(vehicle.co2_wltp)
    ledger.record("ajustement CO2", Reliability.ESTIMATED, "barème WLTP post-2021")

    rule = hybrid_rule_at(registration_date)
    hybrid = rule.reduction_for(vehicle)
    ledger.record("régime hybride", Reliability.ESTIMATED, rule.version)

    ledger.record(
        "taux de base",
        assumptions.base_rate_reliability,
        "paramètre provisoire — table officielle non retrouvée",
    )

    rate = assumptions.base_rate * (Decimal("1") + adj) * (Decimal("1") - hybrid)
    tax = round_money(taxable * rate)

    return TaxResult(
        taxable_value=round_money(taxable),
        registration_tax=tax,
        age_reduction=reduction,
        co2_adjustment=adj,
        hybrid_reduction=hybrid,
        rule_version=rule.version,
        registration_date=registration_date,
        ledger=ledger,
    )
