# Synthese audit chemins supply T4 -> OEM

Fichier audite : `analysis/output8_GEO_normalized_final_primary_complete_lca_marked.json`

## Verdict court

La topologie principale est complete au sens graphe : les chemins principaux disposent bien de T4, T3, T2, T1 et OEM cartographiables. En revanche, elle n'est pas encore propre pour des stress tests avances sans corrections, car plusieurs chemins principaux restent incoherents cote matiere/process et le transport est encore trop generique.

## Couverture auditee

- Records supply audites : 173
- Records exclus car references ACV/procedes non supply : 2
- Chemins principaux enumeres : 175
- Chemins secondaires/candidats enumeres : 29 814
- Total chemins T4 -> T3 -> T2 -> T1 -> OEM : 29 989

## Statut des chemins principaux

- 124 chemins principaux sont complets mais demandent validation avant simulation robuste.
- 28 chemins principaux demandent une reprise metier/matiere.
- 23 chemins principaux demandent surtout une reprise transport.

Les 28 reprises metier concernent principalement :

- `Combigo` utilise en T2 sur des lignes aluminium A2017/A2024 : ce n'est pas coherent comme transformateur aluminium principal.
- `MGR Foamtex Ltd` utilise en T2 sur des lignes aluminium siege : coherent pour mousse/textile, pas pour aluminium.
- Lignes `FRMC55` avec amont `Saarstahl` / `Aubert & Duval` alors que la matiere source est plutot mousse/polyurethane/textile.
- Electronique/COTS avec amont metal/matiere (`Saarstahl`, `Aurubis`) : a remplacer par un placeholder COTS non switchable ou a documenter par BOM/PN.
- `Z10CNT18` avec `SGL Carbon` en T2 : incoherent pour acier/inox.

## ACV / quantity_material.xlsx

- 173 / 173 records supply audites portent une masse ACV/BOM.
- 128 records sont `quantitative_ready`.
- 17 records sont `usable_for_baseline`.
- 12 records sont `usable_with_review`.
- 16 records sont `scenario_only_review_required`.

Interpretation : l'ACV est bien rattachee au reseau, mais toutes les masses ne doivent pas etre utilisees avec le meme niveau de confiance. Les lignes siege agregees et composites/titane/carbone doivent rester en scenario ou etre decomposees avant stress test quantitatif.

## Chemins secondaires

- 16 321 chemins secondaires ne sont pas bloques structurellement, mais restent a qualifier : allocation, certificat, qualification fournisseur, lead time et site.
- 8 280 chemins secondaires sont a reprendre car incompatibilite matiere/famille fournisseur.
- 5 264 chemins secondaires sont a reprendre cote transport.

Conclusion : il ne faut pas activer tous les secondaires en bloc. Il faut d'abord creer un sous-ensemble de switchs par famille matiere : aluminium, acier, textile/mousse, polymeres, COTS, silicone/composite.

## Transport

Le JSON recense bien des modes de transport, mais seulement sous forme de phases generiques :

- `mine_to_refinery`
- `to_first_transformation`
- `from_supplier_to_safran`

Ce n'est pas encore un modele lane-by-lane. Aucun des 29 989 chemins n'a un transport specifique pour toutes les jambes T4->T3, T3->T2, T2->T1, T1->OEM.

Problemes transport principaux :

- `T3->T2` et `T2->T1` ne sont generalement pas renseignes explicitement.
- Plusieurs chemins T1 Asie -> Safran France sont marques `truck` seul, notamment `Senior Aerospace Thailand` et `JAMCO Aircraft Interiors - Niigata/Miyazaki/Philippines`.
- Plusieurs T4 asiatiques ou US vers T3 europeens sont marques camion seul alors qu'il faut au minimum un scenario maritime/air/rail selon la criticite.

## Fichiers produits

- `analysis/output8_GEO_supply_path_network_full_paths.csv`
- `analysis/output8_GEO_supply_path_network_component_summary.csv`
- `analysis/output8_GEO_supply_path_network_issues.csv`
- `analysis/output8_GEO_supply_path_network_transport_lanes.csv`
- `analysis/output8_GEO_supply_path_network_node_quality.csv`
- `analysis/output8_GEO_supply_path_network_audit_report.md`

## Prochaine etape recommandee

1. Corriger les chemins principaux bloques par incoherence matiere/process.
2. Ajouter une table transport lane-by-lane pour T4->T3, T3->T2, T2->T1, T1->OEM.
3. Filtrer les secondaires en trois statuts : `switch_ready`, `candidate_requires_validation`, `exclude_from_simulation`.
4. Decomposer les lignes mixtes ou agregees ACV avant simulation quantitative : aluminium/acier mixte, siege total, textile+mousse, titane+carbone.
