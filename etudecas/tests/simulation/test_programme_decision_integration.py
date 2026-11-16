"""In-memory separation of launch authorization and purchase forecasts."""
from copy import deepcopy
from types import SimpleNamespace

import pytest

from etudecas.simulation.engine import run_first_simulation as engine
from etudecas.simulation.engine.mrp_planning import IndustrialPlanningWindow

PAIR = ("F", "PF")
COMPONENT = ("F", "C")


def evidence_row(known=4):
    return dict(programme_id="P", node_id="F", item_id="PF", state="engaged",
        period_start_day=4, period_end_day_exclusive=11, source_known_day=known,
        source_budget_role="evidence_only_v1", source_budgets=[] if known is None else [
            dict(item_id="C", qty=100, source_file="memory", source_cells="A1")])


def test_evidence_gate_still_routes_new_work_through_physical_checks():
    book = SimpleNamespace(mode="current_week_authorized_lot_multiday_v1", series={PAIR: []},
        explicit_decision_options=True, release_selection="due_existing_lot_v1",
        source_budget_role="evidence_only_v1", budgets_binding=False)
    qty, audit = engine.programme_authorization_gate(book, pair=PAIR,
        decision_day=5, normal_release_qty=100)
    assert qty == 0  # The selector, not this gate, may authorize the physical lot.
    assert audit["normal_due_qty"] == 100 and audit["source_status"] == "unknown_current_week"
    assert audit["source_known_day"] is None and audit["source_budgets"] == []
    assert audit["source_budgets_binding"] is False
    assert audit["hypothesis_not_firm_OF"] is True
    assert engine.programme_authorization_gate(book, pair=PAIR, decision_day=5,
        normal_release_qty=100, campaign_remaining_qty=75) == (100, None)


def test_nonbinding_known_budget_keeps_existing_purchase_forecast_role():
    previous = {COMPONENT: (IndustrialPlanningWindow(4, 6, 11, 70, 4, "old", "B1"),)}
    row = evidence_row()
    before = deepcopy((previous, row))
    result, audit = engine.programme_current_source_windows(previous, [row],
        decision_day=5, weekly_consumed={(4, COMPONENT): 30}, source_purchase_pairs={COMPONENT})
    window, = result[COMPONENT]
    assert (window.first_day, window.end_day_exclusive, window.qty, window.known_day) == (6, 11, 70, 4)
    assert window.source_cells == "A1"
    assert audit[0]["source_full_week_qty"] == 100 and audit[0]["model_week_consumed_qty"] == 30
    assert (previous, row) == before


def test_unknown_nonbinding_budget_neither_erases_nor_invents_purchase_forecast():
    previous = {COMPONENT: (IndustrialPlanningWindow(4, 6, 11, 70, 3, "known", "B1"),)}
    result, audit = engine.programme_current_source_windows(previous, [evidence_row(None)],
        decision_day=5, weekly_consumed={}, source_purchase_pairs={COMPONENT})
    assert result == previous and audit == []


@pytest.mark.parametrize("fault", ["future", "missing_source_with_quantity", "missing_source_binding"])
def test_purchase_forecast_still_refuses_noncausal_or_unattributed_source(fault):
    row = evidence_row(6 if fault == "future" else None)
    if fault == "missing_source_with_quantity":
        row["source_budgets"] = [dict(item_id="C", qty=100, source_file="memory", source_cells="A1")]
    if fault == "missing_source_binding":
        row["source_budget_role"] = "binding_authorization_v1"
    with pytest.raises(ValueError):
        engine.programme_current_source_windows({}, [row], decision_day=5,
            weekly_consumed={}, source_purchase_pairs={COMPONENT})
