"""Independent audit of conditional residual replay; no simulator imports.

The preserved profile defines requests, not service or debt. Actual BOM
withdrawals and physical allocations remain independently reconstructed.
"""
from collections import defaultdict
import csv
from decimal import Decimal
import hashlib
import io
from pathlib import Path

MODE = 'fixed_residual_replay'
STATUS = 'conditional_scenario_not_industrial_observation'
PHYSICAL_SOURCE = 'conditional_fixed_residual_from_retained_control'


def profile_declaration_valid(declaration, horizon, evidence):
    fields = {'schema_version', 'profile_path', 'profile_sha256', 'rows', 'days',
              'quantity_field', 'knowledge', 'status'}
    valid = (isinstance(declaration, dict) and set(declaration) == fields
        and type(declaration.get('schema_version')) is int and declaration['schema_version'] == 1
        and type(declaration.get('rows')) is int and declaration['rows'] > 0
        and type(declaration.get('days')) is int and declaration['days'] == horizon
        and type(horizon) is int and 0 < horizon <= 362
        and declaration.get('quantity_field') == 'residual_requested_qty'
        and declaration.get('knowledge') == 'closing_day_after_own_production'
        and declaration.get('status') == STATUS
        and isinstance(declaration.get('profile_path'), str) and bool(declaration['profile_path'])
        and isinstance(declaration.get('profile_sha256'), str)
        and len(declaration['profile_sha256']) == 64
        and all(c in '0123456789abcdef' for c in declaration['profile_sha256']))
    evidence.check('fixed_residual_profile_declaration', valid, declaration)
    return valid


def load_profile_bytes(manifest, horizon, root, evidence):
    """Bind the explicit runtime profile to the native manifest input bytes."""
    runtime = manifest.get('runtime') if isinstance(manifest, dict) else None
    declaration = runtime.get('fixed_residual_replay') if isinstance(runtime, dict) else None
    if not profile_declaration_valid(declaration, horizon, evidence):
        return declaration, None
    path = Path(declaration['profile_path'])
    root = Path(root).resolve()
    source = (root / path).resolve()
    valid = not path.is_absolute() and source.is_relative_to(root) and source.is_file()
    evidence.check('fixed_residual_original_profile_path', valid, declaration['profile_path'])
    if not valid:
        return declaration, None
    inputs = manifest.get('inputs')
    candidates = []
    if isinstance(inputs, dict):
        candidates = [digest for name, digest in inputs.items()
                      if isinstance(name, str) and (root / name).resolve() == source]
    evidence.check('fixed_residual_native_input_binding',
        candidates == [declaration['profile_sha256']], candidates)
    return declaration, source.read_bytes()


def _decimal(value):
    value = Decimal(str(value))
    if not value.is_finite():
        raise ValueError('Nonfinite quantity')
    return value


def audit_fixed_residual_replay(contract, budgets, events, weekly_rows, allocation_rows,
        cumulative_rows, horizon, scenario, evidence, declaration, profile_bytes,
        *, validate_declared, audit_closed):
    """Return fixed external requirements after checking their independent evidence.

    validate_declared/audit_closed are existing independent CSV oracles. The
    first rebuilds graph budgets and actual own use; its legacy residual
    calculation is discarded and never used to approve a replayed quantity.
    """
    if not profile_declaration_valid(declaration, horizon, evidence):
        return {}
    matching = isinstance(profile_bytes, bytes) and hashlib.sha256(profile_bytes).hexdigest() == declaration['profile_sha256']
    evidence.check('fixed_residual_profile_sha256', matching)
    if not matching:
        return {}
    closed = []
    validate_declared(contract, budgets, events, horizon, scenario, evidence, closed_rows=closed)
    source_by_id = {row['budget_id']: row for row in closed}
    try:
        reader = csv.DictReader(io.StringIO(profile_bytes.decode('utf-8-sig')))
        required = {'budget_id', 'requirement_id', 'node_id', 'item_id', 'uom',
                    'first_day', 'end_day_exclusive', 'closing_day',
                    'covered_scan3_qty', 'residual_requested_qty'}
        fields = reader.fieldnames or []
        valid_fields = required <= set(fields) and len(fields) == len(set(fields))
        evidence.check('fixed_residual_profile_columns', valid_fields, fields)
        if not valid_fields:
            return {}
        profile_rows = list(reader)
    except (UnicodeError, csv.Error):
        evidence.check('fixed_residual_profile_readable', False)
        return {}
    evidence.check('fixed_residual_profile_row_count', len(profile_rows) == declaration['rows'], len(profile_rows))
    fixed = {}
    for row in profile_rows:
        identity = row['budget_id']
        source = source_by_id.get(identity)
        valid_identity = bool(identity) and identity not in fixed and source is not None
        evidence.check('fixed_residual_profile_budget_identity', valid_identity, identity)
        if not valid_identity:
            continue
        identity_fields = ('requirement_id', 'node_id', 'item_id', 'uom',
                           'first_day', 'end_day_exclusive', 'closing_day')
        valid_source = all(str(row.get(k, '')) == str(source[k]) for k in identity_fields)
        evidence.check('fixed_residual_profile_source_identity', valid_source, identity)
        try:
            quantity = _decimal(row['residual_requested_qty'])
            target = _decimal(row['covered_scan3_qty'])
            valid_quantity = quantity >= 0 and target == _decimal(source['covered_scan3_qty'])
            whole = source['uom'] != 'UN' or quantity == quantity.to_integral_value()
        except (ValueError, ArithmeticError, TypeError):
            quantity = Decimal(0)
            valid_quantity = whole = False
        evidence.check('fixed_residual_profile_quantity', valid_quantity, identity)
        evidence.check('fixed_residual_profile_integer_UN', whole, identity)
        if valid_source and valid_quantity and whole:
            fixed[identity] = quantity
    evidence.check('fixed_residual_exact_closed_budget_coverage', set(fixed) == set(source_by_id), {
        'missing': sorted(set(source_by_id) - set(fixed))[:5],
        'extra': sorted(set(fixed) - set(source_by_id))[:5]})
    if set(fixed) != set(source_by_id):
        return {}

    expected_rows, result = [], {}
    for source in closed:
        identity = source['budget_id']
        quantity = fixed[identity]
        expected_rows.append(dict(source, residual_requested_qty=float(quantity)))
        if quantity <= 0:
            continue
        day = source['closing_day']
        rid = source['requirement_id']
        basis = dict(method='fixed_residual_from_retained_control',
            profile_path=declaration['profile_path'], profile_sha256=declaration['profile_sha256'],
            source_budget_id=identity, source_requirement_id=rid,
            fixed_requested_qty=float(quantity), known_day=day,
            known_phase='after_own_production', status=STATUS,
            planning_use='not available before after-production closing')
        result[rid] = dict(pair=(source['node_id'], source['item_id']), day=day, known=day,
            qty=float(quantity), cycle=0,
            source=dict(demand_id=identity, source_file=declaration['profile_path'],
                source_cells='budget_id='+identity, uom=source['uom']),
            physical_source=PHYSICAL_SOURCE, reconciliation_basis=basis)
    audit_closed(expected_rows, events, weekly_rows, allocation_rows, horizon, evidence)
    weekly_by_id = {row.get('budget_id'): row for row in weekly_rows}
    for source in expected_rows:
        identity = source['budget_id']
        row = weekly_by_id.get(identity)
        if row is None:
            continue
        expected_text = dict(scan3_reconciliation_mode=MODE,
            replay_profile_sha256=declaration['profile_sha256'],
            replay_profile_source=declaration['profile_path'], replay_known_phase='after_own_production')
        evidence.check('fixed_residual_weekly_provenance',
            all(row.get(k) == v for k, v in expected_text.items()), identity)
        if source['uom'] == 'UN':
            for field in ('own_physical_qty', 'residual_requested_qty', 'residual_executed_qty',
                    'residual_executed_on_closing_day_qty', 'residual_backlog_initial_qty',
                    'residual_backlog_final_qty', 'residual_backlog_at_closing_qty'):
                try:
                    value = _decimal(row[field])
                    whole = value == value.to_integral_value()
                except (KeyError, ValueError, TypeError, ArithmeticError):
                    whole = False
                evidence.check('fixed_residual_weekly_integer_UN_'+field, whole, identity)
        target, own, requested = (float(source[k]) for k in
                                  ('covered_scan3_qty', 'own_physical_qty', 'residual_requested_qty'))
        for field, expected in (('scan3_target_qty', target), ('scan3_minus_own_qty', target-own),
                ('fixed_residual_source_qty', requested),
                ('scan3_minus_own_and_fixed_residual_qty', target-own-requested)):
            try:
                actual = float(row[field])
            except (KeyError, ValueError, TypeError):
                actual = float('nan')
            evidence.close('fixed_residual_weekly_'+field, actual, expected, identity)

    # A date alone is insufficient: retained residual issues must follow the
    # day's actual own production in the exported physical event ordering.
    own_positions = defaultdict(lambda: -1)
    for position, event in enumerate(events):
        if event.get('event_type') == 'production_consume':
            own_positions[int(event['day'])] = position
    for position, event in enumerate(events):
        if event.get('event_type') == 'external_component_consume' and event.get('source_id') in result:
            evidence.check('fixed_residual_physical_issue_after_own_production',
                position > own_positions[int(event['day'])], event.get('source_id'))
    _audit_cumulative(contract, expected_rows, cumulative_rows, evidence)
    return result


def _audit_cumulative(contract, expected_rows, cumulative_rows, evidence):
    pairs = {tuple(pair) for pair in contract.get('cumulative_pairs', [])}
    cumulative = defaultdict(lambda: [Decimal(0), Decimal(0), Decimal(0)])
    expected = {}
    for row in sorted(expected_rows, key=lambda r: (r['closing_day'], r['budget_id'])):
        pair = row['node_id'], row['item_id']
        if pair not in pairs:
            continue
        state = cumulative[pair]
        prior = state[2]
        requested = _decimal(row['residual_requested_qty'])
        state[0] += _decimal(row['covered_scan3_qty'])
        state[1] += _decimal(row['own_physical_qty'])
        state[2] += requested
        expected[(*pair, row['closing_day'])] = dict(source_cells=row['scan3_source_cell'],
            covered_source_cumulative_qty=state[0], covered_own_cumulative_qty=state[1],
            prior_requested_including_backlog_qty=prior, new_residual_qty=requested,
            total_requested_qty=state[2], cumulative_unreversed_excess_qty=max(Decimal(0),state[1]+state[2]-state[0]),
            scan3_minus_own_and_fixed_residual_qty=state[0]-state[1]-state[2])
    actual = {}
    for row in cumulative_rows:
        try:
            key = row['node_id'], row['item_id'], int(row['closing_day'])
        except (KeyError, ValueError, TypeError):
            evidence.check('fixed_residual_cumulative_identity', False, row)
            continue
        evidence.check('fixed_residual_cumulative_unique', key not in actual, key)
        actual[key] = row
    evidence.check('fixed_residual_cumulative_coverage', set(actual) == set(expected), {
        'missing': sorted(set(expected)-set(actual))[:5], 'extra': sorted(set(actual)-set(expected))[:5]})
    for key in set(actual) & set(expected):
        row, wanted = actual[key], expected[key]
        evidence.check('fixed_residual_cumulative_mode', row.get('scan3_reconciliation_mode') == MODE, key)
        evidence.check('fixed_residual_cumulative_source', row.get('source_cells') == wanted['source_cells'], key)
        for field, expected_value in wanted.items():
            if field == 'source_cells':
                continue
            try:
                value = float(row[field])
            except (KeyError, ValueError, TypeError):
                value = float('nan')
            evidence.close('fixed_residual_cumulative_'+field, value, float(expected_value), key)
