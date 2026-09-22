"""Exercise the actual inline JavaScript against small hand-checkable genealogies."""
import json
from pathlib import Path

import pytest
from playwright.sync_api import sync_playwright


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
    """+SCRIPT.read_text(encoding='utf-8')+SCRIPT.with_name('lot_journey_operations.js').read_text(encoding='utf-8')+SCRIPT.with_name('lot_journey_explorer.js').read_text(encoding='utf-8')+SCRIPT.with_name('lot_journey_timeline.js').read_text(encoding='utf-8')+SCRIPT.with_name('lot_journey_case.js').read_text(encoding='utf-8'))


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
