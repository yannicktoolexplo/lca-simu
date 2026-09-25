import math
import pytest

from etudecas.simulation.engine.api import request_from_dict


@pytest.mark.parametrize("field,value", [
    ("skip_map", "false"), ("skip_plots", 0), ("run_lot_audit", "false"),
    ("common_random_numbers", "false"), ("days", -1), ("days", 1.5),
    ("days", True), ("days", "2"), ("days", None), ("seed", False),
    ("seed", -1), ("output_profile", "bogus"), ("scenario_id", 1),
    ("unknown", 1), ("input_graph", []),
])
def test_request_rejects_coercions(field, value):
    with pytest.raises(ValueError):
        request_from_dict({"input_graph": {}, field: value})


@pytest.mark.parametrize("value", [math.nan, math.inf, -math.inf, -1, True, "1", [], None])
def test_scales_require_finite_nonnegative_numbers(value):
    with pytest.raises(ValueError):
        request_from_dict({"input_graph": {}, "overrides": {"factors": {"stock": value}}})


@pytest.mark.parametrize("overrides", [[], {"unknown": {}}, {"scenario_flags": {"enabled": "false"}},
                                         {"engine_args": "--x"}, {"factors": []}])
def test_override_shapes_are_strict(overrides):
    with pytest.raises(ValueError):
        request_from_dict({"input_graph": {}, "overrides": overrides})


def test_false_zero_and_internal_controls_are_preserved():
    request = request_from_dict({"input_graph": {}, "days": 0, "seed": 0,
        "common_random_numbers": False, "run_lot_audit": False,
        "run_script": "trusted.py", "overrides": {"factors": {"stock": 0},
        "scenario_flags": {"enabled": False}, "engine_args": ["--trusted-option"]}})
    assert request.common_random_numbers is False
    assert request.overrides.scenario_flags == {"enabled": False}
    assert request.overrides.factors == {"stock": 0.0}
    assert request.run_script == "trusted.py"
    assert request.days == request.seed == 0


@pytest.mark.parametrize("payload", [{}, {"input_graph": {}, "input_path": "graph.json"}])
def test_exactly_one_graph_source(payload):
    with pytest.raises(ValueError):
        request_from_dict(payload)
