#!/usr/bin/env python3
"""
Build an interactive HTML world map from a geocoded supply graph.

Includes two hover-panel modes:
- Simulation: current operational stock / production PNGs
- Sensitivity: low/base/high comparisons built from sensitivity case outputs
- Risk: supplier risk, uncertainty, resilience and robust decision KPI panels
"""

from __future__ import annotations

import argparse
import csv
import html
import io
import json
import math
import re
import sys
import statistics
from collections import defaultdict
from pathlib import Path
from typing import Any, Callable, Iterable

try:
    from etudecas.case_config import (
        ITEM_DISPLAY_REFERENCE_NOTES,
    )
    from etudecas.risk.supplier_audit import (
        DEFAULT_SUPPLIER_AUDIT_SOURCE,
        attach_supplier_audit_panels,
        blend_criticality_with_audit,
        estimate_supplier_audit_profiles,
        expand_supplier_audit_coverage,
        load_supplier_audits,
        supplier_audit_coverage_summary,
        supplier_audit_score,
        supplier_estimated_score,
    )
    from etudecas.simulation.lot_trace import build_lot_trace_payload
    from etudecas.simulation.uncertainty import build_uncertainty_diagnostics
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
except ModuleNotFoundError:
    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
    from etudecas.case_config import (
        ITEM_DISPLAY_REFERENCE_NOTES,
    )
    from etudecas.risk.supplier_audit import (
        DEFAULT_SUPPLIER_AUDIT_SOURCE,
        attach_supplier_audit_panels,
        blend_criticality_with_audit,
        estimate_supplier_audit_profiles,
        expand_supplier_audit_coverage,
        load_supplier_audits,
        supplier_audit_coverage_summary,
        supplier_audit_score,
        supplier_estimated_score,
    )
    from etudecas.simulation.lot_trace import build_lot_trace_payload
    from etudecas.simulation.uncertainty import build_uncertainty_diagnostics
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

try:
    from etudecas.visualization.maps.chart_payloads import (
        build_bar_chart_figure,
        build_bar_chart_payload,
        build_combo_bar_line_payload,
        build_dual_line_multi_panel_figure,
        build_dual_panel_figure,
        build_line_chart_figure,
        build_line_chart_payload,
        build_note_payload,
        densify_daily_series,
        densify_event_spike_series,
        load_png_payload,
        png_payload_from_bytes,
        resolve_plot_payload,
    )
    from etudecas.visualization.maps.html_payload_tools import apply_html_payload_mode
    from etudecas.visualization.maps.global_kpi_tree_payload import build_global_kpi_tree_payload
    from etudecas.visualization.maps.montecarlo_trajectory_payload import build_montecarlo_trajectory_assets
except ModuleNotFoundError:
    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
    from etudecas.visualization.maps.chart_payloads import (
        build_bar_chart_figure,
        build_bar_chart_payload,
        build_combo_bar_line_payload,
        build_dual_line_multi_panel_figure,
        build_dual_panel_figure,
        build_line_chart_figure,
        build_line_chart_payload,
        build_note_payload,
        densify_daily_series,
        densify_event_spike_series,
        load_png_payload,
        png_payload_from_bytes,
        resolve_plot_payload,
    )
    from etudecas.visualization.maps.html_payload_tools import apply_html_payload_mode
    from etudecas.visualization.maps.global_kpi_tree_payload import build_global_kpi_tree_payload
    from etudecas.visualization.maps.montecarlo_trajectory_payload import build_montecarlo_trajectory_assets

try:
    from etudecas.visualization.maps.map_data_loader import (
        load_json_dict,
        output_root_from_csv,
        read_csv_rows,
        read_timeline_horizon_days,
    )
    from etudecas.visualization.maps.map_render import (
        data_html_asset,
        fmt_days,
        fmt_pct,
        fmt_qty,
        html_tooltip_attrs,
        html_tooltip_class,
        json_html_asset,
        metric_label_value,
        metric_section,
        render_data_kv,
        render_data_table,
    )
    from etudecas.visualization.maps.map_payload_builder import (
        attach_generic_payload_contract,
        build_payload_layers_manifest,
        compact_graph_payload,
        display_node_label,
        display_standard_order_qty,
        is_pilotage_hidden_edge,
        is_pilotage_hidden_node,
        is_simulation_hidden_item,
        is_upstream_internal_site,
        merge_hover_payload_maps,
        standard_order_override_for_edge,
    )
    from etudecas.visualization.maps.risk_payload import (
        build_risk_payload_manifest,
        build_supplier_risk_campaign_payload,
        render_supplier_risk_campaign_html,
        supplier_risk_campaign_status,
    )
    from etudecas.visualization.maps.scenario_comparison_payload import (
        build_scenario_comparison_payload,
    )
    from etudecas.visualization.maps.scan_dashboard_payload import (
        build_scan_dashboard_payload,
    )
    from etudecas.visualization.maps.supplier_operations_payload import (
        build_passive_uncertainty_metric,
        coefficient_of_variation,
        compact_order_status,
        consolidate_order_rows_weekly,
        display_order_type,
        effective_order_receipt_day,
        effective_procurement_lead_days,
        finite_numeric_values,
        fmt_order_day,
        fmt_order_day_range,
        fmt_uncertainty_band,
        is_display_order_row,
        is_opening_order_row,
        order_placed_day,
        order_week_start,
        planned_order_receipt_day,
        planned_order_to_receipt_days,
        planned_procurement_lead_days,
        reference_transport_lead_days,
        render_factory_nominal_capacities_html,
        render_order_ledger_html,
        render_passive_uncertainty_html,
        render_supplier_nominal_parameters_html,
        render_supplier_risk_prediction_html,
        render_supplier_stock_flows_html,
        resolved_order_day,
        risk_level,
        source_planned_material_lead_days,
        uncertainty_level,
    )
    from etudecas.visualization.maps.adapters.etudecas_run_payload import (
        map_inputs_from_run_package,
        run_contract_payload,
    )
    from etudecas.visualization.maps.supplier_risk_panels import (
        build_simulated_risk_global_diagnostic_payload,
        build_simulated_supplier_risk_metrics,
        build_supplier_risk_hover_payloads,
        render_supplier_risk_catalog_html,
    )
    from etudecas.visualization.maps.sensitivity_payload import (
        align_series,
        baseline_sensitivity_row,
        build_sensitivity_payload_manifest,
        case_multiplier_value,
        case_output_dir,
        case_rows_by_id,
        cumulative_series,
        first_case_row,
        kpi_from_case,
        local_signal_strength,
        multiplier_label,
        safe_case_token,
    )
    from etudecas.visualization.maps.simulation_payload import (
        build_material_balance_table_rows,
        build_simulation_payload_manifest,
        render_material_balance_table_html,
    )
except ModuleNotFoundError:
    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
    from etudecas.visualization.maps.map_data_loader import (
        load_json_dict,
        output_root_from_csv,
        read_csv_rows,
        read_timeline_horizon_days,
    )
    from etudecas.visualization.maps.map_render import (
        data_html_asset,
        fmt_days,
        fmt_pct,
        fmt_qty,
        html_tooltip_attrs,
        html_tooltip_class,
        json_html_asset,
        metric_label_value,
        metric_section,
        render_data_kv,
        render_data_table,
    )
    from etudecas.visualization.maps.map_payload_builder import (
        attach_generic_payload_contract,
        build_payload_layers_manifest,
        compact_graph_payload,
        display_node_label,
        display_standard_order_qty,
        is_pilotage_hidden_edge,
        is_pilotage_hidden_node,
        is_simulation_hidden_item,
        is_upstream_internal_site,
        merge_hover_payload_maps,
        standard_order_override_for_edge,
    )
    from etudecas.visualization.maps.risk_payload import (
        build_risk_payload_manifest,
        build_supplier_risk_campaign_payload,
        render_supplier_risk_campaign_html,
        supplier_risk_campaign_status,
    )
    from etudecas.visualization.maps.scenario_comparison_payload import (
        build_scenario_comparison_payload,
    )
    from etudecas.visualization.maps.scan_dashboard_payload import (
        build_scan_dashboard_payload,
    )
    from etudecas.visualization.maps.supplier_operations_payload import (
        build_passive_uncertainty_metric,
        coefficient_of_variation,
        compact_order_status,
        consolidate_order_rows_weekly,
        display_order_type,
        effective_order_receipt_day,
        effective_procurement_lead_days,
        finite_numeric_values,
        fmt_order_day,
        fmt_order_day_range,
        fmt_uncertainty_band,
        is_display_order_row,
        is_opening_order_row,
        order_placed_day,
        order_week_start,
        planned_order_receipt_day,
        planned_order_to_receipt_days,
        planned_procurement_lead_days,
        reference_transport_lead_days,
        render_factory_nominal_capacities_html,
        render_order_ledger_html,
        render_passive_uncertainty_html,
        render_supplier_nominal_parameters_html,
        render_supplier_risk_prediction_html,
        render_supplier_stock_flows_html,
        resolved_order_day,
        risk_level,
        source_planned_material_lead_days,
        uncertainty_level,
    )
    from etudecas.visualization.maps.adapters.etudecas_run_payload import (
        map_inputs_from_run_package,
        run_contract_payload,
    )
    from etudecas.visualization.maps.supplier_risk_panels import (
        build_simulated_risk_global_diagnostic_payload,
        build_simulated_supplier_risk_metrics,
        build_supplier_risk_hover_payloads,
        render_supplier_risk_catalog_html,
    )
    from etudecas.visualization.maps.sensitivity_payload import (
        align_series,
        baseline_sensitivity_row,
        build_sensitivity_payload_manifest,
        case_multiplier_value,
        case_output_dir,
        case_rows_by_id,
        cumulative_series,
        first_case_row,
        kpi_from_case,
        local_signal_strength,
        multiplier_label,
        safe_case_token,
    )
    from etudecas.visualization.maps.simulation_payload import (
        build_material_balance_table_rows,
        build_simulation_payload_manifest,
        render_material_balance_table_html,
    )

try:
    from etudecas.visualization.maps.worldmap_html_template import ensure_plotly_offline_assets, html_template
except ModuleNotFoundError:
    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
    from etudecas.visualization.maps.worldmap_html_template import ensure_plotly_offline_assets, html_template

DEFAULT_SUPPLIER_PARAMETER_SENSITIVITY_DIR = Path(
    "etudecas/simulation/sensibility/active_supplier_parameter_result_60_75_guarded"
)
DEFAULT_SUPPLIER_RISK_KPI_DIR = Path("etudecas/risk/supplier_criticality/result")
DEFAULT_MONTECARLO_UNCERTAINTY_DIR = Path("etudecas/simulation/montecarlo/active_mrp_physical_uncertainty")
DEFAULT_SUPPLIER_RISK_CAMPAIGN_DIR = Path("etudecas/simulation/sensibility/supplier_risk_campaign_multisource_result")

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--input",
        "-i",
        default="etudecas/simulation_prep/result/supply_graph_poc_simulation_ready.json",
        help="Input geocoded supply graph JSON.",
    )
    parser.add_argument(
        "--output",
        "-o",
        default="etudecas/simulation/result/maps/supply_graph_poc_geocoded_map_with_factory_hover.html",
        help="Output HTML file.",
    )
    parser.add_argument(
        "--title",
        default="Supply Graph POC - Geocoded Map",
        help="HTML page title.",
    )
    parser.add_argument(
        "--run-package",
        default="",
        help=(
            "Generic simulation run package directory. When provided, standard "
            "simulation CSV paths are resolved from run/artifact_index.json."
        ),
    )
    parser.add_argument(
        "--simulated-risk-output-dir",
        default="",
        help=(
            "Optional simulation result directory used as the primary Risques simules "
            "state-dependent scenario. The main map can stay nominal while this run "
            "feeds risk events and risk diagnostic charts."
        ),
    )
    parser.add_argument(
        "--scan-results-dir",
        default="",
        help=(
            "Optional RESILIENCE-SCAN validation package. When provided, the "
            "map embeds a dedicated dashboard with summary metrics, curves and "
            "policy tables. The source package itself is not copied into Git."
        ),
    )
    parser.add_argument(
        "--closed-loop-results-dir",
        default="",
        help=(
            "Optional paired canonical MRP-versus-feedback campaign. When used "
            "with --scan-results-dir, it adds a Boucle fermee pane with causal "
            "audit, paired deltas and controller diagnostics."
        ),
    )
    parser.add_argument(
        "--closed-loop-v2-results-dir",
        default="",
        help=(
            "Optional additive Closed-Loop V2 campaign. When used with "
            "--scan-results-dir, it adds a distinct Closed-Loop V2 pane and "
            "does not replace the historical Boucle fermee pane."
        ),
    )
    parser.add_argument(
        "--scan-frequency-results-dir",
        default="",
        help=(
            "Optional canonical frequency-analysis package. When used with "
            "--scan-results-dir, it adds a distinct Analyse frequentielle pane "
            "with empirical harmonic-line, coherence, spectral-peak and "
            "repeatability evidence."
        ),
    )
    parser.add_argument(
        "--scan-control-system-results-dir",
        default="",
        help=(
            "Optional canonical control-system analysis package. When used "
            "with --scan-results-dir, it adds a distinct Analyse systeme pane "
            "with local state-space, controllability, observability, pole and "
            "stability evidence."
        ),
    )
    parser.add_argument(
        "--externalize-payload",
        action="store_true",
        help=(
            "Write the large JavaScript DATA payload to a sibling JSON file and "
            "load it with fetch(). The resulting HTML must be served over HTTP."
        ),
    )
    parser.add_argument(
        "--compress-embedded-payload",
        action="store_true",
        help=(
            "Keep a single autonomous HTML file but store DATA as embedded gzip/base64. "
            "Requires a recent browser with DecompressionStream(gzip)."
        ),
    )
    parser.add_argument(
        "--chunked-embedded-payload",
        action="store_true",
        help=(
            "Keep a single autonomous HTML file and store each top-level DATA key "
            "as a separate embedded gzip/base64 block."
        ),
    )
    parser.add_argument(
        "--payload-json",
        help="External JSON path when --externalize-payload is used. Defaults to <output>.data.json.",
    )
    parser.add_argument(
        "--read-only-source",
        action="store_true",
        help=(
            "Build the map without writing derived KPI, compliance or supplier "
            "criticality reports next to the source simulation files."
        ),
    )
    parser.add_argument(
        "--sim-input-stocks-csv",
        default="etudecas/simulation/result/data/production_input_stocks_daily.csv",
        help="Simulation CSV for input material stocks.",
    )
    parser.add_argument(
        "--sim-output-products-csv",
        default="etudecas/simulation/result/data/production_output_products_daily.csv",
        help="Simulation CSV for output products production.",
    )
    parser.add_argument(
        "--demand-service-csv",
        default="etudecas/simulation/result/data/production_demand_service_daily.csv",
        help="Simulation CSV for customer demand / served / backlog time series.",
    )
    parser.add_argument(
        "--sim-input-stocks-png-dir",
        default="etudecas/simulation/result/plots",
        help="Directory containing input/supplier/DC PNG files.",
    )
    parser.add_argument(
        "--sim-output-products-png-dir",
        default="etudecas/simulation/result/plots",
        help="Directory containing production_output_products_by_factory_<factory>.png files.",
    )
    parser.add_argument(
        "--sensitivity-cases-csv",
        default="etudecas/simulation/sensibility/result/sensitivity_cases.csv",
        help="Sensitivity cases summary CSV.",
    )
    parser.add_argument(
        "--supplier-shipments-csv",
        default="etudecas/simulation/result/data/production_supplier_shipments_daily.csv",
        help="Baseline supplier shipments CSV.",
    )
    parser.add_argument(
        "--supplier-stocks-csv",
        default="etudecas/simulation/result/data/production_supplier_stocks_daily.csv",
        help="Baseline supplier stocks CSV.",
    )
    parser.add_argument(
        "--supplier-stock-flows-csv",
        default="",
        help="Baseline supplier stock flow CSV with incoming/outgoing stock movements.",
    )
    parser.add_argument(
        "--supplier-capacity-csv",
        default="etudecas/simulation/result/data/production_supplier_capacity_daily.csv",
        help="Baseline supplier capacity utilization CSV.",
    )
    parser.add_argument(
        "--supplier-nominal-parameters-csv",
        default="",
        help="Optional supplier nominal parameter CSV generated by the simulation.",
    )
    parser.add_argument(
        "--factory-nominal-capacities-csv",
        default="",
        help="Optional factory/process nominal capacity CSV generated by the simulation.",
    )
    parser.add_argument(
        "--input-arrivals-csv",
        default="etudecas/simulation/result/data/production_input_replenishment_arrivals_daily.csv",
        help="Baseline input replenishment arrivals CSV.",
    )
    parser.add_argument(
        "--dc-stocks-csv",
        default="etudecas/simulation/result/data/production_dc_stocks_daily.csv",
        help="Baseline distribution center stocks CSV.",
    )
    parser.add_argument(
        "--production-constraint-csv",
        default="etudecas/simulation/result/data/production_constraint_daily.csv",
        help="Production constraint CSV used to detect critical supplied items.",
    )
    parser.add_argument(
        "--lot-events-csv",
        default="",
        help="Optional lot trace event CSV. Defaults to production_lot_events.csv next to simulation data.",
    )
    parser.add_argument(
        "--lot-genealogy-csv",
        default="",
        help="Optional lot genealogy CSV. Defaults to production_lot_genealogy.csv next to simulation data.",
    )
    parser.add_argument(
        "--production-plan-events-csv",
        default="",
        help="Optional production plan event CSV. Defaults to production_plan_events.csv next to simulation data.",
    )
    parser.add_argument(
        "--production-campaigns-csv",
        default="",
        help="Optional production campaign summary CSV. Defaults to production_campaigns.csv next to simulation data.",
    )
    parser.add_argument(
        "--safety-reference-csv",
        default="",
        help="Optional MRP safety stock reference CSV generated by the simulation.",
    )
    parser.add_argument(
        "--daily-kpi-csv",
        default="",
        help="Optional daily KPI CSV generated by the simulation. Defaults to first_simulation_daily.csv next to simulation data.",
    )
    parser.add_argument(
        "--structural-sensitivity-cases-csv",
        default="etudecas/simulation/sensibility/structural_result/sensitivity_cases.csv",
        help="Structural sensitivity cases summary CSV.",
    )
    parser.add_argument(
        "--supplier-local-criticality-csv",
        default="etudecas/simulation/result/data/supplier_local_criticality_ranking.csv",
        help="Output CSV ranking for supplier local criticality.",
    )
    parser.add_argument(
        "--supplier-local-criticality-json",
        default="etudecas/simulation/result/summaries/supplier_local_criticality_summary.json",
        help="Output JSON summary for supplier local criticality.",
    )
    parser.add_argument(
        "--realistic-sensitivity-summary-json",
        default="",
        help="Optional realistic annual sensitivity summary JSON.",
    )
    parser.add_argument(
        "--realistic-local-elasticities-csv",
        default="",
        help="Optional realistic annual local elasticities CSV.",
    )
    parser.add_argument(
        "--realistic-stress-impacts-csv",
        default="",
        help="Optional realistic annual stress impacts CSV.",
    )
    parser.add_argument(
        "--threshold-sensitivity-summary-json",
        default="",
        help="Optional threshold-oriented annual sensitivity summary JSON.",
    )
    parser.add_argument(
        "--threshold-parameter-summary-csv",
        default="",
        help="Optional threshold-oriented annual parameter summary CSV.",
    )
    parser.add_argument(
        "--threshold-sweep-cases-csv",
        default="",
        help="Optional threshold-oriented annual sweep cases CSV.",
    )
    parser.add_argument(
        "--supplier-parameter-sensitivity-summary-json",
        default=str(DEFAULT_SUPPLIER_PARAMETER_SENSITIVITY_DIR / "supplier_parameter_sensitivity_summary.json"),
        help="Optional supplier parameter sensitivity summary JSON.",
    )
    parser.add_argument(
        "--supplier-parameter-summary-csv",
        default=str(DEFAULT_SUPPLIER_PARAMETER_SENSITIVITY_DIR / "supplier_parameter_threshold_summary.csv"),
        help="Optional supplier parameter sensitivity threshold summary CSV.",
    )
    parser.add_argument(
        "--supplier-parameter-cases-csv",
        default=str(DEFAULT_SUPPLIER_PARAMETER_SENSITIVITY_DIR / "supplier_parameter_sensitivity_cases.csv"),
        help="Optional supplier parameter sensitivity case-level CSV.",
    )
    parser.add_argument(
        "--supplier-risk-kpi-summary-json",
        default=str(DEFAULT_SUPPLIER_RISK_KPI_DIR / "summaries" / "supplier_risk_kpi_summary.json"),
        help="Optional supplier risk KPI summary JSON.",
    )
    parser.add_argument(
        "--supplier-risk-kpi-supplier-csv",
        default=str(DEFAULT_SUPPLIER_RISK_KPI_DIR / "data" / "supplier_risk_kpi.csv"),
        help="Optional supplier-level risk KPI CSV.",
    )
    parser.add_argument(
        "--supplier-risk-kpi-pair-csv",
        default=str(DEFAULT_SUPPLIER_RISK_KPI_DIR / "data" / "supplier_item_risk_kpi.csv"),
        help="Optional latest supplier-item-site risk KPI CSV.",
    )
    parser.add_argument(
        "--supplier-risk-kpi-panel-csv",
        default=str(DEFAULT_SUPPLIER_RISK_KPI_DIR / "data" / "supplier_item_week_panel.csv"),
        help="Optional supplier-item-site weekly risk KPI panel CSV.",
    )
    parser.add_argument(
        "--supplier-audit-xlsx",
        default=str(DEFAULT_SUPPLIER_AUDIT_SOURCE),
        help="Supplier audit workbook or directory whose criticality criteria are added to the risk map.",
    )
    parser.add_argument(
        "--montecarlo-summary-json",
        default="",
        help="Optional Monte Carlo uncertainty summary JSON. No implicit fallback is used.",
    )
    parser.add_argument(
        "--supplier-risk-campaign-summary-json",
        default=str(DEFAULT_SUPPLIER_RISK_CAMPAIGN_DIR / "supplier_risk_campaign_summary.json"),
        help="Optional supplier risk stress campaign summary JSON.",
    )
    parser.add_argument(
        "--supplier-risk-campaign-summary-csv",
        default=str(DEFAULT_SUPPLIER_RISK_CAMPAIGN_DIR / "supplier_risk_campaign_summary.csv"),
        help="Optional supplier risk stress campaign summary CSV.",
    )
    parser.add_argument(
        "--supplier-risk-campaign-cases-csv",
        default=str(DEFAULT_SUPPLIER_RISK_CAMPAIGN_DIR / "supplier_risk_campaign_cases.csv"),
        help="Optional supplier risk stress campaign case-level CSV.",
    )
    return parser.parse_args()


def to_float(x: Any) -> float | None:
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def finite_float(value: Any) -> float | None:
    numeric = to_float(value)
    if numeric is None or math.isnan(numeric):
        return None
    return numeric


def first_finite_metric(row: dict[str, Any], keys: list[str]) -> float | None:
    for key in keys:
        numeric = finite_float(row.get(key))
        if numeric is not None:
            return numeric
    return None


def fraction_metric_to_percent(value: float | None) -> float | None:
    if value is None:
        return None
    # Simulation KPI rates are stored as fractions. Keep already-percent values as-is
    # for backward-compatible imported summaries.
    return value * 100.0 if abs(value) <= 1.5 else value


def production_planning_line_count_from_constraint_csv(production_constraint_csv: Path) -> float | None:
    if not production_constraint_csv.exists():
        return None
    line_count = 0
    try:
        for row in read_csv_rows(production_constraint_csv):
            planned = max(0.0, finite_float(row.get("planned_qty_after_lot_rule")) or 0.0)
            actual = max(0.0, finite_float(row.get("actual_qty")) or 0.0)
            requested_lots = finite_float(row.get("requested_lot_starts"))
            if planned > 1e-9 or actual > 1e-9 or (requested_lots is not None and requested_lots > 1e-9):
                line_count += 1
    except Exception:
        return None
    return float(line_count) if line_count > 0 else None


def production_output_pair_count(raw: dict[str, Any]) -> int:
    pairs: set[tuple[str, str]] = set()
    for node in raw.get("nodes", []) or []:
        node_id = str(node.get("id") or "")
        if not node_id:
            continue
        if str(node.get("type") or "") != "factory" and not (node.get("processes") or []):
            continue
        for proc in node.get("processes") or []:
            if not isinstance(proc, dict):
                continue
            for out in proc.get("outputs") or []:
                if not isinstance(out, dict):
                    continue
                item_id = str(out.get("item_id") or "").strip()
                if item_id:
                    pairs.add((node_id, item_id))
    return len(pairs)


def production_replanning_rate_denominator(
    raw: dict[str, Any],
    *,
    horizon_days: int | None,
    production_constraint_csv: Path,
) -> float | None:
    line_count = production_planning_line_count_from_constraint_csv(production_constraint_csv) or 0.0
    pair_count = production_output_pair_count(raw)
    daily_opportunities = float(pair_count * horizon_days) if pair_count > 0 and horizon_days and horizon_days > 0 else 0.0
    denominator = max(line_count, daily_opportunities)
    return denominator if denominator > 0 else None


def sensitivity_availability_percent(row: dict[str, Any]) -> float:
    value = first_finite_metric(row, ["kpi::product_availability", "product_availability", "kpi::fill_rate", "fill_rate"])
    return float(fraction_metric_to_percent(value) or 0.0)


def sensitivity_replanning_rate_percent(
    row: dict[str, Any],
    *,
    baseline_production_planning_line_count: float | None = None,
) -> float | None:
    rate = first_finite_metric(row, ["kpi::production_replanning_rate", "production_replanning_rate"])
    if rate is not None:
        return fraction_metric_to_percent(rate)

    replanning_count = first_finite_metric(row, ["kpi::production_replanning_count", "production_replanning_count"])
    if replanning_count is None:
        return None
    denominator = first_finite_metric(
        row,
        ["kpi::production_planning_line_count", "production_planning_line_count"],
    )
    if denominator is None or denominator <= 0:
        denominator = baseline_production_planning_line_count
    if denominator is None or denominator <= 0:
        return None
    return 100.0 * replanning_count / denominator


def collect_node_item_ids(node: dict[str, Any]) -> list[str]:
    item_ids: set[str] = set()
    for state in (((node.get("inventory") or {}).get("states")) or []):
        if isinstance(state, dict):
            item_id = str(state.get("item_id") or "").strip()
            if item_id:
                item_ids.add(item_id)
    for proc in node.get("processes") or []:
        if not isinstance(proc, dict):
            continue
        for entry in (proc.get("inputs") or []) + (proc.get("outputs") or []):
            if not isinstance(entry, dict):
                continue
            item_id = str(entry.get("item_id") or "").strip()
            if item_id:
                item_ids.add(item_id)
    return sorted(item_ids)


def json_edge_summary(edge: dict[str, Any], item_labels: dict[str, str]) -> dict[str, Any]:
    items = [str(item_id) for item_id in (edge.get("items") or []) if str(item_id or "")]
    return {
        "id": edge.get("id"),
        "type": edge.get("type"),
        "from": edge.get("from"),
        "to": edge.get("to"),
        "items": [
            {
                "id": item_id,
                "label": item_labels.get(item_id, compact_item_label(item_id)),
            }
            for item_id in items
        ],
        "lead_time": edge.get("lead_time"),
        "distance_km": edge.get("distance_km"),
        "transport_cost": edge.get("transport_cost"),
        "standard_order_qty": display_standard_order_qty(edge),
        "attrs": edge.get("attrs") or {},
    }


def build_json_panel_payload(raw: dict[str, Any]) -> dict[str, Any]:
    item_labels = item_label_lookup(raw)
    item_by_id = {
        str(item.get("id") or ""): item
        for item in raw.get("items", []) or []
        if isinstance(item, dict) and str(item.get("id") or "")
    }
    node_by_id = {
        str(node.get("id") or ""): node
        for node in raw.get("nodes", []) or []
        if isinstance(node, dict) and str(node.get("id") or "") and not is_pilotage_hidden_node(str(node.get("id") or ""))
    }
    visible_edges = [
        edge
        for edge in raw.get("edges", []) or []
        if isinstance(edge, dict)
        and not is_pilotage_hidden_edge(str(edge.get("from") or ""), str(edge.get("to") or ""))
    ]
    inbound_by_node: dict[str, list[dict[str, Any]]] = defaultdict(list)
    outbound_by_node: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for edge in visible_edges:
        src = str(edge.get("from") or "")
        dst = str(edge.get("to") or "")
        summary = json_edge_summary(edge, item_labels)
        if dst:
            inbound_by_node[dst].append(summary)
        if src:
            outbound_by_node[src].append(summary)

    node_payload: dict[str, Any] = {}
    for node_id, node in sorted(node_by_id.items()):
        item_ids = collect_node_item_ids(node)
        inventory_states = (((node.get("inventory") or {}).get("states")) or [])
        processes = node.get("processes") or []
        item_definitions = [item_by_id.get(item_id, {"id": item_id}) for item_id in item_ids]
        connected_flux = {
            "flux_entrants": inbound_by_node.get(node_id, []),
            "flux_sortants": outbound_by_node.get(node_id, []),
        }
        full_payload = {
            "node": node,
            "items_identifies": item_definitions,
            **connected_flux,
        }
        node_payload[node_id] = {
            "title": f"{display_node_label(node_id)} - donnees JSON",
            "summary_lines": [
                {"label": "Noeud", "value": display_node_label(node_id)},
                {"label": "Type", "value": str(node.get("type") or "n/a")},
                {"label": "Nom", "value": str(node.get("name") or "")},
                {"label": "Stocks declares", "value": str(len(inventory_states))},
                {"label": "Processus declares", "value": str(len(processes))},
                {"label": "Items identifies", "value": str(len(item_ids))},
                {"label": "Flux entrants / sortants", "value": f"{len(inbound_by_node.get(node_id, []))} / {len(outbound_by_node.get(node_id, []))}"},
            ],
            "incoming": json_html_asset(
                f"{display_node_label(node_id)} - noeud brut",
                "Objet noeud tel qu'il est disponible dans le JSON scenario.",
                node,
            ),
            "outgoing": json_html_asset(
                f"{display_node_label(node_id)} - stocks et processus",
                "Stocks initiaux/politiques MRP et processus de production declares sur le noeud.",
                {
                    "inventory": node.get("inventory") or {},
                    "processes": processes,
                },
            ),
            "third": json_html_asset(
                f"{display_node_label(node_id)} - flux connectes",
                "Flux entrants et sortants visibles dans la carte pour ce noeud.",
                connected_flux,
            ),
            "fourth": {
                "bundle": [
                    {
                        "label": "Noeud complet",
                        "asset": json_html_asset(
                            f"{display_node_label(node_id)} - JSON complet",
                            "Vue consolidee: noeud, items identifies et flux connectes.",
                            full_payload,
                        ),
                    },
                    {
                        "label": "Items",
                        "asset": json_html_asset(
                            f"{display_node_label(node_id)} - items",
                            "Definitions des items references par les stocks/processus du noeud.",
                            item_definitions,
                        ),
                    },
                    {
                        "label": "Flux entrants",
                        "asset": json_html_asset(
                            f"{display_node_label(node_id)} - flux entrants",
                            "Flux amont qui alimentent ce noeud.",
                            connected_flux["flux_entrants"],
                        ),
                    },
                    {
                        "label": "Flux sortants",
                        "asset": json_html_asset(
                            f"{display_node_label(node_id)} - flux sortants",
                            "Flux aval expedies depuis ce noeud.",
                            connected_flux["flux_sortants"],
                        ),
                    },
                ]
            },
        }

    edge_payload: dict[str, Any] = {}
    for edge in visible_edges:
        edge_id = str(edge.get("id") or "")
        if not edge_id:
            continue
        src = str(edge.get("from") or "")
        dst = str(edge.get("to") or "")
        item_ids = [str(item_id) for item_id in (edge.get("items") or []) if str(item_id or "")]
        item_definitions = [item_by_id.get(item_id, {"id": item_id}) for item_id in item_ids]
        source_node = node_by_id.get(src, {"id": src})
        destination_node = node_by_id.get(dst, {"id": dst})
        summary = json_edge_summary(edge, item_labels)
        full_payload = {
            "flux": edge,
            "resume_flux": summary,
            "source_node": source_node,
            "destination_node": destination_node,
            "items": item_definitions,
        }
        edge_payload[edge_id] = {
            "title": f"{src} -> {dst} - donnees JSON",
            "summary_lines": [
                {"label": "Flux", "value": f"{src} -> {dst}"},
                {"label": "Type", "value": str(edge.get("type") or "n/a")},
                {"label": "Items", "value": ", ".join(item_labels.get(item_id, compact_item_label(item_id)) for item_id in item_ids) or "n/a"},
                {"label": "Delai prev.", "value": f"{max(1.0, to_float(((edge.get('lead_time') or {}).get('mean'))) or 1.0):.1f} j"},
                {"label": "Distance", "value": f"{max(0.0, to_float(edge.get('distance_km')) or 0.0):.0f} km"},
                {"label": "Commande standard", "value": fmt_qty(display_standard_order_qty(edge), 1)},
            ],
            "incoming": json_html_asset(
                f"{src} -> {dst} - flux brut",
                "Objet flux tel qu'il est disponible dans le JSON scenario.",
                edge,
            ),
            "outgoing": json_html_asset(
                f"{src} -> {dst} - source et destination",
                "Noeuds source et destination associes a ce flux.",
                {
                    "source_node": source_node,
                    "destination_node": destination_node,
                },
            ),
            "third": json_html_asset(
                f"{src} -> {dst} - items",
                "Definitions des items transportes par ce flux.",
                item_definitions,
            ),
            "fourth": {
                "bundle": [
                    {
                        "label": "Flux complet",
                        "asset": json_html_asset(
                            f"{src} -> {dst} - JSON complet",
                            "Vue consolidee: flux, source, destination et items.",
                            full_payload,
                        ),
                    },
                    {
                        "label": "Resume flux",
                        "asset": json_html_asset(
                            f"{src} -> {dst} - resume flux",
                            "Resume lisible des principales proprietes du flux.",
                            summary,
                        ),
                    },
                ]
            },
        }

    return {
        "nodes": node_payload,
        "edges": edge_payload,
    }


def item_display(item_id: str, item_labels: dict[str, str]) -> str:
    return item_labels.get(item_id, compact_item_label(item_id))


def format_policy_value(value: Any, decimals: int = 1) -> str:
    numeric = to_float(value)
    if numeric is None:
        return str(value) if value not in (None, "") else "n/a"
    return fmt_qty(numeric, decimals)


def summarize_inventory_rows(node: dict[str, Any], item_labels: dict[str, str]) -> list[list[str]]:
    rows: list[list[str]] = []
    for state in (((node.get("inventory") or {}).get("states")) or []):
        if not isinstance(state, dict):
            continue
        item_id = str(state.get("item_id") or "")
        mrp_policy = state.get("mrp_policy") or {}
        holding = state.get("holding_cost") or {}
        rows.append(
            [
                item_display(item_id, item_labels),
                format_policy_value(state.get("initial"), 1),
                str(state.get("uom") or "n/a"),
                format_policy_value(mrp_policy.get("safety_stock_qty"), 1),
                format_policy_value(mrp_policy.get("safety_time_days"), 1),
                format_policy_value(holding.get("unit_value_basis"), 4),
                str(state.get("initial_source") or mrp_policy.get("source") or "n/a"),
            ]
        )
    return rows


def summarize_process_rows(node: dict[str, Any], item_labels: dict[str, str]) -> list[list[str]]:
    rows: list[list[str]] = []
    for proc in node.get("processes") or []:
        if not isinstance(proc, dict):
            continue
        outputs = [
            item_display(str(out.get("item_id") or ""), item_labels)
            for out in proc.get("outputs") or []
            if isinstance(out, dict)
        ]
        inputs = []
        for inp in proc.get("inputs") or []:
            if not isinstance(inp, dict):
                continue
            item_id = str(inp.get("item_id") or "")
            ratio = format_policy_value(inp.get("ratio_per_batch"), 4)
            unit = str(inp.get("uom") or inp.get("ratio_uom") or "").strip()
            inputs.append(f"{item_display(item_id, item_labels)}={ratio} {unit}".strip())
        lot_sizing = proc.get("lot_sizing") or {}
        lot_exec = proc.get("lot_execution") or {}
        capacity = proc.get("capacity") or {}
        rows.append(
            [
                str(proc.get("id") or "n/a"),
                ", ".join(outputs) or "n/a",
                ", ".join(inputs) or "n/a",
                format_policy_value(proc.get("batch_size"), 1),
                format_policy_value(lot_sizing.get("fixed_lot_qty") or lot_sizing.get("min_lot_qty") or lot_sizing.get("lot_multiple_qty"), 1),
                format_policy_value(lot_exec.get("max_lots_per_week"), 1),
                format_policy_value(capacity.get("max_rate"), 1),
            ]
        )
    return rows


def summarize_flux_rows(edges: list[dict[str, Any]], item_labels: dict[str, str], *, direction: str) -> list[list[str]]:
    rows: list[list[str]] = []
    for edge in edges:
        src = str(edge.get("from") or "")
        dst = str(edge.get("to") or "")
        peer = src if direction == "in" else dst
        item_ids = [str(item_id) for item_id in (edge.get("items") or []) if str(item_id or "")]
        lead_time = edge.get("lead_time") or {}
        rows.append(
            [
                peer or "n/a",
                ", ".join(item_display(item_id, item_labels) for item_id in item_ids) or "n/a",
                format_policy_value(lead_time.get("mean"), 1),
                str(lead_time.get("type") or "n/a"),
                format_policy_value(display_standard_order_qty(edge), 1),
                format_policy_value(edge.get("distance_km"), 0),
            ]
        )
    return rows


def build_data_panel_payload(raw: dict[str, Any]) -> dict[str, Any]:
    item_labels = item_label_lookup(raw)
    item_by_id = {
        str(item.get("id") or ""): item
        for item in raw.get("items", []) or []
        if isinstance(item, dict) and str(item.get("id") or "")
    }
    nodes = [
        node
        for node in raw.get("nodes", []) or []
        if isinstance(node, dict) and not is_pilotage_hidden_node(str(node.get("id") or ""))
    ]
    node_by_id = {str(node.get("id") or ""): node for node in nodes if str(node.get("id") or "")}
    edges = [
        edge
        for edge in raw.get("edges", []) or []
        if isinstance(edge, dict)
        and not is_pilotage_hidden_edge(str(edge.get("from") or ""), str(edge.get("to") or ""))
    ]
    inbound_by_node: dict[str, list[dict[str, Any]]] = defaultdict(list)
    outbound_by_node: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for edge in edges:
        inbound_by_node[str(edge.get("to") or "")].append(edge)
        outbound_by_node[str(edge.get("from") or "")].append(edge)

    node_payload: dict[str, Any] = {}
    for node in sorted(nodes, key=lambda row: str(row.get("id") or "")):
        node_id = str(node.get("id") or "")
        if not node_id:
            continue
        item_ids = collect_node_item_ids(node)
        geo = node.get("geo") or {}
        inventory_rows = summarize_inventory_rows(node, item_labels)
        process_rows = summarize_process_rows(node, item_labels)
        inbound_rows = summarize_flux_rows(inbound_by_node.get(node_id, []), item_labels, direction="in")
        outbound_rows = summarize_flux_rows(outbound_by_node.get(node_id, []), item_labels, direction="out")
        summary_rows = [
            ("Noeud", display_node_label(node_id)),
            ("Type", node.get("type") or "n/a"),
            ("Nom", node.get("name") or "n/a"),
            ("Pays", geo.get("country") or node.get("country") or "n/a"),
            ("Items", ", ".join(item_display(item_id, item_labels) for item_id in item_ids) or "n/a"),
            ("Stocks / processus", f"{len(inventory_rows)} / {len(process_rows)}"),
            ("Flux entrants / sortants", f"{len(inbound_rows)} / {len(outbound_rows)}"),
        ]
        node_payload[node_id] = {
            "title": f"{display_node_label(node_id)} - synthese donnees",
            "summary_lines": [
                {"label": "Noeud", "value": display_node_label(node_id)},
                {"label": "Type", "value": str(node.get("type") or "n/a")},
                {"label": "Items", "value": str(len(item_ids))},
                {"label": "Stocks / processus", "value": f"{len(inventory_rows)} / {len(process_rows)}"},
                {"label": "Flux entrants / sortants", "value": f"{len(inbound_rows)} / {len(outbound_rows)}"},
            ],
            "incoming": data_html_asset(
                f"{display_node_label(node_id)} - fiche noeud",
                "Resume des champs utiles presents dans le JSON du scenario.",
                [("Identite", render_data_kv(summary_rows))],
            ),
            "outgoing": data_html_asset(
                f"{display_node_label(node_id)} - stocks et processus",
                "Stocks initiaux, politique MRP et processus declares.",
                [
                    (
                        "Stocks / politiques MRP",
                        render_data_table(
                            ["Item", "Stock initial", "UoM", "Stock secu", "Delai secu j", "Valeur unite", "Source"],
                            inventory_rows,
                        ),
                    ),
                    (
                        "Processus",
                        render_data_table(
                            ["Process", "Sorties", "Intrants", "Batch", "Lot", "Lots/sem", "Cap/j"],
                            process_rows,
                        ),
                    ),
                ],
            ),
            "third": data_html_asset(
                f"{display_node_label(node_id)} - flux connectes",
                "Flux entrants et sortants disponibles pour ce noeud.",
                [
                    (
                        "Flux entrants",
                        render_data_table(
                            ["Source", "Items", "Delai j", "Type delai", "Commande std", "Distance km"],
                            inbound_rows,
                        ),
                    ),
                    (
                        "Flux sortants",
                        render_data_table(
                            ["Destination", "Items", "Delai j", "Type delai", "Commande std", "Distance km"],
                            outbound_rows,
                        ),
                    ),
                ],
            ),
            "fourth": data_html_asset(
                f"{display_node_label(node_id)} - items references",
                "Definitions courtes des items rattaches au noeud.",
                [
                    (
                        "Items",
                        render_data_table(
                            ["Item", "Code", "Nom", "Type", "UoM"],
                            [
                                [
                                    item_display(item_id, item_labels),
                                    (item_by_id.get(item_id) or {}).get("code") or "n/a",
                                    (item_by_id.get(item_id) or {}).get("name") or "n/a",
                                    (item_by_id.get(item_id) or {}).get("kind") or "n/a",
                                    (item_by_id.get(item_id) or {}).get("uom_default") or "n/a",
                                ]
                                for item_id in item_ids
                            ],
                        ),
                    )
                ],
            ),
        }

    edge_payload: dict[str, Any] = {}
    for edge in edges:
        edge_id = str(edge.get("id") or "")
        if not edge_id:
            continue
        src = str(edge.get("from") or "")
        dst = str(edge.get("to") or "")
        item_ids = [str(item_id) for item_id in (edge.get("items") or []) if str(item_id or "")]
        lead_time = edge.get("lead_time") or {}
        order_terms = edge.get("order_terms") or {}
        transport_cost = edge.get("transport_cost") or {}
        summary_rows = [
            ("Flux", f"{src} -> {dst}"),
            ("Type", edge.get("type") or "n/a"),
            ("Items", ", ".join(item_display(item_id, item_labels) for item_id in item_ids) or "n/a"),
            ("Delai previsionnel", f"{format_policy_value(lead_time.get('mean'), 1)} j"),
            ("Type delai", lead_time.get("type") or "n/a"),
            ("Source delai", lead_time.get("source") or "n/a"),
            ("Distance", f"{format_policy_value(edge.get('distance_km'), 0)} km"),
            ("Commande standard", format_policy_value(display_standard_order_qty(edge), 1)),
            ("Cout transport", f"{format_policy_value(transport_cost.get('value'), 4)} / {transport_cost.get('per') or 'n/a'}"),
            ("Prix achat", f"{format_policy_value(order_terms.get('sell_price'), 4)} / {order_terms.get('price_base') or 'n/a'} {order_terms.get('quantity_unit') or ''}".strip()),
        ]
        edge_payload[edge_id] = {
            "title": f"{src} -> {dst} - synthese donnees",
            "summary_lines": [
                {"label": "Flux", "value": f"{src} -> {dst}"},
                {"label": "Items", "value": ", ".join(item_display(item_id, item_labels) for item_id in item_ids) or "n/a"},
                {"label": "Delai prev.", "value": f"{format_policy_value(lead_time.get('mean'), 1)} j"},
                {"label": "Commande std", "value": format_policy_value(display_standard_order_qty(edge), 1)},
            ],
            "incoming": data_html_asset(
                f"{src} -> {dst} - fiche flux",
                "Resume des champs utiles presents dans le JSON du scenario.",
                [("Identite et parametres", render_data_kv(summary_rows))],
            ),
            "outgoing": data_html_asset(
                f"{src} -> {dst} - source / destination",
                "Resume court des noeuds relies par le flux.",
                [
                    (
                        "Noeuds",
                        render_data_table(
                            ["Role", "Noeud", "Type", "Nom", "Pays"],
                            [
                                [
                                    "Source",
                                    src,
                                    (node_by_id.get(src) or {}).get("type") or "n/a",
                                    (node_by_id.get(src) or {}).get("name") or "n/a",
                                    ((node_by_id.get(src) or {}).get("geo") or {}).get("country") or "n/a",
                                ],
                                [
                                    "Destination",
                                    dst,
                                    (node_by_id.get(dst) or {}).get("type") or "n/a",
                                    (node_by_id.get(dst) or {}).get("name") or "n/a",
                                    ((node_by_id.get(dst) or {}).get("geo") or {}).get("country") or "n/a",
                                ],
                            ],
                        ),
                    )
                ],
            ),
            "third": data_html_asset(
                f"{src} -> {dst} - items transportes",
                "Definitions courtes des items transportes par ce flux.",
                [
                    (
                        "Items",
                        render_data_table(
                            ["Item", "Code", "Nom", "Type", "UoM"],
                            [
                                [
                                    item_display(item_id, item_labels),
                                    (item_by_id.get(item_id) or {}).get("code") or "n/a",
                                    (item_by_id.get(item_id) or {}).get("name") or "n/a",
                                    (item_by_id.get(item_id) or {}).get("kind") or "n/a",
                                    (item_by_id.get(item_id) or {}).get("uom_default") or "n/a",
                                ]
                                for item_id in item_ids
                            ],
                        ),
                    )
                ],
            ),
            "fourth": data_html_asset(
                f"{src} -> {dst} - couts et delais",
                "Champs economiques et delai utilises par le simulateur.",
                [
                    ("Delai", render_data_kv([
                        ("Moyenne", f"{format_policy_value(lead_time.get('mean'), 1)} j"),
                        ("Type", lead_time.get("type") or "n/a"),
                        ("Stages", lead_time.get("stages") or "n/a"),
                        ("Source", lead_time.get("source") or "n/a"),
                    ])),
                    ("Economique", render_data_kv([
                        ("Prix achat", f"{format_policy_value(order_terms.get('sell_price'), 4)} / {order_terms.get('price_base') or 'n/a'} {order_terms.get('quantity_unit') or ''}".strip()),
                        ("Cout transport", f"{format_policy_value(transport_cost.get('value'), 4)} / {transport_cost.get('per') or 'n/a'}"),
                        ("Source cout", transport_cost.get("source") or order_terms.get("source") or "n/a"),
                    ])),
                ],
            ),
        }

    return {
        "nodes": node_payload,
        "edges": edge_payload,
    }


def percentile(values: list[float], q: float) -> float:
    if not values:
        return 0.0
    if len(values) == 1:
        return values[0]
    ordered = sorted(values)
    pos = (len(ordered) - 1) * max(0.0, min(1.0, q))
    lo = int(math.floor(pos))
    hi = int(math.ceil(pos))
    if lo == hi:
        return ordered[lo]
    frac = pos - lo
    return ordered[lo] * (1.0 - frac) + ordered[hi] * frac


def build_edge_metrics(
    raw: dict[str, Any],
    supplier_shipments_csv: Path,
    *,
    horizon_days: int | None = None,
) -> dict[str, dict[str, Any]]:
    rows = read_csv_rows(supplier_shipments_csv)
    if horizon_days and horizon_days > 0:
        horizon_end = horizon_days - 1
        rows = [
            row
            for row in rows
            if 0 <= int(to_float(row.get("day")) or 0) <= horizon_end
        ]
    shipment_rows_by_triplet: dict[tuple[str, str, str], list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        shipment_rows_by_triplet[
            (
                str(row.get("src_node_id") or ""),
                str(row.get("dst_node_id") or ""),
                str(row.get("item_id") or ""),
            )
        ].append(row)

    safety_time_by_pair: dict[tuple[str, str], float] = {}
    for node in (raw.get("nodes", []) or []):
        node_id = str(node.get("id") or "")
        for state in (((node.get("inventory") or {}).get("states") or [])):
            item_id = str(state.get("item_id") or "")
            mrp_policy = state.get("mrp_policy") or {}
            safety_time = max(0.0, to_float(mrp_policy.get("safety_time_days")) or 0.0)
            if node_id and item_id and safety_time > 0.0:
                safety_time_by_pair[(node_id, item_id)] = safety_time

    edge_metrics: dict[str, dict[str, Any]] = {}
    for edge in (raw.get("edges", []) or []):
        edge_id = str(edge.get("id") or "")
        src = str(edge.get("from") or "")
        dst = str(edge.get("to") or "")
        items = [str(item_id) for item_id in (edge.get("items") or []) if str(item_id or "")]
        if not edge_id or not src or not dst or not items:
            continue
        lead_values: list[float] = []
        qty_values: list[float] = []
        safety_times: list[float] = []
        active_items: list[str] = []
        for item_id in items:
            scoped_rows = shipment_rows_by_triplet.get((src, dst, item_id), [])
            if scoped_rows:
                active_items.append(item_id)
            for row in scoped_rows:
                lead_values.append(max(0.0, to_float(row.get("lead_days")) or 0.0))
                qty_values.append(max(0.0, to_float(row.get("shipped_qty")) or 0.0))
            safety = max(0.0, safety_time_by_pair.get((dst, item_id), 0.0))
            if safety > 0.0:
                safety_times.append(safety)
        planned_lead_days = max(1.0, to_float(((edge.get("lead_time") or {}).get("mean"))) or 1.0)
        avg_lead_days = statistics.mean(lead_values) if lead_values else planned_lead_days
        min_lead_days = min(lead_values) if lead_values else planned_lead_days
        max_lead_days = max(lead_values) if lead_values else planned_lead_days
        lead_std_days = statistics.pstdev(lead_values) if len(lead_values) > 1 else 0.0
        qty_distinct = len({round(v, 6) for v in qty_values}) if qty_values else 0
        safety_time_days = max(safety_times) if safety_times else 0.0
        edge_metrics[edge_id] = {
            "shipment_rows": len(qty_values),
            "active_items": active_items,
            "avg_lead_days": round(avg_lead_days, 2),
            "min_lead_days": round(min_lead_days, 2),
            "max_lead_days": round(max_lead_days, 2),
            "lead_std_days": round(lead_std_days, 2),
            "lead_p50_days": round(percentile(lead_values, 0.5), 2) if lead_values else round(planned_lead_days, 2),
            "lead_p90_days": round(percentile(lead_values, 0.9), 2) if lead_values else round(planned_lead_days, 2),
            "distinct_lead_days": len({round(v, 6) for v in lead_values}) if lead_values else 1,
            "planned_lead_days": round(planned_lead_days, 2),
            "avg_shipped_qty": round(statistics.mean(qty_values), 4) if qty_values else 0.0,
            "distinct_shipped_qty": qty_distinct,
            "qty_constant_flag": bool(qty_values) and qty_distinct <= 1,
            "safety_time_days": round(safety_time_days, 2),
            "effective_lead_days": round(avg_lead_days + safety_time_days, 2),
        }
    return edge_metrics


def factory_like_node_ids(raw: dict[str, Any]) -> set[str]:
    ids: set[str] = set()
    for node in raw.get("nodes", []) or []:
        node_id = str(node.get("id") or "")
        node_type = str(node.get("type") or "")
        if not node_id:
            continue
        if is_pilotage_hidden_node(node_id):
            continue
        if node_type == "factory" or (node_type == "supplier_dc" and (node.get("processes") or [])):
            ids.add(node_id)
    return ids


def build_factory_hover_series(
    raw: dict[str, Any],
    sim_input_stocks_csv: Path,
    sim_output_products_csv: Path,
) -> dict[str, Any]:
    nodes = raw.get("nodes", []) or []
    items = raw.get("items", []) or []

    factory_ids = factory_like_node_ids(raw)
    node_name = {str(n.get("id")): str(n.get("name") or str(n.get("id"))) for n in nodes}

    item_label: dict[str, str] = {}
    for it in items:
        iid = str(it.get("id"))
        code = str(it.get("code") or "").strip()
        name = str(it.get("name") or "").strip()
        item_label[iid] = code if code else (name if name else iid)

    in_unit_by_node_item: dict[tuple[str, str], str] = {}
    out_unit_by_node_item: dict[tuple[str, str], str] = {}
    for n in nodes:
        nid = str(n.get("id"))
        inv = n.get("inventory") or {}
        for st in (inv.get("states") or []):
            item_id = str(st.get("item_id"))
            uom = str(st.get("uom") or "").strip()
            if item_id and uom:
                in_unit_by_node_item[(nid, item_id)] = uom
        for p in (n.get("processes") or []):
            for inp in (p.get("inputs") or []):
                item_id = str(inp.get("item_id"))
                uom = str(inp.get("ratio_unit") or "").strip()
                if item_id and uom and (nid, item_id) not in in_unit_by_node_item:
                    in_unit_by_node_item[(nid, item_id)] = uom
            for out in (p.get("outputs") or []):
                item_id = str(out.get("item_id"))
                uom = str(out.get("uom") or "").strip()
                if item_id and uom:
                    out_unit_by_node_item[(nid, item_id)] = uom

    incoming_raw: dict[str, dict[str, list[tuple[int, float]]]] = defaultdict(lambda: defaultdict(list))
    if sim_input_stocks_csv.exists():
        with sim_input_stocks_csv.open("r", encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                node_id = str(row.get("node_id") or "")
                if node_id not in factory_ids:
                    continue
                item_id = str(row.get("item_id") or "")
                day = int(to_float(row.get("day")) or 0)
                if day == 0:
                    # Day 0 should reflect the seeded source snapshot before any
                    # same-day consumption, so the graph starts from the true
                    # initial stock photo rather than the post-day state.
                    val = to_float(row.get("stock_before_production"))
                    if val is None:
                        val = to_float(row.get("stock_end_of_day")) or 0.0
                else:
                    val = to_float(row.get("stock_end_of_day"))
                    if val is None:
                        val = to_float(row.get("stock_before_production")) or 0.0
                incoming_raw[node_id][item_id].append((day, val))

    outgoing_raw: dict[str, dict[str, list[tuple[int, float, float, float | None]]]] = defaultdict(lambda: defaultdict(list))
    if sim_output_products_csv.exists():
        with sim_output_products_csv.open("r", encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                node_id = str(row.get("node_id") or "")
                if node_id not in factory_ids:
                    continue
                item_id = str(row.get("item_id") or "")
                day = int(to_float(row.get("day")) or 0)
                prod = float(to_float(row.get("produced_qty")) or 0.0)
                cum = float(to_float(row.get("cum_produced_qty")) or 0.0)
                stock_end = to_float(row.get("stock_end_of_day"))
                outgoing_raw[node_id][item_id].append((day, prod, cum, stock_end))

    out: dict[str, Any] = {}
    for node_id in sorted(factory_ids):
        incoming = []
        for item_id, pts in sorted(incoming_raw[node_id].items(), key=lambda x: item_label.get(x[0], x[0])):
            pts_sorted = sorted(pts, key=lambda x: x[0])
            incoming.append(
                {
                    "item_id": item_id,
                    "item_label": item_label.get(item_id, item_id),
                    "unit": in_unit_by_node_item.get((node_id, item_id), ""),
                    "days": [p[0] for p in pts_sorted],
                    "values": [p[1] for p in pts_sorted],
                }
            )

        outgoing = []
        for item_id, pts in sorted(outgoing_raw[node_id].items(), key=lambda x: item_label.get(x[0], x[0])):
            pts_sorted = sorted(pts, key=lambda x: x[0])
            outgoing.append(
                {
                    "item_id": item_id,
                    "item_label": item_label.get(item_id, item_id),
                    "unit": out_unit_by_node_item.get((node_id, item_id), "unit/day"),
                    "days": [p[0] for p in pts_sorted],
                    "values": [p[1] for p in pts_sorted],
                    "cum_values": [p[2] for p in pts_sorted],
                    "stock_values": [p[3] for p in pts_sorted],
                }
            )

        if incoming or outgoing:
            out[node_id] = {
                "node_id": node_id,
                "node_name": node_name.get(node_id, node_id),
                "incoming": incoming,
                "outgoing": outgoing,
            }

    return out


def build_factory_hover_images(
    raw: dict[str, Any],
    sim_input_stocks_csv: Path,
    sim_output_products_csv: Path,
    input_arrivals_csv: Path,
    supplier_shipments_csv: Path,
    supplier_stocks_csv: Path,
    input_png_dir: Path,
    output_png_dir: Path,
    demand_service_csv: Path,
    production_constraint_csv: Path,
    mrp_trace_csv: Path | None = None,
) -> dict[str, Any]:
    nodes = raw.get("nodes", []) or []
    incoming_items, outgoing_items = build_edge_item_sets(raw)
    _ = demand_service_csv
    constraint_rows = read_csv_rows(production_constraint_csv)
    input_arrival_rows = read_csv_rows(input_arrivals_csv)
    supplier_shipment_rows = read_csv_rows(supplier_shipments_csv)
    mrp_trace_rows = read_csv_rows(mrp_trace_csv) if mrp_trace_csv is not None and mrp_trace_csv.exists() else []
    factory_ids = sorted(factory_like_node_ids(raw))
    node_by_id = {str(n.get("id")): n for n in nodes}
    item_labels = item_label_lookup(raw)
    out: dict[str, Any] = {}
    for factory_id in factory_ids:
        node_type = str((node_by_id.get(factory_id) or {}).get("type") or "")
        safe_factory = re.sub(r"[^A-Za-z0-9_-]+", "_", factory_id)
        detail = build_factory_hover_series(raw, sim_input_stocks_csv, sim_output_products_csv).get(factory_id) or {}
        incoming = resolve_plot_payload(
            input_png_dir,
            Path("factories") / "input_stocks" / f"production_input_stocks_by_material_{safe_factory}.png",
            f"production_input_stocks_by_material_{safe_factory}.png",
        )
        if incoming is None:
            incoming = descriptor_series_to_figure(
                detail.get("incoming") or [],
                title=f"{factory_id} - stocks intrants",
                y_label="Quantite",
            )
        outgoing = descriptor_series_to_figure(
            detail.get("outgoing") or [],
            title=f"{factory_id} - stock produits finis",
            y_label="Quantite",
            value_key="stock_values",
        )
        if outgoing is None:
            outgoing = resolve_plot_payload(
                output_png_dir,
                Path("factories") / "output_products" / f"production_output_products_by_factory_{safe_factory}.png",
                f"production_output_products_by_factory_{safe_factory}.png",
            )
        if outgoing is None:
            outgoing = resolve_plot_payload(
                output_png_dir,
                Path("factories") / "output_products" / "production_output_products.png",
                "production_output_products.png",
            )
        if incoming is None and detail:
            incoming = descriptor_series_to_figure(
                detail.get("incoming") or [],
                title=f"{factory_id} - stocks intrants",
                y_label="Quantite",
            )
        incoming_descriptors = detail.get("incoming") or []
        incoming_stock_series_by_item: dict[str, tuple[str, list[tuple[int, float]]]] = {}
        incoming_unit_by_item: dict[str, str] = {}
        for descriptor in incoming_descriptors:
            item_id = str(descriptor.get("item_id") or "").strip()
            item_label = str(descriptor.get("item_label") or item_id).strip()
            if not item_id or not item_label:
                continue
            pts = list(zip(descriptor.get("days") or [], descriptor.get("values") or []))
            if pts:
                incoming_stock_series_by_item[item_id] = (f"{item_label} - stock physique", pts)
            incoming_unit_by_item[item_id] = normalize_quantity_unit(descriptor.get("unit"))
        incoming_stock_series = {label: pts for label, pts in incoming_stock_series_by_item.values() if pts}
        incoming_item_ids: set[str] = {
            str(descriptor.get("item_id") or "")
            for descriptor in incoming_descriptors
            if str(descriptor.get("item_id") or "")
        }
        incoming_arrival_series_by_item: dict[str, tuple[str, list[tuple[int, float]]]] = {}
        incoming_item_labels: set[str] = set()
        for descriptor in incoming_descriptors:
            item_label = str(descriptor.get("item_label") or descriptor.get("item_id") or "").strip()
            if item_label:
                incoming_item_labels.add(item_label)
        if input_arrival_rows:
            item_ids = sorted(
                {
                    str(row.get("item_id") or "")
                    for row in input_arrival_rows
                    if str(row.get("node_id") or "") == factory_id
                }
            )
            for row in input_arrival_rows:
                if str(row.get("node_id") or "") != factory_id:
                    continue
                item_id = str(row.get("item_id") or "")
                uom = str(row.get("uom") or "").strip()
                if item_id and uom:
                    incoming_unit_by_item[item_id] = normalize_quantity_unit(uom)
            for item_id in item_ids:
                if is_simulation_hidden_item(item_id):
                    continue
                arrival_pts = aggregate_daily_series(
                    input_arrival_rows,
                    value_field="arrived_qty",
                    node_field="node_id",
                    node_id=factory_id,
                    item_ids={item_id},
                )
                if arrival_pts:
                    item_label = item_labels.get(item_id, compact_item_label(item_id))
                    incoming_item_labels.add(item_label)
                    incoming_item_ids.add(item_id)
                    incoming_arrival_series_by_item[item_id] = (f"{item_label} - reception", arrival_pts)
                    incoming_unit_by_item.setdefault(item_id, "unite non renseignee")
        incoming_arrival_series = {label: pts for label, pts in incoming_arrival_series_by_item.values() if pts}
        display_factory_id = display_node_label(factory_id)
        incoming_title = f"{display_factory_id} - stocks et receptions intrants"
        top_title = f"{display_factory_id} - stock intrants"
        bottom_title = f"{display_factory_id} - receptions intrants"
        if is_upstream_internal_site(factory_id):
            sorted_incoming_items = sorted(incoming_item_labels)
            if len(sorted_incoming_items) == 1:
                incoming_item_label = sorted_incoming_items[0]
                incoming_title = f"{display_factory_id} - intrant {incoming_item_label}: stock et arrivages"
                top_title = f"{display_factory_id} - stock intrant {incoming_item_label}"
                bottom_title = f"{display_factory_id} - arrivages intrant {incoming_item_label}"
            else:
                incoming_title = f"{display_factory_id} - stocks et arrivages intrants"
                bottom_title = f"{display_factory_id} - arrivages intrants"
        if incoming_stock_series or incoming_arrival_series:
            all_physical_target_series_by_item = mrp_physical_target_series_by_item(
                mrp_trace_rows,
                node_id=factory_id,
                item_ids=incoming_item_ids,
                item_labels=item_labels,
            )
            unit_groups: dict[str, set[str]] = defaultdict(set)
            for item_id in incoming_item_ids:
                if is_simulation_hidden_item(item_id):
                    continue
                unit = normalize_quantity_unit(incoming_unit_by_item.get(item_id))
                unit_category = unit
                if unit == "KG" and is_significant_kg_overstock(
                    incoming_stock_series_by_item.get(item_id),
                    all_physical_target_series_by_item.get(item_id),
                ):
                    unit_category = KG_OVERSTOCK_CATEGORY_LABEL
                unit_groups[unit_category].add(item_id)
            stock_entries: list[dict[str, Any]] = []
            demand_entries: list[dict[str, Any]] = []
            mrp_entries: list[dict[str, Any]] = []
            receipt_entries: list[dict[str, Any]] = []
            for unit, scoped_item_ids in sorted(unit_groups.items(), key=lambda kv: (kv[0] == "unite non renseignee", kv[0])):
                display_unit = display_unit_for_category(unit)
                scoped_stock_series = {
                    label: pts
                    for item_id, (label, pts) in incoming_stock_series_by_item.items()
                    if item_id in scoped_item_ids and pts
                }
                scoped_arrival_series = {
                    label: pts
                    for item_id, (label, pts) in incoming_arrival_series_by_item.items()
                    if item_id in scoped_item_ids and pts
                }
                physical_target_series_by_item = mrp_physical_target_series_by_item(
                    mrp_trace_rows,
                    node_id=factory_id,
                    item_ids=scoped_item_ids,
                    item_labels=item_labels,
                )
                physical_top_series, physical_top_styles = comparable_stock_series_for_items(
                    scoped_item_ids,
                    stock_series_by_item=incoming_stock_series_by_item,
                    target_series_by_item=physical_target_series_by_item,
                    item_labels=item_labels,
                )
                physical_figure = build_line_chart_figure(
                    physical_top_series,
                    title=f"{display_factory_id} - stock physique vs consigne physique ({unit})",
                    y_label=f"Stock physique ({display_unit})",
                    series_styles=physical_top_styles,
                    lot_trace_category="factory_input",
                    note=(
                        "Vue physique valorisable: stock reel et consigne physique "
                        "= max(cible de position MRP - receptions futures MRP, 0). "
                        "La consigne est lissee sur 30 jours pour eviter les crenaux journaliers de pilotage. "
                        "Un stock durablement au-dessus de cette consigne correspond a du stock immobilise; "
                        "la valeur industrielle de stock immobilise se compare a cette vue physique. "
                        "La vraie cible MRP de position et le pipeline restent dans Pilotage MRP."
                    ),
                )
                gross_daily_requirement_series = mrp_metric_series_by_item(
                    mrp_trace_rows,
                    node_id=factory_id,
                    item_ids=scoped_item_ids,
                    item_labels=item_labels,
                    value_field="bb_demand_signal_raw_qty",
                    label_suffix="besoin brut / jour",
                )
                demand_figure = build_line_chart_figure(
                    gross_daily_requirement_series,
                    title=f"{display_factory_id} - besoins intrants quotidiens ({unit})",
                    y_label=f"Besoin / jour ({display_unit})",
                    series_styles=metric_series_styles_for_items(
                        scoped_item_ids,
                        item_labels=item_labels,
                        label_suffix="besoin brut / jour",
                        dash="solid",
                        width=1.7,
                    ),
                    lot_trace_category="factory_input",
                    note=(
                        "Besoin brut journalier issu de la demande/BOM avant couverture par le stock, "
                        "les receptions futures et les regles de lot. Le besoin net a commander reste "
                        "dans Pilotage MRP."
                    ),
                )
                inventory_position_series = mrp_metric_series_by_item(
                    mrp_trace_rows,
                    node_id=factory_id,
                    item_ids=scoped_item_ids,
                    item_labels=item_labels,
                    value_field="inventory_position_qty",
                    label_suffix="position inventaire MRP",
                )
                target_position_series = mrp_metric_series_by_item(
                    mrp_trace_rows,
                    node_id=factory_id,
                    item_ids=scoped_item_ids,
                    item_labels=item_labels,
                    value_field="target_stock_display_qty",
                    label_suffix="cible MRP (position, moy. 30j)",
                    rolling_window_days=MRP_TARGET_DISPLAY_SMOOTHING_DAYS,
                )
                future_receipt_series = mrp_metric_series_by_item(
                    mrp_trace_rows,
                    node_id=factory_id,
                    item_ids=scoped_item_ids,
                    item_labels=item_labels,
                    value_field="recv_prev_future_qty",
                    label_suffix="receptions futures MRP",
                )
                net_requirement_series = mrp_metric_series_by_item(
                    mrp_trace_rows,
                    node_id=factory_id,
                    item_ids=scoped_item_ids,
                    item_labels=item_labels,
                    value_field="bn_qty",
                    label_suffix="besoin net MRP",
                )
                mrp_top_series = {
                    **inventory_position_series,
                    **target_position_series,
                }
                mrp_bottom_series = {
                    **future_receipt_series,
                    **net_requirement_series,
                }
                mrp_top_styles = {
                    **metric_series_styles_for_items(
                        scoped_item_ids,
                        item_labels=item_labels,
                        label_suffix="position inventaire MRP",
                        dash="solid",
                        width=1.9,
                    ),
                    **metric_series_styles_for_items(
                        scoped_item_ids,
                        item_labels=item_labels,
                        label_suffix="cible MRP (position, moy. 30j)",
                        dash="dash",
                        width=1.55,
                    ),
                }
                mrp_bottom_styles = {
                    **metric_series_styles_for_items(
                        scoped_item_ids,
                        item_labels=item_labels,
                        label_suffix="receptions futures MRP",
                        dash="dot",
                        width=1.45,
                    ),
                    **metric_series_styles_for_items(
                        scoped_item_ids,
                        item_labels=item_labels,
                        label_suffix="besoin net MRP",
                        dash="dash",
                        width=1.45,
                    ),
                }
                mrp_figure = build_dual_line_multi_panel_figure(
                    title=f"{display_factory_id} - pilotage MRP ({unit})",
                    top_title=f"{display_factory_id} - position inventaire vs cible MRP ({unit})",
                    top_y_label=f"Position inventaire / cible MRP ({display_unit})",
                    top_series_map=mrp_top_series,
                    bottom_title=f"{display_factory_id} - receptions futures et besoin net MRP ({unit})",
                    bottom_y_label=f"Receptions futures / besoin net ({display_unit})",
                    bottom_series_map=mrp_bottom_series,
                    top_series_styles=mrp_top_styles,
                    bottom_series_styles=mrp_bottom_styles,
                    lot_trace_category="factory_input",
                )
                receipt_figure = build_line_chart_figure(
                    scoped_arrival_series,
                    title=f"{display_factory_id} - receptions physiques intrants ({unit})",
                    y_label=f"Receptions ({display_unit})",
                    step_like=True,
                    series_styles=series_styles_for_item_entries(
                        scoped_item_ids,
                        incoming_arrival_series_by_item,
                        item_labels=item_labels,
                        dash="dot",
                        width=1.55,
                    ),
                    lot_trace_category="factory_input",
                )
                if physical_figure is not None:
                    stock_entries.append({"label": unit, "asset": {"figure": physical_figure}})
                if demand_figure is not None:
                    demand_entries.append({"label": unit, "asset": {"figure": demand_figure}})
                if mrp_figure is not None:
                    mrp_entries.append({"label": unit, "asset": {"figure": mrp_figure}})
                if receipt_figure is not None:
                    receipt_entries.append({"label": unit, "asset": {"figure": receipt_figure}})
            demand_asset = (
                {"bundle": demand_entries}
                if len(demand_entries) > 1
                else (demand_entries[0]["asset"] if demand_entries else None)
            )
            family_entries = [
                {
                    "label": "Stock physique",
                    "asset": {"bundle": stock_entries} if len(stock_entries) > 1 else (stock_entries[0]["asset"] if stock_entries else None),
                },
                {
                    "label": "Pilotage MRP",
                    "asset": {"bundle": mrp_entries} if len(mrp_entries) > 1 else (mrp_entries[0]["asset"] if mrp_entries else None),
                },
                {
                    "label": "Receptions",
                    "asset": {"bundle": receipt_entries} if len(receipt_entries) > 1 else (receipt_entries[0]["asset"] if receipt_entries else None),
                },
            ]
            family_entries = [entry for entry in family_entries if entry.get("asset")]
            if family_entries:
                incoming = {"bundle": family_entries} if len(family_entries) > 1 else family_entries[0]["asset"]
        else:
            demand_asset = None
        outgoing_descriptors = detail.get("outgoing") or []
        outgoing_stock_series_by_item: dict[str, tuple[str, list[tuple[int, float]]]] = {}
        outgoing_unit_by_item: dict[str, str] = {}
        for descriptor in outgoing_descriptors:
            item_id = str(descriptor.get("item_id") or "").strip()
            item_label = str(descriptor.get("item_label") or item_id).strip()
            if not item_id or not item_label:
                continue
            pts = list(zip(descriptor.get("days") or [], descriptor.get("stock_values") or []))
            if pts:
                outgoing_stock_series_by_item[item_id] = (f"{item_label} - stock", pts)
            outgoing_unit_by_item[item_id] = normalize_quantity_unit(descriptor.get("unit"))
        outgoing_stock_series = {label: pts for label, pts in outgoing_stock_series_by_item.values() if pts}
        outgoing_item_ids: set[str] = {
            str(descriptor.get("item_id") or "")
            for descriptor in outgoing_descriptors
            if str(descriptor.get("item_id") or "")
        }
        def outgoing_stock_asset_for_units(
            *,
            outbound_series_by_item: dict[str, tuple[str, list[tuple[int, float]]]] | None = None,
            outbound_title: str = "expeditions par item",
        ) -> dict[str, Any] | None:
            if not outgoing_stock_series_by_item:
                return None
            outbound_series_by_item = outbound_series_by_item or {}
            unit_groups: dict[str, set[str]] = defaultdict(set)
            for item_id in outgoing_item_ids:
                if is_simulation_hidden_item(item_id):
                    continue
                unit_groups[normalize_quantity_unit(outgoing_unit_by_item.get(item_id))].add(item_id)
            unit_entries: list[dict[str, Any]] = []
            for unit, scoped_item_ids in sorted(unit_groups.items(), key=lambda kv: (kv[0] == "unite non renseignee", kv[0])):
                scoped_stock_series = {
                    label: pts
                    for item_id, (label, pts) in outgoing_stock_series_by_item.items()
                    if item_id in scoped_item_ids and pts
                }
                scoped_outbound_series = {
                    label: pts
                    for item_id, (label, pts) in outbound_series_by_item.items()
                    if item_id in scoped_item_ids and pts
                }
                target_series, target_styles = stock_target_overlay_series(
                    mrp_trace_rows,
                    node_id=factory_id,
                    item_ids=scoped_item_ids,
                    item_labels=item_labels,
                )
                top_series = {**scoped_stock_series, **target_series}
                top_styles = {
                    **{label: {"width": 1.9} for label in scoped_stock_series},
                    **target_styles,
                }
                if scoped_outbound_series:
                    figure = build_dual_line_multi_panel_figure(
                        title=f"{display_factory_id} - stock et {outbound_title} ({unit})",
                        top_title=f"{display_factory_id} - stock produits ({unit})",
                        top_y_label=f"Stock ({unit})",
                        top_series_map=top_series,
                        bottom_title=f"{display_factory_id} - {outbound_title} ({unit})",
                        bottom_y_label=f"Expeditions ({unit})",
                        bottom_series_map=scoped_outbound_series,
                        top_series_styles=top_styles,
                        bottom_step_like=True,
                        lot_trace_category="factory_output",
                    )
                else:
                    figure = build_line_chart_figure(
                        top_series,
                        title=f"{display_factory_id} - stock produits avec cible ({unit})",
                        y_label=f"Quantite ({unit})",
                        note=(
                            "Lecture metier: les series sont separees par unite pour eviter de comparer "
                            "des kilogrammes, grammes, metres et unites sur le meme axe."
                        ),
                        series_styles=top_styles,
                        lot_trace_category="factory_output",
                    )
                if figure is not None:
                    unit_entries.append({"label": unit, "asset": {"figure": figure}})
            if not unit_entries:
                return None
            return {"bundle": unit_entries} if len(unit_entries) > 1 else unit_entries[0]["asset"]
        if is_upstream_internal_site(factory_id) and supplier_shipment_rows:
            outbound_series_by_item: dict[str, tuple[str, list[tuple[int, float]]]] = {}
            outbound_item_ids = sorted(
                {
                    str(row.get("item_id") or "")
                    for row in supplier_shipment_rows
                    if str(row.get("src_node_id") or "") == factory_id
                }
            )
            for item_id in outbound_item_ids:
                if is_simulation_hidden_item(item_id):
                    continue
                shipped_pts = aggregate_daily_series(
                    supplier_shipment_rows,
                    value_field="shipped_qty",
                    node_field="src_node_id",
                    node_id=factory_id,
                    item_ids={item_id},
                )
                if shipped_pts:
                    item_label = item_labels.get(item_id, compact_item_label(item_id))
                    outbound_series_by_item[item_id] = (item_label, shipped_pts)
            if outbound_series_by_item:
                grouped_outgoing = outgoing_stock_asset_for_units(
                    outbound_series_by_item=outbound_series_by_item,
                    outbound_title="expeditions PFI par item",
                )
                if grouped_outgoing is not None:
                    outgoing = grouped_outgoing
                elif not outgoing_stock_series:
                    figure = build_line_chart_figure(
                        {label: pts for label, pts in outbound_series_by_item.values()},
                        title=f"{display_factory_id} - expeditions PFI par item",
                        y_label="Quantite",
                        step_like=True,
                        lot_trace_category="factory_output",
                    )
                    if figure is not None:
                        outgoing = {"figure": figure}
        elif outgoing_stock_series:
            grouped_outgoing = outgoing_stock_asset_for_units()
            if grouped_outgoing is not None:
                outgoing = grouped_outgoing
        factory_rows = [row for row in constraint_rows if str(row.get("node_id") or "") == factory_id]
        production_gantt_figure = build_factory_production_gantt_figure(raw, factory_id, factory_rows, item_labels)
        production_gantt = {"figure": production_gantt_figure} if production_gantt_figure is not None else None
        desired_series = aggregate_daily_series(factory_rows, value_field="desired_qty")
        normal_actual_by_day: dict[int, float] = defaultdict(float)
        recovery_actual_by_day: dict[int, float] = defaultdict(float)
        for row in factory_rows:
            day = int(to_float(row.get("day")) or 0)
            actual_qty = max(0.0, to_float(row.get("actual_qty")) or 0.0)
            if actual_qty <= 0:
                continue
            requested_today_qty = max(0.0, to_float(row.get("campaign_requested_qty")) or 0.0)
            requested_today_lots = max(0.0, to_float(row.get("requested_lot_starts")) or 0.0)
            remaining_at_start = max(0.0, to_float(row.get("campaign_remaining_start_qty")) or 0.0)
            is_recovery = remaining_at_start > 0 and requested_today_qty <= 0 and requested_today_lots <= 0
            if is_recovery:
                recovery_actual_by_day[day] += actual_qty
            else:
                normal_actual_by_day[day] += actual_qty
        actual_series = [(day, qty) for day, qty in sorted(normal_actual_by_day.items())]
        recovery_actual_series = [(day, qty) for day, qty in sorted(recovery_actual_by_day.items())]
        capacity_series = aggregate_daily_series(factory_rows, value_field="cap_qty")
        shortfall_series = aggregate_daily_series(factory_rows, value_field="shortfall_vs_desired_qty")
        lot_plan_shortfall_series = aggregate_daily_series(factory_rows, value_field="shortfall_vs_lot_plan_qty")
        production_execution = build_factory_industrial_payload(
            desired_series,
            actual_series,
            recovery_actual_series,
            capacity_series,
            shortfall_series,
            lot_plan_shortfall_series,
            factory_id=factory_id,
        )
        if production_execution is not None:
            outgoing_entries = [
                {"label": "Execution production", "asset": production_execution},
                {"label": "Stock produits / expeditions", "asset": outgoing},
                {"label": "Planning lots", "asset": production_gantt},
            ]
            outgoing_bundle = {"bundle": [entry for entry in outgoing_entries if entry.get("asset")]}
            outgoing = outgoing_bundle if outgoing_bundle["bundle"] else outgoing
        elif production_gantt is not None and outgoing is not None:
            outgoing_entries = [
                {"label": "Stock produits / expeditions", "asset": outgoing},
                {"label": "Planning lots", "asset": production_gantt},
            ]
            outgoing_bundle = {"bundle": [entry for entry in outgoing_entries if entry.get("asset")]}
            outgoing = outgoing_bundle if len(outgoing_bundle["bundle"]) > 1 else outgoing
        inbound_lead_days = {}
        for edge in raw.get("edges", []) or []:
            if str(edge.get("to") or "") != factory_id:
                continue
            supplier_id = str(edge.get("from") or "")
            lead_days = max(1.0, to_float(((edge.get("lead_time") or {}).get("mean"))) or 1.0)
            prev = inbound_lead_days.get(supplier_id)
            inbound_lead_days[supplier_id] = min(prev, lead_days) if prev is not None else lead_days
        auxiliary = demand_asset
        if node_type == "supplier_dc":
            site_stock_payload = build_site_stock_payload(
                raw,
                supplier_stocks_csv,
                factory_id,
                title=f"{factory_id} - stocks complets du site",
            )
            if auxiliary is None and production_gantt is not None:
                auxiliary = production_gantt
            elif site_stock_payload is not None:
                if incoming is None:
                    incoming = site_stock_payload
                elif auxiliary is None:
                    auxiliary = site_stock_payload
        elif auxiliary is None and production_gantt is not None:
            auxiliary = production_gantt
        if not incoming and not outgoing and not auxiliary:
            continue
        out[factory_id] = {"incoming": incoming, "outgoing": outgoing, "third": auxiliary}
    return out


def descriptor_series_to_figure(
    descriptors: list[dict[str, Any]],
    *,
    title: str,
    y_label: str,
    value_key: str = "values",
) -> dict[str, Any] | None:
    series_map: dict[str, list[tuple[int, float]]] = {}
    for descriptor in descriptors:
        label = str(descriptor.get("item_label") or descriptor.get("item_id") or "").strip()
        if is_simulation_hidden_item(str(descriptor.get("item_id") or "")):
            continue
        days = descriptor.get("days") or []
        values = descriptor.get(value_key) or []
        if not label or not days or not values:
            continue
        points = []
        for day, value in zip(days, values):
            if value is None:
                continue
            try:
                points.append((int(day), float(value)))
            except Exception:
                continue
        if points:
            series_map[label] = points
    figure = build_line_chart_figure(series_map, title=title, y_label=y_label)
    if figure is None:
        return None
    return {"figure": figure}


def build_factory_production_gantt_figure(
    raw: dict[str, Any],
    factory_id: str,
    factory_rows: list[dict[str, str]],
    item_labels: dict[str, str],
) -> dict[str, Any] | None:
    process_tau_by_item: dict[str, float] = {}
    node = next((n for n in (raw.get("nodes") or []) if str(n.get("id") or "") == factory_id), None)
    for proc in (node or {}).get("processes") or []:
        tau_process = max(0.0, to_float(((proc.get("wip") or {}).get("tau_process"))) or 0.0)
        for out in proc.get("outputs") or []:
            item_id = str(out.get("item_id") or "")
            if item_id:
                process_tau_by_item[item_id] = tau_process

    rows: list[dict[str, Any]] = []
    for row in sorted(factory_rows, key=lambda r: (int(to_float(r.get("day")) or 0), str(r.get("output_item_id") or ""))):
        item_id = str(row.get("output_item_id") or "")
        if not item_id or is_simulation_hidden_item(item_id):
            continue
        lot_starts = max(0.0, to_float(row.get("actual_lot_starts")) or 0.0)
        if lot_starts <= 1e-9:
            continue
        started_qty = max(0.0, to_float(row.get("campaign_started_qty")) or 0.0)
        if started_qty <= 1e-9:
            started_qty = max(0.0, to_float(row.get("actual_qty")) or 0.0)
        if started_qty <= 1e-9:
            continue
        day = int(to_float(row.get("day")) or 0)
        cap_qty = max(0.0, to_float(row.get("cap_qty")) or 0.0)
        capacity_mode = str(row.get("capacity_limit_mode") or "")
        if cap_qty > 1e-9:
            duration = max(1.0, float(math.ceil(started_qty / cap_qty)))
            duration_basis = "quantite / capacite journaliere"
        else:
            duration = 0.6
            duration_basis = "jalon de lancement (capacite non modelisee)"
        label = item_labels.get(item_id, compact_item_label(item_id))
        rows.append(
            {
                "lane": label,
                "item_id": item_id,
                "item_label": label,
                "start": day,
                "end": day + duration,
                "duration": duration,
                "duration_basis": duration_basis,
                "capacity_mode": capacity_mode,
                "cap_qty": round(cap_qty, 6),
                "tau_process": round(process_tau_by_item.get(item_id, 0.0), 6),
                "qty": round(started_qty, 6),
                "lots": round(lot_starts, 6),
                "lot_policy": str(row.get("lot_policy_mode") or ""),
                "binding_cause": str(row.get("binding_cause") or "none"),
            }
        )
    if not rows:
        return None
    return {
        "kind": "gantt",
        "title": f"{display_node_label(factory_id)} - planning production lots",
        "lot_trace_category": "production",
        "x_label": "Jour",
        "y_label": "Produit",
        "note": "Barres = lots lances. Duree = quantite/capacite si capacite modelisee; sinon jalon court. Ce n'est pas une charge usine complete.",
        "rows": rows,
    }


def item_label_lookup(raw: dict[str, Any]) -> dict[str, str]:
    lookup: dict[str, str] = {}
    for item in raw.get("items", []) or []:
        item_id = str(item.get("id") or "")
        code = str(item.get("code") or "").strip()
        name = str(item.get("name") or "").strip()
        base_label = code if code else (name if name else item_id)
        lookup[item_id] = ITEM_DISPLAY_REFERENCE_NOTES.get(item_id, base_label)
    return lookup


MRP_TARGET_DISPLAY_SMOOTHING_DAYS = 30
KG_OVERSTOCK_CATEGORY_LABEL = "KG - surstock"
KG_OVERSTOCK_MIN_RATIO = 3.0
KG_OVERSTOCK_MIN_EXCESS_QTY = 5_000.0


def rolling_average_points(points: list[tuple[int, float]], window_days: int) -> list[tuple[int, float]]:
    if window_days <= 1 or len(points) <= 1:
        return points
    ordered = sorted(points, key=lambda item: item[0])
    out: list[tuple[int, float]] = []
    values: list[float] = []
    value_sum = 0.0
    for day, value in ordered:
        value = float(value)
        values.append(value)
        value_sum += value
        if len(values) > window_days:
            value_sum -= values.pop(0)
        out.append((day, value_sum / float(len(values))))
    return out


def mean_positive_series_value(points: list[tuple[int, float]]) -> float:
    values = [float(value) for _, value in points if value is not None and math.isfinite(float(value))]
    return statistics.mean(values) if values else 0.0


def is_significant_kg_overstock(
    stock_entry: tuple[str, list[tuple[int, float]]] | None,
    target_entry: tuple[str, list[tuple[int, float]]] | None,
) -> bool:
    if not stock_entry or not target_entry:
        return False
    stock_mean = mean_positive_series_value(stock_entry[1])
    target_mean = mean_positive_series_value(target_entry[1])
    if target_mean <= 1e-9:
        return False
    excess_qty = stock_mean - target_mean
    if excess_qty < KG_OVERSTOCK_MIN_EXCESS_QTY:
        return False
    return stock_mean / target_mean >= KG_OVERSTOCK_MIN_RATIO


def display_unit_for_category(unit_category: str) -> str:
    if unit_category == KG_OVERSTOCK_CATEGORY_LABEL:
        return "KG"
    return unit_category


def stock_target_overlay_series(
    mrp_trace_rows: list[dict[str, str]],
    *,
    node_id: str,
    item_ids: set[str],
    item_labels: dict[str, str],
    label_suffix: str = "cible MRP",
) -> tuple[dict[str, list[tuple[int, float]]], dict[str, dict[str, Any]]]:
    if not mrp_trace_rows or not node_id or not item_ids:
        return {}, {}
    series_map: dict[str, list[tuple[int, float]]] = {}
    series_styles: dict[str, dict[str, Any]] = {}
    for item_id in sorted(item_ids):
        if is_simulation_hidden_item(item_id):
            continue
        target_pts: list[tuple[int, float]] = []
        for field in ("target_stock_display_qty", "target_stock_qty", "safety_floor_qty"):
            pts = aggregate_daily_series(
                mrp_trace_rows,
                value_field=field,
                node_field="node_id",
                node_id=node_id,
                item_ids={item_id},
            )
            if any(abs(value) > 1e-9 for _, value in pts):
                target_pts = pts
                break
        if not target_pts:
            continue
        target_pts = rolling_average_points(target_pts, MRP_TARGET_DISPLAY_SMOOTHING_DAYS)
        label = (
            f"{item_labels.get(item_id, compact_item_label(item_id))} - "
            f"{label_suffix} (moy. 30j)"
        )
        series_map[label] = target_pts
        series_styles[label] = {"color": "#2563eb", "width": 1.8, "dash": "dash"}
    return series_map, series_styles


def mrp_inventory_position_overlay_series(
    mrp_trace_rows: list[dict[str, str]],
    *,
    node_id: str,
    item_ids: set[str],
    item_labels: dict[str, str],
) -> tuple[dict[str, list[tuple[int, float]]], dict[str, dict[str, Any]]]:
    if not mrp_trace_rows or not node_id or not item_ids:
        return {}, {}
    series_map: dict[str, list[tuple[int, float]]] = {}
    series_styles: dict[str, dict[str, Any]] = {}
    metric_specs = [
        (
            "recv_prev_future_qty",
            "receptions futures MRP",
            {"color": "#7c3aed", "width": 1.25, "dash": "dot"},
        ),
        (
            "inventory_position_qty",
            "position inventaire MRP",
            {"color": "#0f766e", "width": 2.0},
        ),
    ]
    for item_id in sorted(item_ids):
        if is_simulation_hidden_item(item_id):
            continue
        item_name = item_labels.get(item_id, compact_item_label(item_id))
        for field, suffix, style in metric_specs:
            pts = aggregate_daily_series(
                mrp_trace_rows,
                value_field=field,
                node_field="node_id",
                node_id=node_id,
                item_ids={item_id},
            )
            if not any(abs(value) > 1e-9 for _, value in pts):
                continue
            label = f"{item_name} - {suffix}"
            series_map[label] = pts
            series_styles[label] = dict(style)
        target_pts: list[tuple[int, float]] = []
        for field in ("target_stock_display_qty", "target_stock_qty", "safety_floor_qty"):
            pts = aggregate_daily_series(
                mrp_trace_rows,
                value_field=field,
                node_field="node_id",
                node_id=node_id,
                item_ids={item_id},
            )
            if any(abs(value) > 1e-9 for _, value in pts):
                target_pts = pts
                break
        if target_pts:
            target_pts = rolling_average_points(target_pts, MRP_TARGET_DISPLAY_SMOOTHING_DAYS)
            label = f"{item_name} - cible position MRP (moy. 30j)"
            series_map[label] = target_pts
            series_styles[label] = {"color": "#2563eb", "width": 1.65, "dash": "dash"}
    return series_map, series_styles


def mrp_metric_series_by_item(
    mrp_trace_rows: list[dict[str, str]],
    *,
    node_id: str,
    item_ids: set[str],
    item_labels: dict[str, str],
    value_field: str,
    label_suffix: str,
    clip_non_negative: bool = False,
    rolling_window_days: int = 0,
) -> dict[str, list[tuple[int, float]]]:
    if not mrp_trace_rows or not node_id or not item_ids:
        return {}
    out: dict[str, list[tuple[int, float]]] = {}
    scoped_items = {item_id for item_id in item_ids if not is_simulation_hidden_item(item_id)}
    rows_by_item: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in mrp_trace_rows:
        if str(row.get("node_id") or "") != node_id:
            continue
        item_id = str(row.get("item_id") or "")
        if item_id in scoped_items:
            rows_by_item[item_id].append(row)
    for item_id in sorted(scoped_items):
        pts: list[tuple[int, float]] = []
        for row in rows_by_item.get(item_id, []):
            day = int(to_float(row.get("day")) or 0)
            value = float(to_float(row.get(value_field)) or 0.0)
            if clip_non_negative:
                value = max(0.0, value)
            pts.append((day, value))
        if not any(abs(value) > 1e-9 for _, value in pts):
            continue
        if rolling_window_days > 1:
            pts = rolling_average_points(pts, rolling_window_days)
        item_name = item_labels.get(item_id, compact_item_label(item_id))
        out[f"{item_name} - {label_suffix}"] = sorted(pts, key=lambda it: it[0])
    return out


COMPARABLE_STOCK_COLORS = [
    "#0f766e",
    "#2563eb",
    "#dc2626",
    "#d97706",
    "#7c3aed",
    "#0891b2",
    "#be123c",
    "#65a30d",
    "#475569",
    "#ea580c",
    "#4f46e5",
    "#15803d",
]


def comparable_stock_series_for_items(
    item_ids: set[str],
    *,
    stock_series_by_item: dict[str, tuple[str, list[tuple[int, float]]]],
    target_series_by_item: dict[str, tuple[str, list[tuple[int, float]]]],
    item_labels: dict[str, str],
) -> tuple[dict[str, list[tuple[int, float]]], dict[str, dict[str, Any]]]:
    series: dict[str, list[tuple[int, float]]] = {}
    styles: dict[str, dict[str, Any]] = {}
    sorted_item_ids = sorted(
        [item_id for item_id in item_ids if not is_simulation_hidden_item(item_id)],
        key=lambda item_id: item_labels.get(item_id, compact_item_label(item_id)),
    )
    for idx, item_id in enumerate(sorted_item_ids):
        color = COMPARABLE_STOCK_COLORS[idx % len(COMPARABLE_STOCK_COLORS)]
        stock_entry = stock_series_by_item.get(item_id)
        if stock_entry and stock_entry[1]:
            label, points = stock_entry
            series[label] = points
            styles[label] = {"width": 1.9, "color": color}
        target_entry = target_series_by_item.get(item_id)
        if target_entry and target_entry[1]:
            label, points = target_entry
            series[label] = points
            styles[label] = {"width": 1.55, "color": color, "dash": "dash"}
    return series, styles


def comparable_item_color_map(item_ids: set[str], item_labels: dict[str, str]) -> dict[str, str]:
    sorted_item_ids = sorted(
        [item_id for item_id in item_ids if not is_simulation_hidden_item(item_id)],
        key=lambda item_id: item_labels.get(item_id, compact_item_label(item_id)),
    )
    return {
        item_id: COMPARABLE_STOCK_COLORS[idx % len(COMPARABLE_STOCK_COLORS)]
        for idx, item_id in enumerate(sorted_item_ids)
    }


def metric_series_styles_for_items(
    item_ids: set[str],
    *,
    item_labels: dict[str, str],
    label_suffix: str,
    dash: str,
    width: float,
) -> dict[str, dict[str, Any]]:
    colors = comparable_item_color_map(item_ids, item_labels)
    styles: dict[str, dict[str, Any]] = {}
    for item_id, color in colors.items():
        item_name = item_labels.get(item_id, compact_item_label(item_id))
        styles[f"{item_name} - {label_suffix}"] = {"color": color, "dash": dash, "width": width}
    return styles


def series_styles_for_item_entries(
    item_ids: set[str],
    series_by_item: dict[str, tuple[str, list[tuple[int, float]]]],
    *,
    item_labels: dict[str, str],
    dash: str,
    width: float,
) -> dict[str, dict[str, Any]]:
    colors = comparable_item_color_map(item_ids, item_labels)
    styles: dict[str, dict[str, Any]] = {}
    for item_id, (label, points) in series_by_item.items():
        if item_id not in colors or not points:
            continue
        styles[label] = {"color": colors[item_id], "dash": dash, "width": width}
    return styles


def mrp_physical_target_series_by_item(
    mrp_trace_rows: list[dict[str, str]],
    *,
    node_id: str,
    item_ids: set[str],
    item_labels: dict[str, str],
) -> dict[str, tuple[str, list[tuple[int, float]]]]:
    if not mrp_trace_rows or not node_id or not item_ids:
        return {}
    scoped_items = {item_id for item_id in item_ids if not is_simulation_hidden_item(item_id)}
    rows_by_item: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in mrp_trace_rows:
        if str(row.get("node_id") or "") != node_id:
            continue
        item_id = str(row.get("item_id") or "")
        if item_id in scoped_items:
            rows_by_item[item_id].append(row)
    out: dict[str, tuple[str, list[tuple[int, float]]]] = {}
    for item_id in sorted(scoped_items):
        pts: list[tuple[int, float]] = []
        for row in rows_by_item.get(item_id, []):
            day = int(to_float(row.get("day")) or 0)
            target = to_float(row.get("target_stock_display_qty"))
            if target is None or math.isnan(target) or abs(target) <= 1e-9:
                target = to_float(row.get("target_stock_qty"))
            if target is None or math.isnan(target) or abs(target) <= 1e-9:
                target = to_float(row.get("safety_floor_qty"))
            future_receipts = to_float(row.get("recv_prev_future_qty"))
            physical_target = max(0.0, (target or 0.0) - (future_receipts or 0.0))
            pts.append((day, physical_target))
        if not any(abs(value) > 1e-9 for _, value in pts):
            continue
        pts = rolling_average_points(pts, MRP_TARGET_DISPLAY_SMOOTHING_DAYS)
        item_name = item_labels.get(item_id, compact_item_label(item_id))
        out[item_id] = (f"{item_name} - consigne physique (moy. 30j)", sorted(pts, key=lambda it: it[0]))
    return out


def normalize_quantity_unit(unit: Any) -> str:
    value = str(unit or "").strip()
    if not value:
        return "unite non renseignee"
    normalized = value.upper().replace("UNIT/DAY", "UN").replace("UNIT", "UN")
    normalized = normalized.replace("/DAY", "")
    return normalized or "unite non renseignee"


def build_simulation_diagnostics_payload(
    raw: dict[str, Any],
    *,
    demand_service_csv: Path,
    dc_stocks_csv: Path,
    sim_input_stocks_csv: Path,
    sim_output_products_csv: Path,
    production_constraint_csv: Path,
    production_plan_events_csv: Path,
    supplier_shipments_csv: Path,
    supplier_stocks_csv: Path,
    supplier_stock_flows_csv: Path | None,
    supplier_local_criticality_csv: Path,
    mrp_trace_csv: Path | None,
    edge_metrics: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    item_labels = item_label_lookup(raw)
    node_by_id = {str(node.get("id") or ""): node for node in raw.get("nodes", []) or []}
    edge_metrics = edge_metrics or {}

    def item_label(item_id: str) -> str:
        return item_labels.get(item_id, compact_item_label(item_id))

    def compact_qty(value: float) -> str:
        value = float(value or 0.0)
        sign = "-" if value < 0 else ""
        value = abs(value)
        if value >= 1_000_000_000:
            return f"{sign}{value / 1_000_000_000:.2f}Md"
        if value >= 1_000_000:
            return f"{sign}{value / 1_000_000:.2f}M"
        if value >= 1_000:
            return f"{sign}{value / 1_000:.1f}k"
        return f"{sign}{value:.1f}"

    def pct(num: float, den: float) -> float:
        return 100.0 * num / den if den > 1e-9 else 0.0

    def make_diag(
        *,
        pill: str,
        title: str,
        text: str,
        cls: str,
        status: str,
        cause: str,
        proof: str,
        action: str,
        impact: str = "",
    ) -> dict[str, Any]:
        lines = [
            {"label": "Statut", "value": status},
            {"label": "Cause principale", "value": cause},
            {"label": "Preuve", "value": proof},
            {"label": "Action metier", "value": action},
        ]
        if impact:
            lines.insert(2, {"label": "Impact", "value": impact})
        return {
            "pill": pill,
            "title": title,
            "text": text,
            "cls": cls,
            "summary_lines": lines,
        }

    nodes: dict[str, Any] = {}
    edges: dict[str, Any] = {}

    demand_rows = read_csv_rows(demand_service_csv)
    demand_by_node: dict[str, dict[str, Any]] = defaultdict(
        lambda: {
            "demand": 0.0,
            "served": 0.0,
            "max_backlog": 0.0,
            "backlog_days": set(),
            "items": set(),
            "worst_item": "",
            "worst_item_backlog": 0.0,
        }
    )
    for row in demand_rows:
        node_id = str(row.get("node_id") or "")
        item_id = str(row.get("item_id") or "")
        if not node_id or is_simulation_hidden_item(item_id):
            continue
        day = int(to_float(row.get("day")) or 0)
        demand = max(0.0, to_float(row.get("demand_qty")) or 0.0)
        served = max(0.0, to_float(row.get("served_qty")) or 0.0)
        backlog = max(0.0, to_float(row.get("backlog_end_qty")) or 0.0)
        stats = demand_by_node[node_id]
        stats["demand"] += demand
        stats["served"] += served
        stats["items"].add(item_id)
        if backlog > 1e-9:
            stats["backlog_days"].add(day)
        if backlog > stats["max_backlog"]:
            stats["max_backlog"] = backlog
        if backlog > stats["worst_item_backlog"]:
            stats["worst_item_backlog"] = backlog
            stats["worst_item"] = item_id

    for node_id, stats in demand_by_node.items():
        service = pct(stats["served"], stats["demand"])
        backlog_days = len(stats["backlog_days"])
        worst_item = str(stats["worst_item"] or "")
        if service < 98.0 or backlog_days > 14:
            cls = "businessAlert"
            status = "Critique disponibilite"
            action = "Verifier stock aval et prioriser le reapprovisionnement du produit en retard."
        elif service < 99.5 or backlog_days > 2:
            cls = "businessWarn"
            status = "Disponibilite sous surveillance"
            action = "Surveiller les jours de backlog et verifier le stock DC sur les produits demandes."
        else:
            cls = "businessOk"
            status = "Disponibilite produit OK"
            action = "Aucune action immediate; garder la preuve stock/demande pour expliquer la disponibilite."
        proof = (
            f"demande={compact_qty(stats['demand'])}, servi={compact_qty(stats['served'])}, "
            f"disponibilite={service:.2f}%, backlog max={compact_qty(stats['max_backlog'])}"
        )
        if worst_item:
            proof += f" sur {item_label(worst_item)}"
        text = (
            "Question metier: le client est-il servi ? "
            f"Reponse: disponibilite {service:.2f}%, {backlog_days} jour(s) avec backlog. "
            "Preuve: courbes demande / servi / backlog."
        )
        nodes[node_id] = make_diag(
            pill="Diagnostic",
            title=f"{status} - {node_id}",
            text=text,
            cls=cls,
            status=status,
            cause="Demande aval couverte par les receptions et le stock disponible",
            impact=f"{backlog_days} jour(s) de backlog ; backlog max {compact_qty(stats['max_backlog'])}",
            proof=proof,
            action=action,
        )

    dc_rows = read_csv_rows(dc_stocks_csv)
    mrp_rows = read_csv_rows(mrp_trace_csv) if mrp_trace_csv is not None and mrp_trace_csv.exists() else []
    dc_stock: dict[str, dict[str, Any]] = defaultdict(
        lambda: {"items": set(), "first": {}, "last": {}, "min": {}, "min_day": {}, "max_target": defaultdict(float)}
    )
    for row in dc_rows:
        node_id = str(row.get("node_id") or "")
        item_id = str(row.get("item_id") or "")
        if not node_id or not item_id or is_simulation_hidden_item(item_id):
            continue
        day = int(to_float(row.get("day")) or 0)
        value = max(0.0, to_float(row.get("stock_end_of_day")) or 0.0)
        stats = dc_stock[node_id]
        stats["items"].add(item_id)
        stats["first"].setdefault(item_id, value)
        stats["last"][item_id] = value
        if item_id not in stats["min"] or value < stats["min"][item_id]:
            stats["min"][item_id] = value
            stats["min_day"][item_id] = day
    for row in mrp_rows:
        node_id = str(row.get("node_id") or "")
        if node_id not in dc_stock:
            continue
        item_id = str(row.get("item_id") or "")
        if item_id not in dc_stock[node_id]["items"]:
            continue
        target = 0.0
        for field in ("target_stock_display_qty", "target_stock_qty", "safety_floor_qty"):
            target = max(target, max(0.0, to_float(row.get(field)) or 0.0))
        if target > dc_stock[node_id]["max_target"][item_id]:
            dc_stock[node_id]["max_target"][item_id] = target

    shipments = read_csv_rows(supplier_shipments_csv)
    inbound_by_node: dict[str, float] = defaultdict(float)
    outbound_by_node: dict[str, float] = defaultdict(float)
    shipment_qty_by_triplet: dict[tuple[str, str, str], float] = defaultdict(float)
    for row in shipments:
        src = str(row.get("src_node_id") or "")
        dst = str(row.get("dst_node_id") or "")
        item_id = str(row.get("item_id") or "")
        if is_simulation_hidden_item(item_id):
            continue
        qty = max(0.0, to_float(row.get("shipped_qty")) or 0.0)
        if dst:
            inbound_by_node[dst] += qty
        if src:
            outbound_by_node[src] += qty
        if src and dst and item_id:
            shipment_qty_by_triplet[(src, dst, item_id)] += qty

    for node_id, stats in dc_stock.items():
        worst_item = ""
        worst_ratio = math.inf
        worst_min = 0.0
        worst_target = 0.0
        biggest_drop_item = ""
        biggest_drop_ratio = 0.0
        for item_id in sorted(stats["items"]):
            first = float(stats["first"].get(item_id, 0.0))
            minimum = float(stats["min"].get(item_id, 0.0))
            target = float(stats["max_target"].get(item_id, 0.0))
            if first > 1e-9:
                drop_ratio = max(0.0, (first - minimum) / first)
                if drop_ratio > biggest_drop_ratio:
                    biggest_drop_ratio = drop_ratio
                    biggest_drop_item = item_id
            if target > 1e-9:
                ratio = minimum / target
                if ratio < worst_ratio:
                    worst_ratio = ratio
                    worst_item = item_id
                    worst_min = minimum
                    worst_target = target
        if worst_item and worst_min <= 1e-9:
            cls = "businessAlert"
            status = "Stock DC en rupture"
            cause = f"{item_label(worst_item)} atteint un stock nul"
            action = "Verifier les receptions usine->DC et le niveau de couverture client."
        elif worst_item and worst_ratio < 0.8:
            cls = "businessWarn"
            status = "Stock DC sous cible MRP"
            cause = f"{item_label(worst_item)} descend nettement sous la cible MRP"
            action = "Verifier si la cible est un seuil de couverture prudent ou si les receptions DC doivent etre avancees."
        elif worst_item and worst_ratio < 1.0:
            cls = "businessWarn"
            status = "Stock DC proche cible"
            cause = f"{item_label(worst_item)} passe sous la cible MRP"
            action = "Surveiller la trajectoire stock/cible et les prochains lots en reception."
        elif biggest_drop_ratio >= 0.25:
            cls = "businessWarn"
            status = "Stock DC consomme"
            cause = f"{item_label(biggest_drop_item)} baisse fortement avant reapprovisionnement"
            action = "Relier la baisse a la demande client et aux receptions DC."
        else:
            cls = "businessOk"
            status = "Stock DC couvert"
            cause = "Le stock physique reste au-dessus des seuils visibles ou sans rupture detectee"
            action = "Pas d'action immediate; garder la courbe stock/cible comme preuve de couverture."
        if worst_item:
            proof = (
                f"{item_label(worst_item)} min={compact_qty(worst_min)} / cible={compact_qty(worst_target)} "
                f"({worst_ratio:.2f}x)"
            )
        elif biggest_drop_item:
            proof = f"{item_label(biggest_drop_item)} baisse max={biggest_drop_ratio * 100:.1f}%"
        else:
            proof = "stocks DC stables sur les items traces"
        text = (
            "Question metier: le DC protege-t-il la disponibilite produit ? "
            f"Reponse: {status.lower()}. Receptions={compact_qty(inbound_by_node[node_id])}, "
            f"expeditions={compact_qty(outbound_by_node[node_id])}. Preuve: courbe stock DC / cible MRP."
        )
        nodes[node_id] = make_diag(
            pill="Diagnostic",
            title=f"{status} - {node_id}",
            text=text,
            cls=cls,
            status=status,
            cause=cause,
            impact=f"receptions {compact_qty(inbound_by_node[node_id])}, expeditions {compact_qty(outbound_by_node[node_id])}",
            proof=proof,
            action=action,
        )

    constraint_rows = read_csv_rows(production_constraint_csv)
    factory_stats: dict[str, dict[str, Any]] = defaultdict(
        lambda: {
            "desired": 0.0,
            "planned": 0.0,
            "actual": 0.0,
            "short_desired": 0.0,
            "short_plan": 0.0,
            "input_shortage_days": set(),
            "capacity_days": set(),
            "weekly_lot_limit_days": set(),
            "active_days": set(),
            "items": set(),
            "binding_shortfall": defaultdict(float),
            "recovery_days": set(),
            "normal_days": set(),
        }
    )
    for row in constraint_rows:
        node_id = str(row.get("node_id") or "")
        item_id = str(row.get("output_item_id") or "")
        if not node_id or not item_id or is_simulation_hidden_item(item_id):
            continue
        day = int(to_float(row.get("day")) or 0)
        actual = max(0.0, to_float(row.get("actual_qty")) or 0.0)
        planned = max(0.0, to_float(row.get("planned_qty_after_lot_rule")) or 0.0)
        desired = max(0.0, to_float(row.get("desired_qty")) or 0.0)
        short_plan = max(0.0, to_float(row.get("shortfall_vs_lot_plan_qty")) or 0.0)
        stats = factory_stats[node_id]
        stats["items"].add(item_id)
        stats["desired"] += desired
        stats["planned"] += planned
        stats["actual"] += actual
        stats["short_desired"] += max(0.0, to_float(row.get("shortfall_vs_desired_qty")) or 0.0)
        stats["short_plan"] += short_plan
        if actual > 1e-9:
            stats["active_days"].add(day)
            remaining_start = max(0.0, to_float(row.get("campaign_remaining_start_qty")) or 0.0)
            requested_qty = max(0.0, to_float(row.get("campaign_requested_qty")) or 0.0)
            requested_lots = max(0.0, to_float(row.get("requested_lot_starts")) or 0.0)
            if remaining_start > 0 and requested_qty <= 1e-9 and requested_lots <= 1e-9:
                stats["recovery_days"].add(day)
            else:
                stats["normal_days"].add(day)
        cause = str(row.get("binding_cause") or "none")
        if cause == "input_shortage":
            stats["input_shortage_days"].add(day)
            binding_item = str(row.get("binding_input_item_id") or "")
            if binding_item:
                stats["binding_shortfall"][binding_item] += short_plan
        elif cause == "capacity":
            stats["capacity_days"].add(day)
        elif cause == "weekly_lot_limit":
            stats["weekly_lot_limit_days"].add(day)

    for node_id, stats in factory_stats.items():
        exec_rate = pct(stats["actual"], stats["planned"])
        top_blocker = ""
        top_shortfall = 0.0
        if stats["binding_shortfall"]:
            top_blocker, top_shortfall = max(stats["binding_shortfall"].items(), key=lambda item: item[1])
        if stats["input_shortage_days"]:
            cls = "businessWarn"
            status = "Production reportee par intrants"
            cause = f"manque {item_label(top_blocker)}" if top_blocker else "intrants insuffisants"
            action = "Ouvrir le suivi de lots et les ordres reportes, puis verifier le fournisseur du composant bloquant."
        elif stats["capacity_days"]:
            cls = "businessWarn"
            status = "Production contrainte capacite"
            cause = "capacite journaliere atteinte"
            action = "Comparer capacite nominale, lotification et demande lisse avant d'ajouter des intrants."
        elif stats["weekly_lot_limit_days"]:
            cls = "businessInfo"
            status = "Limite hebdomadaire lots"
            cause = "limite de lots par semaine atteinte"
            action = "Verifier que la limite hebdomadaire represente bien la cadence industrielle."
        else:
            cls = "businessOk"
            status = "Production executee"
            cause = "pas de contrainte matiere ou capacite observee"
            action = "Pas d'action immediate; utiliser le planning lots pour expliquer les lancements."
        proof = (
            f"plan lotifie={compact_qty(stats['planned'])}, produit={compact_qty(stats['actual'])}, "
            f"execution={exec_rate:.1f}%"
        )
        if top_blocker:
            proof += f", bloqueur={item_label(top_blocker)} ({compact_qty(top_shortfall)})"
        recovery_count = len(stats["recovery_days"])
        text = (
            "Question metier: pourquoi produit-on ou reporte-t-on ? "
            f"Reponse: {status.lower()}. Jours matiere={len(stats['input_shortage_days'])}, "
            f"jours capacite={len(stats['capacity_days'])}, rattrapages={recovery_count}. "
            "Preuve: execution production et planning lots."
        )
        nodes[node_id] = make_diag(
            pill="Diagnostic",
            title=f"{status} - {display_node_label(node_id)}",
            text=text,
            cls=cls,
            status=status,
            cause=cause,
            impact=(
                f"{len(stats['input_shortage_days'])} jour(s) matiere, "
                f"{len(stats['recovery_days'])} rattrapage(s), manque plan {compact_qty(stats['short_plan'])}"
            ),
            proof=proof,
            action=action,
        )

    supplier_rows = read_csv_rows(supplier_local_criticality_csv)
    supplier_criticality: dict[str, dict[str, str]] = {
        str(row.get("supplier_id") or ""): row
        for row in supplier_rows
        if str(row.get("supplier_id") or "")
    }
    supplier_stock_rows = read_csv_rows(supplier_stocks_csv)
    supplier_stock_min: dict[str, float] = defaultdict(lambda: math.inf)
    supplier_stock_items: dict[str, set[str]] = defaultdict(set)
    for row in supplier_stock_rows:
        node_id = str(row.get("node_id") or "")
        item_id = str(row.get("item_id") or "")
        if not node_id or is_simulation_hidden_item(item_id):
            continue
        supplier_stock_items[node_id].add(item_id)
        supplier_stock_min[node_id] = min(supplier_stock_min[node_id], max(0.0, to_float(row.get("stock_end_of_day")) or 0.0))
    supplier_flow_rows = read_csv_rows(supplier_stock_flows_csv) if supplier_stock_flows_csv is not None else []
    supplier_outgoing_pull: dict[str, float] = defaultdict(float)
    for row in supplier_flow_rows:
        node_id = str(row.get("node_id") or "")
        item_id = str(row.get("item_id") or "")
        if not node_id or is_simulation_hidden_item(item_id):
            continue
        supplier_outgoing_pull[node_id] += max(0.0, to_float(row.get("outgoing_pulled_qty")) or 0.0)

    for node_id, node in sorted(node_by_id.items()):
        if node_id in nodes:
            continue
        if str(node.get("type") or "") != "supplier_dc":
            continue
        row = supplier_criticality.get(node_id, {})
        shortage_events = int(to_float(row.get("shortage_supported_events")) or 0)
        local_score = max(0.0, to_float(row.get("local_criticality_score")) or 0.0)
        top_items = str(row.get("top_items_preview") or "")
        shipped_qty = max(outbound_by_node.get(node_id, 0.0), to_float(row.get("total_shipped_qty")) or 0.0)
        min_stock = supplier_stock_min.get(node_id, math.inf)
        if shortage_events > 0:
            cls = "businessWarn"
            status = "Fournisseur bloquant observe"
            cause = f"{shortage_events} evenement(s) de rupture supporte(s)"
            action = "Verifier commandes recues, envois physiques, delai fournisseur et stock de securite du composant."
        elif local_score >= 0.5:
            cls = "businessWarn"
            status = "Fournisseur critique reseau"
            cause = f"score local {local_score:.2f}"
            action = "Surveiller la couverture et valider une alternative si l'item est mono-source."
        elif shipped_qty > 0:
            cls = "businessOk"
            status = "Fournisseur actif sans rupture"
            cause = "expeditions observees sans support de rupture"
            action = "Pas d'action immediate; garder stock/seuil MRP comme preuve de couverture."
        else:
            cls = "businessInfo"
            status = "Fournisseur peu actif"
            cause = "pas d'expedition observee sur le run"
            action = "Verifier si ce fournisseur est volontairement hors baseline ou source alternative."
        stock_text = "n/a" if min_stock == math.inf else compact_qty(min_stock)
        proof = (
            f"items={top_items or ', '.join(item_label(i) for i in sorted(supplier_stock_items.get(node_id, set()))) or 'n/a'}, "
            f"expedie={compact_qty(shipped_qty)}, stock min={stock_text}, score={local_score:.2f}"
        )
        text = (
            "Question metier: ce fournisseur menace-t-il l'execution ? "
            f"Reponse: {status.lower()}. Expeditions={compact_qty(shipped_qty)}, "
            f"tirages stock={compact_qty(supplier_outgoing_pull[node_id])}. Preuve: commandes/envois et stock fournisseur."
        )
        nodes[node_id] = make_diag(
            pill="Diagnostic",
            title=f"{status} - {node_id}",
            text=text,
            cls=cls,
            status=status,
            cause=cause,
            impact=f"expeditions {compact_qty(shipped_qty)}, ruptures supportees {shortage_events}",
            proof=proof,
            action=action,
        )

    for edge in raw.get("edges", []) or []:
        edge_id = str(edge.get("id") or "")
        if not edge_id:
            continue
        src = str(edge.get("from") or "")
        dst = str(edge.get("to") or "")
        metrics = edge_metrics.get(edge_id) or {}
        shipped_qty = sum(
            shipment_qty_by_triplet.get((src, dst, str(item_id or "")), 0.0)
            for item_id in edge.get("items") or []
            if not is_simulation_hidden_item(str(item_id or ""))
        )
        rows = int(to_float(metrics.get("shipment_rows")) or 0)
        avg_lead = to_float(metrics.get("avg_lead_days"))
        planned_lead = to_float(metrics.get("planned_lead_days"))
        if rows > 0:
            cls = "businessOk"
            status = "Flux actif"
            cause = "expeditions et receptions observees"
            action = "Comparer quantite transportee, delai observe et hypothese logistique si dimensionnement camion requis."
        else:
            cls = "businessInfo"
            status = "Flux sans expedition observee"
            cause = "aucun mouvement physique dans le run nominal"
            action = "Verifier si le flux est alternatif, dormant ou hors horizon."
        proof = (
            f"{rows} expedition(s), quantite={compact_qty(shipped_qty)}, "
            f"delai moyen={avg_lead:.1f}j" if avg_lead is not None else f"{rows} expedition(s), quantite={compact_qty(shipped_qty)}"
        )
        text = (
            "Question metier: le flux a-t-il vraiment bouge ? "
            f"Reponse: {status.lower()} entre {src} et {dst}. "
            f"Delai planifie={planned_lead:.1f}j." if planned_lead is not None else
            f"Question metier: le flux a-t-il vraiment bouge ? Reponse: {status.lower()} entre {src} et {dst}."
        )
        edges[edge_id] = make_diag(
            pill="Diagnostic",
            title=f"{status} - {src} -> {dst}",
            text=text,
            cls=cls,
            status=status,
            cause=cause,
            impact=f"quantite transportee {compact_qty(shipped_qty)}",
            proof=proof,
            action=action,
        )

    return {
        "available": bool(nodes or edges),
        "nodes": nodes,
        "edges": edges,
        "summary": {
            "node_count": len(nodes),
            "edge_count": len(edges),
        },
    }


def build_supplier_hover_images(
    raw: dict[str, Any],
    png_dir: Path,
    supplier_shipments_csv: Path,
    supplier_stocks_csv: Path,
    supplier_stock_flows_csv: Path | None,
    supplier_capacity_csv: Path,
    mrp_trace_csv: Path | None = None,
) -> dict[str, Any]:
    nodes = raw.get("nodes", []) or []
    supplier_ids = sorted(
        str(n.get("id"))
        for n in nodes
        if str(n.get("type") or "") == "supplier_dc" and not is_pilotage_hidden_node(str(n.get("id") or ""))
    )
    out: dict[str, Any] = {}
    item_labels = item_label_lookup(raw)
    mrp_trace_rows = read_csv_rows(mrp_trace_csv) if mrp_trace_csv is not None and mrp_trace_csv.exists() else []
    inbound_lead_days_by_supplier: dict[str, dict[str, float]] = defaultdict(dict)
    for edge in raw.get("edges", []) or []:
        dst = str(edge.get("to") or "")
        src = str(edge.get("from") or "")
        if dst not in supplier_ids or not src:
            continue
        lead_days = max(1.0, to_float(((edge.get("lead_time") or {}).get("mean"))) or 1.0)
        prev = inbound_lead_days_by_supplier[dst].get(src)
        inbound_lead_days_by_supplier[dst][src] = min(prev, lead_days) if prev is not None else lead_days

    for supplier_id in supplier_ids:
        safe_supplier = re.sub(r"[^A-Za-z0-9_-]+", "_", supplier_id)
        incoming = None
        outgoing = None
        third = None
        shipped_series: list[tuple[int, float]] = []
        per_item_stock: dict[str, list[tuple[int, float]]] = {}
        supplier_stock_item_ids: set[str] = set()
        combined_flow: dict[str, list[tuple[int, float]]] = {}
        shipment_rows = read_csv_rows(supplier_shipments_csv)
        flow_rows = (
            read_csv_rows(supplier_stock_flows_csv)
            if supplier_stock_flows_csv is not None and supplier_stock_flows_csv.exists()
            else []
        )
        capacity_rows = read_csv_rows(supplier_capacity_csv)
        if shipment_rows:
            shipped_series = aggregate_daily_series(
                shipment_rows,
                value_field="shipped_qty",
                node_field="src_node_id",
                node_id=supplier_id,
            )
        stock_rows = read_csv_rows(supplier_stocks_csv)
        if stock_rows:
            item_ids = sorted({str(row.get("item_id") or "") for row in stock_rows if str(row.get("node_id") or "") == supplier_id})
            for item_id in item_ids:
                if is_simulation_hidden_item(item_id):
                    continue
                pts = aggregate_daily_series(
                    stock_rows,
                    value_field="stock_end_of_day",
                    node_field="node_id",
                    node_id=supplier_id,
                    item_ids={item_id},
                )
                if pts:
                    supplier_stock_item_ids.add(item_id)
                    per_item_stock[item_labels.get(item_id, compact_item_label(item_id))] = pts
        if flow_rows:
            item_ids = sorted(
                {
                    str(row.get("item_id") or "")
                    for row in flow_rows
                    if str(row.get("node_id") or "") == supplier_id
                }
            )
            for item_id in item_ids:
                if is_simulation_hidden_item(item_id):
                    continue
                item_label = item_labels.get(item_id, compact_item_label(item_id))
                incoming_pts = aggregate_daily_series(
                    flow_rows,
                    value_field="incoming_qty",
                    node_field="node_id",
                    node_id=supplier_id,
                    item_ids={item_id},
                )
                outgoing_pts = aggregate_daily_series(
                    flow_rows,
                    value_field="outgoing_pulled_qty",
                    node_field="node_id",
                    node_id=supplier_id,
                    item_ids={item_id},
                )
                if incoming_pts:
                    combined_flow[f"{item_label} - entree stock"] = incoming_pts
                if outgoing_pts:
                    combined_flow[f"{item_label} - sortie stock"] = outgoing_pts
        elif shipment_rows:
            item_ids = sorted(
                {
                    str(row.get("item_id") or "")
                    for row in shipment_rows
                    if str(row.get("src_node_id") or "") == supplier_id
                }
            )
            for item_id in item_ids:
                if is_simulation_hidden_item(item_id):
                    continue
                item_label = item_labels.get(item_id, compact_item_label(item_id))
                ship_pts = aggregate_daily_series(
                    shipment_rows,
                    value_field="shipped_qty",
                    node_field="src_node_id",
                    node_id=supplier_id,
                    item_ids={item_id},
                )
                receipt_pts = aggregate_daily_series(
                    shipment_rows,
                    value_field="shipped_qty",
                    day_field="arrival_day",
                    node_field="src_node_id",
                    node_id=supplier_id,
                    item_ids={item_id},
                )
                if ship_pts:
                    combined_flow[f"{item_label} - expedition"] = ship_pts
                if receipt_pts:
                    combined_flow[f"{item_label} - reception"] = receipt_pts
        stock_title = f"{supplier_id} - stock fournisseur par item"
        if len(per_item_stock) == 1:
            stock_title = f"{stock_title} - {next(iter(per_item_stock.keys()))}"
        shipment_title = f"{supplier_id} - entrees et sorties de stock fournisseur"
        shipment_item_ids = sorted(
            {
                str(row.get("item_id") or "")
                for row in shipment_rows
                if str(row.get("src_node_id") or "") == supplier_id
            }
        )
        if len(shipment_item_ids) == 1 and shipment_item_ids:
            single_label = item_labels.get(shipment_item_ids[0], compact_item_label(shipment_item_ids[0]))
            shipment_title = f"{shipment_title} - {single_label}"
        supplier_target_series, supplier_target_styles = stock_target_overlay_series(
            mrp_trace_rows,
            node_id=supplier_id,
            item_ids=supplier_stock_item_ids,
            item_labels=item_labels,
        )
        supplier_stock_with_targets = {**per_item_stock, **supplier_target_series}
        figure = build_dual_line_multi_panel_figure(
            title=f"{supplier_id} - stock et flux fournisseur",
            top_title=stock_title,
            top_y_label="Quantite",
            top_series_map=supplier_stock_with_targets,
            bottom_title=shipment_title,
            bottom_y_label="Quantite",
            bottom_series_map=combined_flow,
            top_series_styles=supplier_target_styles,
            top_step_like=True,
            bottom_event_like=True,
            top_lot_trace_category="supplier_stock",
            bottom_lot_trace_category="supplier_send",
        )
        has_dynamic_supplier_panel = figure is not None
        if figure is not None:
            incoming = {"figure": figure}
        if incoming is None:
            incoming = resolve_plot_payload(
                png_dir,
                Path("suppliers") / "input_stocks" / f"production_supplier_input_stocks_by_material_{safe_supplier}.png",
                f"production_supplier_input_stocks_by_material_{safe_supplier}.png",
            )
        if incoming is None:
            incoming = load_png_payload(png_dir / f"production_supplier_shipments_by_material_{safe_supplier}.png")
        if incoming is None:
            incoming = load_png_payload(png_dir / f"production_supplier_stocks_by_material_{safe_supplier}.png")
        if outgoing is None and not has_dynamic_supplier_panel:
            outgoing = load_png_payload(png_dir / f"production_supplier_shipments_by_material_{safe_supplier}.png")
        if incoming or outgoing or third:
            out[supplier_id] = {"incoming": incoming, "outgoing": outgoing, "third": third}
    return out


def build_distribution_center_hover_images(
    raw: dict[str, Any],
    png_dir: Path,
    dc_stocks_csv: Path,
    shipments_csv: Path,
    mrp_trace_csv: Path | None = None,
) -> dict[str, Any]:
    nodes = raw.get("nodes", []) or []
    dc_ids = sorted(
        str(n.get("id"))
        for n in nodes
        if str(n.get("type") or "") == "distribution_center" and not is_pilotage_hidden_node(str(n.get("id") or ""))
    )
    out: dict[str, Any] = {}
    item_labels = item_label_lookup(raw)
    dc_stock_rows = read_csv_rows(dc_stocks_csv)
    shipment_rows = read_csv_rows(shipments_csv)
    mrp_trace_rows = read_csv_rows(mrp_trace_csv) if mrp_trace_csv is not None and mrp_trace_csv.exists() else []
    for dc_id in dc_ids:
        safe_dc = re.sub(r"[^A-Za-z0-9_-]+", "_", dc_id)
        incoming = resolve_plot_payload(
            png_dir,
            Path("distribution_centers") / "factory_outputs" / f"production_dc_factory_outputs_by_material_{safe_dc}.png",
            f"production_dc_factory_outputs_by_material_{safe_dc}.png",
        )
        outgoing = None
        third = None
        if dc_stock_rows:
            per_item_stock: dict[str, list[tuple[int, float]]] = {}
            per_item_styles: dict[str, dict[str, Any]] = {}
            dc_stock_item_ids: set[str] = set()
            item_ids = sorted(
                {str(row.get("item_id") or "") for row in dc_stock_rows if str(row.get("node_id") or "") == dc_id}
            )
            for item_id in item_ids:
                if is_simulation_hidden_item(item_id):
                    continue
                pts = aggregate_daily_series(
                    dc_stock_rows,
                    value_field="stock_end_of_day",
                    node_field="node_id",
                    node_id=dc_id,
                    item_ids={item_id},
                )
                if pts:
                    dc_stock_item_ids.add(item_id)
                    label = item_labels.get(item_id, compact_item_label(item_id))
                    stock_label = f"{label} - stock"
                    per_item_stock[stock_label] = pts
                    per_item_styles[stock_label] = {"color": "#0f766e", "width": 2.3}
            dc_target_series, dc_target_styles = stock_target_overlay_series(
                mrp_trace_rows,
                node_id=dc_id,
                item_ids=dc_stock_item_ids,
                item_labels=item_labels,
            )
            per_item_stock_with_targets = {**per_item_stock, **dc_target_series}
            per_item_styles.update(dc_target_styles)
            figure = build_line_chart_figure(
                per_item_stock_with_targets,
                title=f"{dc_id} - stock DC par item avec cible",
                y_label="Quantite",
                note=(
                    "Lecture metier: stock physique disponible et cible MRP affichee. "
                    "Position inventaire, besoin net et stock projete restent dans Details MRP."
                ),
                series_styles=per_item_styles,
                lot_trace_category="dc_stock",
            )
            if figure is not None:
                incoming = {"figure": figure}
        if shipment_rows:
            inbound_by_item: dict[str, list[tuple[int, float]]] = {}
            inbound_item_ids = sorted(
                {str(row.get("item_id") or "") for row in shipment_rows if str(row.get("dst_node_id") or "") == dc_id}
            )
            for item_id in inbound_item_ids:
                if is_simulation_hidden_item(item_id):
                    continue
                pts = aggregate_daily_series(
                    shipment_rows,
                    value_field="shipped_qty",
                    day_field="arrival_day",
                    node_field="dst_node_id",
                    node_id=dc_id,
                    item_ids={item_id},
                )
                if pts:
                    inbound_by_item[item_labels.get(item_id, compact_item_label(item_id))] = pts
            if inbound_by_item:
                figure = build_line_chart_figure(
                    inbound_by_item,
                    title=f"{dc_id} - receptions journalieres par item",
                    y_label="Quantite",
                    step_like=True,
                    lot_trace_category="receipt",
                )
                if figure is not None:
                    outgoing = {"figure": figure}

            outbound_by_item: dict[str, list[tuple[int, float]]] = {}
            outbound_item_ids = sorted(
                {str(row.get("item_id") or "") for row in shipment_rows if str(row.get("src_node_id") or "") == dc_id}
            )
            for item_id in outbound_item_ids:
                if is_simulation_hidden_item(item_id):
                    continue
                pts = aggregate_daily_series(
                    shipment_rows,
                    value_field="shipped_qty",
                    node_field="src_node_id",
                    node_id=dc_id,
                    item_ids={item_id},
                )
                if pts:
                    outbound_by_item[item_labels.get(item_id, compact_item_label(item_id))] = pts
            if outbound_by_item:
                figure = build_line_chart_figure(
                    outbound_by_item,
                    title=f"{dc_id} - expeditions journalieres par item",
                    y_label="Quantite",
                    step_like=True,
                    lot_trace_category="shipment",
                )
                if figure is not None:
                    third = {"figure": figure}
        if incoming or outgoing or third:
            out[dc_id] = {"incoming": incoming, "outgoing": outgoing, "third": third}
    return out


def build_site_stock_payload(
    raw: dict[str, Any],
    supplier_stocks_csv: Path,
    node_id: str,
    *,
    title: str,
) -> dict[str, Any] | None:
    rows = read_csv_rows(supplier_stocks_csv)
    if not rows:
        return None
    item_labels = item_label_lookup(raw)
    per_item_stock: dict[str, list[tuple[int, float]]] = {}
    item_ids = sorted({str(row.get("item_id") or "") for row in rows if str(row.get("node_id") or "") == node_id})
    for item_id in item_ids:
        if is_simulation_hidden_item(item_id):
            continue
        pts = aggregate_daily_series(
            rows,
            value_field="stock_end_of_day",
            node_field="node_id",
            node_id=node_id,
            item_ids={item_id},
        )
        if pts:
            per_item_stock[item_labels.get(item_id, compact_item_label(item_id))] = pts
    if not per_item_stock:
        return None
    figure = build_line_chart_figure(
        per_item_stock,
        title=title,
        y_label="Quantite",
    )
    if figure is None:
        return None
    return {"figure": figure}


def build_customer_hover_images(
    raw: dict[str, Any],
    demand_service_csv: Path,
    shipments_csv: Path,
) -> tuple[dict[str, Any], dict[str, Any]]:
    rows = read_csv_rows(demand_service_csv)
    if not rows:
        return {}, {}
    shipment_rows = read_csv_rows(shipments_csv)

    customer_ids = sorted(
        str(n.get("id"))
        for n in (raw.get("nodes", []) or [])
        if str(n.get("type") or "") == "customer"
    )
    customer_hover: dict[str, Any] = {}
    customer_metrics: dict[str, Any] = {}
    for customer_id in customer_ids:
        customer_rows = [row for row in rows if str(row.get("node_id") or "") == customer_id]
        if not customer_rows:
            continue
        demand_series = aggregate_daily_series(customer_rows, value_field="demand_qty")
        demand_series_by_item: dict[str, dict[int, float]] = {}
        for item_id in sorted({str(row.get("item_id") or "") for row in customer_rows if str(row.get("item_id") or "")}):
            if is_simulation_hidden_item(item_id):
                continue
            scoped_rows = [row for row in customer_rows if str(row.get("item_id") or "") == item_id]
            scoped_series = aggregate_daily_series(scoped_rows, value_field="demand_qty")
            if scoped_series:
                demand_series_by_item[compact_item_label(item_id)] = scoped_series
        served_series = aggregate_daily_series(customer_rows, value_field="served_qty")
        backlog_series = aggregate_daily_series(customer_rows, value_field="backlog_end_qty")
        incoming_series = {"Demande totale": demand_series}
        incoming_series.update(demand_series_by_item)
        incoming = build_line_chart_payload(
            incoming_series,
            title=f"{customer_id} - demande dans le temps",
            y_label="Quantite",
            filename=f"{safe_case_token(customer_id)}_customer_demand.png",
        )
        figure = build_line_chart_figure(
            incoming_series,
            title=f"{customer_id} - demande dans le temps",
            y_label="Quantite",
            lot_trace_category="customer_service",
        )
        if figure is not None:
            incoming = {"figure": figure}
        if incoming is None:
            figure = build_line_chart_figure(
                incoming_series,
                title=f"{customer_id} - demande dans le temps",
                y_label="Quantite",
                lot_trace_category="customer_service",
            )
            if figure is not None:
                incoming = {"figure": figure}
        outgoing = build_line_chart_payload(
            {
                "Servi": served_series,
                "Backlog": backlog_series,
            },
            title=f"{customer_id} - servi et backlog dans le temps",
            y_label="Quantite",
            filename=f"{safe_case_token(customer_id)}_customer_service_backlog.png",
        )
        figure = build_line_chart_figure(
            {
                "Servi": served_series,
                "Backlog": backlog_series,
            },
            title=f"{customer_id} - servi et backlog dans le temps",
            y_label="Quantite",
            lot_trace_category="customer_service",
        )
        if figure is not None:
            outgoing = {"figure": figure}
        if outgoing is None:
            figure = build_line_chart_figure(
                {
                    "Servi": served_series,
                    "Backlog": backlog_series,
                },
                title=f"{customer_id} - servi et backlog dans le temps",
                y_label="Quantite",
                lot_trace_category="customer_service",
            )
            if figure is not None:
                outgoing = {"figure": figure}

        latest_day = max((int(to_float(row.get("day")) or 0) for row in customer_rows), default=0)
        latest_rows = [row for row in customer_rows if int(to_float(row.get("day")) or 0) == latest_day]
        latest_demand_by_item: dict[str, float] = defaultdict(float)
        latest_backlog_total = 0.0
        latest_served_total = 0.0
        latest_demand_total = 0.0
        for row in latest_rows:
            item_id = str(row.get("item_id") or "")
            demand_value = float(to_float(row.get("demand_qty")) or 0.0)
            latest_demand_by_item[item_id] += demand_value
            latest_demand_total += demand_value
            latest_served_total += float(to_float(row.get("served_qty")) or 0.0)
            latest_backlog_total += float(to_float(row.get("backlog_end_qty")) or 0.0)
        inbound_by_item: dict[str, list[tuple[int, float]]] = {}
        if shipment_rows:
            inbound_item_ids = sorted(
                {str(row.get("item_id") or "") for row in shipment_rows if str(row.get("dst_node_id") or "") == customer_id}
            )
            for item_id in inbound_item_ids:
                if is_simulation_hidden_item(item_id):
                    continue
                scoped_rows = [
                    row
                    for row in shipment_rows
                    if str(row.get("dst_node_id") or "") == customer_id and str(row.get("item_id") or "") == item_id
                ]
                pts = aggregate_daily_series(
                    scoped_rows,
                    value_field="shipped_qty",
                    day_field="arrival_day",
                )
                if pts:
                    inbound_by_item[compact_item_label(item_id)] = pts
        third = None
        if inbound_by_item:
            third = build_line_chart_payload(
                inbound_by_item,
                title=f"{customer_id} - receptions client par item",
                y_label="Quantite",
                filename=f"{safe_case_token(customer_id)}_customer_receipts.png",
            )
            figure = build_line_chart_figure(
                inbound_by_item,
                title=f"{customer_id} - receptions client par item",
                y_label="Quantite",
                step_like=True,
                lot_trace_category="receipt",
            )
            if figure is not None:
                third = {"figure": figure}
            if third is None:
                figure = build_line_chart_figure(
                    inbound_by_item,
                    title=f"{customer_id} - receptions client par item",
                    y_label="Quantite",
                    step_like=True,
                    lot_trace_category="receipt",
                )
                if figure is not None:
                    third = {"figure": figure}
        if third is None:
            third = build_bar_chart_payload(
                {compact_item_label(item_id): value for item_id, value in latest_demand_by_item.items()},
                title=f"{customer_id} - demande du dernier jour par produit",
                y_label="Demande jour courant",
                filename=f"{safe_case_token(customer_id)}_customer_latest_demand.png",
            )
        if third is None:
            figure = build_bar_chart_figure(
                {compact_item_label(item_id): value for item_id, value in latest_demand_by_item.items()},
                title=f"{customer_id} - demande du dernier jour par produit",
                y_label="Demande jour courant",
            )
            if figure is not None:
                third = {"figure": figure}
        if incoming or outgoing or third:
            customer_hover[customer_id] = {"incoming": incoming, "outgoing": outgoing, "third": third}
        customer_metrics[customer_id] = {
            "summary_lines": [
                metric_label_value("Jour courant", str(latest_day)),
                metric_label_value("Demande jour courant", f"{latest_demand_total:,.1f}".replace(",", " ")),
                metric_label_value("Servi jour courant", f"{latest_served_total:,.1f}".replace(",", " ")),
                metric_label_value("Backlog courant", f"{latest_backlog_total:,.1f}".replace(",", " ")),
                metric_label_value(
                    "Produits demandes",
                    ", ".join(
                        f"{compact_item_label(item_id)}={value:.1f}"
                        for item_id, value in sorted(latest_demand_by_item.items())
                    )
                    or "n/a",
                ),
            ]
        }
    return customer_hover, customer_metrics




def extend_global_kpi_tree_with_supplier_risk(
    kpi_tree: dict[str, Any] | None,
    *,
    supplier_risk_panel_csv: Path,
    supplier_risk_supplier_csv: Path,
    supplier_risk_pair_csv: Path,
    supplier_risk_summary_json: Path,
) -> dict[str, Any] | None:
    if not kpi_tree:
        return kpi_tree
    panel_rows = read_csv_rows(supplier_risk_panel_csv)
    if not panel_rows:
        return kpi_tree
    supplier_rows = read_csv_rows(supplier_risk_supplier_csv)
    pair_rows = read_csv_rows(supplier_risk_pair_csv)
    summary_json = load_json_dict(supplier_risk_summary_json)
    days = [int(to_float(day) or 0) for day in (((kpi_tree.get("main") or {}).get("days")) or [])]
    if not days:
        weeks = sorted({int(to_float(row.get("week_index")) or 0) for row in panel_rows})
        days = [week * 7 for week in weeks]
        kpi_tree.setdefault("main", {})["days"] = days
    if not days:
        return kpi_tree

    weekly: dict[int, dict[str, Any]] = defaultdict(
        lambda: {
            "risk_max": 0.0,
            "risk_high_max": 0.0,
            "action_max": 0.0,
            "resilience_min": 1.0,
            "early_warning_max": 0.0,
            "change_point_max": 0.0,
            "watch_count": 0.0,
            "orange_red_count": 0.0,
        }
    )
    for row in panel_rows:
        week = int(to_float(row.get("week_index")) or 0)
        bucket = weekly[week]
        bucket["risk_max"] = max(bucket["risk_max"], risk_ratio(row.get("risk_probability_proxy_4w")))
        bucket["risk_high_max"] = max(bucket["risk_high_max"], risk_ratio(row.get("risk_probability_high_proxy_4w")))
        bucket["action_max"] = max(bucket["action_max"], risk_ratio(row.get("action_priority_score")))
        resilience_value = to_float(row.get("resilience_score"))
        if resilience_value is not None and not math.isnan(resilience_value):
            bucket["resilience_min"] = min(bucket["resilience_min"], max(0.0, min(1.0, resilience_value)))
        bucket["early_warning_max"] = max(bucket["early_warning_max"], risk_ratio(row.get("early_warning_score")))
        bucket["change_point_max"] = max(bucket["change_point_max"], risk_ratio(row.get("change_point_score")))
        zone_rank = supplier_risk_zone_rank(row.get("decision_zone"))
        if zone_rank >= 1:
            bucket["watch_count"] += 1.0
        if zone_rank >= 2:
            bucket["orange_red_count"] += 1.0

    def day_values(field: str, *, scale: float = 1.0) -> list[float]:
        values: list[float] = []
        for day in days:
            week = max(0, int(day // 7))
            values.append(round(float(weekly.get(week, {}).get(field, 0.0)) * scale, 6))
        return values

    top_supplier = None
    if supplier_rows:
        top_supplier = max(supplier_rows, key=lambda row: risk_ratio(row.get("max_action_priority_score")))
    latest_zone_counts = summary_json.get("decision_zone_counts_latest")
    latest_action_counts = summary_json.get("action_counts_latest")
    max_high_supplier = max(
        (risk_ratio(row.get("max_risk_probability_high_proxy_4w")) for row in supplier_rows),
        default=0.0,
    )
    max_action_supplier = max(
        (risk_ratio(row.get("max_action_priority_score")) for row in supplier_rows),
        default=0.0,
    )

    def summary(label: str, value: Any) -> dict[str, str]:
        return {"label": label, "value": str(value)}

    kpi_tree.setdefault("main", {}).setdefault("series", []).append(
        {
            "id": "supplier_risk",
            "label": "Criticite fournisseurs",
            "values": day_values("action_max", scale=100.0),
            "color": "#be123c",
            "note": "Priorite d'action maximale: menace estimee x criticite x marge de recuperation.",
        }
    )
    kpi_tree.setdefault("groups", []).append(
        {
            "id": "supplier_risk",
            "label": "Criticite fournisseurs",
            "objective": "Identifier les fournisseurs critiques a surveiller, le niveau de confiance et l'action a engager.",
            "summary": [
                summary("Fournisseurs couverts", summary_json.get("supplier_count", len(supplier_rows))),
                summary("Couples fournisseur-article-site", summary_json.get("pair_count", len(pair_rows))),
                summary("Zones dernieres", supplier_risk_zone_counts_text(latest_zone_counts if isinstance(latest_zone_counts, dict) else None)),
                summary("Actions dernieres", supplier_risk_zone_counts_text(latest_action_counts if isinstance(latest_action_counts, dict) else None)),
                summary("Borne prudente menace max", fmt_pct(100.0 * max_high_supplier)),
                summary("Priorite d'action max", fmt_pct(100.0 * max_action_supplier)),
                summary(
                    "Top fournisseur",
                    (
                        f"{top_supplier.get('supplier_id')} ({risk_pct(top_supplier.get('max_action_priority_score'))})"
                        if top_supplier
                        else "n/a"
                    ),
                ),
            ],
            "secondary": [
                {"label": "Menace estimee max (%)", "days": days, "values": day_values("risk_max", scale=100.0), "color": "#be123c"},
                {"label": "Borne prudente max (%)", "days": days, "values": day_values("risk_high_max", scale=100.0), "color": "#dc2626", "dash": "dash"},
                {"label": "Priorite d'action max (%)", "days": days, "values": day_values("action_max", scale=100.0), "color": "#7c3aed"},
                {"label": "Marge de recuperation min (%)", "days": days, "values": day_values("resilience_min", scale=100.0), "color": "#0f766e"},
                {"label": "Alerte faible max (%)", "days": days, "values": day_values("early_warning_max", scale=100.0), "color": "#d97706"},
                {"label": "Rupture de tendance max (%)", "days": days, "values": day_values("change_point_max", scale=100.0), "color": "#0891b2"},
                {"label": "Couples sous surveillance", "days": days, "values": day_values("watch_count"), "color": "#475569"},
                {"label": "Couples orange/rouge", "days": days, "values": day_values("orange_red_count"), "color": "#dc2626"},
            ],
            "secondary_y_label": "% / nombre",
        }
    )
    kpi_tree.setdefault("definitions", []).extend(
        [
            {
                "family": "Criticite fournisseurs",
                "level": "KPI principal",
                "name": "Priorite d'action fournisseur",
                "formula": "menace estimee x exposition x penalite de recuperation",
                "terms": "La menace estimee combine performance, signaux faibles et borne prudente. L'exposition vient des volumes attendus.",
                "interpretation": "Score de pilotage: plus il est haut, plus une action fournisseur est justifiee avant incident visible.",
            },
            {
                "family": "Criticite fournisseurs",
                "level": "KPI secondaire",
                "name": "Menace estimee fournisseur",
                "formula": "estimation a 4 semaines issue performance, dynamique, sensibilite, criticite et incertitude",
                "terms": "Combine lead time, variabilite, capacite, stock, warning/change-point et sensibilite locale.",
                "interpretation": "Signal de menace future, distinct de la performance observee du moment.",
            },
            {
                "family": "Criticite fournisseurs",
                "level": "KPI secondaire",
                "name": "Marge de recuperation fournisseur",
                "formula": "capacite a absorber une chute, ajustee par stock, couverture, capacite et stabilite",
                "terms": "Mesure si le fournisseur peut absorber, continuer, puis revenir a la normale.",
                "interpretation": "Capacite a absorber, continuer, recuperer et stabiliser.",
            },
            {
                "family": "Criticite fournisseurs",
                "level": "KPI secondaire",
                "name": "Niveau d'action fournisseur",
                "formula": "regles par quantiles, incertitude, criticite et resilience",
                "terms": "faible=routine; modere=surveillance; eleve=action preventive; critique=action immediate.",
                "interpretation": "Transforme les KPI en action fournisseur explicable.",
            },
        ]
    )
    subtitle = str(kpi_tree.get("subtitle") or "")
    if "Criticite fournisseurs" not in subtitle:
        kpi_tree["subtitle"] = (
            subtitle.rstrip(".")
            + ". L'onglet Criticite fournisseurs transforme les KPI en niveau de criticite, confiance de lecture et action recommandee."
        )
    return kpi_tree
































































def build_edge_item_sets(raw: dict[str, Any]) -> tuple[dict[str, set[str]], dict[str, set[str]]]:
    incoming_items: dict[str, set[str]] = defaultdict(set)
    outgoing_items: dict[str, set[str]] = defaultdict(set)
    for edge in raw.get("edges", []) or []:
        src = str(edge.get("from") or "")
        dst = str(edge.get("to") or "")
        for item_id in edge.get("items") or []:
            item = str(item_id)
            if src:
                outgoing_items[src].add(item)
            if dst:
                incoming_items[dst].add(item)
    return incoming_items, outgoing_items


def build_node_type_lookup(raw: dict[str, Any]) -> dict[str, str]:
    out: dict[str, str] = {}
    for node in raw.get("nodes", []) or []:
        node_id = str(node.get("id") or "")
        if not node_id:
            continue
        out[node_id] = str(node.get("type") or "")
    return out


def build_node_relationships(raw: dict[str, Any]) -> tuple[dict[str, set[str]], dict[str, set[str]]]:
    incoming_sources: dict[str, set[str]] = defaultdict(set)
    outgoing_targets: dict[str, set[str]] = defaultdict(set)
    for edge in raw.get("edges", []) or []:
        src = str(edge.get("from") or "")
        dst = str(edge.get("to") or "")
        if not src or not dst:
            continue
        incoming_sources[dst].add(src)
        outgoing_targets[src].add(dst)
    return incoming_sources, outgoing_targets


def sensitivity_row_scope(
    parameter_key: str,
    node_id: str,
    node_item_ids: dict[str, set[str]],
    node_types: dict[str, str],
    incoming_sources: dict[str, set[str]],
    outgoing_targets: dict[str, set[str]],
) -> str | None:
    if parameter_key.endswith(f"::{node_id}"):
        return "direct"
    if parameter_key.startswith("demand_item::"):
        item_id = parameter_key.split("::", 1)[1]
        if item_id in node_item_ids.get(node_id, set()):
            return "item"
        return None

    if "::" not in parameter_key:
        return None
    _, target = parameter_key.split("::", 1)
    node_type = node_types.get(node_id, "")

    if node_type == "factory" and target in incoming_sources.get(node_id, set()):
        if parameter_key.startswith("edge_src_lead_time_scale::") or parameter_key.startswith("supplier_lead_time_node::"):
            return "upstream_lead_time"
        if parameter_key.startswith("edge_src_reliability_scale::") or parameter_key.startswith(
            "supplier_reliability_node::"
        ):
            return "upstream_reliability"
        if parameter_key.startswith("supplier_capacity_node::"):
            return "upstream_supplier_capacity"
        if parameter_key.startswith("supplier_node_scale::") or parameter_key.startswith("supplier_stock_node::"):
            return "upstream_supplier_stock"
        if parameter_key.startswith("combined_capacity_delay::"):
            return "upstream_combined_capacity_delay"
        if parameter_key.startswith("combined_stock_reliability::"):
            return "upstream_combined_stock_reliability"

    if node_type == "distribution_center" and target in incoming_sources.get(node_id, set()):
        if parameter_key.startswith("capacity_node::"):
            return "upstream_factory_capacity"
        if parameter_key.startswith("edge_src_lead_time_scale::"):
            return "upstream_factory_lead_time"
        if parameter_key.startswith("edge_src_reliability_scale::"):
            return "upstream_factory_reliability"

    if node_type == "supplier_dc" and target in outgoing_targets.get(node_id, set()):
        if parameter_key.startswith("demand_item::"):
            return "downstream_demand"

    return None


def aggregate_daily_series(
    rows: list[dict[str, str]],
    *,
    value_field: str,
    day_field: str = "day",
    node_field: str | None = None,
    node_id: str | None = None,
    item_ids: set[str] | None = None,
) -> list[tuple[int, float]]:
    by_day: dict[int, float] = defaultdict(float)
    for row in rows:
        if node_field and node_id is not None and str(row.get(node_field) or "") != node_id:
            continue
        item_id = str(row.get("item_id") or "")
        if item_ids is not None and item_id not in item_ids:
            continue
        day = int(to_float(row.get(day_field)) or 0)
        value = float(to_float(row.get(value_field)) or 0.0)
        by_day[day] += value
    return sorted(by_day.items(), key=lambda it: it[0])


def compact_item_label(item_id: str) -> str:
    raw = str(item_id or "").strip()
    if raw.startswith("item:"):
        return raw.split(":", 1)[1]
    return raw or "n/a"


def build_factory_industrial_payload(
    desired_series: list[tuple[int, float]],
    actual_series: list[tuple[int, float]],
    recovery_actual_series: list[tuple[int, float]],
    capacity_series: list[tuple[int, float]],
    shortfall_series: list[tuple[int, float]],
    lot_plan_shortfall_series: list[tuple[int, float]],
    *,
    factory_id: str,
) -> dict[str, Any] | None:
    def normalize_points(points: list[tuple[int, float]], *, drop_zero: bool = False) -> list[dict[str, float]]:
        out: list[dict[str, float]] = []
        for day, value in sorted(points):
            qty = float(value)
            if drop_zero and abs(qty) < 1e-9:
                continue
            out.append({"day": int(day), "value": qty})
        return out

    if not any([desired_series, actual_series, recovery_actual_series, capacity_series, shortfall_series, lot_plan_shortfall_series]):
        return None
    return {
        "figure": {
            "kind": "production_execution",
            "title": f"{factory_id} - execution production par lots",
            "lot_trace_category": "production",
            "x_label": "Jour",
            "top_title": "Lots physiques produits ou reportes",
            "bottom_title": "Besoin quotidien avant lotification",
            "top_y_label": "Quantite lot",
            "bottom_y_label": "Quantite / jour",
            "note": (
                "Lecture: le haut est a l'echelle des lots physiques. "
                "Orange = lot produit apres un report precedent. "
                "Le bas montre le besoin quotidien avant lotification, donc il est naturellement beaucoup plus bas."
            ),
            "top_bars": [
                {
                    "label": "Lots produits au lancement",
                    "points": normalize_points(actual_series, drop_zero=True),
                    "color": "#0f766e",
                    "opacity": 0.82,
                },
                {
                    "label": "Lots produits en rattrapage",
                    "points": normalize_points(recovery_actual_series, drop_zero=True),
                    "color": "#f59e0b",
                    "opacity": 0.88,
                },
                {
                    "label": "Lots reportes / bloques",
                    "points": normalize_points(lot_plan_shortfall_series, drop_zero=True),
                    "color": "#dc2626",
                    "opacity": 0.42,
                },
            ],
            "top_lines": [
                {
                    "label": "Capacite jour",
                    "points": normalize_points(capacity_series),
                    "color": "#2563eb",
                    "width": 1.9,
                    "dash": "dash",
                },
            ],
            "bottom_lines": [
                {
                    "label": "Besoin avant lotification",
                    "points": normalize_points(desired_series),
                    "color": "#475569",
                    "width": 1.8,
                    "dash": "dot",
                },
                {
                    "label": "Besoin non execute ce jour",
                    "points": normalize_points(shortfall_series, drop_zero=True),
                    "color": "#dc2626",
                    "width": 1.9,
                    "dash": "solid",
                },
            ],
        }
    }


def build_factory_current_metrics(
    raw: dict[str, Any],
    production_constraint_csv: Path,
) -> dict[str, Any]:
    rows = read_csv_rows(production_constraint_csv)
    if not rows:
        return {}

    inbound_lead_days_by_factory: dict[str, list[float]] = defaultdict(list)
    for edge in raw.get("edges", []) or []:
        dst = str(edge.get("to") or "")
        if not dst:
            continue
        inbound_lead_days_by_factory[dst].append(max(1.0, to_float(((edge.get("lead_time") or {}).get("mean"))) or 1.0))

    out: dict[str, Any] = {}
    for factory_id in sorted(factory_like_node_ids(raw)):
        factory_rows = [row for row in rows if str(row.get("node_id") or "") == factory_id]
        if not factory_rows:
            continue
        by_day: dict[int, dict[str, float]] = defaultdict(
            lambda: {
                "desired_qty": 0.0,
                "actual_qty": 0.0,
                "shortfall_qty": 0.0,
                "capacity_binding": 0.0,
            }
        )
        for row in factory_rows:
            day = int(to_float(row.get("day")) or 0)
            by_day[day]["desired_qty"] += max(0.0, to_float(row.get("desired_qty")) or 0.0)
            by_day[day]["actual_qty"] += max(0.0, to_float(row.get("actual_qty")) or 0.0)
            by_day[day]["shortfall_qty"] += max(0.0, to_float(row.get("shortfall_vs_desired_qty")) or 0.0)
            if str(row.get("binding_cause") or "") == "capacity":
                by_day[day]["capacity_binding"] = 1.0
        total_desired = sum(max(0.0, to_float(row.get("desired_qty")) or 0.0) for row in factory_rows)
        total_actual = sum(max(0.0, to_float(row.get("actual_qty")) or 0.0) for row in factory_rows)
        total_shortfall = sum(max(0.0, to_float(row.get("shortfall_vs_desired_qty")) or 0.0) for row in factory_rows)
        peak_shortfall = max((max(0.0, to_float(row.get("shortfall_vs_desired_qty")) or 0.0) for row in factory_rows), default=0.0)
        capacity_days = sum(1 for row in factory_rows if str(row.get("binding_cause") or "") == "capacity")
        avg_inbound_lead = (
            sum(inbound_lead_days_by_factory.get(factory_id, [])) / len(inbound_lead_days_by_factory.get(factory_id, []))
            if inbound_lead_days_by_factory.get(factory_id)
            else 0.0
        )
        out[factory_id] = {
            "avg_inbound_lead_days": round(avg_inbound_lead, 4),
            "daily_metrics": [
                {
                    "day": day,
                    "desired_qty": round(values["desired_qty"], 6),
                    "actual_qty": round(values["actual_qty"], 6),
                    "shortfall_qty": round(values["shortfall_qty"], 6),
                    "capacity_binding": int(values["capacity_binding"] > 0),
                }
                for day, values in sorted(by_day.items())
            ],
            "summary_lines": [
                metric_label_value("Production demandee cumulee", f"{total_desired:,.1f}".replace(",", " ")),
                metric_label_value("Production reelle cumulee", f"{total_actual:,.1f}".replace(",", " ")),
                metric_label_value("Manque de production cumule", f"{total_shortfall:,.1f}".replace(",", " ")),
                metric_label_value("Pic de manque de production", f"{peak_shortfall:,.1f}".replace(",", " ")),
                metric_label_value("Jours contraints capacite", str(capacity_days)),
                metric_label_value("Lead time entrant moyen", f"{avg_inbound_lead:.1f} j"),
            ]
        }
    return out


def build_supplier_site_detail_payload(
    supplier_id: str,
    shipped_series: list[tuple[int, float]],
    inbound_lead_days: dict[str, float],
) -> dict[str, Any] | None:
    if not shipped_series and not inbound_lead_days:
        return None
    return {
        "figure": build_dual_panel_figure(
            title=f"{supplier_id} - expeditions et lead times entrants",
            top_title=f"{supplier_id} - expeditions journalieres",
            top_x_label="Jour",
            top_y_label="Expedie",
            top_kind="line",
            top_x=[day for day, _ in shipped_series],
            top_y=[float(value) for _, value in shipped_series],
            bottom_title=f"{supplier_id} - lead time moyen entrants",
            bottom_x_label="Fournisseur amont",
            bottom_y_label="Jours",
            bottom_kind="bar",
            bottom_x=list(inbound_lead_days.keys()),
            bottom_y=[float(inbound_lead_days[label]) for label in inbound_lead_days],
        )
    }


def select_best_supplier_case_pair(
    by_case_id: dict[str, dict[str, str]],
    baseline_row: dict[str, str] | None,
    node_id: str,
) -> tuple[str, str, dict[str, str] | None, dict[str, str] | None, float, float]:
    safe_node = safe_case_token(node_id)
    candidates: list[tuple[str, str, dict[str, str] | None, dict[str, str] | None]] = [
        (
            "stock fournisseur local",
            "Stock four.",
            first_case_row(by_case_id, f"supplier_stock_node_{safe_node}_low", f"local_supplier_stock_node_{safe_node}_low"),
            first_case_row(by_case_id, f"supplier_stock_node_{safe_node}_high", f"local_supplier_stock_node_{safe_node}_high"),
        ),
        (
            "lead time sortant local",
            "Lead time",
            first_case_row(by_case_id, f"supplier_lead_time_node_{safe_node}_low", f"local_supplier_lead_time_node_{safe_node}_low"),
            first_case_row(by_case_id, f"supplier_lead_time_node_{safe_node}_high", f"local_supplier_lead_time_node_{safe_node}_high"),
        ),
        (
            "fiabilite locale",
            "OTIF",
            first_case_row(
                by_case_id,
                f"supplier_reliability_node_{safe_node}_low",
                f"local_supplier_reliability_node_{safe_node}_low",
                f"local_supplier_reliability_node_{safe_node}_adverse",
            ),
            first_case_row(by_case_id, f"supplier_reliability_node_{safe_node}_high", f"local_supplier_reliability_node_{safe_node}_high"),
        ),
        (
            "capacite fournisseur locale",
            "Cap. four.",
            first_case_row(by_case_id, f"supplier_capacity_node_{safe_node}_low", f"local_supplier_capacity_node_{safe_node}_low"),
            first_case_row(by_case_id, f"supplier_capacity_node_{safe_node}_high", f"local_supplier_capacity_node_{safe_node}_high"),
        ),
        (
            "capacite process locale",
            "Cap. proc.",
            first_case_row(by_case_id, f"capacity_{safe_node}_low", f"local_capacity_node_{safe_node}_low"),
            first_case_row(by_case_id, f"capacity_{safe_node}_high", f"local_capacity_node_{safe_node}_high"),
        ),
    ]
    best_label = ""
    best_short = ""
    best_low: dict[str, str] | None = None
    best_high: dict[str, str] | None = None
    best_score = -1.0
    best_fill_impact = 0.0
    best_backlog_impact = 0.0
    for label, short_label, low_row, high_row in candidates:
        if low_row is None and high_row is None:
            continue
        fill_impact, backlog_impact = local_signal_strength(baseline_row, low_row, high_row)
        score = fill_impact * 100.0 + backlog_impact / 25.0
        if score > best_score:
            best_label = label
            best_short = short_label
            best_low = low_row
            best_high = high_row
            best_score = score
            best_fill_impact = fill_impact
            best_backlog_impact = backlog_impact
    return best_label, best_short, best_low, best_high, best_fill_impact, best_backlog_impact


def build_factory_sensitivity_hover_images(
    raw: dict[str, Any],
    case_rows: list[dict[str, str]],
    csv_cache: dict[Path, list[dict[str, str]]],
) -> dict[str, Any]:
    by_case_id = case_rows_by_id(case_rows)
    baseline_row = baseline_sensitivity_row(by_case_id)
    baseline_dir = case_output_dir(baseline_row)
    if baseline_row is None or baseline_dir is None:
        return {}

    out: dict[str, Any] = {}
    for node in raw.get("nodes", []) or []:
        node_id = str(node.get("id") or "")
        if str(node.get("type") or "") != "factory":
            continue

        safe_node = safe_case_token(node_id)
        low_row = first_case_row(by_case_id, f"capacity_{safe_node}_low", f"local_capacity_node_{safe_node}_low")
        high_row = first_case_row(by_case_id, f"capacity_{safe_node}_high", f"local_capacity_node_{safe_node}_high")
        if low_row is None and high_row is None:
            continue
        low_label = multiplier_label(case_multiplier_value(low_row), "Low")
        high_label = multiplier_label(case_multiplier_value(high_row), "High")
        low_dir = case_output_dir(low_row)
        high_dir = case_output_dir(high_row)

        base_input_csv = baseline_dir / "production_input_stocks_daily.csv"
        base_output_csv = baseline_dir / "production_output_products_daily.csv"
        if base_input_csv not in csv_cache:
            csv_cache[base_input_csv] = read_csv_rows(base_input_csv)
        if base_output_csv not in csv_cache:
            csv_cache[base_output_csv] = read_csv_rows(base_output_csv)
        base_input_series = aggregate_daily_series(
            csv_cache[base_input_csv],
            value_field="stock_end_of_day",
            node_field="node_id",
            node_id=node_id,
        )
        base_output_series = aggregate_daily_series(
            csv_cache[base_output_csv],
            value_field="cum_produced_qty",
            node_field="node_id",
            node_id=node_id,
        )
        input_deltas: dict[str, list[tuple[int, float]]] = {}
        output_deltas: dict[str, list[tuple[int, float]]] = {}
        for label, root in ((low_label, low_dir), (high_label, high_dir)):
            if root is None:
                continue
            input_csv = root / "production_input_stocks_daily.csv"
            output_csv = root / "production_output_products_daily.csv"
            if input_csv not in csv_cache:
                csv_cache[input_csv] = read_csv_rows(input_csv)
            if output_csv not in csv_cache:
                csv_cache[output_csv] = read_csv_rows(output_csv)
            input_deltas[label] = align_series(
                base_input_series,
                aggregate_daily_series(
                    csv_cache[input_csv],
                    value_field="stock_end_of_day",
                    node_field="node_id",
                    node_id=node_id,
                ),
            )
            output_deltas[label] = align_series(
                base_output_series,
                aggregate_daily_series(
                    csv_cache[output_csv],
                    value_field="cum_produced_qty",
                    node_field="node_id",
                    node_id=node_id,
                ),
            )

        incoming = build_combo_bar_line_payload(
            {
                low_label: kpi_from_case(low_row, "fill_rate"),
                "Base": kpi_from_case(baseline_row, "fill_rate"),
                high_label: kpi_from_case(high_row, "fill_rate"),
            },
            input_deltas,
            bar_title=f"{node_id} - impact capacite sur disponibilite produit systeme",
            bar_y_label="Disponibilite produit",
            line_title=f"{node_id} - ecart de stock intrants vs baseline",
            line_y_label="Delta stock total",
            filename=f"{node_id}_sensitivity_fill_rate.png",
        )
        outgoing = build_combo_bar_line_payload(
            {
                low_label: kpi_from_case(low_row, "ending_backlog"),
                "Base": kpi_from_case(baseline_row, "ending_backlog"),
                high_label: kpi_from_case(high_row, "ending_backlog"),
            },
            output_deltas,
            bar_title=f"{node_id} - impact capacite sur backlog final",
            bar_y_label="Backlog final",
            line_title=f"{node_id} - ecart de production cumulee vs baseline",
            line_y_label="Delta production cumulee",
            filename=f"{node_id}_sensitivity_backlog.png",
        )
        if incoming or outgoing:
            out[node_id] = {"incoming": incoming, "outgoing": outgoing}
    return out


def build_supplier_sensitivity_hover_images(
    raw: dict[str, Any],
    case_rows: list[dict[str, str]],
    csv_cache: dict[Path, list[dict[str, str]]],
) -> dict[str, Any]:
    by_case_id = case_rows_by_id(case_rows)
    baseline_row = baseline_sensitivity_row(by_case_id)
    baseline_dir = case_output_dir(baseline_row)
    if baseline_row is None or baseline_dir is None:
        return {}

    out: dict[str, Any] = {}
    for node in raw.get("nodes", []) or []:
        node_id = str(node.get("id") or "")
        if str(node.get("type") or "") != "supplier_dc":
            continue

        best_label, best_short, best_low, best_high, best_fill_impact, best_backlog_impact = (
            select_best_supplier_case_pair(by_case_id, baseline_row, node_id)
        )
        if best_low is None and best_high is None:
            continue
        low_label = multiplier_label(case_multiplier_value(best_low), "Low")
        high_label = multiplier_label(case_multiplier_value(best_high), "High")
        low_dir = case_output_dir(best_low)
        high_dir = case_output_dir(best_high)
        base_ship_csv = baseline_dir / "production_supplier_shipments_daily.csv"
        base_stock_csv = baseline_dir / "production_supplier_stocks_daily.csv"
        if base_ship_csv not in csv_cache:
            csv_cache[base_ship_csv] = read_csv_rows(base_ship_csv)
        if base_stock_csv not in csv_cache:
            csv_cache[base_stock_csv] = read_csv_rows(base_stock_csv)
        base_ship_series = aggregate_daily_series(
            csv_cache[base_ship_csv],
            value_field="shipped_qty",
            node_field="src_node_id",
            node_id=node_id,
        )
        base_stock_series = aggregate_daily_series(
            csv_cache[base_stock_csv],
            value_field="stock_end_of_day",
            node_field="node_id",
            node_id=node_id,
        )
        ship_deltas: dict[str, list[tuple[int, float]]] = {}
        stock_deltas: dict[str, list[tuple[int, float]]] = {}
        for label, root in ((low_label, low_dir), (high_label, high_dir)):
            if root is None:
                continue
            ship_csv = root / "production_supplier_shipments_daily.csv"
            stock_csv = root / "production_supplier_stocks_daily.csv"
            if ship_csv not in csv_cache:
                csv_cache[ship_csv] = read_csv_rows(ship_csv)
            if stock_csv not in csv_cache:
                csv_cache[stock_csv] = read_csv_rows(stock_csv)
            ship_deltas[label] = align_series(
                base_ship_series,
                aggregate_daily_series(
                    csv_cache[ship_csv],
                    value_field="shipped_qty",
                    node_field="src_node_id",
                    node_id=node_id,
                ),
            )
            stock_deltas[label] = align_series(
                base_stock_series,
                aggregate_daily_series(
                    csv_cache[stock_csv],
                    value_field="stock_end_of_day",
                    node_field="node_id",
                    node_id=node_id,
                ),
            )
        note = None
        if best_fill_impact < 0.002 and best_backlog_impact < 5.0:
            note = "Impact faible: le noeud bouge peu sur le systeme malgre une variation locale forte."

        incoming = build_combo_bar_line_payload(
            {
                low_label: kpi_from_case(best_low, "fill_rate"),
                "Base": kpi_from_case(baseline_row, "fill_rate"),
                high_label: kpi_from_case(best_high, "fill_rate"),
            },
            ship_deltas,
            bar_title=f"{node_id} - impact {best_label} sur disponibilite produit systeme",
            bar_y_label="Disponibilite produit",
            line_title=f"{node_id} - ecart d'expeditions vs baseline",
            line_y_label="Delta expeditions / jour",
            filename=f"{node_id}_sensitivity_fill_rate.png",
            note=note,
        )
        outgoing = build_combo_bar_line_payload(
            {
                low_label: kpi_from_case(best_low, "ending_backlog"),
                "Base": kpi_from_case(baseline_row, "ending_backlog"),
                high_label: kpi_from_case(best_high, "ending_backlog"),
            },
            stock_deltas,
            bar_title=f"{node_id} - impact {best_label} sur backlog final",
            bar_y_label="Backlog final",
            line_title=f"{node_id} - ecart de stock disponible vs baseline",
            line_y_label="Delta stock fin de journee",
            filename=f"{node_id}_sensitivity_backlog.png",
            note=note,
        )
        out[node_id] = {"incoming": incoming, "outgoing": outgoing}
    return out


def build_distribution_center_sensitivity_hover_images(
    raw: dict[str, Any],
    case_rows: list[dict[str, str]],
    csv_cache: dict[Path, list[dict[str, str]]],
) -> dict[str, Any]:
    nodes = raw.get("nodes", []) or []
    incoming_items, outgoing_items = build_edge_item_sets(raw)
    by_case_id = case_rows_by_id(case_rows)
    baseline_row = baseline_sensitivity_row(by_case_id)
    baseline_dir = case_output_dir(baseline_row)
    if baseline_row is None or baseline_dir is None:
        return {}

    out: dict[str, Any] = {}
    for node in nodes:
        node_id = str(node.get("id") or "")
        if str(node.get("type") or "") != "distribution_center":
            continue

        dc_item_ids = set(incoming_items.get(node_id, set())) | set(outgoing_items.get(node_id, set()))
        base_demand_csv = baseline_dir / "production_demand_service_daily.csv"
        if base_demand_csv not in csv_cache:
            csv_cache[base_demand_csv] = read_csv_rows(base_demand_csv)
        fill_values: dict[str, float | None] = {"Base": kpi_from_case(baseline_row, "fill_rate")}
        backlog_values: dict[str, float | None] = {"Base": kpi_from_case(baseline_row, "ending_backlog")}
        backlog_deltas: dict[str, list[tuple[int, float]]] = {}
        served_deltas: dict[str, list[tuple[int, float]]] = {}
        for item_id in sorted(dc_item_ids):
            code = item_id.split(":", 1)[-1]
            base_backlog_series = aggregate_daily_series(
                csv_cache[base_demand_csv],
                value_field="backlog_end_qty",
                item_ids={item_id},
            )
            base_served_series = cumulative_series(
                aggregate_daily_series(
                    csv_cache[base_demand_csv],
                    value_field="served_qty",
                    item_ids={item_id},
                )
            )
            low_row = first_case_row(by_case_id, f"demand_item_{code}_low", f"local_demand_item_item_{code}_low")
            high_row = first_case_row(by_case_id, f"demand_item_{code}_high", f"local_demand_item_item_{code}_high")
            low_label = multiplier_label(case_multiplier_value(low_row), f"{code} low")
            high_label = multiplier_label(case_multiplier_value(high_row), f"{code} high")
            fill_values[f"{code} {low_label}"] = kpi_from_case(low_row, "fill_rate")
            fill_values[f"{code} {high_label}"] = kpi_from_case(high_row, "fill_rate")
            backlog_values[f"{code} {low_label}"] = kpi_from_case(low_row, "ending_backlog")
            backlog_values[f"{code} {high_label}"] = kpi_from_case(high_row, "ending_backlog")
            for label, row in ((f"{code} {low_label}", low_row), (f"{code} {high_label}", high_row)):
                root = case_output_dir(row)
                if root is None:
                    continue
                demand_csv = root / "production_demand_service_daily.csv"
                if demand_csv not in csv_cache:
                    csv_cache[demand_csv] = read_csv_rows(demand_csv)
                backlog_deltas[label] = align_series(
                    base_backlog_series,
                    aggregate_daily_series(
                        csv_cache[demand_csv],
                        value_field="backlog_end_qty",
                        item_ids={item_id},
                    ),
                )
                served_deltas[label] = align_series(
                    base_served_series,
                    cumulative_series(
                        aggregate_daily_series(
                            csv_cache[demand_csv],
                            value_field="served_qty",
                            item_ids={item_id},
                        )
                    ),
                )

        incoming = build_combo_bar_line_payload(
            fill_values,
            backlog_deltas,
            bar_title=f"{node_id} - impact demande sur disponibilite produit systeme",
            bar_y_label="Disponibilite produit",
            line_title=f"{node_id} - ecart de backlog client vs baseline",
            line_y_label="Delta backlog",
            filename=f"{node_id}_sensitivity_fill_rate.png",
        )
        outgoing = build_combo_bar_line_payload(
            backlog_values,
            served_deltas,
            bar_title=f"{node_id} - impact demande sur backlog final",
            bar_y_label="Backlog final",
            line_title=f"{node_id} - ecart de servi cumule vs baseline",
            line_y_label="Delta servi cumule",
            filename=f"{node_id}_sensitivity_backlog.png",
        )
        if incoming or outgoing:
            out[node_id] = {"incoming": incoming, "outgoing": outgoing}
    return out


def build_sensitivity_hover_payloads(
    raw: dict[str, Any],
    sensitivity_cases_csv: Path,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    case_rows = read_csv_rows(sensitivity_cases_csv)
    if not case_rows:
        return {}, {}, {}

    csv_cache: dict[Path, list[dict[str, str]]] = {}
    return (
        build_factory_sensitivity_hover_images(raw, case_rows, csv_cache),
        build_supplier_sensitivity_hover_images(raw, case_rows, csv_cache),
        build_distribution_center_sensitivity_hover_images(raw, case_rows, csv_cache),
    )


def build_factory_structural_hover_images(
    raw: dict[str, Any],
    case_rows: list[dict[str, str]],
    csv_cache: dict[Path, list[dict[str, str]]],
) -> dict[str, Any]:
    by_case_id = case_rows_by_id(case_rows)
    baseline_row = by_case_id.get("baseline")
    baseline_dir = case_output_dir(by_case_id.get("baseline"))
    if baseline_row is None or baseline_dir is None:
        return {}

    out: dict[str, Any] = {}
    for node in raw.get("nodes", []) or []:
        node_id = str(node.get("id") or "")
        if str(node.get("type") or "") != "factory":
            continue
        safe_node = safe_case_token(node_id)
        low_dir = case_output_dir(by_case_id.get(f"capacity_{safe_node}_low"))
        high_dir = case_output_dir(by_case_id.get(f"capacity_{safe_node}_high"))
        low_row = by_case_id.get(f"capacity_{safe_node}_low")
        high_row = by_case_id.get(f"capacity_{safe_node}_high")
        if low_dir is None and high_dir is None:
            continue

        low_label = multiplier_label(to_float(low_row.get("value")) if low_row else None, "Low")
        high_label = multiplier_label(to_float(high_row.get("value")) if high_row else None, "High")
        base_input_csv = baseline_dir / "production_input_stocks_daily.csv"
        base_output_csv = baseline_dir / "production_output_products_daily.csv"
        if base_input_csv not in csv_cache:
            csv_cache[base_input_csv] = read_csv_rows(base_input_csv)
        if base_output_csv not in csv_cache:
            csv_cache[base_output_csv] = read_csv_rows(base_output_csv)
        base_input_series = aggregate_daily_series(
            csv_cache[base_input_csv],
            value_field="stock_end_of_day",
            node_field="node_id",
            node_id=node_id,
        )
        base_output_series = aggregate_daily_series(
            csv_cache[base_output_csv],
            value_field="cum_produced_qty",
            node_field="node_id",
            node_id=node_id,
        )
        input_deltas: dict[str, list[tuple[int, float]]] = {}
        output_deltas: dict[str, list[tuple[int, float]]] = {}
        for label, root in ((low_label, low_dir), (high_label, high_dir)):
            if root is None:
                continue
            input_csv = root / "production_input_stocks_daily.csv"
            output_csv = root / "production_output_products_daily.csv"
            if input_csv not in csv_cache:
                csv_cache[input_csv] = read_csv_rows(input_csv)
            if output_csv not in csv_cache:
                csv_cache[output_csv] = read_csv_rows(output_csv)
            input_deltas[label] = align_series(
                base_input_series,
                aggregate_daily_series(
                    csv_cache[input_csv],
                    value_field="stock_end_of_day",
                    node_field="node_id",
                    node_id=node_id,
                ),
            )
            output_deltas[label] = align_series(
                base_output_series,
                aggregate_daily_series(
                    csv_cache[output_csv],
                    value_field="cum_produced_qty",
                    node_field="node_id",
                    node_id=node_id,
                ),
            )

        incoming = build_combo_bar_line_payload(
            {
                low_label: kpi_from_case(low_row, "fill_rate"),
                "Base": kpi_from_case(baseline_row, "fill_rate"),
                high_label: kpi_from_case(high_row, "fill_rate"),
            },
            input_deltas,
            bar_title=f"{node_id} - structurel: impact capacite sur disponibilite produit",
            bar_y_label="Disponibilite produit",
            line_title=f"{node_id} - structurel: ecart de stock intrants vs baseline",
            line_y_label="Delta stock total",
            filename=f"{node_id}_structural_input.png",
        )
        outgoing = build_combo_bar_line_payload(
            {
                low_label: kpi_from_case(low_row, "ending_backlog"),
                "Base": kpi_from_case(baseline_row, "ending_backlog"),
                high_label: kpi_from_case(high_row, "ending_backlog"),
            },
            output_deltas,
            bar_title=f"{node_id} - structurel: impact capacite sur backlog",
            bar_y_label="Backlog final",
            line_title=f"{node_id} - structurel: ecart de production cumulee vs baseline",
            line_y_label="Delta production cumulee",
            filename=f"{node_id}_structural_output.png",
        )
        if incoming or outgoing:
            out[node_id] = {"incoming": incoming, "outgoing": outgoing}
    return out


def build_supplier_structural_hover_images(
    raw: dict[str, Any],
    case_rows: list[dict[str, str]],
    csv_cache: dict[Path, list[dict[str, str]]],
) -> dict[str, Any]:
    by_case_id = case_rows_by_id(case_rows)
    baseline_row = by_case_id.get("baseline")
    baseline_dir = case_output_dir(baseline_row)
    if baseline_dir is None:
        return {}

    out: dict[str, Any] = {}
    for node in raw.get("nodes", []) or []:
        node_id = str(node.get("id") or "")
        if str(node.get("type") or "") != "supplier_dc":
            continue

        best_label, best_short, best_low_row, best_high_row, best_fill_impact, best_backlog_impact = (
            select_best_supplier_case_pair(by_case_id, baseline_row, node_id)
        )
        if best_low_row is None and best_high_row is None:
            continue

        low_dir = case_output_dir(best_low_row)
        high_dir = case_output_dir(best_high_row)
        low_label = multiplier_label(to_float(best_low_row.get("value")) if best_low_row else None, "Low")
        high_label = multiplier_label(to_float(best_high_row.get("value")) if best_high_row else None, "High")
        base_ship_csv = baseline_dir / "production_supplier_shipments_daily.csv"
        base_stock_csv = baseline_dir / "production_supplier_stocks_daily.csv"
        if base_ship_csv not in csv_cache:
            csv_cache[base_ship_csv] = read_csv_rows(base_ship_csv)
        if base_stock_csv not in csv_cache:
            csv_cache[base_stock_csv] = read_csv_rows(base_stock_csv)
        base_ship_series = aggregate_daily_series(
            csv_cache[base_ship_csv],
            value_field="shipped_qty",
            node_field="src_node_id",
            node_id=node_id,
        )
        base_stock_series = aggregate_daily_series(
            csv_cache[base_stock_csv],
            value_field="stock_end_of_day",
            node_field="node_id",
            node_id=node_id,
        )
        ship_deltas: dict[str, list[tuple[int, float]]] = {}
        stock_deltas: dict[str, list[tuple[int, float]]] = {}
        for label, root in ((low_label, low_dir), (high_label, high_dir)):
            if root is None:
                continue
            shipments_csv = root / "production_supplier_shipments_daily.csv"
            stocks_csv = root / "production_supplier_stocks_daily.csv"
            if shipments_csv not in csv_cache:
                csv_cache[shipments_csv] = read_csv_rows(shipments_csv)
            if stocks_csv not in csv_cache:
                csv_cache[stocks_csv] = read_csv_rows(stocks_csv)
            ship_deltas[label] = align_series(
                base_ship_series,
                aggregate_daily_series(
                    csv_cache[shipments_csv],
                    value_field="shipped_qty",
                    node_field="src_node_id",
                    node_id=node_id,
                ),
            )
            stock_deltas[label] = align_series(
                base_stock_series,
                aggregate_daily_series(
                    csv_cache[stocks_csv],
                    value_field="stock_end_of_day",
                    node_field="node_id",
                    node_id=node_id,
                ),
            )

        note = None
        if best_fill_impact < 0.002 and best_backlog_impact < 5.0:
            note = "Impact faible mais courbes affichees pour comparaison structurelle."

        incoming = build_combo_bar_line_payload(
            {
                low_label: kpi_from_case(best_low_row, "fill_rate"),
                "Base": kpi_from_case(baseline_row, "fill_rate"),
                high_label: kpi_from_case(best_high_row, "fill_rate"),
            },
            ship_deltas,
            bar_title=f"{node_id} - structurel: impact {best_label} sur disponibilite produit",
            bar_y_label="Disponibilite produit",
            line_title=f"{node_id} - structurel: ecart d'expeditions vs baseline",
            line_y_label="Delta expeditions / jour",
            filename=f"{node_id}_structural_shipments.png",
            note=note,
        )
        outgoing = build_combo_bar_line_payload(
            {
                low_label: kpi_from_case(best_low_row, "ending_backlog"),
                "Base": kpi_from_case(baseline_row, "ending_backlog"),
                high_label: kpi_from_case(best_high_row, "ending_backlog"),
            },
            stock_deltas,
            bar_title=f"{node_id} - structurel: impact {best_label} sur backlog",
            bar_y_label="Backlog final",
            line_title=f"{node_id} - structurel: ecart de stock disponible vs baseline",
            line_y_label="Delta stock fin de journee",
            filename=f"{node_id}_structural_stock.png",
            note=note,
        )
        if incoming or outgoing:
            out[node_id] = {"incoming": incoming, "outgoing": outgoing}
    return out


def build_distribution_center_structural_hover_images(
    raw: dict[str, Any],
    case_rows: list[dict[str, str]],
    csv_cache: dict[Path, list[dict[str, str]]],
) -> dict[str, Any]:
    nodes = raw.get("nodes", []) or []
    incoming_items, outgoing_items = build_edge_item_sets(raw)
    by_case_id = case_rows_by_id(case_rows)
    baseline_row = by_case_id.get("baseline")
    baseline_dir = case_output_dir(by_case_id.get("baseline"))
    if baseline_row is None or baseline_dir is None:
        return {}

    out: dict[str, Any] = {}
    for node in nodes:
        node_id = str(node.get("id") or "")
        if str(node.get("type") or "") != "distribution_center":
            continue

        dc_item_ids = set(incoming_items.get(node_id, set())) | set(outgoing_items.get(node_id, set()))
        base_demand_csv = baseline_dir / "production_demand_service_daily.csv"
        if base_demand_csv not in csv_cache:
            csv_cache[base_demand_csv] = read_csv_rows(base_demand_csv)
        fill_values: dict[str, float | None] = {"Base": kpi_from_case(baseline_row, "fill_rate")}
        backlog_values: dict[str, float | None] = {"Base": kpi_from_case(baseline_row, "ending_backlog")}
        backlog_deltas: dict[str, list[tuple[int, float]]] = {}
        served_deltas: dict[str, list[tuple[int, float]]] = {}
        for item_id in sorted(dc_item_ids):
            code = item_id.split(":", 1)[-1]
            base_backlog_series = aggregate_daily_series(
                csv_cache[base_demand_csv],
                value_field="backlog_end_qty",
                item_ids={item_id},
            )
            base_served_series = cumulative_series(
                aggregate_daily_series(
                    csv_cache[base_demand_csv],
                    value_field="served_qty",
                    item_ids={item_id},
                )
            )
            low_row = by_case_id.get(f"demand_item_{code}_low")
            high_row = by_case_id.get(f"demand_item_{code}_high")
            low_label = multiplier_label(to_float(low_row.get("value")) if low_row else None, f"{code} low")
            high_label = multiplier_label(to_float(high_row.get("value")) if high_row else None, f"{code} high")
            fill_values[f"{code} {low_label}"] = kpi_from_case(low_row, "fill_rate")
            fill_values[f"{code} {high_label}"] = kpi_from_case(high_row, "fill_rate")
            backlog_values[f"{code} {low_label}"] = kpi_from_case(low_row, "ending_backlog")
            backlog_values[f"{code} {high_label}"] = kpi_from_case(high_row, "ending_backlog")
            for label, row in ((f"{code} {low_label}", low_row), (f"{code} {high_label}", high_row)):
                root = case_output_dir(row)
                if root is None:
                    continue
                demand_csv = root / "production_demand_service_daily.csv"
                if demand_csv not in csv_cache:
                    csv_cache[demand_csv] = read_csv_rows(demand_csv)
                backlog_deltas[label] = align_series(
                    base_backlog_series,
                    aggregate_daily_series(
                        csv_cache[demand_csv],
                        value_field="backlog_end_qty",
                        item_ids={item_id},
                    ),
                )
                served_deltas[label] = align_series(
                    base_served_series,
                    cumulative_series(
                        aggregate_daily_series(
                            csv_cache[demand_csv],
                            value_field="served_qty",
                            item_ids={item_id},
                        )
                    ),
                )

        incoming = build_combo_bar_line_payload(
            fill_values,
            backlog_deltas,
            bar_title=f"{node_id} - structurel: impact demande sur disponibilite produit",
            bar_y_label="Disponibilite produit",
            line_title=f"{node_id} - structurel: ecart de backlog client vs baseline",
            line_y_label="Delta backlog",
            filename=f"{node_id}_structural_backlog.png",
        )
        outgoing = build_combo_bar_line_payload(
            backlog_values,
            served_deltas,
            bar_title=f"{node_id} - structurel: impact demande sur backlog",
            bar_y_label="Backlog final",
            line_title=f"{node_id} - structurel: ecart de servi cumule vs baseline",
            line_y_label="Delta servi cumule",
            filename=f"{node_id}_structural_served.png",
        )
        if incoming or outgoing:
            out[node_id] = {"incoming": incoming, "outgoing": outgoing}
    return out


def build_structural_sensitivity_hover_payloads(
    raw: dict[str, Any],
    structural_cases_csv: Path,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    case_rows = read_csv_rows(structural_cases_csv)
    if not case_rows:
        return {}, {}, {}

    csv_cache: dict[Path, list[dict[str, str]]] = {}
    return (
        build_factory_structural_hover_images(raw, case_rows, csv_cache),
        build_supplier_structural_hover_images(raw, case_rows, csv_cache),
        build_distribution_center_structural_hover_images(raw, case_rows, csv_cache),
    )


def write_mrp_safety_arrival_reports(
    raw: dict[str, Any],
    *,
    output_root: Path,
    mrp_trace_rows: list[dict[str, str]],
    mrp_order_rows: list[dict[str, str]],
    input_rows: list[dict[str, str]],
    input_arrival_rows: list[dict[str, str]],
    write_outputs: bool = True,
) -> dict[str, dict[str, Any]]:
    reports_dir = output_root / "reports"
    if write_outputs:
        reports_dir.mkdir(parents=True, exist_ok=True)

    factory_ids = factory_like_node_ids(raw)
    analysis_node_ids = set(factory_ids)
    for node in raw.get("nodes", []) or []:
        node_id = str(node.get("id") or "")
        if str(node.get("type") or "").strip().lower() == "distribution_center":
            analysis_node_ids.add(node_id)
    item_labels = build_item_label_lookup(raw)

    initial_stock_by_pair: dict[tuple[str, str], float] = defaultdict(float)
    for node in raw.get("nodes", []) or []:
        node_id = str(node.get("id") or "")
        for state in (((node.get("inventory") or {}).get("states")) or []):
            item_id = str(state.get("item_id") or "")
            if node_id and item_id:
                initial_stock_by_pair[(node_id, item_id)] += max(0.0, to_float(state.get("initial")) or 0.0)

    relevant_input_pairs: set[tuple[str, str]] = set()
    for node in raw.get("nodes", []) or []:
        node_id = str(node.get("id") or "")
        if node_id in factory_ids:
            for process in (node.get("processes") or []):
                for raw_input in (process.get("inputs") or []):
                    item_id = str(raw_input.get("item_id") or "")
                    if node_id and item_id:
                        relevant_input_pairs.add((node_id, item_id))
        elif node_id in analysis_node_ids:
            for state in (((node.get("inventory") or {}).get("states")) or []):
                item_id = str(state.get("item_id") or "")
                mrp_policy = state.get("mrp_policy") or {}
                if node_id and item_id:
                    if max(0.0, to_float(mrp_policy.get("safety_time_days")) or 0.0) > 0.0:
                        relevant_input_pairs.add((node_id, item_id))

    day0_stock_before_by_pair: dict[tuple[str, str], float] = defaultdict(float)
    for row in input_rows:
        node_id = str(row.get("node_id") or "")
        item_id = str(row.get("item_id") or "")
        if int(to_float(row.get("day")) or 0) != 0:
            continue
        if node_id and item_id:
            day0_stock_before_by_pair[(node_id, item_id)] += max(0.0, to_float(row.get("stock_before_production")) or 0.0)

    day0_arrivals_by_pair: dict[tuple[str, str], float] = defaultdict(float)
    first_actual_arrival_day_by_pair: dict[tuple[str, str], int] = {}
    for row in input_arrival_rows:
        node_id = str(row.get("node_id") or "")
        item_id = str(row.get("item_id") or "")
        if not node_id or not item_id:
            continue
        qty = max(0.0, to_float(row.get("arrived_qty")) or 0.0)
        if qty <= 0.0:
            continue
        day = int(to_float(row.get("day")) or 0)
        key = (node_id, item_id)
        if day == 0:
            day0_arrivals_by_pair[key] += qty
        prev = first_actual_arrival_day_by_pair.get(key)
        if prev is None or day < prev:
            first_actual_arrival_day_by_pair[key] = day

    trace_rows_by_pair: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    for row in mrp_trace_rows:
        node_id = str(row.get("node_id") or "")
        item_id = str(row.get("item_id") or "")
        if node_id in analysis_node_ids and item_id:
            trace_rows_by_pair[(node_id, item_id)].append(row)

    order_rows_by_pair: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    for row in mrp_order_rows:
        node_id = str(row.get("node_id") or "")
        item_id = str(row.get("item_id") or "")
        if node_id in analysis_node_ids and item_id and max(0.0, to_float(row.get("planned_receipt_qty")) or 0.0) > 0.0:
            order_rows_by_pair[(node_id, item_id)].append(row)

    report_rows: list[dict[str, Any]] = []
    summary_by_node: dict[str, dict[str, Any]] = {}
    for pair in sorted((set(trace_rows_by_pair) | set(order_rows_by_pair)) & relevant_input_pairs):
        node_id, item_id = pair
        trace_rows = sorted(trace_rows_by_pair.get(pair, []), key=lambda row: int(to_float(row.get("day")) or 0))
        order_rows = sorted(order_rows_by_pair.get(pair, []), key=lambda row: int(to_float(row.get("release_day")) or 0))

        safety_time_days = max(
            [max(0.0, to_float(row.get("safety_time_days")) or 0.0) for row in order_rows + trace_rows] or [0.0]
        )
        review_period_days = max([int(to_float(row.get("review_period_days")) or 0) for row in trace_rows] or [0])
        first_arrival_day = min([int(to_float(row.get("arrival_day")) or 0) for row in order_rows], default=None)
        first_need_day = min([int(to_float(row.get("implied_cover_need_day")) or 0) for row in order_rows], default=None)
        first_planned_receipt_day = min(
            [
                int(to_float(row.get("planned_receipt_min_day")) or 0)
                for row in trace_rows
                if str(row.get("planned_receipt_min_day") or "").strip() != ""
            ],
            default=None,
        )
        deltas = []
        for row in order_rows:
            arrival = to_float(row.get("arrival_day"))
            need = to_float(row.get("implied_cover_need_day"))
            if arrival is None or need is None:
                continue
            deltas.append(float(need) - float(arrival))
        min_delta = min(deltas) if deltas else None
        is_safety_respected = bool(deltas and all(delta + 1e-9 >= safety_time_days for delta in deltas))

        max_bn_qty = max([max(0.0, to_float(row.get("bn_qty")) or 0.0) for row in trace_rows] or [0.0])
        max_target_stock_qty = max([max(0.0, to_float(row.get("target_stock_qty")) or 0.0) for row in trace_rows] or [0.0])
        max_target_with_backlog_qty = max(
            [max(0.0, to_float(row.get("target_with_backlog_qty")) or 0.0) for row in trace_rows] or [0.0]
        )

        if order_rows and is_safety_respected:
            comment = "conforme: reception planifiee avant le jour de besoin de couverture"
        elif order_rows and not is_safety_respected:
            comment = "non conforme: reception planifiee trop tard vs safety time"
        elif max_bn_qty <= 1e-9:
            comment = "pas d'ordre: pas de besoin net observe"
        elif day0_stock_before_by_pair.get(pair, 0.0) + day0_arrivals_by_pair.get(pair, 0.0) >= max_target_with_backlog_qty - 1e-9:
            comment = "pas d'ordre: couverture initiale suffisante via stock seed + arrivages jour 0"
        else:
            comment = "attention: besoin net observe sans ordre planifie visible"

        report_rows.append(
            {
                "node_id": node_id,
                "item_id": item_id,
                "item_label": item_labels.get(item_id, compact_item_label(item_id)),
                "safety_time_days": round(safety_time_days, 6),
                "review_period_days": review_period_days,
                "first_arrival_day": "" if first_arrival_day is None else first_arrival_day,
                "first_need_day": "" if first_need_day is None else first_need_day,
                "first_planned_receipt_day": "" if first_planned_receipt_day is None else first_planned_receipt_day,
                "first_actual_arrival_day": "" if pair not in first_actual_arrival_day_by_pair else first_actual_arrival_day_by_pair[pair],
                "min_delta_need_minus_arrival_days": "" if min_delta is None else round(min_delta, 6),
                "is_safety_respected": int(is_safety_respected),
                "order_count": len(order_rows),
                "initial_stock_source_qty": round(initial_stock_by_pair.get(pair, 0.0), 6),
                "day0_stock_before_production_qty": round(day0_stock_before_by_pair.get(pair, 0.0), 6),
                "day0_arrivals_qty": round(day0_arrivals_by_pair.get(pair, 0.0), 6),
                "max_bn_qty": round(max_bn_qty, 6),
                "max_target_stock_qty": round(max_target_stock_qty, 6),
                "max_target_with_backlog_qty": round(max_target_with_backlog_qty, 6),
                "comment": comment,
            }
        )

        bucket = summary_by_node.setdefault(
            node_id,
            {"total": 0, "conform": 0, "non_conform": 0, "no_orders": 0, "worst_delta_days": None},
        )
        bucket["total"] += 1
        if order_rows:
            if is_safety_respected:
                bucket["conform"] += 1
            else:
                bucket["non_conform"] += 1
        else:
            bucket["no_orders"] += 1
        if min_delta is not None:
            prev = bucket.get("worst_delta_days")
            bucket["worst_delta_days"] = min_delta if prev is None else min(prev, min_delta)

    if not write_outputs:
        return summary_by_node

    csv_path = reports_dir / "mrp_safety_arrival_compliance.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "node_id",
                "item_id",
                "item_label",
                "safety_time_days",
                "review_period_days",
                "first_arrival_day",
                "first_need_day",
                "first_planned_receipt_day",
                "first_actual_arrival_day",
                "min_delta_need_minus_arrival_days",
                "is_safety_respected",
                "order_count",
                "initial_stock_source_qty",
                "day0_stock_before_production_qty",
                "day0_arrivals_qty",
                "max_bn_qty",
                "max_target_stock_qty",
                "max_target_with_backlog_qty",
                "comment",
            ],
        )
        writer.writeheader()
        writer.writerows(report_rows)

    md_path = reports_dir / "mrp_safety_arrival_compliance.md"
    lines = [
        "# MRP Safety Arrival Compliance",
        "",
        f"- Rows analysed: `{len(report_rows)}`",
        f"- Factory/DC nodes analysed: `{len(summary_by_node)}`",
        "",
        "## Summary by node",
    ]
    for node_id in sorted(summary_by_node):
        bucket = summary_by_node[node_id]
        lines.append(
            f"- {node_id}: total=`{bucket['total']}` ; conformes=`{bucket['conform']}` ; non conformes=`{bucket['non_conform']}` ; sans ordres=`{bucket['no_orders']}` ; pire delta=`{bucket['worst_delta_days'] if bucket['worst_delta_days'] is not None else 'n/a'}`"
        )
    lines.extend(["", "## Attention points"])
    flagged = [row for row in report_rows if row["order_count"] == 0 or not row["is_safety_respected"]]
    if flagged:
        for row in flagged:
            lines.append(
                f"- {row['node_id']} / {row['item_id']}: safety=`{row['safety_time_days']}` ; arrival=`{row['first_arrival_day'] or 'n/a'}` ; need=`{row['first_need_day'] or 'n/a'}` ; delta=`{row['min_delta_need_minus_arrival_days'] or 'n/a'}` ; comment=`{row['comment']}`"
            )
    else:
        lines.append("- Aucun point non conforme detecte sur les ordres MRP traces.")
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return summary_by_node


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


def latest_value_map(
    rows: list[dict[str, str]],
    *,
    node_field: str,
    value_field: str,
) -> dict[tuple[str, str], float]:
    latest: dict[tuple[str, str], tuple[int, float]] = {}
    for row in rows:
        node_id = str(row.get(node_field) or "")
        item_id = str(row.get("item_id") or "")
        if not node_id or not item_id:
            continue
        day = int(to_float(row.get("day")) or 0)
        value = float(to_float(row.get(value_field)) or 0.0)
        key = (node_id, item_id)
        prev = latest.get(key)
        if prev is None or day >= prev[0]:
            latest[key] = (day, value)
    return {key: value for key, (_day, value) in latest.items()}


def unique_preserve(seq: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for value in seq:
        if not value or value in seen:
            continue
        seen.add(value)
        out.append(value)
    return out


def preview_join(values: list[str], *, limit: int = 8) -> str:
    usable = [v for v in values if v]
    if not usable:
        return "n/a"
    if len(usable) <= limit:
        return ", ".join(usable)
    return ", ".join(usable[:limit]) + f" ... (+{len(usable) - limit})"


def metric_multiline_value(label: str, values: list[str], *, limit: int = 8) -> dict[str, str]:
    usable = [v for v in values if v]
    if not usable:
        return metric_label_value(label, "n/a")
    shown = usable[:limit]
    value = "\n".join(shown)
    if len(usable) > limit:
        value += f"\n... (+{len(usable) - limit})"
    return metric_label_value(label, value)

def render_global_model_equations_html() -> str:
    def table(rows: list[tuple[str, str, str]]) -> str:
        body = "".join(
            "<tr>"
            f"<td>{html.escape(label)}</td>"
            f"<td><code>{html.escape(equation)}</code></td>"
            f"<td>{html.escape(reading)}</td>"
            "</tr>"
            for label, equation, reading in rows
        )
        return (
            "<div class=\"modelEquationTableWrap\">"
            "<table class=\"modelEquationTable\">"
            "<thead><tr><th>Objet</th><th>Equation / definition</th><th>Lecture</th></tr></thead>"
            f"<tbody>{body}</tbody>"
            "</table>"
            "</div>"
        )

    sections = [
        (
            "1. Lecture du modele",
            table(
                [
                    ("1. Demande client", "D[c,i](t)", "Le simulateur lit chaque jour la demande client par produit fini."),
                    ("2. Service aval", "Served[c,i](t)", "Le stock disponible sert la demande ; ce qui n'est pas servi devient backlog."),
                    ("3. Signal production", "ReqProd[p,s](t)", "La demande aval et les besoins des process aval creent un signal de production par site et produit."),
                    ("4. Plan de production", "MPS[p,s](t) puis PlanLot[p,s](t)", "Le signal est transforme en commande de production, lissee, puis arrondie par regles de lot/campagne."),
                    ("5. Besoin composant", "Req_BOM[s,i](t)", "La BOM transforme le plan de production en besoin de matieres ou semi-finis."),
                    ("6. Decision MRP", "T[n,i](t), IP[n,i](t), Gap[n,i](t), BN[n,i](t)", "Le MRP compare cible, stock et receptions futures pour savoir s'il faut commander."),
                    ("7. Ordre fournisseur", "Q[f,i](t)", "Le besoin net est reparti sur les flux d'approvisionnement puis normalise par lot ou quantite standard."),
                    ("8. Transport et reception", "Ship[f,i](t), Recv[f,i](t)", "La source expedie ce qu'elle peut ; la destination recoit apres le delai simule."),
                    ("9. Etat suivant", "Etat(t+1)", "Stocks, transit, carnet ouvert et backlog sont mis a jour ; le jour suivant repart de ce nouvel etat."),
                ]
            ),
        ),
        (
            "2. Indices",
            table(
                [
                    ("t", "jour courant ; t+1 = etat apres execution du jour t", "Le simulateur avance au pas journalier."),
                    ("c", "client", "Noeud aval qui porte la demande exogene."),
                    ("n", "noeud", "Fournisseur, usine, centre de distribution ou client."),
                    ("s", "site industriel", "Usine ou site de production."),
                    ("i", "item", "Matiere premiere, semi-fini ou produit fini."),
                    ("p", "produit/process", "Produit fabrique par un process."),
                    ("f", "flux source -> destination", "Arc logistique qui transporte un item."),
                ]
            ),
        ),
        (
            "3. Parametres et constantes du scenario",
            table(
                [
                    ("alpha", "production_smoothing", "Coefficient de lissage de la commande de production. Plus alpha est haut, plus la production reagit lentement."),
                    ("production_gap_gain", "gain applique a GapProd[p,s](t)", "Part de l'ecart de stock que l'on cherche a rattraper dans la commande brute."),
                    ("fg_target_days", "jours de couverture produits finis", "Transforme le signal de production en cible de stock sortie usine."),
                    ("SS_qty[n,i]", "stock securite explicite", "Quantite de securite issue des donnees MRP quand elle existe."),
                    ("ST_days[n,i]", "delai de securite MRP", "Nombre de jours de signal MRP a couvrir en securite."),
                    ("Cover_days[n,i]", "couverture appro", "Nombre de jours de signal MRP a maintenir en stock cible pour couvrir le delai previsionnel d'approvisionnement."),
                    ("LotPolicy[p,s]", "lot fixe, min, max, multiple, max lots/semaine", "Regles industrielles qui transforment une commande continue en campagne lotifiee."),
                    ("SourcingShare[f,i]", "part de sourcing du flux", "Part du besoin net affectee a chaque source amont active."),
                    ("LT_ref[f]", "delai previsionnel MRP", "Delai utilise pour lire les dates previsionnelles du carnet."),
                    ("LT_sim[f,t]", "delai simule", "Delai effectivement applique a l'expedition pour calculer la reception reelle."),
                    ("Capacite", "capacite fournisseur ou usine", "Borne physique appliquee a l'expedition ou a la production si elle est modelisee."),
                ]
            ),
        ),
        (
            "4. Variables d'etat portees d'un jour a l'autre",
            table(
                [
                    ("S[n,i](t)", "stock disponible au noeud n pour l'item i", "Variable d'etat principale: elle est recalculee en t+1."),
                    ("B[n,i](t)", "backlog ou besoin non servi au noeud n", "Retard reporte d'un jour au suivant."),
                    ("IT[f,i](t)", "quantite en transit sur le flux f", "Quantite deja expediee mais pas encore disponible a destination."),
                    ("OO[f,i](t)", "carnet ouvert sur le flux f", "Ordres crees mais pas encore completement recus."),
                    ("OC[p,s](t)", "reste de campagne ouverte pour le produit p sur le site s", "Quantite deja lancee en campagne mais pas encore executee."),
                ]
            ),
        ),
        (
            "5. Demande et disponibilite produit",
            table(
                [
                    ("Demande", "D[c,i](t)", "Demande client exogene de l'item i au client c le jour t."),
                    ("Besoin client", "Need[c,i](t) = D[c,i](t) + B[c,i](t)", "Demande du jour plus backlog entrant."),
                    ("Service", "Served[c,i](t) = min(S[c,i](t), Need[c,i](t))", "Quantite livree au client selon le stock disponible."),
                    ("Backlog", "B[c,i](t+1) = Need[c,i](t) - Served[c,i](t)", "Retard client reporte au jour suivant."),
                    ("Signal aval", "Req[c,i](t) = Need[c,i](t)", "Point de depart de la propagation du besoin vers l'amont."),
                ]
            ),
        ),
        (
            "6. Variables auxiliaires de production",
            table(
                [
                    ("ReqProd[p,s](t)", "signal aval retenu pour produire p sur le site s", "Maximum entre demande propagee et besoin des process aval."),
                    ("TProd[p,s](t)", "cible stock du produit fabrique", "Stock que le site cherche a maintenir pour le produit p."),
                    ("GapProd[p,s](t)", "ecart sortie = cible - stock", "Positif: manque a rattraper ; negatif: avance de stock."),
                    ("RawProd[p,s](t)", "commande brute avant lissage", "Besoin courant corrige par l'ecart de stock."),
                    ("MPS[p,s](t)", "commande de production simulee lissee", "Signal de production apres lissage temporel."),
                    ("LotRef[p,s]", "taille de lot de reference", "Lot fixe si present, sinon max/min/multiple selon la politique."),
                    ("OC[p,s](t)", "reste de campagne ouverte", "Quantite deja lancee en campagne mais pas encore fabriquee."),
                    ("IntrantsDisponibles[p,s](t)", "maximum produisible avec les stocks entrants", "Limite calculee a partir des stocks intrants et des coefficients BOM."),
                ]
            ),
        ),
        (
            "7. Equations de production et propagation BOM",
            table(
                [
                    ("Signal production", "ReqProd[p,s](t) = max(Req_aval[p,s](t), Req_process_aval[p,s](t))", "Signal aval retenu pour produire: demande client propagee ou besoin d'un process aval."),
                    ("Cible sortie", "TProd[p,s](t) = max(BaseStock[s,p], fg_target_days * ReqProd[p,s](t))", "Stock cible du produit fabrique par le site."),
                    ("Ecart sortie", "GapProd[p,s](t) = TProd[p,s](t) - S[s,p](t)", "Manque ou avance de stock sur le produit fabrique."),
                    ("Commande brute", "RawProd[p,s](t) = ReqProd[p,s](t) + production_gap_gain * GapProd[p,s](t)", "Production demandee avant lissage: besoin courant plus correction de stock."),
                    ("Commande lissee", "MPS[p,s](t) = max(0, alpha * MPS[p,s](t-1) + (1-alpha) * RawProd[p,s](t))", "alpha est production_smoothing ; cela evite des a-coups trop forts."),
                    ("Declenchement lot", "si S[s,p](t) > TProd[p,s](t) - LotRef[p,s] alors nouveau lot differe", "On evite de lancer un lot complet si le stock est encore dans la bande cible."),
                    ("Plan lotifie", "PlanLot[p,s](t) = CampaignRule(MPS[p,s](t), LotPolicy[p,s], OC[p,s](t), LotsWeek[p,s])", "Application des lots fixes, minimums, multiples, campagnes ouvertes et limite de lots/semaine."),
                    ("Intrants disponibles", "IntrantsDisponibles[p,s](t) = min_i S[s,i](t) / BOM[i,p]", "Maximum produisible compte tenu des intrants modelises et des ratios BOM."),
                    ("Production executable", "Prod[p,s](t) = min(PlanLot[p,s](t), Capacite[p,s](t), IntrantsDisponibles[p,s](t))", "Production reellement faite selon capacite et intrants disponibles."),
                    ("Besoin composant MRP", "Req_BOM[s,i](t) = somme_p BOM[i,p] * PlanLot[p,s](t)", "Signal composant utilise pour commander l'amont."),
                    ("Consommation physique", "Cons[s,i](t) = somme_p BOM[i,p] * Prod[p,s](t)", "Consommation qui decremente vraiment le stock intrant."),
                ]
            ),
        ),
        (
            "8. Variables auxiliaires et decision MRP",
            table(
                [
                    ("Signal MRP", "Req[n,i](t)", "Signal journalier utilise pour dimensionner la cible: demande client, MPS/BOM ou demande propagee."),
                    ("Receptions futures", "RecvPrev[n,i](t) = somme_tau>t Recv[n,i](tau)", "Quantites deja commandees ou en transit vers le noeud."),
                    ("Position inventaire", "IP[n,i](t) = S[n,i](t) + RecvPrev[n,i](t)", "Stock disponible plus receptions futures deja planifiees."),
                    ("Cible MRP", "T[n,i](t) = max(SS_qty[n,i], ST_days[n,i] * Req[n,i](t), Cover_days[n,i] * Req[n,i](t), Target_business[n,i])", "On retient la cible active la plus contraignante."),
                    ("Ecart", "Gap[n,i](t) = T[n,i](t) + B[n,i](t) - IP[n,i](t)", "Quantite restant a couvrir apres stock et commandes deja prevues."),
                    ("Besoin net", "BN[n,i](t) = Gap[n,i](t) si Gap[n,i](t) > 0 ; sinon 0", "Le MRP ne commande que si la position inventaire ne couvre pas la cible."),
                ]
            ),
        ),
        (
            "9. Sourcing, ordre et transport",
            table(
                [
                    ("Ordre flux", "Q[f,i](t) = LotRule(SourcingShare[f,i] * BN[dst(f),i](t))", "Besoin net affecte au flux puis normalise par lot ou quantite standard."),
                    ("Expedition", "Ship[f,i](t) = min(Q[f,i](t), S[src(f),i](t), Capacite[src(f),i](t))", "Quantite sortie du stock source et envoyee vers la destination."),
                    ("Transit", "IT[f,i](t+1) = IT[f,i](t) + Ship[f,i](t) - Recv[f,i](t)", "Quantite en route entre source et destination."),
                    ("Reception", "Recv[f,i](t + LT_sim[f,t]) = Ship[f,i](t)", "Reception effective apres delai simule; le carnet affiche aussi t + LT_ref[f]."),
                    ("Carnet ouvert", "OO[f,i](t+1) = OO[f,i](t) + Q[f,i](t) - Recv[f,i](t)", "Ordres encore non recus en fin de jour."),
                ]
            ),
        ),
        (
            "10. Exemple numerique MRP simple",
            table(
                [
                    ("Hypothese", "T[n,i](t)=180 ; S[n,i](t)=100 ; RecvPrev[n,i](t)=30 ; B[n,i](t)=0", "La cible est 180, mais 100 sont deja en stock et 30 sont deja prevus en reception."),
                    ("Position inventaire", "IP[n,i](t)=100+30=130", "Stock + receptions futures deja planifiees."),
                    ("Ecart", "Gap[n,i](t)=180+0-130=50", "Il manque 50 pour couvrir la cible."),
                    ("Besoin net", "BN[n,i](t)=50", "Comme l'ecart est positif, le MRP peut creer une commande de 50 avant regles de lot/sourcing."),
                    ("Cas inverse", "si IP[n,i](t)=190 alors Gap=-10 et BN=0", "Le simulateur ne commande pas si le stock et les receptions futures couvrent deja la cible."),
                ]
            ),
        ),
        (
            "11. Flux journaliers qui modifient les stocks",
            table(
                [
                    ("Recv[n,i](t)", "receptions[n,i](t)", "Quantite de l'item i qui devient disponible au noeud n le jour t apres transport ou ordre ouvert."),
                    ("Prod[n,i](t)", "production[n,i](t)", "Quantite de l'item i fabriquee par le noeud n le jour t. C'est la production reelle executee, pas le signal MPS."),
                    ("Cons[n,i](t)", "consommations[n,i](t)", "Quantite de l'item i consommee comme intrant BOM par la production reelle du jour."),
                    ("Ship[n,i](t)", "expeditions[n,i](t)", "Quantite de l'item i sortie du stock du noeud n et envoyee vers un autre noeud ou le client."),
                    ("Served[c,i](t)", "disponibilite client", "Cas particulier de sortie aval: quantite livree au client depuis le stock disponible."),
                    ("Req_BOM[s,i](t)", "besoin composant MRP", "Signal de commande amont calcule sur le plan lotifie ; ce n'est pas une consommation physique tant que la production n'est pas executee."),
                ]
            ),
        ),
        (
            "12. Equations de la dynamique et mise a jour",
            table(
                [
                    ("Stock general", "S[n,i](t+1) = S[n,i](t) + receptions[n,i](t) + production[n,i](t) - consommations[n,i](t) - expeditions[n,i](t)", "Les termes sont definis juste avant: receptions=Recv, production=Prod, consommations=Cons, expeditions=Ship."),
                    ("Campagne ouverte", "OC[p,s](t+1) = OC[p,s](t) + CampaignStart[p,s](t) - Prod[p,s](t)", "Reste de campagne a executer apres production du jour."),
                    ("Simulation chronologique", "Etat(t) -> decisions(t) -> Etat(t+1)", "Pas de solveur global: les regles locales sont appliquees jour apres jour dans le sens du temps."),
                ]
            ),
        ),
        (
            "13. Sorties CSV utiles pour verifier le modele",
            table(
                [
                    ("data/mrp_trace_daily.csv", "T, IP, Gap, BN, RecvPrev, basis", "Permet de verifier les calculs MRP par noeud/item/jour."),
                    ("data/mrp_orders_daily.csv", "Q, source, destination, release_day, arrival_day", "Permet de verifier les ordres lances et leurs dates."),
                    ("data/production_constraint_daily.csv", "desired_qty, planned_qty_after_lot_rule, actual_qty, binding_cause", "Permet de verifier MPS, lotification, contraintes et production reelle."),
                    ("data/production_input_consumption_daily.csv", "Cons[s,i](t)", "Permet de verifier les consommations physiques issues de la BOM."),
                    ("data/production_supplier_shipments_daily.csv", "Ship[f,i](t)", "Permet de verifier les expeditions fournisseurs/source."),
                    ("data/production_input_replenishment_arrivals_daily.csv", "Recv[n,i](t)", "Permet de verifier les receptions d'intrants chez les usines."),
                    ("data/production_demand_service_daily.csv", "D, Served, Backlog", "Permet de verifier demande client, service et retard."),
                ]
            ),
        ),
        (
            "14. Limites du modele global",
            table(
                [
                    ("Optimisation", "pas de solveur APS global", "Les decisions viennent de regles MRP/production locales appliquees chronologiquement."),
                    ("Calendrier atelier", "pas de planning machine detaille", "Les lots et campagnes existent, mais pas encore les equipes, changements de format et indisponibilites fines."),
                    ("Fournisseurs", "stock/capacite/delai modelises", "Les contrats, MOQ reels, allocations et arbitrages fournisseurs restent a valider."),
                    ("Couts", "achats reels + estimation production + couts logistiques hypotheses", "La production est une estimation de cout de conversion pharma allouee sur volumes reels; transport, stockage et urgence restent parametrables tant que les couts industriels reels ne sont pas fournis."),
                ]
            ),
        ),
    ]
    section_html = "".join(
        "<section class=\"modelEquationSection\">"
        f"<h3>{html.escape(title)}</h3>"
        f"{content}"
        "</section>"
        for title, content in sections
    )
    return (
        "<div class=\"modelEquationPanel\">"
        "<p class=\"modelEquationIntro\">"
        "Cette vue decrit le modele complet, pas seulement le noeud selectionne. Elle part de la demande client, transforme cette demande en production, propage les besoins par la BOM, lance les ordres MRP vers l'amont, puis met a jour les stocks, le transit, le carnet ouvert et le backlog."
        "</p>"
        f"{section_html}"
        "</div>"
    )


def latest_rows_by_pair(rows: list[dict[str, str]], *, node_field: str) -> dict[tuple[str, str], dict[str, str]]:
    latest: dict[tuple[str, str], tuple[int, dict[str, str]]] = {}
    for row in rows:
        node_id = str(row.get(node_field) or "")
        item_id = str(row.get("item_id") or row.get("output_item_id") or "")
        if not node_id or not item_id:
            continue
        day = int(to_float(row.get("day")) or 0)
        key = (node_id, item_id)
        prev = latest.get(key)
        if prev is None or day >= prev[0]:
            latest[key] = (day, row)
    return {key: value for key, (_day, value) in latest.items()}


def describe_processes(
    processes: list[dict[str, Any]],
    item_labels: dict[str, str],
) -> tuple[list[str], list[str], list[str], list[str]]:
    process_labels: list[str] = []
    io_rules: list[str] = []
    lot_rules: list[str] = []
    source_refs: list[str] = []
    for proc in processes:
        proc_id = str(proc.get("id") or "")
        inputs = [
            item_labels.get(str(inp.get("item_id") or ""), compact_item_label(str(inp.get("item_id") or "")))
            for inp in (proc.get("inputs") or [])
            if str(inp.get("item_id") or "")
        ]
        outputs = [
            item_labels.get(str(out.get("item_id") or ""), compact_item_label(str(out.get("item_id") or "")))
            for out in (proc.get("outputs") or [])
            if str(out.get("item_id") or "")
        ]
        if proc_id or inputs or outputs:
            process_labels.append(
                f"{proc_id or 'process'}: {preview_join(inputs, limit=4)} -> {preview_join(outputs, limit=4)}"
            )
        for inp in (proc.get("inputs") or []):
            item_id = str(inp.get("item_id") or "")
            if not item_id:
                continue
            ratio = to_float(inp.get("ratio_per_batch"))
            ratio_unit = str(inp.get("ratio_unit") or "").strip()
            io_rules.append(
                f"{item_labels.get(item_id, compact_item_label(item_id))}: {fmt_qty(ratio, 3)} {ratio_unit or ''}".strip()
            )
        lot_sizing = proc.get("lot_sizing") or {}
        lot_exec = proc.get("lot_execution") or {}
        lot_parts = []
        if to_float(lot_sizing.get("fixed_lot_qty")):
            lot_parts.append(f"fixe={fmt_qty(lot_sizing.get('fixed_lot_qty'), 0)}")
        if to_float(lot_sizing.get("min_lot_qty")):
            lot_parts.append(f"min={fmt_qty(lot_sizing.get('min_lot_qty'), 0)}")
        if to_float(lot_sizing.get("max_lot_qty")):
            lot_parts.append(f"max={fmt_qty(lot_sizing.get('max_lot_qty'), 0)}")
        if to_float(lot_sizing.get("lot_multiple_qty")):
            lot_parts.append(f"multiple={fmt_qty(lot_sizing.get('lot_multiple_qty'), 0)}")
        if to_float(lot_exec.get("max_lots_per_week")):
            lot_parts.append(f"max_lots/sem={fmt_qty(lot_exec.get('max_lots_per_week'), 0)}")
        if lot_parts:
            lot_rules.append(f"{proc_id or 'process'}: " + " ; ".join(lot_parts))
        source_parts = [
            str((proc.get("attrs") or {}).get("source_workbook") or ""),
            str((proc.get("attrs") or {}).get("source_sheet") or ""),
        ]
        source_ref = " / ".join(part for part in source_parts if part)
        if source_ref:
            source_refs.append(f"{proc_id or 'process'}: {source_ref}")
    return (
        unique_preserve(process_labels),
        unique_preserve(io_rules),
        unique_preserve(lot_rules),
        unique_preserve(source_refs),
    )


def build_model_panel_metrics(
    raw: dict[str, Any],
    *,
    sim_input_stocks_csv: Path,
    sim_output_products_csv: Path,
    input_arrivals_csv: Path,
    demand_service_csv: Path,
    supplier_shipments_csv: Path,
    supplier_stocks_csv: Path,
    supplier_stock_flows_csv: Path | None,
    supplier_capacity_csv: Path,
    supplier_nominal_parameters_csv: Path | None,
    factory_nominal_capacities_csv: Path | None,
    dc_stocks_csv: Path,
    production_constraint_csv: Path,
    write_derived_artifacts: bool = True,
) -> dict[str, Any]:
    item_labels = build_item_label_lookup(raw)
    incoming_items, outgoing_items = build_edge_item_sets(raw)
    incoming_sources, outgoing_targets = build_node_relationships(raw)
    node_types = build_node_type_lookup(raw)
    node_by_id = {
        str(node.get("id") or ""): node
        for node in (raw.get("nodes") or [])
        if isinstance(node, dict) and node.get("id") is not None and not is_pilotage_hidden_node(str(node.get("id") or ""))
    }
    output_root = output_root_from_csv(demand_service_csv)
    summary_file = output_root / "summaries" / "first_simulation_summary.json"
    data_root = output_root / "data"
    summary = json.loads(summary_file.read_text(encoding="utf-8")) if summary_file.exists() else {}
    policy = (summary.get("policy") or {}) if isinstance(summary, dict) else {}
    init_policy = (policy.get("initialization_policy") or {}) if isinstance(policy, dict) else {}
    horizon_days = int(
        to_float(
            summary.get("timeline_days")
            or summary.get("sim_days")
            or summary.get("total_simulated_timeline_days")
            or read_timeline_horizon_days(output_root)
            or 0
        )
        or 0
    )
    horizon_end_day = horizon_days - 1 if horizon_days > 0 else None

    def in_run_horizon(row: dict[str, str], day_field: str = "day") -> bool:
        if horizon_end_day is None:
            return True
        day = int(to_float(row.get(day_field)) or 0)
        return 0 <= day <= horizon_end_day

    mrp_trace_rows = read_csv_rows(data_root / "mrp_trace_daily.csv")
    mrp_order_rows = read_csv_rows(data_root / "mrp_orders_daily.csv")
    assumptions_ledger_rows = read_csv_rows(data_root / "assumptions_ledger.csv")
    supplier_risk_applied_rows = read_csv_rows(data_root / "supplier_risk_events_applied_daily.csv")
    supplier_state_risk_event_rows = read_csv_rows(data_root / "supplier_state_dependent_risk_events.csv")

    input_rows = read_csv_rows(sim_input_stocks_csv)
    output_rows = read_csv_rows(sim_output_products_csv)
    input_arrival_rows = read_csv_rows(input_arrivals_csv)
    demand_rows = read_csv_rows(demand_service_csv)
    supplier_ship_rows = [row for row in read_csv_rows(supplier_shipments_csv) if in_run_horizon(row)]
    supplier_stock_rows = read_csv_rows(supplier_stocks_csv)
    supplier_stock_flow_rows = (
        read_csv_rows(supplier_stock_flows_csv)
        if supplier_stock_flows_csv is not None and supplier_stock_flows_csv.exists()
        else []
    )
    supplier_local_criticality_rows = (
        read_csv_rows(data_root / "supplier_local_criticality_ranking.csv")
        if (data_root / "supplier_local_criticality_ranking.csv").exists()
        else []
    )
    supplier_capacity_rows = read_csv_rows(supplier_capacity_csv)
    supplier_nominal_rows = (
        read_csv_rows(supplier_nominal_parameters_csv)
        if supplier_nominal_parameters_csv is not None and supplier_nominal_parameters_csv.exists()
        else []
    )
    factory_nominal_capacity_rows = (
        read_csv_rows(factory_nominal_capacities_csv)
        if factory_nominal_capacities_csv is not None and factory_nominal_capacities_csv.exists()
        else []
    )
    dc_stock_rows = read_csv_rows(dc_stocks_csv)
    constraint_rows = read_csv_rows(production_constraint_csv)
    mrp_safety_summary_by_node = write_mrp_safety_arrival_reports(
        raw,
        output_root=output_root,
        mrp_trace_rows=mrp_trace_rows,
        mrp_order_rows=mrp_order_rows,
        input_rows=input_rows,
        input_arrival_rows=input_arrival_rows,
        write_outputs=write_derived_artifacts,
    )

    latest_input_stock = latest_value_map(input_rows, node_field="node_id", value_field="stock_end_of_day")
    latest_output_stock = latest_value_map(output_rows, node_field="node_id", value_field="stock_end_of_day")
    latest_supplier_stock = latest_value_map(supplier_stock_rows, node_field="node_id", value_field="stock_end_of_day")
    latest_dc_stock = latest_value_map(dc_stock_rows, node_field="node_id", value_field="stock_end_of_day")
    latest_output_rows = latest_rows_by_pair(output_rows, node_field="node_id")
    latest_dc_rows = latest_rows_by_pair(dc_stock_rows, node_field="node_id")
    latest_supplier_rows = latest_rows_by_pair(supplier_stock_rows, node_field="node_id")
    latest_input_arrival_rows = latest_rows_by_pair(input_arrival_rows, node_field="node_id")

    constraint_by_node: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in constraint_rows:
        constraint_by_node[str(row.get("node_id") or "")].append(row)

    demand_by_node: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in demand_rows:
        demand_by_node[str(row.get("node_id") or "")].append(row)

    supplier_ship_by_node: dict[str, list[dict[str, str]]] = defaultdict(list)
    supplier_ship_by_edge: dict[tuple[str, str, str], list[dict[str, str]]] = defaultdict(list)
    for row in supplier_ship_rows:
        src = str(row.get("src_node_id") or "")
        dst = str(row.get("dst_node_id") or "")
        item_id = str(row.get("item_id") or "")
        supplier_ship_by_node[src].append(row)
        supplier_ship_by_edge[(src, dst, item_id)].append(row)

    supplier_cap_by_node: dict[str, list[dict[str, str]]] = defaultdict(list)
    supplier_cap_by_pair: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    for row in supplier_capacity_rows:
        node_id = str(row.get("node_id") or "")
        item_id = str(row.get("item_id") or "")
        supplier_cap_by_node[node_id].append(row)
        supplier_cap_by_pair[(node_id, item_id)].append(row)

    supplier_nominal_by_node: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in supplier_nominal_rows:
        node_id = str(row.get("supplier_id") or "")
        if node_id:
            supplier_nominal_by_node[node_id].append(row)

    factory_nominal_capacity_by_node: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in factory_nominal_capacity_rows:
        node_id = str(row.get("node_id") or "")
        if node_id:
            factory_nominal_capacity_by_node[node_id].append(row)

    input_arrivals_by_node: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in input_arrival_rows:
        node_id = str(row.get("node_id") or "")
        if node_id:
            input_arrivals_by_node[node_id].append(row)

    input_stocks_by_node: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in input_rows:
        node_id = str(row.get("node_id") or "")
        if node_id:
            input_stocks_by_node[node_id].append(row)

    dc_stocks_by_node: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in dc_stock_rows:
        node_id = str(row.get("node_id") or "")
        if node_id:
            dc_stocks_by_node[node_id].append(row)

    supplier_stocks_by_node: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in supplier_stock_rows:
        node_id = str(row.get("node_id") or "")
        if node_id:
            supplier_stocks_by_node[node_id].append(row)

    supplier_stock_flows_by_node: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in supplier_stock_flow_rows:
        node_id = str(row.get("node_id") or "")
        if node_id:
            supplier_stock_flows_by_node[node_id].append(row)

    supplier_risk_applied_by_node: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in supplier_risk_applied_rows:
        node_id = str(row.get("supplier_id") or "")
        if node_id:
            supplier_risk_applied_by_node[node_id].append(row)

    supplier_risk_config_by_node: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in supplier_state_risk_event_rows:
        node_id = str(row.get("supplier_id") or "")
        if node_id:
            supplier_risk_config_by_node[node_id].append(dict(row))
    for row in assumptions_ledger_rows:
        if str(row.get("category") or "") != "supplier_risk_event":
            continue
        payload_text = str(row.get("payload_json") or "").strip()
        payload: dict[str, Any] = {}
        if payload_text:
            try:
                decoded = json.loads(payload_text)
                if isinstance(decoded, dict):
                    payload = decoded
            except json.JSONDecodeError:
                payload = {}
        node_id = str(payload.get("supplier_id") or row.get("node_id") or "")
        if node_id:
            supplier_risk_config_by_node[node_id].append(payload)

    simulated_risk_metrics = build_simulated_supplier_risk_metrics(
        configured_by_node=supplier_risk_config_by_node,
        applied_by_node=supplier_risk_applied_by_node,
    )

    supplier_local_criticality_by_node: dict[str, dict[str, str]] = {}
    for row in supplier_local_criticality_rows:
        node_id = str(row.get("supplier_id") or "")
        if node_id and node_id not in supplier_local_criticality_by_node:
            supplier_local_criticality_by_node[node_id] = row

    def rows_by_node_item(rows: list[dict[str, str]], *, node_field: str = "node_id") -> dict[tuple[str, str], list[dict[str, str]]]:
        out: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
        for row in rows:
            node_id = str(row.get(node_field) or "")
            item_id = str(row.get("item_id") or "")
            if node_id and item_id:
                out[(node_id, item_id)].append(row)
        return out

    input_rows_by_pair = rows_by_node_item(input_rows)
    output_rows_by_pair = rows_by_node_item(output_rows)
    input_arrivals_by_pair = rows_by_node_item(input_arrival_rows)
    supplier_stock_rows_by_pair = rows_by_node_item(supplier_stock_rows)
    dc_stock_rows_by_pair = rows_by_node_item(dc_stock_rows)

    latest_mrp_trace_by_pair: dict[tuple[str, str], dict[str, str]] = {}
    mrp_trace_rows_by_pair: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    mrp_trace_by_node: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in mrp_trace_rows:
        node_id = str(row.get("node_id") or "")
        item_id = str(row.get("item_id") or "")
        if not node_id or not item_id:
            continue
        mrp_trace_by_node[node_id].append(row)
        mrp_trace_rows_by_pair[(node_id, item_id)].append(row)
        key = (node_id, item_id)
        day = int(to_float(row.get("day")) or 0)
        prev = latest_mrp_trace_by_pair.get(key)
        if prev is None or day >= int(to_float(prev.get("day")) or 0):
            latest_mrp_trace_by_pair[key] = row

    supplier_ids = {
        str(node.get("id") or "")
        for node in raw.get("nodes", []) or []
        if str(node.get("type") or "") == "supplier_dc"
    }
    outgoing_edges_by_node: dict[str, list[dict[str, Any]]] = defaultdict(list)
    incoming_edges_by_node: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for edge in raw.get("edges", []) or []:
        src = str(edge.get("from") or "")
        dst = str(edge.get("to") or "")
        if is_pilotage_hidden_edge(src, dst):
            continue
        if src:
            outgoing_edges_by_node[src].append(edge)
        if dst:
            incoming_edges_by_node[dst].append(edge)

    mrp_orders_by_node: dict[str, list[dict[str, str]]] = defaultdict(list)
    mrp_orders_by_edge: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in mrp_order_rows:
        if not is_display_order_row(row):
            continue
        node_id = str(row.get("node_id") or "")
        src_node_id = str(row.get("src_node_id") or "")
        dst_node_id = str(row.get("dst_node_id") or "")
        edge_id = str(row.get("edge_id") or "")

        linked_node_ids: list[str] = []
        if node_id:
            linked_node_ids.append(node_id)
        if src_node_id in supplier_ids:
            linked_node_ids.append(src_node_id)
        if dst_node_id in supplier_ids:
            linked_node_ids.append(dst_node_id)

        for linked_node_id in dict.fromkeys(linked_node_ids):
            mrp_orders_by_node[linked_node_id].append(row)
        if edge_id:
            mrp_orders_by_edge[edge_id].append(row)

    assumptions_by_node: dict[str, list[dict[str, str]]] = defaultdict(list)
    assumptions_by_edge: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in assumptions_ledger_rows:
        node_id = str(row.get("node_id") or "")
        edge_id = str(row.get("edge_id") or "")
        if node_id:
            assumptions_by_node[node_id].append(row)
        if edge_id:
            assumptions_by_edge[edge_id].append(row)

    def aggregate_trace_series(rows: list[dict[str, str]], field: str) -> list[tuple[int, float]]:
        by_day: dict[int, float] = defaultdict(float)
        for row in rows:
            day = int(to_float(row.get("day")) or 0)
            by_day[day] += max(0.0, to_float(row.get(field)) or 0.0)
        return sorted(by_day.items())

    def aggregate_order_series(
        rows: list[dict[str, str]],
        field: str,
        *,
        day_field: str = "day",
        bucket_days: int = 1,
    ) -> list[tuple[int, float]]:
        by_day: dict[int, float] = defaultdict(float)
        for row in rows:
            day = resolved_order_day(row, day_field)
            if bucket_days > 1:
                day = (day // bucket_days) * bucket_days
            by_day[day] += max(0.0, to_float(row.get(field)) or 0.0)
        return sorted(by_day.items())

    def aggregate_effective_order_receipt_series(
        rows: list[dict[str, str]],
        field: str,
        *,
        bucket_days: int = 1,
    ) -> list[tuple[int, float]]:
        by_day: dict[int, float] = defaultdict(float)
        for row in rows:
            day_value = effective_order_receipt_day(row)
            if day_value is None or math.isnan(day_value):
                continue
            day = int(round(day_value))
            if bucket_days > 1:
                day = (day // bucket_days) * bucket_days
            qty = max(0.0, to_float(row.get(field)) or 0.0)
            if qty <= 1e-9:
                continue
            by_day[day] += qty
        return sorted(by_day.items())

    def bucket_series_points(points: list[tuple[int, float]], bucket_days: int = 7) -> list[tuple[int, float]]:
        if bucket_days <= 1:
            return points
        by_bucket: dict[int, float] = defaultdict(float)
        for point_day, point_value in points:
            bucket_day = (int(point_day) // bucket_days) * bucket_days
            by_bucket[bucket_day] += float(point_value)
        return sorted(by_bucket.items())

    def average_order_series(rows: list[dict[str, str]], field: str) -> list[tuple[int, float]]:
        sums: dict[int, float] = defaultdict(float)
        counts: dict[int, int] = defaultdict(int)
        for row in rows:
            day = int(to_float(row.get("day")) or 0)
            value = to_float(row.get(field))
            if value is None or math.isnan(value):
                continue
            sums[day] += float(value)
            counts[day] += 1
        return [(day, sums[day] / counts[day]) for day in sorted(sums) if counts[day] > 0]

    def average_derived_order_series(
        rows: list[dict[str, str]],
        derive_value: Callable[[dict[str, str]], float | None],
    ) -> list[tuple[int, float]]:
        sums: dict[int, float] = defaultdict(float)
        counts: dict[int, int] = defaultdict(int)
        for row in rows:
            day_value = order_placed_day(row)
            if day_value is None:
                continue
            value = derive_value(row)
            if value is None or math.isnan(value):
                continue
            day = int(round(day_value))
            sums[day] += float(value)
            counts[day] += 1
        return [(day, sums[day] / counts[day]) for day in sorted(sums) if counts[day] > 0]

    def status_bar_figure(rows: list[dict[str, str]], *, field: str, title: str) -> dict[str, Any] | None:
        counts: dict[str, float] = defaultdict(float)
        for row in rows:
            key = str(row.get(field) or "n/a")
            counts[key] += 1.0
        if not counts:
            return None
        return build_bar_chart_figure(counts, title=title, y_label="Nombre d'ordres")

    def lead_distribution_figure(
        rows: list[dict[str, str]],
        *,
        title: str,
        planned_lead_days: float | None,
    ) -> dict[str, Any] | None:
        lead_qty_rows: list[tuple[float, float]] = []
        for row in rows:
            lead = to_float(row.get("lead_days"))
            if lead is None or math.isnan(lead):
                continue
            lead_qty_rows.append((max(0.0, lead), max(0.0, to_float(row.get("shipped_qty")) or 0.0)))
        if not lead_qty_rows:
            return None
        lead_values = [lead for lead, _ in lead_qty_rows]
        min_lead = min(lead_values)
        max_lead = max(lead_values)
        distinct_leads = sorted({round(lead, 1) for lead in lead_values})
        bucket_width = 1.0
        if len(distinct_leads) > 18:
            bucket_width = max(1.0, math.ceil((max_lead - min_lead + 1.0) / 14.0))

        def bucket_key(lead: float) -> float:
            if bucket_width <= 1.0:
                return float(round(lead))
            bucket_start = math.floor(lead / bucket_width) * bucket_width
            return float(bucket_start + (bucket_width / 2.0))

        counts: dict[float, float] = defaultdict(float)
        qty_by_bucket: dict[float, float] = defaultdict(float)
        for lead, qty in lead_qty_rows:
            key = bucket_key(lead)
            counts[key] += 1.0
            qty_by_bucket[key] += qty
        ordered_keys = sorted(counts)
        x_values = [float(key) for key in ordered_keys]
        top_y = [counts[key] for key in ordered_keys]
        bottom_y = [qty_by_bucket[key] for key in ordered_keys]
        planned_lead = planned_lead_days
        has_planned_lead = planned_lead is not None and not math.isnan(planned_lead) and planned_lead >= 0.0
        top_extra_traces: list[dict[str, Any]] = []
        bottom_extra_traces: list[dict[str, Any]] = []
        if has_planned_lead:
            planned_label = f"Delai transport prevu ({planned_lead:g} j)"
            top_extra_traces.append(
                {
                    "type": "scatter",
                    "mode": "lines",
                    "name": planned_label,
                    "x": [planned_lead, planned_lead],
                    "y": [0.0, max(top_y) if top_y else 1.0],
                    "line": {"color": "#111827", "dash": "dot", "width": 2.6},
                    "showlegend": True,
                }
            )
            bottom_extra_traces.append(
                {
                    "type": "scatter",
                    "mode": "lines",
                    "name": planned_label,
                    "x": [planned_lead, planned_lead],
                    "y": [0.0, max(bottom_y) if bottom_y else 1.0],
                    "line": {"color": "#111827", "dash": "dot", "width": 2.6},
                    "showlegend": False,
                }
            )
        return build_dual_panel_figure(
            title=title,
            top_title="Nombre d'expeditions par delai transport simule",
            top_x_label="Delai transport simule (jours)",
            top_y_label="Expeditions",
            top_kind="bar",
            top_x=x_values,
            top_y=top_y,
            bottom_title="Quantite expediee par delai transport simule",
            bottom_x_label="Delai transport simule (jours)",
            bottom_y_label="Quantite",
            bottom_kind="bar",
            bottom_x=x_values,
            bottom_y=bottom_y,
            top_extra_traces=top_extra_traces,
            bottom_extra_traces=bottom_extra_traces,
            show_legend=has_planned_lead,
        )

    def render_mrp_risk_summary_html(
        node_id: str,
        node_type: str,
        *,
        safety_summary: dict[str, Any],
        node_trace_rows: list[dict[str, str]],
        node_orders: list[dict[str, str]],
        stock_rows: list[dict[str, str]],
        supplier_stock_rows_node: list[dict[str, str]],
        supplier_capacity_rows_node: list[dict[str, str]],
        supplier_risk_rows_node: list[dict[str, str]],
        dormant_reason: str | None,
    ) -> str:
        risk_rows: list[tuple[str, str, str, str]] = []

        def add(severity: str, topic: str, signal: str, interpretation: str) -> None:
            risk_rows.append((severity, topic, signal, interpretation))

        total_safety = int(to_float(safety_summary.get("total")) or 0)
        non_conform = int(to_float(safety_summary.get("non_conform")) or 0)
        no_orders = int(to_float(safety_summary.get("no_orders")) or 0)
        conform = int(to_float(safety_summary.get("conform")) or 0)
        if total_safety > 0:
            if non_conform > 0:
                add(
                    "RISQUE",
                    "Arrivees vs delai securite",
                    f"{non_conform}/{total_safety} non conformes",
                    "Des receptions planifiees arrivent trop tard par rapport au delai de securite.",
                )
            elif no_orders > 0:
                add(
                    "ATTENTION",
                    "Arrivees vs delai securite",
                    f"{no_orders}/{total_safety} sans ordre",
                    "Un besoin couvert par safety time n'a pas d'ordre MRP trace.",
                )
            else:
                add(
                    "OK",
                    "Arrivees vs delai securite",
                    f"{conform}/{total_safety} conformes",
                    "Les premieres receptions planifiees respectent le delai de securite.",
                )

        trace_by_item: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
        trace_days_by_item: dict[str, set[int]] = defaultdict(set)
        for row in node_trace_rows:
            item_id = str(row.get("item_id") or "")
            if not item_id:
                continue
            day = int(to_float(row.get("day")) or 0)
            bn_qty = max(0.0, to_float(row.get("bn_qty")) or 0.0)
            safety_floor = max(0.0, to_float(row.get("safety_floor_qty")) or 0.0)
            target_stock = max(0.0, to_float(row.get("target_stock_qty")) or 0.0)
            inventory_position = max(0.0, to_float(row.get("inventory_position_qty")) or 0.0)
            trace_by_item[item_id]["max_bn_qty"] = max(trace_by_item[item_id]["max_bn_qty"], bn_qty)
            trace_by_item[item_id]["max_safety_floor_qty"] = max(
                trace_by_item[item_id]["max_safety_floor_qty"],
                safety_floor,
            )
            trace_by_item[item_id]["max_target_stock_qty"] = max(
                trace_by_item[item_id]["max_target_stock_qty"],
                target_stock,
            )
            trace_by_item[item_id]["worst_inventory_gap_qty"] = min(
                trace_by_item[item_id].get("worst_inventory_gap_qty", 0.0),
                inventory_position - target_stock,
            )
            if bn_qty > 1e-9:
                trace_days_by_item[item_id].add(day)

        bn_items = [
            (item_id, stats.get("max_bn_qty", 0.0), len(trace_days_by_item.get(item_id, set())))
            for item_id, stats in trace_by_item.items()
            if stats.get("max_bn_qty", 0.0) > 1e-9
        ]
        if bn_items:
            item_id, max_bn, bn_days = max(bn_items, key=lambda row: (row[1], row[2]))
            severity = "ATTENTION" if bn_days >= 30 else "INFO"
            add(
                severity,
                "Besoin net MRP",
                f"{item_labels.get(item_id, compact_item_label(item_id))}: max={fmt_qty(max_bn, 0)} ; jours={bn_days}",
                "La position inventaire passe sous la cible MRP; c'est un signal de commande, pas forcement une rupture.",
            )
        elif node_trace_rows:
            add("OK", "Besoin net MRP", "aucun besoin net positif", "La position inventaire couvre les cibles MRP tracees.")

        stock_min_by_item: dict[str, float] = {}
        for row in stock_rows:
            item_id = str(row.get("item_id") or "")
            if not item_id:
                continue
            value = max(0.0, to_float(row.get("stock_end_of_day")) or 0.0)
            stock_min_by_item[item_id] = min(stock_min_by_item.get(item_id, value), value)
        below_safety: list[tuple[float, str, float, float]] = []
        for item_id, min_stock in stock_min_by_item.items():
            safety_floor = trace_by_item.get(item_id, {}).get("max_safety_floor_qty", 0.0)
            if safety_floor <= 1e-9:
                continue
            ratio = min_stock / safety_floor
            if ratio < 1.0:
                below_safety.append((ratio, item_id, min_stock, safety_floor))
        if below_safety:
            ratio, item_id, min_stock, safety_floor = min(below_safety, key=lambda row: row[0])
            add(
                "RISQUE",
                "Stock physique vs securite",
                f"{item_labels.get(item_id, compact_item_label(item_id))}: min={fmt_qty(min_stock, 0)} / cible={fmt_qty(safety_floor, 0)} ({ratio:.2f}x)",
                "Le stock reel simule passe sous le stock equivalent au delai de securite.",
            )
        elif stock_min_by_item and any(stats.get("max_safety_floor_qty", 0.0) > 1e-9 for stats in trace_by_item.values()):
            add("OK", "Stock physique vs securite", "pas de passage sous plancher detecte", "Le stock reel reste au-dessus des planchers de securite traces.")

        non_received = [row for row in node_orders if str(row.get("order_status_end_of_run") or "") != "received"]
        if non_received:
            add(
                "ATTENTION",
                "Carnet fin d'horizon",
                f"{len(non_received)} ordre(s) non recus en fin de run",
                "Souvent normal pres de la fin d'horizon, mais a controler si cela concerne un item critique.",
            )
        elif node_orders:
            add("OK", "Carnet fin d'horizon", "tous les ordres traces sont recus", "Pas d'ordre ouvert restant sur le run courant.")

        if dormant_reason:
            add("INFO", "Diagnostic noeud", dormant_reason, "Point de modelisation a valider si le noeud devrait etre actif.")

        if not risk_rows:
            add("INFO", "Risque MRP", "aucun signal disponible", "Aucune trace MRP ou donnee stock/carnet exploitable pour ce noeud.")

        severity_rank = {"RISQUE": 0, "ATTENTION": 1, "INFO": 2, "OK": 3}
        risk_rows.sort(key=lambda row: (severity_rank.get(row[0], 9), row[1]))
        rows_html = []
        for severity, topic, signal, interpretation in risk_rows:
            rows_html.append(
                "<tr>"
                f"<td>{html.escape(severity)}</td>"
                f"<td>{html.escape(topic)}</td>"
                f"<td>{html.escape(signal)}</td>"
                f"<td>{html.escape(interpretation)}</td>"
                "</tr>"
            )
        return "".join(
            [
                "<div class=\"factoryHtmlPanelContent\">",
                f"<div class=\"orderLedgerTextHeader\">{html.escape(node_id)} - risques MRP explicites</div>",
                "<div class=\"orderLedgerStatus\">Un risque ici est un signal actionnable: non-respect safety time, stock sous plancher, besoin net durable, ordre ouvert ou fournisseur fragile. Une trace MRP normale n'est pas une exception.</div>",
                "<div class=\"kpiFormulaTableWrap\"><table class=\"kpiFormulaTable\">",
                "<thead><tr><th>Niveau</th><th>Sujet</th><th>Signal</th><th>Lecture</th></tr></thead>",
                "<tbody>",
                "".join(rows_html),
                "</tbody></table></div>",
                "</div>",
            ]
        )

    customer_latest_by_pair: dict[tuple[str, str], dict[str, str]] = {}
    for row in demand_rows:
        node_id = str(row.get("node_id") or "")
        item_id = str(row.get("item_id") or "")
        if not node_id or not item_id:
            continue
        day = int(to_float(row.get("day")) or 0)
        key = (node_id, item_id)
        prev = customer_latest_by_pair.get(key)
        if prev is None or day >= int(to_float(prev.get("day")) or 0):
            customer_latest_by_pair[key] = row

    edge_metrics = build_edge_metrics(raw, supplier_shipments_csv, horizon_days=horizon_days or None)
    factory_like_ids = factory_like_node_ids(raw)
    nodes_payload: dict[str, Any] = {}
    edges_payload: dict[str, Any] = {}
    uncertainty_metric_nodes: dict[str, Any] = {}
    uncertainty_metric_edges: dict[str, Any] = {}

    for node_id, node in sorted(node_by_id.items()):
        if is_pilotage_hidden_node(node_id):
            continue
        node_type = str(node.get("type") or "")
        role_raw = str(node.get("role_raw") or "")
        location = str(node.get("location_ID") or "n/a")
        attrs = node.get("attrs") or {}
        inv_states = ((node.get("inventory") or {}).get("states") or [])
        processes = node.get("processes") or []
        review_period = (((node.get("policies") or {}).get("simulation_policy") or {}).get("review_period_days"))
        process_labels, io_rules, process_lot_rules, process_source_refs = describe_processes(processes, item_labels)
        inventory_lines: list[str] = []
        state_var_lines: list[str] = []
        assumption_lines: list[str] = []
        source_refs: list[str] = []
        interaction_lines: list[str] = []
        if attrs.get("source_workbook") or attrs.get("source_sheet"):
            source_refs.append(
                " / ".join(
                    part for part in [str(attrs.get("source_workbook") or ""), str(attrs.get("source_sheet") or "")] if part
                )
            )
        source_refs.extend(process_source_refs)
        for state in inv_states:
            item_id = str(state.get("item_id") or "")
            if not item_id:
                continue
            if is_simulation_hidden_item(item_id):
                continue
            label = item_labels.get(item_id, compact_item_label(item_id))
            initial = fmt_qty(state.get("initial"), 1)
            uom = str(state.get("uom") or "").strip()
            mrp_policy = state.get("mrp_policy") or {}
            safety_time = to_float(mrp_policy.get("safety_time_days"))
            safety_stock = to_float(mrp_policy.get("safety_stock_qty"))
            policy_bits = []
            if safety_time and safety_time > 0:
                policy_bits.append(f"safety_time={fmt_days(safety_time, 0)}")
            if safety_stock and safety_stock > 0:
                policy_bits.append(f"safety_stock={fmt_qty(safety_stock, 0)}")
            inventory_lines.append(
                f"{label}: initial={initial} {uom}".strip() + (f" ; {' ; '.join(policy_bits)}" if policy_bits else "")
            )
            if mrp_policy.get("source"):
                source_refs.append(f"{label}: {mrp_policy.get('source')}")
        interaction_lines.append(
            f"amont={len(incoming_sources.get(node_id, set()))} noeuds ; aval={len(outgoing_targets.get(node_id, set()))} noeuds"
        )
        if incoming_items.get(node_id):
            interaction_lines.append(
                "items amont: " + preview_join(
                    [
                        item_labels.get(i, compact_item_label(i))
                        for i in sorted(incoming_items.get(node_id, set()))
                        if not is_simulation_hidden_item(i)
                    ],
                    limit=10,
                )
            )
        if outgoing_items.get(node_id):
            interaction_lines.append(
                "items aval: " + preview_join(
                    [
                        item_labels.get(i, compact_item_label(i))
                        for i in sorted(outgoing_items.get(node_id, set()))
                        if not is_simulation_hidden_item(i)
                    ],
                    limit=10,
                )
            )
        summary_lines: list[dict[str, str]] = [
            metric_section("Element"),
            metric_label_value("Type", node_type or "n/a"),
            metric_label_value("Role", role_raw or "n/a"),
            metric_label_value("Localisation", location),
            metric_label_value("Id", node_id),
            metric_section("Vue metier"),
            metric_label_value("Principe", "Le simulateur cherche a maintenir les stocks autour d'une cible MRP, sans commander ce qui est deja couvert par le stock ou les receptions futures."),
            metric_label_value("Decision", "A chaque revue, il calcule l'ecart a couvrir. Si cet ecart est positif, il cree un besoin net ; sinon il ne commande rien."),
            metric_label_value("Execution", "Le besoin net devient un ordre lotifie ou normalise par flux d'approvisionnement, puis il arrive selon les delais et les stocks/capacites disponibles."),
            metric_label_value("Modele complet", "Le bouton Equations du modele complet detaille les indices, les variables d'etat et les equations dynamiques globales."),
        ]

        if node_type == "customer":
            rows = demand_by_node.get(node_id, [])
            total_demand = sum(max(0.0, to_float(r.get("demand_qty")) or 0.0) for r in rows)
            total_served = sum(max(0.0, to_float(r.get("served_qty")) or 0.0) for r in rows)
            ending_backlog = 0.0
            by_item = sorted(
                {
                    str(r.get("item_id") or "")
                    for r in rows
                    if str(r.get("item_id") or "") and not is_simulation_hidden_item(str(r.get("item_id") or ""))
                }
            )
            if rows:
                latest_day = max(int(to_float(r.get("day")) or 0) for r in rows)
                ending_backlog = sum(
                    max(0.0, to_float(r.get("backlog_end_qty")) or 0.0)
                    for r in rows
                    if int(to_float(r.get("day")) or 0) == latest_day
                )
            state_var_lines.extend(
                [
                    "Demande_pf(t): demande exogene du jour par produit",
                    "besoin brut client BB_pf(t): required_with_backlog_qty = demande + backlog precedent",
                    "Servi_pf(t): served_qty = min(stock_disponible, besoin_brut_client)",
                    "Backlog_pf(t): backlog_end_qty = besoin_brut_client - Servi_pf(t)",
                ]
            )
            assumption_lines.extend(
                [
                    "la demande est fournie en entree et lue jour par jour",
                    "le client ne produit rien ; il consomme le stock aval disponible",
                    "la cible de couverture est portee par le systeme aval via demand_stock_target_days",
                ]
            )
            summary_lines.extend(
                [
                    metric_section("Application client - lecture metier"),
                    metric_label_value("1. Demande", "Le client porte une demande exogene lue dans le scenario, par jour et par produit."),
                    metric_label_value("2. Service", "Le stock aval disponible sert cette demande dans la limite des quantites disponibles."),
                    metric_label_value("3. Backlog", "La part non servie devient un retard client reporte au jour suivant."),
                    metric_label_value("4. Signal aval", "La demande et le backlog alimentent ensuite le besoin propage vers les DC, usines et composants."),
                    metric_section("Application client - variables locales"),
                    *[metric_label_value(f"Var {idx+1}", line) for idx, line in enumerate(state_var_lines)],
                    metric_section("Application client - regles locales"),
                    metric_label_value("Eq sim 1", "besoin brut client BB_pf(t): demande_jour + backlog_precedent"),
                    metric_label_value("Eq sim 2", "Servi_pf(t): quantite servie au client = min(stock_disponible_pf, besoin_brut_client)"),
                    metric_label_value("Eq sim 3", "Backlog_pf(t): retard client fin de journee = besoin_brut_client - Servi_pf(t)"),
                    metric_section("Application client - correspondance modele global"),
                    metric_label_value("D[c,i](t)", "Demande_pf(t): demande client exogene du jour."),
                    metric_label_value("Served[c,i](t)", "Servi_pf(t): quantite livree depuis le stock disponible."),
                    metric_label_value("B[c,i](t+1)", "Backlog_pf(t): besoin non servi reporte au jour suivant."),
                    metric_section("Lecture simulateur"),
                    metric_label_value("Demande", "D_pf(t) est une entree exogene du scenario."),
                    metric_label_value("Backlog", "Le backlog n'est pas une entree: il est recalcule chaque jour si le stock aval ne couvre pas le besoin client."),
                    metric_label_value("Signal aval", "La demande servie/non servie alimente ensuite la propagation de besoin vers les usines et composants."),
                    metric_section("Donnees et interactions"),
                    metric_label_value("Produits demandes", ", ".join(item_labels.get(i, compact_item_label(i)) for i in by_item) or "n/a"),
                    metric_label_value("Horizon demande", f"{len({int(to_float(r.get('day')) or 0) for r in rows})} jours" if rows else "n/a"),
                    metric_label_value("Cible couverture demandee", fmt_days(policy.get("demand_stock_target_days"), 1)),
                    metric_multiline_value("Interactions", interaction_lines, limit=6),
                    metric_section("Hypotheses"),
                    *[metric_label_value(f"H {idx+1}", line) for idx, line in enumerate(assumption_lines)],
                    metric_section("KPI run courant"),
                    metric_label_value("Demande cumulee", fmt_qty(total_demand)),
                    metric_label_value("Servi cumule", fmt_qty(total_served)),
                    metric_label_value("Backlog final", fmt_qty(ending_backlog)),
                ]
            )
        elif node_type == "distribution_center":
            state_pairs = [
                (node_id, str(state.get("item_id") or ""))
                for state in inv_states
                if str(state.get("item_id") or "") and not is_simulation_hidden_item(str(state.get("item_id") or ""))
            ]
            final_stock_total = sum(max(0.0, latest_dc_stock.get(pair, 0.0)) for pair in state_pairs)
            latest_dc_lines = []
            safety_items = []
            for state in inv_states:
                item_id = str(state.get("item_id") or "")
                if is_simulation_hidden_item(item_id):
                    continue
                mrp_policy = state.get("mrp_policy") or {}
                safety_days = max(0.0, to_float(mrp_policy.get("safety_time_days")) or 0.0)
                if item_id and safety_days > 0:
                    safety_items.append(f"{item_labels.get(item_id, compact_item_label(item_id))}={safety_days:.0f}j")
                latest_row = latest_dc_rows.get((node_id, item_id))
                if latest_row is not None:
                    latest_dc_lines.append(
                        f"{item_labels.get(item_id, compact_item_label(item_id))}: stock_fin={fmt_qty(latest_row.get('stock_end_of_day'))}"
                    )
            state_var_lines.extend(
                [
                    "StockProj_dc(t): stock fin de journee au DC",
                    "RecvPrev_dc(t): receptions futures implicites via in_transit",
                    "T_dc(t): cible MRP du DC pour l'item suivi",
                    "Gap_dc(t): ecart a couvrir = T_dc(t) + Backlog_dc(t) - StockProj_dc(t) - RecvPrev_dc(t)",
                    "BN_dc(t): besoin net du DC = Gap_dc(t) si l'ecart est positif ; sinon 0",
                ]
            )
            assumption_lines.extend(
                [
                    "le DC est pilote par cible stock / couverture et non par plan de production",
                    "les safety times MRP des PF sont portes sur les etats de stock du DC",
                ]
            )
            summary_lines.extend(
                [
                    metric_section("Application DC - lecture metier"),
                    metric_label_value("1. Stock disponible", "Le DC observe son stock par item apres receptions et sorties aval."),
                    metric_label_value("2. Cible MRP", "La cible est calculee avec stock securite, delai securite, couverture appro ou cible active."),
                    metric_label_value("3. Receptions futures", "Les quantites deja en transit vers le DC sont deduites avant de commander."),
                    metric_label_value("4. Besoin net", "Si la cible reste non couverte, le DC cree un besoin net vers ses sources amont."),
                    metric_section("Application DC - variables locales"),
                    *[metric_label_value(f"Var {idx+1}", line) for idx, line in enumerate(state_var_lines)],
                    metric_section("Application DC - regles locales"),
                    metric_label_value("Eq sim 1", "StockProj_dc(t+1) = StockProj_dc(t) + Recv_dc(t) - Ship_dc(t) - Served_dc(t)"),
                    metric_label_value("Eq sim 2", "T_dc(t): cible DC = plus haute valeur entre stock_securite explicite, delai_securite * signal MRP, couverture * signal MRP et cible stock active si definie"),
                    metric_label_value("Eq sim 3", "Gap_dc(t) = T_dc(t) + Backlog_dc(t) - StockProj_dc(t) - RecvPrev_dc(t)"),
                    metric_label_value("Eq sim 4", "BN_dc(t) = Gap_dc(t) si Gap_dc(t) > 0 ; sinon 0"),
                    metric_section("Application DC - correspondance modele global"),
                    metric_label_value("S[n,i](t)", "StockProj_dc(t): stock disponible/projete au DC pour l'item."),
                    metric_label_value("T[n,i](t)", "T_dc(t): cible MRP du DC."),
                    metric_label_value("IP[n,i](t)", "StockProj_dc(t) + RecvPrev_dc(t): position inventaire du DC."),
                    metric_label_value("BN[n,i](t)", "BN_dc(t): besoin net commandable vers l'amont."),
                    metric_section("Lecture simulateur"),
                    metric_label_value("Stock projete", "StockProj_dc(t) est le stock DC simule apres receptions, expeditions et service aval."),
                    metric_label_value("Receptions prevues", "RecvPrev_dc(t) est porte par les quantites deja en transit vers le DC."),
                    metric_label_value("Besoin net", "On calcule d'abord l'ecart a couvrir. Si cet ecart est negatif, le stock et les receptions futures couvrent deja la cible: il n'y a donc pas de nouvelle commande."),
                    metric_section("Donnees et interactions"),
                    metric_label_value("Items entrants", str(len([i for i in incoming_items.get(node_id, set()) if not is_simulation_hidden_item(i)]))),
                    metric_label_value("Items sortants", str(len([i for i in outgoing_items.get(node_id, set()) if not is_simulation_hidden_item(i)]))),
                    metric_label_value("Review period", f"{review_period} j" if review_period is not None else "n/a"),
                    metric_label_value("Safety times MRP", ", ".join(safety_items[:6]) or "n/a"),
                    metric_multiline_value("Stocks suivis", latest_dc_lines, limit=8),
                    metric_multiline_value("Interactions", interaction_lines, limit=6),
                    metric_multiline_value("Etats stock initiaux", inventory_lines, limit=8),
                    metric_section("Hypotheses"),
                    *[metric_label_value(f"H {idx+1}", line) for idx, line in enumerate(assumption_lines)],
                    metric_section("KPI run courant"),
                    metric_label_value("Stock final total", fmt_qty(final_stock_total)),
                    metric_label_value("Sources amont", str(len(incoming_sources.get(node_id, set())))),
                    metric_label_value("Destinations aval", str(len(outgoing_targets.get(node_id, set())))),
                ]
            )
        elif node_type == "supplier_dc" and node_id not in factory_like_ids:
            ship_rows = supplier_ship_by_node.get(node_id, [])
            cap_rows = supplier_cap_by_node.get(node_id, [])
            node_orders_preview = mrp_orders_by_node.get(node_id, [])
            final_stock_total = sum(
                max(0.0, latest_supplier_stock.get((node_id, str(state.get("item_id") or "")), 0.0))
                for state in inv_states
            )
            total_shipped = sum(max(0.0, to_float(r.get("shipped_qty")) or 0.0) for r in ship_rows)
            avg_util = (
                sum(max(0.0, to_float(r.get("utilization")) or 0.0) for r in cap_rows) / len(cap_rows)
                if cap_rows else 0.0
            )
            sim_constraints = node.get("simulation_constraints") or {}
            cap_map = sim_constraints.get("supplier_item_capacity_qty_per_day") or {}
            basis_map = sim_constraints.get("supplier_item_capacity_basis") or {}
            cap_preview = []
            for item_id, cap_qty in list(sorted(cap_map.items()))[:5]:
                if is_simulation_hidden_item(str(item_id)):
                    continue
                basis = str(basis_map.get(item_id) or "")
                cap_preview.append(f"{item_labels.get(item_id, compact_item_label(item_id))}={to_float(cap_qty) or 0.0:.2f}/j ({basis or 'n/a'})")
            latest_supplier_lines = []
            for state in inv_states:
                item_id = str(state.get("item_id") or "")
                if is_simulation_hidden_item(item_id):
                    continue
                latest_row = latest_supplier_rows.get((node_id, item_id))
                if item_id and latest_row is not None:
                    latest_supplier_lines.append(
                        f"{item_labels.get(item_id, compact_item_label(item_id))}: stock_fin={fmt_qty(latest_row.get('stock_end_of_day'))}"
                    )
            nominal_lines = []
            seen_nominal_keys: set[tuple[str, str, str]] = set()
            for row in supplier_nominal_by_node.get(node_id, []):
                item_id = str(row.get("item_id") or "")
                dst_node_id = str(row.get("dst_node_id") or "")
                edge_id = str(row.get("edge_id") or "")
                key = (item_id, dst_node_id, edge_id)
                if key in seen_nominal_keys or is_simulation_hidden_item(item_id):
                    continue
                seen_nominal_keys.add(key)
                nominal_lines.append(
                    (
                        f"{item_labels.get(item_id, compact_item_label(item_id))}"
                        f" -> {dst_node_id or 'n/a'}: "
                        f"stock_ouv={fmt_qty(row.get('simulated_opening_stock_qty'), 0)}, "
                        f"cap={fmt_qty(row.get('effective_capacity_qty_per_day'), 0)}/j, "
                        f"delai={format_policy_value(row.get('planned_lead_time_days'), 1)}j, "
                        f"OTIF={fmt_pct((to_float(row.get('nominal_reliability_otif')) or 0.0) * 100.0)}, "
                        f"base={row.get('capacity_basis') or 'n/a'}"
                    )
                )
                if len(nominal_lines) >= 8:
                    break
            has_estimated_replenishment = any(
                str(row.get("category") or "") == "unmodeled_supplier_source_policy"
                and str(row.get("source") or "") == "estimated_replenishment"
                for row in assumptions_by_node.get(node_id, [])
            )
            is_dormant_supplier = not ship_rows and not cap_rows and not node_orders_preview
            supplier_diagnostic_lines = []
            if is_dormant_supplier:
                supplier_diagnostic_lines.append("Dormant: aucun flux observe sur l'horizon.")
            if has_estimated_replenishment:
                supplier_diagnostic_lines.append("Stock synthetique / estimated replenishment actif sur ce noeud.")
            if not supplier_diagnostic_lines:
                supplier_diagnostic_lines.append("Source active sur le run courant.")
            supplier_equation_mapping_lines = [
                "Stock_source(t) = S[src(f),i](t): stock disponible chez le fournisseur source.",
                "Stock_dest(t) = S[dst(f),i](t): stock disponible chez le noeud receveur.",
                "Req_dest(t) = Req[dst(f),i](t): signal MRP qui dimensionne la cible destination.",
                "T_dest(t) = T[dst(f),i](t): cible MRP destination.",
                "RecvPrev_dest(t) = RecvPrev[dst(f),i](t): receptions futures deja planifiees vers la destination.",
                "Gap_mp(t) = Gap[dst(f),i](t): ecart a couvrir chez la destination.",
                "BN_mp(t) = BN[dst(f),i](t): besoin net commandable si l'ecart est positif.",
                "OA_mp(t) = Q[f,i](t): quantite commandee sur le flux apres regles de lot/sourcing.",
                "Ship_mp(t) = Ship[f,i](t): quantite sortie du stock source et expediee vers la destination.",
                "RecvPrev_mp(t) = reception planifiee issue de Ship_mp(t) a t + lead_time.",
            ]
            state_var_lines.extend(
                [
                    "Stock_source(t): stock source expediable",
                    "Req_dest(t): signal MRP journalier de la destination pour cette matiere",
                    "T_dest(t): cible MRP de la destination pour cette matiere",
                    "Stock_dest(t): stock matiere projete chez la destination, donc chez l'usine ou le DC receveur",
                    "RecvPrev_dest(t): receptions futures deja planifiees vers cette destination",
                "Gap_mp(t): ecart matiere a couvrir = T_dest(t) + Backlog_dest(t) - Stock_dest(t) - RecvPrev_dest(t)",
                    "BN_mp(t): besoin net matiere = Gap_mp(t) si l'ecart est positif ; sinon 0",
                    "OA_mp(t): quantite demandee a la source apres normalisation lot standard",
                    "Ship_mp(t): quantite sortie du stock source et expediee vers la destination",
                    "RecvPrev_mp(t): quantite planifiee en reception destination a t + lead_time",
                ]
            )
            assumption_lines.extend(
                [
                    "le fournisseur est simule comme source de stock + capacite ; pas comme atelier detaille",
                    "standard_order_qty agit comme multiple cible de commande sur le flux d'approvisionnement",
                    "la commande est simulee dans le sens du temps ; il n'y a pas encore de retroplanning explicite de la date d'ordre",
                ]
            )
            summary_lines.extend(
                [
                    metric_section("Application fournisseur - lecture metier"),
                    metric_label_value("1. Besoin destination", "Le noeud receveur du flux, par exemple une usine ou un DC, calcule son besoin MRP pour l'item."),
                    metric_label_value("2. Stock deja couvert", "Son stock disponible et ses receptions futures deja planifiees sont deduits avant toute nouvelle commande."),
                    metric_label_value("3. Ecart a couvrir", "Si la cible MRP reste superieure a la position inventaire, l'ecart devient un besoin net commandable."),
                    metric_label_value("4. Ordre fournisseur", "Le besoin net est affecte au flux source -> destination puis normalise par lot, quantite standard ou regle de sourcing."),
                    metric_label_value("5. Expedition source", "Le fournisseur source reduit son stock de la quantite expediee, sous reserve de stock et capacite."),
                    metric_label_value("6. Reception destination", "La quantite expediee devient une reception future, puis augmente le stock destination apres le delai simule."),
                    metric_section("Application fournisseur - variables locales"),
                    *[metric_label_value(f"Var {idx+1}", line) for idx, line in enumerate(state_var_lines)],
                    metric_section("Application fournisseur - regles locales"),
                    metric_label_value("Eq sim 1", "T_dest(t): plus haute valeur entre stock securite, delai securite * Req_dest(t), couverture appro * Req_dest(t) et cible stock active"),
                    metric_label_value("Eq sim 2", "Gap_mp(t) = T_dest(t) + Backlog_dest(t) - Stock_dest(t) - RecvPrev_dest(t)"),
                    metric_label_value("Eq sim 3", "BN_mp(t) = Gap_mp(t) si Gap_mp(t) > 0 ; sinon 0"),
                    metric_label_value("Eq sim 4", "OA_mp(t): ordre amont source = quantite commandee, normalisee par quantite standard si applicable"),
                    metric_label_value("Eq sim 5", "Ship_mp(t) = min(Stock_source(t), Capacite_source(t), OA_mp(t)): quantite vraiment expediee"),
                    metric_label_value("Eq sim 6", "RecvPrev_mp(t + lead_time) = Ship_mp(t): reception future creee par l'expedition"),
                    metric_section("Application fournisseur - correspondance modele global"),
                    metric_multiline_value(
                        "Mapping",
                        supplier_equation_mapping_lines,
                        limit=10,
                    ),
                    metric_section("Lecture metier fournisseur"),
                    metric_label_value("Besoin matiere", "On lit d'abord l'ecart a couvrir. Si l'ecart est negatif ou nul, BN_mp(t)=0 et aucun ordre supplementaire n'est cree."),
                    metric_label_value("Destination", "La destination est le noeud receveur du flux d'approvisionnement: son stock et ses receptions futures sont deduits avant de commander au fournisseur."),
                    metric_label_value("Ordre fournisseur", "OA_mp(t) est la quantite commandee apres normalisation par quantite standard, lot ou capacite source."),
                    metric_label_value("Expedition fournisseur", "Ship_mp(t) est une sortie du stock source envoyee vers la destination ; ce n'est pas une consommation BOM."),
                    metric_label_value("Reception", "La reception planifiee est datee a arrival_day source pour les ordres d'ouverture, sinon envoi + delai previsionnel source; le delai matiere previsionnel affiche reste la valeur source."),
                    metric_section("Donnees et interactions"),
                    metric_label_value(
                        "Items sortants",
                        ", ".join(
                            item_labels.get(i, compact_item_label(i))
                            for i in sorted(outgoing_items.get(node_id, set()))
                            if not is_simulation_hidden_item(i)
                        ) or "n/a"
                    ),
                    metric_label_value("Clients aval", ", ".join(sorted(outgoing_targets.get(node_id, set()))[:6]) or "n/a"),
                    metric_label_value("Review period", f"{review_period} j" if review_period is not None else "n/a"),
                    metric_label_value("Capacites nominales", " | ".join(cap_preview) or "n/a"),
                    metric_multiline_value("Parametres nominaux", nominal_lines, limit=8),
                    metric_multiline_value("Diagnostic source", supplier_diagnostic_lines, limit=4),
                    metric_multiline_value("Stocks suivis", latest_supplier_lines, limit=8),
                    metric_multiline_value("Etats stock initiaux", inventory_lines, limit=8),
                    metric_multiline_value("Interactions", interaction_lines, limit=6),
                    metric_section("Hypotheses"),
                    *[metric_label_value(f"H {idx+1}", line) for idx, line in enumerate(assumption_lines)],
                    metric_section("KPI run courant"),
                    metric_label_value("Expedie cumule", fmt_qty(total_shipped)),
                    metric_label_value("Stock final total", fmt_qty(final_stock_total)),
                    metric_label_value("Utilisation moyenne", fmt_pct(avg_util * 100.0)),
                    metric_label_value(
                        "Items actifs expedies",
                        str(
                            len(
                                {
                                    str(r.get('item_id') or '')
                                    for r in ship_rows
                                    if max(0.0, to_float(r.get('shipped_qty')) or 0.0) > 0
                                    and not is_simulation_hidden_item(str(r.get('item_id') or ''))
                                }
                            )
                        ),
                    ),
                ]
            )
        else:
            output_labels = []
            input_count = 0
            for proc in processes:
                outputs = proc.get("outputs") or []
                if outputs:
                    output_labels.extend(
                        item_labels.get(str(out.get("item_id") or ""), compact_item_label(str(out.get("item_id") or "")))
                        for out in outputs
                        if not is_simulation_hidden_item(str(out.get("item_id") or ""))
                    )
                input_count += len(
                    [
                        inp
                        for inp in (proc.get("inputs") or [])
                        if not is_simulation_hidden_item(str(inp.get("item_id") or ""))
                    ]
                )
            final_input_total = sum(
                max(0.0, latest_input_stock.get((node_id, str(state.get("item_id") or "")), 0.0))
                for state in inv_states
                if not is_simulation_hidden_item(str(state.get("item_id") or ""))
            )
            final_output_total = sum(
                max(0.0, latest_output_stock.get((node_id, str((proc.get("outputs") or [{}])[0].get("item_id") or "")), 0.0))
                for proc in processes
                if (proc.get("outputs") or []) and not is_simulation_hidden_item(str((proc.get("outputs") or [{}])[0].get("item_id") or ""))
            )
            factory_rows = constraint_by_node.get(node_id, [])
            desired_total = sum(max(0.0, to_float(r.get("desired_qty")) or 0.0) for r in factory_rows)
            actual_total = sum(max(0.0, to_float(r.get("actual_qty")) or 0.0) for r in factory_rows)
            shortfall_total = sum(max(0.0, to_float(r.get("shortfall_vs_desired_qty")) or 0.0) for r in factory_rows)
            capacity_days = sum(1 for r in factory_rows if str(r.get("binding_cause") or "") == "capacity")
            input_shortage_days = sum(1 for r in factory_rows if str(r.get("binding_cause") or "") == "input_shortage")
            input_shortage_lot_shortfall_total = sum(
                max(0.0, to_float(r.get("shortfall_vs_lot_plan_qty")) or 0.0)
                for r in factory_rows
                if str(r.get("binding_cause") or "") == "input_shortage"
            )
            input_shortage_desired_shortfall_total = sum(
                max(0.0, to_float(r.get("shortfall_vs_desired_qty")) or 0.0)
                for r in factory_rows
                if str(r.get("binding_cause") or "") == "input_shortage"
            )
            input_shortage_items = sorted(
                {
                    item_labels.get(str(r.get("binding_input_item_id") or ""), compact_item_label(str(r.get("binding_input_item_id") or "")))
                    for r in factory_rows
                    if str(r.get("binding_cause") or "") == "input_shortage"
                    and str(r.get("binding_input_item_id") or "")
                    and not is_simulation_hidden_item(str(r.get("binding_input_item_id") or ""))
                }
            )
            cap_values = []
            for proc in processes:
                cap = (proc.get("capacity") or {}).get("max_rate")
                if cap is not None:
                    cap_values.append(str(cap))
            latest_output_lines = []
            latest_input_arrival_lines = []
            latest_constraint_rows: dict[str, dict[str, str]] = {}
            for row in factory_rows:
                item_id = str(row.get("output_item_id") or "")
                if not item_id:
                    continue
                if is_simulation_hidden_item(item_id):
                    continue
                latest_constraint_rows[item_id] = row
            latest_arrival_rows: dict[str, dict[str, str]] = {}
            for row in input_arrivals_by_node.get(node_id, []):
                item_id = str(row.get("item_id") or "")
                if not item_id:
                    continue
                if is_simulation_hidden_item(item_id):
                    continue
                latest_arrival_rows[item_id] = row
            for item_id in sorted(latest_arrival_rows):
                row = latest_arrival_rows[item_id]
                latest_input_arrival_lines.append(
                    f"{item_labels.get(item_id, compact_item_label(item_id))}: arrivage_jour={fmt_qty(row.get('arrived_qty'))} ; jour={int(to_float(row.get('day')) or 0)}"
                )
            for item_id in sorted(latest_constraint_rows):
                row = latest_constraint_rows[item_id]
                latest_out = latest_output_rows.get((node_id, item_id))
                latest_output_lines.append(
                    f"{item_labels.get(item_id, compact_item_label(item_id))}: desire={fmt_qty(row.get('desired_qty'))} ; plan_lot={fmt_qty(row.get('planned_qty_after_lot_rule'))} ; reel={fmt_qty(row.get('actual_qty'))} ; stock_fin={fmt_qty((latest_out or {}).get('stock_end_of_day'))}"
                )
            special_flow_lines: list[str] = []
            component_reference_lines: list[str] = []
            output_item_ids = {
                str(out.get("item_id") or "")
                for proc in processes
                for out in (proc.get("outputs") or [])
                if str(out.get("item_id") or "")
            }
            input_item_ids = {
                str(inp.get("item_id") or "")
                for proc in processes
                for inp in (proc.get("inputs") or [])
                if str(inp.get("item_id") or "")
            }
            if "item:268091" in output_item_ids and "item:007923" in input_item_ids:
                component_reference_lines.append(
                    "268091: composant actif BOM = 007923 ; ancienne ref encore visible dans Data_poc.xlsx = 693710."
                )
                component_reference_lines.append(
                    "007923: reference active retenue dans la simulation ; pas de flux FIA actif fourni dans les donnees source."
                )
            if is_upstream_internal_site(node_id):
                actual_output_qty_by_item: dict[str, float] = defaultdict(float)
                for row in factory_rows:
                    item_id = str(row.get("output_item_id") or "")
                    if item_id and not is_simulation_hidden_item(item_id):
                        actual_output_qty_by_item[item_id] += max(0.0, to_float(row.get("actual_qty")) or 0.0)
                external_procurement_qty_by_item: dict[str, float] = defaultdict(float)
                for row in mrp_orders_by_node.get(node_id, []):
                    if str(row.get("order_type") or "") != "external_procurement":
                        continue
                    item_id = str(row.get("item_id") or "")
                    if item_id and not is_simulation_hidden_item(item_id):
                        external_procurement_qty_by_item[item_id] += max(0.0, to_float(row.get("planned_receipt_qty")) or 0.0)
                upstream_output_labels = [
                    item_labels.get(item_id, compact_item_label(item_id))
                    for item_id in sorted(outgoing_items.get(node_id, set()))
                    if not is_simulation_hidden_item(item_id)
                ]
                if upstream_output_labels:
                    special_flow_lines.append(
                        f"Sorties PFI modelisees: {', '.join(upstream_output_labels)}."
                    )
                if aggregate_daily_series(
                    input_arrivals_by_node.get(node_id, []),
                    value_field="arrived_qty",
                    node_field="node_id",
                    node_id=node_id,
                    item_ids={"item:021081"},
                ):
                    special_flow_lines.append(
                        "021081: arrivages intrants observes dans production_input_replenishment_arrivals_daily.csv."
                    )
                if actual_output_qty_by_item.get("item:773474", 0.0) > 0:
                    special_flow_lines.append(
                        f"773474: PFI produit en interne, cumul reel={fmt_qty(actual_output_qty_by_item.get('item:773474', 0.0))}."
                    )
                if external_procurement_qty_by_item.get("item:693055", 0.0) > 0 and actual_output_qty_by_item.get("item:693055", 0.0) <= 0:
                    special_flow_lines.append(
                        f"693055: PFI aval confirme, mais pas de production interne explicite observee ; flux amont simule non detaille={fmt_qty(external_procurement_qty_by_item.get('item:693055', 0.0))}."
                    )
            state_var_lines.extend(
                [
                    "besoin brut produit fini BB_pf(t): signal aval dynamique du produit fini",
                    "T_pf(t): cible stock produit fini/intermediaire active dans la boucle",
                    "SP_pf(t): stock PF courant observe dans la boucle",
                    "Gap_pf(t): ecart stock cible = T_pf(t) - SP_pf(t)",
                    "besoin net produit fini BN_pf(t): commande dynamique avant regles de lot",
                    "LP_pf(t): plan lance apres lot fixe/min/max/multiple",
                    "Prod_pf(t): production reelle bornee par capacite et intrants",
                    "StockProj_site(t): stock site fin de journee",
                ]
            )
            assumption_lines.extend(
                [
                    "la production est pilotee chronologiquement jour par jour et non par retroplanification explicite",
                    "les campagnes et regles de lot industrialisent le besoin net produit fini avant execution",
                    "les causes de binding observees viennent des contraintes reelles du run",
                ]
            )
            outgoing_flow_label = "Sorties PFI" if is_upstream_internal_site(node_id) else "Sorties aval"
            summary_lines.extend(
                [
                    metric_section("Application usine - lecture metier"),
                    metric_label_value("1. Signal aval", "L'usine recoit un signal de besoin depuis la demande finale, les DC ou les process aval."),
                    metric_label_value("2. Cible sortie", "Elle compare son stock de produit fabrique a une cible de couverture ou cible metier."),
                    metric_label_value("3. Commande de production", "Le signal aval et l'ecart de stock produisent une commande de production simulee, lissee dans le temps."),
                    metric_label_value("4. Lotification", "La commande est transformee en campagne selon les lots fixes/min/max/multiples et le maximum de lots par semaine."),
                    metric_label_value("5. Execution", "La production reelle est bornee par la capacite et les intrants disponibles."),
                    metric_label_value("6. Propagation BOM", "Le plan lotifie cree un besoin MRP amont ; la production reelle consomme physiquement les intrants."),
                    metric_section("Application usine - variables locales"),
                    *[metric_label_value(f"Var {idx+1}", line) for idx, line in enumerate(state_var_lines)],
                    metric_section("Application usine - regles locales"),
                    metric_label_value("Eq sim 1", "besoin brut produit fini BB_pf(t): signal aval dynamique = max(demande propagee, besoin process aval)"),
                    metric_label_value("Eq sim 2", "T_pf(t): cible PF = plus haute valeur entre cible stock active et fg_target_days * signal aval"),
                    metric_label_value("Eq sim 3", "SP_pf(t): stock projete PF observe dans la boucle = stock PF courant"),
                    metric_label_value("Eq sim 4", "Gap_pf(t) = T_pf(t) - SP_pf(t)"),
                    metric_label_value("Eq sim 5", "BN_pf(t): commande dynamique = besoin_brut_produit_fini + gain * Gap_pf(t), bornee a 0 si le calcul devient negatif"),
                    metric_label_value("Eq sim 6", "LP_pf(t): plan lance = normalisation_lot(BN_pf(t)) avec lot fixe/min/max/multiple + max lots / semaine"),
                    metric_label_value("Eq sim 7", "Prod_pf(t): production reelle = min(capacite, limite_intrants, LP_pf(t))"),
                    metric_label_value("Eq sim 8", "StockProj_site(t+1) = StockProj_site(t) + Recv_site(t) + Prod_site(t) - Cons_site(t) - Ship_site(t)"),
                    metric_section("Application usine - correspondance modele global"),
                    metric_label_value("ReqProd[p,s](t)", "besoin brut produit fini BB_pf(t): signal aval retenu pour la production."),
                    metric_label_value("TProd[p,s](t)", "T_pf(t): cible du produit fabrique par l'usine."),
                    metric_label_value("MPS[p,s](t)", "BN_pf(t): commande de production simulee avant lotification."),
                    metric_label_value("PlanLot[p,s](t)", "LP_pf(t): plan lance apres regles de lot et campagne."),
                    metric_label_value("Prod[p,s](t)", "Prod_pf(t): production reelle executee."),
                    metric_label_value("Cons[s,i](t)", "Consommations BOM: intrants physiquement decrementes par la production reelle."),
                    metric_label_value("Recv[s,i](t)", "Arrivages intrants observes: quantites devenues disponibles sur le site."),
                    metric_label_value("Ship[s,i](t)", "Sorties aval: quantites expediees ou servies depuis le site."),
                    metric_section("Lecture simulateur"),
                    metric_label_value("Signal production", "Le besoin usine vient du signal aval: demande finale, consommation aval observee ou MPS lotifie propage."),
                    metric_label_value("Plan lotifie", "LP_pf(t) est le besoin usine transforme par les regles de lot: fixe, min/max, multiple et limite lots/semaine."),
                    metric_label_value("Execution", "Prod_pf(t) est le plan lotifie borne par la capacite modelisee et les intrants disponibles."),
                    metric_label_value("Req_BOM vs Cons", "Req_BOM sert a commander l'amont a partir du plan lotifie ; Cons decremente reellement les stocks intrants selon la production executee."),
                    metric_section("Donnees et interactions"),
                    metric_label_value("Sorties process", ", ".join(sorted(set(output_labels))) or "n/a"),
                    metric_label_value(
                        outgoing_flow_label,
                        ", ".join(
                            item_labels.get(item_id, compact_item_label(item_id))
                            for item_id in sorted(outgoing_items.get(node_id, set()))
                            if not is_simulation_hidden_item(item_id)
                        ) or "n/a",
                    ),
                    metric_label_value("Nb intrants modelises", str(input_count)),
                    metric_label_value("Capacite max_rate", " | ".join(cap_values) or "n/a"),
                    metric_multiline_value("Process modelises", process_labels, limit=6),
                    metric_multiline_value("Consommations BOM", io_rules, limit=10),
                    metric_multiline_value("Refs composants", component_reference_lines, limit=4),
                    metric_multiline_value("Regles de lot", process_lot_rules, limit=6),
                    metric_label_value("Review period", f"{review_period} j" if review_period is not None else "n/a"),
                    metric_multiline_value("Etats stock initiaux", inventory_lines, limit=10),
                    metric_multiline_value("Arrivages intrants observes", latest_input_arrival_lines, limit=8),
                    metric_multiline_value("Sorties observees", latest_output_lines, limit=8),
                    metric_multiline_value("Diagnostic PFI", special_flow_lines, limit=6),
                    metric_multiline_value("Interactions", interaction_lines, limit=6),
                    metric_section("Hypotheses"),
                    *[metric_label_value(f"H {idx+1}", line) for idx, line in enumerate(assumption_lines)],
                    metric_section("KPI run courant"),
                    metric_label_value("Stock intrants final", fmt_qty(final_input_total)),
                    metric_label_value("Stock sorties final", fmt_qty(final_output_total)),
                    metric_label_value("Production demandee", fmt_qty(desired_total)),
                    metric_label_value("Production reelle", fmt_qty(actual_total)),
                    metric_label_value("Manque de production", fmt_qty(shortfall_total)),
                    metric_label_value("Jours contrainte matiere", str(input_shortage_days)),
                    metric_label_value("Manque matiere vs plan lotifie", fmt_qty(input_shortage_lot_shortfall_total)),
                    metric_label_value("Manque matiere vs besoin usine", fmt_qty(input_shortage_desired_shortfall_total)),
                    metric_multiline_value("Matieres bloquantes", input_shortage_items, limit=6),
                    metric_label_value("Jours capacite", str(capacity_days)),
                ]
            )

        node_item_candidates = {
            str(state.get("item_id") or "")
            for state in inv_states
            if str(state.get("item_id") or "") and not is_simulation_hidden_item(str(state.get("item_id") or ""))
        }
        for proc in processes:
            for inp in (proc.get("inputs") or []):
                item_id = str(inp.get("item_id") or "")
                if item_id and not is_simulation_hidden_item(item_id):
                    node_item_candidates.add(item_id)
            for out in (proc.get("outputs") or []):
                item_id = str(out.get("item_id") or "")
                if item_id and not is_simulation_hidden_item(item_id):
                    node_item_candidates.add(item_id)
        node_item_candidates |= {
            item_id
            for item_id in set(incoming_items.get(node_id, set())) | set(outgoing_items.get(node_id, set()))
            if not is_simulation_hidden_item(item_id)
        }

        mrp_trace_lines = []
        for item_id in sorted(node_item_candidates):
            latest_trace = latest_mrp_trace_by_pair.get((node_id, item_id))
            if latest_trace is None:
                continue
            mrp_trace_lines.append(
                f"{item_labels.get(item_id, compact_item_label(item_id))}: "
                f"besoin brut={fmt_qty(latest_trace.get('bb_qty'))} ; "
                f"signal brut={fmt_qty(latest_trace.get('bb_demand_signal_raw_qty'))} ; "
                f"signal MRP={fmt_qty(latest_trace.get('bb_demand_signal_qty'))} ; "
                f"base={latest_trace.get('gross_requirement_basis') or 'n/a'} ; "
                f"besoin net={fmt_qty(latest_trace.get('bn_qty'))} ; "
                f"StockProj={fmt_qty(latest_trace.get('stock_proj_qty'))} ; "
                f"RecvPrev={fmt_qty(latest_trace.get('recv_prev_future_qty'))} ; "
                f"OA={fmt_qty(latest_trace.get('planned_release_qty'))} ; "
                f"PR={fmt_qty(latest_trace.get('planned_receipt_qty'))}"
            )

        node_orders = mrp_orders_by_node.get(node_id, [])
        order_status_counts: dict[str, int] = defaultdict(int)
        for row in node_orders:
            status_key = " | ".join(
                [
                    f"plan={str(row.get('planning_status') or 'n/a')}",
                    f"release={str(row.get('release_status') or 'n/a')}",
                    f"receipt={str(row.get('receipt_status') or 'n/a')}",
                    f"run={str(row.get('order_status_end_of_run') or 'n/a')}",
                ]
            )
            order_status_counts[status_key] += 1
        order_lines = []
        for row in sorted(
            node_orders,
            key=lambda r: (
                int(to_float(r.get("day")) or 0),
                str(r.get("item_id") or ""),
                str(r.get("edge_id") or ""),
            ),
            reverse=True,
        ):
            if is_simulation_hidden_item(str(row.get("item_id") or "")):
                continue
            planned_arrival_day = fmt_order_day(planned_order_receipt_day(row))
            planned_lead = planned_procurement_lead_days(row)
            effective_lead = effective_procurement_lead_days(row)
            order_lines.append(
                f"{item_labels.get(str(row.get('item_id') or ''), compact_item_label(str(row.get('item_id') or '')))}: "
                f"{display_order_type(row.get('order_type'))} ; "
                f"release={row.get('release_day') or 'n/a'} ; "
                f"ordre_passe={fmt_order_day(row.get('order_date_imt'))} ; "
                f"arrival_previsionnelle={planned_arrival_day} ; "
                f"arrival_effective={fmt_order_day(row.get('actual_receipt_day'))} ; "
                f"delai_prev_matiere={fmt_days(planned_lead, 1)} ; "
                f"delai_effectif_matiere={fmt_days(effective_lead, 1)} ; "
                f"status={row.get('order_status_end_of_run') or 'n/a'}"
            )
            if len(order_lines) >= 8:
                break

        mrp_industrial_validation_lines: list[str] = []
        for item_id in sorted({str(row.get("item_id") or "") for row in node_orders if str(row.get("item_id") or "")}):
            item_rows = [row for row in node_orders if str(row.get("item_id") or "") == item_id]
            if not item_rows or is_simulation_hidden_item(item_id):
                continue
            release_by_order_day: dict[int, float] = defaultdict(float)
            total_qty = 0.0
            standard_qty = 0.0
            for row in item_rows:
                if str(row.get("order_type") or "") != "lane_release":
                    continue
                day = int(to_float(row.get("order_date_imt")) or 0)
                qty = max(0.0, to_float(row.get("release_qty")) or 0.0)
                release_by_order_day[day] += qty
                total_qty += qty
                standard_qty = max(standard_qty, max(0.0, to_float(row.get("standard_order_qty")) or 0.0))
            if not release_by_order_day:
                continue
            peak_day, peak_qty = max(release_by_order_day.items(), key=lambda it: it[1])
            label = item_labels.get(item_id, compact_item_label(item_id))
            if standard_qty >= 1_000_000.0:
                mrp_industrial_validation_lines.append(
                    f"{label}: lot FIA tres eleve a valider ({fmt_qty(standard_qty, 0)}), pic MRP={fmt_qty(peak_qty, 0)} a J{peak_day}."
                )
            elif 0.0 < standard_qty <= 1.0 and total_qty >= 100_000.0:
                mrp_industrial_validation_lines.append(
                    f"{label}: quantite standard=1 non interpretable comme lot industriel; renseigner le lot/campagne interne."
                )
            elif standard_qty > 1.0 and peak_qty > 10.0 * standard_qty:
                mrp_industrial_validation_lines.append(
                    f"{label}: concentration MRP a valider, pic={fmt_qty(peak_qty, 0)} a J{peak_day} soit {peak_qty / standard_qty:.1f} lots de {fmt_qty(standard_qty, 0)}."
                )

        assumption_lines_node = []
        for row in assumptions_by_node.get(node_id, [])[:8]:
            category = str(row.get("category") or "n/a")
            source = str(row.get("source") or "n/a")
            item_id = str(row.get("item_id") or "")
            if is_simulation_hidden_item(item_id):
                continue
            item_prefix = f"{item_labels.get(item_id, compact_item_label(item_id))}: " if item_id else ""
            assumption_lines_node.append(f"{item_prefix}{category} [{source}]")

        node_trace_rows = mrp_trace_by_node.get(node_id, [])
        node_trace_asset = None
        node_risk_asset = None
        node_flow_asset = None
        node_order_asset = None
        node_ledger_asset = None
        node_nominal_asset = None
        node_supplier_stock_flow_asset = None
        node_supplier_order_send_asset = None
        node_supplier_risk_catalog_asset = None
        node_uncertainty_asset = None
        node_supplier_risk_prediction_asset = None
        node_capacity_nominal_asset = None
        dormant_reason: str | None = None
        if not node_orders:
            if node_type == "supplier_dc":
                outgoing_edges = outgoing_edges_by_node.get(node_id, [])
                observed_shipment_rows = sum(
                    int(to_float(((edge.get("edge_metrics") or {}).get("shipment_rows"))) or 0)
                    for edge in outgoing_edges
                )
                scoped_items = sorted(
                    {
                        compact_item_label(str(item_id))
                        for edge in outgoing_edges
                        for item_id in (edge.get("items") or [])
                        if str(item_id or "") and not is_simulation_hidden_item(str(item_id))
                    }
                )
                scoped_dests = sorted(
                    {str(edge.get("to") or "") for edge in outgoing_edges if str(edge.get("to") or "")}
                )
                if outgoing_edges and observed_shipment_rows == 0 and not supplier_ship_by_node.get(node_id):
                    dormant_reason = (
                        "Diagnostic: source dormante dans ce baseline. "
                        "Aucune expedition observee sur les flux source et aucun tirage simule."
                    )
                    if any(
                        str(row.get("category") or "") == "unmodeled_supplier_source_policy"
                        and str(row.get("source") or "") == "estimated_replenishment"
                        for row in assumptions_by_node.get(node_id, [])
                    ):
                        dormant_reason += " Stock synthetique / estimated replenishment actif."
                    if scoped_dests or scoped_items:
                        dormant_reason += " "
                        dormant_reason += (
                            f"Aval={', '.join(scoped_dests) or 'n/a'} ; "
                            f"items={', '.join(scoped_items) or 'n/a'}."
                        )
                elif not outgoing_edges and not inv_states and not processes:
                    dormant_reason = "Diagnostic: noeud fournisseur orphelin, sans flux, sans stock et sans process dans le graphe actif."
            elif node_type == "distribution_center":
                if not outgoing_edges_by_node.get(node_id) and not incoming_edges_by_node.get(node_id) and not inv_states and not processes:
                    dormant_reason = "Diagnostic: noeud DC orphelin, sans flux, sans stock et sans process dans le graphe actif."
        trace_series = {
            "Besoin brut": aggregate_trace_series(node_trace_rows, "bb_qty"),
            "Besoin propage brut": aggregate_trace_series(node_trace_rows, "bb_demand_signal_raw_qty"),
            "Besoin MRP lisse": aggregate_trace_series(node_trace_rows, "bb_demand_signal_qty"),
            "Besoin net": aggregate_trace_series(node_trace_rows, "bn_qty"),
            "StockProj": aggregate_trace_series(node_trace_rows, "stock_proj_qty"),
            "RecvPrev": aggregate_trace_series(node_trace_rows, "recv_prev_future_qty"),
        }
        trace_figure = build_line_chart_figure(
            trace_series,
            title=f"{node_id} - trace MRP explicite",
            y_label="Quantite",
        )
        if trace_figure is not None:
            node_trace_asset = {"figure": trace_figure}
        safety_summary = mrp_safety_summary_by_node.get(node_id, {})
        node_stock_rows_for_risk = dc_stocks_by_node.get(node_id, []) if node_type == "distribution_center" else input_stocks_by_node.get(node_id, [])
        node_risk_asset = {
            "html": render_mrp_risk_summary_html(
                node_id,
                node_type,
                safety_summary=safety_summary,
                node_trace_rows=node_trace_rows,
                node_orders=node_orders,
                stock_rows=node_stock_rows_for_risk,
                supplier_stock_rows_node=supplier_stocks_by_node.get(node_id, []),
                supplier_capacity_rows_node=supplier_cap_by_node.get(node_id, []),
                supplier_risk_rows_node=supplier_risk_applied_by_node.get(node_id, []),
                dormant_reason=dormant_reason,
            )
        }
        if node_type == "supplier_dc":
            node_supplier_stock_flow_asset = {
                "html": render_supplier_stock_flows_html(
                    node_id,
                    supplier_stock_flows_by_node.get(node_id, []),
                    supplier_ship_by_node.get(node_id, []),
                    node_orders,
                    item_labels,
                )
            }
            node_nominal_asset = {
                "html": render_supplier_nominal_parameters_html(
                    node_id,
                    supplier_nominal_by_node.get(node_id, []),
                    item_labels,
                )
            }
            node_supplier_risk_catalog_asset = {
                "html": render_supplier_risk_catalog_html(
                    node_id,
                    applied_rows=supplier_risk_applied_by_node.get(node_id, []),
                    configured_events=supplier_risk_config_by_node.get(node_id, []),
                    economic_policy=(policy.get("economic_policy") or {}) if isinstance(policy, dict) else {},
                )
            }
            supplier_ship_rows_node = supplier_ship_by_node.get(node_id, [])
            supplier_source_orders = [
                row for row in node_orders
                if str(row.get("src_node_id") or "") == node_id
            ]
            node_uncertainty_asset = {
                "html": render_passive_uncertainty_html(
                    node_id,
                    scope_label="fournisseur",
                    order_rows=supplier_source_orders,
                    stock_rows=supplier_stocks_by_node.get(node_id, []),
                    capacity_rows=supplier_cap_by_node.get(node_id, []),
                    shipment_rows=supplier_ship_rows_node,
                    nominal_rows=supplier_nominal_by_node.get(node_id, []),
                    item_labels=item_labels,
                )
            }
            uncertainty_metric_nodes[node_id] = build_passive_uncertainty_metric(
                node_id,
                scope_label="fournisseur",
                order_rows=supplier_source_orders,
                stock_rows=supplier_stocks_by_node.get(node_id, []),
                capacity_rows=supplier_cap_by_node.get(node_id, []),
                shipment_rows=supplier_ship_rows_node,
                nominal_rows=supplier_nominal_by_node.get(node_id, []),
                item_labels=item_labels,
            )
            node_supplier_risk_prediction_asset = {
                "html": render_supplier_risk_prediction_html(
                    node_id,
                    order_rows=supplier_source_orders,
                    stock_rows=supplier_stocks_by_node.get(node_id, []),
                    capacity_rows=supplier_cap_by_node.get(node_id, []),
                    shipment_rows=supplier_ship_rows_node,
                    nominal_rows=supplier_nominal_by_node.get(node_id, []),
                    criticality_row=supplier_local_criticality_by_node.get(node_id),
                    economic_policy=(policy.get("economic_policy") or {}) if isinstance(policy, dict) else {},
                    item_labels=item_labels,
                )
            }
            supplier_order_received_series = aggregate_order_series(
                supplier_source_orders,
                "release_qty",
                day_field="order_date_imt",
                bucket_days=7,
            )
            supplier_order_send_plan_series = aggregate_order_series(
                supplier_source_orders,
                "release_qty",
                day_field="release_day",
                bucket_days=7,
            )
            supplier_planned_receipt_series = aggregate_order_series(
                supplier_source_orders,
                "planned_receipt_qty",
                day_field="planned_arrival_day",
                bucket_days=7,
            )
            supplier_order_actual_receipt_series = aggregate_effective_order_receipt_series(
                supplier_source_orders,
                "planned_receipt_qty",
                bucket_days=7,
            )
            supplier_actual_send_series = aggregate_daily_series(
                supplier_ship_rows_node,
                value_field="shipped_qty",
                day_field="day",
                node_field="src_node_id",
                node_id=node_id,
            )
            supplier_actual_receipt_series = aggregate_daily_series(
                supplier_ship_rows_node,
                value_field="shipped_qty",
                day_field="arrival_day",
                node_field="src_node_id",
                node_id=node_id,
            )

            supplier_order_send_top = build_line_chart_figure(
                {
                    "Commandes MRP recues": supplier_order_received_series,
                    "Expeditions prevues fournisseur": supplier_order_send_plan_series,
                },
                title=f"{node_id} - commandes MRP et expeditions prevues",
                y_label="Quantite / semaine",
                event_like=True,
                note=(
                    "Commande MRP recue = ordre date a order_date_imt. "
                    "Expedition prevue = release_day, donc date promise/planifiee pour le depart fournisseur. "
                    "Ces deux signaux sont du pilotage, pas une preuve de mouvement physique."
                ),
                series_styles={
                    "Commandes MRP recues": {"color": "#0f766e", "width": 2.2},
                    "Expeditions prevues fournisseur": {"color": "#2563eb", "width": 2.2, "dash": "dash"},
                },
            )
            actual_receipt_series = supplier_order_actual_receipt_series or bucket_series_points(supplier_actual_receipt_series, 7)
            supplier_order_send_bottom = build_line_chart_figure(
                {
                    "Expeditions physiques confirmees": bucket_series_points(supplier_actual_send_series, 7),
                    "Receptions prevues aval": supplier_planned_receipt_series,
                    "Receptions reelles confirmees": actual_receipt_series,
                },
                title=f"{node_id} - executions physiques et receptions aval",
                y_label="Quantite / semaine",
                event_like=True,
                note=(
                    "Expedition physique confirmee = production_supplier_shipments_daily.day. "
                    "Reception prevue aval = carnet MRP date a la date previsionnelle d'arrivee. "
                    "Reception reelle confirmee = actual_receipt_day du carnet quand disponible, sinon arrival_day des expeditions physiques."
                ),
                series_styles={
                    "Expeditions physiques confirmees": {"color": "#ea580c", "width": 2.3},
                    "Receptions prevues aval": {"color": "#7c3aed", "width": 2.1, "dash": "dot"},
                    "Receptions reelles confirmees": {"color": "#16a34a", "width": 2.4},
                },
            )
            if supplier_order_send_top is not None or supplier_order_send_bottom is not None:
                node_supplier_order_send_asset = {
                    "figure": {
                        "kind": "dual_panel_multi",
                        "title": f"{node_id} - pilotage et execution fournisseur",
                        "top": supplier_order_send_top,
                        "bottom": supplier_order_send_bottom,
                    }
                }
        if node_type in {"factory", "supplier_dc"} and factory_nominal_capacity_by_node.get(node_id):
            node_capacity_nominal_asset = {
                "html": render_factory_nominal_capacities_html(
                    node_id,
                    factory_nominal_capacity_by_node.get(node_id, []),
                    item_labels,
                )
            }
        actual_input_arrival_series = aggregate_daily_series(
            input_arrivals_by_node.get(node_id, []),
            value_field="arrived_qty",
            node_field="node_id",
            node_id=node_id,
        )
        if node_type == "factory":
            supplier_order_rows = [
                row
                for row in node_orders
                if str(row.get("dst_node_id") or "") == node_id
                and str(row.get("src_node_id") or "") in supplier_ids
            ]
            if not supplier_order_rows:
                supplier_order_rows = [
                    row
                    for row in node_orders
                    if str(row.get("dst_node_id") or "") == node_id
                    and str(row.get("src_node_id") or "")
                    and str(row.get("src_node_id") or "") != node_id
                ]
            flow_series = {
                "Ordres passes fournisseurs": aggregate_order_series(
                    supplier_order_rows,
                    "release_qty",
                    day_field="order_date_imt",
                    bucket_days=7,
                ),
                "Receptions entree usine": bucket_series_points(actual_input_arrival_series, 7),
            }
            flow_title = f"{node_id} - ordres fournisseurs et receptions entree usine"
            flow_note = (
                "Ordres passes fournisseurs = date order_date_imt du carnet MRP vers les fournisseurs. "
                "Receptions entree usine = arrivees physiques dans production_input_replenishment_arrivals_daily."
            )
            flow_styles = {
                "Ordres passes fournisseurs": {"color": "#0f766e", "width": 2.3},
                "Receptions entree usine": {"color": "#2563eb", "width": 2.3, "dash": "dash"},
            }
        else:
            order_release_series = aggregate_order_series(
                node_orders,
                "release_qty",
                day_field="order_date_imt",
                bucket_days=7,
            )
            order_receipt_series = aggregate_order_series(
                node_orders,
                "planned_receipt_qty",
                day_field="planned_arrival_day",
                bucket_days=7,
            )
            flow_series = {
                "Ordres MRP hebdo": order_release_series,
                "Receptions previsionnelles hebdo": order_receipt_series,
            }
            if actual_input_arrival_series:
                flow_series["Arrivages reels intrants"] = actual_input_arrival_series
            flow_title = f"{node_id} - flux MRP intrants"
            flow_note = (
                "Flux entrants comparables: ordres MRP, receptions previsionnelles et arrivages reels. "
                "Le besoin net MRP n'est pas affiche ici car c'est un ecart de stock a cible, pas un flux journalier. "
                "Les ordres sont affiches a leur date d'ordre calculee pour eviter de faire apparaitre le carnet initial comme un ordre massif au 1er janvier."
            )
            flow_styles = {
                "Ordres MRP hebdo": {"color": "#0f766e", "width": 2.2},
                "Receptions previsionnelles": {"color": "#2563eb", "width": 2.2},
                "Arrivages reels intrants": {"color": "#0891b2", "width": 2.0, "dash": "dot"},
            }
        flow_top_figure = build_line_chart_figure(
            flow_series,
            title=flow_title,
            y_label="Quantite / semaine" if node_type == "factory" else "Quantite / jour",
            event_like=True,
            note=flow_note,
            series_styles=flow_styles,
        )
        actual_input_stock_series = aggregate_daily_series(
            input_stocks_by_node.get(node_id, []),
            value_field="stock_end_of_day",
            node_field="node_id",
            node_id=node_id,
        )
        stock_target_series = {
            "Stock reel simule": actual_input_stock_series,
            "Stock projete MRP": aggregate_trace_series(node_trace_rows, "stock_proj_qty"),
            "Position inventaire MRP": aggregate_trace_series(node_trace_rows, "inventory_position_qty"),
            "Besoin net MRP": aggregate_trace_series(node_trace_rows, "bn_qty"),
            "Stock equiv. delai securite": aggregate_trace_series(node_trace_rows, "safety_floor_qty"),
            "Cible securite souple": aggregate_trace_series(node_trace_rows, "soft_safety_target_qty"),
            "Cible MRP affichee": (
                aggregate_trace_series(node_trace_rows, "target_stock_display_qty")
                or aggregate_trace_series(node_trace_rows, "target_stock_qty")
            ),
        }
        flow_bottom_figure = build_line_chart_figure(
            stock_target_series,
            title=f"{node_id} - stock reel / position MRP vs cibles",
            y_label="Stock / cible",
            note=(
                "Niveaux comparables: stock reel simule, stock projete MRP, position inventaire MRP et cibles exprimees en quantite de stock. "
                "Position inventaire MRP = stock projete + receptions futures deja prevues; le besoin net MRP vient de l'ecart entre cette position et la cible totale."
            ),
            series_styles={
                "Stock reel simule": {"color": "#0f172a", "width": 2.4},
                "Stock projete MRP": {"color": "#2563eb", "width": 2.0, "dash": "dot"},
                "Position inventaire MRP": {"color": "#0f766e", "width": 2.1},
                "Besoin net MRP": {"color": "#dc2626", "width": 1.8, "dash": "dash"},
                "Stock equiv. delai securite": {"color": "#7c3aed", "width": 1.8, "dash": "dot"},
                "Cible securite souple": {"color": "#f59e0b", "width": 1.9, "dash": "dash"},
                "Cible MRP affichee": {"color": "#64748b", "width": 1.4, "dash": "longdash"},
            },
        )
        if flow_top_figure is not None or flow_bottom_figure is not None:
            node_flow_asset = {
                "figure": {
                    "kind": "dual_panel_multi",
                    "title": f"{node_id} - pilotage MRP intrants",
                    "top": flow_top_figure,
                    "bottom": flow_bottom_figure,
                }
            }
        node_order_series: dict[str, list[tuple[int, float]]] = {}
        node_order_styles: dict[str, dict[str, Any]] = {}
        node_order_labels_by_item: dict[str, list[str]] = defaultdict(list)
        node_order_peak_by_item: dict[str, float] = defaultdict(float)
        item_palette = [
            "#0f766e",
            "#2563eb",
            "#dc2626",
            "#d97706",
            "#7c3aed",
            "#475569",
            "#0891b2",
            "#be123c",
            "#65a30d",
            "#b45309",
        ]
        node_order_item_ids = sorted({str(row.get("item_id") or "") for row in node_orders if str(row.get("item_id") or "")})
        for idx, item_id in enumerate(node_order_item_ids):
            item_rows = [row for row in node_orders if str(row.get("item_id") or "") == item_id]
            if not item_rows:
                continue
            item_label = item_labels.get(item_id, compact_item_label(item_id))
            color = item_palette[idx % len(item_palette)]
            release_label = f"{item_label} - ordre hebdo"
            receipt_label = f"{item_label} - reception prev. hebdo"
            release_series = aggregate_order_series(
                item_rows,
                "release_qty",
                day_field="order_date_imt",
                bucket_days=7,
            )
            receipt_series = aggregate_order_series(
                item_rows,
                "planned_receipt_qty",
                day_field="planned_arrival_day",
                bucket_days=7,
            )
            if release_series:
                node_order_series[release_label] = release_series
                node_order_styles[release_label] = {"color": color, "width": 2.0}
                node_order_labels_by_item[item_id].append(release_label)
                node_order_peak_by_item[item_id] = max(node_order_peak_by_item[item_id], max(v for _d, v in release_series))
            if receipt_series:
                node_order_series[receipt_label] = receipt_series
                node_order_styles[receipt_label] = {"color": color, "width": 2.0, "dash": "dash"}
                node_order_labels_by_item[item_id].append(receipt_label)
                node_order_peak_by_item[item_id] = max(node_order_peak_by_item[item_id], max(v for _d, v in receipt_series))
        dominant_order_labels: set[str] = set()
        if node_order_peak_by_item:
            global_peak = max(node_order_peak_by_item.values())
            if global_peak > 0:
                dominant_item_ids = {
                    item_id
                    for item_id, peak in node_order_peak_by_item.items()
                    if peak >= global_peak * 0.20
                }
                if 0 < len(dominant_item_ids) < len(node_order_peak_by_item):
                    for item_id in dominant_item_ids:
                        dominant_order_labels.update(node_order_labels_by_item.get(item_id, []))
        if dominant_order_labels:
            dominant_order_series = {
                label: pts for label, pts in node_order_series.items() if label in dominant_order_labels
            }
            other_order_series = {
                label: pts for label, pts in node_order_series.items() if label not in dominant_order_labels
            }
            dominant_order_figure = build_line_chart_figure(
                dominant_order_series,
                title=f"{node_id} - reappro amont volumes dominants",
                y_label="Quantite",
                event_like=True,
                note="Commandes MRP consolidees par semaine/flux/item pour eviter de lire les lignes MRP comme des PO unitaires.",
                series_styles={label: node_order_styles.get(label, {}) for label in dominant_order_series},
            )
            other_order_figure = build_line_chart_figure(
                other_order_series,
                title=f"{node_id} - reappro amont autres items",
                y_label="Quantite",
                event_like=True,
                note="Agregation hebdo. Meme couleur par item. Trait plein = ordre MRP ; pointille = reception previsionnelle.",
                series_styles={label: node_order_styles.get(label, {}) for label in other_order_series},
            )
            node_orders_figure = {
                "kind": "dual_panel_multi",
                "title": f"{node_id} - reappro amont par item",
                "top": dominant_order_figure,
                "bottom": other_order_figure,
            }
        else:
            node_orders_figure = build_line_chart_figure(
                node_order_series,
                title=f"{node_id} - reappro amont par item",
                y_label="Quantite",
                event_like=True,
                note="Commandes MRP consolidees par semaine/flux/item. Trait plein = ordre MRP ; pointille = reception previsionnelle.",
                series_styles=node_order_styles,
            )
        if node_orders_figure is not None:
            node_order_asset = {"figure": node_orders_figure}
        node_ledger_asset = {"html": render_order_ledger_html(node_id, node_orders, item_labels, dormant_reason)}

        summary_lines.extend(
            [
                metric_section("Limites du modele"),
                metric_label_value("Optimisation", "Ce n'est pas un solveur APS global: les decisions sont calculees par regles MRP et simulation chronologique jour apres jour."),
                metric_label_value("Calendrier industriel", "Les campagnes et lots sont modelises, mais pas encore un calendrier atelier complet avec equipes, changements de format et disponibilites machines fines."),
                metric_label_value("Fournisseurs", "Les fournisseurs sont modelises comme stocks/capacites/delais; les contrats, MOQ reels, allocations et arbitrages fournisseurs restent a valider."),
                metric_label_value("Couts", "Les achats viennent des prix matieres; la production est une estimation de cout de conversion pharma; transport, stockage et urgence restent parametrables tant que les couts industriels reels ne sont pas fournis."),
                metric_section("Detail calcul MRP"),
                metric_multiline_value(
                    "Besoin brut / besoin net / StockProj / RecvPrev / OA",
                    mrp_trace_lines if mrp_trace_lines else ["aucune trace MRP explicite disponible pour ce noeud"],
                    limit=10,
                ),
                metric_label_value(
                    "Conformite arrivee vs delai securite source",
                    (
                        f"conformes={safety_summary.get('conform', 0)} ; "
                        f"non conformes={safety_summary.get('non_conform', 0)} ; "
                        f"sans ordres={safety_summary.get('no_orders', 0)} ; "
                        f"pire delta={fmt_days(safety_summary.get('worst_delta_days'), 1) if safety_summary.get('worst_delta_days') is not None else 'n/a'}"
                    ),
                ),
                metric_section("Carnet d'ordres"),
                metric_label_value(
                    "Statuts fin de run",
                    ", ".join(f"{status}={count}" for status, count in sorted(order_status_counts.items()))
                    or "aucun ordre relie a ce noeud",
                ),
                metric_multiline_value(
                    "Remarques validation industrielle",
                    mrp_industrial_validation_lines
                    if mrp_industrial_validation_lines
                    else ["aucune concentration MRP ou lot atypique detecte sur ce noeud"],
                    limit=8,
                ),
                metric_multiline_value(
                    "Derniers ordres",
                    order_lines if order_lines else ["aucun ordre journalise sur ce noeud"],
                    limit=8,
                ),
                metric_label_value(
                    "Diagnostic carnet",
                    dormant_reason or ("actif" if node_orders else "aucun ordre sur le run courant"),
                ),
                metric_section("Ledger hypotheses / derives"),
                metric_multiline_value(
                    "Elements traces",
                    assumption_lines_node if assumption_lines_node else ["aucun element derive/assume journalise pour ce noeud"],
                    limit=8,
                ),
                metric_section("Sources locales"),
                metric_multiline_value(
                    "Sources structure / MRP du noeud",
                    unique_preserve(source_refs) or ["source structure locale non renseignee dans le JSON enrichi"],
                    limit=10,
                ),
            ]
        )
        nodes_payload[node_id] = {
            "title": "Modele du noeud",
            "summary_lines": summary_lines,
            "incoming": node_trace_asset,
            "risk": node_risk_asset,
            "outgoing": node_flow_asset,
            "third": node_ledger_asset,
            "fourth": node_order_asset,
            "stock_flow": node_supplier_stock_flow_asset,
            "supplier_order_send": node_supplier_order_send_asset,
            "nominal": node_nominal_asset,
            "supplier_risk_catalog": node_supplier_risk_catalog_asset,
            "simulated_risks": node_supplier_risk_catalog_asset,
            "uncertainty": node_uncertainty_asset,
            "risk_prediction": node_supplier_risk_prediction_asset,
            "capacity_nominal": node_capacity_nominal_asset,
        }

    def node_role_label(node_id: str) -> str:
        node = node_by_id.get(node_id) or {}
        node_type = str(node_types.get(node_id) or node.get("type") or "n/a")
        role_raw = str(node.get("role_raw") or (node.get("attrs") or {}).get("description") or "")
        type_label = {
            "supplier_dc": "fournisseur",
            "factory": "producteur/usine",
            "distribution_center": "centre de distribution",
            "customer": "client",
        }.get(node_type, node_type or "n/a")
        return f"{type_label}" + (f" - {role_raw}" if role_raw else "")

    def stock_rows_for_source(node_id: str, item_id: str) -> tuple[str, list[dict[str, str]]]:
        node_type = str(node_types.get(node_id) or "")
        if node_type == "supplier_dc":
            return "stock fournisseur", supplier_stock_rows_by_pair.get((node_id, item_id), [])
        if node_type == "distribution_center":
            return "stock DC source", dc_stock_rows_by_pair.get((node_id, item_id), [])
        rows = output_rows_by_pair.get((node_id, item_id), [])
        if rows:
            return "stock produit source", rows
        return "stock source", input_rows_by_pair.get((node_id, item_id), [])

    def stock_rows_for_destination(node_id: str, item_id: str) -> tuple[str, list[dict[str, str]]]:
        node_type = str(node_types.get(node_id) or "")
        if node_type == "distribution_center":
            rows = dc_stock_rows_by_pair.get((node_id, item_id), [])
            if rows:
                return "stock DC destination", rows
        rows = input_rows_by_pair.get((node_id, item_id), [])
        if rows:
            return "stock matiere destination", rows
        rows = output_rows_by_pair.get((node_id, item_id), [])
        if rows:
            return "stock produit destination", rows
        return "stock destination", []

    def stock_stats(rows: list[dict[str, str]]) -> dict[str, float | int | None]:
        if not rows:
            return {"latest": None, "min": None, "max": None, "zero_days": 0}
        sorted_rows = sorted(rows, key=lambda r: int(to_float(r.get("day")) or 0))
        values = [max(0.0, to_float(row.get("stock_end_of_day")) or 0.0) for row in sorted_rows]
        return {
            "latest": values[-1],
            "min": min(values),
            "max": max(values),
            "zero_days": sum(1 for value in values if value <= 1e-9),
        }

    def capacity_stats(rows: list[dict[str, str]]) -> dict[str, float | int | None]:
        if not rows:
            return {"max_util": None, "avg_active_util": None, "active_days": 0, "max_capacity": None}
        utilizations = [max(0.0, to_float(row.get("utilization")) or 0.0) for row in rows]
        active_utils = [value for value in utilizations if value > 1e-9]
        capacities = [max(0.0, to_float(row.get("capacity_qty_per_day")) or 0.0) for row in rows]
        return {
            "max_util": max(utilizations) if utilizations else None,
            "avg_active_util": statistics.mean(active_utils) if active_utils else 0.0,
            "active_days": len(active_utils),
            "max_capacity": max(capacities) if capacities else None,
        }

    def fmt_optional_qty_value(value: float | int | None, digits: int = 0) -> str:
        return "n/a" if value is None else fmt_qty(float(value), digits)

    def fmt_optional_pct_value(value: float | int | None) -> str:
        return "n/a" if value is None else fmt_pct(float(value) * 100.0)

    def render_edge_context_html(
        edge_id: str,
        src: str,
        dst: str,
        context_rows: list[dict[str, str]],
    ) -> str:
        table_rows: list[str] = []
        for row in context_rows:
            table_rows.append(
                "<tr>"
                f"<td>{html.escape(row.get('item') or '')}</td>"
                f"<td>{html.escape(row.get('source') or '')}</td>"
                f"<td>{html.escape(row.get('destination') or '')}</td>"
                f"<td>{html.escape(row.get('mrp') or '')}</td>"
                f"<td>{html.escape(row.get('flow') or '')}</td>"
                "</tr>"
            )
        if not table_rows:
            table_rows.append("<tr><td colspan=\"5\">Aucune donnee contexte exploitable pour ce flux.</td></tr>")
        return "".join(
            [
                "<div class=\"factoryHtmlPanelContent\">",
                f"<div class=\"orderLedgerTextHeader\">{html.escape(edge_id)} - contexte source / destination</div>",
                f"<div class=\"orderLedgerStatus\">Lecture du flux {html.escape(src)} -> {html.escape(dst)}: ce tableau relie ce que commande la destination a ce que peut expedier la source.</div>",
                "<div class=\"kpiFormulaTableWrap\"><table class=\"kpiFormulaTable\">",
                "<thead><tr><th>Item</th><th>Source</th><th>Destination</th><th>MRP destination</th><th>Flux</th></tr></thead>",
                "<tbody>",
                "".join(table_rows),
                "</tbody></table></div>",
                "</div>",
            ]
        )

    for edge in raw.get("edges", []) or []:
        edge_id = str(edge.get("id") or "")
        if not edge_id:
            continue
        src = str(edge.get("from") or "")
        dst = str(edge.get("to") or "")
        if is_pilotage_hidden_edge(src, dst):
            continue
        items = [str(item_id) for item_id in (edge.get("items") or []) if str(item_id or "")]
        attrs = edge.get("attrs") or {}
        planned_lead = max(1.0, to_float(((edge.get("lead_time") or {}).get("mean"))) or 1.0)
        standard_order_qty = display_standard_order_qty(edge)
        standard_order_override = standard_order_override_for_edge(edge)
        metric = edge_metrics.get(edge_id, {})
        total_shipped = 0.0
        avg_util = None
        edge_shipment_rows: list[dict[str, str]] = []
        state_var_lines = [
            "Req_dst(t): signal MRP journalier de la destination pour cet item",
            "T_dst(t): cible MRP de la destination pour l'item transporte",
            "Stock_dst(t): stock projete a destination",
            "RecvPrev_dst(t): receptions futures deja planifiees sur cette destination",
            "Gap_dst(t): ecart a couvrir a destination = T_dst(t) + Backlog_dst(t) - Stock_dst(t) - RecvPrev_dst(t)",
            "BN_dst(t): besoin net porte par la destination sur ce flux = Gap_dst(t) si l'ecart est positif ; sinon 0",
            "OA_src(t): quantite demandee a la source apres normalisation du flux",
            "Ship_src(t): quantite sortie du stock source et expediee sur le flux",
            "RecvPrev_dst(t): quantite qui arrivera a destination a t + lead_time",
            "Lead_ref: delai previsionnel MRP du flux",
            "LT_effectif: delai metier entre ordre passe fournisseur et reception effective",
            "Delai_retroplanning: delai total utilise pour positionner la date d'ordre previsionnelle",
        ]
        assumption_lines = [
            "le flux est simule chronologiquement au jour d'envoi ; la date d'ordre previsionnelle est un jalon calcule pour lire le carnet",
            "standard_order_qty joue comme multiple cible de commande quand disponible",
            "le delai previsionnel matiere vient des donnees source; le delai effectif metier est mesure entre ordre passe fournisseur et reception effective",
        ]
        for item_id in items:
            item_shipment_rows = supplier_ship_by_edge.get((src, dst, item_id), [])
            edge_shipment_rows.extend(item_shipment_rows)
            total_shipped += sum(max(0.0, to_float(r.get("shipped_qty")) or 0.0) for r in item_shipment_rows)
            pair_cap_rows = supplier_cap_by_pair.get((src, item_id), [])
            if pair_cap_rows:
                util = sum(max(0.0, to_float(r.get("utilization")) or 0.0) for r in pair_cap_rows) / len(pair_cap_rows)
                avg_util = util if avg_util is None else max(avg_util, util)
        lane_data_lines = []
        for item_id in items:
            rows = supplier_ship_by_edge.get((src, dst, item_id), [])
            qty_values = [max(0.0, to_float(r.get("shipped_qty")) or 0.0) for r in rows]
            if rows:
                lane_data_lines.append(
                    f"{item_labels.get(item_id, compact_item_label(item_id))}: rows={len(rows)} ; qte_unique={len(set(round(v, 6) for v in qty_values))} ; expedie={fmt_qty(sum(qty_values))}"
                )
        edge_order_lines = []
        edge_order_rows = mrp_orders_by_edge.get(edge_id, [])
        for row in sorted(
            edge_order_rows,
            key=lambda r: (int(to_float(r.get("day")) or 0), str(r.get("item_id") or "")),
            reverse=True,
        )[:8]:
            planned_arrival_day = fmt_order_day(planned_order_receipt_day(row))
            planned_lead = planned_procurement_lead_days(row)
            effective_lead = effective_procurement_lead_days(row)
            edge_order_lines.append(
                f"{item_labels.get(str(row.get('item_id') or ''), compact_item_label(str(row.get('item_id') or '')))}: "
                f"{display_order_type(row.get('order_type'))} ; "
                f"release={row.get('release_day') or 'n/a'} ; "
                f"ordre_passe={fmt_order_day(row.get('order_date_imt'))} ; "
                f"arrival_previsionnelle={planned_arrival_day} ; "
                f"arrival_effective={fmt_order_day(row.get('actual_receipt_day'))} ; "
                f"delai_prev_matiere={fmt_days(planned_lead, 1)} ; "
                f"delai_effectif_matiere={fmt_days(effective_lead, 1)} ; "
                f"status={row.get('order_status_end_of_run') or 'n/a'}"
            )
        source_role = node_role_label(src)
        destination_role = node_role_label(dst)
        edge_context_rows: list[dict[str, str]] = []
        edge_context_summary_lines: list[str] = []
        for item_id in items:
            item_label = item_labels.get(item_id, compact_item_label(item_id))
            source_stock_label, source_stock_rows = stock_rows_for_source(src, item_id)
            destination_stock_label, destination_stock_rows = stock_rows_for_destination(dst, item_id)
            src_stock = stock_stats(source_stock_rows)
            dst_stock = stock_stats(destination_stock_rows)
            cap = capacity_stats(supplier_cap_by_pair.get((src, item_id), []))
            trace_latest = latest_mrp_trace_by_pair.get((dst, item_id), {})
            trace_rows = mrp_trace_rows_by_pair.get((dst, item_id), [])
            max_bn = max((max(0.0, to_float(row.get("bn_qty")) or 0.0) for row in trace_rows), default=0.0)
            bn_days = sum(1 for row in trace_rows if (to_float(row.get("bn_qty")) or 0.0) > 1e-9)
            shipped_rows = supplier_ship_by_edge.get((src, dst, item_id), [])
            shipped_qty = sum(max(0.0, to_float(row.get("shipped_qty")) or 0.0) for row in shipped_rows)
            arrival_qty = sum(
                max(0.0, to_float(row.get("arrived_qty")) or 0.0)
                for row in input_arrivals_by_pair.get((dst, item_id), [])
            )
            item_order_rows = [row for row in edge_order_rows if str(row.get("item_id") or "") == item_id]
            received_orders = sum(1 for row in item_order_rows if str(row.get("order_status_end_of_run") or "") == "received")
            open_orders = len(item_order_rows) - received_orders
            produced_source_qty = sum(
                max(0.0, to_float(row.get("produced_qty")) or 0.0)
                for row in output_rows_by_pair.get((src, item_id), [])
            )
            source_parts = [
                f"{source_stock_label}: fin={fmt_optional_qty_value(src_stock.get('latest'))}",
                f"min={fmt_optional_qty_value(src_stock.get('min'))}",
            ]
            if (src_stock.get("zero_days") or 0) > 0:
                source_parts.append(f"jours a zero={src_stock.get('zero_days')}")
            if cap.get("max_util") is not None:
                source_parts.append(
                    f"util max={fmt_optional_pct_value(cap.get('max_util'))}"
                )
                source_parts.append(f"jours actifs capacite={cap.get('active_days')}")
            if produced_source_qty > 1e-9:
                source_parts.append(f"produit source cumule={fmt_qty(produced_source_qty, 0)}")

            target_qty = to_float(trace_latest.get("target_stock_qty"))
            inventory_position_qty = to_float(trace_latest.get("inventory_position_qty"))
            safety_floor_qty = to_float(trace_latest.get("safety_floor_qty"))
            destination_parts = [
                f"{destination_stock_label}: fin={fmt_optional_qty_value(dst_stock.get('latest'))}",
                f"min={fmt_optional_qty_value(dst_stock.get('min'))}",
            ]
            if target_qty is not None and not math.isnan(target_qty):
                destination_parts.append(f"cible MRP fin={fmt_qty(target_qty, 0)}")
            if inventory_position_qty is not None and not math.isnan(inventory_position_qty):
                destination_parts.append(f"position inv fin={fmt_qty(inventory_position_qty, 0)}")
            if safety_floor_qty is not None and not math.isnan(safety_floor_qty):
                destination_parts.append(f"plancher secu={fmt_qty(safety_floor_qty, 0)}")

            mrp_parts = [
                f"BN max={fmt_qty(max_bn, 0)}",
                f"jours BN>0={bn_days}",
            ]
            flow_parts = [
                f"expedie={fmt_qty(shipped_qty, 0)}",
                f"arrive destination={fmt_qty(arrival_qty, 0)}",
                f"ordres={len(item_order_rows)}",
                f"recus={received_orders}",
                f"ouverts={open_orders}",
            ]
            edge_context_rows.append(
                {
                    "item": item_label,
                    "source": " ; ".join(source_parts),
                    "destination": " ; ".join(destination_parts),
                    "mrp": " ; ".join(mrp_parts),
                    "flow": " ; ".join(flow_parts),
                }
            )
            edge_context_summary_lines.append(
                f"{item_label}: src fin={fmt_optional_qty_value(src_stock.get('latest'))} ; "
                f"dst fin={fmt_optional_qty_value(dst_stock.get('latest'))} ; "
                f"cible={fmt_qty(target_qty, 0) if target_qty is not None and not math.isnan(target_qty) else 'n/a'} ; "
                f"BN max={fmt_qty(max_bn, 0)} ; ordres={len(item_order_rows)}"
            )
        edge_assumption_lines = []
        for row in assumptions_by_edge.get(edge_id, [])[:6]:
            edge_assumption_lines.append(
                f"{str(row.get('category') or 'n/a')} [{str(row.get('source') or 'n/a')}]"
            )
        edge_order_asset = None
        edge_lead_asset = None
        edge_status_asset = None
        edge_sent_series = aggregate_daily_series(
            edge_shipment_rows,
            value_field="shipped_qty",
            day_field="day",
        )
        edge_received_series = aggregate_daily_series(
            edge_shipment_rows,
            value_field="shipped_qty",
            day_field="arrival_day",
        )
        edge_flow_figure = build_line_chart_figure(
            {
                "Envois physiques": bucket_series_points(edge_sent_series, 7),
                "Receptions physiques": bucket_series_points(edge_received_series, 7),
            },
            title=f"{edge_id} - envois et receptions physiques",
            y_label="Quantite / semaine",
            event_like=True,
            note=(
                "Envoi = sortie de stock source datee par production_supplier_shipments_daily.day. "
                "Reception = meme quantite datee a arrival_day chez la destination."
            ),
            series_styles={
                "Envois physiques": {"color": "#dc2626", "width": 2.2},
                "Receptions physiques": {"color": "#2563eb", "width": 2.2, "dash": "dash"},
            },
        )
        if edge_flow_figure is not None:
            edge_order_asset = {"figure": edge_flow_figure}
        edge_lead_figure = build_line_chart_figure(
            {
                "Delai prev. source donnees": average_derived_order_series(edge_order_rows, planned_procurement_lead_days),
                "Delai effectif metier": average_derived_order_series(edge_order_rows, effective_procurement_lead_days),
            },
            title=f"{edge_id} - delais matiere du flux",
            y_label="Jours",
            note=(
                "Delai prev. = reference source donnees. "
                "Delai effectif = reception effective - ordre passe fournisseur."
            ),
        )
        if edge_lead_figure is not None:
            edge_lead_asset = {"figure": edge_lead_figure}
        edge_status_figure = status_bar_figure(
            edge_order_rows,
            field="order_status_end_of_run",
            title=f"{edge_id} - statuts du carnet d'ordres",
        )
        if edge_status_figure is not None:
            edge_status_asset = {"figure": edge_status_figure}
        edge_lead_distribution_figure = lead_distribution_figure(
            edge_shipment_rows,
            title=f"{edge_id} - distribution des delais transport envoi-reception",
            planned_lead_days=planned_lead,
        )
        edge_capacity_rows = [
            row
            for item_id in items
            for row in supplier_cap_by_pair.get((src, item_id), [])
        ]
        edge_stock_rows = [
            row
            for item_id in items
            for row in supplier_stock_rows_by_pair.get((src, item_id), [])
        ]
        edge_nominal_rows = [
            row
            for row in supplier_nominal_by_node.get(src, [])
            if str(row.get("item_id") or "") in set(items)
            and (not str(row.get("dst_node_id") or "") or str(row.get("dst_node_id") or "") == dst)
        ]
        edge_context_html_asset = {
            "html": render_edge_context_html(edge_id, src, dst, edge_context_rows)
        }
        edge_uncertainty_html_asset = {
            "html": render_passive_uncertainty_html(
                edge_id,
                scope_label="flux",
                order_rows=edge_order_rows,
                stock_rows=edge_stock_rows,
                capacity_rows=edge_capacity_rows,
                shipment_rows=edge_shipment_rows,
                nominal_rows=edge_nominal_rows,
                item_labels=item_labels,
            )
        }
        uncertainty_metric_edges[edge_id] = build_passive_uncertainty_metric(
            edge_id,
            scope_label="flux",
            order_rows=edge_order_rows,
            stock_rows=edge_stock_rows,
            capacity_rows=edge_capacity_rows,
            shipment_rows=edge_shipment_rows,
            nominal_rows=edge_nominal_rows,
            item_labels=item_labels,
        )
        edge_context_bundle = [
            {"label": "Source / destination", "asset": edge_context_html_asset},
            {"label": "Incertitude flux", "asset": edge_uncertainty_html_asset},
        ]
        if edge_lead_distribution_figure is not None:
            edge_context_bundle.append(
                {"label": "Distribution delais transport", "asset": {"figure": edge_lead_distribution_figure}}
            )
        edge_context_asset = {"bundle": edge_context_bundle}
        source_refs = [
            " / ".join(part for part in [str(attrs.get("source_workbook") or ""), str(attrs.get("source_sheet") or "")] if part)
        ]
        summary_lines = [
            metric_section("Element"),
            metric_label_value("Flux", f"{src} -> {dst}"),
            metric_label_value("Items", ", ".join(item_labels.get(i, compact_item_label(i)) for i in items) or "n/a"),
            metric_label_value("Id flux", edge_id),
            metric_section("Contexte source / destination"),
            metric_label_value("Source", f"{src} ({source_role})"),
            metric_label_value("Destination", f"{dst} ({destination_role})"),
            metric_label_value(
                "Topologie",
                f"source aval={len(outgoing_edges_by_node.get(src, []))} flux ; destination amont={len(incoming_edges_by_node.get(dst, []))} flux",
            ),
            metric_multiline_value("Synthese item", edge_context_summary_lines, limit=4),
            metric_section("Vue metier du flux"),
            metric_label_value("Role", "Ce flux transporte un besoin MRP depuis une source amont vers une destination aval."),
            metric_label_value("Decision", "La destination commande seulement l'ecart que son stock et ses receptions futures ne couvrent pas deja."),
            metric_label_value("Execution", "La source expedie selon son stock, sa capacite, la quantite standard du flux et le delai simule."),
            metric_section("Application flux - lecture metier"),
            metric_label_value("1. Destination", "Le noeud receveur calcule son besoin net pour l'item transporte."),
            metric_label_value("2. Affectation sourcing", "Le besoin net est affecte a ce flux selon sa part de sourcing MRP."),
            metric_label_value("3. Normalisation", "La quantite demandee est arrondie ou normalisee par quantite standard/lot si applicable."),
            metric_label_value("4. Expedition", "La source envoie la quantite possible selon son stock et sa capacite."),
            metric_label_value("5. Transit", "La quantite expediee reste en transit pendant le delai simule."),
            metric_label_value("6. Reception", "A l'arrivee, le stock destination augmente et le carnet ouvert diminue."),
            metric_section("Glossaire flux"),
            metric_label_value("T_dst(t)", "Cible MRP du noeud receveur pour l'item transporte."),
            metric_label_value("Stock_dst(t)", "Stock projete de l'item chez le receveur."),
            metric_label_value("RecvPrev_dst(t)", "Receptions futures deja planifiees vers le receveur."),
            metric_label_value("OA_src(t)", "Ordre amont demande a la source sur ce flux."),
            metric_label_value("LT prev. / LT effectif", "LT prev. est le delai previsionnel source; LT effectif est le delai metier entre ordre passe fournisseur et reception effective."),
            metric_section("Application flux - variables locales"),
            *[metric_label_value(f"Var {idx+1}", line) for idx, line in enumerate(state_var_lines)],
            metric_section("Application flux - regles locales"),
            metric_label_value("Eq sim 1", "T_dst(t): plus haute valeur entre stock securite, delai securite * Req_dst(t), couverture appro * Req_dst(t) et cible stock active"),
            metric_label_value("Eq sim 2", "Gap_dst(t) = T_dst(t) + Backlog_dst(t) - Stock_dst(t) - RecvPrev_dst(t)"),
            metric_label_value("Eq sim 3", "BN_dst(t) = Gap_dst(t) si Gap_dst(t) > 0 ; sinon 0"),
            metric_label_value("Eq sim 4", "OA_src(t): ordre amont sur le flux = quantite demandee a la source, normalisee si quantite standard"),
            metric_label_value("Eq sim 5", "Reception_prevue = ordre_passe + LT_prev ; Delai_effectif = reception_effective - ordre_passe"),
            metric_label_value("Eq sim 6", "date_ordre_prevue = date_besoin - delai_securite - LT_ref"),
            metric_section("Application flux - correspondance modele global"),
            metric_label_value("Q[f,i](t)", "OA_src(t): quantite commandee sur ce flux apres sourcing et normalisation."),
            metric_label_value("Ship[f,i](t)", "release_day / expedition: quantite sortie de la source et mise en transit."),
            metric_label_value("Recv[f,i](t)", "arrivee_effective: quantite disponible chez la destination apres delai simule."),
            metric_label_value("IT[f,i](t)", "quantite en transit entre release_day et arrivee_effective."),
            metric_label_value("OO[f,i](t)", "carnet ouvert du flux jusqu'a reception."),
            metric_section("Lecture simulateur"),
            metric_label_value("Date d'ordre", "ordre_passe est une date calculee pour lire le carnet: besoin a couvrir - delai securite - delai d'appro."),
            metric_label_value("Date d'envoi", "release_day est le jour ou la quantite est envoyee sur le flux."),
            metric_label_value("Date reception", "arrivee_previsionnelle = ordre_passe + delai previsionnel source ; arrivee_effective = reception simulee ; delai matiere effectif = arrivee_effective - ordre_passe."),
            metric_section("Limites lecture flux"),
            metric_label_value("Granularite", "Les ordres sont consolides pour la lecture, mais la simulation reste journaliere et peut generer plusieurs evenements par item/flux."),
            metric_label_value("Capacite source", "Si la capacite fournisseur n'est pas connue, elle est une hypothese ou n'est pas limitante selon le parametrage du scenario."),
            metric_section("Donnees et interactions"),
            metric_label_value("Lead transport planifie", fmt_days(planned_lead, 1)),
            metric_label_value("Distance", f"{to_float(edge.get('distance_km')) or 0.0:.0f} km"),
            metric_label_value("Quantite standard", fmt_qty(standard_order_qty, 0) if standard_order_qty > 0 else "non renseignee"),
            metric_label_value("Correction quantite", str((standard_order_override or {}).get("note") or "aucune correction appliquee")),
            metric_label_value("Product code source", str(attrs.get("product_code") or "non renseigne")),
            metric_label_value("Compte fournisseur", str(attrs.get("supplier_account") or "non renseigne")),
            metric_multiline_value(
                "Donnees observees flux",
                lane_data_lines if lane_data_lines else ["aucune expedition observee sur ce flux"],
                limit=8,
            ),
            metric_section("Detail calcul MRP"),
            metric_multiline_value(
                "Carnet d'ordres flux",
                edge_order_lines if edge_order_lines else ["aucun ordre MRP direct sur ce flux ; flux probablement aval ou non pilote par appro"],
                limit=8,
            ),
            metric_section("Hypotheses"),
            *[metric_label_value(f"H {idx+1}", line) for idx, line in enumerate(assumption_lines)],
            metric_multiline_value(
                "Ledger hypotheses",
                edge_assumption_lines if edge_assumption_lines else ["aucune hypothese specifique au flux journalisee"],
                limit=6,
            ),
            metric_section("KPI run courant"),
            metric_label_value("Expedie cumule", fmt_qty(total_shipped)),
            metric_label_value("Lignes expedition", str(metric.get("shipment_rows", 0))),
            metric_label_value("Transit observe moyen", fmt_days(metric.get("avg_lead_days"), 1)),
            metric_label_value("Transit observe p50/p90", f"{metric.get('lead_p50_days', 'n/a')} / {metric.get('lead_p90_days', 'n/a')} j"),
            metric_label_value("Transit observe min-max", f"{metric.get('min_lead_days', 'n/a')} - {metric.get('max_lead_days', 'n/a')} j"),
            metric_label_value("Transits distincts observes", str(metric.get("distinct_lead_days", "n/a"))),
            metric_label_value("Quantites distinctes", str(metric.get("distinct_shipped_qty", 0))),
            metric_label_value("Utilisation source max", fmt_pct((avg_util or 0.0) * 100.0) if avg_util is not None else "non calculee"),
            metric_section("Sources et parametres"),
            metric_multiline_value(
                "Sources flux",
                unique_preserve(source_refs) or ["source flux non renseignee dans le JSON enrichi"],
                limit=4,
            ),
        ]
        edges_payload[edge_id] = {
            "title": "Modele du flux",
            "summary_lines": summary_lines,
            "incoming": edge_order_asset,
            "outgoing": edge_lead_asset,
            "third": edge_status_asset,
            "fourth": edge_context_asset,
        }

    return {
        "nodes": nodes_payload,
        "edges": edges_payload,
        "uncertainty_metrics": {
            "nodes": uncertainty_metric_nodes,
            "edges": uncertainty_metric_edges,
        },
        "simulated_risk_metrics": simulated_risk_metrics,
    }


def build_simulated_risk_metrics_from_output(raw: dict[str, Any], output_root: Path) -> dict[str, Any]:
    """Build simulated-risk metrics from a simulation result directory.

    This lets a nominal map display a separate state-dependent risk run without
    reusing the nominal model panel as the source of risk events.
    """

    data_root = output_root / "data"
    summary = load_json_dict(output_root / "summaries" / "first_simulation_summary.json")
    production_tracking = (summary.get("production_tracking") or {}) if isinstance(summary, dict) else {}
    configured_by_node: dict[str, list[dict[str, Any]]] = defaultdict(list)
    applied_by_node: dict[str, list[dict[str, str]]] = defaultdict(list)

    for event in production_tracking.get("supplier_risk_events", []) or []:
        if not isinstance(event, dict):
            continue
        node_id = str(event.get("supplier_id") or event.get("node_id") or "")
        if node_id:
            configured_by_node[node_id].append(dict(event))

    for row in read_csv_rows(data_root / "supplier_state_dependent_risk_events.csv"):
        node_id = str(row.get("supplier_id") or row.get("node_id") or "")
        if node_id:
            configured_by_node[node_id].append(dict(row))

    for row in read_csv_rows(data_root / "assumptions_ledger.csv"):
        if str(row.get("category") or "") != "supplier_risk_event":
            continue
        payload_text = str(row.get("payload_json") or "").strip()
        payload: dict[str, Any] = {}
        if payload_text:
            try:
                decoded = json.loads(payload_text)
                if isinstance(decoded, dict):
                    payload = decoded
            except json.JSONDecodeError:
                payload = {}
        node_id = str(payload.get("supplier_id") or row.get("node_id") or "")
        if node_id:
            configured_by_node[node_id].append(payload)

    for row in read_csv_rows(data_root / "supplier_risk_events_applied_daily.csv"):
        node_id = str(row.get("supplier_id") or "")
        if node_id:
            applied_by_node[node_id].append(row)

    payload = build_simulated_supplier_risk_metrics(
        configured_by_node=configured_by_node,
        applied_by_node=applied_by_node,
    )
    payload["source_output_dir"] = str(output_root)
    policy = (summary.get("policy") or {}) if isinstance(summary, dict) else {}
    state_policy = (policy.get("supplier_state_dependent_risk") or {}) if isinstance(policy, dict) else {}
    payload.setdefault("global", {})["state_dependent_enabled"] = bool(state_policy.get("enabled"))
    payload.setdefault("global", {})["state_dependent_generated_event_count"] = int(
        to_float(state_policy.get("generated_event_count")) or 0
    )
    payload.setdefault("global", {})["scenario_id"] = str(summary.get("scenario_id") or "")
    return payload


def build_realistic_sensitivity_panel_metrics(
    raw: dict[str, Any],
    summary_json: Path,
    local_elasticities_csv: Path,
    stress_impacts_csv: Path,
) -> dict[str, Any]:
    local_rows = read_csv_rows(local_elasticities_csv)
    stress_rows = read_csv_rows(stress_impacts_csv)
    if not local_rows and not stress_rows and not summary_json.exists():
        return {"nodes": {}, "global": {}}

    try:
        summary = json.loads(summary_json.read_text(encoding="utf-8")) if summary_json.exists() else {}
    except Exception:
        summary = {}

    nodes = raw.get("nodes", []) or []
    node_item_ids = build_node_item_ids(raw)
    node_types = build_node_type_lookup(raw)
    incoming_sources, outgoing_targets = build_node_relationships(raw)

    def is_global_parameter(parameter_key: str) -> bool:
        return "::" not in parameter_key

    def row_scope(parameter_key: str, node_id: str) -> str | None:
        return sensitivity_row_scope(
            parameter_key,
            node_id,
            node_item_ids,
            node_types,
            incoming_sources,
            outgoing_targets,
        )

    def safe_abs(value: Any) -> float:
        num = to_float(value)
        if num is None or math.isnan(num):
            return 0.0
        return abs(num)

    def choose_local_global(kpi: str) -> dict[str, str] | None:
        candidates = [
            row
            for row in local_rows
            if str(row.get("kpi") or "") == kpi and is_global_parameter(str(row.get("parameter_key") or ""))
        ]
        if not candidates:
            return None
        return max(candidates, key=lambda row: safe_abs(row.get("abs_elasticity")))

    def choose_stress_global(kpi: str) -> dict[str, str] | None:
        delta_field = f"delta::{kpi}"
        candidates = [
            row
            for row in stress_rows
            if is_global_parameter(str(row.get("parameter_key") or ""))
        ]
        if not candidates:
            return None
        return max(candidates, key=lambda row: safe_abs(row.get(delta_field)))

    scope_order = {
        "direct": 0,
        "upstream_supplier_capacity": 1,
        "upstream_factory_capacity": 1,
        "upstream_reliability": 2,
        "upstream_factory_reliability": 2,
        "upstream_lead_time": 3,
        "upstream_factory_lead_time": 3,
        "upstream_supplier_stock": 4,
        "item": 5,
        "downstream_demand": 6,
    }

    def choose_node_local(
        node_id: str,
        kpi: str,
        *,
        allowed_scopes: tuple[str, ...] | None = None,
        parameter_groups: tuple[str, ...] | None = None,
    ) -> dict[str, str] | None:
        candidates = []
        for row in local_rows:
            if str(row.get("kpi") or "") != kpi:
                continue
            if parameter_groups and str(row.get("parameter_group") or "") not in parameter_groups:
                continue
            scope = row_scope(str(row.get("parameter_key") or ""), node_id)
            if not scope:
                continue
            if allowed_scopes and scope not in allowed_scopes:
                continue
            candidates.append((scope_order.get(scope, 9), safe_abs(row.get("abs_elasticity")), row))
        if not candidates:
            return None
        candidates.sort(key=lambda item: (item[0], -item[1], str(item[2].get("parameter_label") or "")))
        return candidates[0][2]

    def choose_node_stress(
        node_id: str,
        kpi: str,
        *,
        allowed_scopes: tuple[str, ...] | None = None,
        parameter_groups: tuple[str, ...] | None = None,
    ) -> dict[str, str] | None:
        delta_field = f"delta::{kpi}"
        candidates = []
        for row in stress_rows:
            if parameter_groups and str(row.get("parameter_group") or "") not in parameter_groups:
                continue
            scope = row_scope(str(row.get("parameter_key") or ""), node_id)
            if not scope:
                continue
            if allowed_scopes and scope not in allowed_scopes:
                continue
            candidates.append((scope_order.get(scope, 9), safe_abs(row.get(delta_field)), row))
        if not candidates:
            return None
        candidates.sort(key=lambda item: (item[0], -item[1], str(item[2].get("parameter_label") or "")))
        return candidates[0][2]

    baseline = summary.get("baseline", {}) if isinstance(summary, dict) else {}
    baseline_fill = to_float((baseline or {}).get("fill_rate"))
    baseline_backlog = to_float((baseline or {}).get("ending_backlog"))
    baseline_cost = to_float((baseline or {}).get("total_cost"))

    def fmt_fill(value: float | None) -> str:
        if value is None:
            return "n/a"
        return f"{value * 100:.1f}%"

    def fmt_backlog(value: float | None) -> str:
        if value is None:
            return "n/a"
        return f"{value:,.0f}".replace(",", " ")

    def fmt_money(value: float | None) -> str:
        if value is None:
            return "n/a"
        abs_value = abs(value)
        if abs_value >= 1_000_000:
            return f"{value / 1_000_000:.2f} M"
        if abs_value >= 1_000:
            return f"{value / 1_000:.1f} k"
        return f"{value:.0f}"

    local_test_ranges: dict[str, tuple[float, float] | float] = {
        "lead_time": (0.9, 1.1),
        "transport_cost": (0.9, 1.1),
        "supplier_stock": (0.9, 1.1),
        "production_stock": (0.9, 1.1),
        "capacity_global": (0.95, 1.05),
        "supplier_capacity_global": (0.95, 1.05),
        "safety_stock": (0.9, 1.1),
        "supplier_reliability_global": 0.95,
        "demand_item": (0.9, 1.1),
        "capacity_node": (0.95, 1.05),
        "supplier_stock_node": (0.9, 1.1),
        "supplier_capacity_node": (0.9, 1.1),
        "supplier_lead_time_node": (0.9, 1.1),
        "supplier_reliability_node": 0.95,
    }

    def fmt_factor(value: float | None) -> str:
        if value is None or math.isnan(value):
            return "n/a"
        percent = value * 100.0
        if abs(percent - round(percent)) <= 1e-9:
            return f"{percent:.0f}%"
        return f"{percent:.1f}%"

    def local_test_label(row: dict[str, str] | None) -> str:
        if not row:
            return "amplitude n/a"
        group = str(row.get("parameter_group") or "")
        spec = local_test_ranges.get(group)
        if isinstance(spec, tuple):
            return f"test {fmt_factor(spec[0])} / {fmt_factor(spec[1])}"
        if isinstance(spec, float):
            return f"test {fmt_factor(spec)}"
        return "test n/a"

    def stress_test_label(row: dict[str, str] | None) -> str:
        if not row:
            return "variation n/a"
        factor_value = to_float(row.get("factor_value"))
        if factor_value is None or math.isnan(factor_value):
            return "variation n/a"
        return f"variation severe 100% -> {fmt_factor(factor_value)}"

    def describe_local(row: dict[str, str] | None, *, kpi: str) -> str:
        if not row:
            return "n/a"
        label = str(row.get("parameter_label") or row.get("parameter_key") or "").strip()
        elasticity = to_float(row.get("abs_elasticity"))
        if elasticity is None or math.isnan(elasticity):
            return label or "n/a"
        suffix = ""
        if str(row.get("parameter_key") or "").startswith("demand_item::"):
            suffix = " (via produit)"
        return f"{label}{suffix} | {local_test_label(row)} | e={elasticity:.3f}"

    def describe_stress(row: dict[str, str] | None, *, kpi: str) -> str:
        if not row:
            return "n/a"
        label = str(row.get("parameter_label") or row.get("parameter_key") or "").strip()
        delta = to_float(row.get(f"delta::{kpi}"))
        if delta is None or math.isnan(delta):
            return label or "n/a"
        if kpi == "fill_rate":
            value = f"{delta * 100:+.1f} pts"
        elif kpi == "ending_backlog":
            value = f"{delta:+,.0f}".replace(",", " ")
        else:
            value = f"{fmt_money(delta)}"
            if not value.startswith("-") and not value.startswith("+"):
                value = f"+{value}"
        suffix = ""
        if str(row.get("parameter_key") or "").startswith("demand_item::"):
            suffix = " (via produit)"
        return f"{label}{suffix} | {stress_test_label(row)} | {value}"

    global_fill_local = choose_local_global("fill_rate")
    global_fill_stress = choose_stress_global("fill_rate")
    global_cost_local = choose_local_global("total_cost")
    global_cost_stress = choose_stress_global("total_cost")

    def classify_node(node_id: str) -> str:
        node_type = node_types.get(node_id, "")
        service_stress = safe_abs((choose_node_stress(node_id, "fill_rate") or {}).get("delta::fill_rate"))
        backlog_stress = safe_abs((choose_node_stress(node_id, "ending_backlog") or {}).get("delta::ending_backlog"))
        cost_stress = safe_abs((choose_node_stress(node_id, "total_cost") or {}).get("delta::total_cost"))
        service_elasticity = safe_abs((choose_node_local(node_id, "fill_rate") or {}).get("abs_elasticity"))
        if node_type == "factory":
            upstream_rel = safe_abs(
                (
                    choose_node_stress(
                        node_id,
                        "fill_rate",
                        allowed_scopes=("upstream_reliability",),
                    )
                    or {}
                ).get("delta::fill_rate")
            )
            upstream_lt = safe_abs(
                (
                    choose_node_stress(
                        node_id,
                        "fill_rate",
                        allowed_scopes=("upstream_lead_time",),
                    )
                    or {}
                ).get("delta::fill_rate")
            )
            if service_stress >= 0.05 or backlog_stress >= 200_000 or upstream_rel >= 0.03:
                return "Usine critique pour la disponibilite produit"
            if upstream_lt >= 0.01 or service_elasticity >= 0.03:
                return "Usine sensible aux flux amont"
            return "Usine robuste localement"
        if node_type == "supplier_dc":
            if service_stress >= 0.03 or backlog_stress >= 100_000:
                return "Fournisseur critique"
            if cost_stress >= 250_000:
                return "Fournisseur critique cout"
            return "Impact fournisseur limite"
        if node_type == "distribution_center":
            if service_stress >= 0.02 or backlog_stress >= 100_000:
                return "DC sensible a la demande"
            return "DC plutot robuste"
        if service_stress >= 0.05 or backlog_stress >= 1000 or service_elasticity >= 0.05:
            return "Critique service"
        if cost_stress >= 250_000:
            return "Critique cout"
        if service_stress >= 0.01 or backlog_stress >= 250 or cost_stress >= 25_000:
            return "Surveiller"
        return "Impact local faible"

    def node_summary_lines(node_id: str) -> list[dict[str, str]]:
        node_type = node_types.get(node_id, "")
        service_line = metric_label_value(
            "Disponibilite liee",
            describe_stress(choose_node_stress(node_id, "fill_rate"), kpi="fill_rate"),
        )
        backlog_line = metric_label_value(
            "Backlog lie",
            describe_stress(choose_node_stress(node_id, "ending_backlog"), kpi="ending_backlog"),
        )
        cost_line = metric_label_value(
            "Cout lie",
            describe_stress(choose_node_stress(node_id, "total_cost"), kpi="total_cost"),
        )
        baseline_line = metric_label_value(
            "Baseline",
            f"disponibilite {fmt_fill(baseline_fill)} | backlog {fmt_backlog(baseline_backlog)} | cout {fmt_money(baseline_cost)}",
        )
        if node_type == "factory":
            return [
                baseline_line,
                service_line,
                backlog_line,
                metric_label_value(
                    "Capacite usine",
                    describe_local(
                        choose_node_local(
                            node_id,
                            "fill_rate",
                            allowed_scopes=("direct",),
                            parameter_groups=("capacity_node",),
                        ),
                        kpi="fill_rate",
                    ),
                ),
                metric_label_value(
                    "Backlog usine",
                    describe_stress(
                        choose_node_stress(
                            node_id,
                            "ending_backlog",
                            allowed_scopes=("direct",),
                            parameter_groups=("capacity_node",),
                        ),
                        kpi="ending_backlog",
                    ),
                ),
                metric_label_value(
                    "Fiabilite amont",
                    describe_stress(
                        choose_node_stress(
                            node_id,
                            "fill_rate",
                            allowed_scopes=("upstream_reliability",),
                            parameter_groups=("supplier_reliability_node",),
                        ),
                        kpi="fill_rate",
                    ),
                ),
                metric_label_value(
                    "Lead time amont",
                    describe_stress(
                        choose_node_stress(
                            node_id,
                            "fill_rate",
                            allowed_scopes=("upstream_lead_time",),
                            parameter_groups=("supplier_lead_time_node",),
                        ),
                        kpi="fill_rate",
                    ),
                ),
                cost_line,
                metric_label_value("Statut", classify_node(node_id)),
            ]
        if node_type == "supplier_dc":
            return [
                baseline_line,
                service_line,
                backlog_line,
                metric_label_value(
                    "Fiabilite locale",
                    describe_stress(
                        choose_node_stress(
                            node_id,
                            "fill_rate",
                            allowed_scopes=("direct",),
                            parameter_groups=("supplier_reliability_node",),
                        ),
                        kpi="fill_rate",
                    ),
                ),
                metric_label_value(
                    "Lead time local",
                    describe_stress(
                        choose_node_stress(
                            node_id,
                            "fill_rate",
                            allowed_scopes=("direct",),
                            parameter_groups=("supplier_lead_time_node",),
                        ),
                        kpi="fill_rate",
                    ),
                ),
                metric_label_value(
                    "Debit local",
                    describe_local(
                        choose_node_local(
                            node_id,
                            "fill_rate",
                            allowed_scopes=("direct",),
                            parameter_groups=("supplier_capacity_node",),
                        ),
                        kpi="fill_rate",
                    ),
                ),
                cost_line,
                metric_label_value("Statut", classify_node(node_id)),
            ]
        if node_type == "distribution_center":
            return [
                baseline_line,
                service_line,
                backlog_line,
                metric_label_value(
                    "Demande liee",
                    describe_stress(
                        choose_node_stress(
                            node_id,
                            "fill_rate",
                            allowed_scopes=("item",),
                            parameter_groups=("demand_item",),
                        ),
                        kpi="fill_rate",
                    ),
                ),
                metric_label_value(
                    "Usine amont",
                    describe_stress(
                        choose_node_stress(
                            node_id,
                            "fill_rate",
                            allowed_scopes=("upstream_factory_capacity",),
                            parameter_groups=("capacity_node",),
                        ),
                        kpi="fill_rate",
                    ),
                ),
                cost_line,
                metric_label_value("Statut", classify_node(node_id)),
            ]
        return [
            baseline_line,
            metric_label_value("Disponibilite globale", describe_stress(global_fill_stress, kpi="fill_rate")),
            service_line,
            metric_label_value(
                "Elasticite disponibilite",
                describe_local(choose_node_local(node_id, "fill_rate"), kpi="fill_rate"),
            ),
            backlog_line,
            metric_label_value("Cout global", describe_stress(global_cost_stress, kpi="total_cost")),
            cost_line,
            metric_label_value(
                "Elasticite cout",
                describe_local(choose_node_local(node_id, "total_cost"), kpi="total_cost"),
            ),
            metric_label_value("Statut", classify_node(node_id)),
        ]

    nodes_payload: dict[str, Any] = {}
    for node in nodes:
        node_id = str(node.get("id") or "")
        if not node_id:
            continue
        nodes_payload[node_id] = {
            "title": "Sensibilite parametrique annuelle",
            "summary_lines": node_summary_lines(node_id),
        }

    global_payload = {
        "title": "Sensibilite parametrique annuelle",
        "summary_lines": [
            metric_label_value(
                "Baseline",
                f"disponibilite {fmt_fill(baseline_fill)} | backlog {fmt_backlog(baseline_backlog)} | cout {fmt_money(baseline_cost)}",
            ),
            metric_label_value("Disponibilite globale", describe_stress(global_fill_stress, kpi="fill_rate")),
            metric_label_value("Elasticite disponibilite", describe_local(global_fill_local, kpi="fill_rate")),
            metric_label_value("Cout global", describe_stress(global_cost_stress, kpi="total_cost")),
            metric_label_value("Elasticite cout", describe_local(global_cost_local, kpi="total_cost")),
        ],
    }
    selected_suppliers = summary.get("selected_suppliers", []) if isinstance(summary, dict) else []
    return {"nodes": nodes_payload, "global": global_payload, "selected_suppliers": selected_suppliers}


def build_threshold_sensitivity_panel_metrics(
    raw: dict[str, Any],
    summary_json: Path,
    parameter_summary_csv: Path,
) -> dict[str, Any]:
    rows = read_csv_rows(parameter_summary_csv)
    if not rows and not summary_json.exists():
        return {"nodes": {}, "global": {}, "selected_suppliers": []}

    try:
        summary = json.loads(summary_json.read_text(encoding="utf-8")) if summary_json.exists() else {}
    except Exception:
        summary = {}

    nodes = raw.get("nodes", []) or []
    node_item_ids = build_node_item_ids(raw)
    node_types = build_node_type_lookup(raw)
    incoming_sources, outgoing_targets = build_node_relationships(raw)

    def metric(label: str, value: Any, *, section: bool = False) -> dict[str, Any]:
        return {"label": label, "value": str(value), "section": section}

    def safe_float(value: Any) -> float | None:
        num = to_float(value)
        if num is None or math.isnan(num):
            return None
        return float(num)

    def fmt_fill(value: float | None) -> str:
        if value is None:
            return "n/a"
        return f"{value * 100:.1f}%"

    def fmt_backlog(value: float | None) -> str:
        if value is None:
            return "n/a"
        return f"{value:,.0f}".replace(",", " ")

    def fmt_money(value: float | None) -> str:
        if value is None:
            return "n/a"
        abs_value = abs(value)
        if abs_value >= 1_000_000:
            return f"{value / 1_000_000:.2f} M"
        if abs_value >= 1_000:
            return f"{value / 1_000:.1f} k"
        return f"{value:.0f}"

    def fmt_level(value: float | None) -> str:
        if value is None:
            return "n/a"
        percent = value * 100.0
        return f"{percent:.0f}%" if abs(percent - round(percent)) <= 1e-9 else f"{percent:.1f}%"

    def side_label(row: dict[str, str]) -> str:
        mono = str(row.get("fill_rate_monotonicity") or "").strip().lower()
        cross = safe_float(row.get("fill_rate_cross_service_threshold_at"))
        if cross is None:
            return "pas de rupture dans le sweep"
        if mono == "increasing":
            return f"rupture si < {fmt_level(cross)}"
        if mono == "decreasing":
            return f"rupture si > {fmt_level(cross)}"
        return f"rupture autour de {fmt_level(cross)}"

    def safe_band_label(row: dict[str, str]) -> str:
        low = safe_float(row.get("safe_band_low"))
        high = safe_float(row.get("safe_band_high"))
        if low is None and high is None:
            return "aucune bande sure identifiee"
        if low is None:
            return f"<= {fmt_level(high)}"
        if high is None:
            return f">= {fmt_level(low)}"
        return f"{fmt_level(low)} a {fmt_level(high)}"

    def max_fill_drop_pts(row: dict[str, str]) -> str:
        value = safe_float(row.get("max_fill_rate_drop"))
        if value is None:
            return "n/a"
        return f"{value * 100:.1f} pts"

    def steepest_segment_label(row: dict[str, str]) -> str:
        raw_segment = str(row.get("steepest_fill_segment") or "").strip()
        if not raw_segment:
            return "n/a"
        try:
            values = json.loads(raw_segment)
            if isinstance(values, list) and len(values) == 2:
                return f"{fmt_level(safe_float(values[0]))} -> {fmt_level(safe_float(values[1]))}"
        except Exception:
            pass
        return raw_segment

    def is_global_parameter(parameter_key: str) -> bool:
        return "::" not in parameter_key

    scope_order = {
        "direct": 0,
        "upstream_supplier_capacity": 1,
        "upstream_factory_capacity": 1,
        "upstream_reliability": 2,
        "upstream_factory_reliability": 2,
        "upstream_lead_time": 3,
        "upstream_factory_lead_time": 3,
        "upstream_supplier_stock": 4,
        "item": 5,
        "downstream_demand": 6,
    }

    def row_scope(row: dict[str, str], node_id: str) -> str | None:
        return sensitivity_row_scope(
            str(row.get("parameter_key") or ""),
            node_id,
            node_item_ids,
            node_types,
            incoming_sources,
            outgoing_targets,
        )

    def row_rank(row: dict[str, str], node_id: str) -> tuple[float, int, float]:
        cross = safe_float(row.get("fill_rate_cross_service_threshold_at"))
        max_drop = safe_float(row.get("max_fill_rate_drop")) or 0.0
        scope = row_scope(row, node_id)
        scope_rank = scope_order.get(scope, 9)
        if cross is None:
            return (999.0, scope_rank, -max_drop)
        return (abs(cross - 1.0), scope_rank, -max_drop)

    def choose_global_best() -> dict[str, str] | None:
        candidates = [row for row in rows if is_global_parameter(str(row.get("parameter_key") or ""))]
        if not candidates:
            return None
        candidates.sort(
            key=lambda row: (
                999.0 if safe_float(row.get("fill_rate_cross_service_threshold_at")) is None else abs(
                    (safe_float(row.get("fill_rate_cross_service_threshold_at")) or 1.0) - 1.0
                ),
                -(safe_float(row.get("max_fill_rate_drop")) or 0.0),
                str(row.get("parameter_label") or ""),
            )
        )
        return candidates[0]

    def choose_node_best(node_id: str) -> dict[str, str] | None:
        candidates = [row for row in rows if row_scope(row, node_id)]
        if not candidates:
            return None
        candidates.sort(key=lambda row: row_rank(row, node_id))
        return candidates[0]

    def classify(row: dict[str, str] | None) -> str:
        if not row:
            return "Pas de signal seuil"
        cross = safe_float(row.get("fill_rate_cross_service_threshold_at"))
        max_drop = safe_float(row.get("max_fill_rate_drop")) or 0.0
        if cross is not None and abs(cross - 1.0) <= 0.10:
            return "Critique"
        if cross is not None and abs(cross - 1.0) <= 0.25:
            return "Sensible"
        if max_drop >= 0.05:
            return "A surveiller"
        return "Robuste localement"

    baseline = summary.get("baseline", {}) if isinstance(summary, dict) else {}
    baseline_fill = safe_float((baseline or {}).get("kpi::fill_rate"))
    baseline_backlog = safe_float((baseline or {}).get("kpi::ending_backlog"))
    baseline_cost = safe_float((baseline or {}).get("kpi::total_cost"))
    service_threshold = safe_float(summary.get("service_threshold")) or 0.95
    selected_suppliers = summary.get("selected_suppliers", []) if isinstance(summary, dict) else []

    global_best = choose_global_best()
    global_payload = {
        "title": "Seuils annuels",
        "summary_lines": [
            metric(
                "Baseline",
                f"disponibilite {fmt_fill(baseline_fill)} | backlog {fmt_backlog(baseline_backlog)} | cout {fmt_money(baseline_cost)}",
            ),
            metric("Disponibilite cible", fmt_fill(service_threshold)),
            metric("Levier global critique", str((global_best or {}).get("parameter_label") or "n/a")),
            metric("Point de bascule", side_label(global_best or {})),
            metric("Bande sure", safe_band_label(global_best or {})),
            metric("Max fill drop", max_fill_drop_pts(global_best or {})),
            metric("Segment le plus raide", steepest_segment_label(global_best or {})),
            metric("Statut", classify(global_best)),
        ],
    }

    nodes_payload: dict[str, Any] = {}
    for node in nodes:
        node_id = str(node.get("id") or "")
        if not node_id:
            continue
        best_row = choose_node_best(node_id)
        if best_row is None:
            continue
        nodes_payload[node_id] = {
            "title": "Seuils annuels",
            "summary_lines": [
                metric(
                "Baseline",
                    f"disponibilite {fmt_fill(baseline_fill)} | backlog {fmt_backlog(baseline_backlog)} | cout {fmt_money(baseline_cost)}",
            ),
                metric("Disponibilite cible", fmt_fill(service_threshold)),
                metric("Driver critique", str(best_row.get("parameter_label") or "n/a")),
                metric("Point de bascule", side_label(best_row)),
                metric("Bande sure", safe_band_label(best_row)),
                metric("Max fill drop", max_fill_drop_pts(best_row)),
                metric("Segment le plus raide", steepest_segment_label(best_row)),
                metric("Statut", classify(best_row)),
            ],
        }

    return {"nodes": nodes_payload, "global": global_payload, "selected_suppliers": selected_suppliers}


def build_node_item_ids(raw: dict[str, Any]) -> dict[str, set[str]]:
    nodes = raw.get("nodes", []) or []
    incoming_items, outgoing_items = build_edge_item_sets(raw)
    node_item_ids: dict[str, set[str]] = defaultdict(set)
    for node in nodes:
        node_id = str(node.get("id") or "")
        if not node_id:
            continue
        node_item_ids[node_id].update(incoming_items.get(node_id, set()))
        node_item_ids[node_id].update(outgoing_items.get(node_id, set()))
        inventory = node.get("inventory") or {}
        for state in (inventory.get("states") or []):
            item_id = str((state or {}).get("item_id") or "")
            if item_id:
                node_item_ids[node_id].add(item_id)
        for process in (node.get("processes") or []):
            for inp in (process.get("inputs") or []):
                item_id = str((inp or {}).get("item_id") or "")
                if item_id:
                    node_item_ids[node_id].add(item_id)
            for out in (process.get("outputs") or []):
                item_id = str((out or {}).get("item_id") or "")
                if item_id:
                    node_item_ids[node_id].add(item_id)
    return node_item_ids


def threshold_row_scope(
    row: dict[str, str],
    node_id: str,
    node_item_ids: dict[str, set[str]],
    node_types: dict[str, str],
    incoming_sources: dict[str, set[str]],
    outgoing_targets: dict[str, set[str]],
) -> str | None:
    return sensitivity_row_scope(
        str(row.get("parameter_key") or ""),
        node_id,
        node_item_ids,
        node_types,
        incoming_sources,
        outgoing_targets,
    )


def select_best_threshold_parameter_row(
    summary_rows: list[dict[str, str]],
    node_id: str,
    node_item_ids: dict[str, set[str]],
    node_types: dict[str, str],
    incoming_sources: dict[str, set[str]],
    outgoing_targets: dict[str, set[str]],
) -> dict[str, str] | None:
    scope_order = {
        "direct": 0,
        "upstream_supplier_capacity": 1,
        "upstream_factory_capacity": 1,
        "upstream_reliability": 2,
        "upstream_factory_reliability": 2,
        "upstream_lead_time": 3,
        "upstream_factory_lead_time": 3,
        "upstream_supplier_stock": 4,
        "item": 5,
        "downstream_demand": 6,
    }
    candidates = []
    for row in summary_rows:
        scope = threshold_row_scope(
            row,
            node_id,
            node_item_ids,
            node_types,
            incoming_sources,
            outgoing_targets,
        )
        if not scope:
            continue
        cross = to_float(row.get("fill_rate_cross_service_threshold_at"))
        max_drop = to_float(row.get("max_fill_rate_drop")) or 0.0
        scope_rank = scope_order.get(scope, 9)
        cross_rank = 999.0 if cross is None or math.isnan(cross) else abs(cross - 1.0)
        candidates.append((cross_rank, scope_rank, -max_drop, str(row.get("parameter_label") or ""), row))
    if not candidates:
        return None
    candidates.sort(key=lambda item: (item[0], item[1], item[2], item[3]))
    return candidates[0][4]


def build_threshold_metric_curve_payload(
    parameter_rows: list[dict[str, str]],
    *,
    parameter_label: str,
    filename: str,
    service_threshold: float | None,
    baseline_production_planning_line_count: float | None = None,
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    usable_rows = []
    for row in parameter_rows:
        level = to_float(row.get("level"))
        if level is None or math.isnan(level):
            continue
        usable_rows.append((float(level), row))
    usable_rows.sort(key=lambda item: item[0])
    if len(usable_rows) < 2:
        return None, None

    def format_parameter_level(value: float) -> str:
        percent = value * 100.0
        raw = f"{percent:.0f}%" if abs(percent - round(percent)) <= 1e-9 else f"{percent:.1f}%"
        return f"{raw} ref." if abs(value - 1.0) <= 1e-9 else raw

    x = [format_parameter_level(level) for level, _ in usable_rows]
    availability = [sensitivity_availability_percent(row) for _, row in usable_rows]
    replanning_rate = [
        sensitivity_replanning_rate_percent(
            row,
            baseline_production_planning_line_count=baseline_production_planning_line_count,
        )
        for _, row in usable_rows
    ]
    has_replanning_rate = any(value is not None for value in replanning_rate)
    backlog = [float(to_float(row.get("kpi::ending_backlog")) or 0.0) for _, row in usable_rows]
    inventory_cost = [
        float(to_float(row.get("kpi::inventory_cost")) or to_float(row.get("kpi::total_holding_cost")) or 0.0)
        for _, row in usable_rows
    ]
    material_delay = [float(to_float(row.get("kpi::material_delay_days")) or 0.0) for _, row in usable_rows]

    service_extra = [
    ]
    if service_threshold is not None and not math.isnan(service_threshold):
        service_extra.append(
            {
                "type": "scatter",
                "mode": "lines",
                "name": "Seuil disponibilite",
                "x": x,
                "y": [float(fraction_metric_to_percent(service_threshold)) for _ in x],
                "line": {"width": 1.4, "color": "#dc2626", "dash": "dash"},
            }
        )
    incoming_payload = {
        "figure": {
            "kind": "dual_panel",
            "x_axis_kind": "parameter_sweep",
            "title": f"{parameter_label} - impact KPI par niveau teste",
                "show_legend": True,
                "top": {
                    "kind": "line",
                    "title": "Disponibilite produit",
                    "x_label": "Niveau teste du parametre (100% = reference active)",
                    "y_label": "Disponibilite produit (%)",
                    "y_unit": "percent",
                "x": x,
                "y": availability,
                "extra_traces": service_extra,
            },
                "bottom": {
                    "kind": "line",
                    "title": "Taux de replanification production" if has_replanning_rate else "Taux de replanification production - non calcule dans cette etude",
                    "x_label": "Niveau teste du parametre (100% = reference active)",
                    "y_label": "Taux de replanification (%)",
                    "y_unit": "percent",
                "x": x,
                "y": replanning_rate,
            },
        }
    }
    outgoing_payload = {
        "figure": {
            "kind": "dual_panel",
            "x_axis_kind": "parameter_sweep",
            "title": f"{parameter_label} - cout et detail supply par niveau teste",
                "show_legend": True,
                "top": {
                    "kind": "line",
                    "title": "Cout de stockage",
                    "x_label": "Niveau teste du parametre (100% = reference active)",
                    "y_label": "Cout",
                "x": x,
                "y": inventory_cost,
            },
                "bottom": {
                    "kind": "line",
                    "title": "Backlog final",
                    "x_label": "Niveau teste du parametre (100% = reference active)",
                    "y_label": "Quantite",
                "x": x,
                "y": backlog,
                "extra_traces": [
                    {
                        "type": "scatter",
                        "mode": "lines+markers",
                        "name": "Retard matiere",
                        "x": x,
                        "y": material_delay,
                        "line": {"width": 1.8, "color": "#d97706", "dash": "dot"},
                        "marker": {"size": 5, "color": "#d97706"},
                    }
                ],
            },
        }
    }
    return incoming_payload, outgoing_payload

    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt  # type: ignore
    except Exception:
        return None, None

    x = [level for level, _ in usable_rows]
    fill = [float(to_float(row.get("kpi::fill_rate")) or 0.0) for _, row in usable_rows]
    backlog = [float(to_float(row.get("kpi::ending_backlog")) or 0.0) for _, row in usable_rows]
    total_cost = [float(to_float(row.get("kpi::total_cost")) or 0.0) for _, row in usable_rows]
    avg_inventory = [float(to_float(row.get("kpi::avg_inventory")) or 0.0) for _, row in usable_rows]

    base_fill = None
    base_backlog = None
    base_cost = None
    base_inventory = None
    for level, row in usable_rows:
        if abs(level - 1.0) <= 1e-9:
            base_fill = float(to_float(row.get("kpi::fill_rate")) or 0.0)
            base_backlog = float(to_float(row.get("kpi::ending_backlog")) or 0.0)
            base_cost = float(to_float(row.get("kpi::total_cost")) or 0.0)
            base_inventory = float(to_float(row.get("kpi::avg_inventory")) or 0.0)
            break

    def format_level(value: float) -> str:
        percent = value * 100.0
        return f"{percent:.0f}%" if abs(percent - round(percent)) <= 1e-9 else f"{percent:.1f}%"

    incoming_fig, incoming_axes = plt.subplots(2, 1, figsize=(9.2, 7.0), sharex=True)
    incoming_fig.patch.set_facecolor("#ffffff")
    ax_fill = incoming_axes[0]
    ax_fill.plot(x, fill, color="#2563eb", marker="o", linewidth=2.2)
    if service_threshold is not None and not math.isnan(service_threshold):
        ax_fill.axhline(service_threshold, color="#dc2626", linestyle="--", linewidth=1.2)
    ax_fill.axvline(1.0, color="#64748b", linestyle=":", linewidth=1.1)
    if base_fill is not None:
        ax_fill.axhline(base_fill, color="#0f766e", linestyle=":", linewidth=1.0)
    ax_fill.set_ylabel("Disponibilite produit")
    ax_fill.set_title(f"{parameter_label} - disponibilite produit", fontsize=12, pad=10)
    ax_fill.grid(True, color="#e2e8f0", linewidth=0.9)
    ax_fill.set_facecolor("#ffffff")

    ax_backlog = incoming_axes[1]
    ax_backlog.plot(x, backlog, color="#d97706", marker="o", linewidth=2.2)
    ax_backlog.axvline(1.0, color="#64748b", linestyle=":", linewidth=1.1)
    if base_backlog is not None:
        ax_backlog.axhline(base_backlog, color="#0f766e", linestyle=":", linewidth=1.0)
    ax_backlog.set_ylabel("Backlog")
    ax_backlog.set_xlabel("Niveau du parametre")
    ax_backlog.set_xticks(x)
    ax_backlog.set_xticklabels([format_level(v) for v in x], rotation=0)
    ax_backlog.set_title(f"{parameter_label} - backlog final", fontsize=11, pad=8)
    ax_backlog.grid(True, color="#e2e8f0", linewidth=0.9)
    ax_backlog.set_facecolor("#ffffff")
    incoming_fig.tight_layout()
    incoming_buf = io.BytesIO()
    incoming_fig.savefig(incoming_buf, format="png", dpi=150, bbox_inches="tight")
    plt.close(incoming_fig)
    incoming_payload = png_payload_from_bytes(incoming_buf.getvalue(), filename.replace(".png", "_service.png"))

    outgoing_fig, outgoing_axes = plt.subplots(2, 1, figsize=(9.2, 7.0), sharex=True)
    outgoing_fig.patch.set_facecolor("#ffffff")
    ax_cost = outgoing_axes[0]
    ax_cost.plot(x, total_cost, color="#7c3aed", marker="o", linewidth=2.2)
    ax_cost.axvline(1.0, color="#64748b", linestyle=":", linewidth=1.1)
    if base_cost is not None:
        ax_cost.axhline(base_cost, color="#0f766e", linestyle=":", linewidth=1.0)
    ax_cost.set_ylabel("Cout total")
    ax_cost.set_title(f"{parameter_label} - cout", fontsize=12, pad=10)
    ax_cost.grid(True, color="#e2e8f0", linewidth=0.9)
    ax_cost.set_facecolor("#ffffff")

    ax_inv = outgoing_axes[1]
    ax_inv.plot(x, avg_inventory, color="#0f766e", marker="o", linewidth=2.2)
    ax_inv.axvline(1.0, color="#64748b", linestyle=":", linewidth=1.1)
    if base_inventory is not None:
        ax_inv.axhline(base_inventory, color="#2563eb", linestyle=":", linewidth=1.0)
    ax_inv.set_ylabel("Inventaire moyen")
    ax_inv.set_xlabel("Niveau du parametre")
    ax_inv.set_xticks(x)
    ax_inv.set_xticklabels([format_level(v) for v in x], rotation=0)
    ax_inv.set_title(f"{parameter_label} - inventaire", fontsize=11, pad=8)
    ax_inv.grid(True, color="#e2e8f0", linewidth=0.9)
    ax_inv.set_facecolor("#ffffff")
    outgoing_fig.tight_layout()
    outgoing_buf = io.BytesIO()
    outgoing_fig.savefig(outgoing_buf, format="png", dpi=150, bbox_inches="tight")
    plt.close(outgoing_fig)
    outgoing_payload = png_payload_from_bytes(outgoing_buf.getvalue(), filename.replace(".png", "_economic.png"))

    return incoming_payload, outgoing_payload


def read_supplier_case_metrics(
    case_output_dir: Path,
    node_id: str,
    cache: dict[tuple[str, str], dict[str, float]],
) -> dict[str, float]:
    cache_key = (str(case_output_dir), node_id)
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    data_dir = case_output_dir / "data"
    shipped_total = 0.0
    stock_values: list[float] = []
    util_values: list[float] = []

    shipments_csv = data_dir / "production_supplier_shipments_daily.csv"
    if shipments_csv.exists():
        try:
            for row in read_csv_rows(shipments_csv):
                if str(row.get("src_node_id") or "") != node_id:
                    continue
                shipped_total += float(to_float(row.get("shipped_qty")) or 0.0)
        except Exception:
            shipped_total = 0.0

    stocks_csv = data_dir / "production_supplier_stocks_daily.csv"
    if stocks_csv.exists():
        try:
            for row in read_csv_rows(stocks_csv):
                if str(row.get("node_id") or "") != node_id:
                    continue
                stock_values.append(float(to_float(row.get("stock_end_of_day")) or 0.0))
        except Exception:
            stock_values = []

    capacity_csv = data_dir / "production_supplier_capacity_daily.csv"
    if capacity_csv.exists():
        try:
            for row in read_csv_rows(capacity_csv):
                if str(row.get("node_id") or "") != node_id:
                    continue
                util_values.append(float(to_float(row.get("utilization")) or 0.0))
        except Exception:
            util_values = []

    metrics = {
        "total_shipped": shipped_total,
        "avg_stock": (sum(stock_values) / len(stock_values)) if stock_values else 0.0,
        "ending_stock": stock_values[-1] if stock_values else 0.0,
        "avg_utilization": (sum(util_values) / len(util_values)) if util_values else 0.0,
    }
    cache[cache_key] = metrics
    return metrics


def build_supplier_threshold_metric_curve_payload(
    parameter_rows: list[dict[str, str]],
    *,
    node_id: str,
    parameter_label: str,
    filename: str,
    metrics_cache: dict[tuple[str, str], dict[str, float]],
    baseline_production_planning_line_count: float | None = None,
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    usable_rows = []
    for row in parameter_rows:
        level = to_float(row.get("level"))
        case_output_dir = str(row.get("case_output_dir") or "").strip()
        if level is None or math.isnan(level) or not case_output_dir:
            continue
        usable_rows.append((float(level), row, Path(case_output_dir)))
    usable_rows.sort(key=lambda item: item[0])
    if len(usable_rows) < 2:
        return None, None

    def format_parameter_level(value: float) -> str:
        percent = value * 100.0
        raw = f"{percent:.0f}%" if abs(percent - round(percent)) <= 1e-9 else f"{percent:.1f}%"
        return f"{raw} ref." if abs(value - 1.0) <= 1e-9 else raw

    x = [format_parameter_level(level) for level, _, _ in usable_rows]
    shipped = []
    avg_stock = []
    ending_stock = []
    avg_utilization = []
    availability = []
    replanning_rate = []
    inventory_cost = []
    for _, row, case_output_dir in usable_rows:
        metrics = read_supplier_case_metrics(case_output_dir, node_id, metrics_cache)
        shipped.append(float(metrics.get("total_shipped") or 0.0))
        avg_stock.append(float(metrics.get("avg_stock") or 0.0))
        ending_stock.append(float(metrics.get("ending_stock") or 0.0))
        avg_utilization.append(float(metrics.get("avg_utilization") or 0.0))
        availability.append(sensitivity_availability_percent(row))
        replanning_rate.append(
            sensitivity_replanning_rate_percent(
                row,
                baseline_production_planning_line_count=baseline_production_planning_line_count,
            )
        )
        inventory_cost.append(
            float(to_float(row.get("kpi::inventory_cost")) or to_float(row.get("kpi::total_holding_cost")) or 0.0)
        )
    has_replanning_rate = any(value is not None for value in replanning_rate)

    incoming_payload = {
        "figure": {
            "kind": "dual_panel",
            "x_axis_kind": "parameter_sweep",
            "title": f"{parameter_label} - impact KPI par niveau teste",
                "show_legend": True,
                "top": {
                    "kind": "line",
                    "title": "Disponibilite produit",
                    "x_label": "Niveau teste du parametre (100% = reference active)",
                    "y_label": "Disponibilite produit (%)",
                    "y_unit": "percent",
                "x": x,
                "y": availability,
            },
                "bottom": {
                    "kind": "line",
                    "title": "Taux de replanification production" if has_replanning_rate else "Taux de replanification production - non calcule dans cette etude",
                    "x_label": "Niveau teste du parametre (100% = reference active)",
                    "y_label": "Taux de replanification (%)",
                    "y_unit": "percent",
                "x": x,
                "y": replanning_rate,
            },
        }
    }
    outgoing_payload = {
        "figure": {
            "kind": "dual_panel",
            "x_axis_kind": "parameter_sweep",
            "title": f"{parameter_label} - cout et detail fournisseur par niveau teste",
                "show_legend": True,
                "top": {
                    "kind": "line",
                    "title": "Cout de stockage",
                    "x_label": "Niveau teste du parametre (100% = reference active)",
                    "y_label": "Cout",
                "x": x,
                "y": inventory_cost,
                },
                "bottom": {
                    "kind": "line",
                    "title": "Stock fournisseur",
                    "x_label": "Niveau teste du parametre (100% = reference active)",
                    "y_label": "Quantite",
                "x": x,
                "y": avg_stock,
                "extra_traces": [
                    {
                        "type": "scatter",
                        "mode": "lines+markers",
                        "name": "Stock final fournisseur",
                        "x": x,
                        "y": ending_stock,
                        "line": {"width": 1.8, "color": "#d97706", "dash": "dot"},
                        "marker": {"size": 5, "color": "#d97706"},
                    },
                    {
                        "type": "scatter",
                        "mode": "lines+markers",
                        "name": "Expedie total fournisseur",
                        "x": x,
                        "y": shipped,
                        "line": {"width": 1.8, "color": "#64748b", "dash": "dot"},
                        "marker": {"size": 5, "color": "#64748b"},
                    },
                ],
            },
        }
    }
    return incoming_payload, outgoing_payload

    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt  # type: ignore
    except Exception:
        return None, None

    x = [level for level, _, _ in usable_rows]
    shipped = []
    avg_stock = []
    ending_stock = []
    avg_utilization = []
    for _, _, case_output_dir in usable_rows:
        metrics = read_supplier_case_metrics(case_output_dir, node_id, metrics_cache)
        shipped.append(float(metrics.get("total_shipped") or 0.0))
        avg_stock.append(float(metrics.get("avg_stock") or 0.0))
        ending_stock.append(float(metrics.get("ending_stock") or 0.0))
        avg_utilization.append(float(metrics.get("avg_utilization") or 0.0))

    def format_level(value: float) -> str:
        percent = value * 100.0
        return f"{percent:.0f}%" if abs(percent - round(percent)) <= 1e-9 else f"{percent:.1f}%"

    incoming_fig, incoming_axes = plt.subplots(2, 1, figsize=(9.2, 7.0), sharex=True)
    incoming_fig.patch.set_facecolor("#ffffff")

    ax_ship = incoming_axes[0]
    ax_ship.plot(x, shipped, color="#2563eb", marker="o", linewidth=2.2)
    ax_ship.axvline(1.0, color="#64748b", linestyle=":", linewidth=1.1)
    ax_ship.set_ylabel("Expedie total")
    ax_ship.set_title(f"{parameter_label} - flux fournisseur", fontsize=12, pad=10)
    ax_ship.grid(True, color="#e2e8f0", linewidth=0.9)
    ax_ship.set_facecolor("#ffffff")

    ax_avg_stock = incoming_axes[1]
    ax_avg_stock.plot(x, avg_stock, color="#0f766e", marker="o", linewidth=2.2)
    ax_avg_stock.axvline(1.0, color="#64748b", linestyle=":", linewidth=1.1)
    ax_avg_stock.set_ylabel("Stock moyen")
    ax_avg_stock.set_xlabel("Niveau du parametre")
    ax_avg_stock.set_xticks(x)
    ax_avg_stock.set_xticklabels([format_level(v) for v in x], rotation=0)
    ax_avg_stock.set_title(f"{parameter_label} - stock moyen fournisseur", fontsize=11, pad=8)
    ax_avg_stock.grid(True, color="#e2e8f0", linewidth=0.9)
    ax_avg_stock.set_facecolor("#ffffff")
    incoming_fig.tight_layout()
    incoming_buf = io.BytesIO()
    incoming_fig.savefig(incoming_buf, format="png", dpi=150, bbox_inches="tight")
    plt.close(incoming_fig)
    incoming_payload = png_payload_from_bytes(
        incoming_buf.getvalue(),
        filename.replace(".png", "_supplier_local_flow.png"),
    )

    outgoing_fig, outgoing_axes = plt.subplots(2, 1, figsize=(9.2, 7.0), sharex=True)
    outgoing_fig.patch.set_facecolor("#ffffff")

    ax_util = outgoing_axes[0]
    ax_util.plot(x, avg_utilization, color="#7c3aed", marker="o", linewidth=2.2)
    ax_util.axvline(1.0, color="#64748b", linestyle=":", linewidth=1.1)
    ax_util.set_ylabel("Utilisation moy.")
    ax_util.set_title(f"{parameter_label} - utilisation capacite", fontsize=12, pad=10)
    ax_util.grid(True, color="#e2e8f0", linewidth=0.9)
    ax_util.set_facecolor("#ffffff")

    ax_end_stock = outgoing_axes[1]
    ax_end_stock.plot(x, ending_stock, color="#d97706", marker="o", linewidth=2.2)
    ax_end_stock.axvline(1.0, color="#64748b", linestyle=":", linewidth=1.1)
    ax_end_stock.set_ylabel("Stock final")
    ax_end_stock.set_xlabel("Niveau du parametre")
    ax_end_stock.set_xticks(x)
    ax_end_stock.set_xticklabels([format_level(v) for v in x], rotation=0)
    ax_end_stock.set_title(f"{parameter_label} - stock final fournisseur", fontsize=11, pad=8)
    ax_end_stock.grid(True, color="#e2e8f0", linewidth=0.9)
    ax_end_stock.set_facecolor("#ffffff")
    outgoing_fig.tight_layout()
    outgoing_buf = io.BytesIO()
    outgoing_fig.savefig(outgoing_buf, format="png", dpi=150, bbox_inches="tight")
    plt.close(outgoing_fig)
    outgoing_payload = png_payload_from_bytes(
        outgoing_buf.getvalue(),
        filename.replace(".png", "_supplier_local_state.png"),
    )

    return incoming_payload, outgoing_payload


def build_threshold_hover_payloads(
    raw: dict[str, Any],
    threshold_parameter_summary_csv: Path,
    threshold_sweep_cases_csv: Path,
    threshold_summary_json: Path,
    baseline_production_planning_line_count: float | None = None,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    summary_rows = read_csv_rows(threshold_parameter_summary_csv)
    case_rows = read_csv_rows(threshold_sweep_cases_csv)
    if not summary_rows or not case_rows:
        return {}, {}, {}

    try:
        summary = json.loads(threshold_summary_json.read_text(encoding="utf-8")) if threshold_summary_json.exists() else {}
    except Exception:
        summary = {}
    service_threshold = to_float(summary.get("service_threshold"))

    node_item_ids = build_node_item_ids(raw)
    node_types = build_node_type_lookup(raw)
    incoming_sources, outgoing_targets = build_node_relationships(raw)
    case_rows_by_param: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in case_rows:
        if str(row.get("status") or "").lower() != "ok":
            continue
        parameter_key = str(row.get("parameter_key") or "")
        if not parameter_key or parameter_key == "baseline":
            continue
        case_rows_by_param[parameter_key].append(row)

    factory_out: dict[str, Any] = {}
    supplier_out: dict[str, Any] = {}
    dc_out: dict[str, Any] = {}
    supplier_metrics_cache: dict[tuple[str, str], dict[str, float]] = {}

    for node in raw.get("nodes", []) or []:
        node_id = str(node.get("id") or "")
        node_type = str(node.get("type") or "")
        if node_type not in {"factory", "supplier_dc", "distribution_center"}:
            continue
        best_row = select_best_threshold_parameter_row(
            summary_rows,
            node_id,
            node_item_ids,
            node_types,
            incoming_sources,
            outgoing_targets,
        )
        if best_row is None:
            continue
        parameter_key = str(best_row.get("parameter_key") or "")
        parameter_label = str(best_row.get("parameter_label") or parameter_key)
        parameter_cases = case_rows_by_param.get(parameter_key, [])
        if node_type == "supplier_dc" and parameter_key.endswith(f"::{node_id}"):
            incoming, outgoing = build_supplier_threshold_metric_curve_payload(
                parameter_cases,
                node_id=node_id,
                parameter_label=parameter_label,
                filename=f"{safe_case_token(node_id)}_threshold.png",
                metrics_cache=supplier_metrics_cache,
                baseline_production_planning_line_count=baseline_production_planning_line_count,
            )
        else:
            incoming, outgoing = build_threshold_metric_curve_payload(
                parameter_cases,
                parameter_label=parameter_label,
                filename=f"{safe_case_token(node_id)}_threshold.png",
                service_threshold=service_threshold,
                baseline_production_planning_line_count=baseline_production_planning_line_count,
            )
        if not incoming and not outgoing:
            continue
        payload = {"incoming": incoming, "outgoing": outgoing}
        if node_type == "factory":
            factory_out[node_id] = payload
        elif node_type == "supplier_dc":
            supplier_out[node_id] = payload
        else:
            dc_out[node_id] = payload

    return factory_out, supplier_out, dc_out


def build_supplier_parameter_sensitivity_hover_payloads(
    raw: dict[str, Any],
    supplier_summary_json: Path,
    supplier_parameter_summary_csv: Path,
    supplier_parameter_cases_csv: Path,
    supplier_nominal_parameters_csv: Path | None = None,
    baseline_production_planning_line_count: float | None = None,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    summary_rows = read_csv_rows(supplier_parameter_summary_csv)
    case_rows = read_csv_rows(supplier_parameter_cases_csv)
    if not summary_rows:
        return {}, {}, {}, {}

    try:
        summary = json.loads(supplier_summary_json.read_text(encoding="utf-8")) if supplier_summary_json.exists() else {}
    except Exception:
        summary = {}

    node_item_ids = build_node_item_ids(raw)
    node_types = build_node_type_lookup(raw)
    incoming_sources, outgoing_targets = build_node_relationships(raw)
    service_threshold = to_float(summary.get("service_threshold"))
    selected_suppliers = [str(value) for value in (summary.get("selected_suppliers") or [])]
    baseline = summary.get("baseline") if isinstance(summary.get("baseline"), dict) else {}
    baseline_fill = to_float(baseline.get("kpi::fill_rate") or baseline.get("fill_rate"))
    baseline_backlog = to_float(baseline.get("kpi::ending_backlog") or baseline.get("ending_backlog"))
    baseline_cost = to_float(baseline.get("kpi::total_cost") or baseline.get("total_cost"))
    if baseline_fill is None:
        for row in case_rows:
            if str(row.get("case_id") or "") == "baseline":
                baseline_fill = to_float(row.get("kpi::fill_rate"))
                baseline_backlog = to_float(row.get("kpi::ending_backlog"))
                baseline_cost = to_float(row.get("kpi::total_cost"))
                break
    baseline_case_row = next((row for row in case_rows if str(row.get("case_id") or "") == "baseline"), {})
    baseline_holding_cost = (
        to_float(baseline_case_row.get("kpi::inventory_cost"))
        or to_float(baseline_case_row.get("kpi::total_holding_cost"))
        or to_float(baseline_case_row.get("kpi::inventory_holding_cost_proxy_total"))
    )

    case_rows_by_param: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in case_rows:
        if str(row.get("status") or "").lower() != "ok":
            continue
        parameter_key = str(row.get("parameter_key") or "")
        if not parameter_key or parameter_key == "baseline":
            continue
        case_rows_by_param[parameter_key].append(row)

    supplier_global_groups = {
        "supplier_capacity_global",
        "supplier_stock_global",
        "supplier_lead_time_global",
        "supplier_reliability_global",
        "supplier_upstream_supply",
        "supplier_combined_upstream_supply",
    }
    scope_order = {
        "direct": 0,
        "upstream_supplier_capacity": 1,
        "upstream_reliability": 2,
        "upstream_lead_time": 3,
        "upstream_supplier_stock": 4,
        "upstream_combined_capacity_delay": 5,
        "upstream_combined_stock_reliability": 6,
        "supplier_global": 7,
    }
    scope_labels = {
        "direct": "test direct sur ce noeud",
        "upstream_supplier_capacity": "fournisseur amont relie - capacite",
        "upstream_reliability": "fournisseur amont relie - fiabilite",
        "upstream_lead_time": "fournisseur amont relie - delai",
        "upstream_supplier_stock": "fournisseur amont relie - stock",
        "upstream_combined_capacity_delay": "fournisseur amont relie - capacite + delai",
        "upstream_combined_stock_reliability": "fournisseur amont relie - stock + fiabilite",
        "supplier_global": "tous les fournisseurs - test global",
    }

    def safe_float(value: Any) -> float | None:
        num = to_float(value)
        if num is None or math.isnan(num):
            return None
        return float(num)

    def fmt_factor(value: float | None, *, row: dict[str, str] | None = None) -> str:
        if value is None:
            return "n/a"
        percent = value * 100.0
        raw = f"{percent:.0f}%" if abs(percent - round(percent)) <= 1e-9 else f"{percent:.1f}%"
        if abs(value - 1.0) <= 1e-9:
            raw = f"{raw} ref."
        return raw

    def fmt_fill_value(value: float | None) -> str:
        if value is None:
            return "n/a"
        return f"{value * 100:.1f}%"

    def fmt_money_short(value: float | None) -> str:
        if value is None:
            return "n/a"
        abs_value = abs(value)
        if abs_value >= 1_000_000:
            return f"{value / 1_000_000:.2f} M"
        if abs_value >= 1_000:
            return f"{value / 1_000:.1f} k"
        return f"{value:.0f}"

    def jsonish(value: Any) -> Any:
        raw_value = str(value or "").strip()
        if not raw_value:
            return None
        try:
            return json.loads(raw_value)
        except Exception:
            return raw_value

    def fmt_levels(value: Any, row: dict[str, str] | None = None) -> str:
        parsed = jsonish(value)
        if isinstance(parsed, list):
            values: list[str] = []
            for item in parsed:
                if isinstance(item, list) and len(item) == 2:
                    low = safe_float(item[0])
                    high = safe_float(item[1])
                    values.append(f"{fmt_factor(low, row=row)} -> {fmt_factor(high, row=row)}")
                else:
                    values.append(fmt_factor(safe_float(item), row=row))
            return ", ".join(values) if values else "n/a"
        return str(parsed or "n/a")

    def baseline_contiguous_band(row: dict[str, str]) -> str:
        low = safe_float(row.get("baseline_contiguous_safe_low"))
        high = safe_float(row.get("baseline_contiguous_safe_high"))
        if low is None and high is None:
            low = safe_float(row.get("safe_band_low"))
            high = safe_float(row.get("safe_band_high"))
        if low is None and high is None:
            return "aucune plage continue"
        if low is None:
            return f"<= {fmt_factor(high, row=row)}"
        if high is None:
            return f">= {fmt_factor(low, row=row)}"
        return f"{fmt_factor(low, row=row)} a {fmt_factor(high, row=row)}"

    def first_unacceptable(row: dict[str, str]) -> str:
        value = safe_float(row.get("first_unacceptable_level"))
        return fmt_factor(value, row=row) if value is not None else "aucun dans la grille"

    def bool_text(value: Any) -> bool:
        return str(value).strip().lower() in {"1", "true", "yes", "y"}

    def driver_text(row: dict[str, str]) -> str:
        fill_drop = safe_float(row.get("max_fill_rate_drop")) or 0.0
        availability_drop = safe_float(row.get("max_product_availability_drop")) or 0.0
        adherence_drop = safe_float(row.get("max_line_adherence_drop")) or 0.0
        nervousness_delta = safe_float(row.get("max_line_nervousness_increase")) or 0.0
        replanning_delta = safe_float(row.get("max_production_replanning_count_increase")) or 0.0
        replanning_rate_delta = safe_float(row.get("max_production_replanning_rate_increase")) or 0.0
        material_delay = safe_float(row.get("max_material_delay_days_increase")) or 0.0
        target_gap = safe_float(row.get("max_raw_material_target_gap_increase")) or 0.0
        safety_gap = safe_float(row.get("max_raw_material_safety_floor_gap_increase")) or 0.0
        upstream_delta = safe_float(row.get("max_supplier_upstream_ordered_qty_delta"))
        if upstream_delta is None:
            upstream_delta = safe_float(row.get("max_external_procured_qty_delta")) or 0.0
        inventory_delta = safe_float(row.get("max_inventory_cost_increase")) or 0.0
        cost_delta = safe_float(row.get("max_total_cost_increase")) or 0.0
        parts: list[str] = []
        if fill_drop > 1e-9:
            parts.append(f"disponibilite -{fill_drop * 100:.1f} pts max")
        if availability_drop > 1e-9:
            parts.append(f"dispo -{availability_drop * 100:.1f} pts max")
        if adherence_drop > 1e-9:
            parts.append(f"adherence -{adherence_drop * 100:.1f} pts max")
        if replanning_rate_delta > 1e-9 or replanning_delta > 1e-9 or nervousness_delta > 1e-9:
            planning_parts: list[str] = []
            if replanning_rate_delta > 1e-9:
                planning_parts.append(f"taux replanification +{replanning_rate_delta * 100:.1f} pts")
            if nervousness_delta > 1e-9:
                planning_parts.append(f"amplitude +{nervousness_delta:.0f} pts")
            if replanning_delta > 1e-9:
                planning_parts.append(f"volume associe +{replanning_delta:.0f} lignes")
            parts.append(f"replanification ({' ; '.join(planning_parts)})")
        if material_delay > 1e-9:
            parts.append(f"retard matiere max +{material_delay:.0f} j")
        if target_gap > 1e-6:
            parts.append(f"gap cible stock +{fmt_qty(target_gap, 0)}")
        if safety_gap > 1e-6:
            parts.append(f"gap safety +{fmt_qty(safety_gap, 0)}")
        if upstream_delta > 1e-6:
            parts.append(f"appro amont +{fmt_qty(upstream_delta, 0)}")
        if inventory_delta > 1e-6:
            parts.append(f"stockage +{fmt_money_short(inventory_delta)}")
        if cost_delta > 1e-6:
            parts.append(f"cout +{fmt_money_short(cost_delta)}")
        if not parts:
            parts.append("pas de degradation forte dans la grille")
        if not bool_text(row.get("acceptable_is_contiguous")):
            parts.append("lecture irreguliere")
        return " ; ".join(parts)

    def metric_values_for_row(row: dict[str, str], metric_name: str) -> list[float]:
        values: list[float] = []
        for case_row in case_rows_by_param.get(str(row.get("parameter_key") or ""), []):
            value = safe_float(case_row.get(metric_name))
            if value is not None:
                values.append(value)
        return values

    def metric_min_label(row: dict[str, str], metric_name: str, *, kind: str = "qty") -> str:
        values = metric_values_for_row(row, metric_name)
        if not values:
            return "n/a"
        value = min(values)
        if kind == "pct_fraction":
            return fmt_fill_value(value)
        if kind == "money":
            return fmt_money_short(value)
        return fmt_qty(value, 0)

    def metric_min_label_any(row: dict[str, str], metric_names: list[str], *, kind: str = "qty") -> str:
        for metric_name in metric_names:
            label = metric_min_label(row, metric_name, kind=kind)
            if label != "n/a":
                return label
        return "n/a"

    def metric_max_label_any(row: dict[str, str], metric_names: list[str], *, kind: str = "qty") -> str:
        for metric_name in metric_names:
            label = metric_max_label(row, metric_name, kind=kind)
            if label != "n/a":
                return label
        return "n/a"

    def metric_max_label(row: dict[str, str], metric_name: str, *, kind: str = "qty") -> str:
        values = metric_values_for_row(row, metric_name)
        if not values:
            return "n/a"
        value = max(values)
        if kind == "pct_fraction":
            return fmt_fill_value(value)
        if kind == "money":
            return fmt_money_short(value)
        return fmt_qty(value, 0)

    def holding_cost_delta_label(row: dict[str, str]) -> str:
        values = metric_values_for_row(row, "kpi::inventory_cost")
        if not values:
            values = metric_values_for_row(row, "kpi::total_holding_cost")
        if not values:
            values = metric_values_for_row(row, "kpi::inventory_holding_cost_proxy_total")
        if not values:
            return "n/a"
        max_value = max(values)
        if baseline_holding_cost is None:
            return fmt_money_short(max_value)
        return f"{fmt_money_short(max_value)} ({fmt_money_short(max_value - baseline_holding_cost)} vs baseline)"

    def derived_replanning_rate_from_count(count: float | None) -> float | None:
        if count is None or math.isnan(count):
            return None
        denominator = baseline_production_planning_line_count
        if denominator is None or denominator <= 0:
            return None
        return count / denominator

    def baseline_replanning_rate_label(row: dict[str, str], parameter_key: str) -> str:
        rate = safe_float(row.get("baseline_production_replanning_rate"))
        if rate is not None:
            return fmt_fill_value(rate)
        baseline_count = (
            safe_float(row.get("baseline_production_replanning_count"))
            or safe_float(baseline.get("kpi::production_replanning_count"))
            or safe_float(baseline.get("production_replanning_count"))
            or safe_float(baseline_case_row.get("kpi::production_replanning_count"))
            or safe_float(baseline_case_row.get("production_replanning_count"))
        )
        if baseline_count is None:
            for case_row in case_rows_by_param.get(parameter_key, []):
                level = safe_float(case_row.get("level"))
                if level is not None and abs(level - 1.0) <= 1e-9:
                    baseline_count = (
                        safe_float(case_row.get("kpi::production_replanning_count"))
                        or safe_float(case_row.get("production_replanning_count"))
                    )
                    break
        derived_rate = derived_replanning_rate_from_count(baseline_count)
        if derived_rate is None:
            return "n/a"
        return f"{fmt_fill_value(derived_rate)} derive"

    def replanning_rate_label(row: dict[str, str]) -> str:
        rate = safe_float(row.get("production_replanning_rate_max"))
        if rate is None:
            label = metric_max_label_any(row, ["kpi::production_replanning_rate"], kind="pct_fraction")
            if label != "n/a":
                return label
            count = safe_float(row.get("production_replanning_count_max"))
            if count is None:
                values = metric_values_for_row(row, "kpi::production_replanning_count")
                count = max(values) if values else None
            derived_rate = derived_replanning_rate_from_count(count)
            if derived_rate is not None:
                return f"{fmt_fill_value(derived_rate)} derive"
            return "n/a"
        return fmt_fill_value(rate)

    def replanning_delta_label(row: dict[str, str]) -> str:
        rate_delta = safe_float(row.get("max_production_replanning_rate_increase"))
        count_delta = safe_float(row.get("max_production_replanning_count_increase"))
        if rate_delta is not None and not math.isnan(rate_delta):
            count_suffix = (
                f" ; volume associe +{fmt_qty(count_delta, 0)} lignes"
                if count_delta is not None and not math.isnan(count_delta)
                else ""
            )
            return f"+{rate_delta * 100:.1f} pts{count_suffix}"
        if count_delta is not None and not math.isnan(count_delta):
            derived_delta = derived_replanning_rate_from_count(count_delta)
            if derived_delta is not None:
                return f"+{derived_delta * 100:.2f} pts derive ; volume associe +{fmt_qty(count_delta, 0)} lignes"
            return f"taux n/a ; volume associe +{fmt_qty(count_delta, 0)} lignes"
        return "n/a"

    def line_adherence_label(row: dict[str, str]) -> str:
        return metric_min_label(row, "kpi::line_adherence", kind="pct_fraction")

    def driver_family(row: dict[str, str]) -> str:
        group = str(row.get("parameter_group") or "")
        if "combined" in group:
            return "combined"
        if "capacity" in group:
            return "capacity"
        if "stock" in group:
            return "stock"
        if "lead" in group:
            return "lead_time"
        if "reliability" in group:
            return "reliability"
        if "upstream" in group:
            return "upstream_supply"
        return "other"

    driver_family_labels = {
        "capacity": "Capacite",
        "stock": "Stock",
        "lead_time": "Delai",
        "reliability": "Fiabilite",
        "upstream_supply": "Appro amont",
        "combined": "Scenario combine",
        "other": "Autre",
    }
    driver_family_colors = {
        "capacity": "#d97706",
        "stock": "#0f766e",
        "lead_time": "#7c3aed",
        "reliability": "#2563eb",
        "upstream_supply": "#be123c",
        "combined": "#475569",
        "other": "#64748b",
    }

    def status_for_row(row: dict[str, str], *, locally_tested: bool) -> tuple[str, str]:
        if not locally_tested:
            return "not_local", "Non teste localement"
        fill_drop = safe_float(row.get("max_fill_rate_drop")) or 0.0
        availability_drop = safe_float(row.get("max_product_availability_drop")) or 0.0
        adherence_drop = safe_float(row.get("max_line_adherence_drop")) or 0.0
        nervousness_delta = safe_float(row.get("max_line_nervousness_increase")) or 0.0
        replanning_delta = safe_float(row.get("max_production_replanning_count_increase")) or 0.0
        replanning_rate_delta = safe_float(row.get("max_production_replanning_rate_increase")) or 0.0
        target_gap = safe_float(row.get("max_raw_material_target_gap_increase")) or 0.0
        upstream_delta = safe_float(row.get("max_supplier_upstream_ordered_qty_delta"))
        if upstream_delta is None:
            upstream_delta = safe_float(row.get("max_external_procured_qty_delta")) or 0.0
        material_delay = safe_float(row.get("max_material_delay_days_increase")) or 0.0
        inventory_delta = safe_float(row.get("max_inventory_cost_increase")) or 0.0
        cost_delta = safe_float(row.get("max_total_cost_increase")) or 0.0
        first_bad = safe_float(row.get("first_unacceptable_level"))
        contiguous = bool_text(row.get("acceptable_is_contiguous"))
        low = safe_float(row.get("baseline_contiguous_safe_low"))
        high = safe_float(row.get("baseline_contiguous_safe_high"))
        only_nominal = (
            low is not None
            and high is not None
            and abs(low - 1.0) <= 1e-9
            and abs(high - 1.0) <= 1e-9
        )
        if fill_drop >= 0.02 or availability_drop >= 0.02 or adherence_drop >= 0.02:
            return "sensitive", "Sensible"
        if (
            only_nominal
            or not contiguous
            or (first_bad is not None and abs(first_bad - 1.0) <= 0.25)
            or nervousness_delta > 0.0
            or replanning_delta > 0.0
            or replanning_rate_delta > 0.0
            or target_gap > 1e-6
            or material_delay > 0.0
            or upstream_delta > 5_000_000
            or inventory_delta > 500_000
            or cost_delta > 500_000
        ):
            return "watch", "A surveiller"
        return "robust", "Robuste"

    status_colors = {
        "robust": "#16a34a",
        "watch": "#d97706",
        "sensitive": "#dc2626",
        "not_local": "#64748b",
    }

    def matrix_status_for_row(row: dict[str, str] | None) -> tuple[str, str]:
        if row is None:
            return "not_local", "Non teste"
        key, label = status_for_row(row, locally_tested=True)
        return key, label

    def recommendation_text(row: dict[str, str]) -> str:
        direction = str(row.get("safe_direction") or "").strip()
        band = baseline_contiguous_band(row)
        parameter_group = str(row.get("parameter_group") or "")
        if "capacity" in parameter_group:
            base = f"Capacite: garder au moins {band} tant que les autres hypotheses restent identiques."
        elif "stock" in parameter_group:
            base = f"Stock: utiliser {band} comme limite conservative, puis raffiner par item si besoin."
        elif "lead" in parameter_group:
            base = f"Delai: eviter de sortir de {band}; au-dela, les garde-fous amont/cout se degradent."
        elif "reliability" in parameter_group:
            base = f"Fiabilite: rester dans {band}; une baisse peut creer une contrainte amont meme sans rupture disponibilite."
        elif "upstream" in parameter_group:
            base = f"Appro amont fournisseur: garder {band} comme zone de reference testee."
        elif "combined" in parameter_group:
            base = f"Scenario combine: lire ce test comme une variation simultanee; acceptable seulement si {band} reste valide."
        elif direction == "higher_is_riskier":
            base = f"Ne pas depasser {band} sans retest."
        else:
            base = f"Ne pas descendre sous {band} sans retest."
        if not bool_text(row.get("acceptable_is_contiguous")):
            base += " La reponse est irreguliere: ne pas interpreter les ilots acceptables comme une vraie marge robuste."
        return base

    def supplier_global_scope(row: dict[str, str]) -> str | None:
        parameter_group = str(row.get("parameter_group") or "")
        parameter_key = str(row.get("parameter_key") or "")
        if parameter_group in supplier_global_groups and "::" not in parameter_key:
            return "supplier_global"
        return None

    def node_row_scope(row: dict[str, str], node_id: str, node_type: str) -> str | None:
        scope = sensitivity_row_scope(
            str(row.get("parameter_key") or ""),
            node_id,
            node_item_ids,
            node_types,
            incoming_sources,
            outgoing_targets,
        )
        if scope:
            return scope
        if node_type in {"supplier_dc", "factory", "distribution_center"}:
            return supplier_global_scope(row)
        return None

    def row_severity(row: dict[str, str]) -> float:
        fill_drop = safe_float(row.get("max_fill_rate_drop")) or 0.0
        availability_drop = safe_float(row.get("max_product_availability_drop")) or 0.0
        adherence_drop = safe_float(row.get("max_line_adherence_drop")) or 0.0
        nervousness_delta = safe_float(row.get("max_line_nervousness_increase")) or 0.0
        replanning_delta = safe_float(row.get("max_production_replanning_count_increase")) or 0.0
        replanning_rate_delta = safe_float(row.get("max_production_replanning_rate_increase")) or 0.0
        target_gap = safe_float(row.get("max_raw_material_target_gap_increase")) or 0.0
        safety_gap = safe_float(row.get("max_raw_material_safety_floor_gap_increase")) or 0.0
        upstream_delta = safe_float(row.get("max_supplier_upstream_ordered_qty_delta"))
        if upstream_delta is None:
            upstream_delta = safe_float(row.get("max_external_procured_qty_delta")) or 0.0
        material_delay = safe_float(row.get("max_material_delay_days_increase")) or 0.0
        inventory_delta = safe_float(row.get("max_inventory_cost_increase")) or 0.0
        cost_delta = safe_float(row.get("max_total_cost_increase")) or 0.0
        first_bad = safe_float(row.get("first_unacceptable_level"))
        proximity = 0.0 if first_bad is None else max(0.0, 1.0 - abs(first_bad - 1.0))
        non_contiguous = 0.5 if not bool_text(row.get("acceptable_is_contiguous")) else 0.0
        replanning_score = (
            min(replanning_rate_delta * 140.0, 35.0)
            if replanning_rate_delta > 1e-12
            else min(replanning_delta / 100.0, 10.0)
        )
        return (
            fill_drop * 100.0
            + availability_drop * 120.0
            + adherence_drop * 100.0
            + min(nervousness_delta / 10.0, 30.0)
            + replanning_score
            + min(target_gap / 1_000_000.0, 80.0)
            + min(safety_gap / 1_000_000.0, 40.0)
            + min(upstream_delta / 10_000_000.0, 40.0)
            + min(material_delay * 3.0, 40.0)
            + min(inventory_delta / 250_000.0, 20.0)
            + min(cost_delta / 250_000.0, 20.0)
            + proximity
            + non_contiguous
        )

    def sensitivity_row_tooltip(row: dict[str, str], scope: str | None = None) -> str:
        label = str(row.get("parameter_label") or row.get("parameter_key") or "n/a")
        family = driver_family_labels.get(driver_family(row), driver_family(row))
        scope_text = scope_labels.get(scope or "", scope or "n/a")
        severity = row_severity(row)
        fill_drop = safe_float(row.get("max_fill_rate_drop")) or 0.0
        availability_drop = safe_float(row.get("max_product_availability_drop")) or 0.0
        adherence_drop = safe_float(row.get("max_line_adherence_drop")) or 0.0
        nervousness_delta = safe_float(row.get("max_line_nervousness_increase")) or 0.0
        replanning_delta = safe_float(row.get("max_production_replanning_count_increase")) or 0.0
        replanning_rate_delta = safe_float(row.get("max_production_replanning_rate_increase")) or 0.0
        target_gap = safe_float(row.get("max_raw_material_target_gap_increase")) or 0.0
        material_delay = safe_float(row.get("max_material_delay_days_increase")) or 0.0
        stockout_days = safe_float(row.get("max_raw_material_stockout_days_increase")) or 0.0
        inventory_delta = safe_float(row.get("max_inventory_cost_increase")) or 0.0
        upstream_delta = safe_float(row.get("max_supplier_upstream_ordered_qty_delta"))
        if upstream_delta is None:
            upstream_delta = safe_float(row.get("max_external_procured_qty_delta")) or 0.0
        return "\n".join(
            [
                "Formule",
                "lecture sensibilite = grille de tests du parametre + garde-fous KPI",
                "",
                "Parametre",
                f"{label} ({family})",
                f"Perimetre = {scope_text}",
                "",
                "Calcul ici",
                f"Zone acceptable autour de 100% = {baseline_contiguous_band(row)}",
                f"Premier niveau degrade = {first_unacceptable(row)}",
                f"Disponibilite produit min = {metric_min_label_any(row, ['kpi::product_availability', 'kpi::fill_rate'], kind='pct_fraction')} ; baisse max = {fmt_fill_value(max(availability_drop, fill_drop))}",
                f"Taux replanification max = {replanning_rate_label(row)} ; variation = {replanning_delta_label(row)}",
                f"Signal technique adherence = {line_adherence_label(row)} ; nervosite +{fmt_qty(nervousness_delta, 0)} pts ; volume replanifie +{fmt_qty(replanning_delta, 0)} lignes",
                f"Retard matiere = +{fmt_qty(material_delay, 0)} j",
                f"Gap cible stock = {fmt_qty(target_gap, 0)} ; appro amont delta = {fmt_qty(upstream_delta, 0)}",
                f"Cout stockage max = {holding_cost_delta_label(row)} ; delta = {fmt_money_short(inventory_delta)}",
                f"Score de tri interne = {fmt_qty(severity, 1)}",
                "",
                "Signal technique non decisionnel",
                f"Signal MP usine zero = +{fmt_qty(stockout_days, 0)} jours vs baseline",
                "Compteur de jours ou au moins une MP suivie finit a zero dans les stocks usine. Ce n'est pas une duree de rupture fournisseur/usine et ce score ne pilote plus le statut Sensibilite.",
                "",
                "Lecture",
                driver_text(row),
                "Ce seuil vient d'une grille de simulation, pas d'une donnee fournisseur reelle.",
            ]
        )

    def sorted_relevant_rows(node_id: str, node_type: str) -> list[tuple[str, dict[str, str]]]:
        scoped: list[tuple[str, dict[str, str]]] = []
        for row in summary_rows:
            scope = node_row_scope(row, node_id, node_type)
            if scope:
                scoped.append((scope, row))
        scoped.sort(
            key=lambda item: (
                -row_severity(item[1]),
                scope_order.get(item[0], 9),
                str(item[1].get("parameter_label") or ""),
            )
        )
        return scoped

    def summary_table(scoped_rows: list[tuple[str, dict[str, str]]], limit: int = 8) -> str:
        rows = []
        for scope, row in scoped_rows[:limit]:
            rows.append(
                [
                    str(row.get("parameter_label") or row.get("parameter_key") or "n/a"),
                    scope_labels.get(scope, scope),
                    baseline_contiguous_band(row),
                    first_unacceptable(row),
                    metric_min_label_any(row, ["kpi::product_availability", "kpi::fill_rate"], kind="pct_fraction"),
                    replanning_rate_label(row),
                    holding_cost_delta_label(row),
                    driver_text(row),
                ]
            )
        return render_data_table(
            [
                "Parametre",
                "Perimetre du test",
                "Zone acceptable autour de la reference",
                "Premier niveau ou ca se degrade",
                "Disponibilite produit min",
                "Taux replanification max",
                "Cout stockage max",
                "Lecture metier",
            ],
            rows,
        )

    def detail_table(scoped_rows: list[tuple[str, dict[str, str]]]) -> str:
        rows = []
        for scope, row in scoped_rows:
            rows.append(
                [
                    str(row.get("parameter_label") or row.get("parameter_key") or "n/a"),
                    scope_labels.get(scope, scope),
                    fmt_levels(row.get("levels"), row),
                    fmt_levels(row.get("acceptable_ranges"), row),
                    baseline_contiguous_band(row),
                    first_unacceptable(row),
                    metric_min_label_any(row, ["kpi::product_availability", "kpi::fill_rate"], kind="pct_fraction"),
                    replanning_rate_label(row),
                    replanning_delta_label(row),
                    line_adherence_label(row),
                    holding_cost_delta_label(row),
                    fmt_pct(max((safe_float(row.get("max_product_availability_drop")) or 0.0), (safe_float(row.get("max_fill_rate_drop")) or 0.0)) * 100.0, 1),
                    fmt_qty(
                        safe_float(row.get("max_supplier_upstream_ordered_qty_delta"))
                        if safe_float(row.get("max_supplier_upstream_ordered_qty_delta")) is not None
                        else safe_float(row.get("max_external_procured_qty_delta")),
                        0,
                    ),
                    fmt_qty(safe_float(row.get("max_raw_material_target_gap_increase")), 0),
                    "oui" if bool_text(row.get("acceptable_is_contiguous")) else "non",
                ]
            )
        return render_data_table(
            [
                "Parametre",
                "Perimetre du test",
                "Niveaux testes",
                "Plages acceptables",
                "Zone acceptable autour de la reference",
                "Premier niveau ou ca se degrade",
                "Disponibilite produit min",
                "Taux replanification max",
                "Variation replanification",
                "Signal technique adherence",
                "Cout stockage max",
                "Baisse disponibilite produit max",
                "Variation appro amont",
                "Variation ecart cible",
                "Lecture stable",
            ],
            rows,
        )

    def margin_pct_label(row: dict[str, str], key: str) -> str:
        value = safe_float(row.get(key))
        if value is None:
            return "-"
        return f"{value:.0f}%"

    def margin_table(scoped_rows: list[tuple[str, dict[str, str]]], limit: int = 8) -> str:
        rows = []
        for scope, row in scoped_rows[:limit]:
            rows.append(
                [
                    str(row.get("parameter_label") or row.get("parameter_key") or "n/a"),
                    scope_labels.get(scope, scope),
                    margin_pct_label(row, "capacity_reduction_margin_pct"),
                    margin_pct_label(row, "stock_reduction_margin_pct"),
                    margin_pct_label(row, "delay_increase_margin_pct"),
                    margin_pct_label(row, "reliability_reduction_margin_pct"),
                    margin_pct_label(row, "upstream_capacity_reduction_margin_pct"),
                    margin_pct_label(row, "upstream_delay_increase_margin_pct"),
                    metric_min_label_any(row, ["kpi::product_availability", "kpi::fill_rate"], kind="pct_fraction"),
                    replanning_rate_label(row),
                    holding_cost_delta_label(row),
                ]
            )
        return render_data_table(
            [
                "Parametre",
                "Perimetre du test",
                "Capacite - marge baisse",
                "Stock - marge baisse",
                "Delai - marge hausse",
                "Fiabilite - marge baisse",
                "Appro amont cap - marge baisse",
                "Appro amont delai - marge hausse",
                "Disponibilite produit min",
                "Taux replanification max",
                "Cout stockage max",
            ],
            rows,
        )

    def sensitivity_card_status(row: dict[str, str], metric: str) -> str:
        if metric == "service":
            if (safe_float(row.get("max_fill_rate_drop")) or 0.0) >= 0.02:
                return "sensitive"
            if (safe_float(row.get("max_fill_rate_drop")) or 0.0) > 1e-9:
                return "watch"
            return "robust"
        if metric == "availability":
            if (safe_float(row.get("max_product_availability_drop")) or 0.0) >= 0.02:
                return "sensitive"
            if (safe_float(row.get("max_product_availability_drop")) or 0.0) > 1e-9:
                return "watch"
            return "robust"
        if metric == "adherence":
            if (safe_float(row.get("max_line_adherence_drop")) or 0.0) >= 0.02:
                return "sensitive"
            if (safe_float(row.get("max_line_adherence_drop")) or 0.0) > 1e-9:
                return "watch"
            return "robust"
        if metric == "nervousness":
            delta = safe_float(row.get("max_line_nervousness_increase")) or 0.0
            if delta >= 50.0:
                return "sensitive"
            if delta > 0.0:
                return "watch"
            return "robust"
        if metric == "replanning":
            rate_delta = safe_float(row.get("max_production_replanning_rate_increase")) or 0.0
            count_delta = safe_float(row.get("max_production_replanning_count_increase")) or 0.0
            if rate_delta >= 0.02 or count_delta >= 50.0:
                return "sensitive"
            if rate_delta > 0.0 or count_delta > 0.0:
                return "watch"
            return "robust"
        if metric == "planning":
            nervousness_status = sensitivity_card_status(row, "nervousness")
            replanning_status = sensitivity_card_status(row, "replanning")
            if "sensitive" in {nervousness_status, replanning_status}:
                return "sensitive"
            if "watch" in {nervousness_status, replanning_status}:
                return "watch"
            return "robust"
        if metric == "stock":
            gap = safe_float(row.get("max_raw_material_target_gap_increase")) or 0.0
            if gap > 1e-6:
                return "watch"
            return "robust"
        if metric == "cost":
            delta = safe_float(row.get("max_inventory_cost_increase")) or 0.0
            if delta > 500_000:
                return "watch"
            return "robust"
        if metric == "upstream":
            delta = safe_float(row.get("max_supplier_upstream_ordered_qty_delta"))
            if delta is None:
                delta = safe_float(row.get("max_external_procured_qty_delta")) or 0.0
            if delta > 5_000_000:
                return "watch"
            return "robust"
        return "robust"

    def sensitivity_metric_card(title: str, value: str, note: str, status_key: str, tooltip: str | None = None) -> str:
        return "".join(
            [
                f"<div class=\"{html_tooltip_class(f'sensitivityMetricCard sensitivityStatus-{html.escape(status_key)}', tooltip)}\"{html_tooltip_attrs(tooltip)}>",
                f"<div class=\"sensitivityMetricLabel\">{html.escape(title)}</div>",
                f"<div class=\"sensitivityMetricValue\">{html.escape(value)}</div>",
                f"<div class=\"sensitivityMetricNote\">{html.escape(note)}</div>",
                "</div>",
            ]
        )

    def sensitivity_fact(label: str, value: str, tooltip: str | None = None) -> str:
        return "".join(
            [
                f"<div class=\"{html_tooltip_class('', tooltip)}\"{html_tooltip_attrs(tooltip)}>",
                f"<span>{html.escape(label)}</span>",
                f"<b>{html.escape(value)}</b>",
                "</div>",
            ]
        )

    def sensitivity_metric_tooltip(row: dict[str, str], title: str, formula: str, value: str, source: str) -> str:
        return "\n".join(
            [
                "Formule",
                formula,
                "",
                "Calcul ici",
                f"Valeur affichee = {value}",
                f"Source = {source}",
                f"Parametre teste = {row.get('parameter_label') or row.get('parameter_key') or 'n/a'}",
                f"Zone acceptable = {baseline_contiguous_band(row)}",
                f"Premier niveau degrade = {first_unacceptable(row)}",
                "",
                "Lecture",
                f"{title}: {driver_text(row)}",
            ]
        )

    def card_value_from_row(row: dict[str, str], row_key: str, fallback: str, *, kind: str = "pct_fraction") -> str:
        value = safe_float(row.get(row_key))
        if value is not None:
            if kind == "pct_fraction":
                return fmt_fill_value(value)
            if kind == "money":
                return fmt_money_short(value)
            return fmt_qty(value, 0)
        return fallback

    def planning_instability_value(row: dict[str, str]) -> str:
        rate = safe_float(row.get("production_replanning_rate_max"))
        replanning = safe_float(row.get("production_replanning_count_max"))
        if rate is None and replanning is None:
            return "n/a"
        if rate is not None:
            suffix = f" / {fmt_qty(replanning, 0)} lignes" if replanning is not None else ""
            return f"{fmt_fill_value(rate)}{suffix}"
        derived_rate = derived_replanning_rate_from_count(replanning)
        if derived_rate is not None:
            return f"{fmt_fill_value(derived_rate)} derive / {fmt_qty(replanning, 0)} lignes"
        return f"taux n/a ({fmt_qty(replanning, 0)} lignes)"

    def planning_instability_tooltip(row: dict[str, str], value: str) -> str:
        raw_rate = safe_float(row.get("production_replanning_rate_max"))
        raw_rate_delta = safe_float(row.get("max_production_replanning_rate_increase"))
        raw_replanning = safe_float(row.get("production_replanning_count_max"))
        derived_rate = derived_replanning_rate_from_count(raw_replanning)
        derived_rate_delta = derived_replanning_rate_from_count(
            safe_float(row.get("max_production_replanning_count_increase"))
        )
        rate = raw_rate or 0.0
        rate_delta = raw_rate_delta or 0.0
        nervousness = safe_float(row.get("line_nervousness_max")) or 0.0
        replanning = raw_replanning or 0.0
        nervousness_delta = safe_float(row.get("max_line_nervousness_increase")) or 0.0
        replanning_delta = safe_float(row.get("max_production_replanning_count_increase")) or 0.0
        if raw_rate is None and raw_replanning is None:
            return "\n".join(
                [
                    "Lecture metier",
                    "Le taux de replanification mesure la part des lignes de planning production qui ont ete reportees ou replanifiees dans la grille testee.",
                    "",
                    "Statut des donnees",
                    "Ce KPI n'est pas encore present dans les resultats de sensibilite utilises pour cette carte.",
                    "",
                    "Action",
                    "Regenerer l'etude de sensibilite avec le script a jour pour alimenter ce KPI sur les courbes et les cartes.",
                ]
            )
        if raw_rate is None and derived_rate is None:
            return "\n".join(
                [
                    "Lecture metier",
                    "Le KPI principal attendu est le taux de replanification: part des lignes de planning production reportees ou replanifiees.",
                    "",
                    "Statut des donnees",
                    "Cette ligne ne contient pas encore le taux. On affiche donc seulement le volume technique associe.",
                    "",
                    "Volume associe",
                    f"Maximum observe = {fmt_qty(replanning, 0)} lignes",
                    f"Augmentation vs reference = +{fmt_qty(replanning_delta, 0)} lignes",
                    "",
                    "Action",
                    "Regenerer l'etude de sensibilite avec production_replanning_rate pour comparer les scenarios en pourcentage.",
                ]
            )
        if raw_rate is None and derived_rate is not None:
            return "\n".join(
                [
                    "Lecture metier",
                    "Le KPI principal est le taux de replanification: part des lignes de planning production reportees ou replanifiees.",
                    "",
                    "Compatibilite donnees",
                    "Cette etude ancienne ne contient que le nombre de lignes. Le taux affiche est derive avec le denominateur du run nominal.",
                    "",
                    "KPI derive",
                    f"Taux max derive = {fmt_fill_value(derived_rate)}",
                    f"Variation derivee vs reference = +{(derived_rate_delta or 0.0) * 100:.2f} pts",
                    "",
                    "Volume associe",
                    f"Maximum observe = {fmt_qty(replanning, 0)} lignes",
                    f"Augmentation vs reference = +{fmt_qty(replanning_delta, 0)} lignes",
                    "",
                    "Valeur affichee",
                    f"{value}",
                ]
            )
        return "\n".join(
            [
                "Lecture metier",
                "Le taux de replanification mesure la part des lignes de planning production qui ont ete reportees ou replanifiees dans la grille testee.",
                "",
                "KPI principal",
                f"Taux max observe = {fmt_fill_value(rate)}",
                f"Variation vs reference = +{rate_delta * 100:.1f} pts",
                "",
                "Volume associe",
                f"Maximum observe = {fmt_qty(replanning, 0)} lignes",
                f"Augmentation vs reference = +{fmt_qty(replanning_delta, 0)} lignes",
                "",
                "Signal technique conserve en detail",
                f"Nervosite planning max = {fmt_qty(nervousness, 0)} ; variation +{fmt_qty(nervousness_delta, 0)} pts",
                "",
                "Valeur affichee",
                f"{value}",
                "",
                "Lecture",
                "C'est un KPI de stabilite industrielle: plus il monte, plus l'usine doit reorganiser son planning a cause des contraintes intrants ou fournisseurs.",
            ]
        )

    def sensitivity_dashboard_html(
        *,
        node_id: str,
        status_label: str,
        status_key: str,
        best_row: dict[str, str],
        best_scope: str,
        locally_tested: bool,
    ) -> str:
        family = driver_family(best_row)
        family_label = driver_family_labels.get(family, family)
        driver_label = str(best_row.get("parameter_label") or best_row.get("parameter_key") or "n/a")
        break_label = first_unacceptable(best_row)
        band = baseline_contiguous_band(best_row)
        scope_note = "test local" if locally_tested else "lecture globale/amont"
        regularity = "lecture stable" if bool_text(best_row.get("acceptable_is_contiguous")) else "lecture irreguliere"
        dashboard_tooltip = sensitivity_row_tooltip(best_row, best_scope)
        availability_value = card_value_from_row(
            best_row,
            "product_availability_min",
            metric_min_label_any(best_row, ["kpi::product_availability", "kpi::fill_rate"], kind="pct_fraction"),
        )
        planning_value = planning_instability_value(best_row)
        cost_value = card_value_from_row(best_row, "inventory_cost_max", holding_cost_delta_label(best_row), kind="money")
        kpi_cards = [
            sensitivity_metric_card(
                "Disponibilite produit",
                availability_value,
                "plus bas observe dans la grille",
                sensitivity_card_status(best_row, "availability"),
                sensitivity_metric_tooltip(best_row, "Disponibilite produit min", "disponibilite produit min = minimum observe dans la grille", availability_value, "kpi::product_availability"),
            ),
            sensitivity_metric_card(
                "Taux replanification",
                planning_value,
                "part max des lignes touchees",
                sensitivity_card_status(best_row, "replanning"),
                planning_instability_tooltip(best_row, planning_value),
            ),
            sensitivity_metric_card(
                "Cout stockage",
                cost_value,
                "plus haut observe dans la grille",
                sensitivity_card_status(best_row, "cost"),
                sensitivity_metric_tooltip(best_row, "Cout stockage", "cout stockage = maximum du cout de stock observe dans les scenarios testes", cost_value, "kpi::inventory_cost"),
            ),
        ]
        return "".join(
            [
                f"<div class=\"{html_tooltip_class(f'sensitivityDashboard sensitivityStatus-{html.escape(status_key)}', dashboard_tooltip)}\"{html_tooltip_attrs(dashboard_tooltip)}>",
                "<div class=\"sensitivityHero\">",
                "<div class=\"sensitivityHeroMain\">",
                f"<div class=\"sensitivityStatusPill\">{html.escape(status_label)}</div>",
                f"<div class=\"sensitivityHeroTitle\">{html.escape(display_node_label(node_id))}</div>",
                f"<div class=\"sensitivityHeroText\">Point de fragilite teste: <b>{html.escape(driver_label)}</b>. Premier niveau qui degrade les KPI: <b>{html.escape(break_label)}</b>. Famille: <b>{html.escape(family_label)}</b>.</div>",
                "<div class=\"sensitivityHeroText\">Lecture: ce seuil vient d'une grille de simulation. Ce n'est pas une donnee reelle fournisseur ni un seuil exact continu.</div>",
                "</div>",
                "<div class=\"sensitivityHeroFacts\">",
                sensitivity_fact("Zone acceptable", band, f"Formule\nzone acceptable = plage continue de niveaux testes autour de x1 qui respecte les garde-fous KPI.\n\nCalcul ici\nZone = {band}\nPremier niveau degrade = {break_label}"),
                sensitivity_fact("Perimetre du test", scope_labels.get(best_scope, best_scope), f"Perimetre\n{scope_labels.get(best_scope, best_scope)}\n\nLecture\nIndique si le test agit directement sur ce noeud ou via un parametre fournisseur global/amont."),
                sensitivity_fact("Type de lecture", scope_note, f"Type de lecture\n{scope_note}\n\nLecture\nUn test local est plus directement interpretable pour ce noeud qu'une lecture globale/amont."),
                sensitivity_fact("Regularite", regularity, f"Formule\nregularite = plage acceptable continue autour de x1.\n\nCalcul ici\nacceptable_is_contiguous = {best_row.get('acceptable_is_contiguous') or 'n/a'}\nLecture = {regularity}"),
                "</div>",
                "</div>",
                "<div class=\"sensitivityMetricGrid\">",
                "".join(kpi_cards),
                "</div>",
                f"<div class=\"sensitivityRecommendation\"><b>Reco.</b> {html.escape(recommendation_text(best_row))}</div>",
                "</div>",
            ]
        )

    def sensitivity_tornado_html(scoped_rows: list[tuple[str, dict[str, str]]], limit: int = 7) -> str:
        candidates = [(scope, row, row_severity(row)) for scope, row in scoped_rows[:limit]]
        if not candidates:
            return "<div class=\"panelEmptyState dataEmptyState\">Aucun point faible disponible.</div>"
        max_score = max((score for _scope, _row, score in candidates), default=0.0) or 1.0
        parts = ["<div class=\"sensitivityTornado\">"]
        for scope, row, score in candidates:
            family = driver_family(row)
            color = driver_family_colors.get(family, driver_family_colors["other"])
            width = max(5.0, min(100.0, score / max_score * 100.0))
            status_key, status_label = status_for_row(row, locally_tested=True)
            label = str(row.get("parameter_label") or row.get("parameter_key") or "n/a")
            tooltip = sensitivity_row_tooltip(row, scope)
            parts.append(
                "".join(
                    [
                        f"<div class=\"{html_tooltip_class('sensitivityTornadoRow', tooltip)}\"{html_tooltip_attrs(tooltip)}>",
                        "<div class=\"sensitivityTornadoHead\">",
                        f"<span class=\"sensitivityTornadoLabel\">{html.escape(label)}</span>",
                        f"<span class=\"sensitivityTornadoMeta sensitivityStatus-{html.escape(status_key)}\">{html.escape(status_label)} - {html.escape(driver_family_labels.get(family, family))}</span>",
                        "</div>",
                        "<div class=\"sensitivityTornadoTrack\">",
                        f"<div class=\"sensitivityTornadoBar\" style=\"width:{width:.1f}%; background:{html.escape(color)}\"></div>",
                        "</div>",
                        "<div class=\"sensitivityTornadoFoot\">",
                        f"<span>{html.escape(scope_labels.get(scope, scope))}</span>",
                        f"<span>se degrade a partir de: {html.escape(first_unacceptable(row))}</span>",
                        f"<span>{html.escape(driver_text(row))}</span>",
                        "</div>",
                        "</div>",
                    ]
                )
            )
        parts.append("</div>")
        return "".join(parts)

    def top_distinct_sensitivity_rows(scoped_rows: list[tuple[str, dict[str, str]]], limit: int = 3) -> list[tuple[str, dict[str, str]]]:
        selected: list[tuple[str, dict[str, str]]] = []
        seen_families: set[str] = set()
        ranked = sorted(
            scoped_rows,
            key=lambda item: (
                -row_severity(item[1]),
                scope_order.get(item[0], 9),
                str(item[1].get("parameter_label") or ""),
            ),
        )
        for scope, row in ranked:
            family = driver_family(row)
            if family in seen_families:
                continue
            selected.append((scope, row))
            seen_families.add(family)
            if len(selected) >= limit:
                return selected
        for scope, row in ranked:
            if any(row is selected_row for _selected_scope, selected_row in selected):
                continue
            selected.append((scope, row))
            if len(selected) >= limit:
                break
        return selected

    def sensitivity_comparison_context(row: dict[str, str]) -> str:
        parameter_key = str(row.get("parameter_key") or "")
        if "::" in parameter_key:
            node_id = parameter_key.rsplit("::", 1)[-1]
            return display_node_label(node_id)
        return "Tous fournisseurs"

    def sensitivity_comparison_card(scope: str, row: dict[str, str], rank: int, *, include_context: bool = False) -> str:
        family = driver_family(row)
        family_label = driver_family_labels.get(family, family)
        status_key, status_label = status_for_row(row, locally_tested=True)
        label = str(row.get("parameter_label") or row.get("parameter_key") or "n/a")
        tooltip = sensitivity_row_tooltip(row, scope)
        availability_value = card_value_from_row(
            row,
            "product_availability_min",
            metric_min_label_any(row, ["kpi::product_availability", "kpi::fill_rate"], kind="pct_fraction"),
        )
        planning_value = planning_instability_value(row)
        cost_value = card_value_from_row(row, "inventory_cost_max", holding_cost_delta_label(row), kind="money")
        color = driver_family_colors.get(family, driver_family_colors["other"])
        return "".join(
            [
                f"<div class=\"{html_tooltip_class(f'sensitivityCompareCard sensitivityStatus-{html.escape(status_key)}', tooltip)}\"{html_tooltip_attrs(tooltip)}>",
                f"<div class=\"sensitivityCompareAccent\" style=\"background:{html.escape(color)}\"></div>",
                "<div class=\"sensitivityCompareTop\">",
                f"<span class=\"sensitivityCompareRank\">#{rank}</span>",
                f"<span class=\"sensitivityStatusPill\">{html.escape(status_label)}</span>",
                "</div>",
                f"<div class=\"sensitivityCompareFamily\">{html.escape(family_label)}</div>",
                f"<div class=\"sensitivityCompareContext\">{html.escape(sensitivity_comparison_context(row))}</div>" if include_context else "",
                f"<div class=\"sensitivityCompareTitle\">{html.escape(label)}</div>",
                f"<div class=\"sensitivityCompareText\">Se degrade a partir de <b>{html.escape(first_unacceptable(row))}</b>. Zone acceptable autour de 100%: <b>{html.escape(baseline_contiguous_band(row))}</b>.</div>",
                "<div class=\"sensitivityCompareKpis\">",
                f"<div><span>Disponibilite produit</span><b>{html.escape(availability_value)}</b></div>",
                f"<div><span>Taux replanification</span><b>{html.escape(planning_value)}</b></div>",
                f"<div><span>Cout stockage</span><b>{html.escape(cost_value)}</b></div>",
                "</div>",
                f"<div class=\"sensitivityCompareReason\">{html.escape(driver_text(row))}</div>",
                "</div>",
            ]
        )

    def sensitivity_comparison_html(
        node_id: str,
        scoped_rows: list[tuple[str, dict[str, str]]],
        *,
        title: str | None = None,
        include_context: bool = False,
    ) -> str:
        selected = top_distinct_sensitivity_rows(scoped_rows, limit=3)
        if not selected:
            return "<div class=\"panelEmptyState dataEmptyState\">Aucune sensibilite exploitable pour ce noeud.</div>"
        families = {driver_family(row) for _scope, row in selected}
        note = (
            "Trois familles differentes retenues."
            if len(families) >= min(3, len(selected))
            else "Moins de trois familles distinctes disponibles: la vue complete avec les meilleurs cas restants."
        )
        cards = "".join(
            sensitivity_comparison_card(scope, row, idx + 1, include_context=include_context)
            for idx, (scope, row) in enumerate(selected)
        )
        heading = title or f"{display_node_label(node_id)} - top sensibilites distinctes"
        return "".join(
            [
                "<div class=\"sensitivityCompareDashboard\">",
                "<div class=\"sensitivityCompareHeader\">",
                f"<div><div class=\"sensitivityCompareEyebrow\">Vue comparee</div><div class=\"sensitivityCompareHeading\">{html.escape(heading)}</div></div>",
                f"<div class=\"sensitivityCompareNote\">{html.escape(note)} Chaque carte correspond a un niveau teste; ce sont des resultats de grille, pas des donnees fournisseur reelles.</div>",
                "</div>",
                "<div class=\"sensitivityCompareGrid\">",
                cards,
                "</div>",
                "<div class=\"sensitivityRecommendation\"><b>Lecture.</b> Utiliser cette vue pour comparer ce qui degrade d'abord le noeud: disponibilite produit, taux de replanification ou cout de stockage. Revenir aux courbes pour voir l'effet niveau par niveau.</div>",
                "</div>",
            ]
        )

    def collapsible_panel_html(label: str, content: str, *, open_by_default: bool = False) -> str:
        open_attr = " open" if open_by_default else ""
        return "".join(
            [
                f"<details class=\"sensitivityDetails\"{open_attr}>",
                f"<summary>{html.escape(label)}</summary>",
                content,
                "</details>",
            ]
        )

    def supplier_direct_row(node_id: str, group: str) -> dict[str, str] | None:
        expected_prefix = {
            "capacity": "supplier_capacity_node::",
            "stock": "supplier_stock_node::",
            "lead_time": "supplier_lead_time_node::",
            "reliability": "supplier_reliability_node::",
        }.get(group)
        if not expected_prefix:
            return None
        expected_key = f"{expected_prefix}{node_id}"
        return next((row for row in summary_rows if str(row.get("parameter_key") or "") == expected_key), None)

    def global_upstream_row() -> dict[str, str] | None:
        candidates = [
            row
            for row in summary_rows
            if str(row.get("parameter_group") or "") == "supplier_upstream_supply"
        ]
        if not candidates:
            return None
        candidates.sort(key=lambda row: -row_severity(row))
        return candidates[0]

    def supplier_matrix_html(node_id: str) -> str:
        cells = [
            ("Capacite", supplier_direct_row(node_id, "capacity")),
            ("Stock", supplier_direct_row(node_id, "stock")),
            ("Delai", supplier_direct_row(node_id, "lead_time")),
            ("Fiabilite", supplier_direct_row(node_id, "reliability")),
            ("Appro amont", global_upstream_row()),
        ]
        parts = ["<div class=\"sensitivityMatrix\">"]
        for label, row in cells:
            status_key, status_label = matrix_status_for_row(row)
            if row is None:
                detail = "pas de sweep local"
                band = "n/a"
                tooltip = "\n".join(
                    [
                        "Lecture",
                        f"{label}: aucun test local disponible pour ce noeud.",
                        "",
                        "Important",
                        "Non teste ne veut pas dire robuste. Cela veut dire que la grille ne donne pas de seuil local.",
                    ]
                )
            else:
                band = baseline_contiguous_band(row)
                detail = f"se degrade: {first_unacceptable(row)}"
                tooltip = sensitivity_row_tooltip(row, "direct")
            parts.append(
                "".join(
                    [
                        f"<div class=\"{html_tooltip_class(f'sensitivityMatrixCell sensitivityStatus-{html.escape(status_key)}', tooltip)}\"{html_tooltip_attrs(tooltip)}>",
                        f"<div class=\"sensitivityMatrixLabel\">{html.escape(label)}</div>",
                        f"<div class=\"sensitivityMatrixStatus\">{html.escape(status_label)}</div>",
                        f"<div class=\"sensitivityMatrixBand\">{html.escape(band)}</div>",
                        f"<div class=\"sensitivityMatrixDetail\">{html.escape(detail)}</div>",
                        "</div>",
                    ]
                )
            )
        parts.append("</div>")
        return "".join(parts)

    def technical_signals_html(row: dict[str, str]) -> str:
        upstream_delta = safe_float(row.get("max_supplier_upstream_ordered_qty_delta"))
        if upstream_delta is None:
            upstream_delta = safe_float(row.get("max_external_procured_qty_delta"))
        return render_data_kv(
            [
                (
                    "Signal technique MP usine",
                    f"{fmt_qty(safe_float(row.get('raw_material_stockout_days_max')), 0)} jours max dans la grille ; +{fmt_qty(safe_float(row.get('max_raw_material_stockout_days_increase')), 0)} jours vs baseline",
                ),
                (
                    "Lecture du signal",
                    "Diagnostic technique: nombre de jours ou au moins une matiere premiere suivie finit la journee a stock usine nul. Le compteur est par jour, pas par article. Ce n'est pas une rupture client, pas une duree de rupture fournisseur, et pas un KPI de decision.",
                ),
                (
                    "Retard matiere",
                    f"delta max {fmt_qty(safe_float(row.get('max_material_delay_days_increase')), 0)} j",
                ),
                (
                    "Nervosite planning",
                    f"amplitude +{fmt_qty(safe_float(row.get('max_line_nervousness_increase')), 0)} pts ; volume replanifie +{fmt_qty(safe_float(row.get('max_production_replanning_count_increase')), 0)} lignes",
                ),
                (
                    "Ecart cible stock MP",
                    f"delta max {fmt_qty(safe_float(row.get('max_raw_material_target_gap_increase')), 0)}",
                ),
                (
                    "Appro amont",
                    f"delta max commandes amont {fmt_qty(upstream_delta, 0)}",
                ),
                (
                    "Usage",
                    "Ces signaux expliquent la contrainte interne du modele. La decision metier reste prioritairement: disponibilite produit, taux de replanification, cout de stockage.",
                ),
            ]
        )

    def method_asset(node_id: str, scoped_rows: list[tuple[str, dict[str, str]]]) -> dict[str, str]:
        method_rows = [
            ("Objet", "Sensibilite des parametres fournisseur: capacite, stock, delai, fiabilite et appro amont."),
            (
                "Lecture",
                "La plage continue baseline est la zone acceptable contigue qui contient x1. C'est la reference a utiliser en premier.",
            ),
            (
                "Garde-fous",
                "Acceptable signifie: disponibilite produit conservee, taux de replanification non degrade, cout de stockage dans le seuil et backlog final nul ou controle.",
            ),
            (
                "Lecture irreguliere",
                "Si les plages acceptables sont disjointes, on n'en deduit pas une marge robuste; il faut garder la plage continue autour de x1.",
            ),
            (
                "Signal technique MP usine",
                "Diagnostic technique: jours calendaires ou au moins une matiere premiere suivie finit la journee a stock usine nul. Le compteur est par jour, pas par article. Ce n'est pas une duree de rupture fournisseur/usine et ce signal ne pilote pas seul la decision metier.",
            ),
            (
                "Perimetre",
                f"{len(summary_rows)} parametres resumes, {len(case_rows)} simulations, {len(selected_suppliers)} fournisseurs selectionnes.",
            ),
            ("Fournisseurs testes", ", ".join(selected_suppliers[:12]) or "n/a"),
        ]
        return data_html_asset(
            f"{display_node_label(node_id)} - methode sensibilite fournisseur",
            "Regles de lecture de l'etude et limites d'interpretation.",
            [
                ("Methode", render_data_kv(method_rows)),
                (
                    "Parametres vus par ce noeud",
                    collapsible_panel_html(
                        "Afficher les 12 premiers parametres",
                        detail_table(scoped_rows[:12]),
                        open_by_default=False,
                    ),
                ),
            ],
        )

    def build_payload_for_node(node_id: str, node_type: str) -> dict[str, Any] | None:
        scoped_rows = sorted_relevant_rows(node_id, node_type)
        if not scoped_rows:
            return None
        direct_rows = [(scope, row) for scope, row in scoped_rows if scope == "direct"]
        if node_type == "supplier_dc" and direct_rows:
            direct_rows.sort(key=lambda item: (-row_severity(item[1]), str(item[1].get("parameter_label") or "")))
            best_scope, best_row = direct_rows[0]
        else:
            non_global_rows = [(scope, row) for scope, row in scoped_rows if scope != "supplier_global"]
            if non_global_rows:
                non_global_rows.sort(
                    key=lambda item: (-row_severity(item[1]), scope_order.get(item[0], 9), str(item[1].get("parameter_label") or ""))
                )
                best_scope, best_row = non_global_rows[0]
            else:
                best_scope, best_row = scoped_rows[0]
        parameter_key = str(best_row.get("parameter_key") or "")
        parameter_label = str(best_row.get("parameter_label") or parameter_key)
        direct_count = sum(1 for scope, _row in scoped_rows if scope == "direct")
        locally_tested = node_type != "supplier_dc" or direct_count > 0
        status_key, status_label = status_for_row(best_row, locally_tested=locally_tested)
        family = driver_family(best_row)
        local_scope_note = (
            "fournisseur teste localement"
            if node_type == "supplier_dc" and direct_count
            else (
                "hors perimetre local: affichage des contraintes fournisseur globales"
                if node_type == "supplier_dc"
                else "vue amont: fournisseurs relies au noeud + contraintes globales"
            )
        )
        baseline_line = (
            f"disponibilite {fmt_fill_value(baseline_fill)} | "
            f"replanification {baseline_replanning_rate_label(best_row, parameter_key)} | "
            f"backlog {fmt_qty(baseline_backlog, 0)} | cout {fmt_money_short(baseline_cost)}"
        )
        summary_rows_html = render_data_kv(
            [
                ("Noeud", display_node_label(node_id)),
                ("Perimetre", local_scope_note),
                ("Statut", status_label),
                ("Baseline", baseline_line),
                (
                    "Lecture niveaux testes",
                    "100% ref. = valeur du scenario actif; 75% = 75% de cette reference. Les taux capacite cible sont gardes dans les onglets nominaux.",
                ),
                ("Disponibilite cible", fmt_fill_value(service_threshold)),
                ("Point faible principal", parameter_label),
                ("Type de point faible", driver_family_labels.get(family, family)),
                ("Ou agit ce point faible", scope_labels.get(best_scope, best_scope)),
                ("Zone acceptable autour de la reference", baseline_contiguous_band(best_row)),
                ("Premier niveau ou ca se degrade", first_unacceptable(best_row)),
                (
                    "Disponibilite produit",
                    metric_min_label_any(best_row, ["kpi::product_availability", "kpi::fill_rate"], kind="pct_fraction"),
                ),
                ("Taux replanification", planning_instability_value(best_row)),
                ("Cout stockage max", holding_cost_delta_label(best_row)),
                ("Cause principale", driver_text(best_row)),
                ("Recommandation", recommendation_text(best_row)),
            ]
        )
        dashboard_html = sensitivity_dashboard_html(
            node_id=node_id,
            status_label=status_label,
            status_key=status_key,
            best_row=best_row,
            best_scope=best_scope,
            locally_tested=locally_tested,
        )
        overview_sections = [
            (
                "Lecture immediate",
                dashboard_html,
            ),
            ("Pourquoi ce statut ?", sensitivity_tornado_html(scoped_rows, limit=3)),
        ]
        if node_type == "supplier_dc":
            overview_sections.append(("Matrice fournisseur", supplier_matrix_html(node_id)))
        overview = data_html_asset(
            f"{display_node_label(node_id)} - synthese sensibilite fournisseur",
            "Lecture courte: point faible teste, premier niveau ou ca se degrade et impact sur les KPI metier essentiels.",
            overview_sections,
        )
        compare = data_html_asset(
            f"{display_node_label(node_id)} - priorites KPI",
            "Vue comparee: les tests de sensibilite les plus degradants sur disponibilite produit, taux de replanification ou cout de stockage.",
            [
                (
                    "Comparaison priorites KPI",
                    sensitivity_comparison_html(node_id, scoped_rows),
                )
            ],
        )
        incoming = {
            "bundle": [
                {"label": "Lecture immediate", "asset": overview},
                {"label": "Priorites KPI", "asset": compare},
            ]
        }

        curve_candidates = [
            (scope, row)
            for scope, row in scoped_rows
            if len(case_rows_by_param.get(str(row.get("parameter_key") or ""), [])) >= 2
        ]
        if node_type == "supplier_dc":
            direct_curve_candidates = [
                (scope, row)
                for scope, row in curve_candidates
                if scope == "direct"
            ]
            if direct_curve_candidates:
                curve_candidates = direct_curve_candidates
        curve_scope, curve_row = curve_candidates[0] if curve_candidates else (best_scope, best_row)
        curve_parameter_key = str(curve_row.get("parameter_key") or "")
        curve_parameter_label = str(curve_row.get("parameter_label") or curve_parameter_key)
        parameter_cases = case_rows_by_param.get(curve_parameter_key, [])
        if node_type == "supplier_dc" and curve_parameter_key.endswith(f"::{node_id}"):
            curve_primary, curve_secondary = build_supplier_threshold_metric_curve_payload(
                parameter_cases,
                node_id=node_id,
                parameter_label=curve_parameter_label,
                filename=f"{safe_case_token(node_id)}_supplier_parameter_sensitivity.png",
                metrics_cache={},
                baseline_production_planning_line_count=baseline_production_planning_line_count,
            )
        else:
            curve_primary, curve_secondary = build_threshold_metric_curve_payload(
                parameter_cases,
                parameter_label=curve_parameter_label,
                filename=f"{safe_case_token(node_id)}_supplier_parameter_sensitivity.png",
                service_threshold=service_threshold,
                baseline_production_planning_line_count=baseline_production_planning_line_count,
            )
        curve_entries = [
            {"label": "KPI metier", "asset": curve_primary},
            {"label": "Cout / detail supply", "asset": curve_secondary},
        ]
        curve_bundle = [entry for entry in curve_entries if entry.get("asset")]
        outgoing = {"bundle": curve_bundle} if len(curve_bundle) > 1 else (curve_bundle[0]["asset"] if curve_bundle else None)
        if outgoing is None:
            outgoing = data_html_asset(
                f"{display_node_label(node_id)} - courbes sensibilite",
                "Aucune courbe multi-niveaux exploitable; le detail tabulaire reste disponible.",
                [
                    (
                        "Lecture",
                        render_data_kv(
                            [
                                ("Point faible principal", parameter_label),
                                ("Niveaux testes", fmt_levels(best_row.get("levels"), best_row)),
                                ("Courbe candidate", curve_parameter_label),
                                ("Note", "Les courbes de sensibilite utilisent le niveau du parametre en abscisse, pas le temps."),
                            ]
                        ),
                    )
                ],
            )
        third = data_html_asset(
            f"{display_node_label(node_id)} - details avances sensibilite",
            "A utiliser pour audit. La lecture operationnelle principale est dans la synthese.",
            [
                (
                    "Definitions des signaux techniques",
                    technical_signals_html(best_row),
                ),
                (
                    "Action et recommandation",
                    collapsible_panel_html("Afficher la lecture detaillee", summary_rows_html, open_by_default=False),
                ),
                (
                    "Marges testees",
                    collapsible_panel_html("Afficher les marges par parametre", margin_table(scoped_rows, limit=8), open_by_default=False),
                ),
                (
                    "Principaux points faibles en tableau",
                    collapsible_panel_html("Afficher le tableau des principaux points faibles", summary_table(scoped_rows, limit=8), open_by_default=False),
                ),
                (
                    "Seuils et garde-fous",
                    collapsible_panel_html(
                        "Afficher le tableau complet des seuils",
                        detail_table(scoped_rows),
                        open_by_default=False,
                    ),
                ),
            ],
        )
        fourth = method_asset(node_id, scoped_rows)
        return {
            "incoming": incoming,
            "outgoing": outgoing,
            "third": third,
            "fourth": fourth,
            "compare": compare,
            "_meta": {
                "status": status_key,
                "status_label": status_label,
                "driver_family": family,
                "driver_family_label": driver_family_labels.get(family, family),
                "driver_color": driver_family_colors.get(family, driver_family_colors["other"]),
                "driver_label": parameter_label,
                "first_unacceptable": first_unacceptable(best_row),
                "reason": driver_text(best_row),
                "locally_tested": locally_tested,
                "scope": scope_labels.get(best_scope, best_scope),
            },
        }

    factory_out: dict[str, Any] = {}
    supplier_out: dict[str, Any] = {}
    dc_out: dict[str, Any] = {}
    node_meta: dict[str, Any] = {}
    for node in raw.get("nodes", []) or []:
        node_id = str(node.get("id") or "")
        node_type = str(node.get("type") or "")
        if node_type not in {"factory", "supplier_dc", "distribution_center"} or not node_id:
            continue
        payload = build_payload_for_node(node_id, node_type)
        if not payload:
            continue
        meta = payload.pop("_meta", None)
        if meta:
            node_meta[node_id] = meta
        if node_type == "factory":
            factory_out[node_id] = payload
        elif node_type == "supplier_dc":
            supplier_out[node_id] = payload
        else:
            dc_out[node_id] = payload
    global_scoped_rows = [
        ("global", row)
        for row in summary_rows
        if str(row.get("parameter_key") or "") and str(row.get("parameter_key") or "") != "baseline"
    ]
    node_meta["_global_top3"] = data_html_asset(
        "Sensibilite - priorites KPI globales",
        "Vue accessible sans selectionner de noeud: les tests qui degradent le plus disponibilite produit, taux de replanification ou cout de stockage.",
        [
            (
                "Priorites KPI globales",
                sensitivity_comparison_html(
                    "__global__",
                    global_scoped_rows,
                    title="Priorites KPI globales",
                    include_context=True,
                ),
            )
        ],
    )
    return factory_out, supplier_out, dc_out, node_meta


def build_montecarlo_uncertainty_payload(summary_json: Path) -> dict[str, Any]:
    def as_float(value: Any, default: float = 0.0) -> float:
        numeric = to_float(value)
        if numeric is None or math.isnan(numeric):
            return default
        return numeric

    def pct01(value: Any, digits: int = 1) -> str:
        numeric = to_float(value)
        if numeric is None or math.isnan(numeric):
            return "n/a"
        return fmt_pct(numeric * 100.0, digits)

    def fmt_money_short(value: Any) -> str:
        numeric = to_float(value)
        if numeric is None or math.isnan(numeric):
            return "n/a"
        abs_value = abs(numeric)
        if abs_value >= 1_000_000:
            return f"{numeric / 1_000_000:.2f} M"
        if abs_value >= 1_000:
            return f"{numeric / 1_000:.1f} k"
        return f"{numeric:.0f}"

    def stat(summary: dict[str, Any], metric: str) -> dict[str, Any]:
        return (summary.get("metric_statistics") or {}).get(f"kpi::{metric}") or {}

    def stat_value(summary: dict[str, Any], metric: str, key: str) -> float | None:
        return to_float(stat(summary, metric).get(key))

    def format_stat(summary: dict[str, Any], metric: str, key: str, kind: str = "qty") -> str:
        value = stat_value(summary, metric, key)
        if value is None:
            return "n/a"
        if kind == "pct01":
            return pct01(value)
        if kind == "money":
            return fmt_money_short(value)
        if kind == "int":
            return fmt_qty(value, 0)
        return fmt_qty(value, 1)

    def factor_label(raw_factor: str) -> str:
        raw_factor = str(raw_factor or "")
        labels = {
            "factor::demand_scale": "Demande globale",
            "factor::lead_time_scale": "Delais fournisseurs globaux",
            "factor::transport_cost_scale": "Couts transport",
            "factor::supplier_stock_scale": "Stocks fournisseurs globaux",
            "factor::production_stock_scale": "Stocks usines globaux",
            "factor::capacity_scale": "Capacites usines globales",
            "factor::supplier_capacity_scale": "Capacites fournisseurs globales",
            "factor::supplier_reliability_scale": "Fiabilite fournisseurs globale",
            "factor::external_procurement_daily_cap_days_scale": "Appro amont capacite globale",
            "factor::external_procurement_lead_days_scale": "Appro amont delai global",
            "factor::holding_cost_scale": "Cout de stockage",
        }
        if raw_factor in labels:
            return labels[raw_factor]
        prefix_labels = [
            ("demand_item::", "Demande article "),
            ("capacity_node::", "Capacite usine "),
            ("supplier_stock_node::", "Stock fournisseur "),
            ("supplier_capacity_node::", "Capacite fournisseur "),
            ("supplier_lead_node::", "Delai fournisseur "),
            ("supplier_reliability_node::", "Fiabilite fournisseur "),
        ]
        for prefix, label in prefix_labels:
            if raw_factor.startswith(prefix):
                return f"{label}{raw_factor.removeprefix(prefix)}"
        return raw_factor.replace("factor::", "").replace("_", " ")

    def metric_card(title: str, value: str, note: str, tooltip: str | None = None) -> str:
        return "".join(
            [
                f"<div class=\"{html_tooltip_class('uncertaintyCard', tooltip)}\"{html_tooltip_attrs(tooltip)}>",
                f"<div class=\"uncertaintyCardLabel\">{html.escape(title)}</div>",
                f"<div class=\"uncertaintyCardValue\">{html.escape(value)}</div>",
                f"<div class=\"uncertaintyCardNote\">{html.escape(note)}</div>",
                "</div>",
            ]
        )

    def corr_text(value: float | None) -> str:
        if value is None or math.isnan(value):
            return "n/a"
        return f"{value * 100.0:+.1f}%"

    def mc_node_driver_from_factor(raw_factor: str) -> tuple[str, str, str, str, str] | None:
        prefixes = {
            "supplier_stock_node::": ("stock", "Stock fournisseur", "low_is_worse", "#0f766e", "moins de stock degrade la disponibilite produit"),
            "supplier_capacity_node::": ("capacity", "Capacite fournisseur", "low_is_worse", "#d97706", "moins de capacite degrade la disponibilite produit"),
            "supplier_lead_node::": ("lead", "Delai fournisseur", "high_is_worse", "#7c3aed", "plus de delai degrade la disponibilite produit"),
            "supplier_reliability_node::": ("reliability", "Fiabilite fournisseur", "low_is_worse", "#2563eb", "moins de fiabilite degrade la disponibilite produit"),
            "capacity_node::": ("factory_capacity", "Capacite usine", "low_is_worse", "#be123c", "moins de capacite degrade la disponibilite produit"),
        }
        for prefix, payload in prefixes.items():
            if raw_factor.startswith(prefix):
                family, label, direction, color, meaning = payload
                return family, raw_factor.removeprefix(prefix), label, direction, color, meaning
        return None

    def mc_driver_score(corrs: dict[str, Any], direction: str) -> tuple[float, float, float, float, str]:
        fill_corr = as_float(corrs.get("kpi::fill_rate"), 0.0)
        backlog_corr = as_float(corrs.get("kpi::ending_backlog"), 0.0)
        cost_corr = as_float(corrs.get("kpi::total_cost"), 0.0)
        if direction == "high_is_worse":
            service_signal = max(0.0, -fill_corr)
            backlog_signal = max(0.0, backlog_corr)
            cost_signal = max(0.0, cost_corr)
            formula = (
                "55% x max(0, -corr disponibilite produit) + "
                "35% x max(0, corr backlog) + "
                "10% x max(0, corr cout)"
            )
        else:
            service_signal = max(0.0, fill_corr)
            backlog_signal = max(0.0, -backlog_corr)
            cost_signal = max(0.0, -cost_corr)
            formula = (
                "55% x max(0, corr disponibilite produit) + "
                "35% x max(0, -corr backlog) + "
                "10% x max(0, -corr cout)"
            )
        score = max(0.0, min(1.0, 0.55 * service_signal + 0.35 * backlog_signal + 0.10 * cost_signal))
        return score, fill_corr, backlog_corr, cost_corr, formula

    def mc_driver_signals(corrs: dict[str, Any], direction: str) -> tuple[float, float, float]:
        fill_corr = as_float(corrs.get("kpi::fill_rate"), 0.0)
        backlog_corr = as_float(corrs.get("kpi::ending_backlog"), 0.0)
        cost_corr = as_float(corrs.get("kpi::total_cost"), 0.0)
        if direction == "high_is_worse":
            return max(0.0, -fill_corr), max(0.0, backlog_corr), max(0.0, cost_corr)
        return max(0.0, fill_corr), max(0.0, -backlog_corr), max(0.0, -cost_corr)

    def mc_status(score: float) -> tuple[str, str, str]:
        if score >= 0.20:
            return "sensitive", "Fragile dans Monte Carlo", "businessAlert"
        if score >= 0.08:
            return "watch", "A surveiller dans Monte Carlo", "businessWarn"
        return "robust", "Robuste dans Monte Carlo", "businessOk"

    def build_montecarlo_node_payloads(summary: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
        node_rows: dict[str, list[dict[str, Any]]] = defaultdict(list)
        correlations = summary.get("factor_kpi_correlations_pearson") or {}
        if not isinstance(correlations, dict):
            return {}, {}

        for raw_factor, corrs in correlations.items():
            parsed = mc_node_driver_from_factor(str(raw_factor or ""))
            if not parsed or not isinstance(corrs, dict):
                continue
            family, node_id, label, direction, color, meaning = parsed
            score, fill_corr, backlog_corr, cost_corr, formula = mc_driver_score(corrs, direction)
            service_signal, backlog_signal, cost_signal = mc_driver_signals(corrs, direction)
            if score <= 0.0 and abs(fill_corr) < 0.03 and abs(backlog_corr) < 0.03 and abs(cost_corr) < 0.03:
                continue
            node_rows[node_id].append(
                {
                    "factor": str(raw_factor or ""),
                    "family": family,
                    "label": label,
                    "direction": direction,
                    "color": color,
                    "meaning": meaning,
                    "score": round(score, 6),
                    "service_score": round(service_signal, 6),
                    "backlog_score": round(backlog_signal, 6),
                    "cost_score": round(cost_signal, 6),
                    "fill_corr": round(fill_corr, 6),
                    "backlog_corr": round(backlog_corr, 6),
                    "cost_corr": round(cost_corr, 6),
                    "formula": formula,
                }
            )

        nodes: dict[str, Any] = {}
        node_assets: dict[str, Any] = {}
        for node_id, rows in node_rows.items():
            rows = sorted(rows, key=lambda row: (float(row.get("score") or 0.0), abs(float(row.get("fill_corr") or 0.0))), reverse=True)
            if not rows:
                continue
            top = rows[0]
            score = float(top.get("score") or 0.0)
            status, status_label, business_class = mc_status(score)
            color = str(top.get("color") or "#64748b")
            driver_label = str(top.get("label") or "Parametre")
            score_label = fmt_pct(score * 100.0, 1)

            def view_payload(view_key: str, score_key: str, title: str) -> dict[str, Any]:
                selected = max(
                    rows,
                    key=lambda row: (float(row.get(score_key) or 0.0), float(row.get("score") or 0.0)),
                )
                view_score = float(selected.get(score_key) or 0.0)
                view_status, view_status_label, view_business_class = mc_status(view_score)
                return {
                    "view": view_key,
                    "title": title,
                    "score": round(view_score, 6),
                    "status": view_status,
                    "status_label": view_status_label,
                    "business_class": view_business_class,
                    "color": str(selected.get("color") or "#64748b"),
                    "dominant_dimension": str(selected.get("label") or "Parametre"),
                    "driver_family": str(selected.get("family") or ""),
                    "driver_factor": str(selected.get("factor") or ""),
                    "fill_rate_correlation": selected.get("fill_corr"),
                    "backlog_correlation": selected.get("backlog_corr"),
                    "cost_correlation": selected.get("cost_corr"),
                }

            views = {
                "global": view_payload("global", "score", "Impact global Monte Carlo"),
                "service": view_payload("service", "service_score", "Impact disponibilite produit"),
                "backlog": view_payload("backlog", "backlog_score", "Impact backlog"),
                "cost": view_payload("cost", "cost_score", "Impact cout"),
            }
            tooltip = "\n".join(
                [
                    "Source",
                    f"{runs} runs Monte Carlo, horizon {days} jours, profil {profile}",
                    "",
                    "Formule impact noeud",
                    str(top.get("formula") or ""),
                    "",
                    "Calcul driver principal",
                    f"corr disponibilite = {corr_text(float(top.get('fill_corr') or 0.0))}",
                    f"corr backlog = {corr_text(float(top.get('backlog_corr') or 0.0))}",
                    f"corr cout = {corr_text(float(top.get('cost_corr') or 0.0))}",
                    f"score impact = {score_label}",
                    "",
                    "Lecture",
                    "Ce score vient des runs Monte Carlo. Il indique quels noeuds expliquent le plus les ecarts entre scenarios.",
                ]
            )
            summary_lines = [
                {"label": "Lecture", "value": "Monte Carlo"},
                {"label": "Statut", "value": status_label},
                {"label": "Impact noeud", "value": score_label},
                {"label": "Driver principal", "value": driver_label},
                {"label": "Correlation disponibilite", "value": corr_text(float(top.get("fill_corr") or 0.0))},
                {"label": "Correlation backlog", "value": corr_text(float(top.get("backlog_corr") or 0.0))},
                {"label": "Correlation cout", "value": corr_text(float(top.get("cost_corr") or 0.0))},
                {"label": "Runs", "value": str(runs)},
                {"label": "Horizon", "value": f"{days} j"},
            ]

            driver_table_rows = []
            for row in rows[:8]:
                score_row = float(row.get("score") or 0.0)
                raw_factor = str(row.get("factor") or "")
                driver_table_rows.append(
                    "<tr>"
                    f"<td>{html.escape(str(row.get('label') or 'n/a'))}</td>"
                    f"<td>{html.escape(fmt_pct(score_row * 100.0, 1))}</td>"
                    f"<td>{html.escape(factor_tested_range_text(raw_factor))}</td>"
                    f"<td>{html.escape(corr_text(float(row.get('fill_corr') or 0.0)))}</td>"
                    f"<td>{html.escape(corr_text(float(row.get('backlog_corr') or 0.0)))}</td>"
                    f"<td>{html.escape(corr_text(float(row.get('cost_corr') or 0.0)))}</td>"
                    f"<td>{html.escape(str(row.get('meaning') or ''))}</td>"
                    "</tr>"
                )

            driver_table = (
                "<div class=\"orderLedgerTableWrap\" tabindex=\"0\">"
                "<table class=\"kpiFormulaTable\"><thead><tr>"
                "<th>Dimension testee</th><th>Lien observe</th><th>Plage testee</th><th>Corr. disponibilite</th><th>Corr. backlog</th><th>Corr. cout</th><th>Lecture</th>"
                "</tr></thead><tbody>"
                f"{''.join(driver_table_rows)}"
                "</tbody></table></div>"
            )
            limit_note = (
                "<div class=\"orderLedgerStatus\">"
                "Lecture importante: ce n'est pas une donnee fournisseur reelle. C'est l'impact observe quand les parametres aleatoires "
                "de la simulation bougent. Une correlation proche de zero signifie seulement que les 200 runs n'ont pas montre d'effet clair "
                "pour cette dimension."
                "</div>"
            )
            node_assets[node_id] = data_html_asset(
                f"{node_id} - impact Monte Carlo",
                "Details du mode Incertitude: dimensions testees, correlations et limites de lecture.",
                [
                    ("Drivers observes pour ce noeud", driver_table),
                    ("Limites", limit_note),
                ],
            )
            nodes[node_id] = {
                "source": "montecarlo",
                "title": f"Impact Monte Carlo - {node_id}",
                "summary_lines": summary_lines,
                "score": round(score, 6),
                "confidence": 1.0 if runs >= 100 else min(1.0, runs / 100.0),
                "status": status,
                "status_label": status_label,
                "business_class": business_class,
                "color": color,
                "dominant_dimension": driver_label,
                "dominant_score": round(score, 6),
                "driver_family": str(top.get("family") or ""),
                "driver_label": driver_label,
                "driver_factor": str(top.get("factor") or ""),
                "fill_rate_correlation": top.get("fill_corr"),
                "backlog_correlation": top.get("backlog_corr"),
                "cost_correlation": top.get("cost_corr"),
                "runs": runs,
                "days": days,
                "profile": profile,
                "views": views,
                "drivers": rows,
            }
        return nodes, node_assets

    if not summary_json.exists():
        html_body = (
            "<div class=\"factoryHtmlPanelContent dataSummaryPanelContent\">"
            "<div class=\"uncertaintyDashboard sensitivityStatus-untested\">"
            "<div class=\"uncertaintyHero\">"
            "<div class=\"sensitivityStatusPill\">Monte Carlo non lance</div>"
            "<div class=\"uncertaintyHeroTitle\">Incertitude dynamique</div>"
            "<div class=\"uncertaintyHeroText\">Aucun resultat Monte Carlo n'a encore ete trouve pour cette baseline. "
            "L'onglet Incertitude attend des runs Monte Carlo pour colorer les noeuds par impact observe.</div>"
            "</div></div></div>"
        )
        return {"available": False, "summary_json": str(summary_json), "html": html_body}

    try:
        summary = json.loads(summary_json.read_text(encoding="utf-8"))
    except Exception as exc:
        html_body = (
            "<div class=\"factoryHtmlPanelContent dataSummaryPanelContent\">"
            "<div class=\"uncertaintyDashboard sensitivityStatus-sensitive\">"
            "<div class=\"uncertaintyHero\">"
            "<div class=\"sensitivityStatusPill\">Lecture impossible</div>"
            "<div class=\"uncertaintyHeroTitle\">Incertitude dynamique</div>"
            f"<div class=\"uncertaintyHeroText\">Le fichier Monte Carlo existe mais ne peut pas etre lu: {html.escape(str(exc))}</div>"
            "</div></div></div>"
        )
        return {"available": False, "summary_json": str(summary_json), "html": html_body}

    diagnostics = build_uncertainty_diagnostics(summary_json)
    decision = summary.get("decision_metrics") or {}
    if not decision and isinstance(diagnostics.get("decision_metrics"), dict):
        decision = diagnostics.get("decision_metrics") or {}
    runs = int(as_float(summary.get("successful_stochastic_runs"), 0.0) or 0)
    failed = int(as_float(summary.get("failed_runs"), 0.0) or 0)
    days = int(as_float(summary.get("days_override"), 0.0) or 0)
    profile = str(summary.get("uncertainty_profile") or "n/a")
    seed = str(summary.get("seed") or "n/a")
    service_risk = as_float(decision.get("fill_rate_below_100pct"), 0.0)
    backlog_risk = as_float(decision.get("backlog_positive"), 0.0)
    cost_risk = as_float(decision.get("total_cost_above_baseline"), 0.0)
    status_cls = "robust"
    status_label = "Resilience observee"
    if runs < 20 or failed > 0:
        status_cls = "watch"
        status_label = "Echantillon a renforcer"
    if service_risk > 0.0 or backlog_risk > 0.0:
        status_cls = "watch"
        status_label = "Fragilite disponibilite observee"
    if service_risk >= 0.20 or backlog_risk >= 0.20:
        status_cls = "sensitive"
        status_label = "Risque disponibilite eleve"
    diag_meta = diagnostics.get("meta") if isinstance(diagnostics.get("meta"), dict) else {}
    suite_assessment = diagnostics.get("suite_assessment") if isinstance(diagnostics.get("suite_assessment"), dict) else {}
    interpretation = str(diag_meta.get("interpretation") or "incertitude_operationnelle")
    suite_status = str(suite_assessment.get("status") or "")
    if interpretation == "stress_tres_severe" or suite_status == "too_extreme":
        status_cls = "sensitive"
        status_label = "Variation tres severe"

    fill_stat = stat(summary, "fill_rate")
    backlog_stat = stat(summary, "ending_backlog")
    cost_stat = stat(summary, "total_cost")
    inv_cost_stat = stat(summary, "total_inventory_cost_legacy_raw_holding")
    supplier_binding_stat = stat(summary, "total_supplier_capacity_binding_qty")
    trajectory_assets = build_montecarlo_trajectory_assets(summary_json)
    trajectory_days = trajectory_assets.get("days") if isinstance(trajectory_assets.get("days"), list) else []
    trajectory_horizon_label = (
        f"J{min(trajectory_days)} -> J{max(trajectory_days)} ; {len(trajectory_days)} pts"
        if trajectory_days
        else "n/a"
    )
    trajectory_summaries = (
        trajectory_assets.get("metric_summaries")
        if isinstance(trajectory_assets.get("metric_summaries"), dict)
        else {}
    )

    def trajectory_value(metric_key: str, field: str) -> float | None:
        row = trajectory_summaries.get(metric_key) if isinstance(trajectory_summaries, dict) else None
        if not isinstance(row, dict):
            return None
        return to_float(row.get(field))

    def format_trajectory_value(metric_key: str, field: str, kind: str = "qty") -> str:
        value = trajectory_value(metric_key, field)
        if value is None:
            return "n/a"
        if kind == "int":
            return fmt_qty(value, 0)
        if kind == "money":
            return fmt_money_short(value)
        return fmt_qty(value, 1)

    def threshold_value_text(row: dict[str, Any]) -> str:
        value = to_float(row.get("threshold"))
        if value is None:
            return "n/a"
        metric = str(row.get("metric") or "")
        if metric.endswith("fill_rate"):
            return pct01(value)
        if abs(value) >= 1_000_000:
            return fmt_money_short(value) if metric.endswith("total_cost") else fmt_qty(value, 0)
        return fmt_qty(value, 1)

    def format_kpi_value(metric: str, value: Any) -> str:
        numeric = to_float(value)
        if numeric is None or math.isnan(numeric):
            return "n/a"
        if metric == "kpi::fill_rate":
            return pct01(numeric)
        if "cost" in metric:
            return fmt_money_short(numeric)
        if abs(numeric) >= 1_000_000:
            return fmt_qty(numeric, 0)
        return fmt_qty(numeric, 1)

    def format_input_factor_value(value: Any) -> str:
        numeric = to_float(value)
        if numeric is None or math.isnan(numeric):
            return "n/a"
        return fmt_pct(numeric * 100.0, 0)

    def format_kpi_delta(metric: str, value: Any) -> str:
        numeric = to_float(value)
        if numeric is None or math.isnan(numeric):
            return "n/a"
        sign = "+" if numeric >= 0 else "-"
        abs_value = abs(numeric)
        if metric == "kpi::fill_rate":
            return f"{sign}{abs_value * 100.0:.2f} pts"
        if "cost" in metric:
            return f"{sign}{fmt_money_short(abs_value)}"
        return f"{sign}{fmt_qty(abs_value, 1)}"

    def display_kpi_label(value: Any) -> str:
        raw = str(value or "").strip()
        normalized = raw.lower().replace("_", " ")
        if raw == "kpi::fill_rate" or normalized in {"fill rate", "fillrate", "service", "service client"}:
            return "Disponibilite produit"
        if raw == "kpi::ending_backlog" or normalized in {"ending backlog", "backlog final"}:
            return "Backlog final"
        if raw == "kpi::total_cost" or normalized in {"total cost", "cout total"}:
            return "Cout total"
        if raw == "kpi::total_supplier_capacity_binding_qty":
            return "Capacite fournisseur contrainte"
        if raw == "kpi::total_produced":
            return "Production realisee"
        return raw or "n/a"

    def factor_distribution_values(raw_factor: Any) -> list[float]:
        factor = str(raw_factor or "").strip()
        distributions = summary.get("factor_distributions") if isinstance(summary.get("factor_distributions"), dict) else {}
        if not factor or not distributions:
            return []
        if factor.startswith("factor::"):
            values = (distributions.get("global") or {}).get(factor.removeprefix("factor::"))
        else:
            mapping = [
                ("demand_item::", "demand_item_scale"),
                ("capacity_node::", "capacity_node_scale"),
                ("supplier_stock_node::", "supplier_stock_node_scale"),
                ("supplier_capacity_node::", "supplier_capacity_node_scale"),
                ("supplier_lead_node::", "supplier_lead_node_scale"),
                ("supplier_reliability_node::", "supplier_reliability_node_scale"),
            ]
            values = None
            for prefix, distribution_key in mapping:
                if factor.startswith(prefix):
                    values = (distributions.get(distribution_key) or {}).get(factor.removeprefix(prefix))
                    break
        if not isinstance(values, list):
            return []
        out: list[float] = []
        for value in values:
            numeric = to_float(value)
            if numeric is not None and not math.isnan(numeric):
                out.append(float(numeric))
        return out

    def factor_tested_range_text(raw_factor: Any) -> str:
        values = factor_distribution_values(raw_factor)
        if not values:
            return "n/a"
        low = min(values)
        high = max(values)
        center = values[len(values) // 2] if len(values) >= 3 else None

        def factor_pct(value: float) -> str:
            percent = value * 100.0
            return f"{percent:.0f}%" if abs(percent - round(percent)) <= 1e-9 else f"{percent:.1f}%"

        if center is not None and low < center < high:
            return f"{factor_pct(low)} -> {factor_pct(high)} ; centre {factor_pct(center)}"
        return f"{factor_pct(low)} -> {factor_pct(high)}"

    mc_nodes, mc_node_assets = build_montecarlo_node_payloads(summary)

    def propagation_signal_text(corr: float | None, r2: float | None) -> str:
        if corr is None or math.isnan(corr) or r2 is None or math.isnan(r2):
            return "signal non lisible"
        explained = max(0.0, min(1.0, r2))
        if explained >= 0.50:
            label = "signal fort"
        elif explained >= 0.20:
            label = "signal moyen"
        elif explained >= 0.05:
            label = "signal faible"
        else:
            label = "signal fragile"
        return f"{label} - {fmt_pct(explained * 100.0, 0)} des ecarts expliques"

    def propagation_transfer_text(row: dict[str, Any]) -> str:
        input_rel = to_float(row.get("input_relative_uncertainty"))
        output_rel = to_float(row.get("kpi_uncertainty_relative_to_baseline"))
        ratio = to_float(row.get("uncertainty_transfer_ratio"))
        if input_rel is None or math.isnan(input_rel) or output_rel is None or math.isnan(output_rel):
            return "n/a - baseline KPI nulle"
        if ratio is None or math.isnan(ratio):
            ratio = output_rel / input_rel if abs(input_rel) > 1e-12 else float("nan")
        if math.isnan(ratio):
            return "n/a"
        return f"x{ratio:.1f} ({fmt_pct(input_rel * 100.0, 0)} entree -> {fmt_pct(output_rel * 100.0, 1)} KPI)"

    def propagation_band_chart_html(rows: list[dict[str, Any]]) -> str:
        chart_rows: list[tuple[dict[str, Any], float, float | None]] = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            output_rel = to_float(row.get("kpi_uncertainty_relative_to_baseline"))
            if output_rel is None or math.isnan(output_rel) or output_rel <= 0:
                continue
            ratio = to_float(row.get("uncertainty_transfer_ratio"))
            chart_rows.append((row, output_rel, ratio))
            if len(chart_rows) >= 8:
                break
        if not chart_rows:
            return ""

        max_rel = max(value for _, value, _ in chart_rows)
        max_rel = max(max_rel, 0.05)
        width = 980
        label_x = 18
        axis_x = 360
        axis_w = 430
        value_x = 820
        row_h = 42
        top = 58
        height = top + len(chart_rows) * row_h + 40
        center = axis_x + axis_w / 2.0

        def svg_text(value: Any, limit: int = 48) -> str:
            text = str(value or "n/a").replace("\n", " ").strip()
            if len(text) > limit:
                text = f"{text[: limit - 1]}..."
            return html.escape(text)

        row_bits = [
            f"<line x1=\"{axis_x}\" y1=\"34\" x2=\"{axis_x + axis_w}\" y2=\"34\" stroke=\"#cbd5e1\" stroke-width=\"1\"/>",
            f"<line x1=\"{center:.1f}\" y1=\"28\" x2=\"{center:.1f}\" y2=\"{height - 28}\" stroke=\"#0f172a\" stroke-width=\"1.2\" opacity=\"0.65\"/>",
            f"<text x=\"{axis_x}\" y=\"24\" font-size=\"11\" fill=\"#64748b\" text-anchor=\"middle\">-{html.escape(fmt_pct(max_rel * 100.0, 1))}</text>",
            f"<text x=\"{center:.1f}\" y=\"24\" font-size=\"11\" fill=\"#0f172a\" text-anchor=\"middle\">nominal</text>",
            f"<text x=\"{axis_x + axis_w}\" y=\"24\" font-size=\"11\" fill=\"#64748b\" text-anchor=\"middle\">+{html.escape(fmt_pct(max_rel * 100.0, 1))}</text>",
        ]
        for idx, (row, output_rel, ratio) in enumerate(chart_rows):
            y = top + idx * row_h
            half = min(axis_w / 2.0, (output_rel / max_rel) * (axis_w / 2.0))
            x1 = center - half
            band_w = half * 2.0
            ratio_text = "n/a" if ratio is None or math.isnan(ratio) else f"x{ratio:.1f}"
            kpi_label = display_kpi_label(row.get("kpi_label") or row.get("kpi") or "KPI")
            input_label = row.get("label") or row.get("factor") or "input"
            status = row.get("status_label") or ""
            row_bits.extend(
                [
                    f"<text x=\"{label_x}\" y=\"{y + 4}\" font-size=\"12\" font-weight=\"700\" fill=\"#0f172a\">{svg_text(input_label, 42)}</text>",
                    f"<text x=\"{label_x}\" y=\"{y + 20}\" font-size=\"11\" fill=\"#64748b\">{svg_text(kpi_label, 44)}</text>",
                    f"<rect x=\"{x1:.1f}\" y=\"{y - 10}\" width=\"{band_w:.1f}\" height=\"20\" rx=\"10\" fill=\"#0f766e\" opacity=\"0.16\"/>",
                    f"<line x1=\"{x1:.1f}\" y1=\"{y}\" x2=\"{x1 + band_w:.1f}\" y2=\"{y}\" stroke=\"#0f766e\" stroke-width=\"2.4\" opacity=\"0.72\"/>",
                    f"<circle cx=\"{center:.1f}\" cy=\"{y}\" r=\"3.5\" fill=\"#111827\"/>",
                    f"<text x=\"{value_x}\" y=\"{y + 3}\" font-size=\"12\" fill=\"#0f172a\">+/- {html.escape(fmt_pct(output_rel * 100.0, 1))} KPI</text>",
                    f"<text x=\"{value_x}\" y=\"{y + 19}\" font-size=\"11\" fill=\"#64748b\">{html.escape(ratio_text)} - {svg_text(status, 24)}</text>",
                ]
            )

        return (
            "<div class=\"orderLedgerStatus\">"
            "Lecture graphique: chaque bande traduit l'incertitude de sortie estimee si l'input fournisseur varie de -20% a +20%. "
            "Le point central est le nominal. Ce n'est pas une probabilite historique; c'est une sensibilite observee dans les runs Monte Carlo."
            "</div>"
            "<div class=\"orderLedgerTableWrap\" tabindex=\"0\">"
            f"<svg role=\"img\" aria-label=\"Bandes d'incertitude fournisseur\" viewBox=\"0 0 {width} {height}\" "
            "style=\"width:100%;min-width:760px;height:auto;display:block;background:#ffffff;border:1px solid #dbe5f1;border-radius:12px;\">"
            "<rect x=\"0\" y=\"0\" width=\"980\" height=\"100%\" fill=\"#ffffff\"/>"
            f"<text x=\"{label_x}\" y=\"26\" font-size=\"13\" font-weight=\"800\" fill=\"#0f172a\">Bandes d'incertitude fournisseur</text>"
            f"<text x=\"{axis_x + axis_w / 2.0}\" y=\"{height - 10}\" font-size=\"11\" fill=\"#64748b\" text-anchor=\"middle\">plage KPI finale relative au nominal</text>"
            f"{''.join(row_bits)}"
            "</svg>"
            "</div>"
        )

    def interpretation_label(key: str) -> str:
        labels = {
            "stress_tres_severe": "stress tres severe",
            "stress_non_probabiliste": "stress non probabiliste",
            "incertitude_operationnelle": "incertitude operationnelle",
        }
        return labels.get(key, key.replace("_", " "))

    cards = [
        metric_card(
            "Disponibilite produit",
            f"P05 {format_stat(summary, 'fill_rate', 'p05', 'pct01')}",
            f"mediane {format_stat(summary, 'fill_rate', 'p50', 'pct01')} ; baseline {format_stat(summary, 'fill_rate', 'baseline', 'pct01')}",
            "Part de la demande client servie dans les scenarios. C'est la mesure principale de disponibilite produit cote client.",
        ),
        metric_card(
            "Backlog",
            f"P95 {format_stat(summary, 'ending_backlog', 'p95', 'qty')}",
            f"risque backlog > 0: {pct01(backlog_risk)}",
            "Backlog final observe dans les scenarios. Un backlog positif indique que la demande client n'est pas totalement absorbee.",
        ),
        metric_card(
            "Reports de production",
            f"P95 max {format_trajectory_value('production_reports', 'p95_max', 'qty')}",
            f"mediane max {format_trajectory_value('production_reports', 'p50_max', 'qty')}",
            "Volume de lots produits qui entrent en report par manque supply. C'est un signal de nervosite MRP et une cause possible de degradation de disponibilite.",
        ),
        metric_card(
            "Capacite fournisseur contrainte",
            f"P95 {format_stat(summary, 'total_supplier_capacity_binding_qty', 'p95', 'qty')}",
            f"baseline {format_stat(summary, 'total_supplier_capacity_binding_qty', 'baseline', 'qty')}",
            "Quantite totale qui rencontre une limite de capacite fournisseur dans la simulation.",
        ),
    ]
    secondary_cards = [
        metric_card(
            "Lecture statistique",
            "exploratoire" if runs < 30 else ("solide" if runs >= 100 else "intermediaire"),
            f"{runs} runs valides ; drivers a confirmer" if runs < 30 else f"{runs} runs valides",
            "Moins de 30 runs: les enveloppes donnent une premiere lecture, mais les correlations de drivers restent instables. Viser 60-120 runs pour un diagnostic exploitable.",
        ),
        metric_card(
            "Nature du profil",
            interpretation_label(interpretation),
            f"assessment {suite_status or 'n/a'} ; profil {profile}",
            "Un profil stress explore les points de rupture du modele. Il ne doit pas etre lu comme une probabilite historique terrain.",
        ),
        metric_card(
            "Risque disponibilite < 100%",
            pct01(service_risk),
            "part des scenarios ou toute la demande client n'est pas servie",
            "Calcul = nombre de runs Monte Carlo avec disponibilite produit < 100% / nombre de runs valides.",
        ),
        metric_card(
            "Cout total",
            f"P50 {format_stat(summary, 'total_cost', 'p50', 'money')}",
            f"P05-P95 {format_stat(summary, 'total_cost', 'p05', 'money')} - {format_stat(summary, 'total_cost', 'p95', 'money')}",
            "Distribution du cout total quand les parametres incertains bougent autour du nominal.",
        ),
        metric_card(
            "Ordres production en attente",
            f"P95 max {format_trajectory_value('production_delay_active_orders', 'p95_max', 'int')}",
            f"mediane max {format_trajectory_value('production_delay_active_orders', 'p50_max', 'int')}",
            "Nombre de campagnes de production encore bloquees en fin de jour. Cette lecture distingue le stock de reports du simple signal journalier de planification.",
        ),
        metric_card(
            "Pertes fiabilite fournisseur",
            f"P95 {format_stat(summary, 'total_unreliable_loss_qty', 'p95', 'qty')}",
            f"baseline {format_stat(summary, 'total_unreliable_loss_qty', 'baseline', 'qty')}",
            "Quantite perdue par fiabilite/OTIF fournisseur degradee dans les scenarios.",
        ),
        metric_card(
            "Appro amont mobilisee",
            f"P50 {format_stat(summary, 'total_external_procured_qty', 'p50', 'qty')}",
            f"P95 {format_stat(summary, 'total_external_procured_qty', 'p95', 'qty')}",
            "Quantite totale reconstituee via l'approvisionnement amont fournisseur. Elle mesure la resilience consommee par les scenarios.",
        ),
        metric_card(
            "Trajectoires",
            "disponibles" if trajectory_assets.get("available") else "non generees",
            (
                f"{trajectory_assets.get('stochastic_run_count') or 0} runs ; horizon {trajectory_horizon_label}"
                if trajectory_assets.get("available")
                else "relancer Monte Carlo avec --save-trajectories"
            ),
            "Les trajectoires permettent d'afficher toutes les courbes, leur enveloppe et la mediane. Le resume Monte Carlo seul ne contient que des KPI finaux.",
        ),
    ]
    secondary_cards_html = (
        "<section class=\"dataSummarySection\">"
        "<div class=\"dataSummarySectionTitle\">KPI secondaires et qualite du test</div>"
        "<div class=\"uncertaintyCardGrid\">"
        f"{''.join(secondary_cards)}"
        "</div>"
        "</section>"
    )

    distribution_rows = [
        ("Disponibilite produit", "fill_rate", "pct01"),
        ("Backlog final", "ending_backlog", "qty"),
        ("Cout total", "total_cost", "money"),
        ("Cout stockage", "total_inventory_cost_legacy_raw_holding", "money"),
        ("Production realisee", "total_produced", "qty"),
        ("Capacite fournisseur contrainte", "total_supplier_capacity_binding_qty", "qty"),
        ("Appro amont mobilisee", "total_external_procured_qty", "qty"),
        ("Pertes fiabilite fournisseur", "total_unreliable_loss_qty", "qty"),
        ("Appro amont rejetee", "total_external_procured_rejected_qty", "qty"),
    ]
    table_rows = []
    for label, metric, kind in distribution_rows:
        if not stat(summary, metric):
            continue
        table_rows.append(
            "<tr>"
            f"<td>{html.escape(label)}</td>"
            f"<td>{html.escape(format_stat(summary, metric, 'baseline', kind))}</td>"
            f"<td>{html.escape(format_stat(summary, metric, 'p05', kind))}</td>"
            f"<td>{html.escape(format_stat(summary, metric, 'p50', kind))}</td>"
            f"<td>{html.escape(format_stat(summary, metric, 'p95', kind))}</td>"
            f"<td>{html.escape(format_stat(summary, metric, 'max', kind))}</td>"
            "</tr>"
        )

    driver_targets = [
        ("kpi::fill_rate", "Facteurs qui expliquent la disponibilite produit"),
        ("kpi::total_cost", "Facteurs qui expliquent le cout total"),
        ("kpi::ending_backlog", "Facteurs qui expliquent le backlog"),
    ]
    driver_sections: list[str] = []
    rankings = summary.get("driver_rankings") or {}
    for target, title in driver_targets:
        rows = rankings.get(target) or []
        if not rows:
            continue
        driver_rows = []
        for row in rows[:8]:
            corr = as_float(row.get("correlation"), 0.0)
            direction = "augmente avec le KPI" if corr >= 0 else "fait baisser le KPI"
            raw_factor = str(row.get("factor") or "")
            driver_rows.append(
                "<tr>"
                f"<td>{html.escape(factor_label(raw_factor))}</td>"
                f"<td>{html.escape(factor_tested_range_text(raw_factor))}</td>"
                f"<td>{corr:+.2f}</td>"
                f"<td>{html.escape(direction)}</td>"
                "</tr>"
            )
        driver_sections.append(
            "<div class=\"orderLedgerSectionTitle\">"
            f"{html.escape(title)}"
            "</div>"
            "<div class=\"orderLedgerTableWrap\" tabindex=\"0\">"
            "<table class=\"kpiFormulaTable\"><thead><tr><th>Parametre aleatoire</th><th>Plage testee</th><th>Correlation</th><th>Lecture</th></tr></thead><tbody>"
            f"{''.join(driver_rows)}"
            "</tbody></table></div>"
        )

    hero_tooltip = "\n".join(
        [
            "Monte Carlo = plusieurs simulations rejouees avec des parametres tires aleatoirement autour du nominal.",
            "Baseline nominale conservee: elle sert de reference, elle n'est pas modifiee.",
            f"Runs valides = {runs}. Horizon = {days} jours. Seed = {seed}.",
        ]
    )
    driver_sections_html = (
        "".join(driver_sections)
        if driver_sections
        else '<div class="orderLedgerStatus">Pas assez de runs ou de variance pour classer les drivers.</div>'
    )

    threshold_rows_html = []
    for row in (diagnostics.get("threshold_probabilities") or [])[:12]:
        if not isinstance(row, dict):
            continue
        threshold_label = str(row.get("label") or "n/a").replace("Fill rate", "Disponibilite produit")
        threshold_rows_html.append(
            "<tr>"
            f"<td>{html.escape(threshold_label)}</td>"
            f"<td>{html.escape(display_kpi_label(row.get('metric_label') or row.get('metric') or 'n/a'))}</td>"
            f"<td>{html.escape(str(row.get('comparator') or ''))} {html.escape(threshold_value_text(row))}</td>"
            f"<td>{html.escape(pct01(row.get('probability'), 1))}</td>"
            "</tr>"
        )
    threshold_section_html = (
        "<section class=\"dataSummarySection\">"
        "<div class=\"dataSummarySectionTitle\">Probabilites de seuils metier</div>"
        "<div class=\"orderLedgerStatus\">Lecture: les seuils sont comptes run par run sur les scenarios valides. En profil stress, ce sont des frequences de test, pas des probabilites historiques.</div>"
        "<div class=\"orderLedgerTableWrap\" tabindex=\"0\">"
        "<table class=\"kpiFormulaTable\"><thead><tr><th>Seuil</th><th>KPI</th><th>Condition</th><th>Frequence</th></tr></thead><tbody>"
        f"{''.join(threshold_rows_html)}"
        "</tbody></table></div>"
        "</section>"
        if threshold_rows_html
        else ""
    )

    family_rows_html = []
    for row in (diagnostics.get("factor_family_impacts") or [])[:10]:
        if not isinstance(row, dict):
            continue
        top = row.get("top_driver") if isinstance(row.get("top_driver"), dict) else {}
        score = to_float(row.get("top_absolute_correlation")) or 0.0
        family_rows_html.append(
            "<tr>"
            f"<td>{html.escape(str(row.get('label') or row.get('family') or 'n/a'))}</td>"
            f"<td>{html.escape(fmt_pct(score * 100.0, 1))}</td>"
            f"<td>{html.escape(str(row.get('driver_count') or 0))}</td>"
            f"<td>{html.escape(str(top.get('label') or top.get('factor') or 'n/a'))}</td>"
            f"<td>{html.escape(factor_tested_range_text(top.get('factor')))}</td>"
            f"<td>{html.escape(display_kpi_label(top.get('target_label') or top.get('target') or 'n/a'))}</td>"
            f"<td>{html.escape(corr_text(to_float(top.get('correlation')) or 0.0))}</td>"
            "</tr>"
        )
    family_section_html = (
        "<section class=\"dataSummarySection\">"
        "<div class=\"dataSummarySectionTitle\">Familles de parametres les plus explicatives</div>"
        "<div class=\"orderLedgerStatus\">Lecture: classe les familles d'aleas qui expliquent le plus les ecarts entre runs. Utile pour savoir si le probleme vient plutot des stocks, des delais, des capacites ou de la demande.</div>"
        "<div class=\"orderLedgerTableWrap\" tabindex=\"0\">"
        "<table class=\"kpiFormulaTable\"><thead><tr><th>Famille</th><th>Lien max observe</th><th>Drivers</th><th>Driver principal</th><th>Plage testee</th><th>KPI explique</th><th>Corr.</th></tr></thead><tbody>"
        f"{''.join(family_rows_html)}"
        "</tbody></table></div>"
        "</section>"
        if family_rows_html
        else ""
    )

    propagation = diagnostics.get("uncertainty_propagation") if isinstance(diagnostics.get("uncertainty_propagation"), dict) else {}
    supplier_relative_rows_for_chart = []
    if propagation.get("available"):
        candidate_rows = propagation.get("top_supplier_relative_factors") or propagation.get("top_relative_factors") or []
        supplier_relative_rows_for_chart = candidate_rows if isinstance(candidate_rows, list) else []
    propagation_band_chart = propagation_band_chart_html(supplier_relative_rows_for_chart)
    propagation_rows_html = []
    if propagation.get("available"):
        for row in supplier_relative_rows_for_chart[:18]:
            if not isinstance(row, dict):
                continue
            rel = to_float(row.get("kpi_uncertainty_relative_to_baseline"))
            if rel is None or math.isnan(rel):
                continue
            rel_text = fmt_pct(rel * 100.0, 1)
            corr = to_float(row.get("correlation")) or 0.0
            r2 = to_float(row.get("r2")) or 0.0
            signed_delta = to_float(row.get("kpi_delta_for_input_uncertainty")) or 0.0
            direction_text = "KPI augmente" if signed_delta >= 0 else "KPI baisse"
            link_text = "lien positif" if corr >= 0 else "lien negatif"
            domain_text = (
                f"p05 {format_input_factor_value(row.get('input_p05'))} - "
                f"p95 {format_input_factor_value(row.get('input_p95'))}"
            )
            propagation_rows_html.append(
                "<tr>"
                f"<td>{html.escape(str(row.get('label') or row.get('factor') or 'n/a'))}</td>"
                f"<td>{html.escape(str(row.get('family_label') or 'n/a'))}</td>"
                f"<td>{html.escape(display_kpi_label(row.get('kpi_label') or row.get('kpi') or 'n/a'))}</td>"
                f"<td>{html.escape(pct01(row.get('input_relative_uncertainty'), 0))}</td>"
                f"<td>{html.escape(format_kpi_delta(str(row.get('kpi') or ''), row.get('kpi_uncertainty_abs')))}</td>"
                f"<td>{html.escape(direction_text)}</td>"
                f"<td>{html.escape(rel_text)}</td>"
                f"<td>{html.escape(propagation_transfer_text(row))}</td>"
                f"<td>{html.escape(f'{link_text} ({corr_text(corr)})')}</td>"
                f"<td>{html.escape(propagation_signal_text(corr, r2))}</td>"
                f"<td>{html.escape(domain_text)}</td>"
                f"<td>{html.escape(str(row.get('status_label') or 'n/a'))}</td>"
                "</tr>"
            )
    propagation_absolute_rows_html = []
    if propagation.get("available"):
        for row in (propagation.get("top_supplier_absolute_factors") or propagation.get("top_absolute_factors") or [])[:12]:
            if not isinstance(row, dict):
                continue
            corr = to_float(row.get("correlation")) or 0.0
            r2 = to_float(row.get("r2")) or 0.0
            signed_delta = to_float(row.get("kpi_delta_for_input_uncertainty")) or 0.0
            direction_text = "KPI augmente" if signed_delta >= 0 else "KPI baisse"
            link_text = "lien positif" if corr >= 0 else "lien negatif"
            domain_text = (
                f"p05 {format_input_factor_value(row.get('input_p05'))} - "
                f"p95 {format_input_factor_value(row.get('input_p95'))}"
            )
            propagation_absolute_rows_html.append(
                "<tr>"
                f"<td>{html.escape(str(row.get('label') or row.get('factor') or 'n/a'))}</td>"
                f"<td>{html.escape(str(row.get('family_label') or 'n/a'))}</td>"
                f"<td>{html.escape(display_kpi_label(row.get('kpi_label') or row.get('kpi') or 'n/a'))}</td>"
                f"<td>{html.escape(pct01(row.get('input_relative_uncertainty'), 0))}</td>"
                f"<td>{html.escape(format_kpi_delta(str(row.get('kpi') or ''), row.get('kpi_uncertainty_abs')))}</td>"
                f"<td>{html.escape(direction_text)}</td>"
                f"<td>{html.escape(f'{link_text} ({corr_text(corr)})')}</td>"
                f"<td>{html.escape(propagation_signal_text(corr, r2))}</td>"
                f"<td>{html.escape(domain_text)}</td>"
                f"<td>{html.escape(str(row.get('status_label') or 'n/a'))}</td>"
                "</tr>"
            )
    research_control_rows_html = []
    if propagation.get("available"):
        for row in (propagation.get("research_control_factors") or [])[:10]:
            if not isinstance(row, dict):
                continue
            rel = to_float(row.get("kpi_uncertainty_relative_to_baseline"))
            rel_text = "n/a" if rel is None or math.isnan(rel) else fmt_pct(rel * 100.0, 1)
            corr = to_float(row.get("correlation")) or 0.0
            r2 = to_float(row.get("r2")) or 0.0
            signed_delta = to_float(row.get("kpi_delta_for_input_uncertainty")) or 0.0
            direction_text = "KPI augmente" if signed_delta >= 0 else "KPI baisse"
            research_control_rows_html.append(
                "<tr>"
                f"<td>{html.escape(str(row.get('label') or row.get('factor') or 'n/a'))}</td>"
                f"<td>{html.escape(display_kpi_label(row.get('kpi_label') or row.get('kpi') or 'n/a'))}</td>"
                f"<td>{html.escape(format_kpi_delta(str(row.get('kpi') or ''), row.get('kpi_uncertainty_abs')))}</td>"
                f"<td>{html.escape(rel_text)}</td>"
                f"<td>{html.escape(propagation_transfer_text(row))}</td>"
                f"<td>{html.escape(direction_text)}</td>"
                f"<td>{html.escape(propagation_signal_text(corr, r2))}</td>"
                "</tr>"
            )
    propagation_absolute_section_html = (
        "<div class=\"dataSummarySectionTitle\">Impacts absolus sur KPI a nominal zero</div>"
        "<div class=\"orderLedgerStatus\">Ces KPI valent zero dans le nominal, par exemple backlog final, pertes ou capacite contrainte. On ne peut donc pas dire +40% versus zero; on affiche ce que l'incertitude peut creer en quantite absolue.</div>"
        "<div class=\"orderLedgerTableWrap\" tabindex=\"0\">"
        "<table class=\"kpiFormulaTable\"><thead><tr><th>Input incertain</th><th>Famille</th><th>KPI a zero nominal</th><th>Incertitude entree</th><th>Impact absolu estime</th><th>Sens si input +20%</th><th>Lien observe</th><th>Qualite du signal</th><th>Domaine MC observe</th><th>Lecture</th></tr></thead><tbody>"
        f"{''.join(propagation_absolute_rows_html)}"
        "</tbody></table></div>"
        if propagation_absolute_rows_html
        else ""
    )
    research_control_section_html = (
        "<div class=\"dataSummarySectionTitle\">Controles modele / recherche</div>"
        "<div class=\"orderLedgerStatus\">Ces lignes gardent les facteurs usine ou internes visibles pour validation scientifique. Dans cette etude, elles ne sont pas l'axe decisionnel principal si la capacite usine n'est pas atteinte; elles servent surtout a verifier que le modele ne confond pas une contrainte fournisseur avec une contrainte industrielle.</div>"
        "<div class=\"orderLedgerTableWrap\" tabindex=\"0\">"
        "<table class=\"kpiFormulaTable\"><thead><tr><th>Facteur controle</th><th>KPI sortie</th><th>Amplitude KPI estimee</th><th>Effet relatif</th><th>Propagation</th><th>Sens si input +20%</th><th>Qualite du signal</th></tr></thead><tbody>"
        f"{''.join(research_control_rows_html)}"
        "</tbody></table></div>"
        if research_control_rows_html
        else ""
    )
    propagation_section_html = (
        "<section class=\"dataSummarySection\">"
        "<div class=\"dataSummarySectionTitle\">Propagation d'incertitude entree -> KPI</div>"
        "<div class=\"orderLedgerStatus\">Lecture supplier-first: la synthese met d'abord les incertitudes fournisseur, car l'objectif metier est la prediction de risque fournisseur. Les facteurs usine restent disponibles plus bas comme controles modele/recherche, pas comme cause metier prioritaire quand la capacite usine n'est pas atteinte.</div>"
        "<div class=\"dataSummarySectionTitle\">Prediction fournisseur - propagation relative lisible</div>"
        f"{propagation_band_chart}"
        "<div class=\"orderLedgerTableWrap\" tabindex=\"0\">"
        "<table class=\"kpiFormulaTable\"><thead><tr><th>Input incertain</th><th>Famille</th><th>KPI sortie</th><th>Incertitude entree</th><th>Amplitude KPI estimee</th><th>Sens si input +20%</th><th>Effet relatif sur KPI</th><th>Propagation</th><th>Lien observe</th><th>Qualite du signal</th><th>Domaine MC observe</th><th>Lecture</th></tr></thead><tbody>"
        f"{''.join(propagation_rows_html)}"
        "</tbody></table></div>"
        f"{propagation_absolute_section_html}"
        f"{research_control_section_html}"
        "</section>"
        if propagation_rows_html
        else ""
    )

    propagation_by_kpi_html = []
    if propagation.get("available"):
        for metric, rows in (propagation.get("by_kpi") or {}).items():
            if metric not in {"kpi::fill_rate", "kpi::ending_backlog", "kpi::total_cost", "kpi::total_produced", "kpi::total_supplier_capacity_binding_qty", "kpi::total_external_procured_qty", "kpi::total_unreliable_loss_qty"}:
                continue
            if not isinstance(rows, list) or not rows:
                continue
            row = next(
                (
                    candidate
                    for candidate in rows
                    if isinstance(candidate, dict)
                    and candidate.get("business_scope") == "supplier_prediction"
                ),
                rows[0],
            )
            scope_note = ""
            if isinstance(row, dict) and row.get("business_scope") != "supplier_prediction":
                scope_note = " (controle modele)"
            propagation_by_kpi_html.append(
                "<div class=\"uncertaintyCard\">"
                f"<div class=\"uncertaintyCardLabel\">{html.escape(display_kpi_label(row.get('kpi_label') or metric))}</div>"
                f"<div class=\"uncertaintyCardValue\">{html.escape(format_kpi_delta(str(metric), row.get('kpi_uncertainty_abs')))}</div>"
                f"<div class=\"uncertaintyCardNote\">input cle: {html.escape(str(row.get('label') or row.get('factor') or 'n/a') + scope_note)}</div>"
                "</div>"
            )
    propagation_cards_html = (
        "<section class=\"dataSummarySection\">"
        "<div class=\"dataSummarySectionTitle\">KPI les plus sensibles a une incertitude fournisseur de 20%</div>"
        "<div class=\"uncertaintyCardGrid\">"
        f"{''.join(propagation_by_kpi_html)}"
        "</div>"
        "</section>"
        if propagation_by_kpi_html
        else ""
    )

    supplier_rows_html = []
    for row in (diagnostics.get("supplier_impacts") or [])[:12]:
        if not isinstance(row, dict):
            continue
        top = row.get("top_driver") if isinstance(row.get("top_driver"), dict) else {}
        score = to_float(row.get("score")) or 0.0
        supplier_rows_html.append(
            "<tr>"
            f"<td>{html.escape(str(row.get('supplier_id') or 'n/a'))}</td>"
            f"<td>{html.escape(str(top.get('family_label') or 'n/a'))}</td>"
            f"<td>{html.escape(factor_tested_range_text(top.get('factor')))}</td>"
            f"<td>{html.escape(display_kpi_label(top.get('target_label') or top.get('target') or 'n/a'))}</td>"
            f"<td>{html.escape(fmt_pct(score * 100.0, 1))}</td>"
            f"<td>{html.escape(corr_text(to_float(top.get('correlation')) or 0.0))}</td>"
            f"<td>{html.escape(str(row.get('driver_count') or 0))}</td>"
            "</tr>"
        )
    supplier_section_html = (
        "<section class=\"dataSummarySection\">"
        "<div class=\"dataSummarySectionTitle\">Fournisseurs et noeuds a prioriser</div>"
        "<div class=\"orderLedgerStatus\">Lecture: le lien KPI observe n'est pas une variation directe du KPI. Il indique a quel point la variation testee du parametre explique les ecarts entre runs Monte Carlo.</div>"
        "<div class=\"orderLedgerTableWrap\" tabindex=\"0\">"
        "<table class=\"kpiFormulaTable\"><thead><tr><th>Fournisseur/noeud</th><th>Type d'alea</th><th>Plage testee</th><th>KPI explique</th><th>Lien max observe</th><th>Corr.</th><th>Drivers</th></tr></thead><tbody>"
        f"{''.join(supplier_rows_html)}"
        "</tbody></table></div>"
        "</section>"
        if supplier_rows_html
        else ""
    )

    def top_driver_for_kpi(metric: str) -> dict[str, Any]:
        rankings_payload = diagnostics.get("driver_rankings") if isinstance(diagnostics.get("driver_rankings"), dict) else {}
        by_kpi = rankings_payload.get("by_kpi") if isinstance(rankings_payload.get("by_kpi"), dict) else {}
        rows = by_kpi.get(metric) if isinstance(by_kpi.get(metric), list) else []
        for row in rows:
            if isinstance(row, dict) and row.get("business_scope") != "research_control":
                return row
        return rows[0] if rows and isinstance(rows[0], dict) else {}

    def short_driver_card(title: str, metric: str, objective: str) -> str:
        row = top_driver_for_kpi(metric)
        if not row:
            return metric_card(title, "n/a", "pas de driver lisible")
        corr = to_float(row.get("correlation")) or 0.0
        return metric_card(
            title,
            str(row.get("label") or row.get("factor") or "n/a"),
            f"{objective} ; corr. {corr_text(corr)}",
        )

    def action_for_driver(row: dict[str, Any]) -> tuple[str, str]:
        family = str(row.get("family") or "")
        factor = str(row.get("factor") or "")
        label = str(row.get("label") or row.get("factor") or "n/a")
        if family == "supplier_lead" or "lead" in factor:
            return "Reduire ou securiser le delai fournisseur", f"Tester delai reduit, transport prioritaire ou source plus proche pour {label}."
        if family == "supplier_stock" or "stock" in factor:
            return "Renforcer stock amont fournisseur", f"Tester stock de securite, stock consigne ou reconstitution plus rapide pour {label}."
        if family == "supplier_capacity" or "capacity" in factor:
            return "Reserver ou diversifier la capacite fournisseur", f"Tester capacite reservee, seconde source ou plafond appro plus haut pour {label}."
        if family == "supplier_reliability" or "reliability" in factor:
            return "Ameliorer fiabilite fournisseur", f"Tester OTIF plus eleve, double sourcing ou controle qualite renforce pour {label}."
        if "external_procurement" in factor:
            return "Renforcer l'approvisionnement amont", f"Tester capacite/delai appro amont plus robuste pour {label}."
        return "Tester mitigation ciblee", f"Construire un scenario de mitigation sur {label} et comparer disponibilite, cout et nervosite."

    decision_cards_html = (
        "<section class=\"dataSummarySection\">"
        "<div class=\"dataSummarySectionTitle\">Synthese decisionnelle Monte Carlo</div>"
        "<div class=\"orderLedgerStatus\">Lecture: priorise les causes d'incertitude qui expliquent les ecarts entre runs. Les courbes ci-dessous montrent ensuite quand ces causes se propagent dans le temps.</div>"
        "<div class=\"uncertaintyCardGrid\">"
        f"{short_driver_card('Disponibilite produit', 'kpi::fill_rate', 'a proteger')}"
        f"{short_driver_card('Backlog client', 'kpi::ending_backlog', 'a eviter')}"
        f"{short_driver_card('Cout supply', 'kpi::total_cost', 'a maitriser')}"
        f"{short_driver_card('Capacite fournisseur', 'kpi::total_supplier_capacity_binding_qty', 'a surveiller')}"
        "</div>"
        "</section>"
    )

    mitigation_rows_html = []
    seen_actions: set[tuple[str, str]] = set()
    supplier_impacts = diagnostics.get("supplier_impacts") if isinstance(diagnostics.get("supplier_impacts"), list) else []
    driver_sources = []
    for row in supplier_impacts[:8]:
        if isinstance(row, dict) and isinstance(row.get("top_driver"), dict):
            driver_sources.append(row.get("top_driver") or {})
    for metric in ["kpi::fill_rate", "kpi::ending_backlog", "kpi::total_cost"]:
        driver = top_driver_for_kpi(metric)
        if driver:
            driver_sources.append(driver)
    for row in driver_sources:
        action, test = action_for_driver(row)
        key = (action, str(row.get("label") or row.get("factor") or ""))
        if key in seen_actions:
            continue
        seen_actions.add(key)
        mitigation_rows_html.append(
            "<tr>"
            f"<td>{html.escape(str(row.get('label') or row.get('factor') or 'n/a'))}</td>"
            f"<td>{html.escape(display_kpi_label(row.get('target_label') or row.get('kpi_label') or 'KPI'))}</td>"
            f"<td>{html.escape(action)}</td>"
            f"<td>{html.escape(test)}</td>"
            "</tr>"
        )
        if len(mitigation_rows_html) >= 8:
            break
    mitigation_section_html = (
        "<section class=\"dataSummarySection\">"
        "<div class=\"dataSummarySectionTitle\">Actions de mitigation a comparer</div>"
        "<div class=\"orderLedgerStatus\">Lecture: propositions issues des drivers Monte Carlo. La decision doit se faire en comparant des scenarios avant/apres: disponibilite produit, backlog, cout, stock consomme et nervosite production.</div>"
        "<div class=\"orderLedgerTableWrap\" tabindex=\"0\">"
        "<table class=\"kpiFormulaTable\"><thead><tr><th>Cause prioritaire</th><th>KPI touche</th><th>Action a tester</th><th>Scenario de comparaison</th></tr></thead><tbody>"
        f"{''.join(mitigation_rows_html)}"
        "</tbody></table></div>"
        "<button id=\"uncertaintyScenarioCompareBtn\" class=\"tableBtn\" type=\"button\">Comparer les scenarios disponibles</button>"
        "</section>"
        if mitigation_rows_html
        else ""
    )

    def driver_label(row: dict[str, Any] | None) -> str:
        if not isinstance(row, dict) or not row:
            return "aucun driver lisible"
        return str(row.get("label") or row.get("factor") or "n/a")

    def driver_family_label(row: dict[str, Any] | None) -> str:
        if not isinstance(row, dict) or not row:
            return "n/a"
        return str(row.get("family_label") or row.get("family") or "n/a")

    def driver_target_label(row: dict[str, Any] | None) -> str:
        if not isinstance(row, dict) or not row:
            return "n/a"
        return display_kpi_label(row.get("target_label") or row.get("kpi_label") or row.get("target") or "KPI")

    def supplier_priority(score: float) -> str:
        if score >= 0.75:
            return "P1 action"
        if score >= 0.65:
            return "P2 qualification"
        return "P3 surveillance"

    service_driver = top_driver_for_kpi("kpi::fill_rate")
    backlog_driver = top_driver_for_kpi("kpi::ending_backlog")
    supplier_binding_driver = top_driver_for_kpi("kpi::total_supplier_capacity_binding_qty")
    cost_driver = top_driver_for_kpi("kpi::total_cost")
    top_supplier_row = next((row for row in supplier_impacts if isinstance(row, dict)), {})
    top_supplier_driver = top_supplier_row.get("top_driver") if isinstance(top_supplier_row.get("top_driver"), dict) else {}
    top_supplier_action, top_supplier_test = action_for_driver(top_supplier_driver or service_driver)

    business_agent_cards_html = "".join(
        [
            metric_card(
                "Agent disponibilite produit",
                f"Disponibilite P05 {format_stat(summary, 'fill_rate', 'p05', 'pct01')}",
                f"Alerte si disponibilite/backlog se degradent. Cause prioritaire: {driver_label(service_driver)}.",
            ),
            metric_card(
                "Agent achats fournisseurs",
                str(top_supplier_row.get("supplier_id") or "top fournisseur n/a"),
                f"{top_supplier_action}. Driver: {driver_family_label(top_supplier_driver)}.",
            ),
            metric_card(
                "Agent planning production",
                f"Reports P95 {format_trajectory_value('production_reports', 'p95_max', 'qty')}",
                f"Suit les lots reportes et la nervosite MRP. Cause supply: {driver_label(backlog_driver or supplier_binding_driver)}.",
            ),
            metric_card(
                "Agent finance / arbitrage",
                f"Cout P95 {format_stat(summary, 'total_cost', 'p95', 'money')}",
                f"Compare mitigations cout-disponibilite. Driver cout: {driver_label(cost_driver)}.",
            ),
        ]
    )

    business_supplier_rows_html = []
    for row in supplier_impacts[:6]:
        if not isinstance(row, dict):
            continue
        top = row.get("top_driver") if isinstance(row.get("top_driver"), dict) else {}
        score = to_float(row.get("score")) or 0.0
        action, _test = action_for_driver(top)
        business_supplier_rows_html.append(
            "<tr>"
            f"<td>{html.escape(supplier_priority(score))}</td>"
            f"<td>{html.escape(str(row.get('supplier_id') or 'n/a'))}</td>"
            f"<td>{html.escape(driver_family_label(top))}</td>"
            f"<td>{html.escape(factor_tested_range_text(top.get('factor')))}</td>"
            f"<td>{html.escape(driver_target_label(top))}</td>"
            f"<td>{html.escape(fmt_pct(score * 100.0, 1))}</td>"
            f"<td>{html.escape(action)}</td>"
            "</tr>"
        )
    business_supplier_table_html = (
        "<div class=\"orderLedgerTableWrap\" tabindex=\"0\">"
        "<table class=\"kpiFormulaTable\"><thead><tr><th>Priorite</th><th>Fournisseur/noeud</th><th>Cause simulee</th><th>Plage testee</th><th>KPI touche</th><th>Lien KPI observe</th><th>Action metier</th></tr></thead><tbody>"
        f"{''.join(business_supplier_rows_html)}"
        "</tbody></table></div>"
        if business_supplier_rows_html
        else "<div class=\"panelEmptyState\">Aucun fournisseur prioritaire lisible dans ce resume Monte Carlo.</div>"
    )
    business_agent_section_html = (
        "<section class=\"dataSummarySection\">"
        "<div class=\"dataSummarySectionTitle\">Cellule supply - priorites par agent metier</div>"
        "<div class=\"orderLedgerStatus\">Lecture: cette section force l'ordre de decision: disponibilite produit, backlog, reports de production, cause fournisseur, action a tester. Les statistiques detaillees restent plus bas comme preuves, pas comme premier niveau de pilotage.</div>"
        "<div class=\"uncertaintyCardGrid\">"
        f"{business_agent_cards_html}"
        "</div>"
        "<div class=\"dataSummarySectionTitle\">Top fournisseurs a traiter</div>"
        f"{business_supplier_table_html}"
        "</section>"
    )

    paired_propagation = summary.get("paired_propagation") if isinstance(summary.get("paired_propagation"), dict) else {}
    if paired_propagation.get("enabled") and paired_propagation.get("method") == "paired_controlled_runs":
        # The controlled paired envelopes shown in the curves tab supersede the
        # former mixed-Monte-Carlo regression approximation. Keep the detailed
        # dashboard concise and avoid presenting two incompatible methods as if
        # they measured the same quantity.
        propagation_cards_html = ""
        propagation_section_html = ""

    html_body = (
        "<div class=\"factoryHtmlPanelContent dataSummaryPanelContent monteCarloPanelContent\">"
        f"<div class=\"{html_tooltip_class(f'uncertaintyDashboard sensitivityStatus-{status_cls}', hero_tooltip)}\"{html_tooltip_attrs(hero_tooltip)}>"
        "<div class=\"uncertaintyHero\">"
        f"<div class=\"sensitivityStatusPill\">{html.escape(status_label)}</div>"
        "<div class=\"uncertaintyHeroTitle\">Incertitude dynamique - Monte Carlo</div>"
        "<div class=\"uncertaintyHeroText\">Cette lecture rejoue la simulation avec des aleas controles. La synthese est supplier-first pour la prediction fournisseur; les capacites usines restent dans les details comme controles modele/recherche. Elle mesure la robustesse de la baseline, pas une probabilite historique fournisseur.</div>"
        "</div>"
        "<div class=\"uncertaintyHeroFacts\">"
        f"<div><span>Runs valides</span><b>{runs}</b></div>"
        f"<div><span>Horizon teste</span><b>{days} j</b></div>"
        f"<div><span>Profil</span><b>{html.escape(profile)}</b></div>"
        f"<div><span>Runs en echec</span><b>{failed}</b></div>"
        "</div>"
        "<div class=\"uncertaintyCardGrid\">"
        f"{''.join(cards)}"
        "</div>"
        "</div>"
        f"{business_agent_section_html}"
        f"{mitigation_section_html}"
        "<div id=\"monteCarloDynamicChartsAnchor\"></div>"
        "<details class=\"dataSummarySection\">"
        "<summary class=\"dataSummarySectionTitle\">Details KPI, propagation et modele Monte Carlo</summary>"
        f"{decision_cards_html}"
        f"{secondary_cards_html}"
        "<section class=\"dataSummarySection\">"
        "<div class=\"dataSummarySectionTitle\">Distribution des KPI metier</div>"
        "<div class=\"orderLedgerTableWrap\" tabindex=\"0\">"
        "<table class=\"kpiFormulaTable\"><thead><tr><th>KPI</th><th>Baseline</th><th>P05</th><th>P50</th><th>P95</th><th>Max</th></tr></thead><tbody>"
        f"{''.join(table_rows)}"
        "</tbody></table></div>"
        "</section>"
        f"{propagation_cards_html}"
        f"{propagation_section_html}"
        f"{threshold_section_html}"
        "<div class=\"dataSummarySectionTitle\">Drivers observes dans les runs</div>"
        "<div class=\"orderLedgerStatus\">La correlation indique quels parametres aleatoires expliquent le plus les ecarts entre scenarios. Ce n'est pas une causalite terrain; c'est une lecture du modele rejoue.</div>"
        f"{driver_sections_html}"
        f"{family_section_html}"
        f"{supplier_section_html}"
        "</details>"
        "</div>"
    )
    return {
        "available": True,
        "summary_json": str(summary_json),
        "html": html_body,
        "runs": runs,
        "days": days,
        "service_risk": round(service_risk, 6),
        "backlog_risk": round(backlog_risk, 6),
        "cost_risk": round(cost_risk, 6),
        "fill_rate_p05": fill_stat.get("p05"),
        "backlog_p95": backlog_stat.get("p95"),
        "total_cost_p95": cost_stat.get("p95"),
        "inventory_cost_p95": inv_cost_stat.get("p95"),
        "supplier_capacity_binding_p95": supplier_binding_stat.get("p95"),
        "nodes": mc_nodes,
        "node_assets": mc_node_assets,
        "trajectory_assets": trajectory_assets,
        "diagnostics": diagnostics,
    }


def build_supplier_local_criticality(
    raw: dict[str, Any],
    supplier_shipments_csv: Path,
    supplier_stocks_csv: Path,
    supplier_capacity_csv: Path,
    production_constraint_csv: Path,
    sensitivity_cases_csv: Path,
    structural_sensitivity_cases_csv: Path,
    supplier_audits: dict[str, dict[str, Any]] | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, Any]]:
    supplier_audits = supplier_audits or {}
    nodes = raw.get("nodes", []) or []
    edges = raw.get("edges", []) or []
    supplier_ids = sorted(str(n.get("id")) for n in nodes if str(n.get("type") or "") == "supplier_dc")
    node_name = {str(n.get("id")): str(n.get("name") or str(n.get("id"))) for n in nodes}
    supplier_has_explicit_capacity = {
        str(n.get("id")): any(
            to_float(((proc.get("capacity") or {}).get("max_rate"))) not in (None, 0.0)
            and (to_float(((proc.get("capacity") or {}).get("max_rate"))) or 0.0) > 0.0
            for proc in (n.get("processes") or [])
        )
        for n in nodes
        if str(n.get("type") or "") == "supplier_dc"
    }
    supplier_nominal_capacity_by_supplier: dict[str, float] = {}
    supplier_capacity_basis_by_supplier: dict[str, str] = {}
    supplier_capacity_scale_by_supplier: dict[str, float] = {}
    for n in nodes:
        if str(n.get("type") or "") != "supplier_dc":
            continue
        supplier_id = str(n.get("id") or "")
        constraints = n.get("simulation_constraints") or {}
        item_caps = constraints.get("supplier_item_capacity_qty_per_day") or {}
        item_basis = constraints.get("supplier_item_capacity_basis") or {}
        capacity_scale = max(0.0, to_float(constraints.get("supplier_capacity_scale")) or 0.0)
        supplier_capacity_scale_by_supplier[supplier_id] = capacity_scale
        if isinstance(item_caps, dict) and item_caps:
            supplier_nominal_capacity_by_supplier[supplier_id] = max(
                max(0.0, to_float(value) or 0.0) for value in item_caps.values()
            )
        if isinstance(item_basis, dict) and item_basis:
            basis_values = sorted({str(value) for value in item_basis.values() if str(value).strip()})
            supplier_capacity_basis_by_supplier[supplier_id] = ", ".join(basis_values)
    incoming_items, outgoing_items = build_edge_item_sets(raw)
    edges_by_src: dict[str, list[dict[str, Any]]] = defaultdict(list)
    suppliers_for_pair: dict[tuple[str, str], set[str]] = defaultdict(set)
    target_share_by_supplier_pair: dict[tuple[str, tuple[str, str]], float] = {}
    supplier_initial_total: dict[str, float] = {}
    for n in nodes:
        if str(n.get("type") or "") != "supplier_dc":
            continue
        supplier_initial_total[str(n.get("id"))] = sum(
            max(0.0, to_float((st or {}).get("initial")) or 0.0)
            for st in ((n.get("inventory") or {}).get("states") or [])
        )
    for e in edges:
        src = str(e.get("from") or "")
        dst = str(e.get("to") or "")
        if src:
            edges_by_src[src].append(e)
        for item_id in e.get("items") or []:
            suppliers_for_pair[(dst, str(item_id))].add(src)

    def edge_transport_cost(edge: dict[str, Any]) -> float:
        tc = edge.get("transport_cost") or {}
        val = to_float((tc or {}).get("value"))
        if val is not None and val > 0:
            return val
        distance = to_float(edge.get("distance_km"))
        return max(0.02, (distance or 0.0) * 0.00008)

    def edge_lead_days(edge: dict[str, Any]) -> float:
        return max(1.0, to_float(((edge.get("lead_time") or {}).get("mean"))) or 1.0)

    def mrp_split_shares(count: int) -> list[float]:
        if count <= 0:
            return []
        if count == 1:
            return [1.0]
        if count == 2:
            return [0.7, 0.3]
        if count == 3:
            return [0.7, 0.2, 0.1]
        tail = 0.1 / float(count - 2)
        return [0.7, 0.2] + [tail] * (count - 2)

    edges_by_pair: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for edge in edges:
        dst = str(edge.get("to") or "")
        src = str(edge.get("from") or "")
        if not dst or not src:
            continue
        for item_id in edge.get("items") or []:
            edges_by_pair[(dst, str(item_id))].append(edge)
    for pair, pair_edges in edges_by_pair.items():
        sorted_edges = sorted(
            pair_edges,
            key=lambda edge: (
                edge_transport_cost(edge),
                edge_lead_days(edge),
                str(edge.get("from") or ""),
            ),
        )
        shares = mrp_split_shares(len(sorted_edges))
        for edge, share in zip(sorted_edges, shares):
            target_share_by_supplier_pair[(str(edge.get("from") or ""), pair)] = share

    avg_procurement_lead_days_by_supplier: dict[str, float] = {}
    for supplier_id, supplier_edges in edges_by_src.items():
        lead_values = [edge_lead_days(edge) for edge in supplier_edges if str(edge.get("from") or "") == supplier_id]
        avg_procurement_lead_days_by_supplier[supplier_id] = (
            sum(lead_values) / len(lead_values) if lead_values else 0.0
        )

    shipment_rows = read_csv_rows(supplier_shipments_csv)
    stock_rows = read_csv_rows(supplier_stocks_csv)
    capacity_rows = read_csv_rows(supplier_capacity_csv)
    constraint_rows = read_csv_rows(production_constraint_csv)
    sensitivity_case_rows = read_csv_rows(sensitivity_cases_csv)
    structural_case_rows = read_csv_rows(structural_sensitivity_cases_csv)
    by_case_std = case_rows_by_id(sensitivity_case_rows)
    by_case_struct = case_rows_by_id(structural_case_rows)
    baseline_std = by_case_std.get("baseline")
    baseline_struct = by_case_struct.get("baseline")

    shipped_qty_by_supplier: dict[str, float] = defaultdict(float)
    shipped_qty_by_supplier_pair: dict[tuple[str, tuple[str, str]], float] = defaultdict(float)
    total_pair_flow_qty: dict[tuple[str, str], float] = defaultdict(float)
    active_days_by_supplier: dict[str, set[int]] = defaultdict(set)
    first_day_by_supplier: dict[str, int] = {}
    last_day_by_supplier: dict[str, int] = {}
    for row in shipment_rows:
        src = str(row.get("src_node_id") or "")
        dst = str(row.get("dst_node_id") or "")
        item_id = str(row.get("item_id") or "")
        qty = max(0.0, to_float(row.get("shipped_qty")) or 0.0)
        day = int(to_float(row.get("day")) or 0)
        if not src:
            continue
        shipped_qty_by_supplier[src] += qty
        if dst and item_id:
            pair = (dst, item_id)
            shipped_qty_by_supplier_pair[(src, pair)] += qty
            total_pair_flow_qty[pair] += qty
        if qty > 0:
            active_days_by_supplier[src].add(day)
            first_day_by_supplier[src] = min(first_day_by_supplier.get(src, day), day)
            last_day_by_supplier[src] = max(last_day_by_supplier.get(src, day), day)

    avg_stock_by_supplier: dict[str, float] = defaultdict(float)
    min_stock_by_supplier: dict[str, float] = {}
    stock_count_by_supplier: dict[str, int] = defaultdict(int)
    for row in stock_rows:
        node_id = str(row.get("node_id") or "")
        val = max(0.0, to_float(row.get("stock_end_of_day")) or 0.0)
        avg_stock_by_supplier[node_id] += val
        stock_count_by_supplier[node_id] += 1
        min_stock_by_supplier[node_id] = min(min_stock_by_supplier.get(node_id, val), val)
    for supplier_id, total in list(avg_stock_by_supplier.items()):
        count = max(1, stock_count_by_supplier.get(supplier_id, 0))
        avg_stock_by_supplier[supplier_id] = total / count

    avg_capacity_utilization_by_supplier: dict[str, float] = defaultdict(float)
    max_capacity_utilization_by_supplier: dict[str, float] = defaultdict(float)
    capacity_count_by_supplier: dict[str, int] = defaultdict(int)
    for row in capacity_rows:
        node_id = str(row.get("node_id") or "")
        util = max(0.0, to_float(row.get("utilization")) or 0.0)
        avg_capacity_utilization_by_supplier[node_id] += util
        capacity_count_by_supplier[node_id] += 1
        max_capacity_utilization_by_supplier[node_id] = max(
            max_capacity_utilization_by_supplier.get(node_id, 0.0),
            util,
        )
    for supplier_id, total in list(avg_capacity_utilization_by_supplier.items()):
        count = max(1, capacity_count_by_supplier.get(supplier_id, 0))
        avg_capacity_utilization_by_supplier[supplier_id] = total / count

    shortage_qty_by_item: dict[str, float] = defaultdict(float)
    shortage_events_by_item: dict[str, int] = defaultdict(int)
    for row in constraint_rows:
        if str(row.get("binding_cause") or "") != "input_shortage":
            continue
        item_id = str(row.get("binding_input_item_id") or "")
        if not item_id:
            continue
        shortage_qty_by_item[item_id] += max(0.0, to_float(row.get("shortfall_vs_desired_qty")) or 0.0)
        shortage_events_by_item[item_id] += 1

    total_shipped_all = sum(shipped_qty_by_supplier.values())
    max_active_days = max((len(days) for days in active_days_by_supplier.values()), default=1)

    def normalize_map(values: dict[str, float], log_scale: bool = False) -> dict[str, float]:
        transformed: dict[str, float] = {}
        for key, value in values.items():
            transformed[key] = math.log1p(value) if log_scale else value
        max_value = max(transformed.values(), default=0.0)
        if max_value <= 0:
            return {key: 0.0 for key in values}
        return {key: transformed.get(key, 0.0) / max_value for key in values}

    raw_metrics: dict[str, dict[str, float]] = {}
    for supplier_id in supplier_ids:
        supplied_items = sorted(outgoing_items.get(supplier_id, set()))
        dest_nodes = sorted({str(e.get("to") or "") for e in edges_by_src.get(supplier_id, []) if e.get("to") is not None})
        sole_source_pairs = 0
        shared_source_pairs = 0
        for e in edges_by_src.get(supplier_id, []):
            dst = str(e.get("to") or "")
            for item_id in e.get("items") or []:
                pair_suppliers = suppliers_for_pair.get((dst, str(item_id)), set())
                if len(pair_suppliers) <= 1:
                    sole_source_pairs += 1
                else:
                    shared_source_pairs += 1
        shortage_supported_qty = sum(shortage_qty_by_item.get(item_id, 0.0) for item_id in supplied_items)
        shortage_supported_events = sum(shortage_events_by_item.get(item_id, 0) for item_id in supplied_items)
        std_label, std_short, std_low, std_high, std_fill_impact, std_backlog_impact = select_best_supplier_case_pair(
            by_case_std,
            baseline_std,
            supplier_id,
        )
        struct_label, struct_short, struct_low, struct_high, struct_fill_impact, struct_backlog_impact = (
            select_best_supplier_case_pair(by_case_struct, baseline_struct, supplier_id)
        )
        raw_metrics[supplier_id] = {
            "total_shipped_qty": shipped_qty_by_supplier.get(supplier_id, 0.0),
            "active_days": float(len(active_days_by_supplier.get(supplier_id, set()))),
            "sole_source_pairs": float(sole_source_pairs),
            "shared_source_pairs": float(shared_source_pairs),
            "shortage_supported_qty": shortage_supported_qty,
            "shortage_supported_events": float(shortage_supported_events),
            "standard_fill_impact": std_fill_impact,
            "structural_fill_impact": struct_fill_impact,
            "standard_backlog_impact": std_backlog_impact,
            "structural_backlog_impact": struct_backlog_impact,
        }

    volume_score = normalize_map({k: v["total_shipped_qty"] for k, v in raw_metrics.items()}, log_scale=True)
    shortage_score = normalize_map({k: v["shortage_supported_qty"] for k, v in raw_metrics.items()}, log_scale=True)
    sole_source_score = normalize_map({k: v["sole_source_pairs"] for k, v in raw_metrics.items()})
    standard_system_score = normalize_map(
        {k: v["standard_fill_impact"] * 100.0 + v["standard_backlog_impact"] / 100.0 for k, v in raw_metrics.items()}
    )
    structural_system_score = normalize_map(
        {k: v["structural_fill_impact"] * 100.0 + v["structural_backlog_impact"] / 100.0 for k, v in raw_metrics.items()}
    )

    metrics_by_supplier: dict[str, Any] = {}
    ranking_rows: list[dict[str, Any]] = []
    for supplier_id in supplier_ids:
        supplied_items = sorted(outgoing_items.get(supplier_id, set()))
        dest_nodes = sorted({str(e.get("to") or "") for e in edges_by_src.get(supplier_id, []) if e.get("to") is not None})
        item_labels = ", ".join(item.split(":", 1)[-1] for item in supplied_items[:5])
        if len(supplied_items) > 5:
            item_labels += ", ..."
        total_shipped_qty = shipped_qty_by_supplier.get(supplier_id, 0.0)
        active_days = len(active_days_by_supplier.get(supplier_id, set()))
        served_pairs = sorted(
            {
                pair
                for (src, pair), qty in shipped_qty_by_supplier_pair.items()
                if src == supplier_id and qty > 1e-9
            }
        )
        all_supported_pairs = sorted(
            {
                (str(e.get("to") or ""), str(item_id))
                for e in edges_by_src.get(supplier_id, [])
                for item_id in (e.get("items") or [])
                if e.get("to") is not None
            }
        )
        observed_share_den = sum(total_pair_flow_qty.get(pair, 0.0) for pair in all_supported_pairs)
        observed_share_num = sum(shipped_qty_by_supplier_pair.get((supplier_id, pair), 0.0) for pair in all_supported_pairs)
        observed_sourcing_share = (observed_share_num / observed_share_den) if observed_share_den > 1e-9 else 0.0
        target_share_weighted_num = sum(
            target_share_by_supplier_pair.get((supplier_id, pair), 0.0) * total_pair_flow_qty.get(pair, 0.0)
            for pair in all_supported_pairs
        )
        target_sourcing_share = (target_share_weighted_num / observed_share_den) if observed_share_den > 1e-9 else 0.0
        local_score = (
            0.35 * volume_score.get(supplier_id, 0.0)
            + 0.20 * (active_days / max_active_days if max_active_days > 0 else 0.0)
            + 0.25 * sole_source_score.get(supplier_id, 0.0)
            + 0.20 * shortage_score.get(supplier_id, 0.0)
        )
        system_score = 0.5 * standard_system_score.get(supplier_id, 0.0) + 0.5 * structural_system_score.get(supplier_id, 0.0)
        structural_criticality_score = 0.55 * local_score + 0.45 * system_score
        audit = supplier_audits.get(supplier_id)
        audit_criticality_score = supplier_audit_score(audit)
        # Keep the operational ranking comparable across the whole supplier
        # population. Audit and proxy values are displayed alongside it and do
        # not silently change the rank when coverage differs by supplier.
        overall_score = structural_criticality_score
        std_label, _std_short, _std_low, _std_high, std_fill_impact, std_backlog_impact = select_best_supplier_case_pair(
            by_case_std,
            baseline_std,
            supplier_id,
        )
        struct_label, _struct_short, _struct_low, _struct_high, struct_fill_impact, struct_backlog_impact = (
            select_best_supplier_case_pair(by_case_struct, baseline_struct, supplier_id)
        )
        row = {
            "supplier_id": supplier_id,
            "supplier_name": node_name.get(supplier_id, supplier_id),
            "items_supplied_count": len(supplied_items),
            "dest_nodes_count": len(dest_nodes),
            "sole_source_pairs": int(raw_metrics[supplier_id]["sole_source_pairs"]),
            "shared_source_pairs": int(raw_metrics[supplier_id]["shared_source_pairs"]),
            "total_shipped_qty": round(total_shipped_qty, 4),
            "active_days": active_days,
            "first_shipment_day": first_day_by_supplier.get(supplier_id, ""),
            "last_shipment_day": last_day_by_supplier.get(supplier_id, ""),
            "initial_stock_total": round(supplier_initial_total.get(supplier_id, 0.0), 4),
            "avg_stock_end_of_day": round(avg_stock_by_supplier.get(supplier_id, 0.0), 4),
            "min_stock_end_of_day": round(min_stock_by_supplier.get(supplier_id, 0.0), 4),
            "avg_capacity_utilization": round(avg_capacity_utilization_by_supplier.get(supplier_id, 0.0), 6),
            "max_capacity_utilization": round(max_capacity_utilization_by_supplier.get(supplier_id, 0.0), 6),
            "observed_sourcing_share": round(observed_sourcing_share, 6),
            "target_sourcing_share": round(target_sourcing_share, 6),
            "avg_procurement_lead_days": round(avg_procurement_lead_days_by_supplier.get(supplier_id, 0.0), 4),
            "capacity_metric_mode": "explicit_capacity" if supplier_has_explicit_capacity.get(supplier_id, False) else "sourcing_share",
            "shortage_supported_qty": round(raw_metrics[supplier_id]["shortage_supported_qty"], 4),
            "shortage_supported_events": int(raw_metrics[supplier_id]["shortage_supported_events"]),
            "standard_best_driver": std_label,
            "standard_fill_impact": round(std_fill_impact, 6),
            "standard_backlog_impact": round(std_backlog_impact, 4),
            "structural_best_driver": struct_label,
            "structural_fill_impact": round(struct_fill_impact, 6),
            "structural_backlog_impact": round(struct_backlog_impact, 4),
            "local_criticality_score": round(local_score, 6),
            "system_criticality_score": round(system_score, 6),
            "structural_criticality_score": round(structural_criticality_score, 6),
            "audit_criticality_score": round(audit_criticality_score, 6) if audit_criticality_score is not None else "",
            "audit_criterion_count": int((audit or {}).get("criterion_count") or 0),
            "audit_answered_criterion_count": int((audit or {}).get("answered_criterion_count") or 0),
            "audit_status": str((audit or {}).get("audit_status") or "not_available"),
            "overall_criticality_score": round(overall_score, 6),
            "indicative_adjusted_score": round(
                blend_criticality_with_audit(structural_criticality_score, audit), 6
            ),
            "top_items_preview": item_labels,
            "destinations_preview": ", ".join(dest_nodes[:4]) + (", ..." if len(dest_nodes) > 4 else ""),
        }
        ranking_rows.append(row)
        first_day = row["first_shipment_day"]
        last_day = row["last_shipment_day"]
        shipment_window = f"J{first_day} -> J{last_day}" if first_day != "" and last_day != "" else "aucun flux"
        summary_lines = [
            metric_label_value("Rang local", ""),
            metric_label_value("Statut flux", "actif" if total_shipped_qty > 1e-9 else "sans expedition simulee"),
            metric_label_value("Flux expedie total", f"{row['total_shipped_qty']:.2f}"),
            metric_label_value("Fenetre expeditions", shipment_window),
            metric_label_value("Jours avec expedition", str(row["active_days"])),
            metric_label_value("Items / destinations", f"{row['items_supplied_count']} / {row['dest_nodes_count']}"),
            metric_label_value("Items principaux", item_labels or "n/a"),
            metric_label_value("Lead prevu moyen", f"{row['avg_procurement_lead_days']:.1f} j"),
        ]
        if supplier_has_explicit_capacity.get(supplier_id, False):
            summary_lines.extend(
                [
                    metric_label_value("Capacite modelisee", "explicite"),
                    metric_label_value("Utilisation cap. moy.", f"{row['avg_capacity_utilization']:.2%}"),
                    metric_label_value("Utilisation cap. max", f"{row['max_capacity_utilization']:.2%}"),
                ]
            )
        else:
            summary_lines.append(metric_label_value("Capacite modelisee", "non explicite"))
        if observed_share_den > 1e-9:
            summary_lines.append(metric_label_value("Part du flux observee", f"{row['observed_sourcing_share']:.1%}"))
            if row["target_sourcing_share"] > 0.0:
                summary_lines.append(metric_label_value("Part cible MRP", f"{row['target_sourcing_share']:.1%}"))
        else:
            summary_lines.append(metric_label_value("Part du flux observee", "n/a"))
        nominal_capacity = supplier_nominal_capacity_by_supplier.get(supplier_id, 0.0)
        if nominal_capacity > 0:
            summary_lines.append(metric_label_value("Capacite nominale", f"{nominal_capacity:,.2f}/j".replace(",", " ")))
        basis_label = supplier_capacity_basis_by_supplier.get(supplier_id, "")
        if basis_label:
            scale = supplier_capacity_scale_by_supplier.get(supplier_id, 0.0)
            suffix = f" x{scale:.0f}" if scale > 0 else ""
            summary_lines.append(metric_label_value("Reference capacite", f"{basis_label}{suffix}"))
        summary_lines.append(metric_label_value("Paires mono-source", str(row["sole_source_pairs"])))
        if row["shortage_supported_qty"] > 0 or row["shortage_supported_events"] > 0:
            summary_lines.append(
                metric_label_value(
                    "Rupture couverte",
                    f"{row['shortage_supported_qty']:.2f} sur {row['shortage_supported_events']} evenements",
                )
            )
        else:
            summary_lines.append(metric_label_value("Rupture couverte", "aucune detectee"))
        summary_lines.append(metric_label_value("Criticite locale", f"{local_score:.3f}"))
        if audit_criticality_score is not None:
            summary_lines.extend(
                [
                    metric_label_value("Criticite structurelle", f"{structural_criticality_score:.3f}"),
                    metric_label_value("Indice audit fournisseur", f"{audit_criticality_score:.1%}"),
                    metric_label_value(
                        "Indice croise indicatif",
                        f"{blend_criticality_with_audit(structural_criticality_score, audit):.3f}",
                    ),
                    metric_label_value("Criteres audit integres", str(audit.get("criterion_count") or 0)),
                ]
            )
        if std_label or struct_label or system_score > 1e-9:
            if std_label:
                summary_lines.append(metric_label_value("Point faible sensibilite", std_label))
            if struct_label:
                summary_lines.append(metric_label_value("Point faible reseau", struct_label))
            summary_lines.append(metric_label_value("Criticite reseau", f"{system_score:.3f}"))
        metrics_by_supplier[supplier_id] = {
            "summary_lines": summary_lines,
            "items": supplied_items,
            "destinations": dest_nodes,
            "scores": {
                "local": round(local_score, 6),
                "system": round(system_score, 6),
                "structural": round(structural_criticality_score, 6),
                "audit": round(audit_criticality_score, 6) if audit_criticality_score is not None else None,
                "overall": round(overall_score, 6),
            },
            "supplier_audit": audit,
        }

    estimate_supplier_audit_profiles(supplier_audits, ranking_rows)
    for row in ranking_rows:
        supplier_id = str(row["supplier_id"])
        audit = supplier_audits.get(supplier_id) or {}
        estimated_score = supplier_estimated_score(audit)
        audited_score = supplier_audit_score(audit)
        row["supplier_name"] = supplier_id
        row["audit_status"] = str(audit.get("audit_status") or "not_available")
        row["audit_criterion_count"] = int(audit.get("criterion_count") or 0)
        row["audit_answered_criterion_count"] = int(audit.get("answered_criterion_count") or 0)
        row["audit_estimated_criterion_count"] = int(audit.get("estimated_criterion_count") or 0)
        row["audit_criticality_score"] = round(audited_score, 6) if audited_score is not None else ""
        row["estimated_audit_risk_index"] = (
            round(estimated_score, 6) if estimated_score is not None else ""
        )
        proxy_score = audited_score if audited_score is not None else estimated_score
        row["indicative_adjusted_score"] = (
            round(0.70 * float(row["structural_criticality_score"]) + 0.30 * proxy_score, 6)
            if proxy_score is not None
            else row["structural_criticality_score"]
        )
        supplier_metrics = metrics_by_supplier.get(supplier_id, {})
        supplier_metrics["supplier_audit"] = audit
        supplier_metrics.setdefault("scores", {})["audit_estimate"] = (
            round(estimated_score, 6) if estimated_score is not None else None
        )
        supplier_metrics["scores"]["indicative_adjusted"] = row["indicative_adjusted_score"]

    ranking_rows.sort(key=lambda row: (-float(row["overall_criticality_score"]), -float(row["total_shipped_qty"]), row["supplier_id"]))
    for rank, row in enumerate(ranking_rows, start=1):
        row["rank"] = rank
        supplier_metrics = metrics_by_supplier.get(str(row["supplier_id"]), {})
        if supplier_metrics:
            supplier_metrics["rank"] = rank
            for entry in supplier_metrics.get("summary_lines", []):
                if entry.get("label") == "Rang local":
                    entry["value"] = f"{rank}"
                    break

    summary = {
        "supplier_count": len(ranking_rows),
        "top_local_criticality": ranking_rows[:10],
        "methodology": {
            "local_score_weights": {
                "volume": 0.35,
                "active_days": 0.20,
                "sole_source_pairs": 0.25,
                "shortage_exposure": 0.20,
            },
            "overall_score_weights": {
                "local": 0.55,
                "system": 0.45,
            },
            "supplier_audit_blend": {
                "structural_score": 0.70,
                "supplier_audit_score": 0.30,
                "ranking_effect": "none",
                "purpose": "indicative_adjusted_score_only",
            },
        },
        "supplier_audit_profile_count": len(supplier_audits),
        "supplier_audit_scored_count": sum(
            1 for audit in supplier_audits.values() if supplier_audit_score(audit) is not None
        ),
        "supplier_audit_estimated_count": sum(
            1 for audit in supplier_audits.values() if supplier_estimated_score(audit) is not None
        ),
    }
    return metrics_by_supplier, ranking_rows, summary




def main() -> None:
    args = parse_args()
    run_inputs = map_inputs_from_run_package(args.run_package) if args.run_package else None
    in_path = Path(args.input)
    out_path = Path(args.output)
    sim_input = Path(args.sim_input_stocks_csv)
    sim_output = Path(args.sim_output_products_csv)
    demand_service_csv = Path(args.demand_service_csv)
    sim_input_png_dir = Path(args.sim_input_stocks_png_dir)
    sim_output_png_dir = Path(args.sim_output_products_png_dir)
    sensitivity_cases_csv = Path(args.sensitivity_cases_csv)
    supplier_shipments_csv = Path(args.supplier_shipments_csv)
    supplier_stocks_csv = Path(args.supplier_stocks_csv)
    supplier_stock_flows_csv = (
        Path(args.supplier_stock_flows_csv)
        if args.supplier_stock_flows_csv
        else supplier_stocks_csv.parent / "production_supplier_stock_flows_daily.csv"
    )
    supplier_capacity_csv = Path(args.supplier_capacity_csv)
    supplier_nominal_parameters_csv = (
        Path(args.supplier_nominal_parameters_csv)
        if args.supplier_nominal_parameters_csv
        else supplier_capacity_csv.parent / "supplier_nominal_parameters.csv"
    )
    factory_nominal_capacities_csv = (
        Path(args.factory_nominal_capacities_csv)
        if args.factory_nominal_capacities_csv
        else supplier_capacity_csv.parent / "production_capacity_nominal_parameters.csv"
    )
    input_arrivals_csv = Path(args.input_arrivals_csv)
    production_constraint_csv = Path(args.production_constraint_csv)
    mrp_trace_csv = production_constraint_csv.parent / "mrp_trace_daily.csv"
    lot_events_csv = (
        Path(args.lot_events_csv)
        if args.lot_events_csv
        else production_constraint_csv.parent / "production_lot_events.csv"
    )
    lot_genealogy_csv = (
        Path(args.lot_genealogy_csv)
        if args.lot_genealogy_csv
        else production_constraint_csv.parent / "production_lot_genealogy.csv"
    )
    production_plan_events_csv = (
        Path(args.production_plan_events_csv)
        if args.production_plan_events_csv
        else production_constraint_csv.parent / "production_plan_events.csv"
    )
    production_campaigns_csv = (
        Path(args.production_campaigns_csv)
        if args.production_campaigns_csv
        else production_constraint_csv.parent / "production_campaigns.csv"
    )
    daily_kpi_csv = Path(args.daily_kpi_csv) if args.daily_kpi_csv else sim_input.parent / "first_simulation_daily.csv"
    structural_sensitivity_cases_csv = Path(args.structural_sensitivity_cases_csv)
    supplier_local_criticality_csv = Path(args.supplier_local_criticality_csv)
    supplier_local_criticality_json = Path(args.supplier_local_criticality_json)
    if run_inputs:
        if run_inputs.input_graph and run_inputs.input_graph.exists():
            in_path = run_inputs.input_graph
        sim_input = run_inputs.sim_input_stocks_csv
        sim_output = run_inputs.sim_output_products_csv
        demand_service_csv = run_inputs.demand_service_csv
        sim_input_png_dir = run_inputs.plots_dir
        sim_output_png_dir = run_inputs.plots_dir
        supplier_shipments_csv = run_inputs.supplier_shipments_csv
        supplier_stocks_csv = run_inputs.supplier_stocks_csv
        supplier_stock_flows_csv = run_inputs.supplier_stock_flows_csv or supplier_stock_flows_csv
        supplier_capacity_csv = run_inputs.supplier_capacity_csv
        supplier_nominal_parameters_csv = run_inputs.supplier_nominal_parameters_csv or supplier_nominal_parameters_csv
        factory_nominal_capacities_csv = run_inputs.factory_nominal_capacities_csv or factory_nominal_capacities_csv
        input_arrivals_csv = run_inputs.input_arrivals_csv
        production_constraint_csv = run_inputs.production_constraint_csv
        mrp_trace_csv = production_constraint_csv.parent / "mrp_trace_daily.csv"
        lot_events_csv = run_inputs.lot_events_csv
        lot_genealogy_csv = run_inputs.lot_genealogy_csv
        production_plan_events_csv = run_inputs.production_plan_events_csv
        production_campaigns_csv = run_inputs.production_campaigns_csv
        daily_kpi_csv = run_inputs.daily_kpi_csv
        supplier_local_criticality_csv = run_inputs.supplier_local_criticality_csv
        supplier_local_criticality_json = run_inputs.supplier_local_criticality_json
        args.dc_stocks_csv = str(run_inputs.dc_stocks_csv)
        if run_inputs.safety_reference_csv:
            args.safety_reference_csv = str(run_inputs.safety_reference_csv)
        if not str(args.simulated_risk_output_dir or "").strip():
            metadata = run_inputs.package.manifest.get("metadata", {})
            if not isinstance(metadata, dict):
                metadata = {}
            configured_risk_dir = metadata.get("simulated_risk_output_dir") or metadata.get("state_dependent_output_dir")
            risk_dir_candidates: list[Path] = []
            if configured_risk_dir:
                configured_path = Path(str(configured_risk_dir))
                risk_dir_candidates.append(configured_path)
                if not configured_path.is_absolute():
                    risk_dir_candidates.append(run_inputs.output_root / configured_path)
            risk_dir_candidates.append(run_inputs.output_root / "scenario_runs" / "state_dependent_full")
            for candidate in risk_dir_candidates:
                if candidate.exists():
                    args.simulated_risk_output_dir = str(candidate)
                    break
    realistic_sensitivity_summary_json = (
        Path(args.realistic_sensitivity_summary_json)
        if args.realistic_sensitivity_summary_json
        else Path("__missing_realistic_sensitivity_summary__.json")
    )
    realistic_local_elasticities_csv = (
        Path(args.realistic_local_elasticities_csv)
        if args.realistic_local_elasticities_csv
        else Path("__missing_realistic_local_elasticities__.csv")
    )
    realistic_stress_impacts_csv = (
        Path(args.realistic_stress_impacts_csv)
        if args.realistic_stress_impacts_csv
        else Path("__missing_realistic_stress_impacts__.csv")
    )
    threshold_sensitivity_summary_json = (
        Path(args.threshold_sensitivity_summary_json)
        if args.threshold_sensitivity_summary_json
        else Path("__missing_threshold_sensitivity_summary__.json")
    )
    threshold_parameter_summary_csv = (
        Path(args.threshold_parameter_summary_csv)
        if args.threshold_parameter_summary_csv
        else Path("__missing_threshold_parameter_summary__.csv")
    )
    threshold_sweep_cases_csv = (
        Path(args.threshold_sweep_cases_csv)
        if args.threshold_sweep_cases_csv
        else Path("__missing_threshold_sweep_cases__.csv")
    )
    supplier_parameter_sensitivity_summary_json = (
        Path(args.supplier_parameter_sensitivity_summary_json)
        if args.supplier_parameter_sensitivity_summary_json
        else Path("__missing_supplier_parameter_sensitivity_summary__.json")
    )
    supplier_parameter_summary_csv = (
        Path(args.supplier_parameter_summary_csv)
        if args.supplier_parameter_summary_csv
        else Path("__missing_supplier_parameter_summary__.csv")
    )
    supplier_parameter_cases_csv = (
        Path(args.supplier_parameter_cases_csv)
        if args.supplier_parameter_cases_csv
        else Path("__missing_supplier_parameter_cases__.csv")
    )
    supplier_risk_summary_json = Path(args.supplier_risk_kpi_summary_json)
    supplier_risk_supplier_csv = Path(args.supplier_risk_kpi_supplier_csv)
    supplier_risk_pair_csv = Path(args.supplier_risk_kpi_pair_csv)
    supplier_risk_panel_csv = Path(args.supplier_risk_kpi_panel_csv)
    supplier_audit_xlsx = Path(args.supplier_audit_xlsx) if str(args.supplier_audit_xlsx or "").strip() else None
    montecarlo_summary_json = (
        Path(args.montecarlo_summary_json)
        if str(args.montecarlo_summary_json or "").strip()
        else Path("__missing_montecarlo_summary__.json")
    )
    supplier_risk_campaign_summary_json = Path(args.supplier_risk_campaign_summary_json)
    supplier_risk_campaign_summary_csv = Path(args.supplier_risk_campaign_summary_csv)
    supplier_risk_campaign_cases_csv = Path(args.supplier_risk_campaign_cases_csv)
    scan_results_dir = (
        Path(args.scan_results_dir)
        if str(args.scan_results_dir or "").strip()
        else Path("__missing_scan_results_package__")
    )
    closed_loop_results_dir = (
        Path(args.closed_loop_results_dir)
        if str(args.closed_loop_results_dir or "").strip()
        else Path("__missing_closed_loop_results_package__")
    )
    closed_loop_v2_results_dir = (
        Path(args.closed_loop_v2_results_dir)
        if str(args.closed_loop_v2_results_dir or "").strip()
        else None
    )
    scan_frequency_results_dir = (
        Path(args.scan_frequency_results_dir)
        if str(args.scan_frequency_results_dir or "").strip()
        else None
    )
    scan_control_system_results_dir = (
        Path(args.scan_control_system_results_dir)
        if str(args.scan_control_system_results_dir or "").strip()
        else None
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    if not args.read_only_source:
        supplier_local_criticality_csv.parent.mkdir(parents=True, exist_ok=True)
        supplier_local_criticality_json.parent.mkdir(parents=True, exist_ok=True)

    try:
        raw = json.loads(in_path.read_text(encoding="utf-8"))
        if not raw.get("nodes") or not raw.get("edges"):
            if raw.get("records") is not None:
                raise ValueError(
                    f"{in_path} is a records/_meta source JSON, not a simulation graph. "
                    "Use etudecas/simulation_prep/result/supply_graph_poc_simulation_ready.json "
                    "or another JSON containing top-level nodes and edges."
                )
            raise ValueError(
                f"{in_path} does not contain top-level nodes/edges required by the map builder."
            )
        payload = compact_graph_payload(raw)
        completed_supplier_audits = load_supplier_audits(supplier_audit_xlsx) if supplier_audit_xlsx else {}
        supplier_audits = expand_supplier_audit_coverage(raw.get("nodes", []) or [], completed_supplier_audits)
        payload["supplier_audits"] = supplier_audits
        payload["supplier_audit_coverage"] = supplier_audit_coverage_summary(supplier_audits)
        payload["data_panel"] = build_data_panel_payload(raw)
        payload["json_panel"] = build_json_panel_payload(raw)
        payload["timeline_horizon_days"] = read_timeline_horizon_days(output_root_from_csv(demand_service_csv))
        payload["factory_like_node_ids"] = sorted(factory_like_node_ids(raw))
        payload["factory_hover_series"] = build_factory_hover_series(raw, sim_input, sim_output)
        payload["factory_hover_images"] = build_factory_hover_images(
            raw,
            sim_input,
            sim_output,
            input_arrivals_csv,
            supplier_shipments_csv,
            supplier_stocks_csv,
            sim_input_png_dir,
            sim_output_png_dir,
            demand_service_csv,
            production_constraint_csv,
            mrp_trace_csv,
        )
        payload["factory_current_metrics"] = build_factory_current_metrics(
            raw,
            production_constraint_csv,
        )
        payload["lot_trace"] = build_lot_trace_payload(
            lot_events_csv,
            lot_genealogy_csv,
            production_plan_events_csv,
            raw,
            sim_input,
            sim_output,
            Path(args.dc_stocks_csv),
            demand_service_csv,
            supplier_stocks_csv,
            production_campaigns_csv=production_campaigns_csv,
            mrp_orders_csv=Path(args.dc_stocks_csv).parent / "mrp_orders_daily.csv",
            include_causal_links=False,
        )
        payload["supplier_hover_images"] = build_supplier_hover_images(
            raw,
            sim_input_png_dir,
            supplier_shipments_csv,
            supplier_stocks_csv,
            supplier_stock_flows_csv,
            supplier_capacity_csv,
            mrp_trace_csv,
        )
        payload["distribution_center_hover_images"] = build_distribution_center_hover_images(
            raw,
            sim_input_png_dir,
            Path(args.dc_stocks_csv),
            supplier_shipments_csv,
            mrp_trace_csv,
        )
        edge_metrics = build_edge_metrics(
            raw,
            supplier_shipments_csv,
            horizon_days=read_timeline_horizon_days(output_root_from_csv(demand_service_csv)),
        )
        for edge_payload in payload.get("edges", []) or []:
            edge_id = str(edge_payload.get("id") or "")
            if edge_id in edge_metrics:
                edge_payload["edge_metrics"] = edge_metrics[edge_id]
        payload["simulation_diagnostics"] = build_simulation_diagnostics_payload(
            raw,
            demand_service_csv=demand_service_csv,
            dc_stocks_csv=Path(args.dc_stocks_csv),
            sim_input_stocks_csv=sim_input,
            sim_output_products_csv=sim_output,
            production_constraint_csv=production_constraint_csv,
            production_plan_events_csv=production_plan_events_csv,
            supplier_shipments_csv=supplier_shipments_csv,
            supplier_stocks_csv=supplier_stocks_csv,
            supplier_stock_flows_csv=supplier_stock_flows_csv,
            supplier_local_criticality_csv=supplier_local_criticality_csv,
            mrp_trace_csv=mrp_trace_csv,
            edge_metrics=edge_metrics,
        )
        payload["model_panel"] = build_model_panel_metrics(
            raw,
            sim_input_stocks_csv=sim_input,
            sim_output_products_csv=sim_output,
            input_arrivals_csv=input_arrivals_csv,
            demand_service_csv=demand_service_csv,
            supplier_shipments_csv=supplier_shipments_csv,
            supplier_stocks_csv=supplier_stocks_csv,
            supplier_stock_flows_csv=supplier_stock_flows_csv,
            supplier_capacity_csv=supplier_capacity_csv,
            supplier_nominal_parameters_csv=supplier_nominal_parameters_csv,
            factory_nominal_capacities_csv=factory_nominal_capacities_csv,
            dc_stocks_csv=Path(args.dc_stocks_csv),
            production_constraint_csv=production_constraint_csv,
            write_derived_artifacts=not args.read_only_source,
        )
        simulated_risk_output_root = (
            Path(args.simulated_risk_output_dir)
            if str(args.simulated_risk_output_dir or "").strip()
            else output_root_from_csv(demand_service_csv)
        )
        if simulated_risk_output_root.exists():
            payload["simulated_risk_metrics"] = build_simulated_risk_metrics_from_output(
                raw,
                simulated_risk_output_root,
            )
        else:
            payload["simulated_risk_metrics"] = payload["model_panel"].get("simulated_risk_metrics", {})
        payload["simulated_risk_global_diagnostic"] = build_simulated_risk_global_diagnostic_payload(
            raw=raw,
            output_root=simulated_risk_output_root if simulated_risk_output_root.exists() else output_root_from_csv(demand_service_csv),
            simulated_risk_metrics=payload.get("simulated_risk_metrics", {}),
        )
        payload["scenario_comparison"] = build_scenario_comparison_payload(output_root_from_csv(demand_service_csv))
        payload["scan_dashboard"] = build_scan_dashboard_payload(
            scan_results_dir,
            closed_loop_results_dir,
            closed_loop_v2_results_dir,
            scan_frequency_results_dir,
            scan_control_system_results_dir,
        )
        payload["supplier_risk_campaign"] = build_supplier_risk_campaign_payload(
            supplier_risk_campaign_summary_json,
            supplier_risk_campaign_summary_csv,
            supplier_risk_campaign_cases_csv,
        )
        payload["customer_hover_images"], payload["customer_current_metrics"] = build_customer_hover_images(
            raw,
            demand_service_csv,
            supplier_shipments_csv,
        )
        payload["global_kpi_tree"] = build_global_kpi_tree_payload(
            daily_kpi_csv,
            demand_service_csv,
            production_constraint_csv,
            Path(args.dc_stocks_csv).parent / "mrp_orders_daily.csv",
            raw,
            write_derived_artifacts=not args.read_only_source,
        )
        payload["global_kpi_tree"] = extend_global_kpi_tree_with_supplier_risk(
            payload.get("global_kpi_tree"),
            supplier_risk_panel_csv=supplier_risk_panel_csv,
            supplier_risk_supplier_csv=supplier_risk_supplier_csv,
            supplier_risk_pair_csv=supplier_risk_pair_csv,
            supplier_risk_summary_json=supplier_risk_summary_json,
        )
        baseline_production_planning_line_count = production_replanning_rate_denominator(
            raw,
            horizon_days=read_timeline_horizon_days(output_root_from_csv(demand_service_csv)),
            production_constraint_csv=production_constraint_csv,
        )
        (
            payload["factory_supplier_risk_hover_images"],
            payload["supplier_risk_hover_images"],
            payload["distribution_center_supplier_risk_hover_images"],
            payload["supplier_risk_metrics"],
        ) = build_supplier_risk_hover_payloads(
            raw,
            supplier_risk_panel_csv=supplier_risk_panel_csv,
            supplier_risk_supplier_csv=supplier_risk_supplier_csv,
            supplier_risk_pair_csv=supplier_risk_pair_csv,
            supplier_risk_summary_json=supplier_risk_summary_json,
        )
        (
            payload["factory_sensitivity_hover_images"],
            payload["supplier_sensitivity_hover_images"],
            payload["distribution_center_sensitivity_hover_images"],
        ) = build_sensitivity_hover_payloads(raw, sensitivity_cases_csv)
        (
            factory_threshold_hover_images,
            supplier_threshold_hover_images,
            dc_threshold_hover_images,
        ) = build_threshold_hover_payloads(
            raw,
            threshold_parameter_summary_csv,
            threshold_sweep_cases_csv,
            threshold_sensitivity_summary_json,
            baseline_production_planning_line_count=baseline_production_planning_line_count,
        )
        payload["factory_sensitivity_hover_images"] = merge_hover_payload_maps(
            factory_threshold_hover_images,
            payload["factory_sensitivity_hover_images"],
        )
        payload["supplier_sensitivity_hover_images"] = merge_hover_payload_maps(
            supplier_threshold_hover_images,
            payload["supplier_sensitivity_hover_images"],
        )
        payload["distribution_center_sensitivity_hover_images"] = merge_hover_payload_maps(
            dc_threshold_hover_images,
            payload["distribution_center_sensitivity_hover_images"],
        )
        (
            factory_supplier_parameter_hover_images,
            supplier_parameter_hover_images,
            dc_supplier_parameter_hover_images,
            supplier_parameter_sensitivity_nodes,
        ) = build_supplier_parameter_sensitivity_hover_payloads(
            raw,
            supplier_parameter_sensitivity_summary_json,
            supplier_parameter_summary_csv,
            supplier_parameter_cases_csv,
            supplier_nominal_parameters_csv,
            baseline_production_planning_line_count=baseline_production_planning_line_count,
        )
        payload["supplier_parameter_sensitivity_nodes"] = supplier_parameter_sensitivity_nodes
        payload["factory_sensitivity_hover_images"] = merge_hover_payload_maps(
            factory_supplier_parameter_hover_images,
            payload["factory_sensitivity_hover_images"],
        )
        payload["supplier_sensitivity_hover_images"] = merge_hover_payload_maps(
            supplier_parameter_hover_images,
            payload["supplier_sensitivity_hover_images"],
        )
        payload["distribution_center_sensitivity_hover_images"] = merge_hover_payload_maps(
            dc_supplier_parameter_hover_images,
            payload["distribution_center_sensitivity_hover_images"],
        )
        (
            payload["factory_structural_hover_images"],
            payload["supplier_structural_hover_images"],
            payload["distribution_center_structural_hover_images"],
        ) = build_structural_sensitivity_hover_payloads(raw, structural_sensitivity_cases_csv)
        (
            payload["supplier_local_metrics"],
            supplier_local_ranking_rows,
            supplier_local_summary,
        ) = build_supplier_local_criticality(
            raw,
            supplier_shipments_csv,
            supplier_stocks_csv,
            supplier_capacity_csv,
            production_constraint_csv,
            sensitivity_cases_csv,
            structural_sensitivity_cases_csv,
            supplier_audits=supplier_audits,
        )
        payload["supplier_audits"] = supplier_audits
        payload["supplier_audit_coverage"] = supplier_audit_coverage_summary(supplier_audits)
        payload["supplier_risk_hover_images"] = attach_supplier_audit_panels(
            payload["supplier_risk_hover_images"],
            supplier_audits,
        )
        payload["realistic_sensitivity"] = build_realistic_sensitivity_panel_metrics(
            raw,
            realistic_sensitivity_summary_json,
            realistic_local_elasticities_csv,
            realistic_stress_impacts_csv,
        )
        payload["threshold_sensitivity"] = build_threshold_sensitivity_panel_metrics(
            raw,
            threshold_sensitivity_summary_json,
            threshold_parameter_summary_csv,
        )
        payload["montecarlo_uncertainty"] = build_montecarlo_uncertainty_payload(montecarlo_summary_json)
        material_table_rows = build_material_balance_table_rows(
            raw,
            demand_service_csv=demand_service_csv,
            sim_input_stocks_csv=sim_input,
            sim_output_products_csv=sim_output,
            sim_dc_stocks_csv=Path(args.dc_stocks_csv),
            supplier_shipments_csv=supplier_shipments_csv,
            safety_reference_csv=Path(args.safety_reference_csv) if args.safety_reference_csv else None,
        )
        payload["material_balance_rows"] = material_table_rows
        payload["payload_layers"] = build_payload_layers_manifest(
            [
                build_simulation_payload_manifest(payload),
                build_risk_payload_manifest(payload),
                build_sensitivity_payload_manifest(payload),
            ]
        )
        if run_inputs:
            payload["run_contract"] = run_contract_payload(run_inputs)
        payload = attach_generic_payload_contract(payload)
    except Exception as exc:
        print(f"[ERROR] Unable to read/parse input JSON: {exc}", file=sys.stderr)
        sys.exit(1)

    if not args.read_only_source:
        csv_columns = sorted({key for row in supplier_local_ranking_rows for key in row.keys()})
        with supplier_local_criticality_csv.open("w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=csv_columns)
            writer.writeheader()
            writer.writerows(supplier_local_ranking_rows)
        supplier_local_criticality_json.write_text(
            json.dumps(
                {
                    "summary": supplier_local_summary,
                    "ranking": supplier_local_ranking_rows,
                },
                indent=2,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

    if not ensure_plotly_offline_assets(allow_download=True):
        print(
            "[WARN] Plotly offline assets unavailable; generated HTML may depend on the Plotly CDN.",
            file=sys.stderr,
        )
    html_str = html_template(
        args.title,
        json.dumps(payload, ensure_ascii=False),
        render_material_balance_table_html(material_table_rows),
        len(material_table_rows),
        render_global_model_equations_html(),
    )
    try:
        html_str = apply_html_payload_mode(
            html_str,
            out_path,
            externalize_payload=bool(args.externalize_payload),
            compress_embedded_payload=bool(args.compress_embedded_payload),
            chunked_embedded_payload=bool(args.chunked_embedded_payload),
            payload_json=args.payload_json,
        )
    except ValueError as exc:
        print(
            f"[ERROR] {exc}",
            file=sys.stderr,
        )
        sys.exit(2)
    out_path.write_text(html_str, encoding="utf-8")
    print(f"[OK] HTML generated: {out_path.resolve()}")


if __name__ == "__main__":
    main()
