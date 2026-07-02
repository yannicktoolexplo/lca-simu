# Knowledge Graph

Ce package formalise le flux generique :

```text
donnees brutes
  -> graphe de connaissance JSON
  -> classeur Excel d'enrichissement
  -> graphe JSON enrichi
  -> simulation / analyse / visualisation
```

## Contrat

Le graphe JSON reste le contrat central entre les modules.

Entites principales :

- `nodes` : acteurs supply-chain.
- `edges` : flux possibles entre acteurs.
- `items` : articles, matieres, semi-finis, produits finis.
- `nodes[].processes` : nomenclatures et transformations de production.
- `nodes[].inventory` : stocks initiaux ou etats de stock.
- `scenarios` : demande, horizon et politiques de simulation.
- `case_config` : hypotheses metier et visualisation.

## Excel

Le classeur generique contient les feuilles :

- `nodes`
- `items`
- `edges`
- `bom`
- `initial_inventory`
- `demand`
- `risks`
- `logistics`
- `case_config`

Les cellules vides ne suppriment pas les donnees existantes.

## Commandes

Creer un classeur Excel depuis un graphe existant :

```powershell
python -m etudecas.knowledge_graph.enrich_graph_from_excel `
  --input-json etudecas/simulation_prep/result/reference_baseline/_mrp_bom_tests/bom_weekly_mps_lotified_no_static_fallback_physical_floor.json `
  --case-config-json etudecas/config/cases/data_poc.json `
  --excel etudecas/config/cases/data_poc_enrichment_input.xlsx `
  --create-template
```

Appliquer le classeur au graphe :

```powershell
python -m etudecas.knowledge_graph.enrich_graph_from_excel `
  --input-json <graph.json> `
  --excel etudecas/config/cases/data_poc_enrichment_input.xlsx `
  --output-json <graph_enriched.json> `
  --report-json <report.json> `
  --apply
```

La meme operation est aussi exposee depuis l'entree centrale :

```powershell
python etudecas/run_etudecas_pipeline.py enrich-graph `
  --input-json <graph.json> `
  --case-config-json etudecas/config/cases/data_poc.json `
  --excel etudecas/config/cases/data_poc_enrichment_input.xlsx `
  --output-json <graph_enriched.json> `
  --report-json <report.json> `
  --create-template `
  --apply
```
