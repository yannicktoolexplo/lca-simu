#!/usr/bin/env python3
"""Run one bounded V8 tranche, then publish one state checkpoint.

The default mode is a read-only preflight.  ``--execute`` is the sole switch
that authorises the existing bounded runner to start one or two explicit
shards.  Only after those shards have finished and their signed evidence has
been revalidated may this module build and validate a 10/20/30 checkpoint for
one operating state in a new directory outside the campaign.

This module does not enable, create or edit scheduled tasks.  It never invokes
cross-state consolidation, lot replay, Stage 2 or Stage 3.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from etudecas.prototypes.scan_2027_risk_control import (
    resume_supplier_operating_point_full_campaign_v8_bounded as bounded,
)
from etudecas.prototypes.scan_2027_risk_control import (
    supplier_v8_state_checkpoint as checkpoint,
)


SCHEMA_VERSION = "etudecas.supplier_v8.bounded_tranche_checkpoint.v1"


class TrancheOrchestrationError(RuntimeError):
    """Raised when the requested tranche cannot be proved safe and coherent."""


@dataclass(frozen=True)
class TrancheRequest:
    campaign_root: Path
    runner: Path
    output_dir: Path
    config: checkpoint.CheckpointConfig
    shard_ids: tuple[str, ...]
    reuse_evidence_dirs: tuple[Path, ...]
    poll_seconds: float


ProcessScanner = bounded.ProcessScanner
TaskScanner = bounded.TaskScanner
BoundedInspector = Callable[..., dict[str, Any]]
BoundedExecutor = Callable[..., dict[str, Any]]
CheckpointReadiness = Callable[..., dict[str, Any]]
CheckpointBuilder = Callable[..., dict[str, Any]]
CheckpointValidator = Callable[..., Mapping[str, Any]]


def _is_within(path: Path, root: Path) -> bool:
    return path == root or path.is_relative_to(root)


def _validate_new_output_destination(
    *, campaign_root: Path, output_dir: Path
) -> Path:
    """Validate a destination without creating it or any parent directory."""

    source = campaign_root.resolve(strict=False)
    destination = output_dir.resolve(strict=False)
    protected = checkpoint.PROTECTED_LEGACY_OUTPUT.resolve(strict=False)
    if destination.exists():
        raise TrancheOrchestrationError(
            "Le dossier de bilan doit être nouveau; la destination existe déjà : "
            + str(destination)
        )
    if _is_within(destination, source):
        raise TrancheOrchestrationError(
            "Le dossier de bilan doit rester extérieur à la campagne source."
        )
    if _is_within(destination, protected):
        raise TrancheOrchestrationError(
            "Le bilan historique 10/30 est protégé; choisir un nouveau dossier."
        )
    return destination


def make_request(
    *,
    campaign_root: Path,
    runner: Path,
    output_dir: Path,
    operating_point_id: str,
    simulation_count: int,
    shard_ids: Sequence[str],
    reuse_evidence_dirs: Sequence[Path] = (),
    expected_campaign_signature: str = bounded.EXPECTED_CAMPAIGN_SIGNATURE,
    poll_seconds: float = bounded.DEFAULT_POLL_SECONDS,
) -> TrancheRequest:
    """Bind one explicit shard suffix to exactly one cumulative checkpoint."""

    if expected_campaign_signature != checkpoint.EXPECTED_CAMPAIGN_SIGNATURE:
        raise TrancheOrchestrationError(
            "Les contrats du lanceur borné et du bilan ne désignent pas la même "
            "campagne."
        )
    config = checkpoint.make_config(
        operating_point_id,
        simulation_count,
        expected_campaign_signature=expected_campaign_signature,
    )
    selected = tuple(str(value) for value in shard_ids)
    if not 1 <= len(selected) <= bounded.MAX_SELECTED_SHARDS:
        raise TrancheOrchestrationError(
            "Une tranche doit contenir exactement un ou deux blocs explicites."
        )
    if len(set(selected)) != len(selected):
        raise TrancheOrchestrationError(
            "Un bloc ne peut pas être demandé deux fois."
        )
    expected_suffix = config.target_shards[-len(selected) :]
    if selected != expected_suffix:
        raise TrancheOrchestrationError(
            "Les blocs doivent être le suffixe ordonné qui ferme le jalon "
            f"{simulation_count}/30 de {operating_point_id} : "
            + ", ".join(expected_suffix)
        )
    if not 0.0 <= poll_seconds <= 60.0:
        raise TrancheOrchestrationError(
            "Le délai de contrôle doit être compris entre 0 et 60 secondes."
        )
    destination = _validate_new_output_destination(
        campaign_root=campaign_root, output_dir=output_dir
    )
    return TrancheRequest(
        campaign_root=campaign_root.resolve(strict=False),
        runner=runner.resolve(strict=False),
        output_dir=destination,
        config=config,
        shard_ids=selected,
        reuse_evidence_dirs=tuple(
            path.resolve(strict=False) for path in reuse_evidence_dirs
        ),
        poll_seconds=poll_seconds,
    )


def _completion_states_for_checkpoint(
    request: TrancheRequest,
) -> dict[str, str]:
    """Read the signed campaign plan and classify every checkpoint shard."""

    with bounded.launcher_v8.patched_v8_context():
        manifest, shards = bounded.implementation.load_campaign_plan(
            request.campaign_root, request.runner
        )
        signature = str(manifest.get("campaign_signature") or "")
        if signature != request.config.expected_campaign_signature:
            raise TrancheOrchestrationError(
                "La signature de campagne ne correspond pas au jalon demandé."
            )
        by_id = {str(shard.shard_id): shard for shard in shards}
        if len(by_id) != len(shards):
            raise TrancheOrchestrationError(
                "Le plan signé contient des identifiants de bloc dupliqués."
            )
        missing = [
            shard_id
            for shard_id in request.config.target_shards
            if shard_id not in by_id
        ]
        if missing:
            raise TrancheOrchestrationError(
                "Bloc du jalon absent du plan signé : " + ", ".join(missing)
            )
        states: dict[str, str] = {}
        for shard_id in request.config.target_shards:
            state, detail = bounded.implementation._completion_state(  # noqa: SLF001
                request.campaign_root,
                campaign_signature=signature,
                shard=by_id[shard_id],
            )
            if state in {"active", "invalid"}:
                raise TrancheOrchestrationError(
                    f"Bloc non exploitable {shard_id} ({state}) : {detail}"
                )
            states[shard_id] = state
    selected = set(request.shard_ids)
    incomplete_prerequisites = [
        shard_id
        for shard_id, state in states.items()
        if shard_id not in selected and state != "complete"
    ]
    if incomplete_prerequisites:
        raise TrancheOrchestrationError(
            "Un bloc antérieur hors tranche est incomplet; aucun calcul ne sera "
            "lancé : "
            + ", ".join(incomplete_prerequisites)
        )
    unsupported_selected = [
        shard_id
        for shard_id in request.shard_ids
        if states[shard_id] not in {"complete", "missing", "resumable"}
    ]
    if unsupported_selected:
        raise TrancheOrchestrationError(
            "État non reprenable pour : " + ", ".join(unsupported_selected)
        )
    return states


def _assert_same_selected_states(
    *,
    bounded_payload: Mapping[str, Any],
    states: Mapping[str, str],
    request: TrancheRequest,
) -> None:
    reported = {
        str(row.get("shard_id")): str(row.get("state"))
        for row in bounded_payload.get("selected_states", ())
        if isinstance(row, Mapping)
    }
    expected = {shard_id: states[shard_id] for shard_id in request.shard_ids}
    if reported != expected:
        raise TrancheOrchestrationError(
            "L'état des blocs a changé pendant le contrôle; relancer le contrôle."
        )


def _checkpoint_preflight_is_coherent(
    *, readiness: Mapping[str, Any], states: Mapping[str, str], request: TrancheRequest
) -> None:
    selected_incomplete = any(
        states[shard_id] != "complete" for shard_id in request.shard_ids
    )
    ready = readiness.get("ready") is True
    status = str(readiness.get("status") or "")
    if status in {"running_target_shards", "activity_race_detected"}:
        raise TrancheOrchestrationError(
            "Une activité concurrente a été détectée pendant le contrôle du jalon."
        )
    if selected_incomplete and ready:
        raise TrancheOrchestrationError(
            "Le jalon est déclaré prêt alors qu'un bloc de la tranche est incomplet."
        )
    if not selected_incomplete and not ready:
        raise TrancheOrchestrationError(
            "Tous les blocs sont terminés mais le bilan reste invalide : "
            + str(readiness.get("message_fr") or status)
        )


def inspect_tranche(
    request: TrancheRequest,
    *,
    scanner: ProcessScanner = bounded.scan_processes,
    task_scanner: TaskScanner = bounded.scan_v8_scheduled_tasks,
    bounded_inspector: BoundedInspector = bounded.inspect_bounded_resume,
    checkpoint_readiness: CheckpointReadiness = checkpoint.evaluate_readiness,
) -> dict[str, Any]:
    """Perform a read-only tranche and checkpoint preflight."""

    _validate_new_output_destination(
        campaign_root=request.campaign_root, output_dir=request.output_dir
    )
    bounded_payload = bounded_inspector(
        campaign_root=request.campaign_root,
        runner=request.runner,
        requested_ids=request.shard_ids,
        reuse_evidence_dirs=request.reuse_evidence_dirs,
        expected_campaign_signature=request.config.expected_campaign_signature,
        scanner=scanner,
        task_scanner=task_scanner,
    )
    states = _completion_states_for_checkpoint(request)
    _assert_same_selected_states(
        bounded_payload=bounded_payload, states=states, request=request
    )
    readiness = checkpoint_readiness(
        request.campaign_root,
        config=request.config,
        scanner=scanner,
    )
    _checkpoint_preflight_is_coherent(
        readiness=readiness, states=states, request=request
    )
    incomplete = [
        shard_id
        for shard_id in request.shard_ids
        if states[shard_id] != "complete"
    ]
    return {
        "schema_version": SCHEMA_VERSION,
        "status": (
            "ready_for_explicit_execution"
            if incomplete
            else "ready_for_explicit_checkpoint_publication"
        ),
        "mode": "validate_only",
        "campaign_root": str(request.campaign_root),
        "campaign_signature": request.config.expected_campaign_signature,
        "operating_point_id": request.config.operating_point_id,
        "simulation_count": request.config.simulation_count,
        "selected_shard_ids": list(request.shard_ids),
        "selected_states": [
            {"shard_id": shard_id, "state": states[shard_id]}
            for shard_id in request.shard_ids
        ],
        "would_launch_shard_ids": incomplete,
        "checkpoint_output_dir": str(request.output_dir),
        "checkpoint_readiness_before_execution": dict(readiness),
        "bounded_resume_preflight": bounded_payload,
        "filesystem_mutation_performed": False,
        "engine_runs_started": 0,
        "explicit_execute_required": True,
        "scheduled_tasks_modified": False,
        "downstream_steps_started": False,
    }


def execute_tranche(
    request: TrancheRequest,
    *,
    scanner: ProcessScanner = bounded.scan_processes,
    task_scanner: TaskScanner = bounded.scan_v8_scheduled_tasks,
    bounded_inspector: BoundedInspector = bounded.inspect_bounded_resume,
    bounded_executor: BoundedExecutor = bounded.execute_bounded_resume,
    checkpoint_readiness: CheckpointReadiness = checkpoint.evaluate_readiness,
    checkpoint_builder: CheckpointBuilder = checkpoint.build_checkpoint,
    checkpoint_validator: CheckpointValidator = checkpoint.validate_package,
) -> dict[str, Any]:
    """Execute only the tranche, then build and validate its one-state checkpoint."""

    preflight = inspect_tranche(
        request,
        scanner=scanner,
        task_scanner=task_scanner,
        bounded_inspector=bounded_inspector,
        checkpoint_readiness=checkpoint_readiness,
    )
    bounded_result = bounded_executor(
        campaign_root=request.campaign_root,
        runner=request.runner,
        requested_ids=request.shard_ids,
        reuse_evidence_dirs=request.reuse_evidence_dirs,
        expected_campaign_signature=request.config.expected_campaign_signature,
        poll_seconds=request.poll_seconds,
        scanner=scanner,
        task_scanner=task_scanner,
    )
    if bounded_result.get("status") != "complete_selected_shards":
        raise TrancheOrchestrationError(
            "La tranche n'est pas terminée; aucun bilan n'a été construit."
        )
    readiness = checkpoint_readiness(
        request.campaign_root,
        config=request.config,
        scanner=scanner,
    )
    if readiness.get("ready") is not True:
        raise TrancheOrchestrationError(
            "La preuve du jalon reste incomplète après la tranche; aucun bilan "
            "n'a été construit : "
            + str(readiness.get("message_fr") or readiness.get("status") or "")
        )
    _validate_new_output_destination(
        campaign_root=request.campaign_root, output_dir=request.output_dir
    )
    build_result = checkpoint_builder(
        campaign_root=request.campaign_root,
        output_dir=request.output_dir,
        config=request.config,
        scanner=scanner,
    )
    manifest = dict(
        checkpoint_validator(request.output_dir, config=request.config)
    )
    package_signature = str(manifest.get("package_signature") or "")
    if not package_signature or package_signature != str(
        build_result.get("package_signature") or ""
    ):
        raise TrancheOrchestrationError(
            "La signature du bilan construit ne correspond pas à sa validation."
        )
    entrypoint = Path(str(build_result.get("entrypoint") or ""))
    if not entrypoint.is_file() or entrypoint.parent.resolve() != request.output_dir:
        raise TrancheOrchestrationError(
            "Le point d'entrée HTML validé du nouveau bilan est absent."
        )
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "checkpoint_created_and_validated",
        "mode": "execute",
        "campaign_root": str(request.campaign_root),
        "campaign_signature": request.config.expected_campaign_signature,
        "operating_point_id": request.config.operating_point_id,
        "simulation_count": request.config.simulation_count,
        "selected_shard_ids": list(request.shard_ids),
        "bounded_resume": bounded_result,
        "checkpoint_readiness_after_execution": readiness,
        "checkpoint": build_result,
        "checkpoint_output_dir": str(request.output_dir),
        "entrypoint": str(entrypoint.resolve()),
        "package_signature": package_signature,
        "scheduled_tasks_modified": False,
        "downstream_steps_started": False,
        "preflight_status": preflight["status"],
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--campaign-root", type=Path, default=bounded.DEFAULT_CAMPAIGN_ROOT
    )
    parser.add_argument("--runner", type=Path, default=bounded.RUNNER)
    parser.add_argument("--checkpoint-output-dir", type=Path, required=True)
    parser.add_argument(
        "--operating-point-id", choices=checkpoint.OPERATING_POINTS, required=True
    )
    parser.add_argument(
        "--simulation-count",
        type=int,
        choices=checkpoint.SIMULATION_COUNTS,
        required=True,
    )
    parser.add_argument("--shard-id", action="append", required=True)
    parser.add_argument("--reuse-evidence-dir", type=Path, action="append", default=[])
    parser.add_argument(
        "--expected-campaign-signature",
        default=bounded.EXPECTED_CAMPAIGN_SIGNATURE,
    )
    parser.add_argument(
        "--poll-seconds", type=float, default=bounded.DEFAULT_POLL_SECONDS
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help=(
            "Autorise explicitement le calcul des seuls blocs demandés, puis la "
            "création du nouveau bilan. Sans ce drapeau, aucun fichier n'est écrit."
        ),
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        request = make_request(
            campaign_root=args.campaign_root,
            runner=args.runner,
            output_dir=args.checkpoint_output_dir,
            operating_point_id=args.operating_point_id,
            simulation_count=args.simulation_count,
            shard_ids=args.shard_id,
            reuse_evidence_dirs=args.reuse_evidence_dir,
            expected_campaign_signature=args.expected_campaign_signature,
            poll_seconds=args.poll_seconds,
        )
        if args.execute:
            result = execute_tranche(request)
        else:
            result = inspect_tranche(request)
    except (
        TrancheOrchestrationError,
        bounded.BoundedResumeError,
        checkpoint.StateCheckpointError,
        FileNotFoundError,
        OSError,
        ValueError,
    ) as exc:
        print(
            json.dumps(
                {
                    "schema_version": SCHEMA_VERSION,
                    "status": "refused",
                    "mode": "execute" if args.execute else "validate_only",
                    "error": f"{type(exc).__name__}: {exc}",
                },
                ensure_ascii=False,
                indent=2,
            ),
            flush=True,
        )
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
