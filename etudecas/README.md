# Etudecas

Le point d'entree actif reste :

```powershell
python etudecas/run_etudecas_pipeline.py
```

Pour un usage operationnel sans IA, le chemin recommande est :

```powershell
python -m pip install -r requirements-etudecas.txt
python etudecas/run_etudecas_pipeline.py doctor
python etudecas/run_etudecas_pipeline.py rebuild-map-5y --open-map
```

Sous Windows, le raccourci suivant lance le meme pipeline actif et ouvre la carte :

```powershell
.\run_etudecas_active.cmd
```

Voir [OPERATIONS.md](OPERATIONS.md) pour les options, les fichiers generes et les criteres de validation.

Chaque run operationnel genere aussi un package generique dans `<result>/run/`.
Ce package est le contrat a privilegier pour les futurs viewers, diagnostics,
API de simulation et etudes de sensibilite : il expose `run_manifest.json`,
`nodes.json`, `flows.json`, `kpis.json` et des index vers les artefacts lourds.

Le livrable principal est un graphe JSON de supply chain. La chaine nominale
enrichit ce graphe depuis les donnees cas, le geocode, le prepare pour la
simulation, lance le moteur dynamique, puis genere les cartes et rapports.

## Structure Actuelle

- `data/source/` : fichiers metier source et graphe JSON de base.
- `data/geocoded/` : graphe geocode et rapports de geocodage.
- `data/reports/` : rapports d'enrichissement de donnees.
- `data/MANIFEST.json` : inventaire canonique des donnees actives et des anciens chemins remplaces.
- `geocoding/` : geocodage hors ligne des noeuds.
- `simulation_prep/` : transformation du graphe en entree simulation.
- `knowledge_graph/` : contrat JSON generique, template Excel et enrichissements JSON.
- `simulation/engine/` : moteur de simulation canonique.
- `simulation/lot_trace/` : lecture, indexation, payload et modeles de vue pour le suivi de lots.
- `simulation/analysis/` : audits et analyses post-run.
- `analysis/` : analyses historiques rangees hors du pipeline nominal.
- `simulation/baselines/`, `simulation/scenarios/`, `simulation/sensibility/`, `simulation/montecarlo/` : campagnes et variantes.
- `visualization/maps/` : generation des cartes HTML interactives.
- `config/` : configuration metier du cas actif.
- `risk/` : criticite fournisseur et vues de risque construites depuis la simulation.
- `prototypes/` : POC non nominaux, dont prediction fournisseur sur donnees synthetiques.
- `archive/` : anciens outputs ou cartes conserves pour reference.

## Chemins Compatibles

Ces anciens chemins restent disponibles comme wrappers :

```powershell
python etudecas/simulation/run_first_simulation.py
python etudecas/affichage_supply_script/build_supplychain_worldmap.py
python etudecas/supplier_risk_kpi/build_supplier_risk_kpi.py
```

Les chemins canoniques sont maintenant :

```powershell
python etudecas/simulation/engine/run_first_simulation.py
python etudecas/visualization/maps/build_supplychain_worldmap.py
python etudecas/risk/supplier_criticality/build_supplier_criticality.py
```

## Pipeline Actif

Chaine principale :

- `knowledge_graph/update_supply_graph_from_case_data.py`
- `geocoding/geocode_nodes_offline.py`
- `simulation_prep/prepare_simulation_graph.py`
- `simulation/baselines/rebuild_real_demand_target_baseline.py`
- `simulation_prep/inject_mrp_seed_data_v2.py`
- `simulation/baselines/rebuild_mrp_lot_policy_baseline.py`
- `simulation/engine/run_first_simulation.py`
- `visualization/maps/build_supplychain_worldmap.py`
- `risk/supplier_criticality/build_supplier_criticality.py`

## Usage

Rebatir le run actif 5 ans lotifie, generer la carte autonome et valider les artefacts :

```powershell
python etudecas/run_etudecas_pipeline.py rebuild-map-5y --open-map
```

Ajouter l'incertitude Monte Carlo robuste au run courant :

```powershell
python etudecas/run_etudecas_pipeline.py rebuild-map-5y --with-montecarlo --montecarlo-runs 60 --open-map
```

Verifier les prerequis sans lancer la simulation :

```powershell
python etudecas/run_etudecas_pipeline.py doctor
```

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

Reconstruire la criticite fournisseur utilisee par la carte et les arbres KPI :

```powershell
python etudecas/run_etudecas_pipeline.py supplier-criticality
```

Exporter ou valider le format de run generique depuis un resultat existant :

```powershell
python etudecas/run_etudecas_pipeline.py export-run --output-dir <result_dir>
python etudecas/run_etudecas_pipeline.py validate-run --package-dir <result_dir>/run
```

## Dossiers non nominaux

Les anciens dossiers `SC_*` ont ete ranges dans `analysis/`. Le POC
`Prediction` a ete deplace dans `prototypes/prediction`. Les anciens resultats
`worstcase` et l'ancien HTML `affichage_result` sont dans `archive/`.

Les anciens dossiers `donnees/`, `scripts_geocodage/` et `result_geocodage/`
ont ete remplaces par `data/source`, `data/geocoded`, `data/reports` et
`geocoding`.
Si `donnees/` existe encore localement, il s'agit d'un reliquat ignore par Git,
generalement conserve tant qu'un fichier Excel est ouvert.
