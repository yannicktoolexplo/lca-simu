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
DEFAULT_PAIRED_PROPAGATION_FILENAME = "montecarlo_paired_propagation.json"
DEFAULT_VARIANCE_DECOMPOSITION_FILENAME = "variance_decomposition.json"
DEFAULT_COST_DIAGNOSTICS_FILENAME = "montecarlo_cost_diagnostics.json"
DEFAULT_TEMPORAL_PROPAGATION_FILENAME = "montecarlo_temporal_propagation.json"
FACTOR_TUBE_DISPLAY_LIMIT = 4
FACTOR_TUBE_GROUP_QUANTILE = 0.20
FACTOR_TUBE_CANDIDATE_LIMIT = FACTOR_TUBE_DISPLAY_LIMIT * 4
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
EXCLUDED_OPERATIONAL_FACTORS = {
    "factor::supplier_reliability_scale",
}
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

VARIANCE_KPI_LABELS = {
    "kpi::fill_rate": "Disponibilite produit",
    "kpi::ending_backlog": "Backlog final",
    "kpi::total_cost": "Cout supply total",
    "kpi::total_produced": "Production realisee",
    "kpi::total_supplier_capacity_binding_qty": "Contrainte capacite fournisseur",
    "kpi::avg_inventory": "Stock moyen",
}

VARIANCE_FAMILY_LABELS = {
    "demand": "Demande",
    "production_capacity": "Capacite usine",
    "production_stock": "Stock produits finis",
    "supplier_stock": "Stock fournisseur",
    "supplier_capacity": "Capacite fournisseur",
    "supplier_lead_time": "Delai fournisseur",
    "supplier_reliability": "Fiabilite fournisseur locale",
    "external_supply_capacity": "Capacite approvisionnement externe",
    "external_supply_lead_time": "Delai approvisionnement externe",
    "external_supply_cost": "Cout approvisionnement externe",
    "purchase_cost": "Prix d'achat",
    "transport_cost": "Cout transport",
    "holding_cost": "Cout de possession",
    "other_global_factors": "Autres parametres globaux",
}

VARIANCE_FAMILY_COLORS = {
    "demand": "#2563eb",
    "production_capacity": "#16a34a",
    "production_stock": "#0f766e",
    "supplier_stock": "#0891b2",
    "supplier_capacity": "#d97706",
    "supplier_lead_time": "#7c3aed",
    "supplier_reliability": "#be123c",
    "external_supply_capacity": "#65a30d",
    "external_supply_lead_time": "#9333ea",
    "external_supply_cost": "#c2410c",
    "purchase_cost": "#0369a1",
    "transport_cost": "#ea580c",
    "holding_cost": "#4f46e5",
    "other_global_factors": "#64748b",
}

VARIANCE_RESIDUAL_KEY = "interactions_nonlinearities_unexplained"
VARIANCE_RESIDUAL_LABEL = "Interactions / non-linearites / non expliquee"
VARIANCE_WARNING = (
    "Contribution predictive issue des runs Monte Carlo; pas une causalite terrain "
    "ni une decomposition de Sobol."
)


def _load_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _clamped_percent(value: Any) -> float:
    numeric = _as_float(value)
    if numeric is None:
        return 0.0
    return min(100.0, max(0.0, numeric))


def _build_variance_decomposition_asset(path: Path) -> dict[str, Any]:
    """Normalize the optional predictive variance decomposition for the map."""

    empty = {
        "available": False,
        "path": str(path),
        "status": "missing" if not path.exists() else "invalid",
        "warning": VARIANCE_WARNING,
        "kpis": [],
        "figure": None,
    }
    if not path.exists():
        return empty
    payload = _load_json(path)
    raw_kpis = payload.get("kpis") if isinstance(payload.get("kpis"), dict) else {}
    if not raw_kpis:
        return empty

    kpis: list[dict[str, Any]] = []
    family_order: list[str] = []
    for kpi_key, raw_kpi in raw_kpis.items():
        if not isinstance(raw_kpi, dict) or str(raw_kpi.get("status") or "") != "ok":
            continue
        families: list[dict[str, Any]] = []
        for raw_family in raw_kpi.get("families") or []:
            if not isinstance(raw_family, dict):
                continue
            family_key = str(raw_family.get("family") or "").strip()
            if not family_key:
                continue
            percent = _clamped_percent(raw_family.get("explained_variance_percent"))
            if percent <= 0.0:
                continue
            if family_key not in family_order:
                family_order.append(family_key)
            families.append(
                {
                    "family": family_key,
                    "label": VARIANCE_FAMILY_LABELS.get(
                        family_key,
                        str(raw_family.get("label") or family_key.replace("_", " ").title()),
                    ),
                    "percent": percent,
                    "factor_count": int(raw_family.get("factor_count") or 0),
                }
            )
        explained_percent = _clamped_percent(raw_kpi.get("explained_percent"))
        residual_percent = _clamped_percent(raw_kpi.get("residual_interactions_unexplained_percent"))
        kpis.append(
            {
                "kpi": str(kpi_key),
                "label": VARIANCE_KPI_LABELS.get(str(kpi_key), str(kpi_key).replace("kpi::", "").replace("_", " ").title()),
                "sample_count": int(raw_kpi.get("sample_count") or 0),
                "explained_percent": explained_percent,
                "residual_percent": residual_percent,
                "families": families,
            }
        )

    if not kpis:
        empty["status"] = "empty"
        return empty

    series: list[dict[str, Any]] = []
    for family_key in family_order:
        values = []
        label = VARIANCE_FAMILY_LABELS.get(family_key, family_key.replace("_", " ").title())
        for kpi in kpis:
            family = next((row for row in kpi["families"] if row["family"] == family_key), None)
            values.append(float(family["percent"]) if family else 0.0)
        series.append(
            {
                "key": family_key,
                "label": label,
                "values": values,
                "color": VARIANCE_FAMILY_COLORS.get(family_key, "#64748b"),
            }
        )
    series.append(
        {
            "key": VARIANCE_RESIDUAL_KEY,
            "label": VARIANCE_RESIDUAL_LABEL,
            "values": [float(kpi["residual_percent"]) for kpi in kpis],
            "color": "#cbd5e1",
        }
    )

    return {
        "available": True,
        "path": str(path),
        "status": "available",
        "schema_version": payload.get("schema_version"),
        "warning": VARIANCE_WARNING,
        "method": payload.get("method") if isinstance(payload.get("method"), dict) else {},
        "source": payload.get("source") if isinstance(payload.get("source"), dict) else {},
        "kpis": kpis,
        "figure": {
            "kind": "stacked_bar_horizontal",
            "title": "Decomposition predictive de la dispersion Monte Carlo",
            "x_label": "Part de la dispersion du KPI (%)",
            "labels": [kpi["label"] for kpi in kpis],
            "series": series,
            "warning": VARIANCE_WARNING,
        },
    }


def _as_float(value: Any) -> float | None:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(numeric):
        return None
    return numeric


def _build_cost_diagnostics_asset(path: Path) -> dict[str, Any]:
    """Expose the accounting perimeter separately from exceptional sourcing."""

    empty = {"available": False, "path": str(path), "status": "missing" if not path.exists() else "invalid"}
    if not path.exists():
        return empty
    payload = _load_json(path)
    total = payload.get("total_cost") if isinstance(payload.get("total_cost"), dict) else {}
    non_production = (
        payload.get("cost_without_production")
        if isinstance(payload.get("cost_without_production"), dict)
        else {}
    )
    exposure = (
        payload.get("economic_exposure_including_exceptional_supply")
        if isinstance(payload.get("economic_exposure_including_exceptional_supply"), dict)
        else {}
    )
    components = payload.get("components") if isinstance(payload.get("components"), dict) else {}
    coupling = (
        payload.get("production_cost_coupling")
        if isinstance(payload.get("production_cost_coupling"), dict)
        else {}
    )
    exceptional = (
        payload.get("exceptional_supply_cost")
        if isinstance(payload.get("exceptional_supply_cost"), dict)
        else {}
    )
    if not total:
        return empty
    return {
        "available": True,
        "path": str(path),
        "status": "available",
        "sample_count": int(payload.get("sample_count") or 0),
        "total_cost": total,
        "cost_without_production": non_production,
        "exceptional_supply": components.get("exceptional_supply") or {},
        "economic_exposure": exposure,
        "production_share": _as_float(coupling.get("median_share_of_total")),
        "production_amplification": _as_float(coupling.get("mechanical_amplification_factor")),
        "fixed_production_share_detected": bool(coupling.get("fixed_share_detected")),
        "production_cost_reading": str(coupling.get("reading") or ""),
        "exceptional_in_total": bool(exceptional.get("included_in_total_cost")),
        "accounting_identity_valid": bool(
            (payload.get("accounting_identity") or {}).get("valid_within_tolerance")
        ),
    }


def _build_temporal_propagation_asset(path: Path) -> dict[str, Any]:
    empty = {
        "available": False,
        "path": str(path),
        "status": "missing" if not path.exists() else "invalid",
        "factors": [],
    }
    if not path.exists():
        return empty
    payload = _load_json(path)
    factors = [
        row
        for row in (payload.get("factors") or [])
        if isinstance(row, dict)
    ]
    if not factors:
        return empty
    return {
        "available": True,
        "path": str(path),
        "status": "available",
        "schema_version": payload.get("schema_version"),
        "horizon_days": int(payload.get("horizon_days") or 0),
        "reading": str(payload.get("reading") or ""),
        "lotification_status": payload.get("lotification_status") or {},
        "factors": factors,
    }


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
    return (
        raw_factor not in EXCLUDED_OPERATIONAL_FACTORS
        and raw_factor.startswith(INPUT_FACTOR_PREFIXES)
    )


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
        if (
            factor
            and factor not in EXCLUDED_OPERATIONAL_FACTORS
            and factor in sample_columns
            and factor not in ranked
        ):
            ranked.append(factor)
    supplier_first = [factor for factor in ranked if _is_supplier_prediction_factor(factor)]
    fallback = [factor for factor in ranked if factor not in supplier_first]
    candidates = supplier_first + fallback
    if candidates:
        return candidates[:FACTOR_TUBE_CANDIDATE_LIMIT]

    discovered = sorted(
        factor
        for factor in sample_columns
        if _is_supplier_prediction_factor(factor)
    )
    return discovered[:FACTOR_TUBE_CANDIDATE_LIMIT]


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


def _float_series(values: Any, length: int) -> list[float]:
    if not isinstance(values, list):
        return []
    clean: list[float] = []
    for value in values[:length]:
        numeric = _as_float(value)
        clean.append(0.0 if numeric is None else numeric)
    if len(clean) != length:
        return []
    return clean


def _global_context_for_metric(metric: dict[str, Any], days: list[int]) -> dict[str, Any]:
    bands = metric.get("bands") if isinstance(metric.get("bands"), dict) else {}
    if not bands:
        return {}
    context_bands: list[dict[str, Any]] = []
    full_low = _float_series(bands.get("min") or bands.get("p00"), len(days))
    full_high = _float_series(bands.get("max") or bands.get("p100"), len(days))
    if not full_low or not full_high:
        full_band = _min_max_band_from_metric_series(days, metric)
        if full_band:
            full_low = _float_series(full_band.get("low"), len(days))
            full_high = _float_series(full_band.get("high"), len(days))
    if full_low and full_high:
        context_bands.append(
            {
                "label": "Monte Carlo global min-max",
                "low": full_low,
                "high": full_high,
                "fillcolor": "rgba(100,116,139,0.045)",
            }
        )
    for label, low_key, high_key, fillcolor in [
        ("Monte Carlo global 5-95%", "p05", "p95", "rgba(15,118,110,0.045)"),
        ("Monte Carlo global 10-90%", "p10", "p90", "rgba(15,118,110,0.065)"),
        ("Monte Carlo global 25-75%", "p25", "p75", "rgba(15,118,110,0.095)"),
    ]:
        low = _float_series(bands.get(low_key), len(days))
        high = _float_series(bands.get(high_key), len(days))
        if low and high:
            context_bands.append({"label": label, "low": low, "high": high, "fillcolor": fillcolor})
    median = _float_series(bands.get("p50"), len(days))
    spread_reference = "min-max" if full_low and full_high else "5-95%"
    spread_low = full_low or _float_series(bands.get("p05"), len(days))
    spread_high = full_high or _float_series(bands.get("p95"), len(days))
    max_spread = (
        max(abs(high - low) for low, high in zip(spread_low, spread_high))
        if spread_low and spread_high
        else 0.0
    )
    if max_spread <= 1e-9 and context_bands:
        first_band = context_bands[0]
        first_low = _float_series(first_band.get("low"), len(days))
        first_high = _float_series(first_band.get("high"), len(days))
        if first_low and first_high:
            max_spread = max(abs(high - low) for low, high in zip(first_low, first_high))
    return {
        "days": days,
        "bands": context_bands,
        "median": median,
        "max_spread": max_spread,
        "spread_reference": spread_reference,
    }


def _series_correlation(left: list[float], right: list[float]) -> float:
    n = min(len(left), len(right))
    if n < 2:
        return 0.0
    xs = left[:n]
    ys = right[:n]
    mean_x = _mean(xs)
    mean_y = _mean(ys)
    centered_x = [value - mean_x for value in xs]
    centered_y = [value - mean_y for value in ys]
    denom_x = math.sqrt(sum(value * value for value in centered_x))
    denom_y = math.sqrt(sum(value * value for value in centered_y))
    if denom_x <= 1e-12 or denom_y <= 1e-12:
        return 0.0
    return float(sum(x * y for x, y in zip(centered_x, centered_y)) / (denom_x * denom_y))


def _is_redundant_delta(delta: list[float], existing: list[list[float]]) -> bool:
    peak = max((abs(value) for value in delta), default=0.0)
    if peak <= 1e-9:
        return True
    for previous in existing:
        previous_peak = max((abs(value) for value in previous), default=0.0)
        if previous_peak <= 1e-9:
            continue
        relative_peak_gap = abs(peak - previous_peak) / max(peak, previous_peak, 1.0)
        if relative_peak_gap > 0.08:
            continue
        if _series_correlation(delta, previous) >= 0.995:
            return True
    return False


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
    return (supplier_first + fallback)[:FACTOR_TUBE_CANDIDATE_LIMIT]


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
    global_context = _global_context_for_metric(metric, days)
    global_max_spread = float(global_context.get("max_spread") or 0.0) if global_context else 0.0
    bands: list[dict[str, Any]] = []
    delta_signatures: list[list[float]] = []
    for factor in factors:
        if len(bands) >= FACTOR_TUBE_DISPLAY_LIMIT:
            break
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
        delta_series = [high - low for low, high in zip(low_medians, high_medians)]
        max_gap = max(abs(value) for value in delta_series)
        if max_gap <= 1e-9:
            continue
        if _is_redundant_delta(delta_series, delta_signatures):
            continue
        delta_signatures.append(delta_series)
        color, fill = FACTOR_TUBE_COLORS[len(bands) % len(FACTOR_TUBE_COLORS)]
        family, node_id = _factor_node_hint(factor)
        explained_share = max_gap / global_max_spread if global_max_spread > 1e-9 else None
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
                "max_gap": max_gap,
                "explained_share": explained_share,
                "global_spread_reference": global_context.get("spread_reference") if global_context else "",
            }
        )
    if not bands:
        return None
    return {
        "kind": "factor_tubes",
        "title": f"{_metric_display_label(metric_key, metric)} - lecture conditionnelle par input incertain",
        "y_label": str(metric.get("y_label") or ""),
        "x_label": "Jour",
        "note": (
            "Lecture: fond gris = dispersion Monte Carlo globale. Couleurs = comparaison conditionnelle entre runs ou l'input est bas et runs ou il est haut. "
            "Cette vue ne doit pas envelopper toutes les trajectoires: elle montre quelle part de la dispersion globale semble associee a un input donne. "
            "Pour les KPI rares en pics, les zones utilisent une moyenne ou un percentile haut de groupe afin de ne pas masquer les evenements tardifs. "
            "Les autres aleas continuent de varier: ce n'est pas une preuve causale isolee."
        ),
        "days": days,
        "bands": bands,
        "global_context": global_context,
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


def _nominal_values_for_days(
    *,
    source_days: list[int],
    metric: dict[str, Any],
    target_days: list[int],
) -> list[float]:
    nominal = next(
        (
            series
            for series in (metric.get("series") or [])
            if isinstance(series, dict) and bool(series.get("is_baseline"))
        ),
        None,
    )
    if not isinstance(nominal, dict):
        return []
    values = nominal.get("values") if isinstance(nominal.get("values"), list) else []
    points = {
        int(day): float(values[position])
        for position, day in enumerate(source_days[: len(values)])
    }
    output: list[float] = []
    previous = 0.0
    for day in target_days:
        previous = points.get(int(day), previous)
        output.append(previous)
    return output


def _build_paired_factor_tube_figures(
    *,
    payload: dict[str, Any],
    source_days: list[int],
    metrics: dict[str, Any],
) -> dict[str, Any]:
    if payload.get("method") != "paired_controlled_runs":
        return {}
    paired_days = [int(day) for day in (payload.get("days") or [])]
    paired_metrics = payload.get("metrics") if isinstance(payload.get("metrics"), dict) else {}
    if not paired_days or not paired_metrics:
        return {}
    uncertainty = float(payload.get("input_relative_uncertainty") or 0.20)
    figures: dict[str, Any] = {}
    for metric_key in FACTOR_TUBE_METRIC_TARGETS:
        paired_metric = paired_metrics.get(metric_key)
        source_metric = metrics.get(metric_key)
        if not isinstance(paired_metric, dict) or not isinstance(source_metric, dict):
            continue
        nominal_values = _nominal_values_for_days(
            source_days=source_days,
            metric=source_metric,
            target_days=paired_days,
        )
        bands: list[dict[str, Any]] = []
        paired_factors = [row for row in (paired_metric.get("factors") or []) if isinstance(row, dict)]
        metric_max_width = max((abs(float(row.get("max_width") or 0.0)) for row in paired_factors), default=0.0)
        display_threshold = max(1e-9, metric_max_width * 0.005)
        for index, factor_data in enumerate(paired_factors):
            if not isinstance(factor_data, dict):
                continue
            if str(factor_data.get("factor") or "") in EXCLUDED_OPERATIONAL_FACTORS:
                continue
            if abs(float(factor_data.get("max_width") or 0.0)) < display_threshold:
                continue
            context_low = factor_data.get("low") if isinstance(factor_data.get("low"), list) else []
            context_high = factor_data.get("high") if isinstance(factor_data.get("high"), list) else []
            context_center = factor_data.get("center") if isinstance(factor_data.get("center"), list) else []
            if not context_low or not context_high or not context_center:
                continue
            length = min(len(context_low), len(context_high), len(context_center), len(nominal_values))
            low: list[float] = []
            high: list[float] = []
            for position in range(length):
                nominal_value = float(nominal_values[position])
                low_value = nominal_value + float(context_low[position]) - float(context_center[position])
                high_value = nominal_value + float(context_high[position]) - float(context_center[position])
                if bool(source_metric.get("zero_floor")):
                    low_value = max(0.0, low_value)
                    high_value = max(0.0, high_value)
                if metric_key == "service_rate":
                    low_value = max(0.0, min(100.0, low_value))
                    high_value = max(0.0, min(100.0, high_value))
                low.append(min(low_value, high_value))
                high.append(max(low_value, high_value))
            factor = str(factor_data.get("factor") or "")
            family = str(factor_data.get("family") or "global")
            node_id = str(factor_data.get("node_id") or "")
            color, fill = FACTOR_TUBE_COLORS[index % len(FACTOR_TUBE_COLORS)]
            bands.append(
                {
                    "factor": factor,
                    "label": _factor_label(factor),
                    "family": family,
                    "node_id": node_id,
                    "highlight_node_ids": [node_id] if node_id else [],
                    "low": low,
                    "high": high,
                    "center": nominal_values[:length],
                    "line_color": color,
                    "fillcolor": fill,
                    "low_input": factor_data.get("input_low", 1.0 - uncertainty),
                    "reference_input": factor_data.get("input_reference", 1.0),
                    "high_input": factor_data.get("input_high", 1.0 + uncertainty),
                    "background_count": int(factor_data.get("background_count") or 0),
                    "aggregation": "paired_effect_p10_p90",
                    "aggregation_label": "effet apparie P10-P90",
                    "max_gap": factor_data.get("max_width"),
                }
            )
        if not bands:
            continue
        figures[metric_key] = {
            "kind": "factor_tubes",
            "method": "paired_controlled_runs",
            "paired_controlled": True,
            "title": f"{_metric_display_label(metric_key, source_metric)} - effet marginal controle",
            "y_label": str(source_metric.get("y_label") or ""),
            "x_label": "Jour",
            "note": (
                "Chaque zone isole l'effet d'un seul parametre, toutes choses egales par ailleurs. "
                "Les valeurs basse, centrale et haute suivent la plage metier affichee pour ce parametre; "
                f"a defaut, la plage de repli est +/-{uncertainty * 100:.0f}%. "
                "La bande P10-P90 agrege plusieurs contextes Monte Carlo apparies puis applique cet effet autour du nominal. "
                "C'est un effet marginal local: il ne doit pas couvrir l'enveloppe Monte Carlo globale, ou plusieurs aleas "
                "et leurs interactions varient simultanement."
            ),
            "days": paired_days,
            "bands": bands,
            "nominal": {"label": "Nominal", "values": nominal_values},
            "background_count": int(payload.get("background_count") or 0),
            "paired_run_count": int(payload.get("run_count") or 0),
        }
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
    variance_path = summary_json.with_name(DEFAULT_VARIANCE_DECOMPOSITION_FILENAME)
    cost_path = summary_json.with_name(DEFAULT_COST_DIAGNOSTICS_FILENAME)
    temporal_path = summary_json.with_name(DEFAULT_TEMPORAL_PROPAGATION_FILENAME)
    variance_decomposition = _build_variance_decomposition_asset(variance_path)
    cost_diagnostics = _build_cost_diagnostics_asset(cost_path)
    temporal_propagation = _build_temporal_propagation_asset(temporal_path)
    if not trajectories_path.exists():
        return {
            "available": False,
            "path": str(trajectories_path),
            "figures": {},
            "factor_tube_figures": {},
            "variance_decomposition": variance_decomposition,
            "cost_diagnostics": cost_diagnostics,
            "temporal_propagation": temporal_propagation,
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
            "variance_decomposition": variance_decomposition,
            "cost_diagnostics": cost_diagnostics,
            "temporal_propagation": temporal_propagation,
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
    paired_path = summary_json.with_name(DEFAULT_PAIRED_PROPAGATION_FILENAME)
    paired_payload = _load_json(paired_path) if paired_path.exists() else {}
    paired_days = [int(day) for day in (paired_payload.get("days") or [])]
    same_scenario = str(paired_payload.get("scenario_id") or "") == str(summary.get("scenario_id") or "")
    same_horizon = bool(paired_days and days and paired_days[-1] == days[-1])
    if paired_payload and (not same_scenario or not same_horizon):
        paired_payload = {}
    factor_tube_figures = _build_paired_factor_tube_figures(
        payload=paired_payload,
        source_days=days,
        metrics=metrics,
    )
    factor_tube_source = "paired_controlled_runs" if factor_tube_figures else "conditional_montecarlo_fallback"
    if not factor_tube_figures:
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
        "factor_tube_source": factor_tube_source,
        "paired_propagation_path": str(paired_path) if paired_path.exists() else "",
        "variance_decomposition": variance_decomposition,
        "cost_diagnostics": cost_diagnostics,
        "temporal_propagation": temporal_propagation,
        "metric_summaries": metric_summaries,
        "overview_bundle": {"bundle": overview_entries} if len(overview_entries) > 1 else (overview_entries[0]["asset"] if overview_entries else None),
    }
