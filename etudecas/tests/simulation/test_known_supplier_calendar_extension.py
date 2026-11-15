"""Memory-only offer calendar extension; shares, prices and lots are immutable."""
from copy import deepcopy
import pytest
from etudecas.simulation.engine import run_first_simulation as engine
from etudecas.simulation.engine.mrp_planning import LotSizing, Requirement, SupplierOffer


def offer(identity, lead, price):
    return SupplierOffer(identity, price, "EUR", "UN", lead, LotSizing(integer=True),
        tuple((d,d+lead) for d in range(6)))


def context(lead):
    return dict(calendar_kind="supplier_receipt", physical_lead_days=lead,
        receipt_days=0, origin_date="2025-01-01")


@pytest.mark.parametrize("allocated", [True,False])
def test_known_supplier_offer_extension_keeps_shares_prices_lots_and_input(allocated):
    first, second = offer("A",10,2), offer("B",20,3)
    source = (dict(offers=(first,second), allocation_weights=(.25,.75)) if allocated else
        dict(primary=first, backups=(second,), protected_backup_receipt_ids=("firm",)))
    before = deepcopy(source)
    updated, audit = engine.extend_known_supplier_offers(source,decision_day=0,through_day=31,
        contexts={"A":context(10),"B":context(20)})
    offers = updated["offers"] if allocated else (updated["primary"],*updated["backups"])
    assert [o.availability_by_release[-1] for o in offers] == [(31,41),(31,51)]
    assert [(o.supplier_id,o.purchase_unit_cost,o.lot_sizing,o.lead_days) for o in offers] == [
        (o.supplier_id,o.purchase_unit_cost,o.lot_sizing,o.lead_days) for o in (first,second)]
    assert all(o.availability_by_release[:6] == original.availability_by_release for o,original in zip(offers,(first,second)))
    assert len(audit)==2 and source==before
    key="allocation_weights" if allocated else "protected_backup_receipt_ids"
    assert updated[key]==source[key]


def test_known_supplier_offer_extension_does_not_infer_missing_supplier_rules():
    source=dict(offers=(offer("A",10,2),offer("unknown",20,3)),allocation_weights=(.5,.5))
    updated,audit=engine.extend_known_supplier_offers(source,decision_day=0,through_day=31,contexts={"A":context(10)})
    assert len(audit)==1 and updated["offers"][1] is source["offers"][1]


def test_network_allocated_supplier_calendars_cover_propagated_need_without_changing_shares():
    pair=("F","C");offers=(offer("A",10,2),offer("B",20,3))
    args=dict(decision_day=0,requirements_by_pair={pair:[Requirement("need",30,100)]},available_by_pair={},
        firm_receipts_by_pair={},transport_sources_by_pair={},bom_by_pair={},lead_days_by_pair={pair:10},
        lot_sizing_by_pair={pair:LotSizing(integer=True)},reserve_targets_by_pair={},coverage_days_by_pair={},
        active_campaigns_by_pair={},anticipated_need_by_pair={pair:dict(source_working_days=0,
            origin_weekday=2,fixed_floor_qty=0)},allocated_sourcing_by_pair={pair:dict(offers=offers,allocation_weights=(.5,.5))})
    before=deepcopy(args)
    plans,needs,audit=engine.plan_component_network(**args,
        known_supplier_calendar_contexts_by_pair={pair:{"A":context(10),"B":context(20)}})
    assert sum(p.qty for p in plans[pair].proposals)==100
    assert sorted((p.release_day,p.available_day,p.qty) for p in plans[pair].proposals)==[(10,30,50),(20,30,50)]
    assert plans[pair].late_qty==0 and len(audit[pair]["calendar_extensions"])==2
    assert needs[pair]==before["requirements_by_pair"][pair] and args==before
