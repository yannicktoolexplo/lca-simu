from __future__ import annotations

import hashlib
import re
from collections.abc import Iterable
from typing import Any


LOT_CAUSAL_EVENT_FIELDS = [
    "scenario_id",
    "causal_event_ids",
    "causal_root_ids",
    "causal_status",
    "baseline_reference_id",
    "planned_order_id",
    "origin_production_order_ids",
    "origin_production_contributions_json",
    "origin_allocation_basis",
    "required_item_id",
    "consumed_item_id",
    "replacement_qty",
    "replacement_reason",
    "replacement_transition_id",
]

LOT_CAUSAL_GENEALOGY_FIELDS = list(LOT_CAUSAL_EVENT_FIELDS)

PLAN_CAUSAL_FIELDS = [
    "scenario_id",
    "planned_order_id",
    "causal_event_ids",
    "causal_root_ids",
    "causal_status",
    "baseline_reference_id",
]

CAMPAIGN_CAUSAL_FIELDS = list(PLAN_CAUSAL_FIELDS)


def normalize_identifier(value: Any) -> str:
    return re.sub(r"[^A-Za-z0-9_.:-]+", "-", str(value or "").strip()).strip("-")


def split_ids(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        raw_values = re.split(r"[|,;]", value)
    elif isinstance(value, Iterable):
        raw_values = [str(item) for item in value]
    else:
        raw_values = [str(value)]
    return sorted({item.strip() for item in raw_values if item and item.strip()})


def join_ids(*values: Any) -> str:
    merged: set[str] = set()
    for value in values:
        merged.update(split_ids(value))
    return "|".join(sorted(merged))


def stable_reference_id(prefix: str, *parts: Any) -> str:
    normalized = "|".join(str(part or "").strip() for part in parts)
    digest = hashlib.sha1(normalized.encode("utf-8")).hexdigest()[:16].upper()
    return f"{normalize_identifier(prefix).upper()}-{digest}"


def planned_order_reference(*, node_id: str, item_id: str, ordinal: int) -> str:
    """Return a production-intent key independent from completion date and lot ID."""

    scope = f"{normalize_identifier(node_id)}-{normalize_identifier(item_id)}"
    return f"PORD-{scope}-{max(1, int(ordinal)):06d}"


def causal_status(
    event_ids: Any,
    *,
    root_ids: Any = "",
    fallback: str = "nominal",
) -> str:
    event_values = split_ids(event_ids)
    root_values = split_ids(root_ids) or event_values
    if len(root_values) > 1:
        return "co_causes"
    return "scenario_affected" if event_values or root_values else fallback


def resolved_causal_status(
    event_ids: Any,
    *,
    root_ids: Any = "",
    provided_status: Any = "",
    fallback: str = "nominal",
) -> str:
    """Keep explicit business statuses, but never label caused data as nominal."""

    provided = str(provided_status or "").strip()
    has_causes = bool(split_ids(event_ids) or split_ids(root_ids))
    if provided and not (provided == fallback and has_causes):
        return provided
    return causal_status(event_ids, root_ids=root_ids, fallback=fallback)


def inherited_causal_fields(
    parent_rows: Iterable[dict[str, Any]],
    *,
    scenario_id: str = "",
    causal_event_ids: Any = "",
    causal_root_ids: Any = "",
    causal_status_value: str = "",
    baseline_reference_id: str = "",
    planned_order_id: str = "",
) -> dict[str, str]:
    parents = list(parent_rows)
    merged_events = join_ids(
        causal_event_ids,
        *(row.get("causal_event_ids") for row in parents),
    )
    merged_roots = join_ids(
        causal_root_ids,
        *(row.get("causal_root_ids") for row in parents),
    )
    return {
        "scenario_id": str(
            scenario_id
            or next((row.get("scenario_id") for row in parents if row.get("scenario_id")), "")
        ),
        "causal_event_ids": merged_events,
        "causal_root_ids": merged_roots or merged_events,
        "causal_status": resolved_causal_status(
            merged_events,
            root_ids=merged_roots,
            provided_status=causal_status_value,
        ),
        "baseline_reference_id": str(
            baseline_reference_id
            or next(
                (row.get("baseline_reference_id") for row in parents if row.get("baseline_reference_id")),
                "",
            )
        ),
        "planned_order_id": str(
            planned_order_id
            or next((row.get("planned_order_id") for row in parents if row.get("planned_order_id")), "")
        ),
    }


__all__ = [
    "CAMPAIGN_CAUSAL_FIELDS",
    "LOT_CAUSAL_EVENT_FIELDS",
    "LOT_CAUSAL_GENEALOGY_FIELDS",
    "PLAN_CAUSAL_FIELDS",
    "causal_status",
    "inherited_causal_fields",
    "join_ids",
    "normalize_identifier",
    "planned_order_reference",
    "resolved_causal_status",
    "split_ids",
    "stable_reference_id",
]
