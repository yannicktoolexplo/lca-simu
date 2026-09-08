#!/usr/bin/env python3
"""Execute the frozen V5 exploratory action protocol, fail closed.

This runner never recreates the paired normal or untreated incident arms.  It
validates and reuses the exact V2/V3 evidence, then executes only the three
currently representable action hypotheses.  The fourth hypothesis (an
alternative source) remains blocked because the reference graph is mono-source.

The first 15 seeds are an exact, signed checkpoint of the 30-seed campaign.
Smoke evidence has a distinct signature and can never be reused by that
campaign.  No industrial action cost is inferred from engine model costs.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import contextmanager
from dataclasses import asdict, dataclass, replace
from datetime import datetime, timezone
from pathlib import Path
from statistics import fmean, pstdev
from typing import Any, Callable, Iterable, Mapping, Sequence


REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from etudecas.prototypes.scan_2027_risk_control import (  # noqa: E402
    supplier_network_exploratory_action_protocol as protocol,
)
from etudecas.prototypes.scan_2027_risk_control import (  # noqa: E402
    supplier_network_post_priority_extension_runner as post_runner,
)
from etudecas.prototypes.scan_2027_risk_control import (  # noqa: E402
    supplier_network_risk_screen_campaign as network,
)
from etudecas.simulation.engine.control_schedule import (  # noqa: E402
    CONTROL_SCHEDULE_COLUMNS,
    ControlCatalog,
    load_control_schedule,
)


SCHEMA_VERSION = "etudecas.supplier_network_exploratory_action_runner.v1"
LEDGER_SCHEMA_VERSION = f"{SCHEMA_VERSION}.ledger"
EVIDENCE_SCHEMA_VERSION = f"{SCHEMA_VERSION}.case_evidence"
CHECKPOINT_SCHEMA_VERSION = f"{SCHEMA_VERSION}.checkpoint_15_of_30"
CONTRACT_REVISION = "v5_exact_sources_open_loop_actions_checkpoint_2026_09"
EXPECTED_PROTOCOL_REVISION = protocol.CONTRACT_REVISION
EXPECTED_PROTOCOL_BUILDER_SHA256 = (
    "2b0d39d9dacd607c7ad10590cd702128b04f8e2711a6ba136c281df57cce0403"
)
DEFAULT_PROTOCOL_DIR = (
    protocol.ARTIFACT_PARENT
    / "supplier_network_exploratory_action_protocol_20260903_v5"
)
DEFAULT_POST_PRIORITY_RESULTS = (
    protocol.ARTIFACT_PARENT / "supplier_network_post_priority_extensions_20260903_v1"
)
DEFAULT_J0_SNAPSHOT_DIR = (
    protocol.ARTIFACT_PARENT / "supplier_network_action_j0_snapshot_20260903_v1"
)
EXECUTABLE_LEVERS = (
    "future_lane_transport_reduction",
    "prepositioned_free_stock_14d",
    "quality_scenario_full_lane_calendar_open_loop_transport_reduction_7d",
)
BLOCKED_LEVER = "explicit_counterfactual_alternative_source"
RUNNER_MANIFEST = "action_runner_manifest.json"
LEDGER_FILE = "execution_ledger.json"
CHECKPOINT_FILE = "preliminary_checkpoint_15_manifest.json"
PRELIMINARY_RESULTS_FILE = "preliminary_paired_action_results.csv"
PRELIMINARY_SUMMARY_FILE = "preliminary_action_results_summary.csv"
FINAL_RESULTS_FILE = "paired_action_results.csv"
FINAL_SUMMARY_FILE = "action_results_summary.csv"
LOCK_FILE = ".action_runner.lock"
J0_SNAPSHOT_SCHEMA_VERSION = "etudecas.supplier_network_action_j0_snapshot.v1"
J0_SNAPSHOT_MANIFEST = "j0_snapshot_manifest.json"
J0_SNAPSHOT_ROWS = "j0_cutover_states.csv"
J0_SNAPSHOT_COLUMNS = (
    "schema_version",
    "seed",
    "seed_prefix_index",
    "baseline_case_key",
    "baseline_evidence_relative_path",
    "baseline_evidence_sha256",
    "source_runner_signature",
    "chain_id",
    "supplier_id",
    "node_id",
    "item_id",
    "uom",
    "stock_before_production_day0_qty",
    "arrival_day0_qty",
    "cutover_stock_before_day0_flows_qty",
    "reconstruction",
    "summary_sha256",
    "stocks_daily_sha256",
    "arrivals_daily_sha256",
    "lot_events_sha256",
    "lot_genealogy_sha256",
    "source_lot_trace_enabled",
    "warmup_core_state_sha256",
    "warmup_component_sha256_json",
    "row_signature",
)
SEED_POLICY = "signed_cumulative_prefix_15_then_30"
MEASURED_DAYS = protocol.SIMULATION_DAYS
CLIENT_NODE_ID = "C-XXXXX"
PRODUCTS = tuple(network.TARGET_PRODUCTS)
ZERO_EPS = 1e-9


class SourcesNotReadyError(RuntimeError):
    """Raised before any action execution when paired sources are incomplete."""


@dataclass(frozen=True)
class ActionCase:
    pairing_id: str
    seed: int
    seed_prefix_index: int
    selection_slot: int
    chain_id: str
    supplier_id: str
    item_id: str
    dst_node_id: str
    edge_id: str
    target_product_id: str
    lever_id: str
    failure_mode: str
    incident_source_case_id: str
    incident_risk_type: str
    incident_value: float
    incident_unit: str
    incident_start_day: int
    incident_end_day: int
    lead_time_adjustment_days: int | None
    buffer_raw_qty: float | None
    buffer_rounded_qty: float | None
    procurement_standard_lot_qty: float | None
    buffer_procurement_lot_count: int | None
    buffer_uom: str
    stage: str = "full"

    @property
    def key(self) -> str:
        return self.pairing_id


@dataclass(frozen=True)
class ActionPlan:
    plan_dir: Path
    manifest: Mapping[str, Any]
    cases: tuple[ActionCase, ...]
    seeds: tuple[int, ...]
    graph_path: Path
    engine_path: Path
    profile_path: Path
    graph: Mapping[str, Any]
    source_dir: Path
    post_priority_plan_dir: Path
    post_priority_plan_manifest: Mapping[str, Any]
    supplier_floors_path: Path
    physical_capacity_by_lane: Mapping[tuple[str, str, str], float]
    profile_args: tuple[str, ...]


@dataclass(frozen=True)
class SourceBundle:
    source_dir: Path
    post_priority_results_dir: Path
    target_seed_ids: tuple[int, ...]
    v2_rows: Mapping[tuple[str, int], Mapping[str, str]]
    v3_quality_evidence: Mapping[tuple[str, int], Mapping[str, Any]]
    v3_baseline_evidence: Mapping[int, Mapping[str, Any]]
    v3_evidence_hashes: Mapping[str, str]
    incident_risk_rows: Mapping[tuple[str, int], tuple[Mapping[str, Any], ...]]
    incident_risk_semantic_sha256: Mapping[tuple[str, int], str]
    baseline_j0: Mapping[tuple[int, str], Mapping[str, Any]]
    source_identity: Mapping[str, Any]
    source_identity_signature: str

    def fingerprint(self, case: ActionCase) -> str:
        payload: dict[str, Any] = {
            "source_identity_signature": self.source_identity_signature,
            "pairing_id": case.pairing_id,
            "seed": case.seed,
            "normal": _stable_sha256(self.v2_rows[("baseline_nominal", case.seed)]),
        }
        if case.failure_mode == "quality_hold":
            key = (case.incident_source_case_id, case.seed)
            evidence = self.v3_quality_evidence[key]
            payload["incident_v3_case_key"] = evidence["case_key"]
            payload["incident_v3_evidence_sha256"] = self.v3_evidence_hashes[
                str(evidence["case_key"])
            ]
        else:
            payload["incident"] = _stable_sha256(
                self.v2_rows[(case.incident_source_case_id, case.seed)]
            )
        payload["incident_risk_semantic_sha256"] = self.incident_risk_semantic_sha256[
            (case.incident_source_case_id, case.seed)
        ]
        if case.lever_id == "prepositioned_free_stock_14d":
            payload["baseline_j0"] = self.baseline_j0[(case.seed, case.chain_id)]
        return _stable_sha256(payload)


@dataclass(frozen=True)
class InputBundle:
    root: Path
    risk_csv: Path
    risk_sha256: str
    control_schedule_csv: Path | None
    control_schedule_sha256: str
    stock_scale_csv: Path | None
    stock_scale_sha256: str
    input_manifest: Path
    input_manifest_sha256: str
    j0_stock_before_qty: float | None
    j0_stock_scale: float | None


CaseExecutor = Callable[
    [ActionCase, ActionPlan, SourceBundle, Path, InputBundle], Mapping[str, Any]
]


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sha256(path: Path) -> str:
    return network.campaign_core.sha256_file(path)


def _stable_sha256(payload: Any) -> str:
    raw = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _read_json(path: Path) -> dict[str, Any]:
    return network.campaign_core.read_json(path)


def _read_csv(path: Path) -> list[dict[str, str]]:
    return network.campaign_core.read_csv_rows(path)


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    for attempt in range(5):
        try:
            network.campaign_core.write_json_atomic(path, payload)
            return
        except PermissionError:
            if attempt == 4:
                raise
            time.sleep(0.02 * (attempt + 1))


def _write_csv(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    for attempt in range(5):
        try:
            network.campaign_core.write_csv_atomic(path, rows)
            return
        except PermissionError:
            if attempt == 4:
                raise
            time.sleep(0.02 * (attempt + 1))


def _as_bool(value: Any) -> bool:
    return network.campaign_core.as_bool(value)


def _to_int(value: Any, default: int = 0) -> int:
    return network.campaign_core.to_int(value, default)


def _to_float(value: Any, default: float = 0.0) -> float:
    return network.campaign_core.to_float(value, default)


def _required_file(path: Path, label: str) -> Path:
    path = path.resolve()
    if path.is_symlink() or not path.is_file():
        raise FileNotFoundError(f"Missing or redirected {label}: {path}")
    return path


def _safe_descendant(root: Path, value: Any, label: str) -> Path:
    root = root.resolve()
    path = Path(str(value or "")).resolve()
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise ValueError(f"{label} escapes its source artifact: {path}") from exc
    if path.is_symlink():
        raise ValueError(f"{label} is redirected: {path}")
    return path


def _case_digest(case_key: str) -> str:
    return hashlib.sha256(case_key.encode("utf-8")).hexdigest()[:20]


def _evidence_relative(case_key: str) -> Path:
    return Path("ledger_cases") / f"{_case_digest(case_key)}.json"


def _signed_payload(payload: Mapping[str, Any], signature_field: str) -> dict[str, Any]:
    unsigned = dict(payload)
    unsigned.pop(signature_field, None)
    return {**unsigned, signature_field: _stable_sha256(unsigned)}


def _validate_signed_payload(
    payload: Mapping[str, Any], signature_field: str, *, label: str
) -> None:
    unsigned = dict(payload)
    signature = str(unsigned.pop(signature_field, ""))
    if not signature or _stable_sha256(unsigned) != signature:
        raise ValueError(f"Invalid {label} integrity signature")


def _require_hash(path: Path, expected: Any, label: str) -> None:
    if _sha256(_required_file(path, label)) != str(expected or ""):
        raise ValueError(f"Hash mismatch for {label}")


def _validate_execution_files_unchanged(plan: ActionPlan) -> None:
    """Fail closed if an execution input changed after the V5 plan was loaded."""

    for field, path in (
        ("graph_sha256", plan.graph_path),
        ("engine_sha256", plan.engine_path),
        ("profile_sha256", plan.profile_path),
    ):
        _require_hash(path, plan.manifest.get(field), field)


def _graph_catalog(graph: Mapping[str, Any]) -> ControlCatalog:
    nodes = {str(row.get("id") or "") for row in graph.get("nodes") or []}
    suppliers = {
        str(row.get("id") or "")
        for row in graph.get("nodes") or []
        if str(row.get("type") or "").lower() == "supplier"
    }
    items = {
        str(item)
        for edge in graph.get("edges") or []
        for item in edge.get("items") or []
        if str(item)
    }
    return ControlCatalog(
        node_ids=nodes,
        supplier_ids=suppliers,
        item_ids=items,
        dst_node_ids=nodes,
    )


def _build_cases(
    parameters: Sequence[Mapping[str, str]],
    design: Sequence[Mapping[str, str]],
) -> tuple[ActionCase, ...]:
    parameter_by_key = {
        (str(row.get("chain_id") or ""), str(row.get("lever_id") or "")): row
        for row in parameters
    }
    if len(parameter_by_key) != len(parameters):
        raise ValueError("Duplicate V5 action parameter")
    grouped: dict[str, dict[str, Mapping[str, str]]] = {}
    for row in design:
        pairing_id = str(row.get("pairing_id") or "")
        arm = str(row.get("arm") or "")
        if not pairing_id or arm in grouped.setdefault(pairing_id, {}):
            raise ValueError("Duplicate or blank paired design row")
        grouped[pairing_id][arm] = row
    cases: list[ActionCase] = []
    for pairing_id, arms in grouped.items():
        if set(arms) != {"normal", "incident_no_action", "incident_with_action"}:
            raise ValueError(f"Incomplete V5 triplet: {pairing_id}")
        action = arms["incident_with_action"]
        lever = str(action.get("lever_id") or "")
        new_count = _to_int(action.get("new_engine_run_count"), -1)
        if lever == BLOCKED_LEVER:
            if new_count != 0 or not str(
                action.get("execution_status") or ""
            ).startswith("blocked_"):
                raise ValueError("Alternative-source lever is not fail-closed")
            continue
        if lever not in EXECUTABLE_LEVERS or new_count != 1:
            raise ValueError(f"Unexpected executable action row: {pairing_id}")
        chain = str(action.get("chain_id") or "")
        parameter = parameter_by_key[(chain, lever)]
        incident = arms["incident_no_action"]
        normal = arms["normal"]
        if (
            str(normal.get("source_case_id") or "") != "baseline_nominal"
            or str(incident.get("source_case_id") or "") == ""
            or _as_bool(action.get("graph_counterfactual"))
            or _as_bool(action.get("priority_weight_used"))
            or _as_bool(action.get("closed_loop_claimed"))
        ):
            raise ValueError(f"Unsafe paired design contract: {pairing_id}")
        lead_raw = str(parameter.get("lead_time_adjustment_days") or "").strip()
        buffer_raw_unparsed = str(parameter.get("buffer_raw_qty") or "").strip()
        buffer_raw = str(parameter.get("buffer_rounded_qty") or "").strip()
        standard_lot_raw = str(
            parameter.get("procurement_standard_lot_qty") or ""
        ).strip()
        lot_count_raw = str(parameter.get("buffer_procurement_lot_count") or "").strip()
        case = ActionCase(
            pairing_id=pairing_id,
            seed=_to_int(action.get("seed"), -1),
            seed_prefix_index=_to_int(action.get("seed_prefix_index"), -1),
            selection_slot=_to_int(action.get("selection_slot"), -1),
            chain_id=chain,
            supplier_id=str(action.get("supplier_id") or ""),
            item_id=str(action.get("item_id") or ""),
            dst_node_id=str(action.get("dst_node_id") or ""),
            edge_id=str(parameter.get("edge_id") or ""),
            target_product_id=str(action.get("target_product_id") or ""),
            lever_id=lever,
            failure_mode=str(action.get("failure_mode") or ""),
            incident_source_case_id=str(incident.get("source_case_id") or ""),
            incident_risk_type=str(parameter.get("incident_risk_type") or ""),
            incident_value=_to_float(parameter.get("incident_value"), math.nan),
            incident_unit=str(parameter.get("incident_unit") or ""),
            incident_start_day=_to_int(parameter.get("incident_start_day"), -1),
            incident_end_day=_to_int(parameter.get("incident_end_day"), -1),
            lead_time_adjustment_days=(_to_int(lead_raw) if lead_raw else None),
            buffer_raw_qty=(
                _to_float(buffer_raw_unparsed, math.nan)
                if buffer_raw_unparsed
                else None
            ),
            buffer_rounded_qty=(
                _to_float(buffer_raw, math.nan) if buffer_raw else None
            ),
            procurement_standard_lot_qty=(
                _to_float(standard_lot_raw, math.nan) if standard_lot_raw else None
            ),
            buffer_procurement_lot_count=(
                _to_int(lot_count_raw, -1) if lot_count_raw else None
            ),
            buffer_uom=str(parameter.get("buffer_uom") or ""),
        )
        if (
            case.seed < 0
            or case.target_product_id not in PRODUCTS
            or case.incident_start_day < 0
            or case.incident_end_day < case.incident_start_day
            or case.incident_end_day >= MEASURED_DAYS
            or not all(
                (
                    case.chain_id,
                    case.supplier_id,
                    case.item_id,
                    case.dst_node_id,
                    case.edge_id,
                )
            )
        ):
            raise ValueError(f"Invalid action case: {pairing_id}")
        if case.lever_id == "prepositioned_free_stock_14d":
            if (
                not case.buffer_raw_qty
                or case.buffer_raw_qty <= 0
                or not case.buffer_rounded_qty
                or case.buffer_rounded_qty <= 0
                or not case.procurement_standard_lot_qty
                or case.procurement_standard_lot_qty <= 0
                or not case.buffer_procurement_lot_count
                or case.buffer_procurement_lot_count <= 0
                or not math.isclose(
                    case.buffer_rounded_qty,
                    case.procurement_standard_lot_qty
                    * case.buffer_procurement_lot_count,
                    rel_tol=0.0,
                    abs_tol=1e-8,
                )
                or case.buffer_rounded_qty + 1e-8 < case.buffer_raw_qty
                or not case.buffer_uom
                or any(
                    str(parameter.get(field) or "").strip()
                    for field in (
                        "procurement_moq_qty",
                        "procurement_explicit_multiple_qty",
                        "procurement_max_order_qty",
                    )
                )
            ):
                raise ValueError(f"Unquantified J0 buffer: {pairing_id}")
        elif case.lead_time_adjustment_days != -protocol.TRANSPORT_REDUCTION_DAYS:
            raise ValueError(
                f"Transport action is not the frozen -7 days: {pairing_id}"
            )
        if case.failure_mode == "quality_hold" and (
            case.incident_risk_type != "quality_delay"
            or not math.isclose(case.incident_value, 90.0, abs_tol=1e-12)
        ):
            raise ValueError("Quality action no longer preserves the 90-day hold")
        cases.append(case)
    cases.sort(
        key=lambda row: (
            row.selection_slot,
            EXECUTABLE_LEVERS.index(row.lever_id),
            row.seed_prefix_index,
        )
    )
    if len(cases) != 360:
        raise ValueError(f"V5 executable case count must be 360, found {len(cases)}")
    return tuple(cases)


def load_action_plan(
    *,
    plan_dir: Path,
    graph: Path,
    engine: Path,
    profile: Path,
) -> ActionPlan:
    plan_dir = plan_dir.resolve()
    protocol.validate_protocol_artifact(plan_dir)
    manifest_path = _required_file(
        plan_dir / "exploratory_action_protocol_manifest.json", "V5 manifest"
    )
    manifest = _read_json(manifest_path)
    if (
        manifest.get("contract_revision") != EXPECTED_PROTOCOL_REVISION
        or manifest.get("builder_sha256") != EXPECTED_PROTOCOL_BUILDER_SHA256
        or _sha256(Path(protocol.__file__).resolve())
        != EXPECTED_PROTOCOL_BUILDER_SHA256
        or manifest.get("engine_execution_enabled") is not False
    ):
        raise ValueError("The action protocol is not the frozen V5 contract")
    graph_path = _required_file(graph, "graph")
    engine_path = _required_file(engine, "engine")
    profile_path = _required_file(profile, "engine profile")
    for name, path in (
        ("graph_sha256", graph_path),
        ("engine_sha256", engine_path),
        ("profile_sha256", profile_path),
    ):
        _require_hash(path, manifest.get(name), name)
    post_plan_dir = Path(str(manifest.get("post_priority_plan_dir") or "")).resolve()
    post_manifest_path = _required_file(
        post_plan_dir / "post_priority_extensions_plan_manifest.json",
        "post-priority V3 plan manifest",
    )
    _require_hash(
        post_manifest_path,
        manifest.get("post_priority_plan_manifest_sha256"),
        "post-priority V3 plan manifest",
    )
    post_manifest = _read_json(post_manifest_path)
    if post_manifest.get("plan_signature") != manifest.get(
        "post_priority_plan_signature"
    ):
        raise ValueError("V3 and V5 plan signatures differ")
    source_dir = Path(str(manifest.get("source_campaign_dir") or "")).resolve()
    source_manifest_path = _required_file(
        source_dir / "campaign_manifest.json", "V2 manifest"
    )
    _require_hash(
        source_manifest_path,
        manifest.get("source_campaign_manifest_sha256"),
        "V2 manifest",
    )
    floors = _required_file(
        source_dir / "inputs" / "prepared_physical_supplier_floors.csv",
        "prepared supplier floors",
    )
    floor_rows = _read_csv(floors)
    floor_signature = network.campaign_core.campaign_signature({"rows": floor_rows})
    source_manifest = _read_json(source_manifest_path)
    if floor_signature != source_manifest.get("prepared_supplier_floor_content_sha256"):
        raise ValueError("Prepared supplier floors differ from V2")
    physical_map = {
        (
            str(row.get("supplier_id") or ""),
            str(row.get("item_id") or ""),
            str(row.get("dst_node_id") or ""),
        ): _to_float(row.get("tested_capacity_floor_qty_per_day"), math.nan)
        for row in floor_rows
    }
    parameters = _read_csv(plan_dir / "action_lever_parameters.csv")
    design = _read_csv(plan_dir / "paired_experiment_design.csv")
    cases = _build_cases(parameters, design)
    seeds = tuple(_to_int(value, -1) for value in manifest.get("seeds") or [])
    if (
        len(seeds) != protocol.FINAL_REPEAT_COUNT
        or len(set(seeds)) != len(seeds)
        or {case.seed for case in cases} != set(seeds)
    ):
        raise ValueError("V5 seed contract is incomplete")
    return ActionPlan(
        plan_dir=plan_dir,
        manifest=manifest,
        cases=cases,
        seeds=seeds,
        graph_path=graph_path,
        engine_path=engine_path,
        profile_path=profile_path,
        graph=_read_json(graph_path),
        source_dir=source_dir,
        post_priority_plan_dir=post_plan_dir,
        post_priority_plan_manifest=post_manifest,
        supplier_floors_path=floors,
        physical_capacity_by_lane=physical_map,
        profile_args=tuple(network.campaign_core.engine_profile_args(profile_path)),
    )


def _v3_case_key(case_id: str, seed: int) -> str:
    return f"priority_four_business_causes::{case_id}::seed_{seed}"


def _v3_baseline_key(seed: int) -> str:
    return f"baseline::baseline_metrics__seed_{seed}::seed_{seed}"


def _load_v3_evidence(
    root: Path,
    ledger: Mapping[str, Any],
    case_key: str,
) -> tuple[dict[str, Any], str]:
    files = ledger.get("case_files") or {}
    hashes = ledger.get("case_file_sha256") or {}
    relative = Path(str(files.get(case_key) or ""))
    canonical = Path("ledger_cases") / f"{_case_digest(case_key)}.json"
    if (
        relative.is_absolute()
        or ".." in relative.parts
        or relative.as_posix() != canonical.as_posix()
        or case_key not in hashes
    ):
        raise SourcesNotReadyError(f"V3 evidence is absent: {case_key}")
    path = _safe_descendant(root, root / relative, "V3 evidence")
    _require_hash(path, hashes[case_key], f"V3 evidence {case_key}")
    payload = _read_json(path)
    if payload.get("case_key") != case_key or payload.get("valid") is not True:
        raise ValueError(f"Invalid V3 evidence: {case_key}")
    return payload, str(hashes[case_key])


def _validate_completed_v3_ledger(
    *,
    manifest: Mapping[str, Any],
    ledger: Mapping[str, Any],
    ledger_path: Path,
) -> None:
    """Bind the live final V3 ledger to the counts and hash it published."""

    live_files = ledger.get("case_files") or {}
    live_hashes = ledger.get("case_file_sha256") or {}
    if (
        not isinstance(live_files, dict)
        or not isinstance(live_hashes, dict)
        or set(live_files) != set(live_hashes)
        or _to_int(manifest.get("ledger_case_count"), -1) != len(live_files)
        or _to_int(manifest.get("ledger_case_file_sha256_count"), -1)
        != len(live_hashes)
        or not str(manifest.get("execution_ledger_sha256") or "")
        or _sha256(ledger_path) != manifest.get("execution_ledger_sha256")
    ):
        raise ValueError("Completed V3 ledger differs from its final manifest")


def _index_v2_rows(
    plan: ActionPlan,
) -> tuple[dict[tuple[str, int], Mapping[str, str]], str]:
    source_hashes = (
        plan.post_priority_plan_manifest.get("source_artifact_file_hashes") or {}
    )
    metrics_path = _required_file(
        plan.source_dir / "confirmation_metrics.csv", "V2 metrics"
    )
    _require_hash(
        metrics_path, source_hashes.get("confirmation_metrics.csv"), "V2 metrics"
    )
    rows = _read_csv(metrics_path)
    index: dict[tuple[str, int], Mapping[str, str]] = {}
    for row in rows:
        key = (str(row.get("scenario_id") or ""), _to_int(row.get("seed"), -1))
        if key in index:
            raise ValueError(f"Duplicate V2 source row: {key}")
        index[key] = row
    if len(rows) != 1110:
        raise ValueError("The frozen V2 confirmation matrix must contain 1110 rows")
    return index, _sha256(metrics_path)


def _canonical_incident_risk_row(row: Mapping[str, Any]) -> dict[str, Any]:
    """Return the engine risk contract with stable scalar types."""

    return {
        "event_id": str(row.get("event_id") or ""),
        "risk_type": str(row.get("risk_type") or ""),
        "supplier_id": str(row.get("supplier_id") or ""),
        "item_id": str(row.get("item_id") or ""),
        "dst_node_id": str(row.get("dst_node_id") or ""),
        "edge_id": str(row.get("edge_id") or ""),
        "start_day": _to_int(row.get("start_day"), -1),
        "end_day": _to_int(row.get("end_day"), -1),
        "multiplier": _to_float(row.get("multiplier"), math.nan),
        "notes": str(row.get("notes") or ""),
    }


def _validate_incident_risk_row(
    *,
    case: ActionCase,
    row: Mapping[str, Any],
    plan: ActionPlan,
) -> dict[str, Any]:
    canonical = _canonical_incident_risk_row(row)
    matching_edges = [
        str(edge.get("id") or "")
        for edge in plan.graph.get("edges") or []
        if str(edge.get("from") or "") == case.supplier_id
        and str(edge.get("to") or "") == case.dst_node_id
        and case.item_id in {str(item) for item in edge.get("items") or []}
    ]
    edge_id = str(canonical["edge_id"] or "")
    if (
        not canonical["event_id"]
        or canonical["risk_type"] != case.incident_risk_type
        or canonical["supplier_id"] != case.supplier_id
        or canonical["item_id"] != case.item_id
        or canonical["dst_node_id"] != case.dst_node_id
        or canonical["start_day"] != case.incident_start_day
        or canonical["end_day"] != case.incident_end_day
        or not math.isclose(
            float(canonical["multiplier"]),
            case.incident_value,
            rel_tol=0.0,
            abs_tol=1e-12,
        )
        or len(matching_edges) != 1
        or matching_edges[0] != case.edge_id
        or (edge_id and edge_id != case.edge_id)
    ):
        raise ValueError(f"Incident risk semantics differ from V5: {case.key}")
    return canonical


def _baseline_cutover_stock(
    *,
    plan: ActionPlan,
    v3_root: Path,
    baseline_evidence: Mapping[str, Any],
    seed: int,
    chain_cases: Sequence[ActionCase],
) -> dict[str, Mapping[str, Any]]:
    run_dir = _safe_descendant(
        v3_root, baseline_evidence.get("run_dir"), "V3 baseline run"
    )
    summary_path = _required_file(
        run_dir / "summaries" / "first_simulation_summary.json", "V3 baseline summary"
    )
    stocks_path = _required_file(
        run_dir / "data" / "production_input_stocks_daily.csv",
        "V3 baseline input stocks",
    )
    arrivals_path = _required_file(
        run_dir / "data" / "production_input_replenishment_arrivals_daily.csv",
        "V3 baseline input arrivals",
    )
    summary = _read_json(summary_path)
    warmup = (summary.get("policy") or {}).get("warmup_boundary_audit") or {}
    if (
        _to_int((summary.get("policy") or {}).get("seed"), -1) != seed
        or summary.get("input_sha256") != _sha256(plan.graph_path)
        or warmup.get("core_state_sha256") != baseline_evidence.get("j0_state_sha256")
    ):
        raise ValueError(f"V3 baseline raw state differs from evidence for seed {seed}")
    stocks = _read_csv(stocks_path)
    arrivals = _read_csv(arrivals_path)
    result: dict[str, Mapping[str, Any]] = {}
    for case in chain_cases:
        stock_rows = [
            row
            for row in stocks
            if _to_int(row.get("day"), -1) == 0
            and str(row.get("node_id") or "") == case.dst_node_id
            and str(row.get("item_id") or "") == case.item_id
        ]
        arrival_rows = [
            row
            for row in arrivals
            if _to_int(row.get("day"), -1) == 0
            and str(row.get("node_id") or "") == case.dst_node_id
            and str(row.get("item_id") or "") == case.item_id
        ]
        if len(stock_rows) != 1 or len(arrival_rows) != 1:
            raise ValueError(
                f"Unique J0 stock/arrival rows are required: {case.chain_id}/{seed}"
            )
        stock_before_production = _to_float(
            stock_rows[0].get("stock_before_production"), math.nan
        )
        j0_arrival = _to_float(arrival_rows[0].get("arrived_qty"), math.nan)
        cutover = stock_before_production - j0_arrival
        if (
            not math.isfinite(cutover)
            or not math.isfinite(j0_arrival)
            or j0_arrival < -ZERO_EPS
            or cutover < -ZERO_EPS
        ):
            raise ValueError(
                f"Invalid J0 cutover reconstruction: {case.chain_id}/{seed}"
            )
        result[case.chain_id] = {
            "seed": seed,
            "chain_id": case.chain_id,
            "node_id": case.dst_node_id,
            "item_id": case.item_id,
            "stock_before_production_day0_qty": stock_before_production,
            "arrival_day0_qty": j0_arrival,
            "cutover_stock_before_day0_flows_qty": max(0.0, cutover),
            "reconstruction": "day0_stock_before_production_minus_day0_arrival",
            "summary_sha256": _sha256(summary_path),
            "stocks_daily_sha256": _sha256(stocks_path),
            "arrivals_daily_sha256": _sha256(arrivals_path),
            "warmup_core_state_sha256": str(warmup.get("core_state_sha256") or ""),
            "warmup_component_sha256": dict(warmup.get("component_sha256") or {}),
        }
    return result


def _snapshot_row_signature(row: Mapping[str, Any]) -> str:
    canonical = {
        column: str(row.get(column) or "")
        for column in J0_SNAPSHOT_COLUMNS
        if column != "row_signature"
    }
    return _stable_sha256(canonical)


def _load_j0_snapshot(
    *,
    plan: ActionPlan,
    snapshot_dir: Path,
    target_seed_ids: Sequence[int],
    v3_manifest: Mapping[str, Any],
    v3_ledger: Mapping[str, Any],
) -> dict[tuple[int, str], Mapping[str, Any]]:
    root = snapshot_dir.resolve()
    manifest_path = _required_file(root / J0_SNAPSHOT_MANIFEST, "J0 snapshot manifest")
    rows_path = _required_file(root / J0_SNAPSHOT_ROWS, "J0 snapshot rows")
    inventory = {
        path.relative_to(root).as_posix()
        for path in root.rglob("*")
        if path.is_file()
    }
    if inventory != {J0_SNAPSHOT_MANIFEST, J0_SNAPSHOT_ROWS}:
        raise ValueError("J0 snapshot file inventory is not exact")
    manifest = _read_json(manifest_path)
    _validate_signed_payload(manifest, "snapshot_signature", label="J0 snapshot")
    captured_seed_ids = tuple(
        _to_int(value, -1) for value in manifest.get("captured_seed_ids") or []
    )
    target = tuple(int(seed) for seed in target_seed_ids)
    expected_status = (
        "complete_30_of_30" if len(captured_seed_ids) == 30 else "complete_15_of_30"
    )
    if (
        manifest.get("schema_version") != J0_SNAPSHOT_SCHEMA_VERSION
        or manifest.get("contract_revision") != CONTRACT_REVISION
        or manifest.get("status") != expected_status
        or manifest.get("V5_protocol_signature")
        != plan.manifest.get("protocol_signature")
        or manifest.get("V3_plan_signature")
        != plan.post_priority_plan_manifest.get("plan_signature")
        or manifest.get("V2_campaign_signature")
        != plan.manifest.get("source_campaign_signature")
        or manifest.get("source_runner_signature")
        != v3_manifest.get("runner_signature")
        or manifest.get("graph_sha256") != _sha256(plan.graph_path)
        or manifest.get("engine_sha256") != _sha256(plan.engine_path)
        or manifest.get("profile_sha256") != _sha256(plan.profile_path)
        or manifest.get("signed_final_seed_ids") != list(plan.seeds)
        or captured_seed_ids not in {plan.seeds[:15], plan.seeds}
        or captured_seed_ids[: len(target)] != target
        or _to_int(manifest.get("seed_count"), -1) != len(captured_seed_ids)
        or _to_int(manifest.get("lane_count_per_seed"), -1) != 4
        or manifest.get("rows_file") != J0_SNAPSHOT_ROWS
        or manifest.get("rows_sha256") != _sha256(rows_path)
    ):
        raise ValueError("J0 snapshot lineage or seed scope differs from V5")
    rows = _read_csv(rows_path)
    if (
        _to_int(manifest.get("row_count"), -1) != len(rows)
        or len(rows) != len(captured_seed_ids) * 4
        or any(set(row) != set(J0_SNAPSHOT_COLUMNS) for row in rows)
    ):
        raise ValueError("J0 snapshot row inventory is incomplete")
    stock_cases = {
        (case.seed, case.chain_id): case
        for case in plan.cases
        if case.lever_id == "prepositioned_free_stock_14d"
    }
    files = v3_ledger.get("case_files") or {}
    hashes = v3_ledger.get("case_file_sha256") or {}
    result: dict[tuple[int, str], Mapping[str, Any]] = {}
    for row in rows:
        seed = _to_int(row.get("seed"), -1)
        chain = str(row.get("chain_id") or "")
        key = (seed, chain)
        case = stock_cases.get(key)
        baseline_key = _v3_baseline_key(seed)
        evidence_relative = str(row.get("baseline_evidence_relative_path") or "")
        stock_before = _to_float(
            row.get("stock_before_production_day0_qty"), math.nan
        )
        arrival = _to_float(row.get("arrival_day0_qty"), math.nan)
        cutover = _to_float(
            row.get("cutover_stock_before_day0_flows_qty"), math.nan
        )
        try:
            warmup_components = json.loads(
                str(row.get("warmup_component_sha256_json") or "")
            )
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid J0 snapshot component hashes: {key}") from exc
        if (
            key in result
            or case is None
            or seed not in captured_seed_ids
            or _to_int(row.get("seed_prefix_index"), -1)
            != plan.seeds.index(seed) + 1
            or row.get("schema_version") != J0_SNAPSHOT_SCHEMA_VERSION
            or row.get("row_signature") != _snapshot_row_signature(row)
            or baseline_key != row.get("baseline_case_key")
            or files.get(baseline_key) != evidence_relative
            or hashes.get(baseline_key) != row.get("baseline_evidence_sha256")
            or row.get("source_runner_signature")
            != v3_manifest.get("runner_signature")
            or row.get("supplier_id") != case.supplier_id
            or row.get("node_id") != case.dst_node_id
            or row.get("item_id") != case.item_id
            or row.get("uom") != case.buffer_uom
            or not all(math.isfinite(value) for value in (stock_before, arrival, cutover))
            or arrival < -ZERO_EPS
            or cutover <= ZERO_EPS
            or not math.isclose(
                stock_before - arrival,
                cutover,
                rel_tol=0.0,
                abs_tol=1e-6,
            )
            or row.get("reconstruction")
            != "day0_stock_before_production_minus_day0_arrival"
            or not all(
                str(row.get(field) or "")
                for field in (
                    "summary_sha256",
                    "stocks_daily_sha256",
                    "arrivals_daily_sha256",
                    "lot_events_sha256",
                    "lot_genealogy_sha256",
                    "warmup_core_state_sha256",
                )
            )
            or str(row.get("source_lot_trace_enabled") or "")
            not in {"True", "False"}
            or not isinstance(warmup_components, dict)
            or not str(warmup_components.get("stock") or "")
            or not str(warmup_components.get("lot_ledger") or "")
        ):
            raise ValueError(f"Invalid or unpaired J0 snapshot row: {key}")
        result[key] = {
            "seed": seed,
            "chain_id": chain,
            "node_id": case.dst_node_id,
            "item_id": case.item_id,
            "uom": case.buffer_uom,
            "stock_before_production_day0_qty": stock_before,
            "arrival_day0_qty": arrival,
            "cutover_stock_before_day0_flows_qty": cutover,
            "reconstruction": str(row["reconstruction"]),
            "summary_sha256": str(row["summary_sha256"]),
            "stocks_daily_sha256": str(row["stocks_daily_sha256"]),
            "arrivals_daily_sha256": str(row["arrivals_daily_sha256"]),
            "lot_events_sha256": str(row["lot_events_sha256"]),
            "lot_genealogy_sha256": str(row["lot_genealogy_sha256"]),
            "source_lot_trace_enabled": _as_bool(
                row.get("source_lot_trace_enabled")
            ),
            "warmup_core_state_sha256": str(row["warmup_core_state_sha256"]),
            "warmup_component_sha256": warmup_components,
            "baseline_case_key": baseline_key,
            "baseline_evidence_sha256": str(row["baseline_evidence_sha256"]),
            "snapshot_row_signature": str(row["row_signature"]),
            "snapshot_contract": J0_SNAPSHOT_SCHEMA_VERSION,
        }
    expected = {
        (seed, chain)
        for seed in target
        for chain in {case.chain_id for case in stock_cases.values()}
    }
    if not expected <= set(result):
        raise SourcesNotReadyError("The signed J0 snapshot lacks the requested seed prefix")
    return {key: result[key] for key in expected}


def validate_paired_sources(
    plan: ActionPlan,
    *,
    post_priority_results_dir: Path,
    target_seed_ids: Sequence[int],
    j0_snapshot_dir: Path = DEFAULT_J0_SNAPSHOT_DIR,
) -> SourceBundle:
    target = tuple(int(seed) for seed in target_seed_ids)
    if (
        not target
        or target != plan.seeds[: len(target)]
        or len(target) not in {1, 15, 30}
    ):
        raise ValueError("Source target must be the exact 1, 15 or 30 seed prefix")
    v2_manifest_path = _required_file(
        plan.source_dir / "campaign_manifest.json", "V2 manifest"
    )
    v2_manifest = _read_json(v2_manifest_path)
    if (
        v2_manifest.get("status") != "complete"
        or v2_manifest.get("campaign_signature")
        != plan.manifest.get("source_campaign_signature")
        or tuple(
            _to_int(value, -1) for value in v2_manifest.get("confirmation_seeds") or []
        )
        != plan.seeds
    ):
        raise ValueError("V2 source campaign is not the exact completed 30-seed source")
    v2_rows, v2_metrics_hash = _index_v2_rows(plan)
    required_cases = [case for case in plan.cases if case.seed in target]
    incident_risk_rows: dict[tuple[str, int], tuple[Mapping[str, Any], ...]] = {}
    incident_risk_hashes: dict[tuple[str, int], str] = {}
    v2_risk_cache: dict[str, tuple[dict[str, Any], str]] = {}
    for case in required_cases:
        normal = v2_rows.get(("baseline_nominal", case.seed))
        if normal is None or not _as_bool(normal.get("valid")):
            raise ValueError(f"Valid V2 baseline absent: seed {case.seed}")
        if normal.get("input_sha256") != _sha256(plan.graph_path):
            raise ValueError(f"V2 baseline graph mismatch: seed {case.seed}")
        if case.failure_mode != "quality_hold":
            incident = v2_rows.get((case.incident_source_case_id, case.seed))
            if incident is None or not _as_bool(incident.get("valid")):
                raise ValueError(f"Valid V2 incident absent: {case.key}")
            if (
                incident.get("input_sha256") != normal.get("input_sha256")
                or incident.get("j0_state_sha256") != normal.get("j0_state_sha256")
                or _to_int(incident.get("seed"), -1) != case.seed
                or str(incident.get("mechanism") or "") != case.failure_mode
                or str(incident.get("level_code") or "") != "severe"
                or str(incident.get("chain_id") or "") != case.chain_id
                or str(incident.get("target_product_id") or "")
                != case.target_product_id
                or not math.isclose(
                    _to_float(incident.get("mechanism_value"), math.nan),
                    case.incident_value,
                    rel_tol=0.0,
                    abs_tol=1e-12,
                )
                or str(incident.get("mechanism_unit") or "") != case.incident_unit
                or _to_int(incident.get("stress_start_day"), -1)
                != case.incident_start_day
                or _to_int(incident.get("stress_end_day"), -1) != case.incident_end_day
            ):
                raise ValueError(f"V2 incident is not paired exactly: {case.key}")
            if case.incident_source_case_id not in v2_risk_cache:
                source_path = _safe_descendant(
                    plan.source_dir,
                    plan.source_dir
                    / "inputs"
                    / "risk_events"
                    / f"{case.incident_source_case_id}.csv",
                    "V2 source risk input",
                )
                source_rows = _read_csv(
                    _required_file(source_path, "V2 source risk input")
                )
                if len(source_rows) != 1:
                    raise ValueError(
                        f"V2 incident must contain exactly one event: {case.key}"
                    )
                canonical = _validate_incident_risk_row(
                    case=case,
                    row=source_rows[0],
                    plan=plan,
                )
                v2_risk_cache[case.incident_source_case_id] = (
                    canonical,
                    _stable_sha256([canonical]),
                )
            source_risk, semantic_hash = v2_risk_cache[case.incident_source_case_id]
            incident_risk_rows[(case.incident_source_case_id, case.seed)] = (
                source_risk,
            )
            incident_risk_hashes[(case.incident_source_case_id, case.seed)] = (
                semantic_hash
            )

    v3_root = post_priority_results_dir.resolve()
    manifest_path = _required_file(
        v3_root / post_runner.RUNNER_MANIFEST, "V3 execution manifest"
    )
    v3_manifest = _read_json(manifest_path)
    required_status = "complete" if len(target) == 30 else None
    status = str(v3_manifest.get("status") or "")
    if (required_status and status != required_status) or (
        not required_status and status not in {"paused_preliminary", "complete"}
    ):
        raise SourcesNotReadyError(
            f"Paired V3 source is not ready for {len(target)} seeds (status={status!r})"
        )
    post_manifest_path = (
        plan.post_priority_plan_dir / "post_priority_extensions_plan_manifest.json"
    )
    if (
        v3_manifest.get("plan_signature")
        != plan.post_priority_plan_manifest.get("plan_signature")
        or v3_manifest.get("plan_manifest_sha256") != _sha256(post_manifest_path)
        or v3_manifest.get("source_campaign_manifest_sha256")
        != _sha256(v2_manifest_path)
        or tuple(
            _to_int(value, -1)
            for value in v3_manifest.get("signed_full_seed_ids") or []
        )
        != plan.seeds
        or _as_bool(v3_manifest.get("custom_executor_used"))
    ):
        raise ValueError("V3 execution lineage differs from the V5 protocol")
    checkpoint = post_runner._validate_preliminary_checkpoint(  # noqa: SLF001
        output_dir=v3_root,
        runner_signature=str(v3_manifest.get("runner_signature") or ""),
        plan_manifest_sha256=_sha256(post_manifest_path),
        require_live_ledger_match=status == "paused_preliminary",
        expected_signed_seed_ids=plan.seeds,
    )
    if checkpoint is None:
        raise SourcesNotReadyError("The signed V3 15-seed checkpoint is absent")
    ledger_path = _required_file(v3_root / post_runner.LEDGER_FILE, "V3 ledger")
    ledger = _read_json(ledger_path)
    if ledger.get("runner_signature") != v3_manifest.get("runner_signature"):
        raise ValueError("V3 ledger signature differs from its manifest")
    if status == "complete":
        _validate_completed_v3_ledger(
            manifest=v3_manifest,
            ledger=ledger,
            ledger_path=ledger_path,
        )

    quality: dict[tuple[str, int], Mapping[str, Any]] = {}
    baselines: dict[int, Mapping[str, Any]] = {}
    evidence_hashes: dict[str, str] = {}
    baseline_j0 = _load_j0_snapshot(
        plan=plan,
        snapshot_dir=j0_snapshot_dir,
        target_seed_ids=target,
        v3_manifest=v3_manifest,
        v3_ledger=ledger,
    )
    cases_by_seed: dict[int, list[ActionCase]] = {}
    for case in required_cases:
        cases_by_seed.setdefault(case.seed, []).append(case)
    for seed, seed_cases in cases_by_seed.items():
        baseline_key = _v3_baseline_key(seed)
        baseline, baseline_hash = _load_v3_evidence(v3_root, ledger, baseline_key)
        normal = v2_rows[("baseline_nominal", seed)]
        if (
            baseline.get("seed") != seed
            or baseline.get("input_sha256") != normal.get("input_sha256")
            or baseline.get("j0_state_sha256") != normal.get("j0_state_sha256")
        ):
            raise ValueError(f"V2/V3 baseline pairing differs for seed {seed}")
        if any(
            row.get("warmup_core_state_sha256") != baseline.get("j0_state_sha256")
            for (row_seed, _chain), row in baseline_j0.items()
            if row_seed == seed
        ):
            raise ValueError(f"J0 snapshot differs from V3 baseline evidence: {seed}")
        baselines[seed] = baseline
        evidence_hashes[baseline_key] = baseline_hash
        for case in seed_cases:
            if case.failure_mode != "quality_hold":
                continue
            key = _v3_case_key(case.incident_source_case_id, seed)
            evidence, evidence_hash = _load_v3_evidence(v3_root, ledger, key)
            loaded = list(evidence.get("loaded_event_rows") or [])
            if (
                evidence.get("seed") != seed
                or evidence.get("input_sha256") != normal.get("input_sha256")
                or evidence.get("j0_state_sha256") != normal.get("j0_state_sha256")
                or len(loaded) != 1
                or str(loaded[0].get("risk_type") or "") != "quality_delay"
                or not math.isclose(
                    _to_float(loaded[0].get("multiplier"), math.nan),
                    90.0,
                    abs_tol=1e-12,
                )
                or str(loaded[0].get("supplier_id") or "") != case.supplier_id
                or str(loaded[0].get("item_id") or "") != case.item_id
                or str(loaded[0].get("dst_node_id") or "") != case.dst_node_id
                or not evidence.get("applied_event_ids")
            ):
                raise ValueError(
                    f"V3 quality source is not the exact 90-day case: {case.key}"
                )
            quality[(case.incident_source_case_id, seed)] = evidence
            evidence_hashes[key] = evidence_hash
            canonical_risk = _validate_incident_risk_row(
                case=case,
                row=loaded[0],
                plan=plan,
            )
            incident_risk_rows[(case.incident_source_case_id, seed)] = (canonical_risk,)
            incident_risk_hashes[(case.incident_source_case_id, seed)] = _stable_sha256(
                [canonical_risk]
            )

    expected_risk_keys = {
        (case.incident_source_case_id, case.seed) for case in required_cases
    }
    if (
        set(incident_risk_rows) != expected_risk_keys
        or set(incident_risk_hashes) != expected_risk_keys
    ):
        raise ValueError("Exact incident risk inventory is incomplete")

    source_identity = {
        "V5_protocol_signature": plan.manifest.get("protocol_signature"),
        "V2_campaign_signature": v2_manifest.get("campaign_signature"),
        "V2_manifest_sha256": _sha256(v2_manifest_path),
        "V2_confirmation_metrics_sha256": v2_metrics_hash,
        "V3_plan_signature": plan.post_priority_plan_manifest.get("plan_signature"),
        "V3_runner_signature": v3_manifest.get("runner_signature"),
        "V3_checkpoint_signature": checkpoint.get("checkpoint_signature"),
        "graph_sha256": _sha256(plan.graph_path),
        "engine_sha256": _sha256(plan.engine_path),
        "profile_sha256": _sha256(plan.profile_path),
        "signed_seed_ids": list(plan.seeds),
        "J0_snapshot_contract": J0_SNAPSHOT_SCHEMA_VERSION,
    }
    return SourceBundle(
        source_dir=plan.source_dir,
        post_priority_results_dir=v3_root,
        target_seed_ids=target,
        v2_rows=v2_rows,
        v3_quality_evidence=quality,
        v3_baseline_evidence=baselines,
        v3_evidence_hashes=evidence_hashes,
        incident_risk_rows=incident_risk_rows,
        incident_risk_semantic_sha256=incident_risk_hashes,
        baseline_j0=baseline_j0,
        source_identity=source_identity,
        source_identity_signature=_stable_sha256(source_identity),
    )


def _risk_rows(case: ActionCase, sources: SourceBundle) -> list[dict[str, Any]]:
    """Reuse the exact signed-source incident semantics for the action arm."""

    rows = sources.incident_risk_rows.get((case.incident_source_case_id, case.seed))
    if not rows or len(rows) != 1:
        raise ValueError(f"Exact source incident is unavailable: {case.key}")
    canonical = _canonical_incident_risk_row(rows[0])
    if _stable_sha256([canonical]) != sources.incident_risk_semantic_sha256.get(
        (case.incident_source_case_id, case.seed)
    ):
        raise ValueError(f"Exact source incident changed: {case.key}")
    return [canonical]


def _control_rows(case: ActionCase) -> list[dict[str, Any]]:
    if case.lever_id not in {
        "future_lane_transport_reduction",
        "quality_scenario_full_lane_calendar_open_loop_transport_reduction_7d",
    }:
        return []
    rows: list[dict[str, Any]] = []
    for day in range(case.incident_start_day, case.incident_end_day + 1):
        row = {name: "" for name in CONTROL_SCHEDULE_COLUMNS}
        row.update(
            {
                "day": day,
                "policy": f"action_v5_{case.lever_id}",
                "supplier_id": case.supplier_id,
                "item_id": case.item_id,
                "dst_node_id": case.dst_node_id,
                "lead_time_adjustment_days": case.lead_time_adjustment_days,
            }
        )
        rows.append(row)
    return rows


def _csv_rows_equal(path: Path, rows: Sequence[Mapping[str, Any]]) -> bool:
    actual = _read_csv(path)
    expected = [
        {
            str(key): str(value) if value is not None else ""
            for key, value in row.items()
        }
        for row in rows
    ]
    return actual == expected


def _ensure_csv(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    if path.is_file():
        if not _csv_rows_equal(path, rows):
            raise ValueError(f"Prepared input changed: {path}")
        return
    if path.exists():
        raise ValueError(f"Prepared input path is not a file: {path}")
    _write_csv(path, rows)


def prepare_case_inputs(
    case: ActionCase,
    plan: ActionPlan,
    sources: SourceBundle,
    output_dir: Path,
) -> InputBundle:
    root = output_dir / "prepared_inputs" / _case_digest(case.key)
    root.mkdir(parents=True, exist_ok=True)
    risk_path = root / "supplier_risk_events.csv"
    risks = _risk_rows(case, sources)
    _ensure_csv(risk_path, risks)
    schedule_path: Path | None = None
    schedule_hash = ""
    control_rows = _control_rows(case)
    if control_rows:
        schedule_path = root / "control_schedule.csv"
        _ensure_csv(schedule_path, control_rows)
        loaded = load_control_schedule(
            schedule_path, catalog=_graph_catalog(plan.graph)
        )
        if len(loaded.rows) != len(control_rows):
            raise ValueError(f"Control schedule row count changed: {case.key}")
        schedule_hash = _sha256(schedule_path)
    stock_path: Path | None = None
    stock_hash = ""
    j0_before: float | None = None
    j0_scale: float | None = None
    if case.lever_id == "prepositioned_free_stock_14d":
        j0 = sources.baseline_j0[(case.seed, case.chain_id)]
        j0_before = _to_float(j0.get("cutover_stock_before_day0_flows_qty"), math.nan)
        if not math.isfinite(j0_before) or j0_before <= ZERO_EPS:
            raise ValueError(
                f"J0 stock is zero; multiplicative stock actuator is blocked: {case.key}"
            )
        assert case.buffer_rounded_qty is not None
        j0_scale = (j0_before + case.buffer_rounded_qty) / j0_before
        stock_path = root / "measurement_start_stock_scale.csv"
        _ensure_csv(
            stock_path,
            [
                {
                    "node_id": case.dst_node_id,
                    "item_id": case.item_id,
                    "scale": format(j0_scale, ".17g"),
                }
            ],
        )
        stock_hash = _sha256(stock_path)
    deterministic = {
        "schema_version": f"{SCHEMA_VERSION}.prepared_input",
        "contract_revision": CONTRACT_REVISION,
        "case_key": case.key,
        "case": asdict(case),
        "source_fingerprint": sources.fingerprint(case),
        "source_incident_risk_semantic_sha256": (
            sources.incident_risk_semantic_sha256[
                (case.incident_source_case_id, case.seed)
            ]
        ),
        "risk_csv": risk_path.name,
        "risk_csv_sha256": _sha256(risk_path),
        "control_schedule_csv": schedule_path.name if schedule_path else "",
        "control_schedule_csv_sha256": schedule_hash,
        "measurement_start_stock_scale_csv": stock_path.name if stock_path else "",
        "measurement_start_stock_scale_csv_sha256": stock_hash,
        "j0_stock_before_qty": j0_before,
        "j0_stock_scale": j0_scale,
        "buffer_raw_qty": case.buffer_raw_qty,
        "buffer_rounded_qty": case.buffer_rounded_qty,
        "procurement_standard_lot_qty": case.procurement_standard_lot_qty,
        "buffer_procurement_lot_count": case.buffer_procurement_lot_count,
        "buffer_procurement_lot_count_semantics": (
            "procurement_rounding_count_not_engine_lot_segmentation"
            if case.buffer_procurement_lot_count is not None
            else ""
        ),
        "engine_j0_stock_adjustment_semantics": (
            "aggregate_stock_scale_with_lot_ledger_reconciliation"
            if case.lever_id == "prepositioned_free_stock_14d"
            else ""
        ),
        "stock_present_at_measured_j0": (
            case.lever_id == "prepositioned_free_stock_14d"
        ),
        "stock_acquisition_simulated": False,
        "stock_procurement_lead_time_simulated": False,
        "stock_procurement_cost_simulated": False,
        "alternative_source_created": False,
        "quality_hold_days_preserved": 90
        if case.failure_mode == "quality_hold"
        else None,
    }
    manifest_path = root / "input_manifest.json"
    expected = _signed_payload(deterministic, "input_signature")
    if manifest_path.is_file():
        actual = _read_json(manifest_path)
        _validate_signed_payload(actual, "input_signature", label="prepared input")
        if actual != expected:
            raise ValueError(f"Prepared input manifest changed: {case.key}")
    else:
        _write_json(manifest_path, expected)
    return InputBundle(
        root=root,
        risk_csv=risk_path,
        risk_sha256=_sha256(risk_path),
        control_schedule_csv=schedule_path,
        control_schedule_sha256=schedule_hash,
        stock_scale_csv=stock_path,
        stock_scale_sha256=stock_hash,
        input_manifest=manifest_path,
        input_manifest_sha256=_sha256(manifest_path),
        j0_stock_before_qty=j0_before,
        j0_stock_scale=j0_scale,
    )


def _run_config(plan: ActionPlan, output_dir: Path) -> network.campaign_core.RunConfig:
    return network.campaign_core.RunConfig(
        repo_root=REPO_ROOT,
        output_dir=output_dir,
        engine=plan.engine_path,
        graph=plan.graph_path,
        supplier_floors=plan.supplier_floors_path,
        factory_capacities=None,
        profile_args=plan.profile_args,
        scenario_id="scn:BASE",
        days=MEASURED_DAYS,
        retention="summary",
        physical_capacity_by_lane=plan.physical_capacity_by_lane,
    )


def build_engine_command(
    case: ActionCase,
    plan: ActionPlan,
    output_dir: Path,
    inputs: InputBundle,
) -> list[str]:
    if case.lever_id == BLOCKED_LEVER:
        raise ValueError("The alternative source has no executable engine case")
    _validate_execution_files_unchanged(plan)
    case_dir = output_dir / "cases" / _case_digest(case.key)
    command = network.build_network_engine_command(
        _run_config(plan, output_dir),
        case_dir=case_dir,
        seed=case.seed,
        risk_csv=inputs.risk_csv,
        lot_trace_required=True,
    )
    if inputs.control_schedule_csv is not None:
        command.extend(["--control-schedule-csv", str(inputs.control_schedule_csv)])
    if inputs.stock_scale_csv is not None:
        command.extend(
            ["--measurement-start-stock-scale-csv", str(inputs.stock_scale_csv)]
        )
    if "--input" not in command or command[command.index("--input") + 1] != str(
        plan.graph_path
    ):
        raise ValueError("Engine command does not use the locked graph")
    return command


def _action_metrics(case_dir: Path, case: ActionCase) -> dict[str, Any]:
    service_rows = _read_csv(case_dir / "data" / "production_demand_service_daily.csv")
    target_service_rows = [
        row
        for row in service_rows
        if str(row.get("node_id") or "") == CLIENT_NODE_ID
        and str(row.get("item_id") or "") == f"item:{case.target_product_id}"
    ]
    if (
        len(target_service_rows) != MEASURED_DAYS
        or {_to_int(row.get("day"), -1) for row in target_service_rows}
        != set(range(MEASURED_DAYS))
        or any(
            not math.isfinite(_to_float(row.get(field), math.nan))
            for row in target_service_rows
            for field in (
                "demand_qty",
                "required_with_backlog_qty",
                "served_qty",
                "backlog_end_qty",
            )
        )
    ):
        raise ValueError(f"Action service series is not exact and complete: {case.key}")
    service = network.campaign_core.compute_service_metrics(
        service_rows,
        client_node_id=CLIENT_NODE_ID,
        products=PRODUCTS,
        days=MEASURED_DAYS,
    )[case.target_product_id]
    if (
        service.get("horizon_complete") is not True
        or _to_int(service.get("horizon_day_count"), -1) != MEASURED_DAYS
    ):
        raise ValueError(f"Action service horizon is incomplete: {case.key}")
    stock_rows = [
        row
        for row in _read_csv(case_dir / "data" / "production_input_stocks_daily.csv")
        if str(row.get("node_id") or "") == case.dst_node_id
        and str(row.get("item_id") or "") == case.item_id
    ]
    if (
        len(stock_rows) != MEASURED_DAYS
        or {_to_int(row.get("day"), -1) for row in stock_rows}
        != set(range(MEASURED_DAYS))
    ):
        raise ValueError(f"Action stock series is not complete: {case.key}")
    raw_stock_values = [
        _to_float(row.get("stock_end_of_day"), math.nan) for row in stock_rows
    ]
    if any(not math.isfinite(value) for value in raw_stock_values):
        raise ValueError(f"Action stock series is non-finite: {case.key}")
    stock_values = [max(0.0, value) for value in raw_stock_values]
    production_rows = [
        row
        for row in _read_csv(case_dir / "data" / "production_output_products_daily.csv")
        if str(row.get("node_id") or "") == case.dst_node_id
        and str(row.get("item_id") or "") == f"item:{case.target_product_id}"
    ]
    if (
        len(production_rows) != MEASURED_DAYS
        or {_to_int(row.get("day"), -1) for row in production_rows}
        != set(range(MEASURED_DAYS))
    ):
        raise ValueError(f"Action production series is not complete: {case.key}")
    released_values = [
        _to_float(row.get("released_qty"), math.nan) for row in production_rows
    ]
    if any(not math.isfinite(value) for value in released_values):
        raise ValueError(f"Action production series is non-finite: {case.key}")
    return {
        "demand_qty": _to_float(service.get("demand_qty"), math.nan),
        "fill_rate": _to_float(service.get("fill_rate"), math.nan),
        "on_due_ratio": _to_float(service.get("on_due_volume_proxy"), math.nan),
        "backlog_qty_days": _to_float(service.get("backlog_qty_days"), math.nan),
        "backlog_end_qty": _to_float(service.get("backlog_end_qty"), math.nan),
        "backlog_max_qty": _to_float(service.get("backlog_max_qty"), math.nan),
        "component_min_stock_qty": min(stock_values),
        "component_reached_zero": min(stock_values) <= ZERO_EPS,
        "component_zero_stock_day_count": sum(
            value <= ZERO_EPS for value in stock_values
        ),
        "component_stock_metric_status": "complete_daily_action_series",
        "target_released_qty": sum(max(0.0, value) for value in released_values),
        "product_uom": "UN",
        "component_uom": case.buffer_uom or "",
        "industrial_action_cost": "",
        "industrial_action_cost_status": "not_quantified_missing_industrial_inputs",
    }


def _loaded_risk_errors(
    case: ActionCase,
    summary: Mapping[str, Any],
    inputs: InputBundle,
    sources: SourceBundle,
    case_dir: Path,
) -> tuple[list[str], list[dict[str, str]]]:
    errors: list[str] = []
    configured, loaded, risk_hash, warnings = post_runner._loaded_risk_contract(  # noqa: SLF001
        summary=summary,
        risk_csv=inputs.risk_csv,
    )
    expected = _risk_rows(case, sources)[0]
    if (
        risk_hash != inputs.risk_sha256
        or warnings
        or len(configured) != 1
        or len(loaded) != 1
    ):
        errors.append("risk input was not loaded exactly once")
    else:
        row = loaded[0]
        for field in (
            "event_id",
            "risk_type",
            "supplier_id",
            "item_id",
            "dst_node_id",
            "edge_id",
            "start_day",
            "end_day",
        ):
            if str(row.get(field)) != str(expected.get(field)):
                errors.append(f"loaded risk differs on {field}")
        if not math.isclose(
            _to_float(row.get("multiplier"), math.nan),
            case.incident_value,
            abs_tol=1e-12,
        ):
            errors.append("loaded risk multiplier differs")
    applied_path = case_dir / "data" / "supplier_risk_events_applied_daily.csv"
    applied = _read_csv(applied_path)
    event_id = str(expected["event_id"])
    exercised = [
        row
        for row in applied
        if event_id
        in {
            token.strip()
            for token in str(row.get("event_ids") or "").replace("|", ",").split(",")
            if token.strip()
        }
    ]
    if not exercised:
        errors.append("risk event was configured but never exercised")
    if case.failure_mode == "quality_hold" and any(
        not math.isclose(
            _to_float(row.get("quality_delay_days"), math.nan), 90.0, abs_tol=1e-12
        )
        for row in exercised
    ):
        errors.append("quality hold is not preserved at 90 days")
    return errors, exercised


def _control_application_errors(
    case: ActionCase,
    summary: Mapping[str, Any],
    inputs: InputBundle,
    case_dir: Path,
) -> tuple[list[str], list[dict[str, str]]]:
    if inputs.control_schedule_csv is None:
        return [], []
    errors: list[str] = []
    policy = (summary.get("policy") or {}).get("control_schedule") or {}
    expected_rows = case.incident_end_day - case.incident_start_day + 1
    if (
        policy.get("enabled") is not True
        or str(policy.get("sha256") or "") != inputs.control_schedule_sha256
        or _to_int(policy.get("schedule_rows"), -1) != expected_rows
        or _to_int(policy.get("resolved_actions"), 0) <= 0
        or bool(policy.get("warnings") or [])
    ):
        errors.append("control schedule was not loaded/resolved as declared")
    rows = _read_csv(case_dir / "data" / "canonical_action_ledger.csv")
    physically_applied = [
        row for row in rows if str(row.get("status") or "") == "applied"
    ]

    def is_declared_lane_reduction(row: Mapping[str, Any]) -> bool:
        return (
            str(row.get("action") or "") == "lead_time_adjustment_days"
            and str(row.get("source_supplier_id") or "") == case.supplier_id
            and str(row.get("source_item_id") or "") == case.item_id
            and str(row.get("source_dst_node_id") or "") == case.dst_node_id
            and _to_int(row.get("effective"), 0)
            == -protocol.TRANSPORT_REDUCTION_DAYS
            and _to_float(row.get("executed_control_volume_qty"), 0.0) > 0.0
        )

    applied = [row for row in physically_applied if is_declared_lane_reduction(row)]
    if not applied:
        errors.append("-7 day lane control was scheduled but not physically applied")
    if any(not is_declared_lane_reduction(row) for row in physically_applied):
        errors.append("an undeclared control lever, lane or value was applied")
    return errors, applied


def _j0_component_errors(
    *,
    case: ActionCase,
    sources: SourceBundle,
    actual_components: Mapping[str, Any],
    ignored_components: set[str],
) -> list[str]:
    reference = sources.baseline_j0[(case.seed, case.chain_id)]
    source_components = dict(reference.get("warmup_component_sha256") or {})
    actual = dict(actual_components)
    return [
        f"paired J0 state changed: {key}"
        for key in sorted(set(source_components) | set(actual))
        if key not in ignored_components
        and source_components.get(key) != actual.get(key)
    ]


def _stock_application_errors(
    case: ActionCase,
    summary: Mapping[str, Any],
    inputs: InputBundle,
    sources: SourceBundle,
    case_dir: Path,
) -> tuple[list[str], list[dict[str, str]], list[dict[str, str]]]:
    if inputs.stock_scale_csv is None:
        return [], [], []
    errors: list[str] = []
    audit = (summary.get("policy") or {}).get("measurement_start_stock_scale") or {}
    rows = _read_csv(case_dir / "data" / "measurement_start_stock_adjustments.csv")
    if (
        audit.get("enabled") is not True
        or str(audit.get("source_csv_sha256") or "") != inputs.stock_scale_sha256
        or _to_int(audit.get("adjustment_rows"), -1) != 1
        or len(rows) != 1
    ):
        errors.append("J0 stock scale was not applied exactly once")
        return errors, rows, []
    row = rows[0]
    assert case.buffer_rounded_qty is not None
    if (
        str(row.get("node_id") or "") != case.dst_node_id
        or str(row.get("item_id") or "") != case.item_id
        or not math.isclose(
            _to_float(row.get("stock_before_qty"), math.nan),
            float(inputs.j0_stock_before_qty or math.nan),
            abs_tol=1e-6,
        )
        or not math.isclose(
            _to_float(row.get("stock_added_qty"), math.nan),
            case.buffer_rounded_qty,
            abs_tol=1e-5,
        )
        or not math.isclose(
            _to_float(row.get("scale"), math.nan),
            float(inputs.j0_stock_scale or math.nan),
            rel_tol=1e-9,
            abs_tol=1e-9,
        )
        or not _as_bool(row.get("lot_balance_matches_stock_after"))
    ):
        errors.append("J0 stock adjustment differs from the lotified V5 buffer")
    lot_events = _read_csv(case_dir / "data" / "production_lot_events.csv")
    stock_lot_rows = [
        event
        for event in lot_events
        if str(event.get("event_type") or "") == "measurement_start_stock_increase"
        and str(event.get("node_id") or "") == case.dst_node_id
        and str(event.get("item_id") or "") == case.item_id
        and str(event.get("source_id") or "") == "measurement_start_stock_scale_csv"
    ]
    if len(stock_lot_rows) != 1 or not math.isclose(
        _to_float(stock_lot_rows[0].get("qty"), math.nan),
        case.buffer_rounded_qty,
        abs_tol=1e-5,
    ):
        errors.append("J0 aggregate stock addition is absent from the lot trace")
    warmup = (summary.get("policy") or {}).get("warmup_boundary_audit") or {}
    actual_components = dict(warmup.get("component_sha256") or {})
    errors.extend(
        _j0_component_errors(
            case=case,
            sources=sources,
            actual_components=actual_components,
            ignored_components={"stock", "lot_ledger"},
        )
    )
    return errors, rows, stock_lot_rows


def execute_engine_case(
    case: ActionCase,
    plan: ActionPlan,
    sources: SourceBundle,
    output_dir: Path,
    inputs: InputBundle,
) -> Mapping[str, Any]:
    case_dir = output_dir / "cases" / _case_digest(case.key)
    summary_path = case_dir / "summaries" / "first_simulation_summary.json"
    service_path = case_dir / "data" / "production_demand_service_daily.csv"
    if summary_path.is_file() != service_path.is_file():
        raise RuntimeError(f"Partial action run requires review: {case.key}")
    status = "reextracted" if summary_path.is_file() else "executed"
    command = build_engine_command(case, plan, output_dir, inputs)
    if status == "executed":
        if case_dir.exists() and any(case_dir.iterdir()):
            raise RuntimeError(f"Unregistered non-empty action case: {case.key}")
        case_dir.mkdir(parents=True, exist_ok=True)
        log_path = case_dir / "action_engine.log"
        with log_path.open("a", encoding="utf-8") as stream:
            stream.write(f"\n[{_utc_now()}] COMMAND {json.dumps(command)}\n")
            completed = subprocess.run(
                command,
                cwd=REPO_ROOT,
                stdout=stream,
                stderr=subprocess.STDOUT,
                text=True,
                check=False,
            )
        if completed.returncode != 0:
            raise RuntimeError(f"Engine failed for {case.key}; see {log_path}")
    _validate_execution_files_unchanged(plan)
    summary = _read_json(summary_path)
    policy = summary.get("policy") or {}
    warmup = policy.get("warmup_boundary_audit") or {}
    errors: list[str] = []
    if (
        summary.get("input_sha256") != _sha256(plan.graph_path)
        or _to_int(summary.get("sim_days"), -1) != MEASURED_DAYS
        or _to_int(policy.get("seed"), -1) != case.seed
        or not _as_bool(policy.get("common_random_numbers"))
        or not _as_bool(policy.get("lot_trace_enabled"))
    ):
        errors.append("engine configuration differs from the paired V5 contract")
    control_policy = policy.get("control_schedule") or {}
    stock_policy = policy.get("measurement_start_stock_scale") or {}
    if inputs.control_schedule_csv is None and _as_bool(control_policy.get("enabled")):
        errors.append("an undeclared control schedule was enabled")
    if inputs.stock_scale_csv is None and _as_bool(stock_policy.get("enabled")):
        errors.append("an undeclared measurement-start stock scale was enabled")
    risk_errors, risk_applied = _loaded_risk_errors(
        case, summary, inputs, sources, case_dir
    )
    errors.extend(risk_errors)
    control_errors, control_applied = _control_application_errors(
        case, summary, inputs, case_dir
    )
    errors.extend(control_errors)
    stock_errors, stock_applied, stock_lot_events = _stock_application_errors(
        case, summary, inputs, sources, case_dir
    )
    errors.extend(stock_errors)
    if inputs.stock_scale_csv is None:
        # Lot tracing is observational instrumentation and was deliberately
        # enabled for every action run, while most compact V2/V3 source arms ran
        # without it.  All physical/dynamic components must still pair.
        errors.extend(
            _j0_component_errors(
                case=case,
                sources=sources,
                actual_components=dict(warmup.get("component_sha256") or {}),
                ignored_components={"lot_ledger"},
            )
        )
    metrics = _action_metrics(case_dir, case)
    if any(
        not math.isfinite(_to_float(metrics.get(name), math.nan))
        for name in (
            "demand_qty",
            "fill_rate",
            "on_due_ratio",
            "backlog_qty_days",
            "backlog_end_qty",
            "target_released_qty",
        )
    ):
        errors.append("non-finite action metric")
    evidence: dict[str, Any] = {
        "schema_version": EVIDENCE_SCHEMA_VERSION,
        "contract_revision": CONTRACT_REVISION,
        "case_key": case.key,
        "case": asdict(case),
        "status": status,
        "valid": not errors,
        "validation_errors": errors,
        "source_fingerprint": sources.fingerprint(case),
        "input_manifest_sha256": inputs.input_manifest_sha256,
        "risk_csv_sha256": inputs.risk_sha256,
        "control_schedule_csv_sha256": inputs.control_schedule_sha256,
        "measurement_start_stock_scale_csv_sha256": inputs.stock_scale_sha256,
        "command_sha256": _stable_sha256(command),
        "summary_sha256": _sha256(summary_path),
        "warmup_core_state_sha256": str(warmup.get("core_state_sha256") or ""),
        "metrics": metrics,
        "risk_applied_rows": risk_applied,
        "control_applied_rows": control_applied,
        "stock_adjustment_rows": stock_applied,
        "stock_lot_event_rows": stock_lot_events,
        "stock_lot_trace_verified": (
            not stock_errors
            if case.lever_id == "prepositioned_free_stock_14d"
            else "not_applicable"
        ),
        "action_application_verified": not errors,
        "quality_hold_days_preserved": (
            90 if case.failure_mode == "quality_hold" and not risk_errors else ""
        ),
        "alternative_source_created": False,
        "industrial_action_cost": "",
        "industrial_action_cost_status": "not_quantified_missing_industrial_inputs",
        "run_dir": str(case_dir.resolve()),
        "created_at_utc": _utc_now(),
    }
    evidence = _signed_payload(evidence, "evidence_signature")
    if errors:
        raise RuntimeError(f"Invalid action evidence {case.key}: {' | '.join(errors)}")
    return evidence


def _validate_evidence(
    evidence: Mapping[str, Any],
    case: ActionCase,
    sources: SourceBundle,
    inputs: InputBundle | None = None,
) -> None:
    _validate_signed_payload(evidence, "evidence_signature", label="case evidence")
    metrics = evidence.get("metrics") or {}
    if (
        evidence.get("schema_version") != EVIDENCE_SCHEMA_VERSION
        or evidence.get("contract_revision") != CONTRACT_REVISION
        or evidence.get("case_key") != case.key
        or evidence.get("case") != asdict(case)
        or evidence.get("valid") is not True
        or evidence.get("validation_errors") != []
        or evidence.get("source_fingerprint") != sources.fingerprint(case)
        or evidence.get("action_application_verified") is not True
        or evidence.get("alternative_source_created") is not False
        or not str(evidence.get("risk_csv_sha256") or "")
        or evidence.get("industrial_action_cost") != ""
        or evidence.get("industrial_action_cost_status")
        != "not_quantified_missing_industrial_inputs"
    ):
        raise ValueError(f"Action evidence contract mismatch: {case.key}")
    if case.lever_id == "prepositioned_free_stock_14d":
        stock_lot_events = evidence.get("stock_lot_event_rows") or []
        if (
            not str(evidence.get("measurement_start_stock_scale_csv_sha256") or "")
            or str(evidence.get("control_schedule_csv_sha256") or "")
            or (evidence.get("stock_lot_trace_verified") is not True)
            or not isinstance(stock_lot_events, list)
            or len(stock_lot_events) != 1
            or not str(stock_lot_events[0].get("lot_id") or "")
            or str(stock_lot_events[0].get("event_type") or "")
            != "measurement_start_stock_increase"
            or str(stock_lot_events[0].get("node_id") or "") != case.dst_node_id
            or str(stock_lot_events[0].get("item_id") or "") != case.item_id
            or not math.isclose(
                _to_float(stock_lot_events[0].get("qty"), math.nan),
                float(case.buffer_rounded_qty or math.nan),
                abs_tol=1e-5,
            )
        ):
            raise ValueError(f"J0 stock evidence actuator mismatch: {case.key}")
    else:
        if (
            not str(evidence.get("control_schedule_csv_sha256") or "")
            or str(evidence.get("measurement_start_stock_scale_csv_sha256") or "")
            or evidence.get("stock_lot_event_rows") not in (None, [])
        ):
            raise ValueError(f"Open-loop evidence actuator mismatch: {case.key}")
    if (
        case.failure_mode == "quality_hold"
        and evidence.get("quality_hold_days_preserved") != 90
    ):
        raise ValueError(f"Quality hold proof is not 90 days: {case.key}")
    if inputs is not None and (
        evidence.get("input_manifest_sha256") != inputs.input_manifest_sha256
        or evidence.get("risk_csv_sha256") != inputs.risk_sha256
        or evidence.get("control_schedule_csv_sha256") != inputs.control_schedule_sha256
        or evidence.get("measurement_start_stock_scale_csv_sha256")
        != inputs.stock_scale_sha256
    ):
        raise ValueError(f"Action evidence input hashes changed: {case.key}")
    for field in (
        "demand_qty",
        "fill_rate",
        "on_due_ratio",
        "backlog_qty_days",
        "backlog_end_qty",
        "target_released_qty",
    ):
        if not math.isfinite(_to_float(metrics.get(field), math.nan)):
            raise ValueError(f"Invalid metric {field}: {case.key}")


def _new_ledger(signature: str, *, smoke_only: bool) -> dict[str, Any]:
    return _signed_payload(
        {
            "schema_version": LEDGER_SCHEMA_VERSION,
            "campaign_signature": signature,
            "smoke_only": smoke_only,
            "case_files": {},
            "case_file_sha256": {},
            "updated_at_utc": _utc_now(),
        },
        "ledger_signature",
    )


def _load_ledger(
    output_dir: Path, signature: str, *, smoke_only: bool
) -> dict[str, Any]:
    path = output_dir / LEDGER_FILE
    evidence_dir = output_dir / "ledger_cases"
    if not path.is_file():
        if evidence_dir.exists() and any(evidence_dir.iterdir()):
            raise ValueError("Evidence files exist without an action ledger")
        return _new_ledger(signature, smoke_only=smoke_only)
    ledger = _read_json(path)
    _validate_signed_payload(ledger, "ledger_signature", label="execution ledger")
    files = ledger.get("case_files") or {}
    hashes = ledger.get("case_file_sha256") or {}
    if (
        ledger.get("schema_version") != LEDGER_SCHEMA_VERSION
        or ledger.get("campaign_signature") != signature
        or ledger.get("smoke_only") is not smoke_only
        or not isinstance(files, dict)
        or not isinstance(hashes, dict)
        or set(files) != set(hashes)
        or len(set(files.values())) != len(files)
    ):
        raise ValueError("Action ledger scope/signature mismatch")
    disk = (
        {
            item.relative_to(output_dir).as_posix()
            for item in evidence_dir.rglob("*")
            if item.is_file()
        }
        if evidence_dir.is_dir()
        else set()
    )
    if disk != set(files.values()):
        raise ValueError("Action ledger disk inventory is not exact")
    for key, relative_text in files.items():
        relative = Path(str(relative_text))
        expected = _evidence_relative(str(key))
        evidence_path = output_dir / relative
        if (
            relative.is_absolute()
            or ".." in relative.parts
            or relative.as_posix() != expected.as_posix()
            or evidence_path.is_symlink()
            or not evidence_path.is_file()
            or _sha256(evidence_path) != hashes[key]
            or _read_json(evidence_path).get("case_key") != key
        ):
            raise ValueError(f"Action ledger evidence mismatch: {key}")
    return ledger


def _write_ledger(output_dir: Path, ledger: Mapping[str, Any]) -> dict[str, Any]:
    unsigned = dict(ledger)
    unsigned.pop("ledger_signature", None)
    signed = _signed_payload(unsigned, "ledger_signature")
    _write_json(output_dir / LEDGER_FILE, signed)
    return signed


def _persist_evidence(
    output_dir: Path,
    ledger: Mapping[str, Any],
    evidence: Mapping[str, Any],
) -> dict[str, Any]:
    updated = dict(ledger)
    files = dict(updated.get("case_files") or {})
    hashes = dict(updated.get("case_file_sha256") or {})
    key = str(evidence["case_key"])
    relative = _evidence_relative(key)
    path = output_dir / relative
    if key in files:
        if (
            files[key] != relative.as_posix()
            or not path.is_file()
            or _sha256(path) != hashes[key]
        ):
            raise ValueError(f"Existing action evidence changed: {key}")
        return updated
    _write_json(path, evidence)
    files[key] = relative.as_posix()
    hashes[key] = _sha256(path)
    updated["case_files"] = files
    updated["case_file_sha256"] = hashes
    updated["updated_at_utc"] = _utc_now()
    return _write_ledger(output_dir, updated)


def _v2_metrics(
    row: Mapping[str, Any], case: ActionCase, *, baseline: bool
) -> dict[str, Any]:
    product = case.target_product_id
    prefix = f"baseline_chain__{case.chain_id}__ops__" if baseline else ""
    component_min = _to_float(row.get(f"{prefix}component_input_stock_min"), math.nan)
    zero_days = _to_float(row.get(f"{prefix}component_days_at_zero"), math.nan)
    return {
        "demand_qty": _to_float(row.get(f"demand_qty_{product}"), math.nan),
        "fill_rate": _to_float(row.get(f"fill_rate_{product}"), math.nan),
        "on_due_ratio": _to_float(row.get(f"on_due_volume_proxy_{product}"), math.nan),
        "backlog_qty_days": _to_float(row.get(f"backlog_qty_days_{product}"), math.nan),
        "backlog_end_qty": _to_float(row.get(f"backlog_end_qty_{product}"), math.nan),
        "backlog_max_qty": _to_float(row.get(f"backlog_max_qty_{product}"), math.nan),
        "component_min_stock_qty": component_min,
        "component_reached_zero": (
            component_min <= ZERO_EPS if math.isfinite(component_min) else ""
        ),
        "component_zero_stock_day_count": (
            zero_days if math.isfinite(zero_days) else ""
        ),
        "component_stock_metric_status": (
            "retained_derived_horizon_count_source_daily_series_compacted"
            if math.isfinite(zero_days)
            else "minimum_only_source_daily_series_compacted"
        ),
        "target_released_qty": _to_float(
            row.get(f"{prefix}target_released_qty"), math.nan
        ),
        "product_uom": "UN",
        "component_uom": str(
            row.get(f"{prefix}component_stock_uom") or case.buffer_uom or ""
        ),
        "industrial_action_cost": "",
        "industrial_action_cost_status": "not_applicable_reference_arm",
    }


def _v3_quality_metrics(
    evidence: Mapping[str, Any], case: ActionCase
) -> dict[str, Any]:
    matches = [
        row
        for row in evidence.get("product_metrics") or []
        if str(row.get("product_id") or "") == case.target_product_id
    ]
    if len(matches) != 1:
        raise ValueError(f"V3 target-product metrics absent: {case.key}")
    row = matches[0]
    return {
        "demand_qty": _to_float(row.get("demand_qty"), math.nan),
        "fill_rate": _to_float(row.get("fill_rate"), math.nan),
        "on_due_ratio": _to_float(row.get("on_due_ratio"), math.nan),
        "backlog_qty_days": _to_float(row.get("backlog_qty_days"), math.nan),
        "backlog_end_qty": _to_float(row.get("backlog_end_qty"), math.nan),
        "backlog_max_qty": "",
        "component_min_stock_qty": "",
        "component_reached_zero": "",
        "component_zero_stock_day_count": "",
        "component_stock_metric_status": "not_retained_in_compact_V3_quality_source",
        "target_released_qty": _to_float(row.get("released_qty"), math.nan),
        "product_uom": str(row.get("uom") or "UN"),
        "component_uom": case.buffer_uom,
        "industrial_action_cost": "",
        "industrial_action_cost_status": "not_applicable_reference_arm",
    }


def _source_arm_metrics(
    case: ActionCase,
    sources: SourceBundle,
    arm: str,
) -> dict[str, Any]:
    if arm == "normal":
        return _v2_metrics(
            sources.v2_rows[("baseline_nominal", case.seed)], case, baseline=True
        )
    if arm != "incident_no_action":
        raise ValueError(f"Unsupported source arm: {arm}")
    if case.failure_mode == "quality_hold":
        return _v3_quality_metrics(
            sources.v3_quality_evidence[(case.incident_source_case_id, case.seed)],
            case,
        )
    return _v2_metrics(
        sources.v2_rows[(case.incident_source_case_id, case.seed)],
        case,
        baseline=False,
    )


def _paired_result(
    case: ActionCase,
    evidence: Mapping[str, Any],
    sources: SourceBundle,
) -> dict[str, Any]:
    normal = _source_arm_metrics(case, sources, "normal")
    incident = _source_arm_metrics(case, sources, "incident_no_action")
    action = dict(evidence.get("metrics") or {})
    if not str(action.get("component_uom") or ""):
        action["component_uom"] = str(
            incident.get("component_uom") or normal.get("component_uom") or ""
        )
    comparable_metrics = (
        "demand_qty",
        "fill_rate",
        "on_due_ratio",
        "backlog_qty_days",
        "backlog_end_qty",
        "target_released_qty",
    )
    for arm_name, values in (
        ("normal", normal),
        ("incident_no_action", incident),
        ("incident_with_action", action),
    ):
        numeric = {
            name: _to_float(values.get(name), math.nan) for name in comparable_metrics
        }
        if (
            any(not math.isfinite(value) for value in numeric.values())
            or numeric["demand_qty"] <= 0.0
            or not 0.0 <= numeric["fill_rate"] <= 1.0
            or not 0.0 <= numeric["on_due_ratio"] <= 1.0
            or any(
                numeric[name] < 0.0
                for name in (
                    "backlog_qty_days",
                    "backlog_end_qty",
                    "target_released_qty",
                )
            )
        ):
            raise ValueError(f"Invalid comparable {arm_name} metrics: {case.key}")
    demand_values = [
        _to_float(row.get("demand_qty"), math.nan) for row in (normal, incident, action)
    ]
    if any(not math.isfinite(value) for value in demand_values) or not all(
        math.isclose(demand_values[0], value, rel_tol=0.0, abs_tol=1e-6)
        for value in demand_values[1:]
    ):
        raise ValueError(f"Triplet demand denominator is not paired: {case.key}")
    row: dict[str, Any] = {
        "pairing_id": case.pairing_id,
        "seed": case.seed,
        "seed_prefix_index": case.seed_prefix_index,
        "chain_id": case.chain_id,
        "supplier_id": case.supplier_id,
        "item_id": case.item_id,
        "dst_node_id": case.dst_node_id,
        "target_product_id": case.target_product_id,
        "lever_id": case.lever_id,
        "failure_mode": case.failure_mode,
        "incident_start_day": case.incident_start_day,
        "incident_end_day": case.incident_end_day,
        "incident_value": case.incident_value,
        "incident_unit": case.incident_unit,
        "buffer_raw_qty": case.buffer_raw_qty or "",
        "buffer_rounded_qty": case.buffer_rounded_qty or "",
        "procurement_standard_lot_qty": (case.procurement_standard_lot_qty or ""),
        "buffer_procurement_lot_count": (case.buffer_procurement_lot_count or ""),
        "buffer_procurement_lot_count_semantics": (
            "procurement_rounding_count_not_engine_lot_segmentation"
            if case.buffer_procurement_lot_count is not None
            else ""
        ),
        "engine_j0_stock_adjustment_semantics": (
            "aggregate_stock_scale_with_lot_ledger_reconciliation"
            if case.lever_id == "prepositioned_free_stock_14d"
            else ""
        ),
        "buffer_uom": case.buffer_uom,
        "stock_present_at_measured_j0": (
            case.lever_id == "prepositioned_free_stock_14d"
        ),
        "stock_acquisition_simulated": False,
        "paired_same_seed": True,
        "paired_source_fingerprint": sources.fingerprint(case),
        "case_evidence_signature": evidence.get("evidence_signature"),
        "action_application_verified": evidence.get("action_application_verified"),
        "quality_hold_days_preserved": evidence.get("quality_hold_days_preserved"),
        "industrial_action_cost": "",
        "industrial_action_cost_status": "not_quantified_missing_industrial_inputs",
        "action_recommended": False,
        "service_ratio_unit": "ratio_0_to_1",
        "service_delta_unit": "percentage_points",
        "backlog_qty_days_unit": "UN_day",
        "target_released_qty_unit": "UN",
        "component_stock_qty_unit": str(action.get("component_uom") or ""),
    }
    metrics = (
        "demand_qty",
        "fill_rate",
        "on_due_ratio",
        "backlog_qty_days",
        "backlog_end_qty",
        "backlog_max_qty",
        "component_min_stock_qty",
        "component_reached_zero",
        "component_zero_stock_day_count",
        "component_stock_metric_status",
        "target_released_qty",
        "product_uom",
        "component_uom",
    )
    for arm_name, values in (
        ("normal", normal),
        ("incident_no_action", incident),
        ("incident_with_action", action),
    ):
        for metric in metrics:
            row[f"{arm_name}__{metric}"] = values.get(metric, "")
    for metric in (
        "fill_rate",
        "on_due_ratio",
        "backlog_qty_days",
        "backlog_end_qty",
        "backlog_max_qty",
        "component_min_stock_qty",
        "component_zero_stock_day_count",
        "target_released_qty",
    ):
        action_value = _to_float(action.get(metric), math.nan)
        incident_value = _to_float(incident.get(metric), math.nan)
        row[f"action_minus_incident__{metric}"] = (
            action_value - incident_value
            if math.isfinite(action_value) and math.isfinite(incident_value)
            else ""
        )
    row["action_minus_incident__on_due_percentage_points"] = 100.0 * _to_float(
        row["action_minus_incident__on_due_ratio"], 0.0
    )
    return row


def _summary_rows(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str, str], list[Mapping[str, Any]]] = {}
    for row in rows:
        key = (
            str(row.get("chain_id") or ""),
            str(row.get("lever_id") or ""),
            str(row.get("target_product_id") or ""),
        )
        grouped.setdefault(key, []).append(row)
    result: list[dict[str, Any]] = []
    summary_metrics = (
        "action_minus_incident__on_due_percentage_points",
        "action_minus_incident__backlog_qty_days",
        "action_minus_incident__backlog_end_qty",
        "action_minus_incident__component_min_stock_qty",
        "action_minus_incident__target_released_qty",
    )
    for key, group in sorted(grouped.items()):
        item: dict[str, Any] = {
            "chain_id": key[0],
            "lever_id": key[1],
            "target_product_id": key[2],
            "seed_count": len(group),
            "seed_ids": "|".join(str(row["seed"]) for row in group),
            "all_actions_applied": all(
                _as_bool(row.get("action_application_verified")) for row in group
            ),
            "industrial_action_cost": "",
            "industrial_action_cost_status": "not_quantified_missing_industrial_inputs",
            "action_recommended": False,
            "service_delta_unit": "percentage_points",
            "backlog_qty_days_delta_unit": "UN_day",
            "target_released_qty_delta_unit": "UN",
            "component_stock_qty_delta_unit": str(
                group[0].get("component_stock_qty_unit") or ""
            ),
        }
        for metric in summary_metrics:
            values = [
                _to_float(row.get(metric), math.nan)
                for row in group
                if math.isfinite(_to_float(row.get(metric), math.nan))
            ]
            item[f"{metric}__available_count"] = len(values)
            item[f"{metric}__mean"] = fmean(values) if values else ""
            item[f"{metric}__std"] = pstdev(values) if values else ""
            item[f"{metric}__min"] = min(values) if values else ""
            item[f"{metric}__max"] = max(values) if values else ""
        result.append(item)
    return result


def _campaign_signature(
    plan: ActionPlan, sources: SourceBundle, *, smoke_only: bool
) -> str:
    return _stable_sha256(
        {
            "schema_version": SCHEMA_VERSION,
            "contract_revision": CONTRACT_REVISION,
            "runner_builder_sha256": _sha256(Path(__file__).resolve()),
            "V5_protocol_signature": plan.manifest.get("protocol_signature"),
            "source_identity_signature": sources.source_identity_signature,
            "seed_policy": SEED_POLICY,
            "full_seed_ids": list(plan.seeds),
            "executable_levers": list(EXECUTABLE_LEVERS),
            "scope": "smoke_nonreusable" if smoke_only else "full_15_then_30",
        }
    )


def _checkpoint_subset_signature(
    cases: Sequence[ActionCase], sources: SourceBundle
) -> str:
    return _stable_sha256(
        {
            case.key: sources.fingerprint(case)
            for case in sorted(cases, key=lambda row: row.key)
        }
    )


def _write_checkpoint(
    *,
    output_dir: Path,
    signature: str,
    cases: Sequence[ActionCase],
    sources: SourceBundle,
    ledger: Mapping[str, Any],
    results_path: Path,
    summary_path: Path,
    full_seed_ids: Sequence[int],
) -> dict[str, Any]:
    files = ledger.get("case_files") or {}
    hashes = ledger.get("case_file_sha256") or {}
    expected = {case.key for case in cases}
    if set(files) != expected or set(hashes) != expected:
        raise ValueError("Preliminary action ledger is not the exact 15-seed subset")
    payload = {
        "schema_version": CHECKPOINT_SCHEMA_VERSION,
        "contract_revision": CONTRACT_REVISION,
        "status": "paused_preliminary_15_of_30",
        "campaign_signature": signature,
        "completed_seed_ids": list(sources.target_seed_ids),
        "signed_final_seed_ids": list(full_seed_ids),
        "seed_scheduling_policy": SEED_POLICY,
        "case_count": len(cases),
        "case_evidence_file_sha256": {
            key: {"relative_path": files[key], "sha256": hashes[key]}
            for key in sorted(expected)
        },
        "source_subset_signature": _checkpoint_subset_signature(cases, sources),
        "execution_ledger_sha256_at_checkpoint": _sha256(output_dir / LEDGER_FILE),
        "preliminary_results_file": results_path.name,
        "preliminary_results_sha256": _sha256(results_path),
        "preliminary_summary_file": summary_path.name,
        "preliminary_summary_sha256": _sha256(summary_path),
        "preliminary_not_final": True,
        "action_recommended": False,
        "industrial_action_cost_quantified": False,
        "checkpoint_at_utc": _utc_now(),
    }
    signed = _signed_payload(payload, "checkpoint_signature")
    path = output_dir / CHECKPOINT_FILE
    if path.is_file():
        existing = _read_json(path)
        _validate_signed_payload(
            existing, "checkpoint_signature", label="action checkpoint"
        )
        left = dict(existing)
        right = dict(signed)
        for value in (left, right):
            value.pop("checkpoint_signature", None)
            value.pop("checkpoint_at_utc", None)
        if left != right:
            raise ValueError("Existing action checkpoint differs")
        return existing
    _write_json(path, signed)
    return signed


def _validate_checkpoint(
    *,
    output_dir: Path,
    signature: str,
    preliminary_cases: Sequence[ActionCase],
    sources: SourceBundle,
    ledger: Mapping[str, Any],
    full_seed_ids: Sequence[int],
) -> dict[str, Any] | None:
    path = output_dir / CHECKPOINT_FILE
    if not path.is_file():
        return None
    payload = _read_json(path)
    _validate_signed_payload(payload, "checkpoint_signature", label="action checkpoint")
    evidence = payload.get("case_evidence_file_sha256") or {}
    expected = {case.key for case in preliminary_cases}
    if (
        payload.get("schema_version") != CHECKPOINT_SCHEMA_VERSION
        or payload.get("contract_revision") != CONTRACT_REVISION
        or payload.get("campaign_signature") != signature
        or payload.get("status") != "paused_preliminary_15_of_30"
        or payload.get("completed_seed_ids") != list(full_seed_ids)[:15]
        or payload.get("signed_final_seed_ids") != list(full_seed_ids)
        or _to_int(payload.get("case_count"), -1) != len(preliminary_cases)
        or set(evidence) != expected
        or payload.get("source_subset_signature")
        != _checkpoint_subset_signature(preliminary_cases, sources)
        or payload.get("preliminary_not_final") is not True
        or payload.get("action_recommended") is not False
        or payload.get("industrial_action_cost_quantified") is not False
    ):
        raise ValueError("Action checkpoint contract mismatch")
    results_path = output_dir / PRELIMINARY_RESULTS_FILE
    summary_path = output_dir / PRELIMINARY_SUMMARY_FILE
    if (
        payload.get("preliminary_results_file") != PRELIMINARY_RESULTS_FILE
        or payload.get("preliminary_summary_file") != PRELIMINARY_SUMMARY_FILE
        or not results_path.is_file()
        or not summary_path.is_file()
        or _sha256(results_path) != payload.get("preliminary_results_sha256")
        or _sha256(summary_path) != payload.get("preliminary_summary_sha256")
    ):
        raise ValueError("Preliminary checkpoint result files changed")
    files = ledger.get("case_files") or {}
    hashes = ledger.get("case_file_sha256") or {}
    for key, item in evidence.items():
        if files.get(key) != item.get("relative_path") or hashes.get(key) != item.get(
            "sha256"
        ):
            raise ValueError("Action checkpoint is no longer an exact ledger subset")
    if set(files) == expected and _sha256(output_dir / LEDGER_FILE) != payload.get(
        "execution_ledger_sha256_at_checkpoint"
    ):
        raise ValueError("Preliminary checkpoint ledger changed")
    return payload


@contextmanager
def _exclusive_lock(output_dir: Path) -> Iterable[None]:
    path = output_dir / LOCK_FILE
    try:
        descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError as exc:
        raise RuntimeError(
            f"Action runner lock exists; inspect before recovery: {path}"
        ) from exc
    try:
        os.write(descriptor, f"{os.getpid()}\n".encode("ascii"))
        os.close(descriptor)
        descriptor = -1
        yield
    finally:
        if descriptor >= 0:
            os.close(descriptor)
        if path.is_file():
            path.unlink()


def _write_manifest(path: Path, payload: Mapping[str, Any]) -> dict[str, Any]:
    signed = _signed_payload(payload, "manifest_signature")
    _write_json(path, signed)
    return signed


def _selected_cases(
    plan: ActionPlan,
    *,
    smoke_only: bool,
    checkpoint_after_repetitions: int | None,
) -> tuple[ActionCase, ...]:
    if smoke_only:
        selected: list[ActionCase] = []
        for lever in EXECUTABLE_LEVERS:
            selected.append(next(case for case in plan.cases if case.lever_id == lever))
        return tuple(replace(case, stage="smoke") for case in selected)
    count = 15 if checkpoint_after_repetitions == 15 else 30
    return tuple(
        replace(case, stage="full")
        for case in plan.cases
        if case.seed_prefix_index <= count
    )


def run_action_campaign(
    *,
    plan_dir: Path,
    post_priority_results_dir: Path,
    j0_snapshot_dir: Path = DEFAULT_J0_SNAPSHOT_DIR,
    output_dir: Path | None,
    mode: str,
    graph: Path = protocol.DEFAULT_GRAPH,
    engine: Path = protocol.DEFAULT_ENGINE,
    profile: Path = protocol.DEFAULT_PROFILE,
    workers: int = 2,
    checkpoint_after_repetitions: int | None = None,
    engine_execution_authorized: bool = False,
    case_executor: CaseExecutor | None = None,
) -> dict[str, Any]:
    if mode not in {"validate", "prepare", "smoke", "full"}:
        raise ValueError(f"Unsupported action runner mode: {mode}")
    if workers <= 0:
        raise ValueError("workers must be positive")
    if checkpoint_after_repetitions not in {None, 15}:
        raise ValueError("Checkpoint must be omitted or exactly 15")
    if mode == "smoke" and checkpoint_after_repetitions is not None:
        raise ValueError("Smoke has its own non-reusable one-seed scope")
    plan = load_action_plan(
        plan_dir=plan_dir,
        graph=graph,
        engine=engine,
        profile=profile,
    )
    source_count = (
        1 if mode == "smoke" else 15 if checkpoint_after_repetitions == 15 else 30
    )
    try:
        sources = validate_paired_sources(
            plan,
            post_priority_results_dir=post_priority_results_dir,
            target_seed_ids=plan.seeds[:source_count],
            j0_snapshot_dir=j0_snapshot_dir,
        )
    except SourcesNotReadyError as exc:
        if mode == "validate":
            return {
                "status": "sources_not_ready",
                "reason": str(exc),
                "requested_seed_count": source_count,
                "engine_execution_started": False,
            }
        raise
    if mode == "validate":
        return {
            "status": "valid_sources_ready",
            "requested_seed_count": source_count,
            "source_identity_signature": sources.source_identity_signature,
            "maximum_new_action_run_count": 180 if source_count == 15 else 360,
            "engine_execution_started": False,
            "alternative_source_created": False,
        }
    if output_dir is None:
        raise ValueError("--output-dir is required outside validate mode")
    if mode in {"smoke", "full"} and not engine_execution_authorized:
        raise PermissionError(
            "Engine execution requires --execute-reviewed-plan after root review"
        )
    smoke_only = mode == "smoke"
    selected = _selected_cases(
        plan,
        smoke_only=smoke_only,
        checkpoint_after_repetitions=checkpoint_after_repetitions,
    )
    evidence_paths = {_evidence_relative(case.key).as_posix() for case in selected}
    if len(evidence_paths) != len(selected):
        raise ValueError("Action case evidence path collision")
    signature = _campaign_signature(plan, sources, smoke_only=smoke_only)
    output_dir = output_dir.resolve()
    if output_dir.exists() and not output_dir.is_dir():
        raise ValueError(f"Output path is not a directory: {output_dir}")
    output_dir.mkdir(parents=True, exist_ok=True)
    custom_executor = case_executor is not None
    executor = case_executor or execute_engine_case
    with _exclusive_lock(output_dir):
        manifest_path = output_dir / RUNNER_MANIFEST
        previous: dict[str, Any] | None = None
        if manifest_path.is_file():
            previous = _read_json(manifest_path)
            _validate_signed_payload(
                previous, "manifest_signature", label="action manifest"
            )
            if (
                previous.get("campaign_signature") != signature
                or previous.get("smoke_only") is not smoke_only
                or previous.get("custom_executor_used") is not custom_executor
            ):
                raise ValueError(
                    "Existing output has a different action campaign scope"
                )
        elif any(path.name != LOCK_FILE for path in output_dir.iterdir()):
            raise ValueError(
                "Refusing an unregistered non-empty action output directory"
            )
        manifest: dict[str, Any] = {
            "schema_version": SCHEMA_VERSION,
            "contract_revision": CONTRACT_REVISION,
            "status": "preparing" if mode == "prepare" else "running",
            "campaign_signature": signature,
            "runner_builder_sha256": _sha256(Path(__file__).resolve()),
            "V5_protocol_signature": plan.manifest.get("protocol_signature"),
            "source_identity_signature": sources.source_identity_signature,
            "source_identity": sources.source_identity,
            "mode": mode,
            "smoke_only": smoke_only,
            "smoke_reusable_in_full": False,
            "smoke_used_for_eta": False,
            "workers": workers,
            "checkpoint_after_repetitions": checkpoint_after_repetitions,
            "selected_case_count": len(selected),
            "selected_seed_ids": list(sources.target_seed_ids),
            "full_seed_ids": list(plan.seeds),
            "seed_scheduling_policy": SEED_POLICY,
            "custom_executor_used": custom_executor,
            "publishable_results": False,
            "engine_execution_authorized": engine_execution_authorized,
            "engine_execution_started": False,
            "alternative_source_created": False,
            "quality_hold_days_preserved": 90,
            "industrial_action_cost_quantified": False,
            "action_recommended": False,
            "first_started_at_utc": (
                previous.get("first_started_at_utc") if previous else _utc_now()
            ),
            "updated_at_utc": _utc_now(),
        }
        _write_manifest(manifest_path, manifest)
        try:
            ledger = _load_ledger(output_dir, signature, smoke_only=smoke_only)
            evidence_by_key = {
                key: _read_json(output_dir / relative)
                for key, relative in (ledger.get("case_files") or {}).items()
            }
            case_by_key = {case.key: case for case in selected}
            if not set(evidence_by_key) <= set(case_by_key):
                raise ValueError("Ledger contains cases outside the cumulative target")
            for key, evidence in evidence_by_key.items():
                _validate_evidence(evidence, case_by_key[key], sources)
            preliminary_cases = tuple(
                replace(case, stage="full")
                for case in plan.cases
                if case.seed_prefix_index <= 15
            )
            checkpoint = (
                _validate_checkpoint(
                    output_dir=output_dir,
                    signature=signature,
                    preliminary_cases=preliminary_cases,
                    sources=sources,
                    ledger=ledger,
                    full_seed_ids=plan.seeds,
                )
                if not smoke_only
                else None
            )
            if (
                mode == "full"
                and checkpoint_after_repetitions is None
                and checkpoint is None
            ):
                raise ValueError(
                    "Final 30-seed run requires the signed 15-seed checkpoint"
                )
            if checkpoint_after_repetitions == 15 and any(
                _to_int((evidence.get("case") or {}).get("seed_prefix_index"), 99) > 15
                for evidence in evidence_by_key.values()
            ):
                raise ValueError(
                    "Future-seed evidence cannot precede the 15-seed checkpoint"
                )
            prepared = {
                case.key: prepare_case_inputs(case, plan, sources, output_dir)
                for case in selected
            }
            if mode == "prepare":
                manifest.update(
                    {
                        "status": "prepared_not_executed",
                        "prepared_case_count": len(prepared),
                        "engine_execution_started": False,
                        "updated_at_utc": _utc_now(),
                    }
                )
                return _write_manifest(manifest_path, manifest)
            missing = [case for case in selected if case.key not in evidence_by_key]
            manifest.update(
                {
                    "engine_execution_started": bool(missing),
                    "missing_case_count_at_invocation_start": len(missing),
                    "reused_valid_action_case_count": len(selected) - len(missing),
                }
            )
            _write_manifest(manifest_path, manifest)
            if missing:
                with ThreadPoolExecutor(max_workers=workers) as pool:
                    futures = {
                        pool.submit(
                            executor,
                            case,
                            plan,
                            sources,
                            output_dir,
                            prepared[case.key],
                        ): case
                        for case in missing
                    }
                    for future in as_completed(futures):
                        case = futures[future]
                        evidence = dict(future.result())
                        _validate_evidence(
                            evidence,
                            case,
                            sources,
                            prepared[case.key],
                        )
                        ledger = _persist_evidence(output_dir, ledger, evidence)
                        evidence_by_key[case.key] = evidence
                        if not custom_executor:
                            run_dir = Path(str(evidence.get("run_dir") or ""))
                            if run_dir.is_dir():
                                network.campaign_core.prune_case_artifacts(run_dir)
            for case in selected:
                evidence = evidence_by_key.get(case.key)
                if evidence is None:
                    raise RuntimeError(
                        f"Missing action evidence after execution: {case.key}"
                    )
                _validate_evidence(
                    evidence,
                    case,
                    sources,
                    prepared[case.key],
                )
            result_rows = [
                _paired_result(case, evidence_by_key[case.key], sources)
                for case in selected
            ]
            summary_rows = _summary_rows(result_rows)
            if smoke_only:
                results_path = output_dir / "smoke_paired_action_results.csv"
                summary_path = output_dir / "smoke_action_results_summary.csv"
            elif checkpoint_after_repetitions == 15:
                results_path = output_dir / PRELIMINARY_RESULTS_FILE
                summary_path = output_dir / PRELIMINARY_SUMMARY_FILE
            else:
                results_path = output_dir / FINAL_RESULTS_FILE
                summary_path = output_dir / FINAL_SUMMARY_FILE
            _write_csv(results_path, result_rows)
            _write_csv(summary_path, summary_rows)
            if checkpoint_after_repetitions == 15:
                checkpoint = _write_checkpoint(
                    output_dir=output_dir,
                    signature=signature,
                    cases=selected,
                    sources=sources,
                    ledger=ledger,
                    results_path=results_path,
                    summary_path=summary_path,
                    full_seed_ids=plan.seeds,
                )
                status = "paused_preliminary_15_of_30"
            elif smoke_only:
                status = "smoke_complete_nonreusable"
            else:
                status = "complete_30_of_30"
            manifest.update(
                {
                    "status": status,
                    "completed_case_count": len(selected),
                    "ledger_case_count": len(ledger.get("case_files") or {}),
                    "execution_ledger_sha256": _sha256(output_dir / LEDGER_FILE),
                    "results_file": results_path.name,
                    "results_sha256": _sha256(results_path),
                    "summary_file": summary_path.name,
                    "summary_sha256": _sha256(summary_path),
                    "checkpoint_signature": (
                        checkpoint.get("checkpoint_signature") if checkpoint else ""
                    ),
                    "preliminary_not_final": status != "complete_30_of_30",
                    # These are exploratory counterfactual simulations.  A complete
                    # numerical campaign is not, by itself, evidence that an action
                    # is operationally feasible or ready for an industrial claim.
                    "publishable_results": False,
                    "exploratory_simulation_results_complete": (
                        status == "complete_30_of_30" and not custom_executor
                    ),
                    "engine_execution_started": bool(missing),
                    "all_actions_applied_and_verified": True,
                    "industrial_action_cost_quantified": False,
                    "action_recommended": False,
                    "updated_at_utc": _utc_now(),
                }
            )
            return _write_manifest(manifest_path, manifest)
        except Exception as exc:
            manifest.update(
                {
                    "status": "failed",
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                    "failed_at_utc": _utc_now(),
                    "industrial_action_cost_quantified": False,
                    "action_recommended": False,
                }
            )
            _write_manifest(manifest_path, manifest)
            raise


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--mode", choices=("validate", "prepare", "smoke", "full"), default="validate"
    )
    parser.add_argument("--plan-dir", type=Path, default=DEFAULT_PROTOCOL_DIR)
    parser.add_argument(
        "--post-priority-results-dir", type=Path, default=DEFAULT_POST_PRIORITY_RESULTS
    )
    parser.add_argument(
        "--j0-snapshot-dir", type=Path, default=DEFAULT_J0_SNAPSHOT_DIR
    )
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--graph", type=Path, default=protocol.DEFAULT_GRAPH)
    parser.add_argument("--engine", type=Path, default=protocol.DEFAULT_ENGINE)
    parser.add_argument("--profile", type=Path, default=protocol.DEFAULT_PROFILE)
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--checkpoint-after-repetitions", type=int)
    parser.add_argument("--execute-reviewed-plan", action="store_true")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    result = run_action_campaign(
        plan_dir=args.plan_dir,
        post_priority_results_dir=args.post_priority_results_dir,
        j0_snapshot_dir=args.j0_snapshot_dir,
        output_dir=args.output_dir,
        mode=args.mode,
        graph=args.graph,
        engine=args.engine,
        profile=args.profile,
        workers=args.workers,
        checkpoint_after_repetitions=args.checkpoint_after_repetitions,
        engine_execution_authorized=args.execute_reviewed_plan,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
