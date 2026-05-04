# Baseline active - MRP physique

Cette baseline est la reference courante pour le scenario MRP avec demande BOM, MPS lotifie, ordres ouverts initiaux et plancher de securite physique.

## Source de verite

- Modele statique: `etudecas/simulation_prep/result/reference_baseline/_mrp_bom_tests/bom_weekly_mps_lotified_no_static_fallback_physical_floor.json`
- Resultats journaliers: `data/*.csv`
- Synthese machine-readable: `summaries/first_simulation_summary.json`
- Rapport humain du run: `reports/first_simulation_report.md`
- Diagnostic d'integrite complet: `reports/baseline_integrity_diagnostic.md`
- Revue scripts/artefacts: `reports/pipeline_artifact_review.md`

## Restitution

- Carte interactive: `maps/supply_graph_mrp_bom_test_weekly_mps_lotified_no_fallback_physical_floor_explicit_input_targets_test.html`
- La carte embarque les series Plotly; aucun dossier `plots` n'est necessaire pour cette baseline.

## Rerun non destructif

Commande de reconstruction officielle sans ecraser la baseline validee:

```powershell
python etudecas/run_etudecas_pipeline.py active-mrp-physical
```

Par defaut, la sortie est creee dans `etudecas/simulation/result/_reruns/active_mrp_physical_<timestamp>`.
La commande embarque la regle validee de cible MRP: base-stock global a 0, puis maintien du base-stock uniquement sur les paires explicites M-1430/M-1810 retenues.

Pour verifier la commande sans lancer le run:

```powershell
python etudecas/run_etudecas_pipeline.py active-mrp-physical --dry-run
```

## Terminologie

- `flux`: couple source -> destination -> item.
- `ordre_flux`: ordre MRP planifie/libere sur un flux.
- `external_procurement*`: realimentation amont fournisseur technique, gardee pour audit mais a separer des vues metier de commande.
- `opening_purchase_order` / `opening_production_order`: ordres ouverts injectes depuis `Extract_En_cours.xlsx`.

## Points d'attention

- Les ordres MRP bruts sont des evenements de simulation journaliers; pour une lecture industrielle, utiliser les vues consolidees semaine/flux/item.
- Le plancher de securite est controle comme objectif MRP/arrivee planifiee. Il ne garantit pas que le stock physique reste toujours au-dessus de la cible a chaque jour.
- La couverture 021081 est tres forte car le stock initial et les ordres ouverts couvrent largement la consommation simulee sur 5 ans.
