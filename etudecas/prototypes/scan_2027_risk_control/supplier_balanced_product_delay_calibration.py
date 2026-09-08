#!/usr/bin/env python3
"""Calibrate balanced service points with product-specific supplier delays.

This additive exploratory utility changes one modelling dimension only: the
planned lead time of the active supplier lanes feeding each finished-product
chain.  It does not load capacity overrides, availability incidents, quality
incidents, controls, or state-dependent risks.

``plan`` builds a portable, signed Cartesian grid of candidate graphs.
``run`` executes the grid once with common random numbers and can be resumed.
``select`` validates an existing complete result table and chooses one offset
pair for 93%/93%, then one (weakly more severe) pair for 80%/80%.

The default plan is intentionally a short exploratory calibration.  It is not
an estimate of historical supplier performance.
"""

from __future__ import annotations

import argparse
import copy
import csv
import hashlib
import itertools
import json
import math
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, Sequence


REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from etudecas.prototypes.scan_2027_risk_control import (  # noqa: E402
    supplier_service_landscape_campaign as campaign_core,
)
from etudecas.prototypes.scan_2027_risk_control import (  # noqa: E402
    supplier_service_regime_calibration_protocol as protocol,
)
from etudecas.prototypes.scan_2027_risk_control import (  # noqa: E402
    supplier_service_regime_calibration_runner as calibration_runner,
)


SCHEMA_VERSION = "etudecas.supplier_balanced_product_delay_calibration.v1"
PLAN_SCHEMA_VERSION = f"{SCHEMA_VERSION}.plan"
EVIDENCE_SCHEMA_VERSION = f"{SCHEMA_VERSION}.case_evidence"
RESULTS_SCHEMA_VERSION = f"{SCHEMA_VERSION}.results"
SELECTION_SCHEMA_VERSION = f"{SCHEMA_VERSION}.selection"
CAMPAIGN_POINTS_SCHEMA_VERSION = f"{SCHEMA_VERSION}.campaign_operating_points"
DEFAULT_ACTIVE_LANES = (
    protocol.ARTIFACT_PARENT
    / "supplier_network_risk_screen_20260902_v2"
    / "active_lane_reference.csv"
)
DEFAULT_PLAN_OUTPUT = (
    protocol.ARTIFACT_PARENT
    / "supplier_balanced_product_delay_calibration_plan_20260904_v1"
)
DEFAULT_RUN_OUTPUT = (
    protocol.ARTIFACT_PARENT
    / "supplier_balanced_product_delay_calibration_screening_20260904_v1"
)
DEFAULT_OFFSETS_268091 = (0.0, 7.0, 10.0, 14.0, 22.0, 30.0)
DEFAULT_OFFSETS_268967 = (0.0, 45.0, 60.0, 90.0, 120.0, 180.0)
DEFAULT_TARGETS = (0.93, 0.80)
DEFAULT_TOLERANCE = 0.015
DEFAULT_SEED = 340281
PRODUCT_FACTORY = {"268091": "M-1810", "268967": "M-1430"}
PRODUCTS = tuple(PRODUCT_FACTORY)
FORBIDDEN_ENGINE_FLAGS = {
    "--supplier-neutral-floors-csv",
    "--factory-nominal-capacities-csv",
    "--supplier-risk-events-csv",
    "--control-schedule-csv",
}
RESULT_FIELDS = (
    "candidate_id",
    "offset_days_268091",
    "offset_days_268967",
    "seed",
    "system_on_due_service",
    "on_due_service_268091",
    "on_due_service_268967",
    "minimum_product_on_due_service",
    "demand_qty_268091",
    "demand_qty_268967",
    "graph_sha256",
    "valid",
    "status",
)


@dataclass(frozen=True)
class Candidate:
    candidate_id: str
    offset_days_268091: float
    offset_days_268967: float


@dataclass(frozen=True)
class ValidatedPlan:
    plan_dir: Path
    manifest: dict[str, Any]
    candidates: tuple[Candidate, ...]
    inventory: dict[str, dict[str, Any]]
    lanes_by_product: dict[str, tuple[dict[str, str], ...]]
    source_graph: Path
    engine: Path
    profile: Path


CaseExecutor = Callable[[Candidate, ValidatedPlan, Path, int], dict[str, Any]]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def _sha256(path: Path) -> str:
    return protocol.sha256_file(path)


def _stable_sha256(payload: Any) -> str:
    return protocol.stable_sha256(payload)


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    campaign_core.write_json_atomic(path, payload)


def _write_csv(
    path: Path,
    rows: Sequence[Mapping[str, Any]],
    fields: Sequence[str] | None = None,
) -> None:
    campaign_core.write_csv_atomic(path, rows, fields)


def _float_code(value: float) -> str:
    return format(float(value), ".12g").replace("-", "m").replace(".", "p")


def _candidate_id(offset_268091: float, offset_268967: float) -> str:
    return (
        f"delay_pf268091_{_float_code(offset_268091)}d"
        f"__pf268967_{_float_code(offset_268967)}d"
    )


def _parse_float_list(specification: str, label: str) -> tuple[float, ...]:
    try:
        values = tuple(
            dict.fromkeys(
                float(token.strip())
                for token in specification.split(",")
                if token.strip()
            )
        )
    except ValueError as exc:
        raise ValueError(f"{label} must be a comma-separated number list") from exc
    if not values or any(not math.isfinite(value) or value < 0.0 for value in values):
        raise ValueError(f"{label} must contain finite non-negative values")
    return tuple(sorted(values))


def _parse_descending_target_list(specification: str) -> tuple[float, ...]:
    """Parse CLI targets in the descending order required by the plan."""

    return tuple(
        sorted(_parse_float_list(specification, "targets"), reverse=True)
    )


def build_candidates(
    offsets_268091: Sequence[float], offsets_268967: Sequence[float]
) -> tuple[Candidate, ...]:
    candidates = tuple(
        Candidate(_candidate_id(left, right), float(left), float(right))
        for left, right in itertools.product(offsets_268091, offsets_268967)
    )
    if len({candidate.candidate_id for candidate in candidates}) != len(candidates):
        raise ValueError("Candidate identifiers are not unique")
    return candidates


def load_lane_scope(path: Path) -> dict[str, tuple[dict[str, str], ...]]:
    """Validate and split the real active-lane inventory by finished product."""

    path = path.resolve()
    if not path.is_file():
        raise FileNotFoundError(f"Active-lane reference missing: {path}")
    groups: dict[str, list[dict[str, str]]] = {product: [] for product in PRODUCTS}
    seen_edges: set[str] = set()
    seen_lanes: set[tuple[str, str, str]] = set()
    for raw in _read_csv(path):
        product = str(raw.get("target_product_id") or "").replace("item:", "")
        if product not in groups:
            raise ValueError(f"Unexpected target product in active lanes: {product!r}")
        row = {
            "chain_id": str(raw.get("chain_id") or ""),
            "supplier_id": str(raw.get("supplier_id") or ""),
            "item_id": str(raw.get("item_id") or ""),
            "dst_node_id": str(raw.get("dst_node_id") or ""),
            "edge_id": str(raw.get("edge_id") or ""),
            "target_product_id": product,
        }
        if not all(row.values()):
            raise ValueError("Active-lane reference contains an incomplete identity")
        if row["dst_node_id"] != PRODUCT_FACTORY[product]:
            raise ValueError(f"Lane/product factory mismatch: {row['edge_id']}")
        lane_key = (row["supplier_id"], row["item_id"], row["dst_node_id"])
        if row["edge_id"] in seen_edges or lane_key in seen_lanes:
            raise ValueError(f"Duplicate active lane: {row['edge_id']}")
        seen_edges.add(row["edge_id"])
        seen_lanes.add(lane_key)
        groups[product].append(row)
    if any(not rows for rows in groups.values()):
        raise ValueError("Each finished-product chain must have at least one active lane")
    return {
        product: tuple(sorted(rows, key=lambda item: item["edge_id"]))
        for product, rows in groups.items()
    }


def _edge_index(graph: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    index: dict[str, dict[str, Any]] = {}
    for edge in graph.get("edges") or []:
        edge_id = str(edge.get("id") or "")
        if not edge_id or edge_id in index:
            raise ValueError(f"Missing or duplicate graph edge id: {edge_id!r}")
        index[edge_id] = edge
    return index


def validate_lanes_against_graph(
    graph: Mapping[str, Any], lanes_by_product: Mapping[str, Sequence[Mapping[str, str]]]
) -> None:
    edges = _edge_index(graph)
    for product, lanes in lanes_by_product.items():
        for lane in lanes:
            edge = edges.get(str(lane["edge_id"]))
            if edge is None:
                raise ValueError(f"Active edge absent from graph: {lane['edge_id']}")
            item_ids = {str(item) for item in edge.get("items") or []}
            if (
                str(edge.get("from") or "") != lane["supplier_id"]
                or str(edge.get("to") or "") != lane["dst_node_id"]
                or lane["item_id"] not in item_ids
                or lane["dst_node_id"] != PRODUCT_FACTORY[product]
            ):
                raise ValueError(f"Active edge identity mismatch: {lane['edge_id']}")


def apply_product_delays(
    source_graph: Mapping[str, Any],
    lanes_by_product: Mapping[str, Sequence[Mapping[str, str]]],
    *,
    offset_days_268091: float,
    offset_days_268967: float,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Return a copy changed only on the two scoped lead-time lane groups."""

    offsets = {
        "268091": float(offset_days_268091),
        "268967": float(offset_days_268967),
    }
    if any(not math.isfinite(value) or value < 0.0 for value in offsets.values()):
        raise ValueError("Lead-time offsets must be finite and non-negative")
    graph = copy.deepcopy(source_graph)
    validate_lanes_against_graph(graph, lanes_by_product)
    edges = _edge_index(graph)
    changes: list[dict[str, Any]] = []
    for product in PRODUCTS:
        offset = offsets[product]
        for lane in lanes_by_product[product]:
            edge = edges[lane["edge_id"]]
            lead = edge.get("lead_time")
            limit = edge.get("delay_step_limit")
            if not isinstance(lead, dict) or not isinstance(limit, dict):
                raise ValueError(f"Missing lead metadata on {lane['edge_id']}")
            reference_lead = protocol.finite_float(lead.get("mean"), math.nan)
            reference_limit = protocol.finite_float(limit.get("value"), math.nan)
            if (
                not math.isfinite(reference_lead)
                or reference_lead <= 0.0
                or not math.isfinite(reference_limit)
            ):
                raise ValueError(f"Invalid lead metadata on {lane['edge_id']}")
            candidate_lead = reference_lead + offset
            candidate_limit = int(math.ceil(2.0 * candidate_lead))
            lead["mean"] = candidate_lead
            limit["value"] = candidate_limit
            changes.append(
                {
                    "target_product_id": product,
                    "factory_id": PRODUCT_FACTORY[product],
                    "edge_id": lane["edge_id"],
                    "supplier_id": lane["supplier_id"],
                    "item_id": lane["item_id"],
                    "offset_days": offset,
                    "lead_time_reference_days": reference_lead,
                    "lead_time_candidate_days": candidate_lead,
                    "delay_step_limit_reference": reference_limit,
                    "delay_step_limit_candidate": candidate_limit,
                    "physically_changed": bool(offset > 0.0),
                }
            )
    expected_count = sum(len(lanes_by_product[product]) for product in PRODUCTS)
    if len(changes) != expected_count:
        raise AssertionError("Not all scoped supplier lanes received their product offset")
    return graph, changes


def _plan_signature_payload(manifest: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": manifest.get("schema_version"),
        "source_hashes": manifest.get("source_hashes"),
        "lane_counts_by_product": manifest.get("lane_counts_by_product"),
        "offset_grid_days": manifest.get("offset_grid_days"),
        "targets": manifest.get("targets"),
        "target_tolerance": manifest.get("target_tolerance"),
        "candidate_inventory": manifest.get("candidate_inventory"),
        "execution_contract": manifest.get("execution_contract"),
    }


def prepare_plan(
    output_dir: Path,
    *,
    active_lanes_path: Path = DEFAULT_ACTIVE_LANES,
    graph_path: Path = protocol.DEFAULT_GRAPH,
    engine_path: Path = protocol.DEFAULT_ENGINE,
    profile_path: Path = protocol.DEFAULT_PROFILE,
    offsets_268091: Sequence[float] = DEFAULT_OFFSETS_268091,
    offsets_268967: Sequence[float] = DEFAULT_OFFSETS_268967,
    targets: Sequence[float] = DEFAULT_TARGETS,
    tolerance: float = DEFAULT_TOLERANCE,
) -> Path:
    """Create a complete immutable plan; never run the engine."""

    output_dir = output_dir.resolve()
    for path in (active_lanes_path, graph_path, engine_path, profile_path):
        if not path.resolve().is_file():
            raise FileNotFoundError(f"Calibration source missing: {path.resolve()}")
    if output_dir.exists():
        raise FileExistsError(f"Refusing to overwrite existing plan: {output_dir}")
    clean_targets = tuple(float(target) for target in targets)
    if (
        len(clean_targets) != 2
        or not clean_targets[0] > clean_targets[1]
        or any(not 0.0 < target < 1.0 for target in clean_targets)
    ):
        raise ValueError("Exactly two descending targets between zero and one are required")
    if not math.isfinite(tolerance) or not 0.0 < tolerance < 0.1:
        raise ValueError("Target tolerance must be between zero and 0.1")
    left_offsets = tuple(sorted({float(value) for value in offsets_268091}))
    right_offsets = tuple(sorted({float(value) for value in offsets_268967}))
    if any(not math.isfinite(value) or value < 0.0 for value in (*left_offsets, *right_offsets)):
        raise ValueError("Offsets must be finite and non-negative")
    if not left_offsets or not right_offsets:
        raise ValueError("Both product grids must be non-empty")
    if 0.0 not in left_offsets or 0.0 not in right_offsets:
        raise ValueError("Both product grids must contain zero for op_100")

    lanes_by_product = load_lane_scope(active_lanes_path)
    source_graph = _read_json(graph_path.resolve())
    validate_lanes_against_graph(source_graph, lanes_by_product)
    candidates = build_candidates(left_offsets, right_offsets)
    temporary = output_dir.parent / f".{output_dir.name}.building-{os.getpid()}"
    if temporary.exists():
        raise FileExistsError(f"Temporary plan path already exists: {temporary}")
    temporary.mkdir(parents=True)
    try:
        inventory: dict[str, dict[str, Any]] = {}
        design_rows: list[dict[str, Any]] = []
        for candidate in candidates:
            candidate_dir = temporary / "inputs" / candidate.candidate_id
            candidate_dir.mkdir(parents=True)
            candidate_graph, changes = apply_product_delays(
                source_graph,
                lanes_by_product,
                offset_days_268091=candidate.offset_days_268091,
                offset_days_268967=candidate.offset_days_268967,
            )
            graph_file = candidate_dir / "candidate_graph.json"
            ledger_file = candidate_dir / "change_ledger.json"
            _write_json(graph_file, candidate_graph)
            _write_json(
                ledger_file,
                {
                    "schema_version": f"{PLAN_SCHEMA_VERSION}.change_ledger",
                    **asdict(candidate),
                    "calibrated_dimension": "planned_supplier_lead_time_days",
                    "changed_dimension_count": 1,
                    "scoped_lane_count": len(changes),
                    "physically_changed_lane_count": sum(
                        bool(change["physically_changed"]) for change in changes
                    ),
                    "changes": changes,
                },
            )
            relative_graph = graph_file.relative_to(temporary).as_posix()
            relative_ledger = ledger_file.relative_to(temporary).as_posix()
            item = {
                **asdict(candidate),
                "graph_path": relative_graph,
                "graph_sha256": _sha256(graph_file),
                "change_ledger_path": relative_ledger,
                "change_ledger_sha256": _sha256(ledger_file),
            }
            inventory[candidate.candidate_id] = item
            design_rows.append(item)
        _write_csv(
            temporary / "candidate_grid.csv",
            design_rows,
            (
                "candidate_id",
                "offset_days_268091",
                "offset_days_268967",
                "graph_path",
                "graph_sha256",
                "change_ledger_path",
                "change_ledger_sha256",
            ),
        )
        _write_json(temporary / "input_inventory.json", inventory)
        manifest: dict[str, Any] = {
            "schema_version": PLAN_SCHEMA_VERSION,
            "status": "planned_not_executed",
            "created_at_utc": _now(),
            "interpretation": (
                "Exploratory simulated hypotheses; not observed supplier performance."
            ),
            "calibrated_dimension": "planned_supplier_lead_time_days_only",
            "excluded_degradation_dimensions": [
                "supplier_capacity",
                "factory_capacity",
                "supplier_availability",
                "quality_hold",
                "quality_yield",
                "acute_incident",
                "state_dependent_risk",
            ],
            "source_paths": {
                "active_lanes": str(active_lanes_path.resolve()),
                "graph": str(graph_path.resolve()),
                "engine": str(engine_path.resolve()),
                "profile": str(profile_path.resolve()),
            },
            "source_hashes": {
                "active_lanes_sha256": _sha256(active_lanes_path.resolve()),
                "graph_sha256": _sha256(graph_path.resolve()),
                "engine_sha256": _sha256(engine_path.resolve()),
                "profile_sha256": _sha256(profile_path.resolve()),
            },
            "lane_counts_by_product": {
                product: len(lanes_by_product[product]) for product in PRODUCTS
            },
            "total_active_lane_count": sum(map(len, lanes_by_product.values())),
            "offset_grid_days": {
                "268091": list(left_offsets),
                "268967": list(right_offsets),
            },
            "candidate_count": len(candidates),
            "targets": list(clean_targets),
            "target_tolerance": float(tolerance),
            "candidate_inventory": inventory,
            "execution_contract": {
                "days": protocol.MEASURED_DAYS,
                "warmup_days": protocol.WARMUP_DAYS,
                "default_seed": DEFAULT_SEED,
                "common_random_numbers": True,
                "supplier_capacity_override": False,
                "factory_capacity_override": False,
                "supplier_availability_incident": False,
                "quality_incident": False,
                "acute_supplier_incident": False,
                "state_dependent_risk": False,
                "selection_metric": "two_product_on_due_service",
                "global_service_reported": True,
                "monotone_offsets_between_targets": True,
            },
        }
        manifest["plan_signature"] = _stable_sha256(
            _plan_signature_payload(manifest)
        )
        _write_json(temporary / "calibration_plan.json", manifest)
        temporary.replace(output_dir)
    except BaseException:
        if temporary.exists():
            import shutil

            shutil.rmtree(temporary)
        raise
    return output_dir


def validate_plan(plan_dir: Path) -> ValidatedPlan:
    plan_dir = plan_dir.resolve()
    manifest_path = plan_dir / "calibration_plan.json"
    inventory_path = plan_dir / "input_inventory.json"
    if not manifest_path.is_file() or not inventory_path.is_file():
        raise FileNotFoundError(f"Incomplete balanced-delay plan: {plan_dir}")
    manifest = _read_json(manifest_path)
    inventory = _read_json(inventory_path)
    if (
        manifest.get("schema_version") != PLAN_SCHEMA_VERSION
        or manifest.get("status") != "planned_not_executed"
        or not isinstance(inventory, dict)
        or inventory != manifest.get("candidate_inventory")
        or manifest.get("plan_signature")
        != _stable_sha256(_plan_signature_payload(manifest))
    ):
        raise ValueError("Balanced-delay plan manifest/signature mismatch")
    paths = manifest.get("source_paths") or {}
    hashes = manifest.get("source_hashes") or {}
    active_lanes = Path(str(paths.get("active_lanes") or "")).resolve()
    source_graph = Path(str(paths.get("graph") or "")).resolve()
    engine = Path(str(paths.get("engine") or "")).resolve()
    profile = Path(str(paths.get("profile") or "")).resolve()
    for path, hash_key in (
        (active_lanes, "active_lanes_sha256"),
        (source_graph, "graph_sha256"),
        (engine, "engine_sha256"),
        (profile, "profile_sha256"),
    ):
        if not path.is_file() or _sha256(path) != hashes.get(hash_key):
            raise ValueError(f"Plan source changed: {path}")
    lanes_by_product = load_lane_scope(active_lanes)
    expected_counts = {
        product: len(lanes_by_product[product]) for product in PRODUCTS
    }
    if manifest.get("lane_counts_by_product") != expected_counts:
        raise ValueError("Active-lane group counts changed")
    graph = _read_json(source_graph)
    validate_lanes_against_graph(graph, lanes_by_product)
    grid = manifest.get("offset_grid_days") or {}
    candidates = build_candidates(grid.get("268091") or (), grid.get("268967") or ())
    if (
        int(manifest.get("candidate_count") or -1) != len(candidates)
        or set(inventory) != {candidate.candidate_id for candidate in candidates}
    ):
        raise ValueError("Candidate grid is incomplete")
    for candidate in candidates:
        item = inventory[candidate.candidate_id]
        graph_path = (plan_dir / str(item.get("graph_path") or "")).resolve()
        ledger_path = (plan_dir / str(item.get("change_ledger_path") or "")).resolve()
        for path in (graph_path, ledger_path):
            try:
                path.relative_to(plan_dir)
            except ValueError as exc:
                raise ValueError(f"Candidate path escapes plan: {path}") from exc
        if (
            not graph_path.is_file()
            or not ledger_path.is_file()
            or _sha256(graph_path) != item.get("graph_sha256")
            or _sha256(ledger_path) != item.get("change_ledger_sha256")
        ):
            raise ValueError(f"Candidate input hash mismatch: {candidate.candidate_id}")
        expected_graph, expected_changes = apply_product_delays(
            graph,
            lanes_by_product,
            offset_days_268091=candidate.offset_days_268091,
            offset_days_268967=candidate.offset_days_268967,
        )
        if _read_json(graph_path) != expected_graph:
            raise ValueError(f"Candidate changes more than scoped delays: {candidate.candidate_id}")
        ledger = _read_json(ledger_path)
        if (
            ledger.get("schema_version") != f"{PLAN_SCHEMA_VERSION}.change_ledger"
            or ledger.get("candidate_id") != candidate.candidate_id
            or ledger.get("changed_dimension_count") != 1
            or ledger.get("changes") != expected_changes
        ):
            raise ValueError(f"Candidate change ledger mismatch: {candidate.candidate_id}")
    return ValidatedPlan(
        plan_dir=plan_dir,
        manifest=manifest,
        candidates=candidates,
        inventory={str(key): dict(value) for key, value in inventory.items()},
        lanes_by_product=lanes_by_product,
        source_graph=source_graph,
        engine=engine,
        profile=profile,
    )


def build_engine_command(
    candidate: Candidate, plan: ValidatedPlan, case_dir: Path, seed: int
) -> list[str]:
    item = plan.inventory[candidate.candidate_id]
    graph_path = (plan.plan_dir / item["graph_path"]).resolve()
    command = [
        sys.executable,
        str(plan.engine),
        "--input",
        str(graph_path),
        "--output-dir",
        str(case_dir),
        "--scenario-id",
        "scn:BASE",
        "--days",
        str(protocol.MEASURED_DAYS),
        "--seed",
        str(seed),
        "--output-profile",
        "compact",
        "--skip-map",
        "--skip-plots",
        "--no-lot-trace",
        "--skip-lot-audit",
        "--common-random-numbers",
    ]
    command.extend(campaign_core.engine_profile_args(plan.profile))
    command.extend(protocol.MANAGED_REFERENCE_PROTOCOL_ARGS)
    if FORBIDDEN_ENGINE_FLAGS.intersection(command):
        raise ValueError("A forbidden capacity/risk/control input entered the command")
    return command


def _policy_errors(
    summary: Mapping[str, Any],
    *,
    candidate: Candidate,
    plan: ValidatedPlan,
    seed: int,
) -> list[str]:
    errors: list[str] = []
    policy = summary.get("policy") or {}
    supplier_risk = policy.get("supplier_risk") or {}
    state_risk = policy.get("supplier_state_dependent_risk") or {}
    supplier_floor = policy.get("supplier_neutral_floor_test") or {}
    factory_capacity = policy.get("factory_nominal_capacity_test") or {}
    warmup = policy.get("warmup_boundary_audit") or {}
    graph_path = (
        plan.plan_dir / plan.inventory[candidate.candidate_id]["graph_path"]
    ).resolve()
    if summary.get("input_sha256") != _sha256(graph_path):
        errors.append("graph input hash mismatch")
    if int(summary.get("sim_days") or -1) != protocol.MEASURED_DAYS:
        errors.append("simulation horizon mismatch")
    if str(summary.get("scenario_id") or "") != "scn:BASE":
        errors.append("engine scenario is not BASE")
    if int(policy.get("seed") or -1) != seed:
        errors.append("seed mismatch")
    if not protocol.truthy(policy.get("common_random_numbers")):
        errors.append("common random numbers disabled")
    if protocol.truthy(policy.get("lot_trace_enabled")):
        errors.append("lot trace unexpectedly enabled")
    if int(warmup.get("physical_warmup_days") or -1) != protocol.WARMUP_DAYS:
        errors.append("warmup duration mismatch")
    if (
        protocol.truthy(supplier_risk.get("enabled"))
        or int(supplier_risk.get("event_count") or 0) != 0
        or supplier_risk.get("warnings")
    ):
        errors.append("acute supplier incident is not neutral")
    if protocol.truthy(state_risk.get("enabled")):
        errors.append("state-dependent supplier risk enabled")
    if protocol.truthy(supplier_floor.get("enabled")):
        errors.append("supplier capacity override enabled")
    if protocol.truthy(factory_capacity.get("enabled")):
        errors.append("factory capacity override enabled")
    return errors


def execute_candidate(
    candidate: Candidate, plan: ValidatedPlan, output_dir: Path, seed: int
) -> dict[str, Any]:
    case_dir = output_dir / "cases" / candidate.candidate_id / f"seed_{seed}"
    summary_path = case_dir / "summaries" / "first_simulation_summary.json"
    service_path = case_dir / "data" / "production_demand_service_daily.csv"
    if summary_path.is_file() != service_path.is_file():
        raise RuntimeError(f"Partial candidate output: {candidate.candidate_id}")
    status = "reextracted" if summary_path.is_file() else "executed"
    command = build_engine_command(candidate, plan, case_dir, seed)
    if status == "executed":
        if case_dir.exists() and any(case_dir.iterdir()):
            raise RuntimeError(f"Unregistered non-empty case: {case_dir}")
        case_dir.mkdir(parents=True, exist_ok=True)
        log_path = case_dir / "balanced_delay_engine.log"
        with log_path.open("a", encoding="utf-8") as stream:
            stream.write(f"[{_now()}] COMMAND {json.dumps(command)}\n")
            completed = subprocess.run(
                command,
                cwd=REPO_ROOT,
                stdout=stream,
                stderr=subprocess.STDOUT,
                text=True,
                check=False,
            )
        if completed.returncode != 0:
            raise RuntimeError(f"Engine failed; see {log_path}")
    summary = _read_json(summary_path)
    service_rows = protocol.read_csv_rows(service_path)
    calibration_runner._validate_daily_service_rows(service_rows)
    metrics = protocol.service_from_daily_rows(
        service_rows, days=protocol.MEASURED_DAYS
    )
    errors = _policy_errors(
        summary, candidate=candidate, plan=plan, seed=seed
    )
    for field in (
        "system_on_due_service",
        "on_due_service_268091",
        "on_due_service_268967",
        "minimum_product_on_due_service",
    ):
        value = protocol.finite_float(metrics.get(field), math.nan)
        if not math.isfinite(value) or not 0.0 <= value <= 1.0:
            errors.append(f"invalid service metric: {field}")
    evidence: dict[str, Any] = {
        "schema_version": EVIDENCE_SCHEMA_VERSION,
        **asdict(candidate),
        "seed": seed,
        "valid": not errors,
        "validation_errors": errors,
        "status": status,
        "metrics": metrics,
        "graph_sha256": plan.inventory[candidate.candidate_id]["graph_sha256"],
        "summary_sha256": _sha256(summary_path),
        "service_daily_sha256": _sha256(service_path),
        "engine_sha256": _sha256(plan.engine),
        "command_sha256": _stable_sha256(command),
        "run_dir": str(case_dir.resolve()),
        "created_at_utc": _now(),
    }
    evidence["evidence_signature"] = _stable_sha256(evidence)
    if errors:
        raise RuntimeError(
            f"Invalid candidate evidence {candidate.candidate_id}: {' | '.join(errors)}"
        )
    return evidence


def _evidence_path(output_dir: Path, candidate_id: str) -> Path:
    digest = hashlib.sha256(candidate_id.encode("utf-8")).hexdigest()[:20]
    return output_dir / "evidence" / f"{digest}.json"


def _validate_evidence(
    evidence: Mapping[str, Any], candidate: Candidate, plan: ValidatedPlan, seed: int
) -> None:
    signature = str(evidence.get("evidence_signature") or "")
    unsigned = dict(evidence)
    unsigned.pop("evidence_signature", None)
    metrics = evidence.get("metrics") or {}
    if (
        evidence.get("schema_version") != EVIDENCE_SCHEMA_VERSION
        or signature != _stable_sha256(unsigned)
        or evidence.get("candidate_id") != candidate.candidate_id
        or int(evidence.get("seed") or -1) != seed
        or evidence.get("valid") is not True
        or evidence.get("validation_errors") != []
        or evidence.get("graph_sha256")
        != plan.inventory[candidate.candidate_id]["graph_sha256"]
        or evidence.get("engine_sha256") != _sha256(plan.engine)
    ):
        raise ValueError(f"Evidence contract mismatch: {candidate.candidate_id}")
    for field in (
        "system_on_due_service",
        "on_due_service_268091",
        "on_due_service_268967",
    ):
        value = protocol.finite_float(metrics.get(field), math.nan)
        if not math.isfinite(value) or not 0.0 <= value <= 1.0:
            raise ValueError(f"Invalid evidence metric: {candidate.candidate_id}/{field}")


def _result_row(evidence: Mapping[str, Any]) -> dict[str, Any]:
    metrics = evidence.get("metrics") or {}
    return {
        "candidate_id": evidence["candidate_id"],
        "offset_days_268091": evidence["offset_days_268091"],
        "offset_days_268967": evidence["offset_days_268967"],
        "seed": evidence["seed"],
        **{field: metrics[field] for field in RESULT_FIELDS if field in metrics},
        "graph_sha256": evidence["graph_sha256"],
        "valid": evidence["valid"],
        "status": evidence["status"],
    }


def select_balanced_targets(
    rows: Sequence[Mapping[str, Any]],
    *,
    candidates: Sequence[Candidate],
    targets: Sequence[float] = DEFAULT_TARGETS,
    tolerance: float = DEFAULT_TOLERANCE,
) -> dict[str, Any]:
    """Jointly choose target points while enforcing increasing delay severity."""

    by_id: dict[str, Mapping[str, Any]] = {}
    for row in rows:
        candidate_id = str(row.get("candidate_id") or "")
        if not candidate_id or candidate_id in by_id:
            raise ValueError(f"Missing or duplicate result candidate: {candidate_id!r}")
        if not protocol.truthy(row.get("valid")):
            raise ValueError(f"Invalid result candidate: {candidate_id}")
        by_id[candidate_id] = row
    expected = {candidate.candidate_id for candidate in candidates}
    if set(by_id) != expected:
        raise ValueError(
            f"Result grid mismatch; missing={sorted(expected - set(by_id))}, "
            f"extra={sorted(set(by_id) - expected)}"
        )
    clean_targets = tuple(float(target) for target in targets)
    if len(clean_targets) != 2 or not clean_targets[0] > clean_targets[1]:
        raise ValueError("Selection expects two descending service targets")
    metrics_by_id: dict[str, tuple[float, float, float]] = {}
    for candidate in candidates:
        row = by_id[candidate.candidate_id]
        for field, expected_offset in (
            ("offset_days_268091", candidate.offset_days_268091),
            ("offset_days_268967", candidate.offset_days_268967),
        ):
            actual_offset = protocol.finite_float(row.get(field), math.nan)
            if not math.isclose(
                actual_offset, expected_offset, rel_tol=0.0, abs_tol=1e-12
            ):
                raise ValueError(
                    f"Candidate offset mismatch: {candidate.candidate_id}/{field}"
                )
        metrics = tuple(
            protocol.finite_float(row.get(field), math.nan)
            for field in (
                "system_on_due_service",
                "on_due_service_268091",
                "on_due_service_268967",
            )
        )
        if any(not math.isfinite(value) or not 0.0 <= value <= 1.0 for value in metrics):
            raise ValueError(f"Invalid service values: {candidate.candidate_id}")
        metrics_by_id[candidate.candidate_id] = metrics

    def diagnostics(candidate: Candidate, target: float) -> dict[str, Any]:
        global_service, product_left, product_right = metrics_by_id[
            candidate.candidate_id
        ]
        left_error = abs(product_left - target)
        right_error = abs(product_right - target)
        return {
            "target_service_each_product": target,
            **asdict(candidate),
            "system_on_due_service": global_service,
            "on_due_service_268091": product_left,
            "on_due_service_268967": product_right,
            "absolute_error_268091": left_error,
            "absolute_error_268967": right_error,
            "maximum_product_error": max(left_error, right_error),
            "sum_product_error": left_error + right_error,
            "product_service_gap": abs(product_left - product_right),
            "within_tolerance_both_products": (
                left_error <= tolerance and right_error <= tolerance
            ),
        }

    ordered_pairs = (
        (high, low)
        for high in candidates
        for low in candidates
        if low.offset_days_268091 + 1e-12 >= high.offset_days_268091
        and low.offset_days_268967 + 1e-12 >= high.offset_days_268967
    )

    def assignment_score(pair: tuple[Candidate, Candidate]) -> tuple[Any, ...]:
        records = [
            diagnostics(candidate, target)
            for candidate, target in zip(pair, clean_targets, strict=True)
        ]
        return (
            max(record["maximum_product_error"] for record in records),
            sum(record["maximum_product_error"] for record in records),
            sum(record["sum_product_error"] for record in records),
            sum(record["product_service_gap"] for record in records),
            sum(
                abs(record["system_on_due_service"] - record["target_service_each_product"])
                for record in records
            ),
            sum(
                record["offset_days_268091"] + record["offset_days_268967"]
                for record in records
            ),
            tuple(record["candidate_id"] for record in records),
        )

    try:
        selected_pair = min(ordered_pairs, key=assignment_score)
    except ValueError as exc:
        raise ValueError("No monotone pair of operating points is selectable") from exc
    records = [
        diagnostics(candidate, target)
        for candidate, target in zip(selected_pair, clean_targets, strict=True)
    ]
    payload: dict[str, Any] = {
        "schema_version": SELECTION_SCHEMA_VERSION,
        "status": (
            "both_targets_attained_within_tolerance"
            if all(record["within_tolerance_both_products"] for record in records)
            else "nearest_grid_points_selected_targets_not_all_attained"
        ),
        "selection_basis": (
            "minimax error across both products and both targets; no interpolation"
        ),
        "target_tolerance": tolerance,
        "monotone_offsets_between_targets_enforced": True,
        "records": records,
        "all_targets_attained": all(
            record["within_tolerance_both_products"] for record in records
        ),
        "simulation_hypotheses_not_observed_performance": True,
    }
    payload["selection_signature"] = _stable_sha256(payload)
    return payload


def _result_rows_signature(rows: Sequence[Mapping[str, Any]]) -> str:
    canonical = []
    for row in rows:
        canonical.append(
            {
                "candidate_id": str(row.get("candidate_id") or ""),
                "offset_days_268091": protocol.finite_float(
                    row.get("offset_days_268091"), math.nan
                ),
                "offset_days_268967": protocol.finite_float(
                    row.get("offset_days_268967"), math.nan
                ),
                "seed": int(protocol.finite_float(row.get("seed"), -1)),
                "system_on_due_service": protocol.finite_float(
                    row.get("system_on_due_service"), math.nan
                ),
                "on_due_service_268091": protocol.finite_float(
                    row.get("on_due_service_268091"), math.nan
                ),
                "on_due_service_268967": protocol.finite_float(
                    row.get("on_due_service_268967"), math.nan
                ),
                "graph_sha256": str(row.get("graph_sha256") or ""),
                "valid": protocol.truthy(row.get("valid")),
            }
        )
    canonical.sort(key=lambda item: item["candidate_id"])
    return _stable_sha256(canonical)


def _signed_payload_is_valid(payload: Mapping[str, Any], signature_field: str) -> bool:
    signature = str(payload.get(signature_field) or "")
    unsigned = dict(payload)
    unsigned.pop(signature_field, None)
    return bool(signature) and signature == _stable_sha256(unsigned)


def build_campaign_operating_points(
    plan: ValidatedPlan,
    rows: Sequence[Mapping[str, Any]],
    selection: Mapping[str, Any],
    *,
    seed: int,
    source_metrics_path: Path | None = None,
    source_run_manifest_path: Path | None = None,
    evidence_signatures: Sequence[str] = (),
) -> dict[str, Any]:
    """Export the exact three-point contract consumed by the V2 campaign."""

    if not _signed_payload_is_valid(selection, "selection_signature"):
        raise ValueError("Balanced-point selection signature mismatch")
    expected_selection = select_balanced_targets(
        rows,
        candidates=plan.candidates,
        targets=plan.manifest["targets"],
        tolerance=float(plan.manifest["target_tolerance"]),
    )
    if dict(selection) != expected_selection:
        raise ValueError("Selection differs from the complete result grid")
    rows_by_id = {str(row.get("candidate_id") or ""): row for row in rows}
    if len(rows_by_id) != len(plan.candidates):
        raise ValueError("Campaign export requires the complete calibration grid")
    baseline_id = _candidate_id(0.0, 0.0)
    if baseline_id not in rows_by_id or baseline_id not in plan.inventory:
        raise ValueError("The zero/zero candidate required for op_100 is absent")
    records = list(selection.get("records") or [])
    if len(records) != 2:
        raise ValueError("The selection must contain exactly the 93 and 80 records")
    selected_by_target = {
        float(record["target_service_each_product"]): record for record in records
    }
    targets = tuple(float(target) for target in plan.manifest["targets"])
    if set(selected_by_target) != set(targets):
        raise ValueError("Selected target identities differ from the plan")

    def point(
        point_id: str,
        label: str,
        target: float,
        candidate_id: str,
    ) -> dict[str, Any]:
        row = rows_by_id[candidate_id]
        item = plan.inventory[candidate_id]
        graph = (plan.plan_dir / item["graph_path"]).resolve()
        if (
            not graph.is_file()
            or _sha256(graph) != item["graph_sha256"]
            or str(row.get("graph_sha256") or "") != item["graph_sha256"]
            or int(protocol.finite_float(row.get("seed"), -1)) != seed
            or not protocol.truthy(row.get("valid"))
        ):
            raise ValueError(f"Unproven result input for {point_id}/{candidate_id}")
        return {
            "operating_point_id": point_id,
            "operating_point_label": label,
            "target_service": target,
            "source_candidate_id": candidate_id,
            "degradation_family": "balanced_product_supplier_planned_lead",
            "degradation_unit": "jours_ajoutes_par_chaine_produit",
            "offset_days_268091": protocol.finite_float(
                row.get("offset_days_268091"), math.nan
            ),
            "offset_days_268967": protocol.finite_float(
                row.get("offset_days_268967"), math.nan
            ),
            "screening_system_service": protocol.finite_float(
                row.get("system_on_due_service"), math.nan
            ),
            "screening_product_268091_service": protocol.finite_float(
                row.get("on_due_service_268091"), math.nan
            ),
            "screening_product_268967_service": protocol.finite_float(
                row.get("on_due_service_268967"), math.nan
            ),
            "graph": str(graph),
            "graph_sha256": item["graph_sha256"],
            "supplier_floors": "",
            "supplier_floors_sha256": "",
            "factory_capacities": "",
            "factory_capacities_sha256": "",
        }

    metrics_path = source_metrics_path.resolve() if source_metrics_path else None
    run_manifest_path = (
        source_run_manifest_path.resolve() if source_run_manifest_path else None
    )
    for source_path in (metrics_path, run_manifest_path):
        if source_path is not None and not source_path.is_file():
            raise FileNotFoundError(f"Campaign export provenance missing: {source_path}")
    target_high, target_low = targets
    high_record = selected_by_target[target_high]
    low_record = selected_by_target[target_low]
    payload: dict[str, Any] = {
        "schema_version": CAMPAIGN_POINTS_SCHEMA_VERSION,
        "status": "exploratory_one_seed_calibration_complete",
        "quality_branch_included": False,
        "supplier_state_dependent_risks_enabled": False,
        "acute_incident_included_in_operating_point": False,
        "supplier_capacity_override_included": False,
        "factory_capacity_override_included": False,
        "supplier_availability_degradation_included": False,
        "simulation_hypotheses_not_observed_supplier_performance": True,
        "source_plan": {
            "path": str(plan.plan_dir),
            "plan_signature": plan.manifest["plan_signature"],
            "manifest_sha256": _sha256(plan.plan_dir / "calibration_plan.json"),
        },
        "source_results": {
            "seed": seed,
            "completed_candidate_count": len(rows_by_id),
            "result_rows_signature": _result_rows_signature(rows),
            "metrics_csv": str(metrics_path) if metrics_path else "",
            "metrics_csv_sha256": _sha256(metrics_path) if metrics_path else "",
            "run_manifest": str(run_manifest_path) if run_manifest_path else "",
            "run_manifest_sha256": (
                _sha256(run_manifest_path) if run_manifest_path else ""
            ),
            "evidence_signature_set_sha256": _stable_sha256(
                sorted(str(value) for value in evidence_signatures)
            ),
            "evidence_signature_count": len(evidence_signatures),
        },
        "selection_signature": selection["selection_signature"],
        "engine_sha256": _sha256(plan.engine),
        "profile_sha256": _sha256(plan.profile),
        "operating_points": [
            point(
                "op_100",
                "Fonctionnement de référence — délais sans ajout",
                1.0,
                baseline_id,
            ),
            point(
                "op_93",
                "Fonctionnement visant 93 % pour chacun des deux produits",
                target_high,
                str(high_record["candidate_id"]),
            ),
            point(
                "op_80",
                "Fonctionnement visant 80 % pour chacun des deux produits",
                target_low,
                str(low_record["candidate_id"]),
            ),
        ],
    }
    payload["artifact_signature"] = _stable_sha256(payload)
    return payload


def validate_campaign_operating_points(
    payload_or_path: Mapping[str, Any] | Path,
    *,
    plan: ValidatedPlan,
    rows: Sequence[Mapping[str, Any]],
    selection: Mapping[str, Any],
    seed: int,
    evidence_signatures: Sequence[str] = (),
) -> dict[str, Any]:
    payload = (
        _read_json(payload_or_path.resolve())
        if isinstance(payload_or_path, Path)
        else dict(payload_or_path)
    )
    if (
        payload.get("schema_version") != CAMPAIGN_POINTS_SCHEMA_VERSION
        or not _signed_payload_is_valid(payload, "artifact_signature")
        or payload.get("quality_branch_included") is not False
        or payload.get("supplier_state_dependent_risks_enabled") is not False
        or payload.get("acute_incident_included_in_operating_point") is not False
        or payload.get("supplier_capacity_override_included") is not False
        or payload.get("factory_capacity_override_included") is not False
        or payload.get("supplier_availability_degradation_included") is not False
    ):
        raise ValueError("Campaign operating-point artifact contract mismatch")
    source_results = payload.get("source_results") or {}
    metrics_text = str(source_results.get("metrics_csv") or "")
    run_manifest_text = str(source_results.get("run_manifest") or "")
    expected = build_campaign_operating_points(
        plan,
        rows,
        selection,
        seed=seed,
        source_metrics_path=Path(metrics_text) if metrics_text else None,
        source_run_manifest_path=(
            Path(run_manifest_text) if run_manifest_text else None
        ),
        evidence_signatures=evidence_signatures,
    )
    if payload != expected:
        raise ValueError("Campaign operating-point provenance/results mismatch")
    return payload


def _load_existing_evidence(
    output_dir: Path, plan: ValidatedPlan, seed: int
) -> dict[str, dict[str, Any]]:
    found: dict[str, dict[str, Any]] = {}
    for candidate in plan.candidates:
        path = _evidence_path(output_dir, candidate.candidate_id)
        if not path.is_file():
            continue
        evidence = _read_json(path)
        _validate_evidence(evidence, candidate, plan, seed)
        found[candidate.candidate_id] = evidence
    return found


def _write_progress(
    output_dir: Path,
    *,
    plan: ValidatedPlan,
    seed: int,
    evidence: Mapping[str, Mapping[str, Any]],
    status: str,
) -> None:
    rows = [_result_row(item) for item in evidence.values()]
    rows.sort(
        key=lambda row: (
            float(row["offset_days_268091"]),
            float(row["offset_days_268967"]),
        )
    )
    _write_csv(output_dir / "screening_metrics.csv", rows, RESULT_FIELDS)
    _write_json(
        output_dir / "progress.json",
        {
            "schema_version": RESULTS_SCHEMA_VERSION,
            "plan_signature": plan.manifest["plan_signature"],
            "engine_sha256": _sha256(plan.engine),
            "seed": seed,
            "status": status,
            "planned_case_count": len(plan.candidates),
            "completed_case_count": len(evidence),
            "failed_case_count": 0,
            "updated_at_utc": _now(),
        },
    )


@contextmanager
def _exclusive_lock(output_dir: Path) -> Iterable[None]:
    path = output_dir / ".balanced_delay_calibration.lock"
    try:
        descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError as exc:
        raise RuntimeError(f"Another calibration owns {path}") from exc
    try:
        os.write(descriptor, f"pid={os.getpid()} utc={_now()}\n".encode())
        os.close(descriptor)
        yield
    finally:
        path.unlink(missing_ok=True)


def run_grid(
    plan_dir: Path,
    output_dir: Path,
    *,
    seed: int = DEFAULT_SEED,
    workers: int = 2,
    executor: CaseExecutor = execute_candidate,
) -> dict[str, Any]:
    """Execute or resume the one-seed grid and select balanced target points."""

    if workers not in (1, 2):
        raise ValueError("Use one or two workers to bound memory use")
    plan = validate_plan(plan_dir)
    output_dir = output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    run_manifest_path = output_dir / "run_manifest.json"
    expected_run_manifest = {
        "schema_version": RESULTS_SCHEMA_VERSION,
        "plan_signature": plan.manifest["plan_signature"],
        "engine_sha256": _sha256(plan.engine),
        "seed": int(seed),
        "planned_case_count": len(plan.candidates),
        "common_random_numbers": True,
    }
    if run_manifest_path.is_file():
        if _read_json(run_manifest_path) != expected_run_manifest:
            raise ValueError("Existing result directory belongs to another run")
    else:
        unmanaged = [
            path for path in output_dir.iterdir() if path.name != run_manifest_path.name
        ]
        if unmanaged:
            raise ValueError("Refusing a non-empty unregistered result directory")
        _write_json(run_manifest_path, expected_run_manifest)
    with _exclusive_lock(output_dir):
        evidence = _load_existing_evidence(output_dir, plan, seed)
        missing = [
            candidate
            for candidate in plan.candidates
            if candidate.candidate_id not in evidence
        ]
        _write_progress(
            output_dir,
            plan=plan,
            seed=seed,
            evidence=evidence,
            status="running" if missing else "complete",
        )
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = {
                pool.submit(executor, candidate, plan, output_dir, seed): candidate
                for candidate in missing
            }
            for future in as_completed(futures):
                candidate = futures[future]
                item = future.result()
                _validate_evidence(item, candidate, plan, seed)
                _write_json(_evidence_path(output_dir, candidate.candidate_id), item)
                evidence[candidate.candidate_id] = item
                _write_progress(
                    output_dir,
                    plan=plan,
                    seed=seed,
                    evidence=evidence,
                    status="running",
                )
        if len(evidence) != len(plan.candidates):
            raise RuntimeError("Balanced-delay grid did not complete")
        rows = [_result_row(evidence[candidate.candidate_id]) for candidate in plan.candidates]
        selection = select_balanced_targets(
            rows,
            candidates=plan.candidates,
            targets=plan.manifest["targets"],
            tolerance=float(plan.manifest["target_tolerance"]),
        )
        _write_json(output_dir / "balanced_operating_points.json", selection)
        _write_progress(
            output_dir,
            plan=plan,
            seed=seed,
            evidence=evidence,
            status="complete",
        )
        evidence_signatures = [
            str(evidence[candidate.candidate_id]["evidence_signature"])
            for candidate in plan.candidates
        ]
        campaign_points = build_campaign_operating_points(
            plan,
            rows,
            selection,
            seed=seed,
            source_metrics_path=output_dir / "screening_metrics.csv",
            source_run_manifest_path=run_manifest_path,
            evidence_signatures=evidence_signatures,
        )
        campaign_points_path = output_dir / "campaign_operating_points.json"
        _write_json(campaign_points_path, campaign_points)
        validate_campaign_operating_points(
            campaign_points_path,
            plan=plan,
            rows=rows,
            selection=selection,
            seed=seed,
            evidence_signatures=evidence_signatures,
        )
    return selection


def select_from_results(plan_dir: Path, metrics_csv: Path, output_path: Path) -> dict[str, Any]:
    plan = validate_plan(plan_dir)
    rows = _read_csv(metrics_csv.resolve())
    selection = select_balanced_targets(
        rows,
        candidates=plan.candidates,
        targets=plan.manifest["targets"],
        tolerance=float(plan.manifest["target_tolerance"]),
    )
    _write_json(output_path.resolve(), selection)
    return selection


def export_completed_run(plan_dir: Path, output_dir: Path) -> dict[str, Any]:
    """Idempotently export campaign points from complete metrics and evidence."""

    plan = validate_plan(plan_dir)
    output_dir = output_dir.resolve()
    metrics_path = output_dir / "screening_metrics.csv"
    run_manifest_path = output_dir / "run_manifest.json"
    if not metrics_path.is_file() or not run_manifest_path.is_file():
        raise FileNotFoundError("Complete metrics and run_manifest.json are required")
    rows = _read_csv(metrics_path)
    seeds = {
        int(protocol.finite_float(row.get("seed"), -1))
        for row in rows
    }
    if len(seeds) != 1 or min(seeds) < 0:
        raise ValueError("Campaign export requires one explicit common seed")
    seed = seeds.pop()
    expected_run_manifest = {
        "schema_version": RESULTS_SCHEMA_VERSION,
        "plan_signature": plan.manifest["plan_signature"],
        "engine_sha256": _sha256(plan.engine),
        "seed": seed,
        "planned_case_count": len(plan.candidates),
        "common_random_numbers": True,
    }
    if _read_json(run_manifest_path) != expected_run_manifest:
        raise ValueError("Run manifest differs from the balanced calibration plan")
    evidence = _load_existing_evidence(output_dir, plan, seed)
    if len(evidence) != len(plan.candidates):
        raise ValueError(
            f"Calibration evidence incomplete: {len(evidence)}/{len(plan.candidates)}"
        )
    evidence_rows = [
        _result_row(evidence[candidate.candidate_id]) for candidate in plan.candidates
    ]
    if _result_rows_signature(rows) != _result_rows_signature(evidence_rows):
        raise ValueError("Metrics CSV differs from the signed case evidence")
    selection = select_balanced_targets(
        rows,
        candidates=plan.candidates,
        targets=plan.manifest["targets"],
        tolerance=float(plan.manifest["target_tolerance"]),
    )
    selection_path = output_dir / "balanced_operating_points.json"
    if selection_path.is_file():
        if _read_json(selection_path) != selection:
            raise ValueError("Existing balanced selection differs from signed results")
    else:
        _write_json(selection_path, selection)
    evidence_signatures = [
        str(evidence[candidate.candidate_id]["evidence_signature"])
        for candidate in plan.candidates
    ]
    campaign_points = build_campaign_operating_points(
        plan,
        rows,
        selection,
        seed=seed,
        source_metrics_path=metrics_path,
        source_run_manifest_path=run_manifest_path,
        evidence_signatures=evidence_signatures,
    )
    campaign_path = output_dir / "campaign_operating_points.json"
    if campaign_path.is_file():
        validate_campaign_operating_points(
            campaign_path,
            plan=plan,
            rows=rows,
            selection=selection,
            seed=seed,
            evidence_signatures=evidence_signatures,
        )
        if _read_json(campaign_path) != campaign_points:
            raise ValueError("Existing campaign operating points are not idempotent")
    else:
        _write_json(campaign_path, campaign_points)
        validate_campaign_operating_points(
            campaign_path,
            plan=plan,
            rows=rows,
            selection=selection,
            seed=seed,
            evidence_signatures=evidence_signatures,
        )
    return campaign_points


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--mode",
        choices=("plan", "validate", "run", "select", "export"),
        required=True,
    )
    parser.add_argument("--plan-dir", type=Path, default=DEFAULT_PLAN_OUTPUT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_RUN_OUTPUT)
    parser.add_argument("--active-lanes", type=Path, default=DEFAULT_ACTIVE_LANES)
    parser.add_argument("--graph", type=Path, default=protocol.DEFAULT_GRAPH)
    parser.add_argument("--engine", type=Path, default=protocol.DEFAULT_ENGINE)
    parser.add_argument("--profile", type=Path, default=protocol.DEFAULT_PROFILE)
    parser.add_argument(
        "--offsets-268091",
        default=",".join(format(value, ".12g") for value in DEFAULT_OFFSETS_268091),
    )
    parser.add_argument(
        "--offsets-268967",
        default=",".join(format(value, ".12g") for value in DEFAULT_OFFSETS_268967),
    )
    parser.add_argument("--targets", default="0.93,0.80")
    parser.add_argument("--tolerance", type=float, default=DEFAULT_TOLERANCE)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--workers", type=int, choices=(1, 2), default=2)
    parser.add_argument("--metrics-csv", type=Path, default=None)
    parser.add_argument("--selection-output", type=Path, default=None)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    if args.mode == "plan":
        path = prepare_plan(
            args.plan_dir,
            active_lanes_path=args.active_lanes,
            graph_path=args.graph,
            engine_path=args.engine,
            profile_path=args.profile,
            offsets_268091=_parse_float_list(args.offsets_268091, "offsets 268091"),
            offsets_268967=_parse_float_list(args.offsets_268967, "offsets 268967"),
            targets=_parse_descending_target_list(args.targets),
            tolerance=args.tolerance,
        )
        print(f"Plan prepared, no simulation executed: {path}")
    elif args.mode == "validate":
        plan = validate_plan(args.plan_dir)
        print(
            f"Valid plan: {len(plan.candidates)} candidates; "
            + ", ".join(
                f"{product}={len(plan.lanes_by_product[product])} lanes"
                for product in PRODUCTS
            )
        )
    elif args.mode == "run":
        selection = run_grid(
            args.plan_dir,
            args.output_dir,
            seed=args.seed,
            workers=args.workers,
        )
        print(json.dumps(selection, ensure_ascii=False, indent=2))
    elif args.mode == "select":
        if args.metrics_csv is None:
            raise ValueError("--metrics-csv is required in select mode")
        output = args.selection_output or (
            args.output_dir / "balanced_operating_points.json"
        )
        selection = select_from_results(args.plan_dir, args.metrics_csv, output)
        print(json.dumps(selection, ensure_ascii=False, indent=2))
    else:
        campaign_points = export_completed_run(args.plan_dir, args.output_dir)
        print(
            "Campaign operating points exported without simulation: "
            f"{args.output_dir.resolve() / 'campaign_operating_points.json'}"
        )
        print(json.dumps(campaign_points, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
