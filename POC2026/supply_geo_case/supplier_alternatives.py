"""Named supplier-alternative selection for lightweight-seat sourcing scenarios."""

from __future__ import annotations

import json
import math
import re
import unicodedata
from collections import defaultdict
from pathlib import Path
from typing import Any


ROLES = ("T4", "T3", "T2", "T1", "OEM")
EUROPE_COUNTRIES = {
    "AT", "BE", "BG", "CH", "CY", "CZ", "DE", "DK", "EE", "ES", "FI", "FR",
    "GB", "GR", "HR", "HU", "IE", "IS", "IT", "LT", "LU", "LV", "MT", "NL",
    "NO", "PL", "PT", "RO", "SE", "SI", "SK",
}
SCENARIOS = (
    {
        "scenario_id": "france_named_alternatives",
        "label": "France prioritaire - fournisseurs nommes",
        "target_scope": "france",
        "electricity_scope": "fr",
        "aluminium_scope": "eu",
        "fallback_scope": "europe",
        "concentration_caps": {"T4": 0.60, "T3": 0.45, "T2": 0.45, "T1": 0.35},
    },
    {
        "scenario_id": "europe_named_alternatives",
        "label": "Europe prioritaire - fournisseurs nommes",
        "target_scope": "europe",
        "electricity_scope": "eu",
        "aluminium_scope": "eu",
        "fallback_scope": "baseline",
        "concentration_caps": {"T4": 0.50, "T3": 0.40, "T2": 0.40, "T1": 0.30},
    },
)


def clean(value: Any) -> str:
    return str(value or "").strip()


def number(value: Any, default: float = 0.0) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    return result if math.isfinite(result) else default


def normalized(value: Any) -> str:
    text = unicodedata.normalize("NFKD", clean(value))
    text = "".join(char for char in text if not unicodedata.combining(char)).lower()
    return " ".join(re.sub(r"[^a-z0-9]+", " ", text).split())


def role_from_hint(value: Any) -> str:
    hint = normalized(value)
    if "tier4" in hint or "raw material" in hint:
        return "T4"
    if "tier3" in hint or "first transformation" in hint or hint == "transformation":
        return "T3"
    if "tier2" in hint or "second transformation" in hint:
        return "T2"
    if "tier1" in hint:
        return "T1"
    if "oem" in hint:
        return "OEM"
    return ""


def in_scope(country_code: Any, scope: str) -> bool:
    country = clean(country_code).upper()
    if scope == "france":
        return country == "FR"
    if scope == "europe":
        return country in EUROPE_COUNTRIES
    return False


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    if not all(math.isfinite(value) for value in (lat1, lon1, lat2, lon2)):
        return 0.0
    radius = 6371.0088
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)
    term = (
        math.sin(delta_phi / 2.0) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0) ** 2
    )
    return 2.0 * radius * math.asin(math.sqrt(min(1.0, term)))


def confidence_score(candidate: dict[str, Any]) -> float:
    levels = {"high": 1.0, "medium_high": 0.85, "medium": 0.68, "low": 0.35}
    source = levels.get(normalized(candidate.get("source_confidence")).replace(" ", "_"), 0.40)
    site = levels.get(normalized(candidate.get("site_selection_confidence")).replace(" ", "_"), 0.0)
    evidence = 0.15 if candidate.get("site_selection_source_url") else 0.0
    evidence += 0.10 if candidate.get("source_ids") else 0.0
    if "source backed" in normalized(candidate.get("geocode_status")):
        evidence += 0.08
    return min(1.0, max(source, site) + evidence)


def context_index(context_rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for row in context_rows:
        key = normalized(row.get("supplier"))
        if not key:
            continue
        current = result.get(key)
        if current is None or number(row.get("data_confidence_score")) > number(current.get("data_confidence_score")):
            result[key] = row
    return result


def baseline_supplier(
    path: dict[str, Any],
    role: str,
    record: dict[str, Any],
    sites: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    role_key = role.lower()
    name = clean(path.get(role_key))
    candidates = [
        supplier
        for supplier in record.get("suppliers", [])
        if role_from_hint(supplier.get("role_hint")) == role and bool(supplier.get("is_primary"))
    ]
    match = next((item for item in candidates if normalized(item.get("name")) == normalized(name)), None)
    if match is None and candidates:
        match = candidates[0]
    result = dict(match or {})
    site_uid = clean(path.get(f"{role_key}_site_uid"))
    site = sites.get(site_uid, {})
    result.update({
        "name": name or clean(result.get("name")),
        "country_code": clean(path.get(f"{role_key}_country_code")) or clean(result.get("country_code")),
        "site_uid": site_uid,
        "lat": number(site.get("lat"), number(result.get("lat"))),
        "lon": number(site.get("lon"), number(result.get("lon"))),
        "is_primary": True,
        "supplier_status": clean(path.get(f"{role_key}_status")) or "baseline_primary",
    })
    return result


def documented_alternatives(record: dict[str, Any], role: str, baseline_name: str) -> list[dict[str, Any]]:
    return [
        dict(supplier)
        for supplier in record.get("suppliers", [])
        if role_from_hint(supplier.get("role_hint")) == role
        and not bool(supplier.get("is_primary"))
        and clean(supplier.get("supplier_status")) == "alternate"
        and normalized(supplier.get("name")) != normalized(baseline_name)
        and clean(supplier.get("country_code"))
        and math.isfinite(number(supplier.get("lat"), float("nan")))
        and math.isfinite(number(supplier.get("lon"), float("nan")))
    ]


def candidate_score(
    candidate: dict[str, Any],
    *,
    downstream: dict[str, Any] | None,
    context: dict[str, dict[str, Any]],
    load_kg: float,
    cap_kg: float,
    path_mass_kg: float,
) -> tuple[float, dict[str, float | bool]]:
    evidence = confidence_score(candidate)
    supplier_context = context.get(normalized(candidate.get("name")), {})
    aerospace = number(supplier_context.get("aerospace_relevance_score"))
    data_confidence = number(supplier_context.get("data_confidence_score"))
    fragility = max(
        number(supplier_context.get("documentary_criticality_score")),
        number(supplier_context.get("observed_fragility_score")),
    )
    distance = 0.0
    if downstream:
        distance = haversine_km(
            number(candidate.get("lat")),
            number(candidate.get("lon")),
            number(downstream.get("lat")),
            number(downstream.get("lon")),
        )
    distance_score = 1.0 / (1.0 + distance / 1200.0)
    capacity_exceeded = bool(cap_kg > 0.0 and load_kg + path_mass_kg > cap_kg + 1e-9)
    capacity_score = max(0.0, 1.0 - (load_kg + path_mass_kg) / cap_kg) if cap_kg else 0.5
    score = (
        0.34 * evidence
        + 0.18 * aerospace
        + 0.13 * data_confidence
        + 0.20 * distance_score
        + 0.15 * capacity_score
        - 0.16 * fragility
        - (0.20 if capacity_exceeded else 0.0)
    )
    return score, {
        "evidence_score": round(evidence, 6),
        "aerospace_relevance_score": round(aerospace, 6),
        "data_confidence_score": round(data_confidence, 6),
        "documentary_fragility_score": round(fragility, 6),
        "distance_to_downstream_km": round(distance, 3),
        "capacity_proxy_exceeded": capacity_exceeded,
    }


def qualification_label(candidate: dict[str, Any], context: dict[str, dict[str, Any]]) -> str:
    evidence = confidence_score(candidate)
    supplier_context = context.get(normalized(candidate.get("name")), {})
    aerospace = number(supplier_context.get("aerospace_relevance_score"))
    if evidence >= 0.85 and aerospace >= 0.5:
        return "documente_a_qualifier"
    if evidence >= 0.65:
        return "source_industrielle_a_qualifier"
    return "candidat_source_a_confirmer"


def route_modes(left: dict[str, Any], right: dict[str, Any], distance_km: float) -> str:
    left_country = clean(left.get("country_code")).upper()
    right_country = clean(right.get("country_code")).upper()
    if normalized(left.get("name")) == normalized(right.get("name")) or distance_km < 20.0:
        return "internal"
    if left_country in EUROPE_COUNTRIES and right_country in EUROPE_COUNTRIES:
        return "truck"
    if distance_km <= 1000.0:
        return "truck"
    return "ship|truck"


def build_supplier_alternative_scenarios(
    *,
    source_json_path: Path,
    path_rows: list[dict[str, Any]],
    site_rows: list[dict[str, Any]],
    context_rows: list[dict[str, Any]],
    target_mass_kg: float,
) -> dict[str, Any]:
    source = json.loads(source_json_path.read_text(encoding="utf-8"))
    records = source.get("records", [])
    usable_paths = [row for row in path_rows if number(row.get("path_mass_kg")) > 0.0]
    baseline_path_mass = sum(number(row.get("path_mass_kg")) for row in usable_paths)
    mass_scale = target_mass_kg / baseline_path_mass if baseline_path_mass else 0.0
    context = context_index(context_rows)
    sites = {clean(row.get("site_uid")): row for row in site_rows}
    all_assignments: list[dict[str, Any]] = []
    all_routes: list[dict[str, Any]] = []
    all_candidates: list[dict[str, Any]] = []
    scenario_summaries: list[dict[str, Any]] = []

    for scenario in SCENARIOS:
        scenario_id = scenario["scenario_id"]
        load_by_role_supplier: dict[tuple[str, str], float] = defaultdict(float)
        scenario_assignments: list[dict[str, Any]] = []
        scenario_routes: list[dict[str, Any]] = []

        for path in sorted(usable_paths, key=lambda row: -number(row.get("path_mass_kg"))):
            record_index = int(number(path.get("record_index")))
            if record_index <= 0 or record_index > len(records):
                continue
            record = records[record_index - 1]
            path_mass = number(path.get("path_mass_kg")) * mass_scale
            selected_by_role: dict[str, dict[str, Any]] = {}

            for role in reversed(ROLES):
                baseline = baseline_supplier(path, role, record, sites)
                if not baseline.get("name"):
                    continue
                downstream = selected_by_role.get(ROLES[ROLES.index(role) + 1]) if role != "OEM" else None
                alternatives = documented_alternatives(record, role, clean(baseline.get("name")))
                selection_type = "retained_primary"
                selected = baseline
                ranked: list[tuple[float, dict[str, Any], dict[str, float | bool], str]] = []

                if role != "OEM" and not in_scope(baseline.get("country_code"), scenario["target_scope"]):
                    primary_scope = ""
                    if scenario["target_scope"] == "france" and in_scope(baseline.get("country_code"), "europe"):
                        primary_scope = "europe_fallback"
                    target_candidates = [candidate for candidate in alternatives if in_scope(candidate.get("country_code"), scenario["target_scope"])]
                    fallback_candidates = []
                    if not target_candidates and scenario.get("fallback_scope") == "europe":
                        fallback_candidates = [candidate for candidate in alternatives if in_scope(candidate.get("country_code"), "europe")]
                    pool = target_candidates or fallback_candidates
                    pool_scope = "target" if target_candidates else "europe_fallback" if fallback_candidates else ""
                    cap_share = number(scenario.get("concentration_caps", {}).get(role))
                    cap_kg = target_mass_kg * cap_share
                    for candidate in pool:
                        key = (role, normalized(candidate.get("name")))
                        score, diagnostics = candidate_score(
                            candidate,
                            downstream=downstream,
                            context=context,
                            load_kg=load_by_role_supplier[key],
                            cap_kg=cap_kg,
                            path_mass_kg=path_mass,
                        )
                        ranked.append((score, candidate, diagnostics, pool_scope))
                    if ranked:
                        ranked.sort(key=lambda item: (-item[0], normalized(item[1].get("name"))))
                        _, selected, _, selected_scope = ranked[0]
                        selection_type = "selected_named_alternative" if selected_scope == "target" else "selected_named_european_fallback"
                    elif primary_scope:
                        selection_type = "retained_primary_european_fallback"
                    else:
                        selection_type = "retained_primary_no_eligible_alternative"

                selected = dict(selected)
                selected.setdefault("site_uid", clean(selected.get("site_id")))
                selected_by_role[role] = selected
                selected_key = (role, normalized(selected.get("name")))
                load_by_role_supplier[selected_key] += path_mass
                selected_diagnostics = next((item[2] for item in ranked if normalized(item[1].get("name")) == normalized(selected.get("name"))), {})
                context_row = context.get(normalized(selected.get("name")), {})
                assignment = {
                    "scenario_id": scenario_id,
                    "scenario_label": scenario["label"],
                    "path_id": path.get("path_id"),
                    "record_index": record_index,
                    "system": path.get("system"),
                    "component": path.get("component"),
                    "family": path.get("family"),
                    "role": role,
                    "lightweight_path_mass_kg": round(path_mass, 9),
                    "baseline_supplier": baseline.get("name"),
                    "baseline_country_code": baseline.get("country_code"),
                    "selected_supplier": selected.get("name"),
                    "selected_supplier_id": selected.get("supplier_id"),
                    "selected_site_id": selected.get("site_id"),
                    "selected_country_code": selected.get("country_code"),
                    "selected_location": selected.get("location"),
                    "selected_lat": round(number(selected.get("lat")), 7),
                    "selected_lon": round(number(selected.get("lon")), 7),
                    "selection_type": selection_type,
                    "is_named_alternative": selection_type.startswith("selected_named"),
                    "strict_target_scope": in_scope(selected.get("country_code"), scenario["target_scope"]),
                    "european_scope": in_scope(selected.get("country_code"), "europe"),
                    "candidate_count_same_role": len(alternatives),
                    "eligible_candidate_count": len(ranked),
                    "qualification_status": "baseline_supplier" if not selection_type.startswith("selected_named") else qualification_label(selected, context),
                    "source_confidence": selected.get("source_confidence"),
                    "site_selection_confidence": selected.get("site_selection_confidence"),
                    "source_url": selected.get("site_selection_source_url"),
                    "context_data_confidence_score": number(context_row.get("data_confidence_score")),
                    "context_aerospace_relevance_score": number(context_row.get("aerospace_relevance_score")),
                    "context_documentary_criticality_score": number(context_row.get("documentary_criticality_score")),
                    **selected_diagnostics,
                }
                scenario_assignments.append(assignment)
                all_assignments.append(assignment)

                selected_name = normalized(selected.get("name"))
                for score, candidate, diagnostics, candidate_scope in ranked:
                    candidate_row = {
                        "scenario_id": scenario_id,
                        "path_id": path.get("path_id"),
                        "record_index": record_index,
                        "role": role,
                        "component": path.get("component"),
                        "candidate_supplier": candidate.get("name"),
                        "candidate_country_code": candidate.get("country_code"),
                        "candidate_scope": candidate_scope,
                        "selection_score": round(score, 6),
                        "selected": normalized(candidate.get("name")) == selected_name,
                        "rejection_reason": "" if normalized(candidate.get("name")) == selected_name else "lower_ranked_compatible_candidate",
                        "qualification_status": qualification_label(candidate, context),
                        "source_url": candidate.get("site_selection_source_url"),
                        **diagnostics,
                    }
                    all_candidates.append(candidate_row)

            for index in range(len(ROLES) - 1):
                left_role, right_role = ROLES[index], ROLES[index + 1]
                left = selected_by_role.get(left_role)
                right = selected_by_role.get(right_role)
                if not left or not right:
                    continue
                distance = haversine_km(
                    number(left.get("lat")), number(left.get("lon")),
                    number(right.get("lat")), number(right.get("lon")),
                )
                edge_key = f"{left_role.lower()}_{right_role.lower()}"
                baseline_distance = number(path.get(f"{edge_key}_km"))
                route = {
                    "scenario_id": scenario_id,
                    "path_id": path.get("path_id"),
                    "record_index": record_index,
                    "component": path.get("component"),
                    "edge": f"{left_role}->{right_role}",
                    "from_supplier": left.get("name"),
                    "from_country_code": left.get("country_code"),
                    "from_lat": round(number(left.get("lat")), 7),
                    "from_lon": round(number(left.get("lon")), 7),
                    "to_supplier": right.get("name"),
                    "to_country_code": right.get("country_code"),
                    "to_lat": round(number(right.get("lat")), 7),
                    "to_lon": round(number(right.get("lon")), 7),
                    "distance_km": round(distance, 3),
                    "baseline_distance_km": round(baseline_distance, 3),
                    "distance_delta_km": round(distance - baseline_distance, 3),
                    "modes": route_modes(left, right, distance),
                    "lightweight_path_mass_kg": round(path_mass, 9),
                    "allocated_kg_km": round(path_mass * distance, 6),
                    "baseline_lightweight_kg_km": round(path_mass * baseline_distance, 6),
                }
                scenario_routes.append(route)
                all_routes.append(route)

        target_assignments = [row for row in scenario_assignments if row["role"] != "OEM"]
        denominator = sum(number(row.get("lightweight_path_mass_kg")) for row in target_assignments)
        strict_mass = sum(number(row.get("lightweight_path_mass_kg")) for row in target_assignments if row.get("strict_target_scope"))
        european_mass = sum(number(row.get("lightweight_path_mass_kg")) for row in target_assignments if row.get("european_scope"))
        path_roles: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in target_assignments:
            path_roles[clean(row.get("path_id"))].append(row)
        fully_local_mass = sum(
            number(rows[0].get("lightweight_path_mass_kg"))
            for rows in path_roles.values()
            if rows and all(bool(row.get("strict_target_scope")) for row in rows)
        )
        path_mass_denominator = sum(
            number(rows[0].get("lightweight_path_mass_kg"))
            for rows in path_roles.values()
            if rows
        )
        baseline_kg_km = sum(number(row.get("baseline_lightweight_kg_km")) for row in scenario_routes)
        scenario_kg_km = sum(number(row.get("allocated_kg_km")) for row in scenario_routes)
        alternatives = [row for row in target_assignments if row.get("is_named_alternative")]
        scenario_summaries.append({
            "scenario_id": scenario_id,
            "label": scenario["label"],
            "target_scope": scenario["target_scope"],
            "electricity_scope": scenario["electricity_scope"],
            "aluminium_scope": scenario["aluminium_scope"],
            "target_mass_kg": round(target_mass_kg, 6),
            "source_path_mass_kg": round(baseline_path_mass, 6),
            "mass_reconciliation_factor": round(mass_scale, 12),
            "path_count": len(path_roles),
            "assignment_count": len(target_assignments),
            "named_alternative_assignment_count": len(alternatives),
            "unique_named_alternative_supplier_count": len({normalized(row.get("selected_supplier")) for row in alternatives}),
            "retained_primary_local_count": sum(1 for row in target_assignments if row.get("selection_type") == "retained_primary"),
            "retained_primary_no_alternative_count": sum(1 for row in target_assignments if row.get("selection_type") == "retained_primary_no_eligible_alternative"),
            "capacity_proxy_exceeded_count": sum(1 for row in alternatives if row.get("capacity_proxy_exceeded")),
            "strict_target_role_mass_pct": round(100.0 * strict_mass / denominator, 6) if denominator else 0.0,
            "european_role_mass_pct": round(100.0 * european_mass / denominator, 6) if denominator else 0.0,
            "fully_localized_path_mass_pct": round(100.0 * fully_local_mass / path_mass_denominator, 6) if path_mass_denominator else 0.0,
            "baseline_lightweight_transport_kg_km": round(baseline_kg_km, 6),
            "scenario_transport_kg_km": round(scenario_kg_km, 6),
            "transport_amount_factor": round(scenario_kg_km / baseline_kg_km, 9) if baseline_kg_km else 1.0,
            "transport_reduction_pct": round(100.0 * (baseline_kg_km - scenario_kg_km) / baseline_kg_km, 6) if baseline_kg_km else 0.0,
            "selected_alternative_suppliers": " | ".join(sorted({clean(row.get("selected_supplier")) for row in alternatives})),
            "selection_status": "named_candidates_selected_component_qualification_required",
            "capacity_note": "Concentration caps are portfolio proxies, not verified industrial capacity.",
        })

    supplier_loads: dict[tuple[str, str, str], dict[str, Any]] = {}
    for row in all_assignments:
        if not row.get("is_named_alternative"):
            continue
        key = (clean(row.get("scenario_id")), clean(row.get("role")), normalized(row.get("selected_supplier")))
        aggregate = supplier_loads.setdefault(key, {
            "scenario_id": row.get("scenario_id"),
            "role": row.get("role"),
            "supplier": row.get("selected_supplier"),
            "country_code": row.get("selected_country_code"),
            "assignment_count": 0,
            "allocated_role_mass_kg": 0.0,
            "components": set(),
            "qualification_statuses": set(),
            "source_urls": set(),
        })
        aggregate["assignment_count"] += 1
        aggregate["allocated_role_mass_kg"] += number(row.get("lightweight_path_mass_kg"))
        aggregate["components"].add(clean(row.get("component")))
        aggregate["qualification_statuses"].add(clean(row.get("qualification_status")))
        if row.get("source_url"):
            aggregate["source_urls"].add(clean(row.get("source_url")))
    supplier_rows = [
        {
            **{key: value for key, value in row.items() if key not in {"components", "qualification_statuses", "source_urls"}},
            "allocated_role_mass_kg": round(row["allocated_role_mass_kg"], 6),
            "component_count": len(row["components"]),
            "components": " | ".join(sorted(row["components"])),
            "qualification_statuses": " | ".join(sorted(row["qualification_statuses"])),
            "source_urls": " | ".join(sorted(row["source_urls"])),
        }
        for row in supplier_loads.values()
    ]
    supplier_rows.sort(key=lambda row: (clean(row.get("scenario_id")), clean(row.get("role")), -number(row.get("allocated_role_mass_kg"))))
    return {
        "schema_version": "poc2026.named_supplier_alternatives.v1",
        "source_json": str(source_json_path),
        "selection_principle": "Same component and tier, documented alternate first, geography, evidence, distance, context risk and concentration proxy.",
        "scenario_summaries": scenario_summaries,
        "assignments": all_assignments,
        "routes": all_routes,
        "candidate_audit": all_candidates,
        "supplier_loads": supplier_rows,
    }
