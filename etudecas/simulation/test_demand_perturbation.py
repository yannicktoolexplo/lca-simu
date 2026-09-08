from __future__ import annotations

from pathlib import Path

import pytest

from etudecas.simulation.engine.demand_perturbation import (
    DemandPerturbationError,
    load_demand_perturbation_schedule,
)


DEMAND_PAIRS = {("customer:A", "item:FG"), ("customer:B", "item:FG")}


def _write_csv(tmp_path: Path, body: str) -> Path:
    path = tmp_path / "demand_perturbations.csv"
    path.write_text(body, encoding="utf-8")
    return path


def test_absent_schedule_is_disabled_and_physically_neutral() -> None:
    schedule = load_demand_perturbation_schedule(
        None,
        demand_pairs=DEMAND_PAIRS,
        measured_days=3,
    )

    baseline = {("customer:A", "item:FG"): 100.0}
    assert schedule.enabled is False
    assert schedule.rows == ()
    assert schedule.apply(0, baseline) == baseline


def test_exact_pair_schedule_applies_only_on_configured_measured_day(
    tmp_path: Path,
) -> None:
    path = _write_csv(
        tmp_path,
        "day,node_id,item_id,demand_multiplier\n"
        "0,customer:A,item:FG,1.1\n"
        "2,customer:B,item:FG,0.75\n",
    )
    schedule = load_demand_perturbation_schedule(
        path,
        demand_pairs=DEMAND_PAIRS,
        measured_days=3,
    )
    baseline = {
        ("customer:A", "item:FG"): 100.0,
        ("customer:B", "item:FG"): 80.0,
    }

    assert schedule.enabled is True
    assert schedule.apply(0, baseline) == {
        ("customer:A", "item:FG"): pytest.approx(110.0),
        ("customer:B", "item:FG"): 80.0,
    }
    assert schedule.apply(1, baseline) == baseline
    assert schedule.apply(2, baseline) == {
        ("customer:A", "item:FG"): 100.0,
        ("customer:B", "item:FG"): pytest.approx(60.0),
    }


@pytest.mark.parametrize(
    ("row", "message"),
    [
        ("0,customer:A,item:FG,nan", "must be finite"),
        ("0,customer:A,item:FG,1.5001", r"outside \[0.5, 1.5\]"),
        ("3,customer:A,item:FG,1.1", "outside this run's horizon"),
        ("0,customer:UNKNOWN,item:FG,1.1", "unknown demand pair"),
    ],
)
def test_schedule_rejects_unsafe_or_unreachable_rows(
    tmp_path: Path,
    row: str,
    message: str,
) -> None:
    path = _write_csv(
        tmp_path,
        "day,node_id,item_id,demand_multiplier\n" + row + "\n",
    )

    with pytest.raises(DemandPerturbationError, match=message):
        load_demand_perturbation_schedule(
            path,
            demand_pairs=DEMAND_PAIRS,
            measured_days=3,
        )


def test_schedule_rejects_duplicate_pair_day(tmp_path: Path) -> None:
    path = _write_csv(
        tmp_path,
        "day,node_id,item_id,demand_multiplier\n"
        "0,customer:A,item:FG,1.1\n"
        "0,customer:A,item:FG,0.9\n",
    )

    with pytest.raises(DemandPerturbationError, match="Duplicate"):
        load_demand_perturbation_schedule(
            path,
            demand_pairs=DEMAND_PAIRS,
            measured_days=3,
        )
