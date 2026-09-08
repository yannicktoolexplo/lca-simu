#!/usr/bin/env python3
"""Build the additive three-view 15/30 supplier-transport delivery.

The builder reads the signed preliminary package but never copies its broad
annex.  It publishes only the four matched ``transport_delay`` supplier cases,
their technical lot genealogy, compact observed 2025 facts, and prepare-only
decision plans.  It does not invoke the simulation engine or mutate a source.
"""

from __future__ import annotations

import argparse
import csv
import html
import json
import math
import os
import re
import shutil
import sys
import tempfile
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

try:
    from . import build_industrial_supply_preliminary_delivery as base
except ImportError:  # pragma: no cover - direct CLI execution
    import build_industrial_supply_preliminary_delivery as base


ARTIFACT_ROOT = Path(r"C:\dev\lca-simu-pr40-validation-artifacts-20260726")
SCHEMA_VERSION = "etudecas.industrial_supply_preliminary_transport_delivery.v2"
MANIFEST_FILE = "preliminary_transport_delivery_manifest_v2.json"
LAUNCHER_FILE = "OUVRIR_PRELIMINAIRE_FOURNISSEURS_15_SUR_30.html"
VIEW_FILES = (
    "01_RISQUES_RESEAU_338929.html",
    "02_INCIDENTS_FOURNISSEURS_ET_LOTS.html",
    "03_DECISIONS_ET_DONNEES.html",
)
MAP_ASSET = "assets/network_map_autonomous.html"
SUMMARY_CSV = "assets/data/supplier_transport_incident_lot_summary.csv"
DETAIL_CSV = "assets/data/supplier_transport_lot_detail.csv"
BOUNDARY_CSV = "assets/data/service_priority_group_context.csv"

DEFAULT_PRELIMINARY_DIR = (
    ARTIFACT_ROOT / "supplier_network_preliminary_15_of_30_20260904_v1"
)
DEFAULT_OBSERVED_DIR = ARTIFACT_ROOT / "observed_2025_supply_bilan_20260901_v1"
DEFAULT_REGIME_PLAN_DIR = (
    ARTIFACT_ROOT / "supplier_service_regime_calibration_plan_20260903_v2"
)
DEFAULT_ACTION_PLAN_DIR = (
    ARTIFACT_ROOT / "supplier_network_exploratory_action_protocol_20260903_v5"
)
DEFAULT_MAP_SOURCE = (
    ARTIFACT_ROOT
    / "supplychain_worldmap_resilience_scan_closed_loop_v3_frequency_control_system_20260827_v14.html"
)
DEFAULT_PLOTLY_JS = (
    Path(r"C:\dev\lca-simu")
    / "etudecas"
    / "visualization"
    / "maps"
    / "vendor"
    / "plotly-2.32.0.min.js"
)
DEFAULT_OUTPUT_DIR = (
    ARTIFACT_ROOT
    / "industrial_supply_preliminary_delivery_15_of_30_20260904_v2_sans_qualite"
)

INCLUDED_EXTENSION = "priority_four_business_causes"
LOT_EXTENSION = "causal_lot_attribution_subset"
INCLUDED_FAILURE_MODE = "transport_delay"
EXPECTED_DETAIL_COUNT = 2231
EXPECTED_ROOT_RECEIPT_COUNT = 338
EXPECTED_DOWNSTREAM_RECORD_COUNT = 1893
EXPECTED_DISTINCT_LOT_ID_COUNT = 1875
EXPECTED_ITEMS = {
    "016332": {
        "root_count": 1,
        "root_qty": 1100.0,
        "root_uom": "KG",
        "production_count": 138,
        "platform_count": 155,
        "client_count": 183,
        "mean_service": -2.229681919368017,
        "min_service": -11.382783154584597,
        "max_service": 0.0,
        "mean_backlog": 0.23439808106529192,
    },
    "029313": {
        "root_count": 1,
        "root_qty": 300.0,
        "root_uom": "KG",
        "production_count": 249,
        "platform_count": 299,
        "client_count": 318,
        "mean_service": -5.008705756749271,
        "min_service": -28.37431878521247,
        "max_service": 0.0,
        "mean_backlog": 1.1745340158812676,
    },
    "338929": {
        "root_count": 329,
        "root_qty": 1_645_000.0,
        "root_uom": "UN",
        "production_count": 163,
        "platform_count": 163,
        "client_count": 125,
        "mean_service": -30.235333577235927,
        "min_service": -30.71669317490531,
        "max_service": -29.48289250703935,
        "mean_backlog": 11.287290402216511,
    },
    "344135": {
        "root_count": 7,
        "root_qty": 840_000.0,
        "root_uom": "UN",
        "production_count": 12,
        "platform_count": 47,
        "client_count": 41,
        "mean_service": -33.890066942199454,
        "min_service": -39.428623073612734,
        "max_service": -20.91835063753318,
        "mean_backlog": 13.254171572029655,
    },
}

USER_FORBIDDEN = re.compile(
    r"quality_hold|retenue\s+qualit|quarantaine",
    flags=re.IGNORECASE,
)
LAUNCHER_MANIFEST_FORBIDDEN = re.compile(
    r"quality|qualit|quarantaine",
    flags=re.IGNORECASE,
)
PLOTLY_CDN = "https://cdn.plot.ly/plotly-2.32.0.min.js"


class PreliminaryTransportDeliveryError(RuntimeError):
    """Raised when the transport-only delivery contract is not satisfied."""


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        return [dict(row) for row in csv.DictReader(stream)]


def _write_csv(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    if not rows:
        raise PreliminaryTransportDeliveryError(f"Table vide: {path.name}")
    fields = list(rows[0])
    if any(list(row) != fields for row in rows):
        raise PreliminaryTransportDeliveryError(f"Colonnes incohérentes: {path.name}")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _finite(value: Any, *, label: str) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError) as error:
        raise PreliminaryTransportDeliveryError(
            f"Valeur numérique invalide: {label}"
        ) from error
    if not math.isfinite(result):
        raise PreliminaryTransportDeliveryError(f"Valeur non finie: {label}")
    return result


def _bool(value: Any) -> bool:
    return value is True or str(value or "").strip().lower() == "true"


def _item(value: Any) -> str:
    return str(value or "").strip().removeprefix("item:")


def _close(actual: Any, expected: float) -> bool:
    return math.isclose(
        _finite(actual, label="contrôle attendu"),
        expected,
        rel_tol=1e-10,
        abs_tol=1e-10,
    )


def _validate_and_load_preliminary(
    root: Path,
) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, str]], list[dict[str, str]]]:
    try:
        base.preliminary_audit.validate_preliminary_package(root)
    except (FileNotFoundError, OSError, TypeError, ValueError, RuntimeError) as error:
        raise PreliminaryTransportDeliveryError(
            f"Paquet préliminaire signé invalide: {error}"
        ) from error
    manifest = base._read_json(root / base.preliminary_audit.MANIFEST_FILE)
    effects = _read_csv(root / base.preliminary_audit.EFFECTS_FILE)
    lots = _read_csv(root / base.preliminary_audit.LOT_SUMMARY_FILE)
    details = _read_csv(root / base.preliminary_audit.LOT_DETAIL_FILE)
    boundary = _read_csv(root / base.preliminary_audit.BOUNDARY_FILE)

    selected_effects = [
        row
        for row in effects
        if row.get("extension") == INCLUDED_EXTENSION
        and row.get("failure_mode") == INCLUDED_FAILURE_MODE
    ]
    selected_lots = [
        row
        for row in lots
        if row.get("case_key", "").startswith(f"{LOT_EXTENSION}::")
        and f"__{INCLUDED_FAILURE_MODE}::" in row.get("case_key", "")
    ]
    selected_details = [
        row
        for row in details
        if row.get("extension") == LOT_EXTENSION
        and row.get("failure_mode") == INCLUDED_FAILURE_MODE
    ]
    availability = [
        row
        for row in effects
        if row.get("extension") == INCLUDED_EXTENSION
        and row.get("failure_mode") == "supply_availability"
    ]
    if (
        len(selected_effects) != 4
        or len(selected_lots) != 4
        or len(selected_details) != EXPECTED_DETAIL_COUNT
        or len(boundary) != 4
        or len(availability) != 4
        or any(int(row.get("paired_seed_count") or 0) != 15 for row in selected_effects)
        or any(int(row.get("paired_seed_count") or 0) != 15 for row in availability)
        or any(
            not _close(row.get(field), 0.0)
            for row in availability
            for field in (
                "mean_service_delta_percentage_points",
                "min_service_delta_percentage_points",
                "max_service_delta_percentage_points",
            )
        )
    ):
        raise PreliminaryTransportDeliveryError(
            "Les quatre incidents transport ou le contrôle disponibilité sont incomplets."
        )
    return manifest, selected_effects, selected_lots, selected_details, boundary


def _build_incident_rows(
    effects: Sequence[Mapping[str, Any]],
    lots: Sequence[Mapping[str, Any]],
    details: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    effect_by_item: dict[str, Mapping[str, Any]] = {}
    for row in effects:
        match = re.search(r"_([0-9]{6})_[a-z0-9_]+__transport_delay$", str(row["case_id"]))
        if not match or match.group(1) in effect_by_item:
            raise PreliminaryTransportDeliveryError("Identité d’incident transport ambiguë.")
        effect_by_item[match.group(1)] = row
    lots_by_item = {_item(row.get("item_id")): row for row in lots}
    details_by_item: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in details:
        match = re.search(r"_([0-9]{6})_[a-z0-9_]+__transport_delay$", str(row["case_id"]))
        if not match:
            raise PreliminaryTransportDeliveryError("Détail lot sans incident transport.")
        details_by_item[match.group(1)].append(row)
    if set(effect_by_item) != set(EXPECTED_ITEMS) or set(lots_by_item) != set(EXPECTED_ITEMS):
        raise PreliminaryTransportDeliveryError("Les quatre articles attendus ne coïncident pas.")

    result: list[dict[str, Any]] = []
    for item_id in EXPECTED_ITEMS:
        expected = EXPECTED_ITEMS[item_id]
        effect = effect_by_item[item_id]
        lot = lots_by_item[item_id]
        item_details = details_by_item[item_id]
        root_rows = [
            row
            for row in item_details
            if row.get("exposure_role") == "risk_tagged_usable_receipt_root"
        ]
        descendant_rows = [
            row
            for row in item_details
            if row.get("exposure_role") == "genealogical_descendant"
        ]
        root_qty = sum(_finite(row.get("qty"), label="quantité racine") for row in root_rows)
        root_uoms = {str(row.get("uom") or "") for row in root_rows}
        production_count = sum(
            row.get("event_type") == "production_output" for row in descendant_rows
        )
        platform_count = sum(row.get("node_id") == "DC-1920" for row in descendant_rows)
        client_count = sum(row.get("node_id") == "C-XXXXX" for row in descendant_rows)
        if (
            len(root_uoms) != 1
            or len(root_rows) != expected["root_count"]
            or not _close(root_qty, expected["root_qty"])
            or next(iter(root_uoms)) != expected["root_uom"]
            or production_count != expected["production_count"]
            or platform_count != expected["platform_count"]
            or client_count != expected["client_count"]
            or production_count + platform_count + client_count != len(descendant_rows)
            or int(lot["genealogical_exposed_lot_count"]) != len(item_details)
            or not _close(effect["mean_service_delta_percentage_points"], expected["mean_service"])
            or not _close(effect["min_service_delta_percentage_points"], expected["min_service"])
            or not _close(effect["max_service_delta_percentage_points"], expected["max_service"])
            or not _close(effect["mean_backlog_delta_days_per_demand_unit"], expected["mean_backlog"])
            or any(
                not _bool(row.get("descendant_quantity_is_exposure_upper_bound"))
                or _bool(row.get("causal_delay_or_loss_claimed"))
                or _bool(row.get("counterfactual_entity_identity_validated"))
                or _bool(row.get("industrial_lot_number_claimed"))
                for row in item_details
            )
        ):
            raise PreliminaryTransportDeliveryError(
                f"Contrôle métier lots/effets non satisfait pour {item_id}."
            )
        result.append(
            {
                "supplier_id": lot["supplier_id"],
                "chain_id": lot["chain_id"],
                "item_id": item_id,
                "destination": (
                    "M-1430" if item_id == "344135" else "M-1810"
                ),
                "target_product_id": lot["target_product_id"],
                "incident_type": "retard_transport_120_jours",
                "incident_start_day": effect["stress_start_day"],
                "incident_end_day": effect["stress_end_day"],
                "effect_repetition_count": 15,
                "mean_service_change_percentage_points": _finite(
                    effect["mean_service_delta_percentage_points"], label="service moyen"
                ),
                "min_service_change_percentage_points": _finite(
                    effect["min_service_delta_percentage_points"], label="service min"
                ),
                "max_service_change_percentage_points": _finite(
                    effect["max_service_delta_percentage_points"], label="service max"
                ),
                "mean_backlog_days_equivalent_per_requested_unit": _finite(
                    effect["mean_backlog_delta_days_per_demand_unit"], label="backlog"
                ),
                "genealogy_illustration_repetition_count": 1,
                "root_receipt_record_count": len(root_rows),
                "root_quantity": root_qty,
                "root_uom": next(iter(root_uoms)),
                "production_descendant_count": production_count,
                "platform_descendant_count": platform_count,
                "generic_client_descendant_count": client_count,
                "genealogical_exposure_record_count": len(item_details),
                "genealogical_exposure_is_upper_bound": True,
                "causal_attribution_claimed": False,
                "historical_probability_estimated": False,
            }
        )
    if (
        sum(int(row["genealogical_exposure_record_count"]) for row in result)
        != EXPECTED_DETAIL_COUNT
        or sum(int(row["root_receipt_record_count"]) for row in result)
        != EXPECTED_ROOT_RECEIPT_COUNT
        or sum(
            int(row["production_descendant_count"])
            + int(row["platform_descendant_count"])
            + int(row["generic_client_descendant_count"])
            for row in result
        )
        != EXPECTED_DOWNSTREAM_RECORD_COUNT
        or len({(str(row["case_id"]), str(row["lot_id"])) for row in details})
        != EXPECTED_DETAIL_COUNT
        or len({str(row["lot_id"]) for row in details})
        != EXPECTED_DISTINCT_LOT_ID_COUNT
    ):
        raise PreliminaryTransportDeliveryError("Total des 2 231 enregistrements divergent.")
    return result


def _validate_map_source(map_source: Path, plotly_js: Path) -> tuple[str, str]:
    if not map_source.is_file() or not plotly_js.is_file():
        raise PreliminaryTransportDeliveryError("Source de carte ou bibliothèque locale absente.")
    try:
        document = map_source.read_text(encoding="utf-8")
        plotly = plotly_js.read_text(encoding="utf-8")
    except UnicodeError as error:
        raise PreliminaryTransportDeliveryError("Source cartographique non UTF-8.") from error
    script_pattern = re.compile(
        r'<script\s+src=["\']https://cdn\.plot\.ly/plotly-2\.32\.0\.min\.js["\']\s*></script>',
        flags=re.IGNORECASE,
    )
    if len(script_pattern.findall(document)) != 1 or "</script" in plotly.lower():
        raise PreliminaryTransportDeliveryError("Contrat Plotly de la carte inattendu.")
    if USER_FORBIDDEN.search(document) or USER_FORBIDDEN.search(plotly):
        raise PreliminaryTransportDeliveryError("La source cartographique contient un thème exclu.")
    return document, plotly


def _offline_map(document: str, plotly: str) -> str:
    # Remove the two visible selectors and legend entry for the excluded family;
    # internal generic variable names are left untouched to preserve map code.
    document = re.sub(
        r'<option\s+value=["\']quality["\']>\s*Qualite\s*</option>',
        "",
        document,
        flags=re.IGNORECASE,
    )
    document = re.sub(
        r'<span class=["\']sensitivityLegendItem["\']>\s*<span[^>]*></span>\s*Qualite\s*</span>',
        "",
        document,
        flags=re.IGNORECASE,
    )
    # Plotly's UTF-8 decoder intentionally contains the replacement character
    # in string literals.  The equivalent JavaScript escape preserves its
    # runtime semantics while satisfying the delivery's UTF-8 corruption scan.
    plotly = plotly.replace("\ufffd", r"\uFFFD")
    replaced, count = re.subn(
        r'<script\s+src=["\']https://cdn\.plot\.ly/plotly-2\.32\.0\.min\.js["\']\s*></script>',
        lambda _: f"<script>{plotly}</script>",
        document,
        count=1,
        flags=re.IGNORECASE,
    )
    if count != 1 or USER_FORBIDDEN.search(replaced):
        raise PreliminaryTransportDeliveryError("Conversion hors ligne de la carte invalide.")
    return replaced


def _fmt(value: Any, digits: int = 2) -> str:
    return f"{_finite(value, label='affichage'):.{digits}f}".replace(".", ",")


def _qty(value: Any) -> str:
    return f"{_finite(value, label='quantité'):,.0f}".replace(",", " ")


def _nav(current: int) -> str:
    labels = (
        "1. Risques réseau / 338929",
        "2. Incidents fournisseurs / lots",
        "3. Décisions / données",
    )
    links = "".join(
        f'<a class="{"active" if index == current else ""}" href="{name}">'
        f"{html.escape(label)}</a>"
        for index, (name, label) in enumerate(zip(VIEW_FILES, labels, strict=True), 1)
    )
    return f'<nav><a href="{LAUNCHER_FILE}">Accueil</a>{links}</nav>'


def _page(title: str, body: str, *, current: int, script: str = "") -> str:
    return f"""<!doctype html><html lang="fr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{html.escape(title)}</title><style>
body{{margin:0;background:#f1f5f9;color:#13233a;font:15px/1.5 system-ui,sans-serif}}nav{{display:flex;gap:8px;flex-wrap:wrap;padding:12px 18px;background:#10233f;position:sticky;top:0;z-index:3}}nav a{{color:white;text-decoration:none;padding:8px 12px;border-radius:18px}}nav a.active{{background:#2670ca}}main{{max-width:1500px;margin:auto;padding:18px}}section,.card{{background:white;border:1px solid #d7e1ed;border-radius:14px;padding:18px;margin:14px 0}}.warning{{background:#fff3cd;border:2px solid #d89000}}.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:12px}}a.card{{display:block;color:#13233a;text-decoration:none}}a.card:hover{{border-color:#2670ca}}table{{width:100%;border-collapse:collapse;font-size:13px}}th,td{{padding:8px;border-bottom:1px solid #dce4ed;text-align:left}}th{{background:#edf3f9;position:sticky;top:0}}.scroll{{overflow:auto;max-height:650px}}.metric{{font-size:1.45rem;font-weight:800}}.muted{{color:#596b80}}code{{font-size:11px}}input{{padding:8px;min-width:280px}}
</style></head><body>{_nav(current)}<main>{body}</main>{script}</body></html>"""


def _network_view(rows: Sequence[Mapping[str, Any]]) -> str:
    row = next(item for item in rows if item["item_id"] == "338929")
    cards = "".join(
        f"<article class='card'><h3>{item['item_id']} → {item['destination']}</h3>"
        f"<p class='metric'>{_fmt(item['mean_service_change_percentage_points'])} point(s)</p>"
        f"<p>Variation moyenne simulée du service sur 15 répétitions; plage "
        f"{_fmt(item['min_service_change_percentage_points'])} à "
        f"{_fmt(item['max_service_change_percentage_points'])}.</p></article>"
        for item in rows
    )
    body = f"""<section class="warning"><h1>338929 → M-1810 → 268091</h1><p><strong>SIMULÉ, PRÉLIMINAIRE 15/30 :</strong> un retard de transport de 120 jours fait baisser le service moyen de <strong>{_fmt(row['mean_service_change_percentage_points'])} points</strong> et ajoute <strong>{_fmt(row['mean_backlog_days_equivalent_per_requested_unit'])} jours-équivalent</strong> de commandes en retard par unité demandée dans cette configuration.</p><p><strong>SIGNAL DE PRIORITÉ :</strong> ce dossier mérite une instruction opérationnelle. Ce n’est ni la probabilité d’un incident, ni une note fournisseur, ni une conclusion finale.</p></section>
<section><h2>Quatre incidents transport comparables</h2><div class="grid">{cards}</div><p>Les articles 338929 et 344135 présentent les effets les plus forts et les plus réguliers dans ce groupe. Les effets de 016332 et 029313 sont plus intermittents : certaines répétitions ne montrent aucune variation.</p></section>
<section><h2>Carte du réseau</h2><a class="card" href="{MAP_ASSET}"><strong>Ouvrir la carte autonome</strong><br><span class="muted">Carte complète avec Plotly intégré; aucune connexion Internet requise.</span></a></section>"""
    return _page("Risques réseau fournisseurs", body, current=1)


def _incidents_view(
    rows: Sequence[Mapping[str, Any]],
    details: Sequence[Mapping[str, Any]],
) -> str:
    summary_body = "".join(
        "<tr>"
        f"<td>{html.escape(str(row['supplier_id']))}</td>"
        f"<td><strong>{row['item_id']}</strong> → {row['destination']} → {row['target_product_id']}</td>"
        f"<td>{_fmt(row['mean_service_change_percentage_points'])} pt<br><span class='muted'>[{_fmt(row['min_service_change_percentage_points'])}; {_fmt(row['max_service_change_percentage_points'])}]</span></td>"
        f"<td>+{_fmt(row['mean_backlog_days_equivalent_per_requested_unit'])}</td>"
        f"<td>{int(row['root_receipt_record_count'])} / {_qty(row['root_quantity'])} {row['root_uom']}</td>"
        f"<td>{int(row['production_descendant_count'])}</td>"
        f"<td>{int(row['platform_descendant_count'])}</td>"
        f"<td>{int(row['generic_client_descendant_count'])}</td>"
        "</tr>"
        for row in rows
    )
    detail_body = "".join(
        "<tr class='lot-row'>"
        f"<td>{html.escape(str(row['supplier_ids']))}</td>"
        f"<td><code>{html.escape(str(row['lot_id']))}</code></td>"
        f"<td>{html.escape(str(row['exposure_role']))}</td>"
        f"<td>{html.escape(str(row.get('genealogy_depth', '')))}</td>"
        f"<td>{html.escape(str(row.get('node_id', '')))}</td>"
        f"<td>{html.escape(_item(row.get('item_id')))}</td>"
        f"<td>{html.escape(str(row.get('day', '')))}</td>"
        f"<td>{_fmt(row['qty'])} {html.escape(str(row['uom']))}</td>"
        "</tr>"
        for row in details
    )
    body = f"""<section class="warning"><h1>Incidents fournisseurs et lots</h1><p><strong>Illustration technique :</strong> pour chaque voie, les effets de service proviennent de 15 répétitions appariées. Le suivi généalogique provient d’une seule répétition technique par voie.</p><p><strong>Exposition généalogique, borne haute :</strong> un lot descendant est relié à une réception exposée. Cela ne prouve ni un retard ou une perte causés par l’incident, ni l’identité d’un même lot entre deux simulations, ni une probabilité industrielle.</p></section>
<section><h2>Synthèse des quatre voies</h2><div class="scroll"><table><thead><tr><th>Fournisseur</th><th>Chaîne</th><th>Service moyen<br>et plage 15/30</th><th>Retard moyen<br>jours-équivalent</th><th>Réceptions racines / quantité</th><th>Production</th><th>Plateforme</th><th>Client</th></tr></thead><tbody>{summary_body}</tbody></table></div><p><strong>Lecture :</strong> 338929 et 344135 sont les deux cas les plus marquants de cette série conditionnelle. 016332 et 029313 restent à surveiller mais leur effet n’apparaît pas dans chaque répétition.</p></section>
<section><h2>{len(details):,} enregistrements techniques de filiation</h2><p>Le tableau contient <strong>338 réceptions racines</strong> et <strong>1 893 enregistrements aval</strong>. Il référence <strong>1 875 identifiants <code>lot_id</code> distincts</strong> au total; certains identifiants sont réutilisés entre scénarios indépendants. Le nombre d’enregistrements ne constitue donc pas un décompte de lots physiques.</p><p>Les identifiants <code>LOT-...</code> sont produits par le moteur et ne sont pas des numéros de lots industriels. Le détail utilise <strong>DC-1920</strong>, alors que le référentiel cartographique indique <strong>DC-1910</strong> : la correspondance doit être confirmée. <strong>C-XXXXX</strong> est un client générique, pas un client nommé.</p><p><label>Rechercher un fournisseur, identifiant, site ou article : <input id="lot-filter" type="search" oninput="filterLots()"></label> <a href="{DETAIL_CSV}">Ouvrir le CSV détaillé</a></p><div class="scroll"><table><thead><tr><th>Fournisseur</th><th>Identifiant technique lot_id</th><th>Rôle</th><th>Niveau</th><th>Site</th><th>Article</th><th>Jour</th><th>Quantité</th></tr></thead><tbody>{detail_body}</tbody></table></div></section>""".replace(
        f"{len(details):,}", f"{len(details):,}".replace(",", " ")
    )
    script = """<script>function filterLots(){const q=document.getElementById('lot-filter').value.toLocaleLowerCase('fr');document.querySelectorAll('.lot-row').forEach((row)=>{row.hidden=!row.textContent.toLocaleLowerCase('fr').includes(q);});}</script>"""
    return _page("Incidents fournisseurs et lots", body, current=2, script=script)


def _decision_view(
    *,
    observed: Mapping[str, Any],
    regime_plan: Mapping[str, Any],
    action_parameters: Sequence[Mapping[str, str]],
) -> str:
    ca_cards = "".join(
        f"<article class='card'><h3>Produit {html.escape(str(row['product_code']))}</h3>"
        f"<p class='metric'>{100*float(row['delivered_share_of_raw_potential']):.2f} %</p>"
        "<p>Part descriptive de la valeur source livrée sur la valeur potentielle; "
        "ce n’est ni un OTIF ni un taux de service en unités.</p>"
        f"<p>Valeur source non livrée positive : {_qty(row['ca_lost_positive_only_source_value'])}. "
        "<strong>Devise non déclarée dans la source.</strong></p></article>"
        for row in observed["ca_summary"]
    )
    stock_rows = [
        row
        for row in action_parameters
        if row.get("lever_id") == "prepositioned_free_stock_14d"
    ]
    stock_list = "".join(
        f"<li>{_item(row['item_id'])} : {_qty(row['buffer_rounded_qty'])} "
        f"{html.escape(str(row['buffer_uom']))} déjà disponibles à J0</li>"
        for row in stock_rows
    )
    readiness = observed.get("supplier_risk_prediction_readiness") or {}
    body = f"""<section class="warning"><h1>Décisions possibles et données manquantes</h1><p>Les valeurs observées, les résultats simulés et les hypothèses de travail restent séparés. Aucune devise n’est supposée, aucune probabilité fournisseur n’est calculée et aucune action n’est recommandée.</p></section>
<section><h2>OBSERVÉ — valeurs 2025</h2><div class="grid">{ca_cards}</div><p>Les stocks disponibles dans la source sont des valeurs comptables hebdomadaires; ils ne donnent pas directement les quantités physiques libres par article, site et lot.</p></section>
<section><h2>Objectifs de service 93 % et 80 %</h2><p class="metric">PRÉPARÉ, AUCUN RÉSULTAT</p><p>Le plan contient {int(regime_plan['screening_candidate_count'])} configurations. Il ne démontre pas encore qu’une configuration atteint 93 % ou 80 %.</p></section>
<section><h2>Hypothèses d’action à tester</h2><div class="grid"><article class="card"><h3>Transport planifié</h3><p>Tester 7 jours de délai calendaire en moins sur les futurs départs de la voie. Plan fixe, pas pilotage automatique et pas expédition déjà identifiée.</p></article><article class="card"><h3>Stock déjà présent à J0</h3><ul>{stock_list}</ul><p>L’achat, le délai d’approvisionnement et le coût ne sont pas simulés.</p></article><article class="card"><h3>Seconde source explicite</h3><p>Bloqué tant qu’un fournisseur qualifié et sa voie logistique ne sont pas documentés dans un graphe alternatif.</p></article></div><p><strong>Statut : préparé, aucun résultat et aucune recommandation.</strong></p></section>
<section><h2>Mécanisme à recalibrer</h2><p>Le scénario qui conserve 50 % de disponibilité donne actuellement zéro variation de service sur les quatre voies et 15 répétitions. Cela ne signifie pas que le risque est nul : le mécanisme doit être revu avant toute présentation comme stress fournisseur.</p></section>
<section><h2>Données nécessaires à la prévision fournisseur</h2><p><strong>Statut actuel : {html.escape(str(readiness.get('industrial_probability_status') or 'NON PRÊT'))}.</strong> Signal à instruire, pas une probabilité.</p><ul><li>dates promises et dates réellement reçues par ligne de commande;</li><li>quantités commandées, reçues, rejetées et utilisables;</li><li>fournisseur, article, site, commande et ligne stables;</li><li>causes d’écart, capacité, options de secours et données financières validées.</li></ul></section>"""
    return _page("Décisions et données", body, current=3)


def _launcher() -> str:
    cards = "".join(
        f'<a class="card" href="{name}"><strong>{label}</strong><span>{note}</span></a>'
        for name, label, note in (
            (VIEW_FILES[0], "1. 338929 et risques réseau", "Effets 15/30 et carte hors ligne"),
            (VIEW_FILES[1], "2. Incidents fournisseurs et lots", "Quatre retards transport et 2 231 enregistrements techniques"),
            (VIEW_FILES[2], "3. Décisions et données", "Observé 2025 et hypothèses non exécutées"),
        )
    )
    return f"""<!doctype html><html lang="fr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Démonstration fournisseurs préliminaire</title><style>body{{font:16px/1.5 system-ui,sans-serif;background:#eef3f8;color:#13233a;margin:0}}main{{max-width:1050px;margin:auto;padding:50px 20px}}.warn{{background:#fff3cd;border:2px solid #d89000;border-radius:14px;padding:18px}}.grid{{display:grid;grid-template-columns:repeat(3,1fr);gap:14px;margin-top:20px}}.card{{display:flex;flex-direction:column;gap:8px;background:white;border:1px solid #d3deeb;border-radius:14px;padding:22px;color:#13233a;text-decoration:none}}@media(max-width:800px){{.grid{{grid-template-columns:1fr}}}}</style></head><body><main><h1>Supply chain fournisseurs — préliminaire</h1><div class="warn"><strong>15 simulations sur 30.</strong> Résultats provisoires : aucune probabilité, aucun classement universel et aucune recommandation d’action.</div><div class="grid">{cards}</div></main></body></html>"""


def _source_hashes(
    *,
    preliminary_dir: Path,
    observed_dir: Path,
    regime_plan_dir: Path,
    action_plan_dir: Path,
    map_source: Path,
    plotly_js: Path,
) -> dict[str, str]:
    return {
        "preliminary/manifest": base._sha256(
            preliminary_dir / base.preliminary_audit.MANIFEST_FILE
        ),
        "preliminary/audit": base._sha256(
            preliminary_dir / base.preliminary_audit.AUDIT_FILE
        ),
        "preliminary/effects": base._sha256(
            preliminary_dir / base.preliminary_audit.EFFECTS_FILE
        ),
        "preliminary/lots_summary": base._sha256(
            preliminary_dir / base.preliminary_audit.LOT_SUMMARY_FILE
        ),
        "preliminary/lots_detail": base._sha256(
            preliminary_dir / base.preliminary_audit.LOT_DETAIL_FILE
        ),
        "preliminary/boundary": base._sha256(
            preliminary_dir / base.preliminary_audit.BOUNDARY_FILE
        ),
        "observed/manifest": base._sha256(observed_dir / "manifest.json"),
        "observed/bilan": base._sha256(observed_dir / "bilan_observed_2025.json"),
        "regime/plan": base._sha256(regime_plan_dir / "calibration_plan.json"),
        "regime/inventory": base._sha256(regime_plan_dir / "input_inventory.json"),
        "actions/manifest": base._sha256(
            action_plan_dir / "exploratory_action_protocol_manifest.json"
        ),
        "actions/parameters": base._sha256(
            action_plan_dir / "action_lever_parameters.csv"
        ),
        "actions/controls": base._sha256(action_plan_dir / "scientific_controls.json"),
        "map/source": base._sha256(map_source),
        "map/plotly_local": base._sha256(plotly_js),
    }


def _assert_clean_delivery(root: Path) -> None:
    for path in root.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in {".html", ".csv"}:
            continue
        text = path.read_text(encoding="utf-8")
        if USER_FORBIDDEN.search(text):
            raise PreliminaryTransportDeliveryError(
                f"Thème exclu encore présent dans {path.relative_to(root)}."
            )
    for path in (root / LAUNCHER_FILE, root / MANIFEST_FILE):
        if LAUNCHER_MANIFEST_FORBIDDEN.search(path.read_text(encoding="utf-8")):
            raise PreliminaryTransportDeliveryError(
                f"Le lanceur ou manifeste contient un thème exclu: {path.name}."
            )


def build_delivery(
    *,
    preliminary_dir: Path,
    observed_dir: Path,
    regime_plan_dir: Path,
    action_plan_dir: Path,
    map_source: Path,
    plotly_js: Path,
    output_dir: Path,
) -> dict[str, Any]:
    sources = (
        preliminary_dir,
        observed_dir,
        regime_plan_dir,
        action_plan_dir,
        map_source,
        plotly_js,
    )
    output_dir = output_dir.resolve()
    base._assert_external_output(output_dir, [Path(path) for path in sources])
    if output_dir.exists():
        raise PreliminaryTransportDeliveryError(f"Destination déjà existante: {output_dir}")
    preliminary_manifest, effects, lots, details, boundary = (
        _validate_and_load_preliminary(preliminary_dir)
    )
    incidents = _build_incident_rows(effects, lots, details)
    try:
        observed = base._validate_observed(observed_dir)
        regime_plan = base._validate_regime_plan(regime_plan_dir)
        action_manifest, action_parameters = base._validate_action_plan(action_plan_dir)
    except (FileNotFoundError, OSError, TypeError, ValueError, RuntimeError) as error:
        raise PreliminaryTransportDeliveryError(f"Source complémentaire invalide: {error}") from error
    map_document, plotly = _validate_map_source(map_source, plotly_js)

    output_dir.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(
        tempfile.mkdtemp(prefix=f".{output_dir.name}.staging-", dir=output_dir.parent)
    )
    try:
        map_target = staging / MAP_ASSET
        map_target.parent.mkdir(parents=True, exist_ok=True)
        map_target.write_text(_offline_map(map_document, plotly), encoding="utf-8")
        map_audit = base.final_package._validate_html(
            map_target,
            validate_navigation=False,
        )
        _write_csv(staging / SUMMARY_CSV, incidents)
        _write_csv(staging / DETAIL_CSV, details)
        _write_csv(staging / BOUNDARY_CSV, boundary)
        (staging / VIEW_FILES[0]).write_text(_network_view(incidents), encoding="utf-8")
        (staging / VIEW_FILES[1]).write_text(
            _incidents_view(incidents, details), encoding="utf-8"
        )
        (staging / VIEW_FILES[2]).write_text(
            _decision_view(
                observed=observed,
                regime_plan=regime_plan,
                action_parameters=action_parameters,
            ),
            encoding="utf-8",
        )
        (staging / LAUNCHER_FILE).write_text(_launcher(), encoding="utf-8")
        source_hashes = _source_hashes(
            preliminary_dir=preliminary_dir,
            observed_dir=observed_dir,
            regime_plan_dir=regime_plan_dir,
            action_plan_dir=action_plan_dir,
            map_source=map_source,
            plotly_js=plotly_js,
        )
        artifact_hashes = {
            name: base._sha256(staging / name)
            for name in sorted(base._relative_files(staging))
        }
        signature_payload = {
            "schema_version": SCHEMA_VERSION,
            "status": "complete_preliminary_not_final",
            "builder_sha256": base._sha256(Path(__file__).resolve()),
            "source_file_sha256": source_hashes,
            "artifact_file_sha256": artifact_hashes,
            "view_files": list(VIEW_FILES),
            "view_count": 3,
            "preliminary_checkpoint_signature": preliminary_manifest[
                "checkpoint_signature"
            ],
            "regime_plan_signature": regime_plan["plan_signature"],
            "action_protocol_signature": action_manifest["protocol_signature"],
            "included_failure_mode": INCLUDED_FAILURE_MODE,
            "included_supplier_incident_count": 4,
            "lot_detail_record_count": EXPECTED_DETAIL_COUNT,
            "root_receipt_record_count": EXPECTED_ROOT_RECEIPT_COUNT,
            "downstream_record_count": EXPECTED_DOWNSTREAM_RECORD_COUNT,
            "distinct_simulated_lot_id_count": EXPECTED_DISTINCT_LOT_ID_COUNT,
            "lot_id_reused_between_independent_scenarios": True,
            "map_external_resource_count": int(map_audit["external_resource_count"]),
            "preliminary_not_final": True,
            "probability_estimated": False,
            "supplier_ranking_promoted": False,
            "causal_attribution_claimed": False,
            "genealogical_exposure_is_upper_bound": True,
            "industrial_cost_claimed": False,
            "currency_assumed": False,
            "days_recovered_claimed": False,
            "action_result_available": False,
            "action_promotion_allowed": False,
            "engine_executed_by_builder": False,
        }
        manifest = {
            **signature_payload,
            "package_signature": base._canonical_sha256(signature_payload),
            "cryptographic_authentication_present": False,
            "source_artifacts_mutated": False,
            "previous_delivery_mutated": False,
            "runner_artifacts_mutated": False,
        }
        base._write_json(staging / MANIFEST_FILE, manifest)
        _assert_clean_delivery(staging)
        os.replace(staging, output_dir)
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    validate_delivery(output_dir)
    return manifest


def validate_delivery(root: Path) -> dict[str, Any]:
    root = root.resolve()
    manifest = base._read_json(root / MANIFEST_FILE)
    artifacts = manifest.get("artifact_file_sha256")
    if not isinstance(artifacts, Mapping) or not artifacts:
        raise PreliminaryTransportDeliveryError("Empreintes du livrable absentes.")
    if base._relative_files(root) != set(artifacts) | {MANIFEST_FILE}:
        raise PreliminaryTransportDeliveryError("Inventaire du livrable v2 non exact.")
    signature_keys = (
        "schema_version",
        "status",
        "builder_sha256",
        "source_file_sha256",
        "artifact_file_sha256",
        "view_files",
        "view_count",
        "preliminary_checkpoint_signature",
        "regime_plan_signature",
        "action_protocol_signature",
        "included_failure_mode",
        "included_supplier_incident_count",
        "lot_detail_record_count",
        "root_receipt_record_count",
        "downstream_record_count",
        "distinct_simulated_lot_id_count",
        "lot_id_reused_between_independent_scenarios",
        "map_external_resource_count",
        "preliminary_not_final",
        "probability_estimated",
        "supplier_ranking_promoted",
        "causal_attribution_claimed",
        "genealogical_exposure_is_upper_bound",
        "industrial_cost_claimed",
        "currency_assumed",
        "days_recovered_claimed",
        "action_result_available",
        "action_promotion_allowed",
        "engine_executed_by_builder",
    )
    signature_payload = {key: manifest.get(key) for key in signature_keys}
    required_false = (
        "probability_estimated",
        "supplier_ranking_promoted",
        "causal_attribution_claimed",
        "industrial_cost_claimed",
        "currency_assumed",
        "days_recovered_claimed",
        "action_result_available",
        "action_promotion_allowed",
        "engine_executed_by_builder",
        "cryptographic_authentication_present",
        "source_artifacts_mutated",
        "previous_delivery_mutated",
        "runner_artifacts_mutated",
    )
    if (
        manifest.get("schema_version") != SCHEMA_VERSION
        or manifest.get("status") != "complete_preliminary_not_final"
        or manifest.get("builder_sha256") != base._sha256(Path(__file__).resolve())
        or manifest.get("view_files") != list(VIEW_FILES)
        or manifest.get("view_count") != 3
        or manifest.get("included_failure_mode") != INCLUDED_FAILURE_MODE
        or manifest.get("included_supplier_incident_count") != 4
        or manifest.get("lot_detail_record_count") != EXPECTED_DETAIL_COUNT
        or manifest.get("root_receipt_record_count") != EXPECTED_ROOT_RECEIPT_COUNT
        or manifest.get("downstream_record_count")
        != EXPECTED_DOWNSTREAM_RECORD_COUNT
        or manifest.get("distinct_simulated_lot_id_count")
        != EXPECTED_DISTINCT_LOT_ID_COUNT
        or manifest.get("lot_id_reused_between_independent_scenarios") is not True
        or manifest.get("map_external_resource_count") != 0
        or manifest.get("preliminary_not_final") is not True
        or manifest.get("genealogical_exposure_is_upper_bound") is not True
        or not all(manifest.get(field) is False for field in required_false)
        or manifest.get("package_signature")
        != base._canonical_sha256(signature_payload)
    ):
        raise PreliminaryTransportDeliveryError("Manifeste du livrable v2 invalide.")
    for name, expected in artifacts.items():
        path = root / str(name)
        if not path.is_file() or base._sha256(path) != str(expected):
            raise PreliminaryTransportDeliveryError(f"Artefact altéré: {name}")
    for name in (LAUNCHER_FILE, *VIEW_FILES):
        base.final_package._validate_html(root / name, validate_navigation=True)
    map_audit = base.final_package._validate_html(
        root / MAP_ASSET,
        validate_navigation=False,
    )
    if int(map_audit["external_resource_count"]) != 0:
        raise PreliminaryTransportDeliveryError("La carte v2 n’est pas autonome.")
    summary = _read_csv(root / SUMMARY_CSV)
    details = _read_csv(root / DETAIL_CSV)
    if len(summary) != 4 or len(details) != EXPECTED_DETAIL_COUNT:
        raise PreliminaryTransportDeliveryError("Tables transport v2 incomplètes.")
    launcher = (root / LAUNCHER_FILE).read_text(encoding="utf-8")
    if sum(f'href="{name}"' in launcher for name in VIEW_FILES) != 3:
        raise PreliminaryTransportDeliveryError("Le lanceur n’offre pas exactement trois vues.")
    _assert_clean_delivery(root)
    return manifest


def parse_args(argv: Iterable[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--preliminary-dir", type=Path, default=DEFAULT_PRELIMINARY_DIR)
    parser.add_argument("--observed-dir", type=Path, default=DEFAULT_OBSERVED_DIR)
    parser.add_argument("--regime-plan-dir", type=Path, default=DEFAULT_REGIME_PLAN_DIR)
    parser.add_argument("--action-plan-dir", type=Path, default=DEFAULT_ACTION_PLAN_DIR)
    parser.add_argument("--map-source", type=Path, default=DEFAULT_MAP_SOURCE)
    parser.add_argument("--plotly-js", type=Path, default=DEFAULT_PLOTLY_JS)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--validate-only", action="store_true")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    if args.validate_only:
        manifest = validate_delivery(args.output_dir)
        print(
            json.dumps(
                {
                    "status": "valid",
                    "entrypoint": str((args.output_dir / LAUNCHER_FILE).resolve()),
                    "package_signature": manifest["package_signature"],
                },
                ensure_ascii=False,
            )
        )
        return 0
    manifest = build_delivery(
        preliminary_dir=args.preliminary_dir,
        observed_dir=args.observed_dir,
        regime_plan_dir=args.regime_plan_dir,
        action_plan_dir=args.action_plan_dir,
        map_source=args.map_source,
        plotly_js=args.plotly_js,
        output_dir=args.output_dir,
    )
    print(
        json.dumps(
            {
                "status": manifest["status"],
                "entrypoint": str((args.output_dir / LAUNCHER_FILE).resolve()),
                "package_signature": manifest["package_signature"],
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
