"""Memory-only counterexamples for conditional transition applicability.

Expected stock/issue values below are hand arithmetic on two or three days;
no generated files, source mutation or external simulation is involved.
"""
from copy import deepcopy

import pytest

from etudecas.simulation.engine.dated_material_launch import (
    DATED_MATERIAL_LAUNCH_POLICY, DATED_MATERIAL_PRIORITY_POLICY,
    DATED_MATERIAL_SUBSTITUTION_POLICY, assess_dated_material_launch,
)


def _transition(**changes):
    row = dict(node_id='M', item_id='PRIMARY', old_item_id='OLD', start_day=0,
               end_day=2, known_day=0, consume_policy='use_old_until_new_stock_available')
    row.update(changes)
    return row


def _case(*, primary=6, other=6, batch=6, rate=2, **changes):
    order = dict(order_id='A', node_id='M', item_id='PF', planned_release_day=0,
                 created_day=0, known_day=0, qty=batch, state='frozen')
    args = dict(decision_day=0, batch_qty=batch,
        components=((('M', 'OTHER'), 1), (('M', 'PRIMARY'), 1)),
        available_by_pair={('M', 'OTHER'): other, ('M', 'PRIMARY'): primary},
        item_uoms={'PRIMARY': 'UN', 'OTHER': 'UN'}, firm_receipts=[], other_requirements=[],
        capacity_context=dict(known_day=0, first_work_day=0, capacity_qty=rate,
            current_capacity_qty=rate, closed_days=(), opening_work=(), active_remaining_qty=0,
            frozen_work=(('A', 0, batch),)),
        own_order_id='A', output_pair=('M', 'PF'), frozen_orders=[order],
        policy=DATED_MATERIAL_SUBSTITUTION_POLICY,
        nonprojectable_substitutions=[_transition()])
    args.update(changes)
    return args


def _need(qty, due=2, known=0):
    return dict(identity='known-other-use', node_id='M', item_id='PRIMARY', due_day=due,
                qty=qty, known_day=known, basis='known_external_estimate')


def _receipt(qty, available=2, known=0):
    return dict(identity='firm-receipt', node_id='M', item_id='PRIMARY', available_day=available,
                qty=qty, known_day=known, origin='external_procurement')


def test_primary_exactly_funds_complete_batch_and_inputs_are_unchanged():
    args = _case()
    before = deepcopy(args)
    result = assess_dated_material_launch(**args)
    assert args == before
    assert result['applicable'] and result['allowed']
    proof = result['substitution_projection']
    assert proof['status'] == 'primary_coverage_proved_for_complete_candidate'
    assert proof['checked_work_days'] == 3 and proof['tested_through_day'] == 2
    assert [r['usable_after_other_requirements'] for r in proof['component_projection']] == [6, 4, 2]
    assert [r['batch_issue_qty'] for r in proof['component_projection']] == [2, 2, 2]
    assert result['projected_completed_qty'] == 6


def test_other_component_shortage_does_not_truncate_primary_coverage_proof():
    result = assess_dated_material_launch(**_case(other=0))
    assert result['applicable'] and result['allowed'] is False
    assert result['reason'] == 'dated_material_shortfall'
    assert result['first_shortage']['item_id'] == 'OTHER'
    assert result['first_shortage']['day'] == 0
    assert result['substitution_projection']['checked_work_days'] == 3
    assert result['substitution_projection']['status'] == 'primary_coverage_proved_for_complete_candidate'


def test_later_known_use_invalidates_apparently_sufficient_initial_stock():
    result = assess_dated_material_launch(**_case(other=0, other_requirements=[_need(1)]))
    assert result['applicable'] is False and result['allowed'] is None
    assert result['reason'] == 'dated_substitution_not_projectable'
    proof = result['substitution_projection']
    assert proof['reason'] == 'primary_coverage_not_proved'
    assert proof['first_shortage'] == dict(day=2, node_id='M', item_id='PRIMARY', required_qty=2, available_qty=1)


def test_known_receipt_available_before_last_debit_can_prove_coverage():
    result = assess_dated_material_launch(**_case(primary=5, firm_receipts=[_receipt(1)]))
    assert result['allowed']
    assert [r['usable_after_other_requirements'] for r in result['substitution_projection']['component_projection']] == [5, 3, 2]


def test_received_but_not_yet_usable_quantity_does_not_fund_batch():
    receipt = dict(_receipt(1, available=3), physical_arrival_day=1)
    result = assess_dated_material_launch(**_case(primary=5, firm_receipts=[receipt]))
    assert result['applicable'] is False and result['allowed'] is None
    assert result['substitution_projection']['first_shortage']['day'] == 2
    assert result['substitution_projection']['first_shortage']['available_qty'] == 1


def test_receipt_not_known_at_decision_is_rejected():
    with pytest.raises(ValueError, match='not known at decision'):
        assess_dated_material_launch(**_case(primary=5, firm_receipts=[_receipt(1, known=1)]))


def test_other_need_not_known_at_decision_is_rejected():
    with pytest.raises(ValueError, match='not known at decision'):
        assess_dated_material_launch(**_case(other_requirements=[_need(1, known=1)]))


def test_unsupported_consume_policy_preserves_explicit_bypass():
    result = assess_dated_material_launch(**_case(nonprojectable_substitutions=[_transition(consume_policy='old_first')]))
    assert result['applicable'] is False and result['allowed'] is None
    assert result['substitution_projection']['reason'] == 'unsupported_or_incomplete_transition_metadata'


def test_incomplete_transition_metadata_preserves_explicit_bypass():
    transition = _transition()
    del transition['old_item_id']
    result = assess_dated_material_launch(**_case(nonprojectable_substitutions=[transition]))
    assert result['applicable'] is False and result['allowed'] is None
    assert result['substitution_projection']['reason'] == 'unsupported_or_incomplete_transition_metadata'


def test_future_transition_knowledge_is_not_used_as_a_proof():
    result = assess_dated_material_launch(**_case(nonprojectable_substitutions=[_transition(known_day=1)]))
    assert result['applicable'] is False and result['allowed'] is None
    assert result['substitution_projection']['reason'] == 'unsupported_or_incomplete_transition_metadata'


def test_transition_without_matching_primary_bom_remains_nonprojectable():
    result = assess_dated_material_launch(**_case(nonprojectable_substitutions=[_transition(item_id='UNKNOWN')]))
    assert result['applicable'] is False and result['allowed'] is None
    assert result['substitution_projection']['reason'] == 'unsupported_or_incomplete_transition_metadata'


def test_transition_starting_on_last_work_day_is_included():
    result = assess_dated_material_launch(**_case(nonprojectable_substitutions=[_transition(start_day=2, end_day=3)]))
    assert result['allowed']
    assert result['substitution_projection']['checked_work_days'] == 3


def test_transition_ending_on_launch_day_still_requires_complete_primary_coverage():
    result = assess_dated_material_launch(**_case(primary=5, nonprojectable_substitutions=[_transition(end_day=0)]))
    assert result['applicable'] is False and result['allowed'] is None
    assert result['substitution_projection']['first_shortage']['day'] == 2


def test_transition_starting_after_completion_does_not_change_v2_result():
    args = _case(nonprojectable_substitutions=[_transition(start_day=3, end_day=4)])
    result = assess_dated_material_launch(**args)
    expected = assess_dated_material_launch(**dict(args, policy=DATED_MATERIAL_PRIORITY_POLICY))
    assert result == dict(expected, policy=DATED_MATERIAL_SUBSTITUTION_POLICY)
    assert 'substitution_projection' not in result


def test_integer_component_rounding_uses_cumulative_batch_debits():
    args = _case(primary=2, batch=3, rate=1)
    args['components'] = ((('M', 'PRIMARY'), 0.4),)
    result = assess_dated_material_launch(**args)
    assert result['allowed']
    assert [r['batch_issue_qty'] for r in result['substitution_projection']['component_projection']] == [1, 0, 1]
    assert sum(r['batch_issue_qty'] for r in result['component_projection']) == 2


def test_closed_days_preserve_continuous_work_trajectory_without_fake_pause():
    args = _case()
    args['capacity_context']['closed_days'] = (1,)
    result = assess_dated_material_launch(**args)
    assert result['allowed'] and result['projected_finish_day'] == 3
    assert [r['day'] for r in result['substitution_projection']['component_projection']] == [0, 2, 3]


def test_capacity_refusal_does_not_claim_substitution_coverage():
    args = _case()
    args['capacity_context']['opening_work'] = (('initial', 1, 2),)
    result = assess_dated_material_launch(**args)
    assert result['applicable'] and result['allowed'] is False
    assert result['reason'] == 'known_capacity_commitment_conflict'
    assert result['substitution_projection']['status'] == 'not_evaluated_capacity_or_priority_refusal'
    assert result['substitution_projection']['component_projection'] == []


def test_all_transitions_must_be_proved_before_removing_bypass():
    rows = [_transition(), _transition(item_id='OTHER', old_item_id='OLD2', consume_policy='unknown')]
    result = assess_dated_material_launch(**_case(nonprojectable_substitutions=rows))
    assert result['applicable'] is False and result['allowed'] is None
    assert len(result['substitution_projection']['unsupported']) == 1


def test_generator_inputs_are_materialized_once_for_both_projections():
    args = _case(primary=5, firm_receipts=[_receipt(1)])
    for key in ('components', 'firm_receipts', 'other_requirements', 'frozen_orders', 'nonprojectable_substitutions'):
        args[key] = iter(args[key])
    result = assess_dated_material_launch(**args)
    assert result['allowed'] and result['projected_completed_qty'] == 6
    assert len(result['component_projection']) == 6
    assert len(result['firm_receipts']) == 1


def test_old_policies_keep_early_bypass_and_original_payload():
    for policy in (DATED_MATERIAL_LAUNCH_POLICY, DATED_MATERIAL_PRIORITY_POLICY):
        args = _case(policy=policy)
        result = assess_dated_material_launch(**args)
        assert result['applicable'] is False and result['allowed'] is None
        assert result['reason'] == 'dated_substitution_not_projectable'
        assert result['component_projection'] == []
        assert 'substitution_projection' not in result and 'priority_projection' not in result


def test_successor_obligations_are_retimed_before_primary_proof_without_erasure():
    args = _case()
    successor = dict(args['frozen_orders'][0], order_id='B')
    args['frozen_orders'].append(successor)
    args['capacity_context']['frozen_work'] += (('B', 0, 6),)
    identity = 'frozen_material:B:M|PRIMARY'
    args['other_requirements'] = [dict(identity='other_frozen_order_components:' + identity,
        node_id='M', item_id='PRIMARY', due_day=0, qty=6, known_day=0,
        basis='other_frozen_order_components', frozen_order_id='B', frozen_output_node_id='M',
        frozen_output_item_id='PF', frozen_component_requirement_id=identity,
        frozen_planned_release_day=0, frozen_created_day=0)]
    result = assess_dated_material_launch(**args)
    assert result['allowed']
    assert result['other_requirements'][0]['due_day'] == 3
    assert result['other_requirements'][0]['qty'] == 6
    assert result['successor_material_obligations'][0]['unfunded_qty'] == 6
