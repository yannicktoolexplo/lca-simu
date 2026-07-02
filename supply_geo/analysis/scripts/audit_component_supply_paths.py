#!/usr/bin/env python3
"""Audit component supply paths by tier, separating real gaps from modeled gaps."""

from __future__ import annotations

import csv
import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


BASE_DIR = Path(__file__).resolve().parent
DEFAULT_INPUT_JSON = BASE_DIR / "output8_GEO_normalized_final_site_refined.json"
DEFAULT_PRIMARY_CSV = BASE_DIR / "output8_GEO_primary_component_path_audit.csv"
DEFAULT_ALL_CSV = BASE_DIR / "output8_GEO_all_component_coverage_audit.csv"
DEFAULT_GAPS_CSV = BASE_DIR / "output8_GEO_component_tier_gap_actions.csv"
DEFAULT_REPORT_MD = BASE_DIR / "output8_GEO_component_path_audit_summary.md"

ROLES = [
    "tier4_raw_material",
    "tier3_first_transformation",
    "tier2_second_transformation",
    "tier1",
    "oem",
]

ROLE_CODE = {
    "tier4_raw_material": "T4",
    "tier3_first_transformation": "T3",
    "tier2_second_transformation": "T2",
    "tier1": "T1",
    "oem": "OEM",
}

ACTION_PRIORITY = {
    "hard_gap_direct_supplier": 0,
    "hard_gap_manual_review": 1,
    "requires_bom_or_part_number": 2,
    "requires_material_certificate": 3,
    "accepted_internalized_process": 4,
    "accepted_do_not_infer_cots": 5,
    "accepted_upstream_family_unknown": 6,
    "accepted_present_but_unpositioned": 7,
    "no_issue": 99,
}


def has_coords(entry: dict[str, Any]) -> bool:
    return entry.get("lat") not in (None, "") and entry.get("lon") not in (None, "")


def clean(value: Any) -> str:
    return str(value or "").strip()


def role_entries(record: dict[str, Any], role: str, *, primary_only: bool, require_coords: bool = False) -> list[dict[str, Any]]:
    if role == "oem":
        entries = [entry for entry in record.get("oem_sites") or [] if isinstance(entry, dict)]
    else:
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


def names(entries: list[dict[str, Any]]) -> str:
    return " | ".join(clean(entry.get("name")) for entry in entries if clean(entry.get("name")))


def names_with_status(entries: list[dict[str, Any]]) -> str:
    values = []
    for entry in entries:
        name = clean(entry.get("name"))
        if not name:
            continue
        status = clean(entry.get("supplier_status") or entry.get("geocode_status"))
        values.append(f"{name} [{status}]" if status else name)
    return " | ".join(values)


def review_by_tier(record: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    out: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in record.get("missing_tier_business_review") or []:
        code = item.get("missing_tier_code")
        if code:
            out[str(code)].append(item)
    return out


def internal_by_tier(record: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    out: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in record.get("internalized_process_tiers") or []:
        code = item.get("missing_tier_code")
        if code:
            out[str(code)].append(item)
    return out


def review_text(items: list[dict[str, Any]]) -> str:
    if not items:
        return ""
    chunks = []
    for item in items:
        resolution = clean(item.get("most_probable_resolution"))
        decision = clean(item.get("recommended_modeling_decision"))
        confidence = clean(item.get("confidence"))
        if resolution or decision:
            chunks.append(f"{resolution} / {decision} ({confidence})".strip())
    return " || ".join(chunks)


def classify_gap(record: dict[str, Any], role: str, *, logical_present: bool, mappable_present: bool) -> tuple[str, str, str]:
    code = ROLE_CODE[role]
    reviews = review_by_tier(record).get(code, [])
    internals = internal_by_tier(record).get(code, [])

    if logical_present and not mappable_present:
        entries = role_entries(record, role, primary_only=True)
        status = "; ".join(clean(entry.get("geocode_status")) for entry in entries if clean(entry.get("geocode_status")))
        return (
            "accepted_present_but_unpositioned",
            f"{code} existe dans le modèle mais n'est pas cartographiable: {status or 'coordonnees absentes'}.",
            "Garder hors carte ou renseigner le site exact; ne pas créer un faux point.",
        )

    if logical_present:
        return ("no_issue", "", "")

    if internals or any(item.get("resolution_class") == "probable_internalized_process" for item in reviews):
        owner = review_text(reviews) or review_text(internals)
        return (
            "accepted_internalized_process",
            f"{code} absent comme fournisseur externe car le procédé est probablement internalisé chez le T1.",
            owner or "Créer un process virtuel rattaché au T1 si la simulation exige un niveau T2 explicite.",
        )

    classes = {clean(item.get("resolution_class")) for item in reviews}
    text = review_text(reviews)

    if "do_not_infer_from_cots" in classes:
        return (
            "accepted_do_not_infer_cots",
            f"{code} non inféré pour COTS/électronique.",
            text or "Demander BOM, part number, EMS/ODM et AVL avant d'ajouter des sous-tiers.",
        )
    if "probable_direct_supplier_requires_part_number" in classes:
        return (
            "requires_bom_or_part_number",
            f"{code} direct non prouvé.",
            text or "Demander part number, fournisseur programme, site et qualification.",
        )
    if "probable_material_certificate_source" in classes or "probable_existing_material_processor" in classes:
        return (
            "requires_material_certificate",
            f"{code} matière/transformateur non activable sans certificat ou routing.",
            text or "Demander certificat matière, mill, stockiste/forge/lamineur exact.",
        )
    family = material_family(record)
    if role == "tier4_raw_material" and family in {"steel", "aluminium", "copper"}:
        return (
            "requires_material_certificate",
            f"{code} producteur matière primaire absent pour famille {family}.",
            "Demander certificat matière, mill exact, pays, site et allocation avant d'activer un producteur.",
        )
    if role == "tier2_second_transformation" and family == "electronics_cots":
        return (
            "requires_bom_or_part_number",
            f"{code} procédé/EMS électronique non identifié.",
            "Demander BOM, part number, EMS/ODM, routage industriel et AVL.",
        )
    if "probable_material_family_source" in classes:
        return (
            "accepted_upstream_family_unknown",
            f"{code} amont de famille matière inconnu.",
            text or "Ne pas activer un fournisseur unique sans fiche matière/grade.",
        )
    if "manual_review_required" in classes:
        return (
            "hard_gap_manual_review",
            f"{code} non déterminable avec les données actuelles.",
            text or "Revue achat/engineering nécessaire.",
        )
    if role == "tier1":
        return (
            "hard_gap_direct_supplier",
            "T1 fournisseur direct absent.",
            "Bloquant pour un switch fournisseur: demander fournisseur programme ou modéliser explicitement en opération interne Safran.",
        )
    return (
        "hard_gap_manual_review",
        f"{code} absent sans règle de résolution documentée.",
        "Créer une décision métier: internalisé, non applicable, ou fournisseur/route à documenter.",
    )


def material_family(record: dict[str, Any]) -> str:
    text = " ".join(
        [
            clean(record.get("component")).lower(),
            " ".join(clean(x).lower() for x in record.get("raw_materials") or []),
        ]
    )
    if any(key in text for key in ["a5086", "a2017", "a2024", "a6060", "aluminium", "alu"]):
        return "aluminium"
    if any(key in text for key in ["cuivre", "copper", "alliage cu"]):
        return "copper"
    if any(key in text for key in ["acier", "steel", "inox", "35nc6", "30ncd6", "15cdv6", "4140"]):
        return "steel"
    if any(key in text for key in ["display", "powerbox", "ife", "ecu", "remote", "lightning", "electronic"]):
        return "electronics_cots"
    if any(key in text for key in ["tissu", "velours", "velcro", "cuir", "textile", "leather"]):
        return "textile_leather"
    if any(key in text for key in ["silicone", "caoutchouc", "rubber", "polychloroprene"]):
        return "rubber_silicone"
    if any(key in text for key in ["ertalon", "nylon", "polyamide", "kydex", "plastique", "plastic", "nida"]):
        return "polymer_plastic"
    if any(key in text for key in ["composite", "carbone", "carbon", "titane"]):
        return "composite_titanium"
    return "general"


def path_status(gap_actions: list[str]) -> str:
    if not gap_actions:
        return "complete_direct"
    highest = min(ACTION_PRIORITY.get(action, 99) for action in gap_actions)
    if highest <= ACTION_PRIORITY["hard_gap_manual_review"]:
        return "blocked_or_manual_review_required"
    if highest <= ACTION_PRIORITY["requires_bom_or_part_number"]:
        return "requires_bom_or_program_data"
    if highest <= ACTION_PRIORITY["requires_material_certificate"]:
        return "requires_certificate_or_routing"
    if highest <= ACTION_PRIORITY["accepted_internalized_process"]:
        return "valid_with_internalized_process_bridge"
    return "valid_but_upstream_not_switchable"


def audit_record(record: dict[str, Any], record_index: int, *, primary_only: bool) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    logical: dict[str, list[dict[str, Any]]] = {
        role: role_entries(record, role, primary_only=primary_only, require_coords=False) for role in ROLES
    }
    mappable: dict[str, list[dict[str, Any]]] = {
        role: role_entries(record, role, primary_only=primary_only, require_coords=True) for role in ROLES
    }

    gap_rows: list[dict[str, Any]] = []
    gap_actions: list[str] = []
    for role in ROLES:
        logical_present = bool(logical[role])
        mappable_present = bool(mappable[role])
        action_class, meaning, action = classify_gap(
            record, role, logical_present=logical_present, mappable_present=mappable_present
        )
        if action_class == "no_issue":
            continue
        gap_actions.append(action_class)
        gap_rows.append(
            {
                "scope": "primary" if primary_only else "all",
                "record_index": record_index,
                "system": record.get("system", ""),
                "component": record.get("component", ""),
                "material_family": material_family(record),
                "tier": ROLE_CODE[role],
                "action_class": action_class,
                "meaning": meaning,
                "recommended_action": action,
                "logical_present": logical_present,
                "mappable_present": mappable_present,
                "primary_t1": names(role_entries(record, "tier1", primary_only=True)),
            }
        )

    present_roles = [ROLE_CODE[role] for role in ROLES if logical[role]]
    mappable_roles = [ROLE_CODE[role] for role in ROLES if mappable[role]]
    missing_roles = [ROLE_CODE[role] for role in ROLES if not logical[role]]
    unpositioned_roles = [ROLE_CODE[role] for role in ROLES if logical[role] and not mappable[role]]
    row = {
        "scope": "primary" if primary_only else "all",
        "record_index": record_index,
        "system": record.get("system", ""),
        "component": record.get("component", ""),
        "material_family": material_family(record),
        "path_status": path_status(gap_actions),
        "logical_path": " > ".join(
            f"{ROLE_CODE[role]}={names(logical[role]) or 'MISSING'}" for role in ROLES
        ),
        "mappable_path": " > ".join(
            f"{ROLE_CODE[role]}={names(mappable[role]) or 'MISSING/UNMAPPED'}" for role in ROLES
        ),
        "present_roles": ";".join(present_roles),
        "mappable_roles": ";".join(mappable_roles),
        "missing_roles": ";".join(missing_roles),
        "unpositioned_roles": ";".join(unpositioned_roles),
        "gap_action_classes": ";".join(gap_actions),
        "gap_count": len(gap_rows),
        "primary_t4": names_with_status(role_entries(record, "tier4_raw_material", primary_only=True)),
        "primary_t3": names_with_status(role_entries(record, "tier3_first_transformation", primary_only=True)),
        "primary_t2": names_with_status(role_entries(record, "tier2_second_transformation", primary_only=True)),
        "primary_t1": names_with_status(role_entries(record, "tier1", primary_only=True)),
        "all_t4_count": len(role_entries(record, "tier4_raw_material", primary_only=False)),
        "all_t3_count": len(role_entries(record, "tier3_first_transformation", primary_only=False)),
        "all_t2_count": len(role_entries(record, "tier2_second_transformation", primary_only=False)),
        "all_t1_count": len(role_entries(record, "tier1", primary_only=False)),
        "all_switchability_note": switchability_note(record),
    }
    return row, gap_rows


def switchability_note(record: dict[str, Any]) -> str:
    notes = []
    for role in ["tier4_raw_material", "tier3_first_transformation", "tier2_second_transformation", "tier1"]:
        all_entries = role_entries(record, role, primary_only=False)
        primary_entries = role_entries(record, role, primary_only=True)
        alt_entries = [entry for entry in all_entries if entry not in primary_entries]
        if alt_entries:
            notes.append(f"{ROLE_CODE[role]} alternates={len(alt_entries)}")
    if not notes:
        return "single_or_unresolved"
    return "; ".join(notes) + "; validate qualification/capacity/share before stress-test activation"


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fieldnames = list(rows[0].keys())
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_report(
    primary_rows: list[dict[str, Any]],
    all_rows: list[dict[str, Any]],
    gaps: list[dict[str, Any]],
    *,
    input_json: Path,
    primary_csv: Path,
    all_csv: Path,
    gaps_csv: Path,
    report_md: Path,
) -> None:
    primary_status = Counter(row["path_status"] for row in primary_rows)
    all_status = Counter(row["path_status"] for row in all_rows)
    primary_actions = Counter(gap["action_class"] for gap in gaps if gap["scope"] == "primary")
    all_actions = Counter(gap["action_class"] for gap in gaps if gap["scope"] == "all")
    missing_by_tier = Counter(gap["tier"] for gap in gaps if gap["scope"] == "primary")

    lines = [
        "# Component Supply Path Audit",
        "",
        f"- Source JSON: `{input_json.as_posix()}`",
        f"- Primary path CSV: `{primary_csv.as_posix()}`",
        f"- All-supplier coverage CSV: `{all_csv.as_posix()}`",
        f"- Gap/action CSV: `{gaps_csv.as_posix()}`",
        "",
        "## Ce que veut dire un tier absent",
        "",
        "Un tier absent signifie qu'aucun noeud fournisseur cartographiable n'est porté à ce niveau dans le JSON pour ce composant. Ce n'est pas automatiquement une erreur.",
        "Les cas fréquents sont: procédé T2 internalisé chez le T1, amont matière volontairement non activé sans certificat, sous-tiers COTS non inférables sans BOM/PN, ou vrai fournisseur direct T1 encore inconnu.",
        "",
        "## Fournisseurs principaux",
        "",
        f"- Records audités: **{len(primary_rows)}**",
        f"- Statuts parcours: {', '.join(f'{k}={v}' for k, v in primary_status.most_common())}",
        f"- Gaps/actions: {', '.join(f'{k}={v}' for k, v in primary_actions.most_common())}",
        f"- Tiers concernés: {', '.join(f'{k}={v}' for k, v in missing_by_tier.most_common())}",
        "",
        "Lecture recommandée: les `accepted_internalized_process` sont normaux pour des pièces mécaniques; ce sont des opérations de fabrication chez ESPACE, SUMPAR, MGA, Senior Aerospace, etc. Les `requires_bom_or_program_data` et `hard_gap_*` sont les vrais blocages pour la simulation.",
        "",
        "## Tous fournisseurs activables",
        "",
        f"- Records audités: **{len(all_rows)}**",
        f"- Statuts parcours/couverture: {', '.join(f'{k}={v}' for k, v in all_status.most_common())}",
        f"- Gaps/actions: {', '.join(f'{k}={v}' for k, v in all_actions.most_common())}",
        "",
        "Même en mode `all`, je ne combine pas automatiquement tous les T4/T3/T2/T1 entre eux. Un alternate par tier est une option de scénario, pas une preuve qu'il est compatible avec chaque autre alternate.",
        "",
        "## Priorités de correction",
        "",
    ]

    priority_order = [
        "hard_gap_direct_supplier",
        "hard_gap_manual_review",
        "requires_bom_or_part_number",
        "requires_material_certificate",
        "accepted_present_but_unpositioned",
        "accepted_internalized_process",
        "accepted_upstream_family_unknown",
        "accepted_do_not_infer_cots",
    ]
    for action in priority_order:
        rows = [gap for gap in gaps if gap["scope"] == "primary" and gap["action_class"] == action]
        if not rows:
            continue
        examples = "; ".join(
            f"R{row['record_index']} {row['tier']} {row['component']}" for row in rows[:8]
        )
        lines.append(f"- `{action}`: {len(rows)} cas. Exemples: {examples}")

    lines += [
        "",
        "## Interprétation pour la carte",
        "",
        "- Trait plein: tiers adjacents présents et cartographiables.",
        "- Pont pointillé: tier intermédiaire absent ou non cartographiable, mais le parcours atteint quand même le constructeur.",
        "- T2 absent sur métal/aluminium: généralement procédé internalisé chez le T1, pas fournisseur manquant.",
        "- T1 absent: vrai blocage métier tant que le fournisseur programme ou le PN n'est pas connu.",
        "- T3/T4 absents sur COTS/textile/polymères: souvent non activable sans BOM, grade ou certificat.",
        "",
    ]
    report_md.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT_JSON)
    parser.add_argument("--primary-csv", type=Path, default=DEFAULT_PRIMARY_CSV)
    parser.add_argument("--all-csv", type=Path, default=DEFAULT_ALL_CSV)
    parser.add_argument("--gaps-csv", type=Path, default=DEFAULT_GAPS_CSV)
    parser.add_argument("--report-md", type=Path, default=DEFAULT_REPORT_MD)
    args = parser.parse_args()

    data = json.loads(args.input.read_text(encoding="utf-8"))
    records = data["records"] if isinstance(data, dict) and "records" in data else data
    primary_rows: list[dict[str, Any]] = []
    all_rows: list[dict[str, Any]] = []
    gap_rows: list[dict[str, Any]] = []

    for idx, record in enumerate(records, 1):
        if not isinstance(record, dict) or record.get("simulation_supply_usable") is False:
            continue
        record_index = record.get("record_index") or record.get("index") or idx
        primary_row, primary_gaps = audit_record(record, record_index, primary_only=True)
        all_row, all_gaps = audit_record(record, record_index, primary_only=False)
        primary_rows.append(primary_row)
        all_rows.append(all_row)
        gap_rows.extend(primary_gaps)
        gap_rows.extend(all_gaps)

    write_csv(args.primary_csv, primary_rows)
    write_csv(args.all_csv, all_rows)
    write_csv(args.gaps_csv, gap_rows)
    write_report(
        primary_rows,
        all_rows,
        gap_rows,
        input_json=args.input,
        primary_csv=args.primary_csv,
        all_csv=args.all_csv,
        gaps_csv=args.gaps_csv,
        report_md=args.report_md,
    )
    print(f"[OK] wrote {args.primary_csv}")
    print(f"[OK] wrote {args.all_csv}")
    print(f"[OK] wrote {args.gaps_csv}")
    print(f"[OK] wrote {args.report_md}")


if __name__ == "__main__":
    main()
