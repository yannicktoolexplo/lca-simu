# Profil des sources Etudecas

- Fichiers inventoriés: 14
- Fichiers métier de référence: 5
- Fichiers manquants: 0

## Synthèse

| Fichier | Type | Lignes | Colonnes | Période | Rôle |
|---|---:|---:|---:|---|---|
| 021081.xlsx | xlsx | n/a | 0 | n/a | source canonique |
| 268191.xlsx | xlsx | n/a | 0 | n/a | source canonique |
| 268967.xlsx | xlsx | n/a | 0 | n/a | source canonique |
| Data_poc.xlsx | xlsx | n/a | 0 | n/a | source canonique |
| demand_PF.xlsx | xlsx | n/a | 0 | n/a | source canonique |
| Extract_En_cours.xlsx | xlsx | n/a | 0 | n/a | source canonique |
| Fournisseur.xlsx | xlsx | n/a | 0 | n/a | source canonique |
| Stocks_MRP.xlsx | xlsx | n/a | 0 | n/a | source canonique |
| CA_Perdu_Réel.csv | csv | 522 | 5 | 2025-01-01 -> 2025-12-31 | Historique CA livre/perdu par produit et date de livraison. |
| Dispo_PF_Projeté.csv | csv | 64 | 4 | 2025|01 -> 2026|26 | Ruptures produit fini projetees par semaine. |
| Stock_Composants_Immobilisé_Cos.csv | csv | 52 | 2 | 2025-01-06 -> 2025-12-29 | Valeur de stock composants immobilise cosmetique. |
| Stock_Composants_Immobilisé_Pharma.csv | csv | 52 | 2 | 2025-01-06 -> 2025-12-29 | Valeur de stock composants immobilise pharma. |
| Stock_PF_Immobilisé.csv | csv | 104 | 3 | 2025-01-06 -> 2025-12-29 | Valeur de stock produits finis immobilise par article. |
| supply_graph_poc.json | json | n/a | 0 | n/a | source canonique |

## Fichiers métier de référence

### CA_Perdu_Réel.csv

- Rôle: Historique CA livre/perdu par produit et date de livraison.
- Usage prévu: Validation service client, pertes de CA et comparaison simulation/reel.
- Mesure: n/a
- Lignes: 522
- Colonnes: Product code, First delivery date, CA_Livré, CA_Perdu, Nb_Rep_CA_Perdu

| Colonne numérique | Min | Max | Somme |
|---|---:|---:|---:|
| CA_Livré | 0 | 800 424.4 | 43 430 514.5 |
| CA_Perdu | -45.9 | 206 969.9 | 2 693 384.8 |
| Nb_Rep_CA_Perdu | 0 | 1 | 255 |

### Dispo_PF_Projeté.csv

- Rôle: Ruptures produit fini projetees par semaine.
- Usage prévu: Validation disponibilite produit et signal de tension PF.
- Mesure: n/a
- Lignes: 64
- Colonnes: SKU Code, Year Week Snapshot, Nb_Semaine_Rupture_Produit, Répétition_Rupture_Produit

| Colonne numérique | Min | Max | Somme |
|---|---:|---:|---:|
| Nb_Semaine_Rupture_Produit | 0 | 11 | 108 |
| Répétition_Rupture_Produit | 0 | 6 | 79 |

### Stock_Composants_Immobilisé_Cos.csv

- Rôle: Valeur de stock composants immobilise cosmetique.
- Usage prévu: Validation cout de stockage / immobilisation composants.
- Mesure: stock_value
- Lignes: 52
- Colonnes: Date de photo DMP, Sum_Valeur totale du stock
- Périmètre produit: domaine cos; PF 268967; item:268967; Composants rattaches au BOM du produit fini 268967.
- Comparaison simulation: Comparer au stock simule des composants du BOM 268967 apres valorisation par les prix composants disponibles sur les liens fournisseur-usine. Controler les prix a zero, les composants internes et les cas multi-sources avant comparaison.

| Colonne numérique | Min | Max | Somme |
|---|---:|---:|---:|
| Sum_Valeur totale du stock | 606 978.6 | 1 435 465.2 | 48 396 151.0 |

### Stock_Composants_Immobilisé_Pharma.csv

- Rôle: Valeur de stock composants immobilise pharma.
- Usage prévu: Validation cout de stockage / immobilisation composants.
- Mesure: stock_value
- Lignes: 52
- Colonnes: Date de photo DMP, Sum_Valeur totale du stock
- Périmètre produit: domaine pharma; PF 268091; item:268091; Composants rattaches au BOM du produit fini 268091.; Hypothese: Le code mentionne comme 26809 est interprete comme 268091, produit fini present dans le graphe et la simulation.
- Comparaison simulation: Comparer au stock simule des composants du BOM 268091 apres valorisation par les prix composants disponibles sur les liens fournisseur-usine. Controler les prix a zero, les composants internes et les cas multi-sources avant comparaison.

| Colonne numérique | Min | Max | Somme |
|---|---:|---:|---:|
| Sum_Valeur totale du stock | 181 337.7 | 382 654.0 | 13 503 276.8 |

### Stock_PF_Immobilisé.csv

- Rôle: Valeur de stock produits finis immobilise par article.
- Usage prévu: Validation cout de stockage PF et dynamique de stock.
- Mesure: stock_value
- Lignes: 104
- Colonnes: Numéro article, Date de photo DMP, Sum_Valeur totale du stock
- Périmètre produit: PF 268967, 268091; item:268967, item:268091; Stocks immobilises de produits finis par article.
- Comparaison simulation: Comparer aux stocks PF simules par article/site apres valorisation avec les memes conventions de cout.

| Colonne numérique | Min | Max | Somme |
|---|---:|---:|---:|
| Sum_Valeur totale du stock | 215 293.3 | 2 472 794.0 | 100 745 429.1 |
