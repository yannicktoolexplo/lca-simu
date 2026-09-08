from __future__ import annotations

import math

import pytest

from etudecas.prototypes.scan_2027_risk_control import (
    supplier_service_regime_calibration_protocol as protocol,
)


def _screening_rows(
    *,
    service_by_family_and_index: dict[tuple[str, int], float] | None = None,
    product_268967_override: dict[tuple[str, int], float] | None = None,
) -> list[dict[str, object]]:
    service_by_family_and_index = service_by_family_and_index or {}
    product_268967_override = product_268967_override or {}
    rows: list[dict[str, object]] = []
    for candidate in protocol.build_candidates():
        service = service_by_family_and_index.get(
            (candidate.family, candidate.severity_index),
            max(0.0, 1.0 - 0.025 * candidate.severity_index),
        )
        rows.append(
            {
                "scenario_id": candidate.scenario_id,
                "valid": True,
                "system_on_due_service": service,
                "on_due_service_268091": service,
                "on_due_service_268967": product_268967_override.get(
                    (candidate.family, candidate.severity_index), service
                ),
            }
        )
    return rows


def test_candidate_design_has_five_isolated_families_and_36_points() -> None:
    candidates = protocol.build_candidates()

    assert len(candidates) == 36
    assert {candidate.family for candidate in candidates} == {
        family.key for family in protocol.FAMILIES
    }
    assert all(candidate.family in protocol.FAMILY_BY_KEY for candidate in candidates)
    assert all(candidate.value > 0 for candidate in candidates)
    assert len({candidate.scenario_id for candidate in candidates}) == len(candidates)
    assert all(
        protocol.FAMILY_BY_KEY[candidate.family].changed_parameter
        for candidate in candidates
    )


def test_supplier_capacity_scope_is_only_the_two_identified_pairs() -> None:
    rows, changes = protocol._supplier_floor_rows(0.4)

    assert len(rows) == 2
    assert {
        (row["supplier_id"], row["item_id"], row["dst_node_id"])
        for row in rows
    } == set(protocol.IDENTIFIED_CAPACITY_PAIRS)
    assert {float(row["tested_capacity_floor_qty_per_day"]) for row in rows} == {
        30_000.0,
        120_000.0,
    }
    assert all(change["scale"] == 0.4 for change in changes)


def test_factory_capacity_excludes_unbounded_intermediate_process() -> None:
    rows, changes = protocol._factory_capacity_rows(0.7)

    assert len(rows) == 2
    assert {(row["node_id"], row["output_item_id"]) for row in rows} == set(
        protocol.MODELED_FINISHED_FACTORY_PROCESSES
    )
    assert all(row["output_item_id"] != "item:773474" for row in rows)
    assert all(change["scale"] == 0.7 for change in changes)


def test_service_metric_excludes_backlog_catchup() -> None:
    rows: list[dict[str, object]] = []
    for product in protocol.PRODUCTS:
        rows.extend(
            [
                {
                    "day": 0,
                    "node_id": protocol.CLIENT_NODE_ID,
                    "item_id": f"item:{product}",
                    "demand_qty": 100,
                    "required_with_backlog_qty": 100,
                    "served_qty": 0,
                    "backlog_end_qty": 100,
                },
                {
                    "day": 1,
                    "node_id": protocol.CLIENT_NODE_ID,
                    "item_id": f"item:{product}",
                    "demand_qty": 100,
                    "required_with_backlog_qty": 200,
                    "served_qty": 200,
                    "backlog_end_qty": 0,
                },
            ]
        )

    metrics = protocol.service_from_daily_rows(rows, days=2)

    assert metrics["on_due_service_268091"] == pytest.approx(0.5)
    assert metrics["on_due_service_268967"] == pytest.approx(0.5)
    assert metrics["system_on_due_service"] == pytest.approx(0.5)
    assert metrics["minimum_product_on_due_service"] == pytest.approx(0.5)


def test_target_selection_uses_point_or_adjacent_bracket_without_interpolation() -> None:
    family = protocol.FAMILIES[0].key
    rows = _screening_rows(
        service_by_family_and_index={
            (family, 1): 0.98,
            (family, 2): 0.93,
            (family, 3): 0.86,
            (family, 4): 0.82,
            (family, 5): 0.78,
            (family, 6): 0.70,
            (family, 7): 0.60,
            (family, 8): 0.40,
        }
    )

    selection = protocol.select_target_candidates(rows)
    records = {
        (row["family"], row["target_service"]): row
        for row in selection["target_records"]
    }
    target_93 = records[(family, 0.93)]
    target_80 = records[(family, 0.80)]

    assert target_93["selection_method"] == "discrete_point_within_tolerance"
    assert len(target_93["selected_scenario_ids"]) == 1
    assert target_80["selection_method"] == (
        "adjacent_discrete_bracket_no_interpolation"
    )
    assert len(target_80["selected_scenario_ids"]) == 2
    assert target_80["interpolation_claim_allowed"] is False
    assert selection["selected_scenario_count"] <= 20


def test_product_balance_guard_rejects_misleading_global_target() -> None:
    family = protocol.FAMILIES[0].key
    rows = _screening_rows(
        service_by_family_and_index={(family, 2): 0.93},
        product_268967_override={(family, 2): 0.70},
    )

    selection = protocol.select_target_candidates(rows)
    record = next(
        row
        for row in selection["target_records"]
        if row["family"] == family and math.isclose(row["target_service"], 0.93)
    )

    assert record["nearest_scenario_id"].endswith("__0p6")
    assert record["nearest_balanced"] is False
    assert record["selection_method"] != "discrete_point_within_tolerance"


def test_preliminary_seed_block_is_reused_when_extending_to_30() -> None:
    selected = ["scenario_a", "scenario_b"]
    preliminary = protocol.missing_confirmation_jobs(
        selected,
        requested_seeds=protocol.PRELIMINARY_CONFIRMATION_SEEDS,
    )
    final_increment = protocol.missing_confirmation_jobs(
        selected,
        requested_seeds=protocol.FINAL_CONFIRMATION_SEEDS,
        existing_keys=preliminary,
    )

    assert len(preliminary) == 30
    assert len(final_increment) == 30
    assert {seed for _, seed in final_increment} == set(
        protocol.FINAL_CONFIRMATION_SEEDS[15:]
    )
    assert not (set(preliminary) & set(final_increment))


def test_selection_rejects_incomplete_or_invalid_screening() -> None:
    rows = _screening_rows()
    rows.pop()
    with pytest.raises(ValueError, match="Screening scope mismatch"):
        protocol.select_target_candidates(rows)

    rows = _screening_rows()
    rows[0]["valid"] = False
    with pytest.raises(ValueError, match="screening row is invalid"):
        protocol.select_target_candidates(rows)
