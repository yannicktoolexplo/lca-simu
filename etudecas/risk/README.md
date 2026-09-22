# Risk

Ce dossier regroupe les briques qui transforment les sorties de simulation en
lectures de risque, criticite ou priorisation.

- `supplier_criticality/` : criticite fournisseur et KPI fournisseur-article-site.
- `supplier_criticality/local.py` : calcul de criticité locale partagé par le
  pipeline et la carte, extrait du constructeur HTML sans changer ses formules.
  Ce module ne dépend pas de `visualization/`.
