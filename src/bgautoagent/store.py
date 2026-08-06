"""Storage for manually entered vehicles.

A JSON file, deliberately. At this stage the point is to try the engine on cars
you already know, and a file you can open, read and correct in a text editor is
worth more than a database you cannot see. Swapping it later touches one module.
"""

from __future__ import annotations

import json
import tempfile
import os
from dataclasses import asdict, dataclass, field
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, List, Optional

DEFAULT_PATH = Path(__file__).resolve().parents[2] / "data" / "vehicles.json"


@dataclass
class Entry:
    """One manually entered vehicle, plus what the engine will need.

    ``own_verdict`` is recorded **before** the score is shown. The gap between
    your judgement and the engine's is the only calibration data that exists
    today, and it costs one field to collect.
    """

    id: str
    make: str
    model: str
    first_registration: str
    mileage_km: int
    body_type: str
    powertrain: str
    co2_wltp: int
    asking_price: str
    source_type: str
    vat_regime: str

    greek_market_price: str
    days_to_sell: int
    mechanical: int
    refurbishment: int
    expected_registration: str

    own_verdict: str = ""
    note: str = ""
    created_at: str = ""

    def to_json(self) -> Dict[str, Any]:
        return asdict(self)

    @staticmethod
    def from_json(raw: Dict[str, Any]) -> "Entry":
        known = {f for f in Entry.__dataclass_fields__}  # type: ignore[attr-defined]
        return Entry(**{k: v for k, v in raw.items() if k in known})


class Store:
    def __init__(self, path: Optional[Path] = None) -> None:
        self.path = Path(path) if path else DEFAULT_PATH
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def load(self) -> List[Entry]:
        if not self.path.exists():
            return []
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            # A corrupt file must not take the application down; the entries are
            # replaceable, the ability to keep working is not.
            return []
        return [Entry.from_json(item) for item in raw]

    def save(self, entries: List[Entry]) -> None:
        payload = json.dumps(
            [e.to_json() for e in entries], ensure_ascii=False, indent=2
        )
        # Write to a temporary file in the same directory, then rename: an
        # interrupted save leaves the previous file intact rather than a
        # half-written one.
        fd, tmp = tempfile.mkstemp(dir=str(self.path.parent), suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(payload)
            os.replace(tmp, self.path)
        except Exception:
            if os.path.exists(tmp):
                os.unlink(tmp)
            raise

    def add(self, entry: Entry) -> None:
        entries = self.load()
        entries.append(entry)
        self.save(entries)

    def delete(self, entry_id: str) -> None:
        self.save([e for e in self.load() if e.id != entry_id])
