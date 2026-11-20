import pytest

from etudecas.simulation.engine.frozen_production import FrozenLotAuthorization, FrozenProductionBook
from etudecas.simulation.engine.mrp_planning import OrderProposal


PAIR = ("M-1430", "item:268967")
MATERIAL = ("M-1430", "item:344135")
TARGET = "FROZEN|M-1430|item:268967|1"
OTHER = "FROZEN|M-1430|item:268967|2"
QTY = 107_800


def frozen_orders(work_authorization=None):
    book = FrozenProductionBook({PAIR[0]: 56}, bom_by_pair={PAIR: [(MATERIAL, 1)]},
                                work_authorization=work_authorization)
    book.reconcile(PAIR, 0, (OrderProposal("planned-target", 96, 99, 99, QTY),
                             OrderProposal("planned-other", 97, 100, 100, QTY)))
    book.begin_day(41)
    return book


def test_work_authorization_preserves_mrp_until_the_due_day_and_defers_one_credit():
    book = frozen_orders(FrozenLotAuthorization.parse(f"{TARGET},103"))
    witness = frozen_orders()
    for day in (41, 42, 95):
        book.begin_day(day)
        witness.begin_day(day)
        assert book.orders == witness.orders
        assert book.events == witness.events
        assert book.planning_snapshot(day) == witness.planning_snapshot(day)

    for day in range(96, 103):
        book.begin_day(day)
        witness.begin_day(day)
        assert book.material_requirements(day) == witness.material_requirements(day)
        assert book.reserved_work(PAIR, day)[0] == (TARGET, 103, QTY)
        assert [(receipt.receipt_id, receipt.available_day, receipt.qty)
                for receipt in book.firm_receipts(PAIR, day) if receipt.receipt_id == TARGET] == [
                    (TARGET, 106, QTY)]
        assert book.orders[TARGET]["actual_release_day"] is None
        assert book.orders[TARGET]["executed_qty"] == 0
        book.due(PAIR, day)

    delays = [event for event in book.events if event["event"] == "physical_launch_delayed"]
    assert [(row["day"], row["block_reason"], row["estimated_available_day"]) for row in delays] == [
        (day, "atelier_authorization_not_before", 106) for day in range(96, 103)]
    assert book.orders[TARGET]["frozen_day"] == 41
    assert book.orders[TARGET]["planned_release_day"] == 96
    assert book.orders[TARGET]["planned_available_day"] == 99


def test_deferred_lot_does_not_block_another_due_order_and_cannot_bind_early():
    book = frozen_orders(FrozenLotAuthorization.parse(f"{TARGET},103"))
    assert book.due(PAIR, 96) is None
    with pytest.raises(ValueError, match="authorized date"):
        book.bind(TARGET, day=96, campaign_id="too-early")
    assert book.due(PAIR, 97)["order_id"] == OTHER
    book.bind(OTHER, day=97, campaign_id="other-campaign")
    book.execute(OTHER, day=97, qty=QTY)
    assert book.due(PAIR, 103)["order_id"] == TARGET
    book.bind(TARGET, day=103, campaign_id="target-campaign")
    book.execute(TARGET, day=103, qty=QTY)
    assert book.orders[TARGET]["actual_release_day"] == 103
    assert book.orders[TARGET]["state"] == "completed"
    assert book.firm_receipts(PAIR, 103) == ()


def test_work_authorization_requires_a_simulated_order_and_integer_day():
    for text in ("OTHER,103", f"{TARGET},-1", f"{TARGET},1.5", f"{TARGET},", f"{TARGET},1,2"):
        with pytest.raises(ValueError, match="ORDER_ID,DAY"):
            FrozenLotAuthorization.parse(text)
    assert FrozenLotAuthorization.parse(f"{TARGET},0").pair == PAIR
