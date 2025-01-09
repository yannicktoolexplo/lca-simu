import requests
import pandas as pd

# Votre clé API FRED
API_KEY = "0f9b43b457facd531052c888f5e9cd50"
BASE_URL = "https://api.stlouisfed.org/fred"

def get_category_series(category_id):
    """
    Récupère les séries d'une catégorie FRED donnée.
    
    :param category_id: ID de la catégorie.
    :return: DataFrame des séries économiques.
    """
    url = f"{BASE_URL}/category/series"
    params = {
        "category_id": category_id,
        "api_key": API_KEY,
        "file_type": "json"
    }
    response = requests.get(url, params=params)
    data = response.json()
    if 'seriess' in data:
        return pd.DataFrame(data['seriess'])
    else:
        raise ValueError(f"Erreur dans la récupération des séries : {data.get('error_message')}")

# ID de la catégorie Durable Goods
durable_goods_category_id = 32312

# Récupérer les séries de la catégorie Durable Goods
durable_goods_series = get_category_series(durable_goods_category_id)

# Sélectionner les colonnes pertinentes
durable_goods_series_display = durable_goods_series[['id', 'title', 'frequency', 'units', 'seasonal_adjustment', 'last_updated']]

# Afficher les séries sous forme de tableau
print(durable_goods_series_display)
