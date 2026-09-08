#!/usr/bin/env python3
"""Run an additive, explicitly preliminary 100/93/80 service calibration.

This utility reuses the immutable V2 candidate inputs while pinning the current
engine separately.  It exists because the signed V2 runner correctly refuses a
different engine byte hash.  It never mutates the V2 plan or historical runs.
No acute supplier incident and no endogenous state-risk layer are enabled.
"""

from __future__ import annotations

import argparse
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

_IMPORT_REPO_ROOT = Path(__file__).resolve().parents[3]
if str(_IMPORT_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_IMPORT_REPO_ROOT))

from etudecas.prototypes.scan_2027_risk_control import (  # noqa: E402
    supplier_service_regime_calibration_protocol as protocol,
)
from etudecas.prototypes.scan_2027_risk_control import (  # noqa: E402
    supplier_service_regime_calibration_runner as runner,
)
from etudecas.prototypes.scan_2027_risk_control import (  # noqa: E402
    supplier_service_landscape_campaign as campaign_core,
)


SCHEMA_VERSION = "etudecas.supplier_service_regime_quick_preliminary.v1"
DEFAULT_OUTPUT = (
    protocol.ARTIFACT_PARENT / "supplier_service_regime_quick_preliminary_20260904_v1"
)
CONFIRMATION_SEEDS = (340282, 340283, 340284)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_preliminary_plan(
    plan_dir: Path,
) -> tuple[runner.ValidatedPlan, dict[str, Any]]:
    """Validate frozen inputs while declaring the current engine hash divergence."""

    plan_dir = plan_dir.resolve()
    digest, files = runner._directory_digest(plan_dir)
    if (
        digest != runner.EXPECTED_PLAN_ARTIFACT_SHA256
        or len(files) != runner.EXPECTED_PLAN_FILE_COUNT
    ):
        raise ValueError("The immutable V2 plan inventory changed")
    manifest = runner._read_json(plan_dir / "calibration_plan.json")
    inventory_raw = runner._read_json(plan_dir / "input_inventory.json")
    inventory = {str(key): dict(value) for key, value in inventory_raw.items()}
    candidates = tuple(protocol.build_candidates())
    if set(inventory) != {candidate.scenario_id for candidate in candidates}:
        raise ValueError("Candidate inventory is incomplete")
    source = manifest.get("source_paths") or {}
    current_engine = protocol.DEFAULT_ENGINE.resolve()
    expected_engine_sha = str(
        (manifest.get("reference_audit") or {}).get("engine_sha256") or ""
    )
    current_engine_sha = protocol.sha256_file(current_engine)
    graph = Path(str(source.get("graph") or protocol.DEFAULT_GRAPH)).resolve()
    profile = Path(str(source.get("profile") or protocol.DEFAULT_PROFILE)).resolve()
    reference = Path(
        str(source.get("reference_campaign") or protocol.DEFAULT_REFERENCE_CAMPAIGN)
    ).resolve()
    plan = runner.ValidatedPlan(
        plan_dir=plan_dir,
        manifest=manifest,
        inventory=inventory,
        candidates=candidates,
        plan_artifact_sha256=digest,
        calibration_plan_sha256=protocol.sha256_file(
            plan_dir / "calibration_plan.json"
        ),
        reference_campaign=reference,
        graph=graph,
        engine=current_engine,
        profile=profile,
    )
    audit = {
        "frozen_plan_inventory_valid": True,
        "frozen_plan_engine_sha256": expected_engine_sha,
        "current_engine_sha256": current_engine_sha,
        "signed_v2_engine_match": current_engine_sha == expected_engine_sha,
        "evidence_status": "preliminary_current_engine_not_signed_v2",
        "quality_branch_included": False,
        "acute_supplier_incident_included": False,
        "endogenous_state_risk_included": False,
    }
    return plan, audit


def _selection(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Select 93% and 80% on one common, global supplier degradation axis.

    Comparing incidents between operating points is only interpretable when the
    operating points differ through the same physical assumption.  The two
    global supplier families are therefore evaluated first and the family that
    jointly approaches both targets is retained.  Factory load, customer demand
    and the two-lane-only capacity hypothesis are intentionally excluded from
    this operating-point selection; they remain useful sensitivity results.
    """

    preferred_families = (
        "supplier_nominal_delivery_reliability",
        "supplier_planned_lead",
    )
    by_family: dict[str, list[Mapping[str, Any]]] = {
        family: [row for row in rows if str(row.get("family")) == family]
        for family in preferred_families
    }
    if any(not family_rows for family_rows in by_family.values()):
        raise ValueError("The global supplier-family screening is incomplete")

    def closest(
        family_rows: Sequence[Mapping[str, Any]], target: float
    ) -> tuple[Mapping[str, Any], float, bool]:
        candidates = []
        for row in family_rows:
            service = float(row["system_on_due_service"])
            product_min = min(
                float(row["on_due_service_268091"]),
                float(row["on_due_service_268967"]),
            )
            balanced = product_min >= target - protocol.PRODUCT_BALANCE_GUARD
            candidates.append(
                (not balanced, abs(service - target), str(row["scenario_id"]), row)
            )
        unbalanced, distance, _scenario_id, best = min(candidates)
        return best, distance, not unbalanced

    family_evaluations: list[dict[str, Any]] = []
    for family in preferred_families:
        target_results = [closest(by_family[family], target) for target in protocol.TARGETS]
        distances = [result[1] for result in target_results]
        balanced = [result[2] for result in target_results]
        services = [
            float(result[0]["system_on_due_service"]) for result in target_results
        ]
        family_evaluations.append(
            {
                "family": family,
                "target_results": target_results,
                "targets_within_tolerance": sum(
                    distance <= protocol.TARGET_TOLERANCE for distance in distances
                ),
                "balanced_target_count": sum(balanced),
                "total_absolute_target_distance": sum(distances),
                "ordered_service_levels": services[0] >= services[1],
            }
        )

    chosen = min(
        family_evaluations,
        key=lambda item: (
            -int(item["targets_within_tolerance"]),
            -int(item["balanced_target_count"]),
            not bool(item["ordered_service_levels"]),
            float(item["total_absolute_target_distance"]),
            preferred_families.index(str(item["family"])),
        ),
    )
    selected: list[str] = []
    records: list[dict[str, Any]] = []
    for target, (best, distance, balanced) in zip(
        protocol.TARGETS, chosen["target_results"], strict=True
    ):
        scenario_id = str(best["scenario_id"])
        selected.append(scenario_id)
        records.append(
            {
                "target_service": target,
                "scenario_id": scenario_id,
                "family": best["family"],
                "parameter_value": best["parameter_value"],
                "parameter_unit": best["parameter_unit"],
                "screening_system_service": best["system_on_due_service"],
                "screening_product_268091_service": best["on_due_service_268091"],
                "screening_product_268967_service": best["on_due_service_268967"],
                "absolute_target_distance": distance,
                "within_1p5_point_tolerance": distance <= protocol.TARGET_TOLERANCE,
                "balanced_products": balanced,
                "interpolation_used": False,
            }
        )
    return {
        "schema_version": f"{SCHEMA_VERSION}.selection",
        "status": "preliminary_discrete_selection_single_supplier_axis",
        "selection_strategy": "one_common_global_supplier_axis_for_93_and_80",
        "selected_family": chosen["family"],
        "selected_scenario_ids": list(dict.fromkeys(selected)),
        "records": records,
        "family_diagnostics": [
            {
                key: value
                for key, value in evaluation.items()
                if key != "target_results"
            }
            for evaluation in family_evaluations
        ],
        "all_targets_within_1p5_point_tolerance": (
            chosen["targets_within_tolerance"] == len(protocol.TARGETS)
        ),
        "operating_points_are_historical_estimates": False,
        "final_regime_claim_allowed": False,
    }


def _operating_point_manifest(
    selection: Mapping[str, Any],
    plan: runner.ValidatedPlan,
    plan_audit: Mapping[str, Any],
) -> dict[str, Any]:
    """Resolve the three provisional operating points into executable inputs."""

    reference_floors = (
        plan.reference_campaign / "inputs" / "prepared_physical_supplier_floors.csv"
    ).resolve()
    points = [
        {
            "operating_point_id": "op_100",
            "operating_point_label": "Fonctionnement de référence proche de 100 %",
            "target_service": 1.0,
            "source_scenario_id": "baseline_nominal",
            "degradation_family": "baseline",
            "degradation_value": 1.0,
            "degradation_unit": "reference",
            "graph": str(plan.graph.resolve()),
            "supplier_floors": str(reference_floors),
            "factory_capacities": "",
        }
    ]
    for record in selection["records"]:
        target = float(record["target_service"])
        scenario_id = str(record["scenario_id"])
        execution = dict(plan.inventory[scenario_id]["execution_inputs"])
        points.append(
            {
                "operating_point_id": f"op_{int(round(target * 100))}",
                "operating_point_label": (
                    f"Fonctionnement visant {target:.0%} de service"
                ),
                "target_service": target,
                "source_scenario_id": scenario_id,
                "degradation_family": record["family"],
                "degradation_value": record["parameter_value"],
                "degradation_unit": record["parameter_unit"],
                "screening_system_service": record["screening_system_service"],
                "screening_product_268091_service": record[
                    "screening_product_268091_service"
                ],
                "screening_product_268967_service": record[
                    "screening_product_268967_service"
                ],
                "graph": execution["graph"],
                "supplier_floors": execution["supplier_floors"],
                "factory_capacities": execution.get("factory_capacities") or "",
            }
        )
    return {
        "schema_version": f"{SCHEMA_VERSION}.operating_points",
        "status": "preliminary_discrete_operating_points",
        "selection_strategy": selection["selection_strategy"],
        "selected_family": selection["selected_family"],
        "quality_branch_included": False,
        "supplier_state_dependent_risks_enabled": False,
        "acute_incident_included_in_operating_point": False,
        "simulation_hypotheses_not_observed_supplier_performance": True,
        "engine_sha256": plan_audit["current_engine_sha256"],
        "operating_points": points,
    }


def _write_progress(
    output: Path,
    *,
    plan_audit: Mapping[str, Any],
    evidence: Mapping[str, Mapping[str, Any]],
    planned_count: int,
    stage: str,
) -> None:
    rows = [runner._metric_row(item) for item in evidence.values()]
    rows.sort(
        key=lambda row: (str(row["stage"]), str(row["scenario_id"]), int(row["seed"]))
    )
    runner._write_csv(output / "preliminary_metrics.csv", rows)
    screening = [row for row in rows if row["stage"] == "screening"]
    nearest: dict[str, Any] = {}
    for target in protocol.TARGETS:
        if screening:
            row = min(
                screening,
                key=lambda item: abs(float(item["system_on_due_service"]) - target),
            )
            nearest[str(target)] = {
                "scenario_id": row["scenario_id"],
                "family": row["family"],
                "parameter_value": row["parameter_value"],
                "system_on_due_service": row["system_on_due_service"],
                "on_due_service_268091": row["on_due_service_268091"],
                "on_due_service_268967": row["on_due_service_268967"],
            }
    stage_rows = [row for row in rows if row["stage"] == stage]
    runner._write_json(
        output / "PRELIMINARY_PROGRESS.json",
        {
            "schema_version": f"{SCHEMA_VERSION}.progress",
            "status": "running"
            if len(stage_rows) < planned_count
            else f"{stage}_complete",
            "stage": stage,
            "completed_case_count": len(stage_rows),
            "planned_case_count": planned_count,
            "nearest_completed_points": nearest,
            "plan_audit": dict(plan_audit),
            "updated_at_utc": _now(),
        },
    )


def run_stage(plan_dir: Path, output: Path, *, stage: str, workers: int) -> None:
    plan, plan_audit = _load_preliminary_plan(plan_dir)
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    signature = runner._stable_sha256(
        {
            "schema_version": SCHEMA_VERSION,
            "plan_artifact_sha256": plan.plan_artifact_sha256,
            "current_engine_sha256": plan_audit["current_engine_sha256"],
            "confirmation_seeds": CONFIRMATION_SEEDS,
        }
    )
    ledger = runner._load_ledger(output, signature)
    evidence = runner._load_evidence_rows(output, ledger)
    if stage == "screening":
        scenario_ids = [candidate.scenario_id for candidate in plan.candidates]
        seeds = (protocol.SCREENING_SEED,)
    else:
        selection_path = output / "preliminary_selection.json"
        if not selection_path.is_file():
            raise ValueError("Run the screening stage first")
        selection = runner._read_json(selection_path)
        scenario_ids = list(selection["selected_scenario_ids"])
        seeds = CONFIRMATION_SEEDS
    planned = [
        runner.PlannedCase(scenario_id, seed, stage)
        for scenario_id in scenario_ids
        for seed in seeds
    ]
    missing = [case for case in planned if case.key not in evidence]
    _write_progress(
        output,
        plan_audit=plan_audit,
        evidence=evidence,
        planned_count=len(planned),
        stage=stage,
    )
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {
            pool.submit(runner.execute_engine_case, case, plan, output): case
            for case in missing
        }
        for future in as_completed(futures):
            case = futures[future]
            item = future.result()
            runner._validate_evidence(item, case, plan)
            runner._persist_evidence(output, ledger, item)
            evidence[case.key] = item
            campaign_core.prune_case_artifacts(Path(str(item["run_dir"])))
            print(
                f"[{stage.upper()}] {case.scenario_id} seed={case.seed} "
                f"service={float(item['metrics']['system_on_due_service']):.4%}",
                flush=True,
            )
            _write_progress(
                output,
                plan_audit=plan_audit,
                evidence=evidence,
                planned_count=len(planned),
                stage=stage,
            )
    if stage == "screening":
        rows = [
            runner._metric_row(item)
            for item in evidence.values()
            if item.get("stage") == "screening"
        ]
        if len(rows) != len(plan.candidates):
            raise RuntimeError("The preliminary screening matrix is incomplete")
        selection = _selection(rows)
        runner._write_json(output / "preliminary_selection.json", selection)
        runner._write_json(
            output / "preliminary_operating_points.json",
            _operating_point_manifest(selection, plan, plan_audit),
        )
    else:
        rows = [
            runner._metric_row(item)
            for item in evidence.values()
            if item.get("stage") == "confirmation"
        ]
        runner._write_csv(output / "preliminary_confirmation_metrics.csv", rows)
        runner._write_csv(
            output / "preliminary_confirmation_summary.csv",
            runner._summary_rows(rows),
        )


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", choices=("screening", "confirmation"), required=True)
    parser.add_argument("--plan-dir", type=Path, default=protocol.DEFAULT_OUTPUT_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--workers", type=int, choices=(1, 2, 3), default=2)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    run_stage(args.plan_dir, args.output_dir, stage=args.stage, workers=args.workers)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
