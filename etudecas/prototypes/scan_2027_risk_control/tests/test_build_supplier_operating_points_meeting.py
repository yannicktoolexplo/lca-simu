from __future__ import annotations

import csv
import base64
import json
from pathlib import Path

import pytest

from etudecas.prototypes.scan_2027_risk_control import (
    build_supplier_operating_points_meeting as module,
)


def _write_fixture(
    path: Path,
    *,
    include_quality: bool = False,
    omit_last: bool = False,
    seeds: tuple[int, ...] = (1,),
    include_exercised_trace: bool = True,
    mismatch_last_seed: bool = False,
    wrong_incident_value: bool = False,
) -> None:
    rows = []
    suppliers = [
        ("S-A", "338929", "M-1810", "268091"),
        ("S-B", "344135", "M-1430", "268967"),
        ("S-C", "029313", "M-1810", "268091"),
        *[
            (
                f"S-{index:02d}",
                f"{100000 + index}",
                "M-1810" if index % 2 else "M-1430",
                "268091" if index % 2 else "268967",
            )
            for index in range(4, 19)
        ],
    ]
    for point_index, (point, rate) in enumerate(
        (("op_100", .999), ("op_93", .93), ("op_80", .80))
    ):
        for supplier_index, (supplier, item, factory, product) in enumerate(suppliers):
            for mechanism in ("transport_delay", "supply_availability"):
                for seed in seeds:
                    rows.append(
                        {
                            "operating_point_id": point,
                            "operating_point_label": point.title(),
                            "realized_global_on_due": rate,
                            "realized_268091_on_due": rate,
                            "realized_268967_on_due": rate,
                            "degradation_family": "test",
                            "degradation_value": point_index,
                            "supplier_id": supplier,
                            "item_id": item,
                            "factory_id": factory,
                            "product_id": product,
                            "incident_mechanism": "quality_hold" if include_quality and not rows else mechanism,
                            "incident_value": (
                                119
                                if (
                                    wrong_incident_value
                                    and point_index == 0
                                    and supplier_index == 0
                                    and mechanism == "transport_delay"
                                    and seed == seeds[0]
                                )
                                else 120
                                if mechanism == "transport_delay"
                                else .5
                            ),
                            "seed": seed,
                            "baseline_service": rate,
                            "incident_service": max(0, rate - (supplier_index + 1) * .01),
                            "service_loss_pp": supplier_index + 1,
                            "backlog_qty_days_delta": 100 * (supplier_index + 1),
                            "production_delta": -10 * (supplier_index + 1),
                            **(
                                {"incident_physically_exercised": True}
                                if include_exercised_trace
                                else {}
                            ),
                            "status": "executed",
                        }
                    )
    if omit_last:
        rows = rows[:-len(seeds)]
    if mismatch_last_seed:
        rows[-1]["seed"] = 999
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    (path.parent / "campaign_manifest.json").write_text(
        json.dumps(
            {
                "status": "complete",
                "detail_row_count": len(rows),
                "row_count_by_operating_point": {
                    point: sum(row["operating_point_id"] == point for row in rows)
                    for point in module.EXPECTED_POINT_IDS
                },
                "lane_count": 18,
                "incident_mechanisms": [
                    "supply_availability",
                    "transport_delay",
                ],
                "seed_ids": list(seeds),
                "same_engine_for_all_108_rows": True,
                "engine_sha256": "a" * 64,
                "quality_branch_included": False,
            }
        ),
        encoding="utf-8",
    )


def _write_cascade_fixture(path: Path) -> None:
    path.write_text("<!doctype html><title>cascade</title>", encoding="utf-8")
    metrics_path = path.parent / "results" / "paired_metrics.csv"
    metrics_path.parent.mkdir()
    with metrics_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=(
                "case",
                "state_dependent_rules_enabled",
                "seed",
            ),
        )
        writer.writeheader()
        writer.writerows(
            [
                {
                    "case": "state_off_nominal",
                    "state_dependent_rules_enabled": False,
                    "seed": 340281,
                },
                {
                    "case": "delay_only_state_off",
                    "state_dependent_rules_enabled": False,
                    "seed": 340281,
                },
                {
                    "case": "state_only",
                    "state_dependent_rules_enabled": True,
                    "seed": 340281,
                },
                {
                    "case": "state_plus_delay",
                    "state_dependent_rules_enabled": True,
                    "seed": 340281,
                },
            ]
        )
    (path.parent / "state_cascade_summary.json").write_text(
        json.dumps(
            {
                "status": "complete",
                "files": {"metrics": "results/paired_metrics.csv"},
                "pair_results": {
                    "service_loss_points_state_off": 31.339856,
                    "service_loss_points_state_on": 34.280286,
                    "service_loss_amplification_points": 2.94043,
                    "backlog_amplification_qty_days": 13984221.796191,
                    "production_loss_amplification_qty": 115200.0,
                    "finished_product_lots_with_primary_or_incremental_signal_ancestry": 251,
                },
            }
        ),
        encoding="utf-8",
    )


def test_builds_three_view_single_offline_html(tmp_path: Path) -> None:
    results = tmp_path / "results.csv"
    source_map = tmp_path / "map.html"
    output = tmp_path / "meeting.html"
    _write_fixture(results)
    source_map.write_text("<!doctype html><title>map</title><p>network</p>", encoding="utf-8")
    before = source_map.read_bytes()
    manifest = module.build_meeting_html(
        results_csv=results,
        map_html=source_map,
        output_html=output,
    )
    document = output.read_text(encoding="utf-8")
    assert manifest["view_count"] == 3
    assert manifest["offline_single_file"] is True
    assert len(manifest["operating_points"]) == 3
    assert manifest["paired_seed_ids"] == [1]
    assert len(manifest["chains"]) == 18
    assert "Les mêmes chaînes fournisseur ressortent-elles" in document
    assert "Pire effet parmi les deux hypothèses" in document
    assert "critique" not in document.casefold()
    assert "classement" not in document.casefold()
    assert "prévoit" not in document.casefold()
    assert "embedded-map" in document
    assert source_map.read_bytes() == before


def test_embeds_optional_state_dependent_cascade(tmp_path: Path) -> None:
    results = tmp_path / "results.csv"
    source_map = tmp_path / "map.html"
    cascade = tmp_path / "cascade.html"
    output = tmp_path / "meeting.html"
    _write_fixture(results)
    source_map.write_text("<!doctype html><title>map</title>", encoding="utf-8")
    _write_cascade_fixture(cascade)
    before = cascade.read_bytes()
    manifest = module.build_meeting_html(
        results_csv=results,
        map_html=source_map,
        cascade_html=cascade,
        output_html=output,
    )
    document = output.read_text(encoding="utf-8")
    assert manifest["has_state_dependent_cascade"] is True
    assert manifest["sources"]["cascade_file"] == "cascade.html"
    assert manifest["state_cascade"]["service_loss_amplification_points"] == pytest.approx(
        2.94043
    )
    assert "cascade.service_loss_points_state_off" in document
    assert "cascade.finished_product_lots_with_primary_or_incremental_signal_ancestry" in document
    assert base64.b64encode(before).decode("ascii") in document
    assert cascade.read_bytes() == before


def test_allows_explicitly_labelled_one_pass_exploration(tmp_path: Path) -> None:
    results = tmp_path / "results.csv"
    source_map = tmp_path / "map.html"
    output = tmp_path / "meeting.html"
    _write_fixture(results, seeds=(7,))
    source_map.write_text("<!doctype html><title>map</title>", encoding="utf-8")
    manifest = module.build_meeting_html(
        results_csv=results,
        map_html=source_map,
        output_html=output,
    )
    assert manifest["paired_seed_ids"] == [7]
    assert "une seule répétition commune" in output.read_text(encoding="utf-8")


def test_rejects_incomplete_matrix(tmp_path: Path) -> None:
    results = tmp_path / "results.csv"
    source_map = tmp_path / "map.html"
    _write_fixture(results, omit_last=True)
    source_map.write_text("<html></html>", encoding="utf-8")
    with pytest.raises(ValueError, match="exactly 108 rows"):
        module.build_meeting_html(
            results_csv=results,
            map_html=source_map,
            output_html=tmp_path / "out.html",
        )


def test_rejects_excluded_quality_branch(tmp_path: Path) -> None:
    results = tmp_path / "results.csv"
    source_map = tmp_path / "map.html"
    _write_fixture(results, include_quality=True)
    source_map.write_text("<html></html>", encoding="utf-8")
    with pytest.raises(ValueError, match="Excluded business branch"):
        module.build_meeting_html(
            results_csv=results,
            map_html=source_map,
            output_html=tmp_path / "out.html",
        )


def test_refuses_overwrite(tmp_path: Path) -> None:
    results = tmp_path / "results.csv"
    source_map = tmp_path / "map.html"
    output = tmp_path / "out.html"
    _write_fixture(results)
    source_map.write_text("<html></html>", encoding="utf-8")
    output.write_text("keep", encoding="utf-8")
    with pytest.raises(FileExistsError):
        module.build_meeting_html(
            results_csv=results,
            map_html=source_map,
            output_html=output,
        )


def test_fails_closed_without_comparable_campaign_manifest(tmp_path: Path) -> None:
    results = tmp_path / "results.csv"
    source_map = tmp_path / "map.html"
    _write_fixture(results)
    (tmp_path / "campaign_manifest.json").unlink()
    source_map.write_text("<html></html>", encoding="utf-8")
    with pytest.raises(FileNotFoundError, match="campaign_manifest.json"):
        module.build_meeting_html(
            results_csv=results,
            map_html=source_map,
            output_html=tmp_path / "out.html",
        )


def test_fails_closed_when_engine_comparability_is_not_true(tmp_path: Path) -> None:
    results = tmp_path / "results.csv"
    source_map = tmp_path / "map.html"
    _write_fixture(results)
    manifest_path = tmp_path / "campaign_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["same_engine_for_all_108_rows"] = None
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    source_map.write_text("<html></html>", encoding="utf-8")
    with pytest.raises(ValueError, match="same_engine_for_all_108_rows=true"):
        module.build_meeting_html(
            results_csv=results,
            map_html=source_map,
            output_html=tmp_path / "out.html",
        )


def test_rejects_missing_physical_exercise_trace(tmp_path: Path) -> None:
    results = tmp_path / "results.csv"
    source_map = tmp_path / "map.html"
    _write_fixture(results, include_exercised_trace=False)
    source_map.write_text("<html></html>", encoding="utf-8")
    with pytest.raises(ValueError, match="incident_physically_exercised"):
        module.build_meeting_html(
            results_csv=results,
            map_html=source_map,
            output_html=tmp_path / "out.html",
        )


def test_rejects_mismatched_seed_between_cells(tmp_path: Path) -> None:
    results = tmp_path / "results.csv"
    source_map = tmp_path / "map.html"
    _write_fixture(results, mismatch_last_seed=True)
    source_map.write_text("<html></html>", encoding="utf-8")
    with pytest.raises(ValueError, match="same paired seed set"):
        module.build_meeting_html(
            results_csv=results,
            map_html=source_map,
            output_html=tmp_path / "out.html",
        )


def test_rejects_hard_coded_incident_label_with_wrong_value(tmp_path: Path) -> None:
    results = tmp_path / "results.csv"
    source_map = tmp_path / "map.html"
    _write_fixture(results, wrong_incident_value=True)
    source_map.write_text("<html></html>", encoding="utf-8")
    with pytest.raises(ValueError, match="Unexpected delay incident value"):
        module.build_meeting_html(
            results_csv=results,
            map_html=source_map,
            output_html=tmp_path / "out.html",
        )
