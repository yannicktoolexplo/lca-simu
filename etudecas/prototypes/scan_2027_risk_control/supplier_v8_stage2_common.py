#!/usr/bin/env python3
"""Fail-closed contracts shared by the additive V8 delivery stage.

V8 keeps the accepted V7 operating-point validation and its 90 signed baseline
traces, but requires the native V8 30/30 exposure registry and result overlay
before any downstream lot, cascade, action, curve, registry, or HTML artifact is
created.  This module never starts the simulation engine and never writes into
the V7/V8 upstream evidence roots.
"""

from __future__ import annotations

import ast
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from etudecas.prototypes.scan_2027_risk_control import (
    build_validated_operating_points_v7 as bridge_v7,
)
from etudecas.prototypes.scan_2027_risk_control import (
    finalize_supplier_operating_point_full_campaign_v8 as finalizer_v8,
)
from etudecas.prototypes.scan_2027_risk_control import (
    supplier_fresh_development_holdout_protocol_v7 as protocol_v7,
)
from etudecas.prototypes.scan_2027_risk_control import (
    supplier_operating_point_full_campaign_v7_dashboard as dashboard_v7,
)
from etudecas.prototypes.scan_2027_risk_control import (
    supplier_operating_point_full_campaign_v8 as campaign_v8,
)
from etudecas.prototypes.scan_2027_risk_control import (
    supplier_physical_cascade_qualification_v5 as physical_v5,
)
from etudecas.prototypes.scan_2027_risk_control import (
    supplier_priority_action_replay_v4 as actions_v4,
)
from etudecas.prototypes.scan_2027_risk_control import (
    supplier_priority_lot_replay_v4 as lots_v4,
)
from etudecas.prototypes.scan_2027_risk_control import (
    supplier_v6_full_incident_lot_registry as registry_v6,
)
from etudecas.prototypes.scan_2027_risk_control import (
    supplier_v7_campaign_trace_package as traces_v7,
)
from etudecas.prototypes.scan_2027_risk_control import (
    supplier_v7_stage2_common as legacy,
)


SCHEMA_VERSION = "etudecas.supplier_v8_stage2.v1"
SOURCE_INVENTORY_SCHEMA_VERSION = f"{SCHEMA_VERSION}.source_inventory.v1"
UPSTREAM_SCHEMA_VERSION = f"{SCHEMA_VERSION}.upstream_validation.v1"
STAGE1_RECEIPT_NAME = "stage1_validation_v8.json"
EXPECTED_PROTOCOL_SHA256 = legacy.EXPECTED_PROTOCOL_SHA256
EXPECTED_STATES = legacy.EXPECTED_STATES
EXPECTED_MECHANISMS = legacy.EXPECTED_MECHANISMS
EXPECTED_VALIDATION_SEEDS = legacy.EXPECTED_VALIDATION_SEEDS
EXPECTED_VALIDATION_CASES = legacy.EXPECTED_VALIDATION_CASES
EXPECTED_CAMPAIGN_SEEDS = legacy.EXPECTED_CAMPAIGN_SEEDS
EXPECTED_BASELINES = legacy.EXPECTED_BASELINES
EXPECTED_INCIDENTS = legacy.EXPECTED_INCIDENTS
EXPECTED_CAMPAIGN_ROWS = legacy.EXPECTED_CAMPAIGN_ROWS
EXPECTED_LANES = legacy.EXPECTED_LANES
MAX_DETAILED_DOSSIERS = legacy.MAX_DETAILED_DOSSIERS
ALLOWED_ACTIONS = legacy.ALLOWED_ACTIONS
FORBIDDEN_INCIDENT_FLAGS = legacy.FORBIDDEN_INCIDENT_FLAGS
PACKAGE_PREFIX = legacy.PACKAGE_PREFIX
SHA256_RE = legacy.SHA256_RE

# The path layout deliberately retains v7_plan_dir/v7_run_dir: those two paths
# are the signed scientific authorization reused by V8, not V8 campaign outputs.
Stage2Paths = legacy.Stage2Paths
Stage2Error = legacy.Stage2Error
Stage2ScientificNoGo = legacy.Stage2ScientificNoGo
Stage2NotReady = legacy.Stage2NotReady

# Generic, already tested mechanics.  The error classes are aliases above, so
# their fail-closed exceptions remain part of the V8 public contract.
utc_now = legacy.utc_now
canonical_json_bytes = legacy.canonical_json_bytes
stable_sha256 = legacy.stable_sha256
sha256_file = legacy.sha256_file
signed = legacy.signed
verify_signature = legacy.verify_signature
read_json = legacy.read_json
atomic_write_json = legacy.atomic_write_json
publish_new_or_identical = legacy.publish_new_or_identical
paths_overlap = legacy.paths_overlap
exclusive_lock = legacy.exclusive_lock
finite_number = legacy.finite_number
_read_csv = legacy._read_csv
validate_observed_2025_pack = legacy.validate_observed_2025_pack


DIRECT_SOURCE_MODULES = (
    protocol_v7,
    traces_v7,
    bridge_v7,
    campaign_v8,
    finalizer_v8,
    dashboard_v7,
    lots_v4,
    physical_v5,
    actions_v4,
    registry_v6,
    legacy,
)


def _module_file(repo: Path, module_name: str) -> Path | None:
    if module_name != PACKAGE_PREFIX and not module_name.startswith(
        f"{PACKAGE_PREFIX}."
    ):
        return None
    base = (repo / Path(*module_name.split("."))).resolve()
    return next(
        (
            candidate
            for candidate in (base.with_suffix(".py"), base / "__init__.py")
            if candidate.is_file()
        ),
        None,
    )


def _imported_local_modules(path: Path, repo: Path) -> set[Path]:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8-sig"), filename=str(path))
    except (OSError, UnicodeDecodeError, SyntaxError) as exc:
        raise Stage2Error(f"Source Python illisible : {path}") from exc
    output: set[Path] = set()
    for node in ast.walk(tree):
        names: list[str] = []
        if isinstance(node, ast.Import):
            names.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level == 0 and node.module:
                names.append(node.module)
                names.extend(f"{node.module}.{alias.name}" for alias in node.names)
            elif node.level > 0:
                relative = path.resolve().relative_to(repo.resolve())
                package_parts = list(relative.parent.parts)
                ascend = node.level - 1
                if ascend > len(package_parts):
                    raise Stage2Error(f"Import relatif hors dépôt : {path}")
                base_parts = package_parts[: len(package_parts) - ascend]
                if node.module:
                    base_parts.extend(node.module.split("."))
                    names.append(".".join(base_parts))
                    names.extend(
                        ".".join([*base_parts, alias.name]) for alias in node.names
                    )
                else:
                    names.extend(
                        ".".join([*base_parts, alias.name]) for alias in node.names
                    )
        for name in names:
            candidate = _module_file(repo, name)
            if candidate is not None:
                output.add(candidate)
    return output


def _package_initializers(path: Path, repo: Path) -> set[Path]:
    output: set[Path] = set()
    parent = path.resolve().parent
    repo = repo.resolve()
    while parent != repo:
        if not parent.is_relative_to(repo):
            raise Stage2Error(f"Source hors dépôt : {path}")
        initializer = parent / "__init__.py"
        if initializer.is_file():
            output.add(initializer)
        parent = parent.parent
    return output


def _transitive_source_paths(roots: set[Path], repo: Path) -> list[Path]:
    repo = repo.resolve()
    pending = [path.resolve() for path in roots]
    discovered = set(pending)
    while pending:
        current = pending.pop()
        dependencies = _imported_local_modules(current, repo) | _package_initializers(
            current, repo
        )
        for dependency in dependencies:
            if dependency not in discovered:
                discovered.add(dependency)
                pending.append(dependency)
    return sorted(discovered, key=lambda path: path.relative_to(repo).as_posix())


def source_paths(repo: Path) -> list[Path]:
    """Inventory the V8 stage and every local dependency it can execute."""

    repo = repo.resolve()
    roots = {Path(module.__file__).resolve() for module in DIRECT_SOURCE_MODULES}
    stage2_directory = Path(__file__).resolve().parent
    roots.update(stage2_directory.glob("supplier_v8_stage2_*.py"))
    discovered = _transitive_source_paths(roots, repo)
    for path in discovered:
        if not path.is_file() or not path.is_relative_to(repo):
            raise Stage2Error(f"Source hors dépôt ou absente : {path}")
    return discovered


def build_source_inventory(repo: Path) -> dict[str, Any]:
    repo = repo.resolve()
    protocol_path = Path(protocol_v7.__file__).resolve()
    if sha256_file(protocol_path) != EXPECTED_PROTOCOL_SHA256:
        raise Stage2Error("Le protocole scientifique V7 accepté a changé")
    try:
        finalizer_v8.validate_frozen_implementation()
    except Exception as exc:
        raise Stage2Error(
            "Les dépendances figées de la finalisation V8 ont changé"
        ) from exc
    entries = [
        {
            "relative_path": path.relative_to(repo).as_posix(),
            "sha256": sha256_file(path),
            "size_bytes": path.stat().st_size,
        }
        for path in source_paths(repo)
    ]
    unsigned = {
        "schema_version": SOURCE_INVENTORY_SCHEMA_VERSION,
        "repo": str(repo),
        "entry_count": len(entries),
        "entries": entries,
        "critical_protocol_sha256": EXPECTED_PROTOCOL_SHA256,
        "v8_campaign_runner_sha256": sha256_file(Path(campaign_v8.__file__).resolve()),
        "v8_finalizer_sha256": sha256_file(Path(finalizer_v8.__file__).resolve()),
    }
    return signed(unsigned, "inventory_signature")


def verify_source_inventory(inventory: Mapping[str, Any]) -> None:
    verify_signature(inventory, "inventory_signature", "inventaire source étape 2 V8")
    repo = Path(str(inventory.get("repo") or "")).resolve()
    entries = inventory.get("entries")
    if (
        inventory.get("schema_version") != SOURCE_INVENTORY_SCHEMA_VERSION
        or not repo.is_dir()
        or not isinstance(entries, list)
        or len(entries) != int(inventory.get("entry_count") or -1)
        or inventory.get("critical_protocol_sha256") != EXPECTED_PROTOCOL_SHA256
        or inventory.get("v8_campaign_runner_sha256")
        != sha256_file(Path(campaign_v8.__file__).resolve())
        or inventory.get("v8_finalizer_sha256")
        != sha256_file(Path(finalizer_v8.__file__).resolve())
    ):
        raise Stage2Error("Inventaire source étape 2 V8 incomplet")
    seen: set[str] = set()
    for entry in entries:
        if not isinstance(entry, Mapping):
            raise Stage2Error("Entrée d'inventaire source V8 invalide")
        relative = str(entry.get("relative_path") or "")
        path = (repo / relative).resolve()
        if (
            not relative
            or relative in seen
            or not path.is_relative_to(repo)
            or not path.is_file()
            or path.stat().st_size != int(entry.get("size_bytes") or -1)
            or sha256_file(path) != str(entry.get("sha256") or "")
        ):
            raise Stage2Error(f"Source étape 2 V8 modifiée ou absente : {relative}")
        seen.add(relative)
    current = {path.relative_to(repo).as_posix() for path in source_paths(repo)}
    if current != seen:
        raise Stage2Error("Le périmètre transitif des sources étape 2 V8 a changé")


def _check_launch_completion(
    campaign_root: Path, manifest: Mapping[str, Any]
) -> dict[str, Any]:
    """Require the completed V8 launcher receipt; finalizer proves the case data."""

    root = campaign_root.resolve()
    progress_path = root / "launch_progress.json"
    contract_path = root / "launch_contract.json"
    progress = read_json(progress_path)
    contract = read_json(contract_path)
    verify_signature(contract, "launch_contract_signature", "contrat de lancement V8")
    completed_ids = progress.get("completed_shard_ids")
    if (
        progress.get("campaign_signature") != manifest.get("campaign_signature")
        or progress.get("launch_contract_signature")
        != contract.get("launch_contract_signature")
        or contract.get("campaign_signature") != manifest.get("campaign_signature")
        or progress.get("status") != "complete"
        or progress.get("target_discovery_status") != "complete"
        or int(progress.get("planned_shard_count") or -1) != EXPECTED_LANES
        or int(progress.get("completed_shard_count") or -1) != EXPECTED_LANES
        or int(progress.get("failed_shard_count", -1)) != 0
        or int(progress.get("active_shard_count", -1)) != 0
        or int(progress.get("queued_shard_count", -1)) != 0
        or not isinstance(completed_ids, list)
        or len(completed_ids) != EXPECTED_LANES
        or len(set(map(str, completed_ids))) != EXPECTED_LANES
    ):
        raise Stage2NotReady("Le lanceur V8 n'atteste pas encore les 18 blocs terminés")
    return {
        "progress": progress,
        "progress_path": str(progress_path),
        "progress_sha256": sha256_file(progress_path),
        "contract": contract,
        "contract_path": str(contract_path),
        "contract_sha256": sha256_file(contract_path),
    }


def probe_stage1(paths: Stage2Paths) -> str:
    """Return a waiting/accepted state or prove the signed V7 scientific rejection."""

    paths = paths.resolved()
    result_path = paths.v7_run_dir / "validation_result.json"
    if not result_path.is_file():
        return "waiting_v7_confirmation"
    result = read_json(result_path)
    verify_signature(result, "result_signature", "décision scientifique V7")
    if (
        result.get("accepted") is False
        or result.get("status") == protocol_v7.REJECTED_STATUS
    ):
        rebuilt = protocol_v7.validate_result(paths.v7_plan_dir, paths.v7_run_dir)
        if rebuilt.get("accepted") is not False:
            raise Stage2Error("Le statut de rejet V7 ne se reconstruit pas")
        raise Stage2ScientificNoGo(
            "Le triplet scientifique V7 a été rejeté; l'étape V8 ne produit rien"
        )
    required = (
        paths.trace_package_dir / "trace_package_manifest.json",
        paths.bridge_json,
        paths.campaign_root / "campaign_manifest.json",
        paths.campaign_root / "launch_contract.json",
        paths.campaign_root / "launch_progress.json",
        paths.results_dir / "campaign_validation.json",
        paths.results_dir / finalizer_v8.V8_RESULT_OVERLAY_NAME,
        paths.results_dir / "cross_state_target_registry.json",
        paths.results_dir / "state_validation_binding.json",
    )
    if not all(path.is_file() for path in required):
        return "waiting_campaign_v8_3330"
    manifest = read_json(paths.campaign_root / "campaign_manifest.json")
    try:
        _check_launch_completion(paths.campaign_root, manifest)
    except Stage2NotReady:
        return "waiting_campaign_v8_3330"
    return "accepted_stage1_complete"


def validate_complete_stage1(paths: Stage2Paths) -> dict[str, Any]:
    """Revalidate V7 authorization plus the native V8 30/30, 3,330-row result."""

    paths = paths.resolved()
    paths.validate_separation()
    result = protocol_v7.validate_result(paths.v7_plan_dir, paths.v7_run_dir)
    if (
        result.get("accepted") is not True
        or result.get("publishable") is not True
        or result.get("status") != protocol_v7.ACCEPTED_STATUS
        or int(result.get("validation_seed_count") or -1) != EXPECTED_VALIDATION_SEEDS
        or int(result.get("fresh_physical_evidence_case_count") or -1)
        != EXPECTED_VALIDATION_CASES
        or result.get("retuning_after_any_v7_result") is not False
    ):
        if result.get("accepted") is False:
            raise Stage2ScientificNoGo("La décision scientifique V7 est négative")
        raise Stage2Error("La décision scientifique V7 n'est pas publiable")

    trace_manifest = traces_v7.validate_package(
        paths.trace_package_dir,
        plan_dir=paths.v7_plan_dir,
        run_dir=paths.v7_run_dir,
    )
    bridge = bridge_v7.validate_bridge(paths.bridge_json, revalidate_source=True)
    overlay = finalizer_v8.validate_v8_overlay(paths.campaign_root, paths.results_dir)
    dashboard = dashboard_v7.load_dashboard_data(
        results_dir=paths.results_dir,
        target_registry_path=paths.results_dir / "cross_state_target_registry.json",
    )
    manifest = read_json(paths.campaign_root / "campaign_manifest.json")
    launch = _check_launch_completion(paths.campaign_root, manifest)
    counts = overlay.get("counts") or {}
    checks = overlay.get("v8_comparability_checks") or {}
    target = overlay.get("target_selection_v8") or {}
    if (
        trace_manifest.get("campaign_cohort", {}).get("seeds")
        != list(traces_v7.CAMPAIGN_SEEDS)
        or bridge.get("holdout_contract", {})
        .get("campaign_baseline_contract", {})
        .get("seeds")
        != list(traces_v7.CAMPAIGN_SEEDS)
        or int(counts.get("validation_seed_count") or -1) != EXPECTED_VALIDATION_SEEDS
        or int(counts.get("validation_case_count") or -1) != EXPECTED_VALIDATION_CASES
        or int(counts.get("campaign_seed_count") or -1) != EXPECTED_CAMPAIGN_SEEDS
        or int(counts.get("baseline_row_count") or -1) != EXPECTED_BASELINES
        or int(counts.get("incident_row_count") or -1) != EXPECTED_INCIDENTS
        or int(counts.get("campaign_row_count") or -1) != EXPECTED_CAMPAIGN_ROWS
        or checks.get("accepted_v7_confirmation_150_seeds_450_cases") is not True
        or checks.get("same_30_seeds_for_baseline_and_incidents") is not True
        or checks.get("all_18_lanes_comparable_on_all_30_seeds") is not True
        or checks.get("selection_uses_incident_outcomes") is not False
        or checks.get("selection_engine_run_count") != 0
        or checks.get("complete_3330_case_matrix_reconstructed") is not True
        or checks.get(
            "quality_capacity_availability_stock_or_state_risk_incident_count"
        )
        != 0
        or target.get("required_comparable_seed_count_per_lane")
        != EXPECTED_CAMPAIGN_SEEDS
        or target.get("same_lane_window_across_all_states_and_seeds") is not True
        or target.get("incident_outcomes_used") is not False
        or target.get("additional_simulation_engine_runs") != 0
        or manifest.get("target_exposure_comparability_status") != "accepted_30_of_30"
        or any(manifest.get(flag) is not False for flag in FORBIDDEN_INCIDENT_FLAGS)
        or int(dashboard.get("repetitions") or -1) != EXPECTED_CAMPAIGN_SEEDS
        or int(dashboard.get("laneCount") or -1) != EXPECTED_LANES
        or {row.get("id") for row in dashboard.get("states") or []}
        != set(EXPECTED_STATES)
        or {row.get("id") for row in dashboard.get("mechanisms") or []}
        != set(EXPECTED_MECHANISMS)
    ):
        raise Stage2Error(
            "L'étape 1 ne prouve pas la matrice V8 30/30, 90 + 3 240 attendue"
        )

    unsigned = {
        "schema_version": UPSTREAM_SCHEMA_VERSION,
        "status": "complete_validated_v8",
        "v7_result_signature": result["result_signature"],
        "trace_package_signature": trace_manifest["run_signature"],
        "bridge_signature": bridge["artifact_signature"],
        "campaign_signature": manifest["campaign_signature"],
        "result_overlay_signature": overlay["overlay_signature"],
        "launch_contract_signature": launch["contract"]["launch_contract_signature"],
        "launch_progress_sha256": launch["progress_sha256"],
        "counts": {
            "validation_seeds": EXPECTED_VALIDATION_SEEDS,
            "validation_cases": EXPECTED_VALIDATION_CASES,
            "campaign_seeds": EXPECTED_CAMPAIGN_SEEDS,
            "baseline_rows": EXPECTED_BASELINES,
            "incident_rows": EXPECTED_INCIDENTS,
            "campaign_rows": EXPECTED_CAMPAIGN_ROWS,
        },
        "target_selection_contract": {
            "revision": target.get("revision"),
            "source_trace_count": 90,
            "required_comparable_seed_count_per_lane": EXPECTED_CAMPAIGN_SEEDS,
            "lane_count": EXPECTED_LANES,
            "same_lane_window_across_all_states_and_seeds": True,
            "incident_outcomes_used": False,
            "engine_runs": 0,
            "historical_incident_probability_estimated": False,
        },
        "incident_contract": {
            "mechanisms": list(EXPECTED_MECHANISMS),
            "exogenous_generation": True,
            "consequences_depend_on_network_state": True,
            "historical_probability_estimated": False,
            "quality_incident_included": False,
            "capacity_or_availability_invented": False,
        },
    }
    return signed(unsigned, "validation_signature")


def validate_bound_stage1_receipt(
    paths: Stage2Paths, receipt_path: Path
) -> dict[str, Any]:
    receipt = read_json(receipt_path.resolve())
    verify_signature(receipt, "validation_signature", "reçu figé de l'étape 1 V8")
    if (
        receipt.get("schema_version") != UPSTREAM_SCHEMA_VERSION
        or receipt.get("status") != "complete_validated_v8"
    ):
        raise Stage2Error("Le reçu figé de l'étape 1 V8 est invalide")
    current = validate_complete_stage1(paths)
    if receipt != current:
        raise Stage2Error("Les preuves V8 ont changé après leur validation initiale")
    return receipt


@contextmanager
def v8_consumer_bindings() -> Iterator[None]:
    """Bind the frozen V4/V5/V6 readers to the genuine V8 campaign context."""

    previous_action_campaign = actions_v4.campaign_v4
    previous_registry_seed_ids = registry_v6.EXPECTED_SEED_IDS
    actions_v4.campaign_v4 = campaign_v8
    registry_v6.EXPECTED_SEED_IDS = tuple(traces_v7.CAMPAIGN_SEEDS)
    try:
        with finalizer_v8.patched_v8_context():
            yield
    finally:
        actions_v4.campaign_v4 = previous_action_campaign
        registry_v6.EXPECTED_SEED_IDS = previous_registry_seed_ids
