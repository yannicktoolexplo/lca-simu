#!/usr/bin/env python3
"""Launch or resume discovery and 18 isolated shards of the V4 campaign.

The launcher never runs simulation logic itself.  It reads the signed campaign
plan, binds the accepted 90-case V4 holdout, completes three design runs, then
starts the additive V4 runner once per shard.
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
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from etudecas.prototypes.scan_2027_risk_control import (  # noqa: E402
    build_validated_operating_points_v4 as v4_bridge,
)
from etudecas.prototypes.scan_2027_risk_control import (  # noqa: E402
    supplier_operating_point_campaign_v4_contract as v4_contract,
)

RUNNER = (
    REPO_ROOT
    / "etudecas"
    / "prototypes"
    / "scan_2027_risk_control"
    / "supplier_operating_point_full_campaign_v4.py"
)
DEFAULT_CAMPAIGN_ROOT = (
    Path(r"C:\dev\lca-simu-pr40-validation-artifacts-20260726")
    / "supplier_operating_point_full_campaign_v4_20260905_v1"
)

SCHEMA_VERSION = "etudecas.supplier_operating_point_full_campaign.v4.launcher.v1"
CONTRACT_SCHEMA_VERSION = f"{SCHEMA_VERSION}.contract"
PROGRESS_SCHEMA_VERSION = f"{SCHEMA_VERSION}.progress"
INPUT_SCHEMA_VERSION = v4_contract.CAMPAIGN_SCHEMA_VERSION
SHARD_PROGRESS_SCHEMA_VERSION = f"{INPUT_SCHEMA_VERSION}.progress.v1"
EXPECTED_SHARD_COUNT = 18
EXPECTED_CASES_PER_SHARD = 185
EXPECTED_TOTAL_CASES = 3330
EXPECTED_DISCOVERY_RUNS = 3
EXPECTED_TARGET_ROWS = 3 * 30 * 18
EXPECTED_OPERATING_POINTS = ("op_100", "op_93", "op_80")
EXPECTED_MECHANISMS = {"transport_delay", "planned_delivery_shortfall"}
EXPECTED_PREFLIGHT_STATUS = "accepted_v4_holdout_bound_no_rerun"
EXPECTED_PREFLIGHT_SCHEMA_VERSION = (
    f"{INPUT_SCHEMA_VERSION}.state_validation_binding.v1"
)
EXPECTED_CONTRACT_REVISION = (
    "v4_fresh30_imported_trace_fixed42d_adaptive_probe_v1_2026_09_05"
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
EXPECTED_CAMPAIGN_SEEDS = v4_contract.CAMPAIGN_SEEDS
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


def _is_sha256(value: Any) -> bool:
    text = str(value or "").casefold()
    return len(text) == 64 and all(character in "0123456789abcdef" for character in text)


def _truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value or "").strip().casefold() in {"1", "true", "yes", "oui"}


def _integer_equals(value: Any, expected: int) -> bool:
    if isinstance(value, bool):
        return False
    try:
        return int(value) == expected
    except (TypeError, ValueError):
        return False


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
        "state_validation_binding",
        "state_validation_binding_sha256",
        "state_validation_binding_signature",
        "state_validation_binding_status",
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
        (
            "operating_points_holdout",
            "operating_points_holdout_sha256",
            "accepted V4 holdout result",
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


def _legacy_validate_operating_point_source_contract(
    manifest: Mapping[str, Any]
) -> None:
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


# V4 deliberately supersedes the legacy V1--V3 source dispatcher above without
# changing those copied routines.  Only the accepted, fully revalidated bridge
# can reach ``load_campaign_plan``.
def _validate_operating_point_source_contract(manifest: Mapping[str, Any]) -> None:
    source_path = Path(str(manifest.get("operating_points_source") or "")).resolve()
    bridge = v4_bridge.validate_bridge(source_path, revalidate_source=True)
    source = dict(bridge["source"])
    source_hashes = dict(bridge["source_hashes"])
    cohorts = dict(bridge["cohorts"])
    if (
        manifest.get("operating_points_producer") != "v4_fresh_holdout_bridge"
        or manifest.get("operating_points_schema_version")
        != v4_contract.BRIDGE_SCHEMA_VERSION
        or manifest.get("operating_points_input_status")
        != v4_contract.BRIDGE_ACCEPTED_STATUS
        or manifest.get("operating_points_artifact_signature")
        != bridge["artifact_signature"]
        or manifest.get("operating_points_cohorts") != cohorts
        or manifest.get("operating_points_calibration_plan_signature")
        != source["plan_signature"]
        or manifest.get("operating_points_selection_signature")
        != source["development_selection_signature"]
        or manifest.get("operating_points_holdout_signature")
        != source["holdout_signature"]
        or manifest.get("operating_points_trace_index_signature")
        != bridge["trace_index_signature"]
        or manifest.get("operating_points_trace_count") != 90
        or manifest.get("operating_points_holdout_contract")
        != bridge["holdout_contract"]
        or source_hashes.get("engine_sha256") != manifest.get("engine_sha256")
        or source_hashes.get("engine_profile_sha256")
        != manifest.get("engine_profile_sha256")
        or cohorts.get("campaign_repetitions_reuse_v4_fresh_holdout")
        != list(EXPECTED_CAMPAIGN_SEEDS)
        or cohorts.get("incident_window_design_reserved") != [900659036]
        or cohorts.get(
            "holdout_reused_for_incident_comparison_not_operating_point_retuning"
        )
        is not True
        or bridge.get("retuning_after_holdout") is not False
    ):
        raise ValueError("Campaign manifest does not preserve the accepted V4 bridge")


def load_campaign_plan(
    campaign_root: Path, runner: Path = RUNNER
) -> tuple[dict[str, Any], list[Shard]]:
    campaign_root = campaign_root.resolve()
    manifest_path = campaign_root / "campaign_manifest.json"
    shard_plan_path = campaign_root / "shard_plan.csv"
    if not manifest_path.is_file() or not shard_plan_path.is_file():
        raise FileNotFoundError(
            "Run the V4 runner in --mode plan before launching shards"
        )
    manifest = _read_json(manifest_path)
    if manifest.get("schema_version") != INPUT_SCHEMA_VERSION:
        raise ValueError("Unsupported V4 campaign manifest schema")
    if manifest.get("contract_revision") != EXPECTED_CONTRACT_REVISION:
        raise ValueError("Campaign manifest is not the signed V4 six-week contract")
    if str(manifest.get("status") or "") not in {"planned", "running", "complete"}:
        raise ValueError("Campaign manifest is not launchable")
    signature = str(manifest.get("campaign_signature") or "")
    if len(signature) != 64:
        raise ValueError("Campaign signature is missing")
    _verify_signed_design(manifest)
    counts = manifest.get("expected_counts") or {}
    if (
        int(counts.get("auxiliary_discovery_runs") or 0) != EXPECTED_DISCOVERY_RUNS
        or int(counts.get("design_window_engine_runs") or 0) != 3
        or int(counts.get("operating_point_validation_engine_runs", -1)) != 0
        or int(counts.get("imported_v4_holdout_service_proofs") or 0) != 90
        or int(counts.get("imported_v4_holdout_shipment_traces") or 0) != 90
        or int(counts.get("baseline_rows") or 0) != 90
        or int(counts.get("incident_rows") or 0) != 3240
        or int(counts.get("shard_count") or 0) != EXPECTED_SHARD_COUNT
        or int(counts.get("rows_per_shard") or 0) != EXPECTED_CASES_PER_SHARD
        or int(counts.get("total_rows") or 0) != EXPECTED_TOTAL_CASES
    ):
        raise ValueError("Campaign expected counts do not match the full V4 matrix")
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
            "campaign_repetitions_reuse_v4_fresh_holdout": list(
                EXPECTED_CAMPAIGN_SEEDS
            ),
            "incident_window_design_reserved": [900659036],
            "holdout_reused_for_incident_comparison_not_operating_point_retuning": True,
        }
        or tuple(int(value) for value in manifest.get("seeds") or [])
        != EXPECTED_CAMPAIGN_SEEDS
    ):
        raise ValueError(
            "Campaign does not preserve the signed V4 holdout/design split"
        )
    mechanisms = manifest.get("mechanisms") or []
    if (
        not isinstance(mechanisms, list)
        or {str(row.get("key") or "") for row in mechanisms if isinstance(row, Mapping)}
        != EXPECTED_MECHANISMS
    ):
        raise ValueError("Campaign mechanisms are not the signed V4 incident pair")
    _validate_manifest_sources(manifest)
    _validate_operating_point_source_contract(manifest)
    runner = runner.resolve()
    if not runner.is_file():
        raise FileNotFoundError(f"Missing V4 shard runner: {runner}")
    planned_runner = Path(str(manifest.get("runner") or "")).resolve()
    if planned_runner != runner:
        raise ValueError("Launcher runner path differs from the signed campaign runner")
    if _sha256_file(runner) != str(manifest.get("runner_sha256") or ""):
        raise ValueError("Signed V4 campaign runner changed after planning")
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


def _smoke_identity(
    campaign_root: Path, manifest: Mapping[str, Any]
) -> tuple[int, str]:
    registry = _read_json(campaign_root.resolve() / "target_discovery" / "target_registry.json")
    lane_order = {
        str(row.get("lane_id") or ""): index
        for index, row in enumerate(manifest.get("lanes") or [])
    }
    seed_order = {seed: index for index, seed in enumerate(EXPECTED_CAMPAIGN_SEEDS)}
    candidates = [
        row
        for row in registry.get("targets") or []
        if row.get("operating_point_id") == "op_93"
        and row.get("seed_cross_state_exposure_comparable") is True
        and str(row.get("target_status") or "").startswith("identified_")
        and float(row.get("target_planned_qty") or 0.0) > 1e-12
    ]
    if not candidates:
        raise ValueError("No positive comparable op_93 case exists for V4 smoke")
    selected = min(
        candidates,
        key=lambda row: (
            lane_order[str(row["lane_id"])],
            seed_order[int(row["seed"])],
        ),
    )
    return int(selected["seed"]), str(selected["lane_id"])


def build_smoke_command(
    *, runner: Path, campaign_root: Path, manifest: Mapping[str, Any]
) -> list[str]:
    seed, lane_id = _smoke_identity(campaign_root, manifest)
    return [
        sys.executable,
        str(runner.resolve()),
        "--mode",
        "smoke",
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
        "op_93",
        "--smoke-seed",
        str(seed),
        "--smoke-lane-id",
        lane_id,
        "--workers",
        "1",
    ]


def _smoke_completion_state(
    campaign_root: Path, *, manifest: Mapping[str, Any]
) -> tuple[str, str]:
    try:
        seed, lane_id = _smoke_identity(campaign_root, manifest)
    except (FileNotFoundError, ValueError) as exc:
        return "invalid", str(exc)
    shard_id = f"smoke__op_93__seed_{seed}"
    smoke_dir = campaign_root.resolve() / "smoke" / shard_id
    progress_path = smoke_dir / "progress.json"
    shard_manifest_path = smoke_dir / "shard_manifest.json"
    metrics_path = smoke_dir / "campaign_metrics.csv"
    if not progress_path.is_file():
        return "missing", ""
    progress = _read_json(progress_path)
    progress_status = str(progress.get("status") or "")
    if progress_status == "running":
        updated = _parse_utc(progress.get("updated_at_utc"))
        if updated is not None:
            age = (datetime.now(timezone.utc) - updated).total_seconds()
            if age <= DEFAULT_ACTIVE_PROGRESS_SECONDS:
                return "active", f"last heartbeat {age:.0f}s ago"
        return "resumable", "stale running V4 smoke"
    if progress_status in {"failed", "planned"}:
        return "resumable", progress_status
    if not shard_manifest_path.is_file() or not metrics_path.is_file():
        return "resumable", "V4 smoke outputs are incomplete"
    shard_manifest = _read_json(shard_manifest_path)
    metrics = _read_csv(metrics_path)
    immutable_shard = dict(shard_manifest)
    for field in (
        "completed_case_count",
        "valid_case_count",
        "invalid_or_not_applicable_case_count",
        "runtime_failure_count",
        "completed_at_utc",
    ):
        immutable_shard.pop(field, None)
    shard_signature = str(immutable_shard.pop("shard_signature", ""))
    immutable_shard["status"] = "planned"
    expected_case_keys = {
        f"op_93__baseline__seed_{seed}",
        *(
            f"op_93__{lane_id}__{mechanism}__seed_{seed}"
            for mechanism in EXPECTED_MECHANISMS
        ),
    }
    if (
        progress.get("schema_version") != SHARD_PROGRESS_SCHEMA_VERSION
        or progress.get("campaign_signature") != manifest.get("campaign_signature")
        or progress.get("shard_id") != shard_id
        or progress.get("status") != "complete"
        or int(progress.get("planned_case_count") or 0) != 3
        or int(progress.get("completed_case_count") or 0) != 3
        or int(progress.get("failed_case_count") or 0) != 0
        or shard_manifest.get("schema_version") != f"{INPUT_SCHEMA_VERSION}.shard.v1"
        or shard_manifest.get("campaign_signature")
        != manifest.get("campaign_signature")
        or shard_manifest.get("operating_point_id") != "op_93"
        or shard_manifest.get("shard_id") != shard_id
        or shard_manifest.get("seed_ids") != [seed]
        or shard_manifest.get("lane_ids") != [lane_id]
        or set(shard_manifest.get("mechanisms") or []) != EXPECTED_MECHANISMS
        or shard_manifest.get("execution_scope") != "smoke_non_reusable"
        or shard_manifest.get("status") != "complete"
        or int(shard_manifest.get("planned_case_count") or 0) != 3
        or int(shard_manifest.get("completed_case_count") or 0) != 3
        or int(shard_manifest.get("valid_case_count") or 0) != 3
        or int(shard_manifest.get("invalid_or_not_applicable_case_count") or 0) != 0
        or int(shard_manifest.get("runtime_failure_count") or 0) != 0
        or not _is_sha256(shard_signature)
        or shard_signature != _stable_sha256(immutable_shard)
        or len(metrics) != 3
        or {row.get("schema_version") for row in metrics}
        != {f"{INPUT_SCHEMA_VERSION}.case.v1"}
        or {row.get("campaign_signature") for row in metrics}
        != {manifest.get("campaign_signature")}
        or {row.get("engine_sha256") for row in metrics}
        != {manifest.get("engine_sha256")}
        or {row.get("shard_id") for row in metrics} != {shard_id}
        or {row.get("operating_point_id") for row in metrics} != {"op_93"}
        or {int(row.get("seed") or -1) for row in metrics} != {seed}
        or {row.get("case_key") for row in metrics} != expected_case_keys
        or {row.get("stage") for row in metrics} != {"baseline", "incident"}
        or {row.get("mechanism") for row in metrics if row.get("stage") == "incident"}
        != EXPECTED_MECHANISMS
        or {row.get("lane_id") for row in metrics if row.get("stage") == "incident"}
        != {lane_id}
        or any(not _truthy(row.get("valid")) for row in metrics)
        or any(str(row.get("validation_errors") or "").strip() for row in metrics)
        or any(not _is_sha256(row.get("case_signature")) for row in metrics)
        or len({row.get("case_signature") for row in metrics}) != 3
    ):
        return "invalid", "V4 smoke proof fails its non-reusable three-case contract"
    baseline = next(row for row in metrics if row.get("stage") == "baseline")
    incidents = [row for row in metrics if row.get("stage") == "incident"]
    warmup_hashes = {
        str(row.get("warmup_core_state_sha256") or "") for row in metrics
    }
    if (
        {row.get("baseline_case_signature") for row in incidents}
        != {baseline.get("case_signature")}
        or len(warmup_hashes) != 1
        or any(not _is_sha256(value) for value in warmup_hashes)
        or any(
            not _truthy(row.get("incident_physically_exercised"))
            for row in incidents
        )
    ):
        return "invalid", "V4 smoke pairing or physical exposure is invalid"
    for row in metrics:
        case_key = str(row["case_key"])
        evidence_path = smoke_dir / "case_evidence" / f"{case_key}.json"
        if not evidence_path.is_file():
            return "invalid", "V4 smoke case evidence is missing"
        evidence = _read_json(evidence_path)
        unsigned = dict(evidence)
        evidence_signature = str(unsigned.pop("evidence_signature", ""))
        if (
            not _is_sha256(evidence_signature)
            or evidence_signature != _stable_sha256(unsigned)
            or evidence.get("schema_version") != f"{INPUT_SCHEMA_VERSION}.case.v1"
            or evidence.get("campaign_signature") != manifest.get("campaign_signature")
            or evidence.get("engine_sha256") != manifest.get("engine_sha256")
            or evidence.get("shard_id") != shard_id
            or evidence.get("case_key") != case_key
            or evidence.get("case_signature") != row.get("case_signature")
            or evidence.get("operating_point_id") != "op_93"
            or evidence.get("seed") != seed
            or evidence.get("stage") != row.get("stage")
            or evidence.get("valid") is not True
            or evidence.get("status") != "valid"
            or evidence.get("validation_errors") != []
            or evidence.get("quality_branch_included") is not False
            or evidence.get("availability_incident_included") is not False
            or evidence.get("supplier_state_dependent_risks_enabled") is not False
            or not isinstance(evidence.get("metrics"), Mapping)
            or evidence["metrics"].get("warmup_core_state_sha256")
            != row.get("warmup_core_state_sha256")
        ):
            return "invalid", "V4 smoke signed case evidence is invalid"
        if row.get("stage") == "incident":
            mechanism = str(row.get("mechanism") or "")
            risk_sha = str(evidence.get("risk_csv_sha256") or "")
            risk_path = smoke_dir / "inputs" / "risk_events" / f"{case_key}.csv"
            if (
                not isinstance(evidence.get("lane"), Mapping)
                or evidence["lane"].get("lane_id") != lane_id
                or not isinstance(evidence.get("mechanism"), Mapping)
                or evidence["mechanism"].get("key") != mechanism
                or not isinstance(evidence.get("incident_proof"), Mapping)
                or evidence["incident_proof"].get("incident_physically_exercised")
                is not True
                or evidence.get("baseline_case_signature")
                != baseline.get("case_signature")
                or not _is_sha256(risk_sha)
                or not risk_path.is_file()
                or _sha256_file(risk_path) != risk_sha
            ):
                return "invalid", "V4 smoke incident proof or risk CSV is invalid"
    return "complete", ""


def _legacy_discovery_completion_state(
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


# V4 completion checks the imported-trace binding rather than the obsolete
# 93-run preflight copied above.
def _discovery_completion_state(
    campaign_root: Path, *, manifest: Mapping[str, Any]
) -> tuple[str, str]:
    status = str(manifest.get("target_discovery_status") or "")
    binding_status = str(manifest.get("state_validation_binding_status") or "")
    if status == "rejected" or binding_status == "rejected":
        return "rejected", "V4 target-exposure comparability rejected the design"
    if not status and not binding_status:
        return "missing", ""
    if status != "complete" or binding_status != EXPECTED_PREFLIGHT_STATUS:
        return "resumable", f"discovery={status!r}, binding={binding_status!r}"
    registry_path = Path(str(manifest.get("target_registry") or "")).resolve()
    binding_path = Path(str(manifest.get("state_validation_binding") or "")).resolve()
    expected_registry = (
        campaign_root.resolve() / "target_discovery" / "target_registry.json"
    )
    expected_binding = (
        campaign_root.resolve() / "target_discovery" / "state_validation_binding.json"
    )
    if registry_path != expected_registry or binding_path != expected_binding:
        return "invalid", "V4 discovery evidence paths escape the campaign directory"
    for path, hash_field, label in (
        (registry_path, "target_registry_sha256", "target registry"),
        (binding_path, "state_validation_binding_sha256", "V4 state binding"),
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
        registry.get("schema_version") != f"{INPUT_SCHEMA_VERSION}.target_registry.v1"
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
        or registry.get("design_seed") != 900659036
        or registry.get("states") != list(EXPECTED_OPERATING_POINTS)
        or registry.get("seeds") != list(EXPECTED_CAMPAIGN_SEEDS)
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
    binding = _read_json(binding_path)
    unsigned_binding = dict(binding)
    binding_signature = str(unsigned_binding.pop("binding_signature", ""))
    if (
        binding.get("schema_version") != EXPECTED_PREFLIGHT_SCHEMA_VERSION
        or binding.get("contract_revision") != EXPECTED_CONTRACT_REVISION
        or binding.get("campaign_signature") != manifest.get("campaign_signature")
        or binding.get("status") != EXPECTED_PREFLIGHT_STATUS
        or binding.get("operating_points_input_status")
        != manifest.get("operating_points_input_status")
        or binding.get("operating_points_artifact_signature")
        != manifest.get("operating_points_artifact_signature")
        or binding.get("v4_plan_signature")
        != manifest.get("operating_points_calibration_plan_signature")
        or binding.get("v4_development_selection_signature")
        != manifest.get("operating_points_selection_signature")
        or binding.get("v4_holdout_signature")
        != manifest.get("operating_points_holdout_signature")
        or binding.get("v4_trace_index_signature")
        != manifest.get("operating_points_trace_index_signature")
        or binding.get("campaign_seeds") != list(EXPECTED_CAMPAIGN_SEEDS)
        or binding.get("design_seed") != 900659036
        or binding.get("state_validation_engine_runs_in_campaign") != 0
        or binding.get("imported_official_service_proof_count") != 90
        or binding.get("imported_official_shipment_trace_count") != 90
        or binding.get("retuning_after_holdout") is not False
        or not isinstance(binding.get("states"), Mapping)
        or set(binding["states"]) != set(EXPECTED_OPERATING_POINTS)
        or binding_signature != _stable_sha256(unsigned_binding)
        or binding_signature
        != str(manifest.get("state_validation_binding_signature") or "")
    ):
        return "invalid", "V4 state-validation binding fails its signed contract"
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
        try:
            shard_manifest = _read_json(shard_dir / "shard_manifest.json")
            metrics = _read_csv(shard_dir / "campaign_metrics.csv")
        except (OSError, ValueError) as exc:
            return "invalid", f"complete shard evidence is unreadable: {exc}"
        immutable = dict(shard_manifest)
        for field in (
            "completed_case_count",
            "valid_case_count",
            "invalid_or_not_applicable_case_count",
            "runtime_failure_count",
            "completed_at_utc",
        ):
            immutable.pop(field, None)
        shard_signature = str(immutable.pop("shard_signature", ""))
        immutable["status"] = "planned"
        lane_ids = [str(value) for value in shard_manifest.get("lane_ids") or []]
        manifest_valid = (
            shard_manifest.get("schema_version") == f"{INPUT_SCHEMA_VERSION}.shard.v1"
            and shard_manifest.get("campaign_signature") == campaign_signature
            and shard_manifest.get("shard_id") == shard.shard_id
            and _integer_equals(shard_manifest.get("shard_index"), shard.shard_index)
            and _integer_equals(
                shard_manifest.get("shard_count"), EXPECTED_SHARD_COUNT
            )
            and shard_manifest.get("operating_point_id") == shard.operating_point_id
            and _integer_equals(shard_manifest.get("seed_block"), shard.seed_block)
            and shard_manifest.get("seed_ids") == list(shard.seed_ids)
            and len(lane_ids) == 18
            and len(set(lane_ids)) == 18
            and set(shard_manifest.get("mechanisms") or []) == EXPECTED_MECHANISMS
            and shard_manifest.get("execution_scope") == "campaign_shard"
            and shard_manifest.get("adaptive_horizon") is True
            and _integer_equals(
                shard_manifest.get("planned_case_count"), EXPECTED_CASES_PER_SHARD
            )
            and shard_manifest.get("status") == "complete"
            and _integer_equals(
                shard_manifest.get("completed_case_count"), EXPECTED_CASES_PER_SHARD
            )
            and _integer_equals(
                shard_manifest.get("valid_case_count"), EXPECTED_CASES_PER_SHARD
            )
            and _integer_equals(
                shard_manifest.get("invalid_or_not_applicable_case_count"), 0
            )
            and _integer_equals(shard_manifest.get("runtime_failure_count"), 0)
            and _is_sha256(shard_signature)
            and shard_signature == _stable_sha256(immutable)
        )
        if not manifest_valid:
            return "invalid", "complete shard manifest contract is invalid"
        expected_cases = {
            f"{shard.operating_point_id}__baseline__seed_{seed}"
            for seed in shard.seed_ids
        } | {
            (
                f"{shard.operating_point_id}__{lane_id}__{mechanism}__seed_{seed}"
            )
            for seed in shard.seed_ids
            for lane_id in lane_ids
            for mechanism in EXPECTED_MECHANISMS
        }
        actual_cases = {str(row.get("case_key") or "") for row in metrics}

        def row_identity_valid(row: Mapping[str, Any]) -> bool:
            try:
                seed = int(row.get("seed") or 0)
            except (TypeError, ValueError):
                return False
            stage = str(row.get("stage") or "")
            mechanism = str(row.get("mechanism") or "")
            lane_id = str(row.get("lane_id") or "")
            if stage == "baseline":
                return (
                    mechanism == "baseline"
                    and not lane_id
                    and row.get("case_key")
                    == f"{shard.operating_point_id}__baseline__seed_{seed}"
                )
            return (
                stage == "incident"
                and mechanism in EXPECTED_MECHANISMS
                and lane_id in lane_ids
                and row.get("case_key")
                == (
                    f"{shard.operating_point_id}__{lane_id}__{mechanism}__seed_{seed}"
                )
            )

        if (
            len(metrics) != EXPECTED_CASES_PER_SHARD
            or actual_cases != expected_cases
            or len(actual_cases) != len(metrics)
            or any(
                row.get("schema_version") != f"{INPUT_SCHEMA_VERSION}.case.v1"
                or row.get("campaign_signature") != campaign_signature
                or row.get("shard_id") != shard.shard_id
                or row.get("operating_point_id") != shard.operating_point_id
                or not any(
                    _integer_equals(row.get("seed"), expected_seed)
                    for expected_seed in shard.seed_ids
                )
                or not _truthy(row.get("valid"))
                or str(row.get("validation_errors") or "").strip()
                or not _is_sha256(row.get("case_signature"))
                or not _is_sha256(row.get("warmup_core_state_sha256"))
                or not _is_sha256(row.get("summary_sha256"))
                or not row_identity_valid(row)
                for row in metrics
            )
        ):
            return "invalid", "complete shard metric matrix is invalid"
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
        "imported_v4_holdout_trace_count": 90,
        "operating_point_validation_engine_run_count": 0,
        "state_validation_binding_required": True,
        "non_reusable_op93_smoke_required_before_shards": True,
        "smoke_reported_case_count": 3,
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
                raise RuntimeError("Another V4 campaign launcher is active") from exc
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
    # Preliminary diagnostics remain read-only; the contract is created or
    # accepted only after the exclusive launcher lock is held below.
    contract = _launch_contract(manifest=manifest, runner=runner, shards=shards)
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

    with _launcher_lock(campaign_root / ".full_campaign_v4_launcher.lock"):
        # Re-read and re-scan after acquiring the OS lock.  The preliminary
        # read above is useful for fast diagnostics, but no scheduling decision
        # may rely on state observed before exclusive ownership (TOCTOU guard).
        manifest, shards = load_campaign_plan(campaign_root, runner)
        contract = _ensure_launch_contract(
            campaign_root,
            manifest=manifest,
            runner=runner,
            shards=shards,
        )
        completed.clear()
        queue.clear()
        active_existing = []
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
        discovery_status, discovery_detail = _discovery_completion_state(
            campaign_root, manifest=manifest
        )
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
        phase = "smoke"
        smoke_status, smoke_detail = _smoke_completion_state(
            campaign_root, manifest=manifest
        )
        if smoke_status == "active":
            raise RuntimeError(
                "A fresh V4 smoke run is already active; wait before restarting: "
                + smoke_detail
            )
        if smoke_status == "invalid":
            raise ValueError("V4 smoke cannot be launched: " + smoke_detail)
        if smoke_status != "complete":
            smoke_command = build_smoke_command(
                runner=runner, campaign_root=campaign_root, manifest=manifest
            )
            smoke_log_path = campaign_root / "launcher_logs" / "smoke_op93.log"
            smoke_log_path.parent.mkdir(parents=True, exist_ok=True)
            smoke_log_handle = smoke_log_path.open("ab")
            smoke_log_handle.write(
                (
                    f"\n[{utc_now()}] LAUNCH "
                    + json.dumps(smoke_command, ensure_ascii=False)
                    + "\n"
                ).encode("utf-8")
            )
            smoke_log_handle.flush()
            try:
                smoke_process = popen_factory(
                    smoke_command,
                    cwd=REPO_ROOT,
                    stdin=subprocess.DEVNULL,
                    stdout=smoke_log_handle,
                    stderr=subprocess.STDOUT,
                    shell=False,
                )
                write_progress("running_smoke")
                while True:
                    sleep(poll_seconds)
                    smoke_return_code = smoke_process.poll()
                    if smoke_return_code is not None:
                        break
                    write_progress("running_smoke")
            except KeyboardInterrupt:
                return write_progress("interrupted_smoke_left_running")
            except Exception as exc:
                failed.append(
                    {
                        "shard_id": "smoke_op93",
                        "return_code": "",
                        "detail": f"{type(exc).__name__}: {exc}",
                        "log_path": str(smoke_log_path),
                        "failed_at_utc": utc_now(),
                    }
                )
                return write_progress("failed")
            finally:
                smoke_log_handle.flush()
                smoke_log_handle.close()
            if smoke_return_code != 0:
                failed.append(
                    {
                        "shard_id": "smoke_op93",
                        "return_code": smoke_return_code,
                        "detail": "mandatory non-reusable op_93 smoke exited non-zero",
                        "log_path": str(smoke_log_path),
                        "failed_at_utc": utc_now(),
                    }
                )
                return write_progress("failed")
            smoke_status, smoke_detail = _smoke_completion_state(
                campaign_root, manifest=manifest
            )
            if smoke_status != "complete":
                failed.append(
                    {
                        "shard_id": "smoke_op93",
                        "return_code": smoke_return_code,
                        "detail": smoke_detail or "mandatory smoke proof incomplete",
                        "log_path": str(smoke_log_path),
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
