"""Independent memory-only oracles for batch-scoped component issues.

Expected component debits below are literal physical quantities, not values
recomputed through the issue helper as their own oracle. No fixture writes,
engine run, source workbook, clock change or synthetic file is used.
"""
from copy import deepcopy
import math

import pytest

from etudecas.simulation.engine.production_component_issues import (
    incremental_component_issue, cumulative_work_bound, feasible_cumulative_work,
)
from etudecas.simulation.lot_trace.campaigns import ProductionBatchWip


def test_packaging_two_fractional_passes_debit485_then7215_not7701():
    first=incremental_component_issue(0,484.8,1,"UN",0)
    second=incremental_component_issue(484.8,7215.2,1,"UN",first)
    assert first == 485 and second == 7215
    assert first+second == 7700
    assert 484.8+7215.2 == 7700


def test_source_ratio_shortage_keeps_work_continuous_and_packaging_total_exact():
    #Source BOM:60342 countable components per1000PF; first available29254.
    first=feasible_cumulative_work(7700,0,[(29254,60.342,"UN",0),(200000,1,"UN",0)])
    assert first == pytest.approx(484.8032879254914,rel=0,abs=1e-10)
    assert incremental_component_issue(0,first,60.342,"UN",0) == 29254
    assert incremental_component_issue(0,first,1,"UN",0) == 485
    last=feasible_cumulative_work(7700-first,first,
        [(435380,60.342,"UN",29254),(7215,1,"UN",485)])
    assert first+last == pytest.approx(7700,rel=0,abs=1e-10)
    assert incremental_component_issue(first,last,1,"UN",485) == 7215
    assert incremental_component_issue(first,last,60.342,"UN",29254) == 435380


def test_small_integer_component_ratio_debits2_then1_for_two_hundred_units():
    assert incremental_component_issue(0,100,.011,"UN",0) == 2
    assert incremental_component_issue(100,100,.011,"UN",2) == 1
    #Both methods finish200PF, but independent operation ceilings would debit4.
    assert math.ceil(200*.011) == 3
    assert math.ceil(100*.011)+math.ceil(100*.011) == 4


def test_existing_component_credit_allows_work_without_new_stock_or_issue():
    assert cumulative_work_bound(executed_before=.8,available=0,ratio=1,uom="UN",issued_before=1) == pytest.approx(.2)
    work=feasible_cumulative_work(.5,.8,[(0,1,"UN",1)])
    assert 0 < work <= .2
    assert .8+work == 1
    assert incremental_component_issue(.8,work,1,"UN",1) == 0


def test_previously_issued_component_credit_never_increases_real_machine_capacity():
    work=feasible_cumulative_work(7215.2,484.8,[(7216,1,"UN",485)])
    assert work == 7215.2  #Not7216, even though the remaining stock is integer.
    assert incremental_component_issue(484.8,work,1,"UN",485) == 7215


def test_packaging_stock484_bounds_first_work_despite_other_material_allowing_more():
    work=feasible_cumulative_work(7700,0,[(29254,60.342,"UN",0),(484,1,"UN",0)])
    assert work == 484
    assert incremental_component_issue(0,work,1,"UN",0) == 484
    assert incremental_component_issue(0,work,60.342,"UN",0) == 29206


def test_credit_from_one_batch_is_unavailable_to_the_next_batch():
    assert incremental_component_issue(.8,.2,1,"UN",1) == 0
    #The caller resets both progress and physically issued counters on batch2.
    assert incremental_component_issue(0,.2,1,"UN",0) == 1
    assert feasible_cumulative_work(.2,0,[(0,1,"UN",0)]) == 0


def test_same_lot_residual_is_reused_across_more_than_two_passes():
    assert incremental_component_issue(0,.1,1,"UN",0) == 1
    assert incremental_component_issue(.1,.6,1,"UN",1) == 0
    assert incremental_component_issue(.7,.3,1,"UN",1) == 0
    assert incremental_component_issue(1,.1,1,"UN",1) == 1


def test_native_wip_keeps_integer_genealogy_and_same_batch_component_credit():
    batch = ProductionBatchWip("campaign", "batch1", "factory", "PF", 0, 0, 7700)
    stock = 7700
    for requested in (484.8, 7215.2):
        issued = batch.issued_by_component.get("required_pack", 0)
        work = feasible_cumulative_work(requested, batch.executed_qty, [(stock, 1, "UN", issued)])
        debit = incremental_component_issue(batch.executed_qty, work, 1, "UN", issued)
        stock -= debit
        batch.issued_by_component["required_pack"] = issued + debit
        batch.add_execution(work, [{"item_id": "physical_substitute", "qty": debit}])
    assert batch.is_complete and batch.target_qty == 7700 and batch.executed_qty == 7700
    assert stock == 0 and batch.issued_by_component == {"required_pack": 7700}
    assert [row["qty"] for row in batch.parent_allocations] == [485, 7215]
    assert all(row["item_id"] == "physical_substitute" for row in batch.parent_allocations)
    # A later physical batch of the same campaign never inherits the credit.
    next_batch = ProductionBatchWip("campaign", "batch2", "factory", "PF", 0, 2, 7700)
    assert next_batch.issued_by_component == {} and next_batch.executed_qty == 0


def test_existing_wip_positional_allocations_remain_compatible():
    parents = [{"item_id": "old_pack", "qty": 5}]
    batch = ProductionBatchWip("c", "b", "f", "p", 0, 0, 10, 4.8, parents)
    assert batch.parent_allocations is parents and batch.executed_qty == 4.8
    assert batch.issued_by_component == {}


@pytest.mark.parametrize("uom", ["KG","G","M"])
def test_continuous_components_retain_exact_per_operation_multiplication(uom):
    work=.123456789
    ratio=.01987654321
    assert incremental_component_issue(500.4,work,ratio,uom,9.7) == work*ratio
    assert cumulative_work_bound(executed_before=500.4,available=.7,ratio=ratio,
                                 uom=uom,issued_before=9.7) == .7/ratio
    #Previously consumed mass/length does not turn into a countable-item credit.
    assert feasible_cumulative_work(.2,.8,[(0,1,uom,1)]) == 0


def test_mixed_components_keep_all_constraints_and_the_input_list_unchanged():
    limits=[(2,1,"UN",1),(.125,.5,"KG",.4),(20,3,"M",7)]
    before=deepcopy(limits)
    work=feasible_cumulative_work(10,.8,limits)
    assert work == .25
    assert incremental_component_issue(.8,work,1,"UN",1) == 1
    assert incremental_component_issue(.8,work,.5,"KG",.4) == .125
    assert limits == before


def test_binary_boundary_never_consumes_fourteen_when_only_thirteen_exist():
    raw=13/.011
    assert math.ceil(raw*.011) == 14  #The actual binary edge, independently.
    work=feasible_cumulative_work(raw,0,[(13,.011,"UN",0)])
    assert 0 < work < raw and raw-work < 1e-9
    assert math.ceil(work*.011) == 13
    assert incremental_component_issue(0,work,.011,"UN",0) == 13


@pytest.mark.parametrize("uom", ["UN","KG","G","M"])
def test_zero_work_never_creates_a_component_issue(uom):
    assert incremental_component_issue(100,0,.011,uom,0) == 0
    assert feasible_cumulative_work(0,100,[(0,.011,uom,0)]) == 0


def test_no_component_constraint_does_not_round_continuous_work_or_capacity():
    assert feasible_cumulative_work(.012345678,1234.5,[]) == .012345678


@pytest.mark.parametrize("field", ["executed_before","additional_work","ratio","issued_before"])
@pytest.mark.parametrize("invalid", [None,True,-1,math.nan,math.inf])
def test_incremental_issue_rejects_missing_negative_or_nonfinite_inputs(field,invalid):
    args=dict(executed_before=0,additional_work=1,ratio=1,uom="UN",issued_before=0)
    args[field]=invalid
    with pytest.raises(ValueError):
        incremental_component_issue(**args)


@pytest.mark.parametrize("invalid", [None,True,-1,math.nan,math.inf,.5])
def test_bound_rejects_nonphysical_available_integer_stock(invalid):
    with pytest.raises(ValueError):
        cumulative_work_bound(executed_before=0,available=invalid,ratio=1,uom="UN",issued_before=0)


@pytest.mark.parametrize("invalid", [None,True,-1,math.nan,math.inf,.5])
def test_cumulative_feasibility_rejects_invalid_issued_countable_component(invalid):
    with pytest.raises(ValueError):
        feasible_cumulative_work(100,0,[(100,1,"UN",invalid)])


@pytest.mark.parametrize("uom", [None,"","unknown"])
def test_unknown_units_cannot_silently_use_continuous_quantity_rules(uom):
    with pytest.raises(ValueError):
        incremental_component_issue(0,1,1,uom,0)
    with pytest.raises(ValueError):
        cumulative_work_bound(executed_before=0,available=1,ratio=1,uom=uom,issued_before=0)


def test_zero_ratio_is_not_a_valid_modelled_component():
    with pytest.raises(ValueError):
        incremental_component_issue(0,1,0,"UN",0)
    with pytest.raises(ValueError):
        feasible_cumulative_work(1,0,[(1,0,"UN",0)])


@pytest.mark.parametrize("limits", [None,[(1,1,"UN")],[(1,1,"UN",0,2)],[None]])
def test_feasibility_rejects_malformed_limits_even_if_work_is_zero(limits):
    with pytest.raises(ValueError):
        feasible_cumulative_work(0,0,limits)
