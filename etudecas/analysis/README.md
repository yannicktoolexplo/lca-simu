# Analyses antérieures et entrées compatibles

[Organisation du projet](../README.md)

Les trois rapports utilisés par le pipeline ont été déplacés dans
[`simulation/analysis/`](../simulation/analysis/). Leurs anciens fichiers
de `from_simulation/` restent des relais d'import et de ligne de commande :

- `report_component_immobilized_stock.py` ;
- `report_finished_goods_stock_value.py` ;
- `audit_source_truth_alignment.py`.

Le pipeline importe directement leurs nouvelles implémentations. Les sources
de données et les destinations de sortie par défaut ont été conservées.
Ces rapports rapprochent des sorties du moteur et des données métier. `first_pass/`
contient une ancienne analyse structurelle du graphe. La présence d'autres
scripts dans `from_simulation/` ne suffit pas à établir leur usage actuel.

Modifier les rapports dans `simulation/analysis/`, pas dans les relais.
Les autres analyses et leurs résultats historiques restent à leur emplacement ;
leur présence dans ce dossier n'autorise pas leur suppression en bloc.
