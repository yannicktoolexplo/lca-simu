"""Hand-computable regression cases for the September audit corrections."""
from collections import defaultdict

import pytest

from etudecas.simulation.engine.run_first_simulation import (
    LotLedger, physical_execution_quantity, seed_lane_pipeline_uniform, scale_physical_allocations,
)
from etudecas.simulation.analysis_batch_common import apply_scales
from etudecas.simulation.source_fingerprint import implementation_fingerprint
from etudecas.testing.qualification import qualify, require_run_invariants
from etudecas.testing.test_independent_review import known_run, write_csv  # noqa: F401


def test_fractional_forecast_accumulates_without_losing_demand():
    ledger = LotLedger(enabled=True)
    ledger.create_lot(day=0, node_id="C", item_id="P", qty=10, uom="UN", source_type="opening_stock")
    stock, backlog, services = 10, 0, []
    for day in range(4):
        required = backlog + 0.5
        served = physical_execution_quantity(min(stock, required), "UN")
        ledger.consume(day=day, node_id="C", item_id="P", qty=served, uom="UN", event_type="demand_service")
        stock -= served
        backlog = required - served
        services.append(served)
    assert services == [0, 1, 0, 1]
    assert backlog == 0 and stock == 8
    assert sum(lot["qty_remaining"] for lot in ledger.lots.values()) == 8


def test_uniform_transit_preserves_ten_whole_units_across_three_days():
    pipeline, transit = defaultdict(list), defaultdict(float)
    seed_lane_pipeline_uniform(pipeline, transit, dst="D", item_id="P", qty=10,
                               edge_id="E", lead_days=3, uom="UN")
    assert [pipeline[day][0][2] for day in range(3)] == [3, 3, 4]
    assert transit[("D", "P")] == 10


def test_physical_execution_retains_mass_precision():
    assert physical_execution_quantity(0.125, "KG") == 0.125
    assert physical_execution_quantity(2.9, "UN") == 2
    with pytest.raises(ValueError):
        physical_execution_quantity(float("nan"), "UN")


def test_scaled_transit_parents_conserve_whole_total():
    parents = [{"lot_id": "a", "qty": 3}, {"lot_id": "b", "qty": 7}]
    actual = scale_physical_allocations(parents, 0.75, "UN")
    assert [p["qty"] for p in actual] == [2, 5]
    assert sum(p["qty"] for p in actual) == physical_execution_quantity(10 * .75, "UN")


@pytest.mark.parametrize("factors", [{"typo": 0.5}, {"capacity_scale": float("nan")}, {"capacity_scale": "0.5"}])
def test_invalid_sensitivity_cannot_be_recorded_as_applied(factors):
    with pytest.raises(ValueError):
        apply_scales({"scenarios": [{"id": "base"}]}, "base", factors)


def test_sibling_runtime_change_invalidates_cache(tmp_path):
    engine = tmp_path / "etudecas/simulation/engine/main.py"
    sibling = tmp_path / "etudecas/simulation/lot_policy/rule.py"
    engine.parent.mkdir(parents=True)
    sibling.parent.mkdir(parents=True)
    engine.write_text("from etudecas.simulation.lot_policy.rule import RATE")
    sibling.write_text("RATE = 1")
    before = implementation_fingerprint(engine)
    sibling.write_text("RATE = 2")
    assert implementation_fingerprint(engine) != before


def test_delivery_gate_refuses_corrupt_stock_and_missing_evidence(known_run):
    assert require_run_invariants(known_run)["ok"]
    write_csv(known_run, "production_output_products_daily", [dict(day=0, node_id="F", item_id="FG", stock_end_of_day=10, released_qty=0)])
    with pytest.raises(ValueError, match="Delivery refused"):
        require_run_invariants(known_run)
    report = qualify([known_run], known_run / "review")
    assert not report["ok"] and not report["display_verified"]
    (known_run / "data/production_lot_events.csv").unlink()
    assert not qualify([known_run], known_run / "review")["ok"]
