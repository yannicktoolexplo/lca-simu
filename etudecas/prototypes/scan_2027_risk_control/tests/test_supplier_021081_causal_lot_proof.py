from __future__ import annotations

from pathlib import Path

import pytest

from etudecas.prototypes.scan_2027_risk_control import (
    supplier_021081_active_flow_campaign as base,
)

from etudecas.prototypes.scan_2027_risk_control import (
    build_supplier_021081_causal_lot_proof as proof,
)


def test_native_traversal_follows_parent_to_child_to_customer() -> None:
    receipt = {"lot_id": "R", "day": 100, "qty": 40_000}
    genealogy = [
        {
            "day": 120,
            "link_type": "production",
            "parent_lot_id": "R",
            "child_lot_id": "I",
            "child_item_id": "item:773474",
            "child_node_id": "SDC-1450",
            "child_qty": 3_200_000,
        },
        {
            "day": 180,
            "link_type": "production",
            "parent_lot_id": "I",
            "child_lot_id": "F",
            "child_item_id": "item:268967",
            "child_node_id": "M-1430",
            "child_qty": 107_800,
        },
        {
            "day": 200,
            "link_type": "transport",
            "parent_lot_id": "F",
            "child_lot_id": "C",
            "child_item_id": "item:268967",
            "child_node_id": "C-XXXXX",
            "child_qty": 50_000,
        },
    ]
    rows = proof.trace_from_receipt(receipt, genealogy, source_row="24")
    assert len(rows) == 3
    aggregate = proof.aggregate_trace(receipt, rows)
    assert aggregate["intermediate_descendant_lot_count"] == 1
    assert aggregate["finished_descendant_lot_count"] == 1
    assert aggregate["customer_delivery_qty"] == 50_000
    assert aggregate["consumption_status"] == "receipt_has_native_descendants_in_horizon"
    assert all(row["origin_source_row"] == "24" for row in rows)


def test_no_descendant_is_reported_as_unconsumed_not_unexposed() -> None:
    receipt = {"lot_id": "R", "day": 100, "qty": 40_000}
    rows = proof.trace_from_receipt(receipt, [], source_row="24")
    aggregate = proof.aggregate_trace(receipt, rows)
    assert aggregate["descendant_link_count"] == 0
    assert aggregate["consumption_status"] == "receipt_not_consumed_in_test_horizon"


def test_source_campaign_requires_positive_execution_provenance(
    tmp_path: Path,
) -> None:
    base.write_json(tmp_path / "campaign_manifest.json", {"status": "complete"})
    base.write_json(
        tmp_path / "execution_provenance_audit.json",
        {"reproducibility_wording_allowed": False},
    )
    with pytest.raises(ValueError, match="audited source execution"):
        proof.validated_source_campaign(tmp_path)

    base.write_json(
        tmp_path / "execution_provenance_audit.json",
        {"reproducibility_wording_allowed": True},
    )
    manifest, audit = proof.validated_source_campaign(tmp_path)
    assert manifest["status"] == "complete"
    assert audit["reproducibility_wording_allowed"] is True
