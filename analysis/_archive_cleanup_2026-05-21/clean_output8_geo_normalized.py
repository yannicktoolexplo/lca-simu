#!/usr/bin/env python3
"""
Clean the supplier-level geography/tier model in output8_GEO_normalized.json.

This script is deliberately conservative:
- source-backed supplier/site fixes are applied directly;
- unverifiable bad coordinates are nulled rather than kept as false precision;
- OEM and logistics providers are moved out of the external supplier list;
- duplicates are merged and a single baseline primary supplier is selected per role.
"""

from __future__ import annotations

import copy
import csv
import datetime as dt
import json
import math
import re
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


BASE_DIR = Path(__file__).resolve().parent
INPUT_JSON = BASE_DIR / "output8_GEO_normalized.json"
OUTPUT_JSON = BASE_DIR / "output8_GEO_normalized_corrected.json"
CHANGES_CSV = BASE_DIR / "output8_GEO_normalized_corrected_changes.csv"
REPORT_MD = BASE_DIR / "output8_GEO_normalized_corrected_report.md"

CANONICAL_ROLES = {
    "tier4_raw_material",
    "tier3_first_transformation",
    "tier2_second_transformation",
    "tier1",
    "oem",
    "logistics",
}

COUNTRY_ALIASES = {
    "france": ("France", "FR"),
    "allemagne": ("Germany", "DE"),
    "germany": ("Germany", "DE"),
    "deutschland": ("Germany", "DE"),
    "japon": ("Japan", "JP"),
    "japan": ("Japan", "JP"),
    "usa": ("United States", "US"),
    "us": ("United States", "US"),
    "u s a": ("United States", "US"),
    "united states": ("United States", "US"),
    "etats unis": ("United States", "US"),
    "etats-unis": ("United States", "US"),
    "royaume uni": ("United Kingdom", "GB"),
    "royaume-uni": ("United Kingdom", "GB"),
    "uk": ("United Kingdom", "GB"),
    "angleterre": ("United Kingdom", "GB"),
    "united kingdom": ("United Kingdom", "GB"),
    "belgique": ("Belgium", "BE"),
    "belgium": ("Belgium", "BE"),
    "lituanie": ("Lithuania", "LT"),
    "lithuania": ("Lithuania", "LT"),
    "chine": ("China", "CN"),
    "china": ("China", "CN"),
    "inde": ("India", "IN"),
    "india": ("India", "IN"),
    "thailande": ("Thailand", "TH"),
    "thailand": ("Thailand", "TH"),
    "philippines": ("Philippines", "PH"),
    "autriche": ("Austria", "AT"),
    "austria": ("Austria", "AT"),
    "luxembourg": ("Luxembourg", "LU"),
    "canada": ("Canada", "CA"),
    "suede": ("Sweden", "SE"),
    "sweden": ("Sweden", "SE"),
    "finlande": ("Finland", "FI"),
    "finland": ("Finland", "FI"),
    "norvege": ("Norway", "NO"),
    "norway": ("Norway", "NO"),
    "danemark": ("Denmark", "DK"),
    "denmark": ("Denmark", "DK"),
    "pologne": ("Poland", "PL"),
    "poland": ("Poland", "PL"),
    "italie": ("Italy", "IT"),
    "italy": ("Italy", "IT"),
    "espagne": ("Spain", "ES"),
    "spain": ("Spain", "ES"),
    "portugal": ("Portugal", "PT"),
    "suisse": ("Switzerland", "CH"),
    "switzerland": ("Switzerland", "CH"),
    "pays bas": ("Netherlands", "NL"),
    "pays-bas": ("Netherlands", "NL"),
    "netherlands": ("Netherlands", "NL"),
    "bresil": ("Brazil", "BR"),
    "brazil": ("Brazil", "BR"),
    "mexique": ("Mexico", "MX"),
    "mexico": ("Mexico", "MX"),
}

COUNTRY_BOUNDS = {
    "France": (41.0, 52.5, -6.0, 10.5),
    "Germany": (47.0, 55.3, 5.0, 16.0),
    "Japan": (30.0, 46.5, 128.0, 146.5),
    "United States": (24.0, 50.5, -125.0, -66.0),
    "United Kingdom": (49.0, 61.5, -9.5, 2.5),
    "Belgium": (49.3, 51.6, 2.4, 6.6),
    "Lithuania": (53.5, 56.6, 20.5, 27.0),
    "China": (18.0, 54.0, 73.0, 135.5),
    "India": (6.0, 36.0, 68.0, 98.0),
    "Thailand": (5.0, 21.5, 97.0, 106.0),
    "Philippines": (4.0, 22.0, 116.0, 127.0),
    "Austria": (46.0, 49.5, 9.0, 18.0),
    "Luxembourg": (49.3, 50.3, 5.5, 6.7),
    "Canada": (42.0, 84.0, -142.0, -52.0),
    "Sweden": (55.0, 70.5, 10.0, 25.0),
    "Finland": (59.0, 70.5, 19.0, 32.0),
    "Norway": (57.0, 72.0, 4.0, 32.0),
    "Denmark": (54.0, 58.5, 8.0, 16.0),
    "Poland": (49.0, 55.0, 14.0, 25.0),
    "Italy": (35.0, 48.0, 6.0, 19.0),
    "Spain": (35.0, 44.5, -10.0, 5.0),
    "Portugal": (36.0, 42.5, -10.0, -6.0),
    "Switzerland": (45.5, 48.0, 5.5, 11.0),
    "Netherlands": (50.5, 54.0, 3.0, 7.5),
    "Brazil": (-34.0, 6.0, -74.0, -34.0),
    "Mexico": (14.0, 33.0, -118.0, -86.0),
}

COUNTRY_CENTROIDS = {
    "France": (46.2276, 2.2137),
    "Germany": (51.1657, 10.4515),
    "Japan": (36.2048, 138.2529),
    "United States": (39.7837304, -100.4458825),
    "United Kingdom": (55.3781, -3.4360),
    "Belgium": (50.5039, 4.4699),
    "Lithuania": (55.1694, 23.8813),
    "China": (35.8617, 104.1954),
    "India": (20.5937, 78.9629),
    "Thailand": (15.8700, 100.9925),
    "Philippines": (12.8797, 121.7740),
    "Austria": (47.5162, 14.5501),
    "Luxembourg": (49.8153, 6.1296),
    "Canada": (56.1304, -106.3468),
    "Sweden": (60.1282, 18.6435),
    "Finland": (61.9241, 25.7482),
    "Denmark": (56.2639, 9.5018),
    "Brazil": (-14.2350, -51.9253),
}

TRANSPORT_MODE_ALIASES = {
    "camion": "truck",
    "bateau": "ship",
    "train": "rail",
    "avion": "air",
    "pipeline": "pipeline",
}

LOGISTICS_PATTERNS = (
    r"kuehne",
    r"nagel",
    r"\bgeodis\b",
    r"\bxpo\b",
    r"ceva",
)


def norm(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value or "").lower()).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


def slug(value: Any) -> str:
    return norm(value).replace(" ", "_")


def normalize_country(value: Any) -> tuple[str | None, str | None]:
    key = norm(value)
    if not key:
        return None, None
    return COUNTRY_ALIASES.get(key, (str(value).strip(), None))


def to_float(value: Any) -> float | None:
    if value in (None, "", "None"):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number):
        return None
    return number


def inside_country(lat: Any, lon: Any, country: str | None) -> bool | None:
    lat_f = to_float(lat)
    lon_f = to_float(lon)
    if lat_f is None or lon_f is None:
        return None
    bounds = COUNTRY_BOUNDS.get(country or "")
    if not bounds:
        return None
    min_lat, max_lat, min_lon, max_lon = bounds
    return min_lat <= lat_f <= max_lat and min_lon <= lon_f <= max_lon


def is_country_centroid(lat: Any, lon: Any, country: str | None) -> bool:
    lat_f = to_float(lat)
    lon_f = to_float(lon)
    if lat_f is None or lon_f is None or not country:
        return False
    centroid = COUNTRY_CENTROIDS.get(country)
    if not centroid:
        return False
    return abs(lat_f - centroid[0]) <= 0.05 and abs(lon_f - centroid[1]) <= 0.05


def source_fix(
    pattern: str,
    canonical: str,
    country: str,
    country_code: str,
    lat: float,
    lon: float,
    address: str,
    source_id: str,
    role_hint: str | None = None,
    confidence: str = "high",
) -> dict[str, Any]:
    return {
        "pattern": re.compile(pattern, re.I),
        "canonical": canonical,
        "country": country,
        "country_code": country_code,
        "lat": lat,
        "lon": lon,
        "address": address,
        "source_id": source_id,
        "role_hint": role_hint,
        "confidence": confidence,
    }


SOURCE_FIXES = [
    source_fix(r"jamco niigata", "JAMCO Aircraft Interiors - Niigata", "Japan", "JP", 38.0218, 139.4275, "341-1 Kamitsubone, Tsubone, Murakami, Niigata 958-0822, Japan", "SRC_JAMCO_001", "tier1"),
    source_fix(r"jamco miyazaki", "JAMCO Aircraft Interiors - Miyazaki", "Japan", "JP", 31.8961, 131.3429, "8136-7 Tanocho-ko, Miyazaki 889-1701, Japan", "SRC_JAMCO_001", "tier1"),
    source_fix(r"jamco philippines|jamco clark", "JAMCO Philippines Inc.", "Philippines", "PH", 15.1858, 120.5615, "N7000 Gil Puyat Avenue, Clark Civil Aviation Complex, Pampanga, Philippines", "SRC_JAMCO_001", "tier1"),
    source_fix(r"\bjamco\b", "JAMCO Aircraft Interiors", "Japan", "JP", 38.0218, 139.4275, "JAMCO Niigata site fallback, Japan", "SRC_JAMCO_001", "tier1", "medium_high"),
    source_fix(r"mgr foamtex", "MGR Foamtex Ltd", "United Kingdom", "GB", 51.739561, -0.966526, "DAX House, Wenman Road, Thame, Oxfordshire OX9 3SE, UK", "SRC_MGR_001"),
    source_fix(r"lauak", "Groupe LAUAK", "France", "FR", 43.3833153, -1.3279615, "2245 Route de Minhotz, 64240 Hasparren, France", "SRC_LAUAK_001", "tier1"),
    source_fix(r"plastiservice", "Plastiservice Charleroi", "Belgium", "BE", 50.4524, 4.4446, "ZI de Jumet, Allee Centrale 72, B-6040 Charleroi, Belgium", "SRC_PLASTISERVICE_001", "tier2_second_transformation"),
    source_fix(r"j\s*&\s*c aero|j c aero|jc aero", "J&C Aero", "Lithuania", "LT", 54.6329, 25.2778, "Vilties st. 11, Kuprioniskes, Vilnius, Lithuania, LT13279", "SRC_JCAERO_001", "tier1"),
    source_fix(r"stelia|airbus atlant|airbus atlantic", "Airbus Atlantic / STELIA Aerospace", "France", "FR", 45.9360, -0.9650, "Rochefort, France", "SRC_STELIA_AIRBUS_001", None, "medium_high"),
    source_fix(r"\bsafran\b", "Safran Seats / Safran internal group", "France", "FR", 48.8125, 1.9495, "61 Rue Pierre Curie, 78373 Plaisir, France", "SRC_SAFRAN_SEATS_001", "oem"),
    source_fix(r"figeac", "Figeac Aero", "France", "FR", 44.590773, 2.0333182, "Zone industrielle de l'Aiguille, 46100 Figeac, France", "SRC_FIGEAC_001", "tier1"),
    source_fix(r"gattefin", "ETS Gattefin", "France", "FR", 47.1426393, 2.2372016, "201 Av. Raoul Aladenize, 18500 Mehun-sur-Yevre, France", "SRC_GATTEFIN_001", "tier1"),
    source_fix(r"segner|segnere", "Groupe Segnere / SEGNERE Ade", "France", "FR", 43.1576, -0.0191, "Z.I. du Toulicou, Ade, Occitanie 65100, France", "SRC_SEGNERE_001", "tier1", "medium_high"),
    source_fix(r"celso", "Celso SAS", "France", "FR", 43.9363, 1.3228, "200 impasse de Fontanilles, ZI de Bressols, 82710 Bressols, France", "SRC_CELSO_001", None),
    source_fix(r"\bach\b", "ACH", "France", "FR", 46.5802, 0.3404, "16 rue Marcellin Berthelot, Zone Pole Republique 3, 86000 Poitiers, France", "SRC_ACH_001", None),
    source_fix(r"exsto|baule|baul", "EXSTO / Baule-Exsto Polymere", "France", "FR", 45.0506, 5.0835, "55 avenue de la Deportation, 26100 Romans-sur-Isere, France", "SRC_EXSTO_001", "tier3_first_transformation"),
    source_fix(r"ancra", "Ancra International", "United States", "US", 34.1230, -117.9080, "601 S Vincent Ave, Azusa, CA 91702, USA", "SRC_ANCRA_001", "tier1"),
    source_fix(r"ta aerospace", "TA Aerospace", "United States", "US", 34.4280, -118.5610, "Valencia, California, USA", "SRC_TA_001", "tier1", "medium"),
    source_fix(r"e2ip", "e2ip technologies", "Canada", "CA", 45.4550, -73.7350, "1455, 32nd Avenue, Lachine, QC H8T 3J1, Canada", "SRC_E2IP_001", "tier2_second_transformation"),
    source_fix(r"thyssen|thyssenkrupp", "thyssenkrupp Materials France", "France", "FR", 48.758488, 1.925304, "Z.A Pariwest, 6 av. Gutenberg, 78310 Maurepas, France", "SRC_THYSSEN_001", "tier3_first_transformation"),
    source_fix(r"euralliage", "Euralliage Ile de France", "France", "FR", 48.9860, 2.4490, "3 rue des freres Montgolfier, ZI des Cressonnieres, 95500 Gonesse, France", "SRC_EURALLIAGE_001", "tier3_first_transformation"),
    source_fix(r"tata steel", "Tata Steel", "India", "IN", 22.7853607, 86.1994836, "Jamshedpur, India fallback; choose actual India plant from traceability", "SRC_TATA_STEEL_001", "tier4_raw_material", "medium_high"),
    source_fix(r"dupont", "DuPont de Nemours", "United States", "US", 39.7391, -75.5398, "Wilmington, Delaware, USA fallback; choose product/site from traceability", "SRC_DUPONT_001", "tier2_second_transformation", "medium_high"),
    source_fix(r"nordic paper", "Nordic Paper", "Sweden", "SE", 59.1320, 12.9280, "Saffle/Amotfors/Backhammar, Sweden fallback; choose actual mill", "SRC_NORDIC_PAPER_001", None),
    source_fix(r"schroth", "SCHROTH Safety Products", "United States", "US", 26.1800, -80.1900, "5320 NW 35th Ave, Fort Lauderdale, FL 33309, USA", "SRC_SCHROTH_001", "tier2_second_transformation"),
    source_fix(r"anjou aero|anjou aeronautique", "Anjou Aeronautique", "France", "FR", 48.9760, 2.0320, "4 Rue Eugene Freyssinet, 78570 Chanteloup-les-Vignes, France", "SRC_ANJOU_001", "tier1"),
    source_fix(r"senior aerospace", "Senior Aerospace Thailand", "Thailand", "TH", 13.0914, 101.0108, "789/115-116 Moo 1, Nhongkham Sriracha, Chonburi 20230, Thailand", "SRC_SENIOR_THAILAND_001", "tier1"),
    source_fix(r"sumpar", "SUMPAR", "France", "FR", 49.3892868, 1.2085766, "134 Rue de la Forge Feret, 76520 Boos, France", "SRC_SUMPAR_001", "tier1"),
    source_fix(r"am safe|amsafe", "AmSafe", "United States", "US", 33.4560, -112.1600, "1043 N. 47th Avenue, Phoenix, Arizona 85043, USA", "SRC_AMSAFE_001", "tier1"),
    source_fix(r"alcoa", "Alcoa", "United States", "US", 40.4406, -79.9959, "Pittsburgh, Pennsylvania, USA fallback; choose actual commodity site", "SRC_ALCOA_001", "tier4_raw_material", "medium_high"),
    source_fix(r"constellium", "Constellium", "France", "FR", 45.3094248, 5.607597, "C-TEC Voreppe, France fallback; choose actual production site", "SRC_CONSTELLIUM_001", "tier3_first_transformation", "medium_high"),
    source_fix(r"austria metall|\bamag\b", "AMAG Austria Metall", "Austria", "AT", 48.2266686, 13.0356549, "Lamprechtshausener Strasse 61, 5282 Ranshofen, Austria", "SRC_AMAG_001", "tier3_first_transformation"),
    source_fix(r"toray", "Toray Industries", "Japan", "JP", 35.6866, 139.7746, "Tokyo 103-8666, Japan fallback; choose actual production site", "SRC_TORAY_001", None, "medium_high"),
    source_fix(r"arcelor mittal|arcelormittal", "ArcelorMittal", "Luxembourg", "LU", 49.6116, 6.1319, "24-26 boulevard d Avranches, L-1160 Luxembourg fallback; choose actual steel plant", "SRC_ARCELORMITTAL_001", "tier4_raw_material", "medium_high"),
    source_fix(r"basf", "BASF", "Germany", "DE", 49.4810, 8.4350, "Ludwigshafen am Rhein, Germany", "SRC_BASF_001", "tier4_raw_material", "medium_high"),
    source_fix(r"hindalco", "Hindalco Industries", "India", "IN", 19.0760, 72.8777, "Mumbai corporate office fallback; choose actual India plant", "SRC_HINDALCO_001", "tier4_raw_material", "medium_high"),
    source_fix(r"china baowu|baowu", "China Baowu / Baosteel", "China", "CN", 31.2304, 121.4737, "Baosteel Tower, Shanghai fallback; choose actual steel plant", "SRC_BAOWU_001", "tier4_raw_material", "medium"),
    source_fix(r"aluminium corporation of china|chalco", "Aluminium Corporation of China / Chalco", "China", "CN", 39.9042, 116.4074, "Beijing fallback; choose actual smelter/refinery", "", "tier4_raw_material", "low"),
    source_fix(r"nucor", "Nucor Corp", "United States", "US", 35.2271, -80.8431, "Charlotte, North Carolina, USA fallback; choose actual mill", "", "tier4_raw_material", "low"),
    source_fix(r"mitsubishi chemical", "Mitsubishi Chemical", "Japan", "JP", 35.6812, 139.7671, "Tokyo fallback; choose actual chemical site", "", "tier4_raw_material", "low"),
    source_fix(r"aubert|duval", "Aubert & Duval", "France", "FR", 45.7772, 3.0870, "Aubiere/Clermont-Ferrand fallback; choose actual industrial site", "SRC_AUBERT_001", "tier3_first_transformation", "medium_high"),
]


def match_source_fix(entry: dict[str, Any]) -> dict[str, Any] | None:
    text = " ".join(
        [
            norm(entry.get("name")),
            norm(entry.get("supplier")),
            norm(entry.get("geocode_query")),
            norm(entry.get("description")),
        ]
    )
    for fix in SOURCE_FIXES:
        if fix["pattern"].search(text):
            if fix["canonical"] == "SCHROTH Safety Products":
                country, _ = normalize_country(entry.get("location"))
                if country == "Germany":
                    adjusted = dict(fix)
                    adjusted.update(
                        {
                            "country": "Germany",
                            "country_code": "DE",
                            "lat": 51.3970,
                            "lon": 8.0640,
                            "address": "Arnsberg, Germany",
                        }
                    )
                    return adjusted
            return fix
    return None


def clean_role_hint(entry: dict[str, Any], fix: dict[str, Any] | None) -> str:
    role = str(entry.get("role_hint") or entry.get("role") or "").strip()
    role_norm = role if role in CANONICAL_ROLES else norm(role)
    if role_norm in CANONICAL_ROLES:
        return role_norm
    if fix and fix.get("role_hint") in CANONICAL_ROLES - {"oem", "logistics"}:
        return str(fix["role_hint"])
    if role_norm == "material":
        return "tier4_raw_material"
    if role_norm == "transformation":
        return "tier3_first_transformation"
    desc = norm(entry.get("description"))
    if any(word in desc for word in ("matiere premiere", "raw material", "acier primaire", "aluminium primaire")):
        return "tier4_raw_material"
    if any(word in desc for word in ("laminage", "extrusion", "fonderie", "forge", "premiere transformation")):
        return "tier3_first_transformation"
    return role or "tier1"


def infer_raw_materials(record: dict[str, Any]) -> tuple[list[str], str]:
    existing = record.get("raw_materials")
    if isinstance(existing, list) and existing:
        return existing, "provided"
    text = norm(f"{record.get('component', '')} {record.get('system', '')}")
    rules = [
        (("aluminium", "alu", "a5086", "a2017", "a2024", "a6060"), "Aluminium"),
        (("acier", "steel", "inox", "z10cnt18", "15cdv6", "30ncd6", "35nc6", "4140"), "Steel"),
        (("titane",), "Titanium"),
        (("cuir", "ultra leather"), "Leather / synthetic leather"),
        (("tissu", "velours", "pa6 6", "nylon"), "Textile / nylon"),
        (("polyurethane", "polyurethane", "mousse", "foam", "frmc55"), "Polyurethane foam"),
        (("silicone",), "Silicone"),
        (("caoutchouc", "polychloroprene"), "Rubber / polychloroprene"),
        (("kydex", "lexan", "plastique", "ertalon", "moulage plastique"), "Engineering plastic"),
        (("resine", "composite", "fibre de carbone"), "Composite resin / carbon fiber"),
        (("cable", "clavier", "powerbox", "display", "ecran", "telecommande"), "Electronics / electrical assemblies"),
        (("alliage cu", "cuivre"), "Copper alloy"),
    ]
    inferred = [material for tokens, material in rules if any(token in text for token in tokens)]
    if inferred:
        return list(dict.fromkeys(inferred)), "inferred_from_component_label"
    return [], "missing_source"


def normalize_transport(record: dict[str, Any], changes: list[dict[str, Any]], record_index: int) -> None:
    transport = record.get("transport")
    if not isinstance(transport, dict):
        return
    for leg, payload in transport.items():
        if not isinstance(payload, dict):
            continue
        raw_modes = payload.get("modes")
        if not isinstance(raw_modes, list):
            continue
        original = list(raw_modes)
        modes: list[str] = []
        internal_transfer = False
        for mode in raw_modes:
            key = norm(mode)
            if key == "interne entreprise":
                internal_transfer = True
                continue
            canonical = TRANSPORT_MODE_ALIASES.get(key)
            if canonical and canonical not in modes:
                modes.append(canonical)
        payload["modes_original"] = original
        payload["modes"] = modes
        if internal_transfer:
            payload["internal_transfer"] = True
        if original != modes:
            changes.append(change_row(record_index, record, "", "", "normalize_transport", f"{leg}: {original} -> {modes}"))


def change_row(record_index: int, record: dict[str, Any], supplier: str, role: str, action: str, detail: str) -> dict[str, Any]:
    return {
        "record_index": record_index,
        "system": record.get("system", ""),
        "component": record.get("component", ""),
        "supplier": supplier,
        "role_hint": role,
        "action": action,
        "detail": detail,
    }


def merge_supplier(existing: dict[str, Any], incoming: dict[str, Any]) -> None:
    existing["is_primary"] = bool(existing.get("is_primary")) or bool(incoming.get("is_primary"))
    for field in ("description", "correction_notes"):
        values = []
        for item in (existing.get(field), incoming.get(field)):
            if isinstance(item, list):
                values.extend(str(x) for x in item if x)
            elif item:
                values.append(str(item))
        existing[field] = list(dict.fromkeys(values)) if field == "correction_notes" else "; ".join(dict.fromkeys(values))
    for field in ("source_ids",):
        values = []
        for item in (existing.get(field), incoming.get(field)):
            if isinstance(item, list):
                values.extend(str(x) for x in item if x)
            elif item:
                values.append(str(item))
        existing[field] = list(dict.fromkeys(values))
    if not existing.get("site_address") and incoming.get("site_address"):
        existing["site_address"] = incoming["site_address"]


def clean_supplier(entry: dict[str, Any], record: dict[str, Any], record_index: int, changes: list[dict[str, Any]]) -> tuple[dict[str, Any], str]:
    original = copy.deepcopy(entry)
    name = str(entry.get("name") or entry.get("supplier") or "").strip()
    role_hint = clean_role_hint(entry, None)
    location, country_code = normalize_country(entry.get("location") or entry.get("country"))
    fix = match_source_fix(entry)
    role_hint = clean_role_hint(entry, fix)

    cleaned = copy.deepcopy(entry)
    cleaned["name"] = name
    cleaned["role_hint"] = role_hint
    cleaned.pop("role", None)

    notes: list[str] = []
    source_ids: list[str] = []

    if fix:
        if fix["canonical"] != name:
            notes.append(f"name_normalized:{name}->{fix['canonical']}")
        if location != fix["country"]:
            notes.append(f"country_normalized:{location}->{fix['country']}")
        cleaned.update(
            {
                "name": fix["canonical"],
                "location": fix["country"],
                "country_code": fix["country_code"],
                "lat": fix["lat"],
                "lon": fix["lon"],
                "geocode_provider": "manual:source_registry" if fix.get("source_id") else "manual:cleanup_rule",
                "geocode_query": fix["address"],
                "site_address": fix["address"],
                "geocode_status": "source_backed_site" if fix.get("source_id") else "fallback_site_needs_source",
                "source_confidence": fix["confidence"],
            }
        )
        if fix.get("source_id"):
            source_ids.append(str(fix["source_id"]))
        if fix.get("role_hint") in CANONICAL_ROLES - {"oem", "logistics"} and role_hint != fix["role_hint"]:
            cleaned["role_hint"] = fix["role_hint"]
            notes.append(f"role_normalized:{role_hint}->{fix['role_hint']}")
    else:
        cleaned["location"] = location or cleaned.get("location") or ""
        cleaned["country_code"] = country_code
        lat = to_float(cleaned.get("lat"))
        lon = to_float(cleaned.get("lon"))
        cleaned["lat"] = lat
        cleaned["lon"] = lon
        if location and (inside_country(lat, lon, location) is False or is_country_centroid(lat, lon, location)):
            cleaned["lat"] = None
            cleaned["lon"] = None
            cleaned["geocode_status"] = "needs_verified_site"
            notes.append("coordinates_removed_unverified_or_centroid")
        elif lat is not None and lon is not None:
            cleaned["geocode_status"] = "kept_from_source_json"
        else:
            cleaned["geocode_status"] = "missing_coordinates"

    if cleaned.get("role_hint") not in CANONICAL_ROLES:
        before = cleaned.get("role_hint")
        cleaned["role_hint"] = "tier1"
        notes.append(f"role_defaulted:{before}->tier1")

    if cleaned.get("source_ids"):
        existing_ids = cleaned["source_ids"] if isinstance(cleaned["source_ids"], list) else [cleaned["source_ids"]]
        source_ids.extend(str(x) for x in existing_ids if x)
    cleaned["source_ids"] = list(dict.fromkeys(source_ids))
    cleaned["supplier_id"] = slug(cleaned["name"])
    if cleaned.get("lat") is not None and cleaned.get("lon") is not None:
        cleaned["site_id"] = f"{cleaned['supplier_id']}@{round(float(cleaned['lat']), 4)},{round(float(cleaned['lon']), 4)}"
    else:
        cleaned["site_id"] = f"{cleaned['supplier_id']}@unverified"

    if notes:
        cleaned["correction_notes"] = list(dict.fromkeys(notes))
    changed = any(
        cleaned.get(key) != original.get(key)
        for key in ("name", "location", "role_hint", "lat", "lon", "geocode_provider", "geocode_query")
    )
    if changed:
        cleaned["original_supplier"] = {
            "name": original.get("name"),
            "location": original.get("location"),
            "role_hint": original.get("role_hint"),
            "lat": original.get("lat"),
            "lon": original.get("lon"),
            "geocode_provider": original.get("geocode_provider"),
            "geocode_query": original.get("geocode_query"),
        }
        changes.append(
            change_row(
                record_index,
                record,
                name,
                str(entry.get("role_hint") or ""),
                "clean_supplier",
                "; ".join(notes) or "source/site normalization",
            )
        )
    target = "supplier"
    text = norm(cleaned.get("name"))
    if cleaned.get("role_hint") == "logistics" or any(re.search(pattern, text) for pattern in LOGISTICS_PATTERNS):
        target = "logistics"
    if cleaned.get("role_hint") == "oem" or text.startswith("safran"):
        target = "oem"
    return cleaned, target


def dedupe_entries(entries: list[dict[str, Any]], record: dict[str, Any], record_index: int, changes: list[dict[str, Any]], target_name: str) -> list[dict[str, Any]]:
    merged: dict[tuple[str, str, str], dict[str, Any]] = {}
    order: list[tuple[str, str, str]] = []
    for entry in entries:
        key = (str(entry.get("supplier_id") or slug(entry.get("name"))), str(entry.get("role_hint") or ""), str(entry.get("site_id") or ""))
        if key in merged:
            merge_supplier(merged[key], entry)
            changes.append(change_row(record_index, record, entry.get("name", ""), entry.get("role_hint", ""), f"dedupe_{target_name}", "merged duplicate supplier/site/role entry"))
        else:
            merged[key] = entry
            order.append(key)
    return [merged[key] for key in order]


def resolve_primary_suppliers(entries: list[dict[str, Any]], record: dict[str, Any], record_index: int, changes: list[dict[str, Any]]) -> None:
    by_role: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for entry in entries:
        by_role[str(entry.get("role_hint") or "")].append(entry)
    for role, group in by_role.items():
        if not group:
            continue
        primaries = [entry for entry in group if entry.get("is_primary")]
        if not primaries:
            chosen = group[0]
            chosen["is_primary"] = True
            chosen["primary_selection_basis"] = "inferred_first_available_no_source"
            changes.append(change_row(record_index, record, chosen.get("name", ""), role, "infer_primary_supplier", "no primary supplier in role; selected first available baseline supplier"))
        elif len(primaries) > 1:
            chosen = primaries[0]
            chosen["primary_selection_basis"] = "kept_first_primary_no_share_source"
            for other in primaries[1:]:
                other["is_primary"] = False
                other["supplier_status"] = "alternate_requires_allocation_source"
                notes = list(other.get("correction_notes") or [])
                notes.append("multiple_primary_resolved_to_alternate")
                other["correction_notes"] = list(dict.fromkeys(notes))
            changes.append(change_row(record_index, record, chosen.get("name", ""), role, "resolve_multiple_primary", f"kept {chosen.get('name')} as baseline primary; {len(primaries)-1} suppliers retained as alternatives"))
        for entry in group:
            if entry.get("is_primary"):
                entry["allocation_share_pct"] = 100.0
                entry["supplier_status"] = "baseline_primary"
            else:
                entry.setdefault("allocation_share_pct", 0.0)
                entry.setdefault("supplier_status", "alternate")


def clean_record(record: dict[str, Any], record_index: int, changes: list[dict[str, Any]], counters: Counter) -> dict[str, Any]:
    out = copy.deepcopy(record)

    if out.get("market_share_pct") in ("", None):
        out["market_share_pct"] = None
        out["market_share_status"] = "missing_source"
        counters["market_share_nulled"] += 1

    if to_float(out.get("mass_kg")) == 0.0:
        out["mass_kg"] = None
        out["mass_status"] = "missing_source_zero_removed"
        counters["mass_zero_nulled"] += 1
    elif out.get("mass_kg") not in (None, ""):
        out["mass_status"] = "provided"

    raw_materials, raw_status = infer_raw_materials(out)
    if raw_materials != out.get("raw_materials"):
        counters["raw_materials_inferred" if raw_status.startswith("inferred") else "raw_materials_missing"] += 1
    out["raw_materials"] = raw_materials
    out["raw_materials_status"] = raw_status

    normalize_transport(out, changes, record_index)

    suppliers = out.get("suppliers") or []
    cleaned_suppliers: list[dict[str, Any]] = []
    oem_sites: list[dict[str, Any]] = list(out.get("oem_sites") or [])
    logistics_providers: list[dict[str, Any]] = list(out.get("logistics_providers") or [])
    for entry in suppliers:
        if not isinstance(entry, dict):
            continue
        cleaned, target = clean_supplier(entry, out, record_index, changes)
        if target == "oem":
            oem_sites.append(cleaned)
            counters["oem_moved"] += 1
            changes.append(change_row(record_index, out, cleaned.get("name", ""), cleaned.get("role_hint", ""), "move_oem_out_of_suppliers", "OEM/internal integrator moved to oem_sites"))
        elif target == "logistics":
            logistics_providers.append(cleaned)
            counters["logistics_moved"] += 1
            changes.append(change_row(record_index, out, cleaned.get("name", ""), cleaned.get("role_hint", ""), "move_logistics_out_of_suppliers", "logistics provider moved to logistics_providers"))
        else:
            cleaned_suppliers.append(cleaned)

    out["suppliers"] = dedupe_entries(cleaned_suppliers, out, record_index, changes, "supplier")
    out["oem_sites"] = dedupe_entries(oem_sites, out, record_index, changes, "oem")
    out["logistics_providers"] = dedupe_entries(logistics_providers, out, record_index, changes, "logistics")
    resolve_primary_suppliers(out["suppliers"], out, record_index, changes)
    resolve_primary_suppliers(out["oem_sites"], out, record_index, changes)

    out["cleanup_status"] = {
        "baseline_primary_policy": "single primary per record and role; alternates retained with allocation_share_pct=0 until share source is available",
        "coordinates_policy": "source-backed or plausible coordinates kept; unverifiable centroids/out-of-country coordinates nulled",
    }
    return out


def audit_cleaned(records: list[dict[str, Any]]) -> Counter:
    audit = Counter()
    for record in records:
        audit["records"] += 1
        audit["suppliers"] += len(record.get("suppliers") or [])
        audit["oem_sites"] += len(record.get("oem_sites") or [])
        audit["logistics_providers"] += len(record.get("logistics_providers") or [])
        if record.get("market_share_pct") is None:
            audit["market_share_missing"] += 1
        if record.get("mass_kg") is None:
            audit["mass_missing"] += 1
        if not record.get("raw_materials"):
            audit["raw_materials_missing"] += 1
        role_groups = defaultdict(list)
        for supplier in record.get("suppliers") or []:
            role = supplier.get("role_hint")
            role_groups[role].append(supplier)
            lat = supplier.get("lat")
            lon = supplier.get("lon")
            country = supplier.get("location")
            if lat is None or lon is None:
                audit["supplier_coordinates_missing"] += 1
            elif inside_country(lat, lon, country) is False:
                audit["supplier_coordinates_outside_country"] += 1
            elif is_country_centroid(lat, lon, country):
                audit["supplier_country_centroid"] += 1
        for group in role_groups.values():
            if sum(1 for supplier in group if supplier.get("is_primary")) != 1:
                audit["roles_without_single_primary"] += 1
    return audit


def write_changes(rows: list[dict[str, Any]]) -> None:
    fields = ["record_index", "system", "component", "supplier", "role_hint", "action", "detail"]
    with CHANGES_CSV.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def write_report(before: dict[str, Any], after: dict[str, Any], counters: Counter, audit: Counter, changes_count: int) -> None:
    before_records = before.get("records") or []
    after_records = after.get("records") or []
    before_supplier_count = sum(len(record.get("suppliers") or []) for record in before_records)
    lines = [
        "# Corrected output8_GEO_normalized.json",
        "",
        f"- Source: `{INPUT_JSON.as_posix()}`",
        f"- Corrected JSON: `{OUTPUT_JSON.as_posix()}`",
        f"- Changes CSV: `{CHANGES_CSV.as_posix()}`",
        f"- Generated at: `{after.get('_meta', {}).get('generated_at')}`",
        "",
        "## Scope",
        "",
        f"- Records: {len(before_records)} -> {len(after_records)}",
        f"- Supplier entries in original `suppliers`: {before_supplier_count}",
        f"- Supplier entries after cleaning: {audit['suppliers']}",
        f"- OEM/internal site entries moved to `oem_sites`: {audit['oem_sites']}",
        f"- Logistics entries moved to `logistics_providers`: {audit['logistics_providers']}",
        f"- Change log rows: {changes_count}",
        "",
        "## Main corrections",
        "",
        f"- Mass zeros changed to `null`: {counters['mass_zero_nulled']}",
        f"- Empty market shares changed to `null`: {counters['market_share_nulled']}",
        f"- Raw materials inferred from component labels: {counters['raw_materials_inferred']}",
        f"- OEM entries removed from external suppliers: {counters['oem_moved']}",
        f"- Logistics entries removed from external suppliers: {counters['logistics_moved']}",
        "",
        "## Remaining limitations",
        "",
        f"- Records with missing market share: {audit['market_share_missing']}",
        f"- Records with missing mass: {audit['mass_missing']}",
        f"- Supplier coordinates still missing because no verified site was available: {audit['supplier_coordinates_missing']}",
        f"- Supplier coordinates outside declared country after cleaning: {audit['supplier_coordinates_outside_country']}",
        f"- Supplier coordinates still at country centroid after cleaning: {audit['supplier_country_centroid']}",
        f"- Role groups without exactly one baseline primary supplier: {audit['roles_without_single_primary']}",
        "",
        "## Simulation readiness note",
        "",
        "The corrected file is cleaner for mapping and scenario design, but it is still not a full stress-test model. "
        "Before quantitative stress tests, fill `mass_kg`, `market_share_pct` or supplier allocation shares, lead times, capacities, safety stocks, and recovery assumptions from BOM/ERP/logistics sources.",
        "",
    ]
    REPORT_MD.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    raw = json.loads(INPUT_JSON.read_text(encoding="utf-8"))
    records = raw.get("records") if isinstance(raw, dict) else raw
    if not isinstance(records, list):
        raise ValueError("Expected JSON object with a records list")

    changes: list[dict[str, Any]] = []
    counters: Counter = Counter()
    cleaned_records = [clean_record(record, index, changes, counters) for index, record in enumerate(records, start=1)]
    cleaned = {
        "records": cleaned_records,
        "_meta": {
            "source_file": INPUT_JSON.as_posix(),
            "generated_at": dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat(),
            "cleaning_script": Path(__file__).as_posix(),
            "policy": {
                "original_file_left_unchanged": True,
                "unverified_bad_coordinates": "lat/lon set to null",
                "oem_and_logistics": "moved out of external suppliers",
                "primary_supplier": "single baseline primary per record and role; alternatives retained",
            },
        },
    }

    audit = audit_cleaned(cleaned_records)
    OUTPUT_JSON.write_text(json.dumps(cleaned, ensure_ascii=False, indent=2), encoding="utf-8")
    write_changes(changes)
    write_report(raw, cleaned, counters, audit, len(changes))

    print(f"[OK] wrote {OUTPUT_JSON}")
    print(f"[OK] wrote {CHANGES_CSV}")
    print(f"[OK] wrote {REPORT_MD}")
    print(f"[INFO] records={audit['records']} suppliers={audit['suppliers']} oem_sites={audit['oem_sites']} logistics={audit['logistics_providers']}")
    print(f"[INFO] missing_coords={audit['supplier_coordinates_missing']} out_of_country={audit['supplier_coordinates_outside_country']} centroids={audit['supplier_country_centroid']}")


if __name__ == "__main__":
    main()
