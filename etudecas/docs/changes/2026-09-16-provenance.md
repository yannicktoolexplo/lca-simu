# Références et provenance — 16 septembre 2026

## Changements

Trois sources figées utilisaient CRLF dans la copie Windows alors que les
empreintes scientifiques correspondaient aux octets LF suivis par Git.
La vérification a confirmé une égalité exacte avec `HEAD` après remplacement
de CRLF par LF. La copie locale a été remise en LF et `.gitattributes` fixe
ce format pour ces trois fichiers. Aucune empreinte attendue, aucun manifeste
historique et aucun résultat de simulation n'ont été réacceptés ou reconstruits.

| Source | SHA-256 LF attendu et retrouvé |
|---|---|
| `build_industrial_supply_preliminary_complete_v3.py` | `1b70b09c45153ee4511223b0526ad88436e219f5379ae802fba299e8b18ca260` |
| `supplier_operating_point_full_campaign_v2.py` | `dafb05400feef0cb77ef980c792a061de553ab94a73b281a6942742538e4444d` |
| `supplier_balanced_product_delay_multiseed_refinement_v3.py` | `707cbd79b8758b48a70665250d15e6af547fe0ad01b7bac44bad66ff14a9858e` |

La commande `python -m etudecas.provenance` permet de reproduire ce diagnostic
en lecture seule. Une différence expliquée par CRLF reste un échec de
comparaison exacte, jusqu'à correction effective de la représentation.

Les deux tests Monte Carlo auparavant en échec fournissent maintenant le lien
de provenance requis vers le run cible. Les tests isolent les recherches de
résultats partagés dans des dossiers temporaires. Des cas négatifs couvrent
les mauvais types, les horizons invalides, l'absence de rattachement et les
rattachements incompatibles. Le pipeline rejette ces entrées sans exception
accidentelle ; les sorties explicites/locales incompatibles restent une erreur.

Le [contrat de provenance](../PROVENANCE.md) précise notamment que le chemin
déclaré d'un manifeste n'est pas une preuve cryptographique du contenu du run.
Deux règles supplémentaires relient ce contrat aux implémentations et tests
dans la documentation générée des packages.

## Vérification

- Simulateur, documentation, pipeline et diagnostic de provenance :
  **422 tests réussis, 2 ignorés, 53 sous-tests réussis**, en 100 secondes.
  Commande : `python -m pytest etudecas/simulation etudecas/documentation etudecas/test_run_etudecas_pipeline.py etudecas/test_provenance.py -q --disable-warnings --tb=short`.
- Pipeline et deux modules historiques
  `test_build_industrial_supply_preliminary_complete_v3.py` et
  `test_finalize_supplier_operating_point_full_campaign_v2.py` : première passe
  **68 réussites et 1 échec** révélant la troisième source CRLF ; après sa
  correction, le seul test en échec, la variante `[v3]` de
  `test_resigned_v1_v2_v3_selection_substitution_is_rejected`, passe en 73 secondes.
  La première passe incluait le contrôle de livraison V3 externe et la
  finalisation complète de campagne adaptative, tous deux réussis.
- Les trois sources locales correspondent octet pour octet à `HEAD` et aux
  empreintes attendues. Les deux contrôles documentaires et `git diff --check`
  passent.

## Périmètre restant

Les dépendances à des chemins externes dans les autres tests de prototypes,
les éventuelles autres différences d'empreintes et l'appel à la fonction
absente `_stable_v2_suppliers` restent à traiter. La suite complète des
prototypes n'a pas été requalifiée. Une campagne reproductible nécessite
encore de vérifier ensemble les entrées, les paramètres, les versions du
moteur et les résultats, au-delà du rattachement Monte Carlo par chemin.
