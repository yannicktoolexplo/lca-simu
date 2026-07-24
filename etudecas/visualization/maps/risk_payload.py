from __future__ import annotations

from collections import defaultdict
import html
import json
import math
from pathlib import Path
from typing import Any

from etudecas.visualization.maps.map_data_loader import read_csv_rows
from etudecas.visualization.maps.map_render import fmt_pct, fmt_qty, render_data_table


SIMULATED_RISK_FAMILY_INFO = {
    "capacity": {"label": "Capacite", "color": "#d97706"},
    "stock": {"label": "Stock", "color": "#0f766e"},
    "lead": {"label": "Delai", "color": "#7c3aed"},
    "reliability": {"label": "Fiabilite", "color": "#2563eb"},
    "upstream": {"label": "Appro amont", "color": "#be123c"},
    "quality": {"label": "Qualite", "color": "#0891b2"},
    "cost": {"label": "Cout appro fournisseur", "color": "#475569"},
    "availability": {"label": "Disponibilite", "color": "#f59e0b"},
    "other": {"label": "Autre", "color": "#64748b"},
}


RISK_LEGACY_KEYS = (
    "simulated_risk_global_diagnostic",
    "scenario_comparison",
    "supplier_risk_campaign",
    "supplier_risk_hover_images",
    "factory_supplier_risk_hover_images",
    "distribution_center_supplier_risk_hover_images",
    "supplier_risk_metrics",
    "supplier_local_metrics",
    "montecarlo_uncertainty",
)


def to_float(x: Any) -> float | None:
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def supplier_risk_campaign_status(score: float) -> tuple[str, str, str]:
    if score >= 0.06:
        return "sensitive", "Impact fort", "businessAlert"
    if score >= 0.02:
        return "watch", "Impact a surveiller", "businessWarn"
    if score > 1e-9:
        return "robust", "Impact faible", "businessOk"
    return "not_local", "Aucun impact visible", "businessInfo"


def render_supplier_risk_campaign_html(
    supplier_id: str,
    *,
    summary_row: dict[str, str],
    case_rows: list[dict[str, str]],
    metadata: dict[str, Any],
) -> str:
    score = max(
        0.0,
        to_float(summary_row.get("worst_score_decisionnel_modele"))
        or to_float(summary_row.get("worst_impact_score"))
        or 0.0,
    )
    observed_score = max(0.0, to_float(summary_row.get("worst_impact_metier_score")) or 0.0)
    observed_kpi = str(summary_row.get("worst_impact_metier_kpi") or "n/a")
    observed_delta = str(summary_row.get("worst_impact_metier_delta") or "n/a")
    observed_reading = str(
        summary_row.get("worst_impact_metier_lecture")
        or summary_row.get("worst_impact_explanation")
        or "aucune degradation KPI visible"
    )
    cost_reading = str(summary_row.get("worst_cout_interpretation") or "")
    status, status_label, _cls = supplier_risk_campaign_status(score)
    family = str(summary_row.get("worst_risk_family") or "other")
    family_label = str(
        summary_row.get("worst_risk_family_label")
        or SIMULATED_RISK_FAMILY_INFO.get(family, SIMULATED_RISK_FAMILY_INFO["other"])["label"]
    )
    info = SIMULATED_RISK_FAMILY_INFO.get(family, SIMULATED_RISK_FAMILY_INFO["other"])
    horizon = metadata.get("days", "n/a")
    family_count = int(to_float(summary_row.get("tested_family_count")) or len(case_rows))
    worst = max(
        case_rows,
        key=lambda row: (
            to_float(row.get("score_decisionnel_modele"))
            or to_float(row.get("impact_score"))
            or 0.0
        ),
    ) if case_rows else {}

    def pct_value(field: str, digits: int = 1, *, delta: bool = False) -> str:
        value = to_float(worst.get(field))
        if value is None or math.isnan(value):
            return "n/a"
        if delta:
            sign = "+" if value > 0 else ""
            return f"{sign}{value:.{digits}f} pts"
        return fmt_pct(value * 100.0, digits)

    family_rows = []
    for row in sorted(
        case_rows,
        key=lambda r: -(
            to_float(r.get("score_decisionnel_modele"))
            or to_float(r.get("impact_score"))
            or 0.0
        ),
    ):
        row_score = to_float(row.get("score_decisionnel_modele")) or to_float(row.get("impact_score")) or 0.0
        row_observed = to_float(row.get("impact_metier_score")) or 0.0
        family_rows.append(
            [
                row.get("risk_family_label") or row.get("risk_family") or "n/a",
                str(row.get("multiplier") or ""),
                fmt_pct(row_score * 100.0, 1),
                str(row.get("impact_metier_kpi") or "n/a"),
                str(row.get("impact_metier_delta") or "n/a"),
                fmt_pct(row_observed * 100.0, 1),
                fmt_pct((to_float(row.get("fill_rate")) or 0.0) * 100.0, 1),
                fmt_pct((to_float(row.get("product_availability")) or 0.0) * 100.0, 1),
                fmt_pct((to_float(row.get("line_adherence")) or 0.0) * 100.0, 1),
                fmt_qty(to_float(row.get("ending_backlog")) or 0.0, 0),
                fmt_qty(to_float(row.get("production_replanning_delta")) or 0.0, 0),
                fmt_qty(to_float(row.get("line_nervousness_delta")) or 0.0, 0),
                fmt_qty(to_float(row.get("material_delay_days_delta")) or 0.0, 1),
                f"{fmt_pct(to_float(row.get('total_cost_delta_pct')) or 0.0, 1)}",
                str(row.get("cout_interpretation") or ""),
                str(row.get("impact_metier_lecture") or row.get("impact_explanation") or "aucune degradation KPI visible"),
            ]
        )

    cost_warning_html = (
        f"<div class=\"sensitivityRecommendation\">Attention cout: {html.escape(cost_reading)}</div>"
        if cost_reading
        else ""
    )

    return "".join(
        [
            "<div class=\"factoryHtmlPanelContent sensitivityHtmlPanelContent\">",
            f"<div class=\"orderLedgerTextHeader\">{html.escape(supplier_id)} - stress tests fournisseurs</div>",
            "<div class=\"orderLedgerStatus\">Question metier: si l'on degrade ce fournisseur dans un scenario contrefactuel, quelle famille de risque impacte le plus les KPI ? Chaque ligne est un run separe, compare a une reference sans evenement.</div>",
            "<div class=\"orderLedgerStatus\">Lecture separee: l'impact metier observe montre les KPI qui bougent vraiment; le score decisionnel est une synthese ponderee provisoire a calibrer. Ce n'est pas une probabilite terrain.</div>",
            f"<div class=\"sensitivityHero sensitivityStatus-{html.escape(status)}\" style=\"border-left-color:{html.escape(info['color'])}\">",
            "<div class=\"sensitivityHeroLeft\">",
            f"<div class=\"sensitivityPill\">{html.escape(status_label)}</div>",
            f"<div class=\"sensitivityHeroTitle\">{html.escape(supplier_id)} - pire risque teste: {html.escape(family_label)}</div>",
            f"<div class=\"sensitivityHeroText\">Impact metier principal: {html.escape(observed_kpi)} {html.escape(observed_delta)}. Score decisionnel modele: {fmt_pct(score * 100.0, 1)} sur une campagne de {html.escape(str(horizon))} jours.</div>",
            f"<div class=\"sensitivityRecommendation\">Lecture metier: {html.escape(observed_reading)}</div>",
            cost_warning_html,
            "</div>",
            "<div class=\"sensitivityHeroMetrics\">",
            f"<div class=\"sensitivityMetricCard\"><div class=\"sensitivityMetricLabel\">Familles testees</div><div class=\"sensitivityMetricValue\">{family_count}</div><div class=\"sensitivityMetricHint\">une famille par run</div></div>",
            f"<div class=\"sensitivityMetricCard\"><div class=\"sensitivityMetricLabel\">Impact metier</div><div class=\"sensitivityMetricValue\">{html.escape(observed_kpi)}</div><div class=\"sensitivityMetricHint\">{html.escape(observed_delta)}</div></div>",
            f"<div class=\"sensitivityMetricCard\"><div class=\"sensitivityMetricLabel\">Intensite metier</div><div class=\"sensitivityMetricValue\">{fmt_pct(observed_score * 100.0, 1)}</div><div class=\"sensitivityMetricHint\">KPI observe normalise</div></div>",
            f"<div class=\"sensitivityMetricCard\"><div class=\"sensitivityMetricLabel\">Score decisionnel</div><div class=\"sensitivityMetricValue\">{fmt_pct(score * 100.0, 1)}</div><div class=\"sensitivityMetricHint\">synthese ponderee provisoire</div></div>",
            f"<div class=\"sensitivityMetricCard\"><div class=\"sensitivityMetricLabel\">Fill rate</div><div class=\"sensitivityMetricValue\">{pct_value('fill_rate')}</div><div class=\"sensitivityMetricHint\">cas le plus dur</div></div>",
            f"<div class=\"sensitivityMetricCard\"><div class=\"sensitivityMetricLabel\">Disponibilite</div><div class=\"sensitivityMetricValue\">{pct_value('product_availability')}</div><div class=\"sensitivityMetricHint\">lignes client servies</div></div>",
            f"<div class=\"sensitivityMetricCard\"><div class=\"sensitivityMetricLabel\">Adherence</div><div class=\"sensitivityMetricValue\">{pct_value('line_adherence')}</div><div class=\"sensitivityMetricHint\">plan vs reel</div></div>",
            f"<div class=\"sensitivityMetricCard\"><div class=\"sensitivityMetricLabel\">Delta cout</div><div class=\"sensitivityMetricValue\">{fmt_pct(to_float(worst.get('total_cost_delta_pct')) or 0.0, 1)}</div><div class=\"sensitivityMetricHint\">vs reference</div></div>",
            "</div>",
            "</div>",
            "<div class=\"orderLedgerTextHeader orderLedgerSubHeader\">Tous les risques testes sur ce fournisseur</div>",
            render_data_table(
                [
                    "Risque teste",
                    "Intensite",
                    "Score decisionnel",
                    "KPI metier principal",
                    "Delta KPI",
                    "Intensite metier",
                    "Fill rate",
                    "Disponibilite",
                    "Adherence",
                    "Backlog fin",
                    "Replanif delta",
                    "Nervosite delta",
                    "Retard MP delta",
                    "Cout delta",
                    "Lecture cout",
                    "Lecture",
                ],
                family_rows,
            ),
            "</div>",
        ]
    )


def build_supplier_risk_campaign_payload(
    summary_json: Path,
    summary_csv: Path,
    cases_csv: Path,
) -> dict[str, Any]:
    summary_rows = read_csv_rows(summary_csv)
    case_rows = read_csv_rows(cases_csv)
    metadata: dict[str, Any] = {}
    if summary_json.exists():
        try:
            payload = json.loads(summary_json.read_text(encoding="utf-8"))
            metadata = payload.get("metadata") or {}
            if not summary_rows:
                summary_rows = [dict(row) for row in (payload.get("summary") or []) if isinstance(row, dict)]
            if not case_rows:
                case_rows = [dict(row) for row in (payload.get("cases") or []) if isinstance(row, dict)]
        except Exception:
            metadata = {}

    case_by_supplier: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in case_rows:
        supplier_id = str(row.get("supplier_id") or "")
        if not supplier_id or supplier_id == "__all__":
            continue
        case_by_supplier[supplier_id].append(row)

    nodes: dict[str, Any] = {}
    for row in summary_rows:
        supplier_id = str(row.get("supplier_id") or "")
        if not supplier_id:
            continue
        score = max(
            0.0,
            to_float(row.get("worst_score_decisionnel_modele"))
            or to_float(row.get("worst_impact_score"))
            or 0.0,
        )
        observed_score = max(0.0, to_float(row.get("worst_impact_metier_score")) or 0.0)
        status, status_label, _business_class = supplier_risk_campaign_status(score)
        family = str(row.get("worst_risk_family") or "other")
        info = SIMULATED_RISK_FAMILY_INFO.get(family, SIMULATED_RISK_FAMILY_INFO["other"])
        family_label = str(row.get("worst_risk_family_label") or info["label"])
        family_cases = case_by_supplier.get(supplier_id, [])
        horizon = metadata.get("days", "n/a")
        nodes[supplier_id] = {
            "source": "supplier_risk_campaign",
            "status": status,
            "status_label": status_label,
            "driver_family": family,
            "driver_label": family_label,
            "driver_color": info["color"],
            "score": round(score, 9),
            "score_decisionnel_pct": round(score * 100.0, 4),
            "impact_metier_pct": round(observed_score * 100.0, 4),
            "impact_metier_kpi": str(row.get("worst_impact_metier_kpi") or "n/a"),
            "impact_metier_delta": str(row.get("worst_impact_metier_delta") or "n/a"),
            "impact_metier_lecture": str(row.get("worst_impact_metier_lecture") or row.get("worst_impact_explanation") or ""),
            "cout_interpretation": str(row.get("worst_cout_interpretation") or ""),
            "impact_pct": round(score * 100.0, 4),
            "tested_family_count": int(to_float(row.get("tested_family_count")) or len(family_cases)),
            "configured_event_count": int(to_float(row.get("tested_family_count")) or len(family_cases)),
            "applied_event_count": int(to_float(row.get("tested_family_count")) or len(family_cases)),
            "period": f"{horizon} jours",
            "event_examples": [str(case.get("risk_family_label") or case.get("risk_family") or "") for case in family_cases[:4]],
            "impact_explanation": str(row.get("worst_impact_metier_lecture") or row.get("worst_impact_explanation") or ""),
            "asset": {
                "html": render_supplier_risk_campaign_html(
                    supplier_id,
                    summary_row=row,
                    case_rows=family_cases,
                    metadata=metadata,
                )
            },
            "summary_lines": [
                {"label": "Lecture", "value": "campagne de stress tests fournisseur"},
                {"label": "Statut", "value": status_label},
                {"label": "Pire famille testee", "value": family_label},
                {"label": "Impact metier principal", "value": str(row.get("worst_impact_metier_kpi") or "n/a")},
                {"label": "Delta metier principal", "value": str(row.get("worst_impact_metier_delta") or "n/a")},
                {"label": "Intensite metier", "value": fmt_pct(observed_score * 100.0, 1)},
                {"label": "Score decisionnel", "value": fmt_pct(score * 100.0, 1)},
                {"label": "Familles testees", "value": str(int(to_float(row.get("tested_family_count")) or len(family_cases)))},
                {"label": "Horizon", "value": f"{horizon} jours"},
                {"label": "Pourquoi", "value": str(row.get("worst_impact_metier_lecture") or row.get("worst_impact_explanation") or "aucune degradation KPI visible")},
            ],
        }

    strongest = max(nodes.values(), key=lambda row: to_float(row.get("score")) or 0.0) if nodes else {}
    return {
        "available": bool(nodes),
        "nodes": nodes,
        "global": {
            "source": "supplier_risk_campaign",
            "supplier_count": len(nodes),
            "case_count": int(to_float(metadata.get("case_count")) or len(case_rows)),
            "stress_case_count": max(0, len(case_rows) - 1),
            "horizon_days": metadata.get("days"),
            "families": metadata.get("families") or [],
            "dominant_family": strongest.get("driver_family") if strongest else "other",
            "dominant_label": strongest.get("driver_label") if strongest else "n/a",
            "max_score_decisionnel_pct": strongest.get("score_decisionnel_pct") if strongest else 0.0,
            "max_impact_metier_pct": strongest.get("impact_metier_pct") if strongest else 0.0,
            "max_impact_pct": strongest.get("score_decisionnel_pct") if strongest else 0.0,
        },
    }


def build_risk_payload_manifest(payload: dict[str, Any]) -> dict[str, Any]:
    """Describe simulated risk, criticality and uncertainty payload sections."""

    scenario = payload.get("scenario_comparison", {}) if isinstance(payload.get("scenario_comparison"), dict) else {}
    diagnostic = (
        payload.get("simulated_risk_global_diagnostic", {})
        if isinstance(payload.get("simulated_risk_global_diagnostic"), dict)
        else {}
    )
    return {
        "domain": "risk",
        "generic_outputs": ["time_series", "events", "diagnostics"],
        "legacy_keys": [key for key in RISK_LEGACY_KEYS if key in payload],
        "counts": {
            "scenario_count": _count_sequence(scenario.get("scenarios")),
            "scenario_figures": _count_mapping(scenario.get("figures")),
            "risk_events": _count_sequence(diagnostic.get("events")),
            "effective_cascades": _count_sequence(diagnostic.get("cascade_roots")),
            "risk_origin_impacts": _count_sequence(diagnostic.get("origin_impacts")),
            "risk_node_impacts": _count_mapping(diagnostic.get("node_impacts")),
            "risk_edge_impacts": _count_mapping(diagnostic.get("edge_impacts")),
            "supplier_risk_panels": _count_mapping(payload.get("supplier_risk_hover_images")),
            "supplier_metrics": _count_mapping(payload.get("supplier_risk_metrics")),
            "supplier_local_metrics": _count_mapping(payload.get("supplier_local_metrics")),
        },
    }


def build_risk_generic_view(payload: dict[str, Any]) -> dict[str, Any]:
    """Project legacy risk sections to the generic map contract."""

    diagnostic = (
        payload.get("simulated_risk_global_diagnostic", {})
        if isinstance(payload.get("simulated_risk_global_diagnostic"), dict)
        else {}
    )
    return {
        "time_series": {
            "scenario_comparison": payload.get("scenario_comparison", {}).get("figures", {})
            if isinstance(payload.get("scenario_comparison"), dict)
            else {},
        },
        "events": {
            "risk_events": diagnostic.get("events", []) or [],
            "effective_cascades": diagnostic.get("cascade_roots", []) or [],
            "risk_origin_impacts": diagnostic.get("origin_impacts", []) or [],
            "risk_node_impacts": list((diagnostic.get("node_impacts") or {}).values())
            if isinstance(diagnostic.get("node_impacts"), dict)
            else [],
            "risk_edge_impacts": list((diagnostic.get("edge_impacts") or {}).values())
            if isinstance(diagnostic.get("edge_impacts"), dict)
            else [],
        },
        "diagnostics": {
            "simulated_risk": diagnostic,
            "scenario_comparison": payload.get("scenario_comparison", {}) or {},
            "supplier_criticality": payload.get("supplier_local_metrics", {}) or {},
            "uncertainty": payload.get("montecarlo_uncertainty", {}) or {},
        },
    }


def _count_mapping(value: Any) -> int:
    return len(value) if isinstance(value, dict) else 0


def _count_sequence(value: Any) -> int:
    return len(value) if isinstance(value, list) else 0
