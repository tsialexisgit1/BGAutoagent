"""Data reliability, and what it forbids.

Every figure entering a decision carries a mark. The engine tracks them and
reports the **floor** — the weakest input — together with which inputs pulled it
down.

The rule that gives the marks teeth: a decision resting on anything marked
INDICATIVE or worse is **not decisional**. It is computed, it is displayed, it
is useful for testing the engine — and it must never say BUY. Without that rule
the legend is decoration, and a plausible-looking placeholder eventually buys a
car on nothing at all.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum
from typing import List, Optional, Tuple


class Reliability(IntEnum):
    """Ordered so that ``min()`` gives the floor of a set of inputs."""

    MISSING = 0      # ✗ identified, not yet collected
    INDICATIVE = 1   # ? order of magnitude, unverified — never decides
    ESTIMATED = 2    # ~ credible secondary source, or a real but partial sample
    VERIFIED = 3     # ✓ official source or direct observation, dated

    @property
    def mark(self) -> str:
        return {0: "✗", 1: "?", 2: "~", 3: "✓"}[int(self)]


#: Below this, a result may be shown but may not be acted on.
DECISION_FLOOR = Reliability.ESTIMATED


@dataclass(frozen=True)
class Input:
    """One figure and where it came from."""

    name: str
    reliability: Reliability
    source: str = ""


@dataclass
class Ledger:
    """Collects the provenance of everything that fed a calculation.

    Kept separate from the arithmetic on purpose. Wrapping every number in a
    reliability-carrying type would make the financial code harder to read, and
    that code has to stay obvious enough to audit by eye.
    """

    inputs: List[Input] = field(default_factory=list)

    def record(
        self,
        name: str,
        reliability: Reliability,
        source: str = "",
    ) -> None:
        self.inputs.append(Input(name=name, reliability=reliability, source=source))

    def extend(self, other: "Ledger") -> None:
        self.inputs.extend(other.inputs)

    @property
    def floor(self) -> Reliability:
        if not self.inputs:
            return Reliability.MISSING
        return min(i.reliability for i in self.inputs)

    @property
    def is_decisional(self) -> bool:
        """Whether a result built on these inputs may be acted on."""
        return self.floor >= DECISION_FLOOR

    def weakest(self) -> List[Input]:
        """The inputs sitting at the floor — i.e. what to go and fix."""
        floor = self.floor
        return [i for i in self.inputs if i.reliability == floor]

    def explain(self) -> str:
        if self.is_decisional:
            return "Décisionnel — donnée la plus faible : {}".format(self.floor.mark)
        names = ", ".join(i.name for i in self.weakest())
        return "NON DÉCISIONNEL — repose sur du {} : {}".format(self.floor.mark, names)


def combine(*ledgers: Optional[Ledger]) -> Ledger:
    merged = Ledger()
    for led in ledgers:
        if led is not None:
            merged.extend(led)
    return merged
