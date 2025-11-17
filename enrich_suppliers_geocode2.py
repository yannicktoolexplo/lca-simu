#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Enrichit la géolocalisation des suppliers avec Nominatim (OpenStreetMap).

COMPORTEMENT CLÉ DEMANDÉ :
- Si tu enlèves lat/lon et modifies geocode_query, le script relance un géocodage
  en priorité avec le champ 'geocode_query' et écrit les nouvelles coordonnées.
- Si geocode_query est absent/vide, on utilise "supplier, country".
- Cache indexé par la requête (query string) => changer geocode_query => re-géocodage assuré.

Usage:
  python enrich_suppliers_geocode.py INPUT.json OUTPUT.json
      [--cache geocode_cache.json] [--sleep 1.2] [--email you@domain.tld] [--overwrite]

Options:
  --overwrite : force la réécriture même si lat/lon présents.
"""

from __future__ import annotations
import json, time, argparse, sys
from pathlib import Path
from typing import Any, Dict, List, Tuple, Optional
import urllib.parse, urllib.request

# --- Pays FR/EN -> normalisé
COUNTRY_ALIASES = {
    "france": "France","angleterre":"United Kingdom","royaume-uni":"United Kingdom","uk":"United Kingdom",
    "belgique":"Belgium","allemagne":"Germany","suede":"Sweden","suède":"Sweden","pologne":"Poland",
    "irlande":"Ireland","autriche":"Austria","italie":"Italy","espagne":"Spain","portugal":"Portugal",
    "chine":"China","india":"India","inde":"India","japon":"Japan","thailande":"Thailand","thaïlande":"Thailand",
    "usa":"United States","etats-unis":"United States","états-unis":"United States","canada":"Canada",
    "brazil":"Brazil","brésil":"Brazil","switzerland":"Switzerland","suisse":"Switzerland",
    "pays-bas":"Netherlands","netherlands":"Netherlands",
}

# --- ISO2 pour filtre Nominatim (facultatif)
ISO2 = {
    "France":"fr","United Kingdom":"gb","Belgium":"be","Germany":"de","Sweden":"se","Poland":"pl","Ireland":"ie",
    "Austria":"at","Italy":"it","Spain":"es","Portugal":"pt","China":"cn","India":"in","Japan":"jp","Thailand":"th",
    "United States":"us","Canada":"ca","Brazil":"br","Switzerland":"ch","Netherlands":"nl",
}

# --- Centroïdes pays (fallback)
COUNTRY_COORDS = {
    "France": (46.2276, 2.2137),"United Kingdom": (55.3781, -3.4360),"Belgium": (50.5039, 4.4699),
    "Germany": (51.1657, 10.4515),"Sweden": (60.1282, 18.6435),"Poland": (51.9194, 19.1451),
    "Ireland": (53.1424, -7.6921),"Austria": (47.5162, 14.5501),"Italy": (41.8719, 12.5674),
    "Spain": (40.4637, -3.7492),"Portugal": (39.3999, -8.2245),"China": (35.8617, 104.1954),
    "India": (20.5937, 78.9629),"Japan": (36.2048, 138.2529),"Thailand": (15.8700, 100.9925),
    "United States": (39.7837, -100.4459),"Canada": (56.1304, -106.3468),"Brazil": (-14.2350, -51.9253),
    "Switzerland": (46.8182, 8.2275),"Netherlands": (52.1326, 5.2913),
}

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

def load_json(path: Path) -> Tuple[List[Dict[str, Any]], bool]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(raw, dict) and "records" in raw:
        return list(raw["records"]), True
    if isinstance(raw, list):
        return raw, False
    raise ValueError("Le JSON doit être une liste ou {'records': [...]}")

def save_json(path: Path, records: List[Dict[str, Any]], wrapped: bool) -> None:
    out = {"records": records} if wrapped else records
    path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")

def open_cache(cache_path: Optional[Path]) -> Dict[str, Dict[str, float]]:
    if cache_path and cache_path.exists():
        try:
            return json.loads(cache_path.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}

def save_cache(cache: Dict[str, Dict[str, float]], cache_path: Optional[Path]) -> None:
    if cache_path:
        cache_path.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")

def nominatim_geocode(query: str, country_iso2: Optional[str], email_hint: str) -> Optional[Tuple[float,float,dict]]:
    base = "https://nominatim.openstreetmap.org/search"
    params = {
        "q": query,
        "format": "jsonv2",
        "limit": "1",
        "addressdetails": "1",  # permet d'inspecter le pays renvoyé
    }
    if country_iso2:
        params["countrycodes"] = country_iso2
    url = base + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": f"LCA-SIMU-Geocoder/1.0 ({email_hint})"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read().decode("utf-8", errors="ignore"))
    if isinstance(data, list) and data:
        it = data[0]
        try:
            lat = float(it["lat"]); lon = float(it["lon"])
            return lat, lon, it
        except Exception:
            return None
    return None

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("input")
    ap.add_argument("output")
    ap.add_argument("--cache", default="geocode_cache.json")
    ap.add_argument("--sleep", type=float, default=1.1, help="Pause entre requêtes (>=1s)")
    ap.add_argument("--email", default="contact@example.com", help="Email à mettre dans le User-Agent")
    ap.add_argument("--overwrite", action="store_true", help="Réécrit lat/lon même s'ils existent déjà")
    args = ap.parse_args()

    in_path, out_path = Path(args.input), Path(args.output)
    records, wrapped = load_json(in_path)

    cache_path = Path(args.cache) if args.cache else None
    cache = open_cache(cache_path)

    added, reused, centroid, skipped, upgraded = 0, 0, 0, 0, 0
    last_call = 0.0

    tiers_all = ["primary_material", "raw_material", "first_transformation", "tier1"]

    for rec in records:
        suppliers = rec.get("suppliers") or {}
        for tier in tiers_all:
            lst = suppliers.get(tier) or []
            if not isinstance(lst, list):
                continue
            for s in lst:
                if not isinstance(s, dict):
                    continue

                # Si coords déjà présentes et pas --overwrite => skip
                has_coords = isinstance(s.get("lat"), (int,float)) and isinstance(s.get("lon"), (int,float))
                if has_coords and not args.overwrite:
                    skipped += 1
                    continue

                name = (s.get("supplier") or s.get("name") or "").strip()
                country_raw = s.get("country") or s.get("location")
                country = normalize_country(country_raw or "")

                # 1) On détermine la QUERY A UTILISER
                #    - priorité à geocode_query si présent
                #    - sinon "name, country"
                q = (s.get("geocode_query") or "").strip()
                if not q:
                    q = f"{name}, {country}" if country else name

                # 2) Cache indexé PAR LA REQUÊTE (clé = q)
                if q in cache:
                    s["lat"] = cache[q]["lat"]
                    s["lon"] = cache[q]["lon"]
                    s["geocode_provider"] = cache[q].get("provider", "cache:nominatim")
                    s["geocode_query"] = q
                    reused += 1
                    continue

                # 3) Appel Nominatim (respecter rate-limit)
                dt = time.time() - last_call
                if dt < args.sleep:
                    time.sleep(args.sleep - dt)
                last_call = time.time()

                iso2 = ISO2.get(country) if country else None
                coords = None
                try:
                    coords = nominatim_geocode(q, iso2, args.email)
                except Exception:
                    coords = None

                if coords:
                    lat, lon, raw = coords
                    # Optionnel: si la réponse renvoie un country_code incohérent par rapport à 'country', on pourrait vérifier ici.
                    s["lat"], s["lon"] = lat, lon
                    s["geocode_provider"] = "nominatim"
                    s["geocode_query"] = q
                    cache[q] = {"lat": lat, "lon": lon, "provider": "nominatim"}
                    # upgraded si on remplaçait un centroïde, sinon added
                    upgraded += 1 if s.get("geocode_provider") == "country_centroid" else added + 1 and 0
                    if s.get("geocode_provider") != "country_centroid":
                        added += 1
                else:
                    # 4) Fallback centroïde pays si on a un pays
                    if country and country in COUNTRY_COORDS:
                        lat, lon = COUNTRY_COORDS[country]
                        s["lat"], s["lon"] = lat, lon
                        s["geocode_provider"] = "country_centroid"
                        s["geocode_query"] = q
                        centroid += 1
                        cache[q] = {"lat": lat, "lon": lon, "provider": "country_centroid"}
                    else:
                        # Rien trouvé et pas de pays → on laisse tel quel
                        skipped += 1

    save_cache(cache, cache_path)
    save_json(out_path, records, wrapped)

    modified = (added + reused + centroid + upgraded) > 0
    print(f"[OK] Écrit: {out_path.name} (modifié: {modified}) "
          f"[added:{added} upgraded:{upgraded} reused:{reused} centroid:{centroid} skipped:{skipped}]")

if __name__ == "__main__":
    main()

