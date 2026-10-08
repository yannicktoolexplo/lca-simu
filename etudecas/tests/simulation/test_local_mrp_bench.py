"""New pure-memory local MRP oracles. No filesystem fixtures or mutations."""
from copy import deepcopy
from datetime import date
from decimal import Decimal

from etudecas.simulation.analysis.local_mrp_bench import (
    coverage, dated_needs, day, run_case, stock_and_book, supply_calendar,
)
from etudecas.simulation.engine.mrp_planning import (
    LotSizing, Requirement, plan_anticipated_requirements,
)


SPEC = {"operation": "external_purchase", "standard_binding": False,
        "review_weekday": None, "lot_basis": "memory oracle without enforced lot"}


def example(rows=None, orders=None):
    return {"article": "memory", "division": "test", "unit": "UN",
        "stock_policy": {"safety_workdays": 0, "fixed_safety_stock": 0, "source": "memory"},
        "FIA_offers": [{"supplier": "memory", "supplier_lead_days": 0,
            "standard_order_quantity": 0, "source": "memory"}],
        "receipt_workdays_in_MRP": {"0": 1}, "opening_orders": orders or [],
        "MRP_snapshots": [{"vintage": "2025-01-05", "rows": rows or [
            ["2025-01-05", 0, 0, 0, 0, 0, 2], ["2025-01-12", 100, 10, 0, 0, 0, 3]]}]}


def test_H_target_changes_never_change_predictions():
    original = example()
    changed = deepcopy(original)
    for row in changed["MRP_snapshots"][0]["rows"]:
        row[1] = 9000000
    first = run_case(original, "2025-01-05", specification=SPEC)
    second = run_case(changed, "2025-01-05", specification=SPEC)
    assert first["proposals"] == second["proposals"]
    assert first["quantity_bounds"] == second["quantity_bounds"]
    assert first["H_reference_comparison"] != second["H_reference_comparison"]


def test_held_J_and_initial_past_G_do_not_create_second_receipt():
    article = example(rows=[["2025-01-05", 0, 100, 20, 0, 0, 2],
                            ["2025-01-12", 0, 0, 40, 0, 0, 3]],
        orders=[{"source_row": 9, "quantity": 40, "physical_delivery_G": "2025-01-03",
                 "availability_I": "2025-01-13", "supplier": "memory"}])
    snapshot = article["MRP_snapshots"][0]
    available, receipts, book = stock_and_book(article, snapshot, day("2025-01-05"))
    assert available == 20
    assert [(r.qty, r.state) for r in receipts] == [(40, "held")]
    assert not book["initial_retained"]
    assert book["initial_excluded"][0]["reason"] == "possible_already_held_do_not_add_over_J"
    result = run_case(article, "2025-01-05", specification=SPEC)
    # Manual net100 - available20 - held40 =40, despite the held40 being late.
    assert result["proposed_qty"] == 40
    assert result["quantity_bounds"]["unprotected_net_lower_bound"] == 40
    assert result["physical_late_qty"] == 40


def test_future_vintage_is_not_used_at_earlier_decision():
    article = example()
    baseline = run_case(article, "2025-01-05", specification=SPEC)
    article["MRP_snapshots"].append({"vintage": "2025-01-12", "rows": [
        ["2025-01-12", 0, 999999, 0, 0, 0, 200]]})
    assert run_case(article, "2025-01-05", specification=SPEC) == baseline


def test_missing_week_is_null_and_breaks_contiguous_prefix():
    article = example(rows=[["2025-01-05", 0, 0, 0, 0, 0, 2],
                            ["2025-01-19", 0, 10, 0, 0, 0, 4]])
    mask = coverage(article["MRP_snapshots"][0])
    assert mask["weekly_I"][:3] == [0, None, 10]
    assert mask["weekly_H_target"][:3] == [0, None, 0]
    assert mask["contiguous_prefix_week_count"] == 1
    assert mask["present_week_count"] == 2
    assert mask["status"] == "conditional_on_documented_needs_incomplete"


def test_receipt_nine_workdays_crosses_two_weekends():
    # Friday Jan3 + nine Mon-Fri days = Thursday Jan16 (not Jan12).
    config = {"physical_lead_days": 0, "receipt_workdays": 9, "review_weekday": None}
    rows = supply_calendar(day("2025-01-03"), day("2025-01-20"), config)
    assert rows[0] == (day("2025-01-03"), day("2025-01-16"))
    assert (date(2025, 1, 16) - date(2025, 1, 3)).days == 13


def test_sunday_review_is_weekday_based_and_UN_budget_is_conserved():
    config = {"physical_lead_days": 0, "receipt_workdays": 0, "review_weekday": 6}
    rows = supply_calendar(day("2025-01-01"), day("2025-01-20"), config)
    assert rows[0][0] == day("2025-01-05")
    assert all((2 + release) % 7 == 6 for release, _ in rows)
    article = example()
    needs, _ = dated_needs(article["MRP_snapshots"][0], day("2025-01-05"), "entirely_remaining")
    assert sum((Decimal(str(n.qty)) for n in needs), Decimal(0)) == Decimal(10)
    assert len({n.requirement_id for n in needs}) == len(needs)
    result = run_case(article, "2025-01-05", specification=SPEC)
    assert result["proposed_qty"] == 10
    # Manual oracle: ceil(10*k/7) cumulative = 2,3,5,6,8,9,10.
    assert [p["qty"] for p in result["proposals"]] == [2, 1, 2, 1, 2, 1, 1]
    assert all(p["qty"] == int(p["qty"]) for p in result["proposals"])


def test_current_week_modes_and_zero_floor_sensitivity_remain_separate():
    article = example(rows=[["2025-01-05", 0, 7, 0, 0, 0, 2],
                            ["2025-01-12", 0, 14, 0, 0, 0, 3]])
    included = run_case(article, "2025-01-05", specification=SPEC)
    excluded = run_case(article, "2025-01-05", current_mode="excluded", specification=SPEC)
    maximum = run_case(article, "2025-01-05", fixed_floor_mode="maximum", specification=SPEC)
    assert included["quantity_bounds"]["documented_requirements"] == 21
    assert excluded["quantity_bounds"]["documented_requirements"] == 14
    assert included["proposed_qty"] == maximum["proposed_qty"] == 21
    assert [{k: v for k, v in p.items() if k != "id"} for p in included["proposals"]] == [
        {k: v for k, v in p.items() if k != "id"} for p in maximum["proposals"]]


def test_protected_envelope_preserves_weekly_budget_and_fragment_identities():
    article = example()
    needs, _ = dated_needs(article["MRP_snapshots"][0], day("2025-01-05"), "entirely_remaining")
    _, _, audit = plan_anticipated_requirements(decision_day=4, available_qty=0,
        requirements=needs, firm_receipts=(), source_working_days=0, origin_weekday=2,
        fixed_floor_qty=0, lead_days=0, lot_sizing=LotSizing(integer=True),
        grouping_days=1, fixed_floor_mode="additive")
    protected = audit["anticipated_requirements"]
    assert sum((Decimal(str(n.qty)) for n in protected), Decimal(0)) == Decimal(10)
    assert len({n.requirement_id for n in protected}) == len(protected)
    assert all(n.requirement_id.startswith("anticipated:") for n in protected)
    assert {n.due_day for n in protected} == set(range(11, 18))


def test_exact_integer_and_genuine_above_integer_need_have_distinct_orders():
    # No tolerance may erase a real positive need, however small. Ten exact UN
    # need ten; ten plus the explicitly supplied 1e-16 forecast need eleven.
    for extra, expected in [(0, 10), (1e-16, 11)]:
        plan, _, audit = plan_anticipated_requirements(decision_day=0, available_qty=0,
            requirements=(Requirement("whole", 7, 10), Requirement("real_extra", 7, extra)),
            firm_receipts=(), source_working_days=0, origin_weekday=2,
            fixed_floor_qty=0, lead_days=0, lot_sizing=LotSizing(integer=True),
            grouping_days=1, fixed_floor_mode="additive")
        assert plan.proposed_qty == expected
        assert sum((Decimal(str(n.qty)) for n in audit["anticipated_requirements"]), Decimal(0)) == Decimal(10) + Decimal(str(extra))
