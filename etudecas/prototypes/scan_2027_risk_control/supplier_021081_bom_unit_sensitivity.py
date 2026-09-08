#!/usr/bin/env python3
"""Additive BOM unit sensitivity for 021081 consumption in process 773474.

Two interpretations are compared without changing the source graph:

* the literal graph ratio, 8.94 KG per 1000 G batch; and
* a ratio divided by 1000, representing the hypothesis that the output basis
  should be 1000 kg/L-equivalent rather than 1000 g.

Neither interpretation is labelled a correction.  The status is always
"unit to validate with the industrial owner".
"""

from __future__ import annotations

import argparse
import copy
import math
import sys
from dataclasses import dataclass
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
SEED = 423081


@dataclass(frozen=True)
class UnitVariant:
    variant_id: str
    ratio_per_batch_kg: float
    label: str
    evidence_class: str


UNIT_VARIANTS = (
    UnitVariant(
        variant_id="literal_graph_ratio",
        ratio_per_batch_kg=8.94,
        label="Ratio exécuté littéralement par le graphe : 8,94 KG / 1000 G",
        evidence_class="literal_source_graph_execution",
    ),
    UnitVariant(
        variant_id="ratio_divided_by_1000_hypothesis",
        ratio_per_batch_kg=0.00894,
        label="Hypothèse de sensibilité : ratio divisé par 1000",
        evidence_class="simulated_unit_interpretation_hypothesis_not_correction",
    ),
)


def graph_with_ratio(
    source: Mapping[str, Any], variant: UnitVariant
) -> tuple[dict[str, Any], dict[str, Any]]:
    graph = copy.deepcopy(dict(source))
    matches: list[dict[str, Any]] = []
    for node in graph.get("nodes") or []:
        if not isinstance(node, dict) or str(node.get("id") or "") != "SDC-1450":
            continue
        for process in node.get("processes") or []:
            if not isinstance(process, dict) or str(process.get("id") or "") != "proc:MAKE_773474":
                continue
            for input_row in process.get("inputs") or []:
                if isinstance(input_row, dict) and str(input_row.get("item_id") or "") == base.ITEM_ID:
                    matches.append(input_row)
    if len(matches) != 1:
        raise base.CampaignValidationError(
            f"Expected one 773474/021081 BOM input, found {len(matches)}"
        )
    row = matches[0]
    before = base.to_float(row.get("ratio_per_batch"), math.nan)
    if not math.isclose(before, 8.94, rel_tol=0.0, abs_tol=1e-12):
        raise base.CampaignValidationError(
            f"Source BOM ratio differs from audited 8.94 KG: {before}"
        )
    row["ratio_per_batch"] = variant.ratio_per_batch_kg
    graph.setdefault("meta", {})["supplier_021081_bom_unit_sensitivity"] = {
        "variant_id": variant.variant_id,
        "source_ratio_per_batch_kg": before,
        "simulated_ratio_per_batch_kg": variant.ratio_per_batch_kg,
        "batch_size": 1000.0,
        "batch_size_unit": "G",
        "status": "unit_to_validate_with_industrial_owner",
        "source_graph_mutated": False,
    }
    return graph, {
        "variant_id": variant.variant_id,
        "source_ratio_per_batch_kg": before,
        "simulated_ratio_per_batch_kg": variant.ratio_per_batch_kg,
        "ratio_divisor_vs_literal": before / variant.ratio_per_batch_kg,
        "status": "unit_to_validate_with_industrial_owner",
    }


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", default=str(base.DEFAULT_GRAPH))
    parser.add_argument("--engine", default=str(base.DEFAULT_ENGINE))
    parser.add_argument("--profile", default=str(base.DEFAULT_PROFILE))
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--days", type=int, default=720)
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--retention", choices=["summary", "full"], default="summary")
    parser.add_argument("--prepare-only", action="store_true")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    source_path = Path(args.input).resolve()
    engine = Path(args.engine).resolve()
    profile = Path(args.profile).resolve()
    root = Path(args.output_dir).resolve()
    root.mkdir(parents=True, exist_ok=True)
    source = base.read_json(source_path)
    source_sha = base.sha256_file(source_path)
    states_all = layers.build_layer_states(source)
    observed_state = next(
        state for state in states_all if state.regime_id == "observed_all_layers"
    )
    joint_30d = next(state for state in states_all if state.regime_id == "joint_30d")
    states = (observed_state, joint_30d)
    scale_paths = {
        state.regime_id: layers.write_scale_input(root, state) for state in states
    }
    scenario_by_id = {
        scenario.scenario_id: scenario for scenario in base.build_scenarios()
    }
    scenarios = (
        scenario_by_id["baseline_observed_order_book"],
        scenario_by_id["all_021081__quality_hold__180"],
    )
    variant_graphs: dict[
        tuple[str, str], tuple[dict[str, Any], Path, dict[str, Any]]
    ] = {}
    variant_audits: dict[str, dict[str, Any]] = {}
    for variant in UNIT_VARIANTS:
        ratio_graph, ratio_audit = graph_with_ratio(source, variant)
        variant_audits[variant.variant_id] = {"ratio": ratio_audit, "states": {}}
        for state in states:
            graph, production_audit = layers.graph_for_state(
                ratio_graph,
                state,
                days=args.days,
            )
            graph_path = (
                root
                / "inputs"
                / f"graph_{variant.variant_id}__{state.regime_id}.json"
            )
            base.write_json(graph_path, graph)
            audit = {
                **ratio_audit,
                "absolute_state_id": state.regime_id,
                "production_layer": production_audit,
                "graph_sha256": base.sha256_file(graph_path),
                "source_graph_sha256": source_sha,
            }
            variant_graphs[(variant.variant_id, state.regime_id)] = (
                graph,
                graph_path,
                audit,
            )
            variant_audits[variant.variant_id]["states"][state.regime_id] = audit
    base.write_json(
        root / "unit_variant_audit.json",
        variant_audits,
    )
    base.write_csv(root / "state_design.csv", layers.state_rows(states))
    base.write_csv(root / "scenario_design.csv", base.scenario_design_rows(scenarios))
    manifest: dict[str, Any] = {
        "schema_version": "supplier-021081-bom-unit-sensitivity.v1",
        "status": "prepared" if args.prepare_only else "running",
        "created_at_utc": base.utc_now(),
        "orchestrator": str(Path(__file__).resolve()),
        "orchestrator_sha256_at_process_start": ORCHESTRATOR_SHA256,
        "campaign_library_sha256_at_process_start": base.PROCESS_ORCHESTRATOR_SHA256,
        "source_graph": str(source_path),
        "source_graph_sha256": source_sha,
        "source_graph_unchanged": True,
        "engine": str(engine),
        "engine_sha256": base.sha256_file(engine),
        "profile": str(profile),
        "profile_sha256": base.sha256_file(profile),
        "days": args.days,
        "seed": SEED,
        "planned_case_count": len(UNIT_VARIANTS) * len(states) * len(scenarios),
        "scientific_scope": {
            "status": "unit_to_validate_with_industrial_owner",
            "literal": "8.94 KG input per 1000 G output batch",
            "alternative": "0.00894 KG per 1000 G; factor-1000 sensitivity only",
            "correction_claim_allowed": False,
            "joint_30d_state": (
                "same absolute J0 stock targets and same 773474 production upper "
                "budget under both unit variants, derived from the literal model; "
                "it is not 30 days under the divided-ratio hypothesis"
            ),
        },
    }
    base.write_json(root / "campaign_manifest.json", manifest)
    if args.prepare_only:
        print(f"[OK] prepared unit sensitivity at {root}")
        return 0

    profile_args = base.engine_profile_args(profile)
    results: list[dict[str, Any]] = []
    gates: dict[str, Any] = {}
    for variant in UNIT_VARIANTS:
        for state in states:
            graph, graph_path, audit = variant_graphs[
                (variant.variant_id, state.regime_id)
            ]
            regime = base.StateRegime(
                regime_id=f"{variant.variant_id}__{state.regime_id}",
                label=f"{variant.label} — {state.label}",
                evidence_class=variant.evidence_class,
                opening_stock_qty_kg=state.component_target_qty_kg,
                stock_scale=state.component_scale,
                target_cover_days=state.cover_days,
            )
            raw = base._run_cases(
                source_graph=graph,
                source_graph_path=graph_path,
                engine=engine,
                profile_args=profile_args,
                output_root=root,
                scenarios=scenarios,
                seeds=[SEED],
                stage="bom_unit_sensitivity",
                days=args.days,
                workers=args.workers,
                retention=args.retention,
                metric_path=root / f"metrics_{regime.regime_id}.csv",
                opening_order_risk_mode="engine",
                state_regime=regime,
                measurement_start_stock_scale_csv=scale_paths[state.regime_id],
            )
            rows = layers.paired_layer_metrics(raw)
            for row in rows:
                row["unit_variant"] = variant.variant_id
                row["unit_evidence_class"] = variant.evidence_class
                row["ratio_per_batch_kg"] = variant.ratio_per_batch_kg
                row["absolute_state_id"] = state.regime_id
                row["source_graph_original_sha256"] = source_sha
                row["variant_graph_sha256"] = audit["graph_sha256"]
            base.write_csv(root / f"metrics_{regime.regime_id}.csv", rows)
            results.extend(rows)
            reference = next(
                row
                for row in rows
                if str(row.get("scenario_id") or "") == "baseline_observed_order_book"
            )
            gate = base.reference_flow_gate(reference)
            gate["ratio_per_batch_kg"] = variant.ratio_per_batch_kg
            gate["component_consumption_qty_kg"] = base.to_float(
                reference.get("component_consumed_qty_kg"), math.nan
            )
            gate["dynamic_production_773474_qty_g"] = base.to_float(
                reference.get("intermediate_773474_dynamic_production_qty_g"),
                math.nan,
            )
            gate["opening_production_order_773474_receipt_qty_g"] = (
                base.to_float(
                    reference.get(
                        "intermediate_773474_opening_production_order_receipt_qty_g"
                    ),
                    math.nan,
                )
            )
            gate["total_production_supply_773474_qty_g"] = base.to_float(
                reference.get(
                    "intermediate_773474_total_production_supply_qty_g"
                ),
                math.nan,
            )
            gate["dynamic_production_773474_upper_budget_qty_g"] = (
                state.production_target_qty_g
            )
            gate["dynamic_production_upper_budget_respected"] = (
                base.to_float(
                    reference.get(
                        "intermediate_773474_dynamic_production_qty_g"
                    ),
                    math.inf,
                )
                <= state.production_target_qty_g
                + max(1.0, 0.01 * state.production_target_qty_g)
                if state.production_open_order_removed
                else True
            )
            gate["opening_production_order_removed_as_configured"] = (
                base.to_float(
                    reference.get(
                        "intermediate_773474_opening_production_order_receipt_qty_g"
                    ),
                    math.inf,
                )
                <= 1e-9
                if state.production_open_order_removed
                else math.isclose(
                    base.to_float(
                        reference.get(
                            "intermediate_773474_opening_production_order_receipt_qty_g"
                        ),
                        math.nan,
                    ),
                    3_200_000.0,
                    rel_tol=0.0,
                    abs_tol=1e-6,
                )
            )
            if not gate["dynamic_production_upper_budget_respected"]:
                gate["errors"].append(
                    "773474 dynamic production exceeded configured upper budget"
                )
                gate["validated"] = False
            if not gate["opening_production_order_removed_as_configured"]:
                gate["errors"].append(
                    "773474 opening production-order receipt does not match configuration"
                )
                gate["validated"] = False
            gates[regime.regime_id] = gate
    base.write_csv(root / "unit_sensitivity_metrics.csv", results)
    base.write_json(root / "reference_flow_gates.json", gates)
    if any(not gate["validated"] for gate in gates.values()):
        manifest.update({"status": "invalid_reference", "gates": gates})
        base.write_json(root / "campaign_manifest.json", manifest)
        raise base.CampaignValidationError("Unit-sensitivity reference gate failed")

    comparison: list[dict[str, Any]] = []
    for state in states:
        for scenario in scenarios:
            by_variant = {
                str(row.get("unit_variant") or ""): row
                for row in results
                if str(row.get("absolute_state_id") or "") == state.regime_id
                and str(row.get("scenario_id") or "") == scenario.scenario_id
            }
            literal = by_variant["literal_graph_ratio"]
            alternative = by_variant["ratio_divided_by_1000_hypothesis"]
            literal_consumption = base.to_float(literal.get("component_consumed_qty_kg"))
            alternative_consumption = base.to_float(alternative.get("component_consumed_qty_kg"))
            literal_daily = literal_consumption / args.days
            alternative_daily = alternative_consumption / args.days
            literal_stock = base.to_float(
                literal.get("measurement_start_stock_after_qty_kg")
            )
            alternative_stock = base.to_float(
                alternative.get("measurement_start_stock_after_qty_kg")
            )
            comparison.append(
                {
                    "absolute_state_id": state.regime_id,
                    "scenario_id": scenario.scenario_id,
                    "literal_component_consumption_kg": literal_consumption,
                    "divided_ratio_component_consumption_kg": alternative_consumption,
                    "literal_to_divided_consumption_ratio": (
                        literal_consumption / alternative_consumption
                        if alternative_consumption > 1e-12
                        else math.inf
                    ),
                    "literal_physical_cover_days": (
                        literal_stock / literal_daily if literal_daily > 1e-12 else math.inf
                    ),
                    "divided_ratio_physical_cover_days": (
                        alternative_stock / alternative_daily
                        if alternative_daily > 1e-12
                        else math.inf
                    ),
                    "literal_product_on_due": base.to_float(
                        literal.get("product_on_due_volume_proxy")
                    ),
                    "divided_ratio_product_on_due": base.to_float(
                        alternative.get("product_on_due_volume_proxy")
                    ),
                    "product_on_due_delta_divided_minus_literal": base.to_float(
                        alternative.get("product_on_due_volume_proxy")
                    )
                    - base.to_float(literal.get("product_on_due_volume_proxy")),
                    "literal_product_released_qty": base.to_float(
                        literal.get("product_268967_released_qty")
                    ),
                    "divided_ratio_product_released_qty": base.to_float(
                        alternative.get("product_268967_released_qty")
                    ),
                    "status": "unit_to_validate_with_industrial_owner",
                    "correction_claim_allowed": False,
                }
            )
    base.write_csv(root / "unit_sensitivity_comparison.csv", comparison)
    manifest.update(
        {
            "status": "complete",
            "completed_at_utc": base.utc_now(),
            "case_count": len(results),
            "gates": gates,
            "outputs": {
                "metrics": "unit_sensitivity_metrics.csv",
                "comparison": "unit_sensitivity_comparison.csv",
                "variant_audit": "unit_variant_audit.json",
            },
        }
    )
    base.write_json(root / "campaign_manifest.json", manifest)
    print(f"[OK] BOM unit sensitivity: {root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
