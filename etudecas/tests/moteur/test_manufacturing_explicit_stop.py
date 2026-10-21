"""Memory-only arithmetic, actual execution-expression and MPS stop oracles.

No source mutation, synthetic disappearance, timestamp change or file fixture.
The execution expression is read from the actual engine so a disconnected
helper cannot make the production-stop check pass.
"""
from __future__ import annotations

import ast
from copy import deepcopy
from functools import lru_cache
import math
from pathlib import Path

import pytest

from etudecas.simulation.engine import run_first_simulation as engine
from etudecas.simulation.lot_trace.campaigns import ProductionBatchWip


PAIR = ("Gaillac", "item:693055")
RAW = ("Gaillac", "item:RAW")
OTHER = ("other_factory", "item:PF")
OTHER_RAW = ("other_factory", "item:RAW")
LOT = {"enabled": True, "fixed_lot_qty": 600, "max_lots_per_week": 20}


@lru_cache(maxsize=1)
def _execution_expressions():
    tree = ast.parse(Path(engine.__file__).read_text(encoding="utf-8-sig"))
    capacity = [node.value for node in ast.walk(tree) if isinstance(node, ast.Assign)
        and any(isinstance(t, ast.Name) and t.id == "cap" for t in node.targets)
        and {"cap_raw", "capacity_multiplier"} <= {
            name.id for name in ast.walk(node.value) if isinstance(name, ast.Name)}]
    closed = [kw.value for node in ast.walk(tree) if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name) and node.func.id == "lotified_mps_component_signal"
        for kw in node.keywords if kw.arg == "closed_output_pairs"]
    assert len(capacity) == 1 and len(closed) == 1
    return capacity[0], closed[0]


def _evaluate(expression, **context):
    namespace = dict(vars(engine))
    namespace.update(context)
    return eval(compile(ast.Expression(body=expression), "<engine-memory-expression>", "eval"), namespace)


def _capacity(nominal, multiplier):
    return _evaluate(_execution_expressions()[0], cap_raw=nominal,
        capacity_multiplier=multiplier, has_capacity_limit=nominal > 0)


def _closed(day, stops, declared=None):
    return _evaluate(_execution_expressions()[1], day=day,
        stopped_daily_pairs=stops, manufacturing_closed_days=declared or {})


def _mps(*, day, campaigns, counters, stops, capacity, demands=None, declared=None):
    return engine.lotified_mps_component_signal(demands or {PAIR: 100}, day=day,
        process_input_requirements_by_output_pair={PAIR: [(RAW, 2)], OTHER: [(OTHER_RAW, 3)]},
        production_lot_policy_by_pair={PAIR: LOT}, process_capacity_by_output_pair=capacity,
        mps_open_campaign_qty_by_pair=campaigns, mps_started_lots_by_week_pair=counters,
        closed_output_pairs=_closed(day, stops, declared))


@pytest.mark.parametrize("nominal", [0.0, 120.0])
@pytest.mark.parametrize("multiplier", [1.0, 0.0, 0.5])
def test_actual_execution_capacity_matches_independent_stop_oracle(nominal, multiplier):
    # Independent statement of the contract; an unknown positive rate is never imputed.
    expected = (0.0 if multiplier == 0 else math.inf if nominal == 0 else nominal * multiplier)
    assert _capacity(nominal, multiplier) == expected


@pytest.mark.parametrize("existing_campaign", [0, 250])
@pytest.mark.parametrize("nominal", [0.0, 120.0])
def test_current_day_stop_preserves_campaign_and_cannot_create_phantom_mps_lot(existing_campaign, nominal):
    campaigns = {PAIR: existing_campaign} if existing_campaign else {}
    counters = {(2, PAIR): 3}
    before = deepcopy((campaigns, counters))
    capacities = {PAIR: _capacity(nominal, 0)}
    components, outputs = _mps(day=20, campaigns=campaigns, counters=counters,
        stops={PAIR}, capacity=capacities)
    assert components == outputs == {}
    assert (campaigns, counters) == before


@pytest.mark.parametrize("existing_campaign", [0, 250])
def test_mps_resumes_same_campaign_without_consuming_a_slot_on_the_stopped_day(existing_campaign):
    campaigns = {PAIR: existing_campaign} if existing_campaign else {}
    counters = {}
    assert _mps(day=0, campaigns=campaigns, counters=counters,
        stops={PAIR}, capacity={PAIR: 0}) == ({}, {})
    assert counters == {} and campaigns == ({PAIR: existing_campaign} if existing_campaign else {})
    first_components, first_outputs = _mps(day=1, campaigns=campaigns, counters=counters,
        stops=set(), capacity={PAIR: 200})
    assert first_outputs == {PAIR: 200} and first_components == {RAW: 400}
    expected_total = existing_campaign or 600
    assert campaigns[PAIR] == expected_total - 200
    expected_counters = {} if existing_campaign else {(0, PAIR): 1}
    assert counters == expected_counters
    last_components, last_outputs = _mps(day=2, campaigns=campaigns, counters=counters,
        stops=set(), capacity={PAIR: 1000})
    assert last_outputs == {PAIR: expected_total - 200}
    assert last_components == {RAW: 2 * (expected_total - 200)}
    assert sum(first_outputs.values()) + sum(last_outputs.values()) == expected_total
    assert campaigns[PAIR] == 0 and counters == expected_counters


def test_stop_scope_and_known_future_calendar_remain_distinct():
    calendar = {OTHER: frozenset({21})}
    original = deepcopy(calendar)
    assert _closed(20, {PAIR}, calendar) == {PAIR}
    assert _closed(21, set(), calendar) == {OTHER}
    campaigns, counters = {}, {}
    components, outputs = _mps(day=20, campaigns=campaigns, counters=counters,
        stops={PAIR}, capacity={}, demands={PAIR: 100, OTHER: 10}, declared=calendar)
    assert outputs == {OTHER: 10} and components == {OTHER_RAW: 30}
    assert campaigns == counters == {} and calendar == original


@pytest.mark.parametrize("nominal", [0.0, 120.0])
def test_physical_wip_and_genealogy_are_unchanged_by_stop_then_resume(nominal):
    old_parents = [{"lot_id": "existing-material", "qty": 800}]
    wip = ProductionBatchWip("existing-OF", "existing-batch", PAIR[0], PAIR[1],
        -1, -1, target_qty=1000, executed_qty=400, parent_allocations=deepcopy(old_parents))
    for _ in range(3):
        accepted = wip.add_execution(min(wip.remaining_qty, _capacity(nominal, 0)), [])
        assert accepted == 0 and wip.executed_qty == 400 and not wip.is_complete
        assert wip.parent_allocations == old_parents
    for _ in range(5):
        work = min(wip.remaining_qty, _capacity(nominal, 1))
        wip.add_execution(work, [{"lot_id": "new-material", "qty": 2 * work}])
    assert wip.is_complete and wip.executed_qty == wip.target_qty == 1000
    assert sum(parent["qty"] for parent in wip.parent_allocations) == 2000
    assert wip.campaign_id == "existing-OF" and wip.batch_id == "existing-batch"


def test_legacy_zero_capacity_without_an_explicit_stop_remains_unmodeled():
    campaigns = {PAIR: 100}
    components, outputs = _mps(day=0, campaigns=campaigns, counters={},
        stops=set(), capacity={PAIR: 0})
    assert outputs == {PAIR: 100} and components == {RAW: 200}
