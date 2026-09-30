"""Independent sourcing oracles, entirely in memory.

Roles are supplied explicitly; these cases do not infer supplier roles from
price, nor certify the unidentified real purchasing policy.
"""
from copy import deepcopy
from datetime import date, timedelta

import pytest

from etudecas.simulation.engine.mrp_planning import (
    FirmReceipt, LotSizing, Requirement, SupplierOffer, plan_dated_requirements,
    plan_sourced_requirements,
)
from etudecas.simulation.engine.run_first_simulation import (
    resolve_sourcing_policies, supplier_receipt_available_day,
)


def offers(*, primary_lead=75, backup_lead=40, primary_lot=6000, backup_lot=4000):
    return (
        SupplierOffer('VD0951020A', 1.58, 'EUR', 'KG', primary_lead,
            LotSizing(minimum=primary_lot, multiple=primary_lot)),
        SupplierOffer('VD0519670A', 4.20, 'EUR', 'KG', backup_lead,
            LotSizing(minimum=backup_lot, multiple=backup_lot)),
    )


def sourcing(requirements, *, stock=0, firms=(), day=0, options=None, protected=()):
    primary, backup = options or offers()
    return plan_sourced_requirements(decision_day=day, available_qty=stock,
        requirements=requirements, firm_receipts=firms, primary=primary, backups=(backup,),
        protected_backup_receipt_ids=protected)


def quantities(plan, role):
    return sum(p.proposal.qty for p in plan.proposals if p.role == role)


def source_calendar(delivery_days, through_day):
    result = []
    for release in range(through_day + 1):
        cursor = date(2025, 1, 1) + timedelta(days=release + delivery_days)
        remaining = 13
        while remaining:
            cursor += timedelta(days=1)
            if cursor.weekday() < 5:
                remaining -= 1
        result.append((release, (cursor - date(2025, 1, 1)).days))
    return tuple(result)


def assert_manual_conservation(result, stock, firms, requirements):
    total_in = stock + sum(r.qty for r in firms) + sum(p.proposal.qty for p in result.proposals)
    assert result.plan.closing_projected_qty == pytest.approx(total_in - sum(r.qty for r in requirements))
    assert sum(a.qty for a in result.plan.allocations) == pytest.approx(sum(r.qty for r in requirements))
    assert result.plan.proposed_qty == pytest.approx(sum(p.proposal.qty for p in result.proposals))


@pytest.mark.parametrize('physical_day, expected_date, expected_day', [
    (56, date(2025, 3, 17), 75),
    (21, date(2025, 2, 10), 40),
])
def test_sourcing_source_delivery_plus_receipt_calendar(physical_day, expected_date, expected_day):
    # Independent weekday loop: no holiday exclusions are claimed by this candidate.
    cursor, remaining = date(2025, 1, 1) + timedelta(days=physical_day), 13
    while remaining:
        cursor += timedelta(days=1)
        if cursor.weekday() < 5:
            remaining -= 1
    assert cursor == expected_date
    assert (cursor - date(2025, 1, 1)).days == expected_day
    assert supplier_receipt_available_day(physical_day, 13, origin_date='2025-01-01') == expected_day


def test_sourcing_primary_covers_a_timely_physical_requirement_without_backup():
    requirements = [Requirement('physical', 90, 3000)]
    result = sourcing(requirements)
    assert quantities(result, 'primary') == 6000
    assert quantities(result, 'backup') == 0
    assert result.primary_available_day == 75
    assert result.physical_shortage_before_primary_qty == 0
    assert [(p.proposal.release_day, p.proposal.available_day) for p in result.proposals] == [(15, 90)]
    assert_manual_conservation(result, 0, (), requirements)


def test_sourcing_stock_already_covers_early_consumption_without_any_purchase():
    requirements = [Requirement('physical', 20, 1000)]
    result = sourcing(requirements, stock=1000)
    assert result.proposals == ()
    assert result.backup_proposed_qty == 0
    assert_manual_conservation(result, 1000, (), requirements)


def test_sourcing_backup_lot_surplus_covers_later_requirement_before_primary_recalculation():
    requirements = [Requirement('physical-early', 50, 3000), Requirement('physical-later', 100, 1000)]
    result = sourcing(requirements)
    assert quantities(result, 'backup') == 4000
    assert quantities(result, 'primary') == 0
    assert result.backup_proposed_qty == 4000
    assert all(p.proposal.available_day <= 50 for p in result.proposals)
    assert result.plan.late_qty == 0
    assert_manual_conservation(result, 0, (), requirements)


def test_sourcing_reserve_alone_never_triggers_backup():
    requirements = [Requirement('reserve:M-1810:item:001848', 20, 3000)]
    result = sourcing(requirements)
    assert quantities(result, 'backup') == 0
    assert quantities(result, 'primary') == 6000
    assert result.physical_shortage_before_primary_qty == 0
    assert_manual_conservation(result, 0, (), requirements)


def test_sourcing_backup_for_physical_consumption_is_not_absorbed_by_earlier_reserve():
    requirements = [Requirement('reserve:technical-protection', 1, 3000), Requirement('physical', 50, 3000)]
    result = sourcing(requirements)
    physical = [a for a in result.plan.allocations if a.requirement_id == 'physical']
    assert sum(a.qty for a in physical) == 3000
    assert all(a.available_day <= 50 and a.delay_days == 0 for a in physical)
    backup_ids = {p.proposal.proposal_id for p in result.proposals if p.role == 'backup'}
    assert all(a.supply_id in backup_ids for a in physical)
    assert quantities(result, 'backup') == 4000
    assert quantities(result, 'primary') == 6000
    assert_manual_conservation(result, 0, (), requirements)


def test_sourcing_sufficient_existing_commitment_prevents_backup():
    requirements = [Requirement('physical', 50, 3000)]
    firms = [FirmReceipt('already-placed', 45, 6000)]
    result = sourcing(requirements, firms=firms)
    assert result.proposals == ()
    assert result.retained_firm_qty == 6000
    assert {(a.supply_id, a.available_day) for a in result.plan.allocations} == {('already-placed', 45)}
    assert_manual_conservation(result, 0, firms, requirements)


def test_sourcing_backup_that_arrives_after_an_existing_firm_does_not_improve_shortage():
    options = offers(primary_lead=75, backup_lead=40, primary_lot=1, backup_lot=1)
    requirements = [Requirement('physical', 20, 100)]
    firms = [FirmReceipt('already-placed', 30, 100)]
    result = sourcing(requirements, firms=firms, options=options)
    assert result.proposals == ()
    assert result.backup_proposed_qty == 0
    assert result.plan.late_qty == 100
    assert result.plan.late_qty_days == 1000
    assert_manual_conservation(result, 0, firms, requirements)


def test_sourcing_backup_bridge_keeps_late_firm_and_exposes_surplus():
    options = offers(primary_lead=75, backup_lead=40, primary_lot=1, backup_lot=1)
    requirements = [Requirement('physical', 20, 100)]
    firms = [FirmReceipt('already-placed', 70, 100)]
    saved = deepcopy((requirements, firms))
    result = sourcing(requirements, firms=firms, options=options)
    assert quantities(result, 'backup') == 100
    assert quantities(result, 'primary') == 0
    assert result.retained_firm_qty == 100
    assert result.bridge_surplus_qty == 100
    assert result.plan.closing_projected_qty == 100
    assert result.plan.late_qty_days == 2000
    assert (requirements, firms) == saved
    assert_manual_conservation(result, 0, firms, requirements)


def test_sourcing_next_review_keeps_committed_backup_without_buying_it_again():
    options = offers(primary_lead=75, backup_lead=40, primary_lot=1, backup_lot=1)
    requirements = [Requirement('physical', 20, 100)]
    firms = [FirmReceipt('late-primary', 70, 100), FirmReceipt('committed-backup', 40, 100)]
    result = sourcing(requirements, firms=firms, options=options, day=1)
    assert result.proposals == ()
    assert result.retained_firm_qty == 200
    assert result.plan.closing_projected_qty == 100
    assert_manual_conservation(result, 0, firms, requirements)


def test_sourcing_delayed_committed_backup_is_not_bought_again_at_nominal_lead():
    options = offers(primary_lead=75, backup_lead=40, primary_lot=1, backup_lot=1)
    requirements = [Requirement('physical', 20, 100)]
    firms = [FirmReceipt('late-primary', 100, 100), FirmReceipt('committed-backup', 80, 100)]
    result = sourcing(requirements, firms=firms, options=options, day=1, protected=('committed-backup',))
    assert result.proposals == ()
    assert result.retained_firm_qty == 200
    assert result.plan.closing_projected_qty == 100
    assert result.plan.late_qty_days == 6000
    assert_manual_conservation(result, 0, firms, requirements)


def test_sourcing_unknown_protected_commitment_is_not_silently_invented():
    with pytest.raises(ValueError):
        sourcing([Requirement('physical', 20, 100)], protected=('missing-order',))


def test_sourcing_backup_not_faster_than_primary_is_not_selected():
    result = sourcing([Requirement('physical', 20, 100)], options=offers(primary_lead=30, backup_lead=40))
    assert quantities(result, 'backup') == 0
    assert quantities(result, 'primary') == 6000


def test_sourcing_cost_rank_conflicting_with_named_policy_is_rejected_not_swapped():
    primary = SupplierOffer('explicit-primary', 5, 'EUR', 'KG', 75, LotSizing(multiple=6000))
    backup = SupplierOffer('explicit-backup', 1, 'EUR', 'KG', 40, LotSizing(multiple=4000))
    # The candidate policy explicitly names cheapest primary; conflicting
    # metadata must fail instead of inventing a new role for another supplier.
    with pytest.raises(ValueError):
        sourcing([Requirement('physical', 90, 3000)], options=(primary, backup))


def test_sourcing_offer_calendar_uses_provided_availability_without_adding_lead_twice():
    primary = SupplierOffer('primary', 1.58, 'EUR', 'KG', 56, LotSizing(multiple=6000), source_calendar(56, 40))
    backup = SupplierOffer('backup', 4.2, 'EUR', 'KG', 21, LotSizing(multiple=4000), source_calendar(21, 40))
    result = sourcing([Requirement('physical', 40, 3000)], options=(primary, backup))
    assert result.primary_available_day == 75
    assert [(p.proposal.release_day, p.proposal.available_day, p.proposal.qty) for p in result.proposals] == [(0, 40, 4000)]


def test_sourcing_receipt_calendar_accepts_weekend_plateau_without_moving_receipts():
    dates = source_calendar(56, 78)
    assert dates[2:5] == ((2, 77), (3, 77), (4, 77))
    primary = SupplierOffer('primary', 1.58, 'EUR', 'KG', 56, LotSizing(multiple=6000), dates)
    backup = SupplierOffer('backup', 4.2, 'EUR', 'KG', 21, LotSizing(multiple=4000), source_calendar(21, 78))
    result = sourcing([Requirement('physical', 78, 3000)], options=(primary, backup))
    assert quantities(result, 'backup') == 0
    assert [(p.proposal.release_day, p.proposal.available_day) for p in result.proposals] == [(5, 78)]


def test_sourcing_incomplete_explicit_calendar_does_not_impute_missing_release_dates():
    primary = SupplierOffer('primary', 1.58, 'EUR', 'KG', 56, LotSizing(multiple=6000), ((0, 75), (1, 76)))
    backup = SupplierOffer('backup', 4.2, 'EUR', 'KG', 21, LotSizing(multiple=4000), ((0, 40), (1, 41)))
    with pytest.raises(ValueError):
        sourcing([Requirement('physical', 40, 3000)], options=(primary, backup))


def test_sourcing_legacy_pure_planner_still_nets_late_commitments_without_bridge():
    # This protects the previous pure API. Runtime absence-policy scope is
    # additionally verified by independent graph and complete witness CSV checks.
    result = plan_dated_requirements(decision_day=0, available_qty=0,
        requirements=[Requirement('physical', 20, 100)],
        firm_receipts=[FirmReceipt('existing', 70, 100)], lead_days=75)
    assert result.proposals == ()
    assert result.late_qty_days == 5000


def source_policy_inputs():
    pair = ('M-1810', 'item:001848')
    primary, backup = 'SDC-VD0951020A', 'SDC-VD0519670A'
    payload = {'schema_version': 1, 'rows': [{'policy_id': 'confirmed-001848',
        'node_id': pair[0], 'item_id': pair[1], 'uom': 'KG', 'currency': 'EUR',
        'policy': 'cheapest_purchase_primary_with_dated_backup', 'confirmation': 'user_confirmed_roles_only',
        'backup_trigger': 'physical_shortage_before_primary', 'bridge_surplus_policy': 'retain_firm_and_disclose_surplus',
        'primary_supplier_id': primary, 'backup_supplier_ids': [backup], 'offers': [
            {'supplier_id': primary, 'purchase_unit_cost': 1.58, 'price_uom': 'KG', 'currency': 'EUR',
                'source_file': '268091.xlsx', 'source_cells': 'FIA!C4:H4'},
            {'supplier_id': backup, 'purchase_unit_cost': 4.2, 'price_uom': 'KG', 'currency': 'EUR',
                'source_file': '268091.xlsx', 'source_cells': 'FIA!C3:H3'},
        ]}]}
    lanes = {pair: [{'src': primary, 'unit_purchase_cost': 1.58}, {'src': backup, 'unit_purchase_cost': 4.2}]}
    return payload, lanes, {pair[1]: 'KG'}


@pytest.mark.parametrize('mode', ['historical', 'dated'])
def test_sourcing_absent_policy_does_not_enable_any_new_supplier_logic(mode):
    _, lanes, units = source_policy_inputs()
    assert resolve_sourcing_policies(None, execution_mode=mode, lanes_by_dest_item=lanes, item_unit_map=units) == {}


def test_sourcing_resolver_enables_only_the_explicit_confirmed_pair_without_mutation():
    payload, lanes, units = source_policy_inputs()
    saved = deepcopy((payload, lanes, units))
    result = resolve_sourcing_policies(payload, execution_mode='dated', lanes_by_dest_item=lanes, item_unit_map=units)
    assert set(result) == {('M-1810', 'item:001848')}
    assert (payload, lanes, units) == saved


@pytest.mark.parametrize('item', ['item:001893', 'item:021081'])
def test_sourcing_resolver_refuses_generalization_of_roles_to_other_materials(item):
    payload, lanes, units = source_policy_inputs()
    payload['rows'][0]['item_id'] = item
    with pytest.raises(ValueError):
        resolve_sourcing_policies(payload, execution_mode='dated', lanes_by_dest_item=lanes, item_unit_map=units)


@pytest.mark.parametrize('bad', [None, float('nan'), float('inf'), -1, True])
def test_sourcing_rejects_unknown_or_invalid_purchase_cost(bad):
    primary, backup = offers()
    with pytest.raises(ValueError):
        invalid = SupplierOffer('invalid', bad, 'EUR', 'KG', 75)
        sourcing([Requirement('physical', 90, 100)], options=(invalid, backup))


@pytest.mark.parametrize('currency,uom', [('USD', 'KG'), ('EUR', 'G')])
def test_sourcing_rejects_unconverted_currency_or_quantity_units(currency, uom):
    primary, _ = offers()
    with pytest.raises(ValueError):
        backup = SupplierOffer('backup', 4.2, currency, uom, 40)
        sourcing([Requirement('physical', 20, 100)], options=(primary, backup))
