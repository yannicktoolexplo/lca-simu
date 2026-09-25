"""Independent resume counterexamples; fake execution writes real small artifacts."""
from __future__ import annotations

import json

import pytest

from etudecas import case_config
from etudecas.simulation import analysis_batch_common as common
from etudecas.simulation import source_fingerprint
from etudecas.simulation.sensibility import run_supplier_parameter_sensitivity as supplier
from etudecas.simulation.sensibility import run_threshold_sensitivity_study as threshold


@pytest.fixture(params=["threshold", "supplier"])
def study(request, tmp_path, monkeypatch):
    engine_dir = tmp_path / "engine"
    engine_dir.mkdir()
    engine = engine_dir / "run.py"
    engine.write_text("# engine source version 1\n", encoding="utf-8")
    dependency = engine_dir / "policy.py"
    dependency.write_text("# dynamically imported policy\n", encoding="utf-8")
    config_path = tmp_path / "case-config.json"
    config_path.write_text('{"policy": 1}', encoding="utf-8")
    monkeypatch.setattr(case_config, "DEFAULT_CASE_CONFIG_PATH", config_path)
    # Isolate concurrent edits to the real application during parallel development.
    # The custom engine and its helper use the actual conservative fingerprint.
    original_fingerprint = source_fingerprint.implementation_fingerprint
    study_version = ["study-source-v1"]
    monkeypatch.setattr(source_fingerprint, "implementation_fingerprint", lambda path:
                        study_version[0] if path.name == "analysis_batch_common.py"
                        else original_fingerprint(path))
    module = threshold if request.param == "threshold" else supplier
    kwargs = dict(
        case_id="baseline", level=1.0, config=module.base_case(),
        base_data={"nodes": [], "edges": [], "scenarios": [{"id": "scn:BASE"}]},
        run_script=engine, scenario_id="scn:BASE", days=365,
        cases_root=tmp_path / "cases", artifact_mode="compact",
    )
    if module is threshold:
        kwargs.update(parameter_key="baseline", parameter_group="baseline",
                      parameter_label="Baseline", realism_focus="baseline", retain_detail=False)
    else:
        kwargs.update(spec={"parameter_key": "baseline", "parameter_group": "baseline",
                            "parameter_label": "Baseline", "safe_direction": "baseline"},
                      extra_args=["--seed", "731"], supplier_floor_csv=None)
    calls = []
    behavior = {"after_write": lambda: None}

    def execute(**options):
        calls.append(options)
        output = options["output_dir"]
        summary = {"simulation_days": options["days"],
                   "kpis": {"fill_rate": 0.42, "total_holding_cost": 12.0}}
        common.write_json(output / "summaries/first_simulation_summary.json", summary)
        behavior["after_write"]()
        return (summary, "") if module is threshold else summary

    monkeypatch.setattr(module, "run_simulation" if module is threshold else "run_simulation_case", execute)
    if module is supplier:
        monkeypatch.setattr(module, "operational_metrics", lambda p: {"backlog_days": 2.0})
        monkeypatch.setattr(module, "derived_case_kpis", lambda *p: {"material_delay_days": 3.0})
    return dict(module=module, kwargs=kwargs, calls=calls, behavior=behavior,
                engine=engine, dependency=dependency, case_config=config_path,
                study_version=study_version,
                case_dir=kwargs["cases_root"] / kwargs["case_id"])


def test_identical_case_reuses_all_published_metrics(study, monkeypatch):
    first = study["module"].run_case(**study["kwargs"])
    if study["module"] is supplier:
        monkeypatch.setattr(supplier, "derived_case_kpis", lambda *args:
                            pytest.fail("Pruned metrics must be loaded from the completed receipt"))
    second = study["module"].run_case(**study["kwargs"])
    assert first == second
    assert len(study["calls"]) == 1
    assert first["kpi::fill_rate"] == 0.42


@pytest.mark.parametrize("changed", ["graph", "config", "horizon", "scenario", "engine", "dependency", "study", "case_config"])
def test_changed_identity_refuses_reuse_and_preserves_old_files(study, changed):
    study["module"].run_case(**study["kwargs"])
    directory = study["case_dir"]
    before = {p.relative_to(directory).as_posix(): p.read_bytes() for p in directory.rglob("*") if p.is_file()}
    if changed == "graph":
        study["kwargs"]["base_data"]["source_revision"] = 2
    elif changed == "config":
        study["kwargs"]["config"]["factors"]["capacity_scale"] = 1.25
    elif changed == "horizon":
        study["kwargs"]["days"] = 1825
    elif changed == "scenario":
        study["kwargs"]["scenario_id"] = "scn:OTHER"
    elif changed == "study":
        study["study_version"][0] = "study-source-v2"
    else:
        study[changed].write_text("changed source or external configuration", encoding="utf-8")
    with pytest.raises(ValueError, match="Cannot safely resume"):
        study["module"].run_case(**study["kwargs"])
    assert len(study["calls"]) == 1
    assert before == {p.relative_to(directory).as_posix(): p.read_bytes() for p in directory.rglob("*") if p.is_file()}


def test_legacy_summary_is_never_a_resume_proof(study):
    directory = study["case_dir"]
    common.write_json(directory / "input_case.json", {"old": True})
    common.write_json(directory / "simulation_output/summaries/first_simulation_summary.json",
                      {"simulation_days": 1, "kpis": {"fill_rate": 0.999}})
    with pytest.raises(ValueError, match="new output directory"):
        study["module"].run_case(**study["kwargs"])
    assert not study["calls"]
    assert not (directory / common.STUDY_CASE_RECEIPT).exists()


@pytest.mark.parametrize("changed", ["input", "summary", "row", "missing_input_proof"])
def test_modified_result_is_refused(study, changed):
    study["module"].run_case(**study["kwargs"])
    directory = study["case_dir"]
    receipt_path = directory / common.STUDY_CASE_RECEIPT
    if changed in {"input", "summary"}:
        file = directory / ("input_case.json" if changed == "input" else
                            "simulation_output/summaries/first_simulation_summary.json")
        file.write_text('{"modified": true}', encoding="utf-8")
    else:
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        if changed == "row":
            receipt["row"]["kpi::fill_rate"] = 0.999
        else:
            del receipt["files"]["input_case.json"]
        receipt_path.write_text(json.dumps(receipt), encoding="utf-8")
    with pytest.raises(ValueError, match="Cannot safely resume"):
        study["module"].run_case(**study["kwargs"])
    assert len(study["calls"]) == 1


@pytest.mark.parametrize("failure", ["engine", "source_drift", "prepared_input"])
def test_no_receipt_is_published_after_incomplete_execution(study, failure):
    def fail():
        if failure == "engine":
            raise RuntimeError("engine stopped after a partial summary")
        if failure == "prepared_input":
            (study["case_dir"] / "input_case.json").write_text('{"changed": true}', encoding="utf-8")
        else:
            study["dependency"].write_text("# source changed during execution\n", encoding="utf-8")
    study["behavior"]["after_write"] = fail
    with pytest.raises((RuntimeError, ValueError)):
        study["module"].run_case(**study["kwargs"])
    assert not (study["case_dir"] / common.STUDY_CASE_RECEIPT).exists()


@pytest.mark.parametrize("changed", ["seed", "option", "external_csv", "floor_csv"])
@pytest.mark.parametrize("study", ["supplier"], indirect=True)
def test_supplier_options_and_external_file_contents_are_part_of_identity(study, changed):
    external = study["case_dir"].parent.parent / "external.csv"
    external.write_text("supplier_id,nominal_capacity_qty_per_day\nSUP,10\n", encoding="utf-8")
    if changed == "floor_csv":
        study["kwargs"]["supplier_floor_csv"] = external
    else:
        study["kwargs"]["extra_args"].append("--supplier-risk-events-csv=" + str(external))
    supplier.run_case(**study["kwargs"])
    if changed in {"floor_csv", "external_csv"}:
        external.write_text("supplier_id,nominal_capacity_qty_per_day\nSUP,11\n", encoding="utf-8")
    elif changed == "seed":
        study["kwargs"]["extra_args"][1] = "732"
    else:
        study["kwargs"]["extra_args"].append("--no-common-random-numbers")
    with pytest.raises(ValueError, match="Cannot safely resume"):
        supplier.run_case(**study["kwargs"])
    assert len(study["calls"]) == 1


@pytest.mark.parametrize("study", ["supplier"], indirect=True)
def test_supplier_csv_shortcut_cannot_bypass_case_validation(study, monkeypatch):
    root = study["case_dir"].parent.parent
    graph = root / "graph.json"
    common.write_json(graph, study["kwargs"]["base_data"])
    study["case_dir"].mkdir(parents=True)
    common.write_json(study["case_dir"] / "simulation_output/summaries/first_simulation_summary.json", {"old": True})
    forged = dict(case_id="baseline", parameter_key="baseline", status="ok",
                  case_output_dir=str(study["case_dir"] / "simulation_output"))
    # Every column required by the former CSV shortcut is present.
    forged.update({"kpi::" + key: 1 for key in (
        "product_availability", "line_adherence", "line_nervousness",
        "production_replanning_count", "production_replanning_rate",
        "raw_material_stockout_days", "material_delay_days", "inventory_cost",
    )})
    supplier.write_csv(root / "supplier_parameter_sensitivity_cases.csv", [forged])
    monkeypatch.setattr("sys.argv", ["supplier", "--input", str(graph), "--run-script", str(study["engine"]),
                                   "--output-dir", str(root), "--baseline-result-dir", str(root)])
    monkeypatch.setattr(supplier, "build_specs", lambda *args: [])
    with pytest.raises(ValueError, match="Cannot safely resume"):
        supplier.main()
    assert not study["calls"]


@pytest.mark.parametrize("study", ["supplier"], indirect=True)
def test_supplier_metrics_failure_does_not_publish_receipt(study, monkeypatch):
    def fail(*args):
        raise ValueError("invalid derived metric")
    monkeypatch.setattr(supplier, "derived_case_kpis", fail)
    with pytest.raises(ValueError, match="invalid derived metric"):
        supplier.run_case(**study["kwargs"])
    assert not (study["case_dir"] / common.STUDY_CASE_RECEIPT).exists()


@pytest.mark.parametrize("study", ["supplier"], indirect=True)
def test_prepared_floor_drift_cannot_be_signed_after_execution(study):
    floor = study["engine"].parent / "floor.csv"
    floor.write_text("supplier_id,nominal_capacity_qty_per_day\nSUP,10\n", encoding="utf-8")
    study["kwargs"]["supplier_floor_csv"] = floor
    def mutate():
        (study["case_dir"] / "supplier_neutral_floors_case.csv").write_text(
            "supplier_id,nominal_capacity_qty_per_day\nSUP,999\n", encoding="utf-8")
    study["behavior"]["after_write"] = mutate
    with pytest.raises(ValueError, match="Prepared study inputs changed"):
        supplier.run_case(**study["kwargs"])
    assert not (study["case_dir"] / common.STUDY_CASE_RECEIPT).exists()


@pytest.mark.parametrize("study", ["supplier"], indirect=True)
def test_historical_summary_does_not_adopt_current_cli_provenance(study, monkeypatch):
    root = study["case_dir"].parent.parent
    graph = root / "graph.json"
    common.write_json(graph, study["kwargs"]["base_data"])
    supplier.write_csv(root / "supplier_parameter_sensitivity_cases.csv", [
        {"case_id": "old", "parameter_key": "baseline", "status": "ok", "kpi::fill_rate": 0.24},
    ])
    monkeypatch.setattr("sys.argv", ["supplier", "--input", str(graph), "--run-script", str(study["engine"]),
                                   "--output-dir", str(root), "--days", "1825", "--summarize-existing"])
    monkeypatch.setattr(supplier, "build_specs", lambda *args: [])
    supplier.main()
    report = common.load_json(root / "supplier_parameter_sensitivity_summary.json")
    assert report["provenance_status"] == "historical_unverified"
    assert report["days"] is None and report["scenario_id"] is None and report["input"] is None
    assert report["baseline"]["kpi::fill_rate"] == "0.24"
    rendered = (root / "supplier_parameter_sensitivity_report.md").read_text(encoding="utf-8")
    assert "provenance unverified" in rendered and "Horizon: unknown" in rendered
    assert "Horizon: 1825" not in rendered
    assert not study["calls"]
