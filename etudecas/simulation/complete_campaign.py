"""Execute a resumable complete-map campaign through the current MRP runtime.

This orchestrates existing simulators and analyses. A completed stage means its
command finished and its declared outputs were recorded, never industrial
calibration or independent qualification. No old result is a fallback.
"""
from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT = ROOT / "etudecas/artifacts/testing/campagne_complete_20261109/campaign"
DEFAULT_MAP = ROOT / "etudecas/resultats/campagne_complete_20261109/carte_complete.html"
RISK_KEYS = ("full", "api_upstream", "packaging_quality", "downstream_distribution", "internal_release_capacity")
_PROCESS_OBSERVER: Callable[[int | None], None] | None = None


def read(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8", newline="\n")


def sha(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def identity(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=True, separators=(",", ":")).encode()).hexdigest()


def campaign_path(raw: str | Path) -> Path:
    path = Path(raw).resolve()
    allowed = (ROOT / "etudecas/artifacts/testing", ROOT / "etudecas/resultats")
    if not any(path.is_relative_to(base) and path != base for base in allowed):
        raise ValueError("Campaign outputs must be in a dedicated directory under etudecas/artifacts/testing or etudecas/resultats")
    return path


def option(args: list[str], name: str, value: str) -> list[str]:
    result = []
    index = 0
    while index < len(args):
        token = args[index]
        if token == name:
            index += 2
        elif token.startswith(name + "="):
            index += 1
        else:
            result.append(token); index += 1
    return [*result, name, value]


def python_module(module: str, *args: str) -> list[str]:
    return [sys.executable, "-B", "-m", module, *map(str, args)]


def build_plan(output: Path, map_output: Path, *, days: int, mc_runs: int, workers: int,
               seed: int, suppliers: int, uncertainty_profile: str = "workshop",
               global_sensitivity: bool = False) -> dict[str, Any]:
    if not 1 <= days <= 1825 or mc_runs < 2 or workers < 1 or suppliers < 1:
        raise ValueError("Require1..1825days, at least2MCdraws, one worker and one supplier")
    nominal = output / "nominal"
    graph = nominal / "input_graph.json"
    manifest = nominal / "run_manifest.json"
    supplier = output / "sensitivity/supplier_parameter"
    mc = output / "montecarlo"
    stages = [{"id": "nominal", "action": "command", "command": python_module(
        "etudecas.simulation.current_reference", "--days", str(days), "--forecast-mode", "coherent_scenario",
        "--output-dir", str(nominal)), "outputs": [str(nominal / "complete_campaign_execution_manifest.json"), str(nominal / "data/production_lot_events.csv"),
                                                   str(nominal / "data/production_lot_genealogy.csv")]}]
    stages.append({"id": "prepare_risks", "action": "prepare_risks", "outputs": [str(output / "risk_inputs/index.json"),str(output / "nominal_metadata_enrichment.json")]})
    for key in RISK_KEYS:
        stages.append({"id": "risk_" + key, "action": "risk_run", "risk_key": key,
                       "outputs": [str(output / "risks" / key / "run_manifest.json")]})
    stages.append({"id": "sensitivity", "action": "command", "command": python_module(
        "etudecas.simulation.sensibility.run_supplier_parameter_sensitivity",
        "--input", str(graph), "--baseline-manifest", str(manifest), "--baseline-result-dir", str(nominal),
        "--days", str(days), "--top-suppliers", str(suppliers), "--artifact-mode", "summary",
        "--output-dir", str(supplier)), "outputs": [str(supplier / "supplier_parameter_sensitivity_cases.csv"),
        str(supplier / "supplier_parameter_sensitivity_summary.json"), str(supplier / "supplier_parameter_threshold_summary.csv")]})
    if global_sensitivity:
        stages.append({"id": "global_sensitivity", "action": "command", "command": python_module(
            "etudecas.simulation.sensibility.run_sensitivity_analysis", "--input", str(graph),
            "--run-manifest", str(manifest), "--days", str(days), "--output-dir", str(output / "sensitivity/global")),
            "outputs": [str(output / "sensitivity/global/sensitivity_cases.csv")]})
    stages.extend([
        {"id": "publish_sensitivity", "action": "publish_sensitivity", "outputs": [str(output / "analyses/sensitivity_cases.csv")]},
        {"id": "risk_registries", "action": "risk_registries", "outputs": [str(output / "risk_registry_index.json")]},
        {"id": "packages", "action": "packages", "outputs": [str(nominal / "run/artifact_index.json")]},
        {"id": "criticality", "action": "command", "command": python_module(
            "etudecas.risk.supplier_criticality.build_supplier_criticality", "--sim-result-dir", str(nominal),
            "--sensitivity-dir", str(supplier),
            "--output-dir", str(output / "supplier_criticality")), "outputs": [str(output / "supplier_criticality/summaries/supplier_risk_kpi_summary.json")]},
        {"id": "local_criticality", "action": "local_criticality", "outputs": [str(nominal / "summaries/supplier_local_criticality_summary.json")]},
        {"id": "montecarlo", "action": "command", "command": python_module(
            "etudecas.simulation.montecarlo.run_montecarlo_analysis", "--manifest-json", str(manifest),
            "--days", str(days), "--runs", str(mc_runs), "--workers", str(workers), "--seed", str(seed),
            "--uncertainty-profile", uncertainty_profile, "--save-trajectories", "--no-paired-propagation",
            "--nominal-lot-events-csv", str(nominal / "data/production_lot_events.csv"), "--output-dir", str(mc)),
         "outputs": [str(mc / "montecarlo_summary.json")]},
        {"id": "map", "action": "map", "outputs": [str(map_output)]},
    ])
    return {"schema": "etudecas.complete-current-campaign.v1", "reference": "coherent-MRP-20261014",
            "days": days, "forecast_mode": "coherent_scenario", "seed": seed,
            "output": str(output), "map_output": str(map_output), "montecarlo_runs": mc_runs,
            "workers": workers, "top_suppliers": suppliers, "uncertainty_profile": uncertainty_profile,
            "global_sensitivity_extra": global_sensitivity,
            "run_budget": {"nominal": 1, "risk_companions": 5, "supplier_sensitivity": 29 + suppliers * 19,
                           "montecarlo": mc_runs + 1, "implicit_paired_runs": 0,
                           "extra_global_sensitivity": "additional design-dependent runs" if global_sensitivity else 0},
            "stages": stages,
            "interpretation": ["New executions only; no historical result fallback.",
                               "2025 historical reconciliation;2026-2029 declared projections.",
                               "Stress-event catalogue supplies hypotheses, not newly measured industrial probabilities.",
                               "Completion is execution/output evidence, not independent qualification."]}


def check_outputs(stage: dict[str, Any]) -> dict[str, str]:
    missing = [name for name in stage["outputs"] if not Path(name).is_file()]
    if missing:
        raise FileNotFoundError("Missing declared outputs: " + ", ".join(missing))
    return {name: sha(Path(name)) for name in stage["outputs"]}


def run_command(command: list[str], log: Path) -> None:
    log.parent.mkdir(parents=True, exist_ok=True)
    with log.open("a", encoding="utf-8") as stream:
        stream.write("\nCOMMAND " + json.dumps(command, ensure_ascii=False) + "\n"); stream.flush()
        with subprocess.Popen(command, cwd=ROOT, stdout=stream, stderr=subprocess.STDOUT) as process:
            if _PROCESS_OBSERVER: _PROCESS_OBSERVER(process.pid)
            try:
                returncode=process.wait()
            finally:
                if process.poll() is not None and _PROCESS_OBSERVER: _PROCESS_OBSERVER(None)
    if returncode:
        raise RuntimeError(f"Command failed({returncode}); see {log}")


def process_alive(pid: int | None) -> bool:
    """Read process status without signalling a Windows process."""
    if not pid:return False
    if os.name=="nt":
        import ctypes
        from ctypes import wintypes as w
        kernel=ctypes.WinDLL("kernel32",use_last_error=True)
        kernel.OpenProcess.argtypes=[w.DWORD,w.BOOL,w.DWORD];kernel.OpenProcess.restype=w.HANDLE
        kernel.GetExitCodeProcess.argtypes=[w.HANDLE,ctypes.POINTER(w.DWORD)];kernel.GetExitCodeProcess.restype=w.BOOL
        kernel.CloseHandle.argtypes=[w.HANDLE];kernel.CloseHandle.restype=w.BOOL
        handle=kernel.OpenProcess(0x1000,False,pid)
        if not handle:return ctypes.get_last_error()==5  # unknown permission is treated as active
        try:
            code=w.DWORD()
            return not kernel.GetExitCodeProcess(handle,ctypes.byref(code)) or code.value==259
        finally:kernel.CloseHandle(handle)
    try:os.kill(pid,0)
    except ProcessLookupError:return False
    except PermissionError:return True
    return True


def enrich_nominal_manifest(original: dict[str, Any], *, graph: Path, output: Path,
                            companions: dict[str, Any], source_sha256: str) -> dict[str, Any]:
    """Add delivery metadata without mutating the immutable execution receipt."""
    if "campaign_metadata_enrichment" in original:
        raise ValueError("Nominal manifest has already been enriched; inspect the stage receipt")
    declared=original.get("input_graph") or original.get("graph")
    if declared:
        path=Path(declared)
        path=path if path.is_absolute() else ROOT/path
        if path.resolve()!=graph.resolve():raise ValueError("Enrichment may not redirect the nominal input graph")
    allowed={"input_graph","output_dir","companion_runs","campaign_metadata_enrichment"}
    physics={key:value for key,value in original.items() if key not in allowed}
    enriched=json.loads(json.dumps(original))
    enriched.update(input_graph=str(graph),output_dir=str(output),companion_runs=companions,
                    campaign_metadata_enrichment={"source_manifest_sha256":source_sha256,
                        "fields_added_or_updated":sorted(allowed),
                        "physics_fields_sha256":identity(physics),
                        "receipt_basis":"complete_campaign_execution_manifest.json remains immutable"})
    preserved={key:value for key,value in enriched.items() if key not in allowed}
    if preserved!=physics:raise ArithmeticError("Metadata enrichment changed execution/physics fields")
    return enriched


def prepare_risks(plan: dict[str, Any]) -> None:
    from etudecas.run_etudecas_pipeline import selected_state_dependent_scenario_specs
    output = Path(plan["output"])
    nominal = output / "nominal"
    source = read(nominal / "input_graph.json")
    base = next(row for row in source["scenarios"] if row["id"] == "scn:BASE")
    index = {}
    for spec in selected_state_dependent_scenario_specs("all", horizon_days=plan["days"]):
        key = spec["key"]
        graph = json.loads(json.dumps(source))
        scenario = json.loads(json.dumps(base))
        events = spec["event_builder"](graph)
        for event in events:
            event["catalogue_notes"] = event.get("notes", "")
            event["notes"] = "Declared stress hypothesis for the new current-reference campaign; not industrial calibration. " + event.get("notes", "")
        scenario["supplier_risk_events"] = [*(scenario.get("supplier_risk_events") or []), *events]
        scenario["name"] = spec["label"]
        scenario["description"] = "Exploratory stress variant with native state-dependent reactions; not an observed industrial event."
        graph["scenarios"] = [scenario]
        graph["meta"]["complete_campaign_variant"] = {"key": key, "run_id": "risk_" + key,
            "source_scenario_id": "scn:BASE", "engine_scenario_id": "scn:BASE", "events": len(events),
            "source_graph_sha256": sha(nominal / "input_graph.json"), "industrial_calibration_claimed": False,
            "dated_mrp_risk_scope": "preserve_opening_orders",
            "opening_purchase_order_policy": "Preserve source quantities and dates; do not apply risk overlays to opening purchase orders."}
        path = output / "risk_inputs" / (key + ".json")
        write(path, graph)
        index[key] = {"key": key, "label": spec["label"], "graph": str(path),
                      "graph_sha256": sha(path), "events": len(events), "scenario_id": "scn:BASE"}
    write(output / "risk_inputs/index.json", index)
    manifest_path = nominal / "run_manifest.json"
    before_sha=sha(manifest_path)
    snapshot=nominal/"complete_campaign_execution_manifest.json"
    snapshot_before_sha=sha(snapshot)
    original=read(manifest_path)
    companions = {key: {"output_dir": str(output / "risks" / key),
        "scenario_id": "scn:BASE", "run_id": "risk_" + key, "label": value["label"],
        "role": "primary_simulated_risk" if key == "full" else "simulated_risk_variant"}
        for key, value in index.items()}
    manifest=enrich_nominal_manifest(original,graph=nominal/"input_graph.json",output=nominal,
                                     companions=companions,source_sha256=before_sha)
    write(manifest_path, manifest)
    if sha(snapshot)!=snapshot_before_sha:raise ArithmeticError("Immutable nominal execution receipt changed")
    write(output/"nominal_metadata_enrichment.json",{"before_manifest_sha256":before_sha,
        "after_manifest_sha256":sha(manifest_path),"immutable_execution_manifest_sha256":snapshot_before_sha,
        "immutable_execution_manifest_preserved":True,
        "physics_fields_sha256":manifest["campaign_metadata_enrichment"]["physics_fields_sha256"],
        "allowed_metadata_fields":manifest["campaign_metadata_enrichment"]["fields_added_or_updated"],
        "CSV_inputs_commands_and_parameters_changed":False})


def risk_run(plan: dict[str, Any], key: str, log: Path) -> None:
    from etudecas.simulation.analysis_batch_common import sensitivity_run_context
    output = Path(plan["output"])
    manifest = read(output / "nominal/run_manifest.json")
    runner, args = sensitivity_run_context(output / "nominal/run_manifest.json", ROOT / "etudecas/simulation/engine/run_first_simulation.py")
    args = option(args, "--output-profile", "full")
    destination = output / "risks" / key
    graph = output / "risk_inputs" / (key + ".json")
    command = [sys.executable, "-B", str(runner), "--input", str(graph), "--output-dir", str(destination),
               "--scenario-id", "scn:BASE", "--days", str(plan["days"]), *args,
               "--supplier-state-dependent-risks", "--dated-mrp-risk-scope", "preserve_opening_orders",
               "--lot-trace", "--skip-map", "--skip-plots"]
    run_command(command, log)
    for filename in ("production_lot_events.csv", "production_lot_genealogy.csv", "supplier_state_dependent_risk_events.csv"):
        if not (destination / "data" / filename).is_file(): raise FileNotFoundError(filename)
    write(destination / "run_manifest.json", {"reference": plan["reference"], "scenario_id": "scn:BASE",
        "run_id": "risk_" + key, "scenario_label": read(output / "risk_inputs/index.json")[key]["label"],
        "days": plan["days"], "graph": str(graph), "input_graph": str(graph),
        "output": str(destination), "output_dir": str(destination), "command": command,
        "engine_arguments": ["--input", str(graph), "--output-dir", str(destination), "--scenario-id", "scn:BASE", "--days", str(plan["days"]),
                             *[x for x in args if x != "--current-reference-scan3-mode" and x != manifest["scan3_reconciliation_mode"]],
                             "--supplier-state-dependent-risks", "--dated-mrp-risk-scope", "preserve_opening_orders", "--lot-trace"],
        "customer_demand_policy": manifest["customer_demand_policy"],
        "scan3_reconciliation_mode": manifest["scan3_reconciliation_mode"],
        "source_nominal_manifest_sha256": sha(output / "nominal/run_manifest.json"),
        "source_graph_sha256": sha(graph), "supplier_state_dependent_risks": True,
        "dated_mrp_risk_scope": "preserve_opening_orders",
        "status": "passed_execution", "returncode": 0,
        "qualification": "New execution; independent qualification not transferred from nominal."})


def read_csv(path: Path) -> list[dict[str,str]]:
    with path.open(encoding="utf-8-sig",newline="") as stream:return list(csv.DictReader(stream))


def validate_montecarlo_completion(summary: dict[str,Any], records: list[dict[str,Any]], requested: int) -> None:
    """Validate real draw coverage, not just process return code or output presence."""
    expected=requested+1
    required={"runs_requested_excluding_baseline":requested,"runs_total_including_baseline":expected,
              "successful_runs":expected,"successful_stochastic_runs":requested,"failed_runs":0}
    for key,value in required.items():
        if summary.get(key)!=value:raise ValueError(f"Incomplete Monte Carlo {key}: {summary.get(key)!r}, expected{value}")
    ids=[str(row.get("run_id") or "") for row in records]
    if len(records)!=expected or len(set(ids))!=expected or set(ids)!={f"run_{index:04d}" for index in range(expected)}:
        raise ValueError("Monte Carlo CSV does not cover each declared draw exactly once")
    if any(str(row.get("status") or "").lower()!="ok" for row in records):
        raise ValueError("Monte Carlo CSV contains a failed or missing execution status")
    baseline=[row for row in records if str(row.get("is_baseline")).lower() in {"true","1"}]
    if len(baseline)!=1 or baseline[0]["run_id"]!="run_0000":
        raise ValueError("Monte Carlo CSV must have the unique declared baseline")


def validate_sensitivity_completion(summary: dict[str,Any], records: list[dict[str,Any]], *,
        expected_cases: dict[str,str], expected_parameters: int, expected_suppliers: list[str],
        expected_input: Path, expected_runner: Path, days: int) -> None:
    """Pure coverage/source contract; unknown industrial KPI assessments remain allowed."""
    if summary.get("provenance_status")!="completed_case_receipts":
        raise ValueError("Sensitivity lacks current completed-case receipts")
    if summary.get("days")!=days or summary.get("scenario_id")!="scn:BASE":
        raise ValueError("Sensitivity horizon/scenario differs from this campaign")
    if Path(str(summary.get("input") or "")).resolve()!=expected_input.resolve():
        raise ValueError("Sensitivity input is not this campaign's prepared nominal graph")
    if Path(str(summary.get("run_script") or "")).resolve()!=expected_runner.resolve():
        raise ValueError("Sensitivity did not use this campaign's current-reference runner")
    if summary.get("selected_suppliers")!=expected_suppliers:
        raise ValueError("Sensitivity selected suppliers differ from the eligible nominal ranking")
    if summary.get("parameter_count")!=expected_parameters or summary.get("simulation_count")!=len(expected_cases):
        raise ValueError("Sensitivity JSON counts do not cover the declared design")
    ids=[str(row.get("case_id") or "") for row in records]
    if len(records)!=len(expected_cases) or len(set(ids))!=len(ids) or set(ids)!=set(expected_cases):
        raise ValueError("Sensitivity CSV is empty, incomplete, duplicated or contains undeclared cases")
    for row in records:
        if str(row.get("status") or "").lower()!="ok":
            raise ValueError("Sensitivity has a failed or missing execution status")
        if row.get("parameter_key")!=expected_cases[str(row["case_id"])]:
            raise ValueError("Sensitivity case is attributed to the wrong parameter")
    baseline=[row for row in records if row.get("parameter_key")=="baseline"]
    if len(baseline)!=1 or baseline[0]["case_id"]!="baseline" or summary.get("baseline",{}).get("case_id")!="baseline":
        raise ValueError("Sensitivity needs one matching baseline in CSV and JSON")


def validate_sensitivity_stage(plan: dict[str,Any]) -> None:
    from etudecas.simulation.analysis_batch_common import sensitivity_run_context
    from etudecas.simulation.sensibility.run_supplier_parameter_sensitivity import (
        build_specs,case_id_for,detect_supplier_nodes,rank_suppliers,
    )
    output=Path(plan["output"]);nominal=output/"nominal";graph=nominal/"input_graph.json"
    selected=rank_suppliers(nominal,set(detect_supplier_nodes(read(graph))))[:plan["top_suppliers"]]
    levels={"stock":[.25,.5,.75,1.0],"capacity":[.5,.6,.75,.9,1.0],
            "lead_time":[1.0,1.25,1.5,2.0],"reliability":[.95,.97,.99,1.0],
            "external_capacity":[.25,.5,.75,1.0],"external_lead":[1.0,1.25,1.5,2.0]}
    specs=build_specs({"stock","capacity","lead_time","reliability","external","combined"},selected,levels,
        {"capacity":.75,"stock":.5,"lead_time":1.25,"reliability":.97,"upstream_capacity":.75,"upstream_lead":1.25})
    expected={"baseline":"baseline"}
    for spec in specs:
        for level in spec["levels"]:
            key=case_id_for(str(spec["parameter_key"]),float(level))
            if key in expected:raise ValueError("Sensitivity design has duplicate case IDs")
            expected[key]=str(spec["parameter_key"])
    runner,_=sensitivity_run_context(nominal/"run_manifest.json",ROOT/"etudecas/simulation/engine/run_first_simulation.py")
    source=output/"sensitivity/supplier_parameter"
    validate_sensitivity_completion(read(source/"supplier_parameter_sensitivity_summary.json"),
        read_csv(source/"supplier_parameter_sensitivity_cases.csv"),expected_cases=expected,
        expected_parameters=len(specs),expected_suppliers=selected,expected_input=graph,
        expected_runner=runner,days=plan["days"])


def publish_sensitivity(plan: dict[str, Any]) -> None:
    import shutil
    output = Path(plan["output"])
    source = output / "sensitivity/supplier_parameter"
    destination = output / "analyses"
    validate_sensitivity_stage(plan)
    destination.mkdir(parents=True, exist_ok=True)
    for filename in ("supplier_parameter_sensitivity_cases.csv", "supplier_parameter_sensitivity_summary.json", "supplier_parameter_threshold_summary.csv"):
        shutil.copyfile(source / filename, destination / filename)
    with (source / "supplier_parameter_sensitivity_cases.csv").open(encoding="utf-8-sig", newline="") as stream:
        records = list(csv.DictReader(stream))
    if any(str(row.get("status", "ok")).lower() not in {"ok", "success", "completed", "reused"} for row in records):
        raise ValueError("Sensitivity contains failed/noncompleted cases")
    for row in records:
        row.setdefault("parameter", row.get("parameter_key", row.get("group", "")))
        row.setdefault("level", str(row.get("value", "")))
    columns = list(dict.fromkeys(key for row in records for key in row))
    with (destination / "sensitivity_cases.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns); writer.writeheader(); writer.writerows(records)
    write(destination / "sensitivity_provenance.json", {"source": str(source), "cases": len(records),
          "source_sha256": sha(source / "supplier_parameter_sensitivity_cases.csv"), "normalized_without_new_simulation": True})


def local_criticality(plan: dict[str, Any]) -> None:
    from etudecas.risk.supplier_audit import DEFAULT_SUPPLIER_AUDIT_SOURCE, expand_supplier_audit_coverage, load_supplier_audits
    from etudecas.risk.supplier_criticality.local import build_supplier_local_criticality
    output = Path(plan["output"]); nominal = output / "nominal"; data = nominal / "data"
    raw = read(nominal / "input_graph.json")
    audits = expand_supplier_audit_coverage(raw.get("nodes", []), load_supplier_audits(DEFAULT_SUPPLIER_AUDIT_SOURCE))
    _, ranking, summary = build_supplier_local_criticality(raw, data / "production_supplier_shipments_daily.csv",
        data / "production_supplier_stocks_daily.csv", data / "production_supplier_capacity_daily.csv",
        data / "production_constraint_daily.csv", output / "analyses/sensitivity_cases.csv",
        output / "__not_available_structural_sensitivity__", supplier_audits=audits)
    columns = sorted({key for row in ranking for key in row})
    with (data / "supplier_local_criticality_ranking.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns); writer.writeheader(); writer.writerows(ranking)
    write(nominal / "summaries/supplier_local_criticality_summary.json", {"summary": summary, "ranking": ranking})


def map_command(plan: dict[str, Any], completed: set[str] | None = None) -> list[str]:
    from etudecas.regenerate import _map_command
    output = Path(plan["output"]); nominal = output / "nominal"; analyses = output / "analyses"
    criticality = output / "supplier_criticality"
    command = _map_command(nominal, nominal / "input_graph.json", Path(plan["map_output"]), current=True)
    values = {"--simulated-risk-output-dir": output / "risks/full",
        "--montecarlo-summary-json": output / "montecarlo/montecarlo_summary.json",
        "--sensitivity-cases-csv": analyses / "sensitivity_cases.csv",
        "--supplier-parameter-cases-csv": analyses / "supplier_parameter_sensitivity_cases.csv",
        "--supplier-parameter-summary-csv": analyses / "supplier_parameter_threshold_summary.csv",
        "--supplier-parameter-sensitivity-summary-json": analyses / "supplier_parameter_sensitivity_summary.json",
        "--supplier-local-criticality-csv": nominal / "data/supplier_local_criticality_ranking.csv",
        "--supplier-local-criticality-json": nominal / "summaries/supplier_local_criticality_summary.json",
        "--supplier-risk-kpi-summary-json": criticality / "summaries/supplier_risk_kpi_summary.json",
        "--supplier-risk-kpi-supplier-csv": criticality / "data/supplier_risk_kpi.csv",
        "--supplier-risk-kpi-pair-csv": criticality / "data/supplier_item_risk_kpi.csv",
        "--supplier-risk-kpi-panel-csv": criticality / "data/supplier_item_week_panel.csv",
        "--title": "Simulation complete - MRP, lots, risques et incertitude"}
    prerequisites={"--simulated-risk-output-dir":"risk_full", "--montecarlo-summary-json":"montecarlo",
                   "--supplier-local-criticality-csv":"local_criticality", "--supplier-local-criticality-json":"local_criticality"}
    for name,value in values.items():
        if name.startswith("--supplier-risk-kpi-"):prerequisites[name]="criticality"
        elif name.startswith("--supplier-parameter-") or name=="--sensitivity-cases-csv":prerequisites[name]="publish_sensitivity"
        required=prerequisites.get(name)
        if completed is not None and required and required not in completed:
            value=output/"__not_yet_calculated__"/name.lstrip("-")
        command=option(command,name,str(value))
    return command


def publish_progress_map(plan: dict[str, Any], state: dict[str, Any], stage_id: str) -> None:
    """Publish a new immutable snapshot; pending analyses stay explicitly absent."""
    import html
    output=Path(plan["output"]);nominal=output/"nominal"
    completed={key for key,value in state["stages"].items() if value["status"]=="completed"}
    if "nominal" not in completed:return
    if not (nominal/"run/artifact_index.json").exists():
        run_command(python_module("etudecas.run_etudecas_pipeline","export-run","--output-dir",str(nominal),
                                 "--input-graph",str(nominal/"input_graph.json")),output/"logs/progress_package.log")
    target=Path(plan["map_output"])
    target=target.with_name(target.stem+".progress_"+stage_id+target.suffix)
    if target.exists():raise FileExistsError("Progress snapshot already exists: "+str(target))
    target.parent.mkdir(parents=True,exist_ok=True)
    command=option(map_command(plan,completed),"--output",str(target))
    pending=[s["id"] for s in plan["stages"] if s["id"] not in completed]
    command=option(command,"--title","Campagne en cours - analyses restantes: "+", ".join(pending))
    run_command(command,output/"logs"/("progress_"+stage_id+".log"))
    document=target.read_text(encoding="utf-8")
    notice='<div id="campaignProgressNotice" style="position:fixed;bottom:0;left:0;right:0;z-index:100000;background:#fff3cd;color:#5c4400;padding:7px 12px;font:13px sans-serif">Campagne en cours. Analyses non encore calculées : '+html.escape(", ".join(pending))+'</div>'
    document=document.replace("</body>",notice+"</body>")
    target.write_text(document,encoding="utf-8",newline="\n")
    state.setdefault("progress_maps",[]).append({"stage":stage_id,"path":str(target),"sha256":sha(target),"pending_stages":pending})


def execute_action(stage: dict[str, Any], plan: dict[str, Any], log: Path) -> None:
    output = Path(plan["output"])
    action = stage["action"]
    if action == "command":
        run_command(stage["command"], log)
        if stage["id"] == "nominal":
            manifest=read(output / "nominal/run_manifest.json")
            if manifest.get("status") != "passed_execution" or manifest.get("returncode") != 0:
                raise ValueError("Nominal runtime did not produce a passed execution manifest")
            write(output / "nominal/complete_campaign_execution_manifest.json",manifest)
        elif stage["id"] == "montecarlo":
            summary=read(output/"montecarlo/montecarlo_summary.json")
            validate_montecarlo_completion(summary,read_csv(output/"montecarlo/montecarlo_samples.csv"),plan["montecarlo_runs"])
        elif stage["id"] == "sensitivity":validate_sensitivity_stage(plan)
    elif action == "prepare_risks": prepare_risks(plan)
    elif action == "risk_run": risk_run(plan, stage["risk_key"], log)
    elif action == "publish_sensitivity": publish_sensitivity(plan)
    elif action == "local_criticality": local_criticality(plan)
    elif action == "risk_registries":
        from etudecas.simulation.lot_trace.risk_impact_registry import build_risk_impact_registry_from_directory, write_risk_impact_registry
        index = {}
        for key in RISK_KEYS:
            registry = build_risk_impact_registry_from_directory(output / "risks" / key / "data")
            files = write_risk_impact_registry(registry, output / "risks" / key / "risk_registry")
            index[key] = {name: str(path) for name, path in files.items()}
        write(output / "risk_registry_index.json", index)
    elif action == "packages":
        for run in [output / "nominal", *(output / "risks" / key for key in RISK_KEYS)]:
            graph = run / "input_graph.json" if run.name == "nominal" else output / "risk_inputs" / (run.name + ".json")
            run_command(python_module("etudecas.run_etudecas_pipeline", "export-run", "--output-dir", str(run), "--input-graph", str(graph)), log)
    elif action == "map":
        target = Path(plan["map_output"])
        if target.exists(): raise FileExistsError(f"Refuse to overwrite map: {target}")
        target.parent.mkdir(parents=True, exist_ok=True)
        command = map_command(plan)
        write(output / "map_command.json", command)
        run_command(command, log)
    else: raise ValueError(action)


def execute(plan: dict[str, Any], *, resume: bool, stop_after: str = "", max_wall_minutes: float = 0,
            max_disk_gb: float = 80, min_free_disk_gb: float = 10, progress_maps: bool = False) -> dict[str, Any]:
    global _PROCESS_OBSERVER
    import shutil
    from etudecas.toolbox.cli import code_fingerprint
    output = campaign_path(plan["output"]); campaign_path(plan["map_output"])
    checkpoint = output / "campaign_state.json"
    signature = identity(plan)
    if checkpoint.exists():
        if not resume: raise FileExistsError("Campaign already exists; use --resume")
        state = read(checkpoint)
        if state["plan_sha256"] != signature: raise ValueError("Resume plan differs from declared campaign")
        if state["implementation_sha256"] != identity(code_fingerprint()):
            raise ValueError("Implementation changed since this campaign started; use a new campaign directory")
        if state.get("owner_pid") != os.getpid() and process_alive(state.get("owner_pid")):
            raise RuntimeError("Another campaign launcher is still active")
        for value in state["stages"].values():
            if process_alive(value.get("child_pid")):
                raise RuntimeError("A recorded stage subprocess is still active; refuse duplicate execution")
    else:
        if output.exists() and any(output.iterdir()): raise FileExistsError("Use a new output directory")
        output.mkdir(parents=True, exist_ok=True)
        state = {"schema": "etudecas.complete-current-campaign-state.v1", "plan_sha256": signature,
                 "implementation_sha256": identity(code_fingerprint()), "status": "declared",
                 "stages": {s["id"]: {"status": "declared"} for s in plan["stages"]}}
        write(output / "campaign_plan.json", plan); write(checkpoint, state)
    state["owner_pid"]=os.getpid()
    started = time.monotonic()
    for stage in plan["stages"]:
        record = state["stages"][stage["id"]]
        if record["status"] == "completed":
            if check_outputs(stage) != record["output_sha256"]:
                raise ValueError("Completed output differs from receipt: " + stage["id"])
            continue
        if record["status"] == "running":
            if stage["id"] in {"sensitivity","global_sensitivity","montecarlo"}:
                record["interrupted_resume_count"]=record.get("interrupted_resume_count",0)+1
                record["status"]="declared"  # native runners verify their own per-case checkpoints
            else:
                raise RuntimeError("Interrupted native stage needs inspection; partial outputs are never assumed complete: " + stage["id"])
        if record["status"] == "failed":
            raise RuntimeError("Failed stage requires inspection/new campaign; no automatic unsafe retry: " + stage["id"])
        if max_wall_minutes and (time.monotonic() - started) / 60 >= max_wall_minutes:
            state["status"] = "budget_stopped_between_stages"; write(checkpoint, state); return state
        if shutil.disk_usage(output).free / 2**30 < min_free_disk_gb:
            state["status"] = "disk_budget_stopped"; write(checkpoint, state); return state
        size = sum(path.stat().st_size for path in output.rglob("*") if path.is_file())
        if size / 2**30 > max_disk_gb:
            state["status"] = "storage_budget_stopped"; write(checkpoint, state); return state
        record.update(status="running", started_utc=datetime.now(timezone.utc).isoformat())
        state["status"] = "running"; state["current_stage"] = stage["id"]; write(checkpoint, state)
        def observe(pid: int | None) -> None:
            record["child_pid"]=pid
            write(checkpoint,state)
        _PROCESS_OBSERVER=observe
        print(json.dumps({"stage": stage["id"], "status": "running"}), flush=True)
        try:
            execute_action(stage, plan, output / "logs" / (stage["id"] + ".log"))
            if identity(code_fingerprint())!=state["implementation_sha256"]:
                raise ValueError("Implementation changed during the stage; no successful receipt is issued")
            record.update(status="completed", output_sha256=check_outputs(stage), finished_utc=datetime.now(timezone.utc).isoformat())
        except BaseException as exc:
            record.update(status="failed", error=repr(exc), finished_utc=datetime.now(timezone.utc).isoformat())
            state["status"] = "failed"; write(checkpoint, state); raise
        write(checkpoint, state)
        print(json.dumps({"stage": stage["id"], "status": "completed"}), flush=True)
        if progress_maps and stage["id"] in {"nominal","risk_full","publish_sensitivity","criticality","montecarlo"}:
            try:
                publish_progress_map(plan,state,stage["id"])
            except BaseException as exc:
                state["status"]="progress_map_failed";state["progress_map_error"]=repr(exc);write(checkpoint,state);raise
            write(checkpoint,state)
        if stop_after == stage["id"]:
            state["status"] = "stopped_after_requested_stage"; write(checkpoint, state); return state
    state["status"] = "execution_completed_requires_independent_qualification"
    state["finished_utc"] = datetime.now(timezone.utc).isoformat(); write(checkpoint, state)
    return state


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--map-output", type=Path, default=DEFAULT_MAP)
    parser.add_argument("--days", type=int, default=1825)
    parser.add_argument("--mc-runs", type=int, default=200)
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--top-suppliers", type=int, default=8)
    parser.add_argument("--uncertainty-profile", choices=["workshop", "risk_probe", "stress_probe", "breakpoint_probe", "portfolio_probe", "legacy"], default="workshop")
    parser.add_argument("--global-sensitivity", action="store_true", help="Additional legacy OAT batch; supplier-parameter batch already includes global cases")
    parser.add_argument("--plan-only", action="store_true", help="Print commands/design only; do not create directories or execute")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--progress-maps", action="store_true", help="Publish clearly labelled map snapshots after major completed stages; never import uncalculated analyses")
    parser.add_argument("--stop-after", default="")
    parser.add_argument("--max-wall-minutes", type=float, default=0, help="Stop between stages; zero means no wall-time stage budget")
    parser.add_argument("--max-disk-gb", type=float, default=80)
    parser.add_argument("--min-free-disk-gb", type=float, default=10)
    args = parser.parse_args(argv)
    plan = build_plan(campaign_path(args.output_dir), campaign_path(args.map_output), days=args.days,
        mc_runs=args.mc_runs, workers=args.workers, seed=args.seed, suppliers=args.top_suppliers,
        uncertainty_profile=args.uncertainty_profile, global_sensitivity=args.global_sensitivity)
    if args.stop_after and args.stop_after not in {stage["id"] for stage in plan["stages"]}:
        parser.error("--stop-after must be one of: " + ", ".join(stage["id"] for stage in plan["stages"]))
    if args.plan_only:
        print(json.dumps(plan, ensure_ascii=False, indent=2)); return 0
    state = execute(plan, resume=args.resume, stop_after=args.stop_after, max_wall_minutes=args.max_wall_minutes,
                    max_disk_gb=args.max_disk_gb, min_free_disk_gb=args.min_free_disk_gb,progress_maps=args.progress_maps)
    print(json.dumps({"status": state["status"], "checkpoint": str(Path(plan["output"]) / "campaign_state.json")}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
