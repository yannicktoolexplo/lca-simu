# Liste des fournisseurs pour chaque matériau, avec localisation et distances vers chaque site.
suppliers = {
    'aluminium': [
        {'name': 'Constellium', 'location': 'France', 'distance_to_sites': {'Texas': 8000, 'California': 8200, 'France': 200,  'UK': 500}},
        {'name': 'Arconic',     'location': 'USA',    'distance_to_sites': {'Texas': 2000, 'California': 3000, 'France': 8500, 'UK': 9000}},
        {'name': 'Norsk Hydro', 'location': 'Norway', 'distance_to_sites': {'Texas': 7500, 'California': 8000, 'France': 1500, 'UK': 1200}}
    ],
    'fabric': [
        {'name': 'Toray Industries', 'location': 'Japan', 'distance_to_sites': {'Texas': 11000, 'California': 10500, 'France': 9400, 'UK': 9100}},
        {'name': 'Hexcel',           'location': 'USA',   'distance_to_sites': {'Texas': 1000,  'California': 2500,  'France': 8500, 'UK': 8700}}
    ],
    'polymers': [
        {'name': 'Sabic', 'location': 'Saudi Arabia', 'distance_to_sites': {'Texas': 13000, 'California': 12500, 'France': 4500, 'UK': 4200}},
        {'name': 'BASF',  'location': 'Germany',      'distance_to_sites': {'Texas': 9500,  'California': 9800,  'France': 300,  'UK': 600}}
    ],
    'paint': [
        {'name': 'PPG Industries',      'location': 'USA',        'distance_to_sites': {'Texas': 2000,  'California': 3000,  'France': 8500, 'UK': 8700}},
        {'name': 'AkzoNobel',           'location': 'Netherlands','distance_to_sites': {'Texas': 7500,  'California': 8000,  'France': 1000, 'UK': 500}},
        {'name': 'Sherwin-Williams',    'location': 'USA',        'distance_to_sites': {'Texas': 1500,  'California': 2000,  'France': 9000, 'UK': 9200}},
        {'name': 'Axalta Coating Systems', 'location': 'Germany','distance_to_sites': {'Texas': 9500,  'California': 9800,  'France': 300,  'UK': 600}}
    ]
}
