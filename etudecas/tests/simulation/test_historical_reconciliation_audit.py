"""Independent audit contract cases, entirely in memory; no disk fixtures."""
from copy import deepcopy
import json

import pytest

from etudecas.testing.independent_review import Evidence, declared_scan3_requirements, audit_external_component_service


PAIR = ["plant", "material"]


def contract(cumulative=True):
    return dict(schema_version=1, mode="scan3_residual_v1",
                cumulative_pairs=[PAIR] if cumulative else [])


def budget(row, first, qty=100, unit="KG"):
    return dict(node_id=PAIR[0], item_id=PAIR[1], source_row=row,
        budget_id=f"plant:material:R{row}", first_day=first,
        end_day_exclusive=first + 7, closing_day=first + 6, covered_days=7,
        covered_scan3_qty=qty, full_week_scan3_qty=qty, raw_signed_scan3_qty=-qty,
        uom=unit, source_file="source.xlsx", scan3_source_cell=f"J{row}",
        source_week_marker="2025-01-05", partial_week=False, include_in_main_source_balance=True,
        coverage_status="documented_zero" if qty == 0 else "documented_withdrawals")


def consume(day, qty, kind="production_consume", unit="KG"):
    return dict(day=day, node_id=PAIR[0], item_id=PAIR[1],
                event_type=kind, qty=qty, uom=unit)


def calculate(budgets, events, declaration=None):
    evidence = Evidence()
    result = declared_scan3_requirements(contract() if declaration is None else declaration,
                                        budgets, events, 40, "scn:BASE", evidence)
    return result, evidence


def failed(evidence):
    return {k: v for k, v in evidence.checks.items() if v["failed"]}


def test_shifted_own_consumption_carries_a_credit_without_negative_use():
    budgets = [budget(1, 5), budget(2, 12)]
    events = [consume(6, 140)]
    original = deepcopy((budgets, events))
    cumulative, evidence = calculate(budgets, events)
    assert not failed(evidence)
    # 200 industrial units -140 already used =60, not100.
    assert sum(r["qty"] for r in cumulative.values()) == 60
    row = next(iter(cumulative.values()))
    assert row["day"] == row["known"] == 18
    assert row["source"]["source_cells"] == "J2"
    weekly, evidence = calculate(budgets, events, contract(False))
    assert not failed(evidence)
    assert sum(r["qty"] for r in weekly.values()) == 100
    assert (budgets, events) == original


def test_prior_requests_credit_backlog_and_irreversible_later_excess_remains():
    result, evidence = calculate([budget(1, 5), budget(2, 12)], [consume(13, 140)])
    assert not failed(evidence)
    # First100 was already requested. The second week adds0, even if the
    # earlier100 was not yet served. Actual own140 cannot be reversed.
    assert len(result) == 1
    assert next(iter(result.values()))["qty"] == 100


def test_missing_period_and_initial_WIP_are_not_credited_as_covered_own_use():
    result, evidence = calculate([budget(1, 5), budget(3, 19)],
        [consume(6, 80, "opening_production_consume"), consume(13, 900)])
    assert not failed(evidence)
    assert [r["qty"] for r in result.values()] == [100, 100]


def test_initial_partial_week_keeps_R5_quantity_and_is_excluded_from_full_week_balance():
    row = budget(1, 0, 10, "UN")
    row.update(end_day_exclusive=5, closing_day=4, covered_days=5,
               partial_week=True, include_in_main_source_balance=False)
    result, evidence = calculate([row], [consume(1, 3, unit="UN")])
    assert not failed(evidence)
    assert next(iter(result.values()))["qty"] == 7


def test_declared_residual_is_audited_end_to_end_and_undeclared_or_early_use_fails():
    row = budget(1, 5)
    # Independent manual example: source100, no own consumption, requested at11.
    basis = dict(method="cumulative_documented_scan3_minus_own_and_prior_requested",
        node_id=PAIR[0], item_id=PAIR[1], closing_day=11, source_cells="J1",
        covered_source_cumulative_qty=100, covered_own_cumulative_qty=0,
        prior_requested_including_backlog_qty=0, new_residual_qty=100,
        total_requested_qty=100, cumulative_unreversed_excess_qty=0,
        timing="Sunday closing, not measured production date",
        planning_use="no future observation supplied to planner")
    note = dict(scope="estimated_non_modelled_component_use",
        physical_demand_source="reconstructed_scan3_residual_not_identified_other_format",
        due_day=11, known_day=11, cycle_index=0, scenario_id="scn:BASE",
        demand_id="plant:material:R1", source_file="source.xlsx", source_cells="J1",
        estimation_basis=json.dumps(basis))
    event = dict(day=11, node_id=PAIR[0], item_id=PAIR[1], uom="KG", qty=100,
        event_type="external_component_consume",
        source_id="external:scn:BASE:zz-reconciled-F3:plant:material:R1:D11", notes=json.dumps(note))
    series = [dict(day=d, node_id=PAIR[0], item_id=PAIR[1], uom="KG",
        demand_qty=100 if d == 11 else 0, consumed_qty=100 if d == 11 else 0,
        backlog_start_qty=0, backlog_end_qty=0, required_qty=100 if d == 11 else 0,
        available_before_qty=100, available_after_qty=0 if d == 11 else 100,
        core_consumed_qty=0, total_component_consumed_qty=100 if d == 11 else 0)
        for d in range(12)]
    policy = dict(scenario_id="scn:BASE", rows=[dict(node_id=PAIR[0], item_id=PAIR[1],
        period_start_day=0, known_day=0, period_days=7, qty=0, uom="KG", demand_id="zero")])
    reconciliation = dict(contract=contract(), budgets=[row])
    evidence = Evidence()
    audit_external_component_service(series, [event], [], policy, 12, evidence, reconciliation=reconciliation)
    assert not failed(evidence)
    undeclared = Evidence()
    audit_external_component_service(series, [event], [], policy, 12, undeclared)
    assert "external_event_matches_declared_requirement" in failed(undeclared)
    early = Evidence()
    audit_external_component_service(series, [dict(event, day=10)], [], policy, 12, early,
                                      reconciliation=reconciliation)
    assert "external_event_known_and_due" in failed(early)


@pytest.mark.parametrize("change, expected", [
    ("mode", "scan3_declared_contract"),
    ("unknown_pair", "scan3_cumulative_pairs_have_budgets"),
    ("duplicate", "scan3_budget_unique"),
    ("overlap", "scan3_budget_disjoint"),
    ("missing_source", "scan3_budget_contract"),
    ("future_closing", "scan3_budget_contract"),
    ("wrong_proration", "scan3_covered_source_quantity"),
    ("fractional_UN", "scan3_source_integer_UN"),
])
def test_malformed_declarations_are_refused(change, expected):
    c, b = contract(), [budget(1, 5)]
    if change == "mode": c["mode"] = "silent_auto_fix"
    elif change == "unknown_pair": c["cumulative_pairs"] = [["elsewhere", "unknown"]]
    elif change == "duplicate": b.append(deepcopy(b[0]))
    elif change == "overlap": b.append(budget(2, 5))
    elif change == "missing_source": b[0]["scan3_source_cell"] = ""
    elif change == "future_closing": b[0]["closing_day"] = 50
    elif change == "wrong_proration": b[0]["covered_scan3_qty"] = 99
    elif change == "fractional_UN": b = [budget(1, 5, 10.5, "UN")]
    _, evidence = calculate(b, [], c)
    assert expected in failed(evidence)
