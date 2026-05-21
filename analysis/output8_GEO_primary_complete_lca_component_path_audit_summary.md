# Component Supply Path Audit

- Source JSON: `analysis/output8_GEO_normalized_final_primary_complete_lca_marked.json`
- Primary path CSV: `analysis/output8_GEO_primary_complete_lca_component_path_audit.csv`
- All-supplier coverage CSV: `analysis/output8_GEO_primary_complete_lca_all_coverage_audit.csv`
- Gap/action CSV: `analysis/output8_GEO_primary_complete_lca_gap_actions.csv`

## Ce que veut dire un tier absent

Un tier absent signifie qu'aucun noeud fournisseur cartographiable n'est porté à ce niveau dans le JSON pour ce composant. Ce n'est pas automatiquement une erreur.
Les cas fréquents sont: procédé T2 internalisé chez le T1, amont matière volontairement non activé sans certificat, sous-tiers COTS non inférables sans BOM/PN, ou vrai fournisseur direct T1 encore inconnu.

## Fournisseurs principaux

- Records audités: **173**
- Statuts parcours: complete_direct=173
- Gaps/actions: 
- Tiers concernés: 

Lecture recommandée: les `accepted_internalized_process` sont normaux pour des pièces mécaniques; ce sont des opérations de fabrication chez ESPACE, SUMPAR, MGA, Senior Aerospace, etc. Les `requires_bom_or_program_data` et `hard_gap_*` sont les vrais blocages pour la simulation.

## Tous fournisseurs activables

- Records audités: **173**
- Statuts parcours/couverture: complete_direct=173
- Gaps/actions: 

Même en mode `all`, je ne combine pas automatiquement tous les T4/T3/T2/T1 entre eux. Un alternate par tier est une option de scénario, pas une preuve qu'il est compatible avec chaque autre alternate.

## Priorités de correction


## Interprétation pour la carte

- Trait plein: tiers adjacents présents et cartographiables.
- Pont pointillé: tier intermédiaire absent ou non cartographiable, mais le parcours atteint quand même le constructeur.
- T2 absent sur métal/aluminium: généralement procédé internalisé chez le T1, pas fournisseur manquant.
- T1 absent: vrai blocage métier tant que le fournisseur programme ou le PN n'est pas connu.
- T3/T4 absents sur COTS/textile/polymères: souvent non activable sans BOM, grade ou certificat.
