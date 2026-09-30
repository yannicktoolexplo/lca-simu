"""Recorded replay sources, KPI extraction and lot-trace evidence."""

from __future__ import annotations

from contextlib import ExitStack
import csv
from dataclasses import dataclass
import hashlib
import json
import math
from pathlib import Path
from typing import Any, Iterator, Literal

from .ranking import ScenarioCandidate

REPO_ROOT = Path(__file__).resolve().parents[4]


def load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"Expected a JSON object in {path}")
    return data


def finite_float(value: Any) -> float | None:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None
    return numeric if math.isfinite(numeric) else None


def nested_value(data: dict[str, Any], path: str) -> Any:
    value: Any = data
    for part in path.split("."):
        if not isinstance(value, dict) or part not in value:
            return None
        value = value[part]
    return value


def _summary_path(run_dir: Path) -> Path:
    candidates = (
        run_dir / "summaries" / "first_simulation_summary.json",
        run_dir / "first_simulation_summary.json",
    )
    for candidate in candidates:
        if candidate.exists():
            return candidate
    raise FileNotFoundError(f"Missing first_simulation_summary.json under {run_dir}")


def _kpis_path(run_dir: Path) -> Path | None:
    candidates = (run_dir / "run" / "kpis.json", run_dir / "kpis.json")
    return next((candidate for candidate in candidates if candidate.exists()), None)


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _replanning_metrics(run_dir: Path, summary: dict[str, Any]) -> tuple[float | None, float | None]:
    summary_count = finite_float(
        nested_value(summary, "production_tracking.production_campaigns.delayed_campaign_rows")
    )
    summary_total = finite_float(
        nested_value(summary, "production_tracking.production_campaigns.campaign_rows")
    )
    campaign_rows = read_csv_rows(run_dir / "data" / "production_campaigns.csv")
    if campaign_rows:
        delayed_statuses = {
            "completed_after_delay",
            "still_blocked",
            "not_started_blocked",
            "planned_without_output",
        }
        delayed = sum(
            1
            for row in campaign_rows
            if str(row.get("status") or "") in delayed_statuses
            or (finite_float(row.get("delay_event_count")) or 0.0) > 0.0
        )
        total = len(campaign_rows)
        return float(delayed), float(delayed) / float(total) if total else None
    if summary_count is None:
        return None, None
    return summary_count, summary_count / summary_total if summary_total else None


KPI_PATHS: dict[str, tuple[str, ...]] = {
    "product_availability": ("kpis.fill_rate", "fill_rate"),
    "fill_rate": ("kpis.fill_rate", "fill_rate"),
    "ending_backlog": ("kpis.ending_backlog", "ending_backlog"),
    "total_cost": ("kpis.total_cost", "total_cost"),
    "total_external_procurement_cost": (
        "kpis.total_external_procurement_cost",
        "total_external_procurement_cost",
    ),
    "total_produced": ("kpis.total_produced", "total_produced"),
    "total_unreliable_loss_qty": (
        "kpis.total_unreliable_loss_qty",
        "total_unreliable_loss_qty",
    ),
    "supplier_capacity_binding_qty": (
        "kpis.total_supplier_capacity_binding_qty",
        "total_supplier_capacity_binding_qty",
    ),
}


def extract_run_metrics(run_dir: Path) -> dict[str, float | None]:
    """Extract stable business KPIs from either the summary or run package."""

    summary = load_json(_summary_path(run_dir))
    packaged_kpis: dict[str, Any] = {}
    packaged_path = _kpis_path(run_dir)
    if packaged_path:
        packaged_kpis = load_json(packaged_path)

    metrics: dict[str, float | None] = {}
    for name, paths in KPI_PATHS.items():
        value: float | None = None
        for path in paths:
            if "." in path:
                value = finite_float(nested_value(summary, path))
            else:
                value = finite_float(packaged_kpis.get(path))
            if value is not None:
                break
        metrics[name] = value

    replanning_count, replanning_rate = _replanning_metrics(run_dir, summary)
    metrics["production_replanning_count"] = replanning_count
    metrics["production_replanning_rate"] = replanning_rate
    return metrics


def _open_csv(
    path: Path, files: ExitStack,
) -> tuple[list[str], Iterator[list[str]]]:
    """Read a header now and keep its stream open until evidence is complete."""
    if not path.exists():
        return [], iter(())
    handle = files.enter_context(path.open("r", encoding="utf-8-sig", newline=""))
    reader = csv.reader(handle)
    return next(reader, []), reader


def _csv_evidence(
    table: tuple[list[str], Iterator[list[str]]],
    mode: Literal["", "causes", "links", "audit"] = "",
) -> dict[str, int]:
    """Count raw CSV rows and DictReader records in one bounded-memory pass."""
    columns, reader = table
    counts = {"rows": 0, "records": 0, "nominal_causes": 0, "causal_roots": 0, "audit_errors": 0}
    for row in reader:
        counts["rows"] += 1
        # csv.reader counts blank rows; DictReader skips them. Preserve both.
        if not row:
            continue
        counts["records"] += 1
        if not mode:
            continue
        record: dict[str | None, Any] = dict(zip(columns, row))
        # Match DictReader for duplicate headers and short or overlong rows.
        if len(row) < len(columns):
            for column in columns[len(row):]:
                record[column] = None
        elif len(row) > len(columns):
            record[None] = row[len(columns):]
        if mode == "causes":
            if str(record.get("causal_status") or "").strip() == "nominal" and (
                str(record.get("causal_event_ids") or "").strip()
                or str(record.get("causal_root_ids") or "").strip()
            ):
                counts["nominal_causes"] += 1
        elif mode == "links":
            counts["causal_roots"] += bool(str(record.get("causal_root_id") or "").strip())
        elif mode == "audit":
            counts["audit_errors"] += str(record.get("severity") or "").strip().lower() in {"error", "critical"}
    return counts


def lot_trace_evidence(run_dir: Path) -> dict[str, Any]:
    """Return auditable evidence that a replay produced lot-level artifacts."""

    summary = load_json(_summary_path(run_dir))
    summary_trace = nested_value(summary, "production_tracking.lot_trace")
    summary_trace = summary_trace if isinstance(summary_trace, dict) else {}
    data_dir = run_dir / "data"
    events_path = data_dir / "production_lot_events.csv"
    genealogy_path = data_dir / "production_lot_genealogy.csv"
    campaigns_path = data_dir / "production_campaigns.csv"
    causal_links_path = data_dir / "lot_causal_links.csv"
    state_events_path = data_dir / "supplier_state_dependent_risk_events.csv"
    audit_issues_path = data_dir / "lot_path_audit_issues.csv"
    run_manifest_path = run_dir / "run" / "run_manifest.json"
    packaged_capability: bool | None = None
    contract_version = ""
    if run_manifest_path.exists():
        packaged_manifest = load_json(run_manifest_path)
        capabilities = packaged_manifest.get("capabilities")
        if isinstance(capabilities, dict):
            raw_capability = capabilities.get("lot_trace_enabled")
            packaged_capability = bool(raw_capability) if raw_capability is not None else None
    contract_version = str(
        summary_trace.get("lot_trace_contract_version")
        or summary.get("lot_trace_contract_version")
        or ""
    )
    enabled = bool(summary_trace.get("enabled"))
    if packaged_capability is not None:
        enabled = enabled and packaged_capability

    with ExitStack() as files:
        event_table = _open_csv(events_path, files)
        event_columns = set(event_table[0])
        genealogy_table = _open_csv(genealogy_path, files)
        genealogy_columns = set(genealogy_table[0])
        causal_link_table = _open_csv(causal_links_path, files)
        causal_link_columns = set(causal_link_table[0])
        required_event_columns = {
            "event_id",
            "business_batch_id",
            "lot_occurrence_id",
            "shipment_id",
            "planned_order_id",
            "origin_production_order_ids",
            "origin_production_contributions_json",
            "causal_event_ids",
            "causal_root_ids",
            "causal_status",
        }
        required_genealogy_columns = {
            "parent_lot_id",
            "child_lot_id",
            "component_allocation_share",
            "planned_order_id",
            "replacement_transition_id",
            "causal_root_ids",
            "causal_status",
        }
        required_causal_link_columns = {
            "causal_root_id",
            "relation_type",
            "entity_type",
            "entity_id",
            "basis",
        }
        audit = _csv_evidence(_open_csv(audit_issues_path, files), "audit")
        causal = _csv_evidence(causal_link_table, "links")
        causal_link_rows = causal["records"]
        causal_root_link_rows = causal["causal_roots"]
        structural_link_rows = causal_link_rows - causal_root_link_rows
        state_events = _csv_evidence(_open_csv(state_events_path, files))
        state_event_rows = state_events["rows"]
        events = _csv_evidence(event_table, "causes")
        genealogy = _csv_evidence(genealogy_table, "causes")
        nominal_event_rows_with_causes = events["nominal_causes"]
        nominal_genealogy_rows_with_causes = genealogy["nominal_causes"]
        audit_error_rows = audit["audit_errors"]
        contract_ready = contract_version == "3.0"
        causal_index_ready = causal_links_path.exists() and required_causal_link_columns <= causal_link_columns
        evidence = {
            "enabled": enabled,
            "contract_version": contract_version,
            "contract_ready": contract_ready,
            "event_rows": events["rows"],
            "genealogy_rows": genealogy["rows"],
            "campaign_rows": _csv_evidence(_open_csv(campaigns_path, files))["rows"],
            "causal_link_rows": causal_link_rows,
            "causal_root_link_rows": causal_root_link_rows,
            "structural_link_rows": structural_link_rows,
            "state_event_rows": state_event_rows,
            "nominal_event_rows_with_causes": nominal_event_rows_with_causes,
            "nominal_genealogy_rows_with_causes": nominal_genealogy_rows_with_causes,
            "audit_issue_rows": audit["records"],
            "audit_error_rows": audit_error_rows,
            "causal_index_ready": causal_index_ready,
            "causal_coverage_status": (
                "causal_links_present"
                if causal_root_link_rows > 0
                else "no_lot_level_causal_effect"
                if state_event_rows > 0
                else "not_required_for_nominal_or_event_free_run"
            ),
            "missing_event_columns": sorted(required_event_columns - event_columns),
            "missing_genealogy_columns": sorted(required_genealogy_columns - genealogy_columns),
            "missing_causal_link_columns": sorted(required_causal_link_columns - causal_link_columns),
            "artifacts": {
                "events": str(events_path),
                "genealogy": str(genealogy_path),
                "campaigns": str(campaigns_path),
                "causal_links": str(causal_links_path),
                "state_events": str(state_events_path),
                "audit_issues": str(audit_issues_path),
                "run_manifest": str(run_manifest_path),
            },
        }
        evidence["valid"] = bool(
            evidence["enabled"]
            and contract_ready
            and evidence["event_rows"] > 0
            and evidence["genealogy_rows"] > 0
            and not evidence["missing_event_columns"]
            and not evidence["missing_genealogy_columns"]
            and causal_index_ready
            and audit_error_rows == 0
            and nominal_event_rows_with_causes == 0
            and nominal_genealogy_rows_with_causes == 0
            and events_path.exists()
            and genealogy_path.exists()
        )
        return evidence


def _resolve_path(value: str | Path, *, base_dir: Path, repo_root: Path) -> Path:
    path = Path(str(value))
    if path.is_absolute():
        return path.resolve()
    base_candidate = (base_dir / path).resolve()
    if base_candidate.exists():
        return base_candidate
    return (repo_root / path).resolve()


def _sha256(path: Path) -> str:
    if not path.exists() or not path.is_file():
        return ""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _command_value(command: list[str], flag: str) -> str:
    for index, token in enumerate(command):
        if token.startswith(f"{flag}="):
            return token.split("=", 1)[1]
        if token == flag and index + 1 < len(command):
            return command[index + 1]
    return ""


def _candidate_from_run(
    run_dir: Path,
    *,
    label: str,
    role: str,
    repo_root: Path,
) -> ScenarioCandidate:
    manifest_path = run_dir / "run_manifest.json"
    if not manifest_path.exists():
        raise FileNotFoundError(f"Missing rerun manifest: {manifest_path}")
    manifest = load_json(manifest_path)
    command = [str(value) for value in (manifest.get("simulator_command") or [])]
    if not command:
        raise ValueError(f"No simulator_command recorded in {manifest_path}")
    input_graph = _resolve_path(
        str(manifest.get("input_graph") or ""),
        base_dir=manifest_path.parent,
        repo_root=repo_root,
    )
    scenario_id = str(manifest.get("scenario_id") or "")
    command_scenario_id = _command_value(command, "--scenario-id")
    if command_scenario_id and command_scenario_id != scenario_id:
        raise ValueError(
            f"Scenario identity mismatch in {manifest_path}: "
            f"manifest={scenario_id!r}, command={command_scenario_id!r}"
        )
    return ScenarioCandidate(
        scenario_id=scenario_id,
        label=label,
        source_run_dir=run_dir.resolve(),
        source_manifest=manifest_path.resolve(),
        simulator_command=command,
        metrics=extract_run_metrics(run_dir),
        role=role,
        metadata={
            "input_graph": str(input_graph),
            "input_graph_sha256": _sha256(input_graph),
            "source_manifest_sha256": _sha256(manifest_path),
            "days": manifest.get("days"),
            "output_profile": manifest.get("output_profile"),
            "supplier_state_dependent_risks": manifest.get("supplier_state_dependent_risks"),
        },
    )


@dataclass(frozen=True)
class ReplayCatalog:
    source_run_dir: Path
    baseline: ScenarioCandidate
    candidates: tuple[ScenarioCandidate, ...]


def discover_replay_catalog(
    source_run_dir: str | Path,
    *,
    repo_root: str | Path | None = None,
) -> ReplayCatalog:
    """Discover the nominal and companion scenario runs from one pipeline output."""

    source_dir = Path(source_run_dir).resolve()
    repo = Path(repo_root).resolve() if repo_root else REPO_ROOT
    root_manifest_path = source_dir / "run_manifest.json"
    if not root_manifest_path.exists():
        raise FileNotFoundError(f"Missing root run manifest: {root_manifest_path}")
    root_manifest = load_json(root_manifest_path)
    baseline = _candidate_from_run(
        source_dir,
        label=str(root_manifest.get("baseline") or "Nominal"),
        role="baseline",
        repo_root=repo,
    )

    companion_rows = root_manifest.get("companion_runs") or {}
    if not isinstance(companion_rows, dict):
        raise ValueError(f"companion_runs must be an object in {root_manifest_path}")
    candidates: list[ScenarioCandidate] = []
    seen_scenario_ids = {baseline.scenario_id}
    for key, raw in companion_rows.items():
        if not isinstance(raw, dict):
            continue
        output_value = str(raw.get("output_dir") or "")
        if not output_value:
            continue
        run_dir = _resolve_path(output_value, base_dir=source_dir, repo_root=repo)
        candidate = _candidate_from_run(
            run_dir,
            label=str(raw.get("label") or key),
            role=str(raw.get("role") or "candidate"),
            repo_root=repo,
        )
        expected_scenario_id = str(raw.get("scenario_id") or "")
        if expected_scenario_id and expected_scenario_id != candidate.scenario_id:
            raise ValueError(
                f"Companion scenario mismatch for {key}: "
                f"root={expected_scenario_id!r}, run={candidate.scenario_id!r}"
            )
        if candidate.scenario_id in seen_scenario_ids:
            raise ValueError(f"Duplicate scenario_id in replay catalog: {candidate.scenario_id}")
        seen_scenario_ids.add(candidate.scenario_id)
        baseline_days = baseline.metadata.get("days")
        candidate_days = candidate.metadata.get("days")
        if (
            baseline_days is not None
            and candidate_days is not None
            and int(baseline_days) != int(candidate_days)
        ):
            raise ValueError(
                f"Horizon mismatch for {candidate.scenario_id}: "
                f"baseline={baseline_days}, scenario={candidate_days}"
            )
        candidates.append(candidate)
    if not candidates:
        raise ValueError(f"No rerunnable companion scenario found in {root_manifest_path}")
    return ReplayCatalog(source_run_dir=source_dir, baseline=baseline, candidates=tuple(candidates))
