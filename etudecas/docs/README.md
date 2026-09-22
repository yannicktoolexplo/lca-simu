# Guides Etudecas

Pour découvrir le logiciel et l'organisation de ses dossiers, commencer par le
[README du projet](../README.md). Cette page oriente vers les guides détaillés.
Les [résultats locaux](../index.html) ont leur propre accueil.

## Comprendre le modèle et ses contrats

| Sujet | Guide et références |
|---|---|
| Entrées de simulation et API locale | [Contrat des entrées](SIMULATION_INPUT_CONTRACT.md) · [Règles liées au code](generated/simulation_input/index.md) |
| Lots, expéditions et risques | [Registre des impacts](../simulation/lot_trace/RISK_IMPACT_REGISTRY.md) · [Règles liées au code](generated/index.md) |
| Matières, lots fournisseurs et incidents | [Conventions métier](MATIERES_LOTS_ET_INCIDENTS.md) · [Règles liées au code](generated/material_traceability/index.md) |
| Quantités physiques et transport | [Exécution et vérification](EXECUTION_VERIFICATION.md) · [Lots, commandes, palettes et camions](LOTS_ET_CAMIONS.md) |
| Besoins et capacités | [Couplage](CAPACITY_COUPLING.md) · [Règles liées au code](generated/capacity_coupling/index.md) |
| Fournisseurs et actions possibles | [Sélection des fournisseurs](SUPPLIER_ACTION_SELECTION.md) · [Règles liées au code](generated/supplier_actions/index.md) |
| Comparaison et diagnostic | [Comparaison des scénarios](SCENARIO_COMPARISON.md) · [Diagnostic et sensibilités](DECISION_SUPPORT.md) |
| Provenance et format des résultats | [Provenance](PROVENANCE.md) · [Contrat des packages](generated/run_package/index.md) |
| Demande, calendrier et valorisation | [Conventions du modèle reliées au code](generated/audited_semantics/index.md) |

La [couverture et les limites](COVERAGE_AND_LIMITS.md) précisent ce qui reste
partiel. Une règle documentée et une empreinte inchangée ne constituent pas une
validation industrielle.

## Modifier le logiciel

- [Valider une modification](TEST_VALIDATION.md) : dépendances, périmètre de référence et lecture des résultats de tests.
- [Utiliser les fixtures](TEST_FIXTURES.md) : données de test autonomes et intégrations historiques explicites.
- [Travailler avec les agents Codex](MULTI_AGENT_OPERATIONNEL.md) : rôles, périmètres de modification et toolbox locale.
- [Mettre à jour la documentation du code](AUTOMATION.md) : règles, références, génération et revue des empreintes.

## Utiliser les commandes et les interfaces

- [Commandes du projet](../OPERATIONS.md) : installation, pipeline et opérations disponibles.
- [Explorateur des lots](EXPLORATEUR_DES_LOTS.md) et [parcours des lots](PARCOURS_DES_LOTS.md) : recherche, navigation et lecture à une date.
- [Fiche de lot](FICHE_LOT.md) : entrées, consommations, expéditions, réservations et soldes.
- [Enquêtes enregistrées](ENQUETES_LOTS.md) : conserver une vue, la rouvrir et exporter une fiche.
- [Transports et impacts](TRANSPORTS_ET_IMPACTS.md) : examiner une expédition et ses liens avec les lots.

## Maintenir le projet

- [Automatisation documentaire](AUTOMATION.md) : manuel du générateur, catalogue, surveillance et contrôle GitHub.
- [Publication et reprise des calibrations](CALIBRATION_EXECUTION.md) : écritures, signatures et checkpoints.
- [Catalogue des règles](catalog.json) : correspondance entre registres éditables et documentation générée.

## Consulter les livraisons et l'historique

Le [bilan de livraison](PROJECT_STATUS.md) identifie les résultats courants et
leurs limites. Les documents suivants décrivent des états datés :

- [Corrections intégrées le 20 septembre](changes/2026-09-20-audit-integrated-corrections.md) et [contre-vérification de la carte](changes/2026-09-20-final-map-numeric-verification.md).
- [Audit initial du 20 septembre](audit_20260920/README.md).
- [Revue des fichiers depuis le dernier commit](audit_since_head_20260920/README.md) : périmètre, constats et corrections proposées, sans modification du code pendant cette revue.
- [Livraison de carte du 18 septembre](MAP_DELIVERY.md) et [recontrôle associé](../../CORRECTIONS_ETUDECAS_2026-09-18.md).
- [Notes de changements](changes/) : interventions et limites constatées à chaque livraison.
