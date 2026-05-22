#!/usr/bin/env python3
"""Build a business validation matrix for supply-chain simulation assumptions.

The structural graph can be complete while procurement assumptions are still not
ready for stress tests. This script separates topology from business evidence:
allocation, qualification, lead time, material evidence, and lane plausibility.
"""

from __future__ import annotations

import csv
import datetime as dt
import math
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


BASE_DIR = Path(__file__).resolve().parent
PATHS_CSV = BASE_DIR / "output8_GEO_simulation_ready_researched_supply_path_network_full_paths.csv"
LANES_CSV = BASE_DIR / "output8_GEO_simulation_ready_researched_supply_path_network_transport_lanes.csv"
SUPPLIER_OPTIONS_CSV = BASE_DIR / "output8_GEO_secondary_switch_supplier_options.csv"

OUT_PATHS = BASE_DIR / "output8_GEO_business_validation_path_audit.csv"
OUT_SUPPLIERS = BASE_DIR / "output8_GEO_business_validation_supplier_matrix.csv"
OUT_LANES = BASE_DIR / "output8_GEO_business_validation_critical_lanes.csv"
OUT_COMPONENTS = BASE_DIR / "output8_GEO_business_validation_component_summary.csv"
OUT_ACTIONS = BASE_DIR / "output8_GEO_business_validation_action_backlog.csv"
OUT_MD = BASE_DIR / "output8_GEO_business_validation_report.md"


METAL_FAMILIES = {"aluminium", "steel", "copper", "titanium_carbon"}
SOFT_GOODS = {"textile_leather", "rubber_silicone"}
POLYMER_FAMILIES = {"polymer_plastic", "adhesive_composite"}


def clean(value: Any) -> str:
    return str(value or "").strip()


def safe_float(value: Any) -> float:
    try:
        if value in (None, ""):
            return 0.0
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def safe_int(value: Any) -> int:
    try:
        if value in (None, ""):
            return 0
        return int(float(value))
    except (TypeError, ValueError):
        return 0


def issue_set(value: Any) -> set[str]:
    return {part for part in clean(value).split(";") if part}


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fieldnames = list(dict.fromkeys(key for row in rows for key in row.keys()))
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def material_evidence_gate(family: str, codes: set[str], raw_materials_status: str) -> tuple[str, str]:
    if family in METAL_FAMILIES:
        if "material_certificate_required" in codes:
            return (
                "material_certificate_required",
                "Check grade, mill/site, heat/batch certificate and aerospace material standard before activation.",
            )
        return (
            "material_certificate_check",
            "Keep certificate/grade check as release gate; no topology blocker detected.",
        )
    if family == "electronics_cots":
        return (
            "bom_pn_avl_required",
            "Validate part number, BOM, AVL, EMS/ODM and obsolescence status; do not infer upstream suppliers.",
        )
    if family in SOFT_GOODS:
        if raw_materials_status != "provided" or "raw_material_source_missing" in codes:
            return (
                "material_source_and_fst_required",
                "Validate exact material datasheet, fire/smoke/tox evidence, color/trim approval and source.",
            )
        return (
            "soft_goods_fst_required",
            "Validate fire/smoke/tox evidence, color/trim approval and process compatibility.",
        )
    if family in POLYMER_FAMILIES:
        return (
            "grade_and_process_datasheet_required",
            "Validate grade, datasheet, process route, drawing compatibility and FST if cabin exposed.",
        )
    return (
        "material_definition_review",
        "Validate exact material definition and industrial role before scenario activation.",
    )


def qualification_gate(family: str, path_type: str) -> tuple[str, str]:
    if path_type == "primary":
        prefix = "baseline"
    else:
        prefix = "switch_candidate"
    if family == "electronics_cots":
        return (
            f"{prefix}_qualification_bom_avl",
            "Qualification depends on PN/program supplier/AVL and cannot be validated from generic supplier names.",
        )
    if family in SOFT_GOODS:
        return (
            f"{prefix}_qualification_cabin_trim",
            "Needs cabin trim qualification: material spec, finish/color, FST, sewing/upholstery process if applicable.",
        )
    if family in METAL_FAMILIES:
        return (
            f"{prefix}_qualification_material_and_process",
            "Needs qualified grade/source and approved process route; internal T2 must remain coupled with its T1.",
        )
    if family in POLYMER_FAMILIES:
        return (
            f"{prefix}_qualification_polymer_process",
            "Needs exact grade, process route, tooling/forming route and cabin material approval when relevant.",
        )
    return (
        f"{prefix}_qualification_role_review",
        "Needs role and process validation before activation.",
    )


def lead_time_gate(family: str, role_context: str, is_secondary: bool, longhaul: bool) -> tuple[str, str]:
    if family in {"aluminium", "steel", "copper"}:
        band = "8-24w material/procurement; 6-18w machining/assembly; longer if new qualification"
    elif family in SOFT_GOODS:
        band = "8-20w material/trim; 12-40w if new FST/color/process qualification"
    elif family in POLYMER_FAMILIES:
        band = "10-26w grade/process; 20-52w if tooling or cabin qualification changes"
    elif family == "electronics_cots":
        band = "12-40w PN/AVL/COTS availability; higher if redesign or obsolescence"
    elif family == "titanium_carbon":
        band = "16-52w material/composite route; qualification can dominate"
    else:
        band = "8-24w planning assumption pending supplier confirmation"

    needs = is_secondary or longhaul or "assumption" in role_context
    status = "lead_time_required" if needs else "lead_time_check"
    return status, band


def allocation_gate(row: dict[str, str], codes: set[str]) -> tuple[str, str]:
    if row.get("path_type") == "secondary_candidate":
        return (
            "allocation_required",
            "Inactive candidate: validate awarded source, allocation share, capacity, MOQ and contractual availability.",
        )
    if "baseline_node_is_assumption" in codes or clean(row.get("contains_assumption")).lower() == "true":
        return (
            "baseline_allocation_assumption",
            "Baseline topology is usable, but source/allocation should be confirmed by purchasing or supplier docs.",
        )
    return ("baseline_allocated_or_not_flagged", "No allocation issue detected in current model.")


def path_validation_status(row: dict[str, str], codes: set[str]) -> str:
    if "internal_process_t1_mismatch" in codes:
        return "secondary_candidate_pair_switch_required"
    if row.get("path_type") == "primary" and not codes:
        return "simulation_ready_topology_business_check_light"
    if row.get("path_type") == "primary":
        return "baseline_usable_business_validation_needed"
    return "secondary_candidate_business_validation_needed"


def transport_lane_plausibility(distance_km: float, modes: set[str]) -> tuple[str, str, str]:
    if distance_km <= 0.1:
        if "internal" in modes:
            return "ok_internal", "internal", "Same-site/internal process."
        return "review_same_site_mode", "internal", "Distance is near zero; use internal movement or confirm local transfer."
    if distance_km <= 800:
        if "truck" in modes:
            return "ok_regional_truck", "truck", "Regional lane; truck is plausible."
        return "review_regional_mode", "truck", "Regional lane normally needs truck or local dedicated carrier."
    if distance_km <= 2500:
        if modes & {"truck", "rail", "ship"}:
            return "ok_long_regional", "truck|rail", "Long regional lane; truck/rail combination is plausible."
        return "review_long_regional_mode", "truck|rail", "Long regional lane needs truck/rail, or ship if islands/coastal."
    if "ship" in modes:
        return "ok_intercontinental_ocean", "ship|truck", "Long-distance lane; ocean + truck is plausible for baseline cost/carbon."
    if "air" in modes:
        return "expedite_only_review", "ship|truck baseline, air expedite", "Air is plausible only for urgent/critical expedites."
    return "review_intercontinental_mode", "ship|truck", "Intercontinental lane should normally include ocean shipping plus truck drayage."


def lane_criticality(row: dict[str, str]) -> tuple[float, str]:
    mass = safe_float(row.get("mass_kg"))
    distance = safe_float(row.get("distance_km"))
    uses = max(1, safe_int(row.get("path_use_count")))
    kg_km = mass * distance * uses
    if kg_km >= 500_000 or distance >= 10_000 or uses >= 100:
        level = "critical"
    elif kg_km >= 50_000 or distance >= 3_500 or uses >= 25:
        level = "high"
    elif kg_km >= 5_000 or distance >= 800:
        level = "medium"
    else:
        level = "low"
    return kg_km, level


def build_path_rows(paths: list[dict[str, str]]) -> tuple[list[dict[str, Any]], dict[str, Counter[str]]]:
    rows: list[dict[str, Any]] = []
    component_counters: dict[str, Counter[str]] = defaultdict(Counter)
    for row in paths:
        codes = issue_set(row.get("issue_codes"))
        family = clean(row.get("family"))
        path_type = clean(row.get("path_type"))
        distances = [
            safe_float(row.get("t4_t3_km")),
            safe_float(row.get("t3_t2_km")),
            safe_float(row.get("t2_t1_km")),
            safe_float(row.get("t1_oem_km")),
        ]
        longhaul = any(d >= 3500 for d in distances)
        is_secondary = path_type == "secondary_candidate"
        allocation_status, allocation_action = allocation_gate(row, codes)
        qualification_status, qualification_action = qualification_gate(family, path_type)
        material_status, material_action = material_evidence_gate(
            family, codes, clean(row.get("raw_materials_status"))
        )
        role_context = " ".join(
            [
                clean(row.get("t4_status")),
                clean(row.get("t3_status")),
                clean(row.get("t2_status")),
                clean(row.get("t1_status")),
            ]
        ).lower()
        lead_time_status, lead_time_assumption = lead_time_gate(
            family, role_context, is_secondary=is_secondary, longhaul=longhaul
        )
        status = path_validation_status(row, codes)
        validation_items = [
            allocation_status,
            qualification_status,
            material_status,
            lead_time_status,
        ]
        if "internal_process_t1_mismatch" in codes:
            validation_items.append("internal_process_t1_pairing_required")
        if any("fallback" in clean(row.get(field)).lower() for field in ["t4_status", "t3_status", "t2_status", "t1_status"]):
            validation_items.append("site_validation_required")
        if longhaul:
            validation_items.append("longhaul_transport_lane_check")
        record_key = clean(row.get("record_index"))
        component_counters[record_key]["paths"] += 1
        component_counters[record_key][status] += 1
        for item in validation_items:
            component_counters[record_key][item] += 1
        rows.append(
            {
                "record_index": row.get("record_index"),
                "system": row.get("system"),
                "component": row.get("component"),
                "family": family,
                "mass_kg": row.get("mass_kg"),
                "lca_use_class": row.get("lca_use_class"),
                "lca_confidence": row.get("lca_confidence"),
                "path_id": row.get("path_id"),
                "path_type": path_type,
                "business_validation_status": status,
                "allocation_status": allocation_status,
                "qualification_status": qualification_status,
                "material_evidence_status": material_status,
                "lead_time_status": lead_time_status,
                "lead_time_assumption_band": lead_time_assumption,
                "longhaul_lane_present": "yes" if longhaul else "no",
                "validation_items": ";".join(validation_items),
                "allocation_action": allocation_action,
                "qualification_action": qualification_action,
                "material_action": material_action,
                "t4": row.get("t4"),
                "t3": row.get("t3"),
                "t2": row.get("t2"),
                "t1": row.get("t1"),
                "oem": row.get("oem"),
                "issue_codes": row.get("issue_codes"),
            }
        )
    return rows, component_counters


def build_component_rows(paths: list[dict[str, str]], counters: dict[str, Counter[str]]) -> list[dict[str, Any]]:
    by_record: dict[str, dict[str, str]] = {}
    for row in paths:
        by_record.setdefault(clean(row.get("record_index")), row)
    out: list[dict[str, Any]] = []
    for record_key, counts in sorted(counters.items(), key=lambda kv: safe_int(kv[0])):
        sample = by_record.get(record_key, {})
        top = counts.most_common(12)
        if counts.get("secondary_candidate_business_validation_needed"):
            next_gate = "curate_secondary_switches"
        elif counts.get("baseline_usable_business_validation_needed"):
            next_gate = "confirm_baseline_assumptions"
        else:
            next_gate = "ready_for_light_business_check"
        out.append(
            {
                "record_index": record_key,
                "system": sample.get("system"),
                "component": sample.get("component"),
                "family": sample.get("family"),
                "mass_kg": sample.get("mass_kg"),
                "lca_use_class": sample.get("lca_use_class"),
                "path_count": counts.get("paths", 0),
                "primary_ready_or_usable": counts.get("simulation_ready_topology_business_check_light", 0)
                + counts.get("baseline_usable_business_validation_needed", 0),
                "secondary_candidates": counts.get("secondary_candidate_business_validation_needed", 0),
                "allocation_required_occurrences": counts.get("allocation_required", 0),
                "material_certificate_occurrences": counts.get("material_certificate_required", 0),
                "material_source_occurrences": counts.get("material_source_and_fst_required", 0)
                + counts.get("material_definition_review", 0),
                "lead_time_required_occurrences": counts.get("lead_time_required", 0),
                "longhaul_transport_occurrences": counts.get("longhaul_transport_lane_check", 0),
                "next_business_gate": next_gate,
                "top_validation_items": ";".join(f"{k}={v}" for k, v in top if k != "paths"),
            }
        )
    return out


def build_lane_rows(lanes: list[dict[str, str]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for row in lanes:
        distance = safe_float(row.get("distance_km"))
        modes = issue_set(clean(row.get("modes")).replace("|", ";"))
        plausibility, recommended_mode, action = transport_lane_plausibility(distance, modes)
        kg_km, criticality = lane_criticality(row)
        if criticality == "low" and plausibility.startswith("ok_"):
            continue
        out.append(
            {
                "record_index": row.get("record_index"),
                "system": row.get("system"),
                "component": row.get("component"),
                "family": row.get("family"),
                "mass_kg": row.get("mass_kg"),
                "lca_use_class": row.get("lca_use_class"),
                "edge": row.get("edge"),
                "from_name": row.get("from_name"),
                "to_name": row.get("to_name"),
                "distance_km": round(distance, 1),
                "modes": row.get("modes"),
                "recommended_baseline_mode": recommended_mode,
                "transport_plausibility": plausibility,
                "transport_validation_action": action,
                "path_use_count": row.get("path_use_count"),
                "kg_km_proxy": round(kg_km, 1),
                "criticality": criticality,
            }
        )
    out.sort(key=lambda r: ({"critical": 0, "high": 1, "medium": 2, "low": 3}.get(r["criticality"], 9), -safe_float(r["kg_km_proxy"])))
    return out


def supplier_activation_gate(family: str, role: str) -> str:
    if family in {"aluminium", "steel", "copper"}:
        return "same_family_only + grade/certificate/site/allocation + keep internal T2 paired with T1"
    if family == "electronics_cots":
        return "PN/program/AVL only; no upstream switch without BOM and approved EMS/ODM"
    if family in SOFT_GOODS:
        return "exact material + FST + trim/color approval + process qualification"
    if family in POLYMER_FAMILIES:
        return "exact grade + process route + drawing/tooling/FST validation"
    if family == "titanium_carbon":
        return "split titanium and carbon/composite; validate material route and integrator"
    return "validate role, material and site before activation"


def build_supplier_rows(suppliers: list[dict[str, str]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for row in suppliers:
        family = clean(row.get("family"))
        role = clean(row.get("role"))
        path_count = safe_int(row.get("path_count"))
        issue_codes = clean(row.get("issue_codes"))
        risk = "medium"
        if any(code in issue_codes for code in ["material_certificate_required", "raw_material_source_missing"]):
            risk = "high"
        if path_count >= 500 or family in {"electronics_cots", "titanium_carbon"}:
            risk = "high"
        if safe_int(row.get("blocked")):
            risk = "blocker"
        _, lead_time_band = lead_time_gate(family, issue_codes.lower(), True, False)
        out.append(
            {
                "role": role,
                "supplier": row.get("supplier"),
                "family": family,
                "path_count": row.get("path_count"),
                "best_verdict": row.get("best_verdict"),
                "validation_risk": risk,
                "activation_gate": supplier_activation_gate(family, role),
                "allocation_validation": "required_for_switch",
                "qualification_validation": qualification_gate(family, "secondary_candidate")[1],
                "lead_time_assumption_band": lead_time_band,
                "issue_codes": issue_codes,
                "status_examples": row.get("status_examples"),
                "components": row.get("components"),
            }
        )
    out.sort(key=lambda r: ({"blocker": 0, "high": 1, "medium": 2, "low": 3}.get(r["validation_risk"], 9), -safe_int(r["path_count"])))
    return out


def build_action_rows(
    path_rows: list[dict[str, Any]], lane_rows: list[dict[str, Any]], supplier_rows: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    actions: list[dict[str, Any]] = []
    validation_counts = Counter()
    for row in path_rows:
        for item in clean(row.get("validation_items")).split(";"):
            if item:
                validation_counts[(clean(row.get("family")), item)] += 1
    for (family, item), count in validation_counts.most_common(40):
        if count < 10:
            continue
        actions.append(
            {
                "priority": "P1" if item in {"allocation_required", "material_certificate_required"} else "P2",
                "scope": "path_validation",
                "family": family,
                "item": item,
                "occurrences": count,
                "recommended_action": action_for_item(family, item),
            }
        )
    for row in lane_rows[:40]:
        if row["criticality"] in {"critical", "high"} or not clean(row["transport_plausibility"]).startswith("ok_"):
            actions.append(
                {
                    "priority": "P1" if row["criticality"] == "critical" else "P2",
                    "scope": "transport_lane",
                    "family": row.get("family"),
                    "item": f"{row.get('edge')} {row.get('from_name')} -> {row.get('to_name')}",
                    "occurrences": row.get("path_use_count"),
                    "recommended_action": row.get("transport_validation_action"),
                }
            )
    for row in supplier_rows[:40]:
        if row["validation_risk"] in {"blocker", "high"}:
            actions.append(
                {
                    "priority": "P1" if row["validation_risk"] == "blocker" else "P2",
                    "scope": "supplier_switch",
                    "family": row.get("family"),
                    "item": f"{row.get('role')} {row.get('supplier')}",
                    "occurrences": row.get("path_count"),
                    "recommended_action": row.get("activation_gate"),
                }
            )
    return actions


def action_for_item(family: str, item: str) -> str:
    if item == "allocation_required":
        return "Confirm awarded source/allocation share/capacity/MOQ before enabling switch scenario."
    if item == "material_certificate_required":
        return "Require grade, mill/site, certificate and material standard before quantitative activation."
    if item == "lead_time_required":
        return "Replace family-level lead-time band by supplier/site-specific lead time and recovery time."
    if item == "longhaul_transport_lane_check":
        return "Validate baseline mode, port/airport assumptions and emergency expedite option."
    if item == "internal_process_t1_pairing_required":
        return "Model the switch as a paired T1/T2 route, or replace the internal process node by a real external processor for independent T2 switching."
    if "qualification" in item:
        return f"Run family qualification gate for {family}: specs, process route and program approval."
    if "fst" in item or "material_source" in item:
        return "Collect exact material datasheet/source and FST evidence."
    return "Review and either promote to active scenario or keep inactive."


def write_report(
    path_rows: list[dict[str, Any]],
    supplier_rows: list[dict[str, Any]],
    lane_rows: list[dict[str, Any]],
    component_rows: list[dict[str, Any]],
    action_rows: list[dict[str, Any]],
) -> None:
    path_counts = Counter(row["business_validation_status"] for row in path_rows)
    family_counts = Counter(row["family"] for row in path_rows)
    action_counts = Counter(row["scope"] for row in action_rows)
    lane_counts = Counter(row["criticality"] for row in lane_rows)
    supplier_risk_counts = Counter(row["validation_risk"] for row in supplier_rows)
    validation_items = Counter()
    for row in path_rows:
        for item in clean(row.get("validation_items")).split(";"):
            if item:
                validation_items[item] += 1

    lines = [
        "# Business Assumption Validation",
        "",
        f"- Generated at: `{dt.datetime.now(dt.UTC).isoformat(timespec='seconds')}`",
        f"- Path rows audited: **{len(path_rows)}**",
        f"- Supplier switch options audited: **{len(supplier_rows)}**",
        f"- Critical/visible transport lanes listed: **{len(lane_rows)}**",
        "",
        "## Interpretation",
        "",
        "The graph is topologically usable. This audit does not certify purchasing truth; it tells which evidence is still needed before a candidate path can be activated in stress tests.",
        "",
        "## Path Status",
        "",
    ]
    for key, count in path_counts.most_common():
        lines.append(f"- `{key}`: **{count}**")
    lines.extend(["", "## Families", ""])
    for key, count in family_counts.most_common():
        lines.append(f"- `{key}`: **{count}** path rows")
    lines.extend(["", "## Main Validation Gates", ""])
    for key, count in validation_items.most_common(16):
        lines.append(f"- `{key}`: **{count}** occurrences")
    lines.extend(["", "## Supplier Switch Risk", ""])
    for key, count in supplier_risk_counts.most_common():
        lines.append(f"- `{key}`: **{count}** supplier/family/tier options")
    lines.extend(["", "## Transport Lanes To Review", ""])
    for key, count in lane_counts.most_common():
        lines.append(f"- `{key}`: **{count}** lanes")
    lines.extend(["", "## Action Backlog", ""])
    for key, count in action_counts.most_common():
        lines.append(f"- `{key}`: **{count}** actions")
    lines.extend(["", "## Top Critical Lanes", ""])
    for row in lane_rows[:12]:
        lines.append(
            f"- `{row['criticality']}` `{row['edge']}` {row['from_name']} -> {row['to_name']} "
            f"({row['distance_km']} km, modes `{row['modes']}`, kg.km proxy {row['kg_km_proxy']})"
        )
    lines.extend(
        [
            "",
            "## Files",
            "",
            f"- Path validation: `{OUT_PATHS.as_posix()}`",
            f"- Supplier matrix: `{OUT_SUPPLIERS.as_posix()}`",
            f"- Critical lanes: `{OUT_LANES.as_posix()}`",
            f"- Component summary: `{OUT_COMPONENTS.as_posix()}`",
            f"- Action backlog: `{OUT_ACTIONS.as_posix()}`",
        ]
    )
    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    paths = read_csv(PATHS_CSV)
    lanes = read_csv(LANES_CSV)
    supplier_options = read_csv(SUPPLIER_OPTIONS_CSV)

    path_rows, component_counters = build_path_rows(paths)
    component_rows = build_component_rows(paths, component_counters)
    lane_rows = build_lane_rows(lanes)
    supplier_rows = build_supplier_rows(supplier_options)
    action_rows = build_action_rows(path_rows, lane_rows, supplier_rows)

    write_csv(OUT_PATHS, path_rows)
    write_csv(OUT_COMPONENTS, component_rows)
    write_csv(OUT_LANES, lane_rows)
    write_csv(OUT_SUPPLIERS, supplier_rows)
    write_csv(OUT_ACTIONS, action_rows)
    write_report(path_rows, supplier_rows, lane_rows, component_rows, action_rows)

    print(f"Wrote {OUT_PATHS}")
    print(f"Wrote {OUT_SUPPLIERS}")
    print(f"Wrote {OUT_LANES}")
    print(f"Wrote {OUT_COMPONENTS}")
    print(f"Wrote {OUT_ACTIONS}")
    print(f"Wrote {OUT_MD}")


if __name__ == "__main__":
    main()
