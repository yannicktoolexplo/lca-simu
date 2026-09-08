#!/usr/bin/env python3
"""Qualify the physical scope of V5 supplier-campaign evidence.

V5 deliberately reuses the frozen V4 incident campaign and lot-replay
machinery.  In those artifacts, ``incident_physically_exercised`` proves that
an acute risk was applied to at least one positive supplier shipment.  It does
not, by itself, prove a stock -> MRP -> production -> service cascade.

This additive module never launches the simulation engine and never modifies
V4 artifacts.  It provides two fail-closed validators:

* :func:`validate_selected_dossiers_physically_exercised` checks that every
  signed replay selection is backed by a positive, risk-applied campaign
  shipment;
* :func:`validate_replay_dossiers_physically_exercised` checks the finalized
  replay and re-counts its inventoried native genealogy files.

The resulting deterministic sidecar distinguishes three evidence levels:

``not_exercised``
    no positive risk-applied supplier shipment is proved;
``partial``
    the incident shipment is exercised, but at least one downstream native
    genealogy stage is absent;
``complete``
    shipment, material receipt, consumption/WIP, finished lot and aggregated
    client contact are all non-empty.

Even ``complete`` is explicitly scoped to a native lot-contact trace.  The V4
replay contract has no signed MRP-response trace, so this module never grants a
"complete dynamic stock-MRP-production-service cascade" claim.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import math
import os
import re
import uuid
from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from etudecas.prototypes.scan_2027_risk_control import (
    supplier_priority_lot_replay_v4 as replay_v4,
)


SCHEMA_VERSION = "etudecas.supplier_physical_cascade_qualification.v5"
PAYLOAD_SCHEMA_VERSION = f"{SCHEMA_VERSION}.payload.v1"
MANIFEST_SCHEMA_VERSION = f"{SCHEMA_VERSION}.manifest.v1"

PAYLOAD_FILE = "physical_cascade_qualification_v5.json"
LANE_TABLE_FILE = "physical_cascade_qualification_v5.csv"
MANIFEST_FILE = "physical_cascade_qualification_v5.manifest.json"

EXPECTED_LANE_COUNT = 18
EXPECTED_OPERATING_POINT_COUNT = 3
EXPECTED_MECHANISM_COUNT = 2
EXPECTED_REPETITION_COUNT = 30
EXPECTED_INCIDENT_ROWS_PER_LANE = (
    EXPECTED_OPERATING_POINT_COUNT
    * EXPECTED_MECHANISM_COUNT
    * EXPECTED_REPETITION_COUNT
)
MAX_REPLAY_DOSSIERS = 3

EXPECTED_ACTIVE_DYNAMIC_PAIRS = frozenset(
    {
        "M-1810|item:338929",
        "M-1430|item:344135",
    }
)
EXPECTED_CONFIGURED_DYNAMIC_PAIRS = frozenset(
    {
        *EXPECTED_ACTIVE_DYNAMIC_PAIRS,
        "SDC-1450|item:021081",
    }
)

PROOF_LEVELS = frozenset({"not_exercised", "partial", "complete"})
PROOF_ORDER = {"not_exercised": 0, "partial": 1, "complete": 2}
REQUIRED_TRACE_COUNT_FIELDS = (
    "shipments",
    "material_receipts",
    "consumptions",
    "campaigns",
    "batches",
    "finished_lots",
    "client_events",
)


class PhysicalCascadeQualificationError(ValueError):
    """Raised when a V5 physical-scope qualification cannot be proved."""


@dataclass(frozen=True)
class CampaignContext:
    campaign_root: Path
    results_dir: Path
    manifest_path: Path
    manifest: dict[str, Any]
    validation_path: Path
    validation: dict[str, Any]
    selection_path: Path
    selection: dict[str, Any]
    metric_paths: tuple[Path, ...]
    metrics: tuple[dict[str, str], ...]
    lanes: tuple[dict[str, Any], ...]
    requirement_modes: dict[str, str]
    configured_static_pairs: tuple[str, ...]
    configured_dynamic_pairs: tuple[str, ...]


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
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _is_sha256(value: Any) -> bool:
    return bool(re.fullmatch(r"[0-9a-f]{64}", str(value or "")))


def _read_json(path: Path, *, label: str) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PhysicalCascadeQualificationError(f"Invalid {label}: {path}") from exc
    if not isinstance(payload, dict):
        raise PhysicalCascadeQualificationError(f"{label} must be a JSON object")
    return payload


def _read_csv(path: Path, *, label: str) -> list[dict[str, str]]:
    if not path.is_file():
        raise PhysicalCascadeQualificationError(f"Missing {label}: {path}")
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            if reader.fieldnames is None:
                raise PhysicalCascadeQualificationError(
                    f"{label} has no CSV header: {path}"
                )
            return list(reader)
    except OSError as exc:
        raise PhysicalCascadeQualificationError(f"Cannot read {label}: {path}") from exc


def _truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value or "").strip().casefold() in {"1", "true", "yes", "oui"}


def _as_int(value: Any, *, label: str) -> int:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise PhysicalCascadeQualificationError(f"{label} must be an integer") from exc
    if not math.isfinite(number) or not number.is_integer():
        raise PhysicalCascadeQualificationError(f"{label} must be an integer")
    return int(number)


def _as_float(value: Any, *, label: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise PhysicalCascadeQualificationError(f"{label} must be numeric") from exc
    if not math.isfinite(number):
        raise PhysicalCascadeQualificationError(f"{label} must be finite")
    return number


def _verify_signed_payload(
    payload: Mapping[str, Any], signature_field: str, *, label: str
) -> str:
    unsigned = dict(payload)
    signature = str(unsigned.pop(signature_field, ""))
    if not _is_sha256(signature) or signature != stable_sha256(unsigned):
        raise PhysicalCascadeQualificationError(f"Invalid {label} signature")
    return signature


def _normalize_item_id(value: Any) -> str:
    item = str(value or "").strip()
    if not item:
        raise PhysicalCascadeQualificationError("Empty item identifier")
    return item if item.startswith("item:") else f"item:{item}"


def _pair_key(node_id: Any, item_id: Any) -> str:
    node = str(node_id or "").strip()
    if not node:
        raise PhysicalCascadeQualificationError("Empty node identifier in MRP pair")
    return f"{node}|{_normalize_item_id(item_id)}"


def _parse_pair_spec(value: Any, *, label: str) -> str:
    text = str(value or "").strip()
    if "|" in text:
        parts = text.split("|", 1)
    elif "/" in text:
        parts = text.split("/", 1)
    elif "," in text:
        parts = text.split(",", 1)
    else:
        raise PhysicalCascadeQualificationError(f"Malformed {label}: {text}")
    if len(parts) != 2 or not all(part.strip() for part in parts):
        raise PhysicalCascadeQualificationError(f"Malformed {label}: {text}")
    return _pair_key(parts[0], parts[1])


def _argument_values(args: Sequence[Any], flag: str) -> tuple[str, ...]:
    if not isinstance(args, (list, tuple)) or not all(
        isinstance(value, str) for value in args
    ):
        raise PhysicalCascadeQualificationError("Engine argument list is malformed")
    values: list[str] = []
    index = 0
    while index < len(args):
        value = args[index]
        if value == flag:
            if index + 1 >= len(args) or args[index + 1].startswith("--"):
                raise PhysicalCascadeQualificationError(
                    f"Engine argument {flag} lacks its value"
                )
            values.append(_parse_pair_spec(args[index + 1], label=flag))
            index += 2
            continue
        index += 1
    return tuple(values)


def resolve_lane_requirement_modes(
    *,
    lanes: Sequence[Mapping[str, Any]],
    profile_args: Sequence[str],
    managed_args: Sequence[str],
) -> tuple[dict[str, str], tuple[str, ...], tuple[str, ...]]:
    """Resolve the frozen command's explicit MRP pair modes.

    The engine accumulates static pairs and then removes every explicitly
    dynamic pair.  This helper mirrors that exact precedence without importing
    or executing the simulation engine.
    """

    static_pairs = set(_argument_values(profile_args, "--mrp-static-requirement-pair"))
    static_pairs.update(_argument_values(managed_args, "--mrp-static-requirement-pair"))
    dynamic_pairs = set(
        _argument_values(profile_args, "--mrp-dynamic-requirement-pair")
    )
    dynamic_pairs.update(
        _argument_values(managed_args, "--mrp-dynamic-requirement-pair")
    )
    static_pairs.difference_update(dynamic_pairs)

    if dynamic_pairs != set(EXPECTED_CONFIGURED_DYNAMIC_PAIRS):
        raise PhysicalCascadeQualificationError(
            "The V5/V4 command no longer has the frozen three-pair dynamic MRP scope"
        )

    modes: dict[str, str] = {}
    active_dynamic: set[str] = set()
    for lane in lanes:
        lane_id = str(lane.get("lane_id") or "").strip()
        pair = _pair_key(lane.get("dst_node_id"), lane.get("item_id"))
        if not lane_id or lane_id in modes:
            raise PhysicalCascadeQualificationError(
                "Campaign lanes have an empty or duplicate lane_id"
            )
        if pair in dynamic_pairs:
            modes[lane_id] = "dynamic_explicit"
            active_dynamic.add(pair)
        elif pair in static_pairs:
            modes[lane_id] = "static_explicit"
        else:
            raise PhysicalCascadeQualificationError(
                f"Lane {lane_id} has no explicit frozen MRP requirement mode"
            )

    if active_dynamic != set(EXPECTED_ACTIVE_DYNAMIC_PAIRS):
        raise PhysicalCascadeQualificationError(
            "The active 18-lane scope no longer contains exactly the two frozen "
            "dynamic MRP pairs"
        )
    if Counter(modes.values()) != Counter(
        {"dynamic_explicit": 2, "static_explicit": 16}
    ):
        raise PhysicalCascadeQualificationError(
            "The active V5 physical scope must remain 2 dynamic + 16 static lanes"
        )
    return modes, tuple(sorted(static_pairs)), tuple(sorted(dynamic_pairs))


def _safe_relative_file(root: Path, raw: Any, *, label: str) -> Path:
    root = root.resolve()
    text = str(raw or "").strip()
    relative = Path(text)
    if not text or relative.is_absolute() or ".." in relative.parts:
        raise PhysicalCascadeQualificationError(f"Unsafe {label} path: {text}")
    path = (root / relative).resolve()
    if path == root or not path.is_relative_to(root) or not path.is_file():
        raise PhysicalCascadeQualificationError(f"Missing {label}: {text}")
    return path


def _verify_file(path: Path, expected_sha256: Any, *, label: str) -> str:
    expected = str(expected_sha256 or "").casefold()
    if not _is_sha256(expected):
        raise PhysicalCascadeQualificationError(f"Invalid SHA-256 for {label}")
    if not path.is_file():
        raise PhysicalCascadeQualificationError(f"Missing {label}: {path}")
    actual = sha256_file(path)
    if actual != expected:
        raise PhysicalCascadeQualificationError(f"SHA-256 mismatch for {label}")
    return actual


def _load_finalizer_selection_allow_empty(
    *,
    results_dir: Path,
    validation: Mapping[str, Any],
    manifest: Mapping[str, Any],
) -> tuple[dict[str, Any], Path]:
    path = (results_dir / "lot_replay_plan.json").resolve()
    payload = _read_json(path, label="signed finalizer replay selection")
    if payload.get("schema_version") != (
        "etudecas.supplier_operating_point_full_campaign.v4.lot_replay_selection.v1"
    ):
        raise PhysicalCascadeQualificationError("Unexpected replay-selection schema")
    if payload.get("status") != "complete_selected":
        raise PhysicalCascadeQualificationError("Replay selection is not complete")
    _verify_signed_payload(payload, "selection_signature", label="replay selection")
    if payload.get("campaign_signature") != manifest.get(
        "campaign_signature"
    ) or payload.get("engine_sha256") != manifest.get("engine_sha256"):
        raise PhysicalCascadeQualificationError(
            "Replay selection does not belong to the finalized campaign"
        )
    contract = payload.get("selection_contract")
    if not isinstance(contract, Mapping):
        raise PhysicalCascadeQualificationError("Replay-selection contract is absent")
    for field, expected in (
        ("evidence_paths_relative_to_campaign_root", True),
        ("risk_paths_relative_to_campaign_root", True),
        ("mechanisms_kept_separate", True),
        ("quality_included", False),
        ("state_dependent_supplier_risks_enabled", False),
        ("replay_executes_simulation", False),
        ("forced_top3", False),
    ):
        if contract.get(field) is not expected:
            raise PhysicalCascadeQualificationError(
                f"Replay-selection contract changed: {field}"
            )
    if _as_int(contract.get("maximum_dossiers"), label="maximum dossiers") != 3:
        raise PhysicalCascadeQualificationError("Replay-selection maximum changed")

    dossiers = payload.get("selected_dossiers")
    if not isinstance(dossiers, list) or len(dossiers) > MAX_REPLAY_DOSSIERS:
        raise PhysicalCascadeQualificationError("Replay selection is outside 0..3")
    if any(not isinstance(item, Mapping) for item in dossiers):
        raise PhysicalCascadeQualificationError("Malformed selected replay dossier")

    declared = (validation.get("outputs") or {}).get(path.name)
    if not isinstance(declared, Mapping):
        declared = validation.get("lot_replay_plan")
    if not isinstance(declared, Mapping):
        raise PhysicalCascadeQualificationError(
            "Campaign validation does not bind the replay selection"
        )
    if str(declared.get("path") or path.name) != path.name:
        raise PhysicalCascadeQualificationError("Replay-selection path binding changed")
    _verify_file(path, declared.get("sha256"), label="replay selection")
    if _as_int(declared.get("row_count"), label="selected dossier count") != len(
        dossiers
    ) or declared.get("selection_signature") != payload.get("selection_signature"):
        raise PhysicalCascadeQualificationError(
            "Replay-selection count or signature binding changed"
        )
    return payload, path


def _load_campaign_context(campaign_root: Path, results_dir: Path) -> CampaignContext:
    campaign_root = campaign_root.resolve()
    results_dir = results_dir.resolve()
    manifest_path = campaign_root / "campaign_manifest.json"
    validation_path = results_dir / "campaign_validation.json"
    try:
        manifest = replay_v4._verify_campaign_manifest(  # noqa: SLF001
            manifest_path
        )
        validation, _priority_path, metric_paths = replay_v4._validate_campaign_results(  # noqa: SLF001
            campaign_root=campaign_root,
            results_dir=results_dir,
            manifest_path=manifest_path,
            manifest=manifest,
        )
        metrics = replay_v4._load_metric_rows(metric_paths)  # noqa: SLF001
    except Exception as exc:
        raise PhysicalCascadeQualificationError(
            "The finalized V4 campaign inputs do not revalidate"
        ) from exc

    selection, selection_path = _load_finalizer_selection_allow_empty(
        results_dir=results_dir,
        validation=validation,
        manifest=manifest,
    )
    raw_lanes = manifest.get("lanes")
    if not isinstance(raw_lanes, list) or len(raw_lanes) != EXPECTED_LANE_COUNT:
        raise PhysicalCascadeQualificationError("Campaign does not contain 18 lanes")
    lanes: list[dict[str, Any]] = []
    lane_ids: set[str] = set()
    lane_identities: set[tuple[str, ...]] = set()
    for raw in raw_lanes:
        if not isinstance(raw, Mapping):
            raise PhysicalCascadeQualificationError("Malformed campaign lane")
        lane = dict(raw)
        fields = (
            "lane_id",
            "supplier_id",
            "item_id",
            "dst_node_id",
            "edge_id",
            "target_product_id",
        )
        identity = tuple(str(lane.get(field) or "").strip() for field in fields)
        if not all(identity) or identity[0] in lane_ids or identity in lane_identities:
            raise PhysicalCascadeQualificationError(
                "Campaign lane identities are incomplete or duplicated"
            )
        lane_ids.add(identity[0])
        lane_identities.add(identity)
        lanes.append(lane)

    profile_path = replay_v4._resolve_declared_path(  # noqa: SLF001
        manifest.get("engine_profile"), (campaign_root,), "engine profile"
    )
    _verify_file(
        profile_path,
        manifest.get("engine_profile_sha256"),
        label="engine profile",
    )
    profile = _read_json(profile_path, label="engine profile")
    profile_args = profile.get("args")
    managed_args = manifest.get("managed_engine_args")
    if not isinstance(profile_args, list) or not isinstance(managed_args, list):
        raise PhysicalCascadeQualificationError("Engine arguments are absent")
    modes, static_pairs, dynamic_pairs = resolve_lane_requirement_modes(
        lanes=lanes,
        profile_args=profile_args,
        managed_args=managed_args,
    )
    return CampaignContext(
        campaign_root=campaign_root,
        results_dir=results_dir,
        manifest_path=manifest_path,
        manifest=manifest,
        validation_path=validation_path,
        validation=validation,
        selection_path=selection_path,
        selection=selection,
        metric_paths=tuple(Path(path).resolve() for path in metric_paths),
        metrics=tuple(dict(row) for row in metrics),
        lanes=tuple(sorted(lanes, key=lambda row: str(row["lane_id"]))),
        requirement_modes=modes,
        configured_static_pairs=static_pairs,
        configured_dynamic_pairs=dynamic_pairs,
    )


def _campaign_exercise_by_lane(
    context: CampaignContext,
) -> dict[str, dict[str, Any]]:
    lane_by_id = {str(lane["lane_id"]): lane for lane in context.lanes}
    states = {
        str(row.get("operating_point_id") or "")
        for row in context.manifest.get("states") or []
        if isinstance(row, Mapping)
    }
    mechanisms = {
        str(row.get("key") or "")
        for row in context.manifest.get("mechanisms") or []
        if isinstance(row, Mapping)
    }
    seeds = {
        _as_int(value, label="campaign seed")
        for value in context.manifest.get("seeds") or []
    }
    if (
        len(states) != EXPECTED_OPERATING_POINT_COUNT
        or len(mechanisms) != EXPECTED_MECHANISM_COUNT
        or len(seeds) != EXPECTED_REPETITION_COUNT
    ):
        raise PhysicalCascadeQualificationError(
            "Campaign state/mechanism/repetition scope is not 3 x 2 x 30"
        )

    incident_rows = [
        row for row in context.metrics if str(row.get("stage") or "") == "incident"
    ]
    expected_total = EXPECTED_LANE_COUNT * EXPECTED_INCIDENT_ROWS_PER_LANE
    if len(incident_rows) != expected_total:
        raise PhysicalCascadeQualificationError(
            f"Expected {expected_total} incident metrics, found {len(incident_rows)}"
        )

    seen: set[tuple[str, str, str, int]] = set()
    rows_by_lane: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in incident_rows:
        lane_id = str(row.get("lane_id") or "")
        point_id = str(row.get("operating_point_id") or "")
        mechanism = str(row.get("mechanism") or "")
        seed = _as_int(row.get("seed"), label="incident seed")
        key = (lane_id, point_id, mechanism, seed)
        if (
            lane_id not in lane_by_id
            or point_id not in states
            or mechanism not in mechanisms
            or seed not in seeds
            or key in seen
        ):
            raise PhysicalCascadeQualificationError(
                "Incident metric matrix has an unknown or duplicate identity"
            )
        seen.add(key)
        lane = lane_by_id[lane_id]
        for field in (
            "supplier_id",
            "item_id",
            "dst_node_id",
            "edge_id",
            "target_product_id",
        ):
            if str(row.get(field) or "") != str(lane.get(field) or ""):
                raise PhysicalCascadeQualificationError(
                    f"Incident metric lane identity differs for {lane_id}: {field}"
                )
        exercised = _truthy(row.get("incident_physically_exercised"))
        if not _truthy(row.get("valid")):
            raise PhysicalCascadeQualificationError(
                f"Incident metric is not valid: {row.get('case_key') or key}"
            )
        expected_status = "valid" if exercised else "valid_no_exposure"
        if str(row.get("status") or "") != expected_status:
            raise PhysicalCascadeQualificationError(
                "Incident exercise flag and validation status disagree"
            )
        applied_rows = _as_int(
            row.get("risk_applied_row_count"), label="risk-applied row count"
        )
        applied_events = _as_int(
            row.get("risk_applied_event_count"), label="risk-applied event count"
        )
        if exercised:
            if applied_rows < 1 or applied_events < 1:
                raise PhysicalCascadeQualificationError(
                    "Exercised incident lacks a positive risk-application trace"
                )
        elif applied_rows != 0 or applied_events != 0:
            raise PhysicalCascadeQualificationError(
                "Non-exercised incident carries a risk-application trace"
            )
        rows_by_lane[lane_id].append(row)

    result: dict[str, dict[str, Any]] = {}
    for lane_id in sorted(lane_by_id):
        rows = rows_by_lane.get(lane_id, [])
        if len(rows) != EXPECTED_INCIDENT_ROWS_PER_LANE:
            raise PhysicalCascadeQualificationError(
                f"Lane {lane_id} does not have 180 incident repetitions"
            )
        exercised_count = sum(
            _truthy(row.get("incident_physically_exercised")) for row in rows
        )
        cells: list[dict[str, Any]] = []
        for point_id in sorted(states):
            for mechanism in sorted(mechanisms):
                cell = [
                    row
                    for row in rows
                    if str(row.get("operating_point_id") or "") == point_id
                    and str(row.get("mechanism") or "") == mechanism
                ]
                if len(cell) != EXPECTED_REPETITION_COUNT:
                    raise PhysicalCascadeQualificationError(
                        f"Lane {lane_id} has an incomplete 30-seed cell"
                    )
                cell_exercised = sum(
                    _truthy(row.get("incident_physically_exercised")) for row in cell
                )
                cells.append(
                    {
                        "operating_point_id": point_id,
                        "mechanism": mechanism,
                        "incident_run_count": len(cell),
                        "shipment_exercised_run_count": cell_exercised,
                    }
                )
        result[lane_id] = {
            "incident_run_count": len(rows),
            "shipment_exercised_run_count": exercised_count,
            "shipment_not_exercised_run_count": len(rows) - exercised_count,
            "shipment_exercise_rate": exercised_count / len(rows),
            "cells": cells,
        }
    return result


def _metric_index(context: CampaignContext) -> dict[str, dict[str, str]]:
    index: dict[str, dict[str, str]] = {}
    for row in context.metrics:
        case_key = str(row.get("case_key") or "")
        if not case_key or case_key in index:
            raise PhysicalCascadeQualificationError(
                "Campaign metric case keys are empty or duplicated"
            )
        index[case_key] = row
    return index


def _selection_identity(item: Mapping[str, Any]) -> tuple[str, str, str]:
    return (
        str(item.get("operating_point_id") or ""),
        str(item.get("mechanism") or ""),
        str(item.get("lane_id") or ""),
    )


def _validated_selected_dossier(
    *,
    context: CampaignContext,
    selected: Mapping[str, Any],
    metric_index: Mapping[str, Mapping[str, str]],
    lane_by_id: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    dossier_id = str(selected.get("dossier_id") or "")
    point_id, mechanism, lane_id = _selection_identity(selected)
    if not dossier_id or not all((point_id, mechanism, lane_id)):
        raise PhysicalCascadeQualificationError(
            "Selected dossier identity is incomplete"
        )
    lane = lane_by_id.get(lane_id)
    if lane is None:
        raise PhysicalCascadeQualificationError(
            f"Selected dossier references an unknown lane: {lane_id}"
        )
    if mechanism not in replay_v4.ALLOWED_MECHANISMS:
        raise PhysicalCascadeQualificationError(
            f"Selected dossier has an unsupported mechanism: {mechanism}"
        )
    if str(selected.get("priority_status") or "") not in replay_v4.PRIORITY_STATUSES:
        raise PhysicalCascadeQualificationError(
            "Selected dossier is not a validated priority signal"
        )
    for field in (
        "supplier_id",
        "item_id",
        "dst_node_id",
        "edge_id",
        "target_product_id",
    ):
        if str(selected.get(field) or "") != str(lane.get(field) or ""):
            raise PhysicalCascadeQualificationError(
                f"Selected dossier lane identity differs: {dossier_id}/{field}"
            )

    incident_case_key = str(selected.get("incident_case_key") or "")
    metric = metric_index.get(incident_case_key)
    if metric is None:
        raise PhysicalCascadeQualificationError(
            f"Selected dossier metric is absent: {dossier_id}"
        )
    seed = _as_int(selected.get("representative_seed"), label="representative seed")
    if (
        str(metric.get("stage") or "") != "incident"
        or _selection_identity(metric) != (point_id, mechanism, lane_id)
        or _as_int(metric.get("seed"), label="selected metric seed") != seed
        or str(metric.get("case_signature") or "")
        != str(selected.get("incident_case_signature") or "")
        or not _truthy(metric.get("valid"))
        or str(metric.get("status") or "") != "valid"
        or not _truthy(metric.get("incident_physically_exercised"))
        or _as_int(
            metric.get("risk_applied_row_count"), label="selected risk-applied rows"
        )
        < 1
        or _as_int(
            metric.get("risk_applied_event_count"), label="selected risk-applied events"
        )
        < 1
    ):
        raise PhysicalCascadeQualificationError(
            f"Selected dossier metric is not physically exercised: {dossier_id}"
        )

    exercised_seed_count = _as_int(
        selected.get("valid_exercised_seed_count"),
        label="selected exercised-seed count",
    )
    if not 1 <= exercised_seed_count <= EXPECTED_REPETITION_COUNT:
        raise PhysicalCascadeQualificationError(
            f"Selected dossier has no exercised representative cohort: {dossier_id}"
        )

    incident_path = _safe_relative_file(
        context.campaign_root,
        selected.get("incident_evidence_path"),
        label="incident evidence",
    )
    _verify_file(
        incident_path,
        selected.get("incident_evidence_sha256"),
        label="selected incident evidence",
    )
    try:
        evidence = replay_v4._validate_case_evidence(  # noqa: SLF001
            incident_path,
            manifest=context.manifest,
            metric_row=metric,
        )
    except Exception as exc:
        raise PhysicalCascadeQualificationError(
            f"Selected incident evidence does not revalidate: {dossier_id}"
        ) from exc
    evidence_lane = evidence.get("lane")
    proof = evidence.get("incident_proof")
    metrics = evidence.get("metrics")
    if (
        not isinstance(evidence_lane, Mapping)
        or not isinstance(proof, Mapping)
        or not isinstance(metrics, Mapping)
    ):
        raise PhysicalCascadeQualificationError(
            f"Selected incident evidence is structurally incomplete: {dossier_id}"
        )
    for field in (
        "lane_id",
        "supplier_id",
        "item_id",
        "dst_node_id",
        "edge_id",
        "target_product_id",
    ):
        expected = lane_id if field == "lane_id" else str(lane.get(field) or "")
        if str(evidence_lane.get(field) or "") != expected:
            raise PhysicalCascadeQualificationError(
                f"Selected evidence lane identity differs: {dossier_id}/{field}"
            )

    tagged_count = _as_int(
        proof.get("tagged_shipment_row_count"), label="tagged shipment row count"
    )
    incident_shipment_count = _as_int(
        proof.get("incident_shipment_count"), label="incident shipment count"
    )
    applied_proof_rows = proof.get("applied_rows")
    stressed_ids = proof.get("stressed_shipment_ids")
    if (
        proof.get("incident_physically_exercised") is not True
        or tagged_count < 1
        or incident_shipment_count < 1
        or tagged_count != incident_shipment_count
        or not isinstance(applied_proof_rows, list)
        or not applied_proof_rows
        or not isinstance(stressed_ids, list)
        or len(stressed_ids) != tagged_count
        or any(not str(value or "").strip() for value in stressed_ids)
        or _as_int(
            metrics.get("risk_applied_row_count"), label="evidence risk-applied rows"
        )
        < 1
        or _as_int(
            metrics.get("risk_applied_event_count"),
            label="evidence risk-applied events",
        )
        < 1
    ):
        raise PhysicalCascadeQualificationError(
            f"Selected evidence does not prove a risk-applied shipment: {dossier_id}"
        )
    if mechanism == "transport_delay":
        if (
            _as_float(
                proof.get("incident_affected_shipped_qty"),
                label="affected shipped quantity",
            )
            <= 0.0
            or _as_int(proof.get("arrival_delay_days"), label="arrival delay") != 120
        ):
            raise PhysicalCascadeQualificationError(
                f"Selected delay dossier has no positive +120-day dose: {dossier_id}"
            )
    else:
        if (
            _as_float(proof.get("quantity_shortfall_qty"), label="quantity shortfall")
            <= 0.0
        ):
            raise PhysicalCascadeQualificationError(
                f"Selected shortfall dossier has no positive physical dose: {dossier_id}"
            )

    risk_path = _safe_relative_file(
        context.campaign_root,
        selected.get("risk_csv_path"),
        label="selected incident risk CSV",
    )
    risk_sha = _verify_file(
        risk_path,
        selected.get("risk_csv_sha256"),
        label="selected incident risk CSV",
    )
    if str(evidence.get("risk_csv_sha256") or "") != risk_sha:
        raise PhysicalCascadeQualificationError(
            f"Selected risk CSV and incident evidence differ: {dossier_id}"
        )
    return {
        "dossier_id": dossier_id,
        "operating_point_id": point_id,
        "mechanism": mechanism,
        "lane_id": lane_id,
        "representative_seed": seed,
        "valid_exercised_seed_count": exercised_seed_count,
        "incident_case_key": incident_case_key,
        "incident_case_signature": str(selected["incident_case_signature"]),
        "incident_evidence_sha256": sha256_file(incident_path),
        "risk_csv_sha256": risk_sha,
        "tagged_shipment_count": tagged_count,
        "risk_applied_row_count": _as_int(
            metrics.get("risk_applied_row_count"), label="evidence risk-applied rows"
        ),
        "risk_applied_event_count": _as_int(
            metrics.get("risk_applied_event_count"),
            label="evidence risk-applied events",
        ),
        "campaign_shipment_exercised": True,
    }


def validate_selected_dossiers_physically_exercised(
    *, campaign_root: Path, results_dir: Path
) -> dict[str, Any]:
    """Fail closed unless every signed replay selection has positive exposure."""

    context = _load_campaign_context(campaign_root, results_dir)
    exercise_by_lane = _campaign_exercise_by_lane(context)
    metric_index = _metric_index(context)
    lane_by_id = {str(lane["lane_id"]): lane for lane in context.lanes}
    selected_rows = context.selection.get("selected_dossiers") or []
    identities: set[tuple[str, str, str]] = set()
    dossier_ids: set[str] = set()
    validated: list[dict[str, Any]] = []
    for selected in selected_rows:
        identity = _selection_identity(selected)
        dossier_id = str(selected.get("dossier_id") or "")
        if identity in identities or not all(identity) or dossier_id in dossier_ids:
            raise PhysicalCascadeQualificationError(
                "Selected replay dossiers are empty or duplicated"
            )
        identities.add(identity)
        dossier_ids.add(dossier_id)
        validated.append(
            _validated_selected_dossier(
                context=context,
                selected=selected,
                metric_index=metric_index,
                lane_by_id=lane_by_id,
            )
        )
    return {
        "campaign_signature": str(context.manifest["campaign_signature"]),
        "selection_signature": str(context.selection["selection_signature"]),
        "selected_dossier_count": len(validated),
        "selected_dossiers": sorted(validated, key=lambda row: row["dossier_id"]),
        "campaign_exercise_by_lane": exercise_by_lane,
    }


def _validate_replay_inventory(
    *, replay_root: Path, validation: Mapping[str, Any]
) -> dict[str, Path]:
    final_root = (replay_root / "finalized").resolve()
    inventory_path = Path(str(validation.get("artifact_inventory") or "")).resolve()
    if inventory_path != final_root / "artifact_inventory.csv":
        raise PhysicalCascadeQualificationError(
            "Replay validation points to an unexpected artifact inventory"
        )
    _verify_file(
        inventory_path,
        validation.get("artifact_inventory_sha256"),
        label="replay artifact inventory",
    )
    rows = _read_csv(inventory_path, label="replay artifact inventory")
    if not rows:
        raise PhysicalCascadeQualificationError("Replay artifact inventory is empty")
    paths: dict[str, Path] = {}
    for row in rows:
        relative_text = str(row.get("relative_path") or "").strip()
        relative = Path(relative_text)
        if (
            not relative_text
            or relative.is_absolute()
            or ".." in relative.parts
            or relative_text in paths
        ):
            raise PhysicalCascadeQualificationError(
                "Replay artifact inventory has an unsafe or duplicate path"
            )
        path = (replay_root / relative).resolve()
        if (
            path == replay_root
            or not path.is_relative_to(replay_root)
            or not path.is_file()
        ):
            raise PhysicalCascadeQualificationError(
                f"Replay artifact is missing or outside its root: {relative_text}"
            )
        if path.stat().st_size != _as_int(
            row.get("size_bytes"), label="replay artifact size"
        ):
            raise PhysicalCascadeQualificationError(
                f"Replay artifact size differs: {relative_text}"
            )
        _verify_file(path, row.get("sha256"), label=f"replay artifact {relative_text}")
        paths[relative_text.replace("\\", "/")] = path
    return paths


def _read_trace_rows(
    path: Path, *, label: str, required_fields: Sequence[str]
) -> list[dict[str, str]]:
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            fields = tuple(reader.fieldnames or ())
            if not set(required_fields).issubset(fields):
                raise PhysicalCascadeQualificationError(
                    f"{label} schema is incomplete: {path}"
                )
            return list(reader)
    except OSError as exc:
        raise PhysicalCascadeQualificationError(f"Cannot read {label}: {path}") from exc


def _nonempty_tokens(value: Any) -> tuple[str, ...]:
    return tuple(
        token.strip() for token in re.split(r"[|;,]", str(value or "")) if token.strip()
    )


def _require_positive(value: Any, *, label: str) -> float:
    number = _as_float(value, label=label)
    if number <= 0.0:
        raise PhysicalCascadeQualificationError(f"{label} must be positive")
    return number


def _derive_trace_counts(
    *, dossier_id: str, inventory: Mapping[str, Path]
) -> tuple[dict[str, int], dict[str, Any]]:
    prefix = f"finalized/dossiers/{dossier_id}/"
    names = {
        "shipment": "shipment_to_mp_lots.csv",
        "consumption": "exposed_consumption_wip.csv",
        "finished": "exposed_finished_lots.csv",
        "client": "exposed_client_events.csv",
        "kpis": "dossier_kpis.json",
    }
    required = {key: prefix + name for key, name in names.items()}
    missing = [relative for relative in required.values() if relative not in inventory]
    if missing:
        raise PhysicalCascadeQualificationError(
            f"Replay dossier {dossier_id} lacks inventoried evidence: {missing}"
        )

    shipments = _read_trace_rows(
        inventory[required["shipment"]],
        label="shipment-to-receipt genealogy",
        required_fields=(
            "shipment_id",
            "receipt_lot_id",
            "parent_qty",
            "child_qty",
            "incident_event_id",
        ),
    )
    shipment_ids: set[str] = set()
    receipt_ids: set[str] = set()
    for row in shipments:
        shipment_id = str(row.get("shipment_id") or "").strip()
        receipt_id = str(row.get("receipt_lot_id") or "").strip()
        if (
            not shipment_id
            or not receipt_id
            or not str(row.get("incident_event_id") or "").strip()
        ):
            raise PhysicalCascadeQualificationError(
                f"Replay dossier {dossier_id} has an incomplete shipment/receipt edge"
            )
        _require_positive(row.get("parent_qty"), label="source-lot quantity")
        _require_positive(row.get("child_qty"), label="receipt-lot quantity")
        shipment_ids.add(shipment_id)
        receipt_ids.add(receipt_id)

    consumptions = _read_trace_rows(
        inventory[required["consumption"]],
        label="exposed consumption/WIP genealogy",
        required_fields=(
            "shipment_ids",
            "material_lot_id",
            "consumed_qty",
            "campaign_id",
            "batch_id",
        ),
    )
    campaigns: set[str] = set()
    batches: set[str] = set()
    for row in consumptions:
        if (
            not _nonempty_tokens(row.get("shipment_ids"))
            or not str(row.get("material_lot_id") or "").strip()
        ):
            raise PhysicalCascadeQualificationError(
                f"Replay dossier {dossier_id} has an incomplete consumption edge"
            )
        _require_positive(row.get("consumed_qty"), label="consumed quantity")
        campaign_id = str(row.get("campaign_id") or "").strip()
        batch_id = str(row.get("batch_id") or "").strip()
        if campaign_id:
            campaigns.add(campaign_id)
        if batch_id:
            batches.add(batch_id)

    finished = _read_trace_rows(
        inventory[required["finished"]],
        label="exposed finished-lot genealogy",
        required_fields=(
            "shipment_ids",
            "finished_lot_id",
            "released_qty",
            "campaign_id",
            "claim",
        ),
    )
    for row in finished:
        if (
            not _nonempty_tokens(row.get("shipment_ids"))
            or not str(row.get("finished_lot_id") or "").strip()
            or str(row.get("claim") or "")
            != "native_genealogical_contact_not_cross_arm_identity"
        ):
            raise PhysicalCascadeQualificationError(
                f"Replay dossier {dossier_id} has an incomplete finished-lot edge"
            )
        _require_positive(row.get("released_qty"), label="released finished quantity")

    clients = _read_trace_rows(
        inventory[required["client"]],
        label="exposed aggregated-client genealogy",
        required_fields=(
            "shipment_ids",
            "client_lot_id",
            "client_node_id",
            "service_event_qty_on_contacted_lot",
            "claim",
        ),
    )
    client_nodes: set[str] = set()
    for row in clients:
        client_node = str(row.get("client_node_id") or "").strip()
        if (
            not _nonempty_tokens(row.get("shipment_ids"))
            or not str(row.get("client_lot_id") or "").strip()
            or not client_node
            or str(row.get("claim") or "")
            != "native_genealogical_contact_not_incremental_service_loss"
        ):
            raise PhysicalCascadeQualificationError(
                f"Replay dossier {dossier_id} has an incomplete client-contact edge"
            )
        _require_positive(
            row.get("service_event_qty_on_contacted_lot"),
            label="client-contact service quantity",
        )
        client_nodes.add(client_node)

    kpis = _read_json(inventory[required["kpis"]], label="replay dossier KPIs")
    required_kpis = {
        "first_component_stock_divergence_day",
        "first_production_divergence_day",
        "first_service_divergence_day",
        "service_loss_pp",
        "production_released_loss_qty",
        "cross_arm_lot_matching_used",
    }
    if not required_kpis.issubset(kpis):
        raise PhysicalCascadeQualificationError(
            f"Replay dossier {dossier_id} lacks paired-response KPI fields"
        )
    if kpis.get("cross_arm_lot_matching_used") is not False:
        raise PhysicalCascadeQualificationError(
            f"Replay dossier {dossier_id} used forbidden cross-arm lot matching"
        )
    _as_float(kpis.get("service_loss_pp"), label="replay service loss")
    _as_float(
        kpis.get("production_released_loss_qty"),
        label="replay production loss",
    )
    counts = {
        "shipments": len(shipment_ids),
        "material_receipts": len(receipt_ids),
        "consumptions": len(consumptions),
        "campaigns": len(campaigns),
        "batches": len(batches),
        "finished_lots": len(finished),
        "client_events": len(clients),
        "clients": len(client_nodes),
    }
    return counts, kpis


def _expected_native_trace_status(counts: Mapping[str, int]) -> str:
    if counts["client_events"]:
        return "native_trace_to_client"
    if counts["finished_lots"]:
        return "native_trace_to_finished_product"
    if counts["consumptions"]:
        return "native_trace_to_wip"
    return "native_trace_to_material_receipt_only"


def _qualify_trace_counts(counts: Mapping[str, int]) -> tuple[str, list[str]]:
    if counts.get("shipments", 0) <= 0 or counts.get("material_receipts", 0) <= 0:
        return "not_exercised", [
            field
            for field in ("shipments", "material_receipts")
            if counts.get(field, 0) <= 0
        ]
    missing = [
        field for field in REQUIRED_TRACE_COUNT_FIELDS if counts.get(field, 0) <= 0
    ]
    return ("partial", missing) if missing else ("complete", [])


def _validated_replay_dossier(
    *,
    plan_dossier: Mapping[str, Any],
    replay_validation: Mapping[str, Any],
    inventory: Mapping[str, Path],
    selected: Mapping[str, Any],
    requirement_mode: str,
) -> dict[str, Any]:
    dossier_id = str(plan_dossier.get("dossier_id") or "")
    priority = plan_dossier.get("priority")
    if not dossier_id or not isinstance(priority, Mapping):
        raise PhysicalCascadeQualificationError("Replay plan dossier is malformed")
    if _selection_identity(priority) != (
        str(selected["operating_point_id"]),
        str(selected["mechanism"]),
        str(selected["lane_id"]),
    ):
        raise PhysicalCascadeQualificationError(
            f"Replay plan priority differs from campaign selection: {dossier_id}"
        )
    incident_metric = plan_dossier.get("incident_metric")
    if (
        not isinstance(incident_metric, Mapping)
        or not _truthy(incident_metric.get("incident_physically_exercised"))
        or str(incident_metric.get("status") or "") != "valid"
        or _as_int(
            incident_metric.get("representative_valid_exercised_seed_count"),
            label="replay exercised-seed count",
        )
        != _as_int(
            selected.get("valid_exercised_seed_count"),
            label="selected exercised-seed count",
        )
    ):
        raise PhysicalCascadeQualificationError(
            f"Replay plan lost its exercised campaign repetition: {dossier_id}"
        )

    pair_proof = replay_validation.get("pair_proof")
    incident_pair = (
        pair_proof.get("incident") if isinstance(pair_proof, Mapping) else None
    )
    if (
        not isinstance(incident_pair, Mapping)
        or _as_int(
            incident_pair.get("tagged_shipment_count"),
            label="replay tagged shipment count",
        )
        < 1
    ):
        raise PhysicalCascadeQualificationError(
            f"Replay incident arm is not physically exercised: {dossier_id}"
        )

    counts, kpis = _derive_trace_counts(dossier_id=dossier_id, inventory=inventory)
    declared_counts = replay_validation.get("trace_counts")
    if not isinstance(declared_counts, Mapping):
        raise PhysicalCascadeQualificationError(
            f"Replay trace counts are absent: {dossier_id}"
        )
    for field, actual in counts.items():
        if _as_int(declared_counts.get(field), label=f"declared {field}") != actual:
            raise PhysicalCascadeQualificationError(
                f"Replay trace count differs from inventoried CSV: {dossier_id}/{field}"
            )
    if counts["shipments"] != _as_int(
        incident_pair.get("tagged_shipment_count"),
        label="replay tagged shipment count",
    ):
        raise PhysicalCascadeQualificationError(
            f"Replay tagged shipments and receipt genealogy differ: {dossier_id}"
        )
    expected_status = _expected_native_trace_status(counts)
    if str(replay_validation.get("status") or "") != expected_status:
        raise PhysicalCascadeQualificationError(
            f"Replay native-trace depth is mislabeled: {dossier_id}"
        )
    if (
        replay_validation.get("cross_arm_lot_matching_used") is not False
        or replay_validation.get("quality_incident_included") is not False
        or replay_validation.get("state_dependent_supplier_risks_enabled") is not False
    ):
        raise PhysicalCascadeQualificationError(
            f"Replay dossier scientific exclusions changed: {dossier_id}"
        )

    proof_level, missing = _qualify_trace_counts(counts)
    if proof_level == "not_exercised":
        # Selected dossiers are required to remain physically exercised after replay.
        raise PhysicalCascadeQualificationError(
            f"Replay dossier has no shipment-to-receipt physical exercise: {dossier_id}"
        )
    paired_response = {
        "component_stock_divergence_observed": kpis.get(
            "first_component_stock_divergence_day"
        )
        is not None,
        "production_divergence_observed": kpis.get("first_production_divergence_day")
        is not None,
        "service_divergence_observed": kpis.get("first_service_divergence_day")
        is not None,
        "service_loss_pp": _as_float(
            kpis.get("service_loss_pp"), label="replay service loss"
        ),
        "production_released_loss_qty": _as_float(
            kpis.get("production_released_loss_qty"),
            label="replay production loss",
        ),
    }
    paired_response["stock_production_service_divergence_observed"] = all(
        paired_response[field]
        for field in (
            "component_stock_divergence_observed",
            "production_divergence_observed",
            "service_divergence_observed",
        )
    )
    missing_full_dynamic: list[str] = []
    if requirement_mode != "dynamic_explicit":
        missing_full_dynamic.append("dynamic_mrp_requirement_not_configured")
    # No MRP trace or MRP response file belongs to the frozen V4 replay contract.
    missing_full_dynamic.append("signed_mrp_response_trace_absent")
    if not paired_response["component_stock_divergence_observed"]:
        missing_full_dynamic.append("paired_component_stock_response_absent")
    if not paired_response["production_divergence_observed"]:
        missing_full_dynamic.append("paired_production_response_absent")
    if not paired_response["service_divergence_observed"]:
        missing_full_dynamic.append("paired_service_response_absent")

    display_label = (
        "Trace native complète jusqu’au client agrégé — hors preuve de réponse MRP"
        if proof_level == "complete"
        else "Trace physique partielle — arrêt avant le client agrégé"
    )
    return {
        "dossier_id": dossier_id,
        "operating_point_id": str(selected["operating_point_id"]),
        "mechanism": str(selected["mechanism"]),
        "lane_id": str(selected["lane_id"]),
        "representative_seed": _as_int(
            selected.get("representative_seed"), label="representative seed"
        ),
        "mrp_requirement_mode": requirement_mode,
        "campaign_shipment_exercised": True,
        "replay_shipment_to_receipt_exercised": True,
        "native_trace_status_v4": expected_status,
        "trace_counts": counts,
        "proof_level": proof_level,
        "missing_native_trace_stages": missing,
        "proof_scope": "native_lot_contact_trace_to_aggregated_client",
        "display_label_fr": display_label,
        "paired_response": paired_response,
        "signed_mrp_response_trace_available": False,
        "full_dynamic_stock_mrp_production_service_cascade_proven": False,
        "full_dynamic_cascade_missing_proofs": missing_full_dynamic,
        "complete_cascade_label_allowed": False,
    }


def validate_replay_dossiers_physically_exercised(
    *, campaign_root: Path, results_dir: Path, replay_root: Path | None
) -> dict[str, Any]:
    """Re-count finalized genealogy and reject any unexercised replay dossier."""

    selection_proof = validate_selected_dossiers_physically_exercised(
        campaign_root=campaign_root,
        results_dir=results_dir,
    )
    context = _load_campaign_context(campaign_root, results_dir)
    selected_rows = selection_proof["selected_dossiers"]
    if not selected_rows:
        if replay_root is not None:
            root = replay_root.resolve()
            forbidden = (
                root / "replay_plan.json",
                root / "replay_run_receipt.json",
                root / "finalized" / "replay_validation.json",
            )
            if any(path.exists() for path in forbidden):
                raise PhysicalCascadeQualificationError(
                    "Replay artifacts exist although the signed selection is empty"
                )
        return {
            "plan_signature": "",
            "run_receipt_signature": "",
            "replay_validation_signature": "",
            "replay_validation_sha256": "",
            "dossier_count": 0,
            "dossiers": [],
        }
    if replay_root is None:
        raise PhysicalCascadeQualificationError(
            "A replay root is required for the non-empty signed selection"
        )
    replay_root = replay_root.resolve()
    try:
        plan = replay_v4.load_and_validate_plan(replay_root)
    except Exception as exc:
        raise PhysicalCascadeQualificationError(
            "Replay plan does not revalidate"
        ) from exc
    if (
        plan.get("campaign_signature") != context.manifest.get("campaign_signature")
        or plan.get("campaign_validation_sha256")
        != sha256_file(context.validation_path)
        or Path(str(plan.get("campaign_root") or "")).resolve() != context.campaign_root
        or Path(str(plan.get("results_dir") or "")).resolve() != context.results_dir
    ):
        raise PhysicalCascadeQualificationError(
            "Replay plan does not belong to the current finalized campaign"
        )
    planned = plan.get("dossiers")
    if not isinstance(planned, list) or len(planned) != len(selected_rows):
        raise PhysicalCascadeQualificationError(
            "Replay plan dossier count differs from the signed selection"
        )
    planned_by_id = {
        str(row.get("dossier_id") or ""): row
        for row in planned
        if isinstance(row, Mapping)
    }
    selected_by_id = {str(row["dossier_id"]): row for row in selected_rows}
    if (
        len(planned_by_id) != len(planned)
        or not all(planned_by_id)
        or set(planned_by_id) != set(selected_by_id)
    ):
        raise PhysicalCascadeQualificationError(
            "Replay plan dossier identities differ from the signed selection"
        )

    receipt_path = replay_root / "replay_run_receipt.json"
    receipt = _read_json(receipt_path, label="replay run receipt")
    _verify_signed_payload(receipt, "run_receipt_signature", label="replay run receipt")
    if (
        receipt.get("schema_version") != replay_v4.RUN_RECEIPT_SCHEMA_VERSION
        or receipt.get("status") != "complete_validated"
        or receipt.get("plan_signature") != plan.get("plan_signature")
    ):
        raise PhysicalCascadeQualificationError("Replay run receipt is incoherent")

    validation_path = replay_root / "finalized" / "replay_validation.json"
    validation = _read_json(validation_path, label="finalized replay validation")
    _verify_signed_payload(
        validation, "validation_signature", label="finalized replay validation"
    )
    dossier_validations = validation.get("dossiers")
    if (
        validation.get("schema_version") != replay_v4.VALIDATION_SCHEMA_VERSION
        or validation.get("status") != "complete_validated"
        or validation.get("plan_signature") != plan.get("plan_signature")
        or validation.get("run_receipt_signature")
        != receipt.get("run_receipt_signature")
        or validation.get("lot_identity_contract") != plan.get("lot_identity_contract")
        or not isinstance(dossier_validations, list)
        or len(dossier_validations) != len(planned)
    ):
        raise PhysicalCascadeQualificationError(
            "Finalized replay validation is incoherent"
        )
    validation_by_id = {
        str(row.get("dossier_id") or ""): row
        for row in dossier_validations
        if isinstance(row, Mapping)
    }
    if (
        len(validation_by_id) != len(dossier_validations)
        or not all(validation_by_id)
        or set(validation_by_id) != set(planned_by_id)
    ):
        raise PhysicalCascadeQualificationError(
            "Finalized replay dossier identities are incomplete or duplicated"
        )
    html = Path(str(validation.get("standalone_html") or "")).resolve()
    if (
        not html.is_file()
        or not html.is_relative_to(replay_root)
        or sha256_file(html) != str(validation.get("standalone_html_sha256") or "")
    ):
        raise PhysicalCascadeQualificationError(
            "Finalized replay standalone HTML is absent or modified"
        )
    inventory = _validate_replay_inventory(
        replay_root=replay_root,
        validation=validation,
    )

    qualified: list[dict[str, Any]] = []
    for dossier_id in sorted(planned_by_id):
        lane_id = str(selected_by_id[dossier_id]["lane_id"])
        qualified.append(
            _validated_replay_dossier(
                plan_dossier=planned_by_id[dossier_id],
                replay_validation=validation_by_id[dossier_id],
                inventory=inventory,
                selected=selected_by_id[dossier_id],
                requirement_mode=context.requirement_modes[lane_id],
            )
        )
    return {
        "plan_signature": str(plan["plan_signature"]),
        "run_receipt_signature": str(receipt["run_receipt_signature"]),
        "replay_validation_signature": str(validation["validation_signature"]),
        "replay_validation_sha256": sha256_file(validation_path),
        "dossier_count": len(qualified),
        "dossiers": qualified,
    }


def _display_label_for_lane(
    *, proof_level: str, requirement_mode: str, selected: bool
) -> str:
    if proof_level == "not_exercised":
        return "Incident non exercé physiquement"
    if not selected:
        return "Exposition fournisseur exercée — sans rejeu généalogique détaillé"
    if proof_level == "complete":
        suffix = (
            "besoin MRP dynamique configuré, réponse MRP non tracée"
            if requirement_mode == "dynamic_explicit"
            else "besoin MRP statique"
        )
        return f"Trace native complète jusqu’au client agrégé — {suffix}"
    return "Trace physique partielle — généalogie aval incomplète"


def build_qualification_payload(
    *, campaign_root: Path, results_dir: Path, replay_root: Path | None
) -> dict[str, Any]:
    """Build the deterministic, signed qualification payload in memory."""

    selection = validate_selected_dossiers_physically_exercised(
        campaign_root=campaign_root,
        results_dir=results_dir,
    )
    replay = validate_replay_dossiers_physically_exercised(
        campaign_root=campaign_root,
        results_dir=results_dir,
        replay_root=replay_root,
    )
    context = _load_campaign_context(campaign_root, results_dir)
    replay_by_lane: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for dossier in replay["dossiers"]:
        replay_by_lane[str(dossier["lane_id"])].append(dossier)

    lane_qualifications: list[dict[str, Any]] = []
    for lane in context.lanes:
        lane_id = str(lane["lane_id"])
        exercise = selection["campaign_exercise_by_lane"][lane_id]
        dossiers = sorted(
            replay_by_lane.get(lane_id, []), key=lambda row: str(row["dossier_id"])
        )
        if dossiers:
            proof_level = max(
                (str(row["proof_level"]) for row in dossiers),
                key=PROOF_ORDER.__getitem__,
            )
        elif int(exercise["shipment_exercised_run_count"]) > 0:
            proof_level = "partial"
        else:
            proof_level = "not_exercised"
        requirement_mode = context.requirement_modes[lane_id]
        lane_qualifications.append(
            {
                "lane_id": lane_id,
                "supplier_id": str(lane["supplier_id"]),
                "item_id": str(lane["item_id"]),
                "dst_node_id": str(lane["dst_node_id"]),
                "edge_id": str(lane["edge_id"]),
                "target_product_id": str(lane["target_product_id"]),
                "site_item_pair": _pair_key(lane["dst_node_id"], lane["item_id"]),
                "mrp_requirement_mode": requirement_mode,
                "physical_interpretation": (
                    "dynamic_mrp_requirement_configured_but_response_not_traced"
                    if requirement_mode == "dynamic_explicit"
                    else "downstream_sensitivity_under_static_mrp_requirement"
                ),
                "campaign_incident_run_count": int(exercise["incident_run_count"]),
                "campaign_shipment_exercised_run_count": int(
                    exercise["shipment_exercised_run_count"]
                ),
                "campaign_shipment_not_exercised_run_count": int(
                    exercise["shipment_not_exercised_run_count"]
                ),
                "campaign_shipment_exercise_rate": float(
                    exercise["shipment_exercise_rate"]
                ),
                "campaign_cells": exercise["cells"],
                "selected_dossier_ids": [
                    str(dossier["dossier_id"]) for dossier in dossiers
                ],
                "selected_dossier_proof_levels": [
                    str(dossier["proof_level"]) for dossier in dossiers
                ],
                "proof_level": proof_level,
                "proof_scope": (
                    "best_available_native_lot_trace"
                    if dossiers
                    else "campaign_supplier_shipment_exercise_only"
                ),
                "display_label_fr": _display_label_for_lane(
                    proof_level=proof_level,
                    requirement_mode=requirement_mode,
                    selected=bool(dossiers),
                ),
                "signed_mrp_response_trace_available": False,
                "full_dynamic_stock_mrp_production_service_cascade_proven": False,
                "complete_cascade_label_allowed": False,
            }
        )

    lane_level_counts = Counter(str(row["proof_level"]) for row in lane_qualifications)
    dossier_level_counts = Counter(
        str(row["proof_level"]) for row in replay["dossiers"]
    )
    payload_unsigned: dict[str, Any] = {
        "schema_version": PAYLOAD_SCHEMA_VERSION,
        "status": "complete_qualified",
        "producer": (
            "etudecas.prototypes.scan_2027_risk_control."
            "supplier_physical_cascade_qualification_v5"
        ),
        "producer_sha256": sha256_file(Path(__file__).resolve()),
        "source": {
            "campaign_manifest_sha256": sha256_file(context.manifest_path),
            "campaign_signature": str(context.manifest["campaign_signature"]),
            "campaign_validation_sha256": sha256_file(context.validation_path),
            "selection_sha256": sha256_file(context.selection_path),
            "selection_signature": str(context.selection["selection_signature"]),
            "campaign_metric_sha256": {
                str(path): sha256_file(path) for path in context.metric_paths
            },
            "engine_sha256": str(context.manifest["engine_sha256"]),
            "engine_profile_sha256": str(context.manifest["engine_profile_sha256"]),
            "replay_plan_signature": replay["plan_signature"],
            "replay_run_receipt_signature": replay["run_receipt_signature"],
            "replay_validation_signature": replay["replay_validation_signature"],
            "replay_validation_sha256": replay["replay_validation_sha256"],
        },
        "requirement_scope": {
            "resolution_rule": (
                "profile and managed static pairs are accumulated; explicit dynamic "
                "pairs override and are removed from the static set"
            ),
            "configured_static_pairs": list(context.configured_static_pairs),
            "configured_dynamic_pairs": list(context.configured_dynamic_pairs),
            "active_lane_dynamic_pair_count": 2,
            "active_lane_static_pair_count": 16,
            "active_dynamic_pairs": sorted(EXPECTED_ACTIVE_DYNAMIC_PAIRS),
            "configured_dynamic_pair_outside_active_18_lanes": ["SDC-1450|item:021081"],
        },
        "evidence_semantics": {
            "target_discovery_proves": (
                "a fixed high-exposure 42-day simulated supplier window comparable "
                "across operating states"
            ),
            "target_discovery_does_not_prove": (
                "downstream stock, MRP, production or service causality"
            ),
            "campaign_incident_physically_exercised_means": (
                "at least one positive in-window supplier shipment was tagged and the "
                "acute risk application trace was non-empty"
            ),
            "complete_definition": (
                "inventoried native incident-arm shipment, material receipt, "
                "consumption/WIP with campaign and batch, finished lot, and aggregated "
                "client-contact evidence are all non-empty"
            ),
            "complete_scope": "native_lot_contact_trace_to_aggregated_client_only",
            "complete_does_not_mean": (
                "a proved dynamic stock-to-MRP-to-production-to-service causal cascade"
            ),
            "mrp_response_evidence_in_v4_replay_contract": False,
            "full_dynamic_cascade_claim_policy": (
                "forbidden_without_an_explicit_signed_MRP_response_trace"
            ),
            "genealogical_client_contact_is_incremental_service_loss": False,
        },
        "selection_guard": {
            "selected_dossier_count": int(selection["selected_dossier_count"]),
            "all_selected_campaign_dossiers_shipment_exercised": True,
            "all_replayed_dossiers_shipment_to_receipt_exercised": True,
            "forced_top_three": False,
            "selection_can_include_static_mrp_lanes": True,
            "selection_proves_full_dynamic_cascade": False,
        },
        "counts": {
            "lane_count": len(lane_qualifications),
            "dynamic_mrp_lane_count": sum(
                row["mrp_requirement_mode"] == "dynamic_explicit"
                for row in lane_qualifications
            ),
            "static_mrp_lane_count": sum(
                row["mrp_requirement_mode"] == "static_explicit"
                for row in lane_qualifications
            ),
            "selected_dossier_count": len(replay["dossiers"]),
            "lane_proof_level_counts": {
                level: int(lane_level_counts[level]) for level in sorted(PROOF_LEVELS)
            },
            "dossier_proof_level_counts": {
                level: int(dossier_level_counts[level])
                for level in sorted(PROOF_LEVELS)
            },
            "full_dynamic_cascade_proven_count": 0,
        },
        "lanes": lane_qualifications,
        "dossiers": replay["dossiers"],
    }
    payload_unsigned["scope_signature"] = stable_sha256(
        {
            "lanes": lane_qualifications,
            "dossiers": replay["dossiers"],
            "requirement_scope": payload_unsigned["requirement_scope"],
            "evidence_semantics": payload_unsigned["evidence_semantics"],
        }
    )
    return {
        **payload_unsigned,
        "qualification_signature": stable_sha256(payload_unsigned),
    }


def _validate_payload_schema(payload: Mapping[str, Any]) -> None:
    _verify_signed_payload(
        payload, "qualification_signature", label="physical qualification"
    )
    lanes = payload.get("lanes")
    dossiers = payload.get("dossiers")
    scope = payload.get("requirement_scope")
    semantics = payload.get("evidence_semantics")
    counts = payload.get("counts")
    if (
        payload.get("schema_version") != PAYLOAD_SCHEMA_VERSION
        or payload.get("status") != "complete_qualified"
        or not isinstance(lanes, list)
        or len(lanes) != EXPECTED_LANE_COUNT
        or not isinstance(dossiers, list)
        or len(dossiers) > MAX_REPLAY_DOSSIERS
        or not isinstance(scope, Mapping)
        or not isinstance(semantics, Mapping)
        or not isinstance(counts, Mapping)
        or semantics.get("mrp_response_evidence_in_v4_replay_contract") is not False
        or counts.get("full_dynamic_cascade_proven_count") != 0
    ):
        raise PhysicalCascadeQualificationError(
            "Physical qualification payload contract is incoherent"
        )
    lane_ids: set[str] = set()
    requirement_counts = Counter()
    proof_counts = Counter()
    for lane in lanes:
        if not isinstance(lane, Mapping):
            raise PhysicalCascadeQualificationError("Malformed lane qualification")
        lane_id = str(lane.get("lane_id") or "")
        proof_level = str(lane.get("proof_level") or "")
        requirement_mode = str(lane.get("mrp_requirement_mode") or "")
        if (
            not lane_id
            or lane_id in lane_ids
            or proof_level not in PROOF_LEVELS
            or requirement_mode not in {"dynamic_explicit", "static_explicit"}
            or lane.get("full_dynamic_stock_mrp_production_service_cascade_proven")
            is not False
            or lane.get("complete_cascade_label_allowed") is not False
        ):
            raise PhysicalCascadeQualificationError("Invalid lane qualification")
        lane_ids.add(lane_id)
        requirement_counts[requirement_mode] += 1
        proof_counts[proof_level] += 1
    if requirement_counts != Counter({"dynamic_explicit": 2, "static_explicit": 16}):
        raise PhysicalCascadeQualificationError("Lane requirement-mode counts changed")
    if counts.get("lane_proof_level_counts") != {
        level: int(proof_counts[level]) for level in sorted(PROOF_LEVELS)
    }:
        raise PhysicalCascadeQualificationError("Lane proof-level counts differ")

    dossier_ids: set[str] = set()
    dossier_counts = Counter()
    for dossier in dossiers:
        if not isinstance(dossier, Mapping):
            raise PhysicalCascadeQualificationError("Malformed dossier qualification")
        dossier_id = str(dossier.get("dossier_id") or "")
        proof_level = str(dossier.get("proof_level") or "")
        trace_counts = dossier.get("trace_counts")
        if (
            not dossier_id
            or dossier_id in dossier_ids
            or proof_level not in {"partial", "complete"}
            or not isinstance(trace_counts, Mapping)
            or dossier.get("campaign_shipment_exercised") is not True
            or dossier.get("replay_shipment_to_receipt_exercised") is not True
            or dossier.get("full_dynamic_stock_mrp_production_service_cascade_proven")
            is not False
            or dossier.get("complete_cascade_label_allowed") is not False
        ):
            raise PhysicalCascadeQualificationError("Invalid dossier qualification")
        derived_level, missing = _qualify_trace_counts(
            {
                field: _as_int(trace_counts.get(field), label=field)
                for field in trace_counts
            }
        )
        if (
            derived_level != proof_level
            or list(dossier.get("missing_native_trace_stages") or []) != missing
        ):
            raise PhysicalCascadeQualificationError(
                f"Dossier proof level contradicts its trace counts: {dossier_id}"
            )
        dossier_ids.add(dossier_id)
        dossier_counts[proof_level] += 1
    if counts.get("dossier_proof_level_counts") != {
        level: int(dossier_counts[level]) for level in sorted(PROOF_LEVELS)
    }:
        raise PhysicalCascadeQualificationError("Dossier proof-level counts differ")
    expected_scope_signature = stable_sha256(
        {
            "lanes": lanes,
            "dossiers": dossiers,
            "requirement_scope": scope,
            "evidence_semantics": semantics,
        }
    )
    if payload.get("scope_signature") != expected_scope_signature:
        raise PhysicalCascadeQualificationError("Physical scope signature differs")


LANE_TABLE_FIELDS = (
    "lane_id",
    "supplier_id",
    "item_id",
    "dst_node_id",
    "edge_id",
    "target_product_id",
    "site_item_pair",
    "mrp_requirement_mode",
    "physical_interpretation",
    "campaign_incident_run_count",
    "campaign_shipment_exercised_run_count",
    "campaign_shipment_not_exercised_run_count",
    "campaign_shipment_exercise_rate",
    "selected_dossier_ids",
    "selected_dossier_proof_levels",
    "proof_level",
    "proof_scope",
    "display_label_fr",
    "signed_mrp_response_trace_available",
    "full_dynamic_stock_mrp_production_service_cascade_proven",
    "complete_cascade_label_allowed",
)


def _payload_bytes(payload: Mapping[str, Any]) -> bytes:
    return (
        json.dumps(
            payload, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False
        )
        + "\n"
    ).encode("utf-8")


def _lane_table_bytes(payload: Mapping[str, Any]) -> bytes:
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(
        stream,
        fieldnames=list(LANE_TABLE_FIELDS),
        extrasaction="ignore",
        lineterminator="\n",
    )
    writer.writeheader()
    for source in payload["lanes"]:
        row = dict(source)
        row["campaign_shipment_exercise_rate"] = format(
            float(row["campaign_shipment_exercise_rate"]), ".12g"
        )
        row["selected_dossier_ids"] = "|".join(row["selected_dossier_ids"])
        row["selected_dossier_proof_levels"] = "|".join(
            row["selected_dossier_proof_levels"]
        )
        for field in (
            "signed_mrp_response_trace_available",
            "full_dynamic_stock_mrp_production_service_cascade_proven",
            "complete_cascade_label_allowed",
        ):
            row[field] = "true" if row[field] else "false"
        writer.writerow(row)
    return stream.getvalue().encode("utf-8")


def _output_material(payload: Mapping[str, Any]) -> tuple[bytes, bytes, dict[str, Any]]:
    _validate_payload_schema(payload)
    payload_bytes = _payload_bytes(payload)
    table_bytes = _lane_table_bytes(payload)
    unsigned_manifest = {
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "status": "complete_validated",
        "producer": payload["producer"],
        "producer_sha256": payload["producer_sha256"],
        "qualification_signature": payload["qualification_signature"],
        "campaign_signature": payload["source"]["campaign_signature"],
        "selection_signature": payload["source"]["selection_signature"],
        "replay_validation_signature": payload["source"]["replay_validation_signature"],
        "output_sha256": {
            PAYLOAD_FILE: hashlib.sha256(payload_bytes).hexdigest(),
            LANE_TABLE_FILE: hashlib.sha256(table_bytes).hexdigest(),
        },
        "output_row_count": {
            PAYLOAD_FILE: len(payload["dossiers"]),
            LANE_TABLE_FILE: len(payload["lanes"]),
        },
        "idempotence_contract": "same_sources_and_same_producer_yield_same_bytes",
    }
    manifest = {
        **unsigned_manifest,
        "manifest_signature": stable_sha256(unsigned_manifest),
    }
    return payload_bytes, table_bytes, manifest


def _manifest_bytes(manifest: Mapping[str, Any]) -> bytes:
    return (
        json.dumps(
            manifest, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False
        )
        + "\n"
    ).encode("utf-8")


def validate_qualification_sidecar(
    *,
    campaign_root: Path,
    results_dir: Path,
    replay_root: Path | None,
    output_dir: Path,
) -> dict[str, Any]:
    """Recompute and byte-validate one published qualification sidecar."""

    output_dir = output_dir.resolve()
    expected_names = {PAYLOAD_FILE, LANE_TABLE_FILE, MANIFEST_FILE}
    if not output_dir.is_dir():
        raise PhysicalCascadeQualificationError(
            f"Physical qualification directory is absent: {output_dir}"
        )
    actual_names = {path.name for path in output_dir.iterdir() if path.is_file()}
    non_files = [path for path in output_dir.iterdir() if not path.is_file()]
    if actual_names != expected_names or non_files:
        raise PhysicalCascadeQualificationError(
            "Physical qualification directory has missing or unsigned artifacts"
        )
    payload_path = output_dir / PAYLOAD_FILE
    table_path = output_dir / LANE_TABLE_FILE
    manifest_path = output_dir / MANIFEST_FILE
    payload = _read_json(payload_path, label="physical qualification payload")
    manifest = _read_json(manifest_path, label="physical qualification manifest")
    _validate_payload_schema(payload)
    _verify_signed_payload(
        manifest, "manifest_signature", label="physical qualification manifest"
    )
    if (
        manifest.get("schema_version") != MANIFEST_SCHEMA_VERSION
        or manifest.get("status") != "complete_validated"
        or manifest.get("producer_sha256") != sha256_file(Path(__file__).resolve())
        or manifest.get("qualification_signature")
        != payload.get("qualification_signature")
        or manifest.get("campaign_signature")
        != payload.get("source", {}).get("campaign_signature")
        or manifest.get("selection_signature")
        != payload.get("source", {}).get("selection_signature")
        or manifest.get("replay_validation_signature")
        != payload.get("source", {}).get("replay_validation_signature")
    ):
        raise PhysicalCascadeQualificationError(
            "Physical qualification manifest bindings differ"
        )
    output_hashes = manifest.get("output_sha256")
    if not isinstance(output_hashes, Mapping):
        raise PhysicalCascadeQualificationError(
            "Physical qualification output hashes are absent"
        )
    for name, path in ((PAYLOAD_FILE, payload_path), (LANE_TABLE_FILE, table_path)):
        _verify_file(
            path, output_hashes.get(name), label=f"qualification output {name}"
        )

    expected_payload = build_qualification_payload(
        campaign_root=campaign_root,
        results_dir=results_dir,
        replay_root=replay_root,
    )
    expected_payload_bytes, expected_table_bytes, expected_manifest = _output_material(
        expected_payload
    )
    if (
        payload_path.read_bytes() != expected_payload_bytes
        or table_path.read_bytes() != expected_table_bytes
        or manifest_path.read_bytes() != _manifest_bytes(expected_manifest)
    ):
        raise PhysicalCascadeQualificationError(
            "Physical qualification is not the deterministic projection of its sources"
        )
    return payload


def _remove_owned_stage(stage: Path) -> None:
    if not stage.name.startswith(".physical-cascade-v5-stage-"):
        raise PhysicalCascadeQualificationError("Refusing to clean an unowned stage")
    for name in (PAYLOAD_FILE, LANE_TABLE_FILE, MANIFEST_FILE):
        candidate = stage / name
        if candidate.is_file():
            candidate.unlink()
    if stage.is_dir():
        stage.rmdir()


def build_qualification_sidecar(
    *,
    campaign_root: Path,
    results_dir: Path,
    replay_root: Path | None,
    output_dir: Path,
) -> dict[str, Any]:
    """Publish a signed deterministic sidecar without overwriting divergent data."""

    output_dir = output_dir.resolve()
    payload = build_qualification_payload(
        campaign_root=campaign_root,
        results_dir=results_dir,
        replay_root=replay_root,
    )
    payload_bytes, table_bytes, manifest = _output_material(payload)
    manifest_bytes = _manifest_bytes(manifest)
    if output_dir.exists():
        validated = validate_qualification_sidecar(
            campaign_root=campaign_root,
            results_dir=results_dir,
            replay_root=replay_root,
            output_dir=output_dir,
        )
        if validated != payload:
            raise PhysicalCascadeQualificationError(
                "Existing qualification differs from the current sources"
            )
        return validated

    output_dir.parent.mkdir(parents=True, exist_ok=True)
    stage = output_dir.parent / f".physical-cascade-v5-stage-{uuid.uuid4().hex}"
    stage.mkdir(parents=False, exist_ok=False)
    try:
        (stage / PAYLOAD_FILE).write_bytes(payload_bytes)
        (stage / LANE_TABLE_FILE).write_bytes(table_bytes)
        (stage / MANIFEST_FILE).write_bytes(manifest_bytes)
        os.replace(stage, output_dir)
    except Exception:
        if stage.exists():
            _remove_owned_stage(stage)
        raise
    return validate_qualification_sidecar(
        campaign_root=campaign_root,
        results_dir=results_dir,
        replay_root=replay_root,
        output_dir=output_dir,
    )


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    for command in ("validate-selection", "validate-replay", "build", "validate"):
        subparser = subparsers.add_parser(command)
        subparser.add_argument("--campaign-root", type=Path, required=True)
        subparser.add_argument("--results-dir", type=Path, required=True)
        if command in {"validate-replay", "build", "validate"}:
            subparser.add_argument("--replay-root", type=Path)
        if command in {"build", "validate"}:
            subparser.add_argument("--output-dir", type=Path, required=True)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        if args.command == "validate-selection":
            result = validate_selected_dossiers_physically_exercised(
                campaign_root=args.campaign_root,
                results_dir=args.results_dir,
            )
        elif args.command == "validate-replay":
            result = validate_replay_dossiers_physically_exercised(
                campaign_root=args.campaign_root,
                results_dir=args.results_dir,
                replay_root=args.replay_root,
            )
        elif args.command == "build":
            result = build_qualification_sidecar(
                campaign_root=args.campaign_root,
                results_dir=args.results_dir,
                replay_root=args.replay_root,
                output_dir=args.output_dir,
            )
        else:
            result = validate_qualification_sidecar(
                campaign_root=args.campaign_root,
                results_dir=args.results_dir,
                replay_root=args.replay_root,
                output_dir=args.output_dir,
            )
    except PhysicalCascadeQualificationError as exc:
        print(f"PHYSICAL QUALIFICATION INVALID: {exc}")
        return 2
    print(
        json.dumps(
            {
                "status": result.get("status", "complete_validated"),
                "selected_dossier_count": result.get(
                    "selected_dossier_count", result.get("dossier_count", 0)
                ),
                "qualification_signature": result.get("qualification_signature", ""),
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
