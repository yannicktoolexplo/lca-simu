# Etudecas — comprendre le projet

Etudecas est le logiciel de l'étude de cas supply chain : il prépare un réseau
à partir des données métier, exécute les règles de stocks, production et
transport, puis construit une carte HTML pour explorer les résultats et les lots.

**Cette page est le point d'entrée pour comprendre et modifier le code.**
La [documentation par sujet](docs/README.md) approfondit les fonctions métier.
Les [résultats et cartes déjà produits](index.html) ont leur accueil séparé.

## Où commencer selon ce que tu veux faire

| Besoin | Endroit à ouvrir |
|---|---|
| Comprendre les dossiers et leur rôle | [Organisation ci-dessous](#organisation-des-dossiers) |
| Savoir où modifier une fonction | [Points de maintenance ci-dessous](#où-modifier-le-code) |
| Installer ou lancer une commande | [Guide des commandes](OPERATIONS.md) ; chaque commande indique si elle écrit des fichiers |
| Comprendre les lots, transports ou règles métier | [Sommaire thématique](docs/README.md) |
| Maintenir la documentation liée au code | [Automatisation documentaire](docs/AUTOMATION.md) |
| Voir ce qui a été rangé | [Rangement effectué et limites](#rangement-effectué-et-limites) |

## Le chemin principal du logiciel

```mermaid
flowchart LR
    A["Données métier et configuration"] --> B["Construction du graphe"]
    B --> C["Préparation des entrées"]
    C --> D["Moteur et règles métier"]
    D --> E["Fichiers de résultats"]
    E --> F["Carte HTML et suivi des lots"]
```

[run_etudecas_pipeline.py](run_etudecas_pipeline.py) coordonne les commandes.
Les étapes sont aussi appelables séparément : `graph` reconstruit le graphe,
`prepare` prépare ses entrées et `simulate` exécute le moteur.
`rebuild-map-5y` repart par défaut d'un **graphe déjà préparé** ; il ne
relit pas automatiquement tous les Excel. Les commandes de reconstruction
sont expliquées dans [OPERATIONS.md](OPERATIONS.md).

Ce graphe est actuellement
`simulation_prep/result/reference_baseline/_mrp_bom_tests/bom_weekly_mps_lotified_no_static_fallback_physical_floor.json`.
Malgré le mot « tests » dans son chemin, c'est une entrée du pipeline actif.
L'option `--refresh-input-graph` demande sa reconstruction à partir de l'amont.

Le code qui produit un résultat et le résultat lui-même ont des rôles différents :
modifier un CSV ou un HTML sous `result/` ne corrige pas le programme qui le génère.

## Organisation des dossiers

Les chemins ci-dessous sont relatifs à `etudecas/`. « Utilisé » désigne un
appel ou une référence trouvé dans le code, pas une certification de tous les
chemins d'exécution. Les fichiers ignorés par Git peuvent rester présents sur
ce poste, notamment les résultats, caches et anciennes données.

| Dossier | Rôle et place dans le projet |
|---|---|
| [data/](data/README.md) | Données métier sous `source/` ; graphes dérivés sous `geocoded/` et rapports sous `reports/`. `MANIFEST.json` identifie les entrées et anciens chemins. Ce dossier contient donc des sources **et** des produits de préparation. |
| [config/](config/) | Paramètres JSON chargés par `case_config.py` et classeur d'enrichissement traité par `knowledge_graph/`. |
| [knowledge_graph/](knowledge_graph/README.md) | Lecture/enrichissement du réseau, schéma JSON et interface Excel. |
| [geocoding/](geocoding/README.md) | Ajout des coordonnées des sites au réseau. |
| [simulation_prep/](simulation_prep/README.md) | Préparation des graphes et données MRP ; son sous-dossier `result/` contient les graphes préparés. |
| [simulation/](simulation/) | Code du moteur, règles, analyses et expériences ; **également** les sorties sous `result/`. Détail ci-dessous. |
| [visualization/](visualization/README.md) | Construction et publication des cartes dans `maps/` ; conditionnement des archives HTML autonomes dans `standalone_html.py`. |
| [risk/](risk/README.md) | Calculs de risque fournisseur. `supplier_criticality/local.py` fournit le calcul commun au pipeline et à la carte, sans dépendance vers la visualisation. |
| [analysis/](analysis/README.md) | Anciennes analyses et relais de compatibilité. Les trois rapports utilisés par le pipeline sont désormais implémentés dans `simulation/analysis/`. |
| [prototypes/](prototypes/README.md) | Recherche, calibrations et développements expérimentaux. L'ancien conditionneur HTML est un relais vers `visualization/standalone_html.py` ; l'enrichisseur de carte n'importe plus les prototypes. |
| [docs/](docs/README.md) | Guides métier et techniques, règles documentaires, pages générées et comptes rendus datés. |
| [documentation/](documentation/) | Programme Python qui construit et contrôle les pages de `docs/generated/` à partir des registres. |
| [testing/](testing/) | Outils de contrôle des CSV, cartes et parcours navigateur. Les anciennes commandes `journey_scenario_delivery.py` et `material_delivery.py` sont des relais ; leur implémentation est dans `visualization/maps/`. |
| [toolbox/](toolbox/) | Commandes communes pour lancer les contrôles et rassembler leurs preuves. Le code métier reste dans ses modules. |
| `artifacts/` | Journaux, captures et preuves locales produits par les contrôles. Certains scripts d'audit ponctuels y sont encore rangés. |
| [archive/](archive/README.md) | Anciens résultats, cartes et fichiers conservés pour relire les travaux antérieurs. Vérifier les références avant tout retrait. |
| [affichage_supply_script/](affichage_supply_script/README.md), [supplier_risk_kpi/](supplier_risk_kpi/README.md) | Anciens points d'entrée conservés comme relais vers `visualization/maps/` et `risk/supplier_criticality/`. |
| `donnees/` | Ancien emplacement remplacé par `data/source/` selon le manifeste ; un classeur subsiste localement. Son retrait demande une comparaison préalable. |
| `__pycache__/` | Cache Python créé à l'exécution. |

### À l'intérieur de simulation/

| Ensemble | Fonction |
|---|---|
| [engine/](simulation/engine/README.md) | Moteur canonique `run_first_simulation.py`, API Python, serveur HTTP et aides de contrôle. Le fichier `run_first_simulation_state_family_pilot.py` est une implémentation pilote distincte ; aucun appel n'a été trouvé dans les points d'entrée actifs examinés. |
| [lot_trace/](simulation/lot_trace/), [lot_policy/](simulation/lot_policy/), [logistics/](simulation/logistics/README.md) | Généalogie et suivi des lots, règles de taille des lots, consolidation et présentation des transports. |
| [run_format/](simulation/run_format/README.md) | Contrat du dossier de résultats : manifeste, objets métier et index des fichiers détaillés. |
| [analysis/](simulation/analysis/) | Analyses des sorties et valorisations appelées notamment par le pipeline. |
| [baselines/](simulation/baselines/), [scenarios/](simulation/scenarios/), [risk_scenarios/](simulation/risk_scenarios/) | Construction des références, variantes de scénarios et scénarios de risques. |
| [experiments/](simulation/experiments/), [sensibility/](simulation/sensibility/README.md) | Expériences ciblées et scripts de sensibilité. Deux familles de développements à inventorier avant de les fusionner. |
| [montecarlo/](simulation/montecarlo/README.md), [uncertainty/](simulation/uncertainty/) | Campagnes répétées et outils de représentation de l'incertitude. Certains résultats sont encore présents à côté des scripts. |
| `result/`, `sensibility_archives/` | Sorties et anciennes campagnes ; les chemins sont parfois encore référencés par des guides ou des tests. |

Les fichiers `test_*.py` et dossiers `tests/` sont répartis près des modules :
ils ne sont pas tous regroupés dans `testing/`.
Les petits modules directement sous `simulation/` fournissent aussi des
politiques communes : état initial, feedback, mesures et empreintes des sources.

## Où modifier le code

| Fonction | Points de maintenance |
|---|---|
| Enchaîner les étapes et choisir les fichiers | [run_etudecas_pipeline.py](run_etudecas_pipeline.py) |
| Charger la configuration du cas | [case_config.py](case_config.py) et [config/cases/data_poc.json](config/cases/data_poc.json) |
| Modifier les règles d'exécution | [simulation/engine/run_first_simulation.py](simulation/engine/run_first_simulation.py), puis les modules spécialisés concernés |
| Modifier l'accès Python ou HTTP au moteur | [simulation/engine/api.py](simulation/engine/api.py), [server.py](simulation/engine/server.py) et [http_contract.py](simulation/engine/http_contract.py) |
| Modifier la généalogie ou les données du suivi | [simulation/lot_trace/](simulation/lot_trace/) |
| Construire les données et graphiques de carte | [visualization/maps/build_supplychain_worldmap.py](visualization/maps/build_supplychain_worldmap.py), les modules `*_payload.py` et les adaptateurs de ce dossier |
| Publier un explorateur ou actualiser la vue matière | [journey_scenario_delivery.py](visualization/maps/journey_scenario_delivery.py) et [material_delivery.py](visualization/maps/material_delivery.py), sous `visualization/maps/` |
| Calculer la criticité commune au pipeline et à la carte | [risk/supplier_criticality/local.py](risk/supplier_criticality/local.py) |
| Modifier l'interface de carte | [worldmap_html_template.py](visualization/maps/worldmap_html_template.py), `lot_journey*.js`, `lot_material_trace.js`, `map_business_ui.js` et le CSS de l'explorateur |
| Modifier le diagnostic et ses actions | [decision_support.py](decision_support.py), [decision_actions.py](decision_actions.py) |
| Contrôler la provenance et écrire les fichiers | [provenance.py](provenance.py), [atomic_io.py](atomic_io.py) |
| Vérifier une référence documentaire enregistrée | [reference_status.py](reference_status.py) ; ses résultats concernent le manifeste choisi |

[launch_interactive_map.py](launch_interactive_map.py) **ouvre une carte existante
et démarre une API locale**. Il ne construit pas le HTML ; son chemin par défaut
vise une ancienne carte. Utiliser un chemin explicite pour cet usage, avec le
[contrat de l'API](docs/SIMULATION_INPUT_CONTRACT.md).

Les JavaScript de lots sont encore assemblés dans une portée commune et
utilisent des fonctions du template. Ils ne sont pas des composants autonomes.
Le constructeur de carte produit aussi certains rapports et classements ;
l'option `--read-only-source` encadre ses écritures annexes dans les sources.

[simulation/run_first_simulation.py](simulation/run_first_simulation.py) et
[affichage_supply_script/build_supplychain_worldmap.py](affichage_supply_script/build_supplychain_worldmap.py)
sont des relais de compatibilité : modifier leurs implémentations canoniques,
pas créer une deuxième logique dans ces relais.

Le dossier voisin [etudecas_codex_multiagent_pack](../etudecas_codex_multiagent_pack/README.md)
contient un kit de démonstration et un déploiement préparé des rôles. Les
instructions actives du travail multi-agent sont à la racine du dépôt dans
`AGENTS.md`, `.codex/` et `.agents/`, avec le
[guide opérationnel](docs/MULTI_AGENT_OPERATIONNEL.md).

## Rangement effectué et limites

Le rangement du code est appliqué. Les anciennes entrées ci-dessous restent
de petits relais : elles ne contiennent plus une deuxième implémentation.
Les commandes existantes et leurs chemins de données par défaut sont conservés.

| Fonction rangée | Emplacement de maintenance | Compatibilité conservée |
|---|---|---|
| Rapports composants, produits finis et rapprochement aux sources | `simulation/analysis/report_component_immobilized_stock.py`, `report_finished_goods_stock_value.py`, `audit_source_truth_alignment.py` | Relais dans `analysis/from_simulation/`. Le pipeline importe directement le nouvel emplacement. |
| Criticité locale des fournisseurs | `risk/supplier_criticality/local.py` | Fonction encore importable depuis le constructeur de carte ; pipeline et carte utilisent la même implémentation. |
| Publication d'un explorateur de scénario et actualisation matière | `visualization/maps/journey_scenario_delivery.py`, `material_delivery.py` | Relais sous `testing/` ; ressources JS, CSS et données résolues aux mêmes endroits. |
| Archives HTML autonomes | `visualization/standalone_html.py` | Ancien module `prototypes/scan_2027_risk_control/standalone_single_html.py` redirigé ; les outils de visualisation importent le module commun. |

Le moteur et le template HTML restent volumineux. Leur découpage complet
constitue un refactoring supplémentaire, au-delà de ces déplacements. La
criticité a déjà été extraite du constructeur de carte ; les interfaces entre
modules JavaScript restent à séparer progressivement.

Les résultats de simulation, graphes d'entrée, archives et campagnes antérieures
gardent leurs chemins. Ils constituent un rangement distinct : les déplacer
demande de reprendre leurs manifestes et lecteurs. Les suffixes `v1`, `v2`,
`pilot` ou le nom `archive` ne suffisent pas à décider qu'un fichier est inutilisé.

## Documentation et résultats

- [Documentation par sujet](docs/README.md) : guides du code et du métier.
- [Commandes et effets](OPERATIONS.md) : installation, préparation et exécution.
- [Résultats locaux](index.html) : cartes déjà produites et bilans de livraison.
- [Historique des audits](docs/README.md#consulter-les-livraisons-et-lhistorique) : constats et preuves datés, à lire pour leur périmètre.

Cette carte du code est fondée sur les points d'entrée, imports, commandes et
guides examinés le 20 septembre 2026. Elle ne classe pas chaque ancien script
comme utilisé ou inutilisé et ne remplace pas les tests lors d'un déplacement.
