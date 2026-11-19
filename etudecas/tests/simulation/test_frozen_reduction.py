"""In-memory arithmetic oracles; no files, native runs or fixture mutation."""
from copy import deepcopy
from dataclasses import replace

import pytest

from etudecas.simulation.engine.frozen_production import (
    FrozenProductionBook, J0_NET_PLAN_HYPOTHESIS_POLICY,
)
from etudecas.simulation.engine.frozen_reduction import (
    _compare_coverage, reduce_unstarted_frozen_orders,
)
from etudecas.simulation.engine.frozen_external_coverage import assess_frozen_external_coverage
from etudecas.simulation.engine.mrp_planning import (
    Allocation, DatedPlan, FirmReceipt, IndustrialPlanningWindow, LotSizing, OrderProposal, ProjectedBalance, Requirement, StockProtection,
    plan_dated_requirements, plan_with_stock_protection,
)

PF = ("M-1810", "item:PF")
COMPONENT = ("M-1810", "item:component")
CLIENT = ("C-customer", "item:PF")
NORMALIZED_COMPONENT = ("M-1810", "item:normalized_component")


def _case(*, extra_qty=0):
    book = FrozenProductionBook({PF[0]:28},bom_by_pair={PF:[(COMPONENT,2)]})
    book.reconcile(PF,0,[OrderProposal("A",28,31,31,100),OrderProposal("B",32,35,35,100)])
    identities = {row["planned_release_day"]: row["order_id"] for row in book.orders.values()}
    book.begin_day(10)
    needs = (Requirement("first",32,90),Requirement("second",39,40))
    if extra_qty:
        needs += (Requirement("extra",40,extra_qty),)
    inputs = dict(decision_day=10,requirements_by_pair={PF:needs},
        protection_by_pair={PF:(StockProtection("safety",11,30),)},
        frozen_production_snapshot=book.planning_snapshot(10),
        manufacturing_capacity_by_pair={PF:dict(new_order_not_before=38,
            frozen_work=book.reserved_work(PF,10))})
    available = {PF:80,COMPONENT:1000}
    return book,identities,inputs,available


def _reconcile(inputs, *, available_by_pair, firm_receipts_by_pair, produced_pairs):
    """Real planner callback; expected values in tests are literal hand balances."""
    day = inputs["decision_day"]
    boundary = inputs["manufacturing_capacity_by_pair"][PF]["new_order_not_before"]
    needs = inputs["requirements_by_pair"][PF]
    floors = inputs["protection_by_pair"][PF]
    receipts = tuple(firm_receipts_by_pair.get(PF,())) + tuple(
        inputs["frozen_production_snapshot"]["receipts"].get(PF,()))
    protected = plan_with_stock_protection(decision_day=day,available_qty=available_by_pair[PF],
        requirements=needs,firm_receipts=receipts,lead_days=3,
        lot_sizing=LotSizing(minimum=100,maximum=100,multiple=100,integer=True),
        protection=floors,availability_by_release=tuple((d,d+3) for d in range(boundary,81)))
    return ({PF:{"decision_day":day,"requirements":needs,"protection":floors}},
        {PF:protected.plan},{PF:needs},{PF:{"protection_points":floors,"protected_plan":protected}})


def _run(book,inputs,available,*,callback=_reconcile,current=None):
    current = current or _reconcile(inputs,available_by_pair=available,
        firm_receipts_by_pair={},produced_pairs={PF})
    return reduce_unstarted_frozen_orders(book,day=10,network_inputs=inputs,
        available_by_pair=available,firm_receipts_by_pair={},produced_pairs={PF},
        reconcile=callback,current_result=current)


def test_surplus_whole_lot_cancelled_and_three_planning_contributions_removed():
    book,ids,inputs,available = _case()
    physical_before = deepcopy(available)
    inputs_before = deepcopy(inputs)
    row_before = deepcopy(book.orders[ids[32]])
    retained,result,audit = _run(book,inputs,available)
    # Hand oracle: 80 + 100 - 90 - 40 = 50, above the persistent safety 30.
    assert audit[0]["order_id"] == ids[32] and audit[0]["accepted"] is True
    assert audit[0]["after_max_shortfall_qty"] == 0
    assert book.orders[ids[32]]["state"] == "cancelled"
    assert book.orders[ids[28]]["state"] == "frozen"
    for field in ("order_id","qty","planned_release_day","planned_available_day","requested_day"):
        assert book.orders[ids[32]][field] == row_before[field]
    assert result[1][PF].closing_projected_qty == 50
    assert [r.receipt_id for r in retained["frozen_production_snapshot"]["receipts"][PF]] == [ids[28]]
    assert sum(r.qty for r in retained["frozen_production_snapshot"]["requirements"][COMPONENT]) == 200
    assert [row[0] for row in retained["manufacturing_capacity_by_pair"][PF]["frozen_work"]] == [ids[28]]
    assert inputs == inputs_before and available == physical_before
    assert [e["event"] for e in book.events].count("unstarted_whole_lot_cancelled") == 1
    assert not any(e["event"] == "physical_work" for e in book.events)


def test_safety_deficit_before_first_possible_new_receipt_keeps_whole_lot():
    book,ids,inputs,available = _case(extra_qty=30)
    before = deepcopy(book.__dict__)
    _,_,audit = _run(book,inputs,available)
    # Without B, 80 + 100 - 90 - 40 - 30 = 20 < 30 at J40.
    # A newly planned lot cannot arrive until J41, so its later surplus cannot help.
    decision = next(r for r in audit if r["order_id"] == ids[32])
    assert decision["accepted"] is False
    assert decision["first_worsening"] == dict(day=40,kind="physical_or_protection_deficit",before_qty=0,after_qty=10)
    assert book.__dict__ == before


def test_strict_book_default_does_not_cancel_after_the_same_need_revision():
    book,ids,inputs,available = _case()
    book.reconcile(PF,10,[])
    assert {row["state"] for row in book.orders.values()} == {"frozen"}
    assert sum(r.qty for r in book.firm_receipts(PF,10)) == 200
    assert not any(e["event"] == "unstarted_whole_lot_cancelled" for e in book.events)


def test_initial_observed_bootstrap_and_started_orders_are_not_reducible():
    book = FrozenProductionBook({PF[0]:28},bom_by_pair={PF:[(COMPONENT,2)]},
        initial_book_policy=J0_NET_PLAN_HYPOTHESIS_POLICY)
    book.register_initial(PF,order_id="FROZEN|initial_name_is_not_provenance",release_day=5,
        available_day=8,qty=100)
    empty = plan_dated_requirements(decision_day=0,available_qty=0,requirements=[],
        firm_receipts=[],lead_days=0,lot_sizing=LotSizing(integer=True))
    plan = replace(empty,proposals=(OrderProposal("bootstrap",7,10,10,100),),proposed_qty=100)
    book.adopt_initial_plan(PF,plan=plan,basis="J0 known net hypothesis")
    book.reconcile(PF,0,[OrderProposal("normal",28,31,31,100)])
    book.begin_day(28)
    normal = next(row for row in book.reducible_unstarted_orders())
    assert normal["order_id"] != "FROZEN|initial_name_is_not_provenance"
    book.bind(normal["order_id"],day=28,campaign_id="native_work")
    assert book.reducible_unstarted_orders() == ()
    for row in book.orders.values():
        with pytest.raises(ValueError,match="unstarted simulated"):
            book.cancel_unstarted_whole_lot(row["order_id"],day=28)
    book.execute(normal["order_id"],day=28,qty=100)
    assert book.reducible_unstarted_orders() == ()


def test_protection_evidence_missing_is_not_assumed_zero():
    book,ids,inputs,available = _case()
    def without_evidence(*args,**kwargs):
        result = _reconcile(*args,**kwargs)
        return result[:3] + ({PF:{}},)
    _,_,audit = _run(book,inputs,available,callback=without_evidence)
    assert all(not r["accepted"] and r["reason"] == "missing_or_invalid_dated_evidence" for r in audit)
    assert book.orders[ids[32]]["state"] == "frozen"


@pytest.mark.parametrize("changed",["requirements","protection"])
def test_changed_physical_need_or_safety_curve_cannot_justify_cancellation(changed):
    book,ids,inputs,available = _case()
    before = _reconcile(inputs,available_by_pair=available,firm_receipts_by_pair={},produced_pairs={PF})
    after = list(before)
    if changed == "requirements":
        after[2] = {PF:(Requirement("first",33,90),Requirement("second",39,40))}
        # Change allocation dates consistently, to isolate requirement identity/date guard.
        after[1] = {PF:replace(before[1][PF],allocations=tuple(replace(a,due_day=33)
            if a.requirement_id == "first" else a for a in before[1][PF].allocations))}
    else:
        after[3] = {PF:dict(before[3][PF],protection_points=(StockProtection("safety",11,29),))}
    accepted,evidence = _compare_coverage(before,tuple(after),PF,10)
    assert not accepted
    assert evidence["reason"] == ("physical_requirements_changed" if changed == "requirements" else "stock_protection_changed")


def test_requirement_delay_is_rejected_even_if_total_balances_are_unchanged():
    book,ids,inputs,available = _case()
    before = _reconcile(inputs,available_by_pair=available,firm_receipts_by_pair={},produced_pairs={PF})
    after = list(before)
    # Deliberately inconsistent totals cannot conceal a lost dated allocation.
    delayed = tuple(replace(a,available_day=33,delay_days=1)
                    if a.requirement_id == "first" else a for a in before[1][PF].allocations)
    after[1] = {PF:replace(before[1][PF],allocations=delayed)}
    accepted,evidence = _compare_coverage(before,tuple(after),PF,10)
    assert not accepted
    assert evidence["first_worsening"]["day"] == 32
    assert evidence["first_worsening"]["kind"] == "physical_requirement_coverage"


def test_new_proposal_inside_frozen_zone_cannot_replace_cancelled_order():
    book,ids,inputs,available = _case()
    def illegal_replacement(*args,**kwargs):
        result = list(_reconcile(*args,**kwargs))
        result[1] = {PF:replace(result[1][PF],proposals=(OrderProposal("illegal",37,40,40,100),))}
        return tuple(result)
    _,_,audit = _run(book,inputs,available,callback=illegal_replacement)
    assert all(not row["accepted"] and row["reason"] == "counterfactual_adds_order_inside_frozen_zone" for row in audit)
    assert all(row["offending_pair"] == list(PF) and row["offending_release_day"] == 37
               and row["offending_qty"] == 100 for row in audit)
    assert book.orders[ids[32]]["state"] == "frozen"


def test_component_purchase_inside_factory_frozen_zone_is_not_a_new_fabrication():
    book,ids,inputs,available = _case()
    def with_component_purchase(*args,**kwargs):
        result = list(_reconcile(*args,**kwargs))
        component_need = Requirement("component_purchase_need",15,200)
        result[1][COMPONENT] = plan_dated_requirements(decision_day=10,available_qty=0,
            requirements=(component_need,),firm_receipts=[],lead_days=3,
            lot_sizing=LotSizing(integer=True))
        result[2][COMPONENT] = (component_need,)
        result[3][COMPONENT] = {"protection_points":()}
        assert result[1][COMPONENT].proposals[0].release_day == 12 < 38
        return tuple(result)
    _,_,audit = _run(book,inputs,available,callback=with_component_purchase)
    decision = next(row for row in audit if row["order_id"] == ids[32])
    assert decision["accepted"]
    assert book.orders[ids[32]]["state"] == "cancelled"


def test_identical_proposals_are_counted_with_multiplicity_in_reduction_audit():
    book,ids,inputs,available = _case()
    original = _reconcile(inputs,available_by_pair=available,firm_receipts_by_pair={},produced_pairs={PF})
    plan = original[1][PF]
    assert plan.closing_projected_qty == 150  #80 + 100 + 100 - 90 - 40.
    first = OrderProposal("future_A",60,63,63,100)
    second = replace(first,proposal_id="future_B")
    before = list(original)
    before[1] = {PF:replace(plan,proposals=(first,),proposed_qty=100,closing_projected_qty=250,
        balances=plan.balances+(ProjectedBalance(63,0,0,100,150,250),))}
    after = list(original)
    after[1] = {PF:replace(plan,proposals=(first,second),proposed_qty=200,closing_projected_qty=350,
        balances=plan.balances+(ProjectedBalance(63,0,0,200,150,350),))}
    accepted,evidence = _compare_coverage(tuple(before),tuple(after),PF,10)
    assert accepted
    assert evidence["after_proposed_qty"]-evidence["before_proposed_qty"] == 100
    assert evidence["new_outside_zone_proposals"] == [dict(release_day=60,available_day=63,requested_day=63,qty=100)]


def test_future_proposal_may_defer_a_lot_only_after_its_valid_availability():
    book,ids,inputs,available = _case()
    inputs["requirements_by_pair"][PF] += (Requirement("later",60,100),)
    _,result,audit = _run(book,inputs,available)
    # Without B:50 at J39; replace its100 for J60, release J57 >= J38.
    decision = next(row for row in audit if row["order_id"] == ids[32])
    assert decision["accepted"] is True
    assert decision["after_proposed_qty"] - decision["before_proposed_qty"] == 100
    assert decision["new_outside_zone_proposals"] == [dict(release_day=57,available_day=60,requested_day=60,qty=100)]
    assert result[1][PF].late_qty == 0


def test_excluding_one_order_is_a_pure_snapshot_not_a_physical_cancellation():
    book,ids,inputs,available = _case()
    before = deepcopy(book.__dict__)
    snapshot = book.planning_snapshot(10,exclude_order_ids=(ids[32],))
    assert len(snapshot["receipts"][PF]) == 1
    assert sum(row.qty for row in snapshot["requirements"][COMPONENT]) == 200
    assert len(book.reserved_work(PF,10,exclude_order_ids=(ids[32],))) == 1
    assert book.__dict__ == before


def test_native_receipt_duplicate_cannot_finance_its_own_cancellation():
    book,ids,inputs,available = _case()
    current = _reconcile(inputs,available_by_pair=available,firm_receipts_by_pair={},produced_pairs={PF})
    _,_,audit = reduce_unstarted_frozen_orders(book,day=10,network_inputs=inputs,
        available_by_pair=available,firm_receipts_by_pair={PF:(FirmReceipt(ids[32],35,100,"confirmed"),)},
        produced_pairs={PF},reconcile=_reconcile,current_result=current)
    decision = next(row for row in audit if row["order_id"] == ids[32])
    assert not decision["accepted"]
    assert decision["reason"] == "native_frozen_receipt_credit_conflict"
    assert decision["conflicting_receipt_ids"] == [ids[32]]
    assert book.orders[ids[32]]["state"] == "frozen"


def test_native_credit_conflict_on_another_order_refuses_every_trial_before_callback():
    book,ids,inputs,available = _case()
    current = _reconcile(inputs,available_by_pair=available,firm_receipts_by_pair={},produced_pairs={PF})
    before = deepcopy(book.__dict__)
    def forbidden_callback(*args,**kwargs):
        raise AssertionError("An ambiguous native/frozen credit must stop the whole review")
    retained,result,audit = reduce_unstarted_frozen_orders(book,day=10,network_inputs=inputs,
        available_by_pair=available,firm_receipts_by_pair={PF:(FirmReceipt(ids[28],31,100,"confirmed"),)},
        produced_pairs={PF},reconcile=forbidden_callback,current_result=current)
    assert retained is inputs and result is current
    assert len(audit) == 2 and audit[0]["order_id"] == ids[32]
    assert all(not row["accepted"] and row["reason"] == "native_frozen_receipt_credit_conflict" for row in audit)
    assert all(row["conflicting_receipt_ids"] == [ids[28]] for row in audit)
    assert book.__dict__ == before


@pytest.mark.parametrize("guarded",["other_pf","client"])
def test_other_pf_or_client_dated_degradation_prevents_cancellation(guarded):
    book,ids,inputs,available = _case()
    other = ("M-1810" if guarded == "other_pf" else "C-customer", "item:other")
    current = list(_reconcile(inputs,available_by_pair=available,firm_receipts_by_pair={},produced_pairs={PF}))
    needs = (Requirement("other_need",32,20),)
    other_plan = plan_dated_requirements(decision_day=10,available_qty=20,requirements=needs,
        firm_receipts=[],lead_days=0,lot_sizing=LotSizing(integer=True))
    current[1] = dict(current[1])
    current[1][other] = other_plan
    current[2] = dict(current[2]);current[2][other] = needs
    current[3] = dict(current[3]);current[3][other] = {"protection_points":()} if guarded == "other_pf" else {}
    if guarded == "client":
        inputs["requirements_by_pair"][other] = needs
    def degrade_other(*args,**kwargs):
        result = list(_reconcile(*args,**kwargs))
        delayed = tuple(replace(a,available_day=33,delay_days=1) for a in other_plan.allocations)
        result[1][other] = replace(other_plan,allocations=delayed)
        result[2][other] = needs
        result[3][other] = current[3][other]
        return tuple(result)
    _,_,audit = reduce_unstarted_frozen_orders(book,day=10,network_inputs=inputs,
        available_by_pair=available,firm_receipts_by_pair={},produced_pairs={PF,other} if guarded == "other_pf" else {PF},
        reconcile=degrade_other,current_result=tuple(current))
    decision = next(row for row in audit if row["order_id"] == ids[32])
    assert not decision["accepted"]
    assert decision["reason"] == "other_pf_or_external_demand_worsened_or_unverified"
    assert decision["downstream_guards"][0]["first_worsening"]["day"] == 32
    assert book.orders[ids[32]]["state"] == "frozen"


def test_component_bom_needs_may_shrink_while_external_demand_stays_protected():
    book,ids,inputs,available = _case()
    external = Requirement("outside_customer",39,10)
    inputs["requirements_by_pair"][COMPONENT] = (external,)
    def with_component(*args,**kwargs):
        result = list(_reconcile(*args,**kwargs))
        needs = (external,) + tuple(args[0]["frozen_production_snapshot"]["requirements"].get(COMPONENT,()))
        plan = plan_dated_requirements(decision_day=10,available_qty=1000,requirements=needs,
            firm_receipts=[],lead_days=0,lot_sizing=LotSizing(integer=True))
        result[1][COMPONENT] = plan
        result[2][COMPONENT] = needs
        result[3][COMPONENT] = {}
        return tuple(result)
    current = with_component(inputs,available_by_pair=available,firm_receipts_by_pair={},produced_pairs={PF})
    _,_,audit = _run(book,inputs,available,callback=with_component,current=current)
    decision = next(row for row in audit if row["order_id"] == ids[32])
    assert decision["accepted"]
    guard = decision["downstream_guards"][0]
    assert guard["mode"] == "external_requirements_only" and guard["accepted"]
    assert guard["checked_requirements"] == 1


def _native_case(*, normalized=False, linked=False):
    """Small real network, including the coverage window used by the runtime."""
    book,ids,inputs,available = _case()
    inputs["requirements_by_pair"][CLIENT] = (Requirement("customer",32,20),)
    available[CLIENT] = 20
    bom = {PF:tuple(book.bom_by_pair[PF])}
    if normalized:
        available[NORMALIZED_COMPONENT] = 1000
        inputs["requirements_by_pair"][NORMALIZED_COMPONENT] = (Requirement("external:source-root",32,20),)
        if linked:
            bom[PF] += ((NORMALIZED_COMPONENT,1),)
            book.bom_by_pair[PF] = bom[PF]
        else:
            # It is a component of another modeled output, with no current OF.
            bom[("M-other", "item:other_output")] = ((NORMALIZED_COMPONENT,1),)
        inputs["industrial_windows_by_pair"] = {NORMALIZED_COMPONENT:(
            IndustrialPlanningWindow(31,31,38,70,4,"source.xlsx","I10"),)}
        inputs["industrial_target_context_by_pair"] = {NORMALIZED_COMPONENT:dict(
            window_days=30,fixed_floor_qty=0,target_days=0,safety_floor_qty=0,safety_days=0,legacy_rate=0)}
    inputs.update(transport_sources_by_pair={},bom_by_pair=bom,
        lead_days_by_pair={pair:(3 if pair==PF else 1) for pair in available},
        lot_sizing_by_pair={PF:LotSizing(minimum=100,multiple=100,maximum=100,integer=True)},
        reserve_targets_by_pair={pair:0 for pair in available},coverage_days_by_pair={pair:1 for pair in available},
        active_campaigns_by_pair={},item_uoms={pair[1]:"UN" for pair in available},
        frozen_production_snapshot=book.planning_snapshot(10),
        manufacturing_capacity_by_pair={PF:dict(capacity_mode="unmodeled",capacity_qty=0,known_day=10,
            first_work_day=11,new_order_not_before=38,intraday=True,
            frozen_work=book.reserved_work(PF,10),supply_calendar=dict(physical_lead_days=3,origin_date="2025-01-01"))})
    return book,ids,inputs,available


def _native_run(book,inputs,available,*,callback=None):
    from etudecas.simulation.engine.run_first_simulation import reconcile_production_execution_snapshot
    current = reconcile_production_execution_snapshot(inputs,available_by_pair=available,
        firm_receipts_by_pair={},produced_pairs={PF})
    retained,result,audit = reduce_unstarted_frozen_orders(book,day=10,network_inputs=inputs,
        available_by_pair=available,firm_receipts_by_pair={},produced_pairs={PF},
        reconcile=callback or reconcile_production_execution_snapshot,current_result=current)
    return retained,result,audit,current


def test_native_client_coverage_window_one_is_not_an_unreported_stock_floor():
    book,ids,inputs,available = _native_case()
    _,_,audit,current = _native_run(book,inputs,available)
    assert inputs["coverage_days_by_pair"][CLIENT] == 1
    assert current[3][CLIENT]["reserve_requirement_qty"] == 0
    assert current[3][CLIENT]["protection_points"] == ()
    decision = next(row for row in audit if row["order_id"] == ids[32])
    assert decision["accepted"]
    client_guard = next(row for row in decision["downstream_guards"] if row["node_id"] == CLIENT[0])
    assert client_guard["accepted"] and client_guard["reason"] == "dated_coverage_not_worsened"


def test_native_identical_normalized_component_needs_keep_full_coverage_guard():
    book,ids,inputs,available = _native_case(normalized=True)
    _,_,audit,current = _native_run(book,inputs,available)
    normalized = current[2][NORMALIZED_COMPONENT]
    assert "external:source-root" not in {r.requirement_id for r in normalized}
    assert sum(r.qty for r in normalized) == 70  #Source70 replaces the revocable20.
    decision = next(row for row in audit if row["order_id"] == ids[32])
    assert decision["accepted"]
    guard = next(row for row in decision["downstream_guards"] if row["item_id"] == NORMALIZED_COMPONENT[1])
    assert guard["accepted"] and guard["mode"] == "normalized_whole_pair_identical"
    assert guard["missing_external_ids_before"] == guard["missing_external_ids_after"] == ["external:source-root"]
    assert guard["checked_requirements"] == 7


def test_native_changed_normalized_component_needs_use_traced_fixed_supply():
    book,ids,inputs,available = _native_case(normalized=True,linked=True)
    _,_,audit,_ = _native_run(book,inputs,available)
    decision = next(row for row in audit if row["order_id"] == ids[32])
    assert decision["accepted"]
    guard = next(row for row in decision["downstream_guards"] if row["item_id"] == NORMALIZED_COMPONENT[1])
    assert guard["reason"] == "fixed_supply_revised_coverage_not_worsened"
    assert guard["mode"] == "fixed_supply_revised_forecast"
    assert guard["new_external_qty"] == 70
    assert not guard["creates_proposals"]
    assert guard["first_removed_or_changed_requirement"] is not None
    assert guard["first_added_or_changed_requirement"] is not None
    assert book.orders[ids[32]]["state"] == "cancelled"


@pytest.mark.parametrize("change",["lost_need","late_allocation"])
def test_normalization_fallback_never_ignores_a_lost_need_or_later_allocation(change):
    from etudecas.simulation.engine.run_first_simulation import reconcile_production_execution_snapshot
    book,ids,inputs,available = _native_case(normalized=True)
    def altered(*args,**kwargs):
        result = list(reconcile_production_execution_snapshot(*args,**kwargs))
        first = result[2][NORMALIZED_COMPONENT][0]
        if change == "lost_need":
            result[2][NORMALIZED_COMPONENT] = result[2][NORMALIZED_COMPONENT][1:]
        else:
            plan = result[1][NORMALIZED_COMPONENT]
            result[1][NORMALIZED_COMPONENT] = replace(plan,allocations=tuple(
                replace(a,available_day=first.due_day+1,delay_days=1)
                if a.requirement_id == first.requirement_id else a for a in plan.allocations))
        return tuple(result)
    _,_,audit,_ = _native_run(book,inputs,available,callback=altered)
    decision = next(row for row in audit if row["order_id"] == ids[32])
    assert not decision["accepted"]
    guard = next(row for row in decision["downstream_guards"] if row["item_id"] == NORMALIZED_COMPONENT[1])
    if change == "lost_need":
        assert guard["reason"] == "external_forecast_provenance_or_fixed_supply_invalid"
        assert "reconciliation audit" in guard["detail"]
    else:
        assert guard["mode"] == "normalized_whole_pair_identical"
        assert guard["reason"] == "dated_coverage_worsened"
        assert guard["first_worsening"]["day"] == 31


def _manual_fixed_plan(needs,stock,receipts=(),proposals=()):
    """Independent small FIFO fixture: no planner/helper used to construct it."""
    supply = [("opening_stock",10,stock,"available")]
    supply += [(r.receipt_id,r.available_day,r.qty,r.state) for r in receipts]
    supply += [(p.proposal_id,p.available_day,p.qty,"proposal") for p in proposals]
    remaining = [list(row) for row in sorted(supply,key=lambda row:(row[1],row[0]))]
    allocations = []
    for need in sorted(needs,key=lambda r:(r.due_day,r.requirement_id)):
        left = need.qty
        for row in remaining:
            used = min(left,row[2])
            if used:
                allocations.append(Allocation(need.requirement_id,row[0],row[3],used,
                    need.due_day,row[1],max(0,row[1]-need.due_day)))
                left -= used;row[2] -= used
    dates = sorted({10}|{r.due_day for r in needs}|{row[1] for row in supply})
    balances = tuple(ProjectedBalance(when,sum(r.qty for r in needs if r.due_day==when),
        sum(r.qty for r in receipts if r.available_day==when),
        sum(p.qty for p in proposals if p.available_day==when),
        stock+sum(r.qty for r in receipts if r.available_day<=when)-sum(r.qty for r in needs if r.due_day<=when),
        sum(row[2] for row in supply if row[1]<=when)-sum(r.qty for r in needs if r.due_day<=when)) for when in dates)
    return DatedPlan(10,stock,(),tuple(allocations),tuple(proposals),balances,
        sum(a.qty for a in allocations if a.delay_days),sum(a.qty*a.delay_days for a in allocations),
        0,sum(p.qty for p in proposals),0,balances[-1].after_proposals_qty)


def _external_case(*,old_own=(),new_own=(),old_external=(),new_external=(),stock=100,
                   old_receipts=(),new_receipts=(),old_proposals=(),new_proposals=(),
                   old_floor=(),new_floor=(),period=40,source_qty=180):
    """A known source window; raw root is explicitly normalized into daily IDs."""
    pair = NORMALIZED_COMPONENT
    def external(rows):
        return tuple(Requirement(f"external:industrial-planning:{pair[0]}:{pair[1]}:W{period}:D{when}",when,qty)
            for when,qty in rows)
    window = IndustrialPlanningWindow(period,period,period+7,source_qty,4,"source.xlsx","I10")
    root = Requirement("external:root",period,source_qty)
    inputs = dict(requirements_by_pair={pair:(root,)},industrial_windows_by_pair={pair:(window,)},
        item_uoms={pair[1]:"UN"})
    results = []
    for own,ext,receipts,proposals,floor in (
        (old_own,old_external,old_receipts,old_proposals,old_floor),
        (new_own,new_external,new_receipts,new_proposals,new_floor)):
        needs = tuple(own)+external(ext)
        audit = dict(firm_receipts=tuple(receipts),protection_points=tuple(floor),
            industrial_requirement_reconciliation_policy="separate_own_and_other_v1",
            industrial_windows=(dict(period_start_day=period,first_day=period,end_day_exclusive=period+7,
                known_day=4,source_file="source.xlsx",source_cells="I10",source_qty=source_qty,
                complement_qty=sum(qty for _,qty in ext)),))
        results.append(({}, {pair:_manual_fixed_plan(needs,stock,receipts,proposals)}, {pair:needs}, {pair:audit}))
    return dict(before=results[0],after=results[1],pair=pair,day=10,network_inputs=inputs,
        raw_requirement_ids={"external:root"})


def test_external_union_uses_known_stock_once_without_generating_a_purchase():
    case = _external_case(old_own=(Requirement("cancelled_B",40,100),),new_external=((40,70),))
    allowed,evidence = assess_frozen_external_coverage(**case)
    assert allowed and evidence["fixed_supply_qty"] == 100
    assert evidence["retained_external_qty"] == 70 and evidence["new_external_qty"] == 70
    assert evidence["remaining_own_qty"] == 0 and not evidence["creates_proposals"]


@pytest.mark.parametrize("late",[False,True])
def test_external_increment_must_be_timely_even_when_original_twenty_was_late(late):
    receipt = FirmReceipt("late_firm",45,20,"confirmed")
    proposal = OrderProposal("fixed_proposal",10,40,40,20)
    case = _external_case(stock=240,old_own=(Requirement("own",30,100),Requirement("cancelled_B",30,100)),
        new_own=(Requirement("own",30,100),),old_external=((40,80),),new_external=((40,180),),
        old_receipts=(receipt,),new_receipts=(receipt,),old_proposals=(proposal,),
        new_proposals=(replace(proposal,available_day=45) if late else proposal,))
    allowed,evidence = assess_frozen_external_coverage(**case)
    assert allowed is (not late)
    assert evidence["fixed_supply_qty"] == 280
    if late:
        assert evidence["first_worsening"]["day"] == 40
        assert evidence["first_worsening"]["required_covered_qty"] == 160
        assert evidence["first_worsening"]["covered_qty"] == 140


def test_external_union_cannot_spend_own_material_or_create_missing_supply():
    case = _external_case(old_own=(Requirement("own",40,80),),new_own=(Requirement("own",40,80),),
        new_external=((40,70),),stock=100)
    allowed,evidence = assess_frozen_external_coverage(**case)
    assert not allowed and not evidence["creates_proposals"]
    assert evidence["first_worsening"]["obligation"] == "remaining_own"
    assert evidence["first_worsening"]["required_covered_qty"] == 80
    assert evidence["first_worsening"]["covered_qty"] == 30


def test_external_union_duplicate_receipt_never_counts_twice():
    receipt = FirmReceipt("same_receipt",20,100,"confirmed")
    case = _external_case(stock=0,new_external=((40,150),),new_receipts=(receipt,receipt))
    allowed,evidence = assess_frozen_external_coverage(**case)
    assert not allowed and evidence["reason"] == "external_forecast_provenance_or_fixed_supply_invalid"
    assert "more than once" in evidence["detail"]


def test_revised_forecast_does_not_accumulate_alternative_weekly_profiles():
    case = _external_case(stock=100,old_external=((40,20),(46,80)),
        new_external=((40,20),(44,40),(46,40)))
    allowed,evidence = assess_frozen_external_coverage(**case)
    assert allowed and evidence["retained_external_qty"] == 100
    assert evidence["new_external_qty"] == 40
    assert not evidence["creates_proposals"]


def test_external_union_rejects_a_new_floor_shortfall_even_if_candidate_already_has_it():
    case = _external_case(old_own=(Requirement("cancelled_B",40,100),),new_external=((40,70),),
        new_floor=(StockProtection("safety",40,40),))
    allowed,evidence = assess_frozen_external_coverage(**case)
    assert not allowed and evidence["reason"] == "fixed_supply_revised_protection_worsened"
    assert evidence["first_worsening"] == dict(day=40,target_qty=40,shortfall_qty=10,allowed_existing_shortfall_qty=0)


def test_unchanged_own_requirement_keeps_old_material_date_even_if_candidate_is_late():
    proposal = OrderProposal("existing_purchase",10,30,30,100)
    case = _external_case(stock=0,old_own=(Requirement("own_A",30,100),Requirement("cancelled_B",40,100)),
        new_own=(Requirement("own_A",30,100),),old_proposals=(proposal,),
        new_proposals=(replace(proposal,available_day=31),))
    allowed,evidence = assess_frozen_external_coverage(**case)
    assert not allowed and evidence["first_worsening"]["day"] == 30
    assert evidence["first_worsening"]["requirement_id"] == "own_A"
    assert evidence["first_worsening"]["required_covered_qty"] == 100


@pytest.mark.parametrize("available_day",[24,31])
def test_external_union_preserves_anticipation_without_double_physical_consumption(available_day):
    receipt = FirmReceipt("fixed",available_day,100,"confirmed")
    case = _external_case(stock=0,period=31,source_qty=100,
        old_own=(Requirement("cancelled_B",31,100),),new_external=((31,100),),
        old_receipts=(receipt,),new_receipts=(receipt,))
    pair = case["pair"]
    case["network_inputs"]["anticipated_need_by_pair"] = {pair:dict(
        source_working_days=5,origin_weekday=0,fixed_floor_qty=0,fixed_floor_mode="maximum")}
    for result in (case["before"],case["after"]):
        result[3][pair].update(anticipated_requirements=(Requirement("anticipated:24",24,100),),
            anticipated_plan=result[1][pair],anticipated_safety_working_days=5,
            anticipated_fixed_floor_qty=0,anticipated_fixed_floor_mode="maximum")
    allowed,evidence = assess_frozen_external_coverage(**case)
    assert allowed is (available_day == 24)
    assert evidence["fixed_supply_qty"] == evidence["retained_external_qty"] == 100
    if available_day == 31:
        assert evidence["reason"] == "fixed_supply_revised_anticipation_worsened"
        assert evidence["anticipation"]["first_worsening"]["day"] == 24


def test_external_union_rejects_new_anticipated_floor_deficit_already_present_in_candidate():
    proposal = OrderProposal("already_planned",10,10,10,100)
    case = _external_case(stock=0,period=31,source_qty=100,
        old_own=(Requirement("cancelled_B",31,100),),new_external=((31,100),),
        old_proposals=(proposal,),new_proposals=(replace(proposal,available_day=24),))
    pair = case["pair"]
    case["network_inputs"]["anticipated_need_by_pair"] = {pair:dict(
        source_working_days=5,origin_weekday=0,fixed_floor_qty=100,fixed_floor_mode="maximum")}
    for result in (case["before"],case["after"]):
        result[3][pair].update(anticipated_requirements=(Requirement("reserve:fixed_source:10",10,100),
                Requirement("reserve:fixed_source:31",31,100)),
            anticipated_plan=result[1][pair],anticipated_safety_working_days=5,
            anticipated_fixed_floor_qty=100,anticipated_fixed_floor_mode="maximum")
    allowed,evidence = assess_frozen_external_coverage(**case)
    assert not allowed and evidence["reason"] == "fixed_supply_revised_anticipation_worsened"
    failure = evidence["anticipation"]
    assert failure["reason"] == "candidate_anticipation_envelope_eroded"
    assert failure["day"] == 10 and failure["shortfall_qty"] == 100
    assert failure["original_shortfall_qty"] == failure["allowed_existing_shortfall_qty"] == 0
    assert failure["candidate_shortfall_qty"] == 100


@pytest.mark.parametrize("change",["window","unknown_id","lost_normalized_need"])
def test_external_union_never_invents_missing_source_provenance(change):
    case = _external_case(old_own=(Requirement("cancelled_B",40,100),),new_external=((40,70),))
    pair = case["pair"]
    if change == "window":
        case["after"][3][pair]["industrial_windows"][0]["source_file"] = "other.xlsx"
    elif change == "unknown_id":
        case["after"][2][pair] = (Requirement("external:unknown_alias",40,70),)
    else:
        case["after"][2][pair] = ()
    allowed,evidence = assess_frozen_external_coverage(**case)
    assert not allowed and evidence["reason"] == "external_forecast_provenance_or_fixed_supply_invalid"


@pytest.mark.parametrize("commitment",[False,True])
def test_only_a_traced_generated_forecast_can_shrink_from_hundred_to_sixty(commitment):
    case = _external_case(stock=100,source_qty=100,old_external=((40,100),),
        new_external=((40,60),),new_own=(Requirement("new_own",40,40),))
    pair = case["pair"]
    if commitment:
        for result in (case["before"],case["after"]):
            needs = tuple(replace(r,requirement_id="external:root") if r.requirement_id.startswith("external:") else r
                for r in result[2][pair])
            result[2][pair] = needs
            result[1][pair] = _manual_fixed_plan(needs,100)
    allowed,evidence = assess_frozen_external_coverage(**case)
    assert allowed is (not commitment)
    if commitment:
        assert evidence["reason"] == "external_forecast_provenance_or_fixed_supply_invalid"
    else:
        assert evidence["revised_forecast_qty"] == 60
        assert evidence["new_external_qty"] == 0 and evidence["remaining_own_qty"] == 40


def test_revised_forecast_new_quantity_due_day31_cannot_use_day32_supply():
    proposal = OrderProposal("existing_purchase",10,32,31,40)
    case = _external_case(period=31,source_qty=100,stock=60,
        old_own=(Requirement("cancelled_B",32,40),),old_external=((31,60),),
        new_external=((31,100),),old_proposals=(proposal,),new_proposals=(proposal,))
    allowed,evidence = assess_frozen_external_coverage(**case)
    assert not allowed and evidence["first_worsening"]["day"] == 31
    assert evidence["first_worsening"]["required_covered_qty"] == 100
    assert evidence["first_worsening"]["covered_qty"] == 60


def test_generated_residual_can_disappear_when_the_same_budget_is_now_an_own_need():
    case = _external_case(stock=100,source_qty=100,old_external=((40,100),),
        new_own=(Requirement("new_own",40,100),))
    allowed,evidence = assess_frozen_external_coverage(**case)
    assert allowed and evidence["revised_forecast_qty"] == 0
    assert evidence["remaining_own_qty"] == 100 and evidence["fixed_supply_qty"] == 100


def _declare_dynamic_floor(case):
    pair = case["pair"]
    context = dict(safety_days=7,fixed_qty=0,
        projection=dict(source_working_days=5,origin_weekday=0,forecast_through_day=100))
    case["network_inputs"]["source_safety_by_pair"] = {pair:context}
    for result in (case["before"],case["after"]):
        audit = result[3][pair]
        audit["chain_source_safety"] = dict(projection_policy="rolling_source_workdays_v1",
            forecast_through_day=100,prospective_safety_source_days=5,fixed_source_qty=0,window_days=7)
        audit["prospective_checkpoints"] = {}
        for point in audit["protection_points"]:
            end = point.day;count = 0
            while count < 5:
                end += 1;count += end%7 < 5
            qty = sum(r.qty for r in result[2][pair] if point.day < r.due_day <= end)
            audit["prospective_checkpoints"][point.day] = dict(safety_window_end_day=end,
                safety_window_need_qty=qty,safety_window_covered=1,safety_source_floor_qty=qty)
    return case


@pytest.mark.parametrize("dynamic",[False,True])
def test_cancelled_lot_dynamic_safety_can_fall_but_a_fixed_floor_cannot(dynamic):
    proposal = OrderProposal("former_supply",10,11,11,100)
    case = _external_case(period=14,source_qty=0,stock=0,
        old_own=(Requirement("cancelled_B",15,100),),old_proposals=(proposal,),
        old_floor=(StockProtection("old",11,100),StockProtection("end",15,0)),
        new_floor=(StockProtection("revised",11,0),))
    if dynamic:
        _declare_dynamic_floor(case)
    allowed,evidence = assess_frozen_external_coverage(**case)
    assert allowed is dynamic
    if not dynamic:
        assert evidence["reason"] == "fixed_supply_revised_protection_worsened"
        assert evidence["first_worsening"]["day"] == 11


def test_dynamic_safety_revision_never_removes_a_real_external_commitment():
    proposal = OrderProposal("former_supply",10,11,11,200)
    case = _external_case(period=14,source_qty=100,stock=0,
        old_own=(Requirement("cancelled_B",15,100),),old_external=((15,100),),new_external=((15,100),),
        old_proposals=(proposal,),
        old_floor=(StockProtection("old",11,200),StockProtection("end",15,0)),
        new_floor=(StockProtection("revised",11,100),StockProtection("end",15,0)))
    pair = case["pair"]
    root = Requirement("external:root",15,100)
    case["network_inputs"]["requirements_by_pair"][pair] = (root,)
    for result in (case["before"],case["after"]):
        needs = tuple(root if r.requirement_id.startswith("external:") else r for r in result[2][pair])
        result[2][pair] = needs
        result[1][pair] = _manual_fixed_plan(needs,0,proposals=result[1][pair].proposals)
    _declare_dynamic_floor(case)
    allowed,evidence = assess_frozen_external_coverage(**case)
    assert not allowed and evidence["first_worsening"]["requirement_id"] == "external:root"
    assert evidence["first_worsening"]["required_covered_qty"] == 100


@pytest.mark.parametrize("change",["days","fixed","false_checkpoint"])
def test_dynamic_safety_requires_unchanged_parameters_and_true_dated_provenance(change):
    proposal = OrderProposal("former_supply",10,11,11,100)
    case = _declare_dynamic_floor(_external_case(period=14,source_qty=0,stock=0,
        old_own=(Requirement("cancelled_B",15,100),),old_proposals=(proposal,),
        old_floor=(StockProtection("old",11,100),StockProtection("end",15,0)),
        new_floor=(StockProtection("revised",11,0),)))
    pair = case["pair"];audit = case["after"][3][pair]
    if change == "days":
        audit["chain_source_safety"]["prospective_safety_source_days"] = 4
    elif change == "fixed":
        audit["chain_source_safety"]["fixed_source_qty"] = 1
    else:
        audit["prospective_checkpoints"][11]["safety_window_need_qty"] = 100
    allowed,evidence = assess_frozen_external_coverage(**case)
    assert not allowed and evidence["reason"] == "external_forecast_provenance_or_fixed_supply_invalid"


def test_dynamic_safety_does_not_reduce_protection_beyond_a_known_source_window():
    proposal = OrderProposal("former_supply",10,11,11,100)
    case = _declare_dynamic_floor(_external_case(period=14,source_qty=0,stock=0,
        old_own=(Requirement("cancelled_B",15,100),),old_proposals=(proposal,),
        old_floor=(StockProtection("old",11,100),StockProtection("end",15,0)),
        new_floor=(StockProtection("revised",11,0),)))
    audit = case["after"][3][case["pair"]]
    audit["prospective_checkpoints"][11]["safety_window_covered"] = 0
    allowed,evidence = assess_frozen_external_coverage(**case)
    assert not allowed and evidence["reason"] == "fixed_supply_revised_protection_worsened"
    assert evidence["first_worsening"]["target_qty"] == 100


def _rounded_dynamic_case(shortfall=499):
    """Gram pool: physical A stays covered; only its early buffer is short."""
    stock = 1000-shortfall
    old_purchase = OrderProposal("old_purchase",10,11,11,2000)
    new_purchase = OrderProposal("new_purchase",10,15,15,1000)
    case = _declare_dynamic_floor(_external_case(period=14,source_qty=0,stock=stock,
        old_own=(Requirement("own_A",15,1000),Requirement("cancelled_B",15,1000)),
        new_own=(Requirement("own_A",15,1000),),
        old_proposals=(old_purchase,),new_proposals=(new_purchase,),
        old_floor=(StockProtection("old",11,2000),StockProtection("end",15,0)),
        new_floor=(StockProtection("revised",11,1000),StockProtection("end",15,0))))
    pair = case["pair"]
    case["network_inputs"]["item_uoms"][pair[1]] = "G"
    case["network_inputs"]["lot_sizing_by_pair"] = {pair:LotSizing(net_rounding_quantum=1000)}
    for result in (case["before"],case["after"]):
        result[1][pair] = replace(result[1][pair],net_rounding_quantum=1000)
    return case


@pytest.mark.parametrize("shortfall,accepted",[(499,True),(500,False),(501,False)])
def test_dynamic_safety_rounding_uses_strict_half_quantum_and_keeps_real_residual(shortfall,accepted):
    case = _rounded_dynamic_case(shortfall)
    allowed,evidence = assess_frozen_external_coverage(**case)
    assert allowed is accepted
    if accepted:
        assert evidence["dynamic_safety_rounding_residuals"] == [dict(day=11,target_qty=1000,
            projected_qty=501,shortfall_qty=499,allowed_existing_shortfall_qty=0,
            quantum_qty=1000,strict_half_quantum_limit_qty=500,fixed_source_qty=0,
            uom="G",policy="nearest_kg_half_up_v1")]
        assert case["after"][1][case["pair"]].balances[1].after_proposals_qty == 501
    else:
        assert evidence["reason"] == "fixed_supply_revised_protection_worsened"
        assert evidence["first_worsening"]["shortfall_qty"] == shortfall
        assert evidence["dynamic_safety_rounding_residuals"] == []


def test_dynamic_safety_rounding_uses_one_kilogram_in_canonical_kg_units():
    case = _rounded_dynamic_case(shortfall=.499)
    pair = case["pair"]
    case["network_inputs"]["item_uoms"][pair[1]] = "KG"
    case["network_inputs"]["lot_sizing_by_pair"][pair] = LotSizing(net_rounding_quantum=1)
    for result in (case["before"],case["after"]):
        result[1][pair] = replace(result[1][pair],net_rounding_quantum=1)
    allowed,evidence = assess_frozen_external_coverage(**case)
    assert allowed
    residual = evidence["dynamic_safety_rounding_residuals"][0]
    assert residual["shortfall_qty"] == .499
    assert residual["quantum_qty"] == 1 and residual["strict_half_quantum_limit_qty"] == .5
    assert residual["uom"] == "KG"


@pytest.mark.parametrize("change",["zero","input_mismatch","plan_mismatch","unsupported_quantum","UN"])
def test_dynamic_safety_rounding_requires_the_same_explicit_mass_policy(change):
    case = _rounded_dynamic_case()
    pair = case["pair"];inputs = case["network_inputs"]
    if change == "zero":
        inputs["lot_sizing_by_pair"][pair] = LotSizing()
        for result in (case["before"],case["after"]):
            result[1][pair] = replace(result[1][pair],net_rounding_quantum=0)
    elif change == "input_mismatch":
        inputs["lot_sizing_by_pair"][pair] = LotSizing(net_rounding_quantum=1)
    elif change == "plan_mismatch":
        case["after"][1][pair] = replace(case["after"][1][pair],net_rounding_quantum=1)
    elif change == "unsupported_quantum":
        inputs["lot_sizing_by_pair"][pair] = LotSizing(net_rounding_quantum=2000)
        for result in (case["before"],case["after"]):
            result[1][pair] = replace(result[1][pair],net_rounding_quantum=2000)
    else:
        inputs["item_uoms"][pair[1]] = "UN"
        inputs["lot_sizing_by_pair"][pair] = LotSizing(integer=True,net_rounding_quantum=1000)
    allowed,evidence = assess_frozen_external_coverage(**case)
    assert not allowed and evidence["reason"] == "fixed_supply_revised_protection_worsened"
    assert evidence["dynamic_safety_rounding_residuals"] == []


@pytest.mark.parametrize("kind",["fixed_only","fixed_inside_dynamic"])
def test_mass_rounding_never_relaxes_a_fixed_stock_floor(kind):
    case = _rounded_dynamic_case()
    pair = case["pair"]
    if kind == "fixed_only":
        del case["network_inputs"]["source_safety_by_pair"]
    else:
        case["network_inputs"]["source_safety_by_pair"][pair]["fixed_qty"] = 600
        for result in (case["before"],case["after"]):
            audit = result[3][pair]
            audit["chain_source_safety"]["fixed_source_qty"] = 600
            audit["protection_points"] = tuple(replace(p,minimum_qty=max(600,p.minimum_qty))
                for p in audit["protection_points"])
            for point in audit["protection_points"]:
                audit["prospective_checkpoints"][point.day]["safety_source_floor_qty"] = point.minimum_qty
    allowed,evidence = assess_frozen_external_coverage(**case)
    assert not allowed and evidence["reason"] == "fixed_supply_revised_protection_worsened"
    assert evidence["dynamic_safety_rounding_residuals"] == []


def test_mass_rounding_never_justifies_a_real_material_shortage_or_negative_balance():
    case = _rounded_dynamic_case(shortfall=49)
    pair = case["pair"];result = case["after"]
    late = replace(result[1][pair].proposals[0],available_day=16)
    result[1][pair] = replace(_manual_fixed_plan(result[2][pair],951,proposals=(late,)),net_rounding_quantum=1000)
    allowed,evidence = assess_frozen_external_coverage(**case)
    assert not allowed and evidence["reason"] == "fixed_supply_external_or_own_coverage_worsened"
    assert evidence["first_worsening"]["requirement_id"] == "own_A"
    assert evidence["first_worsening"]["day"] == 15 and evidence["first_worsening"]["shortfall_qty"] == 49
    assert next(b.after_proposals_qty for b in result[1][pair].balances if b.day==15) == -49


def test_mass_rounding_never_adds_half_a_quantum_to_an_existing_deficit():
    case = _rounded_dynamic_case(shortfall=600)
    pair = case["pair"];result = case["before"]
    smaller = replace(result[1][pair].proposals[0],qty=1200)
    result[1][pair] = replace(_manual_fixed_plan(result[2][pair],400,proposals=(smaller,)),net_rounding_quantum=1000)
    allowed,evidence = assess_frozen_external_coverage(**case)
    assert not allowed and evidence["reason"] == "fixed_supply_revised_protection_worsened"
    assert evidence["first_worsening"]["allowed_existing_shortfall_qty"] == 400
    assert evidence["first_worsening"]["shortfall_qty"] == 600


def _tail_fallback_case():
    """Current window ]10,17] is known; at14 the rolling window ends21>20."""
    case = _declare_dynamic_floor(_external_case(period=14,source_qty=0,stock=0,
        old_own=(Requirement("own_A",15,100),Requirement("cancelled_B",15,100)),
        new_own=(Requirement("own_A",15,100),),
        old_proposals=(OrderProposal("old_purchase",10,11,11,400),),
        new_proposals=(OrderProposal("new_purchase",10,11,11,200),),
        old_floor=(StockProtection("known",11,200),StockProtection("fallback",14,200)),
        new_floor=(StockProtection("known",11,100),StockProtection("fallback",14,100))))
    pair = case["pair"]
    case["network_inputs"]["source_safety_by_pair"][pair]["projection"]["forecast_through_day"] = 20
    for result,amount in ((case["before"],200),(case["after"],100)):
        audit = result[3][pair]
        audit["chain_source_safety"].update(forecast_through_day=20,dated_requirement_qty=amount,
            historical_constant_target_qty=amount,prospective_safety_legacy_qty=amount,
            basis="future_dated_requirements_once_no_overdue_backlog_no_lot_as_daily_rate")
        audit["prospective_safety_legacy_qty"] = amount
        audit["prospective_checkpoints"][14].update(safety_window_covered=0,safety_window_need_qty="")
    return case


def test_native_tail_fallback_is_recomputed_from_the_current_known_source_window():
    case = _tail_fallback_case()
    allowed,evidence = assess_frozen_external_coverage(**case)
    assert allowed and evidence["native_source_safety_fallback_qty"] == {"before":200,"after":100}
    plan = case["after"][1][case["pair"]]
    assert plan.closing_projected_qty == 100 and plan.opening_available_qty == 0
    assert plan.proposed_qty == 200 and not evidence["creates_proposals"]


def test_recomputed_tail_fallback_keeps_a_true_fixed_source_floor():
    case = _tail_fallback_case();pair = case["pair"]
    case["network_inputs"]["source_safety_by_pair"][pair]["fixed_qty"] = 150
    for result in (case["before"],case["after"]):
        audit = result[3][pair];legacy = max(150,audit["prospective_safety_legacy_qty"])
        audit["chain_source_safety"].update(fixed_source_qty=150,
            historical_constant_target_qty=legacy,prospective_safety_legacy_qty=legacy)
        audit["prospective_safety_legacy_qty"] = legacy
        audit["protection_points"] = tuple(replace(p,minimum_qty=max(150,p.minimum_qty))
            for p in audit["protection_points"])
        for p in audit["protection_points"]:
            audit["prospective_checkpoints"][p.day]["safety_source_floor_qty"] = p.minimum_qty
    allowed,evidence = assess_frozen_external_coverage(**case)
    assert not allowed and evidence["reason"] == "fixed_supply_revised_protection_worsened"
    assert evidence["first_worsening"]["day"] == 15
    assert evidence["first_worsening"]["target_qty"] == 150
    assert evidence["first_worsening"]["shortfall_qty"] == 50


@pytest.mark.parametrize("change",["missing","dated_sum","historical_target","top_level",
    "checkpoint","current_window_unknown","false_incomplete_window"])
def test_tail_fallback_requires_a_complete_true_dated_source_proof(change):
    case = _tail_fallback_case();pair = case["pair"];audit = case["after"][3][pair]
    if change == "missing":
        del audit["chain_source_safety"]["historical_constant_target_qty"]
    elif change == "dated_sum":
        audit["chain_source_safety"]["dated_requirement_qty"] = 101
    elif change == "historical_target":
        audit["chain_source_safety"]["historical_constant_target_qty"] = 101
    elif change == "top_level":
        audit["prospective_safety_legacy_qty"] = 101
    elif change == "checkpoint":
        audit["prospective_checkpoints"][14]["safety_source_floor_qty"] = 101
    elif change == "current_window_unknown":
        case["network_inputs"]["source_safety_by_pair"][pair]["projection"]["forecast_through_day"] = 16
        for result in (case["before"],case["after"]):
            result[3][pair]["chain_source_safety"]["forecast_through_day"] = 16
    else:
        audit["prospective_checkpoints"][11].update(safety_window_covered=0,safety_window_need_qty="")
    allowed,evidence = assess_frozen_external_coverage(**case)
    assert not allowed
    assert evidence["reason"] == ("fixed_supply_revised_protection_worsened" if change=="missing"
        else "external_forecast_provenance_or_fixed_supply_invalid")


def test_recomputed_tail_fallback_never_authorizes_late_real_external_demand():
    case = _tail_fallback_case();pair = case["pair"]
    root = Requirement("external:root",15,100)
    case["network_inputs"]["requirements_by_pair"][pair] = (root,)
    source = case["network_inputs"]["industrial_windows_by_pair"][pair][0]
    case["network_inputs"]["industrial_windows_by_pair"][pair] = (replace(source,qty=100),)
    for result in (case["before"],case["after"]):
        needs = tuple(root if r.requirement_id=="own_A" else r for r in result[2][pair])
        proposals = result[1][pair].proposals
        if result is case["after"]:
            proposals = tuple(replace(p,available_day=16) for p in proposals)
        result[2][pair] = needs
        result[1][pair] = _manual_fixed_plan(needs,0,proposals=proposals)
        result[3][pair]["industrial_windows"][0].update(source_qty=100,complement_qty=100)
    allowed,evidence = assess_frozen_external_coverage(**case)
    assert not allowed and evidence["reason"] == "fixed_supply_external_or_own_coverage_worsened"
    assert evidence["first_worsening"]["requirement_id"] == "external:root"
    assert evidence["first_worsening"]["day"] == 15 and evidence["first_worsening"]["shortfall_qty"] == 100
