"""The one question the agent answers: buy, or not.

Two gates sit in front of the score, and both can override it.

**The reliability gate.** A verdict resting on anything marked INDICATIVE or
worse never says BUY, whatever the score. It comes out watermarked instead. The
figure is still useful — it is how the engine gets tested before the data is
good — but a decision built on a placeholder is not a decision.

**The targets gate.** Missing a floor is not a matter of degree. A car that
fails the Greek ROI target is not a 78 to be negotiated; it is a no.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from enum import Enum
from typing import List, Optional

from .financials import Outcome
from .greek_tax import TaxResult, next_rule_change_after
from .reliability import Ledger
from .scoring import Score


class Verdict(Enum):
    BUY_NOW = "acheter_immediatement"
    BUY_IF_PRICE_HOLDS = "acheter_si_prix_conforme"
    NEGOTIATE = "negocier"
    REJECT = "rejeter"
    NOT_DECISIONAL = "non_decisionnel"

    @property
    def label(self) -> str:
        return {
            "acheter_immediatement": "ACHETER immédiatement",
            "acheter_si_prix_conforme": "ACHETER si le prix est conforme",
            "negocier": "NÉGOCIER",
            "rejeter": "REJETER",
            "non_decisionnel": "NON DÉCISIONNEL",
        }[self.value]


@dataclass(frozen=True)
class Decision:
    verdict: Verdict
    score: int
    reasons: List[str]
    warnings: List[str]
    is_decisional: bool
    ledger: Ledger

    @property
    def is_buy(self) -> bool:
        return self.verdict in (Verdict.BUY_NOW, Verdict.BUY_IF_PRICE_HOLDS)


def _verdict_from_score(score: int) -> Verdict:
    if score >= 90:
        return Verdict.BUY_NOW
    if score >= 80:
        return Verdict.BUY_IF_PRICE_HOLDS
    if score >= 70:
        return Verdict.NEGOTIATE
    return Verdict.REJECT


def decide(
    *,
    outcome: Outcome,
    score: Score,
    tax: TaxResult,
    max_price: Decimal,
    asking_price: Decimal,
    expected_registration: date,
) -> Decision:
    reasons: List[str] = []
    warnings: List[str] = []

    # --- Deadline straddle ------------------------------------------------
    # Worth a warning even when the deal passes: it changes what "profitable"
    # means from a fact into a condition on a date.
    change = next_rule_change_after(tax.registration_date)
    if change is not None:
        sale_end_estimate = date.fromordinal(
            expected_registration.toordinal() + outcome.days_held
        )
        if sale_end_estimate >= change:
            warnings.append(
                "Rentable seulement si l'immatriculation intervient avant le "
                "{} — le régime change ce jour-là.".format(change.strftime("%d/%m/%Y"))
            )

    # --- Targets ----------------------------------------------------------
    if not outcome.meets_belgium_target:
        reasons.append("Marge belge sous le plancher de 750 €.")
    if not outcome.meets_greece_profit_target:
        reasons.append("Bénéfice grec sous le plancher de 3 000 €.")
    if not outcome.meets_greece_roi_target:
        reasons.append("ROI grec sous les 25 % exigés.")

    if asking_price > max_price:
        reasons.append(
            "Prix demandé au-dessus du prix maximal d'achat "
            "({} > {}).".format(asking_price, max_price)
        )

    # --- Reliability ------------------------------------------------------
    decisional = outcome.ledger.is_decisional
    if not decisional:
        warnings.append(outcome.ledger.explain())
        return Decision(
            verdict=Verdict.NOT_DECISIONAL,
            score=score.total,
            reasons=reasons,
            warnings=warnings,
            is_decisional=False,
            ledger=outcome.ledger,
        )

    if reasons:
        return Decision(
            verdict=Verdict.REJECT,
            score=score.total,
            reasons=reasons,
            warnings=warnings,
            is_decisional=True,
            ledger=outcome.ledger,
        )

    verdict = _verdict_from_score(score.total)
    reasons.append(
        "Rendement annuel du capital : {} € sur {} rotations.".format(
            outcome.annual_profit_potential,
            outcome.rotations_per_year.quantize(Decimal("0.1")),
        )
    )

    return Decision(
        verdict=verdict,
        score=score.total,
        reasons=reasons,
        warnings=warnings,
        is_decisional=True,
        ledger=outcome.ledger,
    )
