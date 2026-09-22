# Contrôles des sources figées — 17 septembre 2026

Les fins de ligne Windows empêchaient les contrôles SHA-256 de reconnaître des
sources pourtant identiques au contenu Git. Cette correction rétablit les octets
attendus pour 58 fichiers supplémentaires, dont deux fichiers de tests.
Avec les six fichiers déjà traités, `.gitattributes` protège 64 chemins en LF.

Pour chaque correction, trois preuves ont été vérifiées avant écriture :
l'empreinte du fichier courant, l'égalité entre sa version LF et l'empreinte
attendue par un consommateur existant, et l'égalité de cette version LF avec
`git show HEAD:<chemin>`. Une vérification finale confirme les 58 empreintes,
les octets Git et la politique LF. Aucun hash attendu ni comportement scientifique
n'a été modifié. Les preuves sont dans
[`2026-09-17-frozen-sources.json`](../quality/2026-09-17-frozen-sources.json).

## Vérifications

La reprise des **59 tests auparavant en échec** sur les sources ou contrats figés
donne **51 réussites et 8 échecs**, en 253,98 secondes. Ces huit échecs sont
décrits ci-dessous et recensés dans le
[bilan JSON](../quality/2026-09-17-frozen-results.json).

Le socle de référence (`python -m pytest -c pytest-reference.ini -q`, avec sortie
JUnit) réussit : **618 tests, 53 sous-tests**, deux tests longs ignorés et
15 tests historiques exclus, en 173,58 secondes.

Les trois registres documentaires passent `python -m etudecas.documentation check`
avec leurs chemins respectifs. La page `PROVENANCE.md` et la documentation générée
du registre `run_package` ont été mises à jour après revue de cette modification.

Les rapports locaux sont conservés sous
`etudecas/artifacts/testing/2026-09-17-frozen/` : `reference.xml/json/log`,
`selected-tests.json`, `retest-final.xml/json/log` et diagnostics complémentaires.
L'environnement est celui du [bilan de référence](2026-09-17-test-baseline.md).

## Limites et prochaine priorité

Six tests de calibration dépassent désormais le contrôle du constructeur, mais
échouent sur une entrée du plan historique. Le graphe déclaré sous
`C:\dev\lca-simu-pr40\etudecas\simulation_prep\result\reference_baseline\_mrp_bom_tests\`
est absent. Le validateur produit un message générique de discordance d'empreinte
qui couvre aussi cette absence. Il faut rendre ces tests indépendants de cet ancien
checkout, ou fournir explicitement leurs données historiques cohérentes.

Deux tests V8 restent liés à la signature agrégée de l'inventaire Stage2 V2.
Cet inventaire inclut aussi le chemin absolu du dépôt et les tailles des sources.
Les 68 sources courantes de cet inventaire ne présentent pas de différence de
contenu avec HEAD une fois leurs fins de ligne normalisées. Toutefois, reconstruire
en mémoire l'inventaire avec les octets HEAD, pour le chemin courant ou l'ancien
chemin `C:\dev\lca-simu-pr40`, ne retrouve pas la signature attendue. Cela ne suffit
donc pas à attribuer cet écart aux seules fins de ligne : l'inventaire historique
accepté reste nécessaire pour une comparaison concluante. La signature reste intacte.

Le bilan global initial de 79 échecs est conservé comme photographie de départ.
Cette intervention cible les 59 échecs classés « sources ou contrats figés » ;
elle ne remplace pas une nouvelle exécution complète. Les autres familles du plan
(cohérence graphe/audit, signatures V2 et checkouts historiques) restent à traiter.
