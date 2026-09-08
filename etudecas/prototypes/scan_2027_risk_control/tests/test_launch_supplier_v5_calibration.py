from __future__ import annotations

from pathlib import Path

import pytest

from etudecas.prototypes.scan_2027_risk_control import (
    launch_supplier_v5_calibration as launcher,
)
from etudecas.prototypes.scan_2027_risk_control import (
    supplier_balanced_product_delay_multiseed_refinement_v5 as refinement,
)
from etudecas.prototypes.scan_2027_risk_control import (
    supplier_holdout_curve_sidecar_v4 as capture_v4,
)


def _paths(tmp_path: Path) -> launcher.LaunchPaths:
    repo = tmp_path / "repo"
    v4_plan = tmp_path / "v4_plan"
    v4_run = tmp_path / "v4_run"
    for path in (repo, v4_plan, v4_run):
        path.mkdir()
    (v4_plan / "refinement_plan.json").write_text("{}\n", encoding="utf-8")
    (v4_run / "development_selection.json").write_text("{}\n", encoding="utf-8")
    return launcher.LaunchPaths(
        repo=repo,
        v4_plan_dir=v4_plan,
        v4_run_dir=v4_run,
        v4_sidecar_root=tmp_path / "v4_sidecar_absent",
        plan_dir=tmp_path / "v5_plan",
        run_dir=tmp_path / "v5_run",
        supervision_dir=tmp_path / "v5_supervision",
        sidecar_dir=tmp_path / "v5_sidecar",
    )


def test_commands_freeze_three_plus_three_two_workers_and_fresh_holdout(
    tmp_path: Path,
) -> None:
    paths = _paths(tmp_path)
    launcher._assert_contract_constants()  # noqa: SLF001
    commands = launcher.build_commands(paths, max_wait_hours=12)
    development = commands["development"]
    assert development[development.index("--workers") + 1] == "2"
    assert development[development.index("--stage") + 1] == "development"
    assert commands["watcher"][2] == launcher.WATCHER_MODULE
    assert tuple(refinement.DEVELOPMENT_SEEDS) == tuple(range(340287, 340317))
    assert refinement.EXPECTED_NEW_DEVELOPMENT_CASES == 180
    assert refinement.EXPECTED_HOLDOUT_CASES == 90

    relay = launcher.build_relay_command(
        paths, development_pid=123, watcher_pid=456, max_wait_hours=12
    )
    assert relay[relay.index("--development-pid") + 1] == "123"
    assert relay[relay.index("--watcher-pid") + 1] == "456"


def test_fresh_path_validation_refuses_v4_overlap_and_existing_outputs(
    tmp_path: Path,
) -> None:
    paths = _paths(tmp_path)
    launcher.validate_fresh_paths(paths)

    overlap = launcher.LaunchPaths(
        **{**paths.__dict__, "run_dir": paths.v4_run_dir / "v5"}
    )
    with pytest.raises(launcher.LaunchError, match="chevauche"):
        launcher.validate_fresh_paths(overlap)

    paths.sidecar_dir.mkdir()
    with pytest.raises(launcher.LaunchError, match="déjà existante"):
        launcher.validate_fresh_paths(paths)


def test_launch_order_and_signed_receipt_without_real_processes(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    paths = _paths(tmp_path)
    events: list[str] = []

    def fake_run(command, *, cwd, log_path) -> None:
        del cwd, log_path
        events.append("plan" if "plan" in command else "validate")
        if "plan" in command:
            paths.plan_dir.mkdir()
            (paths.plan_dir / "refinement_plan.json").write_text(
                "{}\n", encoding="utf-8"
            )

    class FakeProcess:
        next_pid = 700

        def __init__(self):
            self.pid = FakeProcess.next_pid
            FakeProcess.next_pid += 1

        def poll(self):
            return None

        def terminate(self):
            events.append(f"terminate-{self.pid}")

    def fake_spawn(command, *, cwd, log_path):
        del cwd, log_path
        events.append(command[2])
        return FakeProcess()

    monkeypatch.setattr(launcher, "_run_checked", fake_run)
    monkeypatch.setattr(launcher, "_spawn", fake_spawn)
    receipt = launcher.launch(paths, max_wait_hours=8)
    assert events == [
        "plan",
        "validate",
        launcher.WATCHER_MODULE,
        launcher.CORE_MODULE,
        launcher.RELAY_MODULE,
    ]
    assert receipt["execution_contract"] == {
        "workers": 2,
        "development_seeds": list(range(340287, 340317)),
        "op93_candidate_count": 3,
        "op80_candidate_count": 3,
        "new_development_engine_runs": 180,
        "reused_op100_proofs": 30,
        "fresh_holdout_engine_runs_if_selected": 90,
    }
    capture_v4._verify_signature(  # noqa: SLF001
        receipt, "receipt_signature", "receipt"
    )
    assert (paths.supervision_dir / "launch_receipt.json").is_file()
