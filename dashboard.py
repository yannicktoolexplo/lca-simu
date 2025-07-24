import streamlit as st
from sqlalchemy import create_engine
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from SimChainGreenHorizons import main_function
import plotly.express as px
from line_production.line_production_settings import lines_config

# Connexion à la base locale SQLite
engine = create_engine('sqlite:///simchain.db')

st.title("📊 Supply Chain Simulator – Dashboard")

# Bouton de simulation
if st.button("🚀 Lancer la simulation"):
    with st.spinner("Simulation en cours..."):
        result = main_function()  # ✅ figures, lca_fig, vivant_raw_data

        figures = result["figures"]
        st.success("✅ Simulation terminée !")

        st.markdown("### 📈 Résultats comparés des scénarios")
        for fig in figures:
            st.plotly_chart(fig, use_container_width=True)

        st.markdown("### 🚨 Résultats – scénario de crise")
        for fig in result.get("crisis_figures", []):
            st.plotly_chart(fig, use_container_width=True)

        # Affichage LCA totale tous sièges et tous pays/sites
        st.markdown(f"### 🌍 Analyse du Cycle de Vie : Optimisation Multiobjectifs – **{int(result['production_totals_sum'])} sièges, tous sites**")
        st.plotly_chart(result["lca_fig_total"], use_container_width=True)

        # --- Résultats, figures, etc. ---
        scenario_results = result["scenario_results"]
        crisis_result = result["crisis_result"]



        # 🔁 Attente courte pour laisser le temps d’écrire dans la base
        import time
        time.sleep(1.0)

        st.markdown("### 📦 Résultats enregistrés dans la base")
        df = pd.read_sql("SELECT * FROM result", con=engine)
        if not df.empty:
            st.dataframe(df)
        else:
            st.warning("❌ Aucune donnée trouvée dans la table `result`.")

        # st.header("Production dynamique – Effet d'une perturbation (simulation vivante)")
        # # 🧠 Tension cognitive – scénario vivant
        # st.markdown("### 🧠 Tension cognitive – Système vivant")

        # vivant_data = result.get("vivant_raw_data", [])
        # if vivant_data:
        #     df_vivant = pd.DataFrame(vivant_data)
        #     if not df_vivant.empty:
        #         fig_tension = px.line(df_vivant, x="day", y="tension", color="site",
        #                             title="Évolution de la tension cognitive par site")
        #         st.plotly_chart(fig_tension, use_container_width=True)

        #         fig_command = px.line(df_vivant, x="day", y="command", color="site",
        #                             title="Commande décidée par jour")
        #         st.plotly_chart(fig_command, use_container_width=True)

        #         fig_stock = px.line(df_vivant, x="day", y="stock", color="site",
        #                             title="Évolution du stock par site")
        #         st.plotly_chart(fig_stock, use_container_width=True)



        #     else:
        #         st.info("Pas de données pour le scénario vivant.")
        # else:
        #     st.info("Le scénario vivant n'a pas été simulé ou retourné.")


        # --- Construction DataFrame pour affichage (scores de résilience) ---
        df_scores = pd.DataFrame.from_dict({
            name: res.get("resilience_scores", {"supply": 0, "production": 0, "distribution": 0, "total": 0})
            for name, res in scenario_results.items()
        }, orient='index')

        # Ajout du scénario crise à la main
        df_scores.loc["Crise"] = crisis_result["resilience_scores"]

        # Affichage du tableau complet
        st.markdown("### 🟦 Scores de résilience par scénario")
        st.dataframe(df_scores)

        # --- Exemple Plotly plus interactif ---
        fig_plotly = px.bar(
            df_scores.reset_index(),
            x="index", y="total",
            color="index",
            color_discrete_map={name: ("#4895ef" if name != "Crise" else "#e63946") for name in df_scores.index},
            title="Score de résilience par scénario"
        )
        st.plotly_chart(fig_plotly, use_container_width=True)


# 🟡 Affichage si simulation non encore lancée
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
