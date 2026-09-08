from __future__ import annotations

import math

import pytest

from etudecas.prototypes.scan_2027_risk_control import (
    supplier_021081_active_flow_campaign as base,
)
from etudecas.prototypes.scan_2027_risk_control import (
    supplier_021081_bom_unit_sensitivity as campaign,
)


def _ratio(graph: dict[str, object]) -> float:
    for node in graph["nodes"]:  # type: ignore[index]
        if node.get("id") != "SDC-1450":
            continue
        for process in node.get("processes", []):
            if process.get("id") != "proc:MAKE_773474":
                continue
            for row in process.get("inputs", []):
                if row.get("item_id") == "item:021081":
                    return float(row["ratio_per_batch"])
    raise AssertionError("target ratio absent")


def test_unit_variants_are_literal_and_declared_hypothesis() -> None:
    assert [variant.variant_id for variant in campaign.UNIT_VARIANTS] == [
        "literal_graph_ratio",
        "ratio_divided_by_1000_hypothesis",
    ]
    assert campaign.UNIT_VARIANTS[0].ratio_per_batch_kg == 8.94
    assert campaign.UNIT_VARIANTS[1].ratio_per_batch_kg == 0.00894


def test_ratio_overlay_does_not_mutate_source_graph() -> None:
    source = base.read_json(base.DEFAULT_GRAPH)
    source_hash = base.json_sha256(source)
    alternative = campaign.UNIT_VARIANTS[1]
    graph, audit = campaign.graph_with_ratio(source, alternative)
    assert math.isclose(_ratio(source), 8.94)
    assert math.isclose(_ratio(graph), 0.00894)
    assert base.json_sha256(source) == source_hash
    assert audit["ratio_divisor_vs_literal"] == pytest.approx(1000)
    assert audit["status"] == "unit_to_validate_with_industrial_owner"
