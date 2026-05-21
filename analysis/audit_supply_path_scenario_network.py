#!/usr/bin/env python3
"""Audit all tiered supply paths from T4 to OEM for simulation readiness.

This script treats every supplier candidate in a tier as a possible scenario node,
then builds the cartesian product T4 -> T3 -> T2 -> T1 -> OEM per component.
The goal is not to certify procurement truth. It flags which paths are usable as
simulation topology, which need sourcing evidence, and which are materially
incoherent.
"""

from __future__ import annotations

import csv
import datetime as dt
import argparse
import itertools
import json
import math
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


BASE_DIR = Path(__file__).resolve().parent
INPUT_JSON = BASE_DIR / "output8_GEO_normalized_final_primary_complete_lca_marked.json"
PATHS_CSV = BASE_DIR / "output8_GEO_supply_path_network_full_paths.csv"
COMPONENT_CSV = BASE_DIR / "output8_GEO_supply_path_network_component_summary.csv"
ISSUES_CSV = BASE_DIR / "output8_GEO_supply_path_network_issues.csv"
LANES_CSV = BASE_DIR / "output8_GEO_supply_path_network_transport_lanes.csv"
NODES_CSV = BASE_DIR / "output8_GEO_supply_path_network_node_quality.csv"
REPORT_MD = BASE_DIR / "output8_GEO_supply_path_network_audit_report.md"

ROLES = [
    ("T4", "tier4_raw_material"),
    ("T3", "tier3_first_transformation"),
    ("T2", "tier2_second_transformation"),
    ("T1", "tier1"),
    ("OEM", "oem"),
]

SEVERITY_RANK = {"INFO": 0, "LOW": 1, "MEDIUM": 2, "HIGH": 3, "BLOCKER": 4}


def configure_output_prefix(prefix: str) -> None:
    global PATHS_CSV, COMPONENT_CSV, ISSUES_CSV, LANES_CSV, NODES_CSV, REPORT_MD
    PATHS_CSV = BASE_DIR / f"{prefix}_full_paths.csv"
    COMPONENT_CSV = BASE_DIR / f"{prefix}_component_summary.csv"
    ISSUES_CSV = BASE_DIR / f"{prefix}_issues.csv"
    LANES_CSV = BASE_DIR / f"{prefix}_transport_lanes.csv"
    NODES_CSV = BASE_DIR / f"{prefix}_node_quality.csv"
    REPORT_MD = BASE_DIR / f"{prefix}_audit_report.md"

FAMILY_BAD_KEYWORDS: dict[str, dict[str, list[str]]] = {
    "aluminium": {
        "T4": ["basf", "bayer", "saarstahl", "tata steel", "nucor", "baowu"],
        "T3": ["zhejiang", "toray", "huddersfield", "aurubis", "aubert", "krupp"],
        "T2": ["foam", "dupont", "latim", "ensinger", "combigo"],
    },
    "steel": {
        "T4": ["alcoa", "chalco", "hindalco", "rio tinto alma", "basf", "bayer"],
        "T3": ["toray", "zhejiang", "huddersfield"],
        "T2": ["sgl carbon", "hexcel", "silicone", "plastiservice"],
    },
    "copper": {
        "T4": ["saarstahl", "alcoa", "chalco", "hindalco", "tata steel", "nucor", "baowu"],
        "T3": ["saarstahl", "aubert", "krupp"],
        "T2": ["foam", "textile", "silicone"],
    },
    "polymer_plastic": {
        "T4": ["saarstahl", "tata steel", "nucor", "baowu", "chalco", "hindalco", "rio tinto"],
        "T3": ["krupp", "aubert", "altec", "euralliage", "aluminium france", "zhejiang", "huddersfield"],
        "T2": ["schroth safety"],
    },
    "textile_leather": {
        "T4": ["zijin", "aurubis", "saarstahl", "tata steel", "nucor", "baowu", "alcoa", "chalco"],
        "T3": ["aurubis", "ampco", "thyssenkrupp", "aubert", "krupp", "euralliage"],
        "T2": ["krohne", "vaisala", "auberon", "innoptec"],
    },
    "rubber_silicone": {
        "T4": ["saarstahl", "alcoa", "chalco", "tata steel", "nucor", "baowu", "aurubis"],
        "T3": ["aubert", "krupp", "euralliage"],
        "T2": ["krohne", "vaisala", "auberon", "innoptec"],
    },
    "electronics_cots": {
        "T4": ["saarstahl"],
    },
    "titanium_carbon": {
        "T4": ["basf", "alcoa", "chalco", "saarstahl", "nucor", "baowu"],
        "T2": ["krohne", "ensinger", "plastiforme", "plastitek"],
    },
}


def clean(value: Any) -> str:
    return str(value or "").strip()


def low(value: Any) -> str:
    return clean(value).lower()


def has_coords(entry: dict[str, Any]) -> bool:
    return entry.get("lat") not in (None, "") and entry.get("lon") not in (None, "")


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
    r = 6371.0088
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    h = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlambda / 2) ** 2
    return 2 * r * math.asin(math.sqrt(h))


def component_family(record: dict[str, Any]) -> str:
    override = clean(record.get("component_family_override"))
    if override:
        return override
    component_label = low(record.get("component"))
    mass_match = low(record.get("mass_material_match"))
    component_text = component_label + " " + mass_match
    raw_text = " ".join(low(x) for x in record.get("raw_materials") or [])

    if any(k in component_label for k in ["display", "powerbox", "ife", "ecu", "clavier", "lightning", "screen", "electronic"]):
        return "electronics_cots"
    has_label_aluminium = any(k in component_label for k in ["a5086", "a6060", "a2017", "a2024", "aluminium", " alu"])
    has_label_steel = any(k in component_label for k in ["acier", "steel", "inox", "35nc6", "30ncd6", "15cdv6", "4140", "z10cnt"])
    if has_label_aluminium and has_label_steel:
        return "mixed_metal"
    if any(k in component_label for k in ["acier", "steel", "inox", "35nc6", "30ncd6", "15cdv6", "4140", "z10cnt"]):
        return "steel"
    if any(k in component_label for k in ["a5086", "a6060", "a2017", "a2024", "aluminium", " alu"]):
        return "aluminium"
    if any(k in component_label for k in ["cuivre", "copper", "alliage cu"]):
        return "copper"
    if any(k in component_label for k in ["frmc55", "polyurethane", "polyuréthane", "mousse", "tissu", "velours", "velcro", "cuir", "textile", "leather", "nylon"]):
        return "textile_leather"
    if "silicone" in component_label:
        return "rubber_silicone"
    if any(k in component_label for k in ["lexan", "kydex", "ertalon", "nida", "poly", "plastique", "plastic"]):
        return "polymer_plastic"
    if any(k in component_label for k in ["resine", "résine", "film", "adhes", "aerfilm"]):
        return "adhesive_composite"
    if any(k in component_label for k in ["titane", "titanium", "carbone", "carbon"]):
        return "titanium_carbon"

    if any(k in mass_match for k in ["display", "powerbox", "ife", "ecu", "clavier", "lightning", "screen display"]):
        return "electronics_cots"
    if any(k in mass_match for k in ["acier", "steel", "inox", "35nc6", "30ncd6", "15cdv6", "4140", "z10cnt"]):
        return "steel"
    if any(k in mass_match for k in ["a5086", "a6060", "a2017", "a2024", "aluminium", " alu"]):
        return "aluminium"
    if any(k in mass_match for k in ["cuivre", "copper", "alliage cu"]):
        return "copper"
    if any(k in mass_match for k in ["frmc55", "polyurethane", "polyuréthane", "mousse", "tissu", "velours", "velcro", "cuir", "textile", "leather", "nylon"]):
        return "textile_leather"
    if "silicone" in mass_match:
        return "rubber_silicone"
    if any(k in mass_match for k in ["lexan", "kydex", "ertalon", "nida", "poly", "plastique", "plastic"]):
        return "polymer_plastic"
    if any(k in mass_match for k in ["resine", "résine", "film", "adhes", "aerfilm", "composite"]):
        return "adhesive_composite"
    if any(k in mass_match for k in ["titane", "titanium", "carbone", "carbon"]):
        return "titanium_carbon"

    if any(k in raw_text for k in ["tissus", "textile", "nylon", "polyurethane foam", "polyamide"]):
        return "textile_leather"
    if any(k in raw_text for k in ["a5086", "a6060", "a2017", "a2024", "aluminium", " alu"]):
        return "aluminium"
    if any(k in raw_text for k in ["cuivre", "copper", "alliage cu"]):
        return "copper"
    if any(k in raw_text for k in ["acier", "steel", "inox", "35nc6", "30ncd6", "15cdv6", "4140"]):
        return "steel"
    if "silicone" in raw_text:
        return "rubber_silicone"
    if any(k in raw_text for k in ["lexan", "kydex", "ertalon", "nida", "poly", "plastique", "plastic"]):
        return "polymer_plastic"
    if any(k in raw_text for k in ["resine", "résine", "film", "adhes", "aerfilm"]):
        return "adhesive_composite"
    if any(k in raw_text for k in ["titane", "titanium", "carbone", "carbon"]):
        return "titanium_carbon"
    return "general"


def nodes_by_role(record: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    out: dict[str, list[dict[str, Any]]] = {}
    suppliers = [s for s in record.get("suppliers") or [] if isinstance(s, dict)]
    for code, role in ROLES:
        if role == "oem":
            out[code] = [s for s in record.get("oem_sites") or [] if isinstance(s, dict)]
        else:
            out[code] = [s for s in suppliers if s.get("role_hint") == role]
    return out


def primary_nodes(nodes: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    return [entries[0] if entries else {} for entries in ([n for n in nodes[c] if n.get("is_primary")] for c, _ in ROLES)]


def mode_set(record: dict[str, Any], segment: str) -> set[str]:
    transport = record.get("transport") or {}
    raw = transport.get(segment) if isinstance(transport, dict) else {}
    modes = raw.get("modes") if isinstance(raw, dict) else []
    return {low(m) for m in modes if clean(m)}


def mode_text(modes: set[str]) -> str:
    return "|".join(sorted(modes))


def transport_scenario_modes(record: dict[str, Any], edge: str, src: dict[str, Any], dst: dict[str, Any]) -> set[str]:
    scenarios = [s for s in record.get("transport_scenarios") or [] if isinstance(s, dict) and s.get("edge") == edge]
    if not scenarios:
        return set()
    exact: list[dict[str, Any]] = []
    src_name = node_label(src)
    dst_name = node_label(dst)
    src_id = clean(src.get("supplier_id"))
    dst_id = clean(dst.get("supplier_id"))
    for scenario in scenarios:
        scenario_from = clean(scenario.get("from"))
        scenario_to = clean(scenario.get("to"))
        scenario_from_id = clean(scenario.get("from_supplier_id"))
        scenario_to_id = clean(scenario.get("to_supplier_id"))
        if scenario_from or scenario_to or scenario_from_id or scenario_to_id:
            from_ok = scenario_from == src_name or (scenario_from_id and scenario_from_id == src_id)
            to_ok = scenario_to == dst_name or (scenario_to_id and scenario_to_id == dst_id)
            if from_ok and to_ok:
                exact.append(scenario)
    if exact:
        scenarios = exact
    else:
        scenarios = [
            scenario
            for scenario in scenarios
            if not clean(scenario.get("from"))
            and not clean(scenario.get("to"))
            and not clean(scenario.get("from_supplier_id"))
            and not clean(scenario.get("to_supplier_id"))
        ]
        if not scenarios:
            return set()
    scenarios.sort(
        key=lambda s: (
            0 if "baseline" in low(s.get("scenario_id")) or "baseline" in low(s.get("status")) else 1,
            clean(s.get("scenario_id")),
        )
    )
    modes = scenarios[0].get("modes") or []
    return {low(mode) for mode in modes if clean(mode)}


def node_id(entry: dict[str, Any]) -> str:
    sid = clean(entry.get("supplier_id")) or clean(entry.get("name")).lower().replace(" ", "_")
    site = clean(entry.get("site_id"))
    return f"{sid}@@{site}" if site else sid


def node_label(entry: dict[str, Any]) -> str:
    return clean(entry.get("name"))


def status(entry: dict[str, Any]) -> str:
    return clean(entry.get("supplier_status") or entry.get("geocode_status"))


def is_assumed(entry: dict[str, Any]) -> bool:
    s = status(entry).lower()
    return "assumed" in s or bool(entry.get("baseline_completion_assumption"))


def is_inactive_candidate(entry: dict[str, Any]) -> bool:
    s = status(entry).lower()
    return "alternate" in s or "requires_allocation" in s


def is_internalized_t2(t2: dict[str, Any], t1: dict[str, Any]) -> bool:
    text = low(t2.get("name")) + " " + low(t2.get("supplier_status")) + " " + low(t2.get("simulation_node_type"))
    t1_name = low(t1.get("name"))
    return "internal" in text or (t1_name and t1_name in low(t2.get("name")))


def source_quality(entry: dict[str, Any]) -> str:
    conf = low(entry.get("source_confidence") or entry.get("site_selection_confidence"))
    geo = low(entry.get("geocode_status"))
    if "source_backed" in geo or conf in {"high", "medium_high"}:
        return "source_backed_or_medium_high"
    if "fallback" in geo or "centroid" in geo or "unresolved" in geo:
        return "fallback_or_centroid"
    if conf in {"low", "medium_low"}:
        return "low_confidence"
    return "unknown_or_legacy"


def material_node_issues(family: str, code: str, entry: dict[str, Any]) -> list[dict[str, str]]:
    name = low(entry.get("name"))
    issues: list[dict[str, str]] = []
    for bad in FAMILY_BAD_KEYWORDS.get(family, {}).get(code, []):
        if bad == "krupp" and family in {"aluminium", "copper"} and "thyssenkrupp materials france" in name:
            continue
        if bad in name:
            issues.append(
                {
                    "severity": "BLOCKER",
                    "issue_code": "supplier_material_family_incompatible",
                    "message": f"{code} '{node_label(entry)}' is incompatible with family {family}.",
                    "recommended_action": "Remove from this component scenario set or reclassify with evidence.",
                }
            )
            break

    if family == "electronics_cots" and code in {"T4", "T3"}:
        if "cots electronics" not in name and "non_switchable_cots" not in low(status(entry)):
            issues.append(
                {
                    "severity": "HIGH",
                    "issue_code": "electronics_upstream_requires_bom",
                    "message": f"{code} '{node_label(entry)}' cannot be activated for COTS electronics without BOM or part number.",
                    "recommended_action": "Keep inactive until BOM, part number, EMS/ODM and AVL are known.",
                }
            )

    if "requires_certificate" in low(entry.get("geocode_status")) or "assumed_material_certificate" in low(status(entry)):
        issues.append(
            {
                "severity": "MEDIUM",
                "issue_code": "material_certificate_required",
                "message": f"{code} '{node_label(entry)}' is a candidate that requires a material certificate or mill evidence.",
                "recommended_action": "Require certificate, grade, site and allocation before using as active supply.",
            }
        )
    return issues


def component_model_issues(family: str) -> list[dict[str, str]]:
    if family == "mixed_metal":
        return [
            {
                "severity": "MEDIUM",
                "issue_code": "mixed_material_component_should_split",
                "message": "Component mixes aluminium and steel process/material references in one supply path.",
                "recommended_action": "Split into separate aluminium and steel sub-paths before quantitative transport or disruption simulation.",
            }
        ]
    return []


def node_generic_issues(code: str, entry: dict[str, Any]) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    if not has_coords(entry):
        issues.append(
            {
                "severity": "BLOCKER",
                "issue_code": "node_missing_coordinates",
                "message": f"{code} '{node_label(entry)}' has no coordinates.",
                "recommended_action": "Add a site-level geolocation or exclude from mapped scenarios.",
            }
        )
    q = source_quality(entry)
    if q == "fallback_or_centroid":
        issues.append(
            {
                "severity": "HIGH",
                "issue_code": "site_is_fallback_or_centroid",
                "message": f"{code} '{node_label(entry)}' still uses a fallback/centroid-like site.",
                "recommended_action": "Replace with an industrial site before distance/transport stress tests.",
            }
        )
    elif q == "low_confidence":
        issues.append(
            {
                "severity": "MEDIUM",
                "issue_code": "site_low_confidence",
                "message": f"{code} '{node_label(entry)}' has low site confidence.",
                "recommended_action": "Validate site address/source before using as active scenario.",
            }
        )
    if is_inactive_candidate(entry):
        issues.append(
            {
                "severity": "MEDIUM",
                "issue_code": "inactive_alternate_requires_allocation",
                "message": f"{code} '{node_label(entry)}' is an alternate/candidate with no active allocation.",
                "recommended_action": "Use only as a switch scenario after allocation, qualification and lead time validation.",
            }
        )
    if is_assumed(entry):
        issues.append(
            {
                "severity": "MEDIUM",
                "issue_code": "baseline_node_is_assumption",
                "message": f"{code} '{node_label(entry)}' is an inferred or virtual baseline node.",
                "recommended_action": "Keep visible as modeled assumption; do not treat as verified procurement truth.",
            }
        )
    return issues


def lca_issues(record: dict[str, Any]) -> list[dict[str, str]]:
    lca = record.get("lca_traceability") or {}
    issues: list[dict[str, str]] = []
    if not lca.get("has_lca_mass"):
        issues.append(
            {
                "severity": "BLOCKER",
                "issue_code": "missing_lca_mass",
                "message": "No LCA/BOM mass is attached to this component.",
                "recommended_action": "Link to quantity_material.xlsx or exclude from quantitative stress tests.",
            }
        )
        return issues
    use_class = clean(lca.get("simulation_use_class"))
    if use_class == "scenario_only_review_required":
        issues.append(
            {
                "severity": "HIGH",
                "issue_code": "lca_mass_low_confidence",
                "message": "LCA mass is a weak fallback and should not drive quantitative stress tests without review.",
                "recommended_action": "Validate mass against BOM/drawing or rerun allocation with exact material match.",
            }
        )
    elif use_class == "usable_with_review":
        issues.append(
            {
                "severity": "MEDIUM",
                "issue_code": "lca_mass_requires_review",
                "message": "LCA mass is usable for sizing but needs review before high-stakes simulation.",
                "recommended_action": "Validate material/equipment match before final scenario calibration.",
            }
        )
    if clean(record.get("raw_materials_status")) == "missing_source":
        issues.append(
            {
                "severity": "MEDIUM",
                "issue_code": "raw_material_source_missing",
                "message": "Raw material was not directly sourced in the JSON.",
                "recommended_action": "Confirm raw material family from BOM, drawing or material certificate.",
            }
        )
    return issues


def edge_audit(
    record: dict[str, Any],
    code_from: str,
    code_to: str,
    src: dict[str, Any],
    dst: dict[str, Any],
    *,
    t2_internal: bool = False,
    path_primary: bool = False,
) -> dict[str, Any]:
    edge = f"{code_from}->{code_to}"
    dist = haversine_km(src, dst)
    explicit_segment = ""
    modes: set[str] = set()
    model_status = "missing_explicit_lane_mode"

    scenario_modes = transport_scenario_modes(record, edge, src, dst)
    if scenario_modes:
        explicit_segment = "transport_scenarios"
        modes = scenario_modes
        model_status = "lane_specific_scenario"
    elif edge == "T4->T3":
        explicit_segment = "to_first_transformation"
        modes = mode_set(record, explicit_segment)
        model_status = "generic_phase_mode"
    elif edge == "T1->OEM":
        explicit_segment = "from_supplier_to_safran"
        modes = mode_set(record, explicit_segment)
        model_status = "generic_phase_mode"
    elif edge == "T2->T1" and t2_internal:
        modes = {"internal"}
        model_status = "internalized_no_external_transport"

    issues: list[dict[str, str]] = []
    if dist is None:
        issues.append(
            {
                "severity": "BLOCKER",
                "issue_code": "edge_distance_not_computable",
                "message": f"{edge} distance cannot be computed because at least one node lacks coordinates.",
                "recommended_action": "Add coordinates before mapping this path.",
            }
        )
    if not modes:
        issues.append(
            {
                "severity": "MEDIUM",
                "issue_code": "edge_transport_mode_not_explicit",
                "message": f"{edge} has no explicit lane transport mode.",
                "recommended_action": "Add lane-level mode and distance. Current file only has generic transport phases.",
            }
        )
    elif dist is not None:
        longhaul = dist > 3500
        regional = dist > 1200
        has_longhaul_mode = bool(modes & {"ship", "air", "rail"})
        if longhaul and not has_longhaul_mode and "internal" not in modes:
            issues.append(
                {
                    "severity": "HIGH",
                    "issue_code": "long_distance_mode_implausible",
                    "message": f"{edge} is {dist:.0f} km but modes are only {mode_text(modes)}.",
                    "recommended_action": "Add ship/air/rail or verify real logistics routing.",
                }
            )
        elif regional and modes == {"truck"}:
            issues.append(
                {
                    "severity": "MEDIUM",
                    "issue_code": "regional_long_truck_only",
                    "message": f"{edge} is {dist:.0f} km with truck-only mode.",
                    "recommended_action": "Check whether rail/ship/air should be available for this lane.",
                }
            )

    return {
        "edge": edge,
        "from_name": node_label(src),
        "to_name": node_label(dst),
        "distance_km": "" if dist is None else round(dist, 1),
        "transport_segment_used": explicit_segment,
        "modes": mode_text(modes),
        "transport_model_status": model_status,
        "issues": issues,
    }


def max_severity(issues: list[dict[str, str]]) -> str:
    if not issues:
        return "INFO"
    return max((issue["severity"] for issue in issues), key=lambda sev: SEVERITY_RANK[sev])


def readiness(path_primary: bool, issues: list[dict[str, str]], node_entries: list[dict[str, Any]]) -> str:
    sev = max_severity(issues)
    if sev == "BLOCKER":
        return "not_ready_rework_required"
    if any(issue["issue_code"] == "long_distance_mode_implausible" for issue in issues):
        return "not_ready_transport_rework"
    if path_primary and sev in {"INFO", "LOW"}:
        return "primary_ready_topology"
    if path_primary:
        return "primary_complete_needs_validation"
    if any(is_inactive_candidate(entry) for entry in node_entries):
        return "secondary_candidate_needs_qualification"
    if sev in {"HIGH", "MEDIUM"}:
        return "scenario_candidate_needs_validation"
    return "secondary_ready_topology"


def row_base(record_index: int, record: dict[str, Any], family: str) -> dict[str, Any]:
    lca = record.get("lca_traceability") or {}
    return {
        "record_index": record_index,
        "system": record.get("system", ""),
        "component": record.get("component", ""),
        "family": family,
        "mass_kg": lca.get("mass_kg", record.get("mass_kg")),
        "lca_use_class": lca.get("simulation_use_class", ""),
        "lca_confidence": lca.get("confidence", ""),
        "lca_match_level": lca.get("match_level", ""),
        "lca_equipment_match": lca.get("equipment_match", ""),
        "lca_material_match": lca.get("material_match", ""),
        "raw_materials_status": record.get("raw_materials_status", ""),
    }


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()), extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def main(input_json: Path | None = None, output_prefix: str | None = None) -> None:
    global INPUT_JSON
    if input_json is not None:
        INPUT_JSON = input_json
    if output_prefix:
        configure_output_prefix(output_prefix)

    data = json.loads(INPUT_JSON.read_text(encoding="utf-8"))
    all_records = [(i, r) for i, r in enumerate(data.get("records") or [], 1) if isinstance(r, dict)]
    excluded_records = [(i, r) for i, r in all_records if r.get("simulation_supply_usable") is False]
    records = [(i, r) for i, r in all_records if r.get("simulation_supply_usable") is not False]

    path_rows: list[dict[str, Any]] = []
    component_rows: list[dict[str, Any]] = []
    issue_rows: list[dict[str, Any]] = []
    lane_rows_by_key: dict[tuple[Any, ...], dict[str, Any]] = {}
    node_rows_by_key: dict[tuple[Any, ...], dict[str, Any]] = {}

    readiness_counter = Counter()
    primary_readiness_counter = Counter()
    issue_counter = Counter()
    transport_issue_counter = Counter()
    family_counter = Counter()
    lca_use_counter = Counter()

    for record_index, record in records:
        family = component_family(record)
        family_counter[family] += 1
        lca_use_counter[clean((record.get("lca_traceability") or {}).get("simulation_use_class"))] += 1
        nodes = nodes_by_role(record)
        counts = {code: len(nodes[code]) for code, _role in ROLES}
        all_role_lists = [nodes[code] for code, _role in ROLES]
        component_path_count = math.prod(len(values) for values in all_role_lists)
        primary_path_count = math.prod(sum(1 for entry in nodes[code] if entry.get("is_primary")) for code, _ in ROLES)
        component_readiness = Counter()
        component_issue_counter = Counter()

        missing_roles = [code for code, values in nodes.items() if not values]
        if missing_roles:
            base = row_base(record_index, record, family)
            for code in missing_roles:
                issue_rows.append(
                    {
                        **base,
                        "path_id": "",
                        "scope": "component",
                        "severity": "BLOCKER",
                        "issue_code": "missing_role",
                        "role_or_edge": code,
                        "node": "",
                        "message": f"{code} has no candidate node.",
                        "recommended_action": "Add a node, mark non-applicable, or exclude from full-path simulation.",
                    }
                )

        for combo_index, combo in enumerate(itertools.product(*all_role_lists), 1):
            t4, t3, t2, t1, oem = combo
            node_entries = [t4, t3, t2, t1, oem]
            path_primary = all(bool(entry.get("is_primary")) for entry in node_entries)
            path_id = f"R{record_index:03d}-P{combo_index:04d}"
            issues = lca_issues(record) + component_model_issues(family)

            for code, entry in zip(["T4", "T3", "T2", "T1", "OEM"], node_entries, strict=True):
                node_issues = node_generic_issues(code, entry)
                if code != "OEM":
                    node_issues.extend(material_node_issues(family, code, entry))
                issues.extend(node_issues)

                node_key = (record_index, code, node_id(entry))
                if node_key not in node_rows_by_key:
                    n_issues = node_issues if code == "OEM" else node_generic_issues(code, entry) + material_node_issues(family, code, entry)
                    node_rows_by_key[node_key] = {
                        **row_base(record_index, record, family),
                        "role": code,
                        "name": node_label(entry),
                        "supplier_status": status(entry),
                        "is_primary": bool(entry.get("is_primary")),
                        "allocation_share_pct": entry.get("allocation_share_pct", ""),
                        "country_code": entry.get("country_code", ""),
                        "lat": entry.get("lat", ""),
                        "lon": entry.get("lon", ""),
                        "geocode_status": entry.get("geocode_status", ""),
                        "source_confidence": entry.get("source_confidence") or entry.get("site_selection_confidence") or "",
                        "site_quality": source_quality(entry),
                        "node_issue_count": len(n_issues),
                        "node_max_severity": max_severity(n_issues),
                        "node_issue_codes": ";".join(sorted({issue["issue_code"] for issue in n_issues})),
                    }

            t2_internal = is_internalized_t2(t2, t1)
            edge_rows = [
                edge_audit(record, "T4", "T3", t4, t3, path_primary=path_primary),
                edge_audit(record, "T3", "T2", t3, t2, path_primary=path_primary),
                edge_audit(record, "T2", "T1", t2, t1, t2_internal=t2_internal, path_primary=path_primary),
                edge_audit(record, "T1", "OEM", t1, oem, path_primary=path_primary),
            ]
            for edge_row in edge_rows:
                issues.extend(edge_row["issues"])
                lane_key = (
                    record_index,
                    edge_row["edge"],
                    edge_row["from_name"],
                    edge_row["to_name"],
                    edge_row["modes"],
                    edge_row["transport_model_status"],
                )
                lane = lane_rows_by_key.setdefault(
                    lane_key,
                    {
                        **row_base(record_index, record, family),
                        "edge": edge_row["edge"],
                        "from_name": edge_row["from_name"],
                        "to_name": edge_row["to_name"],
                        "distance_km": edge_row["distance_km"],
                        "transport_segment_used": edge_row["transport_segment_used"],
                        "modes": edge_row["modes"],
                        "transport_model_status": edge_row["transport_model_status"],
                        "lane_issue_codes": "",
                        "lane_max_severity": "INFO",
                        "path_use_count": 0,
                    },
                )
                lane["path_use_count"] += 1
                lane_issues = edge_row["issues"]
                lane["lane_issue_codes"] = ";".join(sorted(set(filter(None, [
                    *(lane["lane_issue_codes"].split(";") if lane["lane_issue_codes"] else []),
                    *(issue["issue_code"] for issue in lane_issues),
                ]))))
                lane["lane_max_severity"] = max([lane["lane_max_severity"], max_severity(lane_issues)], key=lambda s: SEVERITY_RANK[s])

            sev = max_severity(issues)
            ready = readiness(path_primary, issues, node_entries)
            readiness_counter[ready] += 1
            component_readiness[ready] += 1
            if path_primary:
                primary_readiness_counter[ready] += 1

            issue_codes = sorted({issue["issue_code"] for issue in issues})
            for code in issue_codes:
                issue_counter[code] += 1
                component_issue_counter[code] += 1
            for issue in issues:
                if issue["issue_code"].startswith("edge_") or issue["issue_code"] in {
                    "long_distance_mode_implausible",
                    "regional_long_truck_only",
                    "edge_transport_mode_not_explicit",
                }:
                    transport_issue_counter[issue["issue_code"]] += 1

            base = row_base(record_index, record, family)
            path_row = {
                **base,
                "path_id": path_id,
                "path_type": "primary" if path_primary else "secondary_candidate",
                "readiness": ready,
                "max_severity": sev,
                "issue_codes": ";".join(issue_codes),
                "issue_count": len(issues),
                "component_all_path_count": component_path_count,
                "component_primary_path_count": primary_path_count,
                "contains_assumption": any(is_assumed(entry) for entry in node_entries),
                "contains_inactive_candidate": any(is_inactive_candidate(entry) for entry in node_entries),
                "t4": node_label(t4),
                "t4_status": status(t4),
                "t3": node_label(t3),
                "t3_status": status(t3),
                "t2": node_label(t2),
                "t2_status": status(t2),
                "t1": node_label(t1),
                "t1_status": status(t1),
                "oem": node_label(oem),
                "oem_status": status(oem),
                "t4_t3_km": edge_rows[0]["distance_km"],
                "t3_t2_km": edge_rows[1]["distance_km"],
                "t2_t1_km": edge_rows[2]["distance_km"],
                "t1_oem_km": edge_rows[3]["distance_km"],
                "t4_t3_modes": edge_rows[0]["modes"],
                "t3_t2_modes": edge_rows[1]["modes"],
                "t2_t1_modes": edge_rows[2]["modes"],
                "t1_oem_modes": edge_rows[3]["modes"],
                "transport_model": "lane_specific" if not any(er["transport_model_status"] == "missing_explicit_lane_mode" for er in edge_rows) else "generic_phase_modes_only",
            }
            path_rows.append(path_row)

            for issue in issues:
                issue_rows.append(
                    {
                        **base,
                        "path_id": path_id,
                        "scope": "path",
                        "severity": issue["severity"],
                        "issue_code": issue["issue_code"],
                        "role_or_edge": "",
                        "node": "",
                        "message": issue["message"],
                        "recommended_action": issue["recommended_action"],
                    }
                )

        component_rows.append(
            {
                **row_base(record_index, record, family),
                "node_count_t4": counts["T4"],
                "node_count_t3": counts["T3"],
                "node_count_t2": counts["T2"],
                "node_count_t1": counts["T1"],
                "node_count_oem": counts["OEM"],
                "all_path_count": component_path_count,
                "primary_path_count": primary_path_count,
                "primary_path_readiness": next((row["readiness"] for row in path_rows if row["record_index"] == record_index and row["path_type"] == "primary"), ""),
                "readiness_counts": ";".join(f"{k}={v}" for k, v in sorted(component_readiness.items())),
                "issue_codes": ";".join(f"{k}={v}" for k, v in sorted(component_issue_counter.items())),
            }
        )

    lane_rows = list(lane_rows_by_key.values())
    node_rows = list(node_rows_by_key.values())
    write_csv(PATHS_CSV, path_rows)
    write_csv(COMPONENT_CSV, component_rows)
    write_csv(ISSUES_CSV, issue_rows)
    write_csv(LANES_CSV, lane_rows)
    write_csv(NODES_CSV, node_rows)

    total_paths = len(path_rows)
    primary_paths = sum(1 for row in path_rows if row["path_type"] == "primary")
    secondary_paths = total_paths - primary_paths
    primary_ready = sum(1 for row in path_rows if row["path_type"] == "primary" and not str(row["readiness"]).startswith("not_ready"))
    secondary_topology = sum(1 for row in path_rows if row["path_type"] != "primary" and not str(row["readiness"]).startswith("not_ready"))
    all_lane_mode_specific = sum(1 for row in path_rows if row["transport_model"] == "lane_specific")

    lines = [
        "# Supply Path Network Audit",
        "",
        f"- Input JSON: `{INPUT_JSON.as_posix()}`",
        f"- Generated at: `{dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()}`",
        f"- Records audited: **{len(records)}**",
        f"- Records excluded as non-supply LCA/process references: **{len(excluded_records)}**",
        f"- Primary paths: **{primary_paths}**",
        f"- Secondary candidate paths: **{secondary_paths}**",
        f"- Total paths enumerated: **{total_paths}**",
        "",
        "## Main Result",
        "",
        f"- Primary paths not hard-blocked: **{primary_ready} / {primary_paths}**",
        f"- Secondary paths not hard-blocked: **{secondary_topology} / {secondary_paths}**",
        f"- Paths with lane-specific transport model: **{all_lane_mode_specific} / {total_paths}**",
        "",
        "Interpretation: primary baseline paths can now carry lane-specific transport scenarios when provided. Secondary switch paths still need lane validation before activation.",
        "",
        "## Readiness",
        "",
    ]
    for key, count in readiness_counter.most_common():
        lines.append(f"- `{key}`: **{count}**")
    lines.extend(["", "## Primary Readiness", ""])
    for key, count in primary_readiness_counter.most_common():
        lines.append(f"- `{key}`: **{count}**")
    lines.extend(["", "## LCA Use Classes", ""])
    for key, count in lca_use_counter.most_common():
        lines.append(f"- `{key}`: **{count}** records")
    lines.extend(["", "## Families", ""])
    for key, count in family_counter.most_common():
        lines.append(f"- `{key}`: **{count}** records")
    lines.extend(["", "## Top Issue Codes", ""])
    for key, count in issue_counter.most_common(20):
        lines.append(f"- `{key}`: **{count}** path occurrences")
    lines.extend(["", "## Transport Issue Codes", ""])
    for key, count in transport_issue_counter.most_common():
        lines.append(f"- `{key}`: **{count}** path-edge occurrences")
    lines.extend(
        [
            "",
            "## Files",
            "",
            f"- Full path list: `{PATHS_CSV.as_posix()}`",
            f"- Component summary: `{COMPONENT_CSV.as_posix()}`",
            f"- Issue detail: `{ISSUES_CSV.as_posix()}`",
            f"- Transport lane audit: `{LANES_CSV.as_posix()}`",
            f"- Node candidate quality: `{NODES_CSV.as_posix()}`",
            "",
            "## Recommended Next Step",
            "",
            "For stress tests, keep primary paths as the first baseline. Secondary candidates now have lane-specific transport topology; before activation, validate procurement allocation, qualification, lead time, material evidence and the industrial plausibility of the selected mode per lane.",
        ]
    )
    REPORT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=INPUT_JSON, help="JSON to audit")
    parser.add_argument("--prefix", default="output8_GEO_supply_path_network", help="Output filename prefix")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    main(args.input, args.prefix)
