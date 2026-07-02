# SimChainGreenHorizons

Simulation avancée de chaînes logistiques intégrant performance opérationnelle, économique et environnementale.  
Ce projet fait partie de l’initiative **LCA-SIMU** pilotée par SCALIAN et IMT Mines Albi.

## 🎯 Objectifs

- Simuler une chaîne d’approvisionnement multi-sites avec production, transport, demande, et contraintes opérationnelles
- Intégrer une évaluation de cycle de vie (ACV) pour les phases production, usage et transport
- Permettre des scénarios d’optimisation : économique, environnemental ou multi-critère
- Ajouter des modules de résilience, prédiction, et régulation dynamique (notamment avec une logique "système vivant")

## 📦 Structure du projet

```bash
simchaingreenhorizons/
├── SimChainGreenHorizons.py         # Script principal d'exécution
├── run_supply_sim.py                # Simulation supply géocodée (supply_geo)
├── supply_dynamic_sim.py            # Simu supply légère (basée sur supply_network)
├── resilience/                      # Événements, scénarios, résilience, supply_network léger
├── supply_geo/                      # Simulation supply étendue géocodée
├── supply_light/                    # Graphe supply léger (utilisé par supply_dynamic_sim)
├── optimization/                    # Moteur d’optimisation multi-objectif
├── line_production/                 # Moteur de production par ligne
├── economic/                        # Calcul des coûts fixes, variables, et logistique
├── environment/                     # Moteur ACV (phase production, usage, transport)
├── predictions/                     # Modules prédictifs (demande, rupture, etc.)
├── tools/                           # Outils/CLI/visualisations (data_tools, plots…)
├── supply_geo/analysis/             # Données, cartes et archives de l'analyse supply geo
├── data/                            # Fichiers Excel/JSON/DB (demande, coûts, GEO, simchain.db)
└── utils/                           # Fonctions communes et outils de visualisation
