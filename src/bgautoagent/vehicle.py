"""What the engine needs to know about a car, and about where it was found."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from enum import Enum
from typing import Optional


class SourceType(Enum):
    """Where a listing came from.

    This is a discriminant, not a label. It decides what is legal to collect,
    which VAT regime applies — margin scheme or deductible VAT, which changes
    the maths — what the buying process is, and what paperwork follows.
    """

    B2B = "b2b"
    C2C = "c2c"


class BodyType(Enum):
    """Body type, as the Greek depreciation table categorises it.

    Not a descriptive field: the same car at the same age is taxed differently
    depending on this. At five years a saloon gets 72% off its taxable value
    where a hatchback gets 61%.
    """

    SUV_4X4 = "suv_4x4"
    HATCHBACK = "hatchback"
    SALOON = "saloon"
    CABRIOLET = "cabriolet"
    COUPE_ROADSTER = "coupe_roadster"
    MPV = "mpv"


class Powertrain(Enum):
    PETROL = "petrol"
    DIESEL = "diesel"
    HYBRID = "hybrid"
    PLUGIN_HYBRID = "plugin_hybrid"
    ELECTRIC = "electric"


class VatRegime(Enum):
    """How VAT sits on the purchase.

    MARGIN: VAT already borne, not recoverable — the price is the cost.
    DEDUCTIBLE: VAT shown separately and recoverable by the Belgian company.
    """

    MARGIN = "margin"
    DEDUCTIBLE = "deductible"


@dataclass(frozen=True)
class Vehicle:
    make: str
    model: str
    first_registration: date
    mileage_km: int
    body_type: BodyType
    powertrain: Powertrain
    co2_wltp: int
    """Combined-cycle CO2 in g/km. Drives both the Greek tax and the score."""

    asking_price: Decimal
    """Advertised price in Belgium, in euro."""

    source_type: SourceType
    vat_regime: VatRegime
    engine_cc: Optional[int] = None
    euro_standard: Optional[str] = None
    vin: Optional[str] = None
    listing_url: Optional[str] = None
    version: Optional[str] = None

    def age_years_at(self, moment: date) -> Decimal:
        """Age in years, as a Decimal, at a given date.

        The Greek depreciation table is graduated in half-years, so the caller
        needs a fractional age rather than a whole number of years.
        """
        days = (moment - self.first_registration).days
        return Decimal(days) / Decimal(365)
