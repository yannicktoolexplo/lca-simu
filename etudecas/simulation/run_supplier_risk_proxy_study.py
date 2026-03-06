#!/usr/bin/env python3
"""
Extended proxy supplier-material risk study.

This script does not claim empirical prediction. It builds a provisional
"probability x impact" view from:
- observed network structure and baseline simulation outputs,
- targeted pair-level disruption simulations,
- explicit proxy mappings for incident probabilities.
"""

from __future__ import annotations

import copy
import csv
import json
import math
from collections import defaultdict
from pathlib import Path
from typing import Any

from analysis_batch_common import load_json, numeric_kpis, run_simulation, write_json


ROOT = Path(__file__).resolve().parent
RUN_SCRIPT = ROOT / "run_first_simulation.py"
BASE_INPUT = ROOT / "result" / "model_assumption_review" / "cases" / "baseline_gaillac" / "input_case.json"
CRITICAL_MATERIALS = ROOT / "result" / "critical_input_materials_analysis.csv"
OUT_DIR = ROOT / "result" / "supplier_risk_proxy_study"


def to_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def safe_slug(value: str) -> str:
    out = []
    for ch in str(value):
        if ch.isalnum():
            out.append(ch)
        else:
            out.append("_")
    return "".join(out).strip("_")


def parse_csv(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def choose_scenario(data: dict[str, Any]) -> dict[str, Any]:
    scenarios = data.get("scenarios") or []
    return scenarios[0] if scenarios else {}


def find_edge(data: dict[str, Any], edge_id: str) -> dict[str, Any]:
    for edge in data.get("edges") or []:
        if str(edge.get("id")) == edge_id:
            return edge
    raise KeyError(f"Unknown edge {edge_id}")


def set_lane_outage(data: dict[str, Any], edge_id: str, start_day: int, end_day: int, multiplier: float = 0.0) -> None:
    edge = find_edge(data, edge_id)
    edge["availability_profile"] = [
        {"start_day": int(start_day), "end_day": int(end_day), "multiplier": float(multiplier)}
    ]


def scale_edge_lead(data: dict[str, Any], edge_id: str, factor: float) -> None:
    edge = find_edge(data, edge_id)
    lead = edge.setdefault("lead_time", {})
    lead["mean"] = round(max(0.05, to_float(lead.get("mean"), 1.0) * factor), 6)
    if "min" in lead:
        lead["min"] = round(max(0.05, to_float(lead.get("min"), 0.0) * factor), 6)
    if "max" in lead:
        lead["max"] = round(max(0.05, to_float(lead.get("max"), 0.0) * factor), 6)


def scale_edge_otif(data: dict[str, Any], edge_id: str, factor: float) -> None:
    edge = find_edge(data, edge_id)
    service_level = edge.get("service_level") or {}
    base = to_float(service_level.get("otif", edge.get("otif", 1.0)), 1.0)
    service_level["otif"] = round(clamp(base * factor, 0.01, 1.0), 6)
    edge["service_level"] = service_level


def demand_totals_by_item(data: dict[str, Any]) -> dict[str, float]:
    scn = choose_scenario(data)
    out: dict[str, float] = defaultdict(float)
    for demand in scn.get("demand") or []:
        item_id = str(demand.get("item_id"))
        for profile in demand.get("profile") or []:
            ptype = str(profile.get("type", "constant")).lower()
            if ptype in {"constant", "step"}:
                out[item_id] += to_float(profile.get("value"))
            elif ptype == "piecewise":
                for point in profile.get("points") or []:
                    out[item_id] += to_float(point.get("value"))
    return dict(out)


def build_bom_maps(data: dict[str, Any]) -> tuple[dict[tuple[str, str], list[str]], dict[str, list[str]]]:
    item_to_outputs: dict[tuple[str, str], list[str]] = defaultdict(list)
    output_to_inputs: dict[str, list[str]] = defaultdict(list)
    for node in data.get("nodes") or []:
        node_id = str(node.get("id"))
        for proc in node.get("processes") or []:
            outputs = []
            for out_spec in proc.get("outputs") or []:
                out_item = str(out_spec.get("item_id"))
                outputs.append(out_item)
            inputs = [str(inp.get("item_id")) for inp in (proc.get("inputs") or [])]
            for out_item in outputs:
                output_to_inputs[out_item].extend(inputs)
            for inp in inputs:
                item_to_outputs[(node_id, inp)].extend(outputs)
    return item_to_outputs, output_to_inputs


def load_critical_by_pair() -> dict[tuple[str, str], dict[str, Any]]:
    rows = parse_csv(CRITICAL_MATERIALS)
    by_pair: dict[tuple[str, str], dict[str, Any]] = {}
    for row in rows:
        item_id = str(row["item"])
        if not item_id.startswith("item:"):
            item_id = f"item:{item_id}"
        by_pair[(str(row["node"]), item_id)] = row
    return by_pair


def normalize(values: dict[str, float], higher_is_riskier: bool = True, floor: float = 0.0) -> dict[str, float]:
    clean = {k: max(floor, to_float(v)) for k, v in values.items()}
    if not clean:
        return {}
    lo = min(clean.values())
    hi = max(clean.values())
    if hi - lo <= 1e-12:
        return {k: 0.5 for k in clean}
    out = {k: (v - lo) / (hi - lo) for k, v in clean.items()}
    if higher_is_riskier:
        return out
    return {k: 1.0 - v for k, v in out.items()}


def probability_band(prob: float) -> str:
    if prob >= 0.14:
        return "very_high"
    if prob >= 0.10:
        return "high"
    if prob >= 0.06:
        return "medium"
    if prob >= 0.03:
        return "low"
    return "very_low"


def pair_key(supplier_id: str, item_id: str, node_id: str) -> str:
    return f"{supplier_id}|{item_id}|{node_id}"


def build_supplier_material_pairs(base_data: dict[str, Any]) -> list[dict[str, Any]]:
    node_types = {str(node.get("id")): str(node.get("type")) for node in base_data.get("nodes") or []}
    node_names = {str(node.get("id")): str(node.get("name", node.get("id"))) for node in base_data.get("nodes") or []}
    pair_meta: list[dict[str, Any]] = []
    for edge in base_data.get("edges") or []:
        src = str(edge.get("from"))
        dst = str(edge.get("to"))
        if node_types.get(src) != "supplier_dc" or node_types.get(dst) != "factory":
            continue
        items = edge.get("items") or []
        if len(items) != 1:
            continue
        item_id = str(items[0])
        pair_meta.append(
            {
                "edge_id": str(edge.get("id")),
                "supplier_id": src,
                "supplier_name": node_names.get(src, src),
                "factory_id": dst,
                "factory_name": node_names.get(dst, dst),
                "item_id": item_id,
                "lead_mean_days": to_float((edge.get("lead_time") or {}).get("mean"), 0.0),
                "otif": to_float(((edge.get("service_level") or {}).get("otif")), 1.0),
                "uom": str(((edge.get("order_terms") or {}).get("quantity_unit")) or ""),
                "is_assumed_edge": bool(edge.get("is_assumed")),
                "assumption_label": str(edge.get("assumption_label", "")),
            }
        )
    return pair_meta


def run_case(case_data: dict[str, Any], case_dir: Path) -> dict[str, Any]:
    input_path = case_dir / "input_case.json"
    output_dir = case_dir / "simulation_output"
    write_json(input_path, case_data)
    summary, _ = run_simulation(RUN_SCRIPT, input_path, output_dir, "scn:BASE", days=30, skip_map=True, skip_plots=True)
    row = {k: round(v, 6) for k, v in numeric_kpis(summary).items()}
    row["output_dir"] = str(output_dir)
    return row


def build_rows() -> tuple[list[dict[str, Any]], dict[str, Any], list[dict[str, Any]]]:
    base_data = load_json(BASE_INPUT)
    pair_meta = build_supplier_material_pairs(base_data)
    critical_by_pair = load_critical_by_pair()
    demand_totals = demand_totals_by_item(base_data)
    item_to_outputs, _ = build_bom_maps(base_data)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    runs_dir = OUT_DIR / "cases"
    runs_dir.mkdir(parents=True, exist_ok=True)

    baseline_summary = run_case(copy.deepcopy(base_data), runs_dir / "baseline")
    results: list[dict[str, Any]] = []

    for pair in pair_meta:
        item_id = pair["item_id"]
        factory_id = pair["factory_id"]
        supplier_id = pair["supplier_id"]
        edge_id = pair["edge_id"]
        pkey = pair_key(supplier_id, item_id, factory_id)
        critical = critical_by_pair.get((factory_id, item_id), {})
        outputs = sorted(set(item_to_outputs.get((factory_id, item_id), [])))
        downstream_demand = sum(demand_totals.get(out, 0.0) for out in outputs)

        outage_data = copy.deepcopy(base_data)
        set_lane_outage(outage_data, edge_id, 5, 9, 0.0)
        outage_row = run_case(outage_data, runs_dir / f"{safe_slug(edge_id)}__outage5d")

        delay_data = copy.deepcopy(base_data)
        scale_edge_lead(delay_data, edge_id, 3.0)
        delay_row = run_case(delay_data, runs_dir / f"{safe_slug(edge_id)}__delayx3")

        otif_data = copy.deepcopy(base_data)
        scale_edge_otif(otif_data, edge_id, 0.5)
        otif_row = run_case(otif_data, runs_dir / f"{safe_slug(edge_id)}__otif50")

        results.append(
            {
                "pair_key": pkey,
                **pair,
                "supplier_count_for_item": int(to_float(critical.get("suppliers"), 1.0)),
                "criticality_score": to_float(critical.get("criticality_score")),
                "cover_days": to_float(critical.get("cover_days")),
                "total_consumed": to_float(critical.get("total_consumed")),
                "avg_cons_per_day": to_float(critical.get("avg_cons_per_day")),
                "downstream_outputs": ", ".join(outputs),
                "downstream_demand_total": downstream_demand,
                "outage5d_fill_rate": to_float(outage_row.get("fill_rate")),
                "outage5d_backlog": to_float(outage_row.get("ending_backlog")),
                "outage5d_total_cost": to_float(outage_row.get("total_cost")),
                "delayx3_fill_rate": to_float(delay_row.get("fill_rate")),
                "delayx3_backlog": to_float(delay_row.get("ending_backlog")),
                "delayx3_total_cost": to_float(delay_row.get("total_cost")),
                "otif50_fill_rate": to_float(otif_row.get("fill_rate")),
                "otif50_backlog": to_float(otif_row.get("ending_backlog")),
                "otif50_total_cost": to_float(otif_row.get("total_cost")),
                "baseline_fill_rate": to_float(baseline_summary.get("fill_rate")),
                "baseline_backlog": to_float(baseline_summary.get("ending_backlog")),
                "baseline_total_cost": to_float(baseline_summary.get("total_cost")),
            }
        )
    return results, baseline_summary, pair_meta


def compute_scores(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    supplier_count_values = {r["pair_key"]: float(r["supplier_count_for_item"]) for r in rows}
    demand_values = {r["pair_key"]: to_float(r["downstream_demand_total"]) for r in rows}
    volume_values = {r["pair_key"]: math.log1p(max(0.0, to_float(r["total_consumed"]))) for r in rows}
    cover_values = {r["pair_key"]: to_float(r["cover_days"]) for r in rows}
    lead_values = {r["pair_key"]: to_float(r["lead_mean_days"]) for r in rows}
    critical_values = {r["pair_key"]: to_float(r["criticality_score"]) for r in rows}

    demand_norm = normalize(demand_values, higher_is_riskier=True)
    volume_norm = normalize(volume_values, higher_is_riskier=True)
    cover_risk_norm = normalize(cover_values, higher_is_riskier=False)
    lead_norm = normalize(lead_values, higher_is_riskier=True)
    critical_norm = normalize(critical_values, higher_is_riskier=True)

    outage_fill_loss = {
        r["pair_key"]: max(0.0, to_float(r["baseline_fill_rate"]) - to_float(r["outage5d_fill_rate"])) for r in rows
    }
    delay_fill_loss = {
        r["pair_key"]: max(0.0, to_float(r["baseline_fill_rate"]) - to_float(r["delayx3_fill_rate"])) for r in rows
    }
    otif_fill_loss = {
        r["pair_key"]: max(0.0, to_float(r["baseline_fill_rate"]) - to_float(r["otif50_fill_rate"])) for r in rows
    }
    outage_backlog_delta = {
        r["pair_key"]: max(0.0, to_float(r["outage5d_backlog"]) - to_float(r["baseline_backlog"])) for r in rows
    }
    delay_backlog_delta = {
        r["pair_key"]: max(0.0, to_float(r["delayx3_backlog"]) - to_float(r["baseline_backlog"])) for r in rows
    }
    otif_backlog_delta = {
        r["pair_key"]: max(0.0, to_float(r["otif50_backlog"]) - to_float(r["baseline_backlog"])) for r in rows
    }

    expected_fill_loss = {}
    expected_backlog_delta = {}
    for row in rows:
        key = row["pair_key"]
        expected_fill_loss[key] = 0.25 * outage_fill_loss[key] + 0.45 * delay_fill_loss[key] + 0.30 * otif_fill_loss[key]
        expected_backlog_delta[key] = (
            0.25 * outage_backlog_delta[key] + 0.45 * delay_backlog_delta[key] + 0.30 * otif_backlog_delta[key]
        )

    expected_fill_norm = normalize(expected_fill_loss, higher_is_riskier=True)
    expected_backlog_norm = normalize(expected_backlog_delta, higher_is_riskier=True)

    out: list[dict[str, Any]] = []
    for row in rows:
        key = row["pair_key"]
        supplier_count = int(to_float(row["supplier_count_for_item"], 1.0))
        mono_source_risk = {1: 1.0, 2: 0.6, 3: 0.3, 4: 0.15}.get(supplier_count, 0.05)
        uncertainty_penalty = 0.0
        if row["item_id"] == "item:693710":
            uncertainty_penalty = 1.0
        elif row["item_id"] == "item:730384":
            uncertainty_penalty = 0.6
        elif row["is_assumed_edge"]:
            uncertainty_penalty = 0.7

        structural_proxy = (
            0.30 * mono_source_risk
            + 0.18 * demand_norm.get(key, 0.0)
            + 0.18 * volume_norm.get(key, 0.0)
            + 0.14 * cover_risk_norm.get(key, 0.0)
            + 0.10 * lead_norm.get(key, 0.0)
            + 0.05 * critical_norm.get(key, 0.0)
            + 0.05 * uncertainty_penalty
        )

        impact_proxy = (
            0.55 * expected_fill_norm.get(key, 0.0)
            + 0.45 * expected_backlog_norm.get(key, 0.0)
        )

        p_incident_30d_proxy = 0.02 + 0.14 * structural_proxy
        p_service_hit_30d_proxy = clamp(
            p_incident_30d_proxy * impact_proxy,
            0.0,
            0.95,
        )
        p_major_service_hit_30d_proxy = clamp(
            p_incident_30d_proxy * clamp(expected_fill_loss.get(key, 0.0) / 0.05, 0.0, 1.0),
            0.0,
            0.95,
        )
        combined_proxy_risk = 0.45 * structural_proxy + 0.55 * impact_proxy
        expected_fill_loss_30d_proxy = p_incident_30d_proxy * expected_fill_loss.get(key, 0.0)
        expected_backlog_30d_proxy = p_incident_30d_proxy * expected_backlog_delta.get(key, 0.0)

        row = dict(row)
        row.update(
            {
                "mono_source_risk": round(mono_source_risk, 6),
                "demand_exposure_norm": round(demand_norm.get(key, 0.0), 6),
                "volume_exposure_norm": round(volume_norm.get(key, 0.0), 6),
                "cover_risk_norm": round(cover_risk_norm.get(key, 0.0), 6),
                "lead_time_risk_norm": round(lead_norm.get(key, 0.0), 6),
                "criticality_norm": round(critical_norm.get(key, 0.0), 6),
                "uncertainty_penalty": round(uncertainty_penalty, 6),
                "outage5d_fill_loss": round(outage_fill_loss[key], 6),
                "delayx3_fill_loss": round(delay_fill_loss[key], 6),
                "otif50_fill_loss": round(otif_fill_loss[key], 6),
                "outage5d_backlog_delta": round(outage_backlog_delta[key], 6),
                "delayx3_backlog_delta": round(delay_backlog_delta[key], 6),
                "otif50_backlog_delta": round(otif_backlog_delta[key], 6),
                "expected_fill_loss_proxy": round(expected_fill_loss[key], 6),
                "expected_backlog_delta_proxy": round(expected_backlog_delta[key], 6),
                "structural_proxy_score": round(structural_proxy, 6),
                "impact_proxy_score": round(impact_proxy, 6),
                "combined_proxy_risk_score": round(combined_proxy_risk, 6),
                "p_incident_30d_proxy": round(p_incident_30d_proxy, 6),
                "p_service_hit_30d_proxy": round(p_service_hit_30d_proxy, 6),
                "p_major_service_hit_30d_proxy": round(p_major_service_hit_30d_proxy, 6),
                "expected_fill_loss_30d_proxy": round(expected_fill_loss_30d_proxy, 6),
                "expected_backlog_30d_proxy": round(expected_backlog_30d_proxy, 6),
                "incident_probability_band": probability_band(p_incident_30d_proxy),
                "service_hit_probability_band": probability_band(p_service_hit_30d_proxy),
            }
        )
        out.append(row)

    out.sort(key=lambda r: (-to_float(r["combined_proxy_risk_score"]), -to_float(r["expected_backlog_30d_proxy"])))
    return out


def aggregate_by_supplier(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = {}
    for row in rows:
        supplier_id = row["supplier_id"]
        rec = grouped.setdefault(
            supplier_id,
            {
                "supplier_id": supplier_id,
                "supplier_name": row["supplier_name"],
                "material_count": 0,
                "assumed_material_count": 0,
                "max_pair_combined_proxy_risk_score": 0.0,
                "mean_p_incident_30d_proxy": 0.0,
                "mean_p_service_hit_30d_proxy": 0.0,
                "expected_fill_loss_30d_proxy_sum": 0.0,
                "expected_backlog_30d_proxy_sum": 0.0,
                "materials": [],
            },
        )
        rec["material_count"] += 1
        rec["assumed_material_count"] += 1 if row["is_assumed_edge"] else 0
        rec["max_pair_combined_proxy_risk_score"] = max(
            to_float(rec["max_pair_combined_proxy_risk_score"]),
            to_float(row["combined_proxy_risk_score"]),
        )
        rec["mean_p_incident_30d_proxy"] += to_float(row["p_incident_30d_proxy"])
        rec["mean_p_service_hit_30d_proxy"] += to_float(row["p_service_hit_30d_proxy"])
        rec["expected_fill_loss_30d_proxy_sum"] += to_float(row["expected_fill_loss_30d_proxy"])
        rec["expected_backlog_30d_proxy_sum"] += to_float(row["expected_backlog_30d_proxy"])
        rec["materials"].append(row["item_id"])

    out = []
    for rec in grouped.values():
        count = max(1, int(rec["material_count"]))
        rec["mean_p_incident_30d_proxy"] = round(to_float(rec["mean_p_incident_30d_proxy"]) / count, 6)
        rec["mean_p_service_hit_30d_proxy"] = round(to_float(rec["mean_p_service_hit_30d_proxy"]) / count, 6)
        rec["expected_fill_loss_30d_proxy_sum"] = round(to_float(rec["expected_fill_loss_30d_proxy_sum"]), 6)
        rec["expected_backlog_30d_proxy_sum"] = round(to_float(rec["expected_backlog_30d_proxy_sum"]), 6)
        rec["max_pair_combined_proxy_risk_score"] = round(to_float(rec["max_pair_combined_proxy_risk_score"]), 6)
        rec["materials"] = ", ".join(sorted(set(rec["materials"])))
        out.append(rec)
    out.sort(
        key=lambda r: (
            -to_float(r["expected_backlog_30d_proxy_sum"]),
            -to_float(r["max_pair_combined_proxy_risk_score"]),
        )
    )
    return out


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    fieldnames = list(rows[0].keys())
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def markdown_table(rows: list[dict[str, Any]], columns: list[str]) -> str:
    out = ["| " + " | ".join(columns) + " |", "|" + "|".join(["---"] * len(columns)) + "|"]
    for row in rows:
        vals = []
        for col in columns:
            value = row.get(col, "")
            if isinstance(value, float):
                vals.append(f"{value:.6f}")
            else:
                vals.append(str(value))
        out.append("| " + " | ".join(vals) + " |")
    return "\n".join(out)


def build_report(scored_rows: list[dict[str, Any]], supplier_rows: list[dict[str, Any]], baseline: dict[str, Any]) -> tuple[dict[str, Any], str]:
    top_pairs = scored_rows[:15]
    top_suppliers = supplier_rows[:12]
    highest_incident = sorted(scored_rows, key=lambda r: -to_float(r["p_incident_30d_proxy"]))[:12]
    highest_service_hit = sorted(scored_rows, key=lambda r: -to_float(r["p_service_hit_30d_proxy"]))[:12]
    biggest_outage = sorted(scored_rows, key=lambda r: -to_float(r["outage5d_backlog_delta"]))[:12]
    biggest_delay = sorted(scored_rows, key=lambda r: -to_float(r["delayx3_backlog_delta"]))[:12]

    summary = {
        "baseline_context": baseline,
        "methodology": {
            "type": "proxy_probability_times_simulated_impact",
            "warning": "Probabilities are proxy estimates from structural factors, not observed supplier event frequencies.",
            "event_mix_weights": {"outage_5d": 0.25, "delay_x3": 0.45, "otif_50pct": 0.30},
        },
        "pair_count": len(scored_rows),
        "top_pairs": top_pairs,
        "top_suppliers": top_suppliers,
        "highest_incident_probability_pairs": highest_incident,
        "highest_service_hit_probability_pairs": highest_service_hit,
        "largest_outage_backlog_pairs": biggest_outage,
        "largest_delay_backlog_pairs": biggest_delay,
    }

    report = f"""# Etude etendue proxy de risque fournisseur-matiere

## Perimetre
- Base: baseline preparee avec hypothese conservee `item:693710 -> SDC-1450 / Gaillac`
- Cible: couples `supplier -> factory -> item` de la supply amont
- Nombre de couples analyses: **{len(scored_rows)}**
- Nature des probabilites: **proxy**, pas empirique. Elles servent a classer/prioriser tant que le score industriel 22 criteres n'est pas disponible.

## 1) Baseline de reference
- Fill rate: **{to_float(baseline.get('fill_rate')):.6f}**
- Ending backlog: **{to_float(baseline.get('ending_backlog')):.4f}**
- Total cost: **{to_float(baseline.get('total_cost')):.4f}**

## 2) Methode utilisee
Le score provisoire par couple fournisseur-matiere combine 3 couches:
1. **Structure observee**: mono/multi-source, exposition demande aval, volume consomme, couverture, delai, criticite existante.
2. **Impact simule**: pour chaque couple, simulation de:
   - outage 5 jours
   - delai x3
   - OTIF a 50%
3. **Probabilites proxy**:
   - `p_incident_30d_proxy` derivee du score structurel
   - `p_service_hit_30d_proxy` = probabilite proxy d'incident x severite proxy d'impact

Important:
- ces probabilites **ne sont pas des frequences observees**
- elles servent a construire une priorisation rationnelle avant d'avoir le score industriel et l'historique incident

## 3) Top couples fournisseur-matiere a surveiller
{markdown_table(top_pairs, ['supplier_id', 'factory_id', 'item_id', 'combined_proxy_risk_score', 'p_incident_30d_proxy', 'p_service_hit_30d_proxy', 'expected_fill_loss_30d_proxy', 'expected_backlog_30d_proxy', 'supplier_count_for_item', 'is_assumed_edge'])}

Lecture:
- `combined_proxy_risk_score` classe les couples selon **probabilite proxy x impact proxy**.
- `expected_fill_loss_30d_proxy` et `expected_backlog_30d_proxy` donnent une lecture plus operationnelle.

## 4) Couples avec plus forte probabilite proxy d'incident
{markdown_table(highest_incident, ['supplier_id', 'factory_id', 'item_id', 'p_incident_30d_proxy', 'incident_probability_band', 'structural_proxy_score', 'mono_source_risk', 'uncertainty_penalty'])}

Lecture:
- cette table pousse surtout les couples structurellement fragiles:
  mono-source, forte exposition aval, couverture plus faible, delai plus long, ou incertitude modele.

## 5) Couples avec plus forte probabilite proxy de choc service
{markdown_table(highest_service_hit, ['supplier_id', 'factory_id', 'item_id', 'p_service_hit_30d_proxy', 'service_hit_probability_band', 'impact_proxy_score', 'expected_fill_loss_proxy', 'expected_backlog_delta_proxy'])}

Lecture:
- cette table distingue les couples qui ne sont pas seulement fragiles "sur le papier", mais qui **cassent vraiment** le service quand on les secoue.

## 6) Plus gros impacts simules en outage 5 jours
{markdown_table(biggest_outage, ['supplier_id', 'factory_id', 'item_id', 'outage5d_fill_loss', 'outage5d_backlog_delta', 'outage5d_total_cost', 'supplier_count_for_item'])}

## 7) Plus gros impacts simules en delai x3
{markdown_table(biggest_delay, ['supplier_id', 'factory_id', 'item_id', 'delayx3_fill_loss', 'delayx3_backlog_delta', 'delayx3_total_cost', 'lead_mean_days'])}

Lecture:
- certains couples reagissent surtout a la rupture franche,
- d'autres supportent une rupture courte mais deviennent tres couteux quand le delai s'allonge.

## 8) Vue agregée par fournisseur
{markdown_table(top_suppliers, ['supplier_id', 'material_count', 'max_pair_combined_proxy_risk_score', 'mean_p_incident_30d_proxy', 'mean_p_service_hit_30d_proxy', 'expected_backlog_30d_proxy_sum', 'materials'])}

Lecture:
- cette vue permet de prioriser les **fournisseurs** et pas seulement les couples fournisseur-matiere.
- un fournisseur multi-matieres peut remonter haut meme si chaque matiere seule est moyenne.

## 9) Ce qu'on peut deja dire proprement
1. Ce classement est utile pour une **priorisation provisoire** avant le score industriel 22 criteres.
2. Les couples mono-source fortement exposes a la demande restent logiquement en tete.
3. `item:693710` reste un cas special: visible dans le classement, mais une partie du signal depend de l'hypothese Gaillac.
4. `item:730384` peut remonter via son ambiguite d'unite/semantique, mais son impact operationnel simule reste plus faible que les matieres majeures.
5. Cette etude est plus utile pour la **priorisation relative** que pour donner un pourcentage "vrai" d'incident.

## 10) Limites et prochaine etape
- Sans historique fournisseur ni score 22 criteres, les probabilites restent des **proba proxy**.
- La prochaine etape naturelle est de remplacer la couche probabilite proxy par:
  - le score industriel fournisseur-matiere,
  - puis idealement des historiques OTIF / retard / qualite.
- Le bloc impact simule, lui, est deja reutilisable quasiment tel quel.
"""
    return summary, report


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    base_rows, baseline_summary, _ = build_rows()
    scored_rows = compute_scores(base_rows)
    supplier_rows = aggregate_by_supplier(scored_rows)
    summary, report = build_report(scored_rows, supplier_rows, baseline_summary)

    write_csv(OUT_DIR / "supplier_material_risk_proxy_table.csv", scored_rows)
    write_csv(OUT_DIR / "supplier_aggregate_risk_proxy_table.csv", supplier_rows)
    write_json(OUT_DIR / "supplier_risk_proxy_summary.json", summary)
    (OUT_DIR / "supplier_risk_proxy_report.md").write_text(report, encoding="utf-8")

    print(f"[OK] Pair table: {(OUT_DIR / 'supplier_material_risk_proxy_table.csv').resolve()}")
    print(f"[OK] Supplier table: {(OUT_DIR / 'supplier_aggregate_risk_proxy_table.csv').resolve()}")
    print(f"[OK] Summary JSON: {(OUT_DIR / 'supplier_risk_proxy_summary.json').resolve()}")
    print(f"[OK] Report: {(OUT_DIR / 'supplier_risk_proxy_report.md').resolve()}")


if __name__ == "__main__":
    main()
