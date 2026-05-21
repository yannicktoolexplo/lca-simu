# Audit des chemins secondaires et switchs fournisseurs

- Source paths: `C:/dev/lca-simu/analysis/output8_GEO_simulation_ready_researched_supply_path_network_full_paths.csv`
- Generated at: `2026-05-21T14:17:31+00:00`
- Secondary paths audited: **24620**

## Verdict court

On ne peut pas switcher librement tous les fournisseurs entre eux. Les chemins secondaires sont des combinaisons de scenarios, pas des couples d'achat valides par defaut. Un switch doit respecter la famille matiere, le role industriel, la qualification fournisseur, le certificat matiere, le lead time et le transport lane-by-lane.

## Switchability globale

- Candidats non bloques apres validation: **24620 / 24620**
- Bloques ou incoherents avant correction: **0 / 24620**
- `candidate_requires_validation`: **24620**

## Classes detaillees

- `candidate_requires_allocation_and_qualification`: **13492**
- `candidate_requires_material_certificate`: **8626**
- `candidate_scenario_only_mass_review`: **2167**
- `candidate_requires_material_source`: **333**
- `candidate_requires_site_validation`: **2**

## Synthese par composant

- `switch_possible_after_validation`: **168** composants

## Synthese par option fournisseur/tier

- `switch_possible_after_validation`: **244** options fournisseur/famille/tier

## Familles les plus concernees

- `steel`: 8708 chemins secondaires, 8708 candidats apres validation, 0 bloques
- `textile_leather`: 6113 chemins secondaires, 6113 candidats apres validation, 0 bloques
- `aluminium`: 4841 chemins secondaires, 4841 candidats apres validation, 0 bloques
- `polymer_plastic`: 4778 chemins secondaires, 4778 candidats apres validation, 0 bloques
- `general`: 96 chemins secondaires, 96 candidats apres validation, 0 bloques
- `rubber_silicone`: 34 chemins secondaires, 34 candidats apres validation, 0 bloques
- `electronics_cots`: 25 chemins secondaires, 25 candidats apres validation, 0 bloques
- `adhesive_composite`: 14 chemins secondaires, 14 candidats apres validation, 0 bloques
- `copper`: 11 chemins secondaires, 11 candidats apres validation, 0 bloques

## Principales validations restantes

- `steel` / `inactive_alternate_requires_allocation` / `candidate_requires_material_certificate`: **6992** chemins
- `steel` / `material_certificate_required` / `candidate_requires_material_certificate`: **6992** chemins
- `polymer_plastic` / `inactive_alternate_requires_allocation` / `candidate_requires_allocation_and_qualification`: **4541** chemins
- `textile_leather` / `inactive_alternate_requires_allocation` / `candidate_requires_allocation_and_qualification`: **3855** chemins
- `aluminium` / `inactive_alternate_requires_allocation` / `candidate_requires_allocation_and_qualification`: **3255** chemins
- `aluminium` / `baseline_node_is_assumption` / `candidate_requires_allocation_and_qualification`: **3255** chemins
- `textile_leather` / `inactive_alternate_requires_allocation` / `candidate_scenario_only_mass_review`: **1926** chemins
- `textile_leather` / `lca_mass_low_confidence` / `candidate_scenario_only_mass_review`: **1926** chemins
- `steel` / `baseline_node_is_assumption` / `candidate_requires_material_certificate`: **1807** chemins
- `steel` / `inactive_alternate_requires_allocation` / `candidate_requires_allocation_and_qualification`: **1716** chemins
- `aluminium` / `inactive_alternate_requires_allocation` / `candidate_requires_material_certificate`: **1586** chemins
- `aluminium` / `baseline_node_is_assumption` / `candidate_requires_material_certificate`: **1586** chemins
- `aluminium` / `material_certificate_required` / `candidate_requires_material_certificate`: **1586** chemins
- `textile_leather` / `baseline_node_is_assumption` / `candidate_requires_allocation_and_qualification`: **1197** chemins
- `textile_leather` / `lca_mass_requires_review` / `candidate_requires_allocation_and_qualification`: **1155** chemins
- `steel` / `baseline_node_is_assumption` / `candidate_requires_allocation_and_qualification`: **427** chemins
- `textile_leather` / `inactive_alternate_requires_allocation` / `candidate_requires_material_source`: **332** chemins
- `textile_leather` / `baseline_node_is_assumption` / `candidate_requires_material_source`: **332** chemins
- `textile_leather` / `raw_material_source_missing` / `candidate_requires_material_source`: **332** chemins
- `polymer_plastic` / `inactive_alternate_requires_allocation` / `candidate_scenario_only_mass_review`: **237** chemins

## Composants les plus bloques


## Options fournisseur/tier a exclure en priorite


## Regles de switch a appliquer

- Ne jamais activer le produit cartesien complet des alternates.
- Les process internalises T2 doivent rester couples a leur T1; ex. `SUMPAR internal process` ne doit pas etre combine avec `MGA`.
- Pour aluminium/acier/cuivre, un switch T4/T3 exige certificat matiere, nuance, mill/site et allocation.
- Pour textile/mousse/cuir/silicone, il faut les preuves feu/fumee/toxicite et la fiche matiere exacte.
- Pour COTS/electronique, l'amont T3/T4 reste non switchable sans BOM, part number, EMS/ODM et AVL.
- Tout switch international doit conserver un transport lane-by-lane; les secondaires ont maintenant une lane calculee, mais le mode choisi doit rester validable industriellement.

## Fichiers produits

- Detail tous chemins secondaires: `C:/dev/lca-simu/analysis/output8_GEO_secondary_switch_path_audit.csv`
- Resume par composant: `C:/dev/lca-simu/analysis/output8_GEO_secondary_switch_component_summary.csv`
- Options par fournisseur/tier/famille: `C:/dev/lca-simu/analysis/output8_GEO_secondary_switch_supplier_options.csv`
- Blocages groupes: `C:/dev/lca-simu/analysis/output8_GEO_secondary_switch_blockers.csv`
