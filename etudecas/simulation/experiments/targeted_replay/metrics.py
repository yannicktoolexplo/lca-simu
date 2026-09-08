"""Uniform KPI and lot-trace evidence extraction from simulation runs."""

from __future__ import annotations

import csv
import json
import math
from pathlib import Path
from typing import Any


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


def _csv_rows(path: Path) -> list[dict[str, str]]:
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
    campaign_rows = _csv_rows(run_dir / "data" / "production_campaigns.csv")
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


def _count_csv_rows(path: Path) -> int:
    if not path.exists():
        return 0
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.reader(handle)
        next(reader, None)
        return sum(1 for _ in reader)


def _count_nominal_rows_with_causes(path: Path) -> int:
    if not path.exists():
        return 0
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return sum(
            1
            for row in csv.DictReader(handle)
            if str(row.get("causal_status") or "").strip() == "nominal"
            and (
                str(row.get("causal_event_ids") or "").strip()
                or str(row.get("causal_root_ids") or "").strip()
            )
        )


def _csv_columns(path: Path) -> set[str]:
    if not path.exists():
        return set()
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return set(next(csv.reader(handle), []))


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

    event_columns = _csv_columns(events_path)
    genealogy_columns = _csv_columns(genealogy_path)
    causal_link_columns = _csv_columns(causal_links_path)
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
    audit_rows = _csv_rows(audit_issues_path)
    audit_error_rows = sum(
        str(row.get("severity") or "").strip().lower() in {"error", "critical"}
        for row in audit_rows
    )
    causal_rows = _csv_rows(causal_links_path)
    causal_link_rows = len(causal_rows)
    causal_root_link_rows = sum(
        bool(str(row.get("causal_root_id") or "").strip())
        for row in causal_rows
    )
    structural_link_rows = causal_link_rows - causal_root_link_rows
    state_event_rows = _count_csv_rows(state_events_path)
    nominal_event_rows_with_causes = _count_nominal_rows_with_causes(events_path)
    nominal_genealogy_rows_with_causes = _count_nominal_rows_with_causes(
        genealogy_path
    )
    contract_ready = contract_version == "3.0"
    causal_index_ready = causal_links_path.exists() and required_causal_link_columns <= causal_link_columns
    evidence = {
        "enabled": enabled,
        "contract_version": contract_version,
        "contract_ready": contract_ready,
        "event_rows": _count_csv_rows(events_path),
        "genealogy_rows": _count_csv_rows(genealogy_path),
        "campaign_rows": _count_csv_rows(campaigns_path),
        "causal_link_rows": causal_link_rows,
        "causal_root_link_rows": causal_root_link_rows,
        "structural_link_rows": structural_link_rows,
        "state_event_rows": state_event_rows,
        "nominal_event_rows_with_causes": nominal_event_rows_with_causes,
        "nominal_genealogy_rows_with_causes": nominal_genealogy_rows_with_causes,
        "audit_issue_rows": len(audit_rows),
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
