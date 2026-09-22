# Cinq priorités : provenance V8, tests historiques et documentation

## 1. Inventaire V8 expliqué

L'inventaire original a été retrouvé dans la supervision Stage2 V8. Sa signature
`02ed2e5b…f8191a` est bien celle attendue par Stage3. Sa copie conservée dans
[`v8-stage2-reference.json`](../quality/v8-stage2-reference.json) permet désormais
un diagnostic reproductible sans accès au dossier historique.

Le nouvel outil `python -m etudecas.testing.inventory` exige cette signature,
vérifie le manifeste, compare les fichiers et refuse les chemins hors du dépôt.
Il distingue les fichiers absents, les différences de fins de ligne et les autres
écarts. Il n'écrit aucune source et ne remplace aucune empreinte attendue.

Vingt et une représentations CRLF ont été corrigées après preuve d'égalité avec
les octets Git et les hashes historiques. L'inventaire contient maintenant
61 sources identiques sur 68. Sept écarts restent non expliqués par LF ; le
chemin du dépôt signé diffère également. Le contrat historique reste donc refusé.
Les diagnostics [avant](../quality/2026-09-17-v8-inventory-before.json) et
[après](../quality/2026-09-17-v8-inventory-after.json) conservent le détail.

Une [recherche complémentaire](../quality/2026-09-17-v8-historical-source-search.json)
retrouve l'empreinte de `etudecas/__init__.py` avec des fins de ligne CRLF ;
les six autres empreintes ne correspondent pas aux versions Git examinées,
y compris leurs représentations LF/CRLF. Cela ne prouve pas leur absence de
toute archive externe. Ces sept sources ne sont pas remplacées pour satisfaire
un ancien manifeste, et le chemin historique du dépôt reste une autre différence.

## 2. Intégrations historiques explicites

Les validations complètes des wrappers de clôture, de livraison finale et du
checkpoint op100 exigent désormais les options historiques, au lieu de chercher
implicitement un ancien checkout. Les contrôles autonomes de syntaxe, de statut
et de décision sont conservés.

Le test d'inventaire Stage3 figé est une intégration explicite. Deux tests
autonomes vérifient la découverte des sources déclarées et le refus d'un autre
prédécesseur. Ce dernier utilise un prédécesseur simulé pour isoler le contrôle
de signature Stage3 ; il ne certifie pas une livraison complète.

Vérification ciblée : **46 tests réussis, 4 intégrations historiques ignorées**,
en 34,11 secondes. Rapports locaux sous
`etudecas/artifacts/testing/2026-09-17-next-five/inventory-wrappers.xml`.

## 3. Documentation métier reliée au code

Le [domaine besoins/capacités](../CAPACITY_COUPLING.md) ajoute deux règles au
registre documentaire. Elles relient les calculs directs/amont et le rattachement
de l'audit au protocole à leurs fonctions et tests. Elles explicitent les unités,
le rôle des lots et des taux d'utilisation, et le refus d'une attribution au seul
MRP. Les pages [générées](../generated/capacity_coupling/index.md) sont suivies
par les mêmes empreintes AST et métier que les trois domaines existants.

## 4. Automatisation globale

Un catalogue exhaustif pilote `build-all`, `check-all` et `watch-all`. Un registre
oublié, une sortie dupliquée ou une entrée invalide sont signalés. Les contrôles
de fraîcheur restent en lecture seule et les empreintes ne sont jamais acceptées
automatiquement, y compris en surveillance.

Le workflow GitHub prépare un contrôle des documents et de l'outillage pour les
changements du dossier `etudecas`. Il est ajouté localement, sans push ni exécution
distante. Les commandes équivalentes sont vérifiées localement : **24 tests et
4 sous-tests réussis**, puis `check-all` réussi sur les quatre registres, y compris
avec `python -S` (bibliothèque standard seule). Voir le [guide](../AUTOMATION.md).
Le même `check-all` passe dans une copie temporaire relocalisée, contenant
uniquement l'outillage documentaire, ses sources référencées et ses documents.

## 5. Qualification complète

La suite `python -m pytest etudecas -q --tb=short` donne **2 324 réussites,
1 échec et 28 tests ignorés**, avec 62 sous-tests réussis, en 1 681,76 secondes
(28 min 01 s). Elle a collecté 2 353 tests. L'environnement Windows reste
Python 3.11.9, pytest 9.1.1, NumPy 2.4.6, pandas 3.0.3, matplotlib 3.11.0 et
openpyxl 3.1.5.

Les 28 tests ignorés se répartissent en 21 intégrations historiques sans option
explicite, quatre anciennes fixtures incompatibles avec leur contrat publiable,
deux tests longs non activés et un contrôle JavaScript faute de Node.js.

Le [bilan JSON](../quality/2026-09-17-current-test-status.json) rapproche chacun
des 79 anciens échecs de son résultat actuel : **73 passent, cinq sont ignorés
explicitement comme historiques et un échoue pour une nouvelle cause**.
Les cinq intégrations ignorées ne sont pas comptées comme corrigées ni validées.

L'échec concerne `test_screen_checkpoint_and_resume_adds_only_seeds_16_to_30` :
Windows refuse le remplacement de `execution_ledger.json.tmp` par
`execution_ledger.json` (`PermissionError`, WinError 5). Le même test, relancé
isolément sans modification du code, réussit en 19,12 secondes. La cause exacte
du refus d'accès n'est pas démontrée ; la réussite isolée n'annule pas l'échec
de l'exécution complète. Aucune exception n'a été masquée, aucun retry ajouté
au test et aucune source scientifique figée modifiée pour contourner ce résultat.

Les rapports locaux sont sous `etudecas/artifacts/testing/2026-09-17-next-five/` :
`full.log`, `full.xml`, `full.json`, `collection.txt`, `environment.json` et
`calibration-retest.xml`. La qualification complète révèle donc une priorité
supplémentaire : rendre les écritures atomiques robustes aux refus temporaires
Windows, avec une stratégie explicite de versionnement des contrats figés.

Les cinq priorités prévues sont traitées, mais la qualification globale reste
avec cet échec intermittent. Les contrats V8 historiques restent également
non qualifiés dans le checkout courant. Un contrôle documentaire réussi ne vaut
pas validation scientifique des campagnes historiques.
