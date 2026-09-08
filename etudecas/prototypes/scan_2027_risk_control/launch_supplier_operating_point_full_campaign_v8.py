#!/usr/bin/env python3
"""Launch the additive V8 exposure-stratified supplier campaign.

V8 changes only the target-window discovery contract.  The mature V4 launcher
still schedules the smoke and the 18 incident shards, while the V8 runner
validates its own signed 30/30 target registry before any incident is started.
"""

from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator, Mapping, Sequence

from etudecas.prototypes.scan_2027_risk_control import (
    build_validated_operating_points_v7 as v7_bridge,
)
from etudecas.prototypes.scan_2027_risk_control import (
    launch_supplier_operating_point_full_campaign_v7 as adapter_v7,
)
from etudecas.prototypes.scan_2027_risk_control import (
    supplier_operating_point_full_campaign_v8 as campaign_v8,
)
from etudecas.prototypes.scan_2027_risk_control import (
    supplier_v7_campaign_trace_package as trace_package,
)


implementation_v4 = adapter_v7.implementation_v4
ADAPTER_PATH = Path(__file__).resolve()
RUNNER = Path(__file__).resolve().with_name(
    "supplier_operating_point_full_campaign_v8.py"
)
V8LauncherAdapterError = adapter_v7.V7LauncherAdapterError
EXPECTED_V7_ADAPTER_SHA256 = (
    "3d92a645fbb2bf19e244c908226f3dbe78f84c3565cf1791114c1231dfab4bd5"
)


def _load_v8_campaign_plan(
    campaign_root: Path, runner: Path = RUNNER
) -> tuple[dict[str, Any], list[Any]]:
    """Validate a native V8 plan without weakening the mature shard checks."""

    campaign_root = campaign_root.resolve()
    manifest_path = campaign_root / "campaign_manifest.json"
    shard_plan_path = campaign_root / "shard_plan.csv"
    if not manifest_path.is_file() or not shard_plan_path.is_file():
        raise FileNotFoundError(
            "Run the V8 runner in --mode plan before launching shards"
        )
    manifest = implementation_v4._read_json(manifest_path)  # noqa: SLF001
    if manifest.get("schema_version") != implementation_v4.INPUT_SCHEMA_VERSION:
        raise ValueError("Unsupported V8 campaign manifest schema")
    if manifest.get("contract_revision") != implementation_v4.EXPECTED_CONTRACT_REVISION:
        raise ValueError("Campaign manifest does not preserve the mature contract")
    if str(manifest.get("status") or "") not in {"planned", "running", "complete"}:
        raise ValueError("Campaign manifest is not launchable")
    signature = str(manifest.get("campaign_signature") or "")
    if len(signature) != 64:
        raise ValueError("Campaign signature is missing")
    implementation_v4._verify_signed_design(manifest)  # noqa: SLF001
    counts = manifest.get("expected_counts") or {}
    required_counts = {
        "auxiliary_discovery_runs": 0,
        "design_window_engine_runs": 0,
        "target_selection_engine_runs": 0,
        "operating_point_validation_engine_runs": 0,
        "imported_v4_holdout_service_proofs": 90,
        "imported_v4_holdout_shipment_traces": 90,
        "imported_v7_campaign_baseline_service_proofs": 90,
        "imported_v7_campaign_baseline_shipment_traces": 90,
        "baseline_rows": 90,
        "incident_rows": 3_240,
        "shard_count": implementation_v4.EXPECTED_SHARD_COUNT,
        "rows_per_shard": implementation_v4.EXPECTED_CASES_PER_SHARD,
        "total_rows": implementation_v4.EXPECTED_TOTAL_CASES,
    }
    if not isinstance(counts, Mapping) or any(
        int(counts.get(key, -1)) != value for key, value in required_counts.items()
    ):
        raise ValueError("Campaign expected counts do not match the V8 matrix")
    if manifest.get("target_selection_revision") != campaign_v8.TARGET_SELECTION_REVISION:
        raise ValueError("V8 target-selection revision changed")
    if manifest.get("target_selection_engine_runs") != 0:
        raise ValueError("V8 target selection must not run the engine")
    cohort = manifest.get("v8_target_selection_cohort") or {}
    if (
        cohort.get("campaign_baselines_used_for_exposure_stratification")
        != list(trace_package.CAMPAIGN_SEEDS)
        or cohort.get("source_trace_count") != 90
        or cohort.get("reserved_target_design_cohort_used") is not False
        or cohort.get("incident_outcomes_used") is not False
    ):
        raise ValueError("V8 exposure-stratification cohort changed")
    for flag in (
        "quality_branch_included",
        "quality_incident_included",
        "availability_incident_included",
        "capacity_incident_included",
        "stock_incident_included",
        "supplier_state_dependent_risks_enabled",
    ):
        if manifest.get(flag) is not False:
            raise ValueError(f"Campaign must explicitly declare {flag}=false")
    if tuple(int(value) for value in manifest.get("seeds") or []) != tuple(
        trace_package.CAMPAIGN_SEEDS
    ):
        raise ValueError("Campaign does not preserve the 30 V7 campaign seeds")
    mechanisms = manifest.get("mechanisms") or []
    if (
        not isinstance(mechanisms, list)
        or {
            str(row.get("key") or "")
            for row in mechanisms
            if isinstance(row, Mapping)
        }
        != implementation_v4.EXPECTED_MECHANISMS
    ):
        raise ValueError("Campaign mechanisms are not the signed incident pair")
    implementation_v4._validate_manifest_sources(manifest)  # noqa: SLF001
    implementation_v4._validate_operating_point_source_contract(manifest)  # noqa: SLF001
    runner = runner.resolve()
    if not runner.is_file():
        raise FileNotFoundError(f"Missing V8 shard runner: {runner}")
    planned_runner = Path(str(manifest.get("runner") or "")).resolve()
    if planned_runner != runner:
        raise ValueError("Launcher runner path differs from the signed campaign runner")
    if implementation_v4._sha256_file(runner) != str(  # noqa: SLF001
        manifest.get("runner_sha256") or ""
    ):
        raise ValueError("Signed V8 campaign runner changed after planning")
    shards = implementation_v4._load_shards(manifest)  # noqa: SLF001
    plan_rows = implementation_v4._read_csv(shard_plan_path)  # noqa: SLF001
    if len(plan_rows) != implementation_v4.EXPECTED_SHARD_COUNT or {
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
            or int(row.get("total_rows") or 0)
            != implementation_v4.EXPECTED_CASES_PER_SHARD
        ):
            raise ValueError(f"shard_plan.csv row changed for {shard.shard_id}")
    return manifest, shards


def _v8_detached_command(args: Any) -> list[str]:
    """Ensure a detached child re-enters this V8 adapter, not the V4 module."""

    command = [
        implementation_v4.sys.executable,
        str(ADAPTER_PATH),
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


def validate_frozen_implementation() -> Path:
    trace_package.validate_frozen_v7_protocol()
    path = Path(adapter_v7.__file__).resolve()
    digest = adapter_v7.adapter_v6.adapter_v5._sha256_file(path)  # noqa: SLF001
    if digest != EXPECTED_V7_ADAPTER_SHA256:
        raise V8LauncherAdapterError(f"Frozen V7 launcher adapter changed: {digest}")
    parent = adapter_v7.validate_frozen_implementation()
    campaign_v8.validate_frozen_implementation()
    if not RUNNER.is_file():
        raise V8LauncherAdapterError(f"Missing V8 campaign runner: {RUNNER}")
    return parent


def _v8_discovery_completion_state(
    campaign_root: Path, *, manifest: Mapping[str, Any]
) -> tuple[str, str]:
    """Use the V8 registry validator instead of the obsolete design-seed gate."""

    status = str(manifest.get("target_discovery_status") or "")
    binding_status = str(manifest.get("state_validation_binding_status") or "")
    if status == "rejected" or binding_status == "rejected":
        return "rejected", "V8 target-exposure comparability rejected the design"
    if not status and not binding_status:
        return "missing", ""
    if status != "complete" or binding_status != implementation_v4.EXPECTED_PREFLIGHT_STATUS:
        return "resumable", f"discovery={status!r}, binding={binding_status!r}"
    try:
        with campaign_v8.patched_v8_context():
            lanes = campaign_v8.implementation_v4.load_lanes(
                Path(str(manifest.get("lane_reference_source") or ""))
            )
            campaign_v8.implementation_v4.load_target_registry(
                output_dir=campaign_root,
                manifest=manifest,
                lanes=lanes,
            )
    except FileNotFoundError as exc:
        return "resumable", str(exc)
    except (KeyError, TypeError, ValueError) as exc:
        return "invalid", str(exc)
    return "complete", ""


@contextmanager
def patched_v8_context() -> Iterator[None]:
    validate_frozen_implementation()
    previous_bridge: Any = implementation_v4.v4_bridge
    previous_runner: Any = implementation_v4.RUNNER
    previous_seeds: Any = implementation_v4.EXPECTED_CAMPAIGN_SEEDS
    previous_discovery_runs: Any = implementation_v4.EXPECTED_DISCOVERY_RUNS
    previous_plan_loader: Any = implementation_v4.load_campaign_plan
    previous_detached_command: Any = implementation_v4._detached_command  # noqa: SLF001
    previous_discovery_validator: Any = (  # noqa: SLF001
        implementation_v4._discovery_completion_state
    )
    implementation_v4.v4_bridge = v7_bridge
    implementation_v4.RUNNER = RUNNER
    implementation_v4.EXPECTED_CAMPAIGN_SEEDS = trace_package.CAMPAIGN_SEEDS
    implementation_v4.EXPECTED_DISCOVERY_RUNS = 0
    implementation_v4.load_campaign_plan = _load_v8_campaign_plan
    implementation_v4._detached_command = _v8_detached_command  # noqa: SLF001
    implementation_v4._discovery_completion_state = (  # noqa: SLF001
        _v8_discovery_completion_state
    )
    try:
        yield
    finally:
        implementation_v4.v4_bridge = previous_bridge
        implementation_v4.RUNNER = previous_runner
        implementation_v4.EXPECTED_CAMPAIGN_SEEDS = previous_seeds
        implementation_v4.EXPECTED_DISCOVERY_RUNS = previous_discovery_runs
        implementation_v4.load_campaign_plan = previous_plan_loader
        implementation_v4._detached_command = previous_detached_command  # noqa: SLF001
        implementation_v4._discovery_completion_state = (  # noqa: SLF001
            previous_discovery_validator
        )


# Compatibility name used by the existing downstream orchestration helpers.
patched_v5_context = patched_v8_context


def main(argv: Sequence[str] | None = None) -> int:
    with patched_v8_context():
        return int(implementation_v4.main(argv))


if __name__ == "__main__":
    raise SystemExit(main())
