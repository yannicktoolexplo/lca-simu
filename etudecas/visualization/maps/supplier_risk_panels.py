"""Supplier risk HTML panels and payload builders for the world map."""

from __future__ import annotations

from collections import defaultdict
import html
import math
import re
from pathlib import Path
from typing import Any

from etudecas.case_config import ITEM_DISPLAY_REFERENCE_NOTES
from etudecas.visualization.maps.chart_payloads import build_line_chart_figure
from etudecas.visualization.maps.map_data_loader import load_json_dict, read_csv_rows
from etudecas.visualization.maps.map_payload_builder import display_node_label
from etudecas.visualization.maps.map_render import (
    data_html_asset,
    fmt_days,
    fmt_pct,
    fmt_qty,
    render_data_kv,
    render_data_table,
)
from etudecas.visualization.maps.risk_payload import SIMULATED_RISK_FAMILY_INFO, to_float
from etudecas.visualization.maps.supplier_risk_formatting import (
    risk_pct,
    risk_ratio,
    supplier_risk_action_label,
    supplier_risk_worst_zone,
    supplier_risk_zone_color,
    supplier_risk_zone_counts_text,
    supplier_risk_zone_label,
    supplier_risk_zone_rank,
)


def compact_item_label(item_id: str) -> str:
    raw = str(item_id or "").strip()
    if raw.startswith("item:"):
        return raw.split(":", 1)[1]
    return raw or "n/a"


def item_label_lookup(raw: dict[str, Any]) -> dict[str, str]:
    lookup: dict[str, str] = {}
    for item in raw.get("items", []) or []:
        item_id = str(item.get("id") or "")
        code = str(item.get("code") or "").strip()
        name = str(item.get("name") or "").strip()
        base_label = code if code else (name if name else item_id)
        lookup[item_id] = ITEM_DISPLAY_REFERENCE_NOTES.get(item_id, base_label)
    return lookup


def build_item_label_lookup(raw: dict[str, Any]) -> dict[str, str]:
    out: dict[str, str] = {}
    for item in raw.get("items", []) or []:
        item_id = str(item.get("id") or "")
        if not item_id:
            continue
        code = str(item.get("code") or "").strip()
        name = str(item.get("name") or "").strip()
        base_label = code or name or compact_item_label(item_id)
        out[item_id] = ITEM_DISPLAY_REFERENCE_NOTES.get(item_id, base_label)
    return out


def build_node_type_lookup(raw: dict[str, Any]) -> dict[str, str]:
    out: dict[str, str] = {}
    for node in raw.get("nodes", []) or []:
        node_id = str(node.get("id") or "")
        if not node_id:
            continue
        out[node_id] = str(node.get("type") or "")
    return out


def supplier_risk_summary_lines(
    node_id: str,
    rows: list[dict[str, str]],
    *,
    supplier_row: dict[str, str] | None = None,
    destination_view: bool = False,
) -> list[dict[str, str]]:
    if not rows and not supplier_row:
        return []
    max_risk = max((risk_ratio(row.get("risk_probability_proxy_4w")) for row in rows), default=0.0)
    max_high = max((risk_ratio(row.get("risk_probability_high_proxy_4w")) for row in rows), default=0.0)
    max_margin = max(
        (
            max(
                0.0,
                risk_ratio(row.get("risk_probability_high_proxy_4w"))
                - risk_ratio(row.get("risk_probability_proxy_4w")),
            )
            for row in rows
        ),
        default=0.0,
    )
    max_action = max((risk_ratio(row.get("action_priority_score")) for row in rows), default=0.0)
    min_resilience = min((risk_ratio(row.get("resilience_score")) for row in rows), default=0.0)
    early_count = sum(1 for row in rows if int(to_float(row.get("early_warning_flag")) or 0) > 0)
    change_count = sum(1 for row in rows if int(to_float(row.get("change_point_flag")) or 0) > 0)
    zone = supplier_risk_worst_zone(rows)
    robust_decision = ""
    if supplier_row:
        max_risk = max(max_risk, risk_ratio(supplier_row.get("max_risk_probability_proxy_4w")))
        max_high = max(max_high, risk_ratio(supplier_row.get("max_risk_probability_high_proxy_4w")))
        max_margin = max(
            max_margin,
            max(
                0.0,
                risk_ratio(supplier_row.get("max_risk_probability_high_proxy_4w"))
                - risk_ratio(supplier_row.get("max_risk_probability_proxy_4w")),
            ),
        )
        max_action = max(max_action, risk_ratio(supplier_row.get("max_action_priority_score")))
        min_resilience = risk_ratio(supplier_row.get("min_resilience_score")) or min_resilience
        zone = str(supplier_row.get("worst_decision_zone") or zone)
        robust_decision = str(supplier_row.get("robust_decision") or "")
    if not robust_decision and rows:
        robust_decision = str(max(rows, key=lambda row: risk_ratio(row.get("action_priority_score"))).get("robust_decision") or "")
    return [
        {"label": "Noeud analyse", "value": display_node_label(node_id)},
        {"label": "Lecture", "value": "criticite fournisseurs entrants" if destination_view else "criticite fournisseur"},
        {"label": "Niveau de criticite", "value": supplier_risk_zone_label(zone)},
        {"label": "Score criticite fournisseur", "value": fmt_pct(100.0 * max_action)},
        {"label": "Score menace fournisseur", "value": fmt_pct(100.0 * max_risk)},
        {"label": "Borne haute prudente", "value": fmt_pct(100.0 * max_high)},
        {"label": "Marge incertitude scoring", "value": fmt_pct(100.0 * max_margin)},
        {"label": "Score priorite action", "value": fmt_pct(100.0 * max_action)},
        {"label": "Marge de recuperation min", "value": fmt_pct(100.0 * min_resilience)},
        {"label": "Couples analyses", "value": str(len(rows))},
        {"label": "Alertes faibles actives", "value": str(early_count)},
        {"label": "Ruptures de tendance detectees", "value": str(change_count)},
        {"label": "Action prudente", "value": supplier_risk_action_label(robust_decision)},
    ]


def supplier_risk_node_metric(
    node_id: str,
    rows: list[dict[str, str]],
    *,
    supplier_row: dict[str, str] | None = None,
    destination_view: bool = False,
) -> dict[str, Any] | None:
    summary_lines = supplier_risk_summary_lines(
        node_id,
        rows,
        supplier_row=supplier_row,
        destination_view=destination_view,
    )
    if not summary_lines:
        return None
    zone = supplier_risk_worst_zone(rows)
    if supplier_row:
        zone = str(supplier_row.get("worst_decision_zone") or zone)
    action = max(
        [risk_ratio(row.get("action_priority_score")) for row in rows]
        + ([risk_ratio(supplier_row.get("max_action_priority_score"))] if supplier_row else [])
    )
    max_risk = max(
        [risk_ratio(row.get("risk_probability_proxy_4w")) for row in rows]
        + ([risk_ratio(supplier_row.get("max_risk_probability_proxy_4w"))] if supplier_row else [])
    )
    max_high = max(
        [risk_ratio(row.get("risk_probability_high_proxy_4w")) for row in rows]
        + ([risk_ratio(supplier_row.get("max_risk_probability_high_proxy_4w"))] if supplier_row else [])
    )
    max_uncertainty = max(
        [risk_ratio(row.get("uncertainty_pressure")) for row in rows]
        + [max(0.0, max_high - max_risk)]
    )
    return {
        "title": f"Criticite fournisseurs - {display_node_label(node_id)}",
        "summary_lines": summary_lines,
        "decision_zone": zone,
        "zone_color": supplier_risk_zone_color(zone),
        "zone_rank": supplier_risk_zone_rank(zone),
        "action_priority_score": round(action, 6),
        "risk_probability": round(max_risk, 6),
        "risk_probability_high": round(max_high, 6),
        "prediction_uncertainty": round(max_uncertainty, 6),
    }


def supplier_risk_trajectory_asset(
    node_id: str,
    rows: list[dict[str, str]],
    *,
    title_suffix: str,
) -> dict[str, Any] | None:
    if not rows:
        return None
    weekly: dict[int, dict[str, float]] = defaultdict(
        lambda: {
            "risk": 0.0,
            "high": 0.0,
            "action": 0.0,
            "resilience": 1.0,
            "warning": 0.0,
        }
    )
    for row in rows:
        week = int(to_float(row.get("week_index")) or 0)
        bucket = weekly[week]
        bucket["risk"] = max(bucket["risk"], risk_ratio(row.get("risk_probability_proxy_4w")))
        bucket["high"] = max(bucket["high"], risk_ratio(row.get("risk_probability_high_proxy_4w")))
        bucket["action"] = max(bucket["action"], risk_ratio(row.get("action_priority_score")))
        resilience_value = to_float(row.get("resilience_score"))
        if resilience_value is not None and not math.isnan(resilience_value):
            bucket["resilience"] = min(bucket["resilience"], max(0.0, min(1.0, resilience_value)))
        bucket["warning"] = max(bucket["warning"], risk_ratio(row.get("early_warning_score")))
    points = sorted(weekly.items())
    if not points:
        return None
    series_map = {
        "Score menace (%)": [(week * 7, data["risk"] * 100.0) for week, data in points],
        "Borne haute prudente (%)": [(week * 7, data["high"] * 100.0) for week, data in points],
        "Score criticite fournisseur (%)": [(week * 7, data["action"] * 100.0) for week, data in points],
        "Marge recuperation min (%)": [(week * 7, data["resilience"] * 100.0) for week, data in points],
        "Alerte faible max (%)": [(week * 7, data["warning"] * 100.0) for week, data in points],
    }
    figure = build_line_chart_figure(
        series_map,
        title=f"{display_node_label(node_id)} - {title_suffix}",
        y_label="% / score",
        note="Points hebdomadaires projetes sur l'axe jour de la simulation.",
        series_styles={
            "Score menace (%)": {"color": "#be123c"},
            "Borne haute prudente (%)": {"color": "#dc2626", "dash": "dash"},
            "Score criticite fournisseur (%)": {"color": "#7c3aed"},
            "Marge recuperation min (%)": {"color": "#0f766e"},
            "Alerte faible max (%)": {"color": "#d97706"},
        },
    )
    return {"figure": figure} if figure else None


def supplier_risk_pair_table_asset(
    node_id: str,
    rows: list[dict[str, str]],
    *,
    item_labels: dict[str, str],
    title: str,
) -> dict[str, str] | None:
    if not rows:
        return None
    top_rows = sorted(rows, key=lambda row: risk_ratio(row.get("action_priority_score")), reverse=True)[:10]
    table_rows = []
    for row in top_rows:
        item_id = str(row.get("item_id") or "")
        table_rows.append(
            [
                item_labels.get(item_id, compact_item_label(item_id)),
                display_node_label(str(row.get("supplier_id") or "")),
                display_node_label(str(row.get("dst_node_id") or "")),
                supplier_risk_zone_label(row.get("decision_zone")),
                risk_pct(row.get("risk_probability_proxy_4w")),
                risk_pct(row.get("risk_probability_high_proxy_4w")),
                risk_pct(row.get("action_priority_score")),
                risk_pct(row.get("resilience_score")),
            ]
        )
    return data_html_asset(
        title,
        f"{display_node_label(node_id)} - top couples par priorite action",
        [
            (
                "Couples fournisseur / article / site",
                render_data_table(
                    ["Item", "Fournisseur", "Site", "Niveau criticite", "Score menace", "Borne haute prudente", "Score criticite", "Recuperation"],
                    table_rows,
                ),
            )
        ],
    )


def supplier_risk_decision_asset(node_id: str, rows: list[dict[str, str]]) -> dict[str, str] | None:
    if not rows:
        return None
    top = max(rows, key=lambda row: risk_ratio(row.get("action_priority_score")))
    risk_score = max(
        risk_ratio(top.get("risk_probability_proxy_4w")),
        risk_ratio(top.get("action_priority_score")),
        0.45 if supplier_risk_zone_rank(top.get("decision_zone")) >= 2 else 0.0,
    )
    prediction_uncertainty = max(
        risk_ratio(top.get("uncertainty_pressure")),
        max(
            0.0,
            risk_ratio(top.get("risk_probability_high_proxy_4w"))
            - risk_ratio(top.get("risk_probability_proxy_4w")),
        ),
    )
    risk_is_high = risk_score >= 0.35
    uncertainty_is_high = prediction_uncertainty >= 0.20
    if risk_is_high and uncertainty_is_high:
        current_cell = "Menace forte / incertitude forte"
        current_action = "Confirmer vite le signal et engager une mitigation prudente."
    elif risk_is_high:
        current_cell = "Menace forte / incertitude faible"
        current_action = "Agir directement: le probleme est suffisamment confirme."
    elif uncertainty_is_high:
        current_cell = "Menace faible / incertitude forte"
        current_action = "Reduire l'angle mort: couverture donnees, monitoring, confirmation fournisseur."
    else:
        current_cell = "Menace faible / incertitude faible"
        current_action = "Surveillance normale."

    def matrix_cell(title: str, text: str, action: str, *, key: str, level: str) -> str:
        current_class = " current" if key == current_cell else ""
        return (
            f"<div class=\"decisionMatrixCell {html.escape(level)}{current_class}\">"
            f"<div class=\"decisionMatrixCellTitle\">{html.escape(title)}</div>"
            f"<div class=\"decisionMatrixCellText\">{html.escape(text)}</div>"
            f"<div class=\"decisionMatrixCellAction\">{html.escape(action)}</div>"
            "</div>"
        )

    matrix_html = "".join(
        [
            "<div class=\"decisionMatrix\">",
            matrix_cell(
                "Menace forte / incertitude faible",
                "Menace metier elevee et evaluation suffisamment stable.",
                "Action: mitigation immediate.",
                key="Menace forte / incertitude faible",
                level="alert",
            ),
            matrix_cell(
                "Menace forte / incertitude forte",
                "Menace serieuse, mais largeur de prediction ou donnees fragiles.",
                "Action: confirmer vite + action prudente.",
                key="Menace forte / incertitude forte",
                level="alert",
            ),
            matrix_cell(
                "Menace faible / incertitude faible",
                "Menace faible et lecture suffisamment robuste.",
                "Action: routine.",
                key="Menace faible / incertitude faible",
                level="ok",
            ),
            matrix_cell(
                "Menace faible / incertitude forte",
                "Pas de menace confirmee, mais angle mort decisionnel.",
                "Action: renforcer donnees / monitoring.",
                key="Menace faible / incertitude forte",
                level="watch",
            ),
            "</div>",
        ]
    )
    decision_rows = [
        ["Faible", "performance correcte, menace faible, incertitude maitrisee", "routine"],
        ["Modere", "signaux faibles ou incertitude visible", "surveillance, donnees, confirmation fournisseur"],
        ["Eleve", "borne prudente elevee ou recuperation fragile", "action preventive: stock, capacite, audit, allocation"],
        ["Critique", "menace elevee + criticite + faible marge de recuperation", "action prudente immediate: dual source, expedite, replanning"],
    ]
    return data_html_asset(
        f"{display_node_label(node_id)} - action recommandee",
        "Lecture metier: le score de menace decrit la tension fournisseur; l'incertitude decrit la confiance dans cette evaluation. L'action recommandee croise les deux.",
        [
            (
                "Action proposee",
                render_data_kv(
                    [
                        ("Niveau de criticite principal", supplier_risk_zone_label(top.get("decision_zone"))),
                        ("Action recommandee", supplier_risk_action_label(top.get("recommended_action"))),
                        ("Action prudente", supplier_risk_action_label(top.get("robust_decision"))),
                        ("Temps de retour estime", f"{fmt_qty(top.get('time_to_recover_weeks_proxy'), 1)} semaines"),
                        ("Chute de performance estimee", risk_pct(top.get("performance_drop_proxy"))),
                        ("Incertitude", risk_pct(top.get("uncertainty_pressure"))),
                        ("Case decisionnelle", current_cell),
                        ("Lecture", current_action),
                    ]
                ),
            ),
            (
                "Matrice decisionnelle: niveau de menace x confiance",
                matrix_html,
            ),
            ("Regles de lecture", render_data_table(["Niveau", "Situation", "Action"], decision_rows)),
        ],
    )


def supplier_risk_summary_asset(
    node_id: str,
    rows: list[dict[str, str]],
    *,
    supplier_row: dict[str, str] | None = None,
    destination_view: bool = False,
) -> dict[str, str] | None:
    summary_lines = supplier_risk_summary_lines(
        node_id,
        rows,
        supplier_row=supplier_row,
        destination_view=destination_view,
    )
    if not summary_lines:
        return None

    def numeric_values(field: str) -> list[float]:
        values: list[float] = []
        for row in rows:
            value = to_float(row.get(field))
            if value is None or math.isnan(value):
                continue
            values.append(float(value))
        return values

    def max_numeric(field: str) -> float | None:
        values = numeric_values(field)
        return max(values) if values else None

    def min_numeric(field: str) -> float | None:
        values = numeric_values(field)
        return min(values) if values else None

    def pct_field(value: float | None, digits: int = 1) -> str:
        return "n/a" if value is None else fmt_pct(value * 100.0, digits)

    def points_field(value: float | None, digits: int = 1) -> str:
        return "n/a" if value is None else f"{fmt_qty(value * 100.0, digits)} pts"

    def tooltip_attrs(tooltip: str | None) -> str:
        return f" data-tooltip=\"{html.escape(tooltip, quote=True)}\" tabindex=\"0\"" if tooltip else ""

    def tooltip_class(base_class: str, tooltip: str | None) -> str:
        return f"{base_class} riskTooltipHost" if tooltip else base_class

    top_risk_row = max(rows, key=lambda row: risk_ratio(row.get("risk_probability_proxy_4w"))) if rows else {}
    risk_component_rows = [
        ["Criticite supply", "20%", pct_field(to_float(top_risk_row.get("criticality_score"))), "Importance globale du couple fournisseur / article / site.", to_float(top_risk_row.get("criticality_score"))],
        ["Mono-source", "14%", pct_field(to_float(top_risk_row.get("mono_source_score"))), "Fragilite quand peu ou pas d'alternative fournisseur.", to_float(top_risk_row.get("mono_source_score"))],
        ["Stock fournisseur", "15%", pct_field(to_float(top_risk_row.get("stock_pressure"))), "Pression si le stock couvre mal le besoin et les delais.", to_float(top_risk_row.get("stock_pressure"))],
        ["Capacite fournisseur", "11%", pct_field(to_float(top_risk_row.get("capacity_pressure"))), "Pression si l'utilisation capacite est proche de la saturation.", to_float(top_risk_row.get("capacity_pressure"))],
        ["Delai matiere", "10%", pct_field(to_float(top_risk_row.get("lead_time_pressure"))), "Pression issue des delais observes et de leur prudence.", to_float(top_risk_row.get("lead_time_pressure"))],
        ["Exposition volumes", "8%", pct_field(to_float(top_risk_row.get("flow_exposure_pressure"))), "Volume expose sur l'horizon court.", to_float(top_risk_row.get("flow_exposure_pressure"))],
        ["Sensibilite locale", "8%", pct_field(to_float(top_risk_row.get("sensitivity_pressure"))), "Impact observe quand on degrade ce fournisseur dans le modele.", to_float(top_risk_row.get("sensitivity_pressure"))],
        ["Dynamique / signaux faibles", "8%", pct_field(to_float(top_risk_row.get("dynamic_pressure"))), "Variation de flux, stock, capacite ou tendance.", to_float(top_risk_row.get("dynamic_pressure"))],
        ["Incertitude", "6%", pct_field(to_float(top_risk_row.get("uncertainty_pressure"))), "Penalite quand les donnees ou la prediction sont moins fiables.", to_float(top_risk_row.get("uncertainty_pressure"))],
    ]

    def component_status(value_text: str) -> str:
        value = to_float(str(value_text).replace("%", ""))
        if value is None:
            return "not_local"
        if value >= 50.0:
            return "sensitive"
        if value >= 20.0:
            return "watch"
        return "robust"

    def component_bar_width(value_text: str) -> float:
        value = to_float(str(value_text).replace("%", ""))
        if value is None:
            return 0.0
        return max(0.0, min(100.0, value))

    def component_weight_ratio(weight_text: str) -> float | None:
        weight = to_float(str(weight_text).replace("%", ""))
        if weight is None:
            return None
        return max(0.0, weight / 100.0)

    def component_contribution(row: list[Any]) -> float | None:
        weight = component_weight_ratio(str(row[1]))
        raw_value = to_float(row[4] if len(row) > 4 else None)
        if weight is None or raw_value is None:
            return None
        return weight * raw_value

    def top_component_drivers(limit: int = 3) -> list[list[Any]]:
        ranked = sorted(
            risk_component_rows,
            key=lambda row: (component_contribution(row) or 0.0, to_float(row[4] if len(row) > 4 else None) or 0.0),
            reverse=True,
        )
        return ranked[:limit]

    def component_tooltip(row: list[Any]) -> str:
        label, weight, value, note = row[:4]
        contribution = component_contribution(row)
        return "\n".join(
            [
                "Formule",
                "contribution au signal de menace = poids du composant x valeur du composant",
                "",
                "Calcul ici",
                f"{weight} x {value} = {points_field(contribution)}",
                "",
                "Lecture",
                str(note),
                "",
                "Important",
                "Cette contribution alimente le score de menace. Elle n'est pas une probabilite observee.",
            ]
        )

    def risk_component_cards_html(rows: list[list[Any]]) -> str:
        cards = ["<div class=\"riskComponentGrid\">"]
        for label, weight, value, note, raw_value in rows:
            status_key = component_status(value)
            width = component_bar_width(value)
            row = [label, weight, value, note, raw_value]
            contribution = component_contribution(row)
            tooltip = component_tooltip(row)
            cards.append(
                "".join(
                    [
                        f"<div class=\"{tooltip_class(f'riskComponentCard sensitivityStatus-{html.escape(status_key)}', tooltip)}\"{tooltip_attrs(tooltip)}>",
                        "<div class=\"riskComponentTop\">",
                        f"<div class=\"riskComponentLabel\">{html.escape(label)}</div>",
                        f"<div class=\"riskComponentWeight\">poids {html.escape(weight)}</div>",
                        "</div>",
                        f"<div class=\"riskComponentValue\">{html.escape(value)}</div>",
                        "<div class=\"riskComponentBarTrack\">",
                        f"<div class=\"riskComponentBar\" style=\"width:{width:.1f}%\"></div>",
                        "</div>",
                        f"<div class=\"riskComponentContribution\">contribution au signal de menace: {html.escape(pct_field(contribution))}</div>",
                        f"<div class=\"riskComponentNote\">{html.escape(note)}</div>",
                        "</div>",
                    ]
                )
            )
        cards.append("</div>")
        return "".join(cards)

    def risk_driver_summary_html() -> str:
        drivers = top_component_drivers(3)
        if not drivers:
            return "<div class=\"panelEmptyState dataEmptyState\">Aucun signal de menace exploitable pour ce noeud.</div>"
        cards = ["<div class=\"riskDriverGrid\">"]
        for rank, row in enumerate(drivers, start=1):
            label, weight, value, note = row[:4]
            contribution = component_contribution(row)
            status_key = component_status(str(value))
            tooltip = component_tooltip(row)
            cards.append(
                "".join(
                    [
                        f"<div class=\"{tooltip_class(f'riskDriverCard sensitivityStatus-{html.escape(status_key)}', tooltip)}\"{tooltip_attrs(tooltip)}>",
                        f"<div class=\"riskDriverRank\">Signal {rank}</div>",
                        f"<div class=\"riskDriverTitle\">{html.escape(str(label))}</div>",
                        f"<div class=\"riskDriverValue\">{html.escape(str(value))}</div>",
                        f"<div class=\"riskDriverMeta\">poids {html.escape(str(weight))} ; contribution {html.escape(points_field(contribution))}</div>",
                        f"<div class=\"riskDriverNote\">{html.escape(str(note))}</div>",
                        "</div>",
                    ]
                )
            )
        cards.append("</div>")
        return "".join(cards)

    def risk_explanation_card(
        label: str,
        value: str,
        formula: str,
        note: str,
        status_key: str = "not_local",
        breakdown_rows: list[tuple[str, str]] | None = None,
        extra_class: str = "",
    ) -> str:
        breakdown_html = ""
        if breakdown_rows:
            breakdown_html = "".join(
                [
                    "<div class=\"riskExplanationBreakdown\">",
                    "".join(
                        "<div>"
                        f"<span>{html.escape(str(row_label))}</span>"
                        f"<b>{html.escape(str(row_value))}</b>"
                        "</div>"
                        for row_label, row_value in breakdown_rows
                    ),
                    "</div>",
                ]
            )
        class_names = "riskExplanationCard"
        if extra_class:
            class_names += f" {extra_class}"
        class_names += f" sensitivityStatus-{html.escape(status_key)}"
        return "".join(
            [
                f"<div class=\"{class_names}\">",
                f"<div class=\"riskExplanationLabel\">{html.escape(label)}</div>",
                f"<div class=\"riskExplanationValue\">{html.escape(value)}</div>",
                f"<div class=\"riskExplanationFormula\">{html.escape(formula)}</div>",
                breakdown_html,
                f"<div class=\"riskExplanationNote\">{html.escape(note)}</div>",
                "</div>",
            ]
        )

    def risk_signal_card_html(*, primary: bool = False) -> str:
        risk_value = risk_ratio(top_risk_row.get("risk_probability_proxy_4w"))
        uncertainty_value = risk_ratio(top_risk_row.get("uncertainty_pressure"))
        risk_signal = risk_ratio(top_risk_row.get("risk_signal"))
        criticality_value = to_float(top_risk_row.get("criticality_score"))
        mono_source_value = to_float(top_risk_row.get("mono_source_score"))
        stock_value = to_float(top_risk_row.get("stock_pressure"))
        capacity_value = to_float(top_risk_row.get("capacity_pressure"))
        lead_value = to_float(top_risk_row.get("lead_time_pressure"))
        exposure_value = to_float(top_risk_row.get("flow_exposure_pressure"))
        sensitivity_value = to_float(top_risk_row.get("sensitivity_pressure"))
        dynamic_value = to_float(top_risk_row.get("dynamic_pressure"))
        return risk_explanation_card(
            "Score de menace",
            risk_pct(risk_value),
            "courbe S du signal de menace",
            "Indicateur principal: menace a 4 semaines exprimee en score de decision. Ce n'est pas une probabilite historique observee.",
            component_status(risk_pct(risk_value)),
            [
                ("Formule signal", "signal de menace = somme(poids composant x valeur composant)"),
                (
                    "Application signal",
                    " + ".join(
                        [
                            f"20% x criticite {pct_field(criticality_value)}",
                            f"14% x mono-source {pct_field(mono_source_value)}",
                            f"15% x stock {pct_field(stock_value)}",
                            f"11% x capacite {pct_field(capacity_value)}",
                            f"10% x delai {pct_field(lead_value)}",
                            f"8% x exposition {pct_field(exposure_value)}",
                            f"8% x sensibilite {pct_field(sensitivity_value)}",
                            f"8% x dynamique {pct_field(dynamic_value)}",
                            f"6% x incertitude {pct_field(uncertainty_value)}",
                        ]
                    ),
                ),
                ("Resultat signal", pct_field(risk_signal)),
                ("Formule score", "score menace = courbe S(-3 + 5 x signal menace)"),
                ("Application score", f"courbe S(-3 + 5 x {pct_field(risk_signal)}) = {risk_pct(risk_value)}"),
            ],
            extra_class="riskPrimaryCard" if primary else "",
        )

    def risk_signal_components_html() -> str:
        return "".join(
            [
                "<div class=\"riskSignalFrame\">",
                "<div class=\"riskSignalHero\">",
                risk_signal_card_html(primary=True),
                "</div>",
                "<div class=\"riskSignalCompositionHead\">",
                "<div class=\"riskSignalCompositionTitle\">Composition de l'indicateur principal</div>",
                "<div class=\"riskSignalCompositionText\">Chaque carte reprend un terme de la formule du signal de menace, dans l'ordre exact du calcul.</div>",
                "</div>",
                risk_component_cards_html(risk_component_rows),
                "</div>",
            ]
        )

    def risk_indicator_section_html(title: str, note: str, cards: list[str]) -> str:
        return "".join(
            [
                "<div class=\"riskIndicatorSection\">",
                "<div class=\"riskIndicatorSectionHead\">",
                f"<div class=\"riskIndicatorSectionTitle\">{html.escape(title)}</div>",
                f"<div class=\"riskIndicatorSectionNote\">{html.escape(note)}</div>",
                "</div>",
                "<div class=\"riskExplanationGrid\">",
                "".join(cards),
                "</div>",
                "</div>",
            ]
        )

    def risk_explanation_cards_html() -> str:
        risk_value = risk_ratio(top_risk_row.get("risk_probability_proxy_4w"))
        high_value = risk_ratio(top_risk_row.get("risk_probability_high_proxy_4w"))
        uncertainty_value = risk_ratio(top_risk_row.get("uncertainty_pressure"))
        criticality_value = to_float(top_risk_row.get("criticality_score"))
        local_criticality_value = to_float(top_risk_row.get("local_criticality_score"))
        data_quality = to_float(top_risk_row.get("data_quality_score"))
        data_gap = None if data_quality is None else max(0.0, min(1.0, 1.0 - data_quality))
        lead_q50 = to_float(top_risk_row.get("lead_days_q50"))
        lead_width = to_float(top_risk_row.get("lead_interval_width_days"))
        lead_uncertainty = to_float(top_risk_row.get("lead_uncertainty_pressure"))
        if lead_q50 is not None and lead_q50 > 0.0 and lead_width is not None:
            lead_uncertainty = max(0.0, min(1.0, lead_width / lead_q50))
        uncertainty_margin = max(0.0, high_value - risk_value)
        sensitivity_value = to_float(top_risk_row.get("sensitivity_pressure"))
        sensitivity_external_pressure = to_float(top_risk_row.get("sensitivity_external_qty_delta_pressure"))
        sensitivity_external_qty = to_float(top_risk_row.get("sensitivity_external_qty_delta"))
        sensitivity_fill_pressure = to_float(top_risk_row.get("sensitivity_fill_rate_drop_pressure"))
        sensitivity_fill_drop = to_float(top_risk_row.get("sensitivity_fill_rate_drop"))
        priority_value = risk_ratio(top_risk_row.get("action_priority_score"))
        criticality_factor = 0.35 + 0.65 * max(criticality_value or 0.0, local_criticality_value or 0.0)
        sensitivity_factor = 0.75 + 0.25 * (sensitivity_value or 0.0)
        lead_observation_count = to_float(top_risk_row.get("lead_observation_count"))
        capacity_observations = to_float(top_risk_row.get("capacity_observations"))
        stock_observations = to_float(top_risk_row.get("stock_observations"))
        active_week_count = to_float(top_risk_row.get("active_week_count"))
        data_quality_lead = to_float(top_risk_row.get("data_quality_lead_score"))
        data_quality_capacity = to_float(top_risk_row.get("data_quality_capacity_score"))
        data_quality_stock = to_float(top_risk_row.get("data_quality_stock_score"))
        data_quality_criticality = to_float(top_risk_row.get("data_quality_criticality_score"))
        data_quality_active = to_float(top_risk_row.get("data_quality_active_score"))
        sensitivity_lowest_scale = to_float(top_risk_row.get("sensitivity_lowest_acceptable_scale"))
        sensitivity_first_bad = to_float(top_risk_row.get("sensitivity_first_unacceptable_level"))
        sensitivity_threshold_text = (
            f"niveau acceptable min {fmt_qty(sensitivity_lowest_scale, 3)} ; premier niveau degrade {fmt_qty(sensitivity_first_bad, 3)}"
            if sensitivity_first_bad is not None and sensitivity_first_bad > 0.0
            else f"niveau acceptable min {fmt_qty(sensitivity_lowest_scale, 3)} ; aucun niveau degrade detecte dans la grille"
        )

        data_quality_card = risk_explanation_card(
            "Couverture des donnees",
            pct_field(data_quality),
            "proxy de completude des informations disponibles",
            "Mesure seulement si les champs necessaires au scoring sont presents et suffisamment couverts. Ce n'est pas une mesure de fiabilite ni de qualite auditee de la donnee.",
            component_status(pct_field(data_gap)),
            [
                ("Role", "sert a majorer l'incertitude quand il manque des champs utiles"),
                ("Echelle", "100% = champs utiles bien couverts ; 0% = trop peu d'informations exploitables"),
                ("Formule", "couverture donnees = moyenne(couverture delai, capacite, stock, criticite, historique actif)"),
                ("Observations delai", f"{fmt_qty(lead_observation_count, 0)} obs. -> {pct_field(data_quality_lead)}"),
                ("Donnees capacite", f"{fmt_qty(capacity_observations, 0)} lignes -> {pct_field(data_quality_capacity)}"),
                ("Donnees stock", f"{fmt_qty(stock_observations, 0)} lignes -> {pct_field(data_quality_stock)}"),
                ("Criticite renseignee", pct_field(data_quality_criticality)),
                ("Historique actif", f"{fmt_qty(active_week_count, 0)} semaines -> {pct_field(data_quality_active)}"),
                ("Application", f"moyenne({pct_field(data_quality_lead)}, {pct_field(data_quality_capacity)}, {pct_field(data_quality_stock)}, {pct_field(data_quality_criticality)}, {pct_field(data_quality_active)}) = {pct_field(data_quality)}"),
            ],
        )
        uncertainty_card = risk_explanation_card(
            "Incertitude",
            pct_field(uncertainty_value),
            "60% manque couverture donnees + 40% dispersion delai",
            "Mesure le doute autour du score, pas un risque supplementaire observe. Plus elle monte, plus la lecture doit etre verifiee.",
            component_status(pct_field(uncertainty_value)),
            [
                ("Formule", "incertitude = 60% x manque couverture donnees + 40% x dispersion delai"),
                ("Manque couverture donnees", f"1 - {pct_field(data_quality)} = {pct_field(data_gap)}"),
                ("Dispersion delai", f"{fmt_days(lead_width, 1)} / {fmt_days(lead_q50, 1)} = {pct_field(lead_uncertainty)}"),
                ("Application", f"60% x {pct_field(data_gap)} + 40% x {pct_field(lead_uncertainty)} = {pct_field(uncertainty_value)}"),
            ],
        )
        margin_card = risk_explanation_card(
            "Marge de prudence",
            points_field(uncertainty_margin),
            "hypothese de scoring: +4 pts fixes + jusqu'a +26 pts selon incertitude",
            "Tampon de scoring ajoute au score menace pour eviter de sous-lire un fournisseur quand la lecture est moins fiable. Ce n'est pas une donnee observee.",
            component_status(risk_pct(uncertainty_margin)),
            [
                ("Statut", "hypothese de scoring a calibrer avec incidents reels ou Monte Carlo"),
                ("Formule", "majoration prudente = base prudence + coefficient incertitude x incertitude"),
                ("Base fixe", "+4.0 pts"),
                ("Coefficient incertitude", "26.0 pts"),
                ("Incertitude utilisee", pct_field(uncertainty_value)),
                ("Part liee a l'incertitude", f"26.0 pts x {pct_field(uncertainty_value)} = {points_field(0.26 * uncertainty_value)}"),
                ("Application", f"4.0 pts + 26.0 pts x {pct_field(uncertainty_value)} = {points_field(uncertainty_margin)}"),
            ],
        )
        high_card = risk_explanation_card(
            "Borne haute prudente",
            risk_pct(high_value),
            "score menace + marge de prudence",
            "Borne haute de lecture pour decision prudente. Ce n'est ni une probabilite terrain ni une prediction historique.",
            component_status(risk_pct(high_value)),
            [
                ("Formule", "borne haute prudente = score menace + marge de prudence"),
                ("Score menace", risk_pct(risk_value)),
                ("Marge de prudence", points_field(uncertainty_margin)),
                ("Application", f"{risk_pct(risk_value)} + {points_field(uncertainty_margin)} = {risk_pct(high_value)}"),
            ],
        )
        sensitivity_card = risk_explanation_card(
            "Impact sensibilite fournisseur",
            pct_field(sensitivity_value),
            "indice de sensibilite: 65% compensation + 35% baisse disponibilite produit",
            "Ce score resume l'impact observe quand on degrade ce fournisseur dans le modele. Il ne mesure pas la vraie capacite fournisseur.",
            component_status(pct_field(sensitivity_value)),
            [
                ("Statut", "indice issu des variations de sensibilite, pas une donnee terrain"),
                ("Role", "utilise dans le signal de menace avec un poids de 8%, puis dans le facteur sensibilite"),
                ("Formule", "impact sensibilite = 65% x score compensation matiere + 35% x score baisse disponibilite produit"),
                ("Appro fournisseur", f"score {pct_field(sensitivity_external_pressure)} ; delta quantite {fmt_qty(sensitivity_external_qty, 1)}"),
                ("Baisse disponibilite produit", f"score {pct_field(sensitivity_fill_pressure)} ; baisse observee {pct_field(sensitivity_fill_drop)}"),
                ("Seuil de test", sensitivity_threshold_text),
                ("Point important", "0% = aucun impact observe dans les niveaux testes, pas une garantie fournisseur reelle"),
                ("Application", f"65% x {pct_field(sensitivity_external_pressure)} + 35% x {pct_field(sensitivity_fill_pressure)} = {pct_field(sensitivity_value)}"),
            ],
        )
        criticality_factor_card = risk_explanation_card(
            "Facteur criticite",
            f"x{fmt_qty(criticality_factor, 3)}",
            "0.35 + 0.65 x max(criticite globale, criticite locale)",
            "Ce facteur augmente la priorite d'action quand le fournisseur est important pour le reseau ou pour le couple fournisseur / article / site.",
            component_status(pct_field(max(criticality_value or 0.0, local_criticality_value or 0.0))),
            [
                ("Statut", "facteur de priorisation, pas une mesure physique fournisseur"),
                ("Formule", "facteur criticite = 0.35 + 0.65 x max(criticite globale, criticite locale)"),
                ("Criticite globale", pct_field(criticality_value)),
                ("Criticite locale", pct_field(local_criticality_value)),
                ("Valeur retenue", f"max({pct_field(criticality_value)}, {pct_field(local_criticality_value)}) = {pct_field(max(criticality_value or 0.0, local_criticality_value or 0.0))}"),
                ("Echelle", "x0.35 minimum ; x1.00 maximum"),
                ("Pourquoi 0.35 minimum", "un fournisseur peu critique garde une priorite residuelle si le score de menace monte"),
                ("Application", f"0.35 + 0.65 x {pct_field(max(criticality_value or 0.0, local_criticality_value or 0.0))} = x{fmt_qty(criticality_factor, 3)}"),
            ],
        )
        sensitivity_factor_card = risk_explanation_card(
            "Facteur sensibilite",
            f"x{fmt_qty(sensitivity_factor, 3)}",
            "0.75 + 0.25 x sensibilite locale",
            "Ce facteur ajuste la criticite avec l'impact observe quand on degrade ce fournisseur dans le modele.",
            component_status(pct_field(sensitivity_value)),
            [
                ("Statut", "facteur de priorisation derive de la sensibilite fournisseur"),
                ("Formule", "facteur sensibilite = 0.75 + 0.25 x impact sensibilite"),
                ("Sensibilite locale", pct_field(sensitivity_value)),
                ("Echelle", "x0.75 minimum ; x1.00 maximum"),
                ("Pourquoi 0.75 minimum", "une variation neutre dans le modele ne prouve pas l'absence de criticite fournisseur"),
                ("Application", f"0.75 + 0.25 x {pct_field(sensitivity_value)} = x{fmt_qty(sensitivity_factor, 3)}"),
            ],
        )
        priority_card = risk_explanation_card(
            "Score criticite fournisseur",
            risk_pct(priority_value),
            "score menace x facteur criticite x facteur sensibilite",
            "Score d'arbitrage: il combine menace, importance fournisseur et fragilite locale.",
            component_status(risk_pct(priority_value)),
            [
                ("Formule", "score criticite fournisseur = score menace x facteur criticite x facteur sensibilite"),
                ("Score menace", risk_pct(risk_value)),
                ("Facteur criticite", f"x{fmt_qty(criticality_factor, 3)}"),
                ("Facteur sensibilite", f"x{fmt_qty(sensitivity_factor, 3)}"),
                ("Application", f"{risk_pct(risk_value)} x {fmt_qty(criticality_factor, 3)} x {fmt_qty(sensitivity_factor, 3)} = {risk_pct(priority_value)}"),
            ],
        )
        return "".join(
            [
                "<div class=\"riskIndicatorStack\">",
                risk_indicator_section_html(
                    "Incertitude et borne prudente",
                    "Pourquoi la borne prudente peut etre plus haute que le score de menace central.",
                    [data_quality_card, uncertainty_card, margin_card, high_card],
                ),
                risk_indicator_section_html(
                    "Sensibilite fournisseur",
                    "Ce que montrent les variations de sensibilite pour ce fournisseur.",
                    [sensitivity_card],
                ),
                risk_indicator_section_html(
                    "Score criticite et action",
                    "Comment le score de menace devient une priorite de pilotage.",
                    [criticality_factor_card, sensitivity_factor_card, priority_card],
                ),
                "</div>",
            ]
        )

    def risk_detail_html() -> str:
        return "".join(
            [
                "<details class=\"sensitivityDetails\">",
                "<summary>Afficher le calcul detaille</summary>",
                "<div class=\"riskDetailBlock\">",
                "<div class=\"riskDetailTitle\">Formule utilisee pour ce noeud</div>",
                render_data_table(["Etape", "Formule", "Valeur ici"], risk_formula_rows),
                "<div class=\"riskDetailTitle\">Valeurs en tableau</div>",
                render_data_table(["Composant", "Poids", "Valeur ici", "Lecture"], [row[:4] for row in risk_component_rows]),
                "</div>",
                "</details>",
            ]
        )

    def summary_value(label: str) -> str:
        return str(next((entry.get("value") for entry in summary_lines if entry.get("label") == label), "n/a"))

    def risk_level_status_key(level: str) -> str:
        normalized = str(level or "").strip().lower()
        if normalized in {"critique", "eleve", "eleve"}:
            return "sensitive"
        if normalized in {"modere", "modere"}:
            return "watch"
        if normalized == "faible":
            return "robust"
        return "not_local"

    def risk_fact(label: str, value: str, tooltip: str | None = None) -> str:
        return "".join(
            [
                f"<div class=\"{tooltip_class('', tooltip).strip()}\"{tooltip_attrs(tooltip)}>",
                f"<span>{html.escape(label)}</span>",
                f"<b>{html.escape(value)}</b>",
                "</div>",
            ]
        )

    def risk_summary_dashboard_html() -> str:
        node_label = summary_value("Noeud analyse")
        lecture = summary_value("Lecture")
        level = summary_value("Niveau de criticite")
        criticity = summary_value("Score criticite fournisseur")
        risk_value = summary_value("Score menace fournisseur")
        high_value = summary_value("Borne haute prudente")
        uncertainty_gap = summary_value("Marge incertitude scoring")
        priority = summary_value("Score priorite action")
        recovery = summary_value("Marge de recuperation min")
        couples = summary_value("Couples analyses")
        alerts = summary_value("Alertes faibles actives")
        trends = summary_value("Ruptures de tendance detectees")
        action = summary_value("Action prudente")
        top_driver = (top_component_drivers(1) or [["n/a", "n/a", "n/a", "", None]])[0]
        top_driver_text = f"{top_driver[0]} ({points_field(component_contribution(top_driver))})"
        data_quality = to_float(top_risk_row.get("data_quality_score"))
        risk_signal = risk_ratio(top_risk_row.get("risk_signal"))
        risk_max_numeric = max_numeric("risk_probability_proxy_4w")
        high_max_numeric = max_numeric("risk_probability_high_proxy_4w")
        uncertainty_value = risk_ratio(top_risk_row.get("uncertainty_pressure"))
        uncertainty_margin = max(0.0, risk_ratio(top_risk_row.get("risk_probability_high_proxy_4w")) - risk_ratio(top_risk_row.get("risk_probability_proxy_4w")))
        top_action_row = max(rows, key=lambda row: risk_ratio(row.get("action_priority_score"))) if rows else top_risk_row
        action_risk = risk_ratio(top_action_row.get("risk_probability_proxy_4w"))
        action_criticality = max(
            to_float(top_action_row.get("criticality_score")) or 0.0,
            to_float(top_action_row.get("local_criticality_score")) or 0.0,
        )
        action_sensitivity = to_float(top_action_row.get("sensitivity_pressure")) or 0.0
        action_criticality_factor = 0.35 + 0.65 * action_criticality
        action_sensitivity_factor = 0.75 + 0.25 * action_sensitivity
        min_resilience_row = min(rows, key=lambda row: risk_ratio(row.get("resilience_score"))) if rows else top_risk_row
        stock_absorption = 1.0 - (to_float(min_resilience_row.get("stock_pressure")) or 0.0)
        capacity_headroom = 1.0 - (to_float(min_resilience_row.get("capacity_pressure")) or 0.0)
        recovery_slope = 1.0 - (to_float(min_resilience_row.get("dynamic_pressure")) or 0.0)
        source_flexibility = 1.0 - (to_float(min_resilience_row.get("mono_source_score")) or 0.0)
        sensitivity_resilience = 1.0 - (to_float(min_resilience_row.get("sensitivity_pressure")) or 0.0)
        resilience_data_quality = to_float(min_resilience_row.get("data_quality_score"))
        recovery_min_numeric = min_numeric("resilience_score")
        data_quality_lead = to_float(top_risk_row.get("data_quality_lead_score"))
        data_quality_capacity = to_float(top_risk_row.get("data_quality_capacity_score"))
        data_quality_stock = to_float(top_risk_row.get("data_quality_stock_score"))
        data_quality_criticality = to_float(top_risk_row.get("data_quality_criticality_score"))
        data_quality_active = to_float(top_risk_row.get("data_quality_active_score"))
        alert_count = sum(1 for row in rows if int(to_float(row.get("early_warning_flag")) or 0) > 0)
        alert_score_max = max_numeric("early_warning_score")
        trend_count = sum(1 for row in rows if int(to_float(row.get("change_point_flag")) or 0) > 0)
        trend_total = len(rows)
        trend_score_max = max_numeric("change_point_score")
        trend_dynamic_max = max_numeric("dynamic_pressure")
        risk_tooltip = "\n".join(
            [
                "Formule",
                "score menace = courbe S(-3 + 5 x signal menace)",
                "",
                "Calcul ici",
                f"Signal menace = {pct_field(risk_signal)}",
                f"courbe S(-3 + 5 x {pct_field(risk_signal)}) = {risk_pct(risk_max_numeric)}",
                f"Resultat affiche = {risk_value}",
                "",
                "Lecture",
                "Score de decision a 4 semaines sur une echelle 0-100. Ce n'est pas une probabilite historique observee.",
            ]
        )
        high_tooltip = "\n".join(
            [
                "Formule",
                "borne prudente = score menace + majoration prudente",
                "",
                "Calcul ici",
                f"Score menace = {risk_pct(top_risk_row.get('risk_probability_proxy_4w'))}",
                f"Majoration prudente = 4 pts + 26 pts x incertitude {pct_field(uncertainty_value)} = {points_field(uncertainty_margin)}",
                f"Application = {risk_pct(top_risk_row.get('risk_probability_proxy_4w'))} + {points_field(uncertainty_margin)} = {risk_pct(top_risk_row.get('risk_probability_high_proxy_4w'))}",
                f"Max affiche = {risk_pct(high_max_numeric)}",
                "",
                "Lecture",
                "Borne haute de lecture quand les donnees sont moins completes ou les delais plus disperses. Ce n'est pas une probabilite terrain.",
            ]
        )
        priority_tooltip = "\n".join(
            [
                "Formule",
                "criticite fournisseur = menace fournisseur x importance supply x sensibilite locale",
                "",
                "Calcul ici",
                f"Menace fournisseur = {risk_pct(action_risk)}",
                f"Importance supply = 0.35 + 0.65 x {pct_field(action_criticality)} = x{fmt_qty(action_criticality_factor, 3)}",
                f"Sensibilite locale = 0.75 + 0.25 x {pct_field(action_sensitivity)} = x{fmt_qty(action_sensitivity_factor, 3)}",
                f"Application = {risk_pct(action_risk)} x {fmt_qty(action_criticality_factor, 3)} x {fmt_qty(action_sensitivity_factor, 3)} = {priority}",
                "",
                "Lecture",
                "Score de criticite fournisseur: plus il est haut, plus le fournisseur merite surveillance ou action.",
            ]
        )
        uncertainty_short_tooltip = "\n".join(
            [
                "Lecture",
                "La marge d'incertitude scoring n'est pas un KPI metier principal.",
                "",
                "Calcul",
                "marge = borne haute detail - menace centrale detail, calculee ligne par ligne",
                f"Marge affichee = {uncertainty_gap}",
                "",
                "Usage",
                "Elle sert seulement a savoir si la lecture est solide ou s'il faut verifier les donnees avant decision.",
            ]
        )
        recovery_tooltip = "\n".join(
            [
                "Formule",
                "marge recuperation = 25% stock + 20% capacite + 20% stabilite + 15% alternatives + 10% sensibilite + 10% couverture donnees",
                "",
                "Calcul ici",
                f"25% x stock {pct_field(stock_absorption)}",
                f"20% x capacite {pct_field(capacity_headroom)}",
                f"20% x stabilite {pct_field(recovery_slope)}",
                f"15% x alternatives {pct_field(source_flexibility)}",
                f"10% x sensibilite {pct_field(sensitivity_resilience)}",
                f"10% x couverture donnees {pct_field(resilience_data_quality)}",
                f"Resultat min affiche = {risk_pct(recovery_min_numeric)}",
                "",
                "Lecture",
                "Capacite estimee d'absorption et de retour a la normale dans le modele.",
            ]
        )
        driver_tooltip = component_tooltip(top_driver)
        data_quality_tooltip = "\n".join(
            [
                "Formule",
                "couverture donnees = moyenne(couverture delai, capacite, stock, criticite, historique actif)",
                "",
                "Calcul ici",
                f"Delai = {pct_field(data_quality_lead)}",
                f"Capacite = {pct_field(data_quality_capacity)}",
                f"Stock = {pct_field(data_quality_stock)}",
                f"Criticite = {pct_field(data_quality_criticality)}",
                f"Historique actif = {pct_field(data_quality_active)}",
                f"Moyenne = {pct_field(data_quality)}",
                "",
                "Lecture",
                "Proxy de completude des champs utiles au scoring, pas mesure de qualite auditee ni performance fournisseur.",
            ]
        )
        couples_tooltip = "\n".join(
            [
                "Formule",
                "couples analyses = nombre de couples fournisseur / article / site disponibles pour ce noeud",
                "",
                "Calcul ici",
                f"Lignes retenues = {trend_total}",
                f"Resultat affiche = {couples}",
                "",
                "Lecture",
                "Plus le nombre est faible, plus l'analyse locale doit etre lue prudemment.",
            ]
        )
        alert_tooltip = "\n".join(
            [
                "Formule",
                "alertes faibles = nombre de couples avec signal faible actif",
                "",
                "Regle de detection",
                "Alerte active si early_warning_score >= 45%.",
                "",
                "Calcul ici",
                f"Couples en alerte = {alert_count} / {trend_total}",
                f"Score alerte max = {pct_field(alert_score_max)}",
                f"Resultat affiche = {alerts}",
                "",
                "Lecture",
                "Signal avance: volatilite, baisse stock, acceleration capacite, incertitude delai.",
            ]
        )
        trend_tooltip = "\n".join(
            [
                "Formule",
                "Ruptures tendance = nombre de couples fournisseur / article / site avec rupture de tendance detectee.",
                "",
                "Regle de detection",
                "Rupture detectee si change_point_score >= 65%.",
                "",
                "Calcul ici",
                f"Couples detectes = {trend_count} / {trend_total}",
                f"Score rupture max = {pct_field(trend_score_max)}",
                f"Seuil = 65.0%",
                f"Resultat affiche = {trends}",
                "",
                "Lecture",
                f"Dynamique / signaux faibles max = {pct_field(trend_dynamic_max)}.",
            ]
        )
        status_key = risk_level_status_key(level)
        return "".join(
            [
                f"<div class=\"riskSummaryDashboard sensitivityStatus-{html.escape(status_key)}\">",
                "<div class=\"riskSummaryHero\">",
                "<div class=\"riskSummaryMain\">",
                f"<div class=\"sensitivityStatusPill\">Criticite {html.escape(level)}</div>",
                f"<div class=\"riskSummaryTitle\">{html.escape(node_label)} - {html.escape(lecture)}</div>",
                (
                    "<div class=\"riskSummaryText\">"
                    f"Criticite {html.escape(level)} ({html.escape(criticity)}). Principal signal : {html.escape(str(top_driver[0]))}. "
                    f"Couverture donnees : {html.escape(pct_field(data_quality))}. "
                    f"Action prudente : {html.escape(action)}."
                    "</div>"
                ),
                "</div>",
                "<div class=\"riskSummaryFacts\">",
                risk_fact("Score criticite fournisseur", criticity, priority_tooltip),
                risk_fact("Action recommandee", action),
                risk_fact("Signal principal", top_driver_text, driver_tooltip),
                risk_fact("Couverture donnees", pct_field(data_quality), data_quality_tooltip),
                risk_fact("Marge incertitude scoring", uncertainty_gap, uncertainty_short_tooltip),
                "</div>",
                "</div>",
                "</div>",
            ]
        )

    risk_formula_rows = [
        [
            "1. Signal de menace",
            "0.20 x criticite + 0.14 x mono-source + 0.15 x stock + 0.11 x capacite + 0.10 x delai + 0.08 x exposition + 0.08 x sensibilite + 0.08 x dynamique + 0.06 x incertitude",
            pct_field(to_float(top_risk_row.get("risk_signal"))),
        ],
        [
            "2. Score menace 4 semaines",
            "courbe S du signal: 1 / (1 + exp(-(-3 + 5 x signal menace)))",
            risk_pct(top_risk_row.get("risk_probability_proxy_4w")),
        ],
        [
            "3. Borne haute prudente",
            "score menace + marge de prudence ; marge = 4 pts + 26 pts x incertitude",
            risk_pct(top_risk_row.get("risk_probability_high_proxy_4w")),
        ],
        [
            "4. Score criticite fournisseur",
            "score menace x facteur criticite x facteur sensibilite",
            risk_pct(top_risk_row.get("action_priority_score")),
        ],
    ]
    explanation_rows = [
        [
            "Score menace fournisseur",
            "courbe S du signal de menace",
            risk_pct(max_numeric("risk_probability_proxy_4w")),
            "Menace a 4 semaines. Ce n'est pas une probabilite historique observee, c'est un score calibre entre 0 et 95%.",
        ],
        [
            "Borne haute prudente",
            "score menace + marge liee a l'incertitude",
            risk_pct(max_numeric("risk_probability_high_proxy_4w")),
            "Version haute de lecture, augmentee quand les donnees ou la prediction sont moins certaines.",
        ],
        [
            "Score criticite fournisseur",
            "score menace x criticite x sensibilite",
            risk_pct(max_numeric("action_priority_score")),
            "Score d'arbitrage: menace estimee, criticite locale, exposition volumes et marge de recuperation.",
        ],
        [
            "Marge de recuperation",
            "stock + capacite + dynamique + alternatives + couverture donnees",
            pct_field(min_numeric("resilience_score")),
            "Capacite estimee a absorber la perturbation puis revenir a la normale.",
        ],
        [
            "Niveau de criticite",
            "decision_zone",
            next((entry["value"] for entry in summary_lines if entry.get("label") == "Niveau de criticite"), "n/a"),
            "Classification lisible de la priorite: Faible, Modere, Eleve ou Critique.",
        ],
    ]
    observed_rows = [
        [
            "Delai matiere",
            "lead_days_avg_week / lead_days_q95",
            f"moy. max {fmt_days(max_numeric('lead_days_avg_week'), 1)} ; p95 max {fmt_days(max_numeric('lead_days_q95'), 1)}",
            "Delais observes sur les flux fournisseur vers site.",
        ],
        [
            "Fiabilite",
            "reliability_avg_week",
            f"min {pct_field(min_numeric('reliability_avg_week'))}",
            "Ratio moyen expedie / demande tiree fournisseur sur la semaine.",
        ],
        [
            "Stock fournisseur",
            "stock_min_of_week",
            f"min {fmt_qty(min_numeric('stock_min_of_week'), 1)}",
            "Stock minimum observe chez le fournisseur pour les couples couverts.",
        ],
        [
            "Capacite",
            "capacity_utilization_max_week",
            f"utilisation max {pct_field(max_numeric('capacity_utilization_max_week'))}",
            "Utilisation maximale de la capacite fournisseur modelee.",
        ],
        [
            "Criticite locale",
            "local_criticality_score / mono_source_score",
            f"criticite max {pct_field(max_numeric('local_criticality_score'))} ; mono-source max {pct_field(max_numeric('mono_source_score'))}",
            "Importance du fournisseur pour les articles/sites servis.",
        ],
        [
            "Sensibilite",
            "sensitivity_pressure",
            pct_field(max_numeric("sensitivity_pressure")),
            "Pression issue des variations de sensibilite: le systeme se degrade-t-il quand on degrade ce fournisseur ?",
        ],
        [
            "Incertitude scoring",
            "uncertainty_pressure / data_quality_score",
            f"incertitude max {pct_field(max_numeric('uncertainty_pressure'))} ; couverture donnees min {pct_field(min_numeric('data_quality_score'))}",
            "Completude des champs utiles au scoring, pas menace fournisseur additionnelle.",
        ],
        [
            "Exposition volumes",
            "expected_exposure_qty_4w_proxy",
            fmt_qty(sum(numeric_values("expected_exposure_qty_4w_proxy")), 1),
            "Volume attendu expose sur l'horizon de lecture.",
        ],
        [
            "Signaux faibles",
            "early_warning_flag / change_point_flag",
            f"alertes {sum(1 for row in rows if int(to_float(row.get('early_warning_flag')) or 0) > 0)} ; ruptures tendance {sum(1 for row in rows if int(to_float(row.get('change_point_flag')) or 0) > 0)}",
            "Indicateurs de degradation avant incident visible.",
        ],
    ]
    source_rows = [
        ["Flux / delais / fiabilite", "production_supplier_shipments_daily.csv", "envois, quantites tirees, delais, fiabilite"],
        ["Stocks fournisseur", "production_supplier_stocks_daily.csv", "stock journalier fournisseur"],
        ["Capacite fournisseur", "production_supplier_capacity_daily.csv", "capacite, utilisation, reste disponible"],
        ["Panel risque", "supplier_item_week_panel.csv", "agregation hebdomadaire et scores fournisseur-article-site"],
        ["Photo risque", "supplier_item_risk_kpi.csv / supplier_risk_kpi.csv", "derniere photo par couple et aggregation fournisseur"],
    ]

    def details_html(label: str, content: str, *, open_by_default: bool = False) -> str:
        open_attr = " open" if open_by_default else ""
        return "".join(
            [
                f"<details class=\"sensitivityDetails riskMethodDetails\"{open_attr}>",
                f"<summary>{html.escape(label)}</summary>",
                content,
                "</details>",
            ]
        )

    def risk_method_html() -> str:
        return details_html(
            "Afficher la methode, les formules et les sources",
            "".join(
                [
                    "<div class=\"riskMethodStack\">",
                    "<div class=\"riskMethodNote\">Les blocs ci-dessous servent a auditer le score. Ils ne sont pas necessaires pour la lecture operationnelle quotidienne.</div>",
                    "<div class=\"riskMethodSubTitle\">Calcul complet du signal de menace</div>",
                    risk_signal_components_html(),
                    "<div class=\"riskMethodSubTitle\">Indicateurs derives et hypotheses de scoring</div>",
                    risk_explanation_cards_html(),
                    "<div class=\"riskMethodSubTitle\">Tables d'audit</div>",
                    risk_detail_html(),
                    details_html(
                        "Afficher d'ou viennent les chiffres",
                        render_data_table(["Chiffre affiche", "Calcul / source", "Valeur ici", "Lecture"], explanation_rows),
                    ),
                    details_html(
                        "Afficher les signaux observes",
                        render_data_table(["Signal", "Champ utilise", "Valeur ici", "Lecture"], observed_rows),
                    ),
                    details_html(
                        "Afficher les sources de donnees",
                        render_data_table(["Bloc", "Fichier", "Contenu"], source_rows),
                    ),
                    "</div>",
                ]
            ),
        )

    return data_html_asset(
        f"{display_node_label(node_id)} - criticite fournisseurs",
        "Lecture courte: criticite fournisseur, confiance de l'estimation et action recommandee.",
        [
            ("Synthese", risk_summary_dashboard_html()),
            (
                "Raisons principales",
                risk_driver_summary_html(),
            ),
            ("Methode de calcul", risk_method_html()),
        ],
    )


def build_supplier_risk_hover_payloads(
    raw: dict[str, Any],
    *,
    supplier_risk_panel_csv: Path,
    supplier_risk_supplier_csv: Path,
    supplier_risk_pair_csv: Path,
    supplier_risk_summary_json: Path,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    panel_rows = read_csv_rows(supplier_risk_panel_csv)
    pair_rows = read_csv_rows(supplier_risk_pair_csv)
    supplier_rows = read_csv_rows(supplier_risk_supplier_csv)
    if not panel_rows and not pair_rows and not supplier_rows:
        return {}, {}, {}, {"nodes": {}, "global": {}}

    item_labels = item_label_lookup(raw)
    node_types = build_node_type_lookup(raw)
    supplier_by_id = {str(row.get("supplier_id") or ""): row for row in supplier_rows}
    latest_by_supplier: dict[str, list[dict[str, str]]] = defaultdict(list)
    latest_by_dst: dict[str, list[dict[str, str]]] = defaultdict(list)
    panel_by_supplier: dict[str, list[dict[str, str]]] = defaultdict(list)
    panel_by_dst: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in pair_rows:
        supplier_id = str(row.get("supplier_id") or "")
        dst_id = str(row.get("dst_node_id") or "")
        if supplier_id:
            latest_by_supplier[supplier_id].append(row)
        if dst_id:
            latest_by_dst[dst_id].append(row)
    for row in panel_rows:
        supplier_id = str(row.get("supplier_id") or "")
        dst_id = str(row.get("dst_node_id") or "")
        if supplier_id:
            panel_by_supplier[supplier_id].append(row)
        if dst_id:
            panel_by_dst[dst_id].append(row)

    supplier_hover: dict[str, Any] = {}
    factory_hover: dict[str, Any] = {}
    dc_hover: dict[str, Any] = {}
    metrics_nodes: dict[str, Any] = {}

    for supplier_id, rows in sorted(latest_by_supplier.items()):
        supplier_row = supplier_by_id.get(supplier_id)
        title_name = str((supplier_row or {}).get("supplier_name") or supplier_id)
        incoming = supplier_risk_summary_asset(supplier_id, rows, supplier_row=supplier_row)
        outgoing = supplier_risk_trajectory_asset(
            supplier_id,
            panel_by_supplier.get(supplier_id, []),
            title_suffix="trajectoire criticite / resilience fournisseur",
        )
        third = supplier_risk_pair_table_asset(
            supplier_id,
            rows,
            item_labels=item_labels,
            title=f"{display_node_label(supplier_id)} - couples risques",
        )
        fourth = supplier_risk_decision_asset(supplier_id, rows)
        supplier_hover[supplier_id] = {
            "incoming": incoming,
            "outgoing": outgoing,
            "third": third,
            "fourth": fourth,
        }
        metric = supplier_risk_node_metric(supplier_id, rows, supplier_row=supplier_row)
        if metric:
            metric["title"] = f"Criticite fournisseur - {title_name}"
            metrics_nodes[supplier_id] = metric

    for dst_id, rows in sorted(latest_by_dst.items()):
        incoming = supplier_risk_summary_asset(dst_id, rows, destination_view=True)
        outgoing = supplier_risk_trajectory_asset(
            dst_id,
            panel_by_dst.get(dst_id, []),
            title_suffix="criticite fournisseurs entrants",
        )
        third = supplier_risk_pair_table_asset(
            dst_id,
            rows,
            item_labels=item_labels,
            title=f"{display_node_label(dst_id)} - fournisseurs entrants",
        )
        fourth = supplier_risk_decision_asset(dst_id, rows)
        payload = {
            "incoming": incoming,
            "outgoing": outgoing,
            "third": third,
            "fourth": fourth,
        }
        node_type = node_types.get(dst_id, "")
        if node_type == "distribution_center":
            dc_hover[dst_id] = payload
        else:
            factory_hover[dst_id] = payload
        metric = supplier_risk_node_metric(dst_id, rows, destination_view=True)
        if metric:
            metrics_nodes[dst_id] = metric

    summary_json = load_json_dict(supplier_risk_summary_json)
    metrics = {
        "nodes": metrics_nodes,
        "global": {
            "title": "Criticite fournisseurs",
            "summary_lines": [
                {"label": "Fournisseurs", "value": str(summary_json.get("supplier_count", len(supplier_rows)))},
                {"label": "Couples", "value": str(summary_json.get("pair_count", len(pair_rows)))},
                {
                    "label": "Zones dernieres",
                    "value": supplier_risk_zone_counts_text(
                        summary_json.get("decision_zone_counts_latest")
                        if isinstance(summary_json.get("decision_zone_counts_latest"), dict)
                        else None
                    ),
                },
            ],
        },
    }
    return factory_hover, supplier_hover, dc_hover, metrics


def render_supplier_risk_catalog_html(
    node_id: str,
    *,
    applied_rows: list[dict[str, str]],
    configured_events: list[dict[str, Any]],
    economic_policy: dict[str, Any],
    ) -> str:
    configured_event_ids = {
        str(event.get("event_id") or "").strip()
        for event in configured_events
        if str(event.get("event_id") or "").strip()
    }
    applied_event_ids = {
        event_id.strip()
        for row in applied_rows
        for event_id in str(row.get("event_ids") or "").split(",")
        if event_id.strip()
    }
    applied_days = sorted(
        {
            int(to_float(row.get("day")) or 0)
            for row in applied_rows
            if str(row.get("day") or "").strip() != ""
        }
    )
    event_type_counts: dict[str, int] = defaultdict(int)
    for event in configured_events:
        risk_type = str(event.get("risk_type") or "autre").strip() or "autre"
        event_type_counts[risk_type] += 1
    dominant_type = max(event_type_counts.items(), key=lambda item: item[1])[0] if event_type_counts else "n/a"
    period_text = (
        f"J{min(applied_days)} -> J{max(applied_days)}"
        if applied_days
        else "aucune application dans le run"
    )
    status_text = (
        "evenements appliques dans ce run"
        if applied_event_ids
        else ("evenements configures mais non appliques" if configured_event_ids else "aucun evenement configure")
    )
    event_by_id = {
        str(event.get("event_id") or "").strip(): event
        for event in configured_events
        if str(event.get("event_id") or "").strip()
    }
    applied_configured_events = [
        event_by_id[event_id]
        for event_id in sorted(applied_event_ids)
        if event_id in event_by_id
    ]
    configured_only_events = [
        event
        for event in configured_events
        if str(event.get("event_id") or "").strip() not in applied_event_ids
    ]
    scenario_configured = sum(1 for event in configured_events if supplier_risk_event_source_kind(event) == "scenario")
    state_configured = sum(1 for event in configured_events if supplier_risk_event_source_kind(event) == "state")
    scenario_applied = sum(1 for event in applied_configured_events if supplier_risk_event_source_kind(event) == "scenario")
    state_applied = sum(1 for event in applied_configured_events if supplier_risk_event_source_kind(event) == "state")
    dominant_applied_family = "other"
    if applied_configured_events:
        family_counter: dict[str, int] = defaultdict(int)
        for event in applied_configured_events:
            family_counter[supplier_risk_family_for_event(event)] += 1
        dominant_applied_family = max(family_counter.items(), key=lambda item: item[1])[0]
    dominant_applied_info = SIMULATED_RISK_FAMILY_INFO.get(dominant_applied_family, SIMULATED_RISK_FAMILY_INFO["other"])

    def configured_events_for(types: set[str]) -> list[dict[str, Any]]:
        return [
            event
            for event in configured_events
            if str(event.get("risk_type") or "") in types
        ]

    def field_values(field: str, default: float = 1.0) -> list[float]:
        vals: list[float] = []
        for row in applied_rows:
            raw = row.get(field)
            if raw is None or str(raw).strip() == "":
                continue
            value = to_float(raw)
            if value is None or math.isnan(value):
                value = default
            vals.append(float(value))
        return vals

    def has_factor_effect(fields: list[str]) -> bool:
        return any(
            abs(value - 1.0) > 1e-9
            for field in fields
            for value in field_values(field, 1.0)
        )

    def has_positive_effect(fields: list[str]) -> bool:
        return any(
            value > 1e-9
            for field in fields
            for value in field_values(field, 0.0)
        )

    def row_has_factor_effect(row: dict[str, str], fields: list[str]) -> bool:
        for field in fields:
            raw = row.get(field)
            if raw is None or str(raw).strip() == "":
                continue
            value = to_float(raw)
            if value is not None and not math.isnan(value) and abs(value - 1.0) > 1e-9:
                return True
        return False

    def row_has_positive_effect(row: dict[str, str], fields: list[str]) -> bool:
        for field in fields:
            raw = row.get(field)
            if raw is None or str(raw).strip() == "":
                continue
            value = to_float(raw)
            if value is not None and not math.isnan(value) and value > 1e-9:
                return True
        return False

    def event_ids_for(types: set[str], applied_field_names: list[str], *, applied_only: bool = False) -> list[str]:
        ids: set[str] = set()
        if not applied_only:
            for event in configured_events_for(types):
                event_id = str(event.get("event_id") or "").strip()
                if event_id:
                    ids.add(event_id)
        if applied_field_names:
            for row in applied_rows:
                row_event_ids = [event_id.strip() for event_id in str(row.get("event_ids") or "").split(",") if event_id.strip()]
                if applied_only and not any(
                    str((event_by_id.get(event_id) or {}).get("risk_type") or "") in types
                    for event_id in row_event_ids
                ):
                    continue
                factor_fields = [field for field in applied_field_names if "multiplier" in field]
                positive_fields = [field for field in applied_field_names if "multiplier" not in field]
                row_has_effect = row_has_factor_effect(row, factor_fields) or row_has_positive_effect(row, positive_fields)
                if not row_has_effect:
                    continue
                for event_id in row_event_ids:
                    if applied_only and str((event_by_id.get(event_id) or {}).get("risk_type") or "") not in types:
                        continue
                    if event_id:
                        ids.add(event_id)
        return sorted(ids)

    def configured_window_text(events: list[dict[str, Any]]) -> str:
        if not events:
            return "n/a"
        days = [
            int(to_float(event.get(day_field)) or 0)
            for event in events
            for day_field in ("start_day", "end_day")
            if str(event.get(day_field) or "").strip() != ""
        ]
        if not days:
            return "n/a"
        return f"J{min(days)} -> J{max(days)}"

    def compact_event_list(events: list[dict[str, Any]], max_count: int = 4) -> str:
        if not events:
            return "aucun"
        labels = [str(event.get("event_id") or "event") for event in events[:max_count]]
        if len(events) > max_count:
            labels.append(f"+{len(events) - max_count}")
        return ", ".join(labels)

    def applied_event_ids_for(types: set[str], applied_field_names: list[str]) -> list[str]:
        return event_ids_for(types, applied_field_names, applied_only=True)

    def configured_only_events_for(types: set[str]) -> list[dict[str, Any]]:
        return [
            event
            for event in configured_events_for(types)
            if str(event.get("event_id") or "").strip() not in applied_event_ids
        ]

    def scenario_card_html(title: str, text: str, family: str = "other") -> str:
        color = SIMULATED_RISK_FAMILY_INFO.get(family, SIMULATED_RISK_FAMILY_INFO["other"])["color"]
        return (
            f"<div class=\"riskScenarioCard\" style=\"border-left-color:{html.escape(color)}\">"
            f"<div class=\"riskScenarioCardTitle\">{html.escape(title)}</div>"
            f"<div class=\"riskScenarioCardText\">{html.escape(text)}</div>"
            "</div>"
        )

    def configured_text(events: list[dict[str, Any]]) -> str:
        if not events:
            return "aucun"
        parts = []
        for event in events[:4]:
            event_id = str(event.get("event_id") or "event")
            start_day = event.get("start_day", "")
            end_day = event.get("end_day", "")
            multiplier = event.get("multiplier", "")
            item_id = str(event.get("item_id") or "*")
            parts.append(f"{event_id}: item={item_id}, J{start_day}-J{end_day}, val={multiplier}")
        if len(events) > 4:
            parts.append(f"+{len(events) - 4} autre(s)")
        return " ; ".join(parts)

    def numeric_field_values(fields: list[str], default: float = 1.0) -> list[float]:
        return [
            value
            for field in fields
            for value in field_values(field, default)
            if value is not None and not math.isnan(value)
        ]

    def risk_category_business_effect(
        category: str,
        *,
        factor_fields: list[str],
        day_fields: list[str],
        pct_fields: list[str],
        mode: str,
    ) -> str:
        category_lower = category.lower()
        factor_vals = numeric_field_values(factor_fields, 1.0)
        day_vals = numeric_field_values(day_fields, 0.0)
        pct_vals = numeric_field_values(pct_fields, 0.0)
        factor_value = None
        if factor_vals:
            factor_value = max(factor_vals) if mode == "max" else min(factor_vals)
        max_days = max(day_vals) if day_vals else 0.0
        max_pct = max(pct_vals) if pct_vals else 0.0

        if "write-off" in category_lower or "perte stock" in category_lower:
            return f"stock perdu ou bloque jusqu'a {fmt_pct(max_pct * 100.0)}"
        if "stock fournisseur" in category_lower:
            return f"stock accessible descendu a {fmt_pct((factor_value or 1.0) * 100.0)}"
        if "capacite fournisseur" in category_lower:
            return f"capacite fournisseur descendue a {fmt_pct((factor_value or 1.0) * 100.0)}"
        if "disponibilite fournisseur" in category_lower:
            return f"disponibilite fournisseur descendue a {fmt_pct((factor_value or 1.0) * 100.0)}"
        if "lead time fournisseur" in category_lower:
            parts = []
            if factor_value is not None and abs(factor_value - 1.0) > 1e-9:
                parts.append(f"delai multiplie jusqu'a x{factor_value:.2f}")
            if max_days > 1e-9:
                parts.append(f"retard ajoute jusqu'a {fmt_days(max_days, 1)}")
            return " ; ".join(parts) if parts else "aucun allongement de delai applique"
        if "release" in category_lower:
            return f"liberation qualite retardee jusqu'a {fmt_days(max_days, 1)}"
        if "otif" in category_lower or "fiabilite" in category_lower:
            return f"quantite utile expediee descendue a {fmt_pct((factor_value or 1.0) * 100.0)}"
        if "rendement qualite" in category_lower or "rejets" in category_lower:
            return f"rendement utile descendu a {fmt_pct((factor_value or 1.0) * 100.0)}"
        if "cout" in category_lower:
            return f"cout multiplie jusqu'a x{(factor_value or 1.0):.2f}"
        if "appro amont fournisseur - capacite" in category_lower:
            return f"approvisionnement amont limite a {fmt_pct((factor_value or 1.0) * 100.0)}"
        if "appro amont fournisseur - delai" in category_lower:
            parts = []
            if factor_value is not None and abs(factor_value - 1.0) > 1e-9:
                parts.append(f"delai amont multiplie jusqu'a x{factor_value:.2f}")
            if max_days > 1e-9:
                parts.append(f"retard amont ajoute jusqu'a {fmt_days(max_days, 1)}")
            return " ; ".join(parts) if parts else "aucun retard amont applique"
        if "appro amont fournisseur - qualite" in category_lower:
            return f"rendement amont descendu a {fmt_pct((factor_value or 1.0) * 100.0)}"
        return "effet applique dans le run"

    def factor_intensity(fields: list[str], *, mode: str) -> str:
        vals = [
            value
            for field in fields
            for value in field_values(field, 1.0)
        ]
        if not vals:
            return "1.00x"
        if mode == "max":
            return f"max={max(vals):.2f}x"
        return f"min={min(vals):.2f}x"

    def days_intensity(fields: list[str]) -> str:
        vals = [
            value
            for field in fields
            for value in field_values(field, 0.0)
        ]
        if not vals:
            return "0.0 j"
        return f"max={fmt_days(max(vals), 1)}"

    def pct_intensity(fields: list[str]) -> str:
        vals = [
            value
            for field in fields
            for value in field_values(field, 0.0)
        ]
        if not vals:
            return "0.0%"
        return f"max={fmt_pct(max(vals) * 100.0)}"

    catalog = [
        {
            "category": "Stock fournisseur",
            "types": {"stock"},
            "factor_fields": ["stock_multiplier"],
            "day_fields": [],
            "pct_fields": [],
            "mode": "min",
            "reading": "Part de stock fournisseur accessible aux commandes.",
        },
        {
            "category": "Perte stock / write-off",
            "types": {"stock_writeoff"},
            "factor_fields": [],
            "day_fields": [],
            "pct_fields": ["stock_writeoff_fraction"],
            "mode": "max",
            "reading": "Destruction, quarantaine definitive ou perte physique du stock fournisseur.",
        },
        {
            "category": "Capacite fournisseur",
            "types": {"capacity"},
            "factor_fields": ["capacity_multiplier"],
            "day_fields": [],
            "pct_fields": [],
            "mode": "min",
            "reading": "Debit journalier disponible chez le fournisseur.",
        },
        {
            "category": "Disponibilite fournisseur",
            "types": {"availability"},
            "factor_fields": ["availability_multiplier"],
            "day_fields": [],
            "pct_fields": [],
            "mode": "min",
            "reading": "Indisponibilite temporaire du fournisseur ou d'une ligne amont.",
        },
        {
            "category": "Lead time fournisseur",
            "types": {"lead_time", "lead_time_extra_days"},
            "factor_fields": ["lead_time_multiplier"],
            "day_fields": ["lead_time_extra_days"],
            "pct_fields": [],
            "mode": "max",
            "reading": "Allongement du delai reel simule avant reception.",
        },
        {
            "category": "Qualite / release",
            "types": {"quality_delay"},
            "factor_fields": [],
            "day_fields": ["quality_delay_days"],
            "pct_fields": [],
            "mode": "max",
            "reading": "Retard de liberation qualite ajoute au lead time.",
        },
        {
            "category": "Fiabilite / OTIF",
            "types": {"reliability"},
            "factor_fields": ["reliability_multiplier"],
            "day_fields": [],
            "pct_fields": [],
            "mode": "min",
            "reading": "Part utile expediee apres alea de fiabilite fournisseur.",
        },
        {
            "category": "Rendement qualite / rejets",
            "types": {"quality_yield"},
            "factor_fields": ["quality_yield_multiplier"],
            "day_fields": [],
            "pct_fields": [],
            "mode": "min",
            "reading": "Rendement utile apres rejet, scrap ou non-conformite.",
        },
        {
            "category": "Cout achat",
            "types": {"purchase_cost"},
            "factor_fields": ["purchase_cost_multiplier"],
            "day_fields": [],
            "pct_fields": [],
            "mode": "max",
            "reading": "Inflation prix achat ou surcharge fournisseur.",
        },
        {
            "category": "Cout transport",
            "types": {"transport_cost"},
            "factor_fields": ["transport_cost_multiplier"],
            "day_fields": [],
            "pct_fields": [],
            "mode": "max",
            "reading": "Inflation fret, urgence, changement de mode transport.",
        },
        {
            "category": "Appro amont fournisseur - capacite",
            "types": {"external_capacity", "external_availability"},
            "factor_fields": ["external_capacity_multiplier", "external_availability_multiplier"],
            "day_fields": [],
            "pct_fields": [],
            "mode": "min",
            "reading": "Plafond et disponibilite de l'approvisionnement amont qui reconstitue le stock fournisseur.",
        },
        {
            "category": "Appro amont fournisseur - delai",
            "types": {"external_lead_time", "external_lead_time_extra_days"},
            "factor_fields": ["external_lead_time_multiplier"],
            "day_fields": ["external_lead_time_extra_days"],
            "pct_fields": [],
            "mode": "max",
            "reading": "Allongement du delai d'approvisionnement amont fournisseur.",
        },
        {
            "category": "Appro amont fournisseur - qualite",
            "types": {"external_quality_yield"},
            "factor_fields": ["external_quality_yield_multiplier"],
            "day_fields": [],
            "pct_fields": [],
            "mode": "min",
            "reading": "Rendement utile de l'approvisionnement amont apres rejet.",
        },
        {
            "category": "Appro amont fournisseur - cout",
            "types": {"external_cost"},
            "factor_fields": ["external_cost_multiplier"],
            "day_fields": [],
            "pct_fields": [],
            "mode": "max",
            "reading": "Surcout de l'approvisionnement amont, achat et transport d'urgence.",
        },
    ]

    category_entries: list[dict[str, Any]] = []
    for entry in catalog:
        types = set(entry["types"])
        factor_fields = list(entry["factor_fields"])
        day_fields = list(entry["day_fields"])
        pct_fields = list(entry["pct_fields"])
        configured = configured_events_for(types)
        configured_only = configured_only_events_for(types)
        applied = (
            has_factor_effect(factor_fields)
            or has_positive_effect(day_fields)
            or has_positive_effect(pct_fields)
        )
        status = "APPLIQUE" if applied else ("CONFIGURE" if configured else "NEUTRE")
        intensity_parts: list[str] = []
        if factor_fields:
            intensity_parts.append(factor_intensity(factor_fields, mode=str(entry["mode"])))
        if day_fields:
            intensity_parts.append(days_intensity(day_fields))
        if pct_fields:
            intensity_parts.append(pct_intensity(pct_fields))
        intensity = " ; ".join(intensity_parts) if intensity_parts else "n/a"
        effect_text = risk_category_business_effect(
            str(entry["category"]),
            factor_fields=factor_fields,
            day_fields=day_fields,
            pct_fields=pct_fields,
            mode=str(entry["mode"]),
        )
        applied_ids = applied_event_ids_for(types, factor_fields + day_fields + pct_fields)
        all_ids = event_ids_for(types, factor_fields + day_fields + pct_fields)
        category_entries.append(
            {
                "status": status,
                "category": str(entry["category"]),
                "family": supplier_risk_family_for_type(next(iter(types)) if types else ""),
                "intensity": intensity,
                "applied_ids": applied_ids,
                "all_ids": all_ids,
                "configured": configured,
                "configured_only": configured_only,
                "reading": str(entry["reading"]),
                "effect_text": effect_text,
            }
        )

    applied_entries = [entry for entry in category_entries if entry["status"] == "APPLIQUE"]
    configured_only_entries = [
        entry for entry in category_entries
        if entry["status"] == "CONFIGURE" and entry["configured_only"]
    ]
    detail_entries = applied_entries + configured_only_entries
    rows_html: list[str] = []
    for entry in detail_entries:
        applied_ids = entry["applied_ids"]
        configured_only = entry["configured_only"]
        if entry["status"] == "APPLIQUE":
            event_text = ", ".join(applied_ids) or "applique"
            window_text = configured_window_text([
                event_by_id[event_id]
                for event_id in applied_ids
                if event_id in event_by_id
            ])
        else:
            event_text = compact_event_list(configured_only)
            window_text = configured_window_text(configured_only)
        rows_html.append(
            "<tr>"
            f"<td>{html.escape(str(entry['status']))}</td>"
            f"<td>{html.escape(str(entry['category']))}</td>"
            f"<td>{html.escape(str(entry['intensity']))}</td>"
            f"<td>{html.escape(event_text)}</td>"
            f"<td>{html.escape(window_text)}</td>"
            f"<td>{html.escape(str(entry['reading']))}</td>"
            "</tr>"
        )
    if not rows_html:
        rows_html.append(
            "<tr><td colspan=\"6\">Aucun evenement fournisseur configure ou applique sur ce noeud.</td></tr>"
        )

    applied_cards = []
    for entry in applied_entries[:6]:
        card_events = [
            event_by_id[event_id]
            for event_id in entry["applied_ids"]
            if event_id in event_by_id
        ]
        card_window = configured_window_text(card_events)
        applied_cards.append(
            scenario_card_html(
                str(entry["category"]),
                f"{entry['effect_text']}. Fenetre: {card_window}.",
                str(entry["family"]),
            )
        )
    if not applied_cards:
        applied_cards.append(
            scenario_card_html(
                "Aucun effet applique",
                "Des evenements peuvent etre configures, mais aucun n'a rencontre un ordre ou un flux actif sur ce noeud.",
                "other",
            )
        )

    external_enabled = bool(economic_policy.get("external_procurement_enabled"))
    external_proactive = bool(economic_policy.get("external_procurement_proactive_replenishment"))
    external_lead_mode = str(economic_policy.get("external_procurement_lead_mode") or "policy_fixed")
    if external_lead_mode == "supplier_material":
        external_lead_label = (
            "lead=delai matiere fournisseur "
            f"(fallback {fmt_days(economic_policy.get('external_procurement_lead_days'), 0)})"
        )
    else:
        external_lead_label = f"lead fixe={fmt_days(economic_policy.get('external_procurement_lead_days'), 0)}"
    external_capacity_mode = str(economic_policy.get("external_procurement_capacity_mode") or "policy_cap")
    if external_capacity_mode == "supplier_nominal":
        external_capacity_label = (
            "cap=fournisseur nominal par item "
            f"(scale={fmt_qty(economic_policy.get('external_procurement_nominal_capacity_scale', 1.0), 2)} ; "
            f"pipeline init={'oui' if economic_policy.get('external_procurement_seed_upstream_pipeline') else 'non'}, "
            f"fill={fmt_qty(economic_policy.get('external_procurement_upstream_pipeline_fill_ratio', 0.0), 2)})"
        )
    else:
        external_capacity_label = (
            f"cap/j=max({fmt_qty(economic_policy.get('external_procurement_min_daily_cap_qty'), 0)}, "
            f"{fmt_qty(economic_policy.get('external_procurement_daily_cap_days'), 1)} jours de demande)"
        )
    external_policy_text = (
        f"Appro amont fournisseur: {'actif' if external_enabled else 'inactif'} ; "
        f"proactif={'oui' if external_proactive else 'non'} ; "
        f"{external_lead_label} ; "
        f"scale={fmt_qty(economic_policy.get('external_procurement_lead_time_scale', 1.0), 2)} ; "
        f"{external_capacity_label} ; "
        f"cout={fmt_qty(economic_policy.get('external_procurement_cost_multiplier'), 1)}x"
    )

    return "".join(
        [
            "<div class=\"factoryHtmlPanelContent orderLedgerPanelContent\">",
            f"<div class=\"orderLedgerTextHeader\">{html.escape(node_id)} - risques simules fournisseur</div>",
            "<div class=\"orderLedgerStatus\">Question metier: quels aleas ont vraiment pese sur ce fournisseur dans le run, et lesquels etaient seulement configures ?</div>",
            f"<div class=\"riskSummaryCard riskSummaryCardNeutral\" style=\"border-left-color:{html.escape(dominant_applied_info['color'])}\">",
            "<div class=\"riskSummaryHeader\">",
            "<div>",
            "<div class=\"riskSummaryPill\">RISQUES SIMULES</div>",
            f"<div class=\"riskSummaryTitle\">{html.escape(node_id)} - {html.escape(status_text)}</div>",
            f"<div class=\"riskSummaryText\">Lecture locale du run: on ne garde ici que les effets qui ont vraiment modifie un flux, un stock, un delai ou une quantite utile. Les aleas sans effet local sont replies dans les details.</div>",
            "</div>",
            "<div class=\"riskSummaryGrid\">",
            f"<div class=\"riskFactCard\"><div class=\"riskFactLabel\">EFFET DOMINANT</div><div class=\"riskFactValue\">{html.escape(dominant_applied_info['label']) if applied_event_ids else 'aucun effet local'}</div></div>",
            f"<div class=\"riskFactCard\"><div class=\"riskFactLabel\">PERIODE TOUCHEE</div><div class=\"riskFactValue\">{html.escape(period_text)}</div></div>",
            f"<div class=\"riskFactCard\"><div class=\"riskFactLabel\">FAMILLES D'EFFETS</div><div class=\"riskFactValue\">{len(applied_entries)}</div></div>",
            f"<div class=\"riskFactCard\"><div class=\"riskFactLabel\">A REGARDER ENSUITE</div><div class=\"riskFactValue\">stocks, ordres, receptions</div></div>",
            "</div>",
            "</div>",
            "</div>",
            "<div class=\"riskScenarioSection\">Effets reels dans ce run</div>",
            f"<div class=\"riskScenarioCards\">{''.join(applied_cards)}</div>",
            "<div class=\"riskScenarioMuted\">Seuls les effets qui ont modifie le run local sont visibles ici. Les evenements sans effet local restent accessibles ci-dessous.</div>",
            "<details class=\"riskScenarioNativeDetails\">",
            "<summary>Details evenements et mecanique de calcul</summary>",
            f"<div class=\"orderLedgerStatus\">Mecanique appro amont: {html.escape(external_policy_text)}</div>",
            "<div class=\"kpiFormulaTableWrap\"><table class=\"kpiFormulaTable\">",
            "<thead><tr><th>Statut</th><th>Categorie</th><th>Intensite</th><th>Evenements</th><th>Fenetre</th><th>Lecture metier</th></tr></thead>",
            f"<tbody>{''.join(rows_html)}</tbody>",
            "</table></div>",
            "</details>",
            "</div>",
        ]
    )


def supplier_risk_family_for_type(risk_type: str) -> str:
    value = str(risk_type or "").strip().lower()
    if value in {"capacity"}:
        return "capacity"
    if value in {"stock", "stock_writeoff"}:
        return "stock"
    if value in {"lead_time", "lead_time_extra_days"}:
        return "lead"
    if value in {"reliability"}:
        return "reliability"
    if value in {
        "external_capacity",
        "external_availability",
        "external_lead_time",
        "external_lead_time_extra_days",
        "external_quality_yield",
        "external_cost",
    }:
        return "upstream"
    if value in {"quality_delay", "quality_yield"}:
        return "quality"
    if value in {"purchase_cost", "transport_cost"}:
        return "cost"
    if value in {"availability"}:
        return "availability"
    return "other"


def supplier_risk_event_source_kind(event: dict[str, Any]) -> str:
    source = str(event.get("source") or "").strip()
    event_id = str(event.get("event_id") or "").strip()
    if source == "state_dependent_supplier_risk" or event_id.startswith("state_"):
        return "state"
    return "scenario"


def supplier_risk_family_for_event(event: dict[str, Any]) -> str:
    explicit_family = str(event.get("risk_family") or "").strip().lower()
    if explicit_family:
        return explicit_family
    event_id = str(event.get("event_id") or "").strip().lower()
    match = re.match(r"state_(stock|capacity|lead|reliability|quality|upstream|cost|availability)_", event_id)
    if match:
        return match.group(1)
    return supplier_risk_family_for_type(str(event.get("risk_type") or ""))


def supplier_risk_family_severity(row: dict[str, str], family: str) -> float:
    def factor_drop(field: str) -> float:
        value = to_float(row.get(field))
        if value is None or math.isnan(value):
            return 0.0
        return max(0.0, 1.0 - value)

    def factor_increase(field: str, scale: float = 1.0) -> float:
        value = to_float(row.get(field))
        if value is None or math.isnan(value):
            return 0.0
        return max(0.0, (value - 1.0) / max(scale, 1e-9))

    def positive(field: str, scale: float) -> float:
        value = to_float(row.get(field))
        if value is None or math.isnan(value):
            return 0.0
        return max(0.0, value / max(scale, 1e-9))

    if family == "capacity":
        return max(factor_drop("capacity_multiplier"), factor_drop("availability_multiplier"))
    if family == "stock":
        return max(
            factor_drop("stock_multiplier"),
            factor_drop("availability_multiplier"),
            positive("stock_writeoff_fraction", 1.0),
        )
    if family == "lead":
        return max(
            factor_increase("lead_time_multiplier", 2.0),
            positive("lead_time_extra_days", 60.0),
            positive("quality_delay_days", 45.0),
        )
    if family == "reliability":
        return max(factor_drop("reliability_multiplier"), factor_drop("quality_yield_multiplier"))
    if family == "upstream":
        return max(
            factor_drop("external_capacity_multiplier"),
            factor_drop("external_availability_multiplier"),
            factor_increase("external_lead_time_multiplier", 2.0),
            positive("external_lead_time_extra_days", 60.0),
            factor_drop("external_quality_yield_multiplier"),
            factor_increase("external_cost_multiplier", 2.0),
        )
    if family == "quality":
        return max(positive("quality_delay_days", 45.0), factor_drop("quality_yield_multiplier"))
    if family == "cost":
        return max(factor_increase("purchase_cost_multiplier", 2.0), factor_increase("transport_cost_multiplier", 2.0))
    if family == "availability":
        return factor_drop("availability_multiplier")
    return 0.0


def build_simulated_supplier_risk_metrics(
    *,
    configured_by_node: dict[str, list[dict[str, Any]]],
    applied_by_node: dict[str, list[dict[str, str]]],
) -> dict[str, Any]:
    event_family_by_id: dict[str, str] = {}
    event_source_by_id: dict[str, str] = {}
    for events in configured_by_node.values():
        for event in events:
            event_id = str(event.get("event_id") or "").strip()
            if not event_id:
                continue
            event_family_by_id[event_id] = supplier_risk_family_for_event(event)
            event_source_by_id[event_id] = supplier_risk_event_source_kind(event)

    nodes: dict[str, Any] = {}
    global_configured_ids: set[str] = set()
    global_applied_ids: set[str] = set()
    global_configured_family_counts: dict[str, int] = defaultdict(int)
    global_applied_family_counts: dict[str, int] = defaultdict(int)
    global_configured_source_counts: dict[str, int] = defaultdict(int)
    global_applied_source_counts: dict[str, int] = defaultdict(int)

    for node_id in sorted(set(configured_by_node.keys()) | set(applied_by_node.keys())):
        configured_events = configured_by_node.get(node_id, [])
        applied_rows = applied_by_node.get(node_id, [])
        configured_ids = {
            str(event.get("event_id") or "").strip()
            for event in configured_events
            if str(event.get("event_id") or "").strip()
        }
        applied_ids = {
            event_id.strip()
            for row in applied_rows
            for event_id in str(row.get("event_ids") or "").split(",")
            if event_id.strip()
        }
        global_configured_ids.update(configured_ids)
        global_applied_ids.update(applied_ids)

        family_counts: dict[str, int] = defaultdict(int)
        configured_family_counts: dict[str, int] = defaultdict(int)
        applied_family_counts: dict[str, int] = defaultdict(int)
        configured_source_counts: dict[str, int] = defaultdict(int)
        applied_source_counts: dict[str, int] = defaultdict(int)
        family_scores: dict[str, float] = defaultdict(float)
        for event in configured_events:
            family = supplier_risk_family_for_event(event)
            source_kind = supplier_risk_event_source_kind(event)
            family_counts[family] += 1
            configured_family_counts[family] += 1
            configured_source_counts[source_kind] += 1
            global_configured_family_counts[family] += 1
            global_configured_source_counts[source_kind] += 1
        for event_id in applied_ids:
            family = event_family_by_id.get(event_id, "other")
            source_kind = event_source_by_id.get(event_id, "scenario")
            applied_family_counts[family] += 1
            applied_source_counts[source_kind] += 1
            global_applied_family_counts[family] += 1
            global_applied_source_counts[source_kind] += 1
        for row in applied_rows:
            row_event_ids = [event_id.strip() for event_id in str(row.get("event_ids") or "").split(",") if event_id.strip()]
            row_families = {event_family_by_id.get(event_id, "other") for event_id in row_event_ids} or {"other"}
            for family in row_families:
                family_counts[family] += 1
                family_scores[family] = max(family_scores[family], supplier_risk_family_severity(row, family))

        configured_days = [
            int(to_float(event.get(day_field)) or 0)
            for event in configured_events
            for day_field in ("start_day", "end_day")
            if str(event.get(day_field) or "").strip() != ""
        ]
        applied_days = {
            int(to_float(row.get("day")) or 0)
            for row in applied_rows
            if str(row.get("day") or "").strip() != ""
        }
        dominant_family = "other"
        if family_counts:
            dominant_candidates = [family for family in family_counts if family != "cost"] or list(family_counts)
            dominant_family = max(
                dominant_candidates,
                key=lambda family: (family_scores.get(family, 0.0), family_counts.get(family, 0)),
            )
        info = SIMULATED_RISK_FAMILY_INFO.get(dominant_family, SIMULATED_RISK_FAMILY_INFO["other"])
        score = max(family_scores.values()) if family_scores else (0.08 if configured_ids else 0.0)
        period = (
            f"J{min(applied_days)} -> J{max(applied_days)}"
            if applied_days
            else (
                f"J{min(configured_days)} -> J{max(configured_days)}"
                if configured_days
                else "n/a"
            )
        )
        status_label = (
            "Evenement applique dans ce run"
            if applied_ids
            else ("Configure mais pas applique dans ce run" if configured_ids else "Aucun risque simule")
        )
        examples = sorted(applied_ids or configured_ids)[:4]
        source_text = (
            f"scenario {applied_source_counts.get('scenario', 0)}/{configured_source_counts.get('scenario', 0)} ; "
            f"state-dependent {applied_source_counts.get('state', 0)}/{configured_source_counts.get('state', 0)}"
        )
        nodes[node_id] = {
            "source": "supplier_risk_events",
            "status": "applied" if applied_ids else ("configured" if configured_ids else "none"),
            "status_label": status_label,
            "driver_family": dominant_family,
            "driver_label": info["label"],
            "driver_color": info["color"],
            "score": min(1.0, max(0.0, score)),
            "configured_event_count": len(configured_ids),
            "applied_event_count": len(applied_ids),
            "configured_not_applied_count": max(0, len(configured_ids) - len(applied_ids)),
            "applied_row_count": len(applied_rows),
            "active_day_count": len(applied_days),
            "period": period,
            "event_examples": examples,
            "configured_family_counts": dict(sorted(configured_family_counts.items())),
            "applied_family_counts": dict(sorted(applied_family_counts.items())),
            "configured_source_counts": dict(sorted(configured_source_counts.items())),
            "applied_source_counts": dict(sorted(applied_source_counts.items())),
            "summary_lines": [
                {"label": "Lecture", "value": "risques simules injectes"},
                {"label": "Statut", "value": status_label},
                {"label": "Appliques / configures", "value": f"{len(applied_ids)} / {len(configured_ids)}"},
                {"label": "Non appliques", "value": str(max(0, len(configured_ids) - len(applied_ids)))},
                {"label": "Famille appliquee dominante", "value": info["label"] if applied_ids else "aucune"},
                {"label": "Sources", "value": source_text},
                {"label": "Periode", "value": period},
                {"label": "Jours impactes", "value": str(len(applied_days))},
                {"label": "Exemples", "value": ", ".join(examples) if examples else "aucun"},
            ],
        }

    dominant_global_family = "other"
    family_basis = global_applied_family_counts or global_configured_family_counts
    if family_basis:
        dominant_global_candidates = [family for family in family_basis if family != "cost"] or list(family_basis)
        dominant_global_family = max(dominant_global_candidates, key=lambda family: family_basis[family])
    return {
        "nodes": nodes,
        "global": {
            "configured_event_count": len(global_configured_ids),
            "applied_event_count": len(global_applied_ids),
            "node_count": len(nodes),
            "applied_node_count": sum(1 for node in nodes.values() if node.get("status") == "applied"),
            "configured_node_count": sum(1 for node in nodes.values() if node.get("configured_event_count", 0)),
            "dominant_family": dominant_global_family,
            "dominant_label": SIMULATED_RISK_FAMILY_INFO.get(dominant_global_family, SIMULATED_RISK_FAMILY_INFO["other"])["label"],
            "family_counts": dict(sorted((global_applied_family_counts or global_configured_family_counts).items())),
            "configured_family_counts": dict(sorted(global_configured_family_counts.items())),
            "applied_family_counts": dict(sorted(global_applied_family_counts.items())),
            "configured_source_counts": dict(sorted(global_configured_source_counts.items())),
            "applied_source_counts": dict(sorted(global_applied_source_counts.items())),
        },
    }


def build_simulated_risk_global_diagnostic_payload(
    *,
    raw: dict[str, Any],
    output_root: Path,
    simulated_risk_metrics: dict[str, Any],
) -> dict[str, Any]:
    data_root = output_root / "data"
    summary = load_json_dict(output_root / "summaries" / "first_simulation_summary.json")
    kpis = (summary.get("kpis") or {}) if isinstance(summary, dict) else {}
    production_tracking = (summary.get("production_tracking") or {}) if isinstance(summary, dict) else {}
    scenario_events = [
        dict(event)
        for event in production_tracking.get("supplier_risk_events", []) or []
        if isinstance(event, dict)
    ]
    state_events = [dict(row) for row in read_csv_rows(data_root / "supplier_state_dependent_risk_events.csv")]
    configured_events = scenario_events + state_events
    event_by_id = {
        str(event.get("event_id") or "").strip(): event
        for event in configured_events
        if str(event.get("event_id") or "").strip()
    }
    applied_rows = read_csv_rows(data_root / "supplier_risk_events_applied_daily.csv")
    demand_rows = read_csv_rows(data_root / "production_demand_service_daily.csv")
    plan_rows = read_csv_rows(data_root / "production_plan_events.csv")
    constraint_rows = read_csv_rows(data_root / "production_constraint_daily.csv")
    daily_rows = read_csv_rows(data_root / "first_simulation_daily.csv")
    item_labels = build_item_label_lookup(raw)
    node_labels = {
        str(node.get("id") or ""): str(node.get("name") or node.get("label") or node.get("id") or "")
        for node in raw.get("nodes", []) or []
        if isinstance(node, dict) and str(node.get("id") or "")
    }
    node_type_by_id = {
        str(node.get("id") or ""): str(node.get("type") or "").lower()
        for node in raw.get("nodes", []) or []
        if isinstance(node, dict) and str(node.get("id") or "")
    }
    edge_by_id = {
        str(edge.get("id") or ""): edge
        for edge in raw.get("edges", []) or []
        if isinstance(edge, dict) and str(edge.get("id") or "")
    }
    edges_by_from: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for edge in edge_by_id.values():
        edges_by_from[str(edge.get("from") or "")].append(edge)

    def label_node(node_id: str) -> str:
        node_id = str(node_id or "")
        label = node_labels.get(node_id, "")
        return f"{node_id} - {label}" if label and label != node_id else node_id

    def label_item(item_id: str) -> str:
        item_id = str(item_id or "")
        return item_labels.get(item_id, compact_item_label(item_id))

    stage_info = {
        "service_client": {"label": "Disponibilite produit degradee", "color": "#dc2626", "rank": 5},
        "production": {"label": "Production reportee", "color": "#f97316", "rank": 4},
        "cost": {"label": "Surcout fournisseur", "color": "#7c3aed", "rank": 3},
        "local_absorbed": {"label": "Absorbe localement", "color": "#0f766e", "rank": 2},
        "configured_only": {"label": "Signal sans effet", "color": "#94a3b8", "rank": 1},
        "other": {"label": "Autre", "color": "#64748b", "rank": 0},
    }

    def unique_event_ids_from_rows(rows: list[dict[str, str]]) -> set[str]:
        return {
            event_id.strip()
            for row in rows
            for event_id in str(row.get("event_ids") or "").split(",")
            if event_id.strip()
        }

    applied_ids = unique_event_ids_from_rows(applied_rows)
    configured_ids = set(event_by_id)
    applied_days = {
        int(to_float(row.get("day")) or 0)
        for row in applied_rows
        if str(row.get("day") or "").strip() != ""
    }
    applied_period = f"J{min(applied_days)} -> J{max(applied_days)}" if applied_days else "aucune application"

    family_counts: dict[str, int] = defaultdict(int)
    supplier_stats: dict[str, dict[str, Any]] = defaultdict(lambda: {
        "rows": 0,
        "days": set(),
        "items": set(),
        "families": defaultdict(int),
        "event_ids": set(),
        "max_score": 0.0,
    })
    item_stats: dict[str, dict[str, Any]] = defaultdict(lambda: {
        "rows": 0,
        "suppliers": set(),
        "families": defaultdict(int),
        "event_ids": set(),
        "max_score": 0.0,
    })
    for row in applied_rows:
        supplier_id = str(row.get("supplier_id") or "")
        item_id = str(row.get("item_id") or "")
        day = int(to_float(row.get("day")) or 0)
        row_event_ids = [event_id.strip() for event_id in str(row.get("event_ids") or "").split(",") if event_id.strip()]
        row_families = {
            supplier_risk_family_for_event(event_by_id.get(event_id, {"event_id": event_id}))
            for event_id in row_event_ids
        } or {"other"}
        max_score = max((supplier_risk_family_severity(row, family) for family in row_families), default=0.0)
        for family in row_families:
            family_counts[family] += 1
        if supplier_id:
            stats = supplier_stats[supplier_id]
            stats["rows"] += 1
            stats["days"].add(day)
            if item_id:
                stats["items"].add(item_id)
            stats["event_ids"].update(row_event_ids)
            stats["max_score"] = max(stats["max_score"], max_score)
            for family in row_families:
                stats["families"][family] += 1
        if item_id:
            stats = item_stats[item_id]
            stats["rows"] += 1
            if supplier_id:
                stats["suppliers"].add(supplier_id)
            stats["event_ids"].update(row_event_ids)
            stats["max_score"] = max(stats["max_score"], max_score)
            for family in row_families:
                stats["families"][family] += 1

    def family_summary(families: dict[str, int], limit: int = 3) -> str:
        parts = []
        for family, count in sorted(families.items(), key=lambda item: (-int(item[1]), item[0]))[:limit]:
            info = SIMULATED_RISK_FAMILY_INFO.get(family, SIMULATED_RISK_FAMILY_INFO["other"])
            parts.append(f"{info['label']} ({count})")
        return ", ".join(parts) if parts else "n/a"

    def top_supplier_rows(limit: int = 6) -> list[dict[str, str]]:
        out: list[dict[str, str]] = []
        for supplier_id, stats in sorted(
            supplier_stats.items(),
            key=lambda item: (-len(item[1]["days"]), -int(item[1]["rows"]), item[0]),
        )[:limit]:
            out.append(
                {
                    "Fournisseur": label_node(supplier_id),
                    "Periode": f"{len(stats['days'])} j",
                    "Articles touches": ", ".join(label_item(item_id) for item_id in sorted(stats["items"])[:4]) or "n/a",
                    "Effet dominant": family_summary(stats["families"], 2),
                    "Intensite max": fmt_pct(float(stats["max_score"]) * 100.0, 0),
                }
            )
        return out

    def top_item_rows(limit: int = 6) -> list[dict[str, str]]:
        out: list[dict[str, str]] = []
        for item_id, stats in sorted(
            item_stats.items(),
            key=lambda item: (-int(item[1]["rows"]), -len(item[1]["suppliers"]), item[0]),
        )[:limit]:
            out.append(
                {
                    "Article": label_item(item_id),
                    "Fournisseurs": str(len(stats["suppliers"])),
                    "Effet dominant": family_summary(stats["families"], 2),
                    "Occurrences": str(stats["rows"]),
                    "Intensite max": fmt_pct(float(stats["max_score"]) * 100.0, 0),
                }
            )
        return out

    delay_rows = [
        row for row in plan_rows
        if str(row.get("event_type") or "") in {"delay_input_shortage", "delay_weekly_lot_limit"}
        or str(row.get("reason") or "") in {"input_shortage", "weekly_lot_limit"}
    ]
    input_delay_rows = [
        row for row in delay_rows
        if str(row.get("reason") or row.get("event_type") or "") == "input_shortage"
        or str(row.get("event_type") or "") == "delay_input_shortage"
    ]
    production_plan_line_count = sum(
        1
        for row in plan_rows
        if str(row.get("node_id") or "").strip()
        and (
            str(row.get("output_item_id") or "").strip()
            or str(row.get("event_type") or "").strip()
            or str(row.get("reason") or "").strip()
            or (to_float(row.get("planned_qty_after_lot_rule")) or 0.0) > 0.0
            or (to_float(row.get("actual_qty")) or 0.0) > 0.0
        )
    )
    input_replanning_rate = (
        len(input_delay_rows) / production_plan_line_count
        if production_plan_line_count > 0
        else None
    )
    total_replanning_rate = (
        len(delay_rows) / production_plan_line_count
        if production_plan_line_count > 0
        else None
    )

    def replanning_rate_text(rate: float | None, count: int) -> str:
        if rate is not None and math.isfinite(rate):
            return f"{fmt_pct(rate * 100.0, 1)} ; volume associe {count} lignes"
        return f"taux n/a ; volume associe {count} lignes"
    delay_by_blocker: dict[tuple[str, str, str], dict[str, Any]] = defaultdict(lambda: {
        "count": 0,
        "days": set(),
        "lot_shortfall": 0.0,
        "desired_shortfall": 0.0,
        "next_receipts": [],
    })
    for row in input_delay_rows:
        key = (
            str(row.get("node_id") or ""),
            str(row.get("output_item_id") or ""),
            str(row.get("binding_input_item_id") or ""),
        )
        stats = delay_by_blocker[key]
        stats["count"] += 1
        stats["days"].add(int(to_float(row.get("day")) or 0))
        stats["lot_shortfall"] += max(0.0, to_float(row.get("shortfall_vs_lot_plan_qty")) or 0.0)
        stats["desired_shortfall"] += max(0.0, to_float(row.get("shortfall_vs_desired_qty")) or 0.0)
        next_day = to_float(row.get("next_expected_receipt_day"))
        if next_day is not None and not math.isnan(next_day):
            stats["next_receipts"].append(int(next_day))

    blocker_rows: list[dict[str, str]] = []
    for (node_id, output_item_id, input_item_id), stats in sorted(
        delay_by_blocker.items(),
        key=lambda item: (-int(item[1]["count"]), -float(item[1]["lot_shortfall"]), item[0]),
    )[:6]:
        next_receipts = stats["next_receipts"]
        next_text = (
            f"J{min(next_receipts)} -> J{max(next_receipts)}"
            if next_receipts and min(next_receipts) != max(next_receipts)
            else (f"J{next_receipts[0]}" if next_receipts else "n/a")
        )
        days = sorted(stats["days"])
        day_text = f"J{days[0]} -> J{days[-1]}" if days and days[0] != days[-1] else (f"J{days[0]}" if days else "n/a")
        blocker_rows.append(
            {
                "Site": label_node(node_id),
                "Produit": label_item(output_item_id),
                "Intrant bloquant": label_item(input_item_id),
                "Jours reportes": f"{stats['count']} ({day_text})",
                "Lots non lances": fmt_qty(stats["lot_shortfall"], 0),
                "Prochaine reception": next_text,
            }
        )

    max_backlog = 0.0
    backlog_days: set[int] = set()
    backlog_by_pair: dict[tuple[str, str], dict[str, Any]] = defaultdict(lambda: {"max": 0.0, "days": set()})
    for row in demand_rows:
        backlog = max(0.0, to_float(row.get("backlog_end_qty")) or 0.0)
        if backlog <= 1e-9:
            continue
        day = int(to_float(row.get("day")) or 0)
        node_id = str(row.get("node_id") or "")
        item_id = str(row.get("item_id") or "")
        backlog_days.add(day)
        max_backlog = max(max_backlog, backlog)
        stats = backlog_by_pair[(node_id, item_id)]
        stats["max"] = max(stats["max"], backlog)
        stats["days"].add(day)
    top_backlog = max(backlog_by_pair.items(), key=lambda item: item[1]["max"], default=None)
    top_backlog_text = "aucun backlog temporaire"
    if top_backlog:
        (node_id, item_id), stats = top_backlog
        top_backlog_text = f"{label_node(node_id)} / {label_item(item_id)}: pic {fmt_qty(stats['max'], 0)} sur {len(stats['days'])} j"

    actual_produced = sum(max(0.0, to_float(row.get("actual_qty")) or 0.0) for row in constraint_rows)
    planned_after_lot = sum(max(0.0, to_float(row.get("planned_qty_after_lot_rule")) or 0.0) for row in constraint_rows)
    lot_shortfall_total = sum(max(0.0, to_float(row.get("shortfall_vs_lot_plan_qty")) or 0.0) for row in constraint_rows)
    input_shortfall_total = sum(max(0.0, to_float(row.get("shortfall_vs_lot_plan_qty")) or 0.0) for row in input_delay_rows)

    fill_rate = to_float(kpis.get("fill_rate")) or 0.0
    ending_backlog = max(0.0, to_float(kpis.get("ending_backlog")) or 0.0)
    total_unreliable_loss = max(0.0, to_float(kpis.get("total_unreliable_loss_qty")) or 0.0)
    total_external_cost = max(0.0, to_float(kpis.get("total_external_procurement_cost")) or 0.0)
    total_cost = max(0.0, to_float(kpis.get("total_cost")) or 0.0)
    family_text = family_summary(family_counts, 5)
    service_status = (
        "Disponibilite produit final absorbee"
        if fill_rate >= 0.999 and ending_backlog <= 1e-9
        else "Disponibilite produit degradee"
    )
    production_status = (
        "Production reportee par intrants"
        if input_delay_rows
        else ("Production contrainte par regle de lot" if delay_rows else "Production sans report majeur")
    )
    supplier_status = (
        f"{len(supplier_stats)} fournisseurs touches"
        if supplier_stats
        else "Aucun fournisseur touche"
    )

    applied_rows_by_event: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in applied_rows:
        for event_id in str(row.get("event_ids") or "").split(","):
            event_id = event_id.strip()
            if event_id:
                applied_rows_by_event[event_id].append(row)

    def normalized_item_key(item_id: str) -> str:
        raw_item = str(item_id or "").strip()
        return raw_item.split(":", 1)[1] if raw_item.startswith("item:") else raw_item

    def same_item(left: str, right: str) -> bool:
        return bool(normalized_item_key(left)) and normalized_item_key(left) == normalized_item_key(right)

    process_outputs_by_node_input: dict[tuple[str, str], set[str]] = defaultdict(set)
    produced_items_by_node: dict[str, set[str]] = defaultdict(set)
    for node in raw.get("nodes", []) or []:
        if not isinstance(node, dict):
            continue
        node_id = str(node.get("id") or "")
        if not node_id:
            continue
        for process in node.get("processes") or []:
            if not isinstance(process, dict):
                continue
            output_items = {
                str(output.get("item_id") or "")
                for output in process.get("outputs") or []
                if isinstance(output, dict) and str(output.get("item_id") or "")
            }
            if not output_items:
                continue
            produced_items_by_node[node_id].update(output_items)
            for input_row in process.get("inputs") or []:
                if not isinstance(input_row, dict):
                    continue
                input_item = str(input_row.get("item_id") or "")
                if input_item:
                    process_outputs_by_node_input[(node_id, normalized_item_key(input_item))].update(output_items)

    def node_is_factory(node_id: str) -> bool:
        return node_type_by_id.get(str(node_id or "")) == "factory"

    def downstream_factory_nodes_for_item(supplier_id: str, item_id: str) -> set[str]:
        return {
            str(edge.get("to") or "")
            for edge in edges_by_from.get(str(supplier_id or ""), [])
            if node_is_factory(str(edge.get("to") or "")) and edge_matches_items(edge, {str(item_id or "")})
        }

    def output_items_for_component(factory_nodes: set[str], item_id: str) -> set[str]:
        outputs: set[str] = set()
        item_key = normalized_item_key(item_id)
        for factory_id in factory_nodes:
            outputs.update(process_outputs_by_node_input.get((factory_id, item_key), set()))
            if any(same_item(item_id, output_item) for output_item in produced_items_by_node.get(factory_id, set())):
                outputs.add(str(item_id))
        return outputs

    def edge_matches_items(edge: dict[str, Any], item_ids: set[str]) -> bool:
        if not item_ids:
            return True
        return any(
            any(same_item(str(edge_item), item_id) for item_id in item_ids)
            for edge_item in (edge.get("items") or [])
        )

    def edge_display_label(edge_id: str) -> str:
        edge = edge_by_id.get(str(edge_id or "")) or {}
        if edge:
            items = [label_item(str(item)) for item in (edge.get("items") or [])[:2]]
            suffix = f" / {', '.join(items)}" if items else ""
            return f"{edge.get('from') or '?'} -> {edge.get('to') or '?'}{suffix}"
        return str(edge_id or "")

    def route_closure_for_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
        edge_ids: set[str] = set()
        node_ids: set[str] = set()
        route_edges: list[dict[str, Any]] = []

        def add_node(node_id: str) -> None:
            node_id = str(node_id or "")
            if node_id:
                node_ids.add(node_id)

        def add_edge(edge_id: str, *, role: str = "route") -> None:
            edge_id = str(edge_id or "")
            if not edge_id or edge_id in edge_ids:
                return
            edge = edge_by_id.get(edge_id)
            edge_ids.add(edge_id)
            if edge:
                add_node(str(edge.get("from") or ""))
                add_node(str(edge.get("to") or ""))
            route_edges.append(
                {
                    "edge_id": edge_id,
                    "role": role,
                    "label": edge_display_label(edge_id),
                }
            )

        for row in rows:
            for node_id in row.get("highlight_node_ids") or []:
                add_node(str(node_id))
            add_node(str(row.get("supplier_id") or ""))
            for node_id in row.get("affected_factory_nodes") or []:
                add_node(str(node_id))
            for node_id in row.get("affected_customer_nodes") or []:
                add_node(str(node_id))
            for edge_id in row.get("highlight_edge_ids") or []:
                add_edge(str(edge_id), role="local_supply_flow")
            for edge in row.get("impacted_edges") or []:
                add_edge(str(edge.get("edge_id") or ""), role=str(edge.get("role") or "route"))

        supplier_ids = {
            str(row.get("supplier_id") or "")
            for row in rows
            if str(row.get("supplier_id") or "")
        }
        factory_ids = {
            str(node_id)
            for row in rows
            for node_id in (row.get("affected_factory_nodes") or [])
            if str(node_id)
        }
        customer_ids = {
            str(node_id)
            for row in rows
            for node_id in (row.get("affected_customer_nodes") or [])
            if str(node_id)
        }
        local_destination_ids = {
            str(node_id)
            for row in rows
            for node_id in (row.get("highlight_node_ids") or [])
            if str(node_id)
        }
        trigger_items = {
            str(row.get("item_id") or "")
            for row in rows
            if str(row.get("item_id") or "")
        }
        output_items = {
            str(item_id)
            for row in rows
            for item_id in (row.get("impacted_output_items") or [])
            if str(item_id)
        }

        for supplier_id in supplier_ids:
            for edge in edges_by_from.get(supplier_id, []):
                to_node = str(edge.get("to") or "")
                if not to_node or to_node not in (factory_ids | local_destination_ids | node_ids):
                    continue
                if edge_matches_items(edge, trigger_items):
                    add_edge(str(edge.get("id") or ""), role="local_supply_flow")

        # Complete the route from factory to customer when the output product is
        # known. This fixes the common visual gap factory -> DC -> client.
        if factory_ids and output_items:
            max_depth = 4
            target_customers = set(customer_ids)
            for factory_id in sorted(factory_ids):
                queue: list[tuple[str, list[str], set[str]]] = [(factory_id, [], {factory_id})]
                while queue:
                    current_node, path_edge_ids, seen_nodes = queue.pop(0)
                    if len(path_edge_ids) >= max_depth:
                        continue
                    for edge in edges_by_from.get(current_node, []):
                        if not edge_matches_items(edge, output_items):
                            continue
                        edge_id = str(edge.get("id") or "")
                        next_node = str(edge.get("to") or "")
                        if not edge_id or not next_node or next_node in seen_nodes:
                            continue
                        next_path = [*path_edge_ids, edge_id]
                        is_customer = next_node in target_customers
                        if is_customer:
                            for path_edge_id in next_path:
                                add_edge(path_edge_id, role="downstream_route")
                            continue
                        # If no customer is known yet, still keep the first DC leg:
                        # this makes production-stage cascades show the actual
                        # supply route without inventing a customer impact.
                        if not target_customers and len(next_path) <= 2:
                            for path_edge_id in next_path:
                                add_edge(path_edge_id, role="downstream_route")
                        next_seen = set(seen_nodes)
                        next_seen.add(next_node)
                        queue.append((next_node, next_path, next_seen))

        return {
            "route_node_ids": sorted(node_ids),
            "route_edge_ids": sorted(edge_ids),
            "route_edges": sorted(route_edges, key=lambda row: (str(row.get("role") or ""), str(row.get("edge_id") or ""))),
            "route_edge_labels": [edge_display_label(edge_id) for edge_id in sorted(edge_ids)],
        }

    def event_int(event: dict[str, Any], field: str, default: int = 0) -> int:
        value = to_float(event.get(field))
        if value is None or math.isnan(value):
            return default
        return int(value)

    def event_start_end(event: dict[str, Any]) -> tuple[int, int]:
        start_day = event_int(event, "start_day", event_int(event, "trigger_day", 0) + 1)
        end_day = event_int(event, "end_day", start_day)
        if end_day < start_day:
            end_day = start_day
        return start_day, end_day

    def day_in_window(row: dict[str, Any], start_day: int, end_day: int) -> bool:
        value = to_float(row.get("day"))
        if value is None or math.isnan(value):
            return False
        day = int(value)
        return start_day <= day <= end_day

    def local_effect_text(rows: list[dict[str, str]], family: str) -> tuple[str, float, int]:
        if not rows:
            return "non applique localement", 0.0, 0
        days = {
            int(to_float(row.get("day")) or 0)
            for row in rows
            if str(row.get("day") or "").strip() != ""
        }
        max_score = max((supplier_risk_family_severity(row, family) for row in rows), default=0.0)
        return f"{len(rows)} ligne(s), {len(days)} jour(s), intensite max {fmt_pct(max_score * 100.0, 0)}", max_score, len(days)

    def active_factor_text(row: dict[str, str]) -> list[str]:
        factors: list[str] = []
        multiplier_fields = [
            ("stock_multiplier", "stock"),
            ("capacity_multiplier", "capacite"),
            ("lead_time_multiplier", "delai"),
            ("reliability_multiplier", "fiabilite"),
            ("quality_yield_multiplier", "qualite"),
            ("availability_multiplier", "disponibilite"),
            ("purchase_cost_multiplier", "achat"),
            ("transport_cost_multiplier", "transport"),
            ("external_capacity_multiplier", "appro amont capacite"),
            ("external_availability_multiplier", "appro amont disponibilite"),
            ("external_lead_time_multiplier", "appro amont delai"),
            ("external_quality_yield_multiplier", "appro amont qualite"),
            ("external_cost_multiplier", "appro amont cout"),
        ]
        for field, label in multiplier_fields:
            value = to_float(row.get(field))
            if value is None or math.isnan(value) or abs(value - 1.0) <= 1e-9:
                continue
            factors.append(f"{label} x{fmt_qty(value, 2)}")
        extra_day_fields = [
            ("lead_time_extra_days", "delai +"),
            ("quality_delay_days", "qualite +"),
            ("external_lead_time_extra_days", "appro amont delai +"),
        ]
        for field, label in extra_day_fields:
            value = to_float(row.get(field))
            if value is None or math.isnan(value) or abs(value) <= 1e-9:
                continue
            factors.append(f"{label}{fmt_qty(value, 1)}j")
        writeoff = to_float(row.get("stock_writeoff_fraction"))
        if writeoff is not None and not math.isnan(writeoff) and writeoff > 1e-9:
            factors.append(f"perte stock {fmt_pct(writeoff * 100.0, 0)}")
        return factors

    def local_route_label(row: dict[str, str], supplier_id: str) -> str:
        edge_id = str(row.get("edge_id") or "")
        dst_node_id = str(row.get("dst_node_id") or "")
        item_id = str(row.get("item_id") or "")
        item_label = label_item(item_id)
        if edge_id == "SUPPLIER_UPSTREAM_SUPPLY_PROACTIVE":
            return f"appro amont -> {label_node(dst_node_id or supplier_id)} / {item_label}"
        if edge_id:
            return edge_display_label(edge_id)
        if dst_node_id:
            return f"{label_node(supplier_id)} -> {label_node(dst_node_id)} / {item_label}"
        return f"{label_node(supplier_id)} / {item_label}"

    def local_application_summary(
        rows: list[dict[str, str]],
        family: str,
        supplier_id: str,
    ) -> dict[str, Any]:
        if not rows:
            return {
                "applied": False,
                "line_count": 0,
                "day_count": 0,
                "first_day": None,
                "last_day": None,
                "max_intensity_pct": 0.0,
                "factor_labels": [],
                "route_labels": [],
                "destination_labels": [],
                "edge_ids": [],
                "summary": "non applique localement",
            }
        days = sorted({
            int(to_float(row.get("day")) or 0)
            for row in rows
            if str(row.get("day") or "").strip() != ""
        })
        max_score = max((supplier_risk_family_severity(row, family) for row in rows), default=0.0)
        factor_labels = sorted({
            factor
            for row in rows
            for factor in active_factor_text(row)
            if factor
        })
        route_labels = sorted({
            local_route_label(row, supplier_id)
            for row in rows
            if row
        })
        destination_labels = sorted({
            label_node(str(row.get("dst_node_id") or ""))
            for row in rows
            if str(row.get("dst_node_id") or "").strip()
        })
        edge_ids = sorted({
            str(row.get("edge_id") or "")
            for row in rows
            if str(row.get("edge_id") or "").strip()
        })
        return {
            "applied": True,
            "line_count": len(rows),
            "day_count": len(days),
            "first_day": days[0] if days else None,
            "last_day": days[-1] if days else None,
            "max_intensity_pct": round(max_score * 100.0, 6),
            "factor_labels": factor_labels,
            "route_labels": route_labels,
            "destination_labels": destination_labels,
            "edge_ids": edge_ids,
            "summary": f"{len(rows)} ligne(s), {len(days)} jour(s), intensite max {fmt_pct(max_score * 100.0, 0)}",
        }

    def risk_row_has_cost_effect(row: dict[str, str]) -> bool:
        return any(
            (to_float(row.get(field)) or 1.0) > 1.000001
            for field in (
                "purchase_cost_multiplier",
                "transport_cost_multiplier",
                "external_cost_multiplier",
            )
        )

    def cost_signal(rows: list[dict[str, str]], family: str) -> tuple[bool, str]:
        if not rows:
            return False, "pas de surcout local"
        if family == "cost" or any(risk_row_has_cost_effect(row) for row in rows):
            return True, "evenement cout applique localement"
        return False, "pas de surcout local"

    def event_label(event: dict[str, Any]) -> str:
        supplier = label_node(str(event.get("supplier_id") or event.get("node_id") or ""))
        item = label_item(str(event.get("item_id") or ""))
        trigger = str(event.get("trigger_metric") or event.get("risk_type") or event.get("risk_family") or "signal")
        return f"{supplier} / {item} / {trigger}"

    family_root_cause_labels = {
        "stock": "Stock fournisseur insuffisant",
        "lead": "Delai fournisseur ou transport rallonge",
        "upstream": "Appro amont fournisseur degrade",
        "quality": "Qualite ou disponibilite utile reduite",
        "availability": "Disponibilite fournisseur reduite",
        "capacity": "Capacite fournisseur reduite",
        "cost": "Cout fournisseur degrade",
        "reliability": "Fiabilite fournisseur degradee",
        "other": "Signal fournisseur",
    }
    absorption_by_stage = {
        "service_client": ("client_reached", "Client atteint"),
        "production": ("production_blocked", "Absorbe partiellement: production reportee"),
        "cost": ("economic_absorbed", "Absorbe par surcout"),
        "local_absorbed": ("local_absorbed", "Absorbe localement"),
        "configured_only": ("inactive", "Signal sans effet applique"),
    }

    def cascade_root_cause_label(event: dict[str, Any], family: str, start_day: int) -> str:
        supplier = label_node(str(event.get("supplier_id") or event.get("node_id") or ""))
        item = label_item(str(event.get("item_id") or ""))
        trigger = str(event.get("trigger_metric") or event.get("risk_type") or event.get("risk_family") or "signal")
        cause = family_root_cause_labels.get(family, family_root_cause_labels["other"])
        return f"{supplier} / {item} - {cause}, declenche par {trigger}, J{start_day}"

    def cascade_absorption(stage: str) -> tuple[str, str]:
        return absorption_by_stage.get(stage, ("other", "Effet a qualifier"))

    def cascade_action(stage: str, supplier_id: str, item_id: str, factory_nodes: set[str], customer_nodes: set[str]) -> dict[str, Any]:
        target_nodes = sorted({supplier_id, *factory_nodes, *customer_nodes} - {""})
        target_items = [item_id] if item_id else []
        if stage == "service_client":
            return {
                "priority": "high",
                "label": "Proteger le service client",
                "target_node_ids": target_nodes,
                "target_item_ids": target_items,
                "rationale": "Backlog client observe: arbitrer allocation, expedition acceleree, achat spot ou second source.",
            }
        if stage == "production":
            return {
                "priority": "high",
                "label": "Securiser l'intrant bloquant",
                "target_node_ids": target_nodes,
                "target_item_ids": target_items,
                "rationale": "Production reportee: avancer reception, augmenter stock tampon ou prioriser l'approvisionnement.",
            }
        if stage == "cost":
            return {
                "priority": "medium",
                "label": "Arbitrer cout versus service",
                "target_node_ids": target_nodes,
                "target_item_ids": target_items,
                "rationale": "Surcout observe: comparer transport accelere, achat alternatif et maintien nominal.",
            }
        if stage == "local_absorbed":
            return {
                "priority": "low",
                "label": "Surveiller le buffer",
                "target_node_ids": target_nodes,
                "target_item_ids": target_items,
                "rationale": "Effet local absorbe avant production ou client: suivre stock, capacite et prochaines receptions.",
            }
        return {
            "priority": "none",
            "label": "Verifier le seuil",
            "target_node_ids": target_nodes,
            "target_item_ids": target_items,
            "rationale": "Signal configure sans effet observe: verifier le parametrage si un impact etait attendu.",
        }

    def first_day(rows: list[dict[str, Any]]) -> int | None:
        days = [
            int(to_float(row.get("day")) or 0)
            for row in rows
            if str(row.get("day") or "").strip() != ""
        ]
        return min(days) if days else None

    def cascade_timeline_steps(
        *,
        event: dict[str, Any],
        family: str,
        stage: str,
        start_day: int,
        end_day: int,
        local_text: str,
        event_applied_rows: list[dict[str, str]],
        production_rows: list[dict[str, Any]],
        service_rows: list[dict[str, Any]],
        reading: str,
        affected_factory_nodes: set[str],
        affected_customer_nodes: set[str],
        impacted_output_items: set[str],
    ) -> list[dict[str, Any]]:
        supplier_id = str(event.get("supplier_id") or event.get("node_id") or "")
        item_id = str(event.get("item_id") or "")
        trigger_day = event_int(event, "trigger_day", start_day)
        steps: list[dict[str, Any]] = [
            {
                "step": "trigger",
                "day": trigger_day,
                "label": "Declenchement",
                "detail": family_root_cause_labels.get(family, family_root_cause_labels["other"]),
                "node_ids": [supplier_id] if supplier_id else [],
                "item_ids": [item_id] if item_id else [],
                "status": "observed",
            }
        ]
        local_day = first_day(event_applied_rows)
        if local_day is not None:
            dst_nodes = sorted({
                str(row.get("dst_node_id") or "")
                for row in event_applied_rows
                if str(row.get("dst_node_id") or "").strip()
            })
            steps.append(
                {
                    "step": "local_application",
                    "day": local_day,
                    "label": "Effet applique localement",
                    "detail": local_text,
                    "node_ids": sorted({supplier_id, *dst_nodes} - {""}),
                    "item_ids": [item_id] if item_id else [],
                    "status": "observed",
                }
            )
        production_day = first_day(production_rows)
        if production_day is not None:
            steps.append(
                {
                    "step": "production_delay",
                    "day": production_day,
                    "label": "Propagation production",
                    "detail": "Production reportee par manque d'intrant.",
                    "node_ids": sorted(affected_factory_nodes),
                    "item_ids": sorted(impacted_output_items),
                    "status": "observed",
                }
            )
        service_day = first_day(service_rows)
        if service_day is not None:
            steps.append(
                {
                    "step": "customer_backlog",
                    "day": service_day,
                    "label": "Effet client",
                    "detail": "Backlog client observe.",
                    "node_ids": sorted(affected_customer_nodes),
                    "item_ids": sorted(impacted_output_items),
                    "status": "observed",
                }
            )
        final_level, final_label = cascade_absorption(stage)
        steps.append(
            {
                "step": "absorption",
                "day": service_day or production_day or local_day or end_day,
                "label": final_label,
                "detail": reading,
                "node_ids": sorted({supplier_id, *affected_factory_nodes, *affected_customer_nodes} - {""}),
                "item_ids": sorted({item_id, *impacted_output_items} - {""}),
                "status": final_level,
            }
        )
        return steps

    raw_edge_ids = {
        str(edge.get("id") or "")
        for edge in raw.get("edges", []) or []
        if isinstance(edge, dict) and str(edge.get("id") or "")
    }

    daily_cost_by_day: dict[int, float] = defaultdict(float)
    for row in daily_rows:
        day = int(to_float(row.get("day")) or 0)
        daily_cost_by_day[day] += max(0.0, to_float(row.get("external_procurement_transport_cost_day")) or 0.0)
        daily_cost_by_day[day] += max(0.0, to_float(row.get("external_procurement_purchase_cost_day")) or 0.0)
    cost_signal_rows_by_day: dict[int, int] = defaultdict(int)
    for row in applied_rows:
        if not risk_row_has_cost_effect(row):
            continue
        day = int(to_float(row.get("day")) or 0)
        cost_signal_rows_by_day[day] += 1

    def allocated_cost_for_event_rows(rows: list[dict[str, str]], start_day: int, end_day: int) -> float:
        cost_days = {
            int(to_float(row.get("day")) or 0)
            for row in rows
            if risk_row_has_cost_effect(row)
        }
        return sum(
            max(0.0, daily_cost_by_day.get(day, 0.0)) / max(1, cost_signal_rows_by_day.get(day, 1))
            for day in cost_days
            if start_day <= day <= end_day
        )

    cascade_rows: list[dict[str, Any]] = []
    cascade_followup_by_family = {
        "lead": 56,
        "upstream": 56,
        "quality": 42,
        "stock": 35,
        "availability": 35,
        "capacity": 35,
        "cost": 14,
    }
    for event in configured_events:
        event_id = str(event.get("event_id") or "").strip()
        if not event_id:
            continue
        family = supplier_risk_family_for_event(event)
        source_kind = supplier_risk_event_source_kind(event)
        start_day, end_day = event_start_end(event)
        followup_days = cascade_followup_by_family.get(family, 35)
        production_window_end = end_day + followup_days
        service_window_end = end_day + max(45, followup_days)
        event_item = str(event.get("item_id") or "")
        event_applied_rows = applied_rows_by_event.get(event_id, [])
        supplier_id = str(event.get("supplier_id") or event.get("node_id") or "")
        local_destination_nodes = {
            str(row.get("dst_node_id") or "")
            for row in event_applied_rows
            if str(row.get("dst_node_id") or "").strip()
            and str(row.get("dst_node_id") or "").strip() != supplier_id
        }
        configured_dst_node = str(event.get("dst_node_id") or "")
        if configured_dst_node and configured_dst_node != supplier_id:
            local_destination_nodes.add(configured_dst_node)
        local_text, local_score, applied_day_count = local_effect_text(event_applied_rows, family)
        local_application = local_application_summary(event_applied_rows, family, supplier_id)
        cost_flag, cost_text = cost_signal(event_applied_rows, family)

        production_rows = [
            row
            for row in input_delay_rows
            if day_in_window(row, start_day, production_window_end)
            and same_item(str(row.get("binding_input_item_id") or ""), event_item)
        ]
        affected_factory_nodes = {
            str(row.get("node_id") or "")
            for row in production_rows
            if str(row.get("node_id") or "").strip()
        }
        if not affected_factory_nodes:
            affected_factory_nodes = {node_id for node_id in local_destination_nodes if node_is_factory(node_id)}
        if not affected_factory_nodes and node_is_factory(supplier_id):
            affected_factory_nodes.add(supplier_id)
        if not affected_factory_nodes and event_item:
            affected_factory_nodes = downstream_factory_nodes_for_item(supplier_id, event_item)
        impacted_output_items = {
            str(row.get("output_item_id") or "")
            for row in production_rows
            if str(row.get("output_item_id") or "").strip()
        }
        if not impacted_output_items and event_item:
            impacted_output_items = output_items_for_component(affected_factory_nodes, event_item)
        if not impacted_output_items and event_item and (
            node_is_factory(supplier_id) or any(node_type_by_id.get(node_id) in {"distribution_center", "customer"} for node_id in local_destination_nodes)
        ):
            impacted_output_items = {event_item}
        service_rows = [
            row
            for row in demand_rows
            if day_in_window(row, start_day, service_window_end)
            and max(0.0, to_float(row.get("backlog_end_qty")) or 0.0) > 1e-9
            and any(same_item(str(row.get("item_id") or ""), item_id) for item_id in impacted_output_items)
        ]
        affected_customer_nodes = {
            str(row.get("node_id") or "")
            for row in service_rows
            if str(row.get("node_id") or "").strip()
        }
        production_shortfall = sum(max(0.0, to_float(row.get("shortfall_vs_lot_plan_qty")) or 0.0) for row in production_rows)
        production_days = {
            int(to_float(row.get("day")) or 0)
            for row in production_rows
            if str(row.get("day") or "").strip() != ""
        }
        backlog_max = max((max(0.0, to_float(row.get("backlog_end_qty")) or 0.0) for row in service_rows), default=0.0)
        backlog_qty_days = sum(max(0.0, to_float(row.get("backlog_end_qty")) or 0.0) for row in service_rows)
        event_cost_window = allocated_cost_for_event_rows(
            event_applied_rows,
            start_day,
            min(service_window_end, end_day + 14),
        ) if cost_flag else 0.0
        impact_modes = []
        if event_applied_rows:
            impact_modes.append("local")
        if cost_flag:
            impact_modes.append("cost")
        if production_rows:
            impact_modes.append("production")
        if service_rows:
            impact_modes.append("service_client")

        if service_rows:
            cascade_stage = "service_client"
            cascade_label = "Disponibilite produit"
            reading = f"Backlog max {fmt_qty(backlog_max, 0)} sur {len(service_rows)} ligne(s) client."
            priority = 5
        elif production_rows:
            cascade_stage = "production"
            cascade_label = "Production reportee"
            reading = f"{len(production_rows)} report(s), {fmt_qty(production_shortfall, 0)} de volume lotifie reporte."
            priority = 4
        elif cost_flag:
            cascade_stage = "cost"
            cascade_label = "Cout local"
            reading = cost_text
            priority = 3
        elif event_applied_rows:
            cascade_stage = "local_absorbed"
            cascade_label = "Local absorbe"
            reading = "Effet applique localement, sans report production ni backlog client observe dans la fenetre."
            priority = 2
        else:
            cascade_stage = "configured_only"
            cascade_label = "Declenche sans effet applique"
            reading = "Evenement configure/generé, mais pas applique dans la trajectoire observee."
            priority = 1
        impact_score = (
            priority * 1_000_000.0
            + production_shortfall
            + backlog_qty_days * 10.0
            + applied_day_count * 1000.0
            + local_score * 1000.0
            + (min(event_cost_window, 1_000_000.0) if cost_flag else 0.0)
        )
        period = f"J{start_day} -> J{end_day}"
        if production_window_end > end_day:
            period += f" (+{followup_days}j aval)"
        root_day = (
            min(production_days)
            if production_days
            else (
                min(
                    int(to_float(row.get("day")) or 0)
                    for row in service_rows
                    if str(row.get("day") or "").strip() != ""
                )
                if service_rows
                else start_day
            )
        )
        dst_nodes = {
            str(row.get("dst_node_id") or "")
            for row in event_applied_rows
            if str(row.get("dst_node_id") or "").strip()
        }
        event_edge_ids = sorted({
            str(row.get("edge_id") or "").strip()
            for row in event_applied_rows
            if str(row.get("edge_id") or "").strip() in raw_edge_ids
        })
        root_cause_label = cascade_root_cause_label(event, family, start_day)
        absorption_level, absorption_label = cascade_absorption(cascade_stage)
        timeline_steps = cascade_timeline_steps(
            event=event,
            family=family,
            stage=cascade_stage,
            start_day=start_day,
            end_day=end_day,
            local_text=local_text,
            event_applied_rows=event_applied_rows,
            production_rows=production_rows,
            service_rows=service_rows,
            reading=reading,
            affected_factory_nodes=affected_factory_nodes,
            affected_customer_nodes=affected_customer_nodes,
            impacted_output_items=impacted_output_items,
        )
        highlight_node_ids = sorted({supplier_id, *dst_nodes, *affected_factory_nodes, *affected_customer_nodes} - {""})
        impacted_nodes = []
        if supplier_id:
            impacted_nodes.append(
                {
                    "node_id": supplier_id,
                    "role": "origin_supplier",
                    "label": label_node(supplier_id),
                    "first_day": start_day,
                }
            )
        for node_id in sorted(dst_nodes):
            impacted_nodes.append(
                {
                    "node_id": node_id,
                    "role": "local_destination",
                    "label": label_node(node_id),
                    "first_day": first_day(event_applied_rows) or start_day,
                }
            )
        production_day = first_day(production_rows)
        for node_id in sorted(affected_factory_nodes):
            impacted_nodes.append(
                {
                    "node_id": node_id,
                    "role": "affected_factory",
                    "label": label_node(node_id),
                    "first_day": production_day or root_day,
                }
            )
        service_day = first_day(service_rows)
        for node_id in sorted(affected_customer_nodes):
            impacted_nodes.append(
                {
                    "node_id": node_id,
                    "role": "affected_customer",
                    "label": label_node(node_id),
                    "first_day": service_day or root_day,
                }
            )
        impacted_edges = [
            {
                "edge_id": edge_id,
                "role": "supplier_flow",
                "first_day": first_day(event_applied_rows) or start_day,
                "source": "applied_row",
            }
            for edge_id in event_edge_ids
        ]
        action = cascade_action(
            cascade_stage,
            supplier_id,
            event_item,
            affected_factory_nodes,
            affected_customer_nodes,
        )
        root_key = "|".join(
            [
                cascade_stage,
                supplier_id,
                normalized_item_key(event_item),
                str(root_day),
            ]
        )
        cascade_rows.append(
            {
                "event_id": event_id,
                "source": source_kind,
                "stage": cascade_stage,
                "stage_label": cascade_label,
                "risk_family": family,
                "supplier_id": supplier_id,
                "supplier_label": label_node(supplier_id),
                "item_id": event_item,
                "item_label": label_item(event_item),
                "start_day": start_day,
                "end_day": end_day,
                "duration_days": max(0, int(end_day) - int(start_day) + 1),
                "root_day": root_day,
                "root_key": root_key,
                "period": period,
                "risk_type": str(event.get("risk_type") or ""),
                "configured_effect": str(event.get("effect") or ""),
                "trigger_metric": str(event.get("trigger_metric") or ""),
                "trigger_value": event.get("trigger_value"),
                "threshold": event.get("threshold"),
                "consecutive_days": event.get("consecutive_days"),
                "notes": str(event.get("notes") or ""),
                "trigger": str(event.get("trigger_metric") or event.get("risk_type") or event.get("risk_family") or ""),
                "local_effect": local_text,
                "local_application": local_application,
                "production_delay_count": len(production_rows),
                "production_shortfall_qty": round(production_shortfall, 6),
                "production_delay_days": len(production_days),
                "customer_backlog_max_qty": round(backlog_max, 6),
                "customer_backlog_qty_days": round(backlog_qty_days, 6),
                "affected_factory_nodes": sorted(affected_factory_nodes),
                "affected_factory_labels": [label_node(node_id) for node_id in sorted(affected_factory_nodes)],
                "affected_customer_nodes": sorted(affected_customer_nodes),
                "affected_customer_labels": [label_node(node_id) for node_id in sorted(affected_customer_nodes)],
                "impacted_output_items": sorted(impacted_output_items),
                "impacted_output_item_labels": [label_item(item_id) for item_id in sorted(impacted_output_items)],
                "propagation_summary": {
                    "production_window_end_day": production_window_end,
                    "service_window_end_day": service_window_end,
                    "factory_count": len(affected_factory_nodes),
                    "customer_count": len(affected_customer_nodes),
                    "output_item_count": len(impacted_output_items),
                    "edge_count": len(event_edge_ids),
                    "has_production_delay": bool(production_rows),
                    "has_customer_backlog": bool(service_rows),
                    "has_cost_signal": bool(cost_flag),
                    "reading": reading,
                },
                "cost_signal": cost_text,
                "cost_impact_qty": round(event_cost_window, 6),
                "impact_score": round(impact_score, 6),
                "impact_modes": sorted(set(impact_modes)),
                "root_cause_label": root_cause_label,
                "absorption_level": absorption_level,
                "absorption_label": absorption_label,
                "timeline_steps": timeline_steps,
                "highlight_node_ids": highlight_node_ids,
                "highlight_edge_ids": event_edge_ids,
                "impacted_nodes": impacted_nodes,
                "impacted_edges": impacted_edges,
                "impacted_edge_labels": event_edge_ids,
                "action": action,
                "label": event_label(event),
                "reading": reading,
                "table_row": {
                    "Statut": cascade_label,
                    "Fournisseur": label_node(supplier_id),
                    "Article declencheur": label_item(event_item),
                    "Site(s)": ", ".join(label_node(node_id) for node_id in sorted(affected_factory_nodes)) or "n/a",
                    "PF/PFI touche(s)": ", ".join(label_item(item_id) for item_id in sorted(impacted_output_items)) or "n/a",
                    "Declencheur": root_cause_label,
                    "Periode": period,
                    "Duree": f"{max(0, int(end_day) - int(start_day) + 1)} j",
                    "Effet local": local_text,
                    "Volume reporte": fmt_qty(production_shortfall, 0),
                    "Backlog max": fmt_qty(backlog_max, 0),
                    "Aval observe": reading,
                    "Source": "state-dependent" if source_kind == "state" else "scenario",
                },
            }
        )

    cascade_event_stage_counts: dict[str, int] = defaultdict(int)
    for row in cascade_rows:
        cascade_event_stage_counts[str(row["stage"])] += 1

    cascade_groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in cascade_rows:
        cascade_groups[str(row.get("root_key") or row.get("event_id") or "")].append(row)

    def merge_cascade_group(rows: list[dict[str, Any]]) -> dict[str, Any]:
        representative = max(rows, key=lambda row: float(row.get("impact_score") or 0.0))
        stage = str(representative.get("stage") or "")
        families = sorted({str(row.get("risk_family") or "other") for row in rows})
        sources = sorted({str(row.get("source") or "scenario") for row in rows})
        source_text = ", ".join("state-dependent" if source == "state" else source for source in sources)
        family_text = ", ".join(
            SIMULATED_RISK_FAMILY_INFO.get(family, SIMULATED_RISK_FAMILY_INFO["other"])["label"]
            for family in families
        )
        start_day = min(int(row.get("start_day") or 0) for row in rows)
        end_day = max(int(row.get("end_day") or start_day) for row in rows)
        production_delay_count = max(int(row.get("production_delay_count") or 0) for row in rows)
        production_shortfall = max(float(row.get("production_shortfall_qty") or 0.0) for row in rows)
        backlog_max = max(float(row.get("customer_backlog_max_qty") or 0.0) for row in rows)
        backlog_qty_days = max(float(row.get("customer_backlog_qty_days") or 0.0) for row in rows)
        cost_impact = max(float(row.get("cost_impact_qty") or 0.0) for row in rows)
        local_applied = sum(1 for row in rows if str(row.get("local_effect") or "").startswith("non applique") is False)
        affected_factory_nodes = sorted({
            str(node_id)
            for row in rows
            for node_id in (row.get("affected_factory_nodes") or [])
            if str(node_id)
        })
        affected_customer_nodes = sorted({
            str(node_id)
            for row in rows
            for node_id in (row.get("affected_customer_nodes") or [])
            if str(node_id)
        })
        impacted_output_items = sorted({
            str(item_id)
            for row in rows
            for item_id in (row.get("impacted_output_items") or [])
            if str(item_id)
        })
        highlight_node_ids = sorted({
            str(node_id)
            for row in rows
            for node_id in (row.get("highlight_node_ids") or [])
            if str(node_id)
        })
        highlight_edge_ids = sorted({
            str(edge_id)
            for row in rows
            for edge_id in (row.get("highlight_edge_ids") or [])
            if str(edge_id)
        })
        impact_modes = sorted({
            str(mode)
            for row in rows
            for mode in (row.get("impact_modes") or [])
            if str(mode)
        })
        local_applications = [
            row.get("local_application")
            for row in rows
            if isinstance(row.get("local_application"), dict)
        ]
        local_factor_labels = sorted({
            str(value)
            for app in local_applications
            for value in (app.get("factor_labels") or [])
            if str(value)
        })
        local_route_labels = sorted({
            str(value)
            for app in local_applications
            for value in (app.get("route_labels") or [])
            if str(value)
        })
        local_destination_labels = sorted({
            str(value)
            for app in local_applications
            for value in (app.get("destination_labels") or [])
            if str(value)
        })
        local_edge_ids = sorted({
            str(value)
            for app in local_applications
            for value in (app.get("edge_ids") or [])
            if str(value)
        })
        local_application = {
            "applied": bool(local_applications),
            "line_count": sum(int(app.get("line_count") or 0) for app in local_applications),
            "day_count": len({
                day
                for app in local_applications
                for day in range(
                    int(app.get("first_day") or 0),
                    int(app.get("last_day") or int(app.get("first_day") or 0)) + 1,
                )
                if day > 0
            }),
            "first_day": min(
                (int(app.get("first_day") or 0) for app in local_applications if app.get("first_day") is not None),
                default=None,
            ),
            "last_day": max(
                (int(app.get("last_day") or 0) for app in local_applications if app.get("last_day") is not None),
                default=None,
            ),
            "max_intensity_pct": max((float(app.get("max_intensity_pct") or 0.0) for app in local_applications), default=0.0),
            "factor_labels": local_factor_labels,
            "route_labels": local_route_labels,
            "destination_labels": local_destination_labels,
            "edge_ids": local_edge_ids,
            "summary": f"{local_applied}/{len(rows)} signal(aux) applique(s) localement",
        }

        def merge_impacted_nodes() -> list[dict[str, Any]]:
            merged: dict[tuple[str, str], dict[str, Any]] = {}
            for row in rows:
                for node in row.get("impacted_nodes") or []:
                    node_id = str(node.get("node_id") or "")
                    role = str(node.get("role") or "")
                    if not node_id:
                        continue
                    key = (node_id, role)
                    first_day = int(node.get("first_day") or 0)
                    current = merged.get(key)
                    if not current:
                        merged[key] = {
                            "node_id": node_id,
                            "role": role,
                            "label": str(node.get("label") or label_node(node_id)),
                            "first_day": first_day,
                        }
                    else:
                        current["first_day"] = min(int(current.get("first_day") or first_day), first_day)
            return sorted(merged.values(), key=lambda node: (int(node.get("first_day") or 0), str(node.get("role") or ""), str(node.get("node_id") or "")))

        def merge_impacted_edges() -> list[dict[str, Any]]:
            merged: dict[str, dict[str, Any]] = {}
            for row in rows:
                for edge in row.get("impacted_edges") or []:
                    edge_id = str(edge.get("edge_id") or "")
                    if not edge_id:
                        continue
                    first_day = int(edge.get("first_day") or 0)
                    current = merged.get(edge_id)
                    if not current:
                        merged[edge_id] = {
                            "edge_id": edge_id,
                            "role": str(edge.get("role") or "supplier_flow"),
                            "first_day": first_day,
                            "source": str(edge.get("source") or "applied_row"),
                        }
                    else:
                        current["first_day"] = min(int(current.get("first_day") or first_day), first_day)
            return sorted(merged.values(), key=lambda edge: (int(edge.get("first_day") or 0), str(edge.get("edge_id") or "")))

        def merge_timeline_steps() -> list[dict[str, Any]]:
            step_order = ["trigger", "local_application", "production_delay", "customer_backlog", "absorption"]
            merged: dict[str, dict[str, Any]] = {}
            for row in rows:
                for step in row.get("timeline_steps") or []:
                    step_key = str(step.get("step") or "")
                    if not step_key:
                        continue
                    day = int(step.get("day") or 0)
                    current = merged.get(step_key)
                    if not current or day < int(current.get("day") or day):
                        merged[step_key] = dict(step)
                        current = merged[step_key]
                    current["node_ids"] = sorted({
                        *[str(value) for value in current.get("node_ids") or [] if str(value)],
                        *[str(value) for value in step.get("node_ids") or [] if str(value)],
                    })
                    current["item_ids"] = sorted({
                        *[str(value) for value in current.get("item_ids") or [] if str(value)],
                        *[str(value) for value in step.get("item_ids") or [] if str(value)],
                    })
            return [
                merged[key]
                for key in step_order
                if key in merged
            ]

        absorption_level, absorption_label = cascade_absorption(stage)
        action = cascade_action(
            stage,
            str(representative.get("supplier_id") or ""),
            str(representative.get("item_id") or ""),
            set(affected_factory_nodes),
            set(affected_customer_nodes),
        )
        if stage == "service_client":
            reading = f"Backlog max {fmt_qty(backlog_max, 0)} ; backlog cumule {fmt_qty(backlog_qty_days, 0)}."
        elif stage == "production":
            reading = f"{production_delay_count} report(s), {fmt_qty(production_shortfall, 0)} de volume lotifie reporte."
        elif stage == "cost":
            reading = "Surcout local observe sur au moins un effet applique."
        elif stage == "local_absorbed":
            reading = "Effets appliques localement, absorbes avant production/service dans la fenetre."
        else:
            reading = "Signaux generes, sans effet applique dans la trajectoire observee."
        trigger_text = (
            f"{representative.get('label') or ''} - {len(rows)} signal(aux): {family_text}"
            if len(rows) > 1
            else str(representative.get("label") or "")
        )
        supplier_id = str(representative.get("supplier_id") or "")
        item_id = str(representative.get("item_id") or "")
        affected_factory_labels = [label_node(node_id) for node_id in affected_factory_nodes]
        affected_customer_labels = [label_node(node_id) for node_id in affected_customer_nodes]
        impacted_output_item_labels = [label_item(item_id) for item_id in impacted_output_items]
        impacted_edge_labels = highlight_edge_ids
        duration_days = max(0, int(end_day) - int(start_day) + 1)
        return {
            **representative,
            "event_count": len(rows),
            "event_ids": [str(row.get("event_id") or "") for row in rows],
            "risk_families": families,
            "source": source_text,
            "start_day": start_day,
            "end_day": end_day,
            "duration_days": duration_days,
            "period": f"J{start_day} -> J{end_day}",
            "supplier_label": label_node(supplier_id),
            "item_label": label_item(item_id),
            "risk_type": str(representative.get("risk_type") or ""),
            "configured_effect": str(representative.get("configured_effect") or ""),
            "trigger_metric": str(representative.get("trigger_metric") or representative.get("trigger") or ""),
            "trigger_value": representative.get("trigger_value"),
            "threshold": representative.get("threshold"),
            "consecutive_days": representative.get("consecutive_days"),
            "notes": str(representative.get("notes") or ""),
            "local_effect": f"{local_applied}/{len(rows)} signal(aux) applique(s) localement",
            "local_application": local_application,
            "production_delay_count": production_delay_count,
            "production_shortfall_qty": round(production_shortfall, 6),
            "customer_backlog_max_qty": round(backlog_max, 6),
            "customer_backlog_qty_days": round(backlog_qty_days, 6),
            "cost_impact_qty": round(cost_impact, 6),
            "affected_factory_nodes": affected_factory_nodes,
            "affected_factory_labels": affected_factory_labels,
            "affected_customer_nodes": affected_customer_nodes,
            "affected_customer_labels": affected_customer_labels,
            "impacted_output_items": impacted_output_items,
            "impacted_output_item_labels": impacted_output_item_labels,
            "propagation_summary": {
                "production_window_end_day": max(
                    (
                        int((row.get("propagation_summary") or {}).get("production_window_end_day") or row.get("end_day") or end_day)
                        for row in rows
                        if isinstance(row.get("propagation_summary"), dict)
                    ),
                    default=end_day,
                ),
                "service_window_end_day": max(
                    (
                        int((row.get("propagation_summary") or {}).get("service_window_end_day") or row.get("end_day") or end_day)
                        for row in rows
                        if isinstance(row.get("propagation_summary"), dict)
                    ),
                    default=end_day,
                ),
                "factory_count": len(affected_factory_nodes),
                "customer_count": len(affected_customer_nodes),
                "output_item_count": len(impacted_output_items),
                "edge_count": len(highlight_edge_ids),
                "has_production_delay": production_delay_count > 0,
                "has_customer_backlog": backlog_max > 0,
                "has_cost_signal": stage == "cost" or "cost" in impact_modes,
                "reading": reading,
            },
            "impact_modes": impact_modes,
            "root_cause_label": (
                str(representative.get("root_cause_label") or trigger_text)
                if len(rows) == 1
                else f"{trigger_text}"
            ),
            "absorption_level": absorption_level,
            "absorption_label": absorption_label,
            "timeline_steps": merge_timeline_steps(),
            "highlight_node_ids": highlight_node_ids,
            "highlight_edge_ids": highlight_edge_ids,
            "impacted_nodes": merge_impacted_nodes(),
            "impacted_edges": merge_impacted_edges(),
            "impacted_edge_labels": impacted_edge_labels,
            "action": action,
            "reading": reading,
            "table_row": {
                "Statut": str(representative.get("stage_label") or ""),
                "Fournisseur": label_node(supplier_id),
                "Article declencheur": label_item(item_id),
                "Site(s)": ", ".join(affected_factory_labels) or "n/a",
                "PF/PFI touche(s)": ", ".join(impacted_output_item_labels) or "n/a",
                "Declencheur": trigger_text,
                "Periode": f"J{start_day} -> J{end_day}",
                "Duree": f"{duration_days} j",
                "Effet local": f"{local_applied}/{len(rows)} signal(aux) applique(s)",
                "Volume reporte": fmt_qty(production_shortfall, 0),
                "Backlog max": fmt_qty(backlog_max, 0),
                "Aval observe": reading,
                "Source": source_text,
            },
        }

    cascade_root_rows = [merge_cascade_group(rows) for rows in cascade_groups.values() if rows]

    business_path_groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in cascade_root_rows:
        supplier_id = str(row.get("supplier_id") or "")
        item_id = normalized_item_key(str(row.get("item_id") or ""))
        factory_key = ",".join(sorted(str(node_id) for node_id in (row.get("affected_factory_nodes") or []) if str(node_id))) or "no_factory"
        output_key = ",".join(sorted(normalized_item_key(str(item_id)) for item_id in (row.get("impacted_output_items") or []) if str(item_id))) or "no_output"
        stage = str(row.get("stage") or "other")
        key = "|".join([supplier_id, item_id, factory_key, output_key, stage])
        business_path_groups[key].append(row)

    def merge_business_path_group(key: str, rows: list[dict[str, Any]]) -> dict[str, Any]:
        representative = max(rows, key=lambda row: float(row.get("impact_score") or 0.0))
        stage = str(representative.get("stage") or "other")
        supplier_id = str(representative.get("supplier_id") or "")
        item_id = str(representative.get("item_id") or "")
        families = sorted({
            str(family)
            for row in rows
            for family in (row.get("risk_families") or [row.get("risk_family") or "other"])
            if str(family)
        })
        sources = sorted({
            str(source)
            for row in rows
            for source in str(row.get("source") or "scenario").split(",")
            if str(source).strip()
        })
        source_text = ", ".join(source.strip() for source in sources) or "n/a"
        start_day = min(int(row.get("start_day") or 0) for row in rows)
        end_day = max(int(row.get("end_day") or start_day) for row in rows)
        worst = representative
        worst_period = str(worst.get("period") or f"J{worst.get('start_day', start_day)} -> J{worst.get('end_day', end_day)}")
        affected_factory_nodes = sorted({
            str(node_id)
            for row in rows
            for node_id in (row.get("affected_factory_nodes") or [])
            if str(node_id)
        })
        affected_customer_nodes = sorted({
            str(node_id)
            for row in rows
            for node_id in (row.get("affected_customer_nodes") or [])
            if str(node_id)
        })
        impacted_output_items = sorted({
            str(item_id)
            for row in rows
            for item_id in (row.get("impacted_output_items") or [])
            if str(item_id)
        })
        route = route_closure_for_rows(rows)
        route_node_ids = route.get("route_node_ids") or []
        route_edge_ids = route.get("route_edge_ids") or []
        route_edge_labels = route.get("route_edge_labels") or []
        production_shortfall = max(float(row.get("production_shortfall_qty") or 0.0) for row in rows)
        production_shortfall_total_signal = sum(max(0.0, float(row.get("production_shortfall_qty") or 0.0)) for row in rows)
        production_delay_count = max(int(row.get("production_delay_count") or 0) for row in rows)
        production_delay_count_total_signal = sum(max(0, int(row.get("production_delay_count") or 0)) for row in rows)
        backlog_max = max(float(row.get("customer_backlog_max_qty") or 0.0) for row in rows)
        backlog_qty_days = max(float(row.get("customer_backlog_qty_days") or 0.0) for row in rows)
        backlog_qty_days_total_signal = sum(max(0.0, float(row.get("customer_backlog_qty_days") or 0.0)) for row in rows)
        cost_impact = max(float(row.get("cost_impact_qty") or 0.0) for row in rows)
        cost_impact_total_signal = sum(max(0.0, float(row.get("cost_impact_qty") or 0.0)) for row in rows)
        stage_rank = int(stage_info.get(stage, stage_info["other"])["rank"])
        path_score = (
            stage_rank * 1_000_000.0
            + backlog_qty_days * 100.0
            + production_shortfall
            + cost_impact
            + len(rows) * 10_000.0
        )
        action = cascade_action(stage, supplier_id, item_id, set(affected_factory_nodes), set(affected_customer_nodes))
        factory_label = ", ".join(label_node(node_id) for node_id in affected_factory_nodes) or "site non atteint"
        customer_label = ", ".join(label_node(node_id) for node_id in affected_customer_nodes) or "client non atteint"
        output_label = ", ".join(label_item(output_item) for output_item in impacted_output_items) or label_item(item_id)
        business_path_label = (
            f"{label_node(supplier_id)} / {label_item(item_id)} -> {factory_label} -> {output_label} -> "
            f"{stage_info.get(stage, stage_info['other'])['label']}"
        )
        route_text = " -> ".join(
            part
            for part in [
                supplier_id,
                ",".join(affected_factory_nodes),
                "DC/client" if affected_customer_nodes else "",
                ",".join(affected_customer_nodes),
            ]
            if part
        ) or business_path_label
        if stage == "service_client":
            reading = f"Client atteint: backlog max {fmt_qty(backlog_max, 0)}, backlog-jours {fmt_qty(backlog_qty_days, 0)}."
        elif stage == "production":
            reading = f"Production reportee: {production_delay_count} report(s), volume {fmt_qty(production_shortfall, 0)}."
        elif stage == "cost":
            reading = f"Surcout additionnel observe: {fmt_qty(cost_impact, 0)}."
        elif stage == "local_absorbed":
            reading = "Effets appliques puis absorbes avant production ou client."
        else:
            reading = "Signaux configures sans effet applique observable."
        local_application = dict(representative.get("local_application") or {})
        if len(rows) > 1:
            local_application["summary"] = f"{len(rows)} occurrence(s) consolidee(s)"
        impacted_nodes = list(representative.get("impacted_nodes") or [])
        known_node_roles = {(str(node.get("node_id") or ""), str(node.get("role") or "")) for node in impacted_nodes}
        for node_id in route_node_ids:
            role = "route_node"
            if (str(node_id), role) not in known_node_roles:
                impacted_nodes.append(
                    {
                        "node_id": str(node_id),
                        "role": role,
                        "label": label_node(str(node_id)),
                        "first_day": start_day,
                    }
                )
        impacted_edges = list(representative.get("impacted_edges") or [])
        known_edge_ids = {str(edge.get("edge_id") or "") for edge in impacted_edges}
        for edge_id in route_edge_ids:
            if str(edge_id) not in known_edge_ids:
                impacted_edges.append(
                    {
                        "edge_id": str(edge_id),
                        "role": "route",
                        "first_day": start_day,
                        "source": "business_path",
                    }
                )
        return {
            **representative,
            "business_path_key": key,
            "root_key": key,
            "event_id": key,
            "occurrence_count": len(rows),
            "event_count": sum(max(1, int(row.get("event_count") or 1)) for row in rows),
            "event_ids": sorted({
                str(event_id)
                for row in rows
                for event_id in (row.get("event_ids") or [row.get("event_id")])
                if str(event_id)
            }),
            "risk_families": families,
            "source": source_text,
            "stage": stage,
            "stage_label": stage_info.get(stage, stage_info["other"])["label"],
            "start_day": start_day,
            "end_day": end_day,
            "duration_days": max(0, end_day - start_day + 1),
            "period": f"J{start_day} -> J{end_day}",
            "worst_period": worst_period,
            "supplier_id": supplier_id,
            "supplier_label": label_node(supplier_id),
            "item_id": item_id,
            "item_label": label_item(item_id),
            "affected_factory_nodes": affected_factory_nodes,
            "affected_factory_labels": [label_node(node_id) for node_id in affected_factory_nodes],
            "affected_customer_nodes": affected_customer_nodes,
            "affected_customer_labels": [label_node(node_id) for node_id in affected_customer_nodes],
            "impacted_output_items": impacted_output_items,
            "impacted_output_item_labels": [label_item(output_item) for output_item in impacted_output_items],
            "production_delay_count": production_delay_count,
            "production_delay_count_total_signal": production_delay_count_total_signal,
            "production_shortfall_qty": round(production_shortfall, 6),
            "production_shortfall_qty_total_signal": round(production_shortfall_total_signal, 6),
            "customer_backlog_max_qty": round(backlog_max, 6),
            "customer_backlog_qty_days": round(backlog_qty_days, 6),
            "customer_backlog_qty_days_total_signal": round(backlog_qty_days_total_signal, 6),
            "cost_impact_qty": round(cost_impact, 6),
            "cost_impact_qty_total_signal": round(cost_impact_total_signal, 6),
            "impact_score": round(path_score, 6),
            "business_path_label": business_path_label,
            "route_text": route_text,
            "route_node_ids": route_node_ids,
            "route_edge_ids": route_edge_ids,
            "route_edges": route.get("route_edges") or [],
            "route_edge_labels": route_edge_labels,
            "highlight_node_ids": sorted(set(route_node_ids) | {str(node_id) for node_id in (representative.get("highlight_node_ids") or []) if str(node_id)}),
            "highlight_edge_ids": sorted(set(route_edge_ids) | {str(edge_id) for edge_id in (representative.get("highlight_edge_ids") or []) if str(edge_id)}),
            "impacted_nodes": sorted(impacted_nodes, key=lambda node: (int(node.get("first_day") or 0), str(node.get("role") or ""), str(node.get("node_id") or ""))),
            "impacted_edges": sorted(impacted_edges, key=lambda edge: (int(edge.get("first_day") or 0), str(edge.get("role") or ""), str(edge.get("edge_id") or ""))),
            "impacted_edge_labels": route_edge_labels,
            "local_application": local_application,
            "reading": reading,
            "root_cause_label": business_path_label,
            "action": action,
            "table_row": {
                "Chemin metier": business_path_label,
                "Occurrences": str(len(rows)),
                "Pire periode": worst_period,
                "Production reportee": f"{production_delay_count} report(s), {fmt_qty(production_shortfall, 0)}",
                "Backlog max": fmt_qty(backlog_max, 0),
                "Backlog-jours": fmt_qty(backlog_qty_days, 0),
                "Cout additionnel": fmt_qty(cost_impact, 0),
                "Chemin carte": f"{len(route_node_ids)} noeud(s), {len(route_edge_ids)} flux",
                "Action recommandee": str(action.get("label") or "n/a"),
            },
        }

    cascade_path_groups = [
        merge_business_path_group(key, rows)
        for key, rows in business_path_groups.items()
        if rows
    ]
    cascade_path_groups.sort(
        key=lambda row: (
            -int(stage_info.get(str(row.get("stage") or "other"), stage_info["other"])["rank"]),
            -float(row.get("impact_score") or 0.0),
            str(row.get("business_path_key") or ""),
        )
    )

    cascade_stage_counts: dict[str, int] = defaultdict(int)
    for row in cascade_root_rows:
        cascade_stage_counts[str(row["stage"])] += 1
    effective_cascade_rows = [
        row for row in cascade_root_rows if row["stage"] in {"service_client", "production", "cost"}
    ]
    visible_cascade_rows = sorted(
        [row for row in cascade_root_rows if row["stage"] != "configured_only"] or cascade_root_rows,
        key=lambda row: (-float(row.get("impact_score") or 0.0), str(row.get("event_id") or "")),
    )[:12]
    visible_path_group_rows = [
        row for row in cascade_path_groups if str(row.get("stage") or "") != "configured_only"
    ][:12] or cascade_path_groups[:12]
    path_group_table_rows = [dict(row["table_row"]) for row in visible_path_group_rows]
    cascade_table_rows = [dict(row["table_row"]) for row in visible_cascade_rows]
    cascade_summary_text = (
        f"{len(effective_cascade_rows)} cascade(s) avec impact supply: "
        f"{cascade_stage_counts.get('service_client', 0)} service client, "
        f"{cascade_stage_counts.get('production', 0)} production, "
        f"{cascade_stage_counts.get('cost', 0)} cout. "
        f"{cascade_stage_counts.get('local_absorbed', 0)} effet(s) absorbe(s) localement. "
        f"{len(cascade_path_groups)} chemin(s) metier consolide(s)."
    )

    origin_stats: dict[tuple[str, str], dict[str, Any]] = defaultdict(lambda: {
        "roots": 0,
        "effective_roots": 0,
        "signals": 0,
        "stages": defaultdict(int),
        "families": defaultdict(int),
        "first_day": math.inf,
        "last_day": -math.inf,
        "production_shortfall_qty": 0.0,
        "production_delay_count": 0,
        "customer_backlog_max_qty": 0.0,
        "customer_backlog_qty_days": 0.0,
        "cost_roots": 0,
        "local_absorbed_roots": 0,
        "affected_factory_nodes": set(),
        "affected_customer_nodes": set(),
        "impacted_output_items": set(),
        "impact_score": 0.0,
        "top_root": None,
    })
    for row in cascade_root_rows:
        key = (str(row.get("supplier_id") or ""), str(row.get("item_id") or ""))
        stats = origin_stats[key]
        stage = str(row.get("stage") or "other")
        stats["roots"] += 1
        stats["signals"] += max(1, int(row.get("event_count") or 1))
        stats["stages"][stage] += 1
        if stage in {"service_client", "production", "cost"}:
            stats["effective_roots"] += 1
        if stage == "cost":
            stats["cost_roots"] += 1
        if stage == "local_absorbed":
            stats["local_absorbed_roots"] += 1
        for family in row.get("risk_families") or [row.get("risk_family") or "other"]:
            stats["families"][str(family or "other")] += 1
        stats["first_day"] = min(float(stats["first_day"]), float(row.get("start_day") or 0))
        stats["last_day"] = max(float(stats["last_day"]), float(row.get("end_day") or 0))
        stats["production_shortfall_qty"] += max(0.0, float(row.get("production_shortfall_qty") or 0.0))
        stats["production_delay_count"] += max(0, int(row.get("production_delay_count") or 0))
        stats["customer_backlog_max_qty"] = max(
            float(stats["customer_backlog_max_qty"]),
            max(0.0, float(row.get("customer_backlog_max_qty") or 0.0)),
        )
        stats["customer_backlog_qty_days"] += max(0.0, float(row.get("customer_backlog_qty_days") or 0.0))
        stats["affected_factory_nodes"].update(str(node_id) for node_id in (row.get("affected_factory_nodes") or []) if str(node_id))
        stats["affected_customer_nodes"].update(str(node_id) for node_id in (row.get("affected_customer_nodes") or []) if str(node_id))
        stats["impacted_output_items"].update(str(item_id) for item_id in (row.get("impacted_output_items") or []) if str(item_id))
        stats["impact_score"] += max(0.0, float(row.get("impact_score") or 0.0))
        top_root = stats.get("top_root")
        if not isinstance(top_root, dict) or float(row.get("impact_score") or 0.0) > float(top_root.get("impact_score") or 0.0):
            stats["top_root"] = row

    def dominant_stage_key(stage_counts: dict[str, int]) -> str:
        if not stage_counts:
            return "other"
        return max(
            stage_counts,
            key=lambda value: (
                int(stage_info.get(value, stage_info["other"])["rank"]),
                int(stage_counts[value]),
            ),
        )

    def dominant_stage_label(stage_counts: dict[str, int]) -> str:
        stage = dominant_stage_key(stage_counts)
        return str(stage_info.get(stage, stage_info["other"])["label"])

    def origin_family_text(families: dict[str, int]) -> str:
        parts = []
        for family, count in sorted(families.items(), key=lambda item: (-int(item[1]), item[0]))[:3]:
            label = SIMULATED_RISK_FAMILY_INFO.get(family, SIMULATED_RISK_FAMILY_INFO["other"])["label"]
            parts.append(f"{label} ({count})")
        return ", ".join(parts) if parts else "n/a"

    origin_rows: list[dict[str, Any]] = []
    for (supplier_id, item_id), stats in origin_stats.items():
        first_day = int(stats["first_day"]) if math.isfinite(float(stats["first_day"])) else 0
        last_day = int(stats["last_day"]) if math.isfinite(float(stats["last_day"])) else first_day
        production_shortfall = float(stats["production_shortfall_qty"])
        backlog_qty_days = float(stats["customer_backlog_qty_days"])
        cost_roots = int(stats["cost_roots"])
        effective_roots = int(stats["effective_roots"])
        top_root = stats.get("top_root") if isinstance(stats.get("top_root"), dict) else {}
        primary_trigger = str(top_root.get("trigger") or top_root.get("risk_family") or "n/a")
        dominant_stage = dominant_stage_key(stats["stages"])
        # Business ranking: customer impact dominates production, then cost,
        # then repeated local absorption. This is a decision score, not a
        # probability.
        decision_score = (
            backlog_qty_days * 100.0
            + production_shortfall
            + cost_roots * 250_000.0
            + effective_roots * 100_000.0
            + int(stats["local_absorbed_roots"]) * 1_000.0
        )
        origin_rows.append(
            {
                "supplier_id": supplier_id,
                "item_id": item_id,
                "supplier_label": label_node(supplier_id),
                "item_label": label_item(item_id),
                "period": f"J{first_day} -> J{last_day}",
                "dominant_stage_key": dominant_stage,
                "dominant_stage": str(stage_info.get(dominant_stage, stage_info["other"])["label"]),
                "impact_color": str(stage_info.get(dominant_stage, stage_info["other"])["color"]),
                "primary_trigger": primary_trigger,
                "families": origin_family_text(stats["families"]),
                "root_count": int(stats["roots"]),
                "effective_root_count": effective_roots,
                "signal_count": int(stats["signals"]),
                "affected_factory_nodes": sorted(stats["affected_factory_nodes"]),
                "affected_customer_nodes": sorted(stats["affected_customer_nodes"]),
                "impacted_output_items": sorted(stats["impacted_output_items"]),
                "production_shortfall_qty": round(production_shortfall, 6),
                "production_delay_count": int(stats["production_delay_count"]),
                "customer_backlog_max_qty": round(float(stats["customer_backlog_max_qty"]), 6),
                "customer_backlog_qty_days": round(backlog_qty_days, 6),
                "cost_root_count": cost_roots,
                "local_absorbed_root_count": int(stats["local_absorbed_roots"]),
                "decision_score": round(decision_score, 6),
                "table_row": {
                    "Origine": f"{label_node(supplier_id)} / {label_item(item_id)}",
                    "Impact dominant": dominant_stage_label(stats["stages"]),
                    "Declencheur principal": primary_trigger,
                    "Familles": origin_family_text(stats["families"]),
                    "Periode": f"J{first_day} -> J{last_day}",
                    "Causes supply actives": f"{effective_roots}/{int(stats['roots'])} avec impact supply",
                    "Production reportee": f"{int(stats['production_delay_count'])} report(s), {fmt_qty(production_shortfall, 0)}",
                    "Backlog": f"pic {fmt_qty(float(stats['customer_backlog_max_qty']), 0)}",
                    "Lecture": (
                        "Origine prioritaire"
                        if effective_roots
                        else "Effets locaux surtout absorbes"
                    ),
                },
            }
        )
    origin_rows.sort(key=lambda row: (-float(row.get("decision_score") or 0.0), str(row.get("supplier_id") or ""), str(row.get("item_id") or "")))
    top_origin_rows = [dict(row["table_row"]) for row in origin_rows[:10]]
    top_origin = origin_rows[0] if origin_rows else None
    top_origin_text = (
        f"{top_origin['supplier_label']} / {top_origin['item_label']} - {top_origin['dominant_stage']}"
        if top_origin
        else "n/a"
    )

    max_origin_score = max((float(row.get("decision_score") or 0.0) for row in origin_rows), default=0.0)

    def map_score(score: float) -> float:
        if max_origin_score <= 1e-9:
            return 0.0
        return max(0.0, min(1.0, score / max_origin_score))

    def register_node_impact(
        impacts: dict[str, dict[str, Any]],
        node_id: str,
        *,
        role: str,
        stage: str,
        score: float,
        origin: dict[str, Any],
    ) -> None:
        node_id = str(node_id or "")
        if not node_id:
            return
        normalized_score = map_score(score)
        info = stage_info.get(stage, stage_info["other"])
        candidate = {
            "node_id": node_id,
            "role": role,
            "stage": stage,
            "stage_label": info["label"],
            "color": info["color"],
            "score": round(normalized_score, 6),
            "decision_score": round(score, 6),
            "supplier_id": origin.get("supplier_id", ""),
            "item_id": origin.get("item_id", ""),
            "supplier_label": origin.get("supplier_label", ""),
            "item_label": origin.get("item_label", ""),
            "period": origin.get("period", "n/a"),
            "primary_trigger": origin.get("primary_trigger", "n/a"),
            "effective_root_count": int(origin.get("effective_root_count") or 0),
            "root_count": int(origin.get("root_count") or 0),
            "production_delay_count": int(origin.get("production_delay_count") or 0),
            "production_shortfall_qty": float(origin.get("production_shortfall_qty") or 0.0),
            "customer_backlog_max_qty": float(origin.get("customer_backlog_max_qty") or 0.0),
            "customer_backlog_qty_days": float(origin.get("customer_backlog_qty_days") or 0.0),
        }
        previous = impacts.get(node_id)
        if previous is None or (
            int(info["rank"]),
            normalized_score,
            float(candidate["decision_score"]),
        ) > (
            int(stage_info.get(str(previous.get("stage") or "other"), stage_info["other"])["rank"]),
            float(previous.get("score") or 0.0),
            float(previous.get("decision_score") or 0.0),
        ):
            impacts[node_id] = candidate

    node_impacts: dict[str, dict[str, Any]] = {}
    for origin in origin_rows:
        score = float(origin.get("decision_score") or 0.0)
        stage = str(origin.get("dominant_stage_key") or "other")
        register_node_impact(
            node_impacts,
            str(origin.get("supplier_id") or ""),
            role="origin_supplier",
            stage=stage,
            score=score,
            origin=origin,
        )
        affected_stage = "service_client" if stage == "service_client" else "production"
        if stage in {"service_client", "production"}:
            for node_id in origin.get("affected_factory_nodes") or []:
                register_node_impact(
                    node_impacts,
                    str(node_id),
                    role="affected_factory",
                    stage=affected_stage,
                    score=score * 0.86,
                    origin=origin,
                )
        if stage == "service_client":
            for node_id in origin.get("affected_customer_nodes") or []:
                register_node_impact(
                    node_impacts,
                    str(node_id),
                    role="affected_customer",
                    stage="service_client",
                    score=score * 0.92,
                    origin=origin,
                )

    raw_edge_ids = {
        str(edge.get("id") or "")
        for edge in raw.get("edges", []) or []
        if isinstance(edge, dict) and str(edge.get("id") or "")
    }
    edge_stats: dict[str, dict[str, Any]] = defaultdict(lambda: {
        "rows": 0,
        "delay_rows": 0,
        "days": set(),
        "event_ids": set(),
        "families": defaultdict(int),
        "supplier_ids": set(),
        "dst_node_ids": set(),
        "item_ids": set(),
        "max_extra_days": 0.0,
        "max_multiplier": 1.0,
        "max_score": 0.0,
    })

    def applied_row_families(row: dict[str, str]) -> set[str]:
        event_ids = [event_id.strip() for event_id in str(row.get("event_ids") or "").split(",") if event_id.strip()]
        return {
            supplier_risk_family_for_event(event_by_id.get(event_id, {"event_id": event_id}))
            for event_id in event_ids
        } or {"other"}

    for row in applied_rows:
        edge_id = str(row.get("edge_id") or "").strip()
        if not edge_id or edge_id not in raw_edge_ids:
            continue
        day_value = to_float(row.get("day"))
        day = int(day_value or 0) if day_value is not None and not math.isnan(day_value) else 0
        extra_days = max(
            0.0,
            to_float(row.get("lead_time_extra_days")) or 0.0,
            to_float(row.get("quality_delay_days")) or 0.0,
        )
        multiplier = max(1.0, to_float(row.get("lead_time_multiplier")) or 1.0)
        families = applied_row_families(row)
        delay_score = max(extra_days / 14.0, multiplier - 1.0, 0.10 if "lead" in families else 0.0)
        if delay_score <= 1e-9:
            continue
        stats = edge_stats[edge_id]
        stats["rows"] += 1
        stats["delay_rows"] += 1
        stats["days"].add(day)
        stats["event_ids"].update(event_id.strip() for event_id in str(row.get("event_ids") or "").split(",") if event_id.strip())
        stats["supplier_ids"].add(str(row.get("supplier_id") or ""))
        stats["dst_node_ids"].add(str(row.get("dst_node_id") or ""))
        stats["item_ids"].add(str(row.get("item_id") or ""))
        stats["max_extra_days"] = max(float(stats["max_extra_days"]), extra_days)
        stats["max_multiplier"] = max(float(stats["max_multiplier"]), multiplier)
        stats["max_score"] = max(float(stats["max_score"]), min(1.0, delay_score))
        for family in families:
            stats["families"][family] += 1

    edge_impacts: dict[str, dict[str, Any]] = {}
    for edge_id, stats in edge_stats.items():
        days = sorted(int(day) for day in stats["days"])
        if not days:
            continue
        edge_impacts[edge_id] = {
            "edge_id": edge_id,
            "display_label": edge_display_label(edge_id),
            "from_node_id": str((edge_by_id.get(edge_id) or {}).get("from") or ""),
            "to_node_id": str((edge_by_id.get(edge_id) or {}).get("to") or ""),
            "status": "delay_impacted",
            "status_label": "Delai transport impacte",
            "color": "#dc2626" if float(stats["max_extra_days"]) >= 7 or float(stats["max_multiplier"]) >= 1.2 else "#f97316",
            "score": round(float(stats["max_score"]), 6),
            "delay_row_count": int(stats["delay_rows"]),
            "active_day_count": len(days),
            "period": f"J{days[0]} -> J{days[-1]}",
            "max_extra_days": round(float(stats["max_extra_days"]), 6),
            "max_multiplier": round(float(stats["max_multiplier"]), 6),
            "event_count": len(stats["event_ids"]),
            "event_examples": sorted(stats["event_ids"])[:5],
            "supplier_ids": sorted(value for value in stats["supplier_ids"] if value),
            "dst_node_ids": sorted(value for value in stats["dst_node_ids"] if value),
            "item_ids": sorted(value for value in stats["item_ids"] if value),
            "family_counts": dict(sorted(stats["families"].items())),
        }

    def card_html(title: str, value: str, text: str, color: str) -> str:
        return (
            f"<div class=\"riskScenarioCard\" style=\"border-left-color:{html.escape(color)}\">"
            f"<div class=\"riskScenarioCardTitle\">{html.escape(title)}</div>"
            f"<div class=\"riskScenarioCardText\"><strong>{html.escape(value)}</strong><br>{html.escape(text)}</div>"
            "</div>"
        )

    cards_html = "".join(
        [
            card_html(
                "Disponibilite produit",
                service_status,
                f"Disponibilite {fmt_pct(fill_rate * 100.0)} ; backlog final {fmt_qty(ending_backlog, 0)}. Backlog temporaire max: {fmt_qty(max_backlog, 0)} sur {len(backlog_days)} jours.",
                "#16a34a" if service_status.endswith("absorbe") else "#dc2626",
            ),
            card_html(
                "Production",
                production_status,
                f"{len(input_delay_rows)} lignes reportees par manque d'intrants ; {fmt_qty(input_shortfall_total, 0)} de volume lotifie associe. Production realisee: {fmt_qty(actual_produced, 0)}.",
                "#d97706" if input_delay_rows else "#16a34a",
            ),
            card_html(
                "Approvisionnement",
                supplier_status,
                f"{len(applied_ids)} aleas ont eu un effet local entre {applied_period}. Familles principales: {family_text}.",
                "#0f766e" if supplier_stats else "#64748b",
            ),
            card_html(
                "Couts et pertes",
                "Effet economique a surveiller",
                f"Cout total {fmt_qty(total_cost, 0)} ; appro fournisseur {fmt_qty(total_external_cost, 0)} ; pertes utiles fournisseur {fmt_qty(total_unreliable_loss, 0)}.",
                "#475569",
            ),
            card_html(
                "Origine principale",
                top_origin_text,
                "Origine priorisee par impact aval observe: service, production, cout, puis absorption locale.",
                "#dc2626" if top_origin and top_origin.get("effective_root_count") else "#64748b",
            ),
        ]
    )

    diagnosis_lines: list[str] = []
    if fill_rate >= 0.999 and ending_backlog <= 1e-9:
        diagnosis_lines.append("Le risque est absorbe cote disponibilite produit sur l'horizon: le bon indicateur n'est pas seulement la disponibilite finale, mais le taux de replanification, le stock consomme et le cout d'appro fournisseur.")
    else:
        diagnosis_lines.append("Le risque atteint le client: il faut lire les pics de backlog et les receptions aval associees.")
    if input_delay_rows and blocker_rows:
        top = blocker_rows[0]
        diagnosis_lines.append(
            f"Le premier axe d'analyse production est {top['Intrant bloquant']} sur {top['Site']}: c'est l'intrant le plus souvent bloquant dans les reports."
        )
    if total_unreliable_loss > 1e-9:
        diagnosis_lines.append("Une partie de la quantite expediee est perdue ou non utile: les courbes de fiabilite/qualite fournisseur doivent etre lues avec les receptions reelles.")
    if supplier_stats:
        first_supplier = top_supplier_rows(1)[0]
        diagnosis_lines.append(
            f"Le fournisseur a regarder en premier est {first_supplier['Fournisseur']} ({first_supplier['Effet dominant']}, {first_supplier['Periode']})."
        )
    if cascade_rows:
        diagnosis_lines.append(
            f"Cascades state-dependent: {cascade_summary_text} Un alea peut donc etre applique localement sans devenir une rupture aval."
        )
    if top_origin:
        diagnosis_lines.append(
            f"Origine dominante des problemes observes: {top_origin_text}. Ce classement agrege les signaux par couple fournisseur/article pour eviter de confondre plusieurs seuils simultanes avec plusieurs causes."
        )
    if top_backlog:
        diagnosis_lines.append(f"Le backlog temporaire principal est {top_backlog_text}; il est utile meme si le backlog final revient a zero.")

    recommendations: list[str] = []
    if blocker_rows:
        recommendations.append("Tester un stock de protection ou une avance de commande sur les intrants bloquants avant d'augmenter la capacite usine.")
    if supplier_stats:
        recommendations.append("Pour les fournisseurs les plus touches, comparer trois mitigations: stock minimum, second source, et expedition acceleree.")
    if total_unreliable_loss > 1e-9:
        recommendations.append("Ajouter un scenario qualite/release explicite pour distinguer perte physique, quarantaine et retard de liberation.")
    if fill_rate >= 0.999 and ending_backlog <= 1e-9:
        recommendations.append("Garder la disponibilite produit comme indicateur de validation, mais piloter la robustesse par taux de replanification, couverture stock et cout d'appro fournisseur.")
    recommendations.append("Prochaine etape scientifique: comparer ce run a un nominal et a deux scenarios de mitigation, avec les memes KPI.")

    horizon_days = int(
        to_float(summary.get("timeline_days") or summary.get("sim_days") or summary.get("total_simulated_timeline_days"))
        or 0
    )
    max_day = horizon_days - 1 if horizon_days > 0 else max(
        [0]
        + [int(to_float(row.get("day")) or 0) for row in applied_rows if str(row.get("day") or "").strip()]
        + [int(to_float(row.get("day")) or 0) for row in plan_rows if str(row.get("day") or "").strip()]
        + [int(to_float(row.get("day")) or 0) for row in demand_rows if str(row.get("day") or "").strip()]
    )

    def valid_day(day: int) -> bool:
        return 0 <= day <= max_day

    def all_days_points(values: dict[int, float]) -> list[tuple[int, float]]:
        return [(day, float(values.get(day, 0.0))) for day in range(max_day + 1)]

    def rolling_points(values: dict[int, float], window: int = 28) -> list[tuple[int, float]]:
        running = 0.0
        out: list[tuple[int, float]] = []
        for day in range(max_day + 1):
            running += float(values.get(day, 0.0))
            expired_day = day - window
            if expired_day >= 0:
                running -= float(values.get(expired_day, 0.0))
            out.append((day, max(0.0, running)))
        return out

    risk_daily_by_family: dict[str, dict[int, float]] = defaultdict(lambda: defaultdict(float))
    supplier_day_sets: dict[int, set[str]] = defaultdict(set)
    item_day_sets: dict[int, set[str]] = defaultdict(set)
    edge_day_sets: dict[int, set[str]] = defaultdict(set)
    applied_row_count_by_day: dict[int, float] = defaultdict(float)
    for row in applied_rows:
        day = int(to_float(row.get("day")) or 0)
        if not valid_day(day):
            continue
        supplier_id = str(row.get("supplier_id") or "")
        item_id = str(row.get("item_id") or "")
        edge_id = str(row.get("edge_id") or "")
        row_event_ids = [event_id.strip() for event_id in str(row.get("event_ids") or "").split(",") if event_id.strip()]
        row_families = {
            supplier_risk_family_for_event(event_by_id.get(event_id, {"event_id": event_id}))
            for event_id in row_event_ids
        } or {"other"}
        applied_row_count_by_day[day] += 1.0
        if supplier_id:
            supplier_day_sets[day].add(supplier_id)
        if item_id:
            item_day_sets[day].add(item_id)
        if edge_id:
            edge_day_sets[day].add(edge_id)
        for family in row_families:
            severity = supplier_risk_family_severity(row, family)
            risk_daily_by_family[family][day] += max(0.05, severity)

    figures: dict[str, Any] = {}
    family_totals = {
        family: sum(day_values.values())
        for family, day_values in risk_daily_by_family.items()
    }
    top_families = [
        family
        for family, _total in sorted(family_totals.items(), key=lambda item: (-float(item[1]), item[0]))[:6]
    ]
    if top_families:
        series_map = {
            SIMULATED_RISK_FAMILY_INFO.get(family, SIMULATED_RISK_FAMILY_INFO["other"])["label"]: rolling_points(risk_daily_by_family[family], 28)
            for family in top_families
        }
        series_styles = {
            SIMULATED_RISK_FAMILY_INFO.get(family, SIMULATED_RISK_FAMILY_INFO["other"])["label"]: {
                "color": SIMULATED_RISK_FAMILY_INFO.get(family, SIMULATED_RISK_FAMILY_INFO["other"])["color"],
                "width": 2.4,
            }
            for family in top_families
        }
        figure = build_line_chart_figure(
            series_map,
            title="Risques appliques - intensite glissante 28 jours",
            y_label="Score cumule 28 j",
            note="Montre quand les aleas ont vraiment modifie stock, capacite, delai, qualite ou approvisionnement.",
            series_styles=series_styles,
        )
        if figure is not None:
            figures["risk_intensity"] = figure

    breadth_figure = build_line_chart_figure(
        {
            "Fournisseurs touches": all_days_points({day: float(len(values)) for day, values in supplier_day_sets.items()}),
            "Articles touches": all_days_points({day: float(len(values)) for day, values in item_day_sets.items()}),
            "Flux touches": all_days_points({day: float(len(values)) for day, values in edge_day_sets.items()}),
            "Lignes d'effet": all_days_points(applied_row_count_by_day),
        },
        title="Largeur d'impact fournisseur dans le temps",
        y_label="Nombre / jour",
        note="Compte les fournisseurs, articles et flux qui subissent un effet local dans le run.",
        series_styles={
            "Fournisseurs touches": {"color": "#0f766e", "width": 2.4},
            "Articles touches": {"color": "#2563eb", "width": 2.2},
            "Flux touches": {"color": "#7c3aed", "width": 2.2},
            "Lignes d'effet": {"color": "#64748b", "width": 1.8, "dash": "dot"},
        },
    )
    if breadth_figure is not None:
        figures["risk_breadth"] = breadth_figure

    production_starts_by_day: dict[int, float] = defaultdict(float)
    production_delay_input_by_day: dict[int, float] = defaultdict(float)
    production_delay_lot_by_day: dict[int, float] = defaultdict(float)
    for row in plan_rows:
        day = int(to_float(row.get("day")) or 0)
        if not valid_day(day):
            continue
        event_type = str(row.get("event_type") or "")
        reason = str(row.get("reason") or "")
        if event_type == "start_campaign":
            production_starts_by_day[day] += 1.0
        if event_type == "delay_input_shortage" or reason == "input_shortage":
            production_delay_input_by_day[day] += 1.0
        if event_type == "delay_weekly_lot_limit" or reason == "weekly_lot_limit":
            production_delay_lot_by_day[day] += 1.0
    production_figure = build_line_chart_figure(
        {
            "Lots/campagnes lances": all_days_points(production_starts_by_day),
            "Reports manque intrants": all_days_points(production_delay_input_by_day),
            "Reports limite lots": all_days_points(production_delay_lot_by_day),
        },
        title="Production - lancements et reports",
        y_label="Evenements / jour",
        note="Lecture metier: les reports indiquent quand la production attend des intrants ou une fenetre de lotification.",
        event_like=True,
        series_styles={
            "Lots/campagnes lances": {"color": "#0f766e", "width": 2.2},
            "Reports manque intrants": {"color": "#dc2626", "width": 2.4},
            "Reports limite lots": {"color": "#d97706", "width": 2.2},
        },
    )
    if production_figure is not None:
        figures["production_events"] = production_figure

    demand_by_day: dict[int, float] = defaultdict(float)
    served_by_day: dict[int, float] = defaultdict(float)
    backlog_by_day: dict[int, float] = defaultdict(float)
    for row in demand_rows:
        day = int(to_float(row.get("day")) or 0)
        if not valid_day(day):
            continue
        demand_by_day[day] += max(0.0, to_float(row.get("demand_qty")) or 0.0)
        served_by_day[day] += max(0.0, to_float(row.get("served_qty")) or 0.0)
        backlog_by_day[day] += max(0.0, to_float(row.get("backlog_end_qty")) or 0.0)
    service_figure = build_line_chart_figure(
        {
            "Demande client": all_days_points(demand_by_day),
            "Servi client": all_days_points(served_by_day),
            "Backlog fin jour": all_days_points(backlog_by_day),
        },
        title="Disponibilite produit - demande, servi, backlog",
        y_label="Quantite / jour",
        note="Permet de voir si les risques restent absorbes par les stocks ou atteignent le client.",
        series_styles={
            "Demande client": {"color": "#dc2626", "width": 2.0},
            "Servi client": {"color": "#0f766e", "width": 2.4},
            "Backlog fin jour": {"color": "#7c3aed", "width": 2.2, "dash": "dash"},
        },
    )
    if service_figure is not None:
        figures["customer_service"] = service_figure

    def bullet_list(items: list[str]) -> str:
        return "<ul class=\"riskDiagnosticList\">" + "".join(f"<li>{html.escape(item)}</li>" for item in items) + "</ul>"

    def table_html(headers: list[str], rows: list[dict[str, str]], empty_text: str) -> str:
        if not rows:
            body = f"<tr><td colspan=\"{len(headers)}\">{html.escape(empty_text)}</td></tr>"
        else:
            body = "".join(
                "<tr>" + "".join(f"<td>{html.escape(str(row.get(header, '')))}</td>" for header in headers) + "</tr>"
                for row in rows
            )
        return (
            "<div class=\"kpiFormulaTableWrap\"><table class=\"kpiFormulaTable\">"
            "<thead><tr>"
            + "".join(f"<th>{html.escape(header)}</th>" for header in headers)
            + "</tr></thead><tbody>"
            + body
            + "</tbody></table></div>"
        )

    def short_text(value: Any, limit: int = 54) -> str:
        text = re.sub(r"\s+", " ", str(value or "n/a")).strip()
        if len(text) <= limit:
            return text
        return text[: max(0, limit - 1)].rstrip() + "..."

    def cascade_diagram_html(rows: list[dict[str, Any]], *, limit: int = 6) -> str:
        selected = rows[:limit]
        if not selected:
            return "<div class=\"riskScenarioMuted\">Aucune cascade state-dependent a afficher.</div>"
        width = 1120
        row_height = 96
        top = 34
        box_w = 238
        box_h = 66
        xs = [20, 302, 584, 866]
        height = top + row_height * len(selected) + 16

        def text_block(x: int, y: int, title: str, lines: list[str]) -> str:
            out = [
                f"<text class=\"cascadeTitle\" x=\"{x + 12}\" y=\"{y + 20}\">{html.escape(short_text(title, 34))}</text>"
            ]
            for idx, line in enumerate(lines[:3]):
                klass = "cascadeText" if idx == 0 else "cascadeMuted"
                out.append(
                    f"<text class=\"{klass}\" x=\"{x + 12}\" y=\"{y + 38 + idx * 14}\">{html.escape(short_text(line, 42))}</text>"
                )
            return "".join(out)

        rows_svg: list[str] = [
            "<div class=\"riskCascadeDiagram\">",
            f"<svg viewBox=\"0 0 {width} {height}\" role=\"img\" aria-label=\"Diagramme cascades state-dependent\">",
            "<defs><marker id=\"riskCascadeArrow\" markerWidth=\"8\" markerHeight=\"8\" refX=\"7\" refY=\"4\" orient=\"auto\"><path d=\"M0,0 L8,4 L0,8 Z\" fill=\"#64748b\"/></marker></defs>",
            "<text class=\"cascadeMuted\" x=\"20\" y=\"18\">Cause supply</text>",
            "<text class=\"cascadeMuted\" x=\"302\" y=\"18\">Effet local</text>",
            "<text class=\"cascadeMuted\" x=\"584\" y=\"18\">Propagation aval</text>",
            "<text class=\"cascadeMuted\" x=\"866\" y=\"18\">Impact / absorption</text>",
        ]
        for idx, row in enumerate(selected):
            y = top + idx * row_height
            stage = str(row.get("stage") or "other")
            info = stage_info.get(stage, stage_info["other"])
            family = str(row.get("risk_family") or "")
            family_label = SIMULATED_RISK_FAMILY_INFO.get(family, SIMULATED_RISK_FAMILY_INFO["other"])["label"]
            supplier_id = str(row.get("supplier_id") or "")
            item_id = str(row.get("item_id") or "")
            factories = row.get("affected_factory_nodes") or []
            customers = row.get("affected_customer_nodes") or []
            outputs = row.get("impacted_output_items") or []
            route_lines = [
                "Sites: " + (", ".join(label_node(str(node)) for node in factories[:2]) if factories else "pas de report usine"),
                "Produits: " + (", ".join(label_item(str(item)) for item in outputs[:2]) if outputs else label_item(item_id)),
                "Clients: " + (", ".join(label_node(str(node)) for node in customers[:2]) if customers else "pas de backlog client"),
            ]
            rows_svg.append(
                "".join(
                    [
                        f"<rect class=\"cascadeBox trigger\" x=\"{xs[0]}\" y=\"{y}\" width=\"{box_w}\" height=\"{box_h}\" rx=\"7\"/>",
                        text_block(
                            xs[0],
                            y,
                            f"J{row.get('start_day', 'n/a')} - {family_label}",
                            [
                                f"{label_node(supplier_id)}",
                                str(row.get("root_cause_label") or label_item(item_id)),
                                f"Signal: {row.get('trigger') or 'n/a'}",
                            ],
                        ),
                        f"<line class=\"cascadeArrow\" x1=\"{xs[0] + box_w + 10}\" y1=\"{y + box_h / 2:.1f}\" x2=\"{xs[1] - 12}\" y2=\"{y + box_h / 2:.1f}\"/>",
                        f"<rect class=\"cascadeBox local\" x=\"{xs[1]}\" y=\"{y}\" width=\"{box_w}\" height=\"{box_h}\" rx=\"7\"/>",
                        text_block(
                            xs[1],
                            y,
                            "Effet local",
                            [
                                str(row.get("local_effect") or "n/a"),
                                f"Source: {row.get('source') or 'n/a'}",
                                f"Periode: {row.get('period') or 'n/a'}",
                            ],
                        ),
                        f"<line class=\"cascadeArrow\" x1=\"{xs[1] + box_w + 10}\" y1=\"{y + box_h / 2:.1f}\" x2=\"{xs[2] - 12}\" y2=\"{y + box_h / 2:.1f}\"/>",
                        f"<rect class=\"cascadeBox route\" x=\"{xs[2]}\" y=\"{y}\" width=\"{box_w}\" height=\"{box_h}\" rx=\"7\"/>",
                        text_block(xs[2], y, "Propagation aval", route_lines),
                        f"<line class=\"cascadeArrow\" x1=\"{xs[2] + box_w + 10}\" y1=\"{y + box_h / 2:.1f}\" x2=\"{xs[3] - 12}\" y2=\"{y + box_h / 2:.1f}\"/>",
                        f"<rect class=\"cascadeBox effect\" style=\"stroke:{html.escape(str(info['color']))}\" x=\"{xs[3]}\" y=\"{y}\" width=\"{box_w}\" height=\"{box_h}\" rx=\"7\"/>",
                        text_block(
                            xs[3],
                            y,
                            str(row.get("absorption_label") or row.get("stage_label") or info["label"]),
                            [
                                str(row.get("reading") or "n/a"),
                                f"Replanification: {row.get('production_delay_count') or 0} lignes",
                                f"Backlog max: {fmt_qty(float(row.get('customer_backlog_max_qty') or 0.0), 0)}",
                            ],
                        ),
                    ]
                )
            )
        rows_svg.extend(["</svg>", "</div>"])
        return "".join(rows_svg)

    detail_rows = [
        {"Indicateur": "Aleas avec effet local", "Valeur": str(len(applied_ids))},
        {"Indicateur": "Aleas configures", "Valeur": str(len(configured_ids))},
        {"Indicateur": "Noeuds fournisseurs touches", "Valeur": str(len(supplier_stats))},
        {"Indicateur": "Jours avec effet fournisseur", "Valeur": str(len(applied_days))},
        {"Indicateur": "Lignes d'application fournisseur", "Valeur": str(len(applied_rows))},
        {"Indicateur": "Taux replanification par intrants", "Valeur": replanning_rate_text(input_replanning_rate, len(input_delay_rows))},
        {"Indicateur": "Taux replanification tous motifs", "Valeur": replanning_rate_text(total_replanning_rate, len(delay_rows))},
        {"Indicateur": "Plan lotifie total", "Valeur": fmt_qty(planned_after_lot, 0)},
        {"Indicateur": "Manque vs plan lotifie", "Valeur": fmt_qty(lot_shortfall_total, 0)},
        {"Indicateur": "Causes de cascade agregees", "Valeur": str(len(cascade_root_rows))},
        {"Indicateur": "Chemins metier consolides", "Valeur": str(len(cascade_path_groups))},
        {"Indicateur": "Signaux state/scenario analyses", "Valeur": str(len(cascade_rows))},
        {"Indicateur": "Cascades avec impact supply", "Valeur": str(len(effective_cascade_rows))},
        {"Indicateur": "Cascades production", "Valeur": str(cascade_stage_counts.get("production", 0))},
        {"Indicateur": "Cascades disponibilite produit", "Valeur": str(cascade_stage_counts.get("service_client", 0))},
        {"Indicateur": "Effets absorbes localement", "Valeur": str(cascade_stage_counts.get("local_absorbed", 0))},
    ]
    global_metrics = (simulated_risk_metrics.get("global") or {}) if isinstance(simulated_risk_metrics, dict) else {}
    source_counts = global_metrics.get("applied_source_counts") or {}
    if source_counts:
        detail_rows.append(
            {
                "Indicateur": "Origine des aleas appliques",
                "Valeur": ", ".join(f"{key}: {value}" for key, value in sorted(source_counts.items())),
            }
        )

    html_parts = [
        "<div class=\"factoryHtmlPanelContent sensitivityHtmlPanelContent riskGlobalDiagnosticContent\">",
        "<div class=\"orderLedgerTextHeader\">Bilan du scenario risque</div>",
        "<div class=\"orderLedgerStatus\">Question metier: le scenario injecte a-t-il touche le client, la production, les fournisseurs ou surtout les couts et stocks tampon ?</div>",
        f"<div class=\"riskScenarioCards\">{cards_html}</div>",
        f"<div class=\"orderLedgerStatus\">{html.escape(cascade_summary_text)}</div>",
        "<div class=\"riskScenarioSection\">Diagramme des cascades dynamiques fournisseur</div>",
        "<div class=\"riskScenarioMuted\">Lecture: chaque ligne suit une cause supply avec impact depuis son declencheur, son effet local, sa propagation aval, puis son impact ou absorption.</div>",
        cascade_diagram_html(visible_path_group_rows),
        "<div class=\"riskScenarioSection\">Courbes du scenario</div>",
        "<div class=\"riskDiagnosticChartGrid\">",
        "<div id=\"simRiskChartRisk\" class=\"riskDiagnosticChart\"></div>",
        "<div id=\"simRiskChartBreadth\" class=\"riskDiagnosticChart\"></div>",
        "<div id=\"simRiskChartProduction\" class=\"riskDiagnosticChart\"></div>",
        "<div id=\"simRiskChartService\" class=\"riskDiagnosticChart\"></div>",
        "</div>",
        "<div class=\"riskScenarioSection\">Lecture metier</div>",
        bullet_list(diagnosis_lines),
        "<div class=\"riskScenarioSection\">Origines principales des problemes</div>",
        table_html(
            ["Origine", "Impact dominant", "Declencheur principal", "Familles", "Periode", "Causes supply actives", "Production reportee", "Backlog", "Lecture"],
            top_origin_rows,
            "Aucune origine dominante exploitable dans ce run.",
        ),
        "<div class=\"riskScenarioSection\">Chemins metier consolides</div>",
        table_html(
            [
                "Chemin metier",
                "Occurrences",
                "Pire periode",
                "Production reportee",
                "Backlog max",
                "Backlog-jours",
                "Cout additionnel",
                "Chemin carte",
                "Action recommandee",
            ],
            path_group_table_rows,
            "Aucun chemin metier consolide exploitable dans ce run.",
        ),
        "<div class=\"riskScenarioSection\">Cascades avec impact supply</div>",
        table_html(
            [
                "Statut",
                "Fournisseur",
                "Article declencheur",
                "Site(s)",
                "PF/PFI touche(s)",
                "Periode",
                "Duree",
                "Effet local",
                "Volume reporte",
                "Backlog max",
                "Aval observe",
                "Source",
            ],
            cascade_table_rows,
            "Aucune cascade state-dependent exploitable dans ce run.",
        ),
        "<div class=\"riskScenarioSection\">A investiguer en premier</div>",
        table_html(
            ["Site", "Produit", "Intrant bloquant", "Jours reportes", "Lots non lances", "Prochaine reception"],
            blocker_rows,
            "Aucun report de production par manque d'intrants dans ce run.",
        ),
        "<div class=\"riskScenarioSection\">Fournisseurs qui pesent vraiment dans ce run</div>",
        table_html(
            ["Fournisseur", "Periode", "Articles touches", "Effet dominant", "Intensite max"],
            top_supplier_rows(),
            "Aucun evenement fournisseur n'a eu d'effet local dans ce run.",
        ),
        "<div class=\"riskScenarioSection\">Articles les plus touches</div>",
        table_html(
            ["Article", "Fournisseurs", "Effet dominant", "Occurrences", "Intensite max"],
            top_item_rows(),
            "Aucun article touche par un evenement fournisseur applique.",
        ),
        "<div class=\"riskScenarioSection\">Actions recommandees</div>",
        bullet_list(recommendations),
        "<details class=\"riskScenarioNativeDetails\">",
        "<summary>Details de comptage</summary>",
        table_html(["Indicateur", "Valeur"], detail_rows, "Aucun detail disponible."),
        "</details>",
        "</div>",
    ]
    return {
        "available": bool(configured_events or applied_rows or delay_rows),
        "html": "".join(html_parts),
        "figures": figures,
        "summary": {
            "applied_event_count": len(applied_ids),
            "configured_event_count": len(configured_ids),
            "supplier_count": len(supplier_stats),
            "applied_day_count": len(applied_days),
            "input_delay_count": len(input_delay_rows),
            "fill_rate": fill_rate,
            "ending_backlog": ending_backlog,
            "effective_cascade_count": len(effective_cascade_rows),
            "cascade_stage_counts": dict(sorted(cascade_stage_counts.items())),
            "cascade_event_stage_counts": dict(sorted(cascade_event_stage_counts.items())),
            "cascade_root_count": len(cascade_root_rows),
            "cascade_path_group_count": len(cascade_path_groups),
            "cascade_signal_count": len(cascade_rows),
            "origin_count": len(origin_rows),
            "node_impact_count": len(node_impacts),
            "edge_delay_impact_count": len(edge_impacts),
            "top_origin": {
                key: value for key, value in (top_origin or {}).items() if key != "table_row"
            },
        },
        "node_impacts": node_impacts,
        "edge_impacts": edge_impacts,
        "origin_impacts": [
            {key: value for key, value in row.items() if key != "table_row"}
            for row in origin_rows
        ],
        "cascade_roots": [
            {key: value for key, value in row.items() if key != "table_row"}
            for row in sorted(
                cascade_root_rows,
                key=lambda row: (-float(row.get("impact_score") or 0.0), str(row.get("event_id") or "")),
            )
        ],
        "cascade_path_groups": [
            {key: value for key, value in row.items() if key != "table_row"}
            for row in cascade_path_groups
        ],
        "events": [
            {key: value for key, value in row.items() if key != "table_row"}
            for row in sorted(
                cascade_rows,
                key=lambda row: (-float(row.get("impact_score") or 0.0), str(row.get("event_id") or "")),
            )
        ],
    }
