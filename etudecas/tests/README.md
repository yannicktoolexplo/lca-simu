# Tests du cœur Etudecas

Les 70 fichiers auparavant placés directement dans `etudecas/`,
`etudecas/simulation/` et `etudecas/visualization/maps/` sont regroupés ici.
Leurs contrôles sont conservés.

| Dossier | Ce qu'il vérifie |
|---|---|
| `commun/` | Écriture des fichiers, provenance, références, pipeline et exports |
| `moteur/` | Paramètres, état initial, demande, décisions et exécution du moteur |
| `lots/` | Production, lotification, généalogie, stocks et données du suivi |
| `risques/` | Impacts sur les lots et conventions des risques fournisseur |
| `analyses/` | Indicateurs, aide à la décision et études de sensibilité |
| `cartes/` | Données affichées, graphiques, onglets et interactions de la carte |

Depuis la racine du dépôt :

```powershell
# Tous les tests regroupés ici.
python -B -m pytest etudecas/tests -q
# Un thème.
python -B -m pytest etudecas/tests/lots -q
# Un fichier, avec manifeste de vérification.
python -B -m etudecas.toolbox tests --path etudecas/tests/lots/test_lot_ledger.py
# Suite de référence, incluant aussi les tests des autres modules.
python -B -m pytest -c pytest-reference.ini
```

Ces tests s'exécutent séparément des simulations courantes. Certains créent de
petits calculs réels ; d'autres vérifient une fonction sur des données fabriquées
pour connaître exactement le résultat attendu.

Les tests des sous-modules spécialisés restent près de ces sous-modules.
`etudecas/testing/` contient les outils de qualification, de comparaison et de
contrôle du navigateur, ainsi que leurs propres tests. Les anciennes preuves
datées conservent les chemins valides au moment de leur exécution.
