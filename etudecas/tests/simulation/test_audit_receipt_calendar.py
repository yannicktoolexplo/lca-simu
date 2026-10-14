"""Independent date-audit cases; all evidence is in memory, no file fixtures."""
from copy import deepcopy
import json

from etudecas.testing.independent_review import (
    Evidence, audit_declared_receipt_dates, audit_opening_purchase_availability,
)


def example():
    # Friday18April2025 +2 working days, excluding EasterMonday21 =Wednesday23.
    rule = dict(node_id="plant", item_id="material", receipt_days=2)
    calendar = dict(schema_version=1, mode="explicit_site_nonworking_dates_v1",
                    sites=[dict(node_id="plant", nonworking_dates=["2025-04-21"])])
    meta = dict(receipt_calendar_policy=calendar, mrp_forecasts=dict(origin="2025-01-01"),
                production_release_policy=dict(rows=[rule]),
                supplier_delivery_receipt_policy=dict(rows=[rule]))
    policy = dict(dated_component_planning=dict(receipt_calendar_policy=deepcopy(calendar)))
    event = dict(node_id="plant", item_id="material", event_type="production_output",
                 lot_id="batch", day="107", notes=json.dumps(dict(physical_day=107, available_day=112)))
    order = dict(node_id="plant", item_id="material", order_type="external_procurement_supplier_delivery",
                 mrp_order_id="purchase", physical_delivery_day="107", available_day="112", receipt_source_days="2")
    return meta, policy, [event], [order]


def audit(values):
    evidence = Evidence()
    audit_declared_receipt_dates(*values, evidence)
    return {key for key, row in evidence.checks.items() if row["failed"]}


def test_holiday_recount_of_both_created_and_purchased_material():
    values = example()
    before = deepcopy(values)
    assert not audit(values)
    assert values == before


def test_early_production_release_is_not_accepted_from_its_own_notes():
    values = example()
    values[2][0]["notes"] = json.dumps(dict(physical_day=107, available_day=111))
    assert "receipt_calendar_production_exact_date" in audit(values)


def test_early_purchase_and_wrong_declared_duration_fail():
    values = example()
    values[3][0].update(available_day="111", receipt_source_days="1")
    assert audit(values) == {"receipt_calendar_order_exact_date", "receipt_calendar_order_source_duration"}


def test_opening_dates_are_not_recomputed_by_new_calendar():
    values = example()
    values[2][0].update(event_type="opening_production_order", notes="")
    values[3][0].update(order_type="opening_purchase_order", available_day="108")
    assert not audit(values)


def test_changed_export_calendar_fails_even_when_execution_dates_match():
    values = example()
    values[1]["dated_component_planning"]["receipt_calendar_policy"]["sites"][0]["nonworking_dates"] = []
    assert audit(values) == {"receipt_calendar_export_matches_input"}


def test_missing_export_does_not_disable_the_declared_input_contract():
    values = example()
    values[1]["dated_component_planning"] = {}
    assert audit(values) == {"receipt_calendar_export_matches_input"}


def test_boolean_schema_is_not_a_version_number():
    values = example()
    values[0]["receipt_calendar_policy"]["schema_version"] = True
    assert "receipt_calendar_declared_contract" in audit(values)


def test_missing_origin_and_duplicate_closed_dates_fail():
    values = example()
    values[0]["mrp_forecasts"] = {}
    assert audit(values) == {"receipt_calendar_origin_documented"}
    values = example()
    values[0]["receipt_calendar_policy"]["sites"][0]["nonworking_dates"] *= 2
    assert "receipt_calendar_explicit_unique_dates" in audit(values)


def test_zero_delay_keeps_closed_anchor_and_internal_transfer_uses_destination():
    values = example()
    rule = dict(node_id="plant", item_id="material", receipt_days=0)
    values[0]["internal_component_policy"] = dict(rows=[rule])
    values[3][0].update(order_type="lane_release", physical_delivery_day="110", available_day="110")
    assert not audit(values)


def test_unconfigured_historical_calculation_has_no_new_contract():
    values = example()
    values[0].pop("receipt_calendar_policy")
    assert not audit(values)


def fragment_example():
    """Manual oracle: 5+7 UN promised; 6 then4 received; 2 still unreceived.

    Jan6 Monday +2 JO =Jan8; Jan11 Saturday +2 JO =Jan14.
    Horizon ends Jan12: the last4 are physical/held but not available yet.
    A later input receipt exists Jan21, outside the horizon: it cannot execute.
    """
    identities = ['OPENING_DATED_PURCHASE|["Extract.xlsx","1"]',
                  'OPENING_DATED_PURCHASE|["Extract.xlsx","2"]']
    book = dict(source_file="Extract.xlsx", rows=[dict(source_row=i, order_type="purchase_open_order",
        dst_node_id="plant", src_node_id="supplier", item_id="material", quantity=q, uom="UN",
        physical_delivery_day=1, usable_day=5, receipt_release_days=2) for i, q in ((1, 5), (2, 7))])
    source_events = [dict(node_id="plant", item_id="material", known_day=d, quantity=q,
        uom="UN", source_file="Movements.xlsx", source_row=i, source_cell=f"Sheet!H{i}")
        for d, q, i in ((5, 6, 8), (10, 4, 9), (20, 2, 10))]
    meta = dict(mrp_forecasts=dict(origin="2025-01-01"), opening_open_orders=book,
        opening_receipt_execution_policy=dict(schema_version=1, mode="known_weekly_receipts_fifo_v1",
            calendar="monday_friday", pairs=[dict(node_id="plant", item_id="material")], events=source_events))
    orders = []
    for i, q, received, available, pending, held in ((1, 5, 5, 5, 0, 0), (2, 7, 5, 1, 2, 4)):
        identity = identities[i-1]
        orders.append(dict(node_id="plant", item_id="material", order_type="opening_purchase_order",
            mrp_order_id=identity, baseline_reference_id=identity, source_file="Extract.xlsx", source_row=str(i),
            physical_delivery_day="1", available_day="5", arrival_day="5", release_qty=str(q),
            planned_receipt_qty=str(q), opening_execution_mode="known_weekly_receipts_fifo_v1",
            opening_execution_received_qty=str(received), opening_execution_available_qty=str(available),
            opening_execution_pending_qty=str(pending), opening_execution_held_qty=str(held),
            actual_physical_receipt_day="5" if i == 1 else "", actual_available_day="7" if i == 1 else "",
            actual_receipt_day="7" if i == 1 else "",
            order_status_end_of_run="available" if i == 1 else "partially_received_opening_commitment"))
    fragments, events = [], []
    for ordinal, (i, qty, source_row, physical, available) in enumerate(((1, 5, 8, 5, 7), (2, 1, 8, 5, 7), (2, 4, 9, 10, 13))):
        identity = identities[i-1]
        source_id = json.dumps(["Movements.xlsx", source_row, f"Sheet!H{source_row}"], separators=(",", ":"))
        marker = "OPENING_EXECUTED_FRAGMENT|" + json.dumps([identity, source_id], separators=(",", ":"))
        fragments.append(dict(marker=marker, original_marker=identity, node_id="plant", item_id="material", uom="UN",
            quantity=str(qty), physical_delivery_day=str(physical), arrival_day=str(available), receipt_known_day=str(physical),
            receipt_release_days="2", original_source_file="Extract.xlsx", original_source_row=str(i),
            receipt_source_file="Movements.xlsx", receipt_source_row=str(source_row), receipt_source_cell=f"Sheet!H{source_row}",
            original_promised_physical_day="1", original_promised_available_day="5",
            allocation_basis="fifo_technical_not_observed_order_identity",
            availability_basis="original_receipt_workdays_after_known_physical_receipt"))
        for kind, due in (("opening_purchase_order_receipt", physical), ("stock_availability_hold", physical),
                          ("stock_availability_release", available)):
            if due >= 12:
                continue
            events.append(dict(event_id=f"E{ordinal}-{kind}", event_type=kind, day=str(due), node_id="plant",
                item_id="material", uom="UN", qty=str(qty), source_id=marker, lot_id=f"L{ordinal}",
                planned_order_id=identity, baseline_reference_id=identity, source_row=str(i), supplier_id="supplier"))
    summary = dict(mode="known_weekly_receipts_fifo_v1", pairs=[dict(node_id="plant", item_id="material")],
        original_order_count=2, known_receipt_fragment_count=3, pending_by_marker=dict(zip(identities, (0, 2))))
    return dict(orders=orders, events=events, horizon=12, meta=meta, fragments=fragments,
                execution_summary=summary, item_units={"material": "UN"})


def fragment_audit(values):
    evidence = Evidence()
    count = audit_opening_purchase_availability(**values, evidence=evidence)
    return count, {key for key, row in evidence.checks.items() if row["failed"]}


def test_fragments_reconcile_fifo_partial_receipts_and_held_horizon_in_memory():
    values = fragment_example()
    before = deepcopy(values)
    assert fragment_audit(values) == (2, set())
    assert values == before


def test_fragment_calendar_recount_rejects_coherent_but_early_release():
    values = fragment_example()
    values["fragments"][0]["arrival_day"] = "6"
    values["events"][2]["day"] = "6"
    values["orders"][0].update(actual_available_day="6", actual_receipt_day="6")
    failed = fragment_audit(values)[1]
    assert {"opening_execution_fragment_dates", "opening_execution_availability_date_pair_unit",
            "opening_execution_actual_available_day"} <= failed


def test_fragment_duplicate_and_original_receipt_cannot_both_count():
    values = fragment_example()
    values["fragments"].append(deepcopy(values["fragments"][0]))
    extra = deepcopy(values["events"][0])
    extra.update(source_id=values["orders"][0]["mrp_order_id"], event_id="old-promise-created-again")
    values["events"].append(extra)
    failed = fragment_audit(values)[1]
    assert {"opening_execution_unique_fragment", "opening_execution_no_overreceipt",
            "opening_execution_no_duplicate_original_receipt"} <= failed


def test_fragments_require_declared_policy_summary_and_complete_export():
    values = fragment_example()
    values["meta"].pop("opening_receipt_execution_policy")
    assert "opening_execution_no_undeclared_replay" in fragment_audit(values)[1]
    values = fragment_example()
    values["execution_summary"] = None
    assert "opening_execution_summary_present" in fragment_audit(values)[1]
    values = fragment_example()
    values["fragments"].pop()
    assert "opening_execution_complete_fragment_export" in fragment_audit(values)[1]


def test_fragment_source_and_quantity_are_not_proved_by_their_own_csv():
    values = fragment_example()
    values["fragments"][0]["receipt_source_cell"] = "Sheet!H999"
    assert "opening_execution_fragment_declared_identity" in fragment_audit(values)[1]
    values = fragment_example()
    values["fragments"][0]["quantity"] = "6"
    values["events"][0]["qty"] = "6"
    assert "opening_execution_fragment_fifo_quantity" in fragment_audit(values)[1]
    values = fragment_example()
    values["orders"][0]["planned_receipt_qty"] = "6"
    assert "opening_execution_original_planned_quantity" in fragment_audit(values)[1]


def test_fragment_integer_physical_units_and_original_provenance():
    values = fragment_example()
    values["fragments"][0]["quantity"] = "4.5"
    assert "opening_execution_fragment_declared_identity" in fragment_audit(values)[1]
    values = fragment_example()
    values["events"][0]["planned_order_id"] = values["orders"][1]["mrp_order_id"]
    assert "opening_execution_creation_original_genealogy" in fragment_audit(values)[1]
    values = fragment_example()
    values["orders"][0]["available_day"] = "7"
    assert "opening_execution_original_promises_preserved" in fragment_audit(values)[1]


def test_fragment_pending_and_partial_actual_fields_cannot_pretend_complete():
    values = fragment_example()
    values["orders"][1].update(opening_execution_pending_qty="0", actual_physical_receipt_day="10",
                               order_status_end_of_run="available")
    values["execution_summary"]["pending_by_marker"][values["orders"][1]["mrp_order_id"]] = 0
    failed = fragment_audit(values)[1]
    assert {"opening_execution_order_pending", "opening_execution_actual_physical_receipt_day",
            "opening_execution_final_status", "opening_execution_summary_pending"} <= failed


def test_fragment_mass_conversion_uses_original_book_units():
    values = fragment_example()
    values["item_units"]["material"] = "KG"
    for row in values["meta"]["opening_open_orders"]["rows"]:
        row["quantity"] *= 1000
        row["uom"] = "G"
    for row in (values["fragments"] + values["events"]
                + values["meta"]["opening_receipt_execution_policy"]["events"]):
        row["uom"] = "KG"
    assert fragment_audit(values) == (2, set())


def test_fragment_foreign_event_or_shared_physical_lot_is_rejected():
    values = fragment_example()
    values["events"][-1]["source_id"] = "OPENING_EXECUTED_FRAGMENT|foreign"
    assert "opening_execution_no_orphan_fragment_events" in fragment_audit(values)[1]
    values = fragment_example()
    for event in values["events"]:
        if event["lot_id"] == "L1":
            event["lot_id"] = "L0"
    assert "opening_execution_same_unique_lot" in fragment_audit(values)[1]


def test_legacy_opening_purchase_single_lot_contract_remains_strict():
    values = fragment_example()
    order = values["orders"][0]
    order.pop("opening_execution_mode")
    order.update(actual_physical_receipt_day="1", actual_available_day="5", actual_receipt_day="5")
    events = values["events"][:3]
    for event in events:
        event["source_id"] = order["mrp_order_id"]
        event["day"] = "5" if event["event_type"] == "stock_availability_release" else "1"
    evidence = Evidence()
    assert audit_opening_purchase_availability([order], events, 12, evidence) == 1
    assert not any(row["failed"] for row in evidence.checks.values())
    events.append(deepcopy(events[0]))
    evidence = Evidence()
    audit_opening_purchase_availability([order], events, 12, evidence)
    assert evidence.checks["opening_purchase_single_physical"]["failed"] == 1
