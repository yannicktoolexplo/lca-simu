#!/usr/bin/env python3
"""Capture non invasive des courbes du holdout V5 (90 simulations fraîches).

Le moteur de capture binaire/CSV de V4 est réutilisé sans le modifier.  Cette
enveloppe remplace uniquement la découverte des cas par le validateur V5, publie
un accusé de préparation que le relais peut vérifier avant de lancer le holdout,
et ajoute un inventaire V5 signé.  Les sorties restent compatibles avec
``supplier_holdout_curve_aggregator_v4``.

Comme en V4, le lecteur est externe au producteur : la capture est fail-closed,
mais ne peut pas promettre zéro perte sans barrière transactionnelle avant
l'élagage des fichiers moteur.
"""

from __future__ import annotations

import argparse
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

from etudecas.prototypes.scan_2027_risk_control import (
    supplier_balanced_product_delay_multiseed_refinement_v5 as refinement,
)
from etudecas.prototypes.scan_2027_risk_control import (
    supplier_holdout_curve_sidecar_v4 as capture_v4,
)
from etudecas.prototypes.scan_2027_risk_control.continue_supplier_v4_calibration import (
    _process_running,
)


SCHEMA_VERSION = "etudecas.supplier_holdout_curve_sidecar.v5"
CONTRACT_SCHEMA_VERSION = f"{SCHEMA_VERSION}.contract.v1"
READY_SCHEMA_VERSION = f"{SCHEMA_VERSION}.watcher_ready.v1"
INVENTORY_SCHEMA_VERSION = f"{SCHEMA_VERSION}.inventory.v1"
EXPECTED_TARGET_GROUPS = ("op_100", "op_93", "op_80")
EXPECTED_CASES_PER_GROUP = 30
EXPECTED_CASE_COUNT = 90

DEFAULT_POLL_SECONDS = capture_v4.DEFAULT_POLL_SECONDS
DEFAULT_STABILITY_SECONDS = capture_v4.DEFAULT_STABILITY_SECONDS
DEFAULT_HORIZON = capture_v4.DEFAULT_HORIZON

CurveSidecarError = capture_v4.CurveSidecarError
ExpectedCase = capture_v4.ExpectedCase


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _assert_exact_matrix(cases: Sequence[ExpectedCase]) -> None:
    if (
        len(cases) != EXPECTED_CASE_COUNT
        or {case.target_group for case in cases} != set(EXPECTED_TARGET_GROUPS)
        or any(
            sum(case.target_group == group for case in cases)
            != EXPECTED_CASES_PER_GROUP
            for group in EXPECTED_TARGET_GROUPS
        )
        or len({case.identity for case in cases}) != len(cases)
        or any(
            {case.seed for case in cases if case.target_group == group}
            != set(refinement.EXPECTED_HOLDOUT_SEEDS)
            for group in EXPECTED_TARGET_GROUPS
        )
    ):
        raise CurveSidecarError("Le holdout V5 attendu n'est pas exactement 3 x 30")


def load_official_cases(plan_dir: Path, run_dir: Path) -> tuple[ExpectedCase, ...]:
    """Charge les 90 identités exclusivement via le contrat V5 signé."""

    plan = refinement.validate_plan(
        plan_dir.resolve(), verify_runtime_dependencies=True
    )
    try:
        jobs = refinement._stage_jobs(  # noqa: SLF001 - primitive V5 épinglée
            plan, run_dir.resolve(), "holdout"
        )
    except Exception as exc:
        raise CurveSidecarError(
            "La sélection V5 ne permet pas le holdout 3 x 30"
        ) from exc
    cases = tuple(
        ExpectedCase(
            target_group=candidate.target_group,
            candidate_key=candidate.key,
            candidate_id=capture_v4._validate_candidate_component(  # noqa: SLF001
                candidate.candidate_id, "candidate_id"
            ),
            seed=int(seed),
            graph_sha256=str(plan.manifest["inventory"][candidate.key]["graph_sha256"]),
        )
        for candidate, seed in jobs
    )
    _assert_exact_matrix(cases)
    return cases


def build_contract(
    *,
    plan_dir: Path,
    run_dir: Path,
    output_dir: Path,
    cases: Sequence[ExpectedCase],
    horizon: int = DEFAULT_HORIZON,
) -> dict[str, Any]:
    """Construit un contrat V5 tout en conservant le format de capture V4."""

    _assert_exact_matrix(cases)
    contract = capture_v4.build_contract(
        plan_dir=plan_dir,
        run_dir=run_dir,
        output_dir=output_dir,
        cases=cases,
        horizon=horizon,
    )
    unsigned = dict(contract)
    unsigned.pop("contract_signature", None)
    unsigned.update(
        {
            "schema_version": CONTRACT_SCHEMA_VERSION,
            "producer_protocol": refinement.SCHEMA_VERSION,
            "capture_core": "supplier_holdout_curve_sidecar_v4",
            "fresh_execution_contract": {
                "case_count": EXPECTED_CASE_COUNT,
                "groups": list(EXPECTED_TARGET_GROUPS),
                "cases_per_group": EXPECTED_CASES_PER_GROUP,
                "engine_execution": "fresh_after_signed_development_selection",
                "seed_set": list(refinement.EXPECTED_HOLDOUT_SEEDS),
            },
        }
    )
    return {
        **unsigned,
        "contract_signature": capture_v4.stable_sha256(unsigned),
    }


def validate_contract(contract: Mapping[str, Any]) -> dict[str, Any]:
    """Vérifie l'enveloppe V5 avant toute lecture ou finalisation."""

    payload = dict(contract)
    capture_v4._verify_signature(  # noqa: SLF001
        payload, "contract_signature", "contrat sidecar V5"
    )
    try:
        cases = tuple(ExpectedCase(**item) for item in payload.get("cases") or ())
    except (TypeError, ValueError) as exc:
        raise CurveSidecarError("Cas du contrat sidecar V5 invalides") from exc
    _assert_exact_matrix(cases)
    fresh = payload.get("fresh_execution_contract") or {}
    if (
        payload.get("schema_version") != CONTRACT_SCHEMA_VERSION
        or payload.get("producer_protocol") != refinement.SCHEMA_VERSION
        or payload.get("capture_core") != "supplier_holdout_curve_sidecar_v4"
        or int(payload.get("expected_case_count") or -1) != EXPECTED_CASE_COUNT
        or int(fresh.get("case_count") or -1) != EXPECTED_CASE_COUNT
        or fresh.get("groups") != list(EXPECTED_TARGET_GROUPS)
        or int(fresh.get("cases_per_group") or -1) != EXPECTED_CASES_PER_GROUP
        or fresh.get("engine_execution") != "fresh_after_signed_development_selection"
        or tuple(fresh.get("seed_set") or ())
        != tuple(refinement.EXPECTED_HOLDOUT_SEEDS)
    ):
        raise CurveSidecarError("Contrat sidecar V5 incohérent")
    return payload


def _ready_payload(contract: Mapping[str, Any], *, output_dir: Path) -> dict[str, Any]:
    unsigned = {
        "schema_version": READY_SCHEMA_VERSION,
        "created_at_utc": _now(),
        "watcher_pid": os.getpid(),
        "output_directory": str(output_dir.resolve()),
        "contract_signature": contract["contract_signature"],
        "expected_case_count": EXPECTED_CASE_COUNT,
        "holdout_seed_count": len(refinement.EXPECTED_HOLDOUT_SEEDS),
        "status": "ready_before_holdout",
    }
    return {**unsigned, "ready_signature": capture_v4.stable_sha256(unsigned)}


def validate_ready(
    path: Path,
    *,
    expected_output_dir: Path | None = None,
    expected_watcher_pid: int | None = None,
) -> dict[str, Any]:
    payload = capture_v4._read_json(path)  # noqa: SLF001
    capture_v4._verify_signature(  # noqa: SLF001
        payload, "ready_signature", "accusé watcher V5"
    )
    if (
        payload.get("schema_version") != READY_SCHEMA_VERSION
        or payload.get("status") != "ready_before_holdout"
        or int(payload.get("expected_case_count") or -1) != EXPECTED_CASE_COUNT
        or int(payload.get("holdout_seed_count") or -1)
        != len(refinement.EXPECTED_HOLDOUT_SEEDS)
        or int(payload.get("watcher_pid") or -1) <= 0
    ):
        raise CurveSidecarError("Accusé watcher V5 incohérent")
    if (
        expected_output_dir is not None
        and Path(str(payload.get("output_directory") or "")).resolve()
        != expected_output_dir.resolve()
    ):
        raise CurveSidecarError("Répertoire de l'accusé watcher V5 incohérent")
    if expected_watcher_pid is not None and int(
        payload.get("watcher_pid") or -1
    ) != int(expected_watcher_pid):
        raise CurveSidecarError("PID de l'accusé watcher V5 incohérent")
    return payload


def _write_v5_inventory(
    *,
    output_dir: Path,
    contract: Mapping[str, Any],
    base_inventory: Mapping[str, Any],
) -> dict[str, Any]:
    base_path = output_dir / "capture_inventory.json"
    unsigned = {
        "schema_version": INVENTORY_SCHEMA_VERSION,
        "created_at_utc": _now(),
        "status": "complete",
        "contract_signature": contract["contract_signature"],
        "case_count": int(base_inventory["case_count"]),
        "base_inventory_path": str(base_path.resolve()),
        "base_inventory_sha256": capture_v4.sha256_file(base_path),
        "base_inventory_signature": base_inventory["inventory_signature"],
        "interpretation": (
            "Courbes descriptives de 90 simulations de holdout V5 fraîches; "
            "ni observations fournisseurs, ni probabilités historiques."
        ),
    }
    payload = {**unsigned, "inventory_signature": capture_v4.stable_sha256(unsigned)}
    path = output_dir / "capture_inventory_v5.json"
    if path.exists():
        existing = capture_v4._read_json(path)  # noqa: SLF001
        capture_v4._verify_signature(  # noqa: SLF001
            existing, "inventory_signature", "inventaire V5"
        )
        comparable_existing = dict(existing)
        comparable_payload = dict(payload)
        for candidate in (comparable_existing, comparable_payload):
            candidate.pop("created_at_utc", None)
            candidate.pop("inventory_signature", None)
        if comparable_existing != comparable_payload:
            raise CurveSidecarError("Un inventaire V5 différent existe déjà")
        return existing
    capture_v4._atomic_write_json(path, payload)  # noqa: SLF001
    return payload


class V5CurveCaptureWatcher(capture_v4.CurveCaptureWatcher):
    """Watcher V4 éprouvé, avec terminaison et inventaire V5."""

    def watch(self, *, timeout_seconds: float | None = None) -> dict[str, Any]:
        started = time.monotonic()
        while True:
            completed = self.scan_once()
            if completed == len(self.cases):
                base_inventory = capture_v4.finalize_capture(
                    self.contract, self.output_dir
                )
                return _write_v5_inventory(
                    output_dir=self.output_dir,
                    contract=self.contract,
                    base_inventory=base_inventory,
                )
            if (
                timeout_seconds is not None
                and time.monotonic() - started >= timeout_seconds
            ):
                raise CurveSidecarError(
                    f"Délai dépassé : {completed}/{len(self.cases)} cas capturés"
                )
            time.sleep(self.poll_seconds)


def _wait_for_cases(
    plan_dir: Path,
    run_dir: Path,
    *,
    timeout_seconds: float | None,
) -> tuple[ExpectedCase, ...]:
    started = time.monotonic()
    selection_path = run_dir.resolve() / "development_selection.json"
    while not selection_path.is_file():
        if (
            timeout_seconds is not None
            and time.monotonic() - started >= timeout_seconds
        ):
            raise CurveSidecarError("La sélection V5 n'est pas devenue disponible")
        time.sleep(1.0)
    return load_official_cases(plan_dir, run_dir)


def run_watcher(
    *,
    plan_dir: Path,
    run_dir: Path,
    output_dir: Path,
    poll_seconds: float,
    stability_seconds: float,
    timeout_seconds: float | None,
) -> dict[str, Any]:
    cases = _wait_for_cases(plan_dir, run_dir, timeout_seconds=timeout_seconds)
    contract = build_contract(
        plan_dir=plan_dir,
        run_dir=run_dir,
        output_dir=output_dir,
        cases=cases,
    )
    capture_v4.register_contract(output_dir, contract)
    registered = capture_v4._read_json(  # noqa: SLF001
        output_dir / "capture_contract.json"
    )
    validate_contract(registered)
    ready = _ready_payload(registered, output_dir=output_dir)
    ready_path = output_dir / "watcher_ready.json"
    if ready_path.exists():
        existing_ready = validate_ready(
            ready_path,
            expected_output_dir=output_dir,
        )
        old_pid = int(existing_ready["watcher_pid"])
        if existing_ready.get("contract_signature") != registered.get(
            "contract_signature"
        ):
            raise CurveSidecarError("L'accusé watcher vise un autre contrat V5")
        if old_pid != os.getpid() and _process_running(old_pid):
            raise CurveSidecarError("Un autre watcher V5 vivant possède la capture")
        if old_pid != os.getpid():
            capture_v4._atomic_write_json(ready_path, ready)  # noqa: SLF001
    else:
        capture_v4._atomic_write_json(ready_path, ready)  # noqa: SLF001
    watcher = V5CurveCaptureWatcher(
        contract=registered,
        output_dir=output_dir,
        poll_seconds=poll_seconds,
        stability_seconds=stability_seconds,
    )
    return watcher.watch(timeout_seconds=timeout_seconds)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    watch = sub.add_parser("watch")
    watch.add_argument("--plan-dir", type=Path, required=True)
    watch.add_argument("--run-dir", type=Path, required=True)
    watch.add_argument("--output-dir", type=Path, required=True)
    watch.add_argument("--poll-ms", type=float, default=DEFAULT_POLL_SECONDS * 1000)
    watch.add_argument(
        "--stability-ms", type=float, default=DEFAULT_STABILITY_SECONDS * 1000
    )
    watch.add_argument(
        "--timeout-seconds",
        type=float,
        default=0.0,
        help="0 = attente illimitée",
    )
    finalize = sub.add_parser("finalize")
    finalize.add_argument("--output-dir", type=Path, required=True)
    ready = sub.add_parser("validate-ready")
    ready.add_argument("--output-dir", type=Path, required=True)
    ready.add_argument("--watcher-pid", type=int)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.command == "watch":
        result = run_watcher(
            plan_dir=args.plan_dir,
            run_dir=args.run_dir,
            output_dir=args.output_dir,
            poll_seconds=args.poll_ms / 1000.0,
            stability_seconds=args.stability_ms / 1000.0,
            timeout_seconds=(args.timeout_seconds or None),
        )
    elif args.command == "finalize":
        contract = capture_v4._read_json(  # noqa: SLF001
            args.output_dir / "capture_contract.json"
        )
        contract = validate_contract(contract)
        base_inventory = capture_v4.finalize_capture(contract, args.output_dir)
        result = _write_v5_inventory(
            output_dir=args.output_dir.resolve(),
            contract=contract,
            base_inventory=base_inventory,
        )
    else:
        result = validate_ready(
            args.output_dir / "watcher_ready.json",
            expected_output_dir=args.output_dir,
            expected_watcher_pid=args.watcher_pid,
        )
    print(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
