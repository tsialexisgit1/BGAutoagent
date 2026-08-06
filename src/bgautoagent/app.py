"""Manual entry, and the two rankings side by side.

A local web page served by the standard library. No framework, and above all no
second implementation of the maths: the page calls the same engine the tests
cover, so what you see here is what the engine says.

    python3 -m bgautoagent.app
    → http://localhost:8765
"""

from __future__ import annotations

import html
import json
import uuid
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Dict, List, Optional, Tuple
from urllib.parse import parse_qs, urlparse

from .decision import Decision, Verdict, decide
from .financials import Costs, Outcome, Targets, evaluate, max_purchase_price
from .greek_tax import TaxAssumptions, TaxResult, registration_tax
from .money import euro, format_eur
from .reliability import Reliability
from .scoring import RiskInputs, Score, Weights, bg_score
from .store import Entry, Store
from .vehicle import BodyType, Powertrain, SourceType, VatRegime, Vehicle

# --- Assumptions, all in one place so they can be argued with ------------

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

#: The Greek pre-tax reference value, as a fraction of the market price.
#: A stand-in for the official reference value — hence INDICATIVE.
RETAIL_VALUE_RATIO = Decimal("0.80")

BODY_LABELS = {
    BodyType.SUV_4X4: "4×4 / SUV",
    BodyType.HATCHBACK: "Compacte",
    BodyType.SALOON: "Berline",
    BodyType.CABRIOLET: "Cabriolet",
    BodyType.COUPE_ROADSTER: "Coupé / Roadster",
    BodyType.MPV: "Monospace",
}

POWERTRAIN_LABELS = {
    Powertrain.PETROL: "Essence",
    Powertrain.DIESEL: "Diesel",
    Powertrain.HYBRID: "Hybride",
    Powertrain.PLUGIN_HYBRID: "Hybride rechargeable",
    Powertrain.ELECTRIC: "Électrique",
}

VERDICT_CLASS = {
    Verdict.BUY_NOW: "v-buy",
    Verdict.BUY_IF_PRICE_HOLDS: "v-buy-soft",
    Verdict.NEGOTIATE: "v-negotiate",
    Verdict.REJECT: "v-reject",
    Verdict.NOT_DECISIONAL: "v-unknown",
}

OWN_VERDICT_LABELS = {
    "": "—",
    "buy": "J'achète",
    "negotiate": "Je négocie",
    "reject": "Je passe",
    "unsure": "Je ne sais pas",
}


# --- Running the engine on one entry -------------------------------------


class Analysis:
    def __init__(
        self,
        entry: Entry,
        outcome: Outcome,
        score: Score,
        decision: Decision,
        tax: TaxResult,
        max_price: Decimal,
    ) -> None:
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
        """Whether the engine and the human reached the same camp.

        Deliberately coarse: buy-ish versus not. A 'buy now' against a
        'negotiate' is not a disagreement worth flagging.

        Returns None when there is nothing to compare — you did not commit, or
        the engine came out non-decisional. An engine that declined to answer
        has not disagreed with you, and scoring it as a disagreement would
        quietly poison the only calibration data we have.
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

    change_ahead = False
    from .greek_tax import next_rule_change_after

    upcoming = next_rule_change_after(registration)
    if upcoming is not None:
        end = date.fromordinal(registration.toordinal() + outcome.days_held)
        change_ahead = end >= upcoming

    score = bg_score(
        outcome=outcome,
        risks=RiskInputs(mechanical=entry.mechanical, refurbishment=entry.refurbishment),
        co2_wltp=entry.co2_wltp,
        registration_tax=tax.registration_tax,
        straddles_rule_change=change_ahead,
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


# --- Rendering ------------------------------------------------------------

STYLE = """
:root{--ground:#f7f8f9;--surface:#fff;--surface2:#eef1f4;--ink:#1b2227;--ink2:#54616b;
--muted:#8996a1;--line:#e2e7eb;--line2:#c9d2d9;--accent:#0b6b7a;--accent-soft:#dcecef;
--ok:#127a45;--warn:#a86616;--stop:#b5372a;
--font:"Avenir Next","Segoe UI",system-ui,-apple-system,sans-serif;
--mono:ui-monospace,"SF Mono",Menlo,Consolas,monospace}
*{box-sizing:border-box}
body{margin:0;background:var(--ground);color:var(--ink);font-family:var(--font);
font-size:14px;line-height:1.5;-webkit-font-smoothing:antialiased}
.wrap{width:min(100% - 2.5rem,1240px);margin-inline:auto;padding:1.6rem 0 4rem}
h1{font-size:1.45rem;letter-spacing:-.028em;margin:0}
h2{font-size:1rem;letter-spacing:-.015em;margin:0 0 .75rem}
.sub{color:var(--ink2);margin:.3rem 0 1.6rem;max-width:70ch}
.panel{background:var(--surface);border:1px solid var(--line);border-radius:10px;overflow:hidden}
.panel-h{padding:.8rem 1rem;border-bottom:1px solid var(--line);font-weight:700;font-size:.86rem;
display:flex;justify-content:space-between;align-items:center;gap:1rem}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:.9rem;padding:1rem}
.fld{display:flex;flex-direction:column;gap:.3rem}
.fld label{font-size:.76rem;font-weight:600;color:var(--ink2)}
.fld input,.fld select,.fld textarea{font:inherit;font-size:.87rem;color:var(--ink);background:var(--ground);
border:1px solid var(--line2);border-radius:6px;padding:.42rem .55rem;width:100%}
.fld input:focus-visible,.fld select:focus-visible{outline:2px solid var(--accent);outline-offset:1px}
.foot{padding:.85rem 1rem;border-top:1px solid var(--line);display:flex;gap:.6rem;justify-content:flex-end}
button{font:inherit;font-size:.85rem;font-weight:600;padding:.45rem .9rem;border-radius:6px;cursor:pointer;
background:var(--accent);color:#fff;border:1px solid var(--accent)}
button:hover{filter:brightness(1.1)}
button.ghost{background:var(--surface);color:var(--accent)}
button.danger{background:var(--surface);color:var(--stop);border-color:var(--line2);padding:.2rem .5rem;font-size:.76rem}
.cols{display:grid;grid-template-columns:1fr 1fr;gap:1rem;margin-top:1.5rem}
@media(max-width:900px){.cols{grid-template-columns:1fr}}
/* Narrow viewports were clipping the last column — which happens to be the
   annual yield, the one figure the page exists to show. */
.scroll{overflow-x:auto}
table{width:100%;border-collapse:collapse;font-size:.85rem;min-width:440px}
th{text-align:left;font-size:.66rem;letter-spacing:.09em;text-transform:uppercase;color:var(--muted);
padding:.55rem .8rem;border-bottom:1px solid var(--line);white-space:nowrap}
td{padding:.55rem .8rem;border-bottom:1px solid var(--line);vertical-align:middle}
tr:last-child td{border-bottom:0}
.num{font-family:var(--mono);font-variant-numeric:tabular-nums;text-align:right;white-space:nowrap}
.rank{font-family:var(--mono);color:var(--muted);width:1.6rem}
.name{font-weight:600}
.badge{font-size:.7rem;font-weight:700;padding:.14rem .45rem;border-radius:4px;white-space:nowrap}
.b2b{background:var(--accent-soft);color:var(--accent)}
.c2c{background:#fdeee9;color:var(--stop)}
.v-buy{background:#dff3e6;color:var(--ok)}
.v-buy-soft{background:#e6f2ea;color:var(--ok)}
.v-negotiate{background:#fdf0dc;color:var(--warn)}
.v-reject{background:#fdeae7;color:var(--stop)}
.v-unknown{background:var(--surface2);color:var(--muted)}
.moved{font-size:.7rem;font-family:var(--mono);color:var(--accent);font-weight:700}
.detail{margin-top:1.5rem}
.card{padding:.9rem 1rem;border-bottom:1px solid var(--line)}
.card:last-child{border-bottom:0}
.card-h{display:flex;justify-content:space-between;align-items:center;gap:1rem;flex-wrap:wrap}
.bars{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:.5rem;margin-top:.7rem}
.bar{font-size:.74rem;color:var(--ink2)}
.bar .track{height:5px;background:var(--surface2);border-radius:3px;margin-top:.2rem;overflow:hidden}
.bar .fill{height:100%;background:var(--accent);border-radius:3px}
.warn{margin-top:.6rem;padding:.5rem .7rem;border-radius:6px;background:#fdf6e8;
border:1px solid #f0dcb4;font-size:.8rem;color:#7a5610}
.nd{margin-top:.6rem;padding:.5rem .7rem;border-radius:6px;background:var(--surface2);
border:1px solid var(--line2);font-size:.8rem;color:var(--ink2)}
.agree{font-size:.74rem;font-weight:700}
.agree.yes{color:var(--ok)}.agree.no{color:var(--stop)}
.empty{padding:2.2rem 1rem;text-align:center;color:var(--muted)}
.note{margin-top:1.4rem;padding-left:.8rem;border-left:2px solid var(--accent);color:var(--ink2);
font-size:.84rem;max-width:76ch}
"""


def _opt(value: str, label: str, selected: str = "") -> str:
    sel = " selected" if value == selected else ""
    return '<option value="{}"{}>{}</option>'.format(html.escape(value), sel, html.escape(label))


def render_form() -> str:
    today = date.today().isoformat()
    bodies = "".join(_opt(b.value, BODY_LABELS[b], BodyType.SUV_4X4.value) for b in BodyType)
    powers = "".join(
        _opt(p.value, POWERTRAIN_LABELS[p], Powertrain.HYBRID.value) for p in Powertrain
    )
    return """
<form method="post" action="/add" class="panel">
  <div class="panel-h">Saisir un véhicule</div>
  <div class="grid">
    <div class="fld"><label>Marque</label><input name="make" required value="Toyota"></div>
    <div class="fld"><label>Modèle</label><input name="model" required value="C-HR Hybrid"></div>
    <div class="fld"><label>1re immatriculation</label><input type="date" name="first_registration" required value="2021-06-01"></div>
    <div class="fld"><label>Kilométrage</label><input type="number" name="mileage_km" min="0" step="1000" required value="68000"></div>
    <div class="fld"><label>Carrosserie</label><select name="body_type">%s</select></div>
    <div class="fld"><label>Motorisation</label><select name="powertrain">%s</select></div>
    <div class="fld"><label>CO₂ WLTP (g/km)</label><input type="number" name="co2_wltp" min="0" max="500" required value="48"></div>
    <div class="fld"><label>Prix demandé (€)</label><input type="number" name="asking_price" min="0" step="100" required value="15200"></div>
    <div class="fld"><label>Source</label><select name="source_type">
      <option value="b2b">B2B — plateforme pro</option>
      <option value="c2c">C2C — particulier</option></select></div>
    <div class="fld"><label>Régime TVA</label><select name="vat_regime">
      <option value="deductible">TVA déductible</option>
      <option value="margin">Régime de la marge</option></select></div>
    <div class="fld"><label>Prix marché grec (€)</label><input type="number" name="greek_market_price" min="0" step="100" required value="24000"></div>
    <div class="fld"><label>Délai de vente estimé (jours)</label><input type="number" name="days_to_sell" min="1" max="365" required value="12"></div>
    <div class="fld"><label>Immatriculation prévue</label><input type="date" name="expected_registration" required value="%s"></div>
    <div class="fld"><label>Fiabilité mécanique (0-100)</label><input type="number" name="mechanical" min="0" max="100" required value="80"></div>
    <div class="fld"><label>État / remise en état (0-100)</label><input type="number" name="refurbishment" min="0" max="100" required value="75"></div>
    <div class="fld"><label>Votre avis, avant le score</label><select name="own_verdict">
      <option value="">—</option>
      <option value="buy">J'achète</option>
      <option value="negotiate">Je négocie</option>
      <option value="reject">Je passe</option>
      <option value="unsure">Je ne sais pas</option></select></div>
  </div>
  <div class="foot"><button type="submit">Analyser</button></div>
</form>
""" % (bodies, powers, today)


def _ranking_rows(rows: List[Analysis], other_order: List[str]) -> str:
    out = []
    for rank, a in enumerate(rows, 1):
        was = other_order.index(a.entry.id) + 1
        move = ""
        if was != rank:
            arrow = "▲" if was > rank else "▼"
            move = '<span class="moved">{}{}</span>'.format(arrow, abs(was - rank))
        out.append(
            "<tr><td class='rank'>{r}</td><td><span class='name'>{n}</span> {m}</td>"
            "<td class='num'>{p}</td><td class='num'>{d} j</td><td class='num'>{y}</td></tr>".format(
                r=rank,
                n=html.escape(a.name),
                m=move,
                p=format_eur(a.outcome.profit_total),
                d=a.outcome.days_held,
                y=format_eur(a.outcome.annual_profit_potential),
            )
        )
    return "".join(out)


def render_rankings(analyses: List[Analysis]) -> str:
    if not analyses:
        return (
            '<div class="panel" style="margin-top:1.5rem"><div class="empty">'
            "Aucun véhicule. Saisissez-en un pour voir les deux classements.</div></div>"
        )

    by_margin = sorted(analyses, key=lambda a: -a.outcome.profit_total)
    by_year = sorted(analyses, key=lambda a: -a.outcome.annual_profit_potential)

    margin_ids = [a.entry.id for a in by_margin]
    year_ids = [a.entry.id for a in by_year]

    verdict = (
        "Les deux classements coïncident sur cet échantillon."
        if margin_ids == year_ids
        else "Les deux classements diffèrent — c'est la thèse du produit."
    )

    head = (
        "<tr><th></th><th>Véhicule</th><th style='text-align:right'>Marge/vente</th>"
        "<th style='text-align:right'>Immobilisé</th>"
        "<th style='text-align:right'>Bénéfice/an</th></tr>"
    )

    return """
<div class="cols">
  <div class="panel"><div class="panel-h">Par marge unitaire</div>
    <div class="scroll"><table><thead>%s</thead><tbody>%s</tbody></table></div></div>
  <div class="panel"><div class="panel-h">Par rendement annuel du capital</div>
    <div class="scroll"><table><thead>%s</thead><tbody>%s</tbody></table></div></div>
</div>
<p class="note">%s</p>
""" % (
        head,
        _ranking_rows(by_margin, year_ids),
        head,
        _ranking_rows(by_year, margin_ids),
        html.escape(verdict),
    )


def _bar(label: str, value: Decimal) -> str:
    return (
        "<div class='bar'>{l} · {v}<div class='track'>"
        "<div class='fill' style='width:{v}%'></div></div></div>"
    ).format(l=html.escape(label), v=int(value))


def render_details(analyses: List[Analysis]) -> str:
    if not analyses:
        return ""
    cards = []
    for a in sorted(analyses, key=lambda x: -x.outcome.annual_profit_potential):
        d = a.decision
        agree = ""
        if a.agrees_with_owner is True:
            agree = "<span class='agree yes'>✓ d'accord avec vous</span>"
        elif a.agrees_with_owner is False:
            agree = "<span class='agree no'>✗ en désaccord avec vous</span>"

        warnings = "".join(
            "<div class='warn'>⚠ {}</div>".format(html.escape(w)) for w in d.warnings
        )
        reasons = "".join(
            "<div class='nd'>{}</div>".format(html.escape(r)) for r in d.reasons
        )

        bars = "".join(
            _bar(k, v)
            for k, v in [
                ("Rotation", a.score.components["rotation"]),
                ("Rentabilité", a.score.components["profitability"]),
                ("Mécanique", a.score.components["mechanical_risk"]),
                ("Remise en état", a.score.components["refurbishment_risk"]),
                ("Fiscalité", a.score.components["tax_exposure"]),
            ]
        )

        cards.append(
            """
<div class="card">
  <div class="card-h">
    <div><span class="name">{name}</span>
      <span class="badge {srccls}">{src}</span>
      <span class="badge">{body}</span></div>
    <div>
      {agree}
      <span class="badge {vcls}">{verdict} · {score}/100</span>
      <form method="post" action="/delete" style="display:inline">
        <input type="hidden" name="id" value="{id}">
        <button class="danger" type="submit">supprimer</button></form>
    </div>
  </div>
  <div class="bars">{bars}</div>
  <div class="scroll"><table style="margin-top:.7rem"><tbody>
    <tr><td>Prix demandé</td><td class="num">{ask}</td>
        <td>Prix maximal d'achat</td><td class="num">{max}</td></tr>
    <tr><td>Taxe d'immatriculation</td><td class="num">{tax}</td>
        <td>Capital immobilisé</td><td class="num">{cap}</td></tr>
    <tr><td>Bénéfice Belgique</td><td class="num">{pbe}</td>
        <td>Bénéfice Grèce</td><td class="num">{pgr}</td></tr>
    <tr><td>ROI grec</td><td class="num">{roi}</td>
        <td>Rotations par an</td><td class="num">{rot}</td></tr>
  </tbody></table></div>
  {warnings}{reasons}
</div>""".format(
                name=html.escape(a.name),
                srccls="b2b" if a.entry.source_type == "b2b" else "c2c",
                src="B2B" if a.entry.source_type == "b2b" else "C2C",
                body=html.escape(BODY_LABELS[BodyType(a.entry.body_type)]),
                agree=agree,
                vcls=VERDICT_CLASS[d.verdict],
                verdict=html.escape(d.verdict.label),
                score=d.score,
                id=html.escape(a.entry.id),
                bars=bars,
                ask=format_eur(euro(a.entry.asking_price)),
                max=format_eur(a.max_price),
                tax=format_eur(a.tax.registration_tax),
                cap=format_eur(a.outcome.capital_employed),
                pbe=format_eur(a.outcome.profit_belgium),
                pgr=format_eur(a.outcome.profit_greece),
                roi=str((a.outcome.roi_greece * 100).quantize(Decimal("0.1"))) + " %",
                rot=str(a.outcome.rotations_per_year.quantize(Decimal("0.1"))),
                warnings=warnings,
                reasons=reasons,
            )
        )

    return '<div class="panel detail"><div class="panel-h">Détail par véhicule</div>{}</div>'.format(
        "".join(cards)
    )


def render_page(analyses: List[Analysis]) -> str:
    return """<!doctype html><html lang="fr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>BG Auto Agent</title><style>%s</style></head><body><div class="wrap">
<h1>BG Auto Agent</h1>
<p class="sub">Saisissez des voitures que vous connaissez, puis regardez si le moteur
est d'accord avec vous. Les deux classements ci-dessous répondent à la même question
de deux façons : ce que rapporte une vente, et ce que rapporte le capital sur une année.</p>
%s%s%s
<p class="note">Le taux de base de la taxe grecque est un curseur provisoire à 35 %%
et la dépréciation kilométrique manque : toute décision reposant dessus sort
<strong>non décisionnelle</strong>. C'est voulu — le moteur refuse de dire ACHETER
sur une donnée qu'il sait fausse.</p>
</div></body></html>""" % (
        STYLE,
        render_form(),
        render_rankings(analyses),
        render_details(analyses),
    )


# --- HTTP ----------------------------------------------------------------


def _first(form: Dict[str, List[str]], key: str, default: str = "") -> str:
    values = form.get(key) or []
    return values[0].strip() if values else default


class Handler(BaseHTTPRequestHandler):
    store = Store()

    def _send(self, status: int, body: str, content_type: str = "text/html; charset=utf-8") -> None:
        payload = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def _redirect(self) -> None:
        self.send_response(303)
        self.send_header("Location", "/")
        self.end_headers()

    def do_GET(self) -> None:  # noqa: N802
        if urlparse(self.path).path != "/":
            self._send(404, "<h1>404</h1>")
            return
        analyses = []
        for entry in self.store.load():
            try:
                analyses.append(analyse(entry))
            except (ValueError, InvalidOperation, KeyError) as exc:
                # One malformed entry must not blank the page.
                self.log_message("entrée ignorée %s: %s", entry.id, exc)
        self._send(200, render_page(analyses))

    def do_POST(self) -> None:  # noqa: N802
        length = int(self.headers.get("Content-Length", "0"))
        form = parse_qs(self.rfile.read(length).decode("utf-8"))
        path = urlparse(self.path).path

        if path == "/delete":
            self.store.delete(_first(form, "id"))
            self._redirect()
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
            )
            analyse(entry)  # fail here rather than on every later page load
        except (ValueError, InvalidOperation, KeyError) as exc:
            self._send(400, "<h1>Saisie invalide</h1><p>{}</p><a href='/'>retour</a>".format(
                html.escape(str(exc))))
            return

        self.store.add(entry)
        self._redirect()

    def log_message(self, fmt: str, *args) -> None:  # noqa: A003
        pass  # quiet by default; errors still surface in responses


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
