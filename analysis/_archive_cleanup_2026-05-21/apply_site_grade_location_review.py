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
        "names": ["FRN-5AA9E59DA0B02F"],
        "site_name": "FRN-5AA9E59DA0B02F Jamshedpur Works",
        "lat": None,
        "lon": None,
        "location": "Jamshedpur, India",
        "country_code": "IN",
        "site_address": '',
        "geocode_query": '',
        "geocode_status": "source_backed_industrial_site_candidate",
        "source_url": "https://sources.invalid/FRN-5AA9E59DA0B02F/5592a987c0e8bf05",
        "source_note": "FRN-5AA9E59DA0B02F references Jamshedpur as a company site/contact location; exact mill allocation still requires material certificate.",
        "confidence": "medium_high",
        "simulation_action": "Use Jamshedpur Works as steel mill candidate; keep certificate validation required.",
    },
    {
        "id": "SITE_DUPONT_SPRUANCE",
        "names": ["FRN-0B3DAD918C8F64"],
        "site_name": "DuPont Spruance Manufacturing Site",
        "lat": None,
        "lon": None,
        "location": "Richmond, United States",
        "country_code": "US",
        "site_address": '',
        "geocode_query": '',
        "geocode_status": "source_backed_industrial_site",
        "source_url": "https://sources.invalid/FRN-0B3DAD918C8F64/ecd21ddc8101ccb0",
        "source_note": "DuPont identifies Spruance as its largest manufacturing site and links it to Kevlar, Nomex and Tyvek.",
        "confidence": "high",
        "simulation_action": "Replace Wilmington HQ fallback with Spruance manufacturing site for DuPont fiber/polymer exposure.",
    },
    {
        "id": "SITE_BAOSTEEL_BAOSHAN",
        "names": ["FRN-CF71418802439F"],
        "site_name": "Baosteel Baoshan / Fujin Road site",
        "lat": None,
        "lon": None,
        "location": "Shanghai, China",
        "country_code": "CN",
        "site_address": '',
        "geocode_query": '',
        "geocode_status": "source_backed_industrial_site_candidate",
        "source_url": "https://sources.invalid/FRN-CF71418802439F/61e2b40f4124dc67",
        "source_note": "Baosteel/Baowu exact steel plant depends on certificate; Fujin Road anchors the Baoshan steel complex better than a China/HQ centroid.",
        "confidence": "medium",
        "simulation_action": "Use Baoshan/Fujin Road as China steel mill candidate; require certificate for active allocation.",
    },
    {
        "id": "SITE_AUBERT_ANCIZES",
        "names": ["FRN-83186B5AEF84D8"],
        "site_name": "FRN-83186B5AEF84D8 Les Ancizes",
        "lat": None,
        "lon": None,
        "location": "Les Ancizes-Comps, France",
        "country_code": "FR",
        "site_address": '',
        "geocode_query": '',
        "geocode_status": "source_backed_industrial_site",
        "source_url": "https://sources.invalid/FRN-83186B5AEF84D8/9b340f758cab879f",
        "source_note": "SPACE Aero lists the FRN-83186B5AEF84D8 Les Ancizes industrial site.",
        "confidence": "high",
        "simulation_action": "Replace Aubiere/Clermont fallback with Les Ancizes metallurgical site.",
    },
    {
        "id": "SITE_FRN-3C5607FC501E5A_INDUSTEEL",
        "names": ["FRN-3C5607FC501E5A"],
        "site_name": "FRN-3C5607FC501E5A Industeel Le Creusot",
        "lat": None,
        "lon": None,
        "location": "Le Creusot / Torcy, France",
        "country_code": "FR",
        "site_address": '',
        "geocode_query": '',
        "geocode_status": "source_backed_industrial_site_candidate",
        "source_url": "https://sources.invalid/FRN-3C5607FC501E5A/19f83839bed63ba0",
        "source_note": "Industeel is an FRN-3C5607FC501E5A high-quality steel producer; exact FRN-3C5607FC501E5A mill still requires material certificate.",
        "confidence": "medium",
        "simulation_action": "Use Industeel Le Creusot as special-steel scenario candidate; certificate required before hard allocation.",
    },
    {
        "id": "SITE_FRN-7A25E45203FCC9_QINGHAI",
        "names": ["FRN-7A25E45203FCC9"],
        "site_name": "FRN-7A25E45203FCC9 Qinghai Branch / Beichuan Industrial Park",
        "lat": None,
        "lon": None,
        "location": "Xining, China",
        "country_code": "CN",
        "site_address": '',
        "geocode_query": '',
        "geocode_status": "source_backed_industrial_site_candidate",
        "source_url": "https://sources.invalid/FRN-7A25E45203FCC9/8c2766000e43f27a",
        "source_note": "FRN-7A25E45203FCC9 lists Qinghai Branch among remelting aluminum ingot producers; exact smelter allocation remains certificate-dependent.",
        "confidence": "medium",
        "simulation_action": "Replace Beijing fallback with Qinghai smelter candidate; keep allocation validation required.",
    },
    {
        "id": "SITE_FRN-191F6AC0669F77_RENUKOOT",
        "names": ["FRN-60C89B8D6563EA"],
        "site_name": "FRN-191F6AC0669F77 Renukoot",
        "lat": None,
        "lon": None,
        "location": "Renukoot, India",
        "country_code": "IN",
        "site_address": '',
        "geocode_query": '',
        "geocode_status": "source_backed_industrial_site",
        "source_url": "https://sources.invalid/FRN-60C89B8D6563EA/861eab1c437f262c",
        "source_note": "FRN-191F6AC0669F77 describes Renukoot as fully integrated across the aluminium value chain with smelting, rolling and extrusions.",
        "confidence": "high",
        "simulation_action": "Replace Mumbai corporate fallback with Renukoot aluminium plant.",
    },
    {
        "id": "SITE_NUCOR_BERKELEY",
        "names": ["FRN-B8E884308EA449"],
        "site_name": "Nucor Steel Berkeley",
        "lat": None,
        "lon": None,
        "location": "Huger, United States",
        "country_code": "US",
        "site_address": '',
        "geocode_query": '',
        "geocode_status": "source_backed_industrial_site_candidate",
        "source_url": "https://sources.invalid/FRN-B8E884308EA449/03613c032bda4791",
        "source_note": "EPA TRI identifies Nucor Steel-Berkeley as an iron and steel mills facility with coordinates.",
        "confidence": "medium_high",
        "simulation_action": "Replace Charlotte HQ fallback with Nucor Berkeley mill candidate.",
    },
    {
        "id": "SITE_FRN-34B2AC7037114C_WARRICK",
        "names": ["FRN-34B2AC7037114C"],
        "site_name": "FRN-34B2AC7037114C Warrick Operations",
        "lat": None,
        "lon": None,
        "location": "Newburgh, United States",
        "country_code": "US",
        "site_address": '',
        "geocode_query": '',
        "geocode_status": "source_backed_industrial_site",
        "source_url": "https://sources.invalid/FRN-34B2AC7037114C/a5c0942c79e534b3",
        "source_note": "FRN-34B2AC7037114C fact sheet identifies Warrick as a primary aluminium operation.",
        "confidence": "high",
        "simulation_action": "Replace Pittsburgh fallback with Warrick primary aluminium operation.",
    },
    {
        "id": "SITE_FRN-798BE9ED657B85_ISSOIRE",
        "names": ["FRN-798BE9ED657B85"],
        "site_name": "FRN-798BE9ED657B85 Issoire",
        "lat": None,
        "lon": None,
        "location": "Issoire, France",
        "country_code": "FR",
        "site_address": '',
        "geocode_query": '',
        "geocode_status": "source_backed_industrial_site",
        "source_url": "https://sources.invalid/FRN-798BE9ED657B85/6f3c9703af462853",
        "source_note": "FRN-798BE9ED657B85 identifies Issoire as an aerospace hub producing aluminium plates, sheets and extrusions.",
        "confidence": "high",
        "simulation_action": "Replace Voreppe R&D fallback with Issoire aerospace production site.",
    },
    {
        "id": "SITE_FRN-0CA3DB5897A052",
        "names": ["FRN-0CA3DB5897A052"],
        "site_name": "FRN-0CA3DB5897A052 Old Dye Works showroom / company site",
        "lat": None,
        "lon": None,
        "location": "Huddersfield, United Kingdom",
        "country_code": "GB",
        "site_address": '',
        "geocode_query": '',
        "geocode_status": "source_backed_site_postcode",
        "source_url": "https://sources.invalid/FRN-0CA3DB5897A052/83f2b3b47ff32399",
        "source_note": "FRN-0CA3DB5897A052 gives this company/showroom address; manufacturing allocation for fabric still requires supplier traceability.",
        "confidence": "medium",
        "simulation_action": "Replace town centroid with company postcode-level site; validate mill/weaver before production allocation.",
    },
    {
        "id": "SITE_MITSUBISHI_TIELT_ERTALON",
        "names": ["FRN-6378B78052F4FE"],
        "component_any": ["ertalon"],
        "site_name": "FRN-6378B78052F4FE Advanced Materials Tielt",
        "lat": None,
        "lon": None,
        "location": "Tielt, Belgium",
        "country_code": "BE",
        "site_address": '',
        "geocode_query": '',
        "geocode_status": "source_backed_industrial_site",
        "source_url": "https://sources.invalid/FRN-6378B78052F4FE/7fe70d1186a82d79",
        "source_note": "FRN-6378B78052F4FE lists Advanced Materials sites in Tielt; applied only to Ertalon records.",
        "confidence": "high_for_ertalon_only",
        "simulation_action": "Use Tielt for Ertalon/MCAM records; keep non-Ertalon Mitsubishi records unchanged.",
    },
    {
        "id": "SITE_SHINETSU_GUNMA_ISOBE",
        "names": ["FRN-332F92E4BA4B00"],
        "site_name": "Shin-Etsu Chemical Gunma Complex Isobe Plant",
        "lat": None,
        "lon": None,
        "location": "Annaka, Japan",
        "country_code": "JP",
        "site_address": '',
        "geocode_query": '',
        "geocode_status": "source_backed_industrial_site_nearby_geocode",
        "source_url": "https://sources.invalid/FRN-332F92E4BA4B00/fdebbb2c4398c29d",
        "source_note": "Shin-Etsu lists Gunma Complex Isobe Plant with silicones among products; coordinates are district-level because exact address was not resolved.",
        "confidence": "medium_high",
        "simulation_action": "Replace Tokyo HQ/city fallback with Gunma silicone plant area.",
    },
    {
        "id": "SITE_FRN-BDE3FD68E4E87F_BLACKBURN",
        "names": ["FRN-BDE3FD68E4E87F"],
        "site_name": "FRN-BDE3FD68E4E87F Blackburn",
        "lat": None,
        "lon": None,
        "location": "Blackburn, United Kingdom",
        "country_code": "GB",
        "site_address": '',
        "geocode_query": '',
        "geocode_status": "source_backed_industrial_site_nearby_geocode",
        "source_url": "https://sources.invalid/FRN-BDE3FD68E4E87F/30c348c801664ac6",
        "source_note": "UKGSA lists FRN-BDE3FD68E4E87F at Greenbank Business Park and describes silicone rubber manufacturing/supply.",
        "confidence": "medium_high",
        "simulation_action": "Replace Blackburn city point with Blakewater Road/Greenbank Business Park area.",
    },
    {
        "id": "SITE_DAIO_MISHIMA",
        "names": ["FRN-B7600B824E7BC7"],
        "site_name": "FRN-B7600B824E7BC7 Mishima Mill",
        "lat": None,
        "lon": None,
        "location": "Shikokuchuo, Japan",
        "country_code": "JP",
        "site_address": '',
        "geocode_query": '',
        "geocode_status": "source_backed_industrial_site_city_geocode",
        "source_url": "https://sources.invalid/FRN-B7600B824E7BC7/5b8fa58f3adb9d79",
        "source_note": "Daio identifies Mishima Mill as its main production mill; coordinates are city-level because exact address did not resolve.",
        "confidence": "medium",
        "simulation_action": "Replace generic Shikokuchuo city note with Mishima Mill site identity; improve coordinates if local geocoder available.",
    },
    {
        "id": "SITE_KEMCO_STLOUIS",
        "names": ["FRN-EFD76ECB77D7DC"],
        "site_name": "Kemco/Mastercraft Building 1",
        "lat": None,
        "lon": None,
        "location": "St. Louis, United States",
        "country_code": "US",
        "site_address": '',
        "geocode_query": '',
        "geocode_status": "source_backed_industrial_site",
        "source_url": "https://sources.invalid/FRN-EFD76ECB77D7DC/ccd5f84c2d347152",
        "source_note": "Kemco lists this St. Louis building as one of its locations.",
        "confidence": "high",
        "simulation_action": "Replace St. Louis city fallback with Kemco/Mastercraft building.",
    },
    {
        "id": "SITE_FRN-52D5AE23024E5C_LINDENBERG",
        "names": ["FRN-42EDB7DB79E4B3"],
        "site_name": "FRN-42EDB7DB79E4B3 Lindenberg GmbH",
        "lat": None,
        "lon": None,
        "location": "Lindenberg im Allgau, Germany",
        "country_code": "DE",
        "site_address": '',
        "geocode_query": '',
        "geocode_status": "source_backed_industrial_site",
        "source_url": "https://sources.invalid/FRN-42EDB7DB79E4B3/c887764179525dd2",
        "source_note": "FRN-52D5AE23024E5C identifies Lindenberg as a site developing/manufacturing integrated aerospace systems and gives the address.",
        "confidence": "high",
        "simulation_action": "Replace Lindenberg city fallback with the FRN-52D5AE23024E5C site address.",
    },
    {
        "id": "SITE_NORDIC_SAFFLE",
        "names": ["FRN-AC50E317D82C5C"],
        "site_name": "FRN-AC50E317D82C5C Saffle Mill",
        "lat": None,
        "lon": None,
        "location": "Saffle, Sweden",
        "country_code": "SE",
        "site_address": '',
        "geocode_query": '',
        "geocode_status": "source_backed_industrial_site",
        "source_url": "https://sources.invalid/FRN-AC50E317D82C5C/2dd36d5ebf78c77c",
        "source_note": "FRN-AC50E317D82C5C lists Saffle as a paper mill and gives the address/loading point.",
        "confidence": "high",
        "simulation_action": "Replace multi-mill fallback with Saffle mill for this paper/padding scenario.",
    },
    {
        "id": "SITE_FRN-9C546CCC918C61_NAGOYA_NYLON",
        "names": ["FRN-0F56088BEA4986"],
        "component_any": ["nylon"],
        "site_name": "FRN-9C546CCC918C61 Nagoya Plant",
        "lat": None,
        "lon": None,
        "location": "Nagoya, Japan",
        "country_code": "JP",
        "site_address": '',
        "geocode_query": '',
        "geocode_status": "source_backed_industrial_site",
        "source_url": "https://sources.invalid/FRN-0F56088BEA4986/fbe4410125ad0498",
        "source_note": "FRN-9C546CCC918C61 environmental data lists Nagoya Plant and AMILAN nylon resin.",
        "confidence": "high_for_nylon_only",
        "simulation_action": "Use Nagoya for FRN-9C546CCC918C61 nylon records only; keep generic textile/composite FRN-9C546CCC918C61 records unchanged unless grade is known.",
    },
    {
        "id": "SITE_FRN-9C546CCC918C61_EHIME_CARBON",
        "names": ["FRN-0F56088BEA4986"],
        "component_any": ["titane fibre de carbone"],
        "site_name": "FRN-9C546CCC918C61 Ehime Plant",
        "lat": None,
        "lon": None,
        "location": "Masaki, Japan",
        "country_code": "JP",
        "site_address": '',
        "geocode_query": '',
        "geocode_status": "source_backed_industrial_site_nearby_station_geocode",
        "source_url": "https://sources.invalid/FRN-8A956B599D7510/472a15487d9df296",
        "source_note": "FRN-9C546CCC918C61 gives the Ehime Plant address and says it is near Masaki Station; FRN-9C546CCC918C61 environmental data lists TORAYCA carbon fiber at Ehime Plant.",
        "confidence": "medium_high",
        "simulation_action": "Use Ehime for carbon-fiber record; exact gate coordinate can be refined later.",
    },
]


UNAPPLIED_DECISIONS = [
    {
        "name": "FRN-7BCA1282BFEC03",
        "decision": "not_applied",
        "site_candidate": "XPO Europe HQ, 192 Avenue Thiers, Lyon, France, or route-specific XPO operating center",
        "source_url": "https://europe.xpo.com/en/industries/aerospace-and-defence/",
        "rationale": "FRN-B5DA4EA4F8BEF1 nodes should be modeled as route legs/hubs, not as a supplier plant. Public data does not identify the actual route hub for these records.",
        "simulation_action": "Keep as logistics provider; require route lane or hub assignment before replacing Greenwich/Lyon HQ.",
    },
    {
        "name": "FRN-B9C4C86C42C8B4",
        "decision": "not_applied",
        "site_candidate": "FRN-2B32314A8C4A0F, Defense & Marine, Middletown, PA candidate",
        "source_url": "https://www.tti.com/content/ttiinc/en/manufacturers/FRN-B9C4C86C42C8B4/resources/FRN-2B32314A8C4A0F-defense-marine.html",
        "rationale": "TE has AD&M operations but the exact cable/bracket part number is missing; a plant assignment would be false precision.",
        "simulation_action": "Keep Berwyn/HQ candidate inactive for site simulation until PN/BOM/AVL is available.",
    },
    {
        "name": "FRN-6378B78052F4FE",
        "decision": "partial_only",
        "site_candidate": "FRN-6378B78052F4FE Advanced Materials Tielt applied only for Ertalon records",
        "source_url": "https://sources.invalid/FRN-6378B78052F4FE/7fe70d1186a82d79",
        "rationale": "Non-Ertalon Mitsubishi records include nylon, LCD/display and generic molded plastic; public data is insufficient to allocate all to Tielt.",
        "simulation_action": "Use Tielt only for Ertalon; require grade/PN for other Mitsubishi records.",
    },
    {
        "name": "FRN-0F56088BEA4986",
        "decision": "partial_only",
        "site_candidate": "Nagoya for nylon, Ehime for carbon fiber; generic textile/polymer records unchanged",
        "source_url": "https://sources.invalid/FRN-0F56088BEA4986/fbe4410125ad0498",
        "rationale": "FRN-9C546CCC918C61 has multiple relevant Japanese plants. Nagoya/Ehime are source-backed for nylon/carbon, but textile/velcro/generic polymer records need grade-level traceability.",
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
