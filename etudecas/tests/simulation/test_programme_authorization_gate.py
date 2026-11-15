"""Memory tests for the mandatory source-programme gate."""
from copy import deepcopy
from types import SimpleNamespace

import pytest

from etudecas.simulation.engine import run_first_simulation as engine
from etudecas.simulation.engine.mrp_planning import LotSizing, Requirement, WeeklyProductionProgramme


PAIR, A, B = ("F", "PF"), ("F", "A"), ("F", "B")
MODE = "current_week_authorized_lot_multiday_v1"


def source_rows(status="known_budgets_to_check"):
    budgets = [dict(item_id="A", qty=200, uom="UN", source_file="synthetic", source_cells="A1"),
               dict(item_id="B", qty=20, uom="M", source_file="synthetic", source_cells="B1")]
    if status == "incomplete_budgets": budgets = budgets[:1]
    if status == "explicit_zero_budget": budgets[0]["qty"] = 0
    return [dict(known_day=4, period_start_day=4, period_end_day_exclusive=11, component_budgets=budgets)]


@pytest.mark.parametrize("quantity", [100, 200])
@pytest.mark.parametrize("status", ["unknown_current_week", "incomplete_budgets", "explicit_zero_budget", "known_budgets_to_check"])
def test_authorization_gate_blocks_only_new_launch_and_retains_source_status(quantity, status):
    book = SimpleNamespace(mode=MODE, series={PAIR: source_rows(status)})
    decision = 12 if status == "unknown_current_week" else 5
    before = deepcopy(book.series)
    gated, audit = engine.programme_authorization_gate(book, pair=PAIR,
        decision_day=decision, normal_release_qty=quantity)
    assert gated == 0 and audit["normal_due_qty"] == quantity
    assert audit["source_status"] == status and audit["hypothesis_not_firm_OF"] is True
    assert audit["source_known_day"] == (None if status == "unknown_current_week" else 4)
    if status == "unknown_current_week":
        assert audit["source_budgets"] == [] and audit["source_cells"] == []
    else:
        assert audit["source_cells"][0]["source_cells"] == "A1"
    assert book.series == before


@pytest.mark.parametrize("change", ["legacy", "outside_scope", "no_book", "remaining", "WIP"])
def test_authorization_gate_passes_legacy_other_scope_and_any_engaged_work(change):
    book = SimpleNamespace(mode=MODE, series={PAIR: source_rows()})
    args = dict(pair=PAIR, decision_day=5, normal_release_qty=200)
    if change == "legacy": book.mode = "current_week_existing_lot_multiday_recurrent_v1"
    elif change == "outside_scope": args["pair"] = ("other", "PF")
    elif change == "no_book": book = None
    elif change == "remaining": args["campaign_remaining_qty"] = 75
    else: args["executed_wip_qty"] = 25
    assert engine.programme_authorization_gate(book, **args) == (200, None)


def test_authorization_gate_does_not_reuse_a_future_version():
    book = SimpleNamespace(mode=MODE, series={PAIR: source_rows()})
    qty, audit = engine.programme_authorization_gate(book, pair=PAIR, decision_day=3, normal_release_qty=100)
    assert qty == 0 and audit["source_status"] == "unknown_current_week"
    assert audit["source_known_day"] is None


def test_authorization_gate_selection_and_counterfactual_preserve200_with_one_approved100():
    payload = dict(schema_version=1, mode=MODE, max_promotions_per_process=52,
        current_bucket_policy="latest_known_including_current", assumption="Explicit candidate, not industrial firm OF",
        series=[dict(node_id="F", output_item_id="PF", versions=source_rows())])
    book = WeeklyProductionProgramme(payload, bom_by_pair={PAIR: [(A, 2), (B, .2)]},
        pair_uoms={PAIR: "UN", A: "UN", B: "M"})
    capacity = dict(capacity_qty=25, known_day=4, first_work_day=5, current_capacity_qty=25,
        closed_days=(), active_remaining_qty=0, opening_work=(), intraday=True,
        supply_calendar=dict(physical_lead_days=3, receipt_days=0, origin_date="2025-01-01"))
    inputs = dict(decision_day=5, snapshot_day=4, available_qty=0,
        requirements=[Requirement("first", 8, 100), Requirement("second", 16, 100)], firm_receipts=[],
        lead_days=3, lot_sizing=LotSizing(minimum=100, multiple=100, maximum=100, integer=True),
        manufacturing_capacity=capacity)
    saved = deepcopy(inputs)
    normal_due, original = engine.dated_production_release(**inputs)
    assert sum(p.qty for p in original.proposals) == 200 and normal_due == 100
    gated, audit = engine.programme_authorization_gate(book, pair=PAIR, decision_day=5,
        normal_release_qty=normal_due)
    assert gated == 0 and audit["normal_due_qty"] == 100
    placements = engine.programme_multiday_placements(original.proposals, decision_day=5,
        context=capacity, allow_due=True)
    row = book.select(pair=PAIR, decision_day=5, proposals=original.proposals, calendar=[(5, 8)],
        consumed={}, committed={}, available={A: 200, B: 20}, capacity_qty=25,
        multiday_placements=placements)
    assert row["qty"] == 100 and row["programme_action"] == "authorize_due_existing_lot"
    proof = engine.programme_replacement_check(row, original, **inputs)
    assert proof["status"] == "advanced_existing_lot"  # Existing status means quantity retained.
    assert proof["before_proposed_qty"] == proof["after_with_programme_qty"] == 200
    assert sum(p["qty"] for p in proof["remaining_proposals"]) == 100
    book.accept(row)
    assert len(book.history) == 1 and book.rows[PAIR]["qty"] == 100
    assert inputs == saved
