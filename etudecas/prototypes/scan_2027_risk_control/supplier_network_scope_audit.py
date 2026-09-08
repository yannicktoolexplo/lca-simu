#!/usr/bin/env python3
"""Build an evidence ledger for the supplier lanes that may be stress-tested.

This audit does not rank supplier risk.  It separates structural graph lanes,
opening purchase orders observed in the 2025 snapshot, and flows executed by a
reference simulation.  A lane with neither order-book nor simulated-flow
evidence is explicitly marked non-exercised instead of being called robust.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import defaultdict, deque
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_GRAPH = (
    REPO_ROOT
    / "etudecas"
    / "simulation_prep"
    / "result"
    / "reference_baseline"
    / "_mrp_bom_tests"
    / "bom_weekly_mps_lotified_no_static_fallback_physical_floor.json"
)
DEFAULT_ORDER_AUDIT = (
    REPO_ROOT
    / "etudecas"
    / "analysis"
    / "from_simulation"
    / "result"
    / "audit_order_book_vs_source"
    / "source_open_orders_audit.csv"
)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Audit supplier-lane evidence before sensitivity studies."
    )
    parser.add_argument("--graph", type=Path, default=DEFAULT_GRAPH)
    parser.add_argument("--baseline-shipments", type=Path)
    parser.add_argument(
        "--order-audit",
        type=Path,
        help="Carnet 2025 normalisé; seules les voies valid_exact_lane=True sont retenues.",
    )
    parser.add_argument("--local-ranking", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser.parse_args(argv)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _text(value: Any) -> str:
    return str(value or "").strip()


def _read_csv(path: Path | None) -> list[dict[str, str]]:
    if path is None or not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def _write_csv(path: Path, rows: Iterable[Mapping[str, Any]]) -> None:
    materialized = [dict(row) for row in rows]
    fields: list[str] = []
    for row in materialized:
        for key in row:
            if key not in fields:
                fields.append(key)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore")
        if fields:
            writer.writeheader()
            writer.writerows(materialized)


def _lane_key(supplier_id: str, item_id: str, dst_node_id: str) -> tuple[str, str, str]:
    return _text(supplier_id), _text(item_id), _text(dst_node_id)


def _target_products(graph: Mapping[str, Any]) -> set[str]:
    products: set[str] = set()
    for scenario in graph.get("scenarios") or []:
        for row in scenario.get("demand") or []:
            item_id = _text(row.get("item_id"))
            if item_id:
                products.add(item_id)
    return products


def _dependency_transitions(graph: Mapping[str, Any]) -> dict[tuple[str, str], set[tuple[str, str]]]:
    transitions: dict[tuple[str, str], set[tuple[str, str]]] = defaultdict(set)
    for node in graph.get("nodes") or []:
        node_id = _text(node.get("id"))
        for process in node.get("processes") or []:
            outputs = [_text(row.get("item_id")) for row in process.get("outputs") or []]
            for input_row in process.get("inputs") or []:
                input_id = _text(input_row.get("item_id"))
                for output_id in outputs:
                    if input_id and output_id:
                        transitions[(node_id, input_id)].add((node_id, output_id))
    for edge in graph.get("edges") or []:
        src = _text(edge.get("from"))
        dst = _text(edge.get("to"))
        for item_id in edge.get("items") or []:
            item = _text(item_id)
            if src and dst and item:
                transitions[(src, item)].add((dst, item))
    return transitions


def downstream_products(
    start: tuple[str, str],
    transitions: Mapping[tuple[str, str], set[tuple[str, str]]],
    products: set[str],
) -> list[str]:
    queue: deque[tuple[str, str]] = deque([start])
    seen: set[tuple[str, str]] = set()
    found: set[str] = set()
    while queue:
        pair = queue.popleft()
        if pair in seen:
            continue
        seen.add(pair)
        if pair[1] in products:
            found.add(pair[1])
        for target in transitions.get(pair, set()):
            if target not in seen:
                queue.append(target)
    return sorted(item.removeprefix("item:") for item in found)


def graph_supplier_lanes(graph: Mapping[str, Any]) -> list[dict[str, Any]]:
    node_types = {
        _text(node.get("id")): _text(node.get("type")).lower()
        for node in graph.get("nodes") or []
    }
    rows: list[dict[str, Any]] = []
    for edge in graph.get("edges") or []:
        supplier = _text(edge.get("from"))
        if "supplier" not in node_types.get(supplier, "") and not supplier.startswith("SDC-VD"):
            continue
        attrs = edge.get("attrs") if isinstance(edge.get("attrs"), dict) else {}
        terms = edge.get("order_terms") if isinstance(edge.get("order_terms"), dict) else {}
        lead = edge.get("lead_time") if isinstance(edge.get("lead_time"), dict) else {}
        for item_id in edge.get("items") or []:
            rows.append(
                {
                    "supplier_id": supplier,
                    "item_id": _text(item_id),
                    "dst_node_id": _text(edge.get("to")),
                    "edge_id": _text(edge.get("id")),
                    "planned_lead_days": _float(lead.get("mean")),
                    "standard_order_qty": _float(attrs.get("standard_order_qty")),
                    "uom": _text(attrs.get("standard_order_uom") or terms.get("quantity_unit")),
                    "source_workbook": _text(attrs.get("source_workbook")),
                    "source_product_code": _text(attrs.get("product_code")),
                }
            )
    return sorted(rows, key=lambda row: _lane_key(row["supplier_id"], row["item_id"], row["dst_node_id"]))


def observed_order_rows(graph: Mapping[str, Any]) -> list[dict[str, Any]]:
    meta = graph.get("meta") if isinstance(graph.get("meta"), dict) else {}
    payload = meta.get("opening_open_orders") if isinstance(meta.get("opening_open_orders"), dict) else {}
    source_file = _text(payload.get("source_file"))
    snapshot_date = _text(payload.get("snapshot_date"))
    rows: list[dict[str, Any]] = []
    for raw in payload.get("rows") or []:
        if _text(raw.get("order_type")) != "purchase_open_order":
            continue
        rows.append(
            {
                "evidence_kind": "observed_open_order_snapshot",
                "actual_delivery_proof": False,
                "lot_identity_kind": "source_row_technical_not_business_lot",
                "source_file": source_file,
                "snapshot_date": snapshot_date,
                "source_row": raw.get("source_row", ""),
                "supplier_id": _text(raw.get("src_node_id")),
                "item_id": _text(raw.get("item_id")),
                "dst_node_id": _text(raw.get("dst_node_id")),
                "planning_element": _text(raw.get("planning_element")),
                "quantity": _float(raw.get("quantity")),
                "uom": _text(raw.get("uom")),
                "planned_physical_delivery_day": raw.get("physical_delivery_day", ""),
                "planned_usable_day": raw.get("usable_day", ""),
                "planned_physical_delivery_date": _text(raw.get("physical_delivery_date")),
                "planned_usable_date": _text(raw.get("usable_date")),
                "planned_receipt_release_days": raw.get("receipt_release_days", ""),
            }
        )
    return rows


def observed_order_rows_from_audit(
    raw_rows: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Normalise les lignes d'achat dont la correspondance au graphe est validée."""
    rows: list[dict[str, Any]] = []
    for raw in raw_rows:
        if _text(raw.get("order_type")) != "purchase_open_order":
            continue
        if _text(raw.get("valid_exact_lane")).lower() not in {"true", "1", "yes"}:
            continue
        source_quantity = _float(raw.get("quantity"))
        source_uom = _text(raw.get("uom"))
        standard_quantity = _float(raw.get("qty_standard_uom"), source_quantity)
        standard_uom = _text(raw.get("standard_order_uom")) or source_uom
        rows.append(
            {
                "evidence_kind": "observed_open_order_snapshot",
                "actual_delivery_proof": False,
                "lot_identity_kind": "source_row_technical_not_business_lot",
                "source_file": "Extract_En_cours.xlsx",
                "snapshot_date": "2025-01-01",
                "source_row": raw.get("source_row", ""),
                "supplier_id": _text(raw.get("src_node_id")),
                "item_id": _text(raw.get("item_id")),
                "dst_node_id": _text(raw.get("dst_node_id")),
                "planning_element": _text(raw.get("planning_element")),
                "quantity": standard_quantity,
                "uom": standard_uom,
                "source_quantity": source_quantity,
                "source_uom": source_uom,
                "quantity_normalization": (
                    "direct"
                    if not source_uom or source_uom == standard_uom
                    else f"{source_uom}_to_{standard_uom}"
                ),
                "planned_physical_delivery_day": raw.get("graph_physical_delivery_day", ""),
                "planned_usable_day": raw.get("graph_usable_day", ""),
                "planned_physical_delivery_date": _text(raw.get("physical_delivery_date")),
                "planned_usable_date": _text(raw.get("usable_date")),
                "planned_receipt_release_days": raw.get("receipt_release_days", ""),
            }
        )
    return rows


def build_scope(
    graph: Mapping[str, Any],
    shipments: Sequence[Mapping[str, Any]],
    local_ranking: Sequence[Mapping[str, Any]],
    order_ledger: Sequence[Mapping[str, Any]] | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    lanes = graph_supplier_lanes(graph)
    order_ledger = list(order_ledger) if order_ledger is not None else observed_order_rows(graph)
    orders: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in order_ledger:
        orders[_lane_key(row["supplier_id"], row["item_id"], row["dst_node_id"])].append(row)
    flows: dict[tuple[str, str, str], dict[str, float]] = defaultdict(
        lambda: {
            "rows": 0.0,
            "shipped": 0.0,
            "pulled": 0.0,
            "opening_rows": 0.0,
            "opening_shipped": 0.0,
        }
    )
    for row in shipments:
        key = _lane_key(row.get("src_node_id", ""), row.get("item_id", ""), row.get("dst_node_id", ""))
        shipped = max(0.0, _float(row.get("shipped_qty")))
        pulled = max(0.0, _float(row.get("pulled_qty")))
        if shipped > 1e-9 or pulled > 1e-9:
            if _text(row.get("transport_cost_basis")) == "opening_order_book":
                flows[key]["opening_rows"] += 1.0
                flows[key]["opening_shipped"] += shipped
                continue
            flows[key]["rows"] += 1.0
            flows[key]["shipped"] += shipped
            flows[key]["pulled"] += pulled
    structural_suppliers: dict[tuple[str, str], set[str]] = defaultdict(set)
    dynamic_suppliers: dict[tuple[str, str], set[str]] = defaultdict(set)
    orderbook_suppliers: dict[tuple[str, str], set[str]] = defaultdict(set)
    for lane in lanes:
        group = (_text(lane["dst_node_id"]), _text(lane["item_id"]))
        key = _lane_key(lane["supplier_id"], lane["item_id"], lane["dst_node_id"])
        structural_suppliers[group].add(_text(lane["supplier_id"]))
        lane_flow = flows.get(key, {})
        if _float(lane_flow.get("shipped")) > 1e-9 or _float(lane_flow.get("pulled")) > 1e-9:
            dynamic_suppliers[group].add(_text(lane["supplier_id"]))
        if orders.get(key):
            orderbook_suppliers[group].add(_text(lane["supplier_id"]))
    rank_by_supplier = {_text(row.get("supplier_id")): row for row in local_ranking}
    transitions = _dependency_transitions(graph)
    products = _target_products(graph)
    scope: list[dict[str, Any]] = []
    for lane in lanes:
        key = _lane_key(lane["supplier_id"], lane["item_id"], lane["dst_node_id"])
        order_rows = orders.get(key, [])
        flow = flows.get(
            key,
            {"rows": 0.0, "shipped": 0.0, "pulled": 0.0, "opening_rows": 0.0, "opening_shipped": 0.0},
        )
        has_orders = bool(order_rows)
        has_flow = flow["shipped"] > 1e-9 or flow["pulled"] > 1e-9
        if has_orders and has_flow:
            status = "simulated_and_orderbook"
            scope_rank = 1
            reading = "Voie exercée par la référence et présente dans le carnet 2025."
        elif has_flow:
            status = "simulated_only"
            scope_rank = 2
            reading = "Voie exercée par la référence; aucune ligne appariée dans le carnet fourni."
        elif has_orders:
            status = "orderbook_only"
            scope_rank = 3
            reading = "Voie présente dans le carnet 2025 mais non exercée par cette référence; replay requis."
        else:
            status = "unexercised"
            scope_rank = 4
            reading = "Aucune preuve de flux dans ces deux sources; conclusion impossible."
        ranking = rank_by_supplier.get(lane["supplier_id"], {})
        quantities = [row["quantity"] for row in order_rows]
        uoms = sorted({_text(row["uom"]) for row in order_rows if _text(row["uom"])})
        source_group = (_text(lane["dst_node_id"]), _text(lane["item_id"]))
        structural = structural_suppliers[source_group]
        dynamic = dynamic_suppliers[source_group]
        in_orderbook = orderbook_suppliers[source_group]
        evidenced = dynamic | in_orderbook
        scope.append(
            {
                **lane,
                "evidence_status": status,
                "analysis_scope_rank": scope_rank,
                "business_reading": reading,
                "baseline_positive_flow": has_flow,
                "baseline_flow_definition": "dynamic_replenishment_excluding_opening_order_book",
                "baseline_flow_rows": int(flow["rows"]),
                "baseline_shipped_qty": round(flow["shipped"], 6),
                "baseline_pulled_qty": round(flow["pulled"], 6),
                "opening_order_seed_flow_rows": int(flow["opening_rows"]),
                "opening_order_seed_shipped_qty": round(flow["opening_shipped"], 6),
                "orderbook_rows": len(order_rows),
                "orderbook_quantity": round(sum(quantities), 6),
                "orderbook_uom": "|".join(uoms),
                "structural_source_count": len(structural),
                "dynamic_reference_source_count": len(dynamic),
                "orderbook_source_count": len(in_orderbook),
                "evidenced_source_count": len(evidenced),
                "is_sole_structural_source": len(structural) == 1,
                "is_only_dynamic_source_for_item_site": has_flow and len(dynamic) == 1,
                "alternative_structural_suppliers": "|".join(
                    sorted(structural - {_text(lane["supplier_id"])})
                ),
                "first_planned_delivery_day": min((int(row["planned_physical_delivery_day"]) for row in order_rows), default=""),
                "last_planned_usable_day": max((int(row["planned_usable_day"]) for row in order_rows), default=""),
                "downstream_products": "|".join(
                    downstream_products((lane["dst_node_id"], lane["item_id"]), transitions, products)
                ),
                "legacy_local_rank_for_screening_only": _text(ranking.get("rank")),
                "legacy_system_criticality_score": _text(ranking.get("system_criticality_score")),
                "final_risk_ranking": "not_computed",
            }
        )
    status_by_key = {
        _lane_key(row["supplier_id"], row["item_id"], row["dst_node_id"]): row["evidence_status"]
        for row in scope
    }
    for row in scope:
        group = (_text(row["dst_node_id"]), _text(row["item_id"]))
        alternatives = sorted(
            structural_suppliers[group] - {_text(row["supplier_id"])}
        )
        row["alternative_evidence"] = "|".join(
            f"{supplier}:{status_by_key.get(_lane_key(supplier, row['item_id'], row['dst_node_id']), 'unknown')}"
            for supplier in alternatives
        )
    scope.sort(key=lambda row: (row["analysis_scope_rank"], _float(row.get("legacy_local_rank_for_screening_only"), 1e9), row["supplier_id"], row["item_id"]))
    lane_keys = {_lane_key(row["supplier_id"], row["item_id"], row["dst_node_id"]) for row in lanes}
    unmatched = [row for row in order_ledger if _lane_key(row["supplier_id"], row["item_id"], row["dst_node_id"]) not in lane_keys]
    findings = [
        {"finding_id": "ORDERBOOK_NOT_DELIVERY_HISTORY", "severity": "limit", "detail": "Le carnet est un instantané de commandes planifiées; il ne prouve ni réception réelle ni OTIF."},
        {"finding_id": "NO_BUSINESS_LOT_ID", "severity": "limit", "detail": "source_row est un identifiant technique, pas un numéro de commande ou de lot industriel."},
        {
            "finding_id": "RETAINED_EXACT_ORDER_ROWS_NOT_IN_GRAPH",
            "severity": "audit",
            "detail": (
                f"Parmi les {len(order_ledger)} lignes d'achat déjà retenues comme voies exactes, "
                f"{len(unmatched)} ne correspondent pas à une voie structurelle du graphe."
            ),
        },
        {"finding_id": "LEGACY_SYSTEM_SCORE", "severity": "limit", "detail": "Le classement local antérieur sert seulement à ordonner les calculs; il ne remplace pas l'impact aval simulé."},
    ]
    return scope, order_ledger, findings


def build_source_coverage(scope: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Summarise whether structural alternatives have any operational evidence."""
    groups: dict[tuple[str, str], list[Mapping[str, Any]]] = defaultdict(list)
    for row in scope:
        groups[(_text(row.get("dst_node_id")), _text(row.get("item_id")))].append(row)
    result: list[dict[str, Any]] = []
    for (dst_node_id, item_id), rows in sorted(groups.items()):
        structural = sorted({_text(row.get("supplier_id")) for row in rows})
        dynamic = sorted(
            {
                _text(row.get("supplier_id"))
                for row in rows
                if bool(row.get("baseline_positive_flow"))
            }
        )
        in_orderbook = sorted(
            {
                _text(row.get("supplier_id"))
                for row in rows
                if int(_float(row.get("orderbook_rows"))) > 0
            }
        )
        evidenced = sorted(set(dynamic) | set(in_orderbook))
        unexercised = sorted(set(structural) - set(evidenced))
        if len(structural) == 1:
            status = "sole_source_evidenced" if evidenced else "sole_source_unexercised"
        elif len(evidenced) >= 2:
            status = "multisource_multiple_suppliers_evidenced"
        elif len(evidenced) == 1:
            status = "multisource_only_one_supplier_evidenced"
        else:
            status = "multisource_no_supplier_evidenced"
        result.append(
            {
                "dst_node_id": dst_node_id,
                "item_id": item_id,
                "downstream_products": "|".join(
                    sorted(
                        {
                            product
                            for row in rows
                            for product in _text(row.get("downstream_products")).split("|")
                            if product
                        }
                    )
                ),
                "source_coverage_status": status,
                "structural_source_count": len(structural),
                "dynamic_reference_source_count": len(dynamic),
                "orderbook_source_count": len(in_orderbook),
                "evidenced_source_count": len(evidenced),
                "structural_suppliers": "|".join(structural),
                "dynamic_reference_suppliers": "|".join(dynamic),
                "orderbook_suppliers": "|".join(in_orderbook),
                "structural_suppliers_without_evidence": "|".join(unexercised),
                "qualification_and_capacity_confirmed": False,
                "business_reading": (
                    "Une source dessinée dans le graphe n'est pas une solution de secours confirmée; "
                    "qualification, capacité, délai et stock doivent être validés."
                ),
            }
        )
    return result


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    graph_path = args.graph.resolve()
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    graph = json.loads(graph_path.read_text(encoding="utf-8-sig"))
    shipments = _read_csv(args.baseline_shipments.resolve() if args.baseline_shipments else None)
    ranking = _read_csv(args.local_ranking.resolve() if args.local_ranking else None)
    order_audit_path = args.order_audit.resolve() if args.order_audit else None
    external_order_rows = _read_csv(order_audit_path)
    order_ledger = (
        observed_order_rows_from_audit(external_order_rows)
        if order_audit_path
        else observed_order_rows(graph)
    )
    scope, orders, findings = build_scope(graph, shipments, ranking, order_ledger)
    source_coverage = build_source_coverage(scope)
    raw_purchase_order_rows = [
        row
        for row in external_order_rows
        if _text(row.get("order_type")) == "purchase_open_order"
    ]
    excluded_order_rows = [
        row
        for row in raw_purchase_order_rows
        if _text(row.get("valid_exact_lane")).lower() not in {"true", "1", "yes"}
    ]
    excluded_suppliers = sorted({_text(row.get("src_node_id")) for row in excluded_order_rows})
    excluded_items = sorted({_text(row.get("item_id")) for row in excluded_order_rows})
    excluded_unmapped_division_rows = sum(
        "unmapped_division" in _text(row.get("flags")) for row in excluded_order_rows
    )
    normalized_uom_rows = [
        row
        for row in orders
        if _text(row.get("source_uom"))
        and _text(row.get("uom"))
        and _text(row.get("source_uom")) != _text(row.get("uom"))
    ]
    if order_audit_path:
        findings.append(
            {
                "finding_id": "ORDER_AUDIT_ROWS_EXCLUDED_FROM_EXACT_LANES",
                "severity": "audit",
                "detail": (
                    f"{len(excluded_order_rows)} ligne(s) d'achat sur "
                    f"{len(raw_purchase_order_rows)} ne portent pas valid_exact_lane=True; "
                    f"elles concernent {len(excluded_suppliers)} fournisseur(s) et "
                    f"{len(excluded_items)} article(s). {excluded_unmapped_division_rows} "
                    "ligne(s) relèvent notamment d'une division non représentée. Elles sont "
                    "conservées dans l'audit source mais exclues des preuves de voie."
                ),
            }
        )
        findings.append(
            {
                "finding_id": "ORDER_QUANTITIES_NORMALIZED_TO_GRAPH_UOM",
                "severity": "audit",
                "detail": (
                    f"{len(normalized_uom_rows)} ligne(s) retenue(s) ont été converties "
                    "dans l'unité standard du graphe; quantité et unité sources restent "
                    "présentes dans observed_open_order_ledger.csv."
                ),
            }
        )
    weak_multisource = [
        row
        for row in source_coverage
        if row["source_coverage_status"]
        in {
            "multisource_only_one_supplier_evidenced",
            "multisource_no_supplier_evidenced",
        }
    ]
    findings.append(
        {
            "finding_id": "STRUCTURAL_ALTERNATIVES_NOT_OPERATIONAL_PROOF",
            "severity": "limit",
            "detail": (
                f"{len(weak_multisource)} article(s)-site(s) multisources ont au plus une "
                "source étayée; qualification, capacité, délai et stock alternatif restent à confirmer."
            ),
        }
    )
    _write_csv(output_dir / "supplier_lane_scope.csv", scope)
    _write_csv(output_dir / "supplier_item_source_coverage.csv", source_coverage)
    _write_csv(output_dir / "observed_open_order_ledger.csv", orders)
    _write_csv(output_dir / "data_quality_findings.csv", findings)
    counts = {status: sum(row["evidence_status"] == status for row in scope) for status in ("simulated_and_orderbook", "simulated_only", "orderbook_only", "unexercised")}
    manifest = {
        "schema_version": "etudecas.supplier_network_scope_audit.v1",
        "status": "complete",
        "evidence_scope": "graph + observed opening-order snapshot + one simulated reference",
        "not_a_risk_ranking": True,
        "graph": str(graph_path),
        "graph_sha256": _sha256(graph_path),
        "baseline_shipments": str(args.baseline_shipments.resolve()) if args.baseline_shipments else "",
        "baseline_shipments_sha256": _sha256(args.baseline_shipments.resolve()) if args.baseline_shipments else "",
        "order_audit": str(order_audit_path) if order_audit_path else "embedded_graph_metadata",
        "order_audit_sha256": _sha256(order_audit_path) if order_audit_path else "",
        "flow_definition": "dynamic supplier replenishment; rows tagged opening_order_book are reported separately",
        "local_ranking": str(args.local_ranking.resolve()) if args.local_ranking else "",
        "lane_count": len(scope),
        "observed_order_row_count": len(orders),
        "raw_purchase_order_audit_row_count": len(raw_purchase_order_rows),
        "purchase_order_rows_excluded_from_exact_lanes": (
            len(excluded_order_rows) if order_audit_path else 0
        ),
        "purchase_order_suppliers_excluded_from_exact_lanes": len(excluded_suppliers),
        "purchase_order_items_excluded_from_exact_lanes": len(excluded_items),
        "purchase_order_rows_with_unmapped_division": excluded_unmapped_division_rows,
        "purchase_order_rows_uom_normalized": len(normalized_uom_rows),
        "counts_by_evidence_status": counts,
        "priority_lane_count": len(scope) - counts["unexercised"],
        "sole_source_lane_count": sum(bool(row["is_sole_structural_source"]) for row in scope),
        "only_dynamic_source_among_alternatives_count": sum(
            bool(row["is_only_dynamic_source_for_item_site"])
            and int(row["structural_source_count"]) > 1
            for row in scope
        ),
        "item_site_count": len(source_coverage),
        "single_source_item_site_count": sum(
            int(row["structural_source_count"]) == 1 for row in source_coverage
        ),
        "multisource_item_site_count": sum(
            int(row["structural_source_count"]) > 1 for row in source_coverage
        ),
        "multisource_only_one_supplier_evidenced_count": sum(
            row["source_coverage_status"] == "multisource_only_one_supplier_evidenced"
            for row in source_coverage
        ),
        "multisource_multiple_suppliers_evidenced_count": sum(
            row["source_coverage_status"] == "multisource_multiple_suppliers_evidenced"
            for row in source_coverage
        ),
        "multisource_no_supplier_evidenced_count": sum(
            row["source_coverage_status"] == "multisource_no_supplier_evidenced"
            for row in source_coverage
        ),
        "terminology": {"source_row": "identifiant technique de ligne", "lot": "lot simulé dérivé d'une commande, sauf donnée batch explicite"},
        "outputs": [
            "supplier_lane_scope.csv",
            "supplier_item_source_coverage.csv",
            "observed_open_order_ledger.csv",
            "data_quality_findings.csv",
            "REPORT.md",
        ],
    }
    (output_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    report = f"""# Périmètre fournisseurs à analyser

Ce document est un audit de preuve, pas un classement de risque.

- Voies structurelles : {len(scope)}
- Référence simulée + carnet 2025 : {counts['simulated_and_orderbook']}
- Référence simulée uniquement : {counts['simulated_only']}
- Carnet 2025 uniquement, replay requis : {counts['orderbook_only']}
- Non exercées, conclusion impossible : {counts['unexercised']}
- Lignes de commandes ouvertes : {len(orders)}
- Lignes converties vers l'unité standard du graphe : {len(normalized_uom_rows)}
- Lignes d'achat écartées faute de voie exacte : {len(excluded_order_rows)} ({len(excluded_suppliers)} fournisseurs, {len(excluded_items)} articles)
- Articles-sites fournisseurs : {len(source_coverage)}
- Articles-sites à source unique dans le graphe : {sum(int(row['structural_source_count']) == 1 for row in source_coverage)}
- Articles-sites multisources avec au moins deux sources étayées : {sum(row['source_coverage_status'] == 'multisource_multiple_suppliers_evidenced' for row in source_coverage)}
- Articles-sites multisources mais avec une seule source étayée : {sum(row['source_coverage_status'] == 'multisource_only_one_supplier_evidenced' for row in source_coverage)}
- Articles-sites multisources sans aucune source étayée : {sum(row['source_coverage_status'] == 'multisource_no_supplier_evidenced' for row in source_coverage)}

Le carnet fourni décrit des dates planifiées à l'instantané; il ne constitue pas un historique OTIF. `source_row` n'est ni un numéro de commande ni un lot industriel. Une source présente dans le graphe n'est pas automatiquement une solution de secours qualifiée et disponible.
"""
    (output_dir / "REPORT.md").write_text(report, encoding="utf-8")
    print(f"[OK] Supplier network scope audit: {output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
