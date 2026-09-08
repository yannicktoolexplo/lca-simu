from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from etudecas.prototypes.scan_2027_risk_control import (
    supplier_balanced_product_delay_multiseed_refinement_v4 as v4,
)
from etudecas.prototypes.scan_2027_risk_control import (
    supplier_balanced_product_delay_multiseed_refinement_v5 as v5,
)
from etudecas.prototypes.scan_2027_risk_control.tests import (
    test_supplier_balanced_product_delay_multiseed_refinement_v4 as v4_fixture,
)


def _v4_no_go(tmp_path: Path) -> tuple[Path, Path, Path]:
    plan, _source = v4_fixture._prepared_keep_plan(tmp_path)  # noqa: SLF001
    run = tmp_path / "v4_run"

    def executor(**kwargs: Any) -> dict[str, Any]:
        candidate = kwargs["candidate"]
        # No OP93 candidate is inside the V4 development band.  OP100 and the
        # reused OP80 remain valid, so the failure is specifically "no pair".
        service = {"op_100": 1.0, "op_93": 0.95, "op_80": 0.80}[
            candidate.target_group
        ]
        return {"metrics": v4_fixture._metrics(service)}  # noqa: SLF001

    v4.run_stage(
        plan,
        run,
        stage="development",
        executor=executor,
        max_workers=1,
        test_only=True,
    )
    selection = v4.finalize_stage(plan, run, stage="development", test_only=True)
    assert selection["status"] == "development_failed_no_holdout"
    sidecar = tmp_path / "v4_sidecar_never_created"
    return plan, run, sidecar


def _v5_plan(tmp_path: Path) -> tuple[Path, Path, Path, Path, Path]:
    v4_plan, v4_run, sidecar = _v4_no_go(tmp_path)
    plan = tmp_path / "v5_plan"
    v5.prepare_plan(
        plan,
        v4_plan_dir=v4_plan,
        v4_run_dir=v4_run,
        v4_sidecar_root=sidecar,
        allow_test_source=True,
    )
    return plan, tmp_path / "v5_run", v4_plan, v4_run, sidecar


def test_v5_grid_is_small_frozen_and_preserves_the_v4_order_gate() -> None:
    assert v5.OP93_GRID == (
        ("op93_v5_8p2_80p6", 8.2, 80.6),
        ("op93_v5_8p3_80p6", 8.3, 80.6),
        ("op93_v5_8p4_80p6", 8.4, 80.6),
    )
    assert v5.OP80_GRID == (
        ("op80_v5_19p4_96p6", 19.4, 96.6),
        ("op80_v5_19p5_96p6", 19.5, 96.6),
        ("op80_v5_19p6_96p6", 19.6, 96.6),
    )
    assert v5.EXPECTED_NEW_DEVELOPMENT_CASES == 180
    assert v5.EXPECTED_REUSED_DEVELOPMENT_CASES == 30
    projected_counts = v5.SCREENING_PROJECTIONS[
        "projected_same_seed_joint_strict_order_count"
    ]
    assert {count for row in projected_counts.values() for count in row.values()} <= {
        24,
        25,
    }
    assert min(count for row in projected_counts.values() for count in row.values()) == 24
    assert v5.SCREENING_PROJECTIONS["not_acceptance_evidence"] is True
    assert (
        v5.SCREENING_PROJECTIONS["why_both_states_move"][
            "best_projected_joint_count_with_v4_op93_8p5_80p5"
        ]
        < v5.MIN_ORDERED_SEEDS
    )
    contract = v5._selection_contract()  # noqa: SLF001
    assert contract["same_seed_joint_strict_order_required"] == 24
    assert contract["no_interpolation"] is True
    assert (
        contract["candidate_acceptance_requires_executed_proofs_not_reconstruction"]
        is True
    )


def test_v5_plan_requires_exact_reproducible_v4_no_go_and_unseen_holdout(
    tmp_path: Path,
) -> None:
    v4_plan, v4_run, sidecar = _v4_no_go(tmp_path)
    with pytest.raises(v5.V5ProtocolError, match="official 330-case"):
        v5.prepare_plan(
            tmp_path / "not_official_v5",
            v4_plan_dir=v4_plan,
            v4_run_dir=v4_run,
            v4_sidecar_root=sidecar,
        )
    assert not (tmp_path / "not_official_v5").exists()

    leaked = v4_run / "engine_attempts" / "holdout"
    leaked.mkdir(parents=True)
    (leaked / "proof-of-use.txt").write_text("used\n", encoding="utf-8")
    with pytest.raises(v5.V5ProtocolError, match="holdout is not unseen"):
        v5.prepare_plan(
            tmp_path / "leaked_v5",
            v4_plan_dir=v4_plan,
            v4_run_dir=v4_run,
            v4_sidecar_root=sidecar,
            allow_test_source=True,
        )
    assert not (tmp_path / "leaked_v5").exists()

    (leaked / "proof-of-use.txt").unlink()
    leaked.rmdir()
    sidecar.mkdir()
    (sidecar / "capture_contract.json").write_text("{}\n", encoding="utf-8")
    with pytest.raises(v5.V5ProtocolError, match="sidecar"):
        v5.prepare_plan(
            tmp_path / "sidecar_v5",
            v4_plan_dir=v4_plan,
            v4_run_dir=v4_run,
            v4_sidecar_root=sidecar,
            allow_test_source=True,
        )


def test_v5_executes_only_six_new_candidates_then_one_fresh_holdout(
    tmp_path: Path,
) -> None:
    plan, run, _v4_plan, v4_run, _sidecar = _v5_plan(tmp_path)
    source_selection_path = v4_run / "development_selection.json"
    source_selection_hash = v5.sha256_file(source_selection_path)
    validated = v5.validate_plan(
        plan, verify_runtime_dependencies=False, allow_test_source=True
    )
    assert len(validated.candidates) == 7
    assert validated.manifest["new_development_case_count"] == 180
    assert validated.manifest["reused_development_case_count"] == 30
    assert validated.manifest["supersedes"]["modifies_v4_artifacts"] is False

    calls: list[tuple[str, str, int]] = []

    def executor(**kwargs: Any) -> dict[str, Any]:
        candidate = kwargs["candidate"]
        calls.append((kwargs["stage"], candidate.key, kwargs["seed"]))
        service = {"op_93": 0.93, "op_80": 0.80}.get(
            candidate.target_group, 1.0
        )
        return {"metrics": v4_fixture._metrics(service)}  # noqa: SLF001

    progress = v5.run_stage(
        plan,
        run,
        stage="development",
        executor=executor,
        max_workers=2,
        test_only=True,
    )
    assert progress["completed_case_count"] == 210
    assert len(calls) == 180
    assert not any(key == "op100_source" for _stage, key, _seed in calls)
    assert not (run / "shipment_traces").exists()

    selection = v5.finalize_stage(plan, run, stage="development", test_only=True)
    assert selection["status"] == "development_selected_pending_fresh_holdout"
    assert selection["new_candidate_evidence_case_count"] == 180
    assert selection["v4_op100_evidence_case_count"] == 30
    assert selection["v4_candidate_engine_rerun_count"] == 0
    assert selection["selected_candidate_keys"] == {
        "op_100": "op100_source",
        "op_93": "op93_v5_8p2_80p6",
        "op_80": "op80_v5_19p4_96p6",
    }
    assert selection["eligible_pairs"]
    assert all(
        row["same_seed_joint_strict_order_count"] == 30
        for row in selection["eligible_pairs"]
    )

    v5.run_stage(
        plan,
        run,
        stage="development",
        executor=executor,
        max_workers=1,
        test_only=True,
    )
    assert len(calls) == 180

    holdout_progress = v5.run_stage(
        plan,
        run,
        stage="holdout",
        executor=executor,
        max_workers=2,
        test_only=True,
    )
    assert holdout_progress["completed_case_count"] == 90
    assert len(calls) == 270
    result = v5.finalize_stage(plan, run, stage="holdout", test_only=True)
    assert result["accepted"] is True
    assert result["status"] == "holdout_validated_30_carried_unseen_seeds"
    assert result["same_seed_joint_strict_order_count"] == 30
    assert result["retuning_after_holdout"] is False
    assert result["publishable"] is False
    assert v5.sha256_file(source_selection_path) == source_selection_hash

    rogue_trace = run / "shipment_traces" / "rogue.json.gz"
    rogue_trace.parent.mkdir(parents=True)
    rogue_trace.write_bytes(b"not-a-trace")
    with pytest.raises(v5.V5ProtocolError, match="Unexpected compact trace"):
        v5.finalize_stage(plan, run, stage="holdout", test_only=True)


def test_v5_tamper_and_twenty_three_seed_order_fail_closed(tmp_path: Path) -> None:
    plan, run, _v4_plan, _v4_run, _sidecar = _v5_plan(tmp_path)

    def executor(**kwargs: Any) -> dict[str, Any]:
        candidate = kwargs["candidate"]
        seed_index = v5.DEVELOPMENT_SEEDS.index(kwargs["seed"])
        if candidate.target_group == "op_93":
            service = 0.93
        elif candidate.target_group == "op_80":
            # Seven ties are offset by seven low realizations: pooled and median
            # remain exactly 80%, while strict joint order is only 23/30.
            service = 0.93 if seed_index < 7 else 0.67 if seed_index < 14 else 0.80
        else:
            service = 1.0
        return {"metrics": v4_fixture._metrics(service)}  # noqa: SLF001

    v5.run_stage(
        plan,
        run,
        stage="development",
        executor=executor,
        max_workers=1,
        test_only=True,
    )
    selection = v5.finalize_stage(plan, run, stage="development", test_only=True)
    assert all(
        row["admissible_individually"]
        for key, row in selection["candidate_summaries"].items()
        if key.startswith(("op93_v5_", "op80_v5_"))
    )
    assert selection["status"] == "development_failed_no_holdout"
    assert selection["selected_candidate_keys"] is None
    assert selection["eligible_pairs"] == []
    with pytest.raises(v5.V5ProtocolError, match="not authorized"):
        v5.run_stage(
            plan,
            run,
            stage="holdout",
            executor=executor,
            test_only=True,
        )

    manifest_path = plan / "refinement_plan.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["candidate_design"]["op93_exact_grid"][0][
        "offset_days_268091"
    ] = 8.25
    unsigned = dict(manifest)
    unsigned.pop("plan_signature")
    manifest["plan_signature"] = v5.stable_sha256(unsigned)
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    with pytest.raises(v5.V5ProtocolError, match="scientific contract"):
        v5.validate_plan(
            plan, verify_runtime_dependencies=False, allow_test_source=True
        )


def test_v5_interrupted_development_resumes_only_missing_new_cases(
    tmp_path: Path,
) -> None:
    plan, run, _v4_plan, _v4_run, _sidecar = _v5_plan(tmp_path)
    successful: set[tuple[str, int]] = set()
    attempts = 0

    def interrupted(**kwargs: Any) -> dict[str, Any]:
        nonlocal attempts
        candidate = kwargs["candidate"]
        attempts += 1
        if attempts == 6:
            raise RuntimeError("synthetic crash")
        successful.add((candidate.key, kwargs["seed"]))
        service = 0.93 if candidate.target_group == "op_93" else 0.80
        return {"metrics": v4_fixture._metrics(service)}  # noqa: SLF001

    with pytest.raises(RuntimeError, match="synthetic crash"):
        v5.run_stage(
            plan,
            run,
            stage="development",
            executor=interrupted,
            max_workers=1,
            test_only=True,
        )
    failed_progress = json.loads(
        (run / "development_progress.json").read_text(encoding="utf-8")
    )
    assert failed_progress["status"] == "failed"
    assert failed_progress["completed_case_count"] == 35
    assert len(successful) == 5

    resumed_calls: list[tuple[str, int]] = []

    def resumed(**kwargs: Any) -> dict[str, Any]:
        candidate = kwargs["candidate"]
        identity = (candidate.key, kwargs["seed"])
        assert identity not in successful
        resumed_calls.append(identity)
        service = 0.93 if candidate.target_group == "op_93" else 0.80
        return {"metrics": v4_fixture._metrics(service)}  # noqa: SLF001

    progress = v5.run_stage(
        plan,
        run,
        stage="development",
        executor=resumed,
        max_workers=2,
        test_only=True,
    )
    assert progress["status"] == "complete"
    assert progress["completed_case_count"] == 210
    assert len(resumed_calls) == 175
    assert len(successful | set(resumed_calls)) == 180
