# Simulation Prep

Ce dossier convertit le graphe de connaissance en graphe directement executable
par le moteur de simulation.

## Role

- `prepare_simulation_graph.py` : enrichissement simulation-ready depuis le graphe geocode.
- `inject_mrp_seed_data.py` / `inject_mrp_seed_data_v2.py` : injection des stocks MRP, tailles de lots et politiques MRP.
- `estimate_supplier_capacities.py` : estimation de capacites fournisseur quand elles ne sont pas explicites.

## Resultats

`result/` contient des graphes intermediaires regenerables.

- `result/reference_baseline/` : baseline active utilisee par `run_etudecas_pipeline.py`.
- `result/calibrated_variants/` : variantes de calibration historiques ou comparatives.
- fichiers a la racine de `result/` : sorties anciennes conservees pour compatibilite et audit.

Les nouveaux developpements doivent privilegier `run_etudecas_pipeline.py`
comme entree centrale plutot que de consommer manuellement un vieux JSON de
`result/`.

