# Études fournisseurs et cascades

Ce dossier contient les méthodes de recherche utilisées autour du même moteur
Etudecas. Pour travailler sur une étude courante, commencer par l'entrée
`python -m etudecas.simulation.studies`, puis choisir la capacité ci-dessous.

| Besoin | Mode de `simulation.studies` | Implémentation courante |
|---|---|---|
| Propager un incident et comparer des interventions | `cascade` | `canonical_cascade_campaign.py` |
| Comparer des configurations de supply chain | `supplier-configurations` | `supplier_service_landscape_campaign.py` |
| Calibrer des configurations de service | `supplier-calibration` | `supplier_service_regime_calibration_runner.py` |
| Comparer les incidents fournisseurs sur des fenêtres comparables | `supplier-campaign` | `supplier_operating_point_full_campaign_v8.py` |

Exemple : `python -m etudecas.simulation.studies cascade --help`.
Chaque mode conserve les paramètres et prérequis de sa méthode. L'aide ne lance
pas de calcul. Les plans, données et validations exigés restent explicites.

Le nominal sur cinq ans et la carte complète se reconstruisent avec
`python -m etudecas.regenerate --scenario nominal` et
`python -m etudecas.regenerate --delivery lots`. Les quatre présentations
conservées sont accessibles depuis [l'accueil](../../index.html).

## Comment lire le code courant

1. Le plan d'étude fixe les paramètres, graines et scénarios à comparer.
2. Le runner appelle le moteur avec ces paramètres, dans des sorties distinctes.
3. Les calculs d'indicateurs rapprochent les trajectoires et les lots.
4. Le finaliseur vérifie les preuves ; le constructeur HTML présente les résultats.

Pour la campagne fournisseur actuelle, le point d'entrée V8 s'appuie encore
sur les calculs V4 et certaines bases V2. Ces bases ne sont pas des campagnes à
lancer en parallèle par défaut. Les fonctions communes sont dans
`supplier_campaign_mechanics.py`, avec un contexte explicite propre à chaque
protocole. Les adaptateurs de lancement/finalisation sont regroupés dans
`supplier_campaign_adapters.py`. Le superviseur courant est
`supplier_stage_runtime.py`.

Les versions scientifiques ne sont pas interchangeables : fenêtres comparables,
tirages appariés, validation indépendante et méthodes de sélection doivent rester
explicites. La comparaison préliminaire de criticité est conservée, mais ne
remplace pas la validation de la campagne V8.

La préparation du protocole ne demande plus les anciens essais 021081/773474
pour rédiger son bilan historique. Pour joindre cette comparaison, fournir
ensemble `--legacy-combined` et `--legacy-stock` à
`supplier_service_regime_calibration_protocol`. Sans ces options, leur absence
est indiquée, sans chiffre déduit. Les données et preuves de la référence de
calcul restent requises. Le runner de calibration conserve son verrou sur
l'artefact V2 validé : préparer un autre plan ne suffit pas à autoriser son exécution.

## Ce qui a quitté le parcours courant

Le lanceur et le finaliseur V2, avec leurs deux fichiers de tests propres, sont
retirés. Le lancement et la consolidation courants utilisent V4 et les profils
V5–V8. Deux tests de contrat et de classement ex aequo sont conservés côté V4.
Le runner V2 reste présent : la prévalidation fine utilise son lecteur et une
validation historique exige encore son identité exacte. Retirer ce dernier
fichier demande de traiter ces dépendances, pas de substituer silencieusement V4.
Les quatre fichiers retirés sont sauvegardés dans la
[capsule avant retrait](../../config/reproduction_20260920/sources/a99c4246c2be2b0dcc0a690e1cadff454c259e3184f05ee408e832fe1227b9d1.zip).
Les plans existants gardent leur révision de sources ; ils ne deviennent pas
automatiquement exécutables avec le nouveau code.

Les anciennes publications intermédiaires, démos de réunion, moniteurs ponctuels,
relais d'une exécution passée et replays présélectionnés top 4/toutes les liaisons
ont quitté le code actif avec leurs tests propres. Leur sélection historique
exacte ne devient pas celle du parcours actuel.

Les cinq campagnes ponctuelles `supplier_021081_*` et
`supplier_orderbook_only_lane_campaign.py`, ainsi que leurs deux tests exclusifs,
sont également retirées. Le moteur conserve les commandes ouvertes, les incidents
fournisseurs et les variations explicites de stock et de BOM. Le calendrier FIFO
estimé de l'ancien essai 021081 reste une hypothèse historique, sans équivalent
natif identique. Une sensibilité BOM demande encore de préparer des graphes distincts.
Ces sept fichiers sont conservés dans la
[capsule de référence avant cette passe](../../config/reproduction_20260920/sources/f2a5da74a73edb13a9cb9f44f0c7f4e24cdbd52d196e87d483d911160a1f1ec7.zip).

Leurs sources sont conservées à l'identique dans la
[capsule antérieure](../../config/reproduction_20260920/sources/347f4a298c6e11027db7a40513f44abebc8060daec05bb19e75ea2b11e5e4c78.zip).
La liste des retraits et leurs contrôles est dans le
[bilan de simplification](../../artifacts/testing/human_code_20260925/BILAN.md).
Pour reproduire une ancienne commande, utiliser son environnement de reproduction ;
ne pas réintroduire les fichiers dans le parcours courant sans vérifier les dépendances.

## Vérification et limites

La source nominale, les quantités physiques UN entières et les deux suivis de lots
restent les références. Les sensibilités sont des variantes séparées. Les contrôles
techniques ne certifient pas la calibration industrielle.

Après l'incident Sophos du 23 septembre, seuls les tests relus et explicitement
sélectionnés sont exécutables dans notre procédure : calculs en mémoire,
simulations normales et comparaisons en lecture seule. Les anciens tests d'altération
de fichiers, de dates ou de disparition simulée restent exclus.

Le [plan global](../../docs/PLAN_SIMPLIFICATION.md) décrit la cible d'environ
50 fichiers de code, tests et interface compris. Cette cible n'est pas encore atteinte.
