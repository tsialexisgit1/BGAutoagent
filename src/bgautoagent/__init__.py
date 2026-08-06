"""BG Auto Agent — decision engine.

Answers one question about one vehicle: buy, or not.

Deliberately free of third-party dependencies. See pyproject.toml.
"""

from .decision import Decision, Verdict, decide
from .financials import Costs, Outcome, Targets, evaluate, max_purchase_price
from .greek_tax import TaxAssumptions, TaxResult, registration_tax
from .money import euro, format_eur, pct
from .reliability import Ledger, Reliability
from .scoring import RiskInputs, Score, Weights, bg_score
from .vehicle import BodyType, Powertrain, SourceType, VatRegime, Vehicle

__all__ = [
    "BodyType",
    "Costs",
    "Decision",
    "Ledger",
    "Outcome",
    "Powertrain",
    "Reliability",
    "RiskInputs",
    "Score",
    "SourceType",
    "TaxAssumptions",
    "TaxResult",
    "Targets",
    "VatRegime",
    "Vehicle",
    "Verdict",
    "Weights",
    "bg_score",
    "decide",
    "euro",
    "evaluate",
    "format_eur",
    "max_purchase_price",
    "pct",
    "registration_tax",
]
