import pandas as pd
from geopy.geocoders import Nominatim
from geopy.extra.rate_limiter import RateLimiter
import time

# === CONFIGURATION ===
INPUT_FILE = "geocoding_table.xlsx"           # fichier source
OUTPUT_FILE = "geocoding_table_filled.xlsx"   # fichier de sortie
USER_AGENT = "supplychain_geocoder_safran"    # identifiant pour Nominatim

# === INITIALISATION ===
print("Chargement du fichier Excel...")
df = pd.read_excel(INPUT_FILE)

# Vérification des colonnes attendues
expected_cols = {"Société", "Pays", "Rôle", "Latitude", "Longitude"}
missing = expected_cols - set(df.columns)
if missing:
    raise ValueError(f"Colonnes manquantes dans le fichier Excel : {missing}")

geolocator = Nominatim(user_agent=USER_AGENT)
geocode = RateLimiter(geolocator.geocode, min_delay_seconds=1, swallow_exceptions=True)

# === GÉOCODAGE ===
coords = []
for i, row in df.iterrows():
    name = str(row["Société"]).strip()
    country = str(row["Pays"]).strip()
    query = f"{name}, {country}" if country != "Inconnu" else name
    print(f"[{i+1}/{len(df)}] Géocodage : {query}")
    location = None
    try:
        location = geocode(query)
    except Exception as e:
        print(f"  ⚠️ Erreur : {e}")
    if location:
        df.at[i, "Latitude"] = location.latitude
        df.at[i, "Longitude"] = location.longitude
    else:
        df.at[i, "Latitude"] = ""
        df.at[i, "Longitude"] = ""
    time.sleep(0.2)

# === EXPORT FINAL ===
print("Sauvegarde du fichier complété...")
df.to_excel(OUTPUT_FILE, index=False)
print(f"✅ Fichier créé : {OUTPUT_FILE}")
