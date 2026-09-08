from __future__ import annotations

import json
import sys
from pathlib import Path

from etudecas.prototypes.scan_2027_risk_control import (
    audit_supplier_021081_execution_provenance as audit,
)
from etudecas.prototypes.scan_2027_risk_control import (
    supplier_021081_active_flow_campaign as campaign,
)


def unit_artifact(tmp_path: Path) -> tuple[Path, Path]:
    root = tmp_path / "unit_v2"
    root.mkdir()
    engine = tmp_path / "engine.py"
    graph = tmp_path / "source.json"
    profile = tmp_path / "profile.json"
    orchestrator = tmp_path / "unit_orchestrator.py"
    engine.write_text("# engine\n", encoding="utf-8")
    graph.write_text('{"source":true}\n', encoding="utf-8")
    profile.write_text('{"args":[]}\n', encoding="utf-8")
    orchestrator.write_text("# frozen unit orchestrator\n", encoding="utf-8")

    variant = root / "inputs" / "graph_literal__observed.json"
    variant.parent.mkdir(parents=True)
    variant.write_text('{"variant":true}\n', encoding="utf-8")
    case_dir = (
        root
        / "cases"
        / "literal__observed"
        / "baseline_observed_order_book"
        / "seed_7"
    )
    overlay = case_dir / "campaign_inputs" / "graph_overlay.json"
    overlay.parent.mkdir(parents=True)
    overlay.write_text('{"overlay":true}\n', encoding="utf-8")
    command = [
        sys.executable,
        str(engine),
        "--input",
        str(overlay),
        "--output-dir",
        str(case_dir),
        "--scenario-id",
        "scn:test",
        "--days",
        "720",
        "--seed",
        "7",
    ]
    (case_dir / "campaign_engine.log").write_text(
        "[time] COMMAND " + json.dumps(command) + "\n",
        encoding="utf-8",
    )
    campaign.write_csv(
        root / "unit_sensitivity_metrics.csv",
        [
            {
                "stage": "bom_unit_sensitivity",
                "state_regime": "literal__observed",
                "absolute_state_id": "observed",
                "unit_variant": "literal",
                "scenario_id": "baseline_observed_order_book",
                "seed": 7,
                "source_graph_sha256": campaign.sha256_file(variant),
                "source_graph_original_sha256": campaign.sha256_file(graph),
                "variant_graph_sha256": campaign.sha256_file(variant),
                "overlay_graph_sha256": campaign.sha256_file(overlay),
            }
        ],
    )
    campaign.write_json(
        root / "campaign_manifest.json",
        {
            "status": "complete",
            "case_count": 1,
            "engine": str(engine),
            "engine_sha256": campaign.sha256_file(engine),
            "source_graph": str(graph),
            "source_graph_sha256": campaign.sha256_file(graph),
            "profile": str(profile),
            "profile_sha256": campaign.sha256_file(profile),
            "orchestrator": str(orchestrator),
            "orchestrator_sha256_at_process_start": campaign.sha256_file(
                orchestrator
            ),
        },
    )
    return root, orchestrator


def test_audit_reads_unit_metrics_and_validates_variant_graph(tmp_path: Path) -> None:
    root, _ = unit_artifact(tmp_path)
    rows, summary = audit.audit_campaign(root)
    assert len(rows) == 1
    assert rows[0]["metric_file"] == "unit_sensitivity_metrics.csv"
    assert rows[0]["variant_source_matches"] is True
    assert rows[0]["overlay_graph_matches"] is True
    assert summary["case_count_matches_manifest"] is True
    assert summary["reproducibility_wording_allowed"] is True


def test_audit_hashes_manifest_orchestrator_not_campaign_library(
    tmp_path: Path,
) -> None:
    root, orchestrator = unit_artifact(tmp_path)
    rows, summary = audit.audit_campaign(root)
    assert rows[0]["orchestrator_path"] == str(orchestrator)
    assert rows[0]["orchestrator_matches_launch"] is True
    orchestrator.write_text("# changed after launch\n", encoding="utf-8")
    rows, summary = audit.audit_campaign(root)
    assert rows[0]["orchestrator_matches_launch"] is False
    assert summary["reproducibility_wording_allowed"] is False


def test_audit_rejects_mismatched_variant_even_if_original_matches(
    tmp_path: Path,
) -> None:
    root, _ = unit_artifact(tmp_path)
    variant = root / "inputs" / "graph_literal__observed.json"
    variant.write_text('{"variant":"changed"}\n', encoding="utf-8")
    rows, summary = audit.audit_campaign(root)
    assert rows[0]["variant_source_matches"] is False
    assert rows[0]["core_engine_graph_profile_match_manifest"] is False
    assert summary["reproducibility_wording_allowed"] is False


def test_audit_reads_baseline_calibration_metrics(tmp_path: Path) -> None:
    root, _ = unit_artifact(tmp_path)
    source = root / "unit_sensitivity_metrics.csv"
    target = root / "baseline_calibration_metrics.csv"
    source.replace(target)

    rows, summary = audit.audit_campaign(root)

    assert len(rows) == 1
    assert rows[0]["metric_file"] == "baseline_calibration_metrics.csv"
    assert summary["case_count_matches_manifest"] is True
    assert summary["reproducibility_wording_allowed"] is True


def test_audit_accepts_summary_pruned_overlay_only_with_reverified_recipe(
    tmp_path: Path,
) -> None:
    root, _ = unit_artifact(tmp_path)
    metric_path = root / "unit_sensitivity_metrics.csv"
    metric = campaign.read_csv_rows(metric_path)[0]
    case_dir = (
        root
        / "cases"
        / "literal__observed"
        / "baseline_observed_order_book"
        / "seed_7"
    )
    inputs = case_dir / "campaign_inputs"
    overlay = inputs / "graph_overlay.json"
    ledger = inputs / "observed_order_overlay_ledger.csv"
    overlay_audit = inputs / "overlay_audit.json"
    state_scale = root / "inputs" / "measurement_start_scale.csv"
    ledger.write_text("source_row,qty\n1,2\n", encoding="utf-8")
    overlay_audit.write_text('{"ok":true}\n', encoding="utf-8")
    state_scale.write_text("node_id,item_id,scale\nA,item:X,1\n", encoding="utf-8")
    command_log = case_dir / "campaign_engine.log"
    command = json.loads(command_log.read_text(encoding="utf-8").split("COMMAND ", 1)[1])
    command.extend(["--measurement-start-stock-scale-csv", str(state_scale)])
    command_log.write_text(
        "[time] COMMAND " + json.dumps(command) + "\n",
        encoding="utf-8",
    )
    metric.update(
        {
            "observed_order_ledger_sha256": campaign.sha256_file(ledger),
            "overlay_audit_sha256": campaign.sha256_file(overlay_audit),
            "measurement_start_stock_scale_csv_sha256": campaign.sha256_file(
                state_scale
            ),
        }
    )
    campaign.write_csv(metric_path, [metric])
    overlay.unlink()

    rows, summary = audit.audit_campaign(root)

    assert rows[0]["overlay_graph_matches"] is False
    assert rows[0]["overlay_replay_recipe_matches"] is True
    assert rows[0]["overlay_verification_status"] == (
        "pruned_after_hash_recipe_reverified"
    )
    assert summary["reproducibility_wording_allowed"] is True


def test_audit_rejects_summary_pruned_overlay_with_changed_ledger(
    tmp_path: Path,
) -> None:
    root, _ = unit_artifact(tmp_path)
    metric_path = root / "unit_sensitivity_metrics.csv"
    metric = campaign.read_csv_rows(metric_path)[0]
    case_dir = (
        root
        / "cases"
        / "literal__observed"
        / "baseline_observed_order_book"
        / "seed_7"
    )
    inputs = case_dir / "campaign_inputs"
    overlay = inputs / "graph_overlay.json"
    ledger = inputs / "observed_order_overlay_ledger.csv"
    overlay_audit = inputs / "overlay_audit.json"
    state_scale = root / "inputs" / "measurement_start_scale.csv"
    ledger.write_text("source_row,qty\n1,2\n", encoding="utf-8")
    overlay_audit.write_text('{"ok":true}\n', encoding="utf-8")
    state_scale.write_text("node_id,item_id,scale\nA,item:X,1\n", encoding="utf-8")
    command_log = case_dir / "campaign_engine.log"
    command = json.loads(command_log.read_text(encoding="utf-8").split("COMMAND ", 1)[1])
    command.extend(["--measurement-start-stock-scale-csv", str(state_scale)])
    command_log.write_text(
        "[time] COMMAND " + json.dumps(command) + "\n",
        encoding="utf-8",
    )
    metric.update(
        {
            "observed_order_ledger_sha256": campaign.sha256_file(ledger),
            "overlay_audit_sha256": campaign.sha256_file(overlay_audit),
            "measurement_start_stock_scale_csv_sha256": campaign.sha256_file(
                state_scale
            ),
        }
    )
    campaign.write_csv(metric_path, [metric])
    overlay.unlink()
    ledger.write_text("source_row,qty\n1,999\n", encoding="utf-8")

    rows, summary = audit.audit_campaign(root)

    assert rows[0]["observed_order_ledger_matches"] is False
    assert rows[0]["overlay_replay_recipe_matches"] is False
    assert summary["reproducibility_wording_allowed"] is False


def test_audit_resolves_demasking_state_graph_from_overlay_audit(
    tmp_path: Path,
) -> None:
    root, _ = unit_artifact(tmp_path)
    metric_path = root / "unit_sensitivity_metrics.csv"
    metric = campaign.read_csv_rows(metric_path)[0]
    variant = root / "inputs" / "graph_literal__observed.json"
    metric.pop("variant_graph_sha256")
    metric.pop("source_graph_original_sha256")
    metric["source_graph_sha256"] = campaign.sha256_file(variant)
    campaign.write_csv(metric_path, [metric])
    manifest = campaign.read_json(root / "campaign_manifest.json")
    campaign.write_json(
        root / "production_layer_overlay_audit.json",
        {
            "literal__observed": {
                "source_graph_sha256": manifest["source_graph_sha256"],
                "state_graph_sha256": campaign.sha256_file(variant),
            }
        },
    )

    rows, summary = audit.audit_campaign(root)

    assert rows[0]["source_graph_original_sha256_metric"] == manifest[
        "source_graph_sha256"
    ]
    assert rows[0]["variant_source_matches"] is True
    assert summary["reproducibility_wording_allowed"] is True
