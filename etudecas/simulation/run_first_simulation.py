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
        default=30,
        help="Simulation horizon in days (default: 30). Set 0 to use scenario horizon.",
    )
    parser.add_argument(
        "--map-script",
        default="etudecas/affichage_supply_script/build_supplychain_worldmap.py",
        help="Path to map builder script.",
    )
    parser.add_argument(
        "--map-output",
        default="etudecas/simulation/result/supply_graph_poc_geocoded_map_with_factory_hover.html",
        help="Path to generated hover-map HTML.",
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
        if ptype == "constant":
            return to_float(p.get("value"), 0.0)
        if ptype == "step":
            start = int(to_float(p.get("start_day"), 0.0))
            val = to_float(p.get("value"), 0.0)
            if day >= start:
                step_candidates.append((start, val))
        if ptype == "piecewise":
            points = p.get("points") or []
            for pt in points:
                if not isinstance(pt, dict):
                    continue
                t = int(to_float(pt.get("t"), -1))
                v = to_float(pt.get("value"), 0.0)
                if day >= t >= 0:
                    step_candidates.append((t, v))
    if step_candidates:
        step_candidates.sort(key=lambda x: x[0])
        return step_candidates[-1][1]
    return 0.0


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
        cost = explicit_transport_cost if explicit_transport_cost > 0 else fallback_transport_cost
        ot = e.get("order_terms") or {}
        sell_price = to_float((ot or {}).get("sell_price"), 0.0)
        price_base = to_float((ot or {}).get("price_base"), 1.0)
        if price_base <= 0:
            price_base = 1.0
        unit_purchase_cost = max(purchase_floor, max(0.0, sell_price / price_base))
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
                "raw_transport_cost": explicit_transport_cost,
                "transport_cost_is_fallback": explicit_transport_cost <= 0,
                "reliability": reliability,
                "availability_profile": e.get("availability_profile") or [],
            }
            lanes.append(lane)
            lanes_by_dest_item[(dst, str(item_id))].append(lane)

    for key, values in lanes_by_dest_item.items():
        values.sort(key=lambda x: (x["unit_transport_cost"], x["lead_days"], x["src"]))
        lanes_by_dest_item[key] = values
    return lanes, lanes_by_dest_item


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
        out = output_dir / f"production_input_stocks_by_material_{safe_factory}.png"
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
        out = output_dir / "production_output_products.png"
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
        out = output_dir / f"production_output_products_by_factory_{safe_factory}.png"
        plt.savefig(out, dpi=150)
        plt.close()
        generated[f"production_output_products_by_factory_{factory}"] = str(out)

    # Plot 3: supplier view = downstream factory input stocks on supplier-related items.
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
        out = output_dir / f"production_supplier_input_stocks_by_material_{safe_supplier}.png"
        if plot_stock_multiaxis(
            item_map,
            f"Stocks d'entree usine (produits du fournisseur) - {supplier}",
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
        out = output_dir / f"production_dc_factory_outputs_by_material_{safe_dc}.png"
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

    data = json.loads(input_path.read_text(encoding="utf-8"))
    nodes = data.get("nodes", []) or []
    edges = data.get("edges", []) or []
    node_by_id = {str(n.get("id")): n for n in nodes}
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
    safety_stock_days = max(0.0, scenario_policy_value(scenario, "safety_stock_days", 7.0))
    review_period_days = max(1, int(round(scenario_policy_value(scenario, "review_period_days", 1.0))))
    fg_target_days = max(0.0, scenario_policy_value(scenario, "fg_target_days", 0.0))
    production_gap_gain = max(0.0, scenario_policy_value(scenario, "production_gap_gain", 0.25))
    production_smoothing = min(0.95, max(0.0, scenario_policy_value(scenario, "production_smoothing", 0.20)))
    economic_policy_cfg = scenario_policy_dict(scenario, "economic_policy")
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
    rng = random.Random(args.seed)

    stock: dict[tuple[str, str], float] = defaultdict(float)
    holding_cost: dict[tuple[str, str], float] = defaultdict(float)
    base_stock: dict[tuple[str, str], float] = defaultdict(float)
    for n in nodes:
        nid = str(n.get("id"))
        inv = n.get("inventory") or {}
        for st in (inv.get("states") or []):
            key = (nid, str(st.get("item_id")))
            initial = to_float(st.get("initial"), 0.0)
            stock[key] = initial
            base_stock[key] = initial
            hc = st.get("holding_cost") or {}
            holding_cost[key] = to_float((hc or {}).get("value"), 0.0) * economic_policy["holding_cost_scale"]

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
    supplier_factory_items: dict[str, set[tuple[str, str]]] = defaultdict(set)
    for lane in lanes:
        src = str(lane["src"])
        dst = str(lane["dst"])
        item_id = str(lane["item_id"])
        if src in supplier_node_ids and node_type_by_id.get(dst) == "factory":
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
    # If a (node,item) can ship downstream but has no modeled inbound/production source,
    # treat missing upstream as external procurement to avoid artificial source depletion.
    externally_sourced_pairs = sorted(outbound_pairs - inbound_pairs - produced_pairs)
    externally_sourced_pairs_set = set(externally_sourced_pairs)
    demand_rows = scenario.get("demand", []) or []
    demand_pairs = [(str(d.get("node_id")), str(d.get("item_id"))) for d in demand_rows]
    demand_profiles = {
        (str(d.get("node_id")), str(d.get("item_id"))): (d.get("profile") or [])
        for d in demand_rows
    }
    demand_target_daily = {
        pair: profile_value(profile, 0)
        for pair, profile in demand_profiles.items()
    }
    propagated_demand_daily = propagate_demand_rates(demand_target_daily, lanes)

    # Small safety target for pairs with demand signal if base stock is absent.
    for pair, d0 in propagated_demand_daily.items():
        if pair not in inbound_pairs:
            continue
        if base_stock.get(pair, 0.0) <= 0:
            base_stock[pair] = max(50.0, 7.0 * d0)

    backlog: dict[tuple[str, str], float] = defaultdict(float)
    pipeline: dict[int, list[tuple[str, str, float, str]]] = defaultdict(list)
    external_pipeline: dict[int, list[tuple[str, str, float]]] = defaultdict(list)
    in_transit: dict[tuple[str, str], float] = defaultdict(float)
    external_in_transit: dict[tuple[str, str], float] = defaultdict(float)

    total_demand = 0.0
    total_served = 0.0
    total_shipped = 0.0
    total_arrived = 0.0
    total_produced = 0.0
    total_transport_cost = 0.0
    total_holding_cost = 0.0
    total_external_procured = 0.0
    total_external_procured_arrived = 0.0
    total_external_procured_rejected = 0.0
    total_unreliable_loss_qty = 0.0
    total_purchase_cost = 0.0
    total_external_procurement_cost = 0.0

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
    cum_output_by_pair: dict[tuple[str, str], float] = defaultdict(float)
    prev_production_command_by_pair: dict[tuple[str, str], float] = {}
    pair_max_lead_days: dict[tuple[str, str], int] = {}
    pair_stock_cover_days: dict[tuple[str, str], int] = {}
    for pair, lane_list in lanes_by_dest_item.items():
        pair_max_lead_days[pair] = max(int(to_float(l.get("lead_days"), 1.0)) for l in lane_list) if lane_list else 1
        max_cover = max(lead_time_cover_days(l, args.stochastic_lead_times) for l in lane_list) if lane_list else 1
        pair_stock_cover_days[pair] = max_cover + review_period_days

    # Bootstrap opening stocks for production inputs so each pair can cover at least its lead-time demand.
    # This avoids artificial periodic starvation when initial stock is below lead-time consumption.
    opening_stock_bootstrap_rows: list[dict[str, Any]] = []
    total_opening_stock_bootstrap = 0.0
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
    opening_stock_bootstrap_rows.sort(key=lambda r: (r["node_id"], r["item_id"]))

    for day in range(sim_days):
        demand_target_today = {
            pair: max(0.0, profile_value(profile, day))
            for pair, profile in demand_profiles.items()
        }
        propagated_demand_today = propagate_demand_rates(demand_target_today, lanes)

        arrivals_today = pipeline.pop(day, [])
        external_arrivals_today = external_pipeline.pop(day, [])
        arrivals_qty = 0.0
        external_arrivals_qty = 0.0
        arrivals_today_by_pair: dict[tuple[str, str], float] = defaultdict(float)
        for dst, item_id, qty, _lane_id in arrivals_today:
            stock[(dst, item_id)] += qty
            in_transit[(dst, item_id)] -= qty
            arrivals_qty += qty
            arrivals_today_by_pair[(dst, item_id)] += qty
        for src, item_id, qty in external_arrivals_today:
            stock[(src, item_id)] += qty
            external_in_transit[(src, item_id)] -= qty
            external_arrivals_qty += qty
        total_arrived += arrivals_qty
        total_external_procured_arrived += external_arrivals_qty

        # Snapshot: raw material stocks at production input before production starts.
        day_input_rows_by_pair: dict[tuple[str, str], dict[str, Any]] = {}
        for node_id, item_id in production_input_pairs:
            row = {
                "day": day,
                "node_id": node_id,
                "item_id": item_id,
                "stock_before_production": round(stock[(node_id, item_id)], 6),
                "stock_end_of_day": 0.0,
            }
            input_stock_rows.append(row)
            day_input_rows_by_pair[(node_id, item_id)] = row
            input_arrival_rows.append(
                {
                    "day": day,
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
                cap = to_float(((p.get("capacity") or {}).get("max_rate")), 0.0)
                if cap <= 0:
                    continue

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
                out_signal = max(0.0, propagated_demand_today.get(out_pair, 0.0))
                out_stock = max(0.0, stock[out_pair])
                out_target = max(base_stock.get(out_pair, 0.0), fg_target_days * out_signal)
                out_gap = out_target - out_stock
                raw_command = out_signal + production_gap_gain * out_gap

                if out_signal <= 1e-9 and out_pair not in lanes_by_src_item:
                    # Preserve previous behavior for isolated processes not linked to demand flow.
                    raw_command = cap

                prev_cmd = prev_production_command_by_pair.get(out_pair, raw_command)
                desired_qty = production_smoothing * prev_cmd + (1.0 - production_smoothing) * raw_command
                desired_qty = max(0.0, desired_qty)
                prev_production_command_by_pair[out_pair] = desired_qty

                qty = max(0.0, min(cap, max_from_inputs, desired_qty))
                binding_cause = "none"
                binding_item = ""
                if desired_qty > 1e-9:
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
                    if qty + 1e-9 < desired_qty:
                        if max_from_inputs <= cap + 1e-9 and max_from_inputs <= desired_qty + 1e-9:
                            binding_cause = "input_shortage"
                            binding_item = input_binding_item
                        elif cap <= max_from_inputs + 1e-9 and cap <= desired_qty + 1e-9:
                            binding_cause = "capacity"
                        else:
                            binding_cause = "policy_command"
                    production_constraint_rows.append(
                        {
                            "day": day,
                            "node_id": nid,
                            "output_item_id": out_item,
                            "desired_qty": round(desired_qty, 6),
                            "actual_qty": round(qty, 6),
                            "cap_qty": round(cap, 6),
                            "max_from_inputs_qty": round(max_from_inputs, 6),
                            "binding_cause": binding_cause,
                            "binding_input_item_id": binding_item,
                            "shortfall_vs_desired_qty": round(max(0.0, desired_qty - qty), 6),
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

        total_produced += produced_today
        for node_id, item_id in production_output_pairs:
            q = produced_today_by_pair[(node_id, item_id)]
            cum_output_by_pair[(node_id, item_id)] += q
            output_prod_rows.append(
                {
                    "day": day,
                    "node_id": node_id,
                    "item_id": item_id,
                    "produced_qty": round(q, 6),
                    "cum_produced_qty": round(cum_output_by_pair[(node_id, item_id)], 6),
                }
            )
        for node_id, item_id in production_input_pairs:
            input_consumption_rows.append(
                {
                    "day": day,
                    "node_id": node_id,
                    "item_id": item_id,
                    "consumed_qty": round(consumed_today_by_pair[(node_id, item_id)], 6),
                    "uom": item_unit_map.get(item_id, ""),
                }
            )

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
            demand_pair_rows.append(
                {
                    "day": day,
                    "node_id": pair[0],
                    "item_id": pair[1],
                    "demand_qty": round(dval, 6),
                    "required_with_backlog_qty": round(required, 6),
                    "served_qty": round(served, 6),
                    "backlog_end_qty": round(backlog[pair], 6),
                    "available_before_service_qty": round(available, 6),
                }
            )

        total_demand += demand_today
        total_served += served_today

        # Replenishment and shipments
        shipped_today = 0.0
        transport_cost_today = 0.0
        purchase_cost_today = 0.0
        external_procured_today = 0.0
        external_procured_rejected_today = 0.0
        shipped_today_to_pair: dict[tuple[str, str], float] = defaultdict(float)
        external_ordered_today_by_src_pair: dict[tuple[str, str], float] = defaultdict(float)
        for pair, lane_list in lanes_by_dest_item.items():
            dst, item_id = pair
            target = base_stock.get(pair, 0.0)
            item_daily_req = required_daily_input_by_pair.get(pair, propagated_demand_today.get(pair, 0.0))
            if item_daily_req > 0:
                target = max(
                    target,
                    safety_stock_days * item_daily_req,
                    item_daily_req * float(pair_stock_cover_days.get(pair, review_period_days + 1)),
                )
            target += backlog[pair]

            if day % review_period_days != 0:
                continue

            needed = target - stock[pair] - in_transit[pair]
            if needed <= 1e-9:
                continue

            remaining = needed
            for lane in lane_list:
                if remaining <= 1e-9:
                    break
                lane_review_days = int(round(max(1.0, to_float(lane.get("order_frequency_days"), 1.0))))
                if day % lane_review_days != 0:
                    continue
                src_pair = (lane["src"], item_id)
                availability_mult = lane_availability_multiplier(lane, day)
                if availability_mult <= 1e-9:
                    continue
                available = stock[src_pair] * availability_mult
                if src_pair in externally_sourced_pairs_set and available < remaining:
                    if economic_policy["external_procurement_enabled"]:
                        ext_gap = remaining - available
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
                            purchase_cost_today += ext_order_qty * ext_unit_purchase
                            transport_cost_today += ext_order_qty * ext_unit_transport
                            total_external_procurement_cost += ext_order_cost
                        ext_rejected = max(0.0, ext_gap - ext_order_qty)
                        external_procured_rejected_today += ext_rejected
                    available = stock[src_pair]
                if available <= 1e-9:
                    continue
                rel = max(0.01, min(1.0, to_float(lane.get("reliability"), 1.0)))
                pull_qty = min(available, remaining / rel)
                delivered_qty = pull_qty * rel
                if pull_qty <= 1e-9 or delivered_qty <= 1e-9:
                    continue

                stock[src_pair] -= pull_qty
                lead_days = sample_lead_days(lane, rng, args.stochastic_lead_times)
                arrival_day = day + lead_days
                pipeline[arrival_day].append((dst, item_id, delivered_qty, lane["edge_id"]))
                in_transit[pair] += delivered_qty
                remaining -= delivered_qty
                shipped_today += delivered_qty
                shipped_today_to_pair[(dst, item_id)] += delivered_qty
                transport_cost_today += delivered_qty * lane["unit_transport_cost"]
                purchase_cost_today += delivered_qty * lane["unit_purchase_cost"]
                total_unreliable_loss_qty += max(0.0, pull_qty - delivered_qty)
                supplier_shipment_rows.append(
                    {
                        "day": day,
                        "src_node_id": str(lane["src"]),
                        "dst_node_id": str(dst),
                        "item_id": str(item_id),
                        "shipped_qty": round(delivered_qty, 6),
                        "pulled_qty": round(pull_qty, 6),
                        "lead_days": int(lead_days),
                        "arrival_day": int(arrival_day),
                        "reliability": round(rel, 6),
                        "uom": item_unit_map.get(item_id, ""),
                    }
                )

        total_shipped += shipped_today
        total_transport_cost += transport_cost_today
        total_purchase_cost += purchase_cost_today
        total_external_procured += external_procured_today
        total_external_procured_rejected += external_procured_rejected_today
        for node_id, item_id in production_input_pairs:
            input_shipment_rows.append(
                {
                    "day": day,
                    "node_id": node_id,
                    "item_id": item_id,
                    "shipped_to_node_qty": round(shipped_today_to_pair[(node_id, item_id)], 6),
                    "uom": item_unit_map.get(item_id, ""),
                }
            )

        # End-of-day holding costs
        inv_total_today = 0.0
        holding_cost_today = 0.0
        for key, qty in stock.items():
            if qty <= 0:
                continue
            inv_total_today += qty
            holding_cost_today += qty * holding_cost.get(key, 0.0)
        total_holding_cost += holding_cost_today

        for node_id, item_id in production_input_pairs:
            row = day_input_rows_by_pair.get((node_id, item_id))
            if row is not None:
                row["stock_end_of_day"] = round(stock[(node_id, item_id)], 6)

        for node_id, item_id in supplier_stock_pairs:
            supplier_stock_rows.append(
                {
                    "day": day,
                    "node_id": node_id,
                    "item_id": item_id,
                    "stock_end_of_day": round(stock[(node_id, item_id)], 6),
                }
            )
        for node_id, item_id in dc_stock_pairs:
            dc_stock_rows.append(
                {
                    "day": day,
                    "node_id": node_id,
                    "item_id": item_id,
                    "stock_end_of_day": round(stock[(node_id, item_id)], 6),
                }
            )

        daily_rows.append(
            {
                "day": day,
                "demand": round(demand_today, 4),
                "served": round(served_today, 4),
                "backlog_end": round(sum(backlog.values()), 4),
                "arrivals_qty": round(arrivals_qty, 4),
                "produced_qty": round(produced_today, 4),
                "shipped_qty": round(shipped_today, 4),
                "inventory_total": round(inv_total_today, 4),
                "holding_cost_day": round(holding_cost_today, 4),
                "transport_cost_day": round(transport_cost_today, 4),
                "purchase_cost_day": round(purchase_cost_today, 4),
                "external_procured_ordered_qty": round(external_procured_today, 4),
                "external_procured_arrived_qty": round(external_arrivals_qty, 4),
                "external_procured_rejected_qty": round(external_procured_rejected_today, 4),
            }
        )

    ending_inventory = sum(v for v in stock.values() if v > 0)
    ending_backlog = sum(v for v in backlog.values() if v > 0)
    fill_rate = (total_served / total_demand) if total_demand > 0 else 1.0
    avg_inventory = sum(r["inventory_total"] for r in daily_rows) / len(daily_rows) if daily_rows else 0.0

    top_backlog = sorted(
        [
            {"node_id": pair[0], "item_id": pair[1], "backlog": round(val, 4)}
            for pair, val in backlog.items()
            if val > 0
        ],
        key=lambda x: -x["backlog"],
    )[:10]
    total_cost = total_transport_cost + total_holding_cost + total_purchase_cost
    holding_share = total_holding_cost / max(1e-12, total_cost)
    transport_share = total_transport_cost / max(1e-12, total_cost)
    purchase_share = total_purchase_cost / max(1e-12, total_cost)
    economic_warnings: list[str] = []
    if holding_share > 0.90:
        economic_warnings.append("holding_cost_share_above_90pct")
    if transport_share < 0.02:
        economic_warnings.append("transport_cost_share_below_2pct")
    if purchase_share < 0.02:
        economic_warnings.append("purchase_cost_share_below_2pct")
    if total_external_procured > 0 and total_external_procured_arrived <= 1e-9:
        economic_warnings.append("external_procurement_ordered_but_not_arrived_in_horizon")

    summary = {
        "input_file": str(input_path),
        "scenario_id": str(scenario.get("id")),
        "sim_days": sim_days,
        "policy": {
            "safety_stock_days": safety_stock_days,
            "review_period_days": review_period_days,
            "fg_target_days": fg_target_days,
            "production_gap_gain": production_gap_gain,
            "production_smoothing": production_smoothing,
            "opening_stock_bootstrap_scale": opening_stock_bootstrap_scale,
            "stochastic_lead_times": bool(args.stochastic_lead_times),
            "seed": int(args.seed),
            "economic_policy": {
                "transport_cost_floor_per_unit": economic_policy["transport_cost_floor_per_unit"],
                "transport_cost_per_km_per_unit": economic_policy["transport_cost_per_km_per_unit"],
                "purchase_cost_floor_per_unit": economic_policy["purchase_cost_floor_per_unit"],
                "holding_cost_scale": economic_policy["holding_cost_scale"],
                "external_procurement_enabled": economic_policy["external_procurement_enabled"],
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
            "lane_purchase_cost_stats": {
                "lanes_with_positive_purchase_cost": sum(1 for l in lanes if to_float(l.get("unit_purchase_cost"), 0.0) > 0),
                "lanes_with_zero_purchase_cost": sum(1 for l in lanes if to_float(l.get("unit_purchase_cost"), 0.0) <= 0),
                "lanes_with_explicit_transport_cost": lanes_with_explicit_transport_cost,
                "lanes_with_fallback_transport_cost": lanes_with_fallback_transport_cost,
            },
        },
        "kpis": {
            "total_demand": round(total_demand, 4),
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
            "total_purchase_cost": round(total_purchase_cost, 4),
            "total_logistics_cost": round(total_transport_cost + total_holding_cost, 4),
            "total_cost": round(total_cost, 4),
            "total_external_procured_ordered_qty": round(total_external_procured, 4),
            "total_external_procured_arrived_qty": round(total_external_procured_arrived, 4),
            "total_external_procured_rejected_qty": round(total_external_procured_rejected, 4),
            "total_external_procured_qty": round(total_external_procured, 4),
            "total_external_procurement_cost": round(total_external_procurement_cost, 4),
            "total_opening_stock_bootstrap_qty": round(total_opening_stock_bootstrap, 4),
            "total_unreliable_loss_qty": round(total_unreliable_loss_qty, 4),
            "cost_share_holding": round(holding_share, 6),
            "cost_share_transport": round(transport_share, 6),
            "cost_share_purchase": round(purchase_share, 6),
        },
        "economic_consistency": {
            "status": "warn" if economic_warnings else "ok",
            "warnings": economic_warnings,
            "transport_cost_share_target_min": 0.02,
            "holding_cost_share_target_max": 0.90,
        },
        "top_backlog_pairs": top_backlog,
    }

    summary_path = output_dir / "first_simulation_summary.json"
    daily_path = output_dir / "first_simulation_daily.csv"
    report_path = output_dir / "first_simulation_report.md"
    input_stock_path = output_dir / "production_input_stocks_daily.csv"
    input_consumption_path = output_dir / "production_input_consumption_daily.csv"
    input_arrival_path = output_dir / "production_input_replenishment_arrivals_daily.csv"
    input_shipment_path = output_dir / "production_input_replenishment_shipments_daily.csv"
    output_prod_path = output_dir / "production_output_products_daily.csv"
    supplier_shipment_path = output_dir / "production_supplier_shipments_daily.csv"
    supplier_stock_path = output_dir / "production_supplier_stocks_daily.csv"
    dc_stock_path = output_dir / "production_dc_stocks_daily.csv"
    demand_pair_path = output_dir / "production_demand_service_daily.csv"
    production_constraint_path = output_dir / "production_constraint_daily.csv"

    summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
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

    with input_consumption_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["day", "node_id", "item_id", "consumed_qty", "uom"])
        writer.writeheader()
        writer.writerows(input_consumption_rows)

    with input_arrival_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["day", "node_id", "item_id", "arrived_qty", "uom"])
        writer.writeheader()
        writer.writerows(input_arrival_rows)

    with input_shipment_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["day", "node_id", "item_id", "shipped_to_node_qty", "uom"])
        writer.writeheader()
        writer.writerows(input_shipment_rows)

    with output_prod_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["day", "node_id", "item_id", "produced_qty", "cum_produced_qty"])
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
                "actual_qty",
                "cap_qty",
                "max_from_inputs_qty",
                "binding_cause",
                "binding_input_item_id",
                "shortfall_vs_desired_qty",
            ],
        )
        writer.writeheader()
        writer.writerows(production_constraint_rows)

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
            ],
        )
        writer.writeheader()
        writer.writerows(supplier_shipment_rows)

    with supplier_stock_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["day", "node_id", "item_id", "stock_end_of_day"])
        writer.writeheader()
        writer.writerows(supplier_stock_rows)

    with dc_stock_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["day", "node_id", "item_id", "stock_end_of_day"])
        writer.writeheader()
        writer.writerows(dc_stock_rows)

    # Pivot file for easier read: one column per (factory,item) input stock.
    input_pairs = sorted({(str(r["node_id"]), str(r["item_id"])) for r in input_stock_rows})
    input_pivot_path = output_dir / "production_input_stocks_pivot.csv"
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
    map_output_path = Path(args.map_output)
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
                "--sim-input-stocks-png-dir",
                str(output_dir),
                "--sim-output-products-png-dir",
                str(output_dir),
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
    report = f"""# First simulation report

## Run setup
- Input: {summary['input_file']}
- Scenario: {summary['scenario_id']}
- Horizon (days): {summary['sim_days']}
- Safety stock policy (days): {summary['policy']['safety_stock_days']}
- Replenishment review period (days): {summary['policy']['review_period_days']}
- Finished-goods target cover (days): {summary['policy']['fg_target_days']}
- Production stock-gap gain: {summary['policy']['production_gap_gain']}
- Production smoothing factor: {summary['policy']['production_smoothing']}
- Opening stock bootstrap scale: {summary['policy']['opening_stock_bootstrap_scale']}
- Stochastic lead times: {summary['policy']['stochastic_lead_times']}
- Random seed: {summary['policy']['seed']}
- Economic policy transport floor /km: {summary['policy']['economic_policy']['transport_cost_floor_per_unit']} / {summary['policy']['economic_policy']['transport_cost_per_km_per_unit']}
- Economic policy purchase floor: {summary['policy']['economic_policy']['purchase_cost_floor_per_unit']}
- Holding cost scale: {summary['policy']['economic_policy']['holding_cost_scale']}
- External procurement enabled: {summary['policy']['economic_policy']['external_procurement_enabled']}
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
- Holding cost: {summary['kpis']['total_holding_cost']}
- Purchase cost (from order_terms sell_price): {summary['kpis']['total_purchase_cost']}
- Logistics cost (transport + holding): {summary['kpis']['total_logistics_cost']}
- Total cost: {summary['kpis']['total_cost']}
- Total external procured ordered qty: {summary['kpis']['total_external_procured_ordered_qty']}
- Total external procured arrived qty: {summary['kpis']['total_external_procured_arrived_qty']}
- Total external procured rejected qty (cap-limited): {summary['kpis']['total_external_procured_rejected_qty']}
- Total external procurement cost premium: {summary['kpis']['total_external_procurement_cost']}
- Cost share holding / transport / purchase: {summary['kpis']['cost_share_holding']} / {summary['kpis']['cost_share_transport']} / {summary['kpis']['cost_share_purchase']}
- Total opening stock bootstrap qty: {summary['kpis']['total_opening_stock_bootstrap_qty']}
- Total unreliable supplier loss qty: {summary['kpis']['total_unreliable_loss_qty']}
- Economic consistency status: {summary['economic_consistency']['status']}
- Economic consistency warnings: {summary['economic_consistency']['warnings']}

## Top backlog pairs
{json.dumps(summary['top_backlog_pairs'], indent=2, ensure_ascii=False)}

## Files
- first_simulation_summary.json
- first_simulation_daily.csv
- production_input_stocks_daily.csv
- production_input_consumption_daily.csv
- production_input_replenishment_arrivals_daily.csv
- production_input_replenishment_shipments_daily.csv
- production_input_stocks_pivot.csv
- production_output_products_daily.csv
- production_demand_service_daily.csv
- production_constraint_daily.csv
- production_supplier_shipments_daily.csv
- production_supplier_stocks_daily.csv
- production_dc_stocks_daily.csv
- production_input_stocks_by_material_*.png ({', '.join(detailed_input_plot_paths) if detailed_input_plot_paths else 'not generated'})
- production_output_products.png ({generated_plots.get('production_output_products_png', 'not generated')})
- production_output_products_by_factory_*.png ({', '.join(detailed_output_plot_paths) if detailed_output_plot_paths else 'not generated'})
- production_supplier_input_stocks_by_material_*.png ({', '.join(detailed_supplier_plot_paths) if detailed_supplier_plot_paths else 'not generated'})
- production_dc_factory_outputs_by_material_*.png ({', '.join(detailed_dc_plot_paths) if detailed_dc_plot_paths else 'not generated'})
- supply_graph_poc_geocoded_map_with_factory_hover.html ({generated_map_path or 'not generated'})
"""
    report_path.write_text(report, encoding="utf-8")

    print(f"[OK] Simulation summary: {summary_path.resolve()}")
    print(f"[OK] Simulation daily CSV: {daily_path.resolve()}")
    print(f"[OK] Simulation report: {report_path.resolve()}")
    print(f"[OK] Production input stocks CSV: {input_stock_path.resolve()}")
    print(f"[OK] Production input consumption CSV: {input_consumption_path.resolve()}")
    print(f"[OK] Production input replenishment arrivals CSV: {input_arrival_path.resolve()}")
    print(f"[OK] Production input replenishment shipments CSV: {input_shipment_path.resolve()}")
    print(f"[OK] Production input stocks pivot CSV: {input_pivot_path.resolve()}")
    print(f"[OK] Production output products CSV: {output_prod_path.resolve()}")
    print(f"[OK] Production demand service CSV: {demand_pair_path.resolve()}")
    print(f"[OK] Production constraint CSV: {production_constraint_path.resolve()}")
    print(f"[OK] Production supplier shipments CSV: {supplier_shipment_path.resolve()}")
    print(f"[OK] Production supplier stocks CSV: {supplier_stock_path.resolve()}")
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
