from sqlalchemy import create_engine

url = "postgresql://postgres.xoanqzocbsvphbuwcurm:Gvzt6713071987!@aws-0-eu-west-3.pooler.supabase.com:5432/postgres"
engine = create_engine(url)

try:
    with engine.connect() as conn:
        print("✅ Connexion réussie à Supabase via Session Pooler (IPv4)")
except Exception as e:
    print("❌ Échec :", e)
