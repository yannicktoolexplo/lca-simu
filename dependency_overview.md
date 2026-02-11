# Aperçu des dépendances internes

## Chaîne de production principale (simulation + optimisation)
- `SimChainGreenHorizons.py` orchestre la production et la résilience en combinant :
  - Moteur d'optimisation (`optimization.optimization_engine`) pour différentes allocations et scénarios multi-objectifs.
  - Paramétrage des lignes et moteur SimPy (`line_production.line_production_settings`, `line_production.line_production`) plus fonctions de cadence (`line_production.production_engine`).
  - Scénarios/événements (`resilience.scenario_engine`, `resilience.event_engine.PerturbationEvent`) et indicateurs de performance/résilience (`resilience.performance_engine`, `resilience.resilience_analysis`, `resilience.resilience_indicators`).
  - Utilitaires de données et visualisations (`tools.data_tools`, `resilience.hybrid_regulation_engine`).
- Les lignes de production importent par défaut le plan d'appro `resilience.supply_network.get_supply_plan` (fallback `supply_light.supply_engine`) pour alimenter `_stock_control` et cadencer les flux matière dans les process SimPy (`line_production/line_production.py`).

## Réseau supply "lightweight" (connecté à la production)
- `resilience/supply_network.py` définit un graphe multi-niveaux par matériau (fournisseur global → hub → site) et expose :
  - `get_supply_plan(site, seat_weight)` qui retourne quantités et temps de livraison par matière.
  - `trace_path` / `route_time_days` pour inspecter les itinéraires et délais.
- `supply_dynamic_sim.py` et `supply_dynamic_cli.py` réutilisent ce plan pour tester un flux matière donné (stock, ruptures) via une simulation journalière simplifiée.
- `supply_chain_sim.py` propose une version SimPy générique (nœuds `SupplyNode`, liens `TransportLink`) utilisée pour instancier rapidement un réseau de test (délais = `lead_time_days`, lot fixe) à partir d'une liste de nœuds.

## Réseau supply "très étendu" basé sur les données GEO (package `supply_geo/`)
- `supply_geo/data_loader_supply.py` charge les enregistrements JSON (ex. `output8_GEO.json`/`supplychain_ultimate_DEDUP.json`), extrait les tiers (matière première, première transformation, tier1) et construit un graphe (nœuds géocodés + arêtes). Des coordonnées sont déduites via table Excel ou centroïdes pays.
- `supply_geo/sim_supply.py` implémente la simulation SimPy au niveau unité (par composant) :
  - capabilité par rôle (`ROLE_CAPACITY`), temps de process (`PROCESSING_TIME_DAYS`), jitter, choix du mode transport (`pick_mode` + distances haversine) puis enchaînement `START_PROC`/`DEPART_x`/`ARRIVE`.
- `run_supply_sim.py` est le glue-code CLI : charge les données via `supply_geo.data_loader_supply`, initialise `supply_geo.sim_supply.simulate_supply`, exécute l'environnement SimPy et exporte les événements/arrivées CSV + graphiques optionnels.
- Les CSV de sortie sont désormais dans `analysis/` (`supply_events.csv`, `supply_arrivals.csv`).

## Jeux de chocs et résilience
- Dossier `shocks/` : scripts et helpers pour comparer des scénarios de chocs (ex. `compare_shocks.py`, `shock_experiments.py`, `shock_suite.py`, `top_shocks.py`, `tornado_shocks.py`, données `chocs.csv`).

## Points de raccord entre ensembles
- La production assise consomme le plan d'appro rapide (`supply_network`) pour alimenter les conteneurs matières dans `line_production`, ce qui permet de brancher directement le réseau multi-niveaux simplifié sur les scénarios/optimisations (`SimChainGreenHorizons`).
- Le pipeline fondé sur `data_loader_supply`/`sim_supply` reste autonome : il se contente d'émettre des CSV et de la visualisation, sans alimenter directement les lignes de production, mais peut servir à calibrer des paramètres (délais, capacités) pour le réseau simplifié.
