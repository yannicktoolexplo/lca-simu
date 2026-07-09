from __future__ import annotations

from collections import defaultdict
import html
import json
import math
import statistics
from typing import Any, Iterable

from etudecas.visualization.maps.map_payload_builder import is_simulation_hidden_item
from etudecas.visualization.maps.map_render import (
    fmt_days,
    fmt_pct,
    fmt_qty,
    html_tooltip_attrs,
    html_tooltip_class,
    metric_label_value,
    render_data_table,
)


def to_float(x: Any) -> float | None:
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def percentile(values: list[float], q: float) -> float:
    if not values:
        return 0.0
    vals = sorted(values)
    if len(vals) == 1:
        return vals[0]
    pos = (len(vals) - 1) * q
    lo = int(math.floor(pos))
    hi = int(math.ceil(pos))
    if lo == hi:
        return vals[lo]
    frac = pos - lo
    return vals[lo] * (1 - frac) + vals[hi] * frac


def compact_item_label(item_id: str) -> str:
    return str(item_id or "")


def is_display_order_row(row: dict[str, str]) -> bool:
    order_type = str(row.get("order_type") or "").strip()
    source_mode = str(row.get("source_mode") or "").strip()
    return not order_type.startswith("external_procurement") and not source_mode.startswith("external_procurement")


def display_order_type(order_type: Any) -> str:
    raw = str(order_type or "").strip()
    labels = {
        "lane_release": "ordre_flux",
        "opening_purchase_order": "ordre_achat_ouvert",
        "opening_production_order": "ordre_production_ouvert",
    }
    return labels.get(raw, raw or "n/a")


def compact_order_status(value: Any) -> str:
    raw = str(value or "").strip()
    labels = {
        "planned_and_released": "planifie",
        "opening_firm_order": "ouvert",
        "released_before_or_at_j0": "rel<=J0",
        "released": "lance",
        "firm_receipt": "recu ferme",
        "received": "recu",
        "n/a": "n/a",
    }
    return labels.get(raw, raw or "n/a")


def fmt_order_day(value: Any) -> str:
    numeric = to_float(value)
    if numeric is None or math.isnan(numeric):
        return "n/a"
    day = int(round(numeric))
    return f"J{day:+d}".replace("+0", "0").replace("+", "")


def fmt_order_day_range(min_value: Any, max_value: Any) -> str:
    min_day = fmt_order_day(min_value)
    max_day = fmt_order_day(max_value)
    if min_day == max_day:
        return min_day
    return f"{min_day}..{max_day}"


def order_week_start(day: int) -> int:
    return (day // 7) * 7


def order_placed_day(row: dict[str, str]) -> float | None:
    value = to_float(row.get("order_date_imt"))
    if value is None or math.isnan(value):
        value = to_float(row.get("day"))
    if value is None or math.isnan(value):
        return None
    return float(value)


def is_opening_order_row(row: dict[str, str]) -> bool:
    return str(row.get("order_type") or "").startswith("opening_")


def reference_transport_lead_days(row: dict[str, str]) -> float | None:
    value = to_float(row.get("lead_reference_days"))
    if value is None or math.isnan(value) or value <= 0:
        value = to_float(row.get("lead_cover_days"))
    if value is None or math.isnan(value) or value <= 0:
        return None
    return float(value)


def source_planned_material_lead_days(row: dict[str, str]) -> float | None:
    value = to_float(row.get("lead_reference_days"))
    if value is not None and not math.isnan(value) and value > 0:
        return float(value)
    if is_opening_order_row(row):
        value = to_float(row.get("lead_days"))
        if value is not None and not math.isnan(value) and value >= 0:
            return float(value)
    return None


def planned_order_receipt_day(row: dict[str, str]) -> float | None:
    order_day = order_placed_day(row)
    planned_lead_days = planned_procurement_lead_days(row)
    if (
        order_day is not None
        and planned_lead_days is not None
        and not math.isnan(order_day)
        and not math.isnan(planned_lead_days)
        and planned_lead_days >= 0
    ):
        return float(order_day + planned_lead_days)

    release_day = to_float(row.get("release_day"))
    transport_lead_days = to_float(row.get("lead_reference_days"))
    if transport_lead_days is None or math.isnan(transport_lead_days) or transport_lead_days <= 0:
        transport_lead_days = to_float(row.get("lead_cover_days"))
    if (
        release_day is not None
        and transport_lead_days is not None
        and not math.isnan(release_day)
        and not math.isnan(transport_lead_days)
        and transport_lead_days > 0
    ):
        return float(release_day + transport_lead_days)
    arrival_day = to_float(row.get("arrival_day"))
    if arrival_day is not None and not math.isnan(arrival_day):
        return float(arrival_day)
    order_day = order_placed_day(row)
    if order_day is not None and transport_lead_days is not None:
        return float(order_day + transport_lead_days)
    return None


def effective_order_receipt_day(row: dict[str, str]) -> float | None:
    value = to_float(row.get("actual_receipt_day"))
    if value is None or math.isnan(value):
        value = to_float(row.get("arrival_day"))
    if value is None or math.isnan(value):
        return None
    return float(value)


def planned_procurement_lead_days(row: dict[str, str]) -> float | None:
    return source_planned_material_lead_days(row)


def planned_order_to_receipt_days(row: dict[str, str]) -> float | None:
    order_day = order_placed_day(row)
    receipt_day = planned_order_receipt_day(row)
    if order_day is None or receipt_day is None:
        return None
    return max(0.0, float(receipt_day - order_day))


def effective_procurement_lead_days(row: dict[str, str]) -> float | None:
    order_day = order_placed_day(row)
    receipt_day = effective_order_receipt_day(row)
    if (
        order_day is not None
        and receipt_day is not None
        and not math.isnan(order_day)
        and not math.isnan(receipt_day)
    ):
        return max(0.0, float(receipt_day - order_day))

    release_day = to_float(row.get("release_day"))
    if (
        release_day is not None
        and receipt_day is not None
        and not math.isnan(release_day)
        and not math.isnan(receipt_day)
    ):
        return max(0.0, float(receipt_day - release_day))

    value = to_float(row.get("lead_days"))
    if value is not None and not math.isnan(value) and value >= 0:
        return float(value)
    return None


def resolved_order_day(row: dict[str, str], day_field: str = "day") -> int:
    if day_field == "planned_arrival_day":
        planned_day = planned_order_receipt_day(row)
        return int(round(planned_day)) if planned_day is not None else 0
    if day_field == "actual_receipt_day":
        effective_day = effective_order_receipt_day(row)
        return int(round(effective_day)) if effective_day is not None else 0
    return int(to_float(row.get(day_field)) or 0)


def consolidate_order_rows_weekly(rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    groups: dict[tuple[Any, ...], dict[str, Any]] = {}
    for row in rows:
        order_day = int(round(order_placed_day(row) or 0))
        release_day = int(to_float(row.get("release_day")) or 0)
        lead_reference_days = planned_procurement_lead_days(row)
        planned_arrival = planned_order_receipt_day(row)
        planned_arrival_day = int(round(planned_arrival)) if planned_arrival is not None else 0
        effective_arrival = effective_order_receipt_day(row)
        effective_arrival_day = int(round(effective_arrival)) if effective_arrival is not None else planned_arrival_day
        item_id = str(row.get("item_id") or "")
        key = (
            order_week_start(order_day),
            str(row.get("src_node_id") or ""),
            str(row.get("dst_node_id") or ""),
            item_id,
            str(row.get("order_type") or ""),
        )
        group = groups.get(key)
        if group is None:
            group = {
                "week_start": key[0],
                "src_node_id": key[1],
                "dst_node_id": key[2],
                "item_id": item_id,
                "order_type": key[4],
                "line_count": 0,
                "release_qty": 0.0,
                "receipt_qty": 0.0,
                "order_min": order_day,
                "order_max": order_day,
                "release_min": release_day,
                "release_max": release_day,
                "planned_arrival_min": planned_arrival_day,
                "planned_arrival_max": planned_arrival_day,
                "effective_arrival_min": effective_arrival_day,
                "effective_arrival_max": effective_arrival_day,
                "lead_reference_sum": 0.0,
                "lead_reference_count": 0,
                "statuses": defaultdict(int),
                "exceptions": set(),
            }
            groups[key] = group
        group["line_count"] += 1
        group["release_qty"] += max(0.0, to_float(row.get("release_qty")) or 0.0)
        group["receipt_qty"] += max(0.0, to_float(row.get("planned_receipt_qty")) or 0.0)
        group["order_min"] = min(group["order_min"], order_day)
        group["order_max"] = max(group["order_max"], order_day)
        group["release_min"] = min(group["release_min"], release_day)
        group["release_max"] = max(group["release_max"], release_day)
        group["planned_arrival_min"] = min(group["planned_arrival_min"], planned_arrival_day)
        group["planned_arrival_max"] = max(group["planned_arrival_max"], planned_arrival_day)
        group["effective_arrival_min"] = min(group["effective_arrival_min"], effective_arrival_day)
        group["effective_arrival_max"] = max(group["effective_arrival_max"], effective_arrival_day)
        if lead_reference_days is not None and not math.isnan(lead_reference_days):
            group["lead_reference_sum"] += float(lead_reference_days)
            group["lead_reference_count"] += 1
        status_key = str(row.get("order_status_end_of_run") or "n/a")
        group["statuses"][status_key] += 1
        for flag in [
            str(row.get("planning_status") or ""),
            str(row.get("release_status") or ""),
            str(row.get("receipt_status") or ""),
            str(row.get("order_status_end_of_run") or ""),
        ]:
            if flag and flag not in {"planned_and_released", "released", "firm_receipt", "received"}:
                group["exceptions"].add(flag)
    return sorted(
        groups.values(),
        key=lambda group: (
            int(group["week_start"]),
            str(group["item_id"]),
            str(group["src_node_id"]),
            str(group["dst_node_id"]),
        ),
        reverse=True,
    )


def render_order_ledger_html(
    node_id: str,
    node_orders: list[dict[str, str]],
    item_labels: dict[str, str],
    empty_reason: str | None = None,
) -> str:
    node_orders = [row for row in node_orders if is_display_order_row(row)]
    if not node_orders:
        reason_html = (
            f"<div class=\"orderLedgerStatus\">{html.escape(empty_reason)}</div>"
            if empty_reason else ""
        )
        return (
            "<div class=\"factoryHtmlPanelContent orderLedgerPanelContent\">"
            f"{reason_html}"
            "<div class=\"panelEmptyState\">Aucun ordre MRP journalise pour ce noeud.</div>"
            "</div>"
        )

    sorted_orders = sorted(
        node_orders,
        key=lambda r: (
            int(to_float(r.get("order_date_imt")) or to_float(r.get("day")) or 0),
            int(to_float(r.get("release_day")) or 0),
            int(to_float(r.get("arrival_day")) or 0),
            str(r.get("item_id") or ""),
            str(r.get("edge_id") or ""),
        ),
        reverse=True,
    )
    status_counts: dict[str, int] = defaultdict(int)
    for row in sorted_orders:
        status_parts = [
            f"plan={str(row.get('planning_status') or 'n/a')}",
            f"release={str(row.get('release_status') or 'n/a')}",
            f"receipt={str(row.get('receipt_status') or 'n/a')}",
            f"run={str(row.get('order_status_end_of_run') or 'n/a')}",
        ]
        status_counts[" | ".join(status_parts)] += 1

    edge_window_size = 500
    if len(sorted_orders) > edge_window_size * 2:
        display_orders = sorted_orders[:edge_window_size] + sorted_orders[-edge_window_size:]
        display_note = f"{edge_window_size} plus recents + {edge_window_size} plus anciens"
        separator_after = edge_window_size
    else:
        display_orders = sorted_orders
        display_note = "tous les ordres"
        separator_after = None

    recent_rows: list[str] = []
    for row_idx, row in enumerate(display_orders):
        if separator_after is not None and row_idx == separator_after:
            recent_rows.append(
                '<tr class="orderLedgerSliceSeparator">'
                '<td colspan="13">500 premiers ordres chronologiques affiches ci-dessous</td>'
                '</tr>'
            )
        item_id = str(row.get("item_id") or "")
        item_label = item_labels.get(item_id, compact_item_label(item_id))
        mode_label = display_order_type(row.get("order_type"))
        order_day_value = order_placed_day(row)
        planned_arrival_day = planned_order_receipt_day(row)
        actual_arrival_day_value = effective_order_receipt_day(row)
        planned_lead_days_value = planned_procurement_lead_days(row)
        effective_lead_days_value = effective_procurement_lead_days(row)
        exceptions = [
            str(row.get(field) or "").strip()
            for field in ["exception_reason", "exception_type", "exception_code"]
            if str(row.get(field) or "").strip()
        ]
        status_text = " | ".join(
            part
            for part in [
                f"plan={str(row.get('planning_status') or 'n/a')}",
                f"release={str(row.get('release_status') or 'n/a')}",
                f"receipt={str(row.get('receipt_status') or 'n/a')}",
                f"run={str(row.get('order_status_end_of_run') or 'n/a')}",
            ]
            if part
        )
        status_short = " / ".join(
            [
                compact_order_status(row.get("planning_status")),
                compact_order_status(row.get("release_status")),
                compact_order_status(row.get("receipt_status")),
                compact_order_status(row.get("order_status_end_of_run")),
            ]
        )
        release_qty = to_float(row.get("release_qty"))
        receipt_qty = to_float(row.get("receipt_qty"))
        if receipt_qty is None or math.isnan(receipt_qty):
            receipt_qty = to_float(row.get("planned_receipt_qty"))
        src_node_id = str(row.get("src_node_id") or "n/a")
        dst_node_id = str(row.get("dst_node_id") or "n/a")
        edge_id = str(row.get("edge_id") or "n/a")
        flux_text = f"{src_node_id} -> {dst_node_id}"
        exceptions_text = ", ".join(exceptions) if exceptions else "none"
        row_cells = [
            (fmt_order_day(order_day_value), ""),
            (item_label, f"Item complet: {item_label}"),
            (mode_label, mode_label),
            (flux_text, f"{flux_text} | edge={edge_id}"),
            (fmt_order_day(row.get("release_day")), ""),
            (f"{fmt_qty(planned_lead_days_value, 1)} j", "Delai previsionnel matiere source: champ FIA 'Delai previsionnel de livraison en jours' quand disponible; sinon delai derive du carnet d'ouverture."),
            (fmt_order_day(planned_arrival_day), ""),
            (fmt_order_day(actual_arrival_day_value), ""),
            (f"{fmt_qty(effective_lead_days_value, 1)} j", "Delai effectif matiere metier: arrivee effective - ordre passe fournisseur."),
            (fmt_qty(release_qty, 1), ""),
            (fmt_qty(receipt_qty, 1), ""),
            (status_short, status_text or "n/a"),
            (exceptions_text, exceptions_text),
        ]
        numeric_columns = {5, 8, 9, 10}
        row_tds: list[str] = []
        for idx, (value, title) in enumerate(row_cells):
            cell_class = "num" if idx in numeric_columns else ""
            title_attr = f' title="{html.escape(str(title), quote=True)}"' if title else ""
            row_tds.append(
                f'<td class="{cell_class}"{title_attr}>{html.escape(str(value))}</td>'
            )
        recent_rows.append("<tr>" + "".join(row_tds) + "</tr>")

    title_suffix = "carnet d'ordres fournisseur" if node_id.startswith("SDC-") else "carnet d'ordres"
    statuses_text = ", ".join(f"{status}={count}" for status, count in sorted(status_counts.items())) or "aucun"
    table_header = "".join(
        f"<th>{html.escape(label)}</th>"
        for label in [
            "Ordre passe",
            "Item",
            "Type",
            "Flux",
            "Envoi",
            "Delai prev. mat.",
            "Arrivee prev.",
            "Arrivee effective",
            "Delai eff. mat.",
            "Qte envoyee",
            "Qte recue",
            "Statut",
            "Exceptions",
        ]
    )
    table_cols = "".join(
        f"<col style=\"width:{width}px\">"
        for width in [90, 90, 130, 270, 80, 95, 115, 125, 105, 115, 115, 330, 145]
    )
    recent_rows_body = "".join(recent_rows) if recent_rows else "<tr><td colspan=\"13\">Aucun ordre journalise</td></tr>"
    recent_orders_html = (
        "<div class=\"orderLedgerFrame\">"
        "<div class=\"orderLedgerTableWrap\" tabindex=\"0\" aria-label=\"Tableau du carnet MRP avec barre de defilement horizontale native en bas.\">"
        "<table class=\"orderLedgerTable orderLedgerWideTable\">"
        f"<colgroup>{table_cols}</colgroup>"
        f"<thead><tr>{table_header}</tr></thead>"
        f"<tbody>{recent_rows_body}</tbody>"
        "</table>"
        "</div>"
        "</div>"
    )

    return "".join(
        [
            "<div class=\"factoryHtmlPanelContent orderLedgerPanelContent\">",
            f"<div class=\"orderLedgerTextHeader\">{html.escape(node_id)} - {html.escape(title_suffix)}</div>",
            f"<div class=\"orderLedgerStatus\">Ordres MRP journalises: {len(sorted_orders)} ; lignes affichees: {len(display_orders)} ({html.escape(display_note)})</div>",
            f"<div class=\"orderLedgerStatus\">Statuses lignes brutes: {html.escape(statuses_text)}</div>",
            "<div class=\"orderLedgerStatus\">Jalons: ordre_passe=order_date_imt | envoi=release_day | arrivee_previsionnelle=ordre_passe+delai_previsionnel_source | arrivee_effective=actual_receipt_day/arrival_day | delai_previsionnel_matiere=delai source donnees FIA/Extract | delai_effectif_matiere=arrivee_effective-ordre_passe</div>",
            "<div class=\"orderLedgerSectionTitle\">Ordres passes affiches: 500 derniers puis 500 premiers si le carnet depasse 1000 lignes.</div>",
            recent_orders_html,
            "</div>",
        ]
    )


def render_supplier_stock_flows_html(
    node_id: str,
    flow_rows: list[dict[str, str]],
    shipment_rows: list[dict[str, str]],
    order_rows: list[dict[str, str]],
    item_labels: dict[str, str],
) -> str:
    visible_flow_rows = [
        row for row in flow_rows
        if not is_simulation_hidden_item(str(row.get("item_id") or ""))
    ]
    visible_shipment_rows = [
        row for row in shipment_rows
        if not is_simulation_hidden_item(str(row.get("item_id") or ""))
    ]
    visible_order_rows = [
        row for row in order_rows
        if str(row.get("src_node_id") or "") == node_id
        and not is_simulation_hidden_item(str(row.get("item_id") or ""))
    ]
    if not visible_flow_rows and not visible_shipment_rows and not visible_order_rows:
        return (
            "<div class=\"factoryHtmlPanelContent orderLedgerPanelContent\">"
            f"<div class=\"orderLedgerTextHeader\">{html.escape(node_id)} - flux stock fournisseur</div>"
            "<div class=\"panelEmptyState\">Aucun flux stock fournisseur, envoi physique ou ordre previsionnel disponible pour ce noeud.</div>"
            "</div>"
        )

    stats_by_item: dict[str, dict[str, Any]] = {}

    def stats_for(item_id: str, uom: str = "") -> dict[str, Any]:
        stats = stats_by_item.get(item_id)
        if stats is None:
            stats = {
                "uom": uom,
                "first_day": None,
                "last_day": None,
                "stock_start": 0.0,
                "stock_end": 0.0,
                "min_stock": None,
                "max_stock": 0.0,
                "incoming": 0.0,
                "incoming_external": 0.0,
                "incoming_estimated": 0.0,
                "incoming_upstream": 0.0,
                "stock_writeoff": 0.0,
                "outgoing_pulled": 0.0,
                "outgoing_shipped": 0.0,
                "physical_shipped": 0.0,
                "planned_received": 0.0,
                "confirmed_received": 0.0,
                "loss": 0.0,
                "incoming_days": 0,
                "outgoing_days": 0,
                "physical_send_days": set(),
                "planned_receipt_days": set(),
                "confirmed_receipt_days": set(),
                "max_balance_gap": 0.0,
            }
            stats_by_item[item_id] = stats
        elif uom and not stats.get("uom"):
            stats["uom"] = uom
        return stats

    for row in visible_flow_rows:
        item_id = str(row.get("item_id") or "")
        if not item_id:
            continue
        stats = stats_for(item_id, str(row.get("uom") or ""))
        day = int(to_float(row.get("day")) or 0)
        start = max(0.0, to_float(row.get("stock_start_of_day")) or 0.0)
        end = max(0.0, to_float(row.get("stock_end_of_day")) or 0.0)
        incoming = max(0.0, to_float(row.get("incoming_qty")) or 0.0)
        outgoing = max(0.0, to_float(row.get("outgoing_pulled_qty")) or 0.0)
        if stats["first_day"] is None or day < stats["first_day"]:
            stats["first_day"] = day
            stats["stock_start"] = start
        if stats["last_day"] is None or day >= stats["last_day"]:
            stats["last_day"] = day
            stats["stock_end"] = end
        stats["min_stock"] = end if stats["min_stock"] is None else min(stats["min_stock"], end)
        stats["max_stock"] = max(stats["max_stock"], end, start)
        stats["incoming"] += incoming
        stats["incoming_external"] += max(0.0, to_float(row.get("incoming_external_market_qty")) or 0.0)
        stats["incoming_estimated"] += max(0.0, to_float(row.get("incoming_estimated_source_qty")) or 0.0)
        stats["incoming_upstream"] += max(0.0, to_float(row.get("incoming_upstream_pipeline_qty")) or 0.0)
        stats["stock_writeoff"] += max(0.0, to_float(row.get("stock_writeoff_qty")) or 0.0)
        stats["outgoing_pulled"] += outgoing
        stats["outgoing_shipped"] += max(0.0, to_float(row.get("outgoing_shipped_qty")) or 0.0)
        stats["loss"] += max(0.0, to_float(row.get("outgoing_unreliable_loss_qty")) or 0.0)
        if incoming > 1e-9:
            stats["incoming_days"] += 1
        if outgoing > 1e-9:
            stats["outgoing_days"] += 1
        stats["max_balance_gap"] = max(
            stats["max_balance_gap"],
            abs(to_float(row.get("balance_check_gap_qty")) or 0.0),
        )

    for row in visible_shipment_rows:
        item_id = str(row.get("item_id") or "")
        if not item_id:
            continue
        stats = stats_for(item_id, str(row.get("uom") or ""))
        shipped = max(0.0, to_float(row.get("shipped_qty")) or 0.0)
        if shipped <= 1e-9:
            continue
        stats["physical_shipped"] += shipped
        send_day = to_float(row.get("day"))
        if send_day is not None and not math.isnan(send_day):
            stats["physical_send_days"].add(int(round(send_day)))
        receipt_day = to_float(row.get("arrival_day"))
        if receipt_day is not None and not math.isnan(receipt_day):
            stats["confirmed_received"] += shipped
            stats["confirmed_receipt_days"].add(int(round(receipt_day)))

    for row in visible_order_rows:
        item_id = str(row.get("item_id") or "")
        if not item_id:
            continue
        stats = stats_for(item_id, str(row.get("uom") or ""))
        planned_received = max(0.0, to_float(row.get("planned_receipt_qty")) or 0.0)
        if planned_received <= 1e-9:
            continue
        stats["planned_received"] += planned_received
        planned_receipt_day = planned_order_receipt_day(row)
        if planned_receipt_day is not None and not math.isnan(planned_receipt_day):
            stats["planned_receipt_days"].add(int(round(planned_receipt_day)))

    rows_html: list[str] = []
    for item_id, stats in sorted(stats_by_item.items(), key=lambda kv: item_labels.get(kv[0], kv[0])):
        title = (
            "Stock fin = stock debut + entrees - sorties stock. "
            "Sorties stock = quantite prelevee chez fournisseur; expedie aval = quantite utile apres fiabilite."
        )
        cells = [
            (item_labels.get(item_id, compact_item_label(item_id)), f"Item complet: {item_id}"),
            (stats.get("uom") or "n/a", ""),
            (fmt_qty(stats.get("stock_start"), 1), title),
            (fmt_qty(stats.get("incoming"), 1), "entrees reelles dans le stock fournisseur"),
            (fmt_qty(stats.get("incoming_external"), 1), "dont arrivees appro amont fournisseur"),
            (fmt_qty(stats.get("stock_writeoff"), 1), "pertes de stock fournisseur appliquees par evenement de risque"),
            (fmt_qty(stats.get("outgoing_pulled"), 1), "sorties reelles du stock fournisseur"),
            (fmt_qty(stats.get("outgoing_shipped"), 1), "quantite utile expediee aval apres fiabilite"),
            (fmt_qty(stats.get("physical_shipped"), 1), "envois physiques issus de production_supplier_shipments_daily.day"),
            (fmt_qty(stats.get("planned_received"), 1), "receptions aval previsionnelles issues du carnet MRP, datees a ordre_passe + delai previsionnel source"),
            (fmt_qty(stats.get("confirmed_received"), 1), "receptions aval reelles confirmees, datees par arrival_day des envois physiques fournisseur"),
            (
                fmt_qty((stats.get("physical_shipped") or 0.0) - (stats.get("outgoing_shipped") or 0.0), 1),
                "ecart entre envois physiques et expedie aval du bilan stock; les commandes d'ouverture/historiques peuvent etre hors bilan stock quotidien",
            ),
            (fmt_qty(stats.get("loss"), 1), "ecart entre stock preleve et quantite utile aval"),
            (fmt_qty(stats.get("stock_end"), 1), title),
            (fmt_qty(stats.get("min_stock"), 1), "stock fin de jour minimum observe"),
            (fmt_qty(stats.get("max_stock"), 1), "stock maximum observe"),
            (str(stats.get("incoming_days") or 0), "jours avec entree fournisseur"),
            (str(stats.get("outgoing_days") or 0), "jours avec sortie fournisseur"),
            (str(len(stats.get("physical_send_days") or [])), "jours avec envoi physique"),
            (str(len(stats.get("planned_receipt_days") or [])), "jours avec reception aval previsionnelle"),
            (str(len(stats.get("confirmed_receipt_days") or [])), "jours avec reception aval reelle confirmee"),
            (fmt_qty(stats.get("max_balance_gap"), 6), "ecart max du bilan stock quotidien"),
        ]
        numeric_columns = set(range(2, len(cells)))
        row_tds: list[str] = []
        for idx, (value, cell_title) in enumerate(cells):
            cell_class = "num" if idx in numeric_columns else ""
            title_attr = f' title="{html.escape(str(cell_title), quote=True)}"' if cell_title else ""
            row_tds.append(f'<td class="{cell_class}"{title_attr}>{html.escape(str(value))}</td>')
        rows_html.append("<tr>" + "".join(row_tds) + "</tr>")

    headers = [
        "Item",
        "UOM",
        "Stock debut",
        "Entrees total",
        "Dont appro amont",
        "Pertes stock",
        "Sorties stock",
        "Expedie aval",
        "Envois phys.",
        "Receptions prev.",
        "Receptions reelles",
        "Ecart phys/stock",
        "Ecart fiabilite",
        "Stock fin",
        "Stock min",
        "Stock max",
        "Jours entree",
        "Jours sortie",
        "Jours envoi phys.",
        "Jours recept. prev.",
        "Jours recept. reelle",
        "Ecart bilan",
    ]
    table_cols = "".join(
        f"<col style=\"width:{width}px\">"
        for width in [105, 70, 115, 125, 125, 115, 120, 120, 120, 120, 130, 125, 120, 115, 115, 115, 100, 100, 120, 120, 130, 110]
    )
    return "".join(
        [
            "<div class=\"factoryHtmlPanelContent orderLedgerPanelContent\">",
            f"<div class=\"orderLedgerTextHeader\">{html.escape(node_id)} - flux stock fournisseur</div>",
            "<div class=\"orderLedgerStatus\">Bilan quotidien consolide par item: stock debut + entrees fournisseur - pertes stock - sorties stock = stock fin.</div>",
            "<div class=\"orderLedgerStatus\">Entrees = arrivees dans le stock fournisseur; sorties stock = quantite prelevee chez le fournisseur; expedie aval tient compte de la fiabilite.</div>",
            "<div class=\"orderLedgerStatus\">Envois phys. = production_supplier_shipments_daily.day. Receptions prev. = carnet MRP date a ordre_passe + delai previsionnel source. Receptions reelles = arrival_day des envois physiques confirmes.</div>",
            "<div class=\"orderLedgerFrame\">",
            "<div class=\"orderLedgerTableWrap\" tabindex=\"0\" aria-label=\"Tableau des flux de stock fournisseur avec defilement horizontal natif en bas.\">",
            "<table class=\"orderLedgerTable orderLedgerWideTable\">",
            f"<colgroup>{table_cols}</colgroup>",
            f"<thead><tr>{''.join(f'<th>{html.escape(label)}</th>' for label in headers)}</tr></thead>",
            f"<tbody>{''.join(rows_html)}</tbody>",
            "</table>",
            "</div>",
            "</div>",
            "</div>",
        ]
    )


def finite_numeric_values(values: Iterable[Any], *, positive_only: bool = False) -> list[float]:
    out: list[float] = []
    for value in values:
        numeric = to_float(value)
        if numeric is None or math.isnan(numeric):
            continue
        if positive_only and numeric <= 0:
            continue
        out.append(float(numeric))
    return out


def coefficient_of_variation(values: list[float]) -> float | None:
    if len(values) < 2:
        return None
    mean_value = statistics.mean(values)
    if abs(mean_value) <= 1e-12:
        return None
    return statistics.pstdev(values) / abs(mean_value)


def uncertainty_level(cv: float | None) -> str:
    if cv is None:
        return "non estimee"
    if cv < 0.05:
        return "stable"
    if cv < 0.20:
        return "variable"
    return "tres variable"


def fmt_uncertainty_band(values: list[float], *, kind: str = "qty", digits: int = 1) -> str:
    if not values:
        return "n/a"
    p10 = percentile(values, 0.10)
    p50 = percentile(values, 0.50)
    p90 = percentile(values, 0.90)

    def fmt_value(value: float) -> str:
        if kind == "days":
            return fmt_days(value, digits)
        if kind == "pct":
            return fmt_pct(value * 100.0, digits)
        return fmt_qty(value, digits)

    return f"P10={fmt_value(p10)} ; P50={fmt_value(p50)} ; P90={fmt_value(p90)}"


def render_passive_uncertainty_html(
    scope_id: str,
    *,
    scope_label: str,
    order_rows: list[dict[str, str]],
    stock_rows: list[dict[str, str]],
    capacity_rows: list[dict[str, str]],
    shipment_rows: list[dict[str, str]],
    nominal_rows: list[dict[str, str]],
    item_labels: dict[str, str],
) -> str:
    visible_order_rows = [
        row for row in order_rows
        if not is_simulation_hidden_item(str(row.get("item_id") or ""))
    ]
    visible_stock_rows = [
        row for row in stock_rows
        if not is_simulation_hidden_item(str(row.get("item_id") or ""))
    ]
    visible_capacity_rows = [
        row for row in capacity_rows
        if not is_simulation_hidden_item(str(row.get("item_id") or ""))
    ]
    visible_shipment_rows = [
        row for row in shipment_rows
        if not is_simulation_hidden_item(str(row.get("item_id") or ""))
    ]
    visible_nominal_rows = [
        row for row in nominal_rows
        if not is_simulation_hidden_item(str(row.get("item_id") or ""))
    ]

    planned_leads = finite_numeric_values(
        (planned_procurement_lead_days(row) for row in visible_order_rows),
        positive_only=True,
    )
    if not planned_leads:
        planned_leads = finite_numeric_values(
            (row.get("planned_lead_time_days") for row in visible_nominal_rows),
            positive_only=True,
        )
    effective_leads = finite_numeric_values(
        (effective_procurement_lead_days(row) for row in visible_order_rows),
        positive_only=True,
    )
    if not effective_leads:
        effective_leads = finite_numeric_values(
            (row.get("lead_days") for row in visible_shipment_rows),
            positive_only=True,
        )
    comparable_lead_pairs: list[tuple[float, float]] = []
    for row in visible_order_rows:
        planned = planned_procurement_lead_days(row)
        effective = effective_procurement_lead_days(row)
        if planned is None or effective is None or planned <= 0 or effective < 0:
            continue
        comparable_lead_pairs.append((float(planned), float(effective)))
    lead_ratio_values = [
        effective / planned
        for planned, effective in comparable_lead_pairs
        if planned > 0
    ]
    late_pairs = [
        (planned, effective)
        for planned, effective in comparable_lead_pairs
        if effective > planned + 1e-9
    ]
    delay_probability = len(late_pairs) / len(comparable_lead_pairs) if comparable_lead_pairs else None
    avg_delay = (
        statistics.mean(max(0.0, effective - planned) for planned, effective in comparable_lead_pairs)
        if comparable_lead_pairs
        else None
    )
    lead_cv = coefficient_of_variation(lead_ratio_values) or coefficient_of_variation(effective_leads)
    lead_cv_suggested = max(0.05, min(0.35, lead_cv if lead_cv is not None else 0.10))

    capacity_values = finite_numeric_values(
        (row.get("capacity_qty_per_day") for row in visible_capacity_rows),
        positive_only=True,
    )
    utilization_values = finite_numeric_values((row.get("utilization") for row in visible_capacity_rows))
    nominal_capacity_values = finite_numeric_values(
        (
            row.get("industrial_nominal_capacity_qty_per_day")
            or row.get("effective_capacity_qty_per_day")
            or row.get("nominal_capacity_qty_per_day")
            for row in visible_nominal_rows
        ),
        positive_only=True,
    )
    max_utilization = max(utilization_values) if utilization_values else None
    avg_active_utilization_values = [value for value in utilization_values if value > 1e-9]
    avg_active_utilization = statistics.mean(avg_active_utilization_values) if avg_active_utilization_values else None
    capacity_cv = coefficient_of_variation(avg_active_utilization_values or utilization_values)
    capacity_cv_suggested = max(0.05, min(0.30, capacity_cv if capacity_cv is not None else 0.10))

    stock_values = finite_numeric_values((row.get("stock_end_of_day") for row in visible_stock_rows))
    stock_cv = coefficient_of_variation(stock_values)
    stock_cv_suggested = max(0.05, min(0.40, stock_cv if stock_cv is not None else 0.15))
    stock_zero_days = sum(1 for value in stock_values if value <= 1e-9)
    stock_zero_probability = stock_zero_days / len(stock_values) if stock_values else None

    reliability_values = finite_numeric_values((row.get("reliability") for row in visible_shipment_rows))
    loss_ratios: list[float] = []
    for row in visible_shipment_rows:
        pulled = to_float(row.get("pulled_qty"))
        shipped = to_float(row.get("shipped_qty"))
        if pulled is None or shipped is None or math.isnan(pulled) or math.isnan(shipped) or pulled <= 0:
            continue
        loss_ratios.append(max(0.0, min(1.0, (pulled - shipped) / pulled)))
    reliability_cv = coefficient_of_variation(reliability_values)
    reliability_mean = statistics.mean(reliability_values) if reliability_values else None
    loss_mean = statistics.mean(loss_ratios) if loss_ratios else None
    reliability_cv_suggested = max(0.002, min(0.05, reliability_cv if reliability_cv is not None else 0.005))

    item_ids = sorted(
        {
            str(row.get("item_id") or "")
            for row in visible_order_rows
            + visible_stock_rows
            + visible_capacity_rows
            + visible_shipment_rows
            + visible_nominal_rows
            if str(row.get("item_id") or "")
        }
    )
    item_text = ", ".join(item_labels.get(item_id, compact_item_label(item_id)) for item_id in item_ids[:8])
    if len(item_ids) > 8:
        item_text += f" +{len(item_ids) - 8}"
    if not item_text:
        item_text = "n/a"

    def fmt_optional_mean(values: list[float], *, kind: str = "qty", digits: int = 1) -> str:
        if not values:
            return "n/a"
        value = statistics.mean(values)
        if kind == "days":
            return fmt_days(value, digits)
        if kind == "pct":
            return fmt_pct(value * 100.0, digits)
        return fmt_qty(value, digits)

    def fmt_optional_pct_fraction(value: float | None, digits: int = 1) -> str:
        return "n/a" if value is None else fmt_pct(value * 100.0, digits)

    def data_confidence(row_count: int, *, has_distribution: bool = True) -> float:
        value = 0.18 + math.log1p(max(0, row_count)) / 7.5
        if has_distribution:
            value += 0.08
        return max(0.0, min(0.95, value))

    def uncertainty_pressure_from_cv(cv: float | None, *, missing_penalty: float, scale: float) -> float:
        if cv is None:
            return missing_penalty
        return max(0.0, min(1.0, cv / scale))

    lead_uncertainty = uncertainty_pressure_from_cv(lead_cv, missing_penalty=0.45, scale=0.35)
    capacity_uncertainty = uncertainty_pressure_from_cv(capacity_cv, missing_penalty=0.35, scale=0.30)
    stock_uncertainty = uncertainty_pressure_from_cv(stock_cv, missing_penalty=0.35, scale=0.80)
    reliability_uncertainty = uncertainty_pressure_from_cv(reliability_cv, missing_penalty=0.30, scale=0.05)
    delay_risk = max(lead_uncertainty, delay_probability or 0.0)
    capacity_risk = capacity_uncertainty
    stock_cycle_pressure = min(0.35, stock_uncertainty)
    stock_risk = max(stock_cycle_pressure, stock_zero_probability or 0.0)
    reliability_risk = max(reliability_uncertainty, min(1.0, 4.0 * (loss_mean or 0.0)))
    global_uncertainty = (
        0.35 * delay_risk
        + 0.25 * capacity_risk
        + 0.20 * stock_risk
        + 0.20 * reliability_risk
    )
    global_confidence = statistics.mean(
        [
            data_confidence(len(comparable_lead_pairs), has_distribution=bool(effective_leads)),
            data_confidence(len(visible_capacity_rows), has_distribution=bool(capacity_values)),
            data_confidence(len(visible_stock_rows), has_distribution=bool(stock_values)),
            data_confidence(len(visible_shipment_rows), has_distribution=bool(reliability_values or loss_ratios)),
        ]
    )

    def uncertainty_status_key(score: float) -> str:
        if score >= 0.60:
            return "sensitive"
        if score >= 0.30:
            return "watch"
        return "robust"

    def uncertainty_status_label(score: float) -> str:
        if score >= 0.60:
            return "fragile"
        if score >= 0.30:
            return "a qualifier"
        return "fiable"

    def uncertainty_fact(label: str, value: str, tooltip: str | None = None) -> str:
        return "".join(
            [
                f"<div class=\"{html_tooltip_class('', tooltip)}\"{html_tooltip_attrs(tooltip)}>",
                f"<span>{html.escape(label)}</span>",
                f"<b>{html.escape(value)}</b>",
                "</div>",
            ]
        )

    def uncertainty_card(title: str, value: str, note: str, score: float, tooltip: str | None = None) -> str:
        status_key = uncertainty_status_key(score)
        return "".join(
            [
                f"<div class=\"{html_tooltip_class(f'uncertaintyCard sensitivityStatus-{html.escape(status_key)}', tooltip)}\"{html_tooltip_attrs(tooltip)}>",
                f"<div class=\"uncertaintyCardLabel\">{html.escape(title)}</div>",
                f"<div class=\"uncertaintyCardValue\">{html.escape(value)}</div>",
                f"<div class=\"uncertaintyCardNote\">{html.escape(note)}</div>",
                "</div>",
            ]
        )

    global_uncertainty_tooltip = "\n".join(
        [
            "Formule",
            "incertitude globale = 35% delai + 25% capacite + 20% stock + 20% fiabilite",
            "",
            "Calcul ici",
            f"35% x delai {fmt_pct(delay_risk * 100.0)}",
            f"25% x capacite {fmt_pct(capacity_risk * 100.0)}",
            f"20% x stock {fmt_pct(stock_risk * 100.0)}",
            f"20% x fiabilite {fmt_pct(reliability_risk * 100.0)}",
            f"Resultat = {fmt_pct(global_uncertainty * 100.0)}",
            "",
            "Lecture",
            "Mesure la qualite de lecture et la dispersion des donnees locales. Ce n'est ni un incident simule, ni une mesure de resilience.",
        ]
    )
    confidence_tooltip = "\n".join(
        [
            "Formule",
            "confiance donnees = moyenne des couvertures delai, capacite, stock et fiabilite",
            "",
            "Calcul ici",
            f"Ordres comparables delai = {len(comparable_lead_pairs)}",
            f"Lignes capacite = {len(visible_capacity_rows)}",
            f"Lignes stock = {len(visible_stock_rows)}",
            f"Lignes flux = {len(visible_shipment_rows)}",
            f"Confiance moyenne = {fmt_pct(global_confidence * 100.0)}",
            "",
            "Lecture",
            "Plus cette valeur est haute, plus les donnees suffisent a lire la situation.",
        ]
    )
    lead_tooltip = "\n".join(
        [
            "Formule",
            "score delai = max(incertitude delai, taux de retard)",
            "incertitude delai = CV delai / 35%",
            "",
            "Calcul ici",
            f"CV delai = {fmt_optional_pct_fraction(lead_cv)}",
            f"Incertitude delai = {fmt_pct(lead_uncertainty * 100.0)}",
            f"Taux retard = {fmt_optional_pct_fraction(delay_probability)}",
            f"Retard moyen = {fmt_days(avg_delay, 1)}",
            f"Score delai = {fmt_pct(delay_risk * 100.0)}",
            "",
            "Lecture",
            "Mesure si les delais observes sont disperses ou souvent au-dessus du delai prevu.",
        ]
    )
    capacity_tooltip = "\n".join(
        [
            "Formule",
            "score capacite = CV utilisation capacite / 30%",
            "",
            "Calcul ici",
            f"CV utilisation = {fmt_optional_pct_fraction(capacity_cv)}",
            f"Utilisation active moyenne = {fmt_optional_pct_fraction(avg_active_utilization)}",
            f"Utilisation max = {fmt_optional_pct_fraction(max_utilization)}",
            f"Score capacite = {fmt_pct(capacity_risk * 100.0)}",
            "",
            "Lecture",
            "Mesure la dispersion de l'utilisation capacite disponible dans les donnees.",
        ]
    )
    stock_tooltip = "\n".join(
        [
            "Formule",
            "score stock = max(pression cycle stock, part jours a stock zero)",
            "pression cycle stock = min(35%, CV stock / 80%)",
            "",
            "Calcul ici",
            f"CV stock = {fmt_optional_pct_fraction(stock_cv)}",
            f"Pression cycle stock = {fmt_pct(stock_cycle_pressure * 100.0)}",
            f"Part jours stock zero = {fmt_optional_pct_fraction(stock_zero_probability)}",
            f"Jours stock zero = {stock_zero_days}",
            f"Score stock = {fmt_pct(stock_risk * 100.0)}",
            "",
            "Lecture",
            "Mesure l'incertitude de lecture liee aux cycles de stock et aux passages a zero.",
        ]
    )
    reliability_tooltip = "\n".join(
        [
            "Formule",
            "score fiabilite = max(CV fiabilite / 5%, 4 x perte moyenne)",
            "",
            "Calcul ici",
            f"CV fiabilite = {fmt_optional_pct_fraction(reliability_cv)}",
            f"Incertitude fiabilite = {fmt_pct(reliability_uncertainty * 100.0)}",
            f"Perte moyenne = {fmt_optional_pct_fraction(loss_mean, 2)}",
            f"4 x perte moyenne = {fmt_optional_pct_fraction(4.0 * (loss_mean or 0.0), 2)}",
            f"Score fiabilite = {fmt_pct(reliability_risk * 100.0)}",
            "",
            "Lecture",
            "Mesure la dispersion de fiabilite et les pertes observees sur les flux fournisseur.",
        ]
    )

    dashboard_html = "".join(
        [
            f"<div class=\"{html_tooltip_class(f'uncertaintyDashboard sensitivityStatus-{html.escape(uncertainty_status_key(global_uncertainty))}', global_uncertainty_tooltip)}\"{html_tooltip_attrs(global_uncertainty_tooltip)}>",
            "<div class=\"uncertaintyHero\">",
            "<div>",
            f"<div class=\"sensitivityStatusPill\">Lecture {html.escape(uncertainty_status_label(global_uncertainty))}</div>",
            f"<div class=\"uncertaintyHeroTitle\">{html.escape(scope_id)} - confiance de lecture</div>",
            f"<div class=\"uncertaintyHeroText\">Ce panneau dit si les donnees locales sont faciles a lire: couverture, dispersion des delais, cycles de stock, capacite et fiabilite. Il ne mesure pas la resilience du systeme. La resilience se lit dans le bouton Monte Carlo. Score lecture {fmt_pct(global_uncertainty * 100.0)} ; confiance donnees {fmt_pct(global_confidence * 100.0)}.</div>",
            "</div>",
            "<div class=\"uncertaintyHeroFacts\">",
            uncertainty_fact("Items", item_text, f"Items couverts par cette lecture: {item_text}"),
            uncertainty_fact("Lignes ordres", str(len(visible_order_rows)), f"Lignes carnet MRP/ordres utilisees. Couples delai comparables: {len(comparable_lead_pairs)}."),
            uncertainty_fact("Lignes stock", str(len(visible_stock_rows)), f"Lignes de stock fournisseur utilisees. Jours stock zero detectes: {stock_zero_days}."),
            uncertainty_fact("Lignes flux", str(len(visible_shipment_rows)), f"Lignes de flux fournisseur utilisees. Confiance donnees globale: {fmt_pct(global_confidence * 100.0)}."),
            "</div>",
            "</div>",
            "<div class=\"uncertaintyCardGrid\">",
            uncertainty_card(
                "Delai matiere",
                uncertainty_level(lead_cv),
                "dispersion observee des delais" if lead_cv is not None else "donnees de delai limitees",
                delay_risk,
                lead_tooltip,
            ),
            uncertainty_card(
                "Capacite",
                uncertainty_level(capacity_cv),
                f"utilisation max {fmt_optional_pct_fraction(max_utilization)}",
                capacity_risk,
                capacity_tooltip,
            ),
            uncertainty_card(
                "Stock",
                uncertainty_level(stock_cv),
                f"jours a stock zero: {stock_zero_days}",
                stock_risk,
                stock_tooltip,
            ),
            uncertainty_card(
                "Fiabilite",
                uncertainty_level(reliability_cv),
                f"perte moyenne {fmt_optional_pct_fraction(loss_mean, 2)}",
                reliability_risk,
                reliability_tooltip,
            ),
            "</div>",
            "</div>",
        ]
    )

    def envelope_row(
        scenario: str,
        lead_mult: float,
        cap_mult: float,
        stock_mult: float,
        reliability_mult: float,
        meaning: str,
    ) -> str:
        lead_factor = 1.0 + lead_cv_suggested * lead_mult
        cap_factor = max(0.0, 1.0 - capacity_cv_suggested * cap_mult)
        stock_factor = max(0.0, 1.0 - stock_cv_suggested * stock_mult)
        reliability_factor = max(0.0, 1.0 - reliability_cv_suggested * reliability_mult)
        return (
            "<tr>"
            f"<td>{html.escape(scenario)}</td>"
            f"<td>x{lead_factor:.2f}</td>"
            f"<td>x{cap_factor:.2f}</td>"
            f"<td>x{stock_factor:.2f}</td>"
            f"<td>x{reliability_factor:.3f}</td>"
            f"<td>{html.escape(meaning)}</td>"
            "</tr>"
        )

    envelope_rows = [
        envelope_row("Reference", 0.0, 0.0, 0.0, 0.0, "run courant, sans alea ajoute"),
        envelope_row("Prudent", 1.0, 1.0, 1.0, 1.0, "variation plausible a tester en premier"),
        envelope_row("Pessimiste", 2.0, 2.0, 2.0, 2.0, "stress d'incertitude sans incident explicite"),
    ]
    envelope_html = "".join(
        [
            "<div class=\"uncertaintyEnvelope\">",
            "<table class=\"kpiFormulaTable\">",
            "<thead><tr><th>Enveloppe</th><th>Delai</th><th>Capacite</th><th>Stock</th><th>Fiabilite</th><th>Lecture</th></tr></thead>",
            f"<tbody>{''.join(envelope_rows)}</tbody>",
            "</table>",
            "</div>",
        ]
    )

    quality_rows = [
        ("Lead time", len(comparable_lead_pairs), data_confidence(len(comparable_lead_pairs), has_distribution=bool(effective_leads)), "ordre -> reception prevue/effective"),
        ("Capacite", len(visible_capacity_rows), data_confidence(len(visible_capacity_rows), has_distribution=bool(capacity_values)), "capacite quotidienne observee"),
        ("Stock", len(visible_stock_rows), data_confidence(len(visible_stock_rows), has_distribution=bool(stock_values)), "stock fournisseur journalier"),
        ("Fiabilite", len(visible_shipment_rows), data_confidence(len(visible_shipment_rows), has_distribution=bool(reliability_values or loss_ratios)), "expeditions et pertes"),
    ]
    quality_html = "".join(
        [
            "<div class=\"uncertaintyQualityGrid\">",
            *(
                "<div class=\"uncertaintyQualityCell\">"
                f"<div class=\"uncertaintyQualityTitle\">{html.escape(name)}</div>"
                f"<div class=\"uncertaintyQualityValue\">{count} lignes · {fmt_pct(conf * 100.0)}</div>"
                f"<div class=\"uncertaintyQualityNote\">{html.escape(note)}</div>"
                "</div>"
                for name, count, conf, note in quality_rows
            ),
            "</div>",
        ]
    )

    table_rows = [
        (
            "Lead time",
            "mrp_orders_daily: order_date_imt, actual_receipt_day, lead_reference_days",
            fmt_optional_mean(planned_leads, kind="days"),
            f"{uncertainty_level(lead_cv)}" if lead_cv is not None else "non estimee",
            fmt_uncertainty_band(effective_leads, kind="days"),
            f"taux retard={fmt_optional_pct_fraction(delay_probability)} ; retard moyen={fmt_days(avg_delay, 1)}",
            f"lead_time_cv={lead_cv_suggested:.3f} (inactif)",
        ),
        (
            "Capacite",
            "production_supplier_capacity_daily.csv",
            fmt_optional_mean(nominal_capacity_values or capacity_values),
            f"{uncertainty_level(capacity_cv)}" if capacity_cv is not None else "non estimee",
            fmt_uncertainty_band(capacity_values),
            f"util active={fmt_optional_pct_fraction(avg_active_utilization)} ; util max={fmt_optional_pct_fraction(max_utilization)}",
            f"capacity_cv={capacity_cv_suggested:.3f} (inactif)",
        ),
        (
            "Stock fournisseur",
            "production_supplier_stocks_daily.csv",
            fmt_optional_mean(stock_values),
            f"{uncertainty_level(stock_cv)}" if stock_cv is not None else "non estimee",
            fmt_uncertainty_band(stock_values),
            f"part jours stock zero={fmt_optional_pct_fraction(stock_zero_probability)} ; jours zero={stock_zero_days}",
            f"stock_availability_cv={stock_cv_suggested:.3f} (inactif)",
        ),
        (
            "Fiabilite / qualite",
            "production_supplier_shipments_daily.csv",
            fmt_optional_pct_fraction(reliability_mean),
            f"{uncertainty_level(reliability_cv)}" if reliability_cv is not None else "non estimee",
            fmt_uncertainty_band(reliability_values, kind="pct", digits=2),
            f"perte moyenne={fmt_optional_pct_fraction(loss_mean, 2)} ; lignes={len(visible_shipment_rows)}",
            f"reliability_cv={reliability_cv_suggested:.3f} (inactif)",
        ),
    ]
    rows_html = []
    for dim, source, nominal, uncertainty, band, risk, inactive_param in table_rows:
        rows_html.append(
            "<tr>"
            f"<td>{html.escape(dim)}</td>"
            f"<td>{html.escape(source)}</td>"
            f"<td>{html.escape(nominal)}</td>"
            f"<td>{html.escape(uncertainty)}</td>"
            f"<td>{html.escape(band)}</td>"
            f"<td>{html.escape(risk)}</td>"
            f"<td>{html.escape(inactive_param)}</td>"
            "</tr>"
        )

    config_preview = {
        "uncertainty_enabled": False,
        "mode": "passive_calibration_only",
        "scope": scope_id,
        "lead_time_cv": round(lead_cv_suggested, 4),
        "capacity_cv": round(capacity_cv_suggested, 4),
        "stock_availability_cv": round(stock_cv_suggested, 4),
        "reliability_cv": round(reliability_cv_suggested, 4),
    }

    return "".join(
        [
            "<div class=\"factoryHtmlPanelContent orderLedgerPanelContent\">",
            f"<div class=\"orderLedgerTextHeader\">{html.escape(scope_id)} - confiance de lecture {html.escape(scope_label)}</div>",
            "<div class=\"orderLedgerStatus\">Lecture courte: ce panneau local ne dit pas si la supply resiste. Il dit si les donnees fournisseur sont completes, stables et faciles a interpreter. La resilience se lit dans Monte Carlo.</div>",
            "<div class=\"orderLedgerSectionTitle\">Synthese confiance de lecture</div>",
            dashboard_html,
            "<details class=\"sensitivityDetails riskMethodDetails\">",
            "<summary>Afficher la methode, les donnees et les scenarios proposes</summary>",
            "<div class=\"riskMethodStack\">",
            "<div class=\"riskMethodNote\">Aucun alea n'est injecte dans la baseline. Les scenarios ci-dessous sont des enveloppes de test proposees, pas des incidents actives.</div>",
            "<div class=\"orderLedgerSectionTitle\">Scenarios proposes non actives</div>",
            envelope_html,
            "<div class=\"orderLedgerSectionTitle\">Confiance dans les donnees</div>",
            quality_html,
            "<div class=\"orderLedgerSectionTitle\">Sources et calculs techniques</div>",
            "<div class=\"orderLedgerFrame\">",
            "<div class=\"orderLedgerTableWrap\" tabindex=\"0\" aria-label=\"Tableau incertitude passive avec defilement horizontal natif en bas.\">",
            "<table class=\"orderLedgerTable orderLedgerWideTable\">",
            "<colgroup>"
            "<col style=\"width:135px\"><col style=\"width:245px\"><col style=\"width:130px\"><col style=\"width:145px\">"
            "<col style=\"width:235px\"><col style=\"width:235px\"><col style=\"width:185px\">"
            "</colgroup>",
            "<thead><tr><th>Dimension</th><th>Source technique</th><th>Reference</th><th>Variabilite</th><th>Bande observee</th><th>Signal observe</th><th>Parametre technique propose</th></tr></thead>",
            f"<tbody>{''.join(rows_html)}</tbody>",
            "</table>",
            "</div>",
            "</div>",
            "<div class=\"orderLedgerSectionTitle\">Parametres techniques proposes - inactifs dans ce run</div>",
            f"<pre class=\"jsonPanelPre\">{html.escape(json.dumps(config_preview, indent=2, ensure_ascii=False))}</pre>",
            "</div>",
            "</details>",
            "</div>",
        ]
    )


def build_passive_uncertainty_metric(
    scope_id: str,
    *,
    scope_label: str,
    order_rows: list[dict[str, str]],
    stock_rows: list[dict[str, str]],
    capacity_rows: list[dict[str, str]],
    shipment_rows: list[dict[str, str]],
    nominal_rows: list[dict[str, str]],
    item_labels: dict[str, str],
) -> dict[str, Any]:
    visible_order_rows = [
        row for row in order_rows
        if not is_simulation_hidden_item(str(row.get("item_id") or ""))
    ]
    visible_stock_rows = [
        row for row in stock_rows
        if not is_simulation_hidden_item(str(row.get("item_id") or ""))
    ]
    visible_capacity_rows = [
        row for row in capacity_rows
        if not is_simulation_hidden_item(str(row.get("item_id") or ""))
    ]
    visible_shipment_rows = [
        row for row in shipment_rows
        if not is_simulation_hidden_item(str(row.get("item_id") or ""))
    ]
    visible_nominal_rows = [
        row for row in nominal_rows
        if not is_simulation_hidden_item(str(row.get("item_id") or ""))
    ]

    comparable_lead_pairs: list[tuple[float, float]] = []
    for row in visible_order_rows:
        planned = planned_procurement_lead_days(row)
        effective = effective_procurement_lead_days(row)
        if planned is None or effective is None or planned <= 0 or effective < 0:
            continue
        comparable_lead_pairs.append((float(planned), float(effective)))
    effective_leads = finite_numeric_values(
        (effective for _planned, effective in comparable_lead_pairs),
        positive_only=True,
    )
    if not effective_leads:
        effective_leads = finite_numeric_values(
            (row.get("lead_days") for row in visible_shipment_rows),
            positive_only=True,
        )
    lead_ratio_values = [
        effective / planned
        for planned, effective in comparable_lead_pairs
        if planned > 0
    ]
    late_pairs = [
        (planned, effective)
        for planned, effective in comparable_lead_pairs
        if effective > planned + 1e-9
    ]
    delay_probability = len(late_pairs) / len(comparable_lead_pairs) if comparable_lead_pairs else None
    avg_delay = (
        statistics.mean(max(0.0, effective - planned) for planned, effective in comparable_lead_pairs)
        if comparable_lead_pairs
        else None
    )
    lead_cv = coefficient_of_variation(lead_ratio_values) or coefficient_of_variation(effective_leads)

    utilization_values = finite_numeric_values((row.get("utilization") for row in visible_capacity_rows))
    active_utilization_values = [value for value in utilization_values if value > 1e-9]
    max_utilization = max(utilization_values) if utilization_values else None
    capacity_cv = coefficient_of_variation(active_utilization_values or utilization_values)

    stock_values = finite_numeric_values((row.get("stock_end_of_day") for row in visible_stock_rows))
    stock_cv = coefficient_of_variation(stock_values)
    stock_zero_days = sum(1 for value in stock_values if value <= 1e-9)
    stock_zero_probability = stock_zero_days / len(stock_values) if stock_values else None

    reliability_values = finite_numeric_values((row.get("reliability") for row in visible_shipment_rows))
    reliability_cv = coefficient_of_variation(reliability_values)
    loss_ratios: list[float] = []
    for row in visible_shipment_rows:
        pulled = to_float(row.get("pulled_qty"))
        shipped = to_float(row.get("shipped_qty"))
        if pulled is None or shipped is None or math.isnan(pulled) or math.isnan(shipped) or pulled <= 0:
            continue
        loss_ratios.append(max(0.0, min(1.0, (pulled - shipped) / pulled)))
    loss_mean = statistics.mean(loss_ratios) if loss_ratios else None

    def data_confidence(row_count: int, *, has_distribution: bool = True) -> float:
        value = 0.18 + math.log1p(max(0, row_count)) / 7.5
        if has_distribution:
            value += 0.08
        return max(0.0, min(0.95, value))

    def uncertainty_pressure_from_cv(cv: float | None, *, missing_penalty: float, scale: float) -> float:
        if cv is None:
            return missing_penalty
        return max(0.0, min(1.0, cv / scale))

    lead_uncertainty = uncertainty_pressure_from_cv(lead_cv, missing_penalty=0.45, scale=0.35)
    capacity_uncertainty = uncertainty_pressure_from_cv(capacity_cv, missing_penalty=0.35, scale=0.30)
    stock_uncertainty = uncertainty_pressure_from_cv(stock_cv, missing_penalty=0.35, scale=0.80)
    reliability_uncertainty = uncertainty_pressure_from_cv(reliability_cv, missing_penalty=0.30, scale=0.05)
    delay_risk = max(lead_uncertainty, delay_probability or 0.0)
    capacity_risk = capacity_uncertainty
    stock_risk = max(min(0.35, stock_uncertainty), stock_zero_probability or 0.0)
    reliability_risk = max(reliability_uncertainty, min(1.0, 4.0 * (loss_mean or 0.0)))
    dimension_scores = {
        "Delai": delay_risk,
        "Capacite": capacity_risk,
        "Stock": stock_risk,
        "Fiabilite": reliability_risk,
    }
    global_uncertainty = (
        0.35 * delay_risk
        + 0.25 * capacity_risk
        + 0.20 * stock_risk
        + 0.20 * reliability_risk
    )
    global_confidence = statistics.mean(
        [
            data_confidence(len(comparable_lead_pairs), has_distribution=bool(effective_leads)),
            data_confidence(len(visible_capacity_rows), has_distribution=bool(utilization_values)),
            data_confidence(len(visible_stock_rows), has_distribution=bool(stock_values)),
            data_confidence(len(visible_shipment_rows), has_distribution=bool(reliability_values or loss_ratios)),
        ]
    )

    if global_uncertainty >= 0.60:
        status = "high"
        status_label = "Lecture fragile"
        color = "#dc2626"
    elif global_uncertainty >= 0.30:
        status = "moderate"
        status_label = "Lecture a qualifier"
        color = "#d97706"
    else:
        status = "low"
        status_label = "Lecture fiable"
        color = "#16a34a"

    dominant_dimension, dominant_score = max(dimension_scores.items(), key=lambda item: item[1])
    item_ids = sorted(
        {
            str(row.get("item_id") or "")
            for row in visible_order_rows
            + visible_stock_rows
            + visible_capacity_rows
            + visible_shipment_rows
            + visible_nominal_rows
            if str(row.get("item_id") or "")
        }
    )
    item_text = ", ".join(item_labels.get(item_id, compact_item_label(item_id)) for item_id in item_ids[:6])
    if len(item_ids) > 6:
        item_text += f" +{len(item_ids) - 6}"
    if not item_text:
        item_text = "n/a"

    def fmt_ratio_pct(value: float | None, digits: int = 1) -> str:
        return "n/a" if value is None else fmt_pct(value * 100.0, digits)

    summary_lines = [
        metric_label_value("Famille", f"Qualite de lecture {scope_label}"),
        metric_label_value("Lecture", "Confiance dans les donnees et parametres. Aucun alea n'est injecte dans la baseline."),
        metric_label_value("Score general", fmt_pct(global_uncertainty * 100.0)),
        metric_label_value("Statut general", status_label),
        metric_label_value("Source principale d'incertitude", f"{dominant_dimension} ({fmt_pct(dominant_score * 100.0)})"),
        metric_label_value("Confiance donnees", fmt_pct(global_confidence * 100.0)),
        metric_label_value("Retard matiere", f"taux de retard={fmt_ratio_pct(delay_probability)} ; retard moyen={fmt_days(avg_delay, 1)}"),
        metric_label_value("Capacite", f"utilisation max={fmt_ratio_pct(max_utilization)} ; incertitude={fmt_pct(capacity_risk * 100.0)}"),
        metric_label_value("Stock", f"jours a stock zero={stock_zero_days} ; part observee={fmt_ratio_pct(stock_zero_probability)}"),
        metric_label_value("Fiabilite", f"perte moyenne={fmt_ratio_pct(loss_mean, 2)} ; score={fmt_pct(reliability_risk * 100.0)}"),
        metric_label_value("Items couverts", item_text),
    ]

    return {
        "title": f"Qualite de lecture - {scope_id}",
        "summary_lines": summary_lines,
        "score": round(global_uncertainty, 6),
        "confidence": round(global_confidence, 6),
        "status": status,
        "status_label": status_label,
        "color": color,
        "dominant_dimension": dominant_dimension,
        "dominant_score": round(dominant_score, 6),
        "lead_score": round(delay_risk, 6),
        "capacity_score": round(capacity_risk, 6),
        "stock_score": round(stock_risk, 6),
        "reliability_score": round(reliability_risk, 6),
        "row_counts": {
            "orders": len(visible_order_rows),
            "stock": len(visible_stock_rows),
            "capacity": len(visible_capacity_rows),
            "shipments": len(visible_shipment_rows),
        },
    }


def clamp01(value: float | None) -> float:
    if value is None or math.isnan(value):
        return 0.0
    return max(0.0, min(1.0, float(value)))


def risk_level(score: float) -> str:
    if score >= 0.50:
        return "fort"
    if score >= 0.25:
        return "modere"
    return "faible"


def render_supplier_risk_prediction_html(
    node_id: str,
    *,
    order_rows: list[dict[str, str]],
    stock_rows: list[dict[str, str]],
    capacity_rows: list[dict[str, str]],
    shipment_rows: list[dict[str, str]],
    nominal_rows: list[dict[str, str]],
    criticality_row: dict[str, str] | None,
    economic_policy: dict[str, Any],
    item_labels: dict[str, str],
) -> str:
    visible_order_rows = [
        row for row in order_rows
        if not is_simulation_hidden_item(str(row.get("item_id") or ""))
    ]
    visible_stock_rows = [
        row for row in stock_rows
        if not is_simulation_hidden_item(str(row.get("item_id") or ""))
    ]
    visible_capacity_rows = [
        row for row in capacity_rows
        if not is_simulation_hidden_item(str(row.get("item_id") or ""))
    ]
    visible_shipment_rows = [
        row for row in shipment_rows
        if not is_simulation_hidden_item(str(row.get("item_id") or ""))
    ]
    visible_nominal_rows = [
        row for row in nominal_rows
        if not is_simulation_hidden_item(str(row.get("item_id") or ""))
    ]

    comparable_lead_pairs: list[tuple[float, float]] = []
    for row in visible_order_rows:
        planned = planned_procurement_lead_days(row)
        effective = effective_procurement_lead_days(row)
        if planned is None or effective is None or planned <= 0 or effective < 0:
            continue
        comparable_lead_pairs.append((float(planned), float(effective)))
    effective_leads = [effective for _, effective in comparable_lead_pairs]
    lead_cv = coefficient_of_variation(effective_leads)
    late_pairs = [(planned, effective) for planned, effective in comparable_lead_pairs if effective > planned + 1e-9]
    delay_probability = len(late_pairs) / len(comparable_lead_pairs) if comparable_lead_pairs else None
    avg_delay_days = (
        statistics.mean(max(0.0, effective - planned) for planned, effective in comparable_lead_pairs)
        if comparable_lead_pairs
        else None
    )

    capacity_utils = finite_numeric_values((row.get("utilization") for row in visible_capacity_rows))
    max_util = max(capacity_utils) if capacity_utils else None
    avg_active_util_values = [value for value in capacity_utils if value > 1e-9]
    avg_active_util = statistics.mean(avg_active_util_values) if avg_active_util_values else None
    util_cv = coefficient_of_variation(capacity_utils)

    stock_values = finite_numeric_values((row.get("stock_end_of_day") for row in visible_stock_rows))
    stock_cv = coefficient_of_variation(stock_values)
    stock_zero_probability = (
        sum(1 for value in stock_values if value <= 1e-9) / len(stock_values)
        if stock_values
        else None
    )
    stock_p10 = percentile(stock_values, 0.10) if stock_values else None

    reliability_values = finite_numeric_values((row.get("reliability") for row in visible_shipment_rows))
    reliability_mean = statistics.mean(reliability_values) if reliability_values else None
    reliability_cv = coefficient_of_variation(reliability_values)
    loss_ratios: list[float] = []
    for row in visible_shipment_rows:
        pulled = to_float(row.get("pulled_qty"))
        shipped = to_float(row.get("shipped_qty"))
        if pulled is None or shipped is None or math.isnan(pulled) or math.isnan(shipped) or pulled <= 0:
            continue
        loss_ratios.append(max(0.0, min(1.0, (pulled - shipped) / pulled)))
    loss_mean = statistics.mean(loss_ratios) if loss_ratios else None

    local_criticality = clamp01(to_float((criticality_row or {}).get("local_criticality_score")))
    overall_criticality = clamp01(to_float((criticality_row or {}).get("overall_criticality_score")))
    observed_share = clamp01(to_float((criticality_row or {}).get("observed_sourcing_share")))
    sole_source_pairs = int(to_float((criticality_row or {}).get("sole_source_pairs")) or 0)
    shortage_events = int(to_float((criticality_row or {}).get("shortage_supported_events")) or 0)
    impact_score = max(
        overall_criticality,
        0.75 * local_criticality,
        0.60 * observed_share if sole_source_pairs > 0 else 0.35 * observed_share,
        0.25 if shortage_events > 0 else 0.0,
    )
    if impact_score <= 1e-9 and visible_nominal_rows:
        impact_score = max(0.25, max((to_float(row.get("mrp_share")) or 0.0) for row in visible_nominal_rows))
    impact_score = clamp01(impact_score)

    def confidence(row_count: int, *, has_criticality: bool = True) -> float:
        value = 0.25 + math.log1p(max(0, row_count)) / 8.0
        if not has_criticality:
            value -= 0.08
        return clamp01(min(0.95, value))

    lead_occurrence = clamp01(
        0.04
        + 0.55 * (delay_probability or 0.0)
        + 0.25 * min(1.0, (avg_delay_days or 0.0) / 30.0)
        + 0.20 * min(1.0, (lead_cv or 0.0) / 0.30)
    )
    capacity_occurrence = clamp01(
        0.03
        + 0.70 * (max_util or 0.0)
        + 0.20 * (avg_active_util or 0.0)
        + 0.10 * min(1.0, (util_cv or 0.0) / 0.30)
    )
    stock_occurrence = clamp01(
        0.03
        + 0.65 * (stock_zero_probability or 0.0)
        + (0.15 if stock_p10 is not None and stock_p10 <= 1e-9 else 0.0)
        + 0.20 * min(1.0, (stock_cv or 0.0) / 1.0)
    )
    reliability_occurrence = clamp01(
        0.02
        + 1.50 * max(0.0, 1.0 - (reliability_mean if reliability_mean is not None else 1.0))
        + 3.00 * (loss_mean or 0.0)
        + 0.20 * min(1.0, (reliability_cv or 0.0) / 0.05)
    )
    dependency_occurrence = clamp01(0.04 + 0.20 * local_criticality + (0.08 if sole_source_pairs > 0 else 0.0))
    external_enabled = bool(economic_policy.get("external_procurement_enabled"))
    external_occurrence = clamp01((0.08 + 0.20 * impact_score) if external_enabled else 0.0)

    categories = [
        {
            "category": "Delais d'appro allonges",
            "occurrence": lead_occurrence,
            "impact": impact_score,
            "confidence": confidence(len(comparable_lead_pairs), has_criticality=criticality_row is not None),
            "evidence": (
                f"retards={len(late_pairs)}/{len(comparable_lead_pairs)} ; "
                f"taux de retard={fmt_pct((delay_probability or 0.0) * 100.0)} ; "
                f"retard moyen={fmt_days(avg_delay_days, 1)} ; variabilite {uncertainty_level(lead_cv)}" if lead_cv is not None
                else f"retards={len(late_pairs)}/{len(comparable_lead_pairs)} ; donnees lead insuffisantes"
            ),
            "sensitivity": "delai: reference, +10%, +25%, +50%",
        },
        {
            "category": "Capacite fournisseur sous tension",
            "occurrence": capacity_occurrence,
            "impact": impact_score,
            "confidence": confidence(len(visible_capacity_rows), has_criticality=criticality_row is not None),
            "evidence": (
                f"util max={fmt_pct((max_util or 0.0) * 100.0)} ; "
                f"util active={fmt_pct((avg_active_util or 0.0) * 100.0)} ; "
                f"variabilite {uncertainty_level(util_cv)}" if util_cv is not None
                else f"util max={fmt_pct((max_util or 0.0) * 100.0)} ; donnees capacite limitees"
            ),
            "sensitivity": "capacite: reference, -10%, -20%, -30%, -50%",
        },
        {
            "category": "Fragilite stock fournisseur",
            "occurrence": stock_occurrence,
            "impact": impact_score,
            "confidence": confidence(len(visible_stock_rows), has_criticality=criticality_row is not None),
            "evidence": (
                f"part jours stock zero={fmt_pct((stock_zero_probability or 0.0) * 100.0)} ; "
                f"stock bas observe={fmt_qty(stock_p10, 1)} ; variabilite {uncertainty_level(stock_cv)}" if stock_cv is not None
                else f"part jours stock zero={fmt_pct((stock_zero_probability or 0.0) * 100.0)} ; donnees stock limitees"
            ),
            "sensitivity": "stock: reference, -25%, -50%, -75%, zero",
        },
        {
            "category": "Fiabilite / qualite",
            "occurrence": reliability_occurrence,
            "impact": impact_score,
            "confidence": confidence(len(visible_shipment_rows), has_criticality=criticality_row is not None),
            "evidence": (
                f"reliability moyenne={fmt_pct((reliability_mean or 0.0) * 100.0)} ; "
                f"perte moyenne={fmt_pct((loss_mean or 0.0) * 100.0, 2)} ; "
                f"variabilite {uncertainty_level(reliability_cv)}" if reliability_cv is not None
                else f"reliability moyenne={fmt_pct((reliability_mean or 0.0) * 100.0)} ; donnees qualite limitees"
            ),
            "sensitivity": "fiabilite: reference, -1%, -3%, -5%",
        },
        {
            "category": "Dependance fournisseur",
            "occurrence": dependency_occurrence,
            "impact": max(impact_score, local_criticality),
            "confidence": confidence(1 if criticality_row else 0, has_criticality=criticality_row is not None),
            "evidence": (
                f"local={local_criticality:.3f} ; overall={overall_criticality:.3f} ; "
                f"sourcing={fmt_pct(observed_share * 100.0)} ; sole_source={sole_source_pairs}"
            ),
            "sensitivity": "tester perte fournisseur, double source ou baisse de part",
        },
        {
            "category": "Contrainte appro amont fournisseur",
            "occurrence": external_occurrence,
            "impact": impact_score,
            "confidence": confidence(len(visible_nominal_rows), has_criticality=criticality_row is not None),
            "evidence": (
                "appro amont fournisseur actif dans la politique" if external_enabled
                else "appro amont fournisseur non actif pour ce diagnostic passif"
            ),
            "sensitivity": "appro amont: capacite -25/-50/-75% ; delai +25/+50/+100%",
        },
    ]
    for row in categories:
        row["expected"] = clamp01(float(row["occurrence"]) * float(row["impact"]) * float(row["confidence"]))
    categories.sort(key=lambda row: float(row["expected"]), reverse=True)

    rows_html = []
    for row in categories:
        expected = float(row["expected"])
        rows_html.append(
            "<tr>"
            f"<td>{html.escape(str(row['category']))}</td>"
            f"<td>{fmt_pct(float(row['occurrence']) * 100.0)}</td>"
            f"<td>{fmt_pct(float(row['impact']) * 100.0)}</td>"
            f"<td>{fmt_pct(float(row['confidence']) * 100.0)}</td>"
            f"<td>{fmt_pct(expected * 100.0)}</td>"
            f"<td>{html.escape(risk_level(expected))}</td>"
            f"<td>{html.escape(str(row['evidence']))}</td>"
            f"<td>{html.escape(str(row['sensitivity']))}</td>"
            "</tr>"
        )

    sensitivity_rows = [
        ("1", "Capacite fournisseur", "reference, -10%, -20%, -30%, -50%", "tester le seuil de saturation sans changer la reference du run"),
        ("2", "Stock fournisseur", "reference, -25%, -50%, -75%, zero", "identifier le stock minimum qui preserve service, backlog et cibles"),
        ("3", "Delai matiere", "reference, +25%, +50%, +100%", "mesurer la sensibilite aux retards et derives de delai"),
        ("4", "Fiabilite / qualite", "reference, -1%, -3%, -5%", "simuler pertes, retours, release qualite et quantite utile"),
        ("5", "Appro amont fournisseur", "capacite -25/-50/-75% ; delai +25/+50/+100%", "contraindre l'appro amont qui reconstitue le stock fournisseur"),
    ]
    sensitivity_html = "".join(
        "<tr>"
        f"<td>{html.escape(priority)}</td>"
        f"<td>{html.escape(parameter)}</td>"
        f"<td>{html.escape(grid)}</td>"
        f"<td>{html.escape(reason)}</td>"
        "</tr>"
        for priority, parameter, grid, reason in sensitivity_rows
    )

    return "".join(
        [
            "<div class=\"factoryHtmlPanelContent orderLedgerPanelContent\">",
            f"<div class=\"orderLedgerTextHeader\">{html.escape(node_id)} - lecture predictive des tensions fournisseur</div>",
            "<div class=\"orderLedgerStatus\">Lecture seule: ce bloc estime une menace fournisseur probable, mais ne relance pas la simulation et ne modifie pas la baseline.</div>",
            "<div class=\"orderLedgerStatus\">Score menace = tension metier normalisee. Incertitude = confiance dans cette lecture. L'action finale se lit dans la matrice niveau de menace x confiance.</div>",
            "<div class=\"orderLedgerStatus\">Principe: score menace x impact local x confiance donne une priorite de surveillance, puis la grille propose les premiers tests a lancer.</div>",
            "<div class=\"orderLedgerSectionTitle\">Introduction - etude de sensibilite recommandee</div>",
            "<div class=\"kpiFormulaTableWrap\"><table class=\"kpiFormulaTable\">",
            "<thead><tr><th>Priorite</th><th>Parametre</th><th>Grille proposee</th><th>Objectif</th></tr></thead>",
            f"<tbody>{sensitivity_html}</tbody>",
            "</table></div>",
            "<div class=\"orderLedgerSectionTitle\">Prediction passive par categorie</div>",
            "<div class=\"orderLedgerFrame\">",
            "<div class=\"orderLedgerTableWrap\" tabindex=\"0\" aria-label=\"Tableau de prediction passive des tensions fournisseur avec defilement horizontal natif en bas.\">",
            "<table class=\"orderLedgerTable orderLedgerWideTable\">",
            "<colgroup>"
            "<col style=\"width:175px\"><col style=\"width:105px\"><col style=\"width:95px\"><col style=\"width:105px\">"
            "<col style=\"width:105px\"><col style=\"width:85px\"><col style=\"width:320px\"><col style=\"width:260px\">"
            "</colgroup>",
            "<thead><tr><th>Categorie</th><th>Score menace</th><th>Impact</th><th>Confiance</th><th>Priorite estimee</th><th>Niveau</th><th>Signaux observes</th><th>Test utile</th></tr></thead>",
            f"<tbody>{''.join(rows_html)}</tbody>",
            "</table>",
            "</div>",
            "</div>",
            "</div>",
        ]
    )


def render_supplier_nominal_parameters_html(
    node_id: str,
    nominal_rows: list[dict[str, str]],
    item_labels: dict[str, str],
) -> str:
    visible_rows = [
        row for row in nominal_rows
        if not is_simulation_hidden_item(str(row.get("item_id") or ""))
    ]
    if not visible_rows:
        return (
            "<div class=\"factoryHtmlPanelContent orderLedgerPanelContent\">"
            f"<div class=\"orderLedgerTextHeader\">{html.escape(node_id)} - references fournisseur</div>"
            "<div class=\"panelEmptyState\">Aucune reference fournisseur disponible pour ce noeud.</div>"
            "</div>"
        )

    sorted_rows = sorted(
        visible_rows,
        key=lambda row: (
            str(row.get("dst_node_id") or ""),
            str(row.get("item_id") or ""),
            str(row.get("edge_id") or ""),
        ),
    )
    rows_html: list[str] = []
    for row in sorted_rows:
        item_id = str(row.get("item_id") or "")
        item_label = item_labels.get(item_id, compact_item_label(item_id))
        dst_node_id = str(row.get("dst_node_id") or "n/a")
        uom = str(row.get("uom") or "n/a")
        cap_scale = to_float(row.get("applied_capacity_scale"))
        cap_scale_text = f"x{fmt_qty(cap_scale, 1)}" if cap_scale is not None and not math.isnan(cap_scale) else "n/a"
        neutral_cap = to_float(row.get("neutral_capacity_floor_qty_per_day"))
        tested_cap = to_float(row.get("tested_capacity_floor_qty_per_day"))
        displayed_cap_floor = tested_cap if tested_cap is not None and not math.isnan(tested_cap) and tested_cap > 0.0 else neutral_cap
        neutral_cap_scale = to_float(row.get("neutral_capacity_scale_if_nominal"))
        neutral_cap_scale_text = (
            f"x{fmt_qty(neutral_cap_scale, 1)}"
            if neutral_cap_scale is not None and not math.isnan(neutral_cap_scale) and neutral_cap_scale > 0.0
            else "n/a"
        )
        current_headroom = to_float(row.get("current_capacity_headroom_vs_tested_floor"))
        if current_headroom is None or math.isnan(current_headroom):
            current_headroom = to_float(row.get("current_capacity_headroom_factor"))
        current_headroom_text = (
            f"x{fmt_qty(current_headroom, 1)}"
            if current_headroom is not None and not math.isnan(current_headroom)
            else "n/a"
        )
        industrial_cap = to_float(row.get("industrial_nominal_capacity_qty_per_day"))
        industrial_util = to_float(row.get("industrial_peak_utilization_if_nominal"))
        industrial_target = to_float(row.get("industrial_capacity_target_utilization"))
        industrial_headroom = to_float(row.get("current_capacity_headroom_vs_industrial_nominal"))
        industrial_target_text = (
            fmt_pct(industrial_target * 100.0)
            if industrial_target is not None and not math.isnan(industrial_target)
            else "n/a"
        )
        industrial_headroom_text = (
            f"x{fmt_qty(industrial_headroom, 1)}"
            if industrial_headroom is not None and not math.isnan(industrial_headroom)
            else "n/a"
        )
        upstream_cap = to_float(row.get("external_procurement_nominal_capacity_qty_per_day"))
        upstream_need = to_float(row.get("external_procurement_daily_need_qty"))
        upstream_target = to_float(row.get("external_procurement_target_utilization"))
        upstream_seed = to_float(row.get("external_procurement_initial_pipeline_seed_qty"))
        upstream_target_text = (
            fmt_pct(upstream_target * 100.0)
            if upstream_target is not None and not math.isnan(upstream_target) and upstream_target > 0.0
            else "n/a"
        )
        stock_scale = to_float(row.get("neutral_opening_stock_scale"))
        stock_scale_text = (
            f"x{fmt_qty(stock_scale, 2)}"
            if stock_scale is not None and not math.isnan(stock_scale)
            else "n/a"
        )
        util_pct = to_float(row.get("max_capacity_utilization"))
        otif = to_float(row.get("nominal_reliability_otif"))
        mrp_share = to_float(row.get("mrp_share"))
        lead_title = " | ".join(
            part
            for part in [
                f"type={row.get('lead_time_type') or 'n/a'}",
                f"source={row.get('lead_time_source') or 'n/a'}",
                f"stages={row.get('lead_time_stages') or 'n/a'}",
            ]
            if part
        )
        reliability_title = f"source={row.get('reliability_source') or 'n/a'}"
        capacity_title = (
            f"basis={row.get('capacity_basis') or 'n/a'} | "
            f"explicit={fmt_qty(row.get('explicit_capacity_qty_per_day'), 1)} | "
            f"process={fmt_qty(row.get('process_capacity_qty_per_day'), 1)} | "
            f"downstream_req={fmt_qty(row.get('downstream_requirement_qty_per_day'), 1)}"
        )
        neutral_capacity_title = (
            f"Seuil neutre: {row.get('capacity_floor_basis') or 'n/a'} | "
            f"cap min observee={fmt_qty(neutral_cap, 1)} | "
            f"profil industriel={row.get('industrial_capacity_profile') or 'n/a'} | "
            f"scale actuel={cap_scale_text} | "
            f"capacite actuelle={fmt_qty(row.get('effective_capacity_qty_per_day'), 1)}"
        )
        upstream_capacity_title = (
            "Contrainte appro amont fournisseur: besoin journalier baseline / taux cible; "
            f"besoin={fmt_qty(upstream_need, 1)}/j | "
            f"profil={row.get('external_procurement_capacity_profile') or 'n/a'} | "
            f"base={row.get('external_procurement_capacity_basis') or 'n/a'} | "
            f"pipeline ouvert={fmt_qty(upstream_seed, 1)}"
        )
        neutral_stock_title = (
            "Stock initial minimal analytique pour garder les expeditions observees faisables; "
            f"reductible={fmt_qty(row.get('neutral_opening_stock_reducible_qty'), 1)}"
        )
        cells = [
            (item_label, f"Item complet: {item_label} ({item_id})"),
            (dst_node_id, f"Destination: {dst_node_id} | edge={row.get('edge_id') or 'n/a'}"),
            (uom, ""),
            (fmt_qty(row.get("simulated_opening_stock_qty"), 1), "stock source au demarrage simule"),
            (fmt_qty(row.get("neutral_opening_stock_floor_qty"), 1), neutral_stock_title),
            (stock_scale_text, neutral_stock_title),
            (fmt_qty(row.get("effective_capacity_qty_per_day"), 1), capacity_title),
            (fmt_qty(industrial_cap, 1), neutral_capacity_title),
            (industrial_target_text, neutral_capacity_title),
            (fmt_qty(upstream_cap, 1), upstream_capacity_title),
            (upstream_target_text, upstream_capacity_title),
            (fmt_days(row.get("external_procurement_lead_days"), 1), upstream_capacity_title),
            (fmt_qty(upstream_seed, 1), upstream_capacity_title),
            (fmt_pct((industrial_util or 0.0) * 100.0) if industrial_util is not None and not math.isnan(industrial_util) else "n/a", neutral_capacity_title),
            (industrial_headroom_text, neutral_capacity_title),
            (fmt_qty(displayed_cap_floor, 1), neutral_capacity_title),
            (neutral_cap_scale_text, neutral_capacity_title),
            (current_headroom_text, neutral_capacity_title),
            (str(row.get("capacity_basis") or "n/a"), capacity_title),
            (fmt_pct((util_pct or 0.0) * 100.0) if util_pct is not None and not math.isnan(util_pct) else "n/a", "utilisation capacite max observee"),
            (fmt_days(row.get("planned_lead_time_days"), 1), lead_title),
            (fmt_pct((otif or 0.0) * 100.0) if otif is not None and not math.isnan(otif) else "n/a", reliability_title),
            (fmt_pct((mrp_share or 0.0) * 100.0) if mrp_share is not None and not math.isnan(mrp_share) else "n/a", "part de sourcing MRP nominale"),
            (fmt_qty(row.get("total_shipped_qty"), 1), "quantite totale expediee sur le run"),
        ]
        numeric_columns = set(range(3, 18)) | {19, 20, 21, 22, 23}
        row_tds: list[str] = []
        for idx, (value, title) in enumerate(cells):
            cell_class = "num" if idx in numeric_columns else ""
            title_attr = f' title="{html.escape(str(title), quote=True)}"' if title else ""
            row_tds.append(f'<td class="{cell_class}"{title_attr}>{html.escape(str(value))}</td>')
        rows_html.append("<tr>" + "".join(row_tds) + "</tr>")

    headers = [
        "Item",
        "Destination",
        "Unite",
        "Stock ouv.",
        "Stock minimum teste",
        "Facteur stock",
        "Cap actuelle/j",
        "Cap cible/j",
        "Taux cible",
        "Cap amont/j",
        "Taux amont cible",
        "Delai amont",
        "Appro amont deja lancee",
        "Util pic cible",
        "Marge cible",
        "Cap min sans degradation/j",
        "Facteur cap min",
        "Marge actuelle",
        "Reference capacite",
        "Util max",
        "Delai prev.",
        "OTIF",
        "Part MRP",
        "Expedie total",
    ]
    table_header = "".join(f"<th>{html.escape(label)}</th>" for label in headers)
    table_cols = "".join(
        f"<col style=\"width:{width}px\">"
        for width in [
            95, 110, 70, 115, 125, 95, 130, 125, 90, 125, 95, 105,
            135, 105, 115, 135, 95, 120, 175, 95, 105, 90, 95, 130,
        ]
    )
    return "".join(
        [
            "<div class=\"factoryHtmlPanelContent orderLedgerPanelContent\">",
            f"<div class=\"orderLedgerTextHeader\">{html.escape(node_id)} - references fournisseur</div>",
            f"<div class=\"orderLedgerStatus\">Lignes fournisseur affichees: {len(sorted_rows)}. Cap actuelle/j = limite utilisee par le run actif; Cap cible/j = pic observe / taux cible; Cap min sans degradation/j = plus petite capacite testee qui conserve le service du run.</div>",
            "<div class=\"orderLedgerStatus\">Profils cible: matiere qualifiee ~= 70%, delai long ~= 65%, packaging qualifie ~= 75%. Cap amont/j contraint l'appro amont fournisseur avec le meme taux cible; Appro amont deja lancee = commandes en route au demarrage.</div>",
            "<div class=\"orderLedgerFrame\">",
            "<div class=\"orderLedgerTableWrap\" tabindex=\"0\" aria-label=\"Tableau des parametres nominaux fournisseur avec defilement horizontal natif en bas.\">",
            "<table class=\"orderLedgerTable orderLedgerWideTable\">",
            f"<colgroup>{table_cols}</colgroup>",
            f"<thead><tr>{table_header}</tr></thead>",
            f"<tbody>{''.join(rows_html)}</tbody>",
            "</table>",
            "</div>",
            "</div>",
            "</div>",
        ]
    )


def render_factory_nominal_capacities_html(
    node_id: str,
    capacity_rows: list[dict[str, str]],
    item_labels: dict[str, str],
) -> str:
    visible_rows = [
        row for row in capacity_rows
        if not is_simulation_hidden_item(str(row.get("output_item_id") or ""))
    ]
    if not visible_rows:
        return (
            "<div class=\"factoryHtmlPanelContent orderLedgerPanelContent\">"
            f"<div class=\"orderLedgerTextHeader\">{html.escape(node_id)} - references capacite usine</div>"
            "<div class=\"panelEmptyState\">Aucune reference capacite usine disponible pour ce noeud.</div>"
            "</div>"
        )

    rows_html: list[str] = []
    for row in sorted(visible_rows, key=lambda r: (str(r.get("output_item_id") or ""), str(r.get("process_id") or ""))):
        item_id = str(row.get("output_item_id") or "")
        item_label = item_labels.get(item_id, compact_item_label(item_id))
        target_util = to_float(row.get("industrial_capacity_target_utilization"))
        peak_util_indus = to_float(row.get("industrial_peak_utilization_if_nominal"))
        current_max_util = to_float(row.get("current_max_utilization"))
        headroom = to_float(row.get("current_capacity_headroom_vs_industrial_nominal"))
        current_capacity = to_float(row.get("current_capacity_qty_per_day"))
        industrial_capacity = to_float(row.get("industrial_nominal_capacity_qty_per_day"))
        current_capacity_text = (
            fmt_qty(current_capacity, 1)
            if current_capacity is not None and not math.isnan(current_capacity) and current_capacity > 0.0
            else "non modelisee"
        )
        headroom_text = (
            f"x{fmt_qty(headroom, 2)}"
            if headroom is not None and not math.isnan(headroom)
            else "n/a"
        )
        title = (
            f"profil={row.get('industrial_capacity_profile') or 'n/a'} | "
            f"source={row.get('capacity_source') or 'n/a'} | "
            f"mode={row.get('current_capacity_limit_mode') or 'n/a'}"
        )
        cells = [
            (item_label, f"Item complet: {item_label} ({item_id})"),
            (str(row.get("process_id") or "n/a"), title),
            (str(row.get("uom") or "n/a"), ""),
            (current_capacity_text, title),
            (fmt_qty(industrial_capacity, 1), title),
            (fmt_pct((target_util or 0.0) * 100.0) if target_util is not None and not math.isnan(target_util) else "n/a", title),
            (fmt_pct((peak_util_indus or 0.0) * 100.0) if peak_util_indus is not None and not math.isnan(peak_util_indus) else "n/a", title),
            (headroom_text, title),
            (fmt_qty(row.get("max_actual_qty_per_day"), 1), "pic journalier produit observe"),
            (fmt_qty(row.get("total_actual_qty"), 1), "production totale observee"),
            (fmt_pct((current_max_util or 0.0) * 100.0) if current_max_util is not None and not math.isnan(current_max_util) else "n/a", "utilisation max de la capacite actuelle"),
            (str(row.get("capacity_binding_days") or "0"), "jours ou la capacite usine limite l'execution"),
            (str(row.get("input_shortage_days") or "0"), "jours ou les intrants limitent l'execution"),
            (str(row.get("lot_policy_mode") or "n/a"), "politique de lot observee"),
        ]
        numeric_columns = {3, 4, 5, 6, 7, 8, 9, 10, 11, 12}
        row_tds: list[str] = []
        for idx, (value, cell_title) in enumerate(cells):
            cell_class = "num" if idx in numeric_columns else ""
            title_attr = f' title="{html.escape(str(cell_title), quote=True)}"' if cell_title else ""
            row_tds.append(f'<td class="{cell_class}"{title_attr}>{html.escape(str(value))}</td>')
        rows_html.append("<tr>" + "".join(row_tds) + "</tr>")

    headers = [
        "Output",
        "Process",
        "Unite",
        "Cap actuelle/j",
        "Cap cible/j",
        "Taux cible",
        "Util pic cible",
        "Marge actuelle",
        "Pic produit/j",
        "Produit total",
        "Util max actuelle",
        "Jours capacite",
        "Jours intrants",
        "Lot",
    ]
    table_cols = "".join(
        f"<col style=\"width:{width}px\">"
        for width in [110, 140, 80, 130, 130, 95, 105, 115, 120, 125, 120, 105, 105, 95]
    )
    return "".join(
        [
            "<div class=\"factoryHtmlPanelContent orderLedgerPanelContent\">",
            f"<div class=\"orderLedgerTextHeader\">{html.escape(node_id)} - references capacite usine</div>",
            "<div class=\"orderLedgerStatus\">Cap actuelle/j = limite du JSON actif; Cap cible/j = pic journalier produit / taux cible pharma. Le taux cible par defaut est 70% pour une usine GMP multi-produits ou un site interne semi-fini.</div>",
            "<div class=\"orderLedgerStatus\">Pour les usines, appliquer directement la capacite cible peut changer le cadencement interne; elle est donc affichee comme lecture de sensibilite, pas comme remplacement automatique de la baseline.</div>",
            "<div class=\"orderLedgerFrame\">",
            "<div class=\"orderLedgerTableWrap\" tabindex=\"0\" aria-label=\"Tableau des capacites nominales usine avec defilement horizontal natif en bas.\">",
            "<table class=\"orderLedgerTable orderLedgerWideTable\">",
            f"<colgroup>{table_cols}</colgroup>",
            f"<thead><tr>{''.join(f'<th>{html.escape(label)}</th>' for label in headers)}</tr></thead>",
            f"<tbody>{''.join(rows_html)}</tbody>",
            "</table>",
            "</div>",
            "</div>",
            "</div>",
        ]
    )
