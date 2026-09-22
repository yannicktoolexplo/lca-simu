import copy
import pytest
from .schema import validate_graph_contract


def graph():
    return {"items": [{"id": "item:A"}], "nodes": [{"id": "N", "inventory": {
        "raw": [{"item_id": "A", "initial": 1}]}}], "edges": [], "scenarios": []}


@pytest.mark.parametrize("value", [float("nan"), float("inf"), -float("inf"), "NaN", True, "infinity"])
def test_nonfinite_inventory_is_rejected(value):
    data = graph()
    data["nodes"][0]["inventory"]["raw"][0]["initial"] = value
    assert any(i["field"].endswith(".initial") for i in validate_graph_contract(data))


@pytest.mark.parametrize("field,value", [("items", ["invalid"]), ("nodes", [None]),
    ("edges", [42]), ("scenarios", [False]), ("items", {}), ("nodes", "bad")])
def test_malformed_top_level_rows_return_issues(field, value):
    data = graph()
    data[field] = value
    assert validate_graph_contract(data)


@pytest.mark.parametrize("node", [{"id": "N", "inventory": {"raw": ["bad"]}},
    {"id": "N", "inventory": []}, {"id": "N", "processes": [False]},
    {"id": "N", "processes": [{"inputs": [None], "outputs": [42]}]}])
def test_malformed_nested_rows_return_issues(node):
    data = graph()
    data["nodes"] = [node]
    assert validate_graph_contract(data)


def test_valid_graph_validation_does_not_mutate_input():
    data = graph()
    before = copy.deepcopy(data)
    assert validate_graph_contract(data) == []
    assert data == before
