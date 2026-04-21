# Etudecas

Le point d’entrée actif est maintenant :

- [run_etudecas_pipeline.py](C:/dev/lca-simu/etudecas/run_etudecas_pipeline.py)

L’idée directrice est simple :

1. le livrable principal est un **graphe JSON de supply chain**
2. ce graphe est enrichi depuis les `xlsx`
3. il est préparé pour la simulation
4. la simulation et la map se construisent à partir de ce graphe

## Pipeline actif

Chaîne principale :

- [update_supply_graph_from_case_data.py](C:/dev/lca-simu/etudecas/donnees/update_supply_graph_from_case_data.py)
- [geocode_nodes_offline.py](C:/dev/lca-simu/etudecas/scripts_geocodage/geocode_nodes_offline.py)
- [prepare_simulation_graph.py](C:/dev/lca-simu/etudecas/simulation_prep/prepare_simulation_graph.py)
- [rebuild_real_demand_target_baseline.py](C:/dev/lca-simu/etudecas/simulation/baselines/rebuild_real_demand_target_baseline.py)
- [inject_mrp_seed_data_v2.py](C:/dev/lca-simu/etudecas/simulation_prep/inject_mrp_seed_data_v2.py)
- [rebuild_mrp_lot_policy_baseline.py](C:/dev/lca-simu/etudecas/simulation/baselines/rebuild_mrp_lot_policy_baseline.py)
- [run_first_simulation.py](C:/dev/lca-simu/etudecas/simulation/run_first_simulation.py)
- [build_supplychain_worldmap.py](C:/dev/lca-simu/etudecas/affichage_supply_script/build_supplychain_worldmap.py)

Artefacts de référence actifs :

- [supply_graph_reference_baseline_simulation_ready.json](C:/dev/lca-simu/etudecas/simulation_prep/result/reference_baseline/supply_graph_reference_baseline_simulation_ready.json)
- [supply_graph_reference_baseline_real_demand_target_calibrated.json](C:/dev/lca-simu/etudecas/simulation_prep/result/reference_baseline/supply_graph_reference_baseline_real_demand_target_calibrated.json)
- [supply_graph_reference_baseline_real_demand_target_calibrated_mrp_lot_policy.json](C:/dev/lca-simu/etudecas/simulation_prep/result/reference_baseline/supply_graph_reference_baseline_real_demand_target_calibrated_mrp_lot_policy.json)
- [supply_graph_reference_baseline_real_demand_target_calibrated_mrp_lot_policy_recalibrated.json](C:/dev/lca-simu/etudecas/simulation_prep/result/reference_baseline/supply_graph_reference_baseline_real_demand_target_calibrated_mrp_lot_policy_recalibrated.json)
- [supply_graph_reference_baseline_real_demand_target_calibrated_mrp_lot_policy_recalibrated_5y.json](C:/dev/lca-simu/etudecas/simulation_prep/result/reference_baseline/supply_graph_reference_baseline_real_demand_target_calibrated_mrp_lot_policy_recalibrated_5y.json)

## Usage

Rebâtir tout le pipeline actif 1 an :

```powershell
python etudecas/run_etudecas_pipeline.py all
```

Rebâtir aussi la variante 5 ans :

```powershell
python etudecas/run_etudecas_pipeline.py all --with-5y
```

Reconstruire seulement le graphe métier :

```powershell
python etudecas/run_etudecas_pipeline.py graph
```

Lancer la simulation depuis un graphe JSON donné :

```powershell
python etudecas/run_etudecas_pipeline.py simulate --input-graph <graph.json> --output-dir <result_dir>
```

## Scripts legacy ou secondaires

Ces scripts ne sont plus dans la chaîne principale, mais restent disponibles pour étude ou compatibilité :

- [inject_mrp_seed_data.py](C:/dev/lca-simu/etudecas/simulation_prep/inject_mrp_seed_data.py)
- [estimate_supplier_capacities.py](C:/dev/lca-simu/etudecas/simulation_prep/estimate_supplier_capacities.py)
- dossiers `SC_*`, `Prediction`, `worstcase`
- scripts de sensibilité, Monte Carlo et scénarios spécifiques dans [simulation](C:/dev/lca-simu/etudecas/simulation)

Le principe est de ne plus considérer ces scripts comme la voie nominale de construction de la baseline.
