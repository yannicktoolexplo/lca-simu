#!/usr/bin/env python3
"""
Run a first-pass supply simulation from a simulation-ready graph JSON.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import random
import re
import subprocess
import sys
from collections import defaultdict, deque
from pathlib import Path
from typing import Any

try:
    from .result_paths import data_path, ensure_standard_dirs, map_path, plots_path, report_path, summary_path
except ImportError:
    from result_paths import data_path, ensure_standard_dirs, map_path, plots_path, report_path, summary_path


def to_float(x: Any, default: float = 0.0) -> float:
    try:
        return float(x)
    except (TypeError, ValueError):
        return default


def normalize_unit(unit: Any) -> str:
    s = str(unit or "").strip().upper()
    aliases = {
        "UNIT": "UN",
        "UNITE": "UN",
        "UNITS": "UN",
    }
    return aliases.get(s, s)


def unit_dimension(unit: str) -> str:
    u = normalize_unit(unit)
    if u in {"KG", "G"}:
        return "mass"
    if u in {"UN"}:
        return "count"
    if u in {"M"}:
        return "length"
    return "unknown"


def can_convert_units(from_unit: str, to_unit: str) -> bool:
    f = normalize_unit(from_unit)
    t = normalize_unit(to_unit)
    return f == t or {f, t} <= {"G", "KG"}


def convert_quantity(value: float, from_unit: str, to_unit: str) -> float:
    f = normalize_unit(from_unit)
    t = normalize_unit(to_unit)
    if f == t or not f or not t:
        return value
    if f == "G" and t == "KG":
        return value / 1000.0
    if f == "KG" and t == "G":
        return value * 1000.0
    return value


def normalize_lot_value(value: Any, from_unit: str, to_unit: str) -> float:
    qty = max(0.0, to_float(value, 0.0))
    if qty <= 0:
        return 0.0
    return max(0.0, convert_quantity(qty, from_unit, to_unit))


def process_lot_policy(
    proc: dict[str, Any],
    *,
    out_item: str,
    item_unit_map: dict[str, str],
) -> dict[str, Any]:
    raw = proc.get("lot_sizing") or {}
    if not isinstance(raw, dict):
        raw = {}
    item_uom = normalize_unit(item_unit_map.get(out_item, ""))
    policy_uom = normalize_unit(raw.get("uom") or item_uom)
    fixed_lot_qty = normalize_lot_value(raw.get("fixed_lot_qty"), policy_uom, item_uom)
    min_lot_qty = normalize_lot_value(raw.get("min_lot_qty"), policy_uom, item_uom)
    max_lot_qty = normalize_lot_value(raw.get("max_lot_qty"), policy_uom, item_uom)
    lot_multiple_qty = normalize_lot_value(raw.get("lot_multiple_qty"), policy_uom, item_uom)
    normalization_rule = str(raw.get("normalization_rule") or "")
    if fixed_lot_qty <= 1e-9 and min_lot_qty > 1e-9 and abs(min_lot_qty - max_lot_qty) <= 1e-9:
        fixed_lot_qty = min_lot_qty
        normalization_rule = normalization_rule or "min_equals_max_as_fixed"
    enabled = fixed_lot_qty > 1e-9 or min_lot_qty > 1e-9 or max_lot_qty > 1e-9
    execution_raw = proc.get("lot_execution") or {}
    if not isinstance(execution_raw, dict):
        execution_raw = {}
    max_lots_per_week = max(0.0, to_float(execution_raw.get("max_lots_per_week"), 0.0))
    return {
        "enabled": enabled,
        "fixed_lot_qty": fixed_lot_qty,
        "min_lot_qty": min_lot_qty,
        "max_lot_qty": max_lot_qty,
        "lot_multiple_qty": lot_multiple_qty,
        "uom": item_uom,
        "source": str(raw.get("source") or ""),
        "normalization_rule": normalization_rule,
        "max_lots_per_week": max_lots_per_week,
        "execution_source": str(execution_raw.get("source") or ""),
    }


def launch_campaign_qty(net_requirement_qty: float, lot_policy: dict[str, Any]) -> float:
    requirement = max(0.0, net_requirement_qty)
    if requirement <= 1e-9 or not lot_policy.get("enabled"):
        return requirement
    fixed_lot_qty = max(0.0, to_float(lot_policy.get("fixed_lot_qty"), 0.0))
    min_lot_qty = max(0.0, to_float(lot_policy.get("min_lot_qty"), 0.0))
    max_lot_qty = max(0.0, to_float(lot_policy.get("max_lot_qty"), 0.0))
    lot_multiple_qty = max(0.0, to_float(lot_policy.get("lot_multiple_qty"), 0.0))
    if fixed_lot_qty > 1e-9:
        return math.ceil(requirement / fixed_lot_qty) * fixed_lot_qty
    campaign_qty = requirement
    if min_lot_qty > 1e-9:
        campaign_qty = max(campaign_qty, min_lot_qty)
    if lot_multiple_qty > 1e-9:
        campaign_qty = math.ceil(campaign_qty / lot_multiple_qty) * lot_multiple_qty
    if max_lot_qty > 1e-9:
        effective_max = max_lot_qty
        if lot_multiple_qty > 1e-9:
            effective_max = math.floor(max_lot_qty / lot_multiple_qty) * lot_multiple_qty
            if effective_max <= 1e-9:
                effective_max = max_lot_qty
        campaign_qty = min(campaign_qty, effective_max)
    return max(0.0, campaign_qty)


def lot_reference_qty(lot_policy: dict[str, Any]) -> float:
    fixed_lot_qty = max(0.0, to_float(lot_policy.get("fixed_lot_qty"), 0.0))
    if fixed_lot_qty > 1e-9:
        return fixed_lot_qty
    max_lot_qty = max(0.0, to_float(lot_policy.get("max_lot_qty"), 0.0))
    if max_lot_qty > 1e-9:
        return max_lot_qty
    min_lot_qty = max(0.0, to_float(lot_policy.get("min_lot_qty"), 0.0))
    if min_lot_qty > 1e-9:
        return min_lot_qty
    lot_multiple_qty = max(0.0, to_float(lot_policy.get("lot_multiple_qty"), 0.0))
    if lot_multiple_qty > 1e-9:
        return lot_multiple_qty
    return 0.0


def campaign_lot_count(campaign_qty: float, lot_policy: dict[str, Any]) -> int:
    qty = max(0.0, to_float(campaign_qty, 0.0))
    if qty <= 1e-9:
        return 0
    ref_qty = lot_reference_qty(lot_policy)
    if ref_qty <= 1e-9:
        return 0
    return max(0, int(math.ceil((qty / ref_qty) - 1e-9)))


def limit_campaign_qty_by_weekly_lots(
    campaign_qty: float,
    lot_policy: dict[str, Any],
    available_lot_starts: int,
) -> float:
    qty = max(0.0, to_float(campaign_qty, 0.0))
    if qty <= 1e-9:
        return 0.0
    allowed_lots = max(0, int(available_lot_starts))
    if allowed_lots <= 0:
        return 0.0
    ref_qty = lot_reference_qty(lot_policy)
    if ref_qty <= 1e-9:
        return qty
    fixed_lot_qty = max(0.0, to_float(lot_policy.get("fixed_lot_qty"), 0.0))
    min_lot_qty = max(0.0, to_float(lot_policy.get("min_lot_qty"), 0.0))
    max_lot_qty = max(0.0, to_float(lot_policy.get("max_lot_qty"), 0.0))
    capped_qty = min(qty, allowed_lots * ref_qty)
    if fixed_lot_qty > 1e-9:
        fixed_lots = max(0, int(math.floor((capped_qty / fixed_lot_qty) + 1e-9)))
        return fixed_lots * fixed_lot_qty
    if max_lot_qty > 1e-9:
        capped_qty = min(capped_qty, max_lot_qty)
    if min_lot_qty > 1e-9 and capped_qty + 1e-9 < min_lot_qty:
        return 0.0
    return max(0.0, capped_qty)


def infer_item_unit_map(nodes: list[dict[str, Any]], edges: list[dict[str, Any]]) -> dict[str, str]:
    votes: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))

    for e in edges:
        unit = normalize_unit(((e.get("order_terms") or {}).get("quantity_unit")))
        if not unit:
            continue
        for item_id in (e.get("items") or []):
            votes[str(item_id)][unit] += 3

    for n in nodes:
        for p in (n.get("processes") or []):
            for inp in (p.get("inputs") or []):
                item_id = str(inp.get("item_id"))
                unit = normalize_unit(inp.get("ratio_unit"))
                if item_id and unit:
                    votes[item_id][unit] += 1

    priority = {"KG": 4, "G": 3, "UN": 2, "M": 1}
    out: dict[str, str] = {}
    for item_id, cnt in votes.items():
        best = sorted(cnt.items(), key=lambda x: (-x[1], -priority.get(x[0], 0), x[0]))[0][0]
        out[item_id] = best
    return out


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run first-pass supply simulation.")
    parser.add_argument(
        "--input",
        default="etudecas/simulation_prep/result/supply_graph_poc_simulation_ready.json",
        help="Simulation-ready graph JSON.",
    )
    parser.add_argument(
        "--output-dir",
        default="etudecas/simulation/result",
        help="Directory where simulation outputs are written.",
    )
    parser.add_argument(
        "--scenario-id",
        default="scn:BASE",
        help="Scenario id to simulate.",
    )
    parser.add_argument(
        "--days",
        type=int,
        default=0,
        help="Simulation horizon in days (default: scenario horizon). Set 0 to use scenario horizon.",
    )
    parser.add_argument(
        "--warmup-days",
        type=int,
        default=None,
        help="Warm-up days run before the measured horizon. Defaults to scenario policy warmup_days or 0.",
    )
    parser.add_argument(
        "--map-script",
        default="etudecas/affichage_supply_script/build_supplychain_worldmap.py",
        help="Path to map builder script.",
    )
    parser.add_argument(
        "--map-output",
        default="",
        help="Optional path to generated hover-map HTML. Defaults inside <output-dir>/maps/.",
    )
    parser.add_argument(
        "--skip-map",
        action="store_true",
        help="Skip map HTML generation after simulation.",
    )
    parser.add_argument(
        "--skip-plots",
        action="store_true",
        help="Skip PNG plot generation.",
    )
    parser.add_argument(
        "--output-profile",
        choices=["full", "compact"],
        default="compact",
        help="Result output volume: compact keeps only files needed for baseline review and maps.",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed used by stochastic replenishment (default: 42).",
    )
    parser.add_argument(
        "--stochastic-lead-times",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Enable stochastic lead times sampled from lane metadata (default: enabled).",
    )
    return parser.parse_args()


def profile_value(profile: list[dict[str, Any]], day: int) -> float:
    if not profile:
        return 0.0
    step_candidates: list[tuple[int, float]] = []
    for p in profile:
        if not isinstance(p, dict):
            continue
        ptype = str(p.get("type", "constant"))
        repeat_period_days = int(to_float(p.get("repeat_period_days"), 0.0))
        eval_day = day
        if repeat_period_days > 0:
            eval_day = day % repeat_period_days
        if ptype == "constant":
            return to_float(p.get("value"), 0.0)
        if ptype == "step":
            start = int(to_float(p.get("start_day"), 0.0))
            val = to_float(p.get("value"), 0.0)
            if eval_day >= start:
                step_candidates.append((start, val))
        if ptype == "piecewise":
            points = p.get("points") or []
            for pt in points:
                if not isinstance(pt, dict):
                    continue
                t = int(to_float(pt.get("t"), -1))
                v = to_float(pt.get("value"), 0.0)
                if eval_day >= t >= 0:
                    step_candidates.append((t, v))
    if step_candidates:
        step_candidates.sort(key=lambda x: x[0])
        return step_candidates[-1][1]
    return 0.0


def profile_window_average(profile: list[dict[str, Any]], day: int, window_days: int) -> float:
    window_days = max(1, int(window_days))
    if window_days <= 1:
        return profile_value(profile, day)
    return sum(profile_value(profile, day + offset) for offset in range(window_days)) / float(window_days)


def demand_targets_for_day(
    demand_profiles: dict[tuple[str, str], list[dict[str, Any]]],
    day: int,
    *,
    window_days: int = 1,
) -> dict[tuple[str, str], float]:
    return {
        pair: max(0.0, profile_window_average(profile, day, window_days))
        for pair, profile in demand_profiles.items()
    }


def choose_scenario(data: dict[str, Any], scenario_id: str) -> dict[str, Any]:
    scenarios = data.get("scenarios", []) or []
    for scn in scenarios:
        if str(scn.get("id")) == scenario_id:
            return scn
    return scenarios[0] if scenarios else {"id": scenario_id, "demand": []}


def lane_records(
    edges: list[dict[str, Any]],
    economic_policy: dict[str, float] | None = None,
) -> tuple[list[dict[str, Any]], dict[tuple[str, str], list[dict[str, Any]]]]:
    economic_policy = economic_policy or {}
    transport_floor = max(0.0, to_float(economic_policy.get("transport_cost_floor_per_unit"), 0.02))
    transport_per_km = max(0.0, to_float(economic_policy.get("transport_cost_per_km_per_unit"), 0.00008))
    purchase_floor = max(0.0, to_float(economic_policy.get("purchase_cost_floor_per_unit"), 0.01))
    transport_realism_multiplier = max(0.1, to_float(economic_policy.get("transport_cost_realism_multiplier"), 1.0))
    purchase_realism_multiplier = max(0.1, to_float(economic_policy.get("purchase_cost_realism_multiplier"), 1.0))
    lanes: list[dict[str, Any]] = []
    lanes_by_dest_item: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for e in edges:
        src = str(e.get("from"))
        dst = str(e.get("to"))
        lead = e.get("lead_time") or {}
        lead_days = int(round(max(1.0, to_float((lead or {}).get("mean"), 1.0))))
        lead_days_mean = max(1.0, to_float((lead or {}).get("mean"), 1.0))
        lead_stages = int(round(max(1.0, to_float((lead or {}).get("stages"), 1.0))))
        lead_time_type = str((lead or {}).get("type", "constant"))
        distance_km = max(0.0, to_float(e.get("distance_km"), 0.0))
        tc = e.get("transport_cost") or {}
        explicit_transport_cost = max(0.0, to_float((tc or {}).get("value"), 0.0))
        fallback_transport_cost = max(transport_floor, distance_km * transport_per_km)
        # Most lanes in this model have a default 0 transport_cost, so force a realistic floor by distance.
        cost = (explicit_transport_cost if explicit_transport_cost > 0 else fallback_transport_cost) * transport_realism_multiplier
        ot = e.get("order_terms") or {}
        sell_price = to_float((ot or {}).get("sell_price"), 0.0)
        price_base = to_float((ot or {}).get("price_base"), 1.0)
        if price_base <= 0:
            price_base = 1.0
        priced_unit_purchase_cost = max(0.0, sell_price / price_base)
        if priced_unit_purchase_cost > 0.0 and not bool((ot or {}).get("is_default")):
            unit_purchase_cost = priced_unit_purchase_cost * purchase_realism_multiplier
            purchase_cost_is_fallback = False
        else:
            unit_purchase_cost = max(purchase_floor, priced_unit_purchase_cost) * purchase_realism_multiplier
            purchase_cost_is_fallback = True
        order_unit = normalize_unit((ot or {}).get("quantity_unit"))
        attrs = e.get("attrs") or {}
        standard_order_qty_raw = max(0.0, to_float(attrs.get("standard_order_qty"), 0.0))
        standard_order_uom = normalize_unit(attrs.get("standard_order_uom") or order_unit)
        if standard_order_qty_raw > 0 and can_convert_units(standard_order_uom, order_unit):
            standard_order_qty = convert_quantity(standard_order_qty_raw, standard_order_uom, order_unit)
        else:
            standard_order_qty = standard_order_qty_raw
        service_level = e.get("service_level") or {}
        reliability = to_float(
            service_level.get("otif", e.get("otif", 1.0)),
            1.0,
        )
        reliability = max(0.01, min(1.0, reliability))
        supply_order_frequency = (ot.get("supply_order_frequency") or {})
        order_frequency_days = int(
            round(max(1.0, to_float((supply_order_frequency or {}).get("value"), 1.0)))
        )
        delay_step_limit = int(round(max(1.0, to_float(((e.get("delay_step_limit") or {}).get("value")), 999.0))))
        for item_id in (e.get("items") or []):
            standard_order_qty_note = ""
            if (
                str(item_id) == "item:708073"
                and src == "SDC-VD0520115A"
                and dst == "M-1430"
                and standard_order_qty >= 1_000_000.0
                and (order_unit or standard_order_uom) == "KG"
            ):
                # The source FIA row carries 5,000,000 in a context where the
                # quantity is understood as grams. Convert it to 5,000 KG so the
                # hard-lot policy remains realistic for the BOM demand scale.
                standard_order_qty_note = (
                    f"overridden from {standard_order_qty:g} g-equivalent to 5000 KG "
                    "because this source lot is interpreted as grams, not kilograms"
                )
                standard_order_qty = 5000.0
            lane = {
                "edge_id": str(e.get("id")),
                "src": src,
                "dst": dst,
                "item_id": str(item_id),
                "lead_days": lead_days,
                "lead_days_mean": lead_days_mean,
                "lead_stages": lead_stages,
                "lead_time_type": lead_time_type,
                "order_frequency_days": order_frequency_days,
                "delay_step_limit": delay_step_limit,
                "unit_transport_cost": cost,
                "unit_purchase_cost": unit_purchase_cost,
                "raw_purchase_cost": priced_unit_purchase_cost,
                "purchase_cost_is_fallback": purchase_cost_is_fallback,
                "raw_transport_cost": explicit_transport_cost,
                "transport_cost_is_fallback": explicit_transport_cost <= 0,
                "reliability": reliability,
                "availability_profile": e.get("availability_profile") or [],
                "standard_order_qty": standard_order_qty,
                "standard_order_uom": order_unit or standard_order_uom,
                "standard_order_qty_note": standard_order_qty_note,
            }
            lanes.append(lane)
            lanes_by_dest_item[(dst, str(item_id))].append(lane)

    def mrp_split_shares(count: int) -> list[float]:
        if count <= 0:
            return []
        if count == 1:
            return [1.0]
        if count == 2:
            return [0.7, 0.3]
        if count == 3:
            return [0.7, 0.2, 0.1]
        tail = 0.1 / float(count - 2)
        return [0.7, 0.2] + [tail] * (count - 2)

    for key, values in lanes_by_dest_item.items():
        values.sort(key=lambda x: (x["unit_transport_cost"], x["lead_days"], x["src"]))
        shares = mrp_split_shares(len(values))
        for rank, (lane, share) in enumerate(zip(values, shares), start=1):
            lane["mrp_share"] = share
            lane["mrp_rank"] = rank
        lanes_by_dest_item[key] = values
    return lanes, lanes_by_dest_item


def node_review_period_days(node: dict[str, Any], default: int = 7) -> int:
    sim_policy = ((node.get("policies") or {}).get("simulation_policy") or {})
    return int(round(max(1.0, to_float(sim_policy.get("review_period_days"), float(default)))))


def process_output_capacity_by_item(
    node: dict[str, Any],
    item_unit_map: dict[str, str],
) -> dict[str, float]:
    out: dict[str, float] = defaultdict(float)
    for proc in (node.get("processes") or []):
        cap = max(0.0, to_float(((proc.get("capacity") or {}).get("max_rate")), 0.0))
        if cap <= 0:
            continue
        for output in (proc.get("outputs") or []):
            item_id = str(output.get("item_id") or "")
            if not item_id:
                continue
            output_uom = str(output.get("uom") or "")
            output_unit = normalize_unit(output_uom.split("/", 1)[0] if "/" in output_uom else output_uom)
            item_unit = normalize_unit(item_unit_map.get(item_id, output_unit))
            value = cap
            if output_unit and item_unit and can_convert_units(output_unit, item_unit):
                value = convert_quantity(cap, output_unit, item_unit)
            out[item_id] += max(0.0, value)
    return dict(out)


def lane_availability_multiplier(lane: dict[str, Any], day: int) -> float:
    mult = 1.0
    for window in lane.get("availability_profile") or []:
        if not isinstance(window, dict):
            continue
        start = int(round(to_float(window.get("start_day"), 0.0)))
        end = int(round(to_float(window.get("end_day"), start)))
        if start <= day <= end:
            mult *= max(0.0, to_float(window.get("multiplier"), 1.0))
    return max(0.0, mult)


def sample_lead_days(lane: dict[str, Any], rng: random.Random, stochastic: bool) -> int:
    deterministic = int(round(max(1.0, to_float(lane.get("lead_days"), 1.0))))
    if not stochastic:
        return deterministic

    mean = max(1.0, to_float(lane.get("lead_days_mean"), deterministic))
    stages = int(round(max(1.0, to_float(lane.get("lead_stages"), 1.0))))
    lt_type = str(lane.get("lead_time_type", "constant")).lower()

    sampled = mean
    if "erlang" in lt_type:
        sampled = rng.gammavariate(stages, mean / stages)
    elif "constant" not in lt_type:
        sigma = max(0.25, 0.30 * mean)
        sampled = rng.gauss(mean, sigma)

    sampled_days = int(max(1, math.ceil(sampled)))
    delay_limit = int(round(max(1.0, to_float(lane.get("delay_step_limit"), 999.0))))
    return min(sampled_days, delay_limit)


def lead_time_cover_days(lane: dict[str, Any], stochastic: bool) -> int:
    """
    Return conservative lead-time coverage in days for stock sizing.
    With stochastic lead-times, use an approximate p95.
    """
    mean = max(1.0, to_float(lane.get("lead_days_mean"), lane.get("lead_days", 1.0)))
    if not stochastic:
        cover = int(round(max(1.0, to_float(lane.get("lead_days"), mean))))
    else:
        stages = max(1.0, to_float(lane.get("lead_stages"), 1.0))
        lt_type = str(lane.get("lead_time_type", "constant")).lower()
        if "erlang" in lt_type:
            # Erlang(k, theta): sd = mean / sqrt(k)
            sd = mean / math.sqrt(stages)
        elif "constant" in lt_type:
            sd = 0.0
        else:
            # Fallback dispersion used in sampling branch.
            sd = max(0.25, 0.30 * mean)
        cover = int(math.ceil(mean + 1.65 * sd))
    delay_limit = int(round(max(1.0, to_float(lane.get("delay_step_limit"), 999.0))))
    return max(1, min(cover, delay_limit))


def propagate_demand_rates(
    demand_target_daily: dict[tuple[str, str], float],
    lanes: list[dict[str, Any]],
) -> dict[tuple[str, str], float]:
    """
    Propagate customer demand signal upstream on same item lanes.
    """
    upstream: dict[tuple[str, str], list[tuple[str, str]]] = defaultdict(list)
    for lane in lanes:
        src_pair = (str(lane["src"]), str(lane["item_id"]))
        dst_pair = (str(lane["dst"]), str(lane["item_id"]))
        upstream[dst_pair].append(src_pair)

    signal: dict[tuple[str, str], float] = defaultdict(float)
    queue: deque[tuple[str, str]] = deque()
    for pair, val in demand_target_daily.items():
        d0 = max(0.0, to_float(val, 0.0))
        if d0 <= 0:
            continue
        if d0 > signal[pair]:
            signal[pair] = d0
            queue.append(pair)

    while queue:
        dst_pair = queue.popleft()
        d0 = signal[dst_pair]
        for src_pair in upstream.get(dst_pair, []):
            if d0 > signal[src_pair] + 1e-9:
                signal[src_pair] = d0
                queue.append(src_pair)

    return dict(signal)


def build_process_input_requirements_by_output_pair(
    nodes: list[dict[str, Any]],
    item_unit_map: dict[str, str],
) -> dict[tuple[str, str], list[tuple[tuple[str, str], float]]]:
    requirements: dict[tuple[str, str], list[tuple[tuple[str, str], float]]] = defaultdict(list)
    for node in nodes:
        node_id = str(node.get("id"))
        for proc in node.get("processes") or []:
            batch_size = to_float(proc.get("batch_size"), 1000.0)
            if batch_size <= 0:
                batch_size = 1000.0
            output_items = [
                str((out or {}).get("item_id"))
                for out in (proc.get("outputs") or [])
                if (out or {}).get("item_id") is not None
            ]
            if not output_items:
                continue
            input_requirements: list[tuple[tuple[str, str], float]] = []
            for inp in proc.get("inputs") or []:
                in_item = str((inp or {}).get("item_id"))
                if not in_item:
                    continue
                ratio = to_float((inp or {}).get("ratio_per_batch"), 0.0)
                if ratio <= 0:
                    continue
                input_unit = normalize_unit((inp or {}).get("ratio_unit"))
                item_unit = normalize_unit(item_unit_map.get(in_item, input_unit))
                req_per_output_unit = convert_quantity(ratio / batch_size, input_unit, item_unit)
                if req_per_output_unit > 0:
                    input_requirements.append(((node_id, in_item), req_per_output_unit))
            if not input_requirements:
                continue
            for out_item in output_items:
                requirements[(node_id, out_item)].extend(input_requirements)
    return dict(requirements)


def propagate_supply_demand_rates(
    demand_target_daily: dict[tuple[str, str], float],
    lanes: list[dict[str, Any]],
    process_input_requirements_by_output_pair: dict[tuple[str, str], list[tuple[tuple[str, str], float]]],
) -> dict[tuple[str, str], float]:
    """
    Propagate demand upstream through same-item lanes and through production BOMs.

    This is used for MRP sizing: a finished-good demand signal creates component
    requirements at the producing site, then those component requirements propagate
    to upstream suppliers on the corresponding item lanes.
    """
    adjacency: dict[tuple[str, str], list[tuple[tuple[str, str], float]]] = defaultdict(list)
    for lane in lanes:
        src_pair = (str(lane["src"]), str(lane["item_id"]))
        dst_pair = (str(lane["dst"]), str(lane["item_id"]))
        adjacency[dst_pair].append((src_pair, 1.0))
    for output_pair, input_reqs in process_input_requirements_by_output_pair.items():
        for input_pair, req_per_output_unit in input_reqs:
            if req_per_output_unit > 0:
                adjacency[output_pair].append((input_pair, req_per_output_unit))

    signal: dict[tuple[str, str], float] = defaultdict(float)
    propagated_by_edge: dict[tuple[tuple[str, str], tuple[str, str], float], float] = defaultdict(float)
    queue: deque[tuple[str, str]] = deque()
    for pair, val in demand_target_daily.items():
        qty = max(0.0, to_float(val, 0.0))
        if qty <= 0:
            continue
        signal[pair] += qty
        queue.append(pair)

    guard = 0
    guard_limit = max(1000, 20 * (len(adjacency) + sum(len(v) for v in adjacency.values()) + 1))
    while queue:
        guard += 1
        if guard > guard_limit:
            break
        pair = queue.popleft()
        source_qty = signal.get(pair, 0.0)
        if source_qty <= 0:
            continue
        for upstream_pair, multiplier in adjacency.get(pair, []):
            if multiplier <= 0:
                continue
            edge_key = (pair, upstream_pair, round(multiplier, 12))
            already_propagated = propagated_by_edge.get(edge_key, 0.0)
            delta = source_qty - already_propagated
            if delta <= 1e-9:
                continue
            propagated_by_edge[edge_key] = source_qty
            signal[upstream_pair] += delta * multiplier
            queue.append(upstream_pair)

    return dict(signal)


def lotified_mps_component_signal(
    output_demand_signal: dict[tuple[str, str], float],
    *,
    day: int,
    process_input_requirements_by_output_pair: dict[tuple[str, str], list[tuple[tuple[str, str], float]]],
    production_lot_policy_by_pair: dict[tuple[str, str], dict[str, Any]],
    process_capacity_by_output_pair: dict[tuple[str, str], float],
    mps_open_campaign_qty_by_pair: dict[tuple[str, str], float],
    mps_started_lots_by_week_pair: dict[tuple[int, tuple[str, str]], int],
) -> tuple[dict[tuple[str, str], float], dict[tuple[str, str], float]]:
    """
    Build component demand from a lotified master production schedule.

    The input is the output demand seen by production nodes. For each produced
    output, this function applies the same lot/campaign rules used by execution,
    then explodes the planned production through the BOM. If an input is itself
    produced internally, its requirement is queued as a demand for that upstream
    process before non-produced component demand is returned.
    """
    component_signal: dict[tuple[str, str], float] = defaultdict(float)
    planned_output_signal: dict[tuple[str, str], float] = defaultdict(float)
    pending: deque[tuple[str, str]] = deque()
    pending_qty: dict[tuple[str, str], float] = defaultdict(float)
    produced_pairs = set(process_input_requirements_by_output_pair)
    for pair, qty in output_demand_signal.items():
        qty = max(0.0, to_float(qty, 0.0))
        if qty <= 1e-9:
            continue
        pending_qty[pair] += qty
        pending.append(pair)

    guard = 0
    guard_limit = max(1000, 10 * (len(produced_pairs) + len(output_demand_signal) + 1))
    while pending:
        guard += 1
        if guard > guard_limit:
            break
        out_pair = pending.popleft()
        required_qty = pending_qty.pop(out_pair, 0.0)
        if required_qty <= 1e-9:
            continue
        input_requirements = process_input_requirements_by_output_pair.get(out_pair)
        if not input_requirements:
            continue

        lot_policy = production_lot_policy_by_pair.get(out_pair, {"enabled": False})
        cap_qty = max(0.0, process_capacity_by_output_pair.get(out_pair, 0.0))
        campaign_remaining_start_qty = max(0.0, mps_open_campaign_qty_by_pair.get(out_pair, 0.0))
        planned_qty = required_qty
        week_index = int(day // 7)
        week_key = (week_index, out_pair)
        if lot_policy.get("enabled"):
            if campaign_remaining_start_qty <= 1e-9 and required_qty > 1e-9:
                campaign_requested_qty = launch_campaign_qty(required_qty, lot_policy)
                campaign_started_qty = campaign_requested_qty
                weekly_lot_limit = max(0, int(math.floor(to_float(lot_policy.get("max_lots_per_week"), 0.0))))
                if weekly_lot_limit > 0:
                    started_lots = int(mps_started_lots_by_week_pair.get(week_key, 0))
                    available_lots = max(0, weekly_lot_limit - started_lots)
                    campaign_started_qty = limit_campaign_qty_by_weekly_lots(
                        campaign_requested_qty,
                        lot_policy,
                        available_lots,
                    )
                    mps_started_lots_by_week_pair[week_key] = (
                        started_lots + campaign_lot_count(campaign_started_qty, lot_policy)
                    )
                campaign_remaining_start_qty = campaign_started_qty
                mps_open_campaign_qty_by_pair[out_pair] = campaign_started_qty
            planned_qty = campaign_remaining_start_qty

        if cap_qty > 1e-9:
            planned_qty = min(planned_qty, cap_qty)
        planned_qty = max(0.0, planned_qty)
        if planned_qty <= 1e-9:
            continue
        if lot_policy.get("enabled"):
            mps_open_campaign_qty_by_pair[out_pair] = max(0.0, campaign_remaining_start_qty - planned_qty)

        planned_output_signal[out_pair] += planned_qty
        for input_pair, req_per_output_unit in input_requirements:
            input_qty = planned_qty * max(0.0, req_per_output_unit)
            if input_qty <= 1e-9:
                continue
            if input_pair in produced_pairs:
                pending_qty[input_pair] += input_qty
                pending.append(input_pair)
            else:
                component_signal[input_pair] += input_qty

    return dict(component_signal), dict(planned_output_signal)


def pair_label(node_id: str, item_id: str) -> str:
    return f"{node_id} | {item_id}"


def scenario_policy_value(scenario: dict[str, Any], key: str, default: float) -> float:
    raw = scenario.get(key, None)
    if raw is None:
        policy = scenario.get("inventory_policy") or {}
        raw = policy.get(key, None)
    return to_float(raw, default)


def scenario_policy_bool(scenario: dict[str, Any], key: str, default: bool) -> bool:
    raw = scenario.get(key, None)
    if raw is None:
        policy = scenario.get("inventory_policy") or {}
        raw = policy.get(key, None)
    if raw is None:
        return default
    if isinstance(raw, bool):
        return raw
    return str(raw).strip().lower() in {"1", "true", "yes", "y", "on"}


def scenario_policy_dict(scenario: dict[str, Any], key: str) -> dict[str, Any]:
    raw = scenario.get(key, None)
    if raw is None:
        policy = scenario.get("inventory_policy") or {}
        raw = policy.get(key, None)
    return raw if isinstance(raw, dict) else {}


def scenario_initialization_policy(
    scenario: dict[str, Any],
    *,
    review_period_days: int,
    safety_stock_days: float,
) -> dict[str, Any]:
    raw = scenario.get("initialization_policy")
    if not isinstance(raw, dict):
        raw = {}
    safety_days = max(0, int(math.ceil(safety_stock_days)))
    review_days = max(1, int(review_period_days))
    mode = str(raw.get("mode", "legacy_bootstrap")).strip().lower() or "legacy_bootstrap"
    if mode not in {"legacy_bootstrap", "explicit_state"}:
        mode = "legacy_bootstrap"
    return {
        "mode": mode,
        "state_scale": max(0.0, to_float(raw.get("state_scale"), 1.0)),
        "factory_input_on_hand_days": max(
            0.0,
            to_float(raw.get("factory_input_on_hand_days"), float(max(review_days + safety_days, 10))),
        ),
        "supplier_output_on_hand_days": max(
            0.0,
            to_float(raw.get("supplier_output_on_hand_days"), float(max(review_days + safety_days, 10))),
        ),
        "distribution_center_on_hand_days": max(
            0.0,
            to_float(raw.get("distribution_center_on_hand_days"), float(max(review_days + safety_days + 2, 12))),
        ),
        "customer_on_hand_days": max(
            0.0,
            to_float(raw.get("customer_on_hand_days"), 0.0),
        ),
        "seed_in_transit": (
            raw.get("seed_in_transit")
            if isinstance(raw.get("seed_in_transit"), bool)
            else str(raw.get("seed_in_transit", "true")).strip().lower() in {"1", "true", "yes", "y", "on"}
        ),
        "in_transit_fill_ratio": max(
            0.0,
            to_float(raw.get("in_transit_fill_ratio"), 1.0),
        ),
        "seed_estimated_source_pipeline": (
            raw.get("seed_estimated_source_pipeline")
            if isinstance(raw.get("seed_estimated_source_pipeline"), bool)
            else str(raw.get("seed_estimated_source_pipeline", "true")).strip().lower() in {"1", "true", "yes", "y", "on"}
        ),
        "restore_opening_stock_after_warmup": (
            raw.get("restore_opening_stock_after_warmup")
            if isinstance(raw.get("restore_opening_stock_after_warmup"), bool)
            else str(raw.get("restore_opening_stock_after_warmup", "false")).strip().lower()
            in {"1", "true", "yes", "y", "on"}
        ),
        "seed_open_orders_from_january_snapshot": (
            raw.get("seed_open_orders_from_january_snapshot")
            if isinstance(raw.get("seed_open_orders_from_january_snapshot"), bool)
            else str(raw.get("seed_open_orders_from_january_snapshot", "false")).strip().lower()
            in {"1", "true", "yes", "y", "on"}
        ),
        "opening_open_orders_horizon_days": max(
            0,
            int(round(max(0.0, to_float(raw.get("opening_open_orders_horizon_days"), 0.0)))),
        ),
        "opening_open_orders_demand_multiplier": max(
            0.0,
            to_float(raw.get("opening_open_orders_demand_multiplier"), 1.0),
        ),
        "use_bom_demand_signal_for_mrp": (
            raw.get("use_bom_demand_signal_for_mrp")
            if isinstance(raw.get("use_bom_demand_signal_for_mrp"), bool)
            else str(raw.get("use_bom_demand_signal_for_mrp", "false")).strip().lower()
            in {"1", "true", "yes", "y", "on"}
        ),
        "mrp_demand_signal_source": (
            str(raw.get("mrp_demand_signal_source") or "demand").strip().lower()
            if str(raw.get("mrp_demand_signal_source") or "demand").strip().lower()
            in {"demand", "mps_lotified"}
            else "demand"
        ),
        "mrp_demand_signal_smoothing_days": max(
            1,
            int(round(max(1.0, to_float(raw.get("mrp_demand_signal_smoothing_days"), 1.0)))),
        ),
        "mrp_static_fallback_for_propagated_pairs": (
            raw.get("mrp_static_fallback_for_propagated_pairs")
            if isinstance(raw.get("mrp_static_fallback_for_propagated_pairs"), bool)
            else str(raw.get("mrp_static_fallback_for_propagated_pairs", "true")).strip().lower()
            in {"1", "true", "yes", "y", "on"}
        ),
        "mrp_enforce_physical_safety_floor": (
            raw.get("mrp_enforce_physical_safety_floor")
            if isinstance(raw.get("mrp_enforce_physical_safety_floor"), bool)
            else str(raw.get("mrp_enforce_physical_safety_floor", "false")).strip().lower()
            in {"1", "true", "yes", "y", "on"}
        ),
        "soft_safety_time_stock_target_factor": max(
            0.0,
            min(1.0, to_float(raw.get("soft_safety_time_stock_target_factor"), 0.75)),
        ),
    }


def seed_lane_pipeline_uniform(
    pipeline: dict[int, list[tuple[str, str, float, str]]],
    in_transit: dict[tuple[str, str], float],
    *,
    dst: str,
    item_id: str,
    qty: float,
    edge_id: str,
    lead_days: int,
) -> None:
    if qty <= 1e-9:
        return
    lead_days = max(1, int(lead_days))
    per_day = qty / float(lead_days)
    for offset in range(lead_days):
        pipeline[offset].append((dst, item_id, per_day, edge_id))
    in_transit[(dst, item_id)] += qty


def seed_external_pipeline_uniform(
    pipeline: dict[int, list[tuple[str, str, float]]],
    in_transit: dict[tuple[str, str], float],
    *,
    node_id: str,
    item_id: str,
    qty: float,
    lead_days: int,
) -> None:
    if qty <= 1e-9:
        return
    lead_days = max(1, int(lead_days))
    per_day = qty / float(lead_days)
    for offset in range(lead_days):
        pipeline[offset].append((node_id, item_id, per_day))
    in_transit[(node_id, item_id)] += qty


def seed_open_orders_from_opening_snapshot(
    pipeline: dict[int, list[tuple[str, str, float, str]]],
    in_transit: dict[tuple[str, str], float],
    *,
    lanes: list[dict[str, Any]],
    lanes_by_dest_item: dict[tuple[str, str], list[dict[str, Any]]],
    opening_stock_source_snapshot: dict[tuple[str, str], float],
    pair_mrp_safety_time_days: dict[tuple[str, str], float],
    pair_mrp_safety_stock_qty: dict[tuple[str, str], float],
    demand_profiles: dict[tuple[str, str], list[dict[str, Any]]],
    required_daily_input_by_pair: dict[tuple[str, str], float],
    process_input_requirements_by_output_pair: dict[tuple[str, str], list[tuple[tuple[str, str], float]]],
    opening_open_orders_demand_multiplier: float,
    demand_pairs: list[tuple[str, str]],
    stochastic_lead_times: bool,
    horizon_cap_days: int,
    initialization_pipeline_rows: list[dict[str, Any]],
    assumptions_ledger_rows: list[dict[str, Any]],
) -> tuple[float, list[dict[str, Any]], dict[tuple[str, str], int]]:
    if horizon_cap_days <= 0:
        return 0.0, [], {}

    inbound_pairs = sorted(lanes_by_dest_item.keys())
    if not inbound_pairs:
        return 0.0, [], {}

    daily_signals_by_pair: dict[tuple[str, str], list[float]] = {
        pair: [0.0] * horizon_cap_days for pair in inbound_pairs
    }
    safety_daily_signals_by_pair: dict[tuple[str, str], list[float]] = {
        pair: [0.0] * horizon_cap_days for pair in inbound_pairs
    }
    for day in range(horizon_cap_days):
        demand_target_today = {
            pair: max(0.0, profile_value(profile, day))
            for pair, profile in demand_profiles.items()
        }
        propagated_demand_today = propagate_supply_demand_rates(
            demand_target_today,
            lanes,
            process_input_requirements_by_output_pair,
        )
        for pair in inbound_pairs:
            dynamic_req = max(0.0, propagated_demand_today.get(pair, 0.0))
            static_req = max(0.0, required_daily_input_by_pair.get(pair, 0.0))
            daily_signals_by_pair[pair][day] = (
                dynamic_req * opening_open_orders_demand_multiplier
                if dynamic_req > 1e-9
                else static_req
            )
            safety_daily_signals_by_pair[pair][day] = max(
                static_req,
                dynamic_req if dynamic_req > 1e-9 else 0.0,
            )

    seeded_total_qty = 0.0
    open_order_rows: list[dict[str, Any]] = []
    bridge_days_by_pair: dict[tuple[str, str], int] = {}

    for pair in inbound_pairs:
        lane_list = list(lanes_by_dest_item.get(pair, []))
        if not lane_list:
            continue
        opening_qty = max(0.0, opening_stock_source_snapshot.get(pair, 0.0))
        safety_qty = 0.0
        safety_days = int(math.ceil(max(0.0, pair_mrp_safety_time_days.get(pair, 0.0))))
        min_lead_days = min(max(1, int(to_float(lane.get("lead_days"), 1.0))) for lane in lane_list)
        bridge_horizon_days = max(1, min(horizon_cap_days, min_lead_days + safety_days))
        bridge_days_by_pair[pair] = bridge_horizon_days
        daily_signals = daily_signals_by_pair.get(pair, [])
        safety_daily_signals = safety_daily_signals_by_pair.get(pair, daily_signals)
        opening_safety_floor_qty = max(
            safety_qty,
            sum(max(0.0, safety_daily_signals[day]) for day in range(min(safety_days, len(safety_daily_signals)))),
        )
        first_day_need_qty = max(0.0, safety_daily_signals[0]) if safety_daily_signals else 0.0
        opening_safety_gap_qty = max(0.0, opening_safety_floor_qty + first_day_need_qty - opening_qty)
        bridge_need_qty = sum(max(0.0, daily_signals[day]) for day in range(bridge_horizon_days))
        gap_qty = max(0.0, safety_qty + bridge_need_qty - opening_qty, opening_safety_gap_qty)
        if gap_qty <= 1e-9:
            continue

        positive_shares = [max(0.0, to_float(lane.get("mrp_share"), 0.0)) for lane in lane_list]
        share_total = sum(positive_shares)
        if share_total <= 1e-9:
            positive_shares = [1.0] * len(lane_list)
            share_total = float(len(lane_list))

        for lane, share in zip(lane_list, positive_shares):
            lane_gap_qty = gap_qty * (share / share_total)
            lane_opening_safety_gap_qty = opening_safety_gap_qty * (share / share_total)
            if lane_gap_qty <= 1e-9:
                continue
            lead_days = max(1, int(to_float(lane.get("lead_days"), 1.0)))
            order_frequency_days = max(1, int(round(max(1.0, to_float(lane.get("order_frequency_days"), 1.0)))))
            standard_order_qty = max(0.0, to_float(lane.get("standard_order_qty"), 0.0))
            lane_horizon_days = max(1, min(bridge_horizon_days, lead_days + safety_days))
            cadence_order_count = max(1, int(math.ceil(lane_horizon_days / float(order_frequency_days))))
            early_receipts: list[tuple[int, float]] = []
            order_count = cadence_order_count
            if standard_order_qty > 1e-9:
                order_units = max(1, int(math.ceil((lane_gap_qty / standard_order_qty) - 1e-9)))
                opening_safety_units = min(
                    order_units,
                    max(0, int(math.ceil((lane_opening_safety_gap_qty / standard_order_qty) - 1e-9))),
                )
                if opening_safety_units > 0:
                    early_window_days = max(1, min(max(1, safety_days), lane_horizon_days))
                    early_day_count = min(opening_safety_units, early_window_days)
                    base_units = max(1, opening_safety_units // early_day_count)
                    remainder_units = opening_safety_units % early_day_count
                    for idx in range(early_day_count):
                        units = base_units + (1 if idx < remainder_units else 0)
                        early_receipts.append((idx * order_frequency_days, units * standard_order_qty))
                remaining_units = max(0, order_units - opening_safety_units)
                order_count = min(cadence_order_count, remaining_units)
                qty_by_order = []
                if order_count > 0:
                    base_units = max(1, remaining_units // order_count)
                    remainder_units = remaining_units % order_count
                    for idx in range(order_count):
                        units = base_units + (1 if idx < remainder_units else 0)
                        qty_by_order.append(units * standard_order_qty)
            else:
                opening_safety_receipt = min(lane_gap_qty, lane_opening_safety_gap_qty)
                if opening_safety_receipt > 1e-9:
                    early_receipts.append((0, opening_safety_receipt))
                remaining_gap_qty = max(0.0, lane_gap_qty - opening_safety_receipt)
                if remaining_gap_qty > 1e-9:
                    qty_per_order = remaining_gap_qty / float(order_count)
                    qty_by_order = [qty_per_order] * order_count
                else:
                    qty_by_order = []

            if order_count <= 0:
                arrival_days = []
            elif order_count == 1:
                arrival_days = [max(1, lane_horizon_days - 1)]
            else:
                latest_arrival_day = max(1, lane_horizon_days - 1)
                order_count = min(order_count, latest_arrival_day)
                arrival_days = []
                cursor = latest_arrival_day
                for _ in range(order_count):
                    arrival_days.append(max(1, cursor))
                    cursor -= order_frequency_days
                if len(set(arrival_days)) < len(arrival_days):
                    arrival_days = [
                        max(1, int(round(idx * latest_arrival_day / float(order_count - 1))))
                        for idx in range(order_count)
                    ]
                arrival_days = sorted(arrival_days)

            if early_receipts and order_count > 0:
                latest_arrival_day = max(1, lane_horizon_days - 1)
                arrival_days = [
                    min(latest_arrival_day, 1 + idx * order_frequency_days)
                    for idx in range(order_count)
                ]

            if early_receipts:
                arrival_days = [day for day, _ in early_receipts] + arrival_days
                qty_by_order = [qty for _, qty in early_receipts] + qty_by_order

            for arrival_day, receipt_qty in zip(arrival_days, qty_by_order):
                if receipt_qty <= 1e-9:
                    continue
                pipeline[arrival_day].append((pair[0], pair[1], receipt_qty, str(lane.get("edge_id", ""))))
                in_transit[pair] += receipt_qty
                seeded_total_qty += receipt_qty
                release_day_imt = arrival_day - lead_days
                initialization_pipeline_rows.append(
                    {
                        "node_id": pair[0],
                        "item_id": pair[1],
                        "category": "opening_open_order_book",
                        "seeded_pipeline_qty": round(receipt_qty, 6),
                        "lead_days": int(lead_days),
                        "lane_src": str(lane.get("src", "")),
                    }
                )
                row = {
                    "node_id": pair[0],
                    "item_id": pair[1],
                    "src_node_id": str(lane.get("src", "")),
                    "edge_id": str(lane.get("edge_id", "")),
                    "arrival_day": int(arrival_day),
                    "release_day_imt": int(release_day_imt),
                    "receipt_qty": round(receipt_qty, 6),
                    "lead_days": int(lead_days),
                    "order_frequency_days": int(order_frequency_days),
                    "standard_order_qty": round(standard_order_qty, 6),
                    "safety_time_days": round(float(safety_days), 6),
                    "opening_safety_floor_qty": round(opening_safety_floor_qty, 6),
                    "opening_safety_gap_qty": round(opening_safety_gap_qty, 6),
                    "bridge_horizon_days": int(bridge_horizon_days),
                    "opening_stock_qty": round(opening_qty, 6),
                    "bridge_need_qty": round(bridge_need_qty, 6),
                    "gap_qty": round(gap_qty, 6),
                }
                open_order_rows.append(row)
                assumptions_ledger_rows.append(
                    {
                        "category": "opening_open_order_book",
                        "node_id": pair[0],
                        "item_id": pair[1],
                        "edge_id": str(lane.get("edge_id", "")),
                        "source": "mrp_open_orders_reconstruction",
                        "payload_json": json.dumps(row, ensure_ascii=False, sort_keys=True),
                    }
                )

    open_order_rows.sort(key=lambda row: (row["node_id"], row["item_id"], row["arrival_day"], row["src_node_id"]))
    return seeded_total_qty, open_order_rows, bridge_days_by_pair


def derive_supplier_daily_capacity_by_pair(
    *,
    nodes: list[dict[str, Any]],
    supplier_node_ids: set[str],
    lanes_by_src_item: dict[tuple[str, str], list[dict[str, Any]]],
    required_daily_input_by_pair: dict[tuple[str, str], float],
    propagated_demand_today: dict[tuple[str, str], float],
    item_unit_map: dict[str, str],
    stock: dict[tuple[str, str], float],
    default_review_period_days: int,
    stochastic_lead_times: bool,
) -> tuple[dict[tuple[str, str], float], list[dict[str, Any]]]:
    node_by_id = {str(n.get("id")): n for n in nodes}
    capacity_by_pair: dict[tuple[str, str], float] = {}
    metadata_rows: list[dict[str, Any]] = []

    for src_pair, lane_list in sorted(lanes_by_src_item.items()):
        src, item_id = src_pair
        if src not in supplier_node_ids:
            continue

        node = node_by_id.get(src, {})
        review_days = node_review_period_days(node, default_review_period_days)
        sim_constraints = node.get("simulation_constraints") or {}
        node_capacity_scale = max(0.01, to_float(sim_constraints.get("supplier_capacity_scale"), 1.0))
        explicit_capacity_map = sim_constraints.get("supplier_item_capacity_qty_per_day") or {}
        explicit_capacity = max(0.0, to_float(explicit_capacity_map.get(item_id), 0.0))
        initial_stock = max(0.0, stock.get(src_pair, 0.0))
        inventory_fallback = initial_stock / max(1.0, float(review_days))
        process_capacity = process_output_capacity_by_item(node, item_unit_map).get(item_id, 0.0)

        downstream_requirement = 0.0
        downstream_signal = 0.0
        standard_hints: list[float] = []
        for lane in lane_list:
            dst_pair = (str(lane["dst"]), item_id)
            downstream_requirement += max(0.0, required_daily_input_by_pair.get(dst_pair, 0.0))
            downstream_signal += max(0.0, propagated_demand_today.get(dst_pair, 0.0))
            standard_qty = max(0.0, to_float(lane.get("standard_order_qty"), 0.0))
            if standard_qty > 0:
                hint_days = max(
                    1.0,
                    float(review_days),
                    float(lane.get("order_frequency_days", 1)),
                    float(lead_time_cover_days(lane, stochastic_lead_times)),
                )
                standard_hints.append(standard_qty / hint_days)

        demand_anchor = max(downstream_requirement, downstream_signal)
        if explicit_capacity > 0:
            nominal_capacity = explicit_capacity
            basis = "explicit_capacity"
        elif process_capacity > 0:
            nominal_capacity = process_capacity
            basis = "process_capacity"
        elif demand_anchor > 0:
            nominal_capacity = max(demand_anchor * 1.25, inventory_fallback, 1.0)
            basis = "downstream_requirement"
        else:
            nominal_capacity = max(inventory_fallback, 1.0)
            basis = "inventory_fallback"

        if standard_hints and nominal_capacity > 0:
            plausible_hints = [
                hint
                for hint in standard_hints
                if nominal_capacity * 0.25 <= hint <= nominal_capacity * 4.0
            ]
            if plausible_hints:
                nominal_capacity = max(nominal_capacity, sum(plausible_hints) / len(plausible_hints))
                basis += "+fia_hint"

        scaled_capacity = max(0.01, nominal_capacity * node_capacity_scale)
        capacity_by_pair[src_pair] = scaled_capacity
        metadata_rows.append(
            {
                "node_id": src,
                "item_id": item_id,
                "review_period_days": review_days,
                "initial_stock_qty": round(initial_stock, 6),
                "inventory_fallback_qty_per_day": round(inventory_fallback, 6),
                "downstream_requirement_qty_per_day": round(downstream_requirement, 6),
                "downstream_signal_qty_per_day": round(downstream_signal, 6),
                "explicit_capacity_qty_per_day": round(explicit_capacity, 6),
                "process_capacity_qty_per_day": round(process_capacity, 6),
                "nominal_capacity_qty_per_day": round(nominal_capacity, 6),
                "applied_capacity_scale": round(node_capacity_scale, 6),
                "effective_capacity_qty_per_day": round(scaled_capacity, 6),
                "basis": basis,
            }
        )

    return capacity_by_pair, metadata_rows


def allocate_shared_downstream_pull(
    *,
    src_pair: tuple[str, str],
    lanes_by_src_item: dict[tuple[str, str], list[dict[str, Any]]],
    externally_sourced_pairs: list[tuple[str, str]],
    supplier_daily_capacity_by_pair: dict[tuple[str, str], float],
    downstream_values_by_pair: dict[tuple[str, str], float],
) -> float:
    """Allocate downstream pull across alternative upstream sources for the same dst/item."""
    allocated = 0.0
    for lane in lanes_by_src_item.get(src_pair, []):
        dst_pair = (str(lane.get("dst")), src_pair[1])
        downstream_value = max(0.0, downstream_values_by_pair.get(dst_pair, 0.0))
        if downstream_value <= 0.0:
            continue
        candidate_pairs: list[tuple[str, str]] = []
        for candidate_src_pair in externally_sourced_pairs:
            if candidate_src_pair[1] != src_pair[1]:
                continue
            for candidate_lane in lanes_by_src_item.get(candidate_src_pair, []):
                if str(candidate_lane.get("dst")) == dst_pair[0]:
                    candidate_pairs.append(candidate_src_pair)
                    break
        if not candidate_pairs:
            allocated += downstream_value
            continue
        total_capacity = sum(max(0.0, supplier_daily_capacity_by_pair.get(pair, 0.0)) for pair in candidate_pairs)
        if total_capacity > 1e-9:
            share = max(0.0, supplier_daily_capacity_by_pair.get(src_pair, 0.0)) / total_capacity
        else:
            share = 1.0 / float(len(candidate_pairs))
        allocated += downstream_value * share
    return allocated


def derive_unmodeled_supplier_source_policies(
    *,
    externally_sourced_pairs: list[tuple[str, str]],
    nodes: list[dict[str, Any]],
    lanes_by_src_item: dict[tuple[str, str], list[dict[str, Any]]],
    supplier_daily_capacity_by_pair: dict[tuple[str, str], float],
    base_stock: dict[tuple[str, str], float],
    required_daily_input_by_pair: dict[tuple[str, str], float],
    propagated_demand_today: dict[tuple[str, str], float],
    default_review_period_days: int,
    safety_stock_days: float,
    stochastic_lead_times: bool,
) -> tuple[dict[tuple[str, str], dict[str, Any]], list[dict[str, Any]]]:
    node_by_id = {str(n.get("id")): n for n in nodes}
    policies: dict[tuple[str, str], dict[str, Any]] = {}
    metadata_rows: list[dict[str, Any]] = []

    for src_pair in externally_sourced_pairs:
        lane_list = lanes_by_src_item.get(src_pair, [])
        if not lane_list or src_pair not in supplier_daily_capacity_by_pair:
            continue
        src, item_id = src_pair
        node = node_by_id.get(src, {})
        review_days = node_review_period_days(node, default_review_period_days)
        lead_cover_days = max([lead_time_cover_days(lane, stochastic_lead_times) for lane in lane_list] or [1])
        order_frequency_days = max(
            [int(round(max(1.0, to_float(lane.get("order_frequency_days"), 1.0)))) for lane in lane_list] or [1]
        )
        raw_replenishment_lead_days = max(
            float(review_days),
            float(order_frequency_days),
            0.5 * float(lead_cover_days),
        )
        replenishment_lead_days = int(min(21.0, max(2.0, math.ceil(raw_replenishment_lead_days))))
        target_cover_days = max(
            int(math.ceil(safety_stock_days)),
            replenishment_lead_days + review_days,
            order_frequency_days,
        )
        downstream_requirement = allocate_shared_downstream_pull(
            src_pair=src_pair,
            lanes_by_src_item=lanes_by_src_item,
            externally_sourced_pairs=externally_sourced_pairs,
            supplier_daily_capacity_by_pair=supplier_daily_capacity_by_pair,
            downstream_values_by_pair=required_daily_input_by_pair,
        )
        downstream_signal = allocate_shared_downstream_pull(
            src_pair=src_pair,
            lanes_by_src_item=lanes_by_src_item,
            externally_sourced_pairs=externally_sourced_pairs,
            supplier_daily_capacity_by_pair=supplier_daily_capacity_by_pair,
            downstream_values_by_pair=propagated_demand_today,
        )
        demand_anchor = max(downstream_requirement, downstream_signal)
        downstream_lot_floor = max(
            [max(0.0, to_float(lane.get("standard_order_qty"), 0.0)) for lane in lane_list] or [0.0]
        )
        target_stock_qty = max(
            base_stock.get(src_pair, 0.0),
            downstream_lot_floor,
            demand_anchor * float(target_cover_days),
        )
        reorder_point_qty = max(
            base_stock.get(src_pair, 0.0),
            downstream_lot_floor,
            demand_anchor * float(replenishment_lead_days),
        )
        daily_capacity = max(0.0, supplier_daily_capacity_by_pair.get(src_pair, 0.0))
        policies[src_pair] = {
            "replenishment_lead_days": replenishment_lead_days,
            "raw_replenishment_lead_days": raw_replenishment_lead_days,
            "target_cover_days": target_cover_days,
            "review_period_days": review_days,
            "order_frequency_days": order_frequency_days,
            "downstream_requirement_qty_per_day": downstream_requirement,
            "downstream_signal_qty_per_day": downstream_signal,
            "downstream_lot_floor_qty": downstream_lot_floor,
            "target_stock_qty_day0": target_stock_qty,
            "reorder_point_qty_day0": reorder_point_qty,
            "daily_capacity_qty": daily_capacity,
        }
        metadata_rows.append(
            {
                "node_id": src,
                "item_id": item_id,
                "replenishment_lead_days": replenishment_lead_days,
                "raw_replenishment_lead_days": round(raw_replenishment_lead_days, 6),
                "target_cover_days": target_cover_days,
                "review_period_days": review_days,
                "order_frequency_days": order_frequency_days,
                "downstream_requirement_qty_per_day": round(downstream_requirement, 6),
                "downstream_signal_qty_per_day": round(downstream_signal, 6),
                "downstream_lot_floor_qty": round(downstream_lot_floor, 6),
                "reorder_point_qty_day0": round(reorder_point_qty, 6),
                "target_stock_qty_day0": round(target_stock_qty, 6),
                "daily_capacity_qty": round(daily_capacity, 6),
            }
        )
    return policies, metadata_rows


def try_generate_plots(
    input_stock_rows: list[dict[str, Any]],
    output_prod_rows: list[dict[str, Any]],
    supplier_shipment_rows: list[dict[str, Any]],
    supplier_factory_items: dict[str, set[tuple[str, str]]] | None,
    dc_factory_items: dict[str, set[tuple[str, str]]] | None,
    dc_node_ids: set[str] | None,
    output_dir: Path,
    item_unit_map: dict[str, str] | None = None,
) -> dict[str, str]:
    try:
        import matplotlib.pyplot as plt  # type: ignore
    except Exception:
        return {}

    plot_root = output_dir / "plots"
    factory_input_dir = plot_root / "factories" / "input_stocks"
    factory_output_dir = plot_root / "factories" / "output_products"
    supplier_input_dir = plot_root / "suppliers" / "input_stocks"
    dc_output_dir = plot_root / "distribution_centers" / "factory_outputs"
    for plot_dir in (
        factory_input_dir,
        factory_output_dir,
        supplier_input_dir,
        dc_output_dir,
    ):
        plot_dir.mkdir(parents=True, exist_ok=True)

    generated: dict[str, str] = {}

    # Plot 1: raw-material input stocks by material for each factory.
    by_factory_item_day: dict[str, dict[str, dict[int, float]]] = defaultdict(lambda: defaultdict(dict))
    for r in input_stock_rows:
        day = int(r["day"])
        factory = str(r["node_id"])
        item = str(r["item_id"])
        val = r.get("stock_end_of_day", r.get("stock_before_production", 0.0))
        by_factory_item_day[factory][item][day] = to_float(val, 0.0)

    item_unit_map = item_unit_map or {}
    unit_axes_order = ("KG", "G", "UN")
    unit_cmap = {
        "KG": plt.cm.Blues,
        "G": plt.cm.Oranges,
        "UN": plt.cm.Greens,
    }

    def plot_stock_multiaxis(
        item_map: dict[str, dict[int, float]],
        title: str,
        out_path: Path,
        y_label_prefix: str = "Stock",
        unit_by_item: dict[str, str] | None = None,
        legend_label_by_item: dict[str, str] | None = None,
    ) -> bool:
        if not item_map:
            return False
        all_days = sorted({d for values in item_map.values() for d in values.keys()})
        if not all_days:
            return False

        unit_by_item = unit_by_item or {}
        legend_label_by_item = legend_label_by_item or {}
        items_by_unit: dict[str, list[str]] = {u: [] for u in unit_axes_order}
        for item in sorted(item_map.keys()):
            unit = normalize_unit(unit_by_item.get(item, item_unit_map.get(item, "")))
            target_unit = unit if unit in items_by_unit else "KG"
            items_by_unit[target_unit].append(item)

        present_units = [u for u in unit_axes_order if items_by_unit[u]]
        if not present_units:
            return False

        fig, ax_primary = plt.subplots(figsize=(14, 7))
        axis_for_unit: dict[str, Any] = {}
        for idx, unit in enumerate(present_units):
            if idx == 0:
                axis_for_unit[unit] = ax_primary
            else:
                axis = ax_primary.twinx()
                if idx >= 2:
                    axis.spines["right"].set_position(("outward", 62 * (idx - 1)))
                axis_for_unit[unit] = axis

        color_by_item: dict[str, Any] = {}
        for unit in present_units:
            items = items_by_unit[unit]
            cmap = unit_cmap[unit]
            n = len(items)
            for idx, item in enumerate(items):
                t = 0.40 if n == 1 else 0.35 + (0.55 * idx / (n - 1))
                color_by_item[item] = cmap(t)

        lines_by_axis: dict[str, list[Any]] = {u: [] for u in present_units}
        labels_by_axis: dict[str, list[str]] = {u: [] for u in present_units}

        for item in sorted(item_map.keys()):
            series = [item_map[item].get(d, 0.0) for d in all_days]
            unit = normalize_unit(unit_by_item.get(item, item_unit_map.get(item, "")))
            target_unit = unit if unit in axis_for_unit else present_units[0]
            axis = axis_for_unit[target_unit]
            line = axis.plot(
                all_days,
                series,
                marker="o",
                linewidth=1.4,
                color=color_by_item.get(item),
            )[0]
            lines_by_axis[target_unit].append(line)
            legend_label = legend_label_by_item.get(item, item)
            labels_by_axis[target_unit].append(f"{legend_label} [{target_unit}]")

        ax_primary.set_title(title)
        ax_primary.set_xlabel("Jour")
        ax_primary.grid(alpha=0.3)
        for unit in present_units:
            axis_for_unit[unit].set_ylabel(f"{y_label_prefix} ({unit})")

        if len(present_units) == 1:
            x_positions = [0.50]
        elif len(present_units) == 2:
            x_positions = [0.30, 0.70]
        else:
            x_positions = [0.17, 0.50, 0.83]
        legend_positions = {unit: (x_positions[idx], 0.02) for idx, unit in enumerate(present_units)}

        for unit in present_units:
            unit_lines = lines_by_axis[unit]
            unit_labels = labels_by_axis[unit]
            if not unit_lines:
                continue
            fig.legend(
                unit_lines,
                unit_labels,
                ncol=1,
                fontsize=8,
                title=unit,
                title_fontsize=9,
                loc="lower center",
                bbox_to_anchor=legend_positions[unit],
                frameon=True,
            )

        right_by_count = {1: 0.95, 2: 0.90, 3: 0.83}
        fig.subplots_adjust(right=right_by_count.get(len(present_units), 0.83), bottom=0.34)
        fig.savefig(out_path, dpi=150)
        plt.close(fig)
        return True

    for factory, item_map in sorted(by_factory_item_day.items()):
        if not item_map:
            continue
        all_days = sorted({d for values in item_map.values() for d in values.keys()})
        if not all_days:
            continue
        fig, ax_kg = plt.subplots(figsize=(14, 7))
        ax_g = ax_kg.twinx()
        ax_un = ax_kg.twinx()
        ax_un.spines["right"].set_position(("outward", 62))

        axis_for_unit = {
            "KG": ax_kg,
            "G": ax_g,
            "UN": ax_un,
        }
        unit_cmap = {
            "KG": plt.cm.Blues,
            "G": plt.cm.Oranges,
            "UN": plt.cm.Greens,
        }
        lines_by_axis: dict[str, list[Any]] = {u: [] for u in unit_axes_order}
        labels_by_axis: dict[str, list[str]] = {u: [] for u in unit_axes_order}
        items_by_unit: dict[str, list[str]] = {u: [] for u in unit_axes_order}

        for item in sorted(item_map.keys()):
            unit = normalize_unit(item_unit_map.get(item, ""))
            target_unit = unit if unit in axis_for_unit else "KG"
            items_by_unit[target_unit].append(item)

        color_by_item: dict[str, Any] = {}
        for unit in unit_axes_order:
            items = items_by_unit[unit]
            if not items:
                continue
            cmap = unit_cmap[unit]
            n = len(items)
            for idx, item in enumerate(items):
                # Keep colors in a readable mid/high range for each unit palette.
                t = 0.40 if n == 1 else 0.35 + (0.55 * idx / (n - 1))
                color_by_item[item] = cmap(t)

        for item in sorted(item_map.keys()):
            series = [item_map[item].get(d, 0.0) for d in all_days]
            unit = normalize_unit(item_unit_map.get(item, ""))
            target_unit = unit if unit in axis_for_unit else "KG"
            axis = axis_for_unit[target_unit]
            line = axis.plot(
                all_days,
                series,
                marker="o",
                linewidth=1.4,
                color=color_by_item.get(item),
            )[0]
            lines_by_axis[target_unit].append(line)
            labels_by_axis[target_unit].append(f"{item} [{target_unit}]")

        ax_kg.set_title(f"Stocks de fin de journee des matieres premieres - {factory}")
        ax_kg.set_xlabel("Jour")
        ax_kg.set_ylabel("Stock (KG)")
        ax_g.set_ylabel("Stock (G)")
        ax_un.set_ylabel("Stock (UN)")
        ax_kg.grid(alpha=0.3)

        legend_positions = {
            "KG": (0.17, 0.02),
            "G": (0.50, 0.02),
            "UN": (0.83, 0.02),
        }
        for unit in unit_axes_order:
            unit_lines = lines_by_axis[unit]
            unit_labels = labels_by_axis[unit]
            if not unit_lines:
                continue
            fig.legend(
                unit_lines,
                unit_labels,
                ncol=1,
                fontsize=8,
                title=unit,
                title_fontsize=9,
                loc="lower center",
                bbox_to_anchor=legend_positions[unit],
                frameon=True,
            )
        fig.subplots_adjust(right=0.83, bottom=0.34)
        safe_factory = re.sub(r"[^A-Za-z0-9_-]+", "_", factory)
        out = factory_input_dir / f"production_input_stocks_by_material_{safe_factory}.png"
        fig.savefig(out, dpi=150)
        plt.close(fig)
        generated[f"production_input_stocks_by_material_{factory}"] = str(out)

    # Plot 2: production of output products.
    by_pair: dict[str, list[tuple[int, float]]] = defaultdict(list)
    by_factory_pair: dict[str, dict[str, list[tuple[int, float]]]] = defaultdict(lambda: defaultdict(list))
    for r in output_prod_rows:
        factory = str(r["node_id"])
        item_id = str(r["item_id"])
        day = int(r["day"])
        qty = to_float(r["produced_qty"], 0.0)
        label = pair_label(factory, item_id)
        by_pair[label].append((day, qty))
        by_factory_pair[factory][item_id].append((day, qty))

    if by_pair:
        plt.figure(figsize=(12, 6))
        for label in sorted(by_pair.keys()):
            points = sorted(by_pair[label], key=lambda x: x[0])
            days = [p[0] for p in points]
            vals = [p[1] for p in points]
            plt.plot(days, vals, marker="o", linewidth=1.8, label=label)
        plt.title("Production journaliere des produits finis (sortie)")
        plt.xlabel("Jour")
        plt.ylabel("Production (unites/jour)")
        plt.grid(alpha=0.3)
        plt.legend()
        plt.tight_layout()
        out = factory_output_dir / "production_output_products.png"
        plt.savefig(out, dpi=150)
        plt.close()
        generated["production_output_products_png"] = str(out)

    for factory, item_map in sorted(by_factory_pair.items()):
        if not item_map:
            continue
        plt.figure(figsize=(12, 6))
        for item_id in sorted(item_map.keys()):
            points = sorted(item_map[item_id], key=lambda x: x[0])
            days = [p[0] for p in points]
            vals = [p[1] for p in points]
            plt.plot(days, vals, marker="o", linewidth=1.8, label=item_id)
        plt.title(f"Production journaliere des produits finis - {factory}")
        plt.xlabel("Jour")
        plt.ylabel("Production (unites/jour)")
        plt.grid(alpha=0.3)
        plt.legend()
        plt.tight_layout()
        safe_factory = re.sub(r"[^A-Za-z0-9_-]+", "_", factory)
        out = factory_output_dir / f"production_output_products_by_factory_{safe_factory}.png"
        plt.savefig(out, dpi=150)
        plt.close()
        generated[f"production_output_products_by_factory_{factory}"] = str(out)

    # Plot 3: supplier view = downstream process-node input stocks on supplier-related items.
    supplier_factory_items = supplier_factory_items or {}
    for supplier, scoped_pairs in sorted(supplier_factory_items.items()):
        item_map: dict[str, dict[int, float]] = {}
        unit_by_item: dict[str, str] = {}
        legend_label_by_item: dict[str, str] = {}
        for factory, item in sorted(scoped_pairs):
            factory_series = by_factory_item_day.get(factory, {}).get(item)
            if not factory_series:
                continue
            series_key = f"{factory}|{item}"
            item_map[series_key] = dict(factory_series)
            unit_by_item[series_key] = normalize_unit(item_unit_map.get(item, ""))
            legend_label_by_item[series_key] = f"{item} ({factory})"
        if not item_map:
            continue
        safe_supplier = re.sub(r"[^A-Za-z0-9_-]+", "_", supplier)
        out = supplier_input_dir / f"production_supplier_input_stocks_by_material_{safe_supplier}.png"
        if plot_stock_multiaxis(
            item_map,
            f"Stocks d'entree du noeud aval (produits du fournisseur) - {supplier}",
            out,
            y_label_prefix="Stock",
            unit_by_item=unit_by_item,
            legend_label_by_item=legend_label_by_item,
        ):
            generated[f"production_supplier_input_stocks_by_material_{supplier}"] = str(out)

    # Plot 4: distribution center view = upstream factory output series for DC-related items.
    dc_factory_items = dc_factory_items or {}
    by_factory_output_item_day: dict[str, dict[str, dict[int, float]]] = defaultdict(lambda: defaultdict(dict))
    for r in output_prod_rows:
        day = int(r["day"])
        factory = str(r["node_id"])
        item = str(r["item_id"])
        val = to_float(r.get("produced_qty"), 0.0)
        by_factory_output_item_day[factory][item][day] = val

    for dc_node, scoped_pairs in sorted(dc_factory_items.items()):
        item_map: dict[str, dict[int, float]] = {}
        unit_by_item: dict[str, str] = {}
        legend_label_by_item: dict[str, str] = {}
        for factory, item in sorted(scoped_pairs):
            factory_series = by_factory_output_item_day.get(factory, {}).get(item)
            if not factory_series:
                continue
            series_key = f"{factory}|{item}"
            item_map[series_key] = dict(factory_series)
            unit_by_item[series_key] = normalize_unit(item_unit_map.get(item, ""))
            legend_label_by_item[series_key] = f"{item} ({factory})"
        if not item_map:
            continue
        safe_dc = re.sub(r"[^A-Za-z0-9_-]+", "_", dc_node)
        out = dc_output_dir / f"production_dc_factory_outputs_by_material_{safe_dc}.png"
        if plot_stock_multiaxis(
            item_map,
            f"Productions usines liees au distribution center - {dc_node}",
            out,
            y_label_prefix="Production",
            unit_by_item=unit_by_item,
            legend_label_by_item=legend_label_by_item,
        ):
            generated[f"production_dc_factory_outputs_by_material_{dc_node}"] = str(out)

    return generated


def main() -> None:
    args = parse_args()
    input_path = Path(args.input)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    ensure_standard_dirs(output_dir)

    data = json.loads(input_path.read_text(encoding="utf-8"))
    nodes = data.get("nodes", []) or []
    edges = data.get("edges", []) or []
    node_by_id = {str(n.get("id")): n for n in nodes}
    mrp_snapshot_pairs = {
        (str(n.get("id")), str(state.get("item_id")))
        for n in nodes
        for state in (((n.get("inventory") or {}).get("states") or []))
        if str(state.get("initial_source") or "").strip().lower() == "mrp_snapshot"
    }
    item_unit_map = infer_item_unit_map(nodes, edges)
    assumed_supplier_nodes_set = {
        str(n.get("id"))
        for n in nodes
        if bool(n.get("is_invented"))
        or bool((n.get("assumptions") or {}).get("is_invented"))
        or bool(n.get("is_assumed"))
        or bool((n.get("assumptions") or {}).get("is_assumed"))
    }
    assumed_supply_edges_set: set[str] = set()
    for e in edges:
        is_assumed_edge = (
            bool(e.get("is_invented"))
            or str(e.get("source") or "").startswith("simulation_prep_invented_supplier_assumption")
            or bool(e.get("is_assumed"))
            or str(e.get("source") or "").startswith("simulation_prep_gaillac_question_mark_assumption")
        )
        if not is_assumed_edge:
            continue
        assumed_supply_edges_set.add(str(e.get("id")))
        assumed_supplier_nodes_set.add(str(e.get("from")))
    assumed_supplier_nodes = sorted(assumed_supplier_nodes_set)
    assumed_supply_edges = sorted(assumed_supply_edges_set)

    scenario = choose_scenario(data, args.scenario_id)
    default_days = int(to_float(((scenario.get("horizon") or {}).get("steps_to_run")), 30))
    sim_days = args.days if args.days > 0 else (default_days if default_days > 0 else 30)
    warmup_days = (
        max(0, int(args.warmup_days))
        if args.warmup_days is not None
        else max(0, int(round(scenario_policy_value(scenario, "warmup_days", 0.0))))
    )
    reset_backlog_after_warmup = scenario_policy_bool(scenario, "reset_backlog_after_warmup", False)
    total_timeline_days = warmup_days + sim_days
    safety_stock_days = max(0.0, scenario_policy_value(scenario, "safety_stock_days", 7.0))
    review_period_days = max(1, int(round(scenario_policy_value(scenario, "review_period_days", 1.0))))
    fg_target_days = max(0.0, scenario_policy_value(scenario, "fg_target_days", 0.0))
    demand_stock_target_days = max(0.0, scenario_policy_value(scenario, "demand_stock_target_days", 0.0))
    production_gap_gain = max(0.0, scenario_policy_value(scenario, "production_gap_gain", 0.25))
    production_smoothing = min(0.95, max(0.0, scenario_policy_value(scenario, "production_smoothing", 0.20)))
    initialization_policy = scenario_initialization_policy(
        scenario,
        review_period_days=review_period_days,
        safety_stock_days=safety_stock_days,
    )
    economic_policy_cfg = scenario_policy_dict(scenario, "economic_policy")
    unmodeled_supplier_source_mode = str(scenario.get("unmodeled_supplier_source_mode", "external_procurement")).strip().lower()
    if unmodeled_supplier_source_mode not in {
        "external_procurement",
        "estimated_capacity",
        "estimated_replenishment",
    }:
        unmodeled_supplier_source_mode = "external_procurement"
    economic_policy = {
        "transport_cost_floor_per_unit": max(
            0.0,
            to_float(economic_policy_cfg.get("transport_cost_floor_per_unit"), 0.02),
        ),
        "transport_cost_per_km_per_unit": max(
            0.0,
            to_float(economic_policy_cfg.get("transport_cost_per_km_per_unit"), 0.00008),
        ),
        "purchase_cost_floor_per_unit": max(
            0.0,
            to_float(economic_policy_cfg.get("purchase_cost_floor_per_unit"), 0.01),
        ),
        "holding_cost_scale": max(
            0.0,
            to_float(economic_policy_cfg.get("holding_cost_scale"), 1.0),
        ),
        # Benchmark-inspired decomposition for pharma-like supply economics:
        # raw per-item holding cost is reallocated between capital tied-up,
        # warehouse/compliance operations, and inventory risk/obsolescence.
        "inventory_capital_cost_share_of_raw_holding": max(
            0.0,
            to_float(economic_policy_cfg.get("inventory_capital_cost_share_of_raw_holding"), 0.35),
        ),
        "warehouse_operating_cost_share_of_raw_holding": max(
            0.0,
            to_float(economic_policy_cfg.get("warehouse_operating_cost_share_of_raw_holding"), 0.45),
        ),
        "inventory_risk_cost_share_of_raw_holding": max(
            0.0,
            to_float(economic_policy_cfg.get("inventory_risk_cost_share_of_raw_holding"), 0.20),
        ),
        "transport_cost_realism_multiplier": max(
            0.1,
            to_float(economic_policy_cfg.get("transport_cost_realism_multiplier"), 8.0),
        ),
        "purchase_cost_realism_multiplier": max(
            0.1,
            to_float(economic_policy_cfg.get("purchase_cost_realism_multiplier"), 1.0),
        ),
        "external_procurement_enabled": (
            economic_policy_cfg.get("external_procurement_enabled")
            if isinstance(economic_policy_cfg.get("external_procurement_enabled"), bool)
            else str(
                economic_policy_cfg.get(
                    "external_procurement_enabled",
                    scenario_policy_bool(scenario, "external_procurement_enabled", True),
                )
            ).strip().lower()
            in {"1", "true", "yes", "y", "on"}
        ),
        "external_procurement_proactive_replenishment": (
            economic_policy_cfg.get("external_procurement_proactive_replenishment")
            if isinstance(economic_policy_cfg.get("external_procurement_proactive_replenishment"), bool)
            else str(
                economic_policy_cfg.get(
                    "external_procurement_proactive_replenishment",
                    scenario_policy_bool(scenario, "external_procurement_proactive_replenishment", True),
                )
            ).strip().lower()
            in {"1", "true", "yes", "y", "on"}
        ),
        "external_procurement_lead_days": max(
            0,
            int(round(to_float(economic_policy_cfg.get("external_procurement_lead_days"), 4.0))),
        ),
        "external_procurement_daily_cap_days": max(
            0.0,
            to_float(economic_policy_cfg.get("external_procurement_daily_cap_days"), 2.0),
        ),
        "external_procurement_min_daily_cap_qty": max(
            0.0,
            to_float(economic_policy_cfg.get("external_procurement_min_daily_cap_qty"), 0.0),
        ),
        "external_procurement_unit_cost": max(
            0.0,
            to_float(economic_policy_cfg.get("external_procurement_unit_cost"), 0.0),
        ),
        "external_procurement_cost_multiplier": max(
            0.0,
            to_float(economic_policy_cfg.get("external_procurement_cost_multiplier"), 2.0),
        ),
        "external_procurement_transport_cost_per_unit": max(
            0.0,
            to_float(economic_policy_cfg.get("external_procurement_transport_cost_per_unit"), 0.04),
        ),
    }
    inventory_cost_share_sum = (
        economic_policy["inventory_capital_cost_share_of_raw_holding"]
        + economic_policy["warehouse_operating_cost_share_of_raw_holding"]
        + economic_policy["inventory_risk_cost_share_of_raw_holding"]
    )
    if inventory_cost_share_sum <= 1e-9:
        economic_policy["inventory_capital_cost_share_of_raw_holding"] = 0.35
        economic_policy["warehouse_operating_cost_share_of_raw_holding"] = 0.45
        economic_policy["inventory_risk_cost_share_of_raw_holding"] = 0.20
        inventory_cost_share_sum = 1.0
    economic_policy["inventory_capital_cost_share_of_raw_holding"] /= inventory_cost_share_sum
    economic_policy["warehouse_operating_cost_share_of_raw_holding"] /= inventory_cost_share_sum
    economic_policy["inventory_risk_cost_share_of_raw_holding"] /= inventory_cost_share_sum
    rng = random.Random(args.seed)

    stock: dict[tuple[str, str], float] = defaultdict(float)
    holding_cost: dict[tuple[str, str], float] = defaultdict(float)
    base_stock: dict[tuple[str, str], float] = defaultdict(float)
    pair_mrp_safety_time_days: dict[tuple[str, str], float] = defaultdict(float)
    pair_mrp_safety_stock_qty: dict[tuple[str, str], float] = defaultdict(float)
    for n in nodes:
        nid = str(n.get("id"))
        inv = n.get("inventory") or {}
        for st in (inv.get("states") or []):
            key = (nid, str(st.get("item_id")))
            initial = to_float(st.get("initial"), 0.0)
            stock[key] = initial
            # An MRP snapshot is an opening position, not a standing reorder target.
            # Keeping the opening stock as perpetual base stock forces some seeded
            # supplier pairs into daily capped replenishment even when downstream
            # demand is variable and current stock is already ample.
            if key in mrp_snapshot_pairs:
                base_stock[key] = 0.0
            else:
                base_stock[key] = initial
            hc = st.get("holding_cost") or {}
            holding_cost[key] = to_float((hc or {}).get("value"), 0.0) * economic_policy["holding_cost_scale"]
            mrp_policy = st.get("mrp_policy") or {}
            if isinstance(mrp_policy, dict):
                pair_mrp_safety_time_days[key] = max(0.0, to_float(mrp_policy.get("safety_time_days"), 0.0))
                # Business rule: only safety delays are actionable for stock policy.
                # Source safety-stock quantities are ignored in this simulation.
                pair_mrp_safety_stock_qty[key] = 0.0
    opening_stock_source_snapshot = dict(stock)

    lanes, lanes_by_dest_item = lane_records(edges, economic_policy=economic_policy)
    lanes_with_fallback_transport_cost = sum(1 for l in lanes if bool(l.get("transport_cost_is_fallback")))
    lanes_with_explicit_transport_cost = len(lanes) - lanes_with_fallback_transport_cost
    lanes_by_src_item: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for lane in lanes:
        lanes_by_src_item[(str(lane["src"]), str(lane["item_id"]))].append(lane)
    node_type_by_id = {str(n.get("id")): str(n.get("type") or "") for n in nodes}
    supplier_node_ids = {
        node_id
        for node_id, node_type in node_type_by_id.items()
        if node_type == "supplier_dc"
    }
    dc_node_ids = {
        node_id
        for node_id, node_type in node_type_by_id.items()
        if node_type == "distribution_center"
    }
    for lane in lanes:
        if not bool(lane.get("purchase_cost_is_fallback")):
            continue
        src_type = node_type_by_id.get(str(lane.get("src")), "")
        dst_type = node_type_by_id.get(str(lane.get("dst")), "")
        if src_type in {"factory", "distribution_center"} or dst_type in {"distribution_center", "customer"}:
            lane["unit_purchase_cost"] = 0.0
            lane["purchase_cost_suppressed_reason"] = "internal_or_finished_goods_lane_without_purchase_price"
    supplier_factory_items: dict[str, set[tuple[str, str]]] = defaultdict(set)
    process_node_ids = {
        str(n.get("id"))
        for n in nodes
        if n.get("processes")
    }
    for lane in lanes:
        src = str(lane["src"])
        dst = str(lane["dst"])
        item_id = str(lane["item_id"])
        if src in supplier_node_ids and dst in process_node_ids:
            supplier_factory_items[src].add((dst, item_id))
    dc_factory_items: dict[str, set[tuple[str, str]]] = defaultdict(set)
    for lane in lanes:
        src = str(lane["src"])
        dst = str(lane["dst"])
        item_id = str(lane["item_id"])
        if dst in dc_node_ids and node_type_by_id.get(src) == "factory":
            dc_factory_items[dst].add((src, item_id))
    inbound_pairs = set(lanes_by_dest_item.keys())
    outbound_pairs = {(str(l["src"]), str(l["item_id"])) for l in lanes}
    produced_pairs = {
        (str(n.get("id")), str((out or {}).get("item_id")))
        for n in nodes
        for p in (n.get("processes") or [])
        for out in (p.get("outputs") or [])
        if (out or {}).get("item_id") is not None
    }
    process_tau_days_by_pair: dict[tuple[str, str], float] = {}
    for n in nodes:
        nid = str(n.get("id"))
        for p in (n.get("processes") or []):
            tau_days = max(0.0, to_float(((p.get("wip") or {}).get("tau_process")), 0.0))
            for out in (p.get("outputs") or []):
                item_id = str((out or {}).get("item_id"))
                if not item_id:
                    continue
                key = (nid, item_id)
                process_tau_days_by_pair[key] = max(process_tau_days_by_pair.get(key, 0.0), tau_days)
    process_input_requirements_by_output_pair = build_process_input_requirements_by_output_pair(nodes, item_unit_map)
    production_lot_reference_qty_by_pair: dict[tuple[str, str], float] = {}
    production_lot_policy_by_pair: dict[tuple[str, str], dict[str, Any]] = {}
    process_capacity_by_output_pair: dict[tuple[str, str], float] = {}
    for node in nodes:
        node_id = str(node.get("id"))
        for proc in node.get("processes") or []:
            cap_raw = max(0.0, to_float(((proc.get("capacity") or {}).get("max_rate")), 0.0))
            for out in proc.get("outputs") or []:
                out_item = str((out or {}).get("item_id") or "")
                if not out_item:
                    continue
                lot_policy = process_lot_policy(proc, out_item=out_item, item_unit_map=item_unit_map)
                out_pair = (node_id, out_item)
                production_lot_policy_by_pair[out_pair] = lot_policy
                if cap_raw > 1e-9:
                    process_capacity_by_output_pair[out_pair] = max(
                        process_capacity_by_output_pair.get(out_pair, 0.0),
                        cap_raw,
                    )
                ref_qty = lot_reference_qty(lot_policy)
                if ref_qty > 1e-9:
                    production_lot_reference_qty_by_pair[out_pair] = max(
                        production_lot_reference_qty_by_pair.get(out_pair, 0.0),
                        ref_qty,
                    )
    # If a (node,item) can ship downstream but has no modeled inbound/production source,
    # treat missing upstream as external procurement to avoid artificial source depletion.
    externally_sourced_pairs = sorted(outbound_pairs - inbound_pairs - produced_pairs)
    externally_sourced_pairs_set = set(externally_sourced_pairs)
    demand_rows = scenario.get("demand", []) or []
    demand_pairs = [(str(d.get("node_id")), str(d.get("item_id"))) for d in demand_rows]
    finished_good_item_ids = {item_id for _, item_id in demand_pairs}
    demand_profiles = {
        (str(d.get("node_id")), str(d.get("item_id"))): (d.get("profile") or [])
        for d in demand_rows
    }
    mrp_signal_smoothing_days = (
        initialization_policy["mrp_demand_signal_smoothing_days"]
        if initialization_policy["use_bom_demand_signal_for_mrp"]
        else 1
    )
    mrp_demand_signal_source = (
        initialization_policy["mrp_demand_signal_source"]
        if initialization_policy["use_bom_demand_signal_for_mrp"]
        else "demand"
    )
    demand_target_daily = demand_targets_for_day(
        demand_profiles,
        0,
        window_days=mrp_signal_smoothing_days,
    )
    if (
        initialization_policy["use_bom_demand_signal_for_mrp"]
        and mrp_demand_signal_source == "mps_lotified"
    ):
        same_item_demand_daily = propagate_demand_rates(demand_target_daily, lanes)
        mps_component_signal_daily, _mps_output_signal_daily = lotified_mps_component_signal(
            same_item_demand_daily,
            day=0,
            process_input_requirements_by_output_pair=process_input_requirements_by_output_pair,
            production_lot_policy_by_pair=production_lot_policy_by_pair,
            process_capacity_by_output_pair=process_capacity_by_output_pair,
            mps_open_campaign_qty_by_pair=defaultdict(float),
            mps_started_lots_by_week_pair=defaultdict(int),
        )
        propagated_demand_daily = dict(same_item_demand_daily)
        for pair, qty in propagate_demand_rates(mps_component_signal_daily, lanes).items():
            propagated_demand_daily[pair] = propagated_demand_daily.get(pair, 0.0) + qty
    elif initialization_policy["use_bom_demand_signal_for_mrp"]:
        propagated_demand_daily = propagate_supply_demand_rates(
            demand_target_daily,
            lanes,
            process_input_requirements_by_output_pair,
        )
    else:
        propagated_demand_daily = propagate_demand_rates(demand_target_daily, lanes)
    if initialization_policy["use_bom_demand_signal_for_mrp"]:
        propagated_mrp_signal_pairs = set(
            propagate_supply_demand_rates(
                {pair: 1.0 for pair in demand_profiles},
                lanes,
                process_input_requirements_by_output_pair,
            )
        )
    else:
        propagated_mrp_signal_pairs = set()

    # Small safety target for pairs with demand signal if base stock is absent.
    for pair, d0 in propagated_demand_daily.items():
        if pair not in inbound_pairs:
            continue
        if base_stock.get(pair, 0.0) <= 0:
            base_stock[pair] = max(50.0, 7.0 * d0)

    backlog: dict[tuple[str, str], float] = defaultdict(float)
    pipeline: dict[int, list[tuple[str, str, float, str]]] = defaultdict(list)
    external_pipeline: dict[int, list[tuple[str, str, float]]] = defaultdict(list)
    estimated_source_pipeline: dict[int, list[tuple[str, str, float]]] = defaultdict(list)
    in_transit: dict[tuple[str, str], float] = defaultdict(float)
    external_in_transit: dict[tuple[str, str], float] = defaultdict(float)
    estimated_source_in_transit: dict[tuple[str, str], float] = defaultdict(float)

    total_demand = 0.0
    total_served = 0.0
    measurement_starting_backlog = 0.0
    warmup_backlog_cleared_qty = 0.0
    total_shipped = 0.0
    total_arrived = 0.0
    total_produced = 0.0
    total_transport_cost = 0.0
    total_holding_cost = 0.0
    total_warehouse_operating_cost = 0.0
    total_inventory_risk_cost = 0.0
    total_legacy_raw_holding_cost = 0.0
    total_external_procured = 0.0
    total_external_procured_arrived = 0.0
    total_external_procured_rejected = 0.0
    total_unreliable_loss_qty = 0.0
    total_purchase_cost = 0.0
    total_external_procurement_cost = 0.0
    total_estimated_source_replenished = 0.0
    total_estimated_source_ordered = 0.0
    total_estimated_source_rejected = 0.0

    daily_rows: list[dict[str, Any]] = []
    input_stock_rows: list[dict[str, Any]] = []
    output_prod_rows: list[dict[str, Any]] = []
    input_consumption_rows: list[dict[str, Any]] = []
    input_arrival_rows: list[dict[str, Any]] = []
    input_shipment_rows: list[dict[str, Any]] = []
    supplier_shipment_rows: list[dict[str, Any]] = []
    supplier_stock_rows: list[dict[str, Any]] = []
    dc_stock_rows: list[dict[str, Any]] = []
    demand_pair_rows: list[dict[str, Any]] = []
    production_constraint_rows: list[dict[str, Any]] = []
    mrp_trace_rows: list[dict[str, Any]] = []
    mrp_order_rows: list[dict[str, Any]] = []

    production_input_pairs: list[tuple[str, str]] = []
    production_output_pairs: list[tuple[str, str]] = []
    unconstrained_input_pairs: list[tuple[str, str]] = []
    input_unit_conversions_applied: set[tuple[str, str, str, str]] = set()
    input_unit_mismatch_not_converted: set[tuple[str, str, str, str]] = set()
    seen_input_pairs: set[tuple[str, str]] = set()
    seen_output_pairs: set[tuple[str, str]] = set()
    seen_unconstrained: set[tuple[str, str]] = set()
    stock_pairs = set(stock.keys())
    supplier_stock_pairs = sorted(
        {
            pair
            for pair in (stock_pairs | outbound_pairs)
            if pair[0] in supplier_node_ids
        }
    )
    dc_stock_pairs = sorted(
        {
            pair
            for pair in (stock_pairs | inbound_pairs | outbound_pairs)
            if pair[0] in dc_node_ids
        }
    )
    for n in nodes:
        nid = str(n.get("id"))
        for p in (n.get("processes") or []):
            for inp in (p.get("inputs") or []):
                key = (nid, str(inp.get("item_id")))
                # "Input production" means components that actually arrive via supply relations.
                if key in inbound_pairs and key not in seen_input_pairs:
                    seen_input_pairs.add(key)
                    production_input_pairs.append(key)
                # Inputs not represented by relations/inventory are treated as external/non-modeled.
                if key not in inbound_pairs and key not in stock_pairs and key not in seen_unconstrained:
                    seen_unconstrained.add(key)
                    unconstrained_input_pairs.append(key)
            for out in (p.get("outputs") or []):
                key = (nid, str(out.get("item_id")))
                if key not in seen_output_pairs:
                    seen_output_pairs.add(key)
                    production_output_pairs.append(key)
    production_input_pairs = sorted(production_input_pairs)
    production_output_pairs = sorted(production_output_pairs)
    mrp_trace_pairs = sorted(
        stock_pairs
        | inbound_pairs
        | set(demand_pairs)
        | produced_pairs
        | set(production_input_pairs)
        | set(production_output_pairs)
        | set(externally_sourced_pairs)
        | set(mrp_snapshot_pairs)
    )
    cum_output_by_pair: dict[tuple[str, str], float] = defaultdict(float)
    prev_production_command_by_pair: dict[tuple[str, str], float] = {}
    open_production_campaign_qty_by_pair: dict[tuple[str, str], float] = defaultdict(float)
    started_production_lots_by_week_pair: dict[tuple[int, tuple[str, str]], int] = defaultdict(int)
    mps_prev_production_command_by_pair: dict[tuple[str, str], float] = {}
    mps_open_campaign_qty_by_pair: dict[tuple[str, str], float] = defaultdict(float)
    mps_started_lots_by_week_pair: dict[tuple[int, tuple[str, str]], int] = defaultdict(int)
    pair_max_lead_days: dict[tuple[str, str], int] = {}
    pair_stock_cover_days: dict[tuple[str, str], int] = {}
    for pair, lane_list in lanes_by_dest_item.items():
        pair_max_lead_days[pair] = max(int(to_float(l.get("lead_days"), 1.0)) for l in lane_list) if lane_list else 1
        max_cover = max(lead_time_cover_days(l, args.stochastic_lead_times) for l in lane_list) if lane_list else 1
        pair_stock_cover_days[pair] = (
            max_cover + review_period_days + int(math.ceil(pair_mrp_safety_time_days.get(pair, 0.0)))
        )

    # Legacy bootstrap or explicit initial state preparation.
    opening_stock_bootstrap_rows: list[dict[str, Any]] = []
    total_opening_stock_bootstrap = 0.0
    initialization_state_rows: list[dict[str, Any]] = []
    initialization_pipeline_rows: list[dict[str, Any]] = []
    total_initialization_stock_added = 0.0
    total_initialization_pipeline_seeded = 0.0
    opening_open_order_rows: list[dict[str, Any]] = []
    total_opening_open_order_qty = 0.0
    opening_open_order_bridge_days_by_pair: dict[tuple[str, str], int] = {}
    assumptions_ledger_rows: list[dict[str, Any]] = []
    for lane in lanes:
        note = str(lane.get("standard_order_qty_note") or "")
        if not note:
            continue
        assumptions_ledger_rows.append(
            {
                "category": "data_quality_override",
                "node_id": str(lane.get("dst", "")),
                "item_id": str(lane.get("item_id", "")),
                "edge_id": str(lane.get("edge_id", "")),
                "source": "simulation_lane_standard_order_qty_override",
                "payload_json": json.dumps(
                    {
                        "src_node_id": str(lane.get("src", "")),
                        "dst_node_id": str(lane.get("dst", "")),
                        "item_id": str(lane.get("item_id", "")),
                        "standard_order_qty": round(max(0.0, to_float(lane.get("standard_order_qty"), 0.0)), 6),
                        "standard_order_uom": str(lane.get("standard_order_uom", "")),
                        "note": note,
                    },
                    ensure_ascii=False,
                    sort_keys=True,
                ),
            }
        )
    opening_stock_bootstrap_scale = max(
        0.0,
        to_float(scenario.get("opening_stock_bootstrap_scale", 1.0), 1.0),
    )
    required_daily_input_by_pair: dict[tuple[str, str], float] = defaultdict(float)
    for n in nodes:
        nid = str(n.get("id"))
        for p in (n.get("processes") or []):
            cap = to_float(((p.get("capacity") or {}).get("max_rate")), 0.0)
            if cap <= 0:
                continue
            batch_size = to_float(p.get("batch_size"), 1000.0)
            if batch_size <= 0:
                batch_size = 1000.0
            for inp in (p.get("inputs") or []):
                in_item = str(inp.get("item_id"))
                key = (nid, in_item)
                modeled_input = key in inbound_pairs or key in stock_pairs
                if not modeled_input:
                    continue
                ratio = to_float(inp.get("ratio_per_batch"), 0.0)
                req_per_unit_raw = ratio / batch_size if batch_size > 0 else 0.0
                input_unit = normalize_unit(inp.get("ratio_unit"))
                item_unit = normalize_unit(item_unit_map.get(in_item, input_unit))
                req_per_unit = convert_quantity(req_per_unit_raw, input_unit, item_unit)
                if req_per_unit > 0:
                    required_daily_input_by_pair[key] += cap * req_per_unit

    if initialization_policy["mode"] == "legacy_bootstrap":
        for pair, daily_req in required_daily_input_by_pair.items():
            cover_days = pair_stock_cover_days.get(pair, pair_max_lead_days.get(pair, 1) + review_period_days)
            target = max(
                base_stock.get(pair, 0.0),
                daily_req * float(cover_days),
                safety_stock_days * daily_req,
            )
            current = stock.get(pair, 0.0)
            target *= opening_stock_bootstrap_scale
            if target > current + 1e-9:
                add_qty = target - current
                stock[pair] = current + add_qty
                base_stock[pair] = target
                total_opening_stock_bootstrap += add_qty
                opening_stock_bootstrap_rows.append(
                    {
                        "node_id": pair[0],
                        "item_id": pair[1],
                        "lead_days": pair_max_lead_days.get(pair, 1),
                        "cover_days": cover_days,
                        "daily_req_at_cap": round(daily_req, 6),
                        "added_opening_qty": round(add_qty, 6),
                        "target_opening_stock": round(target, 6),
                    }
                )

    # Supplier/process nodes shipping an internally manufactured intermediate also need a finished-goods buffer.
    # Otherwise the simulation falls into pure JIT after a few days and the supplier stock chart suggests a false rupture.
    output_daily_signal_by_pair: dict[tuple[str, str], float] = defaultdict(float)
    for pair in sorted(produced_pairs & outbound_pairs):
        for lane in lanes_by_src_item.get(pair, []):
            dst_pair = (str(lane.get("dst")), pair[1])
            output_daily_signal_by_pair[pair] += required_daily_input_by_pair.get(dst_pair, 0.0)

    if initialization_policy["mode"] == "legacy_bootstrap":
        for pair, daily_signal in sorted(output_daily_signal_by_pair.items()):
            node_id, item_id = pair
            if node_id not in supplier_node_ids or daily_signal <= 0:
                continue
            downstream_cover_days = max(
                [lead_time_cover_days(l, args.stochastic_lead_times) for l in lanes_by_src_item.get(pair, [])] or [1]
            )
            process_tau_days = process_tau_days_by_pair.get(pair, 0.0)
            cover_days = max(
                downstream_cover_days + review_period_days,
                int(math.ceil(process_tau_days)) + review_period_days,
                int(math.ceil(safety_stock_days)),
            )
            target = max(base_stock.get(pair, 0.0), daily_signal * float(cover_days))
            target *= opening_stock_bootstrap_scale
            current = stock.get(pair, 0.0)
            if target > current + 1e-9:
                add_qty = target - current
                stock[pair] = current + add_qty
                base_stock[pair] = target
                total_opening_stock_bootstrap += add_qty
                opening_stock_bootstrap_rows.append(
                    {
                        "node_id": node_id,
                        "item_id": item_id,
                        "lead_days": downstream_cover_days,
                        "cover_days": cover_days,
                        "daily_req_at_cap": round(daily_signal, 6),
                        "added_opening_qty": round(add_qty, 6),
                        "target_opening_stock": round(target, 6),
                        "bootstrap_kind": "process_output_fg",
                    }
                )
    opening_stock_bootstrap_rows.sort(key=lambda r: (r["node_id"], r["item_id"]))

    supplier_daily_capacity_by_pair, supplier_capacity_metadata_rows = derive_supplier_daily_capacity_by_pair(
        nodes=nodes,
        supplier_node_ids=supplier_node_ids,
        lanes_by_src_item=lanes_by_src_item,
        required_daily_input_by_pair=required_daily_input_by_pair,
        propagated_demand_today=propagated_demand_daily,
        item_unit_map=item_unit_map,
        stock=stock,
        default_review_period_days=review_period_days,
        stochastic_lead_times=args.stochastic_lead_times,
    )
    estimated_source_policies, estimated_source_policy_rows = derive_unmodeled_supplier_source_policies(
        externally_sourced_pairs=externally_sourced_pairs,
        nodes=nodes,
        lanes_by_src_item=lanes_by_src_item,
        supplier_daily_capacity_by_pair=supplier_daily_capacity_by_pair,
        base_stock=base_stock,
        required_daily_input_by_pair=required_daily_input_by_pair,
        propagated_demand_today=propagated_demand_daily,
        default_review_period_days=review_period_days,
        safety_stock_days=safety_stock_days,
        stochastic_lead_times=args.stochastic_lead_times,
    )
    if initialization_policy["mode"] == "explicit_state":
        state_scale = initialization_policy["state_scale"]

        def ensure_stock_target(
            pair: tuple[str, str],
            target: float,
            *,
            category: str,
            daily_signal: float,
            cover_days: float,
        ) -> None:
            nonlocal total_initialization_stock_added
            raw_target = max(0.0, target)
            # Estimated upstream supplier sources need their opening buffer at full scale.
            # If we also shrink them with state_scale, the supplier can remain artificially
            # pinned at zero stock while shipping at full daily capacity.
            if category == "estimated_source_on_hand":
                target = max(base_stock.get(pair, 0.0), raw_target)
            else:
                target = max(base_stock.get(pair, 0.0), raw_target * state_scale)
            current = stock.get(pair, 0.0)
            if target <= current + 1e-9:
                base_stock[pair] = max(base_stock.get(pair, 0.0), target)
                return
            add_qty = target - current
            stock[pair] = current + add_qty
            base_stock[pair] = target
            total_initialization_stock_added += add_qty
            initialization_state_rows.append(
                {
                    "node_id": pair[0],
                    "item_id": pair[1],
                    "category": category,
                    "daily_signal": round(daily_signal, 6),
                    "cover_days": round(cover_days, 6),
                    "added_opening_qty": round(add_qty, 6),
                    "target_opening_stock": round(target, 6),
                }
            )

        def ensure_seeded_in_transit(
            pair: tuple[str, str],
            lane_list: list[dict[str, Any]],
            daily_signal: float,
            *,
            category: str,
        ) -> None:
            nonlocal total_initialization_pipeline_seeded
            if not initialization_policy["seed_in_transit"] or daily_signal <= 1e-9 or not lane_list:
                return
            fill_ratio = initialization_policy["in_transit_fill_ratio"]
            for lane in lane_list:
                lead_days = lead_time_cover_days(lane, args.stochastic_lead_times)
                if lead_days <= 0:
                    continue
                share = max(0.0, to_float(lane.get("mrp_share"), 0.0))
                if share <= 0:
                    share = 1.0 / float(len(lane_list))
                transit_qty = daily_signal * share * float(lead_days) * fill_ratio
                if transit_qty <= 1e-9:
                    continue
                seed_lane_pipeline_uniform(
                    pipeline,
                    in_transit,
                    dst=pair[0],
                    item_id=pair[1],
                    qty=transit_qty,
                    edge_id=str(lane.get("edge_id", "")),
                    lead_days=lead_days,
                )
                total_initialization_pipeline_seeded += transit_qty
                initialization_pipeline_rows.append(
                    {
                        "node_id": pair[0],
                        "item_id": pair[1],
                        "category": category,
                        "seeded_pipeline_qty": round(transit_qty, 6),
                        "lead_days": int(lead_days),
                        "lane_src": str(lane.get("src", "")),
                    }
                )

        for pair, daily_req in sorted(required_daily_input_by_pair.items()):
            if pair[0] not in process_node_ids or daily_req <= 1e-9:
                continue
            category_prefix = "factory" if node_type_by_id.get(pair[0]) == "factory" else "process_node"
            cover_days = (
                initialization_policy["factory_input_on_hand_days"]
                + pair_mrp_safety_time_days.get(pair, 0.0)
            )
            ensure_stock_target(
                pair,
                daily_req * cover_days,
                category=f"{category_prefix}_input_on_hand",
                daily_signal=daily_req,
                cover_days=cover_days,
            )
            ensure_seeded_in_transit(
                pair,
                lanes_by_dest_item.get(pair, []),
                daily_req,
                category=f"{category_prefix}_input_in_transit",
            )

        for pair, daily_signal in sorted(output_daily_signal_by_pair.items()):
            node_id, _item_id = pair
            if node_id not in supplier_node_ids or daily_signal <= 1e-9:
                continue
            cover_days = max(
                initialization_policy["supplier_output_on_hand_days"],
                float(review_period_days) + process_tau_days_by_pair.get(pair, 0.0) + pair_mrp_safety_time_days.get(pair, 0.0),
            )
            ensure_stock_target(
                pair,
                daily_signal * cover_days,
                category="supplier_output_on_hand",
                daily_signal=daily_signal,
                cover_days=cover_days,
            )

        dc_pairs = sorted({pair for pair in outbound_pairs if pair[0] in dc_node_ids})
        for pair in dc_pairs:
            daily_signal = max(0.0, propagated_demand_daily.get(pair, 0.0))
            if daily_signal <= 1e-9:
                continue
            cover_days = (
                initialization_policy["distribution_center_on_hand_days"]
                + pair_mrp_safety_time_days.get(pair, 0.0)
            )
            ensure_stock_target(
                pair,
                daily_signal * cover_days,
                category="distribution_center_on_hand",
                daily_signal=daily_signal,
                cover_days=cover_days,
            )
            ensure_seeded_in_transit(
                pair,
                lanes_by_dest_item.get(pair, []),
                daily_signal,
                category="distribution_center_in_transit",
            )

        customer_days = initialization_policy["customer_on_hand_days"]
        if customer_days > 0:
            for pair in sorted(demand_pairs):
                daily_signal = max(0.0, demand_target_daily.get(pair, 0.0))
                if daily_signal <= 1e-9:
                    continue
                ensure_stock_target(
                    pair,
                    daily_signal * customer_days,
                    category="customer_on_hand",
                    daily_signal=daily_signal,
                    cover_days=customer_days,
                )

        for src_pair, policy in sorted(estimated_source_policies.items()):
            ensure_stock_target(
                src_pair,
                to_float(policy.get("target_stock_qty_day0"), 0.0),
                category="estimated_source_on_hand",
                daily_signal=to_float(policy.get("daily_capacity_qty"), 0.0),
                cover_days=to_float(policy.get("target_cover_days"), 0.0),
            )
        if initialization_policy["seed_estimated_source_pipeline"]:
            for src_pair, policy in sorted(estimated_source_policies.items()):
                daily_capacity = max(0.0, to_float(policy.get("daily_capacity_qty"), 0.0))
                lead_days = max(1, int(to_float(policy.get("replenishment_lead_days"), 1.0)))
                transit_qty = daily_capacity * float(lead_days) * initialization_policy["in_transit_fill_ratio"] * state_scale
                if transit_qty <= 1e-9:
                    continue
                seed_external_pipeline_uniform(
                    estimated_source_pipeline,
                    estimated_source_in_transit,
                    node_id=src_pair[0],
                    item_id=src_pair[1],
                    qty=transit_qty,
                    lead_days=lead_days,
                )
                total_initialization_pipeline_seeded += transit_qty
                initialization_pipeline_rows.append(
                    {
                        "node_id": src_pair[0],
                        "item_id": src_pair[1],
                        "category": "estimated_source_in_transit",
                        "seeded_pipeline_qty": round(transit_qty, 6),
                        "lead_days": int(lead_days),
                        "lane_src": "unmodeled_source",
                    }
                )

        initialization_state_rows.sort(key=lambda r: (r["node_id"], r["item_id"], r["category"]))
        initialization_pipeline_rows.sort(key=lambda r: (r["node_id"], r["item_id"], r["category"]))
    if initialization_policy["seed_open_orders_from_january_snapshot"]:
        horizon_cap_days = initialization_policy["opening_open_orders_horizon_days"]
        if horizon_cap_days <= 0:
            inferred_horizon_candidates = [
                max(
                    1,
                    int(to_float(lane.get("lead_days"), 1.0))
                    + int(math.ceil(max(0.0, pair_mrp_safety_time_days.get((str(lane["dst"]), str(lane["item_id"])), 0.0)))),
                )
                for lane in lanes
            ]
            horizon_cap_days = max(inferred_horizon_candidates or [30])
        (
            total_opening_open_order_qty,
            opening_open_order_rows,
            opening_open_order_bridge_days_by_pair,
        ) = seed_open_orders_from_opening_snapshot(
            pipeline,
            in_transit,
            lanes=lanes,
            lanes_by_dest_item=lanes_by_dest_item,
            opening_stock_source_snapshot=opening_stock_source_snapshot,
            pair_mrp_safety_time_days=pair_mrp_safety_time_days,
            pair_mrp_safety_stock_qty=pair_mrp_safety_stock_qty,
            demand_profiles=demand_profiles,
            required_daily_input_by_pair=required_daily_input_by_pair,
            process_input_requirements_by_output_pair=process_input_requirements_by_output_pair,
            opening_open_orders_demand_multiplier=initialization_policy["opening_open_orders_demand_multiplier"],
            demand_pairs=demand_pairs,
            stochastic_lead_times=args.stochastic_lead_times,
            horizon_cap_days=horizon_cap_days,
            initialization_pipeline_rows=initialization_pipeline_rows,
            assumptions_ledger_rows=assumptions_ledger_rows,
        )
        total_initialization_pipeline_seeded += total_opening_open_order_qty
        initialization_pipeline_rows.sort(key=lambda r: (r["node_id"], r["item_id"], r["category"], r.get("lane_src", "")))
    supplier_capacity_daily_rows: list[dict[str, Any]] = []
    total_supplier_capacity_binding_qty = 0.0
    scheduled_lane_release_metrics: dict[int, list[tuple[tuple[str, str], float, float, float, float, bool]]] = defaultdict(list)

    def lane_transport_cost_for_chunk(
        lane: dict[str, Any],
        item_id: str,
        pull_qty: float,
        delivered_qty: float,
    ) -> tuple[float, str, float]:
        unit_transport_cost = max(0.0, to_float(lane.get("unit_transport_cost"), 0.0))
        standard_order_qty = max(0.0, to_float(lane.get("standard_order_qty"), 0.0))
        if item_id not in finished_good_item_ids and standard_order_qty > 1e-9:
            effective_lot_qty = standard_order_qty
            if effective_lot_qty <= 1.0 + 1e-9:
                effective_lot_qty = max(
                    effective_lot_qty,
                    production_lot_reference_qty_by_pair.get((str(lane.get("src")), item_id), 0.0),
                )
            lot_units = max(0.0, pull_qty) / effective_lot_qty
            return lot_units * unit_transport_cost, "lot", lot_units
        return max(0.0, delivered_qty) * unit_transport_cost, "unit", max(0.0, delivered_qty)

    for day in range(total_timeline_days):
        record_day = day >= warmup_days
        output_day = day - warmup_days
        profile_day = day if day < warmup_days else output_day
        if (
            day == warmup_days
            and warmup_days > 0
            and initialization_policy.get("restore_opening_stock_after_warmup")
        ):
            for pair in list(set(stock.keys()) | set(opening_stock_source_snapshot.keys())):
                stock[pair] = max(0.0, opening_stock_source_snapshot.get(pair, 0.0))
        if day == warmup_days and reset_backlog_after_warmup:
            warmup_backlog_cleared_qty = sum(max(0.0, val) for val in backlog.values())
            for pair in list(backlog.keys()):
                backlog[pair] = 0.0
        backlog_start_of_day_by_pair = {
            pair: max(0.0, backlog.get(pair, 0.0))
            for pair in mrp_trace_pairs
        }
        raw_demand_target_today = demand_targets_for_day(
            demand_profiles,
            profile_day,
            window_days=1,
        )
        demand_target_today = demand_targets_for_day(
            demand_profiles,
            profile_day,
            window_days=mrp_signal_smoothing_days,
        )
        if (
            initialization_policy["use_bom_demand_signal_for_mrp"]
            and mrp_demand_signal_source == "mps_lotified"
        ):
            raw_propagated_demand_today = propagate_supply_demand_rates(
                raw_demand_target_today,
                lanes,
                process_input_requirements_by_output_pair,
            )
            same_item_demand_today = propagate_demand_rates(demand_target_today, lanes)
            mps_output_command_today: dict[tuple[str, str], float] = {}
            for out_pair in process_input_requirements_by_output_pair:
                out_signal = max(
                    0.0,
                    same_item_demand_today.get(out_pair, 0.0),
                    output_daily_signal_by_pair.get(out_pair, 0.0),
                )
                out_stock = max(0.0, stock[out_pair])
                out_target = max(base_stock.get(out_pair, 0.0), fg_target_days * out_signal)
                raw_command = out_signal + production_gap_gain * (out_target - out_stock)
                if out_signal <= 1e-9 and out_pair not in lanes_by_src_item:
                    raw_command = 0.0
                prev_cmd = mps_prev_production_command_by_pair.get(out_pair, raw_command)
                desired_qty = production_smoothing * prev_cmd + (1.0 - production_smoothing) * raw_command
                desired_qty = max(0.0, desired_qty)
                mps_prev_production_command_by_pair[out_pair] = desired_qty
                if desired_qty > 1e-9:
                    mps_output_command_today[out_pair] = desired_qty
            mps_component_signal_today, _mps_output_signal_today = lotified_mps_component_signal(
                mps_output_command_today,
                day=day,
                process_input_requirements_by_output_pair=process_input_requirements_by_output_pair,
                production_lot_policy_by_pair=production_lot_policy_by_pair,
                process_capacity_by_output_pair=process_capacity_by_output_pair,
                mps_open_campaign_qty_by_pair=mps_open_campaign_qty_by_pair,
                mps_started_lots_by_week_pair=mps_started_lots_by_week_pair,
            )
            propagated_demand_today = dict(same_item_demand_today)
            for pair, qty in propagate_demand_rates(mps_component_signal_today, lanes).items():
                propagated_demand_today[pair] = propagated_demand_today.get(pair, 0.0) + qty
        elif initialization_policy["use_bom_demand_signal_for_mrp"]:
            raw_propagated_demand_today = propagate_supply_demand_rates(
                raw_demand_target_today,
                lanes,
                process_input_requirements_by_output_pair,
            )
            propagated_demand_today = propagate_supply_demand_rates(
                demand_target_today,
                lanes,
                process_input_requirements_by_output_pair,
            )
        else:
            raw_propagated_demand_today = propagate_demand_rates(raw_demand_target_today, lanes)
            propagated_demand_today = propagate_demand_rates(demand_target_today, lanes)

        arrivals_today = pipeline.pop(day, [])
        external_arrivals_today = external_pipeline.pop(day, [])
        estimated_source_arrivals_today = estimated_source_pipeline.pop(day, [])
        arrivals_qty = 0.0
        external_arrivals_qty = 0.0
        estimated_source_arrivals_qty = 0.0
        arrivals_today_by_pair: dict[tuple[str, str], float] = defaultdict(float)
        external_arrivals_today_by_pair: dict[tuple[str, str], float] = defaultdict(float)
        estimated_source_arrivals_today_by_pair: dict[tuple[str, str], float] = defaultdict(float)
        for dst, item_id, qty, _lane_id in arrivals_today:
            stock[(dst, item_id)] += qty
            in_transit[(dst, item_id)] -= qty
            arrivals_qty += qty
            arrivals_today_by_pair[(dst, item_id)] += qty
        for src, item_id, qty in external_arrivals_today:
            stock[(src, item_id)] += qty
            external_in_transit[(src, item_id)] -= qty
            external_arrivals_qty += qty
            external_arrivals_today_by_pair[(src, item_id)] += qty
        for src, item_id, qty in estimated_source_arrivals_today:
            stock[(src, item_id)] += qty
            estimated_source_in_transit[(src, item_id)] -= qty
            estimated_source_arrivals_qty += qty
            estimated_source_arrivals_today_by_pair[(src, item_id)] += qty
        if record_day:
            total_arrived += arrivals_qty
            total_external_procured_arrived += external_arrivals_qty
            total_estimated_source_replenished += estimated_source_arrivals_qty

        estimated_source_ordered_today = 0.0
        estimated_source_rejected_today = 0.0
        if unmodeled_supplier_source_mode == "estimated_replenishment":
            for src_pair, policy in estimated_source_policies.items():
                downstream_requirement = allocate_shared_downstream_pull(
                    src_pair=src_pair,
                    lanes_by_src_item=lanes_by_src_item,
                    externally_sourced_pairs=externally_sourced_pairs,
                    supplier_daily_capacity_by_pair=supplier_daily_capacity_by_pair,
                    downstream_values_by_pair=required_daily_input_by_pair,
                )
                downstream_signal = allocate_shared_downstream_pull(
                    src_pair=src_pair,
                    lanes_by_src_item=lanes_by_src_item,
                    externally_sourced_pairs=externally_sourced_pairs,
                    supplier_daily_capacity_by_pair=supplier_daily_capacity_by_pair,
                    downstream_values_by_pair=propagated_demand_today,
                )
                demand_anchor = max(downstream_requirement, downstream_signal)
                target_stock_qty = max(
                    base_stock.get(src_pair, 0.0),
                    demand_anchor * float(policy["target_cover_days"]),
                )
                inventory_position = stock.get(src_pair, 0.0) + estimated_source_in_transit.get(src_pair, 0.0)
                desired_order_qty = max(0.0, target_stock_qty - inventory_position)
                daily_capacity = max(0.0, to_float(policy.get("daily_capacity_qty"), 0.0))
                order_qty = min(desired_order_qty, daily_capacity)
                if order_qty > 1e-9:
                    arrival_day = day + int(policy["replenishment_lead_days"])
                    estimated_source_pipeline[arrival_day].append((src_pair[0], src_pair[1], order_qty))
                    estimated_source_in_transit[src_pair] += order_qty
                    register_mrp_order(
                        src_pair,
                        source_mode="estimated_source",
                        src_node_id="ESTIMATED_SOURCE",
                        dst_node_id=src_pair[0],
                        item_id=src_pair[1],
                        release_qty=order_qty,
                        receipt_qty=order_qty,
                        arrival_day=arrival_day,
                        safety_time_days=pair_mrp_safety_time_days.get(src_pair, 0.0),
                        lead_days=int(policy["replenishment_lead_days"]),
                        lead_cover_days=int(policy["replenishment_lead_days"]),
                    )
                    estimated_source_ordered_today += order_qty
                estimated_source_rejected_today += max(0.0, desired_order_qty - order_qty)
        elif unmodeled_supplier_source_mode == "estimated_capacity":
            for src_pair in externally_sourced_pairs:
                if src_pair not in supplier_daily_capacity_by_pair:
                    continue
                replenished_qty = max(0.0, supplier_daily_capacity_by_pair.get(src_pair, 0.0))
                if replenished_qty <= 1e-9:
                    continue
                stock[src_pair] += replenished_qty
                estimated_source_arrivals_qty += replenished_qty
                total_estimated_source_replenished += replenished_qty
        if record_day:
            total_estimated_source_ordered += estimated_source_ordered_today
            total_estimated_source_rejected += estimated_source_rejected_today

        # Snapshot: raw material stocks at production input before production starts.
        day_input_rows_by_pair: dict[tuple[str, str], dict[str, Any]] = {}
        if record_day:
            for node_id, item_id in production_input_pairs:
                row = {
                    "day": output_day,
                    "node_id": node_id,
                    "item_id": item_id,
                    "stock_before_production": round(stock[(node_id, item_id)], 6),
                    "stock_end_of_day": 0.0,
                }
                input_stock_rows.append(row)
                day_input_rows_by_pair[(node_id, item_id)] = row
                input_arrival_rows.append(
                    {
                        "day": output_day,
                        "node_id": node_id,
                        "item_id": item_id,
                        "arrived_qty": round(arrivals_today_by_pair[(node_id, item_id)], 6),
                        "uom": item_unit_map.get(item_id, ""),
                    }
                )

        # Production/transformation
        produced_today = 0.0
        produced_today_by_pair: dict[tuple[str, str], float] = defaultdict(float)
        consumed_today_by_pair: dict[tuple[str, str], float] = defaultdict(float)
        for n in nodes:
            nid = str(n.get("id"))
            for p in (n.get("processes") or []):
                outputs = p.get("outputs") or []
                if not outputs:
                    continue
                out_item = str((outputs[0] or {}).get("item_id"))
                cap_raw = to_float(((p.get("capacity") or {}).get("max_rate")), 0.0)
                has_capacity_limit = cap_raw > 0.0
                # Missing capacity data means "capacity not modeled", not "zero capacity".
                # Lot rules, input availability and demand signal still constrain execution.
                cap = cap_raw if has_capacity_limit else float("inf")

                batch_size = to_float(p.get("batch_size"), 1000.0)
                if batch_size <= 0:
                    batch_size = 1000.0

                input_limits = []
                for inp in (p.get("inputs") or []):
                    in_item = str(inp.get("item_id"))
                    key = (nid, in_item)
                    modeled_input = key in inbound_pairs or key in stock_pairs
                    if not modeled_input:
                        # Input not present in Relations_acteurs/stock model: do not constrain run.
                        continue
                    ratio = to_float(inp.get("ratio_per_batch"), 0.0)
                    req_per_unit_raw = ratio / batch_size if batch_size > 0 else 0.0
                    input_unit = normalize_unit(inp.get("ratio_unit"))
                    item_unit = normalize_unit(item_unit_map.get(in_item, input_unit))
                    if input_unit and item_unit and input_unit != item_unit:
                        if can_convert_units(input_unit, item_unit):
                            input_unit_conversions_applied.add((nid, in_item, input_unit, item_unit))
                        else:
                            input_unit_mismatch_not_converted.add((nid, in_item, input_unit, item_unit))
                    req_per_unit = convert_quantity(req_per_unit_raw, input_unit, item_unit)
                    if req_per_unit > 0:
                        input_limits.append(stock[key] / req_per_unit)

                max_from_inputs = min(input_limits) if input_limits else cap
                out_pair = (nid, out_item)
                lot_policy = process_lot_policy(p, out_item=out_item, item_unit_map=item_unit_map)
                # For internally manufactured intermediates, rely on downstream
                # process requirements as well as customer-demand propagation.
                out_signal = max(
                    0.0,
                    propagated_demand_today.get(out_pair, 0.0),
                    output_daily_signal_by_pair.get(out_pair, 0.0),
                )
                out_stock = max(0.0, stock[out_pair])
                out_target = max(base_stock.get(out_pair, 0.0), fg_target_days * out_signal)
                out_gap = out_target - out_stock
                raw_command = out_signal + production_gap_gain * out_gap

                if out_signal <= 1e-9 and out_pair not in lanes_by_src_item:
                    # Preserve previous behavior for isolated processes not linked to demand flow.
                    raw_command = cap if has_capacity_limit else 0.0

                prev_cmd = prev_production_command_by_pair.get(out_pair, raw_command)
                desired_qty = production_smoothing * prev_cmd + (1.0 - production_smoothing) * raw_command
                desired_qty = max(0.0, desired_qty)
                prev_production_command_by_pair[out_pair] = desired_qty
                campaign_remaining_start_qty = max(0.0, open_production_campaign_qty_by_pair.get(out_pair, 0.0))
                campaign_started_qty = 0.0
                campaign_requested_qty = 0.0
                lot_planned_qty = desired_qty
                week_index = int(day // 7)
                week_key = (week_index, out_pair)
                started_lots_this_week = int(started_production_lots_by_week_pair.get(week_key, 0))
                requested_lot_starts = 0
                actual_lot_starts = 0
                weekly_lot_limit = max(0, int(math.floor(to_float(lot_policy.get("max_lots_per_week"), 0.0))))
                lot_weekly_limit_blocked = False
                if lot_policy["enabled"]:
                    if campaign_remaining_start_qty <= 1e-9 and desired_qty > 1e-9:
                        campaign_requested_qty = launch_campaign_qty(desired_qty, lot_policy)
                        requested_lot_starts = campaign_lot_count(campaign_requested_qty, lot_policy)
                        campaign_started_qty = campaign_requested_qty
                        if weekly_lot_limit > 0:
                            available_lot_starts = max(0, weekly_lot_limit - started_lots_this_week)
                            campaign_started_qty = limit_campaign_qty_by_weekly_lots(
                                campaign_requested_qty,
                                lot_policy,
                                available_lot_starts,
                            )
                            actual_lot_starts = campaign_lot_count(campaign_started_qty, lot_policy)
                            lot_weekly_limit_blocked = actual_lot_starts < requested_lot_starts
                        else:
                            actual_lot_starts = requested_lot_starts
                        campaign_remaining_start_qty = campaign_started_qty
                        open_production_campaign_qty_by_pair[out_pair] = campaign_started_qty
                        if actual_lot_starts > 0:
                            started_production_lots_by_week_pair[week_key] = started_lots_this_week + actual_lot_starts
                            started_lots_this_week = int(started_production_lots_by_week_pair[week_key])
                    lot_planned_qty = campaign_remaining_start_qty

                qty = max(0.0, min(cap, max_from_inputs, lot_planned_qty))
                binding_cause = "none"
                binding_item = ""
                if desired_qty > 1e-9 or campaign_remaining_start_qty > 1e-9:
                    input_binding_item = ""
                    input_binding_value = float("inf")
                    for inp in (p.get("inputs") or []):
                        in_item = str(inp.get("item_id"))
                        key = (nid, in_item)
                        modeled_input = key in inbound_pairs or key in stock_pairs
                        if not modeled_input:
                            continue
                        ratio = to_float(inp.get("ratio_per_batch"), 0.0)
                        req_per_unit_raw = ratio / batch_size if batch_size > 0 else 0.0
                        input_unit = normalize_unit(inp.get("ratio_unit"))
                        item_unit = normalize_unit(item_unit_map.get(in_item, input_unit))
                        req_per_unit = convert_quantity(req_per_unit_raw, input_unit, item_unit)
                        if req_per_unit <= 0:
                            continue
                        item_limit = stock[key] / req_per_unit
                        if item_limit < input_binding_value:
                            input_binding_value = item_limit
                            input_binding_item = in_item
                    binding_reference_qty = lot_planned_qty if lot_policy["enabled"] else desired_qty
                    if lot_weekly_limit_blocked and campaign_remaining_start_qty <= 1e-9 and desired_qty > 1e-9:
                        binding_cause = "weekly_lot_limit"
                    elif lot_policy["enabled"] and campaign_remaining_start_qty > 1e-9 and qty <= 1e-9:
                        binding_cause = "lot_campaign_blocked"
                    elif qty + 1e-9 < binding_reference_qty:
                        if max_from_inputs <= cap + 1e-9 and max_from_inputs <= binding_reference_qty + 1e-9:
                            binding_cause = "input_shortage"
                            binding_item = input_binding_item
                        elif has_capacity_limit and cap <= max_from_inputs + 1e-9 and cap <= binding_reference_qty + 1e-9:
                            binding_cause = "capacity"
                        else:
                            binding_cause = "policy_command"
                    if record_day:
                        cap_qty_for_record = cap if has_capacity_limit else 0.0
                        input_qty_for_record = max_from_inputs if math.isfinite(max_from_inputs) else 0.0
                        production_constraint_rows.append(
                            {
                                "day": output_day,
                                "node_id": nid,
                                "output_item_id": out_item,
                                "desired_qty": round(desired_qty, 6),
                                "planned_qty_after_lot_rule": round(lot_planned_qty, 6),
                                "actual_qty": round(qty, 6),
                                "cap_qty": round(cap_qty_for_record, 6),
                                "capacity_limit_mode": "finite" if has_capacity_limit else "unmodeled",
                                "max_from_inputs_qty": round(input_qty_for_record, 6),
                                "binding_cause": binding_cause,
                                "binding_input_item_id": binding_item,
                                "shortfall_vs_desired_qty": round(max(0.0, desired_qty - qty), 6),
                                "shortfall_vs_lot_plan_qty": round(max(0.0, lot_planned_qty - qty), 6),
                                "lot_policy_mode": (
                                    "fixed"
                                    if lot_policy.get("fixed_lot_qty", 0.0) > 1e-9
                                    else "min_max"
                                    if lot_policy["enabled"]
                                    else "none"
                                ),
                                "lot_fixed_qty": round(to_float(lot_policy.get("fixed_lot_qty"), 0.0), 6),
                                "lot_min_qty": round(to_float(lot_policy.get("min_lot_qty"), 0.0), 6),
                                "lot_max_qty": round(to_float(lot_policy.get("max_lot_qty"), 0.0), 6),
                                "lot_multiple_qty": round(to_float(lot_policy.get("lot_multiple_qty"), 0.0), 6),
                                "max_lots_per_week": weekly_lot_limit,
                                "started_lots_this_week": started_lots_this_week,
                                "requested_lot_starts": requested_lot_starts,
                                "actual_lot_starts": actual_lot_starts,
                                "campaign_requested_qty": round(campaign_requested_qty, 6),
                                "campaign_started_qty": round(campaign_started_qty, 6),
                                "campaign_remaining_start_qty": round(campaign_remaining_start_qty, 6),
                                "campaign_remaining_end_qty": round(max(0.0, campaign_remaining_start_qty - qty), 6),
                            }
                        )
                if qty <= 0:
                    continue

                for inp in (p.get("inputs") or []):
                    in_item = str(inp.get("item_id"))
                    key = (nid, in_item)
                    modeled_input = key in inbound_pairs or key in stock_pairs
                    if not modeled_input:
                        continue
                    ratio = to_float(inp.get("ratio_per_batch"), 0.0)
                    req_per_unit_raw = ratio / batch_size if batch_size > 0 else 0.0
                    input_unit = normalize_unit(inp.get("ratio_unit"))
                    item_unit = normalize_unit(item_unit_map.get(in_item, input_unit))
                    req_per_unit = convert_quantity(req_per_unit_raw, input_unit, item_unit)
                    if req_per_unit > 0:
                        consumed = qty * req_per_unit
                        stock[key] -= consumed
                        consumed_today_by_pair[key] += consumed

                stock[(nid, out_item)] += qty
                produced_today += qty
                produced_today_by_pair[(nid, out_item)] += qty
                if lot_policy["enabled"]:
                    open_production_campaign_qty_by_pair[out_pair] = max(0.0, campaign_remaining_start_qty - qty)

        if record_day:
            total_produced += produced_today
            for node_id, item_id in production_output_pairs:
                q = produced_today_by_pair[(node_id, item_id)]
                cum_output_by_pair[(node_id, item_id)] += q
                output_prod_rows.append(
                    {
                        "day": output_day,
                        "node_id": node_id,
                        "item_id": item_id,
                        "produced_qty": round(q, 6),
                        "cum_produced_qty": round(cum_output_by_pair[(node_id, item_id)], 6),
                        "stock_end_of_day": round(stock[(node_id, item_id)], 6),
                    }
                )
            for node_id, item_id in production_input_pairs:
                input_consumption_rows.append(
                    {
                        "day": output_day,
                        "node_id": node_id,
                        "item_id": item_id,
                        "consumed_qty": round(consumed_today_by_pair[(node_id, item_id)], 6),
                        "uom": item_unit_map.get(item_id, ""),
                    }
                )

        if record_day and day == warmup_days and not reset_backlog_after_warmup:
            measurement_starting_backlog = sum(max(0.0, val) for val in backlog.values())

        # Demand satisfaction
        demand_today = 0.0
        served_today = 0.0
        for pair in demand_pairs:
            dval = demand_target_today.get(pair, 0.0)
            required = backlog[pair] + dval
            available = stock[pair]
            served = min(available, required)
            stock[pair] -= served
            backlog[pair] = required - served
            demand_today += dval
            served_today += served
            if record_day:
                demand_pair_rows.append(
                    {
                        "day": output_day,
                        "node_id": pair[0],
                        "item_id": pair[1],
                        "demand_qty": round(dval, 6),
                        "required_with_backlog_qty": round(required, 6),
                        "served_qty": round(served, 6),
                        "backlog_end_qty": round(backlog[pair], 6),
                        "available_before_service_qty": round(available, 6),
                    }
                )

        if record_day:
            total_demand += demand_today
            total_served += served_today

        # Replenishment and shipments
        shipped_today = 0.0
        transport_cost_today = 0.0
        opening_transport_cost_today = 0.0
        purchase_cost_today = 0.0
        opening_purchase_cost_today = 0.0
        external_procurement_transport_cost_today = 0.0
        external_procurement_purchase_cost_today = 0.0
        external_procured_today = 0.0
        external_procured_rejected_today = 0.0
        supplier_capacity_binding_qty_today = 0.0
        shipped_today_to_pair: dict[tuple[str, str], float] = defaultdict(float)
        external_ordered_today_by_src_pair: dict[tuple[str, str], float] = defaultdict(float)
        supplier_capacity_used_today_by_src_pair: dict[tuple[str, str], float] = defaultdict(float)
        planned_release_today_by_pair: dict[tuple[str, str], float] = defaultdict(float)
        planned_receipt_today_by_pair: dict[tuple[str, str], float] = defaultdict(float)
        planned_order_count_by_pair: dict[tuple[str, str], int] = defaultdict(int)
        planned_receipt_min_day_by_pair: dict[tuple[str, str], int] = {}
        planned_receipt_max_day_by_pair: dict[tuple[str, str], int] = {}
        for metric_pair, metric_shipped, metric_transport, metric_purchase, metric_loss, metric_is_opening in scheduled_lane_release_metrics.pop(day, []):
            shipped_today += metric_shipped
            shipped_today_to_pair[metric_pair] += metric_shipped
            transport_cost_today += metric_transport
            purchase_cost_today += metric_purchase
            total_unreliable_loss_qty += metric_loss
            if metric_is_opening:
                opening_transport_cost_today += metric_transport
                opening_purchase_cost_today += metric_purchase

        def register_mrp_order(
            trace_pair: tuple[str, str],
            *,
            source_mode: str,
            src_node_id: str,
            dst_node_id: str,
            item_id: str,
            release_qty: float,
            receipt_qty: float,
            arrival_day: int,
            safety_time_days: float,
            lead_days: int,
            lead_cover_days: int | None = None,
            edge_id: str = "",
            reliability: float = 1.0,
            standard_order_qty: float = 0.0,
            mrp_share: float = 0.0,
            physical_release_day: int | None = None,
        ) -> None:
            planned_release_today_by_pair[trace_pair] += max(0.0, release_qty)
            planned_receipt_today_by_pair[trace_pair] += max(0.0, receipt_qty)
            planned_order_count_by_pair[trace_pair] += 1
            previous_min = planned_receipt_min_day_by_pair.get(trace_pair)
            previous_max = planned_receipt_max_day_by_pair.get(trace_pair)
            planned_receipt_min_day_by_pair[trace_pair] = (
                arrival_day if previous_min is None else min(previous_min, arrival_day)
            )
            planned_receipt_max_day_by_pair[trace_pair] = (
                arrival_day if previous_max is None else max(previous_max, arrival_day)
            )
            if not record_day:
                return
            safety_days_int = int(math.ceil(max(0.0, safety_time_days)))
            cover_need_day = arrival_day + safety_days_int
            effective_lead_cover_days = int(max(1, lead_cover_days if lead_cover_days is not None else lead_days))
            order_date_imt = cover_need_day - safety_days_int - effective_lead_cover_days
            release_day_for_output = (
                int(physical_release_day) if physical_release_day is not None else output_day
            )
            order_status_end_of_run = "received" if arrival_day < total_timeline_days else "released_in_transit"
            actual_receipt_day = int(arrival_day - warmup_days) if arrival_day >= warmup_days and arrival_day < total_timeline_days else ""
            mrp_order_rows.append(
                {
                    "day": output_day,
                    "node_id": trace_pair[0],
                    "item_id": item_id,
                    "order_type": source_mode,
                    "src_node_id": src_node_id,
                    "dst_node_id": dst_node_id,
                    "edge_id": edge_id,
                    "planning_status": "planned_and_released",
                    "release_status": "released",
                    "receipt_status": "firm_receipt" if arrival_day < total_timeline_days else "firm_receipt_outside_horizon",
                    "order_status_end_of_run": order_status_end_of_run,
                    "release_qty": round(release_qty, 6),
                    "planned_receipt_qty": round(receipt_qty, 6),
                    "release_day": int(release_day_for_output - warmup_days),
                    "order_date_imt": int(order_date_imt - warmup_days),
                    "arrival_day": int(arrival_day - warmup_days),
                    "actual_receipt_day": actual_receipt_day,
                    "implied_cover_need_day": int(cover_need_day - warmup_days),
                    "lead_days": int(lead_days),
                    "lead_cover_days": int(effective_lead_cover_days),
                    "safety_time_days": round(max(0.0, safety_time_days), 6),
                    "reliability": round(reliability, 6),
                    "standard_order_qty": round(max(0.0, standard_order_qty), 6),
                        "mrp_share": round(max(0.0, mrp_share), 6),
                    }
                )

        if (
            unmodeled_supplier_source_mode == "external_procurement"
            and economic_policy["external_procurement_enabled"]
            and economic_policy["external_procurement_proactive_replenishment"]
        ):
            ext_lead_days = int(economic_policy["external_procurement_lead_days"])
            for src_pair, policy in estimated_source_policies.items():
                downstream_requirement = allocate_shared_downstream_pull(
                    src_pair=src_pair,
                    lanes_by_src_item=lanes_by_src_item,
                    externally_sourced_pairs=externally_sourced_pairs,
                    supplier_daily_capacity_by_pair=supplier_daily_capacity_by_pair,
                    downstream_values_by_pair=required_daily_input_by_pair,
                )
                downstream_signal = allocate_shared_downstream_pull(
                    src_pair=src_pair,
                    lanes_by_src_item=lanes_by_src_item,
                    externally_sourced_pairs=externally_sourced_pairs,
                    supplier_daily_capacity_by_pair=supplier_daily_capacity_by_pair,
                    downstream_values_by_pair=propagated_demand_today,
                )
                demand_anchor = max(downstream_requirement, downstream_signal)
                if demand_anchor <= 1e-9:
                    continue
                # External procurement is a source replenishment buffer, not the
                # full downstream factory MRP target. Keeping it close to the
                # external lead time avoids overfilling high-volume suppliers
                # while still preventing reactive "order only at zero" behavior.
                target_cover_days = max(1.0, float(ext_lead_days))
                target_stock_qty = max(
                    max(0.0, to_float(policy.get("downstream_lot_floor_qty"), 0.0)),
                    demand_anchor * target_cover_days,
                )
                inventory_position = (
                    max(0.0, stock.get(src_pair, 0.0))
                    + max(0.0, external_in_transit.get(src_pair, 0.0))
                    + max(0.0, estimated_source_in_transit.get(src_pair, 0.0))
                )
                desired_order_qty = max(0.0, target_stock_qty - inventory_position)
                if desired_order_qty <= 1e-9:
                    continue
                ext_cap_today = max(
                    economic_policy["external_procurement_min_daily_cap_qty"],
                    economic_policy["external_procurement_daily_cap_days"] * demand_anchor,
                )
                ext_cap_left = max(0.0, ext_cap_today - external_ordered_today_by_src_pair[src_pair])
                ext_order_qty = min(desired_order_qty, ext_cap_left)
                if ext_order_qty <= 1e-9:
                    if record_day:
                        external_procured_rejected_today += desired_order_qty
                    continue
                ext_arrival_day = day + ext_lead_days
                external_pipeline[ext_arrival_day].append((src_pair[0], src_pair[1], ext_order_qty))
                external_in_transit[src_pair] += ext_order_qty
                external_ordered_today_by_src_pair[src_pair] += ext_order_qty
                register_mrp_order(
                    src_pair,
                    source_mode="external_procurement_proactive",
                    src_node_id="EXTERNAL_MARKET",
                    dst_node_id=src_pair[0],
                    item_id=src_pair[1],
                    release_qty=ext_order_qty,
                    receipt_qty=ext_order_qty,
                    arrival_day=ext_arrival_day,
                    safety_time_days=pair_mrp_safety_time_days.get(src_pair, 0.0),
                    lead_days=ext_lead_days,
                    lead_cover_days=ext_lead_days,
                )
                ref_lane_purchase = max(
                    [max(0.0, to_float(lane.get("unit_purchase_cost"), 0.0)) for lane in lanes_by_src_item.get(src_pair, [])]
                    or [0.0]
                )
                ref_purchase = max(economic_policy["purchase_cost_floor_per_unit"], ref_lane_purchase)
                ext_unit_purchase = max(
                    economic_policy["external_procurement_unit_cost"],
                    ref_purchase * economic_policy["external_procurement_cost_multiplier"],
                )
                ext_unit_transport = economic_policy["external_procurement_transport_cost_per_unit"]
                ext_purchase_cost = ext_order_qty * ext_unit_purchase
                ext_transport_cost = ext_order_qty * ext_unit_transport
                if record_day:
                    external_procured_today += ext_order_qty
                    purchase_cost_today += ext_purchase_cost
                    transport_cost_today += ext_transport_cost
                    external_procurement_purchase_cost_today += ext_purchase_cost
                    external_procurement_transport_cost_today += ext_transport_cost
                    total_external_procurement_cost += ext_order_qty * (ext_unit_purchase + ext_unit_transport)
                    external_procured_rejected_today += max(0.0, desired_order_qty - ext_order_qty)
        for pair, lane_list in lanes_by_dest_item.items():
            dst, item_id = pair
            target = max(base_stock.get(pair, 0.0), 0.0)
            static_daily_req = max(0.0, required_daily_input_by_pair.get(pair, 0.0))
            dynamic_daily_req = max(0.0, propagated_demand_today.get(pair, 0.0))
            if dynamic_daily_req > 1e-9:
                # Use the propagated downstream demand signal for day-to-day supplier
                # replenishment targets. The static engineering requirement remains a
                # fallback for items that currently have no propagated demand, but it
                # should not force long-lead suppliers into a flat, capped shipment
                # profile when downstream demand and production actually vary.
                item_daily_req = dynamic_daily_req
            elif (
                initialization_policy["use_bom_demand_signal_for_mrp"]
                and not initialization_policy["mrp_static_fallback_for_propagated_pairs"]
                and pair in propagated_mrp_signal_pairs
            ):
                item_daily_req = 0.0
            else:
                item_daily_req = static_daily_req
            soft_safety_target_qty = target
            if item_daily_req > 0:
                soft_safety_target_qty = max(
                    target,
                    item_daily_req
                    * max(0.0, pair_mrp_safety_time_days.get(pair, 0.0))
                    * initialization_policy["soft_safety_time_stock_target_factor"],
                )
                target = max(target, soft_safety_target_qty)
                target = max(target, safety_stock_days * item_daily_req)
                if pair in demand_pairs and demand_stock_target_days > 0.0:
                    target = max(target, demand_stock_target_days * item_daily_req)
                if pair not in mrp_snapshot_pairs:
                    effective_cover_days = float(pair_stock_cover_days.get(pair, review_period_days + 1))
                    if initialization_policy["seed_open_orders_from_january_snapshot"]:
                        effective_cover_days = max(
                            0.0,
                            effective_cover_days - float(opening_open_order_bridge_days_by_pair.get(pair, 0)),
                        )
                    target = max(
                        target,
                        item_daily_req * effective_cover_days,
                    )
            else:
                target = max(target, 0.0)
            target += backlog[pair]

            if day % review_period_days != 0:
                continue

            needed = target - stock[pair] - in_transit[pair]
            if initialization_policy["mrp_enforce_physical_safety_floor"]:
                needed = max(needed, soft_safety_target_qty - stock[pair])
            if needed <= 1e-9:
                continue

            remaining = needed
            active_lanes: list[tuple[dict[str, Any], float]] = []
            for lane in lane_list:
                lane_review_days = int(round(max(1.0, to_float(lane.get("order_frequency_days"), 1.0))))
                if day % lane_review_days != 0:
                    continue
                availability_mult = lane_availability_multiplier(lane, day)
                if availability_mult <= 1e-9:
                    continue
                active_lanes.append((lane, availability_mult))

            if not active_lanes:
                continue

            active_share_total = sum(max(0.0, to_float(lane.get("mrp_share"), 0.0)) for lane, _ in active_lanes)

            def try_ship_lane(
                lane: dict[str, Any],
                availability_mult: float,
                desired_delivered_qty: float,
                remaining_need_qty: float,
            ) -> float:
                nonlocal shipped_today
                nonlocal transport_cost_today
                nonlocal opening_transport_cost_today
                nonlocal purchase_cost_today
                nonlocal opening_purchase_cost_today
                nonlocal external_procurement_transport_cost_today
                nonlocal external_procurement_purchase_cost_today
                nonlocal external_procured_today
                nonlocal external_procured_rejected_today
                nonlocal supplier_capacity_binding_qty_today
                nonlocal total_external_procurement_cost
                nonlocal total_unreliable_loss_qty

                if desired_delivered_qty <= 1e-9 or remaining_need_qty <= 1e-9:
                    return 0.0
                src_pair = (lane["src"], item_id)
                available = stock[src_pair] * availability_mult
                if src_pair in externally_sourced_pairs_set and available < remaining_need_qty:
                    if (
                        unmodeled_supplier_source_mode == "external_procurement"
                        and economic_policy["external_procurement_enabled"]
                    ):
                        ext_gap = remaining_need_qty - available
                        ext_daily_signal = max(
                            propagated_demand_today.get(src_pair, 0.0),
                            item_daily_req,
                        )
                        ext_cap_today = max(
                            economic_policy["external_procurement_min_daily_cap_qty"],
                            economic_policy["external_procurement_daily_cap_days"] * ext_daily_signal,
                        )
                        ext_cap_left = max(0.0, ext_cap_today - external_ordered_today_by_src_pair[src_pair])
                        ext_order_qty = min(ext_gap, ext_cap_left)
                        if ext_order_qty > 1e-9:
                            ext_lead_days = int(economic_policy["external_procurement_lead_days"])
                            ext_arrival_day = day + ext_lead_days
                            external_pipeline[ext_arrival_day].append((src_pair[0], src_pair[1], ext_order_qty))
                            external_in_transit[src_pair] += ext_order_qty
                            register_mrp_order(
                                src_pair,
                                source_mode="external_procurement",
                                src_node_id="EXTERNAL_MARKET",
                                dst_node_id=src_pair[0],
                                item_id=src_pair[1],
                                release_qty=ext_order_qty,
                                receipt_qty=ext_order_qty,
                                arrival_day=ext_arrival_day,
                                safety_time_days=pair_mrp_safety_time_days.get(src_pair, 0.0),
                                lead_days=ext_lead_days,
                                lead_cover_days=ext_lead_days,
                            )
                            if record_day:
                                external_procured_today += ext_order_qty
                            external_ordered_today_by_src_pair[src_pair] += ext_order_qty
                            ref_purchase = max(
                                economic_policy["purchase_cost_floor_per_unit"],
                                to_float(lane.get("unit_purchase_cost"), 0.0),
                            )
                            ext_unit_purchase = max(
                                economic_policy["external_procurement_unit_cost"],
                                ref_purchase * economic_policy["external_procurement_cost_multiplier"],
                            )
                            ext_unit_transport = economic_policy["external_procurement_transport_cost_per_unit"]
                            ext_order_cost = ext_order_qty * (ext_unit_purchase + ext_unit_transport)
                            if record_day:
                                ext_purchase_cost = ext_order_qty * ext_unit_purchase
                                ext_transport_cost = ext_order_qty * ext_unit_transport
                                purchase_cost_today += ext_purchase_cost
                                transport_cost_today += ext_transport_cost
                                external_procurement_purchase_cost_today += ext_purchase_cost
                                external_procurement_transport_cost_today += ext_transport_cost
                                total_external_procurement_cost += ext_order_cost
                        ext_rejected = max(0.0, ext_gap - ext_order_qty)
                        if record_day:
                            external_procured_rejected_today += ext_rejected
                    available = stock[src_pair]
                if available <= 1e-9:
                    return 0.0
                rel = max(0.01, min(1.0, to_float(lane.get("reliability"), 1.0)))
                unconstrained_pull_qty = desired_delivered_qty / rel
                standard_order_qty = max(0.0, to_float(lane.get("standard_order_qty"), 0.0))
                max_feasible_qty = available
                supplier_capacity_left = supplier_daily_capacity_by_pair.get(src_pair)
                if supplier_capacity_left is not None:
                    supplier_capacity_left = max(
                        0.0,
                        supplier_capacity_left * availability_mult - supplier_capacity_used_today_by_src_pair[src_pair],
                    )
                    max_feasible_qty = min(max_feasible_qty, supplier_capacity_left)
                    if supplier_capacity_left + 1e-9 < unconstrained_pull_qty:
                        supplier_capacity_binding_qty_today += unconstrained_pull_qty - max(0.0, supplier_capacity_left)
                if standard_order_qty > 1e-9:
                    target_units = max(1, int(math.ceil((unconstrained_pull_qty / standard_order_qty) - 1e-9)))
                    feasible_units = int(math.floor((max_feasible_qty / standard_order_qty) + 1e-9))
                    if feasible_units <= 0:
                        return 0.0
                    pull_qty = min(target_units, feasible_units) * standard_order_qty
                else:
                    pull_qty = min(unconstrained_pull_qty, max_feasible_qty)
                delivered_qty = pull_qty * rel
                if pull_qty <= 1e-9 or delivered_qty <= 1e-9:
                    return 0.0

                stock[src_pair] -= pull_qty
                supplier_capacity_used_today_by_src_pair[src_pair] += pull_qty
                lead_days = sample_lead_days(lane, rng, args.stochastic_lead_times)
                lead_cover = lead_time_cover_days(lane, args.stochastic_lead_times)
                order_frequency_days = max(1, int(round(max(1.0, to_float(lane.get("order_frequency_days"), 1.0)))))
                delivery_schedule: list[tuple[int, float, float]] = []
                if standard_order_qty > 1e-9 and pull_qty > standard_order_qty + 1e-9:
                    total_units = max(1, int(round(pull_qty / standard_order_qty)))
                    max_delivery_count = max(1, int(math.ceil(float(lead_cover) / float(order_frequency_days))))
                    delivery_count = min(total_units, max_delivery_count)
                    base_units = max(1, total_units // delivery_count)
                    remainder_units = total_units % delivery_count
                    latest_offset = max(0, int(lead_cover) - 1)
                    for idx in range(delivery_count):
                        units = base_units + (1 if idx < remainder_units else 0)
                        chunk_pull_qty = units * standard_order_qty
                        chunk_delivered_qty = chunk_pull_qty * rel
                        if delivery_count > 1:
                            even_offset = int(round(idx * latest_offset / float(delivery_count - 1)))
                            cadence_offset = idx * order_frequency_days
                            delivery_offset = min(latest_offset, max(cadence_offset, even_offset))
                        else:
                            delivery_offset = 0
                        arrival_day = day + lead_days + delivery_offset
                        delivery_schedule.append((arrival_day, chunk_pull_qty, chunk_delivered_qty))
                else:
                    delivery_schedule.append((day + lead_days, pull_qty, delivered_qty))

                for arrival_day, chunk_pull_qty, chunk_delivered_qty in delivery_schedule:
                    physical_release_day = int(arrival_day - lead_days)
                    pipeline[arrival_day].append((dst, item_id, chunk_delivered_qty, lane["edge_id"]))
                    register_mrp_order(
                        pair,
                        source_mode="lane_release",
                        src_node_id=str(lane["src"]),
                        dst_node_id=str(dst),
                        item_id=str(item_id),
                        release_qty=chunk_pull_qty,
                        receipt_qty=chunk_delivered_qty,
                        arrival_day=arrival_day,
                        safety_time_days=pair_mrp_safety_time_days.get(pair, 0.0),
                        lead_days=lead_days,
                        lead_cover_days=lead_cover,
                        edge_id=str(lane["edge_id"]),
                        reliability=rel,
                        standard_order_qty=standard_order_qty,
                        mrp_share=to_float(lane.get("mrp_share"), 0.0),
                        physical_release_day=physical_release_day,
                    )
                in_transit[pair] += delivered_qty
                if record_day:
                    for arrival_day, chunk_pull_qty, chunk_delivered_qty in delivery_schedule:
                        physical_release_day = int(arrival_day - lead_days)
                        chunk_lead_cover_days = int(max(1, lead_cover))
                        chunk_order_date_imt = int(arrival_day - chunk_lead_cover_days - warmup_days)
                        is_opening_open_order_cost = chunk_order_date_imt < 0
                        chunk_transport_cost, transport_cost_basis, transport_cost_units = lane_transport_cost_for_chunk(
                            lane,
                            str(item_id),
                            chunk_pull_qty,
                            chunk_delivered_qty,
                        )
                        chunk_purchase_cost = chunk_delivered_qty * lane["unit_purchase_cost"]
                        chunk_loss = max(0.0, chunk_pull_qty - chunk_delivered_qty)
                        if physical_release_day <= day:
                            shipped_today += chunk_delivered_qty
                            shipped_today_to_pair[(dst, item_id)] += chunk_delivered_qty
                            transport_cost_today += chunk_transport_cost
                            purchase_cost_today += chunk_purchase_cost
                            total_unreliable_loss_qty += chunk_loss
                            if is_opening_open_order_cost:
                                opening_transport_cost_today += chunk_transport_cost
                                opening_purchase_cost_today += chunk_purchase_cost
                        else:
                            scheduled_lane_release_metrics[physical_release_day].append(
                                (
                                    (dst, item_id),
                                    chunk_delivered_qty,
                                    chunk_transport_cost,
                                    chunk_purchase_cost,
                                    chunk_loss,
                                    is_opening_open_order_cost,
                                )
                            )
                        supplier_shipment_rows.append(
                            {
                                "day": int(physical_release_day - warmup_days),
                                "src_node_id": str(lane["src"]),
                                "dst_node_id": str(dst),
                                "item_id": str(item_id),
                                "shipped_qty": round(chunk_delivered_qty, 6),
                                "pulled_qty": round(chunk_pull_qty, 6),
                                "lead_days": int(lead_days),
                                "arrival_day": int(arrival_day - warmup_days),
                                "reliability": round(rel, 6),
                                "uom": item_unit_map.get(item_id, ""),
                                "transport_cost_basis": transport_cost_basis,
                                "transport_cost_units": round(transport_cost_units, 6),
                                "transport_cost": round(chunk_transport_cost, 6),
                            }
                        )
                return delivered_qty

            if active_share_total > 1e-9 and len(active_lanes) > 1:
                for lane, availability_mult in active_lanes:
                    if remaining <= 1e-9:
                        break
                    lane_share = max(0.0, to_float(lane.get("mrp_share"), 0.0))
                    lane_target_qty = needed * lane_share / active_share_total
                    remaining -= try_ship_lane(
                        lane,
                        availability_mult,
                        desired_delivered_qty=min(remaining, lane_target_qty),
                        remaining_need_qty=remaining,
                    )

            for lane, availability_mult in active_lanes:
                if remaining <= 1e-9:
                    break
                remaining -= try_ship_lane(
                    lane,
                    availability_mult,
                    desired_delivered_qty=remaining,
                    remaining_need_qty=remaining,
                )

        if record_day:
            total_shipped += shipped_today
            total_transport_cost += transport_cost_today
            total_purchase_cost += purchase_cost_today
            total_external_procured += external_procured_today
            total_external_procured_rejected += external_procured_rejected_today
            total_supplier_capacity_binding_qty += supplier_capacity_binding_qty_today
            for node_id, item_id in production_input_pairs:
                input_shipment_rows.append(
                    {
                        "day": output_day,
                        "node_id": node_id,
                        "item_id": item_id,
                        "shipped_to_node_qty": round(shipped_today_to_pair[(node_id, item_id)], 6),
                        "uom": item_unit_map.get(item_id, ""),
                    }
                )
            for src_pair, nominal_cap in supplier_daily_capacity_by_pair.items():
                src, item_id = src_pair
                used_qty = supplier_capacity_used_today_by_src_pair.get(src_pair, 0.0)
                supplier_capacity_daily_rows.append(
                    {
                        "day": output_day,
                        "node_id": src,
                        "item_id": item_id,
                        "capacity_qty_per_day": round(nominal_cap, 6),
                        "used_qty": round(used_qty, 6),
                        "remaining_capacity_qty": round(max(0.0, nominal_cap - used_qty), 6),
                        "utilization": round(used_qty / nominal_cap, 6) if nominal_cap > 1e-9 else 0.0,
                    }
                )

            for pair in mrp_trace_pairs:
                item_daily_req_static = max(0.0, required_daily_input_by_pair.get(pair, 0.0))
                item_daily_req_dynamic = max(0.0, propagated_demand_today.get(pair, 0.0))
                item_daily_req_raw_dynamic = max(0.0, raw_propagated_demand_today.get(pair, 0.0))
                if item_daily_req_dynamic > 1e-9:
                    item_daily_req = item_daily_req_dynamic
                    if mrp_demand_signal_source == "mps_lotified":
                        gross_requirement_basis = (
                            f"mps_lotified_{mrp_signal_smoothing_days}d_avg"
                            if mrp_signal_smoothing_days > 1
                            else "mps_lotified"
                        )
                    else:
                        gross_requirement_basis = (
                            f"propagated_demand_{mrp_signal_smoothing_days}d_avg"
                            if mrp_signal_smoothing_days > 1
                            else "propagated_demand"
                        )
                elif (
                    initialization_policy["use_bom_demand_signal_for_mrp"]
                    and not initialization_policy["mrp_static_fallback_for_propagated_pairs"]
                    and pair in propagated_mrp_signal_pairs
                ):
                    item_daily_req = 0.0
                    gross_requirement_basis = "propagated_demand_zero"
                else:
                    item_daily_req = item_daily_req_static
                    gross_requirement_basis = "static_requirement" if item_daily_req_static > 1e-9 else "none"
                safety_floor_qty = max(base_stock.get(pair, 0.0), 0.0)
                soft_safety_target_qty = safety_floor_qty
                coverage_target_qty = 0.0
                if item_daily_req > 0.0:
                    safety_floor_qty = max(
                        safety_floor_qty,
                        item_daily_req * max(0.0, pair_mrp_safety_time_days.get(pair, 0.0)),
                    )
                    soft_safety_target_qty = max(
                        soft_safety_target_qty,
                        safety_floor_qty * initialization_policy["soft_safety_time_stock_target_factor"],
                    )
                    coverage_target_qty = max(coverage_target_qty, safety_stock_days * item_daily_req)
                    if pair in demand_pairs and demand_stock_target_days > 0.0:
                        coverage_target_qty = max(coverage_target_qty, demand_stock_target_days * item_daily_req)
                    if pair not in mrp_snapshot_pairs:
                        effective_cover_days = float(pair_stock_cover_days.get(pair, review_period_days + 1))
                        if initialization_policy["seed_open_orders_from_january_snapshot"]:
                            effective_cover_days = max(
                                0.0,
                                effective_cover_days - float(opening_open_order_bridge_days_by_pair.get(pair, 0)),
                            )
                        coverage_target_qty = max(
                            coverage_target_qty,
                            item_daily_req * effective_cover_days,
                        )
                target_stock_qty = max(soft_safety_target_qty, coverage_target_qty)
                backlog_target_qty = max(0.0, backlog.get(pair, 0.0))
                target_with_backlog_qty = target_stock_qty + backlog_target_qty
                recv_prev_today_qty = (
                    arrivals_today_by_pair.get(pair, 0.0)
                    + external_arrivals_today_by_pair.get(pair, 0.0)
                    + estimated_source_arrivals_today_by_pair.get(pair, 0.0)
                )
                recv_prev_future_qty = (
                    max(0.0, in_transit.get(pair, 0.0))
                    + max(0.0, external_in_transit.get(pair, 0.0))
                    + max(0.0, estimated_source_in_transit.get(pair, 0.0))
                )
                stock_proj_qty = max(0.0, stock.get(pair, 0.0))
                inventory_position_qty = stock_proj_qty + recv_prev_future_qty
                bb_backlog_qty = backlog_start_of_day_by_pair.get(pair, 0.0)
                bb_qty = item_daily_req + bb_backlog_qty
                bn_qty = max(0.0, target_with_backlog_qty - inventory_position_qty)
                if initialization_policy["mrp_enforce_physical_safety_floor"]:
                    bn_qty = max(0.0, bn_qty, soft_safety_target_qty - stock_proj_qty)
                arrival_min_day = planned_receipt_min_day_by_pair.get(pair)
                arrival_max_day = planned_receipt_max_day_by_pair.get(pair)
                mrp_trace_rows.append(
                    {
                        "day": output_day,
                        "node_id": pair[0],
                        "item_id": pair[1],
                        "bb_qty": round(bb_qty, 6),
                        "bb_demand_signal_qty": round(item_daily_req, 6),
                        "bb_demand_signal_raw_qty": round(item_daily_req_raw_dynamic, 6),
                        "bb_backlog_qty": round(bb_backlog_qty, 6),
                        "gross_requirement_basis": gross_requirement_basis,
                        "mrp_demand_signal_source": mrp_demand_signal_source,
                        "mrp_demand_signal_smoothing_days": int(mrp_signal_smoothing_days),
                        "safety_floor_qty": round(safety_floor_qty, 6),
                        "soft_safety_target_qty": round(soft_safety_target_qty, 6),
                        "coverage_target_qty": round(coverage_target_qty, 6),
                        "target_stock_qty": round(target_stock_qty, 6),
                        "backlog_target_qty": round(backlog_target_qty, 6),
                        "target_with_backlog_qty": round(target_with_backlog_qty, 6),
                        "stock_proj_qty": round(stock_proj_qty, 6),
                        "recv_prev_today_qty": round(recv_prev_today_qty, 6),
                        "recv_prev_future_qty": round(recv_prev_future_qty, 6),
                        "inventory_position_qty": round(inventory_position_qty, 6),
                        "bn_qty": round(bn_qty, 6),
                        "planned_release_qty": round(planned_release_today_by_pair.get(pair, 0.0), 6),
                        "planned_receipt_qty": round(planned_receipt_today_by_pair.get(pair, 0.0), 6),
                        "planned_order_count": int(planned_order_count_by_pair.get(pair, 0)),
                        "planned_receipt_min_day": (
                            int(arrival_min_day - warmup_days) if arrival_min_day is not None else ""
                        ),
                        "planned_receipt_max_day": (
                            int(arrival_max_day - warmup_days) if arrival_max_day is not None else ""
                        ),
                        "review_period_days": int(review_period_days),
                        "safety_time_days": round(pair_mrp_safety_time_days.get(pair, 0.0), 6),
                        "safety_stock_qty": round(pair_mrp_safety_stock_qty.get(pair, 0.0), 6),
                        "has_mrp_snapshot_policy": int(pair in mrp_snapshot_pairs),
                    }
                )

        # End-of-day holding costs
        inv_total_today = 0.0
        raw_holding_cost_today = 0.0
        for key, qty in stock.items():
            if qty <= 0:
                continue
            inv_total_today += qty
            raw_holding_cost_today += qty * holding_cost.get(key, 0.0)
        holding_cost_today = (
            raw_holding_cost_today * economic_policy["inventory_capital_cost_share_of_raw_holding"]
        )
        warehouse_operating_cost_today = (
            raw_holding_cost_today * economic_policy["warehouse_operating_cost_share_of_raw_holding"]
        )
        inventory_risk_cost_today = (
            raw_holding_cost_today * economic_policy["inventory_risk_cost_share_of_raw_holding"]
        )
        if record_day:
            total_holding_cost += holding_cost_today
            total_warehouse_operating_cost += warehouse_operating_cost_today
            total_inventory_risk_cost += inventory_risk_cost_today
            total_legacy_raw_holding_cost += raw_holding_cost_today

        for node_id, item_id in production_input_pairs:
            row = day_input_rows_by_pair.get((node_id, item_id))
            if row is not None:
                row["stock_end_of_day"] = round(stock[(node_id, item_id)], 6)

        if record_day:
            for node_id, item_id in supplier_stock_pairs:
                supplier_stock_rows.append(
                    {
                        "day": output_day,
                        "node_id": node_id,
                        "item_id": item_id,
                        "stock_end_of_day": round(stock[(node_id, item_id)], 6),
                    }
                )
            for node_id, item_id in dc_stock_pairs:
                dc_stock_rows.append(
                    {
                        "day": output_day,
                        "node_id": node_id,
                        "item_id": item_id,
                        "stock_end_of_day": round(stock[(node_id, item_id)], 6),
                    }
                )

            daily_rows.append(
                {
                    "day": output_day,
                    "demand": round(demand_today, 4),
                    "served": round(served_today, 4),
                    "backlog_end": round(sum(backlog.values()), 4),
                    "arrivals_qty": round(arrivals_qty, 4),
                    "produced_qty": round(produced_today, 4),
                    "shipped_qty": round(shipped_today, 4),
                    "inventory_total": round(inv_total_today, 4),
                    "holding_cost_day": round(holding_cost_today, 4),
                    "warehouse_operating_cost_day": round(warehouse_operating_cost_today, 4),
                    "inventory_risk_cost_day": round(inventory_risk_cost_today, 4),
                    "legacy_raw_holding_cost_day": round(raw_holding_cost_today, 4),
                    "transport_cost_day": round(transport_cost_today, 4),
                    "opening_open_order_transport_cost_day": round(opening_transport_cost_today, 4),
                    "external_procurement_transport_cost_day": round(external_procurement_transport_cost_today, 4),
                    "operational_transport_cost_day": round(max(0.0, transport_cost_today - opening_transport_cost_today), 4),
                    "purchase_cost_day": round(purchase_cost_today, 4),
                    "opening_open_order_purchase_cost_day": round(opening_purchase_cost_today, 4),
                    "external_procurement_purchase_cost_day": round(external_procurement_purchase_cost_today, 4),
                    "operational_purchase_cost_day": round(max(0.0, purchase_cost_today - opening_purchase_cost_today), 4),
                    "external_procured_ordered_qty": round(external_procured_today, 4),
                    "external_procured_arrived_qty": round(external_arrivals_qty, 4),
                    "external_procured_rejected_qty": round(external_procured_rejected_today, 4),
                    "estimated_source_ordered_qty": round(estimated_source_ordered_today, 4),
                    "estimated_source_arrived_qty": round(estimated_source_arrivals_qty, 4),
                    "estimated_source_rejected_qty": round(estimated_source_rejected_today, 4),
                    "supplier_capacity_binding_qty": round(supplier_capacity_binding_qty_today, 4),
                }
            )

    ending_inventory = sum(v for v in stock.values() if v > 0)
    ending_backlog = sum(v for v in backlog.values() if v > 0)
    measured_required_total = total_demand + measurement_starting_backlog
    fill_rate = (total_served / measured_required_total) if measured_required_total > 0 else 1.0
    avg_inventory = sum(r["inventory_total"] for r in daily_rows) / len(daily_rows) if daily_rows else 0.0

    top_backlog = sorted(
        [
            {"node_id": pair[0], "item_id": pair[1], "backlog": round(val, 4)}
            for pair, val in backlog.items()
            if val > 0
        ],
        key=lambda x: -x["backlog"],
    )[:10]
    total_logistics_cost = (
        total_transport_cost
        + total_holding_cost
        + total_warehouse_operating_cost
        + total_inventory_risk_cost
    )
    total_cost = total_logistics_cost + total_purchase_cost
    holding_share = total_holding_cost / max(1e-12, total_cost)
    warehouse_share = total_warehouse_operating_cost / max(1e-12, total_cost)
    inventory_risk_share = total_inventory_risk_cost / max(1e-12, total_cost)
    transport_share = total_transport_cost / max(1e-12, total_cost)
    purchase_share = total_purchase_cost / max(1e-12, total_cost)
    economic_warnings: list[str] = []
    if holding_share > 0.60:
        economic_warnings.append("capital_holding_cost_share_above_60pct")
    if transport_share < 0.02:
        economic_warnings.append("transport_cost_share_below_2pct")
    if warehouse_share < 0.10:
        economic_warnings.append("warehouse_operating_cost_share_below_10pct")
    if inventory_risk_share < 0.05:
        economic_warnings.append("inventory_risk_cost_share_below_5pct")
    if total_external_procured > 0 and total_external_procured_arrived <= 1e-9:
        economic_warnings.append("external_procurement_ordered_but_not_arrived_in_horizon")

    actual_input_consumption_avg_by_pair: dict[tuple[str, str], float] = defaultdict(float)
    for row in input_consumption_rows:
        actual_input_consumption_avg_by_pair[(str(row["node_id"]), str(row["item_id"]))] += max(
            0.0,
            to_float(row.get("consumed_qty"), 0.0),
        )
    actual_output_production_avg_by_pair: dict[tuple[str, str], float] = defaultdict(float)
    for row in output_prod_rows:
        actual_output_production_avg_by_pair[(str(row["node_id"]), str(row["item_id"]))] += max(
            0.0,
            to_float(row.get("produced_qty"), 0.0),
        )
    actual_demand_avg_by_pair: dict[tuple[str, str], float] = defaultdict(float)
    served_avg_by_pair: dict[tuple[str, str], float] = defaultdict(float)
    for row in demand_pair_rows:
        pair = (str(row["node_id"]), str(row["item_id"]))
        actual_demand_avg_by_pair[pair] += max(0.0, to_float(row.get("demand_qty"), 0.0))
        served_avg_by_pair[pair] += max(0.0, to_float(row.get("served_qty"), 0.0))
    avg_divisor = max(1.0, float(sim_days))
    for bucket in (
        actual_input_consumption_avg_by_pair,
        actual_output_production_avg_by_pair,
        actual_demand_avg_by_pair,
        served_avg_by_pair,
    ):
        for pair in list(bucket.keys()):
            bucket[pair] = bucket[pair] / avg_divisor

    safety_reference_pairs = sorted(
        set(production_input_pairs)
        | set(production_output_pairs)
        | set(demand_pairs)
        | set(propagated_demand_daily)
        | set(pair_mrp_safety_time_days)
        | set(pair_mrp_safety_stock_qty)
    )
    safety_reference_rows: list[dict[str, Any]] = []
    soft_safety_factor = initialization_policy["soft_safety_time_stock_target_factor"]
    for pair in safety_reference_pairs:
        node_id, item_id = pair
        if item_id == "item:__process_time__":
            continue
        safety_days = max(0.0, pair_mrp_safety_time_days.get(pair, 0.0))
        explicit_safety_stock_qty = 0.0
        planned_avg_daily_demand_qty = max(
            0.0,
            demand_target_daily.get(pair, 0.0),
            propagated_demand_daily.get(pair, 0.0),
            required_daily_input_by_pair.get(pair, 0.0),
        )
        observed_avg_daily_flow_qty = max(
            0.0,
            actual_input_consumption_avg_by_pair.get(pair, 0.0),
            actual_output_production_avg_by_pair.get(pair, 0.0),
            actual_demand_avg_by_pair.get(pair, 0.0),
        )
        stock_equiv_safety_time_qty = planned_avg_daily_demand_qty * safety_days
        effective_reference_stock_qty = max(explicit_safety_stock_qty, stock_equiv_safety_time_qty)
        soft_simulated_target_qty = max(
            explicit_safety_stock_qty,
            stock_equiv_safety_time_qty * soft_safety_factor,
        )
        node_type = node_type_by_id.get(node_id, "")
        if pair in demand_pairs or node_type in {"distribution_center", "customer"}:
            scope = "finished_good"
        elif pair in production_output_pairs:
            scope = "semi_finished_or_output"
        elif pair in production_input_pairs:
            scope = "input_material"
        else:
            scope = "supply_pair"
        safety_reference_rows.append(
            {
                "scope": scope,
                "node_id": node_id,
                "item_id": item_id,
                "uom": item_unit_map.get(item_id, ""),
                "safety_time_days": round(safety_days, 6),
                "planned_avg_daily_demand_qty": round(planned_avg_daily_demand_qty, 6),
                "observed_avg_daily_flow_qty": round(observed_avg_daily_flow_qty, 6),
                "stock_equiv_safety_time_qty": round(stock_equiv_safety_time_qty, 6),
                "explicit_safety_stock_qty": round(explicit_safety_stock_qty, 6),
                "effective_reference_stock_qty": round(effective_reference_stock_qty, 6),
                "soft_simulated_target_qty": round(soft_simulated_target_qty, 6),
                "soft_safety_factor": round(soft_safety_factor, 6),
                "served_avg_daily_qty": round(served_avg_by_pair.get(pair, 0.0), 6),
            }
        )

    summary = {
        "input_file": str(input_path),
        "scenario_id": str(scenario.get("id")),
        "sim_days": sim_days,
        "warmup_days": warmup_days,
        "timeline_days": sim_days,
        "total_simulated_timeline_days": total_timeline_days,
        "policy": {
            "safety_stock_days": safety_stock_days,
            "review_period_days": review_period_days,
            "fg_target_days": fg_target_days,
            "demand_stock_target_days": demand_stock_target_days,
            "production_gap_gain": production_gap_gain,
            "production_smoothing": production_smoothing,
            "warmup_days": warmup_days,
            "reset_backlog_after_warmup": reset_backlog_after_warmup,
            "output_profile": args.output_profile,
            "opening_stock_bootstrap_scale": opening_stock_bootstrap_scale,
            "unmodeled_supplier_source_mode": unmodeled_supplier_source_mode,
            "stochastic_lead_times": bool(args.stochastic_lead_times),
            "seed": int(args.seed),
            "initialization_policy": {
                "mode": initialization_policy["mode"],
                "state_scale": initialization_policy["state_scale"],
                "factory_input_on_hand_days": initialization_policy["factory_input_on_hand_days"],
                "supplier_output_on_hand_days": initialization_policy["supplier_output_on_hand_days"],
                "distribution_center_on_hand_days": initialization_policy["distribution_center_on_hand_days"],
                "customer_on_hand_days": initialization_policy["customer_on_hand_days"],
                "seed_in_transit": initialization_policy["seed_in_transit"],
                "in_transit_fill_ratio": initialization_policy["in_transit_fill_ratio"],
                "seed_estimated_source_pipeline": initialization_policy["seed_estimated_source_pipeline"],
                "restore_opening_stock_after_warmup": initialization_policy["restore_opening_stock_after_warmup"],
                "seed_open_orders_from_january_snapshot": initialization_policy["seed_open_orders_from_january_snapshot"],
                "opening_open_orders_horizon_days": initialization_policy["opening_open_orders_horizon_days"],
                "opening_open_orders_demand_multiplier": initialization_policy[
                    "opening_open_orders_demand_multiplier"
                ],
                "use_bom_demand_signal_for_mrp": initialization_policy["use_bom_demand_signal_for_mrp"],
                "mrp_demand_signal_source": initialization_policy["mrp_demand_signal_source"],
                "mrp_demand_signal_smoothing_days": initialization_policy[
                    "mrp_demand_signal_smoothing_days"
                ],
                "mrp_static_fallback_for_propagated_pairs": initialization_policy[
                    "mrp_static_fallback_for_propagated_pairs"
                ],
                "mrp_enforce_physical_safety_floor": initialization_policy[
                    "mrp_enforce_physical_safety_floor"
                ],
                "soft_safety_time_stock_target_factor": initialization_policy[
                    "soft_safety_time_stock_target_factor"
                ],
            },
            "economic_policy": {
                "transport_cost_floor_per_unit": economic_policy["transport_cost_floor_per_unit"],
                "transport_cost_per_km_per_unit": economic_policy["transport_cost_per_km_per_unit"],
                "purchase_cost_floor_per_unit": economic_policy["purchase_cost_floor_per_unit"],
                "holding_cost_scale": economic_policy["holding_cost_scale"],
                "inventory_capital_cost_share_of_raw_holding": round(
                    economic_policy["inventory_capital_cost_share_of_raw_holding"],
                    6,
                ),
                "warehouse_operating_cost_share_of_raw_holding": round(
                    economic_policy["warehouse_operating_cost_share_of_raw_holding"],
                    6,
                ),
                "inventory_risk_cost_share_of_raw_holding": round(
                    economic_policy["inventory_risk_cost_share_of_raw_holding"],
                    6,
                ),
                "transport_cost_realism_multiplier": economic_policy["transport_cost_realism_multiplier"],
                "purchase_cost_realism_multiplier": economic_policy["purchase_cost_realism_multiplier"],
                "external_procurement_enabled": economic_policy["external_procurement_enabled"],
                "external_procurement_proactive_replenishment": economic_policy[
                    "external_procurement_proactive_replenishment"
                ],
                "external_procurement_lead_days": economic_policy["external_procurement_lead_days"],
                "external_procurement_daily_cap_days": economic_policy["external_procurement_daily_cap_days"],
                "external_procurement_min_daily_cap_qty": economic_policy["external_procurement_min_daily_cap_qty"],
                "external_procurement_unit_cost": economic_policy["external_procurement_unit_cost"],
                "external_procurement_cost_multiplier": economic_policy["external_procurement_cost_multiplier"],
                "external_procurement_transport_cost_per_unit": economic_policy["external_procurement_transport_cost_per_unit"],
            },
        },
        "counts": {
            "nodes": len(nodes),
            "edges": len(edges),
            "lanes": len(lanes),
            "demand_rows": len(demand_rows),
        },
        "production_tracking": {
            "input_material_pairs": [
                {"node_id": n, "item_id": i}
                for n, i in production_input_pairs
            ],
            "output_product_pairs": [
                {"node_id": n, "item_id": i}
                for n, i in production_output_pairs
            ],
            "unconstrained_process_inputs_not_in_relations": [
                {"node_id": n, "item_id": i}
                for n, i in unconstrained_input_pairs
            ],
            "item_unit_map": dict(sorted(item_unit_map.items())),
            "input_unit_conversions_applied": [
                {"node_id": n, "item_id": i, "from_unit": fu, "to_unit": tu}
                for n, i, fu, tu in sorted(input_unit_conversions_applied)
            ],
            "input_unit_mismatch_not_converted": [
                {"node_id": n, "item_id": i, "from_unit": fu, "to_unit": tu}
                for n, i, fu, tu in sorted(input_unit_mismatch_not_converted)
            ],
            "customer_demand_daily_signal": [
                {"node_id": n, "item_id": i, "demand_per_day": round(v, 6)}
                for (n, i), v in sorted(demand_target_daily.items())
            ],
            "propagated_demand_daily_signal": [
                {"node_id": n, "item_id": i, "demand_per_day": round(v, 6)}
                for (n, i), v in sorted(propagated_demand_daily.items())
                if v > 0
            ],
            "assumed_supplier_nodes": assumed_supplier_nodes,
            "assumed_supply_edges": assumed_supply_edges,
            "externally_sourced_unmodeled_pairs": [
                {"node_id": n, "item_id": i}
                for n, i in externally_sourced_pairs
            ],
            "opening_stock_bootstrap_pairs": opening_stock_bootstrap_rows,
            "explicit_initialization_stock_rows": initialization_state_rows,
            "explicit_initialization_pipeline_rows": initialization_pipeline_rows,
            "opening_open_order_rows": opening_open_order_rows,
            "pair_mrp_safety_policies": [
                {
                    "node_id": n,
                    "item_id": i,
                    "safety_time_days": round(pair_mrp_safety_time_days.get((n, i), 0.0), 6),
                    "safety_stock_qty": round(pair_mrp_safety_stock_qty.get((n, i), 0.0), 6),
                }
                for (n, i) in sorted(
                    {
                        pair
                        for pair in set(pair_mrp_safety_time_days) | set(pair_mrp_safety_stock_qty)
                        if pair_mrp_safety_time_days.get(pair, 0.0) > 0.0
                        or pair_mrp_safety_stock_qty.get(pair, 0.0) > 0.0
                    }
                )
            ],
            "safety_stock_reference": safety_reference_rows,
            "process_lot_execution_policies": [
                {
                    "node_id": str(node.get("id")),
                    "item_id": str(((proc.get("outputs") or [{}])[0] or {}).get("item_id") or ""),
                    "max_lots_per_week": round(
                        max(0.0, to_float(((proc.get("lot_execution") or {}).get("max_lots_per_week")), 0.0)),
                        6,
                    ),
                    "lot_multiple_qty": round(
                        max(0.0, to_float(((proc.get("lot_sizing") or {}).get("lot_multiple_qty")), 0.0)),
                        6,
                    ),
                    "source": str(((proc.get("lot_execution") or {}).get("source")) or ""),
                }
                for node in (nodes or [])
                for proc in (node.get("processes") or [])
                if (proc.get("outputs") or []) and max(
                    0.0,
                    to_float(((proc.get("lot_execution") or {}).get("max_lots_per_week")), 0.0),
                ) > 0.0
            ],
            "supplier_daily_capacity_pairs": supplier_capacity_metadata_rows,
            "unmodeled_supplier_source_policies": estimated_source_policy_rows,
            "mrp_trace": {
                "enabled": True,
                "tracked_pairs": len(mrp_trace_pairs),
                "trace_rows": len(mrp_trace_rows),
                "order_rows": len(mrp_order_rows),
                "trace_outputs": [
                    "mrp_trace_daily.csv",
                    "mrp_orders_daily.csv",
                ],
            },
            "lane_purchase_cost_stats": {
                "lanes_with_positive_purchase_cost": sum(1 for l in lanes if to_float(l.get("unit_purchase_cost"), 0.0) > 0),
                "lanes_with_zero_purchase_cost": sum(1 for l in lanes if to_float(l.get("unit_purchase_cost"), 0.0) <= 0),
                "lanes_with_explicit_transport_cost": lanes_with_explicit_transport_cost,
                "lanes_with_fallback_transport_cost": lanes_with_fallback_transport_cost,
            },
        },
        "kpis": {
            "total_demand": round(total_demand, 4),
            "measurement_starting_backlog": round(measurement_starting_backlog, 4),
            "warmup_backlog_cleared_qty": round(warmup_backlog_cleared_qty, 4),
            "measured_required_total": round(measured_required_total, 4),
            "total_served": round(total_served, 4),
            "ending_backlog": round(ending_backlog, 4),
            "fill_rate": round(fill_rate, 6),
            "total_shipped": round(total_shipped, 4),
            "total_arrived": round(total_arrived, 4),
            "total_produced": round(total_produced, 4),
            "avg_inventory": round(avg_inventory, 4),
            "ending_inventory": round(ending_inventory, 4),
            "total_transport_cost": round(total_transport_cost, 4),
            "total_holding_cost": round(total_holding_cost, 4),
            "total_warehouse_operating_cost": round(total_warehouse_operating_cost, 4),
            "total_inventory_risk_cost": round(total_inventory_risk_cost, 4),
            "total_inventory_cost_legacy_raw_holding": round(total_legacy_raw_holding_cost, 4),
            "total_purchase_cost": round(total_purchase_cost, 4),
            "total_logistics_cost": round(total_logistics_cost, 4),
            "total_cost": round(total_cost, 4),
            "total_external_procured_ordered_qty": round(total_external_procured, 4),
            "total_external_procured_arrived_qty": round(total_external_procured_arrived, 4),
            "total_external_procured_rejected_qty": round(total_external_procured_rejected, 4),
            "total_external_procured_qty": round(total_external_procured, 4),
            "total_external_procurement_cost": round(total_external_procurement_cost, 4),
            "total_estimated_source_ordered_qty": round(total_estimated_source_ordered, 4),
            "total_estimated_source_replenished_qty": round(total_estimated_source_replenished, 4),
            "total_estimated_source_rejected_qty": round(total_estimated_source_rejected, 4),
            "total_opening_stock_bootstrap_qty": round(total_opening_stock_bootstrap, 4),
            "total_explicit_initialization_stock_qty": round(total_initialization_stock_added, 4),
            "total_explicit_initialization_pipeline_qty": round(total_initialization_pipeline_seeded, 4),
            "total_opening_open_order_qty": round(total_opening_open_order_qty, 4),
            "total_unreliable_loss_qty": round(total_unreliable_loss_qty, 4),
            "total_supplier_capacity_binding_qty": round(total_supplier_capacity_binding_qty, 4),
            "cost_share_holding": round(holding_share, 6),
            "cost_share_warehouse_operating": round(warehouse_share, 6),
            "cost_share_inventory_risk": round(inventory_risk_share, 6),
            "cost_share_transport": round(transport_share, 6),
            "cost_share_purchase": round(purchase_share, 6),
        },
        "economic_consistency": {
            "status": "warn" if economic_warnings else "ok",
            "warnings": economic_warnings,
            "transport_cost_share_target_min": 0.02,
            "capital_holding_cost_share_target_max": 0.60,
            "warehouse_operating_cost_share_target_min": 0.10,
            "inventory_risk_cost_share_target_min": 0.05,
        },
        "top_backlog_pairs": top_backlog,
    }

    for node_id in assumed_supplier_nodes:
        assumptions_ledger_rows.append(
            {
                "category": "assumed_supplier_node",
                "node_id": str(node_id),
                "item_id": "",
                "edge_id": "",
                "source": "simulation_prep_assumption",
                "payload_json": json.dumps({"node_id": node_id}, ensure_ascii=False, sort_keys=True),
            }
        )
    for edge_id in assumed_supply_edges:
        assumptions_ledger_rows.append(
            {
                "category": "assumed_supply_edge",
                "node_id": "",
                "item_id": "",
                "edge_id": str(edge_id),
                "source": "simulation_prep_assumption",
                "payload_json": json.dumps({"edge_id": edge_id}, ensure_ascii=False, sort_keys=True),
            }
        )
    for row in supplier_capacity_metadata_rows:
        assumptions_ledger_rows.append(
            {
                "category": "supplier_capacity_basis",
                "node_id": str(row.get("node_id") or ""),
                "item_id": str(row.get("item_id") or ""),
                "edge_id": "",
                "source": str(row.get("capacity_basis") or row.get("basis") or "derived"),
                "payload_json": json.dumps(row, ensure_ascii=False, sort_keys=True),
            }
        )
    for row in estimated_source_policy_rows:
        assumptions_ledger_rows.append(
            {
                "category": "unmodeled_supplier_source_policy",
                "node_id": str(row.get("node_id") or ""),
                "item_id": str(row.get("item_id") or ""),
                "edge_id": "",
                "source": str(row.get("mode") or "estimated_replenishment"),
                "payload_json": json.dumps(row, ensure_ascii=False, sort_keys=True),
            }
        )
    for pair in sorted(set(pair_mrp_safety_time_days) | set(pair_mrp_safety_stock_qty)):
        assumptions_ledger_rows.append(
            {
                "category": "mrp_safety_policy",
                "node_id": str(pair[0]),
                "item_id": str(pair[1]),
                "edge_id": "",
                "source": "stocks_mrp_or_override",
                "payload_json": json.dumps(
                    {
                        "node_id": pair[0],
                        "item_id": pair[1],
                        "safety_time_days": round(pair_mrp_safety_time_days.get(pair, 0.0), 6),
                        "safety_stock_qty": round(pair_mrp_safety_stock_qty.get(pair, 0.0), 6),
                    },
                    ensure_ascii=False,
                    sort_keys=True,
                ),
            }
        )
    for node in (nodes or []):
        for proc in (node.get("processes") or []):
            outputs = proc.get("outputs") or []
            if not outputs:
                continue
            item_id = str((outputs[0] or {}).get("item_id") or "")
            payload = {
                "node_id": str(node.get("id") or ""),
                "item_id": item_id,
                "lot_sizing": proc.get("lot_sizing") or {},
                "lot_execution": proc.get("lot_execution") or {},
                "capacity": proc.get("capacity") or {},
            }
            assumptions_ledger_rows.append(
                {
                    "category": "process_execution_policy",
                    "node_id": str(node.get("id") or ""),
                    "item_id": item_id,
                    "edge_id": "",
                    "source": str(
                        ((proc.get("lot_execution") or {}).get("source"))
                        or ((proc.get("lot_sizing") or {}).get("source"))
                        or ((proc.get("capacity") or {}).get("source"))
                        or "process_policy"
                    ),
                    "payload_json": json.dumps(payload, ensure_ascii=False, sort_keys=True),
                }
            )
    for node_id, item_id in unconstrained_input_pairs:
        assumptions_ledger_rows.append(
            {
                "category": "unconstrained_process_input",
                "node_id": str(node_id),
                "item_id": str(item_id),
                "edge_id": "",
                "source": "missing_relations_acteurs_lane",
                "payload_json": json.dumps(
                    {"node_id": node_id, "item_id": item_id},
                    ensure_ascii=False,
                    sort_keys=True,
                ),
            }
        )
    assumptions_ledger_rows.sort(key=lambda r: (r["category"], r["node_id"], r["item_id"], r["edge_id"]))

    summary_output_path = summary_path(output_dir, "first_simulation_summary.json")
    daily_path = data_path(output_dir, "first_simulation_daily.csv")
    report_output_path = report_path(output_dir, "first_simulation_report.md")
    safety_reference_path = report_path(output_dir, "mrp_safety_stock_reference.csv")
    input_stock_path = data_path(output_dir, "production_input_stocks_daily.csv")
    input_consumption_path = data_path(output_dir, "production_input_consumption_daily.csv")
    input_arrival_path = data_path(output_dir, "production_input_replenishment_arrivals_daily.csv")
    input_shipment_path = data_path(output_dir, "production_input_replenishment_shipments_daily.csv")
    output_prod_path = data_path(output_dir, "production_output_products_daily.csv")
    supplier_shipment_path = data_path(output_dir, "production_supplier_shipments_daily.csv")
    supplier_stock_path = data_path(output_dir, "production_supplier_stocks_daily.csv")
    supplier_capacity_path = data_path(output_dir, "production_supplier_capacity_daily.csv")
    dc_stock_path = data_path(output_dir, "production_dc_stocks_daily.csv")
    demand_pair_path = data_path(output_dir, "production_demand_service_daily.csv")
    production_constraint_path = data_path(output_dir, "production_constraint_daily.csv")
    mrp_trace_path = data_path(output_dir, "mrp_trace_daily.csv")
    mrp_orders_path = data_path(output_dir, "mrp_orders_daily.csv")
    assumptions_ledger_path = data_path(output_dir, "assumptions_ledger.csv")
    input_pivot_path = data_path(output_dir, "production_input_stocks_pivot.csv")
    compact_output = args.output_profile == "compact"

    summary_output_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    with safety_reference_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "scope",
                "node_id",
                "item_id",
                "uom",
                "safety_time_days",
                "planned_avg_daily_demand_qty",
                "observed_avg_daily_flow_qty",
                "stock_equiv_safety_time_qty",
                "explicit_safety_stock_qty",
                "effective_reference_stock_qty",
                "soft_simulated_target_qty",
                "soft_safety_factor",
                "served_avg_daily_qty",
            ],
        )
        writer.writeheader()
        writer.writerows(safety_reference_rows)
    if not compact_output:
        with daily_path.open("w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=list(daily_rows[0].keys()) if daily_rows else [])
            if daily_rows:
                writer.writeheader()
                writer.writerows(daily_rows)

    with input_stock_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["day", "node_id", "item_id", "stock_before_production", "stock_end_of_day"],
        )
        writer.writeheader()
        writer.writerows(input_stock_rows)

    if not compact_output:
        with input_consumption_path.open("w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=["day", "node_id", "item_id", "consumed_qty", "uom"])
            writer.writeheader()
            writer.writerows(input_consumption_rows)

    with input_arrival_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["day", "node_id", "item_id", "arrived_qty", "uom"])
        writer.writeheader()
        writer.writerows(input_arrival_rows)

    if not compact_output:
        with input_shipment_path.open("w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=["day", "node_id", "item_id", "shipped_to_node_qty", "uom"])
            writer.writeheader()
            writer.writerows(input_shipment_rows)

    with output_prod_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["day", "node_id", "item_id", "produced_qty", "cum_produced_qty", "stock_end_of_day"],
        )
        writer.writeheader()
        writer.writerows(output_prod_rows)

    with demand_pair_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "day",
                "node_id",
                "item_id",
                "demand_qty",
                "required_with_backlog_qty",
                "served_qty",
                "backlog_end_qty",
                "available_before_service_qty",
            ],
        )
        writer.writeheader()
        writer.writerows(demand_pair_rows)

    with production_constraint_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "day",
                "node_id",
                "output_item_id",
                "desired_qty",
                "planned_qty_after_lot_rule",
                "actual_qty",
                "cap_qty",
                "capacity_limit_mode",
                "max_from_inputs_qty",
                "binding_cause",
                "binding_input_item_id",
                "shortfall_vs_desired_qty",
                "shortfall_vs_lot_plan_qty",
                "lot_policy_mode",
                "lot_fixed_qty",
                "lot_min_qty",
                "lot_max_qty",
                "lot_multiple_qty",
                "max_lots_per_week",
                "started_lots_this_week",
                "requested_lot_starts",
                "actual_lot_starts",
                "campaign_requested_qty",
                "campaign_started_qty",
                "campaign_remaining_start_qty",
                "campaign_remaining_end_qty",
            ],
        )
        writer.writeheader()
        writer.writerows(production_constraint_rows)

    with mrp_trace_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "day",
                "node_id",
                "item_id",
                "bb_qty",
                "bb_demand_signal_qty",
                "bb_demand_signal_raw_qty",
                "bb_backlog_qty",
                "gross_requirement_basis",
                "mrp_demand_signal_source",
                "mrp_demand_signal_smoothing_days",
                "safety_floor_qty",
                "soft_safety_target_qty",
                "coverage_target_qty",
                "target_stock_qty",
                "backlog_target_qty",
                "target_with_backlog_qty",
                "stock_proj_qty",
                "recv_prev_today_qty",
                "recv_prev_future_qty",
                "inventory_position_qty",
                "bn_qty",
                "planned_release_qty",
                "planned_receipt_qty",
                "planned_order_count",
                "planned_receipt_min_day",
                "planned_receipt_max_day",
                "review_period_days",
                "safety_time_days",
                "safety_stock_qty",
                "has_mrp_snapshot_policy",
            ],
        )
        writer.writeheader()
        writer.writerows(mrp_trace_rows)

    with mrp_orders_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "day",
                "node_id",
                "item_id",
                "order_type",
                "src_node_id",
                "dst_node_id",
                "edge_id",
                "planning_status",
                "release_status",
                "receipt_status",
                "order_status_end_of_run",
                "release_qty",
                "planned_receipt_qty",
                "release_day",
                "order_date_imt",
                "arrival_day",
                "actual_receipt_day",
                "implied_cover_need_day",
                "lead_days",
                "lead_cover_days",
                "safety_time_days",
                "reliability",
                "standard_order_qty",
                "mrp_share",
            ],
        )
        writer.writeheader()
        writer.writerows(mrp_order_rows)

    with assumptions_ledger_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "category",
                "node_id",
                "item_id",
                "edge_id",
                "source",
                "payload_json",
            ],
        )
        writer.writeheader()
        writer.writerows(assumptions_ledger_rows)

    with supplier_shipment_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "day",
                "src_node_id",
                "dst_node_id",
                "item_id",
                "shipped_qty",
                "pulled_qty",
                "lead_days",
                "arrival_day",
                "reliability",
                "uom",
                "transport_cost_basis",
                "transport_cost_units",
                "transport_cost",
            ],
        )
        writer.writeheader()
        writer.writerows(supplier_shipment_rows)

    with supplier_stock_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["day", "node_id", "item_id", "stock_end_of_day"])
        writer.writeheader()
        writer.writerows(supplier_stock_rows)

    with supplier_capacity_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "day",
                "node_id",
                "item_id",
                "capacity_qty_per_day",
                "used_qty",
                "remaining_capacity_qty",
                "utilization",
            ],
        )
        writer.writeheader()
        writer.writerows(supplier_capacity_daily_rows)

    with dc_stock_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["day", "node_id", "item_id", "stock_end_of_day"])
        writer.writeheader()
        writer.writerows(dc_stock_rows)

    if not compact_output:
        # Pivot file for easier read: one column per (factory,item) input stock.
        input_pairs = sorted({(str(r["node_id"]), str(r["item_id"])) for r in input_stock_rows})
        per_day_values: dict[int, dict[tuple[str, str], float]] = defaultdict(dict)
        for r in input_stock_rows:
            day = int(r["day"])
            key = (str(r["node_id"]), str(r["item_id"]))
            per_day_values[day][key] = to_float(r.get("stock_end_of_day", r.get("stock_before_production")), 0.0)
        with input_pivot_path.open("w", encoding="utf-8", newline="") as f:
            fieldnames = ["day"] + [pair_label(n, i) for n, i in input_pairs]
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for day in sorted(per_day_values.keys()):
                row = {"day": day}
                for n, i in input_pairs:
                    row[pair_label(n, i)] = round(per_day_values[day].get((n, i), 0.0), 6)
                writer.writerow(row)

    generated_plots: dict[str, str] = {}
    if not args.skip_plots:
        generated_plots = try_generate_plots(
            input_stock_rows=input_stock_rows,
            output_prod_rows=output_prod_rows,
            supplier_shipment_rows=supplier_shipment_rows,
            supplier_factory_items=supplier_factory_items,
            dc_factory_items=dc_factory_items,
            dc_node_ids=dc_node_ids,
            output_dir=output_dir,
            item_unit_map=item_unit_map,
        )
        legacy_agg_input_plot = output_dir / "production_input_stocks.png"
        if legacy_agg_input_plot.exists():
            legacy_agg_input_plot.unlink()
    plot_root = plots_path(output_dir)
    if args.map_output:
        map_output_path = Path(args.map_output)
    else:
        default_map_name = f"supply_graph_{output_dir.name}.html"
        map_output_path = map_path(output_dir, default_map_name)
    generated_map_path: str | None = None
    if not args.skip_map:
        map_script_path = Path(args.map_script)
        if map_script_path.exists():
            map_output_path.parent.mkdir(parents=True, exist_ok=True)
            map_cmd = [
                sys.executable,
                str(map_script_path),
                "--input",
                str(input_path),
                "--output",
                str(map_output_path),
                "--sim-input-stocks-csv",
                str(input_stock_path),
                "--sim-output-products-csv",
                str(output_prod_path),
                "--demand-service-csv",
                str(demand_pair_path),
                "--sim-input-stocks-png-dir",
                str(plot_root),
                "--sim-output-products-png-dir",
                str(plot_root),
                "--supplier-shipments-csv",
                str(supplier_shipment_path),
                "--supplier-stocks-csv",
                str(supplier_stock_path),
                "--supplier-capacity-csv",
                str(supplier_capacity_path),
                "--input-arrivals-csv",
                str(input_arrival_path),
                "--dc-stocks-csv",
                str(dc_stock_path),
                "--production-constraint-csv",
                str(production_constraint_path),
                "--safety-reference-csv",
                str(safety_reference_path),
                "--daily-kpi-csv",
                str(daily_path),
                "--supplier-local-criticality-csv",
                str(data_path(output_dir, "supplier_local_criticality_ranking.csv")),
                "--supplier-local-criticality-json",
                str(summary_path(output_dir, "supplier_local_criticality_summary.json")),
            ]
            try:
                subprocess.run(map_cmd, check=True, capture_output=True, text=True)
                generated_map_path = str(map_output_path)
            except subprocess.CalledProcessError as exc:
                print(f"[WARN] Map generation failed: {exc}", file=sys.stderr)
                if exc.stdout:
                    print(exc.stdout.strip(), file=sys.stderr)
                if exc.stderr:
                    print(exc.stderr.strip(), file=sys.stderr)
        else:
            print(f"[WARN] Map script not found: {map_script_path}", file=sys.stderr)

    detailed_input_plot_paths = [
        path
        for key, path in sorted(generated_plots.items())
        if key.startswith("production_input_stocks_by_material_")
    ]
    detailed_output_plot_paths = [
        path
        for key, path in sorted(generated_plots.items())
        if key.startswith("production_output_products_by_factory_")
    ]
    detailed_supplier_plot_paths = [
        path
        for key, path in sorted(generated_plots.items())
        if key.startswith("production_supplier_input_stocks_by_material_")
    ]
    detailed_dc_plot_paths = [
        path
        for key, path in sorted(generated_plots.items())
        if key.startswith("production_dc_factory_outputs_by_material_")
    ]

    output_pairs_txt = ", ".join(pair_label(n, i) for n, i in production_output_pairs) or "n/a"
    unconstrained_txt = ", ".join(pair_label(n, i) for n, i in unconstrained_input_pairs) or "none"
    conversion_count = len(input_unit_conversions_applied)
    mismatch_count = len(input_unit_mismatch_not_converted)
    assumed_nodes_txt = ", ".join(assumed_supplier_nodes) if assumed_supplier_nodes else "none"
    assumed_edges_txt = ", ".join(assumed_supply_edges) if assumed_supply_edges else "none"
    safety_reference_preview_rows = [
        row
        for row in safety_reference_rows
        if row["safety_time_days"] > 0.0 or row["explicit_safety_stock_qty"] > 0.0
    ][:40]
    if safety_reference_preview_rows:
        safety_reference_preview_md = "\n".join(
            [
                "| Scope | Noeud | Item | Delai secu j | Demande moy/j | Stock equiv delai | Cible souple sim | Unite |",
                "|---|---:|---:|---:|---:|---:|---:|---|",
            ]
            + [
                "| {scope} | {node_id} | {item_id} | {safety_time_days} | {planned_avg_daily_demand_qty} | {stock_equiv_safety_time_qty} | {soft_simulated_target_qty} | {uom} |".format(
                    **row
                )
                for row in safety_reference_preview_rows
            ]
        )
    else:
        safety_reference_preview_md = "Aucune politique de delai/stock de securite detectee."

    mrp_validation_by_pair: dict[tuple[str, str], dict[str, Any]] = {}
    release_by_pair_day: dict[tuple[str, str], dict[int, float]] = defaultdict(lambda: defaultdict(float))
    old_release_by_pair_day: dict[tuple[str, str], dict[int, float]] = defaultdict(lambda: defaultdict(float))
    for row in mrp_order_rows:
        if str(row.get("order_type") or "") != "lane_release":
            continue
        node_id = str(row.get("dst_node_id") or row.get("node_id") or "")
        item_id = str(row.get("item_id") or "")
        if not node_id or not item_id or not (
            node_id.startswith("M-") or node_id.startswith("DC-") or node_id == "SDC-1450"
        ):
            continue
        pair = (node_id, item_id)
        qty = max(0.0, to_float(row.get("release_qty"), 0.0))
        imt_day = int(to_float(row.get("order_date_imt"), 0.0))
        sim_day = int(to_float(row.get("day"), 0.0))
        release_by_pair_day[pair][imt_day] += qty
        old_release_by_pair_day[pair][sim_day] += qty
        rec = mrp_validation_by_pair.setdefault(
            pair,
            {
                "node_id": node_id,
                "item_id": item_id,
                "standard_order_qty": 0.0,
                "total_release_qty": 0.0,
                "pre_jan_release_qty": 0.0,
            },
        )
        rec["standard_order_qty"] = max(
            rec["standard_order_qty"],
            max(0.0, to_float(row.get("standard_order_qty"), 0.0)),
        )
        rec["total_release_qty"] += qty
        if imt_day < 0:
            rec["pre_jan_release_qty"] += qty

    industrial_validation_rows: list[dict[str, Any]] = []
    for pair, rec in mrp_validation_by_pair.items():
        imt_series = release_by_pair_day.get(pair, {})
        old_series = old_release_by_pair_day.get(pair, {})
        if not imt_series:
            continue
        peak_imt_day, peak_imt_qty = max(imt_series.items(), key=lambda it: it[1])
        old_peak_day, old_peak_qty = max(old_series.items(), key=lambda it: it[1]) if old_series else (0, 0.0)
        old_day0_qty = old_series.get(0, 0.0)
        std_qty = max(0.0, to_float(rec.get("standard_order_qty"), 0.0))
        lots_at_peak = peak_imt_qty / std_qty if std_qty > 1e-9 else 0.0
        remark = ""
        if std_qty >= 1_000_000.0:
            remark = "Lot FIA tres eleve a valider avec l'industriel."
        elif 0.0 < std_qty <= 1.0 and rec["total_release_qty"] >= 100_000.0:
            remark = "Quantite standard=1 non interpretable comme lot industriel; lot/campagne interne a renseigner."
        elif std_qty > 1.0 and lots_at_peak > 10.0:
            remark = "Concentration MRP a valider; plusieurs lots commandes le meme jour IMT."
        elif old_day0_qty > 0.0 and old_day0_qty > max(peak_imt_qty * 2.0, std_qty * 2.0):
            remark = "Pic initial redate avant le 1er janvier via order_date_IMT; affichage MRP corrige."
        if remark:
            industrial_validation_rows.append(
                {
                    "node_id": rec["node_id"],
                    "item_id": rec["item_id"].replace("item:", ""),
                    "standard_order_qty": round(std_qty, 6),
                    "old_day0_qty": round(old_day0_qty, 6),
                    "old_peak_qty": round(old_peak_qty, 6),
                    "old_peak_day": old_peak_day,
                    "imt_peak_qty": round(peak_imt_qty, 6),
                    "imt_peak_day": peak_imt_day,
                    "pre_jan_release_qty": round(max(0.0, rec["pre_jan_release_qty"]), 6),
                    "lots_at_peak": round(lots_at_peak, 3) if std_qty > 1e-9 else "",
                    "remark": remark,
                }
            )
    industrial_validation_rows = sorted(
        industrial_validation_rows,
        key=lambda r: (
            0 if "Concentration" in str(r["remark"]) else 1,
            -max(0.0, to_float(r.get("imt_peak_qty"), 0.0)),
        ),
    )
    if industrial_validation_rows:
        industrial_validation_md = "\n".join(
            [
                "| Noeud | Item | Lot std | Ancien pic J0 | Pic IMT | Jour IMT | Avant J0 | Lots au pic | Remarque |",
                "|---|---:|---:|---:|---:|---:|---:|---:|---|",
            ]
            + [
                "| {node_id} | {item_id} | {standard_order_qty} | {old_day0_qty} | {imt_peak_qty} | {imt_peak_day} | {pre_jan_release_qty} | {lots_at_peak} | {remark} |".format(
                    **row
                )
                for row in industrial_validation_rows[:30]
            ]
        )
    else:
        industrial_validation_md = "Aucune concentration MRP ou lot atypique detecte."
    unmodeled_process_capacity_rows: list[tuple[str, str, str]] = []
    for node in nodes:
        node_id = str(node.get("id") or "")
        for proc in node.get("processes") or []:
            if not (proc.get("inputs") or []):
                continue
            cap = to_float(((proc.get("capacity") or {}).get("max_rate")), 0.0)
            if cap > 0.0:
                continue
            output_ids = [
                str((out or {}).get("item_id") or "").replace("item:", "")
                for out in (proc.get("outputs") or [])
                if str((out or {}).get("item_id") or "")
            ]
            unmodeled_process_capacity_rows.append(
                (node_id, str(proc.get("id") or "n/a"), ", ".join(output_ids) or "n/a")
            )
    if unmodeled_process_capacity_rows:
        capacity_note_lines = [
            "",
            "Process internes sans capacite source: la simulation ne les bloque pas par capacite, mais conserve les contraintes de lots, d'intrants et de besoin.",
            "| Noeud | Process | Sortie |",
            "|---|---|---:|",
        ]
        capacity_note_lines.extend(
            f"| {node_id} | {proc_id} | {outputs} |"
            for node_id, proc_id, outputs in unmodeled_process_capacity_rows[:10]
        )
        industrial_validation_md = f"{industrial_validation_md}\n" + "\n".join(capacity_note_lines)
    report = f"""# First simulation report

## Run setup
- Input: {summary['input_file']}
- Scenario: {summary['scenario_id']}
- Measured horizon (days): {summary['sim_days']}
- Warm-up (days): {summary['warmup_days']}
- Total simulated timeline (days): {summary['timeline_days']}
- Output profile: {summary['policy']['output_profile']}
- Safety stock policy (days): {summary['policy']['safety_stock_days']}
- Replenishment review period (days): {summary['policy']['review_period_days']}
- Finished-goods target cover (days): {summary['policy']['fg_target_days']}
- Production stock-gap gain: {summary['policy']['production_gap_gain']}
- Production smoothing factor: {summary['policy']['production_smoothing']}
- Opening stock bootstrap scale: {summary['policy']['opening_stock_bootstrap_scale']}
- Initialization mode: {summary['policy']['initialization_policy']['mode']}
- Initialization stock days factory / supplier FG / DC / customer: {summary['policy']['initialization_policy']['factory_input_on_hand_days']} / {summary['policy']['initialization_policy']['supplier_output_on_hand_days']} / {summary['policy']['initialization_policy']['distribution_center_on_hand_days']} / {summary['policy']['initialization_policy']['customer_on_hand_days']}
- Initialization seed in-transit / fill ratio / estimated-source pipeline: {summary['policy']['initialization_policy']['seed_in_transit']} / {summary['policy']['initialization_policy']['in_transit_fill_ratio']} / {summary['policy']['initialization_policy']['seed_estimated_source_pipeline']}
- Opening open-orders reconstruction enabled / horizon days: {summary['policy']['initialization_policy']['seed_open_orders_from_january_snapshot']} / {summary['policy']['initialization_policy']['opening_open_orders_horizon_days']}
- Opening open-orders demand multiplier / BOM signal for MRP: {summary['policy']['initialization_policy']['opening_open_orders_demand_multiplier']} / {summary['policy']['initialization_policy']['use_bom_demand_signal_for_mrp']}
- MRP demand signal source: {summary['policy']['initialization_policy']['mrp_demand_signal_source']}
- MRP demand signal smoothing / static fallback on propagated pairs: {summary['policy']['initialization_policy']['mrp_demand_signal_smoothing_days']} j / {summary['policy']['initialization_policy']['mrp_static_fallback_for_propagated_pairs']}
- MRP physical safety floor enforced: {summary['policy']['initialization_policy']['mrp_enforce_physical_safety_floor']}
- Soft safety-time physical stock target factor: {summary['policy']['initialization_policy']['soft_safety_time_stock_target_factor']}
- Unmodeled supplier source mode: {summary['policy']['unmodeled_supplier_source_mode']}
- Stochastic lead times: {summary['policy']['stochastic_lead_times']}
- Random seed: {summary['policy']['seed']}
- Economic policy transport floor /km: {summary['policy']['economic_policy']['transport_cost_floor_per_unit']} / {summary['policy']['economic_policy']['transport_cost_per_km_per_unit']}
- Economic policy purchase floor: {summary['policy']['economic_policy']['purchase_cost_floor_per_unit']}
- Holding cost scale: {summary['policy']['economic_policy']['holding_cost_scale']}
- Inventory cost split capital / warehouse / risk: {summary['policy']['economic_policy']['inventory_capital_cost_share_of_raw_holding']} / {summary['policy']['economic_policy']['warehouse_operating_cost_share_of_raw_holding']} / {summary['policy']['economic_policy']['inventory_risk_cost_share_of_raw_holding']}
- Transport / purchase realism multipliers: {summary['policy']['economic_policy']['transport_cost_realism_multiplier']} / {summary['policy']['economic_policy']['purchase_cost_realism_multiplier']}
- External procurement enabled: {summary['policy']['economic_policy']['external_procurement_enabled']}
- External procurement proactive supplier replenishment: {summary['policy']['economic_policy']['external_procurement_proactive_replenishment']}
- External procurement lead days: {summary['policy']['economic_policy']['external_procurement_lead_days']}
- External procurement daily cap days: {summary['policy']['economic_policy']['external_procurement_daily_cap_days']}
- External procurement min daily cap qty: {summary['policy']['economic_policy']['external_procurement_min_daily_cap_qty']}
- External procurement unit cost / multiplier / transport unit: {summary['policy']['economic_policy']['external_procurement_unit_cost']} / {summary['policy']['economic_policy']['external_procurement_cost_multiplier']} / {summary['policy']['economic_policy']['external_procurement_transport_cost_per_unit']}
- Nodes: {summary['counts']['nodes']}
- Edges: {summary['counts']['edges']}
- Lanes (edge x item): {summary['counts']['lanes']}
- Demand rows: {summary['counts']['demand_rows']}
- Input material pairs tracked: {len(production_input_pairs)}
- Output product pairs tracked: {len(production_output_pairs)} ({output_pairs_txt})
- Inputs non modelises par Relations_acteurs (non bloquants): {len(unconstrained_input_pairs)} ({unconstrained_txt})
- Conversions d'unites BOM appliquees: {conversion_count}
- Mismatch d'unites non convertis: {mismatch_count}
- Assumed supplier nodes (explicitly tagged, includes '?'): {len(assumed_supplier_nodes)} ({assumed_nodes_txt})
- Assumed supply edges (explicitly tagged, includes '?'): {len(assumed_supply_edges)} ({assumed_edges_txt})
- External upstream sourcing for unmodeled source pairs: {len(externally_sourced_pairs)}
- Opening stock bootstrap pairs (lead-time coverage at max capacity): {len(opening_stock_bootstrap_rows)}
- Opening open-order rows reconstructed from January snapshot: {len(opening_open_order_rows)}
- MRP trace tracked pairs / rows / orders: {summary['production_tracking']['mrp_trace']['tracked_pairs']} / {summary['production_tracking']['mrp_trace']['trace_rows']} / {summary['production_tracking']['mrp_trace']['order_rows']}

## KPIs
- Total demand: {summary['kpis']['total_demand']}
- Total served: {summary['kpis']['total_served']}
- Fill rate: {summary['kpis']['fill_rate']}
- Ending backlog: {summary['kpis']['ending_backlog']}
- Total produced: {summary['kpis']['total_produced']}
- Total shipped: {summary['kpis']['total_shipped']}
- Avg inventory: {summary['kpis']['avg_inventory']}
- Ending inventory: {summary['kpis']['ending_inventory']}
- Transport cost: {summary['kpis']['total_transport_cost']}
- Holding cost (capital tied-up): {summary['kpis']['total_holding_cost']}
- Warehouse operating cost: {summary['kpis']['total_warehouse_operating_cost']}
- Inventory risk cost (obsolescence/compliance proxy): {summary['kpis']['total_inventory_risk_cost']}
- Legacy raw holding cost before split: {summary['kpis']['total_inventory_cost_legacy_raw_holding']}
- Purchase cost (from order_terms sell_price): {summary['kpis']['total_purchase_cost']}
- Logistics cost (transport + inventory capital + warehouse + inventory risk): {summary['kpis']['total_logistics_cost']}
- Total cost: {summary['kpis']['total_cost']}
- Total external procured ordered qty: {summary['kpis']['total_external_procured_ordered_qty']}
- Total external procured arrived qty: {summary['kpis']['total_external_procured_arrived_qty']}
- Total external procured rejected qty (cap-limited): {summary['kpis']['total_external_procured_rejected_qty']}
- Total external procurement cost premium: {summary['kpis']['total_external_procurement_cost']}
- Total estimated source ordered qty: {summary['kpis']['total_estimated_source_ordered_qty']}
- Total estimated source replenished qty: {summary['kpis']['total_estimated_source_replenished_qty']}
- Total estimated source rejected qty: {summary['kpis']['total_estimated_source_rejected_qty']}
- Cost share capital holding / warehouse / inventory risk / transport / purchase: {summary['kpis']['cost_share_holding']} / {summary['kpis']['cost_share_warehouse_operating']} / {summary['kpis']['cost_share_inventory_risk']} / {summary['kpis']['cost_share_transport']} / {summary['kpis']['cost_share_purchase']}
- Total opening stock bootstrap qty: {summary['kpis']['total_opening_stock_bootstrap_qty']}
- Total explicit initialization stock qty: {summary['kpis']['total_explicit_initialization_stock_qty']}
- Total explicit initialization pipeline qty: {summary['kpis']['total_explicit_initialization_pipeline_qty']}
- Total opening open-order qty: {summary['kpis']['total_opening_open_order_qty']}
- Total unreliable supplier loss qty: {summary['kpis']['total_unreliable_loss_qty']}
- Total supplier capacity binding qty: {summary['kpis']['total_supplier_capacity_binding_qty']}
- Economic consistency status: {summary['economic_consistency']['status']}
- Economic consistency warnings: {summary['economic_consistency']['warnings']}

## Top backlog pairs
{json.dumps(summary['top_backlog_pairs'], indent=2, ensure_ascii=False)}

## Safety stock reference
Calcul: `stock equiv delai = demande moyenne journaliere planifiee x delai de securite`. Les `safety_stock_qty` explicites sont ignores dans cette variante: seules les durees de securite pilotent la cible. La cible souple simulee applique le facteur `{summary['policy']['initialization_policy']['soft_safety_time_stock_target_factor']}` sur cette couverture.

{safety_reference_preview_md}

## Remarques validation industrielle
Le graphe `Reappro amont` utilise maintenant `order_date_IMT` pour dater les ordres MRP. Les commandes du carnet initial peuvent donc apparaitre avant J0 au lieu d'etre empilees artificiellement au 1er janvier.

{industrial_validation_md}

## Files
- summaries/first_simulation_summary.json
- reports/mrp_safety_stock_reference.csv
- data/production_input_stocks_daily.csv
- data/production_output_products_daily.csv
- data/production_demand_service_daily.csv
- data/production_constraint_daily.csv
- data/mrp_trace_daily.csv
- data/mrp_orders_daily.csv
- data/assumptions_ledger.csv
- data/production_supplier_shipments_daily.csv
- data/production_supplier_stocks_daily.csv
- data/production_supplier_capacity_daily.csv
- Additional detailed CSVs: {'generated' if summary['policy']['output_profile'] == 'full' else 'skipped in compact mode'}
- production_input_stocks_by_material_*.png ({', '.join(detailed_input_plot_paths) if detailed_input_plot_paths else 'not generated'})
- production_output_products.png ({generated_plots.get('production_output_products_png', 'not generated')})
- production_output_products_by_factory_*.png ({', '.join(detailed_output_plot_paths) if detailed_output_plot_paths else 'not generated'})
- production_supplier_input_stocks_by_material_*.png ({', '.join(detailed_supplier_plot_paths) if detailed_supplier_plot_paths else 'not generated'})
- production_dc_factory_outputs_by_material_*.png ({', '.join(detailed_dc_plot_paths) if detailed_dc_plot_paths else 'not generated'})
- maps/supply_graph_poc_geocoded_map_with_factory_hover.html ({generated_map_path or 'not generated'})
"""
    report_output_path.write_text(report, encoding="utf-8")

    print(f"[OK] Simulation summary: {summary_output_path.resolve()}")
    print(f"[OK] Simulation report: {report_output_path.resolve()}")
    print(f"[OK] MRP safety stock reference CSV: {safety_reference_path.resolve()}")
    print(f"[OK] Production input stocks CSV: {input_stock_path.resolve()}")
    print(f"[OK] Production output products CSV: {output_prod_path.resolve()}")
    print(f"[OK] Production demand service CSV: {demand_pair_path.resolve()}")
    print(f"[OK] Production constraint CSV: {production_constraint_path.resolve()}")
    print(f"[OK] MRP trace CSV: {mrp_trace_path.resolve()}")
    print(f"[OK] MRP orders CSV: {mrp_orders_path.resolve()}")
    print(f"[OK] Assumptions ledger CSV: {assumptions_ledger_path.resolve()}")
    print(f"[OK] Production supplier shipments CSV: {supplier_shipment_path.resolve()}")
    print(f"[OK] Production supplier stocks CSV: {supplier_stock_path.resolve()}")
    print(f"[OK] Production supplier capacity CSV: {supplier_capacity_path.resolve()}")
    if compact_output:
        print("[INFO] Compact output profile: detailed daily/input/DC CSVs skipped.")
    else:
        print(f"[OK] Simulation daily CSV: {daily_path.resolve()}")
        print(f"[OK] Production input consumption CSV: {input_consumption_path.resolve()}")
        print(f"[OK] Production input replenishment arrivals CSV: {input_arrival_path.resolve()}")
        print(f"[OK] Production input replenishment shipments CSV: {input_shipment_path.resolve()}")
        print(f"[OK] Production input stocks pivot CSV: {input_pivot_path.resolve()}")
        print(f"[OK] Production distribution center stocks CSV: {dc_stock_path.resolve()}")
    if generated_plots:
        for _, path in sorted(generated_plots.items()):
            print(f"[OK] Plot generated: {Path(path).resolve()}")
    else:
        reason = "--skip-plots" if args.skip_plots else "matplotlib unavailable"
        print(f"[INFO] Plot generation skipped ({reason}).")
    if generated_map_path:
        print(f"[OK] Hover map generated: {Path(generated_map_path).resolve()}")
    elif args.skip_map:
        print("[INFO] Map generation skipped (--skip-map).")


if __name__ == "__main__":
    main()
