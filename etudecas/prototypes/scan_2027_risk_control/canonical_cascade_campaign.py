#!/usr/bin/env python3
"""Run additive business-cascade intervention campaigns on the canonical engine.

The module does not alter the physical engine or any historical cold-start
artifact.  It prepares explicit supplier incidents and bounded open-loop
control schedules, runs every case below a new output root, and exports a flat
business KPI table for the separate cascade comparator.

Three cases are always retained for each configured cascade:

* ``normal``: no incident and no intervention;
* ``incident_no_action``: the configured incident without intervention;
* ``incident_<solution>``: the same incident plus exactly one declared solution.

All days are measured days.  Warm-up actions remain impossible because the
engine's public ``--control-schedule-csv`` contract only starts at day zero.
"""

from __future__ import annotations

import argparse
import csv
from concurrent.futures import Future, ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import shutil
import subprocess
import sys
from typing import Any, Iterable, Mapping, Sequence


HERE = Path(__file__).resolve()
REPO_ROOT = HERE.parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from etudecas.prototypes.scan_2027_risk_control.canonical_replay import (  # noqa: E402
    MANAGED_CANONICAL_ENGINE_FLAGS,
    discover_canonical_graph,
    load_canonical_engine_profile,
)
from etudecas.simulation.engine.control_schedule import (  # noqa: E402
    CONTROL_BOUNDS,
    CONTROL_SCHEDULE_COLUMNS,
    ControlCatalog,
    ControlScheduleError,
    load_control_schedule,
)


CONFIG_SCHEMA_VERSION = "scan.canonical_cascade_campaign.v2"
MANIFEST_SCHEMA_VERSION = "scan.canonical_cascade_manifest.v2"
DEFAULT_CONFIG_PATH = HERE.parent / "config" / "canonical_cascade_campaign_config.json"
DEFAULT_ENGINE_SCRIPT = REPO_ROOT / "etudecas" / "simulation" / "engine" / "run_first_simulation.py"

RISK_EVENT_COLUMNS: tuple[str, ...] = (
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

RUN_COLUMNS: tuple[str, ...] = (
    "cascade_id",
    "variant_id",
    "case_type",
    "solution_id",
    "seed",
    "status",
    "returncode",
    "error",
    "result_dir",
    "days",
    "scenario_id",
    "native_levers",
    "approximation_levers",
    "lever_fidelity",
    "customer_id",
    "finished_item_id",
    "customer_shortage_days",
    "customer_backlog_qty_days",
    "recovery_day",
    "recovery_observed",
    "customer_demand_qty",
    "customer_served_qty",
    "production_qty",
    "production_lot_count",
    "completed_lot_qty",
    "blocked_lot_qty",
    "target_order_qty",
    "target_order_count",
    "target_stock_qty_days",
    "base_operational_supply_cost",
    "opening_transport_cost",
    "opening_purchase_cost",
    "external_transport_cost",
    "external_purchase_cost",
    "controllable_operating_cost",
    "decision_total_cost",
    "decision_transport_cost",
    "decision_purchase_cost",
    "supplier_risk_applied_row_count",
    "supplier_risk_applied_event_ids",
    "supplier_risk_effects_json",
    "action_execution_status",
    "expected_action_signature_count",
    "verified_action_signature_count",
    "verified_action_row_count",
    "verified_action_evidence_json",
    "measurement_start_state_sha256",
    "measurement_start_component_sha256_json",
    "pairing_status",
    "incident_validation_status",
    "risk_events_sha256",
    "control_schedule_sha256",
    "graph_sha256",
    "engine_profile_sha256",
)

_SUPPORTED_RISK_TYPES = frozenset(
    {
        "quality_delay",
        "quality_yield",
        "lead_time",
        "lead_time_extra_days",
        "availability",
        "capacity",
        "reliability",
        "stock_writeoff",
    }
)
_LEVER_FIDELITIES = frozenset(
    {
        "native_engine",
        "native_graph",
        "native_simplified",
        "mixed",
        "approximation",
    }
)
_MANAGED_FLAGS = frozenset(
    {
        *MANAGED_CANONICAL_ENGINE_FLAGS,
        "--control-policy-json",
        "--control-policy-v2-json",
        "--control-policy-v3-json",
        "--control-probe-schedule-csv",
    }
)
_COMPACT_ARTIFACT_ARGS = (
    "--output-profile",
    "compact",
    "--skip-map",
    "--skip-plots",
    "--no-lot-trace",
    "--skip-lot-audit",
)
_FULL_ARTIFACT_ARGS = (
    "--output-profile",
    "full",
    "--skip-map",
    "--lot-trace",
)

_PAIRED_CASCADE_ENGINE_FLAGS = {
    "--opening-observed-stock-scale-csv",
    "--measurement-start-stock-scale-csv",
    "--measurement-start-in-transit-scale-csv",
}


class CascadeCampaignError(RuntimeError):
    """Raised when a cascade campaign or an engine output is invalid."""


@dataclass(frozen=True)
class PreparedVariant:
    """One normal, untreated-incident, or treated-incident case."""

    cascade_id: str
    variant_id: str
    case_type: str
    solution_id: str
    label: str
    lever_fidelity: str
    native_levers: tuple[str, ...]
    approximation_levers: tuple[str, ...]
    approximation_notes: str
    risk_events: tuple[dict[str, Any], ...]
    schedule_rows: tuple[dict[str, Any], ...]
    engine_args: tuple[str, ...]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_json_object(path: Path, *, label: str) -> dict[str, Any]:
    resolved = path.resolve()
    if not resolved.is_file():
        raise CascadeCampaignError(f"{label} does not exist: {resolved}")
    try:
        payload = json.loads(resolved.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CascadeCampaignError(f"{label} is not valid UTF-8 JSON: {resolved}") from exc
    if not isinstance(payload, dict):
        raise CascadeCampaignError(f"{label} must contain a JSON object: {resolved}")
    return payload


def _resolve_path(value: str | Path, *, relative_to: Path | None = None) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path.resolve()
    repo_candidate = (REPO_ROOT / path).resolve()
    local_candidate = (relative_to / path).resolve() if relative_to else None
    if repo_candidate.exists() or local_candidate is None:
        return repo_candidate
    return local_candidate


def _safe_output_root(path: Path) -> Path:
    resolved = path.resolve()
    if resolved.exists() and not resolved.is_dir():
        raise CascadeCampaignError(f"Output root is not a directory: {resolved}")
    if resolved.exists() and any(resolved.iterdir()):
        raise CascadeCampaignError(
            "Refusing to mix a cascade campaign with existing artifacts: "
            f"{resolved}"
        )
    resolved.mkdir(parents=True, exist_ok=True)
    return resolved


def _as_nonempty_string(value: Any, *, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise CascadeCampaignError(f"{label} must be a non-empty string.")
    return value.strip()


def _as_int(value: Any, *, label: str, minimum: int = 0) -> int:
    if isinstance(value, bool):
        raise CascadeCampaignError(f"{label} must be an integer.")
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise CascadeCampaignError(f"{label} must be an integer.") from exc
    if str(value).strip() not in {str(parsed), f"{parsed}.0"} or parsed < minimum:
        raise CascadeCampaignError(f"{label} must be an integer >= {minimum}.")
    return parsed


def _as_float(value: Any, *, label: str) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError) as exc:
        raise CascadeCampaignError(f"{label} must be numeric.") from exc
    if not math.isfinite(parsed):
        raise CascadeCampaignError(f"{label} must be finite.")
    return parsed


def _as_bool(value: Any, *, label: str) -> bool:
    if not isinstance(value, bool):
        raise CascadeCampaignError(f"{label} must be boolean.")
    return value


def _validate_engine_args(raw: Any, *, label: str) -> tuple[str, ...]:
    if raw is None:
        return ()
    if not isinstance(raw, list) or not all(
        isinstance(token, str) and token.strip() for token in raw
    ):
        raise CascadeCampaignError(f"{label} must be a list of non-empty strings.")
    args = tuple(token.strip() for token in raw)
    for token in args:
        if any(char in token for char in ("\x00", "\n", "\r")):
            raise CascadeCampaignError(f"{label} contains a control character.")
        flag = token.split("=", 1)[0]
        if flag in _MANAGED_FLAGS:
            raise CascadeCampaignError(
                f"{label} cannot override campaign-managed flag {flag}."
            )
    return args


def _engine_arg_value(args: Sequence[str], flag: str) -> str | None:
    """Return the last explicit value for a two-token or ``--flag=value`` option."""

    value: str | None = None
    for index, token in enumerate(args):
        if token == flag and index + 1 < len(args):
            value = args[index + 1]
        elif token.startswith(f"{flag}="):
            value = token.split("=", 1)[1]
    return value


def _validate_paired_cascade_engine_args(
    raw: Any,
    *,
    label: str,
) -> tuple[str, ...]:
    """Allow only pair-scoped J0 sensitivity inputs shared by every cascade arm."""

    args = _validate_engine_args(raw, label=label)
    _paired_cascade_engine_arg_entries(args, label=label)
    return args


def _paired_cascade_engine_arg_entries(
    args: Sequence[str],
    *,
    label: str,
) -> tuple[tuple[str, str], ...]:
    """Parse the small, value-taking set of pair-scoped CSV options."""

    entries: list[tuple[str, str]] = []
    seen: set[str] = set()
    index = 0
    while index < len(args):
        token = args[index]
        if "=" in token:
            flag, value = token.split("=", 1)
            consumed = 1
        else:
            flag = token
            if index + 1 >= len(args) or args[index + 1].startswith("--"):
                raise CascadeCampaignError(f"{label}: {flag} requires a CSV path.")
            value = args[index + 1]
            consumed = 2
        if flag not in _PAIRED_CASCADE_ENGINE_FLAGS:
            raise CascadeCampaignError(
                f"{label}: {flag} is not a permitted pair-scoped J0 sensitivity flag."
            )
        if flag in seen:
            raise CascadeCampaignError(f"{label}: duplicate flag {flag}.")
        if not value.strip():
            raise CascadeCampaignError(f"{label}: {flag} requires a non-empty CSV path.")
        seen.add(flag)
        entries.append((flag, value.strip()))
        index += consumed
    return tuple(entries)


def _resolve_paired_state_csv(
    value: str,
    *,
    config_dir: Path,
    label: str,
) -> tuple[Path, str]:
    """Resolve a paired-state CSV without consulting the process working directory.

    Relative values may identify either a file beside the campaign configuration or
    a repository-relative file.  If both interpretations exist and point at
    different files, failing is safer than silently selecting one of them.
    """

    raw_path = Path(value)
    if raw_path.is_absolute():
        resolved = raw_path.resolve()
        if not resolved.is_file():
            raise CascadeCampaignError(
                f"{label}: paired-state CSV does not exist or is not a file: {resolved}"
            )
        return resolved, "absolute"

    candidates = (
        ("config_relative", (config_dir / raw_path).resolve()),
        ("repo_relative", (REPO_ROOT / raw_path).resolve()),
    )
    existing: dict[Path, list[str]] = {}
    for resolution, candidate in candidates:
        if candidate.is_file():
            existing.setdefault(candidate, []).append(resolution)
    if not existing:
        attempted = ", ".join(str(candidate) for _kind, candidate in candidates)
        raise CascadeCampaignError(
            f"{label}: paired-state CSV is missing; checked {attempted}."
        )
    if len(existing) > 1:
        choices = ", ".join(
            f"{'+'.join(kinds)}={path}" for path, kinds in existing.items()
        )
        raise CascadeCampaignError(
            f"{label}: ambiguous paired-state CSV {value!r}; {choices}."
        )
    resolved, resolution_modes = next(iter(existing.items()))
    return resolved, "+".join(resolution_modes)


def _resolve_paired_state_inputs(
    config: Mapping[str, Any],
    *,
    cascade_ids: Iterable[str],
    config_dir: Path,
) -> dict[str, tuple[dict[str, Any], ...]]:
    """Resolve all selected cascade CSVs before creating campaign artifacts."""

    selected = set(cascade_ids)
    resolved: dict[str, tuple[dict[str, Any], ...]] = {}
    for cascade in config.get("cascades", []):
        cascade_id = str(cascade.get("id") or "")
        if cascade_id not in selected:
            continue
        label = f"cascade {cascade_id}.paired_engine_args"
        args = _validate_paired_cascade_engine_args(
            cascade.get("paired_engine_args", []), label=label
        )
        rows: list[dict[str, Any]] = []
        for flag, value in _paired_cascade_engine_arg_entries(args, label=label):
            source, resolution = _resolve_paired_state_csv(
                value,
                config_dir=config_dir,
                label=f"{label} {flag}",
            )
            rows.append(
                {
                    "cascade_id": cascade_id,
                    "flag": flag,
                    "source": source,
                    "resolution": resolution,
                }
            )
        resolved[cascade_id] = tuple(rows)
    missing = sorted(selected - set(resolved))
    if missing:  # variants and config are expected to have been validated together.
        raise CascadeCampaignError(
            "Selected cascades have no paired-state definition: " + ", ".join(missing)
        )
    return resolved


def _paired_state_snapshot_name(flag: str) -> str:
    """Derive a stable, human-readable CSV name from an engine flag."""

    stem = flag.removeprefix("--").removesuffix("-csv").replace("-", "_")
    return f"{stem}.csv"


def _freeze_paired_state_inputs(
    *,
    output_root: Path,
    resolved_inputs: Mapping[str, Sequence[Mapping[str, Any]]],
) -> tuple[dict[str, tuple[str, ...]], list[dict[str, str]]]:
    """Copy paired CSVs into the campaign and return rewritten engine arguments."""

    frozen_args: dict[str, tuple[str, ...]] = {}
    ledger: list[dict[str, str]] = []
    for cascade_id in sorted(resolved_inputs):
        rewritten: list[str] = []
        target_names: set[str] = set()
        for row in resolved_inputs[cascade_id]:
            flag = str(row["flag"])
            source = Path(row["source"]).resolve()
            target_name = _paired_state_snapshot_name(flag)
            if target_name in target_names:
                raise CascadeCampaignError(
                    f"cascade {cascade_id}: duplicate paired-state snapshot {target_name}."
                )
            target_names.add(target_name)
            snapshot = (
                output_root
                / "prepared_inputs"
                / cascade_id
                / "paired_state"
                / target_name
            )
            snapshot.parent.mkdir(parents=True, exist_ok=True)
            try:
                with source.open("rb") as source_stream, snapshot.open("xb") as target_stream:
                    shutil.copyfileobj(source_stream, target_stream)
            except FileExistsError as exc:
                raise CascadeCampaignError(
                    f"Refusing to overwrite paired-state snapshot: {snapshot}"
                ) from exc
            source_sha256 = _sha256(source)
            snapshot_sha256 = _sha256(snapshot)
            if snapshot_sha256 != source_sha256:
                raise CascadeCampaignError(
                    f"Paired-state snapshot hash mismatch for {cascade_id}/{flag}."
                )
            rewritten.extend((flag, str(snapshot.resolve())))
            ledger.append(
                {
                    "cascade_id": cascade_id,
                    "flag": flag,
                    "resolution": str(row["resolution"]),
                    "source": str(source),
                    "snapshot": str(snapshot.resolve()),
                    "sha256": snapshot_sha256,
                }
            )
        frozen_args[cascade_id] = tuple(rewritten)
    return frozen_args, ledger


def _graph_catalog(graph: Mapping[str, Any]) -> ControlCatalog:
    nodes = [node for node in graph.get("nodes", []) if isinstance(node, Mapping)]
    node_ids = {str(node.get("id") or "") for node in nodes if node.get("id")}
    suppliers = {
        str(node.get("id"))
        for node in nodes
        if str(node.get("type") or "") == "supplier_dc" and node.get("id")
    }
    item_ids = {
        str(item.get("id"))
        for item in graph.get("items", [])
        if isinstance(item, Mapping) and item.get("id")
    }
    return ControlCatalog(
        node_ids=node_ids,
        supplier_ids=suppliers,
        item_ids=item_ids,
        dst_node_ids=node_ids,
    )


def _validate_cascade_path(cascade: Mapping[str, Any], graph: Mapping[str, Any]) -> None:
    cascade_id = _as_nonempty_string(cascade.get("id"), label="cascade.id")
    stages = cascade.get("path")
    if not isinstance(stages, list) or not stages:
        raise CascadeCampaignError(f"cascade {cascade_id}: path must be non-empty.")
    edges = [edge for edge in graph.get("edges", []) if isinstance(edge, Mapping)]
    nodes = {
        str(node.get("id")): node
        for node in graph.get("nodes", [])
        if isinstance(node, Mapping) and node.get("id")
    }
    for index, stage in enumerate(stages):
        if not isinstance(stage, Mapping):
            raise CascadeCampaignError(f"cascade {cascade_id}: path[{index}] must be an object.")
        kind = str(stage.get("kind") or "")
        if kind == "transport":
            src = _as_nonempty_string(stage.get("from"), label=f"{cascade_id}.path[{index}].from")
            dst = _as_nonempty_string(stage.get("to"), label=f"{cascade_id}.path[{index}].to")
            item_id = _as_nonempty_string(
                stage.get("item_id"), label=f"{cascade_id}.path[{index}].item_id"
            )
            matches = [
                edge
                for edge in edges
                if str(edge.get("from") or "") == src
                and str(edge.get("to") or "") == dst
                and item_id in {str(item) for item in edge.get("items", [])}
            ]
            if not matches:
                raise CascadeCampaignError(
                    f"cascade {cascade_id}: missing graph transport {src} -> {dst} for {item_id}."
                )
        elif kind == "transform":
            node_id = _as_nonempty_string(
                stage.get("node_id"), label=f"{cascade_id}.path[{index}].node_id"
            )
            input_item = _as_nonempty_string(
                stage.get("input_item_id"),
                label=f"{cascade_id}.path[{index}].input_item_id",
            )
            output_item = _as_nonempty_string(
                stage.get("output_item_id"),
                label=f"{cascade_id}.path[{index}].output_item_id",
            )
            node = nodes.get(node_id)
            processes = node.get("processes", []) if isinstance(node, Mapping) else []
            if not any(
                input_item
                in {
                    str(row.get("item_id"))
                    for row in process.get("inputs", [])
                    if isinstance(row, Mapping)
                }
                and output_item
                in {
                    str(row.get("item_id"))
                    for row in process.get("outputs", [])
                    if isinstance(row, Mapping)
                }
                for process in processes
                if isinstance(process, Mapping)
            ):
                raise CascadeCampaignError(
                    f"cascade {cascade_id}: missing transform at {node_id}: "
                    f"{input_item} -> {output_item}."
                )
        else:
            raise CascadeCampaignError(
                f"cascade {cascade_id}: path[{index}].kind must be transport or transform."
            )


def _validate_solution(
    solution: Mapping[str, Any],
    *,
    cascade_id: str,
    days: int,
) -> None:
    solution_id = _as_nonempty_string(
        solution.get("id"), label=f"cascade {cascade_id} solution.id"
    )
    fidelity = _as_nonempty_string(
        solution.get("lever_fidelity"),
        label=f"solution {solution_id}.lever_fidelity",
    )
    if fidelity not in _LEVER_FIDELITIES:
        raise CascadeCampaignError(
            f"solution {solution_id}: unsupported lever_fidelity {fidelity!r}."
        )
    approximation_levers = solution.get("approximation_levers", [])
    if not isinstance(approximation_levers, list) or not all(
        isinstance(value, str) and value.strip() for value in approximation_levers
    ):
        raise CascadeCampaignError(
            f"solution {solution_id}.approximation_levers must be a string list."
        )
    notes = str(solution.get("approximation_notes") or "").strip()
    if (fidelity in {"native_simplified", "mixed", "approximation"} or approximation_levers) and not notes:
        raise CascadeCampaignError(
            f"solution {solution_id}: approximations require approximation_notes."
        )
    variant_args = _validate_engine_args(
        solution.get("engine_args", []), label=f"solution {solution_id}.engine_args"
    )
    if variant_args:
        raise CascadeCampaignError(
            f"solution {solution_id}: variant-specific engine_args are forbidden because "
            "they can change the warm-up and measurement-start state; put common "
            "physical options in campaign.engine_args and use measured-day controls."
        )
    ranking_eligible = solution.get("ranking_eligible", True)
    if not isinstance(ranking_eligible, bool):
        raise CascadeCampaignError(
            f"solution {solution_id}.ranking_eligible must be boolean."
        )
    ranking_reason = str(solution.get("ranking_exclusion_reason") or "").strip()
    if not ranking_eligible and not ranking_reason:
        raise CascadeCampaignError(
            f"solution {solution_id}: ranking_exclusion_reason is required when "
            "ranking_eligible is false."
        )
    windows = solution.get("action_windows", [])
    if not isinstance(windows, list):
        raise CascadeCampaignError(f"solution {solution_id}.action_windows must be a list.")
    if not windows:
        raise CascadeCampaignError(
            f"solution {solution_id} must define measured-day action_windows."
        )
    for index, window in enumerate(windows):
        if not isinstance(window, Mapping):
            raise CascadeCampaignError(
                f"solution {solution_id}.action_windows[{index}] must be an object."
            )
        start = _as_int(
            window.get("start_day"),
            label=f"solution {solution_id}.action_windows[{index}].start_day",
        )
        end = _as_int(
            window.get("end_day"),
            label=f"solution {solution_id}.action_windows[{index}].end_day",
        )
        if end < start or end >= days:
            raise CascadeCampaignError(
                f"solution {solution_id}: invalid action window {start}..{end} for {days} days."
            )
        scope = window.get("scope", {})
        actions = window.get("actions")
        if not isinstance(scope, Mapping) or not isinstance(actions, Mapping) or not actions:
            raise CascadeCampaignError(
                f"solution {solution_id}: each action window needs scope/actions objects."
            )
        unknown_scope = sorted(set(scope) - {"node_id", "supplier_id", "item_id", "dst_node_id"})
        unknown_actions = sorted(set(actions) - set(CONTROL_BOUNDS))
        if unknown_scope or unknown_actions:
            raise CascadeCampaignError(
                f"solution {solution_id}: unknown scope={unknown_scope}, actions={unknown_actions}."
            )
        for action, raw_value in actions.items():
            value = _as_float(
                raw_value,
                label=f"solution {solution_id}.action_windows[{index}].actions.{action}",
            )
            bound = CONTROL_BOUNDS[action]
            if value < float(bound.lower) or value > float(bound.upper):
                raise CascadeCampaignError(
                    f"solution {solution_id}: {action}={value} outside "
                    f"[{bound.lower}, {bound.upper}]."
                )
            if bound.integer and not value.is_integer():
                raise CascadeCampaignError(
                    f"solution {solution_id}: {action} must be an integer number of days."
                )


def validate_campaign_config(payload: Mapping[str, Any], graph: Mapping[str, Any]) -> None:
    """Validate schema, graph cascades, incidents, solutions and lever coverage."""

    if str(payload.get("schema_version") or "") != CONFIG_SCHEMA_VERSION:
        raise CascadeCampaignError(
            f"schema_version must be {CONFIG_SCHEMA_VERSION!r}."
        )
    campaign = payload.get("campaign")
    if not isinstance(campaign, Mapping):
        raise CascadeCampaignError("campaign must be a JSON object.")
    guards = payload.get("scientific_guards")
    if not isinstance(guards, Mapping):
        raise CascadeCampaignError("scientific_guards must be a JSON object.")
    minimum_days = _as_int(
        guards.get("minimum_horizon_days"),
        label="scientific_guards.minimum_horizon_days",
        minimum=1,
    )
    minimum_warmup = _as_int(
        guards.get("minimum_warmup_days"),
        label="scientific_guards.minimum_warmup_days",
        minimum=0,
    )
    _as_bool(
        guards.get("require_positive_incremental_customer_backlog"),
        label=(
            "scientific_guards.require_positive_incremental_customer_backlog"
        ),
    )
    days = _as_int(campaign.get("days"), label="campaign.days", minimum=minimum_days)
    _as_nonempty_string(campaign.get("scenario_id"), label="campaign.scenario_id")
    common_engine_args = _validate_engine_args(
        campaign.get("engine_args", []), label="campaign.engine_args"
    )
    warmup_value = _engine_arg_value(common_engine_args, "--warmup-days")
    if warmup_value is None:
        raise CascadeCampaignError(
            "campaign.engine_args must explicitly set --warmup-days for pairing."
        )
    warmup_days = _as_int(
        warmup_value, label="campaign.engine_args --warmup-days", minimum=minimum_warmup
    )
    if "--warmup-boundary-audit" not in common_engine_args:
        raise CascadeCampaignError(
            "campaign.engine_args must enable --warmup-boundary-audit."
        )
    if warmup_days >= days:
        raise CascadeCampaignError(
            "The measured horizon must be longer than the physical warm-up."
        )
    cascades = payload.get("cascades")
    if not isinstance(cascades, list) or not cascades:
        raise CascadeCampaignError("cascades must be a non-empty list.")
    cascade_ids: set[str] = set()
    solution_ids: set[str] = set()
    for raw_cascade in cascades:
        if not isinstance(raw_cascade, Mapping):
            raise CascadeCampaignError("Each cascade must be a JSON object.")
        cascade_id = _as_nonempty_string(raw_cascade.get("id"), label="cascade.id")
        if cascade_id in cascade_ids:
            raise CascadeCampaignError(f"Duplicate cascade id {cascade_id!r}.")
        cascade_ids.add(cascade_id)
        _validate_paired_cascade_engine_args(
            raw_cascade.get("paired_engine_args", []),
            label=f"cascade {cascade_id}.paired_engine_args",
        )
        _validate_cascade_path(raw_cascade, graph)
        _as_nonempty_string(raw_cascade.get("customer_id"), label=f"{cascade_id}.customer_id")
        _as_nonempty_string(
            raw_cascade.get("finished_item_id"), label=f"{cascade_id}.finished_item_id"
        )
        _as_float(raw_cascade.get("reference_lot_qty"), label=f"{cascade_id}.reference_lot_qty")
        incident = raw_cascade.get("incident")
        if not isinstance(incident, Mapping):
            raise CascadeCampaignError(f"cascade {cascade_id}: incident must be an object.")
        incident_start = _as_int(
            incident.get("start_day"), label=f"{cascade_id}.incident.start_day"
        )
        incident_end = _as_int(
            incident.get("end_day"), label=f"{cascade_id}.incident.end_day"
        )
        if incident_end < incident_start or incident_end >= days:
            raise CascadeCampaignError(f"cascade {cascade_id}: invalid incident window.")
        risk_events = incident.get("risk_events")
        if not isinstance(risk_events, list) or not risk_events:
            raise CascadeCampaignError(f"cascade {cascade_id}: risk_events must be non-empty.")
        for index, event in enumerate(risk_events):
            if not isinstance(event, Mapping):
                raise CascadeCampaignError(f"{cascade_id}.risk_events[{index}] must be an object.")
            risk_type = _as_nonempty_string(
                event.get("risk_type"), label=f"{cascade_id}.risk_events[{index}].risk_type"
            )
            if risk_type not in _SUPPORTED_RISK_TYPES:
                raise CascadeCampaignError(
                    f"cascade {cascade_id}: unsupported risk_type {risk_type!r}."
                )
            for field in ("event_id", "supplier_id", "item_id", "dst_node_id"):
                _as_nonempty_string(
                    event.get(field), label=f"{cascade_id}.risk_events[{index}].{field}"
                )
            _as_float(event.get("multiplier"), label=f"{cascade_id}.risk_events[{index}].multiplier")
        solutions = raw_cascade.get("solutions")
        if not isinstance(solutions, list) or not solutions:
            raise CascadeCampaignError(f"cascade {cascade_id}: solutions must be non-empty.")
        local_ids: set[str] = set()
        for solution in solutions:
            if not isinstance(solution, Mapping):
                raise CascadeCampaignError(f"cascade {cascade_id}: solution must be an object.")
            solution_id = _as_nonempty_string(solution.get("id"), label="solution.id")
            if solution_id in local_ids:
                raise CascadeCampaignError(
                    f"cascade {cascade_id}: duplicate solution {solution_id!r}."
                )
            local_ids.add(solution_id)
            solution_ids.add(solution_id)
            _validate_solution(solution, cascade_id=cascade_id, days=days)
    required = payload.get("required_solution_ids", [])
    if not isinstance(required, list) or not all(isinstance(item, str) for item in required):
        raise CascadeCampaignError("required_solution_ids must be a string list.")
    missing = sorted(set(required) - solution_ids)
    if missing:
        raise CascadeCampaignError(
            "Required business levers are not represented by a solution: " + ", ".join(missing)
        )


def _merge_schedule_windows(
    solution: Mapping[str, Any],
    *,
    days: int,
) -> tuple[dict[str, Any], ...]:
    """Expand inclusive windows and merge distinct actions on identical scopes."""

    solution_id = str(solution.get("id") or "")
    merged: dict[tuple[int, str, str, str, str], dict[str, Any]] = {}
    for window in solution.get("action_windows", []):
        start = int(window["start_day"])
        end = int(window["end_day"])
        if start < 0 or end >= days:
            raise CascadeCampaignError(
                f"solution {solution_id}: action window outside measured horizon."
            )
        scope = {
            field: str(window.get("scope", {}).get(field) or "").strip()
            for field in ("node_id", "supplier_id", "item_id", "dst_node_id")
        }
        for day in range(start, end + 1):
            key = (day, *(scope[field] for field in ("node_id", "supplier_id", "item_id", "dst_node_id")))
            row = merged.setdefault(
                key,
                {
                    "day": day,
                    "policy": solution_id,
                    **scope,
                },
            )
            for action, value in window.get("actions", {}).items():
                if action in row and float(row[action]) != float(value):
                    raise CascadeCampaignError(
                        f"solution {solution_id}: conflicting {action} on day {day}, scope {key[1:]}."
                    )
                bound = CONTROL_BOUNDS[action]
                row[action] = int(value) if bound.integer else float(value)
    return tuple(merged[key] for key in sorted(merged))


def expand_variants(
    payload: Mapping[str, Any],
    *,
    cascade_ids: Iterable[str] | None = None,
    solution_ids: Iterable[str] | None = None,
) -> tuple[PreparedVariant, ...]:
    """Expand configured cascades into normal, untreated and solution variants."""

    selected_cascades = set(cascade_ids or ())
    selected_solutions = set(solution_ids or ())
    days = int(payload["campaign"]["days"])
    variants: list[PreparedVariant] = []
    found_cascades: set[str] = set()
    found_solutions: set[str] = set()
    for cascade in payload["cascades"]:
        cascade_id = str(cascade["id"])
        if selected_cascades and cascade_id not in selected_cascades:
            continue
        found_cascades.add(cascade_id)
        paired_engine_args = _validate_paired_cascade_engine_args(
            cascade.get("paired_engine_args", []),
            label=f"cascade {cascade_id}.paired_engine_args",
        )
        incident_events = tuple(dict(event) for event in cascade["incident"]["risk_events"])
        variants.extend(
            (
                PreparedVariant(
                    cascade_id=cascade_id,
                    variant_id="normal",
                    case_type="normal",
                    solution_id="",
                    label="Fonctionnement normal",
                    lever_fidelity="reference",
                    native_levers=(),
                    approximation_levers=(),
                    approximation_notes="",
                    risk_events=(),
                    schedule_rows=(),
                    engine_args=paired_engine_args,
                ),
                PreparedVariant(
                    cascade_id=cascade_id,
                    variant_id="incident_no_action",
                    case_type="incident_no_action",
                    solution_id="",
                    label="Incident sans action",
                    lever_fidelity="reference",
                    native_levers=(),
                    approximation_levers=(),
                    approximation_notes="",
                    risk_events=incident_events,
                    schedule_rows=(),
                    engine_args=paired_engine_args,
                ),
            )
        )
        for solution in cascade["solutions"]:
            solution_id = str(solution["id"])
            if selected_solutions and solution_id not in selected_solutions:
                continue
            found_solutions.add(solution_id)
            variants.append(
                PreparedVariant(
                    cascade_id=cascade_id,
                    variant_id=f"incident_{solution_id}",
                    case_type="incident_with_solution",
                    solution_id=solution_id,
                    label=str(solution.get("label") or solution_id),
                    lever_fidelity=str(solution["lever_fidelity"]),
                    native_levers=tuple(str(value) for value in solution.get("native_levers", [])),
                    approximation_levers=tuple(
                        str(value) for value in solution.get("approximation_levers", [])
                    ),
                    approximation_notes=str(solution.get("approximation_notes") or ""),
                    risk_events=incident_events,
                    schedule_rows=_merge_schedule_windows(solution, days=days),
                    engine_args=(
                        *paired_engine_args,
                        *_validate_engine_args(
                            solution.get("engine_args", []),
                            label=f"solution {solution_id}.engine_args",
                        ),
                    ),
                )
            )
    missing_cascades = sorted(selected_cascades - found_cascades)
    if missing_cascades:
        raise CascadeCampaignError("Unknown cascade ids: " + ", ".join(missing_cascades))
    if selected_solutions:
        configured = {
            str(solution["id"])
            for cascade in payload["cascades"]
            if not selected_cascades or str(cascade["id"]) in selected_cascades
            for solution in cascade["solutions"]
        }
        missing_solutions = sorted(selected_solutions - configured)
        if missing_solutions:
            raise CascadeCampaignError("Unknown solution ids: " + ", ".join(missing_solutions))
    return tuple(variants)


def _write_csv(path: Path, rows: Sequence[Mapping[str, Any]], columns: Sequence[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(columns), extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _prepare_inputs(
    *,
    output_root: Path,
    variants: Sequence[PreparedVariant],
    graph: Mapping[str, Any],
) -> dict[tuple[str, str], dict[str, Any]]:
    prepared: dict[tuple[str, str], dict[str, Any]] = {}
    catalog = _graph_catalog(graph)
    incident_paths: dict[str, Path] = {}
    for variant in variants:
        key = (variant.cascade_id, variant.variant_id)
        risk_path: Path | None = None
        if variant.risk_events:
            risk_path = incident_paths.get(variant.cascade_id)
            if risk_path is None:
                risk_path = (
                    output_root
                    / "prepared_inputs"
                    / variant.cascade_id
                    / "supplier_risk_events.csv"
                )
                _write_csv(risk_path, variant.risk_events, RISK_EVENT_COLUMNS)
                incident_paths[variant.cascade_id] = risk_path
        schedule_path: Path | None = None
        if variant.schedule_rows:
            schedule_path = (
                output_root
                / "prepared_inputs"
                / variant.cascade_id
                / f"{variant.variant_id}_control_schedule.csv"
            )
            _write_csv(schedule_path, variant.schedule_rows, CONTROL_SCHEDULE_COLUMNS)
            try:
                load_control_schedule(schedule_path, catalog=catalog)
            except ControlScheduleError as exc:
                raise CascadeCampaignError(
                    f"Invalid control schedule for {variant.cascade_id}/"
                    f"{variant.variant_id}: {exc}"
                ) from exc
        prepared[key] = {
            "risk_path": risk_path,
            "risk_sha256": _sha256(risk_path) if risk_path else "",
            "schedule_path": schedule_path,
            "schedule_sha256": _sha256(schedule_path) if schedule_path else "",
        }
    return prepared


def _read_csv(
    path: Path,
    *,
    required_columns: Iterable[str] = (),
) -> list[dict[str, str]]:
    if not path.is_file():
        raise CascadeCampaignError(f"Required engine artifact is missing: {path}")
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        columns = set(reader.fieldnames or ())
        missing = sorted(set(required_columns) - columns)
        if missing:
            raise CascadeCampaignError(
                f"Required columns missing from {path}: {', '.join(missing)}"
            )
        return [dict(row) for row in reader]


def _required_number(row: Mapping[str, Any], name: str, *, context: str) -> float:
    raw = row.get(name)
    if raw in {None, ""}:
        raise CascadeCampaignError(f"Missing numeric {name} in {context}.")
    try:
        value = float(raw)
    except (TypeError, ValueError) as exc:
        raise CascadeCampaignError(f"Invalid numeric {name}={raw!r} in {context}.") from exc
    if not math.isfinite(value):
        raise CascadeCampaignError(f"Non-finite numeric {name} in {context}.")
    return value


def _optional_number(row: Mapping[str, Any], name: str, *, context: str) -> float | None:
    if row.get(name) in {None, ""}:
        return None
    return _required_number(row, name, context=context)


def _required_day(row: Mapping[str, Any], *, context: str) -> int:
    value = _required_number(row, "day", context=context)
    if not value.is_integer():
        raise CascadeCampaignError(f"Non-integer day={value!r} in {context}.")
    return int(value)


def _require_day_coverage(
    days: Iterable[int],
    *,
    expected_days: int,
    context: str,
) -> None:
    observed = set(days)
    expected = set(range(expected_days))
    if observed != expected:
        missing = sorted(expected - observed)
        unexpected = sorted(observed - expected)
        raise CascadeCampaignError(
            f"Incomplete measured-day coverage for {context}: "
            f"missing={missing[:10]}, unexpected={unexpected[:10]}, "
            f"expected_days={expected_days}."
        )


def customer_daily_series(
    result_dir: Path,
    *,
    customer_id: str,
    item_id: str,
    expected_days: int | None = None,
) -> dict[int, dict[str, float]]:
    """Return daily demand, service and backlog for one exact customer/item."""

    path = result_dir / "data" / "production_demand_service_daily.csv"
    rows = _read_csv(
        path,
        required_columns=(
            "day",
            "node_id",
            "item_id",
            "demand_qty",
            "served_qty",
            "backlog_end_qty",
        ),
    )
    result: dict[int, dict[str, float]] = {}
    for row in rows:
        if row.get("node_id") != customer_id or row.get("item_id") != item_id:
            continue
        context = f"{path} customer={customer_id} item={item_id}"
        day = _required_day(row, context=context)
        if day in result:
            raise CascadeCampaignError(
                f"Duplicate customer/item/day row for {customer_id}/{item_id}/day {day} in {path}."
            )
        result[day] = {
            "demand": _required_number(row, "demand_qty", context=context),
            "served": _required_number(row, "served_qty", context=context),
            "backlog": _required_number(row, "backlog_end_qty", context=context),
        }
    if not result:
        raise CascadeCampaignError(
            f"No customer trajectory for {customer_id}/{item_id} in {path}."
        )
    if expected_days is not None:
        _require_day_coverage(
            result, expected_days=expected_days, context=f"{customer_id}/{item_id} in {path}"
        )
    return result


def production_daily_series(
    result_dir: Path,
    *,
    node_id: str,
    item_id: str,
    expected_days: int | None = None,
) -> dict[int, float]:
    path = result_dir / "data" / "production_output_products_daily.csv"
    rows = _read_csv(
        path,
        required_columns=("day", "node_id", "item_id", "produced_qty"),
    )
    result: dict[int, float] = {}
    for row in rows:
        if row.get("node_id") != node_id or row.get("item_id") != item_id:
            continue
        context = f"{path} node={node_id} item={item_id}"
        day = _required_day(row, context=context)
        if day in result:
            raise CascadeCampaignError(
                f"Duplicate production node/item/day row for {node_id}/{item_id}/day {day} in {path}."
            )
        result[day] = _required_number(row, "produced_qty", context=context)
    if not result:
        raise CascadeCampaignError(
            f"No production trajectory for {node_id}/{item_id} in {path}."
        )
    if expected_days is not None:
        _require_day_coverage(
            result, expected_days=expected_days, context=f"{node_id}/{item_id} in {path}"
        )
    return result


def _absolute_recovery_day(
    series: Mapping[int, Mapping[str, float]],
    *,
    start_day: int,
    consecutive_days: int,
    tolerance: float,
) -> int | None:
    if not series:
        return None
    last_day = max(series)
    positive_days = [
        day
        for day in range(start_day, last_day + 1)
        if series[day]["backlog"] > tolerance
    ]
    if not positive_days:
        return None
    candidate = max(positive_days) + 1
    if candidate + consecutive_days - 1 > last_day:
        return None
    return (
        candidate
        if all(
            series[day]["backlog"] <= tolerance
            for day in range(candidate, candidate + consecutive_days)
        )
        else None
    )


def _sum_stock_selectors(
    result_dir: Path,
    selectors: Sequence[Mapping[str, Any]],
    *,
    expected_days: int,
) -> float:
    total = 0.0
    for selector in selectors:
        path = result_dir / "data" / str(selector.get("file") or "")
        column = str(selector.get("column") or "stock_end_of_day")
        rows = _read_csv(
            path,
            required_columns=("day", "node_id", "item_id", column),
        )
        node_id = str(selector.get("node_id") or "")
        item_id = str(selector.get("item_id") or "")
        selected = [
            row
            for row in rows
            if (not node_id or row.get("node_id") == node_id)
            and (not item_id or row.get("item_id") == item_id)
        ]
        if not selected:
            raise CascadeCampaignError(
                f"No stock rows for selector {node_id}/{item_id} in {path}."
            )
        _require_day_coverage(
            (_required_day(row, context=str(path)) for row in selected),
            expected_days=expected_days,
            context=f"stock selector {node_id}/{item_id} in {path}",
        )
        total += sum(
            _required_number(row, column, context=str(path)) for row in selected
        )
    return total


_RISK_EFFECT_SPECS: Mapping[str, tuple[str, str, str]] = {
    "quality_delay": ("quality_delay_days", "absolute", "added_days_per_applied_flow"),
    "lead_time_extra_days": (
        "lead_time_extra_days",
        "absolute",
        "added_days_per_applied_flow",
    ),
    "quality_yield": (
        "quality_yield_multiplier",
        "multiplier_deficit",
        "fraction_lost_per_applied_flow",
    ),
    "lead_time": ("lead_time_multiplier", "multiplier_deficit", "multiplier_deviation"),
    "availability": (
        "availability_multiplier",
        "multiplier_deficit",
        "fraction_unavailable_per_applied_flow",
    ),
    "capacity": (
        "capacity_multiplier",
        "multiplier_deficit",
        "capacity_fraction_lost_per_applied_flow",
    ),
    "reliability": (
        "reliability_multiplier",
        "multiplier_deficit",
        "reliability_fraction_lost_per_applied_flow",
    ),
    "stock_writeoff": (
        "stock_writeoff_fraction",
        "absolute",
        "fraction_written_off_per_applied_flow",
    ),
}


def _risk_evidence(
    rows: Sequence[Mapping[str, Any]],
    events: Sequence[Mapping[str, Any]],
    *,
    context: str,
) -> dict[str, Any]:
    event_type = {str(event["event_id"]): str(event["risk_type"]) for event in events}
    applied_ids: set[str] = set()
    relevant_unique_rows: set[tuple[str, ...]] = set()
    evidence: dict[str, dict[str, Any]] = {}
    for risk_type in sorted(set(event_type.values())):
        column, transform, unit = _RISK_EFFECT_SPECS[risk_type]
        ids_for_type = {event_id for event_id, value in event_type.items() if value == risk_type}
        effect_rows: dict[tuple[str, ...], Mapping[str, Any]] = {}
        for row in rows:
            row_ids = {
                token.strip()
                for token in str(row.get("event_ids") or "").split(",")
                if token.strip()
            }
            matched = row_ids & ids_for_type
            if not matched:
                continue
            applied_ids.update(matched)
            key = tuple(
                str(row.get(name) or "")
                for name in ("day", "supplier_id", "dst_node_id", "item_id", "edge_id", "event_ids")
            ) + (str(row.get(column) or ""),)
            effect_rows[key] = row
            relevant_unique_rows.add(key[:-1])
        effect_sum = 0.0
        for row in effect_rows.values():
            value = _required_number(row, column, context=context)
            effect_sum += abs(1.0 - value) if transform == "multiplier_deficit" else abs(value)
        evidence[risk_type] = {
            "configured_event_ids": sorted(ids_for_type),
            "applied_event_ids": sorted(ids_for_type & applied_ids),
            "unique_applied_flow_rows": len(effect_rows),
            "effect_sum": effect_sum,
            "effect_sum_unit": unit,
        }
    return {
        "applied_event_ids": sorted(applied_ids),
        "unique_applied_row_count": len(relevant_unique_rows),
        "effects": evidence,
    }


def _expected_action_signatures(
    schedule_rows: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Return contiguous planned action windows with their exact CSV lines.

    ``schedule_rows`` is written unchanged after the CSV header, hence its
    zero-based position maps deterministically to engine ``source_line``
    position + 2.  Keeping that mapping prevents an applied action on another
    day, scope or requested value from being accepted as evidence for the
    configured intervention.
    """

    planned: dict[tuple[str, str, str, str, str, float], dict[int, int]] = {}
    for row_index, row in enumerate(schedule_rows):
        scope = tuple(
            str(row.get(name) or "")
            for name in ("node_id", "supplier_id", "item_id", "dst_node_id")
        )
        day = _required_day(row, context="configured control schedule")
        for action in CONTROL_BOUNDS:
            if action not in row:
                continue
            requested = _required_number(
                row, action, context=f"configured control schedule day={day}"
            )
            key = (action, *scope, requested)
            if day in planned.setdefault(key, {}):
                raise CascadeCampaignError(
                    f"Duplicate configured {action} action for day {day} and scope {scope}."
                )
            planned[key][day] = row_index + 2

    signatures: list[dict[str, Any]] = []
    for key, day_to_line in sorted(planned.items()):
        action, node_id, supplier_id, item_id, dst_node_id, requested = key
        days = sorted(day_to_line)
        windows: list[list[int]] = []
        for day in days:
            if not windows or day != windows[-1][-1] + 1:
                windows.append([day])
            else:
                windows[-1].append(day)
        for window_days in windows:
            signatures.append(
                {
                    "action": action,
                    "source_node_id": node_id,
                    "source_supplier_id": supplier_id,
                    "source_item_id": item_id,
                    "source_dst_node_id": dst_node_id,
                    "requested": requested,
                    "start_day": window_days[0],
                    "end_day": window_days[-1],
                    "planned_day_to_source_line": {
                        day: day_to_line[day] for day in window_days
                    },
                }
            )
    return signatures


def _action_evidence(
    *,
    ledger: Sequence[Mapping[str, Any]],
    shipments: Sequence[Mapping[str, Any]],
    schedule_rows: Sequence[Mapping[str, Any]],
    context: str,
) -> dict[str, Any]:
    expected = _expected_action_signatures(schedule_rows)
    shipment_volume: dict[tuple[int, str, str, str, str], tuple[float, str]] = {}
    for row in shipments:
        shipment_context = f"{context} supplier shipment"
        day = _required_day(row, context=shipment_context)
        qty = _required_number(row, "shipped_qty", context=shipment_context)
        key = (
            day,
            str(row.get("src_node_id") or ""),
            str(row.get("dst_node_id") or ""),
            str(row.get("item_id") or ""),
            str(row.get("edge_id") or ""),
        )
        prior_qty, prior_uom = shipment_volume.get(key, (0.0, ""))
        shipment_volume[key] = (prior_qty + max(0.0, qty), prior_uom or str(row.get("uom") or ""))

    verified_rows: list[dict[str, Any]] = []
    rejected_rows: list[dict[str, Any]] = []
    for row in ledger:
        if str(row.get("status") or "") != "applied":
            continue
        if row.get("source_line") in {None, ""}:
            continue
        row_context = f"{context} action ledger"
        action = str(row.get("action") or "")
        if action not in CONTROL_BOUNDS:
            continue
        day = _required_day(row, context=row_context)
        source_line_value = _required_number(row, "source_line", context=row_context)
        if not source_line_value.is_integer():
            raise CascadeCampaignError(f"Non-integer source_line in {row_context}.")
        source_line = int(source_line_value)
        requested = _required_number(row, "requested", context=row_context)
        effective = _required_number(row, "effective", context=row_context)
        neutral = float(CONTROL_BOUNDS[action].neutral)
        matching_plans = [
            signature
            for signature in expected
            if signature["action"] == action
            and signature["start_day"] <= day <= signature["end_day"]
            and signature["planned_day_to_source_line"].get(day) == source_line
            and all(
                not signature[source_name]
                or str(row.get(source_name) or "") == signature[source_name]
                for source_name in (
                    "source_node_id",
                    "source_supplier_id",
                    "source_item_id",
                    "source_dst_node_id",
                )
            )
            and math.isclose(requested, float(signature["requested"]), abs_tol=1e-12)
            and math.isclose(effective, float(signature["requested"]), abs_tol=1e-12)
        ]
        resolved_scope_consistent = all(
            not str(row.get(source_name) or "")
            or str(row.get(resolved_name) or "") == str(row.get(source_name) or "")
            for source_name, resolved_name in (
                ("source_node_id", "resolved_node_id"),
                ("source_supplier_id", "resolved_supplier_id"),
                ("source_item_id", "resolved_item_id"),
                ("source_dst_node_id", "resolved_dst_node_id"),
            )
        )
        if (
            not matching_plans
            or math.isclose(requested, neutral, abs_tol=1e-12)
            or math.isclose(effective, neutral, abs_tol=1e-12)
            or str(row.get("action_stage") or "") == "schedule_audit"
            or not resolved_scope_consistent
        ):
            rejected_rows.append(
                {
                    "action": action,
                    "day": day,
                    "source_line": source_line,
                    "requested": requested,
                    "effective": effective,
                    "reason": "planned day/scope/value/line mismatch or neutral action",
                }
            )
            continue
        volume = _optional_number(
            row, "executed_control_volume_qty", context=row_context
        )
        uom = str(row.get("quantity_uom") or "").strip()
        volume_source = "executed_control_volume_qty"
        if (volume is None or volume <= 1e-9) and action == "priority_weight":
            key = (
                day,
                str(row.get("resolved_supplier_id") or ""),
                str(row.get("resolved_dst_node_id") or ""),
                str(row.get("resolved_item_id") or ""),
                str(row.get("edge_id") or ""),
            )
            volume, shipment_uom = shipment_volume.get(key, (0.0, ""))
            uom = uom or shipment_uom
            volume_source = "matched_supplier_shipped_qty"
        if volume is None or volume <= 1e-9 or not uom:
            continue
        verified_rows.append(
            {
                "action": action,
                "resolved_node_id": str(row.get("resolved_node_id") or ""),
                "resolved_supplier_id": str(row.get("resolved_supplier_id") or ""),
                "resolved_item_id": str(row.get("resolved_item_id") or ""),
                "resolved_dst_node_id": str(row.get("resolved_dst_node_id") or ""),
                "source_node_id": str(row.get("source_node_id") or ""),
                "source_supplier_id": str(row.get("source_supplier_id") or ""),
                "source_item_id": str(row.get("source_item_id") or ""),
                "source_dst_node_id": str(row.get("source_dst_node_id") or ""),
                "uom": uom,
                "physical_volume_qty": float(volume),
                "physical_volume_source": volume_source,
                "action_stage": str(row.get("action_stage") or ""),
                "day": day,
                "source_line": source_line,
                "requested": requested,
                "effective": effective,
            }
        )

    grouped: dict[tuple[str, str, str, str, str, str, str], dict[str, Any]] = {}
    for row in verified_rows:
        key = tuple(
            str(row[name])
            for name in (
                "action",
                "resolved_node_id",
                "resolved_supplier_id",
                "resolved_item_id",
                "resolved_dst_node_id",
                "uom",
                "physical_volume_source",
            )
        )
        group = grouped.setdefault(
            key,
            {
                "action": row["action"],
                "resolved_target": {
                    "node_id": row["resolved_node_id"],
                    "supplier_id": row["resolved_supplier_id"],
                    "item_id": row["resolved_item_id"],
                    "dst_node_id": row["resolved_dst_node_id"],
                },
                "uom": row["uom"],
                "physical_volume_source": row["physical_volume_source"],
                "physical_volume_qty": 0.0,
                "row_count": 0,
                "first_day": row["day"],
                "last_day": row["day"],
            },
        )
        group["physical_volume_qty"] += float(row["physical_volume_qty"])
        group["row_count"] += 1
        group["first_day"] = min(int(group["first_day"]), int(row["day"]))
        group["last_day"] = max(int(group["last_day"]), int(row["day"]))

    expected_results: list[dict[str, Any]] = []
    for signature in expected:
        matches = [
            row
            for row in verified_rows
            if row["action"] == signature["action"]
            and signature["start_day"] <= row["day"] <= signature["end_day"]
            and signature["planned_day_to_source_line"].get(row["day"])
            == row["source_line"]
            and math.isclose(
                float(row["requested"]), float(signature["requested"]), abs_tol=1e-12
            )
            and math.isclose(
                float(row["effective"]), float(signature["requested"]), abs_tol=1e-12
            )
            and all(
                not signature[source_name]
                or row[source_name] == signature[source_name]
                for source_name in (
                    "source_node_id",
                    "source_supplier_id",
                    "source_item_id",
                    "source_dst_node_id",
                )
            )
        ]
        expected_results.append(
            {
                **signature,
                "planned_day_to_source_line": {
                    str(day): line
                    for day, line in signature["planned_day_to_source_line"].items()
                },
                "verified": bool(matches),
            }
        )
    verified_signature_count = sum(bool(row["verified"]) for row in expected_results)
    status = (
        "not_applicable"
        if not expected_results
        else "fully_verified"
        if verified_signature_count == len(expected_results)
        else "partially_verified"
        if verified_signature_count
        else "not_verified"
    )
    return {
        "status": status,
        "expected_signature_count": len(expected_results),
        "verified_signature_count": verified_signature_count,
        "verified_row_count": len(verified_rows),
        "evidence": {
            "verification_rule": (
                "ledger status equals applied; source CSV line, planned day/window, configured "
                "scope and requested/effective values match exactly; requested and effective "
                "values are non-neutral; resolved scope is coherent; UOM is present and physical "
                "volume is positive; priority additionally requires a matching positive shipment"
            ),
            "expected_signatures": expected_results,
            "verified_groups": list(grouped.values()),
            "rejected_applied_rows": rejected_rows,
        },
    }


def _load_measurement_start_hashes(
    result_dir: Path, *, expected_warmup_days: int
) -> tuple[str, dict[str, str]]:
    summary_path = result_dir / "summaries" / "first_simulation_summary.json"
    summary = _load_json_object(summary_path, label="Engine summary")
    audit = ((summary.get("policy") or {}).get("warmup_boundary_audit") or {})
    if not isinstance(audit, Mapping):
        raise CascadeCampaignError(f"Invalid warm-up boundary audit in {summary_path}.")
    expected_contract = {
        "schema_version": "etudecas.engine_warmup_boundary_audit.v1",
        "method": "deterministic_paired_burn_in_replay",
        "scope": "core_dynamic_engine_state_not_restart_checkpoint",
        "physical_warmup_days": expected_warmup_days,
        "measured_cutover_day": 0,
        "restart_checkpoint_available": False,
    }
    mismatches = {
        field: {"expected": expected, "observed": audit.get(field)}
        for field, expected in expected_contract.items()
        if audit.get(field) != expected
    }
    if mismatches:
        raise CascadeCampaignError(
            f"Invalid measurement-start audit contract in {summary_path}: {mismatches}."
        )
    core = str(audit.get("core_state_sha256") or "")
    components = audit.get("component_sha256")
    if len(core) != 64 or not isinstance(components, Mapping) or not components:
        raise CascadeCampaignError(
            f"Missing complete measurement-start state hashes in {summary_path}."
        )
    normalized = {str(key): str(value) for key, value in components.items()}
    if any(len(value) != 64 for value in normalized.values()):
        raise CascadeCampaignError(f"Invalid component state hash in {summary_path}.")
    return core, normalized


def _cost_metrics(result_dir: Path, *, expected_days: int) -> dict[str, float]:
    daily_path = result_dir / "data" / "first_simulation_daily.csv"
    columns = (
        "day",
        "total_supply_cost_day",
        "operational_purchase_cost_day",
        "operational_transport_cost_day",
        "opening_open_order_purchase_cost_day",
        "opening_open_order_transport_cost_day",
        "external_procurement_purchase_cost_day",
        "external_procurement_transport_cost_day",
        "holding_cost_day",
        "warehouse_operating_cost_day",
        "inventory_risk_cost_day",
        "production_cost_day",
    )
    rows = _read_csv(daily_path, required_columns=columns)
    _require_day_coverage(
        (_required_day(row, context=str(daily_path)) for row in rows),
        expected_days=expected_days,
        context=str(daily_path),
    )
    totals = {name: 0.0 for name in columns if name != "day"}
    for row in rows:
        context = f"{daily_path} day={row.get('day')}"
        values = {
            name: _required_number(row, name, context=context)
            for name in totals
        }
        reconstructed_base = sum(
            values[name]
            for name in (
                "operational_purchase_cost_day",
                "operational_transport_cost_day",
                "holding_cost_day",
                "warehouse_operating_cost_day",
                "inventory_risk_cost_day",
                "production_cost_day",
            )
        )
        if abs(reconstructed_base - values["total_supply_cost_day"]) > 0.001:
            raise CascadeCampaignError(
                f"Daily supply-cost identity failed in {context}: reported="
                f"{values['total_supply_cost_day']}, reconstructed={reconstructed_base}."
            )
        for name, value in values.items():
            totals[name] += value

    base = totals["total_supply_cost_day"]
    opening_transport = totals["opening_open_order_transport_cost_day"]
    opening_purchase = totals["opening_open_order_purchase_cost_day"]
    external_transport = totals["external_procurement_transport_cost_day"]
    external_purchase = totals["external_procurement_purchase_cost_day"]
    controllable = base + external_transport + external_purchase
    decision_total = controllable + opening_transport + opening_purchase
    summary_path = result_dir / "summaries" / "first_simulation_summary.json"
    summary = _load_json_object(summary_path, label="Engine summary")
    kpis = summary.get("kpis")
    if not isinstance(kpis, Mapping):
        raise CascadeCampaignError(f"Missing kpis in {summary_path}.")
    summary_total = _required_number(kpis, "total_cost", context=str(summary_path))
    summary_external = _required_number(
        kpis, "total_external_procurement_cost", context=str(summary_path)
    )
    summary_reconstruction = summary_total + summary_external
    tolerance = max(0.25, expected_days * 0.001, abs(summary_reconstruction) * 1e-8)
    if abs(decision_total - summary_reconstruction) > tolerance:
        raise CascadeCampaignError(
            f"Daily/summary decision-cost identity failed in {result_dir}: "
            f"daily={decision_total}, summary={summary_reconstruction}, tolerance={tolerance}."
        )
    return {
        "base_operational_supply_cost": base,
        "opening_transport_cost": opening_transport,
        "opening_purchase_cost": opening_purchase,
        "external_transport_cost": external_transport,
        "external_purchase_cost": external_purchase,
        "controllable_operating_cost": controllable,
        "decision_total_cost": decision_total,
        "decision_transport_cost": (
            totals["operational_transport_cost_day"]
            + opening_transport
            + external_transport
        ),
        "decision_purchase_cost": (
            totals["operational_purchase_cost_day"]
            + opening_purchase
            + external_purchase
        ),
    }


def extract_run_metrics(
    result_dir: Path,
    cascade: Mapping[str, Any],
    *,
    expected_days: int,
    expected_warmup_days: int,
    expected_schedule_rows: Sequence[Mapping[str, Any]] = (),
) -> dict[str, Any]:
    """Extract exact cascade KPIs from one completed canonical engine run."""

    customer_id = str(cascade["customer_id"])
    finished_item = str(cascade["finished_item_id"])
    incident = cascade["incident"]
    series = customer_daily_series(
        result_dir,
        customer_id=customer_id,
        item_id=finished_item,
        expected_days=expected_days,
    )
    recovery_days = int(cascade.get("recovery_consecutive_days", 7))
    backlog_tolerance = float(cascade.get("backlog_tolerance_qty", 1e-6))
    recovery = _absolute_recovery_day(
        series,
        start_day=int(incident["end_day"]) + 1,
        consecutive_days=recovery_days,
        tolerance=backlog_tolerance,
    )
    production_target = cascade["production_target"]
    production = production_daily_series(
        result_dir,
        node_id=str(production_target["node_id"]),
        item_id=str(production_target["item_id"]),
        expected_days=expected_days,
    )
    campaign_path = result_dir / "data" / "production_campaigns.csv"
    campaigns = [
        row
        for row in _read_csv(
            campaign_path,
            required_columns=("node_id", "output_item_id", "actual_lot_starts", "completed_lot_qty", "blocked_lot_qty"),
        )
        if row.get("node_id") == str(production_target["node_id"])
        and row.get("output_item_id") == str(production_target["item_id"])
    ]
    order_target = cascade["order_target"]
    orders_path = result_dir / "data" / "mrp_orders_daily.csv"
    orders = [
        row
        for row in _read_csv(
            orders_path,
            required_columns=("node_id", "item_id", "release_qty"),
        )
        if row.get("node_id") == str(order_target["node_id"])
        and row.get("item_id") == str(order_target["item_id"])
    ]
    ledger_path = result_dir / "data" / "canonical_action_ledger.csv"
    scheduled_actions = {
        action
        for row in expected_schedule_rows
        for action in CONTROL_BOUNDS
        if action in row
    }
    required_action_evidence_columns: tuple[str, ...] = (
        (
            "executed_control_volume_qty",
            "quantity_uom",
            "action_stage",
        )
        if scheduled_actions
        else ()
    )
    if "priority_weight" in scheduled_actions:
        required_action_evidence_columns = (
            *required_action_evidence_columns,
            "edge_id",
        )
    ledger = _read_csv(
        ledger_path,
        required_columns=(
            "day",
            "action",
            "status",
            "source_line",
            "resolved_node_id",
            "resolved_supplier_id",
            "resolved_item_id",
            "resolved_dst_node_id",
            "source_node_id",
            "source_supplier_id",
            "source_item_id",
            "source_dst_node_id",
            *required_action_evidence_columns,
        ),
    )
    shipments = _read_csv(
        result_dir / "data" / "production_supplier_shipments_daily.csv",
        required_columns=(
            "day",
            "src_node_id",
            "dst_node_id",
            "item_id",
            "edge_id",
            "shipped_qty",
            "uom",
        ),
    )
    action = _action_evidence(
        ledger=ledger,
        shipments=shipments,
        schedule_rows=expected_schedule_rows,
        context=str(result_dir),
    )
    risk_path = result_dir / "data" / "supplier_risk_events_applied_daily.csv"
    risk_rows = _read_csv(
        risk_path,
        required_columns=(
            "day",
            "supplier_id",
            "dst_node_id",
            "item_id",
            "edge_id",
            "event_ids",
        ),
    )
    risk = _risk_evidence(
        risk_rows,
        incident.get("risk_events", []),
        context=str(risk_path),
    )
    core_hash, component_hashes = _load_measurement_start_hashes(
        result_dir, expected_warmup_days=expected_warmup_days
    )
    cost = _cost_metrics(result_dir, expected_days=expected_days)
    return {
        "customer_id": customer_id,
        "finished_item_id": finished_item,
        "customer_shortage_days": sum(
            1 for row in series.values() if row["backlog"] > backlog_tolerance
        ),
        "customer_backlog_qty_days": sum(row["backlog"] for row in series.values()),
        "recovery_day": "" if recovery is None else recovery,
        "recovery_observed": recovery is not None,
        "customer_demand_qty": sum(row["demand"] for row in series.values()),
        "customer_served_qty": sum(row["served"] for row in series.values()),
        "production_qty": sum(production.values()),
        "production_lot_count": sum(
            _required_number(row, "actual_lot_starts", context=str(campaign_path))
            for row in campaigns
        ),
        "completed_lot_qty": sum(
            _required_number(row, "completed_lot_qty", context=str(campaign_path))
            for row in campaigns
        ),
        "blocked_lot_qty": sum(
            _required_number(row, "blocked_lot_qty", context=str(campaign_path))
            for row in campaigns
        ),
        "target_order_qty": sum(
            _required_number(row, "release_qty", context=str(orders_path)) for row in orders
        ),
        "target_order_count": len(orders),
        "target_stock_qty_days": _sum_stock_selectors(
            result_dir,
            cascade.get("stock_selectors", []),
            expected_days=expected_days,
        ),
        **cost,
        "supplier_risk_applied_row_count": risk["unique_applied_row_count"],
        "supplier_risk_applied_event_ids": ";".join(risk["applied_event_ids"]),
        "supplier_risk_effects_json": json.dumps(
            risk["effects"], ensure_ascii=False, sort_keys=True
        ),
        "action_execution_status": action["status"],
        "expected_action_signature_count": action["expected_signature_count"],
        "verified_action_signature_count": action["verified_signature_count"],
        "verified_action_row_count": action["verified_row_count"],
        "verified_action_evidence_json": json.dumps(
            action["evidence"], ensure_ascii=False, sort_keys=True
        ),
        "measurement_start_state_sha256": core_hash,
        "measurement_start_component_sha256_json": json.dumps(
            component_hashes, ensure_ascii=False, sort_keys=True
        ),
        "pairing_status": "pending_pair_validation",
        "incident_validation_status": "pending_incident_validation",
    }


def _run_engine(command: Sequence[str], *, result_dir: Path) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(
        list(command),
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    result_dir.mkdir(parents=True, exist_ok=True)
    (result_dir / "campaign_engine_stdout.log").write_text(
        completed.stdout or "", encoding="utf-8"
    )
    (result_dir / "campaign_engine_stderr.log").write_text(
        completed.stderr or "", encoding="utf-8"
    )
    return completed


def _git_provenance() -> dict[str, Any]:
    def read(*args: str) -> str:
        result = subprocess.run(
            ["git", "-C", str(REPO_ROOT), *args],
            capture_output=True,
            text=True,
            check=False,
        )
        return result.stdout.strip() if result.returncode == 0 else ""

    commit = read("rev-parse", "HEAD")
    return {
        "commit": commit,
        "branch": read("branch", "--show-current"),
        "working_tree_dirty": bool(read("status", "--porcelain")),
        "available": bool(commit),
    }


def _validate_physical_campaign_rows(
    rows: list[dict[str, Any]],
    *,
    config: Mapping[str, Any],
    expected_days: int,
) -> int:
    """Enforce paired cutover state and a physically active untreated incident."""

    cascades = {str(row["id"]): row for row in config["cascades"]}
    guards = config.get("scientific_guards", {})
    require_positive_customer_exposure = _as_bool(
        guards.get("require_positive_incremental_customer_backlog", True),
        label=(
            "scientific_guards.require_positive_incremental_customer_backlog"
        ),
    )
    by_key = {
        (str(row["cascade_id"]), str(row["variant_id"]), int(row["seed"])): row
        for row in rows
    }
    new_failures = 0
    cascade_seeds = sorted(
        {(str(row["cascade_id"]), int(row["seed"])) for row in rows}
    )
    for cascade_id, seed in cascade_seeds:
        cascade = cascades[cascade_id]
        normal = by_key.get((cascade_id, "normal", seed))
        untreated = by_key.get((cascade_id, "incident_no_action", seed))
        group = [
            row
            for row in rows
            if str(row["cascade_id"]) == cascade_id and int(row["seed"]) == seed
        ]
        if normal is None or untreated is None:
            continue
        if normal.get("status") != "ok" or untreated.get("status") != "ok":
            continue
        reference_core = str(normal["measurement_start_state_sha256"])
        reference_components = str(normal["measurement_start_component_sha256_json"])
        pairing_failed = False
        for row in group:
            if row.get("status") != "ok":
                continue
            if (
                str(row.get("measurement_start_state_sha256") or "") != reference_core
                or str(row.get("measurement_start_component_sha256_json") or "")
                != reference_components
            ):
                row["status"] = "invalid_pairing"
                row["pairing_status"] = "measurement_start_state_mismatch"
                row["error"] = (
                    "Measurement-start core/component state hash differs from paired normal."
                )
                pairing_failed = True
                new_failures += 1
            else:
                row["pairing_status"] = "measurement_start_state_matched"
        if pairing_failed:
            continue

        configured_event_ids = {
            str(event["event_id"])
            for event in cascade["incident"].get("risk_events", [])
        }
        applied_event_ids = {
            value
            for value in str(
                untreated.get("supplier_risk_applied_event_ids") or ""
            ).split(";")
            if value
        }
        applied_row_count = int(
            _required_number(
                untreated,
                "supplier_risk_applied_row_count",
                context=f"run row {cascade_id}/incident_no_action/seed {seed}",
            )
        )
        incident_error = ""
        physical_application_verified = False
        if applied_row_count <= 0 or not configured_event_ids.issubset(applied_event_ids):
            incident_error = (
                "Untreated incident was not physically applied to every configured event: "
                f"configured={sorted(configured_event_ids)}, applied={sorted(applied_event_ids)}, "
                f"rows={applied_row_count}."
            )
        else:
            configured_risk_types = {
                str(event["risk_type"])
                for event in cascade["incident"].get("risk_events", [])
            }
            try:
                effects = json.loads(
                    str(untreated.get("supplier_risk_effects_json") or "")
                )
            except json.JSONDecodeError:
                effects = None
            if not isinstance(effects, Mapping):
                incident_error = (
                    "Untreated incident has no valid physical risk-effect evidence."
                )
            else:
                missing_effects: list[str] = []
                for risk_type in sorted(configured_risk_types):
                    evidence = effects.get(risk_type)
                    if not isinstance(evidence, Mapping):
                        missing_effects.append(f"{risk_type}:missing")
                        continue
                    effect_rows = _required_number(
                        evidence,
                        "unique_applied_flow_rows",
                        context=(
                            f"risk evidence {cascade_id}/incident_no_action/"
                            f"seed {seed}/{risk_type}"
                        ),
                    )
                    effect_sum = _required_number(
                        evidence,
                        "effect_sum",
                        context=(
                            f"risk evidence {cascade_id}/incident_no_action/"
                            f"seed {seed}/{risk_type}"
                        ),
                    )
                    if effect_rows <= 0.0 or effect_sum <= 1e-12:
                        missing_effects.append(
                            f"{risk_type}:rows={effect_rows:g},effect_sum={effect_sum:g}"
                        )
                if missing_effects:
                    incident_error = (
                        "Untreated incident has configured risk effects without positive "
                        "physical application evidence: "
                        + ", ".join(missing_effects)
                    )
                else:
                    physical_application_verified = True
        customer_exposure_detected = False
        if not incident_error:
            customer_id = str(cascade["customer_id"])
            item_id = str(cascade["finished_item_id"])
            normal_series = customer_daily_series(
                Path(str(normal["result_dir"])),
                customer_id=customer_id,
                item_id=item_id,
                expected_days=expected_days,
            )
            untreated_series = customer_daily_series(
                Path(str(untreated["result_dir"])),
                customer_id=customer_id,
                item_id=item_id,
                expected_days=expected_days,
            )
            tolerance = float(cascade.get("backlog_tolerance_qty", 1e-6))
            incremental_backlog = sum(
                max(
                    0.0,
                    untreated_series[day]["backlog"]
                    - normal_series[day]["backlog"],
                )
                for day in range(expected_days)
            )
            customer_exposure_detected = incremental_backlog > tolerance
            if (
                not customer_exposure_detected
                and require_positive_customer_exposure
            ):
                incident_error = (
                    "Untreated incident produced no positive incremental customer-backlog "
                    "area versus paired normal while the strict positive-exposure guard is "
                    "enabled."
                )
        if incident_error:
            untreated["status"] = "invalid_incident"
            untreated["incident_validation_status"] = (
                "physically_applied_no_customer_exposure_rejected_by_guard"
                if physical_application_verified and not customer_exposure_detected
                else "incident_not_physically_applied"
            )
            untreated["error"] = incident_error
            new_failures += 1
            for row in group:
                if row is not untreated and row.get("status") == "ok":
                    row["incident_validation_status"] = "reference_incident_gate_failed"
            continue
        normal["incident_validation_status"] = "reference_no_incident"
        untreated["incident_validation_status"] = (
            "physically_applied_with_customer_exposure"
            if customer_exposure_detected
            else "physically_applied_no_customer_exposure"
        )
        for row in group:
            if row is not normal and row is not untreated and row.get("status") == "ok":
                row["incident_validation_status"] = (
                    "paired_untreated_incident_with_customer_exposure"
                    if customer_exposure_detected
                    else "paired_untreated_incident_no_customer_exposure"
                )
    return new_failures


def run_campaign(
    *,
    config_path: Path = DEFAULT_CONFIG_PATH,
    output_dir: Path,
    seeds: Sequence[int] | None = None,
    cascade_ids: Sequence[str] | None = None,
    solution_ids: Sequence[str] | None = None,
    graph_path: Path | None = None,
    engine_path: Path = DEFAULT_ENGINE_SCRIPT,
    artifact_profile: str = "full",
    prepare_only: bool = False,
    fail_fast: bool = False,
    jobs: int = 1,
) -> Path:
    """Prepare and optionally execute one isolated cascade campaign."""

    config_path = Path(config_path).resolve()
    config = _load_json_object(config_path, label="Cascade campaign config")
    campaign = config.get("campaign", {})
    if graph_path is None:
        graph_value = str(campaign.get("graph") or "auto")
        graph_path = discover_canonical_graph(REPO_ROOT, graph_value)
    if graph_path is None or not Path(graph_path).is_file():
        raise CascadeCampaignError("Canonical graph could not be resolved.")
    graph_path = Path(graph_path).resolve()
    graph = _load_json_object(graph_path, label="Canonical graph")
    validate_campaign_config(config, graph)
    variants = expand_variants(
        config, cascade_ids=cascade_ids, solution_ids=solution_ids
    )
    if not variants:
        raise CascadeCampaignError("No campaign variants were selected.")
    selected_seeds = tuple(
        sorted(
            set(
                int(seed)
                for seed in (
                    seeds if seeds is not None else campaign.get("seeds", [])
                )
            )
        )
    )
    if not selected_seeds or any(seed < 0 for seed in selected_seeds):
        raise CascadeCampaignError("At least one non-negative seed is required.")
    if artifact_profile not in {"compact", "full"}:
        raise CascadeCampaignError("artifact_profile must be compact or full.")
    if isinstance(jobs, bool) or int(jobs) < 1:
        raise CascadeCampaignError("jobs must be an integer >= 1.")
    jobs = int(jobs)
    artifact_args = (
        _FULL_ARTIFACT_ARGS if artifact_profile == "full" else _COMPACT_ARTIFACT_ARGS
    )
    resolved_engine = Path(engine_path).resolve()
    if not resolved_engine.is_file():
        raise CascadeCampaignError(f"Engine script does not exist: {resolved_engine}")
    profile_value = str(campaign.get("engine_profile") or "")
    profile_path = _resolve_path(profile_value, relative_to=config_path.resolve().parent)
    profile_args, profile_metadata = load_canonical_engine_profile(
        REPO_ROOT, str(profile_path)
    )
    campaign_args = _validate_engine_args(
        campaign.get("engine_args", []), label="campaign.engine_args"
    )
    warmup_arg = _engine_arg_value(campaign_args, "--warmup-days")
    if warmup_arg is None:  # guarded by validate_campaign_config; retain fail-closed use.
        raise CascadeCampaignError("campaign.engine_args has no --warmup-days value.")
    expected_warmup_days = _as_int(
        warmup_arg, label="campaign.engine_args --warmup-days", minimum=0
    )
    selected_cascade_ids = {variant.cascade_id for variant in variants}
    resolved_paired_state_inputs = _resolve_paired_state_inputs(
        config,
        cascade_ids=selected_cascade_ids,
        config_dir=config_path.parent,
    )
    output_root = _safe_output_root(output_dir)
    snapshot_path = output_root / "canonical_cascade_config_snapshot.json"
    snapshot_path.write_text(
        json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    prepared = _prepare_inputs(
        output_root=output_root, variants=variants, graph=graph
    )
    frozen_paired_args, paired_state_input_ledger = _freeze_paired_state_inputs(
        output_root=output_root,
        resolved_inputs=resolved_paired_state_inputs,
    )
    cascade_by_id = {str(row["id"]): row for row in config["cascades"]}
    commands: list[dict[str, Any]] = []
    command_lookup: dict[tuple[str, str, int], list[str]] = {}
    for variant in variants:
        inputs = prepared[(variant.cascade_id, variant.variant_id)]
        for seed in selected_seeds:
            result_dir = (
                output_root
                / "runs"
                / variant.cascade_id
                / variant.variant_id
                / f"seed_{seed}"
            )
            command = [
                sys.executable,
                str(resolved_engine),
                "--input",
                str(graph_path),
                "--output-dir",
                str(result_dir),
                "--scenario-id",
                str(campaign["scenario_id"]),
                "--days",
                str(int(campaign["days"])),
                "--seed",
                str(seed),
                *artifact_args,
                *profile_args,
                *campaign_args,
                *frozen_paired_args[variant.cascade_id],
                "--common-random-numbers",
                "--no-supplier-state-dependent-risks",
            ]
            if inputs["risk_path"] is not None:
                command.extend(["--supplier-risk-events-csv", str(inputs["risk_path"])])
            if inputs["schedule_path"] is not None:
                command.extend(["--control-schedule-csv", str(inputs["schedule_path"])])
            command_lookup[(variant.cascade_id, variant.variant_id, seed)] = command
            commands.append(
                {
                    "cascade_id": variant.cascade_id,
                    "variant_id": variant.variant_id,
                    "case_type": variant.case_type,
                    "solution_id": variant.solution_id,
                    "seed": seed,
                    "result_dir": str(result_dir),
                    "risk_events_csv": str(inputs["risk_path"] or ""),
                    "control_schedule_csv": str(inputs["schedule_path"] or ""),
                    "lever_fidelity": variant.lever_fidelity,
                    "approximation_notes": variant.approximation_notes,
                    "command": command,
                }
            )
    commands_path = output_root / "canonical_cascade_commands.json"
    commands_path.write_text(
        json.dumps(commands, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    task_rows: list[tuple[int, PreparedVariant, Mapping[str, Any], int, Path, dict[str, Any]]] = []
    task_index = 0
    for variant in variants:
        inputs = prepared[(variant.cascade_id, variant.variant_id)]
        cascade = cascade_by_id[variant.cascade_id]
        for seed in selected_seeds:
            result_dir = (
                output_root
                / "runs"
                / variant.cascade_id
                / variant.variant_id
                / f"seed_{seed}"
            )
            common = {
                "cascade_id": variant.cascade_id,
                "variant_id": variant.variant_id,
                "case_type": variant.case_type,
                "solution_id": variant.solution_id,
                "seed": seed,
                "result_dir": str(result_dir),
                "days": int(campaign["days"]),
                "scenario_id": str(campaign["scenario_id"]),
                "native_levers": ";".join(variant.native_levers),
                "approximation_levers": ";".join(variant.approximation_levers),
                "lever_fidelity": variant.lever_fidelity,
                "risk_events_sha256": inputs["risk_sha256"],
                "control_schedule_sha256": inputs["schedule_sha256"],
                "graph_sha256": _sha256(graph_path),
                "engine_profile_sha256": str(profile_metadata.get("sha256") or ""),
            }
            task_rows.append((task_index, variant, cascade, seed, result_dir, common))
            task_index += 1

    run_rows_by_index: dict[int, dict[str, Any]] = {}
    failures = 0
    skipped_fail_fast = 0
    if prepare_only:
        for index, _variant, cascade, _seed, _result_dir, common in task_rows:
            run_rows_by_index[index] = {
                **common,
                "status": "planned",
                "returncode": "",
                "error": "",
                "customer_id": str(cascade["customer_id"]),
                "finished_item_id": str(cascade["finished_item_id"]),
            }
    else:
        def execute_task(
            task: tuple[int, PreparedVariant, Mapping[str, Any], int, Path, dict[str, Any]]
        ) -> tuple[int, dict[str, Any], bool]:
            index, variant, cascade, seed, result_dir, common = task
            try:
                completed = _run_engine(
                    command_lookup[(variant.cascade_id, variant.variant_id, seed)],
                    result_dir=result_dir,
                )
            except Exception as exc:  # retain an auditable row for launch failures
                return index, {
                    **common,
                    "status": "launch_failed",
                    "returncode": "",
                    "error": str(exc),
                    "customer_id": str(cascade["customer_id"]),
                    "finished_item_id": str(cascade["finished_item_id"]),
                }, True
            if completed.returncode != 0:
                return index, {
                    **common,
                    "status": "failed",
                    "returncode": completed.returncode,
                    "error": (completed.stderr or completed.stdout).strip()[-2000:],
                    "customer_id": str(cascade["customer_id"]),
                    "finished_item_id": str(cascade["finished_item_id"]),
                }, True
            try:
                metrics = extract_run_metrics(
                    result_dir,
                    cascade,
                    expected_days=int(campaign["days"]),
                    expected_warmup_days=expected_warmup_days,
                    expected_schedule_rows=variant.schedule_rows,
                )
            except Exception as exc:  # preserve failed output for audit
                return index, {
                    **common,
                    "status": "invalid_output",
                    "returncode": 0,
                    "error": str(exc),
                    "customer_id": str(cascade["customer_id"]),
                    "finished_item_id": str(cascade["finished_item_id"]),
                }, True
            return index, {
                **common,
                "status": "ok",
                "returncode": 0,
                "error": "",
                **metrics,
            }, False

        with ThreadPoolExecutor(max_workers=jobs, thread_name_prefix="cascade-run") as executor:
            futures: dict[Future[tuple[int, dict[str, Any], bool]], int] = {
                executor.submit(execute_task, task): task[0] for task in task_rows
            }
            stop_submitting_results = False
            for future in as_completed(futures):
                index = futures[future]
                if future.cancelled():
                    task = task_rows[index]
                    _task_index, _variant, cascade, _seed, _result_dir, common = task
                    run_rows_by_index[index] = {
                        **common,
                        "status": "skipped_fail_fast",
                        "returncode": "",
                        "error": "Cancelled before start after another run failed.",
                        "customer_id": str(cascade["customer_id"]),
                        "finished_item_id": str(cascade["finished_item_id"]),
                    }
                    skipped_fail_fast += 1
                    continue
                try:
                    result_index, row, failed = future.result()
                except Exception as exc:  # defensive: preserve manifest generation
                    task = task_rows[index]
                    _task_index, _variant, cascade, _seed, _result_dir, common = task
                    result_index, row, failed = index, {
                        **common,
                        "status": "worker_failed",
                        "returncode": "",
                        "error": str(exc),
                        "customer_id": str(cascade["customer_id"]),
                        "finished_item_id": str(cascade["finished_item_id"]),
                    }, True
                run_rows_by_index[result_index] = row
                if failed:
                    failures += 1
                    if fail_fast and not stop_submitting_results:
                        stop_submitting_results = True
                        for other in futures:
                            if other is not future:
                                other.cancel()

    run_rows = [run_rows_by_index[index] for index in sorted(run_rows_by_index)]
    if not prepare_only and not failures and not skipped_fail_fast:
        failures += _validate_physical_campaign_rows(
            run_rows,
            config=config,
            expected_days=int(campaign["days"]),
        )
    runs_path = output_root / "canonical_cascade_runs.csv"
    _write_csv(runs_path, run_rows, RUN_COLUMNS)
    manifest = {
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": (
            "prepared_only"
            if prepare_only
            else "completed_with_failures"
            if failures
            else "complete"
        ),
        "config": {
            "path": str(config_path.resolve()),
            "snapshot": str(snapshot_path),
            "sha256": _sha256(snapshot_path),
        },
        "graph": {"path": str(graph_path), "sha256": _sha256(graph_path)},
        "engine": {"path": str(resolved_engine), "sha256": _sha256(resolved_engine)},
        "engine_profile": profile_metadata,
        "artifact_profile": artifact_profile,
        "scenario_id": str(campaign["scenario_id"]),
        "days": int(campaign["days"]),
        "seeds": list(selected_seeds),
        "common_random_numbers": True,
        "state_dependent_risks": False,
        "paired_state_inputs": paired_state_input_ledger,
        "cascade_ids": sorted({variant.cascade_id for variant in variants}),
        "variant_ids": [variant.variant_id for variant in variants],
        "run_count": len(run_rows),
        "failure_count": failures,
        "skipped_fail_fast_count": skipped_fail_fast,
        "jobs": jobs,
        "fail_fast_semantics": (
            "best_effort: pending subprocesses are cancelled after the first observed "
            "failure; already-running subprocesses finish and remain audited"
        ),
        "git": _git_provenance(),
        "outputs": {
            "runs": str(runs_path),
            "commands": str(commands_path),
            "config_snapshot": str(snapshot_path),
        },
        "output_sha256": {
            "runs": _sha256(runs_path),
            "commands": _sha256(commands_path),
            "config_snapshot": _sha256(snapshot_path),
        },
    }
    manifest_path = output_root / "canonical_cascade_manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    if failures:
        raise CascadeCampaignError(
            f"Cascade campaign completed with {failures} failed or invalid runs; "
            f"see {runs_path}."
        )
    return manifest_path


def validate_only(config_path: Path, *, graph_path: Path | None = None) -> dict[str, Any]:
    """Validate configuration and graph without creating artifacts."""

    config = _load_json_object(config_path, label="Cascade campaign config")
    campaign = config.get("campaign", {})
    if graph_path is None:
        graph_path = discover_canonical_graph(
            REPO_ROOT, str(campaign.get("graph") or "auto")
        )
    if graph_path is None:
        raise CascadeCampaignError("Canonical graph could not be resolved.")
    graph = _load_json_object(Path(graph_path), label="Canonical graph")
    validate_campaign_config(config, graph)
    variants = expand_variants(config)
    return {
        "schema_version": CONFIG_SCHEMA_VERSION,
        "valid": True,
        "cascade_count": len(config["cascades"]),
        "variant_count": len(variants),
        "solution_count": sum(
            len(cascade["solutions"]) for cascade in config["cascades"]
        ),
        "graph_path": str(Path(graph_path).resolve()),
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--graph", type=Path)
    parser.add_argument("--engine", type=Path, default=DEFAULT_ENGINE_SCRIPT)
    parser.add_argument("--seeds", type=int, nargs="+")
    parser.add_argument("--cascade", action="append", default=[])
    parser.add_argument("--solution", action="append", default=[])
    parser.add_argument(
        "--artifact-profile", choices=("compact", "full"), default="full"
    )
    parser.add_argument("--prepare-only", action="store_true")
    parser.add_argument("--validate-only", action="store_true")
    parser.add_argument("--fail-fast", action="store_true")
    parser.add_argument(
        "--jobs",
        type=int,
        default=1,
        help=(
            "Parallel physical engine subprocesses (default 1). Each run writes to "
            "a unique directory; output rows remain deterministically ordered."
        ),
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.validate_only:
            result = validate_only(args.config, graph_path=args.graph)
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0
        if args.output_dir is None:
            raise CascadeCampaignError("--output-dir is required unless --validate-only is used.")
        manifest = run_campaign(
            config_path=args.config,
            output_dir=args.output_dir,
            seeds=args.seeds,
            cascade_ids=args.cascade,
            solution_ids=args.solution,
            graph_path=args.graph,
            engine_path=args.engine,
            artifact_profile=args.artifact_profile,
            prepare_only=args.prepare_only,
            fail_fast=args.fail_fast,
            jobs=args.jobs,
        )
    except CascadeCampaignError as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 2
    print(f"[OK] Cascade campaign manifest: {manifest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "CONFIG_SCHEMA_VERSION",
    "MANIFEST_SCHEMA_VERSION",
    "RUN_COLUMNS",
    "CascadeCampaignError",
    "PreparedVariant",
    "customer_daily_series",
    "expand_variants",
    "extract_run_metrics",
    "production_daily_series",
    "run_campaign",
    "validate_campaign_config",
    "validate_only",
]
