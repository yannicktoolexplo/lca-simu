#!/usr/bin/env python3
"""Apply user-provided site geolocation refinements to the reviewed supply JSON."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any


BASE_DIR = Path(__file__).resolve().parent
INPUT_JSON = BASE_DIR / "output8_GEO_normalized_final_site_reviewed.json"
OUTPUT_JSON = BASE_DIR / "output8_GEO_normalized_final_site_refined.json"
INPUT_CSV = Path(r"C:\Users\yannick.martz\Downloads\site_geolocation_refinement_lca_simu.csv")
CHANGELOG_CSV = BASE_DIR / "site_geolocation_refinement_applied_changes.csv"
REPORT_MD = BASE_DIR / "site_geolocation_refinement_applied_report.md"

COUNTRY_CODE = {
    "Belgium": "BE",
    "China": "CN",
    "France": "FR",
    "India": "IN",
    "Japan": "JP",
    "Sweden": "SE",
    "United Kingdom": "GB",
    "United States": "US",
}


def norm(value: Any) -> str:
    return str(value or "").strip().lower()


def has_any(text: str, needles: list[str]) -> bool:
    text_n = norm(text)
    return any(needle in text_n for needle in needles)


def material_text(record: dict[str, Any]) -> str:
    raw = record.get("raw_materials") or []
    refs = record.get("material_modeling_refs") or []
    return " | ".join(
        [
            str(record.get("system") or ""),
            str(record.get("component") or ""),
            " ".join(str(x) for x in raw),
            " ".join(str(x) for x in refs),
        ]
    )


def is_aluminium_record(record: dict[str, Any]) -> bool:
    text = material_text(record)
    return has_any(text, ["aluminium", "aluminum", " a2017", " a2024", " a5086", " a6060", "alu"])


def is_steel_record(record: dict[str, Any]) -> bool:
    text = material_text(record)
    return has_any(
        text,
        [
            "steel",
            "acier",
            "inox",
            "35nc6",
            "30ncd6",
            "15cdv6",
            "4140",
            "z10cnt18",
            "nickel-chrome",
        ],
    )


def can_keep_steel_mill_candidate(record: dict[str, Any]) -> bool:
    text = material_text(record)
    if is_steel_record(record):
        return True
    # Bracket records may have incomplete material tagging but can still be metal hardware.
    return has_any(text, ["bracket"])


def is_toray_nagoya_context(record: dict[str, Any]) -> bool:
    text = material_text(record)
    if has_any(text, ["velours", "velcro", "tissu", "textile", "cuir", "leather", "remote", "telecommande", "télécommande", "steel", "acier", "resine", "résine", "composite", "caoutchouc", "rubber", "polychloroprene"]):
        return False
    return has_any(
        text,
        [
            "ertalon",
            "polyamide",
            "nylon",
            "engineering plastic",
            "moulage plastique",
            "injection plastique",
            "kydex",
            "nida",
        ],
    )


def is_mitsubishi_hiratsuka_context(record: dict[str, Any]) -> bool:
    text = material_text(record)
    if has_any(text, ["display", "liquid crystal", "powerbox", "telecommande", "télécommande", "electronics", "electrical"]):
        return False
    return has_any(
        text,
        [
            "nylon",
            "polyamide",
            "engineering plastic",
            "moulage plastique",
            "injection plastique",
            "nida",
            "polychloroprene",
            "caoutchouc",
        ],
    )


def read_refinements(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def find_ref(rows: list[dict[str, str]], name: str, action_prefix: str | None = None, row_type: str | None = None) -> dict[str, str]:
    for row in rows:
        if row.get("original_name") != name:
            continue
        if action_prefix and not row.get("recommended_action", "").startswith(action_prefix):
            continue
        if row_type and row.get("row_type") != row_type:
            continue
        return row
    raise KeyError((name, action_prefix, row_type))


def snapshot(entry: dict[str, Any]) -> dict[str, Any]:
    keys = [
        "name",
        "location",
        "country_code",
        "lat",
        "lon",
        "geocode_status",
        "geocode_provider",
        "geocode_query",
        "site_address",
        "site_selection_name",
    ]
    return {key: entry.get(key) for key in keys}


def apply_refined_site(
    entry: dict[str, Any],
    row: dict[str, str],
    *,
    status: str,
    provider_suffix: str = "download_refinement_2026-05-21",
    action_override: str | None = None,
) -> None:
    entry.setdefault("location_review_before", snapshot(entry))
    country = row.get("refined_country") or entry.get("country_code") or ""
    location = row.get("refined_city_or_area") or country
    if country and location and country not in location:
        location = f"{location}, {country}"

    entry["location"] = location
    entry["country_code"] = COUNTRY_CODE.get(country, entry.get("country_code"))
    entry["lat"] = float(row["refined_lat"])
    entry["lon"] = float(row["refined_lon"])
    entry["site_address"] = row.get("refined_address") or row.get("refined_site_name")
    entry["geocode_query"] = row.get("refined_address") or row.get("refined_site_name")
    entry["geocode_status"] = status
    entry["geocode_provider"] = f"manual:{provider_suffix}"
    entry["site_selection_name"] = row.get("refined_site_name")
    entry["site_selection_confidence"] = row.get("confidence")
    entry["site_selection_source_url"] = row.get("source_url")
    entry["site_selection_note"] = row.get("evidence_summary")
    entry["simulation_site_action"] = action_override or row.get("simulation_action")
    entry["site_precision_level"] = row.get("precision_level")
    entry["site_refinement_row_type"] = row.get("row_type")
    entry["site_refinement_action"] = row.get("recommended_action")
    source_ids = entry.setdefault("source_ids", [])
    source_id = f"USER_SITE_REFINEMENT_{norm(row.get('original_name')).replace(' ', '_').replace('/', '_')}"
    if source_id not in source_ids:
        source_ids.append(source_id)


def mark_unknown_site(entry: dict[str, Any], row: dict[str, str]) -> None:
    entry.setdefault("location_review_before", snapshot(entry))
    entry["location"] = row.get("refined_site_name") or "unknown site"
    entry["lat"] = None
    entry["lon"] = None
    entry["site_address"] = ""
    entry["geocode_query"] = row.get("recommended_action")
    entry["geocode_status"] = "site_unknown_requires_material_grade_or_supplier_proof"
    entry["geocode_provider"] = "manual:download_refinement_2026-05-21"
    entry["site_selection_name"] = row.get("refined_site_name")
    entry["site_selection_confidence"] = row.get("confidence")
    entry["site_selection_source_url"] = row.get("source_url")
    entry["site_selection_note"] = row.get("evidence_summary")
    entry["simulation_site_action"] = row.get("simulation_action")
    entry["site_refinement_row_type"] = row.get("row_type")
    entry["site_refinement_action"] = row.get("recommended_action")


def add_alternative_site(record: dict[str, Any], row: dict[str, str]) -> None:
    alternatives = record.setdefault("unverified_supplier_candidates", [])
    candidate = {
        "name": row.get("refined_site_name"),
        "role_hint": row.get("role_hint"),
        "location": f"{row.get('refined_city_or_area')}, {row.get('refined_country')}",
        "country_code": COUNTRY_CODE.get(row.get("refined_country")),
        "lat": float(row["refined_lat"]),
        "lon": float(row["refined_lon"]),
        "site_address": row.get("refined_address"),
        "source_url": row.get("source_url"),
        "confidence": row.get("confidence"),
        "reason": row.get("simulation_action"),
        "candidate_status": "alternative_inactive_until_pn_confirms",
    }
    if not any(c.get("name") == candidate["name"] for c in alternatives if isinstance(c, dict)):
        alternatives.append(candidate)


def remove_supplier(record: dict[str, Any], supplier_name: str, reason: str) -> list[dict[str, Any]]:
    removed: list[dict[str, Any]] = []
    kept = []
    for entry in record.get("suppliers") or []:
        if isinstance(entry, dict) and entry.get("name") == supplier_name:
            removed.append(entry)
        else:
            kept.append(entry)
    if removed:
        record["suppliers"] = kept
        excluded = record.setdefault("excluded_suppliers", [])
        for entry in removed:
            excluded.append(
                {
                    "name": entry.get("name"),
                    "role_hint": entry.get("role_hint"),
                    "reason": reason,
                    "previous_status": entry.get("supplier_status"),
                    "previous_location": entry.get("location"),
                    "source_ids": entry.get("source_ids", []),
                }
            )
    return removed


def main() -> None:
    data = json.loads(INPUT_JSON.read_text(encoding="utf-8"))
    records = data["records"] if isinstance(data, dict) and "records" in data else data
    rows = read_refinements(INPUT_CSV)

    row_toray_nagoya = find_ref(rows, "Toray Industries", "SPLIT_REQUIRED: replace")
    row_toray_unknown = find_ref(rows, "Toray Industries", "DO_NOT_FORCE_SITE")
    row_mitsubishi = find_ref(rows, "Mitsubishi Chemical", "REPLACE_HQ_FALLBACK")
    row_xpo = find_ref(rows, "XPO Logistic", "REPLACE_US_HQ_FOR_EUROPEAN_FLOWS")
    row_te_evreux = find_ref(rows, "TE Connectivity", "REPLACE_US_HQ_WITH_AEROSPACE_CONNECTOR_SITE")
    row_te_toulouse = find_ref(rows, "TE Connectivity", "ALTERNATIVE_SITE_IF_SENSOR_OR_ELECTRONIC_PART")

    candidate_rows = {
        "Tata Steel": find_ref(rows, "Tata Steel", "KEEP_AS_STEEL_CANDIDATE_REMOVE_FROM_ALUMINIUM"),
        "China Baowu / Baosteel": find_ref(rows, "China Baowu / Baosteel", "KEEP_AS_STEEL_CANDIDATE_CERTIFICATE_REQUIRED"),
        "ArcelorMittal": find_ref(rows, "ArcelorMittal", "KEEP_AS_SPECIAL_STEEL_CANDIDATE_CERTIFICATE_REQUIRED"),
        "Nucor Corp": find_ref(rows, "Nucor Corp", "KEEP_AS_STEEL_CANDIDATE_CERTIFICATE_REQUIRED"),
        "Aluminium Corporation of China / Chalco": find_ref(rows, "Aluminium Corporation of China / Chalco", "KEEP_AS_ALUMINIUM_PRODUCER_CANDIDATE_CERTIFICATE_REQUIRED"),
    }

    approx_rows = {
        "Huddersfield Textiles": find_ref(rows, "Huddersfield Textiles", "REPLACE_TOWN_CENTROID_WITH_COMPANY_SITE"),
        "Shin-Etsu Silicones": find_ref(rows, "Shin-Etsu Silicones", "REPLACE_TOKYO_OR_CITY_FALLBACK_WITH_GUNMA_PLANT"),
        "Silicone Engineering": find_ref(rows, "Silicone Engineering", "REPLACE_CITY_POINT_WITH_MANUFACTURING_CENTRE"),
        "Daio Paper Corporation": find_ref(rows, "Daio Paper Corporation", "REPLACE_CITY_NOTE_WITH_MISHIMA_MILL_SITE"),
    }

    changes: list[dict[str, Any]] = []

    for idx, record in enumerate(records, 1):
        if not isinstance(record, dict) or record.get("simulation_supply_usable") is False:
            continue
        record_id = record.get("record_index") or record.get("index") or idx

        if is_aluminium_record(record):
            removed = remove_supplier(
                record,
                "Tata Steel",
                "Removed by site refinement: Tata Steel/Jamshedpur is a steel candidate and must not appear in aluminium chains.",
            )
            for entry in removed:
                changes.append(
                    {
                        "record_index": record_id,
                        "supplier": entry.get("name"),
                        "change_type": "removed_from_aluminium_chain",
                        "old_location": entry.get("location"),
                        "new_location": "",
                        "note": "Tata Steel kept only for steel records.",
                    }
                )

        if not can_keep_steel_mill_candidate(record):
            for steel_supplier in ["Tata Steel", "China Baowu / Baosteel", "ArcelorMittal", "Nucor Corp"]:
                removed = remove_supplier(
                    record,
                    steel_supplier,
                    "Removed by site refinement: steel-mill candidate on a non-steel/non-bracket context.",
                )
                for entry in removed:
                    changes.append(
                        {
                            "record_index": record_id,
                            "supplier": entry.get("name"),
                            "change_type": "removed_steel_candidate_from_non_steel_context",
                            "old_location": entry.get("location"),
                            "new_location": "",
                            "note": record.get("component"),
                        }
                    )

        for entry in record.get("suppliers") or []:
            if not isinstance(entry, dict):
                continue
            name = entry.get("name")
            old = snapshot(entry)

            if name == "Toray Industries" and entry.get("geocode_query") == "Tokyo 103-8666, Japan fallback; choose actual production site":
                if is_toray_nagoya_context(record):
                    apply_refined_site(
                        entry,
                        row_toray_nagoya,
                        status="source_backed_industrial_site_candidate",
                        action_override="Nagoya applied only for nylon/polyamide/engineering-plastics contexts; grade certificate still required.",
                    )
                    changes.append({"record_index": record_id, "supplier": name, "change_type": "toray_split_nagoya", "old_location": old.get("location"), "new_location": entry.get("location"), "note": record.get("component")})
                else:
                    mark_unknown_site(entry, row_toray_unknown)
                    changes.append({"record_index": record_id, "supplier": name, "change_type": "toray_generic_unknown_site", "old_location": old.get("location"), "new_location": entry.get("location"), "note": record.get("component")})

            elif name == "Mitsubishi Chemical" and entry.get("geocode_status") == "fallback_site_needs_source":
                if is_mitsubishi_hiratsuka_context(record):
                    apply_refined_site(
                        entry,
                        row_mitsubishi,
                        status="source_backed_industrial_site_candidate",
                        action_override="Hiratsuka applied for polymer/engineering-plastics contexts; PN/grade validation still required.",
                    )
                    changes.append({"record_index": record_id, "supplier": name, "change_type": "mitsubishi_hiratsuka", "old_location": old.get("location"), "new_location": entry.get("location"), "note": record.get("component")})
                else:
                    entry["site_refinement_action"] = "not_applied_to_non_polymer_context"
                    entry["simulation_site_action"] = "Do not apply Hiratsuka to display/electronics records without BOM/PN proving Mitsubishi Chemical material scope."
                    changes.append({"record_index": record_id, "supplier": name, "change_type": "mitsubishi_left_unresolved_non_polymer", "old_location": old.get("location"), "new_location": entry.get("location"), "note": record.get("component")})

            elif name == "TE Connectivity":
                apply_refined_site(entry, row_te_evreux, status="source_backed_aerospace_connector_site_candidate")
                add_alternative_site(record, row_te_toulouse)
                changes.append({"record_index": record_id, "supplier": name, "change_type": "te_evreux_with_toulouse_alternative", "old_location": old.get("location"), "new_location": entry.get("location"), "note": record.get("component")})

            elif name in candidate_rows:
                row = candidate_rows[name]
                if name == "Tata Steel" and not can_keep_steel_mill_candidate(record):
                    continue
                status = "source_backed_industrial_site_candidate_requires_certificate"
                apply_refined_site(entry, row, status=status)
                changes.append({"record_index": record_id, "supplier": name, "change_type": "candidate_site_metadata_refined", "old_location": old.get("location"), "new_location": entry.get("location"), "note": row.get("recommended_action")})

            elif name in approx_rows:
                row = approx_rows[name]
                status = "source_backed_industrial_site_approx"
                apply_refined_site(entry, row, status=status)
                changes.append({"record_index": record_id, "supplier": name, "change_type": "approx_site_refined", "old_location": old.get("location"), "new_location": entry.get("location"), "note": row.get("recommended_action")})

        for entry in record.get("logistics_providers") or []:
            if isinstance(entry, dict) and entry.get("name") == "XPO Logistic":
                old = snapshot(entry)
                apply_refined_site(entry, row_xpo, status="source_backed_europe_company_hq_not_depot")
                changes.append({"record_index": record_id, "supplier": "XPO Logistic", "change_type": "xpo_lyon_company_node", "old_location": old.get("location"), "new_location": entry.get("location"), "note": "Use for company-level EU logistics node, not lane depot."})

    meta = data.setdefault("_meta", {}) if isinstance(data, dict) else {}
    meta["site_geolocation_refinement_applied"] = {
        "input_csv": str(INPUT_CSV),
        "changes": len(changes),
        "output_json": str(OUTPUT_JSON),
        "rule": "Apply source-backed refined sites; keep generic or non-matching contexts unresolved instead of forcing false precision.",
    }

    OUTPUT_JSON.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    with CHANGELOG_CSV.open("w", newline="", encoding="utf-8") as handle:
        fieldnames = ["record_index", "supplier", "change_type", "old_location", "new_location", "note"]
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(changes)

    counts: dict[str, int] = {}
    for change in changes:
        counts[change["change_type"]] = counts.get(change["change_type"], 0) + 1

    with REPORT_MD.open("w", encoding="utf-8") as handle:
        handle.write("# Applied site geolocation refinement\n\n")
        handle.write(f"- Input JSON: `{INPUT_JSON}`\n")
        handle.write(f"- Refinement CSV: `{INPUT_CSV}`\n")
        handle.write(f"- Output JSON: `{OUTPUT_JSON}`\n")
        handle.write(f"- Change log: `{CHANGELOG_CSV}`\n")
        handle.write(f"- Total changes/actions: **{len(changes)}**\n\n")
        handle.write("## Change counts\n\n")
        handle.write("| change_type | count |\n|---|---:|\n")
        for key, value in sorted(counts.items()):
            handle.write(f"| {key} | {value} |\n")
        handle.write("\n## Application notes\n\n")
        handle.write("- Tata Steel was removed from aluminium chains and kept only as a steel candidate.\n")
        handle.write("- Toray Tokyo fallback was split: Nagoya for nylon/polyamide/engineering plastics, unknown site for generic textile/velcro/leather/composite/electronics contexts.\n")
        handle.write("- Mitsubishi Hiratsuka was applied only to polymer/engineering-plastics contexts; display/electronics rows remain unresolved until BOM/PN proof.\n")
        handle.write("- XPO Lyon is a company-level European logistics node, not a physical route depot.\n")
        handle.write("- TE Evreux is applied as the connector/cable-hardware candidate; Toulouse is stored as an inactive sensor/electronics alternative.\n")

    print(f"[OK] wrote {OUTPUT_JSON}")
    print(f"[OK] wrote {CHANGELOG_CSV} ({len(changes)} changes)")
    print(f"[OK] wrote {REPORT_MD}")


if __name__ == "__main__":
    main()
