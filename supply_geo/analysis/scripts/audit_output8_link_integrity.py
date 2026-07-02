#!/usr/bin/env python3
"""Audit map-link continuity from upstream tiers to OEM."""

from __future__ import annotations

import csv
import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT_JSON = ROOT / "analysis" / "output8_GEO_normalized_final_corrected.json"
DEFAULT_OUT_CSV = ROOT / "analysis" / "output8_GEO_link_integrity_audit.csv"
DEFAULT_OUT_MD = ROOT / "analysis" / "output8_GEO_link_integrity_audit.md"

ROLES = [
    "tier4_raw_material",
    "tier3_first_transformation",
    "tier2_second_transformation",
    "tier1",
    "oem",
]

ROLE_SHORT = {
    "tier4_raw_material": "T4",
    "tier3_first_transformation": "T3",
    "tier2_second_transformation": "T2",
    "tier1": "T1",
    "oem": "OEM",
}


def has_coords(entry: dict[str, Any]) -> bool:
    return entry.get("lat") is not None and entry.get("lon") is not None


def role_entries(record: dict[str, Any], role: str, primary_only: bool) -> list[dict[str, Any]]:
    if role == "oem":
        entries = record.get("oem_sites") or []
    else:
        entries = [
            supplier
            for supplier in record.get("suppliers") or []
            if isinstance(supplier, dict) and supplier.get("role_hint") == role
        ]
    entries = [entry for entry in entries if isinstance(entry, dict) and has_coords(entry)]
    if primary_only:
        entries = [entry for entry in entries if entry.get("is_primary")]
    return entries


def audit_record(record: dict[str, Any], record_index: int, variant: str) -> dict[str, Any]:
    primary_only = variant == "primary"
    present = [role for role in ROLES if role_entries(record, role, primary_only)]
    missing = [role for role in ROLES if role not in present]
    adjacent_edges = 0
    bridge_labels: list[str] = []
    for left, right in zip(ROLES, ROLES[1:]):
        if left in present and right in present:
            adjacent_edges += 1
    present_indices = [ROLES.index(role) for role in present]
    for left_idx, right_idx in zip(present_indices, present_indices[1:]):
        if right_idx - left_idx <= 1:
            continue
        left = ROLES[left_idx]
        right = ROLES[right_idx]
        absent = ",".join(ROLE_SHORT[role] for role in ROLES[left_idx + 1 : right_idx])
        bridge_labels.append(f"{ROLE_SHORT[left]}->{ROLE_SHORT[right]} missing:{absent}")

    has_oem = "oem" in present
    has_t1 = "tier1" in present
    complete_roles = all(role in present for role in ROLES)
    needs_bridge = bool(bridge_labels)
    if not has_oem:
        status = "broken_no_oem"
    elif not present or present == ["oem"]:
        status = "broken_no_supply_tier"
    elif needs_bridge:
        status = "continuous_with_gap_bridge"
    else:
        status = "continuous_direct"

    return {
        "variant": variant,
        "record_index": record_index,
        "system": record.get("system", ""),
        "component": record.get("component", ""),
        "present_roles": ";".join(ROLE_SHORT[role] for role in present),
        "missing_roles": ";".join(ROLE_SHORT[role] for role in missing),
        "complete_roles": str(complete_roles),
        "has_t1": str(has_t1),
        "has_oem": str(has_oem),
        "direct_adjacent_edge_count": adjacent_edges,
        "bridge_needed": str(needs_bridge),
        "bridge_labels": ";".join(bridge_labels),
        "status": status,
    }


def write_csv(rows: list[dict[str, Any]], out_csv: Path) -> None:
    fields = [
        "variant",
        "record_index",
        "system",
        "component",
        "present_roles",
        "missing_roles",
        "complete_roles",
        "has_t1",
        "has_oem",
        "direct_adjacent_edge_count",
        "bridge_needed",
        "bridge_labels",
        "status",
    ]
    with out_csv.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def write_report(rows: list[dict[str, Any]], input_json: Path, out_csv: Path, out_md: Path) -> None:
    lines = [
        "# GEO link integrity audit",
        "",
        f"- Source JSON: `{input_json.as_posix()}`",
        f"- Detail CSV: `{out_csv.as_posix()}`",
        "",
        "## Summary",
        "",
        "The previous map drew only strict adjacent links: `T4->T3`, `T3->T2`, `T2->T1`, `T1->OEM`.",
        "Several supply records are valid but have an absent intermediate tier, so they looked visually disconnected from the constructor.",
        "The map generator now adds dotted grey bridge links for these cases, without creating fake suppliers.",
        "",
    ]
    for variant in ("primary", "all"):
        subset = [row for row in rows if row["variant"] == variant]
        status_counts = Counter(row["status"] for row in subset)
        missing_counts: Counter[str] = Counter()
        for row in subset:
            for role in str(row["missing_roles"]).split(";"):
                if role:
                    missing_counts[role] += 1
        lines += [
            f"## {variant.title()} Links",
            "",
            f"- Records audited: {len(subset)}",
            f"- Complete T4->T3->T2->T1->OEM records: {sum(row['complete_roles'] == 'True' for row in subset)}",
            f"- Records needing a dotted bridge: {sum(row['bridge_needed'] == 'True' for row in subset)}",
            f"- Records missing T1: {sum(row['has_t1'] == 'False' for row in subset)}",
            f"- Records missing OEM: {sum(row['has_oem'] == 'False' for row in subset)}",
            f"- Status counts: {', '.join(f'{key}={value}' for key, value in status_counts.most_common())}",
            f"- Missing-role counts: {', '.join(f'{key}={value}' for key, value in missing_counts.most_common())}",
            "",
        ]
    examples = [row for row in rows if row["variant"] == "primary" and row["bridge_needed"] == "True"][:20]
    lines += [
        "## Primary Examples Needing Bridge",
        "",
    ]
    for row in examples:
        lines.append(
            f"- R{row['record_index']} `{row['system']}` / `{row['component']}`: {row['bridge_labels']}"
        )
    lines += [
        "",
        "## Interpretation",
        "",
        "- `continuous_direct`: direct adjacent links already connect the visible chain.",
        "- `continuous_with_gap_bridge`: the chain reaches OEM only if the map bridges one or more absent intermediate tiers.",
        "- `broken_no_oem` and `broken_no_supply_tier` would be hard errors; none should remain for the final JSON.",
        "",
    ]
    out_md.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT_JSON)
    parser.add_argument("--out-csv", type=Path, default=DEFAULT_OUT_CSV)
    parser.add_argument("--out-md", type=Path, default=DEFAULT_OUT_MD)
    args = parser.parse_args()

    source = json.loads(args.input.read_text(encoding="utf-8"))
    records = source.get("records") or source
    rows: list[dict[str, Any]] = []
    for variant in ("primary", "all"):
        for index, record in enumerate(records, start=1):
            if isinstance(record, dict) and record.get("simulation_supply_usable") is False:
                continue
            rows.append(audit_record(record, index, variant))
    write_csv(rows, args.out_csv)
    write_report(rows, args.input, args.out_csv, args.out_md)
    print(f"[OK] wrote {args.out_csv}")
    print(f"[OK] wrote {args.out_md}")


if __name__ == "__main__":
    main()
