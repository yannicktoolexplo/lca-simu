"""CSV-derived transport contents and impact scope checks on the delivered HTML."""
from collections import defaultdict, deque
import json


def check_operations(page, events, links, check, output):
    def fingerprint():
        return page.evaluate("""async () => {
          const hashes=[], encoder=new TextEncoder(),trace=DATA.lot_trace;
          const collections=[trace.events,trace.genealogy,Object.values(trace.lots).map(l=>[l.lot_id,l.qty,l.uom,l.node_id,l.item_id,l.created_day])];
          for (const rows of collections) for (let start=0;start<rows.length;start+=500) {
            const digest=await crypto.subtle.digest('SHA-256',encoder.encode(JSON.stringify(rows.slice(start,start+500))));
            hashes.push(Array.from(new Uint8Array(digest)).map(b=>b.toString(16).padStart(2,'0')).join(''));
          }
          return hashes;
        }""")
    before=fingerprint()
    journey=page.locator('#lotJourney')
    seed='LOT-00000838'
    assert journey.get_attribute('data-journey-root')==seed
    descendants=defaultdict(set)
    for link in links:
        if link['link_type'] in ('production','transport') and float(link['parent_qty'])>0:
            descendants[link['parent_lot_id']].add(link['child_lot_id'])
    expected={seed};queue=deque([seed])
    while queue:
        for child in descendants[queue.popleft()]-expected:
            expected.add(child);queue.append(child)
    journey.locator('[data-journey-tab="operations"]').click()
    journey.locator('#journeyImpacts > summary').click()
    journey.locator('[data-journey-impact-occurrence]').click()
    actual=set(json.loads(journey.locator('[data-journey-impact-scope]').get_attribute('data-journey-impact-scope')))
    check('impact_exact_descendants_from_csv',actual==expected,occurrences=len(actual))
    check('impact_all_visible_descendants_highlighted',journey.locator('.journeyImpacted').count()==len(expected))
    check('impact_unknown_supplier_lot_explicit',journey.locator('#journeyOriginSelect').count()==0 and 'Aucun lot fabricant' in journey.locator('#journeyImpacts').inner_text())
    shipments={e['shipment_id'] for e in events if e['lot_id'] in expected and e['shipment_id'] and e['event_type'] in ('lane_ship','lane_receipt','shipment_reserve')}
    actual_ships=set(journey.locator('#journeyImpacts [data-journey-shipment-open]').evaluate_all('els=>els.map(e=>e.dataset.journeyShipmentOpen)'))
    check('impact_shipments_match_csv',actual_ships==shipments)
    page.screenshot(path=str(output/'impact-scope.png'))
    # A customer shipment mixes the selected PF and another PF. Inspect its
    # full physical cargo, not just the selected PF's contribution.
    ship='SHIP-00001396'
    journey.locator('#journeyTransports > summary').click()
    journey.locator('#journeyTransports [data-journey-shipment-open="SHIP-00000203"]').first.click()
    # Inspect the inbound supplier planning group, with its current estimates.
    group_ids=page.evaluate("id=>DATA.lot_trace.truck_consolidation.groups.filter(g=>g.shipment_ids.includes(id)).map(g=>g.id)",'SHIP-00000203')
    actual_groups=journey.locator('[data-journey-truck-group]').evaluate_all('els=>els.map(e=>e.dataset.journeyTruckGroup)')
    check('transport_reuses_existing_planning_groups',sorted(actual_groups)==sorted(group_ids) and bool(actual_groups))
    check('transport_marks_estimates_and_no_actual_vehicle','camion(s) estimé(s)' in journey.locator('#journeyTransports').inner_text() and 'Aucun camion réel identifié' in journey.locator('#journeyTransports').inner_text())
    page.screenshot(path=str(output/'supplier-transport.png'))
    # Reveal the shipment list inside the impact panel before using its link.
    journey.locator('#journeyImpacts details').filter(has=page.locator(f'[data-journey-shipment-open="{ship}"]')).locator('summary').click()
    journey.locator(f'#journeyImpacts [data-journey-shipment-open="{ship}"]').click()
    panel=journey.locator(f'[data-journey-shipment-detail="{ship}"]')
    expected_events={e['event_id'] for e in events if e['shipment_id']==ship and e['event_type'] in ('lane_ship','lane_receipt','shipment_reserve')}
    actual_events=set(panel.locator('[data-shipment-event]').evaluate_all('els=>els.map(e=>e.dataset.shipmentEvent)'))
    check('transport_all_cargo_events_match_csv',actual_events==expected_events)
    expected_total=sum(float(e['qty']) for e in events if e['shipment_id']==ship and e['event_type']=='lane_ship')
    check('transport_total_not_selected_pf_portion',float(panel.locator('[data-journey-shipped-item="item:268091"]').get_attribute('data-quantity'))==expected_total==13251)
    expected_sources={e['lot_id'] for e in events if e['shipment_id']==ship and e['event_type']=='lane_ship'}
    actual_sources=set(panel.locator('[data-journey-focus]').evaluate_all('els=>els.map(e=>e.dataset.journeyFocus)'))
    check('transport_contains_both_source_lots',len(expected_sources)==2 and expected_sources<=actual_sources)
    check('transport_inspection_preserves_impact_scope',set(json.loads(journey.locator('[data-journey-impact-scope]').get_attribute('data-journey-impact-scope')))==expected)
    page.screenshot(path=str(output/'customer-transport.png'))
    journey.locator('[data-journey-impact-clear]').click()
    check('impact_reset_removes_highlights',journey.locator('.journeyImpacted').count()==0 and journey.locator('[data-journey-impact-scope]').count()==0)
    journey.locator('[data-journey-shipment-close]').click()
    check('transport_and_impact_preserve_physical_ledger',before==fingerprint())
