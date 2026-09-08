#!/usr/bin/env python3
"""Prépare et lance la calibration V5 additive sous supervision.

Le lanceur refuse tout chevauchement avec V4, impose deux moteurs, démarre le
watcher de courbes avant le développement, puis confie au relais l'unique droit
de lancer le holdout après sélection. Il ne lance ni campagne incidents, ni
bridge, ni livraison HTML.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

from etudecas.prototypes.scan_2027_risk_control import (
    supplier_balanced_product_delay_multiseed_refinement_v5 as refinement,
)
from etudecas.prototypes.scan_2027_risk_control import (
    supplier_holdout_curve_sidecar_v4 as capture_v4,
)


CORE_MODULE = (
    "etudecas.prototypes.scan_2027_risk_control."
    "supplier_balanced_product_delay_multiseed_refinement_v5"
)
WATCHER_MODULE = (
    "etudecas.prototypes.scan_2027_risk_control.supplier_holdout_curve_sidecar_v5"
)
RELAY_MODULE = (
    "etudecas.prototypes.scan_2027_risk_control.continue_supplier_v5_calibration"
)
SCHEMA_VERSION = "etudecas.v5_calibration_launcher.receipt.v1"
WORKERS = 2
EXACT_DEVELOPMENT_SEEDS = tuple(range(340287, 340317))


class LaunchError(RuntimeError):
    """Raised before or during creation of the supervised V5 process group."""


@dataclass(frozen=True)
class LaunchPaths:
    repo: Path
    v4_plan_dir: Path
    v4_run_dir: Path
    v4_sidecar_root: Path
    plan_dir: Path
    run_dir: Path
    supervision_dir: Path
    sidecar_dir: Path

    def resolved(self) -> "LaunchPaths":
        return LaunchPaths(
            **{key: value.resolve() for key, value in asdict(self).items()}
        )


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _assert_contract_constants() -> None:
    if (
        tuple(refinement.DEVELOPMENT_SEEDS) != EXACT_DEVELOPMENT_SEEDS
        or len(refinement.OP93_GRID) != 3
        or len(refinement.OP80_GRID) != 3
        or refinement.EXPECTED_NEW_DEVELOPMENT_CASES != 180
        or refinement.EXPECTED_REUSED_DEVELOPMENT_CASES != 30
        or refinement.EXPECTED_DEVELOPMENT_CASES != 210
        or refinement.EXPECTED_HOLDOUT_CASES != 90
    ):
        raise LaunchError("Le cœur V5 ne correspond pas au contrat 3+3 / 30 / 90")


def _overlap(left: Path, right: Path) -> bool:
    left = left.resolve()
    right = right.resolve()
    return left == right or left.is_relative_to(right) or right.is_relative_to(left)


def validate_fresh_paths(paths: LaunchPaths) -> LaunchPaths:
    paths = paths.resolved()
    _assert_contract_constants()
    if not paths.repo.is_dir():
        raise LaunchError("Le dépôt V5 n'existe pas")
    for label, path in (
        ("plan V4", paths.v4_plan_dir),
        ("run V4", paths.v4_run_dir),
    ):
        if not path.is_dir():
            raise LaunchError(f"{label} absent : {path}")
    old = (paths.v4_plan_dir, paths.v4_run_dir, paths.v4_sidecar_root)
    new = (paths.plan_dir, paths.run_dir, paths.supervision_dir, paths.sidecar_dir)
    if any(_overlap(candidate, source) for candidate in new for source in old):
        raise LaunchError("Une sortie V5 chevauche une source V4")
    if any(
        _overlap(left, right)
        for index, left in enumerate(new)
        for right in new[index + 1 :]
    ):
        raise LaunchError("Les sorties V5 doivent être quatre répertoires distincts")
    for path in new:
        if path.exists():
            raise LaunchError(f"Sortie V5 déjà existante : {path}")
    return paths


def build_commands(
    paths: LaunchPaths, *, max_wait_hours: float
) -> dict[str, list[str]]:
    paths = paths.resolved()
    python = sys.executable
    return {
        "prepare_plan": [
            python,
            "-m",
            CORE_MODULE,
            "plan",
            "--output-dir",
            str(paths.plan_dir),
            "--v4-plan-dir",
            str(paths.v4_plan_dir),
            "--v4-run-dir",
            str(paths.v4_run_dir),
            "--v4-sidecar-root",
            str(paths.v4_sidecar_root),
        ],
        "validate_plan": [
            python,
            "-m",
            CORE_MODULE,
            "validate",
            "--plan-dir",
            str(paths.plan_dir),
        ],
        "watcher": [
            python,
            "-m",
            WATCHER_MODULE,
            "watch",
            "--plan-dir",
            str(paths.plan_dir),
            "--run-dir",
            str(paths.run_dir),
            "--output-dir",
            str(paths.sidecar_dir),
            "--poll-ms",
            "25",
            "--stability-ms",
            "12",
            "--timeout-seconds",
            str(max_wait_hours * 3600.0),
        ],
        "development": [
            python,
            "-m",
            CORE_MODULE,
            "run",
            "--plan-dir",
            str(paths.plan_dir),
            "--run-dir",
            str(paths.run_dir),
            "--stage",
            "development",
            "--workers",
            str(WORKERS),
        ],
    }


def build_relay_command(
    paths: LaunchPaths,
    *,
    development_pid: int,
    watcher_pid: int,
    max_wait_hours: float,
) -> list[str]:
    paths = paths.resolved()
    return [
        sys.executable,
        "-m",
        RELAY_MODULE,
        "--repo",
        str(paths.repo),
        "--plan-dir",
        str(paths.plan_dir),
        "--run-dir",
        str(paths.run_dir),
        "--supervision-dir",
        str(paths.supervision_dir),
        "--development-pid",
        str(development_pid),
        "--watcher-pid",
        str(watcher_pid),
        "--sidecar-dir",
        str(paths.sidecar_dir),
        "--max-wait-hours",
        str(max_wait_hours),
    ]


def _run_checked(command: Sequence[str], *, cwd: Path, log_path: Path) -> None:
    with log_path.open("a", encoding="utf-8") as stream:
        result = subprocess.run(
            list(command),
            cwd=cwd,
            stdout=stream,
            stderr=subprocess.STDOUT,
            text=True,
            check=False,
        )
    if result.returncode != 0:
        raise LaunchError(f"Commande préparatoire en échec : {log_path}")


def _spawn(
    command: Sequence[str], *, cwd: Path, log_path: Path
) -> subprocess.Popen[Any]:
    stream = log_path.open("a", encoding="utf-8")
    kwargs: dict[str, Any] = {
        "cwd": cwd,
        "stdout": stream,
        "stderr": subprocess.STDOUT,
        "text": True,
        "stdin": subprocess.DEVNULL,
        "close_fds": True,
    }
    if os.name == "nt":
        kwargs["creationflags"] = (
            subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NO_WINDOW
        )
    else:  # pragma: no cover - campagne Windows, utile aux tests locaux
        kwargs["start_new_session"] = True
    try:
        process = subprocess.Popen(list(command), **kwargs)
    finally:
        stream.close()
    return process


def _receipt(
    paths: LaunchPaths,
    *,
    commands: dict[str, list[str]],
    development_pid: int,
    watcher_pid: int,
    relay_pid: int,
) -> dict[str, Any]:
    module_dir = Path(__file__).resolve().parent
    plan_manifest = paths.plan_dir / "refinement_plan.json"
    unsigned = {
        "schema_version": SCHEMA_VERSION,
        "created_at_utc": _now(),
        "status": "launched",
        "interpretation": (
            "Orchestration additive V5; 180 nouvelles simulations de développement, "
            "30 preuves V4 réutilisées sans moteur, puis 90 holdout fraîches "
            "uniquement après sélection."
        ),
        "paths": {key: str(value) for key, value in asdict(paths).items()},
        "processes": {
            "watcher_pid": watcher_pid,
            "development_pid": development_pid,
            "relay_pid": relay_pid,
        },
        "execution_contract": {
            "workers": WORKERS,
            "development_seeds": list(EXACT_DEVELOPMENT_SEEDS),
            "op93_candidate_count": 3,
            "op80_candidate_count": 3,
            "new_development_engine_runs": 180,
            "reused_op100_proofs": 30,
            "fresh_holdout_engine_runs_if_selected": 90,
        },
        "commands": commands,
        "provenance": {
            "plan_manifest_sha256": capture_v4.sha256_file(plan_manifest),
            "v4_plan_manifest_sha256": capture_v4.sha256_file(
                paths.v4_plan_dir / "refinement_plan.json"
            ),
            "v4_development_selection_sha256": capture_v4.sha256_file(
                paths.v4_run_dir / "development_selection.json"
            ),
            "core_module_sha256": capture_v4.sha256_file(
                module_dir
                / "supplier_balanced_product_delay_multiseed_refinement_v5.py"
            ),
            "watcher_module_sha256": capture_v4.sha256_file(
                module_dir / "supplier_holdout_curve_sidecar_v5.py"
            ),
            "relay_module_sha256": capture_v4.sha256_file(
                module_dir / "continue_supplier_v5_calibration.py"
            ),
        },
    }
    return {**unsigned, "receipt_signature": refinement.stable_sha256(unsigned)}


def launch(paths: LaunchPaths, *, max_wait_hours: float = 16.0) -> dict[str, Any]:
    if max_wait_hours <= 0:
        raise LaunchError("La durée maximale doit être positive")
    paths = validate_fresh_paths(paths)
    paths.supervision_dir.mkdir(parents=True, exist_ok=False)
    commands = build_commands(paths, max_wait_hours=max_wait_hours)
    _run_checked(
        commands["prepare_plan"],
        cwd=paths.repo,
        log_path=paths.supervision_dir / "prepare_plan.log",
    )
    _run_checked(
        commands["validate_plan"],
        cwd=paths.repo,
        log_path=paths.supervision_dir / "validate_plan.log",
    )

    started: list[subprocess.Popen[Any]] = []
    try:
        watcher = _spawn(
            commands["watcher"],
            cwd=paths.repo,
            log_path=paths.supervision_dir / "watcher.log",
        )
        started.append(watcher)
        development = _spawn(
            commands["development"],
            cwd=paths.repo,
            log_path=paths.supervision_dir / "development.log",
        )
        started.append(development)
        relay_command = build_relay_command(
            paths,
            development_pid=development.pid,
            watcher_pid=watcher.pid,
            max_wait_hours=max_wait_hours,
        )
        relay = _spawn(
            relay_command,
            cwd=paths.repo,
            log_path=paths.supervision_dir / "relay_process.log",
        )
        started.append(relay)
        all_commands = {**commands, "relay": relay_command}
        receipt = _receipt(
            paths,
            commands=all_commands,
            development_pid=development.pid,
            watcher_pid=watcher.pid,
            relay_pid=relay.pid,
        )
        capture_v4._atomic_write_json(  # noqa: SLF001
            paths.supervision_dir / "launch_receipt.json", receipt
        )
        return receipt
    except BaseException:
        for process in reversed(started):
            if process.poll() is None:
                process.terminate()
        raise


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--v4-plan-dir", type=Path, required=True)
    parser.add_argument("--v4-run-dir", type=Path, required=True)
    parser.add_argument("--v4-sidecar-root", type=Path, required=True)
    parser.add_argument("--plan-dir", type=Path, required=True)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--supervision-dir", type=Path, required=True)
    parser.add_argument("--sidecar-dir", type=Path, required=True)
    parser.add_argument("--max-wait-hours", type=float, default=16.0)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    receipt = launch(
        LaunchPaths(
            repo=args.repo,
            v4_plan_dir=args.v4_plan_dir,
            v4_run_dir=args.v4_run_dir,
            v4_sidecar_root=args.v4_sidecar_root,
            plan_dir=args.plan_dir,
            run_dir=args.run_dir,
            supervision_dir=args.supervision_dir,
            sidecar_dir=args.sidecar_dir,
        ),
        max_wait_hours=args.max_wait_hours,
    )
    print(json.dumps(receipt, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
