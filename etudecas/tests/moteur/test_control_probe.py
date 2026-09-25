from __future__ import annotations

from pathlib import Path

import pytest

from etudecas.simulation.engine.control_probe import (
    CONTROL_PROBE_ACTIONS,
    CONTROL_PROBE_MODE,
    ControlProbeError,
    ProbeResolvedControl,
    compose_feedback_with_probe,
    load_control_probe_schedule,
)
from etudecas.simulation.engine.control_schedule import load_control_schedule


def _write_csv(path: Path, header: str, row: str) -> Path:
    path.write_text(f"{header}\n{row}\n", encoding="utf-8")
    return path


def test_probe_composes_additively_after_non_neutral_feedback(
    tmp_path: Path,
) -> None:
    feedback = load_control_schedule(
        _write_csv(
            tmp_path / "feedback.csv",
            "day,policy,order_multiplier,safety_stock_multiplier",
            "0,v3_supplier_relief,0.98,1.02",
        )
    ).resolve(0)
    probe = load_control_probe_schedule(
        _write_csv(
            tmp_path / "probe.csv",
            "day,policy,order_multiplier,safety_stock_multiplier",
            "0,frequency_probe,1.005,0.995",
        )
    ).resolve(0)

    composed = compose_feedback_with_probe(feedback, probe)

    assert isinstance(composed, ProbeResolvedControl)
    assert composed.order_multiplier == pytest.approx(0.985)
    assert composed.safety_stock_multiplier == pytest.approx(1.015)
    assert composed.production_target_multiplier == pytest.approx(1.0)
    rows = {row["action"]: row for row in composed.composition_rows()}
    assert rows["order_multiplier"]["feedback_effective"] == pytest.approx(
        0.98
    )
    assert rows["order_multiplier"]["probe_delta"] == pytest.approx(0.005)
    assert rows["order_multiplier"]["composed_effective"] == pytest.approx(
        0.985
    )
    assert rows["order_multiplier"]["composition_mode"] == CONTROL_PROBE_MODE
    assert rows["order_multiplier"]["composition_clipped"] == 0


def test_neutral_probe_preserves_feedback_value_and_unmatched_scope_identity(
    tmp_path: Path,
) -> None:
    feedback = load_control_schedule(
        _write_csv(
            tmp_path / "feedback.csv",
            "day,policy,node_id,item_id,order_multiplier",
            "0,v3,M-1430,item:268967,0.98",
        )
    ).resolve(0, node_id="M-1430", item_id="item:268967")
    schedule = load_control_probe_schedule(
        _write_csv(
            tmp_path / "probe.csv",
            "day,policy,node_id,item_id,order_multiplier",
            "0,frequency_probe,M-1430,item:268967,1.0",
        )
    )

    neutral = compose_feedback_with_probe(
        feedback,
        schedule.resolve(0, node_id="M-1430", item_id="item:268967"),
    )
    assert isinstance(neutral, ProbeResolvedControl)
    assert neutral.order_multiplier == pytest.approx(0.98)
    assert neutral.composition_rows()[0]["probe_delta"] == pytest.approx(0.0)

    unrelated_feedback = load_control_schedule(None).resolve(
        0,
        node_id="M-1810",
        item_id="item:268091",
    )
    unchanged = compose_feedback_with_probe(
        unrelated_feedback,
        schedule.resolve(0, node_id="M-1810", item_id="item:268091"),
    )
    assert unchanged is unrelated_feedback


def test_composition_clips_only_after_feedback_and_probe_are_added(
    tmp_path: Path,
) -> None:
    feedback = load_control_schedule(
        _write_csv(
            tmp_path / "feedback.csv",
            "day,policy,order_multiplier,production_target_multiplier",
            "0,v3,1.98,0.01",
        )
    ).resolve(0)
    probe = load_control_probe_schedule(
        _write_csv(
            tmp_path / "probe.csv",
            "day,policy,order_multiplier,production_target_multiplier",
            "0,frequency_probe,1.05,0.95",
        )
    ).resolve(0)

    composed = compose_feedback_with_probe(feedback, probe)

    assert isinstance(composed, ProbeResolvedControl)
    assert composed.order_multiplier == pytest.approx(2.0)
    assert composed.production_target_multiplier == pytest.approx(0.0)
    rows = {row["action"]: row for row in composed.composition_rows()}
    assert rows["order_multiplier"]["composed_unbounded"] == pytest.approx(
        2.03
    )
    assert rows["order_multiplier"]["composition_bound"] == "upper"
    assert rows["production_target_multiplier"]["composition_bound"] == (
        "lower"
    )
    assert all(row["composition_clipped"] == 1 for row in rows.values())


def test_probe_loader_rejects_unsupported_non_neutral_or_clamped_actions(
    tmp_path: Path,
) -> None:
    unsupported = _write_csv(
        tmp_path / "unsupported.csv",
        "day,policy,order_multiplier,capacity_multiplier",
        "0,frequency_probe,1.01,1.1",
    )
    with pytest.raises(
        ControlProbeError,
        match="unsupported non-neutral probe actions: capacity_multiplier",
    ):
        load_control_probe_schedule(unsupported)

    clamped = _write_csv(
        tmp_path / "clamped.csv",
        "day,policy,order_multiplier",
        "0,frequency_probe,3.0",
    )
    with pytest.raises(ControlProbeError, match="cannot rely on control-bound"):
        load_control_probe_schedule(clamped)


def test_probe_loader_discards_neutral_unsupported_fields(tmp_path: Path) -> None:
    schedule = load_control_probe_schedule(
        _write_csv(
            tmp_path / "neutral_unsupported.csv",
            "day,policy,order_multiplier,capacity_multiplier,expedite_level",
            "0,frequency_probe,1.01,1.0,0.0",
        )
    )
    assert set(schedule.rows[0].effective) == {"order_multiplier"}
    assert set(CONTROL_PROBE_ACTIONS) == {
        "order_multiplier",
        "safety_stock_multiplier",
        "production_target_multiplier",
    }
