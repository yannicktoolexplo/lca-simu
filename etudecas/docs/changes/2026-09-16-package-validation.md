# Validation physique des packages — 16 septembre 2026

## Problème et correction

Le validateur utilisait les déclarations `exists` et `row_count` de l'index
sans contrôler les fichiers correspondants. Il pouvait accepter un résultat
incomplet ou corrompu ; certains JSON invalides provoquaient aussi une exception
au lieu d'un diagnostic. La commande d'export retournait un succès malgré des
contrôles en échec.

Le validateur vérifie désormais les fichiers, la structure des CSV, les nombres
de lignes, les index par groupe, les identifiants et les liens entre nœuds et
flux. Les trois artefacts obligatoires sont imposés à partir du schéma.
Les erreurs de lecture ordinaires deviennent des contrôles en échec. L'export
retourne 1 si son package échoue à la validation.

Le [contrat détaillé](../../simulation/run_format/README.md) précise les limites.
Deux nouvelles règles documentaires relient ce contrat aux symboles Python et
aux tests ; leur mise à jour suit le même mécanisme d'empreintes que le pilote
expéditions/lots/risques. Aucun résultat historique n'a été régénéré.

## Vérification

- `python -m pytest etudecas/simulation etudecas/documentation -q --disable-warnings --tb=short` :
  **391 tests réussis, 2 ignorés, 47 sous-tests réussis**, en 89 secondes.
- `python -m unittest discover -s etudecas -p "test*.py"` :
  **269 tests exécutés, résultat OK, 2 ignorés**.
- Les deux contrôles documentaires `check` passent ; `git diff --check` passe.
- Quatre tests de régression exécutés contre le validateur de `HEAD` produisent
  les neuf échecs attendus, sans erreur d'exécution : fichier requis supprimé,
  six CSV altérés, flux vers un nœud inconnu et index de lots incohérent.

Le périmètre testé n'est pas tout le dépôt. Les échecs de prototypes et de
provenance identifiés dans l'audit initial ne sont pas résolus par cette étape.

## Suite du plan

Le pilote documentaire, la correction des identifiants d'expédition et le
durcissement des packages sont livrés localement avec leurs tests. La prochaine
priorité est de rendre les jeux de référence reproductibles et de traiter les
écarts de provenance, en distinguant les variations de fins de ligne des
changements de contenu. Les empreintes scientifiques ne doivent pas être
réacceptées globalement pour masquer ces écarts.
