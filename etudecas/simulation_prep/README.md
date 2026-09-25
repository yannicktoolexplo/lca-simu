# Simulation Prep

Ce dossier convertit le graphe de connaissance en graphe directement executable
par le moteur de simulation.

## Role

- `prepare_simulation_graph.py` : enrichissement simulation-ready depuis le graphe geocode.
- `inject_mrp_seed_data_v2.py` : injection des stocks MRP, tailles de lots et politiques MRP, utilisée par le pipeline.
- `estimate_supplier_capacities.py` : estimation de capacites fournisseur quand elles ne sont pas explicites.

## Resultats

`result/` contient des graphes intermediaires regenerables.

- `result/reference_baseline/` : baseline active utilisee par `run_etudecas_pipeline.py`.
- `result/calibrated_variants/` : variantes de calibration historiques ou comparatives.
- fichiers a la racine de `result/` : sorties anciennes conservees pour compatibilite et audit.

Les nouveaux developpements doivent privilegier `run_etudecas_pipeline.py`
comme entree centrale plutot que de consommer manuellement un vieux JSON de
`result/`.

L'ancien injecteur `inject_mrp_seed_data.py` a été retiré du code courant après
vérification de ses appels : le pipeline utilise V2 et aucune fonction exclusive
à V1 n'a été identifiée. Les deux versions n'ont pas exactement les mêmes règles
de modification du graphe ; aucun relais V1 vers V2 n'est présenté comme équivalent.
V1 reste disponible dans le commit `34c8e5dc3` et la capsule de sources
`config/reproduction_20260920/sources/823e6fcf3ef8f80787f2ecb12a2414666cc2e0ba42be3ab1ba010be414e40f07.zip`
(chemin relatif à `etudecas/`). Les anciens inventaires de sources sont conservés.
