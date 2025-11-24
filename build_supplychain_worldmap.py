#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Construit un HTML Plotly (carte monde + filtres + flux) directement
à partir du JSON ENRICHI (avec suppliers.{tier1, first_transformation, raw_material}).

Usage:
  python build_from_enriched_json.py \
      --input supplychain_ultimate_ENRICHED_FULL_CLEANED.json \
      --output supplychain_worldmap_from_enriched.html \
      --title "Supply Chain — Enriched JSON"

Aucune dépendance tierce côté Python (Plotly est chargé via CDN dans le HTML).
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

# ---- Centroïdes pays (approx)
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
    "United States": (39.7837304, -100.4458825),
    "Canada": (56.1304, -106.3468),
    "Brazil": (-14.2350, -51.9253),
    "Switzerland": (46.8182, 8.2275),
    "Netherlands": (52.1326, 5.2913),
}

TIERS_ORDER = ["primary_material", "raw_material", "first_transformation", "tier1"]

# Couleurs des NŒUDS (markers) par tier
TIER_STYLES = {
    "primary_material":     {"name": "Primary material",      "color": "#7D3C98", "symbol": "diamond"},
    "raw_material":         {"name": "Raw material",          "color": "#1E8449", "symbol": "square"},
    "first_transformation": {"name": "1st transformation",    "color": "#CA6F1E", "symbol": "triangle-up"},
    "tier1":                {"name": "Tier 1",                "color": "#2874A6", "symbol": "circle"},
}

# Libellés de flux et COULEURS des flux (lignes)
FLOW_LABELS = ["Primary → Raw", "Raw → 1st transf.", "1st transf. → Tier 1", "Tier 1 → Safran"]
FLOW_STYLES = {
  "Primary → Raw":        {"color": "#8A2BE2"},  # violet
  "Raw → 1st transf.":    {"color": "#2CA02C"},  # vert
  "1st transf. → Tier 1": {"color": "#FF7F0E"},  # orange
  "Tier 1 → Safran":      {"color": "#1F77B4"},  # bleu
}

def normalize_country(raw: Optional[str]) -> Optional[str]:
    if not raw:
        return None
    s = (raw or "").strip().lower()
    # capture éventuelle "Name (France)" -> "France"
    if "(" in s and ")" in s:
        inside = s.split("(")[-1].split(")")[0].strip()
        if inside:
            s = inside
    s = s.replace(")", " ").replace("(", " ")
    s = " ".join(s.split())
    if s in COUNTRY_ALIASES:
        return COUNTRY_ALIASES[s]
    return s.title()

def extract_name_and_country(name_field: str, location_field: str) -> Tuple[str, Optional[str], bool]:
    """
    Déduit supplier, country, is_primary depuis name/location.
    - '*' dans le nom => is_primary=True, et on retire '*'.
    - Si 'location' vide, on essaye "Name (France)".
    """
    name = (name_field or "").strip()
    is_primary = False
    if "*" in name or name.endswith("(primary)") or "(primary)" in name.lower():
        is_primary = True
    name_clean = name.replace("*", "").replace("(primary)", "").replace("(Primary)", "").strip()

    country = normalize_country(location_field or "")
    if not country:
        # Essaye de déduire depuis le nom "Foo (France)"
        if "(" in name and ")" in name:
            inside = name.split("(")[-1].split(")")[0].strip()
            country = normalize_country(inside)

    return name_clean, country, is_primary

def load_enriched(path: Path) -> List[Dict[str, Any]]:
    """
    Charge le JSON enrichi (liste d'objets) et fabrique DES 'records' utilisables par la visualisation :
      { system, component, tiers: { tier1:[{supplier,country,is_primary},...], ... } }
    """
    raw = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(raw, dict) and "records" in raw:
        raw = raw["records"]
    if not isinstance(raw, list):
        raise ValueError("Le JSON enrichi doit être une liste (ou un objet avec 'records').")

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
                if isinstance(entry, dict):
                    nm = entry.get("name") or entry.get("supplier") or ""
                    loc = entry.get("location") or entry.get("country") or ""
                    is_p = bool(entry.get("is_primary", False))
                    lat = entry.get("lat")
                    lon = entry.get("lon")
                    # Normalise à partir de name/location
                    supplier, country, is_star = extract_name_and_country(nm, loc)
                    is_primary = is_p or is_star
                    lat = float(lat) if isinstance(lat, (int, float, str)) and str(lat).strip() not in ("", "None") else None
                    lon = float(lon) if isinstance(lon, (int, float, str)) and str(lon).strip() not in ("", "None") else None
                else:
                    # chaîne brute
                    supplier, country, is_primary = extract_name_and_country(str(entry), "")
                    lat = lon = None

                if not supplier:
                    continue
                # ignore si pays inconnu ET impossible de déduire -> la carte ne saura pas placer
                if country is None:
                    continue
                tiers_out[tier].append({
                    "supplier": supplier,
                    "country": country,
                    "is_primary": is_primary,
                    "lat": lat,
                    "lon": lon,
                })

        records.append({"system": system, "component": component, "tiers": tiers_out})
    return records

def build_data(records: List[Dict[str, Any]]) -> Dict[str, Any]:
    systems = ["All"]
    components = ["All"]
    for r in records:
        s = r.get("system") or ""
        c = r.get("component") or ""
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
  <div>
    <label for="systemSel">Système</label>
    <select id="systemSel"></select>
  </div>
  <div>
    <label for="componentSel">Composant</label>
    <select id="componentSel"></select>
  </div>
  <div>
    <label>Niveaux</label>
    <label><input type="checkbox" class="tierChk" value="primary_material"> Primary</label>
    <label><input type="checkbox" class="tierChk" value="raw_material" checked> Raw</label>
    <label><input type="checkbox" class="tierChk" value="first_transformation" checked> 1st transf.</label>
    <label><input type="checkbox" class="tierChk" value="tier1" checked> Tier 1</label>
  </div>
  <div>
    <label>Flux</label>
    <label><input type="checkbox" class="flowChk" value="Primary → Raw" checked> P→R</label>
    <label><input type="checkbox" class="flowChk" value="Raw → 1st transf." checked> R→1st</label>
    <label><input type="checkbox" class="flowChk" value="1st transf. → Tier 1" checked> 1st→T1</label>
    <label><input type="checkbox" class="flowChk" value="Tier 1 → Safran" checked> T1→Safran</label>
  </div>
  <div>
    <label><input type="checkbox" id="onlyPrimary"> Fournisseurs principaux uniquement</label>
  </div>
  <div class="spacer"></div>
</div>
<div id="chart"></div>

<script>
const DATA = {data_json};

// === Styles des flux par catégorie ===
const FLOW_STYLES = DATA.flow_styles || {{}};

// Échelle d’épaisseur (linéaire) — tu pourras adapter
function scaleWidth(value, vmin, vmax, wmin=0.8, wmax=6) {{
  if (!isFinite(value)) return wmin;
  if (vmax <= vmin) return wmin;
  const r = (value - vmin) / (vmax - vmin);
  return wmin + r * (wmax - wmin);
}}

const countryCoords = DATA.country_coords || {{}};
function getLatLon(supplier) {{
  if (!supplier) return null;
  const lat = supplier.lat;
  const lon = supplier.lon;
  if (typeof lat === "number" && typeof lon === "number" && isFinite(lat) && isFinite(lon)) {{
    return {{lat, lon}};
  }}
  const country = supplier.country;
  if (!country) return null;
  const coords = countryCoords[country];
  return coords ? {{lat: coords[0], lon: coords[1]}} : null;
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
  const tierChks = Array.from(document.querySelectorAll(".tierChk")).filter(x => x.checked).map(x => x.value);
  const flowChks = Array.from(document.querySelectorAll(".flowChk")).filter(x => x.checked).map(x => x.value);
  const onlyPrimary = document.getElementById("onlyPrimary").checked;
  return {{ system: sys, component: comp, tiers: tierChks, flows: flowChks, onlyPrimary }};
}}

function recordMatches(rec, filters) {{
  if (filters.system !== "All" && rec.system !== filters.system) return false;
  if (filters.component !== "All" && rec.component !== filters.component) return false;
  return true;
}}

function buildTraces() {{
  const filters = currentFilters();
  const traces = [];
  const lines = [];

  // Points par niveau
  for (const tier of DATA.tiers) {{
    if (!filters.tiers.includes(tier)) continue;
    const style = DATA.tier_styles[tier] || {{}};
    const xs = [], ys = [], texts = [];

    for (const rec of DATA.records) {{
      if (!recordMatches(rec, filters)) continue;
      const suppliers = (rec.tiers && rec.tiers[tier]) ? rec.tiers[tier] : [];
      for (const s of suppliers) {{
        if (filters.onlyPrimary && !s.is_primary) continue;
        const loc = getLatLon(s);
        if (!loc) continue;
        xs.push(loc.lon); ys.push(loc.lat);
        texts.push(`${{s.supplier || "?"}} — ${{s.country || "?"}}\\n[${{rec.system}}] ${{rec.component}}`);
      }}
    }}

    traces.push({{
      type: "scattergeo",
      mode: "markers",
      lon: xs, lat: ys, text: texts,
      name: style.name || tier,
      marker: {{
        size: 8,
        color: style.color || "#666",
        symbol: style.symbol || "circle",
        line: {{width: 0.5, color: "#333"}}
      }}
    }});
  }}

  // Lignes/flux avec agrégation par paire de pays
  function addLines(fromTier, toTier, label) {{
    if (!currentFilters().flows.includes(label)) return;

    const style = FLOW_STYLES[label] || {{ color: "#888" }};
    const edgeMap = new Map(); // key: "lat1,lon1->lat2,lon2" ; val: {{from,to,value}}

    for (const rec of DATA.records) {{
      if (!recordMatches(rec, currentFilters())) continue;

      const fromList = (rec.tiers && rec.tiers[fromTier]) ? rec.tiers[fromTier] : [];
      const toList   = (toTier === "safran")
        ? [{{ supplier: "Safran", country: "France" }}]
        : ((rec.tiers && rec.tiers[toTier]) ? rec.tiers[toTier] : []);

      for (const f of fromList) {{
        if (currentFilters().onlyPrimary && !f.is_primary) continue;
        const fLoc = getLatLon(f);
        if (!fLoc) continue;

        // Option “units” future : si tu ajoutes une quantité (f.units), on la sommera ici
        const fUnits = (typeof f.units === "number" && f.units > 0) ? f.units : 1;

        for (const t of toList) {{
          if (toTier !== "safran" && currentFilters().onlyPrimary && !t.is_primary) continue;
          const tLoc = (toTier === "safran") ? {{lat: DATA.safran.lat, lon: DATA.safran.lon}} : getLatLon(t);
          if (!tLoc) continue;

          const key = `${{fLoc.lat.toFixed(3)}},${{fLoc.lon.toFixed(3)}}->${{tLoc.lat.toFixed(3)}},${{tLoc.lon.toFixed(3)}}`;
          const inc = fUnits; // aujourd’hui: 1 par edge ; demain: mets ta vraie quantité

          if (!edgeMap.has(key)) {{
            edgeMap.set(key, {{ from: fLoc, to: tLoc, value: 0 }});
          }}
          edgeMap.get(key).value += inc;
        }}
      }}
    }}

    // Min/max pour l'échelle d'épaisseur
    let vmin = Infinity, vmax = -Infinity;
    edgeMap.forEach(({{value}}) => {{ if (value < vmin) vmin = value; if (value > vmax) vmax = value; }});
    if (!isFinite(vmin)) {{ vmin = 1; vmax = 1; }}

    // Traces de lignes
    edgeMap.forEach(({{from, to, value}}) => {{
      const width = scaleWidth(value, vmin, vmax, 0.8, 6);
      lines.push({{
        type: "scattergeo",
        mode: "lines",
        lon: [from.lon, to.lon],
        lat: [from.lat, to.lat],
        line: {{ width, color: style.color }},
        opacity: 0.9,
        hoverinfo: "text",
        text: `${{label}} — qty: ${{value}}`,
        showlegend: false
      }});
    }});
  }}

  addLines("primary_material", "raw_material", "Primary → Raw");
  addLines("raw_material", "first_transformation", "Raw → 1st transf.");
  addLines("first_transformation", "tier1", "1st transf. → Tier 1");
  addLines("tier1", "safran", "Tier 1 → Safran");

  return traces.concat(lines);
}}

function draw() {{
  const traces = buildTraces();
  const layout = {{
    geo: {{
      scope: "world",
      projection: {{ type: "natural earth" }},
      showland: true, landcolor: "#f0f0f0",
      subunitwidth: 1, countrywidth: 1,
      subunitcolor: "#dcdcdc", countrycolor: "#dcdcdc"
    }},
    margin: {{l:0,r:0,t:0,b:0}},
    legend: {{orientation: "h"}}
  }};
  Plotly.newPlot("chart", traces, layout, {{displayModeBar: true, responsive: true}});
}}

function refreshDependentSelects() {{
  const sys = document.getElementById("systemSel").value;
  const comp = document.getElementById("componentSel").value;
  const comps = ["All"], syses = ["All"];
  for (const rec of DATA.records) {{
    if (sys === "All" || rec.system === sys) {{
      if (rec.component && !comps.includes(rec.component)) comps.push(rec.component);
    }}
    if (comp === "All" || rec.component === comp) {{
      if (rec.system && !syses.includes(rec.system)) syses.push(rec.system);
    }}
  }}
  fillSelect(document.getElementById("componentSel"), comps);
  fillSelect(document.getElementById("systemSel"), syses);
  if (syses.includes(sys)) document.getElementById("systemSel").value = sys;
  if (comps.includes(comp)) document.getElementById("componentSel").value = comp;
}}

function initUI() {{
  fillSelect(document.getElementById("systemSel"), DATA.systems || ["All"]);
  fillSelect(document.getElementById("componentSel"), DATA.components || ["All"]);
  document.getElementById("systemSel").addEventListener("change", ()=>{{ refreshDependentSelects(); draw(); }});
  document.getElementById("componentSel").addEventListener("change", ()=>{{ refreshDependentSelects(); draw(); }});
  for (const el of document.querySelectorAll(".tierChk, .flowChk, #onlyPrimary")) {{ el.addEventListener("change", draw); }}
  draw();
}}
window.addEventListener("load", initUI);
</script>
</body>
</html>"""

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--input", "-i", required=True, help="Chemin du JSON ENRICHI (avec suppliers.*)")
    p.add_argument("--output", "-o", required=True, help="HTML de sortie")
    p.add_argument("--title", default="Supply Chain — Enriched JSON")
    args = p.parse_args()

    in_path = Path(args.input)
    out_path = Path(args.output)

    try:
        records = load_enriched(in_path)
    except Exception as e:
        print(f"[ERREUR] Lecture/parse JSON enrichi: {e}", file=sys.stderr)
        sys.exit(1)

    # Petit log de contrôle
    n_nodes = sum(len(r["tiers"].get(t, [])) for r in records for t in TIERS_ORDER)
    print(f"[INFO] {len(records)} records, {n_nodes} fournisseurs positionnables.")

    data = build_data(records)
    html_str = html_template(args.title, json.dumps(data, ensure_ascii=False))
    out_path.write_text(html_str, encoding="utf-8")
    print(f"[OK] HTML généré → {out_path.resolve()}")

if __name__ == "__main__":
    main()
