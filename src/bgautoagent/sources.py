"""Catalogue of acquisition sources.

Data, not code — one place where each source is described, assessed and given a
confidence, so that adding one or changing its legal status is an edit to a list.

Everything in `robots_txt` was checked directly on 6 August 2026. The dates
matter: a robots.txt is a statement of intent that can change, and ignoring one
is evidence of bad faith if a dispute ever arises.

Two things this file deliberately does **not** claim:

- That a permissive robots.txt makes collection lawful. It says nothing about
  terms of use, about the EU database right, or about personal data.
- That any API exists on terms we know. None of these platforms publishes
  pricing; access is negotiated against a trade account.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from typing import List, Optional

from .vehicle import SourceType


class Access(Enum):
    """How we would actually get the listings."""

    OFFICIAL_API = "api_officielle"
    SCRAPING_API = "api_scraping"
    OWN_SCRAPER = "scraper_maison"
    MANUAL = "manuel"
    UNKNOWN = "inconnu"


class Status(Enum):
    ACTIVE = "actif"
    TO_CONTACT = "a_contacter"
    LEGAL_REVIEW = "a_valider_juridiquement"
    TO_VERIFY = "a_verifier"
    BLOCKED = "bloque"


@dataclass(frozen=True)
class Source:
    key: str
    name: str
    source_type: SourceType
    status: Status
    access: Access
    robots_txt: str
    robots_checked: str
    api_note: str
    #: Multiplier applied to the BG Score of anything coming from here.
    #: An excellent score from a source we barely trust is not an excellent score.
    confidence: Decimal
    note: str = ""

    @property
    def confidence_pct(self) -> int:
        return int(self.confidence * 100)


CATALOGUE: List[Source] = [
    Source(
        key="autorola",
        name="Autorola",
        source_type=SourceType.B2B,
        status=Status.TO_CONTACT,
        access=Access.OFFICIAL_API,
        robots_txt="Allow: / — aucun Disallow",
        robots_checked="06/08/2026",
        api_note="API documentée publiquement (SwaggerHub, Fleet Management Integration). "
        "Le flux connu sert aux vendeurs déposant leur stock ; l'accès acheteur reste à obtenir.",
        confidence=Decimal("0.95"),
        note="La plus ouverte techniquement des huit.",
    ),
    Source(
        key="ecarstrade",
        name="eCarsTrade",
        source_type=SourceType.B2B,
        status=Status.TO_CONTACT,
        access=Access.UNKNOWN,
        robots_txt="Allow: /, listings et recherche ouverts, sitemap public",
        robots_checked="06/08/2026",
        api_note="Rien de public. Compte professionnel probablement requis.",
        confidence=Decimal("0.90"),
    ),
    Source(
        key="auto1",
        name="Auto1",
        source_type=SourceType.B2B,
        status=Status.TO_CONTACT,
        access=Access.UNKNOWN,
        robots_txt="Bloque login, inscription, désinscription. Listings ouverts",
        robots_checked="06/08/2026",
        api_note="Plateforme de gros pour professionnels ; accès par compte marchand.",
        confidence=Decimal("0.90"),
    ),
    Source(
        key="ayvens",
        name="Ayvens Carmarket",
        source_type=SourceType.B2B,
        status=Status.TO_CONTACT,
        access=Access.UNKNOWN,
        robots_txt="Bloque /lots/*?* et l'inscription ; pages de lots accessibles, sitemap public",
        robots_checked="06/08/2026",
        api_note="Rien de public trouvé.",
        confidence=Decimal("0.85"),
    ),
    Source(
        key="autoscout24",
        name="AutoScout24.be",
        source_type=SourceType.B2B,
        status=Status.BLOCKED,
        access=Access.OFFICIAL_API,
        robots_txt="Bloque nommément ClaudeBot, GPTBot, CCBot. Interdit /lst?, "
        "la recherche avancée et l'API GraphQL des annonces",
        robots_checked="06/08/2026",
        api_note="Des API concessionnaires existent, mais la voie publique est explicitement fermée. "
        "L'accès passe par un accord commercial, pas par la collecte.",
        confidence=Decimal("0.70"),
        note="Le seul des huit à nommer les robots d'IA.",
    ),
    Source(
        key="2ememain",
        name="2ememain.be",
        source_type=SourceType.C2C,
        status=Status.LEGAL_REVIEW,
        access=Access.UNKNOWN,
        robots_txt="Bloque /search?q=* et les comptes ; annonces individuelles non interdites",
        robots_checked="06/08/2026",
        api_note="Aucune API pour les annonces.",
        confidence=Decimal("0.50"),
        note="Plus permissive techniquement que AutoScout24, et bien plus exposée juridiquement : "
        "conditions d'utilisation, droit sui generis des bases de données, et données de "
        "vendeurs particuliers. Décision à prendre avec un juriste.",
    ),
    Source(
        key="bca",
        name="BCA",
        source_type=SourceType.B2B,
        status=Status.TO_VERIFY,
        access=Access.UNKNOWN,
        robots_txt="404 sur bca-europe.com/robots.txt — domaine à confirmer",
        robots_checked="06/08/2026",
        api_note="Rien trouvé.",
        confidence=Decimal("0.60"),
    ),
    Source(
        key="gocar",
        name="Gocar.be",
        source_type=SourceType.B2B,
        status=Status.TO_VERIFY,
        access=Access.UNKNOWN,
        robots_txt="Inaccessible depuis notre environnement (deux tentatives) — "
        "filtrage probable des requêtes automatisées",
        robots_checked="06/08/2026",
        api_note="Inconnue.",
        confidence=Decimal("0.60"),
    ),
]

BY_KEY = {s.key: s for s in CATALOGUE}


def get(key: str) -> Optional[Source]:
    return BY_KEY.get(key)


def collectable() -> List[Source]:
    """Sources we would actually poll today.

    Excludes anything blocked or awaiting a legal opinion — the catalogue keeps
    them visible, the collector leaves them alone.
    """
    return [s for s in CATALOGUE if s.status in (Status.ACTIVE, Status.TO_CONTACT)]
