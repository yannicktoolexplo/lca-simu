# Isolation des fixtures — 16 septembre 2026

## Résultat

Trois modules de tests utilisent désormais une entrée historique explicite
`--historical-artifacts` : courbes nominales, dashboard V8 et campagne V8.
Leurs tests dépendants sont marqués `historical` à la collecte. Sans option,
ils sont ignorés avec un motif explicite. Avec une option, tout artefact requis
manquant fait échouer la vérification.

Trois tests de lecture/rejet du dashboard V8 ont été détachés du registre réel
et utilisent une matrice synthétique en mémoire. Un nouveau test vérifie le
résumé et ses médianes sur les 1 620 cellules. Le test historique de livraison
reste inchangé dans ses assertions scientifiques. Le contrôle de racine du
lanceur borné ne dépend plus du nom `lca-simu-pr40`.

Un contrôle conservé du lanceur a révélé un écart CRLF/LF. Les octets LF de
`launch_supplier_operating_point_full_campaign_v8.py` sont identiques à Git
et retrouvent l'empreinte attendue
`bd8f39d03f97766e193a683076884739bdb72dabcc51fe06b2eadd4e9a146405`.
La copie locale et `.gitattributes` imposent désormais LF pour cette source.
L'empreinte attendue et les résultats historiques restent inchangés.

## Vérification

- Les quatre modules applicatifs concernés, les tests de la politique de
  fixtures et la documentation : **44 réussites, 5 tests historiques ignorés,
  4 sous-tests réussis**, en 11 secondes.
- Dashboard V8 avec `-m "not historical"` : **5 réussites et 1 test exclu**.
- Quatre sessions pytest imbriquées en dossiers temporaires vérifient
  l'absence d'option, une entrée incomplète, une entrée valide et l'exclusion
  par marqueur. Un artefact explicitement requis mais absent produit bien un
  échec, sans masquer l'erreur par un skip.
- `git diff --check` passe. Les sorties documentaires de provenance ont été
  régénérées après ajout du quatrième fichier à la politique LF.

## Suite

Les wrappers PowerShell et les autres fixtures historiques ne sont pas tous
migrés. Le marqueur ne doit donc pas être interprété comme une classification
complète du dépôt. Aucun test historique de campagne n'a été exécuté avec
des artefacts explicitement fournis pendant cette étape, et aucune campagne
n'a été relancée. Le [guide des fixtures](../TEST_FIXTURES.md) précise les
commandes et les dépendances restantes.
