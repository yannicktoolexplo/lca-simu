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

## Ce qui a quitté le parcours courant

Les anciennes publications intermédiaires, démos de réunion, moniteurs ponctuels,
relais d'une exécution passée et replays présélectionnés top 4/toutes les liaisons
ont quitté le code actif avec leurs tests propres. Leur sélection historique
exacte ne devient pas celle du parcours actuel.

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
