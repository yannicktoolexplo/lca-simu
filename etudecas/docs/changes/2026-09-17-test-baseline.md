# Suite de référence et bilan complet — 17 septembre 2026

## Résultat

La commande de référence est désormais :

```powershell
python -m pytest -c pytest-reference.ini -q
```

Son périmètre est explicite dans la configuration : moteur, exports, cartes,
graphe, analyse, pipeline, provenance, documentation, outil de rapport et
modules de prototypes déjà isolés des livraisons externes. La configuration
ne filtre pas les tests en fonction de leur résultat et n'introduit aucun
`xfail`. Les autres prototypes restent dans l'inventaire complet.

| Exécution | Réussites | Échecs | Erreurs de préparation | Ignorés | Exclus à la collecte |
|---|---:|---:|---:|---:|---:|
| Référence, version finale | 618 | 0 | 0 | 2 | 15 |
| Inventaire `pytest etudecas` | 2 230 | 79 | 0 | 22 | 0 |

La référence a aussi exécuté 53 sous-tests avec succès, en 190 secondes.
L'inventaire complet a exécuté 62 sous-tests avec succès, en 1 624 secondes
(27 minutes). La concurrence entre les deux exécutions influence les durées.

Les 79 échecs sont tous situés dans 18 modules sous
`etudecas/prototypes/scan_2027_risk_control/tests`. Aucun échec du moteur,
du pipeline, des cartes ou de la documentation n'a été observé dans cette
exécution complète. Cela ne constitue pas une certification scientifique de
tous les comportements du simulateur.

## Ce qui reste en défaut

La [liste exhaustive JSON](../quality/2026-09-17-failures.json) contient chaque
test, son module, son message et son groupe de diagnostic. Les groupes
décrivent le contrôle qui échoue, pas une cause racine déjà démontrée pour
chaque test.

| Contrôle bloquant | Tests | Prochaine action |
|---|---:|---|
| Sources ou contrats figés | 59 | Comparer les octets attendus, les fins de ligne et les versions ; conserver les vérifications exactes |
| Graphe différent de celui de l'audit de couplage de capacité | 13 | Construire une fixture cohérente graphe/audit, ou établir le changement de source réel |
| Plan V2 et signature incohérents | 5 | Examiner la construction et la signature des fixtures de raffinement V3/V2 |
| Ancien checkout `C:/dev/lca-simu-pr40` absent | 2 | Migrer ces intégrations vers l'opt-in historique et conserver des tests locaux des fonctions |

Un cas du premier groupe est déjà diagnostiqué précisément :
`supplier_operating_point_full_campaign_v4.py` retrouve l'empreinte attendue
`3bc8795490c6ef9ac1fef25d5dedb22811306ae869477df57e70d483881a5d9d`
après normalisation CRLF → LF. Sa copie courante donne
`ef3154d98816e92c15ef8205462faa791a09c1e11b1c4174ce870ade97fd099a`.
Il n'a pas été modifié pendant cette qualification. Les autres différences
ne sont pas présumées avoir la même cause.

Plusieurs tests négatifs s'arrêtent sur un contrôle de provenance antérieur
à celui qu'ils souhaitaient exercer. Leurs assertions de message échouent
donc également ; il faut rétablir la précondition correcte avant de conclure
sur la garde métier testée. Aucun hash historique n'a été réaccepté pour
obtenir ces résultats.

## Ignorances et limites

Les deux tests ignorés de la référence demandent
`ETUDECAS_RUN_SLOW_TESTS=1` pour valider des vues de lots à cinq ans.
Les quinze tests exclus sont les intégrations marquées `historical`.

Les 22 tests ignorés de l'inventaire complet comprennent : 15 intégrations
historiques sans option explicite, ces 2 tests longs, 1 contrôle JavaScript
sans Node.js, et 4 anciens tests de fixture de groupe fournisseur déjà
désactivés dans le dépôt. Ces quatre derniers ne sont pas qualifiés par cette
exécution. Des dépendances historiques non migrées restent présentes ailleurs.

L'inventaire complet a collecté 2 331 cas avant la création des quatre tests
du nouvel outil de rapport. La collecte finale contient **2 335 cas** ; les
quatre nouveaux tests sont exécutés et réussis dans la référence finale.
Les compteurs ci-dessus conservent les résultats réels de chaque commande,
sans prétendre à une unique exécution de cette collecte finale.

Environnement : Python 3.11.9, pytest 9.1.1, NumPy 2.4.6, pandas 3.0.3,
Matplotlib 3.11.0 et openpyxl 3.1.5, sous Windows. La qualification porte sur
la copie de travail avec ses modifications locales, pas sur un commit propre.
La reproductibilité sur un autre environnement n'a pas été vérifiée ici.

## Rapports et entretien

Les rapports bruts et JSON complets sont conservés localement sous
`etudecas/artifacts/testing/2026-09-17/`, ignoré par Git :

- [Référence JSON](../../artifacts/testing/2026-09-17/reference.json) et [journal](../../artifacts/testing/2026-09-17/reference.log).
- [Inventaire complet JSON](../../artifacts/testing/2026-09-17/full.json) et [journal](../../artifacts/testing/2026-09-17/full.log).
- [Environnement](../../artifacts/testing/2026-09-17/environment.json) et [diagnostic d'empreinte](../../artifacts/testing/2026-09-17/source-diagnostics.json).

`python -m etudecas.testing.report` transforme un JUnit en JSON sans supprimer
les diagnostics. Ses quatre tests vérifient notamment les erreurs de fixture,
les rapports invalides et les diagnostics multiples. Le
[guide de validation](../TEST_VALIDATION.md) donne les commandes reproductibles
et la différence entre référence et inventaire complet.

La prochaine correction doit traiter les sources figées par diagnostic exact,
puis les fixtures graphe/audit et les signatures V2. Une nouvelle référence
scientifique ne doit être produite qu'après examen des changements de contenu.
