"""Streamlit app: turnkey interactive supply-risk graph (no Neo4j needed)."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
from plotly.colors import sample_colorscale
import streamlit as st

from supply_issue_graph import (
    _build_actor_info,
    _build_supply_edges,
    _haversine_km,
    _load_data_poc,
    _sd_reception_score,
    _short_actor_label,
    _zone_scores_from_report,
)


ROLE_COLORS = {
    "Supplier Distribution Center": "#4C78A8",
    "Manufacturer": "#F58518",
    "Distribution Center": "#54A24B",
    "Customer": "#E45756",
    "Unknown": "#9D9DA3",
}


@st.cache_data(show_spinner=False)
def load_graph_bundle(graph_path: str, coords_path: str, report_path: str, data_poc_path: str):
    graph = json.loads(Path(graph_path).read_text(encoding="utf-8"))
    coords = json.loads(Path(coords_path).read_text(encoding="utf-8"))
    report = json.loads(Path(report_path).read_text(encoding="utf-8"))

    data_poc = _load_data_poc(data_poc_path) if Path(data_poc_path).exists() else None
    actor_info = _build_actor_info(graph, coords)
    zone_scores = _zone_scores_from_report(report)
    sd_reception = _sd_reception_score(report)
    edges = _build_supply_edges(graph, actor_info, zone_scores, data_poc=data_poc)

    rows = []
    for e in edges:
        src = actor_info[e.source]
        dst = actor_info[e.target]
        rows.append(
            {
                "source_id": e.source,
                "source_code": _short_actor_label(e.source),
                "source_role": src.role,
                "target_id": e.target,
                "target_code": _short_actor_label(e.target),
                "target_role": dst.role,
                "product": e.product,
                "zone": e.zone,
                "material_family": e.material_family,
                "risk_score": float(e.risk_score),
                "risk_display": float(e.risk_display),
                "distance_km": float(_haversine_km(src.lat, src.lon, dst.lat, dst.lon)),
            }
        )
    df = pd.DataFrame(rows).sort_values("risk_score", ascending=False).reset_index(drop=True)
    return actor_info, edges, df, zone_scores, sd_reception


def build_figure(actor_info, edges, min_display: float, zones: set[str], show_labels: bool, show_low_edges: bool):
    fig = go.Figure()

    visible_edges = []
    for edge in edges:
        if edge.zone not in zones:
            continue
        if edge.risk_display < min_display and not show_low_edges:
            continue
        visible_edges.append(edge)

    active_actors = set()
    for edge in visible_edges:
        active_actors.add(edge.source)
        active_actors.add(edge.target)

    for edge in visible_edges:
        src = actor_info[edge.source]
        dst = actor_info[edge.target]
        score = max(0.0, min(1.0, edge.risk_display))
        color = sample_colorscale("Turbo", [score])[0]
        fig.add_trace(
            go.Scatter(
                x=[src.lon, dst.lon],
                y=[src.lat, dst.lat],
                mode="lines",
                line={"color": color, "width": 1.0 + 5.0 * score},
                opacity=0.16 + 0.74 * score,
                showlegend=False,
                hovertemplate=(
                    f"{_short_actor_label(edge.source)} -> {_short_actor_label(edge.target)}<br>"
                    f"product={edge.product}<br>"
                    f"zone={edge.zone}<br>"
                    f"material={edge.material_family}<br>"
                    f"risk={edge.risk_score:.3f}<br>"
                    f"display={edge.risk_display:.3f}<extra></extra>"
                ),
            )
        )

    roles = sorted({info.role for aid, info in actor_info.items() if aid in active_actors})
    for role in roles:
        nodes = [a for aid, a in actor_info.items() if aid in active_actors and a.role == role]
        text = [_short_actor_label(a.actor_id) for a in nodes] if show_labels else None
        fig.add_trace(
            go.Scatter(
                x=[a.lon for a in nodes],
                y=[a.lat for a in nodes],
                mode="markers+text" if show_labels else "markers",
                text=text,
                textposition="top right",
                marker={
                    "size": 10,
                    "color": ROLE_COLORS.get(role, "#9D9DA3"),
                    "line": {"color": "#222", "width": 1},
                },
                name=role,
                hovertemplate=(
                    "actor=%{customdata[0]}<br>"
                    "role=%{customdata[1]}<br>"
                    "description=%{customdata[2]}<extra></extra>"
                ),
                customdata=[[a.actor_id, a.role, a.description] for a in nodes],
            )
        )

    customer_nodes = [a for aid, a in actor_info.items() if aid in active_actors and a.role == "Customer"]
    if customer_nodes:
        fig.add_trace(
            go.Scatter(
                x=[a.lon for a in customer_nodes],
                y=[a.lat for a in customer_nodes],
                mode="markers",
                marker={
                    "size": 28,
                    "color": "rgba(0,0,0,0)",
                    "line": {"color": "rgba(22,96,167,0.95)", "width": 3},
                },
                showlegend=False,
                hovertemplate="SD reception node<extra></extra>",
            )
        )

    fig.add_trace(
        go.Scatter(
            x=[None],
            y=[None],
            mode="markers",
            marker={
                "colorscale": "Turbo",
                "showscale": True,
                "cmin": 0,
                "cmax": 1,
                "color": [0],
                "colorbar": {
                    "title": "Risk percentile",
                    "thickness": 14,
                    "len": 0.70,
                },
            },
            hoverinfo="skip",
            showlegend=False,
        )
    )

    fig.update_layout(
        template="plotly_white",
        height=760,
        margin={"l": 30, "r": 10, "t": 40, "b": 30},
        xaxis_title="Longitude / fallback x",
        yaxis_title="Latitude / fallback y",
        legend={"orientation": "h", "yanchor": "bottom", "y": 1.02, "x": 0},
    )
    fig.update_xaxes(showgrid=True, gridcolor="rgba(0,0,0,0.08)")
    fig.update_yaxes(showgrid=True, gridcolor="rgba(0,0,0,0.08)", scaleanchor="x", scaleratio=1.0)
    return fig, visible_edges


def main():
    st.set_page_config(page_title="Supply Risk Graph", layout="wide")
    st.title("Supply Risk Graph - Streamlit")
    st.caption("Version clé en main sans Neo4j/Bloom.")

    with st.sidebar:
        st.header("Fichiers")
        graph_path = st.text_input("knowledge_graph", "knowledge_graph.json")
        coords_path = st.text_input("actor_coords", "actor_coords.json")
        report_path = st.text_input("report", "advanced_complex_full_report.json")
        data_poc_path = st.text_input("Data_poc", "Data_poc.xlsx")
        refresh = st.button("Recharger")

    if refresh:
        load_graph_bundle.clear()

    try:
        actor_info, edges, df, zone_scores, sd_reception = load_graph_bundle(
            graph_path=graph_path,
            coords_path=coords_path,
            report_path=report_path,
            data_poc_path=data_poc_path,
        )
    except Exception as exc:
        st.error(f"Chargement impossible: {exc}")
        st.stop()

    with st.sidebar:
        st.header("Filtres")
        all_zones = sorted(df["zone"].dropna().unique().tolist())
        selected_zones = st.multiselect("Zones", all_zones, default=all_zones)
        min_display = st.slider("Seuil visuel risque (percentile)", 0.0, 1.0, 0.55, 0.01)
        show_labels = st.checkbox("Afficher labels noeuds", value=False)
        show_low_edges = st.checkbox("Afficher aussi liens sous seuil", value=False)
        top_n = st.slider("Top liens à afficher (table)", 5, 50, 20, 1)

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Actors", len(actor_info))
    col2.metric("Supply links", len(edges))
    col3.metric("SD reception score", f"{sd_reception.get('score', 0.0):.3f}")
    col4.metric("Max zone score", f"{max(zone_scores.values()) if zone_scores else 0.0:.3f}")

    fig, visible_edges = build_figure(
        actor_info=actor_info,
        edges=edges,
        min_display=min_display,
        zones=set(selected_zones),
        show_labels=show_labels,
        show_low_edges=show_low_edges,
    )
    st.plotly_chart(fig, use_container_width=True)

    st.subheader("Zone scores")
    zone_df = pd.DataFrame(
        [{"zone": zone, "score": score} for zone, score in sorted(zone_scores.items(), key=lambda x: x[1], reverse=True)]
    )
    st.dataframe(zone_df, use_container_width=True, hide_index=True)

    st.subheader("Top risky links")
    vis_set = {(e.source, e.target, e.product) for e in visible_edges}
    df_view = df[df.apply(lambda r: (r["source_id"], r["target_id"], r["product"]) in vis_set, axis=1)].copy()
    df_view = df_view.sort_values("risk_score", ascending=False).head(top_n)
    st.dataframe(
        df_view[
            [
                "source_code",
                "target_code",
                "product",
                "zone",
                "material_family",
                "risk_score",
                "risk_display",
                "distance_km",
            ]
        ],
        use_container_width=True,
        hide_index=True,
    )

    st.download_button(
        label="Télécharger liens filtrés (CSV)",
        data=df_view.to_csv(index=False).encode("utf-8"),
        file_name="filtered_supply_risk_links.csv",
        mime="text/csv",
    )

    st.info(
        "Run: `streamlit run /workspaces/lca-simu/streamlit_supply_risk_app.py`"
    )


if __name__ == "__main__":
    main()

