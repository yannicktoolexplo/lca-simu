"""Memory-only oracles; no fake files, source edits or simulator runs."""
import ast
from copy import deepcopy
from decimal import Decimal, ROUND_CEILING
from pathlib import Path
import math

import pytest

from etudecas.simulation.engine.active_batch_materials import (
    ActiveBatchMaterialClaim, allocate_active_batch_materials, claims_for_engaged_batches,
    serve_with_active_batch_protection,
)
from etudecas.simulation.engine.mrp_planning import Requirement, serve_external_component_requirements
from etudecas.simulation.lot_trace.campaigns import ProductionBatchWip


def batch(identity, *, executed=100100, target=107800, item="PF"):
    result=ProductionBatchWip(identity,identity+"-B1","M",item,118,118,target,executed)
    result.issued_by_component={"X":6040235}
    return result


def test_j130_decimal_oracle_protects464633_without_deleting_external_need():
    active=batch("A")
    claims=claims_for_engaged_batches({("M","PF"):active},bom_by_pair={("M","PF"):[(("M","X"),60.342)]},
        modeled_pairs={("M","X")},item_uoms={"X":"UN"},substitutes_by_pair={})
    expected=int((Decimal(107800)*Decimal("60.342")).to_integral_value(rounding=ROUND_CEILING))-6040235
    assert expected==464633 and claims[0].remaining_qty==expected
    protection,_=allocate_active_batch_materials(claims,available_by_pair={("M","X"):3281699},item_uoms={"X":"UN"})
    service,physical=serve_with_active_batch_protection(decision_day=130,available_qty=3281699,
        protected_qty=protection["M","X"],backlog=(),due=(Requirement("residual",130,3372566),),uom="UN")
    assert service.consumed_qty==2817066 and physical==464633
    assert service.remaining==(Requirement("residual",130,555500),)
    assert service.consumed_qty+physical==3281699
    assert service.consumed_qty+service.remaining[0].qty==3372566


def test_not_started_and_completed_batches_have_no_material_claim():
    for executed in (0,107800):
        assert claims_for_engaged_batches({("M","PF"):batch("A",executed=executed)},
            bom_by_pair={("M","PF"):[(("M","X"),60.342)]},modeled_pairs={("M","X")},
            item_uoms={"X":"UN"},substitutes_by_pair={})==()


def test_multi_batch_shared_pool_never_reserves_same_stock_twice():
    claims=[ActiveBatchMaterialClaim("older","M","X",80,"UN",1),ActiveBatchMaterialClaim("newer","M","X",80,"UN",2)]
    stock={("M","X"):100};original=deepcopy(stock)
    protection,audit=allocate_active_batch_materials(reversed(claims),available_by_pair=stock,item_uoms={"X":"UN"})
    assert stock==original and protection=={("M","X"):100}
    assert sum(r["protected_qty"] for r in audit)==100
    assert sum(r["uncovered_qty"] for r in audit)==60
    assert [r["protected_qty"] for r in audit if r["batch_id"]=="older"]==[80]


def test_substitute_and_direct_claim_share_one_physical_pool():
    claims=[ActiveBatchMaterialClaim("A","M","NEW",6,"UN",1,(("OLD","use_old_until_new_stock_available"),)),
            ActiveBatchMaterialClaim("B","M","OLD",8,"UN",2)]
    protection,audit=allocate_active_batch_materials(claims,available_by_pair={("M","NEW"):0,("M","OLD"):8},
        item_uoms={"NEW":"UN","OLD":"UN"})
    assert protection=={("M","OLD"):8}
    assert sum(r["uncovered_qty"] for r in audit)==6
    assert next(r for r in audit if r["batch_id"]=="A")["allocation_kind"]=="authorized_substitute"


def test_old_until_new_policy_does_not_cover_shortage_when_new_stock_present():
    claim=ActiveBatchMaterialClaim("A","M","NEW",9,"UN",1,(("OLD","use_old_until_new_stock_available"),))
    protection,audit=allocate_active_batch_materials([claim],available_by_pair={("M","NEW"):4,("M","OLD"):20},
        item_uoms={"NEW":"UN","OLD":"UN"})
    assert protection=={("M","NEW"):4}
    assert sum(r["uncovered_qty"] for r in audit)==5


def test_other_batch_reservation_does_not_activate_old_reference_substitution():
    claims=[ActiveBatchMaterialClaim("A","M","NEW",4,"UN",1),
        ActiveBatchMaterialClaim("B","M","NEW",9,"UN",2,(("OLD","use_old_until_new_stock_available"),))]
    protection,audit=allocate_active_batch_materials(claims,available_by_pair={("M","NEW"):4,("M","OLD"):20},
        item_uoms={"NEW":"UN","OLD":"UN"})
    assert protection=={("M","NEW"):4}
    assert sum(r["uncovered_qty"] for r in audit if r['batch_id']=='B')==9


def test_backlog_identity_survives_next_week_and_batch_completion_releases_stock():
    first,physical=serve_with_active_batch_protection(decision_day=6,available_qty=10,protected_qty=6,
        backlog=(),due=(Requirement("week0",6,7),),uom="UN")
    assert physical==6 and first.remaining==(Requirement("week0",6,3),)
    # Completion physically consumes its six protected units; they must not
    # become free stock merely because the claim disappears. A separate known
    # receipt of six units funds service at the next weekly closure.
    physical_after_core=physical-6
    assert physical_after_core==0
    second,physical2=serve_with_active_batch_protection(decision_day=13,available_qty=physical_after_core+6,
        protected_qty=0,backlog=first.remaining,due=(Requirement("week1",13,5),),uom="UN")
    assert second.allocations==(Requirement("week0",6,3),Requirement("week1",13,3))
    assert second.remaining==(Requirement("week1",13,2),) and physical2==0
    assert first.consumed_qty+second.consumed_qty+2==7+5


def test_continuous_mass_protection_preserves_fractional_quantity():
    claim=ActiveBatchMaterialClaim("A","M","KG",1.25,"KG",1)
    protection,_=allocate_active_batch_materials([claim],available_by_pair={("M","KG"):2.5},item_uoms={"KG":"KG"})
    service,physical=serve_with_active_batch_protection(decision_day=1,available_qty=2.5,protected_qty=protection["M","KG"],
        backlog=(),due=(Requirement("mass",1,2.5),),uom="KG")
    assert service.consumed_qty==1.25 and physical==1.25


def test_decimal_mass_allocations_do_not_erode_protected_stock():
    service,physical=serve_with_active_batch_protection(decision_day=1,available_qty=.4,protected_qty=.1,
        backlog=(),due=(Requirement("a",1,.1),Requirement("b",1,.2)),uom="KG")
    assert service.consumed_qty==.3 and physical==.1 and service.available_end_qty==0
    assert service.remaining==()
    assert sum((Decimal(str(r.qty)) for r in service.allocations),Decimal(0))+Decimal(str(physical))==Decimal('.4')


def test_duplicate_claim_or_substitute_is_rejected_before_allocation():
    claim=ActiveBatchMaterialClaim("A","M","X",2,"UN",1)
    with pytest.raises(ValueError,match="Duplicate"):
        allocate_active_batch_materials([claim,claim],available_by_pair={("M","X"):10},item_uoms={"X":"UN"})
    duplicate=ActiveBatchMaterialClaim("A","M","X",2,"UN",1,(("Y","allowed"),("Y","allowed")))
    with pytest.raises(ValueError,match="Duplicate"):
        allocate_active_batch_materials([duplicate],available_by_pair={("M","X"):10},item_uoms={"X":"UN","Y":"UN"})


@pytest.mark.parametrize("invalid",[-1,float("nan"),float("inf"),True,1.5])
def test_invalid_physical_unit_protection_is_rejected(invalid):
    with pytest.raises(ValueError):
        serve_with_active_batch_protection(decision_day=1,available_qty=10,protected_qty=invalid,backlog=(),due=(),uom="UN")


@pytest.mark.parametrize("enabled,expected_debit,expected_stock,expected_wait",[(False,7,3,0),(True,4,6,3)])
def test_real_engine_external_service_branch_preserves_stock_and_default(enabled,expected_debit,expected_stock,expected_wait):
    # Execute the actual branch and actual stock assignment in memory, not a
    # copied implementation. Reading engine source does not modify any file.
    path=Path(__file__).resolve().parents[2]/"simulation/engine/run_first_simulation.py"
    tree=ast.parse(path.read_text(encoding="utf-8"))
    branches=[n for n in ast.walk(tree) if isinstance(n,ast.If) and isinstance(n.test,ast.Name)
        and n.test.id=="active_batch_material_protection" and any(isinstance(a,ast.Assign)
        and any(isinstance(t,ast.Name) and t.id=="protected_qty" for t in a.targets) for a in n.body)]
    assignments=[n for n in ast.walk(tree) if isinstance(n,ast.Assign) and isinstance(n.value,ast.Name)
        and n.value.id=="physical_stock_after" and any(isinstance(t,ast.Subscript)
        and isinstance(t.value,ast.Name) and t.value.id=="stock" for t in n.targets)]
    assert len(branches)==len(assignments)==1
    scope=dict(active_batch_material_protection=enabled,protected_materials={("M","X"):6},
        component_pair=("M","X"),component_uom="UN",available_before=10,output_day=1,
        external_component_backlogs={},external_due={("M","X"):(Requirement("demand",1,7),)},
        record_day=False,stock={("M","X"):10},math=math,
        serve_with_active_batch_protection=serve_with_active_batch_protection,
        serve_external_component_requirements=serve_external_component_requirements)
    exec(compile(ast.fix_missing_locations(ast.Module(body=[branches[0],assignments[0]],type_ignores=[])),str(path),"exec"),scope)
    assert scope["external_service"].consumed_qty==expected_debit
    assert scope["stock"]["M","X"]==expected_stock
    assert sum(r.qty for r in scope["external_service"].remaining)==expected_wait
