import time

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from sqlalchemy import create_engine

from SimChainGreenHorizons import main_function

# ------------------------------------------------------------------------------
# Configuration de la base de données SQLite
# ------------------------------------------------------------------------------
DB_PATH = "sqlite:///simchain.db"
engine = create_engine(DB_PATH)

st.title("📊 Supply Chain Simulator – Dashboard")


# ------------------------------------------------------------------------------
# Fonction utilitaires d'affichage
# ------------------------------------------------------------------------------

def plot_global_rate_curves(baseline_rc, crisis_rc_dict):
    """
    Affiche la courbe de taux global (0–1) du scénario Baseline
    et des scénarios de crise, sur un même graphique.
    """
    fig = go.Figure()

    t_base = baseline_rc.get("time", [])
    g_base = baseline_rc.get("global", [])
    if t_base and g_base:
        fig.add_trace(
            go.Scatter(
                x=t_base,
                y=g_base,
                mode="lines",
                name="Baseline",
                line=dict(color="white"),
            )
        )

    for name, rc in crisis_rc_dict.items():
        t = rc.get("time", [])
        g = rc.get("global", [])
        if not t or not g:
            continue
        fig.add_trace(
            go.Scatter(
                x=t,
                y=g,
                mode="lines",
                name=name,
            )
        )

    fig.update_layout(
        title="Taux de production global (0–1) – Baseline vs Crises",
        xaxis_title="Temps",
        yaxis_title="Taux de production (0–1)",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    return fig


def plot_per_line_rates(rate_curves, title):
    """
    Affiche, pour un scénario donné, les taux de production par ligne
    (courbes lissées déjà normalisées 0–1).
    """
    per_line = rate_curves.get("per_line", {})
    t = rate_curves.get("time", [])

    fig = go.Figure()
    if not per_line or not t:
        fig.update_layout(
            title=f"{title} – aucune courbe disponible",
            xaxis_title="Temps",
            yaxis_title="Taux de production (0–1)",
        )
        return fig

    n_times = min(len(t), *(len(v) for v in per_line.values()))
    t = t[:n_times]

    for site, curve in per_line.items():
        fig.add_trace(
            go.Scatter(
                x=t,
                y=curve[:n_times],
                mode="lines",
                name=f"{site} (moy. glissante)",
            )
        )

    fig.update_layout(
        title=title,
        xaxis_title="Temps",
        yaxis_title="Taux de production (0–1)",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    return fig


def plot_crisis_rate_with_indicators(name, rate_curves, ind_ref, ind_auto):
    """
    Affiche la courbe globale de taux pour un scénario de crise
    avec annotation du creux et de la fenêtre de recovery si dispo.
    """
    t = rate_curves.get("time", []) or []
    g = rate_curves.get("global", []) or []

    # Si l'un est vide : rien à tracer
    if not t or not g:
        fig = go.Figure()
        fig.update_layout(
            title=f"Taux de production (%) – {name} (aucune donnée)",
            xaxis_title="Temps",
            yaxis_title="Taux de production (0–1)",
        )
        return fig

    # Sécurité : on force la même longueur
    n = min(len(t), len(g))
    t = t[:n]
    g = g[:n]


    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=t,
            y=g,
            mode="lines",
            name="Taux de production",
        )
    )

    # Annotation "auto" sur la courbe (si amplitude > 0)
    if ind_auto and ind_auto.get("amplitude", 0) > 0:
        arr = np.array(g)
        idx_min = int(np.argmin(arr))
        ref_mean = float(np.mean(arr[:idx_min])) if idx_min > 0 else arr[0]

        fig.add_trace(
            go.Scatter(
                x=[t[idx_min]],
                y=[g[idx_min]],
                mode="markers+text",
                marker=dict(size=10),
                name="Creux (auto)",
                text=["Creux auto"],
                textposition="top center",
            )
        )

        fig.add_hline(
            y=ref_mean,
            line_dash="dot",
            annotation_text="Référence locale",
            annotation_position="bottom right",
        )

        rec_time = ind_auto.get("recovery_time", None)
        if rec_time is not None and not np.isnan(rec_time):
            x1 = t[idx_min] + rec_time
            fig.add_vrect(
                x0=t[idx_min],
                x1=x1,
                fillcolor="red",
                opacity=0.08,
                line_width=0,
                annotation_text="Recovery",
            )

    fig.update_layout(
        title=f"Taux de production (%) – {name}",
        xaxis_title="Temps",
        yaxis_title="Taux de production (0–1)",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    return fig


# ------------------------------------------------------------------------------
# BOUTON : Lancer la simulation
# ------------------------------------------------------------------------------

if st.button("🚀 Lancer la simulation"):
    with st.spinner("Simulation en cours..."):
        result = main_function()
        st.success("✅ Simulation terminée !")

    scenario_results = result["scenario_results"]
    crisis_results = result["crisis_results"]
    cap_max = result["cap_max"]
    lines_config = result["lines_config"]

    # ------------------------------------------------------------------
    # 1. Graphiques comparatifs des scénarios nominaux
    # ------------------------------------------------------------------
    st.markdown("### 📈 Résultats comparés des scénarios (nominal)")
    for i, fig in enumerate(result["figures"]):
        st.plotly_chart(fig, use_container_width=True, key=f"fig_scenario_{i}")

    # ------------------------------------------------------------------
    # 2. Graphiques comparatifs des scénarios de crise
    # ------------------------------------------------------------------
    st.markdown("### 📈 Résultats comparés des scénarios de crise")
    for i, fig in enumerate(result["crisis_figures"]):
        st.plotly_chart(fig, use_container_width=True, key=f"fig_crise_{i}")

    # ------------------------------------------------------------------
    # 3. Baseline vs Crises – Production totale par site
    # ------------------------------------------------------------------
    st.markdown("### ⚖️ Baseline vs Scénarios de crise – Production totale par site")

    baseline_totals = scenario_results["Baseline"]["production_totals"]
    all_sites = set(baseline_totals.keys())
    for crisis in crisis_results.values():
        all_sites.update(crisis["production_totals"].keys())
    sites = sorted(all_sites)

    compare_data = {
        "Site": sites,
        "Baseline": [baseline_totals.get(site, 0) for site in sites],
    }
    for name, crisis in crisis_results.items():
        compare_data[name] = [crisis["production_totals"].get(site, 0) for site in sites]

    df_compare = pd.DataFrame(compare_data)
    df_compare_melted = df_compare.melt(
        id_vars="Site", var_name="Scenario", value_name="Production"
    )

    fig_compare = px.bar(
        df_compare_melted,
        x="Site",
        y="Production",
        color="Scenario",
        barmode="group",
        title="Production totale par site : Baseline vs scénarios de crise",
    )
    st.plotly_chart(fig_compare, use_container_width=True, key="fig_compare_baseline_crises")

    # ------------------------------------------------------------------
    # 4. Analyse LCA globale (scénario multi-objectifs)
    # ------------------------------------------------------------------
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
            "production totale nulle ou aucune ligne active."
        )

    # ------------------------------------------------------------------
    # 5. Résultats enregistrés en base
    # ------------------------------------------------------------------
    # st.markdown("### 📦 Résultats enregistrés dans la base")
    # time.sleep(1.0)  # petit délai pour laisser le temps aux insertions
    # try:
    #     df_db = pd.read_sql("SELECT * FROM result", con=engine)
    #     if not df_db.empty:
    #         st.dataframe(df_db)
    #     else:
    #         st.warning("❌ Aucune donnée trouvée dans la table `result`.")
    # except Exception as e:
    #     st.error(f"Erreur lors de la lecture de la base : {e}")

    # ------------------------------------------------------------------
    # 6. Scores de résilience par scénario
    # ------------------------------------------------------------------
    # st.markdown("### 🟦 Scores de résilience par scénario")

    # df_scores = pd.DataFrame.from_dict(
    #     {
    #         name: res.get(
    #             "resilience_scores",
    #             {"supply": 0, "production": 0, "distribution": 0, "total": 0},
    #         )
    #         for name, res in scenario_results.items()
    #     },
    #     orient="index",
    # )

    # for name, res in crisis_results.items():
    #     df_scores.loc[name] = res.get(
    #         "resilience_scores",
    #         {"supply": 0, "production": 0, "distribution": 0, "total": 0},
    #     )

    # st.dataframe(df_scores)

    # fig_resilience = px.bar(
    #     df_scores.reset_index(),
    #     x="index",
    #     y="total",
    #     color="index",
    #     title="Score de résilience (total) par scénario",
    # )
    # fig_resilience.update_layout(xaxis_title="Scénario", yaxis_title="Score total (0–100)")
    # st.plotly_chart(fig_resilience, use_container_width=True, key="fig_resilience")

    # ------------------------------------------------------------------
    # 7. Indicateurs détaillés de résilience pour les scénarios de crise
    # ------------------------------------------------------------------
    st.markdown("### 📊 Indicateurs de résilience – scénarios de crise")

    rows = []
    for name, res in crisis_results.items():
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
        df_both = pd.DataFrame(rows).set_index("Scénario")
        st.dataframe(df_both)

    # ------------------------------------------------------------------
    # 8. Courbes de taux global – Baseline vs Crises
    # ------------------------------------------------------------------
    st.markdown("### 📈 Taux de production global – Baseline vs Crises")

    baseline_rc = scenario_results["Baseline"].get("rate_curves", {})
    crisis_rc_dict = {
        name: res.get("rate_curves", {}) for name, res in crisis_results.items()
    }
    fig_global_rates = plot_global_rate_curves(baseline_rc, crisis_rc_dict)
    st.plotly_chart(fig_global_rates, use_container_width=True, key="fig_global_rates")

    # ------------------------------------------------------------------
    # 9. Courbes de taux global + indicateurs pour chaque crise
    # ------------------------------------------------------------------
    st.markdown("### 📈 Taux de production global et indicateurs – par scénario de crise")

    for name, res in crisis_results.items():
        rate_curves = res.get("rate_curves", {})
        ind_ref = res.get("resilience_indicators", {})
        ind_auto = res.get("resilience_auto_indicators", {})

        st.subheader(f"Scénario : {name}")
        fig = plot_crisis_rate_with_indicators(name, rate_curves, ind_ref, ind_auto)
        st.plotly_chart(fig, use_container_width=True, key=f"fig_rate_global_{name}")

        with st.expander("Voir les indicateurs de résilience pour ce scénario"):
            st.write("**Par rapport à la référence nominale (Baseline)**")
            st.write(ind_ref)
            st.write("**Détection auto sur la courbe de taux**")
            st.write(ind_auto)
    # ------------------------------------------------------------------
    # 9bis. Courbes de performance agrégée – par scénario de crise
    # ------------------------------------------------------------------
    st.markdown("### 📈 Signal de performance agrégé – scénarios de crise")

    for name, res in crisis_results.items():
        perf = res.get("perf_signal", {})
        t = perf.get("time", [])
        g = perf.get("global", [])
        if not t or not g:
            continue

        st.subheader(f"Scénario : {name} (performance agrégée)")

        fig_perf = go.Figure()
        fig_perf.add_trace(
            go.Scatter(
                x=t,
                y=g,
                mode="lines",
                name="Perf agrégée (0–1)",
            )
        )

        ind_ref = res.get("resilience_perf_indicators", {})
        ind_auto = res.get("resilience_perf_auto_indicators", {})

        # Tu peux réutiliser la logique d’annotation de plot_crisis_rate_with_indicators
        # si tu veux visualiser le creux et la recovery sur ce signal.

        fig_perf.update_layout(
            title=f"Performance agrégée (0–1) – {name}",
            xaxis_title="Temps",
            yaxis_title="Performance (0–1)",
        )
        st.plotly_chart(fig_perf, use_container_width=True)

        with st.expander("Voir les indicateurs de résilience (performance agrégée)"):
            st.write("**Par rapport à la référence Baseline (performance)**")
            st.write(ind_ref)
            st.write("**Détection auto sur la courbe de performance**")
            st.write(ind_auto)

    # ------------------------------------------------------------------
    # 10. Courbes de taux par ligne pour Baseline + Crises
    # ------------------------------------------------------------------
    st.markdown("### 📈 Taux de production par ligne – Baseline et scénarios de crise")

    # Baseline
    st.subheader("Baseline – taux de production par ligne")
    fig_baseline_lines = plot_per_line_rates(
        scenario_results["Baseline"].get("rate_curves", {}),
        "Taux de production par ligne – Baseline",
    )
    st.plotly_chart(fig_baseline_lines, use_container_width=True, key="fig_lines_Baseline")

    # Crises
    for i, (scenario_name, scenario_res) in enumerate(crisis_results.items()):
        st.subheader(f"Scénario : {scenario_name}")
        fig_lines = plot_per_line_rates(
            scenario_res.get("rate_curves", {}),
            f"Taux de production par ligne – {scenario_name}",
        )
        st.plotly_chart(
            fig_lines,
            use_container_width=True,
            key=f"fig_lines_{scenario_name}_{i}",
        )

else:
    # Si aucune simulation n'a encore été lancée, afficher éventuellement la base
    st.markdown("### 📦 Résultats enregistrés dans la base")
    try:
        df = pd.read_sql("SELECT * FROM result", con=engine)
        if not df.empty:
            st.dataframe(df)
        else:
            st.info("Aucune simulation encore enregistrée.")
    except Exception as e:
        st.error(f"Erreur lors de la lecture de la base : {e}")
