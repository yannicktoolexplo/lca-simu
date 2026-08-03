from __future__ import annotations

"""Reinject SCAN response playbooks into the canonical multi-item engine.

Two deliberately distinct integration modes are retained:

* ``overlay`` prepares the legacy fixed graph overlays for comparison and audit;
* ``run`` sends a bounded, precomputed daily control schedule to the canonical
  engine while leaving the graph and the MRP/lotification rules unchanged.

The daily schedule is an open-loop replay of decisions computed by the reduced
model.  It is not described as closed-loop canonical control because decisions
are not recalculated from the canonical state during the run.
"""

import copy
import csv
import hashlib
import json
import math
import subprocess
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np
import pandas as pd

from .core import Action, clamp, safe_float
from .risk_mapping import build_canonical_risk_events


DEFAULT_CANONICAL_GRAPH_CANDIDATES: tuple[str, ...] = (
    "etudecas/simulation_prep/result/reference_baseline/_mrp_bom_tests/bom_weekly_mps_lotified_no_static_fallback_physical_floor.json",
    "etudecas/simulation_prep/result/reference_baseline/supply_graph_reference_baseline_real_demand_target_calibrated_mrp_lot_policy_recalibrated_5y.json",
    "etudecas/simulation_prep/result/reference_baseline/supply_graph_reference_baseline_real_demand_target_calibrated_mrp_lot_policy_recalibrated.json",
)

MANAGED_CANONICAL_ENGINE_FLAGS: frozenset[str] = frozenset({
    "--input",
    "--output-dir",
    "--scenario-id",
    "--days",
    "--seed",
    "--output-profile",
    "--control-schedule-csv",
    "--supplier-risk-events-csv",
    "--common-random-numbers",
    "--no-common-random-numbers",
    "--supplier-state-dependent-risks",
    "--no-supplier-state-dependent-risks",
    "--skip-map",
    "--skip-plots",
    "--no-lot-trace",
    "--lot-trace",
    "--skip-lot-audit",
})

CANONICAL_KPI_NAMES: tuple[str, ...] = (
    "service",
    "mean_service",
    "min_service",
    "service_loss",
    "backlog_area_days",
    "max_backlog_days",
    "recovery_time_days",
    "recovery_time_lower_bound_days",
    "recovery_followup_days",
    "recovery_observed",
    "mean_inventory_days",
    "post_crisis_overstock_days",
    "order_nervousness",
    "production_nervousness",
    "expedite_area",
    "expedited_qty",
    "external_procurement_qty",
    "quality_loss_qty",
    "constraint_violations",
    "supplier_risk_area",
    "exogenous_supplier_risk_area",
    "endogenous_state_supplier_risk_area",
    "canonical_risk_creation_proxy",
    "risk_creation_index",
    "total_economic_exposure",
)

RISK_EFFECT_COLUMN_SPECS: dict[str, tuple[str, float]] = {
    "stock": ("stock_multiplier", 1.0),
    "capacity": ("capacity_multiplier", 1.0),
    "lead_time": ("lead_time_multiplier", 1.0),
    "lead_time_extra_days": ("lead_time_extra_days", 0.0),
    "quality_delay": ("quality_delay_days", 0.0),
    "reliability": ("reliability_multiplier", 1.0),
    "quality_yield": ("quality_yield_multiplier", 1.0),
    "availability": ("availability_multiplier", 1.0),
    "purchase_cost": ("purchase_cost_multiplier", 1.0),
    "transport_cost": ("transport_cost_multiplier", 1.0),
    "external_capacity": ("external_capacity_multiplier", 1.0),
    "external_availability": ("external_availability_multiplier", 1.0),
    "external_lead_time": ("external_lead_time_multiplier", 1.0),
    "external_lead_time_extra_days": (
        "external_lead_time_extra_days",
        0.0,
    ),
    "external_quality_yield": (
        "external_quality_yield_multiplier",
        1.0,
    ),
    "external_cost": ("external_cost_multiplier", 1.0),
    "stock_writeoff": ("stock_writeoff_fraction", 0.0),
}


def discover_canonical_graph(repo_root: Path, explicit: str = "auto") -> Path | None:
    if explicit != "auto":
        path = Path(explicit)
        if not path.is_absolute():
            path = repo_root / path
        return path.resolve() if path.exists() else None
    for relative in DEFAULT_CANONICAL_GRAPH_CANDIDATES:
        candidate = (repo_root / relative).resolve()
        if candidate.exists() and candidate.stat().st_size > 0:
            return candidate
    return None


def load_canonical_engine_profile(
    repo_root: Path,
    explicit: str = "",
) -> tuple[tuple[str, ...], dict[str, Any]]:
    """Load auditable, non-orchestrator engine arguments from JSON.

    The profile may be a JSON list or an object containing an ``args`` list.
    Process identity, output, randomness, risk-event and control-schedule flags
    remain owned by :func:`run_canonical_replays` and cannot be overridden.
    """

    if not str(explicit).strip():
        return (), {
            "enabled": False,
            "source_path": "",
            "sha256": "",
            "argument_count": 0,
            "name": "graph_defaults",
        }
    path = Path(explicit)
    if not path.is_absolute():
        path = repo_root / path
    path = path.resolve()
    if not path.exists() or not path.is_file():
        raise ValueError(
            f"Canonical engine profile does not exist or is not a file: {path}"
        )
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(
            f"Canonical engine profile is not valid UTF-8 JSON: {path}"
        ) from exc
    if isinstance(payload, list):
        raw_args = payload
        name = path.stem
        schema_version = ""
        description = ""
    elif isinstance(payload, Mapping):
        raw_args = payload.get("args")
        name = str(payload.get("name") or path.stem)
        schema_version = str(payload.get("schema_version") or "")
        description = str(payload.get("description") or "")
    else:
        raise ValueError(
            "Canonical engine profile must be a JSON list or an object "
            "containing an 'args' list."
        )
    if not isinstance(raw_args, list) or not all(
        isinstance(item, str) and item.strip() for item in raw_args
    ):
        raise ValueError(
            "Canonical engine profile 'args' must be a list of non-empty strings."
        )
    args = tuple(item.strip() for item in raw_args)
    for token in args:
        if "\x00" in token or "\n" in token or "\r" in token:
            raise ValueError(
                "Canonical engine profile arguments cannot contain control "
                "characters."
            )
        flag = token.split("=", 1)[0]
        if flag in MANAGED_CANONICAL_ENGINE_FLAGS:
            raise ValueError(
                f"Canonical engine profile cannot override managed flag {flag}."
            )
    return args, {
        "enabled": True,
        "source_path": str(path),
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "argument_count": len(args),
        "name": name,
        "schema_version": schema_version,
        "description": description,
    }


def expand_action_schedule(
    decisions: pd.DataFrame,
    actions: Sequence[Action],
    days: int,
) -> pd.DataFrame:
    """Expand reduced-model decisions into the canonical daily CSV contract.

    Blank scope columns deliberately mean "all matching canonical targets".  The
    reduced controller is portfolio-level today, so inventing supplier-item
    specificity here would be misleading.  Supplier-item-destination granularity
    remains preserved in the separate physical risk-event ledger.
    """

    by_name = {action.name: action for action in actions}
    reference = by_name.get("mrp_reference") or actions[0]
    schedule = pd.DataFrame({"day": np.arange(days, dtype=int)})
    schedule["policy"] = reference.name
    if not decisions.empty and "day" in decisions and "selected_policy" in decisions:
        ordered = decisions.sort_values("day")
        for _, row in ordered.iterrows():
            start = int(row["day"])
            name = str(row["selected_policy"])
            if name in by_name:
                schedule.loc[schedule["day"] >= start, "policy"] = name
    for field in (
        "order_gain",
        "production_gain",
        "expedite",
        "smoothing",
        "safety_stock_gain",
        "supplier_relief",
    ):
        schedule[field] = schedule["policy"].map(
            {name: getattr(action, field) for name, action in by_name.items()}
        ).astype(float)

    # Canonical control fields are dimensionless multipliers except the explicit
    # lead-time adjustment (calendar days) and expedite level ([0, 1]).
    schedule["node_id"] = ""
    schedule["supplier_id"] = ""
    schedule["item_id"] = ""
    schedule["dst_node_id"] = ""
    schedule["order_multiplier"] = (1.0 + schedule["order_gain"]).clip(0.50, 1.50)
    schedule["safety_stock_multiplier"] = (
        1.0 + schedule["safety_stock_gain"]
    ).clip(0.50, 2.00)
    schedule["production_target_multiplier"] = (
        1.0 + schedule["production_gain"]
    ).clip(0.50, 1.50)
    schedule["capacity_multiplier"] = (
        1.0 + schedule["production_gain"]
    ).clip(0.50, 1.50)
    schedule["external_procurement_multiplier"] = (
        1.0
        + 1.50 * schedule["expedite"]
        + 0.50 * schedule["order_gain"].clip(lower=0.0)
    ).clip(0.0, 2.00)
    schedule["expedite_level"] = schedule["expedite"].clip(0.0, 1.0)
    schedule["lead_time_adjustment_days"] = np.rint(
        -3.0 * schedule["expedite"]
    ).astype(int)
    # A portfolio-global priority multiplier would multiply every eligible lane
    # by the same number and therefore cancel during share normalization.  Keep
    # it exactly neutral until the reduced controller emits a genuinely
    # supplier/item-targeted priority.  ``smoothing`` likewise has no equivalent
    # in the strict daily contract: the canonical graph's existing production
    # smoothing remains unchanged instead of being silently reinterpreted.
    schedule["priority_weight"] = 1.0
    canonical_columns = [
        "day",
        "policy",
        "node_id",
        "supplier_id",
        "item_id",
        "dst_node_id",
        "order_multiplier",
        "safety_stock_multiplier",
        "production_target_multiplier",
        "capacity_multiplier",
        "external_procurement_multiplier",
        "expedite_level",
        "lead_time_adjustment_days",
        "priority_weight",
    ]
    canonical = schedule[canonical_columns].copy()
    canonical.attrs["reduced_action_lookup"] = {
        name: {
            field: float(getattr(action, field))
            for field in (
                "order_gain",
                "production_gain",
                "expedite",
                "smoothing",
                "safety_stock_gain",
                "supplier_relief",
            )
        }
        for name, action in by_name.items()
    }
    canonical.attrs["mapping_limitations"] = (
        "smoothing_keeps_canonical_graph_value",
        "global_supplier_relief_has_no_priority_allocation_effect",
    )
    return canonical


def fixed_action_schedule(action: Action, days: int) -> pd.DataFrame:
    """Build one neutral-or-fixed daily canonical schedule."""

    decisions = pd.DataFrame(
        [{"day": 0, "selected_policy": action.name}]
    )
    return expand_action_schedule(decisions, (action,), days)


def _schedule_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _event_tokens(values: pd.Series) -> list[set[str]]:
    return [
        {
            token.strip()
            for token in str(value or "").split(",")
            if token.strip()
        }
        for value in values
    ]


def _lane_rows(
    frame: pd.DataFrame,
    expected: pd.Series,
    *,
    supplier_column: str,
) -> pd.DataFrame:
    required = {
        supplier_column,
        "item_id",
        "dst_node_id",
    }
    if frame.empty or not required.issubset(frame.columns):
        return frame.iloc[0:0].copy()
    selected = frame.loc[
        (
            frame[supplier_column].astype(str)
            == str(expected.get("supplier_id") or "")
        )
        & (
            frame["item_id"].astype(str)
            == str(expected.get("item_id") or "")
        )
        & (
            frame["dst_node_id"].astype(str)
            == str(expected.get("dst_node_id") or "")
        )
    ].copy()
    expected_edge_id = str(
        expected.get("edge_id")
        or expected.get("canonical_edge_id")
        or ""
    )
    if expected_edge_id and "edge_id" in selected:
        selected = selected.loc[
            selected["edge_id"].astype(str).eq(expected_edge_id)
        ].copy()
    start_day = int(safe_float(expected.get("start_day"), 0))
    end_day = int(safe_float(expected.get("end_day"), start_day))
    if "day" not in selected:
        return selected.iloc[0:0].copy()
    event_day = pd.to_numeric(selected["day"], errors="coerce")
    return selected.loc[event_day.between(start_day, end_day)].copy()


def _nonzero_activity_count(
    frame: pd.DataFrame,
    quantity_columns: Sequence[str],
) -> int:
    available = [name for name in quantity_columns if name in frame]
    if frame.empty or not available:
        return 0
    quantities = pd.concat(
        [
            pd.to_numeric(frame[name], errors="coerce").abs()
            for name in available
        ],
        axis=1,
    ).fillna(0.0)
    return int(quantities.gt(1e-9).any(axis=1).sum())


def _risk_event_validation_rows(
    expected_risk_events: pd.DataFrame,
    *,
    applied: pd.DataFrame,
    shipments: pd.DataFrame,
    orders: pd.DataFrame,
) -> list[dict[str, Any]]:
    """Build event-level evidence from identity through non-zero lane flow."""

    if expected_risk_events.empty or "event_id" not in expected_risk_events:
        return []
    tokens_by_row = (
        _event_tokens(applied["event_ids"])
        if "event_ids" in applied
        else [set() for _ in applied.index]
    )
    rows: list[dict[str, Any]] = []
    for _, expected in expected_risk_events.iterrows():
        event_id = str(expected.get("event_id") or "")
        risk_type = (
            str(expected.get("risk_type") or "")
            .strip()
            .lower()
            .replace("-", "_")
            .replace(" ", "_")
        )
        matching_indexes = [
            index
            for index, tokens in enumerate(tokens_by_row)
            if event_id in tokens
        ]
        token_matches = applied.iloc[matching_indexes].copy()
        lane_matches = _lane_rows(
            token_matches,
            expected,
            supplier_column="supplier_id",
        )
        matched = not lane_matches.empty

        effect_column = ""
        expected_neutral = math.nan
        effect_non_neutral = False
        expected_effect_non_neutral = False
        effect_spec = RISK_EFFECT_COLUMN_SPECS.get(risk_type)
        if effect_spec is not None:
            effect_column, expected_neutral = effect_spec
            expected_multiplier = safe_float(
                expected.get("multiplier"),
                expected_neutral,
            )
            expected_effect_non_neutral = (
                abs(expected_multiplier - expected_neutral) > 1e-9
            )
            if matched and effect_column in lane_matches:
                applied_effect = pd.to_numeric(
                    lane_matches[effect_column],
                    errors="coerce",
                )
                effect_non_neutral = bool(
                    (applied_effect - expected_neutral)
                    .abs()
                    .gt(1e-9)
                    .any()
                )
        applied_effect_valid = bool(
            matched
            and effect_spec is not None
            and expected_effect_non_neutral
            and effect_non_neutral
        )

        shipment_lane = _lane_rows(
            shipments,
            expected,
            supplier_column="src_node_id",
        )
        order_lane = _lane_rows(
            orders,
            expected,
            supplier_column="src_node_id",
        )
        if "order_type" in order_lane:
            order_lane = order_lane.loc[
                ~order_lane["order_type"]
                .astype(str)
                .str.startswith("opening_")
            ].copy()
        shipment_activity_count = _nonzero_activity_count(
            shipment_lane,
            ("pulled_qty", "shipped_qty"),
        )
        order_activity_count = _nonzero_activity_count(
            order_lane,
            ("release_qty", "planned_receipt_qty"),
        )
        affected_nonzero_flow = bool(
            applied_effect_valid
            and (shipment_activity_count + order_activity_count) > 0
        )

        if not matched:
            status = "not_matched"
            reason = (
                "event_id_found_on_unexpected_lane"
                if not token_matches.empty
                else "event_id_not_found"
            )
        elif not applied_effect_valid:
            status = "matched_not_applied"
            if effect_spec is None:
                reason = "unsupported_risk_type"
            elif not expected_effect_non_neutral:
                reason = "expected_event_effect_is_neutral"
            elif effect_column not in lane_matches:
                reason = "appropriate_effect_column_missing"
            else:
                reason = "appropriate_effect_remained_neutral"
        elif not affected_nonzero_flow:
            status = "applied_no_nonzero_flow"
            reason = "no_nonzero_shipments_or_orders_on_event_lane"
        else:
            status = "affected_nonzero_flow"
            reason = ""
        rows.append(
            {
                "event_id": event_id,
                "risk_type": risk_type,
                "supplier_id": str(expected.get("supplier_id") or ""),
                "item_id": str(expected.get("item_id") or ""),
                "dst_node_id": str(expected.get("dst_node_id") or ""),
                "effect_column": effect_column,
                "matched": matched,
                "applied": applied_effect_valid,
                "affected_nonzero_flow": affected_nonzero_flow,
                "shipment_activity_row_count": shipment_activity_count,
                "order_activity_row_count": order_activity_count,
                "status": status,
                "error": reason,
            }
        )
    return rows


def _validate_canonical_result(
    result_dir: Path,
    *,
    expect_schedule: bool,
    expected_schedule_sha256: str,
    expected_days: int,
    expected_seed: int,
    expected_scenario_id: str,
    expected_input_path: Path,
    expected_risk_events: pd.DataFrame,
    expected_risk_csv_path: Path | None,
) -> list[str]:
    """Return explicit contract violations for a nominally successful replay."""

    errors: list[str] = []
    summary_path = result_dir / "summaries" / "first_simulation_summary.json"
    required_csvs = (
        "first_simulation_daily.csv",
        "canonical_action_ledger.csv",
        "mrp_orders_daily.csv",
        "production_output_products_daily.csv",
        "production_constraint_daily.csv",
        "production_supplier_shipments_daily.csv",
        "supplier_risk_events_applied_daily.csv",
    )
    if not summary_path.exists() or summary_path.stat().st_size <= 0:
        errors.append(
            "missing summaries/first_simulation_summary.json"
        )
        summary: dict[str, Any] = {}
    else:
        try:
            summary = json.loads(summary_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            errors.append(f"invalid engine summary JSON: {exc}")
            summary = {}

    frames: dict[str, pd.DataFrame] = {}
    for name in required_csvs:
        path = result_dir / "data" / name
        if not path.exists() or path.stat().st_size <= 0:
            errors.append(f"missing data/{name}")
            continue
        try:
            # Header-only diagnostic files are valid; malformed/zero-column CSVs
            # are not. The daily KPI source must contain the requested horizon.
            frame = pd.read_csv(path)
            frames[name] = frame
            if name == "first_simulation_daily.csv":
                if frame.empty:
                    errors.append("empty data/first_simulation_daily.csv")
                elif len(frame) != int(expected_days):
                    errors.append(
                        "daily row count mismatch: "
                        f"expected {int(expected_days)}, got {len(frame)}"
                    )
        except (OSError, UnicodeDecodeError, pd.errors.ParserError) as exc:
            errors.append(f"invalid data/{name}: {exc}")

    def same_resolved_path(actual: Any, expected: Path) -> bool:
        if not str(actual or "").strip():
            return False
        try:
            return Path(str(actual)).resolve() == expected.resolve()
        except (OSError, RuntimeError, ValueError):
            return False

    if str(summary.get("scenario_id") or "") != str(expected_scenario_id):
        errors.append(
            "scenario id mismatch: "
            f"expected {expected_scenario_id}, got "
            f"{summary.get('scenario_id') or '<empty>'}"
        )
    if int(safe_float(summary.get("sim_days"), -1)) != int(expected_days):
        errors.append(
            "summary horizon mismatch: "
            f"expected {int(expected_days)}, got "
            f"{summary.get('sim_days', '<missing>')}"
        )
    if not same_resolved_path(
        summary.get("input_file"),
        expected_input_path,
    ):
        errors.append(
            "engine input path mismatch: "
            f"expected {expected_input_path}, got "
            f"{summary.get('input_file') or '<empty>'}"
        )
    expected_input_sha256 = hashlib.sha256(
        expected_input_path.read_bytes()
    ).hexdigest()
    if str(summary.get("input_sha256") or "") != expected_input_sha256:
        errors.append(
            "engine input SHA-256 mismatch: "
            f"expected {expected_input_sha256}, got "
            f"{summary.get('input_sha256') or '<empty>'}"
        )

    policy = summary.get("policy", {}) if isinstance(summary, dict) else {}
    if int(safe_float(policy.get("seed"), -1)) != int(expected_seed):
        errors.append(
            "seed mismatch: "
            f"expected {int(expected_seed)}, got "
            f"{policy.get('seed', '<missing>')}"
        )
    if policy.get("common_random_numbers") is not True:
        errors.append(
            "common-random-numbers mismatch: expected true"
        )
    control = (
        policy.get("control_schedule", {})
        if isinstance(policy, dict)
        else {}
    )
    enabled = bool(control.get("enabled", False))
    if enabled != expect_schedule:
        errors.append(
            "control schedule enabled mismatch: "
            f"expected {expect_schedule}, got {enabled}"
        )
    actual_sha = str(control.get("sha256") or "")
    if expect_schedule and actual_sha != expected_schedule_sha256:
        errors.append(
            "control schedule SHA-256 mismatch: "
            f"expected {expected_schedule_sha256}, got {actual_sha or '<empty>'}"
        )
    if not expect_schedule and actual_sha:
        errors.append(
            "reference replay unexpectedly reports a control schedule SHA-256"
        )

    expected_event_ids = set(
        expected_risk_events.get(
            "event_id",
            pd.Series(dtype=str),
        )
        .dropna()
        .astype(str)
    )
    supplier_risk = (
        policy.get("supplier_risk", {})
        if isinstance(policy, dict)
        else {}
    )
    summary_event_count = int(
        safe_float(supplier_risk.get("event_count"), -1)
    )
    if summary_event_count != len(expected_event_ids):
        errors.append(
            "supplier risk event-count mismatch: "
            f"expected {len(expected_event_ids)}, got "
            f"{summary_event_count}"
        )
    if expected_event_ids:
        if supplier_risk.get("enabled") is not True:
            errors.append(
                "supplier risk disabled despite expected events"
            )
        if expected_risk_csv_path is None or not same_resolved_path(
            supplier_risk.get("events_csv"),
            expected_risk_csv_path,
        ):
            errors.append(
                "supplier risk CSV path mismatch: "
                f"expected {expected_risk_csv_path}, got "
                f"{supplier_risk.get('events_csv') or '<empty>'}"
            )
        expected_risk_sha256 = (
            hashlib.sha256(expected_risk_csv_path.read_bytes()).hexdigest()
            if expected_risk_csv_path is not None
            and expected_risk_csv_path.exists()
            else ""
        )
        if (
            str(supplier_risk.get("events_csv_sha256") or "")
            != expected_risk_sha256
        ):
            errors.append(
                "supplier risk CSV SHA-256 mismatch: "
                f"expected {expected_risk_sha256}, got "
                f"{supplier_risk.get('events_csv_sha256') or '<empty>'}"
            )

        applied = frames.get(
            "supplier_risk_events_applied_daily.csv",
            pd.DataFrame(),
        )
        required_applied_columns = {
            "day",
            "event_ids",
            "supplier_id",
            "item_id",
            "dst_node_id",
        }
        missing_applied_columns = sorted(
            required_applied_columns - set(applied.columns)
        )
        if missing_applied_columns:
            errors.append(
                "supplier risk applied ledger missing columns: "
                + ", ".join(missing_applied_columns)
            )
        elif applied.empty:
            errors.append(
                "expected supplier risk events produced no applied rows"
            )
        validation_rows = _risk_event_validation_rows(
            expected_risk_events,
            applied=applied,
            shipments=frames.get(
                "production_supplier_shipments_daily.csv",
                pd.DataFrame(),
            ),
            orders=frames.get(
                "mrp_orders_daily.csv",
                pd.DataFrame(),
            ),
        )
        pd.DataFrame(validation_rows).to_csv(
            result_dir
            / "data"
            / "canonical_supplier_risk_event_validation.csv",
            index=False,
        )
        for event_validation in validation_rows:
            status = str(event_validation["status"])
            if status == "affected_nonzero_flow":
                continue
            errors.append(
                "supplier risk event validation "
                f"status={status}: {event_validation['event_id']} "
                f"({event_validation['error']})"
            )

    ledger_path = result_dir / "data" / "canonical_action_ledger.csv"
    if ledger_path.exists() and ledger_path.stat().st_size > 0:
        try:
            ledger = pd.read_csv(ledger_path)
            required_ledger_columns = {"day", "action", "status"}
            if expect_schedule:
                required_ledger_columns.update(
                    {
                        "action_stage",
                        "executed_control_volume_qty",
                    }
                )
            missing = sorted(required_ledger_columns - set(ledger.columns))
            if missing:
                errors.append(
                    "canonical action ledger missing columns: "
                    + ", ".join(missing)
                )
            if expect_schedule and ledger.empty:
                errors.append(
                    "controlled replay produced an empty canonical action ledger"
                )
            if not expect_schedule and not ledger.empty:
                errors.append(
                    "reference no-schedule replay produced action ledger rows"
                )
        except (OSError, UnicodeDecodeError, pd.errors.ParserError):
            # The malformed-file error was already reported above.
            pass
    return errors


def duration_weighted_action(schedule: pd.DataFrame, *, name: str = "adaptive_weighted_replay") -> Action:
    if schedule.empty:
        return Action(name, 0, 0, 0, 0.25, 0, 0, "Empty adaptive schedule; MRP-equivalent overlay.")
    reduced_lookup = schedule.attrs.get("reduced_action_lookup", {})
    policy_counts = schedule["policy"].astype(str).value_counts(normalize=True)

    def reduced_mean(field: str, fallback: float) -> float:
        values = [
            float(weight) * float(reduced_lookup.get(policy, {}).get(field, fallback))
            for policy, weight in policy_counts.items()
        ]
        return float(sum(values)) if values else fallback

    means = {
        "order_gain": float(schedule["order_multiplier"].mean() - 1.0),
        "production_gain": float(schedule["production_target_multiplier"].mean() - 1.0),
        "expedite": float(schedule["expedite_level"].mean()),
        # These two reduced levers are retained only for the auditable legacy
        # overlay representation; the daily canonical port does not claim to
        # apply them without a targeted/typed primitive.
        "smoothing": reduced_mean("smoothing", 0.25),
        "safety_stock_gain": float(schedule["safety_stock_multiplier"].mean() - 1.0),
        "supplier_relief": reduced_mean("supplier_relief", 0.0),
    }
    return Action(
        name=name,
        description="Duration-weighted canonical replay of the adaptive reduced-order policy schedule.",
        **means,
    )


def _choose_scenario(graph: dict[str, Any], scenario_id: str) -> dict[str, Any]:
    scenarios = graph.get("scenarios") or []
    for scenario in scenarios:
        if str(scenario.get("id")) == scenario_id:
            return scenario
    if scenarios:
        return scenarios[0]
    scenario = {"id": scenario_id, "demand": []}
    graph["scenarios"] = [scenario]
    return scenario


def action_to_overlay_ledger(action: Action, graph: Mapping[str, Any], scenario_id: str) -> dict[str, Any]:
    scenario = next(
        (item for item in (graph.get("scenarios") or []) if str(item.get("id")) == scenario_id),
        (graph.get("scenarios") or [{}])[0] if (graph.get("scenarios") or []) else {},
    )
    base_safety = max(0.0, safe_float(scenario.get("safety_stock_days"), 7.0))
    base_fg = max(0.0, safe_float(scenario.get("fg_target_days"), 0.0))
    base_gap = max(0.01, safe_float(scenario.get("production_gap_gain"), 0.25))
    base_smoothing = clamp(safe_float(scenario.get("production_smoothing"), 0.20), 0.0, 0.95)
    econ = scenario.get("economic_policy") if isinstance(scenario.get("economic_policy"), dict) else {}
    base_external_cap = max(0.0, safe_float(econ.get("external_procurement_daily_cap_days"), 2.0))
    base_external_lead = max(0.0, safe_float(econ.get("external_procurement_lead_days"), 4.0))
    base_external_cost = max(0.1, safe_float(econ.get("external_procurement_cost_multiplier"), 2.0))

    target_smoothing = clamp(
        max(base_smoothing, 0.10 + 0.80 * action.smoothing + 0.10 * action.supplier_relief),
        0.0,
        0.95,
    )
    target_gap = clamp(
        base_gap * (1.0 + action.production_gain - 0.25 * action.supplier_relief),
        0.02,
        1.50,
    )
    return {
        "policy": action.name,
        "action": asdict(action),
        "scenario_patch": {
            "safety_stock_days": max(0.0, base_safety + 2.5 * action.safety_stock_gain + 1.5 * max(0.0, action.order_gain)),
            "fg_target_days": max(0.0, base_fg + 0.8 * max(0.0, action.safety_stock_gain)),
            "production_gap_gain": target_gap,
            "production_smoothing": target_smoothing,
            "external_procurement_daily_cap_days": max(0.0, base_external_cap * (1.0 + 1.8 * action.expedite + 0.7 * max(0.0, action.order_gain))),
            "external_procurement_lead_days": max(0.0, base_external_lead * (1.0 - 0.55 * action.expedite)),
            "external_procurement_cost_multiplier": base_external_cost * (1.0 + 0.35 * action.expedite),
        },
        "graph_scales": {
            "factory_capacity": max(0.50, 1.0 + action.production_gain),
            "opening_inventory": max(0.50, 1.0 + 0.18 * action.safety_stock_gain),
            "transport_lead_time": max(0.50, 1.0 - 0.35 * action.expedite),
        },
        "interpretation": {
            "order_gain": "Translated through safety-stock and external-procurement headroom; canonical MRP has no direct external order-gain port.",
            "supplier_relief": "Translated through stronger production smoothing and a lower production gap gain.",
            "adaptive_schedule": "A duration-weighted overlay is used in this stage-1 replay; daily controller write-back is not claimed.",
        },
    }


def apply_action_overlay_to_graph(
    graph: Mapping[str, Any],
    action: Action,
    *,
    scenario_id: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    data = copy.deepcopy(dict(graph))
    ledger = action_to_overlay_ledger(action, data, scenario_id)
    scenario = _choose_scenario(data, scenario_id)
    patch = ledger["scenario_patch"]
    scenario["safety_stock_days"] = round(patch["safety_stock_days"], 6)
    scenario["fg_target_days"] = round(patch["fg_target_days"], 6)
    scenario["production_gap_gain"] = round(patch["production_gap_gain"], 6)
    scenario["production_smoothing"] = round(patch["production_smoothing"], 6)
    econ = scenario.get("economic_policy")
    if not isinstance(econ, dict):
        econ = {}
    econ["external_procurement_daily_cap_days"] = round(patch["external_procurement_daily_cap_days"], 6)
    econ["external_procurement_lead_days"] = int(round(patch["external_procurement_lead_days"]))
    econ["external_procurement_cost_multiplier"] = round(patch["external_procurement_cost_multiplier"], 6)
    scenario["economic_policy"] = econ

    capacity_scale = safe_float(ledger["graph_scales"]["factory_capacity"], 1.0)
    inventory_scale = safe_float(ledger["graph_scales"]["opening_inventory"], 1.0)
    lead_scale = safe_float(ledger["graph_scales"]["transport_lead_time"], 1.0)
    process_count = 0
    inventory_state_count = 0
    edge_count = 0
    for node in data.get("nodes") or []:
        for process in node.get("processes") or []:
            capacity = process.get("capacity")
            if isinstance(capacity, dict) and "max_rate" in capacity:
                capacity["max_rate"] = round(max(0.0, safe_float(capacity.get("max_rate")) * capacity_scale), 6)
                capacity["scan_control_source"] = action.name
                process_count += 1
        inventory = node.get("inventory")
        if isinstance(inventory, dict):
            for state in inventory.get("states") or []:
                if "initial" in state:
                    state["initial"] = round(max(0.0, safe_float(state.get("initial")) * inventory_scale), 6)
                    inventory_state_count += 1
    for edge in data.get("edges") or []:
        lead = edge.get("lead_time")
        if not isinstance(lead, dict):
            continue
        changed = False
        for key in ("mean", "min", "max"):
            if key in lead:
                lead[key] = round(max(0.05, safe_float(lead.get(key)) * lead_scale), 6)
                changed = True
        if changed:
            lead["scan_control_source"] = action.name
            edge_count += 1

    metadata = data.get("metadata")
    if not isinstance(metadata, dict):
        metadata = {}
    metadata["scan_control_overlay"] = {
        "schema_version": "scan.canonical_overlay.v1",
        "policy": action.name,
        "ledger": ledger,
        "applied_counts": {
            "process_capacities": process_count,
            "inventory_states": inventory_state_count,
            "edge_lead_times": edge_count,
        },
    }
    data["metadata"] = metadata
    ledger["applied_counts"] = metadata["scan_control_overlay"]["applied_counts"]
    return data, ledger


def _first_existing(paths: Sequence[Path]) -> Path | None:
    return next((path for path in paths if path.exists() and path.stat().st_size > 0), None)


def _read_result_csv(result_dir: Path, name: str) -> pd.DataFrame:
    path = _first_existing(
        [result_dir / "data" / name, result_dir / name]
    )
    if path is None:
        return pd.DataFrame()
    try:
        return pd.read_csv(path)
    except (OSError, pd.errors.ParserError, UnicodeDecodeError):
        return pd.DataFrame()


def _numeric_column(
    frame: pd.DataFrame,
    names: Sequence[str],
    default: float = 0.0,
) -> pd.Series:
    for name in names:
        if name in frame:
            return pd.to_numeric(frame[name], errors="coerce").fillna(default)
    return pd.Series(default, index=frame.index, dtype=float)


def _normalized_churn(frame: pd.DataFrame, value_column: str, scale: float) -> float:
    if frame.empty or "day" not in frame or value_column not in frame:
        return 0.0
    values = (
        pd.to_numeric(frame[value_column], errors="coerce")
        .fillna(0.0)
        .groupby(pd.to_numeric(frame["day"], errors="coerce").fillna(-1).astype(int))
        .sum()
        .sort_index()
    )
    return float(values.diff().abs().sum() / max(scale, 1e-9))


def _supplier_risk_areas(result_dir: Path) -> dict[str, float]:
    """Summarize applied physical supplier risk separately from response RCI.

    The canonical applied-event file can contain repeated observations of the
    same lane/day, so exact event/scope duplicates are removed first.  The
    dimensionless severity proxy averages bounded availability/capacity/quality
    losses, lead deterioration and write-off.  Event identifiers prefixed with
    ``state_`` identify engine-generated (endogenous-state) events; all other
    identifiers are the exogenous replay envelope.
    """

    events = _read_result_csv(
        result_dir,
        "supplier_risk_events_applied_daily.csv",
    )
    if events.empty:
        return {
            "supplier_risk_area": 0.0,
            "exogenous_supplier_risk_area": 0.0,
            "endogenous_state_supplier_risk_area": 0.0,
        }
    identity_columns = [
        name
        for name in (
            "day",
            "supplier_id",
            "dst_node_id",
            "item_id",
            "edge_id",
            "event_ids",
        )
        if name in events
    ]
    if identity_columns:
        events = events.drop_duplicates(identity_columns)

    losses = pd.DataFrame(index=events.index)
    for name in (
        "stock_multiplier",
        "capacity_multiplier",
        "availability_multiplier",
        "reliability_multiplier",
        "quality_yield_multiplier",
    ):
        losses[name] = (
            1.0 - _numeric_column(events, [name], 1.0)
        ).clip(0.0, 1.0)
    losses["lead_multiplier"] = (
        _numeric_column(events, ["lead_time_multiplier"], 1.0) - 1.0
    ).clip(0.0, 1.0)
    losses["lead_extra"] = (
        (
            _numeric_column(events, ["lead_time_extra_days"])
            + _numeric_column(events, ["quality_delay_days"])
        )
        / 30.0
    ).clip(0.0, 1.0)
    losses["writeoff"] = _numeric_column(
        events,
        ["stock_writeoff_fraction"],
    ).clip(0.0, 1.0)
    severity = losses.mean(axis=1).fillna(0.0)
    event_ids = events.get(
        "event_ids",
        pd.Series("", index=events.index, dtype=str),
    ).astype(str)
    split_ids = event_ids.str.split(",").apply(
        lambda values: [value.strip() for value in values if value.strip()]
    )
    state_share = split_ids.apply(
        lambda values: (
            sum(value.startswith("state_") for value in values) / len(values)
            if values
            else 0.0
        )
    )
    exogenous_share = 1.0 - state_share
    return {
        "supplier_risk_area": float(severity.sum()),
        "exogenous_supplier_risk_area": float(
            (severity * exogenous_share).sum()
        ),
        "endogenous_state_supplier_risk_area": float(
            (severity * state_share).sum()
        ),
    }


def extract_canonical_kpis(
    result_dir: Path,
) -> dict[str, float | str]:
    daily_path = _first_existing([
        result_dir / "data" / "first_simulation_daily.csv",
        result_dir / "first_simulation_daily.csv",
    ])
    if daily_path is None:
        return {}
    daily = pd.read_csv(daily_path)
    demand = _numeric_column(daily, ["demand", "demand_qty"])
    served = _numeric_column(daily, ["served", "served_qty"])
    backlog = _numeric_column(daily, ["backlog_end", "backlog"])
    inventory = _numeric_column(daily, ["inventory_total", "inventory"])
    total_cost = _numeric_column(
        daily,
        ["total_economic_exposure_day", "total_supply_cost_day"],
    )
    scale = max(float(demand.replace(0.0, np.nan).median()), 1.0)
    daily_service = (
        served / demand.replace(0.0, np.nan)
    ).replace([np.inf, -np.inf], np.nan).fillna(1.0).clip(0.0, 1.0)
    service = clamp(
        float(served.sum() / max(demand.sum(), 1e-9)),
        0.0,
        1.0,
    )

    mrp_orders = _read_result_csv(result_dir, "mrp_orders_daily.csv")
    if not mrp_orders.empty and "order_type" in mrp_orders:
        mrp_orders = mrp_orders.loc[
            ~mrp_orders["order_type"].astype(str).str.startswith("opening_")
        ].copy()
    order_nervousness = _normalized_churn(
        mrp_orders,
        "release_qty",
        scale,
    )
    if order_nervousness <= 0.0:
        fallback_orders = (
            _numeric_column(daily, ["estimated_source_ordered_qty"])
            + _numeric_column(daily, ["external_procured_ordered_qty"])
        )
        order_nervousness = float(fallback_orders.diff().abs().sum() / scale)

    production = _read_result_csv(
        result_dir,
        "production_output_products_daily.csv",
    )
    production_nervousness = _normalized_churn(
        production,
        "produced_qty",
        scale,
    )
    constraints = _read_result_csv(
        result_dir,
        "production_constraint_daily.csv",
    )
    production_violations = int(
        (_numeric_column(constraints, ["shortfall_vs_desired_qty"]) > 1e-9).sum()
    )
    supplier_capacity_violations = int(
        (_numeric_column(daily, ["supplier_capacity_binding_qty"]) > 1e-9).sum()
    )
    shipments = _read_result_csv(
        result_dir,
        "production_supplier_shipments_daily.csv",
    )
    quality_loss_qty = float(
        (
            _numeric_column(shipments, ["pulled_qty"])
            - _numeric_column(shipments, ["shipped_qty"])
        ).clip(lower=0.0).sum()
    )
    action_ledger = _read_result_csv(result_dir, "canonical_action_ledger.csv")
    expedited_qty = 0.0
    if (
        not action_ledger.empty
        and "action" in action_ledger
        and "effective" in action_ledger
    ):
        expedite_rows = action_ledger.loc[
            action_ledger["action"].astype(str).eq("expedite_level")
        ].copy()
        expedite_rows["effective_expedite_level"] = pd.to_numeric(
            expedite_rows["effective"],
            errors="coerce",
        ).fillna(0.0)
        executed_volume = _numeric_column(
            expedite_rows,
            ["executed_control_volume_qty"],
        )
        # Scheduled controls are not physical expediting.  Only stages with an
        # executed flow contribute, while neutral expedite values remain zero.
        expedite_rows = expedite_rows.loc[executed_volume > 1e-9].copy()
        expedite_rows["executed_control_volume_qty"] = executed_volume.loc[
            expedite_rows.index
        ]
        expedited_qty = float(
            (
                expedite_rows["effective_expedite_level"]
                * expedite_rows["executed_control_volume_qty"]
            ).sum()
        )
        if "day" in expedite_rows:
            expedite_area = float(
                expedite_rows.groupby(
                    pd.to_numeric(
                        expedite_rows["day"],
                        errors="coerce",
                    ).fillna(-1).astype(int)
                )["effective_expedite_level"].max().sum()
            )
        else:
            expedite_area = float(
                expedite_rows["effective_expedite_level"].sum()
            )
    else:
        # Compatibility with early overlay ledgers, which cannot distinguish
        # scheduled from executed expediting.
        expedite_area = float(
            _numeric_column(
                action_ledger,
                ["effective_expedite_level", "expedite_level"],
            ).sum()
        )
        expedited_qty = 0.0 if action_ledger.empty else float("nan")
    external_procurement = float(
        _numeric_column(daily, ["external_procured_ordered_qty"]).sum()
    )
    tail_count = max(1, int(math.ceil(len(inventory) * 0.20)))
    post_crisis_overstock = float(
        inventory.tail(tail_count).mean() / scale
    )
    backlog_disruption = bool((backlog > 1e-9).any())
    service_disruption = bool((daily_service < 0.99).any())
    if not backlog_disruption and not service_disruption:
        recovery_time = math.nan
        recovery_time_lower_bound = math.nan
        recovery_followup = math.nan
        recovery_observed = math.nan
        recovery_status = "not_applicable_no_disruption"
        recovery_episode_detected = 0.0
        recovery_episode_basis = "none"
    else:
        peak_index = (
            int(backlog.to_numpy(dtype=float).argmax())
            if backlog_disruption
            else int(daily_service.to_numpy(dtype=float).argmin())
        )
        recovery_episode_basis = (
            "backlog_peak" if backlog_disruption else "service_minimum"
        )
        recovery_episode_detected = 1.0
        recovery_followup = float(max(0, len(backlog) - peak_index - 1))
        recovery_time = math.nan
        recovery_time_lower_bound = recovery_followup
        recovery_observed = 0.0
        recovery_status = "right_censored"
        for index in range(
            peak_index,
            max(peak_index, len(backlog) - 6),
        ):
            stop = index + 7
            if (
                (backlog.iloc[index:stop] <= 1e-9).all()
                and (daily_service.iloc[index:stop] >= 0.99).all()
            ):
                recovery_time = float(index - peak_index)
                recovery_time_lower_bound = recovery_time
                recovery_observed = 1.0
                recovery_status = "observed"
                break
    supplier_risk = _supplier_risk_areas(result_dir)
    return {
        "service": float(service),
        "mean_service": float(daily_service.mean()),
        "min_service": float(daily_service.min()),
        "service_loss": float(1.0 - service),
        "backlog_area_days": float(backlog.sum() / scale),
        "max_backlog_days": float(backlog.max() / scale),
        "recovery_time_days": recovery_time,
        "recovery_time_lower_bound_days": recovery_time_lower_bound,
        "recovery_followup_days": recovery_followup,
        "recovery_observed": recovery_observed,
        "recovery_status": recovery_status,
        "recovery_episode_detected": recovery_episode_detected,
        "recovery_episode_basis": recovery_episode_basis,
        "mean_inventory_days": float(inventory.mean() / scale),
        "post_crisis_overstock_days": post_crisis_overstock,
        "order_nervousness": order_nervousness,
        "production_nervousness": production_nervousness,
        "expedite_area": expedite_area,
        "expedited_qty": expedited_qty,
        "external_procurement_qty": external_procurement,
        "quality_loss_qty": quality_loss_qty,
        "constraint_violations": float(
            production_violations + supplier_capacity_violations
        ),
        "total_economic_exposure": float(total_cost.sum()),
        **supplier_risk,
    }


def _attach_canonical_rci(runs: pd.DataFrame) -> pd.DataFrame:
    """Attach the canonical response-created-risk proxy relative to MRP.

    This weighted six-component engine proxy is explicitly distinct from the
    reduced-order ``model_rci`` used in the business-review pack. No threshold,
    rank, or validation result is transferable between them without a separate
    alignment study. Components are kept separately to expose the convention.
    """

    result = runs.copy()
    result["rci_order_nervousness_component"] = 0.0
    result["rci_production_nervousness_component"] = 0.0
    result["rci_capacity_violation_component"] = 0.0
    result["rci_expedite_component"] = 0.0
    result["rci_external_procurement_component"] = 0.0
    result["rci_overstock_component"] = 0.0
    result["canonical_risk_creation_proxy"] = 0.0
    result["canonical_risk_creation_proxy_scope"] = (
        "canonical_multi_product_engine_replay"
    )
    result["canonical_risk_creation_proxy_definition_version"] = (
        "scan.canonical_weighted_six_component_rci.v1"
    )
    result["canonical_risk_creation_proxy_business_validation"] = (
        "not_covered_by_reduced_model_business_review"
    )
    # Backward-compatible alias. New consumers should use the scoped name.
    result["risk_creation_index"] = 0.0
    if result.empty or "status" not in result:
        return result
    successful = result.loc[result["status"] == "ok"]
    if successful.empty:
        return result
    reference = successful.loc[
        successful["policy"] == "mrp_reference"
    ].set_index("seed")
    component_specs = {
        "rci_order_nervousness_component": ("order_nervousness", 0.24),
        "rci_production_nervousness_component": (
            "production_nervousness",
            0.18,
        ),
        "rci_capacity_violation_component": (
            "constraint_violations",
            0.20,
        ),
        "rci_expedite_component": ("expedite_area", 0.14),
        "rci_external_procurement_component": (
            "external_procurement_qty",
            0.10,
        ),
        "rci_overstock_component": (
            "post_crisis_overstock_days",
            0.14,
        ),
    }
    for index, row in successful.iterrows():
        seed = int(row["seed"])
        if seed not in reference.index:
            continue
        base = reference.loc[seed]
        total = 0.0
        for component, (metric, weight) in component_specs.items():
            reference_value = float(base.get(metric, 0.0))
            value = float(row.get(metric, 0.0))
            normalized = max(
                0.0,
                value - reference_value,
            ) / max(abs(reference_value), 1.0)
            contribution = float(weight * normalized)
            result.at[index, component] = contribution
            total += contribution
        result.at[index, "canonical_risk_creation_proxy"] = total
        result.at[index, "risk_creation_index"] = total
    return result


def _append_canonical_oracle_rows(
    runs: pd.DataFrame,
    *,
    fixed_policy_names: Sequence[str],
) -> pd.DataFrame:
    """Append a transparent ex-post best-fixed row without another engine run."""

    if runs.empty:
        return runs
    successful = runs.loc[
        runs["status"].eq("ok")
        & runs["policy"].isin(set(fixed_policy_names))
    ].copy()
    if successful.empty:
        return runs

    def finite_value(
        row: pd.Series,
        name: str,
        default: float = math.inf,
    ) -> float:
        value = pd.to_numeric(
            pd.Series([row.get(name, default)]),
            errors="coerce",
        ).iloc[0]
        return float(value) if math.isfinite(float(value)) else default

    oracle_rows: list[dict[str, Any]] = []
    for seed, group in successful.groupby("seed", sort=True):
        ranked = sorted(
            (row for _, row in group.iterrows()),
            key=lambda row: (
                finite_value(row, "service_loss"),
                finite_value(row, "constraint_violations"),
                finite_value(row, "backlog_area_days"),
                -finite_value(row, "recovery_observed", 0.0),
                finite_value(row, "recovery_time_days"),
                finite_value(row, "canonical_risk_creation_proxy"),
                finite_value(row, "total_economic_exposure"),
                str(row.get("policy") or ""),
            ),
        )
        if not ranked:
            continue
        best = ranked[0].to_dict()
        source_policy = str(best["policy"])
        best.update(
            {
                "policy": "oracle",
                "seed": int(seed),
                "run_kind": "derived_oracle",
                "is_derived": 1,
                "oracle_fixed_policy": source_policy,
                "oracle_selection_basis": (
                    "lexicographic(service_loss,constraint_violations,"
                    "backlog_area_days,recovery_observed_desc,"
                    "recovery_time_days,canonical_risk_creation_proxy,"
                    "total_economic_exposure)"
                ),
                "derived_from_result_dir": str(
                    best.get("result_dir") or ""
                ),
            }
        )
        oracle_rows.append(best)
    if not oracle_rows:
        return runs
    return pd.concat(
        [runs, pd.DataFrame(oracle_rows)],
        ignore_index=True,
        sort=False,
    )


def _attach_mrp_reference_deltas(runs: pd.DataFrame) -> pd.DataFrame:
    """Attach auditable per-seed MRP values and exact paired differences."""

    result = runs.copy()
    if result.empty:
        return result
    for metric in CANONICAL_KPI_NAMES:
        if metric not in result:
            result[metric] = math.nan
    if "recovery_status" not in result:
        result["recovery_status"] = ""
    successful_reference = (
        result.loc[
            result["status"].eq("ok")
            & result["policy"].eq("mrp_reference")
        ]
        .drop_duplicates("seed", keep="last")
        .set_index("seed")
    )
    result["mrp_reference_recovery_status"] = result["seed"].map(
        successful_reference.get(
            "recovery_status",
            pd.Series(dtype=str),
        )
    )
    for metric in CANONICAL_KPI_NAMES:
        reference_column = f"mrp_reference_{metric}"
        delta_column = f"delta_vs_mrp_{metric}"
        reference_values = pd.to_numeric(
            successful_reference[metric],
            errors="coerce",
        )
        result[reference_column] = result["seed"].map(reference_values)
        result[delta_column] = (
            pd.to_numeric(result[metric], errors="coerce")
            - pd.to_numeric(result[reference_column], errors="coerce")
        )
        reference_self = (
            result["status"].eq("ok")
            & result["policy"].eq("mrp_reference")
        )
        # A reference compared with itself is exactly zero, including when its
        # recovery duration is right-censored and therefore not numerically
        # observed.
        result.loc[reference_self, delta_column] = 0.0

    exact_recovery_pair = (
        result["recovery_status"].astype(str).eq("observed")
        & result["mrp_reference_recovery_status"].astype(str).eq("observed")
    )
    reference_self = (
        result["status"].eq("ok")
        & result["policy"].eq("mrp_reference")
    )
    for metric in (
        "recovery_time_days",
        "recovery_time_lower_bound_days",
    ):
        delta_column = f"delta_vs_mrp_{metric}"
        result.loc[
            ~(exact_recovery_pair | reference_self),
            delta_column,
        ] = math.nan
    result["delta_vs_mrp_recovery_time_status"] = np.select(
        [
            reference_self,
            exact_recovery_pair,
            result["mrp_reference_recovery_status"].isna(),
        ],
        [
            "reference_self_exact_zero",
            "observed_pair",
            "missing_mrp_reference",
        ],
        default="not_comparable_censored",
    )
    return result


def _paired_canonical_summary(runs: pd.DataFrame) -> pd.DataFrame:
    successful = runs.loc[runs["status"] == "ok"].copy()
    if successful.empty or "mrp_reference" not in set(successful["policy"]):
        return pd.DataFrame()
    metric_names = list(CANONICAL_KPI_NAMES)
    metric_names = [name for name in metric_names if name in successful]
    reference_columns = [*metric_names]
    if "recovery_status" in successful:
        reference_columns.append("recovery_status")
    reference = successful.loc[
        successful["policy"] == "mrp_reference"
    ].set_index("seed")
    rows: list[dict[str, Any]] = []
    for policy, group in successful.groupby("policy", sort=False):
        aligned = group.set_index("seed").join(
            reference[reference_columns],
            rsuffix="_reference",
            how="inner",
        )
        if aligned.empty:
            continue
        row: dict[str, Any] = {"policy": policy, "paired_seed_count": int(len(aligned))}
        for metric in metric_names:
            current = pd.to_numeric(aligned[metric], errors="coerce")
            baseline = pd.to_numeric(
                aligned[f"{metric}_reference"],
                errors="coerce",
            )
            valid_pair = (
                current.notna()
                & baseline.notna()
                & np.isfinite(current)
                & np.isfinite(baseline)
            )
            if metric in {
                "recovery_time_days",
                "recovery_time_lower_bound_days",
            }:
                valid_pair &= (
                    aligned.get(
                        "recovery_status",
                        pd.Series("", index=aligned.index),
                    )
                    .astype(str)
                    .eq("observed")
                    & aligned.get(
                        "recovery_status_reference",
                        pd.Series("", index=aligned.index),
                    )
                    .astype(str)
                    .eq("observed")
                )
            delta = (current - baseline).loc[valid_pair]
            observed_count = int(len(delta))
            if policy == "mrp_reference":
                # Protect the acceptance invariant from floating serialization.
                delta = pd.Series(0.0, index=delta.index)
            mean = (
                0.0
                if policy == "mrp_reference"
                else float(delta.mean()) if observed_count else math.nan
            )
            row[f"mean_delta_{metric}"] = mean
            row[f"paired_observed_count_{metric}"] = observed_count
            row[f"median_delta_{metric}"] = (
                0.0
                if policy == "mrp_reference"
                else float(delta.median()) if observed_count else math.nan
            )
            row[f"p90_delta_{metric}"] = (
                0.0
                if policy == "mrp_reference"
                else float(delta.quantile(0.90)) if observed_count else math.nan
            )
            if policy == "mrp_reference":
                ci95_low = 0.0
                ci95_high = 0.0
                ci95_status = "exact_reference_zero"
            elif observed_count == 0:
                ci95_low = math.nan
                ci95_high = math.nan
                ci95_status = "not_estimable_no_observed_pairs"
            elif observed_count == 1:
                ci95_low = math.nan
                ci95_high = math.nan
                ci95_status = "not_estimable_single_pair"
            else:
                std = float(delta.std(ddof=1))
                half_width = 1.96 * std / math.sqrt(observed_count)
                ci95_low = mean - half_width
                ci95_high = mean + half_width
                ci95_status = "normal_approximation_95"
            row[f"ci95_low_delta_{metric}"] = ci95_low
            row[f"ci95_high_delta_{metric}"] = ci95_high
            row[f"ci95_status_delta_{metric}"] = ci95_status
            delta_std = (
                float(delta.std(ddof=1))
                if observed_count > 1
                else math.nan
            )
            if policy == "mrp_reference":
                standardized_effect = 0.0
                effect_status = "exact_zero"
            elif observed_count == 0:
                standardized_effect = math.nan
                effect_status = "not_estimable_no_observed_pairs"
            elif observed_count == 1:
                standardized_effect = math.nan
                effect_status = "not_estimable_single_pair"
            elif delta_std <= 1e-12:
                standardized_effect = math.nan
                effect_status = "not_estimable_zero_paired_variance"
            elif abs(mean) <= 1e-12:
                standardized_effect = 0.0
                effect_status = "exact_zero"
            else:
                standardized_effect = mean / delta_std
                effect_status = "paired_cohens_dz"
            row[f"standardized_effect_{metric}"] = standardized_effect
            row[f"standardized_effect_status_{metric}"] = effect_status
            lower_is_better = metric not in {
                "service",
                "mean_service",
                "min_service",
                "recovery_observed",
            }
            row[f"win_rate_{metric}"] = float(
                (delta < 0.0).mean()
                if lower_is_better
                else (delta > 0.0).mean()
            ) if observed_count else math.nan
        rows.append(row)
    summary = pd.DataFrame(rows)
    if "mean_delta_service_loss" in summary:
        summary = summary.sort_values("mean_delta_service_loss")
    return summary.reset_index(drop=True)


def prepare_canonical_overlay_package(
    *,
    graph_path: Path,
    decisions: pd.DataFrame,
    actions: Sequence[Action],
    output_root: Path,
    days: int,
    scenario_id: str = "scn:BASE",
    selected_policy_names: Sequence[str] | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Write legacy overlays and the new daily schedule without running the engine."""

    graph = json.loads(graph_path.read_text(encoding="utf-8"))
    schedule = expand_action_schedule(decisions, actions, days)
    adaptive_action = duration_weighted_action(schedule)
    by_name = {action.name: action for action in actions}
    names = list(selected_policy_names or [
        "mrp_reference",
        "reactive_buffer",
        "service_protection",
        "supplier_relief",
        "balanced_robust",
        "recovery_damping",
    ])
    policies = [by_name[name] for name in names if name in by_name]
    policies.append(adaptive_action)
    output_root.mkdir(parents=True, exist_ok=True)
    schedule.to_csv(output_root / "canonical_control_schedule.csv", index=False)
    # Compatibility alias for consumers of the original PR #40 package.
    schedule.to_csv(output_root / "adaptive_control_schedule.csv", index=False)
    pd.DataFrame(
        columns=[
            "day",
            "policy",
            "action_stage",
            "status",
            "node_id",
            "supplier_id",
            "item_id",
            "dst_node_id",
            "q_mrp_base_qty",
            "q_after_control_qty",
            "q_executable_qty",
            "binding_reason",
        ]
    ).to_csv(output_root / "canonical_action_ledger.csv", index=False)
    rows: list[dict[str, Any]] = []
    for action in policies:
        patched, ledger = apply_action_overlay_to_graph(graph, action, scenario_id=scenario_id)
        policy_root = output_root / action.name
        policy_root.mkdir(parents=True, exist_ok=True)
        (policy_root / "canonical_input_graph.json").write_text(
            json.dumps(patched, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        (policy_root / "control_overlay_ledger.json").write_text(
            json.dumps(ledger, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        policy_schedule = (
            schedule
            if action.name == adaptive_action.name
            else fixed_action_schedule(action, days)
        )
        policy_schedule.to_csv(
            policy_root / "canonical_control_schedule.csv",
            index=False,
        )
        rows.append({
            "policy": action.name,
            "integration_mode": "legacy_fixed_overlay_prepared",
            "daily_schedule_path": str(
                policy_root / "canonical_control_schedule.csv"
            ),
            **{f"action_{key}": value for key, value in asdict(action).items() if key != "description"},
            **{f"scenario_{key}": value for key, value in ledger["scenario_patch"].items()},
            **{f"scale_{key}": value for key, value in ledger["graph_scales"].items()},
        })
    overlays = pd.DataFrame(rows)
    overlays.to_csv(output_root / "canonical_control_overlays.csv", index=False)
    return schedule, overlays


def run_canonical_replays(
    *,
    repo_root: Path,
    graph_path: Path,
    decisions: pd.DataFrame,
    actions: Sequence[Action],
    seeds: Sequence[int],
    output_root: Path,
    days: int,
    scenario_id: str = "scn:BASE",
    engine_script: Path | None = None,
    python_executable: str | None = None,
    selected_policy_names: Sequence[str] | None = None,
    prediction_path: Path | None = None,
    physical_risk_envelope: pd.DataFrame | None = None,
    risk_top_pairs: int = 3,
    prediction_horizon_days: int = 30,
    enable_state_dependent_risks: bool = True,
    engine_extra_args: Sequence[str] = (),
    engine_profile_metadata: Mapping[str, Any] | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    graph = json.loads(graph_path.read_text(encoding="utf-8"))
    schedule = expand_action_schedule(decisions, actions, days)
    adaptive_action = duration_weighted_action(schedule, name="adaptive_daily")
    by_name = {action.name: action for action in actions}
    policies: list[Action] = []
    names = list(selected_policy_names or [
        "mrp_reference",
        "reactive_buffer",
        "service_protection",
        "supplier_relief",
        "balanced_robust",
        "recovery_damping",
    ])
    for name in names:
        if name in by_name and by_name[name] not in policies:
            policies.append(by_name[name])
    policies.append(adaptive_action)

    output_root.mkdir(parents=True, exist_ok=True)
    profile_metadata = dict(engine_profile_metadata or {
        "enabled": False,
        "source_path": "",
        "sha256": "",
        "argument_count": 0,
        "name": "graph_defaults",
    })
    schedule.to_csv(output_root / "canonical_control_schedule.csv", index=False)
    # Compatibility alias for the initial end-2026 package.
    schedule.to_csv(output_root / "adaptive_control_schedule.csv", index=False)
    risk_events, risk_mapping_ledger = build_canonical_risk_events(
        prediction_path, physical_risk_envelope,
        days=days, top_pairs=risk_top_pairs,
        prediction_horizon_days=prediction_horizon_days, conservative=True,
        canonical_graph=graph,
    )
    risk_csv_path: Path | None = None
    if not risk_events.empty:
        risk_csv_path = output_root / "canonical_supplier_risk_events.csv"
        risk_events.to_csv(risk_csv_path, index=False)
        risk_mapping_ledger.to_csv(output_root / "canonical_risk_mapping_ledger.csv", index=False)
    engine = engine_script or (repo_root / "etudecas" / "simulation" / "engine" / "run_first_simulation.py")
    interpreter = python_executable or sys.executable
    run_rows: list[dict[str, Any]] = []
    overlay_rows: list[dict[str, Any]] = []
    action_ledger_frames: list[pd.DataFrame] = []
    for action in policies:
        policy_root = output_root / action.name
        policy_root.mkdir(parents=True, exist_ok=True)
        input_path = policy_root / "canonical_input_graph.json"
        ledger_path = policy_root / "control_overlay_ledger.json"
        # Daily replay must not silently combine a graph overlay with a control
        # schedule. Every policy starts from the exact same canonical graph.
        input_path.write_text(json.dumps(graph, indent=2, ensure_ascii=False), encoding="utf-8")
        policy_schedule = (
            schedule
            if action.name == "adaptive_daily"
            else fixed_action_schedule(action, days)
        )
        schedule_path = policy_root / "canonical_control_schedule.csv"
        policy_schedule.to_csv(schedule_path, index=False)
        schedule_hash = _schedule_sha256(schedule_path)
        ledger = {
            "schema_version": "scan.canonical_daily_control.v1",
            "policy": action.name,
            "integration_mode": "daily_open_loop_schedule",
            "closed_loop_claimed": False,
            "graph_mutation_count": 0,
            "schedule_path": str(schedule_path),
            "schedule_sha256": schedule_hash,
            "schedule_rows": int(len(policy_schedule)),
            "scope": "portfolio_global_proxy",
            "engine_profile": profile_metadata,
            "action_mapping": {
                "order_gain": "order_multiplier",
                "safety_stock_gain": "safety_stock_multiplier",
                "production_gain": (
                    "production_target_multiplier and capacity_multiplier"
                ),
                "expedite": (
                    "expedite_level, external_procurement_multiplier and "
                    "lead_time_adjustment_days"
                ),
                "smoothing": (
                    "not mapped; canonical graph production_smoothing is retained"
                ),
                "supplier_relief": (
                    "no global priority mapping; a common priority multiplier "
                    "would cancel during lane-share normalization"
                ),
            },
            "limitations": [
                (
                    "The reduced controller is portfolio-level; supplier-item-site "
                    "specificity is retained in the physical risk-event ledger, not "
                    "invented in the action schedule."
                ),
                (
                    "Production smoothing and supplier-specific relief require "
                    "typed targeted controller outputs and are not claimed as "
                    "daily canonical actions in this open-loop replay."
                ),
            ],
        }
        ledger_path.write_text(json.dumps(ledger, indent=2, ensure_ascii=False), encoding="utf-8")
        overlay_rows.append({
            "policy": action.name,
            "integration_mode": "daily_open_loop_schedule",
            "schedule_path": str(schedule_path),
            "schedule_sha256": schedule_hash,
            "schedule_rows": int(len(policy_schedule)),
            "graph_mutation_count": 0,
            "engine_profile_name": str(
                profile_metadata.get("name") or "graph_defaults"
            ),
            "engine_profile_sha256": str(
                profile_metadata.get("sha256") or ""
            ),
            **{f"action_{key}": value for key, value in asdict(action).items() if key != "description"},
            "smoothing_daily_mapping": "unmapped_graph_value_retained",
            "global_priority_mapping": "neutral_avoids_share_cancellation",
        })
        for seed in seeds:
            result_dir = policy_root / f"seed_{int(seed)}"
            cmd = [
                interpreter,
                str(engine),
                "--input", str(input_path),
                "--output-dir", str(result_dir),
                "--scenario-id", scenario_id,
                "--days", str(int(days)),
                "--seed", str(int(seed)),
                "--output-profile", "compact",
                "--skip-map",
                "--skip-plots",
                "--no-lot-trace",
                "--skip-lot-audit",
            ]
            cmd.extend(str(item) for item in engine_extra_args)
            # The reference deliberately exercises the historical no-schedule
            # code path. Its schedule is still exported for audit, but not passed.
            if action.name != "mrp_reference":
                cmd.extend(["--control-schedule-csv", str(schedule_path)])
            cmd.append("--common-random-numbers")
            if enable_state_dependent_risks:
                cmd.append("--supplier-state-dependent-risks")
            if risk_csv_path is not None:
                cmd.extend(["--supplier-risk-events-csv", str(risk_csv_path)])
            try:
                proc = subprocess.run(cmd, cwd=repo_root, capture_output=True, text=True, check=False)
                if proc.returncode != 0:
                    error = (proc.stderr or proc.stdout)[-2000:]
                    print(
                        f"[ERROR] canonical replay {action.name} seed "
                        f"{int(seed)} failed (rc={int(proc.returncode)}): "
                        f"{error}",
                        file=sys.stderr,
                    )
                    run_rows.append({
                        "policy": action.name,
                        "seed": int(seed),
                        "status": "failed",
                        "returncode": int(proc.returncode),
                        "error": error,
                        "result_dir": str(result_dir),
                        "run_kind": "physical_replay",
                        "is_derived": 0,
                    })
                    continue
                validation_errors = _validate_canonical_result(
                    result_dir,
                    expect_schedule=action.name != "mrp_reference",
                    expected_schedule_sha256=(
                        schedule_hash
                        if action.name != "mrp_reference"
                        else ""
                    ),
                    expected_days=days,
                    expected_seed=int(seed),
                    expected_scenario_id=scenario_id,
                    expected_input_path=input_path,
                    expected_risk_events=risk_events,
                    expected_risk_csv_path=risk_csv_path,
                )
                if validation_errors:
                    error = "; ".join(validation_errors)
                    print(
                        f"[ERROR] canonical replay {action.name} seed "
                        f"{int(seed)} returned 0 but violated its output "
                        f"contract: {error}",
                        file=sys.stderr,
                    )
                    run_rows.append({
                        "policy": action.name,
                        "seed": int(seed),
                        "status": "invalid_output",
                        "returncode": 0,
                        "error": error,
                        "result_dir": str(result_dir),
                        "run_kind": "physical_replay",
                        "is_derived": 0,
                    })
                    continue
                kpis = extract_canonical_kpis(result_dir)
                action_ledger_path = (
                    result_dir / "data" / "canonical_action_ledger.csv"
                )
                if action_ledger_path.exists() and action_ledger_path.stat().st_size > 0:
                    action_ledger = pd.read_csv(action_ledger_path)
                    action_ledger.insert(0, "seed", int(seed))
                    action_ledger.insert(0, "policy_run", action.name)
                    action_ledger_frames.append(action_ledger)
                run_rows.append({
                    "policy": action.name,
                    "seed": int(seed),
                    "status": "ok",
                    "returncode": 0,
                    "error": "",
                    "result_dir": str(result_dir),
                    "run_kind": "physical_replay",
                    "is_derived": 0,
                    "integration_mode": (
                        "historical_no_schedule"
                        if action.name == "mrp_reference"
                        else "daily_open_loop_schedule"
                    ),
                    "engine_profile_name": str(
                        profile_metadata.get("name") or "graph_defaults"
                    ),
                    "engine_profile_sha256": str(
                        profile_metadata.get("sha256") or ""
                    ),
                    "schedule_path": (
                        "" if action.name == "mrp_reference" else str(schedule_path)
                    ),
                    "schedule_sha256": (
                        "" if action.name == "mrp_reference" else schedule_hash
                    ),
                    "action_ledger_path": (
                        str(action_ledger_path)
                        if action_ledger_path.exists()
                        else ""
                    ),
                    **kpis,
                })
            except OSError as exc:
                print(
                    f"[ERROR] canonical replay {action.name} seed "
                    f"{int(seed)} could not start: {exc}",
                    file=sys.stderr,
                )
                run_rows.append({
                    "policy": action.name,
                    "seed": int(seed),
                    "status": "failed",
                    "returncode": -1,
                    "error": str(exc),
                    "result_dir": str(result_dir),
                    "run_kind": "physical_replay",
                    "is_derived": 0,
                })
    runs = _attach_canonical_rci(pd.DataFrame(run_rows))
    runs = _append_canonical_oracle_rows(
        runs,
        fixed_policy_names=[
            action.name
            for action in policies
            if action.name != "adaptive_daily"
        ],
    )
    runs = _attach_mrp_reference_deltas(runs)
    overlays = pd.DataFrame(overlay_rows)
    summary = _paired_canonical_summary(runs)
    if action_ledger_frames:
        pd.concat(action_ledger_frames, ignore_index=True).to_csv(
            output_root / "canonical_action_ledger.csv",
            index=False,
        )
    else:
        ledger_path = output_root / "canonical_action_ledger.csv"
        # Always overwrite: a failed rerun must never leave a previous campaign's
        # successful aggregate ledger in place.
        pd.DataFrame(
            columns=[
                "day",
                "policy",
                "action_stage",
                "status",
                "node_id",
                "supplier_id",
                "item_id",
                "dst_node_id",
                "q_mrp_base_qty",
                "q_after_control_qty",
                "q_executable_qty",
                "executed_control_volume_qty",
                "binding_reason",
            ]
        ).to_csv(ledger_path, index=False)
    return runs, summary, overlays
