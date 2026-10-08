"""Manual weekly-calendar oracles, entirely in memory; no file fixtures."""
import pytest

from etudecas.visualization.maps.source_comparison import (
    COLUMNS, FLOW_TYPES, _event_unit_evidence, _external_component_rows, _external_component_scope,
    _ledger_quantity_matches, _external_forecast_audit, EXTERNAL_FORECAST_AUDIT_FIELDS,
    _sourcing_order, _sourcing_scope, _batching_order, _batching_scope,
    _projection_rows, _projection_protection_levels, _projection_event_buckets, _internal_component_scope,
    _trace_values, _weekly_rows, _weekly_windows,
    production_availability_events, site_flow_kind,
    _customer_source_rows, _movement_source_rows, _physical_week_rows,
    _customer_week_rows, _customer_forecast_rows,
    _managed_inventory_scopes,
)


def test_managed_inventory_candidate_is_not_confused_with_missing_purchases():
    pair = ('M-1430', 'item:001848')
    row = dict(node_id=pair[0], item_id=pair[1], supply_status='configured_candidate',
               supply_policy={'status': 'candidate_not_inferred_ERP'})
    result = _managed_inventory_scopes({'rows': [row]}, {pair: {'uom': 'KG'}})[pair]
    assert result['supply_status'] == 'configured_candidate'
    assert result['simulation_scope'] == 'partial_simulation'
    assert 'nouveaux achats simulés' in result['supply_limit']
    assert 'Aucun nouvel achat' not in result['supply_limit']
    del row['supply_policy']
    with pytest.raises(ValueError, match='experimental policy'):
        _managed_inventory_scopes({'rows': [row]}, {pair: {'uom': 'KG'}})


def test_managed_inventory_scope_is_partial_without_changing_stock_or_other_sites():
    states = {('M-1430', 'item:001848'): {'initial': 31660.43, 'uom': 'KG'},
              ('M-1810', 'item:001848'): {'initial': 100., 'uom': 'KG'}}
    payload = {'rows': [{'node_id': 'M-1430', 'item_id': 'item:001848',
                         'supply_status': 'unconfigured'}]}
    scopes = _managed_inventory_scopes(payload, states)
    assert set(scopes) == {('M-1430', 'item:001848')}
    assert scopes['M-1430', 'item:001848']['simulation_scope'] == 'partial_simulation'
    assert scopes['M-1430', 'item:001848']['supply_status'] == 'unconfigured'
    assert 'Aucun nouvel achat' in scopes['M-1430', 'item:001848']['supply_limit']
    assert states['M-1430', 'item:001848'] == {'initial': 31660.43, 'uom': 'KG'}
    assert payload['rows'][0] == {'node_id': 'M-1430', 'item_id': 'item:001848',
                                  'supply_status': 'unconfigured'}
    assert _managed_inventory_scopes(None, states) == {}
    assert _managed_inventory_scopes({'rows': []}, states) == {}


@pytest.mark.parametrize('payload', [
    [], {}, {'rows': None}, {'rows': [None]},
    {'rows': [{'node_id': '', 'item_id': 'item:001848', 'supply_status': 'unconfigured'}]},
    {'rows': [{'node_id': 'M-1430', 'item_id': 'item:007923', 'supply_status': 'unconfigured'}]},
    {'rows': [{'node_id': 'M-1430', 'item_id': 'item:001848'}]},
    {'rows': [{'node_id': 'M-1430', 'item_id': 'item:001848', 'supply_status': 'configured'}]},
    {'rows': [{'node_id': 'M-1430', 'item_id': 'item:001848', 'supply_status': 'unconfigured'}] * 2},
])
def test_managed_inventory_scope_rejects_ambiguous_or_unmodeled_status(payload):
    with pytest.raises(ValueError):
        _managed_inventory_scopes(payload, {('M-1430', 'item:001848'): {'uom': 'KG'}})


def test_customer_source_keeps_realized_sign_and_separate_forecast_versions():
    history = [(2, ('268091', 'PF', '2024-12-30', -13)),
               (3, ('268091', 'PF', '2025-01-06', 0))]
    forecasts = [(2, ('268091', 'PF', '2024-12-30', '2025-01-06', -70)),
                 (3, ('268091', 'PF', '2025-01-27', '2025-02-03', -140)),
                 (4, ('268091', 'PF', '2024-12-30', '2025-02-03', -90))]
    result = _customer_source_rows(history, forecasts, {'268091': 'UN'})['268091']
    assert result['history'] == [[-2, 13, -13, 2], [5, 0, 0, 3]]
    assert result['projections']['-2'] == [[5, 70, -70, 2], [33, 90, -90, 4]]
    assert result['projections']['26'] == [[33, 140, -140, 3]]
    assert 'site' not in result


@pytest.mark.parametrize('row', [
    ('268091', 'PF', '2025-01-07', -20),
    ('268091', 'PF', '2025-01-06', 20),
    ('268091', 'PF', '2025-01-06', None),
    ('268091', 'PF', '2025-01-06', -20.5),
])
def test_customer_source_rejects_invalid_sign_monday_missing_and_fractional_units(row):
    with pytest.raises(ValueError):
        _customer_source_rows([(2, row)], [], {'268091': 'UN'})


def test_customer_source_rejects_duplicates_without_adding_versions():
    row = ('268091', 'PF', '2025-01-06', -20)
    with pytest.raises(ValueError, match='Duplicate'):
        _customer_source_rows([(2, row), (3, row)], [], {'268091': 'UN'})


def test_movement_rows_preserve_raw_signed_net_and_g_to_kg():
    pairs = {}
    _movement_source_rows([(2, ('268091', 'PF', 'PF', '1920', '2025-01-05', 'UN', 2, 0, 10, 0)),
                          (3, ('001757', 'MP', 'MP', '1810', '2025-01-05', 'G', 0, 2000, -500, -750))], pairs)
    pf = pairs['268091/1920']['source_movements']
    assert pf['rows'] == [[4, 5, 11, 2, 0, 10, 0, 2]]
    assert not pf['gross_identifiable'] and not pf['receipts_comparable']
    material = pairs['001757/1810']['source_movements']
    assert material['rows'][0][3:7] == [0, 2, -.5, -.75]
    assert material['gross_identifiable']


def test_movement_anomaly_is_visible_without_correcting_raw_receipts():
    pairs = {}
    initial = [(2, ('773474', 'SF', 'SF', '1450', '2025-01-05', 'KG', 0, 6400, -3200, 0)),
               (3, ('773474', 'SF', 'SF', '1450', '2025-01-12', 'KG', 0, 6400, -3200, 0)),
               (4, ('773474', 'SF', 'SF', '1450', '2025-01-19', 'KG', 0, 6400, -3200, 0))]
    _movement_source_rows(initial, pairs)
    pairs['773474/1450']['observed'] = [[d, 10000, n] for n, d in enumerate([5, 12, 19, 26], 2)]
    _movement_source_rows(initial, pairs)
    result = pairs['773474/1450']['source_movements']
    assert result['incoming_inconsistent'] and not result['receipts_comparable']
    assert [r[4] for r in result['rows']] == [6400, 6400, 6400]
    assert all(r['gap_qty'] == -3200 for r in result['balances'])


def test_physical_week_uses_net_receipt_production_and_consumption_without_release():
    # One Monday: 10 external + 20 made + 30 received - 4 sent - 5 core - 6 other.
    # The 100-unit quality release changes availability only.
    first = _physical_week_rows([[5, 10, 20, 30, 4, 100, 5, 6, 0]], True)[0]
    assert first == [5, 11, 45, 60, 20, 4, 5, 6]
    assert _physical_week_rows([], False)[0] == [5, 11, None, None, None, None, None, None]


def test_customer_week_keeps_missing_distinct_from_explicit_zero_and_excludes_edges():
    full = [[d, 10, 8, d] for d in range(5, 12)]
    rows = _customer_week_rows(full)
    assert len(rows) == 51 and rows[0] == [5, 70, 56, 11]
    assert rows[1] == [12, None, None, None]
    assert _customer_week_rows([[d, 0, 0, 0] for d in range(5, 12)])[0] == [5, 0, 0, 0]
    assert _customer_week_rows(full[:-1])[0] == [5, None, None, None]


def _forecast_map_row(**changes):
    return dict(dict(day='7', item_id='item:268091', node_id='CLIENT', uom='UN',
        period_start_day='5', period_end_day='11', represented_start_day='8', represented_end_day='11',
        weekly_source_qty='700', used_future_qty='420', source_vintage_days='[-2]', source_rows='[2]',
        source_days='4', fallback_days='0', fallback_source_vintage_days='[]', fallback_source_rows='[]',
        status='source', policy='customer_forecast'), **changes)


def test_customer_used_forecast_keeps_partial_remaining_separate_from_weekly_source():
    result = _customer_forecast_rows([_forecast_map_row()])['268091']['7'][0]
    assert result[:6] == [5, 11, 8, 11, 700, 420]
    fallback = _customer_forecast_rows([_forecast_map_row(weekly_source_qty='', fallback_days='4', source_days='0', status='fallback')])
    assert fallback['268091']['7'][0][4] is None


def test_customer_used_forecast_rejects_client_duplication_and_future_knowledge_confusion():
    with pytest.raises(ValueError, match='across clients'):
        _customer_forecast_rows([_forecast_map_row(), _forecast_map_row(node_id='CLIENT2')])
    with pytest.raises(ValueError, match='represented interval'):
        _customer_forecast_rows([_forecast_map_row(represented_start_day='7')])


@pytest.mark.parametrize("convention,first,last", [
    ("sunday_start", (4, 4, 10), (354, 354, 360)),
    ("monday_after", (4, 5, 11), (354, 355, 361)),
    ("sunday_end", (11, 5, 11), (361, 355, 361)),
])
def test_calendar_keeps_only_complete_nonoverlapping_first_year_weeks(convention, first, last):
    windows = list(_weekly_windows(convention))
    assert len(windows) == 51
    assert windows[0] == first
    assert windows[-1] == last
    days = [d for _, start, end in windows for d in range(start, end + 1)]
    assert len(days) == len(set(days)) == 357
    assert min(days) >= 0 and max(days) < 365


def test_january_seventh_receipt_uses_preceding_or_following_sunday_explicitly():
    # Jan 7 is J6. The source plan labels the 140 t delivery as Jan 5 (J4).
    events = {6: [140_000, 0, 0]}
    start = _weekly_rows(events, {}, {}, True, "sunday_start")
    following = _weekly_rows(events, {}, {}, True, "monday_after")
    historical = _weekly_rows(events, {}, {}, True, "sunday_end")
    assert start[0] == [4, 140_000, 0, 0, None, None, None, 4, 10]
    assert following[0] == [4, 140_000, 0, 0, None, None, None, 5, 11]
    assert historical[0] == [11, 140_000, 0, 0, None, None, None, 5, 11]
    assert sum(row[1] for row in start) == sum(row[1] for row in historical) == 140_000


def test_sunday_boundary_changes_quantity_not_only_display_label():
    # 5 Jan, 7 Jan and 12 Jan: distinguish the two plausible forward windows.
    events = {4: [20, 0, 0], 6: [140, 0, 0], 11: [30, 0, 0]}
    start = _weekly_rows(events, {}, {}, True, "sunday_start")
    following = _weekly_rows(events, {}, {}, True, "monday_after")
    assert start[0][1] == 160
    assert following[0][1] == 170
    assert start[1][1] == 30
    assert following[1][1] == 0


def test_missing_forecast_or_production_day_is_not_a_zero_observation():
    production = {d: 10 for d in (4, 5, 6, 7, 8, 9)}  # missing Jan 11
    trace = {d: [100, 10] for d in (4, 5, 6, 7, 8, 9, 10)}
    first = _weekly_rows({}, production, trace, True, "sunday_start")[0]
    assert first[1:7] == [0, 0, 0, None, 700, 70]
    del trace[7]  # In-memory missing observation, never filesystem alteration.
    assert _weekly_rows({}, production, trace, True, "sunday_start")[0][5:7] == [None, None]


def test_unmodelled_pair_does_not_become_zero_physical_flows():
    first = _weekly_rows({}, {}, {}, False, "sunday_start")[0]
    assert first[1:7] == [None, None, None, None, None, None]


def test_manual_daily_production_and_forecast_totals_keep_distinct_units_of_time():
    production = {d: d for d in (4, 5, 6, 7, 8, 9, 10, 11)}
    trace = {d: [100, d] for d in production}
    start = _weekly_rows({}, production, trace, True, "sunday_start")[0]
    following = _weekly_rows({}, production, trace, True, "monday_after")[0]
    assert start[4:7] == [49, 700, 49]
    assert following[4:7] == [56, 700, 56]


def test_dynamic_pair_unit_comes_from_explicit_lot_event_and_keeps_source_line():
    pair = ('M-1430', 'item:001848')
    rows = [
        {'node_id': 'M-1810', 'item_id': pair[1], 'uom': 'G'},
        {'node_id': pair[0], 'item_id': pair[1], 'uom': 'KG', 'qty': '7000'},
        {'node_id': pair[0], 'item_id': pair[1], 'uom': 'KG', 'qty': '7000'},
    ]
    result = _event_unit_evidence(rows, {pair})
    assert result == {pair: {'uom': 'KG', 'evidence_file': 'production_lot_events.csv', 'csv_line': 3}}
    assert rows[1]['qty'] == '7000'
    # The helper supplies a dimension, never an opening-stock observation.
    assert not {'opening_qty', 'opening_stock', 'initial_quantity'} & set(result[pair])


def test_missing_event_unit_is_not_inferred_from_quantity_or_article_identity():
    pair = ('M-1430', 'item:001848')
    rows = [{'node_id': pair[0], 'item_id': pair[1], 'uom': '', 'qty': '7000'}]
    assert _event_unit_evidence(rows, {pair}) == {}


@pytest.mark.parametrize('contradictory_unit', ['G', 'UN'])
def test_dynamic_pair_conflicting_quantity_unit_or_conversion_factor_is_rejected(contradictory_unit):
    pair = ('M-1430', 'item:001848')
    rows = [{'node_id': pair[0], 'item_id': pair[1], 'uom': unit} for unit in ('KG', contradictory_unit)]
    with pytest.raises(ValueError, match='Conflicting ledger units'):
        _event_unit_evidence(rows, {pair})


def _external_row(**changes):
    row = dict(day='0', node_id='M-1810', item_id='item:002612', uom='G',
               demand_qty='2000', backlog_start_qty='500', required_qty='2500',
               consumed_qty='1250', backlog_end_qty='1250', available_before_qty='10000',
               available_after_qty='8750', core_consumed_qty='3000', total_component_consumed_qty='4250')
    return dict(row, **changes)


def test_external_usage_grams_convert_all_nine_quantities_without_mixing_core_and_extra():
    pair = ('M-1810', 'item:002612')
    result = _external_component_rows([_external_row()], {pair: 'KG'})
    assert result == {pair: [[0, 2, .5, 2.5, 1.25, 1.25, 10, 8.75, 3, 4.25]]}
    assert 'external_component_consume' not in FLOW_TYPES


@pytest.mark.parametrize('field', ['required_qty', 'backlog_end_qty', 'available_after_qty',
                                 'total_component_consumed_qty'])
def test_external_usage_rejects_broken_material_or_requirement_balance(field):
    pair = ('M-1810', 'item:002612')
    with pytest.raises(ValueError, match='balance mismatch'):
        _external_component_rows([_external_row(**{field: '9999'})], {pair: 'KG'})


def test_external_usage_distinguishes_missing_days_from_exported_zero():
    pair = ('M-1810', 'item:002612')
    rows = [_external_row(day='4'), _external_row(day='6')]
    assert [row[0] for row in _external_component_rows(rows, {pair: 'KG'})[pair]] == [4, 6]
    assert _external_component_rows([], {pair: 'KG'}) == {}


def test_external_usage_rejects_duplicate_day_and_backlog_reset():
    pair = ('M-1810', 'item:002612')
    with pytest.raises(ValueError, match='Duplicate'):
        _external_component_rows([_external_row(), _external_row()], {pair: 'KG'})
    with pytest.raises(ValueError, match='backlog discontinuity'):
        _external_component_rows([_external_row(), _external_row(day='1')], {pair: 'KG'})


def test_external_usage_preserves_integer_physical_units_and_rejects_other_dimension():
    pair = ('M-1810', 'item:002612')
    with pytest.raises(ValueError, match='unit mismatch'):
        _external_component_rows([_external_row()], {pair: 'UN'})
    with pytest.raises(ValueError, match='Fractional physical units'):
        _external_component_rows([_external_row(uom='UN', consumed_qty='1.5')], {pair: 'UN'})


def test_external_trace_extension_keeps_legacy_positions_and_absence():
    row = dict(bb_demand_signal_qty='1000', bb_demand_signal_raw_qty='2000',
               target_stock_qty='3000', safety_floor_qty='4000', bn_qty='5000',
               recv_prev_future_qty='6000', coverage_target_qty='7000', receipt_cover_end_day='42')
    legacy = _trace_values(row, .001)
    assert len(COLUMNS['trace']) == len(legacy) + 1 >= 70
    assert legacy[:7] == [1, 2, 3, 4, 5, 6, 7]
    assert legacy[9] == 42  # Inclusive horizon date retains its original position.
    assert legacy[54:58] == [None, None, None, None]
    assert all(value is None for value in legacy[58:])
    row.update(external_demand_qty='2500', external_consumed_qty='1250',
               external_backlog_qty='1250', dated_external_requirement_qty='9000')
    current = _trace_values(row, .001)
    assert current[:54] == legacy[:54]
    assert current[54:58] == [2.5, 1.25, 1.25, 9]
    assert current[58:] == legacy[58:]


def test_real_component_catchup_allows_only_export_rounding_not_material_discrepancy():
    # Actual 001893/M-1810 J75: 27 FIFO catch-up events, each rounded to 6 decimals.
    events = ([808.868146] + [1215.577791] * 3 + [1083.377794] * 7
              + [793.199983] * 7 + [530.928432] * 7 + [769.787103] * 2)
    from math import fsum
    recorded = fsum(events)
    assert len(events) == 27
    assert recorded == pytest.approx(22847.719188, abs=1e-10)
    assert _ledger_quantity_matches(22847.719185, recorded, unit='KG', report_factor=1,
                                    event_factor_sum=27, event_count=27)
    assert not _ledger_quantity_matches(22847.719185 + .0001, recorded, unit='KG', report_factor=1,
                                        event_factor_sum=27, event_count=27)
    # The same values exported in G have a 1000 times smaller canonical allowance.
    assert not _ledger_quantity_matches(22847.719185, recorded, unit='KG', report_factor=.001,
                                        event_factor_sum=.027, event_count=27)
    # No rounding budget may hide a missing physical unit, even with many events.
    assert not _ledger_quantity_matches(5000, 4999, unit='UN', report_factor=1,
                                        event_factor_sum=3_000_000, event_count=3_000_000)


def test_revision_scope_is_pair_specific_and_preserves_versions_without_summing_them():
    from copy import deepcopy
    fixed = dict(node_id='M-1810', item_id='item:002612', known_day=4, qty=20)
    revisions = dict(node_id='M-1810', item_id='item:001848', uom='KG', repeat_period_days=0,
                     versions=[dict(vintage_id='mrp:4', known_day=4, rows=[dict(qty=70)]),
                               dict(vintage_id='mrp:11', known_day=11, rows=[dict(qty=35)])])
    config = dict(schema_version=2, origin='2025-01-01', repeat_period_days=365,
                  rows=[fixed], versioned_series=[revisions])
    before = deepcopy(config)
    rolling = _external_component_scope(config, ('M-1810', 'item:001848'))
    assert rolling['repeat_period_days'] == 0 and rolling['sources'] == []
    assert rolling['versioned_series']['versions'] == revisions['versions']
    assert rolling['forecast_update_mode'] == 'rolling_vintages_future_replacement_current_week_frozen'
    unchanged = _external_component_scope(config, ('M-1810', 'item:002612'))
    assert unchanged['sources'] == [fixed] and unchanged['repeat_period_days'] == 365
    assert 'versioned_series' not in unchanged and 'forecast_update_mode' not in unchanged
    assert config == before


def test_revision_scope_does_not_assign_another_site_or_hide_duplicate_series():
    revisions = dict(node_id='M-1810', item_id='item:001848', versions=[])
    assert 'versioned_series' not in _external_component_scope(
        {'versioned_series': [revisions]}, ('M-1430', 'item:001848'))
    with pytest.raises(ValueError, match='Duplicate versioned component series'):
        _external_component_scope({'versioned_series': [revisions, revisions]},
                                  ('M-1810', 'item:001848'))


def test_revision_audit_separates_frozen_week_from_latest_plan_and_unknown_coverage():
    assert _external_forecast_audit([_external_row()]) == {}
    audit = dict.fromkeys(EXTERNAL_FORECAST_AUDIT_FIELDS, '')
    audit.update(forecast_selection_mode='rolling', forecast_vintage_id='mrp:4',
                 forecast_known_day='4', forecast_latest_known_vintage_id='mrp:11',
                 forecast_latest_known_day='11', forecast_period_start_day='11',
                 forecast_source_covered='0', forecast_coverage_reason='unprovided',
                 forecast_source_file='source.xlsx', forecast_source_cells='["I42"]')
    row = _external_row(day='12', **audit)
    result = _external_forecast_audit([row])[('M-1810', 'item:002612')][0]
    assert result == [12, 'rolling', 'mrp:4', 4, 'mrp:11', 11, 11, 0,
                      'unprovided', 'source.xlsx', '["I42"]']
    # Audit columns never alter or reinterpret any of the nine physical balances.
    assert _external_component_rows([row], {('M-1810', 'item:002612'): 'KG'}) == {
        ('M-1810', 'item:002612'): [[12, 2, .5, 2.5, 1.25, 1.25, 10, 8.75, 3, 4.25]]}


def test_revision_audit_rejects_future_knowledge_and_incomplete_optional_contract():
    row = _external_row(day='4', **dict.fromkeys(EXTERNAL_FORECAST_AUDIT_FIELDS, ''))
    row['forecast_latest_known_day'] = '11'
    with pytest.raises(ValueError, match='not yet known'):
        _external_forecast_audit([row])
    row['forecast_latest_known_day'] = '4'
    row.pop('forecast_source_covered')
    with pytest.raises(ValueError, match='Incomplete external forecast audit'):
        _external_forecast_audit([row])


def _sourcing_row(**changes):
    return dict(dict(sourcing_policy_id='001848_primary_backup', sourcing_role='backup',
        sourcing_reason='shortfall_before_primary', sourcing_purchase_unit_cost='0.0042',
        sourcing_price_uom='G', sourcing_currency='EUR', sourcing_primary_available_day='84',
        sourcing_requirement_due_day='57', sourcing_backup_required_qty='2000000',
        sourcing_proposal_id='proposal:57'), **changes)


def test_sourcing_price_uses_inverse_unit_conversion_and_leaves_dates_unchanged():
    row = _sourcing_row()
    result = _sourcing_order(row, 'KG', .001)
    assert result['sourcing_purchase_unit_cost'] == pytest.approx(4.2)
    assert result['sourcing_price_uom'] == 'KG' and result['sourcing_currency'] == 'EUR'
    assert result['sourcing_backup_required_qty'] == 2000
    assert result['sourcing_primary_available_day'] == 84
    assert result['sourcing_requirement_due_day'] == 57
    assert result['sourcing_role'] == 'backup' and result['sourcing_proposal_id'] == 'proposal:57'
    assert row['sourcing_purchase_unit_cost'] == '0.0042' and row['sourcing_price_uom'] == 'G'
    assert _sourcing_order({}, 'KG', .001) == {}


@pytest.mark.parametrize('unit', ['', 'UN'])
def test_sourcing_price_requires_an_explicit_compatible_unit(unit):
    with pytest.raises(ValueError, match='Sourcing price|sourcing price'):
        _sourcing_order(_sourcing_row(sourcing_price_uom=unit), 'KG', .001)


def test_sourcing_scope_preserves_confirmation_and_provenance_for_only_the_named_pair():
    from copy import deepcopy
    rule = dict(policy_id='001848_primary_backup', node_id='M-1810', item_id='item:001848',
                confirmation='user_confirmed_roles_only', primary_supplier_id='principal',
                offers=[dict(supplier_id='principal', purchase_unit_cost=.00158, price_uom='G',
                             currency='EUR', source_file='268091.xlsx', source_cells='FIA!C4:H4')])
    before = deepcopy(rule)
    scope = _sourcing_scope({'rows': [rule]}, ('M-1810', 'item:001848'), 'KG')
    assert scope['confirmation'] == 'user_confirmed_roles_only'
    assert scope['offers'][0]['display_purchase_unit_cost'] == pytest.approx(1.58)
    assert scope['offers'][0]['source_cells'] == 'FIA!C4:H4'
    assert scope['offers'][0]['purchase_unit_cost'] == .00158
    assert _sourcing_scope({'rows': [rule]}, ('M-1810', 'item:001893'), 'KG') is None
    assert _sourcing_scope({'rows': [rule]}, ('M-1430', 'item:001848'), 'KG') is None
    assert rule == before


def test_sourcing_trace_extension_keeps_previous_59_columns_and_missing_values():
    row = dict(bb_demand_signal_qty='1', bb_demand_signal_raw_qty='2', target_stock_qty='3',
               safety_floor_qty='4', bn_qty='5', recv_prev_future_qty='6', coverage_target_qty='7')
    before = _trace_values(row, .001)
    assert before[58:66] == [None] * 8
    row.update(sourcing_policy_id='policy:001848', sourcing_primary_available_day='84',
               sourcing_physical_shortage_before_primary_qty='1000', sourcing_backup_proposed_qty='2000',
               sourcing_backup_released_qty='0', sourcing_primary_released_qty='6000',
               sourcing_retained_firm_qty='9000', sourcing_bridge_surplus_qty='3000')
    after = _trace_values(row, .001)
    assert after[:58] == before[:58]  # Day is the separate first payload column.
    assert after[58:66] == ['policy:001848', 84, 1, 2, 0, 6, 9, 3]


def test_batching_scope_converts_quantities_but_preserves_window_and_candidate_status():
    rule = dict(policy_id='candidate', node_id='M-1810', item_id='item:001757', uom='G',
                rounding_multiple_qty=1_000_000, grouping_days=28,
                semantics='first_uncovered_requirement_forward_window', status='candidate_sensitivity')
    result = _batching_scope({'rows': [rule]}, ('M-1810', 'item:001757'), 'KG')
    assert result['display_rounding_multiple_qty'] == 1000 and result['display_uom'] == 'KG'
    assert result['grouping_days'] == 28 and result['status'] == 'candidate_sensitivity'
    assert result['rounding_multiple_qty'] == rule['rounding_multiple_qty'] == 1_000_000
    assert 'display_uom' not in rule
    assert _batching_scope({}, ('M-1810', 'item:001757'), 'KG') is None
    assert _batching_scope({'rows': [rule]}, ('M-1430', 'item:001757'), 'KG') is None


def test_batching_scope_rejects_duplicate_policies_and_incompatible_units():
    rule = dict(node_id='M-1810', item_id='item:001757', uom='KG', rounding_multiple_qty=100)
    with pytest.raises(ValueError, match='Duplicate procurement batching policy'):
        _batching_scope({'rows': [rule, rule]}, ('M-1810', 'item:001757'), 'KG')
    with pytest.raises(ValueError, match='batching unit mismatch'):
        _batching_scope({'rows': [rule]}, ('M-1810', 'item:001757'), 'UN')


def test_batching_order_preserves_exclusive_dates_and_separates_net_protection_and_proposal():
    row = dict(procurement_batch_policy_id='candidate', procurement_batch_group_id='group:1',
               procurement_batch_first_need_day='100', procurement_batch_window_end_day_exclusive='128',
               procurement_batch_net_qty='840000', procurement_batch_physical_net_qty='800000',
               procurement_batch_reserve_net_qty='40000', procurement_batch_proposed_qty='1000000',
               procurement_batch_rounding_multiple_qty='1000000', procurement_batch_grouping_days='28',
               procurement_batch_proposal_id='proposal:1')
    result = _batching_order(row, .001)
    assert [result[field] for field in ('procurement_batch_net_qty', 'procurement_batch_physical_net_qty',
            'procurement_batch_reserve_net_qty', 'procurement_batch_proposed_qty',
            'procurement_batch_rounding_multiple_qty')] == [840, 800, 40, 1000, 1000]
    assert result['procurement_batch_first_need_day'] == 100
    assert result['procurement_batch_window_end_day_exclusive'] == 128
    assert result['procurement_batch_grouping_days'] == 28
    assert result['procurement_batch_group_id'] == 'group:1'
    assert row['procurement_batch_net_qty'] == '840000'
    assert _batching_order({}, .001) == {}
    with pytest.raises(ValueError, match='Incomplete procurement batching order audit'):
        _batching_order({'procurement_batch_policy_id': 'candidate'}, .001)


def test_rolling_schema_three_keeps_known_future_weeks_without_repeating_or_adding_vintages():
    series = dict(node_id='M-1810', item_id='item:001757', repeat_period_days=0,
                  versions=[dict(vintage_id='mrp:354', known_day=354,
                                 rows=[dict(period_start_day=368, period_days=7, qty=140),
                                       dict(period_start_day=718, period_days=7, qty=70)])])
    result = _external_component_scope({'schema_version': 3, 'versioned_series': [series]},
                                       ('M-1810', 'item:001757'))
    assert result['schema_version'] == 3 and result['repeat_period_days'] == 0
    assert result['versioned_series']['versions'] == series['versions']
    assert result['versioned_series']['versions'][0]['rows'][0]['period_start_day'] == 368
    assert result['versioned_series']['versions'][0]['known_day'] == 354
    assert result['versioned_series']['versions'][0]['rows'][1] == {
        'period_start_day': 718, 'period_days': 7, 'qty': 70}  # Preserve the entire last source week.


def test_projection_crosses_year_boundary_without_consuming_protection_or_extending_execution():
    buckets = {362: [20, 0, 30, 900], 365: [0, 50, 10, 0], 368: [0, 5, 8, 30],
               376: [999, 999, 999, 999]}
    old = _projection_rows(100, buckets, 361, 364)
    assert old == [[361, 20, 0, 30, 900, 90, 361, 364]]
    future = _projection_rows(100, buckets, 361, 375)
    assert future == [[361, 20, 50, 40, 900, 130, 361, 367],
                      [368, 0, 5, 8, 30, 127, 368, 374],
                      [375, 0, 0, 0, 0, 127, 375, 375]]
    assert set(buckets) == {362, 365, 368, 376}  # No invented source rows or bucket mutation.
    assert _projection_rows(100, buckets, 361, 364) == old
    horizon = _projection_rows(100, {}, 361, 361 + 364)
    assert len(horizon) == 53 and horizon[-1][-2:] == [725, 725]
    assert all(row[5] == 100 for row in horizon)


@pytest.mark.parametrize('delta', [-500, -0.25, 0, 500])
def test_projection_signed_reconciliation_delta_is_audit_only(delta):
    events = [('opening_available', 4, 100, 'component_procurement'),
              ('firm_transit', 5, 20, 'component_procurement'),
              ('proposal', 6, 10, 'component_procurement'),
              ('requirement', 7, 30, 'component_procurement'),
              ('reserve', 8, 40, 'component_procurement'),
              ('stock_protection', 9, 200, 'component_procurement'),
              ('industrial_complement_delta', 7, delta, 'component_procurement')]
    before = list(events)
    opening, buckets, levels = _projection_event_buckets(events, ('M', 'item:X'), 4)
    assert opening == 100 and levels == {9: 200}
    # Independent hand balance: 100 + 20 + 10 - 30 = 100, for either sign.
    assert _projection_rows(opening, buckets, 4, 10) == [[4, 20, 10, 30, 40, 100, 4, 10]]
    assert events == before and events[-1][2] == delta
    assert len(events) == 7  # Audit evidence is retained by the caller.


@pytest.mark.parametrize('quantity', [None, float('nan'), float('inf'), -float('inf')])
def test_projection_signed_reconciliation_delta_rejects_missing_or_nonfinite(quantity):
    events = [('opening_available', 4, 100, 'component_procurement'),
              ('industrial_complement_delta', 7, quantity, 'component_procurement')]
    with pytest.raises(ValueError, match='Invalid signed industrial planning audit'):
        _projection_event_buckets(events, ('M', 'item:X'), 4)


def test_projection_reconciliation_audits_do_not_change_flow_balance_or_protection():
    events = [('opening_available', 4, 100, 'component_procurement'),
              ('firm_transit', 5, 20, 'component_procurement'),
              ('proposal', 6, 10, 'component_procurement'),
              ('requirement', 7, 30, 'component_procurement'),
              ('reserve', 8, 40, 'component_procurement'),
              ('stock_protection', 9, 200, 'component_procurement')]
    expected = _projection_event_buckets(events, ('M', 'item:X'), 4)
    audits = [('industrial_weekly_complement_before_netting', 5, 10000, 'component_procurement'),
              ('industrial_temporal_overlap_removed', 7, 7000, 'component_procurement'),
              ('industrial_original_own_requirement', 10, 30, 'component_procurement'),
              ('industrial_own_planning_allocation', 5, 30, 'component_procurement'),
              ('industrial_own_planned', 5, 30, 'component_procurement'),
              ('industrial_planning', 5, 30, 'component_procurement'),
              ('industrial_own_advanced', 5, 30, 'component_procurement')]
    combined = events + audits
    before = list(combined)
    opening, buckets, levels = _projection_event_buckets(combined, ('M', 'item:X'), 4)
    assert (opening, buckets, levels) == expected
    assert opening == 100 and levels == {9: 200}
    # Hand ledger: 100 + 20 + 10 - 30 = 100. Reserve and floor are not outflows.
    assert _projection_rows(opening, buckets, 4, 10) == [[4, 20, 10, 30, 40, 100, 4, 10]]
    assert combined == before


@pytest.mark.parametrize('kind', [
    'industrial_weekly_complement_before_netting', 'industrial_temporal_overlap_removed',
    'industrial_original_own_requirement', 'industrial_own_planning_allocation',
    'industrial_own_planned', 'industrial_planning', 'industrial_own_advanced',
])
@pytest.mark.parametrize('quantity', [-1, None])
def test_projection_reconciliation_audits_reject_invalid_quantities(kind, quantity):
    events = [('opening_available', 4, 100, 'component_procurement'),
              (kind, 5, quantity, 'component_procurement')]
    with pytest.raises(ValueError, match='Invalid industrial planning audit'):
        _projection_event_buckets(events, ('M', 'item:X'), 4)


def test_projection_event_parser_preserves_legacy_dates_and_rejects_unknown_events():
    events = [('opening_available', 4, 100, 'production'),
              ('firm_held', 2, 15, 'production'),
              ('requirement', 3, 5, 'production'),
              ('industrial_source', 7, 200, 'production')]
    opening, buckets, levels = _projection_event_buckets(events, ('M', 'item:X'), 4)
    assert opening == 100 and dict(buckets) == {4: [15, 0, 5, 0]} and levels == {}
    assert _projection_rows(opening, buckets, 4, 10) == [[4, 15, 0, 5, 0, 110, 4, 10]]
    with pytest.raises(ValueError, match='Unknown dated projection event: mystery'):
        _projection_event_buckets(events + [('mystery', 8, 1, 'production')], ('M', 'item:X'), 4)
    for invalid in (events[1:], events + [events[0]]):
        with pytest.raises(ValueError, match='exactly one opening state'):
            _projection_event_buckets(invalid, ('M', 'item:X'), 4)


def test_stock_protection_trace_adds_levels_without_scaling_dates_or_changing_legacy():
    row = dict(bb_demand_signal_qty='1', bb_demand_signal_raw_qty='2', target_stock_qty='3',
               safety_floor_qty='4', bn_qty='5', recv_prev_future_qty='6', coverage_target_qty='7')
    old = _trace_values(row, .001)
    assert old[66:69] == [None, None, None] and all(value is None for value in old[69:])
    row.update(dated_protection_target_qty='1000000', dated_protection_max_shortfall_qty='100000',
               dated_protection_first_shortfall_day='365')
    new = _trace_values(row, .001)
    assert new[:66] == old[:66]
    assert new[66:69] == [1000, 100, 365]
    assert new[69:] == old[69:]


def test_anticipated_trace_converts_grams_but_preserves_dates_days_and_policy():
    row = dict(bb_demand_signal_qty='1', bb_demand_signal_raw_qty='2', target_stock_qty='3',
               safety_floor_qty='4', bn_qty='5', recv_prev_future_qty='6', coverage_target_qty='7')
    old = _trace_values(row, .001)
    fields = ('purchase_need_date_policy', 'anticipated_safety_working_days', 'anticipated_fixed_floor_qty',
              'anticipated_late_qty', 'anticipated_first_shortage_day', 'anticipated_no_extra_time_floor')
    indices = [COLUMNS['trace'].index(field) - 1 for field in fields]
    assert [old[index] for index in indices] == [None] * 6
    row.update(purchase_need_date_policy='source_safety_backwards_v1',
               anticipated_safety_working_days='20', anticipated_fixed_floor_qty='4000000',
               anticipated_late_qty='100000', anticipated_first_shortage_day='124',
               anticipated_no_extra_time_floor='1')
    new = _trace_values(row, .001)
    assert [new[index] for index in indices] == ['source_safety_backwards_v1', 20, 4000, 100, 124, 1]
    assert all(before == after for index, (before, after) in enumerate(zip(old, new)) if index not in indices)


def test_common_purchase_trace_preserves_strings_days_and_converts_only_quantities():
    row = dict(bb_demand_signal_qty='1', bb_demand_signal_raw_qty='2', target_stock_qty='3',
               safety_floor_qty='4', bn_qty='5', recv_prev_future_qty='6', coverage_target_qty='7')
    old = _trace_values(row, .001)
    fields = ('purchase_rule_version', 'purchase_fixed_floor_mode', 'purchase_grouping_days',
              'purchase_requirement_basis', 'production_projection_floor_qty')
    indices = [COLUMNS['trace'].index(field) - 1 for field in fields]
    assert [old[index] for index in indices] == [None] * 5
    assert len(set(COLUMNS['trace'])) == len(COLUMNS['trace'])
    row.update(purchase_rule_version='source_safety_additive_v2', purchase_fixed_floor_mode='additive',
               purchase_grouping_days='7', purchase_requirement_basis='remaining_physical_BOM_and_reconciled_known_industrial_I',
               production_projection_floor_qty='2500000')
    new = _trace_values(row, .001)
    assert [new[index] for index in indices] == ['source_safety_additive_v2', 'additive', 7,
        'remaining_physical_BOM_and_reconciled_known_industrial_I', 2500]
    assert all(before == after for index, (before, after) in enumerate(zip(old, new)) if index not in indices)
    assert row['production_projection_floor_qty'] == '2500000'


def test_weekly_protection_is_a_maximum_not_a_flow_and_missing_stays_unknown():
    levels = {day: 600 for day in range(362, 368)}
    levels.update({368: 800, 369: 700, 376: 900})
    before = levels.copy()
    assert _projection_protection_levels(levels, 361, 375) == [[361, 600], [368, 800], [375, 700]]
    assert _projection_protection_levels({}, 361, 375) == [[361, None], [368, None], [375, None]]
    assert all(row[1] == 600 for row in _projection_protection_levels({362: 600}, 361, 725))
    assert _projection_protection_levels({362: 0}, 361, 367) == [[361, 0]]
    assert _projection_rows(100, {362: [20, 0, 30, 900]}, 361, 367)[0][5] == 90
    assert levels == before


def test_internal_policy_keeps_independent_options_and_normalizes_only_transfer_quantity():
    rule = dict(policy_id='candidate', node_id='M-1810', item_id='item:693055', uom='G',
                transfer_multiple_qty=600000, receipt_days=7, receipt_calendar='monday_friday',
                protection_mode='dated_stock_floor', status='candidate')
    scope = _internal_component_scope({'rows': [rule]}, ('M-1810', 'item:693055'), 'KG')
    assert scope['display_transfer_multiple_qty'] == 600 and scope['transfer_multiple_qty'] == 600000
    assert scope['receipt_days'] == 7 and scope['protection_mode'] == 'dated_stock_floor'
    assert _internal_component_scope({'rows': [rule]}, ('M-1810', 'item:001757'), 'KG') is None
    assert _internal_component_scope({}, ('M-1810', 'item:693055'), 'KG') is None
    with pytest.raises(ValueError, match='Duplicate internal'):
        _internal_component_scope({'rows': [rule, rule]}, ('M-1810', 'item:693055'), 'KG')
    with pytest.raises(ValueError, match='unit mismatch'):
        _internal_component_scope({'rows': [rule]}, ('M-1810', 'item:693055'), 'UN')
    assert _internal_component_scope({'rows': [dict(node_id='M-1810', item_id='item:693055',
        protection_mode='dated_stock_floor')]}, ('M-1810', 'item:693055'), 'KG')['display_uom'] == 'KG'


def _memory_production_event(event, day, qty, *, lot='lot-1', notes='', uom='UN'):
    return dict(node_id='plant', item_id='finished', lot_id=lot, event_type=event,
                day=str(day), qty=str(qty), uom=uom, notes=notes)


def test_production_availability_keeps_legacy_unheld_date_and_quantity():
    rows = [_memory_production_event('opening_production_order', 9, 100),
            _memory_production_event('production_output', 10, 50, lot='lot-2')]
    assert list(production_availability_events(rows)) == rows


@pytest.mark.parametrize('hold_first', [False, True])
def test_production_availability_rejects_undocumented_initial_hold(hold_first):
    rows = [_memory_production_event('production_output', 9, 100),
            _memory_production_event('stock_availability_hold', 9, 100)]
    if hold_first:
        rows.reverse()
    with pytest.raises(ValueError, match='initially held'):
        list(production_availability_events(rows))


def test_production_availability_uses_executed_release_not_physical_or_scheduled_date():
    physical = _memory_production_event('opening_production_order', 9, 100,
        notes='{"availability_state":"held","available_day":23}')
    # A known future date alone is not a release. Physical entry stays at day9.
    assert list(production_availability_events([physical])) == []
    assert physical['day'] == '9' and site_flow_kind(physical) == 'production_output'
    release = _memory_production_event('stock_availability_release', 24, 100)
    result = list(production_availability_events([physical, release]))
    assert [(r['day'], r['event_type'], float(r['qty'])) for r in result] == [
        ('24', 'opening_production_order', 100)]
    assert site_flow_kind(release) == 'availability_release'
    assert physical['day'] == '9'


def test_production_availability_partials_conserve_one_lot_and_ignore_unrelated_release():
    rows = [_memory_production_event('production_output', 2, 100,
                notes='{"availability_state":"held","available_day":16}'),
            _memory_production_event('stock_availability_release', 16, 300, lot='initial-stock'),
            _memory_production_event('stock_availability_release', 16, 60),
            _memory_production_event('stock_availability_release', 17, 40)]
    result = list(production_availability_events(rows))
    assert [(r['day'], float(r['qty'])) for r in result] == [('16', 60), ('17', 40)]
    assert sum(float(r['qty']) for r in result) == 100


@pytest.mark.parametrize('release', [
    _memory_production_event('stock_availability_release', 22, 100),
    _memory_production_event('stock_availability_release', 23, 101),
    _memory_production_event('stock_availability_release', 23, 100, uom='KG'),
])
def test_production_availability_rejects_early_excess_or_different_unit_release(release):
    physical = _memory_production_event('production_output', 9, 100,
        notes='{"availability_state":"held","available_day":23}')
    with pytest.raises(ValueError, match='Production release'):
        list(production_availability_events([physical, release]))


def test_production_availability_cannot_release_the_same_held_quantity_twice():
    physical = _memory_production_event('production_output', 9, 100,
        notes='{"availability_state":"held","available_day":23}')
    release = _memory_production_event('stock_availability_release', 23, 100)
    with pytest.raises(ValueError, match='exceed'):
        list(production_availability_events([physical, release, release]))


def test_known_forecast_and_dated_production_trace_preserve_provenance_and_units():
    row = dict(bb_demand_signal_qty='1', bb_demand_signal_raw_qty='2', target_stock_qty='3',
               safety_floor_qty='4', bn_qty='5', recv_prev_future_qty='6', coverage_target_qty='7',
               mrp_forecast_missing_period_policy='last_known_period_v1',
               mrp_forecast_source_vintages='4|11', mrp_forecast_source_rows='546|1502',
               mrp_forecast_daily_qty='2000', production_execution_policy='dated_releases_v1',
               production_dated_snapshot_day='11', production_dated_new_release_qty='3200000',
               production_dated_late_qty='600000', production_dated_release_proposal_ids='p1|p2',
               depot_safety_protection_policy='source_stock_floor_v1', depot_safety_protection_qty='5000')
    result = dict(zip(COLUMNS['trace'][1:], _trace_values(row, .001)))
    assert result['mrp_forecast_source_vintages'] == '4|11'
    assert result['mrp_forecast_source_rows'] == '546|1502'
    assert result['mrp_forecast_daily_qty'] == 2
    assert result['production_dated_snapshot_day'] == 11
    assert result['production_dated_new_release_qty'] == 3200
    assert result['production_dated_late_qty'] == 600
    assert result['production_dated_release_proposal_ids'] == 'p1|p2'
    assert result['depot_safety_protection_policy'] == 'source_stock_floor_v1'
    assert result['depot_safety_protection_qty'] == 5
