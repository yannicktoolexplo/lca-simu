"""In-memory observation oracles; no source alterations or native simulation."""
from copy import deepcopy
from dataclasses import dataclass
import json
import sys
from unittest.mock import patch

import pytest

from etudecas.simulation.analysis.production_programme_journal import (
    AUTHORIZATION_BASIS, BASIS, JOURNAL_FIELDS, JOURNAL_FILENAME, ProductionProgrammeJournal,
)


@dataclass(frozen=True)
class Proposal:
    release_day: int
    qty: float


def journal(origin="2025-01-06"):
    return ProductionProgrammeJournal(scenario_id="scn:BASE", origin_date=origin)


def observe(book, day, proposals=(), end=14):
    return book.observe(decision_day=day, node_id="F", output_item_id="item:PF",
                        uom="UN", proposals=proposals, coverage_end_day_exclusive=end)


def launch(book, day=1, qty=10, identity="campaign-a"):
    return book.record_launch(campaign_id=identity, node_id="F", output_item_id="item:PF",
                              uom="UN", day=day, qty=qty)


def vector(row):
    return json.loads(row["launch_quantities_json"])


def test_fixed_contract_has_no_ordinal_proposal_identity():
    assert JOURNAL_FILENAME == "production_programme_snapshots.csv"
    assert BASIS == "simulated_weekly_launch_programme_v1"
    rows = observe(journal(), 0, [Proposal(3, 10)])
    assert set(rows[0]) == set(JOURNAL_FIELDS)
    assert rows[0]["programme_id"] == 'PPROG|["scn:BASE","F","item:PF",0]'


def test_executing_a_planned_launch_keeps_total_target_and_deduplicates_commitment():
    book = journal()
    before = observe(book, 0, [Proposal(1, 10)])[0]
    assert launch(book) is True and launch(book) is False
    after = observe(book, 1)[0]
    assert vector(before) == vector(after)
    assert json.loads(after["committed_quantities_json"])["1"] == 10
    assert json.loads(after["proposed_quantities_json"])["1"] == 0
    assert after["version"] == before["version"] + 1


def test_date_only_change_preserves_identity_but_changes_dated_vector():
    book = journal()
    old = observe(book, 0, [Proposal(3, 10)])[0]
    new = observe(book, 1, [Proposal(4, 10)])[0]
    assert old["programme_id"] == new["programme_id"]
    assert sum(vector(old).values()) == sum(vector(new).values()) == 10
    assert vector(old)["3"] == 10 and vector(new)["4"] == 10
    assert vector(old) != vector(new)


def test_quantity_change_and_cancellation_are_published_as_target_vectors():
    book = journal()
    a = observe(book, 0, [Proposal(4, 10)])[0]
    b = observe(book, 1, [Proposal(4, 15)])[0]
    c = observe(book, 2)[0]
    assert [vector(row)["4"] for row in (a, b, c)] == [10, 15, 0]
    assert len({row["programme_id"] for row in (a, b, c)}) == 1


def test_empty_but_covered_programmes_are_published_without_filling_outside_coverage():
    rows = observe(journal(), 0, end=10)
    assert [(r["coverage_start_day"], r["coverage_end_day_exclusive"]) for r in rows] == [(0, 7), (7, 10)]
    assert vector(rows[1]) == {"7": 0, "8": 0, "9": 0}
    assert "10" not in vector(rows[1])


def test_calendar_weeks_are_absolute_mondays_with_partial_origin_week():
    rows = observe(journal("2025-01-01"), 0, end=8)
    assert [r["week_start_day"] for r in rows] == [-2, 5]
    assert list(vector(rows[0])) == ["0", "1", "2", "3", "4"]
    assert rows[0]["known_day"] == rows[0]["decision_day"] == 0


def test_overdue_recommendation_preserves_raw_date_without_mutating_input():
    book = journal()
    proposals = [Proposal(0, 10), Proposal(-2, 5), Proposal(4, 2)]
    original = deepcopy(proposals)
    row = observe(book, 2, proposals)[0]
    assert proposals == original
    assert vector(row)["0"] == 10 and vector(row)["4"] == 2
    assert vector(row)["3"] == 0


def test_constant_overdue_recommendation_is_not_translated_by_the_observer():
    book = journal()
    proposals = [Proposal(0, 100)]
    before = observe(book, 0, proposals)[0]
    after = observe(book, 1, proposals)[0]
    assert vector(before) == vector(after)
    assert vector(after)["0"] == 100 and vector(after)["1"] == 0


def test_multiple_proposals_same_day_are_aggregated_without_mutation():
    proposals = (Proposal(4, 3), Proposal(4, 7))
    assert vector(observe(journal(), 0, proposals)[0])["4"] == 10
    assert proposals == (Proposal(4, 3), Proposal(4, 7))


def test_unchanged_observations_still_receive_new_publication_versions():
    book = journal()
    a, b = observe(book, 0, [Proposal(4, 10)])[0], observe(book, 1, [Proposal(4, 10)])[0]
    assert vector(a) == vector(b)
    assert (a["version"], b["version"]) == (1, 2)


def test_closed_week_is_not_republished_and_commitments_do_not_leak_into_next_week():
    book = journal()
    launch(book, 1)
    old = observe(book, 1)[0]
    new = observe(book, 7)[0]
    assert old["week_start_day"] == 0 and new["week_start_day"] == 7
    assert old["programme_id"] != new["programme_id"] and sum(vector(new).values()) == 0
    assert launch(book, 1) is False


def test_conflicting_campaign_identity_and_out_of_order_versions_are_rejected():
    book = journal()
    launch(book)
    with pytest.raises(ValueError, match="conflicting"):
        launch(book, qty=9)
    observe(book, 1)
    with pytest.raises(ValueError, match="one ordered"):
        observe(book, 1)


def test_future_physical_launch_and_unit_change_are_not_accepted_as_known_observations():
    book = journal()
    launch(book, 5)
    with pytest.raises(ValueError, match="future campaign commitment"):
        observe(book, 1)
    other = journal()
    observe(other, 0)
    with pytest.raises(ValueError, match="unit"):
        other.observe(decision_day=1, node_id="F", output_item_id="item:PF", uom="KG",
                      proposals=(), coverage_end_day_exclusive=14)


def test_summary_reports_pair_coverage_without_inventing_a_replanning_rate():
    book = journal()
    observe(book, 0)
    summary = book.summary(expected_pairs=[("F", "item:PF"), ("G", "item:PF")])
    assert summary["complete_scope"] is False and summary["published_snapshot_count"] == 2
    assert summary["observed_pairs"] == [{"node_id": "F", "output_item_id": "item:PF"}]
    assert "production_replanning_rate" not in summary


def test_parser_observer_is_enabled_by_default_and_can_be_disabled_for_physical_comparison():
    from etudecas.simulation.engine import run_first_simulation as engine
    with patch.object(sys, "argv", ["simulation"]):
        assert engine.parse_args().production_programme_revision_journal is True
    with patch.object(sys, "argv", ["simulation", "--no-production-programme-revision-journal"]):
        assert engine.parse_args().production_programme_revision_journal is False


def test_legacy_authorization_has_a_distinct_basis_without_claiming_physical_work():
    book = ProductionProgrammeJournal(scenario_id="scn:BASE", origin_date="2025-01-06",
                                      commitment_policy=None)
    before = observe(book, 0, [Proposal(1, 10)])[0]
    # Manual oracle: authorization transfers the whole same-date target from
    # revocable to committed. Physical production can still be zero.
    assert launch(book, day=1, qty=10) is True
    after = observe(book, 1)[0]
    assert vector(before) == vector(after)
    assert json.loads(after["committed_quantities_json"])["1"] == 10
    assert after["basis"] == AUTHORIZATION_BASIS != BASIS
    summary = book.summary(expected_pairs=[("F", "item:PF")])
    assert summary["commitment_policy"] == "campaign_creation_authorization"
    assert "before physical work" in summary["launch_credit"]
    assert "no consumption" in summary["launch_credit"]


def test_first_physical_work_observation_retains_its_original_basis():
    book = journal()
    assert observe(book, 0)[0]["basis"] == BASIS
    assert book.summary(expected_pairs=[("F", "item:PF")])["commitment_policy"] == "first_physical_execution_v1"


def test_unknown_commitment_observation_convention_is_rejected():
    with pytest.raises(ValueError, match="convention"):
        ProductionProgrammeJournal(scenario_id="scn:BASE", origin_date="2025-01-06",
                                    commitment_policy="invented")
