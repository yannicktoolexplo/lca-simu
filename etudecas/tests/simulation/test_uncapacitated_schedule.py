"""Small independent arithmetic/calendar oracles; no filesystem fixtures."""
from copy import deepcopy

import pytest

from etudecas.simulation.engine.finite_production_schedule import ProductionLotRequest
from etudecas.simulation.engine.frozen_production import FrozenProductionBook
from etudecas.simulation.engine.uncapacitated_schedule import (
    UNCONSTRAINED_PRODUCTION_POLICY, next_due_frozen_order, schedule_uncapacitated_lots,
)


def test_two_due_lots_have_no_shared_quantity_ceiling():
    requests = (ProductionLotRequest("A", 107800, 12, 12, 7),
                ProductionLotRequest("B", 215600, 12, 12, 7))
    before = deepcopy(requests)
    rows = schedule_uncapacitated_lots(requests, decision_day=0, first_work_day=1,
        calendar_known_day=0, release_calendar=((7, 12), (8, 13), (9, 14)))
    assert requests == before
    assert [(r.start_day, r.physical_finish_day, r.available_day) for r in rows] == [(7, 7, 12)] * 2
    # Hand oracle: 107800+215600 units can share day7; no invented 7700/day.
    assert sum(q for r in rows for _, q in r.allocations) == 323400
    assert [r.request.proposal_id for r in rows] == ["A", "B"]


def test_future_lot_and_frozen_horizon_keep_their_launch_bounds():
    requests = (ProductionLotRequest("near", 10, 20, 20, 10),
                ProductionLotRequest("future", 20, 70, 70, 65))
    calendar = tuple((day, day+5) for day in range(1, 80))
    four = schedule_uncapacitated_lots(requests, decision_day=0, first_work_day=1,
        calendar_known_day=0, release_calendar=calendar, new_order_not_before=28)
    eight = schedule_uncapacitated_lots(requests, decision_day=0, first_work_day=1,
        calendar_known_day=0, release_calendar=calendar, new_order_not_before=56)
    assert [r.start_day for r in four] == [28, 65]
    assert [r.start_day for r in eight] == [56, 65]
    assert [r.request.qty for r in eight] == [10, 20]


def test_closed_days_move_launch_only_and_keep_source_available_date():
    # Friday is day2, the next permitted launch is Monday day5.
    rows = schedule_uncapacitated_lots((ProductionLotRequest("weekend", 100, 9, 9, 3),),
        decision_day=0, first_work_day=1, calendar_known_day=0,
        release_calendar=((1, 7), (2, 8), (5, 11), (6, 12)))
    assert (rows[0].start_day, rows[0].physical_finish_day, rows[0].available_day) == (5, 5, 11)
    assert rows[0].delay_days == 2
    assert rows[0].allocations == ((5, 100),)


def test_unknown_future_calendar_and_duplicate_or_fractional_units_are_rejected():
    lot = ProductionLotRequest("lot", 100, 7, 7, 2)
    arguments = dict(decision_day=0, first_work_day=1, calendar_known_day=0,
                     release_calendar=((1, 6), (2, 7), (3, 8)))
    with pytest.raises(ValueError, match="future calendar"):
        schedule_uncapacitated_lots((lot,), **dict(arguments, calendar_known_day=1))
    with pytest.raises(ValueError, match="unique proposal"):
        schedule_uncapacitated_lots((lot, lot), **arguments)
    with pytest.raises(ValueError, match="whole physical"):
        schedule_uncapacitated_lots((ProductionLotRequest("fraction", 1.5, 7, 7, 2),), **arguments)
    with pytest.raises(ValueError, match="unique increasing"):
        schedule_uncapacitated_lots((lot,), **dict(arguments, release_calendar=((1, 6), (1, 7))))


def test_native_frozen_book_can_complete_two_due_identities_same_day():
    pair = ("M-1430", "268967")
    book = FrozenProductionBook({"M-1810": 28, "M-1430": 56})
    for identity, day, qty in (("A", 1, 100), ("B", 1, 200), ("future", 2, 300)):
        book.register_initial(pair, order_id=identity, release_day=day, available_day=day+3, qty=qty)
    originals = {k: (v["qty"], v["planned_release_day"], v["known_day"]) for k, v in book.orders.items()}
    eligible, attempted = {"A", "B"}, set()
    for identity, qty in (("A", 100), ("B", 200)):
        selected = next_due_frozen_order(orders=book.orders.values(), pair=pair, day=1,
            eligible_ids=eligible, attempted_ids=attempted)
        assert selected == identity
        attempted.add(identity)
        book.bind(identity, day=1, campaign_id="campaign-"+identity)
        book.execute(identity, day=1, qty=qty)
    assert next_due_frozen_order(orders=book.orders.values(), pair=pair, day=1,
        eligible_ids=eligible, attempted_ids=attempted) is None
    assert sum(r["executed_qty"] for r in book.orders.values()) == 300
    assert [book.orders[k]["state"] for k in ("A", "B", "future")] == ["completed", "completed", "frozen"]
    assert originals == {k: (v["qty"], v["planned_release_day"], v["known_day"]) for k, v in book.orders.items()}


def test_refused_first_order_cannot_be_retried_or_skipped_same_day():
    pair = ("M-1810", "268091")
    book = FrozenProductionBook({"M-1810": 28})
    for identity in ("A", "B"):
        book.register_initial(pair, order_id=identity, release_day=1, available_day=5, qty=100)
    assert next_due_frozen_order(orders=book.orders.values(), pair=pair, day=1,
        eligible_ids={"A", "B"}, attempted_ids={"A"}) is None
    assert next_due_frozen_order(orders=book.orders.values(), pair=pair, day=1,
        eligible_ids={"B"}, attempted_ids=set()) is None


def test_engine_dispatch_preserves_quantities_firms_and_calendar_without_rate():
    from etudecas.simulation.engine.mrp_planning import DatedPlan, OrderProposal, Requirement
    from etudecas.simulation.engine.run_first_simulation import finite_manufacturing_plan

    proposals = (OrderProposal("A", 7, 12, 12, 100), OrderProposal("B", 7, 12, 12, 200))
    plan = DatedPlan(0, 0, (), (), proposals, (), 0, 0, 0, 300, 0, 0)
    requirements = (Requirement("need", 12, 300),)
    context = dict(capacity_mode="unmodeled", capacity_qty=0, known_day=0,
        first_work_day=1, new_order_not_before=1, intraday=True,
        # Existing obligations do not become invented machine load.
        opening_work=(("initial", 1, 999999),), frozen_work=(("firm", 4, 999999),),
        active_remaining_qty=999999, supply_calendar=dict(physical_lead_days=5))
    scheduled, audit = finite_manufacturing_plan(plan, requirements=requirements,
        firm_receipts=(), context=context)
    assert scheduled.proposals == proposals
    assert scheduled.proposed_qty == 300 and scheduled.closing_projected_qty == 0
    assert len(audit) == 2
    assert all(r["policy"] == UNCONSTRAINED_PRODUCTION_POLICY
        and r["nominal_capacity_qty"] == 0 and r["physical_finish_day"] == 7
        and r["available_day"] == 12 and r["reserved_allocations_json"] == "{}" for r in audit)


def test_uncapacitated_plan_with_no_new_lots_retains_late_firm_receipt():
    from etudecas.simulation.engine.mrp_planning import FirmReceipt, Requirement, plan_dated_requirements
    from etudecas.simulation.engine.run_first_simulation import uncapacitated_manufacturing_plan

    requirements = (Requirement("need", 7, 100),)
    receipts = (FirmReceipt("held", 10, 80, "held"),)
    plan = plan_dated_requirements(decision_day=0, available_qty=20, requirements=requirements,
        firm_receipts=receipts, lead_days=3)
    assert not plan.proposals and plan.firm_late_qty == 80
    placed, audit = uncapacitated_manufacturing_plan(plan, requirements=requirements, firm_receipts=receipts,
        context=dict(first_work_day=1, new_order_not_before=28, known_day=0,
                     supply_calendar=dict(physical_lead_days=3, origin_date="2025-01-01")))
    assert placed is plan and audit == []
    assert [(row.day, row.after_proposals_qty) for row in placed.balances] == [(0, 20), (7, -80), (10, 0)]


def test_existing_finite_mode_still_rejects_unmodeled_rate():
    from etudecas.simulation.engine.mrp_planning import DatedPlan, OrderProposal
    from etudecas.simulation.engine.run_first_simulation import finite_manufacturing_plan

    plan = DatedPlan(0, 0, (), (), (OrderProposal("A", 1, 2, 2, 100),), (), 0, 0, 0, 100, 0, 0)
    with pytest.raises(ValueError, match="explicit positive capacity"):
        finite_manufacturing_plan(plan, requirements=(), firm_receipts=(),
            context=dict(capacity_qty=0, intraday=True))


def test_dated_csv_schema_keeps_actual_protection_fields_without_widening_legacy():
    import csv
    from io import StringIO
    from etudecas.simulation.engine.run_first_simulation import (
        STOCK_PROTECTION_FIELDS, dated_plan_daily_csv_fields,
    )

    legacy = dict(day=1, node_id='M-1430', item_id='item:268967', uom='UN', action_scope='production')
    base_fields = dated_plan_daily_csv_fields()
    assert dated_plan_daily_csv_fields(rows=[legacy]) == base_fields
    assert not set(STOCK_PROTECTION_FIELDS) & set(base_fields)
    protected = dict(legacy, dated_protection_target_qty=10,
        dated_protection_max_shortfall_qty=3, dated_protection_first_shortfall_day=2)
    rows = [legacy, protected]
    fields = dated_plan_daily_csv_fields(rows=rows)
    assert fields == base_fields + STOCK_PROTECTION_FIELDS
    output = StringIO()
    writer = csv.DictWriter(output, fieldnames=fields)
    writer.writeheader()
    writer.writerows(rows)
    output.seek(0)
    decoded = list(csv.DictReader(output))
    assert decoded[0]['dated_protection_target_qty'] == ''
    assert decoded[1]['dated_protection_target_qty'] == '10'
    assert decoded[1]['dated_protection_max_shortfall_qty'] == '3'
    assert decoded[1]['dated_protection_first_shortfall_day'] == '2'
    with pytest.raises(ValueError, match='fields not in fieldnames'):
        writer.writerow(dict(protected, unexpected_field=99))
