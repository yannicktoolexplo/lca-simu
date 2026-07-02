from __future__ import annotations

from etudecas.simulation.lot_trace.indexes import (
    build_lot_trace_indexes,
    lot_trace_downstream_stats,
    lot_trace_upstream_roots,
    lot_trace_upstream_stats,
)


def test_chain_counts_upstream_and_downstream_lots() -> None:
    indexes = build_lot_trace_indexes(
        {
            "events": [
                _event("LOT-MP", "opening_stock", "S-RAW"),
                _event("LOT-PF", "production_output", "M-1"),
                _event("LOT-DC", "lane_receipt", "DC-1"),
                _event("LOT-CLIENT", "demand_service", "C-1"),
            ],
            "genealogy": [
                _link("production", "LOT-MP", "LOT-PF"),
                _link("transport", "LOT-PF", "LOT-DC"),
                _link("transport", "LOT-DC", "LOT-CLIENT"),
            ],
        }
    )

    downstream = lot_trace_downstream_stats(indexes, "LOT-MP")
    upstream = lot_trace_upstream_stats(indexes, "LOT-CLIENT")

    assert downstream == {
        "downstream_lot_count": 3,
        "downstream_node_count": 3,
        "downstream_finished_product_lot_count": 1,
        "downstream_link_types": ["production", "transport"],
    }
    assert upstream == {
        "upstream_lot_count": 3,
        "upstream_node_count": 3,
        "upstream_material_lot_count": 1,
        "upstream_link_types": ["production", "transport"],
    }
    assert lot_trace_upstream_roots(indexes, "LOT-CLIENT") == {"LOT-MP"}


def test_cycle_does_not_loop_or_count_root_as_relative() -> None:
    indexes = build_lot_trace_indexes(
        {
            "events": [
                _event("LOT-A", "opening_stock", "N-A"),
                _event("LOT-B", "lane_receipt", "N-B"),
                _event("LOT-C", "lane_receipt", "N-C"),
            ],
            "genealogy": [
                _link("transport", "LOT-A", "LOT-B"),
                _link("transport", "LOT-B", "LOT-C"),
                _link("transport", "LOT-C", "LOT-A"),
            ],
        }
    )

    assert lot_trace_downstream_stats(indexes, "LOT-A")["downstream_lot_count"] == 2
    assert lot_trace_upstream_stats(indexes, "LOT-A")["upstream_lot_count"] == 2
    assert lot_trace_upstream_roots(indexes, "LOT-A") == set()


def _event(lot_id: str, event_type: str, node_id: str) -> dict[str, object]:
    return {
        "event_id": f"E-{lot_id}",
        "day": 0,
        "event_type": event_type,
        "lot_id": lot_id,
        "node_id": node_id,
    }


def _link(link_type: str, parent_lot_id: str, child_lot_id: str) -> dict[str, object]:
    return {
        "day": 0,
        "link_type": link_type,
        "parent_lot_id": parent_lot_id,
        "child_lot_id": child_lot_id,
        "source_id": f"{parent_lot_id}->{child_lot_id}",
    }
