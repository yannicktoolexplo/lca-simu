#!/usr/bin/env python3
"""
Run reproducible Monte Carlo analysis on the supply simulation.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import csv
import gzip
import hashlib
import json
import math
import os
import random
import sys
import tempfile
import threading
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean, pstdev
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from etudecas.simulation.analysis_batch_common import (
    apply_scales,
    detect_demand_items,
    detect_production_nodes,
    load_json,
    numeric_kpis,
    pearson_corr,
    percentile,
    run_simulation,
    safe_name,
    to_float,
    write_json,
)
from etudecas.simulation.montecarlo.trajectory_collector import (
    build_montecarlo_trajectories_payload,
    extract_run_trajectories,
)
from etudecas.simulation.uncertainty.paired_propagation import (
    build_paired_propagation_payload,
    build_paired_run_specs,
    default_business_factor_ranges,
    is_economic_factor,
    select_background_rows,
    select_paired_factors,
    select_supplier_item_factors,
)
from etudecas.simulation.uncertainty.temporal_propagation import (
    build_temporal_propagation,
)
from etudecas.simulation.uncertainty.variance_decomposition import (
    build_variance_decomposition,
)
from etudecas.simulation.uncertainty.cost_diagnostics import build_cost_diagnostics

PROFILE_RANK = {
    "workshop": 0,
    "risk_probe": 1,
    "stress_probe": 2,
    "breakpoint_probe": 3,
    "portfolio_probe": 2,
    "legacy": 1,
}

PORTFOLIO_PROBE_FAMILIES = [
    "near_nominal",
    "demand_peak",
    "demand_mix",
    "supplier_delay",
    "supplier_stock",
    "supplier_capacity",
    "supplier_reliability_quality",
    "inbound_logistics",
    "cost_inflation",
    "combined_moderate",
    "combined_severe",
]

PORTFOLIO_PROBE_FAMILY_LABELS = {
    "near_nominal": "Quasi nominal",
    "demand_peak": "Pic de demande",
    "demand_mix": "Mix produit demande",
    "supplier_delay": "Delais fournisseurs",
    "supplier_stock": "Stocks fournisseurs",
    "supplier_capacity": "Capacites fournisseurs",
    "supplier_reliability_quality": "Fiabilite / qualite fournisseur",
    "inbound_logistics": "Logistique amont",
    "cost_inflation": "Inflation couts supply",
    "combined_moderate": "Scenario combine modere",
    "combined_severe": "Scenario combine severe",
}

RUN_CHECKPOINT_SCHEMA_VERSION = "etudecas.montecarlo.run-checkpoint.v1"


def _json_safe(value: Any) -> Any:
    """Return a deterministic, strict-JSON representation for fingerprints/checkpoints."""

    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if isinstance(value, set):
        return sorted((_json_safe(item) for item in value), key=lambda item: repr(item))
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


def _canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        _json_safe(value),
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _implementation_fingerprint(run_script: Path) -> str:
    """Fingerprint simulation code that can alter a run result."""

    candidates = set(run_script.parent.rglob("*.py")) if run_script.parent.exists() else set()
    candidates.update(
        {
            Path(__file__).resolve().parents[1] / "analysis_batch_common.py",
            Path(__file__).resolve().parent / "trajectory_collector.py",
        }
    )
    digest = hashlib.sha256()
    for candidate in sorted((path.resolve() for path in candidates if path.is_file()), key=str):
        digest.update(str(candidate).encode("utf-8"))
        digest.update(b"\0")
        digest.update(_sha256_file(candidate).encode("ascii"))
        digest.update(b"\0")
    return digest.hexdigest()


def build_checkpoint_config(
    *,
    input_path: Path,
    run_script: Path,
    scenario_id: str,
    days: int,
    simulator_extra_args: list[str],
    keep_run_artifacts: bool,
    save_trajectories: bool,
    trajectory_max_points: int,
) -> dict[str, Any]:
    """Build the compact campaign configuration used to validate resumability."""

    resolved_input = input_path.resolve()
    resolved_script = run_script.resolve()
    dependency_files: dict[str, str] = {}
    for token in simulator_extra_args:
        raw_value = str(token).split("=", 1)[-1]
        candidate = Path(raw_value)
        if not candidate.is_absolute():
            candidate = REPO_ROOT / candidate
        if candidate.is_file():
            dependency_files[str(candidate.resolve())] = _sha256_file(candidate.resolve())
    return {
        "input_path": str(resolved_input),
        "input_sha256": _sha256_file(resolved_input),
        "run_script": str(resolved_script),
        "implementation_sha256": _implementation_fingerprint(resolved_script),
        "scenario_id": str(scenario_id),
        "days": int(days),
        "simulator_extra_args": list(simulator_extra_args),
        "dependency_files": dependency_files,
        "keep_run_artifacts": bool(keep_run_artifacts),
        "save_trajectories": bool(save_trajectories),
        "trajectory_max_points": max(0, int(trajectory_max_points)),
    }


def checkpoint_fingerprint(
    spec: dict[str, Any],
    run_config: dict[str, Any],
    *,
    phase: str,
) -> str:
    payload = {
        "schema_version": RUN_CHECKPOINT_SCHEMA_VERSION,
        "phase": str(phase),
        "run_config": run_config,
        "spec": spec,
    }
    return hashlib.sha256(_canonical_json_bytes(payload)).hexdigest()


def checkpoint_path(checkpoints_dir: Path, spec: dict[str, Any], *, phase: str) -> Path:
    index = int(spec["index"])
    run_id = safe_name(str(spec["run_id"]))
    return checkpoints_dir / safe_name(str(phase)) / f"{index:05d}_{run_id}.json.gz"


def _atomic_write_bytes(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(
        f".{path.name}.{os.getpid()}.{threading.get_ident()}.tmp"
    )
    try:
        with temporary.open("wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def write_run_checkpoint(
    path: Path,
    *,
    fingerprint: str,
    phase: str,
    result: dict[str, Any],
    require_trajectory: bool,
) -> bool:
    """Atomically persist a successful compact result; failed/incomplete runs are retried."""

    row = result.get("row")
    trajectory_run = result.get("trajectory_run")
    if not isinstance(row, dict) or row.get("status") != "ok":
        return False
    if require_trajectory and not isinstance(trajectory_run, dict):
        return False
    payload = {
        "schema_version": RUN_CHECKPOINT_SCHEMA_VERSION,
        "phase": str(phase),
        "fingerprint": str(fingerprint),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "result": {
            "index": int(result["index"]),
            "row": row,
            "trajectory_run": trajectory_run,
        },
    }
    compressed = gzip.compress(_canonical_json_bytes(payload), compresslevel=6, mtime=0)
    _atomic_write_bytes(path, compressed)
    return True


def load_run_checkpoint(
    path: Path,
    *,
    expected_fingerprint: str,
    phase: str,
    require_trajectory: bool,
) -> dict[str, Any] | None:
    """Load a complete checkpoint only when schema, phase and fingerprint all match."""

    if not path.is_file():
        return None
    try:
        payload = json.loads(gzip.decompress(path.read_bytes()).decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    if payload.get("schema_version") != RUN_CHECKPOINT_SCHEMA_VERSION:
        return None
    if payload.get("phase") != str(phase):
        return None
    if payload.get("fingerprint") != str(expected_fingerprint):
        return None
    result = payload.get("result")
    if not isinstance(result, dict) or not isinstance(result.get("row"), dict):
        return None
    if result["row"].get("status") != "ok":
        return None
    if require_trajectory and not isinstance(result.get("trajectory_run"), dict):
        return None
    try:
        result["index"] = int(result["index"])
    except (KeyError, TypeError, ValueError):
        return None
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Monte Carlo simulation analysis.")
    parser.add_argument(
        "--manifest-json",
        default="",
        help=(
            "Optional run_manifest.json. When provided, the Monte Carlo runner reuses the "
            "same simulation input, scenario and calibration options as the active baseline."
        ),
    )
    parser.add_argument(
        "--input",
        default="etudecas/simulation_prep/result/supply_graph_poc_simulation_ready.json",
        help="Simulation-ready graph JSON.",
    )
    parser.add_argument(
        "--run-script",
        default="etudecas/simulation/engine/run_first_simulation.py",
        help="Simulation runner script.",
    )
    parser.add_argument("--scenario-id", default="scn:BASE", help="Scenario id.")
    parser.add_argument(
        "--output-dir",
        default="etudecas/simulation/montecarlo/result",
        help="Monte Carlo result directory.",
    )
    parser.add_argument(
        "--days",
        type=int,
        default=30,
        help="Override simulation horizon in days (default: 30). Set 0 to keep scenario horizon.",
    )
    parser.add_argument(
        "--runs",
        type=int,
        default=120,
        help="Number of stochastic runs (excluding baseline run_0000).",
    )
    parser.add_argument("--seed", type=int, default=42, help="Random seed.")
    parser.add_argument(
        "--uncertainty-profile",
        choices=["workshop", "risk_probe", "stress_probe", "breakpoint_probe", "portfolio_probe", "legacy"],
        default="workshop",
        help=(
            "Sampling profile. workshop keeps perturbations close to operational uncertainty; "
            "risk_probe widens supplier-side uncertainty to reveal fragility; "
            "stress_probe is an exploratory but readable stress envelope, not a probability forecast; "
            "breakpoint_probe searches for severe failure thresholds; "
            "portfolio_probe alternates business families to produce diverse but readable trajectories; "
            "legacy keeps the older wider stress-style ranges."
        ),
    )
    parser.add_argument(
        "--sensitivity-calibration-json",
        default="",
        help=(
            "Optional calibration JSON produced from the current run sensitivity study. "
            "When the requested profile is weaker than the recommended profile, the runner "
            "uses the recommended profile and records the provenance in montecarlo_summary.json."
        ),
    )
    parser.add_argument(
        "--simulator-extra-arg",
        action="append",
        default=[],
        help="Additional argument passed to run_first_simulation.py. Repeat once per token.",
    )
    parser.add_argument(
        "--keep-run-artifacts",
        action="store_true",
        help="Keep per-run folders with full simulation outputs.",
    )
    parser.add_argument(
        "--save-trajectories",
        action="store_true",
        help="Write compact daily trajectories for uncertainty tube charts without keeping full run artifacts.",
    )
    parser.add_argument(
        "--trajectory-max-points",
        type=int,
        default=730,
        help="Maximum points per trajectory. Default 730 keeps long 5-year views compact. 0 keeps every simulated day.",
    )
    parser.add_argument(
        "--trajectory-display-runs",
        type=int,
        default=60,
        help=(
            "Maximum individual trajectories stored for display. Percentile bands are still "
            "computed from every successful run. 0 displays every run."
        ),
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=1,
        help="Parallel simulation workers. 1 keeps the historical sequential execution.",
    )
    parser.add_argument(
        "--resume",
        action=argparse.BooleanOptionalAction,
        default=True,
        help=(
            "Reuse successful compact per-run checkpoints whose simulation configuration "
            "and sampled run specification have the same fingerprint (default: enabled)."
        ),
    )
    parser.add_argument(
        "--paired-propagation",
        action=argparse.BooleanOptionalAction,
        default=None,
        help=(
            "Run controlled -u/nominal/+u experiments for the most influential supplier inputs. "
            "By default this is enabled when --save-trajectories is enabled."
        ),
    )
    parser.add_argument(
        "--paired-factor-count",
        type=int,
        default=8,
        help="Number of operational and economic inputs tested with controlled paired runs (default: 8).",
    )
    parser.add_argument(
        "--paired-background-count",
        type=int,
        default=20,
        help="Number of shared Monte Carlo contexts per paired input (default: 20).",
    )
    parser.add_argument(
        "--paired-input-uncertainty",
        type=float,
        default=0.20,
        help="Relative input uncertainty tested around nominal (default: 0.20, i.e. +/-20%%).",
    )
    parser.add_argument(
        "--nominal-lot-events-csv",
        default="",
        help=(
            "Optional production_lot_events.csv from the nominal run. When available, "
            "the controlled temporal propagation identifies the lots exposed during "
            "each impact window without treating lot genealogy as a random input."
        ),
    )
    parser.add_argument(
        "--include-systemic-supplier-reliability",
        action=argparse.BooleanOptionalAction,
        default=False,
        help=(
            "Vary one reliability multiplier across every supplier. Disabled by default because "
            "this represents a systemic stress rather than ordinary supplier uncertainty. "
            "Supplier-specific reliability remains varied."
        ),
    )
    return parser.parse_args()


def load_sensitivity_calibration(path: str | Path) -> dict[str, Any]:
    if not path:
        return {}
    candidate = Path(path)
    if not candidate.exists():
        candidate = REPO_ROOT / candidate
    if not candidate.exists():
        return {
            "status": "missing",
            "source_json": str(path),
            "recommended_profile": "",
            "reason": "Calibration path was supplied but not found.",
        }
    try:
        calibration = load_json(candidate)
    except Exception as exc:
        return {
            "status": "invalid",
            "source_json": str(candidate),
            "recommended_profile": "",
            "reason": f"Calibration could not be read: {exc}",
        }
    if isinstance(calibration, dict):
        calibration["source_json"] = str(candidate)
        return calibration
    return {"status": "invalid", "source_json": str(candidate), "recommended_profile": ""}


def effective_profile_from_calibration(requested_profile: str, calibration: dict[str, Any]) -> str:
    recommended = str(calibration.get("recommended_profile") or "").strip()
    if not recommended or recommended not in PROFILE_RANK:
        return requested_profile
    if PROFILE_RANK.get(recommended, 0) > PROFILE_RANK.get(requested_profile, 0):
        return recommended
    return requested_profile


def sample_factor(rng: random.Random, lo: float, mode: float, hi: float) -> float:
    return round(rng.triangular(lo, hi, mode), 6)


def detect_supplier_nodes(data: dict[str, Any]) -> list[str]:
    out: list[str] = []
    for n in data.get("nodes", []) or []:
        if str(n.get("type") or "").lower() == "supplier_dc":
            node_id = str(n.get("id") or "")
            if node_id:
                out.append(node_id)
    return sorted(set(out))


def detect_supplier_edge_sources(data: dict[str, Any]) -> list[str]:
    suppliers = set(detect_supplier_nodes(data))
    out: list[str] = []
    for e in data.get("edges", []) or []:
        src = str(e.get("from") or "")
        if src in suppliers:
            out.append(src)
    return sorted(set(out))


def extract_manifest_command(manifest_path: Path) -> dict[str, Any]:
    if not manifest_path.exists():
        raise FileNotFoundError(f"Manifest not found: {manifest_path}")
    manifest = load_json(manifest_path)
    command = [str(x) for x in (manifest.get("simulator_command") or [])]
    if not command:
        raise ValueError(f"No simulator_command found in manifest: {manifest_path}")

    script_idx = next((i for i, tok in enumerate(command) if tok.endswith("run_first_simulation.py")), None)
    if script_idx is None:
        script_idx = 1 if len(command) > 1 else 0
    run_script = Path(command[script_idx])

    input_path = Path(str(manifest.get("input_graph") or ""))
    nominal_output_dir = Path(str(manifest.get("output_dir") or ""))
    scenario_id = str(manifest.get("scenario_id") or "scn:BASE")
    manifest_days = int(to_float(manifest.get("days"), 0.0))
    extra_args: list[str] = []

    base_value_flags = {
        "--input",
        "--output-dir",
        "--scenario-id",
        "--days",
        "--map-script",
        "--map-output",
        "--output-profile",
    }
    base_bool_flags = {"--skip-map", "--skip-plots"}
    i = script_idx + 1
    while i < len(command):
        tok = command[i]
        if tok in base_value_flags:
            val = command[i + 1] if i + 1 < len(command) else ""
            if tok == "--input" and val:
                input_path = Path(val)
            elif tok == "--output-dir" and val:
                nominal_output_dir = Path(val)
            elif tok == "--scenario-id" and val:
                scenario_id = val
            elif tok == "--days" and val:
                manifest_days = int(to_float(val, manifest_days))
            i += 2
            continue
        if tok in base_bool_flags:
            i += 1
            continue
        extra_args.append(tok)
        if tok.startswith("--") and i + 1 < len(command) and not command[i + 1].startswith("--"):
            extra_args.append(command[i + 1])
            i += 2
        else:
            i += 1

    return {
        "manifest_path": str(manifest_path),
        "input_path": str(input_path),
        "run_script": str(run_script),
        "scenario_id": scenario_id,
        "manifest_days": manifest_days,
        "nominal_output_dir": str(nominal_output_dir),
        "simulator_extra_args": extra_args,
    }


def factor_specs(profile: str) -> tuple[dict[str, tuple[float, float, float]], tuple[float, float, float], tuple[float, float, float], tuple[float, float, float], tuple[float, float, float], tuple[float, float, float], tuple[float, float, float]]:
    if profile == "portfolio_probe":
        return factor_specs("risk_probe")
    if profile == "legacy":
        return (
            {
                "lead_time_scale": (0.8, 1.0, 1.3),
                "transport_cost_scale": (0.8, 1.0, 1.4),
                "supplier_stock_scale": (0.7, 1.0, 1.5),
                "production_stock_scale": (0.8, 1.0, 1.3),
            },
            (0.7, 1.0, 1.3),
            (0.7, 1.0, 1.3),
            (0.75, 1.0, 1.15),
            (0.75, 1.0, 1.15),
            (0.85, 1.0, 1.25),
            (0.95, 1.0, 1.0),
        )
    if profile == "risk_probe":
        return (
            {
                "demand_scale": (0.90, 1.0, 1.15),
                "lead_time_scale": (0.90, 1.0, 1.50),
                "transport_cost_scale": (0.90, 1.0, 1.20),
                "supplier_stock_scale": (0.60, 1.0, 1.10),
                "production_stock_scale": (0.85, 1.0, 1.05),
                "supplier_capacity_scale": (0.60, 1.0, 1.05),
                "supplier_reliability_scale": (0.90, 1.0, 1.0),
                "external_procurement_daily_cap_days_scale": (0.60, 1.0, 1.05),
                "external_procurement_lead_days_scale": (0.90, 1.0, 1.60),
                "holding_cost_scale": (0.90, 1.0, 1.12),
            },
            (0.85, 1.0, 1.20),
            (0.85, 1.0, 1.05),
            (0.50, 1.0, 1.10),
            (0.60, 1.0, 1.05),
            (0.90, 1.0, 1.80),
            (0.90, 1.0, 1.0),
        )
    if profile == "stress_probe":
        return (
            {
                "demand_scale": (0.98, 1.10, 1.30),
                "lead_time_scale": (1.00, 1.25, 2.00),
                "transport_cost_scale": (1.00, 1.20, 1.70),
                "supplier_stock_scale": (0.25, 0.65, 1.00),
                "production_stock_scale": (0.65, 0.85, 1.00),
                "capacity_scale": (0.60, 0.82, 1.00),
                "supplier_capacity_scale": (0.25, 0.60, 1.00),
                "supplier_reliability_scale": (0.65, 0.85, 1.00),
                "external_procurement_daily_cap_days_scale": (0.20, 0.60, 1.00),
                "external_procurement_lead_days_scale": (1.00, 1.45, 2.50),
                "external_procurement_cost_multiplier_scale": (1.00, 1.35, 2.50),
                "external_procurement_transport_cost_scale": (1.00, 1.35, 2.20),
                "purchase_cost_floor_scale": (1.00, 1.20, 1.80),
                "holding_cost_scale": (0.90, 1.10, 1.50),
            },
            (0.95, 1.08, 1.35),
            (0.55, 0.80, 1.00),
            (0.20, 0.60, 1.00),
            (0.20, 0.55, 0.95),
            (1.00, 1.50, 2.50),
            (0.65, 0.85, 1.00),
        )
    if profile == "breakpoint_probe":
        return (
            {
                "demand_scale": (1.00, 1.18, 1.45),
                "lead_time_scale": (1.00, 1.45, 2.80),
                "transport_cost_scale": (1.00, 1.35, 2.20),
                "supplier_stock_scale": (0.10, 0.45, 0.95),
                "production_stock_scale": (0.45, 0.75, 1.00),
                "capacity_scale": (0.45, 0.70, 1.00),
                "supplier_capacity_scale": (0.10, 0.45, 0.95),
                "supplier_reliability_scale": (0.45, 0.75, 1.00),
                "external_procurement_daily_cap_days_scale": (0.05, 0.25, 0.80),
                "external_procurement_lead_days_scale": (1.00, 2.00, 4.00),
                "external_procurement_cost_multiplier_scale": (1.00, 1.80, 4.00),
                "external_procurement_transport_cost_scale": (1.00, 1.80, 3.00),
                "purchase_cost_floor_scale": (1.00, 1.40, 2.20),
                "holding_cost_scale": (0.90, 1.20, 1.80),
            },
            (0.95, 1.15, 1.60),
            (0.35, 0.70, 1.00),
            (0.05, 0.40, 1.00),
            (0.05, 0.35, 0.90),
            (1.00, 1.80, 3.50),
            (0.45, 0.75, 1.00),
        )
    return (
        {
            "demand_scale": (0.96, 1.0, 1.06),
            "lead_time_scale": (0.95, 1.0, 1.15),
            "transport_cost_scale": (0.95, 1.0, 1.10),
            "supplier_stock_scale": (0.85, 1.0, 1.05),
            "production_stock_scale": (0.90, 1.0, 1.05),
            "supplier_capacity_scale": (0.85, 1.0, 1.05),
            "external_procurement_daily_cap_days_scale": (0.85, 1.0, 1.05),
            "external_procurement_lead_days_scale": (0.95, 1.0, 1.20),
            "holding_cost_scale": (0.95, 1.0, 1.08),
        },
        (0.95, 1.0, 1.08),
        (0.90, 1.0, 1.05),
        (0.85, 1.0, 1.05),
        (0.85, 1.0, 1.05),
        (0.95, 1.0, 1.20),
        (0.97, 1.0, 1.0),
    )


def portfolio_family_for_run(stochastic_index: int) -> str:
    return PORTFOLIO_PROBE_FAMILIES[stochastic_index % len(PORTFOLIO_PROBE_FAMILIES)]


def portfolio_family_label(family: str) -> str:
    return PORTFOLIO_PROBE_FAMILY_LABELS.get(str(family), str(family))


def _blend_to_neutral(value: float, strength: float) -> float:
    """Keep a secondary perturbation but reduce it toward the nominal value."""

    return round(1.0 + (float(value) - 1.0) * max(0.0, min(1.0, strength)), 6)


def _sample_focus_set(rng: random.Random, candidates: list[str], min_count: int, max_count: int) -> set[str]:
    if not candidates:
        return set()
    hi = min(len(candidates), max(1, int(max_count)))
    lo = min(hi, max(1, int(min_count)))
    count = rng.randint(lo, hi)
    return set(rng.sample(candidates, count))


def _sample_mixed_focus_set(
    rng: random.Random,
    *,
    candidates: list[str],
    preferred: list[str],
    min_count: int,
    max_count: int,
    preferred_probability: float = 0.75,
) -> set[str]:
    """Sample a portfolio focus while regularly exercising critical lanes.

    Pure random sampling over every supplier is too often absorbed by stock.
    This keeps broad coverage but makes sure the Monte Carlo also touches
    suppliers/items connected to demanded finished products.
    """

    if not candidates:
        return set()
    hi = min(len(candidates), max(1, int(max_count)))
    lo = min(hi, max(1, int(min_count)))
    count = rng.randint(lo, hi)
    selected: set[str] = set()
    preferred_pool = [x for x in preferred if x in candidates]
    if preferred_pool and rng.random() < preferred_probability:
        preferred_count = min(len(preferred_pool), max(1, int(round(count * 0.65))))
        selected.update(rng.sample(preferred_pool, preferred_count))
    remaining_pool = [x for x in candidates if x not in selected]
    if len(selected) < count and remaining_pool:
        selected.update(rng.sample(remaining_pool, min(len(remaining_pool), count - len(selected))))
    return selected


def _process_outputs(process: dict[str, Any]) -> list[str]:
    return [str(o.get("item_id")) for o in (process.get("outputs") or []) if o.get("item_id") is not None]


def _process_inputs(process: dict[str, Any]) -> list[str]:
    return [str(i.get("item_id")) for i in (process.get("inputs") or []) if i.get("item_id") is not None]


def detect_portfolio_priority_targets(data: dict[str, Any], scenario_id: str) -> dict[str, list[str]]:
    """Infer critical supplier/item targets from demanded PF and their BOM.

    This is intentionally graph-based and study-agnostic: start from demand
    items, walk upstream through production processes, and collect suppliers
    that feed the required inputs into the producing site.
    """

    demand_items = detect_demand_items(data, scenario_id)
    supplier_nodes = set(detect_supplier_nodes(data))
    supplier_edges: list[dict[str, Any]] = [
        e for e in (data.get("edges") or []) if str(e.get("from") or "") in supplier_nodes
    ]
    supply_sources_by_site_item: dict[tuple[str, str], set[str]] = {}
    for edge in supplier_edges:
        src = str(edge.get("from") or "")
        dst = str(edge.get("to") or "")
        for edge_item in edge.get("items") or []:
            supply_sources_by_site_item.setdefault((dst, str(edge_item)), set()).add(src)
    processes_by_output: dict[str, list[tuple[str, dict[str, Any]]]] = {}
    for node in data.get("nodes", []) or []:
        node_id = str(node.get("id") or "")
        for process in node.get("processes") or []:
            for output_item in _process_outputs(process):
                processes_by_output.setdefault(output_item, []).append((node_id, process))

    critical_items: set[str] = set(demand_items)
    critical_suppliers: set[str] = set()
    high_priority_suppliers: set[str] = set()
    single_source_supply_items: set[str] = set()
    stack = [(item, 0) for item in demand_items]
    seen: set[tuple[str, int]] = set()
    while stack:
        item_id, depth = stack.pop()
        if (item_id, depth) in seen or depth > 4:
            continue
        seen.add((item_id, depth))
        for node_id, process in processes_by_output.get(item_id, []):
            for input_item in _process_inputs(process):
                critical_items.add(input_item)
                for edge in supplier_edges:
                    if str(edge.get("to") or "") != node_id:
                        continue
                    edge_items = {str(x) for x in (edge.get("items") or [])}
                    if input_item in edge_items:
                        critical_suppliers.add(str(edge.get("from") or ""))
                sources = supply_sources_by_site_item.get((node_id, input_item), set())
                if len(sources) == 1:
                    high_priority_suppliers.update(sources)
                    single_source_supply_items.add(input_item)
                if input_item in processes_by_output:
                    stack.append((input_item, depth + 1))

    return {
        "critical_demand_items": sorted(set(demand_items)),
        "critical_supply_items": sorted(critical_items),
        "critical_suppliers": sorted(critical_suppliers),
        "high_priority_suppliers": sorted(high_priority_suppliers),
        "single_source_supply_items": sorted(single_source_supply_items),
    }


def portfolio_focus_sets(
    *,
    family: str,
    rng: random.Random,
    demand_items: list[str],
    supplier_nodes: list[str],
    supplier_edge_sources: list[str],
    critical_suppliers: list[str] | None = None,
    critical_demand_items: list[str] | None = None,
) -> tuple[set[str], set[str], float]:
    """Select where the dominant uncertainty is applied for one portfolio run.

    The non-selected nodes still keep a weak background perturbation. This is
    closer to a portfolio uncertainty study: one cause dominates, while the
    rest of the network is not perfectly deterministic.
    """

    supplier_candidates = sorted(set(supplier_nodes) | set(supplier_edge_sources))
    preferred_suppliers = sorted(set(critical_suppliers or []) & set(supplier_candidates))
    preferred_demand_items = sorted(set(critical_demand_items or []) & set(demand_items))
    focus_suppliers: set[str] = set()
    focus_items: set[str] = set()
    secondary_strength = 0.25

    if family in {"supplier_delay", "supplier_stock", "supplier_capacity", "supplier_reliability_quality"}:
        focus_suppliers = _sample_mixed_focus_set(
            rng,
            candidates=supplier_candidates,
            preferred=preferred_suppliers,
            min_count=1,
            max_count=4,
        )
        secondary_strength = 0.18
    elif family == "inbound_logistics":
        focus_suppliers = _sample_mixed_focus_set(
            rng,
            candidates=supplier_candidates,
            preferred=preferred_suppliers,
            min_count=2,
            max_count=6,
        )
        secondary_strength = 0.25
    elif family in {"combined_moderate", "combined_severe"}:
        focus_suppliers = _sample_mixed_focus_set(
            rng,
            candidates=supplier_candidates,
            preferred=preferred_suppliers,
            min_count=3,
            max_count=8,
        )
        focus_items = _sample_mixed_focus_set(
            rng,
            candidates=demand_items,
            preferred=preferred_demand_items,
            min_count=1,
            max_count=min(2, len(demand_items) or 1),
        )
        secondary_strength = 0.18 if family == "combined_moderate" else 0.25
    elif family in {"demand_peak", "demand_mix"}:
        focus_items = _sample_mixed_focus_set(
            rng,
            candidates=demand_items,
            preferred=preferred_demand_items,
            min_count=1,
            max_count=min(2, len(demand_items) or 1),
        )
        secondary_strength = 0.10
    elif family == "cost_inflation":
        focus_suppliers = _sample_mixed_focus_set(
            rng,
            candidates=supplier_candidates,
            preferred=preferred_suppliers,
            min_count=2,
            max_count=5,
        )
        secondary_strength = 0.12
    elif family == "near_nominal":
        secondary_strength = 0.10

    return focus_suppliers, focus_items, secondary_strength


def attenuate_non_focus(values: dict[str, float], focus: set[str], strength: float) -> dict[str, float]:
    if not values or not focus:
        return values
    return {
        key: value if key in focus else _blend_to_neutral(value, strength)
        for key, value in values.items()
    }


def portfolio_factor_specs(family: str) -> tuple[dict[str, tuple[float, float, float]], tuple[float, float, float], tuple[float, float, float], tuple[float, float, float], tuple[float, float, float], tuple[float, float, float], tuple[float, float, float]]:
    """Return one Monte Carlo family for a supplier-risk portfolio run.

    Each stochastic run stresses one interpretable business mechanism instead
    of degrading every lever at once. Each run still receives a smaller
    secondary perturbation, because real supply risks rarely move one parameter
    in isolation.
    """

    neutral = (1.0, 1.0, 1.0)
    mild_low = (0.92, 1.0, 1.05)
    mild_high = (0.98, 1.03, 1.15)
    global_spec: dict[str, tuple[float, float, float]] = {
        "demand_scale": neutral,
        "lead_time_scale": neutral,
        "transport_cost_scale": neutral,
        "supplier_stock_scale": neutral,
        "production_stock_scale": neutral,
        "capacity_scale": neutral,
        "supplier_capacity_scale": neutral,
        "supplier_reliability_scale": neutral,
        "external_procurement_daily_cap_days_scale": neutral,
        "external_procurement_lead_days_scale": neutral,
        "external_procurement_cost_multiplier_scale": neutral,
        "external_procurement_transport_cost_scale": neutral,
        "purchase_cost_floor_scale": neutral,
        "holding_cost_scale": neutral,
    }
    demand_spec = neutral
    production_capacity_spec = neutral
    supplier_stock_spec = neutral
    supplier_capacity_spec = neutral
    supplier_lead_spec = neutral
    supplier_reliability_spec = neutral

    if family == "near_nominal":
        global_spec.update(
            {
                "demand_scale": (0.99, 1.0, 1.02),
                "lead_time_scale": (0.99, 1.0, 1.04),
                "supplier_stock_scale": (0.98, 1.0, 1.02),
                "supplier_capacity_scale": (0.98, 1.0, 1.02),
                "supplier_reliability_scale": (0.985, 1.0, 1.0),
                "holding_cost_scale": (0.98, 1.0, 1.04),
            }
        )
        demand_spec = (0.99, 1.0, 1.02)
        supplier_stock_spec = (0.98, 1.0, 1.02)
        supplier_capacity_spec = (0.98, 1.0, 1.02)
        supplier_lead_spec = (0.99, 1.0, 1.04)
        supplier_reliability_spec = (0.985, 1.0, 1.0)
    elif family == "demand_peak":
        global_spec.update(
            {
                "demand_scale": (1.00, 1.10, 1.28),
                "holding_cost_scale": mild_high,
            }
        )
        demand_spec = (1.00, 1.12, 1.35)
        supplier_stock_spec = neutral
        supplier_capacity_spec = neutral
    elif family == "demand_mix":
        global_spec.update(
            {
                "demand_scale": (0.96, 1.0, 1.10),
            }
        )
        demand_spec = (0.75, 1.10, 1.55)
        supplier_stock_spec = neutral
    elif family == "supplier_delay":
        global_spec.update(
            {
                "lead_time_scale": (1.00, 1.02, 1.12),
                "external_procurement_lead_days_scale": (1.00, 1.08, 1.35),
                "transport_cost_scale": (1.00, 1.05, 1.20),
            }
        )
        supplier_lead_spec = (1.00, 1.85, 3.80)
        supplier_capacity_spec = neutral
    elif family == "supplier_stock":
        global_spec.update(
            {
                "external_procurement_daily_cap_days_scale": (0.90, 1.0, 1.05),
                "external_procurement_lead_days_scale": (1.00, 1.05, 1.20),
            }
        )
        supplier_stock_spec = (0.05, 0.42, 1.00)
        supplier_lead_spec = neutral
    elif family == "supplier_capacity":
        global_spec.update(
            {
                "external_procurement_daily_cap_days_scale": (0.55, 0.85, 1.05),
            }
        )
        supplier_capacity_spec = (0.05, 0.38, 1.00)
    elif family == "supplier_reliability_quality":
        global_spec.update(
            {
                "lead_time_scale": (1.00, 1.04, 1.20),
                "external_procurement_cost_multiplier_scale": (1.00, 1.15, 1.80),
                "purchase_cost_floor_scale": (1.00, 1.08, 1.45),
            }
        )
        supplier_reliability_spec = (0.35, 0.72, 1.00)
    elif family == "inbound_logistics":
        global_spec.update(
            {
                "lead_time_scale": (1.00, 1.08, 1.30),
                "transport_cost_scale": (1.00, 1.30, 2.30),
                "external_procurement_lead_days_scale": (1.00, 1.18, 1.80),
                "external_procurement_transport_cost_scale": (1.00, 1.45, 2.80),
            }
        )
        supplier_lead_spec = (1.00, 1.70, 3.50)
    elif family == "cost_inflation":
        global_spec.update(
            {
                "transport_cost_scale": (1.00, 1.35, 2.20),
                "external_procurement_cost_multiplier_scale": (1.00, 1.80, 3.50),
                "external_procurement_transport_cost_scale": (1.00, 1.50, 3.00),
                "purchase_cost_floor_scale": (1.00, 1.35, 2.40),
                "holding_cost_scale": (0.90, 1.20, 1.80),
            }
        )
        supplier_lead_spec = neutral
        supplier_reliability_spec = neutral
    elif family == "combined_moderate":
        global_spec.update(
            {
                "demand_scale": (0.98, 1.08, 1.25),
                "lead_time_scale": (1.00, 1.12, 1.60),
                "transport_cost_scale": (1.00, 1.15, 1.60),
                "supplier_stock_scale": (0.75, 0.95, 1.05),
                "supplier_capacity_scale": (0.70, 0.92, 1.05),
                "supplier_reliability_scale": (0.78, 0.95, 1.00),
                "external_procurement_daily_cap_days_scale": (0.50, 0.80, 1.00),
                "external_procurement_lead_days_scale": (1.00, 1.25, 2.20),
                "external_procurement_cost_multiplier_scale": (1.00, 1.25, 2.00),
                "external_procurement_transport_cost_scale": (1.00, 1.20, 2.00),
                "purchase_cost_floor_scale": (1.00, 1.15, 1.70),
                "holding_cost_scale": (0.95, 1.08, 1.40),
            }
        )
        demand_spec = (0.95, 1.08, 1.35)
        supplier_stock_spec = (0.10, 0.45, 1.00)
        supplier_capacity_spec = (0.10, 0.45, 1.00)
        supplier_lead_spec = (1.00, 1.60, 3.20)
        supplier_reliability_spec = (0.45, 0.75, 1.00)
    elif family == "combined_severe":
        global_spec.update(
            {
                "demand_scale": (1.00, 1.12, 1.40),
                "lead_time_scale": (1.00, 1.20, 2.20),
                "transport_cost_scale": (1.00, 1.25, 2.20),
                "supplier_stock_scale": (0.55, 0.85, 1.00),
                "supplier_capacity_scale": (0.50, 0.80, 1.00),
                "supplier_reliability_scale": (0.65, 0.88, 1.00),
                "external_procurement_daily_cap_days_scale": (0.25, 0.60, 1.00),
                "external_procurement_lead_days_scale": (1.00, 1.45, 3.00),
                "external_procurement_cost_multiplier_scale": (1.00, 1.50, 3.00),
                "external_procurement_transport_cost_scale": (1.00, 1.45, 2.80),
                "purchase_cost_floor_scale": (1.00, 1.25, 2.00),
                "holding_cost_scale": (0.95, 1.15, 1.60),
            }
        )
        demand_spec = (1.00, 1.12, 1.45)
        supplier_stock_spec = (0.05, 0.35, 0.95)
        supplier_capacity_spec = (0.05, 0.35, 0.95)
        supplier_lead_spec = (1.00, 1.90, 3.80)
        supplier_reliability_spec = (0.30, 0.65, 1.00)

    return (
        global_spec,
        demand_spec,
        production_capacity_spec,
        supplier_stock_spec,
        supplier_capacity_spec,
        supplier_lead_spec,
        supplier_reliability_spec,
    )


def metric_probability(rows: list[dict[str, Any]], metric: str, predicate) -> float | None:
    values = [to_float(r.get(metric), float("nan")) for r in rows if r.get("status") == "ok"]
    values = [v for v in values if not math.isnan(v)]
    if not values:
        return None
    return sum(1 for v in values if predicate(v)) / float(len(values))


def arg_value(args: list[str], flag: str) -> str:
    for i, token in enumerate(args):
        if token == flag and i + 1 < len(args):
            return args[i + 1]
    return ""


def replace_arg_value(args: list[str], flag: str, value: str) -> list[str]:
    out = list(args)
    for i, token in enumerate(out):
        if token == flag and i + 1 < len(out):
            out[i + 1] = value
            return out
    out.extend([flag, value])
    return out


def scaled_value(raw: Any, factor: float, *, minimum: float = 0.0) -> str:
    value = to_float(raw, float("nan"))
    if math.isnan(value):
        return str(raw if raw is not None else "")
    return str(round(max(minimum, value * factor), 6))


def write_scaled_supplier_neutral_floors(
    source_csv: Path,
    target_csv: Path,
    *,
    factors: dict[str, float],
    supplier_node_scale: dict[str, float],
    supplier_capacity_node_scale: dict[str, float],
    edge_src_lead_time_scale: dict[str, float],
    edge_src_reliability_scale: dict[str, float],
    supplier_stock_pair_scale: dict[str, float] | None = None,
    supplier_capacity_pair_scale: dict[str, float] | None = None,
    edge_pair_lead_time_scale: dict[str, float] | None = None,
    edge_pair_reliability_scale: dict[str, float] | None = None,
) -> bool:
    if not source_csv.exists():
        return False
    target_csv.parent.mkdir(parents=True, exist_ok=True)
    stock_cols = {
        "neutral_opening_stock_floor_qty",
        "simulated_opening_stock_qty",
        "base_stock_qty",
    }
    capacity_cols = {
        "neutral_capacity_floor_qty_per_day",
        "effective_capacity_qty_per_day",
        "tested_capacity_floor_qty_per_day",
        "external_procurement_nominal_capacity_qty_per_day",
    }
    lead_cols = {
        "planned_lead_time_days",
        "lead_reference_days",
        "lead_cover_days",
        "delay_step_limit",
        "external_procurement_lead_days",
    }
    pipeline_cols = {
        "external_procurement_pipeline_target_qty",
        "external_procurement_initial_pipeline_seed_qty",
    }
    reliability_cols = {"nominal_reliability_otif"}
    supplier_stock_pair_scale = supplier_stock_pair_scale or {}
    supplier_capacity_pair_scale = supplier_capacity_pair_scale or {}
    edge_pair_lead_time_scale = edge_pair_lead_time_scale or {}
    edge_pair_reliability_scale = edge_pair_reliability_scale or {}

    with source_csv.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        fieldnames = list(reader.fieldnames or [])

    for row in rows:
        supplier_id = str(row.get("supplier_id") or "")
        destination_id = str(row.get("dst_node_id") or "")
        item_id = str(row.get("item_id") or "")
        pair_key = f"{supplier_id}|{destination_id}|{item_id}"
        stock_factor = to_float(factors.get("supplier_stock_scale"), 1.0) * to_float(
            supplier_node_scale.get(supplier_id), 1.0
        ) * to_float(supplier_stock_pair_scale.get(pair_key), 1.0)
        capacity_factor = to_float(factors.get("supplier_capacity_scale"), 1.0) * to_float(
            supplier_capacity_node_scale.get(supplier_id), 1.0
        ) * to_float(supplier_capacity_pair_scale.get(pair_key), 1.0)
        lead_factor = to_float(factors.get("lead_time_scale"), 1.0) * to_float(
            edge_src_lead_time_scale.get(supplier_id), 1.0
        ) * to_float(edge_pair_lead_time_scale.get(pair_key), 1.0)
        reliability_factor = to_float(factors.get("supplier_reliability_scale"), 1.0) * to_float(
            edge_src_reliability_scale.get(supplier_id), 1.0
        ) * to_float(edge_pair_reliability_scale.get(pair_key), 1.0)
        for col in stock_cols:
            if col in row:
                row[col] = scaled_value(row.get(col), stock_factor)
        for col in capacity_cols:
            if col in row:
                row[col] = scaled_value(row.get(col), capacity_factor)
        for col in lead_cols:
            if col in row:
                row[col] = scaled_value(row.get(col), lead_factor, minimum=1.0)
        for col in pipeline_cols:
            if col in row:
                row[col] = scaled_value(row.get(col), lead_factor)
        for col in reliability_cols:
            if col in row:
                value = to_float(row.get(col), float("nan"))
                if not math.isnan(value):
                    row[col] = str(round(min(1.0, max(0.01, value * reliability_factor)), 6))

    with target_csv.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    return True


def execute_run_spec(
    spec: dict[str, Any],
    *,
    base_data: dict[str, Any],
    scenario_id: str,
    run_script: Path,
    days: int,
    simulator_extra_args: list[str],
    keep_run_artifacts: bool,
    runs_dir: Path,
    save_trajectories: bool,
    trajectory_max_points: int,
) -> dict[str, Any]:
    """Execute one Monte Carlo simulation run.

    The random factors are prepared before this function is called, so parallel
    execution remains reproducible for a fixed seed.
    """

    run_id = str(spec["run_id"])
    row = dict(spec["row"])
    trajectory_run: dict[str, Any] | None = None

    try:
        mutated = apply_scales(
            base_data=base_data,
            scenario_id=scenario_id,
            factors=spec["factors"],
            demand_item_scale=spec["demand_item_scale"],
            capacity_node_scale=spec["capacity_node_scale"],
            supplier_node_scale=spec["supplier_node_scale"],
            supplier_capacity_node_scale=spec["supplier_capacity_node_scale"],
            edge_src_lead_time_scale=spec["edge_src_lead_time_scale"],
            edge_src_reliability_scale=spec["edge_src_reliability_scale"],
            supplier_stock_pair_scale=spec.get("supplier_stock_pair_scale", {}),
            supplier_capacity_pair_scale=spec.get("supplier_capacity_pair_scale", {}),
            edge_pair_lead_time_scale=spec.get("edge_pair_lead_time_scale", {}),
            edge_pair_reliability_scale=spec.get("edge_pair_reliability_scale", {}),
        )

        if keep_run_artifacts:
            case_dir = runs_dir / run_id
            case_dir.mkdir(parents=True, exist_ok=True)
            case_input = case_dir / "input_case.json"
            case_output = case_dir / "simulation_output"
            run_extra_args = list(simulator_extra_args)
            neutral_floors_csv = arg_value(run_extra_args, "--supplier-neutral-floors-csv")
            if neutral_floors_csv:
                case_neutral_floors = case_dir / "supplier_neutral_floors_case.csv"
                wrote_neutral_floors = write_scaled_supplier_neutral_floors(
                    Path(neutral_floors_csv),
                    case_neutral_floors,
                    factors=spec["factors"],
                    supplier_node_scale=spec["supplier_node_scale"],
                    supplier_capacity_node_scale=spec["supplier_capacity_node_scale"],
                    edge_src_lead_time_scale=spec["edge_src_lead_time_scale"],
                    edge_src_reliability_scale=spec["edge_src_reliability_scale"],
                    supplier_stock_pair_scale=spec.get("supplier_stock_pair_scale", {}),
                    supplier_capacity_pair_scale=spec.get("supplier_capacity_pair_scale", {}),
                    edge_pair_lead_time_scale=spec.get("edge_pair_lead_time_scale", {}),
                    edge_pair_reliability_scale=spec.get("edge_pair_reliability_scale", {}),
                )
                if wrote_neutral_floors:
                    run_extra_args = replace_arg_value(
                        run_extra_args,
                        "--supplier-neutral-floors-csv",
                        str(case_neutral_floors),
                    )
            write_json(case_input, mutated)
            summary, _ = run_simulation(
                run_script=run_script,
                input_json=case_input,
                output_dir=case_output,
                scenario_id=scenario_id,
                days=days,
                skip_map=True,
                skip_plots=True,
                extra_args=run_extra_args,
            )
            if save_trajectories:
                series = extract_run_trajectories(
                    case_output,
                    max_points=max(0, int(trajectory_max_points)),
                )
                if series:
                    trajectory_run = {
                        "run_id": run_id,
                        "label": "Nominal" if bool(spec["is_baseline"]) else f"{portfolio_family_label(str(spec.get('scenario_family', 'global')))} - {run_id}",
                        "is_baseline": bool(spec["is_baseline"]),
                        "scenario_family": str(spec.get("scenario_family") or ""),
                        "series": series,
                    }
            row["case_dir"] = str(case_dir)
        else:
            with tempfile.TemporaryDirectory(prefix=f"mc_{safe_name(run_id)}_") as tmp:
                case_dir = Path(tmp)
                case_input = case_dir / "input_case.json"
                case_output = case_dir / "simulation_output"
                run_extra_args = list(simulator_extra_args)
                neutral_floors_csv = arg_value(run_extra_args, "--supplier-neutral-floors-csv")
                if neutral_floors_csv:
                    case_neutral_floors = case_dir / "supplier_neutral_floors_case.csv"
                    wrote_neutral_floors = write_scaled_supplier_neutral_floors(
                        Path(neutral_floors_csv),
                        case_neutral_floors,
                        factors=spec["factors"],
                        supplier_node_scale=spec["supplier_node_scale"],
                        supplier_capacity_node_scale=spec["supplier_capacity_node_scale"],
                        edge_src_lead_time_scale=spec["edge_src_lead_time_scale"],
                        edge_src_reliability_scale=spec["edge_src_reliability_scale"],
                        supplier_stock_pair_scale=spec.get("supplier_stock_pair_scale", {}),
                        supplier_capacity_pair_scale=spec.get("supplier_capacity_pair_scale", {}),
                        edge_pair_lead_time_scale=spec.get("edge_pair_lead_time_scale", {}),
                        edge_pair_reliability_scale=spec.get("edge_pair_reliability_scale", {}),
                    )
                    if wrote_neutral_floors:
                        run_extra_args = replace_arg_value(
                            run_extra_args,
                            "--supplier-neutral-floors-csv",
                            str(case_neutral_floors),
                        )
                write_json(case_input, mutated)
                summary, _ = run_simulation(
                    run_script=run_script,
                    input_json=case_input,
                    output_dir=case_output,
                    scenario_id=scenario_id,
                    days=days,
                    skip_map=True,
                    skip_plots=True,
                    extra_args=run_extra_args,
                )
                if save_trajectories:
                    series = extract_run_trajectories(
                        case_output,
                        max_points=max(0, int(trajectory_max_points)),
                    )
                    if series:
                        trajectory_run = {
                            "run_id": run_id,
                            "label": "Nominal" if bool(spec["is_baseline"]) else f"{portfolio_family_label(str(spec.get('scenario_family', 'global')))} - {run_id}",
                            "is_baseline": bool(spec["is_baseline"]),
                            "scenario_family": str(spec.get("scenario_family") or ""),
                            "series": series,
                        }
            row["case_dir"] = ""

        for k, v in numeric_kpis(summary).items():
            row[f"kpi::{k}"] = v
    except Exception as exc:
        row["status"] = "failed"
        row["error"] = str(exc)

    return {"index": int(spec["index"]), "row": row, "trajectory_run": trajectory_run}


def main() -> None:
    args = parse_args()
    manifest_config: dict[str, Any] = {}
    if args.manifest_json:
        manifest_config = extract_manifest_command(Path(args.manifest_json))

    input_path = Path(manifest_config.get("input_path") or args.input)
    run_script = Path(manifest_config.get("run_script") or args.run_script)
    scenario_id = str(manifest_config.get("scenario_id") or args.scenario_id)
    simulator_extra_args = list(manifest_config.get("simulator_extra_args") or [])
    simulator_extra_args.extend(str(arg) for arg in (args.simulator_extra_arg or []))
    supplier_neutral_floors_csv = arg_value(simulator_extra_args, "--supplier-neutral-floors-csv")
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    runs_dir = output_dir / "runs"
    if args.keep_run_artifacts:
        runs_dir.mkdir(parents=True, exist_ok=True)
    checkpoints_dir = output_dir / "checkpoints"
    main_checkpoint_config = build_checkpoint_config(
        input_path=input_path,
        run_script=run_script,
        scenario_id=scenario_id,
        days=int(args.days),
        simulator_extra_args=simulator_extra_args,
        keep_run_artifacts=bool(args.keep_run_artifacts),
        save_trajectories=bool(args.save_trajectories),
        trajectory_max_points=max(0, int(args.trajectory_max_points)),
    )

    base_data = load_json(input_path)
    demand_items = detect_demand_items(base_data, scenario_id)
    production_nodes = detect_production_nodes(base_data)
    supplier_nodes = detect_supplier_nodes(base_data)
    supplier_edge_sources = detect_supplier_edge_sources(base_data)
    portfolio_priority_targets = detect_portfolio_priority_targets(base_data, scenario_id)
    critical_suppliers = (
        portfolio_priority_targets.get("high_priority_suppliers")
        or portfolio_priority_targets.get("critical_suppliers", [])
    )
    critical_demand_items = portfolio_priority_targets.get("critical_demand_items", [])

    rng = random.Random(args.seed)
    sensitivity_calibration = load_sensitivity_calibration(args.sensitivity_calibration_json)
    effective_uncertainty_profile = effective_profile_from_calibration(
        str(args.uncertainty_profile),
        sensitivity_calibration,
    )

    # Triangular distributions (lo, mode, hi).
    (
        global_factor_spec,
        demand_spec_default,
        production_capacity_spec_default,
        supplier_stock_spec_default,
        supplier_capacity_spec_default,
        supplier_lead_spec_default,
        supplier_reliability_spec_default,
    ) = factor_specs(effective_uncertainty_profile)
    if not args.include_systemic_supplier_reliability:
        global_factor_spec = dict(global_factor_spec)
        global_factor_spec["supplier_reliability_scale"] = (1.0, 1.0, 1.0)
    demand_factor_spec: dict[str, tuple[float, float, float]] = {
        item: demand_spec_default for item in demand_items
    }
    capacity_factor_spec: dict[str, tuple[float, float, float]] = {
        node: production_capacity_spec_default for node in production_nodes
    }
    supplier_stock_factor_spec: dict[str, tuple[float, float, float]] = {
        node: supplier_stock_spec_default for node in supplier_nodes
    }
    supplier_capacity_factor_spec: dict[str, tuple[float, float, float]] = {
        node: supplier_capacity_spec_default for node in supplier_nodes
    }
    supplier_lead_factor_spec: dict[str, tuple[float, float, float]] = {
        node: supplier_lead_spec_default for node in supplier_edge_sources
    }
    supplier_reliability_factor_spec: dict[str, tuple[float, float, float]] = {
        node: supplier_reliability_spec_default for node in supplier_edge_sources
    }

    total_runs = 1 + max(0, int(args.runs))  # baseline + stochastic
    rows: list[dict[str, Any]] = []
    trajectory_runs: list[dict[str, Any]] = []
    run_specs: list[dict[str, Any]] = []

    for i in range(total_runs):
        run_id = f"run_{i:04d}"
        is_baseline = i == 0
        scenario_family = "nominal" if is_baseline else "global"

        factors = {
            "demand_scale": 1.0,
            "lead_time_scale": 1.0,
            "transport_cost_scale": 1.0,
            "supplier_stock_scale": 1.0,
            "production_stock_scale": 1.0,
            "capacity_scale": 1.0,
            "supplier_capacity_scale": 1.0,
            "supplier_reliability_scale": 1.0,
            "external_procurement_daily_cap_days_scale": 1.0,
            "external_procurement_lead_days_scale": 1.0,
            "external_procurement_cost_multiplier_scale": 1.0,
            "external_procurement_transport_cost_scale": 1.0,
            "purchase_cost_floor_scale": 1.0,
            "holding_cost_scale": 1.0,
        }
        demand_item_scale = {item: 1.0 for item in demand_items}
        capacity_node_scale = {node: 1.0 for node in production_nodes}
        supplier_node_scale = {node: 1.0 for node in supplier_nodes}
        supplier_capacity_node_scale = {node: 1.0 for node in supplier_nodes}
        edge_src_lead_time_scale = {node: 1.0 for node in supplier_edge_sources}
        edge_src_reliability_scale = {node: 1.0 for node in supplier_edge_sources}

        if not is_baseline:
            active_global_factor_spec = global_factor_spec
            active_demand_factor_spec = demand_factor_spec
            active_capacity_factor_spec = capacity_factor_spec
            active_supplier_stock_factor_spec = supplier_stock_factor_spec
            active_supplier_capacity_factor_spec = supplier_capacity_factor_spec
            active_supplier_lead_factor_spec = supplier_lead_factor_spec
            active_supplier_reliability_factor_spec = supplier_reliability_factor_spec
            portfolio_focus_suppliers: set[str] = set()
            portfolio_focus_demand_items: set[str] = set()
            portfolio_secondary_strength = 1.0
            if effective_uncertainty_profile == "portfolio_probe":
                scenario_family = portfolio_family_for_run(i - 1)
                (
                    portfolio_focus_suppliers,
                    portfolio_focus_demand_items,
                    portfolio_secondary_strength,
                ) = portfolio_focus_sets(
                    family=scenario_family,
                    rng=rng,
                    demand_items=demand_items,
                    supplier_nodes=supplier_nodes,
                    supplier_edge_sources=supplier_edge_sources,
                    critical_suppliers=critical_suppliers,
                    critical_demand_items=critical_demand_items,
                )
                (
                    family_global_factor_spec,
                    family_demand_spec_default,
                    family_production_capacity_spec_default,
                    family_supplier_stock_spec_default,
                    family_supplier_capacity_spec_default,
                    family_supplier_lead_spec_default,
                    family_supplier_reliability_spec_default,
                ) = portfolio_factor_specs(scenario_family)
                if not args.include_systemic_supplier_reliability:
                    family_global_factor_spec = dict(family_global_factor_spec)
                    family_global_factor_spec["supplier_reliability_scale"] = (1.0, 1.0, 1.0)
                active_global_factor_spec = family_global_factor_spec
                active_demand_factor_spec = {item: family_demand_spec_default for item in demand_items}
                active_capacity_factor_spec = {node: family_production_capacity_spec_default for node in production_nodes}
                active_supplier_stock_factor_spec = {node: family_supplier_stock_spec_default for node in supplier_nodes}
                active_supplier_capacity_factor_spec = {node: family_supplier_capacity_spec_default for node in supplier_nodes}
                active_supplier_lead_factor_spec = {node: family_supplier_lead_spec_default for node in supplier_edge_sources}
                active_supplier_reliability_factor_spec = {node: family_supplier_reliability_spec_default for node in supplier_edge_sources}
            for k, (lo, mode, hi) in active_global_factor_spec.items():
                factors[k] = sample_factor(rng, lo, mode, hi)
            for item, (lo, mode, hi) in active_demand_factor_spec.items():
                demand_item_scale[item] = sample_factor(rng, lo, mode, hi)
            for node, (lo, mode, hi) in active_capacity_factor_spec.items():
                capacity_node_scale[node] = sample_factor(rng, lo, mode, hi)
            for node, (lo, mode, hi) in active_supplier_stock_factor_spec.items():
                supplier_node_scale[node] = sample_factor(rng, lo, mode, hi)
            for node, (lo, mode, hi) in active_supplier_capacity_factor_spec.items():
                supplier_capacity_node_scale[node] = sample_factor(rng, lo, mode, hi)
            for node, (lo, mode, hi) in active_supplier_lead_factor_spec.items():
                edge_src_lead_time_scale[node] = sample_factor(rng, lo, mode, hi)
            for node, (lo, mode, hi) in active_supplier_reliability_factor_spec.items():
                edge_src_reliability_scale[node] = sample_factor(rng, lo, mode, hi)

            if effective_uncertainty_profile == "portfolio_probe":
                if portfolio_focus_demand_items:
                    demand_item_scale = attenuate_non_focus(
                        demand_item_scale,
                        portfolio_focus_demand_items,
                        portfolio_secondary_strength,
                    )
                if portfolio_focus_suppliers:
                    supplier_node_scale = attenuate_non_focus(
                        supplier_node_scale,
                        portfolio_focus_suppliers,
                        portfolio_secondary_strength,
                    )
                    supplier_capacity_node_scale = attenuate_non_focus(
                        supplier_capacity_node_scale,
                        portfolio_focus_suppliers,
                        portfolio_secondary_strength,
                    )
                    edge_src_lead_time_scale = attenuate_non_focus(
                        edge_src_lead_time_scale,
                        portfolio_focus_suppliers,
                        portfolio_secondary_strength,
                    )
                    edge_src_reliability_scale = attenuate_non_focus(
                        edge_src_reliability_scale,
                        portfolio_focus_suppliers,
                        portfolio_secondary_strength,
                    )
        else:
            portfolio_focus_suppliers = set()
            portfolio_focus_demand_items = set()
            portfolio_secondary_strength = 1.0

        row: dict[str, Any] = {
            "run_id": run_id,
            "is_baseline": is_baseline,
            "scenario_family": scenario_family,
            "scenario_family_label": portfolio_family_label(scenario_family),
            "portfolio_focus_suppliers": "|".join(sorted(portfolio_focus_suppliers)),
            "portfolio_focus_demand_items": "|".join(sorted(portfolio_focus_demand_items)),
            "portfolio_secondary_strength": portfolio_secondary_strength,
            "status": "ok",
            "error": "",
        }
        row.update({f"factor::{k}": v for k, v in factors.items()})
        row.update({f"demand_item::{k}": v for k, v in demand_item_scale.items()})
        row.update({f"capacity_node::{k}": v for k, v in capacity_node_scale.items()})
        row.update({f"supplier_stock_node::{k}": v for k, v in supplier_node_scale.items()})
        row.update({f"supplier_capacity_node::{k}": v for k, v in supplier_capacity_node_scale.items()})
        row.update({f"supplier_lead_node::{k}": v for k, v in edge_src_lead_time_scale.items()})
        row.update({f"supplier_reliability_node::{k}": v for k, v in edge_src_reliability_scale.items()})

        run_specs.append(
            {
                "index": i,
                "run_id": run_id,
                "is_baseline": is_baseline,
                "scenario_family": scenario_family,
                "row": row,
                "factors": factors,
                "demand_item_scale": demand_item_scale,
                "capacity_node_scale": capacity_node_scale,
                "supplier_node_scale": supplier_node_scale,
                "supplier_capacity_node_scale": supplier_capacity_node_scale,
                "edge_src_lead_time_scale": edge_src_lead_time_scale,
                "edge_src_reliability_scale": edge_src_reliability_scale,
            }
        )

    result_by_index: dict[int, dict[str, Any]] = {}
    checkpoint_meta: dict[int, tuple[Path, str]] = {}
    pending_specs: list[dict[str, Any]] = []
    main_resumed = 0
    for spec in run_specs:
        index = int(spec["index"])
        fingerprint = checkpoint_fingerprint(spec, main_checkpoint_config, phase="main")
        path = checkpoint_path(checkpoints_dir, spec, phase="main")
        checkpoint_meta[index] = (path, fingerprint)
        cached = None
        if bool(args.resume):
            cached = load_run_checkpoint(
                path,
                expected_fingerprint=fingerprint,
                phase="main",
                require_trajectory=bool(args.save_trajectories),
            )
        if cached is None:
            pending_specs.append(spec)
            continue
        result_by_index[index] = cached
        main_resumed += 1
        print(f"[RESUME] {spec['run_id']} checkpoint valide", flush=True)

    worker_count = max(1, min(int(args.workers or 1), len(pending_specs) or 1))
    print(
        f"[RUNS] total={total_runs} resumed={main_resumed} pending={len(pending_specs)} "
        f"workers={worker_count}",
        flush=True,
    )

    def record_main_result(spec: dict[str, Any], result: dict[str, Any]) -> None:
        index = int(result["index"])
        result_by_index[index] = result
        path, fingerprint = checkpoint_meta[index]
        write_run_checkpoint(
            path,
            fingerprint=fingerprint,
            phase="main",
            result=result,
            require_trajectory=bool(args.save_trajectories),
        )

    if worker_count == 1:
        for completed, spec in enumerate(pending_specs, start=1):
            print(
                f"[RUN] {completed:03d}/{len(pending_specs):03d} {spec['run_id']}",
                flush=True,
            )
            result = execute_run_spec(
                spec,
                base_data=base_data,
                scenario_id=scenario_id,
                run_script=run_script,
                days=args.days,
                simulator_extra_args=simulator_extra_args,
                keep_run_artifacts=bool(args.keep_run_artifacts),
                runs_dir=runs_dir,
                save_trajectories=bool(args.save_trajectories),
                trajectory_max_points=max(0, int(args.trajectory_max_points)),
            )
            record_main_result(spec, result)
    elif pending_specs:
        with concurrent.futures.ThreadPoolExecutor(max_workers=worker_count) as executor:
            future_to_spec = {
                executor.submit(
                    execute_run_spec,
                    spec,
                    base_data=base_data,
                    scenario_id=scenario_id,
                    run_script=run_script,
                    days=args.days,
                    simulator_extra_args=simulator_extra_args,
                    keep_run_artifacts=bool(args.keep_run_artifacts),
                    runs_dir=runs_dir,
                    save_trajectories=bool(args.save_trajectories),
                    trajectory_max_points=max(0, int(args.trajectory_max_points)),
                ): spec
                for spec in pending_specs
            }
            for completed, future in enumerate(concurrent.futures.as_completed(future_to_spec), start=1):
                spec = future_to_spec[future]
                try:
                    result = future.result()
                except Exception as exc:
                    row = dict(spec["row"])
                    row["status"] = "failed"
                    row["error"] = str(exc)
                    result = {"index": int(spec["index"]), "row": row, "trajectory_run": None}
                record_main_result(spec, result)
                status = result["row"].get("status", "unknown")
                print(
                    f"[DONE] {completed:03d}/{len(pending_specs):03d} "
                    f"{spec['run_id']} status={status}",
                    flush=True,
                )

    for i in range(total_runs):
        result = result_by_index[i]
        rows.append(result["row"])
        if result.get("trajectory_run"):
            trajectory_runs.append(result["trajectory_run"])

    samples_csv = output_dir / "montecarlo_samples.csv"
    all_columns = sorted({k for r in rows for k in r.keys()})
    with samples_csv.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=all_columns)
        writer.writeheader()
        writer.writerows(rows)

    ok_rows = [r for r in rows if r.get("status") == "ok"]
    stochastic_ok_rows = [r for r in ok_rows if not bool(r.get("is_baseline"))]
    distribution_rows = stochastic_ok_rows or ok_rows
    failed_rows = [r for r in rows if r.get("status") != "ok"]
    baseline = next((r for r in ok_rows if bool(r.get("is_baseline"))), None)
    if baseline is None:
        raise RuntimeError("Baseline Monte Carlo run failed.")

    kpi_cols = sorted([k for k in baseline.keys() if k.startswith("kpi::")])
    factor_prefixes = (
        "factor::",
        "demand_item::",
        "capacity_node::",
        "supplier_stock_node::",
        "supplier_capacity_node::",
        "supplier_lead_node::",
        "supplier_reliability_node::",
    )
    factor_cols = sorted({k for row in rows for k in row.keys() if k.startswith(factor_prefixes)})

    metric_stats: dict[str, Any] = {}
    for k in kpi_cols:
        values = [to_float(r.get(k), float("nan")) for r in distribution_rows]
        values = [v for v in values if not math.isnan(v)]
        if not values:
            continue
        sv = sorted(values)
        metric_stats[k] = {
            "n": len(values),
            "mean": mean(values),
            "std": pstdev(values) if len(values) > 1 else 0.0,
            "min": sv[0],
            "p05": percentile(sv, 0.05),
            "p50": percentile(sv, 0.50),
            "p95": percentile(sv, 0.95),
            "max": sv[-1],
            "baseline": to_float(baseline.get(k), float("nan")),
        }

    corr_targets = [k for k in ["kpi::fill_rate", "kpi::ending_backlog", "kpi::total_cost", "kpi::total_produced"] if k in kpi_cols]
    correlations: dict[str, dict[str, float]] = {}
    for fc in factor_cols:
        xs = [to_float(r.get(fc), float("nan")) for r in distribution_rows]
        if any(math.isnan(x) for x in xs):
            continue
        correlations[fc] = {}
        for mk in corr_targets:
            ys = [to_float(r.get(mk), float("nan")) for r in distribution_rows]
            if any(math.isnan(y) for y in ys):
                continue
            correlations[fc][mk] = pearson_corr(xs, ys)

    def top_runs(metric: str, reverse: bool, n: int = 10) -> list[dict[str, Any]]:
        candidates = []
        for r in distribution_rows:
            val = to_float(r.get(metric), float("nan"))
            if math.isnan(val):
                continue
            candidates.append({"run_id": r["run_id"], metric: val})
        candidates.sort(key=lambda x: to_float(x.get(metric), 0.0), reverse=reverse)
        return candidates[:n]

    driver_rankings: dict[str, list[dict[str, Any]]] = {}
    for target in corr_targets:
        ranked: list[dict[str, Any]] = []
        for factor, target_corrs in correlations.items():
            corr = to_float(target_corrs.get(target), float("nan"))
            if math.isnan(corr):
                continue
            ranked.append({"factor": factor, "correlation": corr, "absolute_correlation": abs(corr)})
        ranked.sort(key=lambda x: x["absolute_correlation"], reverse=True)
        driver_rankings[target] = ranked[:12]

    decision_metrics = {
        "fill_rate_below_100pct": metric_probability(distribution_rows, "kpi::fill_rate", lambda v: v < 0.999999),
        "fill_rate_below_99pct": metric_probability(distribution_rows, "kpi::fill_rate", lambda v: v < 0.99),
        "backlog_positive": metric_probability(distribution_rows, "kpi::ending_backlog", lambda v: v > 1e-9),
        "total_cost_above_baseline": metric_probability(
            distribution_rows,
            "kpi::total_cost",
            lambda v: v > to_float(baseline.get("kpi::total_cost"), float("inf")),
        ),
        "inventory_cost_above_baseline": metric_probability(
            distribution_rows,
            "kpi::total_inventory_cost_legacy_raw_holding",
            lambda v: v > to_float(baseline.get("kpi::total_inventory_cost_legacy_raw_holding"), float("inf")),
        ),
        "supplier_capacity_binding_above_baseline": metric_probability(
            distribution_rows,
            "kpi::total_supplier_capacity_binding_qty",
            lambda v: v > to_float(baseline.get("kpi::total_supplier_capacity_binding_qty"), float("inf")),
        ),
    }
    family_counts: dict[str, int] = {}
    for row in distribution_rows:
        family = str(row.get("scenario_family") or "global")
        family_counts[family] = family_counts.get(family, 0) + 1

    summary = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "input": str(input_path),
        "run_script": str(run_script),
        "manifest": manifest_config,
        "scenario_id": scenario_id,
        "days_override": args.days,
        "seed": args.seed,
        "uncertainty_profile": args.uncertainty_profile,
        "effective_uncertainty_profile": effective_uncertainty_profile,
        "systemic_supplier_reliability_enabled": bool(args.include_systemic_supplier_reliability),
        "sensitivity_calibration": {
            "applied": bool(sensitivity_calibration)
            and effective_uncertainty_profile != str(args.uncertainty_profile),
            "source_json": sensitivity_calibration.get("source_json", ""),
            "status": sensitivity_calibration.get("status", ""),
            "recommended_profile": sensitivity_calibration.get("recommended_profile", ""),
            "sensitivity_strength_score": sensitivity_calibration.get("sensitivity_strength_score"),
            "reason": sensitivity_calibration.get("reason", ""),
            "max_impact_observed": sensitivity_calibration.get("max_impact_observed", {}),
            "family_priority": sensitivity_calibration.get("family_priority", [])[:8]
            if isinstance(sensitivity_calibration.get("family_priority"), list)
            else [],
            "top_cases": sensitivity_calibration.get("top_cases", [])[:8]
            if isinstance(sensitivity_calibration.get("top_cases"), list)
            else [],
        },
        "workers": worker_count,
        "checkpointing": {
            "schema_version": RUN_CHECKPOINT_SCHEMA_VERSION,
            "resume_enabled": bool(args.resume),
            "directory": str(checkpoints_dir),
            "config_fingerprint": hashlib.sha256(
                _canonical_json_bytes(main_checkpoint_config)
            ).hexdigest(),
            "main_runs_reused": main_resumed,
            "main_runs_executed": len(pending_specs),
        },
        "simulator_extra_args": simulator_extra_args,
        "supplier_neutral_floors_adjusted_per_run": bool(supplier_neutral_floors_csv),
        "supplier_neutral_floors_source_csv": supplier_neutral_floors_csv,
        "portfolio_probe_families": PORTFOLIO_PROBE_FAMILIES if effective_uncertainty_profile == "portfolio_probe" else [],
        "portfolio_probe_family_labels": PORTFOLIO_PROBE_FAMILY_LABELS if effective_uncertainty_profile == "portfolio_probe" else {},
        "portfolio_priority_targets": portfolio_priority_targets
        if effective_uncertainty_profile == "portfolio_probe"
        else {},
        "scenario_family_counts": family_counts,
        "runs_requested_excluding_baseline": args.runs,
        "runs_total_including_baseline": total_runs,
        "successful_runs": len(ok_rows),
        "successful_stochastic_runs": len(stochastic_ok_rows),
        "failed_runs": len(failed_rows),
        "factor_distributions": {
            "global": global_factor_spec,
            "demand_item_scale": demand_factor_spec,
            "capacity_node_scale": capacity_factor_spec,
            "supplier_stock_node_scale": supplier_stock_factor_spec,
            "supplier_capacity_node_scale": supplier_capacity_factor_spec,
            "supplier_lead_node_scale": supplier_lead_factor_spec,
            "supplier_reliability_node_scale": supplier_reliability_factor_spec,
        },
        "metric_statistics": metric_stats,
        "decision_metrics": decision_metrics,
        "factor_kpi_correlations_pearson": correlations,
        "driver_rankings": driver_rankings,
        "top_runs": {
            "best_fill_rate": top_runs("kpi::fill_rate", reverse=True),
            "worst_fill_rate": top_runs("kpi::fill_rate", reverse=False),
            "lowest_total_cost": top_runs("kpi::total_cost", reverse=False),
            "highest_total_cost": top_runs("kpi::total_cost", reverse=True),
        },
    }
    variance_path = output_dir / "variance_decomposition.json"
    variance_payload = build_variance_decomposition(
        samples_csv,
        random_seed=int(args.seed),
    )
    write_json(variance_path, variance_payload)
    summary["variance_decomposition"] = {
        "path": str(variance_path),
        "schema_version": variance_payload.get("schema_version"),
        "method": (variance_payload.get("method") or {}).get("name"),
        "is_sobol": False,
        "excluded_factors": variance_payload.get("excluded_factors") or [],
        "kpi_count": len(variance_payload.get("kpis") or {}),
    }
    cost_diagnostics_path = output_dir / "montecarlo_cost_diagnostics.json"
    cost_diagnostics = build_cost_diagnostics(samples_csv)
    write_json(cost_diagnostics_path, cost_diagnostics)
    summary["cost_diagnostics"] = {
        "path": str(cost_diagnostics_path),
        "schema_version": cost_diagnostics.get("schema_version"),
        "sample_count": cost_diagnostics.get("sample_count"),
        "accounting_identity_valid": (cost_diagnostics.get("accounting_identity") or {}).get("valid_within_tolerance"),
        "exceptional_supply_cost_in_total": (cost_diagnostics.get("exceptional_supply_cost") or {}).get("included_in_total_cost"),
    }
    paired_path = output_dir / "montecarlo_paired_propagation.json"
    temporal_path = output_dir / "montecarlo_temporal_propagation.json"
    paired_enabled = bool(args.save_trajectories) if args.paired_propagation is None else bool(args.paired_propagation)
    if paired_enabled:
        factor_count = max(0, int(args.paired_factor_count))
        pair_target = max(0, factor_count - min(2, factor_count // 4))
        paired_factors = select_supplier_item_factors(
            base_data,
            summary,
            rows,
            limit=pair_target,
        )
        ranked_fallback = select_paired_factors(
            summary,
            rows,
            limit=max(factor_count * 2, factor_count),
        )
        for factor in [
            *[value for value in ranked_fallback if is_economic_factor(value)],
            *ranked_fallback,
        ]:
            if len(paired_factors) >= factor_count:
                break
            if factor not in paired_factors:
                paired_factors.append(factor)
        paired_backgrounds = select_background_rows(
            rows,
            count=max(0, int(args.paired_background_count)),
        )
        paired_specs = build_paired_run_specs(
            factors=paired_factors,
            backgrounds=paired_backgrounds,
            uncertainty=max(0.0, float(args.paired_input_uncertainty)),
            factor_ranges=default_business_factor_ranges(paired_factors),
            range_rows=rows,
            reuse_background_centers=True,
        )
        paired_trajectory_runs: list[dict[str, Any]] = []
        paired_failed = 0
        paired_resumed = 0
        paired_executed = 0
        if paired_specs:
            paired_checkpoint_config = build_checkpoint_config(
                input_path=input_path,
                run_script=run_script,
                scenario_id=scenario_id,
                days=int(args.days),
                simulator_extra_args=simulator_extra_args,
                keep_run_artifacts=False,
                save_trajectories=True,
                trajectory_max_points=max(0, int(args.trajectory_max_points)),
            )
            paired_checkpoint_config["paired_design"] = {
                "input_relative_uncertainty": max(0.0, float(args.paired_input_uncertainty)),
                "factor_count": max(0, int(args.paired_factor_count)),
                "background_count": max(0, int(args.paired_background_count)),
            }
            paired_checkpoint_meta: dict[int, tuple[Path, str]] = {}
            paired_result_by_index: dict[int, dict[str, Any]] = {}
            pending_paired_specs: list[dict[str, Any]] = []
            for spec in paired_specs:
                index = int(spec["index"])
                fingerprint = checkpoint_fingerprint(
                    spec,
                    paired_checkpoint_config,
                    phase="paired",
                )
                path = checkpoint_path(checkpoints_dir, spec, phase="paired")
                paired_checkpoint_meta[index] = (path, fingerprint)
                cached = None
                if bool(args.resume):
                    cached = load_run_checkpoint(
                        path,
                        expected_fingerprint=fingerprint,
                        phase="paired",
                        require_trajectory=True,
                    )
                if cached is None:
                    pending_paired_specs.append(spec)
                    continue
                paired_result_by_index[index] = cached
                paired_resumed += 1

            paired_executed = len(pending_paired_specs)
            paired_workers = max(
                1,
                min(int(args.workers or 1), len(pending_paired_specs) or 1),
            )
            print(
                f"[PAIRED] factors={len(paired_factors)} backgrounds={len(paired_backgrounds)} "
                f"runs={len(paired_specs)} resumed={paired_resumed} "
                f"pending={len(pending_paired_specs)} workers={paired_workers}",
                flush=True,
            )

            def record_paired_result(result: dict[str, Any]) -> None:
                index = int(result["index"])
                paired_result_by_index[index] = result
                path, fingerprint = paired_checkpoint_meta[index]
                write_run_checkpoint(
                    path,
                    fingerprint=fingerprint,
                    phase="paired",
                    result=result,
                    require_trajectory=True,
                )

            if paired_workers == 1:
                for completed, spec in enumerate(pending_paired_specs, start=1):
                    result = execute_run_spec(
                        spec,
                        base_data=base_data,
                        scenario_id=scenario_id,
                        run_script=run_script,
                        days=args.days,
                        simulator_extra_args=simulator_extra_args,
                        keep_run_artifacts=False,
                        runs_dir=output_dir / "paired_runs",
                        save_trajectories=True,
                        trajectory_max_points=max(0, int(args.trajectory_max_points)),
                    )
                    record_paired_result(result)
                    print(
                        f"[PAIRED DONE] {completed:03d}/{len(pending_paired_specs):03d} "
                        f"{spec['run_id']} status={result['row'].get('status', 'unknown')}",
                        flush=True,
                    )
            elif pending_paired_specs:
                with concurrent.futures.ThreadPoolExecutor(max_workers=paired_workers) as executor:
                    future_to_spec = {
                        executor.submit(
                            execute_run_spec,
                            spec,
                            base_data=base_data,
                            scenario_id=scenario_id,
                            run_script=run_script,
                            days=args.days,
                            simulator_extra_args=simulator_extra_args,
                            keep_run_artifacts=False,
                            runs_dir=output_dir / "paired_runs",
                            save_trajectories=True,
                            trajectory_max_points=max(0, int(args.trajectory_max_points)),
                        ): spec
                        for spec in pending_paired_specs
                    }
                    for completed, future in enumerate(concurrent.futures.as_completed(future_to_spec), start=1):
                        spec = future_to_spec[future]
                        try:
                            result = future.result()
                        except Exception as exc:
                            failed_row = dict(spec["row"])
                            failed_row["status"] = "failed"
                            failed_row["error"] = str(exc)
                            result = {"index": int(spec["index"]), "row": failed_row, "trajectory_run": None}
                        record_paired_result(result)
                        print(
                            f"[PAIRED DONE] {completed:03d}/{len(pending_paired_specs):03d} "
                            f"{spec['run_id']} status={result['row'].get('status', 'unknown')}",
                            flush=True,
                        )
            for spec in paired_specs:
                result = paired_result_by_index.get(int(spec["index"]))
                if not result or result["row"].get("status") != "ok":
                    paired_failed += 1
                    continue
                trajectory_run = result.get("trajectory_run")
                if trajectory_run:
                    trajectory_run["paired_metadata"] = dict(spec.get("paired_metadata") or {})
                    paired_trajectory_runs.append(trajectory_run)

        paired_payload = build_paired_propagation_payload(
            factors=paired_factors,
            backgrounds=paired_backgrounds,
            trajectory_runs=paired_trajectory_runs,
            scenario_id=scenario_id,
            uncertainty=max(0.0, float(args.paired_input_uncertainty)),
        )
        paired_payload["failed_runs"] = paired_failed
        write_json(paired_path, paired_payload)
        nominal_output_dir = Path(str(manifest_config.get("nominal_output_dir") or ""))
        lot_events_path = (
            Path(args.nominal_lot_events_csv)
            if args.nominal_lot_events_csv
            else nominal_output_dir / "data" / "production_lot_events.csv"
        )
        temporal_payload = build_temporal_propagation(
            paired_payload,
            base_data,
            lot_events_csv=lot_events_path if lot_events_path.exists() else None,
        )
        write_json(temporal_path, temporal_payload)
        summary["paired_propagation"] = {
            "enabled": True,
            "path": str(paired_path),
            "schema_version": paired_payload.get("schema_version"),
            "method": paired_payload.get("method"),
            "input_relative_uncertainty": paired_payload.get("input_relative_uncertainty"),
            "factor_count": paired_payload.get("factor_count"),
            "background_count": paired_payload.get("background_count"),
            "runs_expected": len(paired_specs),
            "runs_successful": paired_payload.get("run_count"),
            "runs_failed": paired_failed,
            "factors": paired_factors,
            "temporal_propagation_path": str(temporal_path),
            "lot_events_path": str(lot_events_path) if lot_events_path.exists() else "",
        }
        summary["checkpointing"]["paired_runs_reused"] = paired_resumed
        summary["checkpointing"]["paired_runs_executed"] = paired_executed
    else:
        summary["paired_propagation"] = {"enabled": False}
        if paired_path.exists():
            paired_path.unlink()
        if temporal_path.exists():
            temporal_path.unlink()
    summary_json = output_dir / "montecarlo_summary.json"
    write_json(summary_json, summary)

    trajectories_json = output_dir / "montecarlo_trajectories.json"
    if args.save_trajectories:
        trajectories = build_montecarlo_trajectories_payload(
            trajectory_runs,
            scenario_id=scenario_id,
            seed=int(args.seed),
            profile=str(args.uncertainty_profile),
            max_points=max(0, int(args.trajectory_max_points)),
            max_display_runs=max(0, int(args.trajectory_display_runs)),
        )
        write_json(trajectories_json, trajectories)

    failed_csv = output_dir / "montecarlo_failed_runs.csv"
    if failed_rows:
        with failed_csv.open("w", encoding="utf-8", newline="") as f:
            cols = sorted({k for r in failed_rows for k in r.keys()})
            writer = csv.DictWriter(f, fieldnames=cols)
            writer.writeheader()
            writer.writerows(failed_rows)
    elif failed_csv.exists():
        failed_csv.unlink()

    report_md = output_dir / "montecarlo_report.md"
    report = f"""# Monte Carlo Analysis Report

## Setup
- Input: {input_path}
- Scenario: {scenario_id}
- Days override: {args.days}
- Seed: {args.seed}
- Uncertainty profile: {args.uncertainty_profile}
- Effective uncertainty profile: {effective_uncertainty_profile}
- Sensitivity calibration: {json.dumps(summary['sensitivity_calibration'], ensure_ascii=False)}
- Runs requested (excluding baseline): {args.runs}
- Runs total (including baseline): {total_runs}
- Runs success: {len(ok_rows)}
- Stochastic runs success: {len(stochastic_ok_rows)}
- Runs failed: {len(failed_rows)}
- Keep run artifacts: {args.keep_run_artifacts}

## Decision Metrics
{json.dumps(decision_metrics, indent=2, ensure_ascii=False)}

## KPI Statistics (distribution over successful runs)
{json.dumps(metric_stats, indent=2, ensure_ascii=False)}

## Top Drivers
{json.dumps(driver_rankings, indent=2, ensure_ascii=False)}

## Top Runs
- Best fill rate: {json.dumps(summary['top_runs']['best_fill_rate'], ensure_ascii=False)}
- Worst fill rate: {json.dumps(summary['top_runs']['worst_fill_rate'], ensure_ascii=False)}
- Lowest total cost: {json.dumps(summary['top_runs']['lowest_total_cost'], ensure_ascii=False)}
- Highest total cost: {json.dumps(summary['top_runs']['highest_total_cost'], ensure_ascii=False)}

## Files
- montecarlo_samples.csv
- montecarlo_summary.json
- montecarlo_trajectories.json (si --save-trajectories)
- montecarlo_paired_propagation.json (si propagation appariee active)
- montecarlo_report.md
"""
    if failed_rows:
        report += "- montecarlo_failed_runs.csv\n"
    report_md.write_text(report, encoding="utf-8")

    print(f"[OK] Samples CSV: {samples_csv.resolve()}")
    print(f"[OK] Summary JSON: {summary_json.resolve()}")
    if args.save_trajectories:
        print(f"[OK] Trajectories JSON: {trajectories_json.resolve()}")
    if paired_enabled:
        print(f"[OK] Paired propagation JSON: {paired_path.resolve()}")
    print(f"[OK] Report MD: {report_md.resolve()}")
    if failed_rows:
        print(f"[WARN] Failed runs CSV: {failed_csv.resolve()}")


if __name__ == "__main__":
    main()
