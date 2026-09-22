"""Offline browser checks against an independent CSV recall-scope traversal."""
import argparse
from collections import defaultdict, deque
import csv
import hashlib
import json
from pathlib import Path


def review(html, data, output):
    from playwright.sync_api import sync_playwright

    output.mkdir(parents=True, exist_ok=True)
    with (data / "production_lot_genealogy.csv").open(encoding="utf-8-sig", newline="") as handle:
        links = list(csv.DictReader(handle))
    with (data / "production_lot_events.csv").open(encoding="utf-8-sig", newline="") as handle:
        events = list(csv.DictReader(handle))
    # Independent expectation, from the CSVs rather than the display builder.
    receipt = next(e for e in events if e["event_type"] == "lane_receipt" and e["shipment_id"] == "SHIP-00000203")
    adjacency = defaultdict(set)
    for link in links:
        if link["link_type"] in {"production", "transport"} and float(link["parent_qty"]) > 0:
            adjacency[link["parent_lot_id"]].add(link["child_lot_id"])
    reached = {receipt["lot_id"]}
    queue = deque(reached)
    while queue:
        for child in adjacency[queue.popleft()] - reached:
            reached.add(child)
            queue.append(child)
    expected_outputs = sorted({e["lot_id"] for e in events if e["event_type"] == "production_output" and e["lot_id"] in reached})
    report = dict(html=str(html), html_sha256=hashlib.sha256(html.read_bytes()).hexdigest(),
                  checks=[], javascript_errors=[], scope="Receipt quantities, unknown origin, independent recall scope, unrelated branch exclusion, UI reset and source immutability.")

    def check(name, ok, **evidence):
        report["checks"].append(dict(name=name, ok=bool(ok), **evidence))
        print(json.dumps({"check": name, "ok": bool(ok)}), flush=True)

    def physical_fingerprint(page):
        return page.evaluate("""async () => {
          const trace=DATA.lot_trace, hashes=[], encoder=new TextEncoder();
          const collections=[trace.events, trace.genealogy,
            Object.values(trace.lots).map(l=>[l.lot_id,l.qty,l.uom,l.node_id,l.item_id,l.created_day])];
          for (const rows of collections) {
            for (let start=0; start<rows.length; start+=500) {
              const digest=await crypto.subtle.digest('SHA-256',encoder.encode(JSON.stringify(rows.slice(start,start+500))));
              hashes.push(Array.from(new Uint8Array(digest)).map(b=>b.toString(16).padStart(2,'0')).join(''));
            }
          }
          return hashes;
        }""")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            page = browser.new_page(offline=True, viewport={"width": 1800, "height": 1100})
            page.on("pageerror", lambda err: report["javascript_errors"].append(str(err)))
            page.goto(html.resolve().as_uri(), timeout=60000)
            page.wait_for_function('typeof DATA !== "undefined" && DATA.lot_trace && document.querySelector(".js-plotly-plot")', timeout=60000)
            print('Page loaded; fingerprinting physical data in bounded chunks.', flush=True)
            before = physical_fingerprint(page)
            print('Physical fingerprint complete.', flush=True)
            page.locator("#modeOps").click()
            page.locator("#lotTraceOpenBtn").click()
            page.locator("#lotTraceModalSelect").select_option("LOT-00002658")
            page.locator('#lotTraceModal [data-lot-trace-direction="both"]').click()
            article = page.locator('[data-material-article="item:338929"]')
            article.locator("summary").click()
            quantities = article.locator("[data-material-consumed]").evaluate_all("nodes => nodes.map(n => Number(n.dataset.materialConsumed)).sort((a,b)=>a-b)")
            check("four_receipts_consumed_quantities", quantities == [2000, 2400, 5000, 5000], quantities=quantities)
            check("unknown_origins_not_fabricated", article.inner_text().count("Lot fournisseur inconnu") == 4)
            check("containers_not_invented", article.inner_text().count("Contenants non renseignés") == 4)
            check("truck_estimate_label", article.inner_text().count("camion(s) estimé(s)") == 4)
            article.scroll_into_view_if_needed()
            page.screenshot(path=str(output / "receipts-338929.png"))
            page.locator(f'[data-material-target="{receipt["event_id"]}"]').click()
            panel = page.locator('.lotTraceMaterialIncidents')
            actual = dict(potential_production_lot_ids=json.loads(panel.get_attribute('data-production-lots')),
                          potential_lot_ids=json.loads(panel.get_attribute('data-potential-lots')))
            check("recall_matches_independent_csv", actual["potential_production_lot_ids"] == expected_outputs
                  and sorted(actual["potential_lot_ids"]) == sorted(reached), expected_outputs=expected_outputs,
                  actual_outputs=actual["potential_production_lot_ids"])
            check("selected_root_marked", page.locator('.lotTraceGraphNode.root.materialExposed').count() == 1)
            panel_text = page.locator(".lotTraceMaterialIncidents").inner_text()
            check("hypothesis_and_no_replay_visible", "Exploration hypothétique" in panel_text and "restent inchangés" in panel_text)
            page.screenshot(path=str(output / "recall-receipt.png"))
            other = next(id for id in expected_outputs if id != "LOT-00002658")
            page.locator('[data-material-affected-select]').select_option(other)
            check("navigate_affected_lot", page.locator('#lotTraceModalSelect').input_value() == other
                  and page.locator('#lotTraceSelect').input_value() == other)
            unrelated = page.evaluate("ids => Object.values(DATA.lot_trace.lots).find(l=>l.created_event_type==='production_output' && !ids.includes(l.lot_id)).lot_id", actual['potential_lot_ids'])
            page.locator('#lotTraceModalSelect').select_option(unrelated)
            check("unrelated_lot_excluded", "hors de ce périmètre" in page.locator('.lotTraceMaterialIncidents').inner_text()
                  and page.locator('.lotTraceGraphNode.root.materialExposed').count() == 0)
            page.locator('[data-material-clear]').click()
            check("reset_exploration", panel.get_attribute('data-preview-active') == 'false' and page.locator('.materialIncidentCard').count() == 0)
            after = physical_fingerprint(page)
            check("physical_payload_unchanged", before == after)
            # Two hypothetical receipt mappings in browser memory only. Never
            # written into the delivered nominal HTML or its input data.
            page.evaluate("""() => {
              const context=DATA.lot_trace.material_traceability;
              const chosen=Object.values(context.receipts).filter(r=>['SHIP-00000203','SHIP-00000251'].includes(r.shipment_id));
              context.origins['TEST-SUPPLIER-LOT']={id:'TEST-SUPPLIER-LOT', batch_number:'TEST ONLY', manufacturer_id:'TEST', status:'simulated',source_reference:'browser-test'};
              chosen.forEach(r=>r.origins=[{origin_id:'TEST-SUPPLIER-LOT', quantity:r.quantity}]);
            }""")
            page.locator('#lotTraceModalSelect').select_option('LOT-00002658')
            page.locator('[data-material-article="item:338929"] summary').click()
            page.locator('[data-material-preview="supplier_lot"]').first.click()
            check("supplier_lot_groups_receipts_only_when_explicit", len(json.loads(panel.get_attribute('data-receipt-ids'))) == 2)
        except Exception as exc:
            check("browser_execution", False, error=str(exc))
        finally:
            browser.close()
    report["ok"] = bool(report["checks"]) and all(c["ok"] for c in report["checks"]) and not report["javascript_errors"]
    (output / "material-browser.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("html", "data", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    result = review(args.html, args.data, args.output)
    print(json.dumps(result, ensure_ascii=True))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
