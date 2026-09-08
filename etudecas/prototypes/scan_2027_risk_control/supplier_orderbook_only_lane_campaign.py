#!/usr/bin/env python3
"""Replay and stress the two supplier lanes evidenced only by the 2025 order book.

The source graph and every earlier campaign stay untouched.  ``snapshot``
replays the dated purchase orders at the 2025-01-01 snapshot (warm-up zero).
``prospective-severe`` is a separate hypothesis that reduces only the target
component stock to 90 or 30 days at the V10 simulated consumption rate.  It is
never merged with the observed-snapshot results.

The campaign keeps opening-order and dynamic flows separate, requires positive
pulled and shipped quantities in each snapshot reference, and exports the
native purchase-order audit plus lot/genealogy evidence before summary pruning.
``source_row`` is always a technical source-line identifier, never an
industrial purchase-order or lot number.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import shutil
import subprocess
import sys
from collections import defaultdict, deque
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from etudecas.prototypes.scan_2027_risk_control import (  # noqa: E402
    supplier_021081_active_flow_campaign as active,
)
from etudecas.prototypes.scan_2027_risk_control import (  # noqa: E402
    supplier_service_landscape_campaign as service,
)


DEFAULT_GRAPH = active.DEFAULT_GRAPH
DEFAULT_ENGINE = active.DEFAULT_ENGINE
DEFAULT_PROFILE = active.DEFAULT_PROFILE
DEFAULT_V10 = (
    active.ARTIFACT_PARENT / "supplier_service_landscape_calibration_20260831_v10"
)
DEFAULT_SEED = 423081
TARGET_PRODUCT = "268091"
TARGET_ITEM = "item:268091"
CLIENT_NODE = "C-XXXXX"
RISK_FIELDS = active.RISK_FIELDS
ORCHESTRATOR_SHA256 = active.sha256_file(Path(__file__).resolve())


@dataclass(frozen=True)
class LaneSpec:
    lane_id: str
    supplier_id: str
    item_id: str
    destination_id: str
    expected_row_count: int
    expected_standard_qty: float
    standard_uom: str
    expected_physical_days: tuple[int, int]
    expected_usable_days: tuple[int, int]
    v10_measurement_start_qty: float
    v10_horizon_consumption_qty: float
    v10_dynamic_arrival_qty: float

    @property
    def item_code(self) -> str:
        return self.item_id.replace("item:", "")

    @property
    def v10_daily_consumption(self) -> float:
        return self.v10_horizon_consumption_qty / 720.0


LANES = (
    LaneSpec(
        lane_id="vd0951020a_001848_m1810",
        supplier_id="SDC-VD0951020A",
        item_id="item:001848",
        destination_id="M-1810",
        expected_row_count=1,
        expected_standard_qty=6_000.0,
        standard_uom="KG",
        expected_physical_days=(50, 50),
        expected_usable_days=(69, 69),
        v10_measurement_start_qty=7_579.1484,
        v10_horizon_consumption_qty=8_857.296,
        v10_dynamic_arrival_qty=8_000.0,
    ),
    LaneSpec(
        lane_id="vd0910216a_002612_m1810",
        supplier_id="SDC-VD0910216A",
        item_id="item:002612",
        destination_id="M-1810",
        expected_row_count=2,
        expected_standard_qty=45_000.0,
        standard_uom="KG",
        expected_physical_days=(19, 35),
        expected_usable_days=(29, 47),
        v10_measurement_start_qty=149_049.140719,
        v10_horizon_consumption_qty=14_762.16,
        v10_dynamic_arrival_qty=0.0,
    ),
)
LANE_BY_ID = {lane.lane_id: lane for lane in LANES}


@dataclass(frozen=True)
class Scenario:
    scenario_id: str
    mechanism: str
    risk_type: str
    value: float
    value_unit: str
    label: str
    is_baseline: bool = False


SCENARIOS = (
    Scenario(
        "baseline_orderbook_replay",
        "baseline",
        "",
        1.0,
        "reference",
        "Référence : carnet planifié rejoué sans incident",
        True,
    ),
    Scenario("delivery_delay_60", "delivery_delay", "lead_time_extra_days", 60.0, "jours", "Retard ajouté de 60 jours"),
    Scenario("delivery_delay_180", "delivery_delay", "lead_time_extra_days", 180.0, "jours", "Retard ajouté de 180 jours"),
    Scenario("delivery_availability_0p75", "delivery_availability", "availability", 0.75, "ratio", "75 % de la quantité planifiée disponible"),
    Scenario("delivery_availability_0p25", "delivery_availability", "availability", 0.25, "ratio", "25 % de la quantité planifiée disponible"),
    Scenario("quality_hold_60", "quality_hold", "quality_delay", 60.0, "jours", "Libération qualité décalée de 60 jours"),
    Scenario("quality_hold_180", "quality_hold", "quality_delay", 180.0, "jours", "Libération qualité décalée de 180 jours"),
)
SCENARIO_BY_ID = {scenario.scenario_id: scenario for scenario in SCENARIOS}
SEVERE_SCENARIO_IDS = (
    "delivery_delay_180",
    "delivery_availability_0p25",
    "quality_hold_180",
)


class CampaignValidationError(RuntimeError):
    pass


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def parse_seeds(raw: str) -> tuple[int, ...]:
    seeds: list[int] = []
    for chunk in str(raw).split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        if "-" in chunk:
            first, last = (int(value) for value in chunk.split("-", 1))
            seeds.extend(range(first, last + (1 if last >= first else -1), 1 if last >= first else -1))
        else:
            seeds.append(int(chunk))
    result = tuple(dict.fromkeys(seeds))
    if not result:
        raise ValueError("At least one seed is required")
    return result


def _sum(rows: Iterable[Mapping[str, Any]], field: str) -> float:
    return sum(max(0.0, active.to_float(row.get(field))) for row in rows)


def _standard_qty(row: Mapping[str, Any], standard_uom: str) -> float:
    qty = max(0.0, active.to_float(row.get("quantity")))
    raw_uom = str(row.get("uom") or standard_uom).upper()
    target = standard_uom.upper()
    if raw_uom == target:
        return qty
    if raw_uom == "G" and target == "KG":
        return qty / 1000.0
    if raw_uom == "KG" and target == "G":
        return qty * 1000.0
    raise CampaignValidationError(
        f"Unsupported source-order unit conversion: {raw_uom} -> {target}"
    )


def lane_orders(graph: Mapping[str, Any], lane: LaneSpec) -> list[dict[str, Any]]:
    return [
        dict(row)
        for row in active.opening_order_payload(graph)["rows"]
        if isinstance(row, Mapping)
        and str(row.get("order_type") or "") == "purchase_open_order"
        and str(row.get("src_node_id") or "") == lane.supplier_id
        and str(row.get("dst_node_id") or "") == lane.destination_id
        and str(row.get("item_id") or "") == lane.item_id
    ]


def source_order_audit(graph: Mapping[str, Any], lane: LaneSpec) -> dict[str, Any]:
    rows = lane_orders(graph, lane)
    quantities = [_standard_qty(row, lane.standard_uom) for row in rows]
    physical = [active.to_int(row.get("physical_delivery_day"), -1) for row in rows]
    usable = [active.to_int(row.get("usable_day"), -1) for row in rows]
    source_rows = [active.to_int(row.get("source_row"), -1) for row in rows]
    errors: list[str] = []
    if len(rows) != lane.expected_row_count:
        errors.append(f"expected {lane.expected_row_count} rows, found {len(rows)}")
    if not math.isclose(sum(quantities), lane.expected_standard_qty, abs_tol=1e-6):
        errors.append(
            f"expected {lane.expected_standard_qty:g} {lane.standard_uom}, "
            f"found {sum(quantities):g}"
        )
    if physical and (min(physical), max(physical)) != lane.expected_physical_days:
        errors.append("planned physical-day range mismatch")
    if usable and (min(usable), max(usable)) != lane.expected_usable_days:
        errors.append("planned usable-day range mismatch")
    if len(source_rows) != len(set(source_rows)) or any(value < 0 for value in source_rows):
        errors.append("missing or duplicate technical source_row")
    if errors:
        raise CampaignValidationError(f"{lane.lane_id}: {'; '.join(errors)}")
    return {
        "lane_id": lane.lane_id,
        "supplier_id": lane.supplier_id,
        "item_id": lane.item_id,
        "destination_id": lane.destination_id,
        "observed_snapshot_order_row_count": len(rows),
        "observed_snapshot_order_qty_standard": sum(quantities),
        "standard_uom": lane.standard_uom,
        "raw_uoms": "|".join(sorted({str(row.get("uom") or "") for row in rows})),
        "physical_delivery_day_min": min(physical),
        "physical_delivery_day_max": max(physical),
        "usable_day_min": min(usable),
        "usable_day_max": max(usable),
        "source_rows": "|".join(str(value) for value in sorted(source_rows)),
        "date_semantics": "planned dates in one ERP snapshot, not actual delivery history or OTIF",
        "source_row_semantics": "technical source-line identifier, not an industrial order or lot number",
        "validated": True,
    }


def _edge_id(graph: Mapping[str, Any], lane: LaneSpec) -> str:
    matches = [
        str(edge.get("id") or "")
        for edge in graph.get("edges") or []
        if isinstance(edge, Mapping)
        and str(edge.get("from") or edge.get("source") or "") == lane.supplier_id
        and str(edge.get("to") or edge.get("target") or "") == lane.destination_id
        and lane.item_id in (edge.get("items") or [edge.get("item_id")])
    ]
    if len(matches) != 1 or not matches[0]:
        raise CampaignValidationError(f"Expected one graph edge for {lane.lane_id}")
    return matches[0]


def risk_rows(
    graph: Mapping[str, Any], lane: LaneSpec, scenario: Scenario, days: int
) -> list[dict[str, Any]]:
    if scenario.is_baseline:
        return []
    return [
        {
            "event_id": f"{lane.lane_id}__{scenario.scenario_id}",
            "risk_type": scenario.risk_type,
            "supplier_id": lane.supplier_id,
            "item_id": lane.item_id,
            "dst_node_id": lane.destination_id,
            "edge_id": _edge_id(graph, lane),
            "start_day": 0,
            "end_day": days - 1,
            "multiplier": scenario.value,
            "notes": "simulated hypothesis applied to already-planned opening purchase order",
        }
    ]


def v10_masking_audit(v10_root: Path, lane: LaneSpec) -> dict[str, Any]:
    data = v10_root / "data"
    stock_rows = [
        row
        for row in active.read_csv_rows(data / "production_input_stocks_daily.csv")
        if str(row.get("node_id") or "") == lane.destination_id
        and str(row.get("item_id") or "") == lane.item_id
        and 0 <= active.to_int(row.get("day"), -1) < 720
    ]
    day0 = next((row for row in stock_rows if active.to_int(row.get("day"), -1) == 0), None)
    if day0 is None:
        raise CampaignValidationError(f"Missing V10 measurement-start stock for {lane.lane_id}")
    measured_stock = active.to_float(day0.get("stock_before_production"), math.nan)
    consumed = sum(
        max(
            0.0,
            active.to_float(row.get("stock_before_production"))
            - active.to_float(row.get("stock_end_of_day")),
        )
        for row in stock_rows
    )
    shipments = [
        row
        for row in active.read_csv_rows(data / "production_supplier_shipments_daily.csv")
        if str(row.get("dst_node_id") or "") == lane.destination_id
        and str(row.get("item_id") or "") == lane.item_id
        and 0 <= active.to_int(row.get("arrival_day"), -1) < 720
    ]
    dynamic_arrivals = _sum(shipments, "shipped_qty")
    errors: list[str] = []
    for name, value, expected in (
        ("measurement-start stock", measured_stock, lane.v10_measurement_start_qty),
        ("horizon consumption", consumed, lane.v10_horizon_consumption_qty),
        ("dynamic arrivals", dynamic_arrivals, lane.v10_dynamic_arrival_qty),
    ):
        if not math.isclose(value, expected, rel_tol=0.0, abs_tol=1e-3):
            errors.append(f"{name}: expected {expected:g}, found {value:g}")
    daily = consumed / 720.0
    return {
        "lane_id": lane.lane_id,
        "item_id": lane.item_id,
        "measurement_start_stock_qty": measured_stock,
        "horizon_consumption_qty": consumed,
        "simulated_daily_consumption_qty": daily,
        "physical_cover_days_before_dynamic_arrivals": measured_stock / daily if daily > 0 else math.inf,
        "dynamic_arrival_qty": dynamic_arrivals,
        "uom": lane.standard_uom,
        "validation_errors": "|".join(errors),
        "validated": not errors,
        "evidence_class": "measured in dynamic V10 simulation, not observed delivery history",
        "interpretation": "stock can mask the tested opening-order incident; this is not acquired resilience",
    }


def _opening_snapshot_qty(graph: Mapping[str, Any], lane: LaneSpec) -> float:
    values: list[float] = []
    for node in graph.get("nodes") or []:
        if not isinstance(node, Mapping) or str(node.get("id") or "") != lane.destination_id:
            continue
        inventory = node.get("inventory") if isinstance(node.get("inventory"), Mapping) else {}
        for state in inventory.get("states") or []:
            if isinstance(state, Mapping) and str(state.get("item_id") or "") == lane.item_id:
                values.append(max(0.0, active.to_float(state.get("initial"))))
    if len(values) != 1 or values[0] <= 0:
        raise CampaignValidationError(f"Expected one positive snapshot stock for {lane.lane_id}")
    return values[0]


def _write_scale_file(root: Path, lane: LaneSpec, cover_days: float, graph: Mapping[str, Any]) -> tuple[Path, float, float]:
    target = lane.v10_daily_consumption * cover_days
    snapshot = _opening_snapshot_qty(graph, lane)
    scale = target / snapshot
    path = root / "inputs" / f"measurement_start_scale_{lane.lane_id}_{cover_days:g}d.csv"
    active.write_csv(path, [{"node_id": lane.destination_id, "item_id": lane.item_id, "scale": scale}])
    return path, target, scale


def _risk_tokens(value: Any) -> set[str]:
    return {part.strip() for part in str(value or "").replace(",", "|").split("|") if part.strip()}


def _lineage_proof(case_dir: Path, lane: LaneSpec, scenario: Scenario) -> dict[str, Any]:
    events = active.read_csv_rows(case_dir / "data" / "production_lot_events.csv")
    genealogy = active.read_csv_rows(case_dir / "data" / "production_lot_genealogy.csv")
    expected_event = f"{lane.lane_id}__{scenario.scenario_id}"
    roots = [
        dict(row)
        for row in events
        if str(row.get("event_type") or "") == "opening_purchase_order_receipt"
        and str(row.get("node_id") or "") == lane.destination_id
        and str(row.get("item_id") or "") == lane.item_id
        and str(row.get("supplier_id") or "") == lane.supplier_id
        and (scenario.is_baseline or expected_event in _risk_tokens(row.get("risk_event_ids")))
    ]
    root_ids = {str(row.get("lot_id") or "") for row in roots} - {""}
    children: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in genealogy:
        parent = str(row.get("parent_lot_id") or "")
        child = str(row.get("child_lot_id") or "")
        if parent and child:
            children[parent].append(dict(row))
    depths = {lot_id: 0 for lot_id in root_ids}
    queue = deque(sorted(root_ids))
    links: list[dict[str, Any]] = []
    while queue:
        parent = queue.popleft()
        for link in children.get(parent, []):
            links.append(link)
            child = str(link.get("child_lot_id") or "")
            if child and child not in depths:
                depths[child] = depths[parent] + 1
                queue.append(child)
    descendants = set(depths) - root_ids
    descendant_events = [dict(row) for row in events if str(row.get("lot_id") or "") in descendants]
    finished = [row for row in descendant_events if str(row.get("item_id") or "") == TARGET_ITEM]
    client = [
        row
        for row in descendant_events
        if str(row.get("event_type") or "") == "demand_service"
        and str(row.get("node_id") or "") == CLIENT_NODE
    ]
    proof_dir = case_dir / "proofs" / lane.lane_id
    active.write_csv(proof_dir / "opening_order_receipt_lots.csv", roots)
    active.write_csv(proof_dir / "descendant_genealogy.csv", links)
    active.write_csv(proof_dir / "descendant_lot_events.csv", descendant_events)
    normalized = sorted(
        (
            str(row.get("item_id") or ""),
            str(row.get("node_id") or ""),
            active.to_int(row.get("day"), -1),
            round(active.to_float(row.get("qty")), 9),
            str(row.get("event_type") or ""),
        )
        for row in descendant_events
    )
    return {
        "receipt_lot_count": len(root_ids),
        "receipt_lot_qty": _sum(roots, "qty"),
        "receipt_lots_preserve_supplier_and_source_row": bool(roots)
        and all(str(row.get("supplier_id") or "") and str(row.get("source_row") or "") for row in roots),
        "descendant_lot_count": len(descendants),
        "descendant_genealogy_link_count": len(links),
        "finished_descendant_event_count": len(finished),
        "client_descendant_event_count": len(client),
        "descendant_signature_sha256": active.json_sha256(normalized),
        "lot_exposure_semantics": "full descendant lots are an exposure upper bound; causal effect requires a paired difference",
        "source_row_semantics": "technical source-line identifier, not an industrial order or lot number",
        "lineage_status": (
            "reaches_client" if client else "reaches_finished_product" if finished else "reaches_intermediate" if descendants else "receipt_not_consumed_within_horizon"
        ),
    }


def _service_stats(case_dir: Path) -> dict[str, Any]:
    metrics = service.compute_service_metrics(
        active.read_csv_rows(case_dir / "data" / "production_demand_service_daily.csv"),
        client_node_id=CLIENT_NODE,
        products=(TARGET_PRODUCT,),
        days=720,
    )[TARGET_PRODUCT]
    return metrics


def extract_case(
    *,
    case_dir: Path,
    lane: LaneSpec,
    scenario: Scenario,
    seed: int,
    state_id: str,
    evidence_class: str,
    target_stock_qty: float | None,
    stock_scale: float | None,
) -> dict[str, Any]:
    summary = active.read_json(case_dir / "summaries" / "first_simulation_summary.json")
    policy = summary.get("policy") if isinstance(summary.get("policy"), Mapping) else {}
    initialization = policy.get("initialization_policy") if isinstance(policy.get("initialization_policy"), Mapping) else {}
    risk_audit = [
        row
        for row in active.read_csv_rows(case_dir / "data" / "opening_purchase_order_supplier_risk_audit.csv")
        if str(row.get("supplier_id") or "") == lane.supplier_id
        and str(row.get("dst_node_id") or "") == lane.destination_id
        and str(row.get("item_id") or "") == lane.item_id
    ]
    shipments = [
        row
        for row in active.read_csv_rows(case_dir / "data" / "production_supplier_shipments_daily.csv")
        if str(row.get("src_node_id") or "") == lane.supplier_id
        and str(row.get("dst_node_id") or "") == lane.destination_id
        and str(row.get("item_id") or "") == lane.item_id
        and 0 <= active.to_int(row.get("arrival_day"), -1) < 720
    ]
    replayed = [row for row in shipments if str(row.get("transport_cost_basis") or "") == "opening_order_book"]
    dynamic = [row for row in shipments if row not in replayed]
    stocks = [
        row
        for row in active.read_csv_rows(case_dir / "data" / "production_input_stocks_daily.csv")
        if str(row.get("node_id") or "") == lane.destination_id
        and str(row.get("item_id") or "") == lane.item_id
        and 0 <= active.to_int(row.get("day"), -1) < 720
    ]
    day0 = next((row for row in stocks if active.to_int(row.get("day"), -1) == 0), None)
    service_stats = _service_stats(case_dir)
    outputs = [
        row
        for row in active.read_csv_rows(case_dir / "data" / "production_output_products_daily.csv")
        if str(row.get("item_id") or "") == TARGET_ITEM
        and 0 <= active.to_int(row.get("day"), -1) < 720
    ]
    lineage = _lineage_proof(case_dir, lane, scenario)
    normalized_receipts = sorted(
        (
            active.to_int(row.get("source_row"), -1),
            round(active.to_float(row.get("planned_qty_before")), 9),
            round(active.to_float(row.get("pulled_qty_after")), 9),
            round(active.to_float(row.get("physical_shipped_qty_after")), 9),
            round(active.to_float(row.get("usable_qty_after")), 9),
            active.to_int(row.get("physical_delivery_day_after"), -1),
            active.to_int(row.get("usable_day_after"), -1),
        )
        for row in risk_audit
    )
    kpis = summary.get("kpis") if isinstance(summary.get("kpis"), Mapping) else {}
    row: dict[str, Any] = {
        "state_id": state_id,
        "state_evidence_class": evidence_class,
        "lane_id": lane.lane_id,
        "supplier_id": lane.supplier_id,
        "item_id": lane.item_id,
        "destination_id": lane.destination_id,
        "scenario_id": scenario.scenario_id,
        "mechanism": scenario.mechanism,
        "mechanism_value": scenario.value,
        "mechanism_unit": scenario.value_unit,
        "seed": seed,
        "target_stock_qty": target_stock_qty if target_stock_qty is not None else "",
        "measurement_start_stock_scale": stock_scale if stock_scale is not None else "",
        "measurement_start_stock_qty": active.to_float(day0.get("stock_before_production"), math.nan) if day0 else math.nan,
        "component_consumed_qty": sum(max(0.0, active.to_float(item.get("stock_before_production")) - active.to_float(item.get("stock_end_of_day"))) for item in stocks),
        "opening_order_audit_rows": len(risk_audit),
        "opening_order_risk_applied_rows": sum(bool(str(item.get("risk_event_ids") or "")) for item in risk_audit),
        "opening_order_unsupported_risk_rows": sum(bool(str(item.get("unsupported_risk_types") or "")) for item in risk_audit),
        "opening_order_planned_qty": _sum(risk_audit, "planned_qty_before"),
        "opening_order_pulled_qty": _sum(risk_audit, "pulled_qty_after"),
        "opening_order_physical_shipped_qty": _sum(risk_audit, "physical_shipped_qty_after"),
        "opening_order_usable_qty": _sum(risk_audit, "usable_qty_after"),
        "opening_order_weighted_usable_day": (
            sum(active.to_float(item.get("usable_qty_after")) * active.to_float(item.get("usable_day_after")) for item in risk_audit) / _sum(risk_audit, "usable_qty_after")
            if _sum(risk_audit, "usable_qty_after") > 0 else math.nan
        ),
        "opening_order_receipt_signature_sha256": active.json_sha256(normalized_receipts),
        "replayed_shipment_rows": len(replayed),
        "replayed_pulled_qty": _sum(replayed, "pulled_qty"),
        "replayed_shipped_qty": _sum(replayed, "shipped_qty"),
        "dynamic_shipment_rows": len(dynamic),
        "dynamic_pulled_qty": _sum(dynamic, "pulled_qty"),
        "dynamic_shipped_qty": _sum(dynamic, "shipped_qty"),
        "product_on_due_volume_proxy": active.to_float(service_stats.get("on_due_volume_proxy")),
        "product_fill_rate": active.to_float(service_stats.get("fill_rate")),
        "product_backlog_qty_days": active.to_float(service_stats.get("backlog_qty_days")),
        "product_backlog_end_qty": active.to_float(service_stats.get("backlog_end_qty")),
        "product_released_qty": _sum(outputs, "released_qty"),
        "product_produced_qty": _sum(outputs, "produced_qty"),
        "total_cost": active.to_float(kpis.get("total_cost")),
        "resolved_warmup_days": active.to_int(summary.get("warmup_days"), -1),
        "resolved_seed_open_orders_from_snapshot": bool(initialization.get("seed_open_orders_from_january_snapshot")),
        "resolved_lot_trace_enabled": bool(policy.get("lot_trace_enabled") if "lot_trace_enabled" in policy else summary.get("production_tracking", {}).get("lot_trace", {}).get("enabled")),
        **lineage,
    }
    errors: list[str] = []
    if len(risk_audit) != lane.expected_row_count:
        errors.append("native opening-order audit row count mismatch")
    if row["opening_order_pulled_qty"] <= 0 or row["opening_order_physical_shipped_qty"] <= 0:
        errors.append("opening order did not create positive pulled and shipped flow")
    if row["replayed_pulled_qty"] <= 0 or row["replayed_shipped_qty"] <= 0:
        errors.append("replayed shipment flow is zero within horizon")
    if not scenario.is_baseline and row["opening_order_risk_applied_rows"] <= 0:
        errors.append("risk was not applied to opening purchase order")
    if row["opening_order_unsupported_risk_rows"] > 0:
        errors.append("opening-order risk audit contains unsupported risk")
    if row["resolved_warmup_days"] != 0 or not row["resolved_seed_open_orders_from_snapshot"]:
        errors.append("snapshot replay protocol not resolved")
    if not row["resolved_lot_trace_enabled"]:
        errors.append("lot trace not enabled")
    if target_stock_qty is not None and not math.isclose(row["measurement_start_stock_qty"], target_stock_qty, rel_tol=0.0, abs_tol=1e-3):
        errors.append("prospective measurement-start stock target mismatch")
    row["validation_errors"] = "|".join(errors)
    row["valid"] = not errors
    if errors:
        raise CampaignValidationError(f"{state_id}/{lane.lane_id}/{scenario.scenario_id}: {'; '.join(errors)}")
    return row


def attach_pairs(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    baselines = {
        (str(row.get("state_id")), str(row.get("lane_id")), active.to_int(row.get("seed"))): row
        for row in rows
        if str(row.get("scenario_id")) == "baseline_orderbook_replay"
    }
    output: list[dict[str, Any]] = []
    for original in rows:
        row = dict(original)
        baseline = baselines[(str(row["state_id"]), str(row["lane_id"]), active.to_int(row["seed"]))]
        for field in (
            "product_on_due_volume_proxy",
            "product_fill_rate",
            "product_backlog_qty_days",
            "product_backlog_end_qty",
            "product_released_qty",
            "opening_order_usable_qty",
            "opening_order_weighted_usable_day",
            "total_cost",
        ):
            row[f"{field}_delta_vs_paired_baseline"] = active.to_float(row.get(field)) - active.to_float(baseline.get(field))
        receipt_effect = str(row.get("opening_order_receipt_signature_sha256")) != str(baseline.get("opening_order_receipt_signature_sha256"))
        descendant_effect = str(row.get("descendant_signature_sha256")) != str(baseline.get("descendant_signature_sha256"))
        client_effect = (
            abs(active.to_float(row.get("product_on_due_volume_proxy_delta_vs_paired_baseline"))) > 1e-12
            or abs(active.to_float(row.get("product_backlog_qty_days_delta_vs_paired_baseline"))) > 1e-9
            or abs(active.to_float(row.get("product_released_qty_delta_vs_paired_baseline"))) > 1e-9
        )
        row["causal_effect_on_receipt"] = receipt_effect
        row["causal_effect_on_descendants"] = descendant_effect
        row["causal_effect_on_client"] = client_effect
        row["effect_interpretation"] = (
            "paired downstream client effect"
            if client_effect
            else "paired descendant-lot effect without client KPI change"
            if descendant_effect
            else "opening-order receipt changed but was not consumed differently within horizon"
            if receipt_effect
            else "no paired difference"
        )
        output.append(row)
    return output


def _prune(case_dir: Path) -> None:
    for name in ("data", "plots", "maps", "run"):
        path = case_dir / name
        if path.is_dir():
            shutil.rmtree(path)


def _run_engine(
    *,
    engine: Path,
    graph: Path,
    profile_args: Sequence[str],
    case_dir: Path,
    seed: int,
    risk_csv: Path | None,
    scale_csv: Path | None,
) -> dict[str, Any]:
    command = active.build_engine_command(
        engine=engine,
        graph=graph,
        output_dir=case_dir,
        profile_args=profile_args,
        days=720,
        seed=seed,
        risk_csv=risk_csv,
        apply_risk_to_opening_orders=True,
        measurement_start_stock_scale_csv=scale_csv,
    )
    index = command.index("--scenario-id") + 1
    command[index] = "scn:ORDERBOOK_ONLY_LANES"
    case_dir.mkdir(parents=True, exist_ok=True)
    log = case_dir / "campaign_engine.log"
    with log.open("a", encoding="utf-8") as handle:
        handle.write(f"[{utc_now()}] COMMAND {json.dumps(command, ensure_ascii=False)}\n")
        completed = subprocess.run(command, cwd=REPO_ROOT, stdout=handle, stderr=subprocess.STDOUT, text=True, check=False)
    if completed.returncode != 0:
        raise RuntimeError(f"Engine failed; see {log}")
    normalized = active.normalized_engine_command(command)
    return {
        "case_dir": str(case_dir.resolve()),
        "orchestrator_sha256_at_process_start": ORCHESTRATOR_SHA256,
        "active_flow_library_sha256_at_process_start": active.PROCESS_ORCHESTRATOR_SHA256,
        "engine_sha256_at_case": active.sha256_file(engine),
        "source_graph_sha256_at_case": active.sha256_file(graph),
        "engine_profile_args_sha256": active.json_sha256(list(profile_args)),
        "engine_command_normalized_sha256": active.json_sha256(normalized),
        "engine_command_normalized_json": json.dumps(
            normalized, ensure_ascii=False, separators=(",", ":")
        ),
        "risk_csv": str(risk_csv.resolve()) if risk_csv is not None else "",
        "risk_csv_sha256": (
            active.sha256_file(risk_csv) if risk_csv is not None else ""
        ),
        "stock_scale_csv": str(scale_csv.resolve()) if scale_csv is not None else "",
        "stock_scale_csv_sha256": (
            active.sha256_file(scale_csv) if scale_csv is not None else ""
        ),
        "engine_log": str(log.resolve()),
    }


def build_execution_provenance_audit(
    records: Sequence[Mapping[str, Any]],
    manifest: Mapping[str, Any],
    *,
    orchestrator_path: Path,
) -> dict[str, Any]:
    """Verify every physical run against the hashes frozen at launch."""

    def retained_hash_matches(record: Mapping[str, Any], path_field: str, hash_field: str) -> bool:
        raw_path = str(record.get(path_field) or "")
        expected = str(record.get(hash_field) or "")
        if not raw_path:
            return not expected
        path = Path(raw_path)
        return path.is_file() and bool(expected) and active.sha256_file(path) == expected

    unique_case_dirs = {str(record.get("case_dir") or "") for record in records}
    expected_count = active.to_int(
        manifest.get("planned_physical_engine_run_count"), -1
    )
    count_matches = (
        len(records) == expected_count
        and len(unique_case_dirs) == expected_count
        and "" not in unique_case_dirs
    )
    core_matches = all(
        str(record.get("engine_sha256_at_case") or "")
        == str(manifest.get("engine_sha256") or "")
        and str(record.get("source_graph_sha256_at_case") or "")
        == str(manifest.get("source_graph_sha256") or "")
        and str(record.get("engine_profile_args_sha256") or "")
        == str(manifest.get("profile_args_sha256") or "")
        and str(record.get("orchestrator_sha256_at_process_start") or "")
        == str(manifest.get("orchestrator_sha256_at_process_start") or "")
        and str(record.get("active_flow_library_sha256_at_process_start") or "")
        == str(manifest.get("active_flow_library_sha256_at_process_start") or "")
        and bool(str(record.get("engine_command_normalized_sha256") or ""))
        and bool(str(record.get("engine_command_normalized_json") or ""))
        for record in records
    )
    retained_inputs_match = all(
        retained_hash_matches(record, "risk_csv", "risk_csv_sha256")
        and retained_hash_matches(
            record, "stock_scale_csv", "stock_scale_csv_sha256"
        )
        for record in records
    )
    current_orchestrator_sha = active.sha256_file(orchestrator_path)
    orchestrator_matches = current_orchestrator_sha == str(
        manifest.get("orchestrator_sha256_at_process_start") or ""
    )
    allowed = bool(
        records
        and count_matches
        and core_matches
        and retained_inputs_match
        and orchestrator_matches
    )
    return {
        "schema_version": "supplier-orderbook-only-execution-provenance.v1",
        "physical_case_count": len(records),
        "expected_physical_case_count": expected_count,
        "case_count_matches_plan": count_matches,
        "engine_graph_profile_command_and_library_match": core_matches,
        "retained_risk_and_scale_inputs_match": retained_inputs_match,
        "orchestrator_sha256_at_process_start": manifest.get(
            "orchestrator_sha256_at_process_start"
        ),
        "orchestrator_sha256_at_audit": current_orchestrator_sha,
        "orchestrator_matches_launch": orchestrator_matches,
        "reproducibility_wording_allowed": allowed,
        "interpretation": (
            "Every physical engine run is tied to the frozen engine, source graph, "
            "profile arguments, normalized command and retained risk/stock inputs."
        ),
    }


def build_business_summary(
    rows: Sequence[Mapping[str, Any]],
    *,
    mode: str,
    source_audits: Sequence[Mapping[str, Any]],
    masking_audits: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Build a compact, business-readable summary without causal overclaim."""

    source_by_lane = {str(row.get("lane_id") or ""): row for row in source_audits}
    masking_by_lane = {str(row.get("lane_id") or ""): row for row in masking_audits}
    groups: dict[tuple[str, str], list[Mapping[str, Any]]] = defaultdict(list)
    for row in rows:
        groups[(str(row.get("state_id") or ""), str(row.get("lane_id") or ""))].append(row)
    summaries: list[dict[str, Any]] = []
    for (state_id, lane_id), group in sorted(groups.items()):
        baseline = next(
            row
            for row in group
            if str(row.get("scenario_id") or "") == "baseline_orderbook_replay"
        )
        stresses = [
            row
            for row in group
            if str(row.get("scenario_id") or "") != "baseline_orderbook_replay"
        ]
        source = source_by_lane[lane_id]
        masking = masking_by_lane[lane_id]
        receipt_effect_count = sum(bool(row.get("causal_effect_on_receipt")) for row in stresses)
        descendant_effect_count = sum(bool(row.get("causal_effect_on_descendants")) for row in stresses)
        client_effect_count = sum(bool(row.get("causal_effect_on_client")) for row in stresses)
        summaries.append(
            {
                "state_id": state_id,
                "state_evidence_class": baseline.get("state_evidence_class"),
                "lane_id": lane_id,
                "supplier_id": baseline.get("supplier_id"),
                "item_id": baseline.get("item_id"),
                "destination_id": baseline.get("destination_id"),
                "planned_order_line_count": source.get(
                    "observed_snapshot_order_row_count"
                ),
                "planned_order_qty_standard": source.get(
                    "observed_snapshot_order_qty_standard"
                ),
                "standard_uom": source.get("standard_uom"),
                "planned_physical_day_min": source.get("physical_delivery_day_min"),
                "planned_physical_day_max": source.get("physical_delivery_day_max"),
                "planned_usable_day_min": source.get("usable_day_min"),
                "planned_usable_day_max": source.get("usable_day_max"),
                "v10_measured_stock_qty": masking.get(
                    "measurement_start_stock_qty"
                ),
                "v10_simulated_daily_consumption_qty": masking.get(
                    "simulated_daily_consumption_qty"
                ),
                "v10_physical_cover_days_before_dynamic_arrivals": masking.get(
                    "physical_cover_days_before_dynamic_arrivals"
                ),
                "v10_dynamic_arrival_qty": masking.get("dynamic_arrival_qty"),
                "tested_stress_count": len(stresses),
                "stress_with_receipt_effect_count": receipt_effect_count,
                "stress_with_descendant_lot_effect_count": descendant_effect_count,
                "stress_with_client_effect_count": client_effect_count,
                "baseline_product_on_due_volume_proxy": baseline.get(
                    "product_on_due_volume_proxy"
                ),
                "minimum_stressed_product_on_due_volume_proxy": min(
                    (
                        active.to_float(row.get("product_on_due_volume_proxy"))
                        for row in stresses
                    ),
                    default=active.to_float(
                        baseline.get("product_on_due_volume_proxy")
                    ),
                ),
                "conclusion": (
                    "paired client effect detected in at least one tested stress"
                    if client_effect_count
                    else "paired descendant-lot effect detected without client KPI change"
                    if descendant_effect_count
                    else "planned receipts change, but no descendant lot or client KPI differs within the tested horizon"
                    if receipt_effect_count
                    else "no paired difference under the tested configurations"
                ),
                "claim_not_allowed": (
                    "absence of downstream effect is stock/state masking, not acquired resilience"
                ),
            }
        )
    return {
        "schema_version": "supplier-orderbook-only-business-summary.v1",
        "mode": mode,
        "evidence_labels": {
            "observed": (
                "ERP snapshot rows and planned dates at 2025-01-01; not actual delivery history or OTIF"
            ),
            "simulated": "engine replay, risk shifts, lot genealogy and client indicators",
            "hypothesis": (
                "incident settings and, in prospective mode only, reduced component-stock cover"
            ),
        },
        "lane_state_summaries": summaries,
        "source_row_semantics": (
            "technical source-line identifier, not an industrial order or lot number"
        ),
        "causal_rule": (
            "A receipt is exposed when its dates or quantity change. A downstream causal "
            "effect is reported only when paired descendant lots or client indicators differ."
        ),
    }


def write_business_summary_markdown(path: Path, summary: Mapping[str, Any]) -> None:
    mode = str(summary.get("mode") or "")
    title = (
        "Snapshot 2025 rejoué"
        if mode == "snapshot"
        else "Hypothèses prospectives de couverture réduite"
    )
    lines = [
        "# Bilan métier — voies fournisseur présentes uniquement dans le carnet",
        "",
        f"## {title}",
        "",
        (
            "Les dates sont celles planifiées dans le carnet au 1er janvier 2025. "
            "Elles ne constituent ni un historique de livraisons réelles ni un calcul d’OTIF."
        ),
        "",
    ]
    for row in summary.get("lane_state_summaries") or []:
        qty = active.to_float(row.get("planned_order_qty_standard"))
        cover = active.to_float(
            row.get("v10_physical_cover_days_before_dynamic_arrivals")
        )
        lines.extend(
            [
                f"### {str(row.get('supplier_id') or '')} → {str(row.get('destination_id') or '')} / {str(row.get('item_id') or '').replace('item:', '')}",
                "",
                (
                    f"Le carnet contient **{active.to_int(row.get('planned_order_line_count'))} ligne(s)**, "
                    f"soit **{qty:,.3f} {str(row.get('standard_uom') or '')}**, avec livraison physique "
                    f"planifiée entre J{active.to_int(row.get('planned_physical_day_min'))} et "
                    f"J{active.to_int(row.get('planned_physical_day_max'))}, puis disponibilité prévue "
                    f"entre J{active.to_int(row.get('planned_usable_day_min'))} et "
                    f"J{active.to_int(row.get('planned_usable_day_max'))}."
                ),
                "",
                (
                    f"Dans la référence dynamique V10, le stock mesuré au J0 couvre environ "
                    f"**{cover:,.1f} jours** au rythme simulé avant les arrivées futures. "
                    f"Sur {active.to_int(row.get('tested_stress_count'))} incidents testés, "
                    f"{active.to_int(row.get('stress_with_receipt_effect_count'))} modifient la réception, "
                    f"{active.to_int(row.get('stress_with_descendant_lot_effect_count'))} modifient un lot descendant "
                    f"et {active.to_int(row.get('stress_with_client_effect_count'))} modifient l’indicateur client."
                ),
                "",
                (
                    "**Lecture métier :** l’absence d’effet aval signifie que les couches de stock et l’état "
                    "testé absorbent l’incident dans l’horizon. Elle ne démontre pas que le fournisseur est peu critique."
                ),
                "",
            ]
        )
    lines.extend(
        [
            "## Traçabilité",
            "",
            (
                "`source_row` identifie une ligne technique de la source ERP ; ce n’est ni un numéro "
                "de commande industriel ni un numéro de lot. Un effet causal aval n’est retenu que si "
                "la comparaison appariée change les descendants ou les indicateurs client."
            ),
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", default=str(DEFAULT_GRAPH))
    parser.add_argument("--engine", default=str(DEFAULT_ENGINE))
    parser.add_argument("--profile", default=str(DEFAULT_PROFILE))
    parser.add_argument("--v10", default=str(DEFAULT_V10))
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--mode", choices=("snapshot", "prospective-severe"), default="snapshot")
    parser.add_argument("--cover-days", default="90,30")
    parser.add_argument("--seeds", default=str(DEFAULT_SEED))
    parser.add_argument("--scenario-ids", default="")
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--retention", choices=("summary", "full"), default="summary")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    source_path = Path(args.input).resolve()
    engine = Path(args.engine).resolve()
    profile = Path(args.profile).resolve()
    v10 = Path(args.v10).resolve()
    root = Path(args.output_dir).resolve()
    root.mkdir(parents=True, exist_ok=True)
    graph = active.read_json(source_path)
    profile_args = active.engine_profile_args(profile)
    seeds = parse_seeds(args.seeds)
    source_audits = [source_order_audit(graph, lane) for lane in LANES]
    masking_audits = [v10_masking_audit(v10, lane) for lane in LANES]
    if not all(row["validated"] for row in masking_audits):
        raise CampaignValidationError("V10 masking evidence differs from the frozen lane specification")
    active.write_csv(root / "observed_snapshot_order_book_audit.csv", source_audits)
    active.write_csv(root / "v10_measured_masking_audit.csv", masking_audits)

    requested = [value.strip() for value in str(args.scenario_ids).split(",") if value.strip()]
    if requested:
        unknown = sorted(set(requested) - set(SCENARIO_BY_ID))
        if unknown:
            raise ValueError(f"Unknown scenario IDs: {unknown}")
        scenario_ids = tuple(dict.fromkeys(("baseline_orderbook_replay", *requested)))
    elif args.mode == "snapshot":
        scenario_ids = tuple(scenario.scenario_id for scenario in SCENARIOS)
    else:
        scenario_ids = ("baseline_orderbook_replay", *SEVERE_SCENARIO_IDS)
    scenarios = [SCENARIO_BY_ID[value] for value in scenario_ids]
    covers = tuple(float(value.strip()) for value in str(args.cover_days).split(",") if value.strip())
    states: list[dict[str, Any]] = []
    if args.mode == "snapshot":
        states.append({"state_id": "observed_snapshot_2025", "evidence_class": "observed_2025_snapshot_replayed", "lane": None, "cover_days": None, "scale_csv": None, "target": None, "scale": None})
    else:
        for lane in LANES:
            for cover in covers:
                scale_path, target, scale = _write_scale_file(root, lane, cover, graph)
                states.append({"state_id": f"prospective_{lane.item_code}_{cover:g}d", "evidence_class": "simulated_reduced_component_cover_hypothesis_not_observed", "lane": lane, "cover_days": cover, "scale_csv": scale_path, "target": target, "scale": scale})
    planned_physical_engine_run_count = sum(
        (
            1
            + len([scenario for scenario in scenarios if not scenario.is_baseline])
            * len((state["lane"],) if state["lane"] is not None else LANES)
        )
        * len(seeds)
        for state in states
    )
    active.write_csv(root / "scenario_design.csv", [{"scenario_id": s.scenario_id, "mechanism": s.mechanism, "risk_type": s.risk_type, "value": s.value, "unit": s.value_unit, "label": s.label, "is_baseline": s.is_baseline} for s in scenarios])
    active.write_csv(root / "state_design.csv", [{key: value if not isinstance(value, LaneSpec) else value.lane_id for key, value in state.items()} for state in states])

    manifest: dict[str, Any] = {
        "schema_version": "supplier-orderbook-only-lanes.v1",
        "status": "running",
        "created_at_utc": utc_now(),
        "orchestrator": str(Path(__file__).resolve()),
        "orchestrator_sha256_at_process_start": ORCHESTRATOR_SHA256,
        "active_flow_library_sha256_at_process_start": active.PROCESS_ORCHESTRATOR_SHA256,
        "engine": str(engine),
        "engine_sha256": active.sha256_file(engine),
        "source_graph": str(source_path),
        "source_graph_sha256": active.sha256_file(source_path),
        "profile": str(profile),
        "profile_sha256": active.sha256_file(profile),
        "profile_args_sha256": active.json_sha256(list(profile_args)),
        "v10": str(v10),
        "mode": args.mode,
        "seeds": list(seeds),
        "scenario_ids": list(scenario_ids),
        "planned_physical_engine_run_count": planned_physical_engine_run_count,
        "scientific_scope": {
            "snapshot": "planned order-book rows at one ERP snapshot; not actual delivery history or OTIF",
            "prospective": "component-stock sensitivity only; not an observed or globally lean supply state",
            "flow_classes": "opening-order replay and dynamic flows exported separately",
            "source_row": "technical source-line identifier, not an industrial order or lot number",
            "effect_rule": "lot exposure is genealogical; causal effect requires paired date, quantity, descendant or client-KPI difference",
        },
    }
    active.write_json(root / "campaign_manifest.json", manifest)
    rows: list[dict[str, Any]] = []
    run_provenance: list[dict[str, Any]] = []

    for state in states:
        state_lanes = (state["lane"],) if state["lane"] is not None else LANES
        for seed in seeds:
            baseline = SCENARIO_BY_ID["baseline_orderbook_replay"]
            baseline_dir = root / "cases" / state["state_id"] / "baseline_shared" / f"seed_{seed}"
            baseline_provenance = _run_engine(engine=engine, graph=source_path, profile_args=profile_args, case_dir=baseline_dir, seed=seed, risk_csv=None, scale_csv=state["scale_csv"])
            run_provenance.append(baseline_provenance)
            for lane in state_lanes:
                baseline_row = extract_case(case_dir=baseline_dir, lane=lane, scenario=baseline, seed=seed, state_id=state["state_id"], evidence_class=state["evidence_class"], target_stock_qty=state["target"], stock_scale=state["scale"])
                baseline_row.update(baseline_provenance)
                rows.append(baseline_row)
            if args.retention == "summary":
                _prune(baseline_dir)

            jobs = [(lane, scenario) for lane in state_lanes for scenario in scenarios if not scenario.is_baseline]
            with ThreadPoolExecutor(max_workers=max(1, min(args.workers, 4))) as pool:
                futures = {}
                for lane, scenario in jobs:
                    case_dir = root / "cases" / state["state_id"] / f"{lane.lane_id}__{scenario.scenario_id}" / f"seed_{seed}"
                    risk_path = root / "inputs" / "risk_events" / f"{state['state_id']}__{lane.lane_id}__{scenario.scenario_id}.csv"
                    active.write_csv(risk_path, risk_rows(graph, lane, scenario, 720), RISK_FIELDS)
                    futures[pool.submit(_run_engine, engine=engine, graph=source_path, profile_args=profile_args, case_dir=case_dir, seed=seed, risk_csv=risk_path, scale_csv=state["scale_csv"])] = (lane, scenario, case_dir)
                for future in as_completed(futures):
                    lane, scenario, case_dir = futures[future]
                    case_provenance = future.result()
                    run_provenance.append(case_provenance)
                    case_row = extract_case(case_dir=case_dir, lane=lane, scenario=scenario, seed=seed, state_id=state["state_id"], evidence_class=state["evidence_class"], target_stock_qty=state["target"], stock_scale=state["scale"])
                    case_row.update(case_provenance)
                    rows.append(case_row)
                    if args.retention == "summary":
                        _prune(case_dir)
                    active.write_csv(root / "screening_metrics.partial.csv", attach_pairs(rows))
                    print(f"[ORDERBOOK_ONLY] {state['state_id']} {lane.lane_id} {scenario.scenario_id}", flush=True)

    paired = attach_pairs(rows)
    active.write_csv(root / "screening_metrics.csv", paired)
    partial = root / "screening_metrics.partial.csv"
    partial.unlink(missing_ok=True)
    effect_rows = [row for row in paired if str(row.get("scenario_id")) != "baseline_orderbook_replay" and (bool(row.get("causal_effect_on_descendants")) or bool(row.get("causal_effect_on_client")))]
    active.write_csv(root / "execution_provenance_cases.csv", run_provenance)
    provenance_audit = build_execution_provenance_audit(
        run_provenance,
        manifest,
        orchestrator_path=Path(__file__).resolve(),
    )
    active.write_json(root / "execution_provenance_audit.json", provenance_audit)
    business_summary = build_business_summary(
        paired,
        mode=args.mode,
        source_audits=source_audits,
        masking_audits=masking_audits,
    )
    active.write_json(root / "business_summary.json", business_summary)
    write_business_summary_markdown(
        root / "RESUME_METIER.md", business_summary
    )
    manifest.update({
        "status": (
            "complete"
            if provenance_audit["reproducibility_wording_allowed"]
            else "invalid_provenance"
        ),
        "completed_at_utc": utc_now(),
        "physical_engine_run_count": len(run_provenance),
        "metric_row_count": len(paired),
        "downstream_effect_row_count": len(effect_rows),
        "confirmation_required": bool(effect_rows) and len(seeds) == 1,
        "execution_provenance_audit": provenance_audit,
        "outputs": {"metrics": "screening_metrics.csv", "source_audit": "observed_snapshot_order_book_audit.csv", "masking_audit": "v10_measured_masking_audit.csv", "provenance_cases": "execution_provenance_cases.csv", "provenance_audit": "execution_provenance_audit.json", "business_summary": "business_summary.json", "business_summary_markdown": "RESUME_METIER.md"},
    })
    active.write_json(root / "campaign_manifest.json", manifest)
    if not provenance_audit["reproducibility_wording_allowed"]:
        raise CampaignValidationError(
            "Execution provenance audit failed; see execution_provenance_audit.json"
        )
    print(f"[OK] orderbook-only lane campaign: {root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
