#!/usr/bin/env python3
"""Mark LCA/BOM traceability from quantity_material.xlsx in the complete baseline JSON."""

from __future__ import annotations

import csv
import datetime as dt
import importlib.util
import json
from collections import Counter
from pathlib import Path
from typing import Any


BASE_DIR = Path(__file__).resolve().parent
ROOT = BASE_DIR.parent
INPUT_JSON = BASE_DIR / "output8_GEO_normalized_final_primary_complete.json"
OUTPUT_JSON = BASE_DIR / "output8_GEO_normalized_final_primary_complete_lca_marked.json"
DETAIL_CSV = BASE_DIR / "output8_GEO_lca_traceability_marks.csv"
REPORT_MD = BASE_DIR / "output8_GEO_lca_traceability_report.md"
WORKBOOK = ROOT / "data" / "quantity_material.xlsx"
ESTIMATE_SCRIPT = BASE_DIR / "estimate_output8_masses.py"


def load_mass_module():
    spec = importlib.util.spec_from_file_location("estimate_output8_masses", ESTIMATE_SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load {ESTIMATE_SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def norm_source(value: Any) -> str:
    return str(value or "").replace("\\", "/")


def method_level(method: str) -> str:
    if method == "bom_exact_system_material":
        return "exact_equipment_material"
    if method == "bom_mixed_material_share":
        return "equipment_material_split"
    if method == "bom_system_material_family_sum":
        return "equipment_material_family"
    if method == "bom_global_material_total":
        return "global_material"
    if method == "bom_global_material_family_sum":
        return "global_material_family"
    if method == "percentage_of_bom_material_total":
        return "seat_total_percentage"
    if method == "bom_equipment_total_no_material_split":
        return "equipment_total"
    return "not_lca_bom"


def mass_use_class(confidence: str, method: str) -> str:
    if confidence == "high" and method == "bom_exact_system_material":
        return "quantitative_ready"
    if confidence in {"high", "medium_high"}:
        return "usable_for_baseline"
    if confidence == "medium":
        return "usable_with_review"
    return "scenario_only_review_required"


def build_mark(record: dict[str, Any], total_seat_mass: float) -> dict[str, Any]:
    mass = record.get("mass_kg")
    method = str(record.get("mass_estimation_method") or "")
    confidence = str(record.get("mass_confidence") or "")
    source = norm_source(record.get("mass_source"))
    source_is_lca = source.endswith("data/quantity_material.xlsx")
    match_level = method_level(method)
    share = None
    try:
        if mass is not None and total_seat_mass:
            share = float(mass) / total_seat_mass
    except (TypeError, ValueError):
        share = None

    markers = []
    if source_is_lca:
        markers.append("LCA_SOURCE_quantity_material_xlsx")
    if match_level != "not_lca_bom":
        markers.append(f"LCA_MATCH_{match_level}")
    if confidence:
        markers.append(f"LCA_CONFIDENCE_{confidence}")
    if method == "bom_exact_system_material":
        markers.append("LCA_EXACT_BOM_MASS")
    elif method.startswith("bom_") or method == "percentage_of_bom_material_total":
        markers.append("LCA_ESTIMATED_BOM_MASS")

    raw_status = str(record.get("raw_materials_status") or "")
    if raw_status:
        markers.append(f"RAW_MATERIALS_{raw_status}")

    return {
        "source_workbook": WORKBOOK.as_posix(),
        "source_sheet": "BOM",
        "source_type": "life_cycle_inventory_quantity_material",
        "has_lca_mass": bool(source_is_lca and mass is not None),
        "mass_kg": mass,
        "mass_share_of_non_packaging_bom": None if share is None else round(share, 9),
        "mass_method": method,
        "match_level": match_level,
        "confidence": confidence,
        "simulation_use_class": mass_use_class(confidence, method),
        "equipment_match": record.get("mass_equipment_match", ""),
        "material_match": record.get("mass_material_match", ""),
        "raw_materials": record.get("raw_materials") or [],
        "raw_materials_status": raw_status,
        "material_modeling_refs": record.get("material_modeling_refs") or {},
        "markers": markers,
        "interpretation": (
            "ACV/BOM source can support quantitative mass-weighted simulation."
            if confidence in {"high", "medium_high"}
            else "ACV-derived fallback: keep for scenario sizing, review before high-stakes stress tests."
        ),
    }


def add_lca_to_supplier_entries(record: dict[str, Any], mark: dict[str, Any]) -> None:
    summary = {
        "lca_mass_kg": mark["mass_kg"],
        "lca_confidence": mark["confidence"],
        "lca_match_level": mark["match_level"],
        "lca_simulation_use_class": mark["simulation_use_class"],
        "lca_equipment_match": mark["equipment_match"],
        "lca_material_match": mark["material_match"],
        "lca_source": "quantity_material.xlsx" if mark["has_lca_mass"] else "",
    }
    for container in ["suppliers", "oem_sites", "logistics_providers"]:
        for entry in record.get(container) or []:
            if not isinstance(entry, dict):
                continue
            entry.setdefault("lca_component_trace", summary)


def workbook_summary(module) -> dict[str, Any]:
    sheets = module.xlsx_rows(WORKBOOK)
    by_equipment_material, by_equipment_total, by_material_total, _equipment_display = module.parse_bom(sheets)
    total_non_packaging = module.seat_total(by_material_total)
    return {
        "sheet_names": list(sheets.keys()),
        "bom_material_rows": len(by_equipment_material),
        "bom_equipment_count": len(by_equipment_total),
        "bom_material_count": len(by_material_total),
        "total_non_packaging_bom_mass_kg": round(total_non_packaging, 9),
    }


def main() -> None:
    module = load_mass_module()
    wb_summary = workbook_summary(module)
    total_seat_mass = float(wb_summary["total_non_packaging_bom_mass_kg"])

    data = json.loads(INPUT_JSON.read_text(encoding="utf-8"))
    records = data.get("records") or []
    rows: list[dict[str, Any]] = []

    for index, record in enumerate(records, 1):
        if not isinstance(record, dict):
            continue
        mark = build_mark(record, total_seat_mass)
        record["lca_traceability"] = mark
        add_lca_to_supplier_entries(record, mark)
        rows.append(
            {
                "record_index": index,
                "system": record.get("system", ""),
                "component": record.get("component", ""),
                "mass_kg": mark["mass_kg"],
                "mass_share_of_non_packaging_bom": mark["mass_share_of_non_packaging_bom"],
                "has_lca_mass": mark["has_lca_mass"],
                "mass_method": mark["mass_method"],
                "match_level": mark["match_level"],
                "confidence": mark["confidence"],
                "simulation_use_class": mark["simulation_use_class"],
                "equipment_match": mark["equipment_match"],
                "material_match": mark["material_match"],
                "raw_materials_status": mark["raw_materials_status"],
                "markers": ";".join(mark["markers"]),
            }
        )

    methods = Counter(row["mass_method"] for row in rows)
    confidence = Counter(row["confidence"] for row in rows)
    use_classes = Counter(row["simulation_use_class"] for row in rows)
    match_levels = Counter(row["match_level"] for row in rows)
    with DETAIL_CSV.open("w", encoding="utf-8-sig", newline="") as handle:
        fieldnames = list(rows[0].keys()) if rows else []
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    data.setdefault("_meta", {})
    data["_meta"]["lca_traceability"] = {
        "source_workbook": WORKBOOK.as_posix(),
        "generated_at": dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat(),
        "script": Path(__file__).as_posix(),
        **wb_summary,
        "records_marked": len(rows),
    }
    OUTPUT_JSON.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        "# LCA Traceability Marks",
        "",
        f"- Input JSON: `{INPUT_JSON.as_posix()}`",
        f"- Output JSON: `{OUTPUT_JSON.as_posix()}`",
        f"- Source workbook: `{WORKBOOK.as_posix()}`",
        f"- Detail CSV: `{DETAIL_CSV.as_posix()}`",
        f"- Workbook sheets: {', '.join(wb_summary['sheet_names'])}",
        f"- Non-packaging BOM mass: **{total_seat_mass:.6f} kg**",
        f"- Records marked: **{len(rows)}**",
        "",
        "## Coverage",
        "",
        f"- Records with LCA mass: **{sum(1 for row in rows if row['has_lca_mass'])} / {len(rows)}**",
        "",
        "## Match Levels",
        "",
    ]
    for key, count in match_levels.most_common():
        lines.append(f"- `{key}`: {count}")
    lines += ["", "## Methods", ""]
    for key, count in methods.most_common():
        lines.append(f"- `{key}`: {count}")
    lines += ["", "## Confidence", ""]
    for key, count in confidence.most_common():
        lines.append(f"- `{key}`: {count}")
    lines += ["", "## Simulation Use", ""]
    for key, count in use_classes.most_common():
        lines.append(f"- `{key}`: {count}")
    lines += [
        "",
        "## Interpretation",
        "",
        "- `quantitative_ready`: exact equipment/material BOM mass; good for mass-weighted stress tests.",
        "- `usable_for_baseline`: ACV/BOM family or split estimate; useful for baseline sizing.",
        "- `usable_with_review`: percentage or broader fallback; review before sensitive analyses.",
        "- `scenario_only_review_required`: global fallback; keep visible but do not over-interpret.",
        "",
    ]
    REPORT_MD.write_text("\n".join(lines), encoding="utf-8")

    print(f"[OK] wrote {OUTPUT_JSON}")
    print(f"[OK] wrote {DETAIL_CSV}")
    print(f"[OK] wrote {REPORT_MD}")
    print(f"[INFO] lca_mass={sum(1 for row in rows if row['has_lca_mass'])}/{len(rows)}")
    print("[INFO] use_classes=" + ", ".join(f"{k}:{v}" for k, v in use_classes.most_common()))


if __name__ == "__main__":
    main()
