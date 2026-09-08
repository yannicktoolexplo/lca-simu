from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from etudecas.prototypes.scan_2027_risk_control import (
    supplier_post_top3_action_protocol as protocol,
)


@pytest.fixture(scope="module")
def real_scope():
    scope_csv = protocol.DEFAULT_SCOPE_AUDIT / "supplier_lane_scope.csv"
    reference_csv = protocol.DEFAULT_NETWORK_PLAN / "active_lane_reference.csv"
    if not scope_csv.exists() or not reference_csv.exists() or not protocol.DEFAULT_GRAPH.exists():
        pytest.skip("Les artefacts réseau locaux ne sont pas disponibles.")
    scope_rows = protocol._read_csv(scope_csv)
    active = protocol.active_scope_rows(scope_rows)
    graph = protocol._read_json(protocol.DEFAULT_GRAPH)
    states = protocol.inventory_state_index(graph)
    references = protocol._read_csv(reference_csv)
    return scope_rows, active, states, references


def test_real_protocol_covers_18_lanes_and_16_suppliers(real_scope):
    scope_rows, active, states, _references = real_scope
    catalog = protocol.build_action_catalog(
        active_lanes=active,
        all_scope_rows=scope_rows,
        inventory_states=states,
    )
    assert len(active) == 18
    assert len({row["supplier_id"] for row in active}) == 16
    assert len(catalog) == 18 * 12
    assert {row["failure_mode"] for row in catalog} == set(protocol.FAILURE_MODES)
    assert all(row["baseline_positive_flow"] for row in catalog)


def test_current_scope_refuses_targeted_closed_loop_without_lane_observation(real_scope):
    scope_rows, active, states, _references = real_scope
    catalog = protocol.build_action_catalog(
        active_lanes=active,
        all_scope_rows=scope_rows,
        inventory_states=states,
        lane_signal_available=False,
        detection_delay_days=1,
        decision_delay_days=1,
    )
    closed_loop = [
        row
        for row in catalog
        if row["action_id"] == "targeted_transport_after_observed_delay"
    ]
    assert len(closed_loop) == 18
    assert all(
        row["eligibility_status"] == "non_simulable_avec_les_donnees_actuelles"
        for row in closed_loop
    )
    assert all(row["future_realisation_access"] is False for row in closed_loop)
    assert all(row["detection_delay_days"] == 1 for row in closed_loop)
    assert all(row["decision_delay_days"] == 1 for row in closed_loop)
    assert all(row["earliest_effective_lag_days"] == 2 for row in closed_loop)


def test_quality_hold_never_accepts_transport_after_receipt(real_scope):
    scope_rows, active, states, _references = real_scope
    catalog = protocol.build_action_catalog(
        active_lanes=active,
        all_scope_rows=scope_rows,
        inventory_states=states,
        lane_signal_available=True,
        explicit_lot_available=True,
    )
    magic = [
        row for row in catalog if row["action_id"] == "post_receipt_transport_expedite"
    ]
    assert len(magic) == 18
    assert all(not row["simulation_execution_allowed"] for row in magic)
    assert {row["refusal_reason"] for row in magic} == {
        "levier_inadapte_a_la_cause"
    }


def test_quality_transport_is_only_eligible_after_observed_release_and_lot_signal(
    real_scope,
):
    scope_rows, active, states, _references = real_scope
    blocked = protocol.build_action_catalog(
        active_lanes=active,
        all_scope_rows=scope_rows,
        inventory_states=states,
        lane_signal_available=False,
        explicit_lot_available=False,
    )
    blocked_rows = [
        row
        for row in blocked
        if row["action_id"] == "post_release_transport_for_identified_lot"
    ]
    assert len(blocked_rows) == 18
    assert all(not row["simulation_execution_allowed"] for row in blocked_rows)
    assert all(
        row["refusal_reason"]
        == "aucun_lot_identifie_avec_liberation_observee_et_transport_restant"
        for row in blocked_rows
    )

    eligible = protocol.build_action_catalog(
        active_lanes=active,
        all_scope_rows=scope_rows,
        inventory_states=states,
        lane_signal_available=True,
        explicit_lot_available=True,
    )
    eligible_rows = [
        row
        for row in eligible
        if row["action_id"] == "post_release_transport_for_identified_lot"
    ]
    assert len(eligible_rows) == 18
    assert all(row["simulation_execution_allowed"] for row in eligible_rows)


def test_no_active_alternative_is_not_treated_as_a_new_supplier(real_scope):
    scope_rows, active, states, _references = real_scope
    catalog = protocol.build_action_catalog(
        active_lanes=active,
        all_scope_rows=scope_rows,
        inventory_states=states,
        lane_signal_available=True,
    )
    source_rows = [
        row
        for row in catalog
        if row["action_id"]
        in {
            "prepared_qualified_alternative_source",
            "closed_loop_allocation_to_prepared_source",
        }
    ]
    assert len(source_rows) == 18 * 2 * 2
    assert all(not row["simulation_execution_allowed"] for row in source_rows)
    # Three active lanes have structural alternatives in V8, but none has a
    # second dynamically active reference lane.  A graph edge alone is not a
    # new-supplier action.
    structurally_multisource = {
        row["lane_key"] for row in source_rows if row["structural_alternative_count"] > 0
    }
    assert len(structurally_multisource) == 3
    assert all(
        row["active_alternative_count"] == 0
        for row in source_rows
        if row["lane_key"] in structurally_multisource
    )


def test_preventive_buffer_is_native_and_has_a_physical_grid(real_scope):
    scope_rows, active, states, references = real_scope
    catalog = protocol.build_action_catalog(
        active_lanes=active,
        all_scope_rows=scope_rows,
        inventory_states=states,
    )
    buffers = [row for row in catalog if row["action_id"] == "prepositioned_free_stock"]
    assert len(buffers) == 18 * 4
    assert all(row["timing_class"] == "preventif" for row in buffers)
    assert all(row["prepared_before_incident_required"] for row in buffers)
    assert sum(row["simulation_execution_allowed"] for row in buffers) == 17 * 4
    zero_stock_buffers = [
        row for row in buffers if float(row["initial_free_stock_qty"]) <= 0
    ]
    assert len(zero_stock_buffers) == 4
    assert {row["item_id"] for row in zero_stock_buffers} == {"item:344135"}
    grid = protocol.build_buffer_grid(
        active_lanes=active,
        active_reference_rows=references,
        inventory_states=states,
    )
    assert len(grid) == 18 * 3
    assert {row["buffer_cover_days"] for row in grid} == {7, 14, 28}
    assert all(row["additional_free_stock_qty"] > 0 for row in grid)
    scalable = [row for row in grid if row["measurement_start_stock_scale"] != ""]
    assert len(scalable) == 17 * 3
    assert all(float(row["measurement_start_stock_scale"]) > 1 for row in scalable)
    assert all(row["not_a_recommendation"] for row in grid)


def test_any_action_on_a_no_flow_lane_is_automatically_refused():
    lane = {
        "supplier_id": "SUP-A",
        "item_id": "item:X",
        "dst_node_id": "M-X",
        "baseline_positive_flow": False,
        "baseline_shipped_qty": 0,
    }
    catalog = protocol.build_action_catalog(
        active_lanes=[lane],
        all_scope_rows=[lane],
        inventory_states={("M-X", "item:X"): {"initial": 10, "uom": "KG"}},
        lane_signal_available=True,
        explicit_lot_available=True,
    )
    assert len(catalog) == 12
    assert all(not row["simulation_execution_allowed"] for row in catalog)
    assert {row["refusal_reason"] for row in catalog} == {
        "aucun_flux_positif_dans_la_reference_v10"
    }


def _write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_csv(path: Path, rows: list[dict]) -> None:
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def test_top3_selection_refuses_unstable_result(tmp_path: Path):
    _write_json(
        tmp_path / "campaign_manifest.json",
        {
            "status": "complete",
            "mode": "full",
            "final_top3_conclusion_status": "conclusion_top3_refusee",
        },
    )
    suppliers, decision = protocol.select_confirmed_top3(tmp_path)
    assert suppliers == []
    assert decision["selection_status"] == "selection_refused_v2_not_stabilized"


def test_top3_selection_rejects_legacy_ten_realisation_fields(tmp_path: Path):
    _write_json(
        tmp_path / "campaign_manifest.json",
        {
            "status": "complete",
            "mode": "full",
            "final_top3_conclusion_status": "top3_final_confirme",
        },
    )
    _write_csv(
        tmp_path / "supplier_sensitivity_ranking.csv",
        [
            {
                "supplier_id": f"SUP-{rank}",
                "final_top3_rank": rank,
                "stable_confirmed_top3": True,
                "evidence_stage": "confirmation_10_realisations",
            }
            for rank in (1, 2, 3)
        ],
    )
    suppliers, decision = protocol.select_confirmed_top3(tmp_path)
    assert suppliers == []
    assert decision["selection_status"] == "selection_refused_v2_not_stabilized"


def test_top3_selection_accepts_only_consolidated_v2_gates(tmp_path: Path):
    _write_json(
        tmp_path / "campaign_manifest.json",
        {
            "status": "complete",
            "mode": "full",
            "confirmation_seed_count": 30,
            "rank3_rank4_interval_separated": True,
            "scientific_release_gates": {
                "baseline_both_products_on_due_at_least_95_all_seeds_pass": True,
                "all_metric_rows_valid_pass": True,
                "j0_state_hash_pairing_100pct_pass": True,
                "input_graph_hash_pairing_100pct_pass": True,
                "active_window_pulled_and_shipped_at_least_29_of_30_all_lanes_pass": True,
                "all_release_gates_pass": True,
            },
            "extensions_required": {
                "multi_lane_supplier_common_cause": {"pass": True, "complete": True},
                "temporal_robustness": {"pass": True, "complete": True},
                "four_business_cause_confirmation": {"pass": True, "complete": True},
                "causal_lot_attribution": {"pass": True, "complete": True},
            },
        },
    )
    _write_csv(
        tmp_path / "supplier_sensitivity_ranking.csv",
        [
            {"supplier_id": f"SUP-{rank}", "supplier_sensitivity_rank": rank}
            for rank in range(1, 5)
        ],
    )
    _write_csv(
        tmp_path / "confirmed_top3_stability.csv",
        [
            {
                "supplier_id": f"SUP-{rank}",
                "aggregate_confirmation_rank": rank,
                "top3_presence_seed_count": 29,
                "confirmation_seed_count": 30,
            }
            for rank in range(1, 4)
        ],
    )
    suppliers, decision = protocol.select_confirmed_top3(tmp_path)
    assert suppliers == ["SUP-1", "SUP-2", "SUP-3"]
    assert decision["selection_status"] == "stabilized_v2_top3_selected"
