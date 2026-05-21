#!/usr/bin/env python3
"""Apply source-backed site-location corrections for imprecise supplier nodes."""

from __future__ import annotations

import copy
import csv
import json
import re
from pathlib import Path
from typing import Any


BASE_DIR = Path(__file__).resolve().parent
INPUT_JSON = BASE_DIR / "output8_GEO_normalized_final_business_reviewed.json"
OUTPUT_JSON = BASE_DIR / "output8_GEO_normalized_final_site_reviewed.json"
CHANGES_CSV = BASE_DIR / "output8_GEO_site_location_review_changes.csv"
REPORT_MD = BASE_DIR / "output8_GEO_site_location_review.md"


def norm(value: Any) -> str:
    return str(value or "").strip().lower()


def has_any(text: str, needles: list[str]) -> bool:
    text_n = norm(text)
    return any(n in text_n for n in needles)


def matches_fix(entry: dict[str, Any], record: dict[str, Any], fix: dict[str, Any]) -> bool:
    if entry.get("name") not in fix["names"]:
        return False
    roles = fix.get("roles")
    if roles and entry.get("role_hint") not in roles:
        return False
    component_any = fix.get("component_any")
    if component_any and not has_any(record.get("component", ""), component_any):
        return False
    component_not_any = fix.get("component_not_any")
    if component_not_any and has_any(record.get("component", ""), component_not_any):
        return False
    desc_any = fix.get("description_any")
    if desc_any and not has_any(entry.get("description", ""), desc_any):
        return False
    return True


FIXES = [
    {
        "id": "SITE_TATA_JAMSHEDPUR",
        "names": ["Tata Steel"],
        "site_name": "Tata Steel Jamshedpur Works",
        "lat": 22.7853607,
        "lon": 86.1994836,
        "location": "Jamshedpur, India",
        "country_code": "IN",
        "site_address": "Tata Steel Limited, Jamshedpur 831001, Jharkhand, India",
        "geocode_query": "Tata Steel, Jamshedpur, Jharkhand 831001, India",
        "geocode_status": "source_backed_industrial_site_candidate",
        "source_url": "https://www.tatasteel.com/contact-us/",
        "source_note": "Tata Steel references Jamshedpur as a company site/contact location; exact mill allocation still requires material certificate.",
        "confidence": "medium_high",
        "simulation_action": "Use Jamshedpur Works as steel mill candidate; keep certificate validation required.",
    },
    {
        "id": "SITE_DUPONT_SPRUANCE",
        "names": ["DuPont de Nemours"],
        "site_name": "DuPont Spruance Manufacturing Site",
        "lat": 37.4520437,
        "lon": -77.4335412,
        "location": "Richmond, United States",
        "country_code": "US",
        "site_address": "DuPont Spruance manufacturing site, Richmond, Virginia 23234, United States",
        "geocode_query": "DuPont Spruance Richmond VA 23234",
        "geocode_status": "source_backed_industrial_site",
        "source_url": "https://www.dupont.co.jp/locations/dupont-spruance-manufacturing-site.html",
        "source_note": "DuPont identifies Spruance as its largest manufacturing site and links it to Kevlar, Nomex and Tyvek.",
        "confidence": "high",
        "simulation_action": "Replace Wilmington HQ fallback with Spruance manufacturing site for DuPont fiber/polymer exposure.",
    },
    {
        "id": "SITE_BAOSTEEL_BAOSHAN",
        "names": ["China Baowu / Baosteel"],
        "site_name": "Baosteel Baoshan / Fujin Road site",
        "lat": 31.4114498,
        "lon": 121.4557873,
        "location": "Shanghai, China",
        "country_code": "CN",
        "site_address": "Baosteel Administrative Center, No. 885 Fujin Road, Baoshan District, Shanghai, China",
        "geocode_query": "885 Fujin Road, Baoshan District, Shanghai, China",
        "geocode_status": "source_backed_industrial_site_candidate",
        "source_url": "https://craft.co/baosteel/locations",
        "source_note": "Baosteel/Baowu exact steel plant depends on certificate; Fujin Road anchors the Baoshan steel complex better than a China/HQ centroid.",
        "confidence": "medium",
        "simulation_action": "Use Baoshan/Fujin Road as China steel mill candidate; require certificate for active allocation.",
    },
    {
        "id": "SITE_AUBERT_ANCIZES",
        "names": ["Aubert & Duval"],
        "site_name": "Aubert & Duval Les Ancizes",
        "lat": 45.9235016,
        "lon": 2.8415731,
        "location": "Les Ancizes-Comps, France",
        "country_code": "FR",
        "site_address": "Usine des Ancizes BP 1, Les Ancizes, 63770, France",
        "geocode_query": "Aubert Duval Les Ancizes 63770 France",
        "geocode_status": "source_backed_industrial_site",
        "source_url": "https://www.space-aero.org/en/member/aubert-duval-les-ancizes/",
        "source_note": "SPACE Aero lists the Aubert & Duval Les Ancizes industrial site.",
        "confidence": "high",
        "simulation_action": "Replace Aubiere/Clermont fallback with Les Ancizes metallurgical site.",
    },
    {
        "id": "SITE_ARCELORMITTAL_INDUSTEEL",
        "names": ["ArcelorMittal"],
        "site_name": "ArcelorMittal Industeel Le Creusot",
        "lat": 46.7897099,
        "lon": 4.4493912,
        "location": "Le Creusot / Torcy, France",
        "country_code": "FR",
        "site_address": "Industeel Le Creusot, 56 Avenue Clemenceau BP 19, 71201 Le Creusot Cedex, France",
        "geocode_query": "ArcelorMittal Industeel Le Creusot / Torcy, France",
        "geocode_status": "source_backed_industrial_site_candidate",
        "source_url": "https://industeel.arcelormittal.com/legal-mentions/",
        "source_note": "Industeel is an ArcelorMittal high-quality steel producer; exact ArcelorMittal mill still requires material certificate.",
        "confidence": "medium",
        "simulation_action": "Use Industeel Le Creusot as special-steel scenario candidate; certificate required before hard allocation.",
    },
    {
        "id": "SITE_CHALCO_QINGHAI",
        "names": ["Aluminium Corporation of China / Chalco"],
        "site_name": "Chalco Qinghai Branch / Beichuan Industrial Park",
        "lat": 36.7653535,
        "lon": 101.7640249,
        "location": "Xining, China",
        "country_code": "CN",
        "site_address": "Beichuan Industrial Park, Datong County, Xining, Qinghai, China",
        "geocode_query": "Beichuan Industrial Park, Datong County, Xining, Qinghai, China",
        "geocode_status": "source_backed_industrial_site_candidate",
        "source_url": "https://www.chalco.com/en/sctxen/cpzsen/202012/t20201215_66289.html",
        "source_note": "Chalco lists Qinghai Branch among remelting aluminum ingot producers; exact smelter allocation remains certificate-dependent.",
        "confidence": "medium",
        "simulation_action": "Replace Beijing fallback with Qinghai smelter candidate; keep allocation validation required.",
    },
    {
        "id": "SITE_HINDALCO_RENUKOOT",
        "names": ["Hindalco Industries"],
        "site_name": "Hindalco Renukoot",
        "lat": 24.2236632,
        "lon": 83.0306552,
        "location": "Renukoot, India",
        "country_code": "IN",
        "site_address": "Hindalco Renukoot, Sonbhadra, Uttar Pradesh, India",
        "geocode_query": "Hindalco Renukoot, Sonbhadra, Uttar Pradesh, India",
        "geocode_status": "source_backed_industrial_site",
        "source_url": "https://www.hindalco.com/about-us/manufacturing/renukoot",
        "source_note": "Hindalco describes Renukoot as fully integrated across the aluminium value chain with smelting, rolling and extrusions.",
        "confidence": "high",
        "simulation_action": "Replace Mumbai corporate fallback with Renukoot aluminium plant.",
    },
    {
        "id": "SITE_NUCOR_BERKELEY",
        "names": ["Nucor Corp"],
        "site_name": "Nucor Steel Berkeley",
        "lat": 33.007,
        "lon": -79.879,
        "location": "Huger, United States",
        "country_code": "US",
        "site_address": "1455 Hagan Ave, Huger, South Carolina 29450, United States",
        "geocode_query": "EPA TRI NUCOR STEEL-BERKELEY 1455 HAGAN AVE, HUGER SC 29450",
        "geocode_status": "source_backed_industrial_site_candidate",
        "source_url": "https://enviro.epa.gov/triexplorer/release_fac_profile?TRI=29450NCRST1455H",
        "source_note": "EPA TRI identifies Nucor Steel-Berkeley as an iron and steel mills facility with coordinates.",
        "confidence": "medium_high",
        "simulation_action": "Replace Charlotte HQ fallback with Nucor Berkeley mill candidate.",
    },
    {
        "id": "SITE_ALCOA_WARRICK",
        "names": ["Alcoa"],
        "site_name": "Alcoa Warrick Operations",
        "lat": 37.9202921,
        "lon": -87.3302684,
        "location": "Newburgh, United States",
        "country_code": "US",
        "site_address": "Alcoa Warrick Operations, Newburgh, Indiana, United States",
        "geocode_query": "Alcoa Warrick Operations, Newburgh, Indiana, USA",
        "geocode_status": "source_backed_industrial_site",
        "source_url": "https://www.alcoa.com/global/en/pdf/Alcoa-Warrick-Fact-Sheet.pdf",
        "source_note": "Alcoa fact sheet identifies Warrick as a primary aluminium operation.",
        "confidence": "high",
        "simulation_action": "Replace Pittsburgh fallback with Warrick primary aluminium operation.",
    },
    {
        "id": "SITE_CONSTELLIUM_ISSOIRE",
        "names": ["Constellium"],
        "site_name": "Constellium Issoire",
        "lat": 45.5583927,
        "lon": 3.2601128,
        "location": "Issoire, France",
        "country_code": "FR",
        "site_address": "Rue Yves Lamourdedieu, ZI des Listes, CS40042, 63502 Issoire Cedex, France",
        "geocode_query": "Constellium Issoire, Rue Yves Lamourdedieu, Issoire, France",
        "geocode_status": "source_backed_industrial_site",
        "source_url": "https://www.constellium.com/fr/sites-de-production/issoire",
        "source_note": "Constellium identifies Issoire as an aerospace hub producing aluminium plates, sheets and extrusions.",
        "confidence": "high",
        "simulation_action": "Replace Voreppe R&D fallback with Issoire aerospace production site.",
    },
    {
        "id": "SITE_HUDDERSFIELD_TEXTILES",
        "names": ["Huddersfield Textiles"],
        "site_name": "Huddersfield Textiles Old Dye Works showroom / company site",
        "lat": 53.6407700,
        "lon": -1.8007200,
        "location": "Huddersfield, United Kingdom",
        "country_code": "GB",
        "site_address": "The Old Dye Works, Birkhouse Lane, Paddock, Huddersfield, West Yorkshire, HD1 4SF, United Kingdom",
        "geocode_query": "HD1 4SF / Birkhouse Lane, Huddersfield, United Kingdom",
        "geocode_status": "source_backed_site_postcode",
        "source_url": "https://www.huddersfieldtextiles.com/contact/",
        "source_note": "Huddersfield Textiles gives this company/showroom address; manufacturing allocation for fabric still requires supplier traceability.",
        "confidence": "medium",
        "simulation_action": "Replace town centroid with company postcode-level site; validate mill/weaver before production allocation.",
    },
    {
        "id": "SITE_MITSUBISHI_TIELT_ERTALON",
        "names": ["Mitsubishi Chemical"],
        "component_any": ["ertalon"],
        "site_name": "Mitsubishi Chemical Advanced Materials Tielt",
        "lat": 50.9997611,
        "lon": 3.3450176,
        "location": "Tielt, Belgium",
        "country_code": "BE",
        "site_address": "IP Noord, Galgenveldstraat 10/12, 8700 Tielt, Belgium",
        "geocode_query": "Galgenveldstraat 12, 8700 Tielt, Belgium",
        "geocode_status": "source_backed_industrial_site",
        "source_url": "https://eu.mitsubishi-chemical.com/locations/",
        "source_note": "Mitsubishi Chemical lists Advanced Materials sites in Tielt; applied only to Ertalon records.",
        "confidence": "high_for_ertalon_only",
        "simulation_action": "Use Tielt for Ertalon/MCAM records; keep non-Ertalon Mitsubishi records unchanged.",
    },
    {
        "id": "SITE_SHINETSU_GUNMA_ISOBE",
        "names": ["Shin-Etsu Silicones"],
        "site_name": "Shin-Etsu Chemical Gunma Complex Isobe Plant",
        "lat": 36.2983921,
        "lon": 138.8497966,
        "location": "Annaka, Japan",
        "country_code": "JP",
        "site_address": "13-1, Isobe 2-chome, Annaka-shi, Gunma 379-0195, Japan",
        "geocode_query": "Isobe, Annaka, Gunma, Japan",
        "geocode_status": "source_backed_industrial_site_nearby_geocode",
        "source_url": "https://www.shinetsu.co.jp/en/company/network/plant/",
        "source_note": "Shin-Etsu lists Gunma Complex Isobe Plant with silicones among products; coordinates are district-level because exact address was not resolved.",
        "confidence": "medium_high",
        "simulation_action": "Replace Tokyo HQ/city fallback with Gunma silicone plant area.",
    },
    {
        "id": "SITE_SILICONE_ENGINEERING_BLACKBURN",
        "names": ["Silicone Engineering"],
        "site_name": "Silicone Engineering Blackburn",
        "lat": 53.7559111,
        "lon": -2.4483932,
        "location": "Blackburn, United Kingdom",
        "country_code": "GB",
        "site_address": "Greenbank Business Park, Blakewater Road, Blackburn, Lancashire BB1 3HU, United Kingdom",
        "geocode_query": "Blakewater Road, Blackburn BB1 3HU, United Kingdom",
        "geocode_status": "source_backed_industrial_site_nearby_geocode",
        "source_url": "https://ukgsassociation.co.uk/member/silicone-engineering-ltd/",
        "source_note": "UKGSA lists Silicone Engineering at Greenbank Business Park and describes silicone rubber manufacturing/supply.",
        "confidence": "medium_high",
        "simulation_action": "Replace Blackburn city point with Blakewater Road/Greenbank Business Park area.",
    },
    {
        "id": "SITE_DAIO_MISHIMA",
        "names": ["Daio Paper Corporation"],
        "site_name": "Daio Paper Mishima Mill",
        "lat": 33.9807440,
        "lon": 133.5499338,
        "location": "Shikokuchuo, Japan",
        "country_code": "JP",
        "site_address": "5-1 Mishimakamiya-cho, Shikokuchuo-shi, Ehime 799-0402, Japan",
        "geocode_query": "Shikokuchuo, Ehime, Japan; Mishima Mill address source-backed",
        "geocode_status": "source_backed_industrial_site_city_geocode",
        "source_url": "https://www.daio-paper.co.jp/en/company/base/",
        "source_note": "Daio identifies Mishima Mill as its main production mill; coordinates are city-level because exact address did not resolve.",
        "confidence": "medium",
        "simulation_action": "Replace generic Shikokuchuo city note with Mishima Mill site identity; improve coordinates if local geocoder available.",
    },
    {
        "id": "SITE_KEMCO_STLOUIS",
        "names": ["KEMKO Aerospace"],
        "site_name": "Kemco/Mastercraft Building 1",
        "lat": 38.5635720,
        "lon": -90.4559651,
        "location": "St. Louis, United States",
        "country_code": "US",
        "site_address": "3616 Scarlet Oak Blvd, St. Louis, Missouri 63122, United States",
        "geocode_query": "3616 Scarlet Oak Blvd, St. Louis, MO 63122, USA",
        "geocode_status": "source_backed_industrial_site",
        "source_url": "https://kemcoaerospace.com/about/locations/",
        "source_note": "Kemco lists this St. Louis building as one of its locations.",
        "confidence": "high",
        "simulation_action": "Replace St. Louis city fallback with Kemco/Mastercraft building.",
    },
    {
        "id": "SITE_LIEBHERR_LINDENBERG",
        "names": ["Liebherr Aerospace"],
        "site_name": "Liebherr-Aerospace Lindenberg GmbH",
        "lat": 47.5963892,
        "lon": 9.8653206,
        "location": "Lindenberg im Allgau, Germany",
        "country_code": "DE",
        "site_address": "Pfanderstrasse 50-52, 88161 Lindenberg/Allgau, Germany",
        "geocode_query": "Pfanderstrasse 50-52, 88161 Lindenberg im Allgau, Germany",
        "geocode_status": "source_backed_industrial_site",
        "source_url": "https://www.liebherr.com/de-de/firmengruppe/standort/lindenberg-profil-3705432",
        "source_note": "Liebherr identifies Lindenberg as a site developing/manufacturing integrated aerospace systems and gives the address.",
        "confidence": "high",
        "simulation_action": "Replace Lindenberg city fallback with the Liebherr site address.",
    },
    {
        "id": "SITE_NORDIC_SAFFLE",
        "names": ["Nordic Paper"],
        "site_name": "Nordic Paper Saffle Mill",
        "lat": 59.1442024,
        "lon": 12.9149356,
        "location": "Saffle, Sweden",
        "country_code": "SE",
        "site_address": "Forskningsvagen 2, SE-661 29 Saffle, Sweden",
        "geocode_query": "Forskningsvagen 2, Saffle, Sweden",
        "geocode_status": "source_backed_industrial_site",
        "source_url": "https://www.nordic-paper.com/en/about-us/production-units",
        "source_note": "Nordic Paper lists Saffle as a paper mill and gives the address/loading point.",
        "confidence": "high",
        "simulation_action": "Replace multi-mill fallback with Saffle mill for this paper/padding scenario.",
    },
    {
        "id": "SITE_TORAY_NAGOYA_NYLON",
        "names": ["Toray Industries"],
        "component_any": ["nylon"],
        "site_name": "Toray Nagoya Plant",
        "lat": 35.0891705,
        "lon": 136.8965363,
        "location": "Nagoya, Japan",
        "country_code": "JP",
        "site_address": "9-1 Oecho, Minato Ward, Nagoya, Aichi, Japan",
        "geocode_query": "9-1 Oecho, Minato Ward, Nagoya, Aichi, Japan",
        "geocode_status": "source_backed_industrial_site",
        "source_url": "https://www.toray.com/sustainability/activity/environment/data.html",
        "source_note": "Toray environmental data lists Nagoya Plant and AMILAN nylon resin.",
        "confidence": "high_for_nylon_only",
        "simulation_action": "Use Nagoya for Toray nylon records only; keep generic textile/composite Toray records unchanged unless grade is known.",
    },
    {
        "id": "SITE_TORAY_EHIME_CARBON",
        "names": ["Toray Industries"],
        "component_any": ["titane fibre de carbone"],
        "site_name": "Toray Ehime Plant",
        "lat": 33.7860213,
        "lon": 132.7049523,
        "location": "Masaki, Japan",
        "country_code": "JP",
        "site_address": "1515 Tsutsui, Masaki-cho, Iyo-gun, Ehime 791-3120, Japan",
        "geocode_query": "Masaki Station near Toray Ehime Plant, Ehime, Japan",
        "geocode_status": "source_backed_industrial_site_nearby_station_geocode",
        "source_url": "https://www.toray.co.jp/saiyou/fresh/worklifebalance/plants_ehime.html",
        "source_note": "Toray gives the Ehime Plant address and says it is near Masaki Station; Toray environmental data lists TORAYCA carbon fiber at Ehime Plant.",
        "confidence": "medium_high",
        "simulation_action": "Use Ehime for carbon-fiber record; exact gate coordinate can be refined later.",
    },
]


UNAPPLIED_DECISIONS = [
    {
        "name": "XPO Logistic",
        "decision": "not_applied",
        "site_candidate": "XPO Europe HQ, 192 Avenue Thiers, Lyon, France, or route-specific XPO operating center",
        "source_url": "https://europe.xpo.com/en/industries/aerospace-and-defence/",
        "rationale": "XPO logistics nodes should be modeled as route legs/hubs, not as a supplier plant. Public data does not identify the actual route hub for these records.",
        "simulation_action": "Keep as logistics provider; require route lane or hub assignment before replacing Greenwich/Lyon HQ.",
    },
    {
        "name": "TE Connectivity",
        "decision": "not_applied",
        "site_candidate": "TE Connectivity Aerospace, Defense & Marine, Middletown, PA candidate",
        "source_url": "https://www.tti.com/content/ttiinc/en/manufacturers/te-connectivity/resources/te-connectivity-aerospace-defense-marine.html",
        "rationale": "TE has AD&M operations but the exact cable/bracket part number is missing; a plant assignment would be false precision.",
        "simulation_action": "Keep Berwyn/HQ candidate inactive for site simulation until PN/BOM/AVL is available.",
    },
    {
        "name": "Mitsubishi Chemical",
        "decision": "partial_only",
        "site_candidate": "Mitsubishi Chemical Advanced Materials Tielt applied only for Ertalon records",
        "source_url": "https://eu.mitsubishi-chemical.com/locations/",
        "rationale": "Non-Ertalon Mitsubishi records include nylon, LCD/display and generic molded plastic; public data is insufficient to allocate all to Tielt.",
        "simulation_action": "Use Tielt only for Ertalon; require grade/PN for other Mitsubishi records.",
    },
    {
        "name": "Toray Industries",
        "decision": "partial_only",
        "site_candidate": "Nagoya for nylon, Ehime for carbon fiber; generic textile/polymer records unchanged",
        "source_url": "https://www.toray.com/sustainability/activity/environment/data.html",
        "rationale": "Toray has multiple relevant Japanese plants. Nagoya/Ehime are source-backed for nylon/carbon, but textile/velcro/generic polymer records need grade-level traceability.",
        "simulation_action": "Use Nagoya/Ehime only for matching records; require material grade for the rest.",
    },
]


def apply_fix(entry: dict[str, Any], record: dict[str, Any], fix: dict[str, Any], container: str) -> dict[str, Any]:
    before = {
        "name": entry.get("name"),
        "location": entry.get("location"),
        "country_code": entry.get("country_code"),
        "lat": entry.get("lat"),
        "lon": entry.get("lon"),
        "geocode_status": entry.get("geocode_status"),
        "geocode_provider": entry.get("geocode_provider"),
        "geocode_query": entry.get("geocode_query"),
        "site_address": entry.get("site_address"),
    }
    entry["location_review_before"] = before
    entry["lat"] = fix["lat"]
    entry["lon"] = fix["lon"]
    entry["location"] = fix["location"]
    entry["country_code"] = fix["country_code"]
    entry["site_address"] = fix["site_address"]
    entry["geocode_query"] = fix["geocode_query"]
    entry["geocode_provider"] = "manual:site_location_review_2026-05-21"
    entry["geocode_status"] = fix["geocode_status"]
    entry["site_selection_id"] = fix["id"]
    entry["site_selection_name"] = fix["site_name"]
    entry["site_selection_confidence"] = fix["confidence"]
    entry["site_selection_source_url"] = fix["source_url"]
    entry["site_selection_note"] = fix["source_note"]
    entry["simulation_site_action"] = fix["simulation_action"]
    source_ids = list(entry.get("source_ids") or [])
    if fix["id"] not in source_ids:
        source_ids.append(fix["id"])
    entry["source_ids"] = source_ids
    return {
        "record_index": record.get("record_index"),
        "system": record.get("system"),
        "component": record.get("component"),
        "container": container,
        "supplier": before["name"],
        "role_hint": entry.get("role_hint"),
        "fix_id": fix["id"],
        "site_name": fix["site_name"],
        "before_location": before["location"],
        "before_lat": before["lat"],
        "before_lon": before["lon"],
        "after_location": entry["location"],
        "after_lat": entry["lat"],
        "after_lon": entry["lon"],
        "confidence": fix["confidence"],
        "source_url": fix["source_url"],
        "simulation_action": fix["simulation_action"],
    }


def write_outputs(data: dict[str, Any], changes: list[dict[str, Any]]) -> None:
    data.setdefault("_meta", {})["site_location_review"] = {
        "input_json": INPUT_JSON.name,
        "output_json": OUTPUT_JSON.name,
        "changes_csv": CHANGES_CSV.name,
        "report_md": REPORT_MD.name,
        "applied_change_count": len(changes),
        "fix_count": len(FIXES),
        "unapplied_decision_count": len(UNAPPLIED_DECISIONS),
        "policy": "source-backed site candidates applied only where the site is defensible; certificate/BOM validation still required for allocation-sensitive producers.",
    }
    OUTPUT_JSON.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    fields = [
        "record_index",
        "system",
        "component",
        "container",
        "supplier",
        "role_hint",
        "fix_id",
        "site_name",
        "before_location",
        "before_lat",
        "before_lon",
        "after_location",
        "after_lat",
        "after_lon",
        "confidence",
        "source_url",
        "simulation_action",
    ]
    with CHANGES_CSV.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(changes)

    by_fix: dict[str, int] = {}
    for change in changes:
        by_fix[change["fix_id"]] = by_fix.get(change["fix_id"], 0) + 1

    lines = [
        "# Site-grade location review - output8_GEO",
        "",
        f"- Input: `{INPUT_JSON.as_posix()}`",
        f"- Output JSON: `{OUTPUT_JSON.as_posix()}`",
        f"- Change log: `{CHANGES_CSV.as_posix()}`",
        f"- Applied record-level changes: **{len(changes)}**",
        f"- Source-backed fix rules: **{len(FIXES)}**",
        "",
        "## Corrections appliquees",
        "",
        "| fix_id | site retenu | occurrences | confiance | source | action simulation |",
        "|---|---:|---:|---|---|---|",
    ]
    fix_by_id = {fix["id"]: fix for fix in FIXES}
    for fix_id, count in sorted(by_fix.items(), key=lambda kv: (-kv[1], kv[0])):
        fix = fix_by_id[fix_id]
        lines.append(
            f"| {fix_id} | {fix['site_name']} | {count} | {fix['confidence']} | {fix['source_url']} | {fix['simulation_action']} |"
        )

    lines.extend(
        [
            "",
            "## Decisions non appliquees ou partielles",
            "",
            "| fournisseur | decision | candidat | raison | action simulation |",
            "|---|---|---|---|---|",
        ]
    )
    for row in UNAPPLIED_DECISIONS:
        lines.append(
            f"| {row['name']} | {row['decision']} | {row['site_candidate']} | {row['rationale']} | {row['simulation_action']} |"
        )

    lines.extend(
        [
            "",
            "## Limite de lecture",
            "",
            "Ces corrections remplacent des HQ, villes ou fallbacks par des sites industriels source-backed quand c'est raisonnable pour la simulation. Elles ne prouvent pas que le programme siège achète effectivement depuis ce site : cette preuve reste le certificat matière, la BOM, le PN, l'AVL ou la donnée achat/logistique.",
            "",
        ]
    )
    REPORT_MD.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    data = json.loads(INPUT_JSON.read_text(encoding="utf-8"))
    data = copy.deepcopy(data)
    records = data.get("records", [])
    changes: list[dict[str, Any]] = []
    containers = ["suppliers", "oem_sites", "logistics_providers", "packaging_suppliers", "cots_upstream_suppliers"]
    for record in records:
        if record.get("simulation_supply_usable") is False:
            continue
        for container in containers:
            for entry in record.get(container, []) or []:
                if not isinstance(entry, dict):
                    continue
                for fix in FIXES:
                    if matches_fix(entry, record, fix):
                        changes.append(apply_fix(entry, record, fix, container))
                        break

    write_outputs(data, changes)
    print(f"[INFO] wrote {OUTPUT_JSON}")
    print(f"[INFO] changes={len(changes)} report={REPORT_MD}")


if __name__ == "__main__":
    main()
