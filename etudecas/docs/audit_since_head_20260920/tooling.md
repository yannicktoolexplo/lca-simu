# Revue depuis HEAD — outillage, pack, documentation et CI

Référence : `f95b1db6bb233cbf9750fc6ab2fda3943d6e82ab`, commit du 15 septembre 2026. Revue du 20 septembre, **lecture seule des sources**. Les seules écritures sont ce rapport et les expériences sous `etudecas/artifacts/testing/audit_since_head_20260920/tooling/`. Aucun paquet installé, navigateur téléchargé, service lancé ni simulation lourde exécutée.

Deux défauts fonctionnels sont reproduits : la dépendance navigateur manque à la CI/documentation d'installation ; le gate accepte une preuve de tests après modification d'une fixture CSV non empreintée. Deux autres écarts concernent la couverture CI et une documentation opérationnelle devenue partiellement obsolète. Les contrôles existants réussissent sur le poste actuel : **64 tests et 4 sous-tests**, onze registres documentaires à jour. Ces succès ne réfutent pas les contre-exemples ci-dessous.

## T-01 — P1 : la CI collecte des tests Playwright sans installer Playwright ni Chromium

**Localisation.** `.github/workflows/etudecas-documentation.yml:30–32` installe uniquement `pytest>=9,<10`, puis exécute `pytest etudecas/documentation etudecas/testing`. `etudecas/testing/test_lot_journey.py:6` importe `playwright.sync_api` dès la collecte ; sa fixture `page`, lignes 13–17, lance Chromium. Les modules `test_journey_case`, `test_journey_explorer`, `test_journey_operations` et `test_journey_scenario_delivery` réimportent cette fixture. Il n'y a dans ce job ni installation de Playwright ni installation de son navigateur et des bibliothèques système.

**Reproduction.** Une sonde lance réellement `pytest --collect-only` sur `test_lot_journey.py` en bloquant uniquement l'import de Playwright, pour reproduire son absence sans modifier les paquets du poste. Sortie **2**, `ModuleNotFoundError`. [Journal](../../artifacts/testing/audit_since_head_20260920/tooling/ci-missing-playwright.log), commande exacte dans [results.json](../../artifacts/testing/audit_since_head_20260920/tooling/results.json). Ce n'est pas une exécution distante GitHub ni un environnement neuf installé : c'est une reproduction isolée de la dépendance absente, corroborée par le workflow.

**Portée locale.** La recette de `docs/TEST_VALIDATION.md:29–30` installe `requirements-etudecas-test.txt`, qui ajoute seulement pytest aux exigences principales (NumPy, pandas, openpyxl, Matplotlib). Playwright n'y figure pas, alors que `pytest-reference.ini:9` collecte `etudecas/testing`. Même avec le module Python ajouté, Chromium doit être installé pour la fixture. Le doctor natif réclame également PyYAML et Playwright ; installer seulement ces requirements ne suffit pas à l'ensemble de la toolbox.

**Conséquence.** Une installation suivant les instructions échoue avant d'exécuter les contrôles métier ; le succès du poste déjà équipé ne rend pas ce workflow reproductible.

**Correction proposée, non appliquée.** Déclarer un ensemble de dépendances de vérification comprenant les outils effectivement collectés, et une étape explicite d'installation Chromium adaptée à Linux. Si les tests navigateur sont séparés, rendre leur job obligatoire pour les modifications carte : ne pas les faire disparaître silencieusement avec un `importorskip`. Documenter l'installation locale correspondante. `openpyxl` est bien déclaré via `requirements-etudecas.txt` ; il ne faut pas le présenter comme absent. Le pytest 9 local fournit `_pytest.subtests` : aucun défaut de dépendance `pytest-subtests` n'a été établi.

## T-02 — P2 : une fixture modifiée peut laisser le gate de tests vert

**Localisation.** `etudecas/toolbox/cli.py:61–71` empreinte les sources Python/JS/CSS et certains répertoires de configuration. `:199–211` ne déclare comme entrées du sous-processus pytest que les fichiers de tests sélectionnés. Les CSV de `etudecas_codex_multiagent_pack/data/reference/` ne figurent dans aucun de ces ensembles. Pourtant `tests/test_end_to_end.py:15–16` copie ce répertoire pour l'exécuter et `configs/cases/example_minimal.yaml:4` désigne `fal_aircraft_tiny.csv`.

**Reproduction indépendante.** Dans une racine miniature exclusivement sous le dossier de preuves, un vrai test lit un CSV au même emplacement fonctionnel `pack/data/reference`. Première exécution : **passed**. Le CSV passe de `1` à `2`, sans changement du test ni du code. Le gate du premier manifeste reste **passed**. Le test rejoué retourne **refused**, assertion échouée. Le CSV n'est présent ni dans `inputs` ni dans `code` du manifeste. [Résultat structuré](../../artifacts/testing/audit_since_head_20260920/tooling/results.json), [script reproductible](../../artifacts/testing/audit_since_head_20260920/tooling/review_tooling.py), manifestes conservés sous `fixture_gate_workspace/etudecas/artifacts/testing/proofs/`.

**Conséquence.** La protection contre les changements accidentels est incomplète pour les tests qui lisent des fixtures externes au Python et aux configurations couvertes. Il n'y a ni falsification de manifeste ni appel arbitraire : l'usage normal du gate suffit. Cela ne démontre pas une erreur dans les quatre simulations livrées, dont les qualifications CSV ont des entrées explicites ; cela démontre une limite du gate de catégorie `tests`.

**Correction proposée, non appliquée.** Ajouter des entrées déclarées typées pour les fixtures des tests (`--input` répétable ou manifeste de jeu de tests), empreintées avant/après puis au gate. Couvrir explicitement les petits jeux de référence du pack et les fixtures JSON documentaires utilisées par les tests. Une détection des fichiers ajoutés/supprimés est nécessaire au même titre que leur contenu. Éviter d'empreinter sans distinction tous les résultats lourds du dépôt. Ajouter la régression « CSV modifié : ancien manifeste refusé ».

## T-03 — P2 : changements natifs et toolbox sans contrôle CI dédié

**Localisation.** Les filtres `paths` de `.github/workflows/etudecas-documentation.yml:5–13` couvrent `etudecas/**`, le pack et le workflow lui-même. Ils omettent `.codex/**`, `.agents/**`, `AGENTS.md`, `requirements-etudecas-test.txt`, `requirements-etudecas.txt` et `pytest-reference.ini`. Les commandes des trois jobs ne sélectionnent jamais `etudecas/toolbox/test_cli.py` et n'exécutent ni doctor racine ni ses contrôles structurels équivalents. La suite `pytest-reference.ini` n'inclut pas non plus `etudecas/toolbox`.

**Reproduction statique.** Une PR ne modifiant que `.codex/config.toml` ne correspond à aucun filtre ; une PR modifiant `etudecas/toolbox/cli.py` déclenche le workflow, mais ses 21 régressions dédiées ne sont sélectionnées par aucune commande. Vérification des chemins et des sélecteurs présents, sans déclencher une PR ou un job distant.

**Conséquence.** La configuration réellement découvrable et le mécanisme de refus peuvent régresser alors que le workflow existant ne les contrôle pas. Ce constat ne conteste pas les 21 tests exécutés localement pendant cette revue.

**Correction proposée, non appliquée.** Étendre les filtres aux contrats racine pertinents ; ajouter un job ciblé de toolbox et validation native avec ses dépendances explicites. Le contrôle structurel des fichiers peut rester indépendant d'un appel Codex ou d'un service LLM. Documenter si la suite de référence conserve volontairement cette couverture dans une commande séparée.

## T-04 — P3 : deux descriptions opérationnelles ne suivent plus la couverture actuelle

`etudecas/docs/COVERAGE_AND_LIMITS.md:3` annonce neuf registres et son tableau en liste neuf. `docs/catalog.json` en contient maintenant **onze**, avec `material_traceability` et `audited_semantics` supplémentaires. `check-all` confirme que les onze sont synchronisés ; il ne vérifie pas ce texte de couverture.

`etudecas/docs/AUTOMATION.md:46–49` décrit un workflow qui « n'exécute pas le moteur de simulation », puis `:56–58` des tests « sans importer ni lancer le moteur ». Le workflow actuel sélectionne explicitement `test_correction_contracts.py`, qui importe `run_first_simulation` à la ligne 6 ; il sélectionne aussi les tests de l'API moteur. Au minimum, la promesse d'absence d'import n'est plus vraie. Il convient de parler de tests ciblés et de l'absence de grandes campagnes de simulation, selon ce que les fixtures exécutent effectivement.

Correction proposée : actualiser ces deux pages sans réécrire les audits datés ni leurs résultats historiques. Les rapports d'audit initiaux annoncent leur statut historique et pointent vers les corrections ; leurs anciens chiffres ne sont donc pas assimilés ici à des erreurs actuelles.

## Vérifications et limites

- **64 tests et 4 sous-tests réussis** : documentation 16, toolbox 21, pack 27 ; deux avertissements d'échappement `\d`/`\s` lors de l'analyse statique du template. [Journal](../../artifacts/testing/audit_since_head_20260920/tooling/targeted-tests.log), [JUnit](../../artifacts/testing/audit_since_head_20260920/tooling/targeted.xml).
- **Onze registres contrôlés**, retour 0, sans génération ni acceptation d'empreintes. [Journal](../../artifacts/testing/audit_since_head_20260920/tooling/docs-check.log). Le générateur reste statique, n'exécute pas les tests référencés et ne prétend pas certifier le métier.
- **Neuf fichiers natifs identiques** entre staging et racine ; profils limités à leur rôle, modèle hérité, trois enfants concurrents, trois skills réellement présents dans `.agents/skills`. Ce contrôle ne lance pas une nouvelle session Codex ni ne certifie son authentification. [Comparaison](../../artifacts/testing/audit_since_head_20260920/tooling/secondary-checks.json).
- Les trois exemples du pack passent dans des répertoires temporaires ; le test bout en bout vérifie deux UUID et ne dépend plus d'anciennes sorties. Sept PNG déjà présents dans les outputs ont été décodés en lecture seule. Ces outputs ne sont pas nécessaires au test corrigé. Leur politique de versionnement relève du volet global du parent.
- Aucun des **194 fichiers du périmètre inventorié** n'a changé pendant l'exécution des probes et tests. Les hashes individuels et le hash d'inventaire initial sont conservés dans la couverture. Les sorties de cette nouvelle revue ne sont pas réinjectées dans la baseline.

Le handoff vérifie les changements **déclarés**, pas un confinement par fichier ; cette limite est explicitement documentée. Le lien entre HTML et run reste à confirmer par l'intégrateur : il n'est pas déduit du nom du fichier. Ces limites annoncées ne sont pas artificiellement comptées comme des bogues nouveaux. La revue n'a pas requalifié les prix industriels, la causalité métier, ni les simulations historiques. Les versions distantes des actions GitHub et une exécution GitHub effective n'ont pas été testées ici.

## Couverture fichier par fichier

L'[inventaire de couverture](../../artifacts/testing/audit_since_head_20260920/tooling/coverage.json) liste les **194 chemins**, leur SHA-256 au début de revue, le SHA de baseline, le mode d'examen et les contrôles appliqués. Il distingue :

1. **Manuel** : workflow, exigences/tests de référence, racine native et staging par comparaison, CLI/contrats/tests de toolbox, générateur/batch/tests documentaires, changements Python/config/tests du pack, guides `MULTI_AGENT_OPERATIONNEL`, `TEST_VALIDATION`, `AUTOMATION`, `COVERAGE_AND_LIMITS` et note d'intégration native. Les consommateurs directs non modifiés (case, trajectory, fixture Playwright) ont également été lus pour interpréter le diff.
2. **Généré contrôlé** : pages/manifestes des onze registres comparés au rendu attendu par `check-all` ; rapports/PNG du pack contrôlés structurellement. Ce n'est pas une relecture scientifique de chaque règle.
3. **Mécanique** : tous les autres nouveaux guides, notes historiques, propositions et JSON de qualification : inventaire, décodage/structure lorsque pertinent, empreinte et recherche transversale des affirmations de calendrier/coûts/installation/couverture. Aucune affirmation de lecture sémantique intégrale de ces fichiers. Les liens cassés, preuves ignorées par Git et décisions de conservation sont consolidés par le parent dans le volet global, pour éviter une double attribution.

Les recommandations ci-dessus n'ont pas été implémentées dans cette passe de revue.
