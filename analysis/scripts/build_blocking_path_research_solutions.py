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
    "SUMPAR": "https://www.sumpar.com/en/",
    "COMBIGO": "https://www.linkedin.com/company/combigo/",
    "MGA": "https://www.lafrenchfab.fr/entreprise/mga-groupe-arm/",
    "GATTEFIN": "https://gattefin.fr/",
    "MGR": "https://www.mgrfoamtex.com/products-2",
    "BASF_SEATING": "https://aerospace.basf.com/seating-components.html",
    "SENIOR_TH": "https://www.senior-thailand.com/Web/what_we_do",
    "JAMCO": "https://jamcointeriors.com/",
    "TE_DEUTSCH": "https://www.te.com/en/products/brands/deutsch.html?cat=1",
    "LIEBHERR": "https://www.liebherr.com/en-int/aerospace-and-transportation-systems/solutions-and-services/solutions-for-aerospace/on-board-systems/on-board-systems-7174957",
    "LIEBHERR_ELECTRONICS": "https://www.liebherr.com/shared/media/components/documents/control-technology-and-electronics/liebherr-electronics-for-aerospace.pdf",
    "LAEM_CHABANG": "https://lcp.port.co.th/cs/internet/lcp/Information.html",
    "NANTES_PORT": "https://www.nantes.port.fr/en",
    "SEKISUI_KYDEX": "https://kydex.com/library/kydex-5555rcl/",
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
    "Combigo as aluminium T2",
    "Combigo is active as T2 on A2017/A2024 aluminium lines, while the LCA/BOM says supplier/process is SUMPAR for these accoudoir aluminium rows.",
    "Replace T2=Combigo with SUMPAR internal machining/sheet-metal/process node. Keep T1=SUMPAR. Move or remove Combigo from industrial supply tiers.",
    "quantity_material.xlsx BOM exact rows: ACCOUDOIR ALLEE A2017/A2024 -> supplier SUMPAR, process USINAGE/TOLERIE, transport CAMION. SUMPAR states it supplies metal parts/sub-assemblies for aircraft and covers machining, sheet metal work and assembly. Combigo public profile is a travel-arrangements company.",
    "high",
    "Set T2 supplier_status=baseline_primary_assumed_internalized_process; process_owner=SUMPAR; mode T1->OEM=truck. Exclude Combigo from material/process tiers.",
    source_list("LOCAL_LCA", "SUMPAR", "COMBIGO"),
)

add(
    "18",
    "Combigo as aluminium T2 and wrong direct supplier",
    "Ens. Stowage lateral A2017 currently routes via Combigo/SUMPAR, but LCA/BOM exact row says MGA.",
    "Replace T1=SUMPAR with MGA Villeneuve-sur-Lot and replace T2=Combigo with MGA internal machining/forming process.",
    "quantity_material.xlsx BOM exact row: ENS STOWAGE LATERAL A2017 -> supplier MGA, process USINAGE/PLIAGE, transport CAMION. MGA is documented as aerospace subcontractor for equipped parts and mechanical sub-assemblies with aluminium machining capability.",
    "high",
    "Set primary chain Alcoa/AMAG -> MGA internal process -> MGA -> Safran. Keep other aluminium suppliers as inactive scenarios.",
    source_list("LOCAL_LCA", "MGA", "COMBIGO"),
)

add(
    "19",
    "Combigo as aluminium T2",
    "Palette optimisee A2017 uses Combigo as T2 but LCA/BOM says SUMPAR.",
    "Replace T2=Combigo with SUMPAR internal machining/forming process; keep T1=SUMPAR.",
    "quantity_material.xlsx BOM exact row: ENSEMBLE PALETTE OPTIMISEE A2017 -> supplier SUMPAR, process USINAGES, transport CAMION.",
    "high",
    "Use SUMPAR as process owner and direct supplier. Remove Combigo from active path.",
    source_list("LOCAL_LCA", "SUMPAR", "COMBIGO"),
)

add(
    "20,26",
    "Combigo as aluminium T2 and wrong direct supplier",
    "Tablette cocktail A2017/A2024 currently routes via Combigo/SUMPAR, but LCA/BOM exact rows say MGA.",
    "Replace T1=SUMPAR with MGA and T2=Combigo with MGA internal machining process.",
    "quantity_material.xlsx BOM exact rows: ENS TABLETTE COCKTAIL A2017/A2024 -> supplier MGA, process USINAGE, transport CAMION.",
    "high",
    "Set process_owner=MGA; T1=MGA; T1->OEM=truck.",
    source_list("LOCAL_LCA", "MGA", "COMBIGO"),
)

add(
    "21,22,23,24,27,28",
    "Combigo as aluminium T2 and wrong direct supplier",
    "Several A2017/A2024 parts currently route via Combigo/SUMPAR, but LCA/BOM exact rows point to ETS Gattefin.",
    "Replace T1=SUMPAR with ETS Gattefin and T2=Combigo with Gattefin internal machining process.",
    "quantity_material.xlsx exact rows: Tablette repas, Tetiere, Stowage assemble avec porte, Support ecran -> supplier GATTEFIN, transport CAMION. Gattefin is a precision machining and large-dimension machining company with aerospace sector activity.",
    "high",
    "Set process_owner=ETS Gattefin; T1=ETS Gattefin; keep T4/T3 aluminium source as material scenario until certificate.",
    source_list("LOCAL_LCA", "GATTEFIN", "COMBIGO"),
)

add(
    "54,55",
    "Combigo as aluminium T2 and wrong direct supplier",
    "Structure fauteuil A2017/A2024 currently routes via Combigo/SUMPAR, while LCA/BOM exact rows say Senior Aerospace Thailand.",
    "Replace T1=SUMPAR with Senior Aerospace Thailand and T2=Combigo with Senior internal machining/special process/assembly.",
    "quantity_material.xlsx BOM exact rows: ENS STRUCTURE FAUTEUIL A2017/A2024 -> supplier SENIOR AEROSPACE THAILAND, transport AVION. Senior Thailand documents precision machining from billet aluminium, surface treatments and complete seat-structure assemblies for Safran Seats France/GB.",
    "high",
    "Set T2=Senior internal process; T1=Senior Aerospace Thailand; T1->OEM mode=air+truck for ACV baseline, with sea+truck as cost/CO2 scenario.",
    source_list("LOCAL_LCA", "SENIOR_TH", "LAEM_CHABANG", "NANTES_PORT"),
)

add(
    "157,174,175",
    "MGR Foamtex as aluminium T2",
    "Seat-level aluminium aggregate lines use MGR Foamtex as T2, but MGR Foamtex is a foam/upholstery/interiors supplier, not an aluminium structural processor.",
    "Do not use these aggregate seat aluminium rows as active component supply paths. Either mark them scenario_aggregate_only or replace T2 with unknown aluminium structural processor under the real seat T1 after BOM validation.",
    "MGR Foamtex product pages describe SoftWall, foam systems and StyleCover upholstery. The mass confidence is low/global material family; the detailed aluminium component rows already carry better ACV matches.",
    "high",
    "Set simulation_supply_usable=false for active network, or keep as aggregate mass scenario only. Do not use MGR in aluminium T2. Use detailed A2017/A2024/A5086 records for aluminium stress tests.",
    source_list("LOCAL_LCA", "MGR"),
)

add(
    "86,87,88,89,90",
    "FRMC55 with steel upstream",
    "Cushion FRMC55 rows use Saarstahl/Aubert & Duval upstream, but LCA/BOM defines FRMC55 as fire-retardant flexible polyurethane foam and supplier FRANKLIN.",
    "Replace steel upstream with PU/textile chain: T4=BASF or unknown PU chemistry source; T3=unknown certified foam/fabric source; T2=FRANKLIN internal cutting/gluing; T1=FRANKLIN direct cushion supplier.",
    "quantity_material.xlsx: FRMC55 = EU28 polyurethane flexible foam with flame retardant. Cushion rows list process DECOUPES/COLLAGES, family SELLERIE, supplier FRANKLIN, Poland, transport AVION. BASF aerospace seating source supports PU/TPU/FST seating materials.",
    "high for removing steel; medium for BASF as active T4 without grade certificate",
    "Remove Saarstahl/Aubert from these FRMC55 active paths. Use FRANKLIN as direct supplier path; T1->OEM=air+truck per ACV. Keep BASF as candidate/assumption unless grade certificate confirms.",
    source_list("LOCAL_LCA", "BASF_SEATING"),
)

add(
    "91",
    "FRMC55 with steel upstream",
    "Stowage lateral FRMC55 row uses steel upstream and FRANKLIN/ESPACE, but LCA/BOM exact row points to MGA.",
    "Treat this as a small FRMC55 foam/material line embedded in the MGA stowage assembly: T4=unknown/BASF PU chemistry, T3=unknown foam source, T2=MGA internal integration, T1=MGA.",
    "quantity_material.xlsx BOM: ENS STOWAGE LATERAL FRMC55 -> supplier MGA, process USINAGE/PLIAGE, transport CAMION.",
    "medium_high",
    "Attach FRMC55 mass to MGA assembly path; do not route through steel mills.",
    source_list("LOCAL_LCA", "MGA", "BASF_SEATING"),
)

add(
    "92,93",
    "FRMC55 with steel upstream",
    "Manchette FRMC55 rows use steel upstream and FRANKLIN/ESPACE, while LCA/BOM exact rows point to MGR Angleterre.",
    "Replace steel upstream with PU foam chain and use MGR Foamtex as foam/interior supplier candidate for these manchette rows.",
    "quantity_material.xlsx BOM: MANCHETTE ACC MOBILE and MANCHETTE EQUIPEE FRMC55 -> supplier MGR ANGLETERRE, transport TRAIN. MGR Foamtex documents aircraft interior foam/upholstery systems.",
    "high for removing steel; medium for exact site/routing",
    "Set T2/T1 material supplier=MGR Foamtex for FRMC55 manchette lines or keep T1 assembly owner separate if drawing confirms ACH assembly.",
    source_list("LOCAL_LCA", "MGR", "BASF_SEATING"),
)

add(
    "74",
    "Electronics/COTS with steel/copper upstream",
    "Commande actionnement ECU routes through Saarstahl/Aurubis before Liebherr, which is not defensible without an electronics BOM.",
    "Keep T1=Liebherr Aerospace and T2=Liebherr internal electronics/routing package. Replace active T4/T3 with non-switchable COTS electronics placeholder until BOM/PN/AVL is available.",
    "Liebherr documents on-board electronics, flight control/actuation systems and aerospace control/power electronics. The PDF describes control and monitoring electronics, motor control power electronics and product examples.",
    "high",
    "Set T4/T3 status=do_not_infer_from_cots; active=false. Required data: part number, PCB/EMS, AVL, qualified component list.",
    source_list("LIEBHERR", "LIEBHERR_ELECTRONICS"),
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
    "SGL Carbon as T2 on steel Z10CNT18",
    "Z10CNT18 steel path uses SGL Carbon as T2, which is material-family incompatible.",
    "Replace T2=SGL Carbon with MGA internal machining/forming process. Keep T1=MGA. Keep T4/T3 steel mill/stockist as certificate-required candidates.",
    "MGA source documents aluminium, steel, stainless, titanium and Inconel machining, finishing and assembly for aerospace applications.",
    "high",
    "Set T2=internal_T1_process_MGA. Set Baosteel/Krupp as candidates requiring certificate/allocation; do not activate without material certificate.",
    source_list("MGA"),
)

add(
    "33,51,81,94,95,96,98,99,100,101,102,138",
    "Thailand -> France marked truck only",
    "Senior Aerospace Thailand paths have T1->OEM mode truck despite ~9,565 km to Safran France.",
    "Use two lane scenarios: baseline ACV air+truck where BOM says AVION for Senior rows; normal cost/CO2 scenario truck to Laem Chabang + sea to French/European port + truck/rail to Safran.",
    "Senior Thailand source gives Chonburi site and seat-structure capability for Safran Seats France/GB. Laem Chabang is Thailand main deep-sea port. Nantes Saint-Nazaire is a multimodal international logistics platform; Le Havre/other EU ports can be alternates if lane source is available.",
    "high",
    "Replace T1->OEM truck-only with lane_mode_set=[air+truck baseline where ACV=AVION, sea+truck scenario]. Add lane-level distances and ports.",
    source_list("LOCAL_LCA", "SENIOR_TH", "LAEM_CHABANG", "NANTES_PORT"),
)

add(
    "75,128,161,162,164,165,166",
    "Japan -> France marked truck only",
    "JAMCO Niigata paths have T1->OEM mode truck despite intercontinental route.",
    "Replace truck-only with truck+sea+truck baseline for bulky interiors, and truck+air+truck expedite scenario. For rows with ACV percentage/low confidence, keep as aggregate scenario not primary quantitative truth.",
    "Jamco source lists aircraft interiors capabilities and locations including Niigata, Miyazaki and Philippines. The geography requires sea/air between Japan/Philippines and France.",
    "medium_high",
    "Add lane-level routes: plant -> Japan/Philippines port or airport -> French/EU port or CDG -> Safran. Mark transport_source=geography_assumption until freight data is provided.",
    source_list("JAMCO", "NANTES_PORT"),
)

add(
    "103-109,75",
    "Kydex/Lexan/polymer path validation",
    "Thermoplastic interior paths are plausible, but active supplier allocation and exact grade need validation.",
    "Use SEKISUI KYDEX or SABIC Lexan family as material candidate depending exact material. Keep thermoforming/internal T2 under actual T1 only if drawing/routing confirms.",
    "SEKISUI KYDEX documents aviation thermoplastic sheets formulated for aviation fire-safety needs. BASF/SABIC/polymer actors are plausible by material family but not automatically active without grade certificate.",
    "medium",
    "Set material supplier candidates active=false unless certificate/grade confirms; split Kydex vs Lexan vs generic NIDA/plastic rows.",
    source_list("SEKISUI_KYDEX", "LOCAL_LCA"),
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
        "1. Retirer `Combigo` des T2 industriels aluminium : Combigo est une travel-tech, pas un transformateur aluminium. Remplacer par le fournisseur/process exact issu de l'ACV : SUMPAR, MGA, Gattefin ou Senior selon le composant.",
        "2. Retirer `MGR Foamtex` des T2 aluminium : MGR est coherent pour mousse/habillage, pas pour aluminium. Les lignes siege aluminium agregees doivent etre traitees comme scenarios agreges ou decomposees.",
        "3. Corriger `FRMC55` : l'ACV le definit comme mousse polyurethane flexible retardee flamme. Les chemins Saarstahl/Aubert sont faux pour ces lignes.",
        "4. Corriger COTS/electronique : ne pas inferer T4/T3 sans BOM/part number. Garder Liebherr/TE/Thales comme T1/T2 selon role, mais upstream inactive.",
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
