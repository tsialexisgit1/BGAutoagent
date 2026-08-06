"""The BG Score.

Five components out of 100, weighted. Rotation carries the most weight because
the business is an exercise in turning capital over, not in maximising the
margin on any one car.

The weights are **hypotheses, not settings**. 35/30/15/10/10 is a reasonable
intuition and nothing more; it is exposed as an argument precisely so that
watching the ranking move as it changes can tell you which components actually
matter.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Dict

from .financials import Outcome
from .money import pct


@dataclass(frozen=True)
class Weights:
    rotation: Decimal = pct("35")
    profitability: Decimal = pct("30")
    mechanical_risk: Decimal = pct("15")
    refurbishment_risk: Decimal = pct("10")
    tax_exposure: Decimal = pct("10")

    def validate(self) -> None:
        total = (
            self.rotation
            + self.profitability
            + self.mechanical_risk
            + self.refurbishment_risk
            + self.tax_exposure
        )
        if abs(total - Decimal("1")) > Decimal("0.0001"):
            raise ValueError("weights must sum to 100%, got {}".format(total * 100))


@dataclass(frozen=True)
class RiskInputs:
    """Judgement scores, 0–100, higher is better.

    These are the fields where a language model earns its place: reading a free
    text history or an inspection report and turning it into a number. They are
    not arithmetic, which is why they arrive as inputs rather than being derived
    here.
    """

    mechanical: int
    refurbishment: int


@dataclass(frozen=True)
class Score:
    total: int
    components: Dict[str, Decimal]
    weights: Weights


def _clamp(value: Decimal) -> Decimal:
    return max(Decimal("0"), min(Decimal("100"), value))


def rotation_score(days_held: int, *, target_days: int = 45, ceiling_days: int = 150) -> Decimal:
    """100 at or below the target, 0 at the ceiling, linear between.

    Note this scores **days held**, not days on sale: transport, customs and
    registration tie the capital up before the car can even be offered. With
    roughly three weeks of paperwork, a 45-day target is what makes "sold in ten
    days" — the stated ideal — actually score full marks. Scoring days on sale
    instead would flatter every deal by the length of the admin.
    """
    if days_held <= target_days:
        return Decimal("100")
    if days_held >= ceiling_days:
        return Decimal("0")
    span = Decimal(ceiling_days - target_days)
    return _clamp(Decimal("100") * (Decimal(ceiling_days - days_held) / span))


def profitability_score(outcome: Outcome, *, roi_for_full_marks: Decimal = Decimal("0.40")) -> Decimal:
    """Built on annualised ROI, not on the margin.

    Using the margin here would let a fat, slow deal score well twice — once on
    profitability and again on nothing else — and the whole point is that a slow
    deal is a worse deal.
    """
    if not outcome.meets_all_targets:
        # Failing a floor is not a matter of degree.
        return Decimal("0")
    ratio = outcome.annualised_roi / roi_for_full_marks
    return _clamp(ratio * Decimal("100"))


def tax_exposure_score(
    *,
    co2_wltp: int,
    straddles_rule_change: bool,
    tax_share_of_capital: Decimal,
) -> Decimal:
    """Penalises a heavy tax bill, and a deal sitting across a rule change.

    The straddle penalty is deliberately blunt: a deal whose profitability
    depends on registering before a deadline is a different animal from one that
    does not, and averaging that away would hide it.
    """
    base = _clamp(Decimal("100") - (tax_share_of_capital * Decimal("200")))
    if co2_wltp > 200:
        base = _clamp(base - Decimal("15"))
    if straddles_rule_change:
        base = _clamp(base - Decimal("30"))
    return base


def bg_score(
    *,
    outcome: Outcome,
    risks: RiskInputs,
    co2_wltp: int,
    registration_tax: Decimal,
    straddles_rule_change: bool,
    weights: Weights = Weights(),
) -> Score:
    weights.validate()

    tax_share = (
        registration_tax / outcome.capital_employed
        if outcome.capital_employed > 0
        else Decimal("0")
    )

    components = {
        "rotation": rotation_score(outcome.days_held),
        "profitability": profitability_score(outcome),
        "mechanical_risk": _clamp(Decimal(risks.mechanical)),
        "refurbishment_risk": _clamp(Decimal(risks.refurbishment)),
        "tax_exposure": tax_exposure_score(
            co2_wltp=co2_wltp,
            straddles_rule_change=straddles_rule_change,
            tax_share_of_capital=tax_share,
        ),
    }

    total = (
        components["rotation"] * weights.rotation
        + components["profitability"] * weights.profitability
        + components["mechanical_risk"] * weights.mechanical_risk
        + components["refurbishment_risk"] * weights.refurbishment_risk
        + components["tax_exposure"] * weights.tax_exposure
    )

    return Score(total=int(total.to_integral_value()), components=components, weights=weights)
