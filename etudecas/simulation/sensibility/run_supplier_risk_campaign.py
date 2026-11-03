#!/usr/bin/env python3
"""
Run a supplier risk stress campaign.

Each case activates one risk family on one supplier, then compares the result
with a campaign baseline. This is different from the passive risk score:
it measures the modeled impact of an injected event.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import shutil
import subprocess
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from etudecas.simulation.analysis_batch_common import safe_name, to_float  # noqa: E402
from etudecas.simulation.initial_state_policy import merge_living_initial_state_args  # noqa: E402
from etudecas.simulation.sensibility.run_supplier_parameter_sensitivity import (  # noqa: E402
    derived_case_kpis,
)


DEFAULT_BASELINE_RESULT_DIR = Path(
    "etudecas/simulation/result/mrp_bom_test_weekly_mps_lotified_no_fallback_physical_floor_multisource_portfolio_test"
)
DEFAULT_INPUT = Path(
    "etudecas/simulation_prep/result/reference_baseline/_mrp_bom_tests/"
    "bom_weekly_mps_lotified_no_static_fallback_physical_floor.json"
)
DEFAULT_OUTPUT_DIR = Path("etudecas/simulation/sensibility/supplier_risk_campaign_result")

RISK_FAMILIES = {
    "capacity": {
        "label": "Capacite fournisseur",
        "risk_type": "capacity",
        "multiplier": 0.50,
        "unit": "x",
        "reading": "debit fournisseur divise par deux",
    },
    "stock": {
        "label": "Stock fournisseur",
        "risk_type": "stock",
        "multiplier": 0.50,
        "unit": "x",
        "reading": "stock fournisseur accessible reduit de moitie",
    },
    "lead": {
        "label": "Delai fournisseur",
        "risk_type": "lead_time_extra_days",
        "multiplier": 30.0,
        "unit": "jours",
        "reading": "30 jours ajoutes au delai reel simule",
    },
    "reliability": {
        "label": "Fiabilite fournisseur",
        "risk_type": "reliability",
        "multiplier": 0.90,
        "unit": "x",
        "reading": "10% de perte utile sur les expeditions",
    },
    "quality": {
        "label": "Qualite / release",
        "risk_type": "quality_delay",
        "multiplier": 14.0,
        "unit": "jours",
        "reading": "14 jours de retard de liberation qualite",
    },
    "upstream": {
        "label": "Appro amont fournisseur",
        "risk_type": "external_capacity",
        "multiplier": 0.50,
        "unit": "x",
        "reading": "capacite de reappro amont fournisseur divisee par deux",
    },
    "cost": {
        "label": "Cout achat / transport",
        "risk_type": "purchase_cost",
        "multiplier": 1.50,
        "unit": "x",
        "reading": "prix achat multiplie par 1.5",
    },
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a supplier risk stress campaign.")
    parser.add_argument("--input", default=str(DEFAULT_INPUT), help="Simulation-ready graph JSON.")
    parser.add_argument(
        "--run-script",
        default="etudecas/simulation/engine/run_first_simulation.py",
        help="Simulation runner script.",
    )
    parser.add_argument("--scenario-id", default="scn:BASE", help="Scenario id.")
    parser.add_argument("--days", type=int, default=365, help="Campaign horizon in days.")
    parser.add_argument(
        "--baseline-result-dir",
        default=str(DEFAULT_BASELINE_RESULT_DIR),
        help="Existing reference result used to identify active suppliers.",
    )
    parser.add_argument(
        "--output-dir",
        default=str(DEFAULT_OUTPUT_DIR),
        help="Campaign output directory.",
    )
    parser.add_argument(
        "--families",
        default="capacity,stock,lead,reliability,quality,upstream,cost",
        help="Comma-separated risk families to test.",
    )
    parser.add_argument(
        "--top-suppliers",
        type=int,
        default=0,
        help="Limit to top N active suppliers by shipped quantity. 0 means all active suppliers.",
    )
    parser.add_argument(
        "--event-start-day",
        type=int,
        default=0,
        help="Start day of each injected event.",
    )
    parser.add_argument(
        "--event-duration-days",
        type=int,
        default=365,
        help="Duration of each injected event. Capped by --days.",
    )
    parser.add_argument("--force", action="store_true", help="Rerun cases even if summaries exist.")
    parser.add_argument(
        "--keep-case-data",
        action="store_true",
        help="Keep detailed data directories for each case.",
    )
    parser.add_argument(
        "--refresh-existing",
        action="store_true",
        help="Refresh campaign CSV/JSON/report from existing supplier_risk_campaign_cases.csv without rerunning simulations.",
    )
    return parser.parse_args()


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def active_suppliers_from_baseline(baseline_dir: Path, top_n: int = 0) -> list[str]:
    shipped_by_supplier: dict[str, float] = defaultdict(float)
    for row in read_csv_rows(baseline_dir / "data" / "production_supplier_shipments_daily.csv"):
        supplier_id = str(row.get("src_node_id") or "")
        if not supplier_id.startswith("SDC-VD"):
            continue
        shipped_by_supplier[supplier_id] += max(0.0, to_float(row.get("shipped_qty"), 0.0))

    if not shipped_by_supplier:
        for row in read_csv_rows(baseline_dir / "data" / "supplier_nominal_parameters.csv"):
            supplier_id = str(row.get("supplier_id") or "")
            if supplier_id.startswith("SDC-VD"):
                shipped_by_supplier.setdefault(supplier_id, 0.0)

    suppliers = [
        supplier_id
        for supplier_id, _qty in sorted(shipped_by_supplier.items(), key=lambda kv: (-kv[1], kv[0]))
    ]
    if top_n and top_n > 0:
        return suppliers[:top_n]
    return suppliers


def summary_path(case_dir: Path) -> Path:
    return case_dir / "summaries" / "first_simulation_summary.json"


def prune_case(case_dir: Path) -> None:
    for child in case_dir.iterdir():
        if child.name in {"summaries", "reports"}:
            continue
        if child.is_dir() and child.name in {"data", "plots", "maps"}:
            shutil.rmtree(child, ignore_errors=True)
        elif child.is_file() and child.suffix.lower() in {".csv", ".png", ".html"}:
            child.unlink(missing_ok=True)


def write_risk_event_csv(path: Path, *, supplier_id: str, family_key: str, event_start_day: int, event_end_day: int) -> dict[str, Any]:
    family = RISK_FAMILIES[family_key]
    event_id = f"campaign_{family_key}_{safe_name(supplier_id)}"
    row = {
        "event_id": event_id,
        "risk_type": family["risk_type"],
        "supplier_id": supplier_id,
        "item_id": "",
        "dst_node_id": "",
        "edge_id": "",
        "start_day": event_start_day,
        "end_day": event_end_day,
        "multiplier": family["multiplier"],
        "notes": f"Supplier risk campaign: {family['reading']}",
    }
    write_csv(
        path,
        [row],
        [
            "event_id",
            "risk_type",
            "supplier_id",
            "item_id",
            "dst_node_id",
            "edge_id",
            "start_day",
            "end_day",
            "multiplier",
            "notes",
        ],
    )
    return row


def simulator_policy_args(baseline_summary: dict[str, Any]) -> list[str]:
    policy = baseline_summary.get("policy") or {}
    out = [
        "--output-profile",
        "compact",
        "--skip-map",
        "--skip-plots",
    ]
    multisource_policy = str(policy.get("mrp_multisource_policy") or "legacy")
    out.extend(["--mrp-multisource-policy", multisource_policy])
    if policy.get("mrp_multisource_min_annual_lot_window_days") is not None:
        out.extend([
            "--mrp-multisource-min-annual-lot-window-days",
            str(int(to_float(policy.get("mrp_multisource_min_annual_lot_window_days"), 28))),
        ])
    if policy.get("mrp_target_cutover_context_days") is not None:
        out.extend([
            "--mrp-target-cutover-context-days",
            str(int(to_float(policy.get("mrp_target_cutover_context_days"), 0))),
        ])
    econ = policy.get("economic_policy") or {}
    if econ.get("external_procurement_lead_mode"):
        out.extend(["--external-procurement-lead-mode", str(econ.get("external_procurement_lead_mode"))])
    if econ.get("external_procurement_capacity_mode"):
        out.extend(["--external-procurement-capacity-mode", str(econ.get("external_procurement_capacity_mode"))])
    if econ.get("external_procurement_nominal_capacity_scale") is not None:
        out.extend([
            "--external-procurement-nominal-capacity-scale",
            str(econ.get("external_procurement_nominal_capacity_scale")),
        ])
    if econ.get("external_procurement_upstream_pipeline_fill_ratio") is not None:
        out.extend([
            "--external-procurement-upstream-pipeline-fill-ratio",
            str(econ.get("external_procurement_upstream_pipeline_fill_ratio")),
        ])
    return out


def run_simulation_case(
    *,
    run_script: Path,
    input_json: Path,
    output_dir: Path,
    scenario_id: str,
    days: int,
    risk_csv: Path | None,
    extra_args: list[str],
    force: bool,
) -> dict[str, Any]:
    if summary_path(output_dir).exists() and not force:
        return load_json(summary_path(output_dir))

    output_dir.mkdir(parents=True, exist_ok=True)
    merged_extra_args = merge_living_initial_state_args(extra_args)
    cmd = [
        sys.executable,
        str(run_script),
        "--input",
        str(input_json),
        "--output-dir",
        str(output_dir),
        "--scenario-id",
        scenario_id,
        "--days",
        str(days),
        *merged_extra_args,
    ]
    if risk_csv is not None:
        cmd.extend(["--supplier-risk-events-csv", str(risk_csv)])

    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        message = "\n".join(part for part in [proc.stdout.strip(), proc.stderr.strip()] if part)
        raise RuntimeError(f"Simulation failed for {output_dir}:\n{message}")
    return load_json(summary_path(output_dir))


def safe_ratio(numerator: float, denominator: float) -> float:
    if abs(denominator) <= 1e-12:
        return 0.0
    return numerator / denominator


def optional_number(value):
    """Une absence ou valeur non finie reste inconnue, jamais zéro."""
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def optional_delta(metrics, baseline, key, scale=1.0):
    actual, reference = optional_number(metrics.get(key)), optional_number(baseline.get(key))
    return (actual-reference)*scale if actual is not None and reference is not None else None


def optional_round(value, digits=6, scale=1.0):
    number = optional_number(value)
    return round(number*scale, digits) if number is not None else None


def extract_metrics(case_dir: Path, summary: dict[str, Any]) -> dict[str, Any]:
    kpis = summary.get("kpis") or {}
    derived = derived_case_kpis(case_dir)
    names = ("fill_rate", "ending_backlog", "total_cost", "total_holding_cost",
             "total_inventory_cost_legacy_raw_holding", "total_external_procurement_cost",
             "avg_inventory", "ending_inventory", "total_unreliable_loss_qty",
             "total_supplier_capacity_binding_qty", "total_shipped", "total_produced")
    out = {key: optional_number(kpis.get(key)) for key in names}
    out.update({f"derived_{key}": value if isinstance(value, str) else optional_number(value)
                for key, value in derived.items()})
    inventory_cost = derived.get("inventory_cost", derived.get("inventory_holding_cost_proxy_total"))
    out["derived_inventory_cost"] = optional_number(inventory_cost if inventory_cost is not None else kpis.get("total_holding_cost"))
    return out


DECISION_WEIGHTS = {
    "service": 0.22,
    "availability": 0.15,
    "adherence": 0.12,
    "backlog": 0.12,
    "replanning": 0.08,
    "nervousness": 0.06,
    "delay": 0.07,
    "stockout": 0.06,
    "cost": 0.05,
    "inventory_cost": 0.03,
    "loss": 0.02,
    "shipped": 0.02,
}

COMPONENT_LABELS = {
    "service": "Fill rate client",
    "availability": "Disponibilite produit",
    "adherence": "Adherence production",
    "backlog": "Backlog client",
    "replanning": "Replanifications",
    "nervousness": "Nervosite usine",
    "delay": "Retard matiere",
    "stockout": "Stock MP a zero",
    "cost": "Cout total",
    "inventory_cost": "Cout stock",
    "loss": "Volume utile perdu par fiabilite",
    "shipped": "Flux fournisseur expedies",
}


def clamp_unit(value: float) -> float:
    return min(1.0, max(0.0, value))


def _complete_impact_reading_from_deltas(
    *,
    fill_rate_delta_pts: float,
    availability_delta_pts: float,
    adherence_delta_pts: float,
    ending_backlog: float,
    baseline_total_shipped: float,
    production_replanning_delta: float,
    line_nervousness_delta: float,
    material_delay_days_delta: float,
    raw_material_stockout_days_delta: float,
    total_cost_delta_pct: float,
    inventory_cost_delta: float,
    baseline_inventory_cost: float,
    total_unreliable_loss_delta: float,
    total_shipped_delta: float,
) -> dict[str, Any]:
    fill_drop = max(0.0, -fill_rate_delta_pts / 100.0)
    availability_drop = max(0.0, -availability_delta_pts / 100.0)
    adherence_drop = max(0.0, -adherence_delta_pts / 100.0)
    backlog_pressure = clamp_unit(safe_ratio(max(0.0, ending_backlog), max(1.0, baseline_total_shipped * 0.01)))
    cost_increase = max(0.0, total_cost_delta_pct / 100.0)
    inventory_cost_increase = max(0.0, safe_ratio(inventory_cost_delta, max(1.0, baseline_inventory_cost)))
    replanning_increase = max(0.0, production_replanning_delta)
    nervousness_increase = max(0.0, line_nervousness_delta)
    material_delay_increase = max(0.0, material_delay_days_delta)
    stockout_increase = max(0.0, raw_material_stockout_days_delta)
    unreliable_loss = max(0.0, total_unreliable_loss_delta)
    shipped_drop = max(0.0, -total_shipped_delta)
    components = {
        "service": clamp_unit(fill_drop / 0.05),
        "availability": clamp_unit(availability_drop / 0.05),
        "adherence": clamp_unit(adherence_drop / 0.10),
        "backlog": backlog_pressure,
        "replanning": clamp_unit(replanning_increase / 200.0),
        "nervousness": clamp_unit(nervousness_increase / 500.0),
        "delay": clamp_unit(material_delay_increase / 30.0),
        "stockout": clamp_unit(stockout_increase / 30.0),
        "cost": clamp_unit(cost_increase / 0.20),
        "inventory_cost": clamp_unit(inventory_cost_increase / 0.20),
        "loss": clamp_unit(safe_ratio(unreliable_loss, max(1.0, baseline_total_shipped * 0.05))),
        "shipped": clamp_unit(safe_ratio(shipped_drop, max(1.0, baseline_total_shipped * 0.10))),
    }
    decision_score = sum(DECISION_WEIGHTS[key] * components[key] for key in DECISION_WEIGHTS)
    primary_key = max(components, key=lambda key: (components[key], DECISION_WEIGHTS.get(key, 0.0)))
    observed_score = components.get(primary_key, 0.0)
    delta_texts = {
        "service": f"{fill_rate_delta_pts:.1f} pts",
        "availability": f"{availability_delta_pts:.1f} pts",
        "adherence": f"{adherence_delta_pts:.1f} pts",
        "backlog": f"{ending_backlog:.0f}",
        "replanning": f"+{replanning_increase:.0f}",
        "nervousness": f"+{nervousness_increase:.0f}",
        "delay": f"+{material_delay_increase:.1f} j",
        "stockout": f"+{stockout_increase:.0f} j",
        "cost": f"+{cost_increase * 100.0:.1f}%",
        "inventory_cost": f"+{inventory_cost_delta:.0f}",
        "loss": f"-{unreliable_loss:.0f}",
        "shipped": f"-{shipped_drop:.0f}",
    }
    explanations: list[str] = []
    if fill_drop > 1e-9:
        explanations.append(f"fill rate -{fill_drop * 100:.1f} pts")
    if availability_drop > 1e-9:
        explanations.append(f"disponibilite -{availability_drop * 100:.1f} pts")
    if adherence_drop > 1e-9:
        explanations.append(f"adherence -{adherence_drop * 100:.1f} pts")
    if replanning_increase > 0:
        explanations.append(f"replanifications +{replanning_increase:.0f}")
    if nervousness_increase > 0:
        explanations.append(f"nervosite +{nervousness_increase:.0f}")
    if material_delay_increase > 0:
        explanations.append(f"retard matiere +{material_delay_increase:.1f} j")
    if stockout_increase > 0:
        explanations.append(f"jours stock MP zero +{stockout_increase:.0f}")
    if cost_increase > 1e-9:
        explanations.append(f"cout +{cost_increase * 100:.1f}%")
    if unreliable_loss > 0:
        explanations.append(f"volume utile perdu par fiabilite -{unreliable_loss:.0f}")
    if shipped_drop > 0:
        explanations.append(f"flux expedies -{shipped_drop:.0f}")
    cost_reading = ""
    if total_cost_delta_pct < -1e-9 and shipped_drop > 1e-9:
        cost_reading = "cout en baisse car flux/achats baissent: ne pas lire comme un gain"
    elif total_cost_delta_pct > 1e-9:
        cost_reading = "cout en hausse vs reference"
    return {
        "score_decisionnel_modele": clamp_unit(decision_score),
        "impact_metier_score": clamp_unit(observed_score),
        "impact_metier_kpi": COMPONENT_LABELS.get(primary_key, primary_key),
        "impact_metier_delta": delta_texts.get(primary_key, "n/a"),
        "impact_metier_lecture": " ; ".join(explanations) if explanations else "aucune degradation KPI visible",
        "cout_interpretation": cost_reading,
        "components": components,
    }


def impact_reading_from_deltas(**kwargs) -> dict[str, Any]:
    """Conserver les impacts connus sans fabriquer un score global complet."""
    dependencies = {
        "service": ("fill_rate_delta_pts",), "availability": ("availability_delta_pts",),
        "adherence": ("adherence_delta_pts",), "backlog": ("ending_backlog", "baseline_total_shipped"),
        "replanning": ("production_replanning_delta",), "nervousness": ("line_nervousness_delta",),
        "delay": ("material_delay_days_delta",), "stockout": ("raw_material_stockout_days_delta",),
        "cost": ("total_cost_delta_pct",), "inventory_cost": ("inventory_cost_delta", "baseline_inventory_cost"),
        "loss": ("total_unreliable_loss_delta", "baseline_total_shipped"),
        "shipped": ("total_shipped_delta", "baseline_total_shipped"),
    }
    values = {key: optional_number(kwargs.get(key)) for fields in dependencies.values() for key in fields}
    missing = [component for component, fields in dependencies.items() if any(values[f] is None for f in fields)]
    # The complete formula is reused only for the components whose arguments
    # are known. Neutral placeholders below are discarded for missing components.
    reading = _complete_impact_reading_from_deltas(**{key: value if value is not None else 0.0 for key, value in values.items()})
    for component in missing:
        reading["components"][component] = None
    known = {key: value for key, value in reading["components"].items() if value is not None}
    primary = max(known, key=lambda key: (known[key], DECISION_WEIGHTS[key])) if known else None
    if missing:
        reading["score_decisionnel_modele"] = None
        reading["impact_metier_score"] = known[primary] if primary is not None else None
        same_primary = primary is not None and reading['impact_metier_kpi'] == COMPONENT_LABELS[primary]
        reading["impact_metier_kpi"] = COMPONENT_LABELS[primary] if primary is not None else "non évaluable"
        if not same_primary:
            reading["impact_metier_delta"] = "composante connue ; lecture partielle" if primary else "inconnu"
        reading["impact_metier_lecture"] += " ; lecture partielle, composantes inconnues : " + ", ".join(missing)
    reading["assessment_status"] = "donnees_insuffisantes" if missing else "evaluable"
    reading["impact_metier_status"] = "partiel" if missing and known else ("inconnu" if missing else "complet")
    reading["missing_components"] = missing
    return reading


def impact_reading_from_metrics(metrics: dict[str, Any], baseline: dict[str, Any]) -> dict[str, Any]:
    cost_delta = optional_delta(metrics, baseline, "total_cost")
    base_cost = optional_number(baseline.get("total_cost"))
    return impact_reading_from_deltas(
        fill_rate_delta_pts=optional_delta(metrics, baseline, "fill_rate", 100),
        availability_delta_pts=optional_delta(metrics, baseline, "derived_product_availability", 100),
        adherence_delta_pts=optional_delta(metrics, baseline, "derived_line_adherence", 100),
        ending_backlog=metrics.get("ending_backlog"), baseline_total_shipped=baseline.get("total_shipped"),
        production_replanning_delta=optional_delta(metrics, baseline, "derived_production_replanning_count"),
        line_nervousness_delta=optional_delta(metrics, baseline, "derived_line_nervousness"),
        material_delay_days_delta=optional_delta(metrics, baseline, "derived_material_delay_days"),
        raw_material_stockout_days_delta=optional_delta(metrics, baseline, "derived_raw_material_stockout_days"),
        total_cost_delta_pct=cost_delta/max(1.0,base_cost)*100 if cost_delta is not None and base_cost is not None else None,
        inventory_cost_delta=optional_delta(metrics, baseline, "derived_inventory_cost"),
        baseline_inventory_cost=baseline.get("derived_inventory_cost"),
        total_unreliable_loss_delta=optional_delta(metrics, baseline, "total_unreliable_loss_qty"),
        total_shipped_delta=optional_delta(metrics, baseline, "total_shipped"))


def enrich_existing_case_row(row: dict[str, Any]) -> dict[str, Any]:
    shipped, shipped_delta = optional_number(row.get("total_shipped")), optional_number(row.get("total_shipped_delta"))
    inventory, inventory_delta = optional_number(row.get("inventory_cost")), optional_number(row.get("inventory_cost_delta"))
    reading = impact_reading_from_deltas(
        fill_rate_delta_pts=row.get("fill_rate_delta_pts"), availability_delta_pts=row.get("product_availability_delta_pts"),
        adherence_delta_pts=row.get("line_adherence_delta_pts"), ending_backlog=row.get("ending_backlog"),
        baseline_total_shipped=shipped-shipped_delta if shipped is not None and shipped_delta is not None else None,
        production_replanning_delta=row.get("production_replanning_delta"), line_nervousness_delta=row.get("line_nervousness_delta"),
        material_delay_days_delta=row.get("material_delay_days_delta"), raw_material_stockout_days_delta=row.get("raw_material_stockout_days_delta"),
        total_cost_delta_pct=row.get("total_cost_delta_pct"), inventory_cost_delta=inventory_delta,
        baseline_inventory_cost=inventory-inventory_delta if inventory is not None and inventory_delta is not None else None,
        total_unreliable_loss_delta=row.get("total_unreliable_loss_delta"), total_shipped_delta=shipped_delta)
    enriched = dict(row)
    for key in enriched:
        if key.endswith(('_delta', '_delta_pts', '_delta_pct')) or key in (
                'line_nervousness', 'production_replanning_count', 'line_adherence'):
            enriched[key] = optional_number(enriched[key])
    for key in ("assessment_status", "missing_components", "impact_metier_status", "impact_metier_kpi",
                "impact_metier_delta", "impact_metier_lecture", "cout_interpretation"):
        enriched[key] = reading[key]
    score, observed = reading["score_decisionnel_modele"], reading["impact_metier_score"]
    for key in ("score_decisionnel_modele", "impact_score"):
        enriched[key] = optional_round(score, 9)
    for key in ("score_decisionnel_pct", "impact_pct"):
        enriched[key] = optional_round(score, 4, 100)
    enriched["impact_metier_score"] = optional_round(observed, 9)
    enriched["impact_metier_pct"] = optional_round(observed, 4, 100)
    enriched["impact_explanation"] = reading["impact_metier_lecture"]
    return enriched


def case_row(*, supplier_id: str, family_key: str, case_id: str,
             event_row: dict[str, Any] | None, metrics: dict[str, Any],
             baseline_metrics: dict[str, Any], case_dir: Path) -> dict[str, Any]:
    family = RISK_FAMILIES.get(family_key, {})
    row = dict(case_id=case_id, supplier_id=supplier_id, risk_family=family_key,
        risk_family_label=family.get("label",family_key), risk_type=(event_row or {}).get("risk_type","baseline"),
        multiplier=(event_row or {}).get("multiplier",""), event_start_day=(event_row or {}).get("start_day",""),
        event_end_day=(event_row or {}).get("end_day",""), case_dir=str(case_dir))
    fields = {"fill_rate":"fill_rate", "ending_backlog":"ending_backlog", "product_availability":"derived_product_availability",
        "line_adherence":"derived_line_adherence", "line_nervousness":"derived_line_nervousness",
        "production_replanning_count":"derived_production_replanning_count", "raw_material_stockout_days":"derived_raw_material_stockout_days",
        "material_delay_days":"derived_material_delay_days", "total_cost":"total_cost", "inventory_cost":"derived_inventory_cost",
        "total_unreliable_loss_qty":"total_unreliable_loss_qty", "total_shipped":"total_shipped"}
    for output, source in fields.items():
        row[output] = optional_number(metrics.get(source))
    deltas = {"fill_rate_delta_pts":("fill_rate",100), "product_availability_delta_pts":("derived_product_availability",100),
        "line_adherence_delta_pts":("derived_line_adherence",100), "line_nervousness_delta":("derived_line_nervousness",1),
        "production_replanning_delta":("derived_production_replanning_count",1),
        "raw_material_stockout_days_delta":("derived_raw_material_stockout_days",1), "material_delay_days_delta":("derived_material_delay_days",1),
        "total_cost_delta":("total_cost",1), "inventory_cost_delta":("derived_inventory_cost",1),
        "total_unreliable_loss_delta":("total_unreliable_loss_qty",1), "total_shipped_delta":("total_shipped",1)}
    for output,(source,scale) in deltas.items():
        row[output] = optional_round(optional_delta(metrics,baseline_metrics,source,scale))
    base_cost = optional_number(baseline_metrics.get("total_cost"))
    row["total_cost_delta_pct"] = optional_round(row["total_cost_delta"]/max(1.0,base_cost)*100 if row["total_cost_delta"] is not None and base_cost is not None else None)
    return enrich_existing_case_row(row)


def summarize_by_supplier(case_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped = defaultdict(list)
    for row in case_rows:
        if row.get("risk_family") != "baseline":
            grouped[str(row.get("supplier_id") or "")].append(enrich_existing_case_row(row))
    output = []
    for supplier, rows in sorted(grouped.items()):
        known = [row for row in rows if row["assessment_status"]=="evaluable"]
        complete = len(known)==len(rows)
        worst_known = max(known,key=lambda row:row["score_decisionnel_modele"]) if known else {}
        worst = worst_known if complete else {}
        observed = [r for r in rows if r.get("impact_metier_score") is not None]
        physical = max(observed,key=lambda r:r["impact_metier_score"]) if observed else {}
        result = dict(supplier_id=supplier,assessment_status="evaluable" if complete else "donnees_insuffisantes",
            missing_components=sorted({key for r in rows for key in r["missing_components"]}),tested_family_count=len(rows),
            evaluable_family_count=len(known),rank=None,worst_risk_family=worst.get("risk_family"),
            worst_risk_family_label=worst.get("risk_family_label"),worst_risk_type=worst.get("risk_type"),
            worst_known_risk_family=worst_known.get("risk_family"),worst_known_score_decisionnel_modele=worst_known.get("score_decisionnel_modele"),
            known_impact_metier_family=physical.get("risk_family"),known_impact_metier_score=physical.get("impact_metier_score"),
            known_impact_metier_kpi=physical.get("impact_metier_kpi"),known_impact_metier_lecture=physical.get("impact_metier_lecture"))
        for key in ("impact_score","impact_pct","impact_explanation","score_decisionnel_modele","score_decisionnel_pct",
                    "impact_metier_score","impact_metier_pct","impact_metier_kpi","impact_metier_delta","impact_metier_lecture","cout_interpretation"):
            result['worst_'+key]=worst.get(key)
        for family in ("capacity","stock","lead","reliability","quality","upstream","cost"):
            cases=[r for r in rows if r['risk_family']==family]
            scores=[r['score_decisionnel_modele'] for r in cases if r['score_decisionnel_modele'] is not None]
            result[family+'_impact_pct']=optional_round(max(scores),4,100) if cases and len(scores)==len(cases) else None
        output.append(result)
    # A supplier with missing families cannot be ranked against complete ones.
    if output and all(r['assessment_status']=='evaluable' for r in output):
        output.sort(key=lambda r:(-r['worst_score_decisionnel_modele'],r['supplier_id']))
        for rank,row in enumerate(output,1):row['rank']=rank
    return output


def write_report(output_dir: Path, summary_rows: list[dict[str, Any]], case_rows: list[dict[str, Any]], metadata: dict[str, Any]) -> None:
    lines = [
        "# Supplier Risk Campaign",
        "",
        f"- Generated: {metadata['generated_at']}",
        f"- Horizon: {metadata['days']} days",
        f"- Suppliers tested: {metadata['supplier_count']}",
        f"- Families tested: {', '.join(metadata['families'])}",
        f"- Cases: {len(case_rows) - 1} stress cases + 1 baseline",
        "",
        "## Top supplier decision scores",
        "",
        "| Rank | Supplier | Worst risk | Decision score | Main observed KPI | Observed reading |",
        "|---:|---|---|---:|---|---|",
    ]
    for row in summary_rows[:20]:
        lines.append(
            "| {rank} | {supplier_id} | {risk} | {score} | {kpi} | {why} |".format(
                rank=row.get("rank"),
                supplier_id=row.get("supplier_id"),
                risk=row.get("worst_risk_family_label"),
                score=(f"{row['worst_score_decisionnel_pct']:.1f}%" if optional_number(row.get("worst_score_decisionnel_pct")) is not None else "non évaluable"),
                kpi=str(row.get("worst_impact_metier_kpi") or row.get("known_impact_metier_kpi") or "n/a").replace("|", "/"),
                why=str(row.get("worst_impact_metier_lecture") or row.get("known_impact_metier_lecture") or row.get("worst_impact_explanation") or "non évaluable").replace("|", "/"),
            )
        )
    lines.extend(
        [
            "",
            "## Lecture",
            "",
            "Cette campagne active un seul risque a la fois sur un seul fournisseur.",
            "",
            "- Impact metier observe: KPI bruts qui bougent dans le modele (service, disponibilite, adherence, backlog, nervosite, cout, flux).",
            "- Score decisionnel modele: synthese ponderee provisoire des degradations normalisees, a calibrer avec les industriels.",
            "- Ce n'est pas une probabilite terrain et ce n'est pas un risque reel sans probabilite d'occurrence.",
            "",
            "Les familles testees sont: capacite, stock, delai, fiabilite, qualite, appro amont et cout.",
        ]
    )
    (output_dir / "supplier_risk_campaign_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def refresh_existing_outputs(output_dir: Path) -> None:
    cases_path = output_dir / "supplier_risk_campaign_cases.csv"
    if not cases_path.exists():
        raise SystemExit(f"Missing existing cases CSV: {cases_path}")
    case_rows = [enrich_existing_case_row(row) for row in read_csv_rows(cases_path)]
    summary_rows = summarize_by_supplier(case_rows)
    existing_json = output_dir / "supplier_risk_campaign_summary.json"
    metadata: dict[str, Any] = {}
    if existing_json.exists():
        try:
            metadata = (load_json(existing_json).get("metadata") or {})
        except Exception:
            metadata = {}
    metadata.setdefault("generated_at", datetime.now(timezone.utc).isoformat())
    metadata["refreshed_at"] = datetime.now(timezone.utc).isoformat()
    metadata["case_count"] = len(case_rows)
    metadata["reading"] = {
        "impact_metier_observe": "KPI bruts observes vs reference.",
        "score_decisionnel_modele": "Synthese ponderee provisoire des degradations normalisees.",
    }
    write_csv(output_dir / "supplier_risk_campaign_cases.csv", case_rows, list(case_rows[0].keys()) if case_rows else [])
    write_csv(output_dir / "supplier_risk_campaign_summary.csv", summary_rows, list(summary_rows[0].keys()) if summary_rows else [])
    write_json(
        output_dir / "supplier_risk_campaign_summary.json",
        {
            "metadata": metadata,
            "summary": summary_rows,
            "cases": case_rows,
        },
    )
    write_report(output_dir, summary_rows, case_rows, metadata)


def main() -> None:
    args = parse_args()
    input_json = Path(args.input)
    run_script = Path(args.run_script)
    baseline_dir = Path(args.baseline_result_dir)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    if args.refresh_existing:
        refresh_existing_outputs(output_dir)
        print(f"[OK] Supplier risk campaign refreshed from existing cases in {output_dir.resolve()}")
        return
    cases_dir = output_dir / "cases"
    events_dir = output_dir / "events"
    cases_dir.mkdir(parents=True, exist_ok=True)
    events_dir.mkdir(parents=True, exist_ok=True)

    families = [part.strip() for part in str(args.families or "").split(",") if part.strip()]
    unknown = [family for family in families if family not in RISK_FAMILIES]
    if unknown:
        raise SystemExit(f"Unknown families: {', '.join(unknown)}")

    baseline_summary_path = baseline_dir / "summaries" / "first_simulation_summary.json"
    baseline_reference_summary = load_json(baseline_summary_path) if baseline_summary_path.exists() else {}
    extra_args = simulator_policy_args(baseline_reference_summary)

    suppliers = active_suppliers_from_baseline(baseline_dir, args.top_suppliers)
    if not suppliers:
        raise SystemExit(f"No active suppliers found in {baseline_dir}")

    campaign_baseline_dir = cases_dir / "baseline"
    baseline_summary = run_simulation_case(
        run_script=run_script,
        input_json=input_json,
        output_dir=campaign_baseline_dir,
        scenario_id=args.scenario_id,
        days=args.days,
        risk_csv=None,
        extra_args=extra_args,
        force=args.force,
    )
    baseline_metrics = extract_metrics(campaign_baseline_dir, baseline_summary)

    case_rows: list[dict[str, Any]] = [
        case_row(
            supplier_id="__all__",
            family_key="baseline",
            case_id="baseline",
            event_row=None,
            metrics=baseline_metrics,
            baseline_metrics=baseline_metrics,
            case_dir=campaign_baseline_dir,
        )
    ]

    event_start = max(0, int(args.event_start_day))
    event_end = min(max(event_start, args.days - 1), event_start + max(1, int(args.event_duration_days)) - 1)
    for supplier_id in suppliers:
        for family_key in families:
            case_id = f"{safe_name(supplier_id)}__{family_key}"
            case_dir = cases_dir / case_id
            event_csv = events_dir / f"{case_id}.csv"
            event_row = write_risk_event_csv(
                event_csv,
                supplier_id=supplier_id,
                family_key=family_key,
                event_start_day=event_start,
                event_end_day=event_end,
            )
            print(f"[RUN] {case_id}", flush=True)
            summary = run_simulation_case(
                run_script=run_script,
                input_json=input_json,
                output_dir=case_dir,
                scenario_id=args.scenario_id,
                days=args.days,
                risk_csv=event_csv,
                extra_args=extra_args,
                force=args.force,
            )
            metrics = extract_metrics(case_dir, summary)
            case_rows.append(
                case_row(
                    supplier_id=supplier_id,
                    family_key=family_key,
                    case_id=case_id,
                    event_row=event_row,
                    metrics=metrics,
                    baseline_metrics=baseline_metrics,
                    case_dir=case_dir,
                )
            )
            if not args.keep_case_data:
                prune_case(case_dir)

    if not args.keep_case_data:
        prune_case(campaign_baseline_dir)

    summary_rows = summarize_by_supplier(case_rows)
    case_fieldnames = list(case_rows[0].keys())
    summary_fieldnames = list(summary_rows[0].keys()) if summary_rows else []
    write_csv(output_dir / "supplier_risk_campaign_cases.csv", case_rows, case_fieldnames)
    write_csv(output_dir / "supplier_risk_campaign_summary.csv", summary_rows, summary_fieldnames)

    metadata = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "input": str(input_json),
        "baseline_result_dir": str(baseline_dir),
        "days": args.days,
        "event_start_day": event_start,
        "event_end_day": event_end,
        "supplier_count": len(suppliers),
        "suppliers": suppliers,
        "families": families,
        "risk_family_definitions": RISK_FAMILIES,
        "baseline_metrics": baseline_metrics,
        "case_count": len(case_rows),
    }
    write_json(
        output_dir / "supplier_risk_campaign_summary.json",
        {
            "metadata": metadata,
            "summary": summary_rows,
            "cases": case_rows,
        },
    )
    write_report(output_dir, summary_rows, case_rows, metadata)
    print(f"[OK] Supplier risk campaign written to {output_dir.resolve()}")


if __name__ == "__main__":
    main()
