#!/usr/bin/env python3
"""Run a small paired supplier-risk calibration campaign.

This campaign is deliberately separate from every historical cold-start,
dashboard and cascade result.  It compares, with identical random seeds:

* the inferred physical supplier/factory floors; and
* a calibration hypothesis close to the business targets (93% / 80%).

The hypothesis is not presented as an industrial truth.  It shortens the
338929 lane lead time, constrains the M-1430 supplier lanes, and applies a
small 268967 demand stress.  Those assumptions must be validated against
actual supplier and service data.
"""

from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Iterable


REPO_ROOT = Path(__file__).resolve().parents[3]
ARTIFACT_ROOT = Path(
    r"C:\dev\lca-simu-pr40-validation-artifacts-20260726"
)
DEFAULT_OUTPUT = (
    ARTIFACT_ROOT
    / "supplier_risk_influence_20260829_v1"
    / "calibration_probe"
    / "paired_replays_v2"
)
DEFAULT_GRAPH = (
    REPO_ROOT
    / "etudecas"
    / "simulation_prep"
    / "result"
    / "reference_baseline"
    / "_mrp_bom_tests"
    / "bom_weekly_mps_lotified_no_static_fallback_physical_floor.json"
)
DEFAULT_BASELINE_RUN = (
    ARTIFACT_ROOT
    / "supplier_risk_influence_20260829_v1"
    / "calibration_probe"
    / "baseline_365d"
)
DEFAULT_PROFILE = (
    REPO_ROOT
    / "etudecas"
    / "prototypes"
    / "scan_2027_risk_control"
    / "config"
    / "canonical_real_baseline_engine_profile.json"
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--graph", type=Path, default=DEFAULT_GRAPH)
    parser.add_argument(
        "--supplier-floors",
        type=Path,
        default=DEFAULT_BASELINE_RUN / "data" / "supplier_nominal_parameters.csv",
    )
    parser.add_argument(
        "--factory-capacities",
        type=Path,
        default=DEFAULT_BASELINE_RUN / "data" / "production_capacity_nominal_parameters.csv",
    )
    parser.add_argument("--engine-profile", type=Path, default=DEFAULT_PROFILE)
    parser.add_argument("--seeds", default="330281-330290")
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--days", type=int, default=365)
    parser.add_argument("--lead-338929-scale", type=float, default=0.88)
    parser.add_argument("--m1430-capacity-scale", type=float, default=0.20)
    parser.add_argument("--demand-268967-scale", type=float, default=1.04)
    return parser.parse_args()


def parse_seeds(specification: str) -> list[int]:
    seeds: list[int] = []
    for chunk in specification.split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        if "-" in chunk:
            first, last = (int(part.strip()) for part in chunk.split("-", 1))
            step = 1 if last >= first else -1
            seeds.extend(range(first, last + step, step))
        else:
            seeds.append(int(chunk))
    unique = list(dict.fromkeys(seeds))
    if not unique:
        raise ValueError("At least one seed is required")
    return unique


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def write_csv(path: Path, rows: Iterable[dict[str, Any]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def build_candidate_graph(
    source: Path,
    destination: Path,
    *,
    lead_scale: float,
    demand_scale: float,
) -> dict[str, Any]:
    graph = json.loads(source.read_text(encoding="utf-8"))
    matched_lanes = 0
    for edge in graph.get("edges") or []:
        if (
            str(edge.get("from")) == "SDC-VD0914360C"
            and str(edge.get("to")) == "M-1810"
            and "item:338929" in (edge.get("items") or [])
        ):
            lead = edge.get("lead_time") or {}
            lead["mean"] = float(lead.get("mean", 0.0)) * lead_scale
            lead["calibration_hypothesis"] = {
                "original_mean_days": float(lead["mean"]) / lead_scale,
                "scale": lead_scale,
                "status": "hypothesis_to_validate",
            }
            matched_lanes += 1
    matched_demands = 0
    scaled_points = 0
    for scenario in graph.get("scenarios") or []:
        for demand in scenario.get("demand") or []:
            if str(demand.get("item_id")) != "item:268967":
                continue
            matched_demands += 1
            for profile in demand.get("profile") or []:
                for point in profile.get("points") or []:
                    point["value"] = float(point.get("value", 0.0)) * demand_scale
                    scaled_points += 1
            demand["calibration_hypothesis"] = {
                "scale": demand_scale,
                "status": "hypothesis_to_validate",
            }
    if matched_lanes != 1 or matched_demands != 1 or scaled_points == 0:
        raise ValueError(
            "Candidate graph scope mismatch: "
            f"lanes={matched_lanes}, demands={matched_demands}, points={scaled_points}"
        )
    write_json(destination, graph)
    return {
        "lead_lane_count": matched_lanes,
        "demand_profile_count": matched_demands,
        "demand_point_count": scaled_points,
    }


def build_candidate_floors(
    source: Path,
    destination: Path,
    *,
    capacity_scale: float,
) -> dict[str, Any]:
    with source.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        fields = list(reader.fieldnames or [])
        rows = list(reader)
    changed = 0
    positive_changed = 0
    for row in rows:
        if str(row.get("dst_node_id")) != "M-1430":
            continue
        changed += 1
        neutral = float(row.get("neutral_capacity_floor_qty_per_day") or 0.0)
        tested = float(row.get("tested_capacity_floor_qty_per_day") or neutral)
        if tested > 0:
            positive_changed += 1
        row["neutral_capacity_floor_qty_per_day"] = format(neutral * capacity_scale, ".12g")
        # The engine intentionally prefers the tested floor when this audit
        # column is present.  Scaling only the neutral column would therefore
        # leave the physical capacity unchanged.
        row["tested_capacity_floor_qty_per_day"] = format(tested * capacity_scale, ".12g")
    if changed == 0 or positive_changed == 0:
        raise ValueError("No positive M-1430 supplier capacity floor was found")
    write_csv(destination, rows, fields)
    return {
        "m1430_lane_count": changed,
        "positive_capacity_lane_count": positive_changed,
        "scaled_columns": [
            "neutral_capacity_floor_qty_per_day",
            "tested_capacity_floor_qty_per_day",
        ],
    }


def engine_profile_args(path: Path) -> list[str]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    values = payload.get("args") if isinstance(payload, dict) else payload
    if not isinstance(values, list) or not all(isinstance(value, str) for value in values):
        raise ValueError(f"Invalid engine profile: {path}")
    return list(values)


def service_summary(path: Path) -> dict[str, dict[str, float]]:
    grouped: dict[str, dict[str, float]] = {}
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            item = str(row.get("item_id") or "")
            if item not in {"item:268091", "item:268967"}:
                continue
            stats = grouped.setdefault(
                item,
                {
                    "demand": 0.0,
                    "served": 0.0,
                    "backlog_days": 0.0,
                    "ending_backlog": 0.0,
                    "max_backlog": 0.0,
                },
            )
            stats["demand"] += float(row.get("demand_qty") or 0.0)
            stats["served"] += float(row.get("served_qty") or 0.0)
            backlog = float(row.get("backlog_end_qty") or 0.0)
            stats["backlog_days"] += float(backlog > 1e-9)
            stats["ending_backlog"] = backlog
            stats["max_backlog"] = max(stats["max_backlog"], backlog)
    for stats in grouped.values():
        stats["fill_rate"] = stats["served"] / stats["demand"] if stats["demand"] else 1.0
    return grouped


def run_one(
    *,
    repo_root: Path,
    output_dir: Path,
    engine: Path,
    graph: Path,
    floors: Path,
    factory_capacities: Path,
    profile_args: list[str],
    variant: str,
    seed: int,
    days: int,
) -> dict[str, Any]:
    run_dir = output_dir / variant / f"seed_{seed}"
    service_path = run_dir / "data" / "production_demand_service_daily.csv"
    status = "reused" if service_path.exists() else "executed"
    if not service_path.exists():
        run_dir.mkdir(parents=True, exist_ok=True)
        command = [
            sys.executable,
            str(engine),
            "--input",
            str(graph),
            "--output-dir",
            str(run_dir),
            "--days",
            str(days),
            "--seed",
            str(seed),
            "--skip-map",
            "--skip-plots",
            "--output-profile",
            "compact",
            "--no-lot-trace",
            "--skip-lot-audit",
            "--common-random-numbers",
            "--supplier-neutral-floors-csv",
            str(floors),
            "--factory-nominal-capacities-csv",
            str(factory_capacities),
            *profile_args,
        ]
        log_path = run_dir / "campaign_engine.log"
        with log_path.open("w", encoding="utf-8") as log:
            completed = subprocess.run(
                command,
                cwd=repo_root,
                stdout=log,
                stderr=subprocess.STDOUT,
                text=True,
                check=False,
            )
        if completed.returncode != 0:
            raise RuntimeError(
                f"Engine failed for {variant}/seed_{seed}; see {log_path}"
            )
    metrics = service_summary(service_path)
    row: dict[str, Any] = {"variant": variant, "seed": seed, "status": status}
    for product in ("268091", "268967"):
        stats = metrics[f"item:{product}"]
        for name in ("fill_rate", "backlog_days", "ending_backlog", "max_backlog"):
            row[f"{name}_{product}"] = stats[name]
    row["run_dir"] = str(run_dir)
    return row


def main() -> None:
    args = parse_args()
    repo_root = args.repo_root.resolve()
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    inputs = output_dir / "inputs"
    candidate_graph = inputs / "target_hypothesis_graph.json"
    candidate_floors = inputs / "target_hypothesis_supplier_floors.csv"
    graph_audit = build_candidate_graph(
        args.graph.resolve(),
        candidate_graph,
        lead_scale=args.lead_338929_scale,
        demand_scale=args.demand_268967_scale,
    )
    floor_audit = build_candidate_floors(
        args.supplier_floors.resolve(),
        candidate_floors,
        capacity_scale=args.m1430_capacity_scale,
    )
    profile = engine_profile_args(args.engine_profile.resolve())
    seeds = parse_seeds(args.seeds)
    engine = repo_root / "etudecas" / "simulation" / "engine" / "run_first_simulation.py"
    jobs: list[dict[str, Any]] = []
    for seed in seeds:
        jobs.extend(
            [
                {
                    "variant": "physical_nominal",
                    "seed": seed,
                    "graph": args.graph.resolve(),
                    "floors": args.supplier_floors.resolve(),
                },
                {
                    "variant": "target_hypothesis",
                    "seed": seed,
                    "graph": candidate_graph,
                    "floors": candidate_floors,
                },
            ]
        )
    rows: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as pool:
        futures = {
            pool.submit(
                run_one,
                repo_root=repo_root,
                output_dir=output_dir,
                engine=engine,
                graph=job["graph"],
                floors=job["floors"],
                factory_capacities=args.factory_capacities.resolve(),
                profile_args=profile,
                variant=job["variant"],
                seed=job["seed"],
                days=args.days,
            ): job
            for job in jobs
        }
        for future in as_completed(futures):
            row = future.result()
            rows.append(row)
            print(
                f"[{row['status'].upper()}] {row['variant']} seed={row['seed']} "
                f"268091={row['fill_rate_268091']:.4%} "
                f"268967={row['fill_rate_268967']:.4%}",
                flush=True,
            )
    rows.sort(key=lambda row: (row["seed"], row["variant"]))
    fields = list(rows[0])
    write_csv(output_dir / "paired_replay_results.csv", rows, fields)
    by_key = {(row["seed"], row["variant"]): row for row in rows}
    paired: list[dict[str, Any]] = []
    for seed in seeds:
        nominal = by_key[(seed, "physical_nominal")]
        candidate = by_key[(seed, "target_hypothesis")]
        paired.append(
            {
                "seed": seed,
                "nominal_fill_268091": nominal["fill_rate_268091"],
                "hypothesis_fill_268091": candidate["fill_rate_268091"],
                "delta_fill_268091": candidate["fill_rate_268091"] - nominal["fill_rate_268091"],
                "nominal_fill_268967": nominal["fill_rate_268967"],
                "hypothesis_fill_268967": candidate["fill_rate_268967"],
                "delta_fill_268967": candidate["fill_rate_268967"] - nominal["fill_rate_268967"],
            }
        )
    write_csv(output_dir / "paired_deltas.csv", paired, list(paired[0]))
    write_json(
        output_dir / "campaign_manifest.json",
        {
            "schema_version": "etudecas.supplier_risk_calibration_campaign.v1",
            "evidence_class": "hypothesis",
            "purpose": "Explore physical assumptions close to business targets; not a fitted industrial baseline.",
            "seeds": seeds,
            "days": args.days,
            "common_random_numbers": True,
            "variants": {
                "physical_nominal": {
                    "graph": str(args.graph.resolve()),
                    "supplier_floors": str(args.supplier_floors.resolve()),
                },
                "target_hypothesis": {
                    "lead_338929_scale": args.lead_338929_scale,
                    "m1430_supplier_capacity_scale": args.m1430_capacity_scale,
                    "demand_268967_scale": args.demand_268967_scale,
                    "graph": str(candidate_graph),
                    "supplier_floors": str(candidate_floors),
                },
            },
            "graph_scope_audit": graph_audit,
            "floor_scope_audit": floor_audit,
            "results_csv": str(output_dir / "paired_replay_results.csv"),
            "paired_deltas_csv": str(output_dir / "paired_deltas.csv"),
        },
    )
    print(f"[OK] Campaign summary: {output_dir / 'paired_replay_results.csv'}")


if __name__ == "__main__":
    main()
