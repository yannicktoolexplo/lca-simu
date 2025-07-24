import streamlit as st
import pandas as pd
import plotly.express as px
from sqlalchemy import create_engine
from SimChainGreenHorizons import main_function

# Configuration de la base de données SQLite
DB_PATH = 'sqlite:///simchain.db'
engine = create_engine(DB_PATH)

st.title("📊 Supply Chain Simulator – Dashboard")

# Bouton pour lancer la simulation
if st.button("🚀 Lancer la simulation"):
    with st.spinner("Simulation en cours..."):
        result = main_function()  # Exécuter la simulation complète
        st.success("✅ Simulation terminée !")

        # Afficher les graphiques comparatifs des scénarios
        st.markdown("### 📈 Résultats comparés des scénarios")
        for fig in result["figures"]:
            st.plotly_chart(fig, use_container_width=True)

        # Afficher les graphiques pour le scénario de crise
        st.markdown("### 🚨 Résultats – Scénario de crise")
        for fig in result.get("crisis_figures", []):
            st.plotly_chart(fig, use_container_width=True)

        # Affichage de l'analyse LCA totale pour tous sites (scénario multi-objectifs)
        total_units = int(result["production_totals_sum"])
        st.markdown(f"### 🌍 Analyse du Cycle de Vie – Optimisation Multi-Objectifs ({total_units} sièges, tous sites)")
        st.plotly_chart(result["lca_fig_total"], use_container_width=True)

        # Résultats enregistrés en base de données
        st.markdown("### 📦 Résultats enregistrés dans la base")
        # Attendre un court instant que la base soit mise à jour
        import time; time.sleep(1.0)
        df = pd.read_sql("SELECT * FROM result", con=engine)
        if not df.empty:
            st.dataframe(df)
        else:
            st.warning("❌ Aucune donnée trouvée dans la table `result`.")

        # Calculer les scores de résilience de chaque scénario et les afficher
        df_scores = pd.DataFrame.from_dict({
            name: res.get("resilience_scores", {"supply": 0, "production": 0, "distribution": 0, "total": 0})
            for name, res in result["scenario_results"].items()
        }, orient='index')
        df_scores.loc["Crise"] = result["crisis_result"]["resilience_scores"]
        st.markdown("### 🟦 Scores de résilience par scénario")
        st.dataframe(df_scores)
        # Exemple de visualisation interactive des scores de résilience
        fig_resilience = px.bar(
            df_scores.reset_index(), x="index", y="total", color="index",
            color_discrete_map={name: ("#4895ef" if name != "Crise" else "#e63946") for name in df_scores.index},
            title="Score de résilience par scénario"
        )
        st.plotly_chart(fig_resilience, use_container_width=True)

# Si aucune simulation n'a encore été lancée, afficher le contenu actuel de la base (le cas échéant)
else:
    st.markdown("### 📦 Résultats enregistrés dans la base")
    try:
        df = pd.read_sql("SELECT * FROM result", con=engine)
        if not df.empty:
            st.dataframe(df)
        else:
            st.info("Aucune simulation encore enregistrée.")
    except Exception as e:
        st.error(f"Erreur lors de la lecture de la base : {e}")
