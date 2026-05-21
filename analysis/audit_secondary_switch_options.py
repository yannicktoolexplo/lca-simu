#!/usr/bin/env python3
"""Audit secondary supply paths as switch options.

This does not promote alternates to procurement truth. It classifies each
secondary path by switchability and explains why arbitrary cartesian switching
is unsafe.
"""

from __future__ import annotations

import csv
import datetime as dt
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


BASE_DIR = Path(__file__).resolve().parent
PATHS_CSV = BASE_DIR / "output8_GEO_simulation_ready_researched_supply_path_network_full_paths.csv"
OUT_PATHS = BASE_DIR / "output8_GEO_secondary_switch_path_audit.csv"
OUT_COMPONENTS = BASE_DIR / "output8_GEO_secondary_switch_component_summary.csv"
OUT_SUPPLIERS = BASE_DIR / "output8_GEO_secondary_switch_supplier_options.csv"
OUT_BLOCKERS = BASE_DIR / "output8_GEO_secondary_switch_blockers.csv"
OUT_MD = BASE_DIR / "output8_GEO_secondary_switch_audit_summary.md"

ROLES = [
    ("T4", "t4", "t4_status"),
    ("T3", "t3", "t3_status"),
    ("T2", "t2", "t2_status"),
    ("T1", "t1", "t1_status"),
]

HARD_CODES = {
    "supplier_material_family_incompatible",
    "node_missing_coordinates",
    "edge_distance_not_computable",
    "electronics_upstream_requires_bom",
    "mixed_material_component_should_split",
}

TRANSPORT_CODES = {
    "long_distance_mode_implausible",
    "regional_long_truck_only",
    "edge_transport_mode_not_explicit",
}

VALIDATION_CODES = {
    "inactive_alternate_requires_allocation",
    "baseline_node_is_assumption",
    "material_certificate_required",
    "lca_mass_requires_review",
    "lca_mass_low_confidence",
    "raw_material_source_missing",
    "site_is_fallback_or_centroid",
    "site_low_confidence",
}


def clean(value: Any) -> str:
    return str(value or "").strip()


def issue_set(row: dict[str, str]) -> set[str]:
    return {part for part in clean(row.get("issue_codes")).split(";") if part}


def switch_class(row: dict[str, str]) -> tuple[str, str, str]:
    codes = issue_set(row)
    readiness = clean(row.get("readiness"))
    family = clean(row.get("family"))

    if "supplier_material_family_incompatible" in codes:
        return (
            "blocked_material_incoherent",
            "blocked",
            "At least one supplier tier is materially incompatible with the component family.",
        )
    if "node_missing_coordinates" in codes or "edge_distance_not_computable" in codes:
        return (
            "blocked_geolocation",
            "blocked",
            "At least one node has no usable coordinates, so the switch cannot be mapped or transported.",
        )
    if "electronics_upstream_requires_bom" in codes:
        return (
            "blocked_cots_requires_bom",
            "blocked",
            "COTS/electronics upstream cannot be inferred without BOM, part number, EMS/ODM and AVL.",
        )
    if "mixed_material_component_should_split" in codes:
        return (
            "blocked_split_material_first",
            "blocked",
            "Mixed material line must be split before switching suppliers quantitatively.",
        )
    if readiness == "not_ready_transport_rework" or "long_distance_mode_implausible" in codes:
        return (
            "blocked_transport_rework",
            "blocked_until_transport_fixed",
            "Transport lane is implausible or incomplete for this secondary combination.",
        )
    if readiness == "not_ready_rework_required" or codes & HARD_CODES:
        return (
            "blocked_rework_required",
            "blocked",
            "The path has a hard modelling issue that must be corrected before switch use.",
        )
    if "material_certificate_required" in codes:
        return (
            "candidate_requires_material_certificate",
            "candidate_requires_validation",
            "Material family is plausible, but grade/certificate/site/allocation are required.",
        )
    if "lca_mass_low_confidence" in codes:
        return (
            "candidate_scenario_only_mass_review",
            "candidate_requires_validation",
            "Topology may be usable, but the LCA mass is too weak for quantitative stress tests.",
        )
    if "raw_material_source_missing" in codes:
        return (
            "candidate_requires_material_source",
            "candidate_requires_validation",
            "Raw material source is not confirmed; validate BOM/material certificate before activation.",
        )
    if "site_is_fallback_or_centroid" in codes or "site_low_confidence" in codes:
        return (
            "candidate_requires_site_validation",
            "candidate_requires_validation",
            "Supplier exists as a scenario candidate, but the site should be validated.",
        )
    if "edge_transport_mode_not_explicit" in codes or "regional_long_truck_only" in codes:
        return (
            "candidate_requires_lane_validation",
            "candidate_requires_validation",
            "Topology is plausible, but lane-level transport needs validation before use.",
        )
    if "inactive_alternate_requires_allocation" in codes or "baseline_node_is_assumption" in codes:
        return (
            "candidate_requires_allocation_and_qualification",
            "candidate_requires_validation",
            "The path is a plausible switch candidate, but allocation, qualification and lead time are missing.",
        )
    if readiness == "secondary_ready_topology":
        return ("switch_ready_topology", "switch_ready_topology", "No hard issue detected in topology.")

    return (
        "candidate_requires_validation",
        "candidate_requires_validation",
        f"Secondary path needs validation before switch activation for family {family}.",
    )


def family_policy(family: str) -> str:
    if family in {"aluminium", "steel", "copper"}:
        return "Switch possible only within same material family and with certificate/grade/site; T2 internal process must remain paired with its T1."
    if family == "electronics_cots":
        return "No free upstream switch. Switch only at qualified program supplier or PN level after BOM/AVL validation."
    if family in {"textile_leather", "rubber_silicone"}:
        return "Switch requires approved material, fire/smoke/tox evidence, upholstery/process validation and exact site."
    if family in {"polymer_plastic", "adhesive_composite", "titanium_carbon"}:
        return "Switch requires exact grade, process route, certification and part drawing; generic material suppliers are not enough."
    if family == "mixed_metal":
        return "Split material lines before switching; do not activate one combined path."
    return "Switch only after role, material, site and transport validation."


def verdict_from_counts(counts: Counter[str]) -> str:
    if counts.get("switch_ready_topology"):
        return "switch_ready_topology"
    if counts.get("candidate_requires_validation"):
        return "switch_possible_after_validation"
    if counts.get("blocked_until_transport_fixed") and not counts.get("blocked"):
        return "blocked_until_transport_fixed"
    return "blocked_or_incoherent"


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fieldnames = list(dict.fromkeys(key for row in rows for key in row.keys()))
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    with PATHS_CSV.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))

    secondary = [row for row in rows if row.get("path_type") == "secondary_candidate"]
    path_rows: list[dict[str, Any]] = []
    component_stats: dict[str, dict[str, Any]] = {}
    supplier_stats: dict[tuple[str, str, str], dict[str, Any]] = {}
    blocker_stats: Counter[tuple[str, str, str]] = Counter()
    global_switch_verdicts: Counter[str] = Counter()
    detailed_classes: Counter[str] = Counter()

    for row in secondary:
        cls, verdict, reason = switch_class(row)
        codes = issue_set(row)
        detailed_classes[cls] += 1
        global_switch_verdicts[verdict] += 1
        record_key = clean(row.get("record_index"))
        family = clean(row.get("family"))
        comp = component_stats.setdefault(
            record_key,
            {
                "record_index": row.get("record_index"),
                "system": row.get("system"),
                "component": row.get("component"),
                "family": family,
                "mass_kg": row.get("mass_kg"),
                "lca_use_class": row.get("lca_use_class"),
                "total_secondary_paths": 0,
                "switch_ready_topology": 0,
                "candidate_requires_validation": 0,
                "blocked_until_transport_fixed": 0,
                "blocked": 0,
                "best_verdict": "",
                "top_issue_codes": Counter(),
                "switch_policy": family_policy(family),
            },
        )
        comp["total_secondary_paths"] += 1
        comp[verdict] += 1
        comp["top_issue_codes"].update(codes)

        for code in codes:
            blocker_stats[(family, code, cls)] += 1

        path_rows.append(
            {
                "record_index": row.get("record_index"),
                "system": row.get("system"),
                "component": row.get("component"),
                "family": family,
                "path_id": row.get("path_id"),
                "readiness": row.get("readiness"),
                "switch_class": cls,
                "switch_verdict": verdict,
                "switch_reason": reason,
                "issue_codes": row.get("issue_codes"),
                "t4": row.get("t4"),
                "t4_status": row.get("t4_status"),
                "t3": row.get("t3"),
                "t3_status": row.get("t3_status"),
                "t2": row.get("t2"),
                "t2_status": row.get("t2_status"),
                "t1": row.get("t1"),
                "t1_status": row.get("t1_status"),
                "t4_t3_km": row.get("t4_t3_km"),
                "t4_t3_modes": row.get("t4_t3_modes"),
                "t3_t2_km": row.get("t3_t2_km"),
                "t3_t2_modes": row.get("t3_t2_modes"),
                "t2_t1_km": row.get("t2_t1_km"),
                "t2_t1_modes": row.get("t2_t1_modes"),
                "t1_oem_km": row.get("t1_oem_km"),
                "t1_oem_modes": row.get("t1_oem_modes"),
            }
        )

        for role_code, name_col, status_col in ROLES:
            name = clean(row.get(name_col))
            if not name:
                continue
            key = (role_code, name, family)
            stat = supplier_stats.setdefault(
                key,
                {
                    "role": role_code,
                    "supplier": name,
                    "family": family,
                    "path_count": 0,
                    "switch_ready_topology": 0,
                    "candidate_requires_validation": 0,
                    "blocked_until_transport_fixed": 0,
                    "blocked": 0,
                    "components": set(),
                    "status_examples": set(),
                    "issue_codes": Counter(),
                    "best_verdict": "",
                },
            )
            stat["path_count"] += 1
            stat[verdict] += 1
            stat["components"].add(f"{row.get('record_index')}:{row.get('component')}")
            stat["status_examples"].add(clean(row.get(status_col)))
            stat["issue_codes"].update(codes)

    component_rows: list[dict[str, Any]] = []
    for comp in component_stats.values():
        counts = Counter({
            "switch_ready_topology": comp["switch_ready_topology"],
            "candidate_requires_validation": comp["candidate_requires_validation"],
            "blocked_until_transport_fixed": comp["blocked_until_transport_fixed"],
            "blocked": comp["blocked"],
        })
        best = verdict_from_counts(counts)
        comp["best_verdict"] = best
        issue_counter = comp.pop("top_issue_codes")
        comp["top_issue_codes"] = ";".join(f"{k}={v}" for k, v in issue_counter.most_common(8))
        component_rows.append(comp)

    supplier_rows: list[dict[str, Any]] = []
    for stat in supplier_stats.values():
        counts = Counter({
            "switch_ready_topology": stat["switch_ready_topology"],
            "candidate_requires_validation": stat["candidate_requires_validation"],
            "blocked_until_transport_fixed": stat["blocked_until_transport_fixed"],
            "blocked": stat["blocked"],
        })
        stat["best_verdict"] = verdict_from_counts(counts)
        issue_counter = stat.pop("issue_codes")
        stat["issue_codes"] = ";".join(f"{k}={v}" for k, v in issue_counter.most_common(8))
        stat["components"] = " | ".join(sorted(stat["components"])[:30])
        stat["status_examples"] = " | ".join(sorted(x for x in stat["status_examples"] if x))
        supplier_rows.append(stat)

    blocker_rows = [
        {
            "family": family,
            "issue_code": issue_code,
            "switch_class": cls,
            "path_occurrences": count,
        }
        for (family, issue_code, cls), count in blocker_stats.most_common()
    ]

    component_rows.sort(key=lambda r: (r["best_verdict"], -int(r["blocked"]), -int(r["candidate_requires_validation"]), int(r["record_index"])))
    supplier_rows.sort(key=lambda r: (r["best_verdict"], r["role"], r["supplier"]))

    write_csv(OUT_PATHS, path_rows)
    write_csv(OUT_COMPONENTS, component_rows)
    write_csv(OUT_SUPPLIERS, supplier_rows)
    write_csv(OUT_BLOCKERS, blocker_rows)

    candidate_total = global_switch_verdicts["switch_ready_topology"] + global_switch_verdicts["candidate_requires_validation"]
    blocked_total = global_switch_verdicts["blocked"] + global_switch_verdicts["blocked_until_transport_fixed"]
    component_verdicts = Counter(row["best_verdict"] for row in component_rows)
    supplier_verdicts = Counter(row["best_verdict"] for row in supplier_rows)
    family_counts = Counter(row["family"] for row in path_rows)
    family_candidate = Counter(row["family"] for row in path_rows if row["switch_verdict"] in {"switch_ready_topology", "candidate_requires_validation"})
    family_blocked = Counter(row["family"] for row in path_rows if row["switch_verdict"] in {"blocked", "blocked_until_transport_fixed"})

    lines = [
        "# Audit des chemins secondaires et switchs fournisseurs",
        "",
        f"- Source paths: `{PATHS_CSV.as_posix()}`",
        f"- Generated at: `{dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()}`",
        f"- Secondary paths audited: **{len(secondary)}**",
        "",
        "## Verdict court",
        "",
        "On ne peut pas switcher librement tous les fournisseurs entre eux. Les chemins secondaires sont des combinaisons de scenarios, pas des couples d'achat valides par defaut. Un switch doit respecter la famille matiere, le role industriel, la qualification fournisseur, le certificat matiere, le lead time et le transport lane-by-lane.",
        "",
        "## Switchability globale",
        "",
        f"- Candidats non bloques apres validation: **{candidate_total} / {len(secondary)}**",
        f"- Bloques ou incoherents avant correction: **{blocked_total} / {len(secondary)}**",
    ]
    for key, count in global_switch_verdicts.most_common():
        lines.append(f"- `{key}`: **{count}**")
    lines.extend(["", "## Classes detaillees", ""])
    for key, count in detailed_classes.most_common():
        lines.append(f"- `{key}`: **{count}**")
    lines.extend(["", "## Synthese par composant", ""])
    for key, count in component_verdicts.most_common():
        lines.append(f"- `{key}`: **{count}** composants")
    lines.extend(["", "## Synthese par option fournisseur/tier", ""])
    for key, count in supplier_verdicts.most_common():
        lines.append(f"- `{key}`: **{count}** options fournisseur/famille/tier")
    lines.extend(["", "## Familles les plus concernees", ""])
    for family, total in family_counts.most_common():
        lines.append(
            f"- `{family}`: {total} chemins secondaires, {family_candidate[family]} candidats apres validation, {family_blocked[family]} bloques"
        )
    lines.extend(["", "## Principales validations restantes", ""])
    for row in blocker_rows[:20]:
        lines.append(
            f"- `{row['family']}` / `{row['issue_code']}` / `{row['switch_class']}`: **{row['path_occurrences']}** chemins"
        )
    lines.extend(["", "## Composants les plus bloques", ""])
    blocked_components = sorted(component_rows, key=lambda r: int(r["blocked"]), reverse=True)
    for row in blocked_components[:15]:
        if int(row["blocked"]) == 0:
            continue
        lines.append(
            f"- record `{row['record_index']}` `{row['component']}` ({row['family']}): "
            f"{row['blocked']} bloques, {row['candidate_requires_validation']} candidats apres validation"
        )
    lines.extend(["", "## Options fournisseur/tier a exclure en priorite", ""])
    blocked_suppliers = sorted(supplier_rows, key=lambda r: int(r["blocked"]), reverse=True)
    for row in blocked_suppliers[:20]:
        if int(row["blocked"]) == 0:
            continue
        lines.append(
            f"- `{row['role']}` `{row['supplier']}` sur `{row['family']}`: "
            f"{row['blocked']} combinaisons bloquees / {row['path_count']} chemins"
        )
    lines.extend(
        [
            "",
            "## Regles de switch a appliquer",
            "",
            "- Ne jamais activer le produit cartesien complet des alternates.",
            "- Les process internalises T2 doivent rester couples a leur T1; ex. `SUMPAR internal process` ne doit pas etre combine avec `MGA`.",
            "- Pour aluminium/acier/cuivre, un switch T4/T3 exige certificat matiere, nuance, mill/site et allocation.",
            "- Pour textile/mousse/cuir/silicone, il faut les preuves feu/fumee/toxicite et la fiche matiere exacte.",
            "- Pour COTS/electronique, l'amont T3/T4 reste non switchable sans BOM, part number, EMS/ODM et AVL.",
            "- Tout switch international doit conserver un transport lane-by-lane; les secondaires ont maintenant une lane calculee, mais le mode choisi doit rester validable industriellement.",
            "",
            "## Fichiers produits",
            "",
            f"- Detail tous chemins secondaires: `{OUT_PATHS.as_posix()}`",
            f"- Resume par composant: `{OUT_COMPONENTS.as_posix()}`",
            f"- Options par fournisseur/tier/famille: `{OUT_SUPPLIERS.as_posix()}`",
            f"- Blocages groupes: `{OUT_BLOCKERS.as_posix()}`",
        ]
    )
    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"Wrote {OUT_PATHS}")
    print(f"Wrote {OUT_COMPONENTS}")
    print(f"Wrote {OUT_SUPPLIERS}")
    print(f"Wrote {OUT_BLOCKERS}")
    print(f"Wrote {OUT_MD}")


if __name__ == "__main__":
    main()
