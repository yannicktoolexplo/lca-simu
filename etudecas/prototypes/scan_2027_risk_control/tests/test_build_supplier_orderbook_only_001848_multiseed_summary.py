from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from etudecas.prototypes.scan_2027_risk_control import (
    build_supplier_orderbook_only_001848_multiseed_summary as summary,
)


def _row(seed: int, scenario: str, *, descendants: bool = False) -> dict[str, object]:
    stress = scenario == summary.STRESS
    return {
        "state_id": "prospective_001848_90d",
        "scenario_id": scenario,
        "seed": seed,
        "product_on_due_volume_proxy": 0.99,
        "product_on_due_volume_proxy_delta_vs_paired_baseline": 0.0,
        "product_released_qty_delta_vs_paired_baseline": 0.0,
        "product_backlog_qty_days_delta_vs_paired_baseline": 0.0,
        "causal_effect_on_receipt": stress,
        "causal_effect_on_descendants": descendants,
        "causal_effect_on_client": False,
        "outcome_signature_sha256": f"{scenario}-{seed}",
    }


def test_state_summary_counts_tested_effects_without_probability_claim() -> None:
    rows = []
    for seed in range(10):
        rows.extend(
            (
                _row(seed, summary.BASELINE),
                _row(seed, summary.STRESS, descendants=seed < 3),
            )
        )
    result = summary._state_summary(rows, "prospective_001848_90d")
    assert result["paired_seed_count"] == 10
    assert result["receipt_effect_seed_count"] == 10
    assert result["descendant_lot_effect_seed_count"] == 3
    assert result["descendant_lot_effect_share_of_tested_seeds"] == pytest.approx(0.3)
    assert result["client_effect_seed_count"] == 0
    assert "ni une fréquence historique" in result["interpretation"]


def test_distribution_reports_sample_standard_deviation() -> None:
    values = summary._distribution([1.0, 2.0, 3.0], "x")
    assert values["x_mean"] == 2.0
    assert values["x_sample_standard_deviation"] == pytest.approx(1.0)
    assert values["x_minimum"] == 1.0
    assert values["x_maximum"] == 3.0


def test_state_summary_rejects_unpaired_seed() -> None:
    with pytest.raises(summary.SummaryValidationError, match="Unpaired"):
        summary._state_summary(
            [_row(1, summary.BASELINE)], "prospective_001848_90d"
        )


def test_validate_trigger_accepts_audited_divergent_second_seed(tmp_path: Path) -> None:
    (tmp_path / "campaign_manifest.json").write_text(
        json.dumps(
            {
                "status": "complete",
                "new_seed_exactly_matches_screening_for_every_case": False,
                "physical_engine_run_count": 4,
                "seeds": [423082],
            }
        ),
        encoding="utf-8",
    )
    (tmp_path / "execution_provenance_audit.json").write_text(
        json.dumps({"reproducibility_wording_allowed": True}), encoding="utf-8"
    )
    with (tmp_path / "screening_seed_exact_comparison.csv").open(
        "w", encoding="utf-8", newline=""
    ) as handle:
        writer = csv.DictWriter(handle, fieldnames=["exact_outcome_match"])
        writer.writeheader()
        writer.writerows([{"exact_outcome_match": False}] * 4)
    result = summary._validate_trigger(tmp_path)
    assert result["seed"] == 423082
    assert result["all_four_outcomes_differ_from_screening_seed"] is True
