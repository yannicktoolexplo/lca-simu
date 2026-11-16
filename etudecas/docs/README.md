# Guides Etudecas

Pour découvrir le logiciel et l'organisation de ses dossiers, commencer par le
[README du projet](../README.md). Cette page oriente vers les guides détaillés.
Les [résultats locaux](../index.html) ont leur propre accueil.

## Comprendre le modèle et ses contrats

| Sujet | Guide et références |
|---|---|
| Relier MRP, lots et risques jusqu'au client | [Guide pas à pas](MRP_PAS_A_PAS.html) et [PDF complet](MRP_LOTS_RISQUES_PAS_A_PAS.pdf) : formules, variables, recettes, lotification, généalogie, risques dépendant de l'état et cascade ; chapitres 25 à 30 pour la suite ; [texte modifiable](MRP_PAS_A_PAS.md) et [paramètres lisibles](reference/MRP_PARAMETRES_LISIBLES.json) |
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

Le [retour industriel du 13 novembre 2026](changes/2026-11-13-retour-industriel-mrp.md)
rapproche la consommation mensuelle des prévisions, les horizons figés, les
transferts de D1450 et le packaging 338929 avec le code actif. Il distingue
les règles reçues, les écarts démontrés et les corrections encore à réaliser.

La [variante de consommation mensuelle et la comparaison des productions](changes/2026-11-13-consommation-mensuelle-production-mines-albi.md)
décrivent l'implémentation explicite, les essais appariés et les limites de
comparaison aux résultats rapportés par Mines Albi.

Le [recalcul hebdomadaire du reliquat mensuel](changes/2026-11-14-recalcul-hebdomadaire-mensuel.md)
ajoute la cadence demandée, son activation et la comparaison courte de ses
effets sur les lots et l'attente client.

Le [placement des fabrications selon la capacité](changes/2026-11-14-placement-capacitaire-production.md)
réserve la charge avant lancement et compare deux essais de 135 jours au réel.
Le gain synthétique ne se retrouve pas pour 268967 avec la capacité actuelle ;
la comparaison précise aussi les limites de qualification et les quantités en transit.

L'[étude du programme usine et de la production progressive](PRODUCTION_REALISTE_20261115.md)
compare les étuis réellement prélevés aux consommations simulées. Elle distingue
le gain de calendrier, les limites de capacité et les effets jusqu'au client ;
le [rapport interactif local](../resultats/production_realiste_20261115.html)
permet de remonter d'une semaine aux programmes, composants et campagnes.

Le [cumul de production en mai](CUMUL_PRODUCTION_MAI_20261115.md) sépare le
défaut de date du graphique, les semaines inconnues et le blocage des nouveaux
lots par le programme expérimental ; l'essai couvre les deux produits.

La [couverture des besoins par les ordres initiaux](COUVERTURE_INITIALE_20261115.md)
remplace le blocage global par une vérification des engagements, des matières
et de la capacité datée, avec des courbes simulées complètes.

Les [essais sur les budgets et le carnet initial](BUDGETS_ET_CARNET_INITIAL_20261116.md)
écartent l'autorisation stricte par semaines pour 268967 faute de couverture
documentée. Le complément initial de 338928 rapproche le calendrier de 268091,
mais augmente son surplus de production et de stock ; la référence est conservée.

La [correction des promesses avec composants de remplacement](SUBSTITUTION_PROMESSES_20261115.md)
traite le décalage entre la matière utilisable à l'exécution et celle retenue
par le MRP pour une campagne engagée, avec comparaison avant/après.

L'[analyse de l'ensemble des données réelles, priorité 268967](changes/2026-11-14-analyse-reel-268967.md)
rapproche stocks, mouvements, production, demande, prévisions et finance sur
2025 ; elle distingue les écarts mesurés, les mécanismes simulés et les causes
industrielles encore inconnues.

L'[audit des règles MRP du 14 novembre](changes/2026-11-14-audit-regles-mrp.md)
examine chaque étape, sa place dans le système, ses preuves et les corrections
prioritaires hors capacité ; le moteur et le nominal restent conservés.

La [suite de l’audit et les tests discriminants](changes/2026-11-14-tests-regles-mrp.md)
étend la couverture à 51 mécanismes : passage de mois dans le moteur, transferts,
protection hebdomadaire, ordres fermes et information connue à la décision.
Elle conserve les défauts reproduits et distingue les règles exécutées des règles seulement relues.

Les [essais dédiés aux règles encore peu éprouvées](changes/2026-11-14-essais-regles-dedies.md)
comparent les effets du lissage et de la marge de planification, suivent les lots
jusqu'au dépôt et vérifient achats et libérations. Ils reproduisent aussi le
défaut de provenance quotidienne et délimitent la règle fournisseur encore absente.

L'[analyse de la production progressive et du besoin sur quatre semaines](changes/2026-11-14-production-progressive-4semaines.md)
compare les semaines réelles estimées et simulées, puis distingue le lissage du
signal, la consommation mensuelle des prévisions et le placement des lots.

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

[D1450 → D1810 : réel, prévu et simulé](archive/AMONT_AVAL_693055_20261104.html) :
deux calculs natifs de 56 jours pour 693055 ; raccourcir le transport ne corrige
pas les stocks de D1450 et dégrade ceux d’D1810. Les réceptions de mai sont
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
