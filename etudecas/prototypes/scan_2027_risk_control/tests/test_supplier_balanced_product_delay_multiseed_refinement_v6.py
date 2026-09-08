from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from etudecas.prototypes.scan_2027_risk_control import (
    supplier_balanced_product_delay_multiseed_refinement_v5 as v5,
)
from etudecas.prototypes.scan_2027_risk_control import (
    supplier_balanced_product_delay_multiseed_refinement_v6 as v6,
)
from etudecas.prototypes.scan_2027_risk_control.tests import (
    test_supplier_balanced_product_delay_multiseed_refinement_v5 as v5_fixture,
)
from etudecas.prototypes.scan_2027_risk_control.tests import (
    test_supplier_balanced_product_delay_multiseed_refinement_v4 as v4_fixture,
)


def _v5_no_go(tmp_path: Path) -> tuple[Path, Path, Path]:
    plan, run, _v4_plan, _v4_run, _v4_sidecar = v5_fixture._v5_plan(  # noqa: SLF001
        tmp_path
    )

    def executor(**kwargs: Any) -> dict[str, Any]:
        candidate = kwargs["candidate"]
        if candidate.key == "op93_v5_8p2_80p6":
            service = 0.95
        elif candidate.key in v6.SOURCE_OP93_KEYS:
            service = 0.93
        else:
            service = 0.83
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
    selection = v5.finalize_stage(plan, run, stage="development", test_only=True)
    assert selection["status"] == "development_failed_no_holdout"
    admissible_op93 = {
        key
        for key, summary in selection["candidate_summaries"].items()
        if summary["candidate"]["target_group"] == "op_93"
        and summary["admissible_individually"]
    }
    assert admissible_op93 == set(v6.SOURCE_OP93_KEYS)
    sidecar = tmp_path / "v5_sidecar_never_created"
    return plan, run, sidecar


def _v6_plan(tmp_path: Path) -> tuple[Path, Path, Path, Path, Path]:
    v5_plan, v5_run, sidecar = _v5_no_go(tmp_path)
    source_before = {
        path.relative_to(v5_run).as_posix(): v6.sha256_file(path)
        for path in v5_run.rglob("*")
        if path.is_file()
    }
    plan = tmp_path / "v6_plan"
    v6.prepare_plan(
        plan,
        v5_plan_dir=v5_plan,
        v5_run_dir=v5_run,
        v5_sidecar_root=sidecar,
        allow_test_source=True,
    )
    source_after = {
        path.relative_to(v5_run).as_posix(): v6.sha256_file(path)
        for path in v5_run.rglob("*")
        if path.is_file()
    }
    assert source_after == source_before
    return plan, tmp_path / "v6_run", v5_plan, v5_run, sidecar


def test_v6_grid_and_case_counts_are_exact() -> None:
    assert v6.SOURCE_OP93_KEYS == (
        "op93_v5_8p3_80p6",
        "op93_v5_8p4_80p6",
    )
    assert v6.OP80_GRID == (
        ("op80_v6_17_96p6", 17.0, 96.6),
        ("op80_v6_17p5_96p6", 17.5, 96.6),
    )
    assert v6.EXPECTED_IMPORTED_DEVELOPMENT_CASES == 90
    assert v6.EXPECTED_NEW_DEVELOPMENT_CASES == 60
    assert v6.EXPECTED_DEVELOPMENT_CASES == 150
    assert v6._holdout_contract()[  # noqa: SLF001
        "holdout_execution_supported_by_this_module"
    ] is False
    assert "run-development" in v6._parser().format_help()  # noqa: SLF001
    assert "run-holdout" not in v6._parser().format_help()  # noqa: SLF001


@pytest.mark.parametrize(
    ("changed", "value"),
    [
        ("status", "running"),
        ("status", "development_selected_pending_fresh_holdout"),
        ("holdout_cases_read", 1),
        ("selected_candidate_keys", {"op_80": "unexpected"}),
    ],
)
def test_v6_refuses_nonterminal_or_holdout_used_v5_selection(
    changed: str, value: object
) -> None:
    summaries = {
        "op100_source": {
            "candidate": {"target_group": "op_100"},
            "admissible_individually": True,
        },
        "op93_v5_8p2_80p6": {
            "candidate": {"target_group": "op_93"},
            "admissible_individually": False,
        },
        **{
            key: {
                "candidate": {"target_group": "op_93"},
                "admissible_individually": True,
            }
            for key in v6.SOURCE_OP93_KEYS
        },
        **{
            key: {
                "candidate": {"target_group": "op_80"},
                "admissible_individually": False,
            }
            for key, _left, _right in v5.OP80_GRID
        },
    }
    selection = {
        "status": v6.SOURCE_TERMINAL_STATUS,
        "selected_candidate_keys": None,
        "eligible_pairs": [],
        "holdout_cases_read": 0,
        "retuning_after_development": False,
        "candidate_summaries": summaries,
    }
    selection[changed] = value
    with pytest.raises(v6.V6ProtocolError, match="exact terminal V5 no-go"):
        v6._validate_terminal_v5_selection(selection)  # noqa: SLF001


def test_v6_rejects_any_v5_holdout_or_non_development_import(tmp_path: Path) -> None:
    v5_run = tmp_path / "v5_run"
    sidecar = tmp_path / "sidecar"
    leaked = v5_run / "engine_attempts" / "holdout"
    leaked.mkdir(parents=True)
    with pytest.raises(v6.V6ProtocolError, match="V5 holdout is visible"):
        v6._assert_v5_holdout_unseen(v5_run, sidecar)  # noqa: SLF001

    development = v5_run / "evidence" / "development"
    development.mkdir(parents=True)
    v6._assert_development_source_path(  # noqa: SLF001
        development / "proof.json", v5_run
    )
    with pytest.raises(v6.V6ProtocolError, match="only V5 development"):
        v6._assert_development_source_path(  # noqa: SLF001
            v5_run / "evidence" / "holdout" / "proof.json", v5_run
        )


def test_v6_end_to_end_executes_only_two_new_op80_candidates(
    tmp_path: Path,
) -> None:
    plan, run, _v5_plan, v5_run, _sidecar = _v6_plan(tmp_path)
    source_selection = v5_run / "development_selection.json"
    source_selection_hash = v6.sha256_file(source_selection)
    source_before = {
        path.relative_to(v5_run).as_posix(): v6.sha256_file(path)
        for path in v5_run.rglob("*")
        if path.is_file()
    }
    validated = v6.validate_plan(
        plan, verify_runtime_dependencies=False, allow_test_source=True
    )
    assert len(validated.candidates) == 5
    assert validated.manifest["supersedes"]["modifies_v5_artifacts"] is False
    assert validated.manifest["holdout_contract"][
        "holdout_execution_supported_by_this_module"
    ] is False

    calls: list[tuple[str, int]] = []

    def executor(**kwargs: Any) -> dict[str, Any]:
        candidate = kwargs["candidate"]
        calls.append((candidate.key, kwargs["seed"]))
        return {"metrics": v4_fixture._metrics(0.80)}  # noqa: SLF001

    progress = v6.run_development(
        plan,
        run,
        executor=executor,
        max_workers=2,
        test_only=True,
    )
    assert progress["completed_case_count"] == 150
    assert len(calls) == 60
    assert {key for key, _seed in calls} == {
        "op80_v6_17_96p6",
        "op80_v6_17p5_96p6",
    }
    assert not (run / "shipment_traces").exists()
    assert not (run / "evidence" / "holdout").exists()

    selection = v6.finalize_development(plan, run, test_only=True)
    assert selection["status"] == v6.SUCCESS_STATUS
    assert selection["holdout_cases_read"] == 0
    assert selection["holdout_execution_supported_by_this_module"] is False
    assert selection["new_candidate_evidence_case_count"] == 60
    assert selection["v5_imported_development_evidence_case_count"] == 90
    assert selection["v5_candidate_engine_rerun_count"] == 0
    assert selection["selected_candidate_keys"]["op_80"] in {
        "op80_v6_17_96p6",
        "op80_v6_17p5_96p6",
    }
    assert selection["selected_candidate_keys"]["op_93"] in set(
        v6.SOURCE_OP93_KEYS
    )
    assert selection["next_step"] == (
        "freeze_a_separate_holdout_protocol_before_execution"
    )
    assert v6.sha256_file(source_selection) == source_selection_hash
    source_after = {
        path.relative_to(v5_run).as_posix(): v6.sha256_file(path)
        for path in v5_run.rglob("*")
        if path.is_file()
    }
    assert source_after == source_before


def test_v6_has_no_holdout_execution_entry_point(tmp_path: Path) -> None:
    with pytest.raises(SystemExit):
        v6._parser().parse_args(["run-holdout"])  # noqa: SLF001
    with pytest.raises(v6.V6ProtocolError, match="development-only"):
        forbidden = tmp_path / "v6_run" / "evidence" / "holdout"
        forbidden.mkdir(parents=True)
        v6._assert_local_holdout_unseen(tmp_path / "v6_run")  # noqa: SLF001
