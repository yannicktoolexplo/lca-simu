#!/usr/bin/env python3
"""Adaptive Monte Carlo suite for the active supply simulation.

The base runner executes one uncertainty profile. This wrapper probes several
profiles, measures whether they actually move operational KPI, then runs the
best profile with compact trajectories for the map.
"""

from __future__ import annotations

import argparse
import csv
import json
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

RUNNER = Path("etudecas/simulation/montecarlo/run_montecarlo_analysis.py")
DEFAULT_PROFILES = ("workshop", "risk_probe", "stress_probe", "portfolio_probe", "breakpoint_probe")
PROFILE_RANK = {
    "workshop": 0,
    "risk_probe": 1,
    "stress_probe": 2,
    "portfolio_probe": 2,
    "breakpoint_probe": 3,
    "legacy": 1,
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run an adaptive robust Monte Carlo suite.")
    parser.add_argument("--manifest-json", default="", help="Run manifest from the baseline to perturb.")
    parser.add_argument("--input", default="", help="Fallback graph JSON when no manifest is supplied.")
    parser.add_argument("--scenario-id", default="", help="Fallback scenario id when no manifest is supplied.")
    parser.add_argument("--output-dir", required=True, help="Suite output directory.")
    parser.add_argument(
        "--days",
        type=int,
        default=0,
        help="Simulation horizon override. 0 keeps the horizon from the manifest/scenario.",
    )
    parser.add_argument("--seed", type=int, default=42, help="Base random seed.")
    parser.add_argument(
        "--profiles",
        default=",".join(DEFAULT_PROFILES),
        help="Comma-separated profiles probed before the final run.",
    )
    parser.add_argument(
        "--final-profile",
        default="auto",
        help="auto or one explicit profile. auto selects the most informative non-catastrophic profile.",
    )
    parser.add_argument(
        "--sensitivity-calibration-json",
        default="",
        help="Optional calibration JSON from supplier sensitivity. Used as a minimum profile floor.",
    )
    parser.add_argument("--probe-runs", type=int, default=8, help="Runs per profile for the screening step.")
    parser.add_argument("--final-runs", type=int, default=60, help="Runs for the selected final profile.")
    parser.add_argument(
        "--trajectory-max-points",
        type=int,
        default=730,
        help="Maximum points per trajectory written for the map. 0 keeps all days.",
    )
    parser.add_argument(
        "--trajectory-display-runs",
        type=int,
        default=60,
        help="Maximum individual trajectories kept for display. 0 keeps every run.",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=1,
        help="Parallel simulation workers passed to the base Monte Carlo runner.",
    )
    parser.add_argument(
        "--keep-profile-artifacts",
        action="store_true",
        help="Ask the base runner to keep full per-run artifacts. Heavy; normally disabled.",
    )
    parser.add_argument(
        "--simulator-extra-arg",
        action="append",
        default=[],
        help="Additional token passed to the base Monte Carlo runner. Repeat once per token.",
    )
    return parser.parse_args()


def repo_rel(path: Path) -> str:
    try:
        return str(path.resolve(strict=False).relative_to(REPO_ROOT.resolve(strict=False))).replace("\\", "/")
    except ValueError:
        return str(path)


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def load_calibration(path: str) -> dict[str, Any]:
    if not path:
        return {}
    candidate = Path(path)
    if not candidate.exists():
        candidate = REPO_ROOT / candidate
    if not candidate.exists():
        return {"status": "missing", "source_json": path}
    try:
        calibration = load_json(candidate)
    except Exception as exc:
        return {"status": "invalid", "source_json": str(candidate), "reason": str(exc)}
    if isinstance(calibration, dict):
        calibration["source_json"] = str(candidate)
        return calibration
    return {"status": "invalid", "source_json": str(candidate)}


def profile_floor(calibration: dict[str, Any]) -> str:
    profile = str(calibration.get("recommended_profile") or "").strip()
    return profile if profile in PROFILE_RANK else ""


def apply_profile_floor(profiles: list[str], floor: str) -> list[str]:
    if not floor:
        return profiles
    floor_rank = PROFILE_RANK.get(floor, 0)
    filtered = [p for p in profiles if PROFILE_RANK.get(p, 0) >= floor_rank]
    if floor not in filtered:
        filtered.insert(0, floor)
    return filtered or [floor]


def to_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def percentile(values: list[float], p: float) -> float | None:
    clean = sorted(v for v in values if isinstance(v, (int, float)))
    if not clean:
        return None
    if len(clean) == 1:
        return clean[0]
    pos = max(0.0, min(1.0, p)) * (len(clean) - 1)
    lo = int(pos)
    hi = min(lo + 1, len(clean) - 1)
    frac = pos - lo
    return clean[lo] * (1.0 - frac) + clean[hi] * frac


def csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def numeric_series(rows: list[dict[str, str]], column: str) -> list[float]:
    values: list[float] = []
    for row in rows:
        if str(row.get("status") or "ok") != "ok":
            continue
        if str(row.get("is_baseline") or "").lower() in {"true", "1"}:
            continue
        value = to_float(row.get(column), float("nan"))
        if value == value:
            values.append(value)
    return values


def baseline_row(rows: list[dict[str, str]]) -> dict[str, str]:
    for row in rows:
        if str(row.get("is_baseline") or "").lower() in {"true", "1"}:
            return row
    return rows[0] if rows else {}


def clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))


def assess_profile(samples_csv: Path, profile: str) -> dict[str, Any]:
    """Score a profile from its sample CSV.

    The target is not a historical probability estimate. We want enough spread
    to expose weak points, without selecting a profile that simply destroys the
    whole network in most runs.
    """

    rows = csv_rows(samples_csv)
    baseline = baseline_row(rows)
    ok_rows = [r for r in rows if str(r.get("status") or "ok") == "ok"]
    stochastic_rows = [
        r for r in ok_rows if str(r.get("is_baseline") or "").lower() not in {"true", "1"}
    ]
    failed = [r for r in rows if str(r.get("status") or "ok") != "ok"]
    fill = numeric_series(rows, "kpi::fill_rate")
    backlog = numeric_series(rows, "kpi::ending_backlog")
    cost = numeric_series(rows, "kpi::total_cost")
    binding = numeric_series(rows, "kpi::total_supplier_capacity_binding_qty")
    demand = numeric_series(rows, "kpi::total_demand")

    base_fill = to_float(baseline.get("kpi::fill_rate"), 1.0)
    base_cost = max(1.0, to_float(baseline.get("kpi::total_cost"), 1.0))
    demand_ref = max(1.0, percentile(demand, 0.50) or to_float(baseline.get("kpi::total_demand"), 1.0))

    fill_p05 = percentile(fill, 0.05)
    fill_p50 = percentile(fill, 0.50)
    fill_p95 = percentile(fill, 0.95)
    backlog_p95 = percentile(backlog, 0.95) or 0.0
    cost_p05 = percentile(cost, 0.05) or base_cost
    cost_p95 = percentile(cost, 0.95) or base_cost
    binding_p95 = percentile(binding, 0.95) or 0.0

    fill_spread = max(0.0, (fill_p95 or base_fill) - (fill_p05 or base_fill))
    service_loss_tail = max(0.0, base_fill - (fill_p05 if fill_p05 is not None else base_fill))
    service_loss_median = max(0.0, base_fill - (fill_p50 if fill_p50 is not None else base_fill))
    backlog_ratio = backlog_p95 / demand_ref
    cost_spread_ratio = max(0.0, cost_p95 - cost_p05) / base_cost
    binding_ratio = binding_p95 / demand_ref
    failure_ratio = len(failed) / max(1, len(rows))
    degraded_99_ratio = (
        sum(1 for value in fill if value < 0.99) / float(len(fill))
        if fill
        else 0.0
    )

    variation_score = (
        0.30 * clamp01(service_loss_tail / 0.08)
        + 0.20 * clamp01(backlog_ratio / 0.03)
        + 0.20 * clamp01(cost_spread_ratio / 0.20)
        + 0.15 * clamp01(binding_ratio / 0.05)
        + 0.10 * clamp01(fill_spread / 0.08)
        + 0.05 * clamp01(failure_ratio / 0.20)
    )

    too_weak = (
        service_loss_tail < 0.002
        and backlog_ratio < 0.0002
        and binding_ratio < 0.001
        and cost_spread_ratio < 0.025
    )
    if profile == "portfolio_probe":
        # Portfolio probing deliberately mixes near-nominal, cost-only and
        # severe supplier scenarios. A bad tail is expected; what would make it
        # unusable is most runs failing or the median network being destroyed.
        catastrophic = (
            failure_ratio > 0.25
            or service_loss_median > 0.12
            or ((fill_p50 or 1.0) < 0.88)
            or degraded_99_ratio > 0.45
        )
    else:
        catastrophic = (
            failure_ratio > 0.25
            or service_loss_median > 0.12
            or ((fill_p50 or 1.0) < 0.88)
            or backlog_ratio > 0.20
        )
    target_distance = abs(variation_score - 0.38)
    status = "useful"
    if too_weak:
        status = "too_weak"
    elif catastrophic:
        status = "too_extreme"

    return {
        "profile": profile,
        "status": status,
        "sample_count": len(stochastic_rows),
        "failed_count": len(failed),
        "variation_score": round(variation_score, 6),
        "target_distance": round(target_distance, 6),
        "baseline_fill_rate": round(base_fill, 6),
        "fill_rate_p05": round(fill_p05, 6) if fill_p05 is not None else None,
        "fill_rate_p50": round(fill_p50, 6) if fill_p50 is not None else None,
        "fill_rate_p95": round(fill_p95, 6) if fill_p95 is not None else None,
        "service_loss_tail": round(service_loss_tail, 6),
        "service_loss_median": round(service_loss_median, 6),
        "backlog_p95": round(backlog_p95, 6),
        "backlog_ratio_p95": round(backlog_ratio, 8),
        "cost_spread_ratio_p05_p95": round(cost_spread_ratio, 6),
        "supplier_capacity_binding_ratio_p95": round(binding_ratio, 8),
        "failure_ratio": round(failure_ratio, 6),
        "fill_rate_below_99_ratio": round(degraded_99_ratio, 6),
        "samples_csv": repo_rel(samples_csv),
    }


def choose_profile(assessments: list[dict[str, Any]], fallback: str) -> str:
    useful = [a for a in assessments if a.get("status") == "useful"]
    if useful:
        return str(min(useful, key=lambda a: (to_float(a.get("target_distance")), -to_float(a.get("variation_score"))))["profile"])
    non_extreme = [a for a in assessments if a.get("status") != "too_extreme"]
    if non_extreme:
        return str(max(non_extreme, key=lambda a: to_float(a.get("variation_score")))["profile"])
    if assessments:
        return str(min(assessments, key=lambda a: to_float(a.get("variation_score")))["profile"])
    return fallback


def run_base_montecarlo(
    *,
    output_dir: Path,
    profile: str,
    runs: int,
    seed: int,
    days: int,
    manifest_json: str,
    input_json: str,
    scenario_id: str,
    save_trajectories: bool,
    trajectory_max_points: int,
    trajectory_display_runs: int,
    workers: int,
    keep_run_artifacts: bool,
    simulator_extra_args: list[str],
    sensitivity_calibration_json: str,
) -> None:
    cmd = [
        sys.executable,
        repo_rel(RUNNER),
        "--output-dir",
        repo_rel(output_dir),
        "--runs",
        str(max(0, int(runs))),
        "--seed",
        str(seed),
        "--days",
        str(days),
        "--uncertainty-profile",
        profile,
        "--workers",
        str(max(1, int(workers))),
    ]
    if manifest_json:
        cmd.extend(["--manifest-json", manifest_json])
    elif input_json:
        cmd.extend(["--input", input_json])
        if scenario_id:
            cmd.extend(["--scenario-id", scenario_id])
    if save_trajectories:
        cmd.append("--save-trajectories")
        cmd.extend(["--trajectory-max-points", str(trajectory_max_points)])
        cmd.extend(["--trajectory-display-runs", str(trajectory_display_runs)])
    if sensitivity_calibration_json:
        cmd.extend(["--sensitivity-calibration-json", sensitivity_calibration_json])
    if keep_run_artifacts:
        cmd.append("--keep-run-artifacts")
    for token in simulator_extra_args:
        cmd.extend(["--simulator-extra-arg", str(token)])
    subprocess.run(cmd, check=True, cwd=REPO_ROOT)


def copy_selected_artifacts(source_dir: Path, selected_dir: Path) -> None:
    selected_dir.mkdir(parents=True, exist_ok=True)
    for name in [
        "montecarlo_summary.json",
        "montecarlo_samples.csv",
        "montecarlo_trajectories.json",
        "montecarlo_paired_propagation.json",
        "montecarlo_temporal_propagation.json",
        "variance_decomposition.json",
        "montecarlo_cost_diagnostics.json",
        "montecarlo_report.md",
        "montecarlo_failed_runs.csv",
    ]:
        src = source_dir / name
        if src.exists():
            shutil.copy2(src, selected_dir / name)


def main() -> None:
    args = parse_args()
    output_dir = Path(args.output_dir)
    probes_dir = output_dir / "profile_probes"
    final_dir = output_dir / "selected"
    output_dir.mkdir(parents=True, exist_ok=True)

    profiles = [p.strip() for p in str(args.profiles or "").split(",") if p.strip()]
    if not profiles:
        profiles = list(DEFAULT_PROFILES)
    calibration = load_calibration(args.sensitivity_calibration_json)
    calibration_floor = profile_floor(calibration)
    explicit_profile = args.final_profile if args.final_profile != "auto" else ""
    if explicit_profile and explicit_profile not in profiles:
        profiles.append(explicit_profile)
    if not explicit_profile:
        profiles = apply_profile_floor(profiles, calibration_floor)

    assessments: list[dict[str, Any]] = []
    if args.final_profile == "auto" and args.probe_runs > 0:
        for idx, profile in enumerate(profiles):
            probe_dir = probes_dir / profile
            print(f"[PROBE] {profile} ({idx + 1}/{len(profiles)})", flush=True)
            run_base_montecarlo(
                output_dir=probe_dir,
                profile=profile,
                runs=args.probe_runs,
                seed=args.seed + idx * 1009,
                days=args.days,
                manifest_json=args.manifest_json,
                input_json=args.input,
                scenario_id=args.scenario_id,
                save_trajectories=False,
                trajectory_max_points=args.trajectory_max_points,
                trajectory_display_runs=args.trajectory_display_runs,
                workers=args.workers,
                keep_run_artifacts=args.keep_profile_artifacts,
                simulator_extra_args=args.simulator_extra_arg,
                sensitivity_calibration_json=args.sensitivity_calibration_json,
            )
            assessments.append(assess_profile(probe_dir / "montecarlo_samples.csv", profile))
    selected_profile = explicit_profile or choose_profile(assessments, "stress_probe")
    selected_index = profiles.index(selected_profile) if selected_profile in profiles else 0

    print(f"[FINAL] selected profile={selected_profile} runs={args.final_runs}", flush=True)
    run_base_montecarlo(
        output_dir=final_dir,
        profile=selected_profile,
        runs=args.final_runs,
        seed=args.seed + 100_000 + selected_index * 1009,
        days=args.days,
        manifest_json=args.manifest_json,
        input_json=args.input,
        scenario_id=args.scenario_id,
        save_trajectories=True,
        trajectory_max_points=args.trajectory_max_points,
        trajectory_display_runs=args.trajectory_display_runs,
        workers=args.workers,
        keep_run_artifacts=args.keep_profile_artifacts,
        simulator_extra_args=args.simulator_extra_arg,
        sensitivity_calibration_json=args.sensitivity_calibration_json,
    )
    final_assessment = assess_profile(final_dir / "montecarlo_samples.csv", selected_profile)
    if not assessments:
        assessments = [final_assessment]

    suite_summary = {
        "schema_version": "etudecas.robust_montecarlo_suite.v1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "manifest_json": args.manifest_json,
        "input": args.input,
        "scenario_id": args.scenario_id,
        "days": args.days,
        "seed": args.seed,
        "profiles_probed": profiles,
        "sensitivity_calibration": {
            "source_json": calibration.get("source_json", args.sensitivity_calibration_json),
            "status": calibration.get("status", ""),
            "recommended_profile": calibration.get("recommended_profile", ""),
            "sensitivity_strength_score": calibration.get("sensitivity_strength_score"),
            "reason": calibration.get("reason", ""),
        },
        "probe_runs": args.probe_runs,
        "final_runs": args.final_runs,
        "workers": args.workers,
        "selected_profile": selected_profile,
        "selected_summary_json": repo_rel(final_dir / "montecarlo_summary.json"),
        "selected_trajectories_json": repo_rel(final_dir / "montecarlo_trajectories.json"),
        "selected_paired_propagation_json": repo_rel(final_dir / "montecarlo_paired_propagation.json"),
        "selected_temporal_propagation_json": repo_rel(final_dir / "montecarlo_temporal_propagation.json"),
        "selected_variance_decomposition_json": repo_rel(final_dir / "variance_decomposition.json"),
        "selected_cost_diagnostics_json": repo_rel(final_dir / "montecarlo_cost_diagnostics.json"),
        "profile_assessments": assessments,
        "final_assessment": final_assessment,
        "selection_rule": (
            "Prefer useful profiles near variation_score 0.38; if all are weak use the strongest "
            "non-extreme profile; if all are extreme use the least extreme profile."
        ),
    }
    write_json(output_dir / "montecarlo_suite_summary.json", suite_summary)

    report = [
        "# Robust Monte Carlo Suite",
        "",
        f"- Selected profile: **{selected_profile}**",
        f"- Final runs: **{args.final_runs}**",
        f"- Workers: **{args.workers}**",
        f"- Selected summary: `{repo_rel(final_dir / 'montecarlo_summary.json')}`",
        f"- Selected trajectories: `{repo_rel(final_dir / 'montecarlo_trajectories.json')}`",
        f"- Paired propagation: `{repo_rel(final_dir / 'montecarlo_paired_propagation.json')}`",
        f"- Temporal propagation: `{repo_rel(final_dir / 'montecarlo_temporal_propagation.json')}`",
        f"- Variance decomposition: `{repo_rel(final_dir / 'variance_decomposition.json')}`",
        f"- Cost diagnostics: `{repo_rel(final_dir / 'montecarlo_cost_diagnostics.json')}`",
        "",
        "## Profile assessments",
        "",
        "| Profile | Status | Score | Fill p05 | Backlog p95 ratio | Cost spread | Binding ratio |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in assessments:
        report.append(
            "| {profile} | {status} | {variation_score:.3f} | {fill_rate_p05} | {backlog_ratio_p95} | "
            "{cost_spread_ratio_p05_p95} | {supplier_capacity_binding_ratio_p95} |".format(**row)
        )
    (output_dir / "montecarlo_suite_report.md").write_text("\n".join(report) + "\n", encoding="utf-8")
    print(f"[OK] Robust suite summary: {(output_dir / 'montecarlo_suite_summary.json').resolve()}", flush=True)
    print(f"[OK] Selected Monte Carlo: {final_dir.resolve()}", flush=True)


if __name__ == "__main__":
    main()
