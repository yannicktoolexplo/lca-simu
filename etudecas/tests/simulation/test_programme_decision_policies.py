"""Memory-only arithmetic for due selection and nonbinding component forecasts.

No fixture files or engine run are created. The synthetic lot is100PF, made
on four days at25/day, requiring200A units and20B metres. These quantities
are independent expected values, not obtained from the production selector.
"""
from copy import deepcopy

import pytest

from etudecas.simulation.engine.mrp_planning import (
    FirmReceipt, OrderProposal, WeeklyProductionProgramme,
)
from etudecas.simulation.engine.programme_opening_coverage import (
    OPENING_COVERAGE_POLICY, reconcile_opening_programme,
)


PAIR, A, B = ('F', 'PF'), ('F', 'A'), ('F', 'B')
MODE = 'current_week_authorized_lot_multiday_v1'
DUE = 'due_existing_lot_v1'
EVIDENCE = 'evidence_only_v1'


def payload(**options):
    return dict(schema_version=1, mode=MODE, max_promotions_per_process=52,
        current_bucket_policy='latest_known_including_current',
        assumption='Synthetic independent rule comparison; not an industrial OF',
        opening_commitment_policy=OPENING_COVERAGE_POLICY,
        series=[dict(node_id='F', output_item_id='PF', versions=[dict(
            known_day=4, period_start_day=4, period_end_day_exclusive=11,
            component_budgets=[
                dict(item_id='A', qty=200, uom='UN', source_file='synthetic', source_cells='A1'),
                dict(item_id='B', qty=20, uom='M', source_file='synthetic', source_cells='B1'),
            ])])], **options)


def make_book(data=None, **options):
    return WeeklyProductionProgramme(payload(**options) if data is None else data,
        bom_by_pair={PAIR: [(A, 2), (B, .2)]}, pair_uoms={PAIR: 'UN', A: 'UN', B: 'M'})


def arguments(*, day=5, release=5, initial_qty=0):
    proposal = OrderProposal('existing', release, release+3, release+3, 100)
    orders = (() if not initial_qty else (('initial', PAIR, day+2, day+3, initial_qty,
               (('F', 'A', 2*initial_qty), ('F', 'B', .2*initial_qty))),))
    firms = tuple(FirmReceipt(row[0], row[3], row[4], 'confirmed') for row in orders)
    coverage = reconcile_opening_programme(pair=PAIR, decision_day=day, orders=orders,
        firm_receipts=firms, proposals=(proposal,))
    return dict(pair=PAIR, decision_day=day, proposals=(proposal,), calendar=[(day, day+3)],
        consumed={}, committed={}, available={A: 200, B: 20}, capacity_qty=25,
        opening_pack_pending_qty=initial_qty, opening_coverage=coverage, selection_audit=[],
        multiday_placements={'existing': dict(start_day=day, physical_finish_day=day+3,
            available_day=day+3, allocations=[(day+i, 25) for i in range(4)], capacity_known_day=day)})


def complete(book, row):
    book.accept(row)
    identity = f"campaign-{row['decision_day']}"
    book.engage(PAIR, row['decision_day'], identity)
    for day, quantity in row['work_allocations']:
        book.execute(PAIR, day, identity, quantity)


def test_legacy_keeps_future_selection_binding_budgets_and_original_record_shape():
    book = make_book()
    args = arguments(release=20)
    selected = book.select(**args)
    assert selected['qty'] == 100 and selected['original_release_day'] == 20
    assert selected['programme_action'] == 'advance_future_existing_lot'
    assert selected['work_allocations'] == ((5,25), (6,25), (7,25), (8,25))
    assert selected['source_budgets'][0]['residual_qty'] == 0
    assert selected['source_budgets'][1]['residual_qty'] == 0
    assert not {'release_selection', 'source_budget_role', 'source_budgets_binding',
                'review_period_basis', 'missing_source_budget_components'} & selected.keys()
    args['consumed'][A] = 1
    assert book.select(**args) is None
    assert args['selection_audit'][-1]['reason'] == 'source_budget_after_initial_and_consumed'


@pytest.mark.parametrize('evidence', [False, True])
def test_due_selection_refuses_future_proposal_without_modifying_plan_or_quantity(evidence):
    options = dict(release_selection=DUE)
    if evidence:
        options['source_budget_role'] = EVIDENCE
    book, args = make_book(**options), arguments(release=20)
    proposals_before = deepcopy(args['proposals'])
    assert book.select(**args) is None
    assert args['proposals'] == proposals_before
    assert args['selection_audit'][-1] == dict(proposal_id='existing',
        reason='future_net_proposal_not_due', proposal_release_day=20, decision_day=5)
    assert not book.history and not book.events


@pytest.mark.parametrize('release', [3, 5])
def test_due_selection_keeps_due_net_lot_and_original_dates(release):
    row = make_book(release_selection=DUE).select(**arguments(release=release))
    assert row['qty'] == 100
    assert (row['original_release_day'], row['original_available_day']) == (release, release+3)
    assert row['release_day'] == 5 and row['physical_finish_day'] == 8
    assert row['programme_action'] == 'authorize_due_existing_lot'
    assert row['release_selection'] == DUE and row['source_budgets_binding'] is True


def test_due_option_alone_does_not_remove_source_budget_constraint():
    data = payload(release_selection=DUE)
    data['series'][0]['versions'][0]['component_budgets'][0]['qty'] = 0
    args = arguments()
    assert make_book(data).select(**args) is None
    assert args['selection_audit'][-1]['source_budgets'][0]['residual_qty'] == -200


def test_evidence_option_alone_does_not_remove_permission_to_advance():
    row = make_book(source_budget_role=EVIDENCE).select(**arguments(release=20))
    assert row['qty'] == 100 and row['original_release_day'] == 20
    assert row['programme_action'] == 'advance_future_existing_lot'
    assert row['release_selection'] == 'advance_or_due_existing_lot_v1'


def test_nonbinding_budget_retains_negative_residual_and_exact_source_provenance():
    args = arguments()
    args['consumed'][A] = 10
    args['committed'][A] = 5
    args['available'][A] = 205  #205physical less5reserved leaves exactly200.
    assert make_book().select(**args) is None
    row = make_book(source_budget_role=EVIDENCE).select(**args)
    assert row['qty'] == 100 and row['source_budgets_binding'] is False
    assert row['source_budget_role'] == EVIDENCE
    budget = row['source_budgets'][0]
    assert (budget['qty'], budget['consumed_qty'], budget['committed_qty'],
            budget['allocated_qty'], budget['residual_qty']) == (200,10,5,200,-15)
    assert (budget['source_file'], budget['source_cells'], budget['uom']) == ('synthetic','A1','UN')
    assert row['source_known_day'] == 4


@pytest.mark.parametrize('number', [0, 1])
def test_incomplete_source_keeps_absent_components_unknown_and_all_material_guards(number):
    data = payload(source_budget_role=EVIDENCE)
    data['series'][0]['versions'][0]['component_budgets'] = data['series'][0]['versions'][0]['component_budgets'][:number]
    book, args = make_book(data), arguments()
    row = book.select(**args)
    assert row['qty'] == 100 and row['source_known_day'] == 4
    assert row['source_status'] == 'incomplete_budgets'
    assert len(row['source_budgets']) == number
    missing = row['missing_source_budget_components']
    assert [r['item_id'] for r in missing] == (['A','B'] if number == 0 else ['B'])
    assert all(r['status'] == 'unprovided_not_zero' and 'qty' not in r for r in missing)
    args['available'][B] = 19
    assert book.select(**args) is None
    assert args['selection_audit'][-1]['reason'] == 'material_reserved_or_missing'


def test_explicit_zero_is_retained_as_forecast_zero_without_becoming_physical_zero():
    data = payload(source_budget_role=EVIDENCE)
    for budget in data['series'][0]['versions'][0]['component_budgets']:
        budget['qty'] = 0
    row = make_book(data).select(**arguments())
    assert row['source_status'] == 'explicit_zero_budget'
    assert [b['qty'] for b in row['source_budgets']] == [0,0]
    assert [b['allocated_qty'] for b in row['source_budgets']] == [200,20]
    assert [b['residual_qty'] for b in row['source_budgets']] == [-200,-20]
    assert row['source_budgets_binding'] is False and row['qty'] == 100


@pytest.mark.parametrize('day,start', [(1,-3), (12,11)])
def test_missing_current_vintage_uses_calendar_without_borrowing_future_or_expired_source(day, start):
    book = make_book(source_budget_role=EVIDENCE)
    row = book.select(**arguments(day=day, release=day))
    assert row['qty'] == 100 and row['source_known_day'] is None
    assert (row['period_start_day'], row['period_end_day_exclusive']) == (start,start+7)
    assert row['review_period_basis'] == 'calendar_week_without_source'
    assert row['source_status'] == 'unknown_current_week' and row['source_budgets'] == []
    assert len(row['missing_source_budget_components']) == 2
    assert not make_book().can_select(PAIR, day)


def test_scope_without_any_version_remains_unknown_under_evidence_policy():
    data = payload(source_budget_role=EVIDENCE)
    data['series'][0]['versions'] = []
    row = make_book(data).select(**arguments())
    assert row['source_known_day'] is None and row['source_budgets'] == []
    assert row['source_status'] == 'unknown_current_week'
    assert row['period_start_day'] == 4
    del data['source_budget_role']
    with pytest.raises(ValueError, match='known versions'):
        make_book(data)


@pytest.mark.parametrize('guard', ['material', 'reserved_material', 'initial_material',
    'missing_initial_proof', 'stale_initial_proof', 'zero_capacity', 'missing_placement'])
def test_evidence_policy_cannot_bypass_physical_or_initial_coverage_guards(guard):
    args = arguments(initial_qty=30 if guard == 'initial_material' else 0)
    if guard == 'material':
        args['available'][A] = 199
    elif guard == 'reserved_material':
        args['committed'][A] = 1
    elif guard == 'initial_material':
        args['available'] = {A:240, B:26}  #240 minus60reserved leaves180, below200.
    elif guard == 'missing_initial_proof':
        args['opening_coverage'] = None
    elif guard == 'stale_initial_proof':
        args['opening_coverage'] = arguments(day=6)['opening_coverage']
    elif guard == 'zero_capacity':
        args['capacity_qty'] = 0
    else:
        args['multiday_placements'] = {}
    book = make_book(source_budget_role=EVIDENCE)
    assert book.select(**args) is None and book.history == []


def test_evidence_policy_preserves_daily_integer_component_rounding():
    data = payload(source_budget_role=EVIDENCE)
    data['series'][0]['versions'][0]['component_budgets'] = []
    book = WeeklyProductionProgramme(data, bom_by_pair={PAIR:[(A,.5)]},
        pair_uoms={PAIR:'UN',A:'UN'})
    proposal = OrderProposal('two_units',5,6,6,2)
    coverage = reconcile_opening_programme(pair=PAIR, decision_day=5, orders=(),
        firm_receipts=(), proposals=(proposal,))
    args = dict(pair=PAIR, decision_day=5, proposals=(proposal,), calendar=[(5,6)],
        consumed={}, committed={}, available={A:2}, capacity_qty=1, opening_coverage=coverage,
        multiday_placements={'two_units':dict(start_day=5,physical_finish_day=6,available_day=6,
            allocations=[(5,1),(6,1)],capacity_known_day=5)})
    row = book.select(**args)
    #Each day's0.5unit is rounded upward:1+1=2, not ceil(2*0.5)=1.
    assert row['component_requirements'][0]['qty'] == 2
    args['available'][A] = 1
    assert book.select(**args) is None


def test_calendar_review_keeps_one_lot_per_week_after_completion_and_process_cap52():
    data = payload(source_budget_role=EVIDENCE, release_selection=DUE)
    data['series'][0]['versions'] = []
    book = make_book(data)
    for week in range(52):
        day = 5+7*week
        complete(book, book.select(**arguments(day=day, release=day)))
        assert not book.can_select(PAIR, day+4)
    assert len(book.history) == 52 and sum(r['executed_qty'] for r in book.history) == 5200
    assert not book.can_select(PAIR, 369)
    assert book.select(**arguments(day=369, release=369)) is None


def test_evidence_policy_keeps_active_campaign_until_actual_completion():
    book = make_book(source_budget_role=EVIDENCE)
    row = book.select(**arguments())
    book.accept(row)
    book.engage(PAIR, 5, 'active')
    book.execute(PAIR, 5, 'active', 25)
    before = deepcopy(book.history)
    assert book.select(**arguments(day=12, release=12)) is None
    assert book.history == before and book.rows[PAIR]['executed_qty'] == 25


@pytest.mark.parametrize('day', [3,4,10,11])
def test_evidence_policy_does_not_launch_on_weekends(day):
    assert make_book(source_budget_role=EVIDENCE).select(**arguments(day=day,release=day)) is None


@pytest.mark.parametrize('field', ['period_start_day', 'period_end_day_exclusive',
                                  'source_known_day', 'release_selection', 'source_budget_role'])
def test_accept_rejects_mismatched_review_period_or_policy(field):
    book = make_book(source_budget_role=EVIDENCE)
    row = book.select(**arguments())
    row[field] = 'different'
    with pytest.raises(ValueError, match='current review period'):
        book.accept(row)
    assert not book.history


@pytest.mark.parametrize('fault', ['unknown_option', 'bad_release', 'bad_role', 'null_release',
    'null_role', 'missing_coverage', 'wrong_mode', 'empty_series', 'malformed_version'])
def test_invalid_decision_policy_payload_is_rejected(fault):
    data = payload(source_budget_role=EVIDENCE, release_selection=DUE)
    if fault == 'unknown_option':
        data['implicit_override'] = True
    elif fault == 'bad_release':
        data['release_selection'] = 'all'
    elif fault == 'bad_role':
        data['source_budget_role'] = 'ignore'
    elif fault == 'null_release':
        data['release_selection'] = None
    elif fault == 'null_role':
        data['source_budget_role'] = None
    elif fault == 'missing_coverage':
        del data['opening_commitment_policy']
    elif fault == 'wrong_mode':
        data['mode'] = 'current_week_existing_lot_multiday_recurrent_v1'
        del data['opening_commitment_policy']
    elif fault == 'empty_series':
        data['series'] = []
    else:
        data['series'][0]['versions'][0]['known_day'] = 5
    with pytest.raises(ValueError):
        make_book(data)
