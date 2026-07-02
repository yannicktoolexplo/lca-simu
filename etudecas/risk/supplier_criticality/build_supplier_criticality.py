#!/usr/bin/env python3
"""Build supplier criticality KPI panels from etudecas simulation outputs.

The script intentionally uses only the Python standard library. The active local
environment used by some users may not have pandas installed, while the
simulation CSV outputs are regular enough to process with csv.DictReader.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from collections import defaultdict, deque
from pathlib import Path
from statistics import fmean, pstdev
from typing import Any


ROOT = Path(__file__).resolve().parent
ETUDECAS_ROOT = ROOT.parents[1]
DEFAULT_SIM_RESULT_DIR = (
    ETUDECAS_ROOT
    / "simulation"
    / "result"
    / "_codex_lot_trace_5y_risk_portfolio"
)
DEFAULT_SENSITIVITY_DIR = ETUDECAS_ROOT / "simulation" / "sensibility" / "active_supplier_parameter_result"
DEFAULT_OUTPUT_DIR = ROOT / "result"

DATA_DIRNAME = "data"
REPORTS_DIRNAME = "reports"
SUMMARIES_DIRNAME = "summaries"

EPSILON = 1e-9


PairKey = tuple[str, str, str]


def parse_float(value: Any, default: float = 0.0) -> float:
    if value is None:
        return default
    text = str(value).strip()
    if not text:
        return default
    try:
        return float(text.replace(",", "."))
    except ValueError:
        return default


def parse_int(value: Any, default: int = 0) -> int:
    return int(round(parse_float(value, float(default))))


def safe_div(numerator: float, denominator: float, default: float = 0.0) -> float:
    if abs(denominator) <= EPSILON:
        return default
    return numerator / denominator


def clamp(value: float, lower: float = 0.0, upper: float = 1.0) -> float:
    return max(lower, min(upper, value))


def sigmoid(value: float) -> float:
    if value >= 0:
        z = math.exp(-value)
        return 1.0 / (1.0 + z)
    z = math.exp(value)
    return z / (1.0 + z)


def quantile(values: list[float], q: float, default: float = 0.0) -> float:
    clean = sorted(v for v in values if math.isfinite(v))
    if not clean:
        return default
    if len(clean) == 1:
        return clean[0]
    pos = (len(clean) - 1) * clamp(q)
    lower = int(math.floor(pos))
    upper = int(math.ceil(pos))
    if lower == upper:
        return clean[lower]
    weight = pos - lower
    return clean[lower] * (1.0 - weight) + clean[upper] * weight


def mean(values: list[float], default: float = 0.0) -> float:
    clean = [v for v in values if math.isfinite(v)]
    if not clean:
        return default
    return float(fmean(clean))


def stdev(values: list[float], default: float = 0.0) -> float:
    clean = [v for v in values if math.isfinite(v)]
    if len(clean) < 2:
        return default
    return float(pstdev(clean))


def rolling_sum(values: deque[float]) -> float:
    return float(sum(values))


def fmt_float(value: float | int | str | None, digits: int = 6) -> float | str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if not math.isfinite(float(value)):
        return ""
    return round(float(value), digits)


def ensure_output_dirs(output_dir: Path) -> dict[str, Path]:
    paths = {
        "root": output_dir,
        "data": output_dir / DATA_DIRNAME,
        "reports": output_dir / REPORTS_DIRNAME,
        "summaries": output_dir / SUMMARIES_DIRNAME,
    }
    for path in paths.values():
        path.mkdir(parents=True, exist_ok=True)
    return paths


def data_path(sim_result_dir: Path, filename: str) -> Path:
    return sim_result_dir / DATA_DIRNAME / filename


def load_supplier_criticality(path: Path) -> dict[str, dict[str, Any]]:
    criticality: dict[str, dict[str, Any]] = {}
    if not path.exists():
        return criticality
    with path.open(newline="", encoding="utf-8-sig") as handle:
        for row in csv.DictReader(handle):
            supplier_id = row.get("supplier_id", "").strip()
            if not supplier_id:
                continue
            criticality[supplier_id] = {
                "supplier_name": row.get("supplier_name", supplier_id).strip() or supplier_id,
                "local_criticality_score": parse_float(row.get("local_criticality_score")),
                "system_criticality_score": parse_float(row.get("system_criticality_score")),
                "overall_criticality_score": parse_float(row.get("overall_criticality_score")),
                "sole_source_pairs": parse_int(row.get("sole_source_pairs")),
                "shared_source_pairs": parse_int(row.get("shared_source_pairs")),
                "observed_sourcing_share": parse_float(row.get("observed_sourcing_share")),
                "target_sourcing_share": parse_float(row.get("target_sourcing_share")),
                "avg_procurement_lead_days": parse_float(row.get("avg_procurement_lead_days")),
                "items_supplied_count": parse_int(row.get("items_supplied_count")),
                "dest_nodes_count": parse_int(row.get("dest_nodes_count")),
                "total_shipped_qty": parse_float(row.get("total_shipped_qty")),
                "rank": parse_int(row.get("rank"), default=999999),
            }
    return criticality


def load_supplier_sensitivity(path: Path) -> dict[str, dict[str, float]]:
    sensitivity: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
    if not path.exists():
        return {}
    with path.open(newline="", encoding="utf-8-sig") as handle:
        for row in csv.DictReader(handle):
            supplier_id = row.get("supplier_id", "").strip()
            if not supplier_id or supplier_id.upper() == "GLOBAL":
                continue
            current = sensitivity[supplier_id]
            current["max_external_procured_qty_delta"] = max(
                current["max_external_procured_qty_delta"],
                parse_float(row.get("max_external_procured_qty_delta")),
            )
            current["max_fill_rate_drop"] = max(
                current["max_fill_rate_drop"],
                parse_float(row.get("max_fill_rate_drop")),
            )
            min_acceptable = parse_float(row.get("tested_min_acceptable_scale"), default=1.0)
            current["lowest_acceptable_scale"] = (
                min(current["lowest_acceptable_scale"], min_acceptable)
                if current["lowest_acceptable_scale"]
                else min_acceptable
            )
            first_bad = parse_float(row.get("first_unacceptable_level"), default=0.0)
            if first_bad > 0:
                current["first_unacceptable_level"] = (
                    min(current["first_unacceptable_level"], first_bad)
                    if current["first_unacceptable_level"]
                    else first_bad
                )
    return {supplier: dict(values) for supplier, values in sensitivity.items()}


def empty_bucket() -> dict[str, Any]:
    return {
        "shipped_qty": 0.0,
        "pulled_qty": 0.0,
        "shipment_count": 0,
        "lead_weighted_num": 0.0,
        "lead_weighted_den": 0.0,
        "reliability_weighted_num": 0.0,
        "reliability_weighted_den": 0.0,
        "capacity_qty": 0.0,
        "capacity_used_qty": 0.0,
        "capacity_util_values": [],
        "stock_min": None,
        "stock_end": None,
        "stock_last_day": -1,
        "mrp_release_qty": 0.0,
        "mrp_planned_receipt_qty": 0.0,
        "mrp_order_count": 0,
        "mrp_outside_horizon_count": 0,
        "mrp_late_count": 0,
        "mrp_short_count": 0,
        "lead_reference_values": [],
        "lead_cover_values": [],
        "safety_time_values": [],
    }


def empty_meta() -> dict[str, Any]:
    return {
        "lead_values": [],
        "reliability_values": [],
        "weekly_shipped_qty": defaultdict(float),
        "weekly_mrp_release_qty": defaultdict(float),
        "active_weeks": set(),
        "shipment_count": 0,
        "capacity_observations": 0,
        "stock_observations": 0,
        "mrp_order_count": 0,
        "mrp_late_count": 0,
        "mrp_short_count": 0,
        "mrp_outside_horizon_count": 0,
        "lead_reference_values": [],
        "lead_cover_values": [],
        "safety_time_values": [],
    }


def add_stock(bucket: dict[str, Any], stock: float, day: int) -> None:
    current_min = bucket["stock_min"]
    bucket["stock_min"] = stock if current_min is None else min(float(current_min), stock)
    if day >= int(bucket["stock_last_day"]):
        bucket["stock_last_day"] = day
        bucket["stock_end"] = stock


def load_simulation_tables(sim_result_dir: Path) -> tuple[dict[tuple[PairKey, int], dict[str, Any]], dict[PairKey, dict[str, Any]], int, dict[str, int]]:
    pair_week: dict[tuple[PairKey, int], dict[str, Any]] = defaultdict(empty_bucket)
    pair_meta: dict[PairKey, dict[str, Any]] = defaultdict(empty_meta)
    supplier_item_to_keys: dict[tuple[str, str], set[PairKey]] = defaultdict(set)
    max_week = 0
    counters = {
        "shipment_rows": 0,
        "capacity_rows": 0,
        "stock_rows": 0,
        "mrp_order_rows": 0,
        "observable_mrp_late_rows": 0,
        "observable_mrp_short_rows": 0,
    }

    shipments_path = data_path(sim_result_dir, "production_supplier_shipments_daily.csv")
    with shipments_path.open(newline="", encoding="utf-8-sig") as handle:
        for row in csv.DictReader(handle):
            day = parse_int(row.get("day"))
            week = max(0, day // 7)
            max_week = max(max_week, week)
            supplier_id = row.get("src_node_id", "").strip()
            dst_node_id = row.get("dst_node_id", "").strip()
            item_id = row.get("item_id", "").strip()
            if not supplier_id or not item_id:
                continue
            if not supplier_id.startswith("SDC-"):
                continue
            key = (supplier_id, dst_node_id, item_id)
            supplier_item_to_keys[(supplier_id, item_id)].add(key)
            bucket = pair_week[(key, week)]
            meta = pair_meta[key]
            shipped_qty = parse_float(row.get("shipped_qty"))
            pulled_qty = parse_float(row.get("pulled_qty"))
            lead_days = parse_float(row.get("lead_days"))
            reliability = parse_float(row.get("reliability"), default=1.0)

            bucket["shipped_qty"] += shipped_qty
            bucket["pulled_qty"] += pulled_qty
            bucket["shipment_count"] += 1
            bucket["lead_weighted_num"] += lead_days * max(shipped_qty, 1.0)
            bucket["lead_weighted_den"] += max(shipped_qty, 1.0)
            bucket["reliability_weighted_num"] += reliability * max(shipped_qty, 1.0)
            bucket["reliability_weighted_den"] += max(shipped_qty, 1.0)

            meta["lead_values"].append(lead_days)
            meta["reliability_values"].append(reliability)
            meta["weekly_shipped_qty"][week] += shipped_qty
            meta["active_weeks"].add(week)
            meta["shipment_count"] += 1
            counters["shipment_rows"] += 1

    capacity_path = data_path(sim_result_dir, "production_supplier_capacity_daily.csv")
    if capacity_path.exists():
        with capacity_path.open(newline="", encoding="utf-8-sig") as handle:
            for row in csv.DictReader(handle):
                day = parse_int(row.get("day"))
                week = max(0, day // 7)
                max_week = max(max_week, week)
                supplier_id = row.get("node_id", "").strip()
                item_id = row.get("item_id", "").strip()
                if not supplier_id or not item_id:
                    continue
                if not supplier_id.startswith("SDC-"):
                    continue
                keys = supplier_item_to_keys.get((supplier_id, item_id)) or {(supplier_id, "", item_id)}
                capacity_qty = parse_float(row.get("capacity_qty_per_day"))
                used_qty = parse_float(row.get("used_qty"))
                utilization = parse_float(row.get("utilization"), default=safe_div(used_qty, capacity_qty))
                for key in keys:
                    bucket = pair_week[(key, week)]
                    meta = pair_meta[key]
                    bucket["capacity_qty"] += capacity_qty
                    bucket["capacity_used_qty"] += used_qty
                    bucket["capacity_util_values"].append(utilization)
                    meta["capacity_observations"] += 1
                counters["capacity_rows"] += 1

    stock_path = data_path(sim_result_dir, "production_supplier_stocks_daily.csv")
    if stock_path.exists():
        with stock_path.open(newline="", encoding="utf-8-sig") as handle:
            for row in csv.DictReader(handle):
                day = parse_int(row.get("day"))
                week = max(0, day // 7)
                max_week = max(max_week, week)
                supplier_id = row.get("node_id", "").strip()
                item_id = row.get("item_id", "").strip()
                if not supplier_id or not item_id:
                    continue
                if not supplier_id.startswith("SDC-"):
                    continue
                keys = supplier_item_to_keys.get((supplier_id, item_id)) or {(supplier_id, "", item_id)}
                stock = parse_float(row.get("stock_end_of_day"))
                for key in keys:
                    add_stock(pair_week[(key, week)], stock, day)
                    pair_meta[key]["stock_observations"] += 1
                counters["stock_rows"] += 1

    orders_path = data_path(sim_result_dir, "mrp_orders_daily.csv")
    if orders_path.exists():
        with orders_path.open(newline="", encoding="utf-8-sig") as handle:
            for row in csv.DictReader(handle):
                supplier_id = row.get("src_node_id", "").strip()
                dst_node_id = row.get("dst_node_id", "").strip()
                item_id = row.get("item_id", "").strip()
                if not supplier_id or not item_id:
                    continue
                if not supplier_id.startswith("SDC-"):
                    continue
                if (supplier_id, item_id) not in supplier_item_to_keys:
                    continue
                release_day = parse_int(row.get("release_day"), default=parse_int(row.get("day")))
                week = max(0, release_day // 7)
                max_week = max(max_week, week)
                key = (supplier_id, dst_node_id, item_id)
                supplier_item_to_keys[(supplier_id, item_id)].add(key)
                bucket = pair_week[(key, week)]
                meta = pair_meta[key]

                release_qty = parse_float(row.get("release_qty"))
                planned_qty = parse_float(row.get("planned_receipt_qty"))
                arrival_day = parse_float(row.get("arrival_day"))
                actual_receipt_day = parse_float(row.get("actual_receipt_day"), default=arrival_day)
                receipt_status = row.get("receipt_status", "")
                is_late = actual_receipt_day > arrival_day + EPSILON
                is_short = planned_qty + EPSILON < 0.98 * release_qty

                bucket["mrp_release_qty"] += release_qty
                bucket["mrp_planned_receipt_qty"] += planned_qty
                bucket["mrp_order_count"] += 1
                bucket["mrp_outside_horizon_count"] += int("outside_horizon" in receipt_status)
                bucket["mrp_late_count"] += int(is_late)
                bucket["mrp_short_count"] += int(is_short)
                for source_col, target_col in [
                    ("lead_reference_days", "lead_reference_values"),
                    ("lead_cover_days", "lead_cover_values"),
                    ("safety_time_days", "safety_time_values"),
                ]:
                    value = parse_float(row.get(source_col))
                    if value > 0:
                        bucket[target_col].append(value)
                        meta[target_col].append(value)
                meta["weekly_mrp_release_qty"][week] += release_qty
                meta["mrp_order_count"] += 1
                meta["mrp_outside_horizon_count"] += int("outside_horizon" in receipt_status)
                meta["mrp_late_count"] += int(is_late)
                meta["mrp_short_count"] += int(is_short)
                counters["mrp_order_rows"] += 1
                counters["observable_mrp_late_rows"] += int(is_late)
                counters["observable_mrp_short_rows"] += int(is_short)

    return pair_week, pair_meta, max_week, counters


def compute_key_stats(
    pair_meta: dict[PairKey, dict[str, Any]],
    criticality: dict[str, dict[str, Any]],
    sensitivity: dict[str, dict[str, float]],
    max_week: int,
) -> dict[PairKey, dict[str, float | str | int]]:
    key_stats: dict[PairKey, dict[str, float | str | int]] = {}
    for key, meta in pair_meta.items():
        supplier_id, _, _ = key
        supplier_crit = criticality.get(supplier_id, {})
        supplier_sens = sensitivity.get(supplier_id, {})
        weekly_shipments = [float(meta["weekly_shipped_qty"].get(week, 0.0)) for week in range(max_week + 1)]
        weekly_releases = [float(meta["weekly_mrp_release_qty"].get(week, 0.0)) for week in range(max_week + 1)]
        lead_values = list(meta["lead_values"]) or list(meta["lead_reference_values"])
        lead_q50 = quantile(lead_values, 0.50)
        lead_q90 = quantile(lead_values, 0.90, default=lead_q50)
        lead_q95 = quantile(lead_values, 0.95, default=lead_q90)
        weekly_qty_q50 = quantile(weekly_shipments, 0.50)
        weekly_qty_q90 = quantile(weekly_shipments, 0.90)
        weekly_qty_q95 = quantile(weekly_shipments, 0.95)
        nonzero_weeks = [qty for qty in weekly_shipments if qty > EPSILON]

        criticality_score = parse_float(supplier_crit.get("overall_criticality_score"), default=0.0)
        local_criticality = parse_float(supplier_crit.get("local_criticality_score"), default=criticality_score)
        observed_share = parse_float(supplier_crit.get("observed_sourcing_share"), default=0.0)
        target_share = parse_float(supplier_crit.get("target_sourcing_share"), default=0.0)
        sole_pairs = parse_int(supplier_crit.get("sole_source_pairs"), default=0)
        shared_pairs = parse_int(supplier_crit.get("shared_source_pairs"), default=0)
        mono_source_score = 1.0 if sole_pairs > 0 and (shared_pairs == 0 or max(observed_share, target_share) >= 0.85) else 0.0

        key_stats[key] = {
            "supplier_name": str(supplier_crit.get("supplier_name", supplier_id)),
            "lead_observation_count": len(lead_values),
            "lead_days_q50": lead_q50,
            "lead_days_q90": lead_q90,
            "lead_days_q95": lead_q95,
            "lead_interval_width_days": max(0.0, lead_q90 - lead_q50),
            "weekly_shipped_qty_mean": mean(weekly_shipments),
            "weekly_shipped_qty_nonzero_mean": mean(nonzero_weeks),
            "weekly_shipped_qty_q50": weekly_qty_q50,
            "weekly_shipped_qty_q90": weekly_qty_q90,
            "weekly_shipped_qty_q95": weekly_qty_q95,
            "weekly_mrp_release_qty_mean": mean(weekly_releases),
            "active_week_count": len(meta["active_weeks"]),
            "first_active_week": min(meta["active_weeks"]) if meta["active_weeks"] else 0,
            "last_active_week": max(meta["active_weeks"]) if meta["active_weeks"] else 0,
            "shipment_count": int(meta["shipment_count"]),
            "capacity_observations": int(meta["capacity_observations"]),
            "stock_observations": int(meta["stock_observations"]),
            "mrp_order_count": int(meta["mrp_order_count"]),
            "mrp_outside_horizon_count": int(meta["mrp_outside_horizon_count"]),
            "criticality_score": criticality_score,
            "local_criticality_score": local_criticality,
            "mono_source_score": mono_source_score,
            "sole_source_pairs": sole_pairs,
            "shared_source_pairs": shared_pairs,
            "observed_sourcing_share": observed_share,
            "target_sourcing_share": target_share,
            "sensitivity_external_qty_delta": parse_float(supplier_sens.get("max_external_procured_qty_delta")),
            "sensitivity_fill_rate_drop": parse_float(supplier_sens.get("max_fill_rate_drop")),
            "sensitivity_lowest_acceptable_scale": parse_float(supplier_sens.get("lowest_acceptable_scale"), default=1.0),
            "sensitivity_first_unacceptable_level": parse_float(supplier_sens.get("first_unacceptable_level")),
        }
    return key_stats


def compute_data_quality_components(stats: dict[str, Any]) -> dict[str, float]:
    lead_score = min(parse_float(stats.get("lead_observation_count")) / 10.0, 1.0)
    capacity_score = 1.0 if parse_float(stats.get("capacity_observations")) > 0 else 0.0
    stock_score = 1.0 if parse_float(stats.get("stock_observations")) > 0 else 0.0
    criticality_score = 1.0 if parse_float(stats.get("criticality_score")) > 0 else 0.4
    active_score = min(parse_float(stats.get("active_week_count")) / 26.0, 1.0)
    return {
        "lead_score": clamp(lead_score),
        "capacity_score": clamp(capacity_score),
        "stock_score": clamp(stock_score),
        "criticality_score": clamp(criticality_score),
        "active_score": clamp(active_score),
    }


def compute_data_quality(stats: dict[str, Any]) -> float:
    components = compute_data_quality_components(stats)
    return clamp(
        0.20 * components["lead_score"]
        + 0.20 * components["capacity_score"]
        + 0.20 * components["stock_score"]
        + 0.20 * components["criticality_score"]
        + 0.20 * components["active_score"]
    )


def make_action(level: str) -> str:
    actions = {
        "critical": "crisis_review_activate_backup_or_buffer",
        "red": "confirm_supplier_commitment_and_recompute_safety_stock",
        "amber": "weekly_watch_confirm_capacity_and_open_orders",
        "green": "standard_monitoring",
    }
    return actions[level]


def classify_action(priority_score: float, probability_proxy: float, uncertainty: float) -> str:
    if priority_score >= 0.55 or probability_proxy >= 0.70:
        return "critical"
    if priority_score >= 0.35 or probability_proxy >= 0.50:
        return "red"
    if priority_score >= 0.18 or probability_proxy >= 0.30 or uncertainty >= 0.70:
        return "amber"
    return "green"


def classify_decision_zone(
    probability_proxy: float,
    probability_high: float,
    priority_score: float,
    resilience_score: float,
    criticality_score: float,
    uncertainty_pressure: float,
    early_warning_flag: bool,
    change_point_flag: bool,
) -> str:
    if (
        priority_score >= 0.35
        or probability_high >= 0.60
        or (probability_proxy >= 0.35 and resilience_score < 0.40 and criticality_score >= 0.45)
    ):
        return "rouge"
    if priority_score >= 0.18 or probability_high >= 0.45 or uncertainty_pressure >= 0.75:
        return "orange"
    if probability_proxy >= 0.18 or early_warning_flag or change_point_flag or uncertainty_pressure >= 0.55:
        return "jaune"
    return "vert"


def make_robust_decision(zone: str) -> str:
    decisions = {
        "vert": "routine_monitoring",
        "jaune": "watch_collect_data_and_confirm_supplier_status",
        "orange": "preventive_action_buffer_capacity_or_supplier_review",
        "rouge": "immediate_robust_decision_dual_source_buffer_or_escalation",
    }
    return decisions[zone]


def normalizers_from_stats(key_stats: dict[PairKey, dict[str, Any]]) -> dict[str, float]:
    lead_max = max((parse_float(s.get("lead_days_q90")) for s in key_stats.values()), default=1.0)
    qty_max = max((math.log1p(parse_float(s.get("weekly_shipped_qty_q95"))) for s in key_stats.values()), default=1.0)
    sens_delta_max = max(
        (math.log1p(parse_float(s.get("sensitivity_external_qty_delta"))) for s in key_stats.values()),
        default=1.0,
    )
    sens_fill_max = max((parse_float(s.get("sensitivity_fill_rate_drop")) for s in key_stats.values()), default=0.0)
    return {
        "lead_q90_max": max(lead_max, 1.0),
        "weekly_qty_q95_log_max": max(qty_max, 1.0),
        "sensitivity_delta_log_max": max(sens_delta_max, 1.0),
        "sensitivity_fill_drop_max": max(sens_fill_max, 0.01),
    }


def build_week_panel(
    pair_week: dict[tuple[PairKey, int], dict[str, Any]],
    key_stats: dict[PairKey, dict[str, Any]],
    max_week: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    norms = normalizers_from_stats(key_stats)
    panel_rows: list[dict[str, Any]] = []
    latest_rows: list[dict[str, Any]] = []
    action_counts: dict[str, int] = defaultdict(int)
    decision_zone_counts: dict[str, int] = defaultdict(int)

    for key in sorted(key_stats):
        supplier_id, dst_node_id, item_id = key
        stats = key_stats[key]
        lead_q50 = parse_float(stats.get("lead_days_q50"))
        lead_q90 = parse_float(stats.get("lead_days_q90"), default=lead_q50)
        lead_interval_width = parse_float(stats.get("lead_interval_width_days"))
        lead_norm = clamp(lead_q90 / norms["lead_q90_max"])
        qty_q95 = parse_float(stats.get("weekly_shipped_qty_q95"))
        flow_exposure_norm = clamp(math.log1p(qty_q95) / norms["weekly_qty_q95_log_max"])
        sensitivity_delta_norm = clamp(
            math.log1p(parse_float(stats.get("sensitivity_external_qty_delta")))
            / norms["sensitivity_delta_log_max"]
        )
        sensitivity_fill_norm = clamp(
            parse_float(stats.get("sensitivity_fill_rate_drop")) / norms["sensitivity_fill_drop_max"]
        )
        sensitivity_norm = clamp(0.65 * sensitivity_delta_norm + 0.35 * sensitivity_fill_norm)
        data_quality_components = compute_data_quality_components(stats)
        data_quality = compute_data_quality(stats)
        lead_uncertainty = clamp(safe_div(lead_interval_width, max(lead_q50, 1.0)))

        shipped_window_4: deque[float] = deque(maxlen=4)
        shipped_prev_4: deque[float] = deque(maxlen=4)
        shipped_window_12: deque[float] = deque(maxlen=12)
        util_window_4: deque[float] = deque(maxlen=4)
        util_prev_4: deque[float] = deque(maxlen=4)
        stock_history: deque[float] = deque(maxlen=5)
        last_stock_end: float | None = None
        latest_row: dict[str, Any] | None = None

        for week in range(max_week + 1):
            bucket = pair_week.get((key, week), empty_bucket())
            shipped_qty = float(bucket["shipped_qty"])
            pulled_qty = float(bucket["pulled_qty"])
            lead_avg = safe_div(float(bucket["lead_weighted_num"]), float(bucket["lead_weighted_den"]), default=lead_q50)
            reliability_avg = safe_div(
                float(bucket["reliability_weighted_num"]),
                float(bucket["reliability_weighted_den"]),
                default=mean(list(stats.get("reliability_values", [])), default=1.0),
            )
            capacity_qty = float(bucket["capacity_qty"])
            capacity_used_qty = float(bucket["capacity_used_qty"])
            util_values = list(bucket["capacity_util_values"])
            capacity_util_avg = mean(util_values, default=safe_div(capacity_used_qty, capacity_qty))
            capacity_util_max = max(util_values) if util_values else capacity_util_avg
            stock_end_raw = bucket["stock_end"]
            if stock_end_raw is not None:
                last_stock_end = float(stock_end_raw)
            stock_end = last_stock_end
            stock_min = bucket["stock_min"] if bucket["stock_min"] is not None else stock_end

            prev4_before_update = list(shipped_prev_4)
            if len(shipped_window_4) == 4:
                shipped_prev_4.append(shipped_window_4[0])
            shipped_window_4.append(shipped_qty)
            shipped_window_12.append(shipped_qty)
            if len(util_window_4) == 4:
                util_prev_4.append(util_window_4[0])
            util_window_4.append(capacity_util_avg)
            if stock_end is not None:
                stock_history.append(stock_end)

            trailing_4w_qty = rolling_sum(shipped_window_4)
            trailing_12w_avg_qty = mean(list(shipped_window_12))
            prev_4w_avg_qty = mean(prev4_before_update)
            current_4w_avg_qty = mean(list(shipped_window_4))
            flow_velocity_4w = current_4w_avg_qty - prev_4w_avg_qty
            flow_cv_12w = safe_div(stdev(list(shipped_window_12)), trailing_12w_avg_qty)
            flow_volatility_pressure = clamp(flow_cv_12w)
            flow_spike_pressure = clamp(
                safe_div(current_4w_avg_qty - parse_float(stats.get("weekly_shipped_qty_q50")), max(qty_q95, 1.0))
            )

            util_4w_avg = mean(list(util_window_4), default=capacity_util_avg)
            util_prev_4w_avg = mean(list(util_prev_4), default=util_4w_avg)
            util_acceleration = util_4w_avg - util_prev_4w_avg
            capacity_pressure = clamp((max(util_4w_avg, capacity_util_max) - 0.75) / 0.25)
            capacity_trend_pressure = clamp(util_acceleration / 0.15)

            stock_coverage_days: float | None = None
            stock_pressure = 0.0
            stock_trend_pressure = 0.0
            if stock_end is not None:
                avg_daily_ship = trailing_12w_avg_qty / 7.0
                if avg_daily_ship > EPSILON:
                    stock_coverage_days = stock_end / avg_daily_ship
                    target_coverage_days = lead_q90 + 14.0
                    stock_pressure = clamp(
                        safe_div(target_coverage_days - stock_coverage_days, max(target_coverage_days, 1.0))
                    )
                if len(stock_history) >= 5 and trailing_4w_qty > EPSILON:
                    stock_delta_4w = stock_history[-1] - stock_history[0]
                    stock_trend_pressure = clamp(safe_div(-stock_delta_4w, trailing_4w_qty))

            uncertainty_pressure = clamp(0.60 * (1.0 - data_quality) + 0.40 * lead_uncertainty)
            criticality_score = clamp(parse_float(stats.get("criticality_score")))
            local_criticality = clamp(parse_float(stats.get("local_criticality_score")))
            mono_source_score = clamp(parse_float(stats.get("mono_source_score")))

            dynamic_pressure = clamp(
                0.35 * stock_trend_pressure
                + 0.25 * capacity_trend_pressure
                + 0.20 * flow_spike_pressure
                + 0.20 * flow_volatility_pressure
            )
            performance_distance_score = clamp(
                0.25 * lead_norm
                + 0.20 * capacity_pressure
                + 0.20 * stock_pressure
                + 0.15 * flow_volatility_pressure
                + 0.10 * dynamic_pressure
                + 0.10 * clamp(1.0 - reliability_avg)
            )
            performance_score_current = clamp(1.0 - performance_distance_score)
            change_point_score = clamp(
                0.45
                * safe_div(
                    abs(flow_velocity_4w),
                    max(stdev(list(shipped_window_12)), qty_q95 * 0.10, 1.0),
                )
                + 0.25 * capacity_trend_pressure
                + 0.20 * stock_trend_pressure
                + 0.10 * flow_spike_pressure
            )
            change_point_flag = change_point_score >= 0.65
            early_warning_score = clamp(
                0.30 * flow_volatility_pressure
                + 0.25 * stock_trend_pressure
                + 0.20 * capacity_trend_pressure
                + 0.15 * lead_uncertainty
                + 0.10 * uncertainty_pressure
            )
            early_warning_flag = early_warning_score >= 0.45

            stock_absorption_score = 1.0 - stock_pressure if stock_end is not None else 0.50
            capacity_headroom_score = 1.0 - capacity_pressure
            recovery_slope_score = 1.0 - dynamic_pressure
            source_flexibility_score = 1.0 - mono_source_score
            sensitivity_resilience_score = 1.0 - sensitivity_norm
            resilience_score = clamp(
                0.25 * stock_absorption_score
                + 0.20 * capacity_headroom_score
                + 0.20 * recovery_slope_score
                + 0.15 * source_flexibility_score
                + 0.10 * sensitivity_resilience_score
                + 0.10 * data_quality
            )
            performance_drop_proxy = clamp(
                0.35 * stock_pressure
                + 0.25 * capacity_pressure
                + 0.20 * dynamic_pressure
                + 0.20 * sensitivity_norm
            )
            risk_signal = clamp(
                0.20 * criticality_score
                + 0.14 * mono_source_score
                + 0.15 * stock_pressure
                + 0.11 * capacity_pressure
                + 0.10 * lead_norm
                + 0.08 * flow_exposure_norm
                + 0.08 * sensitivity_norm
                + 0.08 * dynamic_pressure
                + 0.06 * uncertainty_pressure
            )
            probability_proxy = clamp(sigmoid(-3.0 + 5.0 * risk_signal), 0.0, 0.95)
            risk_interval_half_width = 0.04 + 0.26 * uncertainty_pressure
            probability_low = clamp(probability_proxy - risk_interval_half_width)
            probability_high = clamp(probability_proxy + risk_interval_half_width)
            time_to_recover_weeks_proxy = 1.0 + 8.0 * (1.0 - resilience_score) + 4.0 * risk_signal
            priority_score = clamp(
                probability_proxy
                * (0.35 + 0.65 * max(criticality_score, local_criticality))
                * (0.75 + 0.25 * sensitivity_norm)
            )
            action_level = classify_action(priority_score, probability_proxy, uncertainty_pressure)
            decision_zone = classify_decision_zone(
                probability_proxy,
                probability_high,
                priority_score,
                resilience_score,
                max(criticality_score, local_criticality),
                uncertainty_pressure,
                early_warning_flag,
                change_point_flag,
            )
            action_counts[action_level] += 1
            decision_zone_counts[decision_zone] += 1

            exposure_qty_4w = max(
                4.0 * trailing_12w_avg_qty,
                qty_q95,
                parse_float(stats.get("weekly_mrp_release_qty_mean")) * 4.0,
            )
            expected_exposure_qty_4w = probability_proxy * exposure_qty_4w * (0.5 + 0.5 * criticality_score)
            cvar_exposure_qty_4w = probability_proxy * max(exposure_qty_4w, 4.0 * qty_q95) * (
                0.5 + 0.5 * max(criticality_score, local_criticality)
            )

            row = {
                "week_index": week,
                "supplier_id": supplier_id,
                "supplier_name": stats.get("supplier_name", supplier_id),
                "dst_node_id": dst_node_id,
                "item_id": item_id,
                "shipped_qty": fmt_float(shipped_qty, 4),
                "pulled_qty": fmt_float(pulled_qty, 4),
                "shipment_count": int(bucket["shipment_count"]),
                "mrp_order_count": int(bucket["mrp_order_count"]),
                "mrp_release_qty": fmt_float(float(bucket["mrp_release_qty"]), 4),
                "mrp_planned_receipt_qty": fmt_float(float(bucket["mrp_planned_receipt_qty"]), 4),
                "lead_days_avg_week": fmt_float(lead_avg, 4),
                "lead_days_q50": fmt_float(lead_q50, 4),
                "lead_days_q90": fmt_float(lead_q90, 4),
                "lead_days_q95": fmt_float(parse_float(stats.get("lead_days_q95")), 4),
                "lead_interval_width_days": fmt_float(lead_interval_width, 4),
                "reliability_avg_week": fmt_float(reliability_avg, 6),
                "capacity_qty_week": fmt_float(capacity_qty, 4),
                "capacity_used_qty_week": fmt_float(capacity_used_qty, 4),
                "capacity_utilization_avg_week": fmt_float(capacity_util_avg, 6),
                "capacity_utilization_max_week": fmt_float(capacity_util_max, 6),
                "stock_end_of_week": fmt_float(stock_end, 4),
                "stock_min_of_week": fmt_float(stock_min, 4),
                "stock_coverage_days": fmt_float(stock_coverage_days, 4),
                "trailing_4w_shipped_qty": fmt_float(trailing_4w_qty, 4),
                "trailing_12w_avg_shipped_qty": fmt_float(trailing_12w_avg_qty, 4),
                "flow_velocity_4w": fmt_float(flow_velocity_4w, 4),
                "flow_cv_12w": fmt_float(flow_cv_12w, 6),
                "capacity_utilization_trailing_4w": fmt_float(util_4w_avg, 6),
                "capacity_utilization_acceleration_4w": fmt_float(util_acceleration, 6),
                "criticality_score": fmt_float(criticality_score, 6),
                "local_criticality_score": fmt_float(local_criticality, 6),
                "mono_source_score": fmt_float(mono_source_score, 6),
                "performance_distance_score": fmt_float(performance_distance_score, 6),
                "performance_score_current": fmt_float(performance_score_current, 6),
                "stock_pressure": fmt_float(stock_pressure, 6),
                "capacity_pressure": fmt_float(capacity_pressure, 6),
                "lead_time_pressure": fmt_float(lead_norm, 6),
                "flow_exposure_pressure": fmt_float(flow_exposure_norm, 6),
                "flow_volatility_pressure": fmt_float(flow_volatility_pressure, 6),
                "dynamic_pressure": fmt_float(dynamic_pressure, 6),
                "change_point_score": fmt_float(change_point_score, 6),
                "change_point_flag": int(change_point_flag),
                "early_warning_score": fmt_float(early_warning_score, 6),
                "early_warning_flag": int(early_warning_flag),
                "resilience_score": fmt_float(resilience_score, 6),
                "performance_drop_proxy": fmt_float(performance_drop_proxy, 6),
                "time_to_recover_weeks_proxy": fmt_float(time_to_recover_weeks_proxy, 4),
                "sensitivity_external_qty_delta": fmt_float(parse_float(stats.get("sensitivity_external_qty_delta")), 4),
                "sensitivity_external_qty_delta_pressure": fmt_float(sensitivity_delta_norm, 6),
                "sensitivity_fill_rate_drop": fmt_float(parse_float(stats.get("sensitivity_fill_rate_drop")), 6),
                "sensitivity_fill_rate_drop_pressure": fmt_float(sensitivity_fill_norm, 6),
                "sensitivity_lowest_acceptable_scale": fmt_float(parse_float(stats.get("sensitivity_lowest_acceptable_scale")), 6),
                "sensitivity_first_unacceptable_level": fmt_float(parse_float(stats.get("sensitivity_first_unacceptable_level")), 6),
                "sensitivity_pressure": fmt_float(sensitivity_norm, 6),
                "lead_uncertainty_pressure": fmt_float(lead_uncertainty, 6),
                "lead_observation_count": int(parse_float(stats.get("lead_observation_count"))),
                "capacity_observations": int(parse_float(stats.get("capacity_observations"))),
                "stock_observations": int(parse_float(stats.get("stock_observations"))),
                "active_week_count": int(parse_float(stats.get("active_week_count"))),
                "data_quality_lead_score": fmt_float(data_quality_components["lead_score"], 6),
                "data_quality_capacity_score": fmt_float(data_quality_components["capacity_score"], 6),
                "data_quality_stock_score": fmt_float(data_quality_components["stock_score"], 6),
                "data_quality_criticality_score": fmt_float(data_quality_components["criticality_score"], 6),
                "data_quality_active_score": fmt_float(data_quality_components["active_score"], 6),
                "uncertainty_pressure": fmt_float(uncertainty_pressure, 6),
                "data_quality_score": fmt_float(data_quality, 6),
                "risk_signal": fmt_float(risk_signal, 6),
                "risk_probability_proxy_4w": fmt_float(probability_proxy, 6),
                "risk_probability_low_proxy_4w": fmt_float(probability_low, 6),
                "risk_probability_high_proxy_4w": fmt_float(probability_high, 6),
                "action_priority_score": fmt_float(priority_score, 6),
                "expected_exposure_qty_4w_proxy": fmt_float(expected_exposure_qty_4w, 4),
                "cvar_exposure_qty_4w_proxy": fmt_float(cvar_exposure_qty_4w, 4),
                "action_level": action_level,
                "decision_zone": decision_zone,
                "recommended_action": make_action(action_level),
                "robust_decision": make_robust_decision(decision_zone),
            }
            panel_rows.append(row)
            latest_row = row

        if latest_row is not None:
            latest_rows.append(latest_row)

    metadata = {
        "normalizers": norms,
        "action_counts_all_weeks": dict(action_counts),
        "decision_zone_counts_all_weeks": dict(decision_zone_counts),
    }
    return panel_rows, latest_rows, metadata


def aggregate_supplier_rows(latest_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in latest_rows:
        grouped[str(row["supplier_id"])].append(row)

    supplier_rows: list[dict[str, Any]] = []
    level_rank = {"green": 0, "amber": 1, "red": 2, "critical": 3}
    zone_rank = {"vert": 0, "jaune": 1, "orange": 2, "rouge": 3}
    for supplier_id, rows in grouped.items():
        rows_sorted = sorted(rows, key=lambda r: parse_float(r["action_priority_score"]), reverse=True)
        top = rows_sorted[0]
        priority_values = [parse_float(r["action_priority_score"]) for r in rows]
        probability_values = [parse_float(r["risk_probability_proxy_4w"]) for r in rows]
        probability_high_values = [parse_float(r["risk_probability_high_proxy_4w"]) for r in rows]
        resilience_values = [parse_float(r["resilience_score"]) for r in rows]
        early_warning_count = sum(parse_int(r["early_warning_flag"]) for r in rows)
        change_point_count = sum(parse_int(r["change_point_flag"]) for r in rows)
        expected_exposure = sum(parse_float(r["expected_exposure_qty_4w_proxy"]) for r in rows)
        cvar_exposure = sum(parse_float(r["cvar_exposure_qty_4w_proxy"]) for r in rows)
        worst_level = max((str(r["action_level"]) for r in rows), key=lambda level: level_rank[level])
        worst_zone = max((str(r["decision_zone"]) for r in rows), key=lambda zone: zone_rank[zone])
        item_preview = ", ".join(str(r["item_id"]) for r in rows_sorted[:5])
        dst_preview = ", ".join(sorted({str(r["dst_node_id"]) for r in rows if str(r["dst_node_id"])}))
        supplier_rows.append(
            {
                "supplier_id": supplier_id,
                "supplier_name": top["supplier_name"],
                "pair_count": len(rows),
                "max_risk_probability_proxy_4w": fmt_float(max(probability_values), 6),
                "max_risk_probability_high_proxy_4w": fmt_float(max(probability_high_values), 6),
                "mean_risk_probability_proxy_4w": fmt_float(mean(probability_values), 6),
                "max_action_priority_score": fmt_float(max(priority_values), 6),
                "mean_action_priority_score": fmt_float(mean(priority_values), 6),
                "min_resilience_score": fmt_float(min(resilience_values), 6),
                "mean_resilience_score": fmt_float(mean(resilience_values), 6),
                "early_warning_pair_count": early_warning_count,
                "change_point_pair_count": change_point_count,
                "expected_exposure_qty_4w_proxy_sum": fmt_float(expected_exposure, 4),
                "cvar_exposure_qty_4w_proxy_sum": fmt_float(cvar_exposure, 4),
                "worst_action_level": worst_level,
                "worst_decision_zone": worst_zone,
                "recommended_action": make_action(worst_level),
                "robust_decision": make_robust_decision(worst_zone),
                "top_item_id": top["item_id"],
                "top_dst_node_id": top["dst_node_id"],
                "items_preview": item_preview,
                "destinations_preview": dst_preview,
            }
        )
    return sorted(
        supplier_rows,
        key=lambda row: (parse_float(row["max_action_priority_score"]), parse_float(row["expected_exposure_qty_4w_proxy_sum"])),
        reverse=True,
    )


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def markdown_table(rows: list[dict[str, Any]], columns: list[str], limit: int = 12) -> str:
    if not rows:
        return "_Aucune ligne._"
    lines = [
        "| " + " | ".join(columns) + " |",
        "| " + " | ".join("---" for _ in columns) + " |",
    ]
    for row in rows[:limit]:
        lines.append("| " + " | ".join(str(row.get(col, "")) for col in columns) + " |")
    return "\n".join(lines)


def write_report(
    path: Path,
    summary: dict[str, Any],
    latest_rows: list[dict[str, Any]],
    supplier_rows: list[dict[str, Any]],
    output_paths: dict[str, Path],
) -> None:
    top_pairs = sorted(latest_rows, key=lambda row: parse_float(row["action_priority_score"]), reverse=True)
    top_suppliers = supplier_rows[:12]
    action_counts = summary["action_counts_latest"]
    zone_counts = summary["decision_zone_counts_latest"]
    lines = [
        "# Supplier Risk KPI",
        "",
        "## Statut",
        "",
        "Cette brique produit un MVP de KPI fournisseur-article-site a partir des sorties de simulation `etudecas`.",
        "Le cadre operationnel est: KPI normalises -> risque probabiliste -> incertitude -> resilience -> decision robuste.",
        "La baseline analysee ne contient pas assez d'incidents observables pour entrainer une probabilite supervisee; les champs `*_proxy` sont donc des proxys explicites.",
        "",
        "## Inputs",
        "",
        f"- Simulation result: `{summary['input_sim_result_dir']}`",
        f"- Sensitivity file: `{summary['input_sensitivity_file']}`",
        f"- Weeks: {summary['week_count']}",
        f"- Suppliers: {summary['supplier_count']}",
        f"- Supplier-item-site pairs: {summary['pair_count']}",
        "",
        "## Qualite evenementielle",
        "",
        f"- MRP order rows: {summary['input_counters']['mrp_order_rows']}",
        f"- Observable late MRP rows: {summary['input_counters']['observable_mrp_late_rows']}",
        f"- Observable short MRP rows: {summary['input_counters']['observable_mrp_short_rows']}",
        "",
        "## Architecture KPI",
        "",
        markdown_table(
            [
                {"bloc": "Performance", "colonnes": "performance_score_current, performance_distance_score", "role": "etat actuel normalise"},
                {"bloc": "Risque", "colonnes": "risk_probability_proxy_4w, action_priority_score", "role": "probabilite x impact x criticite"},
                {"bloc": "Incertitude", "colonnes": "risk_probability_low/high_proxy_4w, uncertainty_pressure", "role": "intervalle de prudence"},
                {"bloc": "Resilience", "colonnes": "resilience_score, time_to_recover_weeks_proxy", "role": "capacite absorption/recuperation"},
                {"bloc": "Dynamique", "colonnes": "change_point_score, early_warning_score", "role": "rupture de regime et signaux faibles"},
                {"bloc": "Decision", "colonnes": "decision_zone, robust_decision", "role": "action robuste"},
            ],
            ["bloc", "colonnes", "role"],
            limit=6,
        ),
        "",
        "## Repartition actions",
        "",
        markdown_table(
            [{"action_level": key, "count": action_counts.get(key, 0)} for key in ["critical", "red", "amber", "green"]],
            ["action_level", "count"],
            limit=4,
        ),
        "",
        "## Zones decisionnelles",
        "",
        markdown_table(
            [{"decision_zone": key, "count": zone_counts.get(key, 0)} for key in ["rouge", "orange", "jaune", "vert"]],
            ["decision_zone", "count"],
            limit=4,
        ),
        "",
        "## Top fournisseurs",
        "",
        markdown_table(
            top_suppliers,
            [
                "supplier_id",
                "supplier_name",
                "pair_count",
                "max_risk_probability_proxy_4w",
                "max_risk_probability_high_proxy_4w",
                "min_resilience_score",
                "max_action_priority_score",
                "worst_decision_zone",
                "top_item_id",
            ],
        ),
        "",
        "## Top couples fournisseur-article-site",
        "",
        markdown_table(
            top_pairs,
            [
                "supplier_id",
                "dst_node_id",
                "item_id",
                "risk_probability_proxy_4w",
                "risk_probability_high_proxy_4w",
                "action_priority_score",
                "resilience_score",
                "early_warning_score",
                "lead_days_q90",
                "decision_zone",
                "robust_decision",
            ],
        ),
        "",
        "## Fichiers",
        "",
        f"- Panel hebdomadaire: `{output_paths['panel']}`",
        f"- KPI couples: `{output_paths['latest']}`",
        f"- KPI fournisseurs: `{output_paths['suppliers']}`",
        f"- Summary JSON: `{output_paths['summary']}`",
        "",
        "## Lecture correcte",
        "",
        "Le score est utile pour prioriser une revue fournisseur, pas pour automatiser seul une decision.",
        "Pour passer a une prediction industrielle, il faut alimenter le panel avec incidents reels ou campagnes Monte Carlo/stress tests, puis calibrer les probabilites avec un split temporel.",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_summary(
    args: argparse.Namespace,
    input_counters: dict[str, int],
    panel_rows: list[dict[str, Any]],
    latest_rows: list[dict[str, Any]],
    supplier_rows: list[dict[str, Any]],
    metadata: dict[str, Any],
    sensitivity_file: Path,
    output_paths: dict[str, Path],
) -> dict[str, Any]:
    action_counts_latest: dict[str, int] = defaultdict(int)
    decision_zone_counts_latest: dict[str, int] = defaultdict(int)
    for row in latest_rows:
        action_counts_latest[str(row["action_level"])] += 1
        decision_zone_counts_latest[str(row["decision_zone"])] += 1
    suppliers = {row["supplier_id"] for row in latest_rows}
    summary = {
        "input_sim_result_dir": str(args.sim_result_dir),
        "input_sensitivity_file": str(sensitivity_file) if sensitivity_file.exists() else "",
        "output_dir": str(args.output_dir),
        "week_count": max((parse_int(row["week_index"]) for row in panel_rows), default=-1) + 1,
        "supplier_count": len(suppliers),
        "pair_count": len(latest_rows),
        "panel_row_count": len(panel_rows),
        "supplier_row_count": len(supplier_rows),
        "input_counters": input_counters,
        "action_counts_latest": dict(action_counts_latest),
        "decision_zone_counts_latest": dict(decision_zone_counts_latest),
        "action_counts_all_weeks": metadata.get("action_counts_all_weeks", {}),
        "decision_zone_counts_all_weeks": metadata.get("decision_zone_counts_all_weeks", {}),
        "normalizers": metadata.get("normalizers", {}),
        "outputs": {key: str(value) for key, value in output_paths.items()},
    }
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--sim-result-dir",
        type=Path,
        default=DEFAULT_SIM_RESULT_DIR,
        help="Simulation result directory containing data/*.csv.",
    )
    parser.add_argument(
        "--sensitivity-dir",
        type=Path,
        default=DEFAULT_SENSITIVITY_DIR,
        help="Directory containing supplier_parameter_recommendations.csv.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="Output directory for KPI artifacts.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    sim_result_dir = args.sim_result_dir.resolve()
    output_dir = args.output_dir.resolve()
    paths = ensure_output_dirs(output_dir)
    sensitivity_file = args.sensitivity_dir / "supplier_parameter_recommendations.csv"

    required_files = [
        data_path(sim_result_dir, "production_supplier_shipments_daily.csv"),
        data_path(sim_result_dir, "production_supplier_capacity_daily.csv"),
        data_path(sim_result_dir, "production_supplier_stocks_daily.csv"),
        data_path(sim_result_dir, "mrp_orders_daily.csv"),
    ]
    missing = [str(path) for path in required_files if not path.exists()]
    if missing:
        raise FileNotFoundError("Missing required simulation CSV files: " + ", ".join(missing))

    pair_week, pair_meta, max_week, counters = load_simulation_tables(sim_result_dir)
    criticality = load_supplier_criticality(data_path(sim_result_dir, "supplier_local_criticality_ranking.csv"))
    sensitivity = load_supplier_sensitivity(sensitivity_file)
    key_stats = compute_key_stats(pair_meta, criticality, sensitivity, max_week)
    panel_rows, latest_rows, metadata = build_week_panel(pair_week, key_stats, max_week)
    supplier_rows = aggregate_supplier_rows(latest_rows)

    latest_rows = sorted(
        latest_rows,
        key=lambda row: (parse_float(row["action_priority_score"]), parse_float(row["expected_exposure_qty_4w_proxy"])),
        reverse=True,
    )

    output_paths = {
        "panel": paths["data"] / "supplier_item_week_panel.csv",
        "latest": paths["data"] / "supplier_item_risk_kpi.csv",
        "suppliers": paths["data"] / "supplier_risk_kpi.csv",
        "summary": paths["summaries"] / "supplier_risk_kpi_summary.json",
        "report": paths["reports"] / "supplier_risk_kpi_report.md",
    }
    write_csv(output_paths["panel"], panel_rows)
    write_csv(output_paths["latest"], latest_rows)
    write_csv(output_paths["suppliers"], supplier_rows)
    summary = build_summary(args, counters, panel_rows, latest_rows, supplier_rows, metadata, sensitivity_file, output_paths)
    output_paths["summary"].write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    write_report(output_paths["report"], summary, latest_rows, supplier_rows, output_paths)

    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
