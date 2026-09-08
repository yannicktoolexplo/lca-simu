#!/usr/bin/env python3
"""Map the 344135 supplier-capacity cliff around one standard order lot.

This is an additive, deliberately narrow supplement to the supplier-service
landscape campaign.  It does not change the simulation engine or the V4
campaign.  It keeps the V4 protocol and varies only the temporary capacity of
the 344135 lane during J45--J224.

The tested reference capacity (300,000 UN/day) is a calibration hypothesis.
The 120,000 UN standard order quantity comes from the reference graph.  In the
current engine, supplier pulls are executed in whole standard-order lots.  A
daily capacity below 120,000 UN therefore cannot execute one such lot.  The
resulting 0.40 ratio is an engine lot/capacity gate, not a claimed physical
discontinuity at the real supplier.
"""

from __future__ import annotations

import argparse
import importlib
import math
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

landscape = importlib.import_module(
    "etudecas.prototypes.scan_2027_risk_control.supplier_service_landscape_campaign"
)


SCHEMA_VERSION = "etudecas.supplier_capacity_lot_threshold_campaign.v1"
CHAIN_ID = "344135_m1430_268967"
SUPPLIER_ID = "SDC-VD0993480A"
ITEM_ID = "item:344135"
DESTINATION_ID = "M-1430"
TARGET_PRODUCT_ID = "268967"
CLIENT_NODE_ID = "C-XXXXX"
REFERENCE_CAPACITY_QTY_PER_DAY = 300_000.0
EXPECTED_STANDARD_ORDER_QTY = 120_000.0
CAPACITY_RATIOS = (1.00, 0.60, 0.50, 0.41, 0.40, 0.39, 0.35)
DEFAULT_CONFIRMATION_RATIOS = (0.41, 0.40, 0.39)
SCREENING_SEED = 330281
MEASURED_DAYS = 720
ENGINE_LIMITATION_FR = (
    "Courbe discontinue liée au moteur : l'approvisionnement est exécuté en "
    "nombres entiers de lots standard de 120 000 UN. Sous 120 000 UN/j, le "
    "moteur ne peut lancer aucun lot ce jour-là. Cette marche numérique ne "
    "prouve pas que le fournisseur réel se comporte de façon discontinue."
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def default_output_dir() -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return (
        landscape.ARTIFACT_PARENT
        / "supplier_capacity_lot_threshold_344135"
        / stamp
    )


def _required_file(path: Path, label: str) -> Path:
    resolved = path.resolve()
    if not resolved.is_file():
        raise FileNotFoundError(f"Missing {label}: {resolved}")
    return resolved


def values_equal(left: float, right: float) -> bool:
    return math.isclose(float(left), float(right), rel_tol=0.0, abs_tol=1e-12)


def ratio_code(ratio: float) -> str:
    return format(float(ratio), ".12g").replace(".", "p")


def parse_ratios(specification: str) -> list[float]:
    ratios: list[float] = []
    for raw in str(specification or "").split(","):
        chunk = raw.strip()
        if not chunk:
            continue
        ratio = float(chunk)
        if ratio <= 0.0:
            raise ValueError("Confirmation capacity ratios must be positive")
        if not any(values_equal(ratio, candidate) for candidate in CAPACITY_RATIOS):
            raise ValueError(
                f"Confirmation ratio {ratio:g} is outside the fixed screening grid"
            )
        if not any(values_equal(ratio, existing) for existing in ratios):
            ratios.append(ratio)
    if not ratios:
        raise ValueError("At least one confirmation ratio is required")
    return ratios


def build_threshold_scenarios() -> list[landscape.Scenario]:
    """Return the seven fixed ratios; ratio 1 reuses the shared baseline."""

    scenarios: list[landscape.Scenario] = []
    for index, ratio in enumerate(CAPACITY_RATIOS):
        alias = values_equal(ratio, 1.0)
        scenario_id = f"344135_capacity_lot_threshold__ratio_{ratio_code(ratio)}"
        scenarios.append(
            landscape.Scenario(
                scenario_id=scenario_id,
                execution_scenario_id="baseline_nominal" if alias else scenario_id,
                chain_id=CHAIN_ID,
                mechanism_key="capacity",
                level_index=index,
                level_code=f"ratio_{ratio_code(ratio)}",
                level_label=f"Capacité à {ratio:.0%} de 300 000 UN/j",
                value=float(ratio),
                unit="ratio",
                target_product_id=TARGET_PRODUCT_ID,
                client_node_id=CLIENT_NODE_ID,
                is_baseline_alias=alias,
            )
        )
    return scenarios


def baseline_scenario() -> landscape.Scenario:
    return landscape.build_scenario_design()[0]


def executable_scenarios(
    scenarios: Sequence[landscape.Scenario],
) -> list[landscape.Scenario]:
    return [scenario for scenario in scenarios if not scenario.is_baseline_alias]


def scenario_for_ratio(
    scenarios: Sequence[landscape.Scenario], ratio: float
) -> landscape.Scenario:
    return next(
        scenario
        for scenario in scenarios
        if values_equal(scenario.value, ratio)
    )


def lot_slots_per_day(capacity_qty_per_day: float, standard_order_qty: float) -> int:
    if standard_order_qty <= 0.0:
        raise ValueError("standard_order_qty must be positive")
    return max(
        0,
        int(math.floor((float(capacity_qty_per_day) / standard_order_qty) + 1e-9)),
    )


def capacity_regime(ratio: float, threshold_ratio: float) -> str:
    if values_equal(ratio, threshold_ratio):
        return "au_seuil_un_lot"
    if ratio > threshold_ratio:
        return "au_dessus_du_seuil"
    return "sous_le_seuil_aucun_lot"


def audit_graph_standard_order(graph: Mapping[str, Any]) -> dict[str, Any]:
    """Prove the one-lane 120,000 UN input without inferring it from results."""

    matches = [
        edge
        for edge in (graph.get("edges") or [])
        if str(edge.get("from") or "") == SUPPLIER_ID
        and str(edge.get("to") or "") == DESTINATION_ID
        and ITEM_ID in {str(item) for item in (edge.get("items") or [])}
    ]
    if len(matches) != 1:
        raise ValueError(
            "Expected exactly one 344135 supplier lane in the reference graph; "
            f"found {len(matches)}"
        )
    edge = matches[0]
    attrs = edge.get("attrs") or {}
    lot_qty = landscape.to_float(attrs.get("standard_order_qty"), 0.0)
    if not values_equal(lot_qty, EXPECTED_STANDARD_ORDER_QTY):
        raise ValueError(
            "Reference graph standard order quantity changed: "
            f"expected {EXPECTED_STANDARD_ORDER_QTY:g}, found {lot_qty:g}"
        )
    lot_uom = str(attrs.get("standard_order_uom") or "")
    if lot_uom != "UN":
        raise ValueError(f"Unexpected 344135 standard-order unit: {lot_uom!r}")
    threshold_ratio = lot_qty / REFERENCE_CAPACITY_QTY_PER_DAY
    if not values_equal(threshold_ratio, 0.40):
        raise ValueError(f"Unexpected arithmetic threshold: {threshold_ratio:g}")
    return {
        "validated": True,
        "edge_id": str(edge.get("id") or ""),
        "supplier_id": SUPPLIER_ID,
        "item_id": ITEM_ID,
        "destination_id": DESTINATION_ID,
        "standard_order_qty": lot_qty,
        "standard_order_uom": lot_uom,
        "standard_order_source": str(attrs.get("source_workbook") or "reference_graph"),
        "reference_capacity_qty_per_day": REFERENCE_CAPACITY_QTY_PER_DAY,
        "arithmetic_one_lot_threshold_ratio": threshold_ratio,
        "proof": "120000 / 300000 = 0.40",
    }


def audit_engine_integer_lot_gate(engine: Path) -> dict[str, Any]:
    """Locate the current whole-lot capacity gate and bind it to an engine hash."""

    lines = engine.read_text(encoding="utf-8").splitlines()
    required_fragments = (
        "feasible_units = int(math.floor((max_feasible_qty / standard_order_qty) + 1e-9))",
        "if feasible_units <= 0:",
        "pull_qty = min(target_units, feasible_units) * standard_order_qty",
    )
    locations: dict[str, int] = {}
    for fragment in required_fragments:
        indexes = [index + 1 for index, line in enumerate(lines) if fragment in line]
        if len(indexes) != 1:
            raise ValueError(
                "Engine whole-lot capacity semantics changed; expected exactly one "
                f"occurrence of {fragment!r}, found {len(indexes)}"
            )
        locations[fragment] = indexes[0]
    if not (
        locations[required_fragments[0]]
        < locations[required_fragments[1]]
        < locations[required_fragments[2]]
    ):
        raise ValueError("Engine whole-lot capacity rule is no longer in expected order")
    return {
        "validated": True,
        "engine": str(engine.resolve()),
        "engine_sha256": landscape.sha256_file(engine),
        "rule_line_numbers": locations,
        "semantics": (
            "feasible whole lots per day = floor(remaining daily capacity / "
            "standard order quantity); zero feasible lots means zero pull"
        ),
        "curve_is_discontinuous_by_construction": True,
        "industrial_limitation_fr": ENGINE_LIMITATION_FR,
    }


def validate_reference_capacity(
    physical_capacity_map: Mapping[tuple[str, str, str], float]
) -> float:
    lane_key = (SUPPLIER_ID, ITEM_ID, DESTINATION_ID)
    capacity = float(physical_capacity_map.get(lane_key, 0.0))
    if not values_equal(capacity, REFERENCE_CAPACITY_QTY_PER_DAY):
        raise ValueError(
            "The V4 physical reference for 344135 must remain exactly 300000 UN/day; "
            f"found {capacity:g}"
        )
    return capacity


def threshold_proof_rows(
    graph_audit: Mapping[str, Any], engine_audit: Mapping[str, Any]
) -> list[dict[str, Any]]:
    threshold = EXPECTED_STANDARD_ORDER_QTY / REFERENCE_CAPACITY_QTY_PER_DAY
    return [
        {
            "supplier_id": SUPPLIER_ID,
            "item_id": ITEM_ID,
            "destination_id": DESTINATION_ID,
            "target_product_id": TARGET_PRODUCT_ID,
            "graph_edge_id": graph_audit["edge_id"],
            "standard_order_qty": EXPECTED_STANDARD_ORDER_QTY,
            "standard_order_uom": "UN",
            "capacity_reference_qty_per_day": REFERENCE_CAPACITY_QTY_PER_DAY,
            "one_lot_threshold_ratio": threshold,
            "arithmetic_proof": "120000 / 300000 = 0.40",
            "engine_rule_validated": engine_audit["validated"],
            "curve_type": "discrete_engine_integer_lot_gate",
            "is_physical_supplier_cliff": False,
            "interpretation_fr": ENGINE_LIMITATION_FR,
        }
    ]


def scenario_design_rows(
    scenarios: Sequence[landscape.Scenario],
) -> list[dict[str, Any]]:
    threshold = EXPECTED_STANDARD_ORDER_QTY / REFERENCE_CAPACITY_QTY_PER_DAY
    rows: list[dict[str, Any]] = []
    for scenario in scenarios:
        capacity = round(REFERENCE_CAPACITY_QTY_PER_DAY * scenario.value, 6)
        slots = lot_slots_per_day(capacity, EXPECTED_STANDARD_ORDER_QTY)
        rows.append(
            {
                "scenario_id": scenario.scenario_id,
                "execution_scenario_id": scenario.execution_scenario_id,
                "capacity_ratio": scenario.value,
                "capacity_qty_per_day": capacity,
                "capacity_reference_qty_per_day": REFERENCE_CAPACITY_QTY_PER_DAY,
                "capacity_reference_class": "calibration_hypothesis_not_observed_capacity",
                "standard_order_qty": EXPECTED_STANDARD_ORDER_QTY,
                "standard_order_uom": "UN",
                "integer_lot_slots_per_day": slots,
                "one_standard_lot_executable_by_engine": slots >= 1,
                "capacity_regime": capacity_regime(scenario.value, threshold),
                "is_baseline_alias": scenario.is_baseline_alias,
                "supplier_id": SUPPLIER_ID,
                "item_id": ITEM_ID,
                "destination_id": DESTINATION_ID,
                "target_product_id": TARGET_PRODUCT_ID,
                "incident_start_day": landscape.INCIDENT_START_DAY,
                "incident_end_day": (
                    landscape.INCIDENT_START_DAY
                    + landscape.INCIDENT_DURATION_DAYS
                    - 1
                ),
                "curve_type": "discrete_engine_integer_lot_gate",
                "is_physical_supplier_cliff": False,
                "industrial_interpretation_fr": ENGINE_LIMITATION_FR,
            }
        )
    return rows


def build_risk_inputs(
    output_dir: Path,
    scenarios: Sequence[landscape.Scenario],
) -> dict[str, tuple[Path, int]]:
    result: dict[str, tuple[Path, int]] = {}
    for scenario in executable_scenarios(scenarios):
        rows = landscape.build_risk_event_rows(scenario, MEASURED_DAYS)
        path = output_dir / "inputs" / "risk_events" / f"{scenario.scenario_id}.csv"
        landscape.write_risk_csv(path, rows)
        result[scenario.scenario_id] = (path, len(rows))
    return result


def _mean(rows: Sequence[Mapping[str, Any]], field: str) -> float:
    values = [landscape.to_float(row.get(field), math.nan) for row in rows]
    clean = [value for value in values if math.isfinite(value)]
    return sum(clean) / len(clean) if clean else math.nan


def _min(rows: Sequence[Mapping[str, Any]], field: str) -> float:
    values = [landscape.to_float(row.get(field), math.nan) for row in rows]
    clean = [value for value in values if math.isfinite(value)]
    return min(clean) if clean else math.nan


def _max(rows: Sequence[Mapping[str, Any]], field: str) -> float:
    values = [landscape.to_float(row.get(field), math.nan) for row in rows]
    clean = [value for value in values if math.isfinite(value)]
    return max(clean) if clean else math.nan


def metric_rows_for_ratio(
    metric_rows: Sequence[Mapping[str, Any]],
    scenario: landscape.Scenario,
) -> list[dict[str, Any]]:
    """Normalize the ratio-1 baseline onto the 268967 target product."""

    source_id = "baseline_nominal" if scenario.is_baseline_alias else scenario.scenario_id
    selected = [row for row in metric_rows if str(row.get("scenario_id")) == source_id]
    normalized: list[dict[str, Any]] = []
    for source in selected:
        row = dict(source)
        if scenario.is_baseline_alias:
            prefix = f"baseline_chain__{CHAIN_ID}__"
            row["product_service_horizon"] = landscape.to_float(
                source.get(f"fill_rate_{TARGET_PRODUCT_ID}"), math.nan
            )
            row["product_on_due_date_proxy"] = landscape.to_float(
                source.get(f"on_due_volume_proxy_{TARGET_PRODUCT_ID}"), math.nan
            )
            row["target_backlog_qty_days"] = landscape.to_float(
                source.get(f"backlog_qty_days_{TARGET_PRODUCT_ID}"), math.nan
            )
            row["target_worst_rolling_28d_on_due_proxy"] = landscape.to_float(
                source.get(
                    f"worst_rolling_28d_on_due_proxy_{TARGET_PRODUCT_ID}"
                ),
                math.nan,
            )
            row["supplier_incident_shipped_qty"] = landscape.to_float(
                source.get(f"{prefix}incident_shipped_qty"), math.nan
            )
            row["supplier_incident_flow_coverage_vs_paired_baseline"] = 1.0
            row["incremental_target_backlog_qty_days"] = 0.0
            row["target_on_due_date_proxy_delta_vs_paired_baseline"] = 0.0
        normalized.append(row)
    return normalized


def same_j0_for_rows(
    rows: Sequence[Mapping[str, Any]], baseline_rows: Sequence[Mapping[str, Any]]
) -> bool:
    baseline_hashes = {
        landscape.to_int(row.get("seed"), -1): str(row.get("j0_state_sha256") or "")
        for row in baseline_rows
    }
    return bool(rows) and all(
        str(row.get("j0_state_sha256") or "")
        == baseline_hashes.get(landscape.to_int(row.get("seed"), -1), "")
        and bool(str(row.get("j0_state_sha256") or ""))
        for row in rows
    )


def _stage_statistics(
    rows: Sequence[Mapping[str, Any]],
    baseline_rows: Sequence[Mapping[str, Any]],
    prefix: str,
) -> dict[str, Any]:
    if not rows:
        return {
            f"{prefix}_n_seeds": 0,
            f"{prefix}_seeds": "",
            f"{prefix}_same_j0_as_paired_baseline": "",
        }
    seeds = sorted({landscape.to_int(row.get("seed"), -1) for row in rows})
    fields = (
        "product_service_horizon",
        "product_on_due_date_proxy",
        "target_backlog_qty_days",
        "incremental_target_backlog_qty_days",
        "target_worst_rolling_28d_on_due_proxy",
        "supplier_incident_shipped_qty",
        "supplier_incident_flow_coverage_vs_paired_baseline",
        "supplier_incident_capacity_binding_days",
        "target_on_due_date_proxy_delta_vs_paired_baseline",
    )
    result: dict[str, Any] = {
        f"{prefix}_n_seeds": len(seeds),
        f"{prefix}_seeds": "|".join(str(seed) for seed in seeds),
        f"{prefix}_same_j0_as_paired_baseline": same_j0_for_rows(
            rows, baseline_rows
        ),
    }
    for field in fields:
        result[f"{prefix}_{field}_mean"] = _mean(rows, field)
        result[f"{prefix}_{field}_min"] = _min(rows, field)
        result[f"{prefix}_{field}_max"] = _max(rows, field)
    return result


def build_threshold_curve_rows(
    screening_rows: Sequence[Mapping[str, Any]],
    confirmation_rows: Sequence[Mapping[str, Any]],
    scenarios: Sequence[landscape.Scenario],
) -> list[dict[str, Any]]:
    threshold = EXPECTED_STANDARD_ORDER_QTY / REFERENCE_CAPACITY_QTY_PER_DAY
    screening_baselines = [
        row for row in screening_rows if str(row.get("scenario_id")) == "baseline_nominal"
    ]
    confirmation_baselines = [
        row
        for row in confirmation_rows
        if str(row.get("scenario_id")) == "baseline_nominal"
    ]
    output: list[dict[str, Any]] = []
    previous_on_due = math.nan
    previous_ratio = math.nan
    for scenario in scenarios:
        capacity = round(REFERENCE_CAPACITY_QTY_PER_DAY * scenario.value, 6)
        screen = metric_rows_for_ratio(screening_rows, scenario)
        confirm = metric_rows_for_ratio(confirmation_rows, scenario)
        row: dict[str, Any] = {
            "scenario_id": scenario.scenario_id,
            "execution_scenario_id": scenario.execution_scenario_id,
            "capacity_ratio": scenario.value,
            "capacity_qty_per_day": capacity,
            "standard_order_qty": EXPECTED_STANDARD_ORDER_QTY,
            "integer_lot_slots_per_day": lot_slots_per_day(
                capacity, EXPECTED_STANDARD_ORDER_QTY
            ),
            "one_standard_lot_executable_by_engine": capacity + 1e-9
            >= EXPECTED_STANDARD_ORDER_QTY,
            "capacity_regime": capacity_regime(scenario.value, threshold),
            "crosses_one_lot_gate_from_previous_ratio": (
                math.isfinite(previous_ratio)
                and previous_ratio >= threshold
                and scenario.value < threshold
            ),
            "curve_type": "discrete_engine_integer_lot_gate",
            "is_physical_supplier_cliff": False,
            "industrial_interpretation_fr": ENGINE_LIMITATION_FR,
            **_stage_statistics(screen, screening_baselines, "screening"),
            **_stage_statistics(confirm, confirmation_baselines, "confirmation"),
        }
        current_on_due = landscape.to_float(
            row.get("screening_product_on_due_date_proxy_mean"), math.nan
        )
        row["screening_on_due_change_from_previous_higher_ratio"] = (
            current_on_due - previous_on_due
            if math.isfinite(current_on_due) and math.isfinite(previous_on_due)
            else math.nan
        )
        output.append(row)
        previous_on_due = current_on_due
        previous_ratio = scenario.value
    return output


def j0_audit(
    screening_rows: Sequence[Mapping[str, Any]],
    confirmation_rows: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    by_stage: dict[str, Any] = {}
    all_ok = True
    for stage, rows in (
        ("screening", screening_rows),
        ("confirmation", confirmation_rows),
    ):
        if not rows:
            by_stage[stage] = {"executed": False, "same_j0_all_cases": None}
            continue
        baseline_by_seed = {
            landscape.to_int(row.get("seed"), -1): str(
                row.get("j0_state_sha256") or ""
            )
            for row in rows
            if str(row.get("scenario_id")) == "baseline_nominal"
        }
        cases = [
            row for row in rows if str(row.get("scenario_id")) != "baseline_nominal"
        ]
        ok = bool(baseline_by_seed) and all(
            str(row.get("j0_state_sha256") or "")
            == baseline_by_seed.get(landscape.to_int(row.get("seed"), -1), "")
            and bool(str(row.get("j0_state_sha256") or ""))
            for row in cases
        )
        all_ok = all_ok and ok
        by_stage[stage] = {
            "executed": True,
            "same_j0_all_cases": ok,
            "baseline_j0_sha256_by_seed": {
                str(seed): digest for seed, digest in sorted(baseline_by_seed.items())
            },
            "stressed_case_count": len(cases),
        }
    return {"validated": all_ok, "by_stage": by_stage}


def threshold_observation(curve_rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    by_ratio = {
        float(row["capacity_ratio"]): row
        for row in curve_rows
    }
    at_gate = by_ratio[0.40]
    below_gate = by_ratio[0.39]
    shipped_at = landscape.to_float(
        at_gate.get("screening_supplier_incident_shipped_qty_mean"), math.nan
    )
    shipped_below = landscape.to_float(
        below_gate.get("screening_supplier_incident_shipped_qty_mean"), math.nan
    )
    on_due_at = landscape.to_float(
        at_gate.get("screening_product_on_due_date_proxy_mean"), math.nan
    )
    on_due_below = landscape.to_float(
        below_gate.get("screening_product_on_due_date_proxy_mean"), math.nan
    )
    return {
        "arithmetic_threshold_ratio": 0.40,
        "capacity_at_threshold_qty_per_day": 120_000.0,
        "capacity_immediately_below_test_qty_per_day": 117_000.0,
        "whole_lot_gate_proven_from_inputs_and_engine": True,
        "screening_supplier_shipped_qty_at_0p40": shipped_at,
        "screening_supplier_shipped_qty_at_0p39": shipped_below,
        "screening_zero_flow_below_gate_observed": (
            math.isfinite(shipped_below) and shipped_below <= 1e-9
        ),
        "screening_product_on_due_at_0p40": on_due_at,
        "screening_product_on_due_at_0p39": on_due_below,
        "screening_product_effect_step_observed": (
            math.isfinite(on_due_at)
            and math.isfinite(on_due_below)
            and not values_equal(on_due_at, on_due_below)
        ),
        "interpretation_fr": ENGINE_LIMITATION_FR,
    }


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=landscape.REPO_ROOT)
    parser.add_argument("--output-dir", type=Path, default=None)
    parser.add_argument("--graph", type=Path, default=landscape.DEFAULT_GRAPH)
    parser.add_argument("--engine", type=Path, default=landscape.DEFAULT_ENGINE)
    parser.add_argument(
        "--supplier-floors",
        type=Path,
        default=(
            landscape.DEFAULT_BASELINE_RUN
            / "data"
            / "supplier_capacity_calibration_measured_period.csv"
        ),
    )
    parser.add_argument("--engine-profile", type=Path, default=landscape.DEFAULT_PROFILE)
    parser.add_argument("--scenario-id", default="scn:BASE")
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument(
        "--retention", choices=("summary",), default="summary"
    )
    parser.add_argument(
        "--confirm-threshold",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Confirm selected ratios with paired seeds after the one-seed screen.",
    )
    parser.add_argument("--confirmation-ratios", default="0.41,0.40,0.39")
    parser.add_argument("--confirmation-seeds", default="330282-330291")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    if args.workers <= 0:
        raise ValueError("--workers must be positive")
    repo_root = args.repo_root.resolve()
    output_dir = (args.output_dir or default_output_dir()).resolve()
    graph = _required_file(args.graph, "reference graph")
    engine = _required_file(args.engine, "simulation engine")
    floors_source = _required_file(args.supplier_floors, "supplier floors")
    engine_profile = _required_file(args.engine_profile, "engine profile")

    graph_payload = landscape.read_json(graph)
    graph_audit = audit_graph_standard_order(graph_payload)
    engine_audit = audit_engine_integer_lot_gate(engine)
    prepared_rows, floor_audit = landscape.build_prepared_physical_floor_rows(
        landscape.read_csv_rows(floors_source)
    )
    physical_capacity_map = landscape.physical_capacity_by_lane(prepared_rows)
    validate_reference_capacity(physical_capacity_map)
    profile_args = tuple(landscape.engine_profile_args(engine_profile))
    scenarios = build_threshold_scenarios()
    stressed_scenarios = executable_scenarios(scenarios)
    confirmation_ratios = parse_ratios(args.confirmation_ratios)
    confirmation_seeds = landscape.parse_seeds(args.confirmation_seeds)
    if SCREENING_SEED in confirmation_seeds:
        raise ValueError("The screening seed must not be repeated in confirmation")

    prepared_floors = output_dir / "inputs" / "prepared_physical_supplier_floors.csv"
    design_path = output_dir / "scenario_design.csv"
    proof_path = output_dir / "threshold_proof.csv"
    screening_path = output_dir / "screening_metrics.csv"
    confirmation_path = output_dir / "confirmation_metrics.csv"
    curve_path = output_dir / "threshold_curve.csv"
    manifest_path = output_dir / "campaign_manifest.json"

    signature_payload = {
        "schema_version": SCHEMA_VERSION,
        "graph": str(graph),
        "graph_sha256": landscape.sha256_file(graph),
        "engine": str(engine),
        "engine_sha256": landscape.sha256_file(engine),
        "supplier_floors_source": str(floors_source),
        "supplier_floors_source_sha256": landscape.sha256_file(floors_source),
        "engine_profile": str(engine_profile),
        "engine_profile_sha256": landscape.sha256_file(engine_profile),
        "screening_seed": SCREENING_SEED,
        "confirmation_enabled": bool(args.confirm_threshold),
        "confirmation_ratios": confirmation_ratios,
        "confirmation_seeds": confirmation_seeds,
        "workers_not_in_signature": True,
        "measured_days": MEASURED_DAYS,
        "warmup_days": landscape.WARMUP_DAYS,
        "incident_start_day": landscape.INCIDENT_START_DAY,
        "incident_end_day": (
            landscape.INCIDENT_START_DAY + landscape.INCIDENT_DURATION_DAYS - 1
        ),
        "capacity_ratios": list(CAPACITY_RATIOS),
        "capacity_reference_qty_per_day": REFERENCE_CAPACITY_QTY_PER_DAY,
        "standard_order_qty": EXPECTED_STANDARD_ORDER_QTY,
        "managed_protocol_args": list(landscape.CAMPAIGN_PROTOCOL_ARGS),
        "scenario_id": str(args.scenario_id),
        "retention": str(args.retention),
    }
    signature = landscape.campaign_signature(signature_payload)
    if output_dir.exists() and any(output_dir.iterdir()):
        if not manifest_path.is_file():
            raise RuntimeError(
                f"Refusing non-empty output without campaign manifest: {output_dir}"
            )
        previous = landscape.read_json(manifest_path)
        if str(previous.get("campaign_signature") or "") != signature:
            raise RuntimeError(
                "Existing threshold output has a different signature; choose a new "
                "additive --output-dir."
            )
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest: dict[str, Any] = {
        **signature_payload,
        "campaign_signature": signature,
        "status": "running",
        "started_or_resumed_at_utc": utc_now(),
        "output_dir": str(output_dir),
        "scope": {
            "supplier_id": SUPPLIER_ID,
            "item_id": ITEM_ID,
            "destination_id": DESTINATION_ID,
            "target_product_id": TARGET_PRODUCT_ID,
            "only_temporary_supplier_capacity_is_varied": True,
            "graph_mutated": False,
            "demand_mutated": False,
            "factory_capacity_mutated": False,
        },
        "graph_lot_audit": graph_audit,
        "engine_integer_lot_gate_audit": engine_audit,
        "physical_floor_audit": floor_audit,
        "curve_semantics": {
            "continuous_curve": False,
            "type": "discrete_engine_integer_lot_gate",
            "is_real_supplier_response_curve": False,
            "limitation_fr": ENGINE_LIMITATION_FR,
        },
        "outputs": {
            "scenario_design_csv": str(design_path),
            "threshold_proof_csv": str(proof_path),
            "screening_metrics_csv": str(screening_path),
            "confirmation_metrics_csv": (
                str(confirmation_path) if args.confirm_threshold else ""
            ),
            "threshold_curve_csv": str(curve_path),
        },
    }
    landscape.write_json_atomic(manifest_path, manifest)
    landscape.write_csv_atomic(prepared_floors, prepared_rows)
    landscape.write_csv_atomic(design_path, scenario_design_rows(scenarios))
    landscape.write_csv_atomic(
        proof_path, threshold_proof_rows(graph_audit, engine_audit)
    )

    config = landscape.RunConfig(
        repo_root=repo_root,
        output_dir=output_dir,
        engine=engine,
        graph=graph,
        supplier_floors=prepared_floors,
        factory_capacities=None,
        profile_args=profile_args,
        scenario_id=str(args.scenario_id),
        days=MEASURED_DAYS,
        retention="summary",
        physical_capacity_by_lane=physical_capacity_map,
    )
    try:
        risk_inputs = build_risk_inputs(output_dir, scenarios)
        screening_rows = landscape.run_stage_baselines(
            config,
            stage="screening",
            seeds=[SCREENING_SEED],
            metric_path=screening_path,
            existing_rows=landscape.read_csv_rows(screening_path),
            workers=args.workers,
        )
        screening_rows = landscape.run_stage_scenarios(
            config,
            stage="screening",
            scenarios=stressed_scenarios,
            seeds=[SCREENING_SEED],
            metric_path=screening_path,
            rows=screening_rows,
            baseline_rows=screening_rows,
            risk_inputs=risk_inputs,
            workers=args.workers,
        )

        confirmation_rows: list[dict[str, Any]] = []
        if args.confirm_threshold:
            selected = [
                scenario_for_ratio(scenarios, ratio)
                for ratio in confirmation_ratios
            ]
            if any(scenario.is_baseline_alias for scenario in selected):
                raise ValueError("Ratio 1 must not be listed as a stressed confirmation")
            confirmation_rows = landscape.run_stage_baselines(
                config,
                stage="confirmation",
                seeds=confirmation_seeds,
                metric_path=confirmation_path,
                existing_rows=landscape.read_csv_rows(confirmation_path),
                fallback_rows=screening_rows,
                workers=args.workers,
            )
            confirmation_rows = landscape.run_stage_scenarios(
                config,
                stage="confirmation",
                scenarios=selected,
                seeds=confirmation_seeds,
                metric_path=confirmation_path,
                rows=confirmation_rows,
                baseline_rows=confirmation_rows,
                risk_inputs=risk_inputs,
                fallback_rows=screening_rows,
                workers=args.workers,
            )

        curve_rows = build_threshold_curve_rows(
            screening_rows, confirmation_rows, scenarios
        )
        landscape.write_csv_atomic(curve_path, curve_rows)
        j0 = j0_audit(screening_rows, confirmation_rows)
        if not j0["validated"]:
            raise landscape.CaseValidationError(
                "J0 core state is not identical to the paired same-seed baseline"
            )
        manifest.update(
            {
                "status": "complete",
                "completed_at_utc": utc_now(),
                "screening_valid_rows": len(screening_rows),
                "confirmation_valid_rows": len(confirmation_rows),
                "same_j0_audit": j0,
                "threshold_observation": threshold_observation(curve_rows),
                "validation_rules": [
                    "reference graph contains exactly one target lane with a 120000 UN standard order",
                    "V4 tested physical capacity for 344135 is exactly 300000 UN/day",
                    "current engine source contains the audited integer-lot capacity gate",
                    "incident affects only SDC-VD0993480A / item:344135 / M-1430 during J45-J224",
                    "all stressed cases have the same J0 core-state SHA-256 as their same-seed baseline",
                    "V4 baseline service guard and full 720-day horizon checks are inherited",
                ],
            }
        )
        landscape.write_json_atomic(manifest_path, manifest)
        print(f"[OK] 344135 capacity/lot threshold: {output_dir}", flush=True)
        return 0
    except Exception as exc:
        manifest.update(
            {
                "status": "failed",
                "failed_at_utc": utc_now(),
                "error_type": type(exc).__name__,
                "error": str(exc),
            }
        )
        landscape.write_json_atomic(manifest_path, manifest)
        raise


if __name__ == "__main__":
    raise SystemExit(main())
