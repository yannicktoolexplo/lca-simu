from __future__ import annotations

import pytest

from etudecas.simulation.engine.run_first_simulation import (
    resolve_mrp_requirement_pair_modes,
    supplier_planning_reliability,
)


def test_targeted_dynamic_pair_overrides_inherited_and_cli_static_modes() -> None:
    static_pairs, dynamic_pairs = resolve_mrp_requirement_pair_modes(
        ["M-1810|item:338929", "M-1810|item:001757"],
        ["M-1430,item:344135", "M-1810,item:338929"],
        ["M-1810,item:338929", "M-1430,item:344135"],
    )

    assert static_pairs == ["M-1810|item:001757"]
    assert dynamic_pairs == [
        "M-1430|item:344135",
        "M-1810|item:338929",
    ]


def test_temporary_supplier_loss_can_be_anticipated_or_unanticipated() -> None:
    assert supplier_planning_reliability(
        0.90,
        0.45,
        gross_up_temporary_risk_loss=True,
    ) == pytest.approx(0.45)
    assert supplier_planning_reliability(
        0.90,
        0.45,
        gross_up_temporary_risk_loss=False,
    ) == pytest.approx(0.90)


def test_disabling_temporary_loss_gross_up_does_not_change_nominal_case() -> None:
    anticipated = supplier_planning_reliability(
        0.97,
        0.97,
        gross_up_temporary_risk_loss=True,
    )
    unanticipated = supplier_planning_reliability(
        0.97,
        0.97,
        gross_up_temporary_risk_loss=False,
    )

    assert anticipated == pytest.approx(0.97)
    assert unanticipated == pytest.approx(anticipated)
