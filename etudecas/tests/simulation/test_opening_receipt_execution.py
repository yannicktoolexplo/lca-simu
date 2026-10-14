"""Memory-only counterexamples for the opening receipt execution boundary.

No filesystem fixtures, timestamp changes, deletion or integrity attack tests.
Expected dates and quantities below are manual independent oracles.
"""
from copy import deepcopy
from datetime import date

import pytest

from etudecas.simulation.engine.opening_receipt_execution import (
    MODE, OpeningReceiptExecutionLedger,
)


PAIR = {"node_id": "SDC-1450", "item_id": "item:021081"}


def opening(quantity=100, row=22, physical=6, available=20, workdays=10, **extra):
    return {**PAIR, "order_type": "opening_purchase_order",
            "source_file": "Extract_En_cours.xlsx", "source_row": row,
            "receipt_qty": quantity, "physical_delivery_day": physical,
            "arrival_day": available, "receipt_release_days": workdays,
            "src_node_id": "SUPPLIER", "edge_id": "purchase-lane", **extra}


def event(day=53, quantity=60, row=376, **extra):
    return {**PAIR, "known_day": day, "quantity": quantity, "uom": "KG",
            "source_file": "Flow_Data_Inventory_movements.xlsx",
            "source_row": row, "source_cell": f"Feuille1!H{row}", **extra}


def ledger(rows=None, events=None, unit="KG", pairs=None):
    return OpeningReceiptExecutionLedger.from_policy(
        {"schema_version": 1, "mode": MODE, "calendar": "monday_friday",
         "pairs": pairs or [PAIR], "events": [] if events is None else events},
        opening_rows=[opening()] if rows is None else rows,
        item_unit_map={"item:021081": unit}, origin_date=date(2025, 1, 1))


def test_receipt_is_not_executed_on_initial_promised_date():
    book = ledger(events=[event()])
    assert book.receive(6) == []  # Extract G, not an actual execution.
    assert book.receive(20) == []  # Extract I, still no source physical receipt.
    assert sum(book.pending_by_marker().values()) == 100
    assert book.receive(52) == []
    fragments = book.receive(53)
    assert sum(row["quantity"] for row in fragments) == 60
    assert sum(book.pending_by_marker().values()) == 40


def test_two_different_future_histories_have_identical_known_prefix():
    left = ledger(events=[event(53, 60), event(60, 10, 377)])
    right = ledger(events=[event(53, 60), event(160, 40, 377)])
    # The MRP-visible promises and all execution observations are identical
    # until either future event actually becomes known.
    for day in range(60):
        assert left.initial_rows_by_marker == right.initial_rows_by_marker
        assert left.pending_by_marker() == right.pending_by_marker()
        assert {m: left.pending_available_day(m, day) for m in left.managed_markers} == {
            m: right.pending_available_day(m, day) for m in right.managed_markers}
        assert left.receive(day) == right.receive(day)
    assert left.receive(60)[0]["quantity"] == 10
    assert right.receive(60) == []


def test_partial_receipts_preserve_original_source_and_unique_fragments():
    original = opening(100, row=22)
    book = ledger(rows=[original], events=[event(53, 60), event(60, 30, 377)])
    a = book.receive(53)[0]
    b = book.receive(60)[0]
    assert a["original_marker"] == b["original_marker"]
    assert a["marker"] != b["marker"]
    assert a["source_row"] == b["source_row"] == 22
    assert a["original_source_row"] == b["original_source_row"] == 22
    assert a["receipt_source_row"] == 376 and b["receipt_source_row"] == 377
    assert a["baseline_reference_id"] == b["baseline_reference_id"] == a["original_marker"]
    assert a["quantity"] + b["quantity"] + sum(book.pending_by_marker().values()) == 100
    assert original == opening(100, row=22)  # Caller input unchanged.


def test_one_receipt_splits_between_opening_orders_without_new_purchase():
    book = ledger(rows=[opening(40, row=23, physical=8), opening(100, row=22)],
                  events=[event(53, 125)])
    fragments = book.receive(53)
    assert [(r["source_row"], r["quantity"]) for r in fragments] == [(22, 100), (23, 25)]
    assert all(r["order_type"] == "opening_purchase_order" for r in fragments)
    assert sum(book.pending_by_marker().values()) == 15


def test_manual_workday_oracle_counts_from_physical_receipt_not_old_I():
    # Sunday 23 February + ten Mon-Fri days = Friday 7 March (day 65).
    book = ledger(events=[event(53, 60)])
    fragment = book.receive(53)[0]
    assert fragment["physical_delivery_day"] == 53
    assert fragment["arrival_day"] == fragment["available_day"] == 65
    assert fragment["original_promised_available_day"] == 20
    assert fragment["receipt_release_days"] == 10
    assert fragment["availability_basis"] == "original_receipt_workdays_after_known_physical_receipt"


def test_zero_processing_releases_on_known_physical_day():
    book = ledger(rows=[opening(workdays=0)], events=[event(53, 60)])
    assert book.receive(53)[0]["arrival_day"] == 53


def test_pending_planning_bound_keeps_unperformed_receipt_processing():
    book = ledger(rows=[opening(100, available=112, workdays=75)], events=[event()])
    marker = next(iter(book.managed_markers))
    # On 1 January, original 23 April promise is later than the technical
    # earliest release. On 22 February, earliest receipt is 23 February and
    # 75 Mon-Fri days require processing through Friday 6 June (day 156).
    assert book.pending_available_day(marker, 0) == 112
    assert book.pending_available_day(marker, 52) == 156
    assert sum(book.pending_by_marker().values()) == 100
    assert book.receive(52) == []


def test_real_quantity_totals_keep_360_kg_unreceived_commitment():
    # Quantities of the 23 Extract rows; simplified promise dates do not claim
    # order-level industrial allocation. H figures come from rows 376..393.
    quantities = [40000, 100000, 40000, 40000, 40000, 100000, 40000, 40000,
                  40000, 100000, 40000, 100000, 40000, 100000, 20000, 20000,
                  40000, 100000, 40000, 100000, 20000, 100000, 20000]
    receipts = [(53, 299856, 376), (60, 199904, 377), (67, 40000, 378),
                (88, 239904, 381), (123, 19976, 386), (137, 220000, 388),
                (144, 100000, 389), (158, 20000, 391), (172, 180000, 393)]
    book = ledger(rows=[opening(q, row=n + 22, physical=n, available=n + 14)
                        for n, q in enumerate(quantities)],
                  events=[event(d, q, r) for d, q, r in receipts])
    all_fragments = [f for d, _, _ in receipts for f in book.receive(d)]
    assert len(book.managed_markers) == 23
    assert sum(quantities) == 1320000
    assert sum(row["quantity"] for row in all_fragments) == 1319640
    assert sum(book.pending_by_marker().values()) == 360
    assert book.receive(1000) == []
    assert sum(book.pending_by_marker().values()) == 360


def test_repeated_day_does_not_duplicate_receipt_or_reduce_commitment_twice():
    book = ledger(events=[event()])
    assert len(book.receive(53)) == 1
    before = book.pending_by_marker()
    assert book.receive(53) == []
    assert book.pending_by_marker() == before


def test_overallocation_is_rejected_transactionally_and_never_uses_new_orders():
    rows = [opening(100), opening(500, row=99, order_type="external_procurement_supplier_delivery")]
    book = ledger(rows=rows, events=[event(53, 60), event(53, 60, 377)])
    before = book.pending_by_marker()
    with pytest.raises(ValueError, match="exceed"):
        book.receive(53)
    assert book.pending_by_marker() == before
    assert len(book.managed_markers) == 1


def test_scope_excludes_other_pairs_and_autonomous_orders():
    other = opening(900, row=98, node_id="M-1810")
    autonomous = opening(500, row=99, order_type="external_procurement_supplier_delivery")
    book = ledger(rows=[opening(), other, autonomous], events=[event()])
    assert len(book.managed_markers) == 1
    assert sum(book.pending_by_marker().values()) == 100
    assert sum(f["quantity"] for f in book.receive(53)) == 60


def test_physical_unit_quantities_must_be_integral():
    with pytest.raises(ValueError, match="integers"):
        ledger(rows=[opening(10.5)], unit="UN")
    with pytest.raises(ValueError, match="integers"):
        ledger(rows=[opening(10)], events=[event(quantity=1.5, uom="UN")], unit="UN")
    book = ledger(rows=[opening(10)], events=[event(quantity=7, uom="UN")], unit="UN")
    assert book.receive(53)[0]["quantity"] == 7
    assert sum(book.pending_by_marker().values()) == 3


def test_decimal_mass_conservation_has_no_rounding_remainder():
    book = ledger(rows=[opening(0.3)], events=[event(53, 0.1), event(60, 0.2, 377)])
    assert book.receive(53)[0]["quantity"] == 0.1
    assert book.receive(60)[0]["quantity"] == 0.2
    assert sum(book.pending_by_marker().values()) == 0


def test_duplicate_source_cell_and_unit_mismatch_are_rejected():
    with pytest.raises(ValueError, match="twice"):
        ledger(events=[event(), event()])
    with pytest.raises(ValueError, match="normalized"):
        ledger(events=[event(uom="G")])


def test_skipped_knowledge_date_or_backwards_time_is_rejected():
    book = ledger(events=[event()])
    with pytest.raises(ValueError, match="skipped"):
        book.receive(54)
    assert sum(book.pending_by_marker().values()) == 100
    book.receive(53)
    with pytest.raises(ValueError, match="backwards"):
        book.receive(52)


def test_initial_promise_access_cannot_mutate_internal_order_identity():
    book = ledger(events=[event()])
    visible = book.initial_rows_by_marker
    saved = deepcopy(visible)
    next(iter(visible.values()))["source_row"] = "changed by caller"
    assert book.initial_rows_by_marker == saved
    assert book.receive(53)[0]["source_row"] == 22
