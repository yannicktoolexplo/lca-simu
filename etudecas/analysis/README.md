# Analyses spécialisées

[Organisation du projet](../README.md)

Les trois rapports utilisés par le pipeline sont dans
[`simulation/analysis/`](../simulation/analysis/). Utiliser ces modules directement :

- `report_component_immobilized_stock.py` ;
- `report_finished_goods_stock_value.py` ;
- `audit_source_truth_alignment.py`.

Le pipeline importe directement leurs nouvelles implémentations. Les sources
de données et les destinations de sortie par défaut ont été conservées.
Ces rapports rapprochent des sorties du moteur et des données métier.

Deux outils complémentaires restent dans `from_simulation/` :

- `build_observed_2025_supply_bilan.py` produit le bilan des observations ;
- `audit_order_book_vs_source.py` compare les commandes aux données sources.

Le test du bilan observé reste à côté de son implémentation.

Les trois anciens relais de `from_simulation/` ont été retirés après migration
des appels et tests. Modifier les rapports dans `simulation/analysis/`.
Quinze investigations ponctuelles par article ont quitté le code actif le
25 septembre 2026. Leurs sources exactes restent dans la capsule
`config/reproduction_20260920/sources/347f4a298c6e11027db7a40513f44abebc8060daec05bb19e75ea2b11e5e4c78.zip`.
Le bilan observé peut encore lire leurs résultats historiques optionnels,
explicitement non validés ; ils ne constituent pas une calibration du modèle
courant. Les anciens CSV conservés comme entrées ne sont pas supprimés ici.
