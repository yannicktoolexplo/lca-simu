"""Prospective contract arithmetic in memory; no filesystem mutation fixtures.

Source vintages deliberately disagree with the declared synthetic scenario.
The oracle uses rational arithmetic and explicit dates, not production helpers.
"""
from contextlib import contextmanager
from copy import deepcopy
from fractions import Fraction
from types import SimpleNamespace

import pytest

from etudecas.simulation import current_reference as reference
from etudecas.simulation.engine import mrp_planning as planning
from etudecas.simulation.engine import run_first_simulation as engine


KG = ("M-1810", "item:002612")
UN = ("M-1430", "item:042342")
CLIENT = ("C-XXXXX", "item:268091")


def _customer_payload():
    return dict(schema_version=1, origin="2025-01-01", calendar="monday_start",
        rows=[dict(node_id=CLIENT[0], item_id=CLIENT[1], uom="UN", period_start_day=start,
                   period_days=7, qty=0 if start == 12 else 100,
                   source_row=f"E{start+3}", source_file="memory_customer.xlsx")
              for start in range(-2, 362, 7)])


def _fixed_profile():
    return reference.FrozenOtherUses(dict(schema_version=1, quantity="W_requested_weekly_not_served",
        source_file="memory_W_requested.csv", source_sha256="memory_not_a_file",
        rows=[dict(node_id=pair[0], item_id=pair[1], uom=unit, period_start_day=start,
                   qty=str(0 if start == 12 else qty))
              for pair, unit, qty in ((KG, "KG", 70), (UN, "UN", 15))
              for start in range(-2, 362, 7)]))


def _external_payload():
    return dict(schema_version=3, origin="2025-01-01", scenario_id="scn:BASE",
        semantics="incremental_non_modelled_component_use", rows=[],
        versioned_series=[dict(node_id=pair[0], item_id=pair[1], uom=unit,
            repeat_period_days=0, period_anchor_day=4, period_days=7,
            current_bucket_policy="freeze_previous_exclude_current_vintage",
            missing_future_policy="unprovided_not_observed_zero",
            versions=[dict(vintage_id="known_2025", known_day=350, rows=[
                dict(demand_id=f"{pair[1]}-{start}", period_start_day=start, period_days=7,
                     qty=qty, source_file="memory_MRP.xlsx", source_cells=f"I{start}",
                     estimation_basis="deliberately distinct source forecast")
                for start, qty in ((368, 700), (375, 700), (382, 0))])])
            for pair, unit in ((KG, "KG"), (UN, "UN"))])


def _industrial_payload():
    payload = _external_payload()
    payload.update(schema_version=1, semantics="industrial_total_gross_requirements_planning_only")
    payload.pop("rows")
    for series in payload["versioned_series"]:
        for version in series["versions"]:
            version.pop("vintage_id")
    return payload


def _forecast_payload():
    return dict(schema_version=1, origin="2025-01-01", calendar="monday_start",
        repeat_period_days=365, current_bucket_policy="excluded_unresolved_carry_over",
        rows=[dict(node_id=CLIENT[0], item_id=CLIENT[1], uom="UN", vintage_day=known,
            period_start_day=start, period_days=7, qty=qty, source_row=f"D{known}_{start}",
            source_file="memory_Projection.xlsx")
            for known, start, qty in ((-2, 5, 700), (-2, 362, 700),
                                     (355, 369, 1400), (355, 376, 1400))])


@contextmanager
def _adapters(mode):
    # Isolated module objects: no mutation of shared imported engine classes.
    p = SimpleNamespace(ExternalComponentDemandCalendar=planning.ExternalComponentDemandCalendar)
    names = ("ExternalComponentDemandCalendar", "PlanningOnlyExternalComponentCalendar",
             "IndustrialComponentPlanningCalendar", "SourceCustomerHistory",
             "resolve_customer_demand_policy", "RollingMrpForecast", "CUSTOMER_DEMAND_POLICY_FIELDS")
    e = SimpleNamespace(**{name: getattr(engine, name) for name in names})
    frozen = _fixed_profile()
    restorations = reference.install_projection(p, e, frozen, 1825,
        forecast_mode=mode, customer_payload=_customer_payload())
    try:
        yield p, e, frozen
    finally:
        for module, name, old in reversed(restorations):
            setattr(module, name, old)


def _forecast(cls):
    return cls(_forecast_payload(), demand_pairs={CLIENT}, origin_date="2025-01-01",
        missing_period_policy="last_known_period_v1", consumption_policy="weekly_actual_orders_v1",
        customer_demand_policy="source_customer_history_v1")


def test_candidate_preserves_all_2025_forecast_decisions_and_publishes_on_20260101():
    with _adapters("source_priority") as (_, e, _):
        old = _forecast(e.RollingMrpForecast)
    with _adapters("coherent_scenario") as (_, e, _):
        candidate = _forecast(e.RollingMrpForecast)
    # A 2025 decision retains its already-known 2026 source projection.
    for decision in (0, 354, 355, 361, 362, 364):
        for target in (362, 368, 369, 375, 376, 400):
            assert candidate.source_for_day(CLIENT, selected=candidate.selection(decision), target_day=target) == (
                old.source_for_day(CLIENT, selected=old.selection(decision), target_day=target))
    # Opening2026 incomplete week stays frozen; next Monday switches.
    assert candidate.source_for_day(CLIENT, selected=candidate.selection(365), target_day=368) == (
        old.source_for_day(CLIENT, selected=old.selection(365), target_day=368))
    value, known = candidate.source_for_day(CLIENT, selected=candidate.selection(365), target_day=369)
    assert value[0] == 15 and known == 365  # 100 * 1.05 / 7 = 15.
    assert value[1].startswith("synthetic_coherent_customer:")
    assert old.source_for_day(CLIENT, selected=old.selection(365), target_day=369)[0][0] == 200
    assert candidate.source_for_day(CLIENT, selected=candidate.selection(365), target_day=376)[0][0] == 0


def test_candidate_customer_forecast_matches_unchanged_integer_orders_and_consumes_once():
    with _adapters("coherent_scenario") as (_, e, _):
        forecast = _forecast(e.RollingMrpForecast)
        history = e.SourceCustomerHistory(_customer_payload(), demand_pairs={CLIENT},
            origin_date="2025-01-01", sim_days=1825)
    with _adapters("source_priority") as (_, e, _):
        baseline = e.SourceCustomerHistory(_customer_payload(), demand_pairs={CLIENT},
            origin_date="2025-01-01", sim_days=1825)
    for day in range(1825):
        actual = history.quantity(CLIENT, decision_day=day, target_day=day)
        assert actual == baseline.quantity(CLIENT, decision_day=day, target_day=day)
        assert type(actual[0]) is int
        forecast.observe_demand(day, {CLIENT: actual[0]})
        if day in (369, 370, 375, 376, 733, 1097, 1461):
            cycle, position = divmod(day + 2, 364)
            weekly = 0 if position // 7 == 2 else int(Fraction(100) * Fraction(21, 20) ** cycle)
            audit = forecast.consumption_audit(CLIENT, day)
            offset = position % 7
            assert audit["weekly_forecast_qty"] == weekly
            assert audit["arrived_demand_qty"] == weekly * (offset + 1) // 7
            assert audit["remaining_forecast_qty"] == weekly - audit["arrived_demand_qty"]
            assert audit["source_vintage_day"] == 365
    rows = forecast.projection_audit_rows(CLIENT, decision_day=730, horizon_days=364)
    assert all(r["status"] == "synthetic_scenario_not_industrial_forecast" for r in rows)


def test_candidate_other_use_forecast_is_requested_profile_with_integer_UN_and_explicit_zero():
    payload = _external_payload()
    saved = deepcopy(payload)
    kwargs = dict(pair_uoms={KG: "KG", UN: "UN"}, origin_date="2025-01-01", horizon_days=2190)
    with _adapters("source_priority") as (p, _, _):
        baseline = p.ExternalComponentDemandCalendar(payload, **kwargs)
    with _adapters("coherent_scenario") as (p, _, frozen):
        candidate = p.ExternalComponentDemandCalendar(payload, **kwargs)
    for decision in (350, 361, 364):
        assert candidate.requirements(decision_day=decision, first_day=365, through_day=400) == (
            baseline.requirements(decision_day=decision, first_day=365, through_day=400))
    values = candidate.requirements(decision_day=365, first_day=366, through_day=400)
    # Sunday368 retains100/day source, Monday369 begins105% frozen profile.
    assert next(r.qty for r in values[KG] if r.due_day == 368) == 100
    for pair, unit in ((KG, "KG"), (UN, "UN")):
        by_day = {r.due_day: r.qty for r in values[pair]}
        assert sum(by_day.get(d, 0) for d in range(369, 376)) == (73.5 if unit == "KG" else 15)
        assert not any(d in by_day for d in range(376, 383))
        assert set(range(376, 383)) <= candidate.covered_days(pair,
            decision_day=365, first_day=366, through_day=400)
        for day in range(369, 401):
            assert by_day.get(day, 0) == frozen.quantity(pair, day)
        if unit == "UN":
            assert all(float(r.qty).is_integer() for r in values[pair])
        detail = candidate.provenance(next(r.requirement_id for r in values[pair] if r.due_day == 369))
        assert detail["known_day"] == 365
        assert "scenario" in detail["source_cells"]
    assert payload == saved
    # Unknown template never silently means zero.
    del frozen.weekly[KG, 5]
    with pytest.raises(ValueError, match="Missing exogenous template"):
        candidate.requirements(decision_day=365, first_day=369, through_day=375)


def test_candidate_clips_industrial_I_and_keeps_BOM_external_reserves_and_commitments_once():
    payload = _industrial_payload()
    kwargs = dict(pair_uoms={KG: "KG", UN: "UN"}, origin_date="2025-01-01")
    with _adapters("source_priority") as (_, e, _):
        baseline = e.IndustrialComponentPlanningCalendar(payload, **kwargs)
    with _adapters("coherent_scenario") as (_, e, _):
        candidate = e.IndustrialComponentPlanningCalendar(payload, **kwargs)
    assert candidate.windows(KG, decision_day=364, first_day=365, through_day=390) == (
        baseline.windows(KG, decision_day=364, first_day=365, through_day=390))
    clipped = candidate.windows(KG, decision_day=365, first_day=366, through_day=390)
    assert [(r.first_day, r.end_day_exclusive, r.qty) for r in clipped] == [(368, 369, 100)]
    assert candidate.windows(KG, decision_day=369, first_day=370, through_day=1097) == ()
    needs = [planning.Requirement("derived:BOM", 370, 25),
             planning.Requirement("external:coherent", 370, 73.5),
             planning.Requirement("reserve:source", 370, 13),
             planning.Requirement("opening_production:initial_once", 371, 7)]
    for policy in (None, "separate_own_and_other_v1", "source_weekly_with_committed_floor_v1"):
        result, audit = planning.reconcile_industrial_requirements(needs, (), pair=KG,
            decision_day=369, policy=policy)
        assert result == needs and audit == []
        assert sum(Fraction(str(r.qty)) for r in result) == Fraction(237, 2)


def test_candidate_physical_observation_calendar_is_never_rewritten():
    payload = dict(schema_version=1, origin="2025-01-01", scenario_id="scn:BASE",
        semantics="incremental_non_modelled_component_use", repeat_period_days=None, physical_use_only=True,
        rows=[dict(demand_id="observed_zero", node_id=KG[0], item_id=KG[1], uom="KG",
            known_day=364, period_start_day=364, period_days=1, qty=0,
            source_file="memory_movements.xlsx", source_cells="I1", estimation_basis="observed")])
    with _adapters("coherent_scenario") as (p, _, _):
        calendar = p.ExternalComponentDemandCalendar(payload, pair_uoms={KG: "KG"},
            origin_date="2025-01-01", horizon_days=1825)
    assert calendar.requirements(decision_day=364, first_day=364, through_day=400) == {}
    assert calendar.covered_days(KG, decision_day=363, first_day=364, through_day=400) == frozenset()
    assert calendar.covered_days(KG, decision_day=364, first_day=365, through_day=400) == frozenset()
    assert calendar.day_audit(KG, decision_day=369)["forecast_selection_mode"] == "fixed_scenario"
