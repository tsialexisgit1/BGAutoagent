"""Rendering. One module so the server stays about serving."""

from __future__ import annotations

import html
from datetime import date
from decimal import Decimal
from typing import List, Optional

from . import sources as src
from . import workflow as wf
from .money import euro, format_eur
from .vehicle import BodyType, Powertrain, SourceType

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

STATUS_LABELS = {
    src.Status.ACTIVE: ("Actif", "s-ok"),
    src.Status.TO_CONTACT: ("À contacter", "s-todo"),
    src.Status.LEGAL_REVIEW: ("À valider juridiquement", "s-legal"),
    src.Status.TO_VERIFY: ("À vérifier", "s-todo"),
    src.Status.BLOCKED: ("Fermé au scraping", "s-blocked"),
}

ACCESS_LABELS = {
    src.Access.OFFICIAL_API: "API officielle",
    src.Access.SCRAPING_API: "API de scraping",
    src.Access.OWN_SCRAPER: "Scraper maison",
    src.Access.MANUAL: "Saisie manuelle",
    src.Access.UNKNOWN: "À déterminer",
}

STYLE = """
:root{--ground:#f7f8f9;--surface:#fff;--surface2:#eef1f4;--ink:#1b2227;--ink2:#54616b;
--muted:#8996a1;--line:#e2e7eb;--line2:#c9d2d9;--accent:#0b6b7a;--accent-soft:#dcecef;
--ok:#127a45;--warn:#a86616;--stop:#b5372a;--lock:#aab4bd;
--font:"Avenir Next","Segoe UI",system-ui,-apple-system,sans-serif;
--mono:ui-monospace,"SF Mono",Menlo,Consolas,monospace}
*{box-sizing:border-box}
body{margin:0;background:var(--ground);color:var(--ink);font-family:var(--font);
font-size:14px;line-height:1.5;-webkit-font-smoothing:antialiased}
a{color:var(--accent)}
.app{display:grid;grid-template-columns:264px 1fr;min-height:100vh}
.side{background:var(--surface);border-right:1px solid var(--line);padding:1.2rem .8rem;
position:sticky;top:0;height:100vh;overflow-y:auto}
.brand{font-weight:800;letter-spacing:-.03em;font-size:1.05rem;padding:0 .5rem 1rem}
.brand small{display:block;font-weight:500;font-size:.7rem;color:var(--muted);letter-spacing:0}
.ctx{margin:0 .5rem .9rem;padding:.55rem .6rem;background:var(--surface2);border-radius:7px;font-size:.78rem}
.ctx b{display:block;font-size:.82rem}
.ctx a{font-size:.72rem}
.stp{display:grid;grid-template-columns:1.7rem 1fr;gap:.55rem;align-items:start;
padding:.5rem .55rem;border-radius:7px;text-decoration:none;color:var(--ink2);margin-bottom:.15rem}
.stp:hover{background:var(--surface2)}
.stp .n{width:1.7rem;height:1.7rem;border-radius:50%;display:grid;place-items:center;
font-family:var(--mono);font-size:.72rem;font-weight:700;background:var(--surface2);
color:var(--muted);border:1px solid var(--line)}
.stp .t{font-size:.83rem;font-weight:600;padding-top:.15rem}
.stp.done .n{background:#dff3e6;color:var(--ok);border-color:transparent}
.stp.current{background:var(--accent-soft)}
.stp.current .n{background:var(--accent);color:#fff;border-color:var(--accent)}
.stp.current .t{color:var(--accent);font-weight:700}
.stp.locked{color:var(--lock);cursor:not-allowed;pointer-events:none}
.stp.locked .n{color:var(--lock)}
.main{padding:1.7rem 2rem 4rem;min-width:0}
h1{font-size:1.4rem;letter-spacing:-.028em;margin:0}
.eyebrow{font-size:.66rem;font-weight:700;letter-spacing:.14em;text-transform:uppercase;color:var(--accent)}
.sub{color:var(--ink2);margin:.4rem 0 1.5rem;max-width:74ch}
.panel{background:var(--surface);border:1px solid var(--line);border-radius:10px;overflow:hidden;margin-bottom:1rem}
.panel-h{padding:.8rem 1rem;border-bottom:1px solid var(--line);font-weight:700;font-size:.85rem;
display:flex;justify-content:space-between;align-items:center;gap:1rem;flex-wrap:wrap}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:.9rem;padding:1rem}
.fld{display:flex;flex-direction:column;gap:.3rem}
.fld label{font-size:.75rem;font-weight:600;color:var(--ink2)}
.fld input,.fld select{font:inherit;font-size:.86rem;color:var(--ink);background:var(--ground);
border:1px solid var(--line2);border-radius:6px;padding:.42rem .55rem;width:100%}
.fld input:focus-visible,.fld select:focus-visible{outline:2px solid var(--accent);outline-offset:1px}
.foot{padding:.85rem 1rem;border-top:1px solid var(--line);display:flex;gap:.6rem;
justify-content:flex-end;align-items:center;flex-wrap:wrap}
.foot .left{margin-right:auto;color:var(--ink2);font-size:.8rem}
button{font:inherit;font-size:.85rem;font-weight:600;padding:.45rem .9rem;border-radius:6px;
cursor:pointer;background:var(--accent);color:#fff;border:1px solid var(--accent)}
button:hover{filter:brightness(1.1)}
button.ghost{background:var(--surface);color:var(--accent)}
button.danger{background:var(--surface);color:var(--stop);border-color:var(--line2);
padding:.2rem .5rem;font-size:.75rem}
.scroll{overflow-x:auto}
table{width:100%;border-collapse:collapse;font-size:.85rem;min-width:440px}
th{text-align:left;font-size:.65rem;letter-spacing:.09em;text-transform:uppercase;color:var(--muted);
padding:.55rem .8rem;border-bottom:1px solid var(--line);white-space:nowrap}
td{padding:.55rem .8rem;border-bottom:1px solid var(--line);vertical-align:top}
tr:last-child td{border-bottom:0}
.num{font-family:var(--mono);font-variant-numeric:tabular-nums;text-align:right;white-space:nowrap}
.rank{font-family:var(--mono);color:var(--muted);width:1.6rem}
.name{font-weight:600}
.badge{font-size:.7rem;font-weight:700;padding:.14rem .45rem;border-radius:4px;white-space:nowrap}
.b2b{background:var(--accent-soft);color:var(--accent)}
.c2c{background:#fdeee9;color:var(--stop)}
.sim{background:#f2eefb;color:#5b3fa0}
.s-ok{background:#dff3e6;color:var(--ok)}
.s-todo{background:#fdf0dc;color:var(--warn)}
.s-legal{background:#fdeae7;color:var(--stop)}
.s-blocked{background:var(--surface2);color:var(--muted)}
.v-buy,.v-buy-soft{background:#dff3e6;color:var(--ok)}
.v-negotiate{background:#fdf0dc;color:var(--warn)}
.v-reject{background:#fdeae7;color:var(--stop)}
.v-unknown{background:var(--surface2);color:var(--muted)}
.moved{font-size:.7rem;font-family:var(--mono);color:var(--accent);font-weight:700}
.cols{display:grid;grid-template-columns:1fr 1fr;gap:1rem}
@media(max-width:1100px){.cols{grid-template-columns:1fr}}
@media(max-width:900px){.app{grid-template-columns:1fr}.side{position:static;height:auto}
.main{padding:1.3rem 1.1rem 3rem}}
.bars{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:.6rem;padding:1rem}
.bar{font-size:.75rem;color:var(--ink2)}
.bar b{color:var(--ink);font-family:var(--mono)}
.bar .track{height:6px;background:var(--surface2);border-radius:3px;margin-top:.25rem;overflow:hidden}
.bar .fill{height:100%;background:var(--accent);border-radius:3px}
.bar .w{font-size:.68rem;color:var(--muted)}
.warn{margin:0 1rem 1rem;padding:.55rem .75rem;border-radius:6px;background:#fdf6e8;
border:1px solid #f0dcb4;font-size:.8rem;color:#7a5610}
.nd{margin:0 1rem 1rem;padding:.55rem .75rem;border-radius:6px;background:var(--surface2);
border:1px solid var(--line2);font-size:.8rem;color:var(--ink2)}
.big{padding:1.3rem 1rem;text-align:center}
.big .verdict{font-size:1.5rem;font-weight:800;letter-spacing:-.03em}
.big .score{font-family:var(--mono);color:var(--muted);font-size:.85rem;margin-top:.2rem}
.empty{padding:2.2rem 1rem;text-align:center;color:var(--muted)}
.note{margin-top:1.2rem;padding-left:.8rem;border-left:2px solid var(--accent);color:var(--ink2);
font-size:.83rem;max-width:78ch}
.kv td:first-child{color:var(--ink2);width:45%}
.mark{font-family:var(--mono);font-size:.78rem}
"""


def esc(value) -> str:
    return html.escape(str(value))


# --- shell ----------------------------------------------------------------


def render_nav(current: str, entry=None) -> str:
    confirmed = list(entry.confirmed) if entry else []
    ctx = ""
    if entry is not None:
        ctx = (
            '<div class="ctx"><b>{}</b>{} · {}<br>'
            '<a href="/?step=opportunites">changer de véhicule</a></div>'
        ).format(
            esc("{} {}".format(entry.make, entry.model)),
            esc(format_eur(euro(entry.asking_price))),
            esc(BODY_LABELS[BodyType(entry.body_type)]),
        )
    else:
        ctx = (
            '<div class="ctx">Aucun véhicule sélectionné<br>'
            '<a href="/?step=opportunites">en choisir un</a></div>'
        )

    items = []
    for s in wf.STEPS:
        state = wf.state_of(s.key, current, confirmed)
        if s.per_vehicle and entry is None:
            state = "locked"
        href = "/?step={}{}".format(s.key, "&id=" + entry.id if entry else "")
        # Confirmed keeps its tick even while you are standing on it — coming
        # back to a step should not make it look unfinished.
        mark = "✓" if (state == "done" or s.key in confirmed) else str(s.number)
        tag = "a" if state != "locked" else "span"
        items.append(
            '<{tag} class="stp {st}"{href}><div class="n">{m}</div>'
            '<div class="t">{t}</div></{tag}>'.format(
                tag=tag,
                st=state,
                href=' href="{}"'.format(href) if state != "locked" else "",
                m=mark,
                t=esc(s.title),
            )
        )

    return (
        '<aside class="side"><div class="brand">BG Auto Agent'
        "<small>Acheter, ou non</small></div>{}{}</aside>"
    ).format(ctx, "".join(items))


def shell(current: str, entry, content: str) -> str:
    return (
        '<!doctype html><html lang="fr"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        "<title>BG Auto Agent</title><style>{}</style></head><body>"
        '<div class="app">{}<main class="main">{}</main></div></body></html>'
    ).format(STYLE, render_nav(current, entry), content)


def header(step: wf.Step) -> str:
    return (
        '<div class="eyebrow">Étape {}</div><h1>{}</h1><p class="sub">{}</p>'
    ).format(step.number, esc(step.title), esc(step.summary))


def confirm_bar(step_key: str, entry, extra_left: str = "") -> str:
    """The action that unlocks the next step, or the note that it already is."""
    nxt = wf.next_step(step_key)
    if entry is None or nxt is None:
        return ""
    done = entry.has_confirmed(step_key)
    if done:
        return (
            '<div class="foot"><span class="left">{}Étape confirmée.</span>'
            '<form method="post" action="/unconfirm"><input type="hidden" name="id" value="{}">'
            '<input type="hidden" name="step" value="{}">'
            '<button class="ghost" type="submit">Rouvrir</button></form>'
            '<a href="/?step={}&id={}"><button type="button">Suivant : {}</button></a></div>'
        ).format(extra_left, esc(entry.id), esc(step_key), nxt.key, esc(entry.id), esc(nxt.title))
    return (
        '<div class="foot"><span class="left">{}</span>'
        '<form method="post" action="/confirm"><input type="hidden" name="id" value="{}">'
        '<input type="hidden" name="step" value="{}">'
        '<button type="submit">Confirmer et passer à : {}</button></form></div>'
    ).format(extra_left, esc(entry.id), esc(step_key), esc(nxt.title))


# --- step 1: sources ------------------------------------------------------


def page_sources() -> str:
    rows = []
    for s in src.CATALOGUE:
        label, cls = STATUS_LABELS[s.status]
        rows.append(
            "<tr><td><span class='name'>{n}</span><br>"
            "<span class='badge {tc}'>{t}</span></td>"
            "<td>{r}<br><span class='mark'>vérifié le {d}</span></td>"
            "<td>{a}<br><span class='mark'>{an}</span></td>"
            "<td><span class='badge {cls}'>{st}</span></td>"
            "<td class='num'>{c} %</td></tr>".format(
                n=esc(s.name),
                tc="b2b" if s.source_type is SourceType.B2B else "c2c",
                t="B2B" if s.source_type is SourceType.B2B else "C2C",
                r=esc(s.robots_txt),
                d=esc(s.robots_checked),
                a=esc(ACCESS_LABELS[s.access]),
                an=esc(s.api_note),
                cls=cls,
                st=esc(label),
                c=s.confidence_pct,
            )
        )

    notes = "".join(
        "<div class='nd'><b>{}</b> — {}</div>".format(esc(s.name), esc(s.note))
        for s in src.CATALOGUE
        if s.note
    )

    active = len(src.collectable())

    return header(wf.BY_KEY["sources"]) + """
<div class="panel">
  <div class="panel-h"><span>Les huit sources</span>
    <span class="mark">{active} interrogeables aujourd'hui</span></div>
  <div class="scroll"><table>
    <thead><tr><th>Source</th><th>robots.txt</th><th>Accès</th><th>Statut</th>
    <th style="text-align:right">Confiance</th></tr></thead>
    <tbody>{rows}</tbody></table></div>
  {notes}
</div>
<p class="note"><b>La confiance n'est pas décorative</b> : elle multiplie le BG Score
de tout ce qui vient de la source. Un 94 issu d'une source à 50 % de confiance
n'est pas un 94.</p>
<p class="note">Un <code>robots.txt</code> permissif ne rend rien légal. Il ne dit rien
des conditions d'utilisation, du droit des bases de données, ni des données
personnelles. Les quatre plateformes B2B sont ouvertes techniquement et fermées
commercialement : l'accès s'y négocie.</p>
""".format(rows="".join(rows), notes=notes, active=active)


# --- step 2: opportunities ------------------------------------------------


def opportunity_form() -> str:
    today = date.today().isoformat()
    bodies = "".join(
        "<option value='{}'{}>{}</option>".format(
            b.value, " selected" if b is BodyType.SUV_4X4 else "", esc(BODY_LABELS[b])
        )
        for b in BodyType
    )
    powers = "".join(
        "<option value='{}'{}>{}</option>".format(
            p.value, " selected" if p is Powertrain.HYBRID else "", esc(POWERTRAIN_LABELS[p])
        )
        for p in Powertrain
    )
    srcs = "".join(
        "<option value='{}'>{}</option>".format(esc(s.key), esc(s.name)) for s in src.CATALOGUE
    )
    return """
<form method="post" action="/add" class="panel">
  <div class="panel-h">Saisir un véhicule</div>
  <div class="grid">
    <div class="fld"><label>Marque</label><input name="make" required value="Toyota"></div>
    <div class="fld"><label>Modèle</label><input name="model" required value="C-HR Hybrid"></div>
    <div class="fld"><label>Source</label><select name="source_key"><option value="">Saisie manuelle</option>%s</select></div>
    <div class="fld"><label>1re immatriculation</label><input type="date" name="first_registration" required value="2021-06-01"></div>
    <div class="fld"><label>Kilométrage</label><input type="number" name="mileage_km" min="0" step="1000" required value="68000"></div>
    <div class="fld"><label>Carrosserie</label><select name="body_type">%s</select></div>
    <div class="fld"><label>Motorisation</label><select name="powertrain">%s</select></div>
    <div class="fld"><label>CO₂ WLTP (g/km)</label><input type="number" name="co2_wltp" min="0" max="500" required value="48"></div>
    <div class="fld"><label>Prix demandé (€)</label><input type="number" name="asking_price" min="0" step="100" required value="15200"></div>
    <div class="fld"><label>Type de vendeur</label><select name="source_type">
      <option value="b2b">B2B — plateforme pro</option><option value="c2c">C2C — particulier</option></select></div>
    <div class="fld"><label>Régime TVA</label><select name="vat_regime">
      <option value="deductible">TVA déductible</option><option value="margin">Régime de la marge</option></select></div>
    <div class="fld"><label>Prix marché grec (€)</label><input type="number" name="greek_market_price" min="0" step="100" required value="24000"></div>
    <div class="fld"><label>Délai de vente estimé (j)</label><input type="number" name="days_to_sell" min="1" max="365" required value="12"></div>
    <div class="fld"><label>Immatriculation prévue</label><input type="date" name="expected_registration" required value="%s"></div>
    <div class="fld"><label>Fiabilité mécanique (0-100)</label><input type="number" name="mechanical" min="0" max="100" required value="80"></div>
    <div class="fld"><label>Remise en état (0-100)</label><input type="number" name="refurbishment" min="0" max="100" required value="75"></div>
    <div class="fld"><label>Votre avis, avant le score</label><select name="own_verdict">
      <option value="">—</option><option value="buy">J'achète</option>
      <option value="negotiate">Je négocie</option><option value="reject">Je passe</option>
      <option value="unsure">Je ne sais pas</option></select></div>
  </div>
  <div class="foot"><button type="submit">Ajouter l'opportunité</button></div>
</form>
""" % (srcs, bodies, powers, today)


def _ranking_rows(rows, other_ids) -> str:
    out = []
    for rank, a in enumerate(rows, 1):
        was = other_ids.index(a.entry.id) + 1
        move = ""
        if was != rank:
            move = '<span class="moved">{}{}</span>'.format("▲" if was > rank else "▼", abs(was - rank))
        out.append(
            "<tr><td class='rank'>{r}</td><td><a href='/?step=marche&id={i}'>"
            "<span class='name'>{n}</span></a> {m}</td>"
            "<td class='num'>{p}</td><td class='num'>{d} j</td>"
            "<td class='num'>{y}</td></tr>".format(
                r=rank, i=esc(a.entry.id), n=esc(a.name), m=move,
                p=esc(format_eur(a.outcome.profit_total)),
                d=a.outcome.days_held,
                y=esc(format_eur(a.outcome.annual_profit_potential)),
            )
        )
    return "".join(out)


def opportunity_level(a):
    """A triage signal: how promising, before the reliability gate has its say.

    Deliberately separate from the verdict. Today every verdict comes out
    NON DÉCISIONNEL because official tables are missing, so a verdict column
    would tell you nothing — yet the economics still differ from one car to the
    next, and that difference is what you need in a list.

    Le potentiel trie ; le verdict décide.
    """
    o = a.outcome
    if not o.meets_all_targets:
        return ("Bas", "v-reject")
    if a.score.total >= 80:
        return ("Élevé", "v-buy")
    if a.score.total >= 70:
        return ("Moyen", "v-negotiate")
    return ("Bas", "v-reject")


def page_opportunities(analyses) -> str:
    head = header(wf.BY_KEY["opportunites"])

    collect = """
<div class="panel"><div class="panel-h"><span>Collecte automatique</span>
<form method="post" action="/simulate"><button class="ghost" type="submit">
Simuler une collecte</button></form></div>
<div class="nd">Aucune source n'est connectée. Ce bouton fabrique des annonces
plausibles, marquées <b>simulées</b>, pour éprouver le parcours de bout en bout.
Rien ici ne provient d'un site réel.</div></div>
"""

    if not analyses:
        return head + collect + opportunity_form() + (
            '<div class="panel"><div class="empty">Aucune opportunité. '
            "Saisissez-en une ou simulez une collecte.</div></div>"
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

    th = ("<tr><th></th><th>Véhicule</th><th style='text-align:right'>Marge/vente</th>"
          "<th style='text-align:right'>Immobilisé</th>"
          "<th style='text-align:right'>Bénéfice/an</th></tr>")

    rankings = """
<div class="cols">
  <div class="panel"><div class="panel-h">Par marge unitaire</div>
    <div class="scroll"><table><thead>{th}</thead><tbody>{a}</tbody></table></div></div>
  <div class="panel"><div class="panel-h">Par rendement annuel du capital</div>
    <div class="scroll"><table><thead>{th}</thead><tbody>{b}</tbody></table></div></div>
</div>
<p class="note">{v}</p>
""".format(th=th, a=_ranking_rows(by_margin, year_ids), b=_ranking_rows(by_year, margin_ids),
           v=esc(verdict))

    rows = []
    for a in by_year:
        s = src.get(a.entry.source_key)
        level, level_cls = opportunity_level(a)
        done = len([c for c in a.entry.confirmed if c in wf.VEHICLE_ORDER])
        total = len(wf.VEHICLE_ORDER)
        spread = euro(a.entry.greek_market_price) - euro(a.entry.asking_price)
        rows.append(
            "<tr><td><a href='/?step=marche&id={i}'><span class='name'>{n}</span></a>{sim}<br>"
            "<span class='mark'>{srcname}</span> "
            "<span class='badge {tc}'>{t}</span></td>"
            "<td class='num'>{year}</td>"
            "<td class='num'>{km}</td>"
            "<td class='num'>{pbe}</td>"
            "<td class='num'>{pgr}<br><span class='mark'>{spread}</span></td>"
            "<td><span class='badge {lc}'>{lvl}</span></td>"
            "<td class='num'>{done}/{total}</td>"
            "<td><form method='post' action='/delete'><input type='hidden' name='id' value='{i}'>"
            "<button class='danger' type='submit'>suppr.</button></form></td></tr>".format(
                i=esc(a.entry.id), n=esc(a.name),
                sim=" <span class='badge sim'>simulée</span>" if a.entry.simulated else "",
                srcname=esc(s.name) if s else "Saisie manuelle",
                tc="b2b" if a.entry.source_type == "b2b" else "c2c",
                t="B2B" if a.entry.source_type == "b2b" else "C2C",
                year=esc(a.entry.first_registration[:4]),
                km="{} km".format("{:,}".format(a.entry.mileage_km).replace(",", " ")),
                pbe=esc(format_eur(euro(a.entry.asking_price))),
                pgr=esc(format_eur(euro(a.entry.greek_market_price))),
                spread=("+" if spread >= 0 else "") + esc(format_eur(spread)),
                lc=level_cls, lvl=esc(level),
                done=done, total=total,
            )
        )

    listing = """
<div class="panel"><div class="panel-h"><span>Opportunités ({n})</span>
<span class="mark">triées par rendement annuel</span></div>
<div class="scroll"><table><thead><tr>
<th>Véhicule</th><th style="text-align:right">Année</th><th style="text-align:right">Km</th>
<th style="text-align:right">Prix Belgique</th><th style="text-align:right">Marché Grèce</th>
<th>Potentiel</th><th style="text-align:right">Avancement</th><th></th></tr></thead>
<tbody>{rows}</tbody></table></div>
<div class="nd"><b>Rien n'est filtré ici.</b> Une voiture dont le marché grec serait
inférieur au prix belge apparaîtrait quand même, avec une marge négative — c'est à
cela que sert la colonne <b>Potentiel</b>.<br>
Le <b>potentiel</b> trie, il ne décide pas : il regarde l'économie de l'affaire
(objectifs atteints et BG Score) sans tenir compte de la fiabilité des données.
Le <b>verdict</b>, lui, tient compte des deux — et c'est lui qui autorise ou non
l'achat, à l'étape 6.<br>
L'<b>avancement</b> compte les étapes du parcours véhicule confirmées, sur quatre :
marché grec, calcul, score, décision.</div></div>
""".format(n=len(analyses), rows="".join(rows))

    return head + collect + rankings + listing + opportunity_form()


# --- step 3: Greek market -------------------------------------------------


def page_market(a) -> str:
    o = a.outcome
    return header(wf.BY_KEY["marche"]) + """
<div class="panel"><div class="panel-h">Référence de revente</div>
<div class="scroll"><table class="kv"><tbody>
<tr><td>Prix de marché grec observé</td><td class="num">{market}</td></tr>
<tr><td>Marge de sécurité appliquée</td><td class="num">{margin} %</td></tr>
<tr><td><b>Prix de revente prudent</b></td><td class="num"><b>{prudent}</b></td></tr>
</tbody></table></div>
<div class="nd">Les annonces grecques affichent des <b>prix demandés</b>, pas des prix
de transaction — systématiquement optimistes. La marge de sécurité corrige ce biais ;
elle devra être recalibrée par modèle sur vos ventes réelles.</div></div>

<div class="panel"><div class="panel-h">Rotation du capital</div>
<div class="scroll"><table class="kv"><tbody>
<tr><td>Délai de vente estimé</td><td class="num">{days} j</td></tr>
<tr><td>Administratif : transport, douane, immatriculation</td><td class="num">{admin} j</td></tr>
<tr><td><b>Capital immobilisé</b></td><td class="num"><b>{held} j</b></td></tr>
<tr><td>Rotations par an</td><td class="num">{rot}</td></tr>
</tbody></table></div>
<div class="nd">C'est le <b>capital immobilisé</b> qui compte, pas le délai de vente :
la voiture mobilise l'argent dès l'achat, bien avant d'être mise en vente.</div>
{confirm}</div>
""".format(
        market=esc(format_eur(euro(a.entry.greek_market_price))),
        margin=str((Decimal("0.075") * 100).quantize(Decimal("0.1"))),
        prudent=esc(format_eur(o.prudent_resale)),
        days=a.entry.days_to_sell,
        admin=o.days_held - a.entry.days_to_sell,
        held=o.days_held,
        rot=str(o.rotations_per_year.quantize(Decimal("0.1"))),
        confirm=confirm_bar("marche", a.entry),
    )


# --- step 4: financials ---------------------------------------------------


def page_calculation(a) -> str:
    o, t = a.outcome, a.tax
    over = euro(a.entry.asking_price) > a.max_price
    return header(wf.BY_KEY["calcul"]) + """
<div class="panel"><div class="panel-h">Taxe d'immatriculation grecque</div>
<div class="scroll"><table class="kv"><tbody>
<tr><td>Dépréciation pour l'âge ({body})</td><td class="num">{dep} %</td></tr>
<tr><td>Ajustement CO₂</td><td class="num">{co2} %</td></tr>
<tr><td>Réduction hybride</td><td class="num">{hyb} %</td></tr>
<tr><td>Valeur taxable</td><td class="num">{taxable}</td></tr>
<tr><td><b>Taxe due</b></td><td class="num"><b>{tax}</b></td></tr>
<tr><td>Règle appliquée</td><td class="num mark">{rule}</td></tr>
<tr><td>Date d'immatriculation retenue</td><td class="num mark">{regdate}</td></tr>
</tbody></table></div>
<div class="nd">La taxe est calculée <b>à la date d'immatriculation prévue</b>, pas à la
date d'achat : une voiture achetée en décembre et immatriculée en janvier paie le
tarif de janvier.</div></div>

<div class="panel"><div class="panel-h">Coût de revient et marges</div>
<div class="scroll"><table class="kv"><tbody>
<tr><td>Prix demandé</td><td class="num">{ask}</td></tr>
<tr><td><b>Prix maximal d'achat</b></td><td class="num"><b>{max}</b>{flag}</td></tr>
<tr><td>Prix de cession à la société grecque</td><td class="num">{transfer}</td></tr>
<tr><td>Transport, préparation, administratif</td><td class="num">{costs}</td></tr>
<tr><td>Capital immobilisé</td><td class="num">{cap}</td></tr>
<tr><td>Bénéfice Belgique {okbe}</td><td class="num">{pbe}</td></tr>
<tr><td>Bénéfice Grèce {okgr}</td><td class="num">{pgr}</td></tr>
<tr><td>ROI grec {okroi}</td><td class="num">{roi} %</td></tr>
<tr><td><b>Bénéfice annuel potentiel</b></td><td class="num"><b>{annual}</b></td></tr>
</tbody></table></div>
{confirm}</div>
""".format(
        body=esc(BODY_LABELS[BodyType(a.entry.body_type)]),
        dep=str((t.age_reduction * 100).quantize(Decimal("0.1"))),
        co2=str((t.co2_adjustment * 100).quantize(Decimal("0.1"))),
        hyb=str((t.hybrid_reduction * 100).quantize(Decimal("0.1"))),
        taxable=esc(format_eur(t.taxable_value)),
        tax=esc(format_eur(t.registration_tax)),
        rule=esc(t.rule_version),
        regdate=esc(t.registration_date.strftime("%d/%m/%Y")),
        ask=esc(format_eur(euro(a.entry.asking_price))),
        max=esc(format_eur(a.max_price)),
        flag=" <span class='badge v-reject'>dépassé</span>" if over else "",
        transfer=esc(format_eur(o.transfer_price)),
        costs=esc(format_eur(o.capital_employed - euro(a.entry.asking_price) - t.registration_tax)),
        cap=esc(format_eur(o.capital_employed)),
        okbe="<span class='badge v-buy'>✓</span>" if o.meets_belgium_target else "<span class='badge v-reject'>✗</span>",
        okgr="<span class='badge v-buy'>✓</span>" if o.meets_greece_profit_target else "<span class='badge v-reject'>✗</span>",
        okroi="<span class='badge v-buy'>✓</span>" if o.meets_greece_roi_target else "<span class='badge v-reject'>✗</span>",
        pbe=esc(format_eur(o.profit_belgium)),
        pgr=esc(format_eur(o.profit_greece)),
        roi=str((o.roi_greece * 100).quantize(Decimal("0.1"))),
        annual=esc(format_eur(o.annual_profit_potential)),
        confirm=confirm_bar("calcul", a.entry),
    )


# --- step 5: score --------------------------------------------------------


def page_score(a) -> str:
    w = a.score.weights
    labels = [
        ("rotation", "Rotation", w.rotation),
        ("profitability", "Rentabilité", w.profitability),
        ("mechanical_risk", "Risque mécanique", w.mechanical_risk),
        ("refurbishment_risk", "Remise en état", w.refurbishment_risk),
        ("tax_exposure", "Fiscalité", w.tax_exposure),
    ]
    bars = "".join(
        "<div class='bar'>{l} · <b>{v}</b><div class='track'>"
        "<div class='fill' style='width:{v}%'></div></div>"
        "<div class='w'>poids {p} %</div></div>".format(
            l=esc(label), v=int(a.score.components[key]), p=int(weight * 100)
        )
        for key, label, weight in labels
    )
    conf = src.get(a.entry.source_key)
    conf_note = ""
    if conf is not None:
        conf_note = (
            "<div class='nd'>Source <b>{}</b>, confiance {} %. "
            "Un score élevé venant d'une source peu fiable reste un score peu fiable.</div>"
        ).format(esc(conf.name), conf.confidence_pct)

    return header(wf.BY_KEY["score"]) + """
<div class="panel"><div class="panel-h"><span>Composantes</span>
<span class="mark">total {total}/100</span></div>
<div class="bars">{bars}</div>
<div class="nd">La rotation pèse le plus parce que l'activité consiste à faire tourner
du capital, pas à maximiser une vente. La rentabilité est calculée sur le
<b>ROI annualisé</b>, pas sur la marge — sinon une affaire grasse et lente
marquerait des points deux fois.</div>
{conf}{confirm}</div>
<p class="note">Les poids sont des <b>hypothèses</b>, pas des réglages.
35/30/15/10/10 est une intuition à éprouver en regardant le classement bouger.</p>
""".format(total=a.score.total, bars=bars, conf=conf_note,
           confirm=confirm_bar("score", a.entry))


# --- step 6: decision -----------------------------------------------------


VERDICT_CLASS = {
    "acheter_immediatement": "v-buy",
    "acheter_si_prix_conforme": "v-buy-soft",
    "negocier": "v-negotiate",
    "rejeter": "v-reject",
    "non_decisionnel": "v-unknown",
}


def page_decision(a) -> str:
    d = a.decision
    reasons = "".join("<div class='nd'>{}</div>".format(esc(r)) for r in d.reasons)
    warnings = "".join("<div class='warn'>⚠ {}</div>".format(esc(w)) for w in d.warnings)

    agree = ""
    if a.agrees_with_owner is True:
        agree = "<div class='nd'>✓ Le moteur est d'accord avec votre avis initial.</div>"
    elif a.agrees_with_owner is False:
        agree = ("<div class='warn'>Le moteur n'est pas d'accord avec votre avis initial. "
                 "Cet écart est la donnée la plus utile que produise l'application aujourd'hui.</div>")

    ledger = "".join(
        "<tr><td>{}</td><td class='num mark'>{}</td><td>{}</td></tr>".format(
            esc(i.name), esc(i.reliability.mark), esc(i.source)
        )
        for i in a.outcome.ledger.inputs
    )

    return header(wf.BY_KEY["decision"]) + """
<div class="panel"><div class="big">
  <div class="verdict"><span class="badge {cls}" style="font-size:1.1rem;padding:.3rem .8rem">{v}</span></div>
  <div class="score">BG Score {s}/100 · plancher de fiabilité {mark}</div>
</div>
{warnings}{reasons}{agree}</div>

<div class="panel"><div class="panel-h">Provenance des données</div>
<div class="scroll"><table><thead><tr><th>Donnée</th><th style="text-align:right">Fiabilité</th>
<th>Source</th></tr></thead><tbody>{ledger}</tbody></table></div>
<div class="nd">{explain}</div></div>

<div class="panel"><div class="panel-h">Validation humaine</div>
<div class="nd">L'agent ne peut jamais acheter, payer, réserver ni envoyer une offre.
Il propose ; vous décidez. Cette contrainte est structurelle, pas un réglage.</div>
{confirm}</div>
""".format(
        cls=VERDICT_CLASS.get(d.verdict.value, "v-unknown"),
        v=esc(d.verdict.label),
        s=d.score,
        mark=esc(a.outcome.ledger.floor.mark),
        warnings=warnings,
        reasons=reasons,
        agree=agree,
        ledger=ledger,
        explain=esc(a.outcome.ledger.explain()),
        confirm=confirm_bar("decision", a.entry),
    )
