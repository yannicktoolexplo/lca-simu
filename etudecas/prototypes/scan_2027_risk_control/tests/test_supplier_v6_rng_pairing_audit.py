from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from etudecas.prototypes.scan_2027_risk_control import (
    supplier_v6_rng_pairing_audit as audit,
)


@pytest.fixture
def trace_fixture() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    lane = {
        "lane_id": "lane_pf967",
        "edge_id": "edge:supplier_to_m1430_component",
        "supplier_id": "SUPPLIER-A",
        "dst_node_id": "M-1430",
        "item_id": "item:component",
        "target_product_id": "268967",
    }
    graph = {
        "edges": [
            {
                "id": lane["edge_id"],
                "from": lane["supplier_id"],
                "to": lane["dst_node_id"],
                "items": [lane["item_id"]],
                "lead_time": {
                    "mean": 43.4,
                    "stages": 4,
                    "type": "erlang_pipeline",
                },
                "delay_step_limit": {"value": 87},
            }
        ]
    }
    fields = [
        "lane_id",
        "shipment_id",
        "risk_decision_day",
        "release_day",
        "arrival_day",
        "pulled_qty",
        "shipped_qty",
        "reliability",
        "lead_days",
        "uom",
    ]
    seed = 1369666196
    first_day = 99
    second_day = 311
    edge = graph["edges"][0]
    first_lead = audit.expected_erlang_lead_days(
        seed=seed,
        measured_day=first_day,
        lane=lane,
        edge=edge,
    )
    second_lead = audit.expected_erlang_lead_days(
        seed=seed,
        measured_day=second_day,
        lane=lane,
        edge=edge,
    )
    payload = {
        "seed": seed,
        "fields": fields,
        "rows": [
            [
                lane["lane_id"],
                "SHIP-00000001",
                first_day,
                first_day,
                first_day + first_lead,
                10.0,
                10.0,
                1.0,
                first_lead,
                "KG",
            ],
            [
                lane["lane_id"],
                "SHIP-00000002",
                first_day,
                first_day + 1,
                first_day + first_lead + 1,
                10.0,
                10.0,
                1.0,
                first_lead,
                "KG",
            ],
            [
                lane["lane_id"],
                "SHIP-00000003",
                second_day,
                second_day,
                second_day + second_lead,
                10.0,
                10.0,
                1.0,
                second_lead,
                "KG",
            ],
        ],
        "trace_signature": "a" * 64,
    }
    return payload, lane, graph


def test_trace_fixture_reconstructs_split_shipments_as_two_draws(
    trace_fixture: tuple[dict[str, Any], dict[str, Any], dict[str, Any]],
) -> None:
    payload, lane, graph = trace_fixture
    result = audit.analyze_trace_payload(
        payload,
        lane_by_id={lane["lane_id"]: lane},
        graph=graph,
        trace_gzip_sha256="b" * 64,
    )

    assert result.shipment_count == 3
    assert result.lane_day_identity_count == 2
    assert result.reconstructed_draw_count == 2
    assert result.regular_stream_match_count == 2
    assert result.annual_stream_only_match_count == 0
    assert result.mismatch_count == 0
    assert result.ambiguous_group_count == 0


def test_trace_fixture_detects_a_changed_lead(
    trace_fixture: tuple[dict[str, Any], dict[str, Any], dict[str, Any]],
) -> None:
    payload, lane, graph = trace_fixture
    payload["rows"][2][8] += 1

    result = audit.analyze_trace_payload(
        payload,
        lane_by_id={lane["lane_id"]: lane},
        graph=graph,
    )

    assert result.reconstructed_draw_count == 1
    assert result.mismatch_count == 1


def test_official_positive_margin_quantile_witnesses_are_stable() -> None:
    positive = {
        1745052434: 0.04526729462430712,
        583480470: 2.4861479409019616,
        887386588: 5.275729923978679,
        1146050562: 6.409105505020108,
        12328805: 9.187318211779804,
        508903655: 9.468010217738899,
        1316742469: 10.233734169789477,
        546039346: 10.569510516806336,
        1545515706: 10.835442999946432,
        1869291112: 12.477897873344945,
        434799925: 12.661152189054947,
        573960646: 15.497692023849098,
        1796420146: 17.626530552448283,
        1734584754: 18.318069559157525,
        1775564575: 19.05767474882082,
        1248984977: 19.765825609462883,
        1374528760: 19.978426403923066,
        1871757092: 21.307040762304386,
        466329796: 22.131243150479342,
        92478021: 24.3884838564561,
        1160236806: 26.73559755912498,
        1332985495: 27.50024884585265,
        1394133310: 29.61902869836235,
        1408401338: 58.742488880861885,
    }

    assert audit.select_quantile_witnesses(positive) == (
        1745052434,
        508903655,
        1869291112,
        1775564575,
        466329796,
        1408401338,
    )


def _delivery_fixture() -> tuple[dict[str, Any], list[dict[str, Any]]]:
    rows = [
        {
            "seed": 1,
            "role": "inversion",
            "margin_pf268967_pp": -1.0,
            "shipments_op93": 10,
            "shipments_op80": 11,
            "traceable_lane_day_draws_op93": 3,
            "traceable_lane_day_draws_op80": 4,
            "shared_lane_day_identities": 2,
            "identity_jaccard_pct": 40.0,
        },
        {
            "seed": 2,
            "role": "temoin_quantile",
            "margin_pf268967_pp": 2.0,
            "shipments_op93": 12,
            "shipments_op80": 13,
            "traceable_lane_day_draws_op93": 5,
            "traceable_lane_day_draws_op80": 6,
            "shared_lane_day_identities": 4,
            "identity_jaccard_pct": 57.1,
        },
    ]
    unsigned = {
        "schema_version": audit.AUDIT_SCHEMA_VERSION,
        "conclusion": audit.CONCLUSION,
        "holdout_context": {"official_joint_strict_order_count": 18},
        "reconstruction": {
            "all_30_seed_state_reconstructed_draws": 9,
            "focused_shared_op80_lead_strictly_longer": 6,
            "focused_shared_lane_day_identities": 6,
        },
        "focused_seed_rows": rows,
    }
    return {**unsigned, "audit_signature": audit.stable_sha256(unsigned)}, rows


def test_delivery_is_signed_and_refuses_overwrite(tmp_path: Path) -> None:
    payload, rows = _delivery_fixture()
    source = tmp_path / "source"
    source.mkdir()
    output = tmp_path / "new_delivery"

    manifest = audit.write_delivery(output, payload, rows, source_dirs=(source,))

    assert manifest["conclusion"] == audit.CONCLUSION
    assert audit.validate_delivery(output) == manifest
    with pytest.raises(FileExistsError, match="Refus d'\u00e9craser"):
        audit.write_delivery(output, payload, rows, source_dirs=(source,))


def test_delivery_refuses_to_overlap_source(tmp_path: Path) -> None:
    payload, rows = _delivery_fixture()
    source = tmp_path / "source"
    source.mkdir()

    with pytest.raises(audit.PairingAuditError, match="chevaucher"):
        audit.write_delivery(source / "child", payload, rows, source_dirs=(source,))
