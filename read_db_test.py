from sqlalchemy import create_engine

url = __import__("os").environ["LCA_SIMU_DATABASE_URL"]
engine = create_engine(url)

try:
    with engine.connect() as conn:
        print("✅ Connexion réussie à Supabase via Session Pooler (IPv4)")
except Exception as e:
    print("❌ Échec :", e)
