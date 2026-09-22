from __future__ import annotations

import json

import pytest

import etudecas.run_etudecas_pipeline as pipeline
from etudecas.run_etudecas_pipeline import selected_state_dependent_scenario_specs


@pytest.fixture(autouse=True)
def isolated_shared_montecarlo_paths(tmp_path, monkeypatch):
    """Tests must never discover the developer's historical simulation results."""
    monkeypatch.setattr(pipeline, "ROOT", tmp_path / "isolated_etudecas")
    monkeypatch.setattr(pipeline, "ACTIVE_MONTECARLO_UNCERTAINTY_SUMMARY_JSON", tmp_path / "absent_active.json")
    monkeypatch.setattr(pipeline, "ACTIVE_MRP_PHYSICAL_RERUN_ROOT", tmp_path / "absent_reruns")


def _attach_target_manifest(summary_path, output_dir):
    manifest = output_dir / "run_manifest.json"
    manifest.write_text('{}', encoding="utf-8")
    value = json.loads(summary_path.read_text(encoding="utf-8"))
    value["manifest"] = {"manifest_path": str(manifest.resolve())}
    summary_path.write_text(json.dumps(value), encoding="utf-8")


def test_operational_map_optional_analyses_are_run_local(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(pipeline, "run_python", lambda script, *args: calls.append(args))
    output = tmp_path / "fresh"
    pipeline.build_map_for_simulation_result(input_graph=tmp_path / "graph.json",
        output_dir=output, supplier_criticality_dir=output / "supplier_criticality")
    args = calls[0]
    from pathlib import Path
    for option in ("--sensitivity-cases-csv", "--structural-sensitivity-cases-csv",
                   "--supplier-parameter-sensitivity-summary-json", "--supplier-parameter-summary-csv",
                   "--supplier-parameter-cases-csv", "--supplier-risk-campaign-summary-json",
                   "--supplier-risk-campaign-summary-csv", "--supplier-risk-campaign-cases-csv"):
        path = Path(args[args.index(option) + 1]).resolve()
        assert path.is_relative_to((output / "analyses").resolve())
    assert "--montecarlo-summary-json" not in args


@pytest.mark.parametrize("compressed", [True, False])
def test_map_compression_marker_after_embedded_plotly_is_checked(tmp_path, compressed):
    maps = tmp_path / "maps"
    maps.mkdir()
    marker = "const DATA_CHUNKED_GZIP_BASE64 = {};" if compressed else "const DATA = {};"
    (maps / "supply_graph_fixture.html").write_text(" " * 700000 + marker, encoding="utf-8")
    checks = pipeline.validate_active_run_outputs(tmp_path, scenario_id="scn:BASE",
        days=1, output_profile="compact", max_map_mb=40)
    assert next(c["ok"] for c in checks if c["name"] == "map_payload_compressed") is compressed


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
    _attach_target_manifest(active_summary, output_dir)
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

    _attach_target_manifest(low_run_summary, output_dir)
    _attach_target_manifest(high_run_summary, output_dir)
    monkeypatch.setattr(pipeline, "ACTIVE_MONTECARLO_UNCERTAINTY_SUMMARY_JSON", low_run_summary)
    monkeypatch.setattr(pipeline, "ACTIVE_MRP_PHYSICAL_RERUN_ROOT", rerun_root)

    resolved = pipeline.resolve_montecarlo_summary_for_map(output_dir)

    assert resolved == high_run_summary


@pytest.mark.parametrize("control_mode", ["none", "schedule", "feedback"])
def test_direct_simulation_forwards_only_the_requested_control_source(
    tmp_path,
    monkeypatch,
    control_mode,
) -> None:
    calls: list[tuple[object, ...]] = []
    monkeypatch.setattr(
        pipeline,
        "run_python",
        lambda script, *args: calls.append((script, *args)),
    )
    for name in [
        "build_component_stock_artifacts",
        "build_finished_goods_stock_artifacts",
        "build_component_stock_source_truth_reports",
        "build_finished_goods_stock_source_truth_reports",
        "export_run_package",
    ]:
        monkeypatch.setattr(pipeline, name, lambda **kwargs: None)

    schedule = tmp_path / "daily controls.csv" if control_mode == "schedule" else None
    policy = tmp_path / "state feedback.json" if control_mode == "feedback" else None
    pipeline.run_direct_simulation(
        input_graph=tmp_path / "graph.json",
        output_dir=tmp_path / "run",
        scenario_id="scn:BASE",
        days=10,
        skip_map=True,
        skip_plots=False,
        control_schedule_csv=schedule,
        control_policy_json=policy,
    )

    assert len(calls) == 1
    command = list(calls[0][1:])
    if schedule is None:
        assert "--control-schedule-csv" not in command
    else:
        flag_index = command.index("--control-schedule-csv")
        assert command[flag_index + 1] == pipeline.repo_rel(schedule)
    if policy is None:
        assert "--control-policy-json" not in command
    else:
        flag_index = command.index("--control-policy-json")
        assert command[flag_index + 1] == pipeline.repo_rel(policy)
    assert "--seed" not in command
    assert "--common-random-numbers" not in command
    assert "--no-common-random-numbers" not in command


def test_direct_simulation_rejects_mixed_open_and_closed_loop_controls(
    tmp_path,
) -> None:
    with pytest.raises(ValueError, match="mutually exclusive"):
        pipeline.run_direct_simulation(
            input_graph=tmp_path / "graph.json",
            output_dir=tmp_path / "run",
            scenario_id="scn:BASE",
            days=10,
            skip_map=True,
            skip_plots=True,
            control_schedule_csv=tmp_path / "schedule.csv",
            control_policy_json=tmp_path / "policy.json",
        )


@pytest.mark.parametrize(
    ("common_random_numbers", "expected_flag"),
    [
        (True, "--common-random-numbers"),
        (False, "--no-common-random-numbers"),
    ],
)
def test_direct_simulation_forwards_typed_randomness_controls(
    tmp_path,
    monkeypatch,
    common_random_numbers,
    expected_flag,
) -> None:
    calls: list[tuple[object, ...]] = []
    monkeypatch.setattr(
        pipeline,
        "run_python",
        lambda script, *args: calls.append((script, *args)),
    )
    for name in [
        "build_component_stock_artifacts",
        "build_finished_goods_stock_artifacts",
        "build_component_stock_source_truth_reports",
        "build_finished_goods_stock_source_truth_reports",
        "export_run_package",
    ]:
        monkeypatch.setattr(pipeline, name, lambda **kwargs: None)

    pipeline.run_direct_simulation(
        input_graph=tmp_path / "graph.json",
        output_dir=tmp_path / "run",
        scenario_id="scn:BASE",
        days=10,
        skip_map=True,
        skip_plots=True,
        seed=2027,
        common_random_numbers=common_random_numbers,
    )

    command = list(calls[0][1:])
    seed_index = command.index("--seed")
    assert command[seed_index + 1] == "2027"
    assert expected_flag in command


@pytest.mark.parametrize("payload", [
    None, [], {"days_override": "bad"}, {"days_override": True},
    {"days_override": 10.5}, {"days_override": -1}, {"days_override": 0},
    {"days_override": 20}, {}, {"days_override": 10, "manifest": []},
    {"days_override": 10, "run_manifest": 123},
    {"days_override": 10, "run_manifest": "other/run_manifest.json"},
    {"days_override": 10},
])
def test_shared_montecarlo_rejects_missing_incompatible_or_malformed_provenance(tmp_path, monkeypatch, payload):
    output = tmp_path / "run"
    (output / "summaries").mkdir(parents=True)
    (output / "summaries" / "first_simulation_summary.json").write_text('{"sim_days": 10}', encoding="utf-8")
    shared = tmp_path / "shared.json"
    shared.write_text(json.dumps(payload), encoding="utf-8")
    monkeypatch.setattr(pipeline, "ACTIVE_MONTECARLO_UNCERTAINTY_SUMMARY_JSON", shared)
    expected = output / "montecarlo" / "selected" / "montecarlo_summary.json"
    assert pipeline.resolve_montecarlo_summary_for_map(output) == expected
    assert not expected.exists()


@pytest.mark.parametrize("local", [False, True])
def test_incompatible_explicit_or_local_summary_raises(tmp_path, local):
    output = tmp_path / "run"
    (output / "summaries").mkdir(parents=True)
    (output / "summaries" / "first_simulation_summary.json").write_text('{"sim_days": 10}', encoding="utf-8")
    candidate = output / "montecarlo" / "selected" / "montecarlo_summary.json" if local else tmp_path / "explicit.json"
    candidate.parent.mkdir(parents=True, exist_ok=True)
    candidate.write_text('{"days_override": 20}', encoding="utf-8")
    with pytest.raises(ValueError, match="not compatible"):
        pipeline.resolve_montecarlo_summary_for_map(output, None if local else candidate)


def test_local_summary_allows_missing_manifest_but_shared_does_not(tmp_path):
    candidate = tmp_path / "summary.json"
    candidate.write_text('{"days_override": 10}', encoding="utf-8")
    kwargs = dict(target_days=10, target_manifest_candidates=[])
    assert pipeline.montecarlo_summary_matches_run(candidate, allow_missing_manifest=True, **kwargs)
    assert not pipeline.montecarlo_summary_matches_run(candidate, allow_missing_manifest=False, **kwargs)


@pytest.mark.parametrize("nested", [False, True])
def test_shared_summary_accepts_both_target_manifest_locations(tmp_path, nested):
    manifest = tmp_path / "run" / "run_manifest.json" if nested else tmp_path / "run_manifest.json"
    candidate = tmp_path / "summary.json"
    candidate.write_text(json.dumps({"days_override": 10, "run_manifest": str(manifest)}), encoding="utf-8")
    assert pipeline.montecarlo_summary_matches_run(candidate, target_days=10,
        target_manifest_candidates=[tmp_path / "run_manifest.json", tmp_path / "run" / "run_manifest.json"],
        allow_missing_manifest=False)


def test_shared_fallback_can_be_disabled(tmp_path, monkeypatch):
    output = tmp_path / "run"
    output.mkdir()
    shared = tmp_path / "shared.json"
    shared.write_text('{"days_override": 10}', encoding="utf-8")
    _attach_target_manifest(shared, output)
    monkeypatch.setattr(pipeline, "ACTIVE_MONTECARLO_UNCERTAINTY_SUMMARY_JSON", shared)
    expected = output / "montecarlo" / "selected" / "montecarlo_summary.json"
    assert pipeline.resolve_montecarlo_summary_for_map(output, allow_shared_fallback=False) == expected
    assert pipeline.resolve_montecarlo_summary_for_map(output) == shared
