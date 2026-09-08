#!/usr/bin/env python3
"""Assemble an external three-view delivery for the exact 15/30 checkpoint.

This is deliberately separate from the final 30/30 package.  It consumes the
signed preliminary audit, compact observed 2025 data, an existing quality/lot
page, an existing autonomous map, and prepare-only plans.  It never promotes a
supplier ranking or an action and never invents a currency or probability.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import html
import json
import math
import os
import re
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any, Mapping, Sequence


REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

try:
    from . import build_industrial_supply_final_package as final_package
    from . import supplier_network_exploratory_action_protocol as action_protocol
    from . import supplier_network_preliminary_15_audit as preliminary_audit
    from . import supplier_service_regime_calibration_protocol as regime_protocol
    from . import supplier_stock_signal_calibration_audit as stock_calibration_audit
except ImportError:  # pragma: no cover - direct CLI execution
    import build_industrial_supply_final_package as final_package
    import supplier_network_exploratory_action_protocol as action_protocol
    import supplier_network_preliminary_15_audit as preliminary_audit
    import supplier_service_regime_calibration_protocol as regime_protocol
    import supplier_stock_signal_calibration_audit as stock_calibration_audit


SCHEMA_VERSION = "etudecas.industrial_supply_preliminary_delivery.v1"
MANIFEST_FILE = "preliminary_delivery_manifest.json"
LAUNCHER_FILE = "OUVRIR_PRELIMINAIRE_15_SUR_30.html"
VIEW_FILES = (
    "01_RISQUES_RESEAU_338929.html",
    "02_CASCADE_QUALITE_LOTS.html",
    "03_DECISIONS_ET_DONNEES.html",
)
PRELIMINARY_ASSET_DIR = "assets/preliminary_15_of_30"
QUALITY_ASSET = "assets/quality_lot_source.html"
MAP_ASSET = "assets/network_map_autonomous.html"
STOCK_CALIBRATION_ASSET = "assets/stock_signal_calibration_audit.html"
MAX_AUTONOMOUS_MAP_BYTES = 40 * 1024 * 1024
FOCUS_SUPPLIER_ID = "SDC-VD0914360C"
FOCUS_CHAIN_ID = "sdc_vd0914360c_338929_m_1810"
FOCUS_SCENARIO_ID = f"{FOCUS_CHAIN_ID}__transport_delay__120"
DEFAULT_ACTION_PLAN_DIR = (
    action_protocol.ARTIFACT_PARENT
    / "supplier_network_exploratory_action_protocol_20260903_v5"
)
STOCK_CALIBRATION_CLIENT_SENTENCES = (
    "Point de vigilance du modèle : pour 21 matières sur 24, la cible de sécurité est calculée avec un débit de référence au moins dix fois supérieur à la consommation effectivement simulée.",
    "Pour 038005 et 049371, les “20/40 jours” représentent en moyenne environ 709/794 jours de consommation ; le stock présent avant J60 couvre à lui seul les 180 jours testés dans 15 simulations sur 15.",
    "Ces essais montrent donc aujourd’hui un incident masqué par le réglage des stocks, et non une résilience industrielle démontrée ; ils doivent être rejoués après recalage sur les consommations, commandes ouvertes et tailles de lot validées.",
)

LEVER_LABELS = {
    "future_lane_transport_reduction": (
        "Réduire de 7 jours le délai des futurs envois sur toute la voie "
        "(plan fixé à l’avance)"
    ),
    "prepositioned_free_stock_14d": (
        "Stock tampon déjà disponible avant l’incident : cible de 14 jours "
        "arrondie au "
        "multiple de commande du modèle"
    ),
    "quality_scenario_full_lane_calendar_open_loop_transport_reduction_7d": (
        "Scénario qualité : réduire le transport de 7 jours sans raccourcir "
        "l’attente qualité"
    ),
    "explicit_counterfactual_alternative_source": (
        "Second fournisseur, uniquement si sa qualification, sa capacité et sa "
        "voie logistique sont renseignées"
    ),
}

STOCK_SERIES_LABELS = {
    "component_stock_cos": "Stock comptable de composants — famille Cos",
    "component_stock_pharma": "Stock comptable de composants — famille Pharma",
    "finished_goods_stock_268091": "Stock comptable de produit fini 268091",
    "finished_goods_stock_268967": "Stock comptable de produit fini 268967",
}


class PreliminaryDeliveryError(RuntimeError):
    """Raised when a source could be mistaken for a completed result."""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _canonical_sha256(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()


def _read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8-sig") as stream:
        value = json.load(stream)
    if not isinstance(value, dict):
        raise PreliminaryDeliveryError(f"Objet JSON attendu: {path}")
    return value


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        return [dict(row) for row in csv.DictReader(stream)]


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _relative_files(root: Path) -> set[str]:
    return {
        path.relative_to(root).as_posix()
        for path in root.rglob("*")
        if path.is_file()
    }


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True


def _assert_external_output(output: Path, sources: Sequence[Path]) -> None:
    resolved = output.resolve()
    for source in sources:
        source_resolved = source.resolve()
        if resolved == source_resolved or _is_relative_to(resolved, source_resolved):
            raise PreliminaryDeliveryError(
                "Le livrable préliminaire doit rester dans un nouveau dossier externe."
            )


def _validate_regime_plan(root: Path) -> dict[str, Any]:
    plan_path = root / "calibration_plan.json"
    inventory_path = root / "input_inventory.json"
    design_path = root / "scenario_design.csv"
    if not all(path.is_file() for path in (plan_path, inventory_path, design_path)):
        raise PreliminaryDeliveryError("Plan 93/80 incomplet.")
    plan = _read_json(plan_path)
    inventory = _read_json(inventory_path)
    stages = plan.get("stages") if isinstance(plan.get("stages"), Mapping) else {}
    execution = (
        plan.get("execution_contract")
        if isinstance(plan.get("execution_contract"), Mapping)
        else {}
    )
    service = (
        plan.get("service_definition")
        if isinstance(plan.get("service_definition"), Mapping)
        else {}
    )
    if (
        plan.get("schema_version") != regime_protocol.SCHEMA_VERSION
        or plan.get("status") != "planned_not_executed"
        or plan.get("evidence_class")
        != "simulation_hypothesis_not_observed_performance"
        or plan.get("old_results_mutated") is not False
        or plan.get("engine_mutated") is not False
        or plan.get("graph_source_mutated") is not False
        or execution.get("implemented_by_this_prepare_only_module") is not False
        or service.get("targets") != [0.93, 0.8]
        or (stages.get("preliminary") or {}).get("publishable_as_final_confirmation")
        is not False
        or (stages.get("final") or {}).get("reuses_preliminary_exactly") is not True
        or not isinstance(inventory, Mapping)
        or not inventory
        or not _read_csv(design_path)
    ):
        raise PreliminaryDeliveryError(
            "Le plan 93/80 ne prouve pas son statut préparé sans résultat."
        )
    expected_signature = regime_protocol.stable_sha256(
        {
            "schema_version": regime_protocol.SCHEMA_VERSION,
            "reference_audit": plan.get("reference_audit"),
            "families": plan.get("families"),
            "candidate_inputs": {
                key: {
                    "input_sha256": value["input_sha256"],
                    "change_ledger_sha256": value["change_ledger_sha256"],
                }
                for key, value in sorted(inventory.items())
            },
            "stages": plan.get("stages"),
            "selection_rule": plan.get("selection_rule"),
            "service_definition": plan.get("service_definition"),
            "execution_contract": plan.get("execution_contract"),
        }
    )
    if plan.get("plan_signature") != expected_signature:
        raise PreliminaryDeliveryError("Empreinte interne du plan 93/80 invalide.")
    result_like_names = {
        name
        for name in _relative_files(root)
        if re.search(r"(^|/)(results?|metrics?|summary)\.(csv|json)$", name, re.I)
    }
    if result_like_names:
        raise PreliminaryDeliveryError(
            "Le dossier 93/80 contient un fichier pouvant être pris pour un résultat."
        )
    return plan


def _validate_action_plan(root: Path) -> tuple[dict[str, Any], list[dict[str, str]]]:
    try:
        action_protocol.validate_protocol_artifact(root)
    except (FileNotFoundError, OSError, TypeError, ValueError) as error:
        raise PreliminaryDeliveryError(f"Protocole d’actions invalide: {error}") from error
    manifest = _read_json(root / "exploratory_action_protocol_manifest.json")
    controls = _read_json(root / "scientific_controls.json")
    parameters = _read_csv(root / "action_lever_parameters.csv")
    lever_ids = sorted({str(row.get("lever_id") or "") for row in parameters})
    claims = controls.get("claims") if isinstance(controls.get("claims"), Mapping) else {}
    execution = (
        controls.get("execution")
        if isinstance(controls.get("execution"), Mapping)
        else {}
    )
    if (
        manifest.get("schema_version") != action_protocol.SCHEMA_VERSION
        or manifest.get("contract_revision") != action_protocol.CONTRACT_REVISION
        or manifest.get("status") != "planned_not_executed"
        or manifest.get("engine_execution_enabled") is not False
        or manifest.get("stock_buffers_lotified") is not True
        or manifest.get("industrial_action_cost_published") is not False
        or manifest.get("closed_loop_claimed") is not False
        or len(parameters)
        != action_protocol.EXPECTED_LANE_COUNT * len(action_protocol.EXPECTED_LEVERS)
        or set(lever_ids) != set(LEVER_LABELS)
        or set(lever_ids) != set(action_protocol.EXPECTED_LEVERS)
        or claims.get("supplier_probability_estimated") is not False
        or claims.get("action_recommended") is not False
        or claims.get("action_promotion_allowed") is not False
        or claims.get("industrial_cost_claimed") is not False
        or execution.get("engine_execution_enabled") is not False
    ):
        raise PreliminaryDeliveryError(
            "Le protocole d’actions doit rester préparé, non exécuté et non promu."
        )
    if any(
        str(row.get("new_action_run_status") or "")
        not in {
            "planned_new_run",
            "conditional_positive_paired_J0_stock",
            "planned_after_V3_quality_pair_available",
            "blocked_missing_explicit_alternative_source_register",
        }
        or str(row.get("industrial_cost_status") or "")
        != "not_estimated_missing_industrial_cost_inputs"
        or str(row.get("industrial_action_cost_available") or "").lower()
        != "false"
        or str(row.get("closed_loop_claimed") or "").lower() != "false"
        or str(row.get("not_a_recommendation") or "").lower() != "true"
        or str(row.get("action_promotion_allowed") or "").lower() != "false"
        for row in parameters
    ):
        raise PreliminaryDeliveryError("Une ligne d’action porte un statut trompeur.")
    by_lever = {
        lever: [row for row in parameters if row.get("lever_id") == lever]
        for lever in action_protocol.EXPECTED_LEVERS
    }
    if any(
        len(rows) != action_protocol.EXPECTED_LANE_COUNT
        for rows in by_lever.values()
    ):
        raise PreliminaryDeliveryError("Les quatre voies ne couvrent pas chaque levier V5.")
    stock_rows = by_lever["prepositioned_free_stock_14d"]
    stock_quantities = {
        (float(row["buffer_rounded_qty"]), str(row["buffer_uom"]))
        for row in stock_rows
    }
    if (
        stock_quantities
        != {(1100.0, "KG"), (300.0, "KG"), (150000.0, "UN"), (120000.0, "UN")}
        or any(
            str(row.get("stock_present_at_j0_hypothesis") or "").lower()
            != "true"
            or str(row.get("stock_acquisition_simulated") or "").lower()
            != "false"
            or float(row.get("buffer_procurement_lot_count") or 0.0) <= 0.0
            for row in stock_rows
        )
    ):
        raise PreliminaryDeliveryError(
            "Les stocks V5 doivent être lotifiés, quantifiés et déjà présents à J0."
        )
    quality_rows = by_lever[
        "quality_scenario_full_lane_calendar_open_loop_transport_reduction_7d"
    ]
    if any(
        str(row.get("action_timing") or "")
        != "fixed_calendar_open_loop_whole_lane_in_quality_scenario"
        or str(row.get("quality_hold_reduction_claimed") or "").lower()
        != "false"
        or str(row.get("identified_lot_claimed") or "").lower() != "false"
        for row in quality_rows
    ):
        raise PreliminaryDeliveryError(
            "Le levier qualité V5 doit conserver l’attente et rester un plan fixe de voie."
        )
    return manifest, parameters


def _validate_quality(
    root: Path,
) -> tuple[dict[str, Any], Path, dict[str, int]]:
    try:
        manifest, page = final_package._validate_component_package(root)
    except (FileNotFoundError, OSError, TypeError, ValueError, RuntimeError) as error:
        raise PreliminaryDeliveryError(f"Page qualité/lots invalide: {error}") from error
    if not page.is_file():
        raise PreliminaryDeliveryError("Page qualité/lots absente.")
    outputs = manifest.get("outputs")
    if not isinstance(outputs, Mapping):
        raise PreliminaryDeliveryError("Payload qualité/lots non déclaré.")
    payload_path = final_package._safe_child(root.resolve(), outputs.get("dashboard_payload"))
    payload = _read_json(payload_path)
    observed = payload.get("observed_2025_order_book")
    lot_proof = payload.get("paired_causal_lot_proof")
    conclusions = payload.get("scientific_conclusions")
    if (
        not isinstance(observed, Mapping)
        or not isinstance(lot_proof, Mapping)
        or not isinstance(conclusions, Mapping)
        or int(observed.get("order_count") or 0) != 23
        or str(lot_proof.get("scenario_id") or "")
        != "all_021081__quality_hold__180"
        or int(lot_proof.get("affected_opening_po_technical_row_count") or 0)
        != 23
        or int(lot_proof.get("technical_rows_with_paired_receipt_effect") or 0)
        != 23
        or int(lot_proof.get("technical_rows_with_paired_descendant_effect", -1))
        != 0
        or str(lot_proof.get("no_descendant_wording") or "")
        != "receipt not consumed in the tested horizon"
        or not isinstance(lot_proof.get("seed"), int)
        or "aucun effet client"
        not in str(conclusions.get("lots") or "").casefold()
    ):
        raise PreliminaryDeliveryError(
            "Les compteurs signés de la cascade qualité attendue sont absents."
        )
    facts = {
        "planned_receipt_line_count": 23,
        "shifted_receipt_line_count": 23,
        "consumed_descendant_count": 0,
        "paired_simulation_count": 1,
        "quality_hold_days": 180,
    }
    return manifest, page, facts


def _load_focus_network_result(root: Path) -> dict[str, str]:
    rows = _read_csv(root / preliminary_audit.BOUNDARY_FILE)
    selected = [row for row in rows if row.get("supplier_id") == FOCUS_SUPPLIER_ID]
    if len(selected) != 1:
        raise PreliminaryDeliveryError("Résultat consolidé 338929 absent ou dupliqué.")
    row = selected[0]
    numeric_fields = (
        "horizon_service_delta_percentage_points",
        "worst_rolling_28d_service_delta_percentage_points",
        "backlog_delta_days_per_demand_unit",
        "released_production_shortfall_percent",
    )
    try:
        values = {field: float(row[field]) for field in numeric_fields}
    except (KeyError, TypeError, ValueError) as error:
        raise PreliminaryDeliveryError(
            "Indicateurs consolidés 338929 non numériques."
        ) from error
    if (
        row.get("driver_chain_id") != FOCUS_CHAIN_ID
        or row.get("driver_scenario_id") != FOCUS_SCENARIO_ID
        or row.get("driver_failure_mode") != "transport_delay"
        or row.get("paired_seed_count") != "30"
        or row.get("group_is_unordered", "").casefold() != "true"
        or row.get("universal_supplier_ranking_claimed", "").casefold() != "false"
        or row.get("historical_probability_estimated", "").casefold() != "false"
        or not all(math.isfinite(value) for value in values.values())
        or values["horizon_service_delta_percentage_points"] > 0.0
        or values["worst_rolling_28d_service_delta_percentage_points"] > 0.0
        or values["backlog_delta_days_per_demand_unit"] < 0.0
        or values["released_production_shortfall_percent"] < 0.0
    ):
        raise PreliminaryDeliveryError(
            "Lignée ou gardes métier du résultat 338929 incohérentes."
        )
    return row


def _validate_map(path: Path) -> dict[str, Any]:
    if not path.is_file() or path.stat().st_size > MAX_AUTONOMOUS_MAP_BYTES:
        raise PreliminaryDeliveryError("Carte autonome absente ou trop volumineuse.")
    try:
        audit = final_package._validate_html(path, validate_navigation=False)
    except (OSError, UnicodeError, ValueError, RuntimeError) as error:
        raise PreliminaryDeliveryError(f"Carte autonome invalide: {error}") from error
    if int(audit.get("external_resource_count") or 0) != 0:
        raise PreliminaryDeliveryError("La carte officielle ne doit dépendre d’Internet.")
    return audit


def _validate_observed(root: Path) -> dict[str, Any]:
    try:
        final_package._validate_observed(root)
    except (FileNotFoundError, OSError, TypeError, ValueError, RuntimeError) as error:
        raise PreliminaryDeliveryError(f"Bilan observé 2025 invalide: {error}") from error
    payload = _read_json(root / "bilan_observed_2025.json")
    if payload.get("currency_status") != (
        "not_declared_in_source; EUR_is_working_convention"
    ):
        raise PreliminaryDeliveryError("Statut de devise observée absent.")
    if not payload.get("ca_summary") or not payload.get("stock_summary"):
        raise PreliminaryDeliveryError("Résumé observé 2025 incomplet.")
    return payload


def _validate_stock_calibration_audit(
    root: Path,
) -> tuple[dict[str, Any], dict[tuple[str, str], Mapping[str, Any]], Path, dict[str, Any]]:
    """Validate the exact 15-simulation calibration evidence consumed by view 3."""

    try:
        stock_calibration_audit.validate(root)
    except (FileNotFoundError, OSError, TypeError, ValueError, RuntimeError) as error:
        raise PreliminaryDeliveryError(
            f"Audit stock/besoin MRP invalide: {error}"
        ) from error
    manifest = _read_json(root / stock_calibration_audit.MANIFEST_JSON)
    payload = _read_json(root / stock_calibration_audit.RESULT_JSON)
    focus_rows = payload.get("focus")
    if not isinstance(focus_rows, list):
        raise PreliminaryDeliveryError("Lignes prioritaires de l’audit stock absentes.")
    focus: dict[tuple[str, str], Mapping[str, Any]] = {}
    for row in focus_rows:
        if not isinstance(row, Mapping):
            raise PreliminaryDeliveryError("Ligne prioritaire stock invalide.")
        key = (str(row.get("node_id") or ""), str(row.get("item_id") or ""))
        if not all(key) or key in focus:
            raise PreliminaryDeliveryError(
                "Couple usine–matière absent ou dupliqué dans l’audit stock."
            )
        focus[key] = row
    expected_focus = set(stock_calibration_audit.FOCUS_KEYS)
    if set(focus) != expected_focus:
        raise PreliminaryDeliveryError("Périmètre prioritaire stock inattendu.")
    numeric_fields = (
        "safety_time_days_mean",
        "physical_consumption_avg_qty_per_calendar_day_mean",
        "safety_target_rate_to_physical_ratio_mean",
        "reference_stock_cover_physical_days_mean",
        "preincident_stock_minus_window_consumption_qty_mean",
        "preincident_stock_minus_window_consumption_qty_min",
        "preincident_stock_minus_window_consumption_qty_max",
    )
    expected_safety_days = {
        ("M-1430", "item:038005"): 20,
        ("M-1810", "item:049371"): 40,
    }
    expected_rounded_cover = {
        ("M-1430", "item:038005"): 709,
        ("M-1810", "item:049371"): 794,
    }
    for key, row in focus.items():
        try:
            values = {field: float(row[field]) for field in numeric_fields}
            cover_count = int(row["preincident_stock_covers_window_simulation_count"])
        except (KeyError, TypeError, ValueError) as error:
            raise PreliminaryDeliveryError(
                f"Valeurs prioritaires stock non numériques pour {key}."
            ) from error
        if (
            not all(math.isfinite(value) for value in values.values())
            or values["safety_time_days_mean"] != expected_safety_days[key]
            or values["safety_target_rate_to_physical_ratio_mean"] < 10.0
            or round(values["reference_stock_cover_physical_days_mean"])
            != expected_rounded_cover[key]
            or values["preincident_stock_minus_window_consumption_qty_min"] <= 0.0
            or cover_count != 15
            or row.get("calibration_status") != "ecart_majeur_de_calibration"
            or "static_requirement_override"
            not in str(row.get("mrp_gross_requirement_basis") or "")
        ):
            raise PreliminaryDeliveryError(
                f"Garde scientifique stock non satisfaite pour {key}."
            )
    status_counts = payload.get("status_counts")
    if (
        payload.get("schema_version") != stock_calibration_audit.SCHEMA_VERSION
        or int(payload.get("simulation_count") or 0) != 15
        or int(payload.get("material_count") or 0) != 24
        or not isinstance(status_counts, Mapping)
        or int(status_counts.get("ecart_majeur_de_calibration") or 0) != 21
        or manifest.get("status") != "complete"
        or manifest.get("engine_invoked") is not False
        or manifest.get("source_files_mutated") is not False
        or int(manifest.get("simulation_count") or 0) != 15
        or int(manifest.get("material_count") or 0) != 24
    ):
        raise PreliminaryDeliveryError(
            "L’audit stock doit prouver 15 simulations, 24 matières et 21 écarts majeurs."
        )
    page = root / stock_calibration_audit.RESULT_HTML
    try:
        page_audit = final_package._validate_html(page, validate_navigation=False)
    except (OSError, UnicodeError, ValueError, RuntimeError) as error:
        raise PreliminaryDeliveryError(
            f"Annexe stock autonome invalide: {error}"
        ) from error
    page_text = page.read_text(encoding="utf-8")
    if (
        int(page_audit.get("external_resource_count") or 0) != 0
        or "ne démontre pas que la chaîne industrielle résisterait" not in page_text
        or "21</div>écarts majeurs" not in page_text
    ):
        raise PreliminaryDeliveryError(
            "L’annexe stock doit rester autonome et porter l’avertissement de calibration."
        )
    return payload, focus, page, page_audit


def _nav(current: int) -> str:
    labels = (
        "1. Risques réseau / 338929",
        "2. Cascade qualité / lots",
        "3. Décisions / données manquantes",
    )
    links = "".join(
        f'<a class="{"active" if index == current else ""}" href="{name}">'
        f"{html.escape(label)}</a>"
        for index, (name, label) in enumerate(zip(VIEW_FILES, labels, strict=True), 1)
    )
    return f'<nav><a href="{LAUNCHER_FILE}">Accueil</a>{links}</nav>'


def _page(title: str, body: str, *, current: int) -> str:
    return f"""<!doctype html><html lang="fr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{html.escape(title)}</title><style>
body{{margin:0;background:#f1f5f9;color:#13233a;font:15px/1.5 system-ui,sans-serif}}nav{{display:flex;gap:8px;flex-wrap:wrap;padding:12px 18px;background:#10233f;position:sticky;top:0;z-index:2}}nav a{{color:white;text-decoration:none;padding:8px 12px;border-radius:18px}}nav a.active{{background:#2670ca}}main{{max-width:1500px;margin:auto;padding:18px}}section,.card{{background:white;border:1px solid #d7e1ed;border-radius:14px;padding:18px;margin:14px 0}}a.card{{display:block;color:#13233a;text-decoration:none}}a.card:hover{{border-color:#2670ca;background:#f7faff}}.warning{{background:#fff3cd;border:2px solid #d89000}}.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(250px,1fr));gap:12px}}table{{width:100%;border-collapse:collapse}}th,td{{padding:8px;border-bottom:1px solid #dce4ed;text-align:left}}.metric{{font-size:1.35rem;font-weight:750}}.muted{{color:#596b80}}code{{font-size:11px}}
</style></head><body>{_nav(current)}<main>{body}</main></body></html>"""


def _format_signed_decimal(value: Any, digits: int = 2) -> str:
    try:
        number = float(value)
    except (TypeError, ValueError) as error:
        raise PreliminaryDeliveryError("Valeur simulée non numérique.") from error
    if abs(number) < 0.5 * 10 ** (-digits):
        number = 0.0
    sign = "+" if number > 0.0 else ("−" if number < 0.0 else "")
    return f"{sign}{abs(number):.{digits}f}".replace(".", ",")


def _render_network_view(focus: Mapping[str, str]) -> str:
    prelim_href = f"{PRELIMINARY_ASSET_DIR}/PRELIMINAIRE_15_SUR_30.html"
    body = f"""<section class="warning"><h1>338929 → M-1810 → 268091, puis réseau fournisseurs</h1><p><strong>SIMULÉ — résultat préliminaire 15/30 :</strong> les chiffres décrivent la réponse du modèle aux incidents testés. Ils ne mesurent pas la probabilité réelle de défaillance d’un fournisseur.</p><p><strong>SIGNAL DE PRIORITÉ :</strong> quatre dossiers restent à examiner ensemble car la campagne terminée ne permet pas de les ordonner de façon fiable. Ce n’est pas un classement fournisseur.</p></section>
<section><h2>Résultat déjà consolidé sur 30 simulations comparables</h2><p><strong>HYPOTHÈSE :</strong> 120 jours de retard de transport sur la voie 338929 vers M-1810. Il s’agit d’un test de conséquence, pas d’une prévision de survenue.</p><div class="grid"><article class="card"><span class="metric">{_format_signed_decimal(focus['horizon_service_delta_percentage_points'])} points</span><p>Impact moyen sur le volume servi à la date attendue sur l’horizon.</p></article><article class="card"><span class="metric">{_format_signed_decimal(focus['worst_rolling_28d_service_delta_percentage_points'])} points</span><p>Pire dégradation moyenne sur une période glissante de 28 jours.</p></article><article class="card"><span class="metric">{_format_signed_decimal(focus['backlog_delta_days_per_demand_unit'])} jours</span><p>Retard cumulé supplémentaire, ramené au volume demandé.</p></article><article class="card"><span class="metric">{_format_signed_decimal(focus['released_production_shortfall_percent'])} %</span><p>Manque de production libérée à J719 : la quantité est rattrapée, mais elle a été servie trop tard.</p></article></div><p>Ces chiffres viennent de la campagne principale terminée 30/30. Les nouvelles analyses 15/30 ajoutent les périodes, les causes métier et les lots; elles restent provisoires.</p></section>
<section><h2>Annexes interactives — facultatives pendant le parcours 01 → 02 → 03</h2><p>Moyenne et plage constatée parmi les 15 premières simulations, sans conclusion statistique finale. La liste des lots techniques simulés est recherchable dans le résultat détaillé.</p><div class="grid"><a class="card" href="{prelim_href}"><strong>Annexe interactive — résultats 15/30 et lots</strong><br><span class="muted">Effets, dispersion descriptive et liste recherchable des lots techniques.</span></a><a class="card" href="{MAP_ASSET}"><strong>Annexe interactive — carte autonome complète</strong><br><span class="muted">Réseau, fournisseurs, articles et flux; aucune connexion Internet requise.</span></a></div><p class="muted">La variante plus légère d’environ 7,7 Mo dépend d’une bibliothèque chargée sur Internet; elle n’est donc pas utilisée comme vue officielle du rendez-vous.</p></section>"""
    return _page("Risques réseau — préliminaire 15/30", body, current=1)


def _render_quality_view(facts: Mapping[str, int]) -> str:
    body = f"""<section class="warning"><h1>Cascade qualité et lots</h1><p><strong>HYPOTHÈSE :</strong> une retenue qualité de {facts['quality_hold_days']} jours est appliquée dans le modèle pour observer sa propagation. <strong>SIMULÉ :</strong> l’exposition généalogique obtenue est une borne haute; elle ne prouve ni une perte causale ni l’identité d’un même lot entre deux simulations.</p></section><section><h2>Ce que montre la cascade testée</h2><div class="grid"><article class="card"><span class="metric">{facts['planned_receipt_line_count']} lignes</span><p><strong>OBSERVÉ :</strong> lignes techniques planifiées dans le snapshot 2025; ce ne sont ni des réceptions réelles ni des numéros de lots industriels.</p></article><article class="card"><span class="metric">{facts['shifted_receipt_line_count']} / {facts['planned_receipt_line_count']}</span><p><strong>SIMULÉ :</strong> disponibilité des réceptions décalée par l’hypothèse qualité.</p></article><article class="card"><span class="metric">{facts['consumed_descendant_count']}</span><p>Descendant consommé dans l’horizon; aucun effet client n’est donc démontré dans ce test.</p></article><article class="card"><span class="metric">{facts['paired_simulation_count']} simulation</span><p>Illustration technique unique : aucune fréquence ni probabilité fournisseur ne peut en être déduite.</p></article></div></section><section><h2>Annexe interactive — facultative pendant le parcours 01 → 02 → 03</h2><a class="card" href="{QUALITY_ASSET}"><strong>Annexe interactive — cascade qualité et détail des lots</strong><br><span class="muted">Page autonome copiée dans ce paquet hors ligne.</span></a></section>"""
    return _page("Cascade qualité et lots", body, current=2)


def _format_source_value(value: Any) -> str:
    try:
        number = float(value)
    except (TypeError, ValueError) as error:
        raise PreliminaryDeliveryError("Valeur observée non numérique.") from error
    return f"{number:,.0f}".replace(",", " ")


def _render_action_cards(
    action_parameters: Sequence[Mapping[str, str]],
) -> str:
    grouped = {
        lever: [row for row in action_parameters if row.get("lever_id") == lever]
        for lever in action_protocol.EXPECTED_LEVERS
    }
    stock_lines = "".join(
        "<li>"
        f"{html.escape(str(row['item_id']).removeprefix('item:'))} vers "
        f"{html.escape(str(row['dst_node_id']))} : "
        f"{_format_source_value(row['buffer_rounded_qty'])} "
        f"{html.escape(str(row['buffer_uom']))}</li>"
        for row in grouped["prepositioned_free_stock_14d"]
    )
    descriptions = {
        "future_lane_transport_reduction": (
            "Plan fixe appliqué aux futurs départs de toute la voie pendant "
            "l’incident. Ce n’est ni une décision automatique ni l’accélération "
            "d’une expédition déjà identifiée."
        ),
        "prepositioned_free_stock_14d": (
            "Hypothèse de stock physiquement disponible avant l’incident, sans "
            "simuler son achat, son délai d’approvisionnement ni son coût. "
            "Le multiple utilisé vient du modèle : ce n’est pas une quantité "
            "minimale contractuelle confirmée."
            f"<ul>{stock_lines}</ul>"
        ),
        "quality_scenario_full_lane_calendar_open_loop_transport_reduction_7d": (
            "L’attente qualité n’est pas raccourcie. Seule la composante transport "
            "de la voie entière est modifiée selon un calendrier fixé à l’avance; "
            "aucun lot particulier n’est piloté."
        ),
        "explicit_counterfactual_alternative_source": (
            "Bloqué tant qu’un fournisseur de remplacement qualifié et sa voie "
            "logistique ne sont pas décrits explicitement dans une version alternative "
            "du réseau."
        ),
    }
    return "".join(
        f"<article class='card'><h3>{html.escape(LEVER_LABELS[lever])}</h3>"
        f"<div>{descriptions[lever]}</div>"
        "<p><strong>PRÉPARÉ, AUCUN RÉSULTAT.</strong> Ce n’est pas une "
        "recommandation et aucun coût industriel n’est chiffré.</p></article>"
        for lever in action_protocol.EXPECTED_LEVERS
    )


def _render_decision_view(
    *,
    observed: Mapping[str, Any],
    regime_plan: Mapping[str, Any],
    action_parameters: Sequence[Mapping[str, str]],
    stock_calibration_focus: Mapping[tuple[str, str], Mapping[str, Any]],
) -> str:
    if set(stock_calibration_focus) != set(stock_calibration_audit.FOCUS_KEYS):
        raise PreliminaryDeliveryError("Périmètre stock incomplet pour la vue 3.")
    ca_cards = "".join(
        f"<article class='card'><h3>Produit {html.escape(str(row['product_code']))}</h3>"
        f"<p class='metric'>{100*float(row['delivered_share_of_raw_potential']):.2f} %</p>"
        "<p>Part de la valeur potentielle que la source indique comme livrée. "
        "Ce pourcentage financier ne mesure pas la part des commandes livrées "
        "complètes et à l’heure.</p>"
        f"<p>Valeur de chiffre d’affaires non livré indiquée par la source : {_format_source_value(row['ca_lost_positive_only_source_value'])}. "
        "<strong>Devise non déclarée dans la source.</strong></p></article>"
        for row in observed["ca_summary"]
    )
    stock_cards = "".join(
        f"<tr><td>{html.escape(STOCK_SERIES_LABELS.get(str(row['series_id']), str(row['series_id'])))}</td>"
        f"<td>{_format_source_value(row['mean_stock_value_source'])}</td>"
        f"<td>{int(row['snapshot_count'])}</td><td>valeur comptable; quantité physique absente</td></tr>"
        for row in observed["stock_summary"]
    )
    lever_cards = _render_action_cards(action_parameters)
    readiness = observed.get("supplier_risk_prediction_readiness") or {}
    readiness_label = {
        "NOT_READY": "données insuffisantes pour calculer une probabilité fournisseur",
    }.get(
        str(readiness.get("industrial_probability_status") or ""),
        "statut à confirmer",
    )
    stock_calibration_warning = "".join(
        f"<p>{html.escape(sentence)}</p>"
        for sentence in STOCK_CALIBRATION_CLIENT_SENTENCES
    )
    body = f"""<section class="warning"><h1>Décisions possibles et données manquantes</h1><p>Les données observées, les résultats simulés et les plans non exécutés restent séparés. Aucune devise n’est supposée, aucune probabilité fournisseur n’est calculée et aucune action n’est recommandée.</p></section>
<section><h2>OBSERVÉ — valeurs 2025</h2><div class="grid">{ca_cards}</div><h3>Stocks comptables observés</h3><table><thead><tr><th>Série</th><th>Valeur moyenne indiquée</th><th>Relevés en 2025</th><th>Limite</th></tr></thead><tbody>{stock_cards}</tbody></table></section>
<section><h2>Objectifs 93 % et 80 %</h2><p class="metric">Préparé, aucun résultat</p><p>Le plan contient {int(regime_plan['screening_candidate_count'])} configurations et définit le service à date sur les produits 268091 et 268967. Il ne démontre pas qu’une configuration atteint 93 % ou 80 % et ne remplace pas la définition de l’indicateur par l’industriel.</p></section>
<section class="warning"><h2>Point de vigilance avant de lire certains incidents fournisseurs</h2>{stock_calibration_warning}<a class="card" href="{STOCK_CALIBRATION_ASSET}"><strong>Annexe facultative — audit stock / besoin MRP</strong><br><span class="muted">Détail autonome des 24 matières et des 15 simulations; cette annexe n’est pas une quatrième vue officielle.</span></a></section>
<section><h2>Quatre leviers à tester</h2><div class="grid">{lever_cards}</div></section>
<section><h2>Données nécessaires avant une prévision fournisseur</h2><p><strong>Statut actuel : {html.escape(readiness_label)}.</strong> {html.escape(str(readiness.get('current_safe_wording') or 'Signal à instruire, pas une probabilité.'))}</p><ul><li>dates promises et dates réellement reçues par ligne de commande;</li><li>quantités commandées, reçues, rejetées et utilisables;</li><li>fournisseur, article, site, commande et ligne stables;</li><li>historique qualité : quarantaine, libération, rejet et cause d’écart;</li><li>qualification, capacité et coûts/devises validés.</li></ul></section>"""
    return _page("Décisions et données manquantes", body, current=3)


def _render_launcher() -> str:
    cards = "".join(
        f'<a class="card" href="{name}"><strong>{html.escape(label)}</strong><span>{html.escape(note)}</span></a>'
        for name, label, note in (
            (
                VIEW_FILES[0],
                "1. 338929 et risques réseau",
                "Résultats 15/30 + carte, sans classement global",
            ),
            (
                VIEW_FILES[1],
                "2. Cascade qualité et lots",
                "Exposition simulée, généalogie borne haute",
            ),
            (
                VIEW_FILES[2],
                "3. Décisions et données manquantes",
                "Observé 2025 + plans non exécutés",
            ),
        )
    )
    return f"""<!doctype html><html lang="fr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Démonstration préliminaire 15/30</title><style>body{{font:16px/1.5 system-ui,sans-serif;background:#eef3f8;color:#13233a;margin:0}}main{{max-width:1050px;margin:auto;padding:50px 20px}}.warn{{background:#fff3cd;border:2px solid #d89000;border-radius:14px;padding:18px}}.grid{{display:grid;grid-template-columns:repeat(3,1fr);gap:14px;margin-top:20px}}.card{{display:flex;flex-direction:column;gap:8px;background:white;border:1px solid #d3deeb;border-radius:14px;padding:22px;color:#13233a;text-decoration:none}}@media(max-width:800px){{.grid{{grid-template-columns:1fr}}}}</style></head><body><main><h1>Supply chain fournisseurs — préliminaire</h1><div class="warn"><strong>15 simulations sur 30.</strong> Parcours de travail, pas livrable final : aucune probabilité, aucun classement universel et aucune recommandation d’action.</div><p><strong>Comment lire les mots :</strong> <strong>OBSERVÉ</strong> décrit ce qui figure dans les fichiers industriels 2025; <strong>SIMULÉ</strong> mesure ce que le modèle produirait si le scénario se réalisait; un <strong>SIGNAL DE PRIORITÉ</strong> ouvre un dossier à instruire, sans lui attribuer une probabilité; une <strong>HYPOTHÈSE</strong> est un incident, une action ou un paramètre qui doit encore être validé.</p><p><strong>Parcours officiel : 01 → 02 → 03.</strong> Les pages détaillées et la carte proposées à l’intérieur sont des annexes interactives facultatives, pas des étapes supplémentaires.</p><div class="grid">{cards}</div></main></body></html>"""


def build_preliminary_delivery(
    *,
    preliminary_dir: Path,
    observed_dir: Path,
    quality_dir: Path,
    network_map_html: Path,
    regime_plan_dir: Path,
    action_plan_dir: Path,
    stock_calibration_audit_dir: Path,
    output_dir: Path,
) -> dict[str, Any]:
    sources = (
        preliminary_dir,
        observed_dir,
        quality_dir,
        network_map_html,
        regime_plan_dir,
        action_plan_dir,
        stock_calibration_audit_dir,
    )
    output_dir = output_dir.resolve()
    _assert_external_output(output_dir, [Path(path) for path in sources])
    if output_dir.exists():
        raise PreliminaryDeliveryError(f"Destination déjà existante: {output_dir}")
    preliminary_audit.validate_preliminary_package(preliminary_dir)
    preliminary_manifest = _read_json(
        preliminary_dir / preliminary_audit.MANIFEST_FILE
    )
    preliminary_result = _read_json(
        preliminary_dir / preliminary_audit.OUTPUT_FILES[0]
    )
    if (
        preliminary_result.get("preliminary_not_final") is not True
        or preliminary_result.get("promotion_allowed") is not False
        or preliminary_result.get("days_recovered_claimed") is not False
        or preliminary_result.get("network_recovery_metric_status")
        != "excluded_invalid_common_window"
    ):
        raise PreliminaryDeliveryError("Gardes du paquet 15/30 insuffisantes.")
    focus_network_result = _load_focus_network_result(preliminary_dir)
    observed = _validate_observed(observed_dir)
    quality_manifest, quality_page, quality_facts = _validate_quality(quality_dir)
    map_audit = _validate_map(network_map_html)
    regime_plan = _validate_regime_plan(regime_plan_dir)
    action_manifest, action_parameters = _validate_action_plan(action_plan_dir)
    (
        stock_calibration,
        stock_calibration_focus,
        stock_calibration_page,
        stock_calibration_page_audit,
    ) = _validate_stock_calibration_audit(stock_calibration_audit_dir)

    output_dir.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(
        tempfile.mkdtemp(prefix=f".{output_dir.name}.staging-", dir=output_dir.parent)
    )
    try:
        prelim_target = staging / PRELIMINARY_ASSET_DIR
        shutil.copytree(preliminary_dir, prelim_target)
        (staging / "assets").mkdir(exist_ok=True)
        shutil.copy2(quality_page, staging / QUALITY_ASSET)
        shutil.copy2(network_map_html, staging / MAP_ASSET)
        shutil.copy2(stock_calibration_page, staging / STOCK_CALIBRATION_ASSET)
        (staging / VIEW_FILES[0]).write_text(
            _render_network_view(focus_network_result), encoding="utf-8"
        )
        (staging / VIEW_FILES[1]).write_text(
            _render_quality_view(quality_facts), encoding="utf-8"
        )
        (staging / VIEW_FILES[2]).write_text(
            _render_decision_view(
                observed=observed,
                regime_plan=regime_plan,
                action_parameters=action_parameters,
                stock_calibration_focus=stock_calibration_focus,
            ),
            encoding="utf-8",
        )
        (staging / LAUNCHER_FILE).write_text(_render_launcher(), encoding="utf-8")
        source_hashes = {
            "preliminary/manifest": _sha256(
                preliminary_dir / preliminary_audit.MANIFEST_FILE
            ),
            "preliminary/audit": _sha256(
                preliminary_dir / preliminary_audit.OUTPUT_FILES[0]
            ),
            "observed/manifest": _sha256(observed_dir / "manifest.json"),
            "observed/bilan": _sha256(observed_dir / "bilan_observed_2025.json"),
            "quality/manifest": _sha256(quality_dir / "campaign_manifest.json"),
            "quality/page": _sha256(quality_page),
            "map/page": _sha256(network_map_html),
            "regime/plan": _sha256(regime_plan_dir / "calibration_plan.json"),
            "regime/inventory": _sha256(regime_plan_dir / "input_inventory.json"),
            "actions/manifest": _sha256(
                action_plan_dir / "exploratory_action_protocol_manifest.json"
            ),
            "actions/parameters": _sha256(
                action_plan_dir / "action_lever_parameters.csv"
            ),
            "actions/controls": _sha256(action_plan_dir / "scientific_controls.json"),
            "stock_calibration/manifest": _sha256(
                stock_calibration_audit_dir / stock_calibration_audit.MANIFEST_JSON
            ),
            "stock_calibration/audit": _sha256(
                stock_calibration_audit_dir / stock_calibration_audit.RESULT_JSON
            ),
            "stock_calibration/summary": _sha256(
                stock_calibration_audit_dir / stock_calibration_audit.SUMMARY_CSV
            ),
            "stock_calibration/details": _sha256(
                stock_calibration_audit_dir / stock_calibration_audit.DETAIL_CSV
            ),
            "stock_calibration/page": _sha256(stock_calibration_page),
        }
        artifact_hashes = {
            name: _sha256(staging / name)
            for name in sorted(_relative_files(staging))
        }
        signature_payload = {
            "schema_version": SCHEMA_VERSION,
            "status": "complete_preliminary_not_final",
            "builder_sha256": _sha256(Path(__file__).resolve()),
            "source_file_sha256": source_hashes,
            "artifact_file_sha256": artifact_hashes,
            "view_files": list(VIEW_FILES),
            "view_count": 3,
            "preliminary_checkpoint_signature": preliminary_manifest[
                "checkpoint_signature"
            ],
            "regime_plan_signature": regime_plan["plan_signature"],
            "action_protocol_signature": action_manifest["protocol_signature"],
            "stock_calibration_schema_version": stock_calibration["schema_version"],
            "stock_calibration_simulation_count": int(
                stock_calibration["simulation_count"]
            ),
            "stock_calibration_material_count": int(stock_calibration["material_count"]),
            "stock_calibration_major_gap_count": int(
                stock_calibration["status_counts"]["ecart_majeur_de_calibration"]
            ),
            "stock_calibration_focus_keys": [
                f"{node_id}|{item_id}"
                for node_id, item_id in sorted(stock_calibration_focus)
            ],
            "stock_calibration_warning_present": True,
            "stock_calibration_annex_offline_verified": True,
            "stock_calibration_annex_size_bytes": int(
                stock_calibration_page_audit["size_bytes"]
            ),
            "stock_calibration_annex_external_resource_count": int(
                stock_calibration_page_audit["external_resource_count"]
            ),
            "network_map_offline_verified": True,
            "network_map_size_bytes": int(map_audit["size_bytes"]),
            "network_map_external_resource_count": int(
                map_audit["external_resource_count"]
            ),
            "lighter_network_map_excluded": True,
            "lighter_network_map_exclusion_reason": (
                "external_plotly_cdn_dependency"
            ),
            "preliminary_not_final": True,
            "probability_estimated": False,
            "currency_assumed": False,
            "industrial_cost_claimed": False,
            "days_recovered_claimed": False,
            "supplier_ranking_promoted": False,
            "service_regime_results_available": False,
            "action_result_available": False,
            "action_promotion_allowed": False,
        }
        manifest = {
            **signature_payload,
            "package_signature": _canonical_sha256(signature_payload),
            "cryptographic_authentication_present": False,
            "source_artifacts_mutated": False,
            "runner_artifacts_mutated": False,
            "quality_source_mutated": False,
            "map_source_mutated": False,
            "stock_calibration_source_mutated": False,
        }
        _write_json(staging / MANIFEST_FILE, manifest)
        os.replace(staging, output_dir)
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    validate_preliminary_delivery(output_dir)
    return manifest


def validate_preliminary_delivery(root: Path) -> dict[str, Any]:
    root = root.resolve()
    manifest = _read_json(root / MANIFEST_FILE)
    expected_files = set(manifest.get("artifact_file_sha256") or {}) | {MANIFEST_FILE}
    if _relative_files(root) != expected_files:
        raise PreliminaryDeliveryError("Inventaire du livrable préliminaire non exact.")
    signature_payload = {
        key: manifest.get(key)
        for key in (
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
            "stock_calibration_schema_version",
            "stock_calibration_simulation_count",
            "stock_calibration_material_count",
            "stock_calibration_major_gap_count",
            "stock_calibration_focus_keys",
            "stock_calibration_warning_present",
            "stock_calibration_annex_offline_verified",
            "stock_calibration_annex_size_bytes",
            "stock_calibration_annex_external_resource_count",
            "network_map_offline_verified",
            "network_map_size_bytes",
            "network_map_external_resource_count",
            "lighter_network_map_excluded",
            "lighter_network_map_exclusion_reason",
            "preliminary_not_final",
            "probability_estimated",
            "currency_assumed",
            "industrial_cost_claimed",
            "days_recovered_claimed",
            "supplier_ranking_promoted",
            "service_regime_results_available",
            "action_result_available",
            "action_promotion_allowed",
        )
    }
    if (
        manifest.get("schema_version") != SCHEMA_VERSION
        or manifest.get("status") != "complete_preliminary_not_final"
        or manifest.get("builder_sha256") != _sha256(Path(__file__).resolve())
        or manifest.get("view_files") != list(VIEW_FILES)
        or manifest.get("view_count") != 3
        or manifest.get("preliminary_not_final") is not True
        or manifest.get("probability_estimated") is not False
        or manifest.get("currency_assumed") is not False
        or manifest.get("industrial_cost_claimed") is not False
        or manifest.get("days_recovered_claimed") is not False
        or manifest.get("supplier_ranking_promoted") is not False
        or manifest.get("service_regime_results_available") is not False
        or manifest.get("action_result_available") is not False
        or manifest.get("action_promotion_allowed") is not False
        or manifest.get("stock_calibration_schema_version")
        != stock_calibration_audit.SCHEMA_VERSION
        or int(manifest.get("stock_calibration_simulation_count") or 0) != 15
        or int(manifest.get("stock_calibration_material_count") or 0) != 24
        or int(manifest.get("stock_calibration_major_gap_count") or 0) != 21
        or manifest.get("stock_calibration_focus_keys")
        != ["M-1430|item:038005", "M-1810|item:049371"]
        or manifest.get("stock_calibration_warning_present") is not True
        or manifest.get("stock_calibration_annex_offline_verified") is not True
        or int(manifest.get("stock_calibration_annex_size_bytes") or 0) <= 0
        or manifest.get("stock_calibration_annex_external_resource_count") != 0
        or manifest.get("network_map_offline_verified") is not True
        or int(manifest.get("network_map_size_bytes") or 0) <= 0
        or manifest.get("network_map_external_resource_count") != 0
        or manifest.get("lighter_network_map_excluded") is not True
        or manifest.get("lighter_network_map_exclusion_reason")
        != "external_plotly_cdn_dependency"
        or manifest.get("cryptographic_authentication_present") is not False
        or manifest.get("source_artifacts_mutated") is not False
        or manifest.get("runner_artifacts_mutated") is not False
        or manifest.get("quality_source_mutated") is not False
        or manifest.get("map_source_mutated") is not False
        or manifest.get("stock_calibration_source_mutated") is not False
        or manifest.get("package_signature") != _canonical_sha256(signature_payload)
    ):
        raise PreliminaryDeliveryError("Manifeste du livrable préliminaire invalide.")
    artifacts = manifest.get("artifact_file_sha256")
    if not isinstance(artifacts, Mapping) or not artifacts:
        raise PreliminaryDeliveryError("Empreintes du livrable absentes.")
    for name, expected in artifacts.items():
        path = root / str(name)
        if not path.is_file() or _sha256(path) != str(expected):
            raise PreliminaryDeliveryError(f"Fichier du livrable altéré: {name}")
    copied_map_audit = _validate_map(root / MAP_ASSET)
    try:
        copied_stock_audit = final_package._validate_html(
            root / STOCK_CALIBRATION_ASSET, validate_navigation=False
        )
    except (OSError, UnicodeError, ValueError, RuntimeError) as error:
        raise PreliminaryDeliveryError(
            f"Annexe stock copiée invalide: {error}"
        ) from error
    sources = manifest.get("source_file_sha256")
    required_stock_source_hashes = (
        "stock_calibration/manifest",
        "stock_calibration/audit",
        "stock_calibration/summary",
        "stock_calibration/details",
        "stock_calibration/page",
    )
    if (
        not isinstance(sources, Mapping)
        or any(
            re.fullmatch(r"[0-9a-f]{64}", str(sources.get(name) or "")) is None
            for name in required_stock_source_hashes
        )
        or str(sources.get("map/page") or "") != copied_map_audit["sha256"]
        or str(artifacts.get(MAP_ASSET) or "") != copied_map_audit["sha256"]
        or int(manifest.get("network_map_size_bytes") or 0)
        != copied_map_audit["size_bytes"]
        or str(sources.get("stock_calibration/page") or "")
        != copied_stock_audit["sha256"]
        or str(artifacts.get(STOCK_CALIBRATION_ASSET) or "")
        != copied_stock_audit["sha256"]
        or int(manifest.get("stock_calibration_annex_size_bytes") or 0)
        != copied_stock_audit["size_bytes"]
        or int(copied_stock_audit.get("external_resource_count") or 0) != 0
    ):
        raise PreliminaryDeliveryError(
            "Empreinte ou taille de la carte copiée incohérente avec le manifeste."
        )
    launcher_audit = final_package._validate_html(
        root / LAUNCHER_FILE, validate_navigation=True
    )
    if launcher_audit["checked_local_navigation_link_count"] != len(VIEW_FILES):
        raise PreliminaryDeliveryError(
            "Le lanceur doit proposer exactement les trois vues officielles."
        )
    for name in VIEW_FILES:
        final_package._validate_html(root / name, validate_navigation=True)
    launcher = (root / LAUNCHER_FILE).read_text(encoding="utf-8")
    if sum(f'href="{name}"' in launcher for name in VIEW_FILES) != 3:
        raise PreliminaryDeliveryError("Le lanceur ne contient pas exactement trois vues.")
    decision = (root / VIEW_FILES[2]).read_text(encoding="utf-8")
    copied_stock_page = (root / STOCK_CALIBRATION_ASSET).read_text(encoding="utf-8")
    forbidden = ("€", "$", "probabilité fournisseur calculée", "action recommandée")
    if any(token in decision for token in forbidden):
        raise PreliminaryDeliveryError("Surpromesse ou devise inventée dans la décision.")
    required = (
        "Préparé, aucun résultat",
        "Devise non déclarée",
        "commandes livrées complètes et à l’heure",
        "données insuffisantes pour calculer une probabilité fournisseur",
        "Annexe facultative — audit stock / besoin MRP",
    )
    if (
        not all(token in decision for token in required)
        or any(decision.count(sentence) != 1 for sentence in STOCK_CALIBRATION_CLIENT_SENTENCES)
        or decision.count(f'href="{STOCK_CALIBRATION_ASSET}"') != 1
        or "ne démontre pas que la chaîne industrielle résisterait"
        not in copied_stock_page
        or "21</div>écarts majeurs" not in copied_stock_page
    ):
        raise PreliminaryDeliveryError("Limites métier absentes de la décision.")
    return manifest


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--preliminary-dir", type=Path)
    parser.add_argument("--observed-dir", type=Path)
    parser.add_argument("--quality-dir", type=Path)
    parser.add_argument("--network-map-html", type=Path)
    parser.add_argument("--regime-plan-dir", type=Path)
    parser.add_argument(
        "--stock-calibration-audit-dir",
        type=Path,
        help="Audit additif stock/besoin MRP validé sur les 15 simulations.",
    )
    parser.add_argument(
        "--action-plan-dir",
        type=Path,
        default=DEFAULT_ACTION_PLAN_DIR,
        help="Protocole V5 préparé, non exécuté (défaut: %(default)s).",
    )
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--validate-only", action="store_true")
    args = parser.parse_args(argv)
    if args.validate_only:
        validate_preliminary_delivery(args.output_dir)
        print(json.dumps({"status": "valid", "output_dir": str(args.output_dir)}))
        return 0
    missing = [
        name
        for name, value in (
            ("--preliminary-dir", args.preliminary_dir),
            ("--observed-dir", args.observed_dir),
            ("--quality-dir", args.quality_dir),
            ("--network-map-html", args.network_map_html),
            ("--regime-plan-dir", args.regime_plan_dir),
            ("--stock-calibration-audit-dir", args.stock_calibration_audit_dir),
        )
        if value is None
    ]
    if missing:
        parser.error("arguments requis: " + ", ".join(missing))
    manifest = build_preliminary_delivery(
        preliminary_dir=args.preliminary_dir,
        observed_dir=args.observed_dir,
        quality_dir=args.quality_dir,
        network_map_html=args.network_map_html,
        regime_plan_dir=args.regime_plan_dir,
        action_plan_dir=args.action_plan_dir,
        stock_calibration_audit_dir=args.stock_calibration_audit_dir,
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
