# Vérifications ciblées et données de test

Une fixture prépare les données d'un test. Pour les calculs, privilégier des
listes et dictionnaires en mémoire : les résultats peuvent être comparés à un
exemple calculé à la main sans créer ni modifier de fichiers factices.

Depuis l'incident Sophos du 23 septembre 2026, ne pas lancer de suite globale.
Relire les cas sélectionnés et leurs fixtures avant exécution. Les tests qui
altèrent des fichiers, restaurent leurs dates, simulent leur disparition ou
réécrivent des fichiers factices pour éprouver l'intégrité sont exclus.
Le marqueur `not historical` ne garantit pas le respect de cette règle.

## Exemple de sélection en mémoire

Les trois fonctions ci-dessous et leur helper `_memory_campaign_rows` ont été
relus le 25 septembre. Ils utilisent des listes et dictionnaires, sans fixture
`tmp_path`, écriture de fichier ou simulation. Chaque fonction est paramétrée
pour V2 et V4, soit six cas au total :

- complétude des jours de service et de production, sans changer les entrées ;
- comparaison des indicateurs sur deux jours avec un oracle numérique manuel ;
- report du retard initial dans le service à date du deuxième jour.

Depuis la racine du dépôt, sélectionner leurs identifiants exacts :

```powershell
python -B -m pytest -p no:cacheprovider -q `
  etudecas/prototypes/scan_2027_risk_control/tests/test_supplier_campaign_mechanics.py::test_memory_horizons_accept_complete_rows_without_changing_them `
  etudecas/prototypes/scan_2027_risk_control/tests/test_supplier_campaign_mechanics.py::test_memory_window_metrics_match_manual_two_day_oracle `
  etudecas/prototypes/scan_2027_risk_control/tests/test_supplier_campaign_mechanics.py::test_memory_window_metrics_day_one_keeps_starting_backlog
```

`-B` évite les caches Python et `-p no:cacheprovider` désactive le cache pytest.
Ne pas remplacer ces identifiants par le fichier entier : il contient aussi
des tests d'intégrité sur fichiers qui ne doivent pas être exécutés.
Cette commande est un exemple relu, pas une preuve d'exécution réussie.

## Résultats historiques

La fixture `historical_artifact` désigne explicitement des livraisons anciennes.
Sans option `--historical-artifacts`, les tests qui en dépendent sont ignorés
avec un motif. Un dossier explicitement demandé mais absent fait échouer la
vérification. Le marqueur `historical` identifie cette dépendance ; il ne rend
pas le test compatible avec les restrictions après l'incident.

Une livraison historique ne doit pas être remplacée par des données inventées
lorsque le test porte sur son identité. Certains anciens protocoles dépendent
également d'un checkout ou de chemins absolus historiques. Leur documentation
et les sources archivées décrivent ces contraintes ; aucune compatibilité avec
le moteur courant n'est déduite d'un nom de dossier.

## Vérifier une modification du simulateur

Exécuter une simulation normale dans un nouveau dossier, puis comparer ses
exports et sa carte aux références en lecture seule. Le parent collecte les
preuves après stabilisation des sources. Les tests exclus restent signalés
comme non exécutés ; les contrôles numériques ne certifient pas une calibration
industrielle.

En cas de refus d'écriture ou d'alerte de sécurité, arrêter les exécutions
concernées et diagnostiquer en lecture seule. Ne pas multiplier les sondes
d'écriture ni contourner Sophos.

La [documentation antérieure](../artifacts/testing/human_code_20260925/docs-retired.zip)
est conservée avec les anciens modes opératoires retirés. Les preuves de
l'incident restent dans `artifacts/testing/research_triage_20260923/`.
