"""Diagnostics for Monte Carlo uncertainty outputs.

This module is intentionally independent from the map renderer. It reads the
compact Monte Carlo files and returns JSON-serializable business diagnostics
that can be rendered by any UI.
"""

from __future__ import annotations

import csv
import json
import math
from collections import defaultdict
from pathlib import Path
from statistics import mean, pstdev
from typing import Any, Callable


KPI_LABELS = {
    "kpi::fill_rate": "Fill rate",
    "kpi::ending_backlog": "Backlog final",
    "kpi::total_cost": "Cout total",
    "kpi::total_produced": "Production realisee",
    "kpi::total_supplier_capacity_binding_qty": "Capacite fournisseur contrainte",
    "kpi::total_external_procured_qty": "Appro amont mobilisee",
    "kpi::total_unreliable_loss_qty": "Pertes fiabilite fournisseur",
    "kpi::total_transport_cost": "Cout transport",
    "kpi::total_holding_cost": "Cout stockage",
}

PROPAGATION_PRIMARY_KPIS = [
    "kpi::fill_rate",
    "kpi::ending_backlog",
    "kpi::total_cost",
    "kpi::total_produced",
    "kpi::total_supplier_capacity_binding_qty",
    "kpi::total_external_procured_qty",
    "kpi::total_unreliable_loss_qty",
    "kpi::total_transport_cost",
    "kpi::total_holding_cost",
    "kpi::total_inventory_cost_legacy_raw_holding",
]

FACTOR_FAMILIES = [
    ("supplier_stock_node::", "supplier_stock", "Stock fournisseur"),
    ("supplier_capacity_node::", "supplier_capacity", "Capacite fournisseur"),
    ("supplier_lead_node::", "supplier_lead", "Delai fournisseur"),
    ("supplier_reliability_node::", "supplier_reliability", "Fiabilite fournisseur"),
    ("capacity_node::", "factory_capacity", "Capacite usine"),
    ("demand_item::", "demand_item", "Demande article"),
    ("factor::", "global", "Parametre global"),
]

SUPPLIER_PREDICTION_FAMILIES = {
    "supplier_stock",
    "supplier_capacity",
    "supplier_lead",
    "supplier_reliability",
}

SUPPLIER_PREDICTION_GLOBAL_SUBJECTS = {
    "lead_time_scale",
    "supplier_stock_scale",
    "supplier_capacity_scale",
    "supplier_reliability_scale",
    "external_procurement_daily_cap_days_scale",
    "external_procurement_lead_days_scale",
    "transport_cost_scale",
}

CONTEXT_GLOBAL_SUBJECTS = {
    "demand_scale",
    "holding_cost_scale",
}

RESEARCH_CONTROL_GLOBAL_SUBJECTS = {
    "capacity_scale",
    "production_stock_scale",
}


def _load_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _to_float(value: Any, default: float = float("nan")) -> float:
    try:
        if value is None or value == "":
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _finite(value: Any) -> bool:
    numeric = _to_float(value)
    return not math.isnan(numeric)


def _metric_label(metric: str) -> str:
    return KPI_LABELS.get(metric, metric.removeprefix("kpi::").replace("_", " "))


def _factor_family(raw_factor: str) -> tuple[str, str, str]:
    raw_factor = str(raw_factor or "")
    for prefix, family, label in FACTOR_FAMILIES:
        if raw_factor.startswith(prefix):
            return family, label, raw_factor.removeprefix(prefix)
    return "other", "Autre parametre", raw_factor


def _factor_label(raw_factor: str) -> str:
    family, label, subject = _factor_family(raw_factor)
    global_labels = {
        "demand_scale": "Demande globale",
        "lead_time_scale": "Delais fournisseurs globaux",
        "transport_cost_scale": "Cout transport",
        "supplier_stock_scale": "Stocks fournisseurs globaux",
        "production_stock_scale": "Stocks usines globaux",
        "capacity_scale": "Capacites usines globales",
        "supplier_capacity_scale": "Capacites fournisseurs globales",
        "supplier_reliability_scale": "Fiabilite fournisseurs globale",
        "external_procurement_daily_cap_days_scale": "Appro amont capacite globale",
        "external_procurement_lead_days_scale": "Appro amont delai global",
        "holding_cost_scale": "Cout de stockage",
    }
    if family == "global":
        return global_labels.get(subject, subject.replace("_", " "))
    return f"{label} {subject}"


def _factor_business_scope(raw_factor: str) -> tuple[str, str]:
    family, _, subject = _factor_family(raw_factor)
    if family in SUPPLIER_PREDICTION_FAMILIES:
        return "supplier_prediction", "Prediction fournisseur"
    if family == "global" and subject in SUPPLIER_PREDICTION_GLOBAL_SUBJECTS:
        return "supplier_prediction", "Prediction fournisseur"
    if family in {"demand_item"} or (family == "global" and subject in CONTEXT_GLOBAL_SUBJECTS):
        return "context", "Contexte demande/cout"
    if family == "factory_capacity" or (family == "global" and subject in RESEARCH_CONTROL_GLOBAL_SUBJECTS):
        return "research_control", "Controle modele/recherche"
    return "context", "Contexte modele"


def _read_samples(samples_csv: Path) -> list[dict[str, str]]:
    if not samples_csv.exists():
        return []
    with samples_csv.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _ok_stochastic_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    out = []
    for row in rows:
        if str(row.get("status") or "").lower() != "ok":
            continue
        if str(row.get("is_baseline") or "").lower() in {"true", "1", "yes"}:
            continue
        out.append(row)
    return out


def _probability(rows: list[dict[str, str]], metric: str, predicate: Callable[[float], bool]) -> float | None:
    values = [_to_float(row.get(metric)) for row in rows]
    values = [value for value in values if not math.isnan(value)]
    if not values:
        return None
    return sum(1 for value in values if predicate(value)) / len(values)


def _build_thresholds(summary: dict[str, Any], rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    baseline_cost = _to_float((summary.get("metric_statistics") or {}).get("kpi::total_cost", {}).get("baseline"))
    thresholds: list[tuple[str, str, str, float | None, Callable[[float], bool]]] = [
        ("Fill rate < 99%", "kpi::fill_rate", "<", 0.99, lambda value: value < 0.99),
        ("Fill rate < 95%", "kpi::fill_rate", "<", 0.95, lambda value: value < 0.95),
        ("Fill rate < 90%", "kpi::fill_rate", "<", 0.90, lambda value: value < 0.90),
        ("Backlog > 0", "kpi::ending_backlog", ">", 0.0, lambda value: value > 0.0),
        ("Backlog > 1M", "kpi::ending_backlog", ">", 1_000_000.0, lambda value: value > 1_000_000.0),
        (
            "Capacite fournisseur contrainte",
            "kpi::total_supplier_capacity_binding_qty",
            ">",
            0.0,
            lambda value: value > 0.0,
        ),
    ]
    if not math.isnan(baseline_cost):
        thresholds.append(
            (
                "Cout > nominal",
                "kpi::total_cost",
                ">",
                baseline_cost,
                lambda value, baseline=baseline_cost: value > baseline,
            )
        )

    payload = []
    for label, metric, comparator, threshold, predicate in thresholds:
        probability = _probability(rows, metric, predicate)
        if probability is None:
            continue
        payload.append(
            {
                "label": label,
                "metric": metric,
                "metric_label": _metric_label(metric),
                "comparator": comparator,
                "threshold": threshold,
                "probability": round(probability, 6),
            }
        )
    return payload


def _build_kpi_distributions(summary: dict[str, Any]) -> list[dict[str, Any]]:
    metric_stats = summary.get("metric_statistics") if isinstance(summary.get("metric_statistics"), dict) else {}
    preferred = [
        "kpi::fill_rate",
        "kpi::ending_backlog",
        "kpi::total_cost",
        "kpi::total_produced",
        "kpi::total_supplier_capacity_binding_qty",
        "kpi::total_external_procured_qty",
        "kpi::total_unreliable_loss_qty",
        "kpi::total_transport_cost",
        "kpi::total_holding_cost",
    ]
    metrics = preferred + [key for key in sorted(metric_stats) if key not in preferred]
    out = []
    for metric in metrics:
        stats = metric_stats.get(metric)
        if not isinstance(stats, dict):
            continue
        row = {"metric": metric, "label": _metric_label(metric)}
        for key in ["baseline", "mean", "std", "min", "p05", "p50", "p95", "max", "n"]:
            if key in stats and _finite(stats.get(key)):
                row[key] = _to_float(stats.get(key))
        out.append(row)
    return out


def _build_drivers(summary: dict[str, Any]) -> tuple[dict[str, list[dict[str, Any]]], list[dict[str, Any]], list[dict[str, Any]]]:
    rankings = summary.get("driver_rankings") if isinstance(summary.get("driver_rankings"), dict) else {}
    by_kpi: dict[str, list[dict[str, Any]]] = {}
    family_rows: dict[str, dict[str, Any]] = {}
    supplier_rows: dict[str, dict[str, Any]] = {}

    for target, rows in rankings.items():
        if not isinstance(rows, list):
            continue
        target_rows = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            raw_factor = str(row.get("factor") or "")
            corr = _to_float(row.get("correlation"))
            abs_corr = _to_float(row.get("absolute_correlation"), abs(corr) if not math.isnan(corr) else 0.0)
            if math.isnan(corr):
                continue
            family, family_label, subject = _factor_family(raw_factor)
            item = {
                "factor": raw_factor,
                "label": _factor_label(raw_factor),
                "family": family,
                "family_label": family_label,
                "subject": subject,
                "target": target,
                "target_label": _metric_label(target),
                "correlation": round(corr, 6),
                "absolute_correlation": round(abs_corr, 6),
                "direction": "positive" if corr >= 0 else "negative",
            }
            target_rows.append(item)

            family_bucket = family_rows.setdefault(
                family,
                {
                    "family": family,
                    "label": family_label,
                    "driver_count": 0,
                    "top_absolute_correlation": 0.0,
                    "top_driver": None,
                },
            )
            family_bucket["driver_count"] += 1
            if abs_corr > float(family_bucket.get("top_absolute_correlation") or 0.0):
                family_bucket["top_absolute_correlation"] = round(abs_corr, 6)
                family_bucket["top_driver"] = item

            if family.startswith("supplier_"):
                supplier_bucket = supplier_rows.setdefault(
                    subject,
                    {
                        "supplier_id": subject,
                        "score": 0.0,
                        "driver_count": 0,
                        "top_driver": None,
                        "drivers": [],
                    },
                )
                supplier_bucket["driver_count"] += 1
                supplier_bucket["drivers"].append(item)
                if abs_corr > float(supplier_bucket.get("score") or 0.0):
                    supplier_bucket["score"] = round(abs_corr, 6)
                    supplier_bucket["top_driver"] = item
        by_kpi[target] = target_rows

    families = sorted(
        family_rows.values(),
        key=lambda row: (float(row.get("top_absolute_correlation") or 0.0), int(row.get("driver_count") or 0)),
        reverse=True,
    )
    suppliers = sorted(
        supplier_rows.values(),
        key=lambda row: (float(row.get("score") or 0.0), int(row.get("driver_count") or 0)),
        reverse=True,
    )
    for supplier in suppliers:
        supplier["drivers"] = sorted(
            supplier["drivers"],
            key=lambda row: float(row.get("absolute_correlation") or 0.0),
            reverse=True,
        )[:6]
    return by_kpi, families, suppliers


def _build_extreme_runs(summary: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    top_runs = summary.get("top_runs") if isinstance(summary.get("top_runs"), dict) else {}
    out: dict[str, list[dict[str, Any]]] = {}
    for bucket, rows in top_runs.items():
        if not isinstance(rows, list):
            continue
        clean_rows = []
        for row in rows[:10]:
            if not isinstance(row, dict):
                continue
            clean_rows.append({key: value for key, value in row.items() if key == "run_id" or _finite(value)})
        out[bucket] = clean_rows
    return out


def _build_trajectory_summary(trajectories_json: Path) -> dict[str, Any]:
    payload = _load_json(trajectories_json)
    if not payload:
        return {"available": False, "path": str(trajectories_json)}
    metrics = payload.get("metrics") if isinstance(payload.get("metrics"), dict) else {}
    metric_rows = []
    for key, metric in metrics.items():
        if not isinstance(metric, dict):
            continue
        bands = metric.get("bands") if isinstance(metric.get("bands"), dict) else {}
        metric_rows.append(
            {
                "metric": key,
                "label": metric.get("label", key),
                "series_total_count": metric.get("series_total_count"),
                "series_display_count": metric.get("series_display_count"),
                "bands": sorted(bands.keys()),
            }
        )
    days = payload.get("days") if isinstance(payload.get("days"), list) else []
    return {
        "available": True,
        "path": str(trajectories_json),
        "run_count": payload.get("run_count"),
        "stochastic_run_count": payload.get("stochastic_run_count"),
        "max_points": payload.get("max_points"),
        "max_display_runs": payload.get("max_display_runs"),
        "day_count": len(days),
        "first_day": days[0] if days else None,
        "last_day": days[-1] if days else None,
        "metrics": metric_rows,
    }


def _suite_assessment(summary_json: Path) -> dict[str, Any]:
    suite_path = summary_json.parent.parent / "montecarlo_suite_summary.json"
    suite = _load_json(suite_path)
    if not suite:
        return {"available": False, "path": str(suite_path)}
    assessment = suite.get("final_assessment") if isinstance(suite.get("final_assessment"), dict) else {}
    return {
        "available": True,
        "path": str(suite_path),
        "selected_profile": suite.get("selected_profile"),
        "final_runs": suite.get("final_runs"),
        "workers": suite.get("workers"),
        "status": assessment.get("status"),
        "variation_score": assessment.get("variation_score"),
        "target_distance": assessment.get("target_distance"),
        "reason": assessment.get("reason"),
    }


def _boolish(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() in {"1", "true", "yes", "y"}


def _ok_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    return [row for row in rows if str(row.get("status") or "ok").lower() == "ok"]


def _distribution_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    ok_rows = _ok_rows(rows)
    stochastic_rows = [row for row in ok_rows if not _boolish(row.get("is_baseline"))]
    return stochastic_rows or ok_rows


def _baseline_row(rows: list[dict[str, str]]) -> dict[str, str]:
    for row in rows:
        if _boolish(row.get("is_baseline")) and str(row.get("status") or "ok").lower() == "ok":
            return row
    ok_rows = _ok_rows(rows)
    return ok_rows[0] if ok_rows else {}


def _coalesce_int(*values: Any) -> int | None:
    for value in values:
        number = _to_float(value)
        if not math.isnan(number):
            return int(number)
    return None


def _finite_number(value: Any) -> int | float | None:
    number = _to_float(value)
    if math.isnan(number) or not math.isfinite(number):
        return None
    if number.is_integer():
        return int(number)
    return number


def _percentile(sorted_values: list[float], p: float) -> float:
    if len(sorted_values) == 1:
        return sorted_values[0]
    pos = max(0.0, min(1.0, p)) * (len(sorted_values) - 1)
    lo = int(pos)
    hi = min(lo + 1, len(sorted_values) - 1)
    frac = pos - lo
    return sorted_values[lo] * (1.0 - frac) + sorted_values[hi] * frac


def _kpi_order(keys: Any) -> list[str]:
    preferred = [
        "kpi::fill_rate",
        "kpi::ending_backlog",
        "kpi::total_cost",
        "kpi::total_produced",
        "kpi::total_supplier_capacity_binding_qty",
        "kpi::total_inventory_cost_legacy_raw_holding",
        "kpi::total_demand",
    ]
    items = [str(key) for key in keys]
    head = [key for key in preferred if key in items]
    tail = sorted(key for key in items if key not in head)
    return head + tail


def _sample_kpi_statistics(rows: list[dict[str, str]]) -> dict[str, dict[str, Any]]:
    distribution_rows = _distribution_rows(rows)
    baseline = _baseline_row(rows)
    kpi_cols = sorted({key for row in rows for key in row if key.startswith("kpi::")})
    out: dict[str, dict[str, Any]] = {}
    for metric in kpi_cols:
        values = [_to_float(row.get(metric)) for row in distribution_rows]
        clean = sorted(value for value in values if not math.isnan(value))
        if not clean:
            continue
        baseline_value = _to_float(baseline.get(metric)) if baseline else float("nan")
        out[metric] = {
            "n": len(clean),
            "mean": mean(clean),
            "std": pstdev(clean) if len(clean) > 1 else 0.0,
            "min": clean[0],
            "p05": _percentile(clean, 0.05),
            "p50": _percentile(clean, 0.50),
            "p95": _percentile(clean, 0.95),
            "max": clean[-1],
            "baseline": None if math.isnan(baseline_value) else baseline_value,
        }
    return out


def _kpi_final_distributions(summary: dict[str, Any], rows: list[dict[str, str]]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    metric_stats = summary.get("metric_statistics") if isinstance(summary.get("metric_statistics"), dict) else {}
    for metric, stats in metric_stats.items():
        if not isinstance(stats, dict):
            continue
        out[str(metric)] = _normalize_kpi_distribution(str(metric), stats, "summary.metric_statistics")

    for metric, stats in _sample_kpi_statistics(rows).items():
        if metric not in out:
            out[metric] = _normalize_kpi_distribution(metric, stats, "montecarlo_samples.csv")

    return {metric: out[metric] for metric in _kpi_order(out.keys())}


def _normalize_kpi_distribution(metric: str, stats: dict[str, Any], source: str) -> dict[str, Any]:
    row = {
        "kpi": metric,
        "name": metric.removeprefix("kpi::"),
        "label": _metric_label(metric),
        "source": source,
    }
    for key in ["n", "mean", "std", "min", "p05", "p50", "p95", "max", "baseline"]:
        row[key] = _finite_number(stats.get(key))
    p50 = _to_float(row.get("p50"))
    baseline = _to_float(row.get("baseline"))
    row["delta_p50_vs_baseline"] = None if math.isnan(p50) or math.isnan(baseline) else p50 - baseline
    return row


def _decision_metrics_payload(
    summary: dict[str, Any],
    rows: list[dict[str, str]],
) -> dict[str, Any]:
    raw = summary.get("decision_metrics")
    if isinstance(raw, dict) and raw:
        return {str(key): _finite_number(value) for key, value in raw.items()}

    distribution_rows = _distribution_rows(rows)
    baseline = _baseline_row(rows)
    baseline_cost = _to_float(baseline.get("kpi::total_cost")) if baseline else float("nan")
    baseline_inventory = (
        _to_float(baseline.get("kpi::total_inventory_cost_legacy_raw_holding"))
        if baseline
        else float("nan")
    )
    baseline_binding = (
        _to_float(baseline.get("kpi::total_supplier_capacity_binding_qty"))
        if baseline
        else float("nan")
    )
    return {
        "fill_rate_below_100pct": _probability(
            distribution_rows,
            "kpi::fill_rate",
            lambda value: value < 0.999999,
        ),
        "fill_rate_below_99pct": _probability(
            distribution_rows,
            "kpi::fill_rate",
            lambda value: value < 0.99,
        ),
        "backlog_positive": _probability(
            distribution_rows,
            "kpi::ending_backlog",
            lambda value: value > 1e-9,
        ),
        "total_cost_above_baseline": None
        if math.isnan(baseline_cost)
        else _probability(distribution_rows, "kpi::total_cost", lambda value: value > baseline_cost),
        "inventory_cost_above_baseline": None
        if math.isnan(baseline_inventory)
        else _probability(
            distribution_rows,
            "kpi::total_inventory_cost_legacy_raw_holding",
            lambda value: value > baseline_inventory,
        ),
        "supplier_capacity_binding_above_baseline": None
        if math.isnan(baseline_binding)
        else _probability(
            distribution_rows,
            "kpi::total_supplier_capacity_binding_qty",
            lambda value: value > baseline_binding,
        ),
    }


def _driver_rankings_payload(drivers_by_kpi: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    by_kpi: dict[str, list[dict[str, Any]]] = {}
    for metric, entries in drivers_by_kpi.items():
        ranked = sorted(
            entries,
            key=lambda row: float(row.get("absolute_correlation") or 0.0),
            reverse=True,
        )
        by_kpi[str(metric)] = ranked[:12]
    return {
        "source": "summary.driver_rankings" if by_kpi else "missing",
        "by_kpi": {metric: by_kpi[metric] for metric in _kpi_order(by_kpi.keys())},
    }


def _pearson_corr(pairs: list[tuple[float, float]]) -> float | None:
    if len(pairs) < 2:
        return None
    xs = [pair[0] for pair in pairs]
    ys = [pair[1] for pair in pairs]
    mx = mean(xs)
    my = mean(ys)
    dx = [x - mx for x in xs]
    dy = [y - my for y in ys]
    denom_x = math.sqrt(sum(value * value for value in dx))
    denom_y = math.sqrt(sum(value * value for value in dy))
    denom = denom_x * denom_y
    if denom <= 0.0:
        return None
    return sum(x * y for x, y in zip(dx, dy)) / denom


def _normalize_correlation_factor(factor: str, corr: float, target: str) -> dict[str, Any]:
    family, family_label, subject = _factor_family(factor)
    return {
        "factor": factor,
        "label": _factor_label(factor),
        "family": family,
        "family_label": family_label,
        "subject": subject,
        "target": target,
        "target_label": _metric_label(target),
        "correlation": round(corr, 6),
        "absolute_correlation": round(abs(corr), 6),
        "direction": "positive" if corr >= 0 else "negative",
    }


def _correlated_factors_payload(
    summary: dict[str, Any],
    rows: list[dict[str, str]],
    fallback_by_kpi: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    raw = summary.get("factor_kpi_correlations_pearson")
    by_kpi: dict[str, list[dict[str, Any]]] = {}
    source = "summary.factor_kpi_correlations_pearson"
    if isinstance(raw, dict) and raw:
        for factor, target_corrs in raw.items():
            if not isinstance(target_corrs, dict):
                continue
            for target, corr_value in target_corrs.items():
                corr = _to_float(corr_value)
                if math.isnan(corr):
                    continue
                by_kpi.setdefault(str(target), []).append(
                    _normalize_correlation_factor(str(factor), corr, str(target))
                )
    else:
        by_kpi = _sample_correlations(rows)
        source = "montecarlo_samples.csv" if by_kpi else "missing"

    if not by_kpi and fallback_by_kpi:
        by_kpi = {metric: list(entries) for metric, entries in fallback_by_kpi.items()}
        source = "summary.driver_rankings"

    for metric, entries in list(by_kpi.items()):
        entries.sort(key=lambda row: float(row.get("absolute_correlation") or 0.0), reverse=True)
        by_kpi[metric] = entries[:12]
    return {
        "source": source,
        "by_kpi": {metric: by_kpi[metric] for metric in _kpi_order(by_kpi.keys())},
    }


def _sample_correlations(rows: list[dict[str, str]]) -> dict[str, list[dict[str, Any]]]:
    distribution_rows = _distribution_rows(rows)
    if len(distribution_rows) < 2:
        return {}
    factor_cols = sorted(
        key
        for key in {key for row in rows for key in row}
        if any(key.startswith(prefix) for prefix, _, _ in FACTOR_FAMILIES)
    )
    kpi_cols = sorted(key for key in {key for row in rows for key in row} if key.startswith("kpi::"))
    by_kpi: dict[str, list[dict[str, Any]]] = {}
    for metric in kpi_cols:
        entries = []
        for factor in factor_cols:
            pairs: list[tuple[float, float]] = []
            for row in distribution_rows:
                x = _to_float(row.get(factor))
                y = _to_float(row.get(metric))
                if not math.isnan(x) and not math.isnan(y):
                    pairs.append((x, y))
            corr = _pearson_corr(pairs)
            if corr is not None:
                entries.append(_normalize_correlation_factor(factor, corr, metric))
        if entries:
            entries.sort(key=lambda row: float(row.get("absolute_correlation") or 0.0), reverse=True)
            by_kpi[metric] = entries[:12]
    return by_kpi


def _factor_columns(rows: list[dict[str, str]]) -> list[str]:
    return sorted(
        key
        for key in {key for row in rows for key in row}
        if any(key.startswith(prefix) for prefix, _, _ in FACTOR_FAMILIES)
    )


def _kpi_columns(rows: list[dict[str, str]]) -> list[str]:
    return sorted(key for key in {key for row in rows for key in row} if key.startswith("kpi::"))


def _linear_regression(pairs: list[tuple[float, float]]) -> tuple[float | None, float | None, float | None]:
    """Return slope, intercept and correlation for y = intercept + slope*x."""

    if len(pairs) < 3:
        return None, None, None
    xs = [pair[0] for pair in pairs]
    ys = [pair[1] for pair in pairs]
    mx = mean(xs)
    my = mean(ys)
    dx = [x - mx for x in xs]
    dy = [y - my for y in ys]
    var_x = sum(value * value for value in dx)
    var_y = sum(value * value for value in dy)
    if var_x <= 1e-18 or var_y <= 1e-18:
        return None, None, None
    cov = sum(x * y for x, y in zip(dx, dy))
    slope = cov / var_x
    intercept = my - slope * mx
    corr = cov / math.sqrt(var_x * var_y)
    return slope, intercept, corr


def _factor_value_stats(
    rows: list[dict[str, str]],
    factor: str,
    baseline_row: dict[str, str] | None = None,
) -> dict[str, Any] | None:
    values = sorted(_to_float(row.get(factor)) for row in rows)
    clean = [value for value in values if not math.isnan(value)]
    if len(clean) < 2:
        return None
    factor_mean = mean(clean)
    factor_std = pstdev(clean) if len(clean) > 1 else 0.0
    if factor_std <= 1e-12:
        return None
    baseline_source = baseline_row if baseline_row is not None else _baseline_row(rows)
    baseline = _to_float(baseline_source.get(factor))
    reference = baseline if not math.isnan(baseline) else 1.0
    relative_std = None if abs(reference) <= 1e-12 else factor_std / abs(reference)
    return {
        "mean": factor_mean,
        "std": factor_std,
        "relative_std": relative_std,
        "p05": _percentile(clean, 0.05),
        "p50": _percentile(clean, 0.50),
        "p95": _percentile(clean, 0.95),
        "baseline": None if math.isnan(baseline) else baseline,
        "reference": reference,
        "n": len(clean),
    }


def _kpi_baseline_value(rows: list[dict[str, str]], metric: str) -> float | None:
    baseline = _to_float(_baseline_row(rows).get(metric))
    if math.isnan(baseline):
        return None
    return baseline


def _signal_confidence(corr: float | None) -> float:
    if corr is None or math.isnan(corr):
        return 0.0
    return min(1.0, abs(corr))


def _propagation_status(output_relative_impact: float | None, corr: float) -> tuple[str, str]:
    impact = abs(output_relative_impact or 0.0)
    signal = _signal_confidence(corr)
    if signal < 0.20:
        return "low", "Signal fragile"
    if output_relative_impact is None and signal >= 0.35:
        return "medium", "Lien visible, impact absolu"
    if impact >= 0.20 and signal >= 0.35:
        return "high", "Propagation forte"
    if impact >= 0.05 and signal >= 0.20:
        return "medium", "Propagation visible"
    if signal >= 0.35:
        return "medium", "Lien visible, effet limite"
    return "low", "Propagation faible"


def _build_uncertainty_propagation(
    rows: list[dict[str, str]],
    input_relative_uncertainty: float = 0.20,
) -> dict[str, Any]:
    """Estimate how input uncertainty propagates to output KPIs.

    The estimate is local and model-based: for each sampled input factor and KPI
    we fit y = a + b*x on successful stochastic Monte Carlo rows. A +/-20%
    input uncertainty around the nominal multiplier is approximated by
    +/- |b| * (0.20 * nominal_input) on the output KPI.
    """

    distribution_rows = _distribution_rows(rows)
    if len(distribution_rows) < 3:
        return {
            "available": False,
            "reason": "not_enough_stochastic_rows",
            "input_relative_uncertainty": input_relative_uncertainty,
            "by_kpi": {},
            "top_factors": [],
            "families": [],
            "method": "linear_regression_montecarlo",
        }

    factor_cols = _factor_columns(distribution_rows)
    kpi_cols = _kpi_order(_kpi_columns(distribution_rows))
    if not factor_cols or not kpi_cols:
        return {
            "available": False,
            "reason": "missing_factor_or_kpi_columns",
            "input_relative_uncertainty": input_relative_uncertainty,
            "by_kpi": {},
            "top_factors": [],
            "families": [],
            "method": "linear_regression_montecarlo",
        }

    baseline_row = _baseline_row(rows)
    factor_stats = {
        factor: stats
        for factor in factor_cols
        if (stats := _factor_value_stats(distribution_rows, factor, baseline_row)) is not None
    }
    primary_kpis = [metric for metric in PROPAGATION_PRIMARY_KPIS if metric in kpi_cols]
    by_kpi: dict[str, list[dict[str, Any]]] = {}
    all_rows: list[dict[str, Any]] = []
    primary_rows: list[dict[str, Any]] = []
    family_acc: dict[str, dict[str, Any]] = {}

    for metric in kpi_cols:
        metric_rows: list[dict[str, Any]] = []
        baseline = _kpi_baseline_value(rows, metric)
        for factor, stats in factor_stats.items():
            pairs: list[tuple[float, float]] = []
            for row in distribution_rows:
                x = _to_float(row.get(factor))
                y = _to_float(row.get(metric))
                if not math.isnan(x) and not math.isnan(y):
                    pairs.append((x, y))
            slope, intercept, corr = _linear_regression(pairs)
            if slope is None or corr is None or intercept is None:
                continue
            input_reference = float(stats.get("reference") or stats.get("baseline") or 1.0)
            input_delta_abs = abs(input_reference) * input_relative_uncertainty
            delta_abs = abs(slope) * input_delta_abs
            delta_signed = slope * input_delta_abs
            output_relative = None
            if baseline is not None and abs(baseline) > 1e-12:
                output_relative = delta_abs / abs(baseline)
            transfer_ratio = None
            if output_relative is not None and abs(input_relative_uncertainty) > 1e-12:
                transfer_ratio = output_relative / abs(input_relative_uncertainty)
            status, status_label = _propagation_status(output_relative, corr)
            signal_confidence = _signal_confidence(corr)
            ranking_score = (
                float(output_relative)
                if output_relative is not None
                else min(1.0, abs(corr)) * math.log1p(delta_abs)
            )
            signal_adjusted_ranking_score = ranking_score * signal_confidence
            family, family_label, subject = _factor_family(factor)
            business_scope, business_scope_label = _factor_business_scope(factor)
            row_payload = {
                "factor": factor,
                "label": _factor_label(factor),
                "family": family,
                "family_label": family_label,
                "business_scope": business_scope,
                "business_scope_label": business_scope_label,
                "subject": subject,
                "kpi": metric,
                "kpi_label": _metric_label(metric),
                "n": len(pairs),
                "correlation": round(corr, 6),
                "r2": round(corr * corr, 6),
                "slope": round(slope, 9),
                "intercept": round(intercept, 9),
                "input_baseline": stats.get("baseline"),
                "input_reference": round(input_reference, 9),
                "input_uncertainty_abs": round(input_delta_abs, 9),
                "input_mean": round(float(stats["mean"]), 9),
                "input_std": round(float(stats["std"]), 9),
                "input_relative_std": None
                if stats.get("relative_std") is None
                else round(float(stats["relative_std"]), 9),
                "input_p05": round(float(stats["p05"]), 9),
                "input_p50": round(float(stats["p50"]), 9),
                "input_p95": round(float(stats["p95"]), 9),
                "input_relative_uncertainty": round(input_relative_uncertainty, 9),
                "kpi_baseline": baseline,
                "kpi_delta_for_input_uncertainty": round(delta_signed, 9),
                "kpi_uncertainty_abs": round(delta_abs, 9),
                "kpi_uncertainty_relative_to_baseline": None
                if output_relative is None
                else round(output_relative, 9),
                "uncertainty_transfer_ratio": None if transfer_ratio is None else round(transfer_ratio, 9),
                "ranking_score": round(ranking_score, 9),
                "signal_confidence": round(signal_confidence, 9),
                "signal_adjusted_ranking_score": round(signal_adjusted_ranking_score, 9),
                "direction": "positive" if slope >= 0 else "negative",
                "status": status,
                "status_label": status_label,
                "method": "linear_regression_montecarlo",
            }
            metric_rows.append(row_payload)
            all_rows.append(row_payload)
            if metric in primary_kpis:
                primary_rows.append(row_payload)

            family_bucket = family_acc.setdefault(
                family,
                {
                    "family": family,
                    "label": family_label,
                    "driver_count": 0,
                    "max_kpi_uncertainty_abs": 0.0,
                    "max_kpi_uncertainty_relative_to_baseline": 0.0,
                    "top_driver": None,
                },
            )
            family_bucket["driver_count"] += 1
            score = float(row_payload.get("signal_adjusted_ranking_score") or 0.0)
            if score > float(family_bucket.get("max_kpi_uncertainty_relative_to_baseline") or 0.0):
                family_bucket["max_kpi_uncertainty_relative_to_baseline"] = round(score, 9)
                family_bucket["max_kpi_uncertainty_abs"] = row_payload["kpi_uncertainty_abs"]
                family_bucket["top_driver"] = row_payload

        metric_rows.sort(
            key=lambda row: (
                float(row.get("signal_adjusted_ranking_score") or 0.0),
                float(row.get("r2") or 0.0),
                float(row.get("ranking_score") or 0.0),
                float(row.get("kpi_uncertainty_abs") or 0.0),
            ),
            reverse=True,
        )
        if metric_rows:
            by_kpi[metric] = metric_rows[:15]

    all_rows.sort(
        key=lambda row: (
            float(row.get("signal_adjusted_ranking_score") or 0.0),
            float(row.get("r2") or 0.0),
            float(row.get("ranking_score") or 0.0),
            float(row.get("kpi_uncertainty_abs") or 0.0),
        ),
        reverse=True,
    )
    primary_rows.sort(
        key=lambda row: (
            float(row.get("signal_adjusted_ranking_score") or 0.0),
            float(row.get("r2") or 0.0),
            float(row.get("ranking_score") or 0.0),
            float(row.get("kpi_uncertainty_abs") or 0.0),
        ),
        reverse=True,
    )
    relative_primary_rows = [
        row for row in primary_rows if row.get("uncertainty_transfer_ratio") is not None
    ]
    relative_primary_rows.sort(
        key=lambda row: (
            float(row.get("signal_adjusted_ranking_score") or 0.0),
            float(row.get("r2") or 0.0),
            float(row.get("kpi_uncertainty_relative_to_baseline") or 0.0),
            float(row.get("kpi_uncertainty_abs") or 0.0),
        ),
        reverse=True,
    )
    absolute_primary_rows = [
        row for row in primary_rows if row.get("uncertainty_transfer_ratio") is None
    ]
    absolute_primary_rows.sort(
        key=lambda row: (
            float(row.get("signal_adjusted_ranking_score") or 0.0),
            float(row.get("r2") or 0.0),
            float(row.get("ranking_score") or 0.0),
            float(row.get("kpi_uncertainty_abs") or 0.0),
        ),
        reverse=True,
    )
    supplier_relative_rows = [
        row for row in relative_primary_rows if row.get("business_scope") == "supplier_prediction"
    ]
    supplier_absolute_rows = [
        row for row in absolute_primary_rows if row.get("business_scope") == "supplier_prediction"
    ]
    research_control_rows = [
        row for row in primary_rows if row.get("business_scope") == "research_control"
    ]
    research_control_rows.sort(
        key=lambda row: (
            float(row.get("signal_adjusted_ranking_score") or 0.0),
            float(row.get("r2") or 0.0),
            float(row.get("ranking_score") or 0.0),
            float(row.get("kpi_uncertainty_abs") or 0.0),
        ),
        reverse=True,
    )
    families = sorted(
        family_acc.values(),
        key=lambda row: (
            float(row.get("max_kpi_uncertainty_relative_to_baseline") or 0.0),
            float(row.get("max_kpi_uncertainty_abs") or 0.0),
            int(row.get("driver_count") or 0),
        ),
        reverse=True,
    )
    return {
        "available": bool(all_rows),
        "reason": "ok" if all_rows else "no_regression_signal",
        "input_relative_uncertainty": input_relative_uncertainty,
        "method": "linear_regression_montecarlo",
        "method_label": "Sensibilite marginale observee dans Monte Carlo",
        "primary_kpis": primary_kpis,
        "reading": (
            "Chaque ligne estime la variation du KPI si un multiplicateur d'entree varie de +/-20%. "
            "C'est une sensibilite marginale observee dans les runs Monte Carlo, pas une probabilite historique "
            "ni une causalite terrain directe."
        ),
        "by_kpi": {metric: by_kpi[metric] for metric in _kpi_order(by_kpi.keys())},
        "top_factors": (primary_rows or all_rows)[:20],
        "business_focus": "supplier_prediction",
        "business_focus_label": "Prediction fournisseur",
        "top_relative_factors": (relative_primary_rows or [row for row in all_rows if row.get("uncertainty_transfer_ratio") is not None])[:20],
        "top_absolute_factors": (absolute_primary_rows or [row for row in all_rows if row.get("uncertainty_transfer_ratio") is None])[:20],
        "top_supplier_relative_factors": (supplier_relative_rows or relative_primary_rows)[:20],
        "top_supplier_absolute_factors": (supplier_absolute_rows or absolute_primary_rows)[:20],
        "research_control_factors": research_control_rows[:20],
        "all_top_factors": all_rows[:20],
        "families": families[:12],
    }


def _top_run_extremes_payload(
    summary: dict[str, Any],
    rows: list[dict[str, str]],
    distributions: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    named_groups = _build_extreme_runs(summary)
    distribution_rows = _distribution_rows(rows)
    by_kpi: dict[str, dict[str, list[dict[str, Any]]]] = {}
    for metric in _kpi_order(distributions.keys()):
        values: list[dict[str, Any]] = []
        for row in distribution_rows:
            value = _to_float(row.get(metric))
            if math.isnan(value):
                continue
            values.append(
                {
                    "run_id": str(row.get("run_id") or ""),
                    "value": value,
                    "is_baseline": _boolish(row.get("is_baseline")),
                }
            )
        if not values:
            continue
        values.sort(key=lambda row: float(row["value"]))
        by_kpi[metric] = {
            "lowest": values[:5],
            "highest": list(reversed(values[-5:])),
        }
    return {
        "source": "montecarlo_samples.csv" if by_kpi else ("summary.top_runs" if named_groups else "missing"),
        "by_kpi": by_kpi,
        "named_groups": named_groups,
    }


def _trajectory_final_distributions_payload(trajectories_json: Path) -> dict[str, Any]:
    payload = _load_json(trajectories_json)
    if not payload:
        return {"available": False, "metrics": {}}
    days = payload.get("days") if isinstance(payload.get("days"), list) else []
    metrics = payload.get("metrics") if isinstance(payload.get("metrics"), dict) else {}
    metric_rows: dict[str, Any] = {}
    for metric_name, metric in metrics.items():
        if not isinstance(metric, dict):
            continue
        bands = metric.get("bands") if isinstance(metric.get("bands"), dict) else {}
        final = {}
        for band_name, values in bands.items():
            if isinstance(values, list) and values:
                final[str(band_name)] = _finite_number(values[-1])
        metric_rows[str(metric_name)] = {
            "label": metric.get("label", metric_name),
            "y_label": metric.get("y_label"),
            "reference_value": _finite_number(metric.get("reference_value")),
            "series_total_count": _coalesce_int(metric.get("series_total_count")),
            "series_display_count": _coalesce_int(metric.get("series_display_count")),
            "final": final,
        }
    return {
        "available": True,
        "run_count": _coalesce_int(payload.get("run_count")),
        "stochastic_run_count": _coalesce_int(payload.get("stochastic_run_count")),
        "final_day": _finite_number(days[-1]) if days else None,
        "metrics": metric_rows,
    }


def _format_number(value: Any) -> str:
    number = _to_float(value)
    if math.isnan(number):
        return "n/a"
    if abs(number) >= 1_000_000:
        return f"{number / 1_000_000:.2f}M"
    if abs(number) >= 1_000:
        return f"{number / 1_000:.1f}k"
    return f"{number:.3g}"


def _format_probability(value: Any) -> str:
    number = _to_float(value)
    if math.isnan(number):
        return "n/a"
    return f"{number * 100.0:.1f}%"


def _format_kpi(metric: str, value: Any) -> str:
    if metric == "kpi::fill_rate":
        return _format_probability(value)
    return _format_number(value)


def _ui_summary_payload(
    meta: dict[str, Any],
    distributions: dict[str, dict[str, Any]],
    decision_metrics: dict[str, Any],
    driver_rankings: dict[str, Any],
    correlated_factors: dict[str, Any],
) -> dict[str, Any]:
    headline = "{success}/{total} runs ok, profile {profile}, {failed} failed.".format(
        success=meta.get("successful_runs"),
        total=meta.get("runs_total"),
        profile=meta.get("profile"),
        failed=meta.get("failed_runs"),
    )
    bullets = []
    fill = distributions.get("kpi::fill_rate")
    if fill:
        bullets.append(
            "Fill rate final p50={p50}, p05={p05}, baseline={baseline}.".format(
                p50=_format_kpi("kpi::fill_rate", fill.get("p50")),
                p05=_format_kpi("kpi::fill_rate", fill.get("p05")),
                baseline=_format_kpi("kpi::fill_rate", fill.get("baseline")),
            )
        )
    cost = distributions.get("kpi::total_cost")
    if cost:
        bullets.append(
            "Total cost final p50={p50}, p95={p95}.".format(
                p50=_format_kpi("kpi::total_cost", cost.get("p50")),
                p95=_format_kpi("kpi::total_cost", cost.get("p95")),
            )
        )
    probability_items = [
        (key, value)
        for key, value in decision_metrics.items()
        if not math.isnan(_to_float(value)) and 0.0 <= _to_float(value) <= 1.0
    ]
    if probability_items:
        key, value = max(probability_items, key=lambda item: _to_float(item[1]))
        bullets.append(f"Main decision signal: {key}={_format_probability(value)}.")
    top_driver = None
    for source in [driver_rankings, correlated_factors]:
        entries = (source.get("by_kpi") or {}).get("kpi::fill_rate")
        if isinstance(entries, list) and entries:
            top_driver = entries[0]
            break
    if top_driver:
        bullets.append(
            "Top fill_rate driver: {factor} (corr={corr}).".format(
                factor=top_driver.get("factor"),
                corr=_format_number(top_driver.get("correlation")),
            )
        )
    fill_below_99 = _to_float(decision_metrics.get("fill_rate_below_99pct"))
    backlog_positive = _to_float(decision_metrics.get("backlog_positive"))
    if (not math.isnan(fill_below_99) and fill_below_99 >= 0.25) or (
        not math.isnan(backlog_positive) and backlog_positive >= 0.25
    ):
        severity = "high"
    elif fill and _to_float(fill.get("p05")) < 0.99:
        severity = "medium"
    else:
        severity = "low"
    return {
        "headline": headline,
        "bullets": bullets[:4],
        "severity": severity,
        "primary_kpi": "kpi::fill_rate" if fill else next(iter(distributions), None),
    }


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, tuple):
        return [_json_safe(item) for item in value]
    if isinstance(value, bool) or value is None or isinstance(value, str):
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, Path):
        return str(value)
    return str(value)


def build_uncertainty_diagnostics(summary_json: Path) -> dict[str, Any]:
    """Build JSON-serializable uncertainty diagnostics from Monte Carlo files."""

    summary_json = Path(summary_json)
    summary = _load_json(summary_json)
    if not summary:
        return {
            "schema_version": "etudecas.uncertainty_diagnostics.v1",
            "available": False,
            "summary_json": str(summary_json),
            "error": "summary_json_missing_or_invalid",
        }

    samples_csv = summary_json.with_name("montecarlo_samples.csv")
    trajectories_json = summary_json.with_name("montecarlo_trajectories.json")
    rows = _read_samples(samples_csv)
    stochastic_rows = _ok_stochastic_rows(rows)
    drivers_by_kpi, factor_families, supplier_impacts = _build_drivers(summary)
    suite = _suite_assessment(summary_json)
    profile = str(summary.get("uncertainty_profile") or "n/a")
    suite_status = str(suite.get("status") or "")
    interpretation = "stress_non_probabiliste" if profile in {"stress_probe", "breakpoint_probe"} else "incertitude_operationnelle"
    if suite_status == "too_extreme":
        interpretation = "stress_tres_severe"

    ok_rows = _ok_rows(rows)
    failed_rows = [row for row in rows if row not in ok_rows]
    distributions = _kpi_final_distributions(summary, rows)
    decision_metrics = _decision_metrics_payload(summary, rows)
    driver_rankings = _driver_rankings_payload(drivers_by_kpi)
    correlated_factors = _correlated_factors_payload(summary, rows, driver_rankings.get("by_kpi") or {})
    top_run_extremes = _top_run_extremes_payload(summary, rows, distributions)
    trajectory_final_distributions = _trajectory_final_distributions_payload(trajectories_json)
    uncertainty_propagation = _build_uncertainty_propagation(rows, input_relative_uncertainty=0.20)
    meta = {
        "profile": profile,
        "uncertainty_profile": profile,
        "interpretation": interpretation,
        "scenario_id": summary.get("scenario_id"),
        "seed": _finite_number(summary.get("seed")),
        "days": _finite_number(summary.get("days_override")),
        "days_override": _finite_number(summary.get("days_override")),
        "runs_requested": _coalesce_int(summary.get("runs_requested_excluding_baseline")),
        "runs_requested_excluding_baseline": _coalesce_int(summary.get("runs_requested_excluding_baseline")),
        "runs_total": _coalesce_int(summary.get("runs_total_including_baseline"), len(rows) if rows else None),
        "runs_total_including_baseline": _coalesce_int(
            summary.get("runs_total_including_baseline"),
            len(rows) if rows else None,
        ),
        "successful_runs": _coalesce_int(summary.get("successful_runs"), len(ok_rows) if rows else None),
        "successful_stochastic_runs": _coalesce_int(
            summary.get("successful_stochastic_runs"),
            len(stochastic_rows) if rows else None,
        ),
        "failed_runs": _coalesce_int(summary.get("failed_runs"), len(failed_rows) if rows else None),
        "sample_rows": len(rows),
        "stochastic_sample_rows": len(stochastic_rows),
        "has_samples": samples_csv.exists(),
        "has_trajectories": trajectories_json.exists(),
        "generated_at_utc": summary.get("generated_at_utc"),
    }

    payload = {
        "schema_version": "etudecas.uncertainty_diagnostics.v1",
        "available": True,
        "summary_json": str(summary_json),
        "samples_csv": str(samples_csv),
        "trajectories_json": str(trajectories_json),
        "source_files": {
            "summary_json": str(summary_json),
            "samples_csv": str(samples_csv) if samples_csv.exists() else None,
            "trajectories_json": str(trajectories_json) if trajectories_json.exists() else None,
        },
        "meta": meta,
        "suite_assessment": suite,
        "decision_metrics": decision_metrics,
        "threshold_probabilities": _build_thresholds(summary, stochastic_rows),
        "kpi_distributions": _build_kpi_distributions(summary),
        "kpi_final_distributions": distributions,
        "drivers_by_kpi": drivers_by_kpi,
        "driver_rankings": driver_rankings,
        "correlated_factors_by_kpi": correlated_factors,
        "factor_family_impacts": factor_families,
        "supplier_impacts": supplier_impacts,
        "extreme_runs": _build_extreme_runs(summary),
        "top_run_extremes": top_run_extremes,
        "trajectory_summary": _build_trajectory_summary(trajectories_json),
        "trajectory_final_distributions": trajectory_final_distributions,
        "uncertainty_propagation": uncertainty_propagation,
        "ui_summary": _ui_summary_payload(
            meta,
            distributions,
            decision_metrics,
            driver_rankings,
            correlated_factors,
        ),
    }
    return _json_safe(payload)
