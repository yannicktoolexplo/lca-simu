from __future__ import annotations

import gzip
import io
from pathlib import Path
from types import SimpleNamespace

import pytest

from etudecas.prototypes.scan_2027_risk_control import (
    supplier_operating_point_campaign_v4_contract as subject,
)
from etudecas.prototypes.scan_2027_risk_control import (
    supplier_balanced_product_delay_multiseed_refinement_v4 as trace_producer,
)


def _lanes() -> list[dict[str, object]]:
    return [
        {
            "lane_id": f"lane_{index:02d}",
            "supplier_id": f"SUP-{index:02d}",
            "item_id": f"item:{index:06d}",
            "dst_node_id": "M-1810",
            "edge_id": f"edge:{index:02d}",
            "target_product_id": "268091",
            "planned_lead_days": 10.0 + index,
        }
        for index in range(1, 19)
    ]


def _payload(
    *, lane_sha: str, filter_contract: dict[str, object], rows: list[list[object]]
) -> dict[str, object]:
    unsigned: dict[str, object] = {
        "schema_version": subject.TRACE_SCHEMA_VERSION,
        "plan_signature": "1" * 64,
        "candidate_key": "op100_source",
        "candidate_id": "v4_op100_source",
        "target_group": "op_100",
        "seed": subject.CAMPAIGN_SEEDS[0],
        "graph_sha256": "2" * 64,
        "engine_sha256": "3" * 64,
        "simulation_days": 720,
        "lane_contract_sha256": lane_sha,
        "filter_contract": filter_contract,
        "fields": list(subject.TRACE_ROW_FIELDS),
        "row_count": len(rows),
        "rows": rows,
        "source_csv_sha256": "4" * 64,
    }
    return {**unsigned, "trace_signature": subject.stable_sha256(unsigned)}


def _reference(path: Path, raw: bytes, payload: dict[str, object]) -> dict[str, object]:
    return {
        "relative_path": path.as_posix(),
        "gzip_sha256": subject.sha256_file(path.parent.parent.parent / path),
        "trace_signature": payload["trace_signature"],
        "source_csv_sha256": payload["source_csv_sha256"],
        "row_count": payload["row_count"],
        "uncompressed_bytes": len(raw),
        "compression": subject.TRACE_COMPRESSION,
    }


def _write_trace(run_dir: Path, payload: dict[str, object]) -> tuple[Path, bytes]:
    relative = Path("shipment_traces") / "holdout" / "case.json.gz"
    path = run_dir / relative
    path.parent.mkdir(parents=True)
    raw = subject.canonical_json_bytes(payload)
    output = io.BytesIO()
    with gzip.GzipFile(
        filename="", mode="wb", compresslevel=9, fileobj=output, mtime=0
    ) as handle:
        handle.write(raw)
    path.write_bytes(output.getvalue())
    return relative, raw


def test_fresh_campaign_seeds_and_design_seed_are_frozen_and_disjoint() -> None:
    assert len(subject.CAMPAIGN_SEEDS) == 30
    assert len(set(subject.CAMPAIGN_SEEDS)) == 30
    assert subject.INCIDENT_DESIGN_SEED == 900659036
    assert subject.INCIDENT_DESIGN_SEED not in subject.CAMPAIGN_SEEDS
    assert len(subject.SEED_BLOCKS) == 6
    assert all(len(block) == 5 for block in subject.SEED_BLOCKS)


def test_campaign_trace_contract_is_byte_contract_compatible_with_v4_producer() -> None:
    lanes = _lanes()
    plan = SimpleNamespace(manifest={"source": {"lanes": lanes}})
    producer_lane_contract = trace_producer._shipment_lane_contract(plan)

    assert subject.TRACE_SCHEMA_VERSION == trace_producer.SHIPMENT_TRACE_SCHEMA_VERSION
    assert subject.TRACE_COMPRESSION == trace_producer.SHIPMENT_TRACE_COMPRESSION
    assert subject.lane_contract_payload(lanes) == producer_lane_contract["lanes"]
    assert subject.lane_contract_sha256(lanes) == producer_lane_contract[
        "lane_contract_sha256"
    ]
    assert subject.trace_filter_contract(lanes) == trace_producer._shipment_filter_contract(
        plan
    )


def test_compact_trace_round_trip_validates_exact_fields_and_mtime(tmp_path: Path) -> None:
    lanes = _lanes()
    lane_sha = subject.lane_contract_sha256(lanes)
    filter_contract = subject.trace_filter_contract(lanes)
    payload = _payload(
        lane_sha=lane_sha,
        filter_contract=filter_contract,
        rows=[
            ["lane_01", "shipment-a", 10, 10, 20, 100.0, 100.0, 1.0, 10, "UN"],
            ["lane_02", "shipment-b", 15, 15, 27, 80.0, 75.0, 0.9, 12, "UN"],
        ],
    )
    relative, raw = _write_trace(tmp_path, payload)
    reference = {
        "relative_path": relative.as_posix(),
        "gzip_sha256": subject.sha256_file(tmp_path / relative),
        "trace_signature": payload["trace_signature"],
        "source_csv_sha256": payload["source_csv_sha256"],
        "row_count": 2,
        "uncompressed_bytes": len(raw),
        "compression": subject.TRACE_COMPRESSION,
    }
    expected = {
        "plan_signature": "1" * 64,
        "candidate_key": "op100_source",
        "candidate_id": "v4_op100_source",
        "target_group": "op_100",
        "seed": subject.CAMPAIGN_SEEDS[0],
        "graph_sha256": "2" * 64,
        "engine_sha256": "3" * 64,
        "simulation_days": 720,
        "lane_contract_sha256": lane_sha,
        "filter_contract": filter_contract,
    }

    validated_reference, validated_payload = subject.validate_trace_reference(
        reference,
        run_dir=tmp_path,
        expected=expected,
        allowed_lane_ids=[row["lane_id"] for row in lanes],
    )

    assert validated_reference == reference
    assert validated_payload == payload


def test_trace_rejects_unsorted_rows_and_reference_corruption(tmp_path: Path) -> None:
    lanes = _lanes()
    lane_sha = subject.lane_contract_sha256(lanes)
    filter_contract = subject.trace_filter_contract(lanes)
    payload = _payload(
        lane_sha=lane_sha,
        filter_contract=filter_contract,
        rows=[
            ["lane_02", "shipment-b", 15, 15, 27, 80.0, 75.0, 0.9, 12, "UN"],
            ["lane_01", "shipment-a", 10, 10, 20, 100.0, 100.0, 1.0, 10, "UN"],
        ],
    )
    expected = {
        "plan_signature": "1" * 64,
        "candidate_key": "op100_source",
        "candidate_id": "v4_op100_source",
        "target_group": "op_100",
        "seed": subject.CAMPAIGN_SEEDS[0],
        "graph_sha256": "2" * 64,
        "engine_sha256": "3" * 64,
        "simulation_days": 720,
        "lane_contract_sha256": lane_sha,
        "filter_contract": filter_contract,
    }
    with pytest.raises(subject.V4CampaignContractError, match="not canonical"):
        subject.validate_trace_payload(
            payload,
            expected=expected,
            allowed_lane_ids=[row["lane_id"] for row in lanes],
        )

    payload["rows"] = list(reversed(payload["rows"]))
    unsigned = dict(payload)
    unsigned.pop("trace_signature")
    payload["trace_signature"] = subject.stable_sha256(unsigned)
    relative, raw = _write_trace(tmp_path, payload)
    reference = {
        "relative_path": relative.as_posix(),
        "gzip_sha256": "0" * 64,
        "trace_signature": payload["trace_signature"],
        "source_csv_sha256": payload["source_csv_sha256"],
        "row_count": 2,
        "uncompressed_bytes": len(raw),
        "compression": subject.TRACE_COMPRESSION,
    }
    with pytest.raises(subject.V4CampaignContractError, match="gzip hash"):
        subject.validate_trace_reference(
            reference,
            run_dir=tmp_path,
            expected=expected,
            allowed_lane_ids=[row["lane_id"] for row in lanes],
        )


def test_trace_rejects_physically_incoherent_arrival_and_quantity() -> None:
    lanes = _lanes()
    lane_sha = subject.lane_contract_sha256(lanes)
    filter_contract = subject.trace_filter_contract(lanes)
    expected = {
        "plan_signature": "1" * 64,
        "candidate_key": "op100_source",
        "candidate_id": "v4_op100_source",
        "target_group": "op_100",
        "seed": subject.CAMPAIGN_SEEDS[0],
        "graph_sha256": "2" * 64,
        "engine_sha256": "3" * 64,
        "simulation_days": 720,
        "lane_contract_sha256": lane_sha,
        "filter_contract": filter_contract,
    }
    bad_arrival = _payload(
        lane_sha=lane_sha,
        filter_contract=filter_contract,
        rows=[["lane_01", "shipment-a", 10, 10, 21, 100.0, 90.0, 1.0, 10, "UN"]],
    )
    with pytest.raises(subject.V4CampaignContractError, match="arrival/release/lead"):
        subject.validate_trace_payload(
            bad_arrival,
            expected=expected,
            allowed_lane_ids=[row["lane_id"] for row in lanes],
        )

    bad_quantity = _payload(
        lane_sha=lane_sha,
        filter_contract=filter_contract,
        rows=[["lane_01", "shipment-a", 10, 10, 20, 90.0, 100.0, 1.0, 10, "UN"]],
    )
    with pytest.raises(subject.V4CampaignContractError, match="exceeds pulled"):
        subject.validate_trace_payload(
            bad_quantity,
            expected=expected,
            allowed_lane_ids=[row["lane_id"] for row in lanes],
        )


def test_trace_rejects_path_escape() -> None:
    with pytest.raises(subject.V4CampaignContractError, match="non-canonical"):
        subject._safe_trace_path(Path.cwd(), "shipment_traces/holdout/../../x.json.gz")
