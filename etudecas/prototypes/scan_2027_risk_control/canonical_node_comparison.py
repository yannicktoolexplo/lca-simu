#!/usr/bin/env python3
"""Granular paired comparison of canonical MRP and closed-loop simulations.

The canonical closed-loop campaign intentionally reports network-level KPI.  This
module complements it without changing either physical run: it aligns the raw
engine tables by their physical grain (day, node, item and, where applicable,
transport lane), compares every numeric indicator available in both runs and
writes a self-contained interactive dashboard.

The source run directories are read-only inputs.  The output directory must be
new or empty so a comparison can never silently replace previous evidence.
"""

from __future__ import annotations

import argparse
import base64
from dataclasses import dataclass
from datetime import datetime, timezone
import gzip
import hashlib
import html
import json
import math
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import numpy as np
import pandas as pd


SCHEMA_VERSION = "scan.canonical_node_comparison.v1"
REFERENCE_POLICY = "mrp_reference"
FEEDBACK_POLICY = "canonical_feedback"
NUMERIC_TOLERANCE = 1e-9


@dataclass(frozen=True)
class FamilySpec:
    """Description of one engine table and its physical comparison grain."""

    name: str
    label: str
    filename: str
    keys: tuple[str, ...]
    include_record_count: bool = False
    summary_only: bool = False
    source_kind: str = "direct"


@dataclass(frozen=True)
class MetricInfo:
    """Comparison semantics inferred for one numeric engine indicator."""

    name: str
    label: str
    kind: str
    row_reducer: str
    horizon_reducer: str
    unit: str


@dataclass(frozen=True)
class NodeComparisonArtifacts:
    """Files and in-memory tables produced by a granular comparison."""

    output_dir: Path
    summary: pd.DataFrame
    coverage: pd.DataFrame
    column_coverage: pd.DataFrame
    missing_metrics: pd.DataFrame
    manifest_path: Path
    report_path: Path
    dashboard_path: Path
    overview_plot_path: Path | None
    top_effects_plot_path: Path | None


FAMILY_SPECS: tuple[FamilySpec, ...] = (
    FamilySpec(
        "network_daily",
        "Bilan global journalier",
        "first_simulation_daily.csv",
        ("day",),
    ),
    FamilySpec(
        "customer_service",
        "Demande, service et backlog client",
        "production_demand_service_daily.csv",
        ("day", "node_id", "item_id"),
    ),
    FamilySpec(
        "distribution_stock",
        "Stocks des centres de distribution",
        "production_dc_stocks_daily.csv",
        ("day", "node_id", "item_id"),
    ),
    FamilySpec(
        "plant_input_stock",
        "Stocks de composants en usine",
        "production_input_stocks_daily.csv",
        ("day", "node_id", "item_id"),
    ),
    FamilySpec(
        "plant_input_consumption",
        "Consommations de composants en usine",
        "production_input_consumption_daily.csv",
        ("day", "node_id", "item_id"),
    ),
    FamilySpec(
        "plant_input_shipments",
        "Expeditions de composants vers les usines",
        "production_input_replenishment_shipments_daily.csv",
        ("day", "node_id", "item_id"),
    ),
    FamilySpec(
        "plant_input_arrivals",
        "Arrivees de composants en usine",
        "production_input_replenishment_arrivals_daily.csv",
        ("day", "node_id", "item_id"),
    ),
    FamilySpec(
        "plant_output",
        "Production et stocks de produits finis",
        "production_output_products_daily.csv",
        ("day", "node_id", "item_id"),
    ),
    FamilySpec(
        "lot_events",
        "Mouvements physiques des lots",
        "production_lot_events.csv",
        ("day", "event_type", "node_id", "item_id"),
        include_record_count=True,
    ),
    FamilySpec(
        "lot_genealogy",
        "Transformations et genealogie des lots",
        "production_lot_genealogy.csv",
        (
            "day",
            "link_type",
            "parent_node_id",
            "parent_item_id",
            "child_node_id",
            "child_item_id",
        ),
        include_record_count=True,
    ),
    FamilySpec(
        "production_constraints",
        "Plan, production et contraintes",
        "production_constraint_daily.csv",
        ("day", "node_id", "item_id"),
        include_record_count=True,
    ),
    FamilySpec(
        "supplier_capacity",
        "Capacites et utilisation fournisseurs",
        "production_supplier_capacity_daily.csv",
        ("day", "node_id", "item_id"),
    ),
    FamilySpec(
        "supplier_stock_flows",
        "Stocks et flux entrants/sortants fournisseurs",
        "production_supplier_stock_flows_daily.csv",
        ("day", "node_id", "item_id"),
    ),
    FamilySpec(
        "supplier_shipments",
        "Expeditions et transport par liaison",
        "production_supplier_shipments_daily.csv",
        ("day", "src_node_id", "dst_node_id", "item_id"),
        include_record_count=True,
    ),
    FamilySpec(
        "mrp_orders",
        "Commandes MRP par liaison",
        "mrp_orders_daily.csv",
        (
            "day",
            "node_id",
            "src_node_id",
            "dst_node_id",
            "item_id",
            "edge_id",
            "order_type",
        ),
        include_record_count=True,
    ),
    FamilySpec(
        "mrp_state",
        "Etat et calcul MRP par noeud/article",
        "mrp_trace_daily.csv",
        ("day", "node_id", "item_id"),
    ),
    FamilySpec(
        "supplier_risk",
        "Risques fournisseurs appliques",
        "supplier_risk_events_applied_daily.csv",
        ("day", "supplier_id", "dst_node_id", "item_id", "edge_id"),
        include_record_count=True,
    ),
    FamilySpec(
        "factory_nervousness",
        "Synthese de nervosite des usines",
        "production_factory_nervousness.csv",
        ("node_id", "item_id"),
        summary_only=True,
    ),
    FamilySpec(
        "supplier_summary",
        "Synthese fournisseur/article",
        "supplier_nominal_parameters.csv",
        ("supplier_id", "dst_node_id", "item_id", "edge_id"),
        summary_only=True,
    ),
    FamilySpec(
        "initial_stock",
        "Etat initial observe",
        "initialization_observed_stock.csv",
        ("node_id", "item_id"),
        summary_only=True,
    ),
    FamilySpec(
        "initial_pipeline",
        "Pipeline initial",
        "initialization_pipeline.csv",
        (
            "node_id",
            "item_id",
            "category",
            "lane_src",
            "physical_delivery_day",
            "usable_day",
        ),
        include_record_count=True,
        summary_only=True,
    ),
)


KEY_ALIASES: Mapping[str, str] = {
    "output_item_id": "item_id",
}

IDENTIFIER_COLUMNS = {
    "campaign_id",
    "event_id",
    "event_ids",
    "lot_id",
    "related_lot_id",
    "parent_lot_id",
    "child_lot_id",
    "production_campaign_id",
    "source_id",
    "source_line",
}

NON_COMPARABLE_COLUMNS = {
    # Remaining quantity of an individual lot after one event.  Lot identifiers
    # are intentionally not paired across policies, so aggregating this field
    # would not describe a physical stock balance.
    "qty_after",
}

CONTEXT_COLUMNS = {
    "uom",
    "notes",
    "policy",
    "planning_status",
    "release_status",
    "receipt_status",
    "order_status_end_of_run",
    "capacity_limit_mode",
    "binding_cause",
    "binding_input_item_id",
    "lot_policy_mode",
    "risk_family",
    "risk_type",
    "effect",
    "lead_time_type",
    "lead_time_source",
    "capacity_basis",
    "business_reading",
    "nervousness_level",
    "nervousness_type",
}


def _normalise_columns(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy()
    for source, target in KEY_ALIASES.items():
        if source in result and target not in result:
            result = result.rename(columns={source: target})
    return result


def _data_path(run_dir: Path, filename: str) -> Path:
    candidates = (run_dir / "data" / filename, run_dir / filename)
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return candidates[0]


def _read_table(run_dir: Path, filename: str) -> tuple[pd.DataFrame, Path]:
    path = _data_path(run_dir, filename)
    if not path.is_file() or path.stat().st_size <= 0:
        return pd.DataFrame(), path
    return _normalise_columns(pd.read_csv(path)), path


def _human_label(name: str) -> str:
    labels = {
        "stock_end_of_day": "stock fin de journee",
        "stock_start_of_day": "stock debut de journee",
        "stock_before_production": "stock avant production",
        "incoming_qty": "entrees totales",
        "incoming_upstream_pipeline_qty": "entrees pipeline amont",
        "incoming_external_market_qty": "entrees marche externe",
        "incoming_estimated_source_qty": "entrees source estimee",
        "outgoing_pulled_qty": "sorties demandees",
        "outgoing_shipped_qty": "sorties expediees",
        "outgoing_unreliable_loss_qty": "pertes de fiabilite",
        "produced_qty": "production realisee",
        "desired_qty": "production souhaitee",
        "planned_qty_after_lot_rule": "production planifiee apres lots",
        "actual_qty": "production effective",
        "arrived_qty": "quantite arrivee",
        "shipped_to_node_qty": "quantite expediee vers l'usine",
        "release_qty": "quantite commandee",
        "planned_receipt_qty": "reception planifiee",
        "served_qty": "demande servie",
        "backlog_end_qty": "backlog fin de journee",
        "capacity_qty_per_day": "capacite journaliere",
        "used_qty": "capacite utilisee",
        "utilization": "taux d'utilisation",
        "transport_cost": "cout de transport",
        "lead_days": "delai de transport realise",
        "lead_time_extra_days": "delai supplementaire applique",
        "lead_time_multiplier": "multiplicateur de delai",
        "qty": "quantite du mouvement de lot",
        "parent_qty": "quantite du lot parent",
        "child_qty": "quantite du lot enfant",
        "allocation_share": "part du lot parent allouee",
        "bn_qty": "besoin net MRP",
        "controlled_bn_qty": "besoin net apres regulation",
        "recv_prev_today_qty": "reception planifiee du jour",
        "derived_consumed_qty": "consommation composant derivee",
        "record_count": "nombre d'enregistrements",
    }
    return labels.get(name, name.replace("_", " "))


def _infer_unit(name: str) -> str:
    lower = name.lower()
    if "cost" in lower or "exposure" in lower:
        return "monnaie"
    if "utilization" in lower or "reliability" in lower or "share" in lower:
        return "ratio"
    if "multiplier" in lower or lower.endswith("_scale"):
        return "multiplicateur"
    if "day" in lower or "lead" in lower or "horizon" in lower:
        return "jour"
    if "count" in lower or lower.endswith("_rows") or lower.endswith("_lots"):
        return "compte"
    if "qty" in lower or "stock" in lower or "inventory" in lower:
        return "quantite"
    return "valeur"


def _metric_info(name: str) -> MetricInfo:
    lower = name.lower()
    if name == "record_count" or "count" in lower or lower.endswith("_rows"):
        kind, row_reducer, horizon_reducer = "count", "sum", "sum"
    elif "cum_" in lower or "cumulative" in lower:
        kind, row_reducer, horizon_reducer = "cumulative", "max", "last"
    elif any(
        token in lower
        for token in (
            "multiplier",
            "utilization",
            "reliability",
            "yield",
            "ratio",
            "share",
            "probability",
            "fill_rate",
        )
    ):
        kind, row_reducer, horizon_reducer = "ratio", "mean", "mean"
    elif any(
        token in lower
        for token in (
            "stock",
            "inventory",
            "backlog_end",
            "available_before",
            "capacity_qty_per_day",
            "remaining_capacity",
            "target_",
            "position",
            "_floor_",
            "lead_days",
            "lead_reference",
            "lead_cover",
            "arrival_day",
            "release_day",
            "actual_receipt_day",
            "horizon_days",
        )
    ):
        kind, row_reducer, horizon_reducer = "state", "mean", "mean"
    elif any(
        token in lower
        for token in (
            "qty",
            "cost",
            "demand",
            "served",
            "shortfall",
            "writeoff",
            "loss",
            "incoming",
            "outgoing",
            "produced",
            "shipped",
            "pulled",
            "ordered",
            "receipt",
            "release",
            "lots",
        )
    ):
        kind, row_reducer, horizon_reducer = "flow", "sum", "sum"
    else:
        kind, row_reducer, horizon_reducer = "state", "mean", "mean"
    return MetricInfo(
        name=name,
        label=_human_label(name),
        kind=kind,
        row_reducer=row_reducer,
        horizon_reducer=horizon_reducer,
        unit=_infer_unit(name),
    )


def _numeric_metrics(
    reference: pd.DataFrame,
    feedback: pd.DataFrame,
    keys: Sequence[str],
) -> tuple[list[MetricInfo], list[dict[str, Any]]]:
    all_columns = list(dict.fromkeys([*reference.columns, *feedback.columns]))
    metrics: list[MetricInfo] = []
    coverage: list[dict[str, Any]] = []
    for name in all_columns:
        if name in keys:
            status = "comparison_key"
        elif name in IDENTIFIER_COLUMNS:
            status = "identifier"
        elif name in NON_COMPARABLE_COLUMNS:
            status = "not_comparable_without_lot_identity"
        elif name in CONTEXT_COLUMNS:
            status = "categorical_context"
        elif name not in reference:
            status = "missing_in_mrp"
        elif name not in feedback:
            status = "missing_in_v3"
        else:
            combined = pd.concat(
                [reference[name], feedback[name]], ignore_index=True
            )
            numeric = pd.to_numeric(combined, errors="coerce")
            source_non_null = int(combined.notna().sum())
            numeric_non_null = int(numeric.notna().sum())
            if source_non_null and numeric_non_null / source_non_null >= 0.98:
                metrics.append(_metric_info(name))
                status = "numeric_compared"
            elif not source_non_null:
                status = "empty_column"
            else:
                status = "categorical_context"
        coverage.append({"column": name, "status": status})
    return metrics, coverage


def _prepare_frame(
    frame: pd.DataFrame,
    spec: FamilySpec,
    metrics: Sequence[MetricInfo],
) -> pd.DataFrame:
    keys = list(spec.keys)
    missing_keys = [name for name in keys if name not in frame]
    if missing_keys:
        raise ValueError(
            f"{spec.filename} is missing comparison key(s): "
            + ", ".join(missing_keys)
        )
    work = frame.copy()
    for key in keys:
        if key == "day":
            work[key] = pd.to_numeric(work[key], errors="raise").astype(int)
        else:
            work[key] = work[key].fillna("").astype(str)
    if spec.include_record_count:
        work["record_count"] = 1.0
    numeric_block = pd.DataFrame(
        {
            metric.name: pd.to_numeric(work[metric.name], errors="coerce")
            for metric in metrics
        },
        index=work.index,
    )
    work = pd.concat(
        [work.drop(columns=[metric.name for metric in metrics]), numeric_block],
        axis=1,
    )
    reducers = {metric.name: metric.row_reducer for metric in metrics}
    if spec.include_record_count:
        reducers["record_count"] = "sum"
    if not reducers:
        return work[keys].drop_duplicates().reset_index(drop=True)
    return (
        work.groupby(keys, as_index=False, dropna=False, sort=True)
        .agg(reducers)
        .sort_values(keys)
        .reset_index(drop=True)
    )


def _entity_id(row: Mapping[str, Any], keys: Sequence[str]) -> str:
    parts = []
    for key in keys:
        if key == "day":
            continue
        value = row.get(key, "")
        if value is None or (isinstance(value, float) and math.isnan(value)):
            continue
        text = str(value)
        if text:
            parts.append(f"{key}={text}")
    return " | ".join(parts) if parts else "reseau_global"


def _finite_or_none(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _compare_family(
    reference_run: Path,
    feedback_run: Path,
    spec: FamilySpec,
    output_dir: Path,
) -> tuple[
    pd.DataFrame,
    pd.DataFrame,
    dict[str, Any],
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
]:
    reference, reference_path = _read_table(reference_run, spec.filename)
    feedback, feedback_path = _read_table(feedback_run, spec.filename)
    if reference.empty or feedback.empty:
        status = "missing_both" if reference.empty and feedback.empty else (
            "missing_mrp" if reference.empty else "missing_v3"
        )
        coverage = {
            "family": spec.name,
            "family_label": spec.label,
            "source_file": spec.filename,
            "source_kind": spec.source_kind,
            "status": status,
            "mrp_rows": int(len(reference)),
            "v3_rows": int(len(feedback)),
            "aligned_rows": 0,
            "metric_count": 0,
            "entity_count": 0,
            "changed_entity_count": 0,
            "mrp_only_rows": 0,
            "v3_only_rows": 0,
        }
        return pd.DataFrame(), pd.DataFrame(), coverage, [], [], []

    if spec.name == "plant_input_stock":
        required = {"stock_before_production", "stock_end_of_day"}
        if required.issubset(reference.columns) and required.issubset(
            feedback.columns
        ):
            for frame in (reference, feedback):
                frame["derived_consumed_qty"] = (
                    pd.to_numeric(
                        frame["stock_before_production"], errors="coerce"
                    )
                    - pd.to_numeric(frame["stock_end_of_day"], errors="coerce")
                )

    metrics, column_rows = _numeric_metrics(reference, feedback, spec.keys)
    if spec.include_record_count:
        metrics.append(_metric_info("record_count"))
        column_rows.append({"column": "record_count", "status": "derived_compared"})
    reference_grouped = _prepare_frame(reference, spec, metrics)
    feedback_grouped = _prepare_frame(feedback, spec, metrics)
    keys = list(spec.keys)
    aligned = reference_grouped.copy().merge(
        feedback_grouped,
        on=keys,
        how="outer",
        suffixes=("_mrp", "_v3"),
        indicator=True,
        validate="one_to_one",
    ).copy()
    aligned["entity_id"] = aligned.apply(
        lambda row: _entity_id(row, keys), axis=1
    )

    categorical_rows: list[dict[str, Any]] = []
    categorical_columns = [
        row["column"]
        for row in column_rows
        if row["status"] == "categorical_context"
        and row["column"] in reference
        and row["column"] in feedback
        and row["column"] not in {"notes", "source_file"}
    ]
    if categorical_columns:
        def categorical_frame(frame: pd.DataFrame) -> pd.DataFrame:
            work = frame[keys + categorical_columns].copy()
            for key in keys:
                if key == "day":
                    work[key] = pd.to_numeric(
                        work[key], errors="raise"
                    ).astype(int)
                else:
                    work[key] = work[key].fillna("").astype(str)
            for column in categorical_columns:
                work[column] = work[column].fillna("").astype(str)
            reducers = {
                column: (
                    lambda values: " | ".join(
                        sorted({value for value in values if str(value)})
                    )
                )
                for column in categorical_columns
            }
            return work.groupby(
                keys, as_index=False, dropna=False, sort=True
            ).agg(reducers)

        categorical = categorical_frame(reference).merge(
            categorical_frame(feedback),
            on=keys,
            how="outer",
            suffixes=("_mrp", "_v3"),
            validate="one_to_one",
        )
        categorical["entity_id"] = categorical.apply(
            lambda row: _entity_id(row, keys), axis=1
        )
        for column in categorical_columns:
            mrp_values = categorical[f"{column}_mrp"].fillna("").astype(str)
            v3_values = categorical[f"{column}_v3"].fillna("").astype(str)
            changed = mrp_values.ne(v3_values)
            for index in categorical.index[changed]:
                row = categorical.loc[index]
                categorical_rows.append(
                    {
                        "family": spec.name,
                        "family_label": spec.label,
                        "column": column,
                        "column_label": _human_label(column),
                        "day": int(row["day"]) if "day" in row else -1,
                        "entity_id": row["entity_id"],
                        "mrp_value": row.get(f"{column}_mrp", ""),
                        "v3_value": row.get(f"{column}_v3", ""),
                    }
                )
        for row in column_rows:
            if row["column"] in categorical_columns:
                row["status"] = "categorical_compared"

    summary_rows: list[dict[str, Any]] = []
    series_rows: list[dict[str, Any]] = []
    metric_names: list[str] = []
    derived_columns: dict[str, pd.Series | np.ndarray] = {}
    for metric in metrics:
        name = metric.name
        metric_names.append(name)
        mrp_col = f"{name}_mrp"
        v3_col = f"{name}_v3"
        if metric.kind in {"flow", "count"}:
            aligned[mrp_col] = aligned[mrp_col].fillna(0.0)
            aligned[v3_col] = aligned[v3_col].fillna(0.0)
        delta_values = aligned[v3_col] - aligned[mrp_col]
        derived_columns[f"{name}_delta"] = delta_values
        denominator = aligned[mrp_col].abs()
        derived_columns[f"{name}_delta_pct"] = np.where(
            denominator > NUMERIC_TOLERANCE,
            100.0 * delta_values / denominator,
            np.nan,
        )
    aligned = pd.concat(
        [aligned, pd.DataFrame(derived_columns, index=aligned.index)], axis=1
    )

    daily_dir = output_dir / "tables_by_family"
    daily_dir.mkdir(parents=True, exist_ok=True)
    family_path = daily_dir / f"{spec.name}_paired.csv"
    aligned.to_csv(family_path, index=False)

    entity_keys = [key for key in keys if key != "day"]
    group_columns = ["entity_id", *entity_keys]
    if not entity_keys:
        grouped_entities: Iterable[tuple[Any, pd.DataFrame]] = [
            (("reseau_global",), aligned)
        ]
    else:
        grouped_entities = aligned.groupby(
            group_columns, dropna=False, sort=True
        )
    for group_key, group in grouped_entities:
        if not isinstance(group_key, tuple):
            group_key = (group_key,)
        identity = dict(zip(group_columns, group_key))
        ordered = group.sort_values("day") if "day" in group else group
        day_values = (
            pd.to_numeric(ordered["day"], errors="coerce").fillna(-1).astype(int)
            if "day" in ordered
            else pd.Series([-1] * len(ordered), index=ordered.index)
        )
        for metric in metrics:
            name = metric.name
            mrp = pd.to_numeric(ordered[f"{name}_mrp"], errors="coerce")
            v3 = pd.to_numeric(ordered[f"{name}_v3"], errors="coerce")
            delta = v3 - mrp
            comparable = mrp.notna() & v3.notna()
            changed = comparable & (delta.abs() > NUMERIC_TOLERANCE)
            presence_changed = ordered["_merge"].ne("both")
            changed_any = changed | presence_changed

            def horizon_value(values: pd.Series) -> float:
                clean = values.dropna()
                if clean.empty:
                    return math.nan
                if metric.horizon_reducer == "sum":
                    return float(clean.sum())
                if metric.horizon_reducer == "last":
                    return float(clean.iloc[-1])
                if metric.horizon_reducer == "max":
                    return float(clean.max())
                return float(clean.mean())

            mrp_primary = horizon_value(mrp)
            v3_primary = horizon_value(v3)
            primary_delta = v3_primary - mrp_primary
            primary_pct = (
                100.0 * primary_delta / abs(mrp_primary)
                if math.isfinite(mrp_primary)
                and abs(mrp_primary) > NUMERIC_TOLERANCE
                else math.nan
            )
            changed_days = day_values.loc[changed_any]
            summary_rows.append(
                {
                    "family": spec.name,
                    "family_label": spec.label,
                    "metric": name,
                    "metric_label": metric.label,
                    "metric_kind": metric.kind,
                    "unit": metric.unit,
                    "horizon_aggregation": metric.horizon_reducer,
                    **identity,
                    "observed_row_count": int(len(ordered)),
                    "comparable_row_count": int(comparable.sum()),
                    "changed_day_count": int(changed_any.sum()),
                    "first_changed_day": (
                        int(changed_days.min()) if not changed_days.empty else math.nan
                    ),
                    "last_changed_day": (
                        int(changed_days.max()) if not changed_days.empty else math.nan
                    ),
                    "mrp_value": mrp_primary,
                    "v3_value": v3_primary,
                    "delta": primary_delta,
                    "delta_pct": primary_pct,
                    "mean_daily_delta": float(delta.mean()) if comparable.any() else math.nan,
                    "max_abs_daily_delta": (
                        float(delta.abs().max()) if comparable.any() else math.nan
                    ),
                    "mrp_min": float(mrp.min()) if mrp.notna().any() else math.nan,
                    "mrp_max": float(mrp.max()) if mrp.notna().any() else math.nan,
                    "v3_min": float(v3.min()) if v3.notna().any() else math.nan,
                    "v3_max": float(v3.max()) if v3.notna().any() else math.nan,
                    "has_difference": bool(changed_any.any()),
                    "paired_table": str(family_path),
                }
            )
            if not spec.summary_only:
                series_rows.append(
                    {
                        "family": spec.name,
                        "family_label": spec.label,
                        "entity_id": identity.get("entity_id", "reseau_global"),
                        "metric": name,
                        "metric_label": metric.label,
                        "unit": metric.unit,
                        "days": [int(value) for value in day_values.tolist()],
                        "mrp": [_finite_or_none(value) for value in mrp.tolist()],
                        "v3": [_finite_or_none(value) for value in v3.tolist()],
                    }
                )

    summary = pd.DataFrame(summary_rows)
    changed_entities = (
        summary.loc[summary["has_difference"], "entity_id"].nunique()
        if not summary.empty
        else 0
    )
    coverage = {
        "family": spec.name,
        "family_label": spec.label,
        "source_file": spec.filename,
        "source_kind": spec.source_kind,
        "status": "compared",
        "mrp_rows": int(len(reference)),
        "v3_rows": int(len(feedback)),
        "aligned_rows": int(len(aligned)),
        "metric_count": int(len(metrics)),
        "entity_count": int(aligned["entity_id"].nunique()),
        "changed_entity_count": int(changed_entities),
        "mrp_only_rows": int(aligned["_merge"].eq("left_only").sum()),
        "v3_only_rows": int(aligned["_merge"].eq("right_only").sum()),
        "mrp_path": str(reference_path),
        "v3_path": str(feedback_path),
        "paired_table": str(family_path),
    }
    for row in column_rows:
        row.update(
            {
                "family": spec.name,
                "source_file": spec.filename,
            }
        )
    return (
        aligned,
        summary,
        coverage,
        column_rows,
        series_rows,
        categorical_rows,
    )


def _scope_registry() -> pd.DataFrame:
    scopes = {
        "network_daily": (
            "indicateurs calcules directement par le moteur au niveau du reseau",
            "demande, service et backlog se reconcilient avec le detail client; "
            "les autres totaux ont un perimetre moteur propre",
        ),
        "customer_service": (
            "couples client ou centre de distribution - produit fini",
            "demande, quantite servie et backlog sont sommables vers le bilan global",
        ),
    }
    rows: list[dict[str, Any]] = []
    for spec in FAMILY_SPECS:
        scope, reconciliation = scopes.get(
            spec.name,
            (
                "perimetres locaux definis par le grain de la table moteur",
                "ne pas sommer vers un indicateur global sans equation de "
                "reconciliation explicite",
            ),
        )
        rows.append(
            {
                "family": spec.name,
                "family_label": spec.label,
                "source_file": spec.filename,
                "physical_grain": " x ".join(spec.keys),
                "scope_definition": scope,
                "global_reconciliation_rule": reconciliation,
            }
        )
    return pd.DataFrame(rows)


def _missing_metric_ledger(coverage: pd.DataFrame) -> pd.DataFrame:
    compared = set(
        coverage.loc[coverage["status"].eq("compared"), "family"].astype(str)
    )
    direct_consumption = "plant_input_consumption" in compared
    direct_shipments = "plant_input_shipments" in compared
    lot_trace = {"lot_events", "lot_genealogy"}.issubset(compared)
    return pd.DataFrame(
        [
            {
                "indicator": "consommation_composants_usine",
                "status": (
                    "direct_table_compared"
                    if direct_consumption
                    else "derived_available"
                ),
                "current_evidence": (
                    "export moteur direct compare"
                    if direct_consumption
                    else "derivee comme stock_before_production - stock_end_of_day"
                ),
                "limitation": (
                    "aucune pour la quantite quotidienne au grain usine/article"
                    if direct_consumption
                    else "la consommation n'est pas exportee dans un fichier moteur dedie"
                ),
                "next_step": (
                    "controler le bilan stock-consommation-arrivees"
                    if direct_consumption
                    else "relancer/exporter avec le profil complet"
                ),
            },
            {
                "indicator": "expeditions_reapprovisionnement_usine",
                "status": (
                    "direct_table_compared"
                    if direct_shipments
                    else "missing_direct_table"
                ),
                "current_evidence": (
                    "export moteur direct compare"
                    if direct_shipments
                    else "arrivees usine et expeditions fournisseur disponibles"
                ),
                "limitation": (
                    "aucune pour la quantite quotidienne au grain usine/article"
                    if direct_shipments
                    else "aucun production_input_replenishment_shipments_daily.csv"
                ),
                "next_step": (
                    "controler le decalage expeditions-arrivees"
                    if direct_shipments
                    else "relancer/exporter avec le profil complet"
                ),
            },
            {
                "indicator": "stock_physique_en_transit_journalier",
                "status": "partially_reconstructible",
                "current_evidence": (
                    "jour d'expedition, quantite, delai et jour d'arrivee disponibles"
                ),
                "limitation": "pas de table quotidienne directe du pipeline physique",
                "next_step": "exporter un etat de transit journalier par liaison/article",
            },
            {
                "indicator": "cout_complet_noeud_article_jour",
                "status": "partial",
                "current_evidence": (
                    "couts reseau journaliers et transport par liaison disponibles"
                ),
                "limitation": (
                    "achat, possession, production et risque non ventiles completement "
                    "par noeud/article/jour"
                ),
                "next_step": "ajouter une ventilation de cout au moteur",
            },
            {
                "indicator": "traces_lots_et_genealogie",
                "status": (
                    "aggregated_event_comparison_available"
                    if lot_trace
                    else "disabled_in_source_run"
                ),
                "current_evidence": (
                    "evenements et genealogie compares par jour, type, noeud et article"
                    if lot_trace
                    else "fichiers presents mais sans evenement exploitable"
                ),
                "limitation": (
                    "les identifiants de lots ne sont pas apparies entre politiques; "
                    "la comparaison porte sur les quantites et nombres d'evenements"
                    if lot_trace
                    else "campagne source executee sans lot trace ni lot audit"
                ),
                "next_step": (
                    "utiliser les viewers de lots de chaque bras pour une trace unitaire"
                    if lot_trace
                    else "relancer une paire en profil complet avec traces de lots"
                ),
            },
            {
                "indicator": "carte_comparative",
                "status": "standalone_dashboard_generated",
                "current_evidence": (
                    "coordonnees des noeuds et scores de changement integres au dashboard"
                ),
                "limitation": "pas encore ajoutee comme onglet de la carte historique",
                "next_step": (
                    "integrer ensuite le paquet valide via une option additive de la carte"
                ),
            },
        ]
    )


def _safe_records(frame: pd.DataFrame) -> list[dict[str, Any]]:
    if frame.empty:
        return []
    clean = frame.replace([np.inf, -np.inf], np.nan)
    return json.loads(clean.to_json(orient="records", force_ascii=False))


def _json_safe(value: Any) -> Any:
    if isinstance(value, np.generic):
        return _json_safe(value.item())
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, Mapping):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    return value


def _load_json_list(path: Path) -> list[dict[str, Any]]:
    if not path.is_file() or path.stat().st_size <= 0:
        return []
    payload = json.loads(path.read_text(encoding="utf-8"))
    return [dict(row) for row in payload] if isinstance(payload, list) else []


def _node_scores(
    summary: pd.DataFrame,
    nodes: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    scores: dict[str, list[float]] = {
        str(node.get("id") or ""): [] for node in nodes
    }
    if not summary.empty:
        changed = summary.loc[summary["has_difference"].astype(bool)]
        for _, row in changed.iterrows():
            pct = _finite_or_none(row.get("delta_pct"))
            if pct is not None:
                score = min(abs(pct), 500.0)
            else:
                delta = abs(float(row.get("max_abs_daily_delta") or 0.0))
                scale = max(
                    abs(float(row.get("mrp_value") or 0.0)),
                    abs(float(row.get("v3_value") or 0.0)),
                    1.0,
                )
                score = min(100.0 * delta / scale, 500.0)
            for column in (
                "node_id",
                "supplier_id",
                "src_node_id",
                "dst_node_id",
            ):
                value = row.get(column)
                if value is not None and str(value) in scores:
                    scores[str(value)].append(float(score))
    result: list[dict[str, Any]] = []
    for node in nodes:
        node_id = str(node.get("id") or "")
        values = scores.get(node_id, [])
        result.append(
            {
                **dict(node),
                "comparison_metric_count": len(values),
                "comparison_score": max(values) if values else 0.0,
                "comparison_mean_score": float(np.mean(values)) if values else 0.0,
            }
        )
    return result


def _effect_rank(frame: pd.DataFrame) -> pd.Series:
    pct = pd.to_numeric(frame.get("delta_pct"), errors="coerce").abs()
    delta = pd.to_numeric(
        frame.get("max_abs_daily_delta"), errors="coerce"
    ).abs()
    scale = pd.concat(
        [
            pd.to_numeric(frame.get("mrp_value"), errors="coerce").abs(),
            pd.to_numeric(frame.get("v3_value"), errors="coerce").abs(),
            pd.Series(1.0, index=frame.index),
        ],
        axis=1,
    ).max(axis=1)
    fallback = 100.0 * delta / scale
    return pct.fillna(fallback).replace([np.inf, -np.inf], np.nan).fillna(0.0)


def _headline_effects(summary: pd.DataFrame) -> pd.DataFrame:
    if summary.empty:
        return summary.copy()
    excluded_families = {
        "network_daily",
        "factory_nervousness",
        "supplier_summary",
        "mrp_state",
        "initial_stock",
        "initial_pipeline",
    }
    excluded_metric_pattern = (
        r"(?:^record_count$|date|(?:^|_)day$|min_day|max_day|horizon_days)"
    )
    candidates = summary.loc[
        summary["has_difference"].astype(bool)
        & ~summary["family"].isin(excluded_families)
        & ~summary["metric"].astype(str).str.contains(
            excluded_metric_pattern, case=False, regex=True
        )
    ].copy()
    candidates["effect_rank"] = _effect_rank(candidates)
    return candidates.sort_values(
        ["effect_rank", "max_abs_daily_delta"], ascending=False
    )


def _short_entity_label(value: Any, limit: int = 78) -> str:
    text = str(value)
    replacements = {
        "node_id=": "noeud=",
        "supplier_id=": "fourn.=",
        "src_node_id=": "src=",
        "dst_node_id=": "dst=",
        "item_id=item:": "article=",
        "edge_id=edge:": "liaison=",
        "order_type=": "type=",
    }
    for source, target in replacements.items():
        text = text.replace(source, target)
    return text if len(text) <= limit else text[: limit - 1] + "…"


def _write_plots(
    output_dir: Path,
    coverage: pd.DataFrame,
    summary: pd.DataFrame,
) -> tuple[Path | None, Path | None, dict[str, str]]:
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ModuleNotFoundError as exc:
        if exc.name and exc.name.startswith("matplotlib"):
            return None, None, {"status": "matplotlib_unavailable"}
        raise

    compared = coverage.loc[coverage["status"].eq("compared")].copy()
    overview_path = output_dir / "node_comparison_coverage.png"
    fig_height = max(5.0, 0.42 * len(compared) + 1.8)
    fig, axis = plt.subplots(figsize=(11.5, fig_height), constrained_layout=True)
    positions = np.arange(len(compared))
    totals = pd.to_numeric(compared["entity_count"], errors="coerce").fillna(0)
    changed = pd.to_numeric(
        compared["changed_entity_count"], errors="coerce"
    ).fillna(0)
    axis.barh(positions, totals, color="#d7dee8", label="entites comparees")
    axis.barh(positions, changed, color="#167d73", label="entites modifiees")
    axis.set_yticks(positions, compared["family_label"].tolist(), fontsize=8)
    axis.invert_yaxis()
    axis.set_xlabel("nombre de perimetres physiques")
    axis.set_title("Couverture de la comparaison MRP / V3 par famille")
    axis.grid(axis="x", alpha=0.2)
    axis.legend(frameon=False)
    for position, total, delta in zip(positions, totals, changed):
        axis.text(total + 0.2, position, f"{int(delta)}/{int(total)}", va="center", fontsize=8)
    fig.savefig(overview_path, dpi=170)
    plt.close(fig)

    top_path = output_dir / "node_comparison_top_effects.png"
    candidates = _headline_effects(summary).head(20)
    fig, axis = plt.subplots(figsize=(14.0, 9.5), constrained_layout=False)
    fig.subplots_adjust(left=0.49, right=0.98, top=0.92, bottom=0.09)
    if candidates.empty:
        axis.text(0.5, 0.5, "Aucun ecart detecte", ha="center", va="center")
        axis.set_axis_off()
    else:
        labels = [
            f"{row.metric_label} — {_short_entity_label(row.entity_id)}"
            for row in candidates.itertuples()
        ]
        values = candidates["effect_rank"].clip(upper=500.0)
        colors = [
            "#b9473f" if float(value) > 0 else "#167d73"
            for value in pd.to_numeric(candidates["delta"], errors="coerce").fillna(0)
        ]
        positions = np.arange(len(candidates))
        axis.barh(positions, values, color=colors, alpha=0.9)
        axis.set_yticks(positions, labels, fontsize=7)
        axis.invert_yaxis()
        axis.set_xlabel("ampleur relative de l'ecart (%) — plafonnee a 500 %")
        axis.set_title("Principaux ecarts locaux V3 par rapport au MRP")
        axis.grid(axis="x", alpha=0.2)
    fig.savefig(top_path, dpi=170)
    plt.close(fig)
    return overview_path, top_path, {"status": "written"}


def _dashboard_html(payload: Mapping[str, Any], title: str) -> str:
    payload_json = json.dumps(
        _json_safe(payload),
        ensure_ascii=False,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    compressed = base64.b64encode(gzip.compress(payload_json, compresslevel=9)).decode(
        "ascii"
    )
    safe_title = html.escape(title)
    return f"""<!doctype html>
<html lang="fr">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>{safe_title}</title>
  <style>
    :root {{ --ink:#17212b; --muted:#64748b; --line:#d7dee8; --mrp:#68768a; --v3:#167d73; --bad:#b9473f; --bg:#f4f7fa; }}
    * {{ box-sizing:border-box; }} body {{ margin:0; font-family:Inter,Segoe UI,Arial,sans-serif; color:var(--ink); background:var(--bg); }}
    header {{ padding:22px 28px; color:white; background:linear-gradient(115deg,#14324a,#167d73); }}
    header h1 {{ margin:0 0 6px; font-size:24px; }} header p {{ margin:0; opacity:.88; }}
    main {{ padding:20px; max-width:1800px; margin:auto; }}
    .cards {{ display:grid; grid-template-columns:repeat(5,minmax(150px,1fr)); gap:12px; margin-bottom:16px; }}
    .card,.panel {{ background:white; border:1px solid var(--line); border-radius:12px; box-shadow:0 2px 10px #17324a12; }}
    .card {{ padding:14px; }} .card b {{ display:block; font-size:24px; }} .card span {{ color:var(--muted); font-size:12px; }}
    .grid {{ display:grid; grid-template-columns:minmax(650px,1.5fr) minmax(420px,1fr); gap:16px; }}
    .panel {{ padding:16px; min-width:0; }} .panel h2 {{ margin:0 0 12px; font-size:17px; }}
    .filters {{ display:grid; grid-template-columns:1fr 1.4fr 1.2fr; gap:9px; margin-bottom:12px; }}
    label {{ color:var(--muted); font-size:11px; }} select {{ width:100%; margin-top:4px; padding:8px; border:1px solid var(--line); border-radius:7px; background:white; }}
    canvas {{ width:100%; height:480px; border:1px solid #e7ecf2; border-radius:8px; }}
    #map {{ width:100%; height:480px; border:1px solid #e7ecf2; border-radius:8px; background:#f8fbfd; }}
    .legend {{ display:flex; gap:18px; font-size:12px; color:var(--muted); margin:8px 0; }} .sw {{ display:inline-block; width:20px; height:3px; vertical-align:middle; margin-right:5px; }}
    .tableWrap {{ max-height:430px; overflow:auto; border:1px solid var(--line); border-radius:8px; }}
    table {{ width:100%; border-collapse:collapse; font-size:12px; }} th {{ position:sticky; top:0; background:#eef3f7; z-index:1; text-align:left; }} th,td {{ padding:7px 8px; border-bottom:1px solid #e8edf2; }} td.num {{ text-align:right; font-variant-numeric:tabular-nums; }}
    .wide {{ margin-top:16px; }} .pill {{ display:inline-block; padding:3px 7px; border-radius:999px; background:#e6f2ef; color:#12665e; font-size:11px; }}
    .warn {{ color:#9a3d36; }} .empty {{ color:var(--muted); padding:30px; text-align:center; }}
    @media(max-width:1050px) {{ .grid {{ grid-template-columns:1fr; }} .cards {{ grid-template-columns:repeat(2,1fr); }} }}
  </style>
</head>
<body>
<header><h1>{safe_title}</h1><p>Comparaison quotidienne par noeud, article et liaison — MRP de reference versus regulation dynamique V3</p></header>
<main>
  <div id="cards" class="cards"></div>
  <div class="grid">
    <section class="panel">
      <h2>Courbes locales</h2>
      <div class="filters">
        <label>Famille<select id="family"></select></label>
        <label>Noeud / article / liaison<select id="entity"></select></label>
        <label>Indicateur<select id="metric"></select></label>
      </div>
      <div class="legend"><span><i class="sw" style="background:var(--mrp)"></i>MRP</span><span><i class="sw" style="background:var(--v3)"></i>V3</span><span><i class="sw" style="background:var(--bad)"></i>V3 − MRP</span></div>
      <canvas id="chart" width="1200" height="560"></canvas>
      <div id="chartMeta" class="legend"></div>
    </section>
    <section class="panel">
      <h2>Carte des noeuds modifies</h2>
      <svg id="map" viewBox="0 0 900 480" role="img" aria-label="Carte comparative des noeuds"></svg>
      <div class="legend">Taille et couleur : ampleur maximale d'un ecart local. Cliquer un noeud pour ouvrir une courbe associee.</div>
    </section>
  </div>
  <section class="panel wide"><h2>Resume du perimetre selectionne</h2><div id="summary" class="tableWrap"></div></section>
  <div class="grid wide">
    <section class="panel"><h2>Couverture des donnees</h2><div id="coverage" class="tableWrap"></div></section>
    <section class="panel"><h2>Indicateurs encore incomplets</h2><div id="missing" class="tableWrap"></div></section>
  </div>
</main>
<script id="payload" type="application/octet-stream">{compressed}</script>
<script>
const fmt = value => value == null || !Number.isFinite(Number(value)) ? "—" : Number(value).toLocaleString("fr-FR", {{maximumFractionDigits:4}});
const esc = value => String(value ?? "").replace(/[&<>\"]/g, c => ({{"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}}[c]));
async function loadPayload() {{
  if (!("DecompressionStream" in window)) throw new Error("Navigateur trop ancien: DecompressionStream(gzip) requis.");
  const raw = atob(document.getElementById("payload").textContent.trim());
  const bytes = Uint8Array.from(raw, c => c.charCodeAt(0));
  const stream = new Blob([bytes]).stream().pipeThrough(new DecompressionStream("gzip"));
  return JSON.parse(await new Response(stream).text());
}}
function table(headers, rows) {{
  return `<table><thead><tr>${{headers.map(h=>`<th>${{esc(h)}}</th>`).join("")}}</tr></thead><tbody>${{rows.join("")}}</tbody></table>`;
}}
function drawChart(series) {{
  const canvas=document.getElementById("chart"), ctx=canvas.getContext("2d");
  const W=canvas.width,H=canvas.height,p={{l:72,r:25,t:25,b:52}}, split=390;
  ctx.clearRect(0,0,W,H); ctx.fillStyle="#fff"; ctx.fillRect(0,0,W,H);
  if(!series) {{ ctx.fillStyle="#64748b";ctx.font="18px sans-serif";ctx.fillText("Aucune serie",W/2-60,H/2);return; }}
  const days=series.days, all=[...series.mrp,...series.v3].filter(v=>v!=null&&Number.isFinite(v));
  const deltas=series.mrp.map((v,i)=>v==null||series.v3[i]==null?null:series.v3[i]-v).filter(v=>v!=null&&Number.isFinite(v));
  if(!all.length) return;
  const xmin=Math.min(...days),xmax=Math.max(...days), ymin=Math.min(...all),ymax=Math.max(...all), dmin=Math.min(0,...deltas),dmax=Math.max(0,...deltas);
  const pad=(ymax-ymin||1)*.06, lo=ymin-pad,hi=ymax+pad, dlo=dmin-(dmax-dmin||1)*.08,dhi=dmax+(dmax-dmin||1)*.08;
  const x=d=>p.l+(d-xmin)/Math.max(xmax-xmin,1)*(W-p.l-p.r), y=v=>p.t+(hi-v)/Math.max(hi-lo,1)*(split-p.t), yd=v=>split+38+(dhi-v)/Math.max(dhi-dlo,1)*(H-split-38-p.b);
  ctx.strokeStyle="#dbe3ea";ctx.lineWidth=1; for(let i=0;i<=5;i++){{let yy=p.t+i*(split-p.t)/5;ctx.beginPath();ctx.moveTo(p.l,yy);ctx.lineTo(W-p.r,yy);ctx.stroke();}}
  function line(vals,color,mapY){{ctx.strokeStyle=color;ctx.lineWidth=2;ctx.beginPath();let open=false;vals.forEach((v,i)=>{{if(v==null||!Number.isFinite(v)){{open=false;return;}}const xx=x(days[i]),yy=mapY(v);if(!open){{ctx.moveTo(xx,yy);open=true;}}else ctx.lineTo(xx,yy);}});ctx.stroke();}}
  line(series.mrp,"#68768a",y); line(series.v3,"#167d73",y); const delta=series.mrp.map((v,i)=>v==null||series.v3[i]==null?null:series.v3[i]-v); line(delta,"#b9473f",yd);
  ctx.strokeStyle="#667788";ctx.lineWidth=1;ctx.beginPath();ctx.moveTo(p.l,p.t);ctx.lineTo(p.l,split);ctx.lineTo(W-p.r,split);ctx.stroke();ctx.beginPath();ctx.moveTo(p.l,split+38);ctx.lineTo(p.l,H-p.b);ctx.lineTo(W-p.r,H-p.b);ctx.stroke();
  ctx.fillStyle="#425466";ctx.font="13px sans-serif";ctx.fillText(fmt(hi),8,p.t+5);ctx.fillText(fmt(lo),8,split);ctx.fillText(fmt(dhi),8,split+43);ctx.fillText(fmt(dlo),8,H-p.b);ctx.fillText(`jour ${{xmin}}`,p.l,H-18);ctx.fillText(`jour ${{xmax}}`,W-p.r-70,H-18);ctx.fillText("trajectoires",p.l+8,20);ctx.fillText("ecart V3 − MRP",p.l+8,split+28);
}}
function drawMap(payload, selectNode) {{
  const svg=document.getElementById("map"), NS="http://www.w3.org/2000/svg"; svg.innerHTML="";
  for(let lon=-150;lon<=150;lon+=30){{const l=document.createElementNS(NS,"line");const x=(lon+180)/360*900;l.setAttribute("x1",x);l.setAttribute("x2",x);l.setAttribute("y1",0);l.setAttribute("y2",480);l.setAttribute("stroke","#e2e8f0");svg.appendChild(l);}}
  for(let lat=-60;lat<=60;lat+=30){{const l=document.createElementNS(NS,"line");const y=(90-lat)/180*480;l.setAttribute("x1",0);l.setAttribute("x2",900);l.setAttribute("y1",y);l.setAttribute("y2",y);l.setAttribute("stroke","#e2e8f0");svg.appendChild(l);}}
  payload.nodes.filter(n=>Number.isFinite(Number(n.lat))&&Number.isFinite(Number(n.lon))).forEach(n=>{{
    const score=Number(n.comparison_score||0), c=document.createElementNS(NS,"circle"), x=(Number(n.lon)+180)/360*900, y=(90-Number(n.lat))/180*480;
    c.setAttribute("cx",x);c.setAttribute("cy",y);c.setAttribute("r",4+Math.min(13,Math.sqrt(score)));c.setAttribute("fill",score>25?"#b9473f":score>1?"#d88b39":score>0?"#167d73":"#94a3b8");c.setAttribute("fill-opacity",".78");c.setAttribute("stroke","#fff");c.setAttribute("stroke-width","1.4");c.style.cursor="pointer";
    const title=document.createElementNS(NS,"title");title.textContent=`${{n.id}} — ${{n.name||""}} — score ${{fmt(score)}}`;c.appendChild(title);c.addEventListener("click",()=>selectNode(String(n.id)));svg.appendChild(c);
  }});
}}
loadPayload().then(payload=>{{
  const families=[...new Map(payload.series.map(s=>[s.family,s.family_label])).entries()];
  const family=document.getElementById("family"),entity=document.getElementById("entity"),metric=document.getElementById("metric");
  family.innerHTML=families.map(([v,l])=>`<option value="${{esc(v)}}">${{esc(l)}}</option>`).join("");
  const changed=payload.summary.filter(r=>r.has_difference).length;
  document.getElementById("cards").innerHTML=[
    [payload.meta.node_count,"noeuds reseau"],[payload.meta.edge_count,"liaisons"],[payload.meta.metric_count,"indicateurs numeriques"],[payload.meta.series_count,"series locales"],[changed,"ecarts detectes"]
  ].map(([v,l])=>`<div class="card"><b>${{fmt(v)}}</b><span>${{esc(l)}}</span></div>`).join("");
  function refreshEntities(preferred=""){{const rows=payload.series.filter(s=>s.family===family.value);const vals=[...new Set(rows.map(s=>s.entity_id))];entity.innerHTML=vals.map(v=>`<option value="${{esc(v)}}">${{esc(v)}}</option>`).join("");if(vals.includes(preferred))entity.value=preferred;refreshMetrics();}}
  function refreshMetrics(preferred=""){{const rows=payload.series.filter(s=>s.family===family.value&&s.entity_id===entity.value);const vals=[...new Map(rows.map(s=>[s.metric,s.metric_label])).entries()];metric.innerHTML=vals.map(([v,l])=>`<option value="${{esc(v)}}">${{esc(l)}}</option>`).join("");if(vals.some(([v])=>v===preferred))metric.value=preferred;render();}}
  function render(){{const s=payload.series.find(x=>x.family===family.value&&x.entity_id===entity.value&&x.metric===metric.value);drawChart(s);document.getElementById("chartMeta").textContent=s?`${{s.family_label}} — ${{s.entity_id}} — ${{s.metric_label}} (${{s.unit}})`:"";const rows=payload.summary.filter(r=>r.family===family.value&&r.entity_id===entity.value).sort((a,b)=>Math.abs(Number(b.delta_pct||0))-Math.abs(Number(a.delta_pct||0)));document.getElementById("summary").innerHTML=table(["Indicateur","Agregation","MRP","V3","Ecart","Ecart %","Jours modifies"],rows.map(r=>`<tr><td>${{esc(r.metric_label)}}</td><td>${{esc(r.horizon_aggregation)}}</td><td class="num">${{fmt(r.mrp_value)}}</td><td class="num">${{fmt(r.v3_value)}}</td><td class="num">${{fmt(r.delta)}}</td><td class="num">${{fmt(r.delta_pct)}}</td><td class="num">${{fmt(r.changed_day_count)}}</td></tr>`));}}
  function selectNode(nodeId){{const hit=payload.series.find(s=>s.entity_id.includes(`=${{nodeId}}`)||s.entity_id.includes(`=${{nodeId}} |`));if(!hit)return;family.value=hit.family;refreshEntities(hit.entity_id);metric.value=hit.metric;render();}}
  family.addEventListener("change",()=>refreshEntities());entity.addEventListener("change",()=>refreshMetrics());metric.addEventListener("change",render);
  document.getElementById("coverage").innerHTML=table(["Famille","Statut","MRP","V3","Indicateurs","Entites modifiees"],payload.coverage.map(r=>`<tr><td>${{esc(r.family_label)}}</td><td><span class="pill">${{esc(r.status)}}</span></td><td class="num">${{fmt(r.mrp_rows)}}</td><td class="num">${{fmt(r.v3_rows)}}</td><td class="num">${{fmt(r.metric_count)}}</td><td class="num">${{fmt(r.changed_entity_count)}} / ${{fmt(r.entity_count)}}</td></tr>`));
  document.getElementById("missing").innerHTML=table(["Indicateur","Statut","Limite","Suite"],payload.missing.map(r=>`<tr><td>${{esc(r.indicator)}}</td><td class="warn">${{esc(r.status)}}</td><td>${{esc(r.limitation)}}</td><td>${{esc(r.next_step)}}</td></tr>`));
  drawMap(payload,selectNode);refreshEntities();
}}).catch(error=>{{document.querySelector("main").innerHTML=`<div class="panel warn"><b>Impossible de charger le dashboard.</b><br>${{esc(error.message)}}</div>`;}});
</script>
</body></html>"""


def _write_report(
    output_dir: Path,
    *,
    paired_results_dir: Path,
    seed: int,
    coverage: pd.DataFrame,
    summary: pd.DataFrame,
    column_coverage: pd.DataFrame,
    categorical_changes: pd.DataFrame,
    missing_metrics: pd.DataFrame,
    scope_registry: pd.DataFrame,
    dashboard_series_count: int,
) -> Path:
    report_path = output_dir / "canonical_node_comparison_report_fr.md"
    compared = coverage.loc[coverage["status"].eq("compared")]
    changed = summary.loc[summary["has_difference"].astype(bool)].copy()
    top = _headline_effects(summary).head(15)
    numeric_compared = int(
        column_coverage["status"].eq("numeric_compared").sum()
        + column_coverage["status"].eq("derived_compared").sum()
    )
    categorical_compared = int(
        column_coverage["status"].eq("categorical_compared").sum()
    )
    lines = [
        "# Comparaison multi-noeuds MRP / regulation dynamique V3",
        "",
        "## Portee",
        "",
        (
            f"La comparaison lit sans les modifier les deux simulations de la graine "
            f"`{seed}` sous `{paired_results_dir}`. Les tables sont alignees selon leur "
            "grain physique : jour, noeud, article et liaison lorsque celle-ci existe."
        ),
        "",
        (
            "Regle de lecture : les totaux globaux de production, stock et "
            "expedition n'ont pas tous le meme perimetre que les tables locales. "
            "Ils ne sont donc jamais presentes comme la somme naive des noeuds. "
            "Seuls demande, service et backlog disposent ici d'une reconciliation "
            "directe avec le detail client."
        ),
        "",
        f"- familles comparees : {len(compared)} ;",
        f"- indicateurs numeriques compares : {numeric_compared} ;",
        f"- colonnes categorielles comparees : {categorical_compared} ;",
        f"- courbes locales consultables : {dashboard_series_count} ;",
        f"- resumes indicateur/perimetre presentant au moins un ecart : {len(changed)} ;",
        f"- changements de categorie : {len(categorical_changes)}.",
        "",
        "## Couverture par famille",
        "",
        "| Famille | Lignes MRP | Lignes V3 | Indicateurs | Entites modifiees / comparees |",
        "|---|---:|---:|---:|---:|",
    ]
    for row in compared.itertuples():
        lines.append(
            f"| {row.family_label} | {row.mrp_rows} | {row.v3_rows} | "
            f"{row.metric_count} | {row.changed_entity_count} / {row.entity_count} |"
        )
    lines.extend(
        [
            "",
            "## Principaux ecarts locaux",
            "",
            "Les pourcentages sont fournis seulement lorsque la reference MRP est non nulle.",
            "",
            "| Famille | Perimetre | Indicateur | MRP | V3 | Ecart | Ecart % | Jours modifies |",
            "|---|---|---|---:|---:|---:|---:|---:|",
        ]
    )
    for row in top.itertuples():
        pct = "" if not math.isfinite(float(row.delta_pct)) else f"{row.delta_pct:.3f}"
        lines.append(
            f"| {row.family_label} | `{row.entity_id}` | {row.metric_label} | "
            f"{row.mrp_value:.6g} | {row.v3_value:.6g} | {row.delta:.6g} | "
            f"{pct} | {row.changed_day_count} |"
        )
    lines.extend(
        [
            "",
            "## Fichiers",
            "",
            "- [Dashboard interactif](canonical_node_comparison_dashboard.html)",
            "- [Resume de toutes les series](canonical_node_comparison_summary.csv)",
            "- [Couverture](canonical_node_comparison_coverage.csv)",
            "- [Couverture des colonnes](canonical_node_comparison_column_coverage.csv)",
            "- [Changements categoriques](canonical_node_comparison_categorical_changes.csv)",
            "- [Perimetre de chaque famille](canonical_node_comparison_scope_registry.csv)",
            "- [Indicateurs encore incomplets](canonical_node_comparison_missing_metrics.csv)",
            "- [Tables detaillees par famille](tables_by_family/)",
            "",
            "## Etat de couverture et limites restantes",
            "",
        ]
    )
    for row in missing_metrics.itertuples():
        lines.append(f"- **{row.indicator}** — {row.limitation} Suite : {row.next_step}.")
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report_path


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_pair_rows(
    paired_results_dir: Path,
    seed: int | None,
) -> tuple[int, Path, Path, dict[str, Any]]:
    runs_path = paired_results_dir / "canonical_closed_loop_runs.csv"
    if not runs_path.is_file():
        raise FileNotFoundError(
            f"Missing canonical paired run table: {runs_path}"
        )
    runs = pd.read_csv(runs_path)
    required = {"policy", "seed", "status", "result_dir"}
    missing = sorted(required - set(runs.columns))
    if missing:
        raise ValueError(
            "canonical_closed_loop_runs.csv is missing columns: "
            + ", ".join(missing)
        )
    runs = runs.loc[runs["status"].astype(str).eq("ok")].copy()
    runs["seed"] = pd.to_numeric(runs["seed"], errors="raise").astype(int)
    available: list[int] = []
    for candidate, group in runs.groupby("seed", sort=True):
        if {REFERENCE_POLICY, FEEDBACK_POLICY}.issubset(
            set(group["policy"].astype(str))
        ):
            available.append(int(candidate))
    if not available:
        raise ValueError("No successful paired MRP/V3 seed is available.")
    selected_seed = int(seed) if seed is not None else available[0]
    if selected_seed not in available:
        raise ValueError(
            f"Seed {selected_seed} is not a successful paired seed; available: "
            + ", ".join(map(str, available))
        )
    pair = runs.loc[runs["seed"].eq(selected_seed)]
    reference_row = pair.loc[pair["policy"].eq(REFERENCE_POLICY)].iloc[0]
    feedback_row = pair.loc[pair["policy"].eq(FEEDBACK_POLICY)].iloc[0]
    reference_dir = Path(str(reference_row["result_dir"])).resolve()
    feedback_dir = Path(str(feedback_row["result_dir"])).resolve()
    if not reference_dir.is_dir() or not feedback_dir.is_dir():
        raise FileNotFoundError(
            "One paired physical result directory does not exist: "
            f"MRP={reference_dir}; V3={feedback_dir}"
        )
    contract_columns = (
        "scenario_id",
        "days",
        "common_random_numbers",
        "state_dependent_risks",
        "graph_sha256",
        "engine_profile_sha256",
    )
    contract: dict[str, Any] = {"seed": selected_seed}
    for column in contract_columns:
        if column not in pair:
            continue
        reference_value = reference_row[column]
        feedback_value = feedback_row[column]
        if str(reference_value) != str(feedback_value):
            raise ValueError(
                f"Paired contract mismatch for {column}: "
                f"MRP={reference_value!r}, V3={feedback_value!r}"
            )
        contract[column] = reference_value
    nodes_reference = reference_dir / "run" / "nodes.json"
    nodes_feedback = feedback_dir / "run" / "nodes.json"
    flows_reference = reference_dir / "run" / "flows.json"
    flows_feedback = feedback_dir / "run" / "flows.json"
    for left, right, label in (
        (nodes_reference, nodes_feedback, "nodes"),
        (flows_reference, flows_feedback, "flows"),
    ):
        if not left.is_file() or not right.is_file():
            raise FileNotFoundError(f"Missing {label}.json in one paired run.")
        if json.loads(left.read_text(encoding="utf-8")) != json.loads(
            right.read_text(encoding="utf-8")
        ):
            raise ValueError(f"Paired topology mismatch in {label}.json")
    reference_summary = reference_dir / "summaries" / "first_simulation_summary.json"
    feedback_summary = feedback_dir / "summaries" / "first_simulation_summary.json"
    if reference_summary.is_file() and feedback_summary.is_file():
        reference_payload = json.loads(reference_summary.read_text(encoding="utf-8"))
        feedback_payload = json.loads(feedback_summary.read_text(encoding="utf-8"))
        reference_state = (
            reference_payload.get("policy", {})
            .get("warmup_boundary_audit", {})
            .get("core_state_sha256")
        )
        feedback_state = (
            feedback_payload.get("policy", {})
            .get("warmup_boundary_audit", {})
            .get("core_state_sha256")
        )
        if reference_state and feedback_state and reference_state != feedback_state:
            raise ValueError(
                "MRP and V3 do not start the measured horizon from the same "
                "physical warm-up state."
            )
        contract["same_physical_state_at_measurement_start"] = bool(
            reference_state and reference_state == feedback_state
        )
    return selected_seed, reference_dir, feedback_dir, contract


def build_canonical_node_comparison(
    *,
    paired_results_dir: Path,
    output_dir: Path,
    seed: int | None = None,
    make_plots: bool = True,
) -> NodeComparisonArtifacts:
    """Build an exhaustive available-data comparison in a separate directory."""

    paired_root = paired_results_dir.resolve()
    output = output_dir.resolve()
    if output.exists() and any(output.iterdir()):
        raise FileExistsError(
            f"Refusing to overwrite a non-empty comparison directory: {output}"
        )
    output.mkdir(parents=True, exist_ok=True)
    selected_seed, reference_dir, feedback_dir, contract = _load_pair_rows(
        paired_root, seed
    )

    summaries: list[pd.DataFrame] = []
    coverage_rows: list[dict[str, Any]] = []
    column_rows: list[dict[str, Any]] = []
    series_rows: list[dict[str, Any]] = []
    categorical_rows: list[dict[str, Any]] = []
    for spec in FAMILY_SPECS:
        (
            _aligned,
            summary,
            coverage,
            family_columns,
            family_series,
            family_categories,
        ) = _compare_family(reference_dir, feedback_dir, spec, output)
        if not summary.empty:
            summaries.append(summary)
        coverage_rows.append(coverage)
        column_rows.extend(family_columns)
        series_rows.extend(family_series)
        categorical_rows.extend(family_categories)

    summary = (
        pd.concat(summaries, ignore_index=True, sort=False)
        if summaries
        else pd.DataFrame()
    )
    coverage = pd.DataFrame(coverage_rows)
    column_coverage = pd.DataFrame(column_rows)
    categorical_changes = pd.DataFrame(
        categorical_rows,
        columns=(
            "family",
            "family_label",
            "column",
            "column_label",
            "day",
            "entity_id",
            "mrp_value",
            "v3_value",
        ),
    )
    missing_metrics = _missing_metric_ledger(coverage)
    scope_registry = _scope_registry()

    summary_path = output / "canonical_node_comparison_summary.csv"
    coverage_path = output / "canonical_node_comparison_coverage.csv"
    columns_path = output / "canonical_node_comparison_column_coverage.csv"
    categories_path = output / "canonical_node_comparison_categorical_changes.csv"
    missing_path = output / "canonical_node_comparison_missing_metrics.csv"
    scope_path = output / "canonical_node_comparison_scope_registry.csv"
    summary.to_csv(summary_path, index=False)
    coverage.to_csv(coverage_path, index=False)
    column_coverage.to_csv(columns_path, index=False)
    categorical_changes.to_csv(categories_path, index=False)
    missing_metrics.to_csv(missing_path, index=False)
    scope_registry.to_csv(scope_path, index=False)

    nodes = _load_json_list(reference_dir / "run" / "nodes.json")
    flows = _load_json_list(reference_dir / "run" / "flows.json")
    node_scores = _node_scores(summary, nodes)
    node_scores_path = output / "canonical_node_comparison_node_scores.csv"
    pd.DataFrame(node_scores).to_csv(node_scores_path, index=False)

    payload = {
        "schema_version": SCHEMA_VERSION,
        "meta": {
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "paired_results_dir": str(paired_root),
            "reference_run": str(reference_dir),
            "feedback_run": str(feedback_dir),
            "seed": selected_seed,
            "node_count": len(nodes),
            "edge_count": len(flows),
            "metric_count": int(
                summary[["family", "metric"]].drop_duplicates().shape[0]
            )
            if not summary.empty
            else 0,
            "series_count": len(series_rows),
            "pairing_contract": contract,
        },
        "nodes": node_scores,
        "flows": flows,
        "coverage": _safe_records(coverage),
        "summary": _safe_records(summary),
        "categorical_changes": _safe_records(categorical_changes),
        "scope_registry": _safe_records(scope_registry),
        "missing": _safe_records(missing_metrics),
        "series": series_rows,
    }
    dashboard_path = output / "canonical_node_comparison_dashboard.html"
    dashboard_path.write_text(
        _dashboard_html(payload, "RESILIENCE-SCAN — Comparaison multi-noeuds MRP / V3"),
        encoding="utf-8",
    )

    if make_plots:
        overview_path, top_path, plot_status = _write_plots(
            output, coverage, summary
        )
    else:
        overview_path, top_path = None, None
        plot_status = {"status": "disabled"}
    report_path = _write_report(
        output,
        paired_results_dir=paired_root,
        seed=selected_seed,
        coverage=coverage,
        summary=summary,
        column_coverage=column_coverage,
        categorical_changes=categorical_changes,
        missing_metrics=missing_metrics,
        scope_registry=scope_registry,
        dashboard_series_count=len(series_rows),
    )

    outputs: dict[str, str] = {
        "summary": str(summary_path),
        "coverage": str(coverage_path),
        "column_coverage": str(columns_path),
        "categorical_changes": str(categories_path),
        "scope_registry": str(scope_path),
        "missing_metrics": str(missing_path),
        "node_scores": str(node_scores_path),
        "dashboard": str(dashboard_path),
        "report": str(report_path),
        "tables_by_family": str(output / "tables_by_family"),
    }
    if overview_path is not None:
        outputs["coverage_plot"] = str(overview_path)
    if top_path is not None:
        outputs["top_effects_plot"] = str(top_path)
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "source": {
            "paired_results_dir": str(paired_root),
            "reference_run": str(reference_dir),
            "feedback_run": str(feedback_dir),
            "reference_nodes_sha256": _sha256(reference_dir / "run" / "nodes.json"),
            "feedback_nodes_sha256": _sha256(feedback_dir / "run" / "nodes.json"),
        },
        "pairing_contract": contract,
        "counts": {
            "family_count": int(len(coverage)),
            "compared_family_count": int(coverage["status"].eq("compared").sum()),
            "summary_row_count": int(len(summary)),
            "changed_summary_row_count": int(
                summary["has_difference"].astype(bool).sum()
            )
            if not summary.empty
            else 0,
            "categorical_change_count": int(len(categorical_changes)),
            "dashboard_series_count": int(len(series_rows)),
            "node_count": len(nodes),
            "edge_count": len(flows),
        },
        "plot_status": plot_status,
        "outputs": outputs,
    }
    manifest_path = output / "canonical_node_comparison_manifest.json"
    manifest_path.write_text(
        json.dumps(_json_safe(manifest), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return NodeComparisonArtifacts(
        output_dir=output,
        summary=summary,
        coverage=coverage,
        column_coverage=column_coverage,
        missing_metrics=missing_metrics,
        manifest_path=manifest_path,
        report_path=report_path,
        dashboard_path=dashboard_path,
        overview_plot_path=overview_path,
        top_effects_plot_path=top_path,
    )


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Compare a paired canonical MRP/V3 campaign at day, node, item "
            "and transport-lane level without modifying either source run."
        )
    )
    parser.add_argument("--paired-results-dir", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument(
        "--plot",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Write static overview figures in addition to the HTML dashboard.",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    artifacts = build_canonical_node_comparison(
        paired_results_dir=Path(args.paired_results_dir),
        output_dir=Path(args.output_dir),
        seed=args.seed,
        make_plots=bool(args.plot),
    )
    print(f"Granular MRP/V3 comparison completed: {artifacts.output_dir}")
    print(f"Dashboard: {artifacts.dashboard_path}")
    print(f"Compared summary rows: {len(artifacts.summary)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
