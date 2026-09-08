from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

import pytest

from etudecas.prototypes.scan_2027_risk_control import (
    supplier_fresh_development_holdout_protocol_v7 as v7,
)
from etudecas.prototypes.scan_2027_risk_control import (
    supplier_fresh_development_holdout_monitor_v7 as live_monitor,
)


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


@pytest.fixture
def v6_design(tmp_path: Path) -> tuple[Path, Path, Path, Path]:
    plan_dir = tmp_path / "v6-plan"
    run_dir = tmp_path / "v6-run"
    holdout_path = tmp_path / "v6-holdout" / "holdout_result.json"
    rng_dir = tmp_path / "v6-rng-audit"
    inventory: dict[str, dict[str, str]] = {}
    summaries: dict[str, dict[str, object]] = {}
    for candidate in v7.FIXED_TRIPLET:
        source_candidate = {
            "key": candidate.key,
            "candidate_id": f"fixture_{candidate.key}",
            "target_group": candidate.target_group,
            "offset_days_268091": candidate.offset_days_268091,
            "offset_days_268967": candidate.offset_days_268967,
            "evidence_mode": "fixture",
            "source_operating_point_id": "",
        }
        graph = plan_dir / "graphs" / f"{candidate.key}.json"
        ledger = plan_dir / "ledgers" / f"{candidate.key}.json"
        _write_json(graph, {"candidate": candidate.key})
        _write_json(ledger, {"candidate": candidate.key, "changes": []})
        inventory[candidate.key] = {
            "graph_path": f"graphs/{candidate.key}.json",
            "graph_sha256": v7.sha256_file(graph),
            "ledger_path": f"ledgers/{candidate.key}.json",
            "ledger_sha256": v7.sha256_file(ledger),
        }
        summaries[candidate.key] = {
            "candidate": source_candidate,
            "admissible_individually": True,
        }
    runtime_unsigned: dict[str, object] = {
        "schema_version": "fixture.runtime.v1",
        "file_count": 0,
        "files": [],
    }
    runtime = {
        **runtime_unsigned,
        "aggregate_sha256": v7.stable_sha256(runtime_unsigned),
    }
    execution = {
        "engine": {"path": str(tmp_path / "engine.py"), "sha256": "a" * 64},
        "engine_profile": {
            "path": str(tmp_path / "profile.json"),
            "sha256": "b" * 64,
        },
        "common_random_numbers": True,
        "simulation_days": v7.SERVICE_DAYS,
        "capacity_override": False,
        "quality_incident": False,
        "availability_incident": False,
        "state_dependent_risk": False,
    }
    plan_unsigned: dict[str, object] = {
        "schema_version": v7.V6_PLAN_SCHEMA_VERSION,
        "inventory": inventory,
        "execution_contract": execution,
        "runtime_dependencies": runtime,
    }
    plan = v7._signed(plan_unsigned, "plan_signature")  # noqa: SLF001
    _write_json(plan_dir / "refinement_plan.json", plan)

    selected = {
        "op_100": "op100_source",
        "op_93": "op93_v5_8p4_80p6",
        "op_80": "op80_v6_17p5_96p6",
    }
    selection_unsigned: dict[str, object] = {
        "schema_version": v7.V6_SELECTION_SCHEMA_VERSION,
        "plan_signature": plan["plan_signature"],
        "status": v7.V6_SUCCESS_STATUS,
        "execution_mode": "test_only_v6_injected_executor",
        "publishable": False,
        "holdout_cases_read": 0,
        "holdout_execution_supported_by_this_module": False,
        "retuning_after_development": False,
        "development_seeds": list(v7.V5_V6_DEVELOPMENT_SEEDS),
        "holdout_seeds_sealed_and_unread": list(v7.V5_V6_HOLDOUT_SEEDS),
        "selected_candidate_keys": selected,
        "candidate_summaries": summaries,
    }
    selection = v7._signed(selection_unsigned, "selection_signature")  # noqa: SLF001
    _write_json(run_dir / "development_selection.json", selection)

    holdout_unsigned: dict[str, object] = {
        "schema_version": (
            "etudecas.multiseed_operating_point_holdout.v6.holdout_result"
        ),
        "status": "holdout_rejected_no_retuning",
        "accepted": False,
        "publishable": True,
        "execution_mode": "official_v6_fresh_holdout",
        "retuning_after_holdout": False,
        "failure_rule": "publish_no_go_and_require_new_fresh_cohort",
        "holdout_evidence_case_count": 90,
        "holdout_seeds": list(v7.V5_V6_HOLDOUT_SEEDS),
        "selected_candidate_keys": selected,
        "source_v6_selection_signature": selection["selection_signature"],
        "holdout_evidence_signature_set_sha256": "c" * 64,
    }
    _write_json(
        holdout_path,
        v7._signed(holdout_unsigned, "holdout_signature"),  # noqa: SLF001
    )

    audit_unsigned: dict[str, object] = {
        "schema_version": "etudecas.supplier_v6_rng_pairing_audit.v1.audit",
        "conclusion": "aucun_defaut_rng_prouve",
        "fixture": True,
    }
    audit = v7._signed(audit_unsigned, "audit_signature")  # noqa: SLF001
    audit_path = rng_dir / "supplier_v6_rng_pairing_audit.json"
    _write_json(audit_path, audit)
    csv_path = rng_dir / "supplier_v6_rng_pairing_seed_summary.csv"
    csv_path.write_text("seed,status\n1,ok\n", encoding="utf-8")
    report_path = rng_dir / "RAPPORT_AUDIT_COUPLAGE_ALEATOIRE_V6_FR.md"
    report_path.write_text("# Fixture\n", encoding="utf-8")
    audit_files = [audit_path, csv_path, report_path]
    manifest_unsigned: dict[str, object] = {
        "schema_version": "etudecas.supplier_v6_rng_pairing_audit.v1.manifest",
        "audit_module_sha256": "d" * 64,
        "audit_signature": audit["audit_signature"],
        "conclusion": "aucun_defaut_rng_prouve",
        "files": [
            {
                "relative_path": path.name,
                "sha256": v7.sha256_file(path),
                "size_bytes": path.stat().st_size,
            }
            for path in sorted(audit_files, key=lambda item: item.name)
        ],
    }
    _write_json(
        rng_dir / "artifact_manifest.json",
        v7._signed(manifest_unsigned, "manifest_signature"),  # noqa: SLF001
    )
    return plan_dir, run_dir, holdout_path, rng_dir


def _prepare(tmp_path: Path, source: tuple[Path, Path, Path, Path]) -> Path:
    plan_dir, run_dir, holdout_path, rng_dir = source
    output = tmp_path / "v7-plan"
    v7.prepare_plan(
        output,
        v6_plan_dir=plan_dir,
        v6_run_dir=run_dir,
        v6_holdout_result=holdout_path,
        rng_audit_dir=rng_dir,
        reviewed_module_sha256=v7.sha256_file(Path(v7.__file__)),
        allow_test_source=True,
    )
    return output


def _metrics(service: float) -> dict[str, float]:
    return {
        "demand_qty_268091": 1_000.0,
        "demand_qty_268967": 1_000.0,
        "demand_qty_global": 2_000.0,
        "on_due_qty_268091": 1_000.0 * service,
        "on_due_qty_268967": 1_000.0 * service,
        "on_due_qty_global": 2_000.0 * service,
        "on_due_service_268091": service,
        "on_due_service_268967": service,
        "system_on_due_service": service,
    }


def _passing_executor(**kwargs: Any) -> dict[str, object]:
    service = {"op_100": 0.999, "op_93": 0.93, "op_80": 0.80}[
        kwargs["candidate"].target_group
    ]
    return {"metrics": _metrics(service)}


def test_plan_freezes_one_triplet_150_new_blocks_and_450_fresh_cases(
    tmp_path: Path, v6_design: tuple[Path, Path, Path, Path]
) -> None:
    output = _prepare(tmp_path, v6_design)
    plan = v7.validate_plan(output, allow_test_source=True, verify_runtime=False)
    registry = v7._read_json(output / "case_registry.json")  # noqa: SLF001

    assert len(plan.candidates) == 3
    assert plan.manifest["cohort"]["seed_count"] == 150
    assert plan.manifest["cohort"]["case_count"] == 450
    assert registry["case_count"] == 450
    assert registry["imported_evidence_case_count"] == 0
    assert plan.manifest["decision_contract"]["bootstrap"]["replicates"] == 50_000
    assert plan.manifest["decision_contract"]["interim_decision_allowed"] is False
    assert plan.manifest["retention_contract"]["capture_timing"].endswith(
        "before_canonical_prune"
    )
    assert (
        plan.manifest["retention_contract"]["evidence_commit_timing"]
        == "only_after_verified_canonical_prune"
    )
    assert (
        plan.manifest["retention_contract"]["final_engine_attempt_cleanliness_required"]
        is True
    )
    assert not any((output / name).exists() for name in ("evidence", "curves"))


def test_seed_derivation_is_reproducible_unique_and_disjoint() -> None:
    assert len(v7.V7_VALIDATION_SEEDS) == 150
    assert len(set(v7.V7_VALIDATION_SEEDS)) == 150
    assert not set(v7.V7_VALIDATION_SEEDS) & v7.PRIOR_SEEDS
    assert v7.V7_VALIDATION_SEEDS == v7._derive_seed_cohort(  # noqa: SLF001
        v7.V7_VALIDATION_SEED_DOMAIN, 150, set(v7.PRIOR_SEEDS)
    )


def test_v6_rejection_and_rng_audit_are_diagnostics_not_v7_evidence(
    tmp_path: Path, v6_design: tuple[Path, Path, Path, Path]
) -> None:
    output = _prepare(tmp_path, v6_design)
    manifest = v7._read_json(output / "protocol_manifest.json")  # noqa: SLF001
    holdout = manifest["v6_design_provenance"]["v6_holdout_diagnostic"]
    rng = manifest["rng_pairing_audit"]

    assert holdout["status"] == "holdout_rejected_no_retuning"
    assert holdout["used_for_protocol_diagnosis_and_sample_sizing"] is True
    assert holdout["reused_as_v7_acceptance_evidence"] is False
    assert rng["conclusion"] == "aucun_defaut_rng_prouve"
    assert rng["role"] == "protocol_diagnostic_not_v7_acceptance_evidence"


def test_wrong_review_hash_and_tampered_rng_audit_are_rejected(
    tmp_path: Path, v6_design: tuple[Path, Path, Path, Path]
) -> None:
    plan_dir, run_dir, holdout_path, rng_dir = v6_design
    with pytest.raises(v7.V7ProtocolError, match="reviewed"):
        v7.prepare_plan(
            tmp_path / "wrong-review",
            v6_plan_dir=plan_dir,
            v6_run_dir=run_dir,
            v6_holdout_result=holdout_path,
            rng_audit_dir=rng_dir,
            reviewed_module_sha256="0" * 64,
            allow_test_source=True,
        )
    (rng_dir / "supplier_v6_rng_pairing_seed_summary.csv").write_text(
        "tampered", encoding="utf-8"
    )
    with pytest.raises(v7.V7ProtocolError, match="audit file changed"):
        v7.prepare_plan(
            tmp_path / "bad-audit",
            v6_plan_dir=plan_dir,
            v6_run_dir=run_dir,
            v6_holdout_result=holdout_path,
            rng_audit_dir=rng_dir,
            reviewed_module_sha256=v7.sha256_file(Path(v7.__file__)),
            allow_test_source=True,
        )


def test_prepare_run_monitor_and_early_finalization_start_no_engine(
    tmp_path: Path, v6_design: tuple[Path, Path, Path, Path]
) -> None:
    plan = _prepare(tmp_path, v6_design)
    run = tmp_path / "v7-run"
    registered = v7.prepare_run(plan, run, test_only=True)
    status = v7.validation_status(plan, run, test_only=True)

    assert registered["new_engine_runs_by_registration"] == 0
    assert status["completed_case_count"] == 0
    assert status["engine_runs_started_by_monitor"] == 0
    with pytest.raises(v7.V7ProtocolError, match="compact curve inventory|450"):
        v7.finalize_validation(plan, run, test_only=True)


def test_official_v4_adapter_supplies_proof_contract_without_running_engine(
    tmp_path: Path, v6_design: tuple[Path, Path, Path, Path]
) -> None:
    plan_dir = _prepare(tmp_path, v6_design)
    plan = v7.validate_plan(plan_dir, allow_test_source=True, verify_runtime=False)
    v4, adapter = v7._v4_adapter(plan)  # noqa: SLF001
    candidate = next(
        item
        for item in adapter["candidate_by_key"].values()
        if item.target_group == "op_93"
    )
    seed = v7.V7_VALIDATION_SEEDS[0]
    engine_sha = plan.manifest["execution_contract"]["engine"]["sha256"]
    unsigned = {
        "schema_version": v4.COARSE_EVIDENCE_SCHEMA_VERSION,
        "candidate_id": candidate.candidate_id,
        "offset_days_268091": candidate.offset_days_268091,
        "offset_days_268967": candidate.offset_days_268967,
        "seed": seed,
        "valid": True,
        "validation_errors": [],
        "graph_sha256": plan.manifest["inventory"][candidate.key]["graph_sha256"],
        "engine_sha256": engine_sha,
        "status": "executed",
        "summary_sha256": "1" * 64,
        "service_daily_sha256": "2" * 64,
        "command_sha256": "3" * 64,
        "run_dir": str(tmp_path / "simulated-official-case"),
        "metrics": _metrics(0.93),
    }
    raw = {**unsigned, "evidence_signature": v4.stable_sha256(unsigned)}

    metrics, proof = v4._executor_output(  # noqa: SLF001
        raw,
        candidate=candidate,
        seed=seed,
        plan=adapter["validated_plan"],
        injected=False,
    )

    assert metrics["system_on_due_service"] == pytest.approx(0.93)
    assert proof["kind"] == "coarse_execute_candidate"
    assert (
        adapter["validated_plan"].manifest["source_hashes"]["engine_sha256"]
        == engine_sha
    )
    assert "source_hashes" not in plan.manifest


def test_existing_plan_output_is_never_overwritten(
    tmp_path: Path, v6_design: tuple[Path, Path, Path, Path]
) -> None:
    plan_dir, run_dir, holdout_path, rng_dir = v6_design
    output = tmp_path / "exists"
    output.mkdir()
    marker = output / "keep.txt"
    marker.write_text("keep", encoding="utf-8")
    with pytest.raises(FileExistsError, match="overwrite"):
        v7.prepare_plan(
            output,
            v6_plan_dir=plan_dir,
            v6_run_dir=run_dir,
            v6_holdout_result=holdout_path,
            rng_audit_dir=rng_dir,
            reviewed_module_sha256=v7.sha256_file(Path(v7.__file__)),
            allow_test_source=True,
        )
    assert marker.read_text(encoding="utf-8") == "keep"


def test_full_injected_run_resumes_retains_outputs_and_finalizes_at_150_blocks(
    tmp_path: Path, v6_design: tuple[Path, Path, Path, Path]
) -> None:
    plan = _prepare(tmp_path, v6_design)
    run = tmp_path / "v7-run"
    calls = 0
    fail_once = True

    def flaky(**kwargs: Any) -> dict[str, object]:
        nonlocal calls, fail_once
        calls += 1
        if fail_once and calls == 8:
            fail_once = False
            raise RuntimeError("fixture interruption")
        return _passing_executor(**kwargs)

    with pytest.raises(RuntimeError, match="fixture interruption"):
        v7.run_validation(plan, run, executor=flaky, max_workers=1, test_only=True)
    assert v7.validation_status(plan, run, test_only=True)["completed_case_count"] == 7

    progress = v7.run_validation(
        plan,
        run,
        executor=_passing_executor,
        max_workers=2,
        test_only=True,
    )
    assert progress["completed_case_count"] == 450
    assert progress["completed_seed_block_count"] == 150
    assert not (run / "validation_result.json").exists()
    assert len(list((run / "curves").rglob("*.json.gz"))) == 450
    assert len(list((run / "snapshots").rglob("*.gz"))) == 450 * len(v7.BUNDLE_SPECS)
    assert sorted(path.name for path in (run / "checkpoints").glob("*.json")) == [
        "checkpoint_030.json",
        "checkpoint_060.json",
        "checkpoint_090.json",
        "checkpoint_120.json",
        "checkpoint_150.json",
    ]
    for path in (run / "checkpoints").glob("*.json"):
        checkpoint = v7._read_json(path)  # noqa: SLF001
        assert checkpoint["acceptance_criteria_evaluated"] is False
        assert checkpoint["early_stop_or_decision_authorized"] is False

    result = v7.finalize_validation(plan, run, test_only=True)
    assert result["accepted"] is True
    assert result["status"] == v7.ACCEPTED_STATUS
    assert all(result["primary_checks"].values())
    assert result["bootstrap"]["replicates"] == 50_000
    assert result["seedwise_monotonicity_is_acceptance_gate"] is False
    assert result["common_seed_diagnostics"]["acceptance_gate"] is False
    result_bytes = (run / "validation_result.json").read_bytes()
    progress_bytes = (run / "progress.json").read_bytes()
    checkpoint_bytes = {
        path.name: path.read_bytes() for path in (run / "checkpoints").glob("*.json")
    }
    with pytest.raises(v7.V7ProtocolError, match="already finalized"):
        v7.run_validation(
            plan,
            run,
            executor=_passing_executor,
            max_workers=2,
            test_only=True,
        )
    assert (run / "validation_result.json").read_bytes() == result_bytes
    assert (run / "progress.json").read_bytes() == progress_bytes
    assert {
        path.name: path.read_bytes() for path in (run / "checkpoints").glob("*.json")
    } == checkpoint_bytes
    assert v7.validate_result(plan, run, test_only=True) == result
    evidence_index = v7.validated_evidence(plan, run, test_only=True)
    assert len(evidence_index) == 450
    first_bundle = next(iter(evidence_index.values()))["retained_bundle"]
    assert any(
        row["source_relative_path"] == "data/production_supplier_shipments_daily.csv"
        for row in first_bundle["files"]
    )


def test_official_transaction_prunes_before_commit_and_cleans_crash_orphans(
    tmp_path: Path,
    v6_design: tuple[Path, Path, Path, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    plan_dir = _prepare(tmp_path, v6_design)
    plan = v7.validate_plan(plan_dir, allow_test_source=True, verify_runtime=False)
    candidate = next(item for item in plan.candidates if item.target_group == "op_93")
    seed = v7.V7_VALIDATION_SEEDS[0]
    run_dir = tmp_path / "official-simulated-run"
    events: list[str] = []

    class FakeV4:
        fail_prune = True
        require_precommit = True

        def _real_executor(self, **kwargs: Any) -> dict[str, object]:
            case_dir = (
                kwargs["attempt_root"]
                / "cases"
                / kwargs["candidate"].candidate_id
                / f"seed_{kwargs['seed']}"
            )
            data_dir = case_dir / "data"
            data_dir.mkdir(parents=True)
            demand = 1_000.0 / v7.SERVICE_DAYS
            served = demand * 0.93
            lines = [
                "day,node_id,item_id,demand_qty,required_with_backlog_qty,"
                "served_qty,backlog_end_qty"
            ]
            for product in v7.PRODUCTS:
                lines.extend(
                    f"{day},C-XXXXX,item:{product},{demand},{demand},{served},0"
                    for day in range(v7.SERVICE_DAYS)
                )
            service_path = data_dir / "production_demand_service_daily.csv"
            service_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
            for relative, _required in v7.BUNDLE_SPECS:
                path = case_dir / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                if relative == "data/production_demand_service_daily.csv":
                    continue
                if relative == "summaries/first_simulation_summary.json":
                    _write_json(
                        path,
                        {
                            "policy": {
                                "seed": seed,
                                "common_random_numbers": True,
                                "warmup_boundary_audit": {
                                    "component_sha256": {
                                        "paired_rng_invocations": "4" * 64,
                                        "rng_state": "5" * 64,
                                    },
                                    "core_state_sha256": "6" * 64,
                                },
                            }
                        },
                    )
                else:
                    path.write_text(f"fixture,{relative}\n", encoding="utf-8")
            events.append("engine_output")
            return {
                "metrics": _metrics(0.93),
                "run_dir": str(case_dir.resolve()),
                "service_daily_sha256": v7.sha256_file(service_path),
            }

        def _executor_output(self, raw: dict[str, object], **_kwargs: Any) -> Any:
            events.append("proof_validated")
            return raw["metrics"], {
                "kind": "coarse_execute_candidate",
                "raw_evidence": raw,
            }

        def _validate_coarse_executor_evidence(
            self, raw: dict[str, object], **_kwargs: Any
        ) -> Any:
            return raw["metrics"]

        def _coarse_case_dir(
            self,
            raw: dict[str, object],
            _run_dir: Path,
            _candidate: Any,
            _seed: int,
        ) -> Path:
            return Path(str(raw["run_dir"])).resolve()

        def _prune_real_executor_case(
            self,
            proof: dict[str, object],
            _run_dir: Path,
            _candidate: Any,
            _seed: int,
        ) -> None:
            events.append("prune")
            if self.require_precommit:
                assert not v7._evidence_path(  # noqa: SLF001
                    run_dir, candidate, seed
                ).exists()
            if self.fail_prune:
                raise RuntimeError("simulated prune crash")
            case_dir = Path(str(proof["raw_evidence"]["run_dir"]))
            for name in v7._ENGINE_HEAVY_DIRECTORY_NAMES:  # noqa: SLF001
                path = case_dir / name
                if path.exists():
                    shutil.rmtree(path)

    fake = FakeV4()
    adapter = {
        "validated_plan": object(),
        "candidate_by_key": {item.key: item for item in plan.candidates},
    }
    monkeypatch.setattr(v7, "_runtime_preflight", lambda _plan: None)
    monkeypatch.setattr(v7, "_v4_adapter", lambda _plan: (fake, adapter))

    with pytest.raises(RuntimeError, match="prune crash"):
        v7._execute_one(  # noqa: SLF001
            plan=plan,
            run_dir=run_dir,
            candidate=candidate,
            seed=seed,
            mode=v7.OFFICIAL_EXECUTION_MODE,
            executor=None,
        )
    assert not v7._evidence_path(run_dir, candidate, seed).exists()  # noqa: SLF001
    assert any((path / "data").exists() for path in run_dir.rglob(f"seed_{seed}"))
    assert list((run_dir / "snapshots").rglob("*.gz"))
    assert list((run_dir / "curves").rglob("*.json.gz"))

    fake.fail_prune = False
    v7._cleanup_official_attempts(plan, run_dir)  # noqa: SLF001
    v7._validate_official_attempt_cleanliness(plan, run_dir)  # noqa: SLF001

    original_write_json = v7._write_json  # noqa: SLF001

    def crash_before_commit(path: Path, payload: dict[str, object]) -> None:
        if path.parent.name == "evidence":
            raise RuntimeError("simulated evidence commit crash")
        original_write_json(path, payload)

    monkeypatch.setattr(v7, "_write_json", crash_before_commit)
    with pytest.raises(RuntimeError, match="commit crash"):
        v7._execute_one(  # noqa: SLF001
            plan=plan,
            run_dir=run_dir,
            candidate=candidate,
            seed=seed,
            mode=v7.OFFICIAL_EXECUTION_MODE,
            executor=None,
        )
    assert not v7._evidence_path(run_dir, candidate, seed).exists()  # noqa: SLF001
    v7._validate_official_attempt_cleanliness(plan, run_dir)  # noqa: SLF001

    monkeypatch.setattr(v7, "_write_json", original_write_json)
    evidence = v7._execute_one(  # noqa: SLF001
        plan=plan,
        run_dir=run_dir,
        candidate=candidate,
        seed=seed,
        mode=v7.OFFICIAL_EXECUTION_MODE,
        executor=None,
    )
    assert v7._evidence_path(run_dir, candidate, seed).is_file()  # noqa: SLF001
    assert evidence["retained_bundle"]["files"]
    fake.require_precommit = False
    v7._cleanup_official_attempts(plan, run_dir)  # noqa: SLF001
    v7._validate_official_attempt_cleanliness(plan, run_dir)  # noqa: SLF001
    assert events.count("prune") >= 4


def test_tampered_retained_snapshot_is_detected(
    tmp_path: Path, v6_design: tuple[Path, Path, Path, Path]
) -> None:
    plan = _prepare(tmp_path, v6_design)
    run = tmp_path / "v7-run"
    v7.prepare_run(plan, run, test_only=True)
    validated = v7.validate_plan(plan, allow_test_source=True, verify_runtime=False)
    candidate = validated.candidates[0]
    seed = v7.V7_VALIDATION_SEEDS[0]
    evidence = v7._execute_one(  # noqa: SLF001
        plan=validated,
        run_dir=run,
        candidate=candidate,
        seed=seed,
        mode=v7.TEST_ONLY_EXECUTION_MODE,
        executor=_passing_executor,
    )
    with pytest.raises(v7.V7ProtocolError, match="aggregate differs"):
        v7._validate_curve_reference(  # noqa: SLF001
            evidence["compact_curve"],
            plan=validated,
            run_dir=run,
            candidate=candidate,
            seed=seed,
            expected_metrics=_metrics(0.80),
        )

    duplicate_bundle = json.loads(json.dumps(evidence["retained_bundle"]))
    duplicate_bundle.pop("bundle_signature")
    duplicate_bundle["files"].append(dict(duplicate_bundle["files"][0]))
    duplicate_bundle = v7._signed(  # noqa: SLF001
        duplicate_bundle, "bundle_signature"
    )
    with pytest.raises(v7.V7ProtocolError, match="Duplicate"):
        v7._validate_bundle_reference(  # noqa: SLF001
            duplicate_bundle,
            plan=validated,
            run_dir=run,
            candidate=candidate,
            seed=seed,
        )

    snapshot = run / evidence["retained_bundle"]["files"][0]["relative_path"]
    snapshot.write_bytes(b"tampered")
    with pytest.raises(v7.V7ProtocolError, match="bundle gzip"):
        v7.validation_status(plan, run, test_only=True)


def test_seedwise_ties_are_secondary_and_not_inversions() -> None:
    rows = {
        group: [{"metrics": _metrics(service)}]
        for group, service in (("op_100", 1.0), ("op_93", 1.0), ("op_80", 0.8))
    }
    diagnostic = v7._seedwise_diagnostics(rows)  # noqa: SLF001
    assert diagnostic["acceptance_gate"] is False
    assert diagnostic["by_measure"]["global"]["tie_count_op100_op93"] == 1
    assert diagnostic["by_measure"]["global"]["inversion_count_op100_below_op93"] == 0


def test_live_monitor_validates_committed_evidence_and_tolerates_active_attempt(
    tmp_path: Path, v6_design: tuple[Path, Path, Path, Path]
) -> None:
    plan_dir = _prepare(tmp_path, v6_design)
    run_dir = tmp_path / "live-monitor-run"
    v7.prepare_run(plan_dir, run_dir, test_only=True)
    plan = v7.validate_plan(plan_dir, allow_test_source=True, verify_runtime=False)
    candidate = plan.candidates[0]
    seed = v7.V7_VALIDATION_SEEDS[0]
    v7._execute_one(  # noqa: SLF001
        plan=plan,
        run_dir=run_dir,
        candidate=candidate,
        seed=seed,
        mode=v7.TEST_ONLY_EXECUTION_MODE,
        executor=_passing_executor,
    )
    active_candidate = plan.candidates[1]
    active_seed = v7.V7_VALIDATION_SEEDS[1]
    active_case = (
        run_dir
        / "engine_attempts"
        / v7._attempt_digest(active_candidate, active_seed)  # noqa: SLF001
        / "attempt-123-0123456789abcdef0123456789abcdef"
        / "cases"
        / active_candidate.candidate_id
        / f"seed_{active_seed}"
    )
    (active_case / "data").mkdir(parents=True)

    observed = live_monitor.inspect_run(
        plan_dir,
        run_dir,
        allow_test_source=True,
        verify_runtime=False,
    )

    assert observed["read_only"] is True
    assert observed["committed_evidence"]["validated_case_count"] == 1
    assert observed["progress"]["state"] == "not_written_yet"
    assert observed["attempts"]["committed_attempts_verified_clean"] == 0
    assert observed["attempts"]["uncommitted_attempt_count"] == 1
    active = observed["attempts"]["uncommitted_attempts"][0]
    assert active["candidate_key"] == active_candidate.key
    assert active["seed"] == active_seed
    assert active["heavy_directories_present"] == ["data"]
    assert observed["descriptive_checkpoint"]["descriptive_only"] is True


def test_cli_exposes_plan_runner_monitor_and_finalizer() -> None:
    help_text = v7._parser().format_help()  # noqa: SLF001
    for command in (
        "prepare-plan",
        "validate-plan",
        "prepare-run",
        "run-validation",
        "status",
        "finalize",
        "validate-result",
    ):
        assert command in help_text
