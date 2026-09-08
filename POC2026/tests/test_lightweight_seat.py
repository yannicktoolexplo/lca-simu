from __future__ import annotations

from pathlib import Path

import pytest

from POC2026.supply_geo_case.lightweight_seat import (
    INDICATOR_METHODS,
    LOCALIZATION_SCENARIO_IDS,
    build_mass_budget_rows,
    classify_family,
    extract_reconciled_mass_budget,
    is_exact_brightway_rows,
    is_exact_localization_rows,
    load_scenario_config,
)


REPO_ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = REPO_ROOT / "POC2026" / "supply_geo_case" / "config" / "lightweight_seat_50.yml"
MASTERBOARD_PATH = REPO_ROOT / "bw_tristan" / "STELIA Masterboard LCA SEATS 6.0.xlsx"


def test_lightweight_mass_budget_closes_at_half_opera_mass() -> None:
    config = load_scenario_config(CONFIG_PATH)
    masses, reconciliation = extract_reconciled_mass_budget(MASTERBOARD_PATH, config)
    rows = build_mass_budget_rows(masses, config)

    assert reconciliation["status"] == "masterboard_reconciled_to_opera_mass"
    assert reconciliation["raw_bom_mass_kg"] == pytest.approx(123.30871422)
    assert len(rows) == 5
    assert sum(row["baseline_mass_kg"] for row in rows) == pytest.approx(109.967, abs=1e-5)
    assert sum(row["target_mass_kg"] for row in rows) == pytest.approx(54.9835, abs=2e-5)
    assert sum(row["mass_saved_kg"] for row in rows) == pytest.approx(54.9835, abs=2e-5)
    assert all(0.0 < row["lca_exchange_scale_factor"] < 1.0 for row in rows)


def test_lightweight_component_classification_covers_key_seat_functions() -> None:
    config = load_scenario_config(CONFIG_PATH)

    assert classify_family("ENS STRUCTURE FAUTEUIL", config) == "primary_structure"
    assert classify_family("ENSEMBLE COQUE", config) == "shell_stowage"
    assert classify_family("ENS COUSSIN ASSISE", config) == "comfort"
    assert classify_family("ENS TABLETTE REPAS", config) == "passenger_interfaces"
    assert classify_family("ECRAN 17,3 INCH", config) == "ife_electrical"


def test_only_complete_brightway_results_can_feed_the_exact_cache() -> None:
    rows = [
        {
            "indicator_id": indicator_id,
            "calculation_status": "brightway_exact_foreground_scaled_screening",
            "fuel_factor_raw_per_kg": 4.1 if indicator_id == "Climate Change - total" else 0.1,
        }
        for indicator_id in INDICATOR_METHODS
    ]

    assert is_exact_brightway_rows(rows) is True

    rows[0]["calculation_status"] = "screening_detailed_workbook_scaled"
    assert is_exact_brightway_rows(rows) is False

    rows[0]["calculation_status"] = "brightway_exact_foreground_scaled_screening"
    rows.pop()
    assert is_exact_brightway_rows(rows) is False


def test_localization_cache_requires_four_complete_scenarios() -> None:
    rows = [
        {
            "sourcing_scenario_id": sourcing_id,
            "indicator_id": indicator_id,
            "calculation_status": "brightway_exact_lightweight_and_localized_screening",
            "fuel_factor_raw_per_kg": 4.1 if indicator_id == "Climate Change - total" else 0.1,
        }
        for sourcing_id in LOCALIZATION_SCENARIO_IDS
        for indicator_id in INDICATOR_METHODS
    ]

    assert is_exact_localization_rows(rows) is True

    rows = [row for row in rows if row["sourcing_scenario_id"] != "france_first"]
    assert is_exact_localization_rows(rows) is False
