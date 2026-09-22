"""Hand-computable balances, mixed attribution bounds and identity access."""
import pytest

from .test_lot_journey import load_fixture, page  # noqa: F401


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
