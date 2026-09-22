# Parcours bidirectionnel des lots — 19 septembre 2026

Correction après retour utilisateur : le parcours devait être une option distincte. L'intégration initiale dans « Suivi de lots » est retirée. Le bouton « Parcours simplifié des lots » ouvre désormais sa propre fenêtre ; l'affichage et les commandes du suivi existant sont restaurés. Les [preuves de séparation](../../artifacts/testing/journey_separate_20260919/verification-summary.json) contrôlent aussi l'absence de modification du suivi pendant la navigation.

La carte propose un parcours compact, une recherche de lots et d'expéditions et un recentrage depuis toute étape. On peut suivre une réception matière jusqu'aux fabrications et aux clients, puis remonter depuis une réception client. Chaque occurrence conserve son identité, ses liens physiques, ses quantités et ses dates.

Pour **PBATCH-411EC755D7110AE0**, le parcours aval présente une fabrication, un dépôt et deux réceptions client. Les contributions du PF sont **3 473 + 10 927 = 14 400 UN**, distinctes des réceptions totales de 13 251 et 13 415 UN. La réception **SHIP-00000203** retrouve les fabrications LOT-00002653 et LOT-00002658, puis leurs destinations.

La revue visuelle a conduit à retirer le regroupement des stocks au même dépôt : celui-ci pouvait suggérer des chemins croisés inexistants. Un test vérifie désormais que chaque branche garde ses propres liens. Un premier test échouait parce qu'il lisait un détail replié ; il ouvre maintenant le détail avant d'examiner son contenu.

Les [preuves de cette livraison](../../artifacts/testing/journey_20260919/verification-summary.json) rassemblent tests ciblés, contrôles Chromium, invariants CSV et empreintes des fichiers. La [capture PF](../../artifacts/testing/journey_20260919/browser/pf-destinations.png) et la [capture matière](../../artifacts/testing/journey_20260919/browser/material-destinations.png) montrent le rendu vérifié. Les vérifications portent sur ces invariants et ces cas ; elles ne certifient pas exhaustivement toute la simulation.

Les données et résumés du calcul nominal sont conservés. La nouvelle carte est produite à partir du résultat qualifié, sans rejouer le moteur ni changer les stocks de sécurité. Les numéros fabricant et camions réels absents restent inconnus ; les nouveaux incidents physiques restent une étape ultérieure.

Voir le [guide d'utilisation et les règles](../PARCOURS_DES_LOTS.md).
