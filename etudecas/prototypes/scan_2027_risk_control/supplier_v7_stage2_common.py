#!/usr/bin/env python3
"""Shared fail-closed contracts for the additive V7 delivery stage.

This module never starts the simulation engine.  It validates the accepted V7
confirmation and the complete 3,330-row incident campaign, keeps every stage-2
output outside the upstream evidence, and records a signed transitive source
inventory for resumable execution.
"""

from __future__ import annotations

import ast
import csv
import hashlib
import json
import math
import os
import re
import tempfile
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from etudecas.prototypes.scan_2027_risk_control import (
    build_validated_operating_points_v7 as bridge_v7,
)
from etudecas.prototypes.scan_2027_risk_control import (
    continue_supplier_full_campaign_v7 as relay_v7,
)
from etudecas.prototypes.scan_2027_risk_control import (
    finalize_supplier_operating_point_full_campaign_v7 as finalizer_v7,
)
from etudecas.prototypes.scan_2027_risk_control import (
    supplier_fresh_development_holdout_protocol_v7 as protocol_v7,
)
from etudecas.prototypes.scan_2027_risk_control import (
    supplier_operating_point_full_campaign_v7 as campaign_v7,
)
from etudecas.prototypes.scan_2027_risk_control import (
    supplier_operating_point_full_campaign_v7_dashboard as dashboard_v7,
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


SCHEMA_VERSION = "etudecas.supplier_v7_stage2.v1"
SOURCE_INVENTORY_SCHEMA_VERSION = f"{SCHEMA_VERSION}.source_inventory.v1"
UPSTREAM_SCHEMA_VERSION = f"{SCHEMA_VERSION}.upstream_validation.v1"
STAGE1_RECEIPT_NAME = "stage1_validation.json"
EXPECTED_PROTOCOL_SHA256 = (
    "f11ba2523bd319e210e5d5d82a25beb1e88a2fc5bd17a181540f8662526a63e5"
)
EXPECTED_STATES = ("op_100", "op_93", "op_80")
EXPECTED_MECHANISMS = ("transport_delay", "planned_delivery_shortfall")
EXPECTED_VALIDATION_SEEDS = 150
EXPECTED_VALIDATION_CASES = 450
EXPECTED_CAMPAIGN_SEEDS = 30
EXPECTED_BASELINES = 90
EXPECTED_INCIDENTS = 3_240
EXPECTED_CAMPAIGN_ROWS = 3_330
EXPECTED_LANES = 18
MAX_DETAILED_DOSSIERS = 3
ALLOWED_ACTIONS = (
    actions_v4.ACTION_STOCK,
    actions_v4.ACTION_LEAD,
    actions_v4.ACTION_REALLOCATION,
)
FORBIDDEN_INCIDENT_FLAGS = (
    "quality_branch_included",
    "quality_incident_included",
    "availability_incident_included",
    "capacity_incident_included",
    "stock_incident_included",
    "supplier_state_dependent_risks_enabled",
)
PACKAGE_PREFIX = "etudecas"
SHA256_RE = re.compile(r"[0-9a-f]{64}")


class Stage2Error(RuntimeError):
    """A stage-2 source, input, result, or path violates its contract."""


class Stage2ScientificNoGo(Stage2Error):
    """The signed V7 scientific confirmation rejected the fixed triplet."""


class Stage2NotReady(Stage2Error):
    """The upstream V7 confirmation or 3,330-row campaign is not complete yet."""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def stable_sha256(value: Any) -> str:
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def signed(unsigned: Mapping[str, Any], field: str) -> dict[str, Any]:
    return {**unsigned, field: stable_sha256(unsigned)}


def verify_signature(payload: Mapping[str, Any], field: str, label: str) -> str:
    unsigned = dict(payload)
    signature = str(unsigned.pop(field, ""))
    if not SHA256_RE.fullmatch(signature) or signature != stable_sha256(unsigned):
        raise Stage2Error(f"Signature invalide : {label}")
    return signature


def read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise Stage2Error(f"JSON illisible : {path}") from exc
    if not isinstance(payload, dict):
        raise Stage2Error(f"Le JSON doit contenir un objet : {path}")
    return payload


def atomic_write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = (
        json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    ).encode("utf-8")
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.stage2-", dir=path.parent
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def publish_new_or_identical(path: Path, raw: bytes) -> None:
    """Publish immutable bytes once; an existing different file is an error."""

    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if not path.is_file() or path.read_bytes() != raw:
            raise Stage2Error(
                f"Sortie existante différente, écrasement refusé : {path}"
            )
        return
    temporary = path.with_name(
        f".{path.name}.stage2-{os.getpid()}-{os.urandom(8).hex()}"
    )
    try:
        with temporary.open("xb") as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        try:
            os.link(temporary, path)
        except FileExistsError:
            if not path.is_file() or path.read_bytes() != raw:
                raise Stage2Error(
                    f"Une écriture concurrente diffère, écrasement refusé : {path}"
                )
    finally:
        temporary.unlink(missing_ok=True)


def paths_overlap(left: Path, right: Path) -> bool:
    first = left.resolve()
    second = right.resolve()
    return first == second or first in second.parents or second in first.parents


@dataclass(frozen=True)
class Stage2Paths:
    repo: Path
    v7_plan_dir: Path
    v7_run_dir: Path
    trace_package_dir: Path
    bridge_json: Path
    campaign_root: Path
    results_dir: Path
    stage1_supervision_dir: Path
    observed_2025_dir: Path | None
    lot_replay_root: Path
    qualification_dir: Path
    action_replay_root: Path
    curves_dir: Path
    registry_dir: Path
    final_html: Path
    supervision_dir: Path

    def resolved(self) -> "Stage2Paths":
        return Stage2Paths(
            **{
                name: value.resolve() if value is not None else None
                for name, value in self.__dict__.items()
            }
        )

    def mapping(self) -> dict[str, str | None]:
        return {
            name: (str(value) if value is not None else None)
            for name, value in self.__dict__.items()
        }

    @property
    def upstream_paths(self) -> tuple[Path, ...]:
        return tuple(
            path
            for path in (
                self.repo,
                self.v7_plan_dir,
                self.v7_run_dir,
                self.trace_package_dir,
                self.bridge_json,
                self.campaign_root,
                self.results_dir,
                self.stage1_supervision_dir,
                self.observed_2025_dir,
            )
            if path is not None
        )

    @property
    def output_roots(self) -> tuple[Path, ...]:
        return (
            self.lot_replay_root,
            self.qualification_dir,
            self.action_replay_root,
            self.curves_dir,
            self.registry_dir,
            self.supervision_dir,
        )

    @property
    def output_files(self) -> tuple[Path, ...]:
        return (self.final_html, Path(str(self.final_html) + ".manifest.json"))

    def validate_separation(self) -> None:
        if not self.repo.is_dir():
            raise Stage2Error(f"Dépôt absent : {self.repo}")
        outputs = (*self.output_roots, *self.output_files)
        for index, output in enumerate(outputs):
            if any(paths_overlap(output, source) for source in self.upstream_paths):
                raise Stage2Error(
                    f"Une sortie étape 2 chevauche une source protégée : {output}"
                )
            if any(paths_overlap(output, other) for other in outputs[index + 1 :]):
                raise Stage2Error(
                    f"Les sorties étape 2 doivent être toutes séparées : {output}"
                )


DIRECT_SOURCE_MODULES = (
    protocol_v7,
    traces_v7,
    bridge_v7,
    campaign_v7,
    finalizer_v7,
    dashboard_v7,
    relay_v7,
    lots_v4,
    physical_v5,
    actions_v4,
    registry_v6,
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
    repo = repo.resolve()
    roots = {Path(module.__file__).resolve() for module in DIRECT_SOURCE_MODULES}
    stage2_directory = Path(__file__).resolve().parent
    roots.update(stage2_directory.glob("supplier_v7_stage2_*.py"))
    discovered = _transitive_source_paths(roots, repo)
    for path in discovered:
        if not path.is_file() or not path.is_relative_to(repo):
            raise Stage2Error(f"Source hors dépôt ou absente : {path}")
    return discovered


def build_source_inventory(repo: Path) -> dict[str, Any]:
    repo = repo.resolve()
    protocol_path = Path(protocol_v7.__file__).resolve()
    if sha256_file(protocol_path) != EXPECTED_PROTOCOL_SHA256:
        raise Stage2Error("Le protocole scientifique V7 figé a changé")
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
    }
    return signed(unsigned, "inventory_signature")


def verify_source_inventory(inventory: Mapping[str, Any]) -> None:
    verify_signature(inventory, "inventory_signature", "inventaire source étape 2")
    repo = Path(str(inventory.get("repo") or "")).resolve()
    entries = inventory.get("entries")
    if (
        inventory.get("schema_version") != SOURCE_INVENTORY_SCHEMA_VERSION
        or not repo.is_dir()
        or not isinstance(entries, list)
        or len(entries) != int(inventory.get("entry_count") or -1)
        or inventory.get("critical_protocol_sha256") != EXPECTED_PROTOCOL_SHA256
    ):
        raise Stage2Error("Inventaire source étape 2 incomplet")
    seen: set[str] = set()
    for entry in entries:
        if not isinstance(entry, Mapping):
            raise Stage2Error("Entrée d'inventaire source invalide")
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
            raise Stage2Error(f"Source étape 2 modifiée ou absente : {relative}")
        seen.add(relative)
    current = {path.relative_to(repo).as_posix() for path in source_paths(repo)}
    if current != seen:
        raise Stage2Error("Le périmètre transitif des sources étape 2 a changé")


def _check_upstream_supervision(path: Path) -> dict[str, Any]:
    status_path = path.resolve() / "status.json"
    status = read_json(status_path)
    verify_signature(status, "status_signature", "statut du relais étape 1")
    if status.get("status") != "complete_campaign_results_pending_delivery_stage":
        raise Stage2NotReady("La campagne 3 330 n'est pas déclarée terminée")
    progress = status.get("progress") or {}
    if (
        int(progress.get("validated_v7_cases") or -1) != EXPECTED_VALIDATION_CASES
        or int(progress.get("derived_baseline_traces") or -1) != EXPECTED_BASELINES
        or int(progress.get("campaign_rows") or -1) != EXPECTED_CAMPAIGN_ROWS
    ):
        raise Stage2Error(
            "Le statut final de l'étape 1 annonce des comptes incohérents"
        )
    return status


def probe_stage1(paths: Stage2Paths) -> str:
    """Return waiting/accepted or prove a signed scientific rejection."""

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
            "Le triplet V7 a été rejeté; l'étape 2 ne produit aucun livrable"
        )
    required = (
        paths.trace_package_dir / "trace_package_manifest.json",
        paths.bridge_json,
        paths.campaign_root / "campaign_manifest.json",
        paths.results_dir / "campaign_validation.json",
        paths.results_dir / finalizer_v7.V7_RESULT_OVERLAY_NAME,
        paths.stage1_supervision_dir / "status.json",
    )
    return (
        "accepted_stage1_complete"
        if all(path.is_file() for path in required)
        else "waiting_campaign_3330"
    )


def validate_complete_stage1(paths: Stage2Paths) -> dict[str, Any]:
    """Revalidate the accepted 450-case decision and complete 3,330-row output."""

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
    overlay = finalizer_v7.validate_v7_overlay(paths.campaign_root, paths.results_dir)
    dashboard = dashboard_v7.load_dashboard_data(
        results_dir=paths.results_dir,
        target_registry_path=paths.results_dir / "cross_state_target_registry.json",
    )
    stage1_status = _check_upstream_supervision(paths.stage1_supervision_dir)
    manifest = read_json(paths.campaign_root / "campaign_manifest.json")
    counts = overlay.get("counts") or {}
    checks = overlay.get("v7_comparability_checks") or {}
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
        or checks.get("all_3330_metrics_reconstructed_from_signed_case_evidence")
        is not True
        or checks.get("campaign_subset_used_as_v7_acceptance_gate") is not False
        or any(manifest.get(flag) is not False for flag in FORBIDDEN_INCIDENT_FLAGS)
        or int(dashboard.get("repetitions") or -1) != EXPECTED_CAMPAIGN_SEEDS
        or int(dashboard.get("laneCount") or -1) != EXPECTED_LANES
        or {row.get("id") for row in dashboard.get("states") or []}
        != set(EXPECTED_STATES)
        or {row.get("id") for row in dashboard.get("mechanisms") or []}
        != set(EXPECTED_MECHANISMS)
    ):
        raise Stage2Error("L'étape 1 ne prouve pas la matrice V7 90 + 3 240 attendue")
    unsigned = {
        "schema_version": UPSTREAM_SCHEMA_VERSION,
        "status": "complete_validated",
        "v7_result_signature": result["result_signature"],
        "trace_package_signature": trace_manifest["run_signature"],
        "bridge_signature": bridge["artifact_signature"],
        "campaign_signature": manifest["campaign_signature"],
        "result_overlay_signature": overlay["overlay_signature"],
        "stage1_status_signature": stage1_status["status_signature"],
        "counts": {
            "validation_seeds": EXPECTED_VALIDATION_SEEDS,
            "validation_cases": EXPECTED_VALIDATION_CASES,
            "campaign_seeds": EXPECTED_CAMPAIGN_SEEDS,
            "baseline_rows": EXPECTED_BASELINES,
            "incident_rows": EXPECTED_INCIDENTS,
            "campaign_rows": EXPECTED_CAMPAIGN_ROWS,
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
    """Revalidate stage 1 and require byte-equivalent signed provenance.

    The receipt is published once by the stage-2 pipeline immediately after its
    first complete upstream validation.  Recomputing the upstream proof before
    every later stage closes the gap where a different, internally coherent
    stage-1 package could otherwise be substituted during the same execution.
    """

    receipt_path = receipt_path.resolve()
    receipt = read_json(receipt_path)
    verify_signature(receipt, "validation_signature", "reçu figé de l'étape 1")
    if (
        receipt.get("schema_version") != UPSTREAM_SCHEMA_VERSION
        or receipt.get("status") != "complete_validated"
    ):
        raise Stage2Error("Le reçu figé de l'étape 1 est invalide")
    current = validate_complete_stage1(paths)
    if receipt != current:
        raise Stage2Error(
            "Les preuves de l'étape 1 ont changé après leur validation initiale"
        )
    return receipt


@contextmanager
def v7_consumer_bindings() -> Iterator[None]:
    """Temporarily bind frozen V4/V5/V6 readers to the 30 V7 campaign seeds."""

    previous_action_campaign = actions_v4.campaign_v4
    previous_registry_seed_ids = registry_v6.EXPECTED_SEED_IDS
    actions_v4.campaign_v4 = campaign_v7
    registry_v6.EXPECTED_SEED_IDS = tuple(traces_v7.CAMPAIGN_SEEDS)
    try:
        with finalizer_v7.patched_v7_context():
            yield
    finally:
        actions_v4.campaign_v4 = previous_action_campaign
        registry_v6.EXPECTED_SEED_IDS = previous_registry_seed_ids


@contextmanager
def exclusive_lock(path: Path) -> Iterator[None]:
    """Hold a process lock that is automatically released after a crash."""

    path.parent.mkdir(parents=True, exist_ok=True)
    stream = path.open("a+b")
    acquired = False
    try:
        if stream.tell() == 0:
            stream.write(b"0")
            stream.flush()
        stream.seek(0)
        try:
            if os.name == "nt":
                import msvcrt

                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
            else:  # pragma: no cover
                import fcntl

                fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            acquired = True
        except OSError as exc:
            raise Stage2Error("Un watcher étape 2 détient déjà le verrou") from exc
        yield
    finally:
        try:
            if acquired:
                stream.seek(0)
                if os.name == "nt":
                    import msvcrt

                    msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
                else:  # pragma: no cover
                    import fcntl

                    fcntl.flock(stream.fileno(), fcntl.LOCK_UN)
        finally:
            stream.close()


def finite_number(value: Any, *, label: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise Stage2Error(f"Valeur numérique invalide : {label}") from exc
    if not math.isfinite(number):
        raise Stage2Error(f"Valeur non finie : {label}")
    return number


def _read_csv(path: Path) -> list[dict[str, str]]:
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as stream:
            return [dict(row) for row in csv.DictReader(stream)]
    except (OSError, UnicodeDecodeError, csv.Error) as exc:
        raise Stage2Error(f"CSV illisible : {path}") from exc


def validate_observed_2025_pack(path: Path | None) -> dict[str, Any] | None:
    """Load only signed observed CA and accounting-stock context, without causality."""

    if path is None:
        return None
    root = path.resolve()
    manifest_path = root / "manifest.json"
    manifest = read_json(manifest_path)
    files = manifest.get("files")
    if (
        manifest.get("schema_version")
        != "etudecas.observed_2025_supply_bilan.manifest.v1"
        or manifest.get("all_validation_checks_pass") is not True
        or not isinstance(files, list)
    ):
        raise Stage2Error("Le paquet observé 2025 n'est pas validé")
    declared: dict[str, dict[str, Any]] = {}
    for row in files:
        if not isinstance(row, Mapping):
            raise Stage2Error("Inventaire du paquet observé 2025 invalide")
        name = str(row.get("name") or "")
        candidate = (root / name).resolve()
        if (
            not name
            or name in declared
            or not candidate.is_relative_to(root)
            or not candidate.is_file()
            or candidate.stat().st_size != int(row.get("size_bytes") or -1)
            or sha256_file(candidate) != str(row.get("sha256") or "")
        ):
            raise Stage2Error(f"Fichier observé 2025 modifié : {name}")
        declared[name] = dict(row)
    required = {
        "bilan_observed_2025.json",
        "observed_ca_product_summary_2025.csv",
        "observed_stock_value_summary_2025.csv",
        "validation_checks.csv",
    }
    if not required.issubset(declared):
        raise Stage2Error(
            "Le paquet observé 2025 ne contient pas les synthèses requises"
        )
    checks = _read_csv(root / "validation_checks.csv")
    if not checks or any(
        str(row.get("status") or "").strip() != "PASS" for row in checks
    ):
        raise Stage2Error("Un contrôle du paquet observé 2025 est en échec")
    bilan = read_json(root / "bilan_observed_2025.json")
    if (
        bilan.get("schema_version") != "etudecas.observed_2025_supply_bilan.v1"
        or bilan.get("currency_status")
        != "not_declared_in_source; EUR_is_working_convention"
        or bilan.get("supplier_attribution_status")
        != "not_supported_by_available_observed_files"
        or bilan.get("component_stock_product_mapping_status")
        != "unresolved_conflicting_hypotheses"
    ):
        raise Stage2Error("Les limites métiers du paquet observé 2025 ont changé")
    ca_rows = _read_csv(root / "observed_ca_product_summary_2025.csv")
    stock_rows = _read_csv(root / "observed_stock_value_summary_2025.csv")
    products = []
    for row in ca_rows:
        product = str(row.get("product_code") or "")
        if product not in {"268091", "268967"}:
            continue
        products.append(
            {
                "product_id": product,
                "lost_revenue_raw_source_value": finite_number(
                    row.get("ca_lost_raw_source_value"), label=f"CA perdu {product}"
                ),
                "lost_share_of_raw_potential_pct": 100.0
                * finite_number(
                    row.get("lost_share_of_raw_potential"),
                    label=f"part CA perdu {product}",
                ),
                "delivered_revenue_source_value": finite_number(
                    row.get("ca_delivered_source_value"),
                    label=f"CA livré {product}",
                ),
                "negative_adjustments_source_value": finite_number(
                    row.get("ca_lost_negative_adjustments_source_value"),
                    label=f"ajustements négatifs {product}",
                ),
                "unit_note": str(row.get("unit_note") or ""),
                "interpretation_limit": str(row.get("interpretation_limit") or ""),
            }
        )
    if {row["product_id"] for row in products} != {"268091", "268967"}:
        raise Stage2Error("Les deux produits attendus manquent au contexte CA observé")
    stocks = [
        {
            "series_id": str(row.get("series_id") or ""),
            "scope": str(row.get("stock_scope") or ""),
            "product_id": str(row.get("product_code") or ""),
            "source_family_label": str(row.get("source_family_label") or ""),
            "mean_accounting_value_source": finite_number(
                row.get("mean_stock_value_source"),
                label=f"stock moyen {row.get('series_id')}",
            ),
            "last_accounting_value_source": finite_number(
                row.get("last_stock_value_source"),
                label=f"stock final {row.get('series_id')}",
            ),
            "physical_quantity_available": str(
                row.get("physical_quantity_available") or ""
            )
            .strip()
            .casefold()
            in {"true", "1", "yes"},
            "unit_note": str(row.get("unit_note") or ""),
            "interpretation_limit": str(row.get("interpretation_limit") or ""),
        }
        for row in stock_rows
    ]
    if not stocks or any(row["physical_quantity_available"] for row in stocks):
        raise Stage2Error("Le contexte stock observé doit rester une valeur comptable")
    if any(
        row["series_id"] in {"component_stock_cos", "component_stock_pharma"}
        and row["product_id"]
        for row in stocks
    ):
        raise Stage2Error("Cos/Pharma ne doivent être associés à aucun produit")
    for product in products:
        denominator = (
            product["delivered_revenue_source_value"]
            + product["lost_revenue_raw_source_value"]
        )
        if denominator <= 0.0 or not math.isclose(
            product["lost_share_of_raw_potential_pct"],
            100.0 * product["lost_revenue_raw_source_value"] / denominator,
            rel_tol=1e-12,
            abs_tol=1e-12,
        ):
            raise Stage2Error("Le taux financier descriptif observé est incohérent")
    if (
        any("devise absente" not in row["unit_note"] for row in products + stocks)
        or any(not row["interpretation_limit"] for row in products + stocks)
        or ca_rows != list(bilan.get("ca_summary") or [])
        or stock_rows != list(bilan.get("stock_summary") or [])
    ):
        # CSV values are strings while JSON values are typed; compare their stable
        # business identities below instead of silently accepting missing limits.
        json_ca_ids = {
            str(row.get("product_code") or "") for row in bilan.get("ca_summary") or []
        }
        json_stock_ids = {
            str(row.get("series_id") or "") for row in bilan.get("stock_summary") or []
        }
        if (
            json_ca_ids != {str(row.get("product_code") or "") for row in ca_rows}
            or json_stock_ids != {str(row.get("series_id") or "") for row in stock_rows}
            or any(
                "devise absente" not in row["unit_note"] for row in products + stocks
            )
            or any(not row["interpretation_limit"] for row in products + stocks)
        ):
            raise Stage2Error(
                "Les synthèses observées ne correspondent pas au bilan signé"
            )
    return {
        "status": "observed_2025_context_validated",
        "manifest": str(manifest_path),
        "manifest_sha256": sha256_file(manifest_path),
        "products": sorted(products, key=lambda row: row["product_id"]),
        "stocks": stocks,
        "currency_status": bilan["currency_status"],
        "currency_display_fr": "devise non renseignée; EUR est seulement une convention de travail",
        "component_stock_product_mapping_status": bilan[
            "component_stock_product_mapping_status"
        ],
        "supplier_attribution_status": bilan["supplier_attribution_status"],
        "supplier_causality_available": False,
        "purchase_order_causality_available": False,
        "lot_causality_available": False,
        "historical_supplier_incident_probability_available": False,
        "calibration_next_data": "PO promis/reçu réels, quantité, date, fournisseur et cause",
    }
