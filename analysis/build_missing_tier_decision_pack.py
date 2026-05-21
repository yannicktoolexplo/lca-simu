#!/usr/bin/env python3
"""Build a review pack for the most probable missing-tier resolution."""

from __future__ import annotations

import csv
import json
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
FINAL_JSON = ROOT / "analysis" / "output8_GEO_normalized_final_corrected.json"
PROPOSALS_CSV = ROOT / "analysis" / "output8_GEO_missing_tier_proposals.csv"
OUT_CSV = ROOT / "analysis" / "output8_GEO_missing_tier_most_probable.csv"
OUT_MD = ROOT / "analysis" / "output8_GEO_missing_tier_most_probable.md"
OUT_PROMPT = ROOT / "analysis" / "output8_GEO_missing_tier_chatgpt_prompt.md"

ROLE_ORDER = [
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


def load_records() -> dict[int, dict[str, Any]]:
    source = json.loads(FINAL_JSON.read_text(encoding="utf-8"))
    return {index: record for index, record in enumerate(source.get("records") or [], start=1)}


def role_names(record: dict[str, Any], role: str, primary: bool | None = None) -> list[str]:
    values: list[str] = []
    for supplier in record.get("suppliers") or []:
        if not isinstance(supplier, dict) or supplier.get("role_hint") != role:
            continue
        if primary is not None and bool(supplier.get("is_primary")) != primary:
            continue
        name = str(supplier.get("name") or "").strip()
        if name:
            values.append(name)
    return values


def chain_summary(record: dict[str, Any]) -> str:
    chunks: list[str] = []
    for role in ROLE_ORDER:
        primaries = role_names(record, role, primary=True)
        alternates = role_names(record, role, primary=False)
        if primaries:
            chunks.append(f"{ROLE_CODE[role]}={', '.join(primaries[:3])}")
        elif alternates:
            chunks.append(f"{ROLE_CODE[role]}=no_primary({', '.join(alternates[:3])})")
        else:
            chunks.append(f"{ROLE_CODE[role]}=MISSING")
    return " | ".join(chunks)


def resolution(row: dict[str, str], record: dict[str, Any]) -> tuple[str, str, str, str]:
    action = row["modeling_action"]
    missing = row["missing_tier_code"]
    candidate = row["candidate_name"]
    confidence = row["confidence"]
    primary_t1 = ", ".join(role_names(record, "tier1", primary=True)[:3])

    if action == "model_as_internalized_T2_at_T1_or_validate_subcontractor":
        return (
            "probable_internalized_process",
            f"{missing} le plus probable: operation internalisee chez le T1 primaire ({primary_t1 or candidate}).",
            "Ne pas creer un fournisseur externe; creer un noeud process virtuel T2 rattache au T1 si la simulation exige un T2 explicite.",
            "Valider gamme/process: usinage, formage, decoupe, traitement, kitting ou assemblage chez le T1.",
        )
    if action in {
        "choose_steelmaker_by_grade_certificate_before_activation",
        "choose_aluminium_source_by_material_certificate_before_activation",
        "choose_copper_source_by_material_certificate_before_activation",
    }:
        return (
            "probable_material_certificate_source",
            f"{missing} le plus probable: fournisseur matiere primaire a choisir via certificat matiere, candidats: {candidate}.",
            "Garder en candidat non actif tant que le certificat matiere ou l'achat ne donne pas le producteur/site exact.",
            "Valider nuance, certificat EN/AMS, mill, pays, site, et allocation.",
        )
    if action in {
        "add_material_family_T4_after_material_spec_validation",
        "choose_candidate_by_material_grade_before_activation",
        "candidate_only_until_silicone_grade_traceability",
        "split_material_before_supplier_activation",
    }:
        return (
            "probable_material_family_source",
            f"{missing} le plus probable: source amont de famille matiere, candidats/famille: {candidate}.",
            "Ne pas activer comme fournisseur unique; utiliser comme hypothese de famille tant que la specification matiere n'est pas connue.",
            "Valider composition exacte, grade, fiche matiere et fournisseur reel.",
        )
    if action == "select_existing_material_processor_based_on_grade_and_traceability":
        return (
            "probable_existing_material_processor",
            f"{missing} le plus probable: un transformateur matiere deja present dans la supply, candidats: {candidate}.",
            "Prioriser le candidat deja utilise sur la meme famille matiere; activer seulement avec traceabilite grade/site.",
            "Valider stockiste/forge/lamineur/extrudeur exact et flux vers le T1.",
        )
    if action in {
        "candidate_only_until_part_number_supplier_validation",
        "validate_program_supplier_or_model_as_internal_Safran_operation",
    }:
        return (
            "probable_direct_supplier_requires_part_number",
            f"{missing} le plus probable: integrateur ou fournisseur direct a confirmer par part number, candidats: {candidate}.",
            "Ne pas activer avant d'avoir le fournisseur programme ou le part number; sinon modeliser comme operation interne Safran.",
            "Valider part number, fournisseur programme, site, statut qualifie, lead time et allocation.",
        )
    if action in {
        "keep_as_COTS_upstream_context_not_supply_tier",
        "keep_out_of_switchable_supplier_network_until_exact_BOM",
    }:
        return (
            "do_not_infer_from_cots",
            f"{missing}: ne pas inferer depuis les marques COTS; il faut la BOM electronique exacte.",
            "Conserver hors reseau switchable; ajouter seulement le fournisseur de carte/equipement exact si connu.",
            "Valider BOM electronique, EMS/ODM, integrateur, distributeur, et reference composant.",
        )
    if action == "keep_gap_bridge_until_purchase_or_routing_data":
        return (
            "probable_process_unknown_owner",
            f"{missing} le plus probable: process intermediaire reel mais proprietaire inconnu.",
            "Garder le pont visuel; ne pas creer de fournisseur tant que routing/achat ne donne pas le site.",
            "Valider routing industriel, sous-traitant eventuel, et responsabilite T1/T2.",
        )
    return (
        "manual_review_required",
        f"{missing}: tier probable non determinable sans information metier supplementaire.",
        "Garder hors simulation active.",
        "Faire valider par achat/engineering avec BOM, drawing, routing ou certificat.",
    )


def build_rows() -> list[dict[str, str]]:
    records = load_records()
    proposals = list(csv.DictReader(PROPOSALS_CSV.open(encoding="utf-8-sig")))
    rows: list[dict[str, str]] = []
    for row in proposals:
        record = records[int(row["record_index"])]
        resolution_class, most_probable, modeling_decision, validation_question = resolution(row, record)
        rows.append(
            {
                "record_index": row["record_index"],
                "system": row["system"],
                "component": row["component"],
                "material_family": row["material_family"],
                "present_chain": chain_summary(record),
                "missing_tier_code": row["missing_tier_code"],
                "resolution_class": resolution_class,
                "most_probable_resolution": most_probable,
                "recommended_modeling_decision": modeling_decision,
                "validation_question": validation_question,
                "candidate_name": row["candidate_name"],
                "confidence": row["confidence"],
                "source_urls": row["source_urls"],
            }
        )
    return rows


def write_csv(rows: list[dict[str, str]]) -> None:
    fields = [
        "record_index",
        "system",
        "component",
        "material_family",
        "present_chain",
        "missing_tier_code",
        "resolution_class",
        "most_probable_resolution",
        "recommended_modeling_decision",
        "validation_question",
        "candidate_name",
        "confidence",
        "source_urls",
    ]
    with OUT_CSV.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def write_md(rows: list[dict[str, str]]) -> None:
    by_class = Counter(row["resolution_class"] for row in rows)
    by_tier = Counter(row["missing_tier_code"] for row in rows)
    by_conf = Counter(row["confidence"] for row in rows)
    lines = [
        "# Most probable missing-tier resolutions",
        "",
        f"- Source JSON: `{FINAL_JSON.as_posix()}`",
        f"- Input proposal CSV: `{PROPOSALS_CSV.as_posix()}`",
        f"- Output CSV: `{OUT_CSV.as_posix()}`",
        f"- ChatGPT prompt: `{OUT_PROMPT.as_posix()}`",
        "",
        "## Summary",
        "",
        f"- Missing-tier rows: {len(rows)}",
        f"- By tier: {', '.join(f'{key}={value}' for key, value in by_tier.most_common())}",
        f"- By confidence: {', '.join(f'{key}={value}' for key, value in by_conf.most_common())}",
        f"- By resolution class: {', '.join(f'{key}={value}' for key, value in by_class.most_common())}",
        "",
        "## Rule",
        "",
        "- If a metal line misses T2, the most probable resolution is usually an internalized T2 process at the primary T1, not an invented external supplier.",
        "- If a material line misses T4, the most probable resolution is a material-certificate source, not a named supplier unless the grade/site is known.",
        "- If an electronics/COTS line misses upstream tiers, do not infer from brand names; require exact BOM/part-number data.",
        "- Keep all rows non-active until business validation promotes them.",
        "",
        "## Highest Confidence Rows",
        "",
    ]
    for row in rows:
        if row["confidence"] not in {"medium_high", "high"}:
            continue
        lines.append(
            f"- R{row['record_index']} `{row['component']}` {row['missing_tier_code']}: "
            f"{row['most_probable_resolution']}"
        )
    OUT_MD.write_text("\n".join(lines), encoding="utf-8")


def write_prompt(rows: list[dict[str, str]]) -> None:
    table_lines = [
        "record_index;system;component;family;present_chain;missing_tier;candidate;confidence;question"
    ]
    for row in rows:
        table_lines.append(
            ";".join(
                [
                    row["record_index"],
                    row["system"].replace(";", ","),
                    row["component"].replace(";", ","),
                    row["material_family"],
                    row["present_chain"].replace(";", ","),
                    row["missing_tier_code"],
                    row["candidate_name"].replace(";", ","),
                    row["confidence"],
                    row["validation_question"].replace(";", ","),
                ]
            )
        )
    prompt = f"""Tu es un expert supply chain aeronautique et achats industriels cabine/siege avion.

Objectif: verifier les tiers manquants d'une supply chain de siege aeronautique, sans inventer de fournisseur.

Regles:
- Ne propose un fournisseur actif que si tu peux justifier le role par une source metier fiable ou par la chaine deja presente.
- Si le tier manquant est probablement une operation internalisee chez le T1, dis-le explicitement au lieu d'inventer un T2.
- Pour les lignes metal, distingue T4 producteur matiere, T3 premiere transformation/stockiste/forge/laminage, T2 usinage/formage/traitement, T1 fournisseur direct/module.
- Pour l'electronique/COTS, n'infere pas T3/T4 depuis des marques generiques; demande la BOM exacte ou le part number.
- Reponds sous forme de tableau avec: record_index, missing_tier, decision, fournisseur/processus le plus probable, confiance, justification, source_url, action simulation.
- Si la bonne reponse est "ne pas completer", indique-le clairement.

Donnees a verifier:

```csv
{chr(10).join(table_lines)}
```
"""
    OUT_PROMPT.write_text(prompt, encoding="utf-8")


def main() -> None:
    rows = build_rows()
    write_csv(rows)
    write_md(rows)
    write_prompt(rows)
    print(f"[OK] wrote {OUT_CSV}")
    print(f"[OK] wrote {OUT_MD}")
    print(f"[OK] wrote {OUT_PROMPT}")
    print(f"[INFO] rows={len(rows)}")


if __name__ == "__main__":
    main()
