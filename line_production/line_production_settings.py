# line_production_settings.py

from event_engine import PerturbationEvent

scenario_events = {
    "baseline": [],
    "crise": [
        # Exemples : panne en France, et rupture aluminium 
        PerturbationEvent(time=10, target="France", event_type="panne", magnitude=1.0, duration=100, description="Panne longue France"),
        PerturbationEvent(time=20, target="aluminium", event_type="rupture_fournisseur", magnitude=1.0, duration=200, description="Rupture aluminium")
    ],
    "surcapacite": [
        # Par exemple, sur-demande qui pousse temporairement la production au-delà de la capacité nominale
        # (On simule en fait une augmentation de capacité requise, ce qui pourrait être interprété par magnitude < 0 pour signifier +50% de capacité ?)
        # Ici on n'affecte pas directement la production_line mais on pourrait utiliser cet événement au niveau allocation.
    ],
    "vivant": [
        # On peut reprendre l'exemple d'événements vivants déjà défini
        PerturbationEvent(time=20, target="France", event_type="panne", magnitude=1.0, duration=5, description="Arrêt total France"),
        PerturbationEvent(time=50, target="aluminium", event_type="rupture_fournisseur", magnitude=1.0, duration=10, description="Plus d'aluminium")
    ],
    "shock_supply": [
        PerturbationEvent(
            time=10, target="aluminium", event_type="rupture_fournisseur",
            magnitude=1.0, duration=100, description="Rupture critique d’aluminium"
        )
    ],
    "shock_production": [
        PerturbationEvent(
            time=10, target="Texas", event_type="panne",
            magnitude=1.0, duration=100, description="Panne usine Texas"
        )
    ],
    "shock_distribution": [
        PerturbationEvent(
            time=10, target="aluminium", event_type="retard",
            magnitude=8, duration=100, description="Retard logistique majeur"
        )
    ],
}


# Configuration de plusieurs lignes de production
lines_config = [
    {   'location': 'Texas',  # Grand centre de production
        'hours': 8,
        'days': 30,
        'total_time': 240,  # En heures
        'aluminium_capacity': 1000,
        'initial_aluminium': 100,
        'foam_capacity': 900,
        'initial_foam': 700,
        'fabric_capacity': 1000,
        'initial_fabric': 800,
        'paint_capacity': 500,
        'initial_paint': 400,
        'dispatch_capacity': 1200,
        'frame_pre_paint_capacity': 150,
        'armrest_pre_paint_capacity': 150,
        'frame_post_paint_capacity': 300,
        'armrest_post_paint_capacity': 300,
        'aluminium_critial_stock': 200,
        'foam_critical_stock': 180,
        'fabric_critical_stock': 200,
        'paint_critical_stock': 100,
        'num_frame': 10,
        'mean_frame': 0.8,
        'std_frame': 0.1,
        'num_armrest': 8,
        'mean_armrest': 0.9,
        'std_armrest': 0.1,
        'num_paint': 6,
        'mean_paint': 1.5,
        'std_paint': 0.2,
        'num_ensam': 12,
        'mean_ensam': 0.9,
        'std_ensam': 0.2
    },
    {   'location': 'California',  # Production moyenne
        'hours': 8,
        'days': 21,
        'total_time': 168,  # En heures
        'aluminium_capacity': 500,
        'initial_aluminium': 100,
        'foam_capacity': 450,
        'initial_foam': 300,
        'fabric_capacity': 500,
        'initial_fabric': 350,
        'paint_capacity': 250,
        'initial_paint': 200,
        'dispatch_capacity': 600,
        'frame_pre_paint_capacity': 80,
        'armrest_pre_paint_capacity': 80,
        'frame_post_paint_capacity': 140,
        'armrest_post_paint_capacity': 140,
        'aluminium_critial_stock': 100,
        'foam_critical_stock': 90,
        'fabric_critical_stock': 100,
        'paint_critical_stock': 50,
        'num_frame': 5,
        'mean_frame': 1,
        'std_frame': 0.1,
        'num_armrest': 4,
        'mean_armrest': 1,
        'std_armrest': 0.2,
        'num_paint': 3,
        'mean_paint': 1.8,
        'std_paint': 0.25,
        'num_ensam': 7,
        'mean_ensam': 1,
        'std_ensam': 0.2
    },
    {   'location': 'France',  # Production spécialisée
        'hours': 8,
        'days': 21,
        'total_time': 168,  # En heures
        'aluminium_capacity': 400,
        'initial_aluminium': 100,
        'foam_capacity': 400,
        'initial_foam': 300,
        'fabric_capacity': 400,
        'initial_fabric': 300,
        'paint_capacity': 200,
        'initial_paint': 150,
        'dispatch_capacity': 500,
        'frame_pre_paint_capacity': 60,
        'armrest_pre_paint_capacity': 60,
        'frame_post_paint_capacity': 120,
        'armrest_post_paint_capacity': 120,
        'aluminium_critial_stock': 80,
        'foam_critical_stock': 80,
        'fabric_critical_stock': 80,
        'paint_critical_stock': 40,
        'num_frame': 4,
        'mean_frame': 1.1,
        'std_frame': 0.1,
        'num_armrest': 4,
        'mean_armrest': 1.1,
        'std_armrest': 0.1,
        'num_paint': 3,
        'mean_paint': 2,
        'std_paint': 0.3,
        'num_ensam': 6,
        'mean_ensam': 1.2,
        'std_ensam': 0.2
    },
    {   'location': 'UK',  # Production secondaire
        'hours': 8,
        'days': 21,
        'total_time': 168,  # En heures
        'aluminium_capacity': 350,
        'initial_aluminium': 100,
        'foam_capacity': 350,
        'initial_foam': 250,
        'fabric_capacity': 350,
        'initial_fabric': 250,
        'paint_capacity': 180,
        'initial_paint': 120,
        'dispatch_capacity': 450,
        'frame_pre_paint_capacity': 50,
        'armrest_pre_paint_capacity': 50,
        'frame_post_paint_capacity': 100,
        'armrest_post_paint_capacity': 100,
        'aluminium_critial_stock': 60,
        'foam_critical_stock': 60,
        'fabric_critical_stock': 60,
        'paint_critical_stock': 30,
        'num_frame': 3,
        'mean_frame': 1.2,
        'std_frame': 0.1,
        'num_armrest': 3,
        'mean_armrest': 1.2,
        'std_armrest': 0.2,
        'num_paint': 2,
        'mean_paint': 2.2,
        'std_paint': 0.3,
        'num_ensam': 5,
        'mean_ensam': 1.3,
        'std_ensam': 0.2
    }
]
