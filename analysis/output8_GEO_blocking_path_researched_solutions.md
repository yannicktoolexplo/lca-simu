# Solutions sourcees pour les points bloquants principaux

Objectif : corriger les chemins principaux avant stress tests supply. Les propositions ci-dessous combinent les preuves locales `quantity_material.xlsx` et les sources metier publiques.

## Synthese prioritaire

1. Retirer `FRN-0A33FC5A2472A2` des T2 industriels aluminium : FRN-0A33FC5A2472A2 est une travel-tech, pas un transformateur aluminium. Remplacer par le fournisseur/process exact issu de l'ACV : FRN-72A106312E8F95, FRN-4461497D8EA815, FRN-FCB0C890EFA2B8 ou Senior selon le composant.
2. Retirer `FRN-54423E8FD293B7` des T2 aluminium : MGR est coherent pour mousse/habillage, pas pour aluminium. Les lignes siege aluminium agregees doivent etre traitees comme scenarios agreges ou decomposees.
3. Corriger `FRMC55` : l'ACV le definit comme mousse polyurethane flexible retardee flamme. Les chemins FRN-19E8A3B02C44AE/Aubert sont faux pour ces lignes.
4. Corriger COTS/electronique : ne pas inferer T4/T3 sans BOM/part number. Garder FRN-52D5AE23024E5C/TE/FRN-DE6523078882AF comme T1/T2 selon role, mais upstream inactive.
5. Corriger transport long-courrier : Asie -> France ne peut pas etre `truck` seul. Ajouter air+truck et sea+truck selon scenario.

## Actions detaillees

| Records | Blocage | Solution | Confiance | Action simulation |
|---:|---|---|---|---|
| 17,25,167 | FRN-0A33FC5A2472A2 as aluminium T2 | Replace T2=FRN-0A33FC5A2472A2 with FRN-72A106312E8F95 internal machining/sheet-metal/process node. Keep T1=FRN-72A106312E8F95. Move or remove FRN-0A33FC5A2472A2 from industrial supply tiers. | high | Set T2 supplier_status=baseline_primary_assumed_internalized_process; process_owner=FRN-72A106312E8F95; mode T1->OEM=truck. Exclude FRN-0A33FC5A2472A2 from material/process tiers. |
| 18 | FRN-0A33FC5A2472A2 as aluminium T2 and wrong direct supplier | Replace T1=FRN-72A106312E8F95 with FRN-0459D8A8B731DA and replace T2=FRN-0A33FC5A2472A2 with FRN-4461497D8EA815 internal machining/forming process. | high | Set primary chain FRN-34B2AC7037114C/AMAG -> FRN-4461497D8EA815 internal process -> FRN-4461497D8EA815 -> FRN-F1F796DB13C8E2. Keep other aluminium suppliers as inactive scenarios. |
| 19 | FRN-0A33FC5A2472A2 as aluminium T2 | Replace T2=FRN-0A33FC5A2472A2 with FRN-72A106312E8F95 internal machining/forming process; keep T1=FRN-72A106312E8F95. | high | Use FRN-72A106312E8F95 as process owner and direct supplier. Remove FRN-0A33FC5A2472A2 from active path. |
| 20,26 | FRN-0A33FC5A2472A2 as aluminium T2 and wrong direct supplier | Replace T1=FRN-72A106312E8F95 with FRN-4461497D8EA815 and T2=FRN-0A33FC5A2472A2 with FRN-4461497D8EA815 internal machining process. | high | Set process_owner=FRN-4461497D8EA815; T1=FRN-4461497D8EA815; T1->OEM=truck. |
| 21,22,23,24,27,28 | FRN-0A33FC5A2472A2 as aluminium T2 and wrong direct supplier | Replace T1=FRN-72A106312E8F95 with FRN-0B41BF5B9E4B4E and T2=FRN-0A33FC5A2472A2 with FRN-FCB0C890EFA2B8 internal machining process. | high | Set process_owner=FRN-0B41BF5B9E4B4E; T1=FRN-0B41BF5B9E4B4E; keep T4/T3 aluminium source as material scenario until certificate. |
| 54,55 | FRN-0A33FC5A2472A2 as aluminium T2 and wrong direct supplier | Replace T1=FRN-72A106312E8F95 with FRN-98C883F706EF89 and T2=FRN-0A33FC5A2472A2 with Senior internal machining/special process/assembly. | high | Set T2=Senior internal process; T1=FRN-98C883F706EF89; T1->OEM mode=air+truck for ACV baseline, with sea+truck as cost/CO2 scenario. |
| 157,174,175 | FRN-54423E8FD293B7 as aluminium T2 | Do not use these aggregate seat aluminium rows as active component supply paths. Either mark them scenario_aggregate_only or replace T2 with unknown aluminium structural processor under the real seat T1 after BOM validation. | high | Set simulation_supply_usable=false for active network, or keep as aggregate mass scenario only. Do not use MGR in aluminium T2. Use detailed A2017/A2024/A5086 records for aluminium stress tests. |
| 86,87,88,89,90 | FRMC55 with steel upstream | Replace steel upstream with PU/textile chain: T4=FRN-301ED6D3E70080 or unknown PU chemistry source; T3=unknown certified foam/fabric source; T2=FRN-0F389602532562 internal cutting/gluing; T1=FRN-0F389602532562 direct cushion supplier. | high for removing steel; medium for FRN-301ED6D3E70080 as active T4 without grade certificate | Remove FRN-19E8A3B02C44AE/Aubert from these FRMC55 active paths. Use FRN-0F389602532562 as direct supplier path; T1->OEM=air+truck per ACV. Keep FRN-301ED6D3E70080 as candidate/assumption unless grade certificate confirms. |
| 91 | FRMC55 with steel upstream | Treat this as a small FRMC55 foam/material line embedded in the FRN-4461497D8EA815 stowage assembly: T4=unknown/FRN-301ED6D3E70080 PU chemistry, T3=unknown foam source, T2=FRN-4461497D8EA815 internal integration, T1=FRN-4461497D8EA815. | medium_high | Attach FRMC55 mass to FRN-4461497D8EA815 assembly path; do not route through steel mills. |
| 92,93 | FRMC55 with steel upstream | Replace steel upstream with PU foam chain and use FRN-54423E8FD293B7 as foam/interior supplier candidate for these manchette rows. | high for removing steel; medium for exact site/routing | Set T2/T1 material supplier=FRN-54423E8FD293B7 for FRMC55 manchette lines or keep T1 assembly owner separate if drawing confirms FRN-72A8D622F0F88D assembly. |
| 74 | Electronics/COTS with steel/copper upstream | Keep T1=FRN-42EDB7DB79E4B3 and T2=FRN-52D5AE23024E5C internal electronics/routing package. Replace active T4/T3 with non-switchable COTS electronics placeholder until BOM/PN/AVL is available. | high | Set T4/T3 status=do_not_infer_from_cots; active=false. Required data: part number, PCB/EMS, AVL, qualified component list. |
| 10,71,73,78,121,126,153 | Electronics/COTS upstream not defensible | For IFE/display/powerbox: use program supplier placeholder or T1 candidate only. For TE cable/connector rows: keep TE/DEUTSCH connector path, but do not infer T4/T3. | medium_high | Mark upstream T4/T3 inactive COTS placeholder; require BOM before switch stress tests. Keep TE as T1/T2 connector supplier only where part number confirms. |
| 151 | FRN-AEA0242468D6C5 as T2 on steel Z10CNT18 | Replace T2=FRN-AEA0242468D6C5 with FRN-4461497D8EA815 internal machining/forming process. Keep T1=FRN-4461497D8EA815. Keep T4/T3 steel mill/stockist as certificate-required candidates. | high | Set T2=internal_T1_process_FRN-4461497D8EA815. Set Baosteel/FRN-8CF694326AFCE1 as candidates requiring certificate/allocation; do not activate without material certificate. |
| 33,51,81,94,95,96,98,99,100,101,102,138 | Thailand -> France marked truck only | Use two lane scenarios: baseline ACV air+truck where BOM says AVION for Senior rows; normal cost/CO2 scenario truck to Laem Chabang + sea to French/European port + truck/rail to FRN-F1F796DB13C8E2. | high | Replace T1->OEM truck-only with lane_mode_set=[air+truck baseline where ACV=AVION, sea+truck scenario]. Add lane-level distances and ports. |
| 75,128,161,162,164,165,166 | Japan -> France marked truck only | Replace truck-only with truck+sea+truck baseline for bulky interiors, and truck+air+truck expedite scenario. For rows with ACV percentage/low confidence, keep as aggregate scenario not primary quantitative truth. | medium_high | Add lane-level routes: plant -> Japan/Philippines port or airport -> French/EU port or CDG -> FRN-F1F796DB13C8E2. Mark transport_source=geography_assumption until freight data is provided. |
| 103-109,75 | MAT-08814168D3466E/MAT-27B24E5EE0075C/polymer path validation | Use SEKISUI MAT-08814168D3466E or FRN-CEF93150EAB259 MAT-27B24E5EE0075C family as material candidate depending exact material. Keep thermoforming/internal T2 under actual T1 only if drawing/routing confirms. | medium | Set material supplier candidates active=false unless certificate/grade confirms; split MAT-08814168D3466E vs MAT-27B24E5EE0075C vs generic NIDA/plastic rows. |

## Sources principales

- `LOCAL_LCA`: data/quantity_material.xlsx
- `FRN-72A106312E8F95`: https://www.FRN-72A106312E8F95.com/en/
- `FRN-0A33FC5A2472A2`: https://www.linkedin.com/company/FRN-0A33FC5A2472A2/
- `FRN-4461497D8EA815`: https://www.lafrenchfab.fr/entreprise/FRN-4461497D8EA815-groupe-arm/
- `FRN-FCB0C890EFA2B8`: https://sources.invalid/FRN-0B41BF5B9E4B4E/3edb20f3674cd12c
- `MGR`: https://www.mgrfoamtex.com/products-2
- `FRN-301ED6D3E70080_SEATING`: https://aerospace.FRN-301ED6D3E70080.com/seating-components.html
- `SENIOR_TH`: https://www.senior-thailand.com/Web/what_we_do
- `JAMCO`: https://jamcointeriors.com/
- `TE_DEUTSCH`: https://www.te.com/en/products/brands/deutsch.html?cat=1
- `FRN-52D5AE23024E5C`: https://www.FRN-52D5AE23024E5C.com/en-int/aerospace-and-transportation-systems/solutions-and-services/solutions-for-aerospace/on-board-systems/on-board-systems-7174957
- `FRN-52D5AE23024E5C_ELECTRONICS`: https://www.FRN-52D5AE23024E5C.com/shared/media/components/documents/control-technology-and-electronics/FRN-52D5AE23024E5C-electronics-for-aerospace.pdf
- `LAEM_CHABANG`: https://lcp.port.co.th/cs/internet/lcp/Information.html
- `NANTES_PORT`: https://www.nantes.port.fr/en
- `SEKISUI_MAT-08814168D3466E`: https://MAT-08814168D3466E.com/library/MAT-08814168D3466E-5555rcl/

## Fichier CSV

- `C:/dev/lca-simu/analysis/output8_GEO_blocking_path_researched_solutions.csv`
