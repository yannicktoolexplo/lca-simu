#!/usr/bin/env python3
"""Paired confirmation for the only orderbook-only effect found in screening.

The scope is intentionally fixed to VD0951020A -> M-1810 / item 001848,
availability 25 %, and the 90/30-day component-stock hypotheses.  All
state/seed/baseline/stress cases are scheduled together with at most four
workers.  A one-seed run first checks whether changing the seed changes any
paired physical, lot or client outcome before duplicating a deterministic run.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Mapping, Sequence

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from etudecas.prototypes.scan_2027_risk_control import (  # noqa: E402
    supplier_021081_active_flow_campaign as active,
)
from etudecas.prototypes.scan_2027_risk_control import (  # noqa: E402
    supplier_orderbook_only_lane_campaign as lanes,
)


ORCHESTRATOR_SHA256 = active.sha256_file(Path(__file__).resolve())
LANE = lanes.LANE_BY_ID["vd0951020a_001848_m1810"]
SCENARIOS = (
    lanes.SCENARIO_BY_ID["baseline_orderbook_replay"],
    lanes.SCENARIO_BY_ID["delivery_availability_0p25"],
)
COVERS = (90.0, 30.0)


def _outcome_signature(row: Mapping[str, Any]) -> str:
    fields = (
        "opening_order_planned_qty",
        "opening_order_pulled_qty",
        "opening_order_physical_shipped_qty",
        "opening_order_usable_qty",
        "opening_order_weighted_usable_day",
        "opening_order_receipt_signature_sha256",
        "descendant_lot_count",
        "intermediate_descendant_lot_count",
        "finished_descendant_lot_count",
        "customer_delivery_lot_count",
        "descendant_signature_sha256",
        "product_on_due_volume_proxy",
        "product_fill_rate",
        "product_backlog_qty_days",
        "product_backlog_end_qty",
        "product_released_qty",
        "product_produced_qty",
        "total_cost",
    )
    normalized: dict[str, Any] = {}
    for field in fields:
        value = row.get(field)
        try:
            number = float(value)
        except (TypeError, ValueError):
            normalized[field] = str(value or "")
        else:
            normalized[field] = round(number, 9) if math.isfinite(number) else str(number)
    return active.json_sha256(normalized)


def _screening_reference_rows(screening_dir: Path) -> dict[tuple[str, str], dict[str, str]]:
    manifest = active.read_json(screening_dir / "campaign_manifest.json")
    audit = active.read_json(screening_dir / "execution_provenance_audit.json")
    if str(manifest.get("status") or "") != "complete" or not bool(
        audit.get("reproducibility_wording_allowed")
    ):
        raise lanes.CampaignValidationError(
            "Confirmation requires a complete audited prospective screening"
        )
    selected: dict[tuple[str, str], dict[str, str]] = {}
    for row in active.read_csv_rows(screening_dir / "screening_metrics.csv"):
        key = (str(row.get("state_id") or ""), str(row.get("scenario_id") or ""))
        if (
            str(row.get("lane_id") or "") == LANE.lane_id
            and key[0] in {"prospective_001848_90d", "prospective_001848_30d"}
            and key[1] in {scenario.scenario_id for scenario in SCENARIOS}
        ):
            selected[key] = row
    if len(selected) != 4:
        raise lanes.CampaignValidationError(
            f"Expected four screening reference rows, found {len(selected)}"
        )
    return selected


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--screening-dir", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--input", default=str(lanes.DEFAULT_GRAPH))
    parser.add_argument("--engine", default=str(lanes.DEFAULT_ENGINE))
    parser.add_argument("--profile", default=str(lanes.DEFAULT_PROFILE))
    parser.add_argument("--v10", default=str(lanes.DEFAULT_V10))
    parser.add_argument("--seeds", default="423082")
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--retention", choices=("summary", "full"), default="summary")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    root = Path(args.output_dir).resolve()
    root.mkdir(parents=True, exist_ok=True)
    source_path = Path(args.input).resolve()
    engine = Path(args.engine).resolve()
    profile = Path(args.profile).resolve()
    screening_dir = Path(args.screening_dir).resolve()
    seeds = lanes.parse_seeds(args.seeds)
    graph = active.read_json(source_path)
    prior = _screening_reference_rows(screening_dir)
    source_audits = [lanes.source_order_audit(graph, LANE)]
    masking_audits = [lanes.v10_masking_audit(Path(args.v10).resolve(), LANE)]
    scale_by_cover = {
        cover: lanes._write_scale_file(root, LANE, cover, graph) for cover in COVERS
    }
    states = [
        {
            "state_id": f"prospective_001848_{cover:g}d",
            "cover_days": cover,
            "scale_csv": scale_by_cover[cover][0],
            "target": scale_by_cover[cover][1],
            "scale": scale_by_cover[cover][2],
        }
        for cover in COVERS
    ]
    profile_args = active.engine_profile_args(profile)
    planned_count = len(states) * len(SCENARIOS) * len(seeds)
    manifest: dict[str, Any] = {
        "schema_version": "supplier-orderbook-only-001848-confirmation.v1",
        "status": "running",
        "orchestrator": str(Path(__file__).resolve()),
        "orchestrator_sha256_at_process_start": ORCHESTRATOR_SHA256,
        "active_flow_library_sha256_at_process_start": active.PROCESS_ORCHESTRATOR_SHA256,
        "engine": str(engine),
        "engine_sha256": active.sha256_file(engine),
        "source_graph": str(source_path),
        "source_graph_sha256": active.sha256_file(source_path),
        "profile": str(profile),
        "profile_sha256": active.sha256_file(profile),
        "profile_args_sha256": active.json_sha256(list(profile_args)),
        "screening_dir": str(screening_dir),
        "screening_manifest_sha256": active.sha256_file(
            screening_dir / "campaign_manifest.json"
        ),
        "seeds": list(seeds),
        "planned_physical_engine_run_count": planned_count,
        "scientific_scope": {
            "lane": LANE.lane_id,
            "stock_cover_hypotheses_days": list(COVERS),
            "failure_mode": "availability 25 % of planned opening-order quantity",
            "confirmation_trigger": (
                "single-seed screening changed descendant genealogy without changing client KPI"
            ),
            "determinism_rule": (
                "If every physical/lot/client signature equals the audited screening "
                "despite a new seed, further identical seed duplication adds no evidence."
            ),
        },
    }
    active.write_json(root / "campaign_manifest.json", manifest)
    active.write_csv(root / "observed_snapshot_order_book_audit.csv", source_audits)
    active.write_csv(root / "v10_measured_masking_audit.csv", masking_audits)

    jobs: list[tuple[dict[str, Any], lanes.Scenario, int, Path, Path | None]] = []
    for state in states:
        for seed in seeds:
            for scenario in SCENARIOS:
                case_dir = (
                    root
                    / "cases"
                    / state["state_id"]
                    / scenario.scenario_id
                    / f"seed_{seed}"
                )
                risk_path: Path | None = None
                if not scenario.is_baseline:
                    risk_path = (
                        root
                        / "inputs"
                        / "risk_events"
                        / f"{state['state_id']}__{scenario.scenario_id}.csv"
                    )
                    active.write_csv(
                        risk_path,
                        lanes.risk_rows(graph, LANE, scenario, 720),
                        lanes.RISK_FIELDS,
                    )
                jobs.append((state, scenario, seed, case_dir, risk_path))

    rows: list[dict[str, Any]] = []
    provenance: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=max(1, min(args.workers, 4))) as pool:
        futures = {
            pool.submit(
                lanes._run_engine,
                engine=engine,
                graph=source_path,
                profile_args=profile_args,
                case_dir=case_dir,
                seed=seed,
                risk_csv=risk_path,
                scale_csv=state["scale_csv"],
            ): (state, scenario, seed, case_dir)
            for state, scenario, seed, case_dir, risk_path in jobs
        }
        for future in as_completed(futures):
            state, scenario, seed, case_dir = futures[future]
            record = future.result()
            record["engine_helper_orchestrator_sha256"] = record[
                "orchestrator_sha256_at_process_start"
            ]
            record["orchestrator_sha256_at_process_start"] = ORCHESTRATOR_SHA256
            provenance.append(record)
            row = lanes.extract_case(
                case_dir=case_dir,
                lane=LANE,
                scenario=scenario,
                seed=seed,
                state_id=state["state_id"],
                evidence_class=(
                    "paired_seed_confirmation_of_reduced_component_cover_hypothesis"
                ),
                target_stock_qty=state["target"],
                stock_scale=state["scale"],
            )
            row.update(record)
            row["confirmation_orchestrator_sha256_at_process_start"] = ORCHESTRATOR_SHA256
            row["outcome_signature_sha256"] = _outcome_signature(row)
            rows.append(row)
            if args.retention == "summary":
                lanes._prune(case_dir)
            print(
                f"[ORDERBOOK_CONFIRM] {state['state_id']} {scenario.scenario_id} seed={seed}",
                flush=True,
            )

    paired = lanes.attach_pairs(rows)
    comparisons: list[dict[str, Any]] = []
    for row in sorted(
        paired,
        key=lambda item: (
            str(item.get("state_id")),
            active.to_int(item.get("seed")),
            str(item.get("scenario_id")),
        ),
    ):
        key = (str(row["state_id"]), str(row["scenario_id"]))
        reference_signature = _outcome_signature(prior[key])
        current_signature = _outcome_signature(row)
        comparisons.append(
            {
                "state_id": key[0],
                "scenario_id": key[1],
                "screening_seed": active.to_int(prior[key].get("seed")),
                "confirmation_seed": active.to_int(row.get("seed")),
                "screening_outcome_signature_sha256": reference_signature,
                "confirmation_outcome_signature_sha256": current_signature,
                "exact_outcome_match": reference_signature == current_signature,
                "causal_effect_on_descendants": row.get(
                    "causal_effect_on_descendants"
                ),
                "causal_effect_on_client": row.get("causal_effect_on_client"),
            }
        )
    seed_invariant = bool(comparisons) and all(
        bool(row["exact_outcome_match"]) for row in comparisons
    )
    active.write_csv(root / "confirmation_metrics.csv", paired)
    active.write_csv(root / "screening_seed_exact_comparison.csv", comparisons)
    active.write_csv(root / "execution_provenance_cases.csv", provenance)
    provenance_audit = lanes.build_execution_provenance_audit(
        provenance,
        manifest,
        orchestrator_path=Path(__file__).resolve(),
    )
    active.write_json(root / "execution_provenance_audit.json", provenance_audit)
    manifest.update(
        {
            "status": (
                "complete"
                if provenance_audit["reproducibility_wording_allowed"]
                else "invalid_provenance"
            ),
            "physical_engine_run_count": len(provenance),
            "metric_row_count": len(paired),
            "execution_provenance_audit": provenance_audit,
            "new_seed_exactly_matches_screening_for_every_case": seed_invariant,
            "additional_seed_duplication_recommended": not seed_invariant,
            "interpretation": (
                "The tested engine path is seed-invariant for these paired physical, "
                "lot and client outcomes; do not duplicate identical runs."
                if seed_invariant
                else "At least one outcome changes with seed; complete a multi-seed confirmation."
            ),
            "outputs": {
                "metrics": "confirmation_metrics.csv",
                "exact_comparison": "screening_seed_exact_comparison.csv",
                "provenance": "execution_provenance_audit.json",
            },
        }
    )
    active.write_json(root / "campaign_manifest.json", manifest)
    if not provenance_audit["reproducibility_wording_allowed"]:
        raise lanes.CampaignValidationError("Confirmation provenance audit failed")
    print(f"[OK] 001848 confirmation: {root}; seed_invariant={seed_invariant}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
