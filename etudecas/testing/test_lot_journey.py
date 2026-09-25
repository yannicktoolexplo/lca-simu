"""Regression tests grouped by business responsibility; original cases retained."""
from __future__ import annotations

import json
from pathlib import Path
import pytest
from playwright.sync_api import sync_playwright
import csv
from etudecas.visualization.maps.material_delivery import build_scenario_explorer
from etudecas.testing.lot_browser_review import business_batch_csv_oracle
from etudecas.simulation.lot_trace.payload import build_lot_trace_payload
import etudecas.tests.lots.test_lot_trace_payload as payload_fixture
from etudecas.simulation.lot_trace.materials import VERSION
from etudecas.visualization.maps.material_delivery import refresh


# Lot journey

SCRIPT = Path(__file__).parents[1] / 'visualization/maps/lot_journey.js'


@pytest.fixture(scope='module')
def page():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        yield browser.new_page()
        browser.close()


def load_fixture(page, url='about:blank'):
    lots = {}
    for id, node, item, qty, kind in [
        ('S', 'SUP', 'RM', 100, 'opening_stock'), ('R1', 'FACT', 'RM', 60, 'lane_receipt'),
        ('R2', 'FACT', 'RM', 40, 'lane_receipt'), ('P1', 'FACT', 'PF', 50, 'production_output'),
        ('P2', 'FACT', 'PF', 40, 'production_output'), ('P3', 'FACT', 'PF', 100, 'production_output'),
        ('D1', 'DEPOT', 'PF', 50, 'lane_receipt'), ('C1', 'CLIENT', 'PF', 70, 'lane_receipt'),
        ('C2', 'CLIENT', 'PF', 30, 'lane_receipt'), ('UNUSED', 'FACT', 'RM', 10, 'opening_stock')]:
        lots[id] = dict(lot_id=id, node_id=node, item_id='item:'+item, qty=qty, uom='UN',
                        created_event_type=kind, created_day=0, business_lot_id='B-'+id)
    links = []
    for parent, child, qty, kind in [('S','R1',60,'transport'),('S','R2',40,'transport'),
            ('R1','P1',50,'production'),('R2','P2',40,'production'),('P1','D1',50,'transport'),
            ('D1','C1',50,'transport'),('P3','C1',20,'transport'),('P3','C2',30,'transport')]:
        links.append(dict(parent_lot_id=parent, child_lot_id=child, parent_qty=qty,
                          child_qty=lots[child]['qty'], link_type=kind, day=2, departure_day=0,
                          arrival_day=2, shipment_id='SHIP-'+child if kind=='transport' else ''))
    trace = dict(lots=lots, genealogy=links, events=[])
    page.goto(url)
    page.add_script_tag(content='const LOT_TRACE='+json.dumps(trace)+';'+"""
      const nodeById={SUP:{type:'supplier_dc'},FACT:{type:'factory'},DEPOT:{type:'distribution_center'},CLIENT:{type:'customer'}};
      function lotTraceLotInfo(id){return LOT_TRACE.lots[id];}
      function escapeTableHtml(v){return String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));}
      function lotTraceQtyText(q){return String(q);}
      function lotTraceViewModelForLot(id){return id==='P1'?{links:LOT_TRACE.genealogy.map(l=>({...l,contribution_qty:50})),contribution_by_lot:{D1:50,C1:50}}:null;}
      function selectedLotTraceSnapshot(){return {lotId:'P1'};}
    """+SCRIPT.read_text(encoding='utf-8'))


def test_forward_and_reverse_exclude_unrelated_sibling_consumption(page):
    load_fixture(page)
    actual = page.evaluate("journeyScope('P1','both')")
    assert set(actual['lot_ids']) == {'S','R1','P1','D1','C1'}
    assert len(actual['links']) == 4
    upstream = page.evaluate("journeyScope('C1','upstream')")
    assert set(upstream['lot_ids']) == {'S','R1','P1','P3','D1','C1'}
    assert 'C2' not in upstream['lot_ids']
    downstream = page.evaluate("journeyScope('R1','downstream')")
    assert set(downstream['lot_ids']) == {'R1','P1','D1','C1'}


def test_mixed_customer_total_and_selected_pf_contribution_stay_distinct(page):
    load_fixture(page)
    page.evaluate("document.body.innerHTML=lotJourneyHtml({lotId:'P1'})")
    customer = page.locator('[data-journey-lot="C1"]')
    assert 'Total 70 UN' in customer.inner_text()
    assert 'Part du PF suivi : 50 UN' in customer.inner_text()
    assert 'J0' in customer.inner_text()
    customer.click()
    assert 'Part du PF suivi : 50 UN' in page.locator('.journeyDetails').inner_text()
    page.locator('[data-journey-tab="links"]').click()
    page.locator('.journeyDetails [data-journey-focus="C1"]').first.click()
    assert page.locator('#lotJourney').get_attribute('data-journey-direction') == 'upstream'
    assert 'P3' in json.loads(page.locator('#lotJourney').get_attribute('data-journey-scope'))


def test_no_mp_to_pf_quantity_is_invented_without_canonical_contribution(page):
    load_fixture(page)
    html = page.evaluate("lotJourneyState={anchor:'R1',focus:'R1',direction:'downstream',detail:'',limit:60};lotJourneyHtml({lotId:'R1'})")
    assert 'Part du PF suivi' not in html
    assert 'quantité de PF attribuable' in html


def test_unknown_boundaries_and_units_are_explicit(page):
    load_fixture(page)
    page.evaluate("LOT_TRACE.lots.UNUSED.uom='KG';document.body.innerHTML=lotJourneyHtml({lotId:'UNUSED'})")
    page.locator('[data-journey-tab="links"]').click()
    page.locator('.journeyDetails summary').click()
    assert 'histoire antérieure non documentée' in page.locator('.journeyDetails').inner_text()
    assert 'Aucun mouvement documenté' in page.locator('#lotJourney').inner_text()
    assert '10 KG' in page.locator('[data-journey-lot="UNUSED"]').inner_text()


def test_stock_cards_preserve_paths_without_inventing_cross_branches(page):
    load_fixture(page)
    layout = page.evaluate("journeyGroups(journeyScope('S','downstream'))")
    assert all(len(g['lots']) == 1 for g in layout['groups'])
    ids = {g['id']: g['lots'][0] for g in layout['groups']}
    edges = {(ids[e['source']], ids[e['target']]) for e in layout['edges']}
    assert ('R1', 'P1') in edges and ('R2', 'P2') in edges
    assert ('R1', 'P2') not in edges and ('R2', 'P1') not in edges


def test_cycle_is_reported_not_silently_rendered(page):
    load_fixture(page)
    page.evaluate("LOT_TRACE.genealogy.push({parent_lot_id:'C1',child_lot_id:'P1',parent_qty:1,link_type:'transport'});lotJourneyIndex=null")
    assert 'Cycle dans la généalogie' in page.evaluate("lotJourneyHtml({lotId:'P1'})")


def test_search_by_shipment_keeps_the_receipt_identity(page):
    load_fixture(page)
    page.evaluate("LOT_TRACE.events.push({lot_id:'C1',event_type:'lane_receipt',shipment_id:'SHIP-C1'});document.body.innerHTML=lotJourneyHtml({lotId:'P1'})")
    page.locator('#journeySearch').fill('SHIP-C1')
    result = page.locator('#journeySearchResults button')
    assert result.count() == 1
    result.click()
    assert page.locator('#lotJourney').get_attribute('data-journey-root') == 'C1'


def test_render_and_navigation_never_change_the_physical_ledger(page):
    load_fixture(page)
    before = page.evaluate('JSON.stringify(LOT_TRACE)')
    page.evaluate("document.body.innerHTML=lotJourneyHtml({lotId:'P1'})")
    page.locator('button[data-journey-direction="upstream"]').click()
    page.locator('button[data-journey-direction="both"]').click()
    assert page.evaluate('JSON.stringify(LOT_TRACE)') == before


def test_separate_option_does_not_modify_legacy_window(page):
    load_fixture(page)
    page.evaluate("document.body.innerHTML='<button id=lotTraceOpenBtn>Suivi de lots</button><div id=lotTraceModal>Original tracking</div>';installLotJourneyOption()")
    page.locator('#lotJourneyOpenBtn').click()
    assert page.locator('#lotJourneyModal #lotJourney').count() == 1
    assert page.locator('#lotTraceModal').inner_html() == 'Original tracking'
    page.locator('button[data-journey-direction="both"]').click()
    assert page.locator('#lotTraceModal').inner_html() == 'Original tracking'
    page.locator('#lotJourneyCloseBtn').click()
    assert 'visible' not in page.locator('#lotJourneyModal').get_attribute('class')


def balance_fixture(page, movements, uom='UN', quantity=100):
    load_fixture(page)
    rows = [dict(event_id=f'E{i}',lot_id='S',node_id='SUP',item_id='item:RM',uom=uom,
                 event_type=kind,qty=qty,qty_after=after,day=day,shipment_id=ship)
            for i,(kind,qty,after,day,ship) in enumerate(movements)]
    page.evaluate("v=>{LOT_TRACE.lots.S.uom=v.uom;LOT_TRACE.lots.S.qty=v.quantity;LOT_TRACE.events=v.rows;lotJourneyIndex=null}",dict(rows=rows,uom=uom,quantity=quantity))


def test_balance_reserved_departure_is_not_debited_twice(page):
    balance_fixture(page, [('opening_stock',100,100,0,''),('shipment_reserve',60,40,1,'SHIP-A'),
                           ('lane_ship',40,40,3,'SHIP-A'),('production_consume',10,30,4,'')])
    result=page.evaluate("journeyLotBalance('S')")
    assert result['status']=='balanced'
    assert result['totals']==dict(entered=100,consumed=10,shipped=40,served=0,written_off=0,pending=20,remaining=30)
    assert result['last_day']==4 and result['dates']['entered']==dict(first=0,last=0)
    page.evaluate("document.body.innerHTML=journeyLotSummaryHtml('S')")
    assert page.locator('[data-journey-metric="pending"]').get_attribute('data-quantity')=='20'
    assert 'J0' in page.locator('[data-journey-metric="entered"]').inner_text()


def test_balance_fractional_kg_consumption_loss_service_and_direct_ship(page):
    balance_fixture(page,[('lane_receipt',100.5,100.5,0,''),('production_consume_reference_transition',10.25,90.25,1,''),
                          ('lane_ship',20,70.25,2,'SHIP-B'),('stock_writeoff',0.25,70,3,''),('demand_service',5,65,3,'')],uom='KG',quantity=100.5)
    result=page.evaluate("journeyLotBalance('S')")
    assert result['status']=='balanced'
    assert result['totals']==dict(entered=100.5,consumed=10.25,shipped=20,served=5,written_off=0.25,pending=0,remaining=65)
    page.evaluate("document.body.innerHTML=journeyLotSummaryHtml('S')")
    assert '100.5 KG' in page.locator('[data-journey-metric="entered"]').inner_text()


@pytest.mark.parametrize('mutation',[
    "LOT_TRACE.events[1].qty_after=999",
    "LOT_TRACE.events[1].event_id='E0'",
    "LOT_TRACE.events[1].uom='KG'",
    "LOT_TRACE.events[1].qty=null",
    "LOT_TRACE.events[1].event_type='unknown_event'",
    "LOT_TRACE.events[1].qty=1.5",
    "LOT_TRACE.events.shift()",
])
def test_balance_invalid_ledger_never_displays_certified_totals(page, mutation):
    balance_fixture(page,[('opening_stock',100,100,0,''),('lane_ship',10,90,1,'SHIP-A')])
    page.evaluate(mutation)
    page.evaluate("document.body.innerHTML=journeyLotSummaryHtml('S')")
    assert page.locator('[data-journey-balance-status]').get_attribute('data-journey-balance-status')=='invalid'
    assert page.locator('[data-journey-metric]').count()==0


def test_balance_uses_entire_occurrence_independent_of_direction(page):
    balance_fixture(page,[('lane_receipt',100,100,0,''),('production_consume',30,70,1,''),('production_consume',40,30,2,'')])
    page.evaluate("document.body.innerHTML=lotJourneyHtml({lotId:'S'})")
    before=page.locator('.journeyLotSummary').inner_html()
    page.locator('button[data-journey-direction="upstream"]').click()
    assert page.locator('.journeyLotSummary').inner_html()==before
    assert page.locator('[data-journey-metric="consumed"]').get_attribute('data-quantity')=='70'


def test_balance_missing_events_remains_unknown(page):
    load_fixture(page)
    page.evaluate("document.body.innerHTML=journeyLotSummaryHtml('S')")
    assert page.locator('[data-journey-balance-status]').get_attribute('data-journey-balance-status')=='unavailable'
    assert page.locator('[data-journey-metric]').count()==0


# Journey explorer

def timeline_fixture(page, url='about:blank'):
    load_fixture(page,url)
    page.evaluate("""() => {
      LOT_TRACE.lots={};LOT_TRACE.events=[];LOT_TRACE.genealogy=[];
      for(const [id,node,qty,day,type] of [['A','FACT',100,0,'production_output'],['U','FACT',40,0,'opening_stock'],['C','CLIENT',100,4,'lane_receipt']]) {
        LOT_TRACE.lots[id]={lot_id:id,node_id:node,item_id:'item:PF',qty,uom:'UN',created_day:day,created_event_type:type,business_lot_id:'B-'+id};
      }
      function event(id,type,qty,after,day,ship='') {
        const lot=LOT_TRACE.lots[id];
        LOT_TRACE.events.push({event_id:'E'+LOT_TRACE.events.length,lot_id:id,node_id:lot.node_id,item_id:lot.item_id,uom:lot.uom,event_type:type,qty,qty_after:after,day,shipment_id:ship,scenario_id:'scn:TEST'});
      }
      event('A','production_output',100,100,0);event('U','opening_stock',40,40,0);
      event('A','shipment_reserve',60,40,1,'S1');event('A','lane_ship',60,40,2,'S1');event('U','lane_ship',40,0,2,'S1');
      event('C','lane_receipt',100,100,4,'S1');event('C','demand_service',50,50,5);
      event('A','lane_ship',40,0,6,'S2');event('C','demand_service',50,0,7);
      LOT_TRACE.genealogy=[{parent_lot_id:'A',child_lot_id:'C',link_type:'transport',parent_qty:60,child_qty:100,shipment_id:'S1',day:4},{parent_lot_id:'U',child_lot_id:'C',link_type:'transport',parent_qty:40,child_qty:100,shipment_id:'S1',day:4}];
      LOT_TRACE.lots.C.business_lot_ids=['B-A','B-U'];LOT_TRACE.lots.C.business_identity_status='mixed';
      LOT_TRACE.lots.A.stock_occurrence_id='LOCC-A';LOT_TRACE.lots.A.stock_lot_id='STOCKLOT-A';
      lotJourneyIndex=null;journeySearchIndex=null;journeyShipmentIndex=null;
    }""")


@pytest.mark.parametrize('day,expected', [
    (0, {'factory':100,'reserved':0,'transit':0,'customer':0}),
    (1, {'factory':40,'reserved':60,'transit':0,'customer':0}),
    (2, {'factory':40,'reserved':0,'transit':60,'customer':0}),
    (3, {'factory':40,'reserved':0,'transit':60,'customer':0}),
    (4, {'factory':40,'reserved':0,'transit':0,'customer':60}),
    (7, {'factory':0,'reserved':0,'transit':40,'customer':0,'served':60}),
])
def test_timeline_exact_reservation_transit_receipt_and_open_shipment(page,day,expected):
    timeline_fixture(page)
    before=page.evaluate('JSON.stringify(LOT_TRACE)')
    result=page.evaluate('(day)=>journeyNetworkBalance("A",day)',day)
    assert result['status']=='balanced' and result['exact'], result
    for name,qty in expected.items():
        assert result['totals'][name]['lo']==result['totals'][name]['hi']==qty
    assert sum(c['lo'] for c in result['totals'].values())==100
    assert page.evaluate('JSON.stringify(LOT_TRACE)')==before


def test_mixed_service_bounds_match_all_possible_integer_allocations(page):
    timeline_fixture(page)
    result=page.evaluate('journeyNetworkBalance("A",5)')
    assert result['status']=='balanced' and not result['exact']
    # A reception contains 60 selected and 40 other units; service removes 50.
    possible=[selected for selected in range(61) if 0<=50-selected<=40]
    served=result['totals']['served']; stock=result['totals']['customer']
    assert [served['lo'],served['hi']]==[min(possible),max(possible)]==[10,50]
    assert [stock['lo'],stock['hi']]==[60-max(possible),60-min(possible)]==[10,50]
    assert result['received']=={'lo':60,'hi':60}
    assert all(float(c[k]).is_integer() for c in result['totals'].values() for k in ('lo','hi'))


def test_local_balance_before_creation_and_during_reservation(page):
    timeline_fixture(page)
    assert page.evaluate('journeyLotBalance("C",3).status')=='not_created'
    result=page.evaluate('journeyLotBalance("A",1)')
    assert result['totals']['remaining']==40 and result['totals']['pending']==60
    assert result['totals']['shipped']==0
    # Recentring on a customer starts a new whole-receipt scope; its initial
    # recorded receipt is included in the cumulative customer arrivals.
    result=page.evaluate('journeyNetworkBalance("C",4)')
    assert result['received']=={'lo':100,'hi':100}
    assert result['totals']['customer']['lo']==100


def test_missing_departure_is_unknown_not_a_fictitious_zero(page):
    timeline_fixture(page)
    page.evaluate("LOT_TRACE.events=LOT_TRACE.events.filter(r=>!(r.lot_id==='A' && r.event_type==='lane_ship'));lotJourneyIndex=null")
    result=page.evaluate('journeyNetworkBalance("A",4)')
    assert result['status']=='unavailable' and 'totals' not in result


def test_identity_search_finds_mixed_business_occurrences_and_filters(page):
    timeline_fixture(page)
    for query,expected in [('B-A',{'A','C'}),('LOCC-A',{'A'}),('STOCKLOT-A',{'A'}),('S1',{'C'}),('S2',{'A'})]:
        result=page.evaluate("q=>{journeyExplorer.query=q;return journeyFindLots().map(r=>r.lot.lot_id)}",query)
        assert set(result)==expected
    result=page.evaluate("journeyExplorer.query='B-A';journeyExplorer.site='CLIENT';journeyExplorer.from='4';journeyExplorer.to='4';journeyFindLots().map(r=>r.lot.lot_id)")
    assert result==['C']


def test_documented_origin_and_handling_unit_search_and_quality_unknown(page):
    timeline_fixture(page)
    page.evaluate("""LOT_TRACE.material_traceability={origins:{O:{id:'O',manufacturer_id:'SUP-EXT',batch_number:'EXT-777',source_reference:'Document test',status:'observed'}},receipt_ids_by_lot:{C:['R']},receipts:{R:{lot_id:'C',origins:[{origin_id:'O',quantity:10}],possible_origin_ids:[],handling_units:[{id:'PALLET-123',kind:'pallet',quantity:100}],risk_event_ids:['RISK-TEST']}}};journeySearchIndex=null""")
    for query in ['SUP-EXT','EXT-777','PALLET-123']:
        assert page.evaluate("q=>{journeyExplorer.query=q;return journeyFindLots().map(r=>r.lot.lot_id)}",query)==['C']
    html=page.evaluate('journeyIdentitiesHtml("C")')
    assert all(value in html for value in ['Document test','PALLET-123','RISK-TEST','scn:TEST','Non documentées'])


def test_inspection_navigation_history_and_date_do_not_mutate_data(page):
    timeline_fixture(page)
    errors=[]
    page.on('pageerror',lambda error:errors.append(str(error)))
    before=page.evaluate('JSON.stringify(LOT_TRACE)')
    page.evaluate("document.body.innerHTML=lotJourneyHtml({lotId:'A'})")
    page.locator('[data-journey-lot="C"]').click()
    assert page.locator('.journeyInspected').get_attribute('data-journey-lot')=='C'
    assert page.locator('#lotJourney').get_attribute('data-journey-root')=='A'
    page.locator('#journeyDay').fill('3');page.locator('#journeyDay').dispatch_event('change')
    assert page.locator('[data-journey-balance-status]').get_attribute('data-journey-balance-status')=='not_created'
    page.locator('[data-journey-tab="links"]').click()
    page.locator('.journeyDetails [data-journey-focus="C"]').first.click()
    assert page.locator('#lotJourney').get_attribute('data-journey-root')=='C'
    page.locator('[data-journey-back]').click()
    assert page.locator('#lotJourney').get_attribute('data-journey-root')=='A'
    assert page.locator('#journeyDay').input_value()=='3'
    assert page.evaluate('JSON.stringify(LOT_TRACE)')==before
    assert not errors


def test_reference_transition_is_consumption_and_unknown_history_is_explicit(page):
    timeline_fixture(page)
    page.evaluate("LOT_TRACE.events=LOT_TRACE.events.filter(r=>r.lot_id==='A' && r.day===0);LOT_TRACE.genealogy=[];LOT_TRACE.events.push({...LOT_TRACE.events[0],event_id:'TRANSITION',event_type:'production_consume_reference_transition',qty:30,qty_after:70,day:1});lotJourneyIndex=null")
    result=page.evaluate('journeyNetworkBalance("A",1)')
    assert result['totals']['consumed']['lo']==30 and result['totals']['factory']['lo']==70
    assert 'Remplacement de référence' in page.evaluate('journeyIdentitiesHtml("A")')
    assert 'antérieur à J0 non documenté' in page.evaluate('journeyIdentitiesHtml("U")')


def test_fractional_kg_roundoff_does_not_amplify_in_conservation_bounds(page):
    timeline_fixture(page)
    page.evaluate("""LOT_TRACE.genealogy=[];LOT_TRACE.lots.A.uom='KG';LOT_TRACE.lots.A.qty=37598.5325;
    const base={lot_id:'A',node_id:'FACT',item_id:'item:PF',uom:'KG'};
    LOT_TRACE.events=[{...base,event_id:'K0',event_type:'production_output',qty:37598.5325,qty_after:37598.5325,day:0},
      {...base,event_id:'K1',event_type:'production_consume',qty:22222.123456,qty_after:15376.409044,day:1},
      {...base,event_id:'K2',event_type:'production_consume',qty:15376.409048,qty_after:0,day:2}];lotJourneyIndex=null;""")
    result=page.evaluate('journeyNetworkBalance("A",2)')
    assert result['status']=='balanced' and result['exact'],result
    assert result['totals']['consumed']['lo']==pytest.approx(37598.5325,abs=0.00002)


# Journey operations

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


# Journey case

@pytest.fixture
def case_page(page,tmp_path):
    html=tmp_path/'fixture.html';html.write_text('<!doctype html><meta charset="utf-8">',encoding='utf-8')
    timeline_fixture(page,html.as_uri())
    page.evaluate("document.body.innerHTML=lotJourneyHtml({lotId:'A'})")
    return page


def test_saved_case_roundtrip_restores_context_and_recomputes_impact(case_page):
    p=case_page
    before=p.evaluate('JSON.stringify(LOT_TRACE)')
    p.evaluate("lotJourneyState.detail='C';journeyExplorer.day=5;journeyExplorer.tab='identity';journeyExplorer.query='B-A';journeyExplorer.site='CLIENT';journeyExplorer.zoom=0.75;journeyCaseState.depth=1;journeyOpsState.shipment='S1';journeyOpsState.impact=journeyImpact('occurrence','A')")
    doc=p.evaluate('journeyCaseDocument()')
    assert len(doc['dataset']['sha256'])==64 and doc['dataset']['scenarios']==['scn:TEST']
    p.evaluate("lotJourneyState.focus='U';lotJourneyState.detail='';journeyExplorer.day=0;journeyOpsState.impact=null;journeyCaseState.depth=null")
    p.evaluate('doc=>journeyRestoreCase(doc)',doc)
    assert p.evaluate('journeyCaseSnapshot()')==doc['view']
    assert set(p.evaluate('journeyOpsState.impact.ids'))=={'A','C'}
    assert p.evaluate('JSON.stringify(LOT_TRACE)')==before


def test_case_rejects_same_lot_ids_with_different_physical_results(case_page):
    p=case_page;doc=p.evaluate('journeyCaseDocument()')
    p.evaluate("LOT_TRACE.events[0].qty=101;journeyDatasetPromise=null")
    before=p.evaluate('JSON.stringify(journeyCaseSnapshot())')
    with pytest.raises(Exception,match='données différentes'):p.evaluate('doc=>journeyRestoreCase(doc)',doc)
    assert p.evaluate('JSON.stringify(journeyCaseSnapshot())')==before


@pytest.mark.parametrize('mutation',[
    "doc.view.day=-1", "doc.view.direction='unknown'", "doc.view.focus='UNKNOWN'",
    "doc.view.zoom=100", "doc.view.shipment='NO-SHIP'", "doc.view.impact={type:'occurrence',id:'missing'}",
    "doc.view.detail='U'", "doc.view.filters.from='NaN'", "doc.view.expanded=['UNKNOWN']",
])
def test_invalid_case_never_partially_replaces_navigation(case_page,mutation):
    p=case_page;doc=p.evaluate('journeyCaseDocument()');before=p.evaluate('JSON.stringify(journeyCaseSnapshot())')
    altered=p.evaluate('doc=>{'+mutation+';return doc}',doc)
    with pytest.raises(Exception):p.evaluate('doc=>journeyRestoreCase(doc)',altered)
    assert p.evaluate('JSON.stringify(journeyCaseSnapshot())')==before


def test_import_cannot_inject_extra_filter_properties(case_page):
    p=case_page;doc=p.evaluate('journeyCaseDocument()')
    doc['view']['filters']['__proto__']={'polluted':True};doc['view']['filters']['arbitrary']='injected'
    p.evaluate('doc=>journeyRestoreCase(doc)',doc)
    assert p.evaluate('journeyExplorer.polluted===undefined && journeyExplorer.arbitrary===undefined')


def test_neighbourhood_expansion_preserves_real_edges_and_full_scope(page):
    load_fixture(page)
    page.evaluate("document.body.innerHTML=lotJourneyHtml({lotId:'P1'})")
    scope_before=page.locator('#lotJourney').get_attribute('data-journey-scope')
    page.locator('#journeyDepth').select_option('1')
    assert set(page.locator('.journeyNode').evaluate_all('els=>els.map(e=>e.dataset.journeyLot)'))=={'P1','D1'}
    assert page.locator('#lotJourney').get_attribute('data-journey-scope')==scope_before
    page.locator('[data-journey-lot="D1"]').click();page.locator('[data-journey-expand]').click()
    assert set(page.locator('.journeyNode').evaluate_all('els=>els.map(e=>e.dataset.journeyLot)'))=={'P1','D1','C1'}
    assert 'P3' not in json.loads(scope_before)
    page.locator('button[data-journey-direction="upstream"]').click()
    assert set(page.locator('.journeyNode').evaluate_all('els=>els.map(e=>e.dataset.journeyLot)'))=={'P1','R1'}
    assert page.evaluate('journeyCaseState.expanded')==[]


def test_neighbourhood_does_not_truncate_network_totals(case_page):
    p=case_page
    p.evaluate("""() => {
      LOT_TRACE.lots.D={...LOT_TRACE.lots.C,lot_id:'D',qty:50,created_day:8};
      const shipped=LOT_TRACE.events.find(r=>r.lot_id==='C' && r.day===7);
      shipped.event_type='lane_ship';shipped.shipment_id='S3';
      LOT_TRACE.events.push({...shipped,event_id:'FINAL-RECEIPT',lot_id:'D',event_type:'lane_receipt',day:8,qty_after:50});
      LOT_TRACE.genealogy.push({parent_lot_id:'C',child_lot_id:'D',link_type:'transport',parent_qty:50,child_qty:50,shipment_id:'S3',day:8});
      lotJourneyIndex=null;journeyExplorer.day=8;refreshLotJourney();
    }""")
    assert p.locator('.journeyNode').count()==3
    before=p.locator('[data-network-category]').evaluate_all('els=>els.map(e=>[e.dataset.networkCategory,e.dataset.low,e.dataset.high])')
    assert ['customer','10','50'] in before
    p.locator('#journeyDepth').select_option('1')
    assert p.locator('.journeyNode').count()==2
    assert p.locator('[data-network-category]').evaluate_all('els=>els.map(e=>[e.dataset.networkCategory,e.dataset.low,e.dataset.high])')==before


def test_printable_report_captures_date_bounds_and_full_links(case_page):
    p=case_page;p.evaluate("journeyExplorer.day=5;lotJourneyState.detail='C';journeyCaseState.depth=1")
    doc=p.evaluate('journeyCaseDocument()')
    p.evaluate("journeyExplorer.day=0;lotJourneyState.focus='U'")
    report=p.evaluate('doc=>journeyReportHtml(doc)',doc)
    assert 'Fin de J5' in report and '10 à 50' in report and 'scn:TEST' in report
    assert 'Solde au site' in report and '<td>50</td>' in report
    assert 'Liens du parcours complet (1)' in report and 'Historique complet' in report
    assert doc['dataset']['sha256'] in report and '<script' not in report


def test_report_escapes_identifiers_instead_of_executing_markup(case_page):
    p=case_page;p.evaluate("LOT_TRACE.lots.A.business_lot_id='<img src=x onerror=alert(1)>';journeyDatasetPromise=null")
    doc=p.evaluate('journeyCaseDocument()');report=p.evaluate('doc=>journeyReportHtml(doc)',doc)
    assert '<img' not in report and '&lt;img' in report


def test_real_download_and_file_reopen_offline(case_page,tmp_path):
    p=case_page;errors=[];p.on('pageerror',lambda error:errors.append(str(error)))
    p.locator('.journeyCaseTools summary').click()
    with p.expect_download() as capture:p.locator('[data-journey-case-save]').click()
    path=tmp_path/capture.value.suggested_filename;capture.value.save_as(path)
    p.evaluate("journeyExplorer.day=0;refreshLotJourney()")
    p.locator('.journeyCaseTools summary').click();p.locator('#journeyCaseFile').set_input_files(path)
    p.wait_for_function("document.getElementById('journeyCaseMessage').textContent.includes('restaurée')")
    assert p.evaluate('journeyExplorer.day') is None
    assert not errors


# Journey scenario delivery

def scenario_files(tmp_path):
    data=tmp_path/'data';data.mkdir()
    row=dict(event_id='E0',lot_id='LOT-TEST',event_type='opening_stock',day=0,node_id='SUP',item_id='item:TEST',
        uom='UN',qty=100,qty_after=100,scenario_id='scn:TEST',shipment_id='',source_id='',source_type='opening_stock',
        trace_status='untraced_before_horizon',business_batch_id='',stock_lot_id='STOCK-TEST',lot_occurrence_id='LOCC-TEST')
    with (data/'production_lot_events.csv').open('w',encoding='utf-8',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(row));writer.writeheader();writer.writerow(row)
    (data/'production_lot_genealogy.csv').write_text('parent_lot_id,child_lot_id,link_type,parent_qty,child_qty,day,shipment_id\n',encoding='utf-8')
    graph=tmp_path/'graph.json';graph.write_text(json.dumps({'nodes':[{'id':'SUP','type':'supplier_dc'}],'edges':[]}),encoding='utf-8')
    return data,graph


def test_scenario_export_opens_offline_with_unknown_origin_and_unchanged_inputs(tmp_path,page):
    data,graph=scenario_files(tmp_path)
    before={p:p.read_bytes() for p in [*data.iterdir(),graph]}
    output=tmp_path/'explorer.html'
    report=build_scenario_explorer(data,graph,output,tmp_path/'evidence')
    assert report['scenario']=='scn:TEST' and report['lots']==1
    errors=[];page.on('pageerror',lambda error:errors.append(str(error)))
    page.goto(output.as_uri());page.wait_for_selector('#lotJourneyModal.visible')
    assert 'scn:TEST' in page.locator('#lotJourneyTitle').inner_text()
    page.locator('[data-journey-tab="identity"]').click()
    text=page.locator('.journeyIdentities').inner_text()
    assert 'Non documentée' in text and 'antérieur à J0' in text
    assert page.locator('[data-network-category="supplier"]').get_attribute('data-low')=='100'
    assert not errors
    assert all(p.read_bytes()==content for p,content in before.items())


def test_scenario_export_rejects_graph_different_from_run_manifest(tmp_path):
    data,graph=scenario_files(tmp_path)
    other=tmp_path/'other.json';other.write_text('{}',encoding='utf-8')
    (tmp_path/'run_manifest.json').write_text(json.dumps({'input_graph':str(other)}),encoding='utf-8')
    with pytest.raises(ValueError,match='Graph must match'):
        build_scenario_explorer(data,graph,tmp_path/'explorer.html',tmp_path/'evidence')
    assert not (tmp_path/'explorer.html').exists()


def test_scenario_export_rejects_missing_scenario_identity(tmp_path):
    data,graph=scenario_files(tmp_path)
    path=data/'production_lot_events.csv';path.write_text(path.read_text(encoding='utf-8').replace('scn:TEST',''),encoding='utf-8')
    with pytest.raises(ValueError,match='explicitly identified'):
        build_scenario_explorer(data,graph,tmp_path/'explorer.html',tmp_path/'evidence')


# Lot customer oracle

def test_customer_oracle_uses_current_csv_split_and_excludes_future_receipts(tmp_path):
    (tmp_path / 'data').mkdir()
    (tmp_path / 'summaries').mkdir()
    (tmp_path / 'summaries/first_simulation_summary.json').write_text(json.dumps({'sim_days':5}))
    def write(name, rows):
        with (tmp_path / 'data' / name).open('w', newline='', encoding='utf-8') as stream:
            writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
    write('production_demand_service_daily.csv', [{'node_id':'CLIENT'}])
    write('production_lot_events.csv', [dict(event_type='production_output', business_batch_id='BATCH', lot_id='ROOT', qty=20)])
    links = [dict(link_type='transport', parent_business_batch_id='BATCH', parent_lot_id='DEPOT', child_lot_id=f'C{i}', child_node_id='CLIENT', shipment_id=f'S{i}', parent_qty=qty, arrival_day=day)
             for i, (qty, day) in enumerate([(3, 2), (7, 3), (10, 8)])]
    write('production_lot_genealogy.csv', links)
    result = business_batch_csv_oracle(tmp_path, 'BATCH')
    assert sorted(result['contributions'].values()) == [3, 7]
    assert result['root_qty'] == 20
    assert result['remaining_not_received_qty'] == 10
    links[0]['parent_qty'] = 30
    write('production_lot_genealogy.csv', links)
    with pytest.raises(ValueError, match='exceed'):
        business_batch_csv_oracle(tmp_path, 'BATCH')


# Material delivery

def test_payload_loads_explicit_origins_without_promoting_simulated_batches(tmp_path):
    fixture = payload_fixture.LotTracePayloadTest()
    paths = [tmp_path / name for name in ('events.csv', 'genealogy.csv', 'plan.csv')]
    for path, fields, rows in zip(paths, [payload_fixture.EVENT_FIELDS, payload_fixture.GENEALOGY_FIELDS, payload_fixture.PLAN_FIELDS],
                                   [fixture._events(), fixture._genealogy(), []]):
        fixture._write_csv(path, fields, rows)
    metadata = dict(version=VERSION, origins=[dict(id='ORIGIN', manufacturer_id='MAKER',
        batch_number='SUP-1', item_id='item:RM', status='observed', source_reference='test:certificate')],
        allocations=[dict(receipt_id='E1', origin_id='ORIGIN', quantity=100, uom='UN')])
    (tmp_path / 'material_traceability.json').write_text(json.dumps(metadata), encoding='utf-8')
    payload = build_lot_trace_payload(*paths, raw=fixture._raw_graph())
    assert payload['material_traceability']['receipts']['E3']['origins'][0]['origin_id'] == 'ORIGIN'
    assert payload['material_traceability']['receipts']['E11']['origins'] == []
    with pytest.raises(FileNotFoundError):
        build_lot_trace_payload(*paths, raw=fixture._raw_graph(), material_traceability_json=tmp_path / 'absent.json')
    metadata['allocations'][0]['quantity'] = 101
    (tmp_path / 'material_traceability.json').write_text(json.dumps(metadata), encoding='utf-8')
    with pytest.raises(ValueError, match='exceed received'):
        build_lot_trace_payload(*paths, raw=fixture._raw_graph())


def test_refresh_refuses_to_attach_another_runs_csvs(tmp_path):
    event = dict(event_id='E1', lot_id='L1', event_type='opening_stock', item_id='item:RM',
                 node_id='SUP', qty=100, day=0, uom='UN')
    html = tmp_path / 'source.html'
    html.write_text('const DATA = ' + json.dumps({'lot_trace': {'events': [event], 'genealogy': []}}) + ';', encoding='utf-8')
    with (tmp_path / 'production_lot_events.csv').open('w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=list(event))
        writer.writeheader()
        writer.writerow({**event, 'qty': 101})
    destination = tmp_path / 'out.html'
    with pytest.raises(ValueError, match='Map/CSV mismatch'):
        refresh(html, tmp_path, Path('unused-graph'), destination, tmp_path / 'proof')
    assert not destination.exists()
    with pytest.raises(ValueError, match='historical map'):
        refresh(html, tmp_path, Path('unused-graph'), html, tmp_path / 'proof')
