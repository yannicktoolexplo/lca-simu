# Etudecas : agents natifs et toolbox de preuves

L'orchestration utilise les sous-agents natifs de Codex. La toolbox Python exécute des contrôles déterministes existants ; elle n'appelle aucun modèle et ne lance ni serveur MCP ni SDK externe. La démonstration Python `etudecas_agentkit` a été retirée ; ses contrats génériques sont conservés dans `etudecas/toolbox/validation_contracts.py`. Aucune installation editable du pack n'est nécessaire.

## Installation locale et état vérifiable

Le déploiement révisable est dans `etudecas_codex_multiagent_pack/native/` :
`AGENTS.md`, `.codex/config.toml`, quatre profils, cinq skills et la référence
`etudecas-supply-diagnose/references/tickets.md`. Les versions de travail sont
celles de la racine ; préparer le staging depuis celles-ci et examiner le diff
avant installation. Les liens des skills ciblent leur emplacement final dans le
dépôt, pas un pack autonome. Le déploiement initial de neuf fichiers du
20 septembre 2026 est historique. Sur un autre poste, fusionner les paramètres
existants ; ne pas écraser la configuration utilisateur. Si les cibles sont
protégées, préparer le staging puis utiliser le mécanisme d'autorisation du
runtime ou l'intégrateur autorisé, sans contourner cette protection.

```powershell
# Validation structurelle du déploiement préparé, sans prétendre qu'il est installé
python -m etudecas.toolbox doctor --native-root etudecas_codex_multiagent_pack/native
# Après copie : contrôle de la racine réellement découvrable
python -m etudecas.toolbox doctor
```

Chaque commande affiche un objet JSON contenant `status`, `manifest` et `error`. Le manifeste référence `result.json`, où `installed_at_repository_root` distingue staging et racine. Un doctor staging réussi ne satisfait pas un gate exigeant doctor. Ce contrôle prouve présence/syntaxe/dépendances, pas encore le chargement des rôles par une nouvelle session, l'authentification Codex ou le lancement du navigateur. Vérifier la découverte dans la prochaine session Codex sur ce dépôt, puis déléguer une tâche bornée réellement utile ; ne pas lancer un second appel LLM uniquement pour produire un badge d'installation.

La configuration limite les enfants concurrents à trois, le parent étant exclu. Les quatre rôles disponibles ne doivent donc pas nécessairement tourner simultanément. Le modèle et l'effort sont hérités du parent. Les politiques réelles du runtime restent prioritaires.

## Ce que fournit le harnais

| Niveau | Fonction | Ce que cela ne démontre pas |
|---|---|---|
| Codex natif | Découverte des instructions/profils/skills et outils de délégation exposés par la session | Un fichier disque ne prouve pas son chargement ni une sandbox par rôle. |
| Consignes déclaratives | `AGENTS.md`, rôles, budgets et périmètres | Pas de verrou de fichier, quota automatique ou preuve scientifique. |
| Procédures spécialisées | Cinq skills et guides métier, chargés selon la tâche | Pas d'automate de routage, tickets ou causalité. |
| Exécutables déterministes | Toolbox, contrats, tests exacts, calculs CSV, navigateur, docs et gate | Leurs preuves couvrent seulement les contrôles exécutés et compatibles. |

Pour auditer une session, constater les profils et skills exposés, l'instruction
reçue par un enfant et un retour utile. Distinguer catalogue disponible et skill
réellement lu. Ne pas tester les permissions par une écriture interdite. Les
changements disque n'altèrent pas rétroactivement les instructions déjà chargées.
Le doctor actuel ne contrôle structurellement que les quatre profils et les trois
skills historiques (orchestration, qualification, carte), pas les deux skills
supply chain, leurs liens, l'héritage du modèle ni la limite exacte de trois.
Compléter par lecture TOML, validation des cinq métadonnées et liens à la racine.

Le parent choisit la première procédure utile selon le défaut et les informations
manquantes. Si le périmètre ou la cause est incertain, commencer par exploration/
diagnostic ; si une information décide entre routes, expliciter l'incertitude.
Le choix d'une route ne vaut ni autorisation d'action ni validation d'un résultat.
Une nouvelle couche de routage exige un gain sur des cas représentatifs face au
natif et à des règles simples, avec erreurs, abstentions, temps et coût mesurables.
Aucun score de routage ne remplace un oracle indépendant ou un contrôle déterministe.

## Contrat d'une délégation

Le parent attribue objectif et réussite observable, scénario/données/versions,
fichiers autorisés/interdits, livrable et preuves attendues. Il précise les budgets
calcul (nombre/taille des essais), temps, mémoire et stockage, et les conditions
d'arrêt ; les budgets cumulés des enfants doivent tenir sur la machine. Si le
coût est inconnu, mesurer un cas réduit avant d'élargir. Une alerte de sécurité
arrête les exécutions concernées ; budget atteint ou donnée indispensable absente
impose un retour borné au parent, sans relance automatiquement plus coûteuse.
Les écrivains n'ont jamais le même fichier en propriété simultanée. Retourner
`complete`, `refused` ou `incomplete`, changements réels, preuves, contrôles et
limites. Une narration sans preuve ne vaut pas validation.

`TaskSpec` n'a pas de champ budget : porter critère, bornes et arrêt dans
`objective`, ou dans le suivi existant référencé par `inputs`. Ne pas ajouter de
champ JSON. Ces budgets sont déclaratifs ; `--timeout` borne seulement chaque
sous-processus, pas la durée totale de mission.

Les objets JSON suivants sont validés strictement par les dataclasses `TaskSpec` et `AgentResult` de `etudecas.toolbox.contracts` : champs inconnus ou manquants refusés, chaînes non vides, listes typées, chemins internes au dépôt et états contrôlés. Exemple de tâche à écrire dans un fichier de preuves `task.json` :

```json
{
  "task_id": "verification-registre-01",
  "role": "etudecas_validator",
  "objective": "Contre-verifier les invariants du nominal conserve",
  "inputs": ["etudecas/simulation/result/_reruns/corrected_map_20260918"],
  "writable": ["etudecas/artifacts/testing"],
  "forbidden": ["etudecas/simulation/engine", "etudecas/visualization"],
  "required_evidence": ["tests", "qualify"]
}
```

Le validateur produit les preuves avec `--task-id verification-registre-01 --owner etudecas_validator`, options disponibles sur toutes les commandes, puis remet `agent-result.json` :

```json
{
  "task_id": "verification-registre-01",
  "role": "etudecas_validator",
  "status": "complete",
  "changed_files": [],
  "manifests": ["CHEMIN_MANIFESTE_TESTS", "CHEMIN_MANIFESTE_QUALIFICATION"],
  "summary": "Controles executes ; voir les manifestes exacts",
  "limitations": ["La calibration industrielle n'est pas certifiee"]
}
```

Remplacer les chemins d'exemple par les preuves réelles. Exécuter `python -m etudecas.toolbox handoff --task-spec CHEMIN_TASK_JSON --agent-result CHEMIN_RESULT_JSON`. La commande vérifie identité tâche/rôle, état `complete`, fichiers modifiés déclarés dans le périmètre, catégories requises, rattachement des manifestes au même identifiant/profil et empreintes actuelles. Un retour `refused` ou `incomplete` reste conservable mais ne passe pas handoff. L'identité est déclarative, pas une authentification de l'agent ; `changed_files` doit être confronté au diff réel par l'intégrateur. Handoff ne détecte pas un changement que l'agent aurait omis de déclarer.

| Profil | Responsabilité | Limite |
|---|---|---|
| `etudecas_explorer` | Contrats, chemins réels, dépendances et preuves localisées | Lecture seule |
| `etudecas_simulation` | Moteur/données/tests attribués | Pas d'écriture concurrente dans la carte |
| `etudecas_map` | Payloads, HTML, interactions et contrôles navigateur | Pas d'écriture concurrente dans le moteur |
| `etudecas_validator` | Oracle indépendant, données gelées, contre-exemples | Pas de correction du code évalué ; preuves seulement |

Les restrictions par fichier et la lecture seule de l'explorateur sont des consignes de rôle. Les enfants héritent des permissions effectives du parent ; un profil ne crée pas une sandbox distincte. Choisir un rôle dont les instructions autorisent la mission. Les worktrees séparent les modifications, sans remplacer les contrôles d'accès ; intégrer séquentiellement.

Les skills `etudecas-orchestrate`, `etudecas-qualify`, `etudecas-map-review` routent vers les contrôles concrets. Les skills `etudecas-supply-diagnose` et `etudecas-supply-calibrate` guident respectivement l'explication d'un écart supply chain et la comparaison de règles ou paramètres. La délégation doit être utile et indépendante ; une modification simple ne nécessite pas quatre agents.

Les anciens rôles, prompts et skills documentaires du pack sont dans les
[archives](../archive/README.md). Le routage courant utilise les profils de
`.codex/agents/` et les skills de `.agents/skills/` installés à la racine.

## Tickets d'une investigation supply chain

Le [schéma canonique du registre](../../.agents/skills/etudecas-supply-diagnose/references/tickets.md) définit les informations à conserver. Le parent tient un seul registre par investigation, dans son dossier de preuves existant sous `etudecas/artifacts/testing`, et le relie au suivi courant. Il en est le seul éditeur ; les agents envoient leurs deltas par message. Ne pas ouvrir un fichier Markdown par ticket, ni recopier les journaux ou les gros tableaux dans le registre. Ce suivi est une méthode de travail sur les contrats existants ; la toolbox n'implémente pas un automate de tickets.

Un ticket porte une question observable et un écart quantifié sur un périmètre article/site/produits partagés, une période et des unités explicites. Prioriser selon les impacts distincts sur le service, les stocks et les coûts, en séparant coût opérationnel et approvisionnement externe. Une donnée absente reste inconnue. Un résultat simulé, une reconstruction et une observation industrielle ne portent pas le même niveau de preuve.

Le parent choisit les investigations qui départagent les explications concurrentes : d'abord vérifier que le périmètre et les conventions permettent une comparaison, puis suivre les bilans et dates de disponibilité jusqu'aux effets aval. Il peut distribuer en parallèle des questions indépendantes, avec leurs dépendances et fichiers disjoints, puis intégrer les résultats avant une expérience commune. L'agent reçoit le ticket, les entrées et le scénario exacts, le mécanisme à départager, ce qui serait attendu s'il est vrai ou faux et la preuve attendue. La profondeur suit les ambiguïtés encore ouvertes ; elle ne repose ni sur une checklist exhaustive ni sur un nombre arbitraire de « pourquoi ».

Les retours restent bornés : identifiant, conclusion et niveau de preuve, chiffres décisifs avec unités/périmètre/période, sources ou manifestes exacts, explications soutenues ou contredites, limites et prochaine action. Le parent met à jour le registre et conserve les apprentissages négatifs. Si plusieurs essais sont identiques, vérifier d'abord que le paramètre atteint le moteur et que le mécanisme est sollicité, puis examiner les stocks tampons avant d'ajouter une variante.

Les statuts du registre sont `à examiner`, `en cours`, `à valider`, `résolu`, `données insuffisantes` et `réfuté`, selon le schéma canonique. `complete`, `refused` ou `incomplete` décrit seulement la tâche d'un agent. Une hypothèse plausible ne devient pas une cause démontrée par l'achèvement d'une tâche, une meilleure courbe ou un gate réussi. Le parent ne clôture à `résolu` qu'avec une réponse vérifiée à la question, sur le périmètre annoncé et avec ses limites. Pour une question causale, exiger une preuve quantitative du mécanisme et l'examen des explications concurrentes ; pour une correction métier, une contre-validation par un agent distinct utilisant un oracle indépendant. La conclusion sépare la réponse à la question, la cause identifiée ou inconnue et l'impact résiduel : un bilan fermé peut résoudre la sous-question de rapprochement, sans démontrer la cause industrielle ni fermer la question causale. Sans preuve suffisante, conserver une conclusion bornée, la limite et la donnée ou l'expérience discriminante manquante ; ne pas inventer une cause industrielle.

Réutiliser les champs stricts de `TaskSpec` : ticket/question dans `objective`, chemin du registre et entrées dans `inputs`, périmètres dans `writable` et `forbidden`, catégories de preuves réellement nécessaires dans `required_evidence`. Le registre reste interdit en écriture aux enfants. Porter le delta dans le message et sa synthèse dans `AgentResult.summary`, les réserves dans `limitations`, les seuls changements réels dans `changed_files` et les manifestes existants dans `manifests`. Aucun champ supplémentaire n'est accepté. Un retour exploratoire sans catégorie de preuve adaptée n'est pas un handoff technique réussi : conserver son message et ses sources sans fabriquer de manifeste.

Handoff contrôle le retour contractuel et gate agrège les preuves techniques sur un état stabilisé ; leur réussite ne statue pas sur la causalité ni sur la promotion d'une nouvelle référence. Le parent conserve cette décision explicite dans le registre, avec gains, dégradations aval, impacts résiduels et limites. La restitution finale désigne les tickets encore ouverts, les contrôles réellement exécutés, les manifestes disponibles et les vérifications non exécutées.

## Commandes exécutables

Toutes les commandes partent de la racine, avec Python 3.11 minimum pour la toolbox (`tomllib`, `hashlib.file_digest`). Vérifier l'environnement existant avant installation. Si nécessaire et justifié, les dépendances runtime/tests sont décrites par `requirements-etudecas-test.txt` ; une revue documentaire ne déclenche aucune installation. Ce fichier ne déclare pas Playwright, pourtant contrôlé par doctor ; la présence du package ne prouve pas celle de Chromium. Ce décalage est suivi dans le backlog de l'audit. PyYAML est notamment utilisé pour lire les métadonnées des skills ; aucune installation editable de l'ancienne démonstration n'est nécessaire.

Après l'incident Sophos, relire chaque cas et ses fixtures avant exécution,
puis sélectionner son identifiant exact. Les anciens essais d'altération de
fichiers, de dates ou de disparition simulée restent exclus. Ne pas lancer tout
un fichier ou une suite globale sur la foi d'une ancienne qualification. Voir
la [procédure de validation](TEST_VALIDATION.md).

```powershell
# Exemple relu : calcul en mémoire rapproché d'un oracle manuel sur deux jours
python -B -m etudecas.toolbox tests --path etudecas/prototypes/scan_2027_risk_control/tests/test_supplier_campaign_mechanics.py::test_memory_window_metrics_match_manual_two_day_oracle

# Invariants indépendants sur le calcul précis, sans régénérer la simulation
python -m etudecas.toolbox qualify --run CHEMIN_RUN

# Qualification CSV et revue hors ligne des lots, si cette carte correspond bien au calcul
python -m etudecas.toolbox qualify --run CHEMIN_RUN --html CHEMIN_HTML

# Autre parcours navigateur existant : navigation générale de la carte
python -m etudecas.toolbox browser --html CHEMIN_HTML

# Contrôle statique des registres documentaires du catalogue
python -m etudecas.toolbox docs

# Agrégation, en remplaçant les chemins par ceux imprimés par les commandes
python -m etudecas.toolbox gate --manifest DOCTOR_MANIFEST --manifest TESTS_MANIFEST --manifest QUALIFY_MANIFEST --require doctor --require tests --require qualify
```

`CHEMIN_RUN`, `CHEMIN_HTML` et les chemins de manifestes sont à remplacer, pas des valeurs par défaut. La toolbox n'infère jamais qu'une archive est le calcul courant. Pour une livraison carte, ajouter une preuve `browser` au gate ; qualifier également les lots lorsque ceux-ci changent. Le parent vérifie le lien de provenance HTML/calcul : les contrôles techniques ne le déduisent pas d'un nom de fichier.

Options communes : `--output` désigne une racine sous `etudecas/artifacts/testing`, `--timeout` le délai maximal de chaque sous-processus (1 800 secondes par défaut). Chaque commande crée son propre sous-dossier UUID ; elle ne réutilise jamais un ancien `junit.xml` ou rapport. Aucun shell n'est appelé et le catalogue ne permet pas d'exécuter une commande libre. Les tests sélectionnés restent du code Python du dépôt : ce runner n'est pas une sandbox pour code hostile. Un timeout termine le processus Python direct ; un navigateur lancé par ce processus peut nécessiter une vérification de fermeture si l'arrêt survient hors de son nettoyage normal.

## Preuves et refus

`manifest.json` contient schéma, run_id, commande, tâche/propriétaire, état, dates, empreintes des entrées, sources/tests et preuves, arguments effectivement exécutés et code retour. `execution.log`, JUnit et/ou rapports existants sont conservés. L'inventaire couvre Python, JavaScript, CSS, PowerShell (`.ps1`), configurations métier, registres des règles et fichiers natifs ; les archives, outputs et preuves générées en sont exclus. L'ajout d'un nouveau fichier couvert invalide aussi l'ancien manifeste. Le code est empreinté avant et après exécution ; une écriture concurrente impose de relancer la vérification sur un état stabilisé.

Le gate exige les types de contrôles demandés, refuse toute preuve non réussie et recalcule les empreintes des fichiers et l'ensemble des sources. Une preuve disparue, altérée ou calculée sur un autre état de code est refusée. Les identités et SHA-256 sont une protection contre les mélanges ou changements accidentels, pas une signature contre un acteur qui falsifierait ensemble manifeste et fichiers. Le gate n'évalue pas lui-même le sens du correctif et ne remplace pas la contre-relecture.

Pour les tests, une sortie pytest nulle sans aucun cas réussi (tous ignorés) est refusée. Un échec réel, une absence de fixture, un timeout ou un rapport de qualification vide ne devient pas un succès. Une commande refusée écrit son manifeste si sa destination est valide ; une erreur d'arguments/destination renvoie un code non nul avant exécution.

La qualification réutilise `etudecas.testing.qualification` et `independent_review`, les résultats JUnit réutilisent `etudecas.testing.report`, le navigateur `etudecas.testing.map_browser`, les docs `etudecas.documentation check-all`. Elle vérifie les conventions physiques programmées et l'affichage couvert. Elle ne certifie ni données industrielles, calibration économique, causalité ni exhaustivité des interactions. Des preuves uniquement de tests ne suffisent pas à qualifier une carte ou une politique économique.

Conventions utilisateur à préserver : jours de sécurité lundi-vendredi, dépôt à 100 % des jours source, conservation des références précédentes et séparation nominal/sensibilités. `tau_process` reste un paramètre de planification à confirmer avant d'en déduire une durée physique d'exécution.

## Validations historiques

Les bilans du déploiement natif, du retrait de la démonstration Python et des
premières qualifications sont conservés dans les [archives](../archive/README.md),
avec leurs chemins d'origine. Ils décrivent les sources et les exécutions de
leur date ; leurs compteurs ne constituent pas une qualification du code
courant ni une autorisation de relancer les anciens essais d'altération de
fichiers.

Les contrats génériques conservés dans `etudecas/toolbox/validation_contracts.py`
ne remplacent pas les indicateurs industriels. Une livraison actuelle doit
désigner ses propres manifestes, les contrôles effectivement exécutés et leurs
limites. Un manifeste refusé conserve sa signification même si un contrôle
interne a réussi.

## Sources officielles revérifiées le 21 octobre 2026

- [Profils natifs et configuration des sous-agents](https://learn.chatgpt.com/docs/agent-configuration/subagents) : champs, héritage, permissions et nombre d'enfants.
- [Skills et découverte projet](https://learn.chatgpt.com/docs/build-skills) : `.agents/skills` et format `SKILL.md`.
- [Instructions AGENTS.md](https://learn.chatgpt.com/docs/agent-configuration/agents-md) : portée du dépôt.

Les exemples sont adaptés aux besoins Etudecas, sans framework supplémentaire. La version `0.154.0-alpha.6.1` était celle observée en septembre. Le relevé du 21 octobre indique Python 3.11.9 et Codex CLI `0.162.0-alpha.17.2` ; cet appel CLI a aussi signalé un refus d'accès à ses fichiers temporaires et n'a pas été relancé. Le [bilan daté](quality/AUDIT_INSTRUCTIONS_20261021.md) distingue versions, preuves et limites.
