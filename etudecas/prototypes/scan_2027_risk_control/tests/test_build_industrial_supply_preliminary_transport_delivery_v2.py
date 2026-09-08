from __future__ import annotations

import csv
import json
import re
from pathlib import Path

import pytest

from etudecas.prototypes.scan_2027_risk_control import (
    build_industrial_supply_preliminary_transport_delivery_v2 as delivery,
)


def _json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _detail_rows(item_id: str, slot: int, expected: dict) -> list[dict]:
    case_id = f"causal_lot__slot{slot}__sdc_fixture_{item_id}_m_1810__transport_delay"
    common = {
        "extension": delivery.LOT_EXTENSION,
        "case_key": f"{delivery.LOT_EXTENSION}::{case_id}::seed_340282",
        "case_id": case_id,
        "seed": 340282,
        "failure_mode": delivery.INCLUDED_FAILURE_MODE,
        "stress_start_day": 44,
        "stress_end_day": 223,
        "chain_ids": f"chain-{item_id}",
        "supplier_ids": f"SUP-{item_id}",
        "genealogy_depth": "",
        "item_id": f"item:{item_id}",
        "event_id": "",
        "day": 100,
        "risk_event_ids": "risk-1",
        "shipment_id": "",
        "production_campaign_id": "",
        "source_type": "lane_receipt",
        "source_id": "fixture",
        "descendant_quantity_is_exposure_upper_bound": True,
        "causal_delay_or_loss_claimed": False,
        "counterfactual_entity_identity_validated": False,
        "industrial_lot_number_claimed": False,
        "lot_identifier_semantics": (
            "identifiant_technique_simule_pas_numero_lot_industriel"
        ),
    }
    rows: list[dict] = []
    root_qty = expected["root_qty"] / expected["root_count"]
    for index in range(expected["root_count"]):
        rows.append(
            {
                **common,
                "lot_id": f"LOT-{item_id}-R-{index}",
                "exposure_role": "risk_tagged_usable_receipt_root",
                "node_id": "M-1810",
                "event_type": "lane_receipt",
                "qty": root_qty,
                "uom": expected["root_uom"],
            }
        )
    for kind, count, node, event_type in (
        ("P", expected["production_count"], "M-1810", "production_output"),
        ("D", expected["platform_count"], "DC-1920", "lane_receipt"),
        ("C", expected["client_count"], "C-XXXXX", "lane_receipt"),
    ):
        for index in range(count):
            rows.append(
                {
                    **common,
                    "lot_id": f"LOT-{item_id}-{kind}-{index}",
                    "exposure_role": "genealogical_descendant",
                    "genealogy_depth": 1,
                    "node_id": node,
                    "item_id": "item:268091",
                    "event_type": event_type,
                    "qty": 1.0,
                    "uom": "UN",
                }
            )
    return rows


def _fixture(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, Path]:
    roots = {
        name: tmp_path / name
        for name in ("preliminary", "observed", "regime", "actions")
    }
    for root in roots.values():
        root.mkdir()
    _json(
        roots["preliminary"] / delivery.base.preliminary_audit.MANIFEST_FILE,
        {"checkpoint_signature": "checkpoint-15"},
    )
    _json(
        roots["preliminary"] / delivery.base.preliminary_audit.AUDIT_FILE,
        {"preliminary_not_final": True},
    )
    effects: list[dict] = []
    lots: list[dict] = []
    details: list[dict] = []
    boundary: list[dict] = []
    for slot, (item_id, expected) in enumerate(delivery.EXPECTED_ITEMS.items(), 1):
        destination = "m_1430" if item_id == "344135" else "m_1810"
        effect_base = {
            "extension": delivery.INCLUDED_EXTENSION,
            "case_id": (
                f"four_causes__slot{slot}__sdc_fixture_{item_id}_{destination}"
            ),
            "product_id": "268967" if item_id == "344135" else "268091",
            "paired_seed_count": 15,
            "stress_start_day": 44,
            "stress_end_day": 223,
            "min_service_delta_percentage_points": expected["min_service"],
            "max_service_delta_percentage_points": expected["max_service"],
            "mean_backlog_delta_days_per_demand_unit": expected["mean_backlog"],
        }
        effects.append(
            {
                **effect_base,
                "case_id": effect_base["case_id"] + "__transport_delay",
                "failure_mode": "transport_delay",
                "mean_service_delta_percentage_points": expected["mean_service"],
            }
        )
        effects.append(
            {
                **effect_base,
                "case_id": effect_base["case_id"] + "__supply_availability",
                "failure_mode": "supply_availability",
                "mean_service_delta_percentage_points": 0.0,
                "min_service_delta_percentage_points": 0.0,
                "max_service_delta_percentage_points": 0.0,
            }
        )
        item_details = _detail_rows(item_id, slot, expected)
        details.extend(item_details)
        lot_case = item_details[0]["case_key"]
        lots.append(
            {
                "case_key": lot_case,
                "supplier_id": f"SUP-{item_id}",
                "chain_id": f"chain-{item_id}",
                "item_id": f"item:{item_id}",
                "target_product_id": (
                    "268967" if item_id == "344135" else "268091"
                ),
                "genealogical_exposed_lot_count": len(item_details),
            }
        )
        boundary.append(
            {
                "supplier_id": f"SUP-{item_id}",
                "driver_chain_id": f"chain-{item_id}",
                "driver_failure_mode": "transport_delay",
                "group_is_unordered": True,
            }
        )
    # Reuse 356 identifiers in a different scenario, matching the global
    # 2,231 records / 1,875 distinct identifiers contract without duplicating
    # an identifier inside one scenario.
    first_case_ids = [row["lot_id"] for row in details[:356]]
    first_expected = next(iter(delivery.EXPECTED_ITEMS.values()))
    second_case_start = sum(
        int(first_expected[field])
        for field in (
            "root_count",
            "production_count",
            "platform_count",
            "client_count",
        )
    )
    for index, lot_id in enumerate(first_case_ids):
        details[second_case_start + index]["lot_id"] = lot_id
    # The signed broad source may contain other rows; the v2 output must not copy them.
    effects.append(
        {
            **effects[0],
            "case_id": "excluded-source-row",
            "failure_mode": "quality_hold",
        }
    )
    _csv(
        roots["preliminary"] / delivery.base.preliminary_audit.EFFECTS_FILE,
        effects,
    )
    _csv(
        roots["preliminary"] / delivery.base.preliminary_audit.LOT_SUMMARY_FILE,
        lots,
    )
    _csv(
        roots["preliminary"] / delivery.base.preliminary_audit.LOT_DETAIL_FILE,
        details,
    )
    _csv(
        roots["preliminary"] / delivery.base.preliminary_audit.BOUNDARY_FILE,
        boundary,
    )
    monkeypatch.setattr(
        delivery.base.preliminary_audit,
        "validate_preliminary_package",
        lambda root: {"status": "valid"},
    )

    _json(roots["observed"] / "manifest.json", {"status": "complete"})
    _json(roots["observed"] / "bilan_observed_2025.json", {"source": "fixture"})
    observed = {
        "ca_summary": [
            {
                "product_code": "268091",
                "delivered_share_of_raw_potential": 0.9287,
                "ca_lost_positive_only_source_value": 1_611_220,
            }
        ],
        "supplier_risk_prediction_readiness": {
            "industrial_probability_status": "NOT_READY"
        },
    }
    monkeypatch.setattr(delivery.base, "_validate_observed", lambda root: observed)

    _json(roots["regime"] / "calibration_plan.json", {"source": "fixture"})
    _json(roots["regime"] / "input_inventory.json", {"source": "fixture"})
    monkeypatch.setattr(
        delivery.base,
        "_validate_regime_plan",
        lambda root: {"plan_signature": "regime-v2", "screening_candidate_count": 36},
    )

    _json(
        roots["actions"] / "exploratory_action_protocol_manifest.json",
        {"source": "fixture"},
    )
    _json(roots["actions"] / "scientific_controls.json", {"source": "fixture"})
    _csv(roots["actions"] / "action_lever_parameters.csv", [{"source": "fixture"}])
    action_rows = [
        {
            "lever_id": "prepositioned_free_stock_14d",
            "item_id": f"item:{item_id}",
            "buffer_rounded_qty": expected["root_qty"],
            "buffer_uom": expected["root_uom"],
        }
        for item_id, expected in delivery.EXPECTED_ITEMS.items()
    ]
    monkeypatch.setattr(
        delivery.base,
        "_validate_action_plan",
        lambda root: ({"protocol_signature": "actions-v5"}, action_rows),
    )

    map_source = tmp_path / "network_source.html"
    map_source.write_text(
        '<!doctype html><html><head><meta charset="utf-8">'
        f'<script src="{delivery.PLOTLY_CDN}"></script></head>'
        '<body><select><option value="quality">Qualite</option>'
        "<option>Transport</option></select><div id='map'></div></body></html>",
        encoding="utf-8",
    )
    plotly = tmp_path / "plotly.min.js"
    plotly.write_text('window.Plotly={};window.decoder="\ufffd";', encoding="utf-8")
    roots["map"] = map_source
    roots["plotly"] = plotly
    return roots


def test_builds_additive_three_view_transport_delivery(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    roots = _fixture(tmp_path, monkeypatch)
    before = {
        path: delivery.base._sha256(path)
        for root in roots.values()
        for path in ([root] if root.is_file() else root.rglob("*"))
        if path.is_file()
    }
    output = tmp_path / "delivery-v2"
    manifest = delivery.build_delivery(
        preliminary_dir=roots["preliminary"],
        observed_dir=roots["observed"],
        regime_plan_dir=roots["regime"],
        action_plan_dir=roots["actions"],
        map_source=roots["map"],
        plotly_js=roots["plotly"],
        output_dir=output,
    )
    assert delivery.validate_delivery(output) == manifest
    assert manifest["view_count"] == 3
    assert manifest["lot_detail_record_count"] == 2231
    assert manifest["root_receipt_record_count"] == 338
    assert manifest["downstream_record_count"] == 1893
    assert manifest["distinct_simulated_lot_id_count"] == 1875
    assert manifest["map_external_resource_count"] == 0
    assert manifest["engine_executed_by_builder"] is False
    assert all(delivery.base._sha256(path) == digest for path, digest in before.items())
    assert not (output / "assets" / "quality_lot_source.html").exists()
    assert not (output / "assets" / "preliminary_15_of_30").exists()
    assert (output / delivery.VIEW_FILES[1]).is_file()
    map_text = (output / delivery.MAP_ASSET).read_text(encoding="utf-8")
    assert delivery.PLOTLY_CDN not in map_text
    assert "window.Plotly={};" in map_text
    assert "\ufffd" not in map_text
    assert r"\uFFFD" in map_text
    launcher = (output / delivery.LAUNCHER_FILE).read_text(encoding="utf-8")
    assert sum(f'href="{name}"' in launcher for name in delivery.VIEW_FILES) == 3
    assert not delivery.LAUNCHER_MANIFEST_FORBIDDEN.search(launcher)
    manifest_text = (output / delivery.MANIFEST_FILE).read_text(encoding="utf-8")
    assert not delivery.LAUNCHER_MANIFEST_FORBIDDEN.search(manifest_text)
    for path in output.rglob("*"):
        if path.is_file() and path.suffix in {".html", ".csv"}:
            document = path.read_text(encoding="utf-8")
            assert not delivery.USER_FORBIDDEN.search(document)
            assert not re.search(r"2[\s\u00a0]*231\s+lots", document, re.IGNORECASE)
    incident_page = (output / delivery.VIEW_FILES[1]).read_text(encoding="utf-8")
    assert "2 231 enregistrements techniques de filiation" in incident_page
    assert "338 réceptions racines" in incident_page
    assert "1 893 enregistrements aval" in incident_page
    assert "1 875 identifiants" in incident_page


def test_business_summary_matches_the_four_verified_transport_cases(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    roots = _fixture(tmp_path, monkeypatch)
    _, effects, lots, details, _ = delivery._validate_and_load_preliminary(
        roots["preliminary"]
    )
    rows = delivery._build_incident_rows(effects, lots, details)
    assert [row["item_id"] for row in rows] == list(delivery.EXPECTED_ITEMS)
    assert sum(row["genealogical_exposure_record_count"] for row in rows) == 2231
    row_338929 = next(row for row in rows if row["item_id"] == "338929")
    assert row_338929["root_receipt_record_count"] == 329
    assert row_338929["root_quantity"] == 1_645_000
    assert row_338929["mean_service_change_percentage_points"] == pytest.approx(
        -30.235333577235927
    )
    assert row_338929["causal_attribution_claimed"] is False


def test_map_source_with_excluded_incident_wording_is_rejected(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    roots = _fixture(tmp_path, monkeypatch)
    roots["map"].write_text(
        '<!doctype html><meta charset="utf-8">'
        f'<script src="{delivery.PLOTLY_CDN}"></script><p>quarantaine</p>',
        encoding="utf-8",
    )
    with pytest.raises(delivery.PreliminaryTransportDeliveryError, match="exclu"):
        delivery._validate_map_source(roots["map"], roots["plotly"])


def test_inventory_and_content_tamper_are_rejected(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    roots = _fixture(tmp_path, monkeypatch)
    output = tmp_path / "delivery-v2"
    delivery.build_delivery(
        preliminary_dir=roots["preliminary"],
        observed_dir=roots["observed"],
        regime_plan_dir=roots["regime"],
        action_plan_dir=roots["actions"],
        map_source=roots["map"],
        plotly_js=roots["plotly"],
        output_dir=output,
    )
    (output / "undeclared.csv").write_text("x\n1\n", encoding="utf-8")
    with pytest.raises(delivery.PreliminaryTransportDeliveryError, match="Inventaire"):
        delivery.validate_delivery(output)
    (output / "undeclared.csv").unlink()
    (output / delivery.VIEW_FILES[1]).write_text("tampered", encoding="utf-8")
    with pytest.raises(delivery.PreliminaryTransportDeliveryError, match="altéré"):
        delivery.validate_delivery(output)
