"""Bounded recurrent programme: independent quantities, memory-only state."""
from copy import deepcopy

import pytest

from etudecas.simulation.engine.mrp_planning import OrderProposal, WeeklyProductionProgramme


PAIR = ("F", "PF")
A, B = ("F", "A"), ("F", "B")
MODE = "current_week_existing_lot_multiday_recurrent_v1"


def programme(*, weeks=3, mode=MODE, limit=None):
    versions = []
    for week in range(weeks):
        day = 4 + 7 * week
        versions.append(dict(known_day=day, period_start_day=day, period_end_day_exclusive=day+7,
            component_budgets=[dict(item_id="A", qty=220, uom="UN", source_file="synthetic",
                source_cells=f"A{week+1}"), dict(item_id="B", qty=22, uom="M",
                source_file="synthetic", source_cells=f"B{week+1}")]))
    payload = dict(schema_version=1, mode=mode, max_promotions_per_process=(
        limit if limit is not None else 52 if mode==MODE else 1),
        current_bucket_policy="latest_known_including_current", assumption="Synthetic explicit candidate",
        series=[dict(node_id=PAIR[0], output_item_id=PAIR[1], versions=versions)])
    return WeeklyProductionProgramme(payload, bom_by_pair={PAIR: [(A, 2), (B, .2)]},
        pair_uoms={PAIR: "UN", A: "UN", B: "M"})


def selection(book, day, **changes):
    identity = f"future-{day}"
    args = dict(pair=PAIR, decision_day=day,
        proposals=[OrderProposal(identity, day+20, day+23, day+23, 100)], calendar=[(day, day+3)],
        consumed={}, committed={}, available={A: 200, B: 20}, capacity_qty=25,
        multiday_placements={identity: dict(start_day=day, physical_finish_day=day+3,
            available_day=day+3, allocations=[(day+i, 25) for i in range(4)], capacity_known_day=day)})
    args.update(changes)
    return book.select(**args)


def complete(book, row):
    book.accept(row)
    campaign = f"campaign-{row['decision_day']}"
    book.engage(PAIR, row["decision_day"], campaign)
    for day, qty in row["work_allocations"]:
        book.execute(PAIR, day, campaign, qty)
    return book.rows[PAIR]


def test_recurrent_promotes_next_known_week_after_completion_preserving_history():
    book = programme()
    first = complete(book, selection(book, 5))
    before = deepcopy(first)
    assert first is book.history[0] and first is book.rows[PAIR]
    assert (first["qty"], first["executed_qty"], first["executed_day"]) == (100, 100, 8)
    assert book.can_select(PAIR, 12)
    second = selection(book, 12)
    assert second["source_known_day"] == 11 and second["qty"] == 100
    complete(book, second)
    assert len(book.history) == 2 and book.history[0] is first
    assert first == before and book.history[1] is book.rows[PAIR]
    assert [r["state"] for r in book.history] == ["executed", "executed"]
    assert sum(r["executed_qty"] for r in book.history) == 200
    assert sum(e.get("executed_today_qty", 0) for e in book.events) == 200


def test_recurrent_refuses_second_promotion_in_same_week_after_completion():
    book = programme()
    complete(book, selection(book, 5))
    assert not book.can_select(PAIR, 9)
    assert selection(book, 9) is None
    assert len(book.history) == 1


def test_recurrent_refuses_proposed_and_engaged_previous_campaign_without_reset():
    book = programme()
    row = selection(book, 5)
    book.accept(row)
    assert not book.can_select(PAIR, 12)
    book.engage(PAIR, 5, "active")
    book.execute(PAIR, 5, "active", 25)
    before = deepcopy(book.history)
    assert not book.can_select(PAIR, 12) and selection(book, 12) is None
    assert book.history == before
    assert book.rows[PAIR]["executed_qty"] == 25 and book.rows[PAIR]["state"] == "engaged"


def test_recurrent_refuses_future_source_and_missing_current_week():
    book = programme(weeks=1)
    assert not book.can_select(PAIR, 3) and selection(book, 3) is None
    assert not book.can_select(PAIR, 12) and selection(book, 12) is None
    assert book.history == []


def test_recurrent_refuses_completion_recorded_after_decision_day():
    book = programme()
    row = selection(book, 5)
    book.accept(row)
    book.engage(PAIR, 5, "active")
    book.execute(PAIR, 15, "active", 100)
    assert not book.can_select(PAIR, 12)


@pytest.mark.parametrize("guard", ["budget", "material", "no_proposal", "opening_work"])
def test_recurrent_preserves_all_source_budget_and_material_gates(guard):
    book = programme()
    complete(book, selection(book, 5))
    changes = dict(consumed={A: 10}, committed={A: 10})
    valid = selection(book, 12, **changes)
    assert valid["source_budgets"][0]["residual_qty"] == 0
    if guard == "budget": changes["committed"] = {A: 11}
    elif guard == "material": changes["available"] = {A: 199, B: 20}
    elif guard == "no_proposal": changes["proposals"] = []
    else: changes["opening_pack_pending_qty"] = 1
    assert selection(book, 12, **changes) is None
    assert len(book.history) == 1 and book.rows[PAIR]["executed_qty"] == 100


def test_recurrent_accept_rechecks_week_limit_after_stale_parallel_selection():
    book = programme()
    row = selection(book, 5)
    book.accept(row)
    with pytest.raises(ValueError, match="limit"):
        book.accept(deepcopy(row))
    assert len(book.history) == 1


def test_recurrent_cap52_is_per_process_and_not_reset_at_next_week():
    book = programme(weeks=53)
    for week in range(52):
        day = 5 + 7 * week
        assert book.can_select(PAIR, day)
        row = selection(book, day)
        assert row is not None and row["qty"] == 100
        complete(book, row)
    assert len(book.history) == 52 and sum(r["executed_qty"] for r in book.history) == 5200
    assert not book.can_select(PAIR, 369)
    assert selection(book, 369) is None


@pytest.mark.parametrize("limit", [1, 51, 53, True])
def test_recurrent_requires_explicit52_bound(limit):
    with pytest.raises(ValueError, match="bounded"):
        programme(limit=limit)


def test_legacy_multiday_stays_one_promotion_after_next_week():
    book = programme(mode="current_week_existing_lot_multiday_v1")
    complete(book, selection(book, 5))
    assert book.max_promotions_per_process == 1
    assert not book.can_select(PAIR, 12) and selection(book, 12) is None
    assert len(book.history) == 1
