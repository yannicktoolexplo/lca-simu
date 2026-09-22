# Les deux simulations à consulter

Rangement local du 21 septembre 2026, sans nouveau calcul ni suppression de résultats.

| Dossier | Utilisation | Carte |
| --- | --- | --- |
| [01_reference_actuelle_2026-09-20](01_reference_actuelle_2026-09-20/) | Référence actuelle : nominal, courbes, suivis des lots, scénario de risque et sensibilités. | [Ouvrir la carte](01_reference_actuelle_2026-09-20/maps/supply_graph_audited_corrections_20260920.html) |
| [02_reference_monte_carlo_2026-07-24](02_reference_monte_carlo_2026-07-24/) | Version historique avec Monte Carlo. Calcul du 17 juillet, carte mise à jour le 24 juillet. | [Ouvrir la carte](02_reference_monte_carlo_2026-07-24/maps/supply_graph_active_5y_map_nomc_20260717_165502.html) |
| [archive](archive/) | Autres simulations, essais, comparaisons et journaux dans leur arborescence d'origine. | Historique uniquement. |

La référence actuelle ne contient pas de résultats Monte Carlo ni SCAN.
La seconde carte conserve Monte Carlo, mais précède les corrections récentes.

[Accueil des résultats et vues complémentaires](../../index.html)

## Compatibilité des anciens chemins

Les dossiers ont été déplacés physiquement, sans duplication des données.
Des jonctions Windows masquées conservent les anciens chemins pour les scripts,
liens, manifestes et preuves historiques. Elles apparaissent si l'affichage des
fichiers masqués est activé ; ce sont des liens, pas d'autres simulations.
Le réglage local `.vscode/settings.json` masque uniquement ces 37 liens dans
l'explorateur VS Code/Cursor. Les deux références et `archive` restent visibles.
Ce réglage ne modifie pas l'affichage de Windows ni celui de l'application Codex.
Ne pas les parcourir pour compter les fichiers : les mêmes données seraient
comptées plusieurs fois. Ne pas écraser une archive via son ancien chemin.

Les manifestes d'origine et les HTML restent identiques. Ces résultats volumineux
restent locaux. Sur un autre poste, copier les dossiers physiques et recréer les
jonctions si les anciens accès sont nécessaires.

Inventaire, journal des déplacements et vérification :
`etudecas/artifacts/testing/results_organization_20260921/`.
