**Audit du pack et architecture multi-agent Codex proposée — 20 septembre 2026**

**Conclusion opérationnelle**

Le pack existant contient une bonne doctrine métier et six skills réutilisables, mais ne configure pas encore un système multi-agent chargeable automatiquement depuis la racine du dépôt. Son mini-kit Python est un pipeline de calcul et de graphiques, pas un orchestrateur Codex. La cible recommandée est une intégration locale au dépôt : instructions applicables, skills découvrables, agents spécialisés, toolbox déterministe construite autour des outils Etudecas existants et preuve de validation indépendante. Un serveur MCP ou une nouvelle application utilisant une API LLM n'est pas un prérequis.

Ce rapport est une proposition issue d'un audit ; il n'installe aucun agent, SDK, plugin ou service. Il ne remplace pas le rapport d'audit de la carte conduit en parallèle.

**Périmètre, versions et preuves**

Les fichiers ont été relus dans leur état du 20 septembre. Les constats du 16 septembre ne peuvent pas être reconduits tels quels : plusieurs défauts du mini-kit ont été corrigés depuis. Lecture de `AGENTS.md`, du rôle orchestrateur, du README, des configurations, du code et des tests du pack ; inspection des emplacements de découverte Codex ; lecture ciblée de `etudecas/testing` ; recherche et ouverture de documentation officielle OpenAI.

Versions observées : Codex CLI `0.154.0-alpha.6.1`, livré par l'extension VS Code `openai.chatgpt-26.908.31748-win32-x64` ; Python 3.11.9 ; pytest 9.1.1 ; pandas 3.0.3 ; numpy 2.4.6 ; PyYAML 6.0.3 ; Matplotlib 3.11.0 ; Pillow 12.3.0 ; Playwright 1.61.0. Les distributions Python `openai` et `openai-agents` ne sont pas installées dans cet interpréteur. Cette observation ne décrit pas les autres environnements virtuels éventuels.

Preuves dans `etudecas/artifacts/testing/full_audit_20260920/pack/` :

- `environment.json` : versions et code de sortie pytest ;
- `pytest_pack.log` : sortie complète de la suite propre ;
- `isolated_pack/` : copie des sources/configurations/tests et sorties de reproduction, sans réutilisation des anciens outputs.

La copie est volontairement hors du pack applicatif. Elle contient des tests Python : exclure `etudecas/artifacts` de la découverte globale, pour ne pas collecter les preuves comme des tests de production. La tentative de nettoyage de cette copie a été refusée par le contrôle automatique de l'outil avec le seul motif « blocked by policy » ; aucun nettoyage ni contournement n'a été effectué.

**État réel du pack**

| Élément | Observation | Implication |
|---|---|---|
| `AGENTS.md:14` et `docs/agents/orchestrateur.md:22` | Routage métier et contrat de délégation avec périmètres disjoints | Bonne base à conserver |
| `docs/agents/*.md` | Sept rôles documentaires | Ils ne créent pas de processus ou de sous-agents |
| `etudecas_agentkit/agents/roles.py:3` | Dictionnaire de descriptions | Aucune délégation, reprise, attente ou agrégation exécutée |
| `etudecas_agentkit/cli.py:20` | CSV → validations → KPI → trajectoires → figures | Démonstrateur de contrats, indépendant de la simulation réelle |
| `skills/*/SKILL.md` | Six workflows métier | Ressources présentes, mais découverte locale à intégrer |
| `skills/*/agents/openai.yaml` | Métadonnées d'interface et prompt par défaut | Ce ne sont pas des définitions de sous-agents TOML |
| `.agents/skills`, `.codex/agents`, `.codex/config.toml` | Absents à la racine lors de l'inspection initiale | Pas de configuration projet native observée |
| `AGENTS.md` à la racine et `etudecas/AGENTS.md` | Absents lors de l'inspection initiale | Le guide du dossier frère n'est pas une consigne racine automatiquement héritée |
| `README.md:58`, `AGENTS.md:70` | Minimum de validation toujours exprimé avec unittest | À remplacer ou compléter par une collecte pytest explicite et des preuves navigateur |

Les agents déjà utilisés dans cette session sont fournis par l'environnement de collaboration. Leur existence ne démontre pas que le pack installe ces agents sur une autre machine. Aucun fichier d'authentification ou secret n'a été consulté. Aucun contenu complet de configuration utilisateur n'a été exporté.

**Résultats du mini-kit et défauts résiduels**

La suite a été exécutée dans une copie fraîche avec `python -B -m pytest -p no:cacheprovider -q --tb=short` : **26 réussites, 1 échec, 20,15 secondes**. Les trois exemples sont désormais couverts et réussissent, dont supply chain avec ses propres specs et règles.

Les corrections visibles et vérifiées par les tests ajoutés comprennent : arrêt sur résultat rejeté (`cli.py:40`), répertoires par cas/UUID (`cli.py:23`), validation des figures, rejet des colonnes de preuve absentes, poids invalides, normalisation inversée et quantités entières non physiques. Le validateur visuel décode maintenant les PNG via Pillow (`validation/visual_checks.py:23`). Il ne faut donc plus présenter ces défauts historiques comme actuels.

Le défaut reproduit est le test `tests/test_end_to_end.py:10` : il cherche encore `outputs/reports/validation_report.json` et `outputs/figures/trajectory_3d.png`. La CLI écrit maintenant dans `outputs/<case>/<UUID>/`. Sur un checkout contenant d'anciens outputs, ces assertions peuvent réussir grâce à des fichiers périmés. Sur une copie propre, elles échouent. Corriger ce test pour utiliser une fixture isolée et vérifier le run effectivement créé ; ne pas rétablir des sorties globales pour satisfaire l'ancien test.

Autres limites ciblées :

- Le champ `output_dir` est imprimé mais `run()` ne renvoie pas un objet de résultat ; le consommateur doit retrouver le run autrement. Un résultat structuré simplifierait les tests.
- Les UUID évitent les collisions, mais aucun manifeste complet avec hashes des inputs, configuration, version d'implémentation et statut global n'est produit par ce mini-kit.
- Le README ne revient pas explicitement à la racine après son `cd` avant la commande relative `unittest`.
- La dépendance directe à `PIL` n'est déclarée explicitement qu'en extra dev dans `pyproject.toml:23`, alors que la CLI normale appelle le validateur. Matplotlib apporte actuellement Pillow transitivement ; déclarer une dépendance directement utilisée rend le contrat plus clair.
- `kpi/aggregators.py:23` conserve une moyenne simple pandas qui ignore les NaN par défaut, contrairement aux contrôles stricts de la moyenne pondérée. Ce n'est pas un échec démontré des trois exemples, mais la convention doit être explicitée avant de présenter ce code comme référence générale.

**Ce que prévoit réellement Codex actuel**

Les pages historiques `developers.openai.com/codex/...` redirigent désormais vers `learn.chatgpt.com`. Les URLs ci-dessous ont été ouvertes ; les liens non localisés essayés sous `developers.openai.com/docs/...` retournaient 404 et ne servent pas de preuve.

Les agents personnalisés de projet sont des TOML dans `.codex/agents/` avec `name`, `description`, `developer_instructions`. La configuration commune utilise `[agents]`, notamment `enabled` et `max_concurrent_threads_per_session`. Ce dernier compte les agents enfants, pas le parent. La délégation locale suit une demande explicite ou une instruction applicable. Les champs modèle et raisonnement peuvent rester omis pour hériter du parent. [Documentation officielle des sous-agents](https://learn.chatgpt.com/docs/agent-configuration/subagents).

La découverte des skills de dépôt utilise `.agents/skills` entre le répertoire courant et la racine. Le dossier arbitraire `etudecas_codex_multiagent_pack/skills` n'est donc pas, à lui seul, un mécanisme de découverte. Les liens symboliques sont pris en charge, mais un emplacement canonique versionné évite les particularités Windows et les copies divergentes. [Créer des skills](https://learn.chatgpt.com/docs/build-skills).

La chaîne `AGENTS.md` est construite depuis la racine vers le répertoire de travail. Un fichier dans le pack frère ne gouverne pas automatiquement `etudecas`. Placer une consigne courte à la racine qui oriente vers les règles Etudecas est plus fiable que demander à chaque session de redécouvrir le pack. [Instructions de projet](https://learn.chatgpt.com/docs/agent-configuration/agents-md).

`codex exec` permet JSONL, schéma de réponse et fichier de résultat. Ces options sont également confirmées par l'aide de la CLI installée. Elles offrent une base pour une automatisation observable ; une réponse structurée ne constitue pas une validation de son contenu. [Mode non interactif](https://learn.chatgpt.com/docs/non-interactive-mode).

Pour une orchestration externe ultérieure, la documentation décrit le SDK Python `openai-codex`, pilotant l'app-server local, et le SDK TypeScript `@openai/codex-sdk`. Elle indique également la suppression de `codex mcp-server`. Ne pas reprendre un ancien tutoriel « Codex comme serveur MCP » sans migration. Le binaire local ne propose effectivement pas cette commande dans son aide. [Codex SDK](https://learn.chatgpt.com/docs/codex-sdk).

MCP reste utile pour exposer une toolbox à plusieurs clients ; les transports STDIO et HTTP sont documentés. La configuration projet peut déclarer un serveur local, ses outils autorisés et ses délais. Cela ne nécessite pas d'ajouter immédiatement un service réseau au projet. [MCP dans Codex](https://learn.chatgpt.com/docs/extend/mcp?surface=cli).

**Architecture concrète recommandée — proposition, pas état installé**

Conserver quatre couches séparées : consignes, workflows, agents, outils. L'orchestrateur natif décide et délègue ; les scripts déterministes produisent les preuves ; le validateur indépendant conclut sur ces preuves. Le mini-kit reste pédagogique.

Arborescence cible :

```text
AGENTS.md                              # routage bref vers Etudecas
.codex/config.toml                     # paramètres multi-agent projet
.codex/agents/etudecas_explorer.toml
.codex/agents/etudecas_simulation.toml
.codex/agents/etudecas_map.toml
.codex/agents/etudecas_validator.toml
.agents/skills/etudecas-*/SKILL.md       # six skills existants adaptés
.agents/skills/etudecas-orchestrate/SKILL.md
etudecas/toolbox/                       # wrappers déterministes à créer
etudecas/toolbox/contracts/             # schémas tâche/résultat/preuve
etudecas/toolbox/tests/                 # tests des contrats et erreurs
etudecas/artifacts/testing/<run_id>/    # preuves exclues de la collecte
```

Exemple minimal de configuration projet à vérifier avec la version installée :

```toml
[agents]
enabled = true
max_concurrent_threads_per_session = 3
```

Trois enfants plus le parent correspondent à la capacité de collaboration exposée dans cette session. Le runtime reste l'autorité si ses limites effectives sont inférieures. Ne pas inventer une disponibilité de modèle ou de quota. Ne pas inscrire de modèle plus récent uniquement parce qu'un exemple de documentation le cite.

Exemple de profil d'exploration proposé :

```toml
name = "etudecas_explorer"
description = "Analyse les chemins du code Etudecas et retourne des preuves localisees."
sandbox_mode = "read-only"
developer_instructions = """
Reste en lecture seule. Identifie les entrees, contrats et consommateurs.
Ne confonds pas artefact historique et sortie courante.
Retourne fichiers, lignes, hypothese, preuve et limite pour chaque constat.
Les corrections et executions qui ecrivent sont deleguees au parent.
"""
```

Ce profil n'est pas une sandbox par chemin fin. Pour écrire des captures ou exécuter des tests, un agent doit disposer d'un espace autorisé ; utiliser un worktree ou une copie de test et des destinations dédiées. Une instruction « n'écris que ce dossier » est une convention, pas une isolation système. Les permissions de cette session sont actuellement larges : l'audit ne prétend pas avoir démontré un confinement des agents.

| Rôle | Travail | Écriture autorisée proposée | Preuve attendue |
|---|---|---|---|
| Orchestrateur parent | Découpage, dépendances, budget, synthèse et intégration | Manifeste de tâche, agrégation ; intégration séquentielle | Graphe de tâches, statuts et décisions |
| Explorer | Repérage et risques transversaux | Aucune dans le code | Références vérifiables et périmètre |
| Simulation | Contrats, calculs, MRP, stocks, lots | Modules assignés, worktree distinct si modifications | Test métier et invariants |
| Map | Payload, HTML/JS, interactions | Modules carte assignés | Reproduction navigateur, console, réseau, captures |
| Validator | Contre-expertise sur artefacts gelés | Dossier de preuves uniquement | Calcul indépendant, verdict argumenté |

Ne pas lancer tous les rôles à chaque tâche : carte + invariants indépendants peuvent progresser ensemble ; intégration du payload et test du HTML qui le consomme restent ordonnés. Une modification d'un même template ou d'un manifeste commun doit avoir un propriétaire unique.

**Toolbox reproductible à construire sur l'existant**

Le projet possède déjà une vraie base d'outillage : `etudecas/testing/independent_review.py:1` annonce et implémente des contrôles arithmétiques sans importer le moteur ; `qualification.py:29` agrège invariants, hashes et éventuellement preuve navigateur ; `map_browser.py:125` expose une CLI HTML ; `report.py:41` transforme du JUnit. Réutiliser ces commandes, sans présenter une simple enveloppe comme une nouvelle validation scientifique.

| Outil proposé | Implémentation à appeler/adapter | Contrat et refus |
|---|---|---|
| `inventory` | Inventaire ciblé et `testing.inventory` pour comparaison signée | Limites de taille ; pas de lecture massive de CSV sans besoin |
| `tests` | `python -B -m pytest` avec listes explicites | JUnit + code sortie ; aucune collecte dans artifacts |
| `run_invariants` | `python -B -m etudecas.testing.independent_review --run ... --output ...` | Inputs existants ; preuve manquante = échec |
| `map_browser` | `python -B -m etudecas.testing.map_browser --html ... --output-dir ...` | Captures et erreurs réelles ; timeout explicite |
| `qualify` | `python -B -m etudecas.testing.qualification --run ... --html ... --output ...` | Refus sur invariant ou navigateur invalide ; distinguer display_verified |
| `simulation_smoke` | API `SimulationRequest` existante, cas compact | Horizon/scénario/seed explicites ; pas de Monte Carlo lourd implicite |
| `run_compare` | Comparaison de sorties compactes et de provenance | Comparaison refusée si populations/horizons/units incompatibles |

Le CLI wrapper doit accepter des arguments typés, construire une liste d'arguments subprocess sans shell, imposer le répertoire racine, valider les chemins résolus, gérer timeout et code retour, produire un JSON compact. Aucun `eval`, commande shell arbitraire ou accès réseau supplémentaire ne doit être nécessaire pour ces opérations. Les durées par défaut sont des paramètres locaux à mesurer, pas des valeurs scientifiques.

Contrat minimal de tâche proposé : `task_id`, `objective`, `owner`, `read_paths`, `write_paths`, `depends_on`, `acceptance_checks`, `timeout_seconds`, `artifact_directory`. Le résultat : `status` parmi `passed/failed/blocked/skipped`, `commands`, `exit_codes`, `evidence_paths`, `input_hashes`, `findings`, `limitations`, `changed_paths`. Une tâche en échec n'est jamais transformée en réussite par le résumé LLM.

Tests de la toolbox à prévoir : succès nominal, dépendance absente, timeout, JSON invalide, test échoué, chemin hors périmètre, rapport périmé, preuve manquante, collisions de destinations. Un mode `--dry-run` affiche le graphe et les commandes sans démarrer d'agent ni de simulation.

**Validation indépendante et carte HTML**

La présence d'un agent reviewer ne suffit pas à rendre le verdict indépendant. Geler hashes de l'HTML, du payload et des CSV avant la revue ; transmettre les artefacts et contrats au reviewer ; lui faire recalculer les invariants avec un chemin distinct de celui de génération. Le parent compare ensuite les constats de l'auteur, du test navigateur et du validateur.

Pour la carte, la toolbox doit conserver : mode d'ouverture testé (`file://` et/ou serveur local), navigateur/version, taille viewport, interactions réalisées, erreurs console, requêtes réseau, captures avant/après et verdict par onglet. Tester réellement sélection de fournisseur/lot, parcours amont/aval, changement de scénario et données absentes ; un screenshot initial ou un fichier non vide ne prouve pas les interactions. Les listes exactes et seuils doivent être issus du rapport carte et du produit courant, sans inventer une couverture complète.

Un test hors ligne doit bloquer le réseau et vérifier les panneaux attendus, pas seulement ouvrir une carte déjà servie avec des caches chauds. Les hashes lient les preuves au livrable exact ; toute reconstruction de l'HTML invalide la qualification précédente.

**Séquence d'intégration utile**

1. Corriger le test pack obsolète et arrêter de dépendre d'anciens outputs. Établir la baseline complète de l'audit courant et classer chaque échec ; pas de validation globale sur la seule suite rapide.
2. Installer dans le dépôt le routage racine et les skills de référence. Définir un emplacement canonique ; si des copies sont conservées dans le pack, vérifier leur synchronisation automatiquement. Utiliser le skill de création de skills lors de cette réalisation.
3. Ajouter les quatre profils d'agents ci-dessus et un workflow orchestration. Vérifier syntaxe TOML, présence des champs et chemins, puis effectuer un test de découverte sur une tâche courte déjà autorisée ; ne pas déclarer « installé » avant cette vérification.
4. Implémenter la toolbox sans LLM autour des commandes existantes. Tests de contrats, erreurs et dry-run entièrement locaux. Cette étape apporte une valeur immédiate aux humains et à la CI.
5. Relier les agents à ces commandes. Lors d'une exécution LLM explicitement lancée, capturer les événements et résultat structurés, stopper sur erreur/timeout et intégrer les changements séquentiellement. Préférer d'abord l'orchestration native Codex.
6. Ajouter une orchestration externe Python seulement si besoin d'ordonnancement durable, reprise ou CI multi-session. Le SDK `openai-codex` est une option documentée ; son ajout n'est pas requis pour les premiers agents. Tester la version choisie et la compatibilité du runtime avant verrouillage.
7. Envisager un MCP local STDIO ou un plugin seulement pour distribuer l'outillage au-delà du dépôt. Garder la CLI sous-jacente testable directement. Pas de plugin tiers requis pour auditer des fichiers locaux et ouvrir une carte déjà accessible.

**Critères d'acceptation de l'intégration**

- Depuis la racine, Codex découvre les bonnes consignes, skills et profils sans recherche manuelle dans le pack.
- Une tâche indépendante est effectivement déléguée ; les résultats des enfants sont associés aux tâches, et une erreur enfant interdit un verdict global de réussite.
- Deux tâches concurrentes produisent des preuves dans des répertoires disjoints ; aucune écriture croisée dans les sources attribuées n'est constatée.
- Un test volontairement échoué et une preuve navigateur absente empêchent la qualification.
- La toolbox fonctionne sans credential LLM ; la partie LLM demeure une couche explicitement démarrée, observable et interrompable.
- Le run de validation ne s'appuie pas sur des artefacts périmés, et ne ré-exécute pas les copies de tests stockées parmi les preuves.

**Limites de ce travail**

Ni installation, ni modification de configuration globale, ni session LLM payante supplémentaire n'ont été lancées. Les commandes `codex --version`, `--help`, `exec --help` et `doctor --help` servent uniquement à inspecter la CLI ; `doctor` lui-même n'a pas été exécuté. Les exemples TOML sont des propositions fondées sur la documentation actuelle, pas un test d'activation dans une nouvelle session. Les capacités des comptes, politiques d'administration et quotas n'ont pas été vérifiés. Les mécanismes d'indépendance décrits doivent encore être testés sur l'intégration réellement construite.

Fichiers applicatifs modifiés : aucun. Livrables de cette sous-tâche : ce rapport et les preuves compactes du pack. Prochaine étape : livrer la toolbox et la découverte native dans un changement borné, avec la baseline de l'audit courant comme condition de qualification.

**Comparaison des outils et skills actuels — complément vérifié le 20 septembre**

Cette comparaison distingue capacités publiées et outils effectivement utilisables ici. Playwright Python 1.61.0 est installé ; `node` et `npm` ne sont pas trouvés dans le PATH de ce shell lors de la vérification. Cela ne prouve pas leur absence de toute la machine, mais interdit de présenter les commandes `npx` des exemples comme déjà opérationnelles. Aucun téléchargement ou serveur supplémentaire n'a été lancé.

| Référence actuelle | Apport documenté | Décision pour Etudecas |
|---|---|---|
| **Playwright Python existant** | API sync/async, Chromium/Firefox/WebKit et intégration pytest pour tests navigateur. [Documentation Microsoft](https://playwright.dev/python/docs/intro) | **Réutiliser en priorité** : conserver les scripts `etudecas/testing/*browser*.py` et leurs preuves. Ils s'intègrent à l'écosystème Python du projet et aux vérifications déterministes. |
| **Microsoft Playwright MCP** | Interaction agent/navigateur via snapshots d'accessibilité structurés ; MCP adapté à une exploration itérative avec état de session. [Dépôt officiel](https://github.com/microsoft/playwright-mcp) | **Optionnel**, si l'exploration manuelle par l'agent exige une session interactive durable. Il n'améliore pas automatiquement les assertions métier. Prévoir runtime Node et version verrouillée avant intégration. |
| **Microsoft Playwright CLI + skills** | Interface shell avec sessions et skill fourni ; Microsoft la présente comme adaptée aux coding agents et à un contexte plus compact. [Dépôt officiel](https://github.com/microsoft/playwright-cli) | **Optionnel** pour une exploration générique réutilisable. L'intérêt est inférieur à celui des scripts Python existants pour les parcours métier déjà écrits ; ne pas maintenir trois couches équivalentes sans besoin. |
| **Chrome DevTools MCP** | Traces de performance, requêtes réseau, console, captures et automation Chrome. Support officiel de Chrome et Chrome for Testing. [Dépôt officiel](https://github.com/ChromeDevTools/chrome-devtools-mcp) | **Optionnel pour diagnostiquer la performance**, notamment parsing, chargement et rendu d'un HTML lourd. Ne pas supposer le même support garanti pour Edge. Employer un profil de test dédié. |
| **OpenAI Docs skill + Docs MCP** | Recherche et lecture documentaires en lecture seule ; le serveur public ne réalise pas d'appels API au nom de l'utilisateur. [Documentation officielle](https://developers.openai.com/learn/docs-mcp) | **Réutiliser le skill local déjà disponible** ; connecter le MCP uniquement si l'accès documentaire direct améliore les maintenances futures. Il aide à vérifier les contrats Codex, pas les règles supply chain. |
| **Skills système `skill-creator` / `skill-installer`** | Disponibles dans le catalogue de cette session pour authoring et installation ; la découverte projet repose sur les emplacements documentés. [Skills Codex](https://learn.chatgpt.com/docs/build-skills) | **Réutiliser lors de la réalisation** ; aucune raison de créer un nouvel installateur générique. Examiner les skills externes avant de les ajouter ; ne pas confondre disponibilité système et installation des six skills Etudecas. |
| **Codex natif + SDK Python/TypeScript** | Agents locaux et contrôle programmatique des sessions ; SDK pour intégration externe. [Codex SDK](https://learn.chatgpt.com/docs/codex-sdk) | **Natif en priorité ; SDK optionnel** pour reprise durable/CI lorsqu'elle est réellement nécessaire. Conserver la toolbox utilisable indépendamment du SDK et des credentials LLM. |
| **Ancien `codex mcp-server`** | Retrait signalé dans la documentation SDK et commande absente de l'aide locale. [Source officielle](https://learn.chatgpt.com/docs/codex-sdk) | **Écarter cette recette** ; si une intégration cliente devient nécessaire, utiliser l'app-server ou le SDK pris en charge. |

Pour Chrome DevTools MCP, les collectes de statistiques d'usage et les requêtes CrUX sont activées par défaut selon le README. Les options `--no-usage-statistics` et `--no-performance-crux` permettent de les désactiver. Ce détail compte pour un audit hors ligne de données industrielles ; il ne concerne pas les scripts Playwright Python déjà présents. [Paramètres documentés par le projet](https://github.com/ChromeDevTools/chrome-devtools-mcp).

Le Docs MCP public utilise `https://developers.openai.com/mcp`. Le simple fait d'avoir lu sa documentation n'établit pas qu'il est connecté dans cette session. Les six skills métier doivent rester les détenteurs des invariants supply chain ; les outils externes apportent interaction, diagnostic ou documentation, sans remplacer ces contrats. [Portée du Docs MCP](https://developers.openai.com/learn/docs-mcp).

La décision de ne pas ajouter de framework d'orchestration tiers à ce stade est architecturale : Codex sait déjà déléguer, le dépôt contient déjà les oracles et le besoin immédiat est de les rendre reproductibles. Ce n'est pas un jugement de capacité sur les autres frameworks, qui n'ont pas fait l'objet d'un benchmark expérimental ici. La matrice compare des capacités vérifiées dans leurs sources primaires ; elle ne prétend pas mesurer un gain de vitesse ou un taux de réussite.
