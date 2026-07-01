from __future__ import annotations

import json
from pathlib import Path
from typing import Any


DEFAULT_CASE_CONFIG_PATH = Path(__file__).resolve().parent / "config" / "cases" / "data_poc.json"


def load_case_config(path: str | Path | None = None) -> dict[str, Any]:
    config_path = Path(path) if path else DEFAULT_CASE_CONFIG_PATH
    if not config_path.exists():
        return {}
    data = json.loads(config_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"Case config root must be a mapping: {config_path}")
    return data


def normalize_item_id(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    return text if text.startswith("item:") else f"item:{text}"


def _tuple_key(row: dict[str, Any]) -> tuple[str, str]:
    return (str(row.get("node_id") or ""), normalize_item_id(row.get("item_id")))


def _load_standard_order_overrides(raw: dict[str, Any]) -> dict[tuple[str, str, str], dict[str, Any]]:
    overrides: dict[tuple[str, str, str], dict[str, Any]] = {}
    for row in raw.get("standard_order_overrides") or []:
        if not isinstance(row, dict):
            continue
        src = str(row.get("src") or "")
        dst = str(row.get("dst") or "")
        item_id = normalize_item_id(row.get("item_id"))
        if src and dst and item_id:
            overrides[(src, dst, item_id)] = {
                key: value
                for key, value in row.items()
                if key not in {"src", "dst", "item_id"}
            }
    return overrides


def _load_production_cost_line_shares(raw: dict[str, Any]) -> dict[tuple[str, str], float]:
    shares: dict[tuple[str, str], float] = {}
    for row in raw.get("production_cost_line_shares") or []:
        if not isinstance(row, dict):
            continue
        node_id, item_id = _tuple_key(row)
        if not node_id or not item_id:
            continue
        try:
            shares[(node_id, item_id)] = float(row.get("share") or 0.0)
        except (TypeError, ValueError):
            continue
    return shares


def _load_production_cost_line_profiles(raw: dict[str, Any]) -> dict[tuple[str, str], str]:
    profiles: dict[tuple[str, str], str] = {}
    for row in raw.get("production_cost_line_profiles") or []:
        if not isinstance(row, dict):
            continue
        node_id, item_id = _tuple_key(row)
        profile = str(row.get("profile") or "")
        if node_id and item_id and profile:
            profiles[(node_id, item_id)] = profile
    return profiles


_ACTIVE_CASE_CONFIG = load_case_config()

NODE_ID_ALIASES = {
    str(old): str(new)
    for old, new in (_ACTIVE_CASE_CONFIG.get("node_aliases") or {}).items()
}
UPSTREAM_INTERNAL_SITE_IDS = {
    str(node_id)
    for node_id in (_ACTIVE_CASE_CONFIG.get("upstream_internal_site_ids") or [])
    if str(node_id)
}
UPSTREAM_INTERNAL_SITE_DISPLAY_LABELS = {
    str(node_id): str(label)
    for node_id, label in (_ACTIVE_CASE_CONFIG.get("node_display_labels") or {}).items()
}
ITEM_DISPLAY_REFERENCE_NOTES = {
    normalize_item_id(item_id): str(label)
    for item_id, label in (_ACTIVE_CASE_CONFIG.get("item_reference_notes") or {}).items()
}
LOT_TRACE_DEFAULT_LOGISTICS_ASSUMPTIONS = {
    normalize_item_id(item_id): dict(policy)
    for item_id, policy in (_ACTIVE_CASE_CONFIG.get("logistics_assumptions") or {}).items()
    if isinstance(policy, dict)
}
STANDARD_ORDER_OVERRIDES = _load_standard_order_overrides(_ACTIVE_CASE_CONFIG)
DEFAULT_PRODUCTION_COST_LINE_SHARES = _load_production_cost_line_shares(_ACTIVE_CASE_CONFIG)
DEFAULT_PRODUCTION_COST_LINE_PROFILES = _load_production_cost_line_profiles(_ACTIVE_CASE_CONFIG)


def canonical_node_id(node_id: Any) -> str:
    raw = str(node_id or "")
    return NODE_ID_ALIASES.get(raw, raw)


def is_upstream_internal_site(node_id: Any) -> bool:
    return canonical_node_id(node_id) in UPSTREAM_INTERNAL_SITE_IDS


def display_node_id(node_id: Any) -> str:
    canonical = canonical_node_id(node_id)
    return UPSTREAM_INTERNAL_SITE_DISPLAY_LABELS.get(canonical, canonical)


def item_display_reference_note(item_id: Any, fallback: str = "") -> str:
    item = normalize_item_id(item_id)
    return ITEM_DISPLAY_REFERENCE_NOTES.get(item, fallback or item)


def standard_order_override(src: Any, dst: Any, item_id: Any) -> dict[str, Any] | None:
    item = normalize_item_id(item_id)
    candidate_keys = [
        (canonical_node_id(src), canonical_node_id(dst), item),
        (str(src or ""), str(dst or ""), item),
    ]
    for key in candidate_keys:
        override = STANDARD_ORDER_OVERRIDES.get(key)
        if override:
            return override
    return None


def build_lot_trace_config(raw: dict[str, Any] | None = None) -> dict[str, Any]:
    """Build lot-trace display rules with optional graph-level overrides.

    Case-specific rules should live in the case JSON file or in graph metadata
    under `case_config`, `lot_trace_config`, `_meta.lot_trace_config`, or
    `visualization.lot_trace_config`.
    """

    config: dict[str, Any] = {
        "node_aliases": dict(NODE_ID_ALIASES),
        "node_display_labels": dict(UPSTREAM_INTERNAL_SITE_DISPLAY_LABELS),
        "upstream_internal_site_ids": sorted(UPSTREAM_INTERNAL_SITE_IDS),
        "item_reference_notes": dict(ITEM_DISPLAY_REFERENCE_NOTES),
        "logistics_assumptions": {
            item_id: dict(policy)
            for item_id, policy in LOT_TRACE_DEFAULT_LOGISTICS_ASSUMPTIONS.items()
        },
    }
    if not raw:
        return config

    override_sources = [
        raw.get("case_config"),
        raw.get("lot_trace_config"),
        (raw.get("_meta") or {}).get("case_config") if isinstance(raw.get("_meta"), dict) else None,
        (raw.get("_meta") or {}).get("lot_trace_config") if isinstance(raw.get("_meta"), dict) else None,
        (raw.get("visualization") or {}).get("lot_trace_config")
        if isinstance(raw.get("visualization"), dict)
        else None,
    ]
    for override in override_sources:
        if not isinstance(override, dict):
            continue
        for key in ["node_aliases", "node_display_labels", "item_reference_notes"]:
            value = override.get(key)
            if isinstance(value, dict):
                config[key].update(value)
        logistics = override.get("logistics_assumptions")
        if isinstance(logistics, dict):
            for item_id, policy in logistics.items():
                if not isinstance(policy, dict):
                    continue
                item_key = normalize_item_id(item_id)
                existing = config["logistics_assumptions"].get(item_key, {})
                if not isinstance(existing, dict):
                    existing = {}
                merged = dict(existing)
                merged.update(policy)
                config["logistics_assumptions"][item_key] = merged
        upstream_sites = override.get("upstream_internal_site_ids")
        if isinstance(upstream_sites, list):
            merged = set(str(node_id) for node_id in config["upstream_internal_site_ids"])
            merged.update(str(node_id) for node_id in upstream_sites if str(node_id))
            config["upstream_internal_site_ids"] = sorted(merged)
    return config
