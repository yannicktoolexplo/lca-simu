#!/usr/bin/env python3
"""Build one additive offline HTML that consolidates supplier-risk evidence.

The builder is deliberately read-only with respect to every source artifact and
does not call the simulation engine.  Its only write is the requested new HTML.
"""

from __future__ import annotations

import argparse
import csv
import html
import json
from pathlib import Path
from typing import Any


ARTIFACT_ROOT = Path(r"C:\dev\lca-simu-pr40-validation-artifacts-20260726")
DEFAULT_OUTPUT_DIR = ARTIFACT_ROOT / "supplier_preliminary_complete_single_20260904_v1"
OUTPUT_NAME = "BILAN_PRELIMINAIRE_COMPLET.html"
SCREEN_DIR = ARTIFACT_ROOT / "supplier_network_risk_screen_20260902_v2"
PRELIM_DIR = ARTIFACT_ROOT / "supplier_network_preliminary_15_of_30_20260904_v1"
MAP_RELATIVE = (
    "../industrial_supply_preliminary_delivery_15_of_30_20260904_v2_sans_qualite/"
    "assets/network_map_autonomous.html"
)
LOT_CSV_RELATIVE = (
    "../supplier_network_preliminary_15_of_30_20260904_v1/"
    "preliminary_lot_genealogical_exposure_detail.csv"
)
FORBIDDEN_OUTPUT_TERMS = (
    "quality_hold",
    "quality_yield",
    "retenue qualité",
    "retenue qualite",
    "quarantaine",
)
FORBIDDEN_SCIENTIFIC_CLAIMS = (
    "doivent être instruits en premier",
    "classement des 16 fournisseurs",
    "les deux premiers signaux sont robustes",
    "ic95 de la moyenne",
    "il est validé techniquement",
    "dominent souvent la réponse",
    "traçabilité des effets",
)


class SingleHtmlBuildError(RuntimeError):
    """Raised when evidence or the standalone output contract is invalid."""


def _read_csv(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        raise SingleHtmlBuildError(f"Source absente: {path}")
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _number(value: str | float | int) -> float:
    return float(value)


def _fr(value: float, digits: int = 2) -> str:
    return (
        f"{value:,.{digits}f}".replace(",", "X")
        .replace(".", ",")
        .replace("X", "\u202f")
    )


def _item(value: str) -> str:
    return value.removeprefix("item:")


def load_payload() -> dict[str, Any]:
    rankings = _read_csv(SCREEN_DIR / "confirmation_supplier_sensitivity_ranking.csv")
    if len(rankings) != 16:
        raise SingleHtmlBuildError(f"16 fournisseurs attendus, trouvé {len(rankings)}")

    confirmation = _read_csv(SCREEN_DIR / "confirmation_summary.csv")
    top_ids = {
        "338929": "sdc_vd0914360c_338929_m_1810__transport_delay__120",
        "344135": "sdc_vd0993480a_344135_m_1430__transport_delay__120",
    }
    top_details: dict[str, dict[str, str]] = {}
    for item_id, scenario_id in top_ids.items():
        matches = [row for row in confirmation if row["scenario_id"] == scenario_id]
        if len(matches) != 1:
            raise SingleHtmlBuildError(f"Résultat confirmé introuvable: {scenario_id}")
        top_details[item_id] = matches[0]

    effects = _read_csv(PRELIM_DIR / "preliminary_effects_15.csv")
    time_rows = [
        row
        for row in effects
        if row["extension"] == "temporal_robustness"
        and row["failure_mode"] == "transport_delay"
        and ("338929" in row["case_id"] or "344135" in row["case_id"])
    ]
    common_rows = [
        row
        for row in effects
        if row["extension"] == "multi_lane_supplier_common_cause"
        and row["failure_mode"] == "transport_delay"
    ]
    illustrations = _read_csv(PRELIM_DIR / "preliminary_lot_illustrations.csv")
    lots_raw = _read_csv(
        PRELIM_DIR / "preliminary_lot_genealogical_exposure_detail.csv"
    )
    if len(lots_raw) != 2231:
        raise SingleHtmlBuildError(
            f"2 231 enregistrements lots attendus, trouvé {len(lots_raw)}"
        )
    lot_fields = (
        "case_key",
        "seed",
        "source_id",
        "supplier_ids",
        "chain_ids",
        "lot_id",
        "exposure_role",
        "genealogy_depth",
        "node_id",
        "item_id",
        "event_type",
        "day",
        "qty",
        "uom",
        "shipment_id",
        "production_campaign_id",
        "causal_delay_or_loss_claimed",
        "counterfactual_entity_identity_validated",
        "industrial_lot_number_claimed",
    )
    lots = [{field: row.get(field, "") for field in lot_fields} for row in lots_raw]
    for illustration in illustrations:
        root_by_uom: dict[str, float] = {}
        for row in lots_raw:
            if (
                row["case_key"] == illustration["case_key"]
                and row["exposure_role"] == "risk_tagged_usable_receipt_root"
            ):
                root_by_uom[row["uom"]] = root_by_uom.get(row["uom"], 0.0) + _number(
                    row["qty"]
                )
        illustration["root_quantity_by_uom"] = json.dumps(root_by_uom)
    return {
        "rankings": rankings,
        "top": top_details,
        "time": time_rows,
        "common": common_rows,
        "illustrations": illustrations,
        "lots": lots,
    }


def _ranking_rows(rows: list[dict[str, str]]) -> str:
    result: list[str] = []
    for row in rows:
        drop = -100 * _number(row["worst_service_delta"])
        width = max(1.2, drop / 34 * 100) if drop else 0
        item_id = _item(row["worst_item_id"])
        status = (
            "Effet descriptif fort"
            if row["supplier_sensitivity_rank"] in {"1", "2"}
            else (
                "Effet descriptif variable"
                if drop > 0
                else "Effet non mesuré à réexaminer"
            )
        )
        result.append(
            "<tr>"
            f"<td class='rank'>{html.escape(row['supplier_sensitivity_rank'])}</td>"
            f"<td><strong>{html.escape(row['supplier_id'])}</strong></td>"
            f"<td>{html.escape(item_id)}</td><td>{html.escape(row['worst_dst_node_id'])}</td>"
            f"<td><div class='barcell'><i style='width:{width:.2f}%'></i>"
            f"<span>{_fr(drop)} points</span></div></td><td>{status}</td></tr>"
        )
    return "".join(result)


def _window_svg(rows: list[dict[str, str]]) -> str:
    ordered = sorted(
        rows, key=lambda row: ("344135" in row["case_id"], int(row["stress_start_day"]))
    )
    labels = [
        "338929 J0–179",
        "J180–359",
        "J360–539",
        "J540–719",
        "344135 J0–179",
        "J180–359",
        "J360–539",
        "J540–719",
    ]
    values = [-_number(row["mean_service_delta_percentage_points"]) for row in ordered]
    bars: list[str] = []
    for idx, (label, value) in enumerate(zip(labels, values, strict=True)):
        y = 22 + idx * 34
        color = "#1467c7" if idx < 4 else "#ea6a2a"
        bars.append(
            f"<text x='0' y='{y + 13}' class='svgtxt'>{label}</text>"
            f"<rect x='116' y='{y}' width='{value * 8.1:.1f}' height='19' rx='5' fill='{color}'/>"
            f"<text x='{122 + value * 8.1:.1f}' y='{y + 14}' class='svgval'>{_fr(value)} pts</text>"
        )
    return (
        "<svg viewBox='0 0 570 310' role='img' aria-label='Baisse moyenne de service selon la fenêtre'>"
        + "".join(bars)
        + "<line x1='116' y1='8' x2='116' y2='300' stroke='#b8c8dc'/></svg>"
    )


def _lot_cards(rows: list[dict[str, str]]) -> str:
    cards: list[str] = []
    for row in rows:
        quantity = json.loads(row["root_quantity_by_uom"])
        root_qty = ", ".join(f"{_fr(_number(v), 0)} {k}" for k, v in quantity.items())
        cards.append(
            "<article class='mini'>"
            f"<span class='tag'>composant {_item(row['item_id'])}</span>"
            f"<h3>{html.escape(row['supplier_id'])} → {html.escape(row['target_product_id'])}</h3>"
            f"<p><b>{row['root_lot_count']}</b> réception(s) racine · "
            f"<b>{row['exposed_descendant_lot_count']}</b> enregistrements descendants</p>"
            f"<p class='muted'>Quantité des réceptions racines uniquement : {html.escape(root_qty)}. "
            "Aucune quantité aval n’est ajoutée à ce volume.</p></article>"
        )
    return "".join(cards)


def _common_table(rows: list[dict[str, str]]) -> str:
    body: list[str] = []
    for row in rows:
        supplier = "SDC-VD0519670A" if "0519670" in row["case_id"] else "SDC-VD0520132A"
        body.append(
            f"<tr><td>{supplier}</td><td>{row['product_id']}</td>"
            f"<td>{_fr(_number(row['mean_service_delta_percentage_points']))} points</td>"
            f"<td>{_fr(_number(row['min_service_delta_percentage_points']))} à "
            f"{_fr(_number(row['max_service_delta_percentage_points']))}</td></tr>"
        )
    return "".join(body)


def render_html(payload: dict[str, Any]) -> str:
    rank_rows = _ranking_rows(payload["rankings"])
    windows = _window_svg(payload["time"])
    lot_cards = _lot_cards(payload["illustrations"])
    common = _common_table(payload["common"])
    lots_json = json.dumps(
        payload["lots"], ensure_ascii=False, separators=(",", ":")
    ).replace("</", "<\\/")
    top338 = payload["top"]["338929"]
    top344 = payload["top"]["344135"]

    def stat(row: dict[str, str], key: str, scale: float = 100) -> str:
        return _fr(_number(row[key]) * scale)

    def stat_abs(row: dict[str, str], key: str, scale: float = 100) -> str:
        return _fr(abs(_number(row[key]) * scale))

    return f"""<!doctype html>
<html lang="fr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Bilan préliminaire consolidé — périmètre fournisseur retenu</title>
<style>
:root{{--ink:#10233f;--muted:#596c86;--line:#d9e4f1;--bg:#f3f7fb;--blue:#1467c7;--orange:#ea6a2a;--green:#17845b;--red:#bd3b32;--amber:#a86709}}
*{{box-sizing:border-box}} html{{scroll-behavior:smooth}} body{{margin:0;color:var(--ink);background:var(--bg);font:15px/1.52 Inter,system-ui,-apple-system,Segoe UI,sans-serif}}
nav{{position:sticky;top:0;z-index:20;background:#ffffffed;border-bottom:1px solid var(--line);backdrop-filter:blur(10px);padding:10px 4vw;display:flex;gap:8px;overflow:auto}}
nav a{{white-space:nowrap;text-decoration:none;color:var(--ink);border:1px solid var(--line);background:white;border-radius:99px;padding:7px 12px;font-weight:700}}
main{{max-width:1320px;margin:auto;padding:26px 24px 70px}} header{{padding:26px 0 10px}} h1{{font-size:clamp(29px,4vw,48px);line-height:1.08;margin:7px 0 12px;max-width:1020px}} h2{{font-size:25px;margin:0 0 9px}} h3{{font-size:17px;margin:6px 0}} p{{margin:7px 0}} .lead{{font-size:18px;max-width:1000px}} .eyebrow,.tag{{font-size:12px;text-transform:uppercase;letter-spacing:.08em;font-weight:850;color:#0750a5}}
.hero{{background:linear-gradient(135deg,#0c315f,#075fb5);color:white;border-radius:24px;padding:28px;box-shadow:0 16px 45px #17385b22}} .hero .eyebrow{{color:#aedaFF}}
.cards{{display:grid;grid-template-columns:repeat(auto-fit,minmax(175px,1fr));gap:12px;margin:18px 0}} .card,.mini{{border:1px solid var(--line);background:white;border-radius:16px;padding:16px}} .hero .card{{background:#ffffff12;border-color:#ffffff35}} .big{{font-size:30px;line-height:1;font-weight:900;margin-bottom:8px}} .muted{{color:var(--muted)}} .hero .muted{{color:#d5e7fa}}
section{{background:white;border:1px solid var(--line);border-radius:20px;padding:24px;margin:18px 0;box-shadow:0 8px 28px #17385b10}} .callout{{padding:15px 17px;border-left:5px solid var(--blue);background:#edf5ff;border-radius:8px;margin:14px 0}} .warn{{border-color:var(--amber);background:#fff7e8}} .good{{border-color:var(--green);background:#edfbf5}}
.grid2{{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:16px}} .tablewrap{{overflow:auto;max-height:660px;border:1px solid var(--line);border-radius:12px}} table{{border-collapse:collapse;width:100%;font-size:13px}} th,td{{padding:9px 10px;border-bottom:1px solid #e6edf6;text-align:left;white-space:nowrap}} th{{position:sticky;top:0;background:#edf4fb;z-index:1}} .rank{{font-size:18px;font-weight:900}} .barcell{{min-width:290px;position:relative;height:24px;background:#f0f4f9;border-radius:6px;overflow:hidden}} .barcell i{{position:absolute;inset:0 auto 0 0;background:linear-gradient(90deg,#e97332,#c43f37)}} .barcell span{{position:absolute;inset:2px 7px;text-align:right;font-weight:800}} svg{{width:100%;height:auto}} .svgtxt{{font:12px system-ui;fill:#405570}} .svgval{{font:bold 11px system-ui;fill:#10233f}}
.meter{{height:30px;background:linear-gradient(90deg,#c5443a,#f0a238 50%,#2b9667);border-radius:99px;position:relative;margin:42px 10px 60px}} .mark{{position:absolute;top:-9px;width:3px;height:48px;background:#10233f}} .mark span{{position:absolute;top:48px;transform:translateX(-46%);white-space:nowrap;font-weight:800;font-size:12px}} .m80{{left:80%}} .m93{{left:93%}} .m929{{left:92.87%;background:#1467c7}} .m954{{left:95.4%;background:#7b3ec7}}
.status{{display:inline-block;padding:4px 9px;border-radius:99px;font-weight:800;font-size:12px}} .done{{background:#dff7eb;color:#11633f}} .ready{{background:#e8f2ff;color:#0750a5}} .todo{{background:#fff1d9;color:#85520a}}
.buttons{{display:flex;gap:10px;flex-wrap:wrap;margin:14px 0}} .button{{display:inline-block;text-decoration:none;background:var(--blue);color:white;padding:10px 15px;border-radius:10px;font-weight:850}} .button.secondary{{background:white;color:var(--blue);border:1px solid var(--blue)}}
#lot-search{{width:100%;padding:12px;border:1px solid #aebed2;border-radius:10px;font:inherit;margin:9px 0}} .foot{{font-size:12px;color:var(--muted)}} details{{border:1px solid var(--line);border-radius:12px;padding:11px 14px;margin:10px 0}} summary{{cursor:pointer;font-weight:850}}
@media(max-width:820px){{.grid2{{grid-template-columns:1fr}} main{{padding:18px 12px 50px}} section{{padding:17px}} .barcell{{min-width:220px}}}}
@media print{{nav{{display:none}} body{{background:white}} section,.hero{{break-inside:avoid;box-shadow:none}}}}
</style></head><body>
<nav><a href="#synthese">Synthèse</a><a href="#classement">16 fournisseurs</a><a href="#robustesse">Dispersion</a><a href="#lots">Lots</a><a href="#stocks">Stocks</a><a href="#service">Service 80/93</a><a href="#actions">Actions</a><a href="#modele">Modèle</a><a href="#preuves">Preuves</a></nav>
<main><header id="synthese" class="hero"><div class="eyebrow">Bilan préliminaire consolidé · 4 septembre 2026</div>
<h1>Deux voies montrent les plus fortes baisses dans ce test. Aucun classement général des fournisseurs n’est encore validé.</h1>
<p class="lead">Cette page rassemble le tri descriptif sous deux perturbations imposées, la dispersion, les périodes sensibles, les lots techniquement exposés, les données industrielles 2025, les actions déjà testées et l’état réel du modèle. Elle ne relance aucun calcul et n’efface aucun résultat antérieur.</p>
<div class="cards"><div class="card"><div class="big">1 255</div>résultats réseau exécutés ou réextraits</div><div class="card"><div class="big">30</div>réalisations comparées dans les mêmes conditions aléatoires</div><div class="card"><div class="big">16</div>fournisseurs sur 18 voies actives</div><div class="card"><div class="big">15 / 30</div>résultats des extensions disponibles</div><div class="card"><div class="big">2 231</div>enregistrements techniques de généalogie</div></div>
<p class="muted"><b>Lecture métier :</b> sous l’hypothèse précise d’un retard de 120 jours, les voies 344135 et 338929 produisent les deux plus fortes baisses moyennes. Cela ne suffit pas à les déclarer fournisseurs les plus critiques : les familles d’incident divergent et l’audit ne sépare pas un ordre de priorité global.</p></header>

<section id="classement"><div class="eyebrow">Vue réseau — périmètre retenu</div><h2>Tri descriptif des 16 fournisseurs sous deux perturbations imposées</h2>
<p>Chaque voie a reçu les deux mêmes familles d’incident sévère dans sa période de flux la plus chargée. La barre montre la pire baisse moyenne de service à la date demandée. L’ordre est une lecture descriptive de cette métrique, pas une hiérarchie scientifique de criticité. Un zéro signifie seulement « effet non mesuré dans cette configuration ».</p>
<div class="tablewrap"><table><thead><tr><th>Ordre descriptif</th><th>Fournisseur</th><th>Composant</th><th>Site</th><th>Pire baisse moyenne</th><th>Lecture</th></tr></thead><tbody>{rank_rows}</tbody></table></div>
<div class="callout warn"><b>Décision :</b> aucun « top 3 industriel » n’est validé. Dans l’enveloppe de service, 016332, 029313, 338929 et 344135 forment un groupe non séparé au niveau scientifique exigé. Ces résultats servent à préparer les questions à poser, pas à noter les fournisseurs.</div></section>

<section id="robustesse"><div class="eyebrow">Moyenne, dispersion et période</div><h2>338929 varie peu entre les 30 tirages ; 344135 varie davantage</h2>
<div class="grid2"><article class="mini"><span class="tag">338929 · SDC-VD0914360C → M-1810 → 268091</span><div class="big">−{stat_abs(top338, "target_on_due_date_proxy_delta_vs_paired_baseline_mean")} points</div><p>moyenne sur 30 réalisations ; écart-type {stat(top338, "target_on_due_date_proxy_delta_vs_paired_baseline_sample_std")} point.</p><p><b>Intervalle bootstrap descriptif 2,5–97,5 % :</b> {stat(top338, "target_on_due_date_proxy_delta_vs_paired_baseline_bootstrap95_low")} à {stat(top338, "target_on_due_date_proxy_delta_vs_paired_baseline_bootstrap95_high")} points.</p><p><b>Cas individuels :</b> {stat(top338, "target_on_due_date_proxy_delta_vs_paired_baseline_min")} à {stat(top338, "target_on_due_date_proxy_delta_vs_paired_baseline_max")} points.</p><p class="muted">La dispersion est faible dans ces 30 tirages du modèle ; ce n’est pas une preuve de criticité historique.</p></article>
<article class="mini"><span class="tag">344135 · SDC-VD0993480A → M-1430 → 268967</span><div class="big">−{stat_abs(top344, "target_on_due_date_proxy_delta_vs_paired_baseline_mean")} points</div><p>moyenne sur 30 réalisations ; écart-type {stat(top344, "target_on_due_date_proxy_delta_vs_paired_baseline_sample_std")} points.</p><p><b>Intervalle bootstrap descriptif 2,5–97,5 % :</b> {stat(top344, "target_on_due_date_proxy_delta_vs_paired_baseline_bootstrap95_low")} à {stat(top344, "target_on_due_date_proxy_delta_vs_paired_baseline_bootstrap95_high")} points.</p><p><b>Cas individuels :</b> {stat(top344, "target_on_due_date_proxy_delta_vs_paired_baseline_min")} à {stat(top344, "target_on_due_date_proxy_delta_vs_paired_baseline_max")} points.</p><p class="muted">La baisse moyenne est plus forte, mais dépend davantage de l’état simulé de la chaîne au moment de l’incident.</p></article></div>
<p class="muted">Ces intervalles rééchantillonnent les mêmes 30 tirages utilisés pour sélectionner et décrire les cas. Ils ne sont ni des intervalles de confiance sur une population industrielle, ni corrigés pour la sélection ou les comparaisons multiples.</p>
<h3>Le moment de l’incident change fortement le résultat — extension préliminaire 15/30</h3>{windows}
<p class="muted">Baisse moyenne du service à la date demandée pour un retard de 120 jours appliqué successivement sur quatre fenêtres de 180 jours. Les moyennes de 338929 sont défavorables sur les quatre fenêtres. Celles de 344135 le sont aussi, mais certains tirages atteignent zéro dans les fenêtres 2 et 4.</p>
<h3>Incident commun à un fournisseur multi-voies</h3><div class="tablewrap"><table><thead><tr><th>Fournisseur</th><th>Produit</th><th>Baisse moyenne</th><th>Étendue sur 15 réalisations</th></tr></thead><tbody>{common}</tbody></table></div>
<p class="muted">Pour SDC-VD0519670A, perturber simultanément 001848 et 029313 donne le même impact agrégé que 029313 seul dans ce cas construit et cette fenêtre : aucune amplification supplémentaire n’y est démontrée. L’autre fournisseur multi-voies n’a pas d’effet mesuré dans cette configuration.</p></section>

<section id="lots"><div class="eyebrow">Généalogie technique d’exposition</div><h2>Du composant au produit et au client agrégé : ce que le moteur sait relier</h2>
<div class="cards">{lot_cards}</div>
<div class="callout"><b>Important :</b> les 2 231 lignes ci-dessous sont des enregistrements successifs de généalogie sur quatre illustrations d’une seule réalisation. Ce ne sont ni 2 231 lots physiques indépendants, ni la preuve que chaque lot a été retardé. Les indicateurs sources confirment que le retard causal, l’identité entre référence et incident et le numéro de lot industriel ne sont pas validés.</div>
<div class="callout warn"><b>Deux limites techniques à corriger :</b> certains identifiants de lots sont réutilisés d’un scénario à l’autre ; la colonne « cas technique » est donc indispensable. Par ailleurs, 1 331 identifiants d’arête source contiennent DC-1910 : 664 lignes aboutissent à DC-1920 et 667 à des nœuds clients. Cette incohérence doit être arbitrée. La généalogie sert ici à repérer une exposition possible, pas à engager une traçabilité industrielle.</div>
<label for="lot-search"><b>Rechercher dans les lots techniques</b> — cas, fournisseur, composant, identifiant, site, expédition ou campagne</label><input id="lot-search" placeholder="Ex. 338929, LOT-00004869, M-1810, SHIP…"><p id="lot-count" class="muted"></p>
<div class="tablewrap"><table><thead><tr><th>Cas technique</th><th>Tirage</th><th>Source</th><th>Fournisseur</th><th>Identifiant technique</th><th>Rôle</th><th>Niveau</th><th>Site</th><th>Article</th><th>Jour</th><th>Quantité</th><th>Expédition / campagne</th></tr></thead><tbody id="lot-body"></tbody></table></div>
<div class="buttons"><a class="button secondary" href="{LOT_CSV_RELATIVE}">Ouvrir le détail CSV complet</a></div>
<p class="foot">Pour passer à une traçabilité industrielle causale, il faut les clés réelles : ligne de commande, réception, lot composant, ordre/campagne, lot fini, allocation et commande client.</p></section>

<section id="stocks"><div class="eyebrow">Pourquoi certains fournisseurs semblent sans effet</div><h2>21 couples matière–site sur 24 présentent un écart majeur de calibration</h2>
<div class="cards"><div class="card"><div class="big">21 / 24</div>écarts majeurs entre besoin de référence et consommation physique simulée</div><div class="card"><div class="big">×35,47</div>rapport besoin de référence / consommation physique, cas typiques M-1430</div><div class="card"><div class="big">×19,84</div>rapport besoin de référence / consommation physique, cas typiques M-1810</div><div class="card"><div class="big">2</div>composants proches de l’ordre de grandeur : 338929 et 344135</div></div>
<p>L’audit détecte un écart d’ordre de grandeur entre le besoin de référence et la consommation physique simulée sur 21 couples. Cela peut contribuer à des couvertures de plusieurs centaines de jours, mais la causalité sur les effets et le tri descriptif n’a pas été vérifiée par une nouvelle simulation corrigée.</p>
<div class="callout warn"><b>Conséquence métier :</b> il faut valider ensemble stocks et pipeline initiaux, période de mise en régime, besoins, capacités, nomenclatures et tailles de lots, puis rejouer les tests. Les effets nuls ne prouvent pas une faible criticité fournisseur.</div></section>

<section id="service"><div class="eyebrow">Niveaux de service à explorer</div><h2>Les repères 80 % et 93 % restent des objectifs de scénarios, pas des calibrations acquises</h2>
<div class="grid2"><article class="mini"><span class="tag">Objectifs simulés à construire</span><div class="big">80 % · 93 %</div><p>Proxy unitaire servi à la date demandée. La nouvelle campagne de calibration n’est pas exécutée.</p></article><article class="mini"><span class="tag">Ratios financiers observés, métrique différente</span><div class="big">92,87 % · 95,40 %</div><p>CA livré / (CA livré + CA non livré) pour 268091 et 268967. Ces nombres ne sont pas comparables aux objectifs simulés.</p></article></div>
<div class="grid2"><article class="mini"><h3>Ce qui a été exploré</h3><p>Disponibilité, capacité, fiabilité, retard ponctuel et retard intermittent, sur plusieurs intensités. Le délai, le stock initial et le moment de l’incident ressortent dans ces explorations ; aucune analyse globale ne permet encore de les déclarer dominants sur tout le réseau.</p></article><article class="mini"><h3>Ce qui reste à faire</h3><p>Après correction des besoins et stocks, rechercher plusieurs combinaisons réalistes qui amènent le service unitaire vers 93 % puis 80 %, et vérifier leur stabilité sur plusieurs réalisations. Aujourd’hui, aucune combinaison réseau n’est validée comme « la » bonne façon de reproduire ces niveaux.</p></article></div>
<h3>Résultats chiffrés déjà obtenus — ancienne exploration, non calibrée</h3>
<div class="tablewrap"><table><thead><tr><th>Composant</th><th>Dégradation simulée</th><th>Proxy unitaire servi à la date demandée</th><th>Réalisations</th><th>Lecture</th></tr></thead><tbody>
<tr><td>338929</td><td>Retard intermittent moyen 90 j</td><td>92,7 %</td><td>10</td><td>proche du repère 93 %</td></tr>
<tr><td>338929</td><td>Retard intermittent moyen 120 j</td><td>73,2 %</td><td>10</td><td>sous le repère 80 %</td></tr>
<tr><td>338929</td><td>Délai ajouté 90 j</td><td>95,4 %</td><td>10</td><td>effet modéré dans cet ancien état</td></tr>
<tr><td>338929</td><td>Délai ajouté 120 j</td><td>75,4 %</td><td>10</td><td>sous le repère 80 %</td></tr>
<tr><td>338929</td><td>Fiabilité réglée à 0,2</td><td>81,7 %</td><td>10</td><td>proche de la zone 80 %</td></tr>
<tr><td>338929</td><td>Fiabilité réglée à 0,3</td><td>99,7 %</td><td>10</td><td>réponse non linéaire à instruire</td></tr>
<tr><td>344135</td><td>Retard intermittent moyen 90 j</td><td>95,8 %</td><td>10</td><td>effet encore limité</td></tr>
<tr><td>344135</td><td>Retard intermittent moyen 120 j</td><td>81,8 %</td><td>10</td><td>proche de la zone 80 %</td></tr>
<tr><td>344135</td><td>Délai ajouté 60 j</td><td>95,1 %</td><td>1</td><td>illustration seule, trop peu pour conclure</td></tr>
<tr><td>344135</td><td>Délai ajouté 120 j</td><td>83,9 %</td><td>10</td><td>dégradation nette</td></tr>
</tbody></table></div>
<p class="muted"><b>Limite :</b> ces valeurs viennent de l’ancien paysage de sensibilité et ne constituent pas encore la calibration réseau finale. Elles montrent toutefois que plusieurs chemins de dégradation peuvent approcher 93 % ou 80 %. Pour 021081, aucun flux fournisseur actif ne traversait la période testée : ses anciens résultats ne sont pas interprétables et ne figurent donc pas dans le tableau.</p>
<h3>Données industrielles 2025 déjà récupérées</h3><div class="tablewrap"><table><thead><tr><th>Produit</th><th>CA livré</th><th>CA perdu brut</th><th>Part financière livrée</th><th>Relevés hebdomadaires de stock PF</th><th>Valeur moyenne stock PF</th></tr></thead><tbody><tr><td>268091</td><td>20 994 246</td><td>1 611 174</td><td>92,87 %</td><td>52</td><td>402 762</td></tr><tr><td>268967</td><td>22 436 269</td><td>1 082 210</td><td>95,40 %</td><td>52</td><td>1 534 650</td></tr></tbody></table></div>
<p class="muted">La devise n’est pas déclarée dans les fichiers. Les stocks observés sont des valeurs comptables agrégées, sans quantité, lot ni fournisseur ; aucune perte de CA réelle ne peut donc encore être attribuée à un fournisseur.</p></section>

<section id="actions"><div class="eyebrow">Leviers pilotables</div><h2>Une seule action possède aujourd’hui un résultat chiffré exploitable — et seulement dans un cas bien précis</h2>
<div class="grid2"><article class="mini"><span class="status done">Ancien test séparé · 10 réalisations</span><h3>Transport accéléré ciblé sur 338929</h3><div class="big">16 jours</div><p>de retour à zéro avancé en moyenne dans les 2 réalisations où l’incident atteignait le client. Dans ces deux cas, le retard client additionnel restant est de 0 UN·jour, soit 0 % du retard cumulé sans action. Le surcoût de 33 532 unités est, lui, moyenné sur les 10 réalisations.</p><p class="muted">Contexte non transférable tel quel : ajout de 35 jours sur les expéditions libérées entre J0 et J89, avec une ancienne configuration simplifiée. Le moteur n’accélère que les nouvelles expéditions libérées, jamais le matériel déjà en transit. 2/10 n’est pas une probabilité industrielle.</p></article>
<article class="mini"><span class="status todo">À tester après recalibration</span><h3>Vrais leviers opérationnels suivants</h3><p>Allocation du stock libre aux commandes prioritaires ; réduction négociée du retard sur une expédition confirmée ; replanification avec capacités et campagnes finies ; stock préventif dimensionné avant la période à risque ; source alternative déjà homologuée avec capacité et délai documentés.</p><p class="muted">Les anciens proxys d’achat exceptionnel, de second fournisseur ou de replanification ne constituent pas encore des preuves opérationnelles.</p></article></div></section>

<section id="modele"><div class="eyebrow">Dynamique, boucle fermée et fréquences</div><h2>Les briques existent, mais elles n’ont pas toutes le même niveau de maturité</h2>
<div class="cards"><article class="mini"><span class="status ready">État des simulations réseau</span><h3>Dynamique partielle, incidents exogènes</h3><p>Les stocks, transits, retards et décisions MRP évoluent avec l’état du système. En revanche, la couche de risque fournisseur dépendante de l’état est désactivée dans ces calculs et les incidents sont imposés de l’extérieur. Seuls 3 couples matière–site sur 24 utilisent déjà un besoin dynamique.</p></article><article class="mini"><span class="status ready">Préparé, non exécuté</span><h3>Référence dynamique 24/24</h3><p>Un protocole additif propose de basculer les 24 matières vers un besoin lié à la demande. Aucun résultat comparatif n’existe encore et la variante modifie aussi des capacités et politiques amont : elle n’isole donc pas le seul calcul du besoin.</p></article><article class="mini"><span class="status ready">Diagnostic existant</span><h3>Boucle fermée</h3><p>Le MRP réagit déjà au stock, au transit et au retard. Le superviseur testé a une mémoire interne exacte z = 0,82, mais le modèle physique identifié a été rejeté : aucun pôle de la supply réelle n’est encore établi.</p></article><article class="mini"><span class="status ready">Diagnostic existant</span><h3>Analyse fréquentielle</h3><p>1 104 réponses ont été examinées ; 22 seulement sont numériquement exploitables, toutes sur le délai fournisseur. Parmi elles, 7 restent dans le même régime et 15 changent de régime. Cela ne valide aucun délai, pôle, diagramme de Bode ni marge de stabilité physique du réseau.</p></article></div>
<div class="callout"><b>Fil rouge scientifique :</b> valider puis recalibrer besoin, stock, pipeline initial et capacités → vérifier la nouvelle référence dynamique → rejouer l’analyse réseau et les cascades → tester les actions → seulement ensuite réidentifier les pôles, la commandabilité et les réponses fréquentielles autour d’un état stable.</div></section>

<section id="preuves"><div class="eyebrow">Ce qui est acquis et ce qui manque</div><h2>Matrice de maturité pour le rendez-vous industriel</h2>
<div class="tablewrap"><table><thead><tr><th>Sujet</th><th>État</th><th>Ce que l’on peut dire</th><th>Prochaine preuve nécessaire</th></tr></thead><tbody>
<tr><td>Données 2025</td><td><span class="status done">Fait</span></td><td>CA, pertes et valeurs de stock sont décrits factuellement.</td><td>Devise, quantités, lots, commandes et clés fournisseur.</td></tr>
<tr><td>Écran réseau 16 fournisseurs</td><td><span class="status done">Tri descriptif calculé</span></td><td>Deux fortes baisses conditionnelles visibles ; aucun ordre global de criticité validé.</td><td>Paramètres validés, plan indépendant et familles d’incident comparables.</td></tr>
<tr><td>Quatre périodes + causes communes</td><td><span class="status ready">15/30</span></td><td>Résultat préliminaire exploitable, pas final.</td><td>Terminer les 15 réalisations restantes et consolider.</td></tr>
<tr><td>Lots</td><td><span class="status ready">Partiel</span></td><td>Chemin technique composant → production → plateforme → client agrégé.</td><td>Identifiants réels et appariement causal référence/incident.</td></tr>
<tr><td>Calibration des stocks</td><td><span class="status done">Diagnostic heuristique</span></td><td>21/24 couples présentent un écart majeur à vérifier par nouvelle simulation.</td><td>Demande, nomenclatures, capacité, stock libre et lots validés.</td></tr>
<tr><td>Service 80/93</td><td><span class="status todo">À refaire</span></td><td>Repères de scénarios seulement.</td><td>Recherche multi-paramètres après recalibration.</td></tr>
<tr><td>Actions</td><td><span class="status ready">1 ancien indice borné</span></td><td>Le transport accéléré a aidé dans 2 cas exposés d’une ancienne configuration ; résultat non transférable.</td><td>Actions réalistes chiffrées sur le nouveau modèle.</td></tr>
<tr><td>Dynamique / commande / fréquences</td><td><span class="status ready">Partiel / préparé</span></td><td>Flux dynamiques, incidents fournisseurs exogènes, pas de modèle physique accepté.</td><td>Référence 24/24 exécutée et essais indépendants autour d’un état stable.</td></tr>
<tr><td>Prévision fournisseur</td><td><span class="status todo">Données manquantes</span></td><td>Signal de priorité, pas probabilité.</td><td>Historique PO-ligne : promis, re-promis, reçu, quantité, cause, action.</td></tr>
</tbody></table></div>
<details><summary>Transparence sur les 48 heures de travail</summary><p>1 765 résultats uniques ont été inventoriés dans les deux campagnes : 1 513 sont retenus dans le périmètre demandé et 252 ont été explicitement écartés. Le protocole réseau principal consolide 1 255 résultats exécutés ou réextraits ; l’extension en ajoute 510 au point d’arrêt. Les résultats 15/30 sont préliminaires. Le temps de calcul a donc surtout produit les données détaillées et leurs contrôles, mais il n’a pas achevé la calibration ni la validation scientifique.</p></details>
<details><summary>Vocabulaire utilisé</summary><p><b>Observé</b> : valeur présente dans les fichiers industriels 2025. <b>Simulé</b> : résultat du moteur sous des hypothèses données. <b>Signal de priorité</b> : dossier qui pourrait être instruit en premier après validation ; aucun signal de ce type n’est libéré par l’audit actuel. <b>Hypothèse</b> : incident, action ou paramètre qui doit être confirmé avec l’industriel.</p></details>
<div class="buttons"><a class="button" href="{MAP_RELATIVE}">Ouvrir la carte réseau locale existante</a><a class="button secondary" href="#synthese">Revenir à la synthèse</a></div>
<p class="foot">Cette page de bilan est autonome et ne dépend pas d’Internet. La carte, facultative et plus lourde, reste dans son paquet local existant afin de conserver un seul fichier de bilan. Aucune simulation n’a été relancée ; les sources antérieures sont inchangées.</p></section>
</main>
<script id="lot-data" type="application/json">{lots_json}</script>
<script>
const lots=JSON.parse(document.getElementById('lot-data').textContent);const body=document.getElementById('lot-body');const count=document.getElementById('lot-count');const search=document.getElementById('lot-search');
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}}[c]));
function role(r){{return r==='risk_tagged_usable_receipt_root'?'réception racine':'descendant généalogique'}}
function render(){{const q=search.value.trim().toLowerCase();const selected=q?lots.filter(r=>Object.values(r).join(' ').toLowerCase().includes(q)):lots;const shown=selected.slice(0,250);body.innerHTML=shown.map(r=>`<tr><td>${{esc(r.case_key)}}</td><td>${{esc(r.seed)}}</td><td>${{esc(r.source_id)}}</td><td>${{esc(r.supplier_ids)}}</td><td>${{esc(r.lot_id)}}</td><td>${{role(r.exposure_role)}}</td><td>${{esc(r.genealogy_depth||'racine')}}</td><td>${{esc(r.node_id)}}</td><td>${{esc(r.item_id.replace('item:',''))}}</td><td>${{esc(r.day)}}</td><td>${{esc(r.qty)}} ${{esc(r.uom)}}</td><td>${{esc(r.shipment_id||r.production_campaign_id||'—')}}</td></tr>`).join('');count.textContent=`${{selected.length.toLocaleString('fr-FR')}} enregistrement(s) trouvé(s) · ${{shown.length}} affiché(s) au maximum`;}}
search.addEventListener('input',render);render();
</script></body></html>"""


def validate_html(text: str) -> None:
    lower = text.casefold()
    for term in FORBIDDEN_OUTPUT_TERMS:
        if term.casefold() in lower:
            raise SingleHtmlBuildError(
                f"Terme hors périmètre détecté dans le HTML: {term}"
            )
    if "https://" in lower or "http://" in lower:
        raise SingleHtmlBuildError("Une dépendance Internet a été détectée")
    overclaims = [
        claim for claim in FORBIDDEN_SCIENTIFIC_CLAIMS if claim.casefold() in lower
    ]
    if overclaims:
        raise SingleHtmlBuildError(
            f"Surinterprétations scientifiques détectées: {overclaims}"
        )
    required = (
        "1 255",
        "30",
        "16",
        "18 voies",
        "2 231",
        "21 / 24",
        "80 %",
        "93 %",
        "1 513",
        "1 765",
        "252 ont été",
        "338929",
        "344135",
        "z = 0,82",
        "tri descriptif",
        "intervalle bootstrap descriptif",
        "incidents exogènes",
    )
    missing = [token for token in required if token.casefold() not in lower]
    if missing:
        raise SingleHtmlBuildError(f"Éléments obligatoires absents: {missing}")
    if text.count("<!doctype html>") != 1 or '<script id="lot-data"' not in text:
        raise SingleHtmlBuildError("Le contrat HTML unique/autonome n'est pas respecté")


def build(output_dir: Path = DEFAULT_OUTPUT_DIR) -> Path:
    payload = load_payload()
    document = render_html(payload)
    validate_html(document)
    output_dir.mkdir(parents=True, exist_ok=True)
    unexpected = [entry for entry in output_dir.iterdir() if entry.name != OUTPUT_NAME]
    if unexpected:
        raise SingleHtmlBuildError(
            f"Le dossier cible contient des fichiers étrangers: {[entry.name for entry in unexpected]}"
        )
    destination = output_dir / OUTPUT_NAME
    destination.write_text(document, encoding="utf-8")
    return destination


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--validate-only", action="store_true")
    args = parser.parse_args()
    if args.validate_only:
        target = args.output_dir / OUTPUT_NAME
        if not target.is_file():
            raise SingleHtmlBuildError(f"HTML absent: {target}")
        validate_html(target.read_text(encoding="utf-8"))
        print(f"VALID {target}")
        return 0
    target = build(args.output_dir)
    print(target)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
