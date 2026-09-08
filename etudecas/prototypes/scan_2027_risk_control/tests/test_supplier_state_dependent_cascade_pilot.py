from __future__ import annotations

import importlib.util
from pathlib import Path
import sys


MODULE_PATH = (
    Path(__file__).resolve().parents[1]
    / "supplier_state_dependent_cascade_pilot.py"
)
SPEC = importlib.util.spec_from_file_location("supplier_state_dependent_cascade_pilot", MODULE_PATH)
assert SPEC and SPEC.loader
pilot = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = pilot
SPEC.loader.exec_module(pilot)


def test_pair_commands_differ_only_by_causal_input(tmp_path: Path) -> None:
    reference = [
        "old-python",
        "engine.py",
        "--input",
        "graph.json",
        "--output-dir",
        "old-output",
        "--days",
        "720",
        "--seed",
        "1",
        "--no-supplier-state-dependent-risks",
        "--supplier-risk-events-csv",
        "old-risk.csv",
        "--lot-trace",
    ]
    state_only = pilot.PairCase("state_only", "A", None, True)
    incident_csv = tmp_path / "risk.csv"
    state_plus_delay = pilot.PairCase("state_plus_delay", "B", incident_csv, True)
    common = {
        "days": 600,
        "seed": 340281,
        "families": pilot.DEFAULT_FAMILIES,
    }
    command_a = pilot.build_case_command(
        reference,
        case=state_only,
        output_dir=tmp_path / "a",
        **common,
    )
    command_b = pilot.build_case_command(
        reference,
        case=state_plus_delay,
        output_dir=tmp_path / "b",
        **common,
    )
    assert "--supplier-state-dependent-risks" in command_a
    assert "--no-supplier-state-dependent-risks" not in command_a
    assert "--supplier-state-risk-families" in command_a
    assert pilot.FORBIDDEN_FAMILY not in command_a
    assert "--supplier-risk-events-csv" not in command_a
    assert command_b[-2:] == ["--supplier-risk-events-csv", str(incident_csv.resolve())]


def test_engine_override_changes_only_script_path(tmp_path: Path) -> None:
    reference = ["old-python", "original-engine.py", "--input", "graph.json"]
    case = pilot.PairCase("state_only", "A", None, True)
    common = {
        "case": case,
        "output_dir": tmp_path / "out",
        "days": 600,
        "seed": 340281,
        "families": pilot.DEFAULT_FAMILIES,
    }
    original = pilot.build_case_command(reference, **common)
    copied_engine = tmp_path / "copied-engine.py"
    overridden = pilot.build_case_command(
        reference,
        engine_path=copied_engine,
        **common,
    )
    assert overridden[1] == str(copied_engine.resolve())
    assert original[:1] + original[2:] == overridden[:1] + overridden[2:]


def test_service_metric_excludes_backlog_catchup() -> None:
    rows = [
        {
            "day": "0",
            "node_id": pilot.TARGET_CUSTOMER,
            "item_id": pilot.TARGET_PRODUCT,
            "demand_qty": "100",
            "required_with_backlog_qty": "100",
            "served_qty": "50",
            "backlog_end_qty": "50",
        },
        {
            "day": "1",
            "node_id": pilot.TARGET_CUSTOMER,
            "item_id": pilot.TARGET_PRODUCT,
            "demand_qty": "100",
            "required_with_backlog_qty": "150",
            "served_qty": "150",
            "backlog_end_qty": "0",
        },
    ]
    result = pilot.service_metrics(rows, days=2)
    assert result["demand_qty"] == 200
    assert result["on_due_qty"] == 150
    assert result["on_due_service"] == 0.75


def test_first_divergence_respects_incident_boundary() -> None:
    left = {0: 10.0, 1: 10.0, 2: 9.0, 3: 8.0}
    right = {0: 11.0, 1: 10.0, 2: 9.0, 3: 7.0}
    assert pilot.first_divergence_day(left, right, start_day=1) == 3


def test_output_lot_exposure_walks_back_to_risky_transport() -> None:
    rows = [
        {
            "day": "240",
            "link_type": "transport",
            "parent_lot_id": "supplier-lot",
            "child_lot_id": "factory-input-lot",
            "child_node_id": pilot.TARGET_FACTORY,
            "child_item_id": pilot.TARGET_COMPONENT,
            "risk_event_ids": "primary-event,state-event",
            "child_qty": "1000",
        },
        {
            "day": "241",
            "link_type": "production",
            "parent_lot_id": "factory-input-lot",
            "child_lot_id": "finished-lot",
            "child_node_id": pilot.TARGET_FACTORY,
            "child_item_id": pilot.TARGET_PRODUCT,
            "risk_event_ids": "",
            "child_qty": "100",
        },
    ]
    result = pilot.output_lot_exposure(
        rows,
        primary_event_id="primary-event",
        incremental_state_event_ids={"state-event"},
    )
    assert len(result) == 1
    assert result[0]["finished_product_lot_id"] == "finished-lot"
    assert result[0]["primary_delay_in_ancestry"] is True
    assert result[0]["incremental_state_events_in_ancestry"] == "state-event"


def test_state_rows_reject_excluded_or_unlisted_family() -> None:
    pilot.audit_state_rows(
        [{"risk_family": "lead", "event_id": "state_lead", "risk_type": "lead_time"}],
        pilot.DEFAULT_FAMILIES,
    )
    try:
        pilot.audit_state_rows(
            [{"risk_family": pilot.FORBIDDEN_FAMILY, "event_id": "state_forbidden"}],
            pilot.DEFAULT_FAMILIES,
        )
    except ValueError:
        pass
    else:
        raise AssertionError("Excluded state branch was not rejected")


def test_offline_html_embeds_curves_without_remote_dependency() -> None:
    summary = {
        "incident_window": {"start_day": 228, "end_day": 407},
        "measured_days": 600,
        "seed": 340281,
        "pair_results": {
            "service_loss_points_state_off": 3.0,
            "service_loss_points_state_on": 4.2,
            "service_loss_amplification_points": 1.2,
            "service_268091_change_points": -4.2,
            "state_event_count_change": 3,
            "new_target_chain_state_signal_count": 4,
            "new_target_chain_state_signal_group_count": 2,
            "first_new_target_chain_state_signal_day": 330,
            "finished_product_lots_with_primary_or_incremental_signal_ancestry": 8,
            "primary_event_last_arrival_day": 500,
            "days_observed_after_last_primary_arrival": 99,
        },
    }
    metrics = [
        {
            "case": "state_off_nominal",
            "service_268091_pct": 99.0,
            "primary_event_shipment_count": 0,
            "primary_event_pulled_qty": 0,
        },
        {
            "case": "delay_only_state_off",
            "service_268091_pct": 96.0,
            "primary_event_shipment_count": 2,
            "primary_event_pulled_qty": 5000,
        },
        {
            "case": "state_only",
            "service_268091_pct": 99.0,
            "primary_event_shipment_count": 0,
            "primary_event_pulled_qty": 0,
        },
        {
            "case": "state_plus_delay",
            "service_268091_pct": 94.8,
            "primary_event_shipment_count": 2,
            "primary_event_pulled_qty": 5000,
        },
    ]
    curves = [
        {
            "case": key,
            "day": 0,
            "component_stock_338929_M1810": 10,
            "production_released_268091": 20,
            "backlog_end_268091": 0,
        }
        for key in ("state_only", "state_plus_delay")
    ]
    document = pilot.build_offline_html(
        summary=summary,
        metric_rows=metrics,
        curve_rows=curves,
        event_rows=[],
        lot_rows=[],
    )
    assert "Cascade dynamique" in document
    assert "https://" not in document
    assert "http://" not in document
    assert 'id="payload"' in document
    assert pilot.FORBIDDEN_FAMILY not in document.casefold()
