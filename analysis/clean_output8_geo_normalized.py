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
    "France": (None, None),
    "Germany": (None, None),
    "Japan": (None, None),
    "United States": (None, None),
    "United Kingdom": (None, None),
    "Belgium": (None, None),
    "Lithuania": (55.1694, 23.8813),
    "China": (None, None),
    "India": (None, None),
    "Thailand": (None, None),
    "Philippines": (12.8797, 121.7740),
    "Austria": (None, None),
    "Luxembourg": (49.8153, 6.1296),
    "Canada": (None, None),
    "Sweden": (None, None),
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
    source_fix('^(?:FRN-4B0BBE731CA526|FRN-B4E809AFDBFA0B)$', 'FRN-B4E809AFDBFA0B', "Japan", "JP", None, None, 'LOC-a51c9127888c68e0', "SRC_JAMCO_001", "tier1"),
    source_fix('^(?:FRN-19277B67029E73|FRN-A215F89D6DB387)$', 'FRN-19277B67029E73', "Japan", "JP", None, None, 'LOC-729d3cafb4a2802e', "SRC_JAMCO_001", "tier1"),
    source_fix('^(?:FRN-1E9DB09C4FE35C|FRN-2ACA6F663C393F|FRN-AA9FC43191C9DB)$', 'FRN-AA9FC43191C9DB', "Philippines", "PH", None, None, 'LOC-95bf4e1591691827', "SRC_JAMCO_001", "tier1"),
    source_fix('^(?:FRN-19277B67029E73|FRN-1E9DB09C4FE35C|FRN-2ACA6F663C393F|FRN-478DCA22B1FC26|FRN-4B0BBE731CA526|FRN-9B72BBB9F69F3D|FRN-A215F89D6DB387|FRN-AA9FC43191C9DB|FRN-B4560E9BC77D2B|FRN-B4E809AFDBFA0B|FRN-C94B308691F6D9|FRN-D7C9F5165C495D)$', 'FRN-B4560E9BC77D2B', "Japan", "JP", None, None, 'LOC-b908dcd9a4a6b402', "SRC_JAMCO_001", "tier1", "medium_high"),
    source_fix('^(?:FRN-213AAC10F8FF68|FRN-54423E8FD293B7)$', 'FRN-213AAC10F8FF68', "United Kingdom", "GB", None, None, 'LOC-66d0b0bb838f52dd', "SRC_MGR_001"),
    source_fix('^(?:FRN-47B10805A1943F|FRN-C1DF555DA868BF)$', 'FRN-C1DF555DA868BF', "France", "FR", None, None, 'LOC-a96caa9148b8765b', "SRC_LAUAK_001", "tier1"),
    source_fix('^(?:FRN-6DA33580D77667|FRN-D16128C2D1AA8B)$', 'FRN-6DA33580D77667', "Belgium", "BE", None, None, 'LOC-199de74117b3f732', "SRC_FRN-D16128C2D1AA8B_001", "tier2_second_transformation"),
    source_fix('^(?:FRN-2D3B1185B3FC0C|FRN-2EC56F8EB8EC02|FRN-E4D4144CC01587)$', 'FRN-2EC56F8EB8EC02', "Lithuania", "LT", None, None, 'LOC-12deab0e25d50c0a', "SRC_JCAERO_001", "tier1"),
    source_fix('^(?:FRN-4F3EF5C6442315)$', 'FRN-4F3EF5C6442315', "France", "FR", None, None, 'LOC-45889eeafb63225f', "SRC_FRN-4F3EF5C6442315_FRN-1045D929655FAF_001", None, "medium_high"),
    source_fix('^(?:FRN-25A8C56CB9C639|FRN-AA08AEDDCB94EB|FRN-F1F796DB13C8E2)$', 'FRN-AA08AEDDCB94EB', "France", "FR", None, None, 'LOC-bfbaea188266187a', "SRC_FRN-AA08AEDDCB94EB_001", "oem"),
    source_fix('^(?:FRN-8461B2D08E3D4E)$', 'FRN-8461B2D08E3D4E', "France", "FR", None, None, 'LOC-cf556fa39ed2a076', "SRC_FIGEAC_001", "tier1"),
    source_fix('^(?:FRN-0B41BF5B9E4B4E|FRN-FCB0C890EFA2B8)$', 'FRN-0B41BF5B9E4B4E', "France", "FR", None, None, 'LOC-7a6194af25eb99ab', "SRC_FRN-FCB0C890EFA2B8_001", "tier1"),
    source_fix('^(?:FRN-297CE635156764|FRN-999053838C0E1C|FRN-D0B6DB0F437592)$', 'FRN-999053838C0E1C', "France", "FR", None, None, 'LOC-4be679a7fb841326', "SRC_FRN-D0B6DB0F437592_001", "tier1", "medium_high"),
    source_fix('^(?:FRN-67CD5F21738C93|FRN-73FE254CB14818)$', 'FRN-73FE254CB14818', "France", "FR", None, None, 'LOC-4f7903c026489243', "SRC_FRN-67CD5F21738C93_001", None),
    source_fix('^(?:FRN-72A8D622F0F88D)$', 'FRN-72A8D622F0F88D', "France", "FR", None, None, 'LOC-a4bb45036482e485', "SRC_FRN-72A8D622F0F88D_001", None),
    source_fix('^(?:FRN-33013E3321A5B5|FRN-4AAE68951598B8|FRN-84293FE4ADFD8D|FRN-BD1C394D9C653E|FRN-EE2656735EBA2B)$', 'FRN-33013E3321A5B5', "France", "FR", None, None, 'LOC-31c1a22d14a4f26b', "SRC_EXSTO_001", "tier3_first_transformation"),
    source_fix('^(?:FRN-51245894531FE9|FRN-5BB9473F176CD6)$', 'FRN-51245894531FE9', "United States", "US", None, None, 'LOC-44714dce8a68646f', "SRC_ANCRA_001", "tier1"),
    source_fix('^(?:FRN-4DC00ECEFB8526)$', 'FRN-4DC00ECEFB8526', "United States", "US", None, None, 'LOC-b340e46e509a33de', "SRC_TA_001", "tier1", "medium"),
    source_fix('^(?:FRN-869E1A8BB344FD|FRN-FD0761D13CF2C9)$', 'FRN-FD0761D13CF2C9', "Canada", "CA", None, None, 'LOC-9a344de4dd906308', "SRC_FRN-869E1A8BB344FD_001", "tier2_second_transformation"),
    source_fix('^(?:FRN-6F69420F958BBD|FRN-8D94FBDCC3B3B5|FRN-BD805D8D4EB65E)$', 'FRN-8D94FBDCC3B3B5', "France", "FR", None, None, 'LOC-ef0c75435de72682', "SRC_THYSSEN_001", "tier3_first_transformation"),
    source_fix('^(?:FRN-6EF3EF62BA6339|FRN-C3B826345B6812)$', 'FRN-6EF3EF62BA6339', "France", "FR", None, None, 'LOC-6fd0e0a841e33fe1', "SRC_FRN-C3B826345B6812_001", "tier3_first_transformation"),
    source_fix('^(?:FRN-5AA9E59DA0B02F)$', 'FRN-5AA9E59DA0B02F', "India", "IN", None, None, 'LOC-7af45989a47d3828', "SRC_FRN-5AA9E59DA0B02F_001", "tier4_raw_material", "medium_high"),
    source_fix('^(?:FRN-0B3DAD918C8F64)$', 'FRN-0B3DAD918C8F64', "United States", "US", None, None, 'LOC-34225a9b6d48979a', "SRC_DUPONT_001", "tier2_second_transformation", "medium_high"),
    source_fix('^(?:FRN-AC50E317D82C5C)$', 'FRN-AC50E317D82C5C', "Sweden", "SE", None, None, 'LOC-455bbedfe2d3d76c', "SRC_FRN-AC50E317D82C5C_001", None),
    source_fix('^(?:FRN-BDF19DDAD7E188|FRN-C2C13D47AFDB04)$', 'FRN-C2C13D47AFDB04', "United States", "US", None, None, 'LOC-559c2b4437301dc3', "SRC_FRN-BDF19DDAD7E188_001", "tier2_second_transformation"),
    source_fix('^(?:FRN-82CCA67E25D130|FRN-E4E6AFF0074745)$', 'FRN-82CCA67E25D130', "France", "FR", None, None, 'LOC-a92261054c2710b9', "SRC_ANJOU_001", "tier1"),
    source_fix('^(?:FRN-98C883F706EF89|FRN-D2BA5EA122CAA7)$', 'FRN-98C883F706EF89', "Thailand", "TH", None, None, 'LOC-b2fe0786c3c3674c', "SRC_FRN-4BCB03E5586F0F_THAILAND_001", "tier1"),
    source_fix('^(?:FRN-72A106312E8F95)$', 'FRN-72A106312E8F95', "France", "FR", None, None, 'LOC-7fe0cd75837cf35f', "SRC_FRN-72A106312E8F95_001", "tier1"),
    source_fix('^(?:FRN-56B73048A39DA4|FRN-D9C48086C34DAF)$', 'FRN-D9C48086C34DAF', "United States", "US", None, None, 'LOC-fb770612313d651b', "SRC_FRN-D9C48086C34DAF_001", "tier1"),
    source_fix('^(?:FRN-34B2AC7037114C)$', 'FRN-34B2AC7037114C', "United States", "US", None, None, 'LOC-1073747006200994', "SRC_FRN-34B2AC7037114C_001", "tier4_raw_material", "medium_high"),
    source_fix('^(?:FRN-798BE9ED657B85)$', 'FRN-798BE9ED657B85', "France", "FR", None, None, 'LOC-8a64959020e31279', "SRC_FRN-798BE9ED657B85_001", "tier3_first_transformation", "medium_high"),
    source_fix('^(?:FRN-180DF1629E64F3|FRN-6C9C7F20179A2A|FRN-CD09D021B366DB)$', 'FRN-CD09D021B366DB', "Austria", "AT", None, None, 'LOC-9cbf8f6fedfd3cde', "SRC_AMAG_001", "tier3_first_transformation"),
    source_fix('^(?:FRN-0F56088BEA4986|FRN-9C546CCC918C61)$', 'FRN-0F56088BEA4986', "Japan", "JP", None, None, 'LOC-378a872018ff5594', "SRC_FRN-9C546CCC918C61_001", None, "medium_high"),
    source_fix('^(?:FRN-3C5607FC501E5A)$', 'FRN-3C5607FC501E5A', "Luxembourg", "LU", None, None, 'LOC-e057d4aeddcb50c7', "SRC_FRN-3C5607FC501E5A_001", "tier4_raw_material", "medium_high"),
    source_fix('^(?:FRN-301ED6D3E70080)$', 'FRN-301ED6D3E70080', "Germany", "DE", None, None, 'LOC-375fafa88a95bec1', "SRC_FRN-301ED6D3E70080_001", "tier4_raw_material", "medium_high"),
    source_fix('^(?:FRN-191F6AC0669F77|FRN-60C89B8D6563EA)$', 'FRN-60C89B8D6563EA', "India", "IN", None, None, 'LOC-def0e2207518c443', "SRC_FRN-191F6AC0669F77_001", "tier4_raw_material", "medium_high"),
    source_fix('^(?:FRN-336EE447D72F75|FRN-7EB48CA0DDDC6E|FRN-CF71418802439F)$', 'FRN-CF71418802439F', "China", "CN", None, None, 'LOC-1e52e83ce5f99f7c', "SRC_BAOWU_001", "tier4_raw_material", "medium"),
    source_fix('^(?:FRN-7A25E45203FCC9)$', 'FRN-7A25E45203FCC9', "China", "CN", None, None, 'LOC-437b302b39a3ba3b', "", "tier4_raw_material", "low"),
    source_fix('^(?:FRN-9412A07ED242D7|FRN-B8E884308EA449)$', 'FRN-B8E884308EA449', "United States", "US", None, None, 'LOC-031131742c0664ff', "", "tier4_raw_material", "low"),
    source_fix('^(?:FRN-6378B78052F4FE)$', 'FRN-6378B78052F4FE', "Japan", "JP", None, None, 'LOC-f22975a338628f9c', "", "tier4_raw_material", "low"),
    source_fix('^(?:FRN-83186B5AEF84D8)$', 'FRN-83186B5AEF84D8', "France", "FR", None, None, 'LOC-e8561f56b1b1e511', "SRC_AUBERT_001", "tier3_first_transformation", "medium_high"),
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
            if fix["canonical"] == "FRN-C2C13D47AFDB04":
                country, _ = normalize_country(entry.get("location"))
                if country == "Germany":
                    adjusted = dict(fix)
                    adjusted.update(
                        {
                            "country": "Germany",
                            "country_code": "DE",
                            "lat": None,
                            "lon": None,
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
        (("cuir", "MAT-96C726278E7E2A"), "Leather / synthetic leather"),
        (("tissu", "velours", "pa6 6", "nylon"), "Textile / nylon"),
        (("polyurethane", "polyurethane", "mousse", "foam", "frmc55"), "Polyurethane foam"),
        (("silicone",), "Silicone"),
        (("caoutchouc", "polychloroprene"), "Rubber / polychloroprene"),
        (("MAT-08814168D3466E", "MAT-27B24E5EE0075C", "plastique", "MAT-F88FE89FB5C95A", "moulage plastique"), "Engineering plastic"),
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
    if cleaned.get("role_hint") == "oem" or text.startswith("FRN-F1F796DB13C8E2"):
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
