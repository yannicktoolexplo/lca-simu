# Etudecas : agents natifs et toolbox de preuves

L'orchestration utilise les sous-agents natifs de Codex. La toolbox Python exécute des contrôles déterministes existants ; elle n'appelle aucun modèle et ne lance ni serveur MCP ni SDK externe. Le mini-kit `etudecas_agentkit` reste une démonstration indépendante du moteur principal.

## Installation locale et état vérifiable

Le déploiement révisable est dans `etudecas_codex_multiagent_pack/native/`, avec la même arborescence que la racine cible : `AGENTS.md`, `.codex/config.toml`, quatre fichiers `.codex/agents/*.toml`, trois `.agents/skills/*/SKILL.md`. Ces neuf fichiers ont été installés à la racine par l'intégrateur le 20 septembre 2026 ; un doctor racine a ensuite réussi. Sur un autre poste, copier ces fichiers après examen et fusionner les instructions et paramètres existants au lieu de les écraser. Aucun paramètre utilisateur global n'est nécessaire. Lorsque les répertoires cibles sont protégés par l'environnement, conserver le staging et confier la copie à l'intégrateur autorisé ; ne pas contourner la protection.

```powershell
# Validation structurelle du déploiement préparé, sans prétendre qu'il est installé
python -m etudecas.toolbox doctor --native-root etudecas_codex_multiagent_pack/native
# Après copie : contrôle de la racine réellement découvrable
python -m etudecas.toolbox doctor
```

Chaque commande affiche un objet JSON contenant `status`, `manifest` et `error`. Le manifeste référence `result.json`, où `installed_at_repository_root` distingue staging et racine. Un doctor staging réussi ne satisfait pas un gate exigeant doctor. Ce contrôle prouve présence/syntaxe/dépendances, pas encore le chargement des rôles par une nouvelle session, l'authentification Codex ou le lancement du navigateur. Vérifier la découverte dans la prochaine session Codex sur ce dépôt, puis déléguer une tâche bornée réellement utile ; ne pas lancer un second appel LLM uniquement pour produire un badge d'installation.

La configuration limite les enfants concurrents à trois, le parent étant exclu. Les quatre rôles disponibles ne doivent donc pas nécessairement tourner simultanément. Le modèle et l'effort sont hérités du parent. Les politiques réelles du runtime restent prioritaires.

## Contrat d'une délégation

Le parent attribue un objectif observable, un scénario et ses entrées exactes, des fichiers autorisés/interdits, un livrable et les contrôles attendus. Les écrivains n'ont jamais le même fichier en propriété simultanée. Un retour contient : état (`terminé`, `refusé` ou `incomplet`), changements, preuves avec chemins de manifestes, résultat des contrôles et limites. Une narration sans preuve ne vaut pas validation.

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

Les restrictions par fichier sont des instructions, pas un mécanisme de confinement. Les profils d'écriture utilisent `workspace-write` et l'explorateur `read-only`, sous réserve des permissions effectivement accordées. Pour une isolation matérielle des modifications, utiliser des worktrees distincts et intégrer séquentiellement.

Les skills `etudecas-orchestrate`, `etudecas-qualify`, `etudecas-map-review` routent vers les contrôles concrets. La délégation doit être utile et indépendante ; une modification simple ne nécessite pas quatre agents.

## Commandes exécutables

Toutes les commandes partent de la racine, avec le Python disposant des dépendances du projet. Python 3.11 minimum pour la toolbox (`tomllib`, `hashlib.file_digest`). Le pack Python conserve son minimum 3.10 et déclare désormais Pillow comme dépendance d'exécution, car son validateur ouvre réellement les images.

```powershell
# Tests ciblés : fichiers explicites ou node IDs, sans arguments pytest arbitraires
python -m etudecas.toolbox tests --path etudecas/toolbox/test_cli.py
python -m etudecas.toolbox tests --path etudecas/testing/test_report.py

# Invariants indépendants sur le calcul précis, sans régénérer la simulation
python -m etudecas.toolbox qualify --run etudecas/simulation/result/_reruns/corrected_map_20260918

# Qualification CSV et revue hors ligne des lots, si cette carte correspond bien au calcul
python -m etudecas.toolbox qualify --run CHEMIN_RUN --html CHEMIN_HTML

# Autre parcours navigateur existant : navigation générale de la carte
python -m etudecas.toolbox browser --html CHEMIN_HTML

# Synchronisation des registres documentaires du catalogue
python -m etudecas.toolbox docs

# Agrégation, en remplaçant les chemins par ceux imprimés par les commandes
python -m etudecas.toolbox gate --manifest DOCTOR_MANIFEST --manifest TESTS_MANIFEST --manifest QUALIFY_MANIFEST --require doctor --require tests --require qualify
```

`CHEMIN_RUN`, `CHEMIN_HTML` et les chemins de manifestes sont à remplacer, pas des valeurs par défaut. La toolbox n'infère jamais qu'une archive est le calcul courant. Pour une livraison carte, ajouter une preuve `browser` au gate ; qualifier également les lots lorsque ceux-ci changent. Le parent vérifie le lien de provenance HTML/calcul : les contrôles techniques ne le déduisent pas d'un nom de fichier.

Options communes : `--output` désigne une racine sous `etudecas/artifacts/testing`, `--timeout` le délai maximal de chaque sous-processus (1 800 secondes par défaut). Chaque commande crée son propre sous-dossier UUID ; elle ne réutilise jamais un ancien `junit.xml` ou rapport. Aucun shell n'est appelé et le catalogue ne permet pas d'exécuter une commande libre. Les tests sélectionnés restent du code Python du dépôt : ce runner n'est pas une sandbox pour code hostile. Un timeout termine le processus Python direct ; un navigateur lancé par ce processus peut nécessiter une vérification de fermeture si l'arrêt survient hors de son nettoyage normal.

## Preuves et refus

`manifest.json` contient schéma, run_id, commande, tâche/propriétaire, état, dates, empreintes des entrées, sources/tests et preuves, arguments effectivement exécutés et code retour. `execution.log`, JUnit et/ou rapports existants sont conservés. L'inventaire couvre Python, JavaScript, CSS, configurations métier, registres des règles et fichiers natifs ; les archives, outputs et preuves générées en sont exclus. L'ajout d'un nouveau fichier couvert invalide aussi l'ancien manifeste. Le code est empreinté avant et après exécution ; une écriture concurrente impose de relancer la vérification sur un état stabilisé.

Le gate exige les types de contrôles demandés, refuse toute preuve non réussie et recalcule les empreintes des fichiers et l'ensemble des sources. Une preuve disparue, altérée ou calculée sur un autre état de code est refusée. Les identités et SHA-256 sont une protection contre les mélanges ou changements accidentels, pas une signature contre un acteur qui falsifierait ensemble manifeste et fichiers. Le gate n'évalue pas lui-même le sens du correctif et ne remplace pas la contre-relecture.

Pour les tests, une sortie pytest nulle sans aucun cas réussi (tous ignorés) est refusée. Un échec réel, une absence de fixture, un timeout ou un rapport de qualification vide ne devient pas un succès. Une commande refusée écrit son manifeste si sa destination est valide ; une erreur d'arguments/destination renvoie un code non nul avant exécution.

La qualification réutilise `etudecas.testing.qualification` et `independent_review`, les résultats JUnit réutilisent `etudecas.testing.report`, le navigateur `etudecas.testing.map_browser`, les docs `etudecas.documentation check-all`. Elle vérifie les conventions physiques programmées et l'affichage couvert. Elle ne certifie ni données industrielles, calibration économique, causalité ni exhaustivité des interactions. Des preuves uniquement de tests ne suffisent pas à qualifier une carte ou une politique économique.

Conventions utilisateur à préserver : jours de sécurité lundi-vendredi, dépôt à 100 % des jours source, conservation des références précédentes et séparation nominal/sensibilités. `tau_process` reste un paramètre de planification à confirmer avant d'en déduire une durée physique d'exécution.

## Validation livrée

Le test bout en bout du pack utilise désormais une copie temporaire de données/configurations et contrôle deux sorties UUID distinctes, le JSON de validation et un PNG réellement décodable. Les anciens outputs globaux ne peuvent plus le satisfaire. Le pack a passé 27 tests après cette correction.

Les 21 tests de toolbox exécutent notamment un pytest réussi, un pytest volontairement faux et un pytest entièrement ignoré, puis vérifient que gate refuse les erreurs, preuves modifiées, sources ajoutées et catégories absentes. Ils couvrent aussi JS/CSS/configuration ajoutés ou modifiés, handoff hors périmètre/mauvaise identité, doctor staging, timeouts, entrées manquantes et destinations interdites. Les preuves documentaires incluent le catalogue et toutes les sources métier déclarées : un texte métier modifié invalide aussi le gate. Voir les manifestes d'exécution locaux sous `etudecas/artifacts/testing/native_multiagent_20260920/` pour l'état précis des runs ; un manifeste refusé conserve sa signification même si un contrôle interne a réussi.

Premières exécutions réelles : `doctor-85134ba8264f4ef5a8dcd4dd922e5f5d` et `tests-29fc4dfc57f64fa4a9d8ed93bd00cfa1` ont réussi ; `qualify-768bdead06334cf2a1f79031484006cb` a qualifié les invariants du nominal conservé. La tentative documentaire `docs-122141e44e5648009647ea7f8dd0e8e9` a correctement refusé des registres/empreintes devenus obsolètes pendant les corrections concurrentes. Ces identifiants retracent les essais, ils ne remplacent pas les contrôles finaux après stabilisation du dépôt : toute modification ultérieure de code rend leurs empreintes historiques.

## Sources officielles consultées le 20 septembre 2026

- [Profils natifs et configuration des sous-agents](https://learn.chatgpt.com/docs/agent-configuration/subagents) : champs, héritage, permissions et nombre d'enfants.
- [Skills et découverte projet](https://learn.chatgpt.com/docs/build-skills) : `.agents/skills` et format `SKILL.md`.
- [Instructions AGENTS.md](https://learn.chatgpt.com/docs/agent-configuration/agents-md) : portée du dépôt.

Les exemples sont adaptés aux besoins Etudecas, sans framework supplémentaire. L'environnement observé utilise Codex CLI `0.154.0-alpha.6.1` et Python 3.11.9 ; le doctor expose les versions effectivement utilisées sur chaque poste.
