# Etudecas

Le point d'entree actif reste :

```powershell
python etudecas/run_etudecas_pipeline.py
```

Le livrable principal est un graphe JSON de supply chain. La chaine nominale
enrichit ce graphe depuis les donnees cas, le geocode, le prepare pour la
simulation, lance le moteur dynamique, puis genere les cartes et rapports.

## Structure Actuelle

- `donnees/` : ingestion et enrichissement du graphe metier depuis les donnees cas.
- `scripts_geocodage/` : geocodage hors ligne des noeuds.
- `simulation_prep/` : transformation du graphe en entree simulation.
- `knowledge_graph/` : contrat JSON generique, template Excel et enrichissements JSON.
- `simulation/engine/` : moteur de simulation canonique.
- `simulation/lot_trace/` : lecture, indexation, payload et modeles de vue pour le suivi de lots.
- `simulation/analysis/` : audits et analyses post-run.
- `simulation/baselines/`, `simulation/scenarios/`, `simulation/sensibility/`, `simulation/montecarlo/` : campagnes et variantes.
- `visualization/maps/` : generation des cartes HTML interactives.
- `config/` : configuration metier du cas actif.
- `supplier_risk_kpi/` : KPI et criticite fournisseurs.

## Chemins Compatibles

Ces anciens chemins restent disponibles comme wrappers :

```powershell
python etudecas/simulation/run_first_simulation.py
python etudecas/affichage_supply_script/build_supplychain_worldmap.py
```

Les chemins canoniques sont maintenant :

```powershell
python etudecas/simulation/engine/run_first_simulation.py
python etudecas/visualization/maps/build_supplychain_worldmap.py
```

## Pipeline Actif

Chaine principale :

- `donnees/update_supply_graph_from_case_data.py`
- `scripts_geocodage/geocode_nodes_offline.py`
- `simulation_prep/prepare_simulation_graph.py`
- `simulation/baselines/rebuild_real_demand_target_baseline.py`
- `simulation_prep/inject_mrp_seed_data_v2.py`
- `simulation/baselines/rebuild_mrp_lot_policy_baseline.py`
- `simulation/engine/run_first_simulation.py`
- `visualization/maps/build_supplychain_worldmap.py`
- `supplier_risk_kpi/build_supplier_risk_kpi.py`

## Usage

Rebatir tout le pipeline actif 1 an :

```powershell
python etudecas/run_etudecas_pipeline.py all
```

Rebatir aussi la variante 5 ans :

```powershell
python etudecas/run_etudecas_pipeline.py all --with-5y
```

Reconstruire seulement le graphe metier :

```powershell
python etudecas/run_etudecas_pipeline.py graph
```

Lancer la simulation depuis un graphe JSON donne :

```powershell
python etudecas/run_etudecas_pipeline.py simulate --input-graph <graph.json> --output-dir <result_dir>
```

## Legacy

Les dossiers `SC_*`, `Prediction`, `worstcase` et certains scripts historiques
restent disponibles pour comparaison ou compatibilite, mais ne sont plus la voie
nominale de construction de la baseline.
