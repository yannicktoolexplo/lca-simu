"""Memory-only bounds, firm-receipt balances and causal V3 compatibility oracles."""
from copy import deepcopy
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from etudecas.simulation.engine import run_first_simulation as engine
from etudecas.simulation.engine.control_provider import (
    CanonicalObservation, ControlProviderError, StateFeedbackControlProvider,
)
from etudecas.simulation.engine.control_provider_v2 import StateFeedbackControlProviderV2
from etudecas.simulation.engine.control_provider_v3 import StateFeedbackControlProviderV3


CONFIG = (Path(__file__).resolve().parents[2] / "prototypes/scan_2027_risk_control/config"
          / "canonical_closed_loop_v3_continuous_config.json")
PAIR = ("C-MEMORY", "item:finished")


def _payload():
    return json.loads(CONFIG.read_text(encoding="utf-8"))


def _provider(payload=None, kind=StateFeedbackControlProviderV3):
    value = deepcopy(_payload() if payload is None else payload)
    if kind is StateFeedbackControlProviderV2:
        value["schema_version"] = "scan.canonical_state_feedback.v2"
    elif kind is StateFeedbackControlProvider:
        value["schema_version"] = "scan.canonical_state_feedback.v1"
    return kind(value, config_path=CONFIG, config_sha256="in-memory-policy")


def _resolve(provider=None, **changes):
    route = dict(src="DC-MEMORY", dst=PAIR[0], item_id=PAIR[1], order_frequency_days=1, standard_order_qty=0)
    kwargs = dict(nodes=[dict(id="DC-MEMORY", type="distribution_center"),
                         dict(id=PAIR[0], type="customer")],
                  demand_pairs={PAIR}, lanes_by_dest_item={PAIR: [route]}, dated_planning=True,
                  controls=provider is not None, control_provider=provider)
    kwargs.update(changes)
    return engine.resolve_customer_physical_cover("physical_demand_cover_v1", **kwargs)


def test_current_relief_only_policy_is_qualified_without_changing_nominal_cover():
    provider = _provider()
    assert provider.supports_physical_customer_cover()
    assert provider.summary_metadata()["physical_customer_cover_relief_only_capability"] is True
    assert set(_resolve(provider)) == {PAIR}
    assert _resolve() == _resolve(provider)
    # Qualification does not observe state, create decisions or apply actions.
    assert provider.commands == () and provider.decision_rows == ()


@pytest.mark.parametrize("action,value", [
    ("order_multiplier", 1.01), ("order_multiplier", 0), ("order_multiplier", True),
    ("safety_stock_multiplier", 1.1), ("production_target_multiplier", 1.1),
    ("capacity_multiplier", 1.1), ("external_procurement_multiplier", 1.1),
    ("expedite_level", .1), ("lead_time_adjustment_days", -1),
    ("priority_weight", .9), ("expedite_level", -1),
])
def test_unsafe_requested_or_effective_playbook_cannot_qualify(action, value):
    payload = _payload()
    payload["playbooks"]["supplier_relief"]["commands"][0]["actions"][action] = value
    provider = _provider(payload)
    assert not provider.supports_physical_customer_cover()
    with pytest.raises(ValueError, match="no warmup or controls"):
        _resolve(provider)


def test_all_playbooks_and_continuous_bounds_are_qualified_not_only_current_regime():
    payload = _payload()
    payload["playbooks"]["unused_aggressive"] = {
        "commands": [{"scope": {}, "actions": {"order_multiplier": 1.2}}]}
    assert not _provider(payload).supports_physical_customer_cover()
    provider = _provider()
    provider._continuous_spec["minimum_order_multiplier"] = 0.0
    assert not provider.supports_physical_customer_cover()
    provider = _provider()
    provider._continuous_spec["production_relief_gain"] = float("nan")
    assert not provider.supports_physical_customer_cover()


@pytest.mark.parametrize("kind", [StateFeedbackControlProvider, StateFeedbackControlProviderV2])
def test_generic_v1_v2_and_probe_are_still_refused(kind):
    with pytest.raises(ValueError, match="no warmup or controls"):
        _resolve(_provider(kind=kind))
    with pytest.raises(ValueError, match="no warmup or controls"):
        _resolve(_provider(), control_probe=True)
    fake = SimpleNamespace(enabled=True, mode=StateFeedbackControlProviderV3.mode,
                           supports_physical_customer_cover=lambda: True)
    with pytest.raises(ValueError, match="no warmup or controls"):
        _resolve(fake)
    with pytest.raises(ValueError, match="no warmup or controls"):
        _resolve(controls=True)


@pytest.mark.parametrize("changes", [
    {"dated_planning": False}, {"stochastic_leads": True}, {"warmup_days": 1},
    {"demand_perturbation": True}, {"review_days": 7},
])
def test_qualified_v3_does_not_relax_existing_timing_guards(changes):
    with pytest.raises(ValueError, match="no warmup or controls"):
        _resolve(_provider(), **changes)


@pytest.mark.parametrize("multiplier,first_dispatch,second_dispatch,ending_backlog", [
    (1.0, 6, 0, 0), (.5, 3, 1, 2),
])
def test_two_receipt_days_close_manual_balance_without_rebuying_firm_quantity(
        multiplier, first_dispatch, second_dispatch, ending_backlog):
    # Ten known units, no stock, four already committed for J2: only six need ordering.
    original = engine.FirmReceipt("original", 2, 4, "in_transit")
    initial = engine.customer_known_demand_need(decision_day=0, arrival_day=1,
        available_qty=0, backlog_qty=10, firm_receipts=[original], uom="UN")
    assert initial["customer_physical_order_qty"] == 6
    engine.validate_customer_cover_relief_order_multiplier(multiplier)
    dispatched = engine.cap_known_customer_dispatch(6 * multiplier, known_need=6, uom="UN")
    assert dispatched == first_dispatch
    # J1: receive and serve that dispatch; the original four remain in transit.
    backlog_j1 = 10 - dispatched
    next_need = engine.customer_known_demand_need(decision_day=1, arrival_day=2,
        available_qty=0, backlog_qty=backlog_j1, firm_receipts=[original], uom="UN")
    assert next_need["customer_physical_order_qty"] == (0 if multiplier == 1 else 3)
    next_dispatch = engine.cap_known_customer_dispatch(
        next_need["customer_physical_order_qty"] * multiplier,
        known_need=next_need["customer_physical_order_qty"], uom="UN")
    assert next_dispatch == second_dispatch
    # J2: the original four arrive once, along with the second dispatch.
    served_total = dispatched + 4 + next_dispatch
    assert 10 - served_total == ending_backlog
    assert all(q % 1 == 0 for q in (dispatched, next_dispatch, served_total, ending_backlog))
    with pytest.raises(ValueError, match="unique"):
        engine.customer_known_demand_need(decision_day=0, arrival_day=1,
            available_qty=0, backlog_qty=10, firm_receipts=[original, original], uom="UN")


@pytest.mark.parametrize("value", [0, -1, 1.000001, float("inf"), float("nan"), True])
def test_customer_runtime_multiplier_cannot_escape_qualified_interval(value):
    with pytest.raises(ValueError, match="relief-only"):
        engine.validate_customer_cover_relief_order_multiplier(value)


def test_qualified_v3_still_applies_observed_state_on_next_day_only():
    payload = _payload()
    # A short supervisory test isolates the causal lag; production config is unchanged.
    payload.update(review_period_days=1, confirmation_days=1, minimum_dwell_days=0)
    payload["dynamics"].update(stress_memory=0, nervousness_gain=0, pressure_gain=0, disruption_gain=1)
    provider = _provider(payload)
    assert provider.supports_physical_customer_cover()
    observation = CanonicalObservation(day=0, demand_qty=100, served_qty=100,
        service_level=1, backlog_qty=0, backlog_days=0, inventory_qty=1000,
        finished_inventory_cover_days=12, material_cover_days=10,
        production_utilization=.5, supplier_utilization=.5, order_nervousness=0,
        active_order_pair_count=1, supplier_disruption_score=1, active_supplier_event_count=1)
    commands = provider.observe(observation, last_effective_day=1)
    assert provider.resolve(0).order_multiplier == 1
    assert commands and all(c.decision_day == 0 and c.effective_day == 1 for c in commands)
    assert 0 < provider.resolve(1).order_multiplier < 1
