# Validation de référence et inventaire complet

Le [bilan du 17 septembre 2026](changes/2026-09-17-test-baseline.md) contient
les résultats initiaux et la liste des échecs à cette date. Les interventions
suivantes sont détaillées dans les bilans des
[sources figées](changes/2026-09-17-frozen-source-checks.md) et des
[fixtures de calibration](changes/2026-09-17-calibration-fixtures.md), puis des
[fixtures graphe/audit](changes/2026-09-17-dynamic-capacity-fixtures.md) et des
[signatures V2](changes/2026-09-17-v2-plan-signatures.md).
Le [bilan des cinq priorités suivantes](changes/2026-09-17-next-five-priorities.md)
rassemble le diagnostic V8, les intégrations historiques explicites, les nouveaux
contrôles documentaires et la qualification complète actualisée.

Le [lot suivant : écritures et reprise V2](changes/2026-09-17-atomic-v2-priorities.md)
ajoute la publication robuste, les tests d'erreur et un cinquième domaine
documentaire. Il conserve les tests V1 : leur défaut Windows peut encore se
manifester. Son bilan de référence est distinct du dernier inventaire complet.

## Suite de référence

Le [lot du 18 septembre : entrées et API HTTP](changes/2026-09-18-input-contract-priorities.md)
ajoute les tests de types, de graphe et de frontière HTTP à cette suite. Le
nouveau contrat et sa migration sont décrits dans le
[guide des entrées](SIMULATION_INPUT_CONTRACT.md).

Depuis la racine du dépôt :

```powershell
python -m pip install -r requirements-etudecas-test.txt
python -m pytest -c pytest-reference.ini -q
```

`pytest-reference.ini` définit explicitement le périmètre relu : simulation,
visualisation, graphe, analyse, documentation, pipeline, provenance, outils de
rapport et une sélection de modules de prototypes rendus autonomes. Les tests
marqués `historical` sont exclus. Les autres tests présents dans ces répertoires
sont collectés normalement ; aucun filtre par réussite ou `xfail` supplémentaire
n'est ajouté. Les nouveaux modules de prototypes nécessitent une revue avant
d'entrer dans cette liste.

Les données du dépôt restent nécessaires. L'autonomie visée concerne les
livraisons externes : cette commande n'est pas un bac à sable interdisant tout
accès au système de fichiers. Sous un système sans Windows PowerShell, ses
tests d'exécution sont ignorés avec leur motif ; les contrôles statiques restent
collectés. Les autres motifs d'ignorance doivent aussi être examinés dans le
résumé `-ra`, activé par la configuration.

Cette suite ne remplace pas l'inventaire complet et ne certifie pas le sens
scientifique de tous les résultats. La découverte `unittest` ne constitue
pas une commande équivalente : elle ne découvre pas toutes les fonctions pytest.

## Inventaire et intégrations historiques

```powershell
python -m pytest etudecas -q --tb=short --junitxml=etudecas/artifacts/testing/full.xml
```

Le nom `pytest-reference.ini` est volontairement explicite : pytest ne le
charge pas automatiquement pour cette commande complète. Celle-ci collecte
aussi les prototypes hors référence. Les intégrations déjà migrées demandent
les options décrites dans le [guide des fixtures](TEST_FIXTURES.md) ; les autres
peuvent encore dépendre de livraisons présentes sur le poste. Un test ignoré
ne constitue pas une qualification de cette intégration.

## Rapports exploitables

```powershell
python -m pytest -c pytest-reference.ini -q --junitxml=etudecas/artifacts/testing/reference.xml
python -m etudecas.testing.report --junit etudecas/artifacts/testing/reference.xml --output etudecas/artifacts/testing/reference.json
```

Le JSON contient les compteurs, les résultats par classe/module, tous les
diagnostics d'échec ou d'erreur et les motifs d'ignorance. L'outil retourne 1
lorsqu'il existe un échec/une erreur, 2 si le rapport est absent ou inexploitable,
et 0 sinon. Il ne change pas le résultat des tests. Il lit uniquement le JUnit ;
les cas exclus à la collecte n'y figurent pas. Les compteurs portent sur les
éléments `testcase`, qui peuvent inclure des sous-tests selon la version pytest.
Il faut donc conserver également le résumé pytest pour distinguer tests,
sous-tests et exclusions.

Les rapports bruts sont écrits sous `etudecas/artifacts/`, ignoré par Git.
Les bilans de qualification dans `docs/changes/` doivent indiquer les commandes,
l'environnement, les limites et les échecs restants, plutôt que présenter une
suite partielle réussie comme une validation globale.
