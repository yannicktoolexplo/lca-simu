#!/usr/bin/env python3
"""Read-only live monitor for an active V7 fixed-triplet validation run.

The frozen V7 runner intentionally requires every official attempt directory to
be clean when it reads status. That is correct at a transaction boundary but
not while worker processes still own uncommitted cases. This companion only
reads the run: it validates committed evidence and requires cleanup only for
attempts associated with such evidence. Uncommitted attempts are reported,
never treated as evidence and never modified.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

from etudecas.prototypes.scan_2027_risk_control import (
    supplier_fresh_development_holdout_protocol_v7 as v7,
)


MONITOR_SCHEMA_VERSION = "etudecas.fixed_triplet_confirmation.v7.live_monitor.v1"


def _read_progress(
    plan: v7.ValidatedPlan,
    run_dir: Path,
    mode: str,
) -> dict[str, Any] | None:
    """Read the signed progress snapshot before collecting evidence."""

    path = run_dir / "progress.json"
    if not path.is_file():
        return None
    payload = v7._read_json(path)  # noqa: SLF001
    v7._verify_signature(payload, "progress_signature", "V7 progress")  # noqa: SLF001
    expected_fields = {
        "schema_version",
        "plan_signature",
        "run_signature",
        "status",
        "completed_case_count",
        "expected_case_count",
        "completed_seed_block_count",
        "expected_seed_block_count",
        "complete_prefix_seed_block_count",
        "milestones_published",
        "decision_status",
        "execution_mode",
        "publishable",
        "error",
        "updated_at_utc",
        "progress_signature",
    }
    reported_cases = payload.get("completed_case_count")
    reported_blocks = payload.get("completed_seed_block_count")
    reported_prefix = payload.get("complete_prefix_seed_block_count")
    published_milestones = payload.get("milestones_published")
    if (
        set(payload) != expected_fields
        or payload.get("schema_version") != v7.PROGRESS_SCHEMA_VERSION
        or payload.get("plan_signature") != plan.manifest["plan_signature"]
        or payload.get("run_signature") != v7._run_manifest(plan, mode)["run_signature"]  # noqa: SLF001
        or payload.get("execution_mode") != mode
        or payload.get("publishable") is not (mode == v7.OFFICIAL_EXECUTION_MODE)
        or payload.get("status")
        not in {"running", "failed_resumable", "complete_pending_finalization"}
        or payload.get("expected_case_count") != v7.EXPECTED_CASES
        or payload.get("expected_seed_block_count") != v7.VALIDATION_SEED_COUNT
        or not isinstance(reported_cases, int)
        or not isinstance(reported_blocks, int)
        or not isinstance(reported_prefix, int)
        or not 0 <= reported_cases <= v7.EXPECTED_CASES
        or not 0 <= reported_blocks <= v7.VALIDATION_SEED_COUNT
        or not 0 <= reported_prefix <= v7.VALIDATION_SEED_COUNT
        or not isinstance(published_milestones, list)
        or any(
            not isinstance(milestone, int)
            or milestone not in v7.MILESTONES
            or milestone > reported_prefix
            for milestone in published_milestones
        )
        or published_milestones != sorted(set(published_milestones))
        or payload.get("decision_status")
        != (
            "eligible_for_finalization_only"
            if reported_cases == v7.EXPECTED_CASES
            else "not_evaluated_before_all_450_cases"
        )
        or not isinstance(payload.get("updated_at_utc"), str)
        or not isinstance(payload.get("error"), str)
    ):
        raise v7.V7ProtocolError("V7 progress snapshot is invalid or ahead of evidence")
    if payload["status"] == "complete_pending_finalization" and (
        reported_cases != v7.EXPECTED_CASES
        or reported_blocks != v7.VALIDATION_SEED_COUNT
        or reported_prefix != v7.VALIDATION_SEED_COUNT
    ):
        raise v7.V7ProtocolError("Completed V7 progress is inconsistent")
    return payload


def _validate_progress(
    payload: Mapping[str, Any] | None,
    completed: Mapping[tuple[str, int], Mapping[str, Any]],
) -> dict[str, Any]:
    """Reconcile a pre-read progress snapshot with later committed evidence."""

    if payload is None:
        return {"present": False, "state": "not_written_yet"}
    actual_blocks = v7._total_complete_blocks(completed)  # noqa: SLF001
    actual_prefix = v7._complete_prefix_blocks(completed)  # noqa: SLF001
    reported_cases = int(payload["completed_case_count"])
    reported_blocks = int(payload["completed_seed_block_count"])
    reported_prefix = int(payload["complete_prefix_seed_block_count"])
    if (
        reported_cases > len(completed)
        or reported_blocks > actual_blocks
        or reported_prefix > actual_prefix
    ):
        raise v7.V7ProtocolError("V7 progress snapshot is ahead of committed evidence")
    return {
        "present": True,
        "state": "current"
        if reported_cases == len(completed)
        else "lagging_committed_evidence",
        "reported_status": payload["status"],
        "reported_completed_case_count": reported_cases,
        "validated_committed_case_count": len(completed),
        "reported_completed_seed_block_count": reported_blocks,
        "validated_completed_seed_block_count": actual_blocks,
        "reported_complete_prefix_seed_block_count": reported_prefix,
        "validated_complete_prefix_seed_block_count": actual_prefix,
        "updated_at_utc": payload["updated_at_utc"],
    }


def _descriptive_checkpoint(
    plan: v7.ValidatedPlan,
    run_dir: Path,
    completed: Mapping[tuple[str, int], Mapping[str, Any]],
) -> dict[str, Any]:
    """Validate published descriptive checkpoints and expose the latest one."""

    prefix = v7._complete_prefix_blocks(completed)  # noqa: SLF001
    checkpoint_dir = run_dir / "checkpoints"
    actual = (
        {path.name for path in checkpoint_dir.glob("*.json")}
        if checkpoint_dir.exists()
        else set()
    )
    allowed = {f"checkpoint_{milestone:03d}.json" for milestone in v7.MILESTONES}
    if actual - allowed:
        raise v7.V7ProtocolError("Unexpected V7 checkpoint exists")
    published: list[dict[str, Any]] = []
    observed_after_evidence_snapshot: list[int] = []
    for milestone in v7.MILESTONES:
        path = checkpoint_dir / f"checkpoint_{milestone:03d}.json"
        if not path.is_file():
            continue
        if prefix < milestone:
            # The runner can publish evidence and its checkpoint between the
            # evidence snapshot and this directory listing. Do not mistake that
            # normal concurrent transition for an invalid active run.
            observed_after_evidence_snapshot.append(milestone)
            continue
        observed = v7._read_json(path)  # noqa: SLF001
        v7._verify_signature(
            observed, "checkpoint_signature", f"V7 checkpoint {milestone}"
        )  # noqa: SLF001
        expected = v7._checkpoint_payload(plan, run_dir, completed, milestone)  # noqa: SLF001
        if v7._checkpoint_fixed_view(observed) != v7._checkpoint_fixed_view(expected):  # noqa: SLF001
            raise v7.V7ProtocolError("Published V7 descriptive checkpoint changed")
        published.append(
            {
                "milestone_seed_blocks": milestone,
                "case_count": observed["case_count"],
                "summary": observed["summary"],
            }
        )
    return {
        "descriptive_only": True,
        "acceptance_criteria_evaluated": False,
        "early_stop_or_decision_authorized": False,
        "complete_prefix_seed_block_count": prefix,
        "published": published,
        "observed_after_evidence_snapshot": observed_after_evidence_snapshot,
        "next_milestone_seed_blocks": next(
            (m for m in v7.MILESTONES if m > prefix), None
        ),
    }


def _attempt_state(
    plan: v7.ValidatedPlan,
    run_dir: Path,
    completed: Mapping[tuple[str, int], Mapping[str, Any]],
) -> dict[str, Any]:
    """Classify bounded attempts; only committed ones must already be pruned."""

    committed_keys = set(completed)
    committed_clean = 0
    uncommitted: list[dict[str, Any]] = []
    for candidate, seed, case_dir in v7._official_attempt_case_dirs(plan, run_dir):  # noqa: SLF001
        key = (candidate.key, seed)
        heavy = sorted(
            name
            for name in v7._ENGINE_HEAVY_DIRECTORY_NAMES
            if (case_dir / name).exists()
        )  # noqa: SLF001
        if key in committed_keys:
            if heavy:
                raise v7.V7ProtocolError(
                    "Committed V7 evidence has an unpruned engine attempt: "
                    f"{candidate.key}/{seed} ({heavy})"
                )
            committed_clean += 1
        else:
            uncommitted.append(
                {
                    "candidate_key": candidate.key,
                    "seed": seed,
                    "case_path": str(case_dir),
                    "heavy_directories_present": heavy,
                    "classification": "uncommitted_attempt_active_or_orphan_not_evidence",
                }
            )
    return {
        "committed_attempts_verified_clean": committed_clean,
        "uncommitted_attempts": uncommitted,
        "uncommitted_attempt_count": len(uncommitted),
        "policy": "uncommitted attempts are tolerated and never counted as evidence",
    }


def inspect_run(
    plan_dir: Path,
    run_dir: Path,
    *,
    allow_test_source: bool = False,
    verify_runtime: bool = True,
) -> dict[str, Any]:
    """Return a read-only, concurrency-tolerant V7 validation snapshot.

    The optional arguments are fixture hooks; the CLI always uses official
    production validation.
    """

    plan = v7.validate_plan(
        plan_dir, allow_test_source=allow_test_source, verify_runtime=verify_runtime
    )
    run_dir = run_dir.resolve()
    mode = v7._registered_mode(plan, run_dir)  # noqa: SLF001
    progress_payload = _read_progress(plan, run_dir, mode)
    completed, missing = v7._collect(plan, run_dir, mode)  # noqa: SLF001
    v7._validate_curve_inventory(plan, run_dir, completed)  # noqa: SLF001
    v7._validate_bundle_inventory(plan, run_dir, completed)  # noqa: SLF001
    attempts = _attempt_state(plan, run_dir, completed)
    progress = _validate_progress(progress_payload, completed)
    checkpoint = _descriptive_checkpoint(plan, run_dir, completed)
    result_path = run_dir / "validation_result.json"
    return {
        "schema_version": MONITOR_SCHEMA_VERSION,
        "read_only": True,
        "execution_mode": mode,
        "plan_signature": plan.manifest["plan_signature"],
        "run_signature": v7._run_manifest(plan, mode)["run_signature"],  # noqa: SLF001
        "committed_evidence": {
            "validated_case_count": len(completed),
            "missing_case_count": len(missing),
            "expected_case_count": v7.EXPECTED_CASES,
            "validated_seed_block_count": v7._total_complete_blocks(completed),  # noqa: SLF001
        },
        "progress": progress,
        "descriptive_checkpoint": checkpoint,
        "attempts": attempts,
        "finalized_result_present": result_path.is_file(),
        "decision_available": result_path.is_file(),
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan-dir", type=Path, default=v7.DEFAULT_PLAN_OUTPUT)
    parser.add_argument("--run-dir", type=Path, default=v7.DEFAULT_RUN_OUTPUT)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        result = inspect_run(args.plan_dir, args.run_dir)
    except Exception as exc:
        print(f"V7 LIVE MONITOR REFUSED: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
