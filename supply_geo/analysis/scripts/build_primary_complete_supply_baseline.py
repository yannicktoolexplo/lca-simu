#!/usr/bin/env python3
"""Build a complete, plausible primary supply baseline for simulation.

This creates explicit primary nodes for accepted internal processes and for
documented assumptions. It does not overwrite the factual/refined JSON.
"""

from __future__ import annotations

import copy
import csv
import json
from pathlib import Path
from typing import Any


BASE_DIR = Path(__file__).resolve().parent
INPUT_JSON = BASE_DIR / "output8_GEO_normalized_final_site_refined.json"
OUTPUT_JSON = BASE_DIR / "output8_GEO_normalized_final_primary_complete.json"
CHANGELOG_CSV = BASE_DIR / "output8_GEO_primary_complete_assumptions.csv"
REPORT_MD = BASE_DIR / "output8_GEO_primary_complete_baseline.md"

ROLES = [
    "tier4_raw_material",
    "tier3_first_transformation",
    "tier2_second_transformation",
    "tier1",
]


def norm(value: Any) -> str:
    return str(value or "").strip().lower()


def has_coords(entry: dict[str, Any]) -> bool:
    return entry.get("lat") not in (None, "") and entry.get("lon") not in (None, "")


def has_any(text: str, needles: list[str]) -> bool:
    t = norm(text)
    return any(needle in t for needle in needles)


def material_text(record: dict[str, Any]) -> str:
    return " | ".join(
        [
            str(record.get("system") or ""),
            str(record.get("component") or ""),
            " ".join(str(x) for x in record.get("raw_materials") or []),
        ]
    )


def material_family(record: dict[str, Any]) -> str:
    text = material_text(record)
    if has_any(text, ["a5086", "a2017", "a2024", "a6060", "aluminium", "aluminum", " alu"]):
        return "aluminium"
    if has_any(text, ["alliage cu", "cuivre", "copper"]):
        return "copper"
    if has_any(text, ["acier", "steel", "inox", "35nc6", "30ncd6", "15cdv6", "4140", "z10cnt18"]):
        return "steel"
    if has_any(text, ["display", "powerbox", "ife", "ecu", "remote", "clavier", "lightning", "electron"]):
        return "electronics_cots"
    if has_any(text, ["silicone", "caoutchouc", "rubber", "polychloroprene"]):
        return "rubber_silicone"
    if has_any(text, ["cuir", "leather", "tissu", "velours", "velcro", "textile"]):
        return "textile_leather"
    if has_any(text, ["composite", "carbone", "carbon", "titane", "titanium"]):
        return "composite_titanium"
    if has_any(text, ["ertalon", "lexan", "nylon", "polyamide", "plastique", "plastic", "kydex", "nida"]):
        return "polymer_plastic"
    return "general"


def all_entries(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for record in records:
        for container in ["suppliers", "oem_sites"]:
            for entry in record.get(container) or []:
                if isinstance(entry, dict) and has_coords(entry):
                    out.append(entry)
    return out


def first_template(records: list[dict[str, Any]], name: str) -> dict[str, Any] | None:
    for entry in all_entries(records):
        if entry.get("name") == name and has_coords(entry):
            return entry
    return None


def role_entries(record: dict[str, Any], role: str, *, primary_only: bool = False, require_coords: bool = False) -> list[dict[str, Any]]:
    entries = [
        entry
        for entry in record.get("suppliers") or []
        if isinstance(entry, dict) and entry.get("role_hint") == role
    ]
    if primary_only:
        entries = [entry for entry in entries if entry.get("is_primary")]
    if require_coords:
        entries = [entry for entry in entries if has_coords(entry)]
    return entries


def primary_t1(record: dict[str, Any]) -> dict[str, Any] | None:
    entries = role_entries(record, "tier1", primary_only=True, require_coords=True)
    return entries[0] if entries else None


def first_present_downstream(record: dict[str, Any], role: str) -> dict[str, Any] | None:
    order = ["tier4_raw_material", "tier3_first_transformation", "tier2_second_transformation", "tier1"]
    start = order.index(role) + 1
    for next_role in order[start:]:
        entries = role_entries(record, next_role, primary_only=True, require_coords=True)
        if entries:
            return entries[0]
    t1 = primary_t1(record)
    return t1


def demote_primary(record: dict[str, Any], role: str, reason: str, *, only_unpositioned: bool = False) -> list[str]:
    changed = []
    for entry in record.get("suppliers") or []:
        if not isinstance(entry, dict) or entry.get("role_hint") != role or not entry.get("is_primary"):
            continue
        if only_unpositioned and has_coords(entry):
            continue
        entry["is_primary"] = False
        entry["supplier_status"] = "alternate_demoted_by_primary_complete_baseline"
        entry["primary_completion_note"] = reason
        changed.append(str(entry.get("name") or ""))
    return changed


def make_from_template(
    template: dict[str, Any],
    role: str,
    *,
    name: str | None = None,
    status: str,
    confidence: str,
    note: str,
    virtual: bool = False,
) -> dict[str, Any]:
    entry = copy.deepcopy(template)
    entry["name"] = name or entry.get("name")
    entry["role_hint"] = role
    entry["is_primary"] = True
    entry["supplier_status"] = status
    entry["allocation_share_pct"] = 100.0
    entry["baseline_completion_assumption"] = True
    entry["baseline_completion_confidence"] = confidence
    entry["baseline_completion_note"] = note
    entry["geocode_provider"] = entry.get("geocode_provider") or "manual:primary_complete_baseline"
    entry["supplier_id"] = f"{norm(entry.get('name')).replace(' ', '_')}__{role}"
    entry["site_id"] = f"{entry['supplier_id']}@{entry.get('lat')},{entry.get('lon')}"
    if virtual:
        entry["simulation_node_type"] = "virtual_process_or_market_basket"
        entry["geocode_status"] = "virtual_node_at_downstream_site"
    return entry


def add_entry(record: dict[str, Any], entry: dict[str, Any]) -> None:
    record.setdefault("suppliers", []).append(entry)


def add_primary_from_template(
    records: list[dict[str, Any]],
    record: dict[str, Any],
    role: str,
    supplier_name: str,
    *,
    status: str,
    confidence: str,
    note: str,
    display_name: str | None = None,
) -> dict[str, Any] | None:
    template = first_template(records, supplier_name)
    if not template:
        return None
    demote_primary(record, role, f"Replaced by assumed primary {display_name or supplier_name}.")
    entry = make_from_template(
        template,
        role,
        name=display_name or supplier_name,
        status=status,
        confidence=confidence,
        note=note,
    )
    add_entry(record, entry)
    return entry


def add_virtual_at(
    record: dict[str, Any],
    role: str,
    base: dict[str, Any],
    name: str,
    *,
    status: str,
    confidence: str,
    note: str,
) -> dict[str, Any]:
    demote_primary(record, role, f"Replaced by virtual assumed node {name}.", only_unpositioned=True)
    entry = make_from_template(
        base,
        role,
        name=name,
        status=status,
        confidence=confidence,
        note=note,
        virtual=True,
    )
    add_entry(record, entry)
    return entry


def missing_primary_mappable(record: dict[str, Any], role: str) -> bool:
    return not role_entries(record, role, primary_only=True, require_coords=True)


def change(changes: list[dict[str, Any]], record_index: int, role: str, entry: dict[str, Any], action: str) -> None:
    changes.append(
        {
            "record_index": record_index,
            "tier": role,
            "supplier_or_node": entry.get("name"),
            "status": entry.get("supplier_status"),
            "confidence": entry.get("baseline_completion_confidence"),
            "action": action,
            "lat": entry.get("lat"),
            "lon": entry.get("lon"),
            "note": entry.get("baseline_completion_note"),
        }
    )


def complete_record(records: list[dict[str, Any]], record: dict[str, Any], record_index: int, changes: list[dict[str, Any]]) -> None:
    family = material_family(record)
    component = norm(record.get("component"))

    # 1) Material certificate choices: complete the main metal path with plausible mill/processor.
    if missing_primary_mappable(record, "tier4_raw_material") and family == "steel":
        entry = add_primary_from_template(
            records,
            record,
            "tier4_raw_material",
            "Saarstahl",
            status="baseline_primary_assumed_material_certificate",
            confidence="medium",
            note="Plausible steel mill for complete baseline; validate by EN/AMS material certificate before factual use.",
        )
        if entry:
            change(changes, record_index, "T4", entry, "add_assumed_steel_mill")
    if missing_primary_mappable(record, "tier3_first_transformation") and family == "steel":
        entry = add_primary_from_template(
            records,
            record,
            "tier3_first_transformation",
            "Aubert & Duval",
            status="baseline_primary_assumed_material_processor",
            confidence="medium",
            note="Plausible aerospace steel processor/forge for complete baseline; validate routing/certificate.",
        )
        if entry:
            change(changes, record_index, "T3", entry, "add_assumed_steel_processor")
    if missing_primary_mappable(record, "tier4_raw_material") and family == "copper":
        entry = add_primary_from_template(
            records,
            record,
            "tier4_raw_material",
            "Aurubis",
            status="baseline_primary_assumed_material_source",
            confidence="medium",
            note="Aurubis is already the primary copper transformation node; reused as copper source assumption for baseline completeness.",
            display_name="Aurubis - copper source assumption",
        )
        if entry:
            change(changes, record_index, "T4", entry, "add_assumed_copper_source")

    # 2) T2 fabrication gaps are usually processes under the primary T1.
    if missing_primary_mappable(record, "tier2_second_transformation") and family in {"aluminium", "steel", "copper"}:
        owner = primary_t1(record)
        if owner:
            entry = add_virtual_at(
                record,
                "tier2_second_transformation",
                owner,
                f"{owner.get('name')} - internal machining/forming process",
                status="baseline_primary_assumed_internalized_process",
                confidence="medium_high",
                note="Explicit virtual T2 so the primary chain is complete; process assumed internal to T1 pending routing validation.",
            )
            change(changes, record_index, "T2", entry, "add_virtual_internal_t2")

    # 3) Electronics/COTS: do not pretend true sub-tiers; add non-switchable market-basket nodes.
    if family == "electronics_cots":
        if missing_primary_mappable(record, "tier1"):
            entry = add_primary_from_template(
                records,
                record,
                "tier1",
                "Thales",
                status="baseline_primary_assumed_program_supplier",
                confidence="medium_low",
                note="Plausible cabin/IFE electronics T1 for complete baseline; validate PN/program supplier before factual use.",
            )
            if entry:
                change(changes, record_index, "T1", entry, "add_assumed_electronics_t1")
        if missing_primary_mappable(record, "tier2_second_transformation"):
            base = primary_t1(record) or first_present_downstream(record, "tier2_second_transformation")
            if base:
                entry = add_virtual_at(
                    record,
                    "tier2_second_transformation",
                    base,
                    f"{base.get('name')} - electronics routing/EMS package",
                    status="baseline_primary_assumed_electronics_process",
                    confidence="low",
                    note="Virtual COTS/EMS node for continuity; replace with BOM/EMS/ODM routing when known.",
                )
                change(changes, record_index, "T2", entry, "add_virtual_electronics_t2")
        if missing_primary_mappable(record, "tier3_first_transformation"):
            base = first_present_downstream(record, "tier3_first_transformation")
            if base:
                entry = add_virtual_at(
                    record,
                    "tier3_first_transformation",
                    base,
                    "COTS electronics PCB/subassembly package",
                    status="baseline_primary_assumed_non_switchable_cots",
                    confidence="low",
                    note="Non-switchable placeholder; do not use for supplier-switch tests without BOM/AVL.",
                )
                change(changes, record_index, "T3", entry, "add_virtual_cots_t3")
        if missing_primary_mappable(record, "tier4_raw_material"):
            base = first_present_downstream(record, "tier4_raw_material")
            if base:
                entry = add_virtual_at(
                    record,
                    "tier4_raw_material",
                    base,
                    "COTS electronics component market basket",
                    status="baseline_primary_assumed_non_switchable_cots",
                    confidence="low",
                    note="Non-switchable placeholder for semiconductor/component upstream; requires BOM/PN for factual model.",
                )
                change(changes, record_index, "T4", entry, "add_virtual_cots_t4")

    # 4) Polymer/plastic direct supplier gaps.
    if missing_primary_mappable(record, "tier1") and family in {"polymer_plastic", "composite_titanium"}:
        supplier = "SUMPAR" if "bumper" in component else "JAMCO Aircraft Interiors - Niigata"
        entry = add_primary_from_template(
            records,
            record,
            "tier1",
            supplier,
            status="baseline_primary_assumed_program_supplier",
            confidence="medium_low",
            note="Plausible direct supplier/integrator for complete baseline; validate drawing, PN and programme allocation.",
        )
        if entry:
            change(changes, record_index, "T1", entry, "add_assumed_polymer_or_composite_t1")
    if missing_primary_mappable(record, "tier3_first_transformation") and family == "polymer_plastic":
        source = "SABIC" if "lexan" in component else "Toray Industries"
        display = "SABIC LEXAN FST sheet production" if source == "SABIC" else None
        entry = add_primary_from_template(
            records,
            record,
            "tier3_first_transformation",
            source,
            status="baseline_primary_assumed_material_processor",
            confidence="medium_low",
            note="Plausible polymer sheet/intermediate processor for baseline completeness; validate grade/routing.",
            display_name=display,
        )
        if entry:
            change(changes, record_index, "T3", entry, "add_assumed_polymer_t3")
    if missing_primary_mappable(record, "tier2_second_transformation") and family == "polymer_plastic":
        owner = primary_t1(record) or first_present_downstream(record, "tier2_second_transformation")
        if owner:
            entry = add_virtual_at(
                record,
                "tier2_second_transformation",
                owner,
                f"{owner.get('name')} - thermoforming/finishing process",
                status="baseline_primary_assumed_internalized_process",
                confidence="medium",
                note="Virtual T2 for thermoforming/finishing; validate actual converter/routing.",
            )
            change(changes, record_index, "T2", entry, "add_virtual_polymer_t2")

    # 5) Textile/leather/silicone upstream gaps.
    if missing_primary_mappable(record, "tier4_raw_material") and family == "rubber_silicone":
        supplier = "Shin-Etsu Silicones" if "silicone" in component else "BASF"
        entry = add_primary_from_template(
            records,
            record,
            "tier4_raw_material",
            supplier,
            status="baseline_primary_assumed_material_source",
            confidence="medium_low",
            note="Plausible chemistry source for complete baseline; validate SDS/grade before factual use.",
        )
        if entry:
            change(changes, record_index, "T4", entry, "add_assumed_rubber_silicone_t4")
    if missing_primary_mappable(record, "tier4_raw_material") and family == "textile_leather":
        if "cuir" in component or "leather" in component:
            supplier = "Gruppo Mastrotto"
            display = "Gruppo Mastrotto - hide/raw leather source assumption"
        else:
            supplier = "DuPont de Nemours"
            display = "DuPont de Nemours - fiber/polymer source assumption"
        entry = add_primary_from_template(
            records,
            record,
            "tier4_raw_material",
            supplier,
            status="baseline_primary_assumed_material_source",
            confidence="medium_low",
            note="Plausible upstream fiber/hide source for baseline completeness; validate actual grade and origin.",
            display_name=display,
        )
        if entry:
            change(changes, record_index, "T4", entry, "add_assumed_textile_leather_t4")
    if missing_primary_mappable(record, "tier3_first_transformation") and family == "textile_leather":
        supplier = "Yamazaki Velvet Co." if "velours" in component else "Huddersfield Textiles"
        entry = add_primary_from_template(
            records,
            record,
            "tier3_first_transformation",
            supplier,
            status="baseline_primary_assumed_textile_processor",
            confidence="medium_low",
            note="Replaces unpositioned/generic textile node for complete baseline; validate fabric mill/order evidence.",
        )
        if entry:
            change(changes, record_index, "T3", entry, "replace_unpositioned_textile_t3")
    if missing_primary_mappable(record, "tier1") and family == "textile_leather":
        entry = add_primary_from_template(
            records,
            record,
            "tier1",
            "JAMCO Aircraft Interiors - Niigata",
            status="baseline_primary_assumed_program_supplier",
            confidence="medium_low",
            note="Seat-level textile/foam aggregate line completed with existing seat integrator; validate programme supplier.",
        )
        if entry:
            change(changes, record_index, "T1", entry, "add_assumed_textile_t1")

    # 6) Composite/titanium upstream gap.
    if missing_primary_mappable(record, "tier4_raw_material") and family == "composite_titanium":
        supplier = "Toray Industries"
        entry = add_primary_from_template(
            records,
            record,
            "tier4_raw_material",
            supplier,
            status="baseline_primary_assumed_material_source",
            confidence="medium_low",
            note="Carbon-fiber upstream source assumption using Toray footprint; titanium source still requires certificate.",
            display_name="Toray Industries - carbon fiber upstream source assumption",
        )
        if entry:
            change(changes, record_index, "T4", entry, "add_assumed_composite_t4")

    # 7) Remaining primary T3 unpositioned for rubber/electronics: add virtual processor at downstream site.
    if missing_primary_mappable(record, "tier3_first_transformation") and family == "rubber_silicone":
        base = role_entries(record, "tier2_second_transformation", primary_only=True, require_coords=True)
        if base:
            entry = add_virtual_at(
                record,
                "tier3_first_transformation",
                base[0],
                f"{base[0].get('name')} - material intermediate sourcing",
                status="baseline_primary_assumed_material_processor",
                confidence="low",
                note="Virtual T3 to replace unpositioned generic node; validate actual compounder/stockist.",
            )
            change(changes, record_index, "T3", entry, "add_virtual_rubber_t3")


def audit_primary_complete(records: list[dict[str, Any]]) -> tuple[int, list[str]]:
    issues = []
    checked = 0
    for idx, record in enumerate(records, 1):
        if not isinstance(record, dict) or record.get("simulation_supply_usable") is False:
            continue
        checked += 1
        for role in ROLES:
            if not role_entries(record, role, primary_only=True, require_coords=True):
                issues.append(f"R{idx}:{role}:{record.get('component')}")
        if not record.get("oem_sites"):
            issues.append(f"R{idx}:oem:{record.get('component')}")
    return checked, issues


def main() -> None:
    data = json.loads(INPUT_JSON.read_text(encoding="utf-8"))
    records = data["records"] if isinstance(data, dict) and "records" in data else data
    changes: list[dict[str, Any]] = []

    for idx, record in enumerate(records, 1):
        if not isinstance(record, dict) or record.get("simulation_supply_usable") is False:
            continue
        complete_record(records, record, record.get("record_index") or record.get("index") or idx, changes)

    checked, issues = audit_primary_complete(records)
    meta = data.setdefault("_meta", {}) if isinstance(data, dict) else {}
    meta["primary_complete_baseline"] = {
        "input_json": str(INPUT_JSON),
        "output_json": str(OUTPUT_JSON),
        "active_records_checked": checked,
        "assumption_count": len(changes),
        "remaining_primary_role_issues": issues,
        "warning": "This is a simulation baseline: assumed/virtual nodes are plausible routing hypotheses, not verified contractual suppliers.",
    }

    OUTPUT_JSON.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    with CHANGELOG_CSV.open("w", encoding="utf-8-sig", newline="") as handle:
        fieldnames = ["record_index", "tier", "supplier_or_node", "status", "confidence", "action", "lat", "lon", "note"]
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(changes)

    with REPORT_MD.open("w", encoding="utf-8") as handle:
        handle.write("# Primary Complete Supply Baseline\n\n")
        handle.write(f"- Input JSON: `{INPUT_JSON}`\n")
        handle.write(f"- Output JSON: `{OUTPUT_JSON}`\n")
        handle.write(f"- Change log: `{CHANGELOG_CSV}`\n")
        handle.write(f"- Active records checked: **{checked}**\n")
        handle.write(f"- Assumed/virtual primary nodes added: **{len(changes)}**\n")
        handle.write(f"- Remaining primary role issues: **{len(issues)}**\n\n")
        handle.write("## Rule\n\n")
        handle.write("This file makes the main chain complete for simulation. Assumed suppliers and virtual process nodes are marked in the JSON and must not be treated as verified procurement truth.\n\n")
        handle.write("## Remaining Issues\n\n")
        if issues:
            for issue in issues[:100]:
                handle.write(f"- {issue}\n")
        else:
            handle.write("None: every active primary record has mappable T4, T3, T2, T1 and OEM nodes.\n")

    print(f"[OK] wrote {OUTPUT_JSON}")
    print(f"[OK] wrote {CHANGELOG_CSV} ({len(changes)} assumptions)")
    print(f"[OK] wrote {REPORT_MD}")
    if issues:
        print(f"[WARN] remaining issues: {len(issues)}")
    else:
        print("[OK] primary chain complete for all active records")


if __name__ == "__main__":
    main()
