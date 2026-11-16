"""Source measurement scope is distinct from inferred residual attribution."""
import json

import pytest

from etudecas.simulation.current_reference import runtime_observed_type
from etudecas.simulation.reference_mrp.historical_adapter import (
    SCAN3_RESIDUAL_PROVENANCE_SCHEMA_VERSION, f3_module, tracker_for,
)
from etudecas.testing.independent_review import Evidence, declared_scan3_requirements


@pytest.mark.parametrize('cumulative', [False, True])
def test_native_residual_provenance_is_explicit_without_changing_physical_requirement(cumulative):
    source = dict(budget_id='plant:component:R1', node_id='plant', item_id='component',
        source_row=1, first_day=5, end_day_exclusive=12, closing_day=11, covered_days=7,
        covered_scan3_qty=100, full_week_scan3_qty=100, raw_signed_scan3_qty=-100,
        uom='UN', source_file='observations.xlsx', scan3_source_cell='Sheet!J1',
        source_week_marker='2025-01-05', partial_week=False,
        include_in_main_source_balance=True, coverage_status='documented_withdrawals')
    pairs = [('plant', 'component')] if cumulative else []
    tracker = tracker_for(f3_module(), [source], pairs)
    tracker.own_withdrawal(day=6, node_id='plant', item_id='component', qty=25,
        event_type='production_consume')
    due = tracker.close(11, {})
    assert due['plant', 'component'][0].qty == 75
    identity = due['plant', 'component'][0].requirement_id
    assert SCAN3_RESIDUAL_PROVENANCE_SCHEMA_VERSION == 2

    class Base:
        def provenance(self, identity, calendar):
            raise AssertionError('Known residual must retain its own source provenance')

    runtime = runtime_observed_type(Base, tracker, None, 20)()
    note = runtime.provenance(identity, None)
    assert note['physical_demand_source'] == 'reconstructed_scan3_residual_not_identified_other_format'
    assert note['known_day'] == 11 and note['source_cells'] == 'Sheet!J1'
    basis = json.loads(note['estimation_basis'])
    if not cumulative:
        assert basis['scan3_scope'] == 'confirmed_reference_scope'
        assert basis['actual_alternate_SKU_scope'] == 'not_identified'
    evidence = Evidence()
    oracle = declared_scan3_requirements(dict(schema_version=1, mode='scan3_residual_v1',
        cumulative_pairs=[list(pair) for pair in pairs]), [source], [dict(day=6,
            node_id='plant', item_id='component', event_type='production_consume', qty=25, uom='UN')],
        20, 'scn:BASE', evidence)
    assert oracle[identity]['qty'] == 75
    assert basis == oracle[identity]['reconciliation_basis']
    assert all(check['failed'] == 0 for check in evidence.checks.values())
    # Inspecting provenance does not close again, consume or create a demand.
    assert tracker.published[source['budget_id']]['residual_executed_qty'] == 0
    assert len(tracker.published) == 1 and tracker.allocations == []
