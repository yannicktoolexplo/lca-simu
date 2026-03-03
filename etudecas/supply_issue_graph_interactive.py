"""Interactive knowledge graph visualization for supply risk diagnostics."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import plotly.graph_objects as go
from plotly.colors import sample_colorscale

from supply_issue_graph import (
    _build_actor_info,
    _build_supply_edges,
    _detailed_text_report,
    _load_data_poc,
    _role_color,
    _sd_reception_score,
    _short_actor_label,
    _top_edge_rows,
    _zone_scores_from_report,
)


def _edge_hover(edge) -> str:
    return (
        f"source={_short_actor_label(edge.source)}<br>"
        f"target={_short_actor_label(edge.target)}<br>"
        f"product={edge.product}<br>"
        f"type={edge.material_family}<br>"
        f"zone={edge.zone}<br>"
        f"risk={edge.risk_score:.3f}<br>"
        f"display={edge.risk_display:.3f}"
    )


def build_interactive_graph(
    graph_path: str | Path,
    coords_path: str | Path,
    report_path: str | Path,
    output_html: str | Path,
    output_json: str | Path | None = None,
    output_text: str | Path | None = None,
    data_poc_path: str | Path | None = "Data_poc.xlsx",
) -> dict[str, object]:
    graph = json.loads(Path(graph_path).read_text(encoding="utf-8"))
    coords = json.loads(Path(coords_path).read_text(encoding="utf-8"))
    report = json.loads(Path(report_path).read_text(encoding="utf-8"))

    data_poc = _load_data_poc(data_poc_path)
    actor_info = _build_actor_info(graph, coords)
    zone_scores = _zone_scores_from_report(report)
    sd_reception = _sd_reception_score(report)
    edges = _build_supply_edges(graph, actor_info, zone_scores, data_poc=data_poc)

    fig = go.Figure()

    # one trace per edge keeps hover precise and readable
    for edge in edges:
        src = actor_info[edge.source]
        dst = actor_info[edge.target]
        color = sample_colorscale("Turbo", [edge.risk_display])[0]
        fig.add_trace(
            go.Scatter(
                x=[src.lon, dst.lon],
                y=[src.lat, dst.lat],
                mode="lines",
                line={"color": color, "width": 1.0 + 6.0 * edge.risk_display},
                hovertemplate=_edge_hover(edge) + "<extra></extra>",
                opacity=0.18 + 0.72 * edge.risk_display,
                showlegend=False,
            )
        )

    # Node traces by role.
    roles = sorted({a.role for a in actor_info.values()})
    for role in roles:
        nodes = [a for a in actor_info.values() if a.role == role]
        fig.add_trace(
            go.Scatter(
                x=[a.lon for a in nodes],
                y=[a.lat for a in nodes],
                mode="markers+text",
                text=[_short_actor_label(a.actor_id) for a in nodes],
                textposition="top right",
                marker={
                    "size": 10,
                    "color": _role_color(role),
                    "line": {"color": "#202020", "width": 1},
                },
                name=role,
                hovertemplate=(
                    "id=%{customdata[0]}<br>"
                    "role=%{customdata[1]}<br>"
                    "desc=%{customdata[2]}<extra></extra>"
                ),
                customdata=[[a.actor_id, a.role, a.description] for a in nodes],
            )
        )

    # SD reception halo.
    reception_nodes = [a for a in actor_info.values() if a.role == "Customer"]
    if reception_nodes:
        score = max(0.0, min(1.0, sd_reception.get("score", 0.0)))
        fig.add_trace(
            go.Scatter(
                x=[a.lon for a in reception_nodes],
                y=[a.lat for a in reception_nodes],
                mode="markers",
                marker={
                    "size": 24 + 26 * score,
                    "color": "rgba(0,0,0,0)",
                    "line": {"color": "rgba(22,96,167,0.95)", "width": 2 + 4 * score},
                },
                name=f"SD reception stress={score:.2f}",
                hovertemplate=(
                    f"SD reception score={score:.3f}<br>"
                    f"stock peak gain={sd_reception.get('stock_peak_gain_db', 0.0):.2f} dB<extra></extra>"
                ),
            )
        )

    # Colorbar for edge risk.
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
                    "title": "DES link risk percentile",
                    "thickness": 14,
                    "len": 0.68,
                },
            },
            hoverinfo="skip",
            showlegend=False,
        )
    )

    fig.update_layout(
        title="Supply Knowledge Graph - Interactive Risk View",
        xaxis_title="Longitude / fallback x",
        yaxis_title="Latitude / fallback y",
        template="plotly_white",
        width=1350,
        height=900,
        legend={"orientation": "h", "yanchor": "bottom", "y": 1.01, "x": 0.0},
        margin={"l": 50, "r": 30, "t": 70, "b": 50},
    )
    fig.update_xaxes(showgrid=True, gridcolor="rgba(0,0,0,0.08)")
    fig.update_yaxes(showgrid=True, gridcolor="rgba(0,0,0,0.08)", scaleanchor="x", scaleratio=1.0)

    fig.write_html(str(output_html), include_plotlyjs=True, full_html=True)

    detailed_text = _detailed_text_report(report, edges, zone_scores, sd_reception, data_poc=data_poc)
    payload = {
        "graph_path": str(graph_path),
        "coords_path": str(coords_path),
        "report_path": str(report_path),
        "output_html": str(output_html),
        "zone_scores": zone_scores,
        "sd_reception": sd_reception,
        "data_poc_used": data_poc is not None,
        "data_poc_relation_rows": 0 if data_poc is None else len(data_poc.relation_by_triplet),
        "data_poc_relation_rows_matched": 0 if data_poc is None else data_poc.matched_relations,
        "data_poc_bom_criticality_products": 0 if data_poc is None else len(data_poc.product_bom_criticality),
        "top_localized_links": _top_edge_rows(edges),
        "detailed_report": detailed_text,
    }

    if output_json is not None:
        Path(output_json).write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")
    if output_text is not None:
        Path(output_text).write_text(detailed_text, encoding="utf-8")
    return payload


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Interactive supply knowledge graph with risk annotations")
    parser.add_argument("--graph", type=str, default="knowledge_graph.json", help="Path to knowledge_graph.json")
    parser.add_argument("--coords", type=str, default="actor_coords.json", help="Path to actor_coords.json")
    parser.add_argument("--report", type=str, default="advanced_complex_full_report.json", help="Path to diagnostics report JSON")
    parser.add_argument("--out-html", type=str, default="supply_issue_annotated_interactive.html", help="Output HTML path")
    parser.add_argument("--out-json", type=str, default="supply_issue_annotated_interactive.json", help="Output metadata JSON path")
    parser.add_argument("--out-text", type=str, default="supply_issue_annotated_interactive_report.txt", help="Output text report path")
    parser.add_argument("--data-poc", type=str, default="Data_poc.xlsx", help="Optional Data_poc.xlsx path")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = build_interactive_graph(
        graph_path=args.graph,
        coords_path=args.coords,
        report_path=args.report,
        output_html=args.out_html,
        output_json=args.out_json,
        output_text=args.out_text,
        data_poc_path=args.data_poc,
    )
    print(f"Interactive graph HTML: {payload['output_html']}")
    print(f"Top links listed: {len(payload['top_localized_links'])}")


if __name__ == "__main__":
    main()

