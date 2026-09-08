from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
import subprocess
import sys

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
ENGINE = (
    REPO_ROOT
    / "etudecas"
    / "simulation"
    / "engine"
    / "run_first_simulation.py"
)
GRAPH = (
    REPO_ROOT
    / "etudecas"
    / "simulation_prep"
    / "result"
    / "reference_baseline"
    / "supply_graph_reference_baseline_real_demand_target_calibrated_mrp_lot_policy_recalibrated_5y.json"
)


def _first_demand_pair() -> tuple[str, str]:
    graph = json.loads(GRAPH.read_text(encoding="utf-8"))
    scenario = next(
        row
        for row in graph["scenarios"]
        if str(row.get("id")) == "scn:BASE"
    )
    demand = scenario["demand"][0]
    return str(demand["node_id"]), str(demand["item_id"])


def _run_engine(
    output_dir: Path,
    *,
    perturbation_csv: Path | None = None,
) -> subprocess.CompletedProcess[str]:
    command = [
        sys.executable,
        str(ENGINE),
        "--input",
        str(GRAPH),
        "--output-dir",
        str(output_dir),
        "--scenario-id",
        "scn:BASE",
        "--days",
        "2",
        "--warmup-days",
        "2",
        "--warmup-boundary-audit",
        "--seed",
        "9102",
        "--output-profile",
        "compact",
        "--skip-map",
        "--skip-plots",
        "--no-lot-trace",
        "--skip-lot-audit",
        "--use-bom-demand-signal-for-mrp",
        "--mrp-demand-signal-smoothing-days",
        "1",
    ]
    if perturbation_csv is not None:
        command.extend(
            ["--demand-perturbation-csv", str(perturbation_csv)]
        )
    return subprocess.run(
        command,
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
        timeout=120,
    )


def _summary(output_dir: Path) -> dict:
    return json.loads(
        (
            output_dir
            / "summaries"
            / "first_simulation_summary.json"
        ).read_text(encoding="utf-8")
    )


def _demand_rows(
    output_dir: Path,
    pair: tuple[str, str],
) -> dict[int, dict[str, str]]:
    with (
        output_dir / "data" / "production_demand_service_daily.csv"
    ).open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    return {
        int(row["day"]): row
        for row in rows
        if (row["node_id"], row["item_id"]) == pair
    }


def _mrp_rows(
    output_dir: Path,
    pair: tuple[str, str],
) -> dict[int, dict[str, str]]:
    with (output_dir / "data" / "mrp_trace_daily.csv").open(
        encoding="utf-8",
        newline="",
    ) as handle:
        rows = list(csv.DictReader(handle))
    return {
        int(row["day"]): row
        for row in rows
        if (row["node_id"], row["item_id"]) == pair
    }


def test_j0_excitation_preserves_boundary_and_starts_on_measured_day_zero(
    tmp_path: Path,
) -> None:
    pair = _first_demand_pair()
    baseline_dir = tmp_path / "baseline"
    baseline = _run_engine(baseline_dir)
    assert baseline.returncode == 0, baseline.stderr or baseline.stdout

    # No flag means no new artifact and no summary-schema change.
    baseline_summary = _summary(baseline_dir)
    assert "demand_perturbation" not in baseline_summary["policy"]
    assert not (
        baseline_dir / "data" / "canonical_demand_perturbations.csv"
    ).exists()

    perturbation_csv = tmp_path / "excitation.csv"
    perturbation_csv.write_text(
        "day,node_id,item_id,demand_multiplier\n"
        f"0,{pair[0]},{pair[1]},1.25\n",
        encoding="utf-8",
    )
    excited_dir = tmp_path / "excited"
    excited = _run_engine(
        excited_dir,
        perturbation_csv=perturbation_csv,
    )
    assert excited.returncode == 0, excited.stderr or excited.stdout

    excited_summary = _summary(excited_dir)
    baseline_boundary = baseline_summary["policy"]["warmup_boundary_audit"]
    excited_boundary = excited_summary["policy"]["warmup_boundary_audit"]
    assert excited_boundary["core_state_sha256"] == baseline_boundary[
        "core_state_sha256"
    ]
    assert excited_boundary["component_sha256"] == baseline_boundary[
        "component_sha256"
    ]

    baseline_demand = _demand_rows(baseline_dir, pair)
    excited_demand = _demand_rows(excited_dir, pair)
    assert float(excited_demand[0]["demand_qty"]) == pytest.approx(
        float(baseline_demand[0]["demand_qty"]) * 1.25,
        abs=1e-6,
    )
    assert excited_demand[1]["demand_qty"] == baseline_demand[1][
        "demand_qty"
    ]
    baseline_mrp = _mrp_rows(baseline_dir, pair)
    excited_mrp = _mrp_rows(excited_dir, pair)
    assert float(excited_mrp[0]["bb_demand_signal_qty"]) == pytest.approx(
        float(baseline_mrp[0]["bb_demand_signal_qty"]) * 1.25,
        abs=1e-6,
    )
    assert excited_mrp[1]["bb_demand_signal_qty"] == baseline_mrp[1][
        "bb_demand_signal_qty"
    ]

    audit_path = (
        excited_dir / "data" / "canonical_demand_perturbations.csv"
    )
    with audit_path.open(encoding="utf-8", newline="") as handle:
        audit_rows = list(csv.DictReader(handle))
    assert len(audit_rows) == 1
    assert audit_rows[0]["day"] == "0"
    assert audit_rows[0]["node_id"] == pair[0]
    assert audit_rows[0]["item_id"] == pair[1]
    assert audit_rows[0]["status"] == "applied"
    assert float(audit_rows[0]["base_demand_qty"]) == pytest.approx(
        float(baseline_demand[0]["demand_qty"]),
        abs=1e-6,
    )
    assert float(audit_rows[0]["perturbed_demand_qty"]) == pytest.approx(
        float(excited_demand[0]["demand_qty"]),
        abs=1e-6,
    )

    manifest = excited_summary["policy"]["demand_perturbation"]
    assert manifest["source_csv"] == str(perturbation_csv.resolve())
    assert manifest["sha256"] == hashlib.sha256(
        perturbation_csv.read_bytes()
    ).hexdigest()
    assert manifest["row_count"] == 1
    assert manifest["applied_count"] == 1
    assert manifest["warmup_application_count"] == 0
    assert manifest["audit_csv"] == (
        "data/canonical_demand_perturbations.csv"
    )

    generic_manifest = json.loads(
        (excited_dir / "run" / "run_manifest.json").read_text(
            encoding="utf-8"
        )
    )
    assert generic_manifest["metadata"]["demand_perturbation"] == manifest
