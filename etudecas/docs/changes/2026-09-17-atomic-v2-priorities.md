# Cinq priorités suivantes : publication et reprise des calibrations

## 1. Écritures atomiques robustes

`etudecas/atomic_io.py` publie les JSON et CSV avec un temporaire unique dans le
dossier cible, synchronisation et remplacement. Les codes Windows 5, 32 et 33
sont retentés dans une limite de six essais. Les autres erreurs remontent
immédiatement. Le fichier précédent reste intact si la publication échoue.
Un nettoyage impossible ajoute une note à l'exception initiale.

## 2. Intégration versionnée et provenance

`supplier_service_regime_calibration_runner_v2.py` utilise ce module. Sa signature
et son manifeste identifient la politique d'écriture et le SHA-256 de sa source.
Les dossiers V1 sont refusés : cette version sert aux nouvelles exécutions,
avec les mêmes exigences de plan signé. Les appelants historiques restent V1.

Le [contrôle des sources](../quality/2026-09-17-atomic-v2-source-review.json)
confirme que les trois modules historiques examinés n'ont pas changé pendant
ce lot. Parmi les 42 fonctions/classes comparées entre V1 et V2, 37 ont le même
AST. Les cinq différences relues concernent les écritures, la signature,
le manifeste et son contrôle final de provenance. Les constantes de version
et les imports sont également modifiés explicitement. Les deux nouvelles
sources sont protégées en LF dans `.gitattributes`.

## 3. Tests des refus et des reprises

Les scénarios de calibration existants s'exécutent maintenant sur les deux
versions, avec leurs validateurs réels et un plan synthétique local. Les tests
ajoutés couvrent notamment : refus Windows temporaire ou persistant, erreur
de sérialisation ou de synchronisation, nettoyage impossible, écrivains
concurrents, CSV multiligne, non-réutilisation des sorties V1, liaison du module
d'écriture à la signature et reprise sans réexécuter les cas terminés.

L'écriture d'une preuve et celle du registre ne forment pas une transaction.
Un refus persistant peut laisser une preuve non inscrite : un test vérifie que
la reprise la refuse, sans réparation automatique ni nouvelle exécution.

Le premier passage ciblé donne **32 réussites, 1 échec et 2 tests historiques
ignorés** en 96,43 secondes. L'échec reproduit `WinError 5` dans le parcours de
checkpoint **V1** ; le même parcours V2 passe. Les quatre tests supplémentaires
d'intégration des erreurs passent ensuite en 62,91 secondes. La V1 reste donc
exposée au problème ; créer V2 ne corrige pas rétroactivement ses contrats.

## 4. Documentation technique et métier automatisée

Le [guide de calibration](../CALIBRATION_EXECUTION.md) décrit les étapes,
les commandes, les garanties et les limites. Trois règles et seize références
au code, aux constantes et aux tests constituent le cinquième domaine du
catalogue. Les pages sont générées et contrôlées par `build-all`/`check-all`,
y compris sans dépendances tierces avec `python -S`.

Le workflow local ajoute les tests d'écriture sur Windows et Linux. Aucun push,
aucune exécution GitHub et aucune nouvelle campagne scientifique n'ont été faits.

## 5. Vérification et bilan

La suite locale de référence est élargie aux tests du module d'écriture, aux
scénarios V2 et aux tests d'erreur. Son résultat final figure ci-dessous après
exécution. La suite complète du lot précédent reste un bilan distinct : elle
n'est pas réexécutée dans ce lot. Une réussite de la suite de référence ne
requalifie pas les campagnes historiques V8 et n'annule pas l'échec V1 observé.

Résultat de l'exécution commencée le 17 et terminée le **18 septembre 2026** :
**685 réussites, 3 échecs, 2 tests longs ignorés, 17 intégrations historiques
désélectionnées et 53 sous-tests réussis**. La collecte sélectionne 690 tests
sur 707. Les 37 tests d'écriture et de calibration V1/V2 passent dans ce parcours.

Les trois échecs sont des `subprocess.TimeoutExpired` dans
`test_historical_fixture_policy` (cas `no_repo`) et
`test_powershell_go_validation` (cas `inventory-v3` et `inventory-v4`).
Cette invocation traversant la nuit indique 58 057,31 secondes écoulées
(16 h 07 min 37 s) ; cette durée n'est pas une mesure de performance exploitable.
La cause environnementale exacte des délais n'est pas établie.

Les trois cas relancés isolément **sans changement de code ni de délai** passent
en **8,35 secondes**. Cette relance n'annule pas les trois échecs du premier
rapport, conservés dans le [bilan de référence](../quality/2026-09-18-atomic-v2-reference.json).
Son [complément de relance](../quality/2026-09-18-atomic-v2-timeout-recheck.json)
est séparé. Les JUnit bruts sont dans
`etudecas/artifacts/testing/2026-09-17-atomic-v2/` ; le journal de référence est
`etudecas/artifacts/testing/2026-09-17-atomic-v2-reference.log`.

Les cinq registres documentaires sont à jour (`python -S -m
etudecas.documentation check-all`). Le YAML du workflow est valide ; les tests
Windows sont exécutés localement, la matrice GitHub Linux/Windows reste à exécuter
après publication. Les cinq priorités sont réalisées ; les réserves de validation
concernent la V1, les délais de cette invocation et les campagnes historiques.
