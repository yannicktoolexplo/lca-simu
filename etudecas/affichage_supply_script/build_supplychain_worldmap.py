#!/usr/bin/env python3
"""
Build an interactive HTML world map from a geocoded supply graph.

Includes hover overlays for factory nodes using simulation outputs:
- incoming input-stock time series
- outgoing production time series
"""

from __future__ import annotations

import argparse
import csv
import html
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

NODE_TYPE_STYLES = {
    "supplier_dc": {"name": "Supplier DC", "color": "#1f77b4", "symbol": "circle"},
    "factory": {"name": "Factory", "color": "#d62728", "symbol": "square"},
    "distribution_center": {"name": "Distribution Center", "color": "#ff7f0e", "symbol": "diamond"},
    "customer": {"name": "Customer", "color": "#2ca02c", "symbol": "star"},
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--input",
        "-i",
        default="etudecas/simulation_prep/result/supply_graph_poc_simulation_ready.json",
        help="Input geocoded supply graph JSON.",
    )
    parser.add_argument(
        "--output",
        "-o",
        default="etudecas/simulation/result/supply_graph_poc_geocoded_map_with_factory_hover.html",
        help="Output HTML file.",
    )
    parser.add_argument(
        "--title",
        default="Supply Graph POC - Geocoded Map",
        help="HTML page title.",
    )
    parser.add_argument(
        "--sim-input-stocks-csv",
        default="etudecas/simulation/result/production_input_stocks_daily.csv",
        help="Simulation CSV for input material stocks.",
    )
    parser.add_argument(
        "--sim-output-products-csv",
        default="etudecas/simulation/result/production_output_products_daily.csv",
        help="Simulation CSV for output products production.",
    )
    return parser.parse_args()


def to_float(x: Any) -> float | None:
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def compact_graph_payload(raw: dict[str, Any]) -> dict[str, Any]:
    nodes_in = raw.get("nodes", [])
    edges_in = raw.get("edges", [])
    if not isinstance(nodes_in, list) or not isinstance(edges_in, list):
        raise ValueError("Expected JSON with list fields: nodes and edges.")

    nodes: list[dict[str, Any]] = []
    for node in nodes_in:
        if not isinstance(node, dict):
            continue
        geo = node.get("geo", {}) or {}
        lat = geo.get("lat")
        lon = geo.get("lon")
        try:
            lat = float(lat) if lat is not None else None
            lon = float(lon) if lon is not None else None
        except (TypeError, ValueError):
            lat = None
            lon = None
        nodes.append(
            {
                "id": node.get("id"),
                "type": node.get("type", "unknown"),
                "name": node.get("name", ""),
                "location_ID": node.get("location_ID"),
                "country": geo.get("country"),
                "lat": lat,
                "lon": lon,
            }
        )

    edges: list[dict[str, Any]] = []
    for edge in edges_in:
        if not isinstance(edge, dict):
            continue
        items = edge.get("items", [])
        if not isinstance(items, list):
            items = []
        edges.append(
            {
                "id": edge.get("id"),
                "type": edge.get("type", "unknown"),
                "from": edge.get("from"),
                "to": edge.get("to"),
                "items": items,
            }
        )

    node_types = sorted({n.get("type", "unknown") for n in nodes})
    return {
        "schema_version": raw.get("schema_version"),
        "meta": raw.get("meta", {}),
        "nodes": nodes,
        "edges": edges,
        "node_types": node_types,
        "node_type_styles": NODE_TYPE_STYLES,
    }


def build_factory_hover_series(
    raw: dict[str, Any],
    sim_input_stocks_csv: Path,
    sim_output_products_csv: Path,
) -> dict[str, Any]:
    nodes = raw.get("nodes", []) or []
    items = raw.get("items", []) or []

    factory_ids = {
        str(n.get("id"))
        for n in nodes
        if str(n.get("type") or "") == "factory"
    }
    node_name = {str(n.get("id")): str(n.get("name") or str(n.get("id"))) for n in nodes}

    item_label: dict[str, str] = {}
    for it in items:
        iid = str(it.get("id"))
        code = str(it.get("code") or "").strip()
        name = str(it.get("name") or "").strip()
        item_label[iid] = code if code else (name if name else iid)

    in_unit_by_node_item: dict[tuple[str, str], str] = {}
    out_unit_by_node_item: dict[tuple[str, str], str] = {}
    for n in nodes:
        nid = str(n.get("id"))
        inv = n.get("inventory") or {}
        for st in (inv.get("states") or []):
            item_id = str(st.get("item_id"))
            uom = str(st.get("uom") or "").strip()
            if item_id and uom:
                in_unit_by_node_item[(nid, item_id)] = uom
        for p in (n.get("processes") or []):
            for inp in (p.get("inputs") or []):
                item_id = str(inp.get("item_id"))
                uom = str(inp.get("ratio_unit") or "").strip()
                if item_id and uom and (nid, item_id) not in in_unit_by_node_item:
                    in_unit_by_node_item[(nid, item_id)] = uom
            for out in (p.get("outputs") or []):
                item_id = str(out.get("item_id"))
                uom = str(out.get("uom") or "").strip()
                if item_id and uom:
                    out_unit_by_node_item[(nid, item_id)] = uom

    incoming_raw: dict[str, dict[str, list[tuple[int, float]]]] = defaultdict(lambda: defaultdict(list))
    if sim_input_stocks_csv.exists():
        with sim_input_stocks_csv.open("r", encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                node_id = str(row.get("node_id") or "")
                if node_id not in factory_ids:
                    continue
                item_id = str(row.get("item_id") or "")
                day = int(to_float(row.get("day")) or 0)
                val = to_float(row.get("stock_end_of_day"))
                if val is None:
                    val = to_float(row.get("stock_before_production")) or 0.0
                incoming_raw[node_id][item_id].append((day, val))

    outgoing_raw: dict[str, dict[str, list[tuple[int, float, float]]]] = defaultdict(lambda: defaultdict(list))
    if sim_output_products_csv.exists():
        with sim_output_products_csv.open("r", encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                node_id = str(row.get("node_id") or "")
                if node_id not in factory_ids:
                    continue
                item_id = str(row.get("item_id") or "")
                day = int(to_float(row.get("day")) or 0)
                prod = float(to_float(row.get("produced_qty")) or 0.0)
                cum = float(to_float(row.get("cum_produced_qty")) or 0.0)
                outgoing_raw[node_id][item_id].append((day, prod, cum))

    out: dict[str, Any] = {}
    for node_id in sorted(factory_ids):
        incoming = []
        for item_id, pts in sorted(incoming_raw[node_id].items(), key=lambda x: item_label.get(x[0], x[0])):
            pts_sorted = sorted(pts, key=lambda x: x[0])
            incoming.append(
                {
                    "item_id": item_id,
                    "item_label": item_label.get(item_id, item_id),
                    "unit": in_unit_by_node_item.get((node_id, item_id), ""),
                    "days": [p[0] for p in pts_sorted],
                    "values": [p[1] for p in pts_sorted],
                }
            )

        outgoing = []
        for item_id, pts in sorted(outgoing_raw[node_id].items(), key=lambda x: item_label.get(x[0], x[0])):
            pts_sorted = sorted(pts, key=lambda x: x[0])
            outgoing.append(
                {
                    "item_id": item_id,
                    "item_label": item_label.get(item_id, item_id),
                    "unit": out_unit_by_node_item.get((node_id, item_id), "unit/day"),
                    "days": [p[0] for p in pts_sorted],
                    "values": [p[1] for p in pts_sorted],
                    "cum_values": [p[2] for p in pts_sorted],
                }
            )

        if incoming or outgoing:
            out[node_id] = {
                "node_id": node_id,
                "node_name": node_name.get(node_id, node_id),
                "incoming": incoming,
                "outgoing": outgoing,
            }

    return out


def html_template(title: str, data_json: str) -> str:
    return f"""<!doctype html>
<html>
<head>
  <meta charset="utf-8"/>
  <title>{html.escape(title)}</title>
  <script src="https://cdn.plot.ly/plotly-2.32.0.min.js"></script>
  <style>
    body {{
      margin: 0;
      font-family: system-ui, -apple-system, Segoe UI, Roboto, Arial, sans-serif;
      color: #0f172a;
      background: #f8fafc;
    }}
    .toolbar {{
      display: flex;
      flex-wrap: wrap;
      gap: 12px;
      align-items: center;
      padding: 12px 16px;
      border-bottom: 1px solid #e2e8f0;
      background: #ffffff;
      position: sticky;
      top: 0;
      z-index: 10;
    }}
    .title {{
      font-weight: 700;
      font-size: 14px;
      margin-right: 8px;
    }}
    .meta {{
      font-size: 12px;
      color: #475569;
      margin-right: 14px;
    }}
    .box {{
      display: flex;
      align-items: center;
      gap: 8px;
    }}
    #typeFilters label {{
      margin-right: 8px;
      font-size: 12px;
      white-space: nowrap;
    }}
    #chart {{
      width: 100%;
      height: calc(100vh - 64px);
    }}
    #factoryHoverPanel {{
      position: fixed;
      right: 16px;
      top: 88px;
      width: min(760px, calc(100vw - 32px));
      max-height: calc(100vh - 110px);
      background: rgba(255,255,255,0.98);
      border: 1px solid #cbd5e1;
      border-radius: 12px;
      box-shadow: 0 10px 30px rgba(15, 23, 42, 0.18);
      z-index: 20;
      overflow: hidden;
      display: none;
      padding: 10px;
    }}
    #factoryHoverPanel.visible {{
      display: block;
    }}
    #factoryHoverTitle {{
      font-size: 13px;
      font-weight: 700;
      margin: 0 0 8px 0;
      color: #0f172a;
    }}
    .factoryHoverGrid {{
      display: grid;
      grid-template-columns: 1fr;
      gap: 10px;
    }}
    .factoryPlot {{
      height: clamp(160px, calc((100vh - 210px) / 2), 260px);
      border: 1px solid #e2e8f0;
      border-radius: 8px;
    }}
  </style>
</head>
<body>
  <div class="toolbar">
    <div class="title">{html.escape(title)}</div>
    <div class="meta" id="stats"></div>
    <div class="box">
      <label><input type="checkbox" id="showEdges" checked> Afficher flux</label>
    </div>
    <div class="box" id="typeFilters"></div>
  </div>
  <div id="chart"></div>

  <div id="factoryHoverPanel">
    <div id="factoryHoverTitle"></div>
    <div class="factoryHoverGrid">
      <div id="factoryIncomingChart" class="factoryPlot"></div>
      <div id="factoryOutgoingChart" class="factoryPlot"></div>
    </div>
  </div>

  <script>
    const DATA = {data_json};
    const STYLES = DATA.node_type_styles || {{}};
    const FACTORY_SERIES = DATA.factory_hover_series || {{}};
    const nodeById = Object.fromEntries((DATA.nodes || []).map(n => [n.id, n]));
    const defaultPalette = ["#1f77b4", "#d62728", "#ff7f0e", "#2ca02c", "#9467bd", "#8c564b"];
    let currentFactoryHoverId = null;
    let hoverHandlersBound = false;

    function styleForType(nodeType, idx) {{
      const s = STYLES[nodeType] || {{}};
      return {{
        name: s.name || nodeType,
        color: s.color || defaultPalette[idx % defaultPalette.length],
        symbol: s.symbol || "circle",
      }};
    }}

    function initFilters() {{
      const container = document.getElementById("typeFilters");
      container.innerHTML = "<strong style='font-size:12px;'>Types:</strong>";
      (DATA.node_types || []).forEach((t, idx) => {{
        const style = styleForType(t, idx);
        const lbl = document.createElement("label");
        lbl.innerHTML = `<input class="typeChk" type="checkbox" value="${{t}}" checked> ${{style.name}}`;
        container.appendChild(lbl);
      }});
    }}

    function selectedTypes() {{
      return new Set(Array.from(document.querySelectorAll(".typeChk"))
        .filter(x => x.checked)
        .map(x => x.value));
    }}

    function nodeText(n) {{
      const loc = n.location_ID ? n.location_ID : "n/a";
      const country = n.country ? n.country : "n/a";
      return `${{n.name || n.id}}<br>ID: ${{n.id}}<br>Type: ${{n.type}}<br>Country: ${{country}}<br>Location: ${{loc}}`;
    }}

    function edgeText(e) {{
      const itemCount = Array.isArray(e.items) ? e.items.length : 0;
      const itemPreview = itemCount ? e.items.join(", ") : "n/a";
      return `Edge: ${{e.id}}<br>${{e.from}} -> ${{e.to}}<br>Items (${{itemCount}}): ${{itemPreview}}`;
    }}

    function clamp(value, min, max) {{
      return Math.min(Math.max(value, min), max);
    }}

    function computeGeoView(visibleNodes) {{
      if (!visibleNodes.length) {{
        return {{ scale: 1 }};
      }}
      const lats = visibleNodes.map(n => n.lat);
      const lons = visibleNodes.map(n => n.lon);

      let minLat = Math.min(...lats);
      let maxLat = Math.max(...lats);
      let minLon = Math.min(...lons);
      let maxLon = Math.max(...lons);

      const latSpan = Math.max(maxLat - minLat, 0.5);
      const lonSpan = Math.max(maxLon - minLon, 0.5);
      const padLat = Math.max(latSpan * 0.25, 2.0);
      const padLon = Math.max(lonSpan * 0.25, 2.0);

      minLat = clamp(minLat - padLat, -85, 85);
      maxLat = clamp(maxLat + padLat, -85, 85);
      minLon = clamp(minLon - padLon, -180, 180);
      maxLon = clamp(maxLon + padLon, -180, 180);

      const spanLat = Math.max(maxLat - minLat, 1);
      const spanLon = Math.max(maxLon - minLon, 1);
      const effectiveSpan = Math.max(spanLat, spanLon * 0.55);
      const scale = clamp(120 / effectiveSpan, 1.1, 25);

      return {{
        scale: scale,
        center: {{
          lat: (minLat + maxLat) / 2,
          lon: (minLon + maxLon) / 2,
        }}
      }};
    }}

    function buildTraces() {{
      const traces = [];
      const visibleTypes = selectedTypes();
      const showEdges = document.getElementById("showEdges").checked;

      const visibleNodes = (DATA.nodes || []).filter(n =>
        visibleTypes.has(n.type) &&
        Number.isFinite(n.lat) &&
        Number.isFinite(n.lon)
      );
      const visibleNodeIds = new Set(visibleNodes.map(n => n.id));

      (DATA.node_types || []).forEach((nodeType, idx) => {{
        if (!visibleTypes.has(nodeType)) return;
        const style = styleForType(nodeType, idx);
        const subset = visibleNodes.filter(n => n.type === nodeType);
        if (!subset.length) return;
        traces.push({{
          type: "scattergeo",
          mode: "markers",
          name: style.name,
          lon: subset.map(n => n.lon),
          lat: subset.map(n => n.lat),
          text: subset.map(nodeText),
          customdata: subset.map(n => [n.id, n.type, n.name || n.id]),
          hovertemplate: "%{{text}}<extra></extra>",
          marker: {{
            size: 9,
            color: style.color,
            symbol: style.symbol,
            line: {{ width: 0.6, color: "#111827" }}
          }}
        }});
      }});

      let drawnEdges = 0;
      if (showEdges) {{
        for (const e of (DATA.edges || [])) {{
          const src = nodeById[e.from];
          const dst = nodeById[e.to];
          if (!src || !dst) continue;
          if (!visibleNodeIds.has(src.id) || !visibleNodeIds.has(dst.id)) continue;
          if (!Number.isFinite(src.lat) || !Number.isFinite(src.lon)) continue;
          if (!Number.isFinite(dst.lat) || !Number.isFinite(dst.lon)) continue;
          const itemCount = Array.isArray(e.items) ? e.items.length : 0;
          const width = 1 + Math.min(itemCount, 4);
          traces.push({{
            type: "scattergeo",
            mode: "lines",
            showlegend: false,
            lon: [src.lon, dst.lon],
            lat: [src.lat, dst.lat],
            line: {{ width, color: "#475569" }},
            opacity: 0.65,
            text: edgeText(e),
            hovertemplate: "%{{text}}<extra></extra>",
          }});
          drawnEdges += 1;
        }}
      }}

      document.getElementById("stats").textContent =
        `${{visibleNodes.length}} nodes visibles / ${{(DATA.nodes || []).length}} | ` +
        `${{showEdges ? drawnEdges : 0}} flux affiches / ${{(DATA.edges || []).length}}`;
      return {{ traces, visibleNodes }};
    }}

    function hideFactoryPanel() {{
      const panel = document.getElementById("factoryHoverPanel");
      panel.classList.remove("visible");
      currentFactoryHoverId = null;
    }}

    function chartLayoutBase(titleText, yTitle) {{
      return {{
        title: {{text: titleText, font: {{size: 12}}}},
        margin: {{l: 45, r: 10, t: 32, b: 36}},
        paper_bgcolor: "rgba(0,0,0,0)",
        plot_bgcolor: "rgba(0,0,0,0)",
        xaxis: {{title: "Jour", showgrid: true, gridcolor: "#e2e8f0"}},
        yaxis: {{title: yTitle, showgrid: true, gridcolor: "#e2e8f0"}},
        legend: {{orientation: "h", font: {{size: 10}}}},
      }};
    }}

    function showFactoryPanel(factoryId) {{
      const info = FACTORY_SERIES[factoryId];
      if (!info) {{
        hideFactoryPanel();
        return;
      }}

      const panel = document.getElementById("factoryHoverPanel");
      const title = document.getElementById("factoryHoverTitle");
      const incomingDiv = document.getElementById("factoryIncomingChart");
      const outgoingDiv = document.getElementById("factoryOutgoingChart");
      title.textContent = `Factory: ${{info.node_name || factoryId}} (${{factoryId}})`;

      if (currentFactoryHoverId !== factoryId) {{
        const incomingTraces = (info.incoming || []).map((s) => ({{
          type: "scatter",
          mode: "lines+markers",
          name: `${{s.item_label}}${{s.unit ? ` (${{s.unit}})` : ""}}`,
          x: s.days || [],
          y: s.values || [],
          line: {{width: 1.8}},
          marker: {{size: 4}},
          hovertemplate: `${{s.item_label}}<br>Jour=%{{x}}<br>Stock=%{{y:.3f}}${{s.unit ? ` ${{s.unit}}` : ""}}<extra></extra>`,
        }}));

        const outgoingTraces = (info.outgoing || []).map((s) => ({{
          type: "scatter",
          mode: "lines+markers",
          name: `${{s.item_label}}${{s.unit ? ` (${{s.unit}})` : ""}}`,
          x: s.days || [],
          y: s.values || [],
          line: {{width: 1.8}},
          marker: {{size: 4}},
          hovertemplate: `${{s.item_label}}<br>Jour=%{{x}}<br>Production=%{{y:.3f}}${{s.unit ? ` ${{s.unit}}` : ""}}<extra></extra>`,
        }}));

        Plotly.react(
          incomingDiv,
          incomingTraces,
          chartLayoutBase("Matieres entrantes (stock avant production)", "Stock"),
          {{displayModeBar: false, responsive: true}}
        );
        Plotly.react(
          outgoingDiv,
          outgoingTraces,
          chartLayoutBase("Produits sortants (production journaliere)", "Production"),
          {{displayModeBar: false, responsive: true}}
        );
      }}

      currentFactoryHoverId = factoryId;
      panel.classList.add("visible");
    }}

    function bindHoverHandlers() {{
      if (hoverHandlersBound) return;
      const gd = document.getElementById("chart");
      gd.on("plotly_hover", (ev) => {{
        const p = ev && ev.points && ev.points.length ? ev.points[0] : null;
        if (!p || !Array.isArray(p.customdata)) {{
          hideFactoryPanel();
          return;
        }}
        const nodeId = p.customdata[0];
        const nodeType = p.customdata[1];
        if (nodeType !== "factory") {{
          hideFactoryPanel();
          return;
        }}
        showFactoryPanel(nodeId);
      }});
      gd.on("plotly_unhover", () => {{
        hideFactoryPanel();
      }});
      hoverHandlersBound = true;
    }}

    function draw() {{
      const {{ traces, visibleNodes }} = buildTraces();
      const geoView = computeGeoView(visibleNodes);
      const geoLayout = {{
        scope: "world",
        projection: {{type: "natural earth", scale: geoView.scale || 1}},
        showland: true,
        landcolor: "#eef2f7",
        showcountries: true,
        countrycolor: "#cbd5e1",
        showocean: true,
        oceancolor: "#f8fbff"
      }};
      if (geoView.center) {{
        geoLayout.center = geoView.center;
      }}

      const layout = {{
        margin: {{l: 0, r: 0, t: 0, b: 0}},
        showlegend: true,
        legend: {{orientation: "h"}},
        geo: geoLayout
      }};

      hideFactoryPanel();
      Plotly.newPlot("chart", traces, layout, {{displayModeBar: true, responsive: true}});
      bindHoverHandlers();
    }}

    function init() {{
      initFilters();
      document.getElementById("showEdges").addEventListener("change", draw);
      for (const chk of document.querySelectorAll(".typeChk")) {{
        chk.addEventListener("change", draw);
      }}
      draw();
    }}

    window.addEventListener("load", init);
  </script>
</body>
</html>"""


def main() -> None:
    args = parse_args()
    in_path = Path(args.input)
    out_path = Path(args.output)
    sim_input = Path(args.sim_input_stocks_csv)
    sim_output = Path(args.sim_output_products_csv)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        raw = json.loads(in_path.read_text(encoding="utf-8"))
        payload = compact_graph_payload(raw)
        payload["factory_hover_series"] = build_factory_hover_series(raw, sim_input, sim_output)
    except Exception as exc:
        print(f"[ERROR] Unable to read/parse input JSON: {exc}", file=sys.stderr)
        sys.exit(1)

    html_str = html_template(args.title, json.dumps(payload, ensure_ascii=False))
    out_path.write_text(html_str, encoding="utf-8")
    print(f"[OK] HTML generated: {out_path.resolve()}")


if __name__ == "__main__":
    main()
