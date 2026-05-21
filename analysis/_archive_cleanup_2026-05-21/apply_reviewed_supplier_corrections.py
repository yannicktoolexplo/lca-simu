#!/usr/bin/env python3
"""Apply reviewed uncertain-supplier corrections to the mass-estimated GEO JSON."""

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


ROOT = Path(__file__).resolve().parents[1]
INPUT_JSON = ROOT / "analysis" / "output8_GEO_normalized_corrected_mass_estimated.json"
REVIEW_CSV = ROOT / "analysis" / "output8_GEO_reviewed_uncertain_supplier_tiers.csv"
OUTPUT_JSON = ROOT / "analysis" / "output8_GEO_normalized_final_corrected.json"
CHANGES_CSV = ROOT / "analysis" / "output8_GEO_final_corrections_applied.csv"
REPORT_MD = ROOT / "analysis" / "output8_GEO_final_correction_report.md"

ROLE_FROM_TIER = {
    "T4": "tier4_raw_material",
    "T3": "tier3_first_transformation",
    "T2": "tier2_second_transformation",
    "T1": "tier1",
}

EXCLUDE_STATUSES = {
    "generic_placeholder",
    "industry_association_not_supplier",
    "wrong_scope_or_unrelated",
    "not_verified_probable_error",
    "wrong_scope_or_too_broad",
}

EXCLUDE_ACTION_PREFIXES = (
    "remove_",
    "remove-",
)

COTS_STATUSES = {
    "cots_brand_not_supply_node",
    "validated_supplier_cots_upstream",
}

PACKAGING_STATUSES = {
    "packaging_or_paper_auxiliary",
}

UNVERIFIED_STATUSES = {
    "needs_business_validation",
    "legacy_or_defunct_supplier",
}

KNOWN_LOCATION_FIXES = {
    "huddersfield textiles": {
        "lat": 53.6458,
        "lon": -1.7850,
        "location": "Huddersfield, United Kingdom",
        "country_code": "GB",
        "site_address": "Huddersfield, West Yorkshire, United Kingdom",
        "source_url": "https://www.huddersfieldtextiles.com/",
        "confidence": "medium",
    },
    "shin etsu silicones": {
        "lat": 35.6812,
        "lon": 139.7671,
        "location": "Tokyo, Japan",
        "country_code": "JP",
        "site_address": "Marunouchi, Chiyoda-ku, Tokyo, Japan",
        "source_url": "https://www.shinetsu.co.jp/en/company/network/office/",
        "confidence": "medium_high",
    },
    "silicone engineering": {
        "lat": 53.7486,
        "lon": -2.4875,
        "location": "Blackburn, United Kingdom",
        "country_code": "GB",
        "site_address": "Greenbank Business Park, Blakewater Road, Blackburn, Lancashire BB1 3HU, United Kingdom",
        "source_url": "https://silicone.co.uk/",
        "confidence": "medium_high",
    },
    "daio paper corporation": {
        "lat": 33.9803,
        "lon": 133.5498,
        "location": "Shikokuchuo, Japan",
        "country_code": "JP",
        "site_address": "Shikokuchuo-shi, Ehime, Japan",
        "source_url": "https://www.daio-paper.co.jp/en/company/base/",
        "confidence": "medium_high",
    },
    "kemko aerospace": {
        "lat": 38.6270,
        "lon": -90.1994,
        "location": "St. Louis, United States",
        "country_code": "US",
        "site_address": "St. Louis, Missouri, United States",
        "source_url": "https://kemkoaerospace.net/",
        "confidence": "low",
    },
    "liebherr aerospace": {
        "lat": 47.6031,
        "lon": 9.8896,
        "location": "Lindenberg im Allgau, Germany",
        "country_code": "DE",
        "site_address": "Liebherr-Aerospace Lindenberg GmbH, Lindenberg im Allgau, Germany",
        "source_url": "https://www.liebherr.com/en/int/products/aerospace-and-transportation-systems/aerospace-and-transportation-systems.html",
        "confidence": "medium_high",
    },
    "te connectivity": {
        "lat": 40.0440,
        "lon": -75.4388,
        "location": "Berwyn, United States",
        "country_code": "US",
        "site_address": "Berwyn, Pennsylvania, United States",
        "source_url": "https://www.te.com/en/industries/aerospace.html",
        "confidence": "medium",
    },
    "xpo logistic": {
        "lat": 41.0262,
        "lon": -73.6282,
        "location": "Greenwich, United States",
        "country_code": "US",
        "site_address": "Greenwich, Connecticut, United States",
        "source_url": "https://investors.xpo.com/",
        "confidence": "medium",
    },
    "mondi": {
        "lat": 48.2076,
        "lon": 16.3840,
        "location": "Vienna, Austria",
        "country_code": "AT",
        "site_address": "Mondi Group Office, Vienna, Austria",
        "source_url": "https://www.mondigroup.com/locations/",
        "confidence": "medium_high",
    },
    "diodes incorporated": {
        "lat": 33.0198,
        "lon": -96.6989,
        "location": "Plano, United States",
        "country_code": "US",
        "site_address": "Plano, Texas, United States",
        "source_url": "https://www.diodes.com/about/company-profile/",
        "confidence": "medium",
    },
    "intel": {
        "lat": 37.3875,
        "lon": -121.9636,
        "location": "Santa Clara, United States",
        "country_code": "US",
        "site_address": "Santa Clara, California, United States",
        "source_url": "https://www.intel.com/content/www/us/en/company-overview/company-overview.html",
        "confidence": "medium",
    },
    "rohm": {
        "lat": 35.0116,
        "lon": 135.7681,
        "location": "Kyoto, Japan",
        "country_code": "JP",
        "site_address": "Kyoto, Japan",
        "source_url": "https://www.rohm.com/company",
        "confidence": "medium",
    },
    "sony": {
        "lat": 35.6285,
        "lon": 139.7405,
        "location": "Tokyo, Japan",
        "country_code": "JP",
        "site_address": "Tokyo, Japan",
        "source_url": "https://www.sony.com/en/SonyInfo/CorporateInfo/",
        "confidence": "medium",
    },
    "tsmc": {
        "lat": 24.7816,
        "lon": 120.9934,
        "location": "Hsinchu, Taiwan",
        "country_code": "TW",
        "site_address": "Hsinchu Science Park, Taiwan",
        "source_url": "https://www.tsmc.com/english/aboutTSMC",
        "confidence": "medium",
    },
}


def norm(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value or "").lower()).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


def slug(value: Any) -> str:
    return norm(value).replace(" ", "_")


def as_list(value: Any) -> list[str]:
    if value is None or value == "":
        return []
    if isinstance(value, list):
        return [str(item) for item in value if item]
    return [str(value)]


def supplier_key(entry: dict[str, Any]) -> tuple[str, str]:
    return (str(entry.get("name") or "").strip(), str(entry.get("role_hint") or "").strip())


def review_key(row: dict[str, str]) -> tuple[str, str]:
    return (str(row.get("supplier") or "").strip(), str(row.get("role_hint") or "").strip())


def source_ids_from_review(row: dict[str, str]) -> list[str]:
    raw = row.get("review_source_ids") or ""
    return [part.strip() for part in raw.split(";") if part.strip()]


def refresh_site_id(entry: dict[str, Any]) -> None:
    entry["supplier_id"] = slug(entry.get("name"))
    lat = entry.get("lat")
    lon = entry.get("lon")
    if isinstance(lat, (int, float)) and isinstance(lon, (int, float)) and math.isfinite(lat) and math.isfinite(lon):
        entry["site_id"] = f"{entry['supplier_id']}@{round(float(lat), 4)},{round(float(lon), 4)}"
    else:
        entry["site_id"] = f"{entry['supplier_id']}@unverified"


def apply_known_location_fix(entry: dict[str, Any]) -> bool:
    fix = KNOWN_LOCATION_FIXES.get(norm(entry.get("name")))
    if not fix:
        return False
    current_lat = entry.get("lat")
    current_lon = entry.get("lon")
    if isinstance(current_lat, (int, float)) and isinstance(current_lon, (int, float)) and math.isfinite(current_lat) and math.isfinite(current_lon):
        return False
    entry["lat"] = fix["lat"]
    entry["lon"] = fix["lon"]
    entry["location"] = fix["location"]
    entry["country_code"] = fix["country_code"]
    entry["site_address"] = fix["site_address"]
    entry["geocode_provider"] = "manual:review_followup"
    entry["geocode_query"] = fix["site_address"]
    entry["geocode_status"] = "source_backed_city_or_hq"
    entry["source_confidence"] = fix["confidence"]
    entry["geocode_source_url"] = fix["source_url"]
    notes = as_list(entry.get("correction_notes"))
    notes.append("location_filled_from_review_followup")
    entry["correction_notes"] = list(dict.fromkeys(notes))
    refresh_site_id(entry)
    return True


def component_is_chemical_or_polymer(record: dict[str, Any]) -> bool:
    text = norm(
        " ".join(
            [
                str(record.get("component") or ""),
                str(record.get("raw_materials") or ""),
                str(record.get("system") or ""),
            ]
        )
    )
    return any(
        token in text
        for token in [
            "polymer",
            "polymere",
            "plastic",
            "plastique",
            "kydex",
            "lexan",
            "silicone",
            "resine",
            "resin",
            "composite",
            "caoutchouc",
            "polychloroprene",
            "film decor",
            "aerfilm",
            "mousse",
            "polyurethane",
            "nylon",
        ]
    )


def scope_allows_keep(record: dict[str, Any], review: dict[str, str]) -> bool:
    action = review.get("reviewed_action") or ""
    if action == "keep_only_for_polymer_records":
        return component_is_chemical_or_polymer(record)
    if action == "keep_only_for_chemical_or_composite_records":
        return component_is_chemical_or_polymer(record)
    return True


def change_row(record_index: int, record: dict[str, Any], supplier: dict[str, Any], action: str, detail: str) -> dict[str, Any]:
    return {
        "record_index": record_index,
        "system": record.get("system", ""),
        "component": record.get("component", ""),
        "supplier_before": supplier.get("original_supplier", {}).get("name") if isinstance(supplier.get("original_supplier"), dict) else supplier.get("name", ""),
        "supplier_after": supplier.get("name", ""),
        "role_hint": supplier.get("role_hint", ""),
        "action": action,
        "detail": detail,
    }


def target_for_review(record: dict[str, Any], review: dict[str, str]) -> tuple[str, str]:
    status = review.get("review_status") or ""
    action = review.get("reviewed_action") or ""
    if status in PACKAGING_STATUSES or review.get("recommended_tier_code") == "PKG":
        return "packaging_suppliers", "moved_to_packaging"
    if status in COTS_STATUSES or "cots" in action or action.startswith("replace_with_exact"):
        return "cots_upstream_suppliers", "moved_to_cots_upstream"
    if status in UNVERIFIED_STATUSES or action.startswith("verify_exact") or action in {"verify_exact_supplier", "replace_with_current_legal_entity"}:
        return "unverified_supplier_candidates", "moved_to_unverified"
    if status in EXCLUDE_STATUSES or action.startswith(EXCLUDE_ACTION_PREFIXES):
        return "excluded_suppliers", "removed_from_switchable_network"
    if not scope_allows_keep(record, review):
        return "excluded_suppliers", "removed_out_of_scope_for_component"
    return "suppliers", "kept_or_normalized"


def apply_review_to_supplier(supplier: dict[str, Any], review: dict[str, str]) -> dict[str, Any]:
    out = copy.deepcopy(supplier)
    before_name = str(out.get("name") or "")
    canonical = (review.get("canonical_supplier") or "").strip()
    action = review.get("reviewed_action") or ""
    if action == "merge_with_ESPACE":
        canonical = "ESPACE"
    if canonical and action not in {
        "remove_replace_with_named_supplier",
        "remove_from_supplier_network",
        "remove_or_replace_with_JAMCO_if_intended",
    }:
        out["name"] = canonical
    recommended_role = ROLE_FROM_TIER.get(review.get("recommended_tier_code") or "")
    if recommended_role:
        out["role_hint"] = recommended_role
    out["review_status"] = review.get("review_status", "")
    out["reviewed_action"] = action
    out["reviewed_confidence"] = review.get("reviewed_confidence", "")
    out["review_rationale"] = review.get("review_rationale", "")
    out["simulation_usable"] = True
    out["switchable_candidate"] = True
    source_ids = list(dict.fromkeys(as_list(out.get("source_ids")) + source_ids_from_review(review)))
    out["source_ids"] = source_ids
    notes = as_list(out.get("correction_notes"))
    if before_name != out.get("name"):
        notes.append(f"review_name_normalized:{before_name}->{out.get('name')}")
    if review.get("review_rationale"):
        notes.append("reviewed_uncertain_supplier")
    out["correction_notes"] = list(dict.fromkeys(notes))
    refresh_site_id(out)
    return out


def mark_non_switchable(supplier: dict[str, Any], layer: str) -> dict[str, Any]:
    out = copy.deepcopy(supplier)
    out["simulation_layer"] = layer
    out["simulation_usable"] = False
    out["switchable_candidate"] = False
    out["is_primary"] = False
    out["allocation_share_pct"] = 0.0
    return out


def merge_entries(existing: dict[str, Any], incoming: dict[str, Any]) -> None:
    existing["is_primary"] = bool(existing.get("is_primary")) or bool(incoming.get("is_primary"))
    existing["allocation_share_pct"] = max(float(existing.get("allocation_share_pct") or 0), float(incoming.get("allocation_share_pct") or 0))
    for field in ("source_ids", "correction_notes"):
        values = list(dict.fromkeys(as_list(existing.get(field)) + as_list(incoming.get(field))))
        existing[field] = values
    for field in ("description", "review_rationale"):
        parts = [part for part in [existing.get(field), incoming.get(field)] if part]
        if parts:
            existing[field] = "; ".join(dict.fromkeys(str(part) for part in parts))


def dedupe(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged: dict[tuple[str, str, str], dict[str, Any]] = {}
    order: list[tuple[str, str, str]] = []
    for entry in entries:
        key = (
            str(entry.get("supplier_id") or slug(entry.get("name"))),
            str(entry.get("role_hint") or ""),
            str(entry.get("site_id") or ""),
        )
        if key in merged:
            merge_entries(merged[key], entry)
        else:
            merged[key] = entry
            order.append(key)
    return [merged[key] for key in order]


def enforce_single_primary(record: dict[str, Any], changes: list[dict[str, Any]], record_index: int) -> None:
    by_role: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for supplier in record.get("suppliers") or []:
        by_role[str(supplier.get("role_hint") or "")].append(supplier)
    for role, group in by_role.items():
        primaries = [supplier for supplier in group if supplier.get("is_primary")]
        if len(primaries) == 1:
            continue
        if not primaries:
            chosen = group[0]
            chosen["is_primary"] = True
            chosen["supplier_status"] = "baseline_primary_inferred_after_review"
            changes.append(change_row(record_index, record, chosen, "infer_primary_after_review", f"selected {chosen.get('name')} as primary for {role}"))
        else:
            chosen = primaries[0]
            for other in primaries[1:]:
                other["is_primary"] = False
                other["supplier_status"] = "alternate_after_primary_review"
            changes.append(change_row(record_index, record, chosen, "resolve_multiple_primary_after_review", f"kept {chosen.get('name')} as primary for {role}"))


def apply_known_location_fixes(record: dict[str, Any], changes: list[dict[str, Any]], record_index: int, counters: Counter) -> None:
    fields = (
        "suppliers",
        "packaging_suppliers",
        "cots_upstream_suppliers",
        "unverified_supplier_candidates",
        "excluded_suppliers",
        "logistics_providers",
    )
    for field in fields:
        for supplier in record.get(field) or []:
            if not isinstance(supplier, dict):
                continue
            if apply_known_location_fix(supplier):
                changes.append(change_row(record_index, record, supplier, "fill_missing_location_from_review_followup", field))
                counters["fill_missing_location_from_review_followup"] += 1


def apply_record(record: dict[str, Any], reviews: dict[tuple[str, str], dict[str, str]], record_index: int, changes: list[dict[str, Any]], counters: Counter) -> dict[str, Any]:
    out = copy.deepcopy(record)
    out.setdefault("packaging_suppliers", [])
    out.setdefault("cots_upstream_suppliers", [])
    out.setdefault("unverified_supplier_candidates", [])
    out.setdefault("excluded_suppliers", [])
    kept_suppliers: list[dict[str, Any]] = []

    for supplier in out.get("suppliers") or []:
        review = reviews.get(supplier_key(supplier))
        if not review:
            kept_suppliers.append(supplier)
            continue
        reviewed = apply_review_to_supplier(supplier, review)
        target, applied_action = target_for_review(out, review)
        if target == "suppliers":
            kept_suppliers.append(reviewed)
            if supplier.get("name") != reviewed.get("name") or supplier.get("role_hint") != reviewed.get("role_hint"):
                changes.append(change_row(record_index, out, reviewed, "normalize_reviewed_supplier", review.get("review_rationale", "")))
            counters["kept_or_normalized"] += 1
        else:
            moved = mark_non_switchable(reviewed, target.replace("_suppliers", ""))
            out[target].append(moved)
            changes.append(change_row(record_index, out, moved, applied_action, review.get("review_rationale", "")))
            counters[applied_action] += 1

    out["suppliers"] = dedupe(kept_suppliers)
    for field in ("packaging_suppliers", "cots_upstream_suppliers", "unverified_supplier_candidates", "excluded_suppliers"):
        out[field] = dedupe(out.get(field) or [])
    enforce_single_primary(out, changes, record_index)
    apply_known_location_fixes(out, changes, record_index, counters)
    return out


def write_changes(rows: list[dict[str, Any]]) -> None:
    fields = ["record_index", "system", "component", "supplier_before", "supplier_after", "role_hint", "action", "detail"]
    with CHANGES_CSV.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def summary_counts(records: list[dict[str, Any]]) -> Counter:
    counts = Counter()
    for record in records:
        counts["records"] += 1
        for field in ("suppliers", "packaging_suppliers", "cots_upstream_suppliers", "unverified_supplier_candidates", "excluded_suppliers"):
            counts[field] += len(record.get(field) or [])
        for supplier in record.get("suppliers") or []:
            counts[f"role:{supplier.get('role_hint')}"] += 1
    return counts


def write_report(before_counts: Counter, after_counts: Counter, action_counts: Counter, changes_count: int) -> None:
    lines = [
        "# Final supplier corrections applied",
        "",
        f"- Input JSON: `{INPUT_JSON.as_posix()}`",
        f"- Review table: `{REVIEW_CSV.as_posix()}`",
        f"- Output JSON: `{OUTPUT_JSON.as_posix()}`",
        f"- Change log: `{CHANGES_CSV.as_posix()}`",
        "",
        "## Counts",
        "",
        f"- Supplier entries before: {before_counts['suppliers']}",
        f"- Supplier entries after switchable cleanup: {after_counts['suppliers']}",
        f"- Packaging/auxiliary entries: {after_counts['packaging_suppliers']}",
        f"- COTS upstream entries: {after_counts['cots_upstream_suppliers']}",
        f"- Unverified supplier candidates: {after_counts['unverified_supplier_candidates']}",
        f"- Excluded/non-supplier entries: {after_counts['excluded_suppliers']}",
        f"- Change rows: {changes_count}",
        "",
        "## Actions Applied",
        "",
    ]
    for action, count in action_counts.most_common():
        lines.append(f"- `{action}`: {count}")
    if action_counts.get("fill_missing_location_from_review_followup"):
        lines += [
            "",
            "## Location Follow-Up Sources",
            "",
        ]
        for supplier_key_name, fix in sorted(KNOWN_LOCATION_FIXES.items()):
            lines.append(
                f"- `{supplier_key_name}`: {fix['location']} "
                f"({fix['confidence']}) - {fix['source_url']}"
            )
    lines += [
        "",
        "## Switchable Supplier Roles After Cleanup",
        "",
    ]
    for key, count in sorted((key, value) for key, value in after_counts.items() if key.startswith("role:")):
        lines.append(f"- `{key.replace('role:', '')}`: {count}")
    lines += [
        "",
        "## Modeling Policy",
        "",
        "- `suppliers` now contains switchable production nodes only.",
        "- `packaging_suppliers` contains packaging/paper auxiliary candidates.",
        "- `cots_upstream_suppliers` contains electronics/COTS brands that should not be treated as direct switchable suppliers.",
        "- `unverified_supplier_candidates` contains plausible names that still need purchasing or engineering validation.",
        "- `excluded_suppliers` preserves placeholders, associations, wrong-scope entities, and likely errors for traceability.",
        "",
    ]
    REPORT_MD.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    source = json.loads(INPUT_JSON.read_text(encoding="utf-8"))
    records = source.get("records") or []
    review_rows = list(csv.DictReader(REVIEW_CSV.open(encoding="utf-8-sig")))
    reviews = {review_key(row): row for row in review_rows}
    changes: list[dict[str, Any]] = []
    counters: Counter = Counter()
    before_counts = summary_counts(records)
    cleaned_records = [apply_record(record, reviews, index, changes, counters) for index, record in enumerate(records, start=1)]
    output = copy.deepcopy(source)
    output["records"] = cleaned_records
    output.setdefault("_meta", {})
    output["_meta"]["final_review_corrections"] = {
        "source_file": INPUT_JSON.as_posix(),
        "review_file": REVIEW_CSV.as_posix(),
        "generated_at": dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat(),
        "script": Path(__file__).as_posix(),
        "policy": "validated production suppliers stay in suppliers; COTS, packaging, unverified, and excluded records are moved to separate layers",
    }
    OUTPUT_JSON.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    write_changes(changes)
    after_counts = summary_counts(cleaned_records)
    write_report(before_counts, after_counts, counters, len(changes))
    print(f"[OK] wrote {OUTPUT_JSON}")
    print(f"[OK] wrote {CHANGES_CSV}")
    print(f"[OK] wrote {REPORT_MD}")
    print(f"[INFO] suppliers {before_counts['suppliers']} -> {after_counts['suppliers']}; changes={len(changes)}")
    print("[INFO] actions=" + ", ".join(f"{key}:{value}" for key, value in counters.most_common()))


if __name__ == "__main__":
    main()
