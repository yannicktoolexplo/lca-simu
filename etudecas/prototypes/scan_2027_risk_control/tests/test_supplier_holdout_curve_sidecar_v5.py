from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from etudecas.prototypes.scan_2027_risk_control import (
    supplier_balanced_product_delay_multiseed_refinement_v5 as refinement,
)
from etudecas.prototypes.scan_2027_risk_control import (
    supplier_holdout_curve_sidecar_v4 as capture_v4,
)
from etudecas.prototypes.scan_2027_risk_control import (
    supplier_holdout_curve_sidecar_v5 as sidecar,
)


def _candidates():
    return (
        refinement.Candidate("op100_source", "v5-op100", "op_100", 0, 0, "x", ""),
        refinement.Candidate("op93", "v5-op93", "op_93", 8, 81, "x", ""),
        refinement.Candidate("op80", "v5-op80", "op_80", 19, 97, "x", ""),
    )


def _cases() -> tuple[sidecar.ExpectedCase, ...]:
    return tuple(
        sidecar.ExpectedCase(
            target_group=candidate.target_group,
            candidate_key=candidate.key,
            candidate_id=candidate.candidate_id,
            seed=seed,
            graph_sha256=(candidate.key[2:] + "a" * 64)[:64],
        )
        for candidate in _candidates()
        for seed in refinement.EXPECTED_HOLDOUT_SEEDS
    )


def test_load_cases_uses_v5_validator_and_requires_exact_three_by_thirty(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    candidates = _candidates()
    plan = SimpleNamespace(
        manifest={
            "inventory": {
                candidate.key: {"graph_sha256": (candidate.key + "a" * 64)[:64]}
                for candidate in candidates
            }
        }
    )
    monkeypatch.setattr(refinement, "validate_plan", lambda *args, **kwargs: plan)
    monkeypatch.setattr(
        refinement,
        "_stage_jobs",
        lambda *args: tuple(
            (candidate, seed)
            for candidate in candidates
            for seed in refinement.EXPECTED_HOLDOUT_SEEDS
        ),
    )
    cases = sidecar.load_official_cases(tmp_path / "plan", tmp_path / "run")
    assert len(cases) == 90
    assert {case.target_group for case in cases} == {"op_100", "op_93", "op_80"}
    assert all(
        len({case.seed for case in cases if case.target_group == group}) == 30
        for group in sidecar.EXPECTED_TARGET_GROUPS
    )

    monkeypatch.setattr(refinement, "_stage_jobs", lambda *args: tuple())
    with pytest.raises(sidecar.CurveSidecarError, match="3 x 30"):
        sidecar.load_official_cases(tmp_path / "plan", tmp_path / "run")


def test_contract_and_ready_receipt_are_v5_signed(tmp_path: Path) -> None:
    plan = tmp_path / "plan"
    run = tmp_path / "run"
    output = tmp_path / "sidecar"
    plan.mkdir()
    run.mkdir()
    (plan / "refinement_plan.json").write_text("{}\n", encoding="utf-8")
    (run / "run_manifest.json").write_text("{}\n", encoding="utf-8")
    contract = sidecar.build_contract(
        plan_dir=plan,
        run_dir=run,
        output_dir=output,
        cases=_cases(),
    )
    assert contract["schema_version"] == sidecar.CONTRACT_SCHEMA_VERSION
    assert contract["producer_protocol"] == refinement.SCHEMA_VERSION
    assert contract["expected_case_count"] == 90
    assert contract["fresh_execution_contract"]["engine_execution"].startswith(
        "fresh_after"
    )
    capture_v4._verify_signature(  # noqa: SLF001
        contract, "contract_signature", "test"
    )
    assert sidecar.validate_contract(contract) == contract

    wrong_contract = dict(contract)
    wrong_contract["expected_case_count"] = 89
    with pytest.raises(sidecar.CurveSidecarError, match="Signature invalide"):
        sidecar.validate_contract(wrong_contract)

    ready = sidecar._ready_payload(contract, output_dir=output)  # noqa: SLF001
    output.mkdir()
    capture_v4._atomic_write_json(output / "watcher_ready.json", ready)  # noqa: SLF001
    validated = sidecar.validate_ready(
        output / "watcher_ready.json",
        expected_output_dir=output,
        expected_watcher_pid=ready["watcher_pid"],
    )
    assert validated["expected_case_count"] == 90

    tampered = json.loads((output / "watcher_ready.json").read_text(encoding="utf-8"))
    tampered["expected_case_count"] = 89
    (output / "watcher_ready.json").write_text(json.dumps(tampered), encoding="utf-8")
    with pytest.raises(sidecar.CurveSidecarError, match="Signature invalide"):
        sidecar.validate_ready(output / "watcher_ready.json")


def test_v5_inventory_wraps_the_compatible_base_inventory(tmp_path: Path) -> None:
    output = tmp_path / "sidecar"
    output.mkdir()
    base_path = output / "capture_inventory.json"
    base_path.write_text('{"case_count": 90}\n', encoding="utf-8")
    contract = {"contract_signature": "c" * 64}
    base = {"case_count": 90, "inventory_signature": "i" * 64}
    inventory = sidecar._write_v5_inventory(  # noqa: SLF001
        output_dir=output,
        contract=contract,
        base_inventory=base,
    )
    assert inventory["schema_version"] == sidecar.INVENTORY_SCHEMA_VERSION
    assert inventory["case_count"] == 90
    assert (output / "capture_inventory_v5.json").is_file()
    capture_v4._verify_signature(  # noqa: SLF001
        inventory, "inventory_signature", "test"
    )
