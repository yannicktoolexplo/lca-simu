"""Independent sourcing oracles, entirely in memory.

Roles are supplied explicitly; these cases do not infer supplier roles from
price, nor certify the unidentified real purchasing policy.
"""
from copy import deepcopy
from dataclasses import replace
from datetime import date, timedelta

import pytest

from etudecas.simulation_prep.inject_mrp_seed_data_v2 import apply_source_mrp_policy_rows

from etudecas.simulation.engine.mrp_planning import (
    FirmReceipt, LotSizing, Requirement, StockProtection, SupplierOffer, plan_dated_requirements,
    plan_sourced_requirements, IndustrialComponentPlanningCalendar,
    plan_allocated_purchase_requirements, plan_anticipated_requirements,
)
from etudecas.simulation.engine.run_first_simulation import (
    resolve_sourcing_policies, supplier_receipt_available_day, provisional_purchase_weekly_fields,
    resolve_purchase_planning_lots,
    plan_component_network,
)


def test_latest_source_policy_preserves_explicit_zero_and_opening_stock():
    graph = {"nodes": [{"id": "DC-1920", "inventory": {"states": [
        {"item_id": "item:268091", "uom": "UN", "initial": 430538,
         "mrp_policy": {"safety_time_days": 20, "safety_stock_qty": 50}},
        {"item_id": "item:268967", "uom": "UN", "initial": 1101534,
         "mrp_policy": {"safety_time_days": 60}},
    ]}}]}
    rows = [{"Numéro d'article": "268091", "Division": "1920",
             "Délai de sécurité (en jours ouvrés)": "00", "Stock de sécurité": "0",
             "Unité de quantité de base": "ZUN"}]
    original = deepcopy(graph)
    report = apply_source_mrp_policy_rows(graph, rows, source="current/Politique de stock MRP")
    states = graph['nodes'][0]['inventory']['states']
    assert states[0]['initial'] == 430538
    assert states[0]['mrp_policy'] == dict(safety_time_days=0, safety_stock_qty=0,
        safety_stock_uom='UN', source='current/Politique de stock MRP!E2:G2')
    assert states[1] == original['nodes'][0]['inventory']['states'][1]
    assert report[0]['previous_policy']['safety_time_days'] == 20


def test_latest_source_policy_converts_grams_without_changing_days():
    graph = {"nodes": [{"id": "M-1810", "inventory": {"states": [
        {"item_id": "item:049371", "uom": "KG", "initial": 4138.93},
    ]}}]}
    rows = [{"Numéro d'article": "049371", "Division": "1810",
             "Délai de sécurité (en jours ouvrés)": "40", "Stock de sécurité": "888000",
             "Unité de quantité de base": "G"}]
    report = apply_source_mrp_policy_rows(graph, rows, source="current")
    assert report[0]['applied_policy']['safety_stock_qty'] == 888
    assert report[0]['applied_policy']['safety_time_days'] == 40
    assert graph['nodes'][0]['inventory']['states'][0]['initial'] == 4138.93


@pytest.mark.parametrize('invalid', ['duplicate', 'unit', 'missing', 'nan'])
def test_latest_source_policy_rejects_invalid_rows_before_mutation(invalid):
    graph = {"nodes": [{"id": "DC-1920", "inventory": {"states": [
        {"item_id": "item:268091", "uom": "UN", "mrp_policy": {"safety_time_days": 20}},
        {"item_id": "item:268967", "uom": "UN", "mrp_policy": {"safety_time_days": 25}},
    ]}}]}
    first = {"Numéro d'article": "268091", "Division": "1920",
             "Délai de sécurité (en jours ouvrés)": "00", "Stock de sécurité": "0",
             "Unité de quantité de base": "ZUN"}
    second = {**first, "Numéro d'article": "268967"}
    if invalid == 'duplicate': second = dict(first)
    if invalid == 'unit': second['Unité de quantité de base'] = 'KG'
    if invalid == 'missing': second['Délai de sécurité (en jours ouvrés)'] = ''
    if invalid == 'nan': second['Stock de sécurité'] = 'nan'
    original = deepcopy(graph)
    with pytest.raises(ValueError):
        apply_source_mrp_policy_rows(graph, [first, second], source='current')
    assert graph == original


def test_common_additive_network_keeps_same_safety_rule_with_and_without_sourcing():
    """F=2000 is not free stock for two 1500 needs protected at day8."""
    one, two = ('plant', 'single'), ('plant', 'multiple')
    primary, backup = offers(primary_lead=10, backup_lead=5)
    plans, needs, audits = plan_component_network(
        decision_day=0, requirements_by_pair={p: [Requirement('a', 10, 1500), Requirement('b', 10, 1500)] for p in (one, two)},
        available_by_pair={one: 2000, two: 2000}, firm_receipts_by_pair={},
        transport_sources_by_pair={}, bom_by_pair={}, lead_days_by_pair={one: 5, two: 10},
        lot_sizing_by_pair={one: LotSizing(minimum=5000, multiple=5000)},
        reserve_targets_by_pair={}, coverage_days_by_pair={}, active_campaigns_by_pair={},
        sourcing_by_pair={two: dict(primary=primary, backups=(backup,))},
        grouping_days_by_pair={one: 1, two: 1},
        anticipated_need_by_pair={p: dict(source_working_days=2, origin_weekday=0,
            fixed_floor_qty=2000, fixed_floor_mode='additive') for p in (one, two)},
    )
    assert plans[one].proposed_qty == 5000
    assert plans[two].proposed_qty == 4000
    assert audits[two]['sourced_plan'].backup_proposed_qty == 4000
    for pair in (one, two):
        assert sum(r.qty for r in needs[pair]) == 3000  # no physical safety consumption
        assert plans[pair].closing_projected_qty >= 2000
        assert sum(r.qty for r in audits[pair]['anticipated_requirements']) == 5000
        assert all(p.requested_day == 8 for p in plans[pair].proposals)


def test_common_production_target_floor_projects_BOM_before_finished_stock_is_empty():
    """10UN stock -8 demand <6 target =>5UN lot, requiring10KG at launch."""
    fg, rm = ('plant', 'finished'), ('plant', 'raw')
    plans, needs, audits = plan_component_network(
        decision_day=0, requirements_by_pair={fg: [Requirement('sale', 20, 8)]},
        available_by_pair={fg: 10, rm: 0}, firm_receipts_by_pair={},
        transport_sources_by_pair={}, bom_by_pair={fg: [(rm, 2)]},
        lead_days_by_pair={fg: 2, rm: 5},
        lot_sizing_by_pair={fg: LotSizing(minimum=5, multiple=5, integer=True)},
        reserve_targets_by_pair={fg: 6}, coverage_days_by_pair={fg: 30}, active_campaigns_by_pair={},
        protection_by_pair={fg: [StockProtection('controller_target', 1, 6)]},
        production_floor_pairs={fg},
        anticipated_need_by_pair={rm: dict(source_working_days=0, origin_weekday=0,
            fixed_floor_qty=0, fixed_floor_mode='additive')},
    )
    assert [(p.release_day, p.qty) for p in plans[fg].proposals] == [(18, 5)]
    assert [(r.due_day, r.qty) for r in needs[rm]] == [(18, 10)]
    assert [(p.release_day, p.qty) for p in plans[rm].proposals] == [(13, 10)]
    assert plans[fg].closing_projected_qty == 7


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


def provisional_sourcing(requirements, *, day=0, stock=0, firms=(), options=None, backups=True):
    primary, backup = options or offers()
    return plan_sourced_requirements(decision_day=day, available_qty=stock,
        requirements=requirements, firm_receipts=firms, primary=primary,
        backups=(backup,) if backups else (), provisional_lots_until_release=True)


def test_provisional_lot_future_4000_becomes_primary_6000_only_at_release():
    needs = [Requirement('need', 90, 3000)]
    future = provisional_sourcing(needs)
    assert [(r.proposal.qty, r.proposal.release_day, r.proposal.available_day,
             r.supplier_id, r.role) for r in future.proposals] == [(4000, 15, 90, '', 'provisional')]
    assert future.proposals[0].planning_supplier_id == 'VD0951020A'
    due = provisional_sourcing(needs, day=15)
    assert [(r.proposal.qty, r.proposal.release_day, r.supplier_id, r.role)
            for r in due.proposals] == [(6000, 15, 'VD0951020A', 'primary')]
    assert_manual_conservation(future, 0, (), needs)
    assert_manual_conservation(due, 0, (), needs)


def test_provisional_lot_backup_4000_when_primary_is_too_late():
    needs = [Requirement('need', 50, 3000)]
    due = provisional_sourcing(needs, day=10)
    assert [(r.proposal.qty, r.proposal.available_day, r.role) for r in due.proposals] == [(4000, 50, 'backup')]
    assert due.plan.late_qty == 0
    assert_manual_conservation(due, 0, (), needs)


def test_provisional_lot_primary_surplus_nets_next_need_and_committed_order_once():
    needs = [Requirement('first', 90, 3000), Requirement('second', 91, 2500)]
    due = provisional_sourcing(needs, day=15)
    assert [r.proposal.qty for r in due.proposals] == [6000]
    assert due.plan.closing_projected_qty == 500
    firm = [FirmReceipt('executed-primary', 90, 6000)]
    later = provisional_sourcing(needs, day=16, firms=firm)
    assert later.proposals == () and later.plan.closing_projected_qty == 500
    assert_manual_conservation(due, 0, (), needs)
    assert_manual_conservation(later, 0, firm, needs)
    assert provisional_sourcing(needs, day=16, stock=6000).proposals == ()


def test_provisional_lot_monosource_and_disabled_modes_are_identical():
    needs = [Requirement('need', 90, 5000)]
    primary, backup = offers()
    kwargs = dict(decision_day=0, available_qty=0, requirements=needs,
                  firm_receipts=(), primary=primary)
    assert plan_sourced_requirements(**kwargs, backups=()) == provisional_sourcing(needs, backups=False)
    assert plan_sourced_requirements(**kwargs, backups=(backup,)) == plan_sourced_requirements(
        **kwargs, backups=(backup,), provisional_lots_until_release=False)


def test_provisional_lot_physical_units_integer_with_fractional_forecast():
    primary, backup = offers(primary_lead=10, backup_lead=5, primary_lot=6, backup_lot=4)
    primary = replace(primary, uom='UN', lot_sizing=LotSizing(minimum=6, multiple=6, integer=True))
    backup = replace(backup, uom='UN', lot_sizing=LotSizing(minimum=4, multiple=4, integer=True))
    needs = [Requirement('forecast', 20, 3.1)]
    future = provisional_sourcing(needs, options=(primary, backup))
    due = provisional_sourcing(needs, day=10, options=(primary, backup))
    assert [r.proposal.qty for r in future.proposals] == [4]
    assert [r.proposal.qty for r in due.proposals] == [6]
    assert due.plan.closing_projected_qty == pytest.approx(2.9)
    assert_manual_conservation(due, 0, (), needs)


def test_provisional_lot_preserves_nonbinding_supplier_standard():
    primary, backup = offers()
    primary = replace(primary, lot_sizing=LotSizing(), standard_order_qty=6000)
    backup = replace(backup, lot_sizing=LotSizing(), standard_order_qty=4000)
    needs = [Requirement('need', 90, 3000)]
    future = provisional_sourcing(needs, options=(primary, backup))
    due = provisional_sourcing(needs, day=15, options=(primary, backup))
    assert [r.proposal.qty for r in future.proposals] == [4000]
    assert [r.proposal.qty for r in due.proposals] == [3000]
    assert due.plan.closing_projected_qty == 0


def test_provisional_lot_weekly_dates_are_nominal_reference_not_confirmation():
    needs = [Requirement('need', 90, 3000)]
    row = provisional_sourcing(needs).proposals[0]
    fields = provisional_purchase_weekly_fields(row, policy='candidate',
                                               delivery_days_by_supplier={'VD0951020A': 56})
    assert fields['supplier_id'] == ''
    assert fields['planning_supplier_id'] == 'VD0951020A'
    assert fields['physical_receipt_day'] == 71 and fields['available_day'] == 90
    assert fields['receipt_date_basis'] == 'nominal_supplier_reference_not_confirmation'
    assert fields['proposal_stage'] == 'provisional_unreleased'
    assert provisional_purchase_weekly_fields(None, policy='candidate', delivery_days_by_supplier={}) == {}


def aligned_purchase_lot(*, standard=300, dispatch=0, binding=True, uom='KG', lanes=None,
                         selected=None, protected=False, enabled=True):
    pair = ('plant', 'component')
    return resolve_purchase_planning_lots(
        'execution_standard_for_unambiguous_offer_v1' if enabled else None,
        purchase_pairs={pair}, lanes_by_dest_item={pair: lanes if lanes is not None else [
            {'src': 'supplier', 'standard_order_qty': standard, 'physical_dispatch_multiple': dispatch}]},
        selected_suppliers={pair: selected} if selected else {}, protected_pairs={pair} if protected else set(),
        nonbinding_pairs=set() if binding else {pair}, item_unit_map={pair[1]: uom})


@pytest.mark.parametrize('need,standard,expected', [(305, 300, 600), (4001, 4000, 8000)])
def test_purchase_lot_alignment_rounds_like_nominal_execution(need, standard, expected):
    policies, audit = aligned_purchase_lot(standard=standard)
    plan = plan_dated_requirements(decision_day=0, available_qty=0,
        requirements=[Requirement('need', 100, need)], firm_receipts=(), lead_days=20,
        lot_sizing=policies['plant', 'component'])
    assert [p.qty for p in plan.proposals] == [expected]
    assert plan.closing_projected_qty == expected - need
    assert audit[0]['status'] == 'aligned_nominal_execution'


def test_purchase_lot_alignment_uses_rounded_surplus_once():
    policies, _ = aligned_purchase_lot()
    needs = [Requirement('first', 100, 305), Requirement('second', 101, 295)]
    plan = plan_dated_requirements(decision_day=0, available_qty=0,
        requirements=needs, firm_receipts=(), lead_days=20, lot_sizing=policies['plant', 'component'])
    assert len(plan.proposals) == 1 and plan.proposed_qty == 600 and plan.closing_projected_qty == 0
    assert sum(a.qty for a in plan.allocations) == 600


def test_purchase_lot_alignment_nonbinding_identity_and_dispatch_only():
    policies, audit = aligned_purchase_lot(binding=False)
    assert policies['plant', 'component'] == LotSizing()
    assert audit[0]['standard_binding'] is False
    policies, _ = aligned_purchase_lot(binding=False, dispatch=20)
    assert policies['plant', 'component'] == LotSizing(multiple=20)


def test_purchase_lot_alignment_physical_un_is_integer_and_rejects_fractional_lot():
    policies, _ = aligned_purchase_lot(standard=6, uom='UN')
    plan = plan_dated_requirements(decision_day=0, available_qty=0,
        requirements=[Requirement('fractional_forecast', 100, 3.1)], firm_receipts=(), lead_days=20,
        lot_sizing=policies['plant', 'component'])
    assert plan.proposed_qty == 6
    with pytest.raises(ValueError, match='must be integer'):
        aligned_purchase_lot(standard=1.5, uom='UN')


def test_purchase_lot_alignment_selected_offer_only_without_price_inference():
    lanes = [{'src': 'cheap', 'standard_order_qty': 300}, {'src': 'selected', 'standard_order_qty': 500}]
    saved = deepcopy(lanes)
    policies, audit = aligned_purchase_lot(lanes=lanes, selected='selected')
    assert policies['plant', 'component'] == LotSizing(minimum=500, multiple=500)
    assert audit[0]['supplier_id'] == 'selected' and lanes == saved


def test_purchase_lot_alignment_ambiguous_offers_and_specific_policies_preserved():
    lanes = [{'src': 'one', 'standard_order_qty': 300}, {'src': 'two', 'standard_order_qty': 500}]
    policies, audit = aligned_purchase_lot(lanes=lanes)
    assert policies == {} and audit[0]['status'] == 'unchanged_ambiguous_offers'
    policies, audit = aligned_purchase_lot(protected=True)
    assert policies == {} and audit[0]['status'] == 'preserved_specific_policy'


def test_purchase_lot_alignment_disabled_does_not_change_existing_plan():
    policies, audit = aligned_purchase_lot(enabled=False)
    assert policies == {} and audit == []
    existing = LotSizing(integer=True)
    assert policies.get(('plant', 'component'), existing) is existing


def test_purchase_lot_alignment_refuses_incompatible_dispatch_rounding():
    with pytest.raises(ValueError, match='incompatible with the physical dispatch multiple'):
        aligned_purchase_lot(standard=300, dispatch=200)
    policies, _ = aligned_purchase_lot(standard=300, dispatch=100)
    assert policies['plant', 'component'] == LotSizing(minimum=300, multiple=300)


def _known_period_calendar(policy=None):
    """Three in-memory revisions; no files, source mutation or physical demand."""
    pair = ('plant', 'raw')
    def row(start, qty, cell):
        return dict(period_start_day=start, period_days=7, qty=qty,
                    source_file='Flow.xlsx', source_cells=cell)
    payload = dict(schema_version=1, origin='2025-01-01', scenario_id='memory-period-oracle',
        semantics='industrial_total_gross_requirements_planning_only', versioned_series=[dict(
            node_id=pair[0], item_id=pair[1], uom='KG', repeat_period_days=0,
            period_days=7, period_anchor_day=4,
            current_bucket_policy='freeze_previous_exclude_current_vintage',
            missing_future_policy='unprovided_not_observed_zero', versions=[
                dict(known_day=4, rows=[row(18, 70, 'I1'), row(25, 140, 'I2'), row(32, 210, 'I3')]),
                dict(known_day=11, rows=[row(25, 0, 'I4')]),
                dict(known_day=18, rows=[row(25, 280, 'I5')]),
            ])])
    saved = deepcopy(payload)
    calendar = IndustrialComponentPlanningCalendar(payload, pair_uoms={pair: 'KG'},
        origin_date='2025-01-01', missing_period_policy=policy)
    assert payload == saved
    return calendar, pair


def test_known_component_period_survives_omission_but_explicit_zero_replaces_it():
    calendar, pair = _known_period_calendar('last_known_period_v1')
    windows = calendar.windows(pair, decision_day=11, first_day=12, through_day=31)
    assert [(w.period_start_day, w.qty, w.known_day, w.source_cells) for w in windows] == [
        (18, 70, 4, 'I1'), (25, 0, 11, 'I4')]


def test_known_component_period_legacy_policy_is_unchanged():
    calendar, pair = _known_period_calendar()
    windows = calendar.windows(pair, decision_day=11, first_day=12, through_day=31)
    assert [(w.period_start_day, w.qty, w.known_day) for w in windows] == [(25, 0, 11)]


@pytest.mark.parametrize('decision, expected', [(17, 0), (18, 280)])
def test_known_component_period_uses_revision_only_when_known(decision, expected):
    calendar, pair = _known_period_calendar('last_known_period_v1')
    windows = calendar.windows(pair, decision_day=decision, first_day=25, through_day=31)
    assert len(windows) == 1 and windows[0].qty == expected
    assert windows[0].known_day <= decision


def test_known_component_period_keeps_current_week_frozen_and_prorates_remaining_days():
    calendar, pair = _known_period_calendar('last_known_period_v1')
    windows = calendar.windows(pair, decision_day=18, first_day=19, through_day=45)
    # Six remaining days at10kg/day; then a revised40kg/day week, then30kg/day.
    # The final never-supplied week remains absent, not an invented zero/window.
    assert [(w.period_start_day, w.qty, w.known_day) for w in windows] == [
        (18, 60, 4), (25, 280, 18), (32, 210, 4)]
    assert sum(w.qty for w in windows) == 550


def test_known_component_period_never_uses_first_forecast_before_knowledge_date():
    calendar, pair = _known_period_calendar('last_known_period_v1')
    assert calendar.windows(pair, decision_day=3, first_day=18, through_day=38) == ()


@pytest.mark.parametrize('policy', ['', 'guess', False, 1])
def test_known_component_period_rejects_an_undeclared_policy(policy):
    with pytest.raises(ValueError, match='missing-period policy'):
        _known_period_calendar(policy)


def allocated_offers(*, integer=False):
    """Explicit execution order: deliberately neither price nor lead ranking."""
    return tuple(SupplierOffer(identity, cost, 'EUR', 'UN' if integer else 'KG', lead,
        LotSizing(minimum=standard, multiple=standard, integer=integer))
        for identity, cost, lead, standard in [
            ('first-in-legacy-order', 9, 62, 23920),
            ('cheaper-second', 1, 90, 20900),
            ('faster-third', 5, 55, 22800)])


def allocated_plan(needs, *, stock=0, firms=(), day=49, options=None, weights=(70, 20, 10), grouping=None):
    return plan_allocated_purchase_requirements(decision_day=day, available_qty=stock,
        requirements=needs, firm_receipts=firms, offers=options or allocated_offers(),
        allocation_weights=weights, grouping_days=grouping)


def test_allocated_purchase_740_uses_first_actual_lot_and_its_62_day_calendar():
    needs = [Requirement('industrial-need', 139, 740)]
    result = allocated_plan(needs)
    # 740 *70%=518; ceil(518/23920)*23920=23920 covers the whole need.
    # Supplier1 lead62 =>139-62=77, not day49 from the legacy maximum90.
    assert [(r.supplier_id, r.role, r.proposal.qty, r.proposal.release_day,
             r.proposal.available_day) for r in result.proposals] == [
        ('first-in-legacy-order', 'allocated', 23920, 77, 139)]
    assert result.plan.closing_projected_qty == 23180
    assert result.backup_proposed_qty == result.bridge_surplus_qty == 0
    assert_manual_conservation(result, 0, (), needs)


def test_allocated_purchase_large_need_uses_each_suppliers_own_lot_and_dates():
    needs = [Requirement('large', 139, 100000)]
    result = allocated_plan(needs)
    # First70000=>71760, second min(20000,28240)=>20900,
    # third min(10000,7340)=>22800. Sum115460, surplus15460.
    assert [(r.proposal.qty, r.proposal.release_day, r.proposal.available_day)
            for r in result.proposals] == [(71760, 77, 139), (20900, 49, 139), (22800, 84, 139)]
    assert result.plan.closing_projected_qty == 15460
    assert_manual_conservation(result, 0, (), needs)


def test_allocated_purchase_surplus_and_late_commitment_are_netted_exactly_once():
    needs = [Requirement('first', 139, 740), Requirement('later', 160, 23180)]
    result = allocated_plan(needs)
    assert len(result.proposals) == 1 and result.plan.closing_projected_qty == 0
    assert_manual_conservation(result, 0, (), needs)
    firms = [FirmReceipt('already-committed', 170, 23920)]
    committed = allocated_plan(needs, firms=firms)
    assert committed.proposals == () and committed.retained_firm_qty == 23920
    assert committed.plan.late_qty_days == 740 *31 + 23180 *10
    assert_manual_conservation(committed, 0, firms, needs)


def test_allocated_purchase_group_increase_is_bought_once_and_audited_without_duplicate_needs():
    needs = [Requirement('first', 139, 740), Requirement('revised-later', 143, 24000)]
    result = allocated_plan(needs, grouping=7)
    # Group24740: first part17318=>23920, remaining820=>second lot20900.
    assert [r.proposal.qty for r in result.proposals] == [23920, 20900]
    assert result.plan.closing_projected_qty == 20080
    assert len(result.plan.procurement_groups) == 1
    group = result.plan.procurement_groups[0]
    assert group.net_requirement_qty == 24740
    assert group.requirement_ids == ('first', 'revised-later')
    assert group.proposed_qty == 44820
    assert_manual_conservation(result, 0, (), needs)


def test_allocated_purchase_physical_un_remains_integer_with_fractional_forecasts():
    choices = tuple(replace(offer, uom='UN', lot_sizing=LotSizing(minimum=6, multiple=6, integer=True))
                    for offer in allocated_offers())
    needs = [Requirement('forecast-first', 139, 1.1), Requirement('forecast-later', 160, 4.9)]
    result = allocated_plan(needs, options=choices)
    assert [r.proposal.qty for r in result.proposals] == [6]
    assert result.plan.closing_projected_qty == 0
    assert_manual_conservation(result, 0, (), needs)


def test_allocated_anticipation_keeps_floor_once_and_uses_explicit_weekly_offer_calendar():
    # OriginMonday, physical needMonday day14; five working safety days=>day7.
    # Weekly releasesMonday with2 calendar days =>latest usable before7 isday2.
    choice = SupplierOffer('weekly', 1, 'EUR', 'KG', 2, LotSizing(minimum=300, multiple=300),
        tuple((day, day +2) for day in range(0, 29, 7)))
    needs = [Requirement('physical', 14, 305)]
    plan, sourced, audit = plan_anticipated_requirements(decision_day=0, available_qty=100,
        requirements=needs, firm_receipts=(), source_working_days=5, origin_weekday=0,
        fixed_floor_qty=100, fixed_floor_mode='additive', lead_days=99,
        allocated_sourcing=dict(offers=(choice,), allocation_weights=(1,)), grouping_days=7)
    assert [(r.proposal.qty, r.proposal.requested_day, r.proposal.release_day,
             r.proposal.available_day) for r in sourced.proposals] == [(600, 7, 0, 2)]
    assert [(r.due_day, r.qty) for r in audit['anticipated_requirements']] == [(0, 100), (7, 305)]
    assert plan.closing_projected_qty == 395  #100 opening+600 receipt-305 physical
    assert audit['anticipated_plan'].closing_projected_qty == 295
    assert sum(a.qty for a in plan.allocations) == 305
    assert sum(b.requirement_qty for b in plan.balances) == 305


def test_allocated_purchase_zero_weight_uses_ordered_fallback_and_offers_are_not_mutated():
    choices = allocated_offers()
    saved = deepcopy(choices)
    result = allocated_plan([Requirement('need', 139, 740)], options=choices, weights=(0, 0, 0))
    assert [r.supplier_id for r in result.proposals] == ['first-in-legacy-order']
    assert result.plan.proposed_qty == 23920 and choices == saved


def test_allocated_anticipation_optout_is_identical_and_conflicting_modes_are_rejected():
    kwargs = dict(decision_day=0, available_qty=0, requirements=[Requirement('need', 100, 740)],
        firm_receipts=(), source_working_days=5, origin_weekday=0, fixed_floor_qty=0, lead_days=90)
    assert plan_anticipated_requirements(**kwargs) == plan_anticipated_requirements(**kwargs, allocated_sourcing=None)
    allocation = dict(offers=allocated_offers(), allocation_weights=(70, 20, 10))
    with pytest.raises(ValueError, match='mutually exclusive'):
        plan_anticipated_requirements(**kwargs, allocated_sourcing=allocation, sourcing={})
    with pytest.raises(ValueError, match='offer calendars'):
        plan_anticipated_requirements(**kwargs, allocated_sourcing=allocation, exact_release_calendar=((0, 90),))


def test_allocated_purchase_mass_quantum_carries_small_net_need_without_rounding_each_share():
    choices = tuple(replace(offer, lot_sizing=LotSizing(net_rounding_quantum=1))
                    for offer in allocated_offers())
    needs = [Requirement('first', 139, .2), Requirement('later', 140, .4)]
    result = allocated_plan(needs, options=choices)
    # .2 rounds to0, but its residual remains: .2+.4=.6 rounds to1kg.
    # Physical split .7/.2/.1kg remains legal; kg quantum is for the net need.
    assert [r.proposal.qty for r in result.proposals] == [.7, .2, .1]
    assert result.plan.proposed_qty == 1
    assert result.plan.closing_projected_qty == pytest.approx(.4)
    assert_manual_conservation(result, 0, (), needs)


@pytest.mark.parametrize('invalid', ['weights', 'negative_weight', 'duplicate_supplier', 'physical_un', 'calendar'])
def test_allocated_purchase_rejects_ambiguous_or_nonphysical_offer_contracts(invalid):
    choices, weights = allocated_offers(), (70, 20, 10)
    if invalid == 'weights':
        weights = (70, 20)
    elif invalid == 'negative_weight':
        weights = (70, -20, 10)
    elif invalid == 'duplicate_supplier':
        choices = (choices[0], choices[0], choices[2])
    elif invalid == 'physical_un':
        choices = tuple(replace(offer, uom='UN') for offer in choices)
    elif invalid == 'calendar':
        choices = (replace(choices[0], availability_by_release=((49, 48), (139, 201))), *choices[1:])
    with pytest.raises(ValueError):
        allocated_plan([Requirement('need', 139, 740)], options=choices, weights=weights)
