"""Hand-checkable cargo and impact cases, including unrelated co-loaded lots."""
import json

import pytest

from .test_lot_journey import load_fixture, page  # noqa: F401


def operations_fixture(page):
    load_fixture(page)
    page.evaluate("""() => {
      let sequence=0;
      const events=[], balances={};
      function event(id,type,qty,after,ship='',day=0) {
        const lot=LOT_TRACE.lots[id];
        events.push({event_id:'E'+sequence++,lot_id:id,node_id:lot.node_id,item_id:lot.item_id,uom:lot.uom,
          event_type:type,qty,qty_after:after,shipment_id:ship,day,departure_day:day,arrival_day:day+2});
      }
      Object.values(LOT_TRACE.lots).forEach(lot=>{
        balances[lot.lot_id]=lot.qty;
        event(lot.lot_id,lot.created_event_type,lot.qty,lot.qty,
          lot.created_event_type==='lane_receipt'?'SHIP-'+lot.lot_id:'');
      });
      LOT_TRACE.genealogy.forEach(link=>{
        const id=link.parent_lot_id;balances[id]-=link.parent_qty;
        if (id==='D1') event(id,'shipment_reserve',link.parent_qty,balances[id],link.shipment_id,1);
        event(id,link.link_type==='transport'?'lane_ship':'production_consume',link.parent_qty,balances[id],link.shipment_id,2);
      });
      event('C1','demand_service',70,0,'',4);
      LOT_TRACE.events=events;lotJourneyIndex=null;journeyShipmentIndex=null;
      LOT_TRACE.truck_consolidation={capacity:{max_pallets:33,max_weight_kg:23000},groups:[
        {id:'G1',origin:'DEPOT',destination:'CLIENT',start_day:0,end_day:6,shipment_ids:['SHIP-C1','SHIP-C2'],
         truck_count:null,estimated_truck_count:1,estimated_pallets:2,missing_dimensions:['weight'],estimate_basis:['test:packaging-analogy']}]};
    }""")


def test_complete_shipment_cargo_excludes_reservation_double_count(page):
    operations_fixture(page)
    before=page.evaluate('JSON.stringify(LOT_TRACE)')
    detail=page.evaluate("journeyShipmentDetail('SHIP-C1')")
    assert {r['lot_id'] for r in detail['departures']}=={'D1','P3'}
    assert detail['totals']==[dict(item_id='item:PF',uom='UN',quantity=70)]
    assert len(detail['receipts'])==1 and len(detail['reservations'])==1
    page.evaluate("document.body.innerHTML=journeyShipmentHtml('SHIP-C1')")
    assert 'camion(s) estimé(s)' in page.locator('body').inner_text()
    assert page.locator('[data-journey-shipment-open="SHIP-C2"]').count()==1
    assert page.evaluate('JSON.stringify(LOT_TRACE)')==before


def test_missing_transport_profile_does_not_invent_truck_or_arrival(page):
    operations_fixture(page)
    page.evaluate("LOT_TRACE.events=LOT_TRACE.events.filter(r=>r.event_type!=='lane_receipt');journeyShipmentIndex=null;LOT_TRACE.truck_consolidation.groups=[];document.body.innerHTML=journeyShipmentHtml('SHIP-C1')")
    text=page.locator('body').inner_text()
    assert 'capacité inconnue' in text and 'Réception non enregistrée' in text
    assert 'camion(s) estimé(s)' not in text


def test_transport_totals_do_not_add_different_articles_or_units(page):
    operations_fixture(page)
    page.evaluate("LOT_TRACE.events.filter(r=>r.shipment_id==='SHIP-C1' && r.lot_id==='P3').forEach(r=>{r.item_id='item:OTHER';r.uom='KG'});journeyShipmentIndex=null")
    totals=page.evaluate("journeyShipmentDetail('SHIP-C1').totals")
    assert {(t['item_id'],t['uom'],t['quantity']) for t in totals}=={('item:PF','UN',50),('item:OTHER','KG',20)}


def test_impact_does_not_spread_to_co_loaded_or_other_mixed_origins(page):
    operations_fixture(page)
    result=page.evaluate("journeyImpact('occurrence','R1')")
    assert set(result['ids'])=={'R1','P1','D1','C1'}
    assert result['productions']==['P1'] and result['customers']==['C1']
    assert result['stocks']==[dict(id='R1',remaining=10,pending=0,day=2)]
    assert 'SHIP-C1' in result['shipments'] and 'SHIP-C2' not in result['shipments']
    assert result['unknown']==[]


def test_supplier_lot_scope_requires_explicit_identity_including_possible_mixes(page):
    operations_fixture(page)
    page.evaluate("""LOT_TRACE.material_traceability={origins:{O:{id:'O',manufacturer_id:'SUP',batch_number:'BATCH-O',status:'observed'}},receipts:{
      E1:{lot_id:'R1',origins:[{origin_id:'O',quantity:5}]},
      E2:{lot_id:'R2',origins:[],possible_origin_ids:['O']}}} """)
    result=page.evaluate("journeyImpact('supplier_lot','O')")
    assert set(result['seeds'])=={'R1','R2'}
    assert set(result['productions'])=={'P1','P2'}
    assert 'P3' not in result['ids']
    with pytest.raises(Exception,match='Aucune occurrence'):
        page.evaluate("journeyImpact('supplier_lot','UNKNOWN')")


def test_impact_navigation_clear_and_transport_leave_ledger_and_legacy_unchanged(page):
    operations_fixture(page)
    before=page.evaluate('JSON.stringify(LOT_TRACE)')
    page.evaluate("document.body.innerHTML='<div id=lotTraceModal>Original</div>'+lotJourneyHtml({lotId:'R1'})")
    page.locator('[data-journey-tab="operations"]').click()
    page.locator('#journeyImpacts summary').first.click()
    page.locator('[data-journey-impact-occurrence]').click()
    assert set(json.loads(page.locator('[data-journey-impact-scope]').get_attribute('data-journey-impact-scope')))=={'R1','P1','D1','C1'}
    assert page.locator('.journeyImpacted').count()==4
    page.locator('#journeyImpacts [data-journey-focus="P1"]').click()
    assert page.locator('[data-journey-impact-scope]').count()==1
    page.locator('[data-journey-tab="operations"]').click()
    page.locator('#journeyTransports summary').first.click()
    page.locator('#journeyTransports [data-journey-shipment-open="SHIP-D1"]').click()
    assert page.locator('[data-journey-shipment-detail="SHIP-D1"]').count()==1
    page.locator('[data-journey-impact-clear]').click()
    assert page.locator('.journeyImpacted').count()==0
    assert page.locator('#lotTraceModal').inner_html()=='Original'
    assert page.evaluate('JSON.stringify(LOT_TRACE)')==before


def test_unused_supplier_identity_has_visible_error(page):
    operations_fixture(page)
    page.evaluate("LOT_TRACE.material_traceability={origins:{O:{id:'O',manufacturer_id:'SUP',batch_number:'Unused',status:'observed'}},receipts:{},receipt_ids_by_lot:{}};document.body.innerHTML=lotJourneyHtml({lotId:'R1'})")
    page.locator('[data-journey-tab="operations"]').click()
    page.locator('#journeyImpacts summary').first.click()
    page.locator('#journeyOriginSelect').select_option('O')
    assert 'Aucune occurrence' in page.locator('[data-journey-impact-error]').inner_text()
