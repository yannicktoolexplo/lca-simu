from __future__ import annotations

import pytest

import etudecas.run_etudecas_pipeline as pipeline
from etudecas.run_etudecas_pipeline import selected_state_dependent_scenario_specs


def test_extended_state_dependent_scenarios_are_catalogued() -> None:
    specs = selected_state_dependent_scenario_specs("extended", horizon_days=365)

    assert [spec["slug"] for spec in specs] == [
        "state_dependent_full",
        "state_api_upstream_crisis",
        "state_packaging_quality_crisis",
        "state_downstream_distribution_crisis",
    ]
    assert [spec["scenario_id"] for spec in specs] == [
        "scn:STATE_DEPENDENT_FULL",
        "scn:STATE_API_UPSTREAM_CRISIS",
        "scn:STATE_PACKAGING_QUALITY_CRISIS",
        "scn:STATE_DOWNSTREAM_DISTRIBUTION_CRISIS",
    ]
    assert [spec["label"] for spec in specs] == [
        "Portefeuille state-dependent complet",
        "Crise amont API / matiere critique",
        "Crise qualite packaging / lots rejetes",
        "Crise distribution aval / transport",
    ]
    assert all(callable(spec["event_builder"]) for spec in specs)


def test_state_dependent_scenario_selection_rejects_unknown_key() -> None:
    with pytest.raises(ValueError, match="Unknown state-dependent scenario"):
        selected_state_dependent_scenario_specs("not_a_scenario", horizon_days=365)


def test_montecarlo_summary_falls_back_to_active_artifact(tmp_path, monkeypatch) -> None:
    output_dir = tmp_path / "run"
    summary_dir = output_dir / "summaries"
    summary_dir.mkdir(parents=True)
    (summary_dir / "first_simulation_summary.json").write_text('{"sim_days": 1825}', encoding="utf-8")
    active_summary = tmp_path / "active_montecarlo" / "montecarlo_summary.json"
    active_summary.parent.mkdir()
    active_summary.write_text(
        '{"days_override": 1825, "successful_stochastic_runs": 999}',
        encoding="utf-8",
    )
    monkeypatch.setattr(pipeline, "ACTIVE_MONTECARLO_UNCERTAINTY_SUMMARY_JSON", active_summary)
    monkeypatch.setattr(pipeline, "ACTIVE_MRP_PHYSICAL_RERUN_ROOT", tmp_path / "empty_reruns")

    resolved = pipeline.resolve_montecarlo_summary_for_map(output_dir)

    assert resolved == active_summary


def test_montecarlo_summary_fallback_prefers_more_compatible_runs(tmp_path, monkeypatch) -> None:
    output_dir = tmp_path / "run"
    summary_dir = output_dir / "summaries"
    summary_dir.mkdir(parents=True)
    (summary_dir / "first_simulation_summary.json").write_text('{"sim_days": 1825}', encoding="utf-8")

    low_run_summary = tmp_path / "active_montecarlo" / "montecarlo_summary.json"
    low_run_summary.parent.mkdir()
    low_run_summary.write_text(
        '{"days_override": 1825, "successful_stochastic_runs": 10}',
        encoding="utf-8",
    )

    rerun_root = tmp_path / "reruns"
    high_run_summary = rerun_root / "active_previous_5y_20260702" / "montecarlo" / "selected" / "montecarlo_summary.json"
    high_run_summary.parent.mkdir(parents=True)
    high_run_summary.write_text(
        '{"days_override": 1825, "successful_stochastic_runs": 200}',
        encoding="utf-8",
    )

    monkeypatch.setattr(pipeline, "ACTIVE_MONTECARLO_UNCERTAINTY_SUMMARY_JSON", low_run_summary)
    monkeypatch.setattr(pipeline, "ACTIVE_MRP_PHYSICAL_RERUN_ROOT", rerun_root)

    resolved = pipeline.resolve_montecarlo_summary_for_map(output_dir)

    assert resolved == high_run_summary
