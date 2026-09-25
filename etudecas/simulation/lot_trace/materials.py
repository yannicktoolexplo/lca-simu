"""Supplier identities and receipt-level incident scope, without changing physics.

An optional material_traceability.json supplies documented manufacturer lots and
handling units. Existing BATCH/SHIP identifiers are never promoted to measured
manufacturer lots. Exposure is a conservative genealogy scope, not a causal
estimate of defective output, lost service or delay.
"""
from __future__ import annotations
from collections import defaultdict, deque
import math
import re
from typing import Any


VERSION = "material-traceability/1.0"
RECEIPT_TYPES = {"lane_receipt", "external_procurement_receipt",
                 "estimated_source_receipt", "estimated_capacity_receipt", "opening_stock"}


def _number(value, *, uom="", positive=False):
    if isinstance(value, bool):
        raise ValueError("Boolean is not a physical quantity")
    result = float(value)
    if not math.isfinite(result) or result < 0 or (positive and result == 0):
        raise ValueError("Physical quantity must be finite and nonnegative")
    if uom.upper() in {"UN", "UNIT", "UNITS", "ZUN"} and not result.is_integer():
        raise ValueError("Physical UN quantities must be integers")
    return result


def _ids(value):
    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip()]
    return [v for v in re.split(r"[;,|\s]+", str(value or "")) if v]


def _required(row, key):
    value = row.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Missing {key}")
    return value.strip()


def _unique(rows, name):
    result = {}
    for row in rows:
        key = _required(row, "id")
        if key in result:
            raise ValueError(f"Duplicate {name}: {key}")
        result[key] = dict(row)
    return result


def build_material_traceability(events, genealogy, graph=None, metadata=None):
    """Build the auditable context shared by the map and offline checks.

Metadata allocations refer to receipt *event* IDs and sum to at most its
quantity. Unmapped remainder stays unknown. Handling units describe the inbound
receipt only, not the current location/contents of a pallet after consumption.
"""
    if metadata is not None and not isinstance(metadata, dict):
        raise ValueError("Material metadata must be a JSON object")
    metadata = metadata or {}
    if metadata and metadata.get("version") != VERSION:
        raise ValueError("Unsupported material traceability version")
    unknown = set(metadata) - {"version", "origins", "allocations", "handling_units", "incidents"}
    if unknown:
        raise ValueError(f"Unknown material metadata keys: {sorted(unknown)}")
    for key in ("origins", "allocations", "handling_units", "incidents"):
        if not isinstance(metadata.get(key, []), list):
            raise ValueError(f"{key} must be a list")
    events = list(events)
    genealogy = list(genealogy)
    by_event = {}
    for row in events:
        identity = str(row.get("event_id") or "")
        if identity and identity in by_event:
            raise ValueError(f"Duplicate event: {identity}")
        if identity:
            by_event[identity] = row
    nodes = {r["id"]: r for r in (graph or {}).get("nodes", [])}
    incoming = defaultdict(list)
    outgoing = defaultdict(list)
    for link in genealogy:
        parent, child = str(link.get("parent_lot_id") or ""), str(link.get("child_lot_id") or "")
        if link.get("link_type") not in {"production", "transport"} or not parent or not child:
            continue
        if _number(link.get("parent_qty", 0)) > 0:
            outgoing[parent].append(link)
            incoming[child].append(link)
    origins = _unique(metadata.get("origins", []), "origin")
    origin_keys = set()
    for origin in origins.values():
        for key in ("manufacturer_id", "item_id", "batch_number", "source_reference"):
            _required(origin, key)
        if origin.get("status") not in {"observed", "simulated"}:
            raise ValueError("Origin status must be observed or simulated")
        signature = tuple(origin[k] for k in ("manufacturer_id", "item_id", "batch_number", "status"))
        if signature in origin_keys:
            raise ValueError("Same manufacturer batch must use one origin identity")
        origin_keys.add(signature)
    receipts = {}
    by_lot = defaultdict(list)
    for event in events:
        if event.get("event_type") not in RECEIPT_TYPES or not event.get("lot_id"):
            continue
        event_id = _required(event, "event_id")
        lot = str(event["lot_id"])
        if by_lot[lot]:
            raise ValueError("Each receipt needs a distinct stock occurrence for quantity allocation")
        uom = str(event.get("uom") or "")
        qty = _number(event.get("qty", 0), uom=uom)
        suppliers = sorted({str(link.get("parent_node_id") or "") for link in incoming[lot]
                            if link.get("link_type") == "transport" and link.get("parent_node_id")})
        node_id = str(event.get("node_id") or "")
        if not suppliers and nodes.get(node_id, {}).get("type") == "supplier_dc":
            suppliers = [node_id]
        receipts[event_id] = dict(
            id=event_id, lot_id=lot, item_id=str(event.get("item_id") or ""),
            node_id=node_id, supplier_ids=suppliers, day=int(float(event.get("day") or 0)),
            event_type=event["event_type"], quantity=qty, uom=uom,
            shipment_id=str(event.get("shipment_id") or ""),
            simulated_batch_id=str(event.get("business_batch_id") or ""),
            quality_status="unknown", origins=[], possible_origin_ids=[], unknown_origin_qty=qty,
            handling_units=[], risk_event_ids=_ids(event.get("risk_event_ids")),
            source_status="opening_stock" if event["event_type"] == "opening_stock" else "simulated_receipt",
        )
        by_lot[lot].append(event_id)
    allocations_seen = set()
    for allocation in metadata.get("allocations", []):
        receipt_id, origin_id = _required(allocation, "receipt_id"), _required(allocation, "origin_id")
        if receipt_id not in receipts or origin_id not in origins:
            raise ValueError("Allocation references unknown receipt/origin")
        if (receipt_id, origin_id) in allocations_seen:
            raise ValueError("Duplicate receipt/origin allocation")
        allocations_seen.add((receipt_id, origin_id))
        receipt, origin = receipts[receipt_id], origins[origin_id]
        if receipt["item_id"] != origin["item_id"]:
            raise ValueError("Manufacturer lot and receipt must have the same item")
        if allocation.get("uom") != receipt["uom"]:
            raise ValueError("Allocation unit differs from receipt unit")
        qty = _number(allocation.get("quantity"), uom=receipt["uom"], positive=True)
        receipt["unknown_origin_qty"] -= qty
        if receipt["unknown_origin_qty"] < -1e-7:
            raise ValueError("Origin allocations exceed received quantity")
        receipt["unknown_origin_qty"] = max(0, receipt["unknown_origin_qty"])
        receipt["origins"].append(dict(origin_id=origin_id, quantity=qty, basis="documented_allocation"))
    # A split of a fully identified single-origin stock keeps that identity.
    # For a mixed parent, genealogy alone cannot tell which origin was picked.
    # Keep possible origins without inventing a proportional physical allocation.
    resolved = set()

    def inherit(lot, visiting):
        if lot in resolved or lot not in by_lot:
            return
        if lot in visiting:
            raise ValueError("Cyclic transport genealogy")
        receipt = receipts[by_lot[lot][0]]
        links = [link for link in incoming[lot] if link.get("link_type") == "transport"]
        portions = defaultdict(float)
        possible = set()
        all_parents_identified = bool(links)
        for link in links:
            parent = str(link["parent_lot_id"])
            inherit(parent, visiting | {lot})
            if parent not in by_lot:
                all_parents_identified = False
                continue
            source = receipts[by_lot[parent][0]]
            if (source["item_id"], source["uom"]) != (receipt["item_id"], receipt["uom"]):
                raise ValueError("Transport changes material identity or unit")
            possible.update(p["origin_id"] for p in source["origins"])
            possible.update(source["possible_origin_ids"])
            all_parents_identified = all_parents_identified and source["unknown_origin_qty"] == 0
            if len(source["origins"]) == 1 and source["unknown_origin_qty"] == 0:
                portions[source["origins"][0]["origin_id"]] += _number(link["parent_qty"], uom=receipt["uom"])
        if not receipt["origins"] and links:
            total = sum(_number(link["parent_qty"]) for link in links)
            if abs(total - receipt["quantity"]) <= 1e-7:
                receipt["origins"] = [dict(origin_id=key, quantity=qty, basis="transport_genealogy")
                                       for key, qty in sorted(portions.items())]
                receipt["unknown_origin_qty"] = max(0, receipt["quantity"] - sum(portions.values()))
        if all_parents_identified and any(p["origin_id"] not in possible for p in receipt["origins"]):
            raise ValueError("Documented receipt origin contradicts identified transport parents")
        receipt["possible_origin_ids"] = sorted(possible - {p["origin_id"] for p in receipt["origins"]}) if receipt["unknown_origin_qty"] else []
        resolved.add(lot)

    for lot in by_lot:
        inherit(lot, set())
    handling = _unique(metadata.get("handling_units", []), "handling unit")
    allocated_handling = defaultdict(float)
    for unit in handling.values():
        _required(unit, "kind")
        _required(unit, "source_reference")
        if unit.get("status") not in {"observed", "simulated"}:
            raise ValueError("Handling unit status must be observed or simulated")
        if not isinstance(unit.get("contents"), list) or not unit["contents"]:
            raise ValueError("Handling unit needs receipt contents")
        for part in unit["contents"]:
            receipt_id = _required(part, "receipt_id")
            if receipt_id not in receipts:
                raise ValueError("Handling unit references unknown receipt")
            receipt = receipts[receipt_id]
            if part.get("uom") != receipt["uom"]:
                raise ValueError("Handling unit content has wrong unit")
            qty = _number(part.get("quantity"), uom=receipt["uom"], positive=True)
            allocated_handling[receipt_id] += qty
            if allocated_handling[receipt_id] > receipt["quantity"] + 1e-7:
                raise ValueError("Handling unit contents exceed received quantity")
            receipt["handling_units"].append(dict(id=unit["id"], kind=unit["kind"], quantity=qty,
                                                   status=unit["status"]))
    # Receipt consumption is checked against the full ledger, not against just
    # the selected production. Transport and production links are distinct uses.
    checks = []
    for lot, receipt_ids in by_lot.items():
        received = sum(receipts[r]["quantity"] for r in receipt_ids)
        used = sum(_number(link["parent_qty"], uom=receipts[receipt_ids[0]]["uom"]) for link in outgoing[lot])
        # Physical mass CSVs round each allocation to six decimals. Bound the
        # accumulated rounding error; UN is exact and never gets this allowance.
        integral = all(receipts[r]["uom"].upper() in {"UN", "UNIT", "UNITS", "ZUN"} for r in receipt_ids)
        tolerance = 1e-9 if integral else (len(outgoing[lot]) + len(receipt_ids)) * 0.5e-6 + 1e-9
        checks.append(dict(lot_id=lot, received=received, allocated_out=used,
                           ok=used <= received + tolerance))
    if any(not check["ok"] for check in checks):
        bad = [c["lot_id"] for c in checks if not c["ok"]]
        raise ValueError(f"Genealogy consumes more than received: {bad[:5]}")
    context = dict(version=VERSION, origins=origins, receipts=receipts,
                   receipt_ids_by_lot=dict(by_lot), handling_units=handling,
                   incidents=[], coverage=dict(receipts=len(receipts),
                   receipts_with_origin_allocation=sum(bool(r["origins"]) for r in receipts.values()),
                   receipts_with_observed_origin=sum(any(origins[p["origin_id"]]["status"] == "observed" for p in r["origins"]) for r in receipts.values()),
                   receipts_with_simulated_origin=sum(any(origins[p["origin_id"]]["status"] == "simulated" for p in r["origins"]) for r in receipts.values()),
                   quantity_balance_checks=len(checks)),
                   exposure_policy="Conservative descendant scope; no inferred defect quantity, delay or service loss.")
    # Keep the engine's native transaction links; never infer an incident from
    # a date, supplier name, truck proposal or an aggregate stock level.
    native = defaultdict(lambda: {"lots": set(), "events": set(), "shipments": set(), "days": []})
    for event in events:
        for incident_id in _ids(event.get("risk_event_ids")):
            row = native[incident_id]
            row["events"].add(str(event.get("event_id") or ""))
            decision_day = event.get("risk_decision_day")
            if decision_day is None or decision_day == "":
                decision_day = event.get("day") or 0
            row["days"].append(int(float(decision_day)))
            # A partial shipment cannot expose every use of its supplier parent.
            if event.get("shipment_id"):
                row["shipments"].add(str(event["shipment_id"]))
            elif event.get("lot_id"):
                row["lots"].add(str(event["lot_id"]))
    for incident_id, row in sorted(native.items()):
        seed_lots = row["lots"] | {r["lot_id"] for r in receipts.values()
                                   if r["shipment_id"] in row["shipments"]}
        context["incidents"].append(_incident_scope(
            dict(id=incident_id, kind="engine_risk", status="engine_recorded",
                 day=min(row["days"]), label=incident_id, evidence="native_transaction",
                 source_event_ids=sorted(row["events"]), shipment_ids=sorted(row["shipments"])),
            seed_lots, events, outgoing))
    for incident in _unique(metadata.get("incidents", []), "incident").values():
        if incident["id"] in native:
            raise ValueError("Scenario incident duplicates a native risk identity")
        context["incidents"].append(build_incident_preview(context, events, genealogy, incident))
    return context


def _incident_scope(incident, seed_lots, events, outgoing):
    reachable = set(seed_lots)
    queue = deque(sorted(reachable))
    while queue:
        for link in outgoing.get(queue.popleft(), []):
            child = str(link["child_lot_id"])
            if child not in reachable:
                reachable.add(child)
                queue.append(child)
    outputs = sorted({str(e["lot_id"]) for e in events
                      if e.get("event_type") == "production_output" and e.get("lot_id") in reachable})
    service = sorted({str(e.get("event_id")) for e in events
                      if e.get("event_type") == "demand_service" and e.get("lot_id") in reachable})
    return {**incident, "seed_lot_ids": sorted(seed_lots), "potential_lot_ids": sorted(reachable),
            "potential_production_lot_ids": outputs, "potential_service_event_ids": service,
            "impact_status": "exposure_only_no_resimulation",
            "interpretation": "Candidate scope for investigation, not proven defective output or service degradation."}


def build_incident_preview(context, events, genealogy, incident):
    """Resolve an explicitly scoped future incident without mutating any ledger.

For mixed receipts/containers, descendants are a conservative candidate set.
We deliberately do not prorate a quality defect into a false output quantity.
The detection day is informational: a recall can include earlier production.
"""
    incident = dict(incident)
    for key in ("id", "label", "source_reference", "target_type", "target_id"):
        _required(incident, key)
    if incident.get("status") != "scenario_preview":
        raise ValueError("Imported incidents must be explicitly scenario_preview")
    if incident.get("kind") not in {"quality_recall", "quarantine", "transport_delay"}:
        raise ValueError("Unsupported incident kind")
    day = _number(incident.get("day"))
    if not day.is_integer():
        raise ValueError("Incident day must be an integer")
    target_type, target = incident["target_type"], incident["target_id"]
    receipts = context["receipts"]
    selected = []
    if target_type == "receipt":
        selected = [r for r in receipts.values() if r["id"] == target]
    elif target_type == "supplier_lot":
        if target not in context["origins"]:
            raise ValueError("Incident references unknown supplier lot")
        selected = [r for r in receipts.values() if any(p["origin_id"] == target for p in r["origins"])
                    or target in r["possible_origin_ids"]]
    elif target_type == "shipment":
        selected = [r for r in receipts.values() if r["shipment_id"] == target]
    elif target_type == "handling_unit":
        if target not in context["handling_units"]:
            raise ValueError("Incident references unknown handling unit")
        ids = {p["receipt_id"] for p in context["handling_units"][target]["contents"]}
        selected = [r for r in receipts.values() if r["id"] in ids]
    else:
        raise ValueError("Incident target must be a receipt, supplier_lot, shipment or handling_unit")
    if not selected:
        raise ValueError("Incident target does not resolve to any receipt")
    if incident["kind"] == "transport_delay" and target_type != "shipment":
        raise ValueError("A transport delay must target a shipment")
    outgoing = defaultdict(list)
    for link in genealogy:
        if link.get("link_type") in {"transport", "production"} and _number(link.get("parent_qty", 0)) > 0:
            outgoing[str(link["parent_lot_id"])].append(link)
    return _incident_scope({**incident, "evidence": "explicit_scenario_scope",
                            "receipt_ids": sorted(r["id"] for r in selected)},
                           {r["lot_id"] for r in selected}, events, outgoing)
