"""Scan3 runtime provenance must equal the independent declared contract."""
import json

import pytest

from etudecas.simulation.reference_mrp.historical_adapter import (
    WeeklyTracker,
    f3_module,
    tracker_for,
)
from etudecas.testing.independent_review import Evidence, declared_scan3_requirements


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

    assert actual == expected
