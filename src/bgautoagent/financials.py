"""The financial picture of one vehicle, across both companies.

The chain is: the Belgian company buys, sells on to the Greek company at a
transfer price; the Greek company imports, registers, and sells to a Greek
private buyer.

Nothing here is an estimate made by the engine. Every assumption arrives as an
explicit argument, so that a figure can be reproduced years later by feeding the
same assumptions back in.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Optional

from .money import round_money
from .reliability import Ledger, Reliability, combine
from .greek_tax import TaxResult


@dataclass(frozen=True)
class Costs:
    """Everything between buying in Belgium and handing over the keys in Greece."""

    transport: Decimal
    preparation: Decimal
    admin_belgium: Decimal
    admin_greece: Decimal

    @property
    def belgium_side(self) -> Decimal:
        return self.admin_belgium

    @property
    def greece_side(self) -> Decimal:
        return self.transport + self.preparation + self.admin_greece


@dataclass(frozen=True)
class Targets:
    """The thresholds the business will not go below."""

    min_profit_belgium: Decimal = Decimal("750")
    min_profit_greece: Decimal = Decimal("3000")
    min_roi_greece: Decimal = Decimal("0.25")
    safety_margin: Decimal = Decimal("0.075")
    """Haircut on the Greek market price.

    Greek listings show asking prices, not transaction prices — systematically
    optimistic. 7.5% is the midpoint of the 5–10% range; it belongs per model
    rather than globally once real sales data exists to calibrate it.
    """


@dataclass(frozen=True)
class Outcome:
    purchase_price: Decimal
    transfer_price: Decimal
    prudent_resale: Decimal

    profit_belgium: Decimal
    profit_greece: Decimal
    profit_total: Decimal

    capital_employed: Decimal
    roi_greece: Decimal
    roi_total: Decimal

    days_held: int
    rotations_per_year: Decimal
    annual_profit_potential: Decimal
    annualised_roi: Decimal

    meets_belgium_target: bool
    meets_greece_profit_target: bool
    meets_greece_roi_target: bool
    ledger: Ledger

    @property
    def meets_all_targets(self) -> bool:
        return (
            self.meets_belgium_target
            and self.meets_greece_profit_target
            and self.meets_greece_roi_target
        )


def evaluate(
    *,
    purchase_price: Decimal,
    transfer_price: Decimal,
    greek_market_price: Decimal,
    tax: TaxResult,
    costs: Costs,
    targets: Targets,
    days_to_sell: int,
    days_admin: int = 21,
    market_price_reliability: Reliability = Reliability.INDICATIVE,
    days_to_sell_reliability: Reliability = Reliability.INDICATIVE,
) -> Outcome:
    """Work out both margins, the ROI, and what the capital earns in a year.

    ``days_admin`` covers transport, customs and registration — the period the
    capital is tied up before the car can even be offered for sale. It is part
    of the rotation whether or not anyone is looking at the car.
    """
    ledger = combine(tax.ledger)
    ledger.record("prix de marché grec", market_price_reliability, "référence marché")
    ledger.record("délai de vente", days_to_sell_reliability, "rotation estimée")

    prudent_resale = round_money(greek_market_price * (Decimal("1") - targets.safety_margin))

    profit_be = round_money(transfer_price - purchase_price - costs.belgium_side)

    greek_outlay = transfer_price + costs.greece_side + tax.registration_tax
    profit_gr = round_money(prudent_resale - greek_outlay)

    profit_total = round_money(profit_be + profit_gr)

    # Capital employed is what the group actually puts on the table: the car
    # plus every cost incurred before the sale. The transfer price is internal
    # and would double-count.
    capital = purchase_price + costs.belgium_side + costs.greece_side + tax.registration_tax

    roi_gr = (profit_gr / greek_outlay) if greek_outlay > 0 else Decimal("0")
    roi_total = (profit_total / capital) if capital > 0 else Decimal("0")

    days_held = max(1, days_to_sell + days_admin)
    rotations = Decimal(365) / Decimal(days_held)

    # The figure the whole thesis rests on: a car earning less per sale can earn
    # more per year if the capital comes back sooner.
    annual_profit = round_money(profit_total * rotations)
    annualised_roi = roi_total * rotations

    return Outcome(
        purchase_price=purchase_price,
        transfer_price=transfer_price,
        prudent_resale=prudent_resale,
        profit_belgium=profit_be,
        profit_greece=profit_gr,
        profit_total=profit_total,
        capital_employed=round_money(capital),
        roi_greece=roi_gr,
        roi_total=roi_total,
        days_held=days_held,
        rotations_per_year=rotations,
        annual_profit_potential=annual_profit,
        annualised_roi=annualised_roi,
        meets_belgium_target=profit_be >= targets.min_profit_belgium,
        meets_greece_profit_target=profit_gr >= targets.min_profit_greece,
        meets_greece_roi_target=roi_gr >= targets.min_roi_greece,
        ledger=ledger,
    )


def max_purchase_price(
    *,
    greek_market_price: Decimal,
    tax: TaxResult,
    costs: Costs,
    targets: Targets,
) -> Decimal:
    """The most that can be paid in Belgium while still clearing every target.

    Solvable in closed form because the Greek registration tax is assessed on a
    reference retail value, not on what we pay — so raising our bid does not
    raise the tax.

    Two constraints bind the transfer price, and the tighter one wins:
      profit >= min_profit_greece
      profit >= min_roi_greece * greek_outlay
    """
    prudent_resale = greek_market_price * (Decimal("1") - targets.safety_margin)
    greek_fixed = costs.greece_side + tax.registration_tax

    by_profit = prudent_resale - greek_fixed - targets.min_profit_greece

    one_plus_roi = Decimal("1") + targets.min_roi_greece
    by_roi = (prudent_resale - greek_fixed * one_plus_roi) / one_plus_roi

    max_transfer = min(by_profit, by_roi)
    ceiling = max_transfer - targets.min_profit_belgium - costs.belgium_side

    return round_money(max(ceiling, Decimal("0")))
