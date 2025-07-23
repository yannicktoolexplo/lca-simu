import streamlit as st
from sqlalchemy import create_engine
import pandas as pd
import matplotlib.pyplot as plt
from SimChainGreenHorizons import main_function
import plotly.express as px
from run_simulation_vivante import run_simulation_vivante
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

        st.markdown("### 🌍 Analyse du Cycle de Vie – 1 siège produit en France")
        st.plotly_chart(result["lca_fig"], use_container_width=True)

        # 🔁 Attente courte pour laisser le temps d’écrire dans la base
        import time
        time.sleep(1.0)

        st.markdown("### 📦 Résultats enregistrés dans la base")
        df = pd.read_sql("SELECT * FROM result", con=engine)
        if not df.empty:
            st.dataframe(df)
        else:
            st.warning("❌ Aucune donnée trouvée dans la table `result`.")

        st.header("Production dynamique – Effet d'une perturbation (simulation vivante)")

        scenario_results = result["scenario_results"]
        prod_viv = scenario_results["Simulation vivante"]["production_data"]

        # Trouver l'index France dans lines_config
        fr_index = next(i for i, cfg in enumerate(lines_config) if cfg["location"] == "France")
        
        fig, ax = plt.subplots(figsize=(10,4))
        ax.plot(prod_viv["France"], label="France (simulation vivante)")
        ax.plot(prod_viv["Texas"], label="Texas (simulation vivante)")
        prod_base = scenario_results["Baseline"]["production_data"]["France"]  # Adapter selon le format
        ax.plot(prod_base, '--', label="France (Baseline)")
        # Ajoute les autres courbes/scénarios si tu veux
        ax.set_xlabel("Jour")
        ax.set_ylabel("Production")
        ax.set_title("Production quotidienne – Scénario Simulation vivante")
        ax.legend()
        ax.grid(True)
        st.pyplot(fig)

        # 🧠 Tension cognitive – scénario vivant
        st.markdown("### 🧠 Tension cognitive – Système vivant")

        vivant_data = result.get("vivant_raw_data", [])
        if vivant_data:
            df_vivant = pd.DataFrame(vivant_data)
            if not df_vivant.empty:
                fig_tension = px.line(df_vivant, x="day", y="tension", color="site",
                                    title="Évolution de la tension cognitive par site")
                st.plotly_chart(fig_tension, use_container_width=True)

                fig_command = px.line(df_vivant, x="day", y="command", color="site",
                                    title="Commande décidée par jour")
                st.plotly_chart(fig_command, use_container_width=True)

                fig_stock = px.line(df_vivant, x="day", y="stock", color="site",
                                    title="Évolution du stock par site")
                st.plotly_chart(fig_stock, use_container_width=True)



            else:
                st.info("Pas de données pour le scénario vivant.")
        else:
            st.info("Le scénario vivant n'a pas été simulé ou retourné.")

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
