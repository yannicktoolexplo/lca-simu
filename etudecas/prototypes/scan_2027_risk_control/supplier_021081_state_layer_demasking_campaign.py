#!/usr/bin/env python3
"""Separate state-layer demasking study for the 021081 -> 773474 -> 268967 chain.

The study never calls a 021081-only reduction a global lean configuration.  It
tests which inventory layer absorbs the same supplier incidents by reducing:
021081 only, 773474 only at both sites, or both layers jointly.  Every reduced
state is a simulated hypothesis and never overwrites the observed-state replay.
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


ORCHESTRATOR_SHA256 = base.sha256_file(Path(__file__).resolve())
SCREENING_SEED = 422081
CONFIRMATION_SEEDS = tuple(range(422082, 422092))
PRIORITY_COVER_LEVELS_DAYS = (90.0, 30.0)
OPTIONAL_COVER_LEVEL_DAYS = 180.0
INTERMEDIATE_DAILY_NEED_G = base.INTERMEDIATE_773474_HORIZON_NEED_G / 720.0
OBSERVED_HORIZON_PRODUCTION_773474_G = 28_800_000.0
SCENARIO_IDS = (
    "baseline_observed_order_book",
    "all_021081__usable_yield__0p1",
    "all_021081__delivery_availability__0p25",
    "all_021081__quality_hold__180",
)


@dataclass(frozen=True)
class LayerState:
    regime_id: str
    label: str
    evidence_class: str
    cover_days: float | None
    component_target_qty_kg: float
    intermediate_target_sdc_g: float
    intermediate_target_m1430_g: float
    component_scale: float
    intermediate_scale: float
    production_target_qty_g: float
    production_capacity_budget_qty_per_day_g: float | None
    production_open_order_removed: bool
    reduced_layers: tuple[str, ...]

    @property
    def intermediate_target_total_g(self) -> float:
        return self.intermediate_target_sdc_g + self.intermediate_target_m1430_g

    def engine_regime(self) -> base.StateRegime:
        return base.StateRegime(
            regime_id=self.regime_id,
            label=self.label,
            evidence_class=self.evidence_class,
            opening_stock_qty_kg=self.component_target_qty_kg,
            stock_scale=self.component_scale,
            target_cover_days=self.cover_days,
        )


def build_layer_states(
    graph: Mapping[str, Any],
    cover_levels_days: Sequence[float] = PRIORITY_COVER_LEVELS_DAYS,
) -> list[LayerState]:
    observed_component = base.observed_opening_stock_021081(graph)
    observed_sdc = base.INTERMEDIATE_773474_STOCK_SDC_G
    observed_m1430 = base.INTERMEDIATE_773474_STOCK_M1430_G
    observed_intermediate = observed_sdc + observed_m1430
    sdc_share = observed_sdc / observed_intermediate
    m1430_share = observed_m1430 / observed_intermediate
    states = [
        LayerState(
            regime_id="observed_all_layers",
            label="État observé du graphe, toutes couches inchangées",
            evidence_class="observed_graph_snapshot_state",
            cover_days=None,
            component_target_qty_kg=observed_component,
            intermediate_target_sdc_g=observed_sdc,
            intermediate_target_m1430_g=observed_m1430,
            component_scale=1.0,
            intermediate_scale=1.0,
            production_target_qty_g=OBSERVED_HORIZON_PRODUCTION_773474_G,
            production_capacity_budget_qty_per_day_g=None,
            production_open_order_removed=False,
            reduced_layers=(),
        )
    ]
    for cover_days in cover_levels_days:
        component_target = base.MODELLED_REFERENCE_DAILY_CONSUMPTION_KG * cover_days
        intermediate_total_target = INTERMEDIATE_DAILY_NEED_G * cover_days
        intermediate_scale = intermediate_total_target / observed_intermediate
        production_target = INTERMEDIATE_DAILY_NEED_G * cover_days
        for layer_id in (
            "component_only",
            "intermediate_stock_only",
            "intermediate_production_only",
            "joint",
        ):
            reduce_component = layer_id in {"component_only", "joint"}
            reduce_intermediate = layer_id in {"intermediate_stock_only", "joint"}
            reduce_production = layer_id in {
                "intermediate_production_only",
                "joint",
            }
            states.append(
                LayerState(
                    regime_id=f"{layer_id}_{int(cover_days)}d",
                    label=(
                        f"Hypothèse {int(cover_days)} jours — "
                        + {
                            "component_only": "021081 seule",
                            "intermediate_stock_only": "stock 773474 seul aux deux sites",
                            "intermediate_production_only": "production 773474 seule",
                            "joint": "021081, stock 773474 et production 773474 conjointement",
                        }[layer_id]
                    ),
                    evidence_class="simulated_state_layer_demasking_hypothesis",
                    cover_days=cover_days,
                    component_target_qty_kg=(
                        component_target if reduce_component else observed_component
                    ),
                    intermediate_target_sdc_g=(
                        intermediate_total_target * sdc_share
                        if reduce_intermediate
                        else observed_sdc
                    ),
                    intermediate_target_m1430_g=(
                        intermediate_total_target * m1430_share
                        if reduce_intermediate
                        else observed_m1430
                    ),
                    component_scale=(
                        component_target / observed_component
                        if reduce_component
                        else 1.0
                    ),
                    intermediate_scale=(
                        intermediate_scale if reduce_intermediate else 1.0
                    ),
                    production_target_qty_g=(
                        production_target
                        if reduce_production
                        else OBSERVED_HORIZON_PRODUCTION_773474_G
                    ),
                    production_capacity_budget_qty_per_day_g=(
                        production_target / 720.0 if reduce_production else None
                    ),
                    production_open_order_removed=reduce_production,
                    reduced_layers=(
                        tuple(
                            item
                            for item, active in (
                                (base.ITEM_ID, reduce_component),
                                ("stock:" + base.INTERMEDIATE_ITEM_ID, reduce_intermediate),
                                ("production:" + base.INTERMEDIATE_ITEM_ID, reduce_production),
                            )
                            if active
                        )
                    ),
                )
            )
    return states


def state_rows(states: Sequence[LayerState]) -> list[dict[str, Any]]:
    return [
        {
            "state_regime": state.regime_id,
            "label": state.label,
            "evidence_class": state.evidence_class,
            "cover_days": state.cover_days if state.cover_days is not None else "",
            "reduced_layers": ";".join(state.reduced_layers),
            "component_021081_target_qty_kg": state.component_target_qty_kg,
            "intermediate_773474_target_sdc_1450_qty_g": state.intermediate_target_sdc_g,
            "intermediate_773474_target_m_1430_qty_g": state.intermediate_target_m1430_g,
            "intermediate_773474_target_total_qty_g": state.intermediate_target_total_g,
            "component_scale": state.component_scale,
            "intermediate_scale_same_at_both_sites": state.intermediate_scale,
            "production_773474_target_upper_budget_qty_g": state.production_target_qty_g,
            "production_773474_capacity_budget_qty_per_day_g": (
                state.production_capacity_budget_qty_per_day_g
                if state.production_capacity_budget_qty_per_day_g is not None
                else ""
            ),
            "production_773474_open_order_removed": state.production_open_order_removed,
            "production_budget_interpretation": (
                "technical layer-ablation upper budget over the 720-day horizon; "
                "not an observed production policy or an operational recommendation"
                if state.production_open_order_removed
                else "source graph production layer unchanged"
            ),
            "intermediate_distribution_rule": (
                "target total split in observed J0 proportions: "
                f"SDC-1450={base.INTERMEDIATE_773474_STOCK_SDC_G / base.INTERMEDIATE_773474_TOTAL_STOCK_G:.12g}; "
                f"M-1430={base.INTERMEDIATE_773474_STOCK_M1430_G / base.INTERMEDIATE_773474_TOTAL_STOCK_G:.12g}"
            ),
            "global_lean_claim_allowed": False,
        }
        for state in states
    ]


def graph_for_state(
    source: Mapping[str, Any],
    state: LayerState,
    *,
    days: int,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Create a traceable graph overlay for the 773474 production layer.

    A reduced-production state removes the one opening 773474 production order
    and installs a finite process-capacity budget.  This is a technical ablation
    used to reveal masking, not a proposed production plan.
    """

    graph = copy.deepcopy(dict(source))
    original_opening_rows: list[dict[str, Any]] = []
    process_matches: list[dict[str, Any]] = []
    for node in graph.get("nodes") or []:
        if not isinstance(node, dict) or str(node.get("id") or "") != base.DESTINATION_ID:
            continue
        for process in node.get("processes") or []:
            if (
                isinstance(process, dict)
                and str(process.get("id") or "") == "proc:MAKE_773474"
            ):
                process_matches.append(process)
    if len(process_matches) != 1:
        raise base.CampaignValidationError(
            f"Expected one SDC-1450/MAKE_773474 process, found {len(process_matches)}"
        )
    process = process_matches[0]
    source_capacity = copy.deepcopy(process.get("capacity") or {})
    rows = base.opening_order_payload(graph)["rows"]
    for row in rows:
        if (
            isinstance(row, dict)
            and str(row.get("order_type") or "") == "production_open_order"
            and str(row.get("dst_node_id") or "") == base.DESTINATION_ID
            and str(row.get("item_id") or "") == base.INTERMEDIATE_ITEM_ID
        ):
            original_opening_rows.append(copy.deepcopy(row))
            if state.production_open_order_removed:
                row["quantity"] = 0.0
                row["supplier_021081_layer_ablation"] = (
                    "opening_773474_production_order_removed_in_hypothesis"
                )
    if len(original_opening_rows) != 1:
        raise base.CampaignValidationError(
            "Expected exactly one opening 773474 production order at SDC-1450"
        )
    if state.production_open_order_removed:
        budget = max(
            1e-6,
            float(state.production_capacity_budget_qty_per_day_g or 0.0),
        )
        process["capacity"] = {
            **source_capacity,
            "max_rate": budget,
            "uom": "G/day",
            "source": "supplier_021081_state_layer_ablation_hypothesis",
        }
    graph.setdefault("meta", {})["supplier_021081_state_layer_demasking"] = {
        "state_regime": state.regime_id,
        "source_graph_unchanged": True,
        "production_layer_reduced": state.production_open_order_removed,
        "opening_773474_production_order_source_row": original_opening_rows[0].get(
            "source_row"
        ),
        "opening_773474_production_order_original_qty_g": base.to_float(
            original_opening_rows[0].get("quantity")
        ),
        "opening_773474_production_order_simulated_qty_g": (
            0.0
            if state.production_open_order_removed
            else base.to_float(original_opening_rows[0].get("quantity"))
        ),
        "production_capacity_source": source_capacity,
        "production_capacity_simulated": copy.deepcopy(process.get("capacity") or {}),
        "production_target_upper_budget_qty_g": state.production_target_qty_g,
        "days": days,
        "interpretation": (
            "technical masking-layer ablation; not observed policy and not an action recommendation"
        ),
    }
    return graph, graph["meta"]["supplier_021081_state_layer_demasking"]


def write_scale_input(root: Path, state: LayerState) -> Path | None:
    rows: list[dict[str, Any]] = []
    if not math.isclose(state.component_scale, 1.0, rel_tol=0.0, abs_tol=1e-12):
        rows.append(
            {
                "node_id": base.DESTINATION_ID,
                "item_id": base.ITEM_ID,
                "scale": format(state.component_scale, ".15g"),
            }
        )
    if not math.isclose(state.intermediate_scale, 1.0, rel_tol=0.0, abs_tol=1e-12):
        for node_id in (base.DESTINATION_ID, "M-1430"):
            rows.append(
                {
                    "node_id": node_id,
                    "item_id": base.INTERMEDIATE_ITEM_ID,
                    "scale": format(state.intermediate_scale, ".15g"),
                }
            )
    if not rows:
        return None
    path = root / "inputs" / f"measurement_start_scale_{state.regime_id}.csv"
    base.write_csv(path, rows, ("node_id", "item_id", "scale"))
    return path


def paired_layer_metrics(
    rows: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    paired = base.attach_pairs(rows)
    baselines = {
        (str(row.get("state_regime") or ""), base.to_int(row.get("seed"))): row
        for row in paired
        if str(row.get("scenario_id") or "") == "baseline_observed_order_book"
    }
    output: list[dict[str, Any]] = []
    for row in paired:
        baseline = baselines[(str(row.get("state_regime") or ""), base.to_int(row.get("seed")))]
        result = dict(row)
        for metric in (
            "intermediate_773474_min_total_qty_g",
            "intermediate_773474_final_total_qty_g",
            "intermediate_773474_produced_qty_g",
            "intermediate_773474_dynamic_production_qty_g",
            "intermediate_773474_opening_production_order_receipt_qty_g",
            "intermediate_773474_total_production_supply_qty_g",
            "intermediate_773474_released_qty_g",
            "product_268967_produced_qty",
            "product_268967_released_qty",
        ):
            result[f"{metric}_delta_vs_paired_baseline"] = base.to_float(
                row.get(metric)
            ) - base.to_float(baseline.get(metric))
        output.append(result)
    return output


def downstream_effect(row: Mapping[str, Any]) -> bool:
    return bool(
        base.to_float(row.get("product_on_due_delta_vs_paired_baseline")) < -1e-12
        or base.to_float(
            row.get("product_backlog_qty_days_delta_vs_paired_baseline")
        )
        > 1e-9
        or abs(
            base.to_float(
                row.get("product_268967_released_qty_delta_vs_paired_baseline")
            )
        )
        > 1e-9
    )


def effect_score(row: Mapping[str, Any]) -> tuple[float, float, float, str]:
    return (
        max(0.0, -base.to_float(row.get("product_on_due_delta_vs_paired_baseline"))),
        max(
            0.0,
            base.to_float(
                row.get("product_backlog_qty_days_delta_vs_paired_baseline")
            ),
        ),
        max(
            0.0,
            -base.to_float(
                row.get("product_268967_released_qty_delta_vs_paired_baseline")
            ),
        ),
        str(row.get("scenario_id") or ""),
    )


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", default=str(base.DEFAULT_GRAPH))
    parser.add_argument("--engine", default=str(base.DEFAULT_ENGINE))
    parser.add_argument("--profile", default=str(base.DEFAULT_PROFILE))
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--days", type=int, default=720)
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--max-confirmations", type=int, default=3)
    parser.add_argument("--retention", choices=["summary", "full"], default="summary")
    parser.add_argument(
        "--include-180",
        action="store_true",
        help="Add the optional 180-day layer states after the priority 90/30 screen.",
    )
    parser.add_argument("--prepare-only", action="store_true")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    graph_path = Path(args.input).resolve()
    engine = Path(args.engine).resolve()
    profile = Path(args.profile).resolve()
    root = Path(args.output_dir).resolve()
    root.mkdir(parents=True, exist_ok=True)
    graph = base.read_json(graph_path)
    order_audit = base.audit_observed_order_book(base.observed_orders(graph))
    cover_levels = (
        (*PRIORITY_COVER_LEVELS_DAYS, OPTIONAL_COVER_LEVEL_DAYS)
        if args.include_180
        else PRIORITY_COVER_LEVELS_DAYS
    )
    states = build_layer_states(graph, cover_levels)
    scenarios_by_id = {scenario.scenario_id: scenario for scenario in base.build_scenarios()}
    scenarios = [scenarios_by_id[scenario_id] for scenario_id in SCENARIO_IDS]
    scale_inputs = {state.regime_id: write_scale_input(root, state) for state in states}
    state_graphs: dict[str, tuple[dict[str, Any], Path, dict[str, Any]]] = {}
    for state in states:
        state_graph, graph_audit = graph_for_state(graph, state, days=args.days)
        state_graph_path = root / "inputs" / f"graph_{state.regime_id}.json"
        base.write_json(state_graph_path, state_graph)
        graph_audit = {
            **graph_audit,
            "state_graph_sha256": base.sha256_file(state_graph_path),
            "source_graph_sha256": base.sha256_file(graph_path),
        }
        state_graphs[state.regime_id] = (
            state_graph,
            state_graph_path,
            graph_audit,
        )
    base.write_csv(root / "state_layer_design.csv", state_rows(states))
    base.write_csv(root / "scenario_design.csv", base.scenario_design_rows(scenarios))
    base.write_json(root / "observed_order_book_audit.json", order_audit)
    base.write_json(
        root / "production_layer_overlay_audit.json",
        {state_id: values[2] for state_id, values in state_graphs.items()},
    )
    manifest: dict[str, Any] = {
        "schema_version": "supplier-021081-state-layer-demasking.v1",
        "status": "prepared" if args.prepare_only else "running",
        "created_at_utc": base.utc_now(),
        "orchestrator": str(Path(__file__).resolve()),
        "orchestrator_sha256_at_process_start": ORCHESTRATOR_SHA256,
        "campaign_library_sha256_at_process_start": base.PROCESS_ORCHESTRATOR_SHA256,
        "engine": str(engine),
        "engine_sha256": base.sha256_file(engine),
        "source_graph": str(graph_path),
        "source_graph_sha256": base.sha256_file(graph_path),
        "profile": str(profile),
        "profile_sha256": base.sha256_file(profile),
        "days": args.days,
        "screening_seed": SCREENING_SEED,
        "state_count": len(states),
        "scenario_count_per_state": len(scenarios),
        "planned_screening_case_count": len(states) * len(scenarios),
        "priority_cover_levels_days": list(PRIORITY_COVER_LEVELS_DAYS),
        "optional_180_included": bool(args.include_180),
        "scientific_scope": {
            "observed_state": "graph snapshot; no stock scaling",
            "hypotheses": (
                "priority 90/30 days applied separately to 021081 stock, 773474 "
                "stock, 773474 production upper budget, or all layers jointly; "
                "180 days is a separate optional extension; none are observed policies"
            ),
            "intermediate_distribution": (
                "773474 target total is split proportionally to observed J0 stock "
                "between SDC-1450 and M-1430 using one common scale factor"
            ),
            "global_lean_claim_allowed": False,
            "production_ablation": (
                "the one opening 773474 production order is set to zero and the "
                "MAKE_773474 process receives a finite cumulative-output budget; "
                "technical causal diagnosis only, not an operational recommendation"
            ),
            "confirmation_rule": (
                "ten paired seeds only for screening configurations with a "
                "downstream release/service/backlog effect"
            ),
        },
    }
    base.write_json(root / "campaign_manifest.json", manifest)
    if args.prepare_only:
        print(f"[OK] prepared state-layer study at {root}")
        return 0

    profile_args = base.engine_profile_args(profile)
    screening: list[dict[str, Any]] = []
    gates: dict[str, Any] = {}
    for state in states:
        state_graph, state_graph_path, _ = state_graphs[state.regime_id]
        raw = base._run_cases(
            source_graph=state_graph,
            source_graph_path=state_graph_path,
            engine=engine,
            profile_args=profile_args,
            output_root=root,
            scenarios=scenarios,
            seeds=[SCREENING_SEED],
            stage="layer_demasking_screening",
            days=args.days,
            workers=args.workers,
            retention=args.retention,
            metric_path=root / f"screening_{state.regime_id}.csv",
            opening_order_risk_mode="engine",
            state_regime=state.engine_regime(),
            measurement_start_stock_scale_csv=scale_inputs[state.regime_id],
        )
        rows = paired_layer_metrics(raw)
        base.write_csv(root / f"screening_{state.regime_id}.csv", rows)
        screening.extend(rows)
        reference = next(
            row
            for row in rows
            if str(row.get("scenario_id") or "") == "baseline_observed_order_book"
        )
        gate = base.reference_flow_gate(reference)
        measured_component = base.to_float(
            reference.get("measurement_start_stock_after_qty_kg"), math.nan
        )
        measured_intermediate = base.to_float(
            reference.get("intermediate_773474_measurement_start_total_qty_g"),
            math.nan,
        )
        gate.update(
            {
                "configured_component_021081_qty_kg": state.component_target_qty_kg,
                "measured_component_021081_qty_kg": measured_component,
                "component_target_matches": math.isclose(
                    measured_component,
                    state.component_target_qty_kg,
                    rel_tol=0.0,
                    abs_tol=1e-3,
                ),
                "configured_intermediate_773474_total_qty_g": state.intermediate_target_total_g,
                "measured_intermediate_773474_total_qty_g": measured_intermediate,
                "intermediate_target_matches": math.isclose(
                    measured_intermediate,
                    state.intermediate_target_total_g,
                    rel_tol=0.0,
                    abs_tol=1e-2,
                ),
                "configured_dynamic_production_773474_upper_budget_qty_g": (
                    state.production_target_qty_g
                ),
                "measured_dynamic_production_773474_qty_g": base.to_float(
                    reference.get(
                        "intermediate_773474_dynamic_production_qty_g"
                    ),
                    math.nan,
                ),
                "measured_opening_production_order_773474_receipt_qty_g": (
                    base.to_float(
                        reference.get(
                            "intermediate_773474_opening_production_order_receipt_qty_g"
                        ),
                        math.nan,
                    )
                ),
                "measured_total_production_supply_773474_qty_g": base.to_float(
                    reference.get(
                        "intermediate_773474_total_production_supply_qty_g"
                    ),
                    math.nan,
                ),
                "dynamic_production_upper_budget_respected": (
                    base.to_float(
                        reference.get(
                            "intermediate_773474_dynamic_production_qty_g"
                        ),
                        math.inf,
                    )
                    <= state.production_target_qty_g + max(
                        1.0, 0.01 * state.production_target_qty_g
                    )
                    if state.production_open_order_removed
                    else True
                ),
                "opening_production_order_removed_as_configured": (
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
                ),
            }
        )
        if not gate["component_target_matches"]:
            gate["errors"].append("021081 measurement-start target mismatch")
        if not gate["intermediate_target_matches"]:
            gate["errors"].append("773474 measurement-start target mismatch")
        if not gate["dynamic_production_upper_budget_respected"]:
            gate["errors"].append(
                "773474 dynamic production exceeded configured upper budget"
            )
        if not gate["opening_production_order_removed_as_configured"]:
            gate["errors"].append(
                "773474 opening production-order receipt does not match configuration"
            )
        gate["validated"] = not gate["errors"]
        gates[state.regime_id] = gate
    base.write_csv(root / "screening_metrics.csv", screening)
    base.write_json(root / "reference_and_state_gates.json", gates)
    if any(not gate["validated"] for gate in gates.values()):
        manifest.update({"status": "invalid_reference_or_state_gate", "gates": gates})
        base.write_json(root / "campaign_manifest.json", manifest)
        raise base.CampaignValidationError("At least one state/reference gate failed")

    effect_rows = [
        row
        for row in screening
        if str(row.get("scenario_id") or "") != "baseline_observed_order_book"
        and downstream_effect(row)
    ]
    effect_rows.sort(key=effect_score, reverse=True)
    selected = effect_rows[: max(0, args.max_confirmations)]
    confirmation: list[dict[str, Any]] = []
    state_by_id = {state.regime_id: state for state in states}
    for regime_id in dict.fromkeys(str(row.get("state_regime") or "") for row in selected):
        state = state_by_id[regime_id]
        state_graph, state_graph_path, _ = state_graphs[state.regime_id]
        state_scenario_ids = {
            str(row.get("scenario_id") or "")
            for row in selected
            if str(row.get("state_regime") or "") == regime_id
        }
        state_scenarios = [
            scenarios_by_id["baseline_observed_order_book"],
            *(scenarios_by_id[scenario_id] for scenario_id in sorted(state_scenario_ids)),
        ]
        raw = base._run_cases(
            source_graph=state_graph,
            source_graph_path=state_graph_path,
            engine=engine,
            profile_args=profile_args,
            output_root=root,
            scenarios=state_scenarios,
            seeds=CONFIRMATION_SEEDS,
            stage="layer_demasking_confirmation_paired",
            days=args.days,
            workers=args.workers,
            retention=args.retention,
            metric_path=root / f"confirmation_{regime_id}.csv",
            opening_order_risk_mode="engine",
            state_regime=state.engine_regime(),
            measurement_start_stock_scale_csv=scale_inputs[state.regime_id],
        )
        rows = paired_layer_metrics(raw)
        base.write_csv(root / f"confirmation_{regime_id}.csv", rows)
        confirmation.extend(rows)
    base.write_csv(root / "confirmation_metrics.csv", confirmation)

    effect_table: list[dict[str, Any]] = []
    for state in states:
        state_rows_ = [
            row
            for row in screening
            if str(row.get("state_regime") or "") == state.regime_id
            and str(row.get("scenario_id") or "") != "baseline_observed_order_book"
        ]
        effect_table.append(
            {
                "state_regime": state.regime_id,
                "cover_days": state.cover_days if state.cover_days is not None else "",
                "reduced_layers": ";".join(state.reduced_layers),
                "tested_incident_count": len(state_rows_),
                "incidents_with_downstream_effect": sum(
                    downstream_effect(row) for row in state_rows_
                ),
                "max_on_due_service_loss_percentage_points": 100.0
                * max(
                    (
                        max(
                            0.0,
                            -base.to_float(
                                row.get("product_on_due_delta_vs_paired_baseline")
                            ),
                        )
                        for row in state_rows_
                    ),
                    default=0.0,
                ),
                "max_incremental_backlog_qty_days": max(
                    (
                        base.to_float(
                            row.get(
                                "product_backlog_qty_days_delta_vs_paired_baseline"
                            )
                        )
                        for row in state_rows_
                    ),
                    default=0.0,
                ),
                "max_released_product_loss_qty": max(
                    (
                        max(
                            0.0,
                            -base.to_float(
                                row.get(
                                    "product_268967_released_qty_delta_vs_paired_baseline"
                                )
                            ),
                        )
                        for row in state_rows_
                    ),
                    default=0.0,
                ),
                "dynamic_production_773474_upper_budget_qty_g": (
                    state.production_target_qty_g
                ),
                "production_773474_open_order_removed": (
                    state.production_open_order_removed
                ),
                "interpretation": (
                    "downstream effect in at least one tested incident"
                    if any(downstream_effect(row) for row in state_rows_)
                    else "tested state still masks downstream effect; not resilience"
                ),
            }
        )
    base.write_csv(root / "layer_effect_table.csv", effect_table)
    manifest.update(
        {
            "status": "complete",
            "completed_at_utc": base.utc_now(),
            "screening_case_count": len(screening),
            "screening_downstream_effect_case_count": len(effect_rows),
            "selected_confirmation_case_keys": [
                f"{row.get('state_regime')}/{row.get('scenario_id')}"
                for row in selected
            ],
            "confirmation_case_count": len(confirmation),
            "gates": gates,
            "outputs": {
                "screening": "screening_metrics.csv",
                "confirmation": "confirmation_metrics.csv",
                "layer_effect_table": "layer_effect_table.csv",
                "state_design": "state_layer_design.csv",
            },
        }
    )
    base.write_json(root / "campaign_manifest.json", manifest)
    print(f"[OK] state-layer demasking campaign: {root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
