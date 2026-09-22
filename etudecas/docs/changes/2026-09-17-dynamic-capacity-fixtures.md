# Fixtures graphe/audit cohérentes — 17 septembre 2026

Treize tests du protocole de besoins dynamiques étaient bloqués parce qu'ils
combinaient les sources du dépôt courant et un audit externe lié à un autre
chemin de graphe. Le contrôle de cohérence refusait correctement cet assemblage.

Les tests utilisent maintenant deux petits CSV conservés et versionnés, avec
leurs empreintes et leur provenance. Le graphe et les profils du dépôt sont copiés
dans le dossier temporaire du test ; le véritable constructeur reconstruit
l'audit à partir de ces mêmes entrées. Les validateurs restent actifs. Les CSV
historiques d'origine et l'ancien audit ne sont ni modifiés ni lus par ces tests.
Le moteur et les contrats de production restent inchangés.

Le test du constructeur d'audit utilise également ces fichiers conservés et
ne dépend plus de la présence d'un export externe. Il vérifie toujours la
conservation du snapshot, la suppression possible de sa copie source et le
refus d'un snapshot altéré. Deux tests supplémentaires vérifient le refus d'un
audit associé à un chemin ou à une empreinte de graphe différents.

## Documentation métier

Le [guide des données de test](../../prototypes/scan_2027_risk_control/tests/fixtures/dynamic_capacity/README.md)
explique le couplage entre besoins MRP, capacités fournisseurs et approvisionnement
amont. Il précise pourquoi la comparaison ne mesure pas un effet du MRP seul.
Les données conservées servent à une régression analytique, sans nouvelle simulation.

## Vérification et limites

La première exécution du module `test_supplier_dynamic_requirement_reference.py`
donne **21 réussites**, en 23,75 secondes, dont les 13 tests auparavant bloqués.
Les deux modules rejoignent ensuite le socle de référence avec les deux nouveaux
contrôles de discordance de graphe.

La suite de référence élargie donne **653 tests et 53 sous-tests réussis**, deux
tests longs ignorés et 16 tests historiques exclus, en 236,89 secondes. Elle
inclut les 25 tests des deux modules concernés. Les trois registres documentaires
passent leur contrôle de fraîcheur. Rapports locaux :
`etudecas/artifacts/testing/2026-09-17-dynamic-capacity/reference.xml` et
`reference.json`. Commande exécutée :

```powershell
python -m pytest -c pytest-reference.ini -q --junitxml=etudecas/artifacts/testing/2026-09-17-dynamic-capacity/reference.xml
```

La suite complète hors périmètre de référence n'a pas été relancée ; le bilan
initial de 79 échecs reste une photographie historique, pas le compteur courant.

La substitution préexistante du validateur profond du checkpoint V3 est conservée
et documentée. Les tests du runner vérifient son orchestration avec des preuves
injectées ; ils ne valident pas une campagne scientifique historique complète.
Les signatures d'inventaire V8 et de plan V2 restent des priorités distinctes.
