# Tests de calibration autonomes — 17 septembre 2026

Les tests du runner de calibration lisaient implicitement un plan externe dont
le graphe pointait vers l'ancien checkout `C:\dev\lca-simu-pr40`. Ils échouaient
avant d'exercer la sélection, le checkpoint et la reprise.

Une fixture construit désormais dans un dossier temporaire une référence
synthétique : 18 liaisons, deux produits, les capacités exigées par le protocole,
31 lignes de référence et les entrées nécessaires au générateur de plan. Le vrai
générateur produit les 36 candidats et les 77 fichiers du plan. Les vrais
validateurs de référence, de signatures et d'empreintes restent exécutés.

Le runner de production n'a pas changé. Une substitution limitée au test autorise
uniquement l'empreinte du plan synthétique fraîchement construit ; pytest restaure
ensuite la valeur originale. Un test distinct vérifie que la configuration de
production refuse ce plan. Les contrôles refusent également un graphe supprimé,
un graphe modifié et un fichier du plan altéré.

L'exécuteur injecté conserve le statut `synthetic_test_only`. Le fichier moteur
de la fixture lève une erreur s'il est exécuté. Ces tests vérifient l'orchestration
et l'intégrité, pas la performance scientifique du simulateur.

Le test du plan historique est conservé avec la fixture `historical_artifact`.
Sans `--historical-artifacts`, il est explicitement ignoré. Avec cette option,
les empreintes et les chemins du plan original doivent être valides ; la fixture
ne réécrit aucune preuve historique. Le module rejoint `pytest-reference.ini`,
qui exclut ce test historique et exécute les tests autonomes.
Une exception dans `.gitignore` permet désormais de versionner cette configuration,
auparavant masquée par la règle générale `*.ini`.

## Validation

Première exécution du module migré : **6 réussites et 1 test historique ignoré**,
en 48,66 secondes. Les quatre nouveaux contrôles de refus passent également
dans une exécution ciblée (21,19 secondes).

La suite de référence élargie réussit : **628 tests et 53 sous-tests**, deux
tests longs ignorés et 16 tests historiques exclus, en 230,58 secondes. Elle
inclut les dix tests autonomes du module. Rapports JUnit et JSON locaux :
`etudecas/artifacts/testing/2026-09-17-calibration/reference.xml` et `reference.json`.
Le contrôle documentaire du registre `run_package` passe également.

Commande ciblée :

```powershell
python -m pytest etudecas/prototypes/scan_2027_risk_control/tests/test_supplier_service_regime_calibration_runner.py -q
```

Les signatures agrégées V8 et les autres fixtures graphe/audit restent des
chantiers distincts. Cette modification ne constitue pas une validation du plan
historique ni une nouvelle exécution de la suite complète.
