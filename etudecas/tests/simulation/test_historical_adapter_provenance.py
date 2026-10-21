"""Scan3 runtime provenance must equal the independent declared contract."""
import json

import pytest

from etudecas.simulation.reference_mrp.historical_adapter import (
    WeeklyTracker,
    f3_module,
    tracker_for,
)
from etudecas.testing.independent_review import Evidence, declared_scan3_requirements
from etudecas.simulation.engine.mrp_planning import Requirement


PAIR = ("plant", "material")


def budget():
    return dict(
        node_id=PAIR[0],
        item_id=PAIR[1],
        source_row=1,
        budget_id="plant:material:R1",
        first_day=5,
        end_day_exclusive=12,
        closing_day=11,
        covered_days=7,
        covered_scan3_qty=100,
        full_week_scan3_qty=100,
        raw_signed_scan3_qty=-100,
        uom="KG",
        source_file="source.xlsx",
        scan3_source_cell="J1",
        source_week_marker="2025-01-05",
        partial_week=False,
        include_in_main_source_balance=True,
        coverage_status="documented_withdrawals",
    )


@pytest.mark.parametrize("cumulative", [False, True], ids=["weekly", "cumulative"])
def test_scan3_runtime_basis_exactly_matches_independent_oracle(cumulative):
    source = budget()
    cumulative_pairs = [list(PAIR)] if cumulative else []
    contract = dict(schema_version=1, mode="scan3_residual_v1",
                    cumulative_pairs=cumulative_pairs)
    event = dict(day=6, node_id=PAIR[0], item_id=PAIR[1],
                 event_type="production_consume", qty=25, uom="KG")

    evidence = Evidence()
    declared = declared_scan3_requirements(
        contract, [source], [event], 40, "scn:BASE", evidence
    )
    assert all(check["failed"] == 0 for check in evidence.checks.values())
    expected = next(iter(declared.values()))["reconciliation_basis"]

    if cumulative:
        tracker = tracker_for(f3_module(), [source], cumulative_pairs=[PAIR])
    else:
        tracker = WeeklyTracker([source])
    tracker.own_withdrawal(day=6, node_id=PAIR[0], item_id=PAIR[1], qty=25,
                           event_type="production_consume")
    tracker.close(11, {})
    actual = json.loads(next(iter(tracker.provenance.values()))["estimation_basis"])

    # The independent legacy oracle still carries the former, unproven scope
    # label.  Keep its numerical oracle while enforcing the confirmed meaning
    # of J/Scan3 in the runtime provenance.
    if not cumulative:
        expected.pop("actual_alternate_SKU_scope")
        expected["scan3_scope"] = "confirmed_reference_scope"
    assert actual == expected


@pytest.mark.parametrize("cumulative", [False, True], ids=["weekly", "configured-cumulative"])
def test_scan3_audit_only_records_signed_gap_without_publishing_requirement(cumulative):
    source = dict(budget(), uom="UN")
    cumulative_pairs = [PAIR] if cumulative else []
    tracker = tracker_for(f3_module(), [source], cumulative_pairs=cumulative_pairs,
                          mode="audit_only")
    tracker.own_withdrawal(day=6, node_id=PAIR[0], item_id=PAIR[1], qty=20,
                           event_type="production_consume")
    base = Requirement("external:source-I", 11, 7)

    result = tracker.close(11, {PAIR: (base,)})

    assert result == {PAIR: (base,)}
    audit = tracker.published[source["budget_id"]]
    assert audit["scan3_reconciliation_mode"] == "audit_only"
    assert audit["scan3_target_qty"] == 100
    assert audit["own_physical_qty"] == 20
    assert audit["scan3_minus_own_qty"] == 80
    assert audit["residual_requested_qty"] == 0
    assert audit["residual_backlog_final_qty"] == 0
    assert audit["requirement_id"] == ""
    assert tracker.by_requirement == {}
    assert tracker.provenance == {}


def test_scan3_audit_only_refuses_fractional_physical_units():
    source = dict(budget(), uom="UN")
    tracker = WeeklyTracker([source], mode="audit_only")
    tracker.own_withdrawal(day=6, node_id=PAIR[0], item_id=PAIR[1], qty=20.5,
                           event_type="production_consume")

    with pytest.raises(ArithmeticError, match="must remain integer"):
        tracker.close(11, {})


def test_scan3_audit_only_refuses_legacy_five_year_profile():
    from etudecas.simulation.current_reference import FIRST, validate_scan3_mode

    validate_scan3_mode("audit_only", FIRST)
    validate_scan3_mode("legacy_residual", FIRST + 1)
    with pytest.raises(ValueError, match="prospective profile still contains legacy Scan3 residuals"):
        validate_scan3_mode("audit_only", FIRST + 1)
