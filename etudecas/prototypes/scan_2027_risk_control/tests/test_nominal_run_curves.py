from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from etudecas.prototypes.scan_2027_risk_control import nominal_run_curves as subject


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as target:
        writer = csv.DictWriter(target, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def _fixture_replay(tmp_path: Path) -> tuple[Path, Path, subject.ChainSpec]:
    replay = tmp_path / "replay"
    summary = {
        "input_sha256": "input-digest",
        "scenario_id": subject.EXPECTED_SCENARIO_ID,
        "sim_days": subject.EXPECTED_HORIZON_DAYS,
        "warmup_days": subject.EXPECTED_WARMUP_DAYS,
        "policy": {
            "seed": subject.EXPECTED_SEED,
            "supplier_risk": {"enabled": False, "event_count": 0},
            "supplier_state_dependent_risk": {
                "enabled": False,
                "generated_event_count": 0,
            },
        },
        "counts": {"nodes": 3},
        "production_tracking": {"actual": 1},
        "kpis": {"fill_rate": 1.0},
    }
    summary_path = replay / "summaries" / "first_simulation_summary.json"
    summary_path.parent.mkdir(parents=True)
    summary_path.write_text(json.dumps(summary), encoding="utf-8")
    expected_path = tmp_path / "expected.json"
    expected_path.write_text(json.dumps(summary), encoding="utf-8")
    chain = subject.ChainSpec(
        key="component_product",
        label="Composant vers produit",
        supplier_id="SUP-1",
        site_id="SITE-1",
        component_id="item:COMP-1",
        product_id="item:PROD-1",
        customer_id="CLIENT-1",
    )
    days = range(subject.EXPECTED_HORIZON_DAYS)
    _write_csv(
        replay / "data" / "production_input_stocks_daily.csv",
        [
            {
                "day": day,
                "node_id": chain.site_id,
                "item_id": chain.component_id,
                "stock_end_of_day": 100 - (day % 10),
            }
            for day in days
        ],
    )
    _write_csv(
        replay / "data" / "production_input_replenishment_arrivals_daily.csv",
        [
            {
                "day": day,
                "node_id": chain.site_id,
                "item_id": chain.component_id,
                "arrived_qty": 3,
            }
            for day in days
        ],
    )
    shipment_rows = [
        {
            "day": day,
            "src_node_id": chain.supplier_id,
            "dst_node_id": chain.site_id,
            "item_id": chain.component_id,
            "shipped_qty": 1,
        }
        for day in days
    ]
    shipment_rows.append(
        {
            "day": 10,
            "src_node_id": chain.supplier_id,
            "dst_node_id": chain.site_id,
            "item_id": chain.component_id,
            "shipped_qty": 2,
        }
    )
    _write_csv(
        replay / "data" / "production_supplier_shipments_daily.csv",
        shipment_rows,
    )
    _write_csv(
        replay / "data" / "production_output_products_daily.csv",
        [
            {
                "day": day,
                "node_id": chain.site_id,
                "item_id": chain.product_id,
                "released_qty": 4,
                "stock_end_of_day": 20,
            }
            for day in days
        ],
    )
    _write_csv(
        replay / "data" / "production_demand_service_daily.csv",
        [
            {
                "day": day,
                "node_id": chain.customer_id,
                "item_id": chain.product_id,
                "demand_qty": 4,
                "served_qty": 4,
                "backlog_end_qty": 0,
            }
            for day in days
        ],
    )
    return replay, expected_path, chain


def test_build_payload_keeps_complete_daily_states_and_aggregates_flows(
    tmp_path: Path,
) -> None:
    replay, expected, chain = _fixture_replay(tmp_path)

    payload = subject.build_nominal_run_curves_payload(
        replay,
        expected_summary_path=expected,
        chains=(chain,),
    )

    assert payload["available"] is True
    assert payload["supplier_incident_enabled"] is False
    assert payload["supplier_state_dependent_risk_enabled"] is False
    assert payload["chain_count"] == 1
    actual = payload["chains"][0]
    assert len(actual["days"]) == subject.EXPECTED_HORIZON_DAYS
    assert all(
        len(values) == subject.EXPECTED_HORIZON_DAYS
        for values in actual["series"].values()
    )
    assert actual["series"]["component_shipments"][10] == 3
    assert actual["summary"]["customer_service_rate_pct"] == 100
    assert (
        len(subject.compact_trajectory_rows(payload)) == subject.EXPECTED_HORIZON_DAYS
    )


def test_build_payload_rejects_state_risk_enabled(tmp_path: Path) -> None:
    replay, expected, chain = _fixture_replay(tmp_path)
    summary_path = replay / "summaries" / "first_simulation_summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    summary["policy"]["supplier_state_dependent_risk"]["enabled"] = True
    summary_path.write_text(json.dumps(summary), encoding="utf-8")

    with pytest.raises(subject.NominalRunCurvesError, match="référence nominale"):
        subject.build_nominal_run_curves_payload(
            replay,
            expected_summary_path=expected,
            chains=(chain,),
        )


def test_injection_is_additive_and_idempotence_is_rejected() -> None:
    document = """<!doctype html><html><head><script>window.Plotly={};</script></head>
<body><button id="existingTab">Onglet existant</button>
<button id="kpiTreeBtn" type="button">Arbres KPI</button>
<button id="scenarioComparisonBtn" type="button">Comparer scenarios</button></body></html>"""
    payload = {
        "available": True,
        "chains": [
            {
                "key": "a",
                "label": "A",
                "supplier_id": "S",
                "site_id": "M",
                "component_id": "1",
                "product_id": "2",
                "days": [0],
                "series": {
                    "component_stock": [1],
                    "component_shipments": [1],
                    "component_receipts": [1],
                    "product_released": [1],
                    "product_stock": [1],
                    "customer_demand": [1],
                    "customer_served": [1],
                    "customer_backlog": [0],
                },
                "summary": {
                    "customer_service_rate_pct": 100,
                    "customer_backlog_max": 0,
                    "component_stock_min": 1,
                    "component_stock_zero_days": 0,
                    "product_released_total": 1,
                },
            }
        ],
    }

    injected = subject.inject_nominal_run_curves(document, payload)

    assert '<button id="existingTab">Onglet existant</button>' in injected
    assert subject.BUTTON_ID in injected
    assert subject.MODAL_ID in injected
    assert injected.count(subject.INJECTION_MARKER) == 4
    assert "une seule réalisation nominale illustrative" in injected
    assert "Adapté" in injected
    assert "Brut" in injected
    with pytest.raises(subject.NominalRunCurvesError, match="déjà injectées"):
        subject.inject_nominal_run_curves(injected, payload)


def test_real_replay_contract_when_available() -> None:
    replay = Path(
        r"C:\dev\lca-simu-pr40-validation-artifacts-20260726\supplier_network_nominal_trajectory_replay_20260904_v1"
    )
    expected = Path(
        r"C:\dev\lca-simu-pr40-validation-artifacts-20260726\supplier_network_risk_screen_20260902_v2\cases\baseline_nominal\seed_340281\summaries\first_simulation_summary.json"
    )
    if not replay.is_dir() or not expected.is_file():
        pytest.skip("Replay nominal externe indisponible.")

    payload = subject.build_nominal_run_curves_payload(
        replay,
        expected_summary_path=expected,
    )

    assert payload["horizon_days"] == 720
    assert payload["chain_count"] == 2
    assert len(subject.compact_trajectory_rows(payload)) == 1440
    assert {chain["key"] for chain in payload["chains"]} == {
        "338929_268091",
        "344135_268967",
    }
