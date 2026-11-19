"""Whole-kit arithmetic examples in memory, without a synthetic machine rate."""
from copy import deepcopy
from decimal import Decimal
import math

import pytest

from etudecas.simulation.engine.unconstrained_material_launch import (
    UNCONSTRAINED_MATERIAL_KIT_POLICY, assess_unconstrained_material_launch,
)


PAIR = ('plant', 'part')
OUTPUT = ('plant', 'PF')


def _case(**updates):
    result = dict(decision_day=0, batch_qty=100, components=((PAIR, 1.0),),
        available_by_pair={PAIR: 100}, item_uoms={'part': 'UN'},
        firm_receipts=[], other_requirements=[], output_pair=OUTPUT)
    result.update(updates)
    return result


def _order(identity, *, release=0, created=0, quantity=100, output=OUTPUT):
    return dict(order_id=identity, state='frozen', node_id=output[0], item_id=output[1],
        planned_release_day=release, created_day=created, known_day=created, qty=quantity)


def _frozen_need(order, *, pair=PAIR, quantity=100):
    rid = 'frozen_material:' + order['order_id'] + ':' + '|'.join(pair)
    return dict(identity='other_frozen_order_components:' + rid,
        node_id=pair[0], item_id=pair[1], due_day=order['planned_release_day'],
        qty=quantity, known_day=order['known_day'], basis='other_frozen_order_components',
        frozen_order_id=order['order_id'], frozen_output_node_id=order['node_id'],
        frozen_output_item_id=order['item_id'], frozen_component_requirement_id=rid,
        frozen_planned_release_day=order['planned_release_day'], frozen_created_day=order['created_day'])


def _external(qty, *, due=0, known=0, basis='prior_external_backlog'):
    return dict(identity=basis, node_id=PAIR[0], item_id=PAIR[1], due_day=due,
        known_day=known, qty=qty, basis=basis)


def _transition(**updates):
    result = dict(node_id=PAIR[0], item_id=PAIR[1], old_item_id='old_part',
        start_day=0, end_day=5, known_day=0, consume_policy='use_old_until_new_stock_available')
    result.update(updates)
    return result


def test_exact_current_kit_is_admitted_without_capacity_context():
    args = _case()
    before = deepcopy(args)
    result = assess_unconstrained_material_launch(**args)
    assert args == before
    assert result['allowed'] is True and result['applicable'] is True
    assert result['policy'] == UNCONSTRAINED_MATERIAL_KIT_POLICY
    assert result['capacity_reservations'] == []
    assert result['capacity_constraint'] == 'not_modelled_no_shared_daily_rate'
    assert result['work_allocations'] == [dict(day=0, qty=100)]
    assert result['projected_completed_qty'] == 100


def test_campaign_kit_rounds_each_physical_batch_and_preserves_transition_proof():
    # Two lots of5 each consume ceil(5*0.3)=2 units, hence4, not ceil(10*0.3)=3.
    args = _case(batch_qty=10, components=((PAIR, 0.3),),
        physical_batch_quantities=(5, 5), available_by_pair={PAIR: 3})
    refused = assess_unconstrained_material_launch(**args)
    assert refused['allowed'] is False and refused['first_shortage']['required_qty'] == 4
    assert refused['first_shortage']['available_qty'] == 3
    admitted = assess_unconstrained_material_launch(**dict(args, available_by_pair={PAIR: 4}))
    assert admitted['allowed'] is True and admitted['physical_batch_quantities'] == [5, 5]
    # The primary-only substitution proof must retain the same decomposition.
    with_transition = assess_unconstrained_material_launch(**dict(args,
        nonprojectable_substitutions=[_transition()]))
    assert with_transition['allowed'] is False
    with pytest.raises(ValueError, match="exactly partition"):
        assess_unconstrained_material_launch(**dict(args, physical_batch_quantities=(5, 4)))


def test_native_mass_roundoff_gap_is_audited_without_stock_increase():
    args = _case(batch_qty=107800, components=((PAIR, 9.654718),),
        available_by_pair={PAIR: 1040778.6003999999}, item_uoms={'part': 'G'})
    before = deepcopy(args)
    result = assess_unconstrained_material_launch(**args)
    row = result['component_projection'][0]
    # Independent decimal arithmetic: exact source BOM, before float storage.
    assert Decimal(107800) * Decimal('9.654718') == Decimal('1040778.6004')
    assert args == before
    assert result['allowed'] is True
    assert row['batch_issue_qty'] == 1040778.6004000001
    assert row['usable_after_other_requirements'] == 1040778.6003999999
    assert row['shortfall_qty'] == 2e-10
    assert row['material_shortfall'] is False
    assert row['accepted_roundoff_gap_qty'] == 2e-10
    assert row['comparison_roundoff_bound_qty'] == (
        math.ulp(1040778.6003999999) + math.ulp(1040778.6004000001))
    assert row['roundoff_bound']['physical_stock_changed'] is False


def test_real_mass_shortage_and_one_missing_unit_remain_refused():
    mass = assess_unconstrained_material_launch(**_case(batch_qty=107800,
        components=((PAIR, 9.654718),), available_by_pair={PAIR: 1040778.5994},
        item_uoms={'part': 'G'}))
    row = mass['component_projection'][0]
    assert mass['allowed'] is False and row['material_shortfall'] is True
    assert row['shortfall_qty'] > 0.0009
    assert row['shortfall_qty'] > row['comparison_roundoff_bound_qty']
    assert row['accepted_roundoff_gap_qty'] == 0
    units = assess_unconstrained_material_launch(**_case(available_by_pair={PAIR: 99}))
    row = units['component_projection'][0]
    assert units['allowed'] is False and row['shortfall_qty'] == 1
    assert row['comparison_roundoff_bound_qty'] == row['accepted_roundoff_gap_qty'] == 0
    # Coarse ULPs of cancelled large stock/claims cannot create a small kit.
    cancelled = assess_unconstrained_material_launch(**_case(batch_qty=1,
        available_by_pair={PAIR: 1e20}, item_uoms={'part': 'G'},
        other_requirements=[_external(1e20)]))
    row = cancelled['component_projection'][0]
    assert cancelled['allowed'] is False and row['shortfall_qty'] == 1
    assert row['comparison_roundoff_bound_qty'] == 0


def test_native_work_quantization_keeps_bom_roundoff_bounded_and_units_strict():
    from etudecas.simulation.engine.production_component_issues import (
        feasible_cumulative_work, incremental_component_issue,
    )
    from etudecas.simulation.engine.run_first_simulation import production_wip_execution_quantity
    from etudecas.simulation.lot_trace.campaigns import ProductionBatchWip

    mass_stock = 1040778.6003999999
    limits = ((mass_stock, 9.654718, 'G', 0), (107800, 1.0, 'UN', 0),
              (6504868, 60.342, 'UN', 0), (863, 0.008, 'UN', 0))
    quantity = production_wip_execution_quantity(feasible_cumulative_work(107800, 0, limits))
    assert quantity <= 107800
    assert 107800-quantity <= 3 * math.ulp(107800.0)
    theoretical_issues = [incremental_component_issue(0, quantity, ratio, unit, issued)
                         for stock, ratio, unit, issued in limits]
    # This helper computes the BOM request, not the physical stock allocation.
    # The native consumer separately takes min(stock, remaining_request).
    # Its real allocations and end stocks require the independent native run;
    # reproducing that min here would not validate the physical ledger.
    theoretical_mass_gap = max(0.0, theoretical_issues[0] - mass_stock)
    assert theoretical_mass_gap <= math.ulp(theoretical_issues[0]) + math.ulp(mass_stock)
    assert theoretical_issues[1:] == [107800, 6504868, 863]
    assert all(issue <= limit[0] and issue == int(issue)
               for issue, limit in zip(theoretical_issues, limits) if limit[2] == 'UN')
    batch = ProductionBatchWip('micro', 'micro-B001', 'M-1430', 'item:268967', 2, 2, 107800)
    assert batch.add_execution(quantity, []) == quantity
    assert batch.is_complete and batch.target_qty == 107800
    assert batch.executed_qty == quantity  # No synthetic work fills the numerical remainder.


def test_known_due_external_and_initial_obligations_are_protected():
    rows = [_external(20, due=-1), _external(30, basis='initial_order_remaining_components')]
    args = _case(available_by_pair={PAIR: 149}, other_requirements=rows)
    result = assess_unconstrained_material_launch(**args)
    assert result['allowed'] is False
    assert result['first_shortage']['available_qty'] == 99
    assert [r['qty'] for r in result['other_requirements']] == [20, 30]


def test_future_known_demand_is_kept_without_becoming_due_today():
    result = assess_unconstrained_material_launch(**_case(other_requirements=[_external(200, due=3)]))
    assert result['allowed'] is True
    assert result['other_requirements'][0]['due_day'] == 3
    assert result['other_requirements'][0]['qty'] == 200


def test_future_receipt_never_funds_current_material_kit():
    receipt = dict(identity='purchase', node_id='plant', item_id='part',
        available_day=1, known_day=0, origin='external_procurement', qty=1000)
    result = assess_unconstrained_material_launch(**_case(
        available_by_pair={PAIR: 99}, firm_receipts=[receipt]))
    assert result['allowed'] is False and result['first_shortage']['available_qty'] == 99
    assert result['firm_receipts'][0]['funds_current_kit'] is False


@pytest.mark.parametrize('field,value', [('available_day', 0), ('known_day', 1), ('origin', 'estimated')])
def test_invalid_or_already_received_receipt_cannot_be_counted_twice(field, value):
    receipt = dict(identity='purchase', node_id='plant', item_id='part',
        available_day=1, known_day=0, origin='external_procurement', qty=100)
    receipt[field] = value
    with pytest.raises(ValueError):
        assess_unconstrained_material_launch(**_case(firm_receipts=[receipt]))


def test_two_due_orders_can_both_start_on_same_day_with_current_stock():
    first, second = _order('a'), _order('b')
    args = _case(available_by_pair={PAIR: 200}, own_order_id='a',
        frozen_orders=[first, second], other_requirements=[_frozen_need(second)])
    before = deepcopy(args)
    a = assess_unconstrained_material_launch(**args)
    assert args == before and a['allowed'] is True
    assert a['successor_material_obligations'][0]['qty'] == 100
    assert a['successor_material_obligations'][0]['due_day'] == 0
    assert a['successor_material_obligations'][0]['unfunded_current_stock_qty'] == 0
    # Physical execution belongs to the caller: independently debit the first
    # 100 units and remove its now-launched order before evaluating the second.
    b = assess_unconstrained_material_launch(**_case(available_by_pair={PAIR: 100},
        own_order_id='b', frozen_orders=[second]))
    assert b['allowed'] is True
    assert a['projected_finish_day'] == b['projected_finish_day'] == 0
    assert a['projected_completed_qty'] + b['projected_completed_qty'] == 200


def test_unfunded_successor_never_blocks_earlier_order_or_disappears():
    first, second = _order('a'), _order('b')
    a = assess_unconstrained_material_launch(**_case(available_by_pair={PAIR: 150},
        own_order_id='a', frozen_orders=[first, second], other_requirements=[_frozen_need(second)]))
    assert a['allowed'] is True
    obligation = a['successor_material_obligations'][0]
    assert (obligation['frozen_order_id'], obligation['qty'], obligation['due_day']) == ('b', 100, 0)
    assert obligation['unfunded_current_stock_qty'] == 50
    b = assess_unconstrained_material_launch(**_case(available_by_pair={PAIR: 50},
        own_order_id='b', frozen_orders=[second]))
    assert b['allowed'] is False and b['first_shortage']['available_qty'] == 50


def test_later_order_cannot_overtake_earlier_order_without_machine_limit():
    first, second = _order('a'), _order('b')
    result = assess_unconstrained_material_launch(**_case(available_by_pair={PAIR: 1000},
        own_order_id='b', frozen_orders=[first, second], other_requirements=[_frozen_need(first)]))
    assert result['allowed'] is False and result['reason'] == 'earlier_frozen_order_unlaunched'


def test_original_release_date_precedes_lexical_order():
    first, second = _order('z', release=0), _order('a', release=1)
    result = assess_unconstrained_material_launch(**_case(decision_day=1, own_order_id='z',
        frozen_orders=[second, first], available_by_pair={PAIR: 200},
        other_requirements=[_frozen_need(second)]))
    assert result['allowed'] is True
    assert [r['order_id'] for r in result['priority_projection']['priority_orders']] == ['z', 'a']


def test_creation_date_breaks_same_release_tie_before_identifier():
    first, second = _order('z', created=0), _order('a', created=1)
    result = assess_unconstrained_material_launch(**_case(decision_day=1, own_order_id='z',
        frozen_orders=[second, first], available_by_pair={PAIR: 200},
        other_requirements=[_frozen_need(second)]))
    assert result['allowed'] is True
    assert [r['order_id'] for r in result['priority_projection']['priority_orders']] == ['z', 'a']


def test_duplicate_frozen_identity_is_rejected():
    own = _order('a')
    with pytest.raises(ValueError, match='priority metadata'):
        assess_unconstrained_material_launch(**_case(own_order_id='a', frozen_orders=[own, dict(own)]))


def test_fractional_usable_physical_units_are_rejected():
    with pytest.raises(ValueError, match='remain integer'):
        assess_unconstrained_material_launch(**_case(available_by_pair={PAIR: 100.5}))


def test_other_product_due_requirement_stays_protected():
    own, other = _order('a'), _order('b', output=('plant', 'other_PF'))
    result = assess_unconstrained_material_launch(**_case(own_order_id='a',
        frozen_orders=[own, other], other_requirements=[_frozen_need(other)]))
    assert result['allowed'] is False and result['first_shortage']['available_qty'] == 0


def test_own_material_requirement_must_already_be_excluded_once():
    own = _order('a:with:colons')
    with pytest.raises(ValueError, match='excluded exactly once'):
        assess_unconstrained_material_launch(**_case(own_order_id=own['order_id'],
            frozen_orders=[own], other_requirements=[_frozen_need(own)]))


@pytest.mark.parametrize('mutation', ['missing', 'quantity', 'identity', 'date', 'duplicate'])
def test_successor_requirement_cannot_be_erased_or_changed(mutation):
    first, second = _order('a'), _order('b')
    rows = [_frozen_need(second)]
    if mutation == 'missing': rows = []
    elif mutation == 'quantity': rows[0]['qty'] = 99
    elif mutation == 'identity': rows[0]['frozen_component_requirement_id'] = 'wrong'
    elif mutation == 'date': rows[0]['frozen_planned_release_day'] = 3
    else: rows.append(deepcopy(rows[0]))
    with pytest.raises(ValueError):
        assess_unconstrained_material_launch(**_case(own_order_id='a',
            frozen_orders=[first, second], other_requirements=rows))


@pytest.mark.parametrize('field,value', [('known_day', 1), ('created_day', 1), ('qty', 100.5)])
def test_future_or_fractional_frozen_order_is_rejected(field, value):
    own = _order('a'); own[field] = value
    with pytest.raises(ValueError):
        assess_unconstrained_material_launch(**_case(own_order_id='a', frozen_orders=[own]))


def test_current_snapshot_cannot_contain_future_requirement_knowledge():
    with pytest.raises(ValueError, match='not known'):
        assess_unconstrained_material_launch(**_case(other_requirements=[_external(1, known=1)]))


def test_fractional_component_ratio_uses_whole_lot_integer_debit():
    result = assess_unconstrained_material_launch(**_case(batch_qty=101,
        components=((PAIR, 1.5),), available_by_pair={PAIR: 152}))
    assert result['allowed'] is True
    assert result['component_projection'][0]['batch_issue_qty'] == 152


def test_fractional_mass_is_preserved_without_unit_rounding():
    result = assess_unconstrained_material_launch(**_case(batch_qty=101,
        components=((PAIR, 0.25),), item_uoms={'part': 'KG'}, available_by_pair={PAIR: 25.25}))
    assert result['allowed'] is True
    assert result['component_projection'][0]['batch_issue_qty'] == 25.25


def test_all_components_are_checked_before_material_admission():
    result = assess_unconstrained_material_launch(**_case(
        components=((PAIR, 1), (('plant', 'pack'), 1)),
        item_uoms={'part': 'UN', 'pack': 'UN'},
        available_by_pair={PAIR: 100, ('plant', 'pack'): 99}))
    assert result['allowed'] is False and result['first_shortage']['item_id'] == 'pack'


def test_proved_primary_transition_keeps_the_full_kit_check():
    args = _case(nonprojectable_substitutions=[_transition()],
        components=((PAIR, 1), (('plant', 'pack'), 1)),
        item_uoms={'part': 'UN', 'pack': 'UN'},
        available_by_pair={PAIR: 100, ('plant', 'pack'): 99})
    before = deepcopy(args)
    result = assess_unconstrained_material_launch(**args)
    assert args == before
    assert result['applicable'] is True and result['allowed'] is False
    assert result['substitution_projection']['status'] == 'primary_coverage_proved_for_complete_candidate'
    assert result['first_shortage']['item_id'] == 'pack'


def test_unproved_primary_transition_is_a_refusal_not_an_uncapped_bypass():
    result = assess_unconstrained_material_launch(**_case(available_by_pair={PAIR: 99},
        nonprojectable_substitutions=[_transition()]))
    assert result['applicable'] is True and result['allowed'] is False
    assert result['reason'] == 'unproven_primary_material_kit'
    assert result['native_fallback_allowed'] is False


def test_incomplete_transition_is_never_claimed_as_material_certification():
    result = assess_unconstrained_material_launch(**_case(
        nonprojectable_substitutions=[_transition(known_day=1)]))
    assert result['allowed'] is False and result['applicable'] is True
    assert result['substitution_projection']['reason'] == 'unsupported_or_incomplete_transition_metadata'


def test_generator_inputs_are_materialized_once_for_primary_and_complete_checks():
    args = _case(components=iter(((PAIR, 1),)), firm_receipts=iter(()),
        other_requirements=iter(()), frozen_orders=iter(()),
        nonprojectable_substitutions=iter((_transition(),)))
    result = assess_unconstrained_material_launch(**args)
    assert result['allowed'] is True and result['projected_completed_qty'] == 100


def test_existing_dated_policy_keeps_its_unknown_capacity_contract():
    from etudecas.simulation.engine.dated_material_launch import assess_dated_material_launch
    result = assess_dated_material_launch(**_case(), capacity_context=None)
    assert result['applicable'] is False and result['allowed'] is None
    assert result['reason'] == 'unknown_finite_capacity'
