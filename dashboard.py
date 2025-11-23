import time

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from sqlalchemy import create_engine

from resilience_analysis import compare_scenarios
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
        st.plotly_chart(fig, width='stretch', key=f"fig_scenario_{i}")

    # ------------------------------------------------------------------
    # 2. Graphiques comparatifs des scénarios de crise
    # ------------------------------------------------------------------
    st.markdown("### 📈 Résultats comparés des scénarios de crise")
    for i, fig in enumerate(result["crisis_figures"]):
        st.plotly_chart(fig, width='stretch', key=f"fig_crise_{i}")

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
    st.plotly_chart(fig_compare, width='stretch', key="fig_compare_baseline_crises")

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
        st.plotly_chart(lca_fig_total, width='stretch', key="lca_multi_total")
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
    # st.plotly_chart(fig_resilience, width='stretch', key="fig_resilience")

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
    st.plotly_chart(fig_global_rates, width='stretch', key="fig_global_rates")

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
        st.plotly_chart(fig, width='stretch', key=f"fig_rate_global_{name}")

        with st.expander("Voir les indicateurs de résilience pour ce scénario"):
            st.write("**Par rapport à la référence nominale (Baseline)**")
            st.write(ind_ref)
            st.write("**Détection auto sur la courbe de taux**")
            st.write(ind_auto)

    # ------------------------------------------------------------------
    # 9bis. Courbes de taux par ligne pour Baseline + Crises
    # ------------------------------------------------------------------
    st.markdown("### 📈 Taux de production par ligne – Baseline et scénarios de crise")

    # # Baseline
    # st.subheader("Baseline – taux de production par ligne")
    # fig_baseline_lines = plot_per_line_rates(
    #     scenario_results["Baseline"].get("rate_curves", {}),
    #     "Taux de production par ligne – Baseline",
    # )
    # st.plotly_chart(fig_baseline_lines, width='stretch', key="fig_lines_Baseline")

    # Crises
    for i, (scenario_name, scenario_res) in enumerate(crisis_results.items()):
        st.subheader(f"Scénario : {scenario_name}")
        fig_lines = plot_per_line_rates(
            scenario_res.get("rate_curves", {}),
            f"Taux de production par ligne – {scenario_name}",
        )
        st.plotly_chart(
            fig_lines,
            width='stretch',
            key=f"fig_lines_{scenario_name}_{i}",
        )


    # ------------------------------------------------------------------
    # 10. Radar chart des scores de résilience (R1–R4)
    # ------------------------------------------------------------------
    # === RADAR de résilience basé sur les taux ===
    import plotly.graph_objects as go
    from resilience_analysis import radar_indicators

    baseline = crisis_results["Baseline"]
    time_vector = baseline["rate_curves"]["time"]
    baseline_curve = baseline["rate_curves"]["global"]
    baseline_total = sum(baseline["production_totals"].values())

    fig_radar = go.Figure()
    categories = ["R1 Amplitude", "R2 Recovery", "R3 Aire", "R4 Ratio", "R5 ProdCumul"]
    baseline_radar_values = None
    baseline_radar_score = None

    for name, crisis in crisis_results.items():
        crisis_curve = crisis["rate_curves"]["global"]
        crisis_total = sum(crisis["production_totals"].values())
        scores = radar_indicators(baseline_curve, crisis_curve, time_vector, baseline_total, crisis_total)
        values = [scores[k] for k in categories] + [scores[categories[0]]]  # fermer le polygone
        trace_line = {}
        fill_color = None
        if name == "Baseline":
            baseline_radar_values = list(values)
            baseline_radar_score = scores["Score global"]
            trace_line["color"] = "#636EFA"
            fill_color = "rgba(99,110,250,0.35)"
        fig_radar.add_trace(go.Scatterpolar(
            r=values,
            theta=categories + [categories[0]],
            fill='toself',
            name=f"{name} (score: {scores['Score global']})",
            line=trace_line,
            fillcolor=fill_color,
        ))

    fig_radar.update_layout(
        polar=dict(radialaxis=dict(visible=True, range=[0, 1.2])),
        showlegend=True,
        title="Radar de résilience"
    )
    st.plotly_chart(fig_radar, width='stretch')
    baseline_reference_values = baseline_radar_values
    baseline_reference_score = baseline_radar_score or 0.0


    # ===============================
    #  SCÉNARIO OPTIMISÉ RÉSILIENCE
    # ===============================
    opt_res = result.get("resilience_optimized")

    if opt_res:
        st.markdown("## 🔵 Scénario Résilience Optimisé")

        st.write(f"**Meilleure configuration** : {opt_res.get('best_name', 'N/A')}")
        st.write(f"**Score moyen de résilience** : {opt_res.get('best_score', 0):.1f} / 100")

        # Radar combiné Crise 1 / Crise 2
        import plotly.graph_objects as go
        categories = ["R1 Amplitude", "R2 Recovery", "R3 Aire", "R4 Ratio", "R5 ProdCumul"]

        fig_r = go.Figure()
        rad1 = opt_res.get("radar_crise1", {})
        rad2 = opt_res.get("radar_crise2", {})
        baseline_curve = baseline["rate_curves"]["global"]
        baseline_time = baseline["rate_curves"]["time"]
        baseline_total = sum(baseline["production_totals"].values())
        scenario_colors = {
            "Optim Résilience": "#FFB300",
            "Baseline": "#636EFA",
            "Optimisation Coût": "#1f77b4",
            "Optimisation CO₂": "#2ca02c",
            "MultiObjectifs": "#d62728",
            "Lightweight": "#9467bd",
        }

        def avg(a, b): 
            return 0.5 * (a + b) if isinstance(a, (int, float)) and isinstance(b, (int, float)) else 0

        # Vérifie la présence des données avant d’afficher
        if not rad1 or not rad2 or any(c not in rad1 for c in categories) or any(c not in rad2 for c in categories):
            st.warning("⚠️ L’optimisation résilience n’a pas trouvé de configuration valide. Aucun radar n’est affiché.")
        else:
            optim_trace = [avg(rad1[c], rad2[c]) for c in categories]
            optim_trace.append(optim_trace[0])
            baseline_values = baseline_reference_values
            baseline_score_display = baseline_reference_score
            if not baseline_values:
                base_scores = radar_indicators(
                    baseline_curve,
                    baseline_curve,
                    baseline_time,
                    baseline_total,
                    baseline_total,
                )
                baseline_values = [base_scores[c] for c in categories]
                baseline_values.append(baseline_values[0])
                baseline_score_display = base_scores["Score global"]
                baseline_reference_values = baseline_values
            scenario_traces = [
                ("Optim Résilience", optim_trace, opt_res.get("best_score", 0.0)),
                ("Baseline", baseline_values, baseline_score_display),
            ]
            for scenario_name in ["Optimisation Coût", "Optimisation CO₂", "MultiObjectifs", "Lightweight"]:
                scenario = scenario_results.get(scenario_name)
                if not scenario:
                    continue
                rate_curves = scenario.get("rate_curves", {})
                nominal_curve = rate_curves.get("global", [])
                nominal_time = rate_curves.get("time", [])
                nominal_total = sum((scenario.get("production_totals") or {}).values())
                crises = scenario.get("resilience_crises") or {}
                if not nominal_curve or not nominal_time or nominal_total <= 0 or not crises:
                    continue
                crisis_curves = []
                for crisis_key in ["Crise 1", "Crise 2"]:
                    entry = crises.get(crisis_key)
                    if not entry:
                        continue
                    rc = entry.get("rate_curves", {})
                    crisis_curve = (rc or {}).get("global", [])
                    crisis_time = (rc or {}).get("time", [])
                    crisis_total = sum((entry.get("production_totals") or {}).values())
                    if not crisis_curve or not crisis_time or crisis_total <= 0:
                        continue
                    min_len = min(len(nominal_curve), len(crisis_curve), len(nominal_time))
                    if min_len == 0:
                        continue
                    score = radar_indicators(
                        nominal_curve[:min_len],
                        crisis_curve[:min_len],
                        nominal_time[:min_len],
                        nominal_total,
                        crisis_total,
                    )
                    crisis_curves.append(score)
                if crisis_curves:
                    averaged = []
                    for c in categories:
                        averaged.append(sum(score.get(c, 0.0) for score in crisis_curves) / len(crisis_curves))
                    averaged.append(averaged[0])
                    scenario_traces.append(
                        (
                            scenario_name,
                            averaged,
                            sum(score.get("Score global", 0.0) for score in crisis_curves) / len(crisis_curves),
                        )
                    )

            for name, values, score in scenario_traces:
                color = scenario_colors.get(name)
                line_options = dict(color=color)
                fillcolor = None
                opacity = 0.6
                if name == "Baseline":
                    line_options["dash"] = "dot"
                    fillcolor = "rgba(135, 137, 140, 0.35)"
                    opacity = 0.8
                fig_r.add_trace(go.Scatterpolar(
                    r=values,
                    theta=categories + [categories[0]],
                    fill='toself',
                    name=f"{name} (score: {score:.1f})",
                    line=line_options,
                    fillcolor=fillcolor,
                    opacity=opacity,
                ))

            fig_r.update_layout(
                title="Radar – Scénario Optimisé Résilience",
                polar=dict(radialaxis=dict(visible=True, range=[0, 1.2]))
            )
            st.plotly_chart(fig_r, width='stretch')

        # Tableau récapitulatif des configurations testées
        st.markdown("### 📊 Détail complet des configurations testées")
        if opt_res.get("summary"):
            st.dataframe([
                {"Configuration": s.get("name", "N/A"), "Score": s.get("score", 0.0)}
                for s in opt_res["summary"]
            ])
        else:
            st.info("Aucune configuration de résilience n’a été trouvée.")



   
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
