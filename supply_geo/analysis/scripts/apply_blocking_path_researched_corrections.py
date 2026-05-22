#!/usr/bin/env python3
"""Apply researched corrections for simulation-ready supply paths.

The script keeps the previous JSON intact and writes a corrected copy. It does
not certify procurement truth. It turns researched decisions into explicit
simulation assumptions, with inactive candidates preserved for traceability.
"""

from __future__ import annotations

import copy
import csv
import datetime as dt
import json
import math
import re
from pathlib import Path
from typing import Any


BASE_DIR = Path(__file__).resolve().parent
INPUT_JSON = BASE_DIR / "output8_GEO_normalized_final_primary_complete_lca_marked.json"
OUTPUT_JSON = BASE_DIR / "output8_GEO_normalized_simulation_ready_researched.json"
CHANGES_CSV = BASE_DIR / "output8_GEO_simulation_ready_researched_changes.csv"
REPORT_MD = BASE_DIR / "output8_GEO_simulation_ready_researched_report.md"

ROLE_T4 = "tier4_raw_material"
ROLE_T3 = "tier3_first_transformation"
ROLE_T2 = "tier2_second_transformation"
ROLE_T1 = "tier1"

TODAY = "2026-05-21"


def clean(value: Any) -> str:
    return str(value or "").strip()


def slug(value: str) -> str:
    out = re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")
    return out or "unknown"


def lca_trace(record: dict[str, Any]) -> dict[str, Any]:
    return record.get("lca_traceability") or {}


def safe_float(value: Any) -> float | None:
    try:
        if value in (None, ""):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def haversine_km(a: dict[str, Any], b: dict[str, Any]) -> float | None:
    lat1 = safe_float(a.get("lat"))
    lon1 = safe_float(a.get("lon"))
    lat2 = safe_float(b.get("lat"))
    lon2 = safe_float(b.get("lon"))
    if lat1 is None or lon1 is None or lat2 is None or lon2 is None:
        return None
    radius = 6371.0088
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    h = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlambda / 2) ** 2
    return 2 * radius * math.asin(math.sqrt(h))


def suppliers(record: dict[str, Any]) -> list[dict[str, Any]]:
    items = record.setdefault("suppliers", [])
    return [s for s in items if isinstance(s, dict)]


def add_change(changes: list[dict[str, Any]], record_index: int, action: str, detail: str) -> None:
    changes.append({"record_index": record_index, "action": action, "detail": detail})


def find_template(records: list[dict[str, Any]], name: str, role: str | None = None) -> dict[str, Any] | None:
    name_l = name.lower()
    for record in records:
        for supplier in record.get("suppliers") or []:
            if not isinstance(supplier, dict):
                continue
            if name_l in clean(supplier.get("name")).lower() and (role is None or supplier.get("role_hint") == role):
                return copy.deepcopy(supplier)
    return None


def clone_node(
    records: list[dict[str, Any]],
    *,
    name: str,
    role: str,
    template_name: str | None = None,
    status: str = "baseline_primary_assumed_internalized_process",
    primary: bool = True,
    allocation: float = 100.0,
    simulation_node_type: str = "virtual_process_or_market_basket",
    description: str | None = None,
    location: str | None = None,
    lat: float | None = None,
    lon: float | None = None,
    note: str | None = None,
    source_ids: list[str] | None = None,
    stress_test_switchable: bool | None = None,
) -> dict[str, Any]:
    template = find_template(records, template_name or name, None)
    node = copy.deepcopy(template) if template else {}
    node["name"] = name
    node["role_hint"] = role
    node["is_primary"] = primary
    node["allocation_share_pct"] = allocation if primary else 0.0
    node["supplier_status"] = status
    if description is not None:
        node["description"] = description
    if location is not None:
        node["location"] = location
    if lat is not None:
        node["lat"] = lat
    if lon is not None:
        node["lon"] = lon
    if source_ids is not None:
        node["source_ids"] = source_ids
    if note:
        notes = node.setdefault("correction_notes", [])
        if note not in notes:
            notes.append(note)
    node["simulation_node_type"] = simulation_node_type
    node["source_confidence"] = node.get("source_confidence") or "medium"
    node["geocode_status"] = node.get("geocode_status") or "virtual_node_at_downstream_site"
    if "internal" in status or "virtual" in simulation_node_type:
        node["geocode_status"] = "virtual_node_at_downstream_site"
        node["baseline_completion_assumption"] = True
    node["baseline_completion_confidence"] = node.get("baseline_completion_confidence") or "medium_high"
    node["baseline_completion_note"] = note or node.get("baseline_completion_note") or "Researched correction for simulation topology; validate with routing, BOM or certificate."
    if stress_test_switchable is not None:
        node["stress_test_switchable"] = stress_test_switchable
    node["supplier_id"] = slug(f"{name}__{role}")
    if node.get("lat") not in (None, "") and node.get("lon") not in (None, ""):
        node["site_id"] = f"{node['supplier_id']}@{node['lat']},{node['lon']}"
    else:
        node["site_id"] = f"{node['supplier_id']}@unknown"
    return node


def attach_lca_trace(record: dict[str, Any], node: dict[str, Any]) -> None:
    lca = lca_trace(record)
    if not lca:
        return
    node["lca_component_trace"] = {
        "lca_mass_kg": lca.get("mass_kg", record.get("mass_kg")),
        "lca_confidence": lca.get("confidence", record.get("mass_confidence")),
        "lca_match_level": lca.get("match_level"),
        "lca_simulation_use_class": lca.get("simulation_use_class"),
        "lca_equipment_match": lca.get("equipment_match"),
        "lca_material_match": lca.get("material_match"),
        "lca_source": "quantity_material.xlsx",
    }


def demote_role(record: dict[str, Any], role: str, reason: str, except_names: set[str] | None = None) -> list[str]:
    except_names = {x.lower() for x in (except_names or set())}
    demoted: list[str] = []
    for supplier in suppliers(record):
        if supplier.get("role_hint") != role:
            continue
        if clean(supplier.get("name")).lower() in except_names:
            continue
        if supplier.get("is_primary"):
            demoted.append(clean(supplier.get("name")))
        supplier["is_primary"] = False
        supplier["allocation_share_pct"] = 0.0
        if "alternate" not in clean(supplier.get("supplier_status")).lower():
            supplier["supplier_status"] = "alternate_demoted_by_researched_correction"
        notes = supplier.setdefault("correction_notes", [])
        if reason not in notes:
            notes.append(reason)
    return demoted


def upsert_primary(record: dict[str, Any], node: dict[str, Any]) -> None:
    role = node.get("role_hint")
    name_l = clean(node.get("name")).lower()
    for idx, supplier in enumerate(record.setdefault("suppliers", [])):
        if not isinstance(supplier, dict):
            continue
        if supplier.get("role_hint") == role and clean(supplier.get("name")).lower() == name_l:
            merged = copy.deepcopy(supplier)
            merged.update(node)
            record["suppliers"][idx] = merged
            return
    record.setdefault("suppliers", []).append(node)


def set_primary(
    records: list[dict[str, Any]],
    record: dict[str, Any],
    record_index: int,
    changes: list[dict[str, Any]],
    *,
    role: str,
    name: str,
    template_name: str | None = None,
    status: str = "baseline_primary",
    description: str | None = None,
    location: str | None = None,
    lat: float | None = None,
    lon: float | None = None,
    note: str,
    simulation_node_type: str = "physical_supplier_site",
    source_ids: list[str] | None = None,
    stress_test_switchable: bool | None = None,
) -> None:
    demoted = demote_role(record, role, note, except_names={name})
    node = clone_node(
        records,
        name=name,
        role=role,
        template_name=template_name,
        status=status,
        primary=True,
        allocation=100.0,
        simulation_node_type=simulation_node_type,
        description=description,
        location=location,
        lat=lat,
        lon=lon,
        note=note,
        source_ids=source_ids,
        stress_test_switchable=stress_test_switchable,
    )
    attach_lca_trace(record, node)
    upsert_primary(record, node)
    add_change(changes, record_index, f"set_primary_{role}", f"{name}; demoted={', '.join(demoted) or 'none'}")


def set_internal_process(
    records: list[dict[str, Any]],
    record: dict[str, Any],
    record_index: int,
    changes: list[dict[str, Any]],
    *,
    owner_name: str,
    owner_template: str | None = None,
    process_label: str = "internal machining/forming process",
    note: str,
    description: str | None = None,
) -> None:
    t1_template = find_template(records, owner_template or owner_name, ROLE_T1)
    name = f"{owner_name} - {process_label}"
    demoted = demote_role(record, ROLE_T2, note, except_names={name})
    node = clone_node(
        records,
        name=name,
        role=ROLE_T2,
        template_name=owner_template or owner_name,
        status="baseline_primary_assumed_internalized_process",
        simulation_node_type="virtual_process_or_market_basket",
        description=description or (t1_template or {}).get("description") or "Internalized process under T1 responsibility",
        location=(t1_template or {}).get("location"),
        lat=(t1_template or {}).get("lat"),
        lon=(t1_template or {}).get("lon"),
        note=note,
        stress_test_switchable=False,
    )
    attach_lca_trace(record, node)
    upsert_primary(record, node)
    add_change(changes, record_index, "set_internal_t2_process", f"{name}; demoted={', '.join(demoted) or 'none'}")


def set_transport(record: dict[str, Any], segment: str, modes: list[str], modes_original: list[str], note: str) -> None:
    transport = record.setdefault("transport", {})
    segment_data = transport.setdefault(segment, {})
    segment_data["modes"] = modes
    segment_data["modes_original"] = modes_original
    segment_data["correction_note"] = note


def add_lane_scenarios(record: dict[str, Any], scenarios: list[dict[str, Any]]) -> None:
    existing = record.setdefault("transport_scenarios", [])
    keys = {clean(s.get("scenario_id")) for s in existing if isinstance(s, dict)}
    for scenario in scenarios:
        if scenario.get("scenario_id") not in keys:
            existing.append(scenario)


def has_edge_scenario(record: dict[str, Any], edge: str) -> bool:
    return any(
        isinstance(scenario, dict)
        and scenario.get("edge") == edge
        and scenario.get("modes")
        and "baseline" in clean(scenario.get("scenario_id")).lower()
        for scenario in record.get("transport_scenarios") or []
    )


def add_record_note(record: dict[str, Any], note: str, sources: list[str]) -> None:
    corrections = record.setdefault("researched_corrections_applied", [])
    entry = {"date": TODAY, "note": note, "sources": sources}
    if entry not in corrections:
        corrections.append(entry)


def infer_record_family(record: dict[str, Any]) -> str:
    override = clean(record.get("component_family_override"))
    if override:
        return override
    component_text = " ".join(
        [
            clean(record.get("component")),
            clean(record.get("mass_material_match")),
        ]
    ).lower()
    raw_text = " ".join(clean(x) for x in record.get("raw_materials") or []).lower()
    text = " ".join(
        [
            clean(record.get("component")),
            clean(record.get("mass_material_match")),
            " ".join(clean(x) for x in record.get("raw_materials") or []),
        ]
    ).lower()
    if any(k in component_text for k in ["display", "powerbox", "ife", "ecu", "clavier", "lightning", "screen", "pcb"]):
        return "electronics_cots"
    if any(k in component_text for k in ["frmc55", "polyurethane", "mousse", "tissu", "velours", "velcro", "cuir", "nylon", "leather"]):
        return "textile_leather"
    if "silicone" in component_text:
        return "rubber_silicone"
    if any(k in component_text for k in ["lexan", "kydex", "ertalon", "nida", "poly", "plastique", "plastic", "caoutchouc"]):
        return "polymer_plastic"
    if any(k in component_text for k in ["resine", "résine", "film", "adhes", "aerfilm", "composite"]):
        return "adhesive_composite"
    if any(k in component_text for k in ["a5086", "a6060", "a2017", "a2024", "aluminium", " alu"]):
        return "aluminium"
    if any(k in component_text for k in ["acier", "steel", "inox", "35nc6", "30ncd6", "15cdv6", "4140", "z10cnt"]):
        return "steel"
    if any(k in component_text for k in ["cuivre", "copper", "alliage cu"]):
        return "copper"
    if any(k in raw_text for k in ["tissu", "textile", "nylon", "polyamide", "cuir", "leather", "mousse"]):
        return "textile_leather"
    if any(k in raw_text for k in ["aluminium", " alu"]):
        return "aluminium"
    if any(k in raw_text for k in ["acier", "steel", "inox"]):
        return "steel"
    return "general"


def exclude_supplier(
    record: dict[str, Any],
    *,
    name: str,
    role: str | None,
    reason: str,
) -> int:
    kept: list[dict[str, Any]] = []
    removed = 0
    for supplier in record.get("suppliers") or []:
        if not isinstance(supplier, dict):
            kept.append(supplier)
            continue
        name_match = clean(supplier.get("name")).lower() == name.lower()
        role_match = role is None or supplier.get("role_hint") == role
        if name_match and role_match:
            supplier = copy.deepcopy(supplier)
            supplier["is_primary"] = False
            supplier["allocation_share_pct"] = 0.0
            supplier["supplier_status"] = "excluded_from_switch_scenarios"
            notes = supplier.setdefault("correction_notes", [])
            if reason not in notes:
                notes.append(reason)
            excluded = record.setdefault("excluded_suppliers", [])
            excluded.append(supplier)
            removed += 1
        else:
            kept.append(supplier)
    record["suppliers"] = kept
    return removed


def apply_aluminium_lca_routes(records: list[dict[str, Any]], changes: list[dict[str, Any]]) -> None:
    route_map = {
        17: "SUMPAR",
        18: "MGA Villeneuve St Lot",
        19: "SUMPAR",
        20: "MGA Villeneuve St Lot",
        21: "ETS Gattefin",
        22: "ETS Gattefin",
        23: "ETS Gattefin",
        24: "ETS Gattefin",
        25: "SUMPAR",
        26: "MGA Villeneuve St Lot",
        27: "ETS Gattefin",
        28: "ETS Gattefin",
        54: "Senior Aerospace Thailand",
        55: "Senior Aerospace Thailand",
        167: "SUMPAR",
    }
    source_note = "LCA/BOM exact supplier replaces Combigo aluminium T2; Combigo demoted as non-industrial travel-arrangements profile."
    sources = ["data/quantity_material.xlsx", "https://www.sumpar.com/en/", "https://www.lafrenchfab.fr/entreprise/mga-groupe-arm/", "https://gattefin.fr/", "https://www.senior-thailand.com/Web/what_we_do"]
    for idx, owner in route_map.items():
        record = records[idx - 1]
        set_primary(
            records,
            record,
            idx,
            changes,
            role=ROLE_T1,
            name=owner,
            template_name=owner,
            status="baseline_primary_lca_exact_supplier",
            note=source_note,
        )
        set_internal_process(records, record, idx, changes, owner_name=owner, note=source_note)
        if owner == "Senior Aerospace Thailand":
            set_transport(record, "from_supplier_to_safran", ["truck", "air"], ["Camion", "Avion"], "ACV/BOM says AVION for Senior Aerospace Thailand; truck-only removed.")
            add_lane_scenarios(
                record,
                [
                    {
                        "scenario_id": "baseline_acv_air_truck",
                        "edge": "T1->OEM",
                        "modes": ["truck", "air", "truck"],
                        "source": "data/quantity_material.xlsx",
                        "status": "baseline_for_acv_record",
                    },
                    {
                        "scenario_id": "cost_co2_sea_truck_candidate",
                        "edge": "T1->OEM",
                        "modes": ["truck", "ship", "truck"],
                        "status": "scenario_candidate_requires_lane_validation",
                    },
                ],
            )
        else:
            set_transport(record, "from_supplier_to_safran", ["truck"], ["Camion"], "ACV/BOM exact supplier is France/near-EU truck baseline.")
        add_record_note(record, source_note, sources)


def apply_secondary_candidate_cleanup(records: list[dict[str, Any]], changes: list[dict[str, Any]]) -> None:
    reason = "Combigo is not an industrial aluminium process supplier; removed from switchable secondary scenarios after LCA/BOM correction."
    for idx, record in enumerate(records, 1):
        removed = exclude_supplier(record, name="Combigo", role=ROLE_T2, reason=reason)
        if removed:
            add_record_note(record, reason, ["data/quantity_material.xlsx", "https://www.linkedin.com/company/combigo/"])
            add_change(changes, idx, "exclude_combigo_from_secondary_switches", f"removed {removed} Combigo T2 candidate(s)")


def is_obviously_incompatible_supplier(family: str, role: str, name: str, status: str) -> str | None:
    n = name.lower()
    if "excluded" in status.lower():
        return "already excluded"
    if family == "electronics_cots" and role in {ROLE_T4, ROLE_T3}:
        if "cots electronics" not in n and "subassembly/pcb" not in n:
            return "COTS/electronics upstream must not use inferred material suppliers without BOM/PN/AVL"

    metal_or_mining = [
        "saarstahl",
        "aubert",
        "krupp",
        "thyssenkrupp",
        "aurubis",
        "ampco",
        "zijin",
        "alcoa",
        "chalco",
        "hindalco",
        "tata steel",
        "nucor",
        "baowu",
        "euralliage",
        "aluminium france",
        "altec",
    ]
    electronics_names = ["krohne", "vaisala", "auberon", "innoptec"]
    carbon_composite = ["sgl carbon", "hexcel"]
    textile_names = ["zhejiang", "huddersfield", "somani", "lelièvre", "lelievre"]
    foam_textile_names = ["foamtex", "franklin"]

    if family == "textile_leather":
        if role in {ROLE_T4, ROLE_T3} and any(k in n for k in metal_or_mining):
            return "metal/mining supplier cannot be a textile/leather/foam upstream option"
        if role == ROLE_T2 and any(k in n for k in electronics_names):
            return "electronics/process instrumentation supplier cannot be textile/leather/foam T2"

    if family == "aluminium":
        if role == ROLE_T4 and any(k in n for k in ["saarstahl", "tata steel", "nucor", "baowu", "basf", "bayer"]):
            return "non-aluminium raw material supplier cannot be aluminium T4"
        if role == ROLE_T3 and (
            any(k in n for k in textile_names + ["aurubis", "aubert"])
            or n == "krupp"
        ):
            return "non-aluminium stockist/transformer cannot be aluminium T3"
        if role == ROLE_T2 and any(k in n for k in ["foam", "dupont", "latim", "ensinger"]):
            return "foam/textile/plastic supplier cannot be aluminium T2"

    if family == "steel":
        if role == ROLE_T4 and any(k in n for k in ["alcoa", "chalco", "hindalco", "rio tinto alma", "basf", "bayer"]):
            return "non-steel raw material supplier cannot be steel T4"
        if role == ROLE_T3 and any(k in n for k in textile_names + ["toray"]):
            return "textile/polymer supplier cannot be steel T3"
        if role == ROLE_T2 and any(k in n for k in carbon_composite + ["silicone", "plastiservice"]):
            return "carbon/composite/silicone supplier cannot be steel T2"

    if family == "copper":
        if role == ROLE_T4 and any(k in n for k in ["saarstahl", "alcoa", "chalco", "hindalco", "tata steel", "nucor", "baowu"]):
            return "non-copper raw material supplier cannot be copper T4"
        if role == ROLE_T3 and any(k in n for k in ["saarstahl", "aubert"]) or (family == "copper" and role == ROLE_T3 and n == "krupp"):
            return "steel supplier cannot be copper T3"

    if family in {"polymer_plastic", "rubber_silicone", "adhesive_composite"}:
        if role == ROLE_T4 and any(k in n for k in ["saarstahl", "tata steel", "nucor", "baowu", "chalco", "hindalco", "rio tinto", "alcoa", "zijin"]):
            return "metal/mining supplier cannot be polymer/silicone/composite T4"
        if role == ROLE_T3 and any(k in n for k in ["krupp", "aubert", "altec", "euralliage", "aluminium france", "zhejiang", "huddersfield", "aurubis"]):
            return "metal/textile supplier cannot be polymer/silicone/composite T3"
        if role == ROLE_T2 and family == "rubber_silicone" and any(k in n for k in electronics_names):
            return "electronics supplier cannot be rubber/silicone T2"

    if family == "titanium_carbon":
        if role == ROLE_T2 and any(k in n for k in ["krohne", "ensinger", "plastiforme", "plastitek"]):
            return "electronics/plastic processor cannot be titanium/carbon T2"

    return None


def apply_common_sense_secondary_filter(records: list[dict[str, Any]], changes: list[dict[str, Any]]) -> None:
    for idx, record in enumerate(records, 1):
        if record.get("simulation_supply_usable") is False:
            continue
        family = infer_record_family(record)
        kept: list[dict[str, Any]] = []
        removed = 0
        examples: list[str] = []
        for supplier in record.get("suppliers") or []:
            if not isinstance(supplier, dict):
                kept.append(supplier)
                continue
            if supplier.get("is_primary"):
                kept.append(supplier)
                continue
            role = clean(supplier.get("role_hint"))
            reason = is_obviously_incompatible_supplier(
                family,
                role,
                clean(supplier.get("name")),
                clean(supplier.get("supplier_status")),
            )
            if reason:
                excluded = copy.deepcopy(supplier)
                excluded["is_primary"] = False
                excluded["allocation_share_pct"] = 0.0
                excluded["supplier_status"] = "excluded_common_sense_material_filter"
                excluded["exclusion_reason"] = reason
                excluded["family_context"] = family
                record.setdefault("excluded_suppliers", []).append(excluded)
                removed += 1
                if len(examples) < 5:
                    examples.append(f"{supplier.get('role_hint')}:{supplier.get('name')} ({reason})")
            else:
                kept.append(supplier)
        if removed:
            record["suppliers"] = kept
            note = f"Removed {removed} impossible secondary supplier candidate(s) for family {family} using common-sense material/role filter."
            add_record_note(record, note, ["local_common_sense_material_role_filter"])
            add_change(changes, idx, "exclude_common_sense_incompatible_secondaries", note + " Examples: " + " | ".join(examples))


def apply_aggregate_exclusions(records: list[dict[str, Any]], changes: list[dict[str, Any]]) -> None:
    note = "Seat-level aluminium aggregate row excluded from active network; use detailed component rows for stress tests."
    for idx in [157, 174, 175]:
        record = records[idx - 1]
        record["simulation_supply_usable"] = False
        record["record_review_status"] = "aggregate_aluminium_mass_not_active_network"
        record["simulation_use_note"] = note
        add_record_note(record, note, ["data/quantity_material.xlsx", "https://www.mgrfoamtex.com/products-2"])
        add_change(changes, idx, "exclude_aggregate_from_active_network", note)


def set_pu_chain(
    records: list[dict[str, Any]],
    record: dict[str, Any],
    idx: int,
    changes: list[dict[str, Any]],
    *,
    t1_name: str,
    t2_owner: str,
    t2_label: str,
    t1_transport_modes: list[str],
    t1_transport_original: list[str],
    note: str,
) -> None:
    set_primary(
        records,
        record,
        idx,
        changes,
        role=ROLE_T4,
        name="BASF - PU chemistry source candidate",
        template_name="BASF",
        status="baseline_primary_assumed_material_source_requires_grade_certificate",
        description="PU chemistry / flame-retardant foam chemistry candidate",
        note=note,
        simulation_node_type="material_source_candidate",
        stress_test_switchable=False,
    )
    t1_template = find_template(records, t1_name, ROLE_T1) or find_template(records, t2_owner, None)
    set_primary(
        records,
        record,
        idx,
        changes,
        role=ROLE_T3,
        name=f"{t2_owner} - FRMC55 certified foam/fabric sourcing package",
        template_name=t2_owner,
        status="baseline_primary_assumed_material_package_requires_bom",
        description="Virtual foam/fabric material package; exact foam mill and grade to validate",
        location=(t1_template or {}).get("location"),
        lat=(t1_template or {}).get("lat"),
        lon=(t1_template or {}).get("lon"),
        note=note,
        simulation_node_type="virtual_process_or_market_basket",
        stress_test_switchable=False,
    )
    set_primary(
        records,
        record,
        idx,
        changes,
        role=ROLE_T1,
        name=t1_name,
        template_name=t1_name,
        status="baseline_primary_lca_exact_supplier",
        location=(t1_template or {}).get("location"),
        lat=(t1_template or {}).get("lat"),
        lon=(t1_template or {}).get("lon"),
        note=note,
    )
    set_internal_process(
        records,
        record,
        idx,
        changes,
        owner_name=t2_owner,
        owner_template=t1_name if t1_name == t2_owner else t2_owner,
        process_label=t2_label,
        note=note,
        description="FRMC55 foam cutting/gluing/integration process",
    )
    set_transport(record, "from_supplier_to_safran", t1_transport_modes, t1_transport_original, note)
    add_record_note(record, note, ["data/quantity_material.xlsx", "https://aerospace.basf.com/seating-components.html"])


def apply_frmc55_corrections(records: list[dict[str, Any]], changes: list[dict[str, Any]]) -> None:
    note_franklin = "FRMC55 is PU flexible foam in LCA/BOM; steel upstream removed and FRANKLIN supplier/process used."
    for idx in [86, 87, 88, 89, 90]:
        set_pu_chain(
            records,
            records[idx - 1],
            idx,
            changes,
            t1_name="FRANKLIN",
            t2_owner="FRANKLIN",
            t2_label="internal cutting/gluing process",
            t1_transport_modes=["truck", "air"],
            t1_transport_original=["Camion", "Avion"],
            note=note_franklin,
        )
        add_lane_scenarios(
            records[idx - 1],
            [
                {
                    "scenario_id": "baseline_acv_air_truck",
                    "edge": "T1->OEM",
                    "modes": ["truck", "air", "truck"],
                    "source": "data/quantity_material.xlsx",
                    "status": "baseline_for_acv_record",
                }
            ],
        )

    note_mga = "FRMC55 small material line embedded in MGA stowage assembly per LCA/BOM; steel upstream removed."
    set_pu_chain(
        records,
        records[91 - 1],
        91,
        changes,
        t1_name="MGA Villeneuve St Lot",
        t2_owner="MGA Villeneuve St Lot",
        t2_label="internal FRMC55 integration process",
        t1_transport_modes=["truck"],
        t1_transport_original=["Camion"],
        note=note_mga,
    )

    note_mgr = "FRMC55 manchette rows point to MGR Angleterre in LCA/BOM; steel upstream removed and MGR foam/interior path used."
    for idx in [92, 93]:
        set_pu_chain(
            records,
            records[idx - 1],
            idx,
            changes,
            t1_name="MGR Foamtex Ltd",
            t2_owner="MGR Foamtex Ltd",
            t2_label="internal foam/upholstery process",
            t1_transport_modes=["rail", "truck"],
            t1_transport_original=["Train", "Camion"],
            note=note_mgr,
        )
        add_record_note(records[idx - 1], note_mgr, ["data/quantity_material.xlsx", "https://www.mgrfoamtex.com/products-2"])


def apply_electronics_placeholders(records: list[dict[str, Any]], changes: list[dict[str, Any]]) -> None:
    groups = {
        10: "Thales",
        71: "TE Connectivity",
        73: "Thales",
        74: "Liebherr Aerospace",
        78: "Thales",
        121: "Thales",
        126: "Thales",
        153: "Thales",
    }
    note = "COTS/electronics upstream cannot be inferred without BOM, PN, EMS/ODM and AVL; use non-switchable placeholders."
    for idx, owner in groups.items():
        record = records[idx - 1]
        owner_template = find_template(records, owner, ROLE_T1) or find_template(records, owner, None)
        lat = (owner_template or {}).get("lat")
        lon = (owner_template or {}).get("lon")
        location = (owner_template or {}).get("location")
        set_primary(
            records,
            record,
            idx,
            changes,
            role=ROLE_T4,
            name=f"{owner} - COTS electronics component market basket",
            template_name=owner,
            status="baseline_primary_non_switchable_cots_placeholder",
            description="Virtual COTS component basket; upstream hidden until BOM/PN/AVL is known",
            location=location,
            lat=lat,
            lon=lon,
            note=note,
            simulation_node_type="virtual_process_or_market_basket",
            stress_test_switchable=False,
        )
        set_primary(
            records,
            record,
            idx,
            changes,
            role=ROLE_T3,
            name=f"{owner} - COTS electronics subassembly/PCB package",
            template_name=owner,
            status="baseline_primary_non_switchable_cots_placeholder",
            description="Virtual COTS electronics subassembly package; requires BOM/PN/AVL",
            location=location,
            lat=lat,
            lon=lon,
            note=note,
            simulation_node_type="virtual_process_or_market_basket",
            stress_test_switchable=False,
        )
        if owner in {"Liebherr Aerospace", "TE Connectivity"}:
            set_internal_process(
                records,
                record,
                idx,
                changes,
                owner_name=owner,
                process_label="electronics routing/EMS package",
                note=note,
                description="Electronics routing/EMS package under T1 responsibility",
            )
            set_primary(
                records,
                record,
                idx,
                changes,
                role=ROLE_T1,
                name=owner,
                template_name=owner,
                status="baseline_primary_lca_or_program_supplier",
                note=note,
            )
        set_transport(record, "from_supplier_to_safran", ["truck"], ["Camion"], "European T1/OEM lane; upstream COTS not geographically expanded.")
        add_record_note(record, note, ["https://www.te.com/en/products/brands/deutsch.html?cat=1", "https://www.liebherr.com/en-int/aerospace-and-transportation-systems/solutions-and-services/solutions-for-aerospace/on-board-systems/on-board-systems-7174957"])


def apply_z10cnt18_correction(records: list[dict[str, Any]], changes: list[dict[str, Any]]) -> None:
    idx = 151
    note = "Z10CNT18 is steel/inox; SGL Carbon removed as T2 and MGA internal process used."
    record = records[idx - 1]
    set_primary(
        records,
        record,
        idx,
        changes,
        role=ROLE_T1,
        name="MGA Villeneuve St Lot",
        template_name="MGA Villeneuve St Lot",
        status="baseline_primary_lca_exact_supplier",
        note=note,
    )
    set_internal_process(records, record, idx, changes, owner_name="MGA Villeneuve St Lot", note=note)
    set_transport(record, "from_supplier_to_safran", ["truck"], ["Camion"], "France T1 to Safran truck baseline.")
    add_record_note(record, note, ["data/quantity_material.xlsx", "https://www.lafrenchfab.fr/entreprise/mga-groupe-arm/"])


def apply_mixed_metal_split(records: list[dict[str, Any]], changes: list[dict[str, Any]]) -> None:
    note = (
        "Mixed process label split analytically: active quantitative material flow follows LCA/BOM material_match=acier; "
        "aluminium cast machining remains a process reference, not a separate aluminium mass flow."
    )
    for idx in [50, 154, 155]:
        record = records[idx - 1]
        record["component_family_override"] = "steel"
        record["raw_materials"] = ["Steel"]
        record["raw_materials_status"] = "lca_material_match_overrides_mixed_process_label"
        record["split_material_subflows"] = [
            {
                "subflow_id": f"R{idx:03d}-steel-active",
                "family": "steel",
                "status": "active_quantitative_material_flow",
                "mass_kg": record.get("mass_kg"),
                "mass_source": "quantity_material.xlsx",
                "lca_material_match": "acier",
                "industrial_process": "steel sheet stamping/bending or tinplated steel machining as labelled",
            },
            {
                "subflow_id": f"R{idx:03d}-aluminium-process-ref",
                "family": "aluminium",
                "status": "process_reference_only_no_separate_mass_in_this_record",
                "mass_kg": None,
                "industrial_process": "aluminium cast part machining",
                "simulation_action": "do not create a separate aluminium supply path until BOM gives an aluminium mass allocation",
            },
        ]
        set_primary(
            records,
            record,
            idx,
            changes,
            role=ROLE_T4,
            name="ArcelorMittal",
            template_name="ArcelorMittal",
            status="baseline_primary_assumed_steel_source_requires_certificate",
            description="Steel source candidate for steel/tinplated sheet flow",
            note=note,
            simulation_node_type="material_source_candidate",
            stress_test_switchable=False,
        )
        set_primary(
            records,
            record,
            idx,
            changes,
            role=ROLE_T3,
            name="thyssenkrupp Materials France",
            template_name="thyssenkrupp Materials France",
            status="baseline_primary_assumed_steel_stockist_requires_certificate",
            description="Steel stockist/distributor candidate for sheet/stamping flow",
            note=note,
            simulation_node_type="physical_supplier_site",
            stress_test_switchable=False,
        )
        set_primary(
            records,
            record,
            idx,
            changes,
            role=ROLE_T1,
            name="SUMPAR",
            template_name="SUMPAR",
            status="baseline_primary_lca_exact_supplier",
            note=note,
        )
        set_internal_process(records, record, idx, changes, owner_name="SUMPAR", note=note)
        set_transport(record, "from_supplier_to_safran", ["truck"], ["Camion"], "SUMPAR France to Safran truck baseline for steel flow.")
        add_record_note(record, note, ["data/quantity_material.xlsx"])
        add_change(changes, idx, "split_mixed_metal_to_active_steel_flow", note)


def apply_longhaul_transport(records: list[dict[str, Any]], changes: list[dict[str, Any]]) -> None:
    senior = [33, 51, 81, 94, 95, 96, 98, 99, 100, 101, 102, 138]
    for idx in senior:
        record = records[idx - 1]
        set_transport(record, "from_supplier_to_safran", ["truck", "air"], ["Camion", "Avion"], "Thailand to France cannot be truck-only; ACV/Senior rows use air+truck baseline.")
        add_lane_scenarios(
            record,
            [
                {
                    "scenario_id": "baseline_acv_air_truck",
                    "edge": "T1->OEM",
                    "modes": ["truck", "air", "truck"],
                    "status": "baseline_for_acv_record_or_expedite",
                },
                {
                    "scenario_id": "cost_co2_sea_truck_candidate",
                    "edge": "T1->OEM",
                    "modes": ["truck", "ship", "truck"],
                    "status": "scenario_candidate_requires_lane_validation",
                },
            ],
        )
        add_record_note(record, "Thailand to France transport corrected from truck-only.", ["data/quantity_material.xlsx", "https://www.senior-thailand.com/Web/what_we_do"])
        add_change(changes, idx, "fix_longhaul_transport", "Senior Aerospace Thailand T1->OEM truck-only replaced with air+truck baseline and sea scenario.")

    jamco = [75, 128, 161, 162, 164, 165, 166]
    for idx in jamco:
        record = records[idx - 1]
        set_transport(record, "from_supplier_to_safran", ["truck", "ship"], ["Camion", "Bateau"], "Japan/Philippines to France cannot be truck-only; sea+truck baseline with air expedite scenario.")
        add_lane_scenarios(
            record,
            [
                {
                    "scenario_id": "baseline_bulky_interiors_sea_truck",
                    "edge": "T1->OEM",
                    "modes": ["truck", "ship", "truck"],
                    "status": "geography_based_baseline_requires_freight_validation",
                },
                {
                    "scenario_id": "expedite_air_truck_candidate",
                    "edge": "T1->OEM",
                    "modes": ["truck", "air", "truck"],
                    "status": "scenario_candidate_requires_lane_validation",
                },
            ],
        )
        add_record_note(record, "JAMCO/Japan longhaul transport corrected from truck-only.", ["https://jamcointeriors.com/"])
        add_change(changes, idx, "fix_longhaul_transport", "JAMCO T1->OEM truck-only replaced with sea+truck baseline and air expedite scenario.")


def apply_residual_material_transport(records: list[dict[str, Any]], changes: list[dict[str, Any]]) -> None:
    intercontinental_t4_t3 = {
        17: "Alcoa US to AMAG Austria cannot be truck-only.",
        25: "Alcoa US to AMAG Austria cannot be truck-only.",
        66: "Chalco China to Euralliage France cannot be truck-only.",
        79: "Mitsubishi Chemical/Toray/Ensinger polymer route needs intercontinental sea/air scenario, not truck-only.",
        167: "Alcoa US to AMAG Austria cannot be truck-only.",
    }
    for idx, note in intercontinental_t4_t3.items():
        record = records[idx - 1]
        set_transport(record, "to_first_transformation", ["truck", "ship", "rail"], ["Camion", "Bateau", "Train"], note)
        add_lane_scenarios(
            record,
            [
                {
                    "scenario_id": "material_longhaul_sea_rail_truck",
                    "edge": "T4->T3",
                    "modes": ["truck", "ship", "rail", "truck"],
                    "status": "geography_based_material_lane_requires_certificate_and_freight_validation",
                },
                {
                    "scenario_id": "material_longhaul_air_expedite_candidate",
                    "edge": "T4->T3",
                    "modes": ["truck", "air", "truck"],
                    "status": "scenario_candidate_requires_lane_validation",
                },
            ],
        )
        add_record_note(record, note, ["data/quantity_material.xlsx"])
        add_change(changes, idx, "fix_material_longhaul_transport", note)


def first_primary(record: dict[str, Any], role: str) -> dict[str, Any] | None:
    if role == "oem":
        entries = record.get("oem_sites") or []
    else:
        entries = [s for s in record.get("suppliers") or [] if isinstance(s, dict) and s.get("role_hint") == role]
    for entry in entries:
        if isinstance(entry, dict) and entry.get("is_primary"):
            return entry
    return entries[0] if entries else None


def inferred_modes_for_distance(distance_km: float | None, *, internal: bool = False) -> list[str]:
    if internal or (distance_km is not None and distance_km <= 2):
        return ["internal"]
    if distance_km is None:
        return ["truck"]
    if distance_km <= 1200:
        return ["truck"]
    if distance_km <= 3500:
        return ["truck", "rail"]
    return ["truck", "ship"]


def add_primary_lane_transport_scenarios(records: list[dict[str, Any]], changes: list[dict[str, Any]]) -> None:
    role_sequence = [
        ("T4", ROLE_T4),
        ("T3", ROLE_T3),
        ("T2", ROLE_T2),
        ("T1", ROLE_T1),
        ("OEM", "oem"),
    ]
    for idx, record in enumerate(records, 1):
        if record.get("simulation_supply_usable") is False:
            continue
        primaries = [(code, first_primary(record, role)) for code, role in role_sequence]
        if any(node is None for _, node in primaries):
            continue
        added = 0
        for (left_code, left), (right_code, right) in zip(primaries, primaries[1:]):
            if left is None or right is None:
                continue
            edge = f"{left_code}->{right_code}"
            if has_edge_scenario(record, edge):
                continue
            distance = haversine_km(left, right)
            t2_internal = edge == "T2->T1" and (
                "internal" in clean(left.get("supplier_status")).lower()
                or clean(right.get("name")).lower() in clean(left.get("name")).lower()
            )
            modes = inferred_modes_for_distance(distance, internal=t2_internal)
            add_lane_scenarios(
                record,
                [
                    {
                        "scenario_id": f"baseline_primary_lane_{left_code.lower()}_{right_code.lower()}",
                        "edge": edge,
                        "from": clean(left.get("name")),
                        "to": clean(right.get("name")),
                        "distance_km_haversine": None if distance is None else round(distance, 1),
                        "modes": modes,
                        "source": "geography_inference_from_site_coordinates",
                        "status": "baseline_primary_lane_inferred_requires_freight_validation",
                    }
                ],
            )
            added += 1
        if added:
            add_change(changes, idx, "add_primary_lane_transport_scenarios", f"added {added} primary edge transport scenarios")


def write_changes(changes: list[dict[str, Any]]) -> None:
    with CHANGES_CSV.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["record_index", "action", "detail"])
        writer.writeheader()
        writer.writerows(changes)


def write_report(changes: list[dict[str, Any]]) -> None:
    counts: dict[str, int] = {}
    for row in changes:
        counts[row["action"]] = counts.get(row["action"], 0) + 1
    lines = [
        "# Corrections researched simulation-ready",
        "",
        f"- Input: `{INPUT_JSON.as_posix()}`",
        f"- Output JSON: `{OUTPUT_JSON.as_posix()}`",
        f"- Change log: `{CHANGES_CSV.as_posix()}`",
        f"- Generated at: `{dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()}`",
        "",
        "## Actions",
        "",
    ]
    for key in sorted(counts):
        lines.append(f"- `{key}`: {counts[key]}")
    lines.extend(
        [
            "",
            "## Main rules applied",
            "",
            "- Combigo is no longer active as aluminium T2 on A2017/A2024 paths.",
            "- Combigo is removed from secondary switch scenarios, not only demoted from primary paths.",
            "- FRMC55 paths no longer use steel upstream; they use PU foam/material packages tied to LCA suppliers.",
            "- COTS/electronics upstream tiers are explicit non-switchable placeholders until BOM/PN/AVL is available.",
            "- Mixed metal process labels 50/154/155 are split analytically: active steel material flow plus aluminium process reference without duplicated mass.",
            "- Obvious material/role-incompatible secondary candidates are excluded from switch scenarios rather than kept as blocked cartesian combinations.",
            "- Aggregate seat aluminium rows 157, 174 and 175 are excluded from the active mapped network.",
            "- Thailand/Japan longhaul lanes no longer use truck-only T1->OEM transport.",
        ]
    )
    REPORT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    data = json.loads(INPUT_JSON.read_text(encoding="utf-8"))
    records = data.get("records") or []
    changes: list[dict[str, Any]] = []

    apply_aluminium_lca_routes(records, changes)
    apply_secondary_candidate_cleanup(records, changes)
    apply_aggregate_exclusions(records, changes)
    apply_frmc55_corrections(records, changes)
    apply_electronics_placeholders(records, changes)
    apply_z10cnt18_correction(records, changes)
    apply_mixed_metal_split(records, changes)
    apply_longhaul_transport(records, changes)
    apply_residual_material_transport(records, changes)
    apply_common_sense_secondary_filter(records, changes)
    add_primary_lane_transport_scenarios(records, changes)

    meta = data.setdefault("_meta", {})
    meta["simulation_ready_researched"] = {
        "generated_at": dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat(),
        "source_file": INPUT_JSON.name,
        "change_log": CHANGES_CSV.name,
        "policy": "researched corrections for plausible simulation topology; procurement truth still requires BOM, PN, routing and certificates",
    }

    OUTPUT_JSON.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    write_changes(changes)
    write_report(changes)
    print(f"Wrote {OUTPUT_JSON}")
    print(f"Wrote {CHANGES_CSV}")
    print(f"Wrote {REPORT_MD}")
    print(f"Changes: {len(changes)}")


if __name__ == "__main__":
    main()
