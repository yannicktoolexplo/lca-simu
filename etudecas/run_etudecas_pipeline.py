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
from etudecas.simulation.analysis.component_immobilized_stock import (  # noqa: E402
    build_component_immobilized_stock_artifacts,
)
from etudecas.simulation.analysis.finished_goods_inventory_value import (  # noqa: E402
    build_finished_goods_inventory_value_artifacts,
)
from etudecas.analysis.from_simulation.report_component_immobilized_stock import (  # noqa: E402
    DEFAULT_PRODUCT_SOURCES,
    build_report as build_component_stock_source_truth_report,
)
from etudecas.analysis.from_simulation.report_finished_goods_stock_value import (  # noqa: E402
    build_report as build_finished_goods_stock_source_truth_report,
)
from etudecas.analysis.from_simulation.audit_source_truth_alignment import (  # noqa: E402
    build_report as build_source_truth_alignment_report,
)
from etudecas.simulation.run_format import export_run_package, validate_run_package  # noqa: E402

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
ROBUST_MONTECARLO_SCRIPT = ROOT / "simulation" / "montecarlo" / "run_robust_montecarlo.py"
SUPPLIER_CRITICALITY_SCRIPT = ROOT / "risk" / "supplier_criticality" / "build_supplier_criticality.py"
SUPPLIER_CRITICALITY_OUTPUT_DIR = ROOT / "risk" / "supplier_criticality" / "result"
SUPPLIER_RISK_CAMPAIGN_CASES_CSV = (
    ROOT / "simulation" / "sensibility" / "supplier_risk_campaign_multisource_result" / "supplier_risk_campaign_cases.csv"
)
SOURCE_PROFILE_SCRIPT = ROOT / "data" / "profile_source_files.py"
DEFAULT_CASE_CONFIG_JSON = ROOT / "config" / "cases" / "data_poc.json"
DEFAULT_ENRICHMENT_EXCEL = ROOT / "config" / "cases" / "data_poc_enrichment_input.xlsx"
ACTIVE_MRP_STATIC_REQUIREMENT_PAIRS = [
    ("M-1430", "item:038005"),
    ("M-1430", "item:042342"),
    ("M-1430", "item:333362"),
    ("M-1430", "item:344135"),
    ("M-1430", "item:708073"),
    ("M-1430", "item:730384"),
    ("M-1430", "item:734545"),
    ("M-1430", "item:773474"),
    ("M-1810", "item:001757"),
    ("M-1810", "item:001848"),
    ("M-1810", "item:001893"),
    ("M-1810", "item:002612"),
    ("M-1810", "item:007923"),
    ("M-1810", "item:016332"),
    ("M-1810", "item:029313"),
    ("M-1810", "item:039668"),
    ("M-1810", "item:049371"),
    ("M-1810", "item:055703"),
    ("M-1810", "item:099439"),
    ("M-1810", "item:338928"),
    ("M-1810", "item:338929"),
    ("M-1810", "item:426331"),
    ("M-1810", "item:693055"),
]
ACTIVE_MRP_COMPONENT_TARGET_PAIRS = [
    ("M-1430", "item:038005"),
    ("M-1430", "item:042342"),
    ("M-1430", "item:333362"),
    ("M-1430", "item:344135"),
    ("M-1430", "item:708073"),
    ("M-1430", "item:730384"),
    ("M-1430", "item:734545"),
    ("M-1430", "item:773474"),
    ("M-1810", "item:001757"),
    ("M-1810", "item:001848"),
    ("M-1810", "item:001893"),
    ("M-1810", "item:002612"),
    ("M-1810", "item:007923"),
    ("M-1810", "item:016332"),
    ("M-1810", "item:029313"),
    ("M-1810", "item:039668"),
    ("M-1810", "item:049371"),
    ("M-1810", "item:055703"),
    ("M-1810", "item:099439"),
    ("M-1810", "item:338928"),
    ("M-1810", "item:338929"),
    ("M-1810", "item:426331"),
    ("M-1810", "item:693055"),
]
ACTIVE_MRP_COMPONENT_SAFETY_TARGET_FACTOR = 1.0
ACTIVE_MRP_PHYSICAL_INITIAL_STATE_ARGS = living_supply_initial_state_args()
ACTIVE_MRP_OPENING_PRODUCTION_ORDER_BOM_ISSUE_MODE = "wip"
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


def run_robust_montecarlo_for_result(
    *,
    output_dir: Path,
    runs: int,
    probe_runs: int,
    profiles: str,
    final_profile: str,
    days: int,
    seed: int,
    trajectory_max_points: int,
    trajectory_display_runs: int,
    workers: int,
) -> Path:
    montecarlo_dir = output_dir / "montecarlo"
    args = [
        "--manifest-json",
        repo_rel(output_dir / "run_manifest.json"),
        "--output-dir",
        repo_rel(montecarlo_dir),
        "--days",
        str(days),
        "--seed",
        str(seed),
        "--profiles",
        profiles,
        "--final-profile",
        final_profile,
        "--probe-runs",
        str(probe_runs),
        "--final-runs",
        str(runs),
        "--trajectory-max-points",
        str(trajectory_max_points),
        "--trajectory-display-runs",
        str(trajectory_display_runs),
        "--workers",
        str(max(1, int(workers))),
    ]
    run_python(ROBUST_MONTECARLO_SCRIPT, *args)
    return montecarlo_dir / "selected" / "montecarlo_summary.json"


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
                "773474.xlsx",
                "268091.xlsx",
                "268967.xlsx",
                "Data_poc.xlsx",
                "demand_PF.xlsx",
                "Extract_En_cours.xlsx",
                "Fournisseur.xlsx",
                "Extract_Données_Complémentaires.xlsx",
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
        SOURCE_PROFILE_SCRIPT,
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
    montecarlo_summary_json: Path | None = None,
    montecarlo_expected_runs: int | None = None,
) -> list[dict[str, Any]]:
    summary_path = output_dir / "summaries" / "first_simulation_summary.json"
    report_path = output_dir / "reports" / "first_simulation_report.md"
    lot_events_path = output_dir / "data" / "production_lot_events.csv"
    lot_genealogy_path = output_dir / "data" / "production_lot_genealogy.csv"
    lot_audit_path = output_dir / "reports" / "lot_path_audit.md"
    daily_path = output_dir / "data" / "first_simulation_daily.csv"
    component_immob_daily_path = output_dir / "data" / "component_immobilized_stock_daily.csv"
    component_immob_summary_path = output_dir / "data" / "component_immobilized_stock_summary.csv"
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
    add(
        "component_immobilized_stock_daily",
        component_immob_daily_path.exists() and count_csv_rows(component_immob_daily_path) > 0,
        f"{count_csv_rows(component_immob_daily_path)} rows",
    )
    add(
        "component_immobilized_stock_summary",
        component_immob_summary_path.exists() and count_csv_rows(component_immob_summary_path) > 0,
        f"{count_csv_rows(component_immob_summary_path)} rows",
    )
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
    if montecarlo_summary_json is not None:
        mc_summary_path = montecarlo_summary_json
        mc_dir = mc_summary_path.parent
        mc_samples_path = mc_dir / "montecarlo_samples.csv"
        mc_trajectories_path = mc_dir / "montecarlo_trajectories.json"
        add("montecarlo_summary", mc_summary_path.exists(), repo_rel(mc_summary_path))
        add("montecarlo_samples", mc_samples_path.exists(), repo_rel(mc_samples_path))
        add("montecarlo_trajectories", mc_trajectories_path.exists(), repo_rel(mc_trajectories_path))
        if mc_summary_path.exists():
            mc_summary = load_json(mc_summary_path)
            add(
                "montecarlo_scenario_id",
                str(mc_summary.get("scenario_id") or "") == scenario_id,
                f"{mc_summary.get('scenario_id')} == {scenario_id}",
            )
            add(
                "montecarlo_days",
                int(mc_summary.get("days_override") or -1) == days,
                f"{mc_summary.get('days_override')} == {days}",
            )
            if montecarlo_expected_runs is not None:
                add(
                    "montecarlo_successful_runs",
                    int(mc_summary.get("successful_stochastic_runs") or -1) == int(montecarlo_expected_runs),
                    f"{mc_summary.get('successful_stochastic_runs')} == {montecarlo_expected_runs}",
                )
            add("montecarlo_failed_runs", int(mc_summary.get("failed_runs") or 0) == 0, str(mc_summary.get("failed_runs")))
    run_package_dir = output_dir / "run"
    if run_package_dir.exists():
        for row in validate_run_package(run_package_dir):
            add(f"generic_run:{row['name']}", bool(row.get("ok")), str(row.get("detail", "")))
    else:
        add("generic_run:package_exists", False, repo_rel(run_package_dir))
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
    manifest_path = output_dir / "run_manifest.json"
    manifest = load_json(manifest_path) if manifest_path.exists() else {}
    report = {
        "schema_version": "etudecas.pipeline_report.v1",
        "command": command_name,
        "started_at_utc": started_at_utc,
        "finished_at_utc": finished_at_utc,
        "output_dir": repo_rel(output_dir),
        "map_html": repo_rel(map_path) if map_path else None,
        "generic_run_package": repo_rel(output_dir / "run") if (output_dir / "run").exists() else None,
        "map_size_mb": round(map_path.stat().st_size / (1024 * 1024), 3) if map_path and map_path.exists() else None,
        "kpis": {
            "fill_rate": kpis.get("fill_rate"),
            "ending_backlog": kpis.get("ending_backlog"),
            "total_cost": kpis.get("total_cost"),
            "total_explicit_initialization_stock_qty": kpis.get("total_explicit_initialization_stock_qty"),
            "total_explicit_initialization_pipeline_qty": kpis.get("total_explicit_initialization_pipeline_qty"),
        },
        "montecarlo": manifest.get("montecarlo") if isinstance(manifest.get("montecarlo"), dict) else None,
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
        f"- Generic run package: `{report['generic_run_package'] or 'missing'}`",
        f"- Map size MB: `{report['map_size_mb']}`",
        f"- Fill rate: `{report['kpis']['fill_rate']}`",
        f"- Ending backlog: `{report['kpis']['ending_backlog']}`",
        f"- Total cost: `{report['kpis']['total_cost']}`",
        f"- Monte Carlo: `{report['montecarlo'] or 'not run'}`",
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


def optional_pf_service_target_args(pf_service_target: float | None) -> list[str]:
    if pf_service_target is None:
        return []
    return ["--pf-service-target", f"{max(0.0, min(1.0, float(pf_service_target))):g}"]


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


def prepare_reference_graph(*, simulation_days: int, pf_service_target: float | None = None) -> None:
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
        *optional_pf_service_target_args(pf_service_target),
    )


def build_reference_baseline(
    *,
    scenario_id: str,
    days: int,
    skip_map: bool,
    skip_plots: bool,
    pf_service_target: float | None = None,
) -> None:
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
        *optional_pf_service_target_args(pf_service_target),
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
    build_component_stock_artifacts(input_graph=FINAL_GRAPH_5Y_JSON, output_dir=FINAL_OUTPUT_5Y_DIR)
    build_finished_goods_stock_artifacts(input_graph=FINAL_GRAPH_5Y_JSON, output_dir=FINAL_OUTPUT_5Y_DIR)
    build_component_stock_source_truth_reports(input_graph=FINAL_GRAPH_5Y_JSON, output_dir=FINAL_OUTPUT_5Y_DIR)
    build_finished_goods_stock_source_truth_reports(output_dir=FINAL_OUTPUT_5Y_DIR)
    export_run_package(output_dir=FINAL_OUTPUT_5Y_DIR, input_graph=FINAL_GRAPH_5Y_JSON)


def refresh_active_mrp_physical_graph(
    *,
    scenario_id: str,
    days: int,
    pf_service_target: float | None,
) -> None:
    """Rebuild the retained active lotified graph from canonical source files."""
    info_line("Refreshing active graph from source workbooks")
    build_knowledge_graph()
    prepare_reference_graph(simulation_days=365, pf_service_target=pf_service_target)
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
        "365",
        "--skip-simulation",
        *optional_pf_service_target_args(pf_service_target),
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
        "365",
        "--skip-simulation",
    )
    patch_repeated_horizon_graph(FINAL_GRAPH_1Y_JSON, ACTIVE_MRP_PHYSICAL_GRAPH_JSON, scenario_id=scenario_id, days=days)
    ok_line(f"Active graph refreshed: {ACTIVE_MRP_PHYSICAL_GRAPH_JSON.resolve()}")


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
    build_component_stock_artifacts(input_graph=input_graph, output_dir=output_dir)
    build_finished_goods_stock_artifacts(input_graph=input_graph, output_dir=output_dir)
    build_component_stock_source_truth_reports(input_graph=input_graph, output_dir=output_dir)
    build_finished_goods_stock_source_truth_reports(output_dir=output_dir)
    export_run_package(output_dir=output_dir, input_graph=input_graph)


def build_supplier_criticality(*, sim_result_dir: Path | None, output_dir: Path) -> None:
    args = [
        "--output-dir",
        repo_rel(output_dir),
    ]
    if sim_result_dir is not None:
        run_package = sim_result_dir / "run"
        if run_package.exists():
            args.extend(["--run-package", repo_rel(run_package)])
        else:
            args.extend(["--sim-result-dir", repo_rel(sim_result_dir)])
    run_python(SUPPLIER_CRITICALITY_SCRIPT, *args)


def build_supplier_local_criticality_artifacts(*, input_graph: Path, output_dir: Path) -> None:
    from etudecas.visualization.maps.build_supplychain_worldmap import build_supplier_local_criticality

    data_dir = output_dir / "data"
    summaries_dir = output_dir / "summaries"
    csv_path = data_dir / "supplier_local_criticality_ranking.csv"
    json_path = summaries_dir / "supplier_local_criticality_summary.json"
    raw = load_json(input_graph)
    _, ranking_rows, summary = build_supplier_local_criticality(
        raw,
        data_dir / "production_supplier_shipments_daily.csv",
        data_dir / "production_supplier_stocks_daily.csv",
        data_dir / "production_supplier_capacity_daily.csv",
        data_dir / "production_constraint_daily.csv",
        ROOT / "simulation" / "sensibility" / "result" / "sensitivity_cases.csv",
        ROOT / "simulation" / "sensibility" / "structural_result" / "sensitivity_cases.csv",
    )
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    columns = sorted({key for row in ranking_rows for key in row.keys()})
    with csv_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader()
        writer.writerows(ranking_rows)
    write_json(json_path, {"summary": summary, "ranking": ranking_rows})
    ok_line(f"Supplier local criticality: {csv_path.resolve()}")


def build_component_stock_artifacts(*, input_graph: Path, output_dir: Path) -> None:
    summary = build_component_immobilized_stock_artifacts(
        run_dir=output_dir,
        graph_path=input_graph,
        output_dir=output_dir / "data",
    )
    ok_line(
        "Component immobilized stock: "
        f"{summary['daily_rows']} daily rows, {summary['component_daily_rows']} component rows"
    )


def build_finished_goods_stock_artifacts(*, input_graph: Path, output_dir: Path) -> None:
    summary = build_finished_goods_inventory_value_artifacts(
        run_dir=output_dir,
        graph_path=input_graph,
        output_dir=output_dir / "data",
    )
    ok_line(
        "Finished-goods stock value: "
        f"{summary['daily_rows']} daily rows, {summary['summary_rows']} summary rows"
    )


def build_finished_goods_stock_source_truth_reports(*, output_dir: Path) -> None:
    summary = build_finished_goods_stock_source_truth_report(
        run_dir=output_dir,
        output_dir=output_dir / "reports" / "source_truth_finished_goods_stock",
    )
    ok_line(
        "Finished-goods stock source-truth report: "
        f"{summary['rows']} comparison rows, {summary['snapshot_pairs']} snapshot pairs"
    )


def build_component_stock_source_truth_reports(*, input_graph: Path, output_dir: Path) -> None:
    summary = build_component_stock_source_truth_report(
        run_dir=output_dir,
        graph_path=input_graph,
        product_codes=sorted(DEFAULT_PRODUCT_SOURCES),
        output_dir=output_dir / "reports" / "source_truth_component_stock",
    )
    ok_line(
        "Component stock source-truth report: "
        f"{summary['rows']} comparison rows, {summary['snapshot_rows']} snapshot pairs"
    )
    for product_code in sorted(DEFAULT_PRODUCT_SOURCES):
        try:
            alignment = build_source_truth_alignment_report(
                run_dir=output_dir,
                graph_path=input_graph,
                product_code=product_code,
                output_dir=output_dir / "reports" / f"source_truth_alignment_{product_code}",
            )
        except (FileNotFoundError, ValueError) as exc:
            warn_line(f"Source-truth alignment {product_code} skipped: {exc}")
            continue
        ok_line(
            "Source-truth alignment "
            f"{product_code}: source stock {alignment['source_component_stock_value_eur']:.0f} EUR, "
            f"opening sim delta {alignment['component_stock_value_delta_eur']:.0f} EUR"
        )


def build_map_for_simulation_result(
    *,
    input_graph: Path,
    output_dir: Path,
    supplier_criticality_dir: Path,
    simulated_risk_output_dir: Path | None = None,
    montecarlo_summary_json: Path | None = None,
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
        "--run-package",
        repo_rel(output_dir / "run"),
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
    if simulated_risk_output_dir is not None:
        map_cmd.extend(["--simulated-risk-output-dir", repo_rel(simulated_risk_output_dir)])
    run_montecarlo_summary_json = (
        montecarlo_summary_json
        if montecarlo_summary_json is not None
        else output_dir / "montecarlo" / "selected" / "montecarlo_summary.json"
    )
    map_cmd.extend(["--montecarlo-summary-json", repo_rel(run_montecarlo_summary_json)])
    run_python(map_script, *map_cmd[2:])
    return map_output_path


def normalize_graph_item_id(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    return text if text.startswith("item:") else f"item:{text}"


def load_supplier_campaign_sensitivity_cases(path: Path = SUPPLIER_RISK_CAMPAIGN_CASES_CSV) -> dict[tuple[str, str], dict[str, str]]:
    """Return the strongest observed sensitivity case per supplier/risk_type."""
    if not path.exists():
        return {}
    best: dict[tuple[str, str], dict[str, str]] = {}
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            supplier_id = str(row.get("supplier_id") or "").strip()
            risk_type = str(row.get("risk_type") or "").strip()
            if not supplier_id or supplier_id == "__all__" or not risk_type:
                continue
            key = (supplier_id, risk_type)
            score = float(row.get("score_decisionnel_modele") or row.get("impact_score") or 0.0)
            previous = best.get(key)
            previous_score = (
                float(previous.get("score_decisionnel_modele") or previous.get("impact_score") or 0.0)
                if previous
                else -1.0
            )
            if score > previous_score:
                best[key] = dict(row)
    return best


def sensitivity_note(
    sensitivity_cases: dict[tuple[str, str], dict[str, str]],
    supplier_id: str,
    risk_type: str,
) -> str:
    case = sensitivity_cases.get((supplier_id, risk_type))
    if not case:
        return "calibrage metier: pas de cas de sensibilite local disponible"
    score = str(case.get("score_decisionnel_pct") or case.get("impact_pct") or "n/a")
    multiplier = str(case.get("multiplier") or "n/a")
    kpi = str(case.get("impact_metier_kpi") or "KPI")
    delta = str(case.get("impact_metier_delta") or "n/a")
    return f"calibre sensibilite: test {risk_type}={multiplier}, score {score}%, KPI {kpi} {delta}"


def graph_edge_lookup(data: dict[str, Any]) -> dict[tuple[str, str, str], dict[str, Any]]:
    lookup: dict[tuple[str, str, str], dict[str, Any]] = {}
    for edge in data.get("edges") or []:
        if not isinstance(edge, dict):
            continue
        src = str(edge.get("from") or "")
        dst = str(edge.get("to") or "")
        for item in edge.get("items") or []:
            lookup[(src, dst, normalize_graph_item_id(item))] = edge
    return lookup


def supplier_risk_event(
    *,
    event_id: str,
    supplier_id: str,
    item_id: str,
    risk_type: str,
    multiplier: float,
    start_day: int,
    end_day: int,
    dst_node_id: str = "",
    edge_id: str = "",
    notes: str = "",
) -> dict[str, Any]:
    return {
        "event_id": event_id,
        "supplier_id": supplier_id,
        "item_id": normalize_graph_item_id(item_id),
        "dst_node_id": dst_node_id,
        "edge_id": edge_id,
        "risk_type": risk_type,
        "multiplier": multiplier,
        "start_day": int(start_day),
        "end_day": int(end_day),
        "notes": notes,
    }


def repeated_windows(
    *,
    horizon_days: int,
    start_offset: int,
    duration_days: int,
    repeat_days: int = 365,
) -> list[tuple[int, int]]:
    windows: list[tuple[int, int]] = []
    base = 0
    while base < max(1, horizon_days):
        start = base + int(start_offset)
        end = start + max(1, int(duration_days)) - 1
        if start < horizon_days:
            windows.append((max(0, start), min(horizon_days - 1, end)))
        base += max(1, int(repeat_days))
    return windows


def variable_repeated_windows(
    *,
    horizon_days: int,
    start_offsets: list[int],
    duration_days: list[int],
    repeat_days: int = 365,
) -> list[tuple[int, int, int]]:
    windows: list[tuple[int, int, int]] = []
    if not start_offsets or not duration_days:
        return windows
    year_idx = 0
    base = 0
    while base < max(1, horizon_days):
        offset = int(start_offsets[year_idx % len(start_offsets)])
        duration = int(duration_days[year_idx % len(duration_days)])
        start = base + offset
        end = start + max(1, duration) - 1
        if start < horizon_days:
            windows.append((year_idx + 1, max(0, start), min(horizon_days - 1, end)))
        year_idx += 1
        base += max(1, int(repeat_days))
    return windows


def build_calibrated_pharma_supplier_risk_events(
    data: dict[str, Any],
    *,
    horizon_days: int,
) -> list[dict[str, Any]]:
    """Build an injected pharma risk portfolio calibrated with sensitivity artifacts.

    The companion run still uses endogenous state-dependent triggers. These events are
    exogenous shocks that make the run severe enough to test propagation: US hurricane
    on upstream active material, packaging/quality crises on sensitive suppliers, and
    an internal PFI release slowdown.
    """
    edge_by_key = graph_edge_lookup(data)
    sensitivity_cases = load_supplier_campaign_sensitivity_cases()
    node_by_id = {
        str(node.get("id") or ""): node
        for node in data.get("nodes") or []
        if isinstance(node, dict) and str(node.get("id") or "")
    }
    events: list[dict[str, Any]] = []

    def add_lane_event(
        *,
        slug: str,
        supplier_id: str,
        dst_node_id: str,
        item_id: str,
        risk_type: str,
        multiplier: float,
        start_day: int,
        end_day: int,
        scenario_label: str,
        require_existing_lane: bool = True,
    ) -> None:
        item_id = normalize_graph_item_id(item_id)
        edge = edge_by_key.get((supplier_id, dst_node_id, item_id), {})
        if require_existing_lane and not edge:
            return
        sens = sensitivity_note(sensitivity_cases, supplier_id, risk_type)
        events.append(
            supplier_risk_event(
                event_id=f"{slug}_{supplier_id}_{item_id.replace(':', '')}_{risk_type}_d{start_day}_{end_day}",
                supplier_id=supplier_id,
                item_id=item_id,
                dst_node_id=dst_node_id,
                edge_id=str(edge.get("id") or ""),
                risk_type=risk_type,
                multiplier=multiplier,
                start_day=start_day,
                end_day=end_day,
                notes=f"{scenario_label}. {sens}.",
            )
        )

    def is_us_supplier(node_id: str) -> bool:
        node = node_by_id.get(node_id) or {}
        geo = node.get("geo") if isinstance(node.get("geo"), dict) else {}
        country = str(geo.get("country") or node.get("country") or "").strip().lower()
        return country in {"united states", "usa", "us", "etats-unis", "états-unis"}

    # 1) US hurricane: all US suppliers feeding item:021081 into SDC-1450 are hit
    # together. The downstream effect is delayed but critical for PFI 773474.
    us_supplier_edges = [
        edge
        for edge in data.get("edges") or []
        if isinstance(edge, dict)
        and str(edge.get("to") or "") == "SDC-1450"
        and normalize_graph_item_id("021081") in {normalize_graph_item_id(item) for item in edge.get("items") or []}
        and is_us_supplier(str(edge.get("from") or ""))
    ]
    for idx, (start, end) in enumerate(repeated_windows(horizon_days=horizon_days, start_offset=215, duration_days=130), start=1):
        for edge in us_supplier_edges:
            supplier_id = str(edge.get("from") or "")
            dst_node_id = str(edge.get("to") or "")
            item_id = "item:021081"
            label = (
                f"Ouragan US saison {idx}: fermeture/ralentissement fournisseurs americains "
                "et congestion transport sur l'actif amont 021081"
            )
            add_lane_event(
                slug=f"us_hurricane_y{idx}",
                supplier_id=supplier_id,
                dst_node_id=dst_node_id,
                item_id=item_id,
                risk_type="availability",
                multiplier=0.15,
                start_day=start,
                end_day=end,
                scenario_label=label,
            )
            add_lane_event(
                slug=f"us_hurricane_y{idx}",
                supplier_id=supplier_id,
                dst_node_id=dst_node_id,
                item_id=item_id,
                risk_type="capacity",
                multiplier=0.20,
                start_day=start,
                end_day=end,
                scenario_label=label,
            )
            add_lane_event(
                slug=f"us_hurricane_y{idx}",
                supplier_id=supplier_id,
                dst_node_id=dst_node_id,
                item_id=item_id,
                risk_type="lead_time_extra_days",
                multiplier=90.0,
                start_day=start,
                end_day=min(horizon_days - 1, end + 45),
                scenario_label=label,
            )
            add_lane_event(
                slug=f"us_hurricane_y{idx}",
                supplier_id=supplier_id,
                dst_node_id=dst_node_id,
                item_id=item_id,
                risk_type="transport_cost",
                multiplier=3.0,
                start_day=start,
                end_day=min(horizon_days - 1, end + 45),
                scenario_label=label,
            )

    # 2) Pharma packaging and incoming quality crises calibrated from sensitivity:
    # SDC-VD0508918A and SDC-VD0525412A were the strongest replanification/stockout
    # signals for lead-time and quality-delay stress tests.
    for idx, (start, end) in enumerate(repeated_windows(horizon_days=horizon_days, start_offset=35, duration_days=220), start=1):
        add_lane_event(
            slug=f"pharma_pack_delay_y{idx}",
            supplier_id="SDC-VD0508918A",
            dst_node_id="M-1430",
            item_id="item:730384",
            risk_type="lead_time_extra_days",
            multiplier=75.0,
            start_day=start,
            end_day=end,
            scenario_label="Crise pharma packaging: retard fournisseur sensible 730384",
        )
        add_lane_event(
            slug=f"pharma_pack_quarantine_y{idx}",
            supplier_id="SDC-VD0508918A",
            dst_node_id="M-1430",
            item_id="item:730384",
            risk_type="quality_delay",
            multiplier=35.0,
            start_day=start + 20,
            end_day=min(horizon_days - 1, end + 20),
            scenario_label="Crise pharma packaging: quarantaine qualite 730384",
        )
        add_lane_event(
            slug=f"pharma_pack_quarantine_y{idx}",
            supplier_id="SDC-VD0508918A",
            dst_node_id="M-1430",
            item_id="item:730384",
            risk_type="stock",
            multiplier=0.15,
            start_day=start + 20,
            end_day=min(horizon_days - 1, end + 20),
            scenario_label="Crise pharma packaging: stock fournisseur 730384 partiellement bloque en quarantaine",
        )
        add_lane_event(
            slug=f"pharma_pack_delay_y{idx}",
            supplier_id="SDC-VD0525412A",
            dst_node_id="M-1430",
            item_id="item:333362",
            risk_type="lead_time_extra_days",
            multiplier=90.0,
            start_day=start,
            end_day=end,
            scenario_label="Crise pharma packaging: retard fournisseur sensible 333362",
        )
        add_lane_event(
            slug=f"pharma_pack_quarantine_y{idx}",
            supplier_id="SDC-VD0525412A",
            dst_node_id="M-1430",
            item_id="item:333362",
            risk_type="quality_delay",
            multiplier=45.0,
            start_day=start + 20,
            end_day=min(horizon_days - 1, end + 20),
            scenario_label="Crise pharma packaging: quarantaine qualite 333362",
        )
        add_lane_event(
            slug=f"pharma_pack_quarantine_y{idx}",
            supplier_id="SDC-VD0525412A",
            dst_node_id="M-1430",
            item_id="item:333362",
            risk_type="stock",
            multiplier=0.10,
            start_day=start + 20,
            end_day=min(horizon_days - 1, end + 20),
            scenario_label="Crise pharma packaging: stock fournisseur 333362 partiellement bloque en quarantaine",
        )
        add_lane_event(
            slug=f"pharma_pack_cost_y{idx}",
            supplier_id="SDC-VD0525412A",
            dst_node_id="M-1430",
            item_id="item:333362",
            risk_type="purchase_cost",
            multiplier=2.0,
            start_day=start,
            end_day=end,
            scenario_label="Crise pharma packaging: achat spot et lots urgents 333362",
        )

    # 3) Supplier reliability and batch release shocks on high-volume pharma inputs.
    for idx, (start, end) in enumerate(repeated_windows(horizon_days=horizon_days, start_offset=70, duration_days=260), start=1):
        add_lane_event(
            slug=f"pharma_capsule_capacity_y{idx}",
            supplier_id="SDC-VD0914690A",
            dst_node_id="M-1430",
            item_id="item:042342",
            risk_type="capacity",
            multiplier=0.22,
            start_day=start,
            end_day=end,
            scenario_label="Crise pharma composant haute cadence: capacite fournisseur 042342 fortement reduite",
        )
        add_lane_event(
            slug=f"pharma_capsule_availability_y{idx}",
            supplier_id="SDC-VD0914690A",
            dst_node_id="M-1430",
            item_id="item:042342",
            risk_type="availability",
            multiplier=0.35,
            start_day=start,
            end_day=end,
            scenario_label="Crise pharma composant haute cadence: disponibilite fournisseur 042342 degradee",
        )
        add_lane_event(
            slug=f"pharma_capsule_reliability_y{idx}",
            supplier_id="SDC-VD0914690A",
            dst_node_id="M-1430",
            item_id="item:042342",
            risk_type="reliability",
            multiplier=0.50,
            start_day=start,
            end_day=end,
            scenario_label="Crise pharma composant haute cadence: pertes de fiabilite 042342",
        )
        add_lane_event(
            slug=f"pharma_pack_reliability_y{idx}",
            supplier_id="SDC-VD0993480A",
            dst_node_id="M-1430",
            item_id="item:344135",
            risk_type="reliability",
            multiplier=0.55,
            start_day=start,
            end_day=end,
            scenario_label="Crise pharma packaging: non-conformites fournisseur 344135",
        )
        add_lane_event(
            slug=f"pharma_pack_availability_y{idx}",
            supplier_id="SDC-VD0993480A",
            dst_node_id="M-1430",
            item_id="item:344135",
            risk_type="availability",
            multiplier=0.35,
            start_day=start,
            end_day=end,
            scenario_label="Crise pharma packaging: disponibilite fournisseur 344135 degradee",
        )
        add_lane_event(
            slug=f"pharma_pack_delay_y{idx}",
            supplier_id="SDC-VD0993480A",
            dst_node_id="M-1430",
            item_id="item:344135",
            risk_type="lead_time_extra_days",
            multiplier=55.0,
            start_day=start,
            end_day=min(horizon_days - 1, end + 30),
            scenario_label="Crise pharma packaging: retard fournisseur 344135",
        )

    # 4) Downstream PFI release consequence: if the US active-material chain is hit,
    # the internal PFI 773474 route can also slow down due to release testing and
    # allocation. This makes the upstream hurricane visible at the pharma factory.
    for idx, (start, end) in enumerate(repeated_windows(horizon_days=horizon_days, start_offset=250, duration_days=180), start=1):
        add_lane_event(
            slug=f"pfi_release_hold_y{idx}",
            supplier_id="SDC-1450",
            dst_node_id="M-1430",
            item_id="item:773474",
            risk_type="lead_time_extra_days",
            multiplier=60.0,
            start_day=start,
            end_day=end,
            scenario_label="Propagation pharma: liberation PFI 773474 ralentie apres tension matiere active",
        )
        add_lane_event(
            slug=f"pfi_release_hold_y{idx}",
            supplier_id="SDC-1450",
            dst_node_id="M-1430",
            item_id="item:773474",
            risk_type="quality_delay",
            multiplier=30.0,
            start_day=start,
            end_day=end,
            scenario_label="Propagation pharma: controle qualite et liberation PFI 773474 prolonges",
        )
        add_lane_event(
            slug=f"pfi_release_hold_y{idx}",
            supplier_id="SDC-1450",
            dst_node_id="M-1430",
            item_id="item:773474",
            risk_type="capacity",
            multiplier=0.40,
            start_day=start,
            end_day=end,
            scenario_label="Propagation pharma: capacite PFI 773474 reservee et allocation limitee",
        )
        add_lane_event(
            slug=f"pfi_release_hold_y{idx}",
            supplier_id="SDC-1450",
            dst_node_id="M-1430",
            item_id="item:773474",
            risk_type="availability",
            multiplier=0.25,
            start_day=start,
            end_day=end,
            scenario_label="Propagation pharma: allocation PFI 773474 vers Gien limitee",
        )

    # 5) More varied pharma supplier waves. These windows are deliberately not
    # annual clones: they create several distinct business paths and make the
    # state-dependent layer easier to audit by route and product.
    varied_supplier_waves = [
        {
            "slug": "api_excipient_pressure",
            "supplier_id": "SDC-VD0520132A",
            "dst_node_id": "M-1430",
            "item_id": "item:038005",
            "label": "Crise excipient pharma: saturation fournisseur et liberation qualite 038005",
            "windows": variable_repeated_windows(
                horizon_days=horizon_days,
                start_offsets=[18, 122, 235, 52, 301],
                duration_days=[155, 96, 185, 128, 210],
            ),
            "events": [
                ("capacity", 0.28, 0, 0),
                ("availability", 0.42, 8, 10),
                ("external_capacity", 0.35, 0, 65),
                ("external_availability", 0.45, 0, 65),
                ("quality_delay", 52.0, 26, 42),
                ("lead_time_extra_days", 85.0, 0, 55),
                ("purchase_cost", 2.4, 0, 20),
            ],
        },
        {
            "slug": "closure_component_pressure",
            "supplier_id": "SDC-VD0993480A",
            "dst_node_id": "M-1430",
            "item_id": "item:344135",
            "label": "Crise composant de fermeture pharma: non-conformites et faiblesse capacitaire 344135",
            "windows": variable_repeated_windows(
                horizon_days=horizon_days,
                start_offsets=[42, 98, 178, 255, 64],
                duration_days=[180, 142, 118, 220, 166],
            ),
            "events": [
                ("stock", 0.04, 0, 28),
                ("external_capacity", 0.25, 0, 84),
                ("external_availability", 0.30, 0, 84),
                ("reliability", 0.32, 12, 20),
                ("availability", 0.18, 28, 42),
                ("lead_time_extra_days", 115.0, 0, 70),
                ("quality_delay", 64.0, 18, 58),
            ],
        },
        {
            "slug": "capsule_supplier_pressure",
            "supplier_id": "SDC-VD0914690A",
            "dst_node_id": "M-1430",
            "item_id": "item:042342",
            "label": "Crise capacitaire gellules pharma: capacite et fiabilite 042342 sous tension",
            "windows": variable_repeated_windows(
                horizon_days=horizon_days,
                start_offsets=[76, 150, 12, 286, 204],
                duration_days=[210, 95, 175, 150, 238],
            ),
            "events": [
                ("capacity", 0.16, 0, 38),
                ("availability", 0.24, 25, 45),
                ("external_capacity", 0.32, 0, 75),
                ("external_availability", 0.40, 0, 75),
                ("reliability", 0.28, 0, 0),
                ("lead_time_extra_days", 105.0, 18, 62),
                ("transport_cost", 3.2, 42, 62),
            ],
        },
        {
            "slug": "pfi_chain_pressure",
            "supplier_id": "SDC-1450",
            "dst_node_id": "M-1430",
            "item_id": "item:773474",
            "label": "Crise PFI interne: arbitrage inter-sites, release qualite et allocation 773474",
            "windows": variable_repeated_windows(
                horizon_days=horizon_days,
                start_offsets=[5, 184, 312, 132, 240],
                duration_days=[120, 196, 142, 252, 165],
            ),
            "events": [
                ("availability", 0.10, 0, 30),
                ("capacity", 0.22, 0, 20),
                ("external_capacity", 0.30, 0, 80),
                ("external_availability", 0.35, 0, 80),
                ("quality_delay", 75.0, 15, 58),
                ("lead_time_extra_days", 95.0, 0, 80),
                ("transport_cost", 2.2, 10, 20),
            ],
        },
    ]
    for wave in varied_supplier_waves:
        for year_idx, start, end in wave["windows"]:
            duration = max(1, end - start + 1)
            for risk_type, multiplier, start_shift, end_shift in wave["events"]:
                shifted_start = min(horizon_days - 1, start + int(start_shift))
                shifted_end = min(horizon_days - 1, end + int(end_shift))
                if shifted_end < shifted_start:
                    shifted_end = min(horizon_days - 1, shifted_start + max(7, duration // 2))
                add_lane_event(
                    slug=f"{wave['slug']}_w{year_idx}",
                    supplier_id=str(wave["supplier_id"]),
                    dst_node_id=str(wave["dst_node_id"]),
                    item_id=str(wave["item_id"]),
                    risk_type=risk_type,
                    multiplier=float(multiplier),
                    start_day=shifted_start,
                    end_day=shifted_end,
                    scenario_label=str(wave["label"]),
                )

    # 5b) Irrecoverable batch failures. These are intentionally punctual:
    # stock_writeoff represents rejected/quarantined stock destroyed once, not a
    # daily availability slowdown.
    stock_writeoff_pulses = [
        (
            "batch_reject_730384",
            "SDC-VD0508918A",
            "M-1430",
            "item:730384",
            "Rejet lot packaging 730384: stock fournisseur non liberable",
            [118, 413, 776, 1138, 1512],
            0.28,
        ),
        (
            "batch_reject_333362",
            "SDC-VD0525412A",
            "M-1430",
            "item:333362",
            "Rejet lot packaging 333362: non-conformite critique",
            [96, 388, 742, 1104, 1486],
            0.32,
        ),
        (
            "batch_reject_344135",
            "SDC-VD0993480A",
            "M-1430",
            "item:344135",
            "Rejet lot fermeture 344135: quarantaine definitive",
            [104, 352, 694, 1069, 1438],
            0.45,
        ),
        (
            "batch_reject_038005",
            "SDC-VD0520132A",
            "M-1430",
            "item:038005",
            "Rejet matiere 038005: destruction ou recontrole impossible",
            [165, 540, 903, 1268, 1615],
            0.22,
        ),
    ]
    for slug, supplier_id, dst_node_id, item_id, label, pulse_days, fraction in stock_writeoff_pulses:
        for idx, pulse_day in enumerate(pulse_days, start=1):
            if pulse_day >= horizon_days:
                continue
            add_lane_event(
                slug=f"{slug}_p{idx}",
                supplier_id=supplier_id,
                dst_node_id="",
                item_id=item_id,
                risk_type="stock_writeoff",
                multiplier=float(fraction),
                start_day=int(pulse_day),
                end_day=int(pulse_day),
                scenario_label=label,
                require_existing_lane=False,
            )

    # 6) Downstream cold-chain/logistics disruption. This is still an explicit
    # risk scenario, but it is not interpreted as a supplier criticality score:
    # it helps validate whether DC and customer arcs appear correctly when the
    # final product route is impacted.
    downstream_waves = [
        (
            "finished_good_dc_lane",
            "M-1430",
            "DC-1920",
            "item:268967",
            "Perturbation transport PF: lane usine vers DC-1920 sur 268967",
            [55, 228, 28, 309, 136],
            [84, 118, 72, 140, 96],
            [
                ("lead_time_extra_days", 32.0, 0, 0),
                ("transport_cost", 3.5, 0, 24),
                ("quality_delay", 18.0, 6, 24),
            ],
        ),
        (
            "finished_good_customer_lane",
            "DC-1920",
            "C-XXXXX",
            "item:268967",
            "Perturbation distribution client: congestion aval et livraisons tardives 268967",
            [84, 248, 43, 330, 165],
            [70, 96, 84, 118, 76],
            [
                ("lead_time_extra_days", 24.0, 0, 0),
                ("transport_cost", 3.0, 0, 18),
                ("availability", 0.35, 4, 28),
            ],
        ),
    ]
    for slug, supplier_id, dst_node_id, item_id, label, offsets, durations, risk_defs in downstream_waves:
        for year_idx, start, end in variable_repeated_windows(
            horizon_days=horizon_days,
            start_offsets=list(offsets),
            duration_days=list(durations),
        ):
            for risk_type, multiplier, start_shift, end_shift in risk_defs:
                add_lane_event(
                    slug=f"{slug}_w{year_idx}",
                    supplier_id=supplier_id,
                    dst_node_id=dst_node_id,
                    item_id=item_id,
                    risk_type=risk_type,
                    multiplier=float(multiplier),
                    start_day=min(horizon_days - 1, start + int(start_shift)),
                    end_day=min(horizon_days - 1, end + int(end_shift)),
                    scenario_label=label,
                )

    return sorted(events, key=lambda row: (int(row["start_day"]), str(row["supplier_id"]), str(row["risk_type"])))


def write_state_dependent_scenario_graph(
    *,
    source_graph: Path,
    output_graph: Path,
    source_scenario_id: str,
    target_scenario_id: str,
    horizon_days: int,
) -> None:
    data = load_json(source_graph)
    scenarios = data.get("scenarios") or []
    source_scenario = next((row for row in scenarios if str(row.get("id")) == source_scenario_id), None)
    if not isinstance(source_scenario, dict):
        source_scenario = scenarios[0] if scenarios else {"id": source_scenario_id}
    state_scenario = json.loads(json.dumps(source_scenario))
    state_scenario["id"] = target_scenario_id
    state_scenario["name"] = "State-dependent complet"
    state_scenario["description"] = (
        "Scenario de risques simules dynamiques: portefeuille de crises pharma "
        "calibre par sensibilite, puis aleas fournisseurs declenches par l'etat "
        "observe pendant la simulation."
    )
    injected_events = build_calibrated_pharma_supplier_risk_events(data, horizon_days=horizon_days)
    existing_events = [row for row in (state_scenario.get("supplier_risk_events") or []) if isinstance(row, dict)]
    state_scenario["supplier_risk_events"] = existing_events + injected_events
    data["scenarios"] = [row for row in scenarios if str((row or {}).get("id")) != target_scenario_id]
    data["scenarios"].append(state_scenario)
    meta = data.get("meta") if isinstance(data.get("meta"), dict) else {}
    meta["state_dependent_scenario_variant"] = {
        "source_graph": repo_rel(source_graph),
        "source_scenario_id": source_scenario_id,
        "target_scenario_id": target_scenario_id,
        "injected_supplier_risk_event_count": len(injected_events),
        "calibration_source": repo_rel(SUPPLIER_RISK_CAMPAIGN_CASES_CSV),
        "scenario_families": [
            "ouragan fournisseurs americains",
            "retards et quarantaine packaging pharma",
            "fiabilite composants haute cadence",
            "ralentissement liberation PFI 773474",
            "crises fournisseur pharma variees",
            "perturbations logistiques aval PF",
        ],
    }
    data["meta"] = meta
    write_json(output_graph, data)


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
    input_graph: Path | None = None,
    supplier_state_dependent_risks: bool = False,
    baseline_name: str = "active_mrp_physical",
) -> Path:
    input_graph = input_graph or ACTIVE_MRP_PHYSICAL_GRAPH_JSON
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
        "--opening-production-order-bom-issue-mode",
        ACTIVE_MRP_OPENING_PRODUCTION_ORDER_BOM_ISSUE_MODE,
        "--use-bom-demand-signal-for-mrp",
        "--mrp-demand-signal-source",
        "mps_lotified",
        "--mrp-demand-signal-smoothing-days",
        "7",
        "--no-mrp-static-fallback-for-propagated-pairs",
        *ACTIVE_MRP_PHYSICAL_INITIAL_STATE_ARGS,
    ]
    for node_id, item_id in ACTIVE_MRP_COMPONENT_TARGET_PAIRS:
        simulator_args.extend(
            [
                "--soft-safety-time-stock-target-factor-pair",
                f"{node_id},{item_id},{ACTIVE_MRP_COMPONENT_SAFETY_TARGET_FACTOR:g}",
            ]
        )
    for node_id, item_id in ACTIVE_MRP_STATIC_REQUIREMENT_PAIRS:
        simulator_args.extend(
            [
                "--mrp-static-requirement-pair",
                f"{node_id},{item_id}",
            ]
        )
    if skip_map:
        simulator_args.append("--skip-map")
    if skip_plots:
        simulator_args.append("--skip-plots")
    if supplier_state_dependent_risks:
        simulator_args.append("--supplier-state-dependent-risks")

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
    if supplier_state_dependent_risks:
        pipeline_cmd.append("--supplier-state-dependent-risks")

    if dry_run:
        print("[DRY-RUN] Active MRP physical baseline rebuild")
        print(f"[DRY-RUN] input_graph={repo_rel(input_graph)}")
        print(f"[DRY-RUN] output_dir={repo_rel(target_output_dir)}")
        print("[DRY-RUN] simulator command:")
        print(" ".join([sys.executable, repo_rel(SIMULATION_ENGINE_SCRIPT), *simulator_args]))
        return target_output_dir

    run_python(SIMULATION_ENGINE_SCRIPT, *simulator_args)
    build_component_stock_artifacts(input_graph=input_graph, output_dir=target_output_dir)
    build_finished_goods_stock_artifacts(input_graph=input_graph, output_dir=target_output_dir)
    build_component_stock_source_truth_reports(input_graph=input_graph, output_dir=target_output_dir)
    build_finished_goods_stock_source_truth_reports(output_dir=target_output_dir)
    manifest = {
        "baseline": baseline_name,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "input_graph": repo_rel(input_graph),
        "output_dir": repo_rel(target_output_dir),
        "scenario_id": scenario_id,
        "supplier_state_dependent_risks": bool(supplier_state_dependent_risks),
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
            "opening_production_order_bom_issue_mode": ACTIVE_MRP_OPENING_PRODUCTION_ORDER_BOM_ISSUE_MODE,
        },
    }
    write_json(target_output_dir / "run_manifest.json", manifest)
    export_run_package(output_dir=target_output_dir, input_graph=input_graph)
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
    refresh_input_graph: bool,
    pf_service_target: float | None,
    build_state_dependent_risk_scenario: bool,
    with_montecarlo: bool,
    montecarlo_runs: int,
    montecarlo_probe_runs: int,
    montecarlo_profiles: str,
    montecarlo_final_profile: str,
    montecarlo_seed: int,
    montecarlo_trajectory_max_points: int,
    montecarlo_trajectory_display_runs: int,
    montecarlo_workers: int,
) -> Path:
    started_at = datetime.now(timezone.utc).isoformat()
    if refresh_input_graph and not dry_run:
        refresh_active_mrp_physical_graph(
            scenario_id=scenario_id,
            days=days,
            pf_service_target=pf_service_target,
        )

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

    simulated_risk_output_dir: Path | None = None
    if build_state_dependent_risk_scenario:
        info_line("Building companion state-dependent risk scenario")
        scenario_graph = target_output_dir / "scenario_graphs" / "state_dependent_full.json"
        state_scenario_id = "scn:STATE_DEPENDENT_FULL"
        write_state_dependent_scenario_graph(
            source_graph=ACTIVE_MRP_PHYSICAL_GRAPH_JSON,
            output_graph=scenario_graph,
            source_scenario_id=scenario_id,
            target_scenario_id=state_scenario_id,
            horizon_days=days,
        )
        simulated_risk_output_dir = run_active_mrp_physical(
            output_dir=target_output_dir / "scenario_runs" / "state_dependent_full",
            scenario_id=state_scenario_id,
            days=days,
            output_profile=output_profile,
            overwrite=True,
            dry_run=False,
            skip_map=True,
            skip_plots=True,
            input_graph=scenario_graph,
            supplier_state_dependent_risks=True,
            baseline_name="state_dependent_full",
        )
        manifest_path = target_output_dir / "run_manifest.json"
        manifest = load_json(manifest_path) if manifest_path.exists() else {}
        companion_runs = manifest.get("companion_runs") if isinstance(manifest.get("companion_runs"), dict) else {}
        companion_runs["state_dependent_full"] = {
            "output_dir": "scenario_runs/state_dependent_full",
            "scenario_id": state_scenario_id,
            "label": "State-dependent complet",
            "role": "primary_simulated_risk",
        }
        manifest["companion_runs"] = companion_runs
        write_json(manifest_path, manifest)

    montecarlo_summary_json: Path | None = None
    if with_montecarlo:
        info_line("Running adaptive robust Monte Carlo suite for the current run")
        montecarlo_summary_json = run_robust_montecarlo_for_result(
            output_dir=target_output_dir,
            runs=montecarlo_runs,
            probe_runs=montecarlo_probe_runs,
            profiles=montecarlo_profiles,
            final_profile=montecarlo_final_profile,
            days=days,
            seed=montecarlo_seed,
            trajectory_max_points=montecarlo_trajectory_max_points,
            trajectory_display_runs=montecarlo_trajectory_display_runs,
            workers=montecarlo_workers,
        )
        manifest_path = target_output_dir / "run_manifest.json"
        manifest = load_json(manifest_path) if manifest_path.exists() else {}
        manifest["montecarlo"] = {
            "output_dir": "montecarlo",
            "suite_summary_json": "montecarlo/montecarlo_suite_summary.json",
            "selected_summary_json": "montecarlo/selected/montecarlo_summary.json",
            "selected_trajectories_json": "montecarlo/selected/montecarlo_trajectories.json",
            "runs": montecarlo_runs,
            "probe_runs": montecarlo_probe_runs,
            "profiles": montecarlo_profiles,
            "final_profile": montecarlo_final_profile,
            "seed": montecarlo_seed,
            "workers": montecarlo_workers,
        }
        write_json(manifest_path, manifest)

    info_line("Building supplier local criticality artifacts for the current run")
    build_supplier_local_criticality_artifacts(
        input_graph=ACTIVE_MRP_PHYSICAL_GRAPH_JSON,
        output_dir=target_output_dir,
    )

    supplier_criticality_dir = target_output_dir / "supplier_criticality"
    info_line("Rebuilding supplier criticality for the current run")
    build_supplier_criticality(sim_result_dir=target_output_dir, output_dir=supplier_criticality_dir)

    info_line("Building final standalone map with current-run supplier criticality")
    build_map_for_simulation_result(
        input_graph=ACTIVE_MRP_PHYSICAL_GRAPH_JSON,
        output_dir=target_output_dir,
        supplier_criticality_dir=supplier_criticality_dir,
        simulated_risk_output_dir=simulated_risk_output_dir,
        montecarlo_summary_json=montecarlo_summary_json,
    )
    map_path = find_generated_map(target_output_dir)

    info_line("Exporting generic simulation run package")
    generic_run_dir = export_run_package(
        output_dir=target_output_dir,
        input_graph=ACTIVE_MRP_PHYSICAL_GRAPH_JSON,
        map_html=map_path,
        extra_metadata={
            "pipeline_command": "rebuild-active",
            "supplier_criticality_dir": repo_rel(supplier_criticality_dir),
            "simulated_risk_output_dir": repo_rel(simulated_risk_output_dir) if simulated_risk_output_dir else "",
            "montecarlo_summary_json": repo_rel(montecarlo_summary_json) if montecarlo_summary_json else "",
        },
    )
    ok_line(f"Generic run package: {generic_run_dir.resolve()}")

    validations: list[dict[str, Any]] = []
    if not skip_validation:
        info_line("Output validations")
        validations = validate_active_run_outputs(
            target_output_dir,
            scenario_id=scenario_id,
            days=days,
            output_profile=output_profile,
            max_map_mb=max_map_mb,
            montecarlo_summary_json=montecarlo_summary_json,
            montecarlo_expected_runs=montecarlo_runs if with_montecarlo else None,
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

    data_profile = sub.add_parser(
        "data-profile",
        help="Profile canonical source files and write etudecas/data/reports/source_data_profile.*.",
    )
    data_profile.add_argument(
        "--output-json",
        default=repo_rel(DATA_REPORTS_DIR / "source_data_profile.json"),
        help="Output JSON report path.",
    )
    data_profile.add_argument(
        "--output-md",
        default=repo_rel(DATA_REPORTS_DIR / "source_data_profile.md"),
        help="Output Markdown report path.",
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
    rebuild_active.add_argument(
        "--refresh-input-graph",
        action="store_true",
        help="Rebuild the retained active simulation graph from data/source before running the 5y simulation.",
    )
    rebuild_active.add_argument(
        "--pf-service-target",
        type=float,
        default=None,
        help="Override finished-product service target while refreshing the input graph, e.g. 1.0 for nominal 100%%.",
    )
    rebuild_active.add_argument(
        "--state-dependent-risk-scenario",
        action=argparse.BooleanOptionalAction,
        default=True,
        help=(
            "Build a companion scn:STATE_DEPENDENT_FULL run and use it as the primary "
            "Risques simules payload. Enabled by default for operational maps."
        ),
    )
    rebuild_active.add_argument(
        "--with-montecarlo",
        action="store_true",
        help="Run the adaptive robust Monte Carlo suite for the current run before building the map.",
    )
    rebuild_active.add_argument(
        "--montecarlo-runs",
        type=int,
        default=200,
        help="Final stochastic runs for the selected Monte Carlo profile.",
    )
    rebuild_active.add_argument(
        "--montecarlo-probe-runs",
        type=int,
        default=8,
        help="Screening runs per profile before selecting the final Monte Carlo profile.",
    )
    rebuild_active.add_argument(
        "--montecarlo-profiles",
        default="workshop,risk_probe,stress_probe,breakpoint_probe",
        help="Comma-separated profiles probed by the adaptive Monte Carlo suite.",
    )
    rebuild_active.add_argument(
        "--montecarlo-final-profile",
        default="auto",
        help="auto or explicit profile used for the final Monte Carlo run.",
    )
    rebuild_active.add_argument("--montecarlo-seed", type=int, default=42)
    rebuild_active.add_argument("--montecarlo-trajectory-max-points", type=int, default=730)
    rebuild_active.add_argument("--montecarlo-trajectory-display-runs", type=int, default=60)
    rebuild_active.add_argument("--montecarlo-workers", type=int, default=4)

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
    prepare.add_argument("--pf-service-target", type=float, default=None)

    reference = sub.add_parser("reference", help="Rebuild the active 1y reference baseline from the graph pipeline.")
    reference.add_argument("--simulation-days", type=int, default=365, help="Prep horizon written into the working graph.")
    reference.add_argument("--days", type=int, default=365, help="Final 1y measured horizon.")
    reference.add_argument("--scenario-id", default="scn:BASE")
    reference.add_argument("--pf-service-target", type=float, default=None)
    reference.add_argument("--skip-map", action="store_true")
    reference.add_argument("--skip-plots", action="store_true")

    all_cmd = sub.add_parser("all", help="Run the full active pipeline and optionally the 5y simulation.")
    all_cmd.add_argument("--simulation-days", type=int, default=365, help="Prep horizon written into the working graph.")
    all_cmd.add_argument("--days", type=int, default=365, help="Final 1y measured horizon.")
    all_cmd.add_argument("--scenario-id", default="scn:BASE")
    all_cmd.add_argument("--pf-service-target", type=float, default=None)
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

    export_run = sub.add_parser("export-run", help="Export a generic run package from an existing simulation result.")
    export_run.add_argument("--output-dir", required=True, help="Existing simulation result directory.")
    export_run.add_argument("--input-graph", default=repo_rel(ACTIVE_MRP_PHYSICAL_GRAPH_JSON))
    export_run.add_argument("--package-dir", default="", help="Defaults to <output-dir>/run.")
    export_run.add_argument("--map-html", default="", help="Optional generated map HTML path.")

    validate_run = sub.add_parser("validate-run", help="Validate a generic run package.")
    validate_run.add_argument("--package-dir", required=True)

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
        "--supplier-state-dependent-risks",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Enable state-dependent supplier risk triggers for this single simulation run.",
    )
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
    if args.command == "data-profile":
        run_python(
            SOURCE_PROFILE_SCRIPT,
            "--output-json",
            repo_rel(resolve_repo_path(Path(args.output_json))),
            "--output-md",
            repo_rel(resolve_repo_path(Path(args.output_md))),
        )
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
            refresh_input_graph=args.refresh_input_graph,
            pf_service_target=args.pf_service_target,
            build_state_dependent_risk_scenario=args.state_dependent_risk_scenario,
            with_montecarlo=args.with_montecarlo,
            montecarlo_runs=args.montecarlo_runs,
            montecarlo_probe_runs=args.montecarlo_probe_runs,
            montecarlo_profiles=args.montecarlo_profiles,
            montecarlo_final_profile=args.montecarlo_final_profile,
            montecarlo_seed=args.montecarlo_seed,
            montecarlo_trajectory_max_points=args.montecarlo_trajectory_max_points,
            montecarlo_trajectory_display_runs=args.montecarlo_trajectory_display_runs,
            montecarlo_workers=args.montecarlo_workers,
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
        prepare_reference_graph(simulation_days=args.simulation_days, pf_service_target=args.pf_service_target)
        return
    if args.command == "reference":
        build_knowledge_graph()
        prepare_reference_graph(simulation_days=args.simulation_days, pf_service_target=args.pf_service_target)
        build_reference_baseline(
            scenario_id=args.scenario_id,
            days=args.days,
            skip_map=args.skip_map,
            skip_plots=args.skip_plots,
            pf_service_target=args.pf_service_target,
        )
        return
    if args.command == "all":
        build_knowledge_graph()
        prepare_reference_graph(simulation_days=args.simulation_days, pf_service_target=args.pf_service_target)
        build_reference_baseline(
            scenario_id=args.scenario_id,
            days=args.days,
            skip_map=args.skip_map,
            skip_plots=args.skip_plots,
            pf_service_target=args.pf_service_target,
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
    if args.command == "export-run":
        output_dir = resolve_repo_path(Path(args.output_dir))
        package_dir = export_run_package(
            output_dir=output_dir,
            input_graph=resolve_repo_path(Path(args.input_graph)) if args.input_graph else None,
            package_dir=resolve_repo_path(Path(args.package_dir)) if args.package_dir else None,
            map_html=resolve_repo_path(Path(args.map_html)) if args.map_html else find_generated_map(output_dir),
            extra_metadata={"pipeline_command": "export-run"},
        )
        ok_line(f"Generic run package: {package_dir.resolve()}")
        validations = validate_run_package(package_dir)
        print_preflight(validations)
        assert_validations_ok(validations)
        return
    if args.command == "validate-run":
        validations = validate_run_package(resolve_repo_path(Path(args.package_dir)))
        print_preflight(validations)
        assert_validations_ok(validations)
        ok_line("Generic run package checks passed.")
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
            supplier_state_dependent_risks=args.supplier_state_dependent_risks,
        )
        return
    raise ValueError(f"Unsupported command: {args.command}")


if __name__ == "__main__":
    main()
