from __future__ import annotations

import csv
from pathlib import Path

import pytest

from etudecas.simulation.engine.control_schedule import (
    ACTION_FIELDS,
    CONTROL_BOUNDS,
    ControlCatalog,
    ControlScheduleError,
    load_control_schedule,
    serialize_control_ledger,
    write_control_ledger_csv,
)


def write_schedule(tmp_path: Path, content: str, *, encoding: str = "utf-8") -> Path:
    path = tmp_path / "control_schedule.csv"
    path.write_text(content, encoding=encoding)
    return path


def test_none_schedule_is_disabled_and_resolves_to_neutral_values() -> None:
    schedule = load_control_schedule(None)

    assert not schedule.enabled
    assert schedule.rows == ()
    assert schedule.warnings == ()
    resolved = schedule.resolve(0)
    assert not resolved.enabled
    assert resolved.requested == {
        name: spec.neutral
        for name, spec in CONTROL_BOUNDS.items()
    }
    assert resolved.effective == resolved.requested
    assert resolved.bound == {name: "none" for name in ACTION_FIELDS}
    assert resolved.source_lines == {name: None for name in ACTION_FIELDS}
    assert serialize_control_ledger(resolved) == []
    assert len(serialize_control_ledger(resolved, include_neutral=True)) == len(ACTION_FIELDS)


def test_global_and_targeted_rows_resolve_field_by_field(tmp_path: Path) -> None:
    path = write_schedule(
        tmp_path,
        "\n".join(
            [
                "day,policy,node_id,supplier_id,item_id,dst_node_id,"
                "order_multiplier,capacity_multiplier,expedite_level",
                "0,global,,,,,1.2,0.9,",
                "0,item_policy,,,item:A,,1.5,,0.2",
            ]
        ),
    )

    schedule = load_control_schedule(path)
    targeted = schedule.resolve(0, item_id="item:A")
    other = schedule.resolve(0, item_id="item:B")
    later = schedule.resolve(1, item_id="item:A")

    assert schedule.enabled
    assert len(schedule.rows) == 2
    assert schedule.rows[0].is_global
    assert schedule.rows[1].specificity == 1
    assert targeted.enabled
    assert targeted.order_multiplier == 1.5
    assert targeted.capacity_multiplier == 0.9
    assert targeted.expedite_level == 0.2
    assert targeted.source_lines["order_multiplier"] == 3
    assert targeted.source_lines["capacity_multiplier"] == 2
    assert targeted.policies == ("item_policy", "global")
    assert targeted.matched_source_lines == (2, 3)
    assert other.order_multiplier == 1.2
    assert other.expedite_level == 0.0
    assert not later.enabled
    assert later.order_multiplier == 1.0


def test_more_specific_row_overrides_a_compatible_less_specific_row(tmp_path: Path) -> None:
    path = write_schedule(
        tmp_path,
        "\n".join(
            [
                "day,policy,supplier_id,item_id,order_multiplier,priority_weight",
                "2,item,,item:A,1.1,2",
                "2,lane,S1,item:A,1.4,",
            ]
        ),
    )

    resolved = load_control_schedule(path).resolve(
        2,
        supplier_id="S1",
        item_id="item:A",
    )

    assert resolved.order_multiplier == 1.4
    assert resolved.priority_weight == 2.0
    assert resolved.source_lines["order_multiplier"] == 3
    assert resolved.source_lines["priority_weight"] == 2


def test_out_of_bounds_values_are_clamped_and_auditable(tmp_path: Path) -> None:
    path = write_schedule(
        tmp_path,
        "\n".join(
            [
                "day,policy,"
                + ",".join(ACTION_FIELDS),
                "0,stress,-1,99,-5,2,4,1.1,-31,11",
            ]
        ),
    )

    schedule = load_control_schedule(path)
    resolved = schedule.resolve(0)

    assert len(schedule.warnings) == len(ACTION_FIELDS)
    assert resolved.requested == {
        "order_multiplier": -1.0,
        "safety_stock_multiplier": 99.0,
        "production_target_multiplier": -5.0,
        "capacity_multiplier": 2.0,
        "external_procurement_multiplier": 4.0,
        "expedite_level": 1.1,
        "lead_time_adjustment_days": -31,
        "priority_weight": 11.0,
    }
    assert resolved.effective == {
        "order_multiplier": 0.0,
        "safety_stock_multiplier": 3.0,
        "production_target_multiplier": 0.0,
        "capacity_multiplier": 1.5,
        "external_procurement_multiplier": 3.0,
        "expedite_level": 1.0,
        "lead_time_adjustment_days": -30,
        "priority_weight": 10.0,
    }
    assert resolved.bound == {
        "order_multiplier": "lower",
        "safety_stock_multiplier": "upper",
        "production_target_multiplier": "lower",
        "capacity_multiplier": "upper",
        "external_procurement_multiplier": "upper",
        "expedite_level": "upper",
        "lead_time_adjustment_days": "lower",
        "priority_weight": "upper",
    }
    assert all(row["source_line"] == 2 for row in resolved.to_ledger_rows())
    assert all(row["policy"] == "stress" for row in resolved.to_ledger_rows())


def test_exact_boundaries_are_accepted_without_warning(tmp_path: Path) -> None:
    path = write_schedule(
        tmp_path,
        "\n".join(
            [
                "day,order_multiplier,lead_time_adjustment_days",
                "0,2,-30",
                "1,0,90",
            ]
        ),
    )

    schedule = load_control_schedule(path)

    assert schedule.warnings == ()
    assert schedule.resolve(0).bound["order_multiplier"] == "none"
    assert schedule.resolve(1).lead_time_adjustment_days == 90


@pytest.mark.parametrize(
    ("content", "message"),
    [
        ("", "empty and has no CSV header"),
        ("day,policy\n0,p", "control action column"),
        ("policy,order_multiplier\np,1", "requires a 'day'"),
        ("day,unknown,order_multiplier\n0,x,1", "unknown columns: unknown"),
        ("day,day,order_multiplier\n0,0,1", "duplicate columns: day"),
        ("day,,order_multiplier\n0,,1", "empty column name"),
        ("day,order_multiplier\n0,1,extra", "more values than CSV columns"),
        ("day,order_multiplier\n,1", "day is required"),
        ("day,order_multiplier\n-1,1", "zero-based non-negative integer"),
        ("day,order_multiplier\n1.5,1", "zero-based non-negative integer"),
        ("day,order_multiplier\n0,", "control action value is required"),
    ],
)
def test_invalid_csv_schema_or_row_is_rejected(
    tmp_path: Path,
    content: str,
    message: str,
) -> None:
    path = write_schedule(tmp_path, content)

    with pytest.raises(ControlScheduleError, match=message):
        load_control_schedule(path)


@pytest.mark.parametrize(
    ("content", "message"),
    [
        (
            (
                "day,supplier_id,production_target_multiplier\n"
                "0,S1,1.1\n"
            ),
            "production_target_multiplier supports node_id and item_id",
        ),
        (
            (
                "day,supplier_id,safety_stock_multiplier\n"
                "0,S1,1.1\n"
            ),
            "safety_stock_multiplier cannot use supplier_id",
        ),
    ],
)
def test_structurally_unresolvable_action_scopes_are_rejected(
    tmp_path: Path,
    content: str,
    message: str,
) -> None:
    path = write_schedule(tmp_path, content)

    with pytest.raises(ControlScheduleError, match=message):
        load_control_schedule(path)


def test_supplier_capacity_requires_supplier_id_with_catalog(
    tmp_path: Path,
) -> None:
    catalog = ControlCatalog(
        node_ids={"N1", "S1"},
        supplier_ids={"S1"},
    )
    invalid = write_schedule(
        tmp_path,
        "day,node_id,capacity_multiplier\n"
        "0,S1,0.5\n",
    )
    with pytest.raises(
        ControlScheduleError,
        match="use supplier_id so the supplier lane execution can resolve it",
    ):
        load_control_schedule(invalid, catalog=catalog)

    valid = write_schedule(
        tmp_path,
        "day,node_id,supplier_id,capacity_multiplier\n"
        "0,,,1.1\n"
        "1,,S1,0.5\n"
        "2,N1,,0.8\n",
    )
    schedule = load_control_schedule(valid, catalog=catalog)

    assert schedule.resolve(0).capacity_multiplier == 1.1
    assert schedule.resolve(
        1,
        node_id="N1",
        supplier_id="S1",
    ).capacity_multiplier == 0.5
    assert schedule.resolve(
        2,
        node_id="N1",
    ).capacity_multiplier == 0.8


@pytest.mark.parametrize("value", ["NaN", "nan", "Inf", "-inf", "not-a-number"])
def test_non_finite_or_non_numeric_action_is_rejected(
    tmp_path: Path,
    value: str,
) -> None:
    path = write_schedule(
        tmp_path,
        f"day,order_multiplier\n0,{value}\n",
    )

    with pytest.raises(ControlScheduleError, match="must be (finite|numeric)"):
        load_control_schedule(path)


@pytest.mark.parametrize("value", ["1.5", "1e1", "two"])
def test_lead_time_adjustment_requires_integer_measured_days(
    tmp_path: Path,
    value: str,
) -> None:
    path = write_schedule(
        tmp_path,
        f"day,lead_time_adjustment_days\n0,{value}\n",
    )

    with pytest.raises(ControlScheduleError, match="must be an integer"):
        load_control_schedule(path)


def test_duplicate_day_and_exact_scope_is_rejected(tmp_path: Path) -> None:
    path = write_schedule(
        tmp_path,
        "\n".join(
            [
                "day,item_id,order_multiplier",
                "0,item:A,1.1",
                "0,item:A,1.2",
            ]
        ),
    )

    with pytest.raises(ControlScheduleError, match="Duplicate control scope"):
        load_control_schedule(path)


def test_equal_specificity_overlapping_scopes_are_rejected_as_ambiguous(
    tmp_path: Path,
) -> None:
    path = write_schedule(
        tmp_path,
        "\n".join(
            [
                "day,node_id,item_id,order_multiplier",
                "0,N1,,1.1",
                "0,,item:A,1.2",
            ]
        ),
    )

    with pytest.raises(ControlScheduleError, match="Ambiguous control scopes"):
        load_control_schedule(path)


def test_equal_specificity_non_overlapping_scopes_are_allowed(tmp_path: Path) -> None:
    path = write_schedule(
        tmp_path,
        "\n".join(
            [
                "day,node_id,order_multiplier",
                "0,N1,1.1",
                "0,N2,1.2",
            ]
        ),
    )

    schedule = load_control_schedule(path)

    assert schedule.resolve(0, node_id="N1").order_multiplier == 1.1
    assert schedule.resolve(0, node_id="N2").order_multiplier == 1.2
    assert not schedule.resolve(0, node_id="N3").enabled


def test_optional_catalog_rejects_unknown_scope_and_policy(tmp_path: Path) -> None:
    path = write_schedule(
        tmp_path,
        "day,policy,node_id,supplier_id,item_id,dst_node_id,order_multiplier\n"
        "0,balanced,N1,S1,item:A,N2,1.1\n",
    )
    valid = ControlCatalog(
        node_ids={"N1", "N2"},
        supplier_ids={"S1"},
        item_ids={"item:A"},
        policies={"balanced"},
    )

    assert load_control_schedule(path, catalog=valid).enabled

    for catalog, unknown_name in [
        (ControlCatalog(node_ids={"N2"}), "node_id"),
        (ControlCatalog(supplier_ids=set()), "supplier_id"),
        (ControlCatalog(item_ids={"item:B"}), "item_id"),
        (ControlCatalog(node_ids={"N1"}), "dst_node_id"),
        (ControlCatalog(policies={"reference"}), "policy"),
    ]:
        with pytest.raises(ControlScheduleError, match=f"unknown {unknown_name}"):
            load_control_schedule(path, catalog=catalog)


def test_header_only_schedule_is_disabled_with_warning(tmp_path: Path) -> None:
    path = write_schedule(tmp_path, "day,order_multiplier\n")

    schedule = load_control_schedule(path)

    assert not schedule.enabled
    assert schedule.rows == ()
    assert schedule.warnings == (
        "Control schedule contains no action rows; controls are disabled.",
    )


def test_utf8_bom_and_surrounding_whitespace_are_supported(tmp_path: Path) -> None:
    path = write_schedule(
        tmp_path,
        " day , policy , item_id , order_multiplier \n"
        " 0 , balanced , item:A , 1.25 \n",
        encoding="utf-8-sig",
    )

    schedule = load_control_schedule(path)
    resolved = schedule.resolve(0, item_id=" item:A ")

    assert resolved.order_multiplier == 1.25
    assert resolved.policy == "balanced"


@pytest.mark.parametrize("day", [-1, True, 1.0, "1"])
def test_resolve_rejects_non_integer_or_negative_day(day: object) -> None:
    with pytest.raises(ControlScheduleError, match="zero-based non-negative integer"):
        load_control_schedule(None).resolve(day)  # type: ignore[arg-type]


def test_ledger_serialization_and_csv_writer_preserve_metadata(
    tmp_path: Path,
) -> None:
    path = write_schedule(
        tmp_path,
        "day,policy,item_id,order_multiplier\n0,balanced,item:A,9\n",
    )
    resolved = load_control_schedule(path).resolve(0, item_id="item:A")

    rows = resolved.to_ledger_rows(extra={"q_mrp": 12.0})
    serialized = serialize_control_ledger(resolved, status="applied")
    ledger_path = write_control_ledger_csv(
        tmp_path / "results" / "canonical_action_ledger.csv",
        resolved,
        status="applied",
    )

    assert len(rows) == 1
    assert rows[0]["action"] == "order_multiplier"
    assert rows[0]["requested"] == 9.0
    assert rows[0]["effective"] == 2.0
    assert rows[0]["bound"] == "upper"
    assert rows[0]["source_item_id"] == "item:A"
    assert rows[0]["q_mrp"] == 12.0
    assert serialized[0]["status"] == "applied"
    with ledger_path.open("r", encoding="utf-8", newline="") as stream:
        written = list(csv.DictReader(stream))
    assert written[0]["action"] == "order_multiplier"
    assert written[0]["requested"] == "9.0"
    assert written[0]["effective"] == "2.0"
    assert written[0]["bound"] == "upper"


def test_missing_path_and_directory_are_rejected(tmp_path: Path) -> None:
    with pytest.raises(ControlScheduleError, match="does not exist"):
        load_control_schedule(tmp_path / "missing.csv")
    with pytest.raises(ControlScheduleError, match="is not a file"):
        load_control_schedule(tmp_path)
