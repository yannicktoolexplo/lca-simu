"""Run the real calendar block without main, files written, or simulation runs."""
import ast
from collections import defaultdict, deque
from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest


ENGINE = Path(__file__).resolve().parents[2] / 'simulation/engine/run_first_simulation.py'
PAIR_A = ('factory-A', 'material-A')
PAIR_B = ('factory-B', 'material-B')


def source_block():
    """Read existing source only; never reproduce the calendar implementation."""
    tree = ast.parse(ENGINE.read_text(encoding='utf-8-sig'), filename=str(ENGINE))
    main, = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == 'main']
    blocks = []
    for node in ast.walk(main):
        for _, statements in ast.iter_fields(node):
            if not isinstance(statements, list):
                continue
            for index, statement in enumerate(statements[:-1]):
                if isinstance(statement, ast.Assign) and any(
                    isinstance(target, ast.Name) and target.id == 'known_supplier_calendars'
                    for target in statement.targets
                ):
                    loop = statements[index+1]
                    assert isinstance(loop, ast.For), 'Calendar construction moved; review this exact block'
                    blocks.append([statement, loop])
    block, = blocks
    helpers = [node for node in tree.body if isinstance(node, ast.FunctionDef)
               and node.name in {'to_float', 'propagate_demand_rates'}]
    assert {node.name for node in helpers} == {'to_float', 'propagate_demand_rates'}
    return ast.Module(body=helpers+block, type_ignores=[])


def case(order):
    # Three supplier routes plus a separate finished-product downstream route.
    # Dates/delays are distinct so a pair/calendar mix-up cannot pass unnoticed.
    supplier_a = dict(src='supplier-A1', dst=PAIR_A[0], item_id=PAIR_A[1])
    backup_a = dict(src='supplier-A2', dst=PAIR_A[0], item_id=PAIR_A[1])
    supplier_b = dict(src='supplier-B', dst=PAIR_B[0], item_id=PAIR_B[1])
    downstream = dict(src='factory-A', dst='depot', item_id='PF')
    network = [supplier_a, backup_a, supplier_b, downstream]
    delays = {'supplier-A1': 3, 'supplier-A2': 7, 'supplier-B': 11}
    review = {'kind': 'explicit-memory-review'}

    class OrderedPairSet(set):
        """Force both legal set traversal orders; no interpreter hash reliance."""
        def __iter__(self):
            return iter(sorted(super().__iter__(), key=order.index))

        def __or__(self, other):
            return type(self)(super().__or__(other))

    # The only stubs select source lead days and applicability of review.
    # Real calendar construction and real subsequent propagation are executed.
    namespace = dict(Any=Any, defaultdict=defaultdict, deque=deque, set=OrderedPairSet,
        lanes=network, sourcing_inputs={PAIR_A: {}}, allocated_sourcing_inputs={PAIR_B: {}},
        sourcing_policies={PAIR_A: {'_lanes_by_supplier': {
            'supplier-A1': supplier_a, 'supplier-A2': backup_a}}},
        lanes_by_dest_item={PAIR_A: [supplier_a, backup_a], PAIR_B: [supplier_b]},
        supplier_receipt_policies={PAIR_A: {'receipt_days': 2}, PAIR_B: {'receipt_days': 5}},
        safety_calendar={'start_date': '2025-01-01'},
        supplier_receipt_nonworking_dates_by_pair={PAIR_A: frozenset({'2025-01-03'})},
        supplier_purchase_review_policy=review,
        lead_time_reference_days=lambda lane: delays[lane['src']],
        purchase_policy_applies=lambda policy, pair: pair == PAIR_B)
    expected = {
        PAIR_A: {
            'supplier-A1': dict(calendar_kind='supplier_receipt', physical_lead_days=3,
                receipt_days=2, origin_date='2025-01-01',
                receipt_nonworking_dates=frozenset({'2025-01-03'})),
            'supplier-A2': dict(calendar_kind='supplier_receipt', physical_lead_days=7,
                receipt_days=2, origin_date='2025-01-01',
                receipt_nonworking_dates=frozenset({'2025-01-03'})),
        },
        PAIR_B: {
            'supplier-B': dict(calendar_kind='supplier_receipt', physical_lead_days=11,
                receipt_days=5, origin_date='2025-01-01',
                receipt_nonworking_dates=frozenset(), purchase_review_policy=review),
        },
    }
    return namespace, network, expected


@pytest.mark.parametrize('order', [(PAIR_A, PAIR_B), (PAIR_B, PAIR_A)], ids=['A-then-B', 'B-then-A'])
def test_supplier_calendars_preserve_complete_network_for_next_propagation(order):
    namespace, network, expected = case(order)
    before = deepcopy(network)
    exec(compile(source_block(), str(ENGINE), 'exec'), namespace)

    assert list(namespace['known_supplier_calendars']) == list(order)
    assert namespace['known_supplier_calendars'] == expected
    assert namespace['lanes'] is network, 'Pair-local routes replaced the complete network'
    assert network == before
    # On the following decision, 17 PF/day at the depot must still reach its
    # factory; each component signal must still reach its declared suppliers.
    demands = {('depot', 'PF'): 17, PAIR_A: 5, PAIR_B: 11}
    signal = namespace['propagate_demand_rates'](demands, namespace['lanes'])
    assert signal == {('depot', 'PF'): 17, ('factory-A', 'PF'): 17,
        PAIR_A: 5, PAIR_B: 11, ('supplier-A1', 'material-A'): 5,
        ('supplier-A2', 'material-A'): 5, ('supplier-B', 'material-B'): 11}


def test_memory_counterexample_detects_historical_network_rebinding():
    # Restore just the historical two variable names in an in-memory AST.
    # No source, artifact, timestamp or other file is changed by this test.
    tree = source_block()
    changed = 0
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and node.id == 'pair_lanes':
            node.id = 'lanes'
            changed += 1
    assert changed == 2, 'Historical two-name counterexample must be reviewed after a refactor'
    namespace, network, expected = case((PAIR_A, PAIR_B))
    exec(compile(tree, str(ENGINE), 'exec'), namespace)
    assert namespace['known_supplier_calendars'] == expected
    assert namespace['lanes'] is not network
    assert namespace['propagate_demand_rates']({('depot', 'PF'): 17}, namespace['lanes']) == {
        ('depot', 'PF'): 17}
    assert len(network) == 4  # Values survive, but the live network binding was lost.
