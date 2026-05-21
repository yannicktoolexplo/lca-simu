#!/usr/bin/env python3
"""Propose candidates for missing tiers without altering validated suppliers."""

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
OUT_JSON = ROOT / "analysis" / "output8_GEO_normalized_final_with_missing_tier_proposals.json"
OUT_CSV = ROOT / "analysis" / "output8_GEO_missing_tier_proposals.csv"
OUT_MD = ROOT / "analysis" / "output8_GEO_missing_tier_proposals.md"

ROLES = [
    "tier4_raw_material",
    "tier3_first_transformation",
    "tier2_second_transformation",
    "tier1",
]

ROLE_CODE = {
    "tier4_raw_material": "T4",
    "tier3_first_transformation": "T3",
    "tier2_second_transformation": "T2",
    "tier1": "T1",
}

SOURCE_URLS = {
    "SRC_LAUAK_001": "https://www.groupe-lauak.com/lauak-groupe/presentation-du-groupe/sites/",
    "SRC_SUMPAR_001": "https://www.sumpar.com/en/join-us/",
    "SRC_FIGEAC_001": "https://www.figeac-aero.com/fr/contact",
    "SRC_SEGNERE_001": "https://www.space-aero.org/en/member/segnere-ade/",
    "SRC_GATTEFIN_001": "https://gattefin.fr/",
    "SRC_PLASTISERVICE_001": "https://plastiservice.com/nos-implantations/",
    "SRC_EXSTO_001": "https://www.exsto.com/en/contact",
    "SRC_THYSSEN_001": "https://www.thyssenkrupp-aerospace.com/en/company/locations/france",
    "SRC_EURALLIAGE_001": "https://www.euralliage.com/coordonnees.htm",
    "SRC_AUBERT_001": "https://www.aubertduval.com/",
    "SRC_ALCOA_001": "https://www.alcoa.com/global/en/who-we-are/locations",
    "SRC_HINDALCO_001": "https://www.hindalco.com/contact-us/",
    "SRC_ARCELORMITTAL_001": "https://luxembourg.arcelormittal.com/en/arcelormittal-in-luxembourg/headquarters",
    "SRC_TATA_STEEL_001": "https://www.tata.com/business/tata-steel",
    "SRC_BAOWU_001": "https://craft.co/baosteel/locations",
    "SRC_SOLVAY_001": "https://www.solvay.com/en/solutions-market/aerospace",
    "SRC_SABIC_001": "https://www.sabic.com/en/about",
    "SRC_BASF_001": "https://www.basf.com/global/en/who-we-are/organization/locations/europe/german-sites/ludwigshafen",
    "SRC_SHINETSU_001": "https://www.shinetsusilicone-global.com/",
    "SRC_TORAY_001": "https://www.toray.com/global/",
    "SRC_DUPONT_001": "https://www.dupont.com/locations.html.html",
    "SRC_HEXCEL_001": "https://www.hexcel.com/About/",
    "SRC_SGL_001": "https://www.sglcarbon.com/en/markets-solutions/industries/aerospace/",
    "SRC_ULTRAFABRICS_001": "https://www.ultrafabricsinc.com/",
    "SRC_THALES_001": "https://www.thalesgroup.com/en/markets/aerospace",
    "SRC_HONEYWELL_001": "https://aerospace.honeywell.com/",
    "SRC_COLLINS_001": "https://www.collinsaerospace.com/",
    "SRC_AUBERON_001": "https://auberon-technologies.com/",
    "SRC_JAMCO_001": "https://www.jamco.co.jp/en/company/group.html",
    "SRC_ACH_001": "https://www.ach-aeronefs.fr/en/contact/",
    "SRC_SAFRAN_SEATS_001": "https://www.safran-group.com/locations",
}


def norm(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value or "").lower()).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


def role_suppliers(record: dict[str, Any], role: str) -> list[dict[str, Any]]:
    return [
        supplier
        for supplier in record.get("suppliers") or []
        if isinstance(supplier, dict) and supplier.get("role_hint") == role
    ]


def primary_names(record: dict[str, Any], role: str) -> list[str]:
    entries = role_suppliers(record, role)
    primaries = [entry.get("name", "") for entry in entries if entry.get("is_primary")]
    return [name for name in primaries if name] or [entry.get("name", "") for entry in entries[:3] if entry.get("name")]


def family(record: dict[str, Any]) -> str:
    text = norm(" ".join([str(record.get("system") or ""), str(record.get("component") or "")]))
    if any(token in text for token in ["aluminium", "alu", "a5086", "a2017", "a2024", "a6060"]):
        return "aluminium"
    if any(token in text for token in ["acier", "inox", "35nc6", "30ncd6", "15cdv6", "4140", "z10cnt18", "frmc55"]):
        return "steel"
    if any(token in text for token in ["cuivre", "alliage cu", "copper"]):
        return "copper"
    if any(token in text for token in ["titane", "fibre de carbone", "carbone", "carbon"]):
        return "titanium_carbon"
    if any(token in text for token in ["tissu", "textile", "velours", "leather", "cuir", "ultra leather"]):
        return "textile_leather"
    if any(token in text for token in ["silicone", "caoutchouc", "polychloroprene"]):
        return "rubber_silicone"
    if any(token in text for token in ["kydex", "nylon", "ertalon", "polyurethane", "moulage plastique", "lexan", "polyethylene", "polymere", "plastique"]):
        return "polymer_plastic"
    if any(token in text for token in ["film decor", "aerfilm", "resine", "composite"]):
        return "adhesive_composite"
    if any(token in text for token in ["display", "ecran", "powerbox", "remote", "clavier", "ife", "lightning", "commande actionnement", "sfcu"]):
        return "electronics_cots"
    if any(token in text for token in ["airvolt", "papier", "paper", "laminat"]):
        return "paper_laminate"
    return "general"


def proposal(
    record: dict[str, Any],
    record_index: int,
    missing_role: str,
    candidate_name: str,
    candidate_type: str,
    confidence: str,
    rationale: str,
    modeling_action: str,
    source_ids: list[str] | None = None,
) -> dict[str, Any]:
    source_ids = source_ids or []
    return {
        "record_index": record_index,
        "system": record.get("system", ""),
        "component": record.get("component", ""),
        "material_family": family(record),
        "missing_role": missing_role,
        "missing_tier_code": ROLE_CODE[missing_role],
        "candidate_name": candidate_name,
        "candidate_type": candidate_type,
        "confidence": confidence,
        "modeling_action": modeling_action,
        "rationale": rationale,
        "source_ids": ";".join(source_ids),
        "source_urls": ";".join(SOURCE_URLS.get(source_id, "") for source_id in source_ids if SOURCE_URLS.get(source_id)),
        "active_supplier_recommendation": "no",
    }


def propose_for_missing(record: dict[str, Any], record_index: int, missing_role: str) -> list[dict[str, Any]]:
    fam = family(record)
    t1 = primary_names(record, "tier1")
    t3 = primary_names(record, "tier3_first_transformation")
    out: list[dict[str, Any]] = []

    if missing_role == "tier2_second_transformation":
        if fam in {"aluminium", "steel", "copper"}:
            owner = ", ".join(t1[:3]) if t1 else "downstream T1"
            out.append(
                proposal(
                    record,
                    record_index,
                    missing_role,
                    f"{owner} - machining/forming process owner",
                    "inferred_process_owner",
                    "medium_high",
                    "For metal parts, the absent T2 is often machining, forming, cutting, treatment, or kitting already covered by the T1 manufacturing scope.",
                    "model_as_internalized_T2_at_T1_or_validate_subcontractor",
                    ["SRC_LAUAK_001", "SRC_SUMPAR_001", "SRC_FIGEAC_001"],
                )
            )
        elif fam in {"polymer_plastic", "rubber_silicone", "adhesive_composite"}:
            out.append(
                proposal(
                    record,
                    record_index,
                    missing_role,
                    "specialist plastics/rubber/composite processor to validate",
                    "candidate_process_family",
                    "medium",
                    "The missing T2 should be a transformation processor rather than a raw-material producer.",
                    "add_candidate_only_after_process_and_part_traceability",
                    ["SRC_PLASTISERVICE_001", "SRC_EXSTO_001"],
                )
            )
        else:
            out.append(
                proposal(
                    record,
                    record_index,
                    missing_role,
                    "process owner not identified",
                    "unknown_process_owner",
                    "low",
                    "A T2 role is structurally expected, but the data does not identify whether it is a subcontractor or internal to T1.",
                    "keep_gap_bridge_until_purchase_or_routing_data",
                )
            )

    elif missing_role == "tier3_first_transformation":
        if fam in {"steel", "aluminium", "copper"}:
            candidates = "thyssenkrupp Materials France / Aubert & Duval / Euralliage"
            out.append(
                proposal(
                    record,
                    record_index,
                    missing_role,
                    candidates,
                    "candidate_supplier_set",
                    "medium",
                    "For metal parts, T3 is usually stockholding, rolling/extrusion, forging, or first transformation before machining.",
                    "select_existing_material_processor_based_on_grade_and_traceability",
                    ["SRC_THYSSEN_001", "SRC_AUBERT_001", "SRC_EURALLIAGE_001"],
                )
            )
        elif fam in {"electronics_cots"}:
            out.append(
                proposal(
                    record,
                    record_index,
                    missing_role,
                    "electronics sub-tier unknown",
                    "needs_exact_bom",
                    "low",
                    "Do not infer electronic T3 from generic semiconductor brands; exact PCB/display/power supplier BOM is required.",
                    "keep_out_of_switchable_supplier_network_until_exact_BOM",
                    ["SRC_THALES_001", "SRC_HONEYWELL_001", "SRC_COLLINS_001"],
                )
            )
        else:
            out.append(
                proposal(
                    record,
                    record_index,
                    missing_role,
                    "first transformation source to validate",
                    "candidate_process_family",
                    "low",
                    "The missing T3 is material-family dependent and cannot be assigned reliably from component text alone.",
                    "manual_validation_required",
                )
            )

    elif missing_role == "tier4_raw_material":
        if fam == "steel":
            out.append(
                proposal(
                    record,
                    record_index,
                    missing_role,
                    "Saarstahl / ArcelorMittal / Tata Steel / China Baowu steel source",
                    "candidate_supplier_set",
                    "medium",
                    "For steel grades, the missing T4 is a steelmaker or alloy/raw steel source; choose the actual mill from material certificates.",
                    "choose_steelmaker_by_grade_certificate_before_activation",
                    ["SRC_ARCELORMITTAL_001", "SRC_TATA_STEEL_001", "SRC_BAOWU_001"],
                )
            )
        elif fam == "aluminium":
            out.append(
                proposal(
                    record,
                    record_index,
                    missing_role,
                    "Alcoa / Hindalco / Chalco aluminium source",
                    "candidate_supplier_set",
                    "medium",
                    "For aluminium grades, the missing T4 is alumina/aluminium primary production; activate only with alloy and mill traceability.",
                    "choose_aluminium_source_by_material_certificate_before_activation",
                    ["SRC_ALCOA_001", "SRC_HINDALCO_001"],
                )
            )
        elif fam == "copper":
            out.append(
                proposal(
                    record,
                    record_index,
                    missing_role,
                    "Hindalco or copper raw-material source to validate",
                    "candidate_supplier_set",
                    "medium_low",
                    "For copper-alloy parts, the missing T4 is copper/refining or alloy raw material; exact mill certificates are needed.",
                    "choose_copper_source_by_material_certificate_before_activation",
                    ["SRC_HINDALCO_001"],
                )
            )
        elif fam in {"textile_leather"}:
            out.append(
                proposal(
                    record,
                    record_index,
                    missing_role,
                    "fiber/polymer or hide upstream source",
                    "candidate_material_family",
                    "medium",
                    "For textile/leather rows, T4 is the fiber, polymer, or hide upstream source; exact material composition decides the supplier.",
                    "add_material_family_T4_after_material_spec_validation",
                    ["SRC_TORAY_001", "SRC_DUPONT_001", "SRC_BASF_001", "SRC_ULTRAFABRICS_001"],
                )
            )
        elif fam in {"rubber_silicone"}:
            out.append(
                proposal(
                    record,
                    record_index,
                    missing_role,
                    "Shin-Etsu / silicone raw chemistry source",
                    "candidate_supplier_set",
                    "medium",
                    "Silicone parts need an upstream silicone chemistry source; Shin-Etsu is already validated as a silicone-material actor, but exact grade/site remains open.",
                    "candidate_only_until_silicone_grade_traceability",
                    ["SRC_SHINETSU_001"],
                )
            )
        elif fam in {"polymer_plastic", "adhesive_composite"}:
            out.append(
                proposal(
                    record,
                    record_index,
                    missing_role,
                    "BASF / SABIC / Solvay raw polymer or resin source",
                    "candidate_supplier_set",
                    "medium",
                    "For plastics, films, and composites, the missing T4 is a resin/polymer/chemical producer; exact grade should drive the choice.",
                    "choose_candidate_by_material_grade_before_activation",
                    ["SRC_BASF_001", "SRC_SABIC_001", "SRC_SOLVAY_001"],
                )
            )
        elif fam == "electronics_cots":
            out.append(
                proposal(
                    record,
                    record_index,
                    missing_role,
                    "do not infer generic semiconductor/foundry tier",
                    "needs_exact_bom",
                    "low",
                    "Electronics T4 depends on exact components and foundry/distributor chain; generic COTS brands should stay out of the switchable production network.",
                    "keep_as_COTS_upstream_context_not_supply_tier",
                    ["SRC_THALES_001", "SRC_HONEYWELL_001", "SRC_COLLINS_001"],
                )
            )
        elif fam == "titanium_carbon":
            out.append(
                proposal(
                    record,
                    record_index,
                    missing_role,
                    "Hexcel / SGL Carbon / Toray for carbon fiber; titanium source to validate",
                    "candidate_supplier_set",
                    "medium_low",
                    "The label mixes titanium and carbon fiber, so it likely needs separate T4 candidates for fiber and metal.",
                    "split_material_before_supplier_activation",
                    ["SRC_HEXCEL_001", "SRC_SGL_001", "SRC_TORAY_001"],
                )
            )
        else:
            out.append(
                proposal(
                    record,
                    record_index,
                    missing_role,
                    "raw material producer to validate",
                    "unknown_material_source",
                    "low",
                    "No robust material-family rule is available for this row.",
                    "manual_validation_required",
                )
            )

    elif missing_role == "tier1":
        if fam == "electronics_cots":
            out.append(
                proposal(
                    record,
                    record_index,
                    missing_role,
                    "Thales / Honeywell Aerospace / Collins / Auberon depending exact equipment",
                    "candidate_supplier_set",
                    "medium_low",
                    "Electronic equipment rows need an exact equipment integrator or part supplier before they become switchable T1 nodes.",
                    "candidate_only_until_part_number_supplier_validation",
                    ["SRC_THALES_001", "SRC_HONEYWELL_001", "SRC_COLLINS_001", "SRC_AUBERON_001"],
                )
            )
        elif fam in {"polymer_plastic", "adhesive_composite", "titanium_carbon"}:
            out.append(
                proposal(
                    record,
                    record_index,
                    missing_role,
                    "JAMCO / Collins / ACH / Safran internal integrator to validate",
                    "candidate_supplier_set",
                    "medium_low",
                    "Interior parts without T1 should be linked to the actual module/integration supplier, not directly to OEM by default.",
                    "validate_program_supplier_or_model_as_internal_Safran_operation",
                    ["SRC_JAMCO_001", "SRC_COLLINS_001", "SRC_ACH_001", "SRC_SAFRAN_SEATS_001"],
                )
            )
        else:
            out.append(
                proposal(
                    record,
                    record_index,
                    missing_role,
                    "direct supplier or internal operation to validate",
                    "unknown_direct_supplier",
                    "low",
                    "A T1 is structurally expected before OEM, but current data does not name it.",
                    "manual_validation_required",
                )
            )
    return out


def write_csv(rows: list[dict[str, Any]]) -> None:
    fields = [
        "record_index",
        "system",
        "component",
        "material_family",
        "missing_role",
        "missing_tier_code",
        "candidate_name",
        "candidate_type",
        "confidence",
        "modeling_action",
        "rationale",
        "source_ids",
        "source_urls",
        "active_supplier_recommendation",
    ]
    with OUT_CSV.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def write_report(rows: list[dict[str, Any]], records_count: int) -> None:
    by_role = Counter(row["missing_tier_code"] for row in rows)
    by_action = Counter(row["modeling_action"] for row in rows)
    by_conf = Counter(row["confidence"] for row in rows)
    lines = [
        "# Missing tier candidate proposals",
        "",
        f"- Source JSON: `{INPUT_JSON.as_posix()}`",
        f"- Proposal JSON: `{OUT_JSON.as_posix()}`",
        f"- Proposal CSV: `{OUT_CSV.as_posix()}`",
        "",
        "## Principle",
        "",
        "These are candidate tier completions, not validated production suppliers.",
        "They are stored outside `suppliers` so they do not become active switch options until a buyer, BOM, drawing, or route validates them.",
        "",
        "## Counts",
        "",
        f"- Records analysed: {records_count}",
        f"- Proposal rows: {len(rows)}",
        f"- By missing tier: {', '.join(f'{key}={value}' for key, value in by_role.most_common())}",
        f"- By confidence: {', '.join(f'{key}={value}' for key, value in by_conf.most_common())}",
        "",
        "## Modeling Actions",
        "",
    ]
    for action, count in by_action.most_common():
        lines.append(f"- `{action}`: {count}")
    lines += [
        "",
        "## High/Medium-High Confidence Examples",
        "",
    ]
    for row in rows:
        if row["confidence"] not in {"high", "medium_high"}:
            continue
        lines.append(
            f"- R{row['record_index']} `{row['component']}` {row['missing_tier_code']}: "
            f"{row['candidate_name']} - {row['modeling_action']}"
        )
    lines += [
        "",
        "## Recommended Use",
        "",
        "- Keep the current final JSON as the validated simulation base.",
        "- Use this file to prioritize purchasing/engineering validation of missing tiers.",
        "- Promote a proposal into `suppliers` only after exact site, role, allocation, lead time, capacity, and qualification are known.",
        "- For metal rows missing T2, prefer modeling a T1-internal process unless a separate machining/forming subcontractor is documented.",
        "",
    ]
    OUT_MD.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    source = json.loads(INPUT_JSON.read_text(encoding="utf-8"))
    records = source.get("records") or []
    all_rows: list[dict[str, Any]] = []
    enriched_records: list[dict[str, Any]] = []
    for index, record in enumerate(records, start=1):
        enriched = json.loads(json.dumps(record, ensure_ascii=False))
        missing_roles = [role for role in ROLES if not role_suppliers(record, role)]
        proposals: list[dict[str, Any]] = []
        for missing_role in missing_roles:
            proposals.extend(propose_for_missing(record, index, missing_role))
        enriched["missing_tier_proposals"] = [
            {
                key: row[key]
                for key in (
                    "missing_role",
                    "missing_tier_code",
                    "candidate_name",
                    "candidate_type",
                    "confidence",
                    "modeling_action",
                    "rationale",
                    "source_ids",
                    "source_urls",
                    "active_supplier_recommendation",
                )
            }
            for row in proposals
        ]
        all_rows.extend(proposals)
        enriched_records.append(enriched)
    output = json.loads(json.dumps(source, ensure_ascii=False))
    output["records"] = enriched_records
    output.setdefault("_meta", {})
    output["_meta"]["missing_tier_proposals"] = {
        "script": Path(__file__).as_posix(),
        "policy": "candidate-only suggestions; do not activate in suppliers without business validation",
        "proposal_count": len(all_rows),
    }
    OUT_JSON.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    write_csv(all_rows)
    write_report(all_rows, len(records))
    print(f"[OK] wrote {OUT_JSON}")
    print(f"[OK] wrote {OUT_CSV}")
    print(f"[OK] wrote {OUT_MD}")
    print(f"[INFO] proposals={len(all_rows)}")


if __name__ == "__main__":
    main()
