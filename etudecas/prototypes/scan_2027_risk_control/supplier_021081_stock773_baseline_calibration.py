#!/usr/bin/env python3
"""Calibrate 268967 baseline service by changing only opening stock 773474.

This additive orchestrator is deliberately staged.  By default it runs the
reference scenario only.  Supplier incidents are opt-in and must be launched
later, once a baseline near the requested service target has been identified.
No interpolation is used: fixed lots can make the response discontinuous.
"""

from __future__ import annotations

import argparse
import math
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Mapping, Sequence

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from etudecas.prototypes.scan_2027_risk_control import (  # noqa: E402
    supplier_021081_active_flow_campaign as base,
)
from etudecas.prototypes.scan_2027_risk_control import (  # noqa: E402
    supplier_021081_state_layer_demasking_campaign as layers,
)


ORCHESTRATOR_SHA256 = base.sha256_file(Path(__file__).resolve())
DEFAULT_SEED = 424081
DEFAULT_TARGETS = (0.93, 0.80)
SCENARIO_IDS = (
    "baseline_observed_order_book",
    "all_021081__usable_yield__0p1",
    "all_021081__delivery_availability__0p25",
    "all_021081__quality_hold__180",
)


def parse_float_list(raw: str) -> tuple[float, ...]:
    values = tuple(dict.fromkeys(float(item.strip()) for item in raw.split(",") if item.strip()))
    if not values or any(value < 0 for value in values):
        raise ValueError("Expected one or more non-negative comma-separated values")
    return values


def stock_states(
    graph: Mapping[str, Any], cover_days: Sequence[float]
) -> list[layers.LayerState]:
    states = layers.build_layer_states(graph, cover_days)
    requested = {float(value) for value in cover_days}
    selected = [
        state
        for state in states
        if state.cover_days in requested
        and state.regime_id.startswith("intermediate_stock_only_")
    ]
    if len(selected) != len(requested):
        raise base.CampaignValidationError(
            f"Expected {len(requested)} stock-773 states, found {len(selected)}"
        )
    return selected


def target_candidate_rows(
    rows: Sequence[Mapping[str, Any]],
    *,
    targets: Sequence[float] = DEFAULT_TARGETS,
    tolerance: float = 0.015,
) -> list[dict[str, Any]]:
    points = sorted(
        (
            (
                base.to_float(row.get("state_regime_target_cover_days"), math.nan),
                base.to_float(row.get("product_on_due_volume_proxy"), math.nan),
                str(row.get("state_regime") or ""),
            )
            for row in rows
            if str(row.get("scenario_id") or "")
            == "baseline_observed_order_book"
        ),
        key=lambda value: value[0],
    )
    points = [point for point in points if math.isfinite(point[0]) and math.isfinite(point[1])]
    output: list[dict[str, Any]] = []
    for target in targets:
        nearest = min(points, key=lambda point: abs(point[1] - target)) if points else (math.nan, math.nan, "")
        brackets = [
            (left, right)
            for left, right in zip(points, points[1:])
            if (left[1] - target) * (right[1] - target) <= 0
        ]
        bracket = min(
            brackets,
            key=lambda pair: abs(pair[1][0] - pair[0][0]),
            default=None,
        )
        output.append(
            {
                "target_service": target,
                "tolerance_percentage_points": tolerance * 100.0,
                "nearest_state_regime": nearest[2],
                "nearest_cover_days": nearest[0],
                "nearest_service": nearest[1],
                "absolute_gap_percentage_points": abs(nearest[1] - target) * 100.0,
                "within_tolerance": abs(nearest[1] - target) <= tolerance,
                "lower_bracket_cover_days": bracket[0][0] if bracket else "",
                "lower_bracket_service": bracket[0][1] if bracket else "",
                "upper_bracket_cover_days": bracket[1][0] if bracket else "",
                "upper_bracket_service": bracket[1][1] if bracket else "",
                "interpolation_claim_allowed": False,
                "interpretation": (
                    "discrete simulated point within tolerance"
                    if abs(nearest[1] - target) <= tolerance
                    else "target not attained by tested discrete points; report bracket only"
                    if bracket
                    else "target not bracketed by tested stock-773-only points"
                ),
            }
        )
    return output


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", default=str(base.DEFAULT_GRAPH))
    parser.add_argument("--engine", default=str(base.DEFAULT_ENGINE))
    parser.add_argument("--profile", default=str(base.DEFAULT_PROFILE))
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--cover-days", required=True)
    parser.add_argument("--targets", default="0.93,0.80")
    parser.add_argument("--tolerance", type=float, default=0.015)
    parser.add_argument("--days", type=int, default=720)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--retention", choices=["summary", "full"], default="summary")
    parser.add_argument(
        "--include-incidents",
        action="store_true",
        help="Opt in only after the requested baseline levels have been calibrated.",
    )
    parser.add_argument("--prepare-only", action="store_true")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    cover_days = parse_float_list(args.cover_days)
    targets = parse_float_list(args.targets)
    source_path = Path(args.input).resolve()
    engine = Path(args.engine).resolve()
    profile = Path(args.profile).resolve()
    root = Path(args.output_dir).resolve()
    root.mkdir(parents=True, exist_ok=True)
    source = base.read_json(source_path)
    states = stock_states(source, cover_days)
    scenarios_by_id = {
        scenario.scenario_id: scenario for scenario in base.build_scenarios()
    }
    selected_scenario_ids = (
        SCENARIO_IDS if args.include_incidents else (SCENARIO_IDS[0],)
    )
    scenarios = [scenarios_by_id[scenario_id] for scenario_id in selected_scenario_ids]
    state_inputs: dict[str, dict[str, Any]] = {}
    for state in states:
        scale_path = layers.write_scale_input(root, state)
        graph, graph_audit = layers.graph_for_state(source, state, days=args.days)
        graph_path = root / "inputs" / f"graph_{state.regime_id}.json"
        base.write_json(graph_path, graph)
        state_inputs[state.regime_id] = {
            "state": state,
            "scale_path": scale_path,
            "graph": graph,
            "graph_path": graph_path,
            "graph_sha256": base.sha256_file(graph_path),
            "graph_audit": graph_audit,
        }
    base.write_csv(root / "stock_773_state_design.csv", layers.state_rows(states))
    base.write_csv(root / "scenario_design.csv", base.scenario_design_rows(scenarios))
    manifest: dict[str, Any] = {
        "schema_version": "supplier-021081-stock773-baseline-calibration.v1",
        "status": "prepared" if args.prepare_only else "running",
        "created_at_utc": base.utc_now(),
        "orchestrator": str(Path(__file__).resolve()),
        "orchestrator_sha256_at_process_start": ORCHESTRATOR_SHA256,
        "campaign_library_sha256_at_process_start": base.PROCESS_ORCHESTRATOR_SHA256,
        "layer_library_sha256_at_process_start": layers.ORCHESTRATOR_SHA256,
        "source_graph": str(source_path),
        "source_graph_sha256": base.sha256_file(source_path),
        "engine": str(engine),
        "engine_sha256": base.sha256_file(engine),
        "profile": str(profile),
        "profile_sha256": base.sha256_file(profile),
        "days": args.days,
        "seed": args.seed,
        "cover_days": list(cover_days),
        "targets": list(targets),
        "tolerance": args.tolerance,
        "include_incidents": bool(args.include_incidents),
        "planned_case_count": len(states) * len(scenarios),
        "scientific_scope": {
            "changed_layer": "opening stock 773474 only at SDC-1450 and M-1430",
            "distribution": "same proportional scale at both sites",
            "baseline_first": not args.include_incidents,
            "interpolation_claim_allowed": False,
            "incident_rule": (
                "incidents are opt-in and only valid after a baseline target has been selected"
            ),
            "observed_claim_allowed": False,
        },
        "state_graphs": {
            state_id: {
                "path": str(values["graph_path"]),
                "sha256": values["graph_sha256"],
                "audit": values["graph_audit"],
            }
            for state_id, values in state_inputs.items()
        },
    }
    base.write_json(root / "campaign_manifest.json", manifest)
    if args.prepare_only:
        print(f"[OK] prepared stock-773 calibration at {root}")
        return 0

    profile_args = base.engine_profile_args(profile)
    jobs = [
        (values, scenario)
        for values in state_inputs.values()
        for scenario in scenarios
    ]
    rows: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=max(1, min(args.workers, 4))) as pool:
        futures = {
            pool.submit(
                base.run_case,
                source_graph=values["graph"],
                source_graph_path=values["graph_path"],
                engine=engine,
                profile_args=profile_args,
                output_root=root,
                scenario=scenario,
                seed=args.seed,
                stage="stock_773_baseline_calibration"
                if not args.include_incidents
                else "stock_773_calibrated_incident_comparison",
                days=args.days,
                retention=args.retention,
                opening_order_risk_mode="engine",
                state_regime=values["state"].engine_regime(),
                measurement_start_stock_scale_csv=values["scale_path"],
            ): (values, scenario)
            for values, scenario in jobs
        }
        for future in as_completed(futures):
            values, scenario = futures[future]
            row = future.result()
            state = values["state"]
            row["calibration_orchestrator_sha256_at_process_start"] = (
                ORCHESTRATOR_SHA256
            )
            row["source_graph_original_sha256"] = base.sha256_file(source_path)
            row["variant_graph_sha256"] = values["graph_sha256"]
            row["state_graph_sha256"] = values["graph_sha256"]
            row["intermediate_773474_target_total_qty_g"] = (
                state.intermediate_target_total_g
            )
            row["stock_773_only_calibration"] = True
            rows.append(row)
            print(
                f"[STOCK_773_CALIBRATION] cover={state.cover_days:g}d "
                f"scenario={scenario.scenario_id} service="
                f"{base.to_float(row.get('product_on_due_volume_proxy')):.2%}",
                flush=True,
            )
    rows = layers.paired_layer_metrics(rows)
    base.write_csv(root / "baseline_calibration_metrics.csv", rows)
    gates: dict[str, Any] = {}
    for state in states:
        reference = next(
            row
            for row in rows
            if str(row.get("state_regime") or "") == state.regime_id
            and str(row.get("scenario_id") or "") == SCENARIO_IDS[0]
        )
        gate = base.reference_flow_gate(reference)
        measured = base.to_float(
            reference.get("intermediate_773474_measurement_start_total_qty_g"),
            math.nan,
        )
        gate.update(
            {
                "configured_intermediate_773474_total_qty_g": (
                    state.intermediate_target_total_g
                ),
                "measured_intermediate_773474_total_qty_g": measured,
                "intermediate_target_matches": math.isclose(
                    measured,
                    state.intermediate_target_total_g,
                    rel_tol=0.0,
                    abs_tol=1e-2,
                ),
            }
        )
        if not gate["intermediate_target_matches"]:
            gate["errors"].append("773474 measurement-start target mismatch")
        gate["validated"] = not gate["errors"]
        gates[state.regime_id] = gate
    candidates = target_candidate_rows(
        rows,
        targets=targets,
        tolerance=args.tolerance,
    )
    base.write_csv(root / "baseline_target_candidates.csv", candidates)
    base.write_json(root / "reference_and_state_gates.json", gates)
    if any(not gate["validated"] for gate in gates.values()):
        manifest.update({"status": "invalid_reference_or_state_gate", "gates": gates})
        base.write_json(root / "campaign_manifest.json", manifest)
        raise base.CampaignValidationError("Stock-773 calibration gate failed")
    manifest.update(
        {
            "status": "complete",
            "completed_at_utc": base.utc_now(),
            "case_count": len(rows),
            "gates": gates,
            "target_candidates": candidates,
            "outputs": {
                "metrics": "baseline_calibration_metrics.csv",
                "candidates": "baseline_target_candidates.csv",
                "state_design": "stock_773_state_design.csv",
            },
        }
    )
    base.write_json(root / "campaign_manifest.json", manifest)
    print(f"[OK] stock-773 baseline calibration: {root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
