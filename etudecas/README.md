# Etudecas — comprendre et utiliser le code

Etudecas simule les stocks, la production et les transports d'une supply chain,
puis construit des cartes HTML pour explorer les résultats et suivre les lots.
Le modèle utilise la dynamique des systèmes : stocks et encours évoluent avec
les flux, délais et décisions ; certains risques dépendent de l'état du système.

**Le parcours à comprendre : données → scénario → boucle quotidienne → lots et
transports → indicateurs → carte.** Les études réutilisent ce parcours avec des
paramètres ou des tirages différents.

La simplification conserve les fonctionnalités et un parcours courant par étude.
Les anciens scripts ponctuels quittent le code actif après sauvegarde et examen de
leurs dépendances. La cible d'environ 50 fichiers de code, tests et interface compris,
**n'est pas encore atteinte**. Le [plan](docs/PLAN_SIMPLIFICATION.md) décrit la suite ;
l'[inventaire Python](docs/INVENTAIRE_PYTHON.csv) sert à retrouver une implémentation.

Pour travailler, utiliser ce guide, [les commandes](OPERATIONS.md),
[les règles métier](docs/README.md) et [les quatre cartes](index.html).
Les anciens `tmp`, audits et comptes rendus sont regroupés dans
[l'archive](archive/README.md). Les références de vérification encore nécessaires
et les pièces de l'incident Sophos restent identifiées séparément.

## Les commandes courantes

Depuis la racine du dépôt, avec l'environnement Python du projet :

```powershell
# Recalculer uniquement le nominal sur cinq ans (1 825 jours).
python -B -m etudecas.regenerate --scenario nominal
# Recalculer les quatre scénarios et reconstruire la carte récente complète.
python -B -m etudecas.regenerate --delivery lots
# Examiner une commande sans lancer le calcul.
python -B -m etudecas.regenerate --scenario nominal --dry-run
# Choisir une étude : sensibilité, incertitude, cascades ou fournisseurs.
python -B -m etudecas.simulation.studies --help
```

Chaque calcul crée son dossier de résultats. Les quatre HTML conservés sont
accessibles depuis [l'accueil](index.html). Le [guide de reconstruction](docs/REGENERER_RESULTATS.md)
précise ce qui peut être recalculé ou seulement réassemblé depuis un HTML historique.
Le [guide des commandes](OPERATIONS.md) couvre l'installation et la préparation des entrées.

## Choisir une étude

Utiliser `python -B -m etudecas.simulation.studies MODE --help` pour consulter
les entrées et paramètres du mode choisi. Cette aide ne lance aucun calcul.

| Besoin | Mode |
|---|---|
| Préparer et rassembler un plan de sensibilité | `sensitivity` |
| Classer et rejouer des scénarios choisis | `targeted` |
| Mesurer l'effet de paramètres incertains dans des contextes appariés | `paired` |
| Relier la propagation aux périodes et aux lots | `temporal` |
| Propager un incident et comparer des interventions | `cascade` |
| Comparer les configurations de supply chain | `supplier-configurations` |
| Calibrer des configurations de service | `supplier-calibration` |
| Comparer les incidents fournisseurs sur des fenêtres comparables | `supplier-campaign` |

Les tirages Monte Carlo et leurs distributions restent dans
[`simulation/montecarlo`](simulation/montecarlo/README.md). Les méthodes de
[sensibilité](simulation/sensibility/README.md) conservent leurs calculs propres
(variations locales, seuils, stress temporels) pendant leur regroupement.
Les études fournisseurs et cascades sont décrites dans le
[guide de recherche courant](prototypes/scan_2027_risk_control/README.md).
Un mode commun ne rend pas ces méthodes scientifiques interchangeables.

## Le chemin principal du logiciel

```mermaid
flowchart LR
    A[Données métier et graphe préparé] --> B[Moteur quotidien]
    B --> C[Résultats et registre des lots]
    C --> D[Analyses et indicateurs]
    C --> E[Carte HTML et deux suivis de lots]
    D --> E
```

| Repère | Fichier ou dossier | Ce que l'on y trouve |
|---|---|---|
| 1. Entrées | [case_config.py](case_config.py), [simulation_prep/](simulation_prep/README.md) | Choix des données et préparation du graphe. |
| 2. Lancement | [regenerate.py](regenerate.py), [engine/api.py](simulation/engine/api.py) | Scénarios, paramètres, horizon, graines et dossier de sortie. |
| 3. Calcul | [engine/run_first_simulation.py](simulation/engine/run_first_simulation.py) | Initialisation et boucle quotidienne dans `main` : stocks, besoins, production, transports et risques. |
| 4. Traçabilité | [lot_trace/](simulation/lot_trace/), [lot_policy/](simulation/lot_policy/), [logistics/](simulation/logistics/README.md) | Généalogie, tailles de lots, palettes, expéditions et camions. Le registre `LotLedger` reste défini dans le moteur. |
| 5. Résultats | [run_format/](simulation/run_format/README.md), [simulation/analysis/](simulation/analysis/) | CSV détaillés, résumés, index et analyses. |
| 6. Carte | [build_supplychain_worldmap.py](visualization/maps/build_supplychain_worldmap.py), [worldmap_html_template.py](visualization/maps/worldmap_html_template.py) | Données des panneaux et interface. Les modules `*_payload.py` préparent les informations affichées. |

Pour lire le moteur, commencer dans `main` par les paramètres et l'état initial,
puis chercher `for day in range(total_timeline_days)` : c'est la boucle quotidienne.
Les classes et fonctions placées avant `main` lui servent d'outils, notamment
`LotLedger` pour les lots. En fin de `main`, les écritures CSV puis
`export_run_package` préparent les résultats que la carte pourra lire.

Le graphe de référence est dans `simulation_prep/result/reference_baseline/_mrp_bom_tests/` :
**c'est une entrée active**, malgré son nom. Le pipeline `run_etudecas_pipeline.py`
coordonne la préparation et les analyses ; `rebuild-map-5y` repart par défaut d'un
graphe préparé. `launch_interactive_map.py` ouvre un HTML existant avec une API locale.

## Organisation des dossiers

| Rôle | Emplacement |
|---|---|
| Données et préparation | [data/](data/README.md), `config/`, [knowledge_graph/](knowledge_graph/README.md), `geocoding/`, `simulation_prep/` |
| Moteur et études courantes | `simulation/` : moteur, lots, logistique, analyses, scénarios, sensibilité, Monte Carlo et incertitude |
| Recherche et analyses spécialisées | [prototypes/](prototypes/README.md), [analysis/](analysis/README.md) |
| Cartes et présentations autonomes | [visualization/](visualization/README.md) |
| Vérification et documentation | `testing/`, `toolbox/`, `documentation/`, [docs/](docs/README.md) |
| Résultats et preuves locales | `resultats/`, `simulation/result/`, `artifacts/testing/` |

Les études de sensibilité, cascades, criticité et audit fournisseur, contexte
collecté sur Internet, Monte Carlo et propagation des paramètres incertains
restent les capacités à conserver. Le [plan](docs/PLAN_SIMPLIFICATION.md#ce-qui-doit-rester-possible)
précise ce périmètre. L'audit et la criticité sont dans [risk/](risk/README.md) ;
les faits du contexte public conservent leur provenance et se distinguent des
estimations et hypothèses.
Les tests du cœur sont regroupés dans [tests/](tests/README.md), par thème.
Les tests spécialisés restent près du sous-module qu'ils vérifient.

Tous ces fichiers ne sont pas chargés pour chaque simulation. Le moteur, la
carte, les études spécialisées et les tests ont des parcours différents.
Pour comprendre une simulation courante, suivre les six repères ci-dessus ;
ouvrir `prototypes/` lorsqu'une question de recherche précise le nécessite.
Les anciennes versions encore importées peuvent fournir des fonctions au parcours
courant ; leur présence n'impose pas de lancer toutes les campagnes historiques.
Les modules retirés restent dans leurs capsules de reproduction. Les dépendances
et différences de méthode doivent être examinées avant tout nouveau retrait.

## Où modifier le code

| Modification | Point de maintenance |
|---|---|
| Conventions métier | [model_semantics.py](simulation/engine/model_semantics.py), puis le module concerné |
| API Python / HTTP | `simulation/engine/api.py`, `http_contract.py`, `server.py` |
| Criticité fournisseur commune | `risk/supplier_criticality/local.py` |
| Diagnostic et actions | `decision_support.py`, `decision_actions.py` |
| Parcours interactif des lots | `visualization/maps/lot_journey.js`, `lot_material_trace.js`, template et payloads |
| Publication d'un suivi de scénario | `python -m etudecas.visualization.maps.material_delivery --mode scenario` |
| Actualisation de la vue matière | `python -m etudecas.visualization.maps.material_delivery` |
| Conditionnement des HTML historiques | `visualization/standalone_html.py`, `rebuild_archives.py` |

## Vérification et limites

Les retraits, regroupements et contrôles de la passe courante sont détaillés dans
le [bilan de simplification](artifacts/testing/human_code_20260925/BILAN.md).
Les quatre HTML conservés restent les références ; la carte récente peut être
recalculée, tandis que les présentations historiques sont réassemblées à partir
de leurs données embarquées selon le guide de reconstruction.

Pour une modification du moteur, vérifier un vrai calcul sur cinq ans : trajectoires,
commandes, événements, lots et transports. La [toolbox](docs/MULTI_AGENT_OPERATIONNEL.md)
rassemble tests, invariants CSV et contrôles du navigateur ; la
[documentation automatique](docs/AUTOMATION.md) relie les règles métier au code.

Après l'incident Sophos, sélectionner les tests après lecture de leurs cas et
fixtures. Les tests d'altération de fichiers, de restauration de dates et de
disparition simulée sont exclus. Utiliser des calculs en mémoire, des simulations
normales dans de nouveaux dossiers et des comparaisons en lecture seule.

La réussite de ces contrôles ne certifie pas la calibration industrielle.
Les conventions confirmées comprennent les quantités physiques entières en UN,
la sécurité lundi-vendredi, les cibles sources du nominal et 100 % des jours source
au dépôt ; `tau_process` conserve sa convention actuelle de planification.

Le [pack multi-agent](../etudecas_codex_multiagent_pack/README.md) conserve les
profils, skills et leur copie de déploiement. Les instructions actives sont à la
racine dans `AGENTS.md`, `.codex/` et `.agents/`. La toolbox est le point d'entrée
des contrôles locaux.
