# Guides Etudecas

Pour découvrir le logiciel et l'organisation de ses dossiers, commencer par le
[README du projet](../README.md). Cette page oriente vers les guides détaillés.
Les [résultats locaux](../index.html) ont leur propre accueil.

## Comprendre le modèle et ses contrats

| Sujet | Guide et références |
|---|---|
| Refaire le système MRP, des clients jusqu’aux fournisseurs | [Guide pas à pas](MRP_PAS_A_PAS.html) et [PDF](MRP_PAS_A_PAS.pdf) : mots simples, formules, variables, exemples, recettes, paramètres et ordre quotidien ; [texte modifiable](MRP_PAS_A_PAS.md) et [paramètres lisibles](reference/MRP_PARAMETRES_LISIBLES.json) |
| Comprendre ce que couvre toute la simulation et quelles données industrielles manquent | [Rapport de complétude de la simulation](RAPPORT_COMPLETUDE_SIMULATION.md) ; demande, production, MRP, achats, lots, risques, incertitude et priorités de données |
| Comprendre les données industrielles et leurs versions | [Bilan des données sources](DONNEES_SOURCES.md) ; couverture, unités, calendriers, redondances et contradictions vérifiées le 8 octobre 2026 |
| Règles MRP courantes et application par liaison | [Les règles simplement](REGLES_MRP.md) ; prévisions, achats, fabrication, transferts et conventions encore à confirmer |
| Reprendre la conception du MRP à partir des sources | [Refondation du MRP](REFONDATION_MRP.md) ; noyau commun, politiques locales, identification et validation avant remplacement |
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

- [Critères scientifiques de développement](DEVELOPPEMENT_SCIENTIFIQUE.md) : contrats, MRP/exécution, calibration, causalité, incertitude et performance ; [audit des instructions et du harnais](quality/AUDIT_INSTRUCTIONS_20261021.md).

- [Comprendre et simplifier les fichiers Python](PLAN_SIMPLIFICATION.md) : parcours courant par étude, cible de refonte, dépendances et priorités ; [tableau filtrable par fichier](INVENTAIRE_PYTHON.csv).
- [Valider une modification](TEST_VALIDATION.md) : tests relus et sélectionnés, comparaisons numériques et limites des preuves.
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

[Gaillac → Avène : réel, prévu et simulé](archive/AMONT_AVAL_693055_20261104.html) :
deux calculs natifs de 56 jours pour 693055 ; raccourcir le transport ne corrige
pas les stocks de Gaillac et dégrade ceux d’Avène. Les réceptions de mai sont
rapprochées des plans connus en avril, sans les assimiler à une reprise de fabrication.

[Priorités mises en œuvre et résultats du 3 novembre 2026](archive/PRIORITES_ET_RESULTATS_20261103.html) :
programmes quotidiens sans doubles comptes, inconnues préservées, graphique des creux et calendrier d’avril.

[Disponibilités et départs d’avril](archive/DISPONIBILITES_AVRIL_20261103.html) :
deux attentes localisées, quatre cas courts et effet du calendrier d’expédition sur le retard client.

[Formats confirmés et besoins sans double compte](archive/FORMATS_CONFIRMES_20261103.html) :
confirmation industrielle du périmètre, ventilation encore inconnue et contrôles courts sur les besoins.

[Semaine d’avril et bilan des 2 et 3 novembre](archive/SEMAINE_AVRIL_ET_BILAN_20261103.html) :
observations industrielles, lots simulés, service des demandes de la semaine et fichier de rapprochement à compléter.

[Aléas localisés et réponse client](archive/ALEAS_LOCALISES_20261104.html) :
36 comparaisons datées sur libération, départ et transport ; demande historique conservée, service industriel à rapprocher.
Un [fichier de collecte journalier](../artifacts/testing/aleas_localises_20261104/service_client_reel_a_completer.csv)
prépare la comparaison des départs et réceptions clients bruts, séparés des mouvements nets de stock.

L'[accueil des résultats](../index.html) donne accès aux quatre présentations
conservées ; le [guide de reconstruction](REGENERER_RESULTATS.md) précise leurs
entrées et leurs limites. Les audits, bilans de livraison et anciennes notes de
changement sont regroupés dans les [archives](../archive/README.md), avec leurs
chemins d'origine. Leurs résultats décrivent l'état audité à leur date.

Deux notes restent dans `changes/` parce que le catalogue les utilise comme
sources métier : [conventions corrigées du modèle](changes/2026-09-20-audit-model-corrections.md)
et [coûts et arrondis](changes/2026-09-20-cost-rounding-README.md).
