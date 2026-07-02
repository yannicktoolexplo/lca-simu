---
name: etudecas-data-knowledge
description: Use when working on Etudecas Excel inputs, JSON case data, graph enrichment, schema validation, geocoding inputs, case_config, source data quality, or knowledge graph contracts.
---

# Etudecas Data Knowledge

## Workflow

1. Treat Excel/JSON case files as source data; do not correct them silently.
2. Produce explicit enrichment reports for any data transformation.
3. Keep schema versions, units, geocoding and case_config consistent.
4. Prefer relative paths in artifacts and manifests.
5. Validate graph structure before simulation.

## Key Files

- Source data: `etudecas/data/source`, `etudecas/config/cases`.
- Knowledge graph: `etudecas/knowledge_graph`.
- Geocoding: `etudecas/geocoding`, `etudecas/data/geocoded`.
- Simulation prep: `etudecas/simulation_prep`.

## Validation

Run fast tests and targeted graph validation:

```powershell
python -B -m unittest discover -s etudecas -p "test*.py"
```
