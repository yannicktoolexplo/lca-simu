#!/usr/bin/env python3
"""Refresh reporting-only 021081 outputs from a completed campaign.

This never runs the engine or changes row-level simulation metrics.  It exists
so a completed simulation artifact can receive corrected vocabulary, explicit
limitations and source-backed masking audits without pretending that the
report builder was the orchestrator used at simulation time.
"""

from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from etudecas.prototypes.scan_2027_risk_control import (  # noqa: E402
    supplier_021081_active_flow_campaign as campaign,
)


def _baseline(rows: Sequence[Mapping[str, Any]]) -> Mapping[str, Any]:
    return next(
        row
        for row in rows
        if str(row.get("state_regime") or "") == "observed_2025"
        and str(row.get("scenario_id") or "")
        == "baseline_observed_order_book"
    )


def finalize(root: Path) -> dict[str, Any]:
    root = root.resolve()
    manifest_path = root / "campaign_manifest.json"
    manifest = campaign.read_json(manifest_path)
    if str(manifest.get("status") or "") not in {"complete", "smoke_complete"}:
        raise RuntimeError("Reporting refresh requires a completed campaign")

    source_graph_path = Path(str(manifest["source_graph"])).resolve()
    source_graph = campaign.read_json(source_graph_path)
    active_regimes = campaign.build_state_regimes(source_graph)
    summaries = campaign.read_csv_rows(root / "scenario_summary.csv")
    confirmation_summaries = [
        row
        for row in summaries
        if campaign.to_int(row.get("n_simulations")) >= 10
    ]
    criticality = campaign.read_csv_rows(
        root / "supplier_criticality_ranking_021081.csv"
    )
    legacy_mechanism_path = root / "mechanism_recurrence_summary_021081.csv"
    sensitivity_path = root / "mechanism_sensitivity_summary_021081.csv"
    mechanisms = campaign.read_csv_rows(
        sensitivity_path if sensitivity_path.exists() else legacy_mechanism_path
    )
    campaign.write_csv(sensitivity_path, mechanisms)
    flow_gates = campaign.read_json(root / "reference_flow_gate.json")
    source_audit = campaign.read_json(root / "observed_order_book_audit.json")
    screening_rows = campaign.read_csv_rows(root / "screening_metrics.csv")
    baseline = _baseline(screening_rows)
    observed_stock = campaign.to_float(
        baseline.get("measurement_start_stock_after_qty_kg"), math.nan
    )
    horizon_consumption = campaign.to_float(
        baseline.get("component_consumed_qty_kg"), math.nan
    )
    daily_consumption = campaign.to_float(
        baseline.get("component_consumed_avg_qty_per_day"), math.nan
    )
    masking_audit = {
        "observed_opening_stock_qty_kg": observed_stock,
        "simulated_horizon_days": campaign.to_int(baseline.get("days")),
        "simulated_horizon_consumption_qty_kg": horizon_consumption,
        "observed_stock_multiple_of_horizon_consumption": (
            observed_stock / horizon_consumption
            if horizon_consumption > 1e-9
            else math.inf
        ),
        "simulated_average_consumption_qty_per_day": daily_consumption,
        "physical_cover_days_at_simulated_average_consumption": (
            observed_stock / daily_consumption
            if daily_consumption > 1e-9
            else math.inf
        ),
        "interpretation": (
            "Masking by opening stock, intermediate stock/production and the "
            "planned open order book; not acquired resilience."
        ),
    }
    confirmation_regime_id = str(
        manifest.get("confirmation_state_regime") or ""
    )
    confirmation_regime = next(
        (
            regime
            for regime in active_regimes
            if regime.regime_id == confirmation_regime_id
        ),
        None,
    )
    intermediate_provenance = campaign.intermediate_masking_evidence(
        source_graph_path
    )
    campaign.write_business_outputs(
        output_root=root,
        source_audit=source_audit,
        active_regimes=active_regimes,
        summaries=summaries,
        confirmation_summaries=confirmation_summaries,
        criticality=criticality,
        mechanisms=mechanisms,
        flow_gates=flow_gates,
        masking_audit=masking_audit,
        confirmation_regime=confirmation_regime,
        days=campaign.to_int(manifest.get("days"), 720),
        intermediate_masking_provenance=intermediate_provenance,
    )

    manifest.setdefault("scientific_scope", {}).update(
        {
            "coherence_with_clean_dynamic_reference": (
                "The clean dynamic reference has zero 021081 arrival without an "
                "opening order book. This campaign deliberately replays 23 planned "
                "orders; replayed and new MRP flows remain separate."
            ),
            "quantity_unit_provenance": (
                "The graph's already-standardized quantity field is used; every "
                "target row declares KG and no new conversion is applied."
            ),
            "mechanism_sensitivity_interpretation": (
                "Counts describe sensitivity to tested scenarios, not historical "
                "recurrence or supplier incident probabilities."
            ),
            "critical_bom_unit_validation": {
                "status": "unit_to_validate_with_industrial_owner",
                "source": "773474.xlsx BOM",
                "output_declared": "1000 G; ELSSR CONT. 1000 L",
                "input_021081_declared": "8.94 KG",
                "literal_graph_ratio_kg_per_kg": 8.94,
                "alternative_ratio_divided_by_1000_is_hypothesis_only": True,
                "source_graph_unchanged": True,
            },
            "intermediate_773474_masking_audit": {
                "released_268967_lot_count": 29,
                "approx_horizon_need_g": 30_182_579.4116,
                "opening_stock_total_g": 24_193_000.0,
                "horizon_773474_production_g": 28_800_000.0,
                "stock_multiple_of_horizon_need": 0.8015550848,
                "stock_plus_production_multiple_of_horizon_need": 1.7557478861,
                "021081_stock_multiple_of_horizon_intermediate_consumption": 4.4358221477,
                "021081_order_book_multiple_of_horizon_intermediate_consumption": 5.1267710664,
                **intermediate_provenance,
            },
        }
    )
    manifest["business_outputs"] = {
        "summary_markdown": "RESUME_METIER_021081.md",
        "future_page_payload": "future_autonomous_page_payload.json",
        "top_observed_state_cases": "top_3_cases_observed_state_021081.csv",
        "top_decision_cases": "top_3_cases_decision_021081.csv",
        "mechanism_sensitivity": "mechanism_sensitivity_summary_021081.csv",
        "quality_cover_sensitivity": "quality_hold_cover_sensitivity_021081.csv",
    }
    manifest["reporting_refresh"] = {
        "report_builder": str(Path(__file__).resolve()),
        "report_builder_sha256": campaign.sha256_file(Path(__file__).resolve()),
        "campaign_library_sha256": campaign.PROCESS_ORCHESTRATOR_SHA256,
        "simulation_metrics_changed": False,
        "simulation_orchestrator_provenance_inherited": False,
        "interpretation": (
            "Reporting-only refresh after simulation completion; it does not "
            "retroactively establish the launch orchestrator hash."
        ),
    }
    campaign.write_json(manifest_path, manifest)
    return {
        "campaign_root": str(root),
        "summary_rows": len(summaries),
        "confirmation_summary_rows": len(confirmation_summaries),
        "reporting_refresh": manifest["reporting_refresh"],
    }


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("campaign_root")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    result = finalize(Path(args.campaign_root))
    print(f"[OK] reporting refresh: {result}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
