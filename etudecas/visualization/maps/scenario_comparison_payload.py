from __future__ import annotations

from collections import defaultdict
import html
import math
from pathlib import Path
from typing import Any

from etudecas.visualization.maps.chart_payloads import build_line_chart_figure
from etudecas.visualization.maps.map_data_loader import load_json_dict, read_csv_rows
from etudecas.visualization.maps.map_render import fmt_pct, fmt_qty


def to_float(x: Any) -> float | None:
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def _positive_gap_below_one(value: Any) -> float:
    parsed = to_float(value)
    if parsed is None:
        return 0.0
    return max(0.0, 1.0 - parsed)


def _positive_gap_above_one(value: Any) -> float:
    parsed = to_float(value)
    if parsed is None:
        return 0.0
    return max(0.0, parsed - 1.0)


def _positive_value(value: Any) -> float:
    parsed = to_float(value)
    if parsed is None:
        return 0.0
    return max(0.0, parsed)


def supplier_risk_row_intensity(row: dict[str, str]) -> float:
    """Daily risk exposure score from effective multipliers applied in the run.

    One point is roughly one supplier-item-day at full disruption. This is not a
    probability; it is a comparable input exposure measure across risk families.
    """

    operational_loss = sum(
        _positive_gap_below_one(row.get(key))
        for key in (
            "stock_multiplier",
            "capacity_multiplier",
            "reliability_multiplier",
            "quality_yield_multiplier",
            "availability_multiplier",
            "external_capacity_multiplier",
            "external_availability_multiplier",
            "external_quality_yield_multiplier",
        )
    )
    delay_loss = (
        0.35 * _positive_gap_above_one(row.get("lead_time_multiplier"))
        + 0.35 * _positive_gap_above_one(row.get("external_lead_time_multiplier"))
        + _positive_value(row.get("lead_time_extra_days")) / 30.0
        + _positive_value(row.get("external_lead_time_extra_days")) / 30.0
        + _positive_value(row.get("quality_delay_days")) / 30.0
    )
    cost_loss = 0.20 * sum(
        _positive_gap_above_one(row.get(key))
        for key in (
            "purchase_cost_multiplier",
            "transport_cost_multiplier",
            "external_cost_multiplier",
        )
    )
    physical_loss = _positive_value(row.get("stock_writeoff_fraction"))
    return max(0.0, operational_loss + delay_loss + cost_loss + physical_loss)


def build_scenario_comparison_payload(current_output_root: Path) -> dict[str, Any]:
    result_root = current_output_root.parent
    sweep_root = result_root / "risk_amplitude_duration_sweep_5y"
    sweep_cases_root = sweep_root / "cases"
    compact_payload_path = sweep_root / "scenario_comparison_payload_compact.json"
    if compact_payload_path.exists() and not sweep_cases_root.exists():
        compact_payload = load_json_dict(compact_payload_path)
        compact_ids = {str(row.get("id") or "") for row in compact_payload.get("scenarios", []) if isinstance(row, dict)}
        current_has_summary = (current_output_root / "summaries" / "first_simulation_summary.json").exists()
        if compact_payload and (not current_has_summary or current_output_root.name in compact_ids):
            return compact_payload
    sweep_summary_csv = sweep_root / "risk_amplitude_duration_sweep_summary.csv"
    sweep_rows = read_csv_rows(sweep_summary_csv)
    sweep_by_id = {str(row.get("case_id") or ""): row for row in sweep_rows if row.get("case_id")}
    preferred_names = [
        "_codex_lot_trace_5y_safe",
        "_codex_lot_trace_5y_state_risks",
        "mrp_bom_test_weekly_mps_lotified_no_fallback_physical_floor_portfolio_cost_risk_non_state_risks_test",
        "_codex_lot_trace_5y_risk_portfolio",
        "mrp_bom_test_weekly_mps_lotified_no_fallback_physical_floor_multisource_portfolio_test",
        "mrp_bom_test_weekly_mps_lotified_no_fallback_physical_floor_multisource_portfolio_state_dependent_risk_test",
        "mrp_bom_test_weekly_mps_lotified_no_fallback_physical_floor_multisource_cost_risk_portfolio_test",
    ]
    if current_output_root.name not in preferred_names:
        preferred_names.append(current_output_root.name)

    label_overrides = {
        "_codex_lot_trace_5y_safe": "Nominal 5 ans",
        "_codex_lot_trace_5y_state_risks": "State-dependent historique",
        "_codex_lot_trace_5y_risk_portfolio": "Portefeuille risques actuel",
        "mrp_bom_test_weekly_mps_lotified_no_fallback_physical_floor_portfolio_cost_risk_non_state_risks_test": "Risques metier fournisseurs",
        "mrp_bom_test_weekly_mps_lotified_no_fallback_physical_floor_multisource_portfolio_test": "Multisource nominal",
        "mrp_bom_test_weekly_mps_lotified_no_fallback_physical_floor_multisource_portfolio_state_dependent_risk_test": "Multisource + state-dependent",
        "mrp_bom_test_weekly_mps_lotified_no_fallback_physical_floor_multisource_cost_risk_portfolio_test": "Multisource + risques cout",
        "state_dependent_full": "Portefeuille state-dependent complet",
        "state_api_upstream_crisis": "Crise amont API / matiere critique",
        "state_packaging_quality_crisis": "Crise qualite packaging / lots rejetes",
        "state_downstream_distribution_crisis": "Crise distribution aval / transport",
        "state_internal_release_capacity_crisis": "Crise release interne / PFI",
    }
    family_overrides = {
        "state_dependent_full": "Portefeuille multi-cascades",
        "state_api_upstream_crisis": "API / matiere critique",
        "state_packaging_quality_crisis": "Qualite packaging / lots rejetes",
        "state_downstream_distribution_crisis": "Distribution aval / transport",
        "state_internal_release_capacity_crisis": "Release interne / PFI",
    }

    def load_manifest(root: Path) -> dict[str, Any]:
        return load_json_dict(root / "run_manifest.json")

    def short_label(name: str) -> str:
        if name in sweep_by_id and sweep_by_id[name].get("label"):
            return str(sweep_by_id[name].get("label") or name)
        if name in label_overrides:
            return label_overrides[name]
        if name.startswith("active_mrp_physical_"):
            return "Nominal 5 ans"
        cleaned = name.replace("_codex_", "").replace("mrp_bom_test_weekly_mps_lotified_no_fallback_physical_floor_", "")
        return cleaned.replace("_", " ").strip().title()

    def classify(name: str, summary: dict[str, Any]) -> str:
        policy = summary.get("policy") or {}
        supplier_risk_count = int(to_float((policy.get("supplier_risk") or {}).get("event_count")) or 0)
        state_count = int(to_float((policy.get("supplier_state_dependent_risk") or {}).get("generated_event_count")) or 0)
        scenario_id = str(summary.get("scenario_id") or "")
        lower = name.lower()
        if "safe" in lower or (supplier_risk_count == 0 and state_count == 0 and (scenario_id == "scn:BASE" or "nominal" in lower)):
            return "nominal"
        if supplier_risk_count > 0 and state_count > 0:
            return "state-dependent : aleas + declencheurs etat"
        if supplier_risk_count > 0:
            return "scenario metier"
        if state_count > 0:
            return "state-dependent : declencheurs etat"
        if "multisource" in lower:
            return "mitigation / multisource"
        return "scenario"

    def load_summary(root: Path) -> dict[str, Any]:
        return load_json_dict(root / "summaries" / "first_simulation_summary.json")

    companion_meta_by_root: dict[Path, dict[str, Any]] = {}

    def scenario_roots() -> list[Path]:
        roots: list[Path] = []
        seen: set[Path] = set()
        companion_meta_by_root.clear()
        if (current_output_root / "summaries" / "first_simulation_summary.json").exists():
            roots.append(current_output_root)
            seen.add(current_output_root)
        manifest = load_manifest(current_output_root)
        companion_runs = manifest.get("companion_runs") if isinstance(manifest.get("companion_runs"), dict) else {}
        has_companion_runs = bool(companion_runs)
        for companion in companion_runs.values():
            if isinstance(companion, dict):
                raw_path = str(companion.get("output_dir") or "")
            else:
                raw_path = str(companion or "")
            if not raw_path:
                continue
            root = Path(raw_path)
            if not root.is_absolute():
                root = current_output_root / root
            if root in seen or not (root / "summaries" / "first_simulation_summary.json").exists():
                continue
            roots.append(root)
            seen.add(root)
            if isinstance(companion, dict):
                companion_meta_by_root[root.resolve()] = companion
        if not has_companion_runs:
            for name in preferred_names:
                root = result_root / name
                if root in seen or not (root / "summaries" / "first_simulation_summary.json").exists():
                    continue
                roots.append(root)
                seen.add(root)
        cases_root = sweep_cases_root
        if cases_root.exists():
            for row in sorted(sweep_rows, key=lambda item: to_float(item.get("impact_score")), reverse=True):
                case_id = str(row.get("case_id") or "")
                if not case_id:
                    continue
                if case_id == "baseline_nominal" and any(root.name == "_codex_lot_trace_5y_safe" for root in roots):
                    continue
                root = cases_root / case_id
                if root in seen or not (root / "summaries" / "first_simulation_summary.json").exists():
                    continue
                roots.append(root)
                seen.add(root)
        return roots

    def daily_totals(rows: list[dict[str, str]], field: str) -> dict[int, float]:
        out: dict[int, float] = defaultdict(float)
        for row in rows:
            day = int(to_float(row.get("day")) or 0)
            out[day] += max(0.0, to_float(row.get(field)) or 0.0)
        return out

    def dense_points(values: dict[int, float], max_day: int) -> list[tuple[int, float]]:
        return [(day, float(values.get(day, 0.0))) for day in range(max_day + 1)]

    def cumulative_ratio_points(num_by_day: dict[int, float], den_by_day: dict[int, float], max_day: int) -> list[tuple[int, float]]:
        points: list[tuple[int, float]] = []
        cum_num = 0.0
        cum_den = 0.0
        last = 100.0
        for day in range(max_day + 1):
            cum_num += float(num_by_day.get(day, 0.0))
            cum_den += float(den_by_day.get(day, 0.0))
            if cum_den > 1e-9:
                last = 100.0 * cum_num / cum_den
            points.append((day, last))
        return points

    def leading_startup_backlog_days(backlog_by_day: dict[int, float], max_day: int) -> list[int]:
        days: list[int] = []
        for day in range(max_day + 1):
            value = float(backlog_by_day.get(day, 0.0))
            if value > 1e-9:
                days.append(day)
                continue
            break
        return days

    roots = scenario_roots()
    scenarios: list[dict[str, Any]] = []
    for root in roots:
        summary = load_summary(root)
        if not summary:
            continue
        companion_meta = companion_meta_by_root.get(root.resolve(), {}) if isinstance(companion_meta_by_root, dict) else {}
        sweep_row = sweep_by_id.get(root.name, {})
        horizon = int(to_float(summary.get("timeline_days") or summary.get("sim_days") or 0) or 0)
        if horizon < 300:
            continue
        kpis = (summary.get("kpis") or {}) if isinstance(summary, dict) else {}
        data_root = root / "data"
        demand_rows = read_csv_rows(data_root / "production_demand_service_daily.csv")
        plan_rows = read_csv_rows(data_root / "production_plan_events.csv")
        constraint_rows = read_csv_rows(data_root / "production_constraint_daily.csv")
        risk_rows = read_csv_rows(data_root / "supplier_risk_events_applied_daily.csv")

        max_day = horizon - 1 if horizon > 0 else max([0] + [int(to_float(row.get("day")) or 0) for row in demand_rows + plan_rows + risk_rows])
        demand_by_day = daily_totals(demand_rows, "demand_qty")
        served_by_day = daily_totals(demand_rows, "served_qty")
        backlog_by_day = daily_totals(demand_rows, "backlog_end_qty")
        startup_backlog_days = leading_startup_backlog_days(backlog_by_day, max_day)
        startup_day_set = set(startup_backlog_days)
        startup_backlog_peak = max((backlog_by_day.get(day, 0.0) for day in startup_backlog_days), default=0.0)
        decision_backlog_by_day = {
            day: value
            for day, value in backlog_by_day.items()
            if day not in startup_day_set
        }
        max_backlog = max(decision_backlog_by_day.values(), default=0.0)
        backlog_days = sum(1 for value in decision_backlog_by_day.values() if value > 1e-9)

        starts_by_day: dict[int, float] = defaultdict(float)
        input_delay_by_day: dict[int, float] = defaultdict(float)
        lot_delay_by_day: dict[int, float] = defaultdict(float)
        input_delay_volume = 0.0
        for row in plan_rows:
            day = int(to_float(row.get("day")) or 0)
            event_type = str(row.get("event_type") or "")
            reason = str(row.get("reason") or "")
            if event_type == "start_campaign":
                starts_by_day[day] += 1.0
            if event_type == "delay_input_shortage" or reason == "input_shortage":
                input_delay_by_day[day] += 1.0
                input_delay_volume += max(0.0, to_float(row.get("shortfall_vs_lot_plan_qty")) or 0.0)
            if event_type == "delay_weekly_lot_limit" or reason == "weekly_lot_limit":
                lot_delay_by_day[day] += 1.0

        risk_by_day: dict[int, float] = defaultdict(float)
        risk_event_ids: set[str] = set()
        risk_suppliers: set[str] = set()
        risk_input_amplitude_points = 0.0
        for row in risk_rows:
            day = int(to_float(row.get("day")) or 0)
            risk_by_day[day] += 1.0
            risk_input_amplitude_points += supplier_risk_row_intensity(row)
            supplier_id = str(row.get("supplier_id") or "")
            if supplier_id:
                risk_suppliers.add(supplier_id)
            for event_id in str(row.get("event_ids") or "").split(","):
                event_id = event_id.strip()
                if event_id:
                    risk_event_ids.add(event_id)

        actual_produced = sum(max(0.0, to_float(row.get("actual_qty")) or 0.0) for row in constraint_rows)
        is_sweep = bool(sweep_row)
        scenario_kind = classify(root.name, summary)
        scenario_label = str(companion_meta.get("label") or short_label(root.name)) if isinstance(companion_meta, dict) else short_label(root.name)
        if root.name in label_overrides:
            scenario_label = label_overrides[root.name]
        if root.resolve() == current_output_root.resolve() and scenario_kind == "nominal":
            scenario_label = "Nominal 5 ans"
        if is_sweep:
            scenario_family = str(sweep_row.get("family") or scenario_kind)
        elif root.name in family_overrides:
            scenario_family = family_overrides[root.name]
        elif isinstance(companion_meta, dict) and companion_meta.get("label"):
            scenario_family = str(companion_meta.get("label") or "")
        else:
            scenario_family = scenario_kind
        scenario_severity = str(sweep_row.get("severity") or "")
        impact_score = max(0.0, to_float(sweep_row.get("impact_score")) or 0.0)
        fill_rate_value = to_float(sweep_row.get("fill_rate")) if is_sweep else None
        if fill_rate_value is None:
            fill_rate_value = to_float(kpis.get("fill_rate")) or 0.0
        max_backlog_value = to_float(sweep_row.get("backlog_max_ex_startup")) if is_sweep else None
        if max_backlog_value is None:
            max_backlog_value = max_backlog
        input_delay_count_value = to_float(sweep_row.get("input_delay_count")) if is_sweep else None
        if input_delay_count_value is None:
            input_delay_count_value = sum(input_delay_by_day.values())
        input_delay_volume_value = to_float(sweep_row.get("input_delay_volume")) if is_sweep else None
        if input_delay_volume_value is None:
            input_delay_volume_value = input_delay_volume
        production_replanning_count_value = to_float(sweep_row.get("production_replanning_count")) if is_sweep else None
        if production_replanning_count_value is None:
            production_replanning_count_value = to_float(kpis.get("production_replanning_count"))
        if production_replanning_count_value is None:
            production_replanning_count_value = input_delay_count_value
        production_replanning_rate_value = to_float(sweep_row.get("production_replanning_rate")) if is_sweep else None
        if production_replanning_rate_value is None:
            production_replanning_rate_value = to_float(kpis.get("production_replanning_rate"))
        if production_replanning_rate_value is None:
            planning_line_count = to_float(kpis.get("production_planning_line_count"))
            if planning_line_count is None:
                planning_line_count = float(
                    sum(
                        1
                        for row in plan_rows
                        if str(row.get("event_type") or "")
                        or str(row.get("reason") or "")
                        or (to_float(row.get("planned_qty_after_lot_rule")) or 0.0) > 0.0
                    )
                )
            if planning_line_count and planning_line_count > 0:
                production_replanning_rate_value = max(0.0, production_replanning_count_value or 0.0) / planning_line_count
        total_cost_value = to_float(sweep_row.get("total_cost")) if is_sweep else None
        if total_cost_value is None:
            total_cost_value = max(0.0, to_float(kpis.get("total_cost")) or 0.0)
        policy = summary.get("policy") or {}
        configured_supplier_risk_count = int(to_float((policy.get("supplier_risk") or {}).get("event_count")) or 0)
        generated_state_event_count = int(to_float((policy.get("supplier_state_dependent_risk") or {}).get("generated_event_count")) or 0)
        scenario_amplitude = scenario_severity
        if not scenario_amplitude and (configured_supplier_risk_count or generated_state_event_count):
            scenario_amplitude = (
                f"{configured_supplier_risk_count} aleas configures ; "
                f"{generated_state_event_count} declencheurs auto"
            )
        scenarios.append(
            {
                "id": root.name,
                "label": scenario_label,
                "kind": "sweep " + scenario_family if is_sweep else scenario_kind,
                "family": scenario_family,
                "severity": scenario_amplitude,
                "source": "risk_amplitude_duration_sweep" if is_sweep else "run_result",
                "impact_score": impact_score,
                "is_current": root.resolve() == current_output_root.resolve(),
                "horizon_days": max_day + 1,
                "kpis": {
                    "fill_rate": fill_rate_value,
                    "fill_rate_delta_pp": to_float(sweep_row.get("fill_rate_delta_pp")) if is_sweep else 0.0,
                    "ending_backlog": max(0.0, to_float(kpis.get("ending_backlog")) or 0.0),
                    "max_backlog": max_backlog_value,
                    "backlog_days": backlog_days,
                    "startup_backlog_days": len(startup_backlog_days),
                    "startup_backlog_peak": startup_backlog_peak,
                    "startup_backlog_last_day": max(startup_backlog_days) if startup_backlog_days else None,
                    "total_demand": max(0.0, to_float(kpis.get("total_demand")) or sum(demand_by_day.values())),
                    "total_served": max(0.0, to_float(kpis.get("total_served")) or sum(served_by_day.values())),
                    "total_produced": max(0.0, to_float(kpis.get("total_produced")) or actual_produced),
                    "actual_produced": actual_produced,
                    "input_delay_count": int(input_delay_count_value),
                    "lot_delay_count": int(sum(lot_delay_by_day.values())),
                    "input_delay_volume": input_delay_volume_value,
                    "input_delay_volume_delta": to_float(sweep_row.get("input_delay_volume_delta")) if is_sweep else 0.0,
                    "production_replanning_count": int(production_replanning_count_value or 0),
                    "production_replanning_rate": production_replanning_rate_value,
                    "risk_input_amplitude_points": risk_input_amplitude_points,
                    "risk_event_count": len(risk_event_ids),
                    "configured_supplier_risk_count": configured_supplier_risk_count,
                    "risk_row_count": len(risk_rows),
                    "risk_supplier_count": len(risk_suppliers),
                    "risk_applied_rows": to_float(sweep_row.get("risk_applied_rows")) if is_sweep else len(risk_rows),
                    "state_events_generated": (
                        to_float(sweep_row.get("state_events_generated"))
                        if is_sweep
                        else to_float(((summary.get("policy") or {}).get("supplier_state_dependent_risk") or {}).get("generated_event_count")) or 0.0
                    ),
                    "total_unreliable_loss_qty": max(
                        0.0,
                        (
                            to_float(sweep_row.get("unreliable_loss_qty"))
                            if is_sweep
                            else to_float(kpis.get("total_unreliable_loss_qty"))
                        )
                        or 0.0,
                    ),
                    "loss_delta": (to_float(sweep_row.get("loss_delta")) if is_sweep else 0.0) or 0.0,
                    "total_external_procurement_cost": max(
                        0.0,
                        (
                            to_float(sweep_row.get("external_procurement_cost"))
                            if is_sweep
                            else to_float(kpis.get("total_external_procurement_cost"))
                        )
                        or 0.0,
                    ),
                    "external_cost_delta": (to_float(sweep_row.get("external_cost_delta")) if is_sweep else 0.0) or 0.0,
                    "total_transport_cost": max(0.0, to_float(kpis.get("total_transport_cost")) or 0.0),
                    "total_purchase_cost": max(0.0, to_float(kpis.get("total_purchase_cost")) or 0.0),
                    "total_cost": max(0.0, total_cost_value),
                    "cost_delta": (to_float(sweep_row.get("cost_delta")) if is_sweep else 0.0) or 0.0,
                    "impact_score": impact_score,
                },
                "series": {
                    "backlog": dense_points(decision_backlog_by_day, max_day),
                    "service_rate": cumulative_ratio_points(served_by_day, demand_by_day, max_day),
                    "served": dense_points(served_by_day, max_day),
                    "demand": dense_points(demand_by_day, max_day),
                    "input_delays": dense_points(input_delay_by_day, max_day),
                    "lot_delays": dense_points(lot_delay_by_day, max_day),
                    "production_starts": dense_points(starts_by_day, max_day),
                    "risk_rows": dense_points(risk_by_day, max_day),
                },
            }
        )

    if not scenarios:
        return {"available": False, "html": "", "figures": {}, "scenarios": []}

    nominal = next(
        (
            scenario
            for scenario in scenarios
            if scenario["id"] in {"_codex_lot_trace_5y_safe", "baseline_nominal"}
        ),
        scenarios[0],
    )
    nominal_kpis = nominal["kpis"]

    def compute_observed_impact(kpis: dict[str, Any], base_kpis: dict[str, Any]) -> dict[str, float | str]:
        total_demand = max(1.0, to_float(kpis.get("total_demand")) or to_float(base_kpis.get("total_demand")) or 1.0)
        service_loss_pp = max(
            0.0,
            ((to_float(base_kpis.get("fill_rate")) or 0.0) - (to_float(kpis.get("fill_rate")) or 0.0)) * 100.0,
        )
        replan_volume_pct = 100.0 * max(0.0, to_float(kpis.get("input_delay_volume")) or 0.0) / total_demand
        backlog_pct = 100.0 * max(0.0, to_float(kpis.get("max_backlog")) or 0.0) / total_demand
        base_cost = max(1.0, to_float(base_kpis.get("total_cost")) or 1.0)
        cost_delta_pct = 100.0 * max(0.0, (to_float(kpis.get("total_cost")) or 0.0) - base_cost) / base_cost
        loss_qty_pct = 100.0 * max(0.0, to_float(kpis.get("total_unreliable_loss_qty")) or 0.0) / total_demand
        # Weighted score for ranking scenarios. Service and backlog are weighted
        # higher than pure cost, because the business decision first protects
        # product availability and production continuity.
        observed_score = (
            5.0 * service_loss_pp
            + 3.0 * backlog_pct
            + 1.0 * replan_volume_pct
            + 0.25 * cost_delta_pct
            + 1.0 * loss_qty_pct
        )
        amplitude = max(0.0, to_float(kpis.get("risk_input_amplitude_points")) or 0.0)
        effect_per_100 = (100.0 * observed_score / amplitude) if amplitude > 1e-9 else 0.0
        if amplitude <= 1e-9:
            absorption_label = "n/a"
        elif service_loss_pp >= 2.0 or backlog_pct >= 0.5:
            absorption_label = "impact client"
        elif replan_volume_pct >= 2.0 or cost_delta_pct >= 5.0:
            absorption_label = "absorbe client, impact production/cout"
        else:
            absorption_label = "absorbe par stocks/MRP"
        return {
            "service_loss_pp": service_loss_pp,
            "replan_volume_pct": replan_volume_pct,
            "backlog_pct": backlog_pct,
            "cost_delta_pct": cost_delta_pct,
            "loss_qty_pct": loss_qty_pct,
            "observed_impact_score": observed_score,
            "effect_per_100_amplitude": effect_per_100,
            "absorption_label": absorption_label,
        }

    for scenario in scenarios:
        scenario["kpis"].update(compute_observed_impact(scenario["kpis"], nominal_kpis))

    def delta(value: float, base: float, digits: int = 1) -> str:
        diff = value - base
        if abs(diff) <= 1e-9:
            return "0"
        sign = "+" if diff > 0 else ""
        return f"{sign}{fmt_qty(diff, digits)}"

    best_cost = min(scenarios, key=lambda item: item["kpis"].get("total_cost", math.inf))
    def replanning_sort_key(scenario: dict[str, Any]) -> tuple[float, float, float]:
        kpis = scenario["kpis"]
        rate = kpis.get("production_replanning_rate")
        rate_key = float(rate) if rate is not None else math.inf
        return (
            rate_key,
            float(kpis.get("production_replanning_count") or kpis.get("input_delay_count") or math.inf),
            float(kpis.get("input_delay_volume") or math.inf),
        )

    def replanning_text(kpis: dict[str, Any]) -> str:
        rate = to_float(kpis.get("production_replanning_rate"))
        count = to_float(kpis.get("production_replanning_count"))
        if count is None:
            count = to_float(kpis.get("input_delay_count"))
        volume = to_float(kpis.get("input_delay_volume")) or 0.0
        if rate is not None:
            return f"taux replanification {fmt_pct(rate * 100.0)} ; volume associe {fmt_qty(volume, 0)}."
        return f"taux replanification n/a ; volume associe {fmt_qty(volume, 0)} ; {fmt_qty(count or 0, 0)} lignes."

    best_production = min(scenarios, key=replanning_sort_key)
    worst_backlog = max(scenarios, key=lambda item: item["kpis"].get("max_backlog", 0.0))
    most_risk = max(
        scenarios,
        key=lambda item: (
            item["kpis"].get("observed_impact_score", 0.0)
            or item["kpis"].get("impact_score", 0.0)
            or item["kpis"].get("risk_event_count", 0.0)
        ),
    )

    def card(title: str, value: str, text: str, color: str) -> str:
        return (
            f"<div class=\"riskScenarioCard\" style=\"border-left-color:{html.escape(color)}\">"
            f"<div class=\"riskScenarioCardTitle\">{html.escape(title)}</div>"
            f"<div class=\"riskScenarioCardText\"><strong>{html.escape(value)}</strong><br>{html.escape(text)}</div>"
            "</div>"
        )

    cards_html = "".join(
        [
            card(
                "Reference",
                nominal["label"],
                (
                    f"Base de comparaison: disponibilite produit {fmt_pct(nominal_kpis['fill_rate'] * 100.0)} ; "
                    f"cout total {fmt_qty(nominal_kpis['total_cost'], 0)}. "
                    f"Amorcage client: {int(nominal_kpis.get('startup_backlog_days') or 0)} j, "
                    f"pic {fmt_qty(nominal_kpis.get('startup_backlog_peak') or 0, 0)}."
                ),
                "#2563eb",
            ),
            card(
                "Cout total le plus bas",
                best_cost["label"],
                f"Cout total {fmt_qty(best_cost['kpis']['total_cost'], 0)} ; delta vs reference {delta(best_cost['kpis']['total_cost'], nominal_kpis['total_cost'], 0)}.",
                "#0f766e",
            ),
            card(
                "Production la moins reportee",
                best_production["label"],
                replanning_text(best_production["kpis"]),
                "#d97706",
            ),
            card(
                "Scenario le plus perturbateur",
                most_risk["label"],
                (
                    f"Impact observe {fmt_qty(most_risk['kpis'].get('observed_impact_score') or 0, 1)} pts ; "
                    f"disponibilite produit {fmt_pct((most_risk['kpis'].get('fill_rate') or 0) * 100.0)} ; "
                    f"backlog max {fmt_qty(most_risk['kpis'].get('max_backlog') or 0, 0)}."
                ),
                "#be123c",
            ),
        ]
    )

    headers = [
        "Scenario",
        "Mecanisme",
        "Crise / chemin metier",
        "Configuration",
        "Amplitude entree",
        "Impact observe",
        "Absorption / effet",
        "Disponibilite produit",
        "Backlog max hors amorcage",
        "Amorcage client",
        "Taux replanification",
        "Volume reporte",
        "Delta volume",
        "Pertes fournisseur",
        "Delta pertes",
        "Cout appro fournisseur",
        "Cout total",
        "Delta cout",
    ]

    def scenario_configuration_text(scenario: dict[str, Any]) -> str:
        kpis = scenario["kpis"]
        configured = int(to_float(kpis.get("configured_supplier_risk_count")) or 0)
        state_events = int(to_float(kpis.get("state_events_generated")) or 0)
        if configured or state_events:
            return f"{configured} aleas configures ; {state_events} declencheurs auto"
        return str(scenario.get("severity") or "n/a")

    def amplitude_text(kpis: dict[str, Any]) -> str:
        amplitude = to_float(kpis.get("risk_input_amplitude_points")) or 0.0
        rows = int(to_float(kpis.get("risk_row_count")) or 0)
        suppliers = int(to_float(kpis.get("risk_supplier_count")) or 0)
        if amplitude <= 1e-9 and rows <= 0:
            return "n/a"
        return f"{fmt_qty(amplitude, 1)} pts risque-jour ; {rows} effets ; {suppliers} fournisseurs"

    def observed_impact_text(kpis: dict[str, Any]) -> str:
        parts: list[str] = []
        service_loss_pp = to_float(kpis.get("service_loss_pp")) or 0.0
        replan_volume_pct = to_float(kpis.get("replan_volume_pct")) or 0.0
        cost_delta_pct = to_float(kpis.get("cost_delta_pct")) or 0.0
        if service_loss_pp > 0.05:
            parts.append(f"dispo -{fmt_qty(service_loss_pp, 1)} pts")
        if replan_volume_pct > 0.05:
            parts.append(f"report {fmt_qty(replan_volume_pct, 1)}% demande")
        if cost_delta_pct > 0.05:
            parts.append(f"cout +{fmt_qty(cost_delta_pct, 1)}%")
        if not parts:
            parts.append("impact KPI faible")
        parts.append(f"score {fmt_qty(kpis.get('observed_impact_score') or 0, 1)}")
        return " ; ".join(parts)

    def absorption_text(kpis: dict[str, Any]) -> str:
        label = str(kpis.get("absorption_label") or "n/a")
        amplitude = to_float(kpis.get("risk_input_amplitude_points")) or 0.0
        if amplitude <= 1e-9:
            return label
        return f"{label} ; {fmt_qty(kpis.get('effect_per_100_amplitude') or 0, 1)} pts impact / 100 pts entree"

    rows_html = []
    for scenario in scenarios:
        k = scenario["kpis"]
        cls = "scenarioCurrentRow" if scenario.get("is_current") else ""
        startup_cell = f"{int(k.get('startup_backlog_days') or 0)} j ; pic {fmt_qty(k.get('startup_backlog_peak') or 0, 0)}"
        rows_html.append(
            f"<tr class=\"{cls}\" data-scenario-id=\"{html.escape(scenario['id'])}\">"
            f"<td>{html.escape(scenario['label'])}</td>"
            f"<td>{html.escape(scenario['kind'])}</td>"
            f"<td>{html.escape(str(scenario.get('family') or 'n/a'))}</td>"
            f"<td>{html.escape(scenario_configuration_text(scenario))}</td>"
            f"<td>{html.escape(amplitude_text(k))}</td>"
            f"<td>{html.escape(observed_impact_text(k))}</td>"
            f"<td>{html.escape(absorption_text(k))}</td>"
            f"<td>{html.escape(fmt_pct(k['fill_rate'] * 100.0))}</td>"
            f"<td>{html.escape(fmt_qty(k['max_backlog'], 0))}</td>"
            f"<td>{html.escape(startup_cell)}</td>"
            f"<td>{html.escape(replanning_text(k))}</td>"
            f"<td>{html.escape(fmt_qty(k['input_delay_volume'], 0))}</td>"
            f"<td>{html.escape(delta(k.get('input_delay_volume_delta') or 0, 0, 0))}</td>"
            f"<td>{html.escape(fmt_qty(k['total_unreliable_loss_qty'], 0))}</td>"
            f"<td>{html.escape(delta(k.get('loss_delta') or 0, 0, 0))}</td>"
            f"<td>{html.escape(fmt_qty(k['total_external_procurement_cost'], 0))}</td>"
            f"<td>{html.escape(fmt_qty(k['total_cost'], 0))}</td>"
            f"<td>{html.escape(delta(k.get('cost_delta') or (k['total_cost'] - nominal_kpis['total_cost']), 0, 0))}</td>"
            "</tr>"
        )

    palette = ["#2563eb", "#0f766e", "#d97706", "#be123c", "#7c3aed", "#475569", "#0891b2"]
    max_impact_id = ""
    if scenarios:
        max_impact_id = max(
            scenarios,
            key=lambda item: float((item.get("kpis") or {}).get("observed_impact_score") or 0.0),
        )["id"]
    style_by_label = {
        scenario["label"]: {
            "color": palette[idx % len(palette)],
            "width": 2.8 if scenario.get("is_current") else 2.1,
            "dash": "solid" if scenario.get("is_current") else "dot" if scenario["kind"] == "nominal" else "solid",
            "scenario_id": scenario["id"],
            "is_current": bool(scenario.get("is_current")),
            "is_nominal": scenario["id"] in {nominal["id"], "baseline_nominal", "_codex_lot_trace_5y_safe"} or scenario["kind"] == "nominal",
            "is_max_impact": scenario["id"] == max_impact_id,
            "family": scenario.get("family") or scenario["kind"],
            "impact_score": float((scenario.get("kpis") or {}).get("observed_impact_score") or 0.0),
        }
        for idx, scenario in enumerate(scenarios)
    }

    def enable_scenario_tube(
        figure: dict[str, Any] | None,
        *,
        reference_value: float | None = None,
        reference_label: str = "",
        zero_floor: bool = False,
        upper_percentile: float = 0.90,
    ) -> dict[str, Any] | None:
        if figure is None:
            return None
        figure["scenario_tube"] = True
        figure["tube_label"] = "Enveloppe scenarios selectionnes"
        figure["trajectory_label"] = "Trajectoires scenarios"
        figure["named_scenario_trajectories"] = True
        figure["tube_zero_floor"] = bool(zero_floor)
        figure["tube_upper_percentile"] = float(upper_percentile)
        if reference_value is not None:
            figure["reference_line_value"] = float(reference_value)
            figure["reference_line_label"] = reference_label
        return figure

    figures: dict[str, Any] = {}
    backlog_figure = build_line_chart_figure(
        {scenario["label"]: scenario["series"]["backlog"] for scenario in scenarios},
        title="Backlog client compare hors amorcage",
        y_label="Backlog fin jour",
        note="Les jours d'amorcage J0..Jn dus au stock client initial nul sont retires de cette courbe et detailles dans le tableau.",
        series_styles=style_by_label,
    )
    if backlog_figure is not None:
        figures["backlog"] = enable_scenario_tube(backlog_figure, reference_value=0.0, reference_label="objectif backlog 0")

    service_figure = build_line_chart_figure(
        {scenario["label"]: scenario["series"]["service_rate"] for scenario in scenarios},
        title="Disponibilite produit cumulee comparee",
        y_label="Servi / demande cumulee (%)",
        note="Trajectoire de disponibilite produit cumulee. Une baisse durable indique que les stocks et receptions n'absorbent plus le risque.",
        series_styles=style_by_label,
    )
    if service_figure is not None:
        figures["service_rate"] = enable_scenario_tube(service_figure, reference_value=100.0, reference_label="service 100%")

    production_figure = build_line_chart_figure(
        {scenario["label"]: scenario["series"]["input_delays"] for scenario in scenarios},
        title="Replanification production par manque d'intrants",
        y_label="Lignes reportees / jour",
        note="Volume journalier associe au taux de replanification: jours ou une production attend de la matiere ou du PFI.",
        event_like=True,
        series_styles=style_by_label,
    )
    if production_figure is not None:
        figures["production_delays"] = enable_scenario_tube(
            production_figure,
            reference_value=0.0,
            reference_label="objectif replanification 0",
            zero_floor=True,
            upper_percentile=1.0,
        )

    starts_figure = build_line_chart_figure(
        {scenario["label"]: scenario["series"]["production_starts"] for scenario in scenarios},
        title="Lancements de production compares",
        y_label="Lots / campagnes lancees",
        note="Permet de voir si le scenario decale ou concentre les lancements de production.",
        event_like=True,
        series_styles=style_by_label,
    )
    if starts_figure is not None:
        figures["production_starts"] = enable_scenario_tube(starts_figure)

    risk_figure = build_line_chart_figure(
        {scenario["label"]: scenario["series"]["risk_rows"] for scenario in scenarios},
        title="Effets fournisseurs appliques dans chaque scenario",
        y_label="Effets locaux / jour",
        note="Mesure la pression risque appliquee dans le run, pas seulement les evenements configures.",
        series_styles=style_by_label,
    )
    if risk_figure is not None:
        figures["risk_rows"] = enable_scenario_tube(risk_figure)

    figures["cost"] = {
        "kind": "bar",
        "title": "Cout total compare",
        "y_label": "Cout total",
        "ids": [scenario["id"] for scenario in scenarios],
        "labels": [scenario["label"] for scenario in scenarios],
        "values": [float(scenario["kpis"]["total_cost"]) for scenario in scenarios],
        "colors": [style_by_label[scenario["label"]]["color"] for scenario in scenarios],
    }

    checks_html = "".join(
        (
            "<label class=\"scenarioComparisonCheck\">"
            f"<input type=\"checkbox\" class=\"scenarioComparisonChk\" value=\"{html.escape(scenario['id'])}\" checked>"
            f"<span>{html.escape(scenario['label'])}</span>"
            f"<small>{html.escape(str(scenario.get('family') or scenario['kind']))}</small>"
            "</label>"
        )
        for scenario in scenarios
    )

    scenarios_by_id = {scenario["id"]: scenario for scenario in scenarios}
    default_selected_ids = []

    def add_default_scenario(scenario: dict[str, Any] | None) -> None:
        if not scenario:
            return
        scenario_id = str(scenario.get("id") or "")
        if scenario_id and scenario_id not in default_selected_ids and scenario_id in scenarios_by_id:
            default_selected_ids.append(scenario_id)

    add_default_scenario(nominal)
    add_default_scenario(scenarios_by_id.get(current_output_root.name))
    for scenario in [most_risk, worst_backlog, best_cost, best_production]:
        add_default_scenario(scenario)
    ranked_defaults = sorted(
        scenarios,
        key=lambda scenario: (
            -float((scenario.get("kpis") or {}).get("observed_impact_score") or 0.0),
            -float((scenario.get("kpis") or {}).get("max_backlog") or 0.0),
            -float((scenario.get("kpis") or {}).get("input_delay_volume") or 0.0),
            str(scenario.get("id") or ""),
        ),
    )
    for scenario in ranked_defaults:
        if len(default_selected_ids) >= 8:
            break
        add_default_scenario(scenario)
    if not default_selected_ids:
        default_selected_ids = [scenario["id"] for scenario in scenarios[: min(8, len(scenarios))]]

    html_parts = [
        "<div class=\"factoryHtmlPanelContent sensitivityHtmlPanelContent scenarioComparisonContent\">",
        "<div class=\"orderLedgerTextHeader\">Comparaison de scenarios</div>",
        "<div class=\"orderLedgerStatus\">Question metier: quel scenario degrade le service, reporte la production, augmente les couts ou consomme la resilience du reseau ? La ligne du scenario courant est surlignee.</div>",
        "<div class=\"orderLedgerStatus\">Lecture state-dependent: les scenarios de crise configurent des aleas metier, puis le moteur declenche et propage les effets selon l'etat du run: stocks, retards, ordres, capacites, receptions et backlog.</div>",
        "<div class=\"orderLedgerStatus\">Amplitude entree: points risque-jour calcules depuis les multiplicateurs vraiment appliques. Impact observe: perte de disponibilite produit, reports, backlog et surcout vs nominal. Ce n'est pas une probabilite.</div>",
        "<div class=\"orderLedgerStatus\">Note: le backlog J0/J1 vient du stock client initialise a zero et du delai DC -> client. Il est affiche comme amorcage client, mais exclu du backlog comparatif des scenarios.</div>",
        "<div class=\"scenarioComparisonControls\">",
        "<div class=\"scenarioComparisonActions\">",
        "<button class=\"tableBtn\" type=\"button\" data-scenario-select=\"all\">Tous</button>",
        "<button class=\"tableBtn\" type=\"button\" data-scenario-select=\"top\">Top perturbateurs</button>",
        "<button class=\"tableBtn\" type=\"button\" data-scenario-select=\"service\">Service degrade</button>",
        "<button class=\"tableBtn\" type=\"button\" data-scenario-select=\"lead_time\">Delais</button>",
        "<button class=\"tableBtn\" type=\"button\" data-scenario-select=\"quality\">Qualite</button>",
        "<button class=\"tableBtn\" type=\"button\" data-scenario-select=\"transport\">Transport</button>",
        "<button class=\"tableBtn\" type=\"button\" data-scenario-select=\"combined\">Cascades</button>",
        "<button class=\"tableBtn\" type=\"button\" data-scenario-select=\"current\">Courant</button>",
        "<button class=\"tableBtn\" type=\"button\" data-scenario-select=\"nominal_current\">Nominal + courant</button>",
        "<span id=\"scenarioComparisonSelectionMeta\" class=\"scenarioComparisonSelectionMeta\"></span>",
        "</div>",
        f"<div id=\"scenarioComparisonScenarioChecks\" class=\"scenarioComparisonChecks\">{checks_html}</div>",
        "</div>",
        f"<div id=\"scenarioComparisonCards\" class=\"riskScenarioCards\">{cards_html}</div>",
        "<div class=\"riskScenarioSection\">Courbes comparatives</div>",
        "<div class=\"riskScenarioMuted\">Lecture des courbes: gris = trajectoires selectionnees, bande bleue = enveloppe centrale P10-P90. Pour les reports, la bande part de zero et montre l'amplitude des scenarios selectionnes. Pointille bleu = mediane, noir = nominal, orange = run courant, rouge = scenario le plus perturbateur.</div>",
        "<div class=\"riskDiagnosticChartGrid\">",
        "<div id=\"scenarioCmpBacklog\" class=\"riskDiagnosticChart\"></div>",
        "<div id=\"scenarioCmpService\" class=\"riskDiagnosticChart\"></div>",
        "<div id=\"scenarioCmpProduction\" class=\"riskDiagnosticChart\"></div>",
        "<div id=\"scenarioCmpStarts\" class=\"riskDiagnosticChart\"></div>",
        "<div id=\"scenarioCmpRisk\" class=\"riskDiagnosticChart\"></div>",
        "<div id=\"scenarioCmpCost\" class=\"riskDiagnosticChart\"></div>",
        "</div>",
        "<div class=\"riskScenarioSection\">Tableau decisionnel</div>",
        "<div class=\"kpiFormulaTableWrap\"><table class=\"kpiFormulaTable scenarioComparisonTable\">",
        "<thead><tr>",
        "".join(f"<th>{html.escape(header)}</th>" for header in headers),
        "</tr></thead>",
        f"<tbody>{''.join(rows_html)}</tbody>",
        "</table></div>",
        "<div class=\"riskScenarioMuted\">Lecture: deux scenarios ne sont comparables a amplitude egale que si leur amplitude entree normalisee est proche. Si l'impact par 100 points entree est eleve, la supply absorbe mal cette famille de crise.</div>",
        "</div>",
    ]
    return {
        "available": True,
        "html": "".join(html_parts),
        "figures": figures,
        "scenarios": [
            {
                "id": scenario["id"],
                "label": scenario["label"],
                "kind": scenario["kind"],
                "family": scenario.get("family") or "",
                "severity": scenario.get("severity") or "",
                "source": scenario.get("source") or "",
                "impact_score": scenario.get("impact_score") or 0.0,
                "is_current": bool(scenario.get("is_current")),
                "kpis": scenario["kpis"],
            }
            for scenario in scenarios
        ],
        "default_selected_ids": default_selected_ids,
    }
