#!/usr/bin/env python3
"""Run controlled paired uncertainty propagation from an existing MC campaign."""

from __future__ import annotations

import argparse
import concurrent.futures
import csv
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from etudecas.simulation.analysis_batch_common import load_json, write_json
from etudecas.simulation.montecarlo.run_montecarlo_analysis import execute_run_spec
from etudecas.simulation.uncertainty.paired_propagation import (
    build_paired_propagation_payload,
    build_paired_run_specs,
    default_business_factor_ranges,
    is_economic_factor,
    select_background_rows,
    select_paired_factors,
    select_supplier_item_factors,
)
from etudecas.simulation.uncertainty.temporal_propagation import (
    build_temporal_propagation,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run paired +/- uncertainty experiments from an existing Monte Carlo result.")
    parser.add_argument("--summary-json", required=True, help="Existing montecarlo_summary.json.")
    parser.add_argument("--factor-count", type=int, default=8)
    parser.add_argument("--background-count", type=int, default=20)
    parser.add_argument("--input-uncertainty", type=float, default=0.20)
    parser.add_argument("--workers", type=int, default=0, help="0 reuses the worker count recorded in the MC summary.")
    parser.add_argument("--trajectory-max-points", type=int, default=730)
    parser.add_argument(
        "--lot-events-csv",
        help="Optional nominal production_lot_events.csv used to identify lots exposed in time.",
    )
    return parser.parse_args()


def resolve_repo_path(value: Any) -> Path:
    candidate = Path(str(value or ""))
    if candidate.is_absolute():
        return candidate
    return REPO_ROOT / candidate


def read_rows(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def main() -> None:
    args = parse_args()
    summary_path = resolve_repo_path(args.summary_json)
    summary = load_json(summary_path)
    samples_path = summary_path.with_name("montecarlo_samples.csv")
    if not samples_path.exists():
        raise FileNotFoundError(f"Monte Carlo samples not found: {samples_path}")
    rows = read_rows(samples_path)
    base_data = load_json(resolve_repo_path(summary.get("input")))
    factor_count = max(0, int(args.factor_count))
    pair_target = max(0, factor_count - min(2, factor_count // 4))
    factors = select_supplier_item_factors(
        base_data,
        summary,
        rows,
        limit=pair_target,
    )
    ranked_fallback = select_paired_factors(
        summary,
        rows,
        limit=max(factor_count * 2, factor_count),
    )
    for factor in [
        *[value for value in ranked_fallback if is_economic_factor(value)],
        *ranked_fallback,
    ]:
        if len(factors) >= factor_count:
            break
        if factor not in factors:
            factors.append(factor)
    backgrounds = select_background_rows(rows, count=max(0, int(args.background_count)))
    specs = build_paired_run_specs(
        factors=factors,
        backgrounds=backgrounds,
        uncertainty=max(0.0, float(args.input_uncertainty)),
        factor_ranges=default_business_factor_ranges(factors),
        range_rows=rows,
        reuse_background_centers=True,
    )
    if not specs:
        raise RuntimeError("No paired run specification could be built from the selected Monte Carlo campaign.")

    run_script = resolve_repo_path(summary.get("run_script") or "etudecas/simulation/engine/run_first_simulation.py")
    scenario_id = str(summary.get("scenario_id") or "scn:BASE")
    days = int(summary.get("days_override") or 0)
    simulator_extra_args = [str(token) for token in (summary.get("simulator_extra_args") or [])]
    worker_count = max(1, min(int(args.workers or summary.get("workers") or 1), len(specs)))
    print(
        f"[PAIRED] factors={len(factors)} backgrounds={len(backgrounds)} "
        f"runs={len(specs)} workers={worker_count}",
        flush=True,
    )

    results: dict[int, dict[str, Any]] = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=worker_count) as executor:
        future_to_spec = {
            executor.submit(
                execute_run_spec,
                spec,
                base_data=base_data,
                scenario_id=scenario_id,
                run_script=run_script,
                days=days,
                simulator_extra_args=simulator_extra_args,
                keep_run_artifacts=False,
                runs_dir=summary_path.parent / "paired_runs",
                save_trajectories=True,
                trajectory_max_points=max(0, int(args.trajectory_max_points)),
            ): spec
            for spec in specs
        }
        for completed, future in enumerate(concurrent.futures.as_completed(future_to_spec), start=1):
            spec = future_to_spec[future]
            try:
                result = future.result()
            except Exception as exc:
                failed_row = dict(spec["row"])
                failed_row["status"] = "failed"
                failed_row["error"] = str(exc)
                result = {"index": int(spec["index"]), "row": failed_row, "trajectory_run": None}
            results[int(spec["index"])] = result
            print(
                f"[PAIRED DONE] {completed:03d}/{len(specs):03d} "
                f"{spec['run_id']} status={result['row'].get('status', 'unknown')}",
                flush=True,
            )

    trajectories: list[dict[str, Any]] = []
    failed = 0
    for spec in specs:
        result = results.get(int(spec["index"]))
        if not result or result["row"].get("status") != "ok" or not result.get("trajectory_run"):
            failed += 1
            continue
        trajectory = result["trajectory_run"]
        trajectory["paired_metadata"] = dict(spec.get("paired_metadata") or {})
        trajectories.append(trajectory)

    payload = build_paired_propagation_payload(
        factors=factors,
        backgrounds=backgrounds,
        trajectory_runs=trajectories,
        scenario_id=scenario_id,
        uncertainty=max(0.0, float(args.input_uncertainty)),
    )
    payload["failed_runs"] = failed
    output_path = summary_path.with_name("montecarlo_paired_propagation.json")
    write_json(output_path, payload)
    lot_events_path = (
        resolve_repo_path(args.lot_events_csv)
        if args.lot_events_csv
        else summary_path.parent.parent.parent / "data" / "production_lot_events.csv"
    )
    temporal_payload = build_temporal_propagation(
        payload,
        base_data,
        lot_events_csv=lot_events_path if lot_events_path.exists() else None,
    )
    temporal_path = summary_path.with_name(
        "montecarlo_temporal_propagation.json"
    )
    write_json(temporal_path, temporal_payload)
    summary["paired_propagation"] = {
        "enabled": True,
        "path": str(output_path),
        "schema_version": payload.get("schema_version"),
        "method": payload.get("method"),
        "input_relative_uncertainty": payload.get("input_relative_uncertainty"),
        "factor_count": payload.get("factor_count"),
        "background_count": payload.get("background_count"),
        "runs_expected": len(specs),
        "runs_successful": payload.get("run_count"),
        "runs_failed": failed,
        "factors": factors,
        "temporal_propagation_path": str(temporal_path),
        "lot_events_path": str(lot_events_path) if lot_events_path.exists() else "",
    }
    write_json(summary_path, summary)
    print(f"[OK] Paired propagation: {output_path.resolve()}", flush=True)


if __name__ == "__main__":
    main()
