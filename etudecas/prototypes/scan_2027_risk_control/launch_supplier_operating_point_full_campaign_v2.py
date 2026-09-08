#!/usr/bin/env python3
"""Launch or resume discovery and 18 isolated shards of the V2 campaign.

The launcher never runs simulation logic itself.  It reads the signed campaign
plan, completes the signed 93-run operating-point/target discovery and its
scientific go/no-go first, then starts the additive V2 runner once per shard.
Concurrency is limited to two shards and two engine workers per shard.  Every
phase owns a separate log and the launcher writes one atomic progress file.

On Windows ``--detach`` starts a hidden, detached child launcher and returns its
PID.  The detached child uses the same idempotent completion checks as a normal
invocation.  A failed shard stops new scheduling; already running shards are
allowed to finish so no engine process is orphaned deliberately.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import subprocess
import sys
import time
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, BinaryIO, Callable, Mapping, Protocol, Sequence


REPO_ROOT = Path(__file__).resolve().parents[3]
RUNNER = (
    REPO_ROOT
    / "etudecas"
    / "prototypes"
    / "scan_2027_risk_control"
    / "supplier_operating_point_full_campaign_v2.py"
)
DEFAULT_CAMPAIGN_ROOT = (
    Path(r"C:\dev\lca-simu-pr40-validation-artifacts-20260726")
    / "supplier_operating_point_full_campaign_v2_20260904_v3"
)

SCHEMA_VERSION = "etudecas.supplier_operating_point_full_campaign.v2.launcher.v1"
CONTRACT_SCHEMA_VERSION = f"{SCHEMA_VERSION}.contract"
PROGRESS_SCHEMA_VERSION = f"{SCHEMA_VERSION}.progress"
INPUT_SCHEMA_VERSION = "etudecas.supplier_operating_point_full_campaign.v2"
SHARD_PROGRESS_SCHEMA_VERSION = f"{INPUT_SCHEMA_VERSION}.progress.v1"
EXPECTED_SHARD_COUNT = 18
EXPECTED_CASES_PER_SHARD = 185
EXPECTED_TOTAL_CASES = 3330
EXPECTED_DISCOVERY_RUNS = 93
EXPECTED_TARGET_ROWS = 3 * 30 * 18
EXPECTED_OPERATING_POINTS = ("op_100", "op_93", "op_80")
EXPECTED_MECHANISMS = {"transport_delay", "planned_delivery_shortfall"}
EXPECTED_PREFLIGHT_STATUS = "holdout_validated_30_seed"
EXPECTED_PREFLIGHT_SCHEMA_VERSION = (
    f"{INPUT_SCHEMA_VERSION}.operating_point_preflight.v2"
)
EXPECTED_CONTRACT_REVISION = (
    "fixed_42d_holdout_gated_adaptive_compact_probe_v5_2026_09_04"
)
V1_POINTS_PRODUCER = "v1_calibration"
V1_POINTS_SCHEMA_VERSION = (
    "etudecas.multiseed_operating_point_calibration.v1.selected_operating_points"
)
V1_POINTS_PENDING_STATUS = "selected_on_five_seed_calibration_pending_holdout"
V1_SELECTION_SCHEMA_VERSION = (
    "etudecas.multiseed_operating_point_calibration.v1.selection"
)
V1_SELECTION_STATUS = "calibration_selected"
V2_POINTS_PRODUCER = "v2_refinement"
V2_POINTS_SCHEMA_VERSION = (
    "etudecas.multiseed_operating_point_refinement.v2.selected_operating_points"
)
V2_POINTS_PENDING_STATUS = "selected_on_five_seed_refinement_pending_30_seed_holdout"
V2_SELECTION_SCHEMA_VERSION = (
    "etudecas.multiseed_operating_point_refinement.v2.selection"
)
V2_SELECTION_STATUS = "five_seed_loo_screen_passed_pending_holdout"
V3_POINTS_PRODUCER = "v3_refinement"
V3_POINTS_SCHEMA_VERSION = (
    "etudecas.multiseed_operating_point_refinement.v3.selected_operating_points"
)
V3_POINTS_PENDING_STATUS = "selected_on_five_seed_refinement_v3_pending_30_seed_holdout"
V3_SELECTION_SCHEMA_VERSION = (
    "etudecas.multiseed_operating_point_refinement.v3.selection"
)
V3_SELECTION_STATUS = "five_seed_loo_screen_v3_passed_pending_holdout"
V3_REFINEMENT_MODULE = RUNNER.with_name(
    "supplier_balanced_product_delay_multiseed_refinement_v3.py"
)
V3_REFINEMENT_MODULE_SHA256 = (
    "707cbd79b8758b48a70665250d15e6af547fe0ad01b7bac44bad66ff14a9858e"
)
OPERATING_POINT_SOURCE_CONTRACTS = {
    (V1_POINTS_PRODUCER, V1_POINTS_SCHEMA_VERSION, V1_POINTS_PENDING_STATUS): (
        V1_SELECTION_SCHEMA_VERSION,
        V1_SELECTION_STATUS,
        False,
    ),
    (V2_POINTS_PRODUCER, V2_POINTS_SCHEMA_VERSION, V2_POINTS_PENDING_STATUS): (
        V2_SELECTION_SCHEMA_VERSION,
        V2_SELECTION_STATUS,
        True,
    ),
    (V3_POINTS_PRODUCER, V3_POINTS_SCHEMA_VERSION, V3_POINTS_PENDING_STATUS): (
        V3_SELECTION_SCHEMA_VERSION,
        V3_SELECTION_STATUS,
        True,
    ),
}
# Kept as a public compatibility alias for callers that build legacy V1 fixtures.
EXPECTED_PENDING_POINT_STATUS = V1_POINTS_PENDING_STATUS
EXPECTED_CAMPAIGN_SEEDS = tuple(range(340287, 340317))
EXPECTED_HOLDOUT_CONTRACT_FIELDS = {
    "status_only_if_passed": EXPECTED_PREFLIGHT_STATUS,
    "fixed_point_count": 3,
    "seed_count": 30,
    "baseline_case_count": 90,
    "seeds": list(EXPECTED_CAMPAIGN_SEEDS),
    "service_window": {"start_day": 0, "end_day": 719, "day_count": 720},
    "op100_minimum_global_and_each_product": 0.985,
    "op93_global_pooled_and_median_band": [0.915, 0.945],
    "op80_global_pooled_and_median_band": [0.785, 0.815],
    "degraded_product_strictly_below": 0.995,
    "pooled_strict_order_required_for": [
        "system_on_due_service",
        "on_due_service_268091",
        "on_due_service_268967",
    ],
    "same_seed_joint_strict_order_required": 24,
    "bootstrap_repetitions_descriptive": 10_000,
    "retuning_after_holdout": False,
}
MAX_PARALLEL_SHARDS = 2
MAX_WORKERS_PER_SHARD = 2
DEFAULT_POLL_SECONDS = 5.0
DEFAULT_ACTIVE_PROGRESS_SECONDS = 1800.0
ES_SYSTEM_REQUIRED = 0x00000001
ES_CONTINUOUS = 0x80000000
WAKEFULNESS_SCHEMA_VERSION = f"{SCHEMA_VERSION}.wakefulness.v1"


class ProcessLike(Protocol):
    pid: int

    def poll(self) -> int | None: ...


PopenFactory = Callable[..., ProcessLike]


@dataclass(frozen=True)
class Shard:
    shard_id: str
    shard_index: int
    operating_point_id: str
    seed_block: int
    seed_ids: tuple[int, ...]


@dataclass
class ActiveShard:
    shard: Shard
    process: ProcessLike
    log_handle: BinaryIO
    log_path: Path
    started_monotonic: float
    started_at_utc: str
    command: list[str]


class WindowsSystemAwake:
    """Keep Windows system sleep disabled, without forcing the display awake."""

    def __init__(
        self,
        campaign_root: Path,
        *,
        execution_state_setter: Callable[[int], int] | None = None,
        platform_name: str | None = None,
    ) -> None:
        self.campaign_root = campaign_root.resolve()
        self.execution_state_setter = execution_state_setter
        self.platform_name = platform_name or os.name
        self.state: dict[str, Any] = {}
        self.path = self.campaign_root / "launcher_wakefulness.json"

    def _write(self) -> None:
        _write_json_atomic(self.path, self.state)

    def _resolve_setter(self) -> Callable[[int], int]:
        if self.execution_state_setter is not None:
            return self.execution_state_setter
        import ctypes

        setter = ctypes.windll.kernel32.SetThreadExecutionState
        setter.argtypes = [ctypes.c_uint]
        setter.restype = ctypes.c_uint
        return setter

    def __enter__(self) -> dict[str, Any]:
        self.state = {
            "schema_version": WAKEFULNESS_SCHEMA_VERSION,
            "requested": True,
            "platform": self.platform_name,
            "scope": "system_sleep_only_display_sleep_allowed",
            "requested_flags": ES_CONTINUOUS | ES_SYSTEM_REQUIRED,
            "reset_flags": ES_CONTINUOUS,
            "status": "not_applicable_non_windows",
            "acquired": False,
            "released": False,
            "activated_at_utc": utc_now(),
            "released_at_utc": "",
            "error": "",
        }
        if self.platform_name == "nt":
            try:
                self.execution_state_setter = self._resolve_setter()
                result = int(
                    self.execution_state_setter(ES_CONTINUOUS | ES_SYSTEM_REQUIRED)
                )
                if result == 0:
                    raise OSError("SetThreadExecutionState returned 0")
                self.state.update(
                    {
                        "status": "active",
                        "acquired": True,
                        "activation_result": result,
                    }
                )
            except Exception as exc:  # fail-soft: campaign can still run
                self.state.update(
                    {
                        "status": "unavailable",
                        "error": f"{type(exc).__name__}: {exc}",
                    }
                )
        self._write()
        return self.state

    def __exit__(self, *_args: Any) -> None:
        if self.state.get("acquired"):
            try:
                if self.execution_state_setter is None:  # defensive only
                    raise RuntimeError("execution-state setter was lost")
                result = int(self.execution_state_setter(ES_CONTINUOUS))
                if result == 0:
                    raise OSError("SetThreadExecutionState reset returned 0")
                self.state.update(
                    {
                        "status": "released",
                        "released": True,
                        "release_result": result,
                    }
                )
            except Exception as exc:  # fail-soft, but preserve the failed reset
                self.state.update(
                    {
                        "status": "release_failed",
                        "error": f"{type(exc).__name__}: {exc}",
                    }
                )
        self.state["released_at_utc"] = utc_now()
        self._write()


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Invalid JSON: {path}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"JSON document must be an object: {path}")
    return payload


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def _write_json_atomic(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    temporary.replace(path)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _stable_sha256(payload: Any) -> str:
    raw = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _parse_utc(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _load_shards(manifest: Mapping[str, Any]) -> list[Shard]:
    raw = manifest.get("shards")
    if not isinstance(raw, list) or len(raw) != EXPECTED_SHARD_COUNT:
        raise ValueError("Campaign manifest must contain exactly 18 shard designs")
    shards: list[Shard] = []
    for row in raw:
        if not isinstance(row, Mapping):
            raise ValueError("Invalid shard design row")
        seeds = tuple(int(value) for value in row.get("seed_ids") or [])
        shard = Shard(
            shard_id=str(row.get("shard_id") or ""),
            shard_index=int(row.get("shard_index") or 0),
            operating_point_id=str(row.get("operating_point_id") or ""),
            seed_block=int(row.get("seed_block") or 0),
            seed_ids=seeds,
        )
        if (
            not shard.shard_id
            or shard.operating_point_id not in set(EXPECTED_OPERATING_POINTS)
            or shard.seed_block not in range(1, 7)
            or len(shard.seed_ids) != 5
            or int(row.get("total_rows") or 0) != EXPECTED_CASES_PER_SHARD
        ):
            raise ValueError(f"Invalid shard contract: {row}")
        shards.append(shard)
    if {shard.shard_index for shard in shards} != set(range(1, 19)):
        raise ValueError("Shard indices must be exactly 1 through 18")
    if len({shard.shard_id for shard in shards}) != EXPECTED_SHARD_COUNT:
        raise ValueError("Shard ids are not unique")
    expected_pairs = {
        (point_id, block_number)
        for point_id in EXPECTED_OPERATING_POINTS
        for block_number in range(1, 7)
    }
    if {
        (shard.operating_point_id, shard.seed_block) for shard in shards
    } != expected_pairs:
        raise ValueError(
            "Shard plan must cover each operating point x seed block exactly once"
        )
    block_seeds: dict[int, tuple[int, ...]] = {}
    for shard in shards:
        previous = block_seeds.setdefault(shard.seed_block, shard.seed_ids)
        if previous != shard.seed_ids:
            raise ValueError(
                "A seed block must be identical across all operating points"
            )
    planned_seeds = tuple(int(value) for value in manifest.get("seeds") or [])
    flattened = tuple(value for block in range(1, 7) for value in block_seeds[block])
    if len(set(flattened)) != 30 or planned_seeds != flattened:
        raise ValueError("Shard seed blocks do not match the 30 signed repetitions")
    return sorted(shards, key=lambda shard: shard.shard_index)


def _verify_signed_design(manifest: Mapping[str, Any]) -> None:
    unsigned_fields = {
        "campaign_signature",
        "status",
        "created_at_utc",
        "completed_at_utc",
        "target_discovery_status",
        "target_registry",
        "target_registry_sha256",
        "target_registry_signature",
        "target_exposure_comparability_status",
        "operating_point_preflight",
        "operating_point_preflight_sha256",
        "operating_point_preflight_signature",
        "operating_point_preflight_status",
        "target_discovery_completed_at_utc",
    }
    signed_design = {
        key: value for key, value in manifest.items() if key not in unsigned_fields
    }
    if _stable_sha256(signed_design) != manifest.get("campaign_signature"):
        raise ValueError("Campaign manifest signed design does not match its signature")


def _validate_manifest_sources(manifest: Mapping[str, Any]) -> None:
    for path_field, hash_field, label in (
        (
            "operating_points_source",
            "operating_points_source_sha256",
            "operating points",
        ),
        (
            "operating_points_calibration_plan",
            "operating_points_calibration_plan_sha256",
            "operating-point calibration plan",
        ),
        (
            "operating_points_selection",
            "operating_points_selection_sha256",
            "operating-point calibration selection",
        ),
        ("lane_reference_source", "lane_reference_source_sha256", "lane reference"),
        ("engine", "engine_sha256", "engine"),
        ("engine_profile", "engine_profile_sha256", "engine profile"),
    ):
        path = Path(str(manifest.get(path_field) or "")).resolve()
        expected_hash = str(manifest.get(hash_field) or "")
        if not path.is_file() or len(expected_hash) != 64:
            raise FileNotFoundError(f"Missing signed {label}: {path}")
        if _sha256_file(path) != expected_hash:
            raise ValueError(
                f"Signed {label} changed after the campaign plan was created"
            )


def _validate_operating_point_source_contract(manifest: Mapping[str, Any]) -> None:
    """Fail closed unless the manifest and source preserve one exact V1/V2/V3 chain."""

    manifest_contract = (
        str(manifest.get("operating_points_producer") or ""),
        str(manifest.get("operating_points_schema_version") or ""),
        str(manifest.get("operating_points_input_status") or ""),
    )
    selection_contract = OPERATING_POINT_SOURCE_CONTRACTS.get(manifest_contract)
    if selection_contract is None:
        raise ValueError(
            "Campaign operating points do not preserve an exact signed V1, V2 or V3 "
            "producer/schema/status contract"
        )
    expected_selection_schema, expected_selection_status, tracks_holdout_cases = (
        selection_contract
    )
    producer_module_raw = str(
        manifest.get("operating_points_producer_module") or ""
    ).strip()
    producer_module_sha256 = str(
        manifest.get("operating_points_producer_module_sha256") or ""
    )
    if producer_module_raw or producer_module_sha256:
        raise ValueError(
            "Campaign claims unsupported redundant producer identity fields"
        )
    if manifest_contract[0] == V3_POINTS_PRODUCER:
        if (
            not V3_REFINEMENT_MODULE.is_file()
            or _sha256_file(V3_REFINEMENT_MODULE) != V3_REFINEMENT_MODULE_SHA256
        ):
            raise ValueError("Signed V3 operating-point producer identity is invalid")

    source_path = Path(str(manifest.get("operating_points_source") or "")).resolve()
    source = _read_json(source_path)
    source_contract = (
        manifest_contract[0],
        str(source.get("schema_version") or ""),
        str(source.get("status") or ""),
    )
    if source_contract != manifest_contract:
        raise ValueError(
            "Signed operating-point source schema/status differs from its campaign "
            "producer contract"
        )

    unsigned_source = dict(source)
    source_artifact_signature = str(unsigned_source.pop("artifact_signature", "") or "")
    if (
        len(source_artifact_signature) != 64
        or source_artifact_signature != _stable_sha256(unsigned_source)
        or source_artifact_signature
        != str(manifest.get("operating_points_artifact_signature") or "")
    ):
        raise ValueError("Signed operating-point artifact signature is invalid")

    source_plan = source.get("plan")
    if not isinstance(source_plan, Mapping):
        raise ValueError("Signed operating-point source has no plan reference")
    source_plan_signature = str(source_plan.get("plan_signature") or "")
    plan_manifest = _read_json(
        Path(str(manifest.get("operating_points_calibration_plan") or "")).resolve()
    )
    manifest_plan_signature = str(
        manifest.get("operating_points_calibration_plan_signature") or ""
    )
    cohorts = manifest.get("operating_points_cohorts")
    holdout_contract = manifest.get("operating_points_holdout_contract")
    changed_holdout_fields = (
        [
            field
            for field, expected in EXPECTED_HOLDOUT_CONTRACT_FIELDS.items()
            if holdout_contract.get(field) != expected
        ]
        if isinstance(holdout_contract, Mapping)
        else list(EXPECTED_HOLDOUT_CONTRACT_FIELDS)
    )
    if (
        not isinstance(cohorts, Mapping)
        or not isinstance(holdout_contract, Mapping)
        or changed_holdout_fields
        or len(source_plan_signature) != 64
        or source_plan_signature != manifest_plan_signature
        or str(plan_manifest.get("plan_signature") or "") != manifest_plan_signature
        or source.get("source_hashes") != plan_manifest.get("source_hashes")
        or plan_manifest.get("cohorts") != cohorts
        or plan_manifest.get("holdout_contract") != holdout_contract
    ):
        raise ValueError("Signed operating-point plan signature chain is invalid")
    if (
        manifest_contract[0] == V3_POINTS_PRODUCER
        and dict(plan_manifest.get("source_hashes") or {}).get("v3_driver_sha256")
        != V3_REFINEMENT_MODULE_SHA256
    ):
        raise ValueError("Signed V3 operating-point producer identity is invalid")

    selection = _read_json(
        Path(str(manifest.get("operating_points_selection") or "")).resolve()
    )
    unsigned_selection = dict(selection)
    selection_signature = str(unsigned_selection.pop("selection_signature", "") or "")
    manifest_selection_signature = str(
        manifest.get("operating_points_selection_signature") or ""
    )
    if (
        selection.get("schema_version") != expected_selection_schema
        or selection.get("status") != expected_selection_status
        or len(selection_signature) != 64
        or selection_signature != _stable_sha256(unsigned_selection)
        or selection_signature != manifest_selection_signature
        or str(source.get("selection_signature") or "") != manifest_selection_signature
        or str(selection.get("plan_signature") or "") != manifest_plan_signature
        or selection.get("calibration_seeds") != list(cohorts.get("calibration") or [])
        or selection.get("holdout_seeds_sealed_and_unread")
        != list(cohorts.get("holdout_sealed") or [])
        or selection.get("selection_contract")
        != plan_manifest.get("selection_contract")
        or selection.get("fallback_required") is not False
    ):
        raise ValueError("Signed operating-point selection signature chain is invalid")

    if (
        source.get("cohorts") != cohorts
        or source.get("holdout_validated") is not False
        or source.get("simulation_hypotheses_not_observed_performance") is not True
    ):
        raise ValueError(
            "Signed operating-point source does not preserve the sealed holdout"
        )
    if not tracks_holdout_cases:
        return

    source_selection = source.get("selection")
    if (
        source.get("holdout_cases_read") != 0
        or source.get("holdout_contract") != holdout_contract
        or holdout_contract.get("status") != "sealed_unread"
        or holdout_contract.get("cases_in_this_plan") != 0
        or holdout_contract.get("selected_output_status") != manifest_contract[2]
        or not isinstance(source_selection, Mapping)
        or source_selection.get("relative_path") != "selection.json"
        or source_selection.get("schema_version") != expected_selection_schema
        or source_selection.get("selection_signature") != manifest_selection_signature
        or selection.get("holdout_cases_read") != 0
        or selection.get("holdout_contract") != holdout_contract
        or selection.get("holdout_launch_permitted") is not True
    ):
        raise ValueError(
            "Signed operating-point refinement does not preserve its sealed holdout"
        )


def load_campaign_plan(
    campaign_root: Path, runner: Path = RUNNER
) -> tuple[dict[str, Any], list[Shard]]:
    campaign_root = campaign_root.resolve()
    manifest_path = campaign_root / "campaign_manifest.json"
    shard_plan_path = campaign_root / "shard_plan.csv"
    if not manifest_path.is_file() or not shard_plan_path.is_file():
        raise FileNotFoundError(
            "Run the V2 runner in --mode plan before launching shards"
        )
    manifest = _read_json(manifest_path)
    if manifest.get("schema_version") != INPUT_SCHEMA_VERSION:
        raise ValueError("Unsupported V2 campaign manifest schema")
    if manifest.get("contract_revision") != EXPECTED_CONTRACT_REVISION:
        raise ValueError("Campaign manifest is not the signed six-week V5 contract")
    if str(manifest.get("status") or "") not in {"planned", "running", "complete"}:
        raise ValueError("Campaign manifest is not launchable")
    signature = str(manifest.get("campaign_signature") or "")
    if len(signature) != 64:
        raise ValueError("Campaign signature is missing")
    _verify_signed_design(manifest)
    counts = manifest.get("expected_counts") or {}
    if (
        int(counts.get("auxiliary_discovery_runs") or 0) != EXPECTED_DISCOVERY_RUNS
        or int(counts.get("baseline_rows") or 0) != 90
        or int(counts.get("incident_rows") or 0) != 3240
        or int(counts.get("shard_count") or 0) != EXPECTED_SHARD_COUNT
        or int(counts.get("rows_per_shard") or 0) != EXPECTED_CASES_PER_SHARD
        or int(counts.get("total_rows") or 0) != EXPECTED_TOTAL_CASES
    ):
        raise ValueError("Campaign expected counts do not match the full V2 matrix")
    if (
        manifest.get("quality_branch_included") is not False
        or manifest.get("availability_incident_included") is not False
    ):
        raise ValueError(
            "Campaign does not explicitly exclude quality/availability incidents"
        )
    if (
        manifest.get("operating_points_cohorts")
        != {
            "design": [340281],
            "calibration": list(range(340282, 340287)),
            "holdout_sealed": list(EXPECTED_CAMPAIGN_SEEDS),
        }
        or tuple(int(value) for value in manifest.get("seeds") or [])
        != EXPECTED_CAMPAIGN_SEEDS
    ):
        raise ValueError(
            "Campaign does not preserve the signed calibration/holdout split"
        )
    mechanisms = manifest.get("mechanisms") or []
    if (
        not isinstance(mechanisms, list)
        or {str(row.get("key") or "") for row in mechanisms if isinstance(row, Mapping)}
        != EXPECTED_MECHANISMS
    ):
        raise ValueError("Campaign mechanisms are not the signed V2 incident pair")
    _validate_manifest_sources(manifest)
    _validate_operating_point_source_contract(manifest)
    runner = runner.resolve()
    if not runner.is_file():
        raise FileNotFoundError(f"Missing V2 shard runner: {runner}")
    planned_runner = Path(str(manifest.get("runner") or "")).resolve()
    if planned_runner != runner:
        raise ValueError("Launcher runner path differs from the signed campaign runner")
    if _sha256_file(runner) != str(manifest.get("runner_sha256") or ""):
        raise ValueError("Signed V2 campaign runner changed after planning")
    shards = _load_shards(manifest)
    plan_rows = _read_csv(shard_plan_path)
    if len(plan_rows) != EXPECTED_SHARD_COUNT or {
        row.get("shard_id") for row in plan_rows
    } != {shard.shard_id for shard in shards}:
        raise ValueError("shard_plan.csv does not match campaign_manifest.json")
    by_id = {shard.shard_id: shard for shard in shards}
    for row in plan_rows:
        shard = by_id[str(row["shard_id"])]
        if (
            int(row.get("shard_index") or 0) != shard.shard_index
            or str(row.get("operating_point_id") or "") != shard.operating_point_id
            or int(row.get("seed_block") or 0) != shard.seed_block
            or int(row.get("total_rows") or 0) != EXPECTED_CASES_PER_SHARD
        ):
            raise ValueError(f"shard_plan.csv row changed for {shard.shard_id}")
    return manifest, shards


def build_shard_command(
    *,
    runner: Path,
    campaign_root: Path,
    manifest: Mapping[str, Any],
    shard: Shard,
    workers_per_shard: int,
    reuse_evidence_dirs: Sequence[Path] = (),
) -> list[str]:
    if workers_per_shard not in range(1, MAX_WORKERS_PER_SHARD + 1):
        raise ValueError("workers_per_shard must be 1 or 2")
    command = [
        sys.executable,
        str(runner.resolve()),
        "--mode",
        "run-shard",
        "--output-dir",
        str(campaign_root.resolve()),
        "--operating-points",
        str(Path(str(manifest["operating_points_source"])).resolve()),
        "--lane-reference",
        str(Path(str(manifest["lane_reference_source"])).resolve()),
        "--engine",
        str(Path(str(manifest["engine"])).resolve()),
        "--engine-profile",
        str(Path(str(manifest["engine_profile"])).resolve()),
        "--operating-point-id",
        shard.operating_point_id,
        "--seed-block",
        str(shard.seed_block),
        "--workers",
        str(workers_per_shard),
    ]
    for source in reuse_evidence_dirs:
        command.extend(["--reuse-evidence-dir", str(source.resolve())])
    return command


def build_discovery_command(
    *,
    runner: Path,
    campaign_root: Path,
    manifest: Mapping[str, Any],
    workers: int,
) -> list[str]:
    if workers not in range(1, MAX_WORKERS_PER_SHARD + 1):
        raise ValueError("discovery workers must be 1 or 2")
    return [
        sys.executable,
        str(runner.resolve()),
        "--mode",
        "discover-targets",
        "--output-dir",
        str(campaign_root.resolve()),
        "--operating-points",
        str(Path(str(manifest["operating_points_source"])).resolve()),
        "--lane-reference",
        str(Path(str(manifest["lane_reference_source"])).resolve()),
        "--engine",
        str(Path(str(manifest["engine"])).resolve()),
        "--engine-profile",
        str(Path(str(manifest["engine_profile"])).resolve()),
        "--workers",
        str(workers),
    ]


def _discovery_completion_state(
    campaign_root: Path, *, manifest: Mapping[str, Any]
) -> tuple[str, str]:
    status = str(manifest.get("target_discovery_status") or "")
    preflight_status = str(manifest.get("operating_point_preflight_status") or "")
    if status == "rejected" or preflight_status == "rejected":
        return "rejected", "operating-point scientific preflight rejected the states"
    if not status and not preflight_status:
        return "missing", ""
    if status != "complete" or preflight_status != EXPECTED_PREFLIGHT_STATUS:
        return "resumable", f"discovery={status!r}, preflight={preflight_status!r}"
    registry_path = Path(str(manifest.get("target_registry") or "")).resolve()
    preflight_path = Path(
        str(manifest.get("operating_point_preflight") or "")
    ).resolve()
    expected_registry = (
        campaign_root.resolve() / "target_discovery" / "target_registry.json"
    )
    expected_preflight = (
        campaign_root.resolve() / "target_discovery" / "operating_point_preflight.json"
    )
    if registry_path != expected_registry or preflight_path != expected_preflight:
        return (
            "invalid",
            "discovery evidence paths escape the signed campaign directory",
        )
    for path, hash_field, label in (
        (registry_path, "target_registry_sha256", "target registry"),
        (preflight_path, "operating_point_preflight_sha256", "state preflight"),
    ):
        if not path.is_file():
            return "resumable", f"missing {label}: {path}"
        if _sha256_file(path) != str(manifest.get(hash_field) or ""):
            return "invalid", f"{label} SHA-256 mismatch"
    registry = _read_json(registry_path)
    unsigned_registry = dict(registry)
    registry_signature = str(unsigned_registry.pop("registry_signature", ""))
    lane_contracts = registry.get("lane_contracts") or []
    if (
        registry.get("schema_version") != f"{INPUT_SCHEMA_VERSION}.target_registry.v4"
        or registry.get("campaign_signature") != manifest.get("campaign_signature")
        or registry_signature != _stable_sha256(unsigned_registry)
        or registry_signature != str(manifest.get("target_registry_signature") or "")
        or len(registry.get("targets") or []) != EXPECTED_TARGET_ROWS
        or len(lane_contracts) != 18
        or any(
            row.get("design_status") != "calibration_design_comparable_42d_window"
            or int(row.get("comparable_campaign_seed_count") or 0) < 24
            for row in lane_contracts
        )
        or registry.get("states") != list(EXPECTED_OPERATING_POINTS)
        or registry.get("seeds") != list(manifest.get("seeds") or [])
        or registry.get("lanes")
        != [str(row.get("lane_id") or "") for row in manifest.get("lanes") or []]
        or int(registry.get("disruption_window_days") or 0) != 42
        or registry.get("all_lane_design_windows_comparable") is not True
        or registry.get("all_lane_holdout_exposures_comparable") is not True
        or registry.get("campaign_exposure_gate_passed") is not True
        or registry.get("exposure_gate_failures") != []
        or manifest.get("target_exposure_comparability_status") != "accepted"
    ):
        return "invalid", "target registry fails its signed V4 contract"
    preflight = _read_json(preflight_path)
    unsigned_preflight = dict(preflight)
    preflight_signature = str(unsigned_preflight.pop("preflight_signature", ""))
    if (
        preflight.get("schema_version") != EXPECTED_PREFLIGHT_SCHEMA_VERSION
        or preflight.get("contract_revision") != EXPECTED_CONTRACT_REVISION
        or preflight.get("campaign_signature") != manifest.get("campaign_signature")
        or preflight.get("status") != EXPECTED_PREFLIGHT_STATUS
        or preflight.get("operating_points_input_status")
        != manifest.get("operating_points_input_status")
        or preflight.get("operating_points_artifact_signature")
        != manifest.get("operating_points_artifact_signature")
        or preflight.get("operating_points_calibration_plan_signature")
        != manifest.get("operating_points_calibration_plan_signature")
        or preflight.get("operating_points_selection_signature")
        != manifest.get("operating_points_selection_signature")
        or preflight.get("no_incident_probe_before_holdout_acceptance") is not True
        or int(preflight.get("campaign_seed_count") or 0) != 30
        or preflight.get("campaign_seeds") != list(manifest.get("seeds") or [])
        or preflight.get("holdout_used_once_without_retuning") is not True
        or preflight.get("ordering_valid") is not True
        or preflight.get("seed_ordering_valid") is not True
        or int(preflight.get("joint_seed_order_count") or 0) < 24
        or len(preflight.get("states") or []) != 3
        or {
            str(row.get("operating_point_id") or "")
            for row in preflight.get("states") or []
        }
        != set(EXPECTED_OPERATING_POINTS)
        or any(row.get("accepted") is not True for row in preflight.get("states") or [])
        or preflight_signature != _stable_sha256(unsigned_preflight)
        or preflight_signature
        != str(manifest.get("operating_point_preflight_signature") or "")
    ):
        return "invalid", "operating-point preflight fails its signed contract"
    return "complete", ""


def _completion_state(
    campaign_root: Path,
    *,
    campaign_signature: str,
    shard: Shard,
) -> tuple[str, str]:
    shard_dir = campaign_root / "shards" / shard.shard_id
    progress_path = shard_dir / "progress.json"
    if not progress_path.is_file():
        return "missing", ""
    try:
        progress = _read_json(progress_path)
    except ValueError as exc:
        return "invalid", str(exc)
    if progress.get("schema_version") != SHARD_PROGRESS_SCHEMA_VERSION:
        return "invalid", "shard progress schema mismatch"
    if progress.get("campaign_signature") != campaign_signature:
        return "invalid", "shard progress campaign signature mismatch"
    if progress.get("shard_id") != shard.shard_id:
        return "invalid", "shard progress id mismatch"
    status = str(progress.get("status") or "").casefold()
    try:
        planned = int(progress.get("planned_case_count") or 0)
        completed = int(progress.get("completed_case_count") or 0)
        failed = int(progress.get("failed_case_count") or 0)
    except (TypeError, ValueError):
        return "invalid", "shard progress counters are invalid"
    if status == "complete":
        if (
            planned != EXPECTED_CASES_PER_SHARD
            or completed != EXPECTED_CASES_PER_SHARD
            or failed != 0
            or not (shard_dir / "campaign_metrics.csv").is_file()
            or not (shard_dir / "shard_manifest.json").is_file()
        ):
            return "invalid", "complete shard evidence is incomplete"
        return "complete", ""
    if status == "running":
        updated = _parse_utc(progress.get("updated_at_utc"))
        if updated is not None:
            age = (datetime.now(timezone.utc) - updated).total_seconds()
            if age <= DEFAULT_ACTIVE_PROGRESS_SECONDS:
                return "active", f"last heartbeat {age:.0f}s ago"
    if status in {"failed", "running", "planned", "preflight_complete"}:
        return "resumable", status
    return "invalid", f"unsupported shard progress status {status!r}"


def _launch_contract(
    *,
    manifest: Mapping[str, Any],
    runner: Path,
    shards: Sequence[Shard],
) -> dict[str, Any]:
    payload = {
        "schema_version": CONTRACT_SCHEMA_VERSION,
        "campaign_signature": manifest["campaign_signature"],
        "runner": str(runner.resolve()),
        "runner_sha256": _sha256_file(runner.resolve()),
        "shard_ids": [shard.shard_id for shard in shards],
        "target_discovery_required_before_shards": True,
        "target_discovery_run_count": EXPECTED_DISCOVERY_RUNS,
        "operating_point_preflight_required": True,
        "failure_policy": "stop_new_scheduling_and_drain_already_running_shards",
        "maximum_parallel_shards": MAX_PARALLEL_SHARDS,
        "maximum_workers_per_shard": MAX_WORKERS_PER_SHARD,
    }
    payload["launch_contract_signature"] = _stable_sha256(payload)
    return payload


def _ensure_launch_contract(
    campaign_root: Path,
    *,
    manifest: Mapping[str, Any],
    runner: Path,
    shards: Sequence[Shard],
) -> dict[str, Any]:
    expected = _launch_contract(manifest=manifest, runner=runner, shards=shards)
    path = campaign_root / "launch_contract.json"
    if path.is_file():
        actual = _read_json(path)
        if actual != expected:
            raise ValueError(
                "Existing launch contract changed; refusing mixed runner code"
            )
    else:
        _write_json_atomic(path, expected)
    return expected


def _progress_payload(
    *,
    manifest: Mapping[str, Any],
    contract: Mapping[str, Any],
    status: str,
    parallel_shards: int,
    workers_per_shard: int,
    started_at_utc: str,
    started_monotonic: float,
    shards: Sequence[Shard],
    queued: Sequence[Shard],
    active: Mapping[str, ActiveShard],
    completed: Mapping[str, float],
    failed: Sequence[Mapping[str, Any]],
    wakefulness_state: Mapping[str, Any] | None = None,
    phase: str = "shards",
    discovery_status: str = "complete",
    discovery_pid: int | None = None,
    discovery_log_path: Path | None = None,
) -> dict[str, Any]:
    elapsed = max(0.0, time.monotonic() - started_monotonic)
    durations = [
        value for value in completed.values() if math.isfinite(value) and value > 0
    ]
    mean_duration = sum(durations) / len(durations) if durations else 0.0
    remaining = max(0, len(shards) - len(completed) - len(failed))
    eta = (
        mean_duration * remaining / parallel_shards if durations and remaining else 0.0
    )
    payload = {
        "schema_version": PROGRESS_SCHEMA_VERSION,
        "campaign_signature": manifest["campaign_signature"],
        "launch_contract_signature": contract["launch_contract_signature"],
        "status": status,
        "phase": phase,
        "target_discovery_status": discovery_status,
        "target_discovery_pid": discovery_pid or "",
        "target_discovery_log_path": (
            str(discovery_log_path) if discovery_log_path is not None else ""
        ),
        "parallel_shards": parallel_shards,
        "workers_per_shard": workers_per_shard,
        "maximum_engine_processes": parallel_shards * workers_per_shard,
        "planned_shard_count": len(shards),
        "completed_shard_count": len(completed),
        "failed_shard_count": len(failed),
        "active_shard_count": len(active),
        "queued_shard_count": len(queued),
        "completed_shard_ids": sorted(completed),
        "queued_shard_ids": [shard.shard_id for shard in queued],
        "active_shards": [
            {
                "shard_id": item.shard.shard_id,
                "pid": item.process.pid,
                "started_at_utc": item.started_at_utc,
                "log_path": str(item.log_path),
                "command_sha256": _stable_sha256(item.command),
            }
            for item in sorted(
                active.values(), key=lambda value: value.shard.shard_index
            )
        ],
        "failures": list(failed),
        "started_at_utc": started_at_utc,
        "updated_at_utc": utc_now(),
        "elapsed_seconds": elapsed,
        "mean_completed_shard_seconds": mean_duration,
        "eta_seconds": eta,
        "failure_policy": contract["failure_policy"],
    }
    if wakefulness_state is not None:
        payload["wakefulness"] = dict(wakefulness_state)
    return payload


def _launcher_lock(path: Path):
    """Return an OS-released non-blocking file lock context manager."""

    class Lock:
        def __init__(self, lock_path: Path) -> None:
            self.path = lock_path
            self.handle: BinaryIO | None = None

        def __enter__(self) -> "Lock":
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.handle = self.path.open("a+b")
            if self.path.stat().st_size == 0:
                self.handle.write(b"0")
                self.handle.flush()
            self.handle.seek(0)
            try:
                if os.name == "nt":
                    import msvcrt

                    msvcrt.locking(self.handle.fileno(), msvcrt.LK_NBLCK, 1)
                else:  # pragma: no cover - Windows is the deployment target
                    import fcntl

                    fcntl.flock(self.handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError as exc:
                self.handle.close()
                self.handle = None
                raise RuntimeError("Another V2 campaign launcher is active") from exc
            return self

        def __exit__(self, *_args: Any) -> None:
            if self.handle is None:
                return
            self.handle.seek(0)
            if os.name == "nt":
                import msvcrt

                msvcrt.locking(self.handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:  # pragma: no cover
                import fcntl

                fcntl.flock(self.handle.fileno(), fcntl.LOCK_UN)
            self.handle.close()

    return Lock(path)


def launch_campaign(
    *,
    campaign_root: Path,
    runner: Path = RUNNER,
    parallel_shards: int = 1,
    workers_per_shard: int = 2,
    poll_seconds: float = DEFAULT_POLL_SECONDS,
    reuse_evidence_dirs: Sequence[Path] = (),
    popen_factory: PopenFactory = subprocess.Popen,
    sleep: Callable[[float], None] = time.sleep,
    wakefulness_state: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Launch missing shards and return the final atomic progress document."""

    if parallel_shards not in range(1, MAX_PARALLEL_SHARDS + 1):
        raise ValueError("parallel_shards must be 1 or 2")
    if workers_per_shard not in range(1, MAX_WORKERS_PER_SHARD + 1):
        raise ValueError("workers_per_shard must be 1 or 2")
    if not 0.0 <= poll_seconds <= 60.0:
        raise ValueError("poll_seconds must be in [0, 60]")
    campaign_root = campaign_root.resolve()
    runner = runner.resolve()
    manifest, shards = load_campaign_plan(campaign_root, runner)
    contract = _ensure_launch_contract(
        campaign_root,
        manifest=manifest,
        runner=runner,
        shards=shards,
    )
    progress_path = campaign_root / "launch_progress.json"
    started_at = utc_now()
    started_monotonic = time.monotonic()
    completed: dict[str, float] = {}
    queue: deque[Shard] = deque()
    active_existing: list[str] = []
    for shard in shards:
        state, detail = _completion_state(
            campaign_root,
            campaign_signature=str(manifest["campaign_signature"]),
            shard=shard,
        )
        if state == "complete":
            completed[shard.shard_id] = math.nan
        elif state == "active":
            active_existing.append(f"{shard.shard_id} ({detail})")
        elif state in {"missing", "resumable"}:
            queue.append(shard)
        else:
            raise ValueError(f"Invalid existing shard {shard.shard_id}: {detail}")
    if active_existing:
        raise RuntimeError(
            "Fresh running shard progress already exists; wait or use the read-only "
            "monitor before restarting: " + ", ".join(active_existing)
        )
    active: dict[str, ActiveShard] = {}
    failed: list[dict[str, Any]] = []
    stop_scheduling = False
    phase = "target_discovery"
    discovery_status, discovery_detail = _discovery_completion_state(
        campaign_root, manifest=manifest
    )
    discovery_pid: int | None = None
    discovery_log_path = campaign_root / "launcher_logs" / "target_discovery.log"

    def write_progress(status: str) -> dict[str, Any]:
        payload = _progress_payload(
            manifest=manifest,
            contract=contract,
            status=status,
            parallel_shards=parallel_shards,
            workers_per_shard=workers_per_shard,
            started_at_utc=started_at,
            started_monotonic=started_monotonic,
            shards=shards,
            queued=list(queue),
            active=active,
            completed=completed,
            failed=failed,
            wakefulness_state=wakefulness_state,
            phase=phase,
            discovery_status=discovery_status,
            discovery_pid=discovery_pid,
            discovery_log_path=discovery_log_path,
        )
        _write_json_atomic(progress_path, payload)
        return payload

    with _launcher_lock(campaign_root / ".full_campaign_v2_launcher.lock"):
        if discovery_status in {"invalid", "rejected"}:
            raise ValueError(f"Target discovery cannot be launched: {discovery_detail}")
        if discovery_status != "complete":
            discovery_command = build_discovery_command(
                runner=runner,
                campaign_root=campaign_root,
                manifest=manifest,
                workers=workers_per_shard,
            )
            discovery_log_path.parent.mkdir(parents=True, exist_ok=True)
            discovery_log_handle = discovery_log_path.open("ab")
            discovery_log_handle.write(
                (
                    f"\n[{utc_now()}] LAUNCH "
                    + json.dumps(discovery_command, ensure_ascii=False)
                    + "\n"
                ).encode("utf-8")
            )
            discovery_log_handle.flush()
            try:
                discovery_process = popen_factory(
                    discovery_command,
                    cwd=REPO_ROOT,
                    stdin=subprocess.DEVNULL,
                    stdout=discovery_log_handle,
                    stderr=subprocess.STDOUT,
                    shell=False,
                )
                discovery_pid = discovery_process.pid
                discovery_status = "running"
                write_progress("running_target_discovery")
                while True:
                    sleep(poll_seconds)
                    return_code = discovery_process.poll()
                    if return_code is not None:
                        break
                    write_progress("running_target_discovery")
            except KeyboardInterrupt:
                discovery_status = "running_interrupted_launcher"
                return write_progress("interrupted_discovery_left_running")
            except Exception as exc:
                discovery_status = "failed_to_start"
                failed.append(
                    {
                        "shard_id": "target_discovery",
                        "return_code": "",
                        "detail": f"{type(exc).__name__}: {exc}",
                        "log_path": str(discovery_log_path),
                        "failed_at_utc": utc_now(),
                    }
                )
                return write_progress("failed")
            finally:
                discovery_log_handle.flush()
                discovery_log_handle.close()
            if return_code != 0:
                discovery_status = "failed"
                failed.append(
                    {
                        "shard_id": "target_discovery",
                        "return_code": return_code,
                        "detail": "target discovery runner exited non-zero",
                        "log_path": str(discovery_log_path),
                        "failed_at_utc": utc_now(),
                    }
                )
                return write_progress("failed")
            manifest, reloaded_shards = load_campaign_plan(campaign_root, runner)
            if reloaded_shards != shards:
                raise ValueError(
                    "Shard plan changed while target discovery was running"
                )
            discovery_status, discovery_detail = _discovery_completion_state(
                campaign_root, manifest=manifest
            )
            if discovery_status != "complete":
                failed.append(
                    {
                        "shard_id": "target_discovery",
                        "return_code": return_code,
                        "detail": discovery_detail
                        or "signed discovery evidence incomplete",
                        "log_path": str(discovery_log_path),
                        "failed_at_utc": utc_now(),
                    }
                )
                return write_progress("failed")
        phase = "shards"
        write_progress("running" if queue else "complete")
        try:
            while queue or active:
                while queue and len(active) < parallel_shards and not stop_scheduling:
                    shard = queue.popleft()
                    command = build_shard_command(
                        runner=runner,
                        campaign_root=campaign_root,
                        manifest=manifest,
                        shard=shard,
                        workers_per_shard=workers_per_shard,
                        reuse_evidence_dirs=reuse_evidence_dirs,
                    )
                    log_path = campaign_root / "launcher_logs" / f"{shard.shard_id}.log"
                    log_path.parent.mkdir(parents=True, exist_ok=True)
                    log_handle = log_path.open("ab")
                    log_handle.write(
                        (
                            f"\n[{utc_now()}] LAUNCH "
                            + json.dumps(command, ensure_ascii=False)
                            + "\n"
                        ).encode("utf-8")
                    )
                    log_handle.flush()
                    try:
                        process = popen_factory(
                            command,
                            cwd=REPO_ROOT,
                            stdin=subprocess.DEVNULL,
                            stdout=log_handle,
                            stderr=subprocess.STDOUT,
                            shell=False,
                        )
                    except Exception:
                        log_handle.close()
                        raise
                    active[shard.shard_id] = ActiveShard(
                        shard=shard,
                        process=process,
                        log_handle=log_handle,
                        log_path=log_path,
                        started_monotonic=time.monotonic(),
                        started_at_utc=utc_now(),
                        command=command,
                    )
                write_progress("failed_draining" if stop_scheduling else "running")
                if not active:
                    break
                sleep(poll_seconds)
                for shard_id, item in list(active.items()):
                    return_code = item.process.poll()
                    if return_code is None:
                        continue
                    duration = max(0.0, time.monotonic() - item.started_monotonic)
                    item.log_handle.flush()
                    item.log_handle.close()
                    del active[shard_id]
                    state, detail = _completion_state(
                        campaign_root,
                        campaign_signature=str(manifest["campaign_signature"]),
                        shard=item.shard,
                    )
                    if return_code == 0 and state == "complete":
                        completed[shard_id] = duration
                    else:
                        failed.append(
                            {
                                "shard_id": shard_id,
                                "return_code": return_code,
                                "completion_state": state,
                                "detail": detail,
                                "log_path": str(item.log_path),
                                "failed_at_utc": utc_now(),
                            }
                        )
                        stop_scheduling = True
                write_progress(
                    "failed_draining" if stop_scheduling and active else "running"
                )
        except KeyboardInterrupt:
            for item in active.values():
                item.log_handle.flush()
                item.log_handle.close()
            payload = write_progress("interrupted_shards_left_running")
            return payload
        if failed:
            payload = write_progress("failed")
        elif len(completed) == len(shards):
            payload = write_progress("complete")
        else:
            payload = write_progress("failed")
            payload["failures"].append(
                {
                    "shard_id": "launcher",
                    "detail": "scheduling stopped before every shard completed",
                }
            )
            _write_json_atomic(progress_path, payload)
    return payload


def _detached_command(args: argparse.Namespace) -> list[str]:
    command = [
        sys.executable,
        str(Path(__file__).resolve()),
        "--campaign-root",
        str(args.campaign_root.resolve()),
        "--runner",
        str(args.runner.resolve()),
        "--parallel-shards",
        str(args.parallel_shards),
        "--workers-per-shard",
        str(args.workers_per_shard),
        "--poll-seconds",
        str(args.poll_seconds),
        "--detached-child",
    ]
    for source in args.reuse_evidence_dir:
        command.extend(["--reuse-evidence-dir", str(source.resolve())])
    return command


def detach_launcher(
    args: argparse.Namespace,
    *,
    popen_factory: PopenFactory = subprocess.Popen,
) -> dict[str, Any]:
    campaign_root = args.campaign_root.resolve()
    # Validate the plan before returning a detached PID.
    load_campaign_plan(campaign_root, args.runner)
    command = _detached_command(args)
    log_path = campaign_root / "launcher_detached.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("ab") as log_handle:
        kwargs: dict[str, Any] = {
            "cwd": REPO_ROOT,
            "stdin": subprocess.DEVNULL,
            "stdout": log_handle,
            "stderr": subprocess.STDOUT,
            "shell": False,
            "close_fds": True,
        }
        if os.name == "nt":
            kwargs["creationflags"] = (
                subprocess.CREATE_NEW_PROCESS_GROUP
                | subprocess.DETACHED_PROCESS
                | subprocess.CREATE_NO_WINDOW
            )
        else:  # pragma: no cover
            kwargs["start_new_session"] = True
        process = popen_factory(command, **kwargs)
    payload = {
        "schema_version": f"{SCHEMA_VERSION}.detached.v1",
        "status": "detached_launcher_started",
        "pid": process.pid,
        "campaign_root": str(campaign_root),
        "log_path": str(log_path),
        "command": command,
        "started_at_utc": utc_now(),
    }
    _write_json_atomic(campaign_root / "launcher_detached.json", payload)
    return payload


def _merge_final_wakefulness(
    campaign_root: Path,
    wakefulness_state: Mapping[str, Any],
) -> None:
    """Record the reset outcome in launch_progress after the awake guard exits."""

    progress_path = campaign_root.resolve() / "launch_progress.json"
    if not progress_path.is_file():
        return
    try:
        payload = _read_json(progress_path)
    except ValueError:
        return
    if payload.get("schema_version") != PROGRESS_SCHEMA_VERSION:
        return
    payload["wakefulness"] = dict(wakefulness_state)
    payload["updated_at_utc"] = utc_now()
    _write_json_atomic(progress_path, payload)


def run_detached_child(
    args: argparse.Namespace,
    *,
    execution_state_setter: Callable[[int], int] | None = None,
    platform_name: str | None = None,
    popen_factory: PopenFactory = subprocess.Popen,
    sleep: Callable[[float], None] = time.sleep,
) -> dict[str, Any]:
    """Run the detached scheduler while holding a fail-soft Windows awake state."""

    guard = WindowsSystemAwake(
        args.campaign_root,
        execution_state_setter=execution_state_setter,
        platform_name=platform_name,
    )
    result: dict[str, Any] | None = None
    try:
        with guard as wakefulness_state:
            result = launch_campaign(
                campaign_root=args.campaign_root,
                runner=args.runner,
                parallel_shards=args.parallel_shards,
                workers_per_shard=args.workers_per_shard,
                poll_seconds=args.poll_seconds,
                reuse_evidence_dirs=args.reuse_evidence_dir,
                popen_factory=popen_factory,
                sleep=sleep,
                wakefulness_state=wakefulness_state,
            )
    finally:
        _merge_final_wakefulness(args.campaign_root, guard.state)
    if result is None:  # pragma: no cover - an exception is already propagating
        raise RuntimeError("Detached launcher did not return a result")
    result["wakefulness"] = dict(guard.state)
    return result


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--campaign-root", type=Path, default=DEFAULT_CAMPAIGN_ROOT)
    parser.add_argument("--runner", type=Path, default=RUNNER)
    parser.add_argument("--parallel-shards", type=int, choices=(1, 2), default=1)
    parser.add_argument("--workers-per-shard", type=int, choices=(1, 2), default=2)
    parser.add_argument("--poll-seconds", type=float, default=DEFAULT_POLL_SECONDS)
    parser.add_argument("--reuse-evidence-dir", type=Path, action="append", default=[])
    parser.add_argument("--detach", action="store_true")
    parser.add_argument("--detached-child", action="store_true", help=argparse.SUPPRESS)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    if args.detach and args.detached_child:
        raise ValueError("Invalid recursive detached-launch request")
    if args.detach:
        result = detach_launcher(args)
    elif args.detached_child:
        result = run_detached_child(args)
    else:
        result = launch_campaign(
            campaign_root=args.campaign_root,
            runner=args.runner,
            parallel_shards=args.parallel_shards,
            workers_per_shard=args.workers_per_shard,
            poll_seconds=args.poll_seconds,
            reuse_evidence_dirs=args.reuse_evidence_dir,
        )
    print(json.dumps(result, ensure_ascii=False, indent=2), flush=True)
    return 0 if result.get("status") in {"complete", "detached_launcher_started"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
