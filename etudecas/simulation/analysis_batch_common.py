#!/usr/bin/env python3
"""
Common helpers for sensitivity and Monte Carlo simulation batches.
"""

from __future__ import annotations

import copy
import csv
import hashlib
import json
import math
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

try:
    from .initial_state_policy import merge_living_initial_state_args
    from .result_paths import resolve_existing_path, summary_path
except ImportError:
    from initial_state_policy import merge_living_initial_state_args
    from result_paths import resolve_existing_path, summary_path


def to_float(x: Any, default: float = 0.0) -> float:
    try:
        return float(x)
    except (TypeError, ValueError):
        return default


def safe_name(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_-]+", "_", str(value))


def parse_supplier_pair_key(value: Any) -> tuple[str, str, str]:
    parts = str(value or "").split("|", 2)
    if len(parts) != 3 or not all(part.strip() for part in parts):
        raise ValueError(
            "Supplier pair keys must use the format 'supplier|destination|item'."
        )
    return tuple(part.strip() for part in parts)  # type: ignore[return-value]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


STUDY_CASE_SCHEMA = "etudecas.sensitivity.completed-case.v1"
STUDY_CASE_RECEIPT = "completed_case.json"


def _study_json_hash(value: Any) -> str:
    payload = json.dumps(
        value, sort_keys=True, ensure_ascii=True, separators=(",", ":"), allow_nan=False,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _study_file_hash(path: Path) -> str:
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def study_case_identity(
    *,
    base_data: dict[str, Any],
    config: dict[str, Any],
    run_script: Path,
    scenario_id: str,
    days: int,
    extra_args: list[str],
    metadata: dict[str, Any],
    dependency_paths: list[Path] | None = None,
) -> str:
    """Strict run identity; source and external data are reread, never cached.

    Relative options have the same working-directory semantics as the runner.
    The graph/config and ordered arguments include seeds and effective policies.
    Both engine and study sources matter, including when a custom engine is used.
    """
    from etudecas.case_config import DEFAULT_CASE_CONFIG_PATH
    from etudecas.simulation.source_fingerprint import implementation_fingerprint

    dependencies = [DEFAULT_CASE_CONFIG_PATH, *(dependency_paths or [])]
    for token in extra_args:
        raw = str(token).split("=", 1)[-1]
        if not raw or raw.startswith("--"):
            continue
        candidate = Path(raw)
        data_suffixes = {".csv", ".json", ".xlsx", ".yaml", ".yml", ".toml", ".py"}
        if candidate.suffix.lower() in data_suffixes or candidate.is_file():
            dependencies.append(candidate)
    return _study_json_hash({
        "schema": STUDY_CASE_SCHEMA,
        "base_data": base_data,
        "config": config,
        "run_script": str(run_script.resolve()),
        "engine_sha256": _study_file_hash(run_script),
        "implementation_sha256": implementation_fingerprint(run_script),
        "study_implementation_sha256": implementation_fingerprint(Path(__file__)),
        "scenario_id": scenario_id,
        "days": days,
        "extra_args": list(extra_args),
        "metadata": metadata,
        "dependencies": {str(p.resolve()): _study_file_hash(p) for p in dependencies},
    })


def load_completed_study_case(case_dir: Path, identity: str) -> dict[str, Any] | None:
    """Only a matching completed receipt permits reuse; old directories are read-only."""
    if not case_dir.exists() or not any(case_dir.iterdir()):
        return None
    try:
        receipt = load_json(case_dir / STUDY_CASE_RECEIPT)
        row = receipt["row"]
        files = receipt["files"]
        required_summary = {
            "simulation_output/summaries/first_simulation_summary.json",
            "simulation_output/first_simulation_summary.json",
        }
        if (
            receipt["schema"] != STUDY_CASE_SCHEMA
            or receipt["identity"] != identity
            or row.get("status") != "ok"
            or "input_case.json" not in files
            or not required_summary.intersection(files)
            or receipt["row_sha256"] != _study_json_hash(row)
        ):
            raise ValueError("case identity or result differs")
        for name, expected in files.items():
            path = (case_dir / name).resolve()
            if not path.is_relative_to(case_dir.resolve()) or _study_file_hash(path) != expected:
                raise ValueError("case input or summary differs")
        return row
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as exc:
        raise ValueError(
            f"Cannot safely resume {case_dir}: missing, incomplete or mismatched "
            "completed-case receipt. Preserve this directory and use a new output directory."
        ) from exc


def publish_completed_study_case(
    case_dir: Path,
    *,
    identity: str,
    current_identity: str,
    prepared_inputs: dict[str, str],
    row: dict[str, Any],
) -> None:
    """Publish after successful execution, metrics and retention, never on partial work."""
    from etudecas.atomic_io import write_json_atomic

    if identity != current_identity or row.get("status") != "ok":
        raise ValueError("Study inputs/sources changed during execution, or case did not succeed")
    if prepared_inputs != study_case_input_hashes(case_dir):
        raise ValueError("Prepared study inputs changed during execution; no receipt published")
    output = case_dir / "simulation_output"
    summary = next((p for p in (
        output / "summaries" / "first_simulation_summary.json",
        output / "first_simulation_summary.json",
    ) if p.is_file()), None)
    if summary is None:
        raise ValueError("Cannot publish completed case without simulation summary")
    paths = [case_dir / "input_case.json", summary]
    floor = case_dir / "supplier_neutral_floors_case.csv"
    if floor.is_file():
        paths.append(floor)
    write_json_atomic(case_dir / STUDY_CASE_RECEIPT, {
        "schema": STUDY_CASE_SCHEMA, "identity": identity, "row": row,
        "row_sha256": _study_json_hash(row),
        "files": {p.relative_to(case_dir).as_posix(): _study_file_hash(p) for p in paths},
    })


def study_case_input_hashes(case_dir: Path) -> dict[str, str]:
    """Capture the exact prepared files before launching the engine."""
    paths = [case_dir / "input_case.json"]
    floor = case_dir / "supplier_neutral_floors_case.csv"
    if floor.is_file():
        paths.append(floor)
    return {p.name: _study_file_hash(p) for p in paths}


def base_sensitivity_case() -> dict[str, Any]:
    return {
        "factors": {
            "demand_scale": 1.0,
            "lead_time_scale": 1.0,
            "transport_cost_scale": 1.0,
            "supplier_stock_scale": 1.0,
            "production_stock_scale": 1.0,
            "capacity_scale": 1.0,
            "supplier_capacity_scale": 1.0,
            "safety_stock_days_scale": 1.0,
            "supplier_reliability_scale": 1.0,
        },
        "demand_item_scale": {},
        "capacity_node_scale": {},
        "supplier_node_scale": {},
        "supplier_capacity_node_scale": {},
        "edge_src_lead_time_scale": {},
        "edge_src_reliability_scale": {},
    }


def clone_sensitivity_case(case_cfg: dict[str, Any]) -> dict[str, Any]:
    return {
        "factors": dict(case_cfg["factors"]),
        "demand_item_scale": dict(case_cfg["demand_item_scale"]),
        "capacity_node_scale": dict(case_cfg["capacity_node_scale"]),
        "supplier_node_scale": dict(case_cfg["supplier_node_scale"]),
        "supplier_capacity_node_scale": dict(case_cfg["supplier_capacity_node_scale"]),
        "edge_src_lead_time_scale": dict(case_cfg["edge_src_lead_time_scale"]),
        "edge_src_reliability_scale": dict(case_cfg["edge_src_reliability_scale"]),
    }


def detect_supplier_nodes(data: dict[str, Any]) -> list[str]:
    outgoing_sources = {
        str(edge.get("from"))
        for edge in (data.get("edges") or [])
        if edge.get("from") is not None
    }
    out: list[str] = []
    for node in data.get("nodes", []) or []:
        node_id = str(node.get("id"))
        if str(node.get("type") or "") == "supplier_dc" and node_id in outgoing_sources:
            out.append(node_id)
    return sorted(set(out))


def select_active_suppliers(
    shipment_csv: Path,
    allowed_suppliers: set[str],
    top_n: int,
) -> list[str]:
    shipped_qty_by_supplier: dict[str, float] = {}
    if shipment_csv.exists():
        with shipment_csv.open("r", encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                src = str(row.get("src_node_id") or "")
                if src not in allowed_suppliers:
                    continue
                shipped_qty_by_supplier[src] = shipped_qty_by_supplier.get(src, 0.0) + max(
                    0.0,
                    to_float(row.get("shipped_qty"), 0.0),
                )
    ordered = sorted(
        shipped_qty_by_supplier.items(),
        key=lambda it: (-it[1], it[0]),
    )
    selected = [supplier for supplier, qty in ordered if qty > 1e-9][:top_n]
    if not selected:
        selected = sorted(allowed_suppliers)[:top_n]
    return selected


def choose_scenario(data: dict[str, Any], scenario_id: str) -> dict[str, Any]:
    scenarios = data.get("scenarios", []) or []
    for scn in scenarios:
        if str(scn.get("id")) == scenario_id:
            return scn
    raise ValueError(f"Unknown scenario: {scenario_id!r}")


def detect_production_nodes(data: dict[str, Any]) -> list[str]:
    out: list[str] = []
    for n in data.get("nodes", []) or []:
        if n.get("processes"):
            out.append(str(n.get("id")))
    return sorted(set(out))


def detect_demand_items(data: dict[str, Any], scenario_id: str) -> list[str]:
    scn = choose_scenario(data, scenario_id)
    items = [str(d.get("item_id")) for d in (scn.get("demand", []) or []) if d.get("item_id") is not None]
    return sorted(set(items))


def scale_profile_values(profile: list[dict[str, Any]], factor: float) -> None:
    if factor <= 0:
        raise ValueError(f"Invalid non-positive scale factor: {factor}")
    for p in profile:
        if not isinstance(p, dict):
            continue
        ptype = str(p.get("type", "constant")).lower()
        if ptype in {"constant", "step"} and "value" in p:
            p["value"] = round(max(0.0, to_float(p.get("value"), 0.0) * factor), 6)
        elif ptype == "piecewise":
            points = p.get("points") or []
            for pt in points:
                if isinstance(pt, dict) and "value" in pt:
                    pt["value"] = round(max(0.0, to_float(pt.get("value"), 0.0) * factor), 6)


SUPPORTED_FACTORS = frozenset(['capacity_scale', 'demand_scale', 'external_procurement_cost_multiplier_scale', 'external_procurement_daily_cap_days_scale', 'external_procurement_lead_days_scale', 'external_procurement_transport_cost_scale', 'fg_target_days_scale', 'holding_cost_scale', 'lead_time_scale', 'production_gap_gain_scale', 'production_smoothing_scale', 'production_stock_scale', 'purchase_cost_floor_scale', 'review_period_scale', 'safety_stock_days_scale', 'supplier_capacity_scale', 'supplier_reliability_scale', 'supplier_stock_scale', 'transport_cost_scale'])


def validate_factors(factors: dict[str, float]) -> None:
    unknown = set(factors) - SUPPORTED_FACTORS
    if unknown:
        raise ValueError(f"Unknown sensitivity factors: {sorted(unknown)}")
    for name, value in factors.items():
        if type(value) not in (int, float) or not math.isfinite(value) or value <= 0:
            raise ValueError(f"Factor {name} must be a finite positive number")


def apply_scales(
    base_data: dict[str, Any],
    scenario_id: str,
    factors: dict[str, float],
    demand_item_scale: dict[str, float] | None = None,
    capacity_node_scale: dict[str, float] | None = None,
    supplier_node_scale: dict[str, float] | None = None,
    supplier_capacity_node_scale: dict[str, float] | None = None,
    edge_src_lead_time_scale: dict[str, float] | None = None,
    edge_src_reliability_scale: dict[str, float] | None = None,
    supplier_stock_pair_scale: dict[str, float] | None = None,
    supplier_capacity_pair_scale: dict[str, float] | None = None,
    edge_pair_lead_time_scale: dict[str, float] | None = None,
    edge_pair_reliability_scale: dict[str, float] | None = None,
) -> dict[str, Any]:
    validate_factors(factors)
    for label, mapping in (
        ("demand_item_scale", demand_item_scale), ("capacity_node_scale", capacity_node_scale),
        ("supplier_node_scale", supplier_node_scale), ("supplier_capacity_node_scale", supplier_capacity_node_scale),
        ("edge_src_lead_time_scale", edge_src_lead_time_scale), ("edge_src_reliability_scale", edge_src_reliability_scale),
        ("supplier_stock_pair_scale", supplier_stock_pair_scale), ("supplier_capacity_pair_scale", supplier_capacity_pair_scale),
        ("edge_pair_lead_time_scale", edge_pair_lead_time_scale), ("edge_pair_reliability_scale", edge_pair_reliability_scale),
    ):
        for key, value in (mapping or {}).items():
            if type(value) not in (int, float) or not math.isfinite(value) or value <= 0:
                raise ValueError(f"{label}[{key}] must be finite and strictly positive")
    data = copy.deepcopy(base_data)
    demand_item_scale = demand_item_scale or {}
    capacity_node_scale = capacity_node_scale or {}
    supplier_node_scale = supplier_node_scale or {}
    supplier_capacity_node_scale = supplier_capacity_node_scale or {}
    edge_src_lead_time_scale = edge_src_lead_time_scale or {}
    edge_src_reliability_scale = edge_src_reliability_scale or {}
    supplier_stock_pair_scale = supplier_stock_pair_scale or {}
    supplier_capacity_pair_scale = supplier_capacity_pair_scale or {}
    edge_pair_lead_time_scale = edge_pair_lead_time_scale or {}
    edge_pair_reliability_scale = edge_pair_reliability_scale or {}
    parsed_stock_pair_scale = {
        parse_supplier_pair_key(key): to_float(value, 1.0)
        for key, value in supplier_stock_pair_scale.items()
    }
    parsed_capacity_pair_scale = {
        parse_supplier_pair_key(key): to_float(value, 1.0)
        for key, value in supplier_capacity_pair_scale.items()
    }
    parsed_lead_pair_scale = {
        parse_supplier_pair_key(key): to_float(value, 1.0)
        for key, value in edge_pair_lead_time_scale.items()
    }
    parsed_reliability_pair_scale = {
        parse_supplier_pair_key(key): to_float(value, 1.0)
        for key, value in edge_pair_reliability_scale.items()
    }
    production_nodes = set(detect_production_nodes(data))

    demand_global_scale = to_float(factors.get("demand_scale", 1.0), 1.0)
    lead_time_scale = to_float(factors.get("lead_time_scale", 1.0), 1.0)
    transport_cost_scale = to_float(factors.get("transport_cost_scale", 1.0), 1.0)
    supplier_stock_scale = to_float(factors.get("supplier_stock_scale", 1.0), 1.0)
    production_stock_scale = to_float(factors.get("production_stock_scale", 1.0), 1.0)
    capacity_global_scale = to_float(factors.get("capacity_scale", 1.0), 1.0)
    supplier_capacity_global_scale = to_float(factors.get("supplier_capacity_scale", 1.0), 1.0)
    safety_stock_days_scale = to_float(factors.get("safety_stock_days_scale", 1.0), 1.0)
    review_period_scale = to_float(factors.get("review_period_scale", 1.0), 1.0)
    supplier_reliability_scale = to_float(factors.get("supplier_reliability_scale", 1.0), 1.0)
    fg_target_days_scale = to_float(factors.get("fg_target_days_scale", 1.0), 1.0)
    production_gap_gain_scale = to_float(factors.get("production_gap_gain_scale", 1.0), 1.0)
    production_smoothing_scale = to_float(factors.get("production_smoothing_scale", 1.0), 1.0)
    holding_cost_scale = to_float(factors.get("holding_cost_scale", 1.0), 1.0)
    purchase_cost_floor_scale = to_float(factors.get("purchase_cost_floor_scale", 1.0), 1.0)
    external_procurement_daily_cap_days_scale = to_float(
        factors.get("external_procurement_daily_cap_days_scale", 1.0),
        1.0,
    )
    external_procurement_lead_days_scale = to_float(
        factors.get("external_procurement_lead_days_scale", 1.0),
        1.0,
    )
    external_procurement_cost_multiplier_scale = to_float(
        factors.get("external_procurement_cost_multiplier_scale", 1.0),
        1.0,
    )
    external_procurement_transport_cost_scale = to_float(
        factors.get("external_procurement_transport_cost_scale", 1.0),
        1.0,
    )

    if any(
        v <= 0
        for v in [
            demand_global_scale,
            lead_time_scale,
            transport_cost_scale,
            supplier_stock_scale,
            production_stock_scale,
            capacity_global_scale,
            supplier_capacity_global_scale,
            safety_stock_days_scale,
            review_period_scale,
            supplier_reliability_scale,
            fg_target_days_scale,
            production_gap_gain_scale,
            production_smoothing_scale,
            holding_cost_scale,
            purchase_cost_floor_scale,
            external_procurement_daily_cap_days_scale,
            external_procurement_lead_days_scale,
            external_procurement_cost_multiplier_scale,
            external_procurement_transport_cost_scale,
        ]
    ):
        raise ValueError("All factors must be strictly positive.")
    if any(v <= 0 for v in supplier_node_scale.values()):
        raise ValueError("All supplier_node_scale values must be strictly positive.")
    if any(v <= 0 for v in supplier_capacity_node_scale.values()):
        raise ValueError("All supplier_capacity_node_scale values must be strictly positive.")
    if any(v <= 0 for v in edge_src_lead_time_scale.values()):
        raise ValueError("All edge_src_lead_time_scale values must be strictly positive.")
    if any(v <= 0 for v in edge_src_reliability_scale.values()):
        raise ValueError("All edge_src_reliability_scale values must be strictly positive.")
    for label, values in (
        ("supplier_stock_pair_scale", parsed_stock_pair_scale.values()),
        ("supplier_capacity_pair_scale", parsed_capacity_pair_scale.values()),
        ("edge_pair_lead_time_scale", parsed_lead_pair_scale.values()),
        ("edge_pair_reliability_scale", parsed_reliability_pair_scale.values()),
    ):
        if any(value <= 0 for value in values):
            raise ValueError(f"All {label} values must be strictly positive.")

    scn = choose_scenario(data, scenario_id)
    for d in (scn.get("demand", []) or []):
        item_id = str(d.get("item_id"))
        scale = demand_global_scale * to_float(demand_item_scale.get(item_id, 1.0), 1.0)
        scale_profile_values(d.get("profile") or [], scale)
    base_safety_days = to_float(scn.get("safety_stock_days", 7.0), 7.0)
    base_review_days = to_float(scn.get("review_period_days", 1.0), 1.0)
    base_fg_target_days = to_float(scn.get("fg_target_days", 0.0), 0.0)
    base_production_gap_gain = to_float(scn.get("production_gap_gain", 0.25), 0.25)
    base_production_smoothing = to_float(scn.get("production_smoothing", 0.20), 0.20)
    scn["safety_stock_days"] = round(max(0.0, base_safety_days * safety_stock_days_scale), 6)
    scn["review_period_days"] = max(1, int(round(max(1.0, base_review_days * review_period_scale))))
    scn["fg_target_days"] = round(max(0.0, base_fg_target_days * fg_target_days_scale), 6)
    scn["production_gap_gain"] = round(max(0.0, base_production_gap_gain * production_gap_gain_scale), 6)
    scn["production_smoothing"] = round(
        min(0.95, max(0.0, base_production_smoothing * production_smoothing_scale)),
        6,
    )
    econ = scn.get("economic_policy")
    if not isinstance(econ, dict):
        econ = {}
    econ["transport_cost_floor_per_unit"] = round(
        max(0.0, to_float(econ.get("transport_cost_floor_per_unit"), 0.02) * transport_cost_scale),
        6,
    )
    econ["transport_cost_per_km_per_unit"] = round(
        max(0.0, to_float(econ.get("transport_cost_per_km_per_unit"), 0.00008) * transport_cost_scale),
        6,
    )
    econ["external_procurement_transport_cost_per_unit"] = round(
        max(
            0.0,
            to_float(econ.get("external_procurement_transport_cost_per_unit"), 0.04)
            * transport_cost_scale
            * external_procurement_transport_cost_scale,
        ),
        6,
    )
    econ["holding_cost_scale"] = round(
        max(0.01, to_float(econ.get("holding_cost_scale"), 1.0) * holding_cost_scale),
        6,
    )
    econ["purchase_cost_floor_per_unit"] = round(
        max(0.0, to_float(econ.get("purchase_cost_floor_per_unit"), 0.01) * purchase_cost_floor_scale),
        6,
    )
    econ["external_procurement_daily_cap_days"] = round(
        max(
            0.0,
            to_float(econ.get("external_procurement_daily_cap_days"), 2.0)
            * external_procurement_daily_cap_days_scale,
        ),
        6,
    )
    econ["external_procurement_nominal_capacity_scale"] = round(
        max(
            0.0,
            to_float(econ.get("external_procurement_nominal_capacity_scale"), 1.0)
            * external_procurement_daily_cap_days_scale,
        ),
        6,
    )
    econ["external_procurement_lead_days"] = int(
        round(max(0.0, to_float(econ.get("external_procurement_lead_days"), 4.0)))
    )
    econ["external_procurement_lead_time_scale"] = round(
        max(
            0.01,
            to_float(econ.get("external_procurement_lead_time_scale"), 1.0)
            * external_procurement_lead_days_scale,
        ),
        6,
    )
    econ["external_procurement_cost_multiplier"] = round(
        max(
            0.1,
            to_float(econ.get("external_procurement_cost_multiplier"), 2.0)
            * external_procurement_cost_multiplier_scale,
        ),
        6,
    )
    scn["economic_policy"] = econ

    for n in data.get("nodes", []) or []:
        node_id = str(n.get("id"))
        node_type = str(n.get("type") or "")
        node_cap_scale = to_float(capacity_node_scale.get(node_id, 1.0), 1.0) * capacity_global_scale
        if node_cap_scale <= 0:
            raise ValueError(f"Invalid capacity scale for node {node_id}: {node_cap_scale}")
        for p in (n.get("processes") or []):
            cap = p.get("capacity") or {}
            if "max_rate" in cap:
                cap["max_rate"] = round(max(0.0, to_float(cap.get("max_rate"), 0.0) * node_cap_scale), 6)
            p["capacity"] = cap

        inv = n.get("inventory") or {}
        states = inv.get("states") or []
        inv_factor = production_stock_scale if node_id in production_nodes else supplier_stock_scale
        if node_type == "supplier_dc":
            inv_factor *= to_float(supplier_node_scale.get(node_id, 1.0), 1.0)
            sim_constraints = n.get("simulation_constraints") or {}
            sim_constraints["supplier_capacity_scale"] = round(
                max(
                    0.01,
                    to_float(sim_constraints.get("supplier_capacity_scale"), 1.0)
                    * supplier_capacity_global_scale
                    * to_float(supplier_capacity_node_scale.get(node_id, 1.0), 1.0),
                ),
                6,
            )
            item_capacity_scale = dict(
                sim_constraints.get("supplier_item_capacity_scale") or {}
            )
            for (src, _dst, item_id), pair_scale in parsed_capacity_pair_scale.items():
                if src != node_id:
                    continue
                item_capacity_scale[item_id] = round(
                    max(
                        0.01,
                        to_float(item_capacity_scale.get(item_id), 1.0) * pair_scale,
                    ),
                    6,
                )
            if item_capacity_scale:
                sim_constraints["supplier_item_capacity_scale"] = item_capacity_scale
            n["simulation_constraints"] = sim_constraints
        for st in states:
            if "initial" in st:
                item_id = str(st.get("item_id") or "")
                pair_stock_factor = 1.0
                for (src, _dst, pair_item), pair_scale in parsed_stock_pair_scale.items():
                    if src == node_id and pair_item == item_id:
                        pair_stock_factor *= pair_scale
                st["initial"] = round(
                    max(
                        0.0,
                        to_float(st.get("initial"), 0.0)
                        * inv_factor
                        * pair_stock_factor,
                    ),
                    6,
                )
        inv["states"] = states
        n["inventory"] = inv

    for e in data.get("edges", []) or []:
        edge_src = str(e.get("from") or "")
        edge_dst = str(e.get("to") or "")
        edge_items = [str(item_id) for item_id in (e.get("items") or [])]
        pair_lead_scale = math.prod(
            parsed_lead_pair_scale.get((edge_src, edge_dst, item_id), 1.0)
            for item_id in edge_items
        )
        pair_reliability_scale = math.prod(
            parsed_reliability_pair_scale.get((edge_src, edge_dst, item_id), 1.0)
            for item_id in edge_items
        )
        edge_lead_scale = (
            to_float(edge_src_lead_time_scale.get(edge_src, 1.0), 1.0)
            * pair_lead_scale
            * lead_time_scale
        )
        edge_reliability = (
            to_float(edge_src_reliability_scale.get(edge_src, 1.0), 1.0)
            * pair_reliability_scale
        )
        lead = e.get("lead_time") or {}
        for k in ["mean", "min", "max"]:
            if k in lead:
                lead[k] = round(max(0.05, to_float(lead.get(k), 0.0) * edge_lead_scale), 6)
        e["lead_time"] = lead

        tc = e.get("transport_cost") or {}
        if "value" in tc:
            tc["value"] = round(max(0.0, to_float(tc.get("value"), 0.0) * transport_cost_scale), 6)
        e["transport_cost"] = tc

        service_level = e.get("service_level") or {}
        base_rel = to_float(service_level.get("otif", e.get("otif", 1.0)), 1.0)
        service_level["otif"] = round(
            min(1.0, max(0.01, base_rel * supplier_reliability_scale * edge_reliability)),
            6,
        )
        e["service_level"] = service_level

    return data


def run_simulation(
    run_script: Path,
    input_json: Path,
    output_dir: Path,
    scenario_id: str,
    days: int = 0,
    skip_map: bool = True,
    skip_plots: bool = True,
    extra_args: list[str] | None = None,
    use_living_initial_state: bool = True,
    *,
    timeout_seconds: float | None = None,
) -> tuple[dict[str, Any], str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    cmd = [
        sys.executable,
        str(run_script),
        "--input",
        str(input_json),
        "--output-dir",
        str(output_dir),
        "--scenario-id",
        str(scenario_id),
    ]
    if days > 0:
        cmd.extend(["--days", str(days)])
    if skip_map:
        cmd.append("--skip-map")
    if skip_plots:
        cmd.append("--skip-plots")
    merged_extra_args = merge_living_initial_state_args(extra_args, enabled=use_living_initial_state)
    if merged_extra_args:
        cmd.extend(merged_extra_args)

    if timeout_seconds is None:
        proc = subprocess.run(cmd, capture_output=True, text=True)
    else:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout_seconds)
    if proc.returncode != 0:
        stderr = proc.stderr.strip()
        stdout = proc.stdout.strip()
        message = "\n".join([part for part in [stdout, stderr] if part]).strip()
        raise RuntimeError(f"Simulation failed for {input_json}:\n{message}")

    summary_file = resolve_existing_path(
        summary_path(output_dir, "first_simulation_summary.json"),
        output_dir / "first_simulation_summary.json",
    )
    summary = load_json(summary_file)
    return summary, proc.stdout


def numeric_kpis(summary: dict[str, Any]) -> dict[str, float]:
    out: dict[str, float] = {}
    for k, v in (summary.get("kpis") or {}).items():
        fv = to_float(v, math.nan)
        if math.isnan(fv):
            continue
        out[str(k)] = fv
    return out


def percentile(sorted_values: list[float], q: float) -> float:
    if not sorted_values:
        return float("nan")
    if len(sorted_values) == 1:
        return sorted_values[0]
    q = min(1.0, max(0.0, q))
    pos = q * (len(sorted_values) - 1)
    i = int(math.floor(pos))
    j = int(math.ceil(pos))
    if i == j:
        return sorted_values[i]
    w = pos - i
    return sorted_values[i] * (1.0 - w) + sorted_values[j] * w


def pearson_corr(xs: list[float], ys: list[float]) -> float:
    n = min(len(xs), len(ys))
    if n < 2:
        return float("nan")
    mx = sum(xs[:n]) / n
    my = sum(ys[:n]) / n
    num = sum((x - mx) * (y - my) for x, y in zip(xs[:n], ys[:n]))
    denx = math.sqrt(sum((x - mx) ** 2 for x in xs[:n]))
    deny = math.sqrt(sum((y - my) ** 2 for y in ys[:n]))
    if denx <= 0 or deny <= 0:
        return float("nan")
    return num / (denx * deny)


def prune_simulation_output(
    output_dir: Path,
    *,
    keep_reports: bool = True,
    keep_summaries: bool = True,
) -> None:
    if not output_dir.exists():
        return

    for child in output_dir.iterdir():
        if child.name == "reports" and keep_reports:
            continue
        if child.name == "summaries" and keep_summaries:
            continue
        if child.is_dir() and child.name in {"data", "plots", "maps"}:
            shutil.rmtree(child, ignore_errors=True)
            continue
        if child.is_file() and child.suffix.lower() in {".csv", ".png", ".html"}:
            child.unlink(missing_ok=True)
