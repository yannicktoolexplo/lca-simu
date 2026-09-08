from __future__ import annotations

import csv
import shutil
from pathlib import Path

import pytest

from etudecas.prototypes.scan_2027_risk_control import (
    supplier_dynamic_capacity_coupling_audit as audit,
)


def _row(**updates: object) -> dict[str, object]:
    result: dict[str, object] = {
        "explicit_capacity_qty_per_day": 0.0,
        "process_capacity_qty_per_day": 0.0,
        "input_initial_stock_qty": 180.0,
        "standard_order_qty": 21_600.0,
        "lead_cover_days": 52.0,
        "applied_capacity_scale": 320.0,
        "external_procurement_target_utilization": 0.8,
    }
    result.update(updates)
    return result


def test_formula_replay_captures_lot_floor_and_upstream_coupling() -> None:
    row = _row()
    old_nominal, old_direct, _ = audit.replay_direct_capacity(
        row, demand_anchor=413.2065, review_days=7.0
    )
    new_nominal, new_direct, basis = audit.replay_direct_capacity(
        row, demand_anchor=29.232, review_days=7.0
    )
    old_need, old_upstream = audit.replay_upstream_capacity(
        row, demand_anchor=413.2065, review_days=7.0
    )
    new_need, new_upstream = audit.replay_upstream_capacity(
        row, demand_anchor=29.232, review_days=7.0
    )

    assert old_nominal == pytest.approx(516.508125)
    assert old_direct == pytest.approx(165_282.6)
    assert new_nominal == pytest.approx(36.54)
    assert new_direct == pytest.approx(21_600.0)
    assert basis.endswith("standard_lot_floor")
    assert old_need == pytest.approx(21_600.0 / 52.0)
    assert new_need == pytest.approx(21_600.0 / 52.0)
    assert old_upstream == pytest.approx(new_upstream)


@pytest.mark.skipif(
    not audit.DEFAULT_SUPPLIER_PARAMETERS.is_file(),
    reason="Completed reference export is not available in this checkout",
)
def test_real_audit_builds_and_validates_without_engine(tmp_path: Path) -> None:
    output = tmp_path / "audit"
    disposable_source = tmp_path / "supplier_nominal_parameters.csv"
    shutil.copyfile(audit.DEFAULT_SUPPLIER_PARAMETERS, disposable_source)
    result = audit.build(
        graph_path=audit.DEFAULT_GRAPH,
        supplier_parameters_path=disposable_source,
        current_floors_path=audit.DEFAULT_CURRENT_FLOORS,
        old_profile_path=audit.DEFAULT_OLD_PROFILE,
        new_profile_path=audit.DEFAULT_NEW_PROFILE,
        output_dir=output,
    )

    assert result["status"] == "analytical_pre_smoke_not_simulated"
    assert result["schema_version"] == "etudecas.dynamic_capacity_coupling_audit.v2"
    assert result["counts"] == audit.EXPECTED_COUNTS
    assert result["interpretation"]["mrp_only_causal_attribution_allowed"] is False
    assert (
        result["interpretation"][
            "true_heterogeneous_isolation_requires_engine_override"
        ]
        is True
    )
    frozen_source = output / audit.FROZEN_SUPPLIER_PARAMETERS
    assert frozen_source.read_bytes() == disposable_source.read_bytes()
    assert result["source_inputs"]["supplier_parameters"]["path"] == str(
        frozen_source.resolve()
    )
    assert result["source_retention"]["validation_depends_on_internal_snapshot_only"]

    # Summary retention may prune the original case export after a checkpoint.
    # The completed analytical package must remain independently valid.
    disposable_source.unlink()
    assert audit.validate(output)["status"].startswith("valid_analytical")
    report = (output / audit.REPORT_MD).read_text(encoding="utf-8")
    assert "M-1430\\|item:038005" in report
    assert "| M-1430|item:038005 |" not in report

    with (output / audit.LANE_CSV).open(encoding="utf-8", newline="") as handle:
        lanes = list(csv.DictReader(handle))
    assert len(lanes) == 33
    assert sum(row["in_19_pair_requirement_switch"] == "True" for row in lanes) == 27
    assert sum(row["estimated_direct_capacity_change"] == "True" for row in lanes) == 22
    assert sum(row["estimated_upstream_capacity_change"] == "True" for row in lanes) == 21

    with frozen_source.open("a", encoding="utf-8") as handle:
        handle.write("tampered\n")
    with pytest.raises(ValueError, match="mismatch"):
        audit.validate(output)
