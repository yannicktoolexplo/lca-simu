"""MRP charts with one physical unit per axis and explicit plan/execution dates."""
from __future__ import annotations
from collections import defaultdict
from typing import Any

from etudecas.visualization.maps.chart_payloads import build_line_chart_figure
from etudecas.visualization.maps.supplier_operations_payload import planned_order_receipt_day


def build_unit_scoped_mrp_assets(raw: dict[str, Any], node_id: str, *, trace_rows: list,
                                order_rows: list, stock_rows: list, arrival_rows: list,
                                shipment_rows: list, horizon_days: int) -> dict[str, Any]:
    units = {}
    item_units = defaultdict(set)
    for node in raw.get("nodes", []):
        for state in (node.get("inventory") or {}).get("states", []):
            unit = str(state.get("uom") or "").upper()
            unit = {"UNIT": "UN", "UNITS": "UN", "UNITE": "UN"}.get(unit, unit)
            if unit:
                units[(str(node.get("id")), str(state.get("item_id")))] = unit
                item_units[str(state.get("item_id"))].add(unit)
    def unit_for(row: dict) -> str:
        item = str(row.get("item_id") or "")
        unit = units.get((node_id, item))
        if not unit:
            candidates = item_units[item]
            unit = next(iter(candidates)) if len(candidates) == 1 else None
        # Unknown or inconsistent units must not be summed across articles.
        return unit or f"unité non documentée — {item}"
    all_rows = trace_rows + order_rows + stock_rows + arrival_rows + shipment_rows
    groups = sorted({unit_for(row) for row in all_rows})
    assets = {key: [] for key in ("incoming", "outgoing", "fourth", "supplier_order_send")}
    def series(rows: list, field: str, date: str = "day", *, weekly: bool = False, realized: bool = False) -> list:
        total = defaultdict(float)
        for row in rows:
            value = planned_order_receipt_day(row) if date == "planned_arrival_day" else row.get(date)
            if value in (None, ""):
                if date == "order_date_imt":
                    value = row.get("day")
                else:
                    continue
            day = int(float(value))
            if realized and not (0 <= day < horizon_days):
                continue
            if realized and date == "day" and str(row.get("departure_executed", "")).lower() in {"false", "0"}:
                continue
            if realized and date == "arrival_day" and str(row.get("arrival_executed", "")).lower() in {"false", "0"}:
                continue
            total[(day // 7) * 7 if weekly else day] += max(0.0, float(row.get(field) or 0))
        return sorted(total.items())
    def figure(values: dict, title: str, unit: str, weekly: bool = False) -> dict | None:
        chart = build_line_chart_figure(values, title=f"{node_id} — {title} ({unit})",
                                       y_label=unit + (" / semaine" if weekly else ""),
                                       note="Une seule unité par graphique. Les quantités prévues ne constituent pas une preuve de mouvement physique.")
        if chart is not None:
            chart.update(quantity_unit=unit, aggregation_basis="same_unit_only")
        return chart
    for unit in groups:
        traces, orders, stocks, arrivals, shipments = ([row for row in rows if unit_for(row) == unit] for rows in (trace_rows, order_rows, stock_rows, arrival_rows, shipment_rows))
        incoming = figure({label: series(traces, field) for label, field in (
            ("Besoin brut", "bb_qty"), ("Besoin propagé brut", "bb_demand_signal_raw_qty"),
            ("Besoin MRP lissé", "bb_demand_signal_qty"), ("Besoin net", "bn_qty"),
            ("Stock projeté", "stock_proj_qty"), ("Réceptions prévues", "recv_prev_future_qty"))}, "Trace MRP", unit)
        planned = figure({"Ordres MRP": series(orders, "release_qty", "order_date_imt", weekly=True),
                          "Réceptions prévues": series(orders, "planned_receipt_qty", "planned_arrival_day", weekly=True),
                          "Réceptions physiques": series(arrivals, "arrived_qty", weekly=True, realized=True)}, "Flux entrants", unit, True)
        levels = {label: series(traces, field) for label, field in (
            ("Stock projeté MRP", "stock_proj_qty"), ("Position inventaire MRP", "inventory_position_qty"),
            ("Besoin net MRP", "bn_qty"), ("Cible de sécurité", "safety_floor_qty"),
            ("Cible sécurité souple", "soft_safety_target_qty"), ("Cible MRP affichée", "target_stock_display_qty"))}
        levels["Stock physique en clôture"] = series(stocks, "stock_end_of_day", realized=True)
        outgoing = {"kind": "dual_panel_multi", "title": f"Pilotage MRP — {unit}", "top": planned,
                    "bottom": figure(levels, "Stocks et cibles", unit), "quantity_unit": unit}
        order_series = {}
        for item in sorted({str(row.get("item_id")) for row in orders}):
            scoped = [row for row in orders if str(row.get("item_id")) == item]
            order_series[f"{item} — ordre"] = series(scoped, "release_qty", "order_date_imt", weekly=True)
            order_series[f"{item} — réception prévue"] = series(scoped, "planned_receipt_qty", "planned_arrival_day", weekly=True)
        fourth = figure(order_series, "Carnet par article", unit, True)
        supplier_orders = [row for row in orders if row.get("src_node_id") == node_id]
        supplier = {"kind": "dual_panel_multi", "title": f"Pilotage et exécution fournisseur — {unit}", "quantity_unit": unit,
                    "top": figure({"Commandes MRP reçues": series(supplier_orders, "release_qty", "order_date_imt", weekly=True),
                                   "Expéditions prévues": series(supplier_orders, "release_qty", "release_day", weekly=True)}, "Plan fournisseur", unit, True),
                    "bottom": figure({"Départs exécutés": series(shipments, "shipped_qty", weekly=True, realized=True),
                                      "Réceptions exécutées aval": series(shipments, "shipped_qty", "arrival_day", weekly=True, realized=True)}, "Mouvements fournisseur dans l'horizon", unit, True)}
        for key, chart in (("incoming", incoming), ("outgoing", outgoing), ("fourth", fourth), ("supplier_order_send", supplier)):
            if chart is not None:
                assets[key].append({"label": unit, "asset": {"figure": chart}})
    return {key: ({"bundle": bundle} if len(bundle) > 1 else bundle[0]["asset"] if bundle else None) for key, bundle in assets.items()}
