"""The local application: six steps, navigable, gated.

Served by the standard library, calling the same engine the tests cover. There
is no second implementation of the maths in JavaScript, because there is no
second source of truth for money.

    PYTHONPATH=src python3 -m bgautoagent.app
    → http://localhost:8765
"""

from __future__ import annotations

import random
import uuid
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Dict, List, Optional
from urllib.parse import parse_qs, urlparse

from . import sources as src
from . import views
from . import workflow as wf
from .decision import Decision, decide
from .financials import Costs, Outcome, Targets, evaluate, max_purchase_price
from .greek_tax import TaxAssumptions, TaxResult, next_rule_change_after, registration_tax
from .money import euro
from .reliability import Reliability
from .scoring import RiskInputs, Score, Weights, bg_score
from .store import Entry, Store
from .vehicle import BodyType, Powertrain, SourceType, VatRegime, Vehicle

# --- Assumptions, gathered so they can be argued with --------------------

COSTS = Costs(
    transport=euro("850"),
    preparation=euro("400"),
    admin_belgium=euro("150"),
    admin_greece=euro("300"),
)

TARGETS = Targets()

TAX_ASSUMPTIONS = TaxAssumptions(
    base_rate=Decimal("0.35"),
    base_rate_reliability=Reliability.INDICATIVE,
)

#: Greek pre-tax reference value as a fraction of market price — a stand-in for
#: the official reference, hence INDICATIVE.
RETAIL_VALUE_RATIO = Decimal("0.80")


class Analysis:
    def __init__(self, entry: Entry, outcome: Outcome, score: Score,
                 decision: Decision, tax: TaxResult, max_price: Decimal) -> None:
        self.entry = entry
        self.outcome = outcome
        self.score = score
        self.decision = decision
        self.tax = tax
        self.max_price = max_price

    @property
    def name(self) -> str:
        return "{} {}".format(self.entry.make, self.entry.model)

    @property
    def agrees_with_owner(self) -> Optional[bool]:
        """Whether engine and human landed in the same camp.

        None when there is nothing to compare: you did not commit, or the engine
        came out non-decisional. An engine that declined to answer has not
        disagreed, and counting it as disagreement would poison the only
        calibration data we have.
        """
        own = self.entry.own_verdict
        if own in ("", "unsure"):
            return None
        if not self.decision.is_decisional:
            return None
        return (own == "buy") == self.decision.is_buy


def analyse(entry: Entry) -> Analysis:
    vehicle = Vehicle(
        make=entry.make,
        model=entry.model,
        first_registration=date.fromisoformat(entry.first_registration),
        mileage_km=entry.mileage_km,
        body_type=BodyType(entry.body_type),
        powertrain=Powertrain(entry.powertrain),
        co2_wltp=entry.co2_wltp,
        asking_price=euro(entry.asking_price),
        source_type=SourceType(entry.source_type),
        vat_regime=VatRegime(entry.vat_regime),
    )
    registration = date.fromisoformat(entry.expected_registration)
    market = euro(entry.greek_market_price)

    tax = registration_tax(
        vehicle=vehicle,
        registration_date=registration,
        pre_tax_retail_value=market * RETAIL_VALUE_RATIO,
        assumptions=TAX_ASSUMPTIONS,
    )
    tax.ledger.record(
        "valeur de référence grecque",
        Reliability.INDICATIVE,
        "dérivée du prix de marché, ratio provisoire",
    )

    transfer = vehicle.asking_price + TARGETS.min_profit_belgium + COSTS.belgium_side

    outcome = evaluate(
        purchase_price=vehicle.asking_price,
        transfer_price=transfer,
        greek_market_price=market,
        tax=tax,
        costs=COSTS,
        targets=TARGETS,
        days_to_sell=entry.days_to_sell,
        market_price_reliability=Reliability.INDICATIVE,
        days_to_sell_reliability=Reliability.INDICATIVE,
    )

    straddles = False
    upcoming = next_rule_change_after(registration)
    if upcoming is not None:
        end = registration + timedelta(days=outcome.days_held)
        straddles = end >= upcoming

    score = bg_score(
        outcome=outcome,
        risks=RiskInputs(mechanical=entry.mechanical, refurbishment=entry.refurbishment),
        co2_wltp=entry.co2_wltp,
        registration_tax=tax.registration_tax,
        straddles_rule_change=straddles,
        weights=Weights(),
    )

    ceiling = max_purchase_price(
        greek_market_price=market, tax=tax, costs=COSTS, targets=TARGETS
    )

    decision = decide(
        outcome=outcome,
        score=score,
        tax=tax,
        max_price=ceiling,
        asking_price=vehicle.asking_price,
        expected_registration=registration,
    )

    return Analysis(entry, outcome, score, decision, tax, ceiling)


# --- Simulated collection -------------------------------------------------

_TEMPLATES = [
    ("Toyota", "Corolla 1.8 Hybrid", "saloon", "hybrid", 47, "16400", "26500", 14),
    ("Škoda", "Octavia 2.0 TDI", "saloon", "diesel", 124, "14900", "24800", 26),
    ("Renault", "Captur E-Tech", "suv_4x4", "hybrid", 49, "15600", "24200", 21),
    ("Ford", "Focus 1.0 EcoBoost", "hatchback", "petrol", 129, "11800", "19400", 33),
    ("Peugeot", "308 SW BlueHDi", "mpv", "diesel", 121, "13700", "22600", 29),
    ("Volvo", "V60 B4", "mpv", "hybrid", 138, "22400", "35200", 44),
]


def simulate_collection(store: Store) -> int:
    """Fabricate a few plausible listings, marked as simulated.

    No source is connected. These exist to exercise the whole path end to end,
    and every one is flagged so a placeholder can never pass for an observation.
    """
    pool = src.collectable()
    if not pool:
        return 0
    existing = {(e.make, e.model) for e in store.load()}
    added = 0
    for make, model, body, power, co2, price, market, days in _TEMPLATES:
        if (make, model) in existing:
            continue
        source = random.choice(pool)
        age_days = random.randint(900, 1900)
        entry = Entry(
            id=uuid.uuid4().hex[:12],
            make=make,
            model=model,
            first_registration=(date.today() - timedelta(days=age_days)).isoformat(),
            mileage_km=random.randrange(40000, 130000, 5000),
            body_type=body,
            powertrain=power,
            co2_wltp=co2,
            asking_price=price,
            source_type=source.source_type.value,
            vat_regime="deductible" if source.source_type is SourceType.B2B else "margin",
            greek_market_price=market,
            days_to_sell=days,
            mechanical=random.randint(60, 92),
            refurbishment=random.randint(55, 90),
            expected_registration=(date.today() + timedelta(days=30)).isoformat(),
            created_at=datetime.now().isoformat(timespec="seconds"),
            source_key=source.key,
            simulated=True,
        )
        store.add(entry)
        added += 1
    return added


# --- HTTP -----------------------------------------------------------------


def _first(form: Dict[str, List[str]], key: str, default: str = "") -> str:
    values = form.get(key) or []
    return values[0].strip() if values else default


class Handler(BaseHTTPRequestHandler):
    store = Store()

    def _send(self, status: int, body: str) -> None:
        payload = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def _redirect(self, location: str = "/") -> None:
        self.send_response(303)
        self.send_header("Location", location)
        self.end_headers()

    def _entries(self) -> List[Entry]:
        return self.store.load()

    def _find(self, entry_id: str) -> Optional[Entry]:
        for entry in self._entries():
            if entry.id == entry_id:
                return entry
        return None

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path != "/":
            self._send(404, "<h1>404</h1>")
            return

        query = parse_qs(parsed.query)
        step_key = (query.get("step") or ["sources"])[0]
        entry_id = (query.get("id") or [""])[0]

        if wf.step(step_key) is None:
            step_key = "sources"

        entry = self._find(entry_id) if entry_id else None
        target = wf.BY_KEY[step_key]

        # A locked step is not an error, it is a step whose premises have not
        # been accepted yet — send the user back to where the work actually is.
        if target.per_vehicle:
            if entry is None:
                self._redirect("/?step=opportunites")
                return
            if not wf.is_unlocked(step_key, entry.confirmed):
                self._redirect("/?step=marche&id={}".format(entry.id))
                return

        try:
            if step_key == "sources":
                content = views.page_sources()
            elif step_key == "opportunites":
                analyses = []
                for candidate in self._entries():
                    try:
                        analyses.append(analyse(candidate))
                    except (ValueError, InvalidOperation, KeyError):
                        continue  # one bad row must not blank the page
                content = views.page_opportunities(analyses)
            else:
                analysis = analyse(entry)
                content = {
                    "marche": views.page_market,
                    "calcul": views.page_calculation,
                    "score": views.page_score,
                    "decision": views.page_decision,
                }[step_key](analysis)
        except (ValueError, InvalidOperation, KeyError) as exc:
            content = "<h1>Donnée invalide</h1><p>{}</p><p><a href='/'>retour</a></p>".format(exc)

        self._send(200, views.shell(step_key, entry, content))

    def do_POST(self) -> None:  # noqa: N802
        length = int(self.headers.get("Content-Length", "0"))
        form = parse_qs(self.rfile.read(length).decode("utf-8"))
        path = urlparse(self.path).path

        if path == "/simulate":
            simulate_collection(self.store)
            self._redirect("/?step=opportunites")
            return

        if path == "/delete":
            self.store.delete(_first(form, "id"))
            self._redirect("/?step=opportunites")
            return

        if path in ("/confirm", "/unconfirm"):
            entry_id = _first(form, "id")
            step_key = _first(form, "step")
            entries = self._entries()
            for entry in entries:
                if entry.id == entry_id:
                    if path == "/confirm":
                        entry.confirm(step_key)
                        nxt = wf.next_step(step_key)
                        target = nxt.key if nxt else step_key
                    else:
                        entry.unconfirm_from(step_key, wf.VEHICLE_ORDER)
                        target = step_key
                    self.store.save(entries)
                    self._redirect("/?step={}&id={}".format(target, entry_id))
                    return
            self._redirect("/?step=opportunites")
            return

        if path != "/add":
            self._send(404, "<h1>404</h1>")
            return

        try:
            entry = Entry(
                id=uuid.uuid4().hex[:12],
                make=_first(form, "make"),
                model=_first(form, "model"),
                first_registration=_first(form, "first_registration"),
                mileage_km=int(_first(form, "mileage_km", "0")),
                body_type=_first(form, "body_type"),
                powertrain=_first(form, "powertrain"),
                co2_wltp=int(_first(form, "co2_wltp", "0")),
                asking_price=_first(form, "asking_price", "0"),
                source_type=_first(form, "source_type"),
                vat_regime=_first(form, "vat_regime"),
                greek_market_price=_first(form, "greek_market_price", "0"),
                days_to_sell=int(_first(form, "days_to_sell", "1")),
                mechanical=int(_first(form, "mechanical", "50")),
                refurbishment=int(_first(form, "refurbishment", "50")),
                expected_registration=_first(form, "expected_registration"),
                own_verdict=_first(form, "own_verdict"),
                created_at=datetime.now().isoformat(timespec="seconds"),
                source_key=_first(form, "source_key"),
            )
            analyse(entry)  # fail here rather than on every later page load
        except (ValueError, InvalidOperation, KeyError) as exc:
            self._send(400, "<h1>Saisie invalide</h1><p>{}</p>"
                            "<p><a href='/?step=opportunites'>retour</a></p>".format(exc))
            return

        self.store.add(entry)
        self._redirect("/?step=marche&id={}".format(entry.id))

    def log_message(self, fmt: str, *args) -> None:  # noqa: A003
        pass


def main(port: int = 8765) -> int:
    server = HTTPServer(("127.0.0.1", port), Handler)
    print("BG Auto Agent — http://localhost:{}".format(port))
    print("Ctrl+C pour arrêter.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nArrêté.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
