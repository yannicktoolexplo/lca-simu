"""Memory-only oracles for a rolling forecast horizon distinct from execution.

Source forecasts are information, not executed receipts or physical inventory.
No workbook, filesystem fixture, simulation or integrity mutation is used here.
"""
from copy import deepcopy
import json

import pytest

from etudecas.simulation.engine.mrp_planning import (
    ExternalComponentDemandCalendar, FirmReceipt, LotSizing, Requirement,
    plan_dated_requirements, serve_external_component_requirements,
)
from etudecas.simulation.engine.run_first_simulation import mrp_planning_horizon_days
from etudecas.simulation.experiments.shared_components import revision_series


PAIR = ("M-1810", "item:001757")
OTHER = ("M-1810", "item:OTHER")


def period(start, qty, *, length=7, source_row=100):
    return {"demand_id": f"need-{start}", "period_start_day": start,
        "period_days": length, "qty": qty, "source_file": "MRP.xlsx",
        "source_cells": f"Feuille1!I{source_row}",
        "estimation_basis": "unchanged_first_plan_share"}


def payload(versions, *, schema=3):
    return {"schema_version": schema, "origin": "2025-01-01", "scenario_id": "rolling52",
        "semantics": "incremental_non_modelled_component_use", "repeat_period_days": None,
        "rows": [], "versioned_series": [{"node_id": PAIR[0], "item_id": PAIR[1], "uom": "KG",
            "period_anchor_day": 4, "period_days": 7, "repeat_period_days": 0,
            "current_bucket_policy": "freeze_previous_exclude_current_vintage",
            "missing_future_policy": "unprovided_not_observed_zero", "versions": versions}]}


def calendar(data, *, horizon=729):
    return ExternalComponentDemandCalendar(data, pair_uoms={PAIR: "KG", OTHER: "UN"},
        origin_date="2025-01-01", horizon_days=horizon)


def requirements(cal, decision, first, end):
    return cal.requirements(decision_day=decision, first_day=first, through_day=end).get(PAIR, ())


@pytest.mark.parametrize("decision,legacy", [(0, 364), (300, 64), (364, 0)])
def test_rolling_window_has_364_future_days_independent_of_export_end(decision, legacy):
    assert mrp_planning_horizon_days(decision_day=decision, execution_days=365) == legacy
    count = mrp_planning_horizon_days(decision_day=decision, execution_days=365, configured_days=364)
    assert count == 364
    future_days = range(decision + 1, decision + count + 1)
    assert len(future_days) == 364
    assert future_days[0] == decision + 1 and future_days[-1] == decision + 364


def test_rolling_window_does_not_change_when_only_execution_duration_changes():
    for execution_days in (365, 730, 1825):
        assert mrp_planning_horizon_days(decision_day=300, execution_days=execution_days,
            configured_days=364) == 364
    assert mrp_planning_horizon_days(decision_day=300, execution_days=1825) == 364


@pytest.mark.parametrize("invalid", [0, -1, True, 363, 365, 364.0, "364"])
def test_rolling_window_rejects_ambiguous_or_unapproved_lengths(invalid):
    with pytest.raises(ValueError):
        mrp_planning_horizon_days(decision_day=300, execution_days=365, configured_days=invalid)


def test_rolling_option_cannot_silently_change_historical_execution():
    with pytest.raises(ValueError):
        mrp_planning_horizon_days(decision_day=300, execution_days=365,
            configured_days=364, execution_mode="historical")


def test_known_need_after_export_end_generates_a_purchase_before_export_end():
    # Manual arithmetic: J400 - 84 days = J316, before the final exported day364.
    need = Requirement("known-2026-need", 400, 100)
    plan = plan_dated_requirements(decision_day=300, available_qty=0,
        requirements=[need], firm_receipts=[], lead_days=84, lot_sizing=LotSizing(multiple=100))
    assert plan.proposed_qty == 100 and len(plan.proposals) == 1
    proposal = plan.proposals[0]
    assert (proposal.release_day, proposal.available_day, proposal.qty) == (316, 400, 100)
    assert plan.late_qty == 0
    assert need == Requirement("known-2026-need", 400, 100)


def test_source2026_forecast_is_visible_only_from_its_known_vintage():
    data = payload([
        {"vintage_id": "v298", "known_day": 298, "rows": [period(396, 70)]},
        {"vintage_id": "v305", "known_day": 305, "rows": [period(396, 140, source_row=200)]},
    ])
    saved = deepcopy(data)
    cal = calendar(data)
    assert requirements(cal, 297, 396, 402) == ()
    old = requirements(cal, 300, 396, 402)
    new = requirements(cal, 305, 396, 402)
    assert [r.qty for r in old] == [10] * 7
    assert [r.qty for r in new] == [20] * 7
    assert [r.requirement_id for r in old] == [r.requirement_id for r in new]
    assert [r.due_day for r in new] == list(range(396, 403))
    assert data == saved


def test_2026_future_rows_never_become_2025_physical_demand():
    cal = calendar(payload([{"vintage_id": "v354", "known_day": 354,
        "rows": [period(368, 700), period(396, 1400)]}]))
    future = requirements(cal, 354, 355, 718)
    assert sum(r.qty for r in future) == 2100
    assert all(r.due_day >= 368 for r in future)
    assert all(cal.due(day) == {} for day in range(365))


def test_year_crossing_week_keeps_daily_2025_quantity_and_full_source_week():
    old = calendar(payload([{"vintage_id": "v354", "known_day": 354,
        "rows": [period(361, 40, length=4)]}], schema=2), horizon=365)
    new = calendar(payload([{"vintage_id": "v354", "known_day": 354,
        "rows": [period(361, 70)]}]))
    for day in range(365):
        assert new.due(day) == old.due(day)
    assert sum(r.qty for r in requirements(new, 354, 361, 367)) == 70
    assert sum(r.qty for r in requirements(new, 354, 365, 367)) == 30
    assert requirements(old, 354, 365, 367) == ()


def test_current_week_remains_frozen_across_the_year_boundary():
    cal = calendar(payload([
        {"vintage_id": "v354", "known_day": 354,
         "rows": [period(361, 70), period(368, 140)]},
        {"vintage_id": "v361", "known_day": 361,
         "rows": [period(368, 210, source_row=200)]},
    ]))
    assert [r.qty for r in requirements(cal, 361, 361, 367)] == [10] * 7
    assert [r.qty for r in requirements(cal, 364, 368, 374)] == [30] * 7
    assert cal.day_audit(PAIR, decision_day=364)["forecast_known_day"] == 354
    assert cal.day_audit(PAIR, decision_day=364)["forecast_latest_known_day"] == 361


def test_new_vintage_missing2026_week_does_not_reuse_old_forecast_or_observed_zero():
    cal = calendar(payload([
        {"vintage_id": "v354", "known_day": 354, "rows": [period(396, 700)]},
        {"vintage_id": "v361", "known_day": 361, "rows": []},
    ]))
    assert sum(r.qty for r in requirements(cal, 360, 396, 402)) == 700
    assert requirements(cal, 361, 396, 402) == ()
    audit = cal.day_audit(PAIR, decision_day=396)
    assert audit["forecast_source_covered"] == 0
    assert audit["forecast_coverage_reason"] == "missing_period_in_selected_vintage"


@pytest.mark.parametrize("firm_day,late", [(400, 0), (405, 100)])
def test_future_firm_is_preserved_without_a_duplicate_year_end_purchase(firm_day, late):
    firms = [FirmReceipt("already-purchased", firm_day, 100)]
    saved = deepcopy(firms)
    plan = plan_dated_requirements(decision_day=300, available_qty=0,
        requirements=[Requirement("2026", 400, 100)], firm_receipts=firms, lead_days=84)
    assert plan.proposed_qty == 0 and plan.late_qty == late
    assert firms == saved


def test_backlog_issued_in2025_keeps_its_original_vintage_when_served_later():
    cal = calendar(payload([
        {"vintage_id": "v354", "known_day": 354, "rows": [period(361, 70)]},
        {"vintage_id": "v361", "known_day": 361, "rows": [period(368, 700)]},
    ]))
    first = serve_external_component_requirements(decision_day=364, available_qty=4,
        backlog=[], due=cal.due(364)[PAIR], uom="KG")
    assert first.consumed_qty == 4 and sum(r.qty for r in first.remaining) == 6
    served = serve_external_component_requirements(decision_day=365, available_qty=16,
        backlog=first.remaining, due=cal.due(365)[PAIR], uom="KG")
    assert served.backlog_start_qty == 6 and served.demand_qty == 10
    assert served.consumed_qty == 16 and served.remaining == ()
    assert cal.provenance(served.allocations[0].requirement_id)["known_day"] == 354


@pytest.mark.parametrize("fault", ["schema2_future", "schema2_full_crossing", "schema3_truncated",
    "current_bucket", "beyond52weeks", "future_vintage"])
def test_schema_extension_does_not_relax_legacy_or_source_horizon_guards(fault):
    data = payload([{"vintage_id": "v354", "known_day": 354, "rows": [period(361, 70)]}])
    version = data["versioned_series"][0]["versions"][0]
    if fault == "schema2_future": data["schema_version"] = 2; version["rows"] = [period(368, 70)]
    elif fault == "schema2_full_crossing": data["schema_version"] = 2
    elif fault == "schema3_truncated": version["rows"] = [period(361, 40, length=4)]
    elif fault == "current_bucket": version["rows"] = [period(354, 70)]
    elif fault == "beyond52weeks": version["rows"] = [period(725, 70)]
    elif fault == "future_vintage": version["known_day"] = 368; version["rows"] = [period(375, 70)]
    with pytest.raises(ValueError):
        calendar(data)


def test_source_horizon_keeps52_full_weeks_but_query_stops_at_364_future_days():
    cal = calendar(payload([{"vintage_id": "v354", "known_day": 354,
        "rows": [period(354 + week * 7, 70) for week in range(1, 53)]}]))
    all_provided = requirements(cal, 354, 361, 724)
    assert len(all_provided) == 52 * 7 and sum(r.qty for r in all_provided) == 3640
    assert all_provided[-1].due_day == 724
    bounded = requirements(cal, 354, 355, 354 + 364)
    assert len(bounded) == 358 and bounded[-1].due_day == 718
    assert requirements(cal, 354, 725, 725) == ()  # Missing source, not an observed zero.


def test_preparation_keeps_full2026_weeks_without_second_unit_conversion_or_HJK_use():
    records = [
        {"known_day": 354, "day": 354, "qty": 999, "unit": "KG", "row": 90},
        {"known_day": 354, "day": 361, "qty": 70, "unit": "KG", "row": 100},
        {"known_day": 354, "day": 711, "qty": 140, "unit": "KG", "row": 101},
        {"known_day": 354, "day": 718, "qty": 210, "unit": "KG", "row": 102},
        {"known_day": 354, "day": 725, "qty": 280, "unit": "KG", "row": 103},
    ]
    old = revision_series(records, [354], "001757/1810", .5)
    revised = revision_series(records, [354], "001757/1810", .5, planning_horizon_days=364)
    assert [(r["period_start_day"], r["period_days"], r["qty"]) for r in old["versions"][0]["rows"]] == [(361, 4, 20)]
    assert [(r["period_start_day"], r["period_days"], r["qty"]) for r in revised["versions"][0]["rows"]] == [(361, 7, 35), (711, 7, 70), (718, 7, 105)]
    for record in records:
        record.update(H=10**12, J=10**12, K=10**12)
    assert revision_series(records, [354], "001757/1810", .5, planning_horizon_days=364) == revised


def test_static_other_component_scenario_remains_identical_with_new_schema():
    new = payload([{"vintage_id": "v354", "known_day": 354, "rows": [period(368, 70)]}])
    new["repeat_period_days"] = 365
    new["rows"] = [{**period(11, 10), "demand_id": "unchanged", "node_id": OTHER[0],
        "item_id": OTHER[1], "known_day": 4, "uom": "UN"}]
    old = deepcopy(new); old["schema_version"] = 1; del old["versioned_series"]
    a, b = calendar(new), calendar(old)
    for day in range(365):
        assert a.due(day).get(OTHER, ()) == b.due(day).get(OTHER, ())
    assert a.requirements(decision_day=369, first_day=376, through_day=382)[OTHER] == \
        b.requirements(decision_day=369, first_day=376, through_day=382)[OTHER]


def exported_2025_oracle_example(*, schema=3):
    """Four executed10KG days; future700KG remains information, not a debit."""
    source_rows = [period(361, 70), period(368, 700)] if schema == 3 else [period(361, 40, length=4)]
    config = payload([{"vintage_id": "v354", "known_day": 354, "rows": source_rows}], schema=schema)
    series, events = [], []
    for day in range(365):
        issued = day >= 361
        selected = "v354" if issued else ""
        source_known = 354 if issued else ""
        quantity = 10 if issued else 0
        series.append({"day": day, "node_id": PAIR[0], "item_id": PAIR[1], "uom": "KG",
            "demand_qty": quantity, "backlog_start_qty": 0, "required_qty": quantity,
            "consumed_qty": quantity, "backlog_end_qty": 0, "available_before_qty": quantity,
            "available_after_qty": 0, "core_consumed_qty": 0, "total_component_consumed_qty": quantity,
            "forecast_selection_mode": "rolling_vintages_current_week_frozen",
            "forecast_vintage_id": selected, "forecast_known_day": source_known,
            "forecast_latest_known_vintage_id": "v354" if day >= 354 else "",
            "forecast_latest_known_day": 354 if day >= 354 else "",
            "forecast_period_start_day": 4 + ((day - 4) // 7) * 7,
            "forecast_source_covered": int(issued),
            "forecast_coverage_reason": "provided_scenario_period" if issued else "no_known_vintage_before_period",
            "forecast_source_file": "MRP.xlsx" if issued else "",
            "forecast_source_cells": "Feuille1!I100" if issued else ""})
        if issued:
            events.append({"day": day, "node_id": PAIR[0], "item_id": PAIR[1], "uom": "KG",
                "event_type": "external_component_consume", "qty": 10,
                "source_id": f"external:rolling52:revision:{PAIR[0]}:{PAIR[1]}:W361:D{day}",
                "notes": json.dumps({"scope": "estimated_non_modelled_component_use", "due_day": day,
                    "known_day": 354, "cycle_index": 0, "scenario_id": "rolling52", "demand_id": "need-361",
                    "source_file": "MRP.xlsx", "source_cells": "Feuille1!I100",
                    "estimation_basis": "unchanged_first_plan_share", "vintage_id": "v354",
                    "period_start_day": 361, "forecast_update_mode": "rolling_vintages_future_replacement_current_week_frozen"})})
    return config, series, events


@pytest.mark.parametrize("schema", [2, 3])
def test_independent_csv_audit_accepts_same2025_execution_with_separate_future_forecast(schema):
    from etudecas.testing.independent_review import Evidence, audit_external_component_service
    config, series, events = exported_2025_oracle_example(schema=schema)
    evidence = Evidence()
    assert audit_external_component_service(series, events, [], config, 365, evidence) == 365
    assert sum(r["qty"] for r in events) == 40
    assert all(check["failed"] == 0 for check in evidence.checks.values())


@pytest.mark.parametrize("fault,failed_check", [
    ("executed_future_early", "external_event_matches_declared_requirement"),
    ("truncated_source", "external_revision_only_future_source"),
    ("unprovided_future_horizon", "external_revision_only_future_source"),
    ("future_vintage", "external_revision_vintage_known_in2025"),
    ("event_outside_export", "external_event_within_execution_horizon"),
])
def test_independent_csv_audit_rejects_fake_execution_or_malformed_future_source(fault, failed_check):
    from etudecas.testing.independent_review import Evidence, audit_external_component_service
    config, series, events = exported_2025_oracle_example()
    version = config["versioned_series"][0]["versions"][0]
    if fault == "executed_future_early":
        events[-1]["source_id"] = f"external:rolling52:revision:{PAIR[0]}:{PAIR[1]}:W368:D368"
    elif fault == "truncated_source": version["rows"][0].update(period_days=4, qty=40)
    elif fault == "unprovided_future_horizon": version["rows"].append(period(725, 700))
    elif fault == "future_vintage": version["known_day"] = 365
    elif fault == "event_outside_export": events[-1]["day"] = 365
    evidence = Evidence()
    audit_external_component_service(series, events, [], config, 365, evidence)
    assert evidence.checks[failed_check]["failed"] > 0
