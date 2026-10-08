from __future__ import annotations

from pathlib import Path

import pytest
from POC2026.supply_geo_case import lightweight_seat as seat

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


def test_missing_fuel_factor_is_not_zero_in_memory() -> None:
    from POC2026.supply_geo_case.lightweight_seat import _fallback_exact_rows

    rows = _fallback_exact_rows(
        [{"family": "Livraison", "indicator": "Climate Change - total", "value": 100}],
        [], {},
    )
    assert rows[0]["lightweight_production_raw"] == 50
    assert rows[0]["fuel_factor_raw_per_kg"] is None


def _memory_exact_rows(scenario_ids=("current_export",)):
    return [
        {"indicator_id": indicator, "sourcing_scenario_id": scenario,
         "calculation_status": "brightway_exact_foreground_scaled_screening",
         "baseline_production_raw": 100, "lightweight_production_raw": 50,
         "fuel_factor_raw_per_kg": 4.148118595,
         "transport_amount_factor": "0.123457",
         "cached_result_status": "historical_unvalidated",
         "cache_source_path": "memory.csv", "cache_content_sha256": "memory-digest",
         "runtime_warning": "Historical cache; not revalidated."}
        for scenario in scenario_ids for indicator in INDICATOR_METHODS
    ]


@pytest.mark.parametrize("kind", ["exact", "localization", "named"])
def test_three_caches_reused_without_runtime_in_memory(monkeypatch, kind):
    ids = LOCALIZATION_SCENARIO_IDS if kind == "localization" else ("current_export",)
    rows = _memory_exact_rows(ids)
    monkeypatch.setattr(seat, "_read_cached_rows", lambda path: rows)
    monkeypatch.setattr(seat.subprocess, "run", lambda *a, **k: pytest.fail("runner forbidden"))
    kwargs = dict(runtime={"can_execute_brightway": True, "cached_only": True},
                  config_path=Path("memory/config.yml"), runner_path=Path("memory/tools/runner.py"))
    if kind == "named":
        result = seat.run_exact_named_supplier_scenarios(**kwargs, supplier_scenarios=[
            {"scenario_id": "current_export", "transport_amount_factor": 0.123456789}])
    elif kind == "localization":
        result = seat.run_exact_localization_scenarios(**kwargs)
    else:
        result = seat.run_exact_brightway(**kwargs)
    assert result == rows
    assert result[0]["cached_result_status"] == "historical_unvalidated"


def test_cache_provenance_hashes_content_in_memory():
    import hashlib

    content = b"indicator_id,fuel_factor_raw_per_kg\nClimate Change - total,4.148118595\n"

    class MemoryCSV:
        def exists(self):
            return True

        def read_bytes(self):
            return content

        def __str__(self):
            return "historical-memory.csv"

    rows = seat._read_cached_rows(MemoryCSV())
    assert rows[0]["cache_content_sha256"] == hashlib.sha256(content).hexdigest()
    assert rows[0]["cache_source_path"] == "historical-memory.csv"
    assert rows[0]["cached_result_status"] == "historical_unvalidated"


@pytest.mark.parametrize("kind", ["exact", "localization", "named"])
def test_cached_only_never_launches_runner_without_usable_cache(monkeypatch, kind):
    monkeypatch.setattr(seat, "_read_cached_rows", lambda path: [])
    monkeypatch.setattr(seat.subprocess, "run", lambda *a, **k: pytest.fail("runner forbidden"))
    kwargs = dict(runtime={"can_execute_brightway": True, "cached_only": True},
                  config_path=Path("memory/config.yml"), runner_path=Path("memory/tools/runner.py"))
    if kind == "named":
        result = seat.run_exact_named_supplier_scenarios(**kwargs, supplier_scenarios=[
            {"scenario_id": "current_export", "transport_amount_factor": 1}])
    elif kind == "localization":
        result = seat.run_exact_localization_scenarios(**kwargs)
    else:
        result = seat.run_exact_brightway(**kwargs)
    assert result == []


def test_localization_missing_results_do_not_become_full_weighted_gain():
    _, summaries = seat.build_localization_results(
        exact_rows=_memory_exact_rows(),
        metadata={"Climate Change - total": {"normalization_factor": 10,
                  "weight_fraction": .5, "use_phase_person_equivalent": 20}},
        avoided_fuel={"central": 2}, regional_scenarios=[],
    )
    assert summaries[0]["weighted_point"] == pytest.approx(12.0851881405)
    assert summaries[0]["cached_result_status"] == "historical_unvalidated"
    for summary in summaries[1:]:
        assert summary["weighted_point"] is None
        assert summary["cycle_climate_central_kgco2e"] is None
        assert summary["weighted_delta_vs_lightweight_current_pct"] is None
        assert summary["fuel_factor_status"] == "unavailable"


@pytest.mark.parametrize("bad", [None, "", "nan", "inf", "invalid"])
def test_invalid_factors_rejected_in_memory(bad):
    rows = _memory_exact_rows()
    rows[0]["fuel_factor_raw_per_kg"] = bad
    assert not seat.is_exact_brightway_rows(rows)
    assert not seat.is_exact_named_supplier_rows(rows, ["current_export"])


def test_named_transport_checks_every_row_and_csv_precision_in_memory():
    rows = _memory_exact_rows()
    scenarios = [{"scenario_id": "current_export", "transport_amount_factor": 0.123456789}]
    assert seat._transport_factors_match(rows, scenarios)
    rows[0]["transport_amount_factor"] = 0.123458
    assert not seat._transport_factors_match(rows, scenarios)
    rows[0]["transport_amount_factor"] = None
    assert not seat._transport_factors_match(rows, scenarios)
    for row in rows:
        row["transport_amount_factor"] = 0
    scenarios[0]["transport_amount_factor"] = 0
    assert seat._transport_factors_match(rows, scenarios)


@pytest.mark.parametrize("cached", [False, True])
@pytest.mark.parametrize("article", [False, True])
def test_summary_use_and_weighted_memory_oracle(monkeypatch, cached, article):
    config = {"baseline_mass_kg": 10, "target_mass_kg": 5,
              "flight_use": {"average_flight_distance_km": 1000, "annual_flight_cycles": 2,
                             "lifetime_years": 1, "marginal_fuel_kg_per_kg_1000km":
                             {"low": 0.1, "central": 0.2, "high": 0.3}}}
    if article:
        config.update(baseline_mass_kg=109.967, target_mass_kg=54.9835)
        config["flight_use"].update(calculation_method="steinegger_a322_2017",
            average_flight_distance_km=5556, annual_flight_cycles=700,
            lifetime_years=7, allow_extrapolation=True)
    monkeypatch.setattr(seat, "load_scenario_config", lambda path: config)
    monkeypatch.setattr(seat, "extract_reconciled_mass_budget", lambda *a: ({}, {}))
    monkeypatch.setattr(seat, "build_mass_budget_rows", lambda *a: [
        {"family_id": "test", "baseline_mass_kg": 10, "target_mass_kg": 5,
         "lca_exchange_scale_factor": 0.5}])
    monkeypatch.setattr(seat, "run_exact_brightway", lambda **k: _memory_exact_rows() if cached else [])
    monkeypatch.setattr(seat, "run_exact_localization_scenarios", lambda **k:
                        _memory_exact_rows(LOCALIZATION_SCENARIO_IDS) if article and cached else [])
    monkeypatch.setattr(seat, "run_exact_named_supplier_scenarios", lambda **k:
                        _memory_exact_rows(("named_supplier",)) if article and cached else [])
    label = "Climate Change - total"
    result = seat.build_lightweight_scenario(
        config_path=Path("memory"), masterboard_path=Path("memory"), runtime={}, runner_path=Path("memory"),
        impact_rows=[{"family": "Livraison", "indicator": label, "value": 100}],
        indicator_unit_views=[{"short_label": label, "include_in_person_equivalent": True,
                               "normalization_factor_per_person_year": 10}],
        reference_person_equivalent_results=[{"short_label": label, "use_phase_person_equivalent": 20}],
        reference_weighting_factors=[{"category": "Climate change", "ef30_weight_pct": 50}],
        supplier_alternative_payload={"scenario_summaries": [{"scenario_id": "named_supplier"}]},
    )
    summary = result["summary"]
    if article:
        from decimal import Decimal

        # Independent decimal oracle, without calling the mission implementation.
        baseline_fuel = Decimal("109.967") * 4900 * Decimal(".18224")
        assert result["mission"]["baseline_fuel_kg"] == pytest.approx(float(baseline_fuel))
        assert summary["use_method"] == "steinegger_a322_2017"
        assert summary["avoided_fuel_central_kg"] == pytest.approx(float(baseline_fuel / 2))
        assert summary["avoided_fuel_low_kg"] is None
        assert summary["avoided_fuel_high_kg"] is None
        row = result["indicator_results"][0]
        assert row["historical_baseline_use_raw"] == 200
        assert row["lightweight_use_low_raw"] is None
        assert row["baseline_total_high_raw"] is None
        if cached:
            baseline_use = float(baseline_fuel * Decimal("4.148118595"))
            assert summary["baseline_use_kgco2e"] == pytest.approx(baseline_use)
            assert summary["lightweight_use_central_kgco2e"] == pytest.approx(baseline_use / 2)
            assert summary["weighted_baseline_point"] == pytest.approx((100 + baseline_use) / 20)
            assert row["fuel_factor_status"] == "historical_unvalidated"
            for key in ("localization_indicator_results", "named_supplier_indicator_results"):
                assert result[key]
                for localized in result[key]:
                    assert localized["baseline_use_raw"] == pytest.approx(baseline_use)
                    assert localized["lightweight_use_central_raw"] == pytest.approx(baseline_use / 2)
                    assert localized["localized_lightweight_total_central_raw"] == pytest.approx(50 + baseline_use / 2)
        else:
            assert summary["baseline_use_kgco2e"] is None
            assert summary["lightweight_use_central_kgco2e"] is None
            assert summary["baseline_total_central_kgco2e"] is None
            assert summary["weighted_baseline_point"] is None
            assert summary["weighted_lightweight_point"] is None
        return
    assert summary["baseline_use_kgco2e"] == 200
    assert summary["avoided_fuel_central_kg"] == 2
    if cached:
        # Independent arithmetic: 5 kg * 2000 km / 1000 * .2 = 2 kg fuel.
        assert summary["avoided_use_central_kgco2e"] == pytest.approx(8.29623719)
        assert summary["weighted_lightweight_point"] == pytest.approx(12.0851881405)
        assert summary["cached_result_status"] == "historical_unvalidated"
        assert result["indicator_results"][0]["cache_source_path"] == "memory.csv"
    else:
        assert summary["avoided_use_central_kgco2e"] is None
        assert summary["lightweight_use_central_kgco2e"] is None
        assert summary["weighted_lightweight_point"] is None
        assert summary["weighted_reduction_pct"] is None
        assert summary["fuel_factor_status"] == "unavailable"


@pytest.mark.parametrize("scenario_id", ["current_export", "named_supplier"])
@pytest.mark.parametrize("factor", [None, 4.0, -2.0, 0.0])
def test_article_localization_and_named_memory_oracle(scenario_id, factor):
    rows = _memory_exact_rows((scenario_id,))
    for row in rows:
        row["fuel_factor_raw_per_kg"] = factor
    result, summaries = seat.build_localization_results(
        exact_rows=rows,
        metadata={"Climate Change - total": {"normalization_factor": 10,
                  "weight_fraction": .5, "use_phase_person_equivalent": 20}},
        avoided_fuel={"central": 99999}, regional_scenarios=[], scenario_ids=[scenario_id],
        mission={"calculation_method": "steinegger_a322_2017", "baseline_fuel_kg": 1000,
                 "target_fuel_kg": 500, "avoided_fuel_kg": 500},
    )
    row = result[0]
    assert row["historical_baseline_use_raw"] == 200
    assert row["lightweight_use_high_raw"] is None
    if factor is None:
        assert row["baseline_use_raw"] is None
        assert row["lightweight_use_central_raw"] is None
        assert row["localized_lightweight_total_central_raw"] is None
        assert summaries[0]["weighted_point"] is None
        assert summaries[0]["weighted_reduction_vs_reference_pct"] is None
    else:
        assert row["baseline_use_raw"] == 1000 * factor
        assert row["lightweight_use_central_raw"] == 500 * factor
        assert row["avoided_use_central_raw"] == 500 * factor
        assert row["localized_lightweight_total_central_raw"] == 50 + 500 * factor
        assert summaries[0]["weighted_point"] == (50 + 500 * factor) / 20
        assert row["fuel_factor_status"] == "historical_unvalidated"


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
            "baseline_production_raw": 100,
            "lightweight_production_raw": 50,
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
            "baseline_production_raw": 100,
            "lightweight_production_raw": 50,
            "fuel_factor_raw_per_kg": 4.1 if indicator_id == "Climate Change - total" else 0.1,
        }
        for sourcing_id in LOCALIZATION_SCENARIO_IDS
        for indicator_id in INDICATOR_METHODS
    ]

    assert is_exact_localization_rows(rows) is True

    rows = [row for row in rows if row["sourcing_scenario_id"] != "france_first"]
    assert is_exact_localization_rows(rows) is False
