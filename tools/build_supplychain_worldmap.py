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
    "England": (52.3555, -1.1743),
    "Denmark": (56.2639, 9.5018),
    "Finland": (61.9241, 25.7482),
    "Luxembourg": (49.8153, 6.1296),
    "Belgium": (50.5039, 4.4699),
    "Germany": (51.1657, 10.4515),
    "Sweden": (60.1282, 18.6435),
    "Norway": (60.4720, 8.4689),
    "Poland": (51.9194, 19.1451),
    "Ireland": (53.1424, -7.6921),
    "Austria": (47.5162, 14.5501),
    "Italy": (41.8719, 12.5674),
    "Spain": (40.4637, -3.7492),
    "Portugal": (39.3999, -8.2245),
    "Switzerland": (46.8182, 8.2275),
    "Netherlands": (52.1326, 5.2913),
    "Lithuania": (55.1694, 23.8813),
    "Latvia": (56.8796, 24.6032),
    "Czech Republic": (49.8175, 15.4729),

    "China": (35.8617, 104.1954),
    "India": (20.5937, 78.9629),
    "Japan": (36.2048, 138.2529),
    "Thailand": (15.8700, 100.9925),
    "United States": (39.7837304, -100.4458825),
    "Canada": (56.1304, -106.3468),
    "Mexico": (23.6345, -102.5528),
    "Brazil": (-14.2350, -51.9253),
    "Cameroon": (7.3697, 12.3547),
    "Nigeria": (9.0820, 8.6753),
    "Liberia": (6.4281, -9.4295),
    "Côte d’Ivoire": (7.5400, -5.5471),
    "Ivory Coast": (7.5400, -5.5471),
    "Indonesia": (-0.7893, 113.9213),
    "Philippines": (12.8797, 121.7740),
    "Saudi Arabia": (23.8859, 45.0792),
    "Thailand": (15.8700, 100.9925),
}

TIERS_ORDER = [
    "tier4_raw_material",
    "tier3_first_transformation",
    "tier2_second_transformation",
    "tier1",
    "logistics",
    "oem",
]

# Couleurs des NŒUDS (markers) par tier
TIER_STYLES = {
    "tier4_raw_material":        {"name": "Tier 4 • Matière",      "color": "#7D3C98", "symbol": "diamond"},
    "tier3_first_transformation": {"name": "Tier 3 • 1ère transfo", "color": "#1E8449", "symbol": "square"},
    "tier2_second_transformation": {"name": "Tier 2 • 2e transfo",  "color": "#CA6F1E", "symbol": "triangle-up"},
    "tier1":                     {"name": "Tier 1",               "color": "#2874A6", "symbol": "circle"},
    "oem":                       {"name": "OEM",                  "color": "#000000", "symbol": "star"},
}

# Libellés de flux et COULEURS des flux (lignes)
FLOW_LABELS = [
    "Tier4 → Tier3",
    "Tier3 → Tier2",
    "Tier2 → Tier1",
    "Tier1 → OEM",
]
FLOW_STYLES = {
  "Tier4 → Tier3": {"color": "#8A2BE2"},  # violet
  "Tier3 → Tier2": {"color": "#2CA02C"},  # vert
  "Tier2 → Tier1": {"color": "#FF7F0E"},  # orange
  "Tier1 → OEM":   {"color": "#1F77B4"},  # bleu
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

def entry_metadata(entry: Any) -> Dict[str, Any]:
    if not isinstance(entry, dict):
        return {
            "supplier_status": "",
            "baseline_completion_assumption": False,
            "baseline_completion_confidence": "",
            "simulation_node_type": "",
            "lca_component_trace": {},
        }
    return {
        "supplier_status": entry.get("supplier_status") or "",
        "baseline_completion_assumption": bool(entry.get("baseline_completion_assumption", False)),
        "baseline_completion_confidence": entry.get("baseline_completion_confidence") or "",
        "simulation_node_type": entry.get("simulation_node_type") or "",
        "lca_component_trace": entry.get("lca_component_trace") or {},
    }

def load_enriched(path: Path) -> List[Dict[str, Any]]:
    """
    Charge le JSON enrichi (liste d'objets) et fabrique DES 'records' utilisables par la visualisation :
      { system, component, tiers: { tier1:[{supplier,country,is_primary},...], ... } }

    Compatible avec :
      - ancien format {suppliers: {raw_material: [...], first_transformation: [...], tier1: [...]}}
      - nouveau format aplati {suppliers: [ {name, location, role_hint, description, ...}, ... ] }
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
        if rec.get("simulation_supply_usable") is False:
            continue
        system = (rec.get("system") or "").strip()
        component = (rec.get("component") or "").strip()
        suppliers_obj = rec.get("suppliers") or {}

        # Prépare la structure tierisée de sortie
        tiers_out: Dict[str, List[Dict[str, Any]]] = {k: [] for k in TIERS_ORDER}

        if isinstance(suppliers_obj, list):
            # Nouveau format aplati : chaque entrée porte son role_hint (ou fallback role)
            for entry in suppliers_obj:
                if not isinstance(entry, dict):
                    continue
                nm = entry.get("name") or entry.get("supplier") or ""
                loc = entry.get("location") or entry.get("country") or ""
                role_hint = entry.get("role_hint") or entry.get("role") or ""
                # map role_hint -> tier bucket, sinon on ignore
                tier = None
                for t in TIERS_ORDER:
                    if role_hint == t:
                        tier = t
                        break
                if tier is None:
                    # logistique ou oem sont aussi présents dans TIERS_ORDER
                    continue
                is_p = bool(entry.get("is_primary", False))
                lat = entry.get("lat")
                lon = entry.get("lon")
                desc = entry.get("description") or entry.get("notes") or ""
                supplier, country, is_star = extract_name_and_country(nm, loc)
                is_primary = is_p or is_star
                lat = float(lat) if isinstance(lat, (int, float, str)) and str(lat).strip() not in ("", "None") else None
                lon = float(lon) if isinstance(lon, (int, float, str)) and str(lon).strip() not in ("", "None") else None
                if not supplier or country is None:
                    continue
                tiers_out[tier].append({
                    "supplier": supplier,
                    "country": country,
                    "is_primary": is_primary,
                    "lat": lat,
                    "lon": lon,
                    "role": role_hint,
                    "description": desc,
                    **entry_metadata(entry),
                })
            for extra_entries, extra_tier in (
                (rec.get("oem_sites") or [], "oem"),
                (rec.get("logistics_providers") or [], "logistics"),
            ):
                for entry in extra_entries:
                    if not isinstance(entry, dict):
                        continue
                    nm = entry.get("name") or entry.get("supplier") or ""
                    loc = entry.get("location") or entry.get("country") or ""
                    role_hint = entry.get("role_hint") or entry.get("role") or extra_tier
                    is_p = bool(entry.get("is_primary", False))
                    lat = entry.get("lat")
                    lon = entry.get("lon")
                    desc = entry.get("description") or entry.get("notes") or ""
                    supplier, country, is_star = extract_name_and_country(nm, loc)
                    is_primary = is_p or is_star
                    lat = float(lat) if isinstance(lat, (int, float, str)) and str(lat).strip() not in ("", "None") else None
                    lon = float(lon) if isinstance(lon, (int, float, str)) and str(lon).strip() not in ("", "None") else None
                    if not supplier or country is None:
                        continue
                    tiers_out[extra_tier].append({
                        "supplier": supplier,
                        "country": country,
                        "is_primary": is_primary,
                        "lat": lat,
                        "lon": lon,
                        "role": role_hint,
                        "description": desc,
                        **entry_metadata(entry),
                    })
        else:
            # Ancien format : dictionnaire par tier
            suppliers_dict = suppliers_obj if isinstance(suppliers_obj, dict) else {}
            for tier in TIERS_ORDER:
                lst = suppliers_dict.get(tier, []) or []
                if not isinstance(lst, list):
                    continue
                for entry in lst:
                    if isinstance(entry, dict):
                        nm = entry.get("name") or entry.get("supplier") or ""
                        loc = entry.get("location") or entry.get("country") or ""
                        is_p = bool(entry.get("is_primary", False))
                        lat = entry.get("lat")
                        lon = entry.get("lon")
                        role_hint = entry.get("role_hint") or tier
                        desc = entry.get("description") or ""
                        # Normalise à partir de name/location
                        supplier, country, is_star = extract_name_and_country(nm, loc)
                        is_primary = is_p or is_star
                        lat = float(lat) if isinstance(lat, (int, float, str)) and str(lat).strip() not in ("", "None") else None
                        lon = float(lon) if isinstance(lon, (int, float, str)) and str(lon).strip() not in ("", "None") else None
                    else:
                        # chaîne brute
                        supplier, country, is_primary = extract_name_and_country(str(entry), "")
                        lat = lon = None
                        role_hint = tier
                        desc = ""

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
                        "role": role_hint,
                        "description": desc,
                        **entry_metadata(entry if isinstance(entry, dict) else {}),
                    })

        records.append({
            "system": system,
            "component": component,
            "tiers": tiers_out,
            "lca": rec.get("lca_traceability") or {},
            "mass_kg": rec.get("mass_kg"),
            "mass_confidence": rec.get("mass_confidence") or "",
            "mass_estimation_method": rec.get("mass_estimation_method") or "",
        })
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
  <div id="tiersContainer">
    <label>Niveaux</label>
    <!-- les cases seront injectées dynamiquement -->
  </div>
  <div>
    <label>Flux</label>
    <label><input type="checkbox" id="showFlows"> Afficher</label>
    <label><input type="checkbox" id="bridgeGaps" checked> Relier tiers absents</label>
    <label><input type="checkbox" class="flowChk" value="Tier4 → Tier3" checked> T4→T3</label>
    <label><input type="checkbox" class="flowChk" value="Tier3 → Tier2" checked> T3→T2</label>
    <label><input type="checkbox" class="flowChk" value="Tier2 → Tier1" checked> T2→T1</label>
    <label><input type="checkbox" class="flowChk" value="Tier1 → OEM" checked> T1→OEM</label>
  </div>
  <div>
    <label><input type="checkbox" id="onlyPrimary"> Fournisseurs principaux uniquement</label>
  </div>
  <div class="spacer"></div>
</div>
<div id="chart"></div>

<script>
// Supprime les nœuds logistiques pour l’affichage (pas de points, pas de cases)
const DATA_RAW = {data_json};
const DATA = (function() {{
  const filteredRecords = (DATA_RAW.records || []).map(r => {{
    const tiers = r.tiers || {{}};
    const {{ logistics, ...rest }} = tiers; // retire la clé logistics
    return {{ ...r, tiers: rest }};
  }});
  const tiersList = (DATA_RAW.tiers || []).filter(t => t !== "logistics");
  const tierStyles = Object.fromEntries(
    Object.entries(DATA_RAW.tier_styles || {{}}).filter(([k,_]) => k !== "logistics")
  );
  return {{
    ...DATA_RAW,
    tiers: tiersList,
    tier_styles: tierStyles,
    records: filteredRecords
  }};
}})();

// === Styles des flux par catégorie ===
const FLOW_STYLES = DATA.flow_styles || {{}};

// Échelle d’épaisseur (linéaire) — tu pourras adapter
function scaleWidth(value, vmin, vmax, wmin=0.8, wmax=6) {{
  if (!isFinite(value)) return wmin;
  if (vmax <= vmin) return wmin;
  const r = (value - vmin) / (vmax - vmin);
  return wmin + r * (wmax - wmin);
}}

// Distance haversine approximative en km
function haversineKm(lat1, lon1, lat2, lon2) {{
  const toRad = d => d * Math.PI / 180;
  const R = 6371;
  const dLat = toRad(lat2 - lat1);
  const dLon = toRad(lon2 - lon1);
  const a = Math.sin(dLat/2)**2 + Math.cos(toRad(lat1)) * Math.cos(toRad(lat2)) * Math.sin(dLon/2)**2;
  return 2 * R * Math.asin(Math.sqrt(a));
}}

const MIN_FLOW_DIST_KM = 10; // filtre les flux quasi nuls (nœuds co-localisés)

const countryCoords = DATA.country_coords || {{}};
function getLatLon(supplier) {{
  if (!supplier) return null;
  const lat = supplier.lat;
  const lon = supplier.lon;
  if (typeof lat === "number" && typeof lon === "number" && isFinite(lat) && isFinite(lon)) {{
    return {{lat, lon}};
  }}
  // Pas de fallback sur un centroïde pays : si pas de coordonnées précises, on ne trace pas.
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
  const tierChks = Array.from(document.querySelectorAll(".tierChk")).filter(x => x.checked).map(x => x.value);
  const flowChks = Array.from(document.querySelectorAll(".flowChk")).filter(x => x.checked).map(x => x.value);
  const onlyPrimary = document.getElementById("onlyPrimary").checked;
  const showFlows = document.getElementById("showFlows")?.checked ?? false;
  const bridgeGaps = document.getElementById("bridgeGaps")?.checked ?? true;
  return {{ system: sys, component: comp, tiers: tierChks, flows: flowChks, onlyPrimary, showFlows, bridgeGaps }};
}}

function recordMatches(rec, filters) {{
  if (filters.system !== "All" && rec.system !== filters.system) return false;
  if (filters.component !== "All" && rec.component !== filters.component) return false;
  return true;
}}

function fmtMass(value) {{
  if (typeof value !== "number" || !isFinite(value)) return "";
  if (value >= 10) return value.toFixed(2);
  if (value >= 1) return value.toFixed(3);
  return value.toPrecision(3);
}}

function lcaHover(rec, supplier) {{
  const lca = rec.lca || supplier.lca_component_trace || {{}};
  if (!lca || !lca.has_lca_mass) return "ACV: non marquee";
  const mass = fmtMass(lca.mass_kg);
  const share = (typeof lca.mass_share_of_non_packaging_bom === "number")
    ? `, ${{(100 * lca.mass_share_of_non_packaging_bom).toFixed(2)}}% BOM`
    : "";
  const equipment = lca.equipment_match ? `\nEquipement ACV: ${{lca.equipment_match}}` : "";
  const material = lca.material_match ? `\nMatiere ACV: ${{lca.material_match}}` : "";
  return `ACV: ${{mass}} kg${{share}} | ${{lca.match_level || "match ?"}} | conf=${{lca.confidence || "?"}}${{equipment}}${{material}}`;
}}

function assumptionHover(supplier) {{
  if (!supplier.baseline_completion_assumption) return "";
  const kind = supplier.simulation_node_type ? `, ${{supplier.simulation_node_type}}` : "";
  const conf = supplier.baseline_completion_confidence ? `, conf=${{supplier.baseline_completion_confidence}}` : "";
  return `\nHypothese supply baseline${{kind}}${{conf}}`;
}}


function initTierCheckboxes() {{
  const container = document.getElementById('tiersContainer');
  container.innerHTML = '<label>Niveaux</label>';
  const tiers = DATA.tiers || [];
  tiers.forEach(t => {{
    const lbl = document.createElement('label');
    const cb = document.createElement('input');
    cb.type = 'checkbox'; cb.className = 'tierChk'; cb.value = t;
    cb.checked = (t !== 'logistics');
    lbl.appendChild(cb);
    const labelTxt = (DATA.tier_styles[t] && DATA.tier_styles[t].name) ? DATA.tier_styles[t].name : t;
    lbl.appendChild(document.createTextNode(' ' + labelTxt));
    container.appendChild(lbl);
  }});
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
        const status = s.supplier_status ? `\\nStatut: ${{s.supplier_status}}` : "";
        texts.push(`${{s.supplier || "?"}} — ${{s.country || "?"}}\\n[${{rec.system}}] ${{rec.component}}\\n${{lcaHover(rec, s)}}${{status}}${{assumptionHover(s)}}`);
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
    const filtersNow = currentFilters();
    if (!filtersNow.showFlows) return;
    if (!filtersNow.flows.includes(label)) return;
    if (!filtersNow.tiers.includes(fromTier) || !filtersNow.tiers.includes(toTier)) return;

    const style = FLOW_STYLES[label] || {{ color: "#888" }};
    const edgeMap = new Map(); // key: "lat1,lon1->lat2,lon2" ; val: {{from,to,value}}

    for (const rec of DATA.records) {{
      if (!recordMatches(rec, filtersNow)) continue;

      const fromList = (rec.tiers && rec.tiers[fromTier]) ? rec.tiers[fromTier] : [];
      const toList   = (rec.tiers && rec.tiers[toTier]) ? rec.tiers[toTier] : [];

      for (const f of fromList) {{
        if (filtersNow.onlyPrimary && !f.is_primary) continue;
        const fLoc = getLatLon(f);
        if (!fLoc) continue;

        // Option “units” future : si tu ajoutes une quantité (f.units), on la sommera ici
        const fUnits = (typeof f.units === "number" && f.units > 0) ? f.units : 1;

        for (const t of toList) {{
          if (filtersNow.onlyPrimary && !t.is_primary) continue;
          const tLoc = getLatLon(t);
          if (!tLoc) continue;

          // Ignore les flux quasi nuls (co-localisation ou même site)
          const dist = haversineKm(fLoc.lat, fLoc.lon, tLoc.lat, tLoc.lon);
          if (dist < MIN_FLOW_DIST_KM) continue;

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

  function compactTierName(tier) {{
    if (tier === "tier4_raw_material") return "T4";
    if (tier === "tier3_first_transformation") return "T3";
    if (tier === "tier2_second_transformation") return "T2";
    if (tier === "tier1") return "T1";
    if (tier === "oem") return "OEM";
    return tier;
  }}

  function addGapBridgeLines() {{
    const filtersNow = currentFilters();
    if (!filtersNow.showFlows || !filtersNow.bridgeGaps) return;

    const ordered = ["tier4_raw_material", "tier3_first_transformation", "tier2_second_transformation", "tier1", "oem"];
    const edgeMap = new Map();

    for (const rec of DATA.records) {{
      if (!recordMatches(rec, filtersNow)) continue;
      const present = [];
      for (let idx = 0; idx < ordered.length; idx++) {{
        const tier = ordered[idx];
        const list = ((rec.tiers && rec.tiers[tier]) ? rec.tiers[tier] : [])
          .filter(s => !filtersNow.onlyPrimary || s.is_primary)
          .filter(s => getLatLon(s));
        if (list.length) present.push({{ tier, idx, list }});
      }}

      for (let i = 0; i < present.length - 1; i++) {{
        const from = present[i];
        const to = present[i + 1];
        if (to.idx - from.idx <= 1) continue;
        if (!filtersNow.tiers.includes(from.tier) || !filtersNow.tiers.includes(to.tier)) continue;
        const missing = ordered.slice(from.idx + 1, to.idx).map(compactTierName).join(", ");
        const label = `${{compactTierName(from.tier)}}->${{compactTierName(to.tier)}} (tier absent: ${{missing}})`;

        for (const f of from.list) {{
          const fLoc = getLatLon(f);
          if (!fLoc) continue;
          for (const t of to.list) {{
            const tLoc = getLatLon(t);
            if (!tLoc) continue;
            const dist = haversineKm(fLoc.lat, fLoc.lon, tLoc.lat, tLoc.lon);
            if (dist < MIN_FLOW_DIST_KM) continue;
            const key = `${{label}}|${{fLoc.lat.toFixed(3)}},${{fLoc.lon.toFixed(3)}}->${{tLoc.lat.toFixed(3)}},${{tLoc.lon.toFixed(3)}}`;
            if (!edgeMap.has(key)) {{
              edgeMap.set(key, {{ from: fLoc, to: tLoc, value: 0, label }});
            }}
            edgeMap.get(key).value += 1;
          }}
        }}
      }}
    }}

    edgeMap.forEach(({{from, to, value, label}}) => {{
      lines.push({{
        type: "scattergeo",
        mode: "lines",
        lon: [from.lon, to.lon],
        lat: [from.lat, to.lat],
        line: {{ width: 1.6, color: "#6B7280", dash: "dot" }},
        opacity: 0.72,
        hoverinfo: "text",
        text: `${{label}} — continuité de chaîne, qty: ${{value}}`,
        showlegend: false
      }});
    }});
  }}

  addLines("tier4_raw_material", "tier3_first_transformation", "Tier4 → Tier3");
  addLines("tier3_first_transformation", "tier2_second_transformation", "Tier3 → Tier2");
  addLines("tier2_second_transformation", "tier1", "Tier2 → Tier1");
  addLines("tier1", "oem", "Tier1 → OEM");
  addGapBridgeLines();

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
  // Injecte dynamiquement les cases à cocher des niveaux
  initTierCheckboxes();
  fillSelect(document.getElementById("systemSel"), DATA.systems || ["All"]);
  fillSelect(document.getElementById("componentSel"), DATA.components || ["All"]);
  document.getElementById("systemSel").addEventListener("change", ()=>{{ refreshDependentSelects(); draw(); }});
  document.getElementById("componentSel").addEventListener("change", ()=>{{ refreshDependentSelects(); draw(); }});
  for (const el of document.querySelectorAll(".tierChk, .flowChk, #onlyPrimary, #showFlows, #bridgeGaps")) {{ el.addEventListener("change", draw); }}
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
    print(f"[OK] HTML generated -> {out_path.resolve()}")

if __name__ == "__main__":
    main()
