#!/usr/bin/env python3
"""Fail-closed common contract for the corrected additive V8 Stage2 V3.

V3 does not mutate or extend the frozen Stage2 V2 source glob.  Its source
inventory names every V3 module explicitly and binds the unchanged V2 source
inventory as predecessor evidence.  The only scientific correction is the
native V8 target-registry reader used by both upstream validation and delivery.
"""

from __future__ import annotations

import json
import os
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from pathlib import Path
from typing import Any, BinaryIO

from etudecas.prototypes.scan_2027_risk_control import (
    supplier_v8_stage2_common as predecessor,
)
from etudecas.prototypes.scan_2027_risk_control import (
    supplier_v8_stage3_dashboard as dashboard_v8,
)


SCHEMA_VERSION = "etudecas.supplier_v8_stage3.v1"
SOURCE_INVENTORY_SCHEMA_VERSION = f"{SCHEMA_VERSION}.source_inventory.v1"
UPSTREAM_SCHEMA_VERSION = f"{SCHEMA_VERSION}.upstream_validation.v1"
STAGE1_RECEIPT_NAME = "stage1_validation_v8_stage3.json"
PREDECESSOR_INVENTORY_SIGNATURE = (
    "02ed2e5b92828732aec51b4322596e99c3fbaa9ec771e89c3be8cf9011f8191a"
)
EXPLICIT_SOURCE_FILENAMES = (
    "supplier_v8_stage3_common.py",
    "supplier_v8_stage3_dashboard.py",
    "supplier_v8_stage3_pipeline.py",
    "supplier_v8_stage3_delivery.py",
    "supplier_v8_stage3_watcher.py",
)

# Stable public mechanics and domain constants remain aliases, not copies.
Stage2Paths = predecessor.Stage2Paths
Stage2Error = predecessor.Stage2Error
Stage2ScientificNoGo = predecessor.Stage2ScientificNoGo
Stage2NotReady = predecessor.Stage2NotReady
EXPECTED_PROTOCOL_SHA256 = predecessor.EXPECTED_PROTOCOL_SHA256
EXPECTED_STATES = predecessor.EXPECTED_STATES
EXPECTED_MECHANISMS = predecessor.EXPECTED_MECHANISMS
EXPECTED_VALIDATION_SEEDS = predecessor.EXPECTED_VALIDATION_SEEDS
EXPECTED_VALIDATION_CASES = predecessor.EXPECTED_VALIDATION_CASES
EXPECTED_CAMPAIGN_SEEDS = predecessor.EXPECTED_CAMPAIGN_SEEDS
EXPECTED_BASELINES = predecessor.EXPECTED_BASELINES
EXPECTED_INCIDENTS = predecessor.EXPECTED_INCIDENTS
EXPECTED_CAMPAIGN_ROWS = predecessor.EXPECTED_CAMPAIGN_ROWS
EXPECTED_LANES = predecessor.EXPECTED_LANES
MAX_DETAILED_DOSSIERS = predecessor.MAX_DETAILED_DOSSIERS
ALLOWED_ACTIONS = predecessor.ALLOWED_ACTIONS
FORBIDDEN_INCIDENT_FLAGS = predecessor.FORBIDDEN_INCIDENT_FLAGS
PACKAGE_PREFIX = predecessor.PACKAGE_PREFIX
SHA256_RE = predecessor.SHA256_RE

utc_now = predecessor.utc_now
canonical_json_bytes = predecessor.canonical_json_bytes
stable_sha256 = predecessor.stable_sha256
sha256_file = predecessor.sha256_file
signed = predecessor.signed
verify_signature = predecessor.verify_signature
atomic_write_json = predecessor.atomic_write_json
publish_new_or_identical = predecessor.publish_new_or_identical
paths_overlap = predecessor.paths_overlap
exclusive_lock = predecessor.exclusive_lock
finite_number = predecessor.finite_number
_read_csv = predecessor._read_csv
validate_observed_2025_pack = predecessor.validate_observed_2025_pack


@contextmanager
def _open_binary_shared(path: Path) -> Iterator[BinaryIO]:
    """Open while requesting Windows read/write/delete sharing."""

    resolved = path.resolve()
    if os.name != "nt":
        with resolved.open("rb") as stream:
            yield stream
        return

    import ctypes
    import msvcrt
    from ctypes import wintypes

    create_file = ctypes.WinDLL("kernel32", use_last_error=True).CreateFileW
    create_file.argtypes = (
        wintypes.LPCWSTR,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.LPVOID,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.HANDLE,
    )
    create_file.restype = wintypes.HANDLE
    handle = create_file(
        str(resolved),
        0x80000000,  # GENERIC_READ
        0x00000001 | 0x00000002 | 0x00000004,  # SHARE_READ|WRITE|DELETE
        None,
        3,  # OPEN_EXISTING
        0x00000080,  # FILE_ATTRIBUTE_NORMAL
        None,
    )
    invalid_handle = ctypes.c_void_p(-1).value
    if handle == invalid_handle:
        error = ctypes.get_last_error()
        raise OSError(error, os.strerror(error), str(resolved))
    try:
        descriptor = msvcrt.open_osfhandle(
            int(handle), os.O_RDONLY | getattr(os, "O_BINARY", 0)
        )
    except Exception:
        ctypes.WinDLL("kernel32", use_last_error=True).CloseHandle(handle)
        raise
    with os.fdopen(descriptor, "rb") as stream:
        yield stream


def _read_bytes_shared(path: Path) -> bytes:
    with _open_binary_shared(path) as stream:
        return stream.read()


def read_json(path: Path) -> dict[str, Any]:
    """Read one JSON snapshot without intentionally denying writer sharing."""

    try:
        payload = json.loads(_read_bytes_shared(path).decode("utf-8-sig"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise Stage2Error(f"JSON Stage2 V3 illisible : {path.resolve()}") from exc
    if not isinstance(payload, dict):
        raise Stage2Error(f"Objet JSON Stage2 V3 attendu : {path.resolve()}")
    return payload


def source_paths(repo: Path) -> list[Path]:
    """Return the explicit V3 roots and their local transitive dependencies."""

    root = repo.resolve()
    directory = Path(__file__).resolve().parent
    stage3_roots = {directory / filename for filename in EXPLICIT_SOURCE_FILENAMES}
    missing = sorted(str(path) for path in stage3_roots if not path.is_file())
    if missing:
        raise Stage2Error("Sources V3 absentes : " + ", ".join(missing))
    discovered = predecessor._transitive_source_paths(stage3_roots, root)  # noqa: SLF001
    for path in discovered:
        if not path.is_file() or not path.is_relative_to(root):
            raise Stage2Error(f"Source V3 hors dépôt ou absente : {path}")
    return discovered


def _predecessor_inventory(repo: Path) -> dict[str, Any]:
    inventory = predecessor.build_source_inventory(repo)
    predecessor.verify_source_inventory(inventory)
    if inventory.get("inventory_signature") != PREDECESSOR_INVENTORY_SIGNATURE:
        raise Stage2Error(
            "Le périmètre Stage2 V2 figé a changé; V3 refuse de masquer cette dérive."
        )
    return inventory


def build_source_inventory(repo: Path) -> dict[str, Any]:
    root = repo.resolve()
    previous = _predecessor_inventory(root)
    entries = [
        {
            "relative_path": path.relative_to(root).as_posix(),
            "sha256": sha256_file(path),
            "size_bytes": path.stat().st_size,
        }
        for path in source_paths(root)
    ]
    unsigned = {
        "schema_version": SOURCE_INVENTORY_SCHEMA_VERSION,
        "repo": str(root),
        "entry_count": len(entries),
        "entries": entries,
        "explicit_stage3_source_filenames": list(EXPLICIT_SOURCE_FILENAMES),
        "predecessor_inventory_signature": previous["inventory_signature"],
        "critical_protocol_sha256": EXPECTED_PROTOCOL_SHA256,
        "v8_campaign_runner_sha256": previous["v8_campaign_runner_sha256"],
        "v8_finalizer_sha256": previous["v8_finalizer_sha256"],
        "native_dashboard_schema_version": dashboard_v8.SCHEMA_VERSION,
    }
    return signed(unsigned, "inventory_signature")


def verify_source_inventory(inventory: Mapping[str, Any]) -> None:
    verify_signature(inventory, "inventory_signature", "inventaire source Stage2 V3")
    root = Path(str(inventory.get("repo") or "")).resolve()
    entries = inventory.get("entries")
    if (
        inventory.get("schema_version") != SOURCE_INVENTORY_SCHEMA_VERSION
        or not root.is_dir()
        or not isinstance(entries, list)
        or len(entries) != int(inventory.get("entry_count") or -1)
        or inventory.get("explicit_stage3_source_filenames")
        != list(EXPLICIT_SOURCE_FILENAMES)
        or inventory.get("predecessor_inventory_signature")
        != PREDECESSOR_INVENTORY_SIGNATURE
        or inventory.get("critical_protocol_sha256") != EXPECTED_PROTOCOL_SHA256
        or inventory.get("native_dashboard_schema_version")
        != dashboard_v8.SCHEMA_VERSION
    ):
        raise Stage2Error("Inventaire source Stage2 V3 incomplet.")
    _predecessor_inventory(root)
    seen: set[str] = set()
    for entry in entries:
        if not isinstance(entry, Mapping):
            raise Stage2Error("Entrée d'inventaire Stage2 V3 invalide.")
        relative = str(entry.get("relative_path") or "")
        path = (root / relative).resolve()
        if (
            not relative
            or relative in seen
            or not path.is_relative_to(root)
            or not path.is_file()
            or path.stat().st_size != int(entry.get("size_bytes") or -1)
            or sha256_file(path) != str(entry.get("sha256") or "")
        ):
            raise Stage2Error(f"Source Stage2 V3 modifiée ou absente : {relative}")
        seen.add(relative)
    current = {path.relative_to(root).as_posix() for path in source_paths(root)}
    if current != seen:
        raise Stage2Error("Le périmètre transitif explicite de Stage2 V3 a changé.")


@contextmanager
def _shared_json_binding() -> Iterator[None]:
    previous_reader = predecessor.read_json
    predecessor.read_json = read_json
    try:
        yield
    finally:
        predecessor.read_json = previous_reader


def probe_stage1(paths: Stage2Paths) -> str:
    """Poll upstream at most once per watcher cycle using share-delete reads."""

    with _shared_json_binding():
        return predecessor.probe_stage1(paths)


@contextmanager
def _native_dashboard_binding(paths: Stage2Paths) -> Iterator[Any]:
    """Correct the predecessor read locally and restore it after every call."""

    previous_dashboard = predecessor.dashboard_v7
    reader = dashboard_v8.NativeV8DashboardReader(paths.campaign_root)
    predecessor.dashboard_v7 = reader
    try:
        yield reader
    finally:
        predecessor.dashboard_v7 = previous_dashboard


def validate_complete_stage1(paths: Stage2Paths) -> dict[str, Any]:
    """Validate V8 with the native registry reader, never a V4 projection."""

    resolved = paths.resolved()
    with _shared_json_binding(), _native_dashboard_binding(resolved) as reader:
        base = predecessor.validate_complete_stage1(resolved)
    evidence = reader.last_evidence
    if (
        not isinstance(evidence, Mapping)
        or evidence.get("registry_schema_version")
        != dashboard_v8.campaign_v8.TARGET_REGISTRY_SCHEMA_VERSION
        or evidence.get("target_cell_count") != 1_620
        or evidence.get("lane_count") != EXPECTED_LANES
        or evidence.get("seed_count") != EXPECTED_CAMPAIGN_SEEDS
        or evidence.get("required_comparable_seed_count") != EXPECTED_CAMPAIGN_SEEDS
        or evidence.get("incident_outcomes_used") is not False
        or evidence.get("target_selection_engine_runs") != 0
    ):
        raise Stage2Error("Le lecteur dashboard V8 natif n'a pas validé le registre.")
    unsigned = {
        key: value for key, value in base.items() if key != "validation_signature"
    }
    unsigned["schema_version"] = UPSTREAM_SCHEMA_VERSION
    unsigned["status"] = "complete_validated_v8_native_registry"
    unsigned["native_dashboard_contract"] = {
        "schema_version": dashboard_v8.SCHEMA_VERSION,
        "registry_schema_version": evidence["registry_schema_version"],
        "registry_signature": evidence["registry_signature"],
        "registry_sha256": evidence["registry_sha256"],
        "target_cell_count": evidence["target_cell_count"],
        "same_lane_window_across_all_states_and_seeds": True,
        "required_comparable_seed_count": EXPECTED_CAMPAIGN_SEEDS,
        "obsolete_design_seed_projection_used": False,
        "incident_outcomes_used": False,
        "target_selection_engine_runs": 0,
    }
    return signed(unsigned, "validation_signature")


def validate_bound_stage1_receipt(
    paths: Stage2Paths, receipt_path: Path
) -> dict[str, Any]:
    receipt = read_json(receipt_path.resolve())
    verify_signature(receipt, "validation_signature", "reçu figé Stage2 V3")
    if (
        receipt.get("schema_version") != UPSTREAM_SCHEMA_VERSION
        or receipt.get("status") != "complete_validated_v8_native_registry"
        or (receipt.get("native_dashboard_contract") or {}).get(
            "obsolete_design_seed_projection_used"
        )
        is not False
    ):
        raise Stage2Error("Le reçu figé Stage2 V3 est invalide.")
    current = validate_complete_stage1(paths)
    if receipt != current:
        raise Stage2Error("Les preuves V8 ont changé après la validation Stage2 V3.")
    return receipt


@contextmanager
def v8_consumer_bindings() -> Iterator[None]:
    with predecessor.v8_consumer_bindings():
        yield
