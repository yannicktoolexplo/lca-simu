from __future__ import annotations

import hashlib
from typing import Any

from etudecas.simulation.analysis_batch_common import safe_name

GLOBAL_PARAMETER_ALIASES = {
    "baseline": "base",
    "lead_time_scale": "lt",
    "transport_cost_scale": "tc",
    "supplier_stock_scale": "sstk",
    "production_stock_scale": "pstk",
    "capacity_scale": "cap",
    "supplier_capacity_scale": "scap",
    "safety_stock_days_scale": "ss",
    "supplier_reliability_scale": "srel",
    "review_period_scale": "rev",
    "opening_stock_bootstrap_scale": "boot",
    "external_procurement_enabled": "ep_on",
    "external_procurement_daily_cap_days_scale": "ep_cap",
    "external_procurement_lead_days_scale": "ep_lt",
    "external_procurement_cost_multiplier_scale": "ep_cost",
    "holding_cost_scale": "hold",
}

SCOPED_PARAMETER_ALIASES = {
    "demand_item": "dem",
    "capacity_node": "cap",
    "supplier_stock_node": "sstk",
    "supplier_capacity_node": "scap",
    "supplier_lead_time_node": "slt",
    "supplier_reliability_node": "srel",
}

DIRECTION_ALIASES = {
    "base": "base",
    "repeat": "rpt",
    "low": "lo",
    "high": "hi",
    "stress": "str",
}


def _clip_with_hash(value: str, max_len: int) -> str:
    if len(value) <= max_len:
        return value
    digest = hashlib.sha1(value.encode("utf-8")).hexdigest()[:8]
    head_len = max(8, max_len - len(digest) - 1)
    return f"{value[:head_len].rstrip('_-')}_{digest}"


def parameter_key_slug(parameter_key: str, *, max_len: int = 36) -> str:
    parameter_key = str(parameter_key or "").strip()
    if not parameter_key:
        return "param"
    if "::" not in parameter_key:
        return _clip_with_hash(GLOBAL_PARAMETER_ALIASES.get(parameter_key, safe_name(parameter_key)), max_len)
    scope, target = parameter_key.split("::", 1)
    scope_slug = SCOPED_PARAMETER_ALIASES.get(scope, safe_name(scope))
    target_slug = safe_name(target)
    return _clip_with_hash(f"{scope_slug}_{target_slug}", max_len)


def level_slug(level: Any) -> str:
    if isinstance(level, bool):
        return "1" if level else "0"
    if isinstance(level, int):
        return str(level)
    if isinstance(level, float):
        if level.is_integer():
            return f"{int(level)}_0"
        text = f"{level:.4f}".rstrip("0").rstrip(".")
        return safe_name(text.replace("-", "m"))
    return safe_name(str(level).replace("-", "m"))


def realistic_case_id(*, study: str, parameter_key: str, direction: str) -> str:
    study = str(study or "").strip()
    direction = str(direction or "").strip()
    if study == "baseline":
        return "baseline_repeat" if direction == "repeat" else "baseline"
    study_slug = {"local": "loc", "stress": "str"}.get(study, safe_name(study))
    direction_slug = DIRECTION_ALIASES.get(direction, safe_name(direction))
    return _clip_with_hash(
        f"{study_slug}_{parameter_key_slug(parameter_key, max_len=28)}_{direction_slug}",
        48,
    )


def threshold_case_id(*, parameter_key: str, level: Any) -> str:
    if str(parameter_key or "").strip() == "baseline":
        return "baseline"
    return _clip_with_hash(
        f"th_{parameter_key_slug(parameter_key, max_len=28)}_{level_slug(level)}",
        48,
    )
