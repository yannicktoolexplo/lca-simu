#!/usr/bin/env python3
"""Build a sourced solution plan for the main blocking supply paths."""

from __future__ import annotations

import csv
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
OUT_CSV = BASE_DIR / "output8_GEO_blocking_path_researched_solutions.csv"
OUT_MD = BASE_DIR / "output8_GEO_blocking_path_researched_solutions.md"


SOURCES = {
    "LOCAL_LCA": "data/quantity_material.xlsx",
    "FRN-72A106312E8F95": "https://www.FRN-72A106312E8F95.com/en/",
    "FRN-0A33FC5A2472A2": "https://www.linkedin.com/company/FRN-0A33FC5A2472A2/",
    "FRN-4461497D8EA815": "https://www.lafrenchfab.fr/entreprise/FRN-4461497D8EA815-groupe-arm/",
    "FRN-FCB0C890EFA2B8": "https://sources.invalid/FRN-0B41BF5B9E4B4E/3edb20f3674cd12c",
    "MGR": "https://www.mgrfoamtex.com/products-2",
    "FRN-301ED6D3E70080_SEATING": "https://aerospace.FRN-301ED6D3E70080.com/seating-components.html",
    "SENIOR_TH": "https://www.senior-thailand.com/Web/what_we_do",
    "JAMCO": "https://jamcointeriors.com/",
    "TE_DEUTSCH": "https://www.te.com/en/products/brands/deutsch.html?cat=1",
    "FRN-52D5AE23024E5C": "https://www.FRN-52D5AE23024E5C.com/en-int/aerospace-and-transportation-systems/solutions-and-services/solutions-for-aerospace/on-board-systems/on-board-systems-7174957",
    "FRN-52D5AE23024E5C_ELECTRONICS": "https://www.FRN-52D5AE23024E5C.com/shared/media/components/documents/control-technology-and-electronics/FRN-52D5AE23024E5C-electronics-for-aerospace.pdf",
    "LAEM_CHABANG": "https://lcp.port.co.th/cs/internet/lcp/Information.html",
    "NANTES_PORT": "https://www.nantes.port.fr/en",
    "SEKISUI_MAT-08814168D3466E": "https://MAT-08814168D3466E.com/library/MAT-08814168D3466E-5555rcl/",
}


def source_list(*keys: str) -> str:
    return " | ".join(f"{key}: {SOURCES[key]}" for key in keys)


rows: list[dict[str, str]] = []


def add(
    record_indices: str,
    blocker: str,
    current_chain_issue: str,
    proposed_solution: str,
    evidence: str,
    confidence: str,
    simulation_action: str,
    sources: str,
) -> None:
    rows.append(
        {
            "record_indices": record_indices,
            "blocker": blocker,
            "current_chain_issue": current_chain_issue,
            "proposed_solution": proposed_solution,
            "evidence": evidence,
            "confidence": confidence,
            "simulation_action": simulation_action,
            "sources": sources,
        }
    )


add(
    "17,25,167",
    "FRN-0A33FC5A2472A2 as aluminium T2",
    "FRN-0A33FC5A2472A2 is active as T2 on A2017/A2024 aluminium lines, while the LCA/BOM says supplier/process is FRN-72A106312E8F95 for these accoudoir aluminium rows.",
    "Replace T2=FRN-0A33FC5A2472A2 with FRN-72A106312E8F95 internal machining/sheet-metal/process node. Keep T1=FRN-72A106312E8F95. Move or remove FRN-0A33FC5A2472A2 from industrial supply tiers.",
    "quantity_material.xlsx BOM exact rows: ACCOUDOIR ALLEE A2017/A2024 -> supplier FRN-72A106312E8F95, process USINAGE/TOLERIE, transport CAMION. FRN-72A106312E8F95 states it supplies metal parts/sub-assemblies for aircraft and covers machining, sheet metal work and assembly. FRN-0A33FC5A2472A2 public profile is a travel-arrangements company.",
    "high",
    "Set T2 supplier_status=baseline_primary_assumed_internalized_process; process_owner=FRN-72A106312E8F95; mode T1->OEM=truck. Exclude FRN-0A33FC5A2472A2 from material/process tiers.",
    source_list("LOCAL_LCA", "FRN-72A106312E8F95", "FRN-0A33FC5A2472A2"),
)

add(
    "18",
    "FRN-0A33FC5A2472A2 as aluminium T2 and wrong direct supplier",
    "Ens. Stowage lateral A2017 currently routes via FRN-0A33FC5A2472A2/FRN-72A106312E8F95, but LCA/BOM exact row says FRN-4461497D8EA815.",
    "Replace T1=FRN-72A106312E8F95 with FRN-0459D8A8B731DA and replace T2=FRN-0A33FC5A2472A2 with FRN-4461497D8EA815 internal machining/forming process.",
    "quantity_material.xlsx BOM exact row: ENS STOWAGE LATERAL A2017 -> supplier FRN-4461497D8EA815, process USINAGE/PLIAGE, transport CAMION. FRN-4461497D8EA815 is documented as aerospace subcontractor for equipped parts and mechanical sub-assemblies with aluminium machining capability.",
    "high",
    "Set primary chain FRN-34B2AC7037114C/AMAG -> FRN-4461497D8EA815 internal process -> FRN-4461497D8EA815 -> FRN-F1F796DB13C8E2. Keep other aluminium suppliers as inactive scenarios.",
    source_list("LOCAL_LCA", "FRN-4461497D8EA815", "FRN-0A33FC5A2472A2"),
)

add(
    "19",
    "FRN-0A33FC5A2472A2 as aluminium T2",
    "Palette optimisee A2017 uses FRN-0A33FC5A2472A2 as T2 but LCA/BOM says FRN-72A106312E8F95.",
    "Replace T2=FRN-0A33FC5A2472A2 with FRN-72A106312E8F95 internal machining/forming process; keep T1=FRN-72A106312E8F95.",
    "quantity_material.xlsx BOM exact row: ENSEMBLE PALETTE OPTIMISEE A2017 -> supplier FRN-72A106312E8F95, process USINAGES, transport CAMION.",
    "high",
    "Use FRN-72A106312E8F95 as process owner and direct supplier. Remove FRN-0A33FC5A2472A2 from active path.",
    source_list("LOCAL_LCA", "FRN-72A106312E8F95", "FRN-0A33FC5A2472A2"),
)

add(
    "20,26",
    "FRN-0A33FC5A2472A2 as aluminium T2 and wrong direct supplier",
    "Tablette cocktail A2017/A2024 currently routes via FRN-0A33FC5A2472A2/FRN-72A106312E8F95, but LCA/BOM exact rows say FRN-4461497D8EA815.",
    "Replace T1=FRN-72A106312E8F95 with FRN-4461497D8EA815 and T2=FRN-0A33FC5A2472A2 with FRN-4461497D8EA815 internal machining process.",
    "quantity_material.xlsx BOM exact rows: ENS TABLETTE COCKTAIL A2017/A2024 -> supplier FRN-4461497D8EA815, process USINAGE, transport CAMION.",
    "high",
    "Set process_owner=FRN-4461497D8EA815; T1=FRN-4461497D8EA815; T1->OEM=truck.",
    source_list("LOCAL_LCA", "FRN-4461497D8EA815", "FRN-0A33FC5A2472A2"),
)

add(
    "21,22,23,24,27,28",
    "FRN-0A33FC5A2472A2 as aluminium T2 and wrong direct supplier",
    "Several A2017/A2024 parts currently route via FRN-0A33FC5A2472A2/FRN-72A106312E8F95, but LCA/BOM exact rows point to FRN-0B41BF5B9E4B4E.",
    "Replace T1=FRN-72A106312E8F95 with FRN-0B41BF5B9E4B4E and T2=FRN-0A33FC5A2472A2 with FRN-FCB0C890EFA2B8 internal machining process.",
    "quantity_material.xlsx exact rows: Tablette repas, Tetiere, Stowage assemble avec porte, Support ecran -> supplier FRN-FCB0C890EFA2B8, transport CAMION. FRN-FCB0C890EFA2B8 is a precision machining and large-dimension machining company with aerospace sector activity.",
    "high",
    "Set process_owner=FRN-0B41BF5B9E4B4E; T1=FRN-0B41BF5B9E4B4E; keep T4/T3 aluminium source as material scenario until certificate.",
    source_list("LOCAL_LCA", "FRN-FCB0C890EFA2B8", "FRN-0A33FC5A2472A2"),
)

add(
    "54,55",
    "FRN-0A33FC5A2472A2 as aluminium T2 and wrong direct supplier",
    "Structure fauteuil A2017/A2024 currently routes via FRN-0A33FC5A2472A2/FRN-72A106312E8F95, while LCA/BOM exact rows say FRN-98C883F706EF89.",
    "Replace T1=FRN-72A106312E8F95 with FRN-98C883F706EF89 and T2=FRN-0A33FC5A2472A2 with Senior internal machining/special process/assembly.",
    "quantity_material.xlsx BOM exact rows: ENS STRUCTURE FAUTEUIL A2017/A2024 -> supplier FRN-98C883F706EF89, transport AVION. Senior Thailand documents precision machining from billet aluminium, surface treatments and complete seat-structure assemblies for FRN-AA08AEDDCB94EB France/GB.",
    "high",
    "Set T2=Senior internal process; T1=FRN-98C883F706EF89; T1->OEM mode=air+truck for ACV baseline, with sea+truck as cost/CO2 scenario.",
    source_list("LOCAL_LCA", "SENIOR_TH", "LAEM_CHABANG", "NANTES_PORT"),
)

add(
    "157,174,175",
    "FRN-54423E8FD293B7 as aluminium T2",
    "Seat-level aluminium aggregate lines use FRN-54423E8FD293B7 as T2, but FRN-54423E8FD293B7 is a foam/upholstery/interiors supplier, not an aluminium structural processor.",
    "Do not use these aggregate seat aluminium rows as active component supply paths. Either mark them scenario_aggregate_only or replace T2 with unknown aluminium structural processor under the real seat T1 after BOM validation.",
    "FRN-54423E8FD293B7 product pages describe SoftWall, foam systems and StyleCover upholstery. The mass confidence is low/global material family; the detailed aluminium component rows already carry better ACV matches.",
    "high",
    "Set simulation_supply_usable=false for active network, or keep as aggregate mass scenario only. Do not use MGR in aluminium T2. Use detailed A2017/A2024/A5086 records for aluminium stress tests.",
    source_list("LOCAL_LCA", "MGR"),
)

add(
    "86,87,88,89,90",
    "FRMC55 with steel upstream",
    "Cushion FRMC55 rows use FRN-19E8A3B02C44AE/FRN-83186B5AEF84D8 upstream, but LCA/BOM defines FRMC55 as fire-retardant flexible polyurethane foam and supplier FRN-0F389602532562.",
    "Replace steel upstream with PU/textile chain: T4=FRN-301ED6D3E70080 or unknown PU chemistry source; T3=unknown certified foam/fabric source; T2=FRN-0F389602532562 internal cutting/gluing; T1=FRN-0F389602532562 direct cushion supplier.",
    "quantity_material.xlsx: FRMC55 = EU28 polyurethane flexible foam with flame retardant. Cushion rows list process DECOUPES/COLLAGES, family SELLERIE, supplier FRN-0F389602532562, Poland, transport AVION. FRN-301ED6D3E70080 aerospace seating source supports PU/TPU/FST seating materials.",
    "high for removing steel; medium for FRN-301ED6D3E70080 as active T4 without grade certificate",
    "Remove FRN-19E8A3B02C44AE/Aubert from these FRMC55 active paths. Use FRN-0F389602532562 as direct supplier path; T1->OEM=air+truck per ACV. Keep FRN-301ED6D3E70080 as candidate/assumption unless grade certificate confirms.",
    source_list("LOCAL_LCA", "FRN-301ED6D3E70080_SEATING"),
)

add(
    "91",
    "FRMC55 with steel upstream",
    "Stowage lateral FRMC55 row uses steel upstream and FRN-0F389602532562/FRN-45A091671294B0, but LCA/BOM exact row points to FRN-4461497D8EA815.",
    "Treat this as a small FRMC55 foam/material line embedded in the FRN-4461497D8EA815 stowage assembly: T4=unknown/FRN-301ED6D3E70080 PU chemistry, T3=unknown foam source, T2=FRN-4461497D8EA815 internal integration, T1=FRN-4461497D8EA815.",
    "quantity_material.xlsx BOM: ENS STOWAGE LATERAL FRMC55 -> supplier FRN-4461497D8EA815, process USINAGE/PLIAGE, transport CAMION.",
    "medium_high",
    "Attach FRMC55 mass to FRN-4461497D8EA815 assembly path; do not route through steel mills.",
    source_list("LOCAL_LCA", "FRN-4461497D8EA815", "FRN-301ED6D3E70080_SEATING"),
)

add(
    "92,93",
    "FRMC55 with steel upstream",
    "Manchette FRMC55 rows use steel upstream and FRN-0F389602532562/FRN-45A091671294B0, while LCA/BOM exact rows point to FRN-74BFD09008994B.",
    "Replace steel upstream with PU foam chain and use FRN-54423E8FD293B7 as foam/interior supplier candidate for these manchette rows.",
    "quantity_material.xlsx BOM: MANCHETTE ACC MOBILE and MANCHETTE EQUIPEE FRMC55 -> supplier FRN-74BFD09008994B, transport TRAIN. FRN-54423E8FD293B7 documents aircraft interior foam/upholstery systems.",
    "high for removing steel; medium for exact site/routing",
    "Set T2/T1 material supplier=FRN-54423E8FD293B7 for FRMC55 manchette lines or keep T1 assembly owner separate if drawing confirms FRN-72A8D622F0F88D assembly.",
    source_list("LOCAL_LCA", "MGR", "FRN-301ED6D3E70080_SEATING"),
)

add(
    "74",
    "Electronics/COTS with steel/copper upstream",
    "Commande actionnement ECU routes through FRN-19E8A3B02C44AE/FRN-1FBDAEFBEB869B before FRN-52D5AE23024E5C, which is not defensible without an electronics BOM.",
    "Keep T1=FRN-42EDB7DB79E4B3 and T2=FRN-52D5AE23024E5C internal electronics/routing package. Replace active T4/T3 with non-switchable COTS electronics placeholder until BOM/PN/AVL is available.",
    "FRN-52D5AE23024E5C documents on-board electronics, flight control/actuation systems and aerospace control/power electronics. The PDF describes control and monitoring electronics, motor control power electronics and product examples.",
    "high",
    "Set T4/T3 status=do_not_infer_from_cots; active=false. Required data: part number, PCB/EMS, AVL, qualified component list.",
    source_list("FRN-52D5AE23024E5C", "FRN-52D5AE23024E5C_ELECTRONICS"),
)

add(
    "10,71,73,78,121,126,153",
    "Electronics/COTS upstream not defensible",
    "Electronics, IFE, display, powerbox, connector/cable rows should not infer metal/polymer raw tiers as active supply without BOM.",
    "For IFE/display/powerbox: use program supplier placeholder or T1 candidate only. For TE cable/connector rows: keep TE/DEUTSCH connector path, but do not infer T4/T3.",
    "TE DEUTSCH connectors are documented for aerospace/defense applications. Electronics sub-tiers require BOM/PN and AVL. Existing COTS rules already say do not infer upstream.",
    "medium_high",
    "Mark upstream T4/T3 inactive COTS placeholder; require BOM before switch stress tests. Keep TE as T1/T2 connector supplier only where part number confirms.",
    source_list("TE_DEUTSCH"),
)

add(
    "151",
    "FRN-AEA0242468D6C5 as T2 on steel Z10CNT18",
    "Z10CNT18 steel path uses FRN-AEA0242468D6C5 as T2, which is material-family incompatible.",
    "Replace T2=FRN-AEA0242468D6C5 with FRN-4461497D8EA815 internal machining/forming process. Keep T1=FRN-4461497D8EA815. Keep T4/T3 steel mill/stockist as certificate-required candidates.",
    "FRN-4461497D8EA815 source documents aluminium, steel, stainless, titanium and Inconel machining, finishing and assembly for aerospace applications.",
    "high",
    "Set T2=internal_T1_process_FRN-4461497D8EA815. Set Baosteel/FRN-8CF694326AFCE1 as candidates requiring certificate/allocation; do not activate without material certificate.",
    source_list("FRN-4461497D8EA815"),
)

add(
    "33,51,81,94,95,96,98,99,100,101,102,138",
    "Thailand -> France marked truck only",
    "FRN-98C883F706EF89 paths have T1->OEM mode truck despite ~9,565 km to FRN-F1F796DB13C8E2 France.",
    "Use two lane scenarios: baseline ACV air+truck where BOM says AVION for Senior rows; normal cost/CO2 scenario truck to Laem Chabang + sea to French/European port + truck/rail to FRN-F1F796DB13C8E2.",
    "Senior Thailand source gives Chonburi site and seat-structure capability for FRN-AA08AEDDCB94EB France/GB. Laem Chabang is Thailand main deep-sea port. Nantes Saint-Nazaire is a multimodal international logistics platform; Le Havre/other EU ports can be alternates if lane source is available.",
    "high",
    "Replace T1->OEM truck-only with lane_mode_set=[air+truck baseline where ACV=AVION, sea+truck scenario]. Add lane-level distances and ports.",
    source_list("LOCAL_LCA", "SENIOR_TH", "LAEM_CHABANG", "NANTES_PORT"),
)

add(
    "75,128,161,162,164,165,166",
    "Japan -> France marked truck only",
    "FRN-4B0BBE731CA526 paths have T1->OEM mode truck despite intercontinental route.",
    "Replace truck-only with truck+sea+truck baseline for bulky interiors, and truck+air+truck expedite scenario. For rows with ACV percentage/low confidence, keep as aggregate scenario not primary quantitative truth.",
    "Jamco source lists aircraft interiors capabilities and locations including Niigata, Miyazaki and Philippines. The geography requires sea/air between Japan/Philippines and France.",
    "medium_high",
    "Add lane-level routes: plant -> Japan/Philippines port or airport -> French/EU port or CDG -> FRN-F1F796DB13C8E2. Mark transport_source=geography_assumption until freight data is provided.",
    source_list("JAMCO", "NANTES_PORT"),
)

add(
    "103-109,75",
    "MAT-08814168D3466E/MAT-27B24E5EE0075C/polymer path validation",
    "Thermoplastic interior paths are plausible, but active supplier allocation and exact grade need validation.",
    "Use SEKISUI MAT-08814168D3466E or FRN-CEF93150EAB259 MAT-27B24E5EE0075C family as material candidate depending exact material. Keep thermoforming/internal T2 under actual T1 only if drawing/routing confirms.",
    "SEKISUI MAT-08814168D3466E documents aviation thermoplastic sheets formulated for aviation fire-safety needs. FRN-301ED6D3E70080/FRN-CEF93150EAB259/polymer actors are plausible by material family but not automatically active without grade certificate.",
    "medium",
    "Set material supplier candidates active=false unless certificate/grade confirms; split MAT-08814168D3466E vs MAT-27B24E5EE0075C vs generic NIDA/plastic rows.",
    source_list("SEKISUI_MAT-08814168D3466E", "LOCAL_LCA"),
)


def write_csv() -> None:
    with OUT_CSV.open("w", encoding="utf-8-sig", newline="") as handle:
        fieldnames = list(rows[0].keys())
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_md() -> None:
    lines = [
        "# Solutions sourcees pour les points bloquants principaux",
        "",
        "Objectif : corriger les chemins principaux avant stress tests supply. Les propositions ci-dessous combinent les preuves locales `quantity_material.xlsx` et les sources metier publiques.",
        "",
        "## Synthese prioritaire",
        "",
        "1. Retirer `FRN-0A33FC5A2472A2` des T2 industriels aluminium : FRN-0A33FC5A2472A2 est une travel-tech, pas un transformateur aluminium. Remplacer par le fournisseur/process exact issu de l'ACV : FRN-72A106312E8F95, FRN-4461497D8EA815, FRN-FCB0C890EFA2B8 ou Senior selon le composant.",
        "2. Retirer `FRN-54423E8FD293B7` des T2 aluminium : MGR est coherent pour mousse/habillage, pas pour aluminium. Les lignes siege aluminium agregees doivent etre traitees comme scenarios agreges ou decomposees.",
        "3. Corriger `FRMC55` : l'ACV le definit comme mousse polyurethane flexible retardee flamme. Les chemins FRN-19E8A3B02C44AE/Aubert sont faux pour ces lignes.",
        "4. Corriger COTS/electronique : ne pas inferer T4/T3 sans BOM/part number. Garder FRN-52D5AE23024E5C/TE/FRN-DE6523078882AF comme T1/T2 selon role, mais upstream inactive.",
        "5. Corriger transport long-courrier : Asie -> France ne peut pas etre `truck` seul. Ajouter air+truck et sea+truck selon scenario.",
        "",
        "## Actions detaillees",
        "",
        "| Records | Blocage | Solution | Confiance | Action simulation |",
        "|---:|---|---|---|---|",
    ]
    for row in rows:
        lines.append(
            f"| {row['record_indices']} | {row['blocker']} | {row['proposed_solution']} | {row['confidence']} | {row['simulation_action']} |"
        )
    lines.extend(
        [
            "",
            "## Sources principales",
            "",
        ]
    )
    for key, value in SOURCES.items():
        lines.append(f"- `{key}`: {value}")
    lines.extend(
        [
            "",
            "## Fichier CSV",
            "",
            f"- `{OUT_CSV.as_posix()}`",
        ]
    )
    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    write_csv()
    write_md()


if __name__ == "__main__":
    main()
