#!/usr/bin/env python3
"""Refine the global supplier lead-time axis around 93% and 80% service."""

from __future__ import annotations

import argparse
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Mapping, Sequence

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from etudecas.prototypes.scan_2027_risk_control import (  # noqa: E402
    supplier_service_landscape_campaign as campaign_core,
)
from etudecas.prototypes.scan_2027_risk_control import (  # noqa: E402
    supplier_service_regime_calibration_protocol as protocol,
)
from etudecas.prototypes.scan_2027_risk_control import (  # noqa: E402
    supplier_service_regime_calibration_runner as runner,
)
from etudecas.prototypes.scan_2027_risk_control import (  # noqa: E402
    supplier_service_regime_quick_preliminary as quick,
)


DEFAULT_SCREENING = (
    protocol.ARTIFACT_PARENT / "supplier_service_regime_quick_preliminary_20260904_v1"
)
DEFAULT_OUTPUT = (
    protocol.ARTIFACT_PARENT / "supplier_service_regime_fine_preliminary_20260904_v1"
)
FAMILY = "supplier_planned_lead"
KIND = "graph_lead"
UNIT = "jours_ajoutes"
DOMAIN = "supplier"


def _values(specification: str) -> tuple[float, ...]:
    values = tuple(dict.fromkeys(float(part.strip()) for part in specification.split(",")))
    if not values or any(value <= 0.0 for value in values):
        raise ValueError("Fine lead values must be positive")
    return values


def _candidate(value: float, index: int) -> protocol.Candidate:
    return protocol.Candidate(
        scenario_id=f"{FAMILY}__fine_{protocol.candidate_code(value)}",
        family=FAMILY,
        severity_index=index,
        value=value,
        unit=UNIT,
        kind=KIND,
        domain=DOMAIN,
    )


def _point_manifest(
    *,
    selected: Sequence[Mapping[str, Any]],
    plan: runner.ValidatedPlan,
    inventory: Mapping[str, Mapping[str, Any]],
    output: Path,
) -> dict[str, Any]:
    reference_floors = (
        plan.reference_campaign / "inputs" / "prepared_physical_supplier_floors.csv"
    ).resolve()
    points: list[dict[str, Any]] = [
        {
            "operating_point_id": "op_100",
            "operating_point_label": "Référence nominale simulée proche de 100 %",
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
    combined_inventory = {**plan.inventory, **inventory}
    for target, row in zip(protocol.TARGETS, selected, strict=True):
        execution = combined_inventory[str(row["scenario_id"])]["execution_inputs"]
        global_service = float(row["system_on_due_service"])
        p1 = float(row["on_due_service_268091"])
        p2 = float(row["on_due_service_268967"])
        balanced = min(p1, p2) >= target - protocol.PRODUCT_BALANCE_GUARD
        points.append(
            {
                "operating_point_id": f"op_{round(target * 100):.0f}",
                "operating_point_label": (
                    f"État simulé {global_service:.1%} global "
                    f"(cible {target:.0%}; {'PF équilibrés' if balanced else 'PF asymétriques'})"
                ),
                "target_service": target,
                "source_scenario_id": row["scenario_id"],
                "degradation_family": FAMILY,
                "degradation_value": row["parameter_value"],
                "degradation_unit": UNIT,
                "screening_system_service": global_service,
                "screening_product_268091_service": p1,
                "screening_product_268967_service": p2,
                "absolute_target_distance": abs(global_service - target),
                "within_1p5_point_tolerance": (
                    abs(global_service - target) <= protocol.TARGET_TOLERANCE
                ),
                "balanced_products": balanced,
                "graph": execution["graph"],
                "supplier_floors": execution["supplier_floors"],
                "factory_capacities": execution.get("factory_capacities") or "",
            }
        )
    return {
        "schema_version": "etudecas.supplier_service_regime_fine_preliminary.v1.operating_points",
        "status": "preliminary_fine_operating_points",
        "selection_strategy": "one_common_global_supplier_lead_axis",
        "selected_family": FAMILY,
        "quality_branch_included": False,
        "supplier_state_dependent_risks_enabled": False,
        "acute_incident_included_in_operating_point": False,
        "simulation_hypotheses_not_observed_supplier_performance": True,
        "engine_sha256": protocol.sha256_file(plan.engine),
        "source_screening_status": "partial_14_of_36_stopped_for_meeting_deadline",
        "output_dir": str(output.resolve()),
        "operating_points": points,
    }


def run(
    *,
    screening_dir: Path,
    output: Path,
    fine_values: Sequence[float],
    workers: int,
) -> None:
    plan, audit = quick._load_preliminary_plan(protocol.DEFAULT_OUTPUT_DIR)
    screening_rows = protocol.read_csv_rows(
        screening_dir / "preliminary_metrics.csv"
    )
    anchor_rows = [
        row
        for row in screening_rows
        if row.get("family") == FAMILY and row.get("stage") == "screening"
    ]
    if len(anchor_rows) < 4:
        raise ValueError("At least four completed lead-time anchors are required")
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    candidates = tuple(
        _candidate(value, index) for index, value in enumerate(fine_values, 1)
    )
    inventory = protocol.write_candidate_inputs(
        output_dir=output / "fine_plan",
        graph_path=plan.graph,
        reference_campaign=plan.reference_campaign,
        candidates=candidates,
    )
    fine_plan = runner.ValidatedPlan(
        plan_dir=output / "fine_plan",
        manifest=plan.manifest,
        inventory=inventory,
        candidates=candidates,
        plan_artifact_sha256=plan.plan_artifact_sha256,
        calibration_plan_sha256=plan.calibration_plan_sha256,
        reference_campaign=plan.reference_campaign,
        graph=plan.graph,
        engine=plan.engine,
        profile=plan.profile,
    )
    evidence: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {
            pool.submit(
                runner.execute_engine_case,
                runner.PlannedCase(candidate.scenario_id, protocol.SCREENING_SEED, "fine"),
                fine_plan,
                output,
            ): candidate
            for candidate in candidates
        }
        for future in as_completed(futures):
            candidate = futures[future]
            item = future.result()
            evidence.append(item)
            runner._write_json(
                output / "case_evidence" / f"{candidate.scenario_id}.json", item
            )
            campaign_core.prune_case_artifacts(Path(str(item["run_dir"])))
            print(
                f"[FINE] lead +{candidate.value:g} j -> "
                f"{float(item['metrics']['system_on_due_service']):.4%}",
                flush=True,
            )
    fine_rows = [runner._metric_row(item) for item in evidence]
    runner._write_csv(output / "fine_metrics.csv", fine_rows)
    combined = [*anchor_rows, *fine_rows]
    selected = [
        min(
            combined,
            key=lambda row: (
                abs(float(row["system_on_due_service"]) - target),
                str(row["scenario_id"]),
            ),
        )
        for target in protocol.TARGETS
    ]
    manifest = _point_manifest(
        selected=selected,
        plan=plan,
        inventory=inventory,
        output=output,
    )
    manifest["fine_values_tested"] = list(fine_values)
    manifest["plan_audit"] = audit
    runner._write_json(output / "preliminary_operating_points.json", manifest)
    runner._write_json(
        output / "fine_selection.json",
        {
            "status": "preliminary",
            "selected": [
                {
                    "target_service": target,
                    "scenario_id": row["scenario_id"],
                    "lead_extra_days": row["parameter_value"],
                    "system_on_due_service": row["system_on_due_service"],
                    "on_due_service_268091": row["on_due_service_268091"],
                    "on_due_service_268967": row["on_due_service_268967"],
                }
                for target, row in zip(protocol.TARGETS, selected, strict=True)
            ],
        },
    )


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--screening-dir", type=Path, default=DEFAULT_SCREENING)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--values", default="9.3,32")
    parser.add_argument("--workers", type=int, choices=(1, 2), default=2)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    run(
        screening_dir=args.screening_dir,
        output=args.output_dir,
        fine_values=_values(args.values),
        workers=args.workers,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
