"""Tests for the decision engine.

Standard library only, run with:  python3 -m unittest discover -s tests
"""

from __future__ import annotations

import sys
import unittest
from datetime import date
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from bgautoagent import (  # noqa: E402
    BodyType,
    Costs,
    Powertrain,
    Reliability,
    RiskInputs,
    SourceType,
    TaxAssumptions,
    Targets,
    VatRegime,
    Vehicle,
    Verdict,
    Weights,
    bg_score,
    decide,
    euro,
    evaluate,
    max_purchase_price,
    registration_tax,
)
from bgautoagent.greek_tax import (  # noqa: E402
    age_depreciation,
    co2_adjustment,
    hybrid_rule_at,
    next_rule_change_after,
)
from bgautoagent.money import format_eur, round_money  # noqa: E402
from bgautoagent.reliability import Ledger  # noqa: E402


def a_vehicle(**overrides):
    defaults = dict(
        make="Toyota",
        model="C-HR",
        first_registration=date(2021, 6, 1),
        mileage_km=68000,
        body_type=BodyType.SUV_4X4,
        powertrain=Powertrain.HYBRID,
        co2_wltp=48,
        asking_price=euro("15200"),
        source_type=SourceType.B2B,
        vat_regime=VatRegime.DEDUCTIBLE,
    )
    defaults.update(overrides)
    return Vehicle(**defaults)


STANDARD_COSTS = Costs(
    transport=euro("850"),
    preparation=euro("400"),
    admin_belgium=euro("150"),
    admin_greece=euro("300"),
)

RELIABLE_ASSUMPTIONS = TaxAssumptions(
    base_rate=Decimal("0.35"),
    base_rate_reliability=Reliability.ESTIMATED,
)


class MoneyTests(unittest.TestCase):
    def test_refuses_a_float(self):
        with self.assertRaises(TypeError):
            euro(15200.00)

    def test_rounds_half_up_to_the_cent(self):
        self.assertEqual(round_money(Decimal("0.125")), Decimal("0.13"))

    def test_no_float_drift_across_a_long_sum(self):
        total = sum((euro("0.10") for _ in range(10)), Decimal("0"))
        self.assertEqual(total, Decimal("1.00"))

    def test_formats_the_way_invoices_do(self):
        self.assertEqual(format_eur(Decimal("15200")), "15 200,00 €")


class ReliabilityTests(unittest.TestCase):
    def test_floor_is_the_weakest_input(self):
        led = Ledger()
        led.record("a", Reliability.VERIFIED)
        led.record("b", Reliability.INDICATIVE)
        led.record("c", Reliability.ESTIMATED)
        self.assertEqual(led.floor, Reliability.INDICATIVE)

    def test_indicative_input_blocks_decisions(self):
        led = Ledger()
        led.record("prix marché", Reliability.INDICATIVE)
        self.assertFalse(led.is_decisional)

    def test_estimated_is_good_enough_to_act_on(self):
        led = Ledger()
        led.record("prix marché", Reliability.ESTIMATED)
        self.assertTrue(led.is_decisional)

    def test_names_what_must_be_fixed(self):
        led = Ledger()
        led.record("solide", Reliability.VERIFIED)
        led.record("délai de vente", Reliability.INDICATIVE)
        self.assertEqual([i.name for i in led.weakest()], ["délai de vente"])


class DepreciationTests(unittest.TestCase):
    def test_body_type_changes_the_tax_base(self):
        # The commercial finding: at five years a saloon is far better treated.
        saloon = age_depreciation(BodyType.SALOON, Decimal("5"))
        hatch = age_depreciation(BodyType.HATCHBACK, Decimal("5"))
        self.assertEqual(saloon, Decimal("0.72"))
        self.assertEqual(hatch, Decimal("0.61"))
        self.assertGreater(saloon - hatch, Decimal("0.10"))

    def test_takes_the_step_actually_reached(self):
        # One day short of three years does not earn the three-year step.
        almost = age_depreciation(BodyType.SUV_4X4, Decimal("2.99"))
        reached = age_depreciation(BodyType.SUV_4X4, Decimal("3.0"))
        self.assertEqual(almost, Decimal("0.35"))
        self.assertEqual(reached, Decimal("0.37"))

    def test_brand_new_gets_nothing(self):
        self.assertEqual(age_depreciation(BodyType.SALOON, Decimal("0.2")), Decimal("0"))

    def test_old_cars_reach_the_ceiling(self):
        self.assertEqual(age_depreciation(BodyType.MPV, Decimal("20")), Decimal("0.95"))


class Co2Tests(unittest.TestCase):
    def test_low_emitters_get_a_discount(self):
        self.assertEqual(co2_adjustment(120), Decimal("-0.05"))

    def test_heavy_emitters_are_penalised(self):
        self.assertEqual(co2_adjustment(200), Decimal("0.20"))
        self.assertEqual(co2_adjustment(400), Decimal("1.00"))

    def test_the_undocumented_band_is_neutral(self):
        self.assertEqual(co2_adjustment(140), Decimal("0"))


class HybridRuleTests(unittest.TestCase):
    def test_efficient_hybrid_keeps_75_percent_until_end_of_2026(self):
        rule = hybrid_rule_at(date(2026, 12, 31))
        self.assertEqual(rule.reduction_for(a_vehicle(co2_wltp=48)), Decimal("0.75"))

    def test_relief_halves_on_the_first_of_january_2027(self):
        rule = hybrid_rule_at(date(2027, 1, 1))
        self.assertEqual(rule.reduction_for(a_vehicle(co2_wltp=48)), Decimal("0.50"))

    def test_a_thirstier_hybrid_gains_from_the_change(self):
        # Above 50 g/km it got nothing before, and gets 50% after.
        thirsty = a_vehicle(co2_wltp=90)
        self.assertEqual(hybrid_rule_at(date(2026, 6, 1)).reduction_for(thirsty), Decimal("0"))
        self.assertEqual(hybrid_rule_at(date(2027, 6, 1)).reduction_for(thirsty), Decimal("0.50"))

    def test_petrol_never_gets_hybrid_relief(self):
        petrol = a_vehicle(powertrain=Powertrain.PETROL, co2_wltp=40)
        self.assertEqual(hybrid_rule_at(date(2026, 1, 1)).reduction_for(petrol), Decimal("0"))

    def test_the_next_change_is_reported(self):
        self.assertEqual(next_rule_change_after(date(2026, 8, 6)), date(2027, 1, 1))
        self.assertIsNone(next_rule_change_after(date(2030, 1, 1)))


class TaxDateTests(unittest.TestCase):
    def test_same_car_taxed_differently_either_side_of_the_deadline(self):
        car = a_vehicle(co2_wltp=48)
        common = dict(
            vehicle=car,
            pre_tax_retail_value=euro("18000"),
            assumptions=RELIABLE_ASSUMPTIONS,
        )
        before = registration_tax(registration_date=date(2026, 12, 15), **common)
        after = registration_tax(registration_date=date(2027, 1, 15), **common)

        self.assertLess(before.registration_tax, after.registration_tax)
        self.assertEqual(before.rule_version, "hybrid-relief-2018")
        self.assertEqual(after.rule_version, "hybrid-relief-2027")

    def test_the_bill_doubles_for_an_efficient_hybrid(self):
        car = a_vehicle(co2_wltp=48)
        common = dict(
            vehicle=car,
            pre_tax_retail_value=euro("18000"),
            assumptions=RELIABLE_ASSUMPTIONS,
        )
        before = registration_tax(registration_date=date(2026, 12, 15), **common)
        after = registration_tax(registration_date=date(2027, 1, 15), **common)
        # 25% of the rate becomes 50% of it. Each side is rounded to the cent
        # independently, so exact doubling is not guaranteed — a cent apart is
        # correct behaviour for money, not a defect.
        gap = abs(after.registration_tax - before.registration_tax * 2)
        self.assertLessEqual(gap, Decimal("0.01"))

    def test_missing_mileage_table_is_recorded_not_hidden(self):
        result = registration_tax(
            vehicle=a_vehicle(),
            registration_date=date(2026, 9, 1),
            pre_tax_retail_value=euro("18000"),
            assumptions=RELIABLE_ASSUMPTIONS,
        )
        names = [i.name for i in result.ledger.inputs]
        self.assertIn("dépréciation kilométrique", names)
        self.assertFalse(result.ledger.is_decisional)


class FinancialTests(unittest.TestCase):
    def setUp(self):
        self.tax = registration_tax(
            vehicle=a_vehicle(),
            registration_date=date(2026, 9, 1),
            pre_tax_retail_value=euro("18000"),
            assumptions=RELIABLE_ASSUMPTIONS,
        )
        self.tax.ledger.inputs[:] = [
            i for i in self.tax.ledger.inputs if i.reliability >= Reliability.ESTIMATED
        ]

    def test_buying_at_the_ceiling_exactly_meets_the_targets(self):
        targets = Targets()
        ceiling = max_purchase_price(
            greek_market_price=euro("24000"),
            tax=self.tax,
            costs=STANDARD_COSTS,
            targets=targets,
        )
        transfer = ceiling + targets.min_profit_belgium + STANDARD_COSTS.belgium_side
        outcome = evaluate(
            purchase_price=ceiling,
            transfer_price=transfer,
            greek_market_price=euro("24000"),
            tax=self.tax,
            costs=STANDARD_COSTS,
            targets=targets,
            days_to_sell=30,
            market_price_reliability=Reliability.ESTIMATED,
            days_to_sell_reliability=Reliability.ESTIMATED,
        )
        self.assertTrue(outcome.meets_all_targets, outcome)
        self.assertEqual(outcome.profit_belgium, targets.min_profit_belgium)

    def test_paying_one_euro_over_the_ceiling_breaks_a_target(self):
        targets = Targets()
        ceiling = max_purchase_price(
            greek_market_price=euro("24000"),
            tax=self.tax,
            costs=STANDARD_COSTS,
            targets=targets,
        )
        over = ceiling + euro("100")
        transfer = over + targets.min_profit_belgium + STANDARD_COSTS.belgium_side
        outcome = evaluate(
            purchase_price=over,
            transfer_price=transfer,
            greek_market_price=euro("24000"),
            tax=self.tax,
            costs=STANDARD_COSTS,
            targets=targets,
            days_to_sell=30,
            market_price_reliability=Reliability.ESTIMATED,
            days_to_sell_reliability=Reliability.ESTIMATED,
        )
        self.assertFalse(outcome.meets_all_targets)

    def test_safety_margin_lowers_the_ceiling(self):
        cautious = max_purchase_price(
            greek_market_price=euro("24000"),
            tax=self.tax,
            costs=STANDARD_COSTS,
            targets=Targets(safety_margin=Decimal("0.10")),
        )
        bold = max_purchase_price(
            greek_market_price=euro("24000"),
            tax=self.tax,
            costs=STANDARD_COSTS,
            targets=Targets(safety_margin=Decimal("0.05")),
        )
        self.assertLess(cautious, bold)

    def test_admin_days_count_against_rotation(self):
        kwargs = dict(
            purchase_price=euro("15000"),
            transfer_price=euro("16000"),
            greek_market_price=euro("24000"),
            tax=self.tax,
            costs=STANDARD_COSTS,
            targets=Targets(),
            days_to_sell=10,
            market_price_reliability=Reliability.ESTIMATED,
            days_to_sell_reliability=Reliability.ESTIMATED,
        )
        outcome = evaluate(**kwargs)
        # Ten days of selling still ties capital up for a month with paperwork.
        self.assertEqual(outcome.days_held, 31)


class TheThesisTest(unittest.TestCase):
    """The reason the product exists.

    A car earning less per sale can earn more per year, because the capital
    comes back sooner. If this test ever fails the engine has stopped
    expressing the business.
    """

    # NB: not named _outcome — unittest.TestCase uses self._outcome internally.
    def _deal(self, *, profit_target_price: str, days: int):
        tax = registration_tax(
            vehicle=a_vehicle(),
            registration_date=date(2026, 9, 1),
            pre_tax_retail_value=euro("18000"),
            assumptions=RELIABLE_ASSUMPTIONS,
        )
        tax.ledger.inputs[:] = [
            i for i in tax.ledger.inputs if i.reliability >= Reliability.ESTIMATED
        ]
        return evaluate(
            purchase_price=euro("14000"),
            transfer_price=euro("15000"),
            greek_market_price=euro(profit_target_price),
            tax=tax,
            costs=STANDARD_COSTS,
            targets=Targets(),
            days_to_sell=days,
            market_price_reliability=Reliability.ESTIMATED,
            days_to_sell_reliability=Reliability.ESTIMATED,
        )

    def test_the_fat_slow_deal_loses_to_the_lean_fast_one(self):
        fat_slow = self._deal(profit_target_price="27000", days=60)
        lean_fast = self._deal(profit_target_price="24000", days=10)

        # Per sale, the slow one wins.
        self.assertGreater(fat_slow.profit_total, lean_fast.profit_total)
        # Over a year, it loses — and that inversion is the product.
        self.assertGreater(
            lean_fast.annual_profit_potential, fat_slow.annual_profit_potential
        )

    def test_ranking_by_margin_differs_from_ranking_by_annual_yield(self):
        deals = [
            ("fat_slow", self._deal(profit_target_price="27000", days=60)),
            ("lean_fast", self._deal(profit_target_price="24000", days=10)),
        ]
        by_margin = [n for n, o in sorted(deals, key=lambda d: -d[1].profit_total)]
        by_year = [n for n, o in sorted(deals, key=lambda d: -d[1].annual_profit_potential)]
        self.assertNotEqual(by_margin, by_year)


class ScoreTests(unittest.TestCase):
    def setUp(self):
        self.tax = registration_tax(
            vehicle=a_vehicle(),
            registration_date=date(2026, 9, 1),
            pre_tax_retail_value=euro("18000"),
            assumptions=RELIABLE_ASSUMPTIONS,
        )
        self.tax.ledger.inputs[:] = [
            i for i in self.tax.ledger.inputs if i.reliability >= Reliability.ESTIMATED
        ]
        self.outcome = evaluate(
            purchase_price=euro("14000"),
            transfer_price=euro("15000"),
            greek_market_price=euro("24000"),
            tax=self.tax,
            costs=STANDARD_COSTS,
            targets=Targets(),
            days_to_sell=12,
            market_price_reliability=Reliability.ESTIMATED,
            days_to_sell_reliability=Reliability.ESTIMATED,
        )

    def test_weights_must_sum_to_one(self):
        with self.assertRaises(ValueError):
            Weights(rotation=Decimal("0.5")).validate()

    def test_a_quick_sale_scores_full_marks_on_rotation(self):
        score = bg_score(
            outcome=self.outcome,
            risks=RiskInputs(mechanical=80, refurbishment=75),
            co2_wltp=48,
            registration_tax=self.tax.registration_tax,
            straddles_rule_change=False,
        )
        self.assertEqual(score.components["rotation"], Decimal("100"))

    def test_failing_a_floor_zeroes_profitability(self):
        bad = evaluate(
            purchase_price=euro("23000"),
            transfer_price=euro("23900"),
            greek_market_price=euro("24000"),
            tax=self.tax,
            costs=STANDARD_COSTS,
            targets=Targets(),
            days_to_sell=12,
            market_price_reliability=Reliability.ESTIMATED,
            days_to_sell_reliability=Reliability.ESTIMATED,
        )
        score = bg_score(
            outcome=bad,
            risks=RiskInputs(mechanical=90, refurbishment=90),
            co2_wltp=48,
            registration_tax=self.tax.registration_tax,
            straddles_rule_change=False,
        )
        self.assertEqual(score.components["profitability"], Decimal("0"))

    def test_reweighting_changes_the_total(self):
        args = dict(
            outcome=self.outcome,
            risks=RiskInputs(mechanical=50, refurbishment=50),
            co2_wltp=48,
            registration_tax=self.tax.registration_tax,
            straddles_rule_change=False,
        )
        default = bg_score(**args)
        rotation_heavy = bg_score(
            weights=Weights(
                rotation=Decimal("0.60"),
                profitability=Decimal("0.20"),
                mechanical_risk=Decimal("0.10"),
                refurbishment_risk=Decimal("0.05"),
                tax_exposure=Decimal("0.05"),
            ),
            **args
        )
        self.assertNotEqual(default.total, rotation_heavy.total)

    def test_a_straddled_deadline_costs_tax_points(self):
        clean = bg_score(
            outcome=self.outcome,
            risks=RiskInputs(mechanical=80, refurbishment=80),
            co2_wltp=48,
            registration_tax=self.tax.registration_tax,
            straddles_rule_change=False,
        )
        straddled = bg_score(
            outcome=self.outcome,
            risks=RiskInputs(mechanical=80, refurbishment=80),
            co2_wltp=48,
            registration_tax=self.tax.registration_tax,
            straddles_rule_change=True,
        )
        self.assertLess(straddled.total, clean.total)


class DecisionTests(unittest.TestCase):
    def _decide(self, *, days_to_sell=12, market_reliability=Reliability.ESTIMATED,
                asking="14000", registration=date(2026, 9, 1)):
        tax = registration_tax(
            vehicle=a_vehicle(),
            registration_date=registration,
            pre_tax_retail_value=euro("18000"),
            assumptions=RELIABLE_ASSUMPTIONS,
        )
        tax.ledger.inputs[:] = [
            i for i in tax.ledger.inputs if i.reliability >= Reliability.ESTIMATED
        ]
        outcome = evaluate(
            purchase_price=euro(asking),
            transfer_price=euro(asking) + euro("900"),
            greek_market_price=euro("24000"),
            tax=tax,
            costs=STANDARD_COSTS,
            targets=Targets(),
            days_to_sell=days_to_sell,
            market_price_reliability=market_reliability,
            days_to_sell_reliability=Reliability.ESTIMATED,
        )
        score = bg_score(
            outcome=outcome,
            risks=RiskInputs(mechanical=85, refurbishment=80),
            co2_wltp=48,
            registration_tax=tax.registration_tax,
            straddles_rule_change=False,
        )
        ceiling = max_purchase_price(
            greek_market_price=euro("24000"),
            tax=tax,
            costs=STANDARD_COSTS,
            targets=Targets(),
        )
        return decide(
            outcome=outcome,
            score=score,
            tax=tax,
            max_price=ceiling,
            asking_price=euro(asking),
            expected_registration=registration,
        )

    def test_indicative_data_can_never_say_buy(self):
        decision = self._decide(market_reliability=Reliability.INDICATIVE)
        self.assertEqual(decision.verdict, Verdict.NOT_DECISIONAL)
        self.assertFalse(decision.is_buy)
        self.assertFalse(decision.is_decisional)

    def test_a_sound_deal_is_a_buy(self):
        decision = self._decide()
        self.assertTrue(decision.is_buy, decision)
        self.assertTrue(decision.is_decisional)

    def test_overpaying_is_rejected_whatever_the_score(self):
        decision = self._decide(asking="21000")
        self.assertEqual(decision.verdict, Verdict.REJECT)
        self.assertTrue(any("maximal" in r or "plancher" in r or "ROI" in r
                            for r in decision.reasons), decision.reasons)

    def test_a_deal_running_past_the_deadline_is_flagged(self):
        decision = self._decide(days_to_sell=90, registration=date(2026, 11, 1))
        self.assertTrue(
            any("01/01/2027" in w for w in decision.warnings), decision.warnings
        )


if __name__ == "__main__":
    unittest.main()
