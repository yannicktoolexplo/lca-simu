# Rapprochement des coûts arrondis

Le vérificateur compare les sommes des CSV aux résumés avec une borne dérivée de l'export moteur, sans modifier la simulation ni la carte.

Les montants sont exportés à quatre décimales. Chaque arrondi représente au plus `0,00005` unité monétaire. Le total opérationnel journalier additionne cinq postes déjà arrondis (achat, transport, possession, fonctionnement d'entrepôt, risque de stock), puis arrondit leur somme avec la production encore non arrondie. Le résumé est arrondi séparément : pour `N` jours, la borne est `(6 × N + 1) × 0,00005`. Pour l'approvisionnement externe, deux colonnes journalières sont arrondies séparément : `(2 × N + 1) × 0,00005`.

Sur 1 825 jours, ces bornes valent respectivement `0,54755` et `0,18255`. Les écarts constatés sont `0,0378` et `0,0112` pour le nominal ; `0,0404` et `0,0035` pour les risques. Ce sont des écarts compatibles avec l'arrondi, pas une preuve que tout écart sous la borne provient nécessairement d'un arrondi.

Les comparaisons utilisent `Decimal`. Une précision inattendue, une valeur non finie, des jours manquants ou dupliqués sont refusés. Les 36 tests du vérificateur passent, notamment les limites de la borne, un écart de 1 sur 1 825 jours, les corruptions de résumé et les coûts de mauvais périmètre. Le premier rapport de refus reste conservé ; [final-map-delivery-v2.json](../../artifacts/testing/audit_corrections_20260920/final-map-delivery-v2.json) publie les écarts, bornes, nombres de termes et empreintes CSV.

Références vérifiées : `run_first_simulation.py`, construction de `daily_rows`, calcul de `total_supply_cost_day` et des `kpis`. Un changement de précision ou de formule exige une nouvelle revue de cette borne. Cette vérification ne certifie ni les prix sources ni une valorisation industrielle complète.
