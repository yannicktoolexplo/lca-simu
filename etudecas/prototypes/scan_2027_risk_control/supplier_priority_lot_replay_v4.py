#!/usr/bin/env python3
"""Plan, execute and finalize additive lot replays for V4 priority lanes.

The wide V4 supplier campaign intentionally runs without the detailed lot
ledger.  This module does not alter that campaign.  It selects representative
physically-exercised cases from its signed outputs, reconstructs two bounded
commands (baseline and incident) with lot tracing enabled, and builds a small
standalone French report from the resulting native ledgers.

Lot identifiers are run-local.  Every exported identifier is therefore
namespaced by its arm and no cross-arm lot pairing is attempted.  Paired
effects are calculated from daily curves and equal cumulative production
volumes only.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import math
import re
import statistics
import subprocess
import sys
from collections import defaultdict, deque
from collections.abc import Callable, Mapping, Sequence
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "etudecas.supplier_priority_lot_replay.v4"
PLAN_SCHEMA_VERSION = f"{SCHEMA_VERSION}.plan.v1"
RUN_RECEIPT_SCHEMA_VERSION = f"{SCHEMA_VERSION}.run_receipt.v1"
VALIDATION_SCHEMA_VERSION = f"{SCHEMA_VERSION}.validation.v1"
CAMPAIGN_SCHEMA_VERSION = "etudecas.supplier_operating_point_full_campaign.v4"
CASE_SCHEMA_VERSION = f"{CAMPAIGN_SCHEMA_VERSION}.case.v1"
V4_CLIENT_NODE_ID = "C-XXXXX"
EXPECTED_CAMPAIGN_REPETITIONS = 30

ALLOWED_MECHANISMS = {
    "transport_delay": ("lead_time_extra_days", 120.0),
    "planned_delivery_shortfall": ("reliability", 0.5),
}
RISK_CSV_FIELDS = (
    "event_id",
    "risk_type",
    "supplier_id",
    "item_id",
    "dst_node_id",
    "edge_id",
    "start_day",
    "end_day",
    "multiplier",
    "notes",
)
PRIORITY_STATUSES = {
    "robust_priority",
    "dossier_to_investigate",
}
FORBIDDEN_RISK_TOKENS = (
    "quality",
    "qualite",
    "availability",
    "capacity",
    "stock_writeoff",
)
CAMPAIGN_RUNTIME_FIELDS = frozenset(
    {
        "campaign_signature",
        "status",
        "created_at_utc",
        "completed_at_utc",
        "state_validation_binding",
        "state_validation_binding_sha256",
        "state_validation_binding_signature",
        "state_validation_binding_status",
        "target_discovery_completed_at_utc",
        "target_registry",
        "target_registry_sha256",
        "target_registry_signature",
        "target_discovery_status",
        "target_exposure_comparability_status",
    }
)
CONTROLLED_ENGINE_FLAGS = {
    "--input": 1,
    "--output-dir": 1,
    "--scenario-id": 1,
    "--days": 1,
    "--seed": 1,
    "--output-profile": 1,
    "--lot-trace": 0,
    "--no-lot-trace": 0,
    "--skip-lot-audit": 0,
    "--skip-map": 0,
    "--skip-plots": 0,
    "--common-random-numbers": 0,
    "--supplier-risk-events-csv": 1,
    "--supplier-state-dependent-risks": 0,
    "--no-supplier-state-dependent-risks": 0,
    "--supplier-neutral-floors-csv": 1,
    "--factory-nominal-capacities-csv": 1,
}
EPS = 1e-9


class ReplayContractError(ValueError):
    """Raised when a replay input or result fails the frozen contract."""


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
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _is_sha256(value: Any) -> bool:
    return bool(re.fullmatch(r"[0-9a-f]{64}", str(value or "")))


def _truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value or "").strip().casefold() in {"1", "true", "yes", "oui"}


def _float(value: Any, *, label: str = "value") -> float:
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise ReplayContractError(f"{label} must be numeric") from exc
    if not math.isfinite(result):
        raise ReplayContractError(f"{label} must be finite")
    return result


def _int(value: Any, *, label: str = "value") -> int:
    number = _float(value, label=label)
    if not number.is_integer():
        raise ReplayContractError(f"{label} must be an integer")
    return int(number)


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ReplayContractError(f"Invalid JSON: {path}") from exc
    if not isinstance(value, dict):
        raise ReplayContractError(f"JSON must contain an object: {path}")
    return value


def _read_csv(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        raise ReplayContractError(f"Missing CSV: {path}")
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise ReplayContractError(f"CSV has no header: {path}")
        return list(reader)


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    temporary.replace(path)


def _ordered_fields(rows: Sequence[Mapping[str, Any]]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for row in rows:
        for field in row:
            if field not in seen:
                seen.add(field)
                result.append(str(field))
    return result


def _write_csv(
    path: Path,
    rows: Sequence[Mapping[str, Any]],
    fields: Sequence[str] | None = None,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(fields or _ordered_fields(rows))
    if not fieldnames:
        raise ReplayContractError(f"Cannot write a CSV without a schema: {path}")
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    temporary.replace(path)


def _risk_csv_bytes(row: Mapping[str, Any]) -> bytes:
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=list(RISK_CSV_FIELDS))
    writer.writeheader()
    writer.writerow({field: row.get(field, "") for field in RISK_CSV_FIELDS})
    return stream.getvalue().encode("utf-8")


def _verify_signed_payload(
    payload: Mapping[str, Any], signature_field: str, label: str
) -> str:
    unsigned = dict(payload)
    signature = str(unsigned.pop(signature_field, ""))
    if not _is_sha256(signature) or signature != stable_sha256(unsigned):
        raise ReplayContractError(f"Invalid {label} signature")
    return signature


def _resolve_declared_path(raw: Any, bases: Sequence[Path], label: str) -> Path:
    text = str(raw or "").strip()
    if not text:
        raise ReplayContractError(f"Missing path for {label}")
    candidate = Path(text)
    candidates = (
        [candidate] if candidate.is_absolute() else [base / candidate for base in bases]
    )
    existing = [path.resolve() for path in candidates if path.is_file()]
    if not existing:
        raise ReplayContractError(f"Missing {label}: {text}")
    if len(set(existing)) != 1:
        raise ReplayContractError(f"Ambiguous {label}: {text}")
    return existing[0]


def _verify_file(path: Path, expected_sha: Any, label: str) -> str:
    expected = str(expected_sha or "").casefold()
    if not _is_sha256(expected):
        raise ReplayContractError(f"Invalid declared SHA-256 for {label}")
    actual = sha256_file(path)
    if actual != expected:
        raise ReplayContractError(f"SHA-256 mismatch for {label}: {path}")
    return actual


def _verify_campaign_manifest(path: Path) -> dict[str, Any]:
    manifest = _read_json(path)
    if manifest.get("schema_version") != CAMPAIGN_SCHEMA_VERSION:
        raise ReplayContractError("The source manifest is not a V4 campaign")
    signature = str(manifest.get("campaign_signature") or "")
    signed_design = {
        key: value
        for key, value in manifest.items()
        if key not in CAMPAIGN_RUNTIME_FIELDS
    }
    if not _is_sha256(signature) or signature != stable_sha256(signed_design):
        raise ReplayContractError("Invalid V4 campaign signature")
    for field in (
        "quality_branch_included",
        "quality_incident_included",
        "availability_incident_included",
        "capacity_incident_included",
        "stock_incident_included",
        "supplier_state_dependent_risks_enabled",
    ):
        if manifest.get(field) is not False:
            raise ReplayContractError(f"V4 manifest must declare {field}=false")
    mechanisms = {
        str(item.get("key") or ""): (
            str(item.get("risk_type") or ""),
            _float(item.get("value"), label="mechanism value"),
        )
        for item in manifest.get("mechanisms") or []
        if isinstance(item, Mapping)
    }
    if mechanisms != ALLOWED_MECHANISMS:
        raise ReplayContractError("V4 incident mechanism contract changed")
    return manifest


def _validate_campaign_results(
    *,
    campaign_root: Path,
    results_dir: Path,
    manifest_path: Path,
    manifest: Mapping[str, Any],
) -> tuple[dict[str, Any], Path, list[Path]]:
    validation_path = results_dir / "campaign_validation.json"
    validation = _read_json(validation_path)
    if validation.get("status") != "complete_validated":
        raise ReplayContractError("V4 campaign finalization is not complete_validated")
    if validation.get("campaign_signature") != manifest.get("campaign_signature"):
        raise ReplayContractError("Campaign validation/manifest signature mismatch")
    if validation.get("engine_sha256") != manifest.get("engine_sha256"):
        raise ReplayContractError("Campaign validation/engine hash mismatch")
    inputs = validation.get("inputs") or {}
    _verify_file(
        manifest_path,
        inputs.get("campaign_manifest_sha256"),
        "finalized campaign manifest",
    )
    expected = validation.get("expected_contract") or {}
    for field in (
        "quality_branch_included",
        "availability_incident_included",
    ):
        if expected.get(field) is not False:
            raise ReplayContractError(f"Finalized campaign must declare {field}=false")
    checks = validation.get("comparability_checks") or {}
    if checks.get("targeted_priority_lot_and_cascade_replay_required") is not True:
        raise ReplayContractError(
            "V4 finalization does not request a targeted lot replay"
        )
    if (
        _int(
            checks.get("quality_or_availability_incident_count", -1),
            label="forbidden incident count",
        )
        != 0
    ):
        raise ReplayContractError("Finalized campaign contains a forbidden incident")

    priority_path = results_dir / "priority_lanes_by_cause_state.csv"
    declared_priority = (validation.get("outputs") or {}).get(priority_path.name) or {}
    _verify_file(priority_path, declared_priority.get("sha256"), "priority lanes")
    if _int(declared_priority.get("row_count", -1), label="priority row count") != len(
        _read_csv(priority_path)
    ):
        raise ReplayContractError("Priority-lane row count differs from validation")

    declared_metrics = inputs.get("metrics_csv_sha256") or {}
    if not isinstance(declared_metrics, Mapping) or not declared_metrics:
        raise ReplayContractError(
            "Finalized V4 validation has no hashed campaign metrics"
        )
    metric_paths: list[Path] = []
    for raw, expected_sha in sorted(
        declared_metrics.items(), key=lambda item: str(item[0])
    ):
        metric_path = _resolve_declared_path(
            raw, (campaign_root, manifest_path.parent, results_dir), "campaign metrics"
        )
        _verify_file(metric_path, expected_sha, "campaign metrics")
        metric_paths.append(metric_path)
    if len(set(metric_paths)) != len(metric_paths):
        raise ReplayContractError("Campaign validation repeats a metrics file")
    return validation, priority_path, metric_paths


def _load_finalizer_selection(
    *,
    results_dir: Path,
    validation: Mapping[str, Any],
    manifest: Mapping[str, Any],
) -> tuple[dict[str, Any], Path] | None:
    """Load the optional signed V4 replay selection emitted by the finalizer."""

    path = results_dir / "lot_replay_plan.json"
    if not path.exists():
        return None
    payload = _read_json(path)
    expected_schema = (
        "etudecas.supplier_operating_point_full_campaign.v4.lot_replay_selection.v1"
    )
    if payload.get("schema_version") != expected_schema:
        raise ReplayContractError("Finalizer lot-replay selection schema changed")
    if payload.get("status") != "complete_selected":
        raise ReplayContractError("Finalizer lot-replay selection is not complete")
    _verify_signed_payload(payload, "selection_signature", "finalizer replay selection")
    if payload.get("campaign_signature") != manifest.get("campaign_signature"):
        raise ReplayContractError("Finalizer replay selection campaign differs")
    if payload.get("engine_sha256") != manifest.get("engine_sha256"):
        raise ReplayContractError("Finalizer replay selection engine differs")
    selection_contract = payload.get("selection_contract")
    if not isinstance(selection_contract, Mapping) or any(
        selection_contract.get(field) is not expected
        for field, expected in (
            ("evidence_paths_relative_to_campaign_root", True),
            ("risk_paths_relative_to_campaign_root", True),
            ("mechanisms_kept_separate", True),
            ("quality_included", False),
            ("state_dependent_supplier_risks_enabled", False),
            ("replay_executes_simulation", False),
        )
    ):
        raise ReplayContractError("Finalizer replay-selection contract changed")
    if (
        _int(
            selection_contract.get("maximum_dossiers"),
            label="finalizer maximum dossiers",
        )
        != 3
    ):
        raise ReplayContractError("Finalizer replay-selection maximum changed")
    declared = (validation.get("outputs") or {}).get(path.name)
    if not isinstance(declared, Mapping):
        declared = validation.get("lot_replay_plan")
    if not isinstance(declared, Mapping):
        raise ReplayContractError(
            "campaign_validation.json does not bind lot_replay_plan.json"
        )
    if str(declared.get("path") or path.name) != path.name:
        raise ReplayContractError("Finalized replay-selection path changed")
    _verify_file(path, declared.get("sha256"), "finalizer replay selection")
    if str(
        declared.get("selection_signature") or payload["selection_signature"]
    ) != str(payload["selection_signature"]):
        raise ReplayContractError(
            "Finalized replay-selection signature reference differs"
        )
    dossiers = payload.get("selected_dossiers")
    if not isinstance(dossiers, list) or not dossiers:
        raise ReplayContractError("Finalizer replay selection contains no dossier")
    declared_count = declared.get("row_count", len(dossiers))
    if _int(declared_count, label="selected dossier count") != len(dossiers):
        raise ReplayContractError("Finalizer replay selection count differs")
    keys: set[tuple[str, str, str]] = set()
    for item in dossiers:
        if not isinstance(item, Mapping):
            raise ReplayContractError("Malformed finalizer replay dossier")
        key = (
            str(item.get("operating_point_id") or ""),
            str(item.get("mechanism") or ""),
            str(item.get("lane_id") or ""),
        )
        if not all(key) or key in keys:
            raise ReplayContractError(
                "Duplicate or incomplete finalizer replay dossier"
            )
        if item.get("priority_status") not in PRIORITY_STATUSES:
            raise ReplayContractError("Finalizer selected a non-priority dossier")
        if key[1] not in ALLOWED_MECHANISMS:
            raise ReplayContractError("Finalizer selected an unknown mechanism")
        keys.add(key)
    return payload, path


def _find_unique(root: Path, relative_tail: str, label: str) -> Path:
    root = root.resolve()
    normalized = relative_tail.replace("\\", "/")
    matches = [
        path.resolve()
        for path in root.glob(f"**/{Path(normalized).name}")
        if path.resolve().is_relative_to(root) and path.as_posix().endswith(normalized)
    ]
    matches = sorted(set(matches))
    if len(matches) != 1:
        raise ReplayContractError(
            f"Expected exactly one {label} under {root}, found {len(matches)}"
        )
    return matches[0]


def _resolve_campaign_relative_file(root: Path, raw: Any, label: str) -> Path:
    """Resolve one signed campaign-relative file without a global search."""

    root = root.resolve()
    text = str(raw or "").strip()
    relative = Path(text)
    if not text or relative.is_absolute() or ".." in relative.parts:
        raise ReplayContractError(f"Unsafe signed campaign path for {label}: {text}")
    resolved = (root / relative).resolve()
    if not resolved.is_relative_to(root) or not resolved.is_file():
        raise ReplayContractError(f"Missing signed campaign file for {label}: {text}")
    return resolved


def _validate_case_evidence(
    path: Path,
    *,
    manifest: Mapping[str, Any],
    metric_row: Mapping[str, Any],
) -> dict[str, Any]:
    evidence = _read_json(path)
    _verify_signed_payload(evidence, "evidence_signature", "V4 case evidence")
    required_equal = {
        "schema_version": CASE_SCHEMA_VERSION,
        "campaign_signature": manifest.get("campaign_signature"),
        "engine_sha256": manifest.get("engine_sha256"),
        "case_key": metric_row.get("case_key"),
        "case_signature": metric_row.get("case_signature"),
        "operating_point_id": metric_row.get("operating_point_id"),
        "stage": metric_row.get("stage"),
    }
    for field, expected in required_equal.items():
        if evidence.get(field) != expected:
            raise ReplayContractError(f"Case evidence {field} differs: {path}")
    if _int(evidence.get("seed"), label="evidence seed") != _int(
        metric_row.get("seed"), label="metric seed"
    ):
        raise ReplayContractError(f"Case evidence seed differs: {path}")
    if _int(evidence.get("simulation_days"), label="evidence horizon") != _int(
        metric_row.get("simulation_days"), label="metric horizon"
    ):
        raise ReplayContractError(f"Case evidence horizon differs: {path}")
    if evidence.get("valid") is not True or evidence.get("status") not in {
        "valid",
        "valid_no_exposure",
    }:
        raise ReplayContractError(f"Case evidence is not valid: {path}")
    for field in (
        "quality_branch_included",
        "availability_incident_included",
        "supplier_state_dependent_risks_enabled",
    ):
        if evidence.get(field) is not False:
            raise ReplayContractError(f"Case evidence must declare {field}=false")
    return evidence


def _priority_sort_key(row: Mapping[str, Any]) -> tuple[Any, ...]:
    status_order = {
        "robust_priority": 0,
        "dossier_to_investigate": 1,
    }
    try:
        position = float(row.get("position") or math.inf)
    except (TypeError, ValueError):
        position = math.inf
    try:
        effect = -float(row.get("fixed360_effect_mean_pp") or 0.0)
    except (TypeError, ValueError):
        effect = 0.0
    return (
        status_order.get(str(row.get("priority_status") or ""), 9),
        position,
        effect,
        str(row.get("operating_point_id") or ""),
        str(row.get("mechanism") or ""),
        str(row.get("lane_id") or ""),
    )


def _select_priority_rows(
    rows: Sequence[Mapping[str, Any]],
    *,
    max_dossiers: int,
    selection_rows: Sequence[Mapping[str, Any]] | None,
) -> list[dict[str, Any]]:
    if not 1 <= max_dossiers <= 3:
        raise ReplayContractError("max_dossiers must be between one and three")
    selection_keys: list[tuple[str, str, str]] | None = None
    selected_key_set: set[tuple[str, str, str]] | None = None
    if selection_rows is not None:
        selection_keys = [
            (
                str(item.get("operating_point_id") or ""),
                str(item.get("mechanism") or ""),
                str(item.get("lane_id") or ""),
            )
            for item in selection_rows
        ]
        selected_key_set = set(selection_keys)
        if (
            not selection_keys
            or any(not all(key) for key in selection_keys)
            or len(selected_key_set) != len(selection_keys)
        ):
            raise ReplayContractError(
                "Explicit selection has duplicate or empty identities"
            )
        if len(selection_keys) > max_dossiers:
            raise ReplayContractError(
                "Explicit selection contains more dossiers than max_dossiers"
            )
    required = {
        "operating_point_id",
        "mechanism",
        "lane_id",
        "supplier_id",
        "item_id",
        "dst_node_id",
        "edge_id",
        "target_product_id",
        "priority_status",
    }
    candidates: list[dict[str, Any]] = []
    for source in rows:
        if not required.issubset(source):
            raise ReplayContractError("Priority-lane CSV schema is incomplete")
        if str(source.get("priority_status") or "") not in PRIORITY_STATUSES:
            continue
        if str(source.get("mechanism") or "") not in ALLOWED_MECHANISMS:
            raise ReplayContractError("Priority output contains an unknown mechanism")
        row = dict(source)
        if selected_key_set is not None:
            key = (
                str(row["operating_point_id"]),
                str(row["mechanism"]),
                str(row["lane_id"]),
            )
            if key not in selected_key_set:
                continue
        candidates.append(row)
    if not candidates:
        raise ReplayContractError(
            "No validated V4 priority lane is available for replay"
        )
    candidates.sort(key=_priority_sort_key)
    if selection_keys is not None and selected_key_set is not None:
        candidates_by_key = {
            (row["operating_point_id"], row["mechanism"], row["lane_id"]): row
            for row in candidates
        }
        if set(candidates_by_key) != selected_key_set:
            raise ReplayContractError(
                "Explicit selection is not an exact priority-lane subset"
            )
        return [candidates_by_key[key] for key in selection_keys]

    # Preserve both physical causes when both produced a priority signal.
    selected: list[dict[str, Any]] = []
    for mechanism in ALLOWED_MECHANISMS:
        match = next((row for row in candidates if row["mechanism"] == mechanism), None)
        if match is not None and len(selected) < max_dossiers:
            selected.append(match)
    for row in candidates:
        if len(selected) >= max_dossiers:
            break
        if row not in selected:
            selected.append(row)
    return selected


def _load_metric_rows(paths: Sequence[Path]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for path in paths:
        rows.extend(_read_csv(path))
    identity: set[tuple[str, str]] = set()
    for row in rows:
        key = (str(row.get("case_key") or ""), str(row.get("case_signature") or ""))
        if not all(key) or key in identity:
            raise ReplayContractError(
                "Campaign metrics contain a duplicate or empty case identity"
            )
        identity.add(key)
    return rows


def _representative_incident(
    rows: Sequence[Mapping[str, Any]], priority: Mapping[str, Any]
) -> dict[str, Any]:
    matching = [
        dict(row)
        for row in rows
        if str(row.get("stage") or "") == "incident"
        and str(row.get("operating_point_id") or "")
        == str(priority.get("operating_point_id") or "")
        and str(row.get("mechanism") or "") == str(priority.get("mechanism") or "")
        and str(row.get("lane_id") or "") == str(priority.get("lane_id") or "")
        and _truthy(row.get("valid"))
        and str(row.get("status") or "") == "valid"
        and _truthy(row.get("incident_physically_exercised"))
    ]
    if not matching:
        raise ReplayContractError(
            "Priority dossier has no valid physically-exercised campaign repetition"
        )
    metric = "impact_service_loss_fed_product_pp"
    values = [_float(row.get(metric), label=metric) for row in matching]
    median = statistics.median(values)
    matching.sort(
        key=lambda row: (
            abs(_float(row.get(metric), label=metric) - median),
            _int(row.get("seed"), label="seed"),
        )
    )
    selected = matching[0]
    selected["representative_cell_median_pp"] = median
    selected["representative_distance_to_median_pp"] = abs(
        _float(selected.get(metric), label=metric) - median
    )
    selected["representative_valid_exercised_seed_count"] = len(matching)
    return selected


def _baseline_for(
    rows: Sequence[Mapping[str, Any]], incident: Mapping[str, Any]
) -> dict[str, Any]:
    matches = [
        dict(row)
        for row in rows
        if str(row.get("stage") or "") == "baseline"
        and str(row.get("operating_point_id") or "")
        == str(incident.get("operating_point_id") or "")
        and _int(row.get("seed"), label="baseline seed")
        == _int(incident.get("seed"), label="incident seed")
        and _truthy(row.get("valid"))
        and str(row.get("status") or "") == "valid"
    ]
    if len(matches) != 1:
        raise ReplayContractError(
            "Representative incident has no unique valid paired baseline"
        )
    baseline = matches[0]
    if str(incident.get("baseline_case_signature") or "") != str(
        baseline.get("case_signature") or ""
    ):
        raise ReplayContractError("Representative incident baseline signature differs")
    return baseline


def _sanitize_id(value: str) -> str:
    result = re.sub(r"[^A-Za-z0-9_.-]+", "_", value).strip("_.")
    if not result:
        raise ReplayContractError("Cannot build an empty dossier identifier")
    return result


def _profile_args(path: Path) -> list[str]:
    payload = _read_json(path)
    values = payload.get("args")
    if not isinstance(values, list) or not all(
        isinstance(value, str) for value in values
    ):
        raise ReplayContractError(f"Invalid engine profile args: {path}")
    return list(values)


def _clean_physics_args(args: Sequence[str]) -> list[str]:
    result: list[str] = []
    index = 0
    while index < len(args):
        token = args[index]
        if token in CONTROLLED_ENGINE_FLAGS:
            arity = CONTROLLED_ENGINE_FLAGS[token]
            if index + arity >= len(args):
                raise ReplayContractError(
                    f"Malformed controlled engine argument: {token}"
                )
            # The standing protocol is allowed to state the required disabled mode.
            if token != "--no-supplier-state-dependent-risks":
                raise ReplayContractError(
                    f"Engine profile/protocol attempts to control replay flag {token}"
                )
            index += arity + 1
            continue
        result.append(token)
        index += 1
    return result


def _build_command(
    *,
    python_executable: str,
    engine: Path,
    graph: Path,
    output_dir: Path,
    horizon: int,
    seed: int,
    supplier_floors: Path | None,
    factory_capacities: Path | None,
    profile_args: Sequence[str],
    managed_args: Sequence[str],
    risk_csv: Path | None,
) -> list[str]:
    physics_args = _clean_physics_args([*profile_args, *managed_args])
    command = [
        python_executable,
        str(engine),
        "--input",
        str(graph),
        "--output-dir",
        str(output_dir),
        "--scenario-id",
        "scn:BASE",
    ]
    if supplier_floors is not None:
        command.extend(["--supplier-neutral-floors-csv", str(supplier_floors)])
    if factory_capacities is not None:
        command.extend(["--factory-nominal-capacities-csv", str(factory_capacities)])
    command.extend(physics_args)
    command.extend(
        [
            "--days",
            str(horizon),
            "--seed",
            str(seed),
            "--output-profile",
            "compact",
            "--skip-map",
            "--skip-plots",
            "--lot-trace",
            "--common-random-numbers",
        ]
    )
    if risk_csv is not None:
        command.extend(["--supplier-risk-events-csv", str(risk_csv)])
    command.append("--no-supplier-state-dependent-risks")
    _validate_command(command, incident=risk_csv is not None)
    return command


def _flag_values(command: Sequence[str], flag: str) -> list[str | None]:
    arity = CONTROLLED_ENGINE_FLAGS[flag]
    values: list[str | None] = []
    for index, token in enumerate(command):
        if token == flag:
            if arity == 0:
                values.append(None)
            elif index + 1 < len(command):
                values.append(command[index + 1])
            else:
                raise ReplayContractError(f"Command flag lacks a value: {flag}")
    return values


def _validate_command(command: Sequence[str], *, incident: bool) -> None:
    required_once = (
        "--input",
        "--output-dir",
        "--scenario-id",
        "--days",
        "--seed",
        "--output-profile",
        "--skip-map",
        "--skip-plots",
        "--lot-trace",
        "--common-random-numbers",
        "--no-supplier-state-dependent-risks",
    )
    for flag in required_once:
        if len(_flag_values(command, flag)) != 1:
            raise ReplayContractError(f"Replay command requires exactly one {flag}")
    if "--no-lot-trace" in command or "--skip-lot-audit" in command:
        raise ReplayContractError("Replay command disables a required lot proof")
    if "--supplier-state-dependent-risks" in command:
        raise ReplayContractError(
            "Replay command enables state-dependent supplier risks"
        )
    risk_values = _flag_values(command, "--supplier-risk-events-csv")
    if len(risk_values) != (1 if incident else 0):
        raise ReplayContractError("Replay command risk CSV scope differs from its arm")
    if _flag_values(command, "--output-profile") != ["compact"]:
        raise ReplayContractError("Replay output profile must be compact")
    if _flag_values(command, "--scenario-id") != ["scn:BASE"]:
        raise ReplayContractError("Replay scenario must remain scn:BASE")


def _risk_row_contract(
    row: Mapping[str, Any], *, priority: Mapping[str, Any], incident: Mapping[str, Any]
) -> dict[str, Any]:
    if set(row) != set(RISK_CSV_FIELDS):
        raise ReplayContractError("V4 risk row schema changed")
    mechanism = str(priority.get("mechanism") or "")
    risk_type, value = ALLOWED_MECHANISMS[mechanism]
    expected_equal = {
        "risk_type": risk_type,
        "supplier_id": str(priority.get("supplier_id") or ""),
        "item_id": str(priority.get("item_id") or ""),
        "dst_node_id": str(priority.get("dst_node_id") or ""),
        "edge_id": str(priority.get("edge_id") or ""),
    }
    for field, expected in expected_equal.items():
        if str(row.get(field) or "") != expected:
            raise ReplayContractError(f"V4 risk row {field} differs from priority lane")
    if _float(row.get("multiplier"), label="risk multiplier") != value:
        raise ReplayContractError("V4 risk multiplier changed")
    start = _int(row.get("start_day"), label="risk start day")
    end = _int(row.get("end_day"), label="risk end day")
    if start != _int(incident.get("risk_start_day"), label="metric risk start day"):
        raise ReplayContractError("Risk start day differs from campaign metrics")
    if end != _int(incident.get("risk_end_day"), label="metric risk end day"):
        raise ReplayContractError("Risk end day differs from campaign metrics")
    if end < start or end - start + 1 != 42:
        raise ReplayContractError(
            "V4 risk window must contain exactly 42 calendar days"
        )
    event_id = str(row.get("event_id") or "").strip()
    if not event_id:
        raise ReplayContractError("V4 risk event_id is empty")
    return dict(row)


def _source_inventory_entry(path: Path, role: str) -> dict[str, Any]:
    return {"role": role, "path": str(path.resolve()), "sha256": sha256_file(path)}


def create_replay_plan(
    *,
    campaign_root: Path,
    results_dir: Path,
    output_root: Path,
    max_dossiers: int = 3,
    selection_csv: Path | None = None,
    python_executable: str | None = None,
) -> dict[str, Any]:
    """Create one immutable replay plan without launching the engine."""

    campaign_root = campaign_root.resolve()
    results_dir = results_dir.resolve()
    output_root = output_root.resolve()
    if not campaign_root.is_dir() or not results_dir.is_dir():
        raise ReplayContractError("Campaign root and finalized results must exist")
    if output_root.exists() and any(output_root.iterdir()):
        raise ReplayContractError(
            f"Refusing to overwrite non-empty replay root: {output_root}"
        )

    manifest_path = campaign_root / "campaign_manifest.json"
    manifest = _verify_campaign_manifest(manifest_path)
    validation, priority_path, metric_paths = _validate_campaign_results(
        campaign_root=campaign_root,
        results_dir=results_dir,
        manifest_path=manifest_path,
        manifest=manifest,
    )
    finalizer_selection = _load_finalizer_selection(
        results_dir=results_dir,
        validation=validation,
        manifest=manifest,
    )
    if selection_csv is not None and finalizer_selection is not None:
        raise ReplayContractError(
            "Use either the signed finalizer selection or --selection-csv, not both"
        )
    engine = _resolve_declared_path(manifest.get("engine"), (campaign_root,), "engine")
    profile = _resolve_declared_path(
        manifest.get("engine_profile"), (campaign_root,), "engine profile"
    )
    _verify_file(engine, manifest.get("engine_sha256"), "engine")
    _verify_file(profile, manifest.get("engine_profile_sha256"), "engine profile")
    profile_args = _profile_args(profile)
    managed_args = manifest.get("managed_engine_args")
    if not isinstance(managed_args, list) or not all(
        isinstance(value, str) for value in managed_args
    ):
        raise ReplayContractError("V4 manifest managed_engine_args are invalid")

    priority_rows = _read_csv(priority_path)
    selection_rows = (
        list(finalizer_selection[0]["selected_dossiers"])
        if finalizer_selection is not None
        else (_read_csv(selection_csv.resolve()) if selection_csv else None)
    )
    priorities = _select_priority_rows(
        priority_rows,
        max_dossiers=max_dossiers,
        selection_rows=selection_rows,
    )
    metrics = _load_metric_rows(metric_paths)
    state_by_id = {
        str(state.get("operating_point_id") or ""): dict(state)
        for state in manifest.get("states") or []
        if isinstance(state, Mapping)
    }
    if len(state_by_id) != len(manifest.get("states") or []):
        raise ReplayContractError(
            "V4 manifest contains duplicate operating-point states"
        )

    staged: list[dict[str, Any]] = []
    inventory_paths: dict[Path, str] = {
        manifest_path: "campaign_manifest",
        results_dir / "campaign_validation.json": "campaign_validation",
        priority_path: "priority_lanes",
        engine: "engine",
        profile: "engine_profile",
    }
    for path in metric_paths:
        inventory_paths[path] = "campaign_metrics"
    if selection_csv:
        inventory_paths[selection_csv.resolve()] = "explicit_selection"
    if finalizer_selection is not None:
        inventory_paths[finalizer_selection[1]] = "signed_finalizer_replay_selection"
    declared_selection_by_key = {
        (
            str(item.get("operating_point_id") or ""),
            str(item.get("mechanism") or ""),
            str(item.get("lane_id") or ""),
        ): dict(item)
        for item in (
            finalizer_selection[0]["selected_dossiers"]
            if finalizer_selection is not None
            else []
        )
    }

    for priority in priorities:
        incident = _representative_incident(metrics, priority)
        baseline = _baseline_for(metrics, incident)
        exercised_seed_count = _int(
            incident.get("representative_valid_exercised_seed_count"),
            label="representative exercised-seed count",
        )
        if not 1 <= exercised_seed_count <= EXPECTED_CAMPAIGN_REPETITIONS:
            raise ReplayContractError(
                "Representative exercised-seed count is outside the 30-run cohort"
            )
        point_id = str(priority["operating_point_id"])
        state = state_by_id.get(point_id)
        if state is None:
            raise ReplayContractError(
                f"Priority operating point absent from manifest: {point_id}"
            )
        graph = _resolve_declared_path(
            state.get("graph"), (campaign_root,), "state graph"
        )
        _verify_file(graph, state.get("graph_sha256"), "state graph")
        inventory_paths[graph] = f"graph:{point_id}"

        supplier_floors: Path | None = None
        if str(state.get("supplier_floors") or "").strip():
            supplier_floors = _resolve_declared_path(
                state.get("supplier_floors"), (campaign_root,), "supplier floors"
            )
            _verify_file(
                supplier_floors,
                state.get("supplier_floors_sha256"),
                "supplier floors",
            )
            inventory_paths[supplier_floors] = f"supplier_floors:{point_id}"
        factory_capacities: Path | None = None
        if str(state.get("factory_capacities") or "").strip():
            factory_capacities = _resolve_declared_path(
                state.get("factory_capacities"),
                (campaign_root,),
                "factory capacities",
            )
            _verify_file(
                factory_capacities,
                state.get("factory_capacities_sha256"),
                "factory capacities",
            )
            inventory_paths[factory_capacities] = f"factory_capacities:{point_id}"

        incident_case_key = str(incident.get("case_key") or "")
        baseline_case_key = str(baseline.get("case_key") or "")
        declared_selection = declared_selection_by_key.get(
            (point_id, str(priority["mechanism"]), str(priority["lane_id"]))
        )
        if declared_selection is not None:
            incident_evidence_path = _resolve_campaign_relative_file(
                campaign_root,
                declared_selection.get("incident_evidence_path"),
                "incident case evidence",
            )
            baseline_evidence_path = _resolve_campaign_relative_file(
                campaign_root,
                declared_selection.get("baseline_evidence_path"),
                "baseline case evidence",
            )
            _verify_file(
                incident_evidence_path,
                declared_selection.get("incident_evidence_sha256"),
                "signed incident case evidence",
            )
            _verify_file(
                baseline_evidence_path,
                declared_selection.get("baseline_evidence_sha256"),
                "signed baseline case evidence",
            )
        else:
            shard_root = campaign_root / "shards"
            incident_evidence_path = _find_unique(
                shard_root,
                f"case_evidence/{incident_case_key}.json",
                "incident case evidence",
            )
            baseline_evidence_path = _find_unique(
                shard_root,
                f"case_evidence/{baseline_case_key}.json",
                "baseline case evidence",
            )
        incident_evidence = _validate_case_evidence(
            incident_evidence_path, manifest=manifest, metric_row=incident
        )
        baseline_evidence = _validate_case_evidence(
            baseline_evidence_path, manifest=manifest, metric_row=baseline
        )
        inventory_paths[incident_evidence_path] = "incident_case_evidence"
        inventory_paths[baseline_evidence_path] = "baseline_case_evidence"
        risk_row = _risk_row_contract(
            incident_evidence.get("risk_row") or {},
            priority=priority,
            incident=incident,
        )
        declared_risk_sha = str(incident_evidence.get("risk_csv_sha256") or "")
        if not _is_sha256(declared_risk_sha):
            raise ReplayContractError("Incident evidence lacks a valid risk CSV hash")
        if declared_selection is not None:
            risk_sources = [
                _resolve_campaign_relative_file(
                    campaign_root,
                    declared_selection.get("risk_csv_path"),
                    "incident risk CSV",
                )
            ]
            _verify_file(
                risk_sources[0],
                declared_selection.get("risk_csv_sha256"),
                "signed incident risk CSV",
            )
        else:
            shard_root = (campaign_root / "shards").resolve()
            risk_sources = sorted(
                set(
                    path.resolve()
                    for path in shard_root.glob(
                        f"**/inputs/risk_events/{incident_case_key}.csv"
                    )
                    if path.resolve().is_relative_to(shard_root)
                )
            )
        if len(risk_sources) > 1:
            raise ReplayContractError(
                "Multiple source risk CSVs match one incident case"
            )
        if risk_sources:
            risk_bytes = risk_sources[0].read_bytes()
            inventory_paths[risk_sources[0]] = "incident_risk_csv"
        else:
            risk_bytes = _risk_csv_bytes(risk_row)
        if hashlib.sha256(risk_bytes).hexdigest() != declared_risk_sha:
            raise ReplayContractError(
                "Reconstructed/source risk CSV differs from case evidence"
            )

        horizon = _int(
            incident.get("required_simulation_days") or incident.get("simulation_days"),
            label="required replay horizon",
        )
        minimum_days = _int(
            manifest.get("minimum_case_days", 1), label="minimum case horizon"
        )
        if horizon < minimum_days:
            raise ReplayContractError("Replay horizon is shorter than the V4 minimum")
        seed = _int(incident.get("seed"), label="representative seed")
        expected_warmup = str(incident.get("warmup_core_state_sha256") or "")
        if not _is_sha256(expected_warmup) or expected_warmup != str(
            baseline.get("warmup_core_state_sha256") or ""
        ):
            raise ReplayContractError(
                "Paired campaign warmup-state proof differs or is absent"
            )
        if expected_warmup != str(
            (incident_evidence.get("metrics") or {}).get("warmup_core_state_sha256")
            or ""
        ) or expected_warmup != str(
            (baseline_evidence.get("metrics") or {}).get("warmup_core_state_sha256")
            or ""
        ):
            raise ReplayContractError(
                "Case evidence lost the paired warmup-state proof"
            )
        dossier_id = _sanitize_id(
            str(declared_selection.get("dossier_id") or "")
            if declared_selection is not None
            else f"{point_id}__{priority['mechanism']}__{priority['lane_id']}"
        )
        if declared_selection is not None:
            for field, resolved_evidence in (
                ("incident_evidence_path", incident_evidence_path),
                ("baseline_evidence_path", baseline_evidence_path),
                ("risk_csv_path", risk_sources[0]),
            ):
                relative = Path(str(declared_selection.get(field) or ""))
                if relative.is_absolute() or ".." in relative.parts:
                    raise ReplayContractError(
                        f"Unsafe finalizer replay evidence path: {field}"
                    )
                declared_path = (campaign_root / relative).resolve()
                if (
                    not declared_path.is_relative_to(campaign_root)
                    or declared_path != resolved_evidence.resolve()
                ):
                    raise ReplayContractError(
                        f"Finalizer replay evidence path differs on {field}"
                    )
            expected_fields = {
                "dossier_id": dossier_id,
                "supplier_id": str(priority["supplier_id"]),
                "item_id": str(priority["item_id"]),
                "dst_node_id": str(priority["dst_node_id"]),
                "edge_id": str(priority["edge_id"]),
                "target_product_id": str(priority["target_product_id"]),
                "priority_status": str(priority["priority_status"]),
                "representative_seed": seed,
                "valid_exercised_seed_count": exercised_seed_count,
                "incident_case_key": incident_case_key,
                "incident_case_signature": str(incident["case_signature"]),
                "baseline_case_key": baseline_case_key,
                "baseline_case_signature": str(baseline["case_signature"]),
                "required_simulation_days": horizon,
                "warmup_core_state_sha256": expected_warmup,
                "risk_csv_sha256": declared_risk_sha,
                "incident_evidence_sha256": sha256_file(incident_evidence_path),
                "baseline_evidence_sha256": sha256_file(baseline_evidence_path),
            }
            for field, expected_value in expected_fields.items():
                actual_value = declared_selection.get(field)
                if field in {
                    "representative_seed",
                    "valid_exercised_seed_count",
                    "required_simulation_days",
                }:
                    actual_value = _int(actual_value, label=f"selection {field}")
                else:
                    actual_value = str(actual_value or "")
                if actual_value != expected_value:
                    raise ReplayContractError(
                        f"Signed finalizer replay selection differs on {field}"
                    )
            if declared_selection.get("representative_metric") != (
                "impact_service_loss_fed_product_pp"
            ):
                raise ReplayContractError("Finalizer representative metric changed")
            for field, calculated in (
                (
                    "representative_effect_pp",
                    _float(
                        incident.get("impact_service_loss_fed_product_pp"),
                        label="representative effect",
                    ),
                ),
                (
                    "cell_median_effect_pp",
                    _float(
                        incident.get("representative_cell_median_pp"),
                        label="cell median",
                    ),
                ),
            ):
                if not math.isclose(
                    _float(declared_selection.get(field), label=f"selection {field}"),
                    calculated,
                    abs_tol=1e-12,
                    rel_tol=1e-12,
                ):
                    raise ReplayContractError(
                        f"Signed finalizer replay selection differs on {field}"
                    )
        staged.append(
            {
                "dossier_id": dossier_id,
                "priority": dict(priority),
                "incident_metric": dict(incident),
                "baseline_metric": dict(baseline),
                "incident_evidence_path": str(incident_evidence_path),
                "incident_evidence_sha256": sha256_file(incident_evidence_path),
                "baseline_evidence_path": str(baseline_evidence_path),
                "baseline_evidence_sha256": sha256_file(baseline_evidence_path),
                "risk_row": risk_row,
                "risk_csv_sha256": declared_risk_sha,
                "risk_bytes": risk_bytes,
                "graph": graph,
                "graph_sha256": sha256_file(graph),
                "supplier_floors": supplier_floors,
                "factory_capacities": factory_capacities,
                "horizon_days": horizon,
                "seed": seed,
                "warmup_core_state_sha256": expected_warmup,
            }
        )

    dossier_ids = [item["dossier_id"] for item in staged]
    if len(set(dossier_ids)) != len(dossier_ids):
        raise ReplayContractError(
            "Selected priority rows produce duplicate dossier IDs"
        )

    output_root.mkdir(parents=True, exist_ok=True)
    python_value = str(Path(python_executable or sys.executable).resolve())
    dossiers: list[dict[str, Any]] = []
    for item in staged:
        dossier_id = item["dossier_id"]
        risk_path = output_root / "inputs" / dossier_id / "supplier_risk_events.csv"
        risk_path.parent.mkdir(parents=True, exist_ok=True)
        risk_path.write_bytes(item.pop("risk_bytes"))
        if sha256_file(risk_path) != item["risk_csv_sha256"]:
            raise ReplayContractError("Copied replay risk CSV changed unexpectedly")
        arms: dict[str, Any] = {}
        for arm in ("baseline", "incident"):
            run_dir = output_root / "runs" / dossier_id / arm
            command = _build_command(
                python_executable=python_value,
                engine=engine,
                graph=item["graph"],
                output_dir=run_dir,
                horizon=item["horizon_days"],
                seed=item["seed"],
                supplier_floors=item["supplier_floors"],
                factory_capacities=item["factory_capacities"],
                profile_args=profile_args,
                managed_args=managed_args,
                risk_csv=risk_path if arm == "incident" else None,
            )
            arms[arm] = {
                "run_dir": str(run_dir),
                "command": command,
                "command_sha256": stable_sha256(command),
            }
        dossier = {
            key: value
            for key, value in item.items()
            if key not in {"graph", "supplier_floors", "factory_capacities"}
        }
        dossier.update(
            {
                "graph": str(item["graph"]),
                "supplier_floors": (
                    str(item["supplier_floors"]) if item["supplier_floors"] else ""
                ),
                "factory_capacities": (
                    str(item["factory_capacities"])
                    if item["factory_capacities"]
                    else ""
                ),
                "risk_csv": str(risk_path),
                "kpi_scope": {
                    "service_node_id": V4_CLIENT_NODE_ID,
                    "production_node_id": str(item["priority"]["dst_node_id"]),
                    "product_id": str(item["priority"]["target_product_id"]),
                    "service_definition": (
                        "current demand served after clearing starting backlog"
                    ),
                },
                "arms": arms,
            }
        )
        dossiers.append(dossier)

    source_inventory = [
        _source_inventory_entry(path, role)
        for path, role in sorted(inventory_paths.items(), key=lambda item: str(item[0]))
    ]
    plan: dict[str, Any] = {
        "schema_version": PLAN_SCHEMA_VERSION,
        "created_at_utc": utc_now(),
        "replay_root": str(output_root),
        "campaign_root": str(campaign_root),
        "results_dir": str(results_dir),
        "campaign_signature": manifest["campaign_signature"],
        "campaign_validation_sha256": sha256_file(
            results_dir / "campaign_validation.json"
        ),
        "engine": str(engine),
        "engine_sha256": manifest["engine_sha256"],
        "engine_profile": str(profile),
        "engine_profile_sha256": manifest["engine_profile_sha256"],
        "python_executable": python_value,
        "selection_contract": {
            "source": (
                "signed_finalizer_lot_replay_plan"
                if finalizer_selection is not None
                else "signed_priority_lanes_by_cause_state"
            ),
            "priority_statuses": sorted(PRIORITY_STATUSES),
            "max_dossiers": max_dossiers,
            "representative_seed": (
                "valid physically-exercised seed nearest the cell median paired "
                "fixed-360 service loss; smallest seed breaks ties"
            ),
            "representative_population": (
                "physically-exercised repetitions only; count reported out of 30"
            ),
            "mechanisms_kept_separate": True,
            "quality_included": False,
            "state_dependent_supplier_risks_enabled": False,
        },
        "lot_identity_contract": {
            "ids_are_run_local": True,
            "namespace_format": "<arm>::<native_lot_id>",
            "cross_arm_lot_id_matching_allowed": False,
            "cross_arm_comparison": "daily curves and equal cumulative volumes only",
        },
        "source_inventory": source_inventory,
        "dossiers": dossiers,
    }
    plan["plan_signature"] = stable_sha256(plan)
    _write_json(output_root / "replay_plan.json", plan)
    command_bundle = {
        "schema_version": f"{SCHEMA_VERSION}.commands.v1",
        "plan_signature": plan["plan_signature"],
        "commands": [
            {
                "dossier_id": dossier["dossier_id"],
                "arm": arm,
                **dossier["arms"][arm],
            }
            for dossier in dossiers
            for arm in ("baseline", "incident")
        ],
    }
    command_bundle["command_bundle_signature"] = stable_sha256(command_bundle)
    _write_json(output_root / "replay_commands.json", command_bundle)
    return plan


def load_and_validate_plan(replay_root: Path) -> dict[str, Any]:
    replay_root = replay_root.resolve()
    plan_path = replay_root / "replay_plan.json"
    plan = _read_json(plan_path)
    if plan.get("schema_version") != PLAN_SCHEMA_VERSION:
        raise ReplayContractError("Replay plan schema changed")
    _verify_signed_payload(plan, "plan_signature", "replay plan")
    if Path(str(plan.get("replay_root") or "")).resolve() != replay_root:
        raise ReplayContractError("Replay plan was moved to another root")
    if not plan.get("dossiers"):
        raise ReplayContractError("Replay plan contains no dossier")
    for entry in plan.get("source_inventory") or []:
        path = Path(str(entry.get("path") or ""))
        _verify_file(path, entry.get("sha256"), str(entry.get("role") or "source"))
    engine = Path(str(plan.get("engine") or ""))
    profile = Path(str(plan.get("engine_profile") or ""))
    _verify_file(engine, plan.get("engine_sha256"), "planned engine")
    _verify_file(profile, plan.get("engine_profile_sha256"), "planned profile")
    for dossier in plan["dossiers"]:
        if sha256_file(Path(dossier["risk_csv"])) != dossier["risk_csv_sha256"]:
            raise ReplayContractError("Planned risk CSV changed")
        for arm in ("baseline", "incident"):
            arm_plan = dossier.get("arms", {}).get(arm) or {}
            command = arm_plan.get("command") or []
            if stable_sha256(command) != arm_plan.get("command_sha256"):
                raise ReplayContractError("Planned command hash changed")
            _validate_command(command, incident=arm == "incident")
            if (
                Path(arm_plan["run_dir"]).resolve()
                != (replay_root / "runs" / dossier["dossier_id"] / arm).resolve()
            ):
                raise ReplayContractError(
                    "Planned run directory escaped the replay root"
                )
    command_bundle = _read_json(replay_root / "replay_commands.json")
    if command_bundle.get("schema_version") != f"{SCHEMA_VERSION}.commands.v1":
        raise ReplayContractError("Replay command-bundle schema changed")
    _verify_signed_payload(
        command_bundle, "command_bundle_signature", "replay command bundle"
    )
    if command_bundle.get("plan_signature") != plan.get("plan_signature"):
        raise ReplayContractError("Replay command bundle belongs to another plan")
    expected_commands = [
        {
            "dossier_id": dossier["dossier_id"],
            "arm": arm,
            **dossier["arms"][arm],
        }
        for dossier in plan["dossiers"]
        for arm in ("baseline", "incident")
    ]
    if command_bundle.get("commands") != expected_commands:
        raise ReplayContractError("Replay command bundle differs from the signed plan")
    return plan


def _event_tokens(value: Any) -> set[str]:
    return {
        token.strip() for token in re.split(r"[;,|]", str(value or "")) if token.strip()
    }


def _required_run_files(run_dir: Path) -> dict[str, Path]:
    data = run_dir / "data"
    return {
        "summary": run_dir / "summaries" / "first_simulation_summary.json",
        "shipments": data / "production_supplier_shipments_daily.csv",
        "lot_events": data / "production_lot_events.csv",
        "genealogy": data / "production_lot_genealogy.csv",
        "plan_events": data / "production_plan_events.csv",
        "campaigns": data / "production_campaigns.csv",
        "input_stocks": data / "production_input_stocks_daily.csv",
        "production": data / "production_output_products_daily.csv",
        "demand": data / "production_demand_service_daily.csv",
        "applied_risk": data / "supplier_risk_events_applied_daily.csv",
        "state_risk": data / "supplier_state_dependent_risk_events.csv",
        "lot_audit": data / "lot_path_audit_issues.csv",
    }


def _validate_applied_risk(
    rows: Sequence[Mapping[str, Any]], *, dossier: Mapping[str, Any], arm: str
) -> None:
    if arm == "baseline":
        if rows:
            raise ReplayContractError("Baseline contains applied supplier-risk rows")
        return
    if not rows:
        raise ReplayContractError("Incident has no applied supplier-risk row")
    expected_event = str(dossier["risk_row"]["event_id"])
    mechanism = str(dossier["priority"]["mechanism"])
    risk_type, value = ALLOWED_MECHANISMS[mechanism]
    for row in rows:
        tokens = _event_tokens(row.get("event_ids"))
        if tokens != {expected_event}:
            raise ReplayContractError("Applied-risk row contains an unexpected event")
        for field, neutral in (
            ("stock_multiplier", 1.0),
            ("capacity_multiplier", 1.0),
            ("quality_delay_days", 0.0),
            ("quality_yield_multiplier", 1.0),
            ("availability_multiplier", 1.0),
            ("stock_writeoff_fraction", 0.0),
        ):
            if (
                field in row
                and str(row.get(field) or "").strip()
                and not math.isclose(
                    _float(row[field], label=field), neutral, abs_tol=1e-9, rel_tol=0.0
                )
            ):
                raise ReplayContractError(f"Forbidden applied-risk modifier: {field}")
        if risk_type == "lead_time_extra_days":
            if not math.isclose(
                _float(row.get("lead_time_extra_days"), label="lead_time_extra_days"),
                value,
                abs_tol=1e-9,
                rel_tol=0.0,
            ):
                raise ReplayContractError(
                    "Applied transport delay differs from +120 days"
                )
            if "reliability_multiplier" in row and not math.isclose(
                _float(
                    row.get("reliability_multiplier"), label="reliability_multiplier"
                ),
                1.0,
                abs_tol=1e-9,
                rel_tol=0.0,
            ):
                raise ReplayContractError("Delay incident also changes reliability")
        else:
            if not math.isclose(
                _float(
                    row.get("reliability_multiplier"), label="reliability_multiplier"
                ),
                value,
                abs_tol=1e-9,
                rel_tol=0.0,
            ):
                raise ReplayContractError(
                    "Applied delivery shortfall differs from x0.5"
                )
            if "lead_time_extra_days" in row and not math.isclose(
                _float(row.get("lead_time_extra_days"), label="lead_time_extra_days"),
                0.0,
                abs_tol=1e-9,
                rel_tol=0.0,
            ):
                raise ReplayContractError("Shortfall incident also changes lead time")


def validate_arm(
    run_dir: Path,
    *,
    dossier: Mapping[str, Any],
    arm: str,
) -> dict[str, Any]:
    """Validate one generated arm without comparing run-local lot IDs."""

    if arm not in {"baseline", "incident"}:
        raise ReplayContractError(f"Unknown replay arm: {arm}")
    run_dir = run_dir.resolve()
    files = _required_run_files(run_dir)
    missing = [name for name, path in files.items() if not path.is_file()]
    if missing:
        raise ReplayContractError(f"Replay arm lacks required files: {missing}")
    summary = _read_json(files["summary"])
    policy = summary.get("policy") or {}
    if summary.get("input_sha256") != dossier.get("graph_sha256"):
        raise ReplayContractError("Replay graph hash differs from the V4 dossier")
    if _int(summary.get("sim_days"), label="summary horizon") != _int(
        dossier.get("horizon_days"), label="planned horizon"
    ):
        raise ReplayContractError("Replay horizon differs from the V4 dossier")
    if _int(policy.get("seed"), label="summary seed") != _int(
        dossier.get("seed"), label="planned seed"
    ):
        raise ReplayContractError("Replay seed differs from the V4 dossier")
    if (
        policy.get("output_profile") != "compact"
        or policy.get("lot_trace_enabled") is not True
    ):
        raise ReplayContractError("Replay must be compact with lot tracing enabled")
    if policy.get("common_random_numbers") is not True:
        raise ReplayContractError("Replay must use common random numbers")
    state_risk = policy.get("supplier_state_dependent_risk") or {}
    if state_risk.get("enabled") is not False:
        raise ReplayContractError("State-dependent supplier risks are enabled")
    warmup = policy.get("warmup_boundary_audit") or {}
    if warmup.get("core_state_sha256") != dossier.get("warmup_core_state_sha256"):
        raise ReplayContractError(
            "Replay warmup state differs from the paired V4 proof"
        )
    supplier_risk = policy.get("supplier_risk") or {}
    expected_count = 1 if arm == "incident" else 0
    if (
        _int(supplier_risk.get("event_count", 0), label="supplier risk event count")
        != expected_count
    ):
        raise ReplayContractError("Replay acute supplier-risk event count differs")
    if supplier_risk.get("warnings"):
        raise ReplayContractError("Replay supplier-risk loader emitted warnings")
    if arm == "baseline":
        if _truthy(supplier_risk.get("enabled")):
            raise ReplayContractError("Baseline supplier-risk layer is enabled")
    else:
        if not _truthy(supplier_risk.get("enabled")):
            raise ReplayContractError("Incident supplier-risk layer is disabled")
        if supplier_risk.get("events_csv_sha256") != dossier.get("risk_csv_sha256"):
            raise ReplayContractError("Incident summary risk CSV hash differs")

    state_rows = _read_csv(files["state_risk"])
    if state_rows:
        raise ReplayContractError("State-dependent supplier-risk ledger is not empty")
    audit_rows = _read_csv(files["lot_audit"])
    audit_errors = [
        row
        for row in audit_rows
        if str(row.get("severity") or "").casefold() == "error"
    ]
    if audit_errors:
        raise ReplayContractError(f"Lot audit contains {len(audit_errors)} error(s)")
    applied_rows = _read_csv(files["applied_risk"])
    _validate_applied_risk(applied_rows, dossier=dossier, arm=arm)

    shipments = _read_csv(files["shipments"])
    expected_event = str(dossier["risk_row"]["event_id"])
    start = _int(dossier["risk_row"]["start_day"], label="risk start")
    end = _int(dossier["risk_row"]["end_day"], label="risk end")
    lane = dossier["priority"]
    scoped_positive = []
    tagged = []
    for row in shipments:
        tokens = _event_tokens(row.get("risk_event_ids"))
        decision = _int(
            row.get("risk_decision_day", row.get("day", -1)),
            label="shipment decision day",
        )
        lane_match = (
            str(row.get("src_node_id") or "") == str(lane.get("supplier_id") or "")
            and str(row.get("dst_node_id") or "") == str(lane.get("dst_node_id") or "")
            and str(row.get("item_id") or "") == str(lane.get("item_id") or "")
            and str(row.get("edge_id") or "") == str(lane.get("edge_id") or "")
        )
        if (
            lane_match
            and start <= decision <= end
            and _float(row.get("shipped_qty", 0), label="shipment quantity") > EPS
        ):
            scoped_positive.append(row)
        if expected_event in tokens:
            tagged.append(row)
            if arm != "incident" or not lane_match or not start <= decision <= end:
                raise ReplayContractError(
                    "Risk event is tagged outside its exact lane/window"
                )
    if arm == "baseline" and tagged:
        raise ReplayContractError("Baseline shipment is tagged with the incident")
    if arm == "incident":
        if not scoped_positive:
            raise ReplayContractError(
                "Representative replay incident is not physically exercised"
            )
        if {str(row.get("shipment_id") or "") for row in scoped_positive} != {
            str(row.get("shipment_id") or "") for row in tagged
        }:
            raise ReplayContractError(
                "Not every positive in-window shipment is natively tagged"
            )
        if any(not str(row.get("shipment_id") or "").strip() for row in tagged):
            raise ReplayContractError("Tagged shipment lacks shipment_id")

    # Headers and parseability are part of the compact lot contract.
    lot_events = _read_csv(files["lot_events"])
    genealogy = _read_csv(files["genealogy"])
    if lot_events and not {
        "event_type",
        "lot_id",
        "shipment_id",
        "risk_event_ids",
        "production_campaign_id",
    }.issubset(lot_events[0]):
        raise ReplayContractError("Lot-event ledger schema is incomplete")
    if genealogy and not {
        "link_type",
        "parent_lot_id",
        "child_lot_id",
        "shipment_id",
        "risk_event_ids",
        "production_campaign_id",
    }.issubset(genealogy[0]):
        raise ReplayContractError("Lot-genealogy ledger schema is incomplete")
    return {
        "arm": arm,
        "run_dir": str(run_dir),
        "summary_sha256": sha256_file(files["summary"]),
        "warmup_core_state_sha256": warmup["core_state_sha256"],
        "shipment_row_count": len(shipments),
        "tagged_shipment_count": len(tagged),
        "lot_event_row_count": len(lot_events),
        "genealogy_row_count": len(genealogy),
        "lot_audit_warning_count": sum(
            str(row.get("severity") or "").casefold() == "warning" for row in audit_rows
        ),
    }


def _shipment_trace_signature(
    rows: Sequence[Mapping[str, Any]], end_exclusive: int
) -> str:
    projection = []
    for row in rows:
        decision = _int(
            row.get("risk_decision_day", row.get("day", -1)), label="decision day"
        )
        if decision >= end_exclusive:
            continue
        projection.append(
            {
                field: str(row.get(field) or "")
                for field in (
                    "day",
                    "shipment_id",
                    "risk_decision_day",
                    "src_node_id",
                    "dst_node_id",
                    "item_id",
                    "edge_id",
                    "shipped_qty",
                    "pulled_qty",
                    "lead_days",
                    "arrival_day",
                    "reliability",
                    "uom",
                )
            }
        )
    projection.sort(key=lambda row: tuple(row[field] for field in sorted(row)))
    return stable_sha256(projection)


def _validate_pair(dossier: Mapping[str, Any]) -> dict[str, Any]:
    baseline_dir = Path(dossier["arms"]["baseline"]["run_dir"])
    incident_dir = Path(dossier["arms"]["incident"]["run_dir"])
    baseline = validate_arm(baseline_dir, dossier=dossier, arm="baseline")
    incident = validate_arm(incident_dir, dossier=dossier, arm="incident")
    if baseline["warmup_core_state_sha256"] != incident["warmup_core_state_sha256"]:
        raise ReplayContractError("Paired replay warmup states differ")
    baseline_demand = _read_csv(_required_run_files(baseline_dir)["demand"])
    incident_demand = _read_csv(_required_run_files(incident_dir)["demand"])

    def demand_projection(
        rows: Sequence[Mapping[str, Any]],
    ) -> list[tuple[str, str, str, str]]:
        return sorted(
            (
                str(row.get("day") or ""),
                str(row.get("node_id") or ""),
                str(row.get("item_id") or ""),
                str(row.get("demand_qty") or ""),
            )
            for row in rows
        )

    if demand_projection(baseline_demand) != demand_projection(incident_demand):
        raise ReplayContractError("Paired replay demand changed between arms")
    baseline_shipments = _read_csv(_required_run_files(baseline_dir)["shipments"])
    incident_shipments = _read_csv(_required_run_files(incident_dir)["shipments"])
    start = _int(dossier["risk_row"]["start_day"], label="risk start")
    baseline_pre = _shipment_trace_signature(baseline_shipments, start)
    incident_pre = _shipment_trace_signature(incident_shipments, start)
    if baseline_pre != incident_pre:
        raise ReplayContractError("Paired shipment traces diverge before the incident")
    return {
        "baseline": baseline,
        "incident": incident,
        "pre_incident_shipment_trace_sha256": baseline_pre,
    }


Executor = Callable[[Sequence[str], Path], Any]


def execute_replay(
    replay_root: Path,
    *,
    execute: bool = False,
    executor: Executor | None = None,
) -> dict[str, Any]:
    """Validate commands, and optionally launch them.  Tests inject an executor."""

    replay_root = replay_root.resolve()
    plan = load_and_validate_plan(replay_root)
    commands = [
        {
            "dossier_id": dossier["dossier_id"],
            "arm": arm,
            "command": dossier["arms"][arm]["command"],
        }
        for dossier in plan["dossiers"]
        for arm in ("baseline", "incident")
    ]
    if not execute:
        return {
            "status": "validated_not_executed",
            "plan_signature": plan["plan_signature"],
            "commands": commands,
        }
    receipt_path = replay_root / "replay_run_receipt.json"
    if receipt_path.exists():
        raise ReplayContractError("Refusing to overwrite an existing run receipt")
    repo_root = Path(__file__).resolve().parents[3]
    results: list[dict[str, Any]] = []
    for dossier in plan["dossiers"]:
        for arm in ("baseline", "incident"):
            arm_plan = dossier["arms"][arm]
            run_dir = Path(arm_plan["run_dir"])
            if run_dir.exists():
                raise ReplayContractError(
                    f"Refusing to overwrite replay arm: {run_dir}"
                )
            command = list(arm_plan["command"])
            if executor is None:
                log_path = replay_root / "logs" / f"{dossier['dossier_id']}__{arm}.log"
                log_path.parent.mkdir(parents=True, exist_ok=True)
                with log_path.open("w", encoding="utf-8") as stream:
                    completed = subprocess.run(
                        command,
                        cwd=repo_root,
                        stdout=stream,
                        stderr=subprocess.STDOUT,
                        text=True,
                        check=False,
                    )
                return_code = completed.returncode
            else:
                completed = executor(command, repo_root)
                return_code = (
                    int(completed)
                    if isinstance(completed, int)
                    else int(getattr(completed, "returncode", -1))
                )
            if return_code != 0:
                raise ReplayContractError(
                    f"Replay engine failed for {dossier['dossier_id']} {arm}: {return_code}"
                )
            proof = validate_arm(run_dir, dossier=dossier, arm=arm)
            results.append({"dossier_id": dossier["dossier_id"], **proof})
    for dossier in plan["dossiers"]:
        _validate_pair(dossier)
    receipt: dict[str, Any] = {
        "schema_version": RUN_RECEIPT_SCHEMA_VERSION,
        "status": "complete_validated",
        "created_at_utc": utc_now(),
        "plan_signature": plan["plan_signature"],
        "arms": results,
    }
    receipt["run_receipt_signature"] = stable_sha256(receipt)
    _write_json(receipt_path, receipt)
    return receipt


def namespace_lot_id(arm: str, lot_id: Any) -> str:
    value = str(lot_id or "").strip()
    return f"{arm}::{value}" if value else ""


def _propagate_shipment_provenance(
    genealogy: Sequence[Mapping[str, Any]],
    seeds: Mapping[str, set[str]],
) -> dict[str, set[str]]:
    provenance = {lot: set(shipments) for lot, shipments in seeds.items()}
    allowed_shipments = {
        shipment for shipments in seeds.values() for shipment in shipments
    }
    pending = deque(dict(row) for row in genealogy)
    stalled = 0
    while pending and stalled <= len(pending):
        row = pending.popleft()
        parent = str(row.get("parent_lot_id") or "")
        child = str(row.get("child_lot_id") or "")
        direct = str(row.get("shipment_id") or "")
        incoming = set(provenance.get(parent, set()))
        if direct in allowed_shipments:
            incoming.add(direct)
        before = len(provenance.get(child, set()))
        if incoming and child:
            provenance.setdefault(child, set()).update(incoming)
        if incoming or len(provenance.get(child, set())) > before:
            stalled = 0
        else:
            pending.append(row)
            stalled += 1
    return provenance


def _validate_native_supplier_transport(
    *,
    shipments: Sequence[Mapping[str, Any]],
    events: Sequence[Mapping[str, Any]],
    genealogy: Sequence[Mapping[str, Any]],
    dossier: Mapping[str, Any],
) -> tuple[set[str], dict[str, set[str]], dict[str, set[str]]]:
    """Prove dispatch-to-receipt identity, timing, quantity and unit continuity."""

    event_id = str(dossier["risk_row"]["event_id"])
    lane = dossier["priority"]
    horizon = _int(dossier["horizon_days"], label="native-trace horizon")
    selected = [
        row
        for row in shipments
        if event_id in _event_tokens(row.get("risk_event_ids"))
        and _float(row.get("shipped_qty", 0), label="shipped_qty") > EPS
    ]
    shipment_ids = [str(row.get("shipment_id") or "") for row in selected]
    if (
        not shipment_ids
        or "" in shipment_ids
        or len(set(shipment_ids)) != len(shipment_ids)
    ):
        raise ReplayContractError(
            "Native trace has duplicate or empty incident shipment IDs"
        )
    source_by_shipment: dict[str, set[str]] = defaultdict(set)
    receipt_by_shipment: dict[str, set[str]] = defaultdict(set)
    for shipment in selected:
        shipment_id = str(shipment["shipment_id"])
        decision = _int(
            shipment.get("risk_decision_day"), label="shipment decision day"
        )
        arrival = _int(shipment.get("arrival_day"), label="shipment arrival day")
        if not 0 <= arrival < horizon:
            raise ReplayContractError(
                "Incident receipt is censored outside the adaptive replay horizon: "
                f"{shipment_id} arrival J{arrival}, horizon J0-J{horizon - 1}"
            )
        expected_identity = {
            "node_id": str(lane["supplier_id"]),
            "item_id": str(lane["item_id"]),
            "source_id": str(lane["edge_id"]),
        }
        source_events = [
            row
            for row in events
            if row.get("event_type") == "lane_ship"
            and str(row.get("shipment_id") or "") == shipment_id
        ]
        if not source_events:
            raise ReplayContractError(
                f"Incident shipment lacks lane_ship events: {shipment_id}"
            )
        shipment_uom = str(shipment.get("uom") or "").strip().upper()
        if not shipment_uom:
            raise ReplayContractError(f"Incident shipment lacks a unit: {shipment_id}")
        for row in source_events:
            if any(
                str(row.get(field) or "") != value
                for field, value in expected_identity.items()
            ):
                raise ReplayContractError(f"lane_ship identity differs: {shipment_id}")
            if (
                _int(row.get("day"), label="lane_ship day") != decision
                or _int(row.get("risk_decision_day"), label="lane_ship decision day")
                != decision
                or _event_tokens(row.get("risk_event_ids")) != {event_id}
                or str(row.get("uom") or "").strip().upper() != shipment_uom
            ):
                raise ReplayContractError(
                    f"lane_ship timing, risk tag or unit differs: {shipment_id}"
                )
            lot_id = str(row.get("lot_id") or "")
            if not lot_id:
                raise ReplayContractError(
                    f"lane_ship lacks a source lot: {shipment_id}"
                )
            source_by_shipment[shipment_id].add(lot_id)
        pulled = _float(shipment.get("pulled_qty"), label="shipment pulled_qty")
        shipped = _float(shipment.get("shipped_qty"), label="shipment shipped_qty")
        if pulled <= EPS or shipped <= EPS or shipped > pulled + 1e-6:
            raise ReplayContractError(
                f"Incident shipment quantities are invalid: {shipment_id}"
            )
        if not math.isclose(
            sum(_float(row.get("qty"), label="lane_ship qty") for row in source_events),
            pulled,
            abs_tol=1e-5,
            rel_tol=1e-9,
        ):
            raise ReplayContractError(
                f"lane_ship quantity does not cover pulled_qty: {shipment_id}"
            )

        edges = [
            row
            for row in genealogy
            if row.get("link_type") == "transport"
            and str(row.get("shipment_id") or "") == shipment_id
        ]
        if not edges:
            raise ReplayContractError(
                f"Incident shipment lacks a transport receipt: {shipment_id}"
            )
        by_child: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
        for row in edges:
            child = str(row.get("child_lot_id") or "")
            if (
                not child
                or str(row.get("parent_lot_id") or "")
                not in source_by_shipment[shipment_id]
                or str(row.get("parent_node_id") or "") != str(lane["supplier_id"])
                or str(row.get("child_node_id") or "") != str(lane["dst_node_id"])
                or str(row.get("parent_item_id") or "") != str(lane["item_id"])
                or str(row.get("child_item_id") or "") != str(lane["item_id"])
                or str(row.get("source_id") or "") != str(lane["edge_id"])
                or _int(row.get("day"), label="transport receipt day") != arrival
                or _int(row.get("risk_decision_day"), label="receipt decision day")
                != decision
                or _event_tokens(row.get("risk_event_ids")) != {event_id}
            ):
                raise ReplayContractError(
                    f"Transport genealogy identity, timing or risk tag differs: {shipment_id}"
                )
            by_child[child].append(row)
            receipt_by_shipment[shipment_id].add(child)
        if not math.isclose(
            sum(
                _float(row.get("parent_qty"), label="transport parent_qty")
                for row in edges
            ),
            pulled,
            abs_tol=1e-5,
            rel_tol=1e-9,
        ):
            raise ReplayContractError(
                f"Transport genealogy does not cover pulled_qty: {shipment_id}"
            )
        receipt_total = 0.0
        for child, child_edges in by_child.items():
            receipt_events = [
                row
                for row in events
                if row.get("event_type") == "lane_receipt"
                and str(row.get("lot_id") or "") == child
                and str(row.get("shipment_id") or "") == shipment_id
            ]
            if len(receipt_events) != 1:
                raise ReplayContractError(
                    f"Receipt lot lacks one native lane_receipt event: {shipment_id}/{child}"
                )
            receipt = receipt_events[0]
            receipt_qty = _float(receipt.get("qty"), label="receipt lot qty")
            if (
                _int(receipt.get("day"), label="receipt event day") != arrival
                or _int(
                    receipt.get("risk_decision_day"), label="receipt event decision"
                )
                != decision
                or str(receipt.get("node_id") or "") != str(lane["dst_node_id"])
                or str(receipt.get("item_id") or "") != str(lane["item_id"])
                or _event_tokens(receipt.get("risk_event_ids")) != {event_id}
                or str(receipt.get("uom") or "").strip().upper() != shipment_uom
            ):
                raise ReplayContractError(
                    f"Receipt event identity, timing, risk tag or unit differs: {shipment_id}"
                )
            parent_qty = sum(
                _float(row.get("parent_qty"), label="transport parent_qty")
                for row in child_edges
            )
            if not math.isclose(
                receipt_qty,
                parent_qty * shipped / pulled,
                abs_tol=1e-5,
                rel_tol=1e-9,
            ) or any(
                not math.isclose(
                    _float(row.get("child_qty"), label="transport child_qty"),
                    receipt_qty,
                    abs_tol=1e-5,
                    rel_tol=1e-9,
                )
                for row in child_edges
            ):
                raise ReplayContractError(
                    f"Receipt lot quantity is inconsistent with shipment yield: {shipment_id}"
                )
            shares = [
                _float(row.get("allocation_share"), label="allocation_share")
                for row in child_edges
            ]
            if not math.isclose(sum(shares), 1.0, abs_tol=1e-6, rel_tol=1e-9):
                raise ReplayContractError(
                    f"Receipt genealogy allocation shares do not sum to one: {shipment_id}"
                )
            receipt_total += receipt_qty
        if not math.isclose(receipt_total, shipped, abs_tol=1e-5, rel_tol=1e-9):
            raise ReplayContractError(
                f"Receipt-lot quantity does not cover shipped_qty: {shipment_id}"
            )
    return set(shipment_ids), source_by_shipment, receipt_by_shipment


def extract_native_trace(
    incident_dir: Path, *, dossier: Mapping[str, Any]
) -> dict[str, list[dict[str, Any]]]:
    """Extract native incident-arm paths; never creates a cross-arm lot match."""

    files = _required_run_files(incident_dir)
    shipments = _read_csv(files["shipments"])
    events = _read_csv(files["lot_events"])
    genealogy = _read_csv(files["genealogy"])
    plan_events = _read_csv(files["plan_events"])
    campaigns = _read_csv(files["campaigns"])
    event_id = str(dossier["risk_row"]["event_id"])
    exposed_shipments, source_by_shipment, receipt_by_shipment = (
        _validate_native_supplier_transport(
            shipments=shipments,
            events=events,
            genealogy=genealogy,
            dossier=dossier,
        )
    )
    seeds: dict[str, set[str]] = defaultdict(set)
    for row in events:
        shipment_id = str(row.get("shipment_id") or "")
        lot_id = str(row.get("lot_id") or "")
        if (
            row.get("event_type") == "lane_ship"
            and shipment_id in exposed_shipments
            and event_id in _event_tokens(row.get("risk_event_ids"))
            and lot_id
        ):
            seeds[lot_id].add(shipment_id)

    shipment_mp_rows: list[dict[str, Any]] = []
    for row in genealogy:
        shipment_id = str(row.get("shipment_id") or "")
        if shipment_id not in exposed_shipments or row.get("link_type") != "transport":
            continue
        parent = str(row.get("parent_lot_id") or "")
        child = str(row.get("child_lot_id") or "")
        if (
            parent not in source_by_shipment[shipment_id]
            or child not in receipt_by_shipment[shipment_id]
        ):
            continue
        seeds[child].add(shipment_id)
        shipment_mp_rows.append(
            {
                "arm": "incident",
                "incident_event_id": event_id,
                "shipment_id": shipment_id,
                "risk_decision_day": row.get("risk_decision_day", ""),
                "source_lot_id": namespace_lot_id("incident", parent),
                "source_node_id": row.get("parent_node_id", ""),
                "source_item_id": row.get("parent_item_id", ""),
                "receipt_lot_id": namespace_lot_id("incident", child),
                "receipt_node_id": row.get("child_node_id", ""),
                "receipt_item_id": row.get("child_item_id", ""),
                "parent_qty": row.get("parent_qty", ""),
                "child_qty": row.get("child_qty", ""),
                "uom_guard": "validated_on_source_and_receipt_events",
            }
        )
    if {row["shipment_id"] for row in shipment_mp_rows} != exposed_shipments:
        raise ReplayContractError(
            "Not every incident shipment has a native receipt-lot edge"
        )

    provenance = _propagate_shipment_provenance(genealogy, seeds)
    plan_index: dict[tuple[int, str], list[dict[str, str]]] = defaultdict(list)
    for row in plan_events:
        key = (
            _int(row.get("day"), label="plan-event day"),
            str(row.get("campaign_id") or ""),
        )
        plan_index[key].append(row)
    campaign_index = {
        str(row.get("campaign_id") or ""): row
        for row in campaigns
        if str(row.get("campaign_id") or "")
    }
    if len(campaign_index) != sum(
        bool(str(row.get("campaign_id") or "")) for row in campaigns
    ):
        raise ReplayContractError(
            "Production campaign ledger has duplicate campaign_id"
        )

    consumption_rows: list[dict[str, Any]] = []
    for row in events:
        lot_id = str(row.get("lot_id") or "")
        campaign_id = str(row.get("production_campaign_id") or "")
        if row.get("event_type") != "production_consume" or lot_id not in provenance:
            continue
        key = (_int(row.get("day"), label="consumption day"), campaign_id)
        plans = plan_index.get(key, [])
        if len(plans) != 1:
            raise ReplayContractError(
                "Native consumption cannot be joined uniquely to day+campaign plan state"
            )
        plan = plans[0]
        campaign = campaign_index.get(campaign_id, {})
        consumption_rows.append(
            {
                "arm": "incident",
                "incident_event_id": event_id,
                "shipment_ids": "|".join(sorted(provenance[lot_id])),
                "material_lot_id": namespace_lot_id("incident", lot_id),
                "day": row.get("day", ""),
                "node_id": row.get("node_id", ""),
                "item_id": row.get("item_id", ""),
                "consumed_qty": row.get("qty", ""),
                "uom": row.get("uom", ""),
                "campaign_id": campaign_id,
                "batch_id": plan.get("batch_id", ""),
                "wip_start_qty": plan.get("wip_start_qty", ""),
                "wip_end_qty": plan.get("wip_end_qty", ""),
                "released_qty_same_day": plan.get("released_qty", ""),
                "released_lot_id_same_day": namespace_lot_id(
                    "incident", plan.get("released_lot_id", "")
                ),
                "binding_input_item_id": plan.get("binding_input_item_id", ""),
                "plan_reason": plan.get("reason", ""),
                "campaign_status": campaign.get("status", ""),
                "campaign_wip_qty_end_of_run": campaign.get("wip_qty", ""),
                "campaign_blocked_lot_qty": campaign.get("blocked_lot_qty", ""),
            }
        )

    target_product = str(dossier["priority"]["target_product_id"]).replace("item:", "")
    service_node = str((dossier.get("kpi_scope") or {}).get("service_node_id") or "")
    if not service_node:
        raise ReplayContractError("Native trace lacks the signed client-service scope")
    output_events = {
        str(row.get("lot_id") or ""): row
        for row in events
        if row.get("event_type") == "production_output"
        and str(row.get("lot_id") or "") in provenance
        and str(row.get("item_id") or "").replace("item:", "") == target_product
    }
    finished_rows: list[dict[str, Any]] = []
    for lot_id, row in sorted(output_events.items()):
        parent_lots = sorted(
            {
                str(edge.get("parent_lot_id") or "")
                for edge in genealogy
                if edge.get("link_type") == "production"
                and str(edge.get("child_lot_id") or "") == lot_id
                and str(edge.get("parent_lot_id") or "") in provenance
            }
        )
        finished_rows.append(
            {
                "arm": "incident",
                "incident_event_id": event_id,
                "shipment_ids": "|".join(sorted(provenance[lot_id])),
                "finished_lot_id": namespace_lot_id("incident", lot_id),
                "day": row.get("day", ""),
                "node_id": row.get("node_id", ""),
                "item_id": row.get("item_id", ""),
                "released_qty": row.get("qty", ""),
                "uom": row.get("uom", ""),
                "campaign_id": row.get("production_campaign_id", ""),
                "exposed_parent_lot_ids": "|".join(
                    namespace_lot_id("incident", value) for value in parent_lots
                ),
                "claim": "native_genealogical_contact_not_cross_arm_identity",
            }
        )

    client_rows: list[dict[str, Any]] = []
    for row in events:
        lot_id = str(row.get("lot_id") or "")
        if (
            row.get("event_type") != "demand_service"
            or lot_id not in provenance
            or str(row.get("node_id") or "") != service_node
            or str(row.get("item_id") or "").replace("item:", "") != target_product
        ):
            continue
        client_rows.append(
            {
                "arm": "incident",
                "incident_event_id": event_id,
                "shipment_ids": "|".join(sorted(provenance[lot_id])),
                "client_lot_id": namespace_lot_id("incident", lot_id),
                "day": row.get("day", ""),
                "client_node_id": row.get("node_id", ""),
                "item_id": row.get("item_id", ""),
                "service_event_qty_on_contacted_lot": row.get("qty", ""),
                "uom": row.get("uom", ""),
                "claim": "native_genealogical_contact_not_incremental_service_loss",
            }
        )
    return {
        "shipment_to_mp_lots": shipment_mp_rows,
        "exposed_consumption_wip": consumption_rows,
        "exposed_finished_lots": finished_rows,
        "exposed_client_events": client_rows,
    }


def _daily_series(
    run_dir: Path, *, dossier: Mapping[str, Any]
) -> dict[str, dict[int, float]]:
    files = _required_run_files(run_dir)
    horizon = _int(dossier["horizon_days"], label="horizon")
    component = str(dossier["priority"]["item_id"])
    factory = str(dossier["priority"]["dst_node_id"])
    product = str(dossier["priority"]["target_product_id"])
    scope = dossier.get("kpi_scope")
    if not isinstance(scope, Mapping):
        raise ReplayContractError("Replay dossier lacks its signed KPI scope")
    if str(scope.get("production_node_id") or "") != factory or str(
        scope.get("product_id") or ""
    ).replace("item:", "") != product.replace("item:", ""):
        raise ReplayContractError("Replay KPI scope differs from its priority lane")
    service_node = str(scope.get("service_node_id") or "")
    if not service_node:
        raise ReplayContractError("Replay KPI scope lacks its service node")
    result: dict[str, dict[int, float]] = {
        metric: {day: 0.0 for day in range(horizon)}
        for metric in (
            "component_stock",
            "production_released",
            "wip",
            "demand",
            "served_on_due",
            "backlog",
        )
    }
    stock_seen: set[int] = set()
    for row in _read_csv(files["input_stocks"]):
        if (
            str(row.get("node_id") or "") == factory
            and str(row.get("item_id") or "") == component
        ):
            day = _int(row.get("day"), label="stock day")
            if day in stock_seen or day not in result["component_stock"]:
                raise ReplayContractError(
                    "Component stock series is duplicate/out of horizon"
                )
            stock_seen.add(day)
            result["component_stock"][day] = _float(
                row.get("stock_end_of_day"), label="component stock"
            )
    if stock_seen != set(range(horizon)):
        raise ReplayContractError(
            "Component stock series does not cover the replay horizon"
        )
    production_seen: set[int] = set()
    for row in _read_csv(files["production"]):
        if str(row.get("node_id") or "") != factory or str(
            row.get("item_id") or ""
        ).replace("item:", "") != product.replace("item:", ""):
            continue
        day = _int(row.get("day"), label="production day")
        if day in production_seen or day not in result["production_released"]:
            raise ReplayContractError(
                "Target production series is duplicate/out of horizon"
            )
        production_seen.add(day)
        result["production_released"][day] = max(
            0.0, _float(row.get("released_qty", 0), label="released production")
        )
        result["wip"][day] = max(0.0, _float(row.get("wip_end_qty", 0), label="wip"))
    if production_seen != set(range(horizon)):
        raise ReplayContractError(
            "Target production series does not cover the replay horizon"
        )
    service_seen: set[int] = set()
    for row in _read_csv(files["demand"]):
        if str(row.get("node_id") or "") != service_node or str(
            row.get("item_id") or ""
        ).replace("item:", "") != product.replace("item:", ""):
            continue
        day = _int(row.get("day"), label="demand day")
        if day in service_seen or day not in result["demand"]:
            raise ReplayContractError(
                "Target service series is duplicate/out of horizon"
            )
        service_seen.add(day)
        demand = max(0.0, _float(row.get("demand_qty", 0), label="demand"))
        served = max(0.0, _float(row.get("served_qty", 0), label="served"))
        required = max(
            demand,
            _float(
                row.get("required_with_backlog_qty", demand),
                label="required with backlog",
            ),
        )
        starting_backlog = max(0.0, required - demand)
        result["demand"][day] = demand
        result["served_on_due"][day] = min(demand, max(0.0, served - starting_backlog))
        result["backlog"][day] = max(
            0.0, _float(row.get("backlog_end_qty", 0), label="backlog")
        )
    if service_seen != set(range(horizon)):
        raise ReplayContractError(
            "Target service series does not cover the replay horizon"
        )
    return result


def _first_divergence(
    baseline: Mapping[int, float],
    incident: Mapping[int, float],
    *,
    start: int,
    end: int,
) -> int | None:
    for day in range(start, end + 1):
        if not math.isclose(
            baseline.get(day, 0.0), incident.get(day, 0.0), abs_tol=1e-6, rel_tol=1e-9
        ):
            return day
    return None


def _paired_curves_and_kpis(
    baseline_dir: Path, incident_dir: Path, *, dossier: Mapping[str, Any]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    baseline = _daily_series(baseline_dir, dossier=dossier)
    incident = _daily_series(incident_dir, dossier=dossier)
    start = _int(
        dossier["incident_metric"].get("impact_window_start_day"), label="impact start"
    )
    end = _int(
        dossier["incident_metric"].get("impact_window_end_day"), label="impact end"
    )
    horizon = _int(dossier["horizon_days"], label="horizon")
    if not 0 <= start <= end < horizon:
        raise ReplayContractError("Impact window falls outside the replay horizon")
    curve_rows = [
        {
            "day": day,
            "metric": metric,
            "baseline_value": baseline[metric][day],
            "incident_value": incident[metric][day],
            "delta_incident_minus_baseline": incident[metric][day]
            - baseline[metric][day],
        }
        for metric in baseline
        for day in range(horizon)
    ]

    def window_sum(series: Mapping[int, float]) -> float:
        return sum(series[day] for day in range(start, end + 1))

    base_demand = window_sum(baseline["demand"])
    incident_demand = window_sum(incident["demand"])
    if not math.isclose(base_demand, incident_demand, abs_tol=1e-6, rel_tol=1e-12):
        raise ReplayContractError("Impact-window demand differs between replay arms")
    base_on_due = window_sum(baseline["served_on_due"])
    incident_on_due = window_sum(incident["served_on_due"])
    service_loss_pp = (
        100.0 * (base_on_due - incident_on_due) / base_demand
        if base_demand > EPS
        else 0.0
    )
    base_backlog_days = window_sum(baseline["backlog"])
    incident_backlog_days = window_sum(incident["backlog"])
    base_max_backlog = max(baseline["backlog"][day] for day in range(start, end + 1))
    incident_max_backlog = max(
        incident["backlog"][day] for day in range(start, end + 1)
    )
    base_production = window_sum(baseline["production_released"])
    incident_production = window_sum(incident["production_released"])

    cumulative_base: dict[int, float] = {}
    cumulative_incident: dict[int, float] = {}
    total_base = total_incident = 0.0
    for day in range(start, end + 1):
        total_base += baseline["production_released"][day]
        total_incident += incident["production_released"][day]
        cumulative_base[day] = total_base
        cumulative_incident[day] = total_incident
    lag_rows: list[dict[str, Any]] = []
    for fraction in (0.10, 0.25, 0.50, 0.75, 0.90, 1.0):
        calculable = total_base > EPS
        threshold = total_base * fraction if calculable else 0.0
        base_day = (
            next(
                (
                    day
                    for day in range(start, end + 1)
                    if cumulative_base[day] + EPS >= threshold
                ),
                None,
            )
            if calculable
            else None
        )
        incident_day = (
            next(
                (
                    day
                    for day in range(start, end + 1)
                    if cumulative_incident[day] + EPS >= threshold
                ),
                None,
            )
            if calculable
            else None
        )
        lag_rows.append(
            {
                "baseline_volume_fraction": fraction,
                "threshold_qty": threshold,
                "baseline_reach_day": base_day,
                "incident_reach_day": incident_day,
                "lag_days": (
                    incident_day - base_day
                    if base_day is not None and incident_day is not None
                    else ""
                ),
                "incident_censored_at_window_end": calculable and incident_day is None,
                "status": (
                    "calculated"
                    if calculable and incident_day is not None
                    else "censored_at_window_end"
                    if calculable
                    else "not_calculable_zero_reference_volume"
                ),
                "claim": "equal_cumulative_volume_not_same_lot",
            }
        )
    risk_end = _int(dossier["risk_row"]["end_day"], label="risk end")
    latest_arrival_raw = str(
        dossier["incident_metric"].get("target_latest_stressed_arrival_day") or ""
    ).strip()
    latest_arrival = (
        _int(latest_arrival_raw, label="latest stressed arrival")
        if latest_arrival_raw
        else risk_end + 1
    )
    recovery_anchor = max(start, risk_end + 1, latest_arrival)
    recovery_day: int | None = None
    for day in range(recovery_anchor, end - 5):
        if all(
            incident["backlog"][probe] <= baseline["backlog"][probe] + 1e-6
            for probe in range(day, end + 1)
        ):
            recovery_day = day
            break
    kpis = {
        "impact_window_start_day": start,
        "impact_window_end_day": end,
        "impact_window_days": end - start + 1,
        "service_baseline_pct": 100.0 * base_on_due / base_demand
        if base_demand
        else 100.0,
        "service_incident_pct": 100.0 * incident_on_due / base_demand
        if base_demand
        else 100.0,
        "service_loss_pp": service_loss_pp,
        "on_due_units_lost": base_on_due - incident_on_due,
        "backlog_qty_days_delta": incident_backlog_days - base_backlog_days,
        "max_backlog_qty_delta": incident_max_backlog - base_max_backlog,
        "production_released_loss_qty": base_production - incident_production,
        "first_component_stock_divergence_day": _first_divergence(
            baseline["component_stock"],
            incident["component_stock"],
            start=start,
            end=end,
        ),
        "first_production_divergence_day": _first_divergence(
            baseline["production_released"],
            incident["production_released"],
            start=start,
            end=end,
        ),
        "first_service_divergence_day": _first_divergence(
            baseline["served_on_due"], incident["served_on_due"], start=start, end=end
        ),
        "first_backlog_divergence_day": _first_divergence(
            baseline["backlog"], incident["backlog"], start=start, end=end
        ),
        "backlog_recovery_day": recovery_day,
        "backlog_recovered_within_window": recovery_day is not None,
        "backlog_recovery_observation_anchor_day": recovery_anchor,
        "backlog_recovery_rule": (
            "after latest stressed arrival, incident backlog <= baseline for at least "
            "7 days and without relapse through impact-window end"
        ),
        "cross_arm_lot_matching_used": False,
    }
    expected = dossier["incident_metric"]
    comparisons = {
        "impact_service_loss_fed_product_pp": service_loss_pp,
        "impact_on_due_loss_fed_product_qty": base_on_due - incident_on_due,
        "impact_production_loss_fed_product_qty": base_production - incident_production,
    }
    for field, actual in comparisons.items():
        raw = str(expected.get(field) or "").strip()
        if raw and not math.isclose(
            actual, _float(raw, label=f"campaign {field}"), abs_tol=1e-5, rel_tol=1e-9
        ):
            raise ReplayContractError(
                f"Replay KPI differs from signed campaign metric: {field}"
            )
    return curve_rows, lag_rows, kpis


def _render_html(dossiers: Sequence[Mapping[str, Any]]) -> str:
    payload = json.dumps(dossiers, ensure_ascii=False, separators=(",", ":")).replace(
        "</", "<\\/"
    )
    return f"""<!doctype html>
<html lang="fr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Dossiers fournisseurs V4 — lots et impacts</title>
<style>
body{{margin:0;background:#eef3f8;color:#10233f;font:15px system-ui,sans-serif}}main{{max-width:1180px;margin:auto;padding:24px}}
h1{{margin:0 0 8px}}.note,.card,.panel{{background:white;border:1px solid #d8e2ec;border-radius:15px;padding:16px;margin:12px 0}}
.tabs button{{border:1px solid #bfd0e1;background:white;border-radius:20px;padding:8px 13px;margin:4px;cursor:pointer}}.tabs button.on{{background:#123c69;color:white}}
.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:10px}}.k{{font-size:25px;font-weight:750}}.muted{{color:#5b6d83}}
canvas{{width:100%;height:330px}}table{{width:100%;border-collapse:collapse;font-size:13px}}th,td{{text-align:left;border-bottom:1px solid #e4ebf2;padding:7px}}
select{{padding:7px}}.tag{{display:inline-block;background:#e8f1ff;border-radius:12px;padding:4px 8px;margin-right:5px}}
</style></head><body><main><h1>Dossiers fournisseurs prioritaires V4</h1>
<div class="note"><b>SIMULÉ.</b> Chaque dossier compare la même configuration et la même graine, avec ou sans l’hypothèse fournisseur. La fenêtre de 42 jours a été choisie pour obtenir une forte exposition commune : elle ne représente ni un incident moyen ni sa probabilité. Les identifiants de lots sont propres à chaque calcul : les délais sont comparés à volume cumulé égal, jamais en prétendant suivre « le même lot » entre deux simulations. Aucun incident qualité et aucun risque fournisseur endogène ne sont activés.</div>
<div class="tabs" id="tabs"></div><section id="view"></section></main>
<script>const DATA={payload};const F=n=>new Intl.NumberFormat('fr-FR',{{maximumFractionDigits:2}}).format(Number(n||0));
let current=0;function chain(d){{return `<div class="panel"><h3>Chaîne de lots consultable</h3><p class="muted">Extrait compact ; les CSV du dossier conservent toutes les lignes natives.</p><table><thead><tr><th>Expédition / jour</th><th>Lot MP reçu</th><th>Campagne / batch</th><th>Lot PF descendant</th><th>Nœud client agrégé</th></tr></thead><tbody>${{d.trace_preview.map(r=>`<tr><td>${{r.shipment_id}} / J${{r.decision_day}}</td><td>${{r.material_receipt}}</td><td>${{r.campaigns_batches||'—'}}</td><td>${{r.finished_lots||'—'}}</td><td>${{r.clients||'—'}}</td></tr>`).join('')}}</tbody></table></div>`}}function draw(rows,metric){{const c=document.querySelector('canvas'),x=c.getContext('2d'),dpr=devicePixelRatio||1,W=c.clientWidth,H=330;c.width=W*dpr;c.height=H*dpr;x.scale(dpr,dpr);x.clearRect(0,0,W,H);const r=rows.filter(v=>v.metric===metric),vals=r.flatMap(v=>[v.baseline_value,v.incident_value]),hi=Math.max(1,...vals),p={{l:48,r:14,t:15,b:30}},iw=W-p.l-p.r,ih=H-p.t-p.b,X=i=>p.l+iw*i/Math.max(1,r.length-1),Y=v=>p.t+ih-v/hi*ih;x.strokeStyle='#dbe5ef';for(let i=0;i<5;i++){{let y=p.t+ih*i/4;x.beginPath();x.moveTo(p.l,y);x.lineTo(W-p.r,y);x.stroke();}}function line(key,col){{x.strokeStyle=col;x.lineWidth=2;x.beginPath();r.forEach((v,i)=>i?x.lineTo(X(i),Y(v[key])):x.moveTo(X(i),Y(v[key])));x.stroke()}}line('baseline_value','#70839a');line('incident_value','#e33b2e');x.fillStyle='#50647b';x.fillText('J'+r[0]?.day,p.l,H-8);x.fillText('J'+r.at(-1)?.day,W-48,H-8)}}
function render(i){{current=i;document.querySelectorAll('#tabs button').forEach((b,j)=>b.classList.toggle('on',i===j));const d=DATA[i],k=d.kpis,t=d.trace_counts;document.querySelector('#view').innerHTML=`<div class="panel"><span class="tag">${{d.operating_point_id}}</span><span class="tag">${{d.mechanism_label}}</span><h2>${{d.supplier_id}} — ${{d.item_id}} vers ${{d.dst_node_id}}</h2><p class="muted">Signal de priorité issu de la campagne V4 ; graine ${{d.seed}}, choisie près de la médiane des ${{d.exercised_seed_count}} répétitions sur 30 où le flux a réellement été exposé.</p><div class="grid"><div class="card"><div class="k">${{F(k.service_loss_pp)}} pt</div>Perte de service</div><div class="card"><div class="k">${{F(k.on_due_units_lost)}}</div>Unités à l'heure perdues</div><div class="card"><div class="k">${{F(k.production_released_loss_qty)}}</div>Production libérée perdue</div><div class="card"><div class="k">${{k.backlog_recovery_day===null?'Non démontré':('J'+k.backlog_recovery_day)}}</div>Rattrapage sans rechute jusqu'à la fin</div></div></div><div class="panel"><h3>Courbes comparées</h3><select id="metric"><option value="component_stock">Stock composant</option><option value="production_released">Production libérée</option><option value="wip">Encours</option><option value="served_on_due">Service à l'heure</option><option value="backlog">Retard client agrégé</option></select><p><span style="color:#70839a">■ Sans incident</span> &nbsp; <span style="color:#e33b2e">■ Incident sans action</span></p><canvas></canvas></div><div class="panel"><h3>Preuve physique native</h3><div class="grid"><div><b>${{t.shipments}}</b><br>expéditions touchées</div><div><b>${{t.material_receipts}}</b><br>lots MP reçus</div><div><b>${{t.consumptions}}</b><br>événements de consommation</div><div><b>${{t.campaigns}}</b><br>campagnes</div><div><b>${{t.batches}}</b><br>batches</div><div><b>${{t.finished_lots}}</b><br>lots PF descendants</div><div><b>${{t.clients}}</b><br>nœuds clients agrégés descendants</div></div><p class="muted">Le contact généalogique s'arrête ici au nœud client agrégé C-XXXXX : aucun client réel ni aucune commande réelle n'est nommé. La perte causale vient de la comparaison des courbes, pas de la quantité brute d'un événement généalogique.</p></div>${{chain(d)}}<div class="panel"><h3>Retard à volume cumulé égal</h3><table><thead><tr><th>Volume de référence</th><th>Jour sans incident</th><th>Jour avec incident</th><th>Retard</th></tr></thead><tbody>${{d.lags.map(r=>`<tr><td>${{Math.round(r.baseline_volume_fraction*100)}} % (${{F(r.threshold_qty)}})</td><td>${{r.baseline_reach_day??'—'}}</td><td>${{r.incident_reach_day??'non atteint'}}</td><td>${{r.status==='not_calculable_zero_reference_volume'?'non calculable':r.lag_days===''?'censuré':r.lag_days+' j'}}</td></tr>`).join('')}}</tbody></table></div>`;const s=document.querySelector('#metric');s.onchange=()=>draw(d.curves,s.value);draw(d.curves,s.value)}}
DATA.forEach((d,i)=>{{const b=document.createElement('button');b.textContent=d.dossier_id;b.onclick=()=>render(i);document.querySelector('#tabs').appendChild(b)}});if(DATA.length)render(0);
</script></body></html>"""


def finalize_replay(replay_root: Path) -> dict[str, Any]:
    """Validate all arms, extract native paths and build an offline report."""

    replay_root = replay_root.resolve()
    plan = load_and_validate_plan(replay_root)
    receipt_path = replay_root / "replay_run_receipt.json"
    receipt = _read_json(receipt_path)
    if receipt.get("schema_version") != RUN_RECEIPT_SCHEMA_VERSION:
        raise ReplayContractError("Replay run receipt schema changed")
    _verify_signed_payload(receipt, "run_receipt_signature", "run receipt")
    if receipt.get("status") != "complete_validated" or receipt.get(
        "plan_signature"
    ) != plan.get("plan_signature"):
        raise ReplayContractError("Run receipt does not close the current replay plan")
    final_root = replay_root / "finalized"
    html_path = replay_root / "OUVRIR_DOSSIERS_PRIORITAIRES_LOTS_V4.html"
    if (final_root.exists() and any(final_root.iterdir())) or html_path.exists():
        raise ReplayContractError("Refusing to overwrite finalized replay outputs")
    final_root.mkdir(parents=True, exist_ok=True)

    report_payload: list[dict[str, Any]] = []
    dossier_validations: list[dict[str, Any]] = []
    kpi_rows: list[dict[str, Any]] = []
    for dossier in plan["dossiers"]:
        pair_proof = _validate_pair(dossier)
        dossier_dir = final_root / "dossiers" / dossier["dossier_id"]
        trace = extract_native_trace(
            Path(dossier["arms"]["incident"]["run_dir"]), dossier=dossier
        )
        schemas = {
            "shipment_to_mp_lots": (
                "arm",
                "incident_event_id",
                "shipment_id",
                "risk_decision_day",
                "source_lot_id",
                "source_node_id",
                "source_item_id",
                "receipt_lot_id",
                "receipt_node_id",
                "receipt_item_id",
                "parent_qty",
                "child_qty",
                "uom_guard",
            ),
            "exposed_consumption_wip": (
                "arm",
                "incident_event_id",
                "shipment_ids",
                "material_lot_id",
                "day",
                "node_id",
                "item_id",
                "consumed_qty",
                "uom",
                "campaign_id",
                "batch_id",
                "wip_start_qty",
                "wip_end_qty",
                "released_qty_same_day",
                "released_lot_id_same_day",
                "binding_input_item_id",
                "plan_reason",
                "campaign_status",
                "campaign_wip_qty_end_of_run",
                "campaign_blocked_lot_qty",
            ),
            "exposed_finished_lots": (
                "arm",
                "incident_event_id",
                "shipment_ids",
                "finished_lot_id",
                "day",
                "node_id",
                "item_id",
                "released_qty",
                "uom",
                "campaign_id",
                "exposed_parent_lot_ids",
                "claim",
            ),
            "exposed_client_events": (
                "arm",
                "incident_event_id",
                "shipment_ids",
                "client_lot_id",
                "day",
                "client_node_id",
                "item_id",
                "service_event_qty_on_contacted_lot",
                "uom",
                "claim",
            ),
        }
        for name, rows in trace.items():
            _write_csv(dossier_dir / f"{name}.csv", rows, schemas[name])
        curves, lags, kpis = _paired_curves_and_kpis(
            Path(dossier["arms"]["baseline"]["run_dir"]),
            Path(dossier["arms"]["incident"]["run_dir"]),
            dossier=dossier,
        )
        _write_csv(
            dossier_dir / "paired_daily_curves.csv",
            curves,
            (
                "day",
                "metric",
                "baseline_value",
                "incident_value",
                "delta_incident_minus_baseline",
            ),
        )
        _write_csv(
            dossier_dir / "cumulative_release_lag.csv",
            lags,
            (
                "baseline_volume_fraction",
                "threshold_qty",
                "baseline_reach_day",
                "incident_reach_day",
                "lag_days",
                "incident_censored_at_window_end",
                "status",
                "claim",
            ),
        )
        _write_json(dossier_dir / "dossier_kpis.json", kpis)
        trace_counts = {
            "shipments": len(
                {row["shipment_id"] for row in trace["shipment_to_mp_lots"]}
            ),
            "material_receipts": len(
                {row["receipt_lot_id"] for row in trace["shipment_to_mp_lots"]}
            ),
            "consumptions": len(trace["exposed_consumption_wip"]),
            "campaigns": len(
                {
                    row["campaign_id"]
                    for row in trace["exposed_consumption_wip"]
                    if row["campaign_id"]
                }
            ),
            "batches": len(
                {
                    row["batch_id"]
                    for row in trace["exposed_consumption_wip"]
                    if row["batch_id"]
                }
            ),
            "finished_lots": len(trace["exposed_finished_lots"]),
            "client_events": len(trace["exposed_client_events"]),
            "clients": len(
                {
                    row["client_node_id"]
                    for row in trace["exposed_client_events"]
                    if row["client_node_id"]
                }
            ),
        }
        trace_preview: list[dict[str, Any]] = []
        for receipt_row in trace["shipment_to_mp_lots"][:30]:
            shipment_id = receipt_row["shipment_id"]

            def touched(row: Mapping[str, Any]) -> bool:
                return shipment_id in str(row.get("shipment_ids") or "").split("|")

            consumptions = [
                row for row in trace["exposed_consumption_wip"] if touched(row)
            ]
            finished = [row for row in trace["exposed_finished_lots"] if touched(row)]
            clients = [row for row in trace["exposed_client_events"] if touched(row)]
            trace_preview.append(
                {
                    "shipment_id": shipment_id,
                    "decision_day": receipt_row["risk_decision_day"],
                    "material_receipt": receipt_row["receipt_lot_id"],
                    "campaigns_batches": ", ".join(
                        sorted(
                            {
                                "/".join(
                                    value
                                    for value in (
                                        str(row.get("campaign_id") or ""),
                                        str(row.get("batch_id") or ""),
                                    )
                                    if value
                                )
                                for row in consumptions
                                if row.get("campaign_id") or row.get("batch_id")
                            }
                        )
                    ),
                    "finished_lots": ", ".join(
                        f"{row['finished_lot_id']} (J{row['day']})" for row in finished
                    ),
                    "clients": ", ".join(
                        f"{row['client_node_id']} / {row['client_lot_id']} (J{row['day']})"
                        for row in clients
                    ),
                }
            )
        status = (
            "native_trace_to_client"
            if trace_counts["client_events"]
            else (
                "native_trace_to_finished_product"
                if trace_counts["finished_lots"]
                else (
                    "native_trace_to_wip"
                    if trace_counts["consumptions"]
                    else "native_trace_to_material_receipt_only"
                )
            )
        )
        dossier_validation = {
            "dossier_id": dossier["dossier_id"],
            "status": status,
            "pair_proof": pair_proof,
            "trace_counts": trace_counts,
            "cross_arm_lot_matching_used": False,
            "quality_incident_included": False,
            "state_dependent_supplier_risks_enabled": False,
        }
        dossier_validations.append(dossier_validation)
        kpi_rows.append({"dossier_id": dossier["dossier_id"], **kpis, **trace_counts})
        mechanism = str(dossier["priority"]["mechanism"])
        report_payload.append(
            {
                "dossier_id": dossier["dossier_id"],
                "operating_point_id": dossier["priority"]["operating_point_id"],
                "mechanism": mechanism,
                "mechanism_label": (
                    "Retard transport +120 jours"
                    if mechanism == "transport_delay"
                    else "Fiabilité × 0,5 — 50 % du volume normalement livrable"
                ),
                "supplier_id": dossier["priority"]["supplier_id"],
                "item_id": dossier["priority"]["item_id"],
                "dst_node_id": dossier["priority"]["dst_node_id"],
                "target_product_id": dossier["priority"]["target_product_id"],
                "seed": dossier["seed"],
                "exercised_seed_count": _int(
                    dossier["incident_metric"].get(
                        "representative_valid_exercised_seed_count"
                    ),
                    label="report exercised-seed count",
                ),
                "kpis": kpis,
                "trace_counts": trace_counts,
                "trace_preview": trace_preview,
                "curves": curves,
                "lags": lags,
            }
        )

    _write_csv(final_root / "dossier_kpis.csv", kpi_rows)
    html_path.write_text(_render_html(report_payload), encoding="utf-8")
    artifact_paths = sorted(
        [path for path in final_root.rglob("*") if path.is_file()] + [html_path]
    )
    inventory_rows = [
        {
            "relative_path": path.relative_to(replay_root).as_posix(),
            "size_bytes": path.stat().st_size,
            "sha256": sha256_file(path),
        }
        for path in artifact_paths
    ]
    inventory_path = final_root / "artifact_inventory.csv"
    _write_csv(
        inventory_path,
        inventory_rows,
        ("relative_path", "size_bytes", "sha256"),
    )
    validation: dict[str, Any] = {
        "schema_version": VALIDATION_SCHEMA_VERSION,
        "status": "complete_validated",
        "created_at_utc": utc_now(),
        "plan_signature": plan["plan_signature"],
        "run_receipt_signature": receipt["run_receipt_signature"],
        "dossiers": dossier_validations,
        "artifact_inventory": str(inventory_path),
        "artifact_inventory_sha256": sha256_file(inventory_path),
        "standalone_html": str(html_path),
        "standalone_html_sha256": sha256_file(html_path),
        "lot_identity_contract": plan["lot_identity_contract"],
    }
    validation["validation_signature"] = stable_sha256(validation)
    _write_json(final_root / "replay_validation.json", validation)
    return validation


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    plan = subparsers.add_parser("plan", help="Create the signed replay plan only")
    plan.add_argument("--campaign-root", type=Path, required=True)
    plan.add_argument("--results-dir", type=Path, required=True)
    plan.add_argument("--output-root", type=Path, required=True)
    plan.add_argument("--max-dossiers", type=int, default=3)
    plan.add_argument("--selection-csv", type=Path)
    plan.add_argument("--python-executable")
    run = subparsers.add_parser("run", help="Validate or explicitly execute the plan")
    run.add_argument("--replay-root", type=Path, required=True)
    run.add_argument(
        "--execute",
        action="store_true",
        help="Required to launch the simulation engine; without it only validates commands",
    )
    final = subparsers.add_parser(
        "finalize", help="Validate runs and build offline outputs"
    )
    final.add_argument("--replay-root", type=Path, required=True)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        if args.command == "plan":
            result = create_replay_plan(
                campaign_root=args.campaign_root,
                results_dir=args.results_dir,
                output_root=args.output_root,
                max_dossiers=args.max_dossiers,
                selection_csv=args.selection_csv,
                python_executable=args.python_executable,
            )
        elif args.command == "run":
            result = execute_replay(args.replay_root, execute=args.execute)
        else:
            result = finalize_replay(args.replay_root)
    except ReplayContractError as exc:
        print(f"REPLAY V4 INVALID: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
