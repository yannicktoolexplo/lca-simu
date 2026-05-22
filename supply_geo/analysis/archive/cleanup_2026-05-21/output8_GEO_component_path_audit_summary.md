# Component Supply Path Audit

- Source JSON: `C:/dev/lca-simu/analysis/output8_GEO_normalized_final_site_refined.json`
- Primary path CSV: `C:/dev/lca-simu/analysis/output8_GEO_primary_component_path_audit.csv`
- All-supplier coverage CSV: `C:/dev/lca-simu/analysis/output8_GEO_all_component_coverage_audit.csv`
- Gap/action CSV: `C:/dev/lca-simu/analysis/output8_GEO_component_tier_gap_actions.csv`

## Ce que veut dire un tier absent

Un tier absent signifie qu'aucun noeud fournisseur cartographiable n'est porté à ce niveau dans le JSON pour ce composant. Ce n'est pas automatiquement une erreur.
Les cas fréquents sont: procédé T2 internalisé chez le T1, amont matière volontairement non activé sans certificat, sous-tiers COTS non inférables sans BOM/PN, ou vrai fournisseur direct T1 encore inconnu.

## Fournisseurs principaux

- Records audités: **173**
- Statuts parcours: complete_direct=87, valid_with_internalized_process_bridge=38, valid_but_upstream_not_switchable=25, requires_bom_or_program_data=11, blocked_or_manual_review_required=7, requires_certificate_or_routing=5
- Gaps/actions: accepted_internalized_process=43, accepted_upstream_family_unknown=21, requires_bom_or_part_number=11, requires_material_certificate=8, hard_gap_manual_review=8, accepted_do_not_infer_cots=5, accepted_present_but_unpositioned=4, hard_gap_direct_supplier=1
- Tiers concernés: T2=46, T4=34, T1=11, T3=10

Lecture recommandée: les `accepted_internalized_process` sont normaux pour des pièces mécaniques; ce sont des opérations de fabrication chez ESPACE, SUMPAR, MGA, Senior Aerospace, etc. Les `requires_bom_or_program_data` et `hard_gap_*` sont les vrais blocages pour la simulation.

## Tous fournisseurs activables

- Records audités: **173**
- Statuts parcours/couverture: complete_direct=88, valid_with_internalized_process_bridge=38, valid_but_upstream_not_switchable=24, requires_bom_or_program_data=11, blocked_or_manual_review_required=7, requires_certificate_or_routing=5
- Gaps/actions: accepted_internalized_process=43, accepted_upstream_family_unknown=21, requires_bom_or_part_number=11, requires_material_certificate=8, hard_gap_manual_review=8, accepted_do_not_infer_cots=5, accepted_present_but_unpositioned=2, hard_gap_direct_supplier=1

Même en mode `all`, je ne combine pas automatiquement tous les T4/T3/T2/T1 entre eux. Un alternate par tier est une option de scénario, pas une preuve qu'il est compatible avec chaque autre alternate.

## Priorités de correction

- `hard_gap_direct_supplier`: 1 cas. Exemples: R75 T1 copolymere lexan fst simapro: extrusion et thermoformage
- `hard_gap_manual_review`: 8 cas. Exemples: R75 T3 copolymere lexan fst simapro: extrusion et thermoformage; R75 T2 copolymere lexan fst simapro: extrusion et thermoformage; R140 T4 velcro; R141 T4 velcro; R142 T4 velcro; R143 T4 velcro; R149 T4 velcro; R165 T1 16 % Tissu, mousse
- `requires_bom_or_part_number`: 11 cas. Exemples: R71 T2 cables FJKL1-3K1J01-01ATAB_BRACKETS-SET; R73 T1 Clavier; R74 T2 Commande actionnement ECU; R78 T1 Display, liquid crystal, 17 pouces; R110 T1 NIDA - GLO (moulage par injection plastique); R121 T1 Display, liquid crystal, 17 pouces; R126 T1 powerbox; R128 T1 Résine BR623 - composite
- `requires_material_certificate`: 8 cas. Exemples: R5 T4 alliage Cu; R14 T4 35NC6 (nickel-chrome); R16 T4 35NC6 (nickel-chrome); R16 T3 35NC6 (nickel-chrome); R51 T4 35NC6 (nickel-chrome); R51 T3 35NC6 (nickel-chrome); R116 T4 35NC6 (nickel-chrome); R116 T3 35NC6 (nickel-chrome)
- `accepted_present_but_unpositioned`: 4 cas. Exemples: R32 T3 velours eu28: polyurethane flexible foam, with flame retardant eu28: pa6.6 fibres; R124 T3 caoutchouc; R125 T3 Polychloroprene; R130 T3 télécommande
- `accepted_internalized_process`: 43 cas. Exemples: R1 T2 A5086 - Aluminium; R2 T2 15CDV6 (chrome, molibdene, vanadium); R5 T2 alliage Cu; R13 T2 30NCD6 (nickel-chrome- molibdene); R14 T2 35NC6 (nickel-chrome); R16 T2 35NC6 (nickel-chrome); R29 T2 A5086 - Aluminium; R30 T2 A5086 - Aluminium
- `accepted_upstream_family_unknown`: 21 cas. Exemples: R4 T4 FILM DECOR AERFILM - Ep0.33 714g-m2; R6 T4 cuir; R9 T4 Silicone; R11 T4 tissu; R32 T4 velours eu28: polyurethane flexible foam, with flame retardant eu28: pa6.6 fibres; R76 T4 cuir; R77 T4 cuir; R129 T4 Silicone50 shore
- `accepted_do_not_infer_cots`: 5 cas. Exemples: R7 T4 lightning; R7 T3 lightning; R10 T4 System IFE boitier ref FJKL1-3K1100-01ATAB; R73 T4 Clavier; R73 T3 Clavier

## Interprétation pour la carte

- Trait plein: tiers adjacents présents et cartographiables.
- Pont pointillé: tier intermédiaire absent ou non cartographiable, mais le parcours atteint quand même le constructeur.
- T2 absent sur métal/aluminium: généralement procédé internalisé chez le T1, pas fournisseur manquant.
- T1 absent: vrai blocage métier tant que le fournisseur programme ou le PN n'est pas connu.
- T3/T4 absents sur COTS/textile/polymères: souvent non activable sans BOM, grade ou certificat.
