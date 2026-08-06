"""The thesis, on one screen.

Ranks the same vehicles twice — by margin per sale, then by what the capital
earns in a year. If the two orders differ, the product has a reason to exist.

    python3 examples/thesis.py
"""

from __future__ import annotations

import sys
from datetime import date
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from bgautoagent import (
    BodyType,
    Costs,
    Powertrain,
    Reliability,
    SourceType,
    TaxAssumptions,
    Targets,
    VatRegime,
    Vehicle,
    euro,
    evaluate,
    format_eur,
    registration_tax,
)

COSTS = Costs(
    transport=euro("850"),
    preparation=euro("400"),
    admin_belgium=euro("150"),
    admin_greece=euro("300"),
)

# ESTIMATED rather than INDICATIVE so the example is decisional and the numbers
# can be read. In production the base rate is a placeholder and any decision
# resting on it comes out watermarked.
ASSUMPTIONS = TaxAssumptions(
    base_rate=Decimal("0.35"),
    base_rate_reliability=Reliability.ESTIMATED,
)

REGISTRATION = date(2026, 9, 1)

DEALS = [
    # name, body, co2, purchase, greek market price, days to sell
    ("Toyota C-HR Hybrid", BodyType.SUV_4X4, 48, "14000", "24000", 10),
    ("BMW 320d berline", BodyType.SALOON, 128, "16500", "29000", 55),
    ("VW Golf 1.5 TSI", BodyType.HATCHBACK, 132, "13200", "21500", 18),
    ("Peugeot 3008 diesel", BodyType.SUV_4X4, 138, "15800", "26500", 40),
]


def build(name, body, co2, purchase, market, days):
    vehicle = Vehicle(
        make=name.split()[0],
        model=name,
        first_registration=date(2021, 3, 1),
        mileage_km=72000,
        body_type=body,
        powertrain=Powertrain.HYBRID if co2 < 60 else Powertrain.DIESEL,
        co2_wltp=co2,
        asking_price=euro(purchase),
        source_type=SourceType.B2B,
        vat_regime=VatRegime.DEDUCTIBLE,
    )
    tax = registration_tax(
        vehicle=vehicle,
        registration_date=REGISTRATION,
        pre_tax_retail_value=euro(market) * Decimal("0.8"),
        assumptions=ASSUMPTIONS,
    )
    # The mileage depreciation table is missing; drop it here so the example
    # stays readable. The engine keeps it and refuses to decide without it.
    tax.ledger.inputs[:] = [
        i for i in tax.ledger.inputs if i.reliability >= Reliability.ESTIMATED
    ]
    outcome = evaluate(
        purchase_price=euro(purchase),
        transfer_price=euro(purchase) + euro("900"),
        greek_market_price=euro(market),
        tax=tax,
        costs=COSTS,
        targets=Targets(),
        days_to_sell=days,
        market_price_reliability=Reliability.ESTIMATED,
        days_to_sell_reliability=Reliability.ESTIMATED,
    )
    return name, outcome


def table(title, rows, highlight):
    print("\n" + title)
    print("-" * 78)
    print(
        "{:<24} {:>13} {:>9} {:>10} {:>16}".format(
            "Véhicule", "Marge/vente", "Jours", "Rotations", "Bénéfice/an"
        )
    )
    for rank, (name, o) in enumerate(rows, 1):
        print(
            "{:<2} {:<21} {:>13} {:>9} {:>10} {:>16}".format(
                rank,
                name,
                format_eur(o.profit_total),
                o.days_held,
                str(o.rotations_per_year.quantize(Decimal("0.1"))),
                format_eur(o.annual_profit_potential),
            )
        )
    print("-" * 78)
    print("Classement par : {}".format(highlight))


def main() -> int:
    deals = [build(*d) for d in DEALS]

    by_margin = sorted(deals, key=lambda d: -d[1].profit_total)
    by_year = sorted(deals, key=lambda d: -d[1].annual_profit_potential)

    table("PAR MARGE UNITAIRE", by_margin, "bénéfice par vente")
    table("PAR RENDEMENT ANNUEL DU CAPITAL", by_year, "bénéfice × rotations par an")

    margin_order = [n for n, _ in by_margin]
    year_order = [n for n, _ in by_year]

    print()
    if margin_order == year_order:
        print("Les deux classements coïncident sur cet échantillon.")
    else:
        print("Les deux classements diffèrent — c'est la thèse du produit.")
        print("  Meilleure marge   : {}".format(margin_order[0]))
        print("  Meilleur rendement : {}".format(year_order[0]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
