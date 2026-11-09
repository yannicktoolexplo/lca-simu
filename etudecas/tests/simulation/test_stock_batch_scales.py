"""Opening-stock batch oracles in memory, with source graph read-only coverage."""
from copy import deepcopy
from fractions import Fraction
import gzip
import json
from pathlib import Path

import pytest

from etudecas.simulation.analysis_batch_common import apply_scales, scale_initial_inventory
from etudecas.simulation.engine import run_first_simulation as engine


def graph():
    nodes = []
    for node_id, kind in [("S", "supplier_dc"), ("F", "factory"),
                          ("D", "distribution_center"), ("C", "customer")]:
        node = {"id": node_id, "type": kind, "inventory": {"states": [
            {"item_id": "item:U", "initial": 100, "uom": "UN", "initial_source": "mrp_snapshot_memory"},
            {"item_id": "item:M", "initial": 100.25, "uom": "KG", "initial_source": "memory_mass"},
        ]}}
        if kind == "factory":
            node["processes"] = [{"id": "p"}]
        nodes.append(node)
    return {"nodes": nodes, "edges": [], "items": [], "scenarios": [{"id": "scn:BASE"}], "meta": {}}


def states(data):
    return {(node["id"], state["item_id"]): state for node in data["nodes"]
            for state in node["inventory"]["states"]}


def add_held(data, quantity, *, item="item:U", uom="UN"):
    data["meta"]["initial_stock_availability"] = {
        "schema_version": 1, "knowledge_date": "2025-01-01", "rows": [
            {"node_id": "F", "item_id": item, "quantity": quantity, "uom": uom,
             "release_day": 7, "source_row": "memory_source!A2"},
        ],
    }


def test_neutral_stock_factors_preserve_every_inventory_field_and_metadata():
    original = graph()
    add_held(original, 80)
    direct = deepcopy(original)
    scale_initial_inventory(direct, supplier_scale=1, production_scale=1,
                            supplier_node_scale={"S": 1}, supplier_pair_scale={("S", "F", "item:U"): 1})
    assert direct == original
    result = apply_scales(original, "scn:BASE", {"supplier_stock_scale": 1, "production_stock_scale": 1})
    assert states(result) == states(original) and result["meta"] == original["meta"]


@pytest.mark.parametrize("quantity,global_scale,node_scale,pair_scale,expected", [
    (100, 0.7, 1, 0.1, 7),
    (10000, 0.94, 0.95, 1, 8930),
    (15, 1.1, 1.5, 0.7, 17),
])
def test_global_node_and_pair_stock_factors_compose_before_single_integer_floor(
    quantity, global_scale, node_scale, pair_scale, expected,
):
    original = graph()
    states(original)["S", "item:U"]["initial"] = quantity
    before = deepcopy(original)
    result = apply_scales(original, "scn:BASE", {"supplier_stock_scale": global_scale},
        supplier_node_scale={"S": node_scale}, supplier_stock_pair_scale={"S|F|item:U": pair_scale})
    exact = Fraction(quantity) * Fraction(str(global_scale)) * Fraction(str(node_scale)) * Fraction(str(pair_scale))
    assert exact.numerator // exact.denominator == expected
    quantity_after = states(result)["S", "item:U"]["initial"]
    assert quantity_after == expected and type(quantity_after) is int
    assert original == before


def test_shared_supplier_item_pool_is_scaled_once_across_destinations():
    original = graph()
    result = apply_scales(original, "scn:BASE", {}, supplier_stock_pair_scale={
        "S|F|item:U": 0.5, "S|D|item:U": 0.5,
    })
    assert states(result)["S", "item:U"]["initial"] == 50
    with pytest.raises(ValueError, match="Conflicting route factors"):
        apply_scales(original, "scn:BASE", {}, supplier_stock_pair_scale={
            "S|F|item:U": 0.5, "S|D|item:U": 0.6,
        })


@pytest.mark.parametrize("held,factor,expected", [(80, 0.1, 82), (100, 0.37, 100)])
def test_free_stock_scaling_preserves_retained_source_quantities_dates_and_validity(held, factor, expected):
    original = graph()
    add_held(original, held)
    before = deepcopy(original)
    result = apply_scales(original, "scn:BASE", {"production_stock_scale": factor})
    assert result["meta"]["initial_stock_availability"] == before["meta"]["initial_stock_availability"]
    state = states(result)["F", "item:U"]
    assert state["initial"] == expected and state["initial"] >= held
    assert state["initial_source"].startswith("mrp_snapshot_")
    assert state["initial_before_scenario_scale"] == 100
    assert state["scenario_initial_quantity_status"] == "hypothetical_not_industrial_observation"
    availability = engine.InitialStockAvailability(result["meta"]["initial_stock_availability"],
        stock={("F", "item:U"): expected}, item_unit_map={"item:U": "UN"}, origin_date="2025-01-01")
    assert availability.held_by_pair["F", "item:U"] == held
    assert availability.rows[0]["release_day"] == 7
    provenance = next(row for row in result["meta"]["initial_stock_scale_scenario"]["rows"]
                      if (row["node_id"], row["item_id"]) == ("F", "item:U"))
    assert provenance["physical_after"] == provenance["retained_source_quantity"] + provenance["free_after"]
    assert provenance["free_before"] == 100 - held
    assert original == before


def test_mass_stock_preserves_unit_and_scales_only_free_quantity():
    original = graph()
    add_held(original, 20.1, item="item:M", uom="KG")
    result = apply_scales(original, "scn:BASE", {"production_stock_scale": 0.7})
    state = states(result)["F", "item:M"]
    expected = Fraction("20.1") + (Fraction("100.25") - Fraction("20.1")) * Fraction("0.7")
    assert state["uom"] == "KG" and state["initial"] == float(expected)
    assert result["meta"]["initial_stock_availability"] == original["meta"]["initial_stock_availability"]


def test_supplier_and_production_scopes_preserve_downstream_and_virtual_inventory():
    original = graph()
    original["items"] = [{"id": "item:T", "kind": "virtual_process_input", "attrs": {"virtual": True}}]
    original["nodes"][1]["inventory"]["states"].append(
        {"item_id": "item:T", "initial": 730, "uom": "UN", "initial_source": "technical_bound"})
    before = deepcopy(original)
    result = apply_scales(original, "scn:BASE", {"supplier_stock_scale": 0.93, "production_stock_scale": 0.91})
    output, source = states(result), states(original)
    assert output["S", "item:U"]["initial"] == 93
    assert output["F", "item:U"]["initial"] == 91
    for pair in source:
        if pair[0] in {"D", "C"} or pair[1] == "item:T":
            assert output[pair] == source[pair]
    assert result["meta"]["initial_stock_scale_scenario"]["excluded_virtual_inputs"] == [{"node_id": "F", "item_id": "item:T"}]
    assert original == before


def test_supplier_stock_mapping_cannot_target_distribution_or_customer_inventory():
    for node_id in ("D", "C", "F"):
        with pytest.raises(ValueError, match="non-supplier inventory"):
            apply_scales(graph(), "scn:BASE", {}, supplier_node_scale={node_id: 0.5})


def test_workshop_scales_keep_real_source_holds_and_every_physical_unit_integral():
    path = Path(__file__).resolve().parents[2] / "config/mrp_reference_20261013/graph.json.gz"
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        original = json.load(handle)
    before = deepcopy(original)
    result = apply_scales(original, "scn:BASE", {"supplier_stock_scale": 0.937481, "production_stock_scale": 0.913217},
                          supplier_node_scale={node["id"]: 0.952137 for node in original["nodes"] if node.get("type") == "supplier_dc"})
    source, output = states(original), states(result)
    held = {}
    for row in original["meta"]["initial_stock_availability"]["rows"]:
        pair = row["node_id"], row["item_id"]
        held[pair] = held.get(pair, Fraction(0)) + Fraction(str(row["quantity"]))
    for node in original["nodes"]:
        for state in node["inventory"]["states"]:
            pair = node["id"], state["item_id"]
            if node["type"] in {"distribution_center", "customer"} or "VIRTUAL" in state["item_id"]:
                assert output[pair] == source[pair]
            if state["uom"] == "UN":
                actual = output[pair]["initial"]
                assert int(actual) == actual
                engine.require_physical_integer(actual, "UN")
            elif pair in held:
                factor = Fraction("0.913217")
                expected = held[pair] + (Fraction(str(state["initial"])) - held[pair]) * factor
                assert output[pair]["initial"] == float(expected)
    availability = engine.InitialStockAvailability(result["meta"]["initial_stock_availability"],
        stock={pair: state["initial"] for pair, state in output.items()},
        item_unit_map=engine.infer_item_unit_map(result["nodes"], result["edges"]), origin_date="2025-01-01")
    assert len(availability.rows) == 5
    assert result["meta"]["initial_stock_availability"] == original["meta"]["initial_stock_availability"]
    assert original == before


def test_scaled_future_leads_preserve_internal_source_contract_and_whole_fia_days():
    path = Path(__file__).resolve().parents[2] / "config/mrp_reference_20261013/graph.json.gz"
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        original = json.load(handle)
    before = deepcopy(original)
    factor = 1.015947
    result = apply_scales(original, "scn:BASE", {"lead_time_scale": factor})
    protected = {(row["source_node_id"], row["node_id"], row["item_id"])
                 for row in original["meta"]["internal_component_policy"]["rows"]}
    previous = {edge["id"]: edge for edge in original["edges"]}
    changed = 0
    for edge in result["edges"]:
        source = previous[edge["id"]]
        if any((edge["from"], edge["to"], item) in protected for item in edge.get("items", [])):
            assert edge["lead_time"] == source["lead_time"]
        elif (source.get("lead_time") or {}).get("source") == "case_data_fia":
            exact = Fraction(str(source["lead_time"]["mean"])) * Fraction(str(factor))
            expected = -(-exact.numerator // exact.denominator)
            assert edge["lead_time"]["mean"] == expected
            changed += edge["lead_time"]["mean"] != source["lead_time"]["mean"]
    assert changed > 0
    lanes, incoming = engine.lane_records(result["edges"])
    resolved = engine.resolve_internal_component_policies(result["meta"]["internal_component_policy"],
        execution_mode="dated", lanes_by_dest_item=incoming,
        item_unit_map=engine.infer_item_unit_map(result["nodes"], result["edges"]), nodes=result["nodes"])
    assert len(resolved) == len(protected)
    suppliers = {node["id"] for node in result["nodes"] if node.get("type") == "supplier_dc"}
    checked = 0
    for lane in lanes:
        if lane["src"] in suppliers and lane["lead_time_source"] == "case_data_fia":
            assert engine.supplier_delivery_lead_days(lane, None, mode="source", stochastic=False) >= 1
            checked += 1
    assert checked > 0
    audit = result["meta"]["lead_time_scale_scenario"]
    assert sum(row["status"] == "excluded_source_bound_internal_reference" for row in audit["rows"]) == len(protected)
    assert result["meta"]["internal_component_policy"] == original["meta"]["internal_component_policy"]
    assert result["meta"]["opening_open_orders"] == original["meta"]["opening_open_orders"]
    assert original == before


def test_neutral_lead_factor_preserves_source_references_without_hypothesis_metadata():
    original = graph()
    original["edges"] = [{"id": "lane", "from": "S", "to": "F", "items": ["item:U"],
                          "lead_time": {"source": "case_data_fia", "mean": 13}}]
    result = apply_scales(original, "scn:BASE", {"lead_time_scale": 1})
    assert result["edges"][0]["lead_time"] == original["edges"][0]["lead_time"]
    assert "lead_time_scale_scenario" not in result["meta"]


def test_whole_fia_days_compose_decimal_factors_before_ceiling():
    original = graph()
    original["edges"] = [{"id": "lane", "from": "S", "to": "F", "items": ["item:U"],
                          "lead_time": {"source": "case_data_fia", "mean": 100}}]
    result = apply_scales(original, "scn:BASE", {"lead_time_scale": 0.28},
                          edge_src_lead_time_scale={"S": 0.25})
    exact = Fraction(100) * Fraction(28, 100) * Fraction(1, 4)
    assert -(-exact.numerator // exact.denominator) == 7
    assert result["edges"][0]["lead_time"]["mean"] == 7
