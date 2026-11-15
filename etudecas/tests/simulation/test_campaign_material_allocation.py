"""Independent memory-only material allocations; no fixtures, files or runs."""
from copy import deepcopy

import pytest

from etudecas.simulation.engine.campaign_material_allocation import allocate_campaign_materials
from etudecas.simulation.engine.mrp_planning import FirmReceipt, Requirement


PF, MAIN, OLD = ("M-1430", "item:268967"), ("M-1430", "item:344135"), ("M-1430", "item:EX-344135")


def case(*, remaining=53900, wip=53900, old=53900, principal=0, finish=88):
    transition = dict(node_id=MAIN[0], new_item_id=MAIN[1], old_item_id=OLD[1],
        start_day=0, end_day=120, consume_policy="use_old_until_new_stock_available", uom="UN")
    return dict(decision_day=81, active_campaigns_by_pair={PF: ("engaged", remaining, wip, finish)},
        bom_by_pair={PF: [(MAIN, 1)]}, available_by_pair={MAIN: principal, OLD: old},
        firm_receipts_by_pair={MAIN: [FirmReceipt("later", 92, 100, "confirmed")]},
        requirements_by_pair={}, reserve_targets_by_pair={}, reference_substitutes_by_pair={MAIN: [transition]},
        item_uoms={MAIN[1]: "UN", OLD[1]: "UN"})


def amounts(rows):
    return {r["consumed_pair"]: r["qty"] for r in rows}


def test_campaign_substitute_captured53900_remaining_excludes53900_executed_wip():
    args = case(); before = deepcopy(args)
    allocated, audit = allocate_campaign_materials(**args)
    assert amounts(allocated[PF]) == {OLD: 53900}
    assert audit[PF]["remaining_work_qty"] == audit[PF]["excluded_executed_wip_qty"] == 53900
    assert audit[PF]["components"][0]["remaining_bom_qty"] == 53900
    assert audit[PF]["components"][0]["attempts"][0]["reason"] == "allocated_current_stock"
    assert args == before and args["available_by_pair"][OLD] == 53900
    assert len(args["firm_receipts_by_pair"][MAIN]) == 1


def test_campaign_substitute_partial20_keeps30_on_original_principal_identity():
    args = case(remaining=50, wip=0, old=20)
    allocated, _ = allocate_campaign_materials(**args)
    assert amounts(allocated[PF]) == {OLD: 20, MAIN: 30}
    principal, = [r for r in allocated[PF] if r["consumed_pair"] == MAIN]
    assert principal["requirement_id"] == "campaign:engaged:M-1430|item:344135"
    assert sum(r["qty"] for r in allocated[PF]) == 50


def test_campaign_substitute_without_option_is_identical_to_historical_principal_need():
    args = case(remaining=50, wip=20)
    args["reference_substitutes_by_pair"] = None
    allocated, _ = allocate_campaign_materials(**args)
    assert allocated[PF] == (dict(required_pair=MAIN, consumed_pair=MAIN, qty=50,
        requirement_id="campaign:engaged:M-1430|item:344135"),)


def test_campaign_without_substitution_preserves_exact_legacy_float_BOM_product():
    args = case(remaining=.1, wip=0)
    args["reference_substitutes_by_pair"] = None
    args["bom_by_pair"][PF] = [(MAIN, .2)]
    allocated, _ = allocate_campaign_materials(**args)
    assert allocated[PF][0]["qty"] == .1 * .2


def test_campaign_substitute_shared_pool_obeys_stable_campaign_order_and_never_overallocates():
    args = case(remaining=40, old=50)
    other = (PF[0], "item:999999")
    args["active_campaigns_by_pair"] = {other: ("second", 40, 0, 88), PF: ("first", 40, 0, 88)}
    args["bom_by_pair"][other] = [(MAIN, 1)]
    before = deepcopy(args)
    allocated, _ = allocate_campaign_materials(**args)
    assert amounts(allocated[PF]) == {OLD: 40}
    assert amounts(allocated[other]) == {OLD: 10, MAIN: 30}
    assert sum(r["qty"] for rows in allocated.values() for r in rows if r["consumed_pair"] == OLD) == 50
    assert args == before


def test_campaign_substitute_two_bom_components_same_old_have_distinct_ids_and_shared_pool():
    args = case(remaining=30, old=40)
    main2 = (MAIN[0], "item:OTHER")
    args["bom_by_pair"][PF].append((main2, 1))
    args["item_uoms"][main2[1]] = "UN"
    transition = dict(args["reference_substitutes_by_pair"][MAIN][0], new_item_id=main2[1])
    args["reference_substitutes_by_pair"][main2] = [transition]
    allocated, _ = allocate_campaign_materials(**args)
    assert [(r["required_pair"], r["consumed_pair"], r["qty"]) for r in allocated[PF]] == [
        (MAIN, OLD, 30), (main2, OLD, 10), (main2, main2, 20)]
    assert len({r["requirement_id"] for r in allocated[PF]}) == 3


@pytest.mark.parametrize("fault,reason", [
    ("principal", "principal_usable_stock_positive"),
    ("firm_at_finish", "principal_firm_receipt_before_finish"),
    ("firm_before_finish", "principal_firm_receipt_before_finish"),
    ("starts_later", "transition_not_active_through_finish"),
    ("ends_earlier", "transition_not_active_through_finish"),
    ("policy", "unsupported_policy"), ("ratio", "non_unit_ratio"),
    ("unit_missing", "units_missing_or_mismatched"), ("unit_different", "units_missing_or_mismatched"),
    ("site", "reference_or_site_mismatch"),
    ("protected", "protected_competing_scope"),
    ("own_need", "substitute_has_own_requirements"),
    ("reserve", "substitute_has_reserve_target"),
])
def test_campaign_substitute_inadmissible_case_retains_full_principal_with_reason(fault, reason):
    args = case(remaining=50, old=100)
    transition = args["reference_substitutes_by_pair"][MAIN][0]
    if fault == "principal": args["available_by_pair"][MAIN] = 1
    elif fault.startswith("firm_"):
        args["firm_receipts_by_pair"][MAIN] = [FirmReceipt("arriving", 88 if fault == "firm_at_finish" else 87, 1, "confirmed")]
    elif fault == "starts_later": transition["start_day"] = 82
    elif fault == "ends_earlier": transition["end_day"] = 87
    elif fault == "policy": transition["consume_policy"] = "use_any_stock"
    elif fault == "ratio": transition["ratio"] = 2
    elif fault == "unit_missing": del args["item_uoms"][OLD[1]]
    elif fault == "unit_different": args["item_uoms"][OLD[1]] = "KG"
    elif fault == "site": transition["node_id"] = "other_site"
    elif fault == "protected": args["protected_component_pairs"] = {OLD}
    elif fault == "own_need": args["requirements_by_pair"][OLD] = [Requirement("other_use", 100, 1)]
    else: args["reserve_targets_by_pair"][OLD] = 1
    allocated, audit = allocate_campaign_materials(**args)
    assert amounts(allocated[PF]) == {MAIN: 50}
    assert audit[PF]["components"][0]["attempts"][0]["reason"] == reason


def test_campaign_substitute_transition_finish_boundary_is_inclusive():
    args = case()
    args["reference_substitutes_by_pair"][MAIN][0].update(start_day=81, end_day=88)
    allocated, _ = allocate_campaign_materials(**args)
    assert amounts(allocated[PF]) == {OLD: 53900}


def test_campaign_substitute_future_old_receipt_never_creates_allocatable_stock():
    args = case(remaining=50, old=0)
    args["firm_receipts_by_pair"][OLD] = [FirmReceipt("future_old", 82, 100, "confirmed")]
    before = deepcopy(args)
    allocated, audit = allocate_campaign_materials(**args)
    assert amounts(allocated[PF]) == {MAIN: 50}
    assert audit[PF]["components"][0]["attempts"][0]["reason"] == "no_current_substitute_stock"
    assert args == before


def test_campaign_substitute_integer_old_units_preserve_theoretical_principal_residual():
    args = case(remaining=1.5, wip=0, old=10)
    args["item_uoms"] = {MAIN: "UN", OLD: "UN"}
    allocated, _ = allocate_campaign_materials(**args)
    assert amounts(allocated[PF]) == {OLD: 1, MAIN: .5}
    assert sum(r["qty"] for r in allocated[PF]) == 1.5


def test_campaign_substitute_transition_list_order_uses_first_stock_then_second():
    args = case(remaining=50, old=20)
    old2 = (OLD[0], "item:SECOND_OLD")
    args["reference_substitutes_by_pair"][MAIN].append(dict(
        args["reference_substitutes_by_pair"][MAIN][0], old_item_id=old2[1]))
    args["item_uoms"][old2[1]] = "UN"
    args["available_by_pair"][old2] = 40
    allocated, audit = allocate_campaign_materials(**args)
    assert [(r["consumed_pair"], r["qty"]) for r in allocated[PF]] == [(OLD, 20), (old2, 30)]
    assert [r["transition_index"] for r in audit[PF]["components"][0]["attempts"]] == [0, 1]
    assert len({r["requirement_id"] for r in allocated[PF]}) == 2


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), -1, True, 1.5])
def test_campaign_substitute_rejects_invalid_or_fractional_physical_un_stock(bad):
    args = case(); args["available_by_pair"][OLD] = bad
    with pytest.raises(ValueError, match="stock|Stock"):
        allocate_campaign_materials(**args)


@pytest.mark.parametrize("field", ["remaining", "wip", "ratio", "receipt", "reserve"])
def test_campaign_substitute_rejects_nonfinite_essential_quantities(field):
    args = case()
    if field == "remaining": args["active_campaigns_by_pair"][PF] = ("engaged", float("nan"), 0, 88)
    elif field == "wip": args["active_campaigns_by_pair"][PF] = ("engaged", 1, float("inf"), 88)
    elif field == "ratio": args["bom_by_pair"][PF] = [(MAIN, float("nan"))]
    elif field == "receipt": args["firm_receipts_by_pair"][MAIN] = [FirmReceipt("invalid", 92, float("inf"), "confirmed")]
    else: args["reserve_targets_by_pair"][OLD] = float("nan")
    with pytest.raises(ValueError, match="finite"):
        allocate_campaign_materials(**args)
