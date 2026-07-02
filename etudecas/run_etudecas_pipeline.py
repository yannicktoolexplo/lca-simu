#!/usr/bin/env python3
"""Unified entrypoint for the active etudecas pipeline.

The primary artifact is the supply-chain knowledge-graph JSON. The active flow is:

1. enrich the graph from case-study XLSX data
2. geocode nodes
3. prepare a simulation-ready reference graph
4. calibrate it to the real-demand reference
5. inject MRP snapshot + lot-policy data
6. run the reference simulation and regenerate the map

Secondary analysis and sensitivity scripts remain available, but this file is the
single operational entrypoint for rebuilding the reference graph and its simulations.
"""

from __future__ import annotations

import argparse
import csv
import importlib.util
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parent
REPO_ROOT = ROOT.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from etudecas.simulation.initial_state_policy import living_supply_initial_state_args  # noqa: E402

SOURCE_DATA_DIR = ROOT / "data" / "source"
DATA_REPORTS_DIR = ROOT / "data" / "reports"
GEOCODED_DATA_DIR = ROOT / "data" / "geocoded"
BASE_GRAPH_JSON = SOURCE_DATA_DIR / "supply_graph_poc.json"
GEOCODED_GRAPH_JSON = GEOCODED_DATA_DIR / "supply_graph_poc_geocoded.json"
PREP_GRAPH_JSON = ROOT / "simulation_prep" / "result" / "reference_baseline" / "supply_graph_reference_baseline_simulation_ready.json"
REAL_DEMAND_GRAPH_JSON = (
    ROOT / "simulation_prep" / "result" / "reference_baseline" / "supply_graph_reference_baseline_real_demand_target_calibrated.json"
)
MRP_LOT_GRAPH_JSON = (
    ROOT / "simulation_prep" / "result" / "reference_baseline" / "supply_graph_reference_baseline_real_demand_target_calibrated_mrp_lot_policy.json"
)
FINAL_GRAPH_1Y_JSON = (
    ROOT
    / "simulation_prep"
    / "result"
    / "reference_baseline"
    / "supply_graph_reference_baseline_real_demand_target_calibrated_mrp_lot_policy_recalibrated.json"
)
FINAL_GRAPH_5Y_JSON = (
    ROOT
    / "simulation_prep"
    / "result"
    / "reference_baseline"
    / "supply_graph_reference_baseline_real_demand_target_calibrated_mrp_lot_policy_recalibrated_5y.json"
)
FINAL_OUTPUT_1Y_DIR = ROOT / "simulation" / "result" / "reference_baseline_real_demand_target_calibrated_mrp_lot_policy_recalibrated"
FINAL_OUTPUT_5Y_DIR = ROOT / "simulation" / "result" / "reference_baseline_real_demand_target_calibrated_mrp_lot_policy_recalibrated_5y"
ACTIVE_MRP_PHYSICAL_GRAPH_JSON = (
    ROOT
    / "simulation_prep"
    / "result"
    / "reference_baseline"
    / "_mrp_bom_tests"
    / "bom_weekly_mps_lotified_no_static_fallback_physical_floor.json"
)
ACTIVE_MRP_PHYSICAL_OUTPUT_DIR = (
    ROOT
    / "simulation"
    / "result"
    / "mrp_bom_test_weekly_mps_lotified_no_fallback_physical_floor_explicit_input_targets_test"
)
ACTIVE_MRP_PHYSICAL_RERUN_ROOT = ROOT / "simulation" / "result" / "_reruns"
SIMULATION_ENGINE_SCRIPT = ROOT / "simulation" / "engine" / "run_first_simulation.py"
SUPPLIER_CRITICALITY_SCRIPT = ROOT / "risk" / "supplier_criticality" / "build_supplier_criticality.py"
SUPPLIER_CRITICALITY_OUTPUT_DIR = ROOT / "risk" / "supplier_criticality" / "result"
DEFAULT_CASE_CONFIG_JSON = ROOT / "config" / "cases" / "data_poc.json"
DEFAULT_ENRICHMENT_EXCEL = ROOT / "config" / "cases" / "data_poc_enrichment_input.xlsx"
ACTIVE_MRP_PHYSICAL_BASE_STOCK_FLOOR_PAIRS = [
    ("M-1430", "item:038005", 1.0),
    ("M-1430", "item:042342", 1.0),
    ("M-1430", "item:333362", 1.0),
    ("M-1430", "item:344135", 1.0),
    ("M-1430", "item:708073", 1.0),
    ("M-1430", "item:730384", 1.0),
    ("M-1430", "item:734545", 1.0),
    ("M-1430", "item:773474", 1.0),
    ("M-1810", "item:001757", 1.0),
    ("M-1810", "item:001848", 1.0),
    ("M-1810", "item:001893", 1.0),
    ("M-1810", "item:002612", 1.0),
    ("M-1810", "item:007923", 1.0),
    ("M-1810", "item:016332", 1.0),
    ("M-1810", "item:029313", 1.0),
    ("M-1810", "item:039668", 1.0),
    ("M-1810", "item:049371", 1.0),
    ("M-1810", "item:055703", 1.0),
    ("M-1810", "item:099439", 1.0),
    ("M-1810", "item:338928", 1.0),
    ("M-1810", "item:338929", 1.0),
    ("M-1810", "item:426331", 1.0),
    ("M-1810", "item:693055", 1.0),
]
ACTIVE_MRP_PHYSICAL_INITIAL_STATE_ARGS = living_supply_initial_state_args()
CORE_RUNTIME_MODULES = ["numpy", "pandas", "openpyxl"]
PIPELINE_SUCCESS_MARKER = "DATA_CHUNKED_GZIP_BASE64"
DEFAULT_MAX_STANDALONE_MAP_MB = 40.0


def ok_line(message: str) -> None:
    print(f"[OK] {message}", flush=True)


def info_line(message: str) -> None:
    print(f"[INFO] {message}", flush=True)


def warn_line(message: str) -> None:
    print(f"[WARN] {message}", flush=True)


def repo_rel(path: Path) -> str:
    try:
        resolved = path.resolve(strict=False)
        root = REPO_ROOT.resolve(strict=False)
        return str(resolved.relative_to(root)).replace("\\", "/")
    except ValueError:
        return str(path)


def run_python(script: Path, *args: str) -> None:
    cmd = [sys.executable, str(script), *args]
    subprocess.run(cmd, check=True, cwd=REPO_ROOT)


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def resolve_repo_path(path: Path) -> Path:
    return path if path.is_absolute() else REPO_ROOT / path


def data_manifest_source_files() -> list[Path]:
    manifest_path = ROOT / "data" / "MANIFEST.json"
    if not manifest_path.exists():
        return [
            SOURCE_DATA_DIR / name
            for name in [
                "021081.xlsx",
                "268191.xlsx",
                "268967.xlsx",
                "Data_poc.xlsx",
                "demand_PF.xlsx",
                "Extract_En_cours.xlsx",
                "Fournisseur.xlsx",
                "Stocks_MRP.xlsx",
                "supply_graph_poc.json",
            ]
        ]
    manifest = load_json(manifest_path)
    files = manifest.get("canonical_source_files") or []
    return [SOURCE_DATA_DIR / str(name) for name in files]


def missing_runtime_modules() -> list[str]:
    return [name for name in CORE_RUNTIME_MODULES if importlib.util.find_spec(name) is None]


def preflight_checks(*, require_active_graph: bool = True) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []

    def add(name: str, ok: bool, detail: str = "") -> None:
        checks.append({"name": name, "ok": bool(ok), "detail": detail})

    add("repo_root", REPO_ROOT.exists(), repo_rel(REPO_ROOT))
    for path in data_manifest_source_files():
        add(f"source:{path.name}", path.exists(), repo_rel(path))
    for script in [
        ROOT / "knowledge_graph" / "update_supply_graph_from_case_data.py",
        ROOT / "geocoding" / "geocode_nodes_offline.py",
        ROOT / "simulation_prep" / "prepare_simulation_graph.py",
        SIMULATION_ENGINE_SCRIPT,
        ROOT / "visualization" / "maps" / "build_supplychain_worldmap.py",
    ]:
        add(f"script:{script.name}", script.exists(), repo_rel(script))
    if require_active_graph:
        add("active_lotified_graph", ACTIVE_MRP_PHYSICAL_GRAPH_JSON.exists(), repo_rel(ACTIVE_MRP_PHYSICAL_GRAPH_JSON))
    missing_modules = missing_runtime_modules()
    add(
        "python_runtime_modules",
        not missing_modules,
        "missing=" + ", ".join(missing_modules) if missing_modules else "ok",
    )
    return checks


def assert_preflight_ok(checks: list[dict[str, Any]]) -> None:
    failed = [check for check in checks if not check.get("ok")]
    if not failed:
        return
    lines = ["Preflight failed. Missing or invalid prerequisites:"]
    lines.extend(f"- {row['name']}: {row.get('detail', '')}" for row in failed)
    if any(str(row.get("name")) == "python_runtime_modules" for row in failed):
        lines.append("Install dependencies with: python -m pip install -r requirements.txt")
    raise RuntimeError("\n".join(lines))


def print_preflight(checks: list[dict[str, Any]]) -> None:
    for row in checks:
        status = "OK" if row.get("ok") else "FAIL"
        print(f"[{status}] {row['name']} - {row.get('detail', '')}", flush=True)


def find_generated_map(output_dir: Path) -> Path | None:
    maps_dir = output_dir / "maps"
    if not maps_dir.exists():
        return None
    maps = sorted(maps_dir.glob("*.html"), key=lambda p: p.stat().st_mtime, reverse=True)
    return maps[0] if maps else None


def count_csv_rows(path: Path) -> int:
    if not path.exists():
        return 0
    with path.open("r", encoding="utf-8", newline="") as f:
        return max(0, sum(1 for _ in csv.reader(f)) - 1)


def read_summary_kpis(summary_path: Path) -> dict[str, Any]:
    if not summary_path.exists():
        return {}
    summary = load_json(summary_path)
    kpis = summary.get("kpis")
    return kpis if isinstance(kpis, dict) else {}


def validate_active_run_outputs(
    output_dir: Path,
    *,
    scenario_id: str,
    days: int,
    output_profile: str,
    max_map_mb: float,
) -> list[dict[str, Any]]:
    summary_path = output_dir / "summaries" / "first_simulation_summary.json"
    report_path = output_dir / "reports" / "first_simulation_report.md"
    lot_events_path = output_dir / "data" / "production_lot_events.csv"
    lot_genealogy_path = output_dir / "data" / "production_lot_genealogy.csv"
    lot_audit_path = output_dir / "reports" / "lot_path_audit.md"
    daily_path = output_dir / "data" / "first_simulation_daily.csv"
    supplier_criticality_summary_path = output_dir / "supplier_criticality" / "summaries" / "supplier_risk_kpi_summary.json"
    supplier_criticality_csv_path = output_dir / "supplier_criticality" / "data" / "supplier_risk_kpi.csv"
    map_path = find_generated_map(output_dir)

    validations: list[dict[str, Any]] = []

    def add(name: str, ok: bool, detail: str = "") -> None:
        validations.append({"name": name, "ok": bool(ok), "detail": detail})

    add("summary_json", summary_path.exists(), repo_rel(summary_path))
    add("simulation_report", report_path.exists(), repo_rel(report_path))
    daily_rows = count_csv_rows(daily_path)
    lot_event_rows = count_csv_rows(lot_events_path)
    lot_genealogy_rows = count_csv_rows(lot_genealogy_path)
    add("daily_kpi_csv", daily_path.exists(), repo_rel(daily_path))
    add("daily_kpi_row_count", daily_rows == days, f"{daily_rows} rows, expected {days}")
    add("lot_events_csv", lot_events_path.exists() and lot_event_rows > 0, f"{lot_event_rows} rows")
    add("lot_genealogy_csv", lot_genealogy_path.exists() and lot_genealogy_rows > 0, f"{lot_genealogy_rows} rows")
    add("lot_path_audit", lot_audit_path.exists(), repo_rel(lot_audit_path))
    add(
        "supplier_criticality_summary",
        supplier_criticality_summary_path.exists(),
        repo_rel(supplier_criticality_summary_path),
    )
    add(
        "supplier_criticality_csv",
        supplier_criticality_csv_path.exists() and count_csv_rows(supplier_criticality_csv_path) > 0,
        f"{count_csv_rows(supplier_criticality_csv_path)} rows",
    )
    add("map_html", map_path is not None and map_path.exists(), repo_rel(map_path) if map_path else "missing")
    if map_path and map_path.exists():
        map_size_mb = map_path.stat().st_size / (1024 * 1024)
        add("map_size", map_size_mb <= max_map_mb, f"{map_size_mb:.2f} MB <= {max_map_mb:.2f} MB")
        head = map_path.read_text(encoding="utf-8", errors="ignore")[:600_000]
        add("map_payload_compressed", PIPELINE_SUCCESS_MARKER in head, PIPELINE_SUCCESS_MARKER)
    summary = load_json(summary_path) if summary_path.exists() else {}
    add("summary_scenario_id", summary.get("scenario_id") == scenario_id, f"{summary.get('scenario_id')} == {scenario_id}")
    add("summary_sim_days", int(summary.get("sim_days") or -1) == days, f"{summary.get('sim_days')} == {days}")
    add("summary_timeline_days", int(summary.get("timeline_days") or -1) == days, f"{summary.get('timeline_days')} == {days}")
    policy = summary.get("policy") if isinstance(summary.get("policy"), dict) else {}
    add("summary_output_profile", policy.get("output_profile") == output_profile, f"{policy.get('output_profile')} == {output_profile}")
    add("summary_lot_trace_enabled", bool(policy.get("lot_trace_enabled")), str(policy.get("lot_trace_enabled")))
    economic = summary.get("economic_consistency") if isinstance(summary.get("economic_consistency"), dict) else {}
    if economic:
        add("economic_consistency", str(economic.get("status") or "").lower() == "ok", str(economic.get("status")))
    kpis = summary.get("kpis") if isinstance(summary.get("kpis"), dict) else {}
    if kpis:
        fill_rate = kpis.get("fill_rate")
        ending_backlog = kpis.get("ending_backlog")
        total_cost = kpis.get("total_cost")
        add("kpi_fill_rate_present", fill_rate is not None, f"fill_rate={fill_rate}")
        add("kpi_total_cost_present", total_cost is not None, f"total_cost={total_cost}")
        add("kpi_ending_backlog_present", ending_backlog is not None, f"ending_backlog={ending_backlog}")
    return validations


def assert_validations_ok(validations: list[dict[str, Any]]) -> None:
    failed = [row for row in validations if not row.get("ok")]
    if not failed:
        return
    lines = ["Pipeline output validation failed:"]
    lines.extend(f"- {row['name']}: {row.get('detail', '')}" for row in failed)
    raise RuntimeError("\n".join(lines))


def write_pipeline_report(
    *,
    output_dir: Path,
    command_name: str,
    preflight: list[dict[str, Any]],
    validations: list[dict[str, Any]],
    started_at_utc: str,
    finished_at_utc: str,
) -> None:
    map_path = find_generated_map(output_dir)
    kpis = read_summary_kpis(output_dir / "summaries" / "first_simulation_summary.json")
    report = {
        "schema_version": "etudecas.pipeline_report.v1",
        "command": command_name,
        "started_at_utc": started_at_utc,
        "finished_at_utc": finished_at_utc,
        "output_dir": repo_rel(output_dir),
        "map_html": repo_rel(map_path) if map_path else None,
        "map_size_mb": round(map_path.stat().st_size / (1024 * 1024), 3) if map_path and map_path.exists() else None,
        "kpis": {
            "fill_rate": kpis.get("fill_rate"),
            "ending_backlog": kpis.get("ending_backlog"),
            "total_cost": kpis.get("total_cost"),
            "total_explicit_initialization_stock_qty": kpis.get("total_explicit_initialization_stock_qty"),
            "total_explicit_initialization_pipeline_qty": kpis.get("total_explicit_initialization_pipeline_qty"),
        },
        "preflight": preflight,
        "validations": validations,
    }
    reports_dir = output_dir / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    json_path = reports_dir / "pipeline_report.json"
    md_path = reports_dir / "pipeline_report.md"
    write_json(json_path, report)
    md_lines = [
        "# Etudecas Pipeline Report",
        "",
        f"- Command: `{command_name}`",
        f"- Output: `{repo_rel(output_dir)}`",
        f"- Map: `{repo_rel(map_path) if map_path else 'missing'}`",
        f"- Map size MB: `{report['map_size_mb']}`",
        f"- Fill rate: `{report['kpis']['fill_rate']}`",
        f"- Ending backlog: `{report['kpis']['ending_backlog']}`",
        f"- Total cost: `{report['kpis']['total_cost']}`",
        "",
        "## Validations",
        "",
    ]
    for row in validations:
        status = "OK" if row.get("ok") else "FAIL"
        md_lines.append(f"- {status} `{row['name']}`: {row.get('detail', '')}")
    md_path.write_text("\n".join(md_lines) + "\n", encoding="utf-8")
    ok_line(f"Pipeline report: {json_path.resolve()}")


def open_file_in_default_app(path: Path) -> None:
    if os.name == "nt":
        os.startfile(str(path.resolve()))  # type: ignore[attr-defined]
    elif sys.platform == "darwin":
        subprocess.run(["open", str(path.resolve())], check=False)
    else:
        subprocess.run(["xdg-open", str(path.resolve())], check=False)


def timestamped_active_mrp_physical_output_dir() -> Path:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return ACTIVE_MRP_PHYSICAL_RERUN_ROOT / f"active_mrp_physical_{stamp}"


def validate_simulation_output_dir(output_dir: Path, *, overwrite: bool) -> Path:
    resolved = resolve_repo_path(output_dir).resolve(strict=False)
    result_root = (ROOT / "simulation" / "result").resolve(strict=False)
    try:
        resolved.relative_to(result_root)
    except ValueError as exc:
        raise ValueError(f"Refusing output outside simulation/result: {resolved}") from exc
    if resolved.exists() and any(resolved.iterdir()) and not overwrite:
        raise FileExistsError(
            f"Output directory already exists and is not empty: {repo_rel(resolved)}. "
            "Use --output-dir with a new path, or pass --overwrite explicitly."
        )
    return resolved


def patch_repeated_horizon_graph(source_graph: Path, output_graph: Path, *, scenario_id: str, days: int) -> None:
    data = load_json(source_graph)
    scenarios = data.get("scenarios") or []
    scenario = next((row for row in scenarios if str(row.get("id")) == scenario_id), None)
    if not isinstance(scenario, dict):
        if not scenarios:
            raise ValueError(f"No scenario found in {source_graph}")
        scenario = scenarios[0]
    horizon = scenario.get("horizon")
    if not isinstance(horizon, dict):
        horizon = {}
    horizon["steps_to_run"] = int(days)
    horizon["repeat_period_days"] = 365
    scenario["horizon"] = horizon

    meta = data.get("meta")
    if not isinstance(meta, dict):
        meta = {}
    meta["generated_by_pipeline"] = {
        "script": repo_rel(Path(__file__)),
        "source_graph": repo_rel(source_graph),
        "horizon_days": int(days),
        "repeat_period_days": 365,
    }
    data["meta"] = meta
    write_json(output_graph, data)


def forward_optional_flags(*, skip_map: bool, skip_plots: bool) -> list[str]:
    args: list[str] = []
    if skip_map:
        args.append("--skip-map")
    if skip_plots:
        args.append("--skip-plots")
    return args


def build_knowledge_graph() -> None:
    run_python(
        ROOT / "knowledge_graph" / "update_supply_graph_from_case_data.py",
        "--input-json",
        repo_rel(BASE_GRAPH_JSON),
        "--data-dir",
        repo_rel(SOURCE_DATA_DIR),
        "--output-json",
        repo_rel(BASE_GRAPH_JSON),
        "--report-json",
        repo_rel(DATA_REPORTS_DIR / "case_data_update_report.json"),
        "--report-md",
        repo_rel(DATA_REPORTS_DIR / "case_data_update_report.md"),
    )
    run_python(
        ROOT / "geocoding" / "geocode_nodes_offline.py",
        "--input-json",
        repo_rel(BASE_GRAPH_JSON),
        "--output-dir",
        repo_rel(GEOCODED_DATA_DIR),
        "--output-name",
        GEOCODED_GRAPH_JSON.name,
    )


def run_excel_enrichment(
    *,
    input_json: Path,
    excel: Path,
    output_json: Path,
    report_json: Path,
    case_config_json: Path | None,
    create_template: bool,
    apply: bool,
) -> None:
    from etudecas.knowledge_graph.enrichers import enrich_graph_from_excel
    from etudecas.knowledge_graph.excel_template import write_excel_template
    from etudecas.knowledge_graph.io import load_graph, save_graph

    if not create_template and not apply:
        raise ValueError("Pass create_template and/or apply for Excel enrichment.")
    graph = load_graph(input_json)
    if case_config_json:
        config = load_json(case_config_json)
        if not isinstance(config, dict):
            raise ValueError(f"Case config must be a JSON object: {case_config_json}")
        graph["case_config"] = config
    if create_template:
        write_excel_template(excel, graph)
        print(f"[OK] Excel template written: {excel.resolve()}")
    if apply:
        enriched, report = enrich_graph_from_excel(graph, excel)
        save_graph(output_json, enriched)
        report_json.parent.mkdir(parents=True, exist_ok=True)
        report_json.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"[OK] Enriched graph written: {output_json.resolve()}")
        print(f"[OK] Report written: {report_json.resolve()}")


def prepare_reference_graph(*, simulation_days: int) -> None:
    run_python(
        ROOT / "simulation_prep" / "prepare_simulation_graph.py",
        "--input",
        repo_rel(GEOCODED_GRAPH_JSON),
        "--output-graph",
        repo_rel(PREP_GRAPH_JSON),
        "--output-report-json",
        "etudecas/simulation_prep/result/reference_baseline/simulation_prep_report.json",
        "--output-report-md",
        "etudecas/simulation_prep/result/reference_baseline/simulation_prep_report.md",
        "--simulation-days",
        str(simulation_days),
    )


def build_reference_baseline(*, scenario_id: str, days: int, skip_map: bool, skip_plots: bool) -> None:
    run_python(
        ROOT / "simulation" / "baselines" / "rebuild_real_demand_target_baseline.py",
        "--source",
        repo_rel(PREP_GRAPH_JSON),
        "--output-graph",
        repo_rel(REAL_DEMAND_GRAPH_JSON),
        "--named-output-graph",
        repo_rel(REAL_DEMAND_GRAPH_JSON),
        "--scenario-id",
        scenario_id,
        "--days",
        str(days),
        "--skip-simulation",
    )
    run_python(
        ROOT / "simulation_prep" / "inject_mrp_seed_data_v2.py",
        "--input-graph",
        repo_rel(REAL_DEMAND_GRAPH_JSON),
        "--output-graph",
        repo_rel(MRP_LOT_GRAPH_JSON),
        "--output-report-json",
        "etudecas/simulation_prep/result/reference_baseline/mrp_lot_policy_report.json",
        "--output-report-md",
        "etudecas/simulation_prep/result/reference_baseline/mrp_lot_policy_report.md",
        "--include-mrp-lot-policies",
    )
    run_python(
        ROOT / "simulation" / "baselines" / "rebuild_mrp_lot_policy_baseline.py",
        "--source",
        repo_rel(MRP_LOT_GRAPH_JSON),
        "--output-graph",
        repo_rel(FINAL_GRAPH_1Y_JSON),
        "--output-dir",
        repo_rel(FINAL_OUTPUT_1Y_DIR),
        "--scenario-id",
        scenario_id,
        "--days",
        str(days),
        *forward_optional_flags(skip_map=skip_map, skip_plots=skip_plots),
    )


def run_5y_reference(*, scenario_id: str, days: int, skip_map: bool, skip_plots: bool) -> None:
    patch_repeated_horizon_graph(FINAL_GRAPH_1Y_JSON, FINAL_GRAPH_5Y_JSON, scenario_id=scenario_id, days=days)
    run_python(
        SIMULATION_ENGINE_SCRIPT,
        "--input",
        repo_rel(FINAL_GRAPH_5Y_JSON),
        "--output-dir",
        repo_rel(FINAL_OUTPUT_5Y_DIR),
        "--scenario-id",
        scenario_id,
        "--days",
        str(days),
        *forward_optional_flags(skip_map=skip_map, skip_plots=skip_plots),
    )


def run_direct_simulation(*, input_graph: Path, output_dir: Path, scenario_id: str, days: int, skip_map: bool, skip_plots: bool) -> None:
    run_python(
        SIMULATION_ENGINE_SCRIPT,
        "--input",
        repo_rel(input_graph),
        "--output-dir",
        repo_rel(output_dir),
        "--scenario-id",
        scenario_id,
        "--days",
        str(days),
        *forward_optional_flags(skip_map=skip_map, skip_plots=skip_plots),
    )


def build_supplier_criticality(*, sim_result_dir: Path | None, output_dir: Path) -> None:
    args = [
        "--output-dir",
        repo_rel(output_dir),
    ]
    if sim_result_dir is not None:
        args.extend(["--sim-result-dir", repo_rel(sim_result_dir)])
    run_python(SUPPLIER_CRITICALITY_SCRIPT, *args)


def build_map_for_simulation_result(
    *,
    input_graph: Path,
    output_dir: Path,
    supplier_criticality_dir: Path,
    title: str = "Supply Graph POC - Geocoded Map",
) -> Path:
    data_dir = output_dir / "data"
    reports_dir = output_dir / "reports"
    summaries_dir = output_dir / "summaries"
    plots_dir = output_dir / "plots"
    maps_dir = output_dir / "maps"
    maps_dir.mkdir(parents=True, exist_ok=True)
    map_output_path = maps_dir / f"supply_graph_{output_dir.name}.html"
    map_script = ROOT / "visualization" / "maps" / "build_supplychain_worldmap.py"
    criticality_data = supplier_criticality_dir / "data"
    criticality_summaries = supplier_criticality_dir / "summaries"
    map_cmd = [
        sys.executable,
        repo_rel(map_script),
        "--input",
        repo_rel(input_graph),
        "--output",
        repo_rel(map_output_path),
        "--title",
        title,
        "--sim-input-stocks-csv",
        repo_rel(data_dir / "production_input_stocks_daily.csv"),
        "--sim-output-products-csv",
        repo_rel(data_dir / "production_output_products_daily.csv"),
        "--demand-service-csv",
        repo_rel(data_dir / "production_demand_service_daily.csv"),
        "--sim-input-stocks-png-dir",
        repo_rel(plots_dir),
        "--sim-output-products-png-dir",
        repo_rel(plots_dir),
        "--supplier-shipments-csv",
        repo_rel(data_dir / "production_supplier_shipments_daily.csv"),
        "--supplier-stocks-csv",
        repo_rel(data_dir / "production_supplier_stocks_daily.csv"),
        "--supplier-stock-flows-csv",
        repo_rel(data_dir / "production_supplier_stock_flows_daily.csv"),
        "--supplier-capacity-csv",
        repo_rel(data_dir / "production_supplier_capacity_daily.csv"),
        "--supplier-nominal-parameters-csv",
        repo_rel(data_dir / "supplier_nominal_parameters.csv"),
        "--factory-nominal-capacities-csv",
        repo_rel(data_dir / "production_capacity_nominal_parameters.csv"),
        "--input-arrivals-csv",
        repo_rel(data_dir / "production_input_replenishment_arrivals_daily.csv"),
        "--dc-stocks-csv",
        repo_rel(data_dir / "production_dc_stocks_daily.csv"),
        "--production-constraint-csv",
        repo_rel(data_dir / "production_constraint_daily.csv"),
        "--safety-reference-csv",
        repo_rel(reports_dir / "mrp_safety_stock_reference.csv"),
        "--daily-kpi-csv",
        repo_rel(data_dir / "first_simulation_daily.csv"),
        "--supplier-local-criticality-csv",
        repo_rel(data_dir / "supplier_local_criticality_ranking.csv"),
        "--supplier-local-criticality-json",
        repo_rel(summaries_dir / "supplier_local_criticality_summary.json"),
        "--supplier-risk-kpi-summary-json",
        repo_rel(criticality_summaries / "supplier_risk_kpi_summary.json"),
        "--supplier-risk-kpi-supplier-csv",
        repo_rel(criticality_data / "supplier_risk_kpi.csv"),
        "--supplier-risk-kpi-pair-csv",
        repo_rel(criticality_data / "supplier_item_risk_kpi.csv"),
        "--supplier-risk-kpi-panel-csv",
        repo_rel(criticality_data / "supplier_item_week_panel.csv"),
        "--chunked-embedded-payload",
    ]
    run_python(map_script, *map_cmd[2:])
    return map_output_path


def run_active_mrp_physical(
    *,
    output_dir: Path | None,
    scenario_id: str,
    days: int,
    output_profile: str,
    overwrite: bool,
    dry_run: bool,
    skip_map: bool,
    skip_plots: bool,
) -> Path:
    input_graph = ACTIVE_MRP_PHYSICAL_GRAPH_JSON
    if not input_graph.exists():
        raise FileNotFoundError(f"Active MRP physical graph not found: {repo_rel(input_graph)}")
    target_output_dir = validate_simulation_output_dir(
        output_dir or timestamped_active_mrp_physical_output_dir(),
        overwrite=overwrite or dry_run,
    )
    simulator_args = [
        "--input",
        repo_rel(input_graph),
        "--output-dir",
        repo_rel(target_output_dir),
        "--scenario-id",
        scenario_id,
        "--days",
        str(days),
        "--output-profile",
        output_profile,
        "--mrp-base-stock-floor-factor",
        "0",
        *ACTIVE_MRP_PHYSICAL_INITIAL_STATE_ARGS,
    ]
    for node_id, item_id, factor in ACTIVE_MRP_PHYSICAL_BASE_STOCK_FLOOR_PAIRS:
        simulator_args.extend(
            [
                "--mrp-base-stock-floor-factor-pair",
                f"{node_id},{item_id},{factor:g}",
            ]
        )
    if skip_map:
        simulator_args.append("--skip-map")
    if skip_plots:
        simulator_args.append("--skip-plots")

    pipeline_cmd = [
        sys.executable,
        repo_rel(Path(__file__)),
        "active-mrp-physical",
        "--output-dir",
        repo_rel(target_output_dir),
        "--scenario-id",
        scenario_id,
        "--days",
        str(days),
        "--output-profile",
        output_profile,
    ]
    if overwrite:
        pipeline_cmd.append("--overwrite")
    if dry_run:
        pipeline_cmd.append("--dry-run")
    if skip_map:
        pipeline_cmd.append("--skip-map")
    if not skip_plots:
        pipeline_cmd.append("--with-plots")

    if dry_run:
        print("[DRY-RUN] Active MRP physical baseline rebuild")
        print(f"[DRY-RUN] input_graph={repo_rel(input_graph)}")
        print(f"[DRY-RUN] output_dir={repo_rel(target_output_dir)}")
        print("[DRY-RUN] simulator command:")
        print(" ".join([sys.executable, repo_rel(SIMULATION_ENGINE_SCRIPT), *simulator_args]))
        return target_output_dir

    run_python(SIMULATION_ENGINE_SCRIPT, *simulator_args)
    manifest = {
        "baseline": "active_mrp_physical",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "input_graph": repo_rel(input_graph),
        "output_dir": repo_rel(target_output_dir),
        "scenario_id": scenario_id,
        "days": days,
        "output_profile": output_profile,
        "overwrite": overwrite,
        "skip_map": skip_map,
        "skip_plots": skip_plots,
        "pipeline_command": pipeline_cmd,
        "simulator_command": [
            sys.executable,
            repo_rel(SIMULATION_ENGINE_SCRIPT),
            *simulator_args,
        ],
        "initial_state_policy": {
            "reason": "run starts from observed ERP/MRP J0 stocks and firm open orders, without synthetic startup cover",
            "args": ACTIVE_MRP_PHYSICAL_INITIAL_STATE_ARGS,
        },
    }
    write_json(target_output_dir / "run_manifest.json", manifest)
    print(f"[OK] Active MRP physical run manifest: {(target_output_dir / 'run_manifest.json').resolve()}")
    return target_output_dir


def run_operational_rebuild(
    *,
    output_dir: Path | None,
    scenario_id: str,
    days: int,
    output_profile: str,
    overwrite: bool,
    dry_run: bool,
    skip_preflight: bool,
    skip_validation: bool,
    with_plots: bool,
    open_map: bool,
    max_map_mb: float,
) -> Path:
    started_at = datetime.now(timezone.utc).isoformat()
    preflight: list[dict[str, Any]] = []
    if not skip_preflight:
        info_line("Preflight checks")
        preflight = preflight_checks(require_active_graph=True)
        print_preflight(preflight)
        assert_preflight_ok(preflight)

    target_output_dir = run_active_mrp_physical(
        output_dir=output_dir,
        scenario_id=scenario_id,
        days=days,
        output_profile=output_profile,
        overwrite=overwrite,
        dry_run=dry_run,
        skip_map=True,
        skip_plots=not with_plots,
    )
    if dry_run:
        info_line("Dry-run stops before supplier criticality rebuild, final map build and validations.")
        return target_output_dir

    supplier_criticality_dir = target_output_dir / "supplier_criticality"
    info_line("Rebuilding supplier criticality for the current run")
    build_supplier_criticality(sim_result_dir=target_output_dir, output_dir=supplier_criticality_dir)

    info_line("Building final standalone map with current-run supplier criticality")
    build_map_for_simulation_result(
        input_graph=ACTIVE_MRP_PHYSICAL_GRAPH_JSON,
        output_dir=target_output_dir,
        supplier_criticality_dir=supplier_criticality_dir,
    )

    validations: list[dict[str, Any]] = []
    if not skip_validation:
        info_line("Output validations")
        validations = validate_active_run_outputs(
            target_output_dir,
            scenario_id=scenario_id,
            days=days,
            output_profile=output_profile,
            max_map_mb=max_map_mb,
        )
        print_preflight(validations)
        assert_validations_ok(validations)

    finished_at = datetime.now(timezone.utc).isoformat()
    write_pipeline_report(
        output_dir=target_output_dir,
        command_name="rebuild-active",
        preflight=preflight,
        validations=validations,
        started_at_utc=started_at,
        finished_at_utc=finished_at,
    )
    map_path = find_generated_map(target_output_dir)
    if map_path:
        ok_line(f"Standalone map: {map_path.resolve()}")
        if open_map:
            open_file_in_default_app(map_path)
    return target_output_dir


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Unified etudecas pipeline around the supply-chain JSON graph.")
    sub = parser.add_subparsers(dest="command", required=True)

    doctor = sub.add_parser("doctor", help="Check data files, scripts and Python runtime dependencies.")
    doctor.add_argument(
        "--no-active-graph",
        action="store_true",
        help="Do not require the retained active lotified graph during the check.",
    )

    rebuild_active = sub.add_parser(
        "rebuild-active",
        aliases=["rebuild-map-5y"],
        help=(
            "One-command operational rebuild: active lotified 5y simulation, standalone compressed map, "
            "artifact validation and pipeline report."
        ),
    )
    rebuild_active.add_argument(
        "--output-dir",
        default=None,
        help=(
            "Output directory. Defaults to a timestamped folder under "
            "etudecas/simulation/result/_reruns."
        ),
    )
    rebuild_active.add_argument("--scenario-id", default="scn:BASE")
    rebuild_active.add_argument("--days", type=int, default=1825)
    rebuild_active.add_argument("--overwrite", action="store_true")
    rebuild_active.add_argument("--dry-run", action="store_true")
    rebuild_active.add_argument("--skip-preflight", action="store_true")
    rebuild_active.add_argument("--skip-validation", action="store_true")
    rebuild_active.add_argument("--with-plots", action="store_true", help="Also generate legacy PNG plots.")
    rebuild_active.add_argument("--open-map", action="store_true", help="Open the generated HTML map at the end.")
    rebuild_active.add_argument(
        "--output-profile",
        choices=["compact", "full"],
        default="compact",
        help="compact is the normal operational mode; full keeps heavy debug CSVs.",
    )
    rebuild_active.add_argument(
        "--full-output",
        action="store_true",
        default=False,
        help="Shortcut for --output-profile full.",
    )
    rebuild_active.add_argument(
        "--max-map-mb",
        type=float,
        default=DEFAULT_MAX_STANDALONE_MAP_MB,
        help="Fail validation if the standalone HTML map exceeds this size.",
    )

    graph = sub.add_parser("graph", help="Rebuild the knowledge-graph JSON from XLSX and geocode it.")

    enrich = sub.add_parser("enrich-graph", help="Create/apply the generic Excel enrichment workbook for a graph JSON.")
    enrich.add_argument("--input-json", required=True)
    enrich.add_argument("--excel", default=repo_rel(DEFAULT_ENRICHMENT_EXCEL))
    enrich.add_argument("--output-json", default="etudecas/data/source/supply_graph_poc_enriched_from_excel.json")
    enrich.add_argument("--report-json", default="etudecas/data/reports/supply_graph_excel_enrichment_report.json")
    enrich.add_argument("--case-config-json", default="", help="Optional case config JSON merged before creating/applying.")
    enrich.add_argument("--create-template", action="store_true")
    enrich.add_argument("--apply", action="store_true")

    prepare = sub.add_parser("prepare", help="Prepare the simulation-ready reference graph from the geocoded graph.")
    prepare.add_argument("--simulation-days", type=int, default=365)

    reference = sub.add_parser("reference", help="Rebuild the active 1y reference baseline from the graph pipeline.")
    reference.add_argument("--simulation-days", type=int, default=365, help="Prep horizon written into the working graph.")
    reference.add_argument("--days", type=int, default=365, help="Final 1y measured horizon.")
    reference.add_argument("--scenario-id", default="scn:BASE")
    reference.add_argument("--skip-map", action="store_true")
    reference.add_argument("--skip-plots", action="store_true")

    all_cmd = sub.add_parser("all", help="Run the full active pipeline and optionally the 5y simulation.")
    all_cmd.add_argument("--simulation-days", type=int, default=365, help="Prep horizon written into the working graph.")
    all_cmd.add_argument("--days", type=int, default=365, help="Final 1y measured horizon.")
    all_cmd.add_argument("--scenario-id", default="scn:BASE")
    all_cmd.add_argument("--with-5y", action="store_true", help="Also rebuild and run the repeated 5y variant.")
    all_cmd.add_argument("--days-5y", type=int, default=1825)
    all_cmd.add_argument("--skip-map", action="store_true")
    all_cmd.add_argument("--skip-plots", action="store_true")

    sim = sub.add_parser("simulate", help="Run the simulator directly from a graph JSON.")
    sim.add_argument("--input-graph", required=True)
    sim.add_argument("--output-dir", required=True)
    sim.add_argument("--scenario-id", default="scn:BASE")
    sim.add_argument("--days", type=int, default=365)
    sim.add_argument("--skip-map", action="store_true")
    sim.add_argument("--skip-plots", action="store_true")

    sim5 = sub.add_parser("simulate-5y", help="Patch the active 1y graph to a repeated 5y horizon and run it.")
    sim5.add_argument("--scenario-id", default="scn:BASE")
    sim5.add_argument("--days", type=int, default=1825)
    sim5.add_argument("--skip-map", action="store_true")
    sim5.add_argument("--skip-plots", action="store_true")

    supplier_criticality = sub.add_parser(
        "supplier-criticality",
        help="Build supplier criticality KPI artifacts used by the map and KPI trees.",
    )
    supplier_criticality.add_argument(
        "--sim-result-dir",
        default="",
        help="Simulation result directory. Defaults to the current retained 5y lot-trace run.",
    )
    supplier_criticality.add_argument(
        "--output-dir",
        default=repo_rel(SUPPLIER_CRITICALITY_OUTPUT_DIR),
        help="Output directory for supplier criticality artifacts.",
    )

    active = sub.add_parser(
        "active-mrp-physical",
        help="Rebuild the current active 5y MRP physical baseline from its retained JSON source.",
    )
    active.add_argument(
        "--output-dir",
        default=None,
        help=(
            "Output directory. Defaults to a timestamped folder under "
            "etudecas/simulation/result/_reruns, so the validated baseline is not overwritten."
        ),
    )
    active.add_argument("--scenario-id", default="scn:BASE")
    active.add_argument("--days", type=int, default=1825)
    active.add_argument("--overwrite", action="store_true", help="Allow writing into an existing non-empty output directory.")
    active.add_argument("--dry-run", action="store_true", help="Print the exact simulator command without running it.")
    active.add_argument("--skip-map", action="store_true")
    active.add_argument("--with-plots", action="store_true", help="Generate legacy PNG plots in addition to the HTML Plotly map.")
    active.add_argument(
        "--output-profile",
        choices=["compact", "full"],
        default="compact",
        help="Result output volume. compact is enough for the interactive map; full keeps heavy debug CSVs.",
    )
    active.add_argument(
        "--full-output",
        action="store_true",
        default=False,
        help="Shortcut for --output-profile full.",
    )

    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.command == "doctor":
        checks = preflight_checks(require_active_graph=not args.no_active_graph)
        print_preflight(checks)
        assert_preflight_ok(checks)
        ok_line("Doctor checks passed.")
        return
    if args.command in {"rebuild-active", "rebuild-map-5y"}:
        output_profile = "full" if args.full_output else args.output_profile
        run_operational_rebuild(
            output_dir=Path(args.output_dir) if args.output_dir else None,
            scenario_id=args.scenario_id,
            days=args.days,
            output_profile=output_profile,
            overwrite=args.overwrite,
            dry_run=args.dry_run,
            skip_preflight=args.skip_preflight,
            skip_validation=args.skip_validation,
            with_plots=args.with_plots,
            open_map=args.open_map,
            max_map_mb=args.max_map_mb,
        )
        return
    if args.command == "graph":
        build_knowledge_graph()
        return
    if args.command == "enrich-graph":
        run_excel_enrichment(
            input_json=resolve_repo_path(Path(args.input_json)),
            excel=resolve_repo_path(Path(args.excel)),
            output_json=resolve_repo_path(Path(args.output_json)),
            report_json=resolve_repo_path(Path(args.report_json)),
            case_config_json=resolve_repo_path(Path(args.case_config_json)) if args.case_config_json else None,
            create_template=args.create_template,
            apply=args.apply,
        )
        return
    if args.command == "prepare":
        prepare_reference_graph(simulation_days=args.simulation_days)
        return
    if args.command == "reference":
        build_knowledge_graph()
        prepare_reference_graph(simulation_days=args.simulation_days)
        build_reference_baseline(
            scenario_id=args.scenario_id,
            days=args.days,
            skip_map=args.skip_map,
            skip_plots=args.skip_plots,
        )
        return
    if args.command == "all":
        build_knowledge_graph()
        prepare_reference_graph(simulation_days=args.simulation_days)
        build_reference_baseline(
            scenario_id=args.scenario_id,
            days=args.days,
            skip_map=args.skip_map,
            skip_plots=args.skip_plots,
        )
        if args.with_5y:
            run_5y_reference(
                scenario_id=args.scenario_id,
                days=args.days_5y,
                skip_map=args.skip_map,
                skip_plots=args.skip_plots,
            )
        return
    if args.command == "simulate":
        run_direct_simulation(
            input_graph=Path(args.input_graph),
            output_dir=Path(args.output_dir),
            scenario_id=args.scenario_id,
            days=args.days,
            skip_map=args.skip_map,
            skip_plots=args.skip_plots,
        )
        return
    if args.command == "simulate-5y":
        run_5y_reference(
            scenario_id=args.scenario_id,
            days=args.days,
            skip_map=args.skip_map,
            skip_plots=args.skip_plots,
        )
        return
    if args.command == "supplier-criticality":
        build_supplier_criticality(
            sim_result_dir=Path(args.sim_result_dir) if args.sim_result_dir else None,
            output_dir=Path(args.output_dir),
        )
        return
    if args.command == "active-mrp-physical":
        output_profile = "full" if args.full_output else args.output_profile
        run_active_mrp_physical(
            output_dir=Path(args.output_dir) if args.output_dir else None,
            scenario_id=args.scenario_id,
            days=args.days,
            output_profile=output_profile,
            overwrite=args.overwrite,
            dry_run=args.dry_run,
            skip_map=args.skip_map,
            skip_plots=not args.with_plots,
        )
        return
    raise ValueError(f"Unsupported command: {args.command}")


if __name__ == "__main__":
    main()
