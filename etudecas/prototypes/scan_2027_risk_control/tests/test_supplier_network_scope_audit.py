from __future__ import annotations

import csv
import json
from pathlib import Path

from etudecas.prototypes.scan_2027_risk_control import supplier_network_scope_audit as audit


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def test_scope_separates_flow_orderbook_and_unexercised(tmp_path: Path) -> None:
    graph = {
        "meta": {
            "opening_open_orders": {
                "source_file": "orders.xlsx",
                "snapshot_date": "2025-01-01",
                "rows": [
                    {
                        "source_row": 7,
                        "order_type": "purchase_open_order",
                        "src_node_id": "SUP-B",
                        "dst_node_id": "F",
                        "item_id": "item:B",
                        "quantity": 20,
                        "uom": "KG",
                        "physical_delivery_day": 3,
                        "usable_day": 9,
                    }
                ],
            }
        },
        "nodes": [
            {"id": "SUP-A", "type": "supplier_dc"},
            {"id": "SUP-B", "type": "supplier_dc"},
            {"id": "SUP-C", "type": "supplier_dc"},
            {
                "id": "F",
                "type": "factory",
                "processes": [
                    {
                        "inputs": [{"item_id": "item:A"}, {"item_id": "item:B"}, {"item_id": "item:C"}],
                        "outputs": [{"item_id": "item:P"}],
                    }
                ],
            },
        ],
        "edges": [
            {"id": "A", "from": "SUP-A", "to": "F", "items": ["item:A"]},
            {"id": "B", "from": "SUP-B", "to": "F", "items": ["item:B"]},
            {"id": "C", "from": "SUP-C", "to": "F", "items": ["item:C"]},
        ],
        "scenarios": [{"demand": [{"node_id": "CLIENT", "item_id": "item:P"}]}],
    }
    graph_path = tmp_path / "graph.json"
    graph_path.write_text(json.dumps(graph), encoding="utf-8")
    shipments_path = tmp_path / "shipments.csv"
    _write_csv(
        shipments_path,
        [{"day": 1, "src_node_id": "SUP-A", "dst_node_id": "F", "item_id": "item:A", "shipped_qty": 10, "pulled_qty": 10}],
    )
    output_dir = tmp_path / "out"
    assert audit.main(["--graph", str(graph_path), "--baseline-shipments", str(shipments_path), "--output-dir", str(output_dir)]) == 0
    with (output_dir / "supplier_lane_scope.csv").open(encoding="utf-8", newline="") as stream:
        rows = {row["supplier_id"]: row for row in csv.DictReader(stream)}
    assert rows["SUP-A"]["evidence_status"] == "simulated_only"
    assert rows["SUP-B"]["evidence_status"] == "orderbook_only"
    assert rows["SUP-C"]["evidence_status"] == "unexercised"
    assert rows["SUP-A"]["downstream_products"] == "P"
    manifest = json.loads((output_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["priority_lane_count"] == 2
    assert manifest["not_a_risk_ranking"] is True


def test_order_ledger_never_claims_actual_delivery_or_business_lot(tmp_path: Path) -> None:
    graph = {
        "meta": {
            "opening_open_orders": {
                "rows": [
                    {
                        "source_row": 40,
                        "order_type": "purchase_open_order",
                        "src_node_id": "SUP",
                        "dst_node_id": "F",
                        "item_id": "item:X",
                        "quantity": 40_000,
                        "uom": "KG",
                    }
                ]
            }
        }
    }
    rows = audit.observed_order_rows(graph)
    assert rows[0]["actual_delivery_proof"] is False
    assert rows[0]["lot_identity_kind"] == "source_row_technical_not_business_lot"


def test_opening_order_shipments_are_not_counted_as_dynamic_flow() -> None:
    graph = {
        "meta": {"opening_open_orders": {"rows": []}},
        "nodes": [
            {"id": "SUP", "type": "supplier_dc"},
            {"id": "F", "type": "factory", "processes": []},
        ],
        "edges": [{"id": "lane", "from": "SUP", "to": "F", "items": ["item:X"]}],
    }
    shipments = [
        {
            "src_node_id": "SUP",
            "dst_node_id": "F",
            "item_id": "item:X",
            "shipped_qty": 20_000,
            "pulled_qty": 20_000,
            "transport_cost_basis": "opening_order_book",
        }
    ]
    scope, _, _ = audit.build_scope(graph, shipments, [])
    assert scope[0]["evidence_status"] == "unexercised"
    assert scope[0]["baseline_shipped_qty"] == 0.0
    assert scope[0]["opening_order_seed_shipped_qty"] == 20_000.0


def test_external_order_audit_keeps_only_exact_purchase_lanes() -> None:
    rows = audit.observed_order_rows_from_audit(
        [
            {
                "order_type": "purchase_open_order",
                "valid_exact_lane": "True",
                "src_node_id": "SUP-A",
                "dst_node_id": "F",
                "item_id": "item:A",
                "quantity": "2000000",
                "uom": "G",
                "qty_standard_uom": "2000",
                "standard_order_uom": "KG",
            },
            {
                "order_type": "purchase_open_order",
                "valid_exact_lane": "False",
                "src_node_id": "SUP-B",
                "dst_node_id": "F",
                "item_id": "item:B",
                "quantity": "20",
            },
        ]
    )
    assert len(rows) == 1
    assert rows[0]["supplier_id"] == "SUP-A"
    assert rows[0]["source_quantity"] == 2_000_000
    assert rows[0]["source_uom"] == "G"
    assert rows[0]["quantity"] == 2_000
    assert rows[0]["uom"] == "KG"
    assert rows[0]["quantity_normalization"] == "G_to_KG"


def test_unmatched_finding_is_explicitly_limited_to_retained_exact_rows() -> None:
    graph = {
        "meta": {"opening_open_orders": {"rows": []}},
        "nodes": [
            {"id": "SUP-A", "type": "supplier_dc"},
            {"id": "F", "type": "factory", "processes": []},
        ],
        "edges": [{"id": "A", "from": "SUP-A", "to": "F", "items": ["item:A"]}],
    }
    retained_orders = [
        {
            "supplier_id": "SUP-B",
            "dst_node_id": "F",
            "item_id": "item:B",
            "quantity": 10,
        }
    ]
    _, _, findings = audit.build_scope(graph, [], [], retained_orders)
    finding = next(
        row
        for row in findings
        if row["finding_id"] == "RETAINED_EXACT_ORDER_ROWS_NOT_IN_GRAPH"
    )
    assert "Parmi les 1 lignes" in finding["detail"]
    assert "1 ne correspondent" in finding["detail"]


def test_multisource_structure_does_not_imply_an_exercised_backup() -> None:
    graph = {
        "meta": {"opening_open_orders": {"rows": []}},
        "nodes": [
            {"id": "SUP-A", "type": "supplier_dc"},
            {"id": "SUP-B", "type": "supplier_dc"},
            {"id": "F", "type": "factory", "processes": []},
        ],
        "edges": [
            {"id": "A", "from": "SUP-A", "to": "F", "items": ["item:X"]},
            {"id": "B", "from": "SUP-B", "to": "F", "items": ["item:X"]},
        ],
    }
    shipments = [
        {
            "src_node_id": "SUP-A",
            "dst_node_id": "F",
            "item_id": "item:X",
            "shipped_qty": 10,
            "pulled_qty": 10,
        }
    ]
    scope, _, _ = audit.build_scope(graph, shipments, [])
    by_supplier = {row["supplier_id"]: row for row in scope}
    assert by_supplier["SUP-A"]["structural_source_count"] == 2
    assert by_supplier["SUP-A"]["dynamic_reference_source_count"] == 1
    assert by_supplier["SUP-A"]["is_only_dynamic_source_for_item_site"] is True
    assert by_supplier["SUP-A"]["alternative_evidence"] == "SUP-B:unexercised"
    assert by_supplier["SUP-B"]["alternative_evidence"] == "SUP-A:simulated_only"
    coverage = audit.build_source_coverage(scope)
    assert coverage[0]["source_coverage_status"] == "multisource_only_one_supplier_evidenced"
    assert coverage[0]["qualification_and_capacity_confirmed"] is False
