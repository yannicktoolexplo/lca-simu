**Analyse d’Etudecas et du pack multi-agent — 16 septembre 2026**

**Conclusion**

Etudecas possède une base fonctionnelle riche : simulation physique, MRP, stocks, lots, risques fournisseurs, expériences appariées, visualisation et traçabilité. Son architecture évolue dans une direction cohérente, avec une API de simulation et des contrats de sortie dédiés. Sa principale fragilité est l’écart entre ces interfaces structurées et une implémentation encore très concentrée, accompagnée de validations parfois trop permissives.

Le pack est utile comme référentiel de travail et exemple pédagogique. Ce n’est ni le moteur de simulation ni un orchestrateur d’agents exécutable. Plusieurs défauts de ses exemples et validateurs empêchent de le considérer comme une référence robuste sans corrections.

La suite complète confirme que le dépôt n’est pas entièrement validé dans cet environnement : **2 113 tests réussis, 126 échecs, 7 erreurs et 7 tests ignorés**. La commande unittest documentée est verte mais ne couvre qu’un sous-ensemble. Plusieurs échecs sont liés à la provenance et aux fins de ligne Windows ; d’autres révèlent une rupture de jointure entre expéditions et lots, des divergences de contrats ou un appel de fonction inexistante.

**Périmètre et méthode**

Le second dossier réellement présent est `etudecas_codex_multiagent_pack/`, à la racine du dépôt. Aucun dossier `etudecas/_codex/_multiagent/_pack` n’a été trouvé. L’analyse porte sur les deux dossiers existants.

Inventaire des fichiers et de leur suivi Git, lecture des documentations et des interfaces principales, analyse syntaxique des 590 fichiers Python d’Etudecas, inspection ciblée des moteurs, validateurs, configurations, tests et contrats, exécution du diagnostic et des suites de tests, reproductions minimales des défauts. Le pack a fait l’objet d’une revue indépendante selon ses règles AGENTS.md.

Il s’agit d’un audit transversal approfondi, pas d’une lecture ligne par ligne des quelque 484 000 lignes Python, ni d’une certification des résultats scientifiques. Aucune campagne opérationnelle complète sur cinq ans n’a été relancée. Les gros CSV ont été inventoriés, pas intégralement réconciliés.

**Inventaire mesuré**

Chiffres hors `__pycache__`, au début de l’analyse. Go et Mo sont exprimés en base décimale.

| Indicateur | Etudecas | Pack |
|---|---:|---:|
| Fichiers locaux | 10 795 | 102 |
| Fichiers suivis par Git | 1 290 | 99 |
| Fichiers Python | 590 | 39 |
| Fichiers de tests Python | 219 | 8 |
| Volume local | 14,386 Go | Moins de 1 Mo |
| Volume des fichiers Etudecas suivis par Git | 308,13 Mo | — |

`simulation/` représente 14,336 Go. `prototypes/` contient 329 fichiers Python, 315 962 lignes et 144 fichiers de tests : les recherches et campagnes constituent désormais la majorité du code Python. Le nom « prototypes » ne reflète donc plus à lui seul leur importance dans le projet.

Deux fichiers `lot_causal_links.csv` de replay ciblé occupent respectivement 2,400 et 2,338 Go. Une carte historique atteint 157,8 Mo. Ces observations concernent les artefacts existants ; elles ne prouvent pas que chaque reconstruction actuelle génère les mêmes volumes.

**Architecture du vrai projet**

Le flux principal est : sources Excel/CSV et JSON → enrichissement du graphe → géocodage → préparation des politiques et états initiaux → simulation → analyses, contrats de run et cartes.

| Couche | Rôle et appréciation |
|---|---|
| `data/` | Sources et manifeste canonique. La distinction entre données d’entrée et références de comparaison est utile. |
| `knowledge_graph/` | Contrat JSON, enrichissement Excel, rapports. Bonne frontière conceptuelle ; validation structurelle à durcir. |
| `geocoding/` | Géocodage hors ligne, séparé du moteur. |
| `simulation_prep/` | Transformation du graphe, état initial, données MRP et baselines. Étape déterminante pour l’interprétation des résultats. |
| `simulation/engine/` | API typée, contrôles externes, politique de feedback et moteur historique. Interface structurée, mais calcul principal monolithique. |
| `simulation/lot_policy/`, `lot_trace/`, `logistics/` | Modules spécialisés pour politique de lots, généalogie, causalité et consolidation. Découpage pertinent à poursuivre. |
| `simulation/run_format/` | Contrat stable `run_manifest`, nœuds, flux, KPI et index d’artefacts. Bonne cible pour les futurs consommateurs. |
| `simulation/experiments/` | Sensibilités génériques et replays ciblés, séparés des scripts historiques `sensibility/`. |
| `simulation/montecarlo/`, `uncertainty/` | Incertitude, profils adaptatifs, checkpoints, diagnostics et expériences appariées. |
| `visualization/maps/` | Assemblage des payloads et HTML autonome, adaptateurs pour les campagnes. Couplage et taille encore importants. |
| `risk/` | Criticité fournisseurs et analyses associées. |
| `prototypes/scan_2027_risk_control/` | Contrôle, calibration, campagnes fournisseurs, livraisons et audits scientifiques. Domaine devenu très volumineux. |
| `analysis/`, `archive/`, wrappers historiques | Conservation et compatibilité des usages précédents. |

Le graphe actif contient 35 nœuds, 26 articles, 39 arcs et un scénario `scn:BASE`. Il passe le validateur de graphe existant sans anomalie déclarée. Cela confirme sa conformité aux contrôles actuellement implémentés, pas l’exactitude de toutes ses hypothèses.

Les nouvelles frontières sont déjà présentes : `SimulationRequest`, `SimulationOverrides`, `SimulationResult`, package de run générique et payloads de lots. Une réécriture complète n’est donc pas nécessaire pour améliorer le projet ; il est préférable de renforcer puis d’exploiter ces interfaces.

L’environnement minimal est simple : `requirements-etudecas.txt` déclare NumPy, pandas, openpyxl et Matplotlib. Ces dépendances sont définies par des versions minimales, sans verrouillage exact dans ce fichier. Le seul `pyproject.toml` suivi trouvé appartient au pack. Pour reproduire une campagne scientifique, enregistrer aussi les versions Python et bibliothèques réellement utilisées ; la seule configuration métier ne suffit pas à figer l’environnement de calcul.

**Constats prioritaires sur Etudecas**

**E1 — Priorité haute : la validation du package peut annoncer un faux succès.**

Dans `etudecas/simulation/run_format/validator.py:65`, les contrôles utilisent les attributs `exists` et `row_count` enregistrés dans l’index. Ils ne revérifient pas les CSV physiques. Les KPI sont essentiellement contrôlés par l’existence de leur point d’entrée, sans validation de leur contenu.

Reproduction dans un répertoire temporaire : un manifeste valide, des nœuds et flux contenant chacun `{}`, des KPI vides et un index déclarant trois CSV absents comme présents donnent tous les contrôles à `ok=True`.

Conséquence : déplacement, nettoyage ou détérioration d’un run peuvent laisser une validation verte. Le validateur doit résoudre les chemins selon le contrat, vérifier les fichiers effectivement présents, analyser les structures et contrôler au minimum identifiants, références et valeurs numériques. Les invariants physiques doivent rester des contrôles supplémentaires explicites.

**E2 — Priorité haute : la commande de tests recommandée ne couvre pas tous les tests.**

`python -m unittest discover -s etudecas -p "test*.py" -v` découvre 243 tests dans 46 modules, alors que 219 fichiers de tests sont présents. Les fonctions pytest ne sont pas exécutées par unittest ; certains sous-dossiers ne sont pas non plus parcourus de la même façon. Cela touche notamment les campagnes SCAN, plusieurs tests de contrôle et le test du pipeline principal.

Le README du pack et ses règles de validation utilisent cette commande comme minimum. Elle ne suffit pas à qualifier la non-régression globale. Définir une commande pytest canonique, avec un ensemble rapide et des intégrations explicitement identifiées. Aucun workflow n’a été trouvé dans `.github/workflows` ; cela ne permet pas d’exclure une CI externe.

**E3 — Priorité haute si l’API locale est utilisée : frontière HTTP trop permissive.**

`engine/server.py:31` accepte toutes les origines CORS ; `server.py:59` transmet directement le JSON à `request_from_dict`. Celui-ci accepte notamment un `run_script`, un `output_dir` et des arguments moteur libres. `analysis_batch_common.py:435` exécute ensuite le script demandé avec l’interpréteur Python courant.

Le serveur écoute localhost par défaut, ce qui limite l’exposition réseau directe. Toutefois, localhost ne remplace pas une validation des commandes accessibles au navigateur. Le code HTTP permet de sélectionner un script local et des chemins d’écriture sans restriction applicative ; aucune authentification, limite de travail concurrent ou durée maximale de sous-processus n’apparaît dans cette interface.

Séparer le contrat interne de confiance du contrat HTTP : moteur imposé côté serveur, répertoire de résultats contrôlé, liste de champs autorisés, contrôle d’origine/token compatible avec l’ouverture locale de la carte, limites de taille et d’exécution. Constat issu du code ; aucun scénario d’exploitation navigateur n’a été exécuté.

**E4 — Priorité moyenne : validations de types et numériques incomplètes.**

`knowledge_graph/schema.py:142` considère `float(value)` comme preuve de validité numérique : `NaN` et les infinis passent. Reproduction : un stock initial `NaN` ne produit aucune anomalie. Une liste `items=["invalid"]` provoque un `AttributeError` au lieu d’un rapport de validation. Certaines relations et valeurs manquantes ne sont pas vérifiées exhaustivement.

`engine/api.py:179` convertit plusieurs champs avec `bool(...)`. Reproduction : les chaînes JSON `"false"` deviennent `True` pour `common_random_numbers` et `run_lot_audit`. Un horizon négatif est accepté par le parseur de requête. Un contrat strict doit refuser les mauvais types plutôt que leur donner une signification inattendue.

**E5 — Priorité moyenne : généricité encore partielle.**

`case_config.py:116` charge globalement `config/cases/data_poc.json` à l’import. Ces constantes sont ensuite importées par le moteur. Une configuration absente retourne silencieusement `{}` à la ligne 13. Les surcharges de graphe existantes améliorent certains usages, mais ne remplacent pas une configuration de cas explicitement transmise à toutes les couches.

Le pipeline contient également des listes de couples nœud/article et des générateurs de risques calibrés pour le cas actif. Le rendu conserve des exceptions métier dans `visualization/maps/map_payload_builder.py:26`, notamment un nœud masqué et des corrections géographiques pour des fournisseurs précis. C’est compréhensible pour un outil de cas d’étude, mais ces données doivent être distinguées du contrat générique. Préférer un objet de contexte explicite chargé et validé pour chaque run ; prévoir un test de deux cas différents exécutés dans un même processus.

**E6 — Priorité moyenne : concentration du code et variante de moteur dupliquée.**

| Fichier | Lignes |
|---|---:|
| `simulation/engine/run_first_simulation.py` | 17 295 |
| `simulation/engine/run_first_simulation_state_family_pilot.py` | 15 631 |
| `visualization/maps/worldmap_html_template.py` | 16 041 |
| `visualization/maps/build_supplychain_worldmap.py` | 13 128 |
| `run_etudecas_pipeline.py` | 3 326 |

Le `main()` du moteur canonique représente 10 492 lignes. Le template HTML explique une partie de la taille du module de rendu, mais le moteur concentre réellement de nombreuses responsabilités. Comparaison AST des fonctions de premier niveau des deux moteurs : 91 noms communs, dont 81 implémentations identiques. Cela crée un risque de divergence lors des corrections.

Extraire progressivement initialisation, transition journalière, approvisionnement, production, risques, comptabilité et export, en conservant des références de résultats déterministes. Clarifier le statut de la variante pilote avant de la supprimer ou de la fusionner.

**E7 — Priorité moyenne : politique de stockage partiellement appliquée.**

Les profils compacts, checkpoints et règles `.gitignore` vont dans le bon sens. Cependant, plusieurs CSV lourds restent suivis par Git : quatre `mrp_trace_daily.csv` d’environ 30 Mo chacun ont été identifiés. Ajouter un motif à `.gitignore` ne retire pas un fichier déjà suivi.

Le contrat compact indexe des artefacts externes au dossier `run/` : conserver uniquement `run/` ne suffit donc pas nécessairement à rendre un résultat portable ou exploitable. Définir un export autonome compact et un export de diagnostic ; ne nettoyer qu’après vérification des références et de la reproductibilité. Aucun artefact n’a été supprimé pendant cet audit.

**E8 — Priorité moyenne : documentation opérationnelle décalée des valeurs par défaut.**

README et OPERATIONS présentent Monte Carlo comme une option à ajouter via `--with-montecarlo`. Le parseur actuel active `--require-montecarlo` par défaut et fixe `--montecarlo-runs` à 200 ; une reconstruction opérationnelle peut donc déclencher des calculs sensiblement plus longs que ce que suggère la documentation. Voir `run_etudecas_pipeline.py:2945`.

Documenter séparément le run de vérification rapide et la reconstruction opérationnelle complète, en reprenant les options réellement actives.

**E9 — Priorité haute : contrôles de provenance sensibles aux fins de ligne Windows.**

Le test `test_generated_v3_contract_when_audited_sources_are_available` échoue sur la livraison externe disponible dans cet environnement : « Le builder ne correspond plus au manifeste. » Une exécution ciblée reproduit l’échec en 2,82 secondes. `build_industrial_supply_preliminary_complete_v3.py:2268` compare l’empreinte du builder courant à celle enregistrée dans le manifeste.

Le diagnostic complémentaire identifie précisément la cause : l’empreinte du fichier local en CRLF vaut `99471a5e…ff255e91`, tandis que le même fichier normalisé LF vaut `1b70b09c…18ca260`, exactement l’empreinte du manifeste. Il ne s’agit donc pas ici d’une différence de logique du builder.

Un second test représentatif, `test_complete_adaptive_campaign_writes_global_and_product_results`, échoue pour la même raison. Le finaliseur V2 fixe une empreinte source à la ligne 62 et vérifie les octets bruts à la ligne 591. L’empreinte attendue `dafb0540…e4444d` correspond au contenu Git LF ; le fichier local CRLF donne `725a0f79…b3618c`. `git ls-files --eol` confirme `i/lf w/crlf`. L’échec intervient avant l’appel du stub de validation du test.

Le mécanisme de provenance reste utile, mais sa représentation doit être définie : imposer LF aux sources concernées via une politique de dépôt, ou versionner une méthode d’empreinte canonique qui normalise explicitement les fins de ligne des sources textuelles. Ne pas retirer les vérifications SHA-256. Ces deux échecs ne prouvent pas une régression métier. Le premier montre également qu’une partie de la suite dépend d’artefacts locaux externes : distinguer ces tests des tests reproductibles sur fixtures.

**E10 — Priorité haute pour le protocole concerné : appel de fonction inexistante.**

Trois tests du protocole d’action après sélection des fournisseurs échouent avec un `AttributeError`. `supplier_post_top3_action_protocol.py:725` appelle `v2_selector._stable_v2_suppliers(...)`, mais cette fonction n’existe pas dans le module `supplier_v2_controllable_action_selector`. La recherche du symbole retrouve uniquement son appel. Ce défaut est distinct des problèmes d’empreinte : restaurer un contrat public de sélection ou adapter l’appel et ses tests.

**E11 — Priorité moyenne : divergence entre les tests Monte Carlo et le contrat actuel de provenance.**

Les deux tests aux lignes 54 et 83 de `test_run_etudecas_pipeline.py` attendent la réutilisation de résumés externes ne contenant que l’horizon et le nombre de runs. La fonction actuelle exige une provenance vers le run cible pour les résumés partagés (`run_etudecas_pipeline.py:463` et `:493`), puis retourne le chemin local attendu si aucun candidat ne convient.

Les fixtures ne fournissent pas cette provenance. L’échec ne prouve donc pas que le filtrage actuel est incorrect : sa sévérité peut être intentionnelle et protège contre un mélange de runs. Il faut décider et documenter le contrat de réutilisation, puis tester explicitement les cas compatible, incompatible et absent ; ne pas assouplir le contrôle seulement pour reverdir les anciens tests. La docstring décrivant le fallback doit être alignée sur cette exigence.

**E12 — Priorité haute : rupture de la jointure native expéditions → lots.**

Le test `simulation/test_risk_lot_impact_registry.py:1047` échoue après un smoke test réel du moteur. Les identifiants d’expédition du CSV fournisseur sont des `SHIP-*`, tandis que les événements de lots correspondants portent des `SHP-*`. Le test exige la présence des mêmes identifiants, sans imposer leur préfixe : ce n’est pas une simple attente de format obsolète.

Cause identifiée dans `simulation/engine/run_first_simulation.py` : `_attach_shipment_trace_ids` crée les identifiants séquentiels dans le planning (`:365`). La première boucle remplace seulement la variable locale `shipment_id` par un identifiant dérivé de route/dates (`:13111`) et l’utilise dans les événements de lots. Une seconde boucle relit le planning d’origine (`:13272`) et exporte encore l’ancien identifiant dans `production_supplier_shipments_daily.csv` (`:13325`).

`lot_trace/risk_impact_registry.py:1605` exige l’égalité des identifiants lorsqu’ils sont présents ; son rapprochement historique ne compense pas deux identifiants différents. La divergence peut donc empêcher l’allocation des expéditions exposées aux lots sources et dégrader leur traçabilité aval. Les résultats de couverture du registre doivent être examinés avant d’exploiter cette chaîne comme preuve native.

Corriger la création et la propagation d’une identité unique à la source, en définissant son grain : expédition logistique consolidée ou contribution article/chunk. Ajouter un cas multi-articles partageant route et dates, car le nouvel identifiant est construit à ce niveau. Un simple changement de préfixe ne traite pas ce contrat.

**Analyse du pack**

Il contient sept rôles opérationnels, six skills, des prompts, une roadmap, des configurations et le package indépendant `etudecas_agentkit`. Aucun import de ce mini-kit n’a été trouvé dans le code Python d’Etudecas.

Son flux est : YAML → CSV → validation des données → KPI → trajectoires → validation des résultats → figures Matplotlib. Le registre de rôles décrit les responsabilités ; il ne lance pas d’agents. Les skills présents dans ce dossier sont des ressources à utiliser ou installer explicitement, pas la preuve qu’ils sont actifs dans toutes les sessions.

Les règles de fond sont bien choisies : moteur générique, données métier configurables, conservation des quantités, distinction lot/transport, traces d’enrichissement, artefacts compacts et délégation par périmètre. Les chemins explicites vers Etudecas présents dans les six skills existent. La roadmap devrait néanmoins distinguer ce qui est déjà réalisé — API, lot trace, contrats de run — de ce qui reste à consolider.

Dans le tableau suivant, les chemins `validation/`, `kpi/` et `data/` sont relatifs à `etudecas_codex_multiagent_pack/etudecas_agentkit/`.

| Référence | Constat reproduit | Conséquence et correction |
|---|---|---|
| P1 — `etudecas_agentkit/cli.py:29` | Un rapport `reject` est écrit, mais la CLI poursuit les figures et annonce `Case executed`. | Émettre un code de sortie non nul après sauvegarde du rapport ; ne pas annoncer une réussite. |
| P2 — `validation/result_checks.py:43` | Une colonne exigée mais absente est ignorée ; le résultat peut être `ok` avec contrôle `passed`. | Distinguer contrôles exécutés, non applicables et obligatoires manquants. |
| P3 — `configs/cases/supply_chain_bullwhip.yaml:45` | L’exemple supply chain réutilise les colonnes visuelles aircraft ; erreur `Missing visual column: quality`. | Fournir les visualisations et règles adaptées ; tester les trois exemples. |
| P4 — `kpi/aggregators.py:10` | Des poids `{a:2,b:-1}` produisent un score 2 pour `a=1,b=0`. | Vérifier finitude et non-négativité des poids si le score doit rester borné. |
| P5 — `kpi/normalizers.py:24` | Des paramètres inversés pour `maximize` sont acceptés et récompensent les valeurs basses. | Valider l’ordre des bornes et la position de la cible. |
| P6 — `data/validator.py:96` | Le type `integer` accepte 1,5. | Vérifier l’intégralité, pas seulement la conversion en nombre. |
| P7 — `cli.py:30` | Rapport et figures partagent des noms globaux entre cas. | Isoler les sorties par cas/run et ajouter la provenance. |
| P8 — `validation/visual_checks.py` | Le validateur vérifie essentiellement un fichier non vide ; un faux PNG passe le test. | Clarifier ce contrôle ou décoder réellement l’image. Il ne prouve pas la lisibilité du graphique. |

Les 11 tests existants passent malgré ces problèmes. Ils vérifient surtout les chemins nominaux. Les exemples `example_minimal.yaml` et `fal_aircraft.yaml` réussissent ; `supply_chain_bullwhip.yaml` échoue. Les trois exemples ont été vérifiés dans une copie temporaire.

Le README demande un `cd` dans le pack pour son installation, puis donne plus bas une commande de validation d’Etudecas relative à la racine du dépôt sans indiquer explicitement le retour. Préciser le répertoire de travail de chaque commande.

**Qualité scientifique et interprétation**

Plusieurs choix sont particulièrement bons : séparation exposition physique/effet contrefactuel dans `lot_trace/RISK_IMPACT_REGISTRY.md`, comparaisons appariées, conservation de la provenance, distinction entre commandes prédéfinies et feedback causal, limites explicites des analyses fréquentielles et des coefficients de recherche.

Le module logistique documente aussi correctement les limites des conversions : masse nette distincte de la masse chargée, absence d’inférence arbitraire des palettes et conservation d’un nombre de camions inconnu lorsque les dimensions nécessaires manquent. La politique de lots dispose de types dédiés, d’unités et de contrôles préalables. Ces briques sont de bons exemples de responsabilités à extraire du moteur monolithique sans perdre les règles physiques.

Ces distinctions doivent être préservées dans les livrables. Une généalogie de lots exposés ne démontre pas à elle seule une perte de service causée par l’incident. Des profils de stress choisis pour faire varier les KPI ne constituent pas automatiquement une distribution prédictive calibrée. Un signal cohérent ne prouve pas une marge de stabilité. L’audit n’a pas recalibré le modèle sur les observations métier ni vérifié tous les bilans quantitatifs historiques.

**Vérifications exécutées**

- Python 3.11.9 ; diagnostic `doctor` : tous les contrôles réussis.
- Environnement observé : NumPy 2.4.6, pandas 3.0.3, openpyxl 3.1.5, Matplotlib 3.11.0, pytest 9.1.1, PyYAML 6.0.3 et Playwright 1.61.0.
- Analyse AST des 590 fichiers Python d’Etudecas : aucune erreur de syntaxe.
- Graphe actif : aucun problème remonté par le validateur existant, avec les limites décrites plus haut.
- Suite unittest documentée : 243 tests, succès, 2 ignorés, environ 10 secondes.
- Pack : 11 tests pytest réussis en 10,17 secondes.
- Exemples du pack : deux réussites, un échec reproduit.
- Reproductions isolées des défauts des validateurs et conversions de requête.
- Suite complète `python -m pytest etudecas -q --disable-warnings --tb=short` : **2 113 réussites, 126 échecs, 7 ignorés, 7 erreurs**, plus 9 sous-tests réussis, en **1 715,44 secondes / 28 min 35 s** ; code de sortie 1.

La collecte pytest se répartit en 1 767 tests de prototypes, 365 de simulation, 101 de visualisation, 10 du pipeline, 5 d’analyse, 3 du graphe et 2 de configuration des lots. Cette répartition compte les cas paramétrés, pas uniquement les fonctions de test. Elle ne constitue pas une mesure de couverture des lignes de code.

Les 126 échecs se répartissent en **123 dans les prototypes, 1 dans la simulation et 2 dans le pipeline**. Les 7 erreurs de préparation de tests concernent les prototypes V8. Les traces montrent plusieurs familles : empreintes et signatures figées incompatibles, références à un checkout absent `C:\dev\lca-simu-pr40`, divergence de provenance du graphe dans l’audit de capacité, fonction de sélection manquante, contrat Monte Carlo et jointure des expéditions/lots. La cause LF/CRLF a été démontrée sur deux cas représentatifs, pas attribuée sans preuve à chacun des 133 échecs ou erreurs.

Les journaux de tests sont dans le répertoire temporaire Windows, sous `etudecas_audit_unittest_20260916.log` et `etudecas_audit_pytest_20260916.log`. Aucun changement de code applicatif n’a été réalisé. Les tests peuvent créer des caches et sorties ignorées ; le test de bout en bout du pack actualise notamment son rapport JSON et une figure PNG.

**Ordre de travail recommandé**

1. Corriger la rupture de jointure expéditions/lots et l’appel de sélection inexistant ; fiabiliser la preuve de validation avec une commande pytest canonique, une politique LF/CRLF des empreintes et des tests négatifs des validateurs.
2. Durcir le contrat HTTP si l’API interactive est utilisée : retirer les paramètres réservés au code interne et contrôler les chemins.
3. Corriger les exemples et les règles de validation du mini-kit, puis actualiser les consignes du pack.
4. Rendre la configuration métier explicite par run et fixer les contrats numériques.
5. Consolider les manifestes et la portabilité des artefacts, puis traiter les fichiers lourds suivis par Git par une opération séparée et revue.
6. Extraire progressivement les responsabilités du moteur et du rendu, avec tests de référence et clarification de la variante pilote.
7. Classer les campagnes SCAN en composants réutilisables, protocoles de recherche et outils de livraison ; aligner la documentation opérationnelle sur les commandes actuelles.

Le premier livrable utile serait une correction ciblée de la jointure expéditions/lots, des validations et de la commande de tests : elle améliore immédiatement la confiance dans les résultats et dans les évolutions suivantes.
