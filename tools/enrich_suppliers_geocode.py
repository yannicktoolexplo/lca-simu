#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Ajoute des lat/lon aux fournisseurs à partir du nom + pays via Nominatim (OpenStreetMap),
avec cache local et respect de la limite de requêtes.

Usage:
  python enrich_suppliers_geocode.py INPUT.json OUTPUT.json [--cache geocode_cache.json] [--overwrite]

- INPUT / OUTPUT : JSON au format LCA-SIMU (liste d'objets ou {"records": [...]})
- --cache : fichier JSON de cache (clé = "supplier|country", valeur = {"lat":..,"lon":..})
- --overwrite : réécrit lat/lon même si déjà présents dans l'entrée

Le script n'écrase pas le contenu hormis l'ajout de clés lat/lon (et métadonnées) dans suppliers[*].
"""

from __future__ import annotations
import json, time, argparse, sys
from pathlib import Path
from typing import Any, Dict, List, Tuple, Optional
import urllib.parse, urllib.request

# --- Mapping FR/EN (pour le champ "location")
COUNTRY_ALIASES = {
    "france": "France", "angleterre":"United Kingdom", "royaume-uni":"United Kingdom", "uk":"United Kingdom",
    "belgique":"Belgium", "allemagne":"Germany", "suede":"Sweden", "suède":"Sweden", "pologne":"Poland",
    "irlande":"Ireland", "autriche":"Austria", "italie":"Italy", "espagne":"Spain", "portugal":"Portugal",
    "chine":"China", "india":"India", "inde":"India", "japon":"Japan", "thailande":"Thailand", "thaïlande":"Thailand",
    "usa":"United States", "etats-unis":"United States", "états-unis":"United States", "canada":"Canada",
    "brazil":"Brazil", "brésil":"Brazil", "switzerland":"Switzerland", "suisse":"Switzerland",
    "pays-bas":"Netherlands", "netherlands":"Netherlands",
}

# --- Centroïdes pays (fallback)
COUNTRY_COORDS = {
    "France": (46.2276, 2.2137), "United Kingdom": (55.3781, -3.4360), "Belgium": (50.5039, 4.4699),
    "Germany": (51.1657, 10.4515), "Sweden": (60.1282, 18.6435), "Poland": (51.9194, 19.1451),
    "Ireland": (53.1424, -7.6921), "Austria": (47.5162, 14.5501), "Italy": (41.8719, 12.5674),
    "Spain": (40.4637, -3.7492), "Portugal": (39.3999, -8.2245), "China": (35.8617, 104.1954),
    "India": (20.5937, 78.9629), "Japan": (36.2048, 138.2529), "Thailand": (15.8700, 100.9925),
    "United States": (39.7837304, -100.4458825), "Canada": (56.1304, -106.3468), "Brazil": (-14.2350, -51.9253),
    "Switzerland": (46.8182, 8.2275), "Netherlands": (52.1326, 5.2913),
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
    """Retourne (records, wrapped). wrapped=True si l'input était {'records':[...]}"""
    raw = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(raw, dict) and "records" in raw:
        return list(raw["records"]), True
    if isinstance(raw, list):
        return raw, False
    raise ValueError("Le JSON doit être une liste ou un objet avec 'records'.")

def save_json(path: Path, records: List[Dict[str, Any]], wrapped: bool) -> None:
    out = {"records": records} if wrapped else records
    path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")

def open_cache(cache_path: Optional[Path]) -> Dict[str, Dict[str, float]]:
    if not cache_path or not cache_path.exists():
        return {}
    try:
        return json.loads(cache_path.read_text(encoding="utf-8"))
    except Exception:
        return {}

def save_cache(cache: Dict[str, Dict[str, float]], cache_path: Optional[Path]) -> None:
    if cache_path:
        cache_path.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")

def cache_key(supplier: str, country: Optional[str]) -> str:
    return f"{(supplier or '').strip().lower()}|{(country or '').strip().lower()}"

def nominatim_geocode(query: str, email_hint: str = "contact@example.com") -> Optional[Tuple[float,float]]:
    """
    Geocode via Nominatim. Respecter les conditions d'utilisation :
      - User-Agent + email (hint)
      - 1 requête par seconde minimum
    """
    base = "https://nominatim.openstreetmap.org/search"
    params = {
        "q": query,
        "format": "jsonv2",
        "limit": "1",
        "addressdetails": "0",
    }
    url = base + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={
        "User-Agent": f"LCA-SIMU-Geocoder/1.0 ({email_hint})"
    })
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read().decode("utf-8", errors="ignore"))
    if isinstance(data, list) and data:
        try:
            lat = float(data[0]["lat"]); lon = float(data[0]["lon"])
            return (lat, lon)
        except Exception:
            return None
    return None

def iter_supplier_entries(rec: Dict[str, Any], tiers: List[str]) -> List[Tuple[str, Dict[str, Any]]]:
    out = []
    suppliers = rec.get("suppliers") or {}
    for tier in tiers:
        lst = suppliers.get(tier, []) or []
        if isinstance(lst, list):
            for entry in lst:
                if isinstance(entry, dict):
                    out.append((tier, entry))
    return out

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("input")
    ap.add_argument("output")
    ap.add_argument("--cache", default="geocode_cache.json")
    ap.add_argument("--overwrite", action="store_true", help="Force la réécriture de lat/lon si déjà présents.")
    ap.add_argument("--email", default="contact@example.com", help="Email contact pour User-Agent Nominatim.")
    ap.add_argument("--sleep", type=float, default=1.1, help="Pause (s) entre requêtes pour le rate-limit (>= 1s).")
    args = ap.parse_args()

    in_path = Path(args.input)
    out_path = Path(args.output)
    cache_path = Path(args.cache) if args.cache else None

    try:
        records, wrapped = load_json(in_path)
    except Exception as e:
        print(f"[ERREUR] Lecture JSON: {e}", file=sys.stderr); sys.exit(1)

    cache = open_cache(cache_path)
    tiers_all = ["primary_material", "raw_material", "first_transformation", "tier1"]

    added, reused, fallback, skipped = 0, 0, 0, 0
    last_call = 0.0

    for rec in records:
        for tier, entry in iter_supplier_entries(rec, tiers_all):
            name = (entry.get("name") or entry.get("supplier") or "").strip()
            country_raw = entry.get("location") or entry.get("country")
            country = normalize_country(country_raw or "")

            # déjà présent ?
            if (not args.overwrite) and ("lat" in entry and "lon" in entry):
                skipped += 1
                continue

            # cache ?
            key = cache_key(name, country)
            if key in cache:
                entry["lat"] = cache[key]["lat"]
                entry["lon"] = cache[key]["lon"]
                entry["geocode_provider"] = "cache:nominatim"
                entry["geocode_query"] = f"{name}, {country}" if country else name
                reused += 1
                continue

            # si pas de pays, on tente quand même sur le nom brut (faible précision)
            q = f"{name}, {country}" if country else name
            # respect du rate-limit
            dt = time.time() - last_call
            if dt < args.sleep:
                time.sleep(args.sleep - dt)

            coords = None
            try:
                coords = nominatim_geocode(q, email_hint=args.email)
            except Exception as e:
                # en cas d'erreur réseau, on tentera fallback pays
                coords = None

            last_call = time.time()

            if coords:
                lat, lon = coords
                entry["lat"] = lat
                entry["lon"] = lon
                entry["geocode_provider"] = "nominatim"
                entry["geocode_query"] = q
                added += 1
                cache[key] = {"lat": lat, "lon": lon}
            else:
                # fallback centroïde pays si dispo
                if country and country in COUNTRY_COORDS:
                    lat, lon = COUNTRY_COORDS[country]
                    entry["lat"] = lat
                    entry["lon"] = lon
                    entry["geocode_provider"] = "country_centroid"
                    entry["geocode_query"] = q
                    entry["geo_fallback"] = "country_centroid"
                    fallback += 1
                    cache[key] = {"lat": lat, "lon": lon}
                else:
                    # pas de coords trouvées, on laisse tel quel
                    entry["geocode_provider"] = "none"
                    entry["geocode_query"] = q
                    skipped += 1

    save_cache(cache, cache_path)
    # Détection "modifié ou pas"
    modified = (added + reused + fallback) > 0
    save_json(out_path, records, wrapped)
    print(f"[OK] Écrit: {out_path.name} (modifié: {str(modified)})  "
          f"[added:{added} reused:{reused} fallback:{fallback} skipped:{skipped}]")

if __name__ == "__main__":
    main()
