"""Risk-to-lot impact registry with explicit causality and quantity bounds.

The simulation already emits two complementary ledgers:

* risk events applied to a supplier lane and day;
* physical lot genealogy for transport and production.

This module joins them without pretending that temporal proximity proves an
incremental business impact.  New engine runs may put ``risk_event_ids`` and a
``shipment_id`` directly on shipment/lot rows; those links are labelled
``native_transaction``.  Older runs can still be explored through an exact
scope/day/FIFO reconstruction, but the resulting link is deliberately labelled
``scope_day_association`` and must not be presented as native causality.

Quantities are propagated conservatively through splits and merges.  Transport
preserves mass in one unit.  Production can combine several component units, so
the output exposure is reported as a lower/upper bound: the largest component
exposure fraction is the lower bound and the sum of component fractions (capped
at one) is the upper bound.  This prevents false precision and double counting.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import os
from collections import defaultdict, deque
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

REGISTRY_VERSION = "risk-lot-impact-registry/1.0"
PROVENANCE_VERSION = "risk-lot-impact-provenance/1.0"
EPS = 1e-9

SOURCE_FILES = {
    "assumptions": "assumptions_ledger.csv",
    "state_risk_events": "supplier_state_dependent_risk_events.csv",
    "applied_risk": "supplier_risk_events_applied_daily.csv",
    "supplier_shipments": "production_supplier_shipments_daily.csv",
    "lot_events": "production_lot_events.csv",
    "lot_genealogy": "production_lot_genealogy.csv",
    "production_campaigns": "production_campaigns.csv",
    "demand_service": "production_demand_service_daily.csv",
    "supplier_parameters": "supplier_nominal_parameters.csv",
}

CAMPAIGN_SENTINELS = (
    "canonical_cascade_manifest.json",
    "canonical_cascade_runs.csv",
    "canonical_cascade_commands.json",
    "canonical_cascade_config_snapshot.json",
)

CREATION_EVENT_TYPES = {
    "opening_stock",
    "opening_production_order",
    "external_procurement_receipt",
    "estimated_source_receipt",
    "estimated_capacity_receipt",
    "lane_receipt",
    "production_output",
}

OUTPUT_FILENAMES = {
    "incidents": "risk_impact_incidents.csv",
    "bundles": "risk_impact_exposure_bundles.csv",
    "bundle_events": "risk_impact_bundle_events.csv",
    "entities": "risk_impact_entities.csv",
    "edges": "risk_impact_edges.csv",
    "client_service": "risk_impact_client_service.csv",
    "costs": "risk_impact_costs.csv",
    "quality": "risk_impact_quality.json",
}


@dataclass(frozen=True)
class RiskImpactRegistry:
    incidents: list[dict[str, Any]]
    bundles: list[dict[str, Any]]
    bundle_events: list[dict[str, Any]]
    entities: list[dict[str, Any]]
    edges: list[dict[str, Any]]
    client_service: list[dict[str, Any]]
    costs: list[dict[str, Any]]
    quality: dict[str, Any]


class RiskImpactProvenanceError(ValueError):
    """Raised when detected run or campaign provenance is contradictory."""


class RiskImpactUnitError(ValueError):
    """Raised when an impact edge cannot carry trustworthy endpoint units."""


@dataclass
class _LotImpact:
    lower_qty: float
    upper_qty: float
    lower_share: float
    upper_share: float
    method: str
    causality_level: str
    pre_horizon_origin: bool


def build_risk_impact_registry_from_directory(data_dir: Path) -> RiskImpactRegistry:
    """Build a registry from one simulation arm's ``data`` directory."""

    resolved = _resolve_data_dir(data_dir)
    loaded: dict[str, list[dict[str, str]]] = {}
    source_files: dict[str, dict[str, Any]] = {}
    for source_name, filename in SOURCE_FILES.items():
        rows, source_record = _read_csv_source(
            resolved / filename,
            required=source_name == "lot_events",
        )
        loaded[source_name] = rows
        source_files[source_name] = source_record

    assumption_risk_events = _risk_events_from_assumptions(loaded["assumptions"])
    risk_event_rows = [*assumption_risk_events, *loaded["state_risk_events"]]
    provenance = _build_source_provenance(
        data_dir=resolved,
        source_files=source_files,
        risk_event_rows=risk_event_rows,
    )
    registry = build_risk_impact_registry(
        risk_event_rows=risk_event_rows,
        applied_risk_rows=loaded["applied_risk"],
        shipment_rows=loaded["supplier_shipments"],
        lot_event_rows=loaded["lot_events"],
        genealogy_rows=loaded["lot_genealogy"],
        campaign_rows=loaded["production_campaigns"],
        demand_service_rows=loaded["demand_service"],
        supplier_parameter_rows=loaded["supplier_parameters"],
        source_data_dir=str(resolved),
    )
    quality = dict(registry.quality)
    quality["provenance"] = provenance
    return RiskImpactRegistry(
        incidents=registry.incidents,
        bundles=registry.bundles,
        bundle_events=registry.bundle_events,
        entities=registry.entities,
        edges=registry.edges,
        client_service=registry.client_service,
        costs=registry.costs,
        quality=quality,
    )


def _read_csv_source(
    path: Path,
    *,
    required: bool,
) -> tuple[list[dict[str, str]], dict[str, Any]]:
    """Read one immutable byte snapshot and describe the exact bytes consumed."""

    resolved = Path(path).resolve(strict=False)
    if not resolved.is_file():
        if required:
            raise FileNotFoundError(resolved)
        return [], {
            "filename": resolved.name,
            "path": str(resolved),
            "required": False,
            "exists": False,
            "read_status": "absent_optional",
            "sha256": None,
            "size_bytes": 0,
            "row_count": 0,
        }
    raw = resolved.read_bytes()
    try:
        decoded = raw.decode("utf-8-sig")
        rows = list(csv.DictReader(io.StringIO(decoded, newline="")))
    except (UnicodeDecodeError, csv.Error) as exc:
        raise RiskImpactProvenanceError(
            f"Could not read provenance CSV {resolved}: {exc}"
        ) from exc
    return rows, {
        "filename": resolved.name,
        "path": str(resolved),
        "required": required,
        "exists": True,
        "read_status": "read_from_single_byte_snapshot",
        "sha256": hashlib.sha256(raw).hexdigest(),
        "size_bytes": len(raw),
        "row_count": len(rows),
    }


def _read_json_artifact(
    path: Path,
    *,
    required: bool,
    expected_type: type = dict,
) -> tuple[Any, dict[str, Any] | None]:
    resolved = Path(path).resolve(strict=False)
    if not resolved.is_file():
        if required:
            raise FileNotFoundError(resolved)
        return None, None
    raw = resolved.read_bytes()
    try:
        payload = json.loads(raw.decode("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RiskImpactProvenanceError(
            f"Could not read provenance JSON {resolved}: {exc}"
        ) from exc
    if not isinstance(payload, expected_type):
        raise RiskImpactProvenanceError(
            f"Expected {expected_type.__name__} in {resolved}, got "
            f"{type(payload).__name__}."
        )
    return payload, {
        "filename": resolved.name,
        "path": str(resolved),
        "exists": True,
        "sha256": hashlib.sha256(raw).hexdigest(),
        "size_bytes": len(raw),
    }


def _normalized_path(path: Path | str) -> str:
    return os.path.normcase(str(Path(path).resolve(strict=False)))


def _metadata_path(value: Any, *, relative_to: Path, label: str) -> Path:
    raw = str(value or "").strip()
    if not raw:
        raise RiskImpactProvenanceError(f"Missing declared path for {label}.")
    path = Path(raw)
    if not path.is_absolute():
        path = relative_to / path
    return path.resolve(strict=False)


def _optional_sha256(value: Any, *, label: str) -> str | None:
    raw = str(value or "").strip().lower()
    if not raw:
        return None
    if len(raw) != 64 or any(character not in "0123456789abcdef" for character in raw):
        raise RiskImpactProvenanceError(f"Invalid SHA-256 for {label}: {value!r}")
    return raw


def _require_matching_hash(
    declared: Any,
    actual: str,
    *,
    label: str,
) -> str:
    expected = _optional_sha256(declared, label=label)
    if expected is None:
        raise RiskImpactProvenanceError(f"Missing declared SHA-256 for {label}.")
    if expected != actual:
        raise RiskImpactProvenanceError(
            f"SHA-256 mismatch for {label}: declared={expected}, actual={actual}."
        )
    return actual


def _optional_int(value: Any, *, label: str) -> int | None:
    if value is None or str(value).strip() == "":
        return None
    try:
        numeric = float(str(value).strip())
        parsed = int(numeric)
    except (TypeError, ValueError, OverflowError) as exc:
        raise RiskImpactProvenanceError(
            f"Invalid integer for {label}: {value!r}"
        ) from exc
    if numeric != parsed:
        raise RiskImpactProvenanceError(f"Invalid integer for {label}: {value!r}")
    return parsed


def _discover_campaign_root(run_root: Path) -> Path | None:
    candidates: list[Path] = []
    for candidate in (run_root, *run_root.parents):
        if any((candidate / name).exists() for name in CAMPAIGN_SENTINELS):
            candidates.append(candidate)
    if len(candidates) > 1:
        raise RiskImpactProvenanceError(
            "Ambiguous parent cascade campaigns: "
            + ", ".join(str(path) for path in candidates)
        )
    if not candidates:
        return None
    root = candidates[0]
    missing = [name for name in CAMPAIGN_SENTINELS if not (root / name).is_file()]
    if missing:
        raise RiskImpactProvenanceError(
            f"Incomplete cascade campaign detected at {root}; missing: "
            + ", ".join(missing)
        )
    return root


def _run_summary_context(
    run_root: Path,
    *,
    campaign_detected: bool,
) -> tuple[dict[str, Any], dict[str, Any] | None, dict[str, Any] | None]:
    summary, summary_record = _read_json_artifact(
        run_root / "summaries" / "first_simulation_summary.json",
        required=campaign_detected,
    )
    run_manifest, manifest_record = _read_json_artifact(
        run_root / "run" / "run_manifest.json",
        required=False,
    )
    summary = summary or {}
    policy = summary.get("policy") if isinstance(summary.get("policy"), dict) else {}
    scenario_id = str(summary.get("scenario_id") or "").strip() or None
    seed = _optional_int(policy.get("seed"), label="run summary seed")
    j0_audit = (
        policy.get("warmup_boundary_audit")
        if isinstance(policy.get("warmup_boundary_audit"), dict)
        else {}
    )
    j0_hash = _optional_sha256(
        j0_audit.get("core_state_sha256"),
        label="measurement-start state",
    )
    raw_components = j0_audit.get("component_sha256")
    if raw_components is not None and not isinstance(raw_components, dict):
        raise RiskImpactProvenanceError(
            "measurement-start component_sha256 must be an object."
        )
    component_hashes = {
        str(name): _optional_sha256(
            value,
            label=f"measurement-start component {name}",
        )
        for name, value in sorted((raw_components or {}).items())
    }
    component_hashes = {
        name: value for name, value in component_hashes.items() if value is not None
    }

    risk_policy = (
        policy.get("supplier_risk")
        if isinstance(policy.get("supplier_risk"), dict)
        else {}
    )
    risk_path_raw = str(risk_policy.get("events_csv") or "").strip()
    risk_record: dict[str, Any] | None = None
    configured_risk_rows: list[dict[str, str]] = []
    if risk_path_raw:
        risk_path = Path(risk_path_raw)
        if not risk_path.is_absolute():
            risk_path = run_root / risk_path
        if risk_path.is_file():
            configured_risk_rows, risk_record = _read_csv_source(
                risk_path,
                required=True,
            )
            declared_risk_hash = _optional_sha256(
                risk_policy.get("events_csv_sha256"),
                label="run summary risk events",
            )
            if declared_risk_hash and declared_risk_hash != risk_record["sha256"]:
                raise RiskImpactProvenanceError(
                    "The run summary risk-event hash no longer matches its source CSV."
                )
            event_count = _optional_int(
                risk_policy.get("event_count"),
                label="run summary risk event count",
            )
            if event_count is not None and event_count != len(configured_risk_rows):
                raise RiskImpactProvenanceError(
                    "The run summary risk-event count does not match its source CSV."
                )
        elif campaign_detected:
            raise RiskImpactProvenanceError(
                f"Campaign run risk-event source is missing: {risk_path}"
            )
        else:
            risk_record = {
                "filename": risk_path.name,
                "path": str(risk_path.resolve(strict=False)),
                "exists": False,
                "declared_sha256": _optional_sha256(
                    risk_policy.get("events_csv_sha256"),
                    label="run summary risk events",
                ),
                "read_status": "unavailable_legacy_external_input",
            }
    elif bool(risk_policy.get("enabled")):
        if campaign_detected:
            raise RiskImpactProvenanceError(
                "Supplier risk is enabled but the run summary has no events_csv path."
            )
        risk_record = {
            "filename": None,
            "path": None,
            "exists": False,
            "declared_sha256": _optional_sha256(
                risk_policy.get("events_csv_sha256"),
                label="run summary risk events",
            ),
            "read_status": "unavailable_legacy_external_input",
        }

    control_policy = (
        policy.get("control_schedule")
        if isinstance(policy.get("control_schedule"), dict)
        else {}
    )
    control_path_raw = str(control_policy.get("source_csv") or "").strip()
    control_record: dict[str, Any] | None = None
    configured_control_rows: list[dict[str, str]] = []
    if control_path_raw:
        control_path = Path(control_path_raw)
        if not control_path.is_absolute():
            control_path = run_root / control_path
        if control_path.is_file():
            configured_control_rows, control_record = _read_csv_source(
                control_path,
                required=True,
            )
            declared_control_hash = _optional_sha256(
                control_policy.get("sha256"),
                label="run summary control schedule",
            )
            if (
                declared_control_hash
                and declared_control_hash != control_record["sha256"]
            ):
                raise RiskImpactProvenanceError(
                    "The run summary control-schedule hash no longer matches its source CSV."
                )
            schedule_rows = _optional_int(
                control_policy.get("schedule_rows"),
                label="run summary control schedule row count",
            )
            if schedule_rows is not None and schedule_rows != len(
                configured_control_rows
            ):
                raise RiskImpactProvenanceError(
                    "The run summary control-schedule row count does not match its source CSV."
                )
        elif campaign_detected:
            raise RiskImpactProvenanceError(
                f"Campaign run control-schedule source is missing: {control_path}"
            )
        else:
            control_record = {
                "filename": control_path.name,
                "path": str(control_path.resolve(strict=False)),
                "exists": False,
                "declared_sha256": _optional_sha256(
                    control_policy.get("sha256"),
                    label="run summary control schedule",
                ),
                "read_status": "unavailable_legacy_external_input",
            }
    elif bool(control_policy.get("enabled")):
        if campaign_detected:
            raise RiskImpactProvenanceError(
                "Control schedule is enabled but the run summary has no source_csv path."
            )
        control_record = {
            "filename": None,
            "path": None,
            "exists": False,
            "declared_sha256": _optional_sha256(
                control_policy.get("sha256"),
                label="run summary control schedule",
            ),
            "read_status": "unavailable_legacy_external_input",
        }

    context = {
        "detected": bool(summary_record or manifest_record),
        "root": str(run_root.resolve(strict=False)),
        "summary": summary_record,
        "run_manifest": manifest_record,
        "scenario_id": scenario_id,
        "seed": seed,
        "measurement_start_state_sha256": j0_hash,
        "measurement_start_component_sha256": component_hashes,
        "configured_risk_events": risk_record,
        "configured_control_schedule": control_record,
    }

    if run_manifest:
        declared_root = str(run_manifest.get("output_dir") or "").strip()
        if declared_root and _normalized_path(declared_root) != _normalized_path(
            run_root
        ):
            raise RiskImpactProvenanceError(
                "Generic run manifest output_dir does not identify the source run."
            )
        manifest_scenario = str(run_manifest.get("scenario_id") or "").strip()
        if manifest_scenario and scenario_id and manifest_scenario != scenario_id:
            raise RiskImpactProvenanceError(
                "Scenario identity differs between run manifest and run summary."
            )
        for manifest_field, summary_field in (
            ("sim_days", "sim_days"),
            ("timeline_days", "timeline_days"),
        ):
            manifest_value = _optional_int(
                run_manifest.get(manifest_field),
                label=f"run manifest {manifest_field}",
            )
            summary_value = _optional_int(
                summary.get(summary_field),
                label=f"run summary {summary_field}",
            )
            if (
                manifest_value is not None
                and summary_value is not None
                and manifest_value != summary_value
            ):
                raise RiskImpactProvenanceError(
                    f"{manifest_field} differs between run manifest and summary."
                )
        summary_profile = str(policy.get("output_profile") or "").strip()
        manifest_profile = str(run_manifest.get("output_profile") or "").strip()
        if summary_profile and manifest_profile and summary_profile != manifest_profile:
            raise RiskImpactProvenanceError(
                "Output profile differs between run manifest and run summary."
            )
        capabilities = (
            run_manifest.get("capabilities")
            if isinstance(run_manifest.get("capabilities"), dict)
            else {}
        )
        if "lot_trace_enabled" in capabilities and "lot_trace_enabled" in policy:
            if bool(capabilities["lot_trace_enabled"]) != bool(
                policy["lot_trace_enabled"]
            ):
                raise RiskImpactProvenanceError(
                    "Lot-trace status differs between run manifest and run summary."
                )
    return (
        context,
        summary or None,
        {
            "rows": configured_risk_rows,
            "record": risk_record,
            "control_rows": configured_control_rows,
            "control_record": control_record,
        },
    )


def _campaign_artifact_path(
    mapping: Any,
    key: str,
    expected: Path,
    *,
    campaign_root: Path,
) -> None:
    if not isinstance(mapping, dict) or key not in mapping:
        raise RiskImpactProvenanceError(
            f"Campaign manifest is missing declared output path {key}."
        )
    declared = _metadata_path(
        mapping[key],
        relative_to=campaign_root,
        label=f"campaign output {key}",
    )
    if _normalized_path(declared) != _normalized_path(expected):
        raise RiskImpactProvenanceError(
            f"Campaign output path mismatch for {key}: {declared} != {expected}."
        )


def _command_flag_value(command: Any, flag: str) -> str:
    if not isinstance(command, list):
        raise RiskImpactProvenanceError("Campaign command must be an argument list.")
    positions = [index for index, value in enumerate(command) if str(value) == flag]
    if len(positions) > 1:
        raise RiskImpactProvenanceError(f"Campaign command repeats {flag}.")
    if not positions:
        return ""
    index = positions[0]
    if index + 1 >= len(command):
        raise RiskImpactProvenanceError(f"Campaign command has no value after {flag}.")
    return str(command[index + 1])


def _verify_campaign_context(
    *,
    campaign_root: Path,
    run_root: Path,
    run_context: dict[str, Any],
    summary: dict[str, Any] | None,
    summary_risk: dict[str, Any] | None,
    registry_risk_event_rows: list[dict[str, Any]],
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    manifest_path = campaign_root / "canonical_cascade_manifest.json"
    runs_path = campaign_root / "canonical_cascade_runs.csv"
    commands_path = campaign_root / "canonical_cascade_commands.json"
    config_path = campaign_root / "canonical_cascade_config_snapshot.json"
    manifest, manifest_record = _read_json_artifact(manifest_path, required=True)
    run_rows, runs_record = _read_csv_source(runs_path, required=True)
    commands, commands_record = _read_json_artifact(
        commands_path,
        required=True,
        expected_type=list,
    )
    config, config_record = _read_json_artifact(config_path, required=True)
    assert manifest_record and runs_record and commands_record and config_record

    if manifest.get("status") != "complete":
        raise RiskImpactProvenanceError(
            f"Parent cascade campaign is not complete: {manifest.get('status')!r}."
        )
    if _optional_int(
        manifest.get("failure_count"), label="campaign failure_count"
    ) not in (None, 0):
        raise RiskImpactProvenanceError("Parent cascade campaign contains failures.")
    if _optional_int(
        manifest.get("skipped_fail_fast_count"),
        label="campaign skipped_fail_fast_count",
    ) not in (None, 0):
        raise RiskImpactProvenanceError(
            "Parent cascade campaign contains fail-fast skips."
        )
    declared_run_count = _optional_int(
        manifest.get("run_count"), label="campaign run_count"
    )
    if declared_run_count is None or declared_run_count != len(run_rows):
        raise RiskImpactProvenanceError(
            "Campaign manifest run_count differs from canonical_cascade_runs.csv."
        )
    if len(commands) != len(run_rows):
        raise RiskImpactProvenanceError(
            "Campaign commands and run ledger contain different run counts."
        )

    outputs = manifest.get("outputs")
    output_hashes = manifest.get("output_sha256")
    for key, path, record in (
        ("runs", runs_path, runs_record),
        ("commands", commands_path, commands_record),
        ("config_snapshot", config_path, config_record),
    ):
        _campaign_artifact_path(
            outputs,
            key,
            path,
            campaign_root=campaign_root,
        )
        if not isinstance(output_hashes, dict):
            raise RiskImpactProvenanceError(
                "Campaign manifest has no output_sha256 object."
            )
        _require_matching_hash(
            output_hashes.get(key),
            str(record["sha256"]),
            label=f"campaign {key}",
        )
    config_metadata = manifest.get("config")
    if not isinstance(config_metadata, dict):
        raise RiskImpactProvenanceError("Campaign manifest has no config object.")
    config_snapshot = _metadata_path(
        config_metadata.get("snapshot"),
        relative_to=campaign_root,
        label="campaign config snapshot",
    )
    if _normalized_path(config_snapshot) != _normalized_path(config_path):
        raise RiskImpactProvenanceError(
            "Campaign config.snapshot does not identify the frozen config."
        )
    _require_matching_hash(
        config_metadata.get("sha256"),
        str(config_record["sha256"]),
        label="campaign config snapshot",
    )

    invalid_statuses = sorted(
        {
            str(row.get("status") or "")
            for row in run_rows
            if str(row.get("status") or "") != "ok"
        }
    )
    if invalid_statuses:
        raise RiskImpactProvenanceError(
            "Campaign run ledger contains non-ok statuses: "
            + ", ".join(invalid_statuses)
        )
    matching_rows = [
        row
        for row in run_rows
        if str(row.get("result_dir") or "").strip()
        and _normalized_path(str(row["result_dir"])) == _normalized_path(run_root)
    ]
    if len(matching_rows) != 1:
        raise RiskImpactProvenanceError(
            "Source run must match exactly one row in canonical_cascade_runs.csv."
        )
    run_row = matching_rows[0]
    cascade_id = str(run_row.get("cascade_id") or "").strip()
    variant_id = str(run_row.get("variant_id") or "").strip()
    case_type = str(run_row.get("case_type") or "").strip()
    solution_id = str(run_row.get("solution_id") or "").strip() or None
    seed = _optional_int(run_row.get("seed"), label="campaign run seed")
    if not cascade_id or not variant_id or seed is None:
        raise RiskImpactProvenanceError("Campaign run identity is incomplete.")

    try:
        relative_run = run_root.resolve().relative_to(
            (campaign_root / "runs").resolve()
        )
    except ValueError as exc:
        raise RiskImpactProvenanceError(
            "Campaign run is outside the declared runs directory."
        ) from exc
    if relative_run.parts != (cascade_id, variant_id, f"seed_{seed}"):
        raise RiskImpactProvenanceError(
            "Campaign path identity differs from its run-ledger identity."
        )
    for manifest_key, expected in (
        ("cascade_ids", cascade_id),
        ("variant_ids", variant_id),
        ("seeds", seed),
    ):
        values = manifest.get(manifest_key)
        if not isinstance(values, list) or expected not in values:
            raise RiskImpactProvenanceError(
                f"Campaign manifest {manifest_key} omits source-run identity {expected!r}."
            )

    matching_commands = [
        row
        for row in commands
        if isinstance(row, dict)
        and str(row.get("result_dir") or "").strip()
        and _normalized_path(str(row["result_dir"])) == _normalized_path(run_root)
    ]
    if len(matching_commands) != 1:
        raise RiskImpactProvenanceError(
            "Source run must match exactly one campaign command entry."
        )
    command_entry = matching_commands[0]
    for key, expected in (
        ("cascade_id", cascade_id),
        ("variant_id", variant_id),
        ("seed", seed),
    ):
        observed = command_entry.get(key)
        if key == "seed":
            observed = _optional_int(observed, label="campaign command seed")
        else:
            observed = str(observed or "").strip()
        if observed != expected:
            raise RiskImpactProvenanceError(
                f"Campaign command {key} differs from the run ledger."
            )

    config_cascades = config.get("cascades")
    if not isinstance(config_cascades, list):
        raise RiskImpactProvenanceError("Campaign config has no cascades list.")
    matching_cascades = [
        row
        for row in config_cascades
        if isinstance(row, dict) and str(row.get("id") or "") == cascade_id
    ]
    if len(matching_cascades) != 1:
        raise RiskImpactProvenanceError(
            "Campaign config must define the source cascade exactly once."
        )

    if summary is None:
        raise RiskImpactProvenanceError("Campaign run has no simulation summary.")
    summary_seed = run_context.get("seed")
    if summary_seed is None or summary_seed != seed:
        raise RiskImpactProvenanceError(
            "Simulation summary seed differs from the campaign identity."
        )
    scenario_id = str(run_row.get("scenario_id") or "").strip()
    if scenario_id and run_context.get("scenario_id") != scenario_id:
        raise RiskImpactProvenanceError(
            "Simulation summary scenario differs from the campaign run ledger."
        )
    manifest_scenario = str(manifest.get("scenario_id") or "").strip()
    if scenario_id and manifest_scenario and scenario_id != manifest_scenario:
        raise RiskImpactProvenanceError(
            "Campaign manifest scenario differs from its run ledger."
        )
    campaign_days = _optional_int(manifest.get("days"), label="campaign days")
    summary_days = _optional_int(summary.get("sim_days"), label="summary sim_days")
    row_days = _optional_int(run_row.get("days"), label="campaign row days")
    if (
        len(
            {
                value
                for value in (campaign_days, summary_days, row_days)
                if value is not None
            }
        )
        > 1
    ):
        raise RiskImpactProvenanceError(
            "Simulation horizon differs between campaign, run ledger and summary."
        )

    summary_j0 = run_context.get("measurement_start_state_sha256")
    row_j0 = _optional_sha256(
        run_row.get("measurement_start_state_sha256"),
        label="campaign run measurement-start state",
    )
    if summary_j0 != row_j0:
        raise RiskImpactProvenanceError(
            "Measurement-start state hash differs between summary and campaign ledger."
        )
    raw_row_components = str(
        run_row.get("measurement_start_component_sha256_json") or ""
    ).strip()
    if raw_row_components:
        try:
            row_components = json.loads(raw_row_components)
        except json.JSONDecodeError as exc:
            raise RiskImpactProvenanceError(
                "Campaign run has invalid measurement-start component hashes."
            ) from exc
        if not isinstance(row_components, dict):
            raise RiskImpactProvenanceError(
                "Campaign measurement-start component hashes must be an object."
            )
        normalized_components = {
            str(name): _optional_sha256(
                value,
                label=f"campaign measurement-start component {name}",
            )
            for name, value in sorted(row_components.items())
        }
    else:
        normalized_components = {}
    if normalized_components != run_context.get(
        "measurement_start_component_sha256", {}
    ):
        raise RiskImpactProvenanceError(
            "Measurement-start component hashes differ between summary and campaign ledger."
        )

    raw_command = command_entry.get("command")
    risk_path_raw = str(command_entry.get("risk_events_csv") or "").strip()
    if _command_flag_value(raw_command, "--supplier-risk-events-csv") != risk_path_raw:
        raise RiskImpactProvenanceError(
            "Campaign risk_events_csv differs from its executed command."
        )
    risk_input: dict[str, Any] | None = None
    if risk_path_raw:
        risk_path = _metadata_path(
            risk_path_raw,
            relative_to=campaign_root,
            label="campaign risk events",
        )
        risk_rows, risk_input = _read_csv_source(risk_path, required=True)
        _require_matching_hash(
            run_row.get("risk_events_sha256"),
            str(risk_input["sha256"]),
            label="campaign risk events",
        )
        summary_risk_record = (summary_risk or {}).get("record")
        if not summary_risk_record or not summary_risk_record.get("exists"):
            raise RiskImpactProvenanceError(
                "Campaign risk input is not available through the run summary."
            )
        if summary_risk_record.get("sha256") != risk_input["sha256"]:
            raise RiskImpactProvenanceError(
                "Campaign and run summary identify different risk-event bytes."
            )
        configured_ids = {
            str(row.get("event_id") or "").strip()
            for row in risk_rows
            if str(row.get("event_id") or "").strip()
        }
        ledger_ids = {
            str(row.get("event_id") or "").strip()
            for row in registry_risk_event_rows
            if str(row.get("event_id") or "").strip()
        }
        if not configured_ids or not configured_ids <= ledger_ids:
            raise RiskImpactProvenanceError(
                "Configured campaign risk events are absent from the assumptions/event ledgers read by the registry."
            )
    elif str(run_row.get("risk_events_sha256") or "").strip():
        raise RiskImpactProvenanceError(
            "Campaign run declares a risk hash without a risk-event input."
        )

    schedule_path_raw = str(command_entry.get("control_schedule_csv") or "").strip()
    if _command_flag_value(raw_command, "--control-schedule-csv") != schedule_path_raw:
        raise RiskImpactProvenanceError(
            "Campaign control_schedule_csv differs from its executed command."
        )
    schedule_input: dict[str, Any] | None = None
    if schedule_path_raw:
        schedule_path = _metadata_path(
            schedule_path_raw,
            relative_to=campaign_root,
            label="campaign control schedule",
        )
        _schedule_rows, schedule_input = _read_csv_source(schedule_path, required=True)
        _require_matching_hash(
            run_row.get("control_schedule_sha256"),
            str(schedule_input["sha256"]),
            label="campaign control schedule",
        )
        summary_control_record = (summary_risk or {}).get("control_record")
        if not summary_control_record or not summary_control_record.get("exists"):
            raise RiskImpactProvenanceError(
                "Campaign control schedule is not available through the run summary."
            )
        if summary_control_record.get("sha256") != schedule_input["sha256"]:
            raise RiskImpactProvenanceError(
                "Campaign and run summary identify different control-schedule bytes."
            )
    elif str(run_row.get("control_schedule_sha256") or "").strip():
        raise RiskImpactProvenanceError(
            "Campaign run declares a control-schedule hash without an input."
        )
    elif (summary_risk or {}).get("control_record"):
        raise RiskImpactProvenanceError(
            "Run summary declares a control schedule absent from the campaign command."
        )

    identity = {
        "campaign_id": campaign_root.name,
        "cascade_id": cascade_id,
        "variant_id": variant_id,
        "case_type": case_type,
        "solution_id": solution_id,
        "seed": seed,
        "scenario_id": run_context.get("scenario_id"),
    }
    critical_hashes = {
        "campaign_manifest_sha256": manifest_record["sha256"],
        "campaign_runs_sha256": runs_record["sha256"],
        "campaign_commands_sha256": commands_record["sha256"],
        "campaign_config_snapshot_sha256": config_record["sha256"],
        "risk_events_sha256": risk_input["sha256"] if risk_input else None,
        "control_schedule_sha256": (
            schedule_input["sha256"] if schedule_input else None
        ),
        "measurement_start_state_sha256": summary_j0,
    }
    campaign_context = {
        "detected": True,
        "root": str(campaign_root.resolve()),
        "manifest": manifest_record,
        "runs": {**runs_record, "row_count": len(run_rows)},
        "commands": {**commands_record, "entry_count": len(commands)},
        "config_snapshot": config_record,
        "risk_events": risk_input,
        "control_schedule": schedule_input,
        "matched_run_ledger_row": {
            "cascade_id": cascade_id,
            "variant_id": variant_id,
            "case_type": case_type,
            "solution_id": solution_id,
            "seed": seed,
            "status": str(run_row.get("status") or ""),
            "result_dir": str(run_root.resolve()),
        },
    }
    return campaign_context, identity, critical_hashes


def _build_source_provenance(
    *,
    data_dir: Path,
    source_files: dict[str, dict[str, Any]],
    risk_event_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    run_root = data_dir.parent if data_dir.name.lower() == "data" else data_dir
    campaign_root = _discover_campaign_root(run_root)
    run_context, summary, summary_risk = _run_summary_context(
        run_root,
        campaign_detected=campaign_root is not None,
    )
    identity = {
        "campaign_id": None,
        "cascade_id": None,
        "variant_id": None,
        "case_type": None,
        "solution_id": None,
        "seed": run_context.get("seed"),
        "scenario_id": run_context.get("scenario_id"),
    }
    critical_hashes = {
        "campaign_manifest_sha256": None,
        "campaign_runs_sha256": None,
        "campaign_commands_sha256": None,
        "campaign_config_snapshot_sha256": None,
        "risk_events_sha256": (
            (summary_risk or {}).get("record", {}).get("sha256")
            if isinstance((summary_risk or {}).get("record"), dict)
            else None
        ),
        "control_schedule_sha256": (
            (summary_risk or {}).get("control_record", {}).get("sha256")
            if isinstance((summary_risk or {}).get("control_record"), dict)
            else None
        ),
        "measurement_start_state_sha256": run_context.get(
            "measurement_start_state_sha256"
        ),
    }
    campaign_context: dict[str, Any] = {"detected": False}
    if campaign_root is not None:
        campaign_context, identity, critical_hashes = _verify_campaign_context(
            campaign_root=campaign_root,
            run_root=run_root,
            run_context=run_context,
            summary=summary,
            summary_risk=summary_risk,
            registry_risk_event_rows=risk_event_rows,
        )
        verification_status = "campaign_run_verified"
    elif run_context["detected"]:
        verification_status = "standalone_run_sources_hashed"
    else:
        verification_status = "standalone_data_sources_hashed"
    if run_context.get("summary"):
        critical_hashes["run_summary_sha256"] = run_context["summary"]["sha256"]
    else:
        critical_hashes["run_summary_sha256"] = None
    if run_context.get("run_manifest"):
        critical_hashes["run_manifest_sha256"] = run_context["run_manifest"]["sha256"]
    else:
        critical_hashes["run_manifest_sha256"] = None
    return {
        "schema_version": PROVENANCE_VERSION,
        "verification_status": verification_status,
        "identity": identity,
        "critical_hashes": critical_hashes,
        "source_files": source_files,
        "parent_run": run_context,
        "parent_campaign": campaign_context,
        "integrity_contract": {
            "source_bytes": (
                "Each present source CSV hash covers the exact immutable byte snapshot parsed by the registry."
            ),
            "campaign": (
                "When a campaign sentinel is detected, manifest outputs, hashes, run row, command, "
                "config, risk input and measurement-start identity must all reconcile or the build fails."
            ),
            "legacy": (
                "A data directory outside a campaign remains valid; unavailable external legacy "
                "inputs are reported as unavailable and never invented."
            ),
        },
    }


def _risk_events_from_assumptions(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Recover normalized exogenous and state event metadata embedded by the engine."""

    out: list[dict[str, Any]] = []
    for row in rows:
        if _text(row.get("category")) != "supplier_risk_event":
            continue
        try:
            payload = json.loads(_text(row.get("payload_json")))
        except (TypeError, ValueError, json.JSONDecodeError):
            continue
        if not isinstance(payload, dict) or not _text(payload.get("event_id")):
            continue
        event = dict(payload)
        event.setdefault("source", _text(row.get("source")))
        out.append(event)
    return out


def build_risk_impact_registry(
    *,
    risk_event_rows: list[dict[str, Any]],
    applied_risk_rows: list[dict[str, Any]],
    shipment_rows: list[dict[str, Any]],
    lot_event_rows: list[dict[str, Any]],
    genealogy_rows: list[dict[str, Any]],
    campaign_rows: list[dict[str, Any]] | None = None,
    demand_service_rows: list[dict[str, Any]] | None = None,
    supplier_parameter_rows: list[dict[str, Any]] | None = None,
    source_data_dir: str = "",
) -> RiskImpactRegistry:
    """Create all registry tables from in-memory ledgers.

    The function is intentionally pure: it never mutates a historical run and
    never writes files.  Use :func:`write_risk_impact_registry` to create a new
    versioned output directory.
    """

    campaign_rows = campaign_rows or []
    demand_service_rows = demand_service_rows or []
    supplier_parameter_rows = supplier_parameter_rows or []
    lot_info, lot_events_by_lot = _build_lot_info(lot_event_rows, genealogy_rows)
    applied = _prepare_applied_rows(applied_risk_rows)
    metadata = _prepare_incident_metadata(risk_event_rows, applied)
    bundle_build = _build_exposure_bundles(shipment_rows, applied)
    bundles = bundle_build["bundles"]
    bundle_events = bundle_build["bundle_events"]
    shipment_matches = bundle_build["shipment_matches"]

    source_allocations, source_alloc_quality = _allocate_source_lots(
        bundles,
        lot_event_rows,
    )
    arrival_allocations, arrival_quality = _allocate_receipt_lots(
        bundles,
        source_allocations,
        genealogy_rows,
    )

    service_context = {
        (
            _int(row.get("day")),
            _text(row.get("node_id")),
            _text(row.get("item_id")),
        ): row
        for row in demand_service_rows
    }
    parameter_index = _supplier_parameter_index(supplier_parameter_rows)
    costs = _build_cost_rows(bundles, shipment_matches, parameter_index)

    incident_entities: list[dict[str, Any]] = []
    incident_edges: list[dict[str, Any]] = []
    client_service: list[dict[str, Any]] = []
    incident_summaries: list[dict[str, Any]] = []
    events_to_bundles: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for bridge in bundle_events:
        bundle = next(
            (
                row
                for row in bundles
                if row["exposure_bundle_id"] == bridge["exposure_bundle_id"]
            ),
            None,
        )
        if bundle is not None:
            events_to_bundles[bridge["incident_id"]].append(bundle)

    source_by_bundle: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in source_allocations:
        source_by_bundle[row["exposure_bundle_id"]].append(row)
    arrivals_by_bundle: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in arrival_allocations:
        arrivals_by_bundle[row["exposure_bundle_id"]].append(row)

    genealogy = _prepare_genealogy(genealogy_rows)
    lot_order = _topological_lot_order(lot_info, genealogy)
    campaign_by_id = {
        _text(row.get("campaign_id")): row
        for row in campaign_rows
        if _text(row.get("campaign_id"))
    }

    for incident_id in sorted(metadata):
        incident_bundles = _unique_rows(
            events_to_bundles.get(incident_id, []), "exposure_bundle_id"
        )
        seeds: dict[str, tuple[float, bool, str]] = {}
        native_bundle_count = sum(
            row["causality_level"] == "native_transaction" for row in incident_bundles
        )
        associated_bundle_count = len(incident_bundles) - native_bundle_count

        for bundle in incident_bundles:
            bundle_id = bundle["exposure_bundle_id"]
            for source in source_by_bundle.get(bundle_id, []):
                lot_id = source["source_lot_id"]
                if not lot_id:
                    continue
                info = lot_info.get(lot_id, {})
                incident_entities.append(
                    _entity_row(
                        incident_id=incident_id,
                        entity_type="supplier_source_lot",
                        entity_id=lot_id,
                        lot_id=lot_id,
                        node_id=_text(info.get("node_id")),
                        item_id=_text(info.get("item_id")),
                        day=_int(bundle.get("shipment_day")),
                        lower_qty=_float(source.get("pulled_qty")),
                        upper_qty=_float(source.get("pulled_qty")),
                        total_qty=_float(info.get("created_qty")),
                        uom=_text(info.get("uom")) or _text(bundle.get("uom")),
                        method="shipment_source_lot_fifo_reconstruction",
                        causality_level=_text(bundle.get("causality_level")),
                        pre_horizon_origin=bool(info.get("pre_horizon_origin")),
                        exposure_bundle_id=bundle_id,
                        notes="Source material allocated to the exposed shipment; not propagated as an entire source lot.",
                    )
                )
            for arrival in arrivals_by_bundle.get(bundle_id, []):
                child_lot_id = arrival["receipt_lot_id"]
                qty = _float(arrival.get("attributed_qty"))
                pre_horizon = bool(arrival.get("pre_horizon_origin"))
                existing_qty, existing_pre_horizon, existing_causality = seeds.get(
                    child_lot_id, (0.0, False, "")
                )
                seeds[child_lot_id] = (
                    existing_qty + qty,
                    existing_pre_horizon or pre_horizon,
                    _strongest_causality(
                        existing_causality, _text(bundle.get("causality_level"))
                    ),
                )
                incident_edges.append(
                    _edge_row(
                        incident_id=incident_id,
                        exposure_bundle_id=bundle_id,
                        link_type="risk_exposed_transport",
                        day=_int(arrival.get("arrival_day")),
                        source_lot_id=_text(arrival.get("source_lot_id")),
                        target_lot_id=child_lot_id,
                        genealogy=arrival,
                        source_qty_lower=qty,
                        source_qty_upper=qty,
                        target_qty_lower=qty,
                        target_qty_upper=qty,
                        method=_text(arrival.get("attribution_method")),
                        causality_level=_text(bundle.get("causality_level")),
                        shipment_id=_text(bundle.get("shipment_id")),
                        pre_horizon_origin=pre_horizon,
                        notes="Risk exposure enters physical lot genealogy at this receipt.",
                    )
                )

        impacts, propagation_edges = _propagate_incident(
            incident_id,
            seeds,
            lot_info,
            genealogy,
            lot_order,
        )
        incident_edges.extend(propagation_edges)
        incident_entities.extend(
            _impact_entity_rows(
                incident_id, impacts, lot_info, lot_events_by_lot, campaign_by_id
            )
        )
        incident_service = _client_service_rows(
            incident_id,
            impacts,
            lot_info,
            lot_events_by_lot,
            service_context,
        )
        client_service.extend(incident_service)
        incident_edges.extend(_service_edge_rows(incident_service, impacts))
        incident_summaries.append(
            _incident_summary(
                metadata[incident_id],
                incident_bundles,
                impacts,
                lot_info,
                incident_service,
                costs,
                native_bundle_count=native_bundle_count,
                associated_bundle_count=associated_bundle_count,
            )
        )

    incident_entities = _aggregate_entity_rows(incident_entities)
    incident_edges = _attach_and_validate_edge_units(
        _deduplicate_edges(incident_edges), incident_entities
    )
    quality = _quality_report(
        source_data_dir=source_data_dir,
        incident_count=len(metadata),
        applied_rows=applied,
        bundles=bundles,
        bundle_events=bundle_events,
        source_allocations=source_allocations,
        arrival_allocations=arrival_allocations,
        source_alloc_quality=source_alloc_quality,
        arrival_quality=arrival_quality,
        entities=incident_entities,
        edges=incident_edges,
        client_service=client_service,
    )
    return RiskImpactRegistry(
        incidents=incident_summaries,
        bundles=bundles,
        bundle_events=bundle_events,
        entities=incident_entities,
        edges=incident_edges,
        client_service=client_service,
        costs=costs,
        quality=quality,
    )


def write_risk_impact_registry(
    registry: RiskImpactRegistry, output_dir: Path
) -> dict[str, Path]:
    """Write the registry into a new directory, refusing silent overwrite."""

    output_dir = Path(output_dir)
    if output_dir.exists() and any(output_dir.iterdir()):
        raise FileExistsError(
            f"risk impact output directory is not empty: {output_dir}"
        )
    output_dir.mkdir(parents=True, exist_ok=True)
    written: dict[str, Path] = {}
    output_records: dict[str, dict[str, Any]] = {}
    for table_name in (
        "incidents",
        "bundles",
        "bundle_events",
        "entities",
        "edges",
        "client_service",
        "costs",
    ):
        rows = getattr(registry, table_name)
        path = output_dir / OUTPUT_FILENAMES[table_name]
        _write_csv(path, rows)
        persisted_rows, record = _read_csv_source(path, required=True)
        if len(persisted_rows) != len(rows):
            raise RiskImpactProvenanceError(
                f"Registry output row count changed while writing {path.name}."
            )
        written[table_name] = path
        output_records[table_name] = {
            "filename": path.name,
            "sha256": record["sha256"],
            "size_bytes": record["size_bytes"],
            "row_count": record["row_count"],
        }
    quality_path = output_dir / OUTPUT_FILENAMES["quality"]
    quality_payload = dict(registry.quality)
    quality_payload["registry_outputs"] = {
        "output_dir": str(output_dir.resolve()),
        "csv_artifacts": output_records,
        "quality_json": {
            "filename": quality_path.name,
            "sha256": None,
            "self_hash_status": "intentionally_excluded_to_avoid_recursive_self_hash",
        },
        "integrity_contract": (
            "SHA-256 and row_count cover every emitted registry CSV after it was "
            "persisted. The quality JSON cannot contain its own stable SHA-256."
        ),
    }
    quality_path.write_text(
        json.dumps(quality_payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    written["quality"] = quality_path
    return written


def _resolve_data_dir(path: Path) -> Path:
    path = Path(path)
    if (path / "production_lot_events.csv").exists():
        return path
    if (path / "data" / "production_lot_events.csv").exists():
        return path / "data"
    raise FileNotFoundError(f"could not find simulation data CSV files below {path}")


def _prepare_applied_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for ordinal, source in enumerate(rows, 1):
        row = dict(source)
        row["_row_number"] = ordinal
        row["_event_ids"] = _split_ids(row.get("event_ids"))
        row["_scope_key"] = _scope_key(
            row.get("day"),
            row.get("supplier_id"),
            row.get("dst_node_id"),
            row.get("item_id"),
        )
        out.append(row)
    return out


def _prepare_incident_metadata(
    risk_event_rows: list[dict[str, Any]],
    applied_rows: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for row in risk_event_rows:
        event_id = _text(row.get("event_id"))
        if event_id:
            out[event_id] = dict(row)
    for row in applied_rows:
        for event_id in row["_event_ids"]:
            out.setdefault(
                event_id,
                {
                    "event_id": event_id,
                    "notes": "Metadata absent from state-dependent event ledger; discovered in applied-risk ledger.",
                },
            )
    return out


def _build_exposure_bundles(
    shipment_rows: list[dict[str, Any]],
    applied_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    applied_by_scope: dict[tuple[Any, ...], list[dict[str, Any]]] = defaultdict(list)
    for row in applied_rows:
        applied_by_scope[row["_scope_key"]].append(row)
    bundles: list[dict[str, Any]] = []
    bridges: list[dict[str, Any]] = []
    shipment_matches: dict[str, dict[str, Any]] = {}
    occurrence_by_signature: dict[str, int] = defaultdict(int)
    for row_number, source in enumerate(shipment_rows, 1):
        row = dict(source)
        native_event_ids = _split_ids(row.get("risk_event_ids") or row.get("event_ids"))
        decision_day = _int(row.get("risk_decision_day"), _int(row.get("day")))
        scope = _scope_key(
            decision_day,
            row.get("src_node_id"),
            row.get("dst_node_id"),
            row.get("item_id"),
        )
        matched_applied = applied_by_scope.get(scope, [])
        inferred_event_ids = sorted(
            {
                event_id
                for applied in matched_applied
                for event_id in applied["_event_ids"]
            }
        )
        event_ids = native_event_ids or inferred_event_ids
        if not event_ids:
            continue
        edge_ids = sorted(
            {
                _text(row.get("edge_id")),
                *(_text(applied.get("edge_id")) for applied in matched_applied),
            }
            - {""}
        )
        edge_id = edge_ids[0] if len(edge_ids) == 1 else _text(row.get("edge_id"))
        shipment_id = _text(row.get("shipment_id"))
        if not shipment_id:
            signature = "|".join(
                [
                    str(_int(row.get("day"))),
                    _text(row.get("src_node_id")),
                    _text(row.get("dst_node_id")),
                    _text(row.get("item_id")),
                    str(_float(row.get("pulled_qty"))),
                    str(_float(row.get("shipped_qty"))),
                    str(_int(row.get("arrival_day"))),
                ]
            )
            occurrence_by_signature[signature] += 1
            shipment_id = "SHIP-RECON-" + _short_hash(
                f"{signature}|{occurrence_by_signature[signature]}"
            )
        bundle_id = "RISK-BUNDLE-" + _short_hash(f"{shipment_id}|{'|'.join(event_ids)}")
        causality_level = (
            "native_transaction" if native_event_ids else "scope_day_association"
        )
        risk_effects = _combined_risk_effects(matched_applied)
        bundle = {
            "registry_version": REGISTRY_VERSION,
            "exposure_bundle_id": bundle_id,
            "overlap_group_id": bundle_id,
            "shipment_id": shipment_id,
            "shipment_source_row": row_number,
            "risk_decision_day": decision_day,
            "shipment_day": _int(row.get("day")),
            "arrival_day": _int(row.get("arrival_day")),
            "supplier_id": _text(row.get("src_node_id")),
            "dst_node_id": _text(row.get("dst_node_id")),
            "item_id": _text(row.get("item_id")),
            "edge_id": edge_id,
            "event_ids": "|".join(event_ids),
            "event_count": len(event_ids),
            "pulled_qty": _round(
                _float(row.get("pulled_qty"), _float(row.get("shipped_qty")))
            ),
            "shipped_qty": _round(_float(row.get("shipped_qty"))),
            "unreliable_loss_qty": _round(
                max(
                    0.0,
                    _float(row.get("pulled_qty"), _float(row.get("shipped_qty")))
                    - _float(row.get("shipped_qty")),
                )
            ),
            "uom": _text(row.get("uom")),
            "lead_days": _int(row.get("lead_days")),
            "transport_cost_actual": _round(_float(row.get("transport_cost"))),
            "purchase_cost_actual_native": _optional_float(row.get("purchase_cost")),
            "causality_level": causality_level,
            "causal_claim_allowed": int(causality_level == "native_transaction"),
            "association_basis": "native shipment identifiers"
            if native_event_ids
            else "exact supplier/destination/item/decision-day scope",
            "quantity_count_rule": "count shipped_qty once per bundle; never sum bridge rows by event",
            "do_not_sum_across_incidents": 1,
            **risk_effects,
        }
        bundles.append(bundle)
        shipment_matches[bundle_id] = {
            "shipment": row,
            "applied_rows": matched_applied,
            "native": bool(native_event_ids),
        }
        for event_id in event_ids:
            bridges.append(
                {
                    "registry_version": REGISTRY_VERSION,
                    "exposure_bundle_id": bundle_id,
                    "overlap_group_id": bundle_id,
                    "incident_id": event_id,
                    "shipment_id": shipment_id,
                    "causality_level": causality_level,
                    "causal_claim_allowed": int(
                        causality_level == "native_transaction"
                    ),
                    "event_exposure_qty_non_additive": bundle["shipped_qty"],
                    "uom": bundle["uom"],
                    "do_not_sum_across_incidents": 1,
                    "notes": "Events in one bundle overlap on the same shipment quantity.",
                }
            )
    return {
        "bundles": bundles,
        "bundle_events": bridges,
        "shipment_matches": shipment_matches,
    }


def _combined_risk_effects(rows: list[dict[str, Any]]) -> dict[str, Any]:
    fields = [
        "stock_multiplier",
        "capacity_multiplier",
        "lead_time_multiplier",
        "lead_time_extra_days",
        "quality_delay_days",
        "reliability_multiplier",
        "quality_yield_multiplier",
        "availability_multiplier",
        "purchase_cost_multiplier",
        "transport_cost_multiplier",
        "external_capacity_multiplier",
        "external_availability_multiplier",
        "external_lead_time_multiplier",
        "external_lead_time_extra_days",
        "external_quality_yield_multiplier",
        "external_cost_multiplier",
        "stock_writeoff_fraction",
    ]
    out: dict[str, Any] = {}
    for field in fields:
        values = [_optional_float(row.get(field)) for row in rows]
        values = [value for value in values if value is not None]
        out[field] = (
            values[0]
            if values and all(abs(value - values[0]) <= EPS for value in values)
            else (values[-1] if values else "")
        )
    return out


def _allocate_source_lots(
    bundles: list[dict[str, Any]],
    lot_event_rows: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    lane_ship_events: list[dict[str, Any]] = []
    lot_created_day: dict[str, int] = {}
    for ordinal, source in enumerate(lot_event_rows, 1):
        lot_id = _text(source.get("lot_id"))
        if lot_id and _text(source.get("event_type")) in CREATION_EVENT_TYPES:
            lot_created_day[lot_id] = min(
                lot_created_day.get(lot_id, _int(source.get("day"))),
                _int(source.get("day")),
            )
        if _text(source.get("event_type")) != "lane_ship":
            continue
        row = dict(source)
        row["_ordinal"] = ordinal
        row["_remaining_qty"] = _float(row.get("qty"))
        lane_ship_events.append(row)
    allocations: list[dict[str, Any]] = []
    native_matched_qty = 0.0
    reconstructed_matched_qty = 0.0
    requested_qty = 0.0
    for bundle in bundles:
        bundle_id = bundle["exposure_bundle_id"]
        needed = _float(bundle.get("pulled_qty"), _float(bundle.get("shipped_qty")))
        requested_qty += needed
        shipment_id = _text(bundle.get("shipment_id"))
        risk_day = _int(bundle.get("risk_decision_day"))
        candidates = [
            event
            for event in lane_ship_events
            if _float(event.get("_remaining_qty")) > EPS
            and (
                (
                    _text(event.get("shipment_id"))
                    and _text(event.get("shipment_id")) == shipment_id
                )
                or (
                    not _text(event.get("shipment_id"))
                    and _int(event.get("day")) == risk_day
                    and _text(event.get("node_id")) == _text(bundle.get("supplier_id"))
                    and _text(event.get("item_id")) == _text(bundle.get("item_id"))
                    and (
                        not _text(bundle.get("edge_id"))
                        or _text(event.get("source_id")) == _text(bundle.get("edge_id"))
                    )
                )
            )
        ]
        candidates.sort(
            key=lambda row: (_int(row.get("day")), _int(row.get("_ordinal")))
        )
        # Legacy ledgers have no explicit marker for supplier-backordered chunks.
        # Never consume a partial FIFO allocation for such a shipment: doing so
        # would steal lot events from the following transaction and manufacture
        # false lineage.  Native shipment IDs are expected to reconcile fully;
        # a shortfall there is likewise kept visible as a data-quality gap.
        if (
            sum(_float(event.get("_remaining_qty")) for event in candidates) + EPS
            < needed
        ):
            continue
        delivered_ratio = min(1.0, _float(bundle.get("shipped_qty")) / max(EPS, needed))
        for event in candidates:
            if needed <= EPS:
                break
            take = min(needed, _float(event.get("_remaining_qty")))
            if take <= EPS:
                continue
            event["_remaining_qty"] = _float(event.get("_remaining_qty")) - take
            needed -= take
            method = (
                "native_shipment_id"
                if _text(event.get("shipment_id"))
                else "scope_day_fifo_reconstruction"
            )
            if method == "native_shipment_id":
                native_matched_qty += take
            else:
                reconstructed_matched_qty += take
            allocations.append(
                {
                    "exposure_bundle_id": bundle_id,
                    "shipment_id": shipment_id,
                    "source_lot_event_id": _text(event.get("event_id")),
                    "source_lot_id": _text(event.get("lot_id")),
                    "source_node_id": _text(event.get("node_id")),
                    "item_id": _text(event.get("item_id")),
                    "edge_id": _text(event.get("source_id"))
                    or _text(bundle.get("edge_id")),
                    "pulled_qty": _round(take),
                    "delivered_equivalent_qty": _round(take * delivered_ratio),
                    "uom": _text(event.get("uom")) or _text(bundle.get("uom")),
                    "attribution_method": method,
                    "causality_level": _text(bundle.get("causality_level")),
                    "pre_horizon_origin": lot_created_day.get(
                        _text(event.get("lot_id")), _int(event.get("day"))
                    )
                    < 0,
                }
            )
    matched = native_matched_qty + reconstructed_matched_qty
    quality = {
        "requested_source_allocation_qty": _round(requested_qty),
        "matched_source_allocation_qty": _round(matched),
        "native_source_allocation_qty": _round(native_matched_qty),
        "reconstructed_source_allocation_qty": _round(reconstructed_matched_qty),
        "unmatched_source_allocation_qty": _round(max(0.0, requested_qty - matched)),
        "source_allocation_coverage_ratio": _coverage_ratio(matched, requested_qty),
    }
    return allocations, quality


def _allocate_receipt_lots(
    bundles: list[dict[str, Any]],
    source_allocations: list[dict[str, Any]],
    genealogy_rows: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    links: list[dict[str, Any]] = []
    for ordinal, source in enumerate(genealogy_rows, 1):
        if _text(source.get("link_type")) != "transport":
            continue
        row = dict(source)
        row["_ordinal"] = ordinal
        row["_remaining_qty"] = _float(row.get("parent_qty"))
        links.append(row)
    by_bundle: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in source_allocations:
        by_bundle[row["exposure_bundle_id"]].append(row)
    output: list[dict[str, Any]] = []
    expected_qty = 0.0
    expected_in_horizon_qty = 0.0
    outside_horizon_qty = 0.0
    matched_qty = 0.0
    max_genealogy_day = max((_int(row.get("day")) for row in genealogy_rows), default=0)
    for bundle in bundles:
        bundle_id = bundle["exposure_bundle_id"]
        for source in by_bundle.get(bundle_id, []):
            needed = _float(source.get("delivered_equivalent_qty"))
            expected_qty += needed
            if _int(bundle.get("arrival_day")) > max_genealogy_day:
                outside_horizon_qty += needed
            else:
                expected_in_horizon_qty += needed
            candidates = [
                link
                for link in links
                if _float(link.get("_remaining_qty")) > EPS
                and _int(link.get("day")) == _int(bundle.get("arrival_day"))
                and _text(link.get("parent_lot_id"))
                == _text(source.get("source_lot_id"))
                and _text(link.get("parent_item_id")) == _text(bundle.get("item_id"))
                and (
                    not _text(link.get("shipment_id"))
                    or _text(link.get("shipment_id"))
                    == _text(bundle.get("shipment_id"))
                )
                and (
                    not _text(bundle.get("edge_id"))
                    or _text(link.get("source_id")) == _text(bundle.get("edge_id"))
                )
            ]
            candidates.sort(key=lambda row: _int(row.get("_ordinal")))
            for link in candidates:
                if needed <= EPS:
                    break
                take = min(needed, _float(link.get("_remaining_qty")))
                if take <= EPS:
                    continue
                link["_remaining_qty"] = _float(link.get("_remaining_qty")) - take
                needed -= take
                matched_qty += take
                output.append(
                    {
                        "exposure_bundle_id": bundle_id,
                        "shipment_id": _text(bundle.get("shipment_id")),
                        "arrival_day": _int(bundle.get("arrival_day")),
                        "source_lot_id": _text(link.get("parent_lot_id")),
                        "source_node_id": _text(link.get("parent_node_id")),
                        "receipt_lot_id": _text(link.get("child_lot_id")),
                        "receipt_node_id": _text(link.get("child_node_id")),
                        "item_id": _text(link.get("child_item_id")),
                        "edge_id": _text(link.get("source_id")),
                        "parent_qty": _float(link.get("parent_qty")),
                        "child_qty": _float(link.get("child_qty")),
                        "attributed_qty": _round(take),
                        "attribution_method": (
                            "native_shipment_id_to_transport_genealogy"
                            if _text(link.get("shipment_id"))
                            else "shipment_source_lot_to_transport_genealogy_fifo"
                        ),
                        "pre_horizon_origin": bool(source.get("pre_horizon_origin")),
                        "notes": _text(link.get("notes")),
                    }
                )
    quality = {
        "max_genealogy_day": max_genealogy_day,
        "expected_receipt_lineage_qty": _round(expected_qty),
        "expected_receipt_lineage_in_horizon_qty": _round(expected_in_horizon_qty),
        "receipt_qty_arriving_after_horizon": _round(outside_horizon_qty),
        "matched_receipt_lineage_qty": _round(matched_qty),
        "unmatched_receipt_lineage_qty": _round(max(0.0, expected_qty - matched_qty)),
        "unmatched_receipt_lineage_in_horizon_qty": _round(
            max(0.0, expected_in_horizon_qty - matched_qty)
        ),
        "receipt_lineage_coverage_ratio": _coverage_ratio(matched_qty, expected_qty),
        "receipt_lineage_in_horizon_coverage_ratio": _coverage_ratio(
            matched_qty, expected_in_horizon_qty
        ),
    }
    return output, quality


def _build_lot_info(
    lot_event_rows: list[dict[str, Any]],
    genealogy_rows: list[dict[str, Any]],
) -> tuple[dict[str, dict[str, Any]], dict[str, list[dict[str, Any]]]]:
    events_by_lot: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in lot_event_rows:
        lot_id = _text(row.get("lot_id"))
        if lot_id:
            events_by_lot[lot_id].append(row)
    info: dict[str, dict[str, Any]] = {}
    for lot_id, events in events_by_lot.items():
        ordered = sorted(
            events, key=lambda row: (_int(row.get("day")), _text(row.get("event_id")))
        )
        creation = next(
            (
                row
                for row in ordered
                if _text(row.get("event_type")) in CREATION_EVENT_TYPES
            ),
            ordered[0],
        )
        created_qty = _float(creation.get("qty"))
        if created_qty <= EPS:
            created_qty = max(
                (_float(row.get("qty_after")) for row in ordered), default=0.0
            )
        notes = " ".join(_text(row.get("notes")) for row in ordered).lower()
        info[lot_id] = {
            "lot_id": lot_id,
            "created_day": _int(creation.get("day")),
            "created_qty": created_qty,
            "node_id": _text(creation.get("node_id")),
            "item_id": _text(creation.get("item_id")),
            "uom": _text(creation.get("uom")),
            "creation_event_type": _text(creation.get("event_type")),
            "production_campaign_id": _text(creation.get("production_campaign_id")),
            "pre_horizon_origin": _int(creation.get("day")) < 0
            or "pre-horizon" in notes
            or "initial" in notes,
            "aggregate_origin": "aggregate pipeline" in notes
            or "without scheduled parent" in notes,
        }
    for row in genealogy_rows:
        child = _text(row.get("child_lot_id"))
        parent = _text(row.get("parent_lot_id"))
        for lot_id, prefix in ((child, "child"), (parent, "parent")):
            if not lot_id:
                continue
            current = info.setdefault(
                lot_id,
                {
                    "lot_id": lot_id,
                    "created_day": _int(row.get("day")),
                    "created_qty": 0.0,
                    "node_id": _text(row.get(f"{prefix}_node_id")),
                    "item_id": _text(row.get(f"{prefix}_item_id")),
                    "uom": "",
                    "creation_event_type": "genealogy_only",
                    "production_campaign_id": _text(row.get("production_campaign_id")),
                    "pre_horizon_origin": _int(row.get("day")) < 0,
                    "aggregate_origin": False,
                },
            )
            if prefix == "child":
                current["created_qty"] = max(
                    _float(current.get("created_qty")), _float(row.get("child_qty"))
                )
    return info, dict(events_by_lot)


def _prepare_genealogy(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for ordinal, source in enumerate(rows, 1):
        parent = _text(source.get("parent_lot_id"))
        child = _text(source.get("child_lot_id"))
        if not parent or not child:
            continue
        row = dict(source)
        row["_ordinal"] = ordinal
        out.append(row)
    return out


def _topological_lot_order(
    lot_info: dict[str, dict[str, Any]],
    genealogy: list[dict[str, Any]],
) -> list[str]:
    children: dict[str, set[str]] = defaultdict(set)
    indegree: dict[str, int] = {lot_id: 0 for lot_id in lot_info}
    for row in genealogy:
        parent = _text(row.get("parent_lot_id"))
        child = _text(row.get("child_lot_id"))
        if child not in children[parent]:
            children[parent].add(child)
            indegree[child] = indegree.get(child, 0) + 1
            indegree.setdefault(parent, 0)
    queue = deque(
        sorted(
            (lot_id for lot_id, degree in indegree.items() if degree == 0),
            key=lambda lot: (_int(lot_info.get(lot, {}).get("created_day")), lot),
        )
    )
    order: list[str] = []
    while queue:
        parent = queue.popleft()
        order.append(parent)
        for child in sorted(children.get(parent, set())):
            indegree[child] -= 1
            if indegree[child] == 0:
                queue.append(child)
    if len(order) != len(indegree):
        remaining = sorted(
            set(indegree) - set(order),
            key=lambda lot: (_int(lot_info.get(lot, {}).get("created_day")), lot),
        )
        order.extend(remaining)
    return order


def _propagate_incident(
    incident_id: str,
    seeds: dict[str, tuple[float, bool, str]],
    lot_info: dict[str, dict[str, Any]],
    genealogy: list[dict[str, Any]],
    lot_order: list[str],
) -> tuple[dict[str, _LotImpact], list[dict[str, Any]]]:
    incoming: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in genealogy:
        incoming[_text(row.get("child_lot_id"))].append(row)
    impacts: dict[str, _LotImpact] = {}
    edges: list[dict[str, Any]] = []
    for lot_id, (qty, pre_horizon, causality) in seeds.items():
        total = max(EPS, _float(lot_info.get(lot_id, {}).get("created_qty"), qty))
        clamped = min(total, max(0.0, qty))
        share = clamped / total
        impacts[lot_id] = _LotImpact(
            lower_qty=clamped,
            upper_qty=clamped,
            lower_share=share,
            upper_share=share,
            method="risk_exposed_receipt_seed",
            causality_level=causality or "scope_day_association",
            pre_horizon_origin=pre_horizon,
        )

    for child in lot_order:
        links = incoming.get(child, [])
        if not links:
            continue
        derived = _derive_child_impact(child, links, impacts, lot_info)
        if derived is None:
            continue
        seed = impacts.get(child)
        if seed is not None and seed.method == "risk_exposed_receipt_seed":
            total = max(
                EPS,
                _float(lot_info.get(child, {}).get("created_qty"), derived.upper_qty),
            )
            lower = max(seed.lower_qty, derived.lower_qty)
            upper = min(total, seed.upper_qty + derived.upper_qty)
            impacts[child] = _LotImpact(
                lower_qty=lower,
                upper_qty=upper,
                lower_share=min(1.0, lower / total),
                upper_share=min(1.0, upper / total),
                method="seed_union_downstream_genealogy_bounds",
                causality_level=_strongest_causality(
                    seed.causality_level, derived.causality_level
                ),
                pre_horizon_origin=seed.pre_horizon_origin
                or derived.pre_horizon_origin,
            )
        else:
            impacts[child] = derived
        child_impact = impacts[child]
        for row in links:
            parent = _text(row.get("parent_lot_id"))
            parent_impact = impacts.get(parent)
            if parent_impact is None:
                continue
            link_parent_qty = _float(row.get("parent_qty"))
            source_lower = link_parent_qty * parent_impact.lower_share
            source_upper = link_parent_qty * parent_impact.upper_share
            if source_upper <= EPS:
                continue
            edges.append(
                _edge_row(
                    incident_id=incident_id,
                    exposure_bundle_id="",
                    link_type=_text(row.get("link_type")),
                    day=_int(row.get("day")),
                    source_lot_id=parent,
                    target_lot_id=child,
                    genealogy=row,
                    source_qty_lower=source_lower,
                    source_qty_upper=source_upper,
                    target_qty_lower=child_impact.lower_qty,
                    target_qty_upper=child_impact.upper_qty,
                    method=child_impact.method,
                    causality_level=child_impact.causality_level,
                    shipment_id="",
                    pre_horizon_origin=child_impact.pre_horizon_origin,
                    notes="Downstream exposure propagated through physical genealogy; edge quantities are not additive across parents.",
                )
            )
    return impacts, edges


def _derive_child_impact(
    child: str,
    links: list[dict[str, Any]],
    impacts: dict[str, _LotImpact],
    lot_info: dict[str, dict[str, Any]],
) -> _LotImpact | None:
    contributing = [row for row in links if _text(row.get("parent_lot_id")) in impacts]
    if not contributing:
        return None
    total = max(
        EPS,
        _float(lot_info.get(child, {}).get("created_qty")),
        max((_float(row.get("child_qty")) for row in links), default=0.0),
    )
    link_types = {_text(row.get("link_type")) for row in links}
    pre_horizon = any(
        impacts[_text(row.get("parent_lot_id"))].pre_horizon_origin
        for row in contributing
    )
    causality = ""
    for row in contributing:
        causality = _strongest_causality(
            causality, impacts[_text(row.get("parent_lot_id"))].causality_level
        )
    if link_types == {"transport"}:
        lower = sum(
            _float(row.get("parent_qty"))
            * impacts[_text(row.get("parent_lot_id"))].lower_share
            for row in contributing
        )
        upper = sum(
            _float(row.get("parent_qty"))
            * impacts[_text(row.get("parent_lot_id"))].upper_share
            for row in contributing
        )
        lower = min(total, lower)
        upper = min(total, max(lower, upper))
        return _LotImpact(
            lower_qty=lower,
            upper_qty=upper,
            lower_share=lower / total,
            upper_share=upper / total,
            method="same_item_transport_mass_balance",
            causality_level=causality,
            pre_horizon_origin=pre_horizon,
        )

    component_denominator: dict[str, float] = defaultdict(float)
    component_lower: dict[str, float] = defaultdict(float)
    component_upper: dict[str, float] = defaultdict(float)
    for row in links:
        item = _text(row.get("parent_item_id"))
        qty = _float(row.get("parent_qty"))
        component_denominator[item] += qty
        parent_impact = impacts.get(_text(row.get("parent_lot_id")))
        if parent_impact is not None:
            component_lower[item] += qty * parent_impact.lower_share
            component_upper[item] += qty * parent_impact.upper_share
    lower_fractions = [
        min(1.0, component_lower[item] / max(EPS, denominator))
        for item, denominator in component_denominator.items()
    ]
    upper_fractions = [
        min(1.0, component_upper[item] / max(EPS, denominator))
        for item, denominator in component_denominator.items()
    ]
    lower_share = max(lower_fractions, default=0.0)
    upper_share = min(1.0, sum(upper_fractions))
    upper_share = max(lower_share, upper_share)
    return _LotImpact(
        lower_qty=total * lower_share,
        upper_qty=total * upper_share,
        lower_share=lower_share,
        upper_share=upper_share,
        method="component_mix_union_bounds",
        causality_level=causality,
        pre_horizon_origin=pre_horizon,
    )


def _impact_entity_rows(
    incident_id: str,
    impacts: dict[str, _LotImpact],
    lot_info: dict[str, dict[str, Any]],
    lot_events_by_lot: dict[str, list[dict[str, Any]]],
    campaign_by_id: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    campaigns: dict[str, dict[str, Any]] = {}
    for lot_id, impact in impacts.items():
        info = lot_info.get(lot_id, {})
        entity_type = _lot_entity_type(info)
        out.append(
            _entity_row(
                incident_id=incident_id,
                entity_type=entity_type,
                entity_id=lot_id,
                lot_id=lot_id,
                node_id=_text(info.get("node_id")),
                item_id=_text(info.get("item_id")),
                day=_int(info.get("created_day")),
                lower_qty=impact.lower_qty,
                upper_qty=impact.upper_qty,
                total_qty=_float(info.get("created_qty")),
                uom=_text(info.get("uom")),
                method=impact.method,
                causality_level=impact.causality_level,
                pre_horizon_origin=impact.pre_horizon_origin,
                exposure_bundle_id="",
                notes="Physical exposure; not proof that the incident changed service or cost versus a counterfactual.",
            )
        )
        campaign_id = _text(info.get("production_campaign_id"))
        is_campaign_output = _text(info.get("creation_event_type")) in {
            "production_output",
            "opening_production_order",
        }
        if is_campaign_output and not campaign_id:
            campaign_id = next(
                (
                    _text(row.get("production_campaign_id"))
                    for row in lot_events_by_lot.get(lot_id, [])
                    if _text(row.get("production_campaign_id"))
                ),
                "",
            )
        if is_campaign_output and campaign_id:
            aggregate = campaigns.setdefault(
                campaign_id,
                {
                    "lower": 0.0,
                    "upper": 0.0,
                    "total": 0.0,
                    "uom": _text(info.get("uom")),
                    "node": _text(info.get("node_id")),
                    "item": _text(info.get("item_id")),
                    "day": _int(info.get("created_day")),
                    "causality": impact.causality_level,
                    "pre_horizon": impact.pre_horizon_origin,
                    "methods": set(),
                },
            )
            aggregate["lower"] += impact.lower_qty
            aggregate["upper"] += impact.upper_qty
            aggregate["total"] += _float(info.get("created_qty"))
            aggregate["causality"] = _strongest_causality(
                aggregate["causality"], impact.causality_level
            )
            aggregate["pre_horizon"] = (
                aggregate["pre_horizon"] or impact.pre_horizon_origin
            )
            aggregate["methods"].add(impact.method)
    for campaign_id, aggregate in campaigns.items():
        campaign = campaign_by_id.get(campaign_id, {})
        out.append(
            _entity_row(
                incident_id=incident_id,
                entity_type="production_campaign",
                entity_id=campaign_id,
                lot_id="",
                node_id=_text(campaign.get("node_id")) or aggregate["node"],
                item_id=_text(campaign.get("output_item_id")) or aggregate["item"],
                day=_int(campaign.get("first_event_day"), aggregate["day"]),
                lower_qty=aggregate["lower"],
                upper_qty=aggregate["upper"],
                total_qty=max(aggregate["total"], _float(campaign.get("actual_qty"))),
                uom=aggregate["uom"],
                method="campaign_output_lot_aggregation:"
                + "|".join(sorted(aggregate["methods"])),
                causality_level=aggregate["causality"],
                pre_horizon_origin=aggregate["pre_horizon"],
                exposure_bundle_id="",
                notes=f"Campaign status={_text(campaign.get('status')) or 'unknown'}; campaign exposure is not incident-attributable delay.",
            )
        )
    return out


def _client_service_rows(
    incident_id: str,
    impacts: dict[str, _LotImpact],
    lot_info: dict[str, dict[str, Any]],
    lot_events_by_lot: dict[str, list[dict[str, Any]]],
    service_context: dict[tuple[Any, ...], dict[str, Any]],
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for lot_id, impact in impacts.items():
        for event in lot_events_by_lot.get(lot_id, []):
            if _text(event.get("event_type")) != "demand_service":
                continue
            served = _float(event.get("qty"))
            context = service_context.get(
                (
                    _int(event.get("day")),
                    _text(event.get("node_id")),
                    _text(event.get("item_id")),
                ),
                {},
            )
            out.append(
                {
                    "registry_version": REGISTRY_VERSION,
                    "incident_id": incident_id,
                    "client_service_event_id": _text(event.get("event_id")),
                    "client_lot_id": lot_id,
                    "day": _int(event.get("day")),
                    "client_node_id": _text(event.get("node_id")),
                    "item_id": _text(event.get("item_id")),
                    "served_qty_actual": _round(served),
                    "served_exposed_qty_lower": _round(
                        min(served, served * impact.lower_share)
                    ),
                    "served_exposed_qty_upper": _round(
                        min(served, served * impact.upper_share)
                    ),
                    "uom": _text(event.get("uom"))
                    or _text(lot_info.get(lot_id, {}).get("uom")),
                    "demand_qty_actual": _round(_float(context.get("demand_qty"))),
                    "backlog_end_qty_actual": _round(
                        _float(context.get("backlog_end_qty"))
                    ),
                    "attribution_method": "client_lot_proportional_mix_bounds",
                    "causality_level": impact.causality_level,
                    "service_impact_claim": "lineage_exposure_only_not_counterfactual_service_degradation",
                    "pre_horizon_origin": int(impact.pre_horizon_origin),
                    "do_not_sum_across_incidents": 1,
                }
            )
    return out


def _service_edge_rows(
    service_rows: list[dict[str, Any]],
    impacts: dict[str, _LotImpact],
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for row in service_rows:
        impact = impacts.get(_text(row.get("client_lot_id")))
        if impact is None:
            continue
        out.append(
            {
                "registry_version": REGISTRY_VERSION,
                "incident_id": _text(row.get("incident_id")),
                "exposure_bundle_id": "",
                "edge_id": "IMPACT-EDGE-"
                + _short_hash(
                    f"{row.get('incident_id')}|{row.get('client_lot_id')}|{row.get('client_service_event_id')}"
                ),
                "day": _int(row.get("day")),
                "link_type": "client_service",
                "source_lot_id": _text(row.get("client_lot_id")),
                "target_lot_id": "",
                "target_entity_id": _text(row.get("client_service_event_id")),
                "source_node_id": _text(row.get("client_node_id")),
                "source_item_id": _text(row.get("item_id")),
                "target_node_id": _text(row.get("client_node_id")),
                "target_item_id": _text(row.get("item_id")),
                "source_qty_lower": _round(_float(row.get("served_exposed_qty_lower"))),
                "source_qty_upper": _round(_float(row.get("served_exposed_qty_upper"))),
                "source_uom": _text(row.get("uom")),
                "target_qty_lower": _round(_float(row.get("served_exposed_qty_lower"))),
                "target_qty_upper": _round(_float(row.get("served_exposed_qty_upper"))),
                "target_uom": _text(row.get("uom")),
                "attribution_method": _text(row.get("attribution_method")),
                "causality_level": _text(row.get("causality_level")),
                "shipment_id": "",
                "production_campaign_id": "",
                "pre_horizon_origin": row.get("pre_horizon_origin", 0),
                "do_not_sum_across_incidents": 1,
                "notes": _text(row.get("service_impact_claim")),
            }
        )
    return out


def _supplier_parameter_index(
    rows: list[dict[str, Any]],
) -> dict[tuple[str, str, str], dict[str, Any]]:
    out: dict[tuple[str, str, str], dict[str, Any]] = {}
    for row in rows:
        key = (
            _text(row.get("supplier_id")),
            _text(row.get("dst_node_id")),
            _text(row.get("item_id")),
        )
        out[key] = row
    return out


def _build_cost_rows(
    bundles: list[dict[str, Any]],
    shipment_matches: dict[str, dict[str, Any]],
    parameter_index: dict[tuple[str, str, str], dict[str, Any]],
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for bundle in bundles:
        params = parameter_index.get(
            (
                _text(bundle.get("supplier_id")),
                _text(bundle.get("dst_node_id")),
                _text(bundle.get("item_id")),
            ),
            {},
        )
        native_purchase = bundle.get("purchase_cost_actual_native")
        if native_purchase not in (None, ""):
            purchase_actual: Any = _round(_float(native_purchase))
            purchase_basis = "native_shipment_field"
        elif params and bundle.get("purchase_cost_multiplier") not in (None, ""):
            purchase_actual = _round(
                _float(bundle.get("shipped_qty"))
                * _float(params.get("unit_purchase_cost"))
                * _float(bundle.get("purchase_cost_multiplier"), 1.0)
            )
            purchase_basis = "reconstructed_from_engine_formula_and_nominal_lane_cost"
        else:
            purchase_actual = ""
            purchase_basis = "not_available"
        transport_actual = _float(bundle.get("transport_cost_actual"))
        transport_multiplier = _optional_float(bundle.get("transport_cost_multiplier"))
        purchase_multiplier = _optional_float(bundle.get("purchase_cost_multiplier"))
        direct_transport_delta: Any = ""
        if transport_multiplier is not None and transport_multiplier > EPS:
            direct_transport_delta = _round(
                transport_actual - transport_actual / transport_multiplier
            )
        direct_purchase_delta: Any = ""
        if (
            purchase_actual != ""
            and purchase_multiplier is not None
            and purchase_multiplier > EPS
        ):
            direct_purchase_delta = _round(
                _float(purchase_actual) - _float(purchase_actual) / purchase_multiplier
            )
        out.append(
            {
                "registry_version": REGISTRY_VERSION,
                "exposure_bundle_id": bundle["exposure_bundle_id"],
                "shipment_id": bundle["shipment_id"],
                "event_ids": bundle["event_ids"],
                "transport_cost_actual_exposed": _round(transport_actual),
                "transport_cost_basis": "native_shipment_field",
                "purchase_cost_actual_exposed": purchase_actual,
                "purchase_cost_basis": purchase_basis,
                "direct_transport_multiplier_delta_conditional_on_observed_shipment": direct_transport_delta,
                "direct_purchase_multiplier_delta_conditional_on_observed_shipment": direct_purchase_delta,
                "incremental_total_cost_status": "not_identified_without_matched_counterfactual",
                "cost_aggregation_rule": "bundle costs count once; event-level incident summaries overlap",
                "do_not_sum_across_incidents": 1,
                "notes": "Actual exposed transaction cost is not the causal cost of the incident. Downstream stock, production and service costs require a paired counterfactual.",
            }
        )
    return out


def _incident_summary(
    metadata: dict[str, Any],
    bundles: list[dict[str, Any]],
    impacts: dict[str, _LotImpact],
    lot_info: dict[str, dict[str, Any]],
    service_rows: list[dict[str, Any]],
    costs: list[dict[str, Any]],
    *,
    native_bundle_count: int,
    associated_bundle_count: int,
) -> dict[str, Any]:
    incident_id = _text(metadata.get("event_id"))
    bundle_ids = {row["exposure_bundle_id"] for row in bundles}
    incident_costs = [row for row in costs if row["exposure_bundle_id"] in bundle_ids]
    shipment_qty = _sum_by_uom(bundles, "shipped_qty", "uom")
    output_impacts = [
        (lot_id, impact)
        for lot_id, impact in impacts.items()
        if _text(lot_info.get(lot_id, {}).get("creation_event_type"))
        == "production_output"
    ]
    client_nodes = sorted(
        {
            _text(row.get("client_node_id"))
            for row in service_rows
            if _text(row.get("client_node_id"))
        }
    )
    served_lower = _sum_by_uom(service_rows, "served_exposed_qty_lower", "uom")
    served_upper = _sum_by_uom(service_rows, "served_exposed_qty_upper", "uom")
    causal_level = (
        "native_transaction"
        if native_bundle_count and not associated_bundle_count
        else "mixed_native_and_association"
        if native_bundle_count
        else "scope_day_association"
        if associated_bundle_count
        else "no_exposed_shipment_observed"
    )
    return {
        "registry_version": REGISTRY_VERSION,
        "incident_id": incident_id,
        "trigger_day": _int(metadata.get("trigger_day")),
        "start_day": _int(metadata.get("start_day")),
        "end_day": _int(metadata.get("end_day")),
        "supplier_id": _text(metadata.get("supplier_id")),
        "dst_node_id": _text(metadata.get("dst_node_id")),
        "item_id": _text(metadata.get("item_id")),
        "edge_id": _text(metadata.get("edge_id")),
        "event_source": _text(metadata.get("source")) or "state_dependent_event_ledger",
        "risk_family": _text(metadata.get("risk_family")),
        "risk_type": _text(metadata.get("risk_type")),
        "trigger_metric": _text(metadata.get("trigger_metric")),
        "trigger_value": metadata.get("trigger_value", ""),
        "threshold": metadata.get("threshold", ""),
        "effect": _text(metadata.get("effect")),
        "causality_level": causal_level,
        "causal_claim_allowed": int(causal_level == "native_transaction"),
        "exposure_bundle_count": len(bundles),
        "native_bundle_count": native_bundle_count,
        "associated_bundle_count": associated_bundle_count,
        "exposed_shipment_qty_by_uom_json": json.dumps(shipment_qty, sort_keys=True),
        "exposed_lot_count": len(impacts),
        "exposed_finished_lot_count": len(output_impacts),
        "exposed_client_count": len(client_nodes),
        "exposed_client_ids": "|".join(client_nodes),
        "served_exposed_qty_lower_by_uom_json": json.dumps(
            served_lower, sort_keys=True
        ),
        "served_exposed_qty_upper_by_uom_json": json.dumps(
            served_upper, sort_keys=True
        ),
        "transport_cost_actual_exposed_non_additive": _round(
            sum(
                _float(row.get("transport_cost_actual_exposed"))
                for row in incident_costs
            )
        ),
        "purchase_cost_actual_exposed_non_additive": _round(
            sum(
                _float(row.get("purchase_cost_actual_exposed"))
                for row in incident_costs
            )
        ),
        "incremental_total_cost_status": "not_identified_without_matched_counterfactual",
        "pre_horizon_origin_present": int(
            any(impact.pre_horizon_origin for impact in impacts.values())
        ),
        "do_not_sum_across_incidents": 1,
        "notes": _text(metadata.get("notes")),
    }


def _quality_report(**kwargs: Any) -> dict[str, Any]:
    bundles = kwargs["bundles"]
    applied_rows = kwargs["applied_rows"]
    entities = kwargs["entities"]
    edges = kwargs["edges"]
    service = kwargs["client_service"]
    native = sum(
        _text(row.get("causality_level")) == "native_transaction" for row in bundles
    )
    associated = len(bundles) - native
    warnings: list[str] = []
    if associated:
        warnings.append(
            "Some shipment links were reconstructed by exact scope/day and are associations, not native transaction causality."
        )
    if kwargs["source_alloc_quality"]["source_allocation_coverage_ratio"] < 0.999:
        warnings.append(
            "Some exposed shipment quantity could not be assigned to source lots."
        )
    if kwargs["arrival_quality"]["receipt_lineage_in_horizon_coverage_ratio"] < 0.999:
        warnings.append(
            "Some in-horizon exposed shipment quantity has no receipt genealogy (legacy association ambiguity or aggregate origin)."
        )
    if kwargs["arrival_quality"]["receipt_qty_arriving_after_horizon"] > EPS:
        warnings.append(
            "Some exposed shipments arrive after the simulated horizon; no downstream lot/client claim is made for them."
        )
    warnings.append(
        "Incident-level quantities and costs overlap when several events share one exposure bundle; never sum incident rows."
    )
    warnings.append(
        "Client exposure means genealogical contact, not incident-caused backlog or service loss."
    )
    warnings.append(
        "Incremental total cost requires a matched counterfactual and is intentionally not identified here."
    )
    return {
        "registry_version": REGISTRY_VERSION,
        "source_data_dir": kwargs["source_data_dir"],
        "counts": {
            "incident_count": kwargs["incident_count"],
            "applied_risk_row_count": len(applied_rows),
            "exposure_bundle_count": len(bundles),
            "native_transaction_bundle_count": native,
            "scope_day_association_bundle_count": associated,
            "bundle_event_bridge_count": len(kwargs["bundle_events"]),
            "source_lot_allocation_count": len(kwargs["source_allocations"]),
            "receipt_lot_allocation_count": len(kwargs["arrival_allocations"]),
            "impact_entity_count": len(entities),
            "impact_edge_count": len(edges),
            "client_service_exposure_count": len(service),
        },
        "quantity_reconciliation": {
            **kwargs["source_alloc_quality"],
            **kwargs["arrival_quality"],
        },
        "claim_contract": {
            "native_transaction": "Event IDs were carried on the shipment transaction; a causal exposure claim is allowed.",
            "scope_day_association": "Legacy reconstruction by exact scope/day; only an association claim is allowed.",
            "physical_genealogy": "Quantity propagated through explicit lot genealogy with stated exact method or bounds.",
            "client_service": "Exposed material was served; degradation versus normal operation is not identified.",
            "cost": "Actual exposed cost is reported; total incremental incident cost needs a paired counterfactual.",
        },
        "double_counting_contract": {
            "unique_counting_unit": "exposure_bundle_id",
            "bridge_rule": "Never sum event_exposure_qty_non_additive across incident IDs sharing an overlap_group_id.",
            "incident_rule": "Incident summaries may overlap and are not network totals.",
            "uom_rule": "Quantities are never summed across units; summaries are dictionaries keyed by UOM.",
        },
        "edge_unit_integrity": _edge_unit_quality(edges),
        "warnings": warnings,
    }


def _entity_row(
    *,
    incident_id: str,
    entity_type: str,
    entity_id: str,
    lot_id: str,
    node_id: str,
    item_id: str,
    day: int,
    lower_qty: float,
    upper_qty: float,
    total_qty: float,
    uom: str,
    method: str,
    causality_level: str,
    pre_horizon_origin: bool,
    exposure_bundle_id: str,
    notes: str,
) -> dict[str, Any]:
    denominator = max(EPS, total_qty)
    return {
        "registry_version": REGISTRY_VERSION,
        "incident_id": incident_id,
        "exposure_bundle_id": exposure_bundle_id,
        "entity_type": entity_type,
        "entity_id": entity_id,
        "lot_id": lot_id,
        "node_id": node_id,
        "item_id": item_id,
        "day": day,
        "attributed_qty_lower": _round(lower_qty),
        "attributed_qty_upper": _round(upper_qty),
        "entity_total_qty": _round(total_qty),
        "attributed_share_lower": _round(min(1.0, lower_qty / denominator)),
        "attributed_share_upper": _round(min(1.0, upper_qty / denominator)),
        "uom": uom,
        "attribution_method": method,
        "causality_level": causality_level,
        "pre_horizon_origin": int(pre_horizon_origin),
        "do_not_sum_across_incidents": 1,
        "notes": notes,
    }


def _edge_row(
    *,
    incident_id: str,
    exposure_bundle_id: str,
    link_type: str,
    day: int,
    source_lot_id: str,
    target_lot_id: str,
    genealogy: dict[str, Any],
    source_qty_lower: float,
    source_qty_upper: float,
    target_qty_lower: float,
    target_qty_upper: float,
    method: str,
    causality_level: str,
    shipment_id: str,
    pre_horizon_origin: bool,
    notes: str,
) -> dict[str, Any]:
    edge_id = "IMPACT-EDGE-" + _short_hash(
        f"{incident_id}|{exposure_bundle_id}|{link_type}|{day}|{source_lot_id}|{target_lot_id}|{genealogy.get('_ordinal', '')}"
    )
    return {
        "registry_version": REGISTRY_VERSION,
        "incident_id": incident_id,
        "exposure_bundle_id": exposure_bundle_id,
        "edge_id": edge_id,
        "day": day,
        "link_type": link_type,
        "source_lot_id": source_lot_id,
        "target_lot_id": target_lot_id,
        "target_entity_id": target_lot_id,
        "source_node_id": _text(
            genealogy.get("parent_node_id") or genealogy.get("source_node_id")
        ),
        "source_item_id": _text(
            genealogy.get("parent_item_id") or genealogy.get("item_id")
        ),
        "target_node_id": _text(
            genealogy.get("child_node_id") or genealogy.get("receipt_node_id")
        ),
        "target_item_id": _text(
            genealogy.get("child_item_id") or genealogy.get("item_id")
        ),
        "source_qty_lower": _round(source_qty_lower),
        "source_qty_upper": _round(source_qty_upper),
        "source_uom": "",
        "target_qty_lower": _round(target_qty_lower),
        "target_qty_upper": _round(target_qty_upper),
        "target_uom": "",
        "attribution_method": method,
        "causality_level": causality_level,
        "shipment_id": shipment_id,
        "production_campaign_id": _text(genealogy.get("production_campaign_id")),
        "pre_horizon_origin": int(pre_horizon_origin),
        "do_not_sum_across_incidents": 1,
        "notes": notes,
    }


def _aggregate_entity_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str, str, str], dict[str, Any]] = {}
    for row in rows:
        key = (
            _text(row.get("incident_id")),
            _text(row.get("entity_type")),
            _text(row.get("entity_id")),
            _text(row.get("exposure_bundle_id")),
        )
        existing = grouped.get(key)
        if existing is None:
            grouped[key] = dict(row)
            continue
        total = max(
            _float(existing.get("entity_total_qty")),
            _float(row.get("entity_total_qty")),
        )
        lower = min(
            total,
            _float(existing.get("attributed_qty_lower"))
            + _float(row.get("attributed_qty_lower")),
        )
        upper = min(
            total,
            _float(existing.get("attributed_qty_upper"))
            + _float(row.get("attributed_qty_upper")),
        )
        existing["attributed_qty_lower"] = _round(lower)
        existing["attributed_qty_upper"] = _round(max(lower, upper))
        existing["attributed_share_lower"] = _round(lower / max(EPS, total))
        existing["attributed_share_upper"] = _round(max(lower, upper) / max(EPS, total))
        existing["pre_horizon_origin"] = int(
            bool(existing.get("pre_horizon_origin"))
            or bool(row.get("pre_horizon_origin"))
        )
    return sorted(
        grouped.values(),
        key=lambda row: (
            _text(row.get("incident_id")),
            _int(row.get("day")),
            _text(row.get("entity_id")),
        ),
    )


def _deduplicate_edges(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for row in rows:
        out[_text(row.get("edge_id"))] = row
    return sorted(
        out.values(),
        key=lambda row: (
            _text(row.get("incident_id")),
            _int(row.get("day")),
            _text(row.get("edge_id")),
        ),
    )


def _attach_and_validate_edge_units(
    edges: list[dict[str, Any]], entities: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Make every edge self-contained without converting endpoint quantities.

    Edge quantities describe two distinct physical sides.  In particular, a
    production edge may consume kilograms and produce units, so its source and
    target UOMs are resolved independently from the corresponding lot entities.
    Only transport and client-service links require matching endpoint units.
    Missing or contradictory metadata fails closed instead of silently assuming
    a conversion.
    """

    endpoint_uoms: dict[tuple[str, str], str] = {}
    for entity in entities:
        incident_id = _text(entity.get("incident_id"))
        lot_id = _text(entity.get("lot_id"))
        if not incident_id or not lot_id:
            continue
        uom = _text(entity.get("uom"))
        if not uom:
            continue
        key = (incident_id, lot_id)
        existing = endpoint_uoms.get(key)
        if existing and existing.casefold() != uom.casefold():
            raise RiskImpactUnitError(
                "Conflicting UOMs for impact entity "
                f"incident={incident_id!r}, lot={lot_id!r}: "
                f"{existing!r} versus {uom!r}."
            )
        endpoint_uoms.setdefault(key, uom)

    completed: list[dict[str, Any]] = []
    for source in edges:
        row = dict(source)
        incident_id = _text(row.get("incident_id"))
        edge_id = _text(row.get("edge_id"))
        link_type = _text(row.get("link_type"))
        source_lot_id = _text(row.get("source_lot_id"))
        target_lot_id = _text(row.get("target_lot_id"))

        source_entity_uom = endpoint_uoms.get((incident_id, source_lot_id), "")
        target_entity_uom = endpoint_uoms.get((incident_id, target_lot_id), "")
        source_uom = _resolve_edge_endpoint_uom(
            edge_id=edge_id,
            endpoint="source",
            lot_id=source_lot_id,
            edge_uom=_text(row.get("source_uom")),
            entity_uom=source_entity_uom,
        )
        if target_lot_id:
            target_uom = _resolve_edge_endpoint_uom(
                edge_id=edge_id,
                endpoint="target",
                lot_id=target_lot_id,
                edge_uom=_text(row.get("target_uom")),
                entity_uom=target_entity_uom,
            )
        elif link_type == "client_service":
            target_uom = _text(row.get("target_uom")) or source_uom
        else:
            raise RiskImpactUnitError(
                f"Impact edge {edge_id!r} has no target lot or supported target entity."
            )

        if not source_uom or not target_uom:
            raise RiskImpactUnitError(
                f"Impact edge {edge_id!r} has an unresolved endpoint UOM."
            )
        if link_type in {"transport", "risk_exposed_transport", "client_service"}:
            if source_uom.casefold() != target_uom.casefold():
                raise RiskImpactUnitError(
                    f"Impact edge {edge_id!r} ({link_type}) changes UOM from "
                    f"{source_uom!r} to {target_uom!r}; no conversion is declared."
                )

        row["source_uom"] = source_uom
        row["target_uom"] = target_uom
        completed.append(row)
    return completed


def _resolve_edge_endpoint_uom(
    *,
    edge_id: str,
    endpoint: str,
    lot_id: str,
    edge_uom: str,
    entity_uom: str,
) -> str:
    if not lot_id:
        raise RiskImpactUnitError(
            f"Impact edge {edge_id!r} has no {endpoint} lot for UOM resolution."
        )
    if edge_uom and entity_uom and edge_uom.casefold() != entity_uom.casefold():
        raise RiskImpactUnitError(
            f"Impact edge {edge_id!r} {endpoint} UOM {edge_uom!r} disagrees "
            f"with lot {lot_id!r} UOM {entity_uom!r}."
        )
    resolved = entity_uom or edge_uom
    if not resolved:
        raise RiskImpactUnitError(
            f"Impact edge {edge_id!r} {endpoint} lot {lot_id!r} has no UOM."
        )
    return resolved


def _edge_unit_quality(edges: list[dict[str, Any]]) -> dict[str, Any]:
    production = [row for row in edges if _text(row.get("link_type")) == "production"]
    mixed_production = sum(
        _text(row.get("source_uom")).casefold()
        != _text(row.get("target_uom")).casefold()
        for row in production
    )
    return {
        "status": "verified" if edges else "not_applicable_no_edges",
        "edge_count": len(edges),
        "edges_with_both_endpoint_uoms": sum(
            bool(_text(row.get("source_uom"))) and bool(_text(row.get("target_uom")))
            for row in edges
        ),
        "production_edge_count": len(production),
        "mixed_uom_production_edge_count": mixed_production,
        "contract": (
            "Source and target quantities retain their own lot UOM. No endpoint "
            "conversion and no cross-stage quantity summation is performed."
        ),
    }


def _lot_entity_type(info: dict[str, Any]) -> str:
    event_type = _text(info.get("creation_event_type"))
    node = _text(info.get("node_id"))
    if event_type == "production_output":
        return "finished_product_lot"
    if event_type == "opening_stock":
        return "opening_stock_lot"
    if node.startswith("C-"):
        return "customer_receipt_lot"
    if node.startswith("DC-"):
        return "distribution_receipt_lot"
    if node.startswith("M-"):
        return "plant_material_lot"
    if event_type == "external_procurement_receipt":
        return "supplier_material_lot"
    return "physical_lot"


def _scope_key(day: Any, supplier: Any, dst: Any, item: Any) -> tuple[Any, ...]:
    return (_int(day), _text(supplier), _text(dst), _text(item))


def _split_ids(value: Any) -> list[str]:
    text = _text(value).replace(";", ",").replace("|", ",")
    return sorted({part.strip() for part in text.split(",") if part.strip()})


def _unique_rows(rows: Iterable[dict[str, Any]], key: str) -> list[dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for row in rows:
        out[_text(row.get(key))] = row
    return list(out.values())


def _sum_by_uom(
    rows: Iterable[dict[str, Any]], qty_field: str, uom_field: str
) -> dict[str, float]:
    out: dict[str, float] = defaultdict(float)
    for row in rows:
        out[_text(row.get(uom_field)) or "UNSPECIFIED"] += _float(row.get(qty_field))
    return {uom: _round(qty) for uom, qty in sorted(out.items())}


def _strongest_causality(left: str, right: str) -> str:
    rank = {
        "": 0,
        "scope_day_association": 1,
        "physical_genealogy": 2,
        "native_transaction": 3,
    }
    return left if rank.get(left, 0) >= rank.get(right, 0) else right


def _short_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16].upper()


def _text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _optional_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _int(value: Any, default: int = 0) -> int:
    try:
        return int(round(float(value)))
    except (TypeError, ValueError):
        return default


def _round(value: float) -> float:
    return round(float(value), 6)


def _coverage_ratio(matched: float, expected: float) -> float:
    if expected <= EPS:
        return 1.0
    return _round(max(0.0, min(1.0, matched / expected)))


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fields: list[str] = []
    seen: set[str] = set()
    for row in rows:
        for field in row:
            if field not in seen:
                seen.add(field)
                fields.append(field)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
