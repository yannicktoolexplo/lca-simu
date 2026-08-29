"""CSV/JSON adapters for the truck consolidation contract."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any, Iterable

from .models import (
    ConsolidationResult,
    ItemLogisticsProfile,
    ShipmentLine,
)


def _float_or_none(value: Any) -> float | None:
    text = str(value or "").strip()
    return float(text) if text else None


def _int_or_none(value: Any) -> int | None:
    text = str(value or "").strip()
    return int(float(text)) if text else None


def load_profiles_csv(path: str | Path) -> list[ItemLogisticsProfile]:
    profile_path = Path(path)
    if not profile_path.exists():
        raise FileNotFoundError(profile_path)
    with profile_path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    return [
        ItemLogisticsProfile(
            item_id=str(row.get("item_id") or ""),
            uom=str(row.get("uom") or ""),
            source_reference=str(row.get("source_reference") or ""),
            kg_per_unit=_float_or_none(row.get("kg_per_unit")),
            pallets_per_unit=_float_or_none(row.get("pallets_per_unit")),
            volume_m3_per_unit=_float_or_none(row.get("volume_m3_per_unit")),
            compatibility_group=str(row.get("compatibility_group") or "default"),
            notes=str(row.get("notes") or ""),
        )
        for row in rows
    ]


def load_lane_shipments(
    lot_events_csv: str | Path,
    graph_json: str | Path,
) -> list[ShipmentLine]:
    """Load lane_ship lot events and resolve their destination from the graph edge."""

    graph_path = Path(graph_json)
    graph = json.loads(graph_path.read_text(encoding="utf-8"))
    edges = {
        str(edge.get("id") or ""): edge
        for edge in (graph.get("edges") or [])
        if isinstance(edge, dict)
    }
    events_path = Path(lot_events_csv)
    with events_path.open("r", encoding="utf-8-sig", newline="") as handle:
        event_rows = list(csv.DictReader(handle))

    lines: list[ShipmentLine] = []
    for row in event_rows:
        if str(row.get("event_type") or "") != "lane_ship":
            continue
        edge_id = str(row.get("source_id") or "")
        edge = edges.get(edge_id)
        if not edge:
            raise ValueError(
                f"Cannot resolve destination for lot event {row.get('event_id')}: "
                f"unknown edge {edge_id}"
            )
        event_origin = str(row.get("node_id") or "").strip()
        edge_origin = str(edge.get("from") or "").strip()
        if event_origin and edge_origin and event_origin != edge_origin:
            raise ValueError(
                f"Lot event {row.get('event_id')} declares origin {event_origin}, "
                f"but edge {edge_id} starts at {edge_origin}."
            )
        departure_day = _int_or_none(row.get("departure_day"))
        if departure_day is None:
            departure_day = int(float(str(row.get("day") or 0)))
        lines.append(
            ShipmentLine(
                line_id=str(row.get("event_id") or ""),
                departure_day=departure_day,
                arrival_day=_int_or_none(row.get("arrival_day")),
                origin_node_id=event_origin or edge_origin,
                destination_node_id=str(edge.get("to") or ""),
                item_id=str(row.get("item_id") or ""),
                quantity=float(str(row.get("qty") or 0.0)),
                uom=str(row.get("uom") or ""),
                mode=str(edge.get("mode") or "truck"),
                lot_id=str(row.get("lot_id") or ""),
                shipment_id=str(row.get("shipment_id") or ""),
                explicit_weight_kg=_float_or_none(row.get("weight_kg")),
                explicit_pallets=_float_or_none(row.get("pallets")),
                explicit_volume_m3=_float_or_none(row.get("volume_m3")),
                physical_data_source=str(row.get("physical_data_source") or ""),
                metadata={"edge_id": edge_id},
            )
        )
    return lines


def _write_csv(path: Path, rows: Iterable[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_consolidation_result(
    output_dir: str | Path,
    result: ConsolidationResult,
) -> dict[str, str]:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    load_rows: list[dict[str, Any]] = []
    allocation_rows: list[dict[str, Any]] = []
    for load in result.loads:
        load_rows.append(
            {
                "load_id": load.load_id,
                "origin_node_id": load.origin_node_id,
                "destination_node_id": load.destination_node_id,
                "mode": load.mode,
                "compatibility_group": load.compatibility_group,
                "window_start_day": load.window_start_day,
                "window_end_day": load.window_end_day,
                "consolidation_day": load.consolidation_day,
                "weight_kg": load.weight_kg,
                "pallets": load.pallets,
                "volume_m3": load.volume_m3,
                "weight_utilization": load.weight_utilization,
                "pallet_utilization": load.pallet_utilization,
                "volume_utilization": load.volume_utilization,
                "allocation_count": len(load.allocations),
            }
        )
        for allocation in load.allocations:
            allocation_rows.append({"load_id": load.load_id, **allocation.to_dict()})
    fallback_rows = []
    for group in result.fallback_groups:
        fallback_rows.append(
            {
                "group_id": group.group_id,
                "origin_node_id": group.origin_node_id,
                "destination_node_id": group.destination_node_id,
                "mode": group.mode,
                "compatibility_group": group.compatibility_group,
                "window_start_day": group.window_start_day,
                "window_end_day": group.window_end_day,
                "consolidation_day": group.consolidation_day,
                "line_ids": "|".join(group.line_ids),
                "lot_ids": "|".join(group.lot_ids),
                "shipment_ids": "|".join(group.shipment_ids),
                "item_ids": "|".join(group.item_ids),
                "quantities_by_uom_json": json.dumps(
                    group.quantities_by_uom, ensure_ascii=False, sort_keys=True
                ),
                "quantities_by_item_uom_json": json.dumps(
                    group.quantities_by_item_uom,
                    ensure_ascii=False,
                    sort_keys=True,
                ),
                "known_weight_kg": group.known_weight_kg,
                "weight_bases": "|".join(group.weight_bases),
                "known_pallets": group.known_pallets,
                "known_volume_m3": group.known_volume_m3,
                "weight_known_line_count": group.weight_known_line_count,
                "pallet_known_line_count": group.pallet_known_line_count,
                "volume_known_line_count": group.volume_known_line_count,
                "missing_dimensions": "|".join(group.missing_dimensions),
                "known_capacity_lower_bound_trucks": group.known_capacity_lower_bound_trucks,
                "truck_count": "",
                "basis": group.basis,
                "reason": group.reason,
            }
        )

    load_fields = [
        "load_id",
        "origin_node_id",
        "destination_node_id",
        "mode",
        "compatibility_group",
        "window_start_day",
        "window_end_day",
        "consolidation_day",
        "weight_kg",
        "pallets",
        "volume_m3",
        "weight_utilization",
        "pallet_utilization",
        "volume_utilization",
        "allocation_count",
    ]
    allocation_fields = [
        "load_id",
        "line_id",
        "item_id",
        "quantity",
        "uom",
        "lot_id",
        "shipment_id",
        "weight_kg",
        "pallets",
        "volume_m3",
    ]
    fallback_fields = list(fallback_rows[0].keys()) if fallback_rows else [
        "group_id",
        "origin_node_id",
        "destination_node_id",
        "mode",
        "compatibility_group",
        "window_start_day",
        "window_end_day",
        "consolidation_day",
        "line_ids",
        "lot_ids",
        "shipment_ids",
        "item_ids",
        "quantities_by_uom_json",
        "quantities_by_item_uom_json",
        "known_weight_kg",
        "weight_bases",
        "known_pallets",
        "known_volume_m3",
        "weight_known_line_count",
        "pallet_known_line_count",
        "volume_known_line_count",
        "missing_dimensions",
        "known_capacity_lower_bound_trucks",
        "truck_count",
        "basis",
        "reason",
    ]
    loads_path = output / "truck_loads.csv"
    allocations_path = output / "truck_load_allocations.csv"
    fallback_path = output / "weekly_fallback_groups.csv"
    audit_path = output / "consolidation_audit.json"
    _write_csv(loads_path, load_rows, load_fields)
    _write_csv(allocations_path, allocation_rows, allocation_fields)
    _write_csv(fallback_path, fallback_rows, fallback_fields)
    audit_path.write_text(
        json.dumps(result.audit, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return {
        "loads": str(loads_path),
        "allocations": str(allocations_path),
        "fallback_groups": str(fallback_path),
        "audit": str(audit_path),
    }
