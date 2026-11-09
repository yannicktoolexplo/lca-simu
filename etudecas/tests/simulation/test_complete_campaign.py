"""Pure planning contracts: no simulations, file mutation or integrity probes."""
from pathlib import Path
import pytest

from etudecas.simulation.complete_campaign import (
    build_plan,option,map_command,enrich_nominal_manifest,identity,RISK_KEYS,
    validate_montecarlo_completion,validate_sensitivity_completion,
)


def test_current_campaign_keeps_all_requested_families_and_five_year_horizon():
    root=Path("C:/dev/lca-simu/etudecas/artifacts/testing/campaign-memory-contract")
    plan=build_plan(root,root/"map.html",days=1825,mc_runs=200,workers=1,seed=42,suppliers=8)
    assert plan["days"]==1825
    assert len([stage for stage in plan["stages"] if stage["action"]=="risk_run"])==5
    assert {stage["risk_key"] for stage in plan["stages"] if stage["action"]=="risk_run"}==set(RISK_KEYS)
    assert plan["run_budget"]=={"nominal":1,"risk_companions":5,"supplier_sensitivity":181,
        "montecarlo":201,"implicit_paired_runs":0,"extra_global_sensitivity":0}
    nominal=plan["stages"][0]["command"]
    assert "etudecas.simulation.current_reference" in nominal
    assert nominal[nominal.index("--forecast-mode")+1]=="coherent_scenario"
    assert "run_first_simulation.py" not in nominal


def test_montecarlo_is_explicit_and_does_not_add_paired_campaign_or_old_results():
    root=Path("C:/dev/lca-simu/etudecas/artifacts/testing/campaign-memory-contract")
    plan=build_plan(root,root/"map.html",days=1825,mc_runs=200,workers=1,seed=42,suppliers=8)
    stage=next(stage for stage in plan["stages"] if stage["id"]=="montecarlo")
    command=stage["command"]
    assert "--no-paired-propagation" in command and "--save-trajectories" in command
    assert command[command.index("--manifest-json")+1]==str(root/"nominal/run_manifest.json")
    assert command[command.index("--runs")+1]=="200"
    assert command[command.index("--workers")+1]=="1"
    assert command[command.index("--uncertainty-profile")+1]=="workshop"
    assert stage["outputs"]==[str(root/"montecarlo/montecarlo_summary.json")]


def test_criticality_consumes_new_sensitivity_and_nominal_only():
    root=Path("C:/dev/lca-simu/etudecas/artifacts/testing/campaign-memory-contract")
    plan=build_plan(root,root/"map.html",days=1825,mc_runs=200,workers=1,seed=42,suppliers=8)
    command=next(stage for stage in plan["stages"] if stage["id"]=="criticality")["command"]
    assert command[command.index("--sim-result-dir")+1]==str(root/"nominal")
    assert command[command.index("--sensitivity-dir")+1]==str(root/"sensitivity/supplier_parameter")


def test_option_replaces_duplicate_forms_without_reordering_other_tokens():
    assert option(["--x","A","--profile","old","--x=B","--z"],"--x","new")==[
        "--profile","old","--z","--x","new"]


def test_progress_map_never_uses_pending_or_historical_analysis_results():
    root=Path("C:/dev/lca-simu/etudecas/artifacts/testing/campaign-memory-contract")
    plan=build_plan(root,root/"map.html",days=1825,mc_runs=200,workers=1,seed=42,suppliers=8)
    command=map_command(plan,{"nominal"})
    for name in ["--simulated-risk-output-dir","--montecarlo-summary-json","--sensitivity-cases-csv",
                 "--supplier-parameter-cases-csv","--supplier-local-criticality-csv","--supplier-risk-kpi-supplier-csv"]:
        assert "__not_yet_calculated__" in command[command.index(name)+1]
    assert "--read-only-source" in command and "--chunked-embedded-payload" in command
    final=map_command(plan)
    assert final[final.index("--simulated-risk-output-dir")+1]==str(root/"risks/full")
    assert final[final.index("--montecarlo-summary-json")+1]==str(root/"montecarlo/montecarlo_summary.json")


def test_nominal_metadata_enrichment_preserves_the_execution_receipt_in_memory():
    root=Path("C:/dev/lca-simu/etudecas/artifacts/testing/campaign-memory-contract")
    nominal=root/"nominal"
    original={"graph":str(nominal/"input_graph.json"),"days":1825,"scenario_id":"scn:BASE",
              "command":["python","-m","etudecas.simulation.current_reference"],
              "engine_arguments":["--lot-trace","--days","1825"],"inputs":{"graph":"input-sha"},
              "runtime":{"historical_F3_budgets":467},"status":"passed_execution"}
    immutable_receipt_sha=identity(original)
    companions={"full":{"scenario_id":"scn:BASE","run_id":"risk_full","output_dir":str(root/"risks/full")}}
    enriched=enrich_nominal_manifest(original,graph=nominal/"input_graph.json",output=nominal,
                                     companions=companions,source_sha256="original-byte-sha")
    assert identity(original)==immutable_receipt_sha
    assert identity(enriched)!=immutable_receipt_sha  # delivery metadata is a separate view
    for field in ["command","engine_arguments","inputs","runtime","days","scenario_id","status"]:
        assert enriched[field]==original[field]
    assert enriched["companion_runs"]==companions
    assert enriched["campaign_metadata_enrichment"]["physics_fields_sha256"]==identity(original)
    plan=build_plan(root,root/"map.html",days=1825,mc_runs=200,workers=1,seed=42,suppliers=8)
    nominal_outputs=plan["stages"][0]["outputs"]
    assert str(nominal/"complete_campaign_execution_manifest.json") in nominal_outputs
    assert str(nominal/"run_manifest.json") not in nominal_outputs
    assert str(root/"nominal_metadata_enrichment.json") in plan["stages"][1]["outputs"]


def test_montecarlo_completion_rejects_partial_or_duplicate_draw_data_in_memory():
    complete={"runs_requested_excluding_baseline":2,"runs_total_including_baseline":3,
              "successful_runs":3,"successful_stochastic_runs":2,"failed_runs":0}
    rows=[{"run_id":f"run_{i:04d}","status":"ok","is_baseline":i==0} for i in range(3)]
    validate_montecarlo_completion(complete,rows,2)
    for values in [{**complete,"failed_runs":1},{**complete,"runs_total_including_baseline":2},
                   {**complete,"successful_runs":2},{**complete,"successful_stochastic_runs":1}]:
        with pytest.raises(ValueError):validate_montecarlo_completion(values,rows,2)
    with pytest.raises(ValueError):validate_montecarlo_completion(complete,[rows[0],rows[1],rows[1]],2)
    with pytest.raises(ValueError):validate_montecarlo_completion(complete,[rows[0],rows[1]],2)


def test_sensitivity_completion_uses_declared_eligible_supplier_design_in_memory():
    graph=Path("prepared_nominal.json");runner=Path("current_reference_sensitivity_runner.py")
    cases={"baseline":"baseline","capacity_low":"supplier_capacity"}
    summary={"provenance_status":"completed_case_receipts","days":1825,"scenario_id":"scn:BASE",
             "input":str(graph),"run_script":str(runner),"selected_suppliers":["S-1"],
             "parameter_count":1,"simulation_count":2,"baseline":{"case_id":"baseline"}}
    rows=[{"case_id":key,"parameter_key":value,"status":"ok"} for key,value in cases.items()]
    kwargs=dict(expected_cases=cases,expected_parameters=1,expected_suppliers=["S-1"],
                expected_input=graph,expected_runner=runner,days=1825)
    validate_sensitivity_completion(summary,rows,**kwargs)  # one eligible supplier, not a phantom eight
    for values in [{**summary,"simulation_count":1},{**summary,"parameter_count":2},
                   {**summary,"provenance_status":"historical_unverified"}]:
        with pytest.raises(ValueError):validate_sensitivity_completion(values,rows,**kwargs)
    for records in [[],[rows[0]], [rows[0],rows[0]],
                    [rows[0],{"case_id":"capacity_low","parameter_key":"supplier_capacity"}]]:
        with pytest.raises(ValueError):validate_sensitivity_completion(summary,records,**kwargs)
