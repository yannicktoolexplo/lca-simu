import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from sqlalchemy import create_engine
import numpy as np
from SimChainGreenHorizons import main_function
from utils.data_tools import display_all_stock_variations, get_total_prod_curve
from line_production.production_engine import get_global_production_rate, get_global_production_rate_journalier
import uuid

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
        for i, fig in enumerate(result["figures"]):
            st.plotly_chart(fig, use_container_width=True, key=f"fig_scenario_{i}")

        # Afficher les graphiques comparatifs des crises
        st.markdown("### 📈 Résultats comparés des scénarios de crise")
        for i, fig in enumerate(result["crisis_figures"]):
            st.plotly_chart(fig, use_container_width=True, key=f"fig_crise_{i}")


        # Section comparatif Baseline vs Crises
        st.markdown("### ⚖️ Comparatif Baseline vs Scénarios de crise – Production totale par site")

        baseline_totals = result["scenario_results"]["Baseline"]["production_totals"]
        crisis_results = result["crisis_results"]  # c'est bien crisis_results ici, pas crisis_result

        # Agrège tous les sites de tous les scénarios
        all_sites = set(baseline_totals.keys())
        for crisis in crisis_results.values():
            all_sites.update(crisis["production_totals"].keys())
        sites = sorted(list(all_sites))

        compare_data = {
            "Site": sites,
            "Baseline": [baseline_totals.get(site, 0) for site in sites],
        }
        for name, crisis in crisis_results.items():
            compare_data[name] = [crisis["production_totals"].get(site, 0) for site in sites]

        df_compare = pd.DataFrame(compare_data)
        df_compare_melted = df_compare.melt(id_vars="Site", var_name="Scenario", value_name="Production")

        fig_compare = px.bar(
            df_compare_melted,
            x="Site", y="Production", color="Scenario", barmode="group",
            title="Production totale par site : Baseline vs Scénarios de crise"
        )
        st.plotly_chart(fig_compare, use_container_width=True, key="fig_compare_baseline_crises")



        # Affichage de l'analyse LCA totale pour tous sites (scénario multi-objectifs)
        total_units = int(result.get("production_totals_sum", 0))
        lca_fig_total = result.get("lca_fig_total", None)

        if lca_fig_total is not None:
            st.markdown(
                f"### 🌍 Analyse du Cycle de Vie – Optimisation Multi-Objectifs\n"
                f"Nombre total de sièges produits : **{total_units}**"
            )
            st.plotly_chart(lca_fig_total, use_container_width=True, key="lca_multi_total")
        else:
            st.warning(
                "⚠️ Aucun graphique LCA global pour le scénario multi-objectifs : "
                "production totale nulle ou aucune ligne active (MultiObjectifs ne produit rien)."
            )


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
        for name, res in result["crisis_results"].items():
            df_scores.loc[name] = res.get("resilience_scores", {"supply": 0, "production": 0, "distribution": 0, "total": 0})

        st.markdown("### 🟦 Scores de résilience par scénario")
        st.dataframe(df_scores)
        # Exemple de visualisation interactive des scores de résilience
        fig_resilience = px.bar(
            df_scores.reset_index(), x="index", y="total", color="index",
            color_discrete_map={name: ("#4895ef" if name != "Crise" else "#e63946") for name in df_scores.index},
            title="Score de résilience par scénario"
        )
        st.plotly_chart(fig_resilience, use_container_width=True, key="fig_resilience")


        st.markdown("### 📊 Indicateurs de résilience (deux approches)")

        rows = []
        for name, res in result["crisis_results"].items():
            ind_ref = res.get("resilience_indicators", {})
            ind_auto = res.get("resilience_auto_indicators", {})
            if ind_ref or ind_auto:
                row = {"Scénario": name}
                for k, v in ind_ref.items():
                    row[f"Ref_{k}"] = v
                for k, v in ind_auto.items():
                    row[f"Auto_{k}"] = v
                rows.append(row)
        if rows:
            df_both = pd.DataFrame(rows)
            st.dataframe(df_both.set_index("Scénario"))


        st.markdown("### 📈 Courbes de production et indicateurs de résilience (Plotly, un graphe par scénario)")

        def get_production_rate_curves_per_line(result, lines_config, cap_max):
            """
            Pour chaque ligne/site, retourne la série du taux de production journalier (production du jour / capacité max)
            """
            prod_datas = result.get("production_data", [])
            rates = {}
            for cfg, site_data in zip(lines_config, prod_datas):
                location = cfg['location']
                cap = cap_max.get(location, None)
                if cap is None or cap == 0:
                    continue
                # Production CUMULEE (toujours croissante)
                cumul = site_data["Total Seats made"][1]
                # PRODUCTION JOURNALIÈRE brute
                prod_journalier = [cumul[0]] + [cumul[j] - cumul[j-1] for j in range(1, len(cumul))]
                # TAUX JOURNALIER
                taux_journalier = [p / cap for p in prod_journalier]
                rates[location] = taux_journalier
            return rates

        
        
        def moving_average(arr, window=7):
            arr = np.array(arr)
            if len(arr) < window:
                return arr
            return np.convolve(arr, np.ones(window)/window, mode='same')



        cap_max = result["cap_max"]
        lines_config = result["lines_config"]


        for name, res in result["crisis_results"].items():
            st.subheader(f"Scénario : {name}")
            rate_curve = get_global_production_rate_journalier(res, lines_config, cap_max)
            if not rate_curve or len(rate_curve) < 2:
                st.warning("Pas de courbe trouvée.")
                continue
            time_vector = list(range(len(rate_curve)))
            ind_ref = res.get("resilience_indicators", {})
            ind_auto = res.get("resilience_auto_indicators", {})

            fig = go.Figure()
            # Courbe de taux de production (0-1)
            fig.add_trace(go.Scatter(x=time_vector, y=rate_curve, mode='lines', name='Taux de production', line=dict(color='royalblue')))
            # Reste du code (creux, recovery, etc.) identique mais avec `rate_curve` au lieu de `prod_curve` !
            if ind_auto and ind_auto.get("amplitude", 0) > 0:
                idx_min = int(np.argmin(rate_curve))
                ref_mean = float(np.mean(rate_curve[:idx_min])) if idx_min > 0 else rate_curve[0]
                fig.add_trace(go.Scatter(
                    x=[time_vector[idx_min]], y=[rate_curve[idx_min]],
                    mode='markers+text', marker=dict(size=12, color='red'),
                    name='Creux (auto)', text=["Creux auto"], textposition="top center"
                ))
                fig.add_hline(
                    y=ref_mean, line_dash="dot", line_color="green",
                    annotation_text="Référence locale", annotation_position="bottom right"
                )
                rec_time = ind_auto.get("recovery_time", None)
                if rec_time is not None and not np.isnan(rec_time):
                    x1 = time_vector[idx_min] + rec_time
                    fig.add_vrect(
                        x0=time_vector[idx_min], x1=x1,
                        fillcolor="red", opacity=0.1, line_width=0, annotation_text="Recovery window"
                    )
            fig.update_layout(
                title=f"Taux de production (%) – {name}",
                xaxis_title="Temps",
                yaxis_title="Taux de production (0-1)",
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
            )
            st.plotly_chart(fig, use_container_width=True)
            with st.expander("Voir indicateurs de résilience pour ce scénario"):
                st.write("**Par rapport à la référence nominale**")
                st.write(ind_ref)
                st.write("**Détection auto sur la courbe**")
                st.write(ind_auto)

        st.markdown("### 📈 Taux de production par ligne (Plotly, tous sites sur un même graphique)")

    for i, (scenario_name, scenario_res) in enumerate(result["crisis_results"].items()):
        st.subheader(f"Scénario : {scenario_name}")
        rate_curves = get_production_rate_curves_per_line(scenario_res, lines_config, cap_max)
        if not rate_curves:
            st.warning("Aucun taux trouvé pour ce scénario.")
            continue
        n_times = min(len(r) for r in rate_curves.values())
        time_vector = list(range(n_times))

        fig = go.Figure()
        window = 14  # à adapter selon la taille de tes pas de temps
        for site, curve in rate_curves.items():
            smoothed = moving_average(curve, window)
            fig.add_trace(go.Scatter(
                x=time_vector, y=smoothed[:n_times], mode='lines',
                name=f"{site} (moy. glissante)"
            ))
        fig.update_layout(
            title=f"Taux de production par ligne – {scenario_name}",
            xaxis_title="Temps",
            yaxis_title="Taux de production (0-1)",
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
        )
        st.plotly_chart(
            fig, 
            use_container_width=True, 
            key=f"fig_stock_crises_{scenario_name}_{i}"
    )





        # st.markdown("## 📦 Évolution des stocks – Tous scénarios")
        # for i, (scenario_name, scenario_res) in enumerate(result["scenario_results"].items()):
        #     prod_data = scenario_res.get("production_data", None)
        #     config = scenario_res.get("config", None)
        #     if prod_data is not None and config is not None:
        #         with st.expander(f"Voir stocks pour : {scenario_name}"):
        #             fig = display_all_stock_variations(prod_data, config["lines_config"])
        #             unique_key = f"fig_stock_results_{scenario_name}_{i}_{uuid.uuid4()}"
        #             st.plotly_chart(fig, use_container_width=True, key=unique_key)
        


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
