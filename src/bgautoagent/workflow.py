"""The six steps, and what unlocks each one.

The process is fixed: the same stages in the same order, every time. That is
precisely why it is a workflow and not an agent — there is no decision about
what to do next, only work to do inside each stage.

Gating exists for one reason: each stage's figures are derived from the stage
before it. Letting someone read a BG Score before confirming the market
reference it rests on would present a conclusion as if its premises had been
accepted.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional


@dataclass(frozen=True)
class Step:
    key: str
    number: int
    title: str
    summary: str
    #: Global steps stand alone; vehicle steps run against one opportunity.
    per_vehicle: bool


STEPS: List[Step] = [
    Step(
        key="sources",
        number=1,
        title="Sources d'acquisition",
        summary="D'où viennent les annonces, ce que chaque source autorise, "
        "et la confiance qu'on lui accorde.",
        per_vehicle=False,
    ),
    Step(
        key="opportunites",
        number=2,
        title="Opportunités",
        summary="Les véhicules candidats, saisis à la main ou remontés par la collecte.",
        per_vehicle=False,
    ),
    Step(
        key="marche",
        number=3,
        title="Marché grec",
        summary="Prix de revente prudent, délai de vente, et ce que le capital "
        "peut faire de rotations dans l'année.",
        per_vehicle=True,
    ),
    Step(
        key="calcul",
        number=4,
        title="Calcul financier",
        summary="Coût de revient complet, prix maximal d'achat, marges des deux "
        "sociétés, ROI.",
        per_vehicle=True,
    ),
    Step(
        key="score",
        number=5,
        title="BG Score",
        summary="Cinq composantes pondérées. La rotation pèse le plus.",
        per_vehicle=True,
    ),
    Step(
        key="decision",
        number=6,
        title="Décision",
        summary="Acheter ou non — sous réserve de validation humaine, toujours.",
        per_vehicle=True,
    ),
]

ORDER = [s.key for s in STEPS]
VEHICLE_ORDER = [s.key for s in STEPS if s.per_vehicle]
BY_KEY = {s.key: s for s in STEPS}


def step(key: str) -> Optional[Step]:
    return BY_KEY.get(key)


def is_unlocked(key: str, confirmed: List[str]) -> bool:
    """Whether a step can be opened, given what has been confirmed.

    The two global steps are always open — you can always look at your sources
    or your candidates. The vehicle steps open one at a time.
    """
    target = BY_KEY.get(key)
    if target is None:
        return False
    if not target.per_vehicle:
        return True
    index = VEHICLE_ORDER.index(key)
    if index == 0:
        return True
    return VEHICLE_ORDER[index - 1] in confirmed


def state_of(key: str, current: str, confirmed: List[str]) -> str:
    """One of: done, current, open, locked — what the left panel renders."""
    if key == current:
        return "current"
    if key in confirmed:
        return "done"
    return "open" if is_unlocked(key, confirmed) else "locked"


def next_step(key: str) -> Optional[Step]:
    if key not in ORDER:
        return None
    index = ORDER.index(key)
    return STEPS[index + 1] if index + 1 < len(STEPS) else None
