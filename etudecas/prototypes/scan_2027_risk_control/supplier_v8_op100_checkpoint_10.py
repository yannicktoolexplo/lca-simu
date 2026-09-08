#!/usr/bin/env python3
"""Build a safe, descriptive 10/30 checkpoint from two completed V8 shards.

The adapter is deliberately separate from the frozen campaign and Stage3
sources.  It never starts the simulation engine.  While either target shard
or one of its child processes is active, readiness consults the process table
only and refuses to inspect campaign files.  Once both shards are inactive,
all shard files are read with delete sharing enabled on Windows.

The resulting package is a provisional view of the reference operating state.
It contains descriptive statistics only; it cannot support a final supplier
classification or any comparison between operating states.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import html
import io
import json
import math
import os
import re
import shutil
import tempfile
from collections.abc import Callable, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Iterator

import numpy as np
import pandas as pd

from etudecas.prototypes.scan_2027_risk_control import (
    finalize_supplier_operating_point_full_campaign_v4 as finalizer_v4,
)
from etudecas.prototypes.scan_2027_risk_control import (
    finalize_supplier_operating_point_full_campaign_v8 as finalizer_v8,
)
from etudecas.prototypes.scan_2027_risk_control import (
    supervise_supplier_operating_point_full_campaign_v8_v2 as supervisor,
)
from etudecas.prototypes.scan_2027_risk_control import (
    supplier_operating_point_full_campaign_v4 as campaign_v4,
)
from etudecas.prototypes.scan_2027_risk_control import (
    supplier_operating_point_full_campaign_v8 as campaign_v8,
)
from etudecas.prototypes.scan_2027_risk_control import (
    supplier_v7_campaign_trace_package as trace_package,
)
from etudecas.prototypes.scan_2027_risk_control import (
    supplier_v8_stage3_common as shared_io,
)

SCHEMA_VERSION = "etudecas.supplier_v8.reference_checkpoint_10.v1"
PACKAGE_SCHEMA_VERSION = f"{SCHEMA_VERSION}.package.v1"
RESULT_SCHEMA_VERSION = f"{SCHEMA_VERSION}.result.v1"
EVIDENCE_INDEX_SCHEMA_VERSION = f"{SCHEMA_VERSION}.evidence_index.v1"

TARGET_SHARDS = (
    "op_100__seed_block_01",
    "op_100__seed_block_02",
)
TARGET_BLOCKS = (1, 2)
EXPECTED_SEEDS = tuple(trace_package.CAMPAIGN_SEEDS[:10])
EXPECTED_SEEDS_PER_SHARD = 5
EXPECTED_LANE_COUNT = 18
MECHANISMS = ("transport_delay", "planned_delivery_shortfall")
EXPECTED_ROWS_PER_SHARD = 185
EXPECTED_BASELINE_COUNT = 10
EXPECTED_INCIDENT_COUNT = 360
EXPECTED_TOTAL_COUNT = 370
EXPECTED_RISK_FILE_COUNT = 360
NUMERIC_TOLERANCE = 1e-9

HTML_NAME = "OUVRIR_BILAN_PROVISOIRE_REFERENCE_10_SUR_30.html"
RESULT_NAME = "bilan_provisoire.json"
METRICS_NAME = "mesures_simulees_370.csv"
LANE_STATS_NAME = "resultats_descriptifs_par_voie.csv"
SUPPLIER_STATS_NAME = "vue_descriptive_fournisseurs.csv"
EVIDENCE_INDEX_NAME = "index_preuves_sources.json"
MANIFEST_NAME = "manifest_paquet.json"
PACKAGE_FILES = frozenset(
    {
        HTML_NAME,
        RESULT_NAME,
        METRICS_NAME,
        LANE_STATS_NAME,
        SUPPLIER_STATS_NAME,
        EVIDENCE_INDEX_NAME,
        MANIFEST_NAME,
    }
)
SOURCE_METADATA_PATHS = (
    "campaign_manifest.json",
    *(f"shards/{shard_id}/progress.json" for shard_id in TARGET_SHARDS),
    *(f"shards/{shard_id}/shard_manifest.json" for shard_id in TARGET_SHARDS),
)

LANE_STAT_FIELDS = (
    "mechanism",
    "lane_id",
    "supplier_id",
    "item_id",
    "dst_node_id",
    "target_product_id",
    "simulation_count",
    "physical_exercise_count",
    "physical_exercise_rate",
    "service_loss_mean_pp",
    "service_loss_median_pp",
    "service_loss_min_pp",
    "service_loss_p10_pp",
    "service_loss_p90_pp",
    "service_loss_max_pp",
    "positive_service_effect_count",
    "on_due_units_lost_mean",
    "backlog_qty_days_per_demand_unit_mean",
    "production_not_released_mean_qty",
    "causal_service_loss_mean_pp",
    "effective_exposure_dose_sum",
    "effective_exposure_dose_unit",
)
SUPPLIER_STAT_FIELDS = (
    "mechanism",
    "descriptive_order",
    "supplier_id",
    "representative_lane_id",
    "item_id",
    "dst_node_id",
    "target_product_id",
    "tested_lane_count",
    "simulation_count",
    "physical_exercise_count",
    "service_loss_mean_pp",
    "service_loss_min_pp",
    "service_loss_p10_pp",
    "service_loss_p90_pp",
    "service_loss_max_pp",
    "positive_service_effect_count",
    "on_due_units_lost_mean",
    "backlog_qty_days_per_demand_unit_mean",
    "production_not_released_mean_qty",
)


class CheckpointError(ValueError):
    """Raised when the provisional checkpoint cannot fail closed."""


class CheckpointNotReady(CheckpointError):
    """Raised when one of the two immutable shard boundaries is not reached."""


ProcessScanner = Callable[[], Sequence[supervisor.ObservedProcess]]


@dataclass(frozen=True)
class SourceSnapshot:
    campaign_root: Path
    manifest: Mapping[str, Any]
    context: finalizer_v4.SignedCampaignContext
    seeds: tuple[int, ...]
    metric_rows: tuple[dict[str, str], ...]
    paired: pd.DataFrame
    evidence_index: tuple[dict[str, Any], ...]
    source_files: Mapping[str, Mapping[str, Any]]
    completed_at_utc: str


def _sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _stable_sha256(payload: Any) -> str:
    raw = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return _sha256_bytes(raw)


def _signed(payload: Mapping[str, Any], signature_field: str) -> dict[str, Any]:
    result = dict(payload)
    result[signature_field] = _stable_sha256(result)
    return result


def _verify_signature(
    payload: Mapping[str, Any], signature_field: str, *, label: str
) -> None:
    unsigned = dict(payload)
    actual = str(unsigned.pop(signature_field, ""))
    if not re.fullmatch(r"[0-9a-f]{64}", actual) or actual != _stable_sha256(unsigned):
        raise CheckpointError(f"Signature invalide ({label}).")


def _read_bytes_shared(path: Path) -> bytes:
    try:
        return shared_io._read_bytes_shared(path)  # noqa: SLF001
    except OSError as exc:
        raise CheckpointError(f"Fichier source illisible : {path.resolve()}") from exc


def _reject_duplicate_keys(pairs: Sequence[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise CheckpointError(f"Clé JSON dupliquée : {key}")
        result[key] = value
    return result


def _decode_json(raw: bytes, *, label: str) -> dict[str, Any]:
    try:
        payload = json.loads(
            raw.decode("utf-8-sig"), object_pairs_hook=_reject_duplicate_keys
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CheckpointError(f"JSON invalide ({label}).") from exc
    if not isinstance(payload, dict):
        raise CheckpointError(f"Objet JSON attendu ({label}).")
    return payload


def _read_json_shared(path: Path) -> tuple[dict[str, Any], bytes]:
    raw = _read_bytes_shared(path)
    return _decode_json(raw, label=str(path.resolve())), raw


@contextmanager
def _shared_finalizer_readers() -> Iterator[None]:
    """Temporarily make the frozen finalizer read campaign files with delete sharing."""

    previous_read_json = finalizer_v4._read_json  # noqa: SLF001
    previous_sha256 = finalizer_v4._sha256  # noqa: SLF001

    def read_json(path: Path) -> dict[str, Any]:
        return _read_json_shared(Path(path))[0]

    def sha256(path: Path) -> str:
        return _sha256_bytes(_read_bytes_shared(Path(path)))

    finalizer_v4._read_json = read_json  # type: ignore[attr-defined]  # noqa: SLF001
    finalizer_v4._sha256 = sha256  # type: ignore[attr-defined]  # noqa: SLF001
    try:
        yield
    finally:
        finalizer_v4._read_json = previous_read_json  # type: ignore[attr-defined]  # noqa: SLF001
        finalizer_v4._sha256 = previous_sha256  # type: ignore[attr-defined]  # noqa: SLF001


def _validate_source_metadata_snapshot(
    *, campaign_root: Path, expected: Mapping[str, Any]
) -> None:
    """Fail closed unless the five exact completion files remain byte-identical."""

    if set(expected) != set(SOURCE_METADATA_PATHS):
        raise CheckpointError("Empreintes de fin de blocs incomplètes.")
    for relative in SOURCE_METADATA_PATHS:
        reference = expected.get(relative)
        if not isinstance(reference, Mapping):
            raise CheckpointError(f"Empreinte source absente : {relative}.")
        raw = _read_bytes_shared(campaign_root / Path(relative))
        if reference.get("sha256") != _sha256_bytes(raw) or int(
            reference.get("size_bytes", -1)
        ) != len(raw):
            raise CheckpointNotReady(
                f"Le fichier de fin de bloc a changé pendant le contrôle : {relative}."
            )


def _normalised_path(value: str | Path) -> str:
    return os.path.normcase(str(Path(value).resolve(strict=False))).replace("/", "\\")


def _target_processes(
    *,
    campaign_root: Path,
    records: Sequence[supervisor.ObservedProcess],
) -> list[dict[str, Any]]:
    root = campaign_root.resolve(strict=False)
    runner = Path(campaign_v8.__file__).resolve()
    target_paths = {
        shard_id: _normalised_path(root / "shards" / shard_id)
        for shard_id in TARGET_SHARDS
    }
    found: dict[tuple[int, str], dict[str, Any]] = {}
    for process in records:
        exact = supervisor.identify_exact_run_shard(
            process, runner=runner, campaign_root=root
        )
        if exact is not None and exact.shard_id in TARGET_SHARDS:
            found[(process.pid, exact.shard_id)] = {
                "pid": process.pid,
                "shard_id": exact.shard_id,
                "role": "runner",
            }
        normalised_command = " ".join(process.command_line).replace("/", "\\")
        normalised_command = os.path.normcase(normalised_command)
        for shard_id, target_path in target_paths.items():
            if target_path in normalised_command:
                found.setdefault(
                    (process.pid, shard_id),
                    {
                        "pid": process.pid,
                        "shard_id": shard_id,
                        "role": "child_or_writer",
                    },
                )
    return sorted(found.values(), key=lambda row: (row["shard_id"], row["pid"]))


def _active_targets(
    campaign_root: Path, *, scanner: ProcessScanner
) -> list[dict[str, Any]]:
    try:
        records = scanner()
    except Exception as exc:  # noqa: BLE001 - fail closed on incomplete process table
        raise CheckpointError(
            "Impossible de vérifier intégralement la table des processus."
        ) from exc
    return _target_processes(campaign_root=campaign_root, records=records)


def _expected_seed_map(manifest: Mapping[str, Any]) -> dict[str, tuple[int, ...]]:
    shards = manifest.get("shards")
    if not isinstance(shards, list):
        raise CheckpointError("Définitions de blocs absentes du manifeste de campagne.")
    by_id = {
        str(row.get("shard_id") or ""): row
        for row in shards
        if isinstance(row, Mapping)
    }
    if any(shard_id not in by_id for shard_id in TARGET_SHARDS):
        raise CheckpointError("Les deux blocs de référence ne sont pas déclarés.")
    result: dict[str, tuple[int, ...]] = {}
    for shard_id in TARGET_SHARDS:
        row = by_id[shard_id]
        try:
            seeds = tuple(int(value) for value in row.get("seed_ids") or ())
        except (TypeError, ValueError) as exc:
            raise CheckpointError(f"Simulations invalides pour {shard_id}.") from exc
        if len(seeds) != EXPECTED_SEEDS_PER_SHARD or len(set(seeds)) != len(seeds):
            raise CheckpointError(
                f"Cinq simulations distinctes attendues : {shard_id}."
            )
        result[shard_id] = seeds
    combined = tuple(seed for shard_id in TARGET_SHARDS for seed in result[shard_id])
    if combined != EXPECTED_SEEDS:
        raise CheckpointError(
            "Les deux blocs ne correspondent pas aux 10 premières simulations signées."
        )
    return result


def _validate_complete_shard_metadata(
    *,
    manifest: Mapping[str, Any],
    shard_id: str,
    block_number: int,
    seeds: Sequence[int],
    progress: Mapping[str, Any],
    shard_manifest: Mapping[str, Any],
) -> None:
    campaign_signature = str(manifest.get("campaign_signature") or "")
    if (
        progress.get("schema_version") != campaign_v4.PROGRESS_SCHEMA_VERSION
        or progress.get("campaign_signature") != campaign_signature
        or progress.get("shard_id") != shard_id
        or progress.get("operating_point_id") != "op_100"
        or int(progress.get("seed_block", -1)) != block_number
        or progress.get("seed_ids") != list(seeds)
        or progress.get("status") != "complete"
        or int(progress.get("planned_case_count", -1)) != EXPECTED_ROWS_PER_SHARD
        or int(progress.get("completed_case_count", -1)) != EXPECTED_ROWS_PER_SHARD
        or int(progress.get("failed_case_count", -1)) != 0
        or progress.get("running_case_keys") != []
        or progress.get("errors") != []
    ):
        raise CheckpointNotReady(f"Bloc incomplet ou en erreur : {shard_id}.")

    unsigned = dict(shard_manifest)
    for field in (
        "completed_case_count",
        "valid_case_count",
        "invalid_or_not_applicable_case_count",
        "runtime_failure_count",
        "completed_at_utc",
    ):
        unsigned.pop(field, None)
    signature = str(unsigned.pop("shard_signature", ""))
    unsigned["status"] = "planned"
    expected_lanes = [str(row.get("lane_id") or "") for row in manifest["lanes"]]
    if (
        shard_manifest.get("schema_version") != f"{campaign_v4.SCHEMA_VERSION}.shard.v1"
        or shard_manifest.get("campaign_signature") != campaign_signature
        or shard_manifest.get("shard_id") != shard_id
        or shard_manifest.get("operating_point_id") != "op_100"
        or int(shard_manifest.get("seed_block", -1)) != block_number
        or shard_manifest.get("seed_ids") != list(seeds)
        or shard_manifest.get("lane_ids") != expected_lanes
        or shard_manifest.get("mechanisms") != list(MECHANISMS)
        or shard_manifest.get("execution_scope") != "campaign_shard"
        or shard_manifest.get("status") != "complete"
        or int(shard_manifest.get("planned_case_count", -1)) != EXPECTED_ROWS_PER_SHARD
        or int(shard_manifest.get("completed_case_count", -1))
        != EXPECTED_ROWS_PER_SHARD
        or int(shard_manifest.get("valid_case_count", -1)) != EXPECTED_ROWS_PER_SHARD
        or int(shard_manifest.get("invalid_or_not_applicable_case_count", -1)) != 0
        or int(shard_manifest.get("runtime_failure_count", -1)) != 0
        or not re.fullmatch(r"[0-9a-f]{64}", signature)
        or signature != campaign_v4._stable_sha256(unsigned)  # noqa: SLF001
    ):
        raise CheckpointError(f"Contrat final du bloc invalide : {shard_id}.")


def evaluate_readiness(
    campaign_root: Path,
    *,
    scanner: ProcessScanner = supervisor.scan_processes,
) -> dict[str, Any]:
    """Check the process table first and touch no campaign file while active."""

    root = campaign_root.resolve(strict=False)
    active = _active_targets(root, scanner=scanner)
    if active:
        return {
            "schema_version": f"{SCHEMA_VERSION}.readiness.v1",
            "status": "running_target_shards",
            "ready": False,
            "campaign_files_read": False,
            "active_processes": active,
            "message_fr": "Les deux blocs travaillent encore; aucun fichier de campagne n'a été lu.",
        }

    try:
        manifest, manifest_raw = _read_json_shared(root / "campaign_manifest.json")
        seed_map = _expected_seed_map(manifest)
        metadata: dict[str, Any] = {
            "campaign_manifest.json": {
                "sha256": _sha256_bytes(manifest_raw),
                "size_bytes": len(manifest_raw),
            }
        }
        completed_at: list[str] = []
        for shard_id, block_number in zip(TARGET_SHARDS, TARGET_BLOCKS, strict=True):
            shard_dir = root / "shards" / shard_id
            progress, progress_raw = _read_json_shared(shard_dir / "progress.json")
            shard_manifest, shard_manifest_raw = _read_json_shared(
                shard_dir / "shard_manifest.json"
            )
            _validate_complete_shard_metadata(
                manifest=manifest,
                shard_id=shard_id,
                block_number=block_number,
                seeds=seed_map[shard_id],
                progress=progress,
                shard_manifest=shard_manifest,
            )
            for name, raw in (
                (f"shards/{shard_id}/progress.json", progress_raw),
                (f"shards/{shard_id}/shard_manifest.json", shard_manifest_raw),
            ):
                metadata[name] = {
                    "sha256": _sha256_bytes(raw),
                    "size_bytes": len(raw),
                }
            completed_at.append(str(shard_manifest.get("completed_at_utc") or ""))
    except (CheckpointError, FileNotFoundError, KeyError, TypeError, ValueError) as exc:
        return {
            "schema_version": f"{SCHEMA_VERSION}.readiness.v1",
            "status": "not_ready",
            "ready": False,
            "campaign_files_read": True,
            "active_processes": [],
            "message_fr": str(exc),
        }

    active_after = _active_targets(root, scanner=scanner)
    if active_after:
        return {
            "schema_version": f"{SCHEMA_VERSION}.readiness.v1",
            "status": "activity_race_detected",
            "ready": False,
            "campaign_files_read": True,
            "active_processes": active_after,
            "message_fr": "Une activité sur les blocs est apparue pendant le contrôle; publication refusée.",
        }
    return {
        "schema_version": f"{SCHEMA_VERSION}.readiness.v1",
        "status": "ready_two_complete_shards",
        "ready": True,
        "campaign_files_read": True,
        "active_processes": [],
        "campaign_signature": manifest["campaign_signature"],
        "shard_ids": list(TARGET_SHARDS),
        "seed_ids": list(EXPECTED_SEEDS),
        "completed_case_count": EXPECTED_TOTAL_COUNT,
        "failed_case_count": 0,
        "completed_at_utc": max(completed_at),
        "source_metadata": metadata,
        "message_fr": "Deux blocs terminés et sans erreur; le bilan provisoire peut être construit.",
    }


def _expected_case_keys(
    *, shard_id: str, seeds: Sequence[int], lane_ids: Sequence[str]
) -> set[str]:
    del shard_id  # Identity is checked in every row; keys do not carry the block id.
    keys = {f"op_100__baseline__seed_{seed}" for seed in seeds}
    keys.update(
        f"op_100__{lane_id}__{mechanism}__seed_{seed}"
        for seed in seeds
        for lane_id in lane_ids
        for mechanism in MECHANISMS
    )
    return keys


def _csv_rows(
    raw: bytes, *, expected_fields: Sequence[str], label: str
) -> list[dict[str, str]]:
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise CheckpointError(f"CSV non UTF-8 : {label}.") from exc
    reader = csv.DictReader(io.StringIO(text, newline=""))
    if reader.fieldnames != list(expected_fields):
        raise CheckpointError(f"Colonnes CSV inattendues : {label}.")
    return [dict(row) for row in reader]


def _canonical_metric_row(row: Mapping[str, Any]) -> dict[str, str]:
    return {
        field: "" if row.get(field) is None else str(row.get(field, ""))
        for field in campaign_v4.METRIC_FIELDS
    }


def _validate_evidence_payload(
    *,
    payload: Mapping[str, Any],
    manifest: Mapping[str, Any],
    row: Mapping[str, str],
    shard_id: str,
) -> None:
    case_key = str(row["case_key"])
    try:
        campaign_v4._validate_evidence(  # noqa: SLF001
            payload,
            manifest=manifest,
            case_key=case_key,
            case_signature=str(row["case_signature"]),
        )
    except ValueError as exc:
        raise CheckpointError(f"Preuve signée invalide : {case_key}.") from exc
    metrics = payload.get("metrics")
    if (
        payload.get("contract_revision") != campaign_v4.CONTRACT_REVISION
        or payload.get("shard_id") != shard_id
        or payload.get("valid") is not True
        or payload.get("status") not in {"valid", "valid_no_exposure"}
        or payload.get("validation_errors") != []
        or not isinstance(metrics, Mapping)
        or not finalizer_v4._is_sha256(metrics.get("warmup_core_state_sha256"))  # noqa: SLF001
        or not finalizer_v4._is_sha256(metrics.get("summary_sha256"))  # noqa: SLF001
    ):
        raise CheckpointError(f"Preuve physique incomplète : {case_key}.")


def _reconstruct_signed_metrics(
    *,
    campaign_root: Path,
    manifest: Mapping[str, Any],
    seed_map: Mapping[str, Sequence[int]],
) -> tuple[
    tuple[dict[str, str], ...],
    tuple[dict[str, Any], ...],
    dict[str, dict[str, Any]],
]:
    lane_ids = tuple(str(row["lane_id"]) for row in manifest["lanes"])
    if len(lane_ids) != EXPECTED_LANE_COUNT or len(set(lane_ids)) != len(lane_ids):
        raise CheckpointError("Exactement 18 voies physiques distinctes sont requises.")
    all_rows: list[dict[str, str]] = []
    metrics_source: dict[str, dict[str, Any]] = {}
    expected_by_shard: dict[str, set[str]] = {}
    for shard_id in TARGET_SHARDS:
        path = campaign_root / "shards" / shard_id / "campaign_metrics.csv"
        raw = _read_bytes_shared(path)
        rows = _csv_rows(
            raw,
            expected_fields=campaign_v4.METRIC_FIELDS,
            label=str(path.resolve()),
        )
        if len(rows) != EXPECTED_ROWS_PER_SHARD:
            raise CheckpointError(f"185 lignes attendues dans {shard_id}.")
        expected = _expected_case_keys(
            shard_id=shard_id, seeds=seed_map[shard_id], lane_ids=lane_ids
        )
        if {str(row.get("case_key") or "") for row in rows} != expected:
            raise CheckpointError(f"Univers de cas incomplet ou dupliqué : {shard_id}.")
        if any(str(row.get("shard_id") or "") != shard_id for row in rows):
            raise CheckpointError(f"Identité de bloc incohérente : {shard_id}.")
        expected_by_shard[shard_id] = expected
        all_rows.extend(rows)
        relative = path.relative_to(campaign_root).as_posix()
        metrics_source[relative] = {
            "sha256": _sha256_bytes(raw),
            "size_bytes": len(raw),
            "row_count": len(rows),
        }
    case_keys = [str(row["case_key"]) for row in all_rows]
    if len(all_rows) != EXPECTED_TOTAL_COUNT or len(set(case_keys)) != len(case_keys):
        raise CheckpointError("Les 370 résultats attendus ne sont pas uniques.")

    evidence_by_case: dict[str, dict[str, Any]] = {}
    baseline_by_signature: dict[str, dict[str, Any]] = {}
    evidence_index: list[dict[str, Any]] = []
    row_by_case = {str(row["case_key"]): row for row in all_rows}
    for shard_id in TARGET_SHARDS:
        shard_root = (campaign_root / "shards" / shard_id).resolve()
        evidence_root = (shard_root / "case_evidence").resolve()
        risk_root = (shard_root / "inputs" / "risk_events").resolve()
        for case_key in sorted(expected_by_shard[shard_id]):
            row = row_by_case[case_key]
            evidence_path = (evidence_root / f"{case_key}.json").resolve()
            if (
                not evidence_path.is_relative_to(evidence_root)
                or evidence_path.name != f"{case_key}.json"
            ):
                raise CheckpointError(f"Chemin de preuve invalide : {case_key}.")
            evidence_raw = _read_bytes_shared(evidence_path)
            payload = _decode_json(evidence_raw, label=case_key)
            _validate_evidence_payload(
                payload=payload,
                manifest=manifest,
                row=row,
                shard_id=shard_id,
            )
            index_row: dict[str, Any] = {
                "case_key": case_key,
                "shard_id": shard_id,
                "stage": str(payload.get("stage") or ""),
                "mechanism": str(row.get("mechanism") or "baseline"),
                "evidence_relative_path": evidence_path.relative_to(
                    campaign_root
                ).as_posix(),
                "evidence_sha256": _sha256_bytes(evidence_raw),
            }
            if payload.get("stage") == "incident":
                risk_path = (risk_root / f"{case_key}.csv").resolve()
                if not risk_path.is_relative_to(risk_root):
                    raise CheckpointError(f"Chemin d'incident invalide : {case_key}.")
                risk_raw = _read_bytes_shared(risk_path)
                risk_sha = str(payload.get("risk_csv_sha256") or "")
                if (
                    not re.fullmatch(r"[0-9a-f]{64}", risk_sha)
                    or _sha256_bytes(risk_raw) != risk_sha
                ):
                    raise CheckpointError(f"Fichier d'incident altéré : {case_key}.")
                index_row.update(
                    {
                        "risk_relative_path": risk_path.relative_to(
                            campaign_root
                        ).as_posix(),
                        "risk_sha256": risk_sha,
                    }
                )
            evidence_by_case[case_key] = payload
            if payload.get("stage") == "baseline":
                signature = str(payload.get("case_signature") or "")
                if (
                    not finalizer_v4._is_sha256(signature)  # noqa: SLF001
                    or signature in baseline_by_signature
                ):
                    raise CheckpointError(
                        "Signature de référence absente ou dupliquée."
                    )
                baseline_by_signature[signature] = payload
            evidence_index.append(index_row)
    if len(baseline_by_signature) != EXPECTED_BASELINE_COUNT:
        raise CheckpointError("Dix références appariées sont requises.")
    if (
        sum(row["stage"] == "incident" for row in evidence_index)
        != EXPECTED_INCIDENT_COUNT
    ):
        raise CheckpointError("Les 360 preuves d'incident sont requises.")

    for case_key, row in row_by_case.items():
        rebuilt = campaign_v4._flatten_metric_row(  # noqa: SLF001
            evidence_by_case[case_key], baseline_by_signature=baseline_by_signature
        )
        if _canonical_metric_row(rebuilt) != dict(row):
            changed = [
                field
                for field in campaign_v4.METRIC_FIELDS
                if _canonical_metric_row(rebuilt)[field] != row[field]
            ]
            raise CheckpointError(
                f"Mesure différente de sa preuve signée ({case_key}) : "
                + ", ".join(changed[:8])
            )
    return tuple(all_rows), tuple(evidence_index), metrics_source


@contextmanager
def _partial_validation_constants() -> Iterator[None]:
    names = (
        "OPERATING_POINTS",
        "EXPECTED_SEEDS",
        "EXPECTED_REPETITION_COUNT",
        "EXPECTED_BASELINE_COUNT",
        "EXPECTED_INCIDENT_COUNT",
        "EXPECTED_TOTAL_COUNT",
    )
    previous = {name: getattr(finalizer_v4, name) for name in names}
    finalizer_v4.OPERATING_POINTS = ("op_100",)
    finalizer_v4.EXPECTED_SEEDS = EXPECTED_SEEDS
    finalizer_v4.EXPECTED_REPETITION_COUNT = len(EXPECTED_SEEDS)
    finalizer_v4.EXPECTED_BASELINE_COUNT = EXPECTED_BASELINE_COUNT
    finalizer_v4.EXPECTED_INCIDENT_COUNT = EXPECTED_INCIDENT_COUNT
    finalizer_v4.EXPECTED_TOTAL_COUNT = EXPECTED_TOTAL_COUNT
    try:
        yield
    finally:
        for name, value in previous.items():
            setattr(finalizer_v4, name, value)


def _v8_compatibility_validation_frame(
    frame: pd.DataFrame,
    *,
    context: finalizer_v4.SignedCampaignContext,
) -> pd.DataFrame:
    """Project signed V8 comparability fields onto a validation-only copy.

    V8 intentionally leaves three legacy V4 metric columns empty: their
    authoritative values live in the signed target registry.  The mature V4
    validator still requires those columns to be populated before it checks
    them against that registry.  Rehydrate only the disposable validation
    frame; the reconstructed source rows written to the checkpoint stay
    byte-for-byte equivalent to their signed evidence.
    """

    required_fields = (
        "required_comparable_seed_count",
        "comparable_campaign_seed_count",
        "seed_cross_state_exposure_comparable",
    )
    missing_columns = [field for field in required_fields if field not in frame]
    if missing_columns:
        raise CheckpointError(
            "Colonnes de comparabilité V8 absentes : "
            + ", ".join(missing_columns)
        )

    registry = context.registry
    targets = registry.get("targets") if isinstance(registry, Mapping) else None
    required_seed_count = (
        registry.get("required_comparable_seed_count")
        if isinstance(registry, Mapping)
        else None
    )
    if (
        not isinstance(targets, list)
        or required_seed_count != campaign_v8.REQUIRED_COMPARABLE_SEED_COUNT
    ):
        raise CheckpointError("Contrat de comparabilité V8 signé incohérent.")

    registry_by_key: dict[tuple[str, int, str], Mapping[str, Any]] = {}
    for target in targets:
        if not isinstance(target, Mapping):
            raise CheckpointError("Cellule invalide dans le registre V8 signé.")
        try:
            key = (
                str(target["operating_point_id"]),
                int(target["seed"]),
                str(target["lane_id"]),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise CheckpointError(
                "Identité de cellule incomplète dans le registre V8 signé."
            ) from exc
        if key in registry_by_key:
            raise CheckpointError(
                "Cellule dupliquée dans le registre V8 signé : " + repr(key)
            )
        registry_by_key[key] = target

    projected = frame.copy(deep=True)
    for field in required_fields:
        projected[field] = projected[field].astype(object)
    incident_mask = (
        projected["stage"].astype(str).str.strip().str.casefold() == "incident"
    )

    def is_blank(value: Any) -> bool:
        return value is None or str(value).strip() in {"", "nan", "None"}

    for index, row in projected.loc[incident_mask].iterrows():
        try:
            key = (
                str(row["operating_point_id"]),
                int(float(row["seed"])),
                str(row["lane_id"]),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise CheckpointError(
                "Identité de mesure incidente V8 incomplète."
            ) from exc
        target = registry_by_key.get(key)
        if target is None:
            raise CheckpointError(
                "Mesure absente du registre de cibles V8 signé : " + repr(key)
            )
        expected = {
            "required_comparable_seed_count": target.get(
                "required_comparable_seed_count"
            ),
            "comparable_campaign_seed_count": target.get(
                "comparable_campaign_seed_count"
            ),
            "seed_cross_state_exposure_comparable": target.get(
                "seed_cross_state_exposure_comparable"
            ),
        }
        if (
            expected["required_comparable_seed_count"] != required_seed_count
            or expected["comparable_campaign_seed_count"] != required_seed_count
            or expected["seed_cross_state_exposure_comparable"] is not True
        ):
            raise CheckpointError(
                "Comparabilité de cellule incohérente dans le registre V8 signé : "
                + repr(key)
            )
        for field, expected_value in expected.items():
            actual = row[field]
            if not is_blank(actual):
                if field == "seed_cross_state_exposure_comparable":
                    matches = finalizer_v4._truthy(actual) is bool(expected_value)  # noqa: SLF001
                else:
                    try:
                        matches = math.isclose(
                            float(actual),
                            float(expected_value),
                            rel_tol=0.0,
                            abs_tol=NUMERIC_TOLERANCE,
                        )
                    except (TypeError, ValueError):
                        matches = False
                if not matches:
                    raise CheckpointError(
                        f"Mesure/registre V8 incompatibles : {field} pour {key!r}."
                    )
            projected.at[index, field] = expected_value
    return projected


def _validated_paired_frame(
    *,
    rows: Sequence[Mapping[str, str]],
    context: finalizer_v4.SignedCampaignContext,
) -> pd.DataFrame:
    frame = pd.DataFrame([dict(row) for row in rows]).fillna("")
    validation_frame = _v8_compatibility_validation_frame(frame, context=context)
    subset_context = replace(context, shard_ids=frozenset(TARGET_SHARDS))
    with _partial_validation_constants():
        paired, validation = finalizer_v4.validate_and_pair(
            validation_frame, subset_context
        )
    if (
        validation.get("baseline_row_count") != EXPECTED_BASELINE_COUNT
        or validation.get("incident_row_count") != EXPECTED_INCIDENT_COUNT
        or validation.get("total_row_count") != EXPECTED_TOTAL_COUNT
        or validation.get("divergent_duplicate_count") != 0
    ):
        raise CheckpointError("Validation arithmétique partielle incohérente.")
    return paired


def _load_snapshot(
    campaign_root: Path,
    *,
    readiness: Mapping[str, Any],
    scanner: ProcessScanner,
) -> SourceSnapshot:
    root = campaign_root.resolve()
    if readiness.get("ready") is not True:
        raise CheckpointNotReady(str(readiness.get("message_fr") or "Bilan non prêt."))
    if _active_targets(root, scanner=scanner):
        raise CheckpointNotReady("Une activité sur les deux blocs a repris.")

    readiness_metadata = readiness.get("source_metadata")
    if not isinstance(readiness_metadata, Mapping):
        raise CheckpointError(
            "Empreintes de fin de blocs absentes du contrôle préalable."
        )
    _validate_source_metadata_snapshot(campaign_root=root, expected=readiness_metadata)
    finalizer_v8.validate_frozen_implementation()
    manifest, manifest_raw = _read_json_shared(root / "campaign_manifest.json")
    seed_map = _expected_seed_map(manifest)
    metric_paths = tuple(
        root / "shards" / shard_id / "campaign_metrics.csv"
        for shard_id in TARGET_SHARDS
    )
    input_evidence = finalizer_v4.InputEvidence(
        manifest_path=root / "campaign_manifest.json",
        metrics_paths=metric_paths,
        manifest_sha256=_sha256_bytes(manifest_raw),
        metrics_sha256={},
    )
    with finalizer_v8.patched_v8_context(), _shared_finalizer_readers():
        context = finalizer_v8._validate_v8_signed_context(  # noqa: SLF001
            input_evidence, manifest
        )
    rows, evidence_index, metric_sources = _reconstruct_signed_metrics(
        campaign_root=root, manifest=manifest, seed_map=seed_map
    )
    paired = _validated_paired_frame(rows=rows, context=context)
    _validate_source_metadata_snapshot(campaign_root=root, expected=readiness_metadata)
    if _active_targets(root, scanner=scanner):
        raise CheckpointNotReady(
            "Une activité sur les deux blocs est apparue pendant la lecture; publication refusée."
        )

    registry_raw = _read_bytes_shared(context.registry_path)
    preflight_raw = _read_bytes_shared(context.preflight_path)
    source_files = {
        **dict(readiness_metadata),
        **metric_sources,
        "target_discovery/target_registry.json": {
            "sha256": _sha256_bytes(registry_raw),
            "size_bytes": len(registry_raw),
        },
        "state_validation_binding.json": {
            "sha256": _sha256_bytes(preflight_raw),
            "size_bytes": len(preflight_raw),
        },
    }
    return SourceSnapshot(
        campaign_root=root,
        manifest=manifest,
        context=context,
        seeds=EXPECTED_SEEDS,
        metric_rows=rows,
        paired=paired,
        evidence_index=evidence_index,
        source_files=source_files,
        completed_at_utc=str(readiness["completed_at_utc"]),
    )


def _quantile(values: np.ndarray, probability: float) -> float:
    return float(np.quantile(values, probability, method="linear"))


def _descriptive_statistics(
    paired: pd.DataFrame,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    lane_rows: list[dict[str, Any]] = []
    group_fields = ["mechanism", "lane_id"]
    expected_seed_set = set(EXPECTED_SEEDS)
    for (mechanism, lane_id), raw_group in paired.groupby(group_fields, sort=True):
        group = raw_group.set_index("seed").loc[list(EXPECTED_SEEDS)].reset_index()
        if len(group) != len(EXPECTED_SEEDS) or set(group["seed"]) != expected_seed_set:
            raise CheckpointError(f"Dix comparaisons appariées attendues : {lane_id}.")
        first = group.iloc[0]
        service = group["impact_service_loss_fed_product_pp"].to_numpy(dtype=float)
        exercise = group["incident_physically_exercised"].to_numpy(dtype=bool)
        lane_rows.append(
            {
                "mechanism": str(mechanism),
                "lane_id": str(lane_id),
                "supplier_id": str(first["supplier_id"]),
                "item_id": str(first["item_id"]),
                "dst_node_id": str(first["dst_node_id"]),
                "target_product_id": str(first["target_product_id"]),
                "simulation_count": len(group),
                "physical_exercise_count": int(np.count_nonzero(exercise)),
                "physical_exercise_rate": float(np.mean(exercise)),
                "service_loss_mean_pp": float(np.mean(service)),
                "service_loss_median_pp": float(np.median(service)),
                "service_loss_min_pp": float(np.min(service)),
                "service_loss_p10_pp": _quantile(service, 0.10),
                "service_loss_p90_pp": _quantile(service, 0.90),
                "service_loss_max_pp": float(np.max(service)),
                "positive_service_effect_count": int(
                    np.count_nonzero(service > NUMERIC_TOLERANCE)
                ),
                "on_due_units_lost_mean": float(
                    group["impact_on_due_loss_fed_product_qty"].mean()
                ),
                "backlog_qty_days_per_demand_unit_mean": float(
                    group["impact_backlog_qty_days_per_demand_unit"].mean()
                ),
                "production_not_released_mean_qty": float(
                    group["impact_production_loss_fed_product_qty"].mean()
                ),
                "causal_service_loss_mean_pp": float(
                    group["causal_service_loss_fed_product_pp"].mean()
                ),
                "effective_exposure_dose_sum": float(
                    group["effective_exposure_dose"].sum()
                ),
                "effective_exposure_dose_unit": str(
                    first["effective_exposure_dose_unit"]
                ),
            }
        )

    supplier_rows: list[dict[str, Any]] = []
    lane_frame = pd.DataFrame(lane_rows)
    for mechanism, mechanism_group in lane_frame.groupby("mechanism", sort=True):
        selected: list[dict[str, Any]] = []
        for supplier_id, group in mechanism_group.groupby("supplier_id", sort=True):
            ordered = group.sort_values(
                ["service_loss_mean_pp", "lane_id"], ascending=[False, True]
            )
            representative = ordered.iloc[0].to_dict()
            selected.append(
                {
                    "mechanism": str(mechanism),
                    "supplier_id": str(supplier_id),
                    "representative_lane_id": representative["lane_id"],
                    "item_id": representative["item_id"],
                    "dst_node_id": representative["dst_node_id"],
                    "target_product_id": representative["target_product_id"],
                    "tested_lane_count": len(group),
                    **{
                        field: representative[field]
                        for field in (
                            "simulation_count",
                            "physical_exercise_count",
                            "service_loss_mean_pp",
                            "service_loss_min_pp",
                            "service_loss_p10_pp",
                            "service_loss_p90_pp",
                            "service_loss_max_pp",
                            "positive_service_effect_count",
                            "on_due_units_lost_mean",
                            "backlog_qty_days_per_demand_unit_mean",
                            "production_not_released_mean_qty",
                        )
                    },
                }
            )
        selected.sort(
            key=lambda row: (-float(row["service_loss_mean_pp"]), row["supplier_id"])
        )
        for order, row in enumerate(selected, start=1):
            row["descriptive_order"] = order
            supplier_rows.append(row)
    lane_rows.sort(key=lambda row: (row["mechanism"], row["lane_id"]))
    return lane_rows, supplier_rows


def _json_safe(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, (np.floating, float)):
        number = float(value)
        if not math.isfinite(number):
            raise CheckpointError("Valeur numérique non finie dans le résultat.")
        return number
    return value


def _json_bytes(payload: Mapping[str, Any]) -> bytes:
    return (
        json.dumps(
            _json_safe(payload),
            ensure_ascii=False,
            sort_keys=True,
            indent=2,
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")


def _csv_bytes(rows: Sequence[Mapping[str, Any]], fields: Sequence[str]) -> bytes:
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    writer.writerows({field: row.get(field, "") for field in fields} for row in rows)
    return b"\xef\xbb\xbf" + buffer.getvalue().encode("utf-8")


def _fr(value: Any, digits: int = 2) -> str:
    number = float(value)
    return f"{number:,.{digits}f}".replace(",", " ").replace(".", ",")


def _mechanism_label(value: str) -> str:
    if value == "transport_delay":
        return "Retard de transport de 120 jours"
    if value == "planned_delivery_shortfall":
        return "Livraison réduite à la moitié de la quantité attendue"
    raise CheckpointError(f"Mécanisme inattendu : {value}.")


def _render_supplier_table(rows: Sequence[Mapping[str, Any]], mechanism: str) -> str:
    body: list[str] = []
    for row in rows:
        if row["mechanism"] != mechanism:
            continue
        item = str(row["item_id"]).removeprefix("item:")
        body.append(
            "<tr>"
            f"<td>{int(row['descriptive_order'])}</td>"
            f"<td><strong>{html.escape(str(row['supplier_id']))}</strong><br>"
            f"<small>{html.escape(item)} vers {html.escape(str(row['dst_node_id']))} "
            f"puis produit {html.escape(str(row['target_product_id']))}</small></td>"
            f"<td>{_fr(row['service_loss_mean_pp'])} point(s)</td>"
            f"<td>{_fr(row['service_loss_min_pp'])} à {_fr(row['service_loss_max_pp'])}</td>"
            f"<td>{int(row['physical_exercise_count'])}/10</td>"
            f"<td>{_fr(row['on_due_units_lost_mean'], 0)}</td>"
            f"<td>{_fr(row['production_not_released_mean_qty'], 0)}</td>"
            "</tr>"
        )
    return "".join(body)


def render_html(result: Mapping[str, Any]) -> str:
    supplier_rows = result["supplier_view"]
    sections = []
    for mechanism in MECHANISMS:
        sections.append(
            f"""
<section>
  <span class="tag">HYPOTHÈSE SIMULÉE</span>
  <h2>{html.escape(_mechanism_label(mechanism))}</h2>
  <p>Le tableau est trié par baisse moyenne du service du produit alimenté. Ce tri
  décrit seulement les dix simulations disponibles et ne constitue ni une note
  fournisseur ni une conclusion finale.</p>
  <div class="scroll"><table><thead><tr><th>Ordre descriptif</th><th>Flux représentatif</th>
  <th>Baisse moyenne du service</th><th>Minimum–maximum</th><th>Incident exercé</th>
  <th>Unités à l'heure perdues, moyenne</th><th>Production non libérée, moyenne</th></tr></thead>
  <tbody>{_render_supplier_table(supplier_rows, mechanism)}</tbody></table></div>
</section>"""
        )
    return f"""<!doctype html>
<html lang="fr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Bilan provisoire — fonctionnement de référence</title>
<style>
:root{{--ink:#13263d;--muted:#586b80;--line:#d7e1ec;--bg:#eef3f8;--card:#fff;--blue:#175ec7;--amber:#fff1ca}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--ink);font:15px/1.5 system-ui,-apple-system,"Segoe UI",sans-serif}}
main{{max-width:1450px;margin:auto;padding:28px}}section{{background:var(--card);border:1px solid var(--line);border-radius:16px;padding:20px;margin:16px 0}}
h1,h2{{margin-top:0}}.lead{{font-size:1.08rem;color:var(--muted);max-width:90ch}}.warn{{background:var(--amber);border:2px solid #c98500}}
.grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:12px}}.metric{{background:white;border:1px solid var(--line);border-radius:13px;padding:16px}}
.metric strong{{font-size:1.55rem;display:block}}.metric small,small{{color:var(--muted)}}.tag{{display:inline-block;background:#e6efff;color:#124caa;border-radius:999px;padding:4px 9px;font-weight:750}}
.scroll{{overflow:auto}}table{{border-collapse:collapse;width:100%;min-width:1100px}}th,td{{padding:10px;border-bottom:1px solid var(--line);text-align:left;vertical-align:top}}th{{background:#edf3fa;font-size:.78rem;text-transform:uppercase}}
.definitions{{display:grid;grid-template-columns:repeat(2,1fr);gap:12px}}.definitions article{{border-left:4px solid var(--blue);padding:10px 14px;background:#f6f9fd}}
@media(max-width:850px){{main{{padding:14px}}.grid,.definitions{{grid-template-columns:1fr}}}}
</style></head><body><main>
<section class="warn"><span class="tag">RÉSULTAT PROVISOIRE</span><h1>Premier bilan du fonctionnement de référence</h1>
<p class="lead"><strong>Dix simulations sur les trente prévues sont disponibles.</strong>
Cette page montre un point d'étape reproductible. Elle ne permet pas encore de conclure
sur la stabilité des constats lorsque le fonctionnement du réseau change.</p></section>
<section class="grid">
  <article class="metric"><strong>10</strong><small>répétitions stochastiques appariées à leur référence</small></article>
  <article class="metric"><strong>360</strong><small>incidents simulés et appariés</small></article>
  <article class="metric"><strong>18</strong><small>voies physiques testées</small></article>
  <article class="metric"><strong>0</strong><small>échec dans les deux blocs terminés</small></article>
</section>
<section><h2>Ce que signifient les résultats</h2><div class="definitions">
<article><strong>HYPOTHÈSE</strong><p>L'incident est imposé au modèle pendant 42 jours. Il ne décrit pas un événement historique.</p></article>
<article><strong>SIMULÉ</strong><p>L'écart compare chaque incident au même fonctionnement sans incident, avec la même graine et un protocole de nombres aléatoires communs afin de réduire le bruit de comparaison.</p></article>
<article><strong>Incident exercé</strong><p>Une expédition prévue a réellement été touchée dans la simulation. Ce compteur ne mesure pas une fréquence réelle.</p></article>
<article><strong>Ordre descriptif</strong><p>Le tri porte sur la voie testée ayant la baisse moyenne la plus forte pour chaque fournisseur. Il pourra changer avec les résultats suivants.</p></article>
</div></section>
{"".join(sections)}
<section><h2>Limite de ce point d'étape</h2><p>Seul le fonctionnement de référence est présenté ici.
Les conséquences aval évoluent avec les stocks, les flux en transit, les besoins et les retards du modèle,
mais les incidents eux-mêmes sont des hypothèses externes. Les résultats définitifs demanderont l'ensemble
des simulations prévues et la comparaison des autres fonctionnements du réseau.</p></section>
</main></body></html>"""


def _result_payload(
    *,
    snapshot: SourceSnapshot,
    lane_rows: Sequence[Mapping[str, Any]],
    supplier_rows: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    unsigned = {
        "schema_version": RESULT_SCHEMA_VERSION,
        "status": "complete_provisional_checkpoint_not_final",
        "evidence_class": "conditional_simulation_descriptive_checkpoint",
        "scope": {
            "operating_point_id": "op_100",
            "business_label_fr": "fonctionnement de référence",
            "completed_simulation_count": len(snapshot.seeds),
            "planned_simulation_count": len(trace_package.CAMPAIGN_SEEDS),
            "baseline_case_count": EXPECTED_BASELINE_COUNT,
            "incident_case_count": EXPECTED_INCIDENT_COUNT,
            "total_case_count": EXPECTED_TOTAL_COUNT,
            "lane_count": EXPECTED_LANE_COUNT,
            "mechanisms": list(MECHANISMS),
            "incident_window_days": snapshot.context.disruption_window_days,
            "business_effect_window_days": finalizer_v4.BUSINESS_WINDOW_DAYS,
        },
        "interpretation": {
            "descriptive_only": True,
            "final_supplier_classification_allowed": False,
            "cross_state_comparison_available": False,
            "historical_frequency_estimated": False,
            "bootstrap_or_inferential_interval_published": False,
            "engine_runs_started_by_builder": 0,
        },
        "seed_ids": list(snapshot.seeds),
        "lane_statistics": list(lane_rows),
        "supplier_view": list(supplier_rows),
    }
    return _signed(_json_safe(unsigned), "result_signature")


def _source_evidence_payload(snapshot: SourceSnapshot) -> dict[str, Any]:
    unsigned = {
        "schema_version": EVIDENCE_INDEX_SCHEMA_VERSION,
        "status": "complete_reconstructed_from_signed_sources",
        "campaign_signature": snapshot.manifest["campaign_signature"],
        "case_count": len(snapshot.evidence_index),
        "baseline_case_count": EXPECTED_BASELINE_COUNT,
        "incident_case_count": EXPECTED_INCIDENT_COUNT,
        "risk_file_count": sum("risk_sha256" in row for row in snapshot.evidence_index),
        "entries": list(snapshot.evidence_index),
    }
    return _signed(unsigned, "evidence_index_signature")


def _builder_sources() -> dict[str, dict[str, Any]]:
    paths = (
        Path(__file__).resolve(),
        Path(campaign_v8.__file__).resolve(),
        Path(finalizer_v8.__file__).resolve(),
        Path(finalizer_v4.__file__).resolve(),
        Path(shared_io.__file__).resolve(),
        Path(supervisor.__file__).resolve(),
    )
    return {
        str(path): {"sha256": _sha256_file(path), "size_bytes": path.stat().st_size}
        for path in paths
    }


def _files_for_package(snapshot: SourceSnapshot) -> dict[str, bytes]:
    lane_rows, supplier_rows = _descriptive_statistics(snapshot.paired)
    result = _result_payload(
        snapshot=snapshot, lane_rows=lane_rows, supplier_rows=supplier_rows
    )
    evidence_index = _source_evidence_payload(snapshot)
    files: dict[str, bytes] = {
        RESULT_NAME: _json_bytes(result),
        METRICS_NAME: _csv_bytes(snapshot.metric_rows, campaign_v4.METRIC_FIELDS),
        LANE_STATS_NAME: _csv_bytes(lane_rows, LANE_STAT_FIELDS),
        SUPPLIER_STATS_NAME: _csv_bytes(supplier_rows, SUPPLIER_STAT_FIELDS),
        EVIDENCE_INDEX_NAME: _json_bytes(evidence_index),
        HTML_NAME: render_html(result).encode("utf-8"),
    }
    output_index = {
        name: {
            "sha256": _sha256_bytes(raw),
            "size_bytes": len(raw),
            **(
                {"row_count": len(snapshot.metric_rows)}
                if name == METRICS_NAME
                else {"row_count": len(lane_rows)}
                if name == LANE_STATS_NAME
                else {"row_count": len(supplier_rows)}
                if name == SUPPLIER_STATS_NAME
                else {}
            ),
        }
        for name, raw in sorted(files.items())
    }
    manifest_unsigned = {
        "schema_version": PACKAGE_SCHEMA_VERSION,
        "status": "complete_provisional_new_or_identical",
        "source_completed_at_utc": snapshot.completed_at_utc,
        "campaign_root": str(snapshot.campaign_root),
        "campaign_signature": snapshot.manifest["campaign_signature"],
        "shard_ids": list(TARGET_SHARDS),
        "seed_ids": list(snapshot.seeds),
        "source_case_count": EXPECTED_TOTAL_COUNT,
        "source_failure_count": 0,
        "engine_runs_started_by_builder": 0,
        "source_files": snapshot.source_files,
        "builder_sources": _builder_sources(),
        "outputs": output_index,
    }
    files[MANIFEST_NAME] = _json_bytes(_signed(manifest_unsigned, "package_signature"))
    return files


def _safe_remove_staging(path: Path, parent: Path) -> None:
    resolved = path.resolve(strict=False)
    expected_parent = parent.resolve()
    if resolved.parent != expected_parent or not resolved.name.startswith(
        ".supplier-v8-reference-checkpoint-"
    ):
        raise CheckpointError(f"Dossier temporaire inattendu : {resolved}")
    if resolved.exists():
        shutil.rmtree(resolved)


def _publish_new_or_identical(
    *, output_dir: Path, files: Mapping[str, bytes]
) -> tuple[Path, bool]:
    destination = output_dir.resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(
        tempfile.mkdtemp(
            prefix=".supplier-v8-reference-checkpoint-", dir=destination.parent
        )
    ).resolve()
    try:
        for name, raw in files.items():
            (staging / name).write_bytes(raw)
        validate_package(staging)
        if destination.exists():
            validate_package(destination)
            expected_names = {path.name for path in staging.iterdir() if path.is_file()}
            actual_names = {
                path.name for path in destination.iterdir() if path.is_file()
            }
            identical = expected_names == actual_names and all(
                _sha256_file(staging / name) == _sha256_file(destination / name)
                for name in expected_names
            )
            if not identical:
                raise CheckpointError(
                    f"Destination existante différente; aucun écrasement : {destination}"
                )
            _safe_remove_staging(staging, destination.parent)
            return destination, True
        os.replace(staging, destination)
        return destination, False
    except Exception:
        if staging.exists():
            _safe_remove_staging(staging, destination.parent)
        raise


def build_checkpoint(
    *,
    campaign_root: Path,
    output_dir: Path,
    scanner: ProcessScanner = supervisor.scan_processes,
) -> dict[str, Any]:
    root = campaign_root.resolve(strict=False)
    destination = output_dir.resolve(strict=False)
    if destination == root or root in destination.parents:
        raise CheckpointError("La sortie doit rester extérieure à la campagne source.")
    readiness = evaluate_readiness(root, scanner=scanner)
    if readiness.get("ready") is not True:
        raise CheckpointNotReady(str(readiness.get("message_fr") or "Bilan non prêt."))
    snapshot = _load_snapshot(root, readiness=readiness, scanner=scanner)
    files = _files_for_package(snapshot)
    output, already_identical = _publish_new_or_identical(
        output_dir=destination, files=files
    )
    manifest = validate_package(output)
    return {
        "status": "already_identical" if already_identical else "created",
        "output_dir": str(output),
        "entrypoint": str(output / HTML_NAME),
        "package_signature": manifest["package_signature"],
        "case_count": EXPECTED_TOTAL_COUNT,
        "engine_runs_started": 0,
    }


def _validate_html(page: str) -> None:
    folded = re.sub(r"\s+", " ", page.casefold())
    required = (
        "résultat provisoire",
        "dix simulations sur les trente prévues",
        "ordre descriptif",
        "ne constitue ni une note fournisseur ni une conclusion finale",
        "fonctionnement de référence",
    )
    if any(fragment not in folded for fragment in required):
        raise CheckpointError("Les avertissements obligatoires manquent dans la page.")
    forbidden_patterns = (
        r"\btop\s*-?\s*3\b",
        r"\bcriticité\b",
        r"\bop[_ -]?93\b",
        r"\bop[_ -]?80\b",
        r"\blots?\b",
        r"\bactions?\b",
    )
    if any(re.search(pattern, folded) for pattern in forbidden_patterns):
        raise CheckpointError("La page contient une revendication hors périmètre.")
    if any(
        token in folded
        for token in (
            "http://",
            "https://",
            "<script src=",
            "<link rel=",
            "fetch(",
        )
    ):
        raise CheckpointError("La page n'est pas autonome.")


def validate_package(output_dir: Path) -> dict[str, Any]:
    root = output_dir.resolve(strict=True)
    if not root.is_dir():
        raise CheckpointError(f"Dossier attendu : {root}")
    names = {path.name for path in root.iterdir() if path.is_file()}
    if names != PACKAGE_FILES:
        raise CheckpointError("Contenu inattendu dans le paquet provisoire.")
    manifest = _decode_json((root / MANIFEST_NAME).read_bytes(), label=MANIFEST_NAME)
    _verify_signature(manifest, "package_signature", label="paquet")
    if (
        manifest.get("schema_version") != PACKAGE_SCHEMA_VERSION
        or manifest.get("status") != "complete_provisional_new_or_identical"
        or manifest.get("shard_ids") != list(TARGET_SHARDS)
        or manifest.get("seed_ids") != list(EXPECTED_SEEDS)
        or manifest.get("source_case_count") != EXPECTED_TOTAL_COUNT
        or manifest.get("source_failure_count") != 0
        or manifest.get("engine_runs_started_by_builder") != 0
    ):
        raise CheckpointError("Contrat du paquet provisoire invalide.")
    outputs = manifest.get("outputs")
    if not isinstance(outputs, Mapping) or set(outputs) != PACKAGE_FILES - {
        MANIFEST_NAME
    }:
        raise CheckpointError("Index de sorties incomplet.")
    for name, reference in outputs.items():
        path = root / name
        if (
            not isinstance(reference, Mapping)
            or reference.get("sha256") != _sha256_file(path)
            or int(reference.get("size_bytes", -1)) != path.stat().st_size
        ):
            raise CheckpointError(f"Sortie altérée : {name}.")

    result = _decode_json((root / RESULT_NAME).read_bytes(), label=RESULT_NAME)
    _verify_signature(result, "result_signature", label="résultat")
    interpretation = result.get("interpretation")
    scope = result.get("scope")
    if (
        result.get("schema_version") != RESULT_SCHEMA_VERSION
        or result.get("status") != "complete_provisional_checkpoint_not_final"
        or not isinstance(interpretation, Mapping)
        or interpretation.get("descriptive_only") is not True
        or interpretation.get("final_supplier_classification_allowed") is not False
        or interpretation.get("cross_state_comparison_available") is not False
        or interpretation.get("bootstrap_or_inferential_interval_published")
        is not False
        or interpretation.get("engine_runs_started_by_builder") != 0
        or not isinstance(scope, Mapping)
        or scope.get("completed_simulation_count") != 10
        or scope.get("incident_case_count") != EXPECTED_INCIDENT_COUNT
        or scope.get("total_case_count") != EXPECTED_TOTAL_COUNT
        or len(result.get("lane_statistics") or [])
        != EXPECTED_LANE_COUNT * len(MECHANISMS)
    ):
        raise CheckpointError("Résultat provisoire incohérent.")
    if any(
        set(row) != set(LANE_STAT_FIELDS) or row.get("simulation_count") != 10
        for row in result["lane_statistics"]
    ):
        raise CheckpointError("Statistiques par voie non descriptives ou incomplètes.")
    if any(
        set(row) != set(SUPPLIER_STAT_FIELDS) or row.get("simulation_count") != 10
        for row in result["supplier_view"]
    ):
        raise CheckpointError("Vue fournisseur non descriptive ou incomplète.")

    evidence = _decode_json(
        (root / EVIDENCE_INDEX_NAME).read_bytes(), label=EVIDENCE_INDEX_NAME
    )
    _verify_signature(evidence, "evidence_index_signature", label="preuves")
    if (
        evidence.get("schema_version") != EVIDENCE_INDEX_SCHEMA_VERSION
        or evidence.get("status") != "complete_reconstructed_from_signed_sources"
        or evidence.get("case_count") != EXPECTED_TOTAL_COUNT
        or evidence.get("baseline_case_count") != EXPECTED_BASELINE_COUNT
        or evidence.get("incident_case_count") != EXPECTED_INCIDENT_COUNT
        or evidence.get("risk_file_count") != EXPECTED_RISK_FILE_COUNT
        or len(evidence.get("entries") or []) != EXPECTED_TOTAL_COUNT
    ):
        raise CheckpointError("Index des preuves incomplet.")

    entries = evidence["entries"]
    evidence_case_keys: list[str] = []
    risk_case_keys: list[str] = []
    for entry in entries:
        if not isinstance(entry, Mapping):
            raise CheckpointError("Entrée de preuve invalide.")
        case_key = str(entry.get("case_key") or "")
        stage = entry.get("stage")
        expected_fields = {
            "case_key",
            "shard_id",
            "stage",
            "mechanism",
            "evidence_relative_path",
            "evidence_sha256",
        }
        if stage == "incident":
            expected_fields.update({"risk_relative_path", "risk_sha256"})
            risk_case_keys.append(case_key)
        elif stage != "baseline":
            raise CheckpointError(f"Étape de preuve invalide : {case_key}.")
        if (
            set(entry) != expected_fields
            or not case_key
            or entry.get("shard_id") not in TARGET_SHARDS
            or not re.fullmatch(
                r"[0-9a-f]{64}", str(entry.get("evidence_sha256") or "")
            )
            or (
                stage == "incident"
                and not re.fullmatch(
                    r"[0-9a-f]{64}", str(entry.get("risk_sha256") or "")
                )
            )
        ):
            raise CheckpointError(f"Référence de preuve invalide : {case_key}.")
        evidence_case_keys.append(case_key)
    if (
        len(set(evidence_case_keys)) != EXPECTED_TOTAL_COUNT
        or len(set(risk_case_keys)) != EXPECTED_RISK_FILE_COUNT
    ):
        raise CheckpointError("Références de preuves dupliquées ou incomplètes.")

    metric_rows = _csv_rows(
        (root / METRICS_NAME).read_bytes(),
        expected_fields=campaign_v4.METRIC_FIELDS,
        label=METRICS_NAME,
    )
    lane_rows = _csv_rows(
        (root / LANE_STATS_NAME).read_bytes(),
        expected_fields=LANE_STAT_FIELDS,
        label=LANE_STATS_NAME,
    )
    supplier_rows = _csv_rows(
        (root / SUPPLIER_STATS_NAME).read_bytes(),
        expected_fields=SUPPLIER_STAT_FIELDS,
        label=SUPPLIER_STATS_NAME,
    )
    if (
        len(metric_rows) != EXPECTED_TOTAL_COUNT
        or len(lane_rows) != EXPECTED_LANE_COUNT * len(MECHANISMS)
        or len(supplier_rows) != len(result["supplier_view"])
    ):
        raise CheckpointError("Comptage des tableaux du paquet invalide.")
    expected_output_rows = {
        METRICS_NAME: len(metric_rows),
        LANE_STATS_NAME: len(lane_rows),
        SUPPLIER_STATS_NAME: len(supplier_rows),
    }
    if any(
        outputs[name].get("row_count") != count
        for name, count in expected_output_rows.items()
    ):
        raise CheckpointError("Comptage signé des tableaux du paquet invalide.")
    metric_case_keys = [str(row.get("case_key") or "") for row in metric_rows]
    if len(set(metric_case_keys)) != EXPECTED_TOTAL_COUNT or set(
        metric_case_keys
    ) != set(evidence_case_keys):
        raise CheckpointError("Mesures et preuves ne couvrent pas les mêmes cas.")
    _validate_html((root / HTML_NAME).read_text(encoding="utf-8"))
    return manifest


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--mode", choices=("readiness", "build", "validate"), required=True
    )
    parser.add_argument("--campaign-root", type=Path)
    parser.add_argument("--output-dir", type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.mode in {"readiness", "build"} and args.campaign_root is None:
        raise SystemExit("--campaign-root est requis pour readiness/build")
    if args.mode in {"build", "validate"} and args.output_dir is None:
        raise SystemExit("--output-dir est requis pour build/validate")
    try:
        if args.mode == "readiness":
            result = evaluate_readiness(args.campaign_root)
            print(json.dumps(result, ensure_ascii=False, indent=2), flush=True)
            return 0 if result["ready"] else 2
        if args.mode == "validate":
            manifest = validate_package(args.output_dir)
            print(
                json.dumps(
                    {
                        "status": "valid",
                        "output_dir": str(args.output_dir.resolve()),
                        "package_signature": manifest["package_signature"],
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                flush=True,
            )
            return 0
        result = build_checkpoint(
            campaign_root=args.campaign_root, output_dir=args.output_dir
        )
        print(json.dumps(result, ensure_ascii=False, indent=2), flush=True)
        return 0
    except CheckpointNotReady as exc:
        print(
            json.dumps(
                {"status": "not_ready", "message_fr": str(exc)},
                ensure_ascii=False,
                indent=2,
            ),
            flush=True,
        )
        return 2
    except (CheckpointError, FileNotFoundError, OSError) as exc:
        print(
            json.dumps(
                {"status": "failed_closed", "message_fr": str(exc)},
                ensure_ascii=False,
                indent=2,
            ),
            flush=True,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
