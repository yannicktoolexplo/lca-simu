"""Independent in-memory candidate batching oracles, without source mutation."""
from copy import deepcopy

import pytest

from etudecas.simulation.engine.mrp_planning import FirmReceipt, LotSizing, Requirement, plan_dated_requirements
from etudecas.simulation.engine.run_first_simulation import mrp_purchase_order_quantity, resolve_procurement_batching


def plan(needs, *, window=None, multiple=100, stock=0, firms=(), day=0, lead=10):
    return plan_dated_requirements(decision_day=day, available_qty=stock,
        requirements=needs, firm_receipts=firms, lead_days=lead,
        lot_sizing=LotSizing(multiple=multiple), grouping_days=window)


def schedule(result):
    return [(r.release_day, r.available_day, r.qty) for r in result.proposals]


def conserved(result, needs, stock=0, firms=()):
    assert result.closing_projected_qty == pytest.approx(stock + sum(r.qty for r in firms)
        + sum(r.qty for r in result.proposals) - sum(r.qty for r in needs))
    assert sum(r.qty for r in result.allocations) == pytest.approx(sum(r.qty for r in needs))


def test_batching_no_policy_preserves_existing_manual_dated_plan():
    needs = [Requirement('a', 100, 60), Requirement('b', 110, 60), Requirement('c', 114, 60)]
    omitted = plan_dated_requirements(decision_day=0, available_qty=0, requirements=needs,
        firm_receipts=(), lead_days=10, lot_sizing=LotSizing(multiple=100))
    explicit_none = plan(needs, window=None)
    assert omitted == explicit_none
    assert schedule(omitted) == [(90, 100, 100), (100, 110, 100)]
    assert omitted.procurement_groups == ()
    conserved(omitted, needs)


def test_batching_rounding_only_1000_retains_first_shortage_date_and_surplus():
    needs = [Requirement('a', 100, 60), Requirement('b', 110, 60), Requirement('c', 114, 60)]
    result = plan(needs, window=0, multiple=1000)
    assert schedule(result) == [(90, 100, 1000)]
    assert result.closing_projected_qty == 820
    assert result.late_qty == 0
    conserved(result, needs)


def test_batching_14_day_group_is_half_open_and_previous_lot_surplus_is_reused():
    needs = [Requirement('a', 100, 60), Requirement('b', 110, 60), Requirement('c', 114, 60)]
    saved = deepcopy(needs)
    result = plan(needs, window=14)
    assert schedule(result) == [(90, 100, 200)]
    assert result.closing_projected_qty == 20
    first = result.procurement_groups[0]
    assert first.first_requirement_day == 100
    assert first.window_end_day_exclusive == 114
    assert set(first.requirement_ids) == {'a', 'b'}
    assert first.physical_net_qty == first.net_requirement_qty == 120
    assert first.reserve_net_qty == 0
    assert first.proposed_qty == 200
    assert needs == saved
    conserved(result, needs)


def test_batching_requirement_on_exclusive_boundary_creates_a_separate_group_when_needed():
    needs = [Requirement('a', 100, 100), Requirement('b', 113, 100), Requirement('boundary', 114, 100)]
    result = plan(needs, window=14)
    assert schedule(result) == [(90, 100, 200), (104, 114, 100)]
    assert [set(g.requirement_ids) for g in result.procurement_groups] == [{'a', 'b'}, {'boundary'}]
    conserved(result, needs)


def test_batching_28_days_does_not_mean_a_fixed_review_calendar():
    needs = [Requirement('a', 100, 100), Requirement('b', 120, 100), Requirement('c', 127, 100), Requirement('d', 130, 100)]
    result = plan(needs, window=28)
    assert schedule(result) == [(90, 100, 300), (120, 130, 100)]
    assert [g.first_requirement_day for g in result.procurement_groups] == [100, 130]
    assert [g.window_end_day_exclusive for g in result.procurement_groups] == [128, 158]
    conserved(result, needs)


@pytest.mark.parametrize('window', [0, 14, 28])
def test_batching_late_firm_is_netted_and_not_rebought(window):
    needs = [Requirement('early', 3, 50), Requirement('later', 7, 50)]
    firms = [FirmReceipt('existing', 5, 60)]
    saved = deepcopy((needs, firms))
    result = plan(needs, window=window, multiple=1000, stock=20, firms=firms, lead=2)
    assert schedule(result) == [(5, 7, 1000)]
    assert result.late_qty == 30
    assert result.late_qty_days == 60
    assert result.closing_projected_qty == 980
    assert (needs, firms) == saved
    conserved(result, needs, stock=20, firms=firms)


def test_batching_existing_stock_and_firms_can_cover_all_groups_without_new_purchase():
    needs = [Requirement('a', 100, 60), Requirement('b', 110, 60)]
    firms = [FirmReceipt('existing', 105, 100)]
    result = plan(needs, window=28, multiple=1000, stock=60, firms=firms)
    assert result.proposals == ()
    assert result.procurement_groups == ()
    conserved(result, needs, stock=60, firms=firms)


def test_batching_committed_group_is_not_bought_again_on_next_daily_review():
    needs = [Requirement('a', 100, 60), Requirement('b', 110, 60), Requirement('c', 114, 60)]
    result = plan(needs, window=14, firms=[FirmReceipt('committed-group', 100, 200)], day=91)
    assert result.proposals == ()
    assert result.closing_projected_qty == 20
    assert result.late_qty == 0


def test_batching_reserve_is_counted_once_and_separately_from_physical_need():
    needs = [Requirement('physical-a', 100, 60), Requirement('reserve:unchanged-target', 110, 40), Requirement('physical-b', 114, 60)]
    saved = deepcopy(needs)
    result = plan(needs, window=14)
    assert schedule(result) == [(90, 100, 100), (104, 114, 100)]
    first = result.procurement_groups[0]
    assert (first.physical_net_qty, first.reserve_net_qty, first.net_requirement_qty) == (60, 40, 100)
    assert sum(g.reserve_net_qty for g in result.procurement_groups) == 40
    assert needs == saved
    conserved(result, needs)


def test_batching_earliest_infeasible_need_is_not_delayed_further_by_grouping():
    needs = [Requirement('a', 100, 60), Requirement('b', 110, 60)]
    result = plan(needs, window=14, lead=103)
    assert schedule(result) == [(0, 103, 200)]
    early = [a for a in result.allocations if a.requirement_id == 'a']
    assert sum(a.qty for a in early) == 60
    assert all(a.available_day == 103 for a in early)
    assert result.late_qty_days == 180
    conserved(result, needs)


def test_batching_respects_order_maximum_without_postponing_first_delivery():
    needs = [Requirement('a', 100, 160), Requirement('b', 110, 160)]
    result = plan_dated_requirements(decision_day=0, available_qty=0, requirements=needs,
        firm_receipts=(), lead_days=10, lot_sizing=LotSizing(multiple=100, maximum=200), grouping_days=14)
    assert sum(r.qty for r in result.proposals) == 400
    assert all(r.qty <= 200 and r.qty % 100 == 0 and r.available_day == 100 for r in result.proposals)
    conserved(result, needs)


def batching_policy_inputs():
    pair = ('M-1810', 'item:001757')
    payload = {'schema_version': 1, 'rows': [{'policy_id': 'test-001757-1000-14',
        'node_id': pair[0], 'item_id': pair[1], 'uom': 'KG', 'rounding_multiple_qty': 1000,
        'grouping_days': 14, 'semantics': 'first_uncovered_requirement_forward_window', 'status': 'candidate_sensitivity'}]}
    lanes = {pair: [{'src': 'SDC-VD0951020A', 'physical_dispatch_multiple': 0}]}
    return payload, lanes, {pair[1]: 'KG'}


@pytest.mark.parametrize('mode', ['historical', 'dated'])
def test_batching_absent_policy_keeps_legacy_scope(mode):
    _, lanes, units = batching_policy_inputs()
    assert resolve_procurement_batching(None, execution_mode=mode, lanes_by_dest_item=lanes, item_unit_map=units) == {}


def test_batching_policy_does_not_modify_source_lane_or_safety_data():
    payload, lanes, units = batching_policy_inputs()
    lanes[('M-1810', 'item:001757')][0].update(standard_order_qty=100, lead_reference_days=84, safety_time_source_days=20)
    saved = deepcopy((payload, lanes, units))
    result = resolve_procurement_batching(payload, execution_mode='dated', lanes_by_dest_item=lanes, item_unit_map=units)
    assert set(result) == {('M-1810', 'item:001757')}
    assert (payload, lanes, units) == saved


@pytest.mark.parametrize('change', [
    {'item_id': 'item:001848'}, {'uom': 'G'}, {'status': 'industrial_rule'},
    {'grouping_days': 7}, {'rounding_multiple_qty': 500},
])
def test_batching_scope_rejects_unsupported_or_mislabeled_candidates(change):
    payload, lanes, units = batching_policy_inputs()
    payload['rows'][0].update(change)
    with pytest.raises(ValueError):
        resolve_procurement_batching(payload, execution_mode='dated', lanes_by_dest_item=lanes, item_unit_map=units)


@pytest.mark.parametrize('available,expected', [(0, 0), (999, 0), (1000, 1000), (1500, 1000), (2000, 2000)])
def test_batching_larger_multiple_does_not_create_stock_or_override_capacity(available, expected):
    actual = mrp_purchase_order_quantity(3000, available, 1000, binding=True, uom='KG')
    assert actual == expected
    assert actual <= available


def test_batching_fractional_forecasts_do_not_create_a_phantom_physical_unit():
    needs = [Requirement(f'forecast-{i}', 100 + i, .1) for i in range(30)]
    result = plan_dated_requirements(decision_day=0, available_qty=3, requirements=needs,
        firm_receipts=(), lead_days=10, lot_sizing=LotSizing(multiple=1, integer=True), grouping_days=14)
    assert result.proposals == ()
    assert result.closing_projected_qty == 0


@pytest.mark.parametrize('invalid', [-1, True, 1.5, '14', float('nan')])
def test_batching_rejects_unknown_or_non_integer_group_window(invalid):
    with pytest.raises(ValueError):
        plan([Requirement('a', 100, 1)], window=invalid)
