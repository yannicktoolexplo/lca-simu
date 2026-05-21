#!/usr/bin/env python3
"""Apply the business review of missing tiers without inventing suppliers."""

from __future__ import annotations

import copy
import csv
import datetime as dt
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[1]
INPUT_JSON = ROOT / "analysis" / "output8_GEO_normalized_final_corrected.json"
MOST_PROBABLE_CSV = ROOT / "analysis" / "output8_GEO_missing_tier_most_probable.csv"
OUTPUT_JSON = ROOT / "analysis" / "output8_GEO_normalized_final_business_reviewed.json"
CHANGES_CSV = ROOT / "analysis" / "output8_GEO_business_review_changes.csv"
REPORT_MD = ROOT / "analysis" / "output8_GEO_business_review_report.md"

STEEL_T4_NAMES = {
    "Saarstahl",
    "ArcelorMittal",
    "China Baowu / Baosteel",
    "Tata Steel",
    "Nucor Corp",
}


def as_list(value: Any) -> list[str]:
    if value is None or value == "":
        return []
    if isinstance(value, list):
        return [str(item) for item in value if item]
    return [str(value)]


def append_note(entry: dict[str, Any], note: str) -> None:
    notes = as_list(entry.get("correction_notes"))
    notes.append(note)
    entry["correction_notes"] = list(dict.fromkeys(notes))


def change_row(record_index: int, record: dict[str, Any], supplier: dict[str, Any], action: str, detail: str) -> dict[str, Any]:
    return {
        "record_index": record_index,
        "system": record.get("system", ""),
        "component": record.get("component", ""),
        "supplier": supplier.get("name", ""),
        "role_hint": supplier.get("role_hint", ""),
        "action": action,
        "detail": detail,
    }


def mark_non_active(entry: dict[str, Any], layer: str, reason: str) -> dict[str, Any]:
    out = copy.deepcopy(entry)
    out["simulation_layer"] = layer
    out["simulation_usable"] = False
    out["switchable_candidate"] = False
    out["is_primary"] = False
    out["allocation_share_pct"] = 0.0
    out["business_review_status"] = reason
    append_note(out, reason)
    return out


def move_suppliers(
    record: dict[str, Any],
    record_index: int,
    predicate: Callable[[dict[str, Any]], bool],
    target_field: str,
    reason: str,
    changes: list[dict[str, Any]],
) -> int:
    moved_count = 0
    kept: list[dict[str, Any]] = []
    record.setdefault(target_field, [])
    for supplier in record.get("suppliers") or []:
        if isinstance(supplier, dict) and predicate(supplier):
            moved = mark_non_active(supplier, target_field.replace("_suppliers", ""), reason)
            record[target_field].append(moved)
            changes.append(change_row(record_index, record, moved, f"moved_to_{target_field}", reason))
            moved_count += 1
        else:
            kept.append(supplier)
    record["suppliers"] = kept
    return moved_count


def move_all_suppliers_to_excluded(record: dict[str, Any], record_index: int, reason: str, changes: list[dict[str, Any]]) -> int:
    count = 0
    record.setdefault("excluded_suppliers", [])
    for supplier in record.get("suppliers") or []:
        if not isinstance(supplier, dict):
            continue
        moved = mark_non_active(supplier, "lca_process_ref", reason)
        record["excluded_suppliers"].append(moved)
        changes.append(change_row(record_index, record, moved, "moved_to_excluded_suppliers", reason))
        count += 1
    record["suppliers"] = []
    return count


def enforce_single_primary(record: dict[str, Any], record_index: int, changes: list[dict[str, Any]]) -> None:
    by_role: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for supplier in record.get("suppliers") or []:
        if isinstance(supplier, dict):
            by_role[str(supplier.get("role_hint") or "")].append(supplier)
    for role, suppliers in by_role.items():
        primaries = [supplier for supplier in suppliers if supplier.get("is_primary")]
        if len(primaries) == 1:
            continue
        if not primaries and suppliers:
            chosen = suppliers[0]
            chosen["is_primary"] = True
            chosen["supplier_status"] = "baseline_primary_inferred_after_business_review"
            changes.append(change_row(record_index, record, chosen, "infer_primary_after_business_review", f"selected {chosen.get('name')} as primary for {role}"))
        elif len(primaries) > 1:
            chosen = primaries[0]
            for supplier in primaries[1:]:
                supplier["is_primary"] = False
                supplier["supplier_status"] = "alternate_after_business_review"
            changes.append(change_row(record_index, record, chosen, "resolve_multiple_primary_after_business_review", f"kept {chosen.get('name')} as primary for {role}"))


def load_decisions() -> dict[int, list[dict[str, str]]]:
    rows = list(csv.DictReader(MOST_PROBABLE_CSV.open(encoding="utf-8-sig")))
    by_record: dict[int, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        by_record[int(row["record_index"])].append(row)
    return by_record


def compact_decision(row: dict[str, str]) -> dict[str, str]:
    return {
        "missing_tier_code": row["missing_tier_code"],
        "resolution_class": row["resolution_class"],
        "most_probable_resolution": row["most_probable_resolution"],
        "recommended_modeling_decision": row["recommended_modeling_decision"],
        "confidence": row["confidence"],
        "validation_question": row["validation_question"],
    }


def apply_record(record: dict[str, Any], record_index: int, decisions: dict[int, list[dict[str, str]]], changes: list[dict[str, Any]], counters: Counter) -> dict[str, Any]:
    out = copy.deepcopy(record)
    out["missing_tier_business_review"] = [compact_decision(row) for row in decisions.get(record_index, [])]

    process_decisions = [
        row for row in decisions.get(record_index, [])
        if row.get("resolution_class") == "probable_internalized_process"
    ]
    if process_decisions:
        out["internalized_process_tiers"] = [
            {
                "missing_tier_code": row["missing_tier_code"],
                "process_owner_basis": row["most_probable_resolution"],
                "active_supplier_node_created": False,
                "validation_question": row["validation_question"],
                "confidence": row["confidence"],
            }
            for row in process_decisions
        ]
        counters["internalized_process_metadata"] += len(process_decisions)

    if record_index == 4:
        counters["combigo_packaging_review"] += move_suppliers(
            out,
            record_index,
            lambda s: s.get("name") == "Combigo" and s.get("role_hint") == "tier2_second_transformation",
            "packaging_suppliers",
            "business_review: Combigo looks like packaging/conditioning, not active material transformation for AERFILM",
            changes,
        )

    if record_index == 5:
        counters["wrong_steel_t4_on_copper"] += move_suppliers(
            out,
            record_index,
            lambda s: s.get("role_hint") == "tier4_raw_material" and s.get("name") in STEEL_T4_NAMES,
            "excluded_suppliers",
            "business_review: steel producer is wrong material family for copper alloy",
            changes,
        )
        counters["unverified_copper_t4"] += move_suppliers(
            out,
            record_index,
            lambda s: s.get("role_hint") == "tier4_raw_material" and s.get("name") == "Zijin Mining Group",
            "unverified_supplier_candidates",
            "business_review: possible copper upstream actor, but not a validated active material source",
            changes,
        )

    if record_index in {16, 51}:
        counters["wrong_alcoa_on_steel"] += move_suppliers(
            out,
            record_index,
            lambda s: s.get("role_hint") == "tier4_raw_material" and s.get("name") == "Alcoa",
            "excluded_suppliers",
            "business_review: Alcoa is an aluminium actor, not an active steel source for 35NC6",
            changes,
        )

    if record_index == 75:
        counters["wrong_metal_t3_on_polymer"] += move_suppliers(
            out,
            record_index,
            lambda s: s.get("role_hint") == "tier3_first_transformation" and s.get("name") == "Euralliage Ile de France",
            "excluded_suppliers",
            "business_review: Euralliage is a metals actor, not a polymer Lexan/FST transformation source",
            changes,
        )
        counters["polymer_t1_scope_validation"] += move_suppliers(
            out,
            record_index,
            lambda s: s.get("role_hint") == "tier1",
            "unverified_supplier_candidates",
            "business_review: metal T1 candidate not proven as Lexan/polymer thermoforming supplier",
            changes,
        )

    if record_index in {127, 156}:
        out["simulation_supply_usable"] = False
        out["record_review_status"] = "lca_process_reference_not_supplier_chain"
        out["lca_process_ref"] = {
            "original_component": out.get("component", ""),
            "reason": "business_review: process reference from SimaPro/GLO should not generate supplier tiers",
        }
        counters["lca_process_records_disabled"] += 1
        counters["lca_process_suppliers_removed"] += move_all_suppliers_to_excluded(
            out,
            record_index,
            "business_review: LCA process reference, not a supplier-chain item",
            changes,
        )

    enforce_single_primary(out, record_index, changes)
    return out


def summary_counts(records: list[dict[str, Any]]) -> Counter:
    counts = Counter()
    for record in records:
        counts["records"] += 1
        if record.get("simulation_supply_usable") is False:
            counts["disabled_records"] += 1
        for field in ("suppliers", "packaging_suppliers", "cots_upstream_suppliers", "unverified_supplier_candidates", "excluded_suppliers"):
            counts[field] += len(record.get(field) or [])
        for supplier in record.get("suppliers") or []:
            if isinstance(supplier, dict):
                counts[f"role:{supplier.get('role_hint')}"] += 1
    return counts


def write_changes(rows: list[dict[str, Any]]) -> None:
    fields = ["record_index", "system", "component", "supplier", "role_hint", "action", "detail"]
    with CHANGES_CSV.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def write_report(before: Counter, after: Counter, counters: Counter, changes: list[dict[str, Any]]) -> None:
    lines = [
        "# Business review applied to missing tiers",
        "",
        f"- Input JSON: `{INPUT_JSON.as_posix()}`",
        f"- Missing-tier decision CSV: `{MOST_PROBABLE_CSV.as_posix()}`",
        f"- Output JSON: `{OUTPUT_JSON.as_posix()}`",
        f"- Change log: `{CHANGES_CSV.as_posix()}`",
        "",
        "## Principle",
        "",
        "- No missing tier was completed by inventing an active supplier.",
        "- Metal T2 gaps are modeled as internalized process metadata under the primary T1.",
        "- Material-family mismatches are removed from the active supplier network.",
        "- LCA process-reference rows are disabled for supply-chain mapping/simulation.",
        "",
        "## Counts",
        "",
        f"- Active supplier entries before: {before['suppliers']}",
        f"- Active supplier entries after: {after['suppliers']}",
        f"- Disabled records: {after['disabled_records']}",
        f"- Unverified supplier candidates after: {after['unverified_supplier_candidates']}",
        f"- Excluded supplier entries after: {after['excluded_suppliers']}",
        f"- Change rows: {len(changes)}",
        "",
        "## Applied Actions",
        "",
    ]
    for action, count in counters.most_common():
        lines.append(f"- `{action}`: {count}")
    lines += [
        "",
        "## Active Roles After Review",
        "",
    ]
    for key, count in sorted((key, value) for key, value in after.items() if key.startswith("role:")):
        lines.append(f"- `{key.replace('role:', '')}`: {count}")
    lines += [
        "",
        "## Notes",
        "",
        "- R5 copper alloy: steel T4 candidates were removed from active suppliers; copper upstream remains unverified.",
        "- R16/R51 35NC6: Alcoa was removed from active steel chains.",
        "- R75 Lexan/FST: metal T3/T1 candidates were removed or demoted pending polymer routing validation.",
        "- R127/R156: SimaPro/GLO process references are no longer active supply-chain records in this reviewed JSON.",
        "",
    ]
    REPORT_MD.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    source = json.loads(INPUT_JSON.read_text(encoding="utf-8"))
    records = source.get("records") or []
    decisions = load_decisions()
    changes: list[dict[str, Any]] = []
    counters: Counter = Counter()
    before = summary_counts(records)
    reviewed_records = [
        apply_record(record, index, decisions, changes, counters)
        for index, record in enumerate(records, start=1)
    ]
    output = copy.deepcopy(source)
    output["records"] = reviewed_records
    output.setdefault("_meta", {})
    output["_meta"]["business_missing_tier_review"] = {
        "source_file": INPUT_JSON.as_posix(),
        "decision_file": MOST_PROBABLE_CSV.as_posix(),
        "generated_at": dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat(),
        "script": Path(__file__).as_posix(),
        "policy": "no invented active suppliers; wrong material-family suppliers removed; internal process tiers stored as metadata",
    }
    OUTPUT_JSON.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    write_changes(changes)
    after = summary_counts(reviewed_records)
    write_report(before, after, counters, changes)
    print(f"[OK] wrote {OUTPUT_JSON}")
    print(f"[OK] wrote {CHANGES_CSV}")
    print(f"[OK] wrote {REPORT_MD}")
    print(f"[INFO] suppliers {before['suppliers']} -> {after['suppliers']}; changes={len(changes)}")


if __name__ == "__main__":
    main()
