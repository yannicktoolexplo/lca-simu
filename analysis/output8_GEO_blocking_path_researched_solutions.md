# Solutions sourcees pour les points bloquants principaux

Objectif : corriger les chemins principaux avant stress tests supply. Les propositions ci-dessous combinent les preuves locales `quantity_material.xlsx` et les sources metier publiques.

## Synthese prioritaire

1. Retirer `Combigo` des T2 industriels aluminium : Combigo est une travel-tech, pas un transformateur aluminium. Remplacer par le fournisseur/process exact issu de l'ACV : SUMPAR, MGA, Gattefin ou Senior selon le composant.
2. Retirer `MGR Foamtex` des T2 aluminium : MGR est coherent pour mousse/habillage, pas pour aluminium. Les lignes siege aluminium agregees doivent etre traitees comme scenarios agreges ou decomposees.
3. Corriger `FRMC55` : l'ACV le definit comme mousse polyurethane flexible retardee flamme. Les chemins Saarstahl/Aubert sont faux pour ces lignes.
4. Corriger COTS/electronique : ne pas inferer T4/T3 sans BOM/part number. Garder Liebherr/TE/Thales comme T1/T2 selon role, mais upstream inactive.
5. Corriger transport long-courrier : Asie -> France ne peut pas etre `truck` seul. Ajouter air+truck et sea+truck selon scenario.

## Actions detaillees

| Records | Blocage | Solution | Confiance | Action simulation |
|---:|---|---|---|---|
| 17,25,167 | Combigo as aluminium T2 | Replace T2=Combigo with SUMPAR internal machining/sheet-metal/process node. Keep T1=SUMPAR. Move or remove Combigo from industrial supply tiers. | high | Set T2 supplier_status=baseline_primary_assumed_internalized_process; process_owner=SUMPAR; mode T1->OEM=truck. Exclude Combigo from material/process tiers. |
| 18 | Combigo as aluminium T2 and wrong direct supplier | Replace T1=SUMPAR with MGA Villeneuve-sur-Lot and replace T2=Combigo with MGA internal machining/forming process. | high | Set primary chain Alcoa/AMAG -> MGA internal process -> MGA -> Safran. Keep other aluminium suppliers as inactive scenarios. |
| 19 | Combigo as aluminium T2 | Replace T2=Combigo with SUMPAR internal machining/forming process; keep T1=SUMPAR. | high | Use SUMPAR as process owner and direct supplier. Remove Combigo from active path. |
| 20,26 | Combigo as aluminium T2 and wrong direct supplier | Replace T1=SUMPAR with MGA and T2=Combigo with MGA internal machining process. | high | Set process_owner=MGA; T1=MGA; T1->OEM=truck. |
| 21,22,23,24,27,28 | Combigo as aluminium T2 and wrong direct supplier | Replace T1=SUMPAR with ETS Gattefin and T2=Combigo with Gattefin internal machining process. | high | Set process_owner=ETS Gattefin; T1=ETS Gattefin; keep T4/T3 aluminium source as material scenario until certificate. |
| 54,55 | Combigo as aluminium T2 and wrong direct supplier | Replace T1=SUMPAR with Senior Aerospace Thailand and T2=Combigo with Senior internal machining/special process/assembly. | high | Set T2=Senior internal process; T1=Senior Aerospace Thailand; T1->OEM mode=air+truck for ACV baseline, with sea+truck as cost/CO2 scenario. |
| 157,174,175 | MGR Foamtex as aluminium T2 | Do not use these aggregate seat aluminium rows as active component supply paths. Either mark them scenario_aggregate_only or replace T2 with unknown aluminium structural processor under the real seat T1 after BOM validation. | high | Set simulation_supply_usable=false for active network, or keep as aggregate mass scenario only. Do not use MGR in aluminium T2. Use detailed A2017/A2024/A5086 records for aluminium stress tests. |
| 86,87,88,89,90 | FRMC55 with steel upstream | Replace steel upstream with PU/textile chain: T4=BASF or unknown PU chemistry source; T3=unknown certified foam/fabric source; T2=FRANKLIN internal cutting/gluing; T1=FRANKLIN direct cushion supplier. | high for removing steel; medium for BASF as active T4 without grade certificate | Remove Saarstahl/Aubert from these FRMC55 active paths. Use FRANKLIN as direct supplier path; T1->OEM=air+truck per ACV. Keep BASF as candidate/assumption unless grade certificate confirms. |
| 91 | FRMC55 with steel upstream | Treat this as a small FRMC55 foam/material line embedded in the MGA stowage assembly: T4=unknown/BASF PU chemistry, T3=unknown foam source, T2=MGA internal integration, T1=MGA. | medium_high | Attach FRMC55 mass to MGA assembly path; do not route through steel mills. |
| 92,93 | FRMC55 with steel upstream | Replace steel upstream with PU foam chain and use MGR Foamtex as foam/interior supplier candidate for these manchette rows. | high for removing steel; medium for exact site/routing | Set T2/T1 material supplier=MGR Foamtex for FRMC55 manchette lines or keep T1 assembly owner separate if drawing confirms ACH assembly. |
| 74 | Electronics/COTS with steel/copper upstream | Keep T1=Liebherr Aerospace and T2=Liebherr internal electronics/routing package. Replace active T4/T3 with non-switchable COTS electronics placeholder until BOM/PN/AVL is available. | high | Set T4/T3 status=do_not_infer_from_cots; active=false. Required data: part number, PCB/EMS, AVL, qualified component list. |
| 10,71,73,78,121,126,153 | Electronics/COTS upstream not defensible | For IFE/display/powerbox: use program supplier placeholder or T1 candidate only. For TE cable/connector rows: keep TE/DEUTSCH connector path, but do not infer T4/T3. | medium_high | Mark upstream T4/T3 inactive COTS placeholder; require BOM before switch stress tests. Keep TE as T1/T2 connector supplier only where part number confirms. |
| 151 | SGL Carbon as T2 on steel Z10CNT18 | Replace T2=SGL Carbon with MGA internal machining/forming process. Keep T1=MGA. Keep T4/T3 steel mill/stockist as certificate-required candidates. | high | Set T2=internal_T1_process_MGA. Set Baosteel/Krupp as candidates requiring certificate/allocation; do not activate without material certificate. |
| 33,51,81,94,95,96,98,99,100,101,102,138 | Thailand -> France marked truck only | Use two lane scenarios: baseline ACV air+truck where BOM says AVION for Senior rows; normal cost/CO2 scenario truck to Laem Chabang + sea to French/European port + truck/rail to Safran. | high | Replace T1->OEM truck-only with lane_mode_set=[air+truck baseline where ACV=AVION, sea+truck scenario]. Add lane-level distances and ports. |
| 75,128,161,162,164,165,166 | Japan -> France marked truck only | Replace truck-only with truck+sea+truck baseline for bulky interiors, and truck+air+truck expedite scenario. For rows with ACV percentage/low confidence, keep as aggregate scenario not primary quantitative truth. | medium_high | Add lane-level routes: plant -> Japan/Philippines port or airport -> French/EU port or CDG -> Safran. Mark transport_source=geography_assumption until freight data is provided. |
| 103-109,75 | Kydex/Lexan/polymer path validation | Use SEKISUI KYDEX or SABIC Lexan family as material candidate depending exact material. Keep thermoforming/internal T2 under actual T1 only if drawing/routing confirms. | medium | Set material supplier candidates active=false unless certificate/grade confirms; split Kydex vs Lexan vs generic NIDA/plastic rows. |

## Sources principales

- `LOCAL_LCA`: data/quantity_material.xlsx
- `SUMPAR`: https://www.sumpar.com/en/
- `COMBIGO`: https://www.linkedin.com/company/combigo/
- `MGA`: https://www.lafrenchfab.fr/entreprise/mga-groupe-arm/
- `GATTEFIN`: https://gattefin.fr/
- `MGR`: https://www.mgrfoamtex.com/products-2
- `BASF_SEATING`: https://aerospace.basf.com/seating-components.html
- `SENIOR_TH`: https://www.senior-thailand.com/Web/what_we_do
- `JAMCO`: https://jamcointeriors.com/
- `TE_DEUTSCH`: https://www.te.com/en/products/brands/deutsch.html?cat=1
- `LIEBHERR`: https://www.liebherr.com/en-int/aerospace-and-transportation-systems/solutions-and-services/solutions-for-aerospace/on-board-systems/on-board-systems-7174957
- `LIEBHERR_ELECTRONICS`: https://www.liebherr.com/shared/media/components/documents/control-technology-and-electronics/liebherr-electronics-for-aerospace.pdf
- `LAEM_CHABANG`: https://lcp.port.co.th/cs/internet/lcp/Information.html
- `NANTES_PORT`: https://www.nantes.port.fr/en
- `SEKISUI_KYDEX`: https://kydex.com/library/kydex-5555rcl/

## Fichier CSV

- `C:/dev/lca-simu/analysis/output8_GEO_blocking_path_researched_solutions.csv`
