"""Memory-only network oracles; no file fixtures, mutation probes or subprocesses."""
from copy import deepcopy

import pytest

from etudecas.simulation.engine.mrp_planning import FirmReceipt, LotSizing, Requirement, StockProtection
from etudecas.simulation.engine.run_first_simulation import plan_component_network

PF = ("M", "PF")
MAIN = ("M", "NEW")
OLD = ("M", "OLD")


def inputs():
    return dict(decision_day=81,
        requirements_by_pair={PF: [Requirement("client", 88, 107800)]},
        available_by_pair={MAIN: 0, OLD: 53900},
        firm_receipts_by_pair={MAIN: [FirmReceipt("purchase", 92, 120000)]},
        transport_sources_by_pair={}, bom_by_pair={PF: [(MAIN, 1)]},
        lead_days_by_pair={PF: 1, MAIN: 1}, lot_sizing_by_pair={PF: LotSizing(integer=True)},
        reserve_targets_by_pair={}, coverage_days_by_pair={},
        active_campaigns_by_pair={PF: ("C", 53900, 53900, 88)},
        reference_substitutes_by_pair={MAIN: [dict(node_id="M", old_item_id="OLD",
            new_item_id="NEW", start_day=0, end_day=120,
            consume_policy="use_old_until_new_stock_available", transition_id="transition")]},
        item_uoms={"NEW": "UN", "OLD": "UN"})


def test_engaged_substitute_corrects_four_day_promise_without_stock_or_credit_creation():
    args = inputs()
    before = deepcopy(args)
    plans, needs, audit = plan_component_network(**args)
    assert audit[PF]["firm_receipts"] == [FirmReceipt("campaign:C", 88, 107800, "confirmed")]
    assert sum(r.qty for r in needs[OLD]) == 53900
    assert sum(r.qty for r in needs[MAIN]) == 0
    assert plans[OLD].proposals == () and plans[PF].proposals == ()
    assert sum(a.qty for a in plans[OLD].allocations) == 53900
    assert plans[PF].late_qty == 0
    assert args == before


def test_engaged_partial_substitute_leaves_principal_receipt_bound():
    args = inputs()
    args["available_by_pair"][OLD] = 30000
    plans, needs, audit = plan_component_network(**args)
    assert sum(r.qty for r in needs[OLD]) == 30000
    assert sum(r.qty for r in needs[MAIN]) == 23900
    assert audit[PF]["firm_receipts"] == [FirmReceipt("campaign:C", 92, 107800, "confirmed")]
    assert plans[OLD].proposals == ()


def test_two_engaged_campaigns_share_single_substitute_pool():
    args = inputs()
    second = ("M", "PF2")
    args["available_by_pair"][OLD] = 60000
    args["active_campaigns_by_pair"][second] = ("C2", 53900, 53900, 88)
    args["bom_by_pair"][second] = [(MAIN, 1)]
    args["requirements_by_pair"][second] = [Requirement("client2", 88, 107800)]
    plans, needs, audit = plan_component_network(**args)
    assert sum(r.qty for r in needs[OLD]) == 60000
    assert sum(r.qty for r in needs[MAIN]) == 47800
    assert len({r.requirement_id for r in needs[OLD]}) == len(needs[OLD])
    assert plans[OLD].proposals == ()
    assert sum(r.qty for p in (PF, second) for r in audit[p]["firm_receipts"]) == 215600


@pytest.mark.parametrize("condition", ["principal_present", "principal_arrives", "expired", "protected", "own_need"])
def test_ambiguous_substitution_keeps_conservative_principal_plan(condition):
    args = inputs()
    if condition == "principal_present":
        args["available_by_pair"][MAIN] = 1
    elif condition == "principal_arrives":
        args["firm_receipts_by_pair"][MAIN] = [FirmReceipt("purchase", 85, 120000)]
    elif condition == "expired":
        args["reference_substitutes_by_pair"][MAIN][0]["end_day"] = 87
    elif condition == "protected":
        args["protection_by_pair"] = {OLD: [StockProtection("safety", 82, 1)]}
    else:
        args["requirements_by_pair"][OLD] = [Requirement("own", 82, 1)]
    _, needs, audit = plan_component_network(**args)
    assert sum(r.qty for r in needs[MAIN] if r.requirement_id.startswith("campaign:")) == 53900
    assert sum(r.qty for r in needs.get(OLD, ()) if r.requirement_id.startswith("campaign:")) == 0
    assert audit[PF]["firm_receipts"][0].available_day == (88 if condition == "principal_arrives" else 92)


def test_absent_substitution_keeps_legacy_requirement_identity_and_results():
    args = inputs()
    args.pop("reference_substitutes_by_pair")
    args.pop("item_uoms")
    legacy = plan_component_network(**args)
    empty = plan_component_network(**dict(args, reference_substitutes_by_pair={}))
    assert legacy == empty
    assert legacy[1][MAIN] == [Requirement("campaign:C:M|NEW", 82, 53900)]
    assert legacy[2][PF]["firm_receipts"][0].available_day == 92
