#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Construit un HTML Plotly (carte monde + filtres + flux) directement
à partir du JSON ENRICHI (avec suppliers.{tier1, first_transformation, raw_material}).

Version NOPRIMARY (hardcodée) :
- Nœud 'Primary' retiré (non proposé dans l'UI, non tracé)
- Flux 'Primary → Raw' retiré (non proposé dans l'UI, non tracé)
- Si lat/lon sont présents dans le JSON, ils sont utilisés directement.
- Sinon, fallback sur le centroïde du pays.

Usage:
  python build_supplychain_worldmap.py \
      --input supplychain_ultimate_ENRICHED_FULL_PRIMARYFIX_GEO.json \
      --output supplychain_worldmap.html \
      --title "Supply Chain — Enriched JSON"
"""

from __future__ import annotations
import json, argparse, html, sys
from pathlib import Path
from typing import Any, Dict, List, Tuple, Optional

# ---- Normalisation pays (alias FR/EN courants)
COUNTRY_ALIASES = {
    "france": "France",
    "angleterre": "United Kingdom",
    "royaume-uni": "United Kingdom",
    "uk": "United Kingdom",
    "belgique": "Belgium",
    "allemagne": "Germany",
    "suede": "Sweden",
    "suède": "Sweden",
    "pologne": "Poland",
    "irlande": "Ireland",
    "autriche": "Austria",
    "italie": "Italy",
    "espagne": "Spain",
    "portugal": "Portugal",
    "chine": "China",
    "india": "India",
    "inde": "India",
    "japon": "Japan",
    "thailande": "Thailand",
    "thaïlande": "Thailand",
    "thailand": "Thailand",
    "usa": "United States",
    "etats-unis": "United States",
    "états-unis": "United States",
    "canada": "Canada",
    "brazil": "Brazil",
    "brésil": "Brazil",
    "switzerland": "Switzerland",
    "suisse": "Switzerland",
    "pays-bas": "Netherlands",
    "netherlands": "Netherlands",
}

# ---- Centroïdes pays
COUNTRY_COORDS = {
    "France": (46.2276, 2.2137),
    "United Kingdom": (55.3781, -3.4360),
    "Belgium": (50.5039, 4.4699),
    "Germany": (51.1657, 10.4515),
    "Sweden": (60.1282, 18.6435),
    "Poland": (51.9194, 19.1451),
    "Ireland": (53.1424, -7.6921),
    "Austria": (47.5162, 14.5501),
    "Italy": (41.8719, 12.5674),
    "Spain": (40.4637, -3.7492),
    "Portugal": (39.3999, -8.2245),
    "China": (35.8617, 104.1954),
    "India": (20.5937, 78.9629),
    "Japan": (36.2048, 138.2529),
    "Thailand": (15.8700, 100.9925),
    "United States": (39.7837, -100.4459),
    "Canada": (56.1304, -106.3468),
    "Brazil": (-14.2350, -51.9253),
    "Switzerland": (46.8182, 8.2275),
    "Netherlands": (52.1326, 5.2913),
}

# --- Niveaux actifs
TIERS_ORDER = ["raw_material", "first_transformation", "tier1"]

# --- Styles
TIER_STYLES = {
    "raw_material":         {"name": "Raw material",       "color": "#1E8449", "symbol": "square"},
    "first_transformation": {"name": "1st transformation", "color": "#CA6F1E", "symbol": "triangle-up"},
    "tier1":                {"name": "Tier 1",             "color": "#2874A6", "symbol": "circle"},
}

FLOW_LABELS = ["Raw → 1st transf.", "1st transf. → Tier 1", "Tier 1 → Safran"]
FLOW_STYLES = {
  "Raw → 1st transf.":    {"color": "#2CA02C"},
  "1st transf. → Tier 1": {"color": "#FF7F0E"},
  "Tier 1 → Safran":      {"color": "#1F77B4"},
}

# ---- Normalisation pays
def normalize_country(raw: Optional[str]) -> Optional[str]:
    if not raw: return None
    s = (raw or "").strip().lower()
    if "(" in s and ")" in s:
        inside = s.split("(")[-1].split(")")[0].strip()
        if inside: s = inside
    s = s.replace(")", " ").replace("(", " ")
    s = " ".join(s.split())
    if s in COUNTRY_ALIASES:
        return COUNTRY_ALIASES[s]
    return s.title()

# ---- Extraction fournisseur
def extract_name_and_country(name_field: str, location_field: str) -> Tuple[str, Optional[str], bool]:
    name = (name_field or "").strip()
    is_primary = False
    if "*" in name or "(primary)" in name.lower():
        is_primary = True
    name_clean = name.replace("*", "").replace("(primary)", "").replace("(Primary)", "").strip()
    country = normalize_country(location_field or "")
    if not country and "(" in name and ")" in name:
        inside = name.split("(")[-1].split(")")[0].strip()
        country = normalize_country(inside)
    return name_clean, country, is_primary

# ---- Chargement du JSON enrichi
def load_enriched(path: Path) -> List[Dict[str, Any]]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(raw, dict) and "records" in raw:
        raw = raw["records"]
    if not isinstance(raw, list):
        raise ValueError("Le JSON enrichi doit être une liste.")
    records = []
    for rec in raw:
        if not isinstance(rec, dict):
            continue
        system = (rec.get("system") or "").strip()
        component = (rec.get("component") or "").strip()
        suppliers = rec.get("suppliers") or {}
        tiers_out = {k: [] for k in TIERS_ORDER}
        for tier in TIERS_ORDER:
            lst = suppliers.get(tier, []) or []
            if not isinstance(lst, list):
                continue
            for entry in lst:
                if not isinstance(entry, dict):
                    supplier, country, is_primary = extract_name_and_country(str(entry), "")
                    lat = lon = None
                else:
                    nm = entry.get("name") or entry.get("supplier") or ""
                    loc = entry.get("location") or entry.get("country") or ""
                    supplier, country, is_star = extract_name_and_country(nm, loc)
                    is_primary = bool(entry.get("is_primary", False)) or is_star
                    lat = entry.get("lat")
                    lon = entry.get("lon")
                if not supplier or not country:
                    continue
                d = {"supplier": supplier, "country": country, "is_primary": is_primary}
                if isinstance(lat, (int, float)) and isinstance(lon, (int, float)):
                    d["lat"], d["lon"] = float(lat), float(lon)
                tiers_out[tier].append(d)
        records.append({"system": system, "component": component, "tiers": tiers_out})
    return records

def build_data(records: List[Dict[str, Any]]) -> Dict[str, Any]:
    systems, components = ["All"], ["All"]
    for r in records:
        s, c = r.get("system") or "", r.get("component") or ""
        if s and s not in systems: systems.append(s)
        if c and c not in components: components.append(c)
    return {
        "tiers": TIERS_ORDER,
        "tier_styles": TIER_STYLES,
        "safran": {"lat": 46.2276, "lon": 2.2137},
        "systems": systems,
        "components": components,
        "records": records,
        "flow_labels": FLOW_LABELS,
        "flow_styles": FLOW_STYLES,
        "country_coords": COUNTRY_COORDS,
    }

# ---- HTML / JS
def html_template(title: str, data_json: str) -> str:
    return f"""<!doctype html>
<html>
<head>
<meta charset="utf-8"/>
<title>{html.escape(title)}</title>
<script src="https://cdn.plot.ly/plotly-2.32.0.min.js"></script>
<style>
 body {{ font-family: system-ui, -apple-system, Segoe UI, Roboto, Arial, sans-serif; margin: 0; }}
 .toolbar {{
   display: flex; flex-wrap: wrap; gap: 12px; align-items: center;
   padding: 12px 16px; border-bottom: 1px solid #e5e5e5; background: #fafafa;
   position: sticky; top: 0; z-index: 5;
 }}
 label {{ font-size: 12px; color: #333; margin-right: 4px; }}
 select, input[type="checkbox"] {{ padding: 6px 8px; font-size: 13px; border: 1px solid #ccc; border-radius: 6px; background: white; }}
 #chart {{ width: 100%; height: calc(100vh - 64px); }}
 .spacer {{ flex: 1; }}
</style>
</head>
<body>
<div class="toolbar">
  <div><label for="systemSel">Système</label><select id="systemSel"></select></div>
  <div><label for="componentSel">Composant</label><select id="componentSel"></select></div>
  <div>
    <label>Niveaux</label>
    <label><input type="checkbox" class="tierChk" value="raw_material" checked> Raw</label>
    <label><input type="checkbox" class="tierChk" value="first_transformation" checked> 1st transf.</label>
    <label><input type="checkbox" class="tierChk" value="tier1" checked> Tier 1</label>
  </div>
  <div>
    <label>Flux</label>
    <label><input type="checkbox" class="flowChk" value="Raw → 1st transf." checked> R→1st</label>
    <label><input type="checkbox" class="flowChk" value="1st transf. → Tier 1" checked> 1st→T1</label>
    <label><input type="checkbox" class="flowChk" value="Tier 1 → Safran" checked> T1→Safran</label>
  </div>
  <div><label><input type="checkbox" id="onlyPrimary"> Fournisseurs principaux uniquement</label></div>
  <div class="spacer"></div>
</div>
<div id="chart"></div>

<script>
const DATA = {data_json};
const countryCoords = DATA.country_coords || {{}};

function getSupplierCoords(s) {{
  if (s && typeof s.lat === "number" && typeof s.lon === "number") {{
    return {{lat: s.lat, lon: s.lon}};
  }}
  if (s && s.country && countryCoords[s.country]) {{
    const c = countryCoords[s.country];
    return {{lat: c[0], lon: c[1]}};
  }}
  return null;
}}

function fillSelect(sel, options) {{
  sel.innerHTML = "";
  for (const opt of options) {{
    const o = document.createElement("option");
    o.value = opt; o.textContent = opt;
    sel.appendChild(o);
  }}
}}

function currentFilters() {{
  const sys = document.getElementById("systemSel").value;
  const comp = document.getElementById("componentSel").value;
  const tierChks = Array.from(document.querySelectorAll(".tierChk")).filter(x=>x.checked).map(x=>x.value);
  const flowChks = Array.from(document.querySelectorAll(".flowChk")).filter(x=>x.checked).map(x=>x.value);
  const onlyPrimary = document.getElementById("onlyPrimary").checked;
  return {{system: sys, component: comp, tiers: tierChks, flows: flowChks, onlyPrimary}};
}}

function recordMatches(rec, f) {{
  if (f.system !== "All" && rec.system !== f.system) return false;
  if (f.component !== "All" && rec.component !== f.component) return false;
  return true;
}}

function buildTraces() {{
  const f = currentFilters();
  const traces = [], lines = [];

  // Points
  for (const tier of DATA.tiers) {{
    if (!f.tiers.includes(tier)) continue;
    const style = DATA.tier_styles[tier] || {{}};
    const xs=[], ys=[], texts=[];
    for (const rec of DATA.records) {{
      if (!recordMatches(rec, f)) continue;
      const suppliers = (rec.tiers && rec.tiers[tier]) || [];
      for (const s of suppliers) {{
        if (f.onlyPrimary && !s.is_primary) continue;
        const loc = getSupplierCoords(s);
        if (!loc) continue;
        xs.push(loc.lon); ys.push(loc.lat);
        texts.push(`${{s.supplier||"?"}} — ${{s.country||"?"}}\\n[${{rec.system}}] ${{rec.component}}`);
      }}
    }}
    traces.push({{
      type:"scattergeo", mode:"markers", lon:xs, lat:ys, text:texts,
      name:style.name||tier,
      marker:{{size:8,color:style.color||"#666",symbol:style.symbol||"circle",line:{{width:0.5,color:"#333"}}}}
    }});
  }}

  // Flux
  const flows = {{
    "Raw → 1st transf.": ["raw_material","first_transformation"],
    "1st transf. → Tier 1": ["first_transformation","tier1"],
    "Tier 1 → Safran": ["tier1","safran"]
  }};
  for (const [label,[fromTier,toTier]] of Object.entries(flows)) {{
    if (!f.flows.includes(label)) continue;
    for (const rec of DATA.records) {{
      if (!recordMatches(rec, f)) continue;
      const fromList=(rec.tiers||{{}})[fromTier]||[];
      const toList=(toTier==="safran")?[{{supplier:"Safran",country:"France"}}]:(rec.tiers||{{}})[toTier]||[];
      for (const fnode of fromList) {{
        if (f.onlyPrimary && !fnode.is_primary) continue;
        const floc=getSupplierCoords(fnode); if(!floc) continue;
        for (const tnode of toList) {{
          const tloc=(toTier==="safran")?{{lat:DATA.safran.lat,lon:DATA.safran.lon}}:getSupplierCoords(tnode);
          if(!tloc) continue;
          lines.push({{type:"scattergeo",mode:"lines",
            lon:[floc.lon,tloc.lon],lat:[floc.lat,tloc.lat],
            line:{{width:1,color:DATA.flow_styles[label].color}},hoverinfo:"skip",showlegend:false}});
        }}
      }}
    }}
  }}
  return traces.concat(lines);
}}

function draw() {{
  const traces = buildTraces();
  const layout = {{
    geo: {{
      scope:"world", projection:{{type:"natural earth"}},
      showland:true, landcolor:"#f6f6f6", showocean:true, oceancolor:"#eef6ff",
      showcountries:true, countrycolor:"#6b7280", countrywidth:1.2,
      showcoastlines:true, coastlinecolor:"#6b7280", coastlinewidth:0.8,
      showsubunits:true, subunitcolor:"#a3a3a3", subunitwidth:0.6,
      bgcolor:"#ffffff"
    }},
    margin:{{l:0,r:0,t:0,b:0}}, legend:{{orientation:"h"}}
  }};
  Plotly.newPlot("chart", traces, layout, {{displayModeBar:true, responsive:true}});
}}

function initUI() {{
  fillSelect(document.getElementById("systemSel"), DATA.systems||["All"]);
  fillSelect(document.getElementById("componentSel"), DATA.components||["All"]);
  for (const el of document.querySelectorAll(".tierChk,.flowChk,#onlyPrimary,#systemSel,#componentSel")) {{
    el.addEventListener("change", draw);
  }}
  draw();
}}
window.addEventListener("load", initUI);
</script>
</body></html>"""

# ---- Main
def main():
    p = argparse.ArgumentParser()
    p.add_argument("--input", "-i", required=True)
    p.add_argument("--output", "-o", required=True)
    p.add_argument("--title", default="Supply Chain — Enriched JSON")
    args = p.parse_args()

    in_path, out_path = Path(args.input), Path(args.output)
    records = load_enriched(in_path)
    data = build_data(records)
    html_out = html_template(args.title, json.dumps(data, ensure_ascii=False))
    out_path.write_text(html_out, encoding="utf-8")
    print(f"[OK] HTML généré → {out_path.resolve()}")

if __name__ == "__main__":
    main()
