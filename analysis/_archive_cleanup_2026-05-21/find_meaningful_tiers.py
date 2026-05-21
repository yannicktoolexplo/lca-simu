#!/usr/bin/env python3
"""Build a meaningful tier taxonomy and supplier-tier assignment table."""

from __future__ import annotations

import csv
import json
import re
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
INPUT_JSON = ROOT / "analysis" / "output8_GEO_normalized_final_corrected.json"
OUT_TAXONOMY = ROOT / "analysis" / "output8_GEO_meaningful_tier_taxonomy.csv"
OUT_SUPPLIERS = ROOT / "analysis" / "output8_GEO_meaningful_supplier_tiers.csv"
OUT_MD = ROOT / "analysis" / "output8_GEO_meaningful_tiers.md"

ROLE_ORDER = [
    "tier4_raw_material",
    "tier3_first_transformation",
    "tier2_second_transformation",
    "tier1",
    "oem",
    "logistics",
]

TAXONOMY = [
    {
        "tier_code": "T4",
        "role_hint": "tier4_raw_material",
        "label": "Raw material / primary producer",
        "simulation_use": "upstream_supply_node",
        "meaning": "Mine/refinery/smelter/steelmaker/chemical producer or upstream commodity group supplying base materials.",
        "examples": "Alcoa, Tata Steel, BASF, ArcelorMittal, Hindalco, China Baowu",
        "stress_test_parameters": "commodity availability, geopolitical risk, energy shock, export restriction, long lead time",
    },
    {
        "tier_code": "T3",
        "role_hint": "tier3_first_transformation",
        "label": "First transformation / material processor",
        "simulation_use": "upstream_supply_node",
        "meaning": "Rolling, extrusion, forging, stockist/cutting service, textile/fiber/polymer first transformation.",
        "examples": "Constellium, AMAG, thyssenkrupp Materials France, Euralliage, Toray, EXSTO",
        "stress_test_parameters": "mill capacity, batch size, material substitution, regional sourcing, qualification delay",
    },
    {
        "tier_code": "T2",
        "role_hint": "tier2_second_transformation",
        "label": "Second transformation / component processor",
        "simulation_use": "upstream_supply_node",
        "meaning": "Injection, machining subcontractor, electronics/material component processor, textile/plastic sub-component supplier.",
        "examples": "Ensinger, Plastiservice, DuPont, MGR Foamtex, SCHROTH when component supplier",
        "stress_test_parameters": "process capacity, yield, tooling, supplier switch time, local make-or-buy",
    },
    {
        "tier_code": "T1",
        "role_hint": "tier1",
        "label": "Direct supplier / module or subassembly integrator",
        "simulation_use": "direct_supplier_node",
        "meaning": "Supplier directly feeding Safran/OEM with seat structures, interiors, upholstery, restraint, IFE or assembled modules.",
        "examples": "JAMCO, SUMPAR, Gattefin, Figeac Aero, Senior Aerospace Thailand, LAUAK, J&C Aero",
        "stress_test_parameters": "direct delivery, qualified alternates, capacity, service level, supplier recovery",
    },
    {
        "tier_code": "OEM",
        "role_hint": "oem",
        "label": "OEM / internal final integrator",
        "simulation_use": "sink_or_internal_factory",
        "meaning": "Safran Seats / internal final assembly or customer-facing integrator; keep separate from external suppliers.",
        "examples": "Safran Seats / Safran internal group",
        "stress_test_parameters": "final assembly capacity, demand, internal stock, bottleneck recovery",
    },
    {
        "tier_code": "LOG",
        "role_hint": "logistics",
        "label": "Logistics provider",
        "simulation_use": "route_or_transport_provider",
        "meaning": "Transport provider; should not be modeled as a manufacturing tier node unless the simulation needs carrier capacity.",
        "examples": "GEODIS, CEVA Logistics, XPO, Kuehne+Nagel",
        "stress_test_parameters": "lane availability, mode disruption, carrier capacity, customs delay",
    },
    {
        "tier_code": "PKG",
        "role_hint": "packaging",
        "label": "Packaging / consumables",
        "simulation_use": "optional_auxiliary_supply",
        "meaning": "Packaging is present in LCA BOM but should be a separate auxiliary flow, not mixed with seat material tiers.",
        "examples": "carton, film plastique, palette, papier bulle",
        "stress_test_parameters": "packaging shortage, returnable packaging loops, one-way packaging stock",
    },
]

ROLE_TO_CODE = {row["role_hint"]: row["tier_code"] for row in TAXONOMY}
ROLE_TO_LABEL = {row["role_hint"]: row["label"] for row in TAXONOMY}


def norm(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value or "").lower()).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


def country_region(country: str) -> str:
    europe = {
        "Austria",
        "Belgium",
        "Czech Republic",
        "Denmark",
        "Finland",
        "France",
        "Germany",
        "Ireland",
        "Italy",
        "Lithuania",
        "Luxembourg",
        "Netherlands",
        "Norway",
        "Poland",
        "Portugal",
        "Spain",
        "Sweden",
        "Switzerland",
        "United Kingdom",
    }
    if country == "France":
        return "France"
    if country in europe:
        return "Europe_non_FR"
    if country:
        return "Outside_Europe"
    return "unknown"


def supplier_key(supplier: dict[str, Any]) -> tuple[str, str, str]:
    return (
        str(supplier.get("name") or "").strip(),
        str(supplier.get("role_hint") or "").strip(),
        str(supplier.get("location") or "").strip(),
    )


def supplier_business_family(name: str, role: str, descriptions: list[str]) -> str:
    text = norm(" ".join([name, role] + descriptions))
    rules = [
        ("steel_metal_raw", r"steel|acier|saarstahl|tata|nucor|arcelor|baowu|krupp"),
        ("aluminium_raw_or_transformation", r"alcoa|aluminium|chalco|hindalco|constellium|amag|a5086|a2017|a2024|a6060"),
        ("metal_transformation_or_machining", r"usinage|machining|forge|forging|gattefin|figeac|sumpar|lauak|segnere|aerospace"),
        ("polymer_plastic_chemical", r"plastic|plast|polymer|polymere|dupont|basf|bayer|ensinger|exsto|kydex|ertalon|lexan"),
        ("textile_foam_leather", r"textile|tissu|foam|mousse|cuir|leather|mgr|ultrafabrics|huddersfield|paragon"),
        ("electronics_ife", r"electronics|electronic|display|screen|ife|keyboard|power|ecu|e2ip|krohne"),
        ("seat_interior_module", r"jamco|interior|cabin|seat|stelia|airbus|j c aero|collins"),
        ("restraint_safety", r"amsafe|schroth|ancra|ceinture|restraint|safety"),
        ("logistics", r"logistics|geodis|ceva|kuehne|xpo"),
    ]
    for label, pattern in rules:
        if re.search(pattern, text):
            return label
    return "general_industrial"


def confidence_for_supplier(role: str, row: dict[str, Any]) -> str:
    if role in {"oem", "logistics"}:
        return "high"
    if row["source_ids"]:
        return "high"
    if row["geocode_status_counts"].get("source_backed_site"):
        return "high"
    if row["record_count"] >= 10 and row["has_coordinates"]:
        return "medium"
    return "review"


def aggregate_suppliers(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    aggregates: dict[tuple[str, str, str], dict[str, Any]] = {}

    def add_supplier(record: dict[str, Any], supplier: dict[str, Any], collection: str) -> None:
        key = supplier_key(supplier)
        role = key[1]
        if role not in ROLE_TO_CODE:
            role = collection
        if key not in aggregates:
            aggregates[key] = {
                "supplier": key[0],
                "role_hint": role,
                "tier_code": ROLE_TO_CODE.get(role, role.upper()),
                "tier_label": ROLE_TO_LABEL.get(role, role),
                "country": key[2],
                "region": country_region(key[2]),
                "record_count": 0,
                "primary_count": 0,
                "component_examples": [],
                "system_examples": [],
                "mass_exposure_kg_sum_record_level": 0.0,
                "source_ids": set(),
                "descriptions": [],
                "geocode_status_counts": Counter(),
                "has_coordinates": False,
                "collection": collection,
            }
        row = aggregates[key]
        row["record_count"] += 1
        if supplier.get("is_primary"):
            row["primary_count"] += 1
        mass = record.get("mass_kg")
        if isinstance(mass, (int, float)):
            row["mass_exposure_kg_sum_record_level"] += float(mass)
        component = str(record.get("component") or "")
        system = str(record.get("system") or "")
        if component and component not in row["component_examples"] and len(row["component_examples"]) < 8:
            row["component_examples"].append(component)
        if system and system not in row["system_examples"] and len(row["system_examples"]) < 6:
            row["system_examples"].append(system)
        for source_id in supplier.get("source_ids") or []:
            if source_id:
                row["source_ids"].add(str(source_id))
        description = str(supplier.get("description") or "")
        if description and description not in row["descriptions"] and len(row["descriptions"]) < 6:
            row["descriptions"].append(description)
        geocode_status = str(supplier.get("geocode_status") or "")
        if geocode_status:
            row["geocode_status_counts"][geocode_status] += 1
        if supplier.get("lat") is not None and supplier.get("lon") is not None:
            row["has_coordinates"] = True

    for record in records:
        for supplier in record.get("suppliers") or []:
            add_supplier(record, supplier, "supplier")
        for supplier in record.get("oem_sites") or []:
            add_supplier(record, supplier, "oem")
        for supplier in record.get("logistics_providers") or []:
            add_supplier(record, supplier, "logistics")

    out: list[dict[str, Any]] = []
    for row in aggregates.values():
        family = supplier_business_family(row["supplier"], row["role_hint"], row["descriptions"])
        confidence = confidence_for_supplier(row["role_hint"], row)
        modeling_action = "keep_as_supply_tier_node"
        if row["role_hint"] == "oem":
            modeling_action = "model_as_sink_or_internal_factory"
        elif row["role_hint"] == "logistics":
            modeling_action = "move_to_transport_layer"
        out.append(
            {
                "tier_code": row["tier_code"],
                "role_hint": row["role_hint"],
                "tier_label": row["tier_label"],
                "supplier": row["supplier"],
                "country": row["country"],
                "region": row["region"],
                "business_family": family,
                "record_count": row["record_count"],
                "primary_count": row["primary_count"],
                "alternate_count": row["record_count"] - row["primary_count"],
                "mass_exposure_kg_sum_record_level": round(row["mass_exposure_kg_sum_record_level"], 9),
                "confidence": confidence,
                "modeling_action": modeling_action,
                "has_coordinates": row["has_coordinates"],
                "source_ids": ";".join(sorted(row["source_ids"])),
                "geocode_status_counts": ";".join(f"{k}:{v}" for k, v in row["geocode_status_counts"].most_common()),
                "system_examples": " | ".join(row["system_examples"]),
                "component_examples": " | ".join(row["component_examples"]),
                "description_examples": " | ".join(row["descriptions"]),
            }
        )
    out.sort(key=lambda row: (ROLE_ORDER.index(row["role_hint"]) if row["role_hint"] in ROLE_ORDER else 99, -row["record_count"], row["supplier"]))
    return out


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fields = list(rows[0].keys())
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def write_markdown(rows: list[dict[str, Any]], records_count: int) -> None:
    role_counts = Counter(row["role_hint"] for row in rows)
    role_record_counts = Counter()
    role_primary_counts = Counter()
    confidence_counts = Counter(row["confidence"] for row in rows)
    action_counts = Counter(row["modeling_action"] for row in rows)
    region_by_role: dict[str, Counter] = defaultdict(Counter)
    for row in rows:
        role_record_counts[row["role_hint"]] += int(row["record_count"])
        role_primary_counts[row["role_hint"]] += int(row["primary_count"])
        region_by_role[row["role_hint"]][row["region"]] += 1

    lines = [
        "# Meaningful tiers for the aeronautical-seat supply network",
        "",
        f"- Source JSON: `{INPUT_JSON.as_posix()}`",
        f"- Taxonomy CSV: `{OUT_TAXONOMY.as_posix()}`",
        f"- Supplier assignment CSV: `{OUT_SUPPLIERS.as_posix()}`",
        "",
        "## Tier taxonomy to keep",
        "",
    ]
    for item in TAXONOMY:
        lines.append(f"- **{item['tier_code']} / {item['role_hint']}**: {item['label']}. {item['meaning']}")
    lines += [
        "",
        "## Counts",
        "",
        f"- Records analysed: {records_count}",
        f"- Supplier/site/tier assignments: {len(rows)}",
        f"- Confidence: " + ", ".join(f"{k}={v}" for k, v in confidence_counts.most_common()),
        f"- Modeling actions: " + ", ".join(f"{k}={v}" for k, v in action_counts.most_common()),
        "",
        "| Role | Unique supplier/site/tier | Record appearances | Primary appearances | Region split |",
        "|---|---:|---:|---:|---|",
    ]
    for role in ROLE_ORDER:
        lines.append(
            f"| {role} | {role_counts[role]} | {role_record_counts[role]} | {role_primary_counts[role]} | "
            + ", ".join(f"{k}={v}" for k, v in region_by_role[role].most_common())
            + " |"
        )
    lines += [
        "",
        "## Interpretation",
        "",
        "- The meaningful manufacturing tiers are `T4`, `T3`, `T2`, and `T1`; `OEM` is the sink/internal factory, not an external supplier tier.",
        "- `LOG` should be kept in the route/transport layer, not mixed with production suppliers.",
        "- `PKG` is meaningful for LCA and operational packaging risk, but it should be an auxiliary flow unless the simulation explicitly tests packaging shortages.",
        "- For supplier-switch simulations, use `T1-T4` as switchable supplier layers, keep `OEM` fixed, and apply logistics disruptions separately.",
        "",
        "## Highest-exposure assignments to review first",
        "",
    ]
    for row in sorted(rows, key=lambda r: float(r["mass_exposure_kg_sum_record_level"]), reverse=True)[:20]:
        lines.append(
            f"- {row['tier_code']} `{row['supplier']}` ({row['country']}): "
            f"{row['mass_exposure_kg_sum_record_level']} kg record-level exposure, "
            f"records={row['record_count']}, confidence={row['confidence']}"
        )
    lines += [
        "",
        "## Caveat",
        "",
        "The mass exposure column is a record-level screening proxy. It can double-count if aggregate `Siege` rows and detailed material rows are analysed together.",
        "",
    ]
    OUT_MD.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    data = json.loads(INPUT_JSON.read_text(encoding="utf-8"))
    records = data.get("records") or []
    supplier_rows = aggregate_suppliers(records)
    write_csv(OUT_TAXONOMY, TAXONOMY)
    write_csv(OUT_SUPPLIERS, supplier_rows)
    write_markdown(supplier_rows, len(records))
    print(f"[OK] wrote {OUT_MD}")
    print(f"[OK] wrote {OUT_TAXONOMY}")
    print(f"[OK] wrote {OUT_SUPPLIERS}")
    print(f"[INFO] assignments={len(supplier_rows)}")


if __name__ == "__main__":
    main()
