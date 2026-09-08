#!/usr/bin/env python3
"""Audit the calibration between MRP reference signals and physical use.

This module is deliberately read-only with respect to simulation artefacts.  It
does not invoke the engine and writes a compact, standalone package in a new
directory.  The audit distinguishes:

* the static MRP reference used to size a safety-time target;
* physical component consumption reconstructed from plant stock movements;
* stock available before production at J0 and at the incident cut-off;
* fixed replenishment lots and receipts;
* BOM consumption evidenced by released production-lot genealogy.

It is an audit of a simulated baseline, not evidence of industrial resilience
or of a supplier occurrence probability.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import html
import json
import math
import os
import shutil
import statistics
import tempfile
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


SCHEMA_VERSION = "etudecas.supplier_stock_signal_calibration_audit.v1"
EXPECTED_DAYS = 720
DEFAULT_SEEDS = tuple(range(340282, 340297))
FOCUS_KEYS = (("M-1430", "item:038005"), ("M-1810", "item:049371"))
FOCUS_INCIDENT_START_DAY = 60
FOCUS_INCIDENT_DURATION_DAYS = 180

RESULT_JSON = "audit_calibration_stock_signal.json"
SUMMARY_CSV = "materiaux_calibration_synthese.csv"
DETAIL_CSV = "materiaux_calibration_15_simulations.csv"
RESULT_HTML = "AUDIT_CALIBRATION_STOCK_SIGNAL.html"
MANIFEST_JSON = "manifest_audit_calibration_stock_signal.json"
OUTPUT_FILES = (RESULT_JSON, SUMMARY_CSV, DETAIL_CSV, RESULT_HTML, MANIFEST_JSON)

SOURCE_FILES = (
    "reports/mrp_safety_stock_reference.csv",
    "data/production_input_stocks_daily.csv",
    "data/production_input_replenishment_arrivals_daily.csv",
    "data/mrp_trace_daily.csv",
    "data/production_lot_genealogy.csv",
    "data/production_campaigns.csv",
    "data/production_capacity_nominal_parameters.csv",
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _canonical_json_bytes(payload: Mapping[str, Any]) -> bytes:
    return (
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")


def _read_csv(path: Path) -> list[dict[str, str]]:
    if not path.is_file() or path.is_symlink():
        raise FileNotFoundError(f"Fichier source absent ou lien refusé: {path}")
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if not reader.fieldnames or len(reader.fieldnames) != len(set(reader.fieldnames)):
            raise ValueError(f"En-tête CSV absent ou dupliqué: {path}")
        return [dict(row) for row in reader]


def _float(value: Any, *, default: float = 0.0) -> float:
    if value in (None, ""):
        return default
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"Valeur non finie: {value!r}")
    return number


def _integer(value: Any) -> int:
    number = _float(value)
    if abs(number - round(number)) > 1e-9:
        raise ValueError(f"Entier attendu: {value!r}")
    return int(round(number))


def _safe_div(numerator: float, denominator: float) -> float | None:
    if abs(denominator) <= 1e-12:
        return None
    return numerator / denominator


def _r(value: float | None, digits: int = 6) -> float | None:
    return None if value is None else round(float(value), digits)


def _mean(values: Iterable[float | None]) -> float | None:
    kept = [float(value) for value in values if value is not None]
    return statistics.fmean(kept) if kept else None


def _range(values: Iterable[float | None]) -> tuple[float | None, float | None]:
    kept = [float(value) for value in values if value is not None]
    return (min(kept), max(kept)) if kept else (None, None)


def _key(row: Mapping[str, str]) -> tuple[str, str]:
    return str(row.get("node_id") or ""), str(row.get("item_id") or "")


def _require_days(
    rows: Sequence[Mapping[str, str]],
    *,
    context: str,
) -> dict[int, Mapping[str, str]]:
    by_day: dict[int, Mapping[str, str]] = {}
    for row in rows:
        day = _integer(row.get("day"))
        if day in by_day:
            raise ValueError(f"Jour dupliqué pour {context}: {day}")
        by_day[day] = row
    expected = set(range(EXPECTED_DAYS))
    if set(by_day) != expected:
        missing = sorted(expected - set(by_day))
        extra = sorted(set(by_day) - expected)
        raise ValueError(
            f"Série journalière incomplète pour {context}; "
            f"manquants={missing[:5]}, supplémentaires={extra[:5]}"
        )
    return by_day


def _seed_run_dir(runner_dir: Path, seed: int) -> Path:
    result = (
        runner_dir
        / "cases"
        / "baseline"
        / f"baseline_metrics__seed_{seed}"
        / f"seed_{seed}"
    )
    if not result.is_dir() or result.is_symlink():
        raise FileNotFoundError(f"Baseline détaillée absente pour la simulation {seed}: {result}")
    return result.resolve(strict=True)


def _index_rows(
    rows: Sequence[dict[str, str]],
    keys: set[tuple[str, str]],
) -> dict[tuple[str, str], list[dict[str, str]]]:
    result: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        key = _key(row)
        if key in keys:
            result[key].append(row)
    return result


def _read_one_seed(runner_dir: Path, seed: int) -> tuple[list[dict[str, Any]], dict[str, str]]:
    run_dir = _seed_run_dir(runner_dir, seed)
    paths = {relative: run_dir / Path(relative) for relative in SOURCE_FILES}
    hashes = {relative: _sha256(path) for relative, path in paths.items()}

    safety_rows = [
        row
        for row in _read_csv(paths["reports/mrp_safety_stock_reference.csv"])
        if row.get("scope") == "input_material"
    ]
    safety_by_key: dict[tuple[str, str], dict[str, str]] = {}
    for row in safety_rows:
        key = _key(row)
        if not all(key) or key in safety_by_key:
            raise ValueError(f"Clé matière absente ou dupliquée, simulation {seed}: {key}")
        safety_by_key[key] = row
    if not safety_by_key:
        raise ValueError(f"Aucune matière d'entrée, simulation {seed}")
    keys = set(safety_by_key)

    stocks = _index_rows(
        _read_csv(paths["data/production_input_stocks_daily.csv"]), keys
    )
    arrivals = _index_rows(
        _read_csv(paths["data/production_input_replenishment_arrivals_daily.csv"]),
        keys,
    )
    traces = _index_rows(_read_csv(paths["data/mrp_trace_daily.csv"]), keys)

    genealogy_by_key_campaign: dict[
        tuple[str, str], dict[str, dict[str, Any]]
    ] = defaultdict(dict)
    for row in _read_csv(paths["data/production_lot_genealogy.csv"]):
        if row.get("link_type") != "production":
            continue
        key = (str(row.get("parent_node_id") or ""), str(row.get("parent_item_id") or ""))
        if key not in keys:
            continue
        day = _integer(row.get("day"))
        if not 0 <= day < EXPECTED_DAYS:
            continue
        campaign_id = str(row.get("production_campaign_id") or "")
        if not campaign_id:
            raise ValueError(f"Campagne absente dans la généalogie, simulation {seed}, {key}")
        entry = genealogy_by_key_campaign[key].setdefault(
            campaign_id,
            {
                "component_qty": 0.0,
                "output_qty": None,
                "output_node_id": str(row.get("child_node_id") or ""),
                "output_item_id": str(row.get("child_item_id") or ""),
            },
        )
        child_qty = _float(row.get("child_qty"))
        if entry["output_qty"] is not None and not math.isclose(
            float(entry["output_qty"]), child_qty, rel_tol=0.0, abs_tol=1e-5
        ):
            raise ValueError(f"Quantité produite incohérente dans {campaign_id}")
        entry["output_qty"] = child_qty
        entry["component_qty"] += _float(row.get("parent_qty"))

    campaign_rows = {
        str(row.get("campaign_id") or ""): row
        for row in _read_csv(paths["data/production_campaigns.csv"])
        if row.get("campaign_id")
    }
    capacity_by_output = {
        (str(row.get("node_id") or ""), str(row.get("output_item_id") or "")): row
        for row in _read_csv(paths["data/production_capacity_nominal_parameters.csv"])
    }

    details: list[dict[str, Any]] = []
    for key in sorted(keys):
        safety = safety_by_key[key]
        stock_days = _require_days(stocks.get(key, []), context=f"stock {seed} {key}")
        arrival_days = _require_days(
            arrivals.get(key, []), context=f"arrivages {seed} {key}"
        )
        trace_days = _require_days(traces.get(key, []), context=f"MRP {seed} {key}")

        consumption_daily: list[float] = []
        for day, row in stock_days.items():
            consumed = _float(row.get("stock_before_production")) - _float(
                row.get("stock_end_of_day")
            )
            if consumed < -1e-5:
                raise ValueError(f"Consommation négative reconstruite: simulation {seed}, {key}, J{day}")
            consumption_daily.append(max(0.0, consumed))
        physical_total = sum(consumption_daily)
        physical_daily = physical_total / EXPECTED_DAYS

        observed_report = _float(safety.get("observed_avg_daily_flow_qty"))
        if not math.isclose(
            physical_daily, observed_report, rel_tol=1e-7, abs_tol=2e-5
        ):
            raise ValueError(
                f"Flux physique et rapport MRP non réconciliés: simulation {seed}, {key}, "
                f"{physical_daily} != {observed_report}"
            )

        target_signals = [_float(row.get("target_demand_signal_qty")) for row in trace_days.values()]
        soft_targets = [_float(row.get("soft_safety_target_qty")) for row in trace_days.values()]
        raw_signals = [_float(row.get("bb_demand_signal_raw_qty")) for row in trace_days.values()]
        target_basis = sorted({str(row.get("gross_requirement_basis") or "") for row in trace_days.values()})
        safety_time = _float(safety.get("safety_time_days"))
        explicit_safety = _float(safety.get("explicit_safety_stock_qty"))
        reference_daily = _float(safety.get("planned_avg_daily_demand_qty"))
        stock_equiv_safety_time = _float(safety.get("stock_equiv_safety_time_qty"))
        reference_stock = _float(safety.get("effective_reference_stock_qty"))
        expected_stock_equiv = safety_time * reference_daily
        if not math.isclose(
            stock_equiv_safety_time, expected_stock_equiv, rel_tol=1e-7, abs_tol=2e-4
        ):
            raise ValueError(
                f"Équivalent temps de sécurité non réconcilié: simulation {seed}, {key}, "
                f"{stock_equiv_safety_time} != {expected_stock_equiv}"
            )
        if not math.isclose(
            reference_stock,
            statistics.fmean(soft_targets),
            rel_tol=1e-7,
            abs_tol=2e-4,
        ):
            raise ValueError(
                f"Cible de sécurité effective non réconciliée: simulation {seed}, {key}"
            )
        effective_safety_rate = (
            reference_stock / safety_time if safety_time > 1e-12 else None
        )

        positive_arrivals = [
            _float(row.get("arrived_qty"))
            for row in arrival_days.values()
            if _float(row.get("arrived_qty")) > 1e-12
        ]
        j0_stock = _float(stock_days[0].get("stock_before_production"))
        preincident_stock = _float(
            stock_days[FOCUS_INCIDENT_START_DAY - 1].get("stock_end_of_day")
        )
        cutoff_stock = _float(
            stock_days[FOCUS_INCIDENT_START_DAY].get("stock_before_production")
        )
        incident_window_consumption = sum(
            consumption_daily[
                FOCUS_INCIDENT_START_DAY : FOCUS_INCIDENT_START_DAY
                + FOCUS_INCIDENT_DURATION_DAYS
            ]
        )
        preincident_margin = preincident_stock - incident_window_consumption
        final_stock = _float(stock_days[EXPECTED_DAYS - 1].get("stock_end_of_day"))
        j0_pipeline = _float(trace_days[0].get("recv_prev_future_qty"))
        j0_inventory_position = _float(trace_days[0].get("inventory_position_qty"))

        campaigns = genealogy_by_key_campaign.get(key, {})
        genealogy_available = bool(campaigns)
        output_pairs = sorted(
            {
                (str(value["output_node_id"]), str(value["output_item_id"]))
                for value in campaigns.values()
            }
        )
        if not output_pairs:
            output_pairs = sorted(
                pair
                for pair, capacity in capacity_by_output.items()
                if pair[0] == key[0]
                and _float(capacity.get("current_capacity_qty_per_day")) > 1e-12
            )
        relevant_campaign_rows = [
            row
            for row in campaign_rows.values()
            if (str(row.get("node_id") or ""), str(row.get("output_item_id") or ""))
            in output_pairs
        ]
        campaign_actual_qty = sum(
            _float(row.get("actual_qty")) for row in relevant_campaign_rows
        )
        genealogy_consumption: float | None = None
        genealogy_output: float | None = None
        coefficients: list[float] = []
        if genealogy_available:
            genealogy_consumption = sum(
                float(value["component_qty"]) for value in campaigns.values()
            )
            genealogy_output = sum(
                float(value["output_qty"] or 0.0) for value in campaigns.values()
            )
            coefficients = [
                float(value["component_qty"]) / float(value["output_qty"])
                for value in campaigns.values()
                if float(value["output_qty"] or 0.0) > 1e-12
            ]
            missing_campaigns = sorted(set(campaigns) - set(campaign_rows))
            if missing_campaigns:
                raise ValueError(
                    f"Campagnes généalogiques absentes du bilan: {missing_campaigns[:3]}"
                )
            if not math.isclose(
                genealogy_output, campaign_actual_qty, rel_tol=1e-7, abs_tol=2e-3
            ):
                raise ValueError(
                    f"Production et généalogie non réconciliées: simulation {seed}, {key}"
                )
            if not math.isclose(
                genealogy_consumption, physical_total, rel_tol=1e-7, abs_tol=2e-3
            ):
                raise ValueError(
                    f"Consommation stock et nomenclature non réconciliées: simulation {seed}, {key}, "
                    f"écart={genealogy_consumption - physical_total}"
                )
        elif len(output_pairs) == 1 and campaign_actual_qty > 1e-12:
            # The campaign outputs and stock movements remain available in every
            # baseline.  Their ratio is a realised component coefficient, but
            # only the trace-enabled seed provides direct lot-level BOM proof.
            coefficients = [physical_total / campaign_actual_qty]

        process_capacity = None
        if len(output_pairs) == 1:
            capacity = capacity_by_output.get(output_pairs[0])
            if capacity is not None:
                process_capacity = _float(capacity.get("current_capacity_qty_per_day"))
        capacity_bom_rate = (
            process_capacity * statistics.fmean(coefficients)
            if process_capacity is not None and coefficients
            else None
        )
        static_formula_verified = (
            genealogy_available
            and target_basis == ["static_requirement_override"]
            and capacity_bom_rate is not None
            and math.isclose(
                reference_daily,
                capacity_bom_rate,
                rel_tol=1e-6,
                abs_tol=2e-4,
            )
        )

        details.append(
            {
                "seed": seed,
                "node_id": key[0],
                "item_id": key[1],
                "uom": str(safety.get("uom") or ""),
                "safety_time_days": _r(safety_time),
                "mrp_reference_demand_qty_per_day": _r(reference_daily),
                "mrp_reference_basis": str(safety.get("safety_reference_basis") or ""),
                "mrp_gross_requirement_basis": ";".join(target_basis),
                "mrp_target_signal_min_qty_per_day": _r(min(target_signals)),
                "mrp_target_signal_max_qty_per_day": _r(max(target_signals)),
                "mrp_raw_signal_avg_qty_per_day": _r(statistics.fmean(raw_signals)),
                "physical_consumption_total_qty": _r(physical_total),
                "physical_consumption_avg_qty_per_calendar_day": _r(physical_daily),
                "physical_consumption_active_days": sum(value > 1e-12 for value in consumption_daily),
                "physical_consumption_max_qty_per_day": _r(max(consumption_daily)),
                "mrp_reference_to_physical_rate_ratio": _r(
                    _safe_div(reference_daily, physical_daily)
                ),
                "safety_target_rate_qty_per_day": _r(effective_safety_rate),
                "safety_target_rate_to_physical_ratio": _r(
                    _safe_div(effective_safety_rate or 0.0, physical_daily)
                    if effective_safety_rate is not None
                    else None
                ),
                "mrp_raw_to_physical_rate_ratio": _r(
                    _safe_div(statistics.fmean(raw_signals), physical_daily)
                ),
                "explicit_safety_stock_qty": _r(explicit_safety),
                "effective_reference_stock_qty": _r(reference_stock),
                "reference_stock_cover_physical_days": _r(
                    _safe_div(reference_stock, physical_daily)
                ),
                "stock_j0_before_production_qty": _r(j0_stock),
                "stock_j0_cover_physical_days": _r(_safe_div(j0_stock, physical_daily)),
                "pipeline_j0_qty": _r(j0_pipeline),
                "inventory_position_j0_qty": _r(j0_inventory_position),
                "inventory_position_j0_cover_physical_days": _r(
                    _safe_div(j0_inventory_position, physical_daily)
                ),
                "stock_before_production_j60_qty": _r(cutoff_stock),
                "stock_j60_cover_physical_days": _r(
                    _safe_div(cutoff_stock, physical_daily)
                ),
                "stock_end_j59_preincident_qty": _r(preincident_stock),
                "incident_window_baseline_consumption_qty": _r(
                    incident_window_consumption
                ),
                "preincident_stock_minus_window_consumption_qty": _r(
                    preincident_margin
                ),
                "preincident_stock_to_window_consumption_ratio": _r(
                    _safe_div(preincident_stock, incident_window_consumption)
                ),
                "preincident_stock_covers_window_without_arrivals": (
                    preincident_margin >= -1e-6
                ),
                "stock_final_qty": _r(final_stock),
                "stock_min_end_of_day_qty": _r(
                    min(_float(row.get("stock_end_of_day")) for row in stock_days.values())
                ),
                "stock_zero_days": sum(
                    _float(row.get("stock_end_of_day")) <= 1e-9
                    for row in stock_days.values()
                ),
                "arrival_total_qty": _r(sum(positive_arrivals)),
                "arrival_positive_days": len(positive_arrivals),
                "arrival_lot_min_qty": _r(min(positive_arrivals) if positive_arrivals else None),
                "arrival_lot_median_qty": _r(
                    statistics.median(positive_arrivals) if positive_arrivals else None
                ),
                "arrival_lot_max_qty": _r(max(positive_arrivals) if positive_arrivals else None),
                "production_campaign_count": len(relevant_campaign_rows),
                "production_output_pairs": ";".join(f"{a}|{b}" for a, b in output_pairs),
                "production_output_total_qty": _r(campaign_actual_qty),
                "bom_evidence_mode": (
                    "direct_released_lot_genealogy"
                    if genealogy_available
                    else "stock_consumption_divided_by_released_campaign_output"
                ),
                "bom_component_qty_per_output_min": _r(min(coefficients) if coefficients else None, 12),
                "bom_component_qty_per_output_max": _r(max(coefficients) if coefficients else None, 12),
                "process_capacity_output_qty_per_day": _r(process_capacity),
                "capacity_times_bom_component_rate_qty_per_day": _r(
                    capacity_bom_rate
                ),
                "mrp_reference_vs_capacity_bom_abs_difference_qty_per_day": _r(
                    abs(reference_daily - capacity_bom_rate)
                    if capacity_bom_rate is not None
                    else None
                ),
                "static_capacity_bom_formula_verified": static_formula_verified,
                "process_calendar_utilization_ratio": _r(
                    _safe_div(campaign_actual_qty / EXPECTED_DAYS, process_capacity or 0.0)
                ),
                "stock_consumption_vs_genealogy_abs_difference_qty": _r(
                    abs(physical_total - genealogy_consumption)
                    if genealogy_consumption is not None
                    else None
                ),
            }
        )
    return details, hashes


def _status(row: Mapping[str, Any]) -> tuple[str, str]:
    physical = row.get("physical_consumption_avg_qty_per_calendar_day_mean")
    safety_days = row.get("safety_time_days_mean")
    ratio = row.get("safety_target_rate_to_physical_ratio_mean")
    if physical is None or float(physical) <= 1e-12:
        return (
            "non_evaluable_flux_physique_nul",
            "Aucune consommation physique dans l'horizon; le nombre de jours de couverture n'est pas calculable.",
        )
    if safety_days is None or float(safety_days) <= 1e-12:
        return (
            "sans_cible_de_securite_en_jours",
            "Aucune cible de sécurité exprimée en jours pour cette matière.",
        )
    if ratio is not None and float(ratio) >= 10.0:
        return (
            "ecart_majeur_de_calibration",
            "Le besoin MRP de référence dépasse d'au moins dix fois le flux physique simulé; la protection apparente est dominée par le réglage du modèle.",
        )
    if ratio is not None and (float(ratio) >= 2.0 or float(ratio) <= 0.5):
        return (
            "ecart_de_calibration_a_instruire",
            "Le besoin MRP et le flux physique diffèrent d'au moins un facteur deux; la cible doit être recalée avant lecture métier.",
        )
    return (
        "ordre_de_grandeur_proche_a_valider",
        "Les ordres de grandeur sont proches, mais cela ne vaut pas validation sur données industrielles.",
    )


def _summarize(details: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str], list[Mapping[str, Any]]] = defaultdict(list)
    for row in details:
        grouped[(str(row["node_id"]), str(row["item_id"]))].append(row)
    summaries: list[dict[str, Any]] = []
    numeric_fields = (
        "safety_time_days",
        "mrp_reference_demand_qty_per_day",
        "mrp_raw_signal_avg_qty_per_day",
        "physical_consumption_total_qty",
        "physical_consumption_avg_qty_per_calendar_day",
        "physical_consumption_active_days",
        "mrp_reference_to_physical_rate_ratio",
        "safety_target_rate_qty_per_day",
        "safety_target_rate_to_physical_ratio",
        "mrp_raw_to_physical_rate_ratio",
        "effective_reference_stock_qty",
        "reference_stock_cover_physical_days",
        "stock_j0_before_production_qty",
        "stock_j0_cover_physical_days",
        "pipeline_j0_qty",
        "inventory_position_j0_qty",
        "inventory_position_j0_cover_physical_days",
        "stock_before_production_j60_qty",
        "stock_j60_cover_physical_days",
        "stock_end_j59_preincident_qty",
        "incident_window_baseline_consumption_qty",
        "preincident_stock_minus_window_consumption_qty",
        "preincident_stock_to_window_consumption_ratio",
        "stock_final_qty",
        "stock_min_end_of_day_qty",
        "stock_zero_days",
        "arrival_total_qty",
        "arrival_positive_days",
        "arrival_lot_min_qty",
        "arrival_lot_median_qty",
        "arrival_lot_max_qty",
        "production_campaign_count",
        "production_output_total_qty",
        "bom_component_qty_per_output_min",
        "bom_component_qty_per_output_max",
        "process_capacity_output_qty_per_day",
        "capacity_times_bom_component_rate_qty_per_day",
        "mrp_reference_vs_capacity_bom_abs_difference_qty_per_day",
        "process_calendar_utilization_ratio",
        "stock_consumption_vs_genealogy_abs_difference_qty",
    )
    for key, rows in sorted(grouped.items()):
        first = rows[0]
        result: dict[str, Any] = {
            "node_id": key[0],
            "item_id": key[1],
            "uom": first["uom"],
            "simulation_count": len(rows),
            "seed_min": min(int(row["seed"]) for row in rows),
            "seed_max": max(int(row["seed"]) for row in rows),
            "mrp_gross_requirement_basis": ";".join(
                sorted({str(row["mrp_gross_requirement_basis"]) for row in rows})
            ),
            "production_output_pairs": ";".join(
                sorted({str(row["production_output_pairs"]) for row in rows})
            ),
            "bom_evidence_modes": ";".join(
                sorted({str(row["bom_evidence_mode"]) for row in rows})
            ),
        }
        for field in numeric_fields:
            values = [row.get(field) for row in rows]
            low, high = _range(values)
            result[f"{field}_mean"] = _r(_mean(values))
            result[f"{field}_min"] = _r(low)
            result[f"{field}_max"] = _r(high)
        result["preincident_stock_covers_window_simulation_count"] = sum(
            bool(row["preincident_stock_covers_window_without_arrivals"])
            for row in rows
        )
        result["static_capacity_bom_formula_verified_simulation_count"] = sum(
            bool(row["static_capacity_bom_formula_verified"]) for row in rows
        )
        status, interpretation = _status(result)
        result["calibration_status"] = status
        result["interpretation"] = interpretation
        summaries.append(result)
    return summaries


def _write_csv(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    if not rows:
        raise ValueError(f"Aucune ligne à écrire dans {path.name}")
    fields = list(rows[0])
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="raise")
        writer.writeheader()
        writer.writerows(rows)


def _fmt(value: Any, digits: int = 1) -> str:
    if value is None or value == "":
        return "non calculable"
    if isinstance(value, (int, float)):
        return f"{float(value):,.{digits}f}".replace(",", " ").replace(".", ",")
    return str(value)


def _render_html(payload: Mapping[str, Any]) -> str:
    summaries = list(payload["material_summary"])
    focus = list(payload["focus"])
    focus_rows = "".join(
        "<tr>"
        f"<td>{html.escape(str(row['item_id']).replace('item:', ''))}</td>"
        f"<td>{html.escape(str(row['node_id']))}</td>"
        f"<td>{_fmt(row['safety_time_days_mean'], 0)} j</td>"
        f"<td>{_fmt(row['mrp_reference_demand_qty_per_day_mean'], 2)} {html.escape(str(row['uom']))}/j</td>"
        f"<td>{_fmt(row['physical_consumption_avg_qty_per_calendar_day_mean'], 2)} {html.escape(str(row['uom']))}/j</td>"
        f"<td>×{_fmt(row['safety_target_rate_to_physical_ratio_mean'], 2)}</td>"
        f"<td><strong>{_fmt(row['reference_stock_cover_physical_days_mean'], 1)} j</strong></td>"
        f"<td>{_fmt(row['stock_j60_cover_physical_days_mean'], 1)} j</td>"
        f"<td>+{_fmt(row['preincident_stock_minus_window_consumption_qty_mean'], 0)} {html.escape(str(row['uom']))} ({int(row['preincident_stock_covers_window_simulation_count'])}/{int(row['simulation_count'])})</td>"
        f"<td>{_fmt(row['arrival_lot_median_qty_mean'], 0)} {html.escape(str(row['uom']))}</td>"
        "</tr>"
        for row in focus
    )
    all_rows = "".join(
        "<tr>"
        f"<td>{html.escape(str(row['node_id']))}</td>"
        f"<td>{html.escape(str(row['item_id']).replace('item:', ''))}</td>"
        f"<td>{_fmt(row['safety_time_days_mean'], 0)}</td>"
        f"<td>{_fmt(row['physical_consumption_avg_qty_per_calendar_day_mean'], 2)}</td>"
        f"<td>{_fmt(row['safety_target_rate_to_physical_ratio_mean'], 2)}</td>"
        f"<td>{_fmt(row['reference_stock_cover_physical_days_mean'], 1)}</td>"
        f"<td>{_fmt(row['stock_j0_cover_physical_days_mean'], 1)}</td>"
        f"<td>{_fmt(row['stock_zero_days_mean'], 1)}</td>"
        f"<td>{html.escape(str(row['calibration_status']).replace('_', ' '))}</td>"
        "</tr>"
        for row in summaries
    )
    status_counts = payload["status_counts"]
    return f"""<!doctype html>
<html lang="fr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Audit de calibration stock / besoin MRP</title>
<style>
:root{{--ink:#10233f;--muted:#586a82;--line:#dce5f0;--blue:#0b67d1;--warn:#b44719;--bg:#f3f7fb}}
*{{box-sizing:border-box}} body{{margin:0;background:var(--bg);color:var(--ink);font:16px/1.48 system-ui,-apple-system,Segoe UI,sans-serif}}
main{{max-width:1320px;margin:auto;padding:28px}} section{{background:white;border:1px solid var(--line);border-radius:16px;padding:22px;margin:16px 0;box-shadow:0 8px 28px #17385b12}}
h1{{font-size:30px;margin:0 0 8px}} h2{{font-size:21px;margin:0 0 12px}} p{{margin:8px 0}} .lead{{font-size:18px}} .tag{{display:inline-block;padding:5px 10px;border-radius:99px;background:#e8f2ff;color:#064b99;font-weight:700;font-size:13px}}
.alert{{border-left:5px solid var(--warn);background:#fff4ed;padding:14px 16px;margin:14px 0}} .cards{{display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:12px}} .card{{background:#f7faff;border:1px solid var(--line);border-radius:12px;padding:14px}} .big{{font-size:25px;font-weight:800;color:var(--blue)}}
.table-wrap{{overflow:auto}} table{{border-collapse:collapse;width:100%;font-size:14px}} th,td{{text-align:left;border-bottom:1px solid var(--line);padding:9px 10px;white-space:nowrap}} th{{background:#eef4fb;position:sticky;top:0}} small,.muted{{color:var(--muted)}} code{{background:#edf2f7;padding:2px 5px;border-radius:4px}}
</style></head><body><main>
<span class="tag">SIMULÉ — audit de calibration</span>
<h1>Les « jours de stock » ne mesurent pas ici la consommation réellement simulée</h1>
<p class="lead">Le moteur multiplie, pour certaines matières, un besoin calculé à la capacité maximale du procédé par le nombre de jours de sécurité. La production réellement exécutée est beaucoup plus faible : la couverture physique devient alors très supérieure à son libellé.</p>
<div class="alert"><strong>Lecture métier :</strong> l'absence d'effet d'un incident sur 038005 ou 049371 ne démontre pas que la chaîne industrielle résisterait. Dans cette configuration, le stock et les arrivages simulés masquent l'incident parce que le besoin de référence est surdimensionné par rapport à la consommation produite par le même modèle.</div>
<section><h2>Deux matières qui expliquent le constat</h2>
<div class="table-wrap"><table><thead><tr><th>Matière</th><th>Usine</th><th>Libellé</th><th>Besoin MRP</th><th>Consommation physique</th><th>Écart</th><th>Couverture réelle de la cible</th><th>Stock au début de l'incident</th><th>Marge sur 180 j sans nouvel arrivage</th><th>Lot reçu</th></tr></thead><tbody>{focus_rows}</tbody></table></div>
<p class="muted">Le « début de l'incident » correspond ici à J{FOCUS_INCIDENT_START_DAY}. La fenêtre de comparaison de {FOCUS_INCIDENT_DURATION_DAYS} jours est une hypothèse de scénario, pas une durée observée.</p></section>
<section><h2>Ce qui est vérifié</h2><div class="cards">
<div class="card"><div class="big">{payload['simulation_count']}</div>simulations de référence indépendantes</div>
<div class="card"><div class="big">{payload['material_count']}</div>couples usine–matière analysés</div>
<div class="card"><div class="big">{status_counts.get('ecart_majeur_de_calibration', 0)}</div>écarts majeurs (facteur ≥ 10)</div>
<div class="card"><div class="big">{payload['static_capacity_bom_formula_verified_material_count']}</div>besoins statiques égaux à capacité × nomenclature</div>
<div class="card"><div class="big">{payload['lot_genealogy_simulation_count']}</div>simulation avec généalogie directe des lots</div>
</div>
<p>La consommation physique est reconstruite chaque jour par <code>stock avant production − stock de fin de journée</code>. La simulation 340282, seule exécutée avec la généalogie détaillée des lots dans ce lot de calcul, la réconcilie directement avec les composants consommés et les campagnes libérées (écart maximal : {_fmt(payload['max_genealogy_tieout_abs_qty'], 4)}). Pour les quatorze autres, le coefficient réalisé est le rapport entre consommation de stock et production libérée : il confirme l'ordre de grandeur mais n'est pas une preuve lot par lot.</p></section>
<section><h2>Vue complète des matières</h2><div class="table-wrap"><table><thead><tr><th>Usine</th><th>Matière</th><th>Jours annoncés</th><th>Consommation/j</th><th>Besoin MRP / consommation</th><th>Couverture cible</th><th>Couverture stock J0</th><th>Jours à zéro</th><th>Diagnostic</th></tr></thead><tbody>{all_rows}</tbody></table></div></section>
<section><h2>À faire avant toute conclusion fournisseur</h2>
<p>Recalculer les besoins matière avec les ordres de fabrication et la demande réellement attendus, puis conserver séparément les contraintes de capacité maximale. Rejouer ensuite les incidents avec des stocks initiaux, des commandes ouvertes et des tailles de lots validés par l'industriel. Enfin, comparer les sorties recalées aux stocks et consommations observés en 2025.</p>
<p><strong>Limite :</strong> toutes les valeurs de cette page sont simulées. Elles ne sont ni une observation fournisseur, ni une probabilité d'incident, ni une recommandation de stock.</p></section>
<small>Paquet autonome, sans ressource externe — schéma {SCHEMA_VERSION}</small>
</main></body></html>"""


def build(runner_dir: Path, output_dir: Path, seeds: Sequence[int]) -> dict[str, Any]:
    runner_root = runner_dir.resolve(strict=True)
    if not runner_root.is_dir():
        raise NotADirectoryError(runner_root)
    chosen = tuple(int(seed) for seed in seeds)
    if not chosen or len(chosen) != len(set(chosen)):
        raise ValueError("Liste de simulations vide ou dupliquée")
    details: list[dict[str, Any]] = []
    sources: dict[str, Any] = {}
    for seed in chosen:
        seed_rows, seed_hashes = _read_one_seed(runner_root, seed)
        details.extend(seed_rows)
        sources[str(seed)] = seed_hashes
    summaries = _summarize(details)
    if any(int(row["simulation_count"]) != len(chosen) for row in summaries):
        raise ValueError("Périmètre matière non constant entre simulations")
    by_key = {(row["node_id"], row["item_id"]): row for row in summaries}
    missing_focus = [key for key in FOCUS_KEYS if key not in by_key]
    if missing_focus:
        raise ValueError(f"Matières prioritaires absentes: {missing_focus}")
    focus = [by_key[key] for key in FOCUS_KEYS]
    for row in focus:
        if row["calibration_status"] != "ecart_majeur_de_calibration":
            raise ValueError(f"Écart majeur attendu non confirmé: {row['item_id']}")
    status_counts = dict(Counter(str(row["calibration_status"]) for row in summaries))
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "scope": {
            "nature": "audit_additif_lecture_seule_de_baselines_simulees",
            "runner_dir": str(runner_root),
            "simulation_days": EXPECTED_DAYS,
            "seeds": list(chosen),
            "incident_comparison_hypothesis": {
                "start_day": FOCUS_INCIDENT_START_DAY,
                "duration_days": FOCUS_INCIDENT_DURATION_DAYS,
            },
        },
        "definitions": {
            "mrp_reference_demand": "besoin moyen indiqué dans le rapport MRP; pour les deux lignes prioritaires il est statique et porte static_requirement_override",
            "safety_target_rate": "cible de sécurité effective divisée par son nombre de jours; c'est le débit réellement implicite dans le stock cible",
            "physical_consumption": "somme journalière de stock_before_production moins stock_end_of_day, divisée par 720",
            "reference_stock_cover_physical_days": "cible de stock MRP divisée par la consommation physique moyenne simulée",
            "calibration_status": "contrôle d'ordre de grandeur; ce n'est ni une mesure de résilience ni un jugement fournisseur",
        },
        "screening_rules": {
            "major": "ratio débit implicite de la cible / consommation physique >= 10 et cible exprimée en jours",
            "to_investigate": "ratio du débit implicite >= 2 ou <= 0,5 et cible exprimée en jours",
            "warning": "seuils de contrôle transparents, non calibrés sur un historique industriel",
        },
        "simulation_count": len(chosen),
        "material_count": len(summaries),
        "status_counts": status_counts,
        "static_capacity_bom_formula_verified_material_count": sum(
            int(row["static_capacity_bom_formula_verified_simulation_count"]) > 0
            for row in summaries
        ),
        "lot_genealogy_simulation_count": len(
            {
                int(row["seed"])
                for row in details
                if row["bom_evidence_mode"] == "direct_released_lot_genealogy"
            }
        ),
        "max_genealogy_tieout_abs_qty": _r(
            max(
                float(row["stock_consumption_vs_genealogy_abs_difference_qty"])
                for row in details
                if row["stock_consumption_vs_genealogy_abs_difference_qty"] is not None
            )
        ),
        "focus": focus,
        "material_summary": summaries,
        "source_sha256": sources,
    }

    output = output_dir.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists():
        raise FileExistsError(f"Sortie déjà présente; aucun écrasement autorisé: {output}")
    temp = Path(tempfile.mkdtemp(prefix=f".{output.name}.", dir=output.parent))
    try:
        (temp / RESULT_JSON).write_bytes(_canonical_json_bytes(payload))
        _write_csv(temp / SUMMARY_CSV, summaries)
        _write_csv(temp / DETAIL_CSV, details)
        (temp / RESULT_HTML).write_text(_render_html(payload), encoding="utf-8")
        produced = (RESULT_JSON, SUMMARY_CSV, DETAIL_CSV, RESULT_HTML)
        manifest = {
            "schema_version": SCHEMA_VERSION,
            "status": "complete",
            "output_files": {
                name: {"size_bytes": (temp / name).stat().st_size, "sha256": _sha256(temp / name)}
                for name in produced
            },
            "source_runner_dir": str(runner_root),
            "source_files_mutated": False,
            "engine_invoked": False,
            "simulation_count": len(chosen),
            "material_count": len(summaries),
        }
        (temp / MANIFEST_JSON).write_bytes(_canonical_json_bytes(manifest))
        os.replace(temp, output)
    except Exception:
        shutil.rmtree(temp, ignore_errors=True)
        raise
    return payload


def validate(output_dir: Path) -> dict[str, Any]:
    output = output_dir.resolve(strict=True)
    manifest_path = output / MANIFEST_JSON
    if not manifest_path.is_file() or manifest_path.is_symlink():
        raise FileNotFoundError("Manifest de l'audit absent")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("schema_version") != SCHEMA_VERSION or manifest.get("status") != "complete":
        raise ValueError("Manifest de l'audit incompatible ou incomplet")
    if manifest.get("engine_invoked") is not False or manifest.get("source_files_mutated") is not False:
        raise ValueError("Garanties de lecture seule absentes")
    expected = set(OUTPUT_FILES[:-1])
    inventory = manifest.get("output_files")
    if not isinstance(inventory, dict) or set(inventory) != expected:
        raise ValueError("Inventaire de sortie inattendu")
    for name, evidence in inventory.items():
        path = output / name
        if not path.is_file() or path.is_symlink():
            raise FileNotFoundError(f"Sortie absente: {name}")
        if path.stat().st_size != int(evidence["size_bytes"]) or _sha256(path) != evidence["sha256"]:
            raise ValueError(f"Sortie modifiée après création: {name}")
    payload = json.loads((output / RESULT_JSON).read_text(encoding="utf-8"))
    if payload.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("Résultat JSON incompatible")
    return manifest


def _parse_seeds(value: str) -> tuple[int, ...]:
    result = tuple(int(token.strip()) for token in value.split(",") if token.strip())
    if not result:
        raise argparse.ArgumentTypeError("Au moins une simulation est requise")
    return result


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("build", "validate"), default="build")
    parser.add_argument("--runner-dir", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument(
        "--seeds",
        type=_parse_seeds,
        default=DEFAULT_SEEDS,
        help="Liste séparée par des virgules (défaut: les 15 simulations 340282 à 340296)",
    )
    args = parser.parse_args(argv)
    if args.mode == "build":
        if args.runner_dir is None:
            parser.error("--runner-dir est requis en mode build")
        payload = build(args.runner_dir, args.output_dir, args.seeds)
        print(
            json.dumps(
                {
                    "status": "complete",
                    "simulation_count": payload["simulation_count"],
                    "material_count": payload["material_count"],
                    "output_dir": str(args.output_dir.resolve()),
                },
                ensure_ascii=False,
            )
        )
    else:
        manifest = validate(args.output_dir)
        print(json.dumps(manifest, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
