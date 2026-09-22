"""Read-only audit of coverage, identity search and practical lot navigation."""
import hashlib
import json
from pathlib import Path
import time

from playwright.sync_api import sync_playwright


def audit(html, output):
    output.mkdir(parents=True, exist_ok=True)
    script=(Path(__file__).parents[1]/'visualization/maps/lot_journey.js').read_text(encoding='utf-8')
    pure=script[:script.index('function journeyLotSummaryHtml')]
    report={'html':str(html),'sha256':hashlib.sha256(html.read_bytes()).hexdigest(),'javascript_errors':[]}
    with sync_playwright() as p:
        browser=p.chromium.launch(headless=True)
        page=browser.new_page(offline=True,viewport={'width':1366,'height':768})
        page.on('pageerror',lambda e:report['javascript_errors'].append(str(e)))
        start=time.perf_counter()
        page.goto(html.resolve().as_uri(),timeout=90000)
        page.wait_for_function('typeof DATA!=="undefined" && DATA.lot_trace && document.querySelector(".js-plotly-plot")',timeout=90000)
        report['load_seconds']=round(time.perf_counter()-start,2)
        report['data']=page.evaluate("""pure=>{
          const t=DATA.lot_trace,lots=Object.values(t.lots),counts={},bad=[];
          const inspect=new Function('LOT_TRACE','nodeById','lotTraceLotInfo','escapeTableHtml',pure+';return {balance:journeyLotBalance,scope:journeyScope};');
          const api=inspect(t,{},id=>t.lots[id],String);
          for (const lot of lots) {const r=api.balance(lot.lot_id);counts[r.status]=(counts[r.status]||0)+1;if(r.status!=='balanced')bad.push({id:lot.lot_id,...r});}
          const s=api.scope('LOT-00000003','downstream');
          const m=t.material_traceability || {},g=t.truck_consolidation?.groups || [];
          return {keys:Object.keys(DATA),lot_count:lots.length,event_count:t.events.length,link_count:t.genealogy.length,
            balance_status:counts,balance_exceptions:bad.slice(0,30),business_mixed:lots.filter(l=>l.business_identity_status==='mixed').length,
            opening_stock:lots.filter(l=>l.created_event_type==='opening_stock').length,manufacturer_origins:Object.keys(m.origins || {}).length,
            inbound_handling_units:Object.values(m.receipts || {}).reduce((n,r)=>n+r.handling_units.length,0),
            transport_groups:g.length,estimated_groups:g.filter(r=>r.estimated_truck_count!=null).length,proposed_groups:g.filter(r=>r.truck_count!=null).length,
            unknown_groups:g.filter(r=>r.truck_count==null && r.estimated_truck_count==null).length,
            broad_scope:{root:'LOT-00000003',lots:s.lot_ids.length,links:s.links.length},
            signaled:lots.filter(l=>l.business_lot_id==='PBATCH-411EC755D7110AE0' || (l.business_lot_ids || []).includes('PBATCH-411EC755D7110AE0')).map(l=>({id:l.lot_id,business:l.business_lot_id,occurrence:l.stock_occurrence_id,status:l.business_identity_status,node:l.node_id}))};
        }""",pure)
        page.locator('#modeOps').click()
        page.locator('#lotTraceSelect').select_option('LOT-00002658')
        page.locator('#lotJourneyOpenBtn').click()
        page.screenshot(path=str(output/'overview-1366.png'))
        searches=[]
        for query in ['PBATCH-411EC755D7110AE0','LOCC-00002658','LOT-00002658','SHIP-00001396','338929']:
            start=time.perf_counter();page.locator('#journeySearch').fill(query)
            searches.append({'query':query,'text':page.locator('#journeySearchResults').inner_text(),'buttons':page.locator('#journeySearchResults button').count(),'seconds':round(time.perf_counter()-start,3)})
        report['searches']=searches
        page.locator('#journeySearch').fill('')
        page.locator('[data-journey-lot="LOT-00002738"]').click()
        report['after_card_click']={
            'graph_focus':page.locator('#lotJourney').get_attribute('data-journey-root'),
            'summary_lot':page.locator('[data-journey-summary-lot]').get_attribute('data-journey-summary-lot'),
            'direction':page.locator('#lotJourney').get_attribute('data-journey-direction')}
        page.locator('.journeyDetails [data-journey-focus="LOT-00002738"]').first.click()
        report['reverse_customer_scope']=json.loads(page.locator('#lotJourney').get_attribute('data-journey-scope'))
        page.locator('#journeySearch').fill('LOT-00000003')
        page.locator('#journeySearchResults button').first.click()
        start=time.perf_counter();page.locator('button[data-journey-direction="downstream"]').click()
        report['broad_view']={'seconds':round(time.perf_counter()-start,2),'cards':page.locator('.journeyNode').count(),
                             'notice':page.locator('#lotJourney').inner_text()[-1800:]}
        page.screenshot(path=str(output/'broad-scope-1366.png'))
        report['controls']=page.locator('#lotJourney').evaluate("e=>({scrollWidth:e.scrollWidth,clientWidth:e.clientWidth,buttons:[...e.querySelectorAll('button')].map(b=>b.textContent),inputs:[...e.querySelectorAll('input')].map(i=>({id:i.id,type:i.type}))})")
        browser.close()
    (output/'audit.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:report[k] for k in ['load_seconds','data','after_card_click','broad_view','javascript_errors']},ensure_ascii=True))
    return report


if __name__=='__main__':
    audit(Path('etudecas/simulation/result/_reruns/corrected_map_20260918/maps/supply_graph_corrected_map_20260918_transport_impacts.html'),Path('etudecas/artifacts/testing/lot_usability_20260919'))
