#!/usr/bin/env python3
"""One-shot V4 refinement after a signed rejected V3 campaign.

The module is additive and fail-closed.  Importing it does not import or run the
simulation engine.  A plan can only be created from a cryptographically valid
V3 rejection and an explicit, signed op80 decision.  Development reuses the
burned V3 campaign seeds; the fresh holdout is executed only after a frozen
development selection and is never used for retuning.
"""

from __future__ import annotations

import argparse
import copy
import csv
import gzip
import hashlib
import importlib
import io
import json
import math
import os
import random
import re
import shutil
import time
import uuid
from collections.abc import Callable, Mapping, Sequence
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from statistics import median
from typing import Any


SCHEMA_VERSION = "etudecas.multiseed_operating_point_refinement.v4"
PLAN_SCHEMA_VERSION = f"{SCHEMA_VERSION}.plan"
EVIDENCE_SCHEMA_VERSION = f"{SCHEMA_VERSION}.evidence"
SELECTION_SCHEMA_VERSION = f"{SCHEMA_VERSION}.development_selection"
HOLDOUT_SCHEMA_VERSION = f"{SCHEMA_VERSION}.holdout_result"
OP80_DECISION_SCHEMA_VERSION = f"{SCHEMA_VERSION}.op80_decision"

V3_CAMPAIGN_SCHEMA_VERSION = "etudecas.supplier_operating_point_full_campaign.v2"
V3_PREFLIGHT_SCHEMA_VERSION = (
    "etudecas.supplier_operating_point_full_campaign.v2.operating_point_preflight.v2"
)
V3_REJECTED_STATUS = "holdout_rejected_30_seed"
V3_POINTS_SCHEMA_VERSION = (
    "etudecas.multiseed_operating_point_refinement.v3.selected_operating_points"
)
V3_POINTS_STATUS = "selected_on_five_seed_refinement_v3_pending_30_seed_holdout"
V3_PLAN_SCHEMA_VERSION = "etudecas.multiseed_operating_point_refinement.v3.plan"
COARSE_EVIDENCE_SCHEMA_VERSION = (
    "etudecas.supplier_balanced_product_delay_calibration.v1.case_evidence"
)

SOURCE_DESIGN_SEEDS = (340281,)
SOURCE_CALIBRATION_SEEDS = tuple(range(340282, 340287))
DEVELOPMENT_SEEDS = tuple(range(340287, 340317))
INCIDENT_DESIGN_SEED = 900659036
INCIDENT_DESIGN_SEED_DOMAIN = "ETUDECAS-V4-INCIDENT-WINDOW-DESIGN-20260905"
INCIDENT_DESIGN_MESSAGE_SHA256 = (
    "59f7aeb5ac1ec166fa0716c1a338ad62786e95857688fa6f744e817eeea15a1f"
)

HOLDOUT_SEED_DOMAIN = "ETUDECAS-V4-INDEPENDENT-HOLDOUT-20260905"
HOLDOUT_SEED_COUNT = 30
HOLDOUT_SEED_CSV_SHA256 = (
    "8741fc44dd57a7388f452bfb3dbdc2d8d75dcea635cdc30beb29bc96bfce24bd"
)
EXPECTED_HOLDOUT_SEEDS = (
    573960646,
    1871757092,
    1745052434,
    1160236806,
    92478021,
    1394133310,
    1596008569,
    1416403695,
    1492750790,
    1316742469,
    1332985495,
    1408401338,
    1869291112,
    12328805,
    1374528760,
    434799925,
    1796420146,
    55195456,
    1146050562,
    583480470,
    1369666196,
    1545515706,
    43087084,
    1248984977,
    887386588,
    1734584754,
    1775564575,
    508903655,
    546039346,
    466329796,
)

OP93_GRID = (
    ("op93_source_7_81", 7.0, 81.0, "reuse_source_development"),
    ("op93_v4_8_80p5", 8.0, 80.5, "execute"),
    ("op93_v4_8_81p5", 8.0, 81.5, "execute"),
    ("op93_v4_8p5_80p5", 8.5, 80.5, "execute"),
    ("op93_v4_8p5_81p5", 8.5, 81.5, "execute"),
)

OP80_GRID = (
    ("op80_v4_17_95", 17.0, 95.0),
    ("op80_v4_17_96", 17.0, 96.0),
    ("op80_v4_17p5_95", 17.5, 95.0),
    ("op80_v4_17p5_96", 17.5, 96.0),
)

PRODUCTS = ("268091", "268967")
PRODUCT_FACTORY = {"268091": "M-1810", "268967": "M-1430"}
TARGETS = {"op_100": 1.0, "op_93": 0.93, "op_80": 0.80}
DEVELOPMENT_INNER_BANDS = {"op_93": (0.9225, 0.9375), "op_80": (0.7925, 0.8075)}
OUTER_BANDS = {"op_93": (0.915, 0.945), "op_80": (0.785, 0.815)}
REFERENCE_MINIMUM = 0.985
NON_SATURATION_LIMIT = 0.995
MIN_ORDERED_SEEDS = 24
SERVICE_DAYS = 720
BOOTSTRAP_REPLICATES = 10_000
BOOTSTRAP_SEED = 20260905
SOURCE_PREFLIGHT_BOOTSTRAP_SEED = 20260904
DEMAND_REL_TOLERANCE = 1e-9
DEMAND_ABS_TOLERANCE = 1e-7
SOURCE_DEMAND_REL_TOLERANCE = 1e-12
PRODUCT_GAP_WARNING_PP = 5.0
INTERPRETATION = (
    "Simulation hypotheses only; no observed supplier performance or incident "
    "probability is inferred."
)

_IS_WINDOWS = os.name == "nt"
_JSON_REPLACE_MAX_ATTEMPTS = 8
_JSON_REPLACE_BACKOFF_SECONDS = 0.02

OFFICIAL_EXECUTION_MODE = "official_coarse_execute_candidate"
TEST_ONLY_EXECUTION_MODE = "test_only_injected_executor"
RUNTIME_DEPENDENCY_SCHEMA_VERSION = f"{PLAN_SCHEMA_VERSION}.runtime_dependencies.v1"
SHIPMENT_TRACE_SCHEMA_VERSION = "etudecas.v4_holdout_shipment_trace.v1"
SHIPMENT_LANE_CONTRACT_SCHEMA_VERSION = f"{SHIPMENT_TRACE_SCHEMA_VERSION}.lane_contract"
SHIPMENT_TRACE_COMPRESSION = "gzip_mtime_0_filename_empty_compresslevel_9"
SHIPMENT_TRACE_SOURCE_RELATIVE_PATH = "data/production_supplier_shipments_daily.csv"
SHIPMENT_TRACE_FIELDS = (
    "lane_id",
    "shipment_id",
    "risk_decision_day",
    "release_day",
    "arrival_day",
    "pulled_qty",
    "shipped_qty",
    "reliability",
    "lead_days",
    "uom",
)
SHIPMENT_TRACE_REFERENCE_FIELDS = frozenset(
    {
        "relative_path",
        "gzip_sha256",
        "trace_signature",
        "source_csv_sha256",
        "row_count",
        "uncompressed_bytes",
        "compression",
    }
)
CAMPAIGN_LANE_FIELDS = frozenset(
    {
        "lane_id",
        "supplier_id",
        "item_id",
        "dst_node_id",
        "edge_id",
        "target_product_id",
        "planned_lead_days",
    }
)

REPO_ROOT = Path(__file__).resolve().parents[3]
RUNTIME_DEPENDENCY_RELATIVE_PATHS = (
    "etudecas/__init__.py",
    "etudecas/case_config.py",
    "etudecas/prototypes/scan_2027_risk_control/__init__.py",
    "etudecas/prototypes/scan_2027_risk_control/calibration.py",
    "etudecas/prototypes/scan_2027_risk_control/core.py",
    "etudecas/prototypes/scan_2027_risk_control/decision.py",
    "etudecas/prototypes/scan_2027_risk_control/experiments.py",
    "etudecas/prototypes/scan_2027_risk_control/model.py",
    "etudecas/prototypes/scan_2027_risk_control/risk_mapping.py",
    "etudecas/prototypes/scan_2027_risk_control/supplier_balanced_product_delay_calibration.py",
    "etudecas/prototypes/scan_2027_risk_control/supplier_balanced_product_delay_multiseed_refinement_v4.py",
    "etudecas/prototypes/scan_2027_risk_control/supplier_service_landscape_campaign.py",
    "etudecas/prototypes/scan_2027_risk_control/supplier_service_regime_calibration_protocol.py",
    "etudecas/prototypes/scan_2027_risk_control/supplier_service_regime_calibration_runner.py",
    "etudecas/simulation/__init__.py",
    "etudecas/simulation/analysis/factory_nervousness.py",
    "etudecas/simulation/analysis_batch_common.py",
    "etudecas/simulation/engine/__init__.py",
    "etudecas/simulation/engine/api.py",
    "etudecas/simulation/engine/contracts.py",
    "etudecas/simulation/engine/control_probe.py",
    "etudecas/simulation/engine/control_provider.py",
    "etudecas/simulation/engine/control_provider_v2.py",
    "etudecas/simulation/engine/control_provider_v3.py",
    "etudecas/simulation/engine/control_schedule.py",
    "etudecas/simulation/engine/demand_perturbation.py",
    "etudecas/simulation/engine/run_first_simulation.py",
    "etudecas/simulation/initial_state_policy.py",
    "etudecas/simulation/lot_trace/__init__.py",
    "etudecas/simulation/lot_trace/campaigns.py",
    "etudecas/simulation/lot_trace/execution.py",
    "etudecas/simulation/lot_trace/indexes.py",
    "etudecas/simulation/lot_trace/io.py",
    "etudecas/simulation/lot_trace/payload.py",
    "etudecas/simulation/lot_trace/rules.py",
    "etudecas/simulation/lot_trace/schema.py",
    "etudecas/simulation/lot_trace/stock_context.py",
    "etudecas/simulation/lot_trace/view_model.py",
    "etudecas/simulation/result_paths.py",
    "etudecas/simulation/run_format/__init__.py",
    "etudecas/simulation/run_format/exporter.py",
    "etudecas/simulation/run_format/loader.py",
    "etudecas/simulation/run_format/schema.py",
    "etudecas/simulation/run_format/validator.py",
)
EXECUTOR_DEPENDENCY_RELATIVE_PATHS = {
    "supplier_balanced_product_delay_calibration.py": (
        "etudecas/prototypes/scan_2027_risk_control/"
        "supplier_balanced_product_delay_calibration.py"
    ),
    "supplier_service_landscape_campaign.py": (
        "etudecas/prototypes/scan_2027_risk_control/"
        "supplier_service_landscape_campaign.py"
    ),
    "supplier_service_regime_calibration_protocol.py": (
        "etudecas/prototypes/scan_2027_risk_control/"
        "supplier_service_regime_calibration_protocol.py"
    ),
    "supplier_service_regime_calibration_runner.py": (
        "etudecas/prototypes/scan_2027_risk_control/"
        "supplier_service_regime_calibration_runner.py"
    ),
}

CAMPAIGN_RUNTIME_FIELDS = frozenset(
    {
        "campaign_signature",
        "status",
        "created_at_utc",
        "completed_at_utc",
        "target_discovery_status",
        "target_registry",
        "target_registry_sha256",
        "target_registry_signature",
        "operating_point_preflight",
        "operating_point_preflight_sha256",
        "operating_point_preflight_signature",
        "operating_point_preflight_status",
        "target_discovery_completed_at_utc",
    }
)
V3_PLAN_SIGNED_FIELDS = (
    "schema_version",
    "status",
    "interpretation",
    "source",
    "source_hashes",
    "cohorts",
    "candidates",
    "candidate_design",
    "inventory",
    "cases",
    "expected_case_count",
    "new_case_count",
    "reused_case_count",
    "selection_contract",
    "holdout_contract",
    "execution_contract",
)

V4_EVIDENCE_FIELDS = frozenset(
    {
        "schema_version",
        "plan_signature",
        "stage",
        "candidate_key",
        "candidate_id",
        "target_group",
        "seed",
        "evidence_mode",
        "graph_sha256",
        "engine_sha256",
        "metrics",
        "source_evidence",
        "executor_proof",
        "shipment_trace",
        "valid",
        "created_at_utc",
        "evidence_signature",
    }
)

DEFAULT_ARTIFACT_ROOT = Path(r"C:\dev\lca-simu-pr40-validation-artifacts-20260726")
DEFAULT_SOURCE_CAMPAIGN_MANIFEST = (
    DEFAULT_ARTIFACT_ROOT
    / "supplier_operating_point_full_campaign_v2_20260904_v3"
    / "campaign_manifest.json"
)
DEFAULT_PLAN_OUTPUT = (
    DEFAULT_ARTIFACT_ROOT / "supplier_delay_multiseed_refinement_plan_20260905_v4"
)
DEFAULT_RUN_OUTPUT = (
    DEFAULT_ARTIFACT_ROOT / "supplier_delay_multiseed_refinement_run_20260905_v4"
)


class V4ProtocolError(ValueError):
    """Raised when a frozen scientific contract is incomplete or changed."""


@dataclass(frozen=True)
class Candidate:
    key: str
    candidate_id: str
    target_group: str
    offset_days_268091: float
    offset_days_268967: float
    evidence_mode: str
    source_operating_point_id: str = ""


@dataclass(frozen=True)
class ValidatedPlan:
    plan_dir: Path
    manifest: dict[str, Any]
    candidates: tuple[Candidate, ...]


Executor = Callable[..., Mapping[str, Any]]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def stable_sha256(payload: Any) -> str:
    raw = json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _runtime_dependency_inventory_from_worktree() -> dict[str, Any]:
    if (
        len(RUNTIME_DEPENDENCY_RELATIVE_PATHS) != 44
        or tuple(sorted(RUNTIME_DEPENDENCY_RELATIVE_PATHS))
        != RUNTIME_DEPENDENCY_RELATIVE_PATHS
    ):
        raise V4ProtocolError("V4 runtime dependency path inventory changed")
    files: list[dict[str, str]] = []
    for relative in RUNTIME_DEPENDENCY_RELATIVE_PATHS:
        path = (REPO_ROOT / relative).resolve()
        if not path.is_relative_to(REPO_ROOT) or not path.is_file():
            raise V4ProtocolError(f"Missing V4 runtime dependency: {relative}")
        files.append({"path": relative, "sha256": sha256_file(path)})
    unsigned: dict[str, Any] = {
        "schema_version": RUNTIME_DEPENDENCY_SCHEMA_VERSION,
        "file_count": len(files),
        "files": files,
    }
    return {
        **unsigned,
        "aggregate_sha256": stable_sha256(unsigned),
    }


def _validate_runtime_dependency_inventory(
    raw: Any,
) -> dict[str, Any]:
    if not isinstance(raw, Mapping):
        raise V4ProtocolError("V4 runtime dependency inventory is missing")
    inventory = dict(raw)
    if set(inventory) != {
        "schema_version",
        "file_count",
        "files",
        "aggregate_sha256",
    }:
        raise V4ProtocolError("V4 runtime dependency inventory fields changed")
    files = inventory.get("files")
    if not isinstance(files, list) or len(files) != 44:
        raise V4ProtocolError("V4 runtime dependency inventory must contain 44 files")
    expected_paths = list(RUNTIME_DEPENDENCY_RELATIVE_PATHS)
    actual_paths: list[str] = []
    for record in files:
        if not isinstance(record, Mapping) or set(record) != {"path", "sha256"}:
            raise V4ProtocolError("Invalid V4 runtime dependency record")
        relative = str(record.get("path") or "")
        digest = str(record.get("sha256") or "")
        if (
            not relative
            or Path(relative).is_absolute()
            or "\\" in relative
            or not re.fullmatch(r"[0-9a-f]{64}", digest)
        ):
            raise V4ProtocolError("Invalid V4 runtime dependency path or SHA-256")
        actual_paths.append(relative)
    unsigned = {
        "schema_version": RUNTIME_DEPENDENCY_SCHEMA_VERSION,
        "file_count": 44,
        "files": files,
    }
    if (
        inventory.get("schema_version") != RUNTIME_DEPENDENCY_SCHEMA_VERSION
        or inventory.get("file_count") != 44
        or actual_paths != expected_paths
        or len(actual_paths) != len(set(actual_paths))
        or inventory.get("aggregate_sha256") != stable_sha256(unsigned)
    ):
        raise V4ProtocolError("V4 runtime dependency inventory contract changed")
    return inventory


def _assert_runtime_dependencies_current(plan: ValidatedPlan) -> None:
    expected = _validate_runtime_dependency_inventory(
        plan.manifest.get("runtime_dependencies")
    )
    actual = _runtime_dependency_inventory_from_worktree()
    if actual == expected:
        return
    expected_by_path = {
        str(row["path"]): str(row["sha256"]) for row in expected["files"]
    }
    actual_by_path = {str(row["path"]): str(row["sha256"]) for row in actual["files"]}
    changed = [
        path
        for path in RUNTIME_DEPENDENCY_RELATIVE_PATHS
        if expected_by_path.get(path) != actual_by_path.get(path)
    ]
    detail = ", ".join(changed[:3]) or "aggregate digest"
    raise V4ProtocolError(f"V4 runtime dependency changed after plan freeze: {detail}")


def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise V4ProtocolError(f"Invalid JSON source: {path}") from exc
    if not isinstance(payload, dict):
        raise V4ProtocolError(f"Expected a JSON object: {path}")
    return payload


def _write_bytes(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp-{os.getpid()}-{uuid.uuid4().hex}")
    error_in_flight = False
    try:
        temporary.write_bytes(payload)
        for attempt in range(_JSON_REPLACE_MAX_ATTEMPTS):
            try:
                os.replace(temporary, path)
                break
            except PermissionError:
                if not _IS_WINDOWS or attempt + 1 == _JSON_REPLACE_MAX_ATTEMPTS:
                    raise
                time.sleep(_JSON_REPLACE_BACKOFF_SECONDS * (2**attempt))
    except BaseException:
        error_in_flight = True
        raise
    finally:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass
        except OSError:
            if not error_in_flight:
                raise


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    serialized = (
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")
    _write_bytes(path, serialized)


def generate_holdout_seeds(
    domain: str = HOLDOUT_SEED_DOMAIN, count: int = HOLDOUT_SEED_COUNT
) -> tuple[int, ...]:
    """Generate distinct positive 31-bit seeds from a domain-separated SHA-256."""

    if not domain or count < 1:
        raise V4ProtocolError("Seed domain and positive count are required")
    accepted: list[int] = []
    counter = 1
    while len(accepted) < count:
        message = f"{domain}|{counter:02d}".encode("utf-8")
        digest = hashlib.sha256(message).digest()
        value = int.from_bytes(digest[:4], byteorder="little", signed=False)
        seed = (value % 2_147_483_646) + 1
        if seed != 0 and seed not in accepted:
            accepted.append(seed)
        counter += 1
    return tuple(accepted)


def derive_domain_seed(domain: str, counter: int) -> tuple[int, str]:
    if not domain or counter < 1:
        raise V4ProtocolError("Positive domain-separated seed counter is required")
    message = f"{domain}|{counter:02d}".encode("utf-8")
    digest = hashlib.sha256(message).digest()
    value = (int.from_bytes(digest[:4], "little") % 2_147_483_646) + 1
    return value, digest.hex()


def seed_csv_sha256(seeds: Sequence[int]) -> str:
    return hashlib.sha256(
        ",".join(str(int(seed)) for seed in seeds).encode("utf-8")
    ).hexdigest()


def _resolve_declared_path(manifest_path: Path, raw: Any) -> Path:
    path = Path(str(raw or ""))
    if not path.is_absolute():
        path = manifest_path.parent / path
    return path.resolve()


def _require_hash(path: Path, expected: Any, label: str) -> str:
    if not path.is_file():
        raise V4ProtocolError(f"Missing {label}: {path}")
    actual = sha256_file(path)
    if actual != str(expected or ""):
        raise V4ProtocolError(f"Changed {label}: {path}")
    return actual


def _verify_self_signature(
    payload: Mapping[str, Any], signature_field: str, label: str
) -> str:
    unsigned = dict(payload)
    signature = str(unsigned.pop(signature_field, ""))
    if len(signature) != 64 or signature != stable_sha256(unsigned):
        raise V4ProtocolError(f"Invalid {label} signature")
    return signature


def _state_by_id(manifest: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    states = manifest.get("states")
    if not isinstance(states, list):
        raise V4ProtocolError("V3 campaign states are missing")
    result = {
        str(row.get("operating_point_id") or ""): dict(row)
        for row in states
        if isinstance(row, Mapping)
    }
    if set(result) != set(TARGETS) or len(result) != 3:
        raise V4ProtocolError("V3 campaign must expose exactly op100/op93/op80")
    return result


def _campaign_lanes(manifest: Mapping[str, Any]) -> list[dict[str, Any]]:
    raw_lanes = manifest.get("lanes")
    if not isinstance(raw_lanes, list) or len(raw_lanes) != 18:
        raise V4ProtocolError("V3 campaign must contain exactly 18 signed lanes")
    lanes: list[dict[str, Any]] = []
    for raw in raw_lanes:
        if not isinstance(raw, Mapping) or set(raw) != CAMPAIGN_LANE_FIELDS:
            raise V4ProtocolError("V3 campaign lane fields changed")
        target_product_id = str(raw.get("target_product_id") or "")
        lane = {
            "lane_id": str(raw.get("lane_id") or ""),
            "supplier_id": str(raw.get("supplier_id") or ""),
            "item_id": str(raw.get("item_id") or ""),
            "dst_node_id": str(raw.get("dst_node_id") or ""),
            "edge_id": str(raw.get("edge_id") or ""),
            "target_product_id": target_product_id,
            "planned_lead_days": _finite_nonnegative(
                raw.get("planned_lead_days"), "V3 campaign planned lead"
            ),
        }
        if (
            not all(str(lane[field]) for field in CAMPAIGN_LANE_FIELDS)
            or target_product_id not in PRODUCTS
            or lane["dst_node_id"] != PRODUCT_FACTORY[target_product_id]
            or lane["planned_lead_days"] <= 0.0
        ):
            raise V4ProtocolError("V3 campaign lane identity is incomplete")
        lanes.append(lane)
    lanes.sort(key=lambda lane: str(lane["lane_id"]))
    if (
        len({str(lane["lane_id"]) for lane in lanes}) != 18
        or len({str(lane["edge_id"]) for lane in lanes}) != 18
        or len(
            {
                (
                    str(lane["supplier_id"]),
                    str(lane["item_id"]),
                    str(lane["dst_node_id"]),
                )
                for lane in lanes
            }
        )
        != 18
    ):
        raise V4ProtocolError("V3 campaign lane identities are not unique")
    return lanes


def _pooled_state_metrics(
    rows: Sequence[Mapping[str, float]],
) -> dict[str, Any]:
    if len(rows) != len(DEVELOPMENT_SEEDS):
        raise V4ProtocolError("Source state does not contain exactly 30 paired rows")
    pooled: dict[str, float] = {}
    per_seed: dict[str, list[float]] = {}
    for name, demand_field, on_due_field in (
        ("global", "demand_qty_global", "on_due_qty_global"),
        ("268091", "demand_qty_268091", "on_due_qty_268091"),
        ("268967", "demand_qty_268967", "on_due_qty_268967"),
    ):
        demand = sum(float(row[demand_field]) for row in rows)
        if demand <= 0.0:
            raise V4ProtocolError("Source state has no positive demand")
        pooled[name] = sum(float(row[on_due_field]) for row in rows) / demand
        per_seed[name] = [
            float(row[on_due_field]) / float(row[demand_field]) for row in rows
        ]
    leave_one_out_global = []
    for omitted in range(len(rows)):
        kept = [row for index, row in enumerate(rows) if index != omitted]
        demand = sum(float(row["demand_qty_global"]) for row in kept)
        on_due = sum(float(row["on_due_qty_global"]) for row in kept)
        leave_one_out_global.append(on_due / demand)
    return {
        "pooled": pooled,
        "per_seed": per_seed,
        "median_global": median(per_seed["global"]),
        "leave_one_out_global": leave_one_out_global,
    }


def _validate_source_preflight_recomputation(
    preflight: Mapping[str, Any],
    evidence: Mapping[tuple[str, int], Mapping[str, float]],
) -> dict[str, dict[str, bool]]:
    """Recompute the V3 acceptance inputs from all 90 acceptance proofs."""

    bootstrap = preflight.get("bootstrap") or {}
    if bootstrap != {
        "method": "paired_common_seed_resampling",
        "replicates": BOOTSTRAP_REPLICATES,
        "seed": SOURCE_PREFLIGHT_BOOTSTRAP_SEED,
    }:
        raise V4ProtocolError("V3 preflight bootstrap contract changed")
    summaries = {
        point_id: _pooled_state_metrics(
            [evidence[(point_id, seed)] for seed in DEVELOPMENT_SEEDS]
        )
        for point_id in TARGETS
    }
    rows = {
        str(row.get("operating_point_id") or ""): dict(row)
        for row in preflight.get("states") or []
        if isinstance(row, Mapping)
    }
    if set(rows) != set(TARGETS) or len(rows) != 3:
        raise V4ProtocolError("V3 preflight state decisions are incomplete")

    individually_accepted: dict[str, bool] = {}
    for point_id, summary in summaries.items():
        row = rows[point_id]
        pooled = summary["pooled"]
        reported = {
            "global": row.get("service_global_ratio_of_sums_pct"),
            "268091": row.get("service_268091_ratio_of_sums_pct"),
            "268967": row.get("service_268967_ratio_of_sums_pct"),
            "median_global": row.get("service_global_seed_median_pct"),
        }
        recomputed = {
            "global": 100.0 * pooled["global"],
            "268091": 100.0 * pooled["268091"],
            "268967": 100.0 * pooled["268967"],
            "median_global": 100.0 * summary["median_global"],
        }
        for name, expected in recomputed.items():
            try:
                actual = float(reported[name])
            except (TypeError, ValueError) as exc:
                raise V4ProtocolError("V3 preflight aggregate is incomplete") from exc
            if not math.isclose(actual, expected, rel_tol=1e-12, abs_tol=1e-7):
                raise V4ProtocolError(
                    f"V3 preflight aggregate differs from evidence: {point_id}/{name}"
                )
        if point_id == "op_100":
            accepted = (
                REFERENCE_MINIMUM <= pooled["global"] <= 1.0 + 1e-9
                and REFERENCE_MINIMUM <= summary["median_global"] <= 1.0 + 1e-9
                and all(
                    REFERENCE_MINIMUM <= pooled[product] <= 1.0 + 1e-9
                    for product in PRODUCTS
                )
            )
        else:
            lower, upper = OUTER_BANDS[point_id]
            accepted = (
                lower <= pooled["global"] <= upper
                and lower <= summary["median_global"] <= upper
                and all(
                    pooled[product] < NON_SATURATION_LIMIT - 1e-12
                    for product in PRODUCTS
                )
            )
        individually_accepted[point_id] = accepted

    pooled_order = {
        name: summaries["op_100"]["pooled"][name]
        > summaries["op_93"]["pooled"][name]
        > summaries["op_80"]["pooled"][name]
        for name in ("global", *PRODUCTS)
    }
    joint = sum(
        all(
            summaries["op_100"]["per_seed"][name][index]
            > summaries["op_93"]["per_seed"][name][index]
            > summaries["op_80"]["per_seed"][name][index]
            for name in ("global", *PRODUCTS)
        )
        for index in range(len(DEVELOPMENT_SEEDS))
    )
    ordering_accepted = all(pooled_order.values()) and joint >= MIN_ORDERED_SEEDS
    if (
        preflight.get("pooled_ordering_by_measure") != pooled_order
        or preflight.get("ordering_valid") is not all(pooled_order.values())
        or int(preflight.get("joint_seed_order_count") or -1) != joint
        or preflight.get("seed_ordering_valid") is not (joint >= MIN_ORDERED_SEEDS)
        or int(preflight.get("joint_seed_order_required") or -1) != MIN_ORDERED_SEEDS
    ):
        raise V4ProtocolError("V3 preflight ordering differs from its 90 proofs")
    reported_acceptance = {
        point_id: accepted and ordering_accepted
        for point_id, accepted in individually_accepted.items()
    }
    if any(
        bool(rows[key].get("accepted")) != value
        for key, value in reported_acceptance.items()
    ):
        raise V4ProtocolError("V3 preflight acceptance differs from its 90 proofs")
    if (
        individually_accepted["op_100"] is not True
        or individually_accepted["op_93"] is not False
    ):
        raise V4ProtocolError(
            "V4 requires individually valid V3 op100 and individually rejected op93"
        )
    development_inner_accepted = dict(individually_accepted)
    for point_id in ("op_93", "op_80"):
        summary = summaries[point_id]
        lower, upper = DEVELOPMENT_INNER_BANDS[point_id]
        development_inner_accepted[point_id] = (
            lower <= summary["pooled"]["global"] <= upper
            and lower <= summary["median_global"] <= upper
            and all(
                summary["pooled"][product] < NON_SATURATION_LIMIT - 1e-12
                for product in PRODUCTS
            )
            and all(
                OUTER_BANDS[point_id][0] <= value <= OUTER_BANDS[point_id][1]
                for value in summary["leave_one_out_global"]
            )
        )
    return {
        "individual_outer": individually_accepted,
        "development_inner": development_inner_accepted,
        "reported_after_ordering": reported_acceptance,
    }


def validate_rejected_v3_campaign(manifest_path: Path) -> dict[str, Any]:
    """Validate the signed rejection and every directly referenced V3 source."""

    manifest_path = manifest_path.resolve()
    manifest = _read_json(manifest_path)
    campaign_signature = str(manifest.get("campaign_signature") or "")
    signed_design = {
        key: value
        for key, value in manifest.items()
        if key not in CAMPAIGN_RUNTIME_FIELDS
    }
    if (
        manifest.get("schema_version") != V3_CAMPAIGN_SCHEMA_VERSION
        or len(campaign_signature) != 64
        or campaign_signature != stable_sha256(signed_design)
        or manifest.get("operating_points_producer") != "v3_refinement"
        or manifest.get("operating_points_schema_version") != V3_POINTS_SCHEMA_VERSION
        or manifest.get("operating_points_input_status") != V3_POINTS_STATUS
        or manifest.get("target_discovery_status") != "rejected"
        or manifest.get("operating_point_preflight_status") != V3_REJECTED_STATUS
        or manifest.get("target_registry") not in (None, "")
        or manifest.get("target_registry_sha256") not in (None, "")
        or manifest.get("target_registry_signature") not in (None, "")
        or tuple(int(value) for value in manifest.get("seeds") or ())
        != DEVELOPMENT_SEEDS
    ):
        raise V4ProtocolError("Source is not the required signed rejected V3 campaign")
    cohorts = manifest.get("operating_points_cohorts") or {}
    if (
        tuple(cohorts.get("design") or ()) != SOURCE_DESIGN_SEEDS
        or tuple(cohorts.get("calibration") or ()) != SOURCE_CALIBRATION_SEEDS
        or tuple(cohorts.get("holdout_sealed") or ()) != DEVELOPMENT_SEEDS
    ):
        raise V4ProtocolError("V3 source cohorts changed")

    preflight_path = _resolve_declared_path(
        manifest_path, manifest.get("operating_point_preflight")
    )
    preflight_hash = _require_hash(
        preflight_path,
        manifest.get("operating_point_preflight_sha256"),
        "V3 rejected preflight",
    )
    preflight = _read_json(preflight_path)
    preflight_signature = _verify_self_signature(
        preflight, "preflight_signature", "V3 preflight"
    )
    if (
        preflight.get("schema_version") != V3_PREFLIGHT_SCHEMA_VERSION
        or preflight.get("status") != V3_REJECTED_STATUS
        or preflight.get("campaign_signature") != campaign_signature
        or preflight_signature
        != str(manifest.get("operating_point_preflight_signature") or "")
        or tuple(preflight.get("campaign_seeds") or ()) != DEVELOPMENT_SEEDS
        or preflight.get("holdout_used_once_without_retuning") is not True
        or preflight.get("no_incident_probe_before_holdout_acceptance") is not True
    ):
        raise V4ProtocolError("V3 rejection/preflight contract changed")

    points_path = _resolve_declared_path(
        manifest_path, manifest.get("operating_points_source")
    )
    points_hash = _require_hash(
        points_path, manifest.get("operating_points_source_sha256"), "V3 points"
    )
    points = _read_json(points_path)
    points_signature = _verify_self_signature(
        points, "artifact_signature", "V3 selected points"
    )
    if (
        points.get("schema_version") != V3_POINTS_SCHEMA_VERSION
        or points.get("status") != V3_POINTS_STATUS
        or points_signature
        != str(manifest.get("operating_points_artifact_signature") or "")
    ):
        raise V4ProtocolError("V3 selected points changed")

    selection_path = _resolve_declared_path(
        manifest_path, manifest.get("operating_points_selection")
    )
    selection_hash = _require_hash(
        selection_path,
        manifest.get("operating_points_selection_sha256"),
        "V3 selection",
    )
    selection = _read_json(selection_path)
    selection_signature = _verify_self_signature(
        selection, "selection_signature", "V3 selection"
    )
    if selection_signature != str(
        manifest.get("operating_points_selection_signature") or ""
    ):
        raise V4ProtocolError("V3 selection signature changed")

    v3_plan_path = _resolve_declared_path(
        manifest_path, manifest.get("operating_points_calibration_plan")
    )
    v3_plan_hash = _require_hash(
        v3_plan_path,
        manifest.get("operating_points_calibration_plan_sha256"),
        "V3 refinement plan",
    )
    v3_plan = _read_json(v3_plan_path)
    plan_signature = str(v3_plan.get("plan_signature") or "")
    plan_unsigned = {key: v3_plan.get(key) for key in V3_PLAN_SIGNED_FIELDS}
    if (
        v3_plan.get("schema_version") != V3_PLAN_SCHEMA_VERSION
        or plan_signature != stable_sha256(plan_unsigned)
        or plan_signature
        != str(manifest.get("operating_points_calibration_plan_signature") or "")
    ):
        raise V4ProtocolError("V3 refinement plan signature changed")
    campaign_lanes = _campaign_lanes(manifest)
    plan_lane_scope = _base_lane_scope(v3_plan)
    plan_lanes_by_edge = {
        str(lane["edge_id"]): {
            "supplier_id": str(lane["supplier_id"]),
            "item_id": str(lane["item_id"]),
            "dst_node_id": str(lane["dst_node_id"]),
            "target_product_id": product,
        }
        for product, lanes in plan_lane_scope.items()
        for lane in lanes
    }
    campaign_lanes_by_edge = {
        str(lane["edge_id"]): {
            "supplier_id": str(lane["supplier_id"]),
            "item_id": str(lane["item_id"]),
            "dst_node_id": str(lane["dst_node_id"]),
            "target_product_id": str(lane["target_product_id"]),
        }
        for lane in campaign_lanes
    }
    if campaign_lanes_by_edge != plan_lanes_by_edge:
        raise V4ProtocolError("V3 campaign lanes differ from the signed V3 plan")

    direct_files: dict[str, dict[str, str]] = {}
    for key, hash_key in (
        ("engine", "engine_sha256"),
        ("engine_profile", "engine_profile_sha256"),
        ("runner", "runner_sha256"),
    ):
        path = _resolve_declared_path(manifest_path, manifest.get(key))
        digest = _require_hash(path, manifest.get(hash_key), f"V3 {key}")
        direct_files[key] = {"path": str(path), "sha256": digest}

    states = _state_by_id(manifest)
    state_sources: dict[str, dict[str, str]] = {}
    for point_id, state in states.items():
        graph = _resolve_declared_path(manifest_path, state.get("graph"))
        digest = _require_hash(graph, state.get("graph_sha256"), f"V3 {point_id} graph")
        state_sources[point_id] = {"path": str(graph), "sha256": digest}

    progress_path = manifest_path.parent / "target_discovery" / "progress.json"
    progress = _read_json(progress_path)
    if (
        progress.get("schema_version")
        != f"{V3_CAMPAIGN_SCHEMA_VERSION}.target_discovery.progress.v1"
        or progress.get("campaign_signature") != campaign_signature
        or progress.get("status") != "failed_operating_point_preflight"
        or int(progress.get("planned") or -1) != 93
        or int(progress.get("completed") or -1) != 93
        or int(progress.get("failed", -1)) != 0
        or int(progress.get("running", -1)) != 0
        or int(progress.get("design_baselines_completed") or -1) != 3
        or int(progress.get("holdout_baselines_completed") or -1) != 90
        or progress.get("incident_probes_started") is not False
    ):
        raise V4ProtocolError("V3 target-discovery rejection progress is not final")

    discovery_hashes: dict[str, str] = {}
    discovery_metrics: dict[tuple[str, int], dict[str, float]] = {}
    discovery_seeds = (*SOURCE_DESIGN_SEEDS, *DEVELOPMENT_SEEDS)
    evidence_dir = manifest_path.parent / "target_discovery" / "evidence"
    expected_evidence_names = {
        f"{point_id}__target_discovery__seed_{seed}.json"
        for point_id in TARGETS
        for seed in discovery_seeds
    }
    actual_evidence_names = {
        path.name for path in evidence_dir.glob("*.json") if path.is_file()
    }
    if actual_evidence_names != expected_evidence_names:
        raise V4ProtocolError("V3 target-discovery JSON inventory is not exactly 93")
    if (manifest_path.parent / "target_discovery" / "target_registry.json").exists():
        raise V4ProtocolError(
            "Rejected V3 source unexpectedly contains a target registry"
        )
    for point_id in TARGETS:
        state = states[point_id]
        for seed in discovery_seeds:
            key = f"{point_id}__target_discovery__seed_{seed}"
            path = evidence_dir / f"{key}.json"
            payload = _read_json(path)
            _verify_self_signature(
                payload, "evidence_signature", f"V3 discovery evidence {key}"
            )
            expected_discovery = stable_sha256(
                {
                    "campaign_signature": campaign_signature,
                    "engine_sha256": manifest["engine_sha256"],
                    "engine_profile_sha256": manifest["engine_profile_sha256"],
                    "point_id": point_id,
                    "graph_sha256": state["graph_sha256"],
                    "seed": seed,
                    "simulation_days": SERVICE_DAYS,
                    "purpose": "cross_state_42d_target_discovery",
                }
            )
            if (
                payload.get("schema_version")
                != f"{V3_CAMPAIGN_SCHEMA_VERSION}.target_discovery.case.v1"
                or payload.get("campaign_signature") != campaign_signature
                or payload.get("engine_sha256") != manifest["engine_sha256"]
                or payload.get("operating_point_id") != point_id
                or int(payload.get("seed") or -1) != seed
                or int(payload.get("simulation_days") or -1) != SERVICE_DAYS
                or payload.get("discovery_signature") != expected_discovery
            ):
                raise V4ProtocolError(f"Invalid V3 discovery evidence: {key}")
            discovery_metrics[(point_id, seed)] = _normalize_metrics(
                payload.get("state_service_metrics") or {}
            )
            discovery_hashes[key] = sha256_file(path)
    for seed in DEVELOPMENT_SEEDS:
        reference = discovery_metrics[("op_100", seed)]
        for point_id in ("op_93", "op_80"):
            candidate = discovery_metrics[(point_id, seed)]
            for product in PRODUCTS:
                field = f"demand_qty_{product}"
                if not math.isclose(
                    reference[field],
                    candidate[field],
                    rel_tol=SOURCE_DEMAND_REL_TOLERANCE,
                    abs_tol=DEMAND_ABS_TOLERANCE,
                ):
                    raise V4ProtocolError(
                        f"V3 paired demand changed for {point_id}/seed {seed}/{product}"
                    )

    preflight_state_acceptance = _validate_source_preflight_recomputation(
        preflight, discovery_metrics
    )

    return {
        "campaign_manifest": {
            "path": str(manifest_path),
            "sha256": sha256_file(manifest_path),
            "campaign_signature": campaign_signature,
        },
        "preflight": {
            "path": str(preflight_path),
            "sha256": preflight_hash,
            "preflight_signature": preflight_signature,
            "status": V3_REJECTED_STATUS,
        },
        "target_discovery_progress": {
            "path": str(progress_path.resolve()),
            "sha256": sha256_file(progress_path),
            "status": "failed_operating_point_preflight",
            "incident_probes_started": False,
        },
        "target_discovery_evidence": {
            "case_count": len(discovery_hashes),
            "acceptance_case_count": len(TARGETS) * len(DEVELOPMENT_SEEDS),
            "design_case_count": len(TARGETS) * len(SOURCE_DESIGN_SEEDS),
            "sha256_by_case": discovery_hashes,
        },
        "selected_points": {
            "path": str(points_path),
            "sha256": points_hash,
            "artifact_signature": points_signature,
        },
        "selection": {
            "path": str(selection_path),
            "sha256": selection_hash,
            "selection_signature": selection_signature,
        },
        "v3_plan": {
            "path": str(v3_plan_path),
            "sha256": v3_plan_hash,
            "plan_signature": plan_signature,
        },
        "direct_files": direct_files,
        "state_sources": state_sources,
        "lanes": campaign_lanes,
        "preflight_state_acceptance": preflight_state_acceptance,
    }


def _validate_op80_decision(
    path: Path, source: Mapping[str, Any]
) -> tuple[dict[str, Any], tuple[Candidate, ...]]:
    path = path.resolve()
    decision = _read_json(path)
    signature = _verify_self_signature(decision, "artifact_signature", "op80 decision")
    common = {
        "schema_version",
        "mode",
        "source_campaign_signature",
        "source_preflight_signature",
        "rationale",
        "artifact_signature",
    }
    if (
        decision.get("schema_version") != OP80_DECISION_SCHEMA_VERSION
        or decision.get("source_campaign_signature")
        != source["campaign_manifest"]["campaign_signature"]
        or decision.get("source_preflight_signature")
        != source["preflight"]["preflight_signature"]
        or not isinstance(decision.get("rationale"), str)
        or not str(decision.get("rationale") or "").strip()
    ):
        raise V4ProtocolError("op80 decision is not bound to the rejected V3 source")
    op80_passed = bool(
        source["preflight_state_acceptance"]["development_inner"]["op_80"]
    )
    mode = str(decision.get("mode") or "")
    if mode == "keep":
        if set(decision) != common | {"keep"} or not op80_passed:
            raise V4ProtocolError(
                "op80 keep is allowed only when V3 op80 passes the V4 inner contract"
            )
        keep = decision.get("keep")
        if keep != {"source_operating_point_id": "op_80"}:
            raise V4ProtocolError("Invalid op80 keep decision")
        candidates = (
            Candidate(
                "op80_source_16p5_94",
                "v4_op80_source_16p5_94",
                "op_80",
                16.5,
                94.0,
                "reuse_source_development",
                "op_80",
            ),
        )
    elif mode == "candidates":
        if set(decision) != common | {"candidates"} or op80_passed:
            raise V4ProtocolError(
                "op80 candidates are required only when V3 op80 fails the V4 inner contract"
            )
        rows = decision.get("candidates")
        expected_rows = [
            {
                "key": key,
                "offset_days_268091": left,
                "offset_days_268967": right,
            }
            for key, left, right in OP80_GRID
        ]
        if rows != expected_rows:
            raise V4ProtocolError(
                "The explicit op80 grid must contain exactly the four frozen V4 points"
            )
        built: list[Candidate] = [
            Candidate(
                "op80_source_16p5_94",
                "v4_op80_source_16p5_94",
                "op_80",
                16.5,
                94.0,
                "reuse_source_development",
                "op_80",
            )
        ]
        seen_coordinates = {(16.5, 94.0)}
        for row in rows:
            if not isinstance(row, Mapping) or set(row) != {
                "key",
                "offset_days_268091",
                "offset_days_268967",
            }:
                raise V4ProtocolError("Invalid or mixed op80 candidate definition")
            key = str(row.get("key") or "")
            left = _finite_nonnegative(row.get("offset_days_268091"), "op80 offset")
            right = _finite_nonnegative(row.get("offset_days_268967"), "op80 offset")
            coordinates = (left, right)
            if not re.fullmatch(r"op80_v4_[a-z0-9_]{1,64}", key) or any(
                candidate.key == key for candidate in built
            ):
                raise V4ProtocolError("Duplicate or empty op80 candidate key")
            if coordinates in seen_coordinates:
                raise V4ProtocolError("Duplicate op80 candidate coordinate")
            seen_coordinates.add(coordinates)
            built.append(
                Candidate(
                    key,
                    f"v4_{key}",
                    "op_80",
                    left,
                    right,
                    "execute",
                )
            )
        candidates = tuple(built)
    else:
        raise V4ProtocolError("op80 decision mode must be exactly keep or candidates")
    return (
        {
            "path": str(path),
            "sha256": sha256_file(path),
            "artifact_signature": signature,
            "payload": decision,
        },
        candidates,
    )


def write_op80_decision(
    output_path: Path,
    *,
    source_campaign_manifest: Path = DEFAULT_SOURCE_CAMPAIGN_MANIFEST,
    mode: str,
    rationale: str,
    candidates_json: Path | None = None,
) -> Path:
    """Create the signed explicit op80 decision; never execute the engine."""

    output_path = output_path.resolve()
    if output_path.exists():
        raise FileExistsError(f"Refusing to overwrite op80 decision: {output_path}")
    source = validate_rejected_v3_campaign(source_campaign_manifest)
    if _paths_overlap(
        output_path, Path(source["campaign_manifest"]["path"]).parent
    ) or _paths_overlap(output_path, Path(source["v3_plan"]["path"]).parent):
        raise V4ProtocolError("op80 decision path overlaps a protected V3 source")
    inner_passed = bool(
        source["preflight_state_acceptance"]["development_inner"]["op_80"]
    )
    if not rationale.strip():
        raise V4ProtocolError("A non-empty op80 decision rationale is required")
    unsigned: dict[str, Any] = {
        "schema_version": OP80_DECISION_SCHEMA_VERSION,
        "mode": mode,
        "source_campaign_signature": source["campaign_manifest"]["campaign_signature"],
        "source_preflight_signature": source["preflight"]["preflight_signature"],
        "rationale": rationale.strip(),
    }
    if mode == "keep":
        if not inner_passed or candidates_json is not None:
            raise V4ProtocolError(
                "op80 keep requires the recomputed V4 inner band and no candidate grid"
            )
        unsigned["keep"] = {"source_operating_point_id": "op_80"}
    elif mode == "candidates":
        if inner_passed or candidates_json is None:
            raise V4ProtocolError(
                "op80 candidates require an inner-band failure and an explicit grid"
            )
        try:
            grid_payload = json.loads(candidates_json.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise V4ProtocolError("Invalid op80 candidate-grid JSON") from exc
        if not isinstance(grid_payload, dict) or set(grid_payload) != {"candidates"}:
            raise V4ProtocolError(
                "op80 candidate-grid JSON must contain exactly a candidates list"
            )
        unsigned["candidates"] = grid_payload["candidates"]
    else:
        raise V4ProtocolError("op80 decision mode must be exactly keep or candidates")
    payload = {**unsigned, "artifact_signature": stable_sha256(unsigned)}
    temporary = output_path.with_name(f".{output_path.name}.building-{os.getpid()}")
    if temporary.exists():
        raise FileExistsError(f"Temporary op80 decision already exists: {temporary}")
    try:
        _write_json(temporary, payload)
        _, op80 = _validate_op80_decision(temporary, source)
        _all_candidates(op80)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        os.replace(temporary, output_path)
    finally:
        if temporary.exists():
            temporary.unlink()
    return output_path


def _finite_nonnegative(value: Any, label: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise V4ProtocolError(f"Invalid {label}") from exc
    if not math.isfinite(number) or number < 0.0:
        raise V4ProtocolError(f"Invalid {label}")
    return number


def _candidate_payload(candidate: Candidate) -> dict[str, Any]:
    return {
        "key": candidate.key,
        "candidate_id": candidate.candidate_id,
        "target_group": candidate.target_group,
        "offset_days_268091": candidate.offset_days_268091,
        "offset_days_268967": candidate.offset_days_268967,
        "evidence_mode": candidate.evidence_mode,
        "source_operating_point_id": candidate.source_operating_point_id,
    }


def _all_candidates(op80: Sequence[Candidate]) -> tuple[Candidate, ...]:
    candidates = [
        Candidate(
            "op100_source",
            "v4_op100_source",
            "op_100",
            0.0,
            0.0,
            "reuse_source_development",
            "op_100",
        )
    ]
    candidates.extend(
        Candidate(
            key,
            f"v4_{key}",
            "op_93",
            left,
            right,
            mode,
            "op_93" if mode.startswith("reuse") else "",
        )
        for key, left, right, mode in OP93_GRID
    )
    candidates.extend(op80)
    keys = [candidate.key for candidate in candidates]
    if len(keys) != len(set(keys)):
        raise V4ProtocolError("Candidate keys are not unique")
    return tuple(candidates)


def _edge_index(graph: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for edge in graph.get("edges") or []:
        if not isinstance(edge, dict):
            raise V4ProtocolError("Invalid graph edge")
        edge_id = str(edge.get("id") or "")
        if not edge_id or edge_id in result:
            raise V4ProtocolError("Missing or duplicate graph edge id")
        result[edge_id] = edge
    return result


def _base_lane_scope(
    v3_plan: Mapping[str, Any],
) -> dict[str, tuple[dict[str, str], ...]]:
    inventory = v3_plan.get("inventory") or {}
    reference = inventory.get("op100_reference") or {}
    changes = reference.get("changes")
    if not isinstance(changes, list) or not changes:
        raise V4ProtocolError("V3 op100 lane-change ledger is missing")
    grouped: dict[str, list[dict[str, str]]] = {product: [] for product in PRODUCTS}
    seen_edge_ids: set[str] = set()
    for row in changes:
        if not isinstance(row, Mapping):
            raise V4ProtocolError("Invalid V3 lane-change row")
        product = str(row.get("target_product_id") or "")
        if product not in grouped:
            raise V4ProtocolError("Unexpected product in V3 lane scope")
        lane = {
            "edge_id": str(row.get("edge_id") or ""),
            "supplier_id": str(row.get("supplier_id") or ""),
            "item_id": str(row.get("item_id") or ""),
            "dst_node_id": str(row.get("factory_id") or ""),
        }
        if not all(lane.values()) or lane["edge_id"] in seen_edge_ids:
            raise V4ProtocolError("V3 lane scope has an empty or duplicate edge")
        seen_edge_ids.add(lane["edge_id"])
        grouped[product].append(lane)
    if any(not rows for rows in grouped.values()):
        raise V4ProtocolError("V3 lane scope is incomplete")
    return {key: tuple(value) for key, value in grouped.items()}


def _v3_source_changes(
    v3_plan: Mapping[str, Any], candidate: Candidate
) -> list[dict[str, Any]]:
    inventory_key = {
        "op_100": "op100_reference",
        "op_93": "op93_refine_7_81",
        "op_80": "op80_refine_v3_16p5_94",
    }.get(candidate.source_operating_point_id)
    item = (v3_plan.get("inventory") or {}).get(inventory_key or "") or {}
    changes = item.get("changes")
    if not isinstance(changes, list) or not changes:
        raise V4ProtocolError("V3 source change ledger is missing")
    offsets = {
        "268091": candidate.offset_days_268091,
        "268967": candidate.offset_days_268967,
    }
    for row in changes:
        if not isinstance(row, Mapping):
            raise V4ProtocolError("V3 source change ledger row is invalid")
        product = str(row.get("target_product_id") or "")
        if product not in offsets or not math.isclose(
            float(row.get("offset_days")), offsets[product], abs_tol=1e-12
        ):
            raise V4ProtocolError("V3 source anchor offsets changed")
    return [dict(row) for row in changes]


def _apply_offsets(
    base_graph: Mapping[str, Any],
    lanes_by_product: Mapping[str, Sequence[Mapping[str, str]]],
    left: float,
    right: float,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    offsets = {"268091": left, "268967": right}
    graph = copy.deepcopy(base_graph)
    edges = _edge_index(graph)
    changes: list[dict[str, Any]] = []
    for product in PRODUCTS:
        if not lanes_by_product.get(product):
            raise V4ProtocolError(f"No V3 lanes for product {product}")
        for lane in lanes_by_product[product]:
            edge = edges.get(str(lane["edge_id"]))
            if edge is None:
                raise V4ProtocolError(
                    f"V3 lane absent from base graph: {lane['edge_id']}"
                )
            if (
                str(edge.get("from") or "") != lane["supplier_id"]
                or str(edge.get("to") or "") != lane["dst_node_id"]
                or lane["item_id"]
                not in {str(value) for value in edge.get("items") or []}
                or lane["dst_node_id"] != PRODUCT_FACTORY[product]
            ):
                raise V4ProtocolError(f"V3 lane identity changed: {lane['edge_id']}")
            lead = edge.get("lead_time")
            limit = edge.get("delay_step_limit")
            if not isinstance(lead, dict) or not isinstance(limit, dict):
                raise V4ProtocolError(f"Missing lead metadata: {lane['edge_id']}")
            reference_lead = _finite_nonnegative(lead.get("mean"), "reference lead")
            reference_limit = _finite_nonnegative(limit.get("value"), "reference limit")
            if reference_lead <= 0:
                raise V4ProtocolError("Reference lead must be positive")
            candidate_lead = reference_lead + offsets[product]
            candidate_limit = int(math.ceil(2.0 * candidate_lead))
            lead["mean"] = candidate_lead
            limit["value"] = candidate_limit
            changes.append(
                {
                    "target_product_id": product,
                    "factory_id": PRODUCT_FACTORY[product],
                    **{key: lane[key] for key in ("edge_id", "supplier_id", "item_id")},
                    "offset_days": offsets[product],
                    "lead_time_reference_days": reference_lead,
                    "lead_time_candidate_days": candidate_lead,
                    "delay_step_limit_reference": reference_limit,
                    "delay_step_limit_candidate": candidate_limit,
                    "physically_changed": offsets[product] > 0,
                }
            )
    return graph, changes


def _selection_contract() -> dict[str, Any]:
    return {
        "primary_measure": "ratio_of_summed_on_due_quantities_to_summed_demand",
        "service_window_days": SERVICE_DAYS,
        "development_seed_count": 30,
        "op100_pooled_global_and_each_product_minimum": REFERENCE_MINIMUM,
        "op100_seed_median_global_minimum": REFERENCE_MINIMUM,
        "development_inner_pooled_and_median_bands": {
            key: list(value) for key, value in DEVELOPMENT_INNER_BANDS.items()
        },
        "development_leave_one_out_outer_bands": {
            key: list(value) for key, value in OUTER_BANDS.items()
        },
        "degraded_product_pooled_strictly_below": NON_SATURATION_LIMIT,
        "pooled_strict_order_global_and_each_product": True,
        "same_seed_joint_strict_order_required": MIN_ORDERED_SEEDS,
        "candidate_must_have_all_development_seeds": True,
        "pair_tie_break_v4": [
            "minimum_max_of_op93_op80_global_error_over_pool_median_and_loo",
            "maximum_joint_strict_order_count_global_pf091_pf967",
            "maximum_strict_order_count_pf967",
            "minimum_max_of_op93_op80_pooled_product_gap_pp",
            "minimum_sum_of_op93_op80_pooled_product_gap_pp",
            "minimum_max_of_op93_op80_global_service_iqr",
            "minimum_sum_of_op93_op80_global_service_iqr",
            "lexicographic_offsets_op93_091_op93_967_op80_091_op80_967",
        ],
        "tie_break_change_from_v2": (
            "V4 prioritizes paired ordering counts before product gap and dispersion; "
            "it removes V2 summed error, demand-weighted offset, and candidate-id keys."
        ),
        "paired_demand_tolerance": {
            "relative": DEMAND_REL_TOLERANCE,
            "absolute_units": DEMAND_ABS_TOLERANCE,
        },
        "no_interpolation": True,
        "no_holdout_read_before_selection": True,
    }


def _holdout_contract() -> dict[str, Any]:
    return {
        "status_before_development_selection": "sealed_unread",
        "seed_count": 30,
        "seeds": list(EXPECTED_HOLDOUT_SEEDS),
        "selected_point_count": 3,
        "baseline_case_count": 90,
        "service_window_days": SERVICE_DAYS,
        "op100_pooled_global_and_each_product_minimum": REFERENCE_MINIMUM,
        "op100_seed_median_global_minimum": REFERENCE_MINIMUM,
        "op93_pooled_and_median_band": list(OUTER_BANDS["op_93"]),
        "op80_pooled_and_median_band": list(OUTER_BANDS["op_80"]),
        "degraded_product_pooled_strictly_below": NON_SATURATION_LIMIT,
        "pooled_strict_order_global_and_each_product": True,
        "same_seed_joint_strict_order_required": MIN_ORDERED_SEEDS,
        "paired_demand_tolerance": {
            "relative": DEMAND_REL_TOLERANCE,
            "absolute_units": DEMAND_ABS_TOLERANCE,
        },
        "bootstrap": {
            "method": "paired_common_seed_resampling_ratio_of_sums_percentile",
            "replicates": BOOTSTRAP_REPLICATES,
            "seed": BOOTSTRAP_SEED,
            "acceptance_gate": False,
        },
        "shipment_trace": {
            "schema_version": SHIPMENT_TRACE_SCHEMA_VERSION,
            "required_scope": "official_holdout_only",
            "null_scope": ["development", "test_only"],
            "lane_count": 18,
            "source_csv": SHIPMENT_TRACE_SOURCE_RELATIVE_PATH,
            "fields": list(SHIPMENT_TRACE_FIELDS),
            "compression": SHIPMENT_TRACE_COMPRESSION,
            "selection_metrics_unchanged": True,
        },
        "product_gap_warning_above_pp": PRODUCT_GAP_WARNING_PP,
        "retuning_after_holdout": False,
        "failure_rule": "publish_no_go_and_require_new_fresh_cohort",
    }


def _seed_generation_contract() -> dict[str, Any]:
    return {
        "domain": HOLDOUT_SEED_DOMAIN,
        "message_template": "{domain}|{counter:02d}",
        "counter_origin": 1,
        "encoding": "utf-8_without_bom",
        "digest": "sha256",
        "word": "first_4_digest_bytes_uint32_little_endian",
        "reduction": "(word % 2147483646) + 1",
        "zero_policy": "impossible_after_plus_one_then_reject_defensively",
        "duplicate_policy": "reject_and_increment_counter",
        "ordered_csv_sha256": HOLDOUT_SEED_CSV_SHA256,
        "incident_design_seed": {
            "domain": INCIDENT_DESIGN_SEED_DOMAIN,
            "message": f"{INCIDENT_DESIGN_SEED_DOMAIN}|01",
            "message_sha256": INCIDENT_DESIGN_MESSAGE_SHA256,
            "derivation": "same_sha256_little_endian_31bit_rule",
            "value": INCIDENT_DESIGN_SEED,
            "reserved_not_in_operating_point_selection": True,
        },
        "freshness_audit": {
            "performed_utc_date": "2026-09-05",
            "scope": "repository_and_existing_validation_artifacts_before_v4_creation",
            "result": "no_prior_occurrence_of_any_30_holdout_seed_values",
        },
    }


def _portable_decision_provenance(decision: Mapping[str, Any]) -> dict[str, Any]:
    required = {"sha256", "artifact_signature", "payload"}
    if not required.issubset(decision):
        raise V4ProtocolError("Portable op80 decision provenance is incomplete")
    return {key: copy.deepcopy(decision[key]) for key in sorted(required)}


def _candidate_design_contract(decision: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "op100": "reuse_source_in_development_execute_fresh_in_holdout",
        "op93_exact_grid": [
            {
                "key": key,
                "offset_days_268091": left,
                "offset_days_268967": right,
                "evidence_mode": mode,
            }
            for key, left, right, mode in OP93_GRID
        ],
        "op93_grid_expansion_allowed": False,
        "op80_exact_grid_if_source_inner_fails": [
            {
                "key": key,
                "offset_days_268091": left,
                "offset_days_268967": right,
            }
            for key, left, right in OP80_GRID
        ],
        "op80_grid_expansion_allowed": False,
        "op80_decision": _portable_decision_provenance(decision),
        "op80_source_anchor_always_reused_in_development": True,
        "op80_source_anchor_selectable_only_if_individually_admissible": True,
        "source_states_reused_only_in_development": True,
    }


def _execution_dependency_records(
    runtime_dependencies: Mapping[str, Any],
) -> dict[str, dict[str, str]]:
    validated = _validate_runtime_dependency_inventory(runtime_dependencies)
    hashes = {str(row["path"]): str(row["sha256"]) for row in validated["files"]}
    records: dict[str, dict[str, str]] = {}
    for name, relative in EXECUTOR_DEPENDENCY_RELATIVE_PATHS.items():
        records[name] = {
            "path": str((REPO_ROOT / relative).resolve()),
            "sha256": hashes[relative],
        }
    return records


def _execution_contract(
    source: Mapping[str, Any], runtime_dependencies: Mapping[str, Any]
) -> dict[str, Any]:
    return {
        "scenario": "scn:BASE",
        "simulation_days": SERVICE_DAYS,
        "output_profile": "compact",
        "common_random_numbers": True,
        "changed_dimension": "planned_supplier_lead_time_days_only",
        "quality_incident": False,
        "availability_incident": False,
        "capacity_override": False,
        "state_dependent_risk": False,
        "engine": source["direct_files"]["engine"],
        "engine_profile": source["direct_files"]["engine_profile"],
        "executor_dependencies": _execution_dependency_records(runtime_dependencies),
        "runtime_dependency_aggregate_sha256": runtime_dependencies["aggregate_sha256"],
        "maximum_workers": 2,
        "resume_from_signed_evidence": True,
        "retention": {
            "preserve": [
                "summaries/first_simulation_summary.json",
                "balanced_delay_engine.log",
            ],
            "hashed_before_prune": ["data/production_demand_service_daily.csv"],
            "canonical_pruner": "supplier_service_landscape_campaign.prune_case_artifacts",
            "prune_after_atomic_outer_evidence_only": True,
        },
    }


def _source_hash_contract(
    source: Mapping[str, Any],
    decision_sha256: str,
    runtime_dependencies: Mapping[str, Any],
) -> dict[str, str]:
    validated_runtime = _validate_runtime_dependency_inventory(runtime_dependencies)
    runtime_hashes = {
        str(row["path"]): str(row["sha256"]) for row in validated_runtime["files"]
    }
    result = {
        "v4_driver_sha256": runtime_hashes[
            "etudecas/prototypes/scan_2027_risk_control/"
            "supplier_balanced_product_delay_multiseed_refinement_v4.py"
        ],
        "source_campaign_manifest_sha256": source["campaign_manifest"]["sha256"],
        "source_preflight_sha256": source["preflight"]["sha256"],
        "source_target_discovery_progress_sha256": source["target_discovery_progress"][
            "sha256"
        ],
        "source_target_discovery_evidence_index_sha256": stable_sha256(
            source["target_discovery_evidence"]["sha256_by_case"]
        ),
        "source_selected_points_sha256": source["selected_points"]["sha256"],
        "source_selection_sha256": source["selection"]["sha256"],
        "source_v3_plan_sha256": source["v3_plan"]["sha256"],
        "engine_sha256": source["direct_files"]["engine"]["sha256"],
        "engine_profile_sha256": source["direct_files"]["engine_profile"]["sha256"],
        "source_runner_sha256": source["direct_files"]["runner"]["sha256"],
        "op80_decision_sha256": decision_sha256,
    }
    result.update(
        {
            f"executor_dependency_{name}_sha256": record["sha256"]
            for name, record in _execution_dependency_records(validated_runtime).items()
        }
    )
    return result


def prepare_plan(
    output_dir: Path,
    *,
    source_campaign_manifest: Path = DEFAULT_SOURCE_CAMPAIGN_MANIFEST,
    op80_decision_path: Path | None = None,
) -> Path:
    """Create a signed immutable V4 plan without executing any simulation."""

    if op80_decision_path is None:
        raise V4ProtocolError(
            "Explicit signed op80 decision is required before prepare"
        )
    output_dir = output_dir.resolve()
    if output_dir.exists():
        raise FileExistsError(f"Refusing to overwrite V4 plan: {output_dir}")
    source = validate_rejected_v3_campaign(source_campaign_manifest)
    decision, op80 = _validate_op80_decision(op80_decision_path, source)
    for protected in (
        Path(source["campaign_manifest"]["path"]).parent,
        Path(source["v3_plan"]["path"]).parent,
    ):
        if _paths_overlap(output_dir, protected):
            raise V4ProtocolError("V4 plan directory overlaps a protected V3 source")
    candidates = _all_candidates(op80)
    seeds = generate_holdout_seeds()
    incident_seed, incident_digest = derive_domain_seed(INCIDENT_DESIGN_SEED_DOMAIN, 1)
    if (
        seeds != EXPECTED_HOLDOUT_SEEDS
        or seed_csv_sha256(seeds) != HOLDOUT_SEED_CSV_SHA256
        or incident_seed != INCIDENT_DESIGN_SEED
        or incident_digest != INCIDENT_DESIGN_MESSAGE_SHA256
    ):
        raise V4ProtocolError("Fresh holdout seed derivation changed")
    burned = set(SOURCE_DESIGN_SEEDS + SOURCE_CALIBRATION_SEEDS + DEVELOPMENT_SEEDS)
    if (
        burned.intersection(seeds)
        or INCIDENT_DESIGN_SEED in burned
        or INCIDENT_DESIGN_SEED in seeds
    ):
        raise V4ProtocolError("V4 seed cohorts are not globally disjoint")

    runtime_dependencies = _runtime_dependency_inventory_from_worktree()
    v3_plan = _read_json(Path(source["v3_plan"]["path"]))
    lanes = _base_lane_scope(v3_plan)
    if sum(len(rows) for rows in lanes.values()) != 18:
        raise V4ProtocolError("V4 requires exactly 18 frozen supplier lanes")
    base_graph = _read_json(Path(source["state_sources"]["op_100"]["path"]))
    temporary = output_dir.parent / f".{output_dir.name}.building-{os.getpid()}"
    if temporary.exists():
        raise FileExistsError(f"Temporary V4 plan already exists: {temporary}")
    temporary.mkdir(parents=True)
    try:
        shutil.copyfile(decision["path"], temporary / "op80_decision.json")
        inventory: dict[str, dict[str, Any]] = {}
        state_sources = source["state_sources"]
        for candidate in candidates:
            graph_path = temporary / "graphs" / f"{candidate.key}.json"
            ledger_path = temporary / "ledgers" / f"{candidate.key}.json"
            if candidate.evidence_mode == "reuse_source_development":
                source_graph = Path(
                    state_sources[candidate.source_operating_point_id]["path"]
                )
                graph_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source_graph, graph_path)
                expected_source_hash = state_sources[
                    candidate.source_operating_point_id
                ]["sha256"]
                if sha256_file(graph_path) != expected_source_hash:
                    raise V4ProtocolError("Copied V3 graph hash changed")
                changes = _v3_source_changes(v3_plan, candidate)
            else:
                graph, changes = _apply_offsets(
                    base_graph,
                    lanes,
                    candidate.offset_days_268091,
                    candidate.offset_days_268967,
                )
                _write_json(graph_path, graph)
            ledger = {
                "schema_version": f"{PLAN_SCHEMA_VERSION}.change_ledger",
                "candidate": _candidate_payload(candidate),
                "changed_dimension": "planned_supplier_lead_time_days_only",
                "changes": changes,
            }
            _write_json(ledger_path, ledger)
            inventory[candidate.key] = {
                "graph_path": graph_path.relative_to(temporary).as_posix(),
                "graph_sha256": sha256_file(graph_path),
                "ledger_path": ledger_path.relative_to(temporary).as_posix(),
                "ledger_sha256": sha256_file(ledger_path),
            }

        cases = [
            {
                "stage": "development",
                "candidate_key": candidate.key,
                "seed": seed,
                "evidence_mode": candidate.evidence_mode,
            }
            for candidate in candidates
            for seed in DEVELOPMENT_SEEDS
        ]
        source_hashes = _source_hash_contract(
            source, decision["sha256"], runtime_dependencies
        )
        manifest: dict[str, Any] = {
            "schema_version": PLAN_SCHEMA_VERSION,
            "status": "frozen_before_v4_development",
            "interpretation": INTERPRETATION,
            "source": source,
            "source_hashes": source_hashes,
            "runtime_dependencies": runtime_dependencies,
            "cohorts": {
                "source_design_burned": list(SOURCE_DESIGN_SEEDS),
                "source_calibration_burned": list(SOURCE_CALIBRATION_SEEDS),
                "development_burned": list(DEVELOPMENT_SEEDS),
                "holdout_sealed_fresh": list(seeds),
                "incident_design_reserved": [INCIDENT_DESIGN_SEED],
            },
            "seed_generation": _seed_generation_contract(),
            "candidate_design": _candidate_design_contract(decision),
            "candidates": [_candidate_payload(candidate) for candidate in candidates],
            "inventory": inventory,
            "development_cases": cases,
            "expected_development_case_count": len(cases),
            "reused_development_case_count": sum(
                row["evidence_mode"].startswith("reuse_source") for row in cases
            ),
            "new_development_case_count": sum(
                row["evidence_mode"] == "execute" for row in cases
            ),
            "selection_contract": _selection_contract(),
            "holdout_contract": _holdout_contract(),
            "execution_contract": _execution_contract(source, runtime_dependencies),
        }
        manifest["plan_signature"] = stable_sha256(manifest)
        _write_json(temporary / "refinement_plan.json", manifest)
        os.replace(temporary, output_dir)
    except BaseException:
        if temporary.exists():
            shutil.rmtree(temporary)
        raise
    return output_dir


def _manifest_without_signature(manifest: Mapping[str, Any]) -> dict[str, Any]:
    unsigned = dict(manifest)
    unsigned.pop("plan_signature", None)
    return unsigned


def validate_plan(
    plan_dir: Path, *, verify_runtime_dependencies: bool = True
) -> ValidatedPlan:
    plan_dir = plan_dir.resolve()
    manifest = _read_json(plan_dir / "refinement_plan.json")
    signature = str(manifest.get("plan_signature") or "")
    if manifest.get(
        "schema_version"
    ) != PLAN_SCHEMA_VERSION or signature != stable_sha256(
        _manifest_without_signature(manifest)
    ):
        raise V4ProtocolError("Invalid V4 plan signature")
    expected_fields = {
        "schema_version",
        "status",
        "interpretation",
        "source",
        "source_hashes",
        "runtime_dependencies",
        "cohorts",
        "seed_generation",
        "candidate_design",
        "candidates",
        "inventory",
        "development_cases",
        "expected_development_case_count",
        "reused_development_case_count",
        "new_development_case_count",
        "selection_contract",
        "holdout_contract",
        "execution_contract",
        "plan_signature",
    }
    if (
        set(manifest) != expected_fields
        or manifest.get("status") != "frozen_before_v4_development"
        or manifest.get("interpretation") != INTERPRETATION
    ):
        raise V4ProtocolError("Unexpected field or status in V4 plan")
    source = validate_rejected_v3_campaign(
        Path(manifest["source"]["campaign_manifest"]["path"])
    )
    if _paths_overlap(
        plan_dir, Path(source["campaign_manifest"]["path"]).parent
    ) or _paths_overlap(plan_dir, Path(source["v3_plan"]["path"]).parent):
        raise V4ProtocolError("V4 plan directory overlaps a protected V3 source")
    if source != manifest.get("source"):
        raise V4ProtocolError("V4 source provenance changed")
    runtime_dependencies = _validate_runtime_dependency_inventory(
        manifest.get("runtime_dependencies")
    )
    decision_copy = plan_dir / "op80_decision.json"
    if sha256_file(decision_copy) != manifest["source_hashes"]["op80_decision_sha256"]:
        raise V4ProtocolError("V4 op80 decision copy changed")
    copied_decision, op80 = _validate_op80_decision(decision_copy, source)
    declared_decision = (manifest.get("candidate_design") or {}).get(
        "op80_decision"
    ) or {}
    if (
        declared_decision != _portable_decision_provenance(copied_decision)
        or "path" in declared_decision
    ):
        raise V4ProtocolError("V4 copied op80 decision provenance changed")
    candidates = _all_candidates(op80)
    if manifest.get("candidates") != [_candidate_payload(item) for item in candidates]:
        raise V4ProtocolError("V4 candidate grid changed")
    if (
        manifest.get("seed_generation") != _seed_generation_contract()
        or manifest.get("candidate_design")
        != _candidate_design_contract(copied_decision)
        or manifest.get("selection_contract") != _selection_contract()
        or manifest.get("holdout_contract") != _holdout_contract()
        or manifest.get("execution_contract")
        != _execution_contract(source, runtime_dependencies)
    ):
        raise V4ProtocolError("V4 selection or holdout contract changed")
    seeds = generate_holdout_seeds()
    incident_seed, incident_digest = derive_domain_seed(INCIDENT_DESIGN_SEED_DOMAIN, 1)
    cohorts = manifest.get("cohorts") or {}
    if (
        tuple(cohorts.get("source_design_burned") or ()) != SOURCE_DESIGN_SEEDS
        or tuple(cohorts.get("source_calibration_burned") or ())
        != SOURCE_CALIBRATION_SEEDS
        or tuple(cohorts.get("development_burned") or ()) != DEVELOPMENT_SEEDS
        or tuple(cohorts.get("holdout_sealed_fresh") or ()) != seeds
        or cohorts.get("incident_design_reserved") != [INCIDENT_DESIGN_SEED]
        or seed_csv_sha256(seeds) != HOLDOUT_SEED_CSV_SHA256
        or incident_seed != INCIDENT_DESIGN_SEED
        or incident_digest != INCIDENT_DESIGN_MESSAGE_SHA256
    ):
        raise V4ProtocolError("V4 seed contract changed")
    cases = [
        {
            "stage": "development",
            "candidate_key": candidate.key,
            "seed": seed,
            "evidence_mode": candidate.evidence_mode,
        }
        for candidate in candidates
        for seed in DEVELOPMENT_SEEDS
    ]
    if (
        manifest.get("development_cases") != cases
        or manifest.get("expected_development_case_count") != len(cases)
        or manifest.get("reused_development_case_count")
        != sum(row["evidence_mode"].startswith("reuse_source") for row in cases)
        or manifest.get("new_development_case_count")
        != sum(row["evidence_mode"] == "execute" for row in cases)
    ):
        raise V4ProtocolError("V4 development case grid changed")
    inventory = manifest.get("inventory") or {}
    if set(inventory) != {candidate.key for candidate in candidates}:
        raise V4ProtocolError("V4 graph inventory changed")
    v3_plan = _read_json(Path(source["v3_plan"]["path"]))
    lanes = _base_lane_scope(v3_plan)
    if sum(len(rows) for rows in lanes.values()) != 18:
        raise V4ProtocolError("V4 requires exactly 18 frozen supplier lanes")
    base_graph = _read_json(Path(source["state_sources"]["op_100"]["path"]))
    for candidate in candidates:
        item = inventory[candidate.key]
        if not isinstance(item, Mapping) or set(item) != {
            "graph_path",
            "graph_sha256",
            "ledger_path",
            "ledger_sha256",
        }:
            raise V4ProtocolError("V4 inventory item fields changed")
        graph = (plan_dir / item["graph_path"]).resolve()
        ledger = (plan_dir / item["ledger_path"]).resolve()
        if not graph.is_relative_to(plan_dir) or not ledger.is_relative_to(plan_dir):
            raise V4ProtocolError("V4 inventory escapes plan directory")
        if (
            item["graph_path"] != f"graphs/{candidate.key}.json"
            or item["ledger_path"] != f"ledgers/{candidate.key}.json"
        ):
            raise V4ProtocolError("V4 inventory canonical paths changed")
        _require_hash(graph, item["graph_sha256"], f"V4 {candidate.key} graph")
        _require_hash(ledger, item["ledger_sha256"], f"V4 {candidate.key} ledger")
        if candidate.evidence_mode == "reuse_source_development":
            expected_graph = _read_json(
                Path(
                    source["state_sources"][candidate.source_operating_point_id]["path"]
                )
            )
            expected_changes = _v3_source_changes(v3_plan, candidate)
        else:
            expected_graph, expected_changes = _apply_offsets(
                base_graph,
                lanes,
                candidate.offset_days_268091,
                candidate.offset_days_268967,
            )
        if _read_json(graph) != expected_graph:
            raise V4ProtocolError(f"V4 canonical graph changed: {candidate.key}")
        ledger_payload = _read_json(ledger)
        expected_ledger = {
            "schema_version": f"{PLAN_SCHEMA_VERSION}.change_ledger",
            "candidate": _candidate_payload(candidate),
            "changed_dimension": "planned_supplier_lead_time_days_only",
            "changes": expected_changes,
        }
        if ledger_payload != expected_ledger:
            raise V4ProtocolError(f"V4 canonical ledger changed: {candidate.key}")
    expected_hashes = _source_hash_contract(
        source, sha256_file(decision_copy), runtime_dependencies
    )
    if manifest.get("source_hashes") != expected_hashes:
        raise V4ProtocolError("V4 source hashes changed")
    validated = ValidatedPlan(plan_dir, manifest, candidates)
    if verify_runtime_dependencies:
        _assert_runtime_dependencies_current(validated)
    return validated


def _case_key(stage: str, candidate_key: str, seed: int) -> str:
    return f"{stage}__{candidate_key}__seed_{seed}"


def _evidence_path(run_dir: Path, stage: str, candidate_key: str, seed: int) -> Path:
    key = _case_key(stage, candidate_key, seed)
    digest = hashlib.sha256(key.encode("utf-8")).hexdigest()[:24]
    return run_dir / "evidence" / stage / f"{digest}.json"


def _normalize_metrics(raw: Mapping[str, Any]) -> dict[str, float]:
    aliases = {
        "system_on_due_service": ("system_on_due_service", "service_global_pct"),
        "on_due_service_268091": ("on_due_service_268091", "service_268091_pct"),
        "on_due_service_268967": ("on_due_service_268967", "service_268967_pct"),
    }
    result: dict[str, float] = {}
    for field, names in aliases.items():
        value: Any = None
        used = ""
        for name in names:
            if name in raw:
                value = raw[name]
                used = name
                break
        try:
            number = float(value)
        except (TypeError, ValueError) as exc:
            raise V4ProtocolError(f"Missing metric {field}") from exc
        if used.endswith("_pct"):
            number /= 100.0
        if not math.isfinite(number) or not 0 <= number <= 1:
            raise V4ProtocolError(f"Invalid service metric {field}")
        result[field] = number
    for product in PRODUCTS:
        for prefix in ("demand_qty", "on_due_qty"):
            field = f"{prefix}_{product}"
            try:
                number = float(raw[field])
            except (KeyError, TypeError, ValueError) as exc:
                raise V4ProtocolError(f"Missing metric {field}") from exc
            if not math.isfinite(number) or number < 0:
                raise V4ProtocolError(f"Invalid quantity metric {field}")
            result[field] = number
        if result[f"demand_qty_{product}"] <= 0:
            raise V4ProtocolError("Positive product demand is required")
        ratio = result[f"on_due_qty_{product}"] / result[f"demand_qty_{product}"]
        if not math.isclose(
            ratio, result[f"on_due_service_{product}"], rel_tol=1e-9, abs_tol=1e-9
        ):
            raise V4ProtocolError("Service/quantity metrics are inconsistent")
    demand = sum(result[f"demand_qty_{product}"] for product in PRODUCTS)
    on_due = sum(result[f"on_due_qty_{product}"] for product in PRODUCTS)
    result["demand_qty_global"] = demand
    result["on_due_qty_global"] = on_due
    if not math.isclose(
        on_due / demand,
        result["system_on_due_service"],
        rel_tol=1e-9,
        abs_tol=1e-9,
    ):
        raise V4ProtocolError("Global service/quantity metrics are inconsistent")
    return result


def _shipment_lane_contract(plan: ValidatedPlan) -> dict[str, Any]:
    source_lanes = (plan.manifest.get("source") or {}).get("lanes")
    if not isinstance(source_lanes, list) or len(source_lanes) != 18:
        raise V4ProtocolError("Shipment trace requires exactly 18 frozen lanes")
    lanes: list[dict[str, Any]] = []
    for row in source_lanes:
        if not isinstance(row, Mapping) or set(row) != CAMPAIGN_LANE_FIELDS:
            raise V4ProtocolError("Shipment lane contract row is invalid")
        lane = {
            "lane_id": str(row.get("lane_id") or ""),
            "edge_id": str(row.get("edge_id") or ""),
            "supplier_id": str(row.get("supplier_id") or ""),
            "item_id": str(row.get("item_id") or ""),
            "dst_node_id": str(row.get("dst_node_id") or ""),
            "target_product_id": str(row.get("target_product_id") or ""),
            "planned_lead_days": float(row.get("planned_lead_days")),
        }
        if (
            not all(str(value) for value in lane.values())
            or lane["target_product_id"] not in PRODUCTS
            or not math.isfinite(lane["planned_lead_days"])
            or lane["planned_lead_days"] <= 0.0
        ):
            raise V4ProtocolError("Shipment lane contract identity is incomplete")
        lanes.append(lane)
    lanes.sort(key=lambda lane: str(lane["lane_id"]))
    lane_ids = [lane["lane_id"] for lane in lanes]
    edge_ids = [lane["edge_id"] for lane in lanes]
    if len(lane_ids) != len(set(lane_ids)) or len(edge_ids) != len(set(edge_ids)):
        raise V4ProtocolError("Shipment lane or edge ids are not unique")
    unsigned = {
        "schema_version": SHIPMENT_LANE_CONTRACT_SCHEMA_VERSION,
        "lanes": lanes,
    }
    return {**unsigned, "lane_contract_sha256": stable_sha256(unsigned)}


def _shipment_filter_contract(plan: ValidatedPlan) -> dict[str, Any]:
    lane_contract = _shipment_lane_contract(plan)
    return {
        "source_csv": SHIPMENT_TRACE_SOURCE_RELATIVE_PATH,
        "lane_ids": [lane["lane_id"] for lane in lane_contract["lanes"]],
        "source_edge_id_by_lane_id": {
            lane["lane_id"]: lane["edge_id"] for lane in lane_contract["lanes"]
        },
        "risk_decision_day_min_inclusive": 0,
        "risk_decision_day_max_inclusive": SERVICE_DAYS - 1,
        "quantity_rule": (
            "pulled_qty_strictly_positive_and_shipped_qty_strictly_positive"
        ),
        "identifier_rule": "lane_id_and_shipment_id_non_empty",
        "arrival_rule": "arrival_day_equals_release_day_plus_positive_lead_days",
        "source_column_mapping": {
            "edge_id": "lane_id",
            "day": "release_day",
        },
        "canonical_sort_fields": [
            "lane_id",
            "risk_decision_day",
            "shipment_id",
            "arrival_day",
            "release_day",
        ],
    }


def _shipment_trace_relative_path(candidate: Candidate, seed: int) -> str:
    return f"shipment_traces/holdout/{candidate.key}/seed_{int(seed)}.json.gz"


def _strict_trace_int(value: Any, label: str) -> int:
    text = "" if value is None else str(value).strip()
    if not re.fullmatch(r"-?[0-9]+", text):
        raise V4ProtocolError(f"Invalid shipment trace integer: {label}")
    return int(text)


def _strict_trace_float(value: Any, label: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise V4ProtocolError(f"Invalid shipment trace number: {label}") from exc
    if not math.isfinite(number):
        raise V4ProtocolError(f"Invalid shipment trace number: {label}")
    return number


def _canonical_trace_rows(
    source_csv_bytes: bytes, plan: ValidatedPlan
) -> list[list[Any]]:
    try:
        source_text = source_csv_bytes.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise V4ProtocolError("Shipment source CSV is not UTF-8") from exc
    reader = csv.DictReader(io.StringIO(source_text, newline=""))
    required_source_fields = {
        "edge_id",
        "shipment_id",
        "risk_decision_day",
        "day",
        "arrival_day",
        "pulled_qty",
        "shipped_qty",
        "reliability",
        "lead_days",
        "uom",
    }
    if reader.fieldnames is None or not required_source_fields.issubset(
        set(reader.fieldnames)
    ):
        raise V4ProtocolError("Shipment source CSV columns are incomplete")
    filter_contract = _shipment_filter_contract(plan)
    lane_by_edge_id = {
        edge_id: lane_id
        for lane_id, edge_id in filter_contract["source_edge_id_by_lane_id"].items()
    }
    rows: list[list[Any]] = []
    shipment_ids: set[str] = set()
    for source_row_number, row in enumerate(reader, start=2):
        edge_id = str(row.get("edge_id") or "").strip()
        if edge_id not in lane_by_edge_id:
            continue
        lane_id = lane_by_edge_id[edge_id]
        decision_day = _strict_trace_int(
            row.get("risk_decision_day"),
            f"risk_decision_day row {source_row_number}",
        )
        if not 0 <= decision_day < SERVICE_DAYS:
            continue
        pulled_qty = _strict_trace_float(
            row.get("pulled_qty"), f"pulled_qty row {source_row_number}"
        )
        shipped_qty = _strict_trace_float(
            row.get("shipped_qty"), f"shipped_qty row {source_row_number}"
        )
        if pulled_qty < 0.0 or shipped_qty < 0.0:
            raise V4ProtocolError("Shipment trace quantity cannot be negative")
        if pulled_qty == 0.0 or shipped_qty == 0.0:
            continue
        if shipped_qty > pulled_qty + 1e-7:
            raise V4ProtocolError("Shipment trace shipped quantity exceeds pull")
        shipment_id = str(row.get("shipment_id") or "").strip()
        if not shipment_id or shipment_id in shipment_ids:
            raise V4ProtocolError("Shipment trace shipment id is empty or duplicated")
        shipment_ids.add(shipment_id)
        release_day = _strict_trace_int(
            row.get("day"), f"release day row {source_row_number}"
        )
        arrival_day = _strict_trace_int(
            row.get("arrival_day"), f"arrival day row {source_row_number}"
        )
        lead_days = _strict_trace_int(
            row.get("lead_days"), f"lead days row {source_row_number}"
        )
        if lead_days <= 0 or arrival_day < 0 or arrival_day != release_day + lead_days:
            raise V4ProtocolError("Shipment trace arrival/lead relationship is invalid")
        reliability = _strict_trace_float(
            row.get("reliability"), f"reliability row {source_row_number}"
        )
        if not 0.0 <= reliability <= 1.0:
            raise V4ProtocolError("Shipment trace reliability is outside [0, 1]")
        uom = str(row.get("uom") or "").strip()
        if not uom:
            raise V4ProtocolError("Shipment trace uom is empty")
        rows.append(
            [
                lane_id,
                shipment_id,
                decision_day,
                release_day,
                arrival_day,
                pulled_qty,
                shipped_qty,
                reliability,
                lead_days,
                uom,
            ]
        )
    rows.sort(key=lambda row: (row[0], row[2], row[1], row[4], row[3]))
    return rows


def _validate_canonical_trace_rows(rows: Any, plan: ValidatedPlan) -> list[list[Any]]:
    if not isinstance(rows, list):
        raise V4ProtocolError("Shipment trace rows are missing")
    lane_ids = set(_shipment_filter_contract(plan)["lane_ids"])
    validated: list[list[Any]] = []
    shipment_ids: set[str] = set()
    for raw in rows:
        if not isinstance(raw, list) or len(raw) != len(SHIPMENT_TRACE_FIELDS):
            raise V4ProtocolError("Shipment trace row shape changed")
        lane_id, shipment_id, decision, release, arrival = raw[:5]
        pulled, shipped, reliability, lead, uom = raw[5:]
        if (
            not isinstance(lane_id, str)
            or lane_id not in lane_ids
            or not isinstance(shipment_id, str)
            or not shipment_id
            or shipment_id in shipment_ids
            or type(decision) is not int
            or not 0 <= decision < SERVICE_DAYS
            or type(release) is not int
            or type(arrival) is not int
            or arrival < 0
            or type(lead) is not int
            or lead <= 0
            or arrival != release + lead
            or isinstance(pulled, bool)
            or not isinstance(pulled, (int, float))
            or not math.isfinite(float(pulled))
            or float(pulled) <= 0.0
            or isinstance(shipped, bool)
            or not isinstance(shipped, (int, float))
            or not math.isfinite(float(shipped))
            or float(shipped) <= 0.0
            or float(shipped) > float(pulled) + 1e-7
            or isinstance(reliability, bool)
            or not isinstance(reliability, (int, float))
            or not math.isfinite(float(reliability))
            or not 0.0 <= float(reliability) <= 1.0
            or not isinstance(uom, str)
            or not uom
        ):
            raise V4ProtocolError("Shipment trace row value is invalid")
        shipment_ids.add(shipment_id)
        validated.append(list(raw))
    if validated != sorted(
        validated, key=lambda row: (row[0], row[2], row[1], row[4], row[3])
    ):
        raise V4ProtocolError("Shipment trace rows are not canonically sorted")
    return validated


def _trace_json_bytes(payload: Mapping[str, Any]) -> bytes:
    return json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _deterministic_gzip(payload: bytes) -> bytes:
    output = io.BytesIO()
    with gzip.GzipFile(
        filename="",
        mode="wb",
        compresslevel=9,
        fileobj=output,
        mtime=0,
    ) as stream:
        stream.write(payload)
    return output.getvalue()


def _shipment_trace_payload(
    *,
    plan: ValidatedPlan,
    candidate: Candidate,
    seed: int,
    rows: list[list[Any]],
    source_csv_sha256: str,
) -> dict[str, Any]:
    lane_contract = _shipment_lane_contract(plan)
    unsigned = {
        "schema_version": SHIPMENT_TRACE_SCHEMA_VERSION,
        "plan_signature": plan.manifest["plan_signature"],
        "candidate_key": candidate.key,
        "candidate_id": candidate.candidate_id,
        "target_group": candidate.target_group,
        "seed": int(seed),
        "graph_sha256": plan.manifest["inventory"][candidate.key]["graph_sha256"],
        "engine_sha256": plan.manifest["source_hashes"]["engine_sha256"],
        "simulation_days": SERVICE_DAYS,
        "lane_contract_sha256": lane_contract["lane_contract_sha256"],
        "source_csv_sha256": source_csv_sha256,
        "row_count": len(rows),
        "filter_contract": _shipment_filter_contract(plan),
        "fields": list(SHIPMENT_TRACE_FIELDS),
        "rows": rows,
    }
    return {**unsigned, "trace_signature": stable_sha256(unsigned)}


def _load_shipment_trace_file(
    *,
    plan: ValidatedPlan,
    run_dir: Path,
    candidate: Candidate,
    seed: int,
) -> tuple[dict[str, Any], bytes, bytes]:
    path = (run_dir / _shipment_trace_relative_path(candidate, seed)).resolve()
    if not path.is_relative_to(run_dir.resolve()) or not path.is_file():
        raise V4ProtocolError("Required official holdout shipment trace is missing")
    compressed = path.read_bytes()
    try:
        raw = gzip.decompress(compressed)
        payload = json.loads(raw.decode("utf-8"))
    except (OSError, EOFError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise V4ProtocolError("Official holdout shipment trace is corrupt") from exc
    if not isinstance(payload, dict):
        raise V4ProtocolError("Official holdout shipment trace payload is invalid")
    if _deterministic_gzip(raw) != compressed:
        raise V4ProtocolError("Shipment trace gzip is not deterministic/canonical")
    signature = _verify_self_signature(
        payload, "trace_signature", "official holdout shipment trace"
    )
    expected_fields = {
        "schema_version",
        "plan_signature",
        "candidate_key",
        "candidate_id",
        "target_group",
        "seed",
        "graph_sha256",
        "engine_sha256",
        "simulation_days",
        "lane_contract_sha256",
        "source_csv_sha256",
        "row_count",
        "filter_contract",
        "fields",
        "rows",
        "trace_signature",
    }
    lane_contract = _shipment_lane_contract(plan)
    if (
        set(payload) != expected_fields
        or payload.get("schema_version") != SHIPMENT_TRACE_SCHEMA_VERSION
        or payload.get("plan_signature") != plan.manifest["plan_signature"]
        or payload.get("candidate_key") != candidate.key
        or payload.get("candidate_id") != candidate.candidate_id
        or payload.get("target_group") != candidate.target_group
        or type(payload.get("seed")) is not int
        or payload.get("seed") != int(seed)
        or payload.get("graph_sha256")
        != plan.manifest["inventory"][candidate.key]["graph_sha256"]
        or payload.get("engine_sha256")
        != plan.manifest["source_hashes"]["engine_sha256"]
        or payload.get("simulation_days") != SERVICE_DAYS
        or payload.get("lane_contract_sha256") != lane_contract["lane_contract_sha256"]
        or not re.fullmatch(
            r"[0-9a-f]{64}", str(payload.get("source_csv_sha256") or "")
        )
        or type(payload.get("row_count")) is not int
        or payload.get("filter_contract") != _shipment_filter_contract(plan)
        or payload.get("fields") != list(SHIPMENT_TRACE_FIELDS)
    ):
        raise V4ProtocolError("Official holdout shipment trace identity changed")
    rows = _validate_canonical_trace_rows(payload.get("rows"), plan)
    if payload.get("row_count") != len(rows):
        raise V4ProtocolError("Official holdout shipment trace row count changed")
    payload["trace_signature"] = signature
    return payload, raw, compressed


def _validate_shipment_trace_reference(
    reference: Any,
    *,
    plan: ValidatedPlan,
    run_dir: Path,
    candidate: Candidate,
    seed: int,
) -> dict[str, Any]:
    if not isinstance(reference, Mapping) or set(reference) != (
        SHIPMENT_TRACE_REFERENCE_FIELDS
    ):
        raise V4ProtocolError("Official holdout shipment trace reference is invalid")
    expected_relative = _shipment_trace_relative_path(candidate, seed)
    if (
        reference.get("relative_path") != expected_relative
        or reference.get("compression") != SHIPMENT_TRACE_COMPRESSION
        or not re.fullmatch(r"[0-9a-f]{64}", str(reference.get("gzip_sha256") or ""))
        or not re.fullmatch(
            r"[0-9a-f]{64}", str(reference.get("trace_signature") or "")
        )
        or not re.fullmatch(
            r"[0-9a-f]{64}", str(reference.get("source_csv_sha256") or "")
        )
        or type(reference.get("row_count")) is not int
        or int(reference["row_count"]) < 0
        or type(reference.get("uncompressed_bytes")) is not int
        or int(reference["uncompressed_bytes"]) <= 0
    ):
        raise V4ProtocolError("Official holdout shipment trace reference changed")
    payload, raw, compressed = _load_shipment_trace_file(
        plan=plan,
        run_dir=run_dir,
        candidate=candidate,
        seed=seed,
    )
    if (
        hashlib.sha256(compressed).hexdigest() != reference["gzip_sha256"]
        or payload["trace_signature"] != reference.get("trace_signature")
        or payload["source_csv_sha256"] != reference["source_csv_sha256"]
        or payload["row_count"] != reference["row_count"]
        or len(payload["rows"]) != reference["row_count"]
        or len(raw) != reference["uncompressed_bytes"]
    ):
        raise V4ProtocolError("Official holdout shipment trace proof differs")
    return payload


def _write_holdout_shipment_trace(
    *,
    plan: ValidatedPlan,
    run_dir: Path,
    candidate: Candidate,
    seed: int,
    source_csv: Path,
) -> dict[str, Any]:
    if not source_csv.is_file():
        raise V4ProtocolError("Official holdout supplier shipment CSV is missing")
    source_csv_bytes = source_csv.read_bytes()
    source_csv_sha256 = hashlib.sha256(source_csv_bytes).hexdigest()
    rows = _canonical_trace_rows(source_csv_bytes, plan)
    payload = _shipment_trace_payload(
        plan=plan,
        candidate=candidate,
        seed=seed,
        rows=rows,
        source_csv_sha256=source_csv_sha256,
    )
    raw = _trace_json_bytes(payload)
    compressed = _deterministic_gzip(raw)
    relative = _shipment_trace_relative_path(candidate, seed)
    output = (run_dir / relative).resolve()
    if not output.is_relative_to(run_dir.resolve()):
        raise V4ProtocolError("Shipment trace output escaped the V4 run")
    if output.is_file():
        _load_shipment_trace_file(
            plan=plan,
            run_dir=run_dir,
            candidate=candidate,
            seed=seed,
        )
        if output.read_bytes() != compressed:
            raise V4ProtocolError(
                "Existing orphan shipment trace differs from deterministic replay"
            )
    else:
        _write_bytes(output, compressed)
    reference = {
        "relative_path": relative,
        "gzip_sha256": hashlib.sha256(compressed).hexdigest(),
        "trace_signature": payload["trace_signature"],
        "source_csv_sha256": source_csv_sha256,
        "row_count": len(rows),
        "uncompressed_bytes": len(raw),
        "compression": SHIPMENT_TRACE_COMPRESSION,
    }
    _validate_shipment_trace_reference(
        reference,
        plan=plan,
        run_dir=run_dir,
        candidate=candidate,
        seed=seed,
    )
    return reference


def _source_development_metrics(
    plan: ValidatedPlan, candidate: Candidate, seed: int
) -> tuple[dict[str, float], dict[str, str]]:
    source_manifest_path = Path(plan.manifest["source"]["campaign_manifest"]["path"])
    campaign = _read_json(source_manifest_path)
    point_id = candidate.source_operating_point_id
    path = (
        source_manifest_path.parent
        / "target_discovery"
        / "evidence"
        / f"{point_id}__target_discovery__seed_{seed}.json"
    )
    payload = _read_json(path)
    signature = _verify_self_signature(
        payload, "evidence_signature", "V3 development evidence"
    )
    state = _state_by_id(campaign)[point_id]
    expected_discovery = stable_sha256(
        {
            "campaign_signature": campaign["campaign_signature"],
            "engine_sha256": campaign["engine_sha256"],
            "engine_profile_sha256": campaign["engine_profile_sha256"],
            "point_id": point_id,
            "graph_sha256": state["graph_sha256"],
            "seed": seed,
            "simulation_days": SERVICE_DAYS,
            "purpose": "cross_state_42d_target_discovery",
        }
    )
    if (
        payload.get("schema_version")
        != f"{V3_CAMPAIGN_SCHEMA_VERSION}.target_discovery.case.v1"
        or payload.get("campaign_signature") != campaign["campaign_signature"]
        or payload.get("engine_sha256") != campaign["engine_sha256"]
        or payload.get("operating_point_id") != point_id
        or int(payload.get("seed") or -1) != seed
        or int(payload.get("simulation_days") or -1) != SERVICE_DAYS
        or payload.get("discovery_signature") != expected_discovery
    ):
        raise V4ProtocolError("V3 reusable development evidence changed")
    return _normalize_metrics(payload.get("state_service_metrics") or {}), {
        "path": str(path.resolve()),
        "sha256": sha256_file(path),
        "evidence_signature": signature,
    }


def _real_executor(**kwargs: Any) -> Mapping[str, Any]:
    """Lazily reuse the executor underlying V3; never imported at module load."""

    candidate: Candidate = kwargs["candidate"]
    plan: ValidatedPlan = kwargs["validated_plan"]
    seed = int(kwargs["seed"])
    attempt_root: Path = kwargs["attempt_root"]
    coarse = importlib.import_module(
        "etudecas.prototypes.scan_2027_risk_control."
        "supplier_balanced_product_delay_calibration"
    )
    if int(coarse.protocol.MEASURED_DAYS) != SERVICE_DAYS:
        raise V4ProtocolError("Pinned executor simulation horizon changed")
    inventory = plan.manifest["inventory"][candidate.key]
    adapter = coarse.ValidatedPlan(
        plan_dir=plan.plan_dir,
        manifest={},
        candidates=(),
        inventory={candidate.candidate_id: inventory},
        lanes_by_product={},
        source_graph=(
            plan.plan_dir / plan.manifest["inventory"]["op100_source"]["graph_path"]
        ),
        engine=Path(plan.manifest["execution_contract"]["engine"]["path"]),
        profile=Path(plan.manifest["execution_contract"]["engine_profile"]["path"]),
    )
    coarse_candidate = coarse.Candidate(
        candidate.candidate_id,
        candidate.offset_days_268091,
        candidate.offset_days_268967,
    )
    return coarse.execute_candidate(coarse_candidate, adapter, attempt_root, seed)


def _validate_coarse_executor_evidence(
    raw: Mapping[str, Any],
    *,
    candidate: Candidate,
    seed: int,
    plan: ValidatedPlan,
) -> dict[str, float]:
    metrics = _normalize_metrics(raw.get("metrics") or raw)
    unsigned = dict(raw)
    raw_signature = str(unsigned.pop("evidence_signature", ""))
    expected_graph_sha256 = plan.manifest["inventory"][candidate.key]["graph_sha256"]
    expected_engine_sha256 = plan.manifest["source_hashes"]["engine_sha256"]
    required_hashes = (
        "summary_sha256",
        "service_daily_sha256",
        "command_sha256",
    )
    if (
        len(raw_signature) != 64
        or raw_signature != stable_sha256(unsigned)
        or raw.get("schema_version") != COARSE_EVIDENCE_SCHEMA_VERSION
        or raw.get("candidate_id") != candidate.candidate_id
        or not math.isclose(
            _finite_nonnegative(raw.get("offset_days_268091"), "executor offset"),
            candidate.offset_days_268091,
            abs_tol=1e-12,
        )
        or not math.isclose(
            _finite_nonnegative(raw.get("offset_days_268967"), "executor offset"),
            candidate.offset_days_268967,
            abs_tol=1e-12,
        )
        or int(raw.get("seed") or -1) != seed
        or raw.get("valid") is not True
        or raw.get("validation_errors") != []
        or raw.get("graph_sha256") != expected_graph_sha256
        or raw.get("engine_sha256") != expected_engine_sha256
        or raw.get("status") not in {"executed", "reextracted"}
        or any(len(str(raw.get(field) or "")) != 64 for field in required_hashes)
        or not str(raw.get("run_dir") or "")
    ):
        raise V4ProtocolError(
            f"Underlying executor proof is invalid: {candidate.key}/{seed}"
        )
    return metrics


def _executor_output(
    raw: Mapping[str, Any],
    *,
    candidate: Candidate,
    seed: int,
    plan: ValidatedPlan,
    injected: bool,
) -> tuple[dict[str, float], dict[str, Any]]:
    metrics = _normalize_metrics(raw.get("metrics") or raw)
    if injected:
        return metrics, {
            "kind": "injected_test_executor",
            "raw_payload": dict(raw),
        }
    metrics = _validate_coarse_executor_evidence(
        raw, candidate=candidate, seed=seed, plan=plan
    )
    return metrics, {
        "kind": "coarse_execute_candidate",
        "raw_evidence": dict(raw),
    }


def _coarse_case_dir(
    raw: Mapping[str, Any], run_dir: Path, candidate: Candidate, seed: int
) -> Path:
    case_dir = Path(str(raw.get("run_dir") or "")).resolve()
    attempt_parent = (run_dir / "engine_attempts").resolve()
    if (
        not case_dir.is_relative_to(attempt_parent)
        or case_dir.name != f"seed_{seed}"
        or case_dir.parent.name != candidate.candidate_id
    ):
        raise V4ProtocolError("Executor case path escaped the V4 attempt directory")
    return case_dir


def _prune_real_executor_case(
    proof: Mapping[str, Any], run_dir: Path, candidate: Candidate, seed: int
) -> None:
    if proof.get("kind") != "coarse_execute_candidate":
        return
    raw = proof.get("raw_evidence") or {}
    case_dir = _coarse_case_dir(raw, run_dir, candidate, seed)
    coarse = importlib.import_module(
        "etudecas.prototypes.scan_2027_risk_control."
        "supplier_balanced_product_delay_calibration"
    )
    coarse.campaign_core.prune_case_artifacts(case_dir)


def _validate_v4_evidence(
    payload: Mapping[str, Any],
    *,
    plan: ValidatedPlan,
    run_dir: Path,
    stage: str,
    candidate: Candidate,
    seed: int,
    execution_mode: str,
) -> dict[str, Any]:
    signature = _verify_self_signature(payload, "evidence_signature", "V4 evidence")
    expected_mode = (
        candidate.evidence_mode if stage == "development" else "execute_fresh_holdout"
    )
    if (
        set(payload) != V4_EVIDENCE_FIELDS
        or payload.get("schema_version") != EVIDENCE_SCHEMA_VERSION
        or payload.get("plan_signature") != plan.manifest["plan_signature"]
        or payload.get("stage") != stage
        or payload.get("candidate_key") != candidate.key
        or payload.get("candidate_id") != candidate.candidate_id
        or payload.get("target_group") != candidate.target_group
        or int(payload.get("seed") or -1) != seed
        or payload.get("evidence_mode") != expected_mode
        or payload.get("graph_sha256")
        != plan.manifest["inventory"][candidate.key]["graph_sha256"]
        or payload.get("engine_sha256")
        != plan.manifest["source_hashes"]["engine_sha256"]
        or payload.get("valid") is not True
        or not isinstance(payload.get("created_at_utc"), str)
    ):
        raise V4ProtocolError(f"V4 evidence contract mismatch: {candidate.key}/{seed}")
    source_proof = payload.get("source_evidence")
    executor_proof = payload.get("executor_proof")
    if stage == "development" and candidate.evidence_mode.startswith("reuse_source"):
        if not isinstance(source_proof, Mapping) or executor_proof is not None:
            raise V4ProtocolError("Reused V4 evidence lacks its V3 source proof")
        point_id = candidate.source_operating_point_id
        case_key = f"{point_id}__target_discovery__seed_{seed}"
        expected_path = (
            Path(plan.manifest["source"]["campaign_manifest"]["path"]).parent
            / "target_discovery"
            / "evidence"
            / f"{case_key}.json"
        ).resolve()
        if set(source_proof) != {"path", "sha256", "evidence_signature"} or (
            Path(str(source_proof.get("path") or "")).resolve() != expected_path
            or source_proof.get("sha256")
            != plan.manifest["source"]["target_discovery_evidence"]["sha256_by_case"][
                case_key
            ]
        ):
            raise V4ProtocolError("Reused V4 evidence source proof changed")
        source_payload = _read_json(expected_path)
        source_signature = _verify_self_signature(
            source_payload, "evidence_signature", "reused V3 evidence"
        )
        if (
            sha256_file(expected_path) != source_proof["sha256"]
            or source_signature != source_proof["evidence_signature"]
        ):
            raise V4ProtocolError("Reused V4 evidence no longer matches V3 proof")
    else:
        if source_proof is not None or not isinstance(executor_proof, Mapping):
            raise V4ProtocolError("Executed V4 evidence lacks executor provenance")
        kind = executor_proof.get("kind")
        expected_kind = (
            "coarse_execute_candidate"
            if execution_mode == OFFICIAL_EXECUTION_MODE
            else "injected_test_executor"
        )
        if (
            execution_mode
            not in {
                OFFICIAL_EXECUTION_MODE,
                TEST_ONLY_EXECUTION_MODE,
            }
            or kind != expected_kind
        ):
            raise V4ProtocolError(
                "Executor proof is incompatible with the registered execution mode"
            )
        if kind == "coarse_execute_candidate":
            raw = executor_proof.get("raw_evidence")
            if set(executor_proof) != {"kind", "raw_evidence"} or not isinstance(
                raw, Mapping
            ):
                raise V4ProtocolError("Invalid coarse executor proof")
            raw_metrics = _validate_coarse_executor_evidence(
                raw, candidate=candidate, seed=seed, plan=plan
            )
            if raw_metrics != _normalize_metrics(payload.get("metrics") or {}):
                raise V4ProtocolError("Outer/coarse executor metrics differ")
        elif kind == "injected_test_executor":
            raw_payload = executor_proof.get("raw_payload")
            if set(executor_proof) != {"kind", "raw_payload"} or not isinstance(
                raw_payload, Mapping
            ):
                raise V4ProtocolError("Invalid injected executor proof")
            if _normalize_metrics(raw_payload.get("metrics") or raw_payload) != (
                _normalize_metrics(payload.get("metrics") or {})
            ):
                raise V4ProtocolError("Outer/injected executor metrics differ")
        else:
            raise V4ProtocolError("Unknown V4 executor proof kind")
    shipment_trace = payload.get("shipment_trace")
    trace_required = stage == "holdout" and execution_mode == OFFICIAL_EXECUTION_MODE
    if trace_required:
        _validate_shipment_trace_reference(
            shipment_trace,
            plan=plan,
            run_dir=run_dir,
            candidate=candidate,
            seed=seed,
        )
    elif shipment_trace is not None:
        raise V4ProtocolError(
            "Shipment trace must be null outside the official holdout"
        )
    normalized = _normalize_metrics(payload.get("metrics") or {})
    result = dict(payload)
    result["metrics"] = normalized
    result["evidence_signature"] = signature
    return result


@contextmanager
def _run_lock(run_dir: Path):
    lock = run_dir / ".v4.lock"
    lock.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(lock, os.O_CREAT | os.O_RDWR, 0o600)
    acquired = False
    try:
        if os.fstat(descriptor).st_size == 0:
            os.write(descriptor, b"\0")
            os.fsync(descriptor)
        os.lseek(descriptor, 0, os.SEEK_SET)
        try:
            if os.name == "nt":
                import msvcrt

                msvcrt.locking(descriptor, msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            raise V4ProtocolError(f"V4 run is already locked: {lock}") from exc
        acquired = True
        os.ftruncate(descriptor, 0)
        os.lseek(descriptor, 0, os.SEEK_SET)
        os.write(descriptor, f"pid={os.getpid()}\n".encode())
        os.fsync(descriptor)
        yield
    finally:
        if acquired:
            try:
                os.lseek(descriptor, 0, os.SEEK_SET)
                if os.name == "nt":
                    import msvcrt

                    msvcrt.locking(descriptor, msvcrt.LK_UNLCK, 1)
                else:
                    import fcntl

                    fcntl.flock(descriptor, fcntl.LOCK_UN)
            except OSError:
                # Closing the descriptor still releases the process-owned lock.
                pass
        os.close(descriptor)


def _load_development_selection(plan: ValidatedPlan, run_dir: Path) -> dict[str, Any]:
    path = run_dir / "development_selection.json"
    if not path.is_file():
        raise V4ProtocolError(
            "Fresh holdout is not authorized before development finalization"
        )
    selection = _read_json(path)
    _verify_self_signature(selection, "selection_signature", "V4 development selection")
    execution_mode = _registered_execution_mode(plan, run_dir)
    if (
        selection.get("schema_version") != SELECTION_SCHEMA_VERSION
        or selection.get("plan_signature") != plan.manifest["plan_signature"]
        or selection.get("status") != "development_selected_pending_fresh_holdout"
        or selection.get("holdout_cases_read") != 0
        or selection.get("execution_mode") != execution_mode
        or selection.get("publishable")
        is not (execution_mode == OFFICIAL_EXECUTION_MODE)
    ):
        raise V4ProtocolError("Fresh holdout is not authorized")
    development_evidence = _load_stage_evidence(plan, run_dir, "development")
    expected = _build_development_selection(
        plan, development_evidence, execution_mode=execution_mode
    )
    if selection != expected:
        raise V4ProtocolError(
            "Development selection is not reproducible from its proofs"
        )
    return selection


def _stage_jobs(
    plan: ValidatedPlan, run_dir: Path, stage: str
) -> tuple[tuple[Candidate, int], ...]:
    if stage == "development":
        return tuple(
            (candidate, seed)
            for candidate in plan.candidates
            for seed in DEVELOPMENT_SEEDS
        )
    if stage != "holdout":
        raise V4ProtocolError("Stage must be development or holdout")
    selection = _load_development_selection(plan, run_dir)
    selected_keys = selection.get("selected_candidate_keys") or {}
    if set(selected_keys) != set(TARGETS):
        raise V4ProtocolError("Development selection is incomplete")
    by_key = {candidate.key: candidate for candidate in plan.candidates}
    try:
        selected = tuple(by_key[selected_keys[group]] for group in TARGETS)
    except KeyError as exc:
        raise V4ProtocolError(
            "Development selection references an unknown candidate"
        ) from exc
    return tuple(
        (candidate, seed) for candidate in selected for seed in EXPECTED_HOLDOUT_SEEDS
    )


def _run_manifest(plan: ValidatedPlan, execution_mode: str) -> dict[str, Any]:
    if execution_mode not in {
        OFFICIAL_EXECUTION_MODE,
        TEST_ONLY_EXECUTION_MODE,
    }:
        raise V4ProtocolError("Unknown V4 execution mode")
    unsigned = {
        "schema_version": f"{SCHEMA_VERSION}.run",
        "plan_path": str(plan.plan_dir),
        "plan_sha256": sha256_file(plan.plan_dir / "refinement_plan.json"),
        "plan_signature": plan.manifest["plan_signature"],
        "engine_sha256": plan.manifest["source_hashes"]["engine_sha256"],
        "development_seeds": list(DEVELOPMENT_SEEDS),
        "holdout_seeds": list(EXPECTED_HOLDOUT_SEEDS),
        "incident_design_seed_excluded": INCIDENT_DESIGN_SEED,
        "execution_mode": execution_mode,
        "publishable": execution_mode == OFFICIAL_EXECUTION_MODE,
    }
    return {**unsigned, "run_signature": stable_sha256(unsigned)}


def _registered_execution_mode(plan: ValidatedPlan, run_dir: Path) -> str:
    manifest = _read_json(run_dir / "run_manifest.json")
    for execution_mode in (OFFICIAL_EXECUTION_MODE, TEST_ONLY_EXECUTION_MODE):
        if manifest == _run_manifest(plan, execution_mode):
            return execution_mode
    raise V4ProtocolError("Invalid V4 run registration")


def _paths_overlap(left: Path, right: Path) -> bool:
    left = left.resolve()
    right = right.resolve()
    return left == right or left.is_relative_to(right) or right.is_relative_to(left)


def _validate_run_location(plan: ValidatedPlan, run_dir: Path) -> None:
    source_campaign_dir = (
        Path(plan.manifest["source"]["campaign_manifest"]["path"]).resolve().parent
    )
    if _paths_overlap(run_dir, plan.plan_dir) or _paths_overlap(
        run_dir, source_campaign_dir
    ):
        raise V4ProtocolError("V4 run directory overlaps a plan or source campaign")


def _assert_holdout_unseen(run_dir: Path) -> None:
    forbidden = (
        run_dir / "evidence" / "holdout",
        run_dir / "shipment_traces" / "holdout",
        run_dir / "holdout_progress.json",
        run_dir / "holdout_result.json",
    )
    if any(path.exists() for path in forbidden):
        raise V4ProtocolError(
            "Development is invalid because fresh holdout output is already visible"
        )


def _validate_existing_evidence_inventory(
    run_dir: Path, stage: str, jobs: Sequence[tuple[Candidate, int]]
) -> None:
    directory = run_dir / "evidence" / stage
    if not directory.exists():
        return
    expected = {
        _evidence_path(run_dir, stage, candidate.key, seed).name
        for candidate, seed in jobs
    }
    actual = {path.name for path in directory.glob("*.json") if path.is_file()}
    if not actual.issubset(expected):
        raise V4ProtocolError(f"Unexpected JSON evidence exists in {stage}")


def _validate_shipment_trace_inventory(
    plan: ValidatedPlan,
    run_dir: Path,
    stage: str,
    jobs: Sequence[tuple[Candidate, int]],
    execution_mode: str,
    *,
    require_complete: bool,
) -> None:
    trace_root = run_dir / "shipment_traces"
    actual = (
        {path.resolve() for path in trace_root.rglob("*") if path.is_file()}
        if trace_root.exists()
        else set()
    )
    expected_by_path: dict[Path, tuple[Candidate, int]] = {}
    if stage == "holdout" and execution_mode == OFFICIAL_EXECUTION_MODE:
        expected_by_path = {
            (run_dir / _shipment_trace_relative_path(candidate, seed)).resolve(): (
                candidate,
                seed,
            )
            for candidate, seed in jobs
        }
    expected = set(expected_by_path)
    if not actual.issubset(expected):
        raise V4ProtocolError("Unexpected shipment trace exists in the V4 run")
    for path in sorted(actual, key=str):
        candidate, seed = expected_by_path[path]
        _load_shipment_trace_file(
            plan=plan,
            run_dir=run_dir,
            candidate=candidate,
            seed=seed,
        )
    if require_complete:
        evidence_complete = all(
            _evidence_path(run_dir, stage, candidate.key, seed).is_file()
            for candidate, seed in jobs
        )
        if actual != expected or not evidence_complete:
            raise V4ProtocolError(
                "Official holdout shipment trace inventory is incomplete"
            )


def _register_run(plan: ValidatedPlan, run_dir: Path, execution_mode: str) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    path = run_dir / "run_manifest.json"
    expected = _run_manifest(plan, execution_mode)
    if path.exists():
        if _read_json(path) != expected:
            raise V4ProtocolError("Run directory belongs to another V4 plan")
    elif any(entry.name != ".v4.lock" for entry in run_dir.iterdir()):
        raise V4ProtocolError("Refusing an unregistered non-empty V4 run directory")
    else:
        _write_json(path, expected)


def _collect_existing_stage_evidence(
    plan: ValidatedPlan,
    run_dir: Path,
    stage: str,
    jobs: Sequence[tuple[Candidate, int]],
    execution_mode: str,
) -> tuple[dict[tuple[str, int], dict[str, Any]], list[tuple[Candidate, int]]]:
    completed: dict[tuple[str, int], dict[str, Any]] = {}
    missing: list[tuple[Candidate, int]] = []
    for candidate, seed in jobs:
        path = _evidence_path(run_dir, stage, candidate.key, seed)
        if not path.exists():
            missing.append((candidate, seed))
            continue
        existing = _validate_v4_evidence(
            _read_json(path),
            plan=plan,
            run_dir=run_dir,
            stage=stage,
            candidate=candidate,
            seed=seed,
            execution_mode=execution_mode,
        )
        completed[(candidate.key, seed)] = existing
        _prune_real_executor_case(
            existing["executor_proof"] or {}, run_dir, candidate, seed
        )
    return completed, missing


def run_stage(
    plan_dir: Path,
    run_dir: Path,
    *,
    stage: str,
    executor: Executor | None = None,
    max_workers: int = 2,
    test_only: bool = False,
) -> dict[str, Any]:
    """Execute or resume one complete stage using signed per-case evidence."""

    if stage not in {"development", "holdout"}:
        raise V4ProtocolError("Stage must be development or holdout")
    if max_workers < 1 or max_workers > 2:
        raise V4ProtocolError("V4 permits one or two workers")
    if executor is not None and not test_only:
        raise V4ProtocolError(
            "An injected executor requires the explicit test_only=True contract"
        )
    if executor is None and test_only:
        raise V4ProtocolError("test_only=True requires an injected executor")
    execution_mode = TEST_ONLY_EXECUTION_MODE if test_only else OFFICIAL_EXECUTION_MODE
    plan = validate_plan(plan_dir, verify_runtime_dependencies=not test_only)
    run_dir = run_dir.resolve()
    _validate_run_location(plan, run_dir)
    if stage == "development":
        _assert_holdout_unseen(run_dir)
    jobs = _stage_jobs(plan, run_dir, stage)
    _validate_existing_evidence_inventory(run_dir, stage, jobs)
    _register_run(plan, run_dir, execution_mode)
    _validate_shipment_trace_inventory(
        plan,
        run_dir,
        stage,
        jobs,
        execution_mode,
        require_complete=False,
    )
    selected_executor = executor or _real_executor
    injected_executor = executor is not None

    def execute(candidate: Candidate, seed: int) -> dict[str, Any]:
        source_proof: dict[str, str] | None = None
        shipment_trace: dict[str, Any] | None = None
        if stage == "development" and candidate.evidence_mode.startswith(
            "reuse_source"
        ):
            metrics, source_proof = _source_development_metrics(plan, candidate, seed)
            executor_proof: dict[str, Any] | None = None
            mode = candidate.evidence_mode
        else:
            if execution_mode == OFFICIAL_EXECUTION_MODE:
                _assert_runtime_dependencies_current(plan)
            attempt_key = _case_key(stage, candidate.key, seed)
            attempt_digest = hashlib.sha256(attempt_key.encode("utf-8")).hexdigest()[
                :24
            ]
            attempt_root = (
                run_dir
                / "engine_attempts"
                / stage
                / attempt_digest
                / f"attempt-{os.getpid()}-{os.urandom(8).hex()}"
            )
            raw = selected_executor(
                candidate=candidate,
                seed=seed,
                stage=stage,
                run_dir=run_dir,
                plan=plan.manifest,
                validated_plan=plan,
                attempt_root=attempt_root,
            )
            if execution_mode == OFFICIAL_EXECUTION_MODE:
                _assert_runtime_dependencies_current(plan)
            if not isinstance(raw, Mapping):
                raise V4ProtocolError("V4 executor must return a mapping")
            metrics, executor_proof = _executor_output(
                raw,
                candidate=candidate,
                seed=seed,
                plan=plan,
                injected=injected_executor,
            )
            if stage == "holdout" and execution_mode == OFFICIAL_EXECUTION_MODE:
                case_dir = _coarse_case_dir(raw, run_dir, candidate, seed)
                shipment_trace = _write_holdout_shipment_trace(
                    plan=plan,
                    run_dir=run_dir,
                    candidate=candidate,
                    seed=seed,
                    source_csv=(case_dir / SHIPMENT_TRACE_SOURCE_RELATIVE_PATH),
                )
                _assert_runtime_dependencies_current(plan)
            mode = "execute_fresh_holdout" if stage == "holdout" else "execute"
        unsigned: dict[str, Any] = {
            "schema_version": EVIDENCE_SCHEMA_VERSION,
            "plan_signature": plan.manifest["plan_signature"],
            "stage": stage,
            "candidate_key": candidate.key,
            "candidate_id": candidate.candidate_id,
            "target_group": candidate.target_group,
            "seed": seed,
            "evidence_mode": mode,
            "graph_sha256": plan.manifest["inventory"][candidate.key]["graph_sha256"],
            "engine_sha256": plan.manifest["source_hashes"]["engine_sha256"],
            "metrics": metrics,
            "source_evidence": source_proof,
            "executor_proof": executor_proof,
            "shipment_trace": shipment_trace,
            "valid": True,
            "created_at_utc": _now(),
        }
        payload = {**unsigned, "evidence_signature": stable_sha256(unsigned)}
        _validate_v4_evidence(
            payload,
            plan=plan,
            run_dir=run_dir,
            stage=stage,
            candidate=candidate,
            seed=seed,
            execution_mode=execution_mode,
        )
        _write_json(_evidence_path(run_dir, stage, candidate.key, seed), payload)
        _prune_real_executor_case(executor_proof or {}, run_dir, candidate, seed)
        return payload

    with _run_lock(run_dir):
        if execution_mode == OFFICIAL_EXECUTION_MODE:
            _assert_runtime_dependencies_current(plan)
        _validate_existing_evidence_inventory(run_dir, stage, jobs)
        _validate_shipment_trace_inventory(
            plan,
            run_dir,
            stage,
            jobs,
            execution_mode,
            require_complete=False,
        )
        completed, missing = _collect_existing_stage_evidence(
            plan, run_dir, stage, jobs, execution_mode
        )
        _validate_existing_stage_progress(plan, run_dir, stage, len(jobs))
        _write_progress(plan, run_dir, stage, len(completed), len(jobs), "running", "")
        try:
            with ThreadPoolExecutor(max_workers=max_workers) as pool:
                pending_jobs = iter(missing)
                futures = {}
                for _ in range(max_workers):
                    try:
                        candidate, seed = next(pending_jobs)
                    except StopIteration:
                        break
                    futures[pool.submit(execute, candidate, seed)] = (candidate, seed)
                while futures:
                    future = next(as_completed(futures))
                    candidate, seed = futures.pop(future)
                    try:
                        payload = future.result()
                    except BaseException:
                        for queued in futures:
                            queued.cancel()
                        raise
                    _validate_v4_evidence(
                        payload,
                        plan=plan,
                        run_dir=run_dir,
                        stage=stage,
                        candidate=candidate,
                        seed=seed,
                        execution_mode=execution_mode,
                    )
                    completed[(candidate.key, seed)] = payload
                    _write_progress(
                        plan,
                        run_dir,
                        stage,
                        len(completed),
                        len(jobs),
                        "running",
                        "",
                    )
                    try:
                        next_candidate, next_seed = next(pending_jobs)
                    except StopIteration:
                        continue
                    futures[pool.submit(execute, next_candidate, next_seed)] = (
                        next_candidate,
                        next_seed,
                    )
        except BaseException as exc:
            completed, _missing = _collect_existing_stage_evidence(
                plan, run_dir, stage, jobs, execution_mode
            )
            _write_progress(
                plan, run_dir, stage, len(completed), len(jobs), "failed", str(exc)
            )
            raise
        if len(completed) != len(jobs):
            raise V4ProtocolError(
                "V4 stage did not produce its complete evidence matrix"
            )
        _validate_shipment_trace_inventory(
            plan,
            run_dir,
            stage,
            jobs,
            execution_mode,
            require_complete=True,
        )
        return _write_progress(
            plan, run_dir, stage, len(completed), len(jobs), "complete", ""
        )


def _write_progress(
    plan: ValidatedPlan,
    run_dir: Path,
    stage: str,
    completed: int,
    expected: int,
    status: str,
    error: str,
) -> dict[str, Any]:
    execution_mode = _registered_execution_mode(plan, run_dir)
    unsigned = {
        "schema_version": f"{SCHEMA_VERSION}.{stage}.progress",
        "plan_signature": plan.manifest["plan_signature"],
        "stage": stage,
        "status": status,
        "completed_case_count": completed,
        "expected_case_count": expected,
        "execution_mode": execution_mode,
        "publishable": execution_mode == OFFICIAL_EXECUTION_MODE,
        "error": error,
        "updated_at_utc": _now(),
    }
    payload = {**unsigned, "progress_signature": stable_sha256(unsigned)}
    _write_json(run_dir / f"{stage}_progress.json", payload)
    return payload


_PROGRESS_FIELDS = {
    "schema_version",
    "plan_signature",
    "stage",
    "status",
    "completed_case_count",
    "expected_case_count",
    "execution_mode",
    "publishable",
    "error",
    "updated_at_utc",
    "progress_signature",
}


def _validate_progress_document(
    plan: ValidatedPlan,
    run_dir: Path,
    progress: Mapping[str, Any],
    stage: str,
    expected: int,
) -> dict[str, Any]:
    _verify_self_signature(progress, "progress_signature", f"V4 {stage} progress")
    completed = progress.get("completed_case_count")
    declared_expected = progress.get("expected_case_count")
    status = progress.get("status")
    error = progress.get("error")
    execution_mode = _registered_execution_mode(plan, run_dir)
    if (
        set(progress) != _PROGRESS_FIELDS
        or progress.get("schema_version") != f"{SCHEMA_VERSION}.{stage}.progress"
        or progress.get("plan_signature") != plan.manifest["plan_signature"]
        or progress.get("stage") != stage
        or status not in {"running", "failed", "complete"}
        or type(completed) is not int
        or not 0 <= completed <= expected
        or type(declared_expected) is not int
        or declared_expected != expected
        or progress.get("execution_mode") != execution_mode
        or progress.get("publishable")
        is not (execution_mode == OFFICIAL_EXECUTION_MODE)
        or not isinstance(error, str)
        or (status in {"running", "complete"} and error != "")
        or (status == "complete" and completed != expected)
        or not isinstance(progress.get("updated_at_utc"), str)
        or not progress.get("updated_at_utc")
    ):
        raise V4ProtocolError(f"Invalid signed V4 {stage} progress")
    return dict(progress)


def _validate_existing_stage_progress(
    plan: ValidatedPlan, run_dir: Path, stage: str, expected: int
) -> dict[str, Any] | None:
    path = run_dir / f"{stage}_progress.json"
    if not path.exists():
        return None
    return _validate_progress_document(plan, run_dir, _read_json(path), stage, expected)


def _validate_stage_progress(
    plan: ValidatedPlan, run_dir: Path, stage: str, expected: int
) -> dict[str, Any]:
    progress = _validate_progress_document(
        plan,
        run_dir,
        _read_json(run_dir / f"{stage}_progress.json"),
        stage,
        expected,
    )
    if progress["status"] != "complete":
        raise V4ProtocolError(f"V4 {stage} progress is not signed and complete")
    return progress


def _load_stage_evidence(
    plan: ValidatedPlan, run_dir: Path, stage: str
) -> dict[tuple[str, int], dict[str, Any]]:
    execution_mode = _registered_execution_mode(plan, run_dir)
    jobs = _stage_jobs(plan, run_dir, stage)
    expected_paths = {
        _evidence_path(run_dir, stage, candidate.key, seed).resolve()
        for candidate, seed in jobs
    }
    directory = run_dir / "evidence" / stage
    actual_paths = {
        path.resolve() for path in directory.glob("*.json") if path.is_file()
    }
    if actual_paths != expected_paths:
        raise V4ProtocolError(
            f"{stage} must contain exactly {len(expected_paths)} JSON proofs"
        )
    _validate_stage_progress(plan, run_dir, stage, len(jobs))
    loaded: dict[tuple[str, int], dict[str, Any]] = {}
    for candidate, seed in jobs:
        path = _evidence_path(run_dir, stage, candidate.key, seed)
        if not path.is_file():
            raise V4ProtocolError(f"Incomplete {stage} evidence")
        loaded[(candidate.key, seed)] = _validate_v4_evidence(
            _read_json(path),
            plan=plan,
            run_dir=run_dir,
            stage=stage,
            candidate=candidate,
            seed=seed,
            execution_mode=execution_mode,
        )
    _validate_shipment_trace_inventory(
        plan,
        run_dir,
        stage,
        jobs,
        execution_mode,
        require_complete=True,
    )
    return loaded


def _linear_quantile(values: Sequence[float], probability: float) -> float:
    ordered = sorted(float(value) for value in values)
    if not ordered:
        raise V4ProtocolError("A quantile requires at least one value")
    position = (len(ordered) - 1) * probability
    lower = int(math.floor(position))
    upper = int(math.ceil(position))
    if lower == upper:
        return ordered[lower]
    fraction = position - lower
    return ordered[lower] + fraction * (ordered[upper] - ordered[lower])


def _validate_paired_demand(
    evidence: Mapping[tuple[str, int], Mapping[str, Any]],
    candidate_keys: Sequence[str],
    seeds: Sequence[int],
) -> None:
    if not candidate_keys:
        raise V4ProtocolError("Paired demand validation requires candidates")
    reference_key = candidate_keys[0]
    for seed in seeds:
        reference = evidence[(reference_key, seed)]["metrics"]
        for candidate_key in candidate_keys[1:]:
            metrics = evidence[(candidate_key, seed)]["metrics"]
            for field in (
                "demand_qty_268091",
                "demand_qty_268967",
                "demand_qty_global",
            ):
                if not math.isclose(
                    float(metrics[field]),
                    float(reference[field]),
                    rel_tol=DEMAND_REL_TOLERANCE,
                    abs_tol=DEMAND_ABS_TOLERANCE,
                ):
                    raise V4ProtocolError(
                        "Demand mismatch across paired candidates for "
                        f"seed={seed}, field={field}, candidate={candidate_key}"
                    )


def _candidate_summary(
    candidate: Candidate, rows: Sequence[Mapping[str, Any]], inner: bool
) -> dict[str, Any]:
    if len(rows) != 30:
        raise V4ProtocolError("Every candidate requires exactly 30 paired seeds")
    services: dict[str, list[float]] = {
        field: [float(row["metrics"][field]) for row in rows]
        for field in (
            "system_on_due_service",
            "on_due_service_268091",
            "on_due_service_268967",
        )
    }
    pooled: dict[str, float] = {}
    for field, demand_field, on_due_field in (
        ("system_on_due_service", "demand_qty_global", "on_due_qty_global"),
        ("on_due_service_268091", "demand_qty_268091", "on_due_qty_268091"),
        ("on_due_service_268967", "demand_qty_268967", "on_due_qty_268967"),
    ):
        demand = sum(float(row["metrics"][demand_field]) for row in rows)
        pooled[field] = (
            sum(float(row["metrics"][on_due_field]) for row in rows) / demand
        )
    medians = {field: median(values) for field, values in services.items()}
    global_iqr = _linear_quantile(
        services["system_on_due_service"], 0.75
    ) - _linear_quantile(services["system_on_due_service"], 0.25)
    loo_global: list[float] = []
    for omitted in range(len(rows)):
        kept = [row for index, row in enumerate(rows) if index != omitted]
        demand = sum(float(row["metrics"]["demand_qty_global"]) for row in kept)
        on_due = sum(float(row["metrics"]["on_due_qty_global"]) for row in kept)
        loo_global.append(on_due / demand)
    if candidate.target_group == "op_100":
        admissible = medians["system_on_due_service"] >= REFERENCE_MINIMUM and all(
            pooled[field] >= REFERENCE_MINIMUM
            for field in (
                "system_on_due_service",
                "on_due_service_268091",
                "on_due_service_268967",
            )
        )
        global_errors = [
            abs(1.0 - pooled["system_on_due_service"]),
            abs(1.0 - medians["system_on_due_service"]),
            *(abs(1.0 - value) for value in loo_global),
        ]
    else:
        band = (
            DEVELOPMENT_INNER_BANDS[candidate.target_group]
            if inner
            else OUTER_BANDS[candidate.target_group]
        )
        outer = OUTER_BANDS[candidate.target_group]
        admissible = (
            band[0] <= pooled["system_on_due_service"] <= band[1]
            and band[0] <= medians["system_on_due_service"] <= band[1]
            and pooled["on_due_service_268091"] < NON_SATURATION_LIMIT
            and pooled["on_due_service_268967"] < NON_SATURATION_LIMIT
            and (
                not inner or all(outer[0] <= value <= outer[1] for value in loo_global)
            )
        )
        target = TARGETS[candidate.target_group]
        global_errors = [
            abs(pooled["system_on_due_service"] - target),
            abs(medians["system_on_due_service"] - target),
            *(abs(value - target) for value in loo_global),
        ]
    maximum_error = max(global_errors)
    total_error = sum(global_errors)
    product_gap_pp = 100.0 * abs(
        pooled["on_due_service_268091"] - pooled["on_due_service_268967"]
    )
    return {
        "candidate": _candidate_payload(candidate),
        "pooled": pooled,
        "median": medians,
        "leave_one_out_global": loo_global,
        "admissible_individually": admissible,
        "maximum_absolute_global_target_error": maximum_error,
        "total_absolute_global_target_error": total_error,
        "global_service_iqr": global_iqr,
        "product_service_gap_pp": product_gap_pp,
        "product_gap_warning": product_gap_pp > PRODUCT_GAP_WARNING_PP + 1e-12,
        "demand_totals": {
            product: sum(float(row["metrics"][f"demand_qty_{product}"]) for row in rows)
            for product in PRODUCTS
        },
        "service_by_seed": services,
    }


def _pair_score(
    high: Mapping[str, Any],
    low: Mapping[str, Any],
    *,
    joint_order_count: int,
    pf967_order_count: int,
) -> tuple[Any, ...]:
    high_candidate = high["candidate"]
    low_candidate = low["candidate"]
    numeric = (
        max(
            high["maximum_absolute_global_target_error"],
            low["maximum_absolute_global_target_error"],
        ),
        -int(joint_order_count),
        -int(pf967_order_count),
        max(high["product_service_gap_pp"], low["product_service_gap_pp"]),
        high["product_service_gap_pp"] + low["product_service_gap_pp"],
        max(high["global_service_iqr"], low["global_service_iqr"]),
        high["global_service_iqr"] + low["global_service_iqr"],
        high_candidate["offset_days_268091"],
        high_candidate["offset_days_268967"],
        low_candidate["offset_days_268091"],
        low_candidate["offset_days_268967"],
    )
    return tuple(round(float(value), 12) for value in numeric)


def _paired_bootstrap_global(
    rows_by_group: Mapping[str, Sequence[Mapping[str, Any]]],
) -> dict[str, dict[str, float]]:
    rng = random.Random(BOOTSTRAP_SEED)
    indices = [
        [rng.randrange(len(EXPECTED_HOLDOUT_SEEDS)) for _ in EXPECTED_HOLDOUT_SEEDS]
        for _ in range(BOOTSTRAP_REPLICATES)
    ]
    result: dict[str, dict[str, float]] = {}
    for group, rows in rows_by_group.items():
        values: list[float] = []
        for sample in indices:
            demand = sum(
                float(rows[index]["metrics"]["demand_qty_global"]) for index in sample
            )
            on_due = sum(
                float(rows[index]["metrics"]["on_due_qty_global"]) for index in sample
            )
            values.append(on_due / demand)
        result[group] = {
            "ci95_low": _linear_quantile(values, 0.025),
            "ci95_high": _linear_quantile(values, 0.975),
        }
    return result


def _ordered_pair(
    reference: Mapping[str, Any],
    high: Mapping[str, Any],
    low: Mapping[str, Any],
) -> tuple[bool, int, int]:
    fields = (
        "system_on_due_service",
        "on_due_service_268091",
        "on_due_service_268967",
    )
    pooled = all(
        reference["pooled"][field] > high["pooled"][field] > low["pooled"][field]
        for field in fields
    )
    joint = sum(
        all(
            reference["service_by_seed"][field][index]
            > high["service_by_seed"][field][index]
            > low["service_by_seed"][field][index]
            for field in fields
        )
        for index in range(30)
    )
    pf967 = sum(
        reference["service_by_seed"]["on_due_service_268967"][index]
        > high["service_by_seed"]["on_due_service_268967"][index]
        > low["service_by_seed"]["on_due_service_268967"][index]
        for index in range(30)
    )
    return pooled, joint, pf967


def _build_development_selection(
    plan: ValidatedPlan,
    evidence: Mapping[tuple[str, int], Mapping[str, Any]],
    *,
    execution_mode: str,
) -> dict[str, Any]:
    by_key = {candidate.key: candidate for candidate in plan.candidates}
    _validate_paired_demand(evidence, tuple(by_key), DEVELOPMENT_SEEDS)
    summaries = {
        key: _candidate_summary(
            candidate,
            [evidence[(key, seed)] for seed in DEVELOPMENT_SEEDS],
            True,
        )
        for key, candidate in by_key.items()
    }
    reference = summaries["op100_source"]
    highs = [
        summary
        for key, summary in summaries.items()
        if by_key[key].target_group == "op_93" and summary["admissible_individually"]
    ]
    lows = [
        summary
        for key, summary in summaries.items()
        if by_key[key].target_group == "op_80" and summary["admissible_individually"]
    ]
    eligible: list[dict[str, Any]] = []
    if reference["admissible_individually"]:
        for high in highs:
            for low in lows:
                high_candidate = by_key[high["candidate"]["key"]]
                low_candidate = by_key[low["candidate"]["key"]]
                monotone = (
                    low_candidate.offset_days_268091
                    >= high_candidate.offset_days_268091
                    and low_candidate.offset_days_268967
                    >= high_candidate.offset_days_268967
                )
                pooled, joint, pf967 = _ordered_pair(reference, high, low)
                if monotone and pooled and joint >= MIN_ORDERED_SEEDS:
                    eligible.append(
                        {
                            "op93_candidate_key": high_candidate.key,
                            "op80_candidate_key": low_candidate.key,
                            "same_seed_joint_strict_order_count": joint,
                            "same_seed_pf268967_strict_order_count": pf967,
                            "selection_score_v4": list(
                                _pair_score(
                                    high,
                                    low,
                                    joint_order_count=joint,
                                    pf967_order_count=pf967,
                                )
                            ),
                        }
                    )
    eligible.sort(key=lambda row: tuple(row["selection_score_v4"]))
    winner = eligible[0] if eligible else None
    unsigned = {
        "schema_version": SELECTION_SCHEMA_VERSION,
        "plan_signature": plan.manifest["plan_signature"],
        "status": (
            "development_selected_pending_fresh_holdout"
            if winner
            else "development_failed_no_holdout"
        ),
        "development_seeds": list(DEVELOPMENT_SEEDS),
        "holdout_seeds_sealed_and_unread": list(EXPECTED_HOLDOUT_SEEDS),
        "holdout_cases_read": 0,
        "execution_mode": execution_mode,
        "publishable": execution_mode == OFFICIAL_EXECUTION_MODE,
        "development_evidence_signature_set_sha256": stable_sha256(
            sorted(str(row["evidence_signature"]) for row in evidence.values())
        ),
        "candidate_summaries": summaries,
        "eligible_pairs": eligible,
        "selected_candidate_keys": (
            {
                "op_100": "op100_source",
                "op_93": winner["op93_candidate_key"],
                "op_80": winner["op80_candidate_key"],
            }
            if winner
            else None
        ),
        "selection_contract": plan.manifest["selection_contract"],
        "retuning_after_development": False,
    }
    return {**unsigned, "selection_signature": stable_sha256(unsigned)}


def finalize_stage(
    plan_dir: Path,
    run_dir: Path,
    *,
    stage: str,
    test_only: bool = False,
) -> dict[str, Any]:
    """Finalize development selection or the one-shot fresh holdout."""

    if stage not in {"development", "holdout"}:
        raise V4ProtocolError("Stage must be development or holdout")
    plan = validate_plan(plan_dir, verify_runtime_dependencies=not test_only)
    run_dir = run_dir.resolve()
    _validate_run_location(plan, run_dir)
    execution_mode = TEST_ONLY_EXECUTION_MODE if test_only else OFFICIAL_EXECUTION_MODE
    if _read_json(run_dir / "run_manifest.json") != _run_manifest(plan, execution_mode):
        raise V4ProtocolError(
            "Official and test-only V4 finalizations use distinct run registrations"
        )
    if stage == "development":
        _assert_holdout_unseen(run_dir)
    evidence = _load_stage_evidence(plan, run_dir, stage)
    by_key = {candidate.key: candidate for candidate in plan.candidates}
    if stage == "development":
        result = _build_development_selection(
            plan, evidence, execution_mode=execution_mode
        )
        output = run_dir / "development_selection.json"
        signature_field = "selection_signature"
    elif stage == "holdout":
        selection = _load_development_selection(plan, run_dir)
        chosen = selection["selected_candidate_keys"]
        ordered_keys = [chosen[group] for group in TARGETS]
        _validate_paired_demand(evidence, ordered_keys, EXPECTED_HOLDOUT_SEEDS)
        rows_by_group = {
            group: [evidence[(key, seed)] for seed in EXPECTED_HOLDOUT_SEEDS]
            for group, key in chosen.items()
        }
        summaries = {
            group: _candidate_summary(
                by_key[key],
                rows_by_group[group],
                False,
            )
            for group, key in chosen.items()
        }
        bootstrap = _paired_bootstrap_global(rows_by_group)
        pooled, joint, pf967 = _ordered_pair(
            summaries["op_100"], summaries["op_93"], summaries["op_80"]
        )
        accepted = (
            all(summary["admissible_individually"] for summary in summaries.values())
            and pooled
            and joint >= MIN_ORDERED_SEEDS
        )
        unsigned = {
            "schema_version": HOLDOUT_SCHEMA_VERSION,
            "plan_signature": plan.manifest["plan_signature"],
            "development_selection_signature": selection["selection_signature"],
            "status": "holdout_validated_30_fresh_seeds"
            if accepted
            else "holdout_rejected_no_retuning",
            "holdout_seeds": list(EXPECTED_HOLDOUT_SEEDS),
            "holdout_evidence_case_count": len(evidence),
            "execution_mode": execution_mode,
            "publishable": execution_mode == OFFICIAL_EXECUTION_MODE,
            "holdout_evidence_signature_set_sha256": stable_sha256(
                sorted(str(row["evidence_signature"]) for row in evidence.values())
            ),
            "selected_candidate_keys": chosen,
            "state_summaries": summaries,
            "paired_bootstrap_global_descriptive_only": {
                "contract": plan.manifest["holdout_contract"]["bootstrap"],
                "intervals": bootstrap,
            },
            "product_gap_warning_above_5pp_by_state": {
                group: summary["product_gap_warning"]
                for group, summary in summaries.items()
            },
            "pooled_strict_order": pooled,
            "same_seed_joint_strict_order_count": joint,
            "same_seed_pf268967_strict_order_count": pf967,
            "accepted": accepted,
            "retuning_after_holdout": False,
            "failure_rule": "publish_no_go_and_require_new_fresh_cohort",
        }
        result = {**unsigned, "holdout_signature": stable_sha256(unsigned)}
        output = run_dir / "holdout_result.json"
        signature_field = "holdout_signature"
    else:
        raise V4ProtocolError("Stage must be development or holdout")
    if execution_mode == OFFICIAL_EXECUTION_MODE:
        _assert_runtime_dependencies_current(plan)
    if output.exists():
        existing = _read_json(output)
        if (
            existing.get(signature_field) != result[signature_field]
            or existing != result
        ):
            raise V4ProtocolError(f"Existing {stage} finalization differs")
    else:
        _write_json(output, result)
    return result


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    decision = sub.add_parser(
        "decision", help="Create the signed op80 keep/candidates decision"
    )
    decision.add_argument("--output", type=Path, required=True)
    decision.add_argument(
        "--source-campaign-manifest",
        type=Path,
        default=DEFAULT_SOURCE_CAMPAIGN_MANIFEST,
    )
    decision.add_argument("--mode", choices=("keep", "candidates"), required=True)
    decision.add_argument("--rationale", required=True)
    decision.add_argument("--candidates-json", type=Path)
    plan = sub.add_parser(
        "plan", help="Create the signed V4 plan; never run the engine"
    )
    plan.add_argument("--output-dir", type=Path, default=DEFAULT_PLAN_OUTPUT)
    plan.add_argument(
        "--source-campaign-manifest",
        type=Path,
        default=DEFAULT_SOURCE_CAMPAIGN_MANIFEST,
    )
    plan.add_argument("--op80-decision", type=Path, required=True)
    validate = sub.add_parser("validate", help="Revalidate the complete signed V4 plan")
    validate.add_argument("--plan-dir", type=Path, default=DEFAULT_PLAN_OUTPUT)
    run = sub.add_parser("run", help="Execute or resume a complete frozen V4 stage")
    run.add_argument("--plan-dir", type=Path, default=DEFAULT_PLAN_OUTPUT)
    run.add_argument("--run-dir", type=Path, default=DEFAULT_RUN_OUTPUT)
    run.add_argument("--stage", choices=("development", "holdout"), required=True)
    run.add_argument("--workers", type=int, choices=(1, 2), default=2)
    finalize = sub.add_parser("finalize", help="Finalize a complete V4 stage")
    finalize.add_argument("--plan-dir", type=Path, default=DEFAULT_PLAN_OUTPUT)
    finalize.add_argument("--run-dir", type=Path, default=DEFAULT_RUN_OUTPUT)
    finalize.add_argument("--stage", choices=("development", "holdout"), required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.command == "decision":
        print(
            write_op80_decision(
                args.output,
                source_campaign_manifest=args.source_campaign_manifest,
                mode=args.mode,
                rationale=args.rationale,
                candidates_json=args.candidates_json,
            )
        )
    elif args.command == "plan":
        path = prepare_plan(
            args.output_dir,
            source_campaign_manifest=args.source_campaign_manifest,
            op80_decision_path=args.op80_decision,
        )
        print(path)
    elif args.command == "validate":
        print(validate_plan(args.plan_dir).manifest["plan_signature"])
    elif args.command == "run":
        print(
            json.dumps(
                run_stage(
                    args.plan_dir,
                    args.run_dir,
                    stage=args.stage,
                    max_workers=args.workers,
                ),
                ensure_ascii=False,
            )
        )
    else:
        print(
            json.dumps(
                finalize_stage(args.plan_dir, args.run_dir, stage=args.stage),
                ensure_ascii=False,
            )
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
