"""Investigation restore, wrong-dataset rejection, and graph-only neighbourhoods."""
import json

import pytest

from .test_lot_journey import load_fixture, page  # noqa: F401
from .test_journey_explorer import timeline_fixture


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
