#!/usr/bin/env python3
"""Build a static HTML viewer for simulation lot traces."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a static lot-trace viewer from simulation CSV outputs.")
    parser.add_argument(
        "--output-root",
        default="etudecas/simulation/result",
        help="Simulation output root containing data/production_lot_*.csv.",
    )
    parser.add_argument(
        "--output",
        default="",
        help="Output HTML path. Defaults to reports/lot_trace_viewer.html.",
    )
    parser.add_argument(
        "--max-events",
        type=int,
        default=0,
        help="Optional cap on loaded event rows. 0 keeps all rows.",
    )
    parser.add_argument(
        "--max-genealogy",
        type=int,
        default=0,
        help="Optional cap on loaded genealogy rows. 0 keeps all rows.",
    )
    return parser.parse_args()


def read_csv(path: Path, max_rows: int = 0) -> list[dict[str, str]]:
    if not path.exists():
        return []
    rows: list[dict[str, str]] = []
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            rows.append(dict(row))
            if max_rows > 0 and len(rows) >= max_rows:
                break
    return rows


def to_float(value: Any) -> float:
    try:
        return float(str(value).replace(",", "."))
    except (TypeError, ValueError):
        return 0.0


def lot_creation_rows(events: list[dict[str, str]]) -> dict[str, dict[str, str]]:
    preferred = {
        "opening_stock",
        "lane_receipt",
        "external_procurement_receipt",
        "estimated_source_receipt",
        "estimated_capacity_receipt",
        "production_output",
    }
    lots: dict[str, dict[str, str]] = {}
    for row in events:
        lot_id = str(row.get("lot_id") or "")
        if not lot_id:
            continue
        if lot_id not in lots or row.get("event_type") in preferred:
            lots[lot_id] = row
    return lots


def build_payload(output_root: Path, max_events: int, max_genealogy: int) -> dict[str, Any]:
    data_dir = output_root / "data"
    events = read_csv(data_dir / "production_lot_events.csv", max_events)
    genealogy = read_csv(data_dir / "production_lot_genealogy.csv", max_genealogy)
    plan_events = read_csv(data_dir / "production_plan_events.csv")
    lots = lot_creation_rows(events)

    item_counts: dict[str, int] = {}
    event_counts: dict[str, int] = {}
    link_counts: dict[str, int] = {}
    for row in events:
        item = str(row.get("item_id") or "")
        event_type = str(row.get("event_type") or "")
        if item:
            item_counts[item] = item_counts.get(item, 0) + 1
        if event_type:
            event_counts[event_type] = event_counts.get(event_type, 0) + 1
    for row in genealogy:
        link_type = str(row.get("link_type") or "")
        if link_type:
            link_counts[link_type] = link_counts.get(link_type, 0) + 1

    default_lot = ""
    for lot_id, row in lots.items():
        if row.get("event_type") == "production_output":
            default_lot = lot_id
            break
    if not default_lot and lots:
        default_lot = sorted(lots)[0]

    return {
        "output_root": str(output_root),
        "events": events,
        "genealogy": genealogy,
        "plan_events": plan_events,
        "lots": lots,
        "default_lot": default_lot,
        "summary": {
            "event_rows": len(events),
            "genealogy_rows": len(genealogy),
            "plan_event_rows": len(plan_events),
            "lot_count": len(lots),
            "item_counts": item_counts,
            "event_counts": event_counts,
            "link_counts": link_counts,
        },
    }


def script_json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=True, separators=(",", ":")).replace("</", "<\\/")


HTML_TEMPLATE = """<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Lot Trace Viewer</title>
<style>
:root {{
  --bg: #f7f8fa;
  --panel: #ffffff;
  --text: #17202a;
  --muted: #5d6976;
  --border: #d7dde5;
  --blue: #2f6fb1;
  --green: #2f855a;
  --amber: #a16207;
  --red: #b42318;
  --violet: #6d5bd0;
}}
* {{ box-sizing: border-box; }}
body {{
  margin: 0;
  background: var(--bg);
  color: var(--text);
  font: 13px/1.45 "Segoe UI", Arial, sans-serif;
}}
button, input, select {{
  font: inherit;
}}
.app {{
  min-height: 100vh;
  display: grid;
  grid-template-columns: minmax(280px, 360px) minmax(0, 1fr);
}}
.sidebar {{
  background: var(--panel);
  border-right: 1px solid var(--border);
  padding: 14px;
  display: grid;
  grid-template-rows: auto auto auto minmax(0, 1fr);
  gap: 12px;
  min-height: 100vh;
}}
.main {{
  min-width: 0;
  display: grid;
  grid-template-rows: auto minmax(360px, 1fr) auto;
  gap: 12px;
  padding: 14px;
}}
.topbar {{
  display: grid;
  grid-template-columns: repeat(4, minmax(120px, 1fr));
  gap: 8px;
}}
.metric {{
  background: var(--panel);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 10px 12px;
}}
.metric b {{
  display: block;
  font-size: 18px;
  line-height: 1.1;
}}
.metric span {{ color: var(--muted); }}
.field {{
  display: grid;
  gap: 4px;
}}
.field label {{
  color: var(--muted);
  font-size: 12px;
}}
.field input, .field select {{
  width: 100%;
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 8px 9px;
  background: #fff;
  min-width: 0;
}}
.segmented {{
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  border: 1px solid var(--border);
  border-radius: 6px;
  overflow: hidden;
}}
.segmented button {{
  border: 0;
  border-right: 1px solid var(--border);
  background: #fff;
  padding: 8px 6px;
  color: var(--muted);
  cursor: pointer;
}}
.segmented button:last-child {{ border-right: 0; }}
.segmented button.active {{
  background: #eaf2fb;
  color: var(--blue);
  font-weight: 600;
}}
.lot-list {{
  overflow: auto;
  border: 1px solid var(--border);
  border-radius: 8px;
}}
.lot-row {{
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 8px;
  width: 100%;
  border: 0;
  border-bottom: 1px solid var(--border);
  background: #fff;
  padding: 8px 9px;
  text-align: left;
  cursor: pointer;
}}
.lot-row:last-child {{ border-bottom: 0; }}
.lot-row.active {{ background: #f0f7f2; }}
.lot-row strong {{
  display: block;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}}
.lot-row span {{
  color: var(--muted);
  font-size: 12px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}}
.pill {{
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 74px;
  height: 22px;
  border-radius: 999px;
  padding: 0 8px;
  color: #fff;
  background: var(--muted);
  font-size: 11px;
}}
.pill.production_output {{ background: var(--green); }}
.pill.opening_stock {{ background: var(--violet); }}
.pill.lane_receipt {{ background: var(--blue); }}
.pill.external_procurement_receipt {{ background: var(--amber); }}
.graph-wrap, .table-wrap {{
  background: var(--panel);
  border: 1px solid var(--border);
  border-radius: 8px;
  min-width: 0;
}}
.graph-wrap {{
  overflow: hidden;
  position: relative;
}}
.graph-header {{
  position: absolute;
  z-index: 2;
  top: 10px;
  left: 12px;
  right: 12px;
  display: flex;
  align-items: center;
  gap: 8px;
  pointer-events: none;
}}
.graph-header h1 {{
  margin: 0;
  font-size: 15px;
  font-weight: 700;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}}
.graph-header span {{
  color: var(--muted);
  white-space: nowrap;
}}
svg {{
  display: block;
  width: 100%;
  height: 100%;
  min-height: 430px;
}}
.edge {{
  fill: none;
  stroke: #9aa7b5;
  stroke-width: 1.4;
}}
.edge.production {{ stroke: var(--green); }}
.edge.transport {{ stroke: var(--blue); stroke-dasharray: 5 3; }}
.node rect {{
  fill: #fff;
  stroke: var(--border);
  stroke-width: 1.2;
  rx: 8;
}}
.node.production_output rect {{ stroke: var(--green); }}
.node.opening_stock rect {{ stroke: var(--violet); }}
.node.lane_receipt rect {{ stroke: var(--blue); }}
.node.external_procurement_receipt rect {{ stroke: var(--amber); }}
.node text {{ pointer-events: none; }}
.node .title {{ font-weight: 700; font-size: 12px; }}
.node .sub {{ fill: var(--muted); font-size: 11px; }}
.node.selected rect {{
  stroke: var(--red);
  stroke-width: 2;
}}
.bottom {{
  display: grid;
  grid-template-columns: minmax(0, 1.2fr) minmax(0, 1fr);
  gap: 12px;
}}
.table-wrap {{
  min-height: 220px;
  overflow: auto;
}}
.table-title {{
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 12px;
  border-bottom: 1px solid var(--border);
  font-weight: 700;
}}
table {{
  width: 100%;
  border-collapse: collapse;
}}
th, td {{
  padding: 7px 9px;
  border-bottom: 1px solid var(--border);
  text-align: left;
  vertical-align: top;
  white-space: nowrap;
}}
th {{
  color: var(--muted);
  font-weight: 600;
  background: #fbfcfd;
  position: sticky;
  top: 0;
  z-index: 1;
}}
td.wrap {{
  white-space: normal;
  min-width: 160px;
}}
.empty {{
  padding: 24px;
  color: var(--muted);
}}
@media (max-width: 920px) {{
  .app {{
    grid-template-columns: 1fr;
  }}
  .sidebar {{
    min-height: auto;
  }}
  .topbar, .bottom {{
    grid-template-columns: 1fr;
  }}
}}
</style>
</head>
<body>
<div class="app">
  <aside class="sidebar">
    <div class="field">
      <label for="lotSearch">Lot</label>
      <input id="lotSearch" type="search" autocomplete="off" placeholder="LOT-00000095, item:268967, M-1430">
    </div>
    <div class="field">
      <label for="eventFilter">Type</label>
      <select id="eventFilter"></select>
    </div>
    <div class="field">
      <label>Trace</label>
      <div class="segmented">
        <button id="dirAncestors" type="button" data-dir="ancestors">Amont</button>
        <button id="dirBoth" type="button" data-dir="both">Tout</button>
        <button id="dirDescendants" type="button" data-dir="descendants">Aval</button>
      </div>
    </div>
    <div id="lotList" class="lot-list"></div>
  </aside>
  <main class="main">
    <section class="topbar">
      <div class="metric"><b id="metricLots">0</b><span>lots</span></div>
      <div class="metric"><b id="metricEvents">0</b><span>evenements</span></div>
      <div class="metric"><b id="metricLinks">0</b><span>liens genealogie</span></div>
      <div class="metric"><b id="metricPlan">0</b><span>evenements plan</span></div>
    </section>
    <section class="graph-wrap">
      <div class="graph-header">
        <h1 id="selectedTitle"></h1>
        <span id="selectedMeta"></span>
      </div>
      <svg id="graph" role="img" aria-label="Lot genealogy graph"></svg>
    </section>
    <section class="bottom">
      <div class="table-wrap">
        <div class="table-title"><span>Evenements du lot</span><span id="timelineCount"></span></div>
        <div id="timelineTable"></div>
      </div>
      <div class="table-wrap">
        <div class="table-title"><span>Planification liee</span><span id="planCount"></span></div>
        <div id="planTable"></div>
      </div>
    </section>
  </main>
</div>
<script id="payload" type="application/json">{payload_json}</script>
<script>
const DATA = JSON.parse(document.getElementById('payload').textContent);
const events = DATA.events || [];
const genealogy = DATA.genealogy || [];
const lots = DATA.lots || {{}};
const planEvents = DATA.plan_events || [];
const byLotEvents = new Map();
const parentByChild = new Map();
const childByParent = new Map();
let selectedLotId = DATA.default_lot || '';
let direction = 'both';

for (const row of events) {{
  const lotId = row.lot_id || '';
  if (!lotId) continue;
  if (!byLotEvents.has(lotId)) byLotEvents.set(lotId, []);
  byLotEvents.get(lotId).push(row);
}}
for (const row of genealogy) {{
  const child = row.child_lot_id || '';
  const parent = row.parent_lot_id || '';
  if (child) {{
    if (!parentByChild.has(child)) parentByChild.set(child, []);
    parentByChild.get(child).push(row);
  }}
  if (parent) {{
    if (!childByParent.has(parent)) childByParent.set(parent, []);
    childByParent.get(parent).push(row);
  }}
}}

const fmt = new Intl.NumberFormat('fr-FR', {{ maximumFractionDigits: 3 }});
function num(v) {{
  const n = Number(String(v || '0').replace(',', '.'));
  return Number.isFinite(n) ? n : 0;
}}
function esc(s) {{
  return String(s ?? '').replace(/[&<>"']/g, c => ({{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}}[c]));
}}
function lotRow(lotId) {{
  return lots[lotId] || (byLotEvents.get(lotId) || [{{lot_id: lotId}}])[0] || {{lot_id: lotId}};
}}
function eventClass(row) {{
  return String(row.event_type || '').replace(/[^a-zA-Z0-9_-]/g, '_');
}}
function lotLabel(lotId) {{
  const row = lotRow(lotId);
  return `${{lotId}} | ${{row.node_id || ''}} | ${{row.item_id || ''}}`;
}}

function setMetrics() {{
  document.getElementById('metricLots').textContent = fmt.format(DATA.summary?.lot_count || 0);
  document.getElementById('metricEvents').textContent = fmt.format(DATA.summary?.event_rows || 0);
  document.getElementById('metricLinks').textContent = fmt.format(DATA.summary?.genealogy_rows || 0);
  document.getElementById('metricPlan').textContent = fmt.format(DATA.summary?.plan_event_rows || 0);
}}

function populateFilters() {{
  const sel = document.getElementById('eventFilter');
  const types = Array.from(new Set(Object.values(lots).map(row => row.event_type || '').filter(Boolean))).sort();
  sel.innerHTML = `<option value="">Tous</option>` + types.map(t => `<option value="${{esc(t)}}">${{esc(t)}}</option>`).join('');
}}

function filteredLots() {{
  const q = document.getElementById('lotSearch').value.trim().toLowerCase();
  const type = document.getElementById('eventFilter').value;
  return Object.entries(lots).filter(([lotId, row]) => {{
    if (type && row.event_type !== type) return false;
    if (!q) return true;
    return `${{lotId}} ${{row.node_id || ''}} ${{row.item_id || ''}} ${{row.event_type || ''}} ${{row.source_id || ''}}`.toLowerCase().includes(q);
  }}).sort((a, b) => {{
    const da = num(a[1].day), db = num(b[1].day);
    if (da !== db) return da - db;
    return a[0].localeCompare(b[0]);
  }}).slice(0, 240);
}}

function renderLotList() {{
  const box = document.getElementById('lotList');
  const rows = filteredLots();
  if (!rows.length) {{
    box.innerHTML = `<div class="empty">Aucun lot</div>`;
    return;
  }}
  box.innerHTML = rows.map(([lotId, row]) => `
    <button class="lot-row ${{lotId === selectedLotId ? 'active' : ''}}" data-lot="${{esc(lotId)}}" type="button">
      <span><strong>${{esc(lotId)}}</strong><span>${{esc(row.node_id || '')}} | ${{esc(row.item_id || '')}} | J${{esc(row.day || '')}}</span></span>
      <em class="pill ${{esc(eventClass(row))}}">${{esc(row.event_type || '')}}</em>
    </button>
  `).join('');
  for (const btn of box.querySelectorAll('.lot-row')) {{
    btn.addEventListener('click', () => selectLot(btn.dataset.lot));
  }}
}}

function traceGraph(rootLotId) {{
  const nodes = [];
  const edges = [];
  const seen = new Set();
  const queue = [{{lotId: rootLotId, depth: 0, side: 'root', via: null}}];
  while (queue.length) {{
    const cur = queue.shift();
    if (seen.has(cur.lotId)) continue;
    seen.add(cur.lotId);
    nodes.push(cur);
    if (cur.depth >= 5) continue;
    if (direction === 'ancestors' || direction === 'both') {{
      for (const edge of parentByChild.get(cur.lotId) || []) {{
        const parent = edge.parent_lot_id;
        if (!parent || seen.has(parent)) continue;
        edges.push({{from: parent, to: cur.lotId, type: edge.link_type || '', row: edge}});
        queue.push({{lotId: parent, depth: cur.depth + 1, side: 'ancestor', via: edge}});
      }}
    }}
    if (direction === 'descendants' || direction === 'both') {{
      for (const edge of childByParent.get(cur.lotId) || []) {{
        const child = edge.child_lot_id;
        if (!child || seen.has(child)) continue;
        edges.push({{from: cur.lotId, to: child, type: edge.link_type || '', row: edge}});
        queue.push({{lotId: child, depth: cur.depth + 1, side: 'descendant', via: edge}});
      }}
    }}
  }}
  return {{nodes, edges}};
}}

function layoutTrace(trace, width, height) {{
  const columns = new Map();
  for (const n of trace.nodes) {{
    const xKey = n.side === 'ancestor' ? -n.depth : n.side === 'descendant' ? n.depth : 0;
    if (!columns.has(xKey)) columns.set(xKey, []);
    columns.get(xKey).push(n);
    n.xKey = xKey;
  }}
  const keys = Array.from(columns.keys()).sort((a, b) => a - b);
  const colGap = keys.length > 1 ? (width - 220) / (keys.length - 1) : 0;
  const pos = new Map();
  keys.forEach((key, idx) => {{
    const col = columns.get(key);
    const yGap = height / (col.length + 1);
    col.forEach((n, j) => {{
      n.x = keys.length > 1 ? 110 + idx * colGap : width / 2;
      n.y = Math.max(72, (j + 1) * yGap);
      pos.set(n.lotId, n);
    }});
  }});
  return pos;
}}

function renderGraph() {{
  const svg = document.getElementById('graph');
  const root = lotRow(selectedLotId);
  document.getElementById('selectedTitle').textContent = lotLabel(selectedLotId);
  document.getElementById('selectedMeta').textContent = `${{root.event_type || ''}} | qty ${{fmt.format(num(root.qty))}} | J${{root.day || ''}}`;
  const rect = svg.getBoundingClientRect();
  const width = Math.max(720, rect.width || 900);
  const height = Math.max(430, rect.height || 500);
  const trace = traceGraph(selectedLotId);
  const pos = layoutTrace(trace, width, height);
  const edgeMarkup = trace.edges.map(e => {{
    const a = pos.get(e.from), b = pos.get(e.to);
    if (!a || !b) return '';
    const mid = (a.x + b.x) / 2;
    return `<path class="edge ${{esc(e.type)}}" d="M ${{a.x}} ${{a.y}} C ${{mid}} ${{a.y}}, ${{mid}} ${{b.y}}, ${{b.x}} ${{b.y}}" />`;
  }}).join('');
  const nodeMarkup = trace.nodes.map(n => {{
    const row = lotRow(n.lotId);
    const cls = eventClass(row);
    const item = row.item_id || '';
    const qty = fmt.format(num(row.qty));
    return `<g class="node ${{esc(cls)}} ${{n.lotId === selectedLotId ? 'selected' : ''}}" data-lot="${{esc(n.lotId)}}" transform="translate(${{n.x - 82}},${{n.y - 28}})">
      <rect width="164" height="56"></rect>
      <text class="title" x="10" y="19">${{esc(n.lotId)}}</text>
      <text class="sub" x="10" y="35">${{esc(row.node_id || '')}} | ${{esc(item)}}</text>
      <text class="sub" x="10" y="49">${{esc(row.event_type || '')}} | ${{qty}}</text>
    </g>`;
  }}).join('');
  svg.setAttribute('viewBox', `0 0 ${{width}} ${{height}}`);
  svg.innerHTML = `<g>${{edgeMarkup}}</g><g>${{nodeMarkup}}</g>`;
  for (const node of svg.querySelectorAll('.node')) {{
    node.addEventListener('click', () => selectLot(node.dataset.lot));
  }}
}}

function renderTable(containerId, rows, columns) {{
  const container = document.getElementById(containerId);
  if (!rows.length) {{
    container.innerHTML = `<div class="empty">Aucune ligne</div>`;
    return;
  }}
  container.innerHTML = `<table><thead><tr>${{columns.map(c => `<th>${{esc(c.label)}}</th>`).join('')}}</tr></thead><tbody>${
    rows.map(row => `<tr>${{columns.map(c => `<td class="${{c.wrap ? 'wrap' : ''}}">${{esc(c.format ? c.format(row[c.key], row) : row[c.key] || '')}}</td>`).join('')}}</tr>`).join('')
  }}</tbody></table>`;
}}

function renderTimeline() {{
  const rows = (byLotEvents.get(selectedLotId) || []).slice().sort((a, b) => num(a.day) - num(b.day));
  document.getElementById('timelineCount').textContent = fmt.format(rows.length);
  renderTable('timelineTable', rows, [
    {{key:'day', label:'Jour'}},
    {{key:'event_type', label:'Evenement'}},
    {{key:'node_id', label:'Noeud'}},
    {{key:'item_id', label:'Item'}},
    {{key:'qty', label:'Qte', format:v => fmt.format(num(v))}},
    {{key:'qty_after', label:'Solde', format:v => fmt.format(num(v))}},
    {{key:'source_id', label:'Source', wrap:true}},
  ]);
}}

function renderPlan() {{
  const lotEvents = byLotEvents.get(selectedLotId) || [];
  const campaigns = new Set(lotEvents.map(r => r.production_campaign_id).filter(Boolean));
  for (const g of genealogy) {{
    if (g.parent_lot_id === selectedLotId || g.child_lot_id === selectedLotId) {{
      if (g.production_campaign_id) campaigns.add(g.production_campaign_id);
    }}
  }}
  const rows = planEvents.filter(r => campaigns.has(r.campaign_id)).sort((a, b) => num(a.day) - num(b.day));
  document.getElementById('planCount').textContent = fmt.format(rows.length);
  renderTable('planTable', rows, [
    {{key:'day', label:'Jour'}},
    {{key:'event_type', label:'Evenement'}},
    {{key:'reason', label:'Cause'}},
    {{key:'output_item_id', label:'Sortie'}},
    {{key:'binding_input_item_id', label:'Intrant'}},
    {{key:'actual_qty', label:'Reel', format:v => fmt.format(num(v))}},
    {{key:'planned_qty_after_lot_rule', label:'Plan lot', format:v => fmt.format(num(v))}},
    {{key:'next_expected_receipt_day', label:'Prochaine reception'}},
  ]);
}}

function selectLot(lotId) {{
  if (!lotId || !lots[lotId]) return;
  selectedLotId = lotId;
  renderLotList();
  renderGraph();
  renderTimeline();
  renderPlan();
}}

function setDirection(next) {{
  direction = next;
  for (const btn of document.querySelectorAll('.segmented button')) {{
    btn.classList.toggle('active', btn.dataset.dir === direction);
  }}
  renderGraph();
}}

document.getElementById('lotSearch').addEventListener('input', renderLotList);
document.getElementById('eventFilter').addEventListener('change', renderLotList);
for (const btn of document.querySelectorAll('.segmented button')) {{
  btn.addEventListener('click', () => setDirection(btn.dataset.dir));
}}
window.addEventListener('resize', () => renderGraph());

setMetrics();
populateFilters();
setDirection('both');
renderLotList();
selectLot(selectedLotId);
</script>
</body>
</html>
"""


def main() -> None:
    args = parse_args()
    output_root = Path(args.output_root)
    payload = build_payload(output_root, max(0, int(args.max_events)), max(0, int(args.max_genealogy)))
    out_path = Path(args.output) if args.output else output_root / "reports" / "lot_trace_viewer.html"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    html = HTML_TEMPLATE.replace("{{", "{").replace("}}", "}")
    out_path.write_text(html.replace("{payload_json}", script_json(payload)), encoding="utf-8")
    print(f"[OK] Lot trace viewer HTML: {out_path.resolve()}")
    print(
        "[OK] Loaded "
        f"{payload['summary']['lot_count']} lots, "
        f"{payload['summary']['event_rows']} events, "
        f"{payload['summary']['genealogy_rows']} genealogy rows."
    )


if __name__ == "__main__":
    main()
