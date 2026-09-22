"""Physical material ledger reconciliation, separate from BOM forecasts.

The stock snapshot is an independent closing observation. A missing ledger is
never replaced by a BOM calculation or a shipment scheduled in the future.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Any


def apply_physical_material_balances(
    rows: list[dict[str, Any]], events: list[dict[str, Any]],
    stock_rows: list[dict[str, Any]], *, horizon_days: int, source_available: bool,
) -> None:
    def number(value: Any) -> float:
        return float(value or 0)

    ledger = defaultdict(list)
    snapshots = defaultdict(dict)
    for event in events:
        day = int(number(event.get("day")))
        if 0 <= day < horizon_days:
            ledger[(event.get("node_id"), event.get("item_id"))].append(event)
    for stock in stock_rows:
        day = int(number(stock.get("day")))
        if 0 <= day < horizon_days:
            snapshots[(stock.get("node_id"), stock.get("item_id"))][day] = number(stock.get("stock_end_of_day"))

    receipt_types = {"lane_receipt", "external_procurement_receipt", "estimated_source_receipt", "estimated_capacity_receipt"}
    consume_types = {"production_consume", "production_consume_reference_transition"}
    outflow_types = {"shipment_reserve", "demand_service", "writeoff", "stock_writeoff"}
    adjustment_types = {"stock_reconciliation", "production_output"}
    known_types = receipt_types | consume_types | outflow_types | adjustment_types | {"opening_stock", "lane_ship", "opening_production_order"}

    for row in rows:
        scope = row.get("scope")
        if scope != "material":
            # These historical rows describe service (PF) or production and
            # dispatch (PFI), not a material stock conservation equation.
            row["balance_status"] = "not_applicable"
            row["physical_source_available"] = False
            row["quantity_basis"] = "customer_service" if scope == "pf" else "production_and_dispatch"
            row["source_notes"] = ["Ligne de service client, hors bilan matière." if scope == "pf" else "Production et expéditions du PFI ; hors bilan des intrants."]
            for bucket in row.get("yearly", {}).values():
                bucket.update(balance_status="not_applicable", physical_source_available=False, source_notes=row["source_notes"])
            continue
        pair = (row.get("node_id"), row.get("item_id"))
        pair_events = ledger[pair]
        stock = snapshots[pair]
        opening_events = [event for event in pair_events if event.get("event_type") == "opening_stock"]
        initial = sum(number(event.get("qty")) for event in opening_events)
        unknown = sorted({str(event.get("event_type")) for event in pair_events if event.get("event_type") not in known_types})
        expected_unit = str(row.get("unit") or "").upper()
        mismatched_units = sorted({str(event.get("uom")) for event in pair_events if event.get("uom") and str(event["uom"]).upper() != expected_unit})
        available = bool(source_available and pair_events and not unknown and not mismatched_units)
        notes = ["Consommations et réceptions : événements physiques datés du registre des lots ; clôtures : stocks journaliers."]
        if unknown:
            notes.append("Types d'événements non rapprochés : " + ", ".join(unknown))
        if mismatched_units:
            notes.append("Unités du registre incompatibles avec la ligne : " + ", ".join(mismatched_units))
        if not source_available or not pair_events:
            notes.append("Registre physique absent pour cette référence ; calcul BOM conservé séparément.")
        row["theoretical_consumed_qty"] = row.get("consumed_qty")
        row["quantity_basis"] = "physical_ledger"
        yearly = row.get("yearly", {})
        for year, bucket in yearly.items():
            first = (int(year) - 1) * 365
            last = min(horizon_days, first + 365) - 1
            bucket["theoretical_consumed_qty"] = bucket.get("consumed_qty")
            period_available = available and last in stock and (first == 0 or first - 1 in stock)
            bucket.update(physical_source_available=period_available, source_notes=notes, balance_tolerance_qty=1e-5)
            if not period_available:
                for field in ("delivered_qty", "consumed_qty", "stock_outflow_qty", "stock_adjustment_qty", "balance_expected_final_qty", "balance_gap_qty"):
                    bucket[field] = None
                bucket["balance_status"] = "unavailable"
                continue
            relevant = [event for event in pair_events if first <= int(number(event.get("day"))) <= last]
            def total(types: set[str]) -> float:
                return sum(number(event.get("qty")) for event in relevant if event.get("event_type") in types)
            bucket.update(
                initial_qty=initial if first == 0 else stock[first - 1],
                final_stock_qty=stock[last], delivered_qty=total(receipt_types),
                consumed_qty=total(consume_types), stock_outflow_qty=total(outflow_types),
                stock_adjustment_qty=total(adjustment_types),
            )
            # lane_ship confirms the departure of a previously reserved lot;
            # it does not remove the same quantity from on-hand a second time.
            expected = bucket["initial_qty"] + bucket["delivered_qty"] + bucket["stock_adjustment_qty"] - bucket["consumed_qty"] - bucket["stock_outflow_qty"]
            gap = expected - bucket["final_stock_qty"]
            bucket.update(balance_expected_final_qty=expected, balance_gap_qty=gap,
                          balance_status="reconciled" if abs(gap) <= 1e-5 else "mismatch")
        complete = bool(yearly) and all(bucket["physical_source_available"] for bucket in yearly.values())
        row.update(physical_source_available=complete, source_notes=notes, balance_tolerance_qty=1e-5 * len(yearly))
        for field in ("delivered_qty", "consumed_qty", "stock_outflow_qty", "stock_adjustment_qty", "balance_gap_qty"):
            row[field] = sum(bucket[field] for bucket in yearly.values()) if complete else None
        if complete:
            row["initial_qty"] = initial
            row["final_stock_qty"] = stock[horizon_days - 1]
            row["balance_expected_final_qty"] = row["final_stock_qty"] + row["balance_gap_qty"]
            row["gap_vs_need_qty"] = row["consumed_qty"] - number(row.get("planned_qty"))
            row["balance_status"] = "reconciled" if all(bucket["balance_status"] == "reconciled" for bucket in yearly.values()) else "mismatch"
            row["diagnostic"] = "Bilan physique rapproché" if row["balance_status"] == "reconciled" else "Écart de bilan physique à vérifier"
        else:
            row.update(balance_status="unavailable", balance_expected_final_qty=None, gap_vs_need_qty=None,
                       diagnostic="Bilan physique non vérifiable avec les sources disponibles")
