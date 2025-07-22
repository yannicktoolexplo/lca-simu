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
├── dashboard.py                     # Interface Streamlit pour visualiser les résultats
├── optimization/                    # Moteur d’optimisation multi-objectif
├── line_production/                 # Moteur de production par ligne
├── economic/                        # Calcul des coûts fixes, variables, et logistique
├── environment/                     # Moteur ACV (phase production, usage, transport)
├── predictions/                     # Modules prédictifs (demande, rupture, etc.)
├── supply/                          # Gestion de l’approvisionnement
├── scenario_engine.py               # Générateur de scénarios combinés
├── data/                            # Fichiers Excel de demande, coûts, distances...
└── utils/                           # Fonctions communes et outils de visualisation
