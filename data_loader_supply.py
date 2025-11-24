
import json, os, math, pandas as pd

COUNTRY_CENTROIDS = {
    "France": (46.2, 2.21), "Allemagne": (51.16, 10.45), "Germany": (51.16, 10.45),
    "Belgique": (50.50, 4.47), "Belgium": (50.50, 4.47),
    "Luxembourg": (49.81, 6.13), "Suisse": (46.82, 8.23), "Switzerland": (46.82, 8.23),
    "Italie": (41.87, 12.57), "Italy": (41.87, 12.57), "Espagne": (40.46, -3.75), "Spain": (40.46, -3.75),
    "Pays-Bas": (52.13, 5.29), "Netherlands": (52.13, 5.29), "Autriche": (47.52, 14.55), "Austria": (47.52,14.55),
    "Pologne": (51.92, 19.15), "Poland": (51.92, 19.15), "Tchéquie": (49.82, 15.47), "Czech Republic": (49.82, 15.47),
    "Suède": (60.13, 18.64), "Sweden": (60.13,18.64), "Norvège": (60.47, 8.47), "Norway": (60.47,8.47),
    "Royaume-Uni": (55.38, -3.44), "United Kingdom": (55.38,-3.44), "Angleterre": (52.36, -1.17),
    "Irlande": (53.14, -7.69), "Ireland": (53.14,-7.69), "Portugal": (39.40, -8.22),
    "USA": (39.38, -99.12), "États-Unis": (39.38,-99.12), "United States": (39.38,-99.12),
    "Canada": (56.13, -106.35), "Mexique": (23.63, -102.55), "Brazil": (-14.24,-51.93), "Brésil": (-14.24,-51.93),
    "Chine": (35.86, 104.20), "China": (35.86, 104.20), "Japon": (36.20, 138.25), "Japan": (36.20,138.25),
    "Inde": (20.59, 78.96), "India": (20.59, 78.96), "Thaïlande": (15.87, 100.99), "Thailand": (15.87,100.99),
    "Corée du Sud": (36.50, 127.98), "South Korea": (36.50,127.98), "Taïwan": (23.70, 121.00), "Taiwan": (23.70,121.00),
    "Singapour": (1.35, 103.82), "Singapore": (1.35, 103.82), "Malaisie": (4.21, 101.98), "Malaysia": (4.21,101.98),
    "Turquie": (39.92, 32.86), "Turkey": (39.92,32.86),
    "Australie": (-25.27, 133.77), "Australia": (-25.27, 133.77),
    "Finlande": (64.0, 26.0)
}

def norm(s):
    if s is None:
        return ""
    s = str(s).strip()
    if s.lower() in {"nan","none","null"}:
        return ""
    return s

def load_json(json_path):
    with open(json_path, "r", encoding="utf-8") as f:
        payload = json.load(f)
    return payload.get("records", [])

def load_geocoding(geocoding_path):
    geolook = {}
    if geocoding_path and os.path.exists(geocoding_path):
        df = pd.read_excel(geocoding_path)
        cols = {c.lower(): c for c in df.columns}
        ren = {}
        for k in ["société","latitude","longitude"]:
            if k in cols:
                ren[cols[k]] = k.capitalize() if k != "société" else "Société"
        df = df.rename(columns=ren)
        for _, r in df.iterrows():
            name = norm(r.get("Société",""))
            lat = r.get("Latitude","")
            lon = r.get("Longitude","")
            try:
                latf = float(lat); lonf = float(lon)
                if name:
                    geolook[name.lower()] = (latf, lonf)
            except Exception:
                pass
    return geolook

def haversine_km(lat1, lon1, lat2, lon2):
    R = 6371.0
    import math
    phi1 = math.radians(lat1); phi2 = math.radians(lat2)
    dphi = math.radians(lat2-lat1); dlambda = math.radians(lon2-lon1)
    a = (math.sin(dphi/2)**2 +
         math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2)
    c = 2*math.atan2(math.sqrt(a), math.sqrt(1-a))
    return R*c

def get_coords(name, country, geolook):
    if name and name.lower() in geolook:
        return geolook[name.lower()]
    if country in COUNTRY_CENTROIDS:
        return COUNTRY_CENTROIDS[country]
    return (0.0, 0.0)

def extract_tiers(record):
    tiers = []
    transport = record.get("transport") or {}
    # modes globaux par leg (optionnels)
    modes_to_first = transport.get("to_first_transformation", {}).get("modes", [])
    modes_to_safran = transport.get("from_supplier_to_safran", {}).get("modes", [])
    # mine_to_refinery non utilisé dans le graphe actuel (pas de leg explicite)

    sup = record.get("suppliers", {})
    mapping = [
        ("primary_material","Matière 1ère"),
        ("raw_material","Matière 1ère"),
        ("first_transformation","1ère transformation"),
        ("tier1","Tier 1")
    ]
    for key, role in mapping:
        arr = []
        if isinstance(sup, dict):
            arr = sup.get(key, []) or []
        for it in arr:
            if isinstance(it, dict):
                name = norm(it.get("name","")) or "(sans nom)"
                country = norm(it.get("location","")) or "Inconnu"
                modes = it.get("mode") or it.get("modes")
                if isinstance(modes, str):
                    modes = [m.strip() for m in modes.split(",") if m.strip()]
                elif not isinstance(modes, (list, tuple)):
                    modes = []
                # inject global transport hints if missing
                if not modes and role == "1ère transformation":
                    modes = modes_to_first if isinstance(modes_to_first, list) else []
                if not modes and role == "Tier 1":
                    modes = modes_to_safran if isinstance(modes_to_safran, list) else []
                tiers.append({"name": name, "country": country, "role": role, "modes": modes})
            elif isinstance(it, str) and it.strip():
                tiers.append({"name": it.strip(), "country": "Inconnu", "role": role, "modes": []})
    return tiers

def build_graph(records, geolook):
    nodes = {}
    edges = []  # (src_key, dst_key, distance_km, component, modes)
    def ensure_node(name, country, role):
        key = (name, role)
        if key in nodes:
            return key
        lat, lon = get_coords(name, country, geolook)
        nodes[key] = {"name": name, "country": country, "role": role, "lat": lat, "lon": lon}
        return key

    for rec in records:
        component = norm(rec.get("component","")) or norm(rec.get("system",""))
        tiers = extract_tiers(rec)
        prim  = [t for t in tiers if t["role"]=="Matière 1ère"]
        first = [t for t in tiers if t["role"]=="1ère transformation"]
        tier1 = [t for t in tiers if t["role"]=="Tier 1"]
        safran_key = ensure_node("Safran", "France", "Client")

        pkeys = [ensure_node(t["name"], t["country"], t["role"]) for t in prim]
        fkeys = [ensure_node(t["name"], t["country"], t["role"]) for t in first]
        tkeys = [ensure_node(t["name"], t["country"], t["role"]) for t in tier1]
        p_modes = [t.get("modes", []) for t in prim]
        f_modes = [t.get("modes", []) for t in first]
        t_modes = [t.get("modes", []) for t in tier1]

        def add_edge(a, b, modes):
            sa = nodes[a]; sb = nodes[b]
            dist = haversine_km(sa["lat"], sa["lon"], sb["lat"], sb["lon"])
            edges.append((a, b, dist, component, modes))

        if pkeys and fkeys:
            for ia, a in enumerate(pkeys):
                for ib, b in enumerate(fkeys):
                    modes = p_modes[ia] or f_modes[ib]
                    add_edge(a,b, modes)
        if fkeys and tkeys:
            for ia, a in enumerate(fkeys):
                for ib, b in enumerate(tkeys):
                    modes = f_modes[ia] or t_modes[ib]
                    add_edge(a,b, modes)
        if tkeys:
            for ia, a in enumerate(tkeys):
                modes = t_modes[ia] or []
                add_edge(a, safran_key, modes)

    return nodes, edges
