"""Map payload helpers for Monte Carlo uncertainty trajectories."""

from __future__ import annotations

import csv
import json
import math
import statistics
from pathlib import Path
from typing import Any

from etudecas.visualization.maps.chart_payloads import build_line_chart_figure


DEFAULT_TRAJECTORY_FILENAME = "montecarlo_trajectories.json"
DEFAULT_SAMPLES_FILENAME = "montecarlo_samples.csv"
FACTOR_TUBE_DISPLAY_LIMIT = 4
FACTOR_TUBE_GROUP_QUANTILE = 0.20
FACTOR_TUBE_METRIC_TARGETS = {
    "service_rate": "kpi::fill_rate",
    "backlog": "kpi::ending_backlog",
    "production_delay_active_orders": "kpi::total_produced",
    "production_reports": "kpi::total_produced",
    "supplier_capacity_binding": "kpi::total_supplier_capacity_binding_qty",
    "total_supply_cost_cum": "kpi::total_cost",
}
FACTOR_TUBE_COLORS = [
    ("#0f766e", "rgba(15,118,110,0.18)"),
    ("#d97706", "rgba(217,119,6,0.18)"),
    ("#7c3aed", "rgba(124,58,237,0.16)"),
    ("#2563eb", "rgba(37,99,235,0.16)"),
    ("#be123c", "rgba(190,18,60,0.14)"),
]
INPUT_FACTOR_PREFIXES = (
    "factor::",
    "supplier_stock_node::",
    "supplier_capacity_node::",
    "supplier_lead_node::",
    "supplier_reliability_node::",
    "demand_item::",
    "capacity_node::",
)
SPARSE_FACTOR_TUBE_METRICS = {
    "production_delay_active_orders",
    "production_reports",
}
EVENT_FACTOR_TUBE_METRICS = {
    "supplier_capacity_binding",
}
TEMPORAL_FACTOR_SELECTION_METRICS = SPARSE_FACTOR_TUBE_METRICS | {
    "supplier_capacity_binding",
}


def _load_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _as_float(value: Any) -> float | None:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(numeric):
        return None
    return numeric


def _load_samples(path: Path) -> dict[str, dict[str, str]]:
    if not path.exists():
        return {}
    try:
        with path.open("r", encoding="utf-8", newline="") as handle:
            return {
                str(row.get("run_id") or ""): row
                for row in csv.DictReader(handle)
                if str(row.get("run_id") or "")
                and str(row.get("status") or "ok").strip().lower() in {"", "ok", "success"}
            }
    except Exception:
        return {}


def _metric_title(label: str) -> str:
    return f"{label} - trajectoires Monte Carlo globales"


def _metric_display_label(metric_key: str, metric: dict[str, Any] | None = None) -> str:
    if metric_key == "service_rate":
        return "Disponibilite produit"
    if isinstance(metric, dict) and metric.get("label"):
        return str(metric.get("label"))
    return metric_key


def _factor_label(raw_factor: str) -> str:
    labels = {
        "factor::supplier_reliability_scale": "Fiabilite fournisseurs globale",
        "factor::supplier_stock_scale": "Stocks fournisseurs globaux",
        "factor::supplier_capacity_scale": "Capacites fournisseurs globales",
        "factor::lead_time_scale": "Delais fournisseurs globaux",
        "factor::external_procurement_lead_days_scale": "Delai appro amont global",
        "factor::external_procurement_daily_cap_days_scale": "Capacite appro amont globale",
        "factor::external_procurement_transport_cost_scale": "Couts transport appro amont",
        "factor::external_procurement_cost_multiplier_scale": "Couts appro amont",
        "factor::capacity_scale": "Capacites usines globales",
        "factor::demand_scale": "Demande globale",
        "factor::production_stock_scale": "Stock produits finis global",
        "factor::holding_cost_scale": "Couts de stockage globaux",
        "factor::purchase_cost_floor_scale": "Couts achats plancher",
        "factor::transport_cost_scale": "Couts transport globaux",
    }
    if raw_factor in labels:
        return labels[raw_factor]
    prefix_labels = [
        ("supplier_stock_node::", "Stock fournisseur "),
        ("supplier_capacity_node::", "Capacite fournisseur "),
        ("supplier_lead_node::", "Delai fournisseur "),
        ("supplier_reliability_node::", "Fiabilite fournisseur "),
        ("demand_item::", "Demande article "),
        ("capacity_node::", "Capacite usine "),
    ]
    for prefix, label in prefix_labels:
        if raw_factor.startswith(prefix):
            return f"{label}{raw_factor.removeprefix(prefix)}"
    return raw_factor.replace("factor::", "").replace("_", " ")


def _is_supplier_prediction_factor(raw_factor: str) -> bool:
    supplier_prefixes = (
        "supplier_stock_node::",
        "supplier_capacity_node::",
        "supplier_lead_node::",
        "supplier_reliability_node::",
        "factor::supplier_",
        "factor::lead_time_scale",
        "factor::external_procurement_",
    )
    return raw_factor.startswith(supplier_prefixes)


def _is_montecarlo_input_factor(raw_factor: str) -> bool:
    return raw_factor.startswith(INPUT_FACTOR_PREFIXES)


def _ranked_factor_candidates(summary: dict[str, Any], target_kpi: str, samples: dict[str, dict[str, str]]) -> list[str]:
    rankings = summary.get("driver_rankings") if isinstance(summary.get("driver_rankings"), dict) else {}
    ranked_rows = rankings.get(target_kpi) if isinstance(rankings.get(target_kpi), list) else []
    sample_columns = set()
    for row in samples.values():
        sample_columns.update(row.keys())
        break

    ranked: list[str] = []
    for row in ranked_rows:
        if not isinstance(row, dict):
            continue
        factor = str(row.get("factor") or "")
        if factor and factor in sample_columns and factor not in ranked:
            ranked.append(factor)
    supplier_first = [factor for factor in ranked if _is_supplier_prediction_factor(factor)]
    fallback = [factor for factor in ranked if factor not in supplier_first]
    candidates = supplier_first + fallback
    if candidates:
        return candidates[:FACTOR_TUBE_DISPLAY_LIMIT]

    discovered = sorted(
        factor
        for factor in sample_columns
        if _is_supplier_prediction_factor(factor)
    )
    return discovered[:FACTOR_TUBE_DISPLAY_LIMIT]


def _median(values: list[float]) -> float:
    return float(statistics.median(values)) if values else 0.0


def _percentile(values: list[float], q: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    if len(ordered) == 1:
        return float(ordered[0])
    pos = max(0.0, min(1.0, q)) * (len(ordered) - 1)
    lower = int(math.floor(pos))
    upper = int(math.ceil(pos))
    if lower == upper:
        return float(ordered[lower])
    weight = pos - lower
    return float(ordered[lower] * (1.0 - weight) + ordered[upper] * weight)


def _mean(values: list[float]) -> float:
    return float(sum(values) / len(values)) if values else 0.0


def _reduce_group(values: list[float], reducer: str) -> float:
    if reducer == "p90":
        return _percentile(values, 0.90)
    if reducer == "mean":
        return _mean(values)
    return _median(values)


def _reducer_label(reducer: str) -> str:
    if reducer == "p90":
        return "percentile 90 de groupe"
    if reducer == "mean":
        return "moyenne de groupe"
    return "mediane de groupe"


def _series_by_run(metric: dict[str, Any], days: list[int]) -> tuple[dict[str, list[float]], list[float] | None]:
    by_run: dict[str, list[float]] = {}
    nominal: list[float] | None = None
    for series in metric.get("series") or []:
        if not isinstance(series, dict):
            continue
        run_id = str(series.get("run_id") or "")
        values = series.get("values") if isinstance(series.get("values"), list) else []
        if not run_id or not values:
            continue
        clean_values = []
        for value in values[: len(days)]:
            numeric = _as_float(value)
            clean_values.append(0.0 if numeric is None else numeric)
        if len(clean_values) < len(days):
            clean_values.extend([0.0] * (len(days) - len(clean_values)))
        by_run[run_id] = clean_values
        if series.get("is_baseline"):
            nominal = clean_values
    return by_run, nominal


def _temporal_effect_factor_candidates(
    *,
    samples: dict[str, dict[str, str]],
    by_run: dict[str, list[float]],
    days: list[int],
    reducer: str,
) -> list[str]:
    sample_columns: set[str] = set()
    for row in samples.values():
        sample_columns.update(row.keys())
        break
    scored: list[tuple[float, float, str]] = []
    for factor in sample_columns:
        if not _is_montecarlo_input_factor(factor):
            continue
        rows: list[tuple[float, list[float]]] = []
        for run_id, sample in samples.items():
            if str(sample.get("is_baseline") or "").strip().lower() in {"1", "true", "yes"}:
                continue
            value = _as_float(sample.get(factor))
            values = by_run.get(run_id)
            if value is None or values is None:
                continue
            rows.append((value, values))
        if len(rows) < 4:
            continue
        rows.sort(key=lambda item: item[0])
        if abs(rows[-1][0] - rows[0][0]) <= 1e-12:
            continue
        group_size = max(1, int(math.ceil(len(rows) * FACTOR_TUBE_GROUP_QUANTILE)))
        group_size = min(group_size, max(1, len(rows) // 2))
        low_group = rows[:group_size]
        high_group = rows[-group_size:]
        max_gap = 0.0
        total_gap = 0.0
        for pos in range(len(days)):
            low_value = _reduce_group([series[pos] for _, series in low_group], reducer)
            high_value = _reduce_group([series[pos] for _, series in high_group], reducer)
            gap = abs(high_value - low_value)
            max_gap = max(max_gap, gap)
            total_gap += gap
        if max_gap > 1e-9:
            scored.append((total_gap, max_gap, factor))
    scored.sort(reverse=True)
    ordered = [factor for _, _, factor in scored]
    supplier_first = [factor for factor in ordered if _is_supplier_prediction_factor(factor)]
    fallback = [factor for factor in ordered if factor not in supplier_first]
    return (supplier_first + fallback)[:FACTOR_TUBE_DISPLAY_LIMIT]


def _factor_tube_bands_for_metric(
    *,
    summary: dict[str, Any],
    samples: dict[str, dict[str, str]],
    days: list[int],
    metric_key: str,
    metric: dict[str, Any],
) -> dict[str, Any] | None:
    target_kpi = FACTOR_TUBE_METRIC_TARGETS.get(metric_key)
    if not target_kpi:
        return None
    by_run, nominal = _series_by_run(metric, days)
    if not by_run:
        return None
    if metric_key in EVENT_FACTOR_TUBE_METRICS:
        reducer = "p90"
    elif metric_key in SPARSE_FACTOR_TUBE_METRICS:
        reducer = "mean"
    else:
        reducer = "median"
    factors = _ranked_factor_candidates(summary, target_kpi, samples)
    if metric_key in TEMPORAL_FACTOR_SELECTION_METRICS:
        temporal_factors = _temporal_effect_factor_candidates(
            samples=samples,
            by_run=by_run,
            days=days,
            reducer=reducer,
        )
        if temporal_factors:
            factors = temporal_factors
    bands: list[dict[str, Any]] = []
    for idx, factor in enumerate(factors):
        rows: list[tuple[str, float, list[float]]] = []
        for run_id, sample in samples.items():
            if str(sample.get("is_baseline") or "").strip().lower() in {"1", "true", "yes"}:
                continue
            value = _as_float(sample.get(factor))
            values = by_run.get(run_id)
            if value is None or values is None:
                continue
            rows.append((run_id, value, values))
        if len(rows) < 4:
            continue
        rows.sort(key=lambda item: item[1])
        if abs(rows[-1][1] - rows[0][1]) <= 1e-12:
            continue
        group_size = max(1, int(math.ceil(len(rows) * FACTOR_TUBE_GROUP_QUANTILE)))
        group_size = min(group_size, max(1, len(rows) // 2))
        low_group = rows[:group_size]
        high_group = rows[-group_size:]
        low_medians: list[float] = []
        high_medians: list[float] = []
        low_band: list[float] = []
        high_band: list[float] = []
        for pos in range(len(days)):
            low_value = _reduce_group([series[pos] for _, _, series in low_group], reducer)
            high_value = _reduce_group([series[pos] for _, _, series in high_group], reducer)
            low_medians.append(low_value)
            high_medians.append(high_value)
            low_band.append(min(low_value, high_value))
            high_band.append(max(low_value, high_value))
        max_gap = max(abs(high - low) for low, high in zip(low_band, high_band))
        if max_gap <= 1e-9:
            continue
        color, fill = FACTOR_TUBE_COLORS[idx % len(FACTOR_TUBE_COLORS)]
        family, node_id = _factor_node_hint(factor)
        bands.append(
            {
                "factor": factor,
                "label": _factor_label(factor),
                "family": family,
                "node_id": node_id,
                "highlight_node_ids": [node_id] if node_id else [],
                "low": low_band,
                "high": high_band,
                "low_group_median": low_medians,
                "high_group_median": high_medians,
                "line_color": color,
                "fillcolor": fill,
                "low_input": _median([value for _, value, _ in low_group]),
                "high_input": _median([value for _, value, _ in high_group]),
                "low_group_count": len(low_group),
                "high_group_count": len(high_group),
                "aggregation": reducer,
                "aggregation_label": _reducer_label(reducer),
            }
        )
    if not bands:
        return None
    return {
        "kind": "factor_tubes",
        "title": f"{_metric_display_label(metric_key, metric)} - zones temporelles par input incertain",
        "y_label": str(metric.get("y_label") or ""),
        "x_label": "Jour",
        "note": (
            "Lecture: chaque zone compare les runs ou l'input est bas avec ceux ou il est haut. "
            "La largeur de la zone montre quand l'incertitude de cet input se propage dans le temps. "
            "Les courbes ont le meme perimetre que les trajectoires Monte Carlo globales; les inputs affiches sont choisis a partir des drivers KPI disponibles. "
            "Pour les KPI rares en pics, les zones utilisent une moyenne ou un percentile haut de groupe afin de ne pas masquer les evenements tardifs. "
            "Les autres aleas continuent de varier: c'est une lecture conditionnelle Monte Carlo, pas une preuve causale isolee."
        ),
        "days": days,
        "bands": bands,
        "nominal": {"label": "Nominal", "values": nominal or []},
    }


def _factor_node_hint(raw_factor: str) -> tuple[str, str]:
    prefixes = [
        ("supplier_stock_node::", "stock"),
        ("supplier_capacity_node::", "capacity"),
        ("supplier_lead_node::", "lead"),
        ("supplier_reliability_node::", "reliability"),
        ("capacity_node::", "factory_capacity"),
    ]
    for prefix, family in prefixes:
        if raw_factor.startswith(prefix):
            return family, raw_factor.removeprefix(prefix)
    if raw_factor == "factor::supplier_stock_scale":
        return "stock", ""
    if raw_factor == "factor::supplier_capacity_scale":
        return "capacity", ""
    if raw_factor in {"factor::lead_time_scale", "factor::external_procurement_lead_days_scale"}:
        return "lead", ""
    if raw_factor == "factor::supplier_reliability_scale":
        return "reliability", ""
    return "global", ""


def _build_factor_tube_figures(
    *,
    summary_json: Path,
    summary: dict[str, Any],
    days: list[int],
    metrics: dict[str, Any],
) -> dict[str, Any]:
    samples = _load_samples(summary_json.with_name(DEFAULT_SAMPLES_FILENAME))
    if not samples:
        return {}
    figures: dict[str, Any] = {}
    for metric_key in FACTOR_TUBE_METRIC_TARGETS:
        metric = metrics.get(metric_key)
        if not isinstance(metric, dict):
            continue
        figure = _factor_tube_bands_for_metric(
            summary=summary,
            samples=samples,
            days=days,
            metric_key=metric_key,
            metric=metric,
        )
        if figure is not None:
            figures[metric_key] = figure
    return figures


def _global_trajectory_note_asset(run_count: Any, day_count: int) -> dict[str, Any]:
    return {
        "html": (
            "<div class=\"factoryHtmlPanelContent sensitivityHtmlPanelContent\">"
            "<div class=\"orderLedgerTextHeader\">Trajectoires Monte Carlo globales</div>"
            "<div class=\"orderLedgerStatus\">"
            "Lecture: ces courbes sont calculees sur l'ensemble du run Monte Carlo. "
            "Elles ne sont pas filtrees par le noeud selectionne. Le noeud selectionne sert a lire l'impact local, "
            "le driver dominant et les correlations; les trajectoires ci-dessous montrent la consequence globale sur la supply."
            "</div>"
            "<div class=\"riskScenarioCards\">"
            "<div class=\"riskScenarioCard\" style=\"border-left-color:#2563eb\">"
            "<div class=\"riskScenarioCardTitle\">Portee</div>"
            "<div class=\"riskScenarioCardText\"><strong>Globale run</strong><br>disponibilite produit, backlog, production, couts et contraintes consolides</div>"
            "</div>"
            "<div class=\"riskScenarioCard\" style=\"border-left-color:#0f766e\">"
            "<div class=\"riskScenarioCardTitle\">Echantillon</div>"
            f"<div class=\"riskScenarioCardText\"><strong>{run_count or 'n/a'} series</strong><br>{day_count} points temporels affiches</div>"
            "</div>"
            "</div>"
            "</div>"
        )
    }


def _min_max_band_from_metric_series(days: list[int], metric: dict[str, Any]) -> dict[str, list[float]] | None:
    """Build a full min-max envelope from stored trajectories.

    This is mainly a compatibility fallback for Monte Carlo trajectory files
    produced before explicit min/max bands were added.
    """

    lows: list[float | None] = [None] * len(days)
    highs: list[float | None] = [None] * len(days)
    for series in metric.get("series") or []:
        values = series.get("values") or []
        if not isinstance(values, list):
            continue
        for pos, value in enumerate(values[: len(days)]):
            try:
                numeric = float(value)
            except (TypeError, ValueError):
                continue
            lows[pos] = numeric if lows[pos] is None else min(lows[pos], numeric)
            highs[pos] = numeric if highs[pos] is None else max(highs[pos], numeric)
    if any(value is None for value in lows) or any(value is None for value in highs):
        return None
    return {
        "low": [float(value) for value in lows if value is not None],
        "high": [float(value) for value in highs if value is not None],
    }


def _scenario_tube_figure(
    *,
    days: list[int],
    metric_key: str,
    metric: dict[str, Any],
) -> dict[str, Any] | None:
    series_map: dict[str, list[tuple[int, float]]] = {}
    series_styles: dict[str, dict[str, Any]] = {}
    for idx, series in enumerate(metric.get("series") or []):
        values = series.get("values") or []
        if not isinstance(values, list) or not values:
            continue
        label = str(series.get("label") or series.get("run_id") or f"run {idx}")
        points = [
            (int(day), float(values[pos]))
            for pos, day in enumerate(days[: len(values)])
        ]
        series_map[label] = points
        is_nominal = bool(series.get("is_baseline"))
        series_styles[label] = {
            "is_nominal": is_nominal,
            "is_current": False,
            "is_max_impact": False,
            "color": "#111827" if is_nominal else "#64748b",
            "width": 2.6 if is_nominal else 0.8,
            "dash": "solid",
            "scenario_id": str(series.get("run_id") or label),
        }

    figure = build_line_chart_figure(
        series_map,
        title=_metric_title(_metric_display_label(metric_key, metric)),
        y_label=str(metric.get("y_label") or ""),
        note=(
            "Lecture: les zones montrent l'incertitude qui evolue dans le temps "
            "(min-max, 5-95%, 10-90%, 25-75%). La zone min-max contient toutes les courbes affichees; les percentiles excluent les extremes. "
            "Les traits noirs fins sont les runs, la mediane est pointillee et le nominal est noir plus epais. "
            "Courbe globale du run: elle n'est pas filtree par le noeud selectionne."
        ),
        series_styles=series_styles,
    )
    if figure is None:
        return None
    figure["scenario_tube"] = True
    figure["tube_label"] = "Enveloppe Monte Carlo"
    figure["trajectory_label"] = "Trajectoires Monte Carlo"
    figure["tube_zero_floor"] = bool(metric.get("zero_floor"))
    figure["tube_upper_percentile"] = float(metric.get("upper_percentile") or 0.90)
    figure["fan_bands"] = True
    figure["preserve_sparse_days"] = True
    figure["fan_band_percentiles"] = [[0.05, 0.95], [0.10, 0.90], [0.25, 0.75]]
    figure["fan_band_colors"] = [
        "rgba(15,118,110,0.035)",
        "rgba(15,118,110,0.07)",
        "rgba(15,118,110,0.12)",
        "rgba(15,118,110,0.20)",
    ]
    bands = metric.get("bands") if isinstance(metric.get("bands"), dict) else {}
    if bands:
        full_band = None
        min_values = bands.get("min") or bands.get("p00") or []
        max_values = bands.get("max") or bands.get("p100") or []
        if min_values and max_values:
            full_band = {"low": min_values, "high": max_values}
        else:
            full_band = _min_max_band_from_metric_series(days, metric)
        band_values = []
        if full_band:
            band_values.append(
                {
                    "label": "min-max (toutes courbes)",
                    "low": full_band["low"],
                    "high": full_band["high"],
                }
            )
        band_values.extend(
            [
                {"label": "5-95%", "low": bands.get("p05") or [], "high": bands.get("p95") or []},
                {"label": "10-90%", "low": bands.get("p10") or [], "high": bands.get("p90") or []},
                {"label": "25-75%", "low": bands.get("p25") or [], "high": bands.get("p75") or []},
            ]
        )
        figure["fan_band_days"] = days
        figure["fan_band_values"] = band_values
        figure["fan_median_values"] = bands.get("p50") or []
        figure["fan_series_total_count"] = metric.get("series_total_count")
        figure["fan_series_display_count"] = metric.get("series_display_count")
    reference_value = metric.get("reference_value")
    if reference_value is not None:
        try:
            figure["reference_line_value"] = float(reference_value)
            reference_label = str(metric.get("reference_label") or "")
            if metric_key == "service_rate":
                reference_label = "disponibilite 100%"
            figure["reference_line_label"] = reference_label
        except (TypeError, ValueError):
            pass
    return figure


def build_montecarlo_trajectory_assets(summary_json: Path) -> dict[str, Any]:
    """Build reusable figure assets for Monte Carlo trajectory tubes.

    The function is deliberately optional: if the trajectories file is missing,
    the existing Monte Carlo summary-only uncertainty view still works.
    """

    summary = _load_json(summary_json)
    trajectories_path = summary_json.with_name(DEFAULT_TRAJECTORY_FILENAME)
    if not trajectories_path.exists():
        return {
            "available": False,
            "path": str(trajectories_path),
            "figures": {},
            "factor_tube_figures": {},
            "overview_bundle": None,
        }

    payload = _load_json(trajectories_path)
    days = [int(day) for day in (payload.get("days") or [])]
    metrics = payload.get("metrics") or {}
    if not days or not isinstance(metrics, dict):
        return {
            "available": False,
            "path": str(trajectories_path),
            "figures": {},
            "factor_tube_figures": {},
            "overview_bundle": None,
        }

    preferred_order = [
        "service_rate",
        "backlog",
        "production_delay_active_orders",
        "production_reports",
        "total_supply_cost_cum",
        "supplier_capacity_binding",
        "production_delay_input_qty",
        "production_delay_capacity_qty",
        "production_delay_active_qty",
        "produced_qty",
    ]
    labels = {
        "service_rate": "Disponibilite produit",
        "backlog": "Backlog",
        "production_delay_active_orders": "Ordres en attente",
        "production_reports": "Lots reportes",
        "production_delay_input_qty": "Volume replanifie par intrants",
        "production_delay_capacity_qty": "Reports capacite",
        "production_delay_active_qty": "Volume en attente",
        "produced_qty": "Production",
        "total_supply_cost_cum": "Cout cumule",
        "supplier_capacity_binding": "Capacite fournisseur",
    }
    figures: dict[str, Any] = {}
    metric_summaries: dict[str, Any] = {}
    bundle: list[dict[str, Any]] = []
    for metric_key in preferred_order:
        metric = metrics.get(metric_key)
        if not isinstance(metric, dict):
            continue
        figure = _scenario_tube_figure(days=days, metric_key=metric_key, metric=metric)
        if figure is None:
            continue
        figures[metric_key] = figure
        bands = metric.get("bands") if isinstance(metric.get("bands"), dict) else {}
        metric_summary: dict[str, Any] = {
            "label": _metric_display_label(metric_key, metric),
            "series_total_count": metric.get("series_total_count"),
            "series_display_count": metric.get("series_display_count"),
        }
        for band_key in ["p05", "p50", "p95"]:
            values = [float(value) for value in (bands.get(band_key) or [])]
            if values:
                metric_summary[f"{band_key}_final"] = values[-1]
                metric_summary[f"{band_key}_max"] = max(values)
                metric_summary[f"{band_key}_max_day"] = days[values.index(max(values))] if days else None
        metric_summaries[metric_key] = metric_summary
        bundle.append(
            {
                "label": labels.get(metric_key, _metric_display_label(metric_key, metric)),
                "asset": {"figure": figure},
            }
        )

    overview_entries = (
        [{"label": "Lecture", "asset": _global_trajectory_note_asset(payload.get("run_count"), len(days))}] + bundle
        if bundle
        else []
    )
    factor_tube_figures = _build_factor_tube_figures(
        summary_json=summary_json,
        summary=summary,
        days=days,
        metrics=metrics,
    )

    return {
        "available": bool(bundle),
        "path": str(trajectories_path),
        "schema_version": payload.get("schema_version"),
        "run_count": payload.get("run_count"),
        "stochastic_run_count": payload.get("stochastic_run_count"),
        "days": days,
        "figures": figures,
        "factor_tube_figures": factor_tube_figures,
        "metric_summaries": metric_summaries,
        "overview_bundle": {"bundle": overview_entries} if len(overview_entries) > 1 else (overview_entries[0]["asset"] if overview_entries else None),
    }
