from __future__ import annotations

import tempfile
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from etudecas.prototypes.scan_2027_risk_control.calibration import (
    VALIDATED_REGIMES,
    apply_calibrated_regime_labels,
    apply_regime_annotations,
    build_calibration_frame,
    calibrate_from_context,
    load_regime_annotations,
)
from etudecas.prototypes.scan_2027_risk_control.core import (
    REGIME_CLASSIFICATION_RULES,
    RunContext,
    SimulationState,
    aggregate_baseline_with_metadata,
    build_input_context,
    classify_regime_signals,
    load_config,
)
from etudecas.prototypes.scan_2027_risk_control.model import classify_regime


CONFIG = load_config(None)
THRESHOLDS = CONFIG["regime_thresholds"]


def _signals(**updates: float | bool) -> dict[str, float | bool]:
    result: dict[str, float | bool] = {
        "backlog_days": 0.0,
        "previous_backlog_days": 0.0,
        "service": 1.0,
        "supplier_risk": 0.10,
        "supplier_stress": 0.10,
        "nervousness": 0.10,
        "production_utilization": 0.20,
        "supplier_utilization": 0.20,
        "material_cover_days": 2.0,
        "material_cover_known": True,
        "inventory_cover_days": 4.0,
        "inventory_excess_ratio": 1.0,
        "recent_disruption_signal": 0.0,
        "post_crisis_overstock_candidate": 0.0,
    }
    result.update(updates)
    return result


REGIME_BOUNDARY_CASES = (
    (
        "NOMINAL",
        _signals(),
    ),
    (
        "MATERIAL_TENSION",
        _signals(material_cover_days=THRESHOLDS["material_tension_days"]),
    ),
    (
        "CAPACITY_SATURATION",
        _signals(
            backlog_days=0.0200001,
            production_utilization=THRESHOLDS["capacity_saturation"],
            material_cover_days=THRESHOLDS["material_tension_days"],
        ),
    ),
    (
        "SUPPLIER_STRESS",
        _signals(
            backlog_days=0.06,
            supplier_risk=THRESHOLDS["supplier_risk"],
            nervousness=THRESHOLDS["oscillation_nervousness"],
            production_utilization=THRESHOLDS["capacity_saturation"],
            material_cover_days=THRESHOLDS["material_tension_days"],
        ),
    ),
    (
        "OSCILLATORY",
        _signals(
            backlog_days=0.0500001,
            nervousness=THRESHOLDS["oscillation_nervousness"],
            production_utilization=THRESHOLDS["capacity_saturation"],
            material_cover_days=THRESHOLDS["material_tension_days"],
        ),
    ),
    (
        "CRISIS",
        _signals(
            backlog_days=THRESHOLDS["crisis_backlog_days"],
            service=np.nextafter(0.95, 0.0),
            supplier_risk=THRESHOLDS["supplier_risk"],
            supplier_stress=THRESHOLDS["supplier_stress"],
            nervousness=THRESHOLDS["oscillation_nervousness"],
            production_utilization=THRESHOLDS["capacity_saturation"],
            material_cover_days=THRESHOLDS["material_tension_days"],
        ),
    ),
    (
        "RECOVERY",
        _signals(
            backlog_days=THRESHOLDS["recovery_backlog_days"],
            previous_backlog_days=THRESHOLDS["recovery_backlog_days"] + 0.01,
        ),
    ),
    (
        "POST_CRISIS_OVERSTOCK",
        _signals(
            backlog_days=0.02,
            inventory_cover_days=THRESHOLDS["overstock_days"],
            inventory_excess_ratio=1.05,
            recent_disruption_signal=np.nextafter(0.0, 1.0),
            post_crisis_overstock_candidate=1.0,
        ),
    ),
)


def _calibration_row(signals: dict[str, float | bool]) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "backlog_days": signals["backlog_days"],
                "previous_backlog_days": signals["previous_backlog_days"],
                "service": signals["service"],
                "base_risk": signals["supplier_risk"],
                "supplier_stress_proxy": signals["supplier_stress"],
                "nervousness": signals["nervousness"],
                "production_utilization": signals["production_utilization"],
                "supplier_utilization": signals["supplier_utilization"],
                "material_cover_days": signals["material_cover_days"],
                "material_cover_known": signals["material_cover_known"],
                "inventory_cover_days": signals["inventory_cover_days"],
                "inventory_excess_ratio": signals["inventory_excess_ratio"],
                "recent_disruption_signal": signals["recent_disruption_signal"],
                "post_crisis_overstock_candidate": signals[
                    "post_crisis_overstock_candidate"
                ],
            }
        ]
    )


def _operational_state_and_metrics(
    signals: dict[str, float | bool],
) -> tuple[SimulationState, dict[str, float | bool]]:
    material_cover = float(signals["material_cover_days"])
    total_cover = float(signals["inventory_cover_days"])
    state = SimulationState(
        raw_inventory=material_cover,
        finished_inventory=max(0.0, total_cover - material_cover),
        backlog=float(signals["backlog_days"]),
        pipeline=1.0,
        previous_order=1.0,
        supplier_stress=float(signals["supplier_stress"]),
        supplier_risk=float(signals["supplier_risk"]),
        previous_backlog=float(signals["previous_backlog_days"]),
    )
    metrics: dict[str, float | bool] = {
        "demand": 1.0,
        "service": signals["service"],
        "nervousness": signals["nervousness"],
        "production_utilization": signals["production_utilization"],
        "supplier_utilization": signals["supplier_utilization"],
        "material_cover_days": signals["material_cover_days"],
        "material_cover_known": signals["material_cover_known"],
        "inventory_excess_ratio": signals["inventory_excess_ratio"],
        "recent_disruption_signal": signals["recent_disruption_signal"],
        "post_crisis_overstock_candidate": signals[
            "post_crisis_overstock_candidate"
        ],
    }
    return state, metrics


@pytest.mark.parametrize(("expected", "signals"), REGIME_BOUNDARY_CASES)
def test_calibration_and_operational_classification_share_rules_and_priority(
    expected: str,
    signals: dict[str, float | bool],
) -> None:
    direct = classify_regime_signals(signals, THRESHOLDS)
    calibrated = apply_calibrated_regime_labels(
        _calibration_row(signals), THRESHOLDS
    ).loc[0, "calibrated_regime"]
    state, metrics = _operational_state_and_metrics(signals)
    operational = classify_regime(state, metrics, CONFIG)

    assert direct == expected
    assert calibrated == expected
    assert operational == expected


@pytest.mark.parametrize(
    ("updates", "expected"),
    (
        (
            {
                "backlog_days": THRESHOLDS["crisis_backlog_days"],
                "service": 0.95,
            },
            "NOMINAL",
        ),
        (
            {
                "backlog_days": 0.05,
                "nervousness": THRESHOLDS["oscillation_nervousness"],
            },
            "NOMINAL",
        ),
        (
            {
                "backlog_days": 0.02,
                "production_utilization": THRESHOLDS["capacity_saturation"],
            },
            "NOMINAL",
        ),
    ),
)
def test_strict_secondary_boundaries_are_explicit(
    updates: dict[str, float], expected: str
) -> None:
    assert classify_regime_signals(_signals(**updates), THRESHOLDS) == expected


@pytest.mark.parametrize(
    "material_value",
    (np.nan, None),
)
def test_unknown_material_cover_does_not_trigger_tension(
    material_value: float | None,
) -> None:
    row = _calibration_row(_signals())
    row["material_cover_days"] = material_value
    row["material_cover_known"] = False
    result = apply_calibrated_regime_labels(row, THRESHOLDS)
    assert result.loc[0, "calibrated_regime"] == "NOMINAL"

    without_material_columns = row.drop(
        columns=["material_cover_days", "material_cover_known"]
    )
    result_without = apply_calibrated_regime_labels(
        without_material_columns, THRESHOLDS
    )
    assert result_without.loc[0, "calibrated_regime"] == "NOMINAL"


def test_pair_level_material_gaps_remain_unknown_in_calibration_frame() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        data_dir = Path(tmp) / "baseline" / "data"
        data_dir.mkdir(parents=True)
        baseline_path = data_dir / "first_simulation_daily.csv"
        pd.DataFrame(
            {
                "day": np.arange(7),
                "demand": 100.0,
                "served": 100.0,
                "backlog_end": 0.0,
                "arrivals_qty": 100.0,
                "produced_qty": 100.0,
                "inventory_total": 500.0,
                "orders": 100.0,
            }
        ).to_csv(baseline_path, index=False)
        pd.DataFrame(
            {
                "day": [0, 1, 2],
                "node_id": "F1",
                "item_id": "RAW",
                "stock_end_of_day": [20.0, 20.0, 20.0],
            }
        ).to_csv(data_dir / "production_input_stocks_daily.csv", index=False)
        pd.DataFrame(
            {
                "day": [0, 1, 2],
                "node_id": "F1",
                "item_id": "RAW",
                "consumed_qty": [10.0, 10.0, 10.0],
            }
        ).to_csv(data_dir / "production_input_consumption_daily.csv", index=False)
        context = build_input_context(
            Path(tmp),
            str(baseline_path),
            "auto",
            7,
            1,
            False,
            mapping_config=CONFIG["physical_risk_mapping"],
        )
        frame, _ = build_calibration_frame(context)

    gaps = frame.loc[frame["day"] >= 3]
    assert gaps["material_cover_days"].isna().all()
    assert not gaps["material_cover_known"].any()
    assert set(gaps["material_cover_status"]) == {"unknown_pair_level_gap"}


@pytest.mark.parametrize("inventory_mode", ("absent", "all_nan"))
def test_absent_or_all_nan_aggregate_inventory_is_unknown_not_stockout(
    inventory_mode: str,
) -> None:
    baseline = pd.DataFrame(
        {
            "day": np.arange(8),
            "demand": 1.0,
            "served": 1.0,
            "backlog": 0.0,
            "arrivals": 1.0,
            "produced": 1.0,
            "orders": 1.0,
        }
    )
    if inventory_mode == "all_nan":
        baseline["inventory"] = np.nan
    daily, _, metadata = aggregate_baseline_with_metadata(baseline, 8)
    daily["base_risk"] = 0.1
    daily["risk_uncertainty"] = 0.05
    context = RunContext(
        input_series=daily,
        source_mode="etudecas_baseline",
        baseline_path=None,
        risk_path=None,
        observability_base=0.7,
        baseline_columns=list(baseline.columns),
        baseline_ingestion_metadata=metadata,
    )

    frame, _ = build_calibration_frame(context)
    labeled = apply_calibrated_regime_labels(frame, THRESHOLDS)
    artifacts = calibrate_from_context(context, CONFIG)

    assert not daily["inventory_signal_known"].any()
    assert metadata["unknown_signal_days"]["inventory"] == 8
    assert frame["material_cover_days"].isna().all()
    assert not frame["material_cover_known"].any()
    assert not (labeled["calibrated_regime"] == "MATERIAL_TENSION").any()
    material_evidence = artifacts.evidence.loc[
        artifacts.evidence["regime"] == "MATERIAL_TENSION"
    ].iloc[0]
    assert material_evidence["signal_status"] == "insufficient_signal"
    assert "unknown material cover" in material_evidence["limitations"]


def test_text_false_material_known_flag_is_not_truthy() -> None:
    signals = _signals(material_cover_days=0.0, material_cover_known="False")
    assert classify_regime_signals(signals, THRESHOLDS) == "NOMINAL"

    row = _calibration_row(_signals(material_cover_days=0.0))
    row["material_cover_known"] = "False"
    calibrated = apply_calibrated_regime_labels(row, THRESHOLDS)
    assert calibrated.loc[0, "calibrated_regime"] == "NOMINAL"


def test_calibration_evidence_has_one_complete_row_per_regime() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        context = build_input_context(
            Path(tmp), "auto", "auto", 35, 3, True,
            mapping_config=CONFIG["physical_risk_mapping"],
        )
        artifacts = calibrate_from_context(context, CONFIG)

    evidence = artifacts.evidence
    required = {
        "regime",
        "classification_rule",
        "variables_used",
        "initial_thresholds",
        "calibrated_thresholds",
        "method",
        "anchor_count",
        "separation",
        "confidence",
        "limitations",
    }
    assert required <= set(evidence.columns)
    assert evidence["regime"].tolist() == list(VALIDATED_REGIMES)
    assert not evidence["regime"].duplicated().any()
    assert evidence["classification_rule"].to_dict() == {
        index: REGIME_CLASSIFICATION_RULES[regime]
        for index, regime in enumerate(VALIDATED_REGIMES)
    }
    text_columns = sorted(required - {"anchor_count", "separation"})
    assert evidence[text_columns].notna().all().all()


def _dated_annotations(path: Path) -> None:
    pd.DataFrame(
        {
            "period": ["2026-10-01", "2026-10-03"],
            "site": ["S1", "S2"],
            "item": ["A1", "A2"],
            "validated_regime": ["NOMINAL", "SUPPLIER_STRESS"],
            "expert_confidence": [0.6, 0.9],
            "comment": ["baseline", "supplier alert"],
        }
    ).to_csv(path, index=False)


def test_calendar_annotations_require_baseline_origin_and_use_exact_offsets() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "dated_annotations.csv"
        _dated_annotations(path)
        with pytest.raises(ValueError, match="explicit baseline calendar origin"):
            load_regime_annotations(path)

        annotations = load_regime_annotations(
            path, period_origin="2026-09-28"
        )

    assert annotations.rows["day"].tolist() == [3, 5]
    assert annotations.metadata["time_mapping"] == (
        "calendar_day_offset_from_baseline_origin:2026-09-28"
    )


def test_calendar_annotations_outside_horizon_are_not_applied() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "dated_annotations.csv"
        _dated_annotations(path)
        annotations = load_regime_annotations(
            path, period_origin="2026-09-28"
        )

    frame = pd.DataFrame(
        {"day": [0, 1, 2, 3], "calibrated_regime": ["NOMINAL"] * 4}
    )
    applied, metadata = apply_regime_annotations(frame, annotations)
    assert applied.loc[applied["day"] == 3, "calibrated_regime"].item() == "NOMINAL"
    assert metadata["matched_annotation_days"] == 1
    assert metadata["unmatched_annotation_days"] == 1


def test_calendar_annotation_before_origin_is_rejected() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "dated_annotations.csv"
        _dated_annotations(path)
        with pytest.raises(ValueError, match="precede the baseline period origin"):
            load_regime_annotations(path, period_origin="2026-10-02")


def test_baseline_calendar_column_exposes_only_a_coherent_origin() -> None:
    baseline = pd.DataFrame(
        {
            "day": [0, 1, 2],
            "calendar_date": ["2026-09-28", "2026-09-29", "2026-09-30"],
            "demand": [1.0, 1.0, 1.0],
            "served": [1.0, 1.0, 1.0],
            "backlog": [0.0, 0.0, 0.0],
            "arrivals": [1.0, 1.0, 1.0],
            "produced": [1.0, 1.0, 1.0],
            "inventory": [4.0, 4.0, 4.0],
            "orders": [1.0, 1.0, 1.0],
        }
    )
    _, _, metadata = aggregate_baseline_with_metadata(baseline, 3)
    assert metadata["period_origin"] == "2026-09-28"
    assert metadata["period_origin_source"].startswith("baseline_calendar_column")

    inconsistent = baseline.copy()
    inconsistent.loc[2, "calendar_date"] = "2026-10-03"
    _, _, inconsistent_metadata = aggregate_baseline_with_metadata(inconsistent, 3)
    assert inconsistent_metadata["period_origin"] is None
