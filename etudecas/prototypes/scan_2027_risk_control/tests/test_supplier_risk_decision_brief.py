from __future__ import annotations

import csv
import json
import math
from pathlib import Path

import pytest

from etudecas.prototypes.scan_2027_risk_control.supplier_risk_calibration_campaign import (
    build_candidate_floors,
    build_candidate_graph,
)
from etudecas.prototypes.scan_2027_risk_control.supplier_risk_decision_brief import (
    REPO_ROOT,
    bundle_offline_views,
    json_safe,
    real_2025_metrics,
    response_curve_rows,
    service_metrics,
    supplier_decision_table,
    sensitivity_ranking,
    target_lever_analysis,
)


def _write_csv(path: Path, fields: list[str], rows: list[dict[str, object]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def test_service_metrics_separates_horizon_fill_from_due_date_proxy(tmp_path: Path) -> None:
    path = tmp_path / "service.csv"
    fields = [
        "day",
        "node_id",
        "item_id",
        "demand_qty",
        "required_with_backlog_qty",
        "served_qty",
        "backlog_end_qty",
    ]
    _write_csv(
        path,
        fields,
        [
            {
                "day": 0,
                "node_id": "C1",
                "item_id": "item:P",
                "demand_qty": 10,
                "required_with_backlog_qty": 10,
                "served_qty": 0,
                "backlog_end_qty": 10,
            },
            {
                "day": 1,
                "node_id": "C1",
                "item_id": "item:P",
                "demand_qty": 10,
                "required_with_backlog_qty": 20,
                "served_qty": 15,
                "backlog_end_qty": 5,
            },
        ],
    )

    result = service_metrics(path)["item:P"]

    assert result["fill_rate"] == pytest.approx(0.75)
    assert result["on_due_date_volume_proxy"] == pytest.approx(0.25)
    assert result["backlog_days"] == 2
    assert result["ending_backlog"] == pytest.approx(5)
    assert result["max_backlog"] == pytest.approx(10)


def test_target_analysis_keeps_capacity_bracket_and_demand_stress_separate() -> None:
    cases = [
        {
            "case_id": "oat2/m1430_capacity_0p18",
            "fill_268967": 0.70,
        },
        {
            "case_id": "oat2/m1430_capacity_0p20",
            "fill_268967": 0.835,
        },
        {
            "case_id": "oat3/m1430cap020_demand268967_1p04",
            "fill_268967": 0.804,
        },
        {
            "case_id": "oat3/lead338929_0p88",
            "fill_268091": 0.934,
        },
    ]

    result = target_lever_analysis(cases)

    assert result["268967"]["capacity_only_lower_bracket"]["fill_268967"] == 0.70
    assert result["268967"]["capacity_only_upper_bracket"]["fill_268967"] == 0.835
    assert result["268967"]["closest_demand_stress_case"]["fill_268967"] == 0.804
    assert result["target_definition_confirmed"] is False


def test_response_curve_rows_classifies_product_specific_levers() -> None:
    base = {
        "fill_268091": 0.93,
        "fill_268967": 0.80,
        "on_due_date_volume_proxy_268091": 0.85,
        "on_due_date_volume_proxy_268967": 0.79,
        "backlog_days_268091": 4,
        "backlog_days_268967": 5,
    }
    rows = response_curve_rows(
        [
            {**base, "case_id": "oat3/lead338929_0p88"},
            {**base, "case_id": "oat2/m1430_capacity_0p20"},
            {**base, "case_id": "oat2/338929_stock_50000"},
            {**base, "case_id": "oat/oat_M1810_capacity_3p00"},
            {**base, "case_id": "unrelated"},
        ]
    )

    assert len(rows) == 4
    assert {row["product"] for row in rows} == {"268091", "268967"}
    lead = next(row for row in rows if row["lever"] == "Delai du composant 338929")
    assert lead["level"] == pytest.approx(0.88)


def test_floor_builder_scales_both_engine_capacity_columns(tmp_path: Path) -> None:
    source = tmp_path / "source.csv"
    destination = tmp_path / "candidate.csv"
    fields = [
        "supplier_id",
        "item_id",
        "dst_node_id",
        "neutral_capacity_floor_qty_per_day",
        "tested_capacity_floor_qty_per_day",
    ]
    _write_csv(
        source,
        fields,
        [
            {
                "supplier_id": "SDC-VD1",
                "item_id": "item:A",
                "dst_node_id": "M-1430",
                "neutral_capacity_floor_qty_per_day": 100,
                "tested_capacity_floor_qty_per_day": 250,
            },
            {
                "supplier_id": "SDC-VD2",
                "item_id": "item:B",
                "dst_node_id": "M-1810",
                "neutral_capacity_floor_qty_per_day": 80,
                "tested_capacity_floor_qty_per_day": 200,
            },
        ],
    )

    audit = build_candidate_floors(source, destination, capacity_scale=0.2)
    rows = list(csv.DictReader(destination.open("r", encoding="utf-8")))

    assert audit["positive_capacity_lane_count"] == 1
    assert float(rows[0]["neutral_capacity_floor_qty_per_day"]) == pytest.approx(20)
    assert float(rows[0]["tested_capacity_floor_qty_per_day"]) == pytest.approx(50)
    assert float(rows[1]["tested_capacity_floor_qty_per_day"]) == pytest.approx(200)


def test_candidate_graph_changes_only_scoped_lead_and_demand(tmp_path: Path) -> None:
    source = tmp_path / "source.json"
    destination = tmp_path / "candidate.json"
    source.write_text(
        json.dumps(
            {
                "edges": [
                    {
                        "from": "SDC-VD0914360C",
                        "to": "M-1810",
                        "items": ["item:338929"],
                        "lead_time": {"mean": 42},
                    },
                    {
                        "from": "OTHER",
                        "to": "M-1810",
                        "items": ["item:X"],
                        "lead_time": {"mean": 10},
                    },
                ],
                "scenarios": [
                    {
                        "demand": [
                            {
                                "item_id": "item:268967",
                                "profile": [
                                    {"points": [{"t": 0, "value": 100}]}
                                ],
                            }
                        ]
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    audit = build_candidate_graph(
        source,
        destination,
        lead_scale=0.88,
        demand_scale=1.04,
    )
    graph = json.loads(destination.read_text(encoding="utf-8"))

    assert audit == {
        "lead_lane_count": 1,
        "demand_profile_count": 1,
        "demand_point_count": 1,
    }
    assert graph["edges"][0]["lead_time"]["mean"] == pytest.approx(36.96)
    assert graph["edges"][1]["lead_time"]["mean"] == 10
    assert graph["scenarios"][0]["demand"][0]["profile"][0]["points"][0][
        "value"
    ] == pytest.approx(104)


def test_real_2025_mapping_and_totals_are_stable() -> None:
    result = real_2025_metrics(REPO_ROOT)
    by_product = {row["product"]: row for row in result["products"]}

    assert by_product["268091"]["family"] == "Cosmétique"
    assert by_product["268091"]["factory"] == "M-1810"
    assert by_product["268967"]["family"] == "Pharma"
    assert by_product["268967"]["factory"] == "M-1430"
    assert result["total_ca_lost_2025"] == pytest.approx(2_693_384.81302)
    assert by_product["268091"]["ca_service_rate"] == pytest.approx(0.9287255, rel=1e-6)
    assert by_product["268967"]["ca_service_rate"] == pytest.approx(0.9539847, rel=1e-6)
    assert by_product["268967"]["target_definition_confirmed"] is False


def test_supplier_table_distinguishes_missing_from_zero_effect() -> None:
    graph = (
        REPO_ROOT
        / "etudecas"
        / "simulation_prep"
        / "result"
        / "reference_baseline"
        / "_mrp_bom_tests"
        / "bom_weekly_mps_lotified_no_static_fallback_physical_floor.json"
    )
    ranking, _meta = sensitivity_ranking(REPO_ROOT)
    result = supplier_decision_table(REPO_ROOT, graph, ranking)

    assert all(row["supplier_id"] != "SDC-1450" for row in result["rows"])
    untested = [row for row in result["rows"] if not row["conditional_consequence_tested"]]
    assert untested
    assert all(row["conditional_fill_drop_tested"] is None for row in untested)
    assert any(row["stock_coverage_days"] is None for row in result["rows"])
    assert result["occurrence_probability_calibrated"] is False


def test_json_safe_replaces_non_finite_values() -> None:
    result = json_safe({"nan": math.nan, "inf": math.inf, "ok": 1.5})

    assert result == {"nan": None, "inf": None, "ok": 1.5}


def test_bundle_offline_views_keeps_sources_and_local_dependencies(
    tmp_path: Path,
) -> None:
    sources = tmp_path / "sources"
    sources.mkdir()
    network_map = sources / "carte_reseau.html"
    quality_map = sources / "carte_qualite.html"
    delay_map = sources / "carte_retard.html"
    stress_test = sources / "stress.html"
    plotly = sources / "plotly-2.32.0.min.js"
    topojson = sources / "world_110m.json"
    network_source = (
        '<!doctype html><html><head><script src="plotly-2.32.0.min.js">'
        "</script></head><body>map</body></html>"
    )
    stress_source = "<!doctype html><html><body>stress</body></html>"
    network_map.write_text(network_source, encoding="utf-8")
    aligned_map_source = (
        '<!doctype html><html><head><script src="https://cdn.plot.ly/'
        'plotly-2.32.0.min.js"></script></head><body>aligned</body></html>'
    )
    quality_map.write_text(aligned_map_source, encoding="utf-8")
    delay_map.write_text(aligned_map_source, encoding="utf-8")
    stress_test.write_text(stress_source, encoding="utf-8")
    plotly.write_text("window.Plotly = {};", encoding="utf-8")
    topojson.write_text('{"type":"Topology"}', encoding="utf-8")

    outputs = bundle_offline_views(
        tmp_path / "package",
        network_map_html=network_map,
        network_map_plotly=plotly,
        network_map_topojson=topojson,
        stress_test_html=stress_test,
        quality_risk_map_html=quality_map,
        delay_risk_map_html=delay_map,
    )

    by_name = {path.name: path for path in outputs}
    bundled_map = by_name["carte_reseau_lots.html"].read_text(encoding="utf-8")
    bundled_stress = by_name["stress_tests_incidents_lots.html"].read_text(
        encoding="utf-8"
    )
    assert 'src="plotly-2.32.0.min.js"' in bundled_map
    assert 'href="../index.html#access"' in bundled_map
    assert 'href="../index.html#cascades"' in bundled_stress
    for name in (
        "carte_qualite_incident_lots.html",
        "carte_retard_338929_incident_lots.html",
    ):
        aligned_map = by_name[name].read_text(encoding="utf-8")
        assert 'src="plotly-2.32.0.min.js"' in aligned_map
        assert "https://cdn.plot.ly" not in aligned_map
        assert 'href="../index.html#access"' in aligned_map
        assert "data:application/json;base64," in aligned_map
    assert by_name["plotly-2.32.0.min.js"].exists()
    assert by_name["world_110m.json"].exists()
    assert network_map.read_text(encoding="utf-8") == network_source
    assert quality_map.read_text(encoding="utf-8") == aligned_map_source
    assert delay_map.read_text(encoding="utf-8") == aligned_map_source
    assert stress_test.read_text(encoding="utf-8") == stress_source
