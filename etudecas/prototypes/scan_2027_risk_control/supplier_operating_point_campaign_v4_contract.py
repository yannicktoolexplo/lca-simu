#!/usr/bin/env python3
"""Shared immutable contracts for the additive V4 supplier campaign.

This module contains no simulation entry point.  It only defines the fresh
seed cohorts and validates the compact shipment traces retained by the V4
operating-point holdout before the raw engine directories are pruned.
"""

from __future__ import annotations

import gzip
import hashlib
import io
import json
import math
from collections.abc import Mapping, Sequence
from pathlib import Path, PurePosixPath
from typing import Any


CAMPAIGN_SCHEMA_VERSION = "etudecas.supplier_operating_point_full_campaign.v4"
CASE_SCHEMA_VERSION = f"{CAMPAIGN_SCHEMA_VERSION}.case.v1"
BRIDGE_SCHEMA_VERSION = (
    f"{CAMPAIGN_SCHEMA_VERSION}.validated_operating_points.v1"
)
BRIDGE_ACCEPTED_STATUS = "accepted_v4_fresh_30_holdout_no_retuning"
TRACE_SCHEMA_VERSION = "etudecas.v4_holdout_shipment_trace.v1"
TRACE_LANE_CONTRACT_SCHEMA_VERSION = f"{TRACE_SCHEMA_VERSION}.lane_contract"
TRACE_COMPRESSION = "gzip_mtime_0_filename_empty_compresslevel_9"
TRACE_SOURCE_RELATIVE_PATH = "data/production_supplier_shipments_daily.csv"

OPERATING_POINT_IDS = ("op_100", "op_93", "op_80")
INCIDENT_DESIGN_SEED = 900659036
CAMPAIGN_SEEDS = (
    573960646,
    1871757092,
    1745052434,
    1160236806,
    92478021,
    1394133310,
    1596008569,
    1416403695,
    1492750790,
    1316742469,
    1332985495,
    1408401338,
    1869291112,
    12328805,
    1374528760,
    434799925,
    1796420146,
    55195456,
    1146050562,
    583480470,
    1369666196,
    1545515706,
    43087084,
    1248984977,
    887386588,
    1734584754,
    1775564575,
    508903655,
    546039346,
    466329796,
)
SEED_BLOCK_SIZE = 5
SEED_BLOCKS = tuple(
    CAMPAIGN_SEEDS[index : index + SEED_BLOCK_SIZE]
    for index in range(0, len(CAMPAIGN_SEEDS), SEED_BLOCK_SIZE)
)

TRACE_ROW_FIELDS = (
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
)
TRACE_REFERENCE_FIELDS = frozenset(
    {
        "relative_path",
        "gzip_sha256",
        "trace_signature",
        "source_csv_sha256",
        "row_count",
        "uncompressed_bytes",
        "compression",
    }
)
TRACE_PAYLOAD_FIELDS = frozenset(
    {
        "schema_version",
        "plan_signature",
        "candidate_key",
        "candidate_id",
        "target_group",
        "seed",
        "graph_sha256",
        "engine_sha256",
        "simulation_days",
        "lane_contract_sha256",
        "filter_contract",
        "fields",
        "row_count",
        "rows",
        "source_csv_sha256",
        "trace_signature",
    }
)
TRACE_LANE_FIELDS = (
    "lane_id",
    "edge_id",
    "supplier_id",
    "item_id",
    "dst_node_id",
    "target_product_id",
    "planned_lead_days",
)


class V4CampaignContractError(ValueError):
    """Raised when a signed V4 campaign dependency changes or is incomplete."""


def canonical_json_bytes(payload: Any) -> bytes:
    """Return the one canonical JSON representation used by V4 signatures."""

    return json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def stable_sha256(payload: Any) -> str:
    return hashlib.sha256(canonical_json_bytes(payload)).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def is_sha256(value: Any) -> bool:
    text = str(value or "")
    return len(text) == 64 and all(char in "0123456789abcdef" for char in text)


def lane_contract_payload(lanes: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Canonical lane projection used by the frozen V4 trace producer."""

    projected: list[dict[str, Any]] = []
    for raw in lanes:
        item: dict[str, Any] = {
            field: str(raw.get(field) or "").strip()
            for field in TRACE_LANE_FIELDS
            if field != "planned_lead_days"
        }
        lead = _finite_number(
            raw.get("planned_lead_days"), "V4 lane planned_lead_days"
        )
        item["planned_lead_days"] = lead
        if not all(item.values()) or lead <= 0.0:
            raise V4CampaignContractError("Incomplete lane identity in V4 contract")
        projected.append(item)
    projected.sort(key=lambda item: item["lane_id"])
    if len(projected) != 18:
        raise V4CampaignContractError("The V4 trace contract requires exactly 18 lanes")
    if len({item["lane_id"] for item in projected}) != len(projected):
        raise V4CampaignContractError("Duplicate lane_id in V4 trace contract")
    identity = {
        (item["supplier_id"], item["item_id"], item["dst_node_id"], item["edge_id"])
        for item in projected
    }
    if len(identity) != len(projected):
        raise V4CampaignContractError("Duplicate physical lane identity in V4 contract")
    return projected


def lane_contract_sha256(lanes: Sequence[Mapping[str, Any]]) -> str:
    return stable_sha256(
        {
            "schema_version": TRACE_LANE_CONTRACT_SCHEMA_VERSION,
            "lanes": lane_contract_payload(lanes),
        }
    )


def trace_filter_contract(lanes: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Return the exact dynamic filter signed into every official V4 trace."""

    projected = lane_contract_payload(lanes)
    return {
        "source_csv": TRACE_SOURCE_RELATIVE_PATH,
        "lane_ids": [lane["lane_id"] for lane in projected],
        "source_edge_id_by_lane_id": {
            lane["lane_id"]: lane["edge_id"] for lane in projected
        },
        "risk_decision_day_min_inclusive": 0,
        "risk_decision_day_max_inclusive": 719,
        "quantity_rule": (
            "pulled_qty_strictly_positive_and_shipped_qty_strictly_positive"
        ),
        "identifier_rule": "lane_id_and_shipment_id_non_empty",
        "arrival_rule": "arrival_day_equals_release_day_plus_positive_lead_days",
        "source_column_mapping": {"edge_id": "lane_id", "day": "release_day"},
        "canonical_sort_fields": [
            "lane_id",
            "risk_decision_day",
            "shipment_id",
            "arrival_day",
            "release_day",
        ],
    }


def _require_exact_keys(
    payload: Mapping[str, Any], expected: frozenset[str], label: str
) -> None:
    if set(payload) != expected:
        missing = sorted(expected - set(payload))
        extra = sorted(set(payload) - expected)
        raise V4CampaignContractError(
            f"{label} fields changed (missing={missing}, extra={extra})"
        )


def _finite_number(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise V4CampaignContractError(f"{label} must be numeric")
    result = float(value)
    if not math.isfinite(result):
        raise V4CampaignContractError(f"{label} must be finite")
    return result


def _integer(value: Any, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise V4CampaignContractError(f"{label} must be an integer")
    return value


def trace_unsigned_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    unsigned = dict(payload)
    unsigned.pop("trace_signature", None)
    return unsigned


def validate_trace_payload(
    payload: Mapping[str, Any],
    *,
    expected: Mapping[str, Any],
    allowed_lane_ids: Sequence[str],
) -> dict[str, Any]:
    """Validate the logical, uncompressed trace and its scientific filter."""

    _require_exact_keys(payload, TRACE_PAYLOAD_FIELDS, "V4 shipment trace")
    if payload.get("schema_version") != TRACE_SCHEMA_VERSION:
        raise V4CampaignContractError("V4 shipment-trace schema changed")
    for field in (
        "plan_signature",
        "candidate_key",
        "candidate_id",
        "target_group",
        "seed",
        "graph_sha256",
        "engine_sha256",
        "simulation_days",
        "lane_contract_sha256",
    ):
        if payload.get(field) != expected.get(field):
            raise V4CampaignContractError(f"V4 shipment-trace {field} changed")
    if payload.get("simulation_days") != 720:
        raise V4CampaignContractError("V4 holdout traces must cover exactly J0--J719")
    expected_filter = expected.get("filter_contract")
    if not isinstance(expected_filter, Mapping) or payload.get(
        "filter_contract"
    ) != dict(expected_filter):
        raise V4CampaignContractError("V4 shipment-trace filter contract changed")
    if payload.get("fields") != list(TRACE_ROW_FIELDS):
        raise V4CampaignContractError("V4 shipment-trace row fields changed")
    source_csv_sha = payload.get("source_csv_sha256")
    if not is_sha256(source_csv_sha):
        raise V4CampaignContractError("Invalid shipment source CSV hash")
    rows = payload.get("rows")
    if not isinstance(rows, list):
        raise V4CampaignContractError("V4 shipment-trace rows must be a list")
    row_count = payload.get("row_count")
    if isinstance(row_count, bool) or not isinstance(row_count, int):
        raise V4CampaignContractError("V4 shipment-trace row_count must be an integer")
    if row_count != len(rows):
        raise V4CampaignContractError("V4 shipment-trace row count changed")
    allowed = set(allowed_lane_ids)
    if not allowed:
        raise V4CampaignContractError("V4 shipment-trace lane scope is empty")
    prior_key: tuple[str, int, str, int, int] | None = None
    shipment_ids: set[str] = set()
    for index, row in enumerate(rows):
        if not isinstance(row, list) or len(row) != len(TRACE_ROW_FIELDS):
            raise V4CampaignContractError(f"Malformed V4 shipment row {index}")
        lane_id, shipment_id, decision, release, arrival, pulled, shipped, reliability, lead, uom = row
        if not isinstance(lane_id, str) or lane_id not in allowed:
            raise V4CampaignContractError(f"Unknown lane in V4 shipment row {index}")
        if (
            not isinstance(shipment_id, str)
            or not shipment_id.strip()
            or shipment_id in shipment_ids
        ):
            raise V4CampaignContractError(
                f"Empty or duplicated shipment_id in V4 row {index}"
            )
        shipment_ids.add(shipment_id)
        decision_day = _integer(decision, f"risk_decision_day row {index}")
        release_day = _integer(release, f"release_day row {index}")
        arrival_day = _integer(arrival, f"arrival_day row {index}")
        if not 0 <= decision_day < 720:
            raise V4CampaignContractError(f"Decision day outside J0--J719 in row {index}")
        lead_days = _integer(lead, f"lead_days row {index}")
        if arrival_day < 0 or lead_days <= 0 or arrival_day != release_day + lead_days:
            raise V4CampaignContractError(
                f"Invalid arrival/release/lead relationship in V4 row {index}"
            )
        pulled_value = _finite_number(pulled, f"pulled_qty row {index}")
        shipped_value = _finite_number(shipped, f"shipped_qty row {index}")
        if pulled_value <= 0.0:
            raise V4CampaignContractError(f"Non-positive pulled quantity in row {index}")
        if shipped_value <= 0.0:
            raise V4CampaignContractError(f"Non-positive shipped quantity in row {index}")
        if shipped_value > pulled_value + 1e-7:
            raise V4CampaignContractError(
                f"Shipped quantity exceeds pulled quantity in row {index}"
            )
        reliability_value = _finite_number(reliability, f"reliability row {index}")
        if not 0.0 <= reliability_value <= 1.0:
            raise V4CampaignContractError(f"Reliability outside [0,1] in row {index}")
        if not isinstance(uom, str) or not uom.strip():
            raise V4CampaignContractError(f"Empty uom in V4 row {index}")
        key = (lane_id, decision_day, shipment_id, arrival_day, release_day)
        if prior_key is not None and key < prior_key:
            raise V4CampaignContractError("V4 shipment-trace rows are not canonical")
        prior_key = key
    signature = str(payload.get("trace_signature") or "")
    if not is_sha256(signature) or signature != stable_sha256(
        trace_unsigned_payload(payload)
    ):
        raise V4CampaignContractError("Invalid V4 logical shipment-trace signature")
    return dict(payload)


def _safe_trace_path(run_dir: Path, relative_path: Any) -> Path:
    relative = str(relative_path or "")
    posix = PurePosixPath(relative)
    if (
        not relative
        or posix.is_absolute()
        or ".." in posix.parts
        or posix.suffixes[-2:] != [".json", ".gz"]
        or posix.parts[:2] != ("shipment_traces", "holdout")
    ):
        raise V4CampaignContractError("Unsafe or non-canonical shipment-trace path")
    root = run_dir.resolve()
    path = root.joinpath(*posix.parts).resolve()
    if not path.is_relative_to(root):
        raise V4CampaignContractError("Shipment-trace path escapes the V4 run")
    return path


def validate_trace_reference(
    reference: Mapping[str, Any],
    *,
    run_dir: Path,
    expected: Mapping[str, Any],
    allowed_lane_ids: Sequence[str],
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Validate a retained deterministic gzip and its signed evidence reference."""

    _require_exact_keys(reference, TRACE_REFERENCE_FIELDS, "V4 trace reference")
    if reference.get("compression") != TRACE_COMPRESSION:
        raise V4CampaignContractError("V4 shipment-trace compression changed")
    for field in ("gzip_sha256", "trace_signature", "source_csv_sha256"):
        if not is_sha256(reference.get(field)):
            raise V4CampaignContractError(f"Invalid V4 trace reference {field}")
    row_count = reference.get("row_count")
    uncompressed_bytes = reference.get("uncompressed_bytes")
    if (
        isinstance(row_count, bool)
        or not isinstance(row_count, int)
        or row_count < 0
        or isinstance(uncompressed_bytes, bool)
        or not isinstance(uncompressed_bytes, int)
        or uncompressed_bytes <= 0
    ):
        raise V4CampaignContractError("Invalid V4 trace size metadata")
    path = _safe_trace_path(run_dir, reference.get("relative_path"))
    if not path.is_file():
        raise V4CampaignContractError(f"Missing retained V4 shipment trace: {path}")
    compressed = path.read_bytes()
    if sha256_file(path) != reference["gzip_sha256"]:
        raise V4CampaignContractError("Retained V4 shipment-trace gzip hash changed")
    if len(compressed) < 10 or compressed[:3] != b"\x1f\x8b\x08":
        raise V4CampaignContractError("Retained V4 shipment trace is not gzip")
    if int.from_bytes(compressed[4:8], "little") != 0:
        raise V4CampaignContractError("V4 shipment gzip is not deterministic mtime=0")
    try:
        raw = gzip.decompress(compressed)
    except (EOFError, OSError) as exc:
        raise V4CampaignContractError("Corrupt retained V4 shipment gzip") from exc
    if len(raw) != uncompressed_bytes:
        raise V4CampaignContractError("V4 trace uncompressed size changed")
    canonical_gzip = io.BytesIO()
    with gzip.GzipFile(
        filename="",
        mode="wb",
        compresslevel=9,
        fileobj=canonical_gzip,
        mtime=0,
    ) as handle:
        handle.write(raw)
    if canonical_gzip.getvalue() != compressed:
        raise V4CampaignContractError(
            "V4 shipment gzip is not the canonical filename-empty level-9 stream"
        )
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise V4CampaignContractError("Invalid retained V4 shipment JSON") from exc
    if not isinstance(payload, Mapping):
        raise V4CampaignContractError("Retained V4 shipment payload is not an object")
    validated = validate_trace_payload(
        payload, expected=expected, allowed_lane_ids=allowed_lane_ids
    )
    for field in ("trace_signature", "source_csv_sha256", "row_count"):
        if reference.get(field) != validated.get(field):
            raise V4CampaignContractError(f"V4 trace reference/payload {field} differs")
    return dict(reference), validated
