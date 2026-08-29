from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

import pytest

from etudecas.prototypes.scan_2027_risk_control.canonical_industrial_brief import (
    DELAY_CASCADE_ID,
    EXPECTED_DEMO_SCHEMA_VERSION,
    FINISHED_ITEM_BY_CASCADE,
    QUALITY_CASCADE_ID,
    _select_series,
    _short_axis_number,
    _svg_chart,
    _trailing_rolling_mean,
    build_industrial_brief,
)


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def _metric(mean: float, maximum: float | None = None) -> dict[str, float]:
    return {
        "mean": mean,
        "min": mean,
        "max": mean if maximum is None else maximum,
    }


def _aggregate(
    cascade_id: str,
    solution_id: str,
    *,
    no_action: float,
    no_action_worst: float,
    remaining: float,
    days: float,
    cost: float,
    exposed: int,
) -> dict[str, object]:
    return {
        "cascade_id": cascade_id,
        "solution_id": solution_id,
        "customer_exposure_count": exposed,
        "customer_no_exposure_count": 10 - exposed,
        "simulation_count": 10,
        "metrics": {
            "no_action_incremental_customer_backlog_qty_days": _metric(
                no_action, no_action_worst
            ),
            "remaining_incremental_customer_backlog_qty_days": _metric(
                remaining, remaining * 2
            ),
            "days_recovered_vs_no_action": _metric(days),
            "incremental_decision_total_cost_vs_no_action": _metric(cost),
        },
    }


def _series(
    metric: str,
    node_id: str,
    item_id: str,
    base: float,
    *,
    uom: str = "UN",
) -> dict[str, object]:
    mean = [base + float(value % 7) for value in range(720)]
    return {
        "metric": metric,
        "node_id": node_id,
        "item_id": item_id,
        "uom": uom,
        "mean": mean,
        "min": [max(0.0, value - 0.5) for value in mean],
        "max": [value + 0.5 for value in mean],
    }


def _variant_series(cascade_id: str, base: float) -> list[dict[str, object]]:
    if cascade_id == QUALITY_CASCADE_ID:
        return [
            _series(
                "input_stock_end_qty", "SDC-1450", "item:021081", base, uom="KG"
            ),
            _series(
                "production_released_qty", "M-1430", "item:268967", base + 3
            ),
            _series(
                "customer_backlog_end_qty", "C-XXXXX", "item:268967", base + 6
            ),
        ]
    return [
        _series("input_stock_end_qty", "M-1810", "item:338929", base),
        _series("production_released_qty", "M-1810", "item:268091", base + 3),
        _series(
            "customer_backlog_end_qty", "C-XXXXX", "item:268091", base + 6
        ),
    ]


def _registry_fixture(
    data_dir: Path,
    *,
    registry_dir: str,
    cascade_id: str,
    uom: str,
) -> dict[str, object]:
    directory = data_dir / registry_dir
    entity_rows = [
        {
            "entity_type": "finished_product_lot",
            "item_id": FINISHED_ITEM_BY_CASCADE[cascade_id],
            "lot_id": f"FINISHED-{index}",
        }
        for index in range(3)
    ]
    if cascade_id == QUALITY_CASCADE_ID:
        entity_rows.append(
            {
                "entity_type": "finished_product_lot",
                "item_id": "item:773474",
                "lot_id": "INTERMEDIATE-0",
            }
        )
    files = {
        "bundles": (
            "risk_impact_exposure_bundles.csv",
            [
                {
                    "exposure_bundle_id": f"BUNDLE-{index}",
                    "shipped_qty": 10 + index,
                    "uom": uom,
                }
                for index in range(2)
            ],
        ),
        "entities": (
            "risk_impact_entities.csv",
            entity_rows,
        ),
        "client_service": (
            "risk_impact_client_service.csv",
            [
                {
                    "client_lot_id": f"CLIENT-LOT-{index}",
                    "client_node_id": "C-XXXXX",
                }
                for index in range(4)
            ],
        ),
    }
    metadata: dict[str, object] = {}
    for artifact_id, (filename, rows) in files.items():
        path = directory / filename
        _write_csv(path, rows)
        metadata[artifact_id] = {
            "filename": filename,
            "sha256": _digest(path),
            "row_count": len(rows),
        }
    return {
        "verification_status": "campaign_run_verified_and_paired_to_final_campaign",
        "identity": {
            "cascade_id": cascade_id,
            "variant_id": "incident_no_action",
            "seed": 330281,
        },
        "registry_outputs": {
            "verified": True,
            "csv_artifacts": metadata,
        },
    }


def _fixture(tmp_path: Path) -> Path:
    demo_dir = tmp_path / "scientific-demo"
    data_dir = demo_dir / "data"
    data_dir.mkdir(parents=True)
    aggregates = [
        _aggregate(
            QUALITY_CASCADE_ID,
            "combined_response",
            no_action=100.0,
            no_action_worst=300.0,
            remaining=35.0,
            days=12.0,
            cost=40.0,
            exposed=9,
        ),
        _aggregate(
            QUALITY_CASCADE_ID,
            "expedited_transport",
            no_action=100.0,
            no_action_worst=300.0,
            remaining=60.0,
            days=8.0,
            cost=5.0,
            exposed=9,
        ),
        _aggregate(
            DELAY_CASCADE_ID,
            "expedited_transport",
            no_action=20.0,
            no_action_worst=80.0,
            remaining=0.0,
            days=4.0,
            cost=3.0,
            exposed=2,
        ),
        _aggregate(
            DELAY_CASCADE_ID,
            "combined_response",
            no_action=20.0,
            no_action_worst=80.0,
            remaining=0.0,
            days=4.0,
            cost=7.0,
            exposed=2,
        ),
        _aggregate(
            DELAY_CASCADE_ID,
            "replanning",
            no_action=20.0,
            no_action_worst=80.0,
            remaining=86.0,
            days=-3.0,
            cost=1.0,
            exposed=2,
        ),
    ]
    demo_data = {"schema_version": EXPECTED_DEMO_SCHEMA_VERSION, "aggregates": aggregates}
    (demo_dir / "index.html").write_text(
        '<script id="demo-data" type="application/json">'
        + json.dumps(demo_data)
        + "</script>",
        encoding="utf-8",
    )
    registry_provenance = [
        _registry_fixture(
            data_dir,
            registry_dir="risk_registry_01",
            cascade_id=QUALITY_CASCADE_ID,
            uom="KG",
        ),
        _registry_fixture(
            data_dir,
            registry_dir="risk_registry_02",
            cascade_id=DELAY_CASCADE_ID,
            uom="UN",
        ),
    ]
    (demo_dir / "demo_manifest.json").write_text(
        json.dumps(
            {
                "schema_version": EXPECTED_DEMO_SCHEMA_VERSION,
                "status": "complete",
                "counts": {
                    "cascade_runs": 180,
                    "minimum_paired_seed_count": 10,
                },
                "risk_registry_provenance": registry_provenance,
            }
        ),
        encoding="utf-8",
    )
    compact = {
        "day_axis": list(range(720)),
        "cascades": {
            QUALITY_CASCADE_ID: {
                "variants": {
                    variant: {"series": _variant_series(QUALITY_CASCADE_ID, index)}
                    for index, variant in enumerate(
                        (
                            "normal",
                            "incident_no_action",
                            "incident_combined_response",
                            "incident_expedited_transport",
                        )
                    )
                }
            },
            DELAY_CASCADE_ID: {
                "variants": {
                    variant: {"series": _variant_series(DELAY_CASCADE_ID, index)}
                    for index, variant in enumerate(
                        (
                            "normal",
                            "incident_no_action",
                            "incident_expedited_transport",
                            "incident_replanning",
                        )
                    )
                }
            },
        },
    }
    compact_path = data_dir / "canonical_cascade_trajectories_compact.json"
    compact_path.write_text(json.dumps(compact), encoding="utf-8")
    (data_dir / "canonical_cascade_trajectories_manifest.json").write_text(
        json.dumps({"outputs": {"compact_json_sha256": _digest(compact_path)}}),
        encoding="utf-8",
    )
    return demo_dir


def test_builds_a_small_static_offline_brief(tmp_path: Path) -> None:
    demo_dir = _fixture(tmp_path)
    source_hashes = {
        path: _digest(path) for path in demo_dir.rglob("*") if path.is_file()
    }

    artifacts = build_industrial_brief(
        demo_dir=demo_dir,
        output_dir=tmp_path / "brief",
    )

    document = artifacts.index_path.read_text(encoding="utf-8")
    manifest = json.loads(artifacts.manifest_path.read_text(encoding="utf-8"))
    results = json.loads(artifacts.results_path.read_text(encoding="utf-8"))
    assert "Si un fournisseur se dégrade" in document
    assert "PRÉVISION CONDITIONNELLE DES RISQUES FOURNISSEURS" in document
    assert "cascades réelles du modèle" not in document
    assert "ni des risques détectés ou classés" in document
    assert document.count('class="chart-card"') == 6
    assert document.count("Moyenne glissante 5 j") == 2
    assert document.count("Moyenne glissante 7 j") == 2
    assert document.count("Moyenne glissante 14 j") == 2
    assert document.count("Moyenne glissante 28 j") == 0
    assert document.count('class="range-label"') == 6
    assert document.count('class="chart-note"') == 6
    assert document.count("Perturbation fournisseur simulée") == 6
    assert "Vue ciblée J0–J480" in document
    assert "Vue ciblée J0–J180" in document
    assert "Ce ne sont pas les probabilités" in document
    assert "La moyenne glissante facilite la lecture" in document
    assert "Une moyenne de stock positive ne garantit pas" in document
    assert "<polygon" not in document
    assert document.count('class="trace"') == 2
    assert document.count('class="solutions-explained"') == 1
    assert "aucune régulation en boucle fermée" in document
    assert "Actions sans régulation" in document
    assert "Plan préparé dès J0" in document
    assert "Configuration à recalibrer" in document
    assert "même état physique au J0" in document
    assert "65,0 %" in document
    assert "430,0 %" in document
    assert "http://" not in document
    assert "https://" not in document
    assert "fetch(" not in document
    assert "<script" not in document
    assert artifacts.index_path.stat().st_size < 500_000
    assert len(list(artifacts.output_dir.iterdir())) == 3
    assert not (artifacts.output_dir / "canonical_cascade_trajectories_long.csv").exists()
    assert manifest["status"] == "complete"
    assert manifest["schema_version"] == "etudecas.industrial_cascade_brief.v2"
    assert manifest["profile"] == "executive_light_static_svg"
    assert manifest["counts"]["static_charts"] == 6
    assert manifest["visualization"]["line_transform"] == "trailing_rolling_mean"
    assert manifest["visualization"]["uses_future_values"] is False
    chart_settings = manifest["visualization"]["charts"]
    assert {
        chart_id: settings["window_days"]
        for chart_id, settings in chart_settings.items()
    } == {
        "quality_stock_021081": 5,
        "quality_production_268967": 7,
        "quality_customer_backlog_268967": 14,
        "delay_stock_338929": 14,
        "delay_production_268091": 7,
        "delay_customer_backlog_268091": 5,
    }
    assert manifest["visualization"]["min_max_bands"].startswith("excluded")
    assert results["quality"]["combined"]["remaining_ratio"] == 0.35
    assert results["scenario_selection"]["ranked_across_network_risks"] is False
    assert results["supplier_risk_forecast"]["primary_subject"] is True
    assert (
        results["supplier_risk_forecast"][
            "incident_occurrence_probability_estimated"
        ]
        is False
    )
    assert (
        results["supplier_risk_forecast"]["scenario_selected_by_supplier_risk_model"]
        is False
    )
    assert (
        results["quality"]["conditional_impact_timeline"]["incident_start_day"]
        == 45
    )
    assert (
        results["delay"]["conditional_impact_timeline"]["incident_start_day"] == 0
    )
    assert results["decision_policy"]["closed_loop_regulation_active"] is False
    assert results["decision_policy"]["daily_feedback_redecision"] is False
    assert results["quality"]["traceability_example"]["exposure_bundle_count"] == 2
    assert results["quality"]["traceability_example"]["finished_lot_count"] == 3
    assert results["quality"]["traceability_example"][
        "other_production_lot_counts"
    ] == {"item:773474": 1}
    assert results["quality"]["traceability_example"]["client_lot_count"] == 4
    assert "demo_dir" not in manifest["source"]
    assert str(tmp_path) not in document
    assert str(tmp_path) not in artifacts.results_path.read_text(encoding="utf-8")
    assert str(tmp_path) not in artifacts.manifest_path.read_text(encoding="utf-8")
    assert all(_digest(path) == digest for path, digest in source_hashes.items())


def test_rejects_a_tampered_compact_source(tmp_path: Path) -> None:
    demo_dir = _fixture(tmp_path)
    compact_path = demo_dir / "data" / "canonical_cascade_trajectories_compact.json"
    compact_path.write_text("{}", encoding="utf-8")

    with pytest.raises(ValueError, match="Empreinte du JSON compact incoherente"):
        build_industrial_brief(
            demo_dir=demo_dir,
            output_dir=tmp_path / "brief",
        )


def test_rejects_a_tampered_traceability_registry(tmp_path: Path) -> None:
    demo_dir = _fixture(tmp_path)
    bundle_path = (
        demo_dir
        / "data"
        / "risk_registry_01"
        / "risk_impact_exposure_bundles.csv"
    )
    bundle_path.write_text("tampered", encoding="utf-8")

    with pytest.raises(ValueError, match="Empreinte du registre incoherente"):
        build_industrial_brief(
            demo_dir=demo_dir,
            output_dir=tmp_path / "brief",
        )


def test_select_series_rejects_duplicates() -> None:
    row = _series("metric", "node", "item", 1.0)
    compact = {
        "cascades": {
            "cascade": {"variants": {"variant": {"series": [row, dict(row)]}}}
        }
    }

    with pytest.raises(ValueError, match="Serie unique attendue"):
        _select_series(
            compact,
            cascade_id="cascade",
            variant_id="variant",
            metric="metric",
            node_id="node",
            item_id="item",
        )


def test_svg_rejects_inconsistent_daily_lengths() -> None:
    row = _series("metric", "node", "item", 1.0)
    row["mean"] = [1.0]

    with pytest.raises(ValueError, match="Longueur invalide"):
        _svg_chart(
            title="Courbe",
            subtitle="Test",
            days=[0, 1, 2, 3, 4],
            series=[{"label": "Serie", "color": "#000", "series": row}],
            incident_window=(1, 2),
            rolling_window=7,
        )


def test_trailing_rolling_mean_never_uses_future_values() -> None:
    assert _trailing_rolling_mean([1, 2, 3, 100], 3) == pytest.approx(
        [1, 1.5, 2, 35]
    )
    with pytest.raises(ValueError, match="fenetre glissante"):
        _trailing_rolling_mean([1, 2], 0)


def test_short_axis_labels_keep_distinct_low_thousands() -> None:
    assert _short_axis_number(1_600) == "1,6 k"
    assert _short_axis_number(2_400) == "2,4 k"
