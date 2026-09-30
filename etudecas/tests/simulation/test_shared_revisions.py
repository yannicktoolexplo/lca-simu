"""Independent in-memory oracles for replacing shared-use forecasts.

No workbook, output directory, filesystem fixture or simulation is used here.
Forecasts remain hypotheses; only already known future buckets may be replaced.
"""
from copy import deepcopy
import json

import pytest

from etudecas.simulation.engine.mrp_planning import (
    ExternalComponentDemandCalendar, FirmReceipt, Requirement,
    plan_dated_requirements, serve_external_component_requirements,
)
from etudecas.simulation.experiments.shared_components import revision_series


PAIR = ("M-1810", "item:001848")
OTHER = ("M-1", "item:OTHER")


def row(start, qty, *, source_row=84, length=7):
    return {"demand_id": f"material-week-{start}", "period_start_day": start,
            "period_days": length, "qty": qty, "source_file": "MRP.xlsx",
            "source_cells": f"Feuille1!I{source_row}",
            "estimation_basis": "fixed_initial_share_not_observed_consumption"}


def payload(versions=None, *, unit="KG"):
    if versions is None:
        versions = [
            {"vintage_id": "v4", "known_day": 4,
             "rows": [row(11, 70), row(18, 140), row(25, 210)]},
            {"vintage_id": "v11", "known_day": 11,
             "rows": [row(18, 210, source_row=1065), row(25, 280, source_row=1066)]},
            {"vintage_id": "v18", "known_day": 18,
             "rows": [row(25, 0, source_row=2049), row(32, 350, source_row=2050)]},
        ]
    return {"schema_version": 2, "origin": "2025-01-01", "scenario_id": "trial",
        "semantics": "incremental_non_modelled_component_use", "repeat_period_days": None,
        "rows": [], "versioned_series": [{"node_id": PAIR[0], "item_id": PAIR[1], "uom": unit,
            "period_anchor_day": 4, "period_days": 7, "repeat_period_days": 0,
            "current_bucket_policy": "freeze_previous_exclude_current_vintage",
            "missing_future_policy": "unprovided_not_observed_zero", "versions": versions}]}


def calendar(data=None, *, unit="KG", horizon=365):
    return ExternalComponentDemandCalendar(data or payload(unit=unit),
        pair_uoms={PAIR: unit, OTHER: "UN"}, origin_date="2025-01-01", horizon_days=horizon)


def requirements(cal, decision, start, end):
    return cal.requirements(decision_day=decision, first_day=start, through_day=end).get(PAIR, ())


def test_revisions_unknown_vintage_cannot_affect_a_known_future_week():
    cal = calendar()
    assert requirements(cal, 3, 18, 24) == ()
    assert sum(r.qty for r in requirements(cal, 4, 18, 24)) == 140
    assert sum(r.qty for r in requirements(cal, 10, 18, 24)) == 140
    assert sum(r.qty for r in requirements(cal, 11, 18, 24)) == 210
    assert sum(r.qty for r in requirements(cal, 17, 18, 24)) == 210


def test_revisions_current_week_stays_frozen_in_execution_and_planning():
    cal = calendar()
    expected = requirements(cal, 10, 11, 17)
    assert len(expected) == 7 and sum(r.qty for r in expected) == 70
    # The new vintage cannot remove or replay this now-current week.
    assert requirements(cal, 11, 11, 17) == expected
    assert requirements(cal, 16, 11, 17) == expected
    assert requirements(cal, 300, 11, 17) == expected
    assert [cal.due(day)[PAIR][0].qty for day in range(11, 18)] == [10] * 7
    assert requirements(cal, 11, 12, 17) == expected[1:]


def test_revisions_replace_future_quantity_without_changing_requirement_identity():
    cal = calendar()
    old = requirements(cal, 4, 18, 24)
    new = requirements(cal, 11, 18, 24)
    assert [r.requirement_id for r in old] == [r.requirement_id for r in new]
    assert [r.due_day for r in old] == list(range(18, 25))
    assert sum(r.qty for r in new) == 210  # Not 140 + 210.
    assert {cal.provenance(r.requirement_id)["known_day"] for r in new} == {11}
    assert {cal.provenance(r.requirement_id)["source_cells"] for r in new} == {"Feuille1!I1065"}


def test_revisions_missing_future_week_does_not_fall_back_to_an_older_vintage():
    data = payload()
    data["versioned_series"][0]["versions"] = [
        {"vintage_id": "v4", "known_day": 4, "rows": [row(25, 210)]},
        {"vintage_id": "v11", "known_day": 11, "rows": [row(18, 70)]},
    ]
    cal = calendar(data)
    assert sum(r.qty for r in requirements(cal, 10, 25, 31)) == 210
    assert requirements(cal, 11, 25, 31) == ()
    assert cal.due(25) == {}
    # This is an unprovided forecast, not evidence of industrial zero demand.


def test_revisions_explicit_zero_replaces_future_but_does_not_rewrite_past_need():
    cal = calendar()
    assert sum(r.qty for r in requirements(cal, 17, 25, 31)) == 280
    assert requirements(cal, 18, 25, 31) == ()
    assert sum(r.qty for r in requirements(cal, 18, 18, 24)) == 210


def test_revisions_audit_distinguishes_frozen_week_from_latest_known_forecast():
    cal = calendar()
    audit = cal.day_audit(PAIR, decision_day=11)
    assert audit["forecast_vintage_id"] == "v4"
    assert audit["forecast_known_day"] == 4
    assert audit["forecast_latest_known_vintage_id"] == "v11"
    assert audit["forecast_latest_known_day"] == 11
    assert audit["forecast_period_start_day"] == 11
    assert audit["forecast_source_covered"] == 1
    assert audit["forecast_source_cells"] == "Feuille1!I84"


def test_revisions_audit_never_labels_a_missing_forecast_as_an_observed_zero():
    cal = calendar(payload([
        {"vintage_id": "v4", "known_day": 4, "rows": [row(11, 0), row(25, 70)]},
        {"vintage_id": "v11", "known_day": 11, "rows": []},
    ]))
    zero = cal.day_audit(PAIR, decision_day=11)
    missing = cal.day_audit(PAIR, decision_day=18)
    assert cal.due(11) == cal.due(18) == {}
    assert zero["forecast_source_covered"] == 1
    assert zero["forecast_source_cells"] == "Feuille1!I84"
    assert missing["forecast_source_covered"] == 0
    assert missing["forecast_coverage_reason"] == "missing_period_in_selected_vintage"
    assert missing["forecast_source_cells"] == ""
    assert requirements(cal, 11, 25, 31) == ()  # An empty new version replaces the old future.


def test_revisions_requantize_each_week_without_fractional_physical_units():
    cal = calendar(payload([
        {"vintage_id": "v4", "known_day": 4, "rows": [row(18, 10)]},
        {"vintage_id": "v11", "known_day": 11, "rows": [row(18, 15)]},
    ], unit="UN"), unit="UN")
    assert [r.qty for r in requirements(cal, 4, 18, 24)] == [1, 1, 2, 1, 2, 1, 2]
    assert [r.qty for r in requirements(cal, 11, 18, 24)] == [2, 2, 2, 2, 2, 2, 3]
    assert sum(cal.due(day)[PAIR][0].qty for day in range(18, 25)) == 15


def test_revisions_unserved_past_demand_remains_once_after_a_new_vintage():
    data = payload(unit="UN")
    for version in data["versioned_series"][0]["versions"]:
        for record in version["rows"]:
            if record["period_start_day"] == 11:
                record["qty"] = 14
    cal = calendar(data, unit="UN")
    first = serve_external_component_requirements(decision_day=11, available_qty=1,
        backlog=(), due=cal.due(11)[PAIR], uom="UN")
    assert first.consumed_qty == 1
    assert sum(r.qty for r in first.remaining) == 1
    second = serve_external_component_requirements(decision_day=12, available_qty=3,
        backlog=first.remaining, due=cal.due(12)[PAIR], uom="UN")
    assert second.backlog_start_qty == 1
    assert second.demand_qty == 2
    assert second.consumed_qty == 3 and second.remaining == ()
    assert second.allocations[0].requirement_id == first.remaining[0].requirement_id
    assert first.consumed_qty + second.consumed_qty == 4


@pytest.mark.parametrize("revised,expected_new,unused_firm", [(210, 70, 0), (70, 0, 70)])
def test_revisions_never_cancel_or_duplicate_an_existing_firm_receipt(revised, expected_new, unused_firm):
    data = payload()
    data["versioned_series"][0]["versions"][1]["rows"][0]["qty"] = revised
    cal = calendar(data)
    committed = [FirmReceipt("committed-purchase", 20, 140)]
    saved = deepcopy(committed)
    old = plan_dated_requirements(decision_day=4, available_qty=0,
        requirements=requirements(cal, 4, 18, 24), firm_receipts=committed, lead_days=5)
    updated = plan_dated_requirements(decision_day=11, available_qty=0,
        requirements=requirements(cal, 11, 18, 24), firm_receipts=committed, lead_days=5)
    assert old.proposed_qty == 0
    assert updated.proposed_qty == expected_new
    assert updated.unallocated_firm_qty == unused_firm
    assert committed == saved  # Original physical date and quantity are intact.


def test_revisions_leave_other_static_series_and_their_repeat_convention_unchanged():
    data = payload()
    data["repeat_period_days"] = 365
    data["rows"] = [{"demand_id": "other-use", "node_id": OTHER[0], "item_id": OTHER[1],
        "known_day": 4, "period_start_day": 11, "period_days": 7, "qty": 10,
        "uom": "UN", "source_file": "MRP.xlsx", "source_cells": "I999",
        "estimation_basis": "unchanged_static_first_plan"}]
    static = deepcopy(data)
    static["schema_version"] = 1
    del static["versioned_series"]
    mixed, original = calendar(data, horizon=730), calendar(static, horizon=730)
    assert mixed.requirements(decision_day=369, first_day=376, through_day=382)[OTHER] == \
           original.requirements(decision_day=369, first_day=376, through_day=382)[OTHER]
    assert requirements(mixed, 369, 376, 382) == ()
    assert sum(r.qty for r in mixed.requirements(decision_day=369, first_day=376, through_day=382)[OTHER]) == 10


def test_revisions_last_year_bucket_keeps_exact_truncated_quantity_without_repetition():
    cal = calendar(payload([{"vintage_id": "last", "known_day": 354,
        "rows": [row(361, 40, length=4)]}]), horizon=730)
    actual = requirements(cal, 354, 361, 400)
    assert [r.due_day for r in actual] == [361, 362, 363, 364]
    assert [r.qty for r in actual] == [10] * 4
    assert requirements(cal, 719, 726, 729) == ()


@pytest.mark.parametrize("fault", ["current_row", "duplicate_week", "duplicate_vintage", "off_anchor", "repeat", "unit", "static_overlap"])
def test_revisions_ambiguous_or_incompatible_inputs_are_rejected(fault):
    data = payload()
    series = data["versioned_series"][0]
    if fault == "current_row": series["versions"][0]["rows"][0]["period_start_day"] = 4
    elif fault == "duplicate_week": series["versions"][0]["rows"].append(deepcopy(series["versions"][0]["rows"][0]))
    elif fault == "duplicate_vintage": series["versions"].append(deepcopy(series["versions"][0]))
    elif fault == "off_anchor": series["versions"][0]["rows"][0]["period_start_day"] = 12
    elif fault == "repeat": series["repeat_period_days"] = 365
    elif fault == "unit": series["uom"] = "UN"
    elif fault == "static_overlap":
        record = {**row(11, 70), "node_id": PAIR[0], "item_id": PAIR[1], "uom": "KG", "known_day": 4}
        data["rows"].append(record)
    with pytest.raises(ValueError):
        calendar(data)


def test_revision_preparation_uses_only_future_I_with_fixed_share_and_stable_week_id():
    records = [
        {"known_day": 4, "day": 4, "qty": 924.006, "unit": "KG", "row": 83},
        {"known_day": 4, "day": 11, "qty": 1450, "unit": "KG", "row": 84},
        {"known_day": 11, "day": 11, "qty": 2374, "unit": "KG", "row": 1064},
        {"known_day": 11, "day": 18, "qty": 720, "unit": "KG", "row": 1065},
        {"known_day": 4, "day": 18, "qty": 900, "unit": "KG", "row": 85},
    ]
    original = deepcopy(records)
    result = revision_series(records, [4, 11], "001848/1810", .5)
    old, new = result["versions"]
    assert [(r["period_start_day"], r["qty"]) for r in old["rows"]] == [(11, 725), (18, 450)]
    assert [(r["period_start_day"], r["qty"]) for r in new["rows"]] == [(18, 360)]
    assert old["rows"][1]["demand_id"] == new["rows"][0]["demand_id"]
    assert new["rows"][0]["source_cells"] == "Feuille1!I1065"
    assert records == original
    for record in records:
        record.update(H=10**12, J=10**12, K=10**12)
    assert revision_series(records, [4, 11], "001848/1810", .5) == result


def test_revision_preparation_does_not_convert_kg_twice_and_prorates_final_four_days():
    # 70,000 raw G were normalized to 70 KG before this pure preparation step.
    result = revision_series([{"known_day": 354, "day": 361, "qty": 70,
        "unit": "KG", "row": 100}], [354], "001848/1810", .5)
    record = result["versions"][0]["rows"][0]
    assert record["qty"] == 20  # 70 KG * 50% * 4/7, not 0.02 KG or 35 KG.
    assert record["period_days"] == 4
    assert result["uom"] == "KG"


def revision_audit_example():
    """Manual two-day service: one old unit plus one new unit served on day12."""
    data = payload([
        {"vintage_id": "v4", "known_day": 4, "rows": [row(11, 7)]},
        {"vintage_id": "v11", "known_day": 11, "rows": [row(18, 7000)]},
    ], unit="UN")
    series = []
    for day in range(13):
        supplied = day >= 11
        audit = {"forecast_selection_mode": "rolling_vintages_current_week_frozen",
            "forecast_vintage_id": "v4" if supplied else "",
            "forecast_known_day": 4 if supplied else "",
            "forecast_latest_known_vintage_id": "v11" if supplied else "v4" if day >= 4 else "",
            "forecast_latest_known_day": 11 if supplied else 4 if day >= 4 else "",
            "forecast_period_start_day": 11 if supplied else 4 if day >= 4 else -3,
            "forecast_source_covered": int(supplied),
            "forecast_coverage_reason": "provided_scenario_period" if supplied else "no_known_vintage_before_period",
            "forecast_source_file": "MRP.xlsx" if supplied else "",
            "forecast_source_cells": "Feuille1!I84" if supplied else ""}
        series.append({"day": day, "node_id": PAIR[0], "item_id": PAIR[1], "uom": "UN",
            "demand_qty": int(supplied), "backlog_start_qty": int(day == 12),
            "required_qty": 2 if day == 12 else int(supplied), "consumed_qty": 2 if day == 12 else 0,
            "backlog_end_qty": int(day == 11), "available_before_qty": 2 if day == 12 else 0,
            "available_after_qty": 0, "core_consumed_qty": 0,
            "total_component_consumed_qty": 2 if day == 12 else 0, **audit})
    events = []
    for due in (11, 12):
        events.append({"day": 12, "node_id": PAIR[0], "item_id": PAIR[1], "uom": "UN",
            "event_type": "external_component_consume", "qty": 1,
            "source_id": f"external:trial:revision:{PAIR[0]}:{PAIR[1]}:W11:D{due}",
            "notes": json.dumps({"scope": "estimated_non_modelled_component_use", "due_day": due,
                "known_day": 4, "cycle_index": 0, "scenario_id": "trial", "demand_id": "material-week-11",
                "source_file": "MRP.xlsx", "source_cells": "Feuille1!I84",
                "estimation_basis": "fixed_initial_share_not_observed_consumption",
                "vintage_id": "v4", "period_start_day": 11,
                "forecast_update_mode": "rolling_vintages_future_replacement_current_week_frozen"})})
    return data, series, events


def test_revision_independent_audit_accepts_frozen_source_and_later_backlog_service():
    from etudecas.testing.independent_review import Evidence, audit_external_component_service
    data, series, events = revision_audit_example()
    evidence = Evidence()
    assert audit_external_component_service(series, events, [], data, 13, evidence) == 13
    assert all(check["failed"] == 0 for check in evidence.checks.values())


@pytest.mark.parametrize("fault", ["future_known", "wrong_vintage", "replayed_issue",
    "current_replaces_old", "reset_backlog", "missing_as_zero"])
def test_revision_independent_audit_rejects_double_counting_or_false_source_in_memory(fault):
    from etudecas.testing.independent_review import Evidence, audit_external_component_service
    data, series, events = revision_audit_example()
    if fault in ("future_known", "wrong_vintage"):
        note = json.loads(events[0]["notes"])
        note["known_day" if fault == "future_known" else "vintage_id"] = 11 if fault == "future_known" else "v11"
        events[0]["notes"] = json.dumps(note)
    elif fault == "replayed_issue": events.append(deepcopy(events[0]))
    elif fault == "current_replaces_old": series[11]["demand_qty"] = 100
    elif fault == "reset_backlog": series[12]["backlog_start_qty"] = 0
    elif fault == "missing_as_zero": series[5]["forecast_source_covered"] = 1
    evidence = Evidence()
    audit_external_component_service(series, events, [], data, 13, evidence)
    assert any(check["failed"] for check in evidence.checks.values())
