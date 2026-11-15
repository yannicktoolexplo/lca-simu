"""Memory tests for source-authorized existing lots.

No fixture or disk operation. This candidate tests a planning hypothesis, not
an eight-week frozen industrial order book.
"""
from copy import deepcopy

import pytest

from etudecas.simulation.engine.mrp_planning import OrderProposal, WeeklyProductionProgramme


PAIR, A, B = ("F", "PF"), ("F", "A"), ("F", "B")
AUTHORIZED = "current_week_authorized_lot_multiday_v1"
RECURRENT = "current_week_existing_lot_multiday_recurrent_v1"


def make_book(*, mode=AUTHORIZED, weeks=3):
    versions = [dict(known_day=4+7*i, period_start_day=4+7*i, period_end_day_exclusive=11+7*i,
        component_budgets=[dict(item_id="A", qty=200, uom="UN", source_file="synthetic", source_cells=f"A{i}"),
            dict(item_id="B", qty=20, uom="M", source_file="synthetic", source_cells=f"B{i}")])
        for i in range(weeks)]
    payload = dict(schema_version=1, mode=mode, max_promotions_per_process=52,
        current_bucket_policy="latest_known_including_current", assumption="Candidate authorization, not industrial OF",
        series=[dict(node_id="F", output_item_id="PF", versions=versions)])
    return WeeklyProductionProgramme(payload, bom_by_pair={PAIR: [(A, 2), (B, .2)]},
        pair_uoms={PAIR: "UN", A: "UN", B: "M"})


def arguments(*, day=5, release=5, qty=100):
    return dict(pair=PAIR, decision_day=day,
        proposals=[OrderProposal("existing", release, release+3, release+3, qty)], calendar=[(day, day+3)],
        consumed={}, committed={}, available={A: 200, B: 20}, capacity_qty=25,
        multiday_placements={"existing": dict(start_day=day, physical_finish_day=day+3,
            available_day=day+3, allocations=[(day+i, 25) for i in range(4)], capacity_known_day=day)})


def complete(book, row):
    book.accept(row)
    identity = f"campaign-{row['decision_day']}"
    book.engage(PAIR, row["decision_day"], identity)
    for day, qty in row["work_allocations"]:
        book.execute(PAIR, day, identity, qty)


@pytest.mark.parametrize("release", [3, 5, 20])
def test_authorized_accepts_past_due_current_due_and_future_existing_lot_without_changing_qty(release):
    book, args = make_book(), arguments(release=release)
    before = deepcopy(args)
    row = book.select(**args)
    assert row["qty"] == 100 and row["original_proposal_id"] == "existing"
    assert row["original_release_day"] == release and row["original_available_day"] == release+3
    assert (row["release_day"], row["physical_finish_day"], row["available_day"]) == (5, 8, 8)
    assert row["programme_action"] == ("authorize_due_existing_lot" if release <= 5 else "advance_future_existing_lot")
    assert args == before


@pytest.mark.parametrize("release", [3, 5])
def test_existing_recurrent_advance_only_mode_still_refuses_due_lot(release):
    assert make_book(mode=RECURRENT).select(**arguments(release=release)) is None


def test_authorized_keeps_one_per_week_after_completion_and_complete_history():
    book = make_book()
    row = book.select(**arguments())
    complete(book, row)
    first = book.rows[PAIR]
    assert not book.can_select(PAIR, 9)
    assert book.select(**arguments(day=9, release=9)) is None
    complete(book, book.select(**arguments(day=12, release=12)))
    assert len(book.history) == 2 and book.history[0] is first
    assert [r["executed_qty"] for r in book.history] == [100, 100]


def test_authorized_does_not_reset_or_replace_an_engaged_campaign():
    book = make_book()
    book.accept(book.select(**arguments()))
    book.engage(PAIR, 5, "engaged")
    book.execute(PAIR, 5, "engaged", 25)
    before = deepcopy(book.history)
    assert book.select(**arguments(day=12, release=12)) is None
    assert book.history == before and book.rows[PAIR]["executed_qty"] == 25


@pytest.mark.parametrize("fault", ["missing_week", "future_source", "material", "consumed", "committed", "no_proposal"])
def test_authorized_abstains_without_known_budget_full_material_or_existing_proposal(fault):
    book = make_book(weeks=1)
    args = arguments()
    if fault == "missing_week": args = arguments(day=12, release=12)
    elif fault == "future_source": args = arguments(day=3, release=3)
    elif fault == "material": args["available"][A] = 199
    elif fault == "consumed": args["consumed"][A] = 1
    elif fault == "committed": args["committed"][A] = 1
    else: args["proposals"] = []
    assert book.select(**args) is None and book.history == []


def test_authorized_does_not_round_an_insufficient_budget_up_to_an_existing_lot():
    book = make_book()
    # Budget200 supports100PF; a genuine existing lot200PF needs400A.
    args = arguments(qty=200)
    args["available"] = {A: 400, B: 40}
    args["multiday_placements"]["existing"].update(physical_finish_day=12, available_day=12,
        allocations=[(d, 25) for d in range(5, 13)])
    assert book.select(**args) is None


def test_authorized_cap52_survives_new_source_weeks():
    book = make_book(weeks=53)
    for week in range(52):
        day = 5+7*week
        complete(book, book.select(**arguments(day=day, release=day)))
    assert len(book.history) == 52
    assert book.select(**arguments(day=369, release=369)) is None
