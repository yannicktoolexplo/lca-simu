from __future__ import annotations

import csv
import json
import math
from pathlib import Path

from etudecas.analysis.from_simulation.build_observed_2025_supply_bilan import (
    ANALYSIS_RESULT_DIR,
    DEFAULT_021_REFERENCE_RUN,
    DEFAULT_REFERENCE_RUN,
    SOURCE_DIR,
    build_bilan,
)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def test_build_bilan_preserves_value_vs_quantity_semantics(tmp_path: Path) -> None:
    payload = build_bilan(
        source_dir=SOURCE_DIR,
        analysis_result_dir=ANALYSIS_RESULT_DIR,
        reference_run=DEFAULT_REFERENCE_RUN,
        reference_021_run=DEFAULT_021_REFERENCE_RUN,
        output_dir=tmp_path,
    )

    assert len(payload["ca_summary"]) == 2
    assert len(payload["stock_summary"]) == 4
    assert all(row["physical_quantity_available"] is False for row in payload["stock_summary"])
    component_rows = [
        row for row in payload["stock_summary"] if row["stock_scope"] == "component_immobilized_accounting_value"
    ]
    assert {row["product_code"] for row in component_rows} == {""}
    assert payload["component_stock_product_mapping_status"] == "unresolved_conflicting_hypotheses"
    assert payload["supplier_risk_prediction_readiness"]["industrial_probability_status"] == "NOT_READY"
    assert all(row["status"] == "PASS" for row in payload["validation_checks"])

    stock_rows = read_csv(tmp_path / "observed_stock_value_snapshots_2025.csv")
    assert len(stock_rows) == 208
    assert {row["physical_quantity_available"] for row in stock_rows} == {"False"}
    assert {row["physical_uom"] for row in stock_rows} == {""}


def test_ca_totals_and_signal_mismatches_are_kept_separate(tmp_path: Path) -> None:
    payload = build_bilan(
        source_dir=SOURCE_DIR,
        analysis_result_dir=ANALYSIS_RESULT_DIR,
        reference_run=DEFAULT_REFERENCE_RUN,
        reference_021_run=DEFAULT_021_REFERENCE_RUN,
        output_dir=tmp_path,
    )
    ca = {row["product_code"]: row for row in payload["ca_summary"]}

    assert math.isclose(ca["268091"]["ca_lost_raw_source_value"], 1_611_174.49302, abs_tol=1e-6)
    assert ca["268091"]["lost_signal_count"] == 179
    assert ca["268091"]["days_with_positive_lost_value"] == 186
    assert ca["268091"]["days_positive_lost_without_signal"] == 7
    assert ca["268091"]["negative_lost_value_row_count"] == 1

    assert math.isclose(ca["268967"]["ca_lost_raw_source_value"], 1_082_210.32, abs_tol=1e-6)
    assert ca["268967"]["lost_signal_count"] == 76
    assert ca["268967"]["days_with_positive_lost_value"] == 98
    assert ca["268967"]["days_positive_lost_without_signal"] == 22


def test_projected_shortages_are_summarized_without_summing_snapshots(tmp_path: Path) -> None:
    payload = build_bilan(
        source_dir=SOURCE_DIR,
        analysis_result_dir=ANALYSIS_RESULT_DIR,
        reference_run=DEFAULT_REFERENCE_RUN,
        reference_021_run=DEFAULT_021_REFERENCE_RUN,
        output_dir=tmp_path,
    )
    rows = {
        (row["product_code"], row["snapshot_year"]): row
        for row in payload["projected_shortage_summary"]
    }
    assert rows[("268091", 2025)]["nonzero_snapshot_count"] == 4
    assert rows[("268091", 2025)]["maximum_projected_shortage_weeks"] == 3
    assert rows[("268967", 2025)]["nonzero_snapshot_count"] == 0
    assert rows[("268967", 2026)]["nonzero_snapshot_count"] == 18
    assert rows[("268967", 2026)]["maximum_projected_shortage_weeks"] == 11
    assert all(row["sum_deliberately_not_computed"] for row in rows.values())


def test_021081_context_keeps_observed_and_simulated_evidence_distinct(tmp_path: Path) -> None:
    payload = build_bilan(
        source_dir=SOURCE_DIR,
        analysis_result_dir=ANALYSIS_RESULT_DIR,
        reference_run=DEFAULT_REFERENCE_RUN,
        reference_021_run=DEFAULT_021_REFERENCE_RUN,
        output_dir=tmp_path,
    )
    context = payload["component_021081_context"]
    assert context["opening_stock_source_kg"] == 1_142_100
    assert context["opening_order_book_kg"] == 1_320_000
    assert context["opening_order_line_count"] == 23
    assert context["simulated_horizon_days"] == 720
    assert context["simulated_consumption_kg"] == 257_472

    rows = read_csv(tmp_path / "component_021081_physical_context.csv")
    assert {row["evidence"] for row in rows} == {
        "OBSERVED_SNAPSHOT",
        "OBSERVED_PLANNED_ORDER_BOOK",
        "SIMULATED_REFERENCE",
    }


def test_artifact_bundle_is_self_consistent(tmp_path: Path) -> None:
    build_bilan(
        source_dir=SOURCE_DIR,
        analysis_result_dir=ANALYSIS_RESULT_DIR,
        reference_run=DEFAULT_REFERENCE_RUN,
        reference_021_run=DEFAULT_021_REFERENCE_RUN,
        output_dir=tmp_path,
    )
    manifest = json.loads((tmp_path / "manifest.json").read_text(encoding="utf-8"))
    payload = json.loads((tmp_path / "bilan_observed_2025.json").read_text(encoding="utf-8"))
    assert manifest["all_validation_checks_pass"] is True
    assert payload["currency_status"] == "not_declared_in_source; EUR_is_working_convention"
    assert payload["supplier_attribution_status"] == "not_supported_by_available_observed_files"
    assert (tmp_path / "REPORT.md").stat().st_size > 5_000
