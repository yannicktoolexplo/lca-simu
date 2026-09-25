# Vérifier une modification

Chaque modification doit être vérifiée sur des sources stabilisées, avec un
périmètre annoncé. Les anciens bilans et inventaires de tests sont dans les
[archives](../archive/README.md) ; ils ne qualifient pas le code actuel.

## Sélectionner les contrôles

Après l'incident Sophos du 23 septembre 2026, relire les cas sélectionnés et
leurs fixtures avant de les exécuter. Ne pas lancer une suite globale, un
dossier entier ou une découverte automatique en supposant que tous les tests
respectent la consigne. `pytest-reference.ini` décrit un périmètre historique ;
il ne constitue pas une liste de tests autorisés après cet incident.

Les tests qui altèrent volontairement des fichiers, restaurent leurs dates,
simulent leur disparition ou réécrivent en boucle des fichiers factices restent
exclus. Les contrôles à privilégier sont les calculs en mémoire, les simulations
normales dans un nouveau dossier et les comparaisons en lecture seule avec les
références. En cas de refus d'écriture ou d'alerte, arrêter les exécutions
concernées et diagnostiquer en lecture seule, sans contourner la protection.

Depuis la racine du dépôt, installer les dépendances si nécessaire avec
`python -m pip install -r requirements-etudecas-test.txt`.
Exemples précis de tests de calcul en mémoire relus :

```powershell
python -B -m pytest -q -p no:cacheprovider etudecas/prototypes/scan_2027_risk_control/tests/test_supplier_campaign_mechanics.py::test_memory_window_metrics_match_manual_two_day_oracle
python -B -m pytest -q -p no:cacheprovider etudecas/prototypes/scan_2027_risk_control/tests/test_supplier_campaign_mechanics.py::test_memory_lane_quantities_count_shipped_and_exact_lane_only
```

Le premier rapproche les indicateurs d'un calcul manuel sur deux jours ; le
second vérifie les quantités expédiées pour la liaison exacte. Ces exemples
portent sur leurs fonctions, pas sur tout le moteur. Ne pas élargir la commande
au fichier entier : il contient aussi des anciens tests d'intégrité exclus.
Pour une autre modification, choisir et relire les cas qui couvrent sa règle.

## Vérifier le moteur, les cartes et la documentation

Le [guide de reconstruction](REGENERER_RESULTATS.md) décrit le recalcul nominal
sur 1 825 jours et les quatre présentations conservées. Après un changement du
moteur, rapprocher les résultats du nouveau calcul de la référence : quantités,
stocks, service, coûts et lots concernés. Conserver les conventions sources du
nominal ; les sensibilités utilisent des paramètres séparés.

Les commandes de qualification CSV et de navigation hors ligne figurent dans
le [guide de la toolbox](MULTI_AGENT_OPERATIONNEL.md). Elles prennent le run
et le HTML exacts à vérifier. Les contrôles d'invariants ne certifient ni la
calibration industrielle ni toutes les interactions de la carte.

Le contrôle documentaire est une lecture statique :

```powershell
python -B -m etudecas.documentation check-all
```

Il ne lance ni simulation ni tests métier. Les règles de mise à jour des
empreintes sont dans [AUTOMATION.md](AUTOMATION.md). Les données de tests et
intégrations historiques sont décrites dans [TEST_FIXTURES.md](TEST_FIXTURES.md) ;
leur présence ne dispense pas de la relecture avant exécution.

## Garder une preuve compréhensible

Pour enregistrer le test ciblé et son rapport dans un nouveau dossier de preuves :

```powershell
python -B -m etudecas.toolbox tests --path etudecas/prototypes/scan_2027_risk_control/tests/test_supplier_campaign_mechanics.py::test_memory_window_metrics_match_manual_two_day_oracle
```

La toolbox écrit sous `etudecas/artifacts/testing` et affiche le chemin du
manifeste. Ce dossier contient les commandes réellement exécutées, les résultats
et leurs empreintes. L'outil de rapport `python -m etudecas.testing.report`
peut aussi lire un JUnit existant ; son aide précise les chemins d'entrée et de
sortie. Un rapport absent ou inexploitable ne devient pas un succès.

La restitution doit indiquer les cas exécutés, les résultats, les exclusions et
les limites. Conserver le résumé pytest avec le JUnit pour distinguer tests,
sous-tests et ignorés. Un test ignoré ou exclu n'est pas réussi ; une sélection
réussie n'est pas une validation de toute l'application.
