#!/usr/bin/env python3
"""Build a compact, standalone supplier-service landscape dashboard.

The campaign directory is read-only input.  The generated document contains
the complete compact campaign payload, its presentation code and its styles;
it never loads a network resource and it refuses to replace an existing file.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import re
import unicodedata
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


SCHEMA_VERSION = "etudecas.supplier_service_landscape_dashboard.v1"

CAMPAIGN_FILES = {
    "manifest": "campaign_manifest.json",
    "scenario_design": "scenario_design.csv",
    "screening_metrics": "screening_metrics.csv",
    "confirmation_metrics": "confirmation_metrics.csv",
    "scenario_summary": "scenario_summary.csv",
    "worst_cases": "worst_cases.csv",
}


def _normalise_key(value: object) -> str:
    text = unicodedata.normalize("NFKD", str(value))
    text = "".join(character for character in text if not unicodedata.combining(character))
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")


def _clean_text(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _to_float(value: object) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        number = float(value)
        return number if math.isfinite(number) else None
    text = str(value).strip().replace("\u202f", "").replace("\xa0", "").replace(" ", "")
    if not text:
        return None
    is_percent = text.endswith("%")
    if is_percent:
        text = text[:-1]
    if "," in text and "." not in text:
        text = text.replace(",", ".")
    try:
        number = float(text)
    except ValueError:
        return None
    if not math.isfinite(number):
        return None
    return number / 100.0 if is_percent else number


def _as_rate(value: object) -> float | None:
    number = _to_float(value)
    if number is None:
        return None
    if 1.5 < abs(number) <= 100.0:
        number /= 100.0
    if number < 0.0 or number > 1.25:
        return None
    return number


def _as_rate_delta(value: object) -> float | None:
    number = _to_float(value)
    if number is None:
        return None
    if 1.5 < abs(number) <= 100.0:
        number /= 100.0
    return number if abs(number) <= 1.25 else None


def _as_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    number = _to_float(value)
    if number is not None:
        return bool(number)
    return _normalise_key(value) in {"1", "true", "yes", "oui", "baseline", "reference"}


def _as_fraction(value: object) -> float | None:
    """Read either a boolean run flag or a numeric fraction."""
    if isinstance(value, bool):
        return 1.0 if value else 0.0
    key = _normalise_key(value)
    if key in {"true", "yes", "oui"}:
        return 1.0
    if key in {"false", "no", "non"}:
        return 0.0
    return _as_rate(value)


def _level_display(
    *,
    scenario: str,
    mechanism: str,
    level_label: str,
    level_code: str,
    mechanism_value: str,
    mechanism_unit: str,
) -> str:
    label = level_label or level_code or scenario
    if not mechanism_value:
        return label
    value = mechanism_value
    number = _to_float(mechanism_value)
    if number is not None:
        value = f"{number:g}".replace(".", ",")
    mechanism_key = _normalise_key(mechanism)
    unit_key = _normalise_key(mechanism_unit)
    if number is not None and unit_key == "ratio":
        percent = f"{number * 100:g}".replace(".", ",") + " %"
        suffix = {
            "capacity": "de la capacité de référence",
            "reliability": "de quantité utile expédiée",
            "availability": "de disponibilité fournisseur",
            "quality_yield": "de quantité reçue utilisable",
        }.get(mechanism_key, "du niveau de référence")
        return f"{percent} {suffix}"
    if number is not None and unit_key == "jours":
        prefix = "+" if number > 0 else ""
        suffix = " de délai de libération qualité" if mechanism_key == "quality_delay" else " de retard fournisseur"
        return f"{prefix}{value} jours{suffix}"
    if number is not None and unit_key == "jours_moyens_ajoutes":
        prefix = "+" if number > 0 else ""
        return f"{prefix}{value} jours moyens de retard intermittent"
    physical = " ".join(part for part in (value, mechanism_unit) if part)
    return physical or label


def _row_values(row: Mapping[str, object]) -> dict[str, object]:
    return {
        _normalise_key(key): value
        for key, value in row.items()
        if key is not None and _clean_text(value)
    }


def _pick(
    row: Mapping[str, object],
    aliases: Sequence[str],
    *,
    include_any: Sequence[Sequence[str]] = (),
    exclude: Sequence[str] = (),
) -> object | None:
    values = _row_values(row)
    for alias in aliases:
        value = values.get(_normalise_key(alias))
        if value is not None:
            return value
    excluded = tuple(_normalise_key(token) for token in exclude)
    for tokens in include_any:
        wanted = tuple(_normalise_key(token) for token in tokens)
        for key, value in values.items():
            if all(token in key for token in wanted) and not any(token in key for token in excluded):
                return value
    return None


def _pick_text(row: Mapping[str, object], aliases: Sequence[str]) -> str:
    return _clean_text(_pick(row, aliases))


def _pick_rate(
    row: Mapping[str, object],
    aliases: Sequence[str],
    *,
    include_any: Sequence[Sequence[str]] = (),
    exclude: Sequence[str] = (),
) -> float | None:
    return _as_rate(_pick(row, aliases, include_any=include_any, exclude=exclude))


def _read_csv(path: Path) -> dict[str, object]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        columns = [str(column) for column in (reader.fieldnames or []) if column is not None]
        rows: list[dict[str, str]] = []
        for raw in reader:
            row = {
                str(key): "" if value is None else str(value)
                for key, value in raw.items()
                if key is not None
            }
            rows.append(row)
    return {"columns": columns, "rows": rows}


def _read_json(path: Path) -> object:
    with path.open("r", encoding="utf-8-sig") as handle:
        return json.load(handle)


def _scenario_id(row: Mapping[str, object], fallback: str) -> str:
    return _pick_text(
        row,
        (
            "scenario_id",
            "case_id",
            "configuration_id",
            "variant_id",
            "scenario",
            "case",
            "variant",
            "run_id",
        ),
    ) or fallback


def _design_context(table: Mapping[str, object]) -> dict[str, dict[str, object]]:
    contexts: dict[str, dict[str, object]] = {}
    rows = table.get("rows", [])
    if not isinstance(rows, list):
        return contexts
    for index, row in enumerate(rows):
        if not isinstance(row, Mapping):
            continue
        scenario = _scenario_id(row, f"configuration-{index + 1}")
        context: dict[str, object] = dict(row)
        encoded = _pick_text(row, ("parameter_values_json", "parameters_json", "configuration_json"))
        if encoded:
            try:
                decoded = json.loads(encoded)
            except json.JSONDecodeError:
                decoded = None
            if isinstance(decoded, Mapping):
                for key, value in decoded.items():
                    context.setdefault(str(key), value)
        contexts[scenario] = context
    return contexts


def _chain_label(row: Mapping[str, object]) -> str:
    explicit = _pick_text(
        row,
        (
            "chain_label",
            "chain",
            "supply_chain",
            "cascade",
            "cascade_id",
            "flow",
            "flow_id",
            "network_path",
            "scope",
            "chain_id",
        ),
    )
    if explicit:
        return explicit
    supplier = _pick_text(row, ("supplier", "supplier_id", "supplier_node"))
    item = _pick_text(row, ("item", "item_id", "component", "component_id", "material"))
    product = _pick_text(row, ("product", "product_id", "finished_product", "sku"))
    parts = [part for part in (supplier, item, product) if part]
    return " → ".join(parts) if parts else "Chaîne non renseignée"


def _mechanism_label(row: Mapping[str, object]) -> str:
    return _pick_text(
        row,
        (
            "mechanism_label",
            "risk_mechanism_label",
            "mechanism",
            "mechanism_id",
            "risk_mechanism",
            "stress_type",
            "incident_type",
            "parameter_group",
            "lever_group",
            "changed_parameters",
            "kind",
        ),
    ) or "Mécanisme non renseigné"


def _normalise_metric_row(
    row: Mapping[str, object],
    *,
    table_name: str,
    index: int,
    context: Mapping[str, object] | None,
) -> dict[str, object]:
    enriched: dict[str, object] = dict(context or {})
    enriched.update(row)
    scenario = _scenario_id(enriched, f"{table_name}-{index + 1}")

    supplier_horizon = _pick_rate(
        enriched,
        (
            "supplier_service_horizon",
            "supplier_service_horizon_mean",
            "supplier_horizon_service",
            "supplier_service_rate",
            "supplier_fill_rate",
            "simulated_supplier_service",
            "supplier_service",
            "supplier_delivery_rate",
            "upstream_service_rate",
            "kpi::supplier_service_horizon",
            "kpi::supplier_fill_rate",
        ),
        include_any=(("supplier", "service"), ("supplier", "fill")),
        exclude=("p05", "p10", "p90", "p95", "due", "date", "proxy", "observed"),
    )
    supplier_due = _pick_rate(
        enriched,
        (
            "supplier_on_due_date_proxy",
            "supplier_on_due_date_proxy_mean",
            "supplier_service_due_proxy",
            "supplier_due_date_proxy",
            "supplier_service_at_due_date",
            "supplier_service_proxy",
            "supplier_otif_proxy",
            "kpi::supplier_on_due_date_proxy",
        ),
        include_any=(
            ("supplier", "due"),
            ("supplier", "date", "proxy"),
            ("supplier", "otif", "proxy"),
        ),
        exclude=("p05", "p10", "p90", "p95", "observed"),
    )
    supplier_metric_kind = "service fournisseur simulé sur l’horizon"
    supplier_metric_is_proxy = False
    if supplier_horizon is None:
        supplier_horizon = _pick_rate(
            enriched,
            (
                "supplier_weighted_reliability",
                "supplier_weighted_reliability_mean",
                "weighted_supplier_reliability",
            ),
        )
        if supplier_horizon is not None:
            supplier_metric_kind = "proxy de fiabilité fournisseur pondérée"
            supplier_metric_is_proxy = True
    if supplier_horizon is None:
        shipped = _to_float(
            _pick(
                enriched,
                (
                    "supplier_shipped_qty",
                    "supplier_shipped_qty_mean",
                    "supplier_shipments_qty",
                    "supplier_shipments_qty_mean",
                ),
            )
        )
        pulled = _to_float(
            _pick(
                enriched,
                (
                    "supplier_pulled_qty",
                    "supplier_pulled_qty_mean",
                    "supplier_requested_qty",
                    "supplier_requested_qty_mean",
                    "supplier_demand_qty",
                    "supplier_demand_qty_mean",
                ),
            )
        )
        if shipped is not None and pulled is not None and pulled > 0.0:
            supplier_horizon = max(0.0, min(1.25, shipped / pulled))
            supplier_metric_kind = "proxy fournisseur expédié / appelé"
            supplier_metric_is_proxy = True
    product_horizon = _pick_rate(
        enriched,
        (
            "target_fill_rate",
            "target_fill_rate_mean",
            "product_service_horizon",
            "client_service_horizon",
            "product_service_rate",
            "client_service_rate",
            "product_fill_rate",
            "client_fill_rate",
            "horizon_fill_rate",
            "fill_rate",
            "service_rate",
            "service_level",
            "mean_service",
            "kpi::product_service_horizon",
            "kpi::client_service_rate",
            "kpi::fill_rate",
        ),
        include_any=(
            ("product", "service"),
            ("client", "service"),
            ("product", "fill"),
            ("client", "fill"),
            ("fill", "268"),
        ),
        exclude=(
            "supplier",
            "p05",
            "p10",
            "p90",
            "p95",
            "due",
            "date",
            "proxy",
            "observed",
        ),
    )
    product_due = _pick_rate(
        enriched,
        (
            "target_on_due_volume_proxy",
            "target_on_due_volume_proxy_mean",
            "product_on_due_date_proxy",
            "client_on_due_date_proxy",
            "on_due_date_volume_proxy",
            "product_service_due_proxy",
            "client_service_due_proxy",
            "product_service_at_due_date",
            "client_service_at_due_date",
            "kpi::on_due_date_volume_proxy",
        ),
        include_any=(
            ("product", "due"),
            ("client", "due"),
            ("on", "due", "date", "proxy"),
            ("service", "date", "proxy"),
        ),
        exclude=("supplier", "p05", "p10", "p90", "p95", "observed"),
    )
    product_due_min = _pick_rate(
        enriched,
        (
            "product_on_due_date_proxy_min",
            "target_on_due_volume_proxy_min",
            "client_on_due_date_proxy_min",
        ),
    )
    product_due_max = _pick_rate(
        enriched,
        (
            "product_on_due_date_proxy_max",
            "target_on_due_volume_proxy_max",
            "client_on_due_date_proxy_max",
        ),
    )

    product_p10 = _pick_rate(
        enriched,
        (
            "product_service_p10",
            "client_service_p10",
            "fill_rate_p10",
            "service_p10",
            "p10_product_service",
        ),
        include_any=(("p10", "service"), ("p10", "fill")),
        exclude=("supplier",),
    )
    product_p90 = _pick_rate(
        enriched,
        (
            "product_service_p90",
            "client_service_p90",
            "fill_rate_p90",
            "service_p90",
            "p90_product_service",
        ),
        include_any=(("p90", "service"), ("p90", "fill")),
        exclude=("supplier",),
    )
    backlog = _to_float(
        _pick(
            enriched,
            (
                "target_backlog_qty_days",
                "target_backlog_qty_days_mean",
                "backlog_qty",
                "customer_backlog_qty",
                "ending_backlog",
                "mean_backlog",
                "total_backlog",
                "backlog",
                "kpi::backlog_qty",
            ),
            include_any=(("backlog",),),
        )
    )
    incremental_backlog = _to_float(
        _pick(
            enriched,
            (
                "incremental_target_backlog_qty_days",
                "incremental_target_backlog_qty_days_mean",
                "target_backlog_qty_days_delta_vs_paired_baseline",
                "target_backlog_qty_days_delta_vs_paired_baseline_mean",
            ),
            include_any=(("incremental", "backlog", "qty", "days"),),
        )
    )
    worst_rolling_28d_due = _pick_rate(
        enriched,
        (
            "target_worst_rolling_28d_on_due_proxy",
            "target_worst_rolling_28d_on_due_proxy_mean",
            "worst_rolling_28d_on_due_proxy",
            "worst_rolling_28d_on_due_proxy_mean",
        ),
        include_any=(("worst", "rolling", "28d", "on", "due"),),
        exclude=("delta", "baseline", "p05", "min", "max"),
    )
    baseline_worst_rolling_28d_due = _pick_rate(
        enriched,
        (
            "paired_baseline_target_worst_rolling_28d_on_due_proxy",
            "paired_baseline_target_worst_rolling_28d_on_due_proxy_mean",
            "baseline_target_worst_rolling_28d_on_due_proxy",
        ),
    )
    worst_rolling_28d_due_delta = _as_rate_delta(
        _pick(
            enriched,
            (
                "target_worst_rolling_28d_on_due_delta_vs_paired_baseline",
                "target_worst_rolling_28d_on_due_delta_vs_paired_baseline_mean",
                "worst_rolling_28d_on_due_delta_vs_baseline",
            ),
            include_any=(("worst", "rolling", "28d", "delta", "baseline"),),
        )
    )
    if (
        worst_rolling_28d_due_delta is None
        and baseline_worst_rolling_28d_due is not None
        and worst_rolling_28d_due is not None
    ):
        worst_rolling_28d_due_delta = (
            worst_rolling_28d_due - baseline_worst_rolling_28d_due
        )
    first_backlog_day = _to_float(
        _pick(
            enriched,
            (
                "target_first_backlog_day",
                "target_first_backlog_day_mean",
                "first_backlog_day",
                "first_backlog_day_mean",
            ),
        )
    )
    backlog_days = _to_float(
        _pick(
            enriched,
            (
                "target_backlog_days",
                "target_backlog_days_mean",
                "backlog_days",
                "backlog_days_mean",
            ),
        )
    )
    backlog_end_qty = _to_float(
        _pick(
            enriched,
            (
                "target_backlog_end_qty",
                "target_backlog_end_qty_mean",
                "backlog_end_qty",
                "backlog_end_qty_mean",
                "ending_backlog",
            ),
        )
    )
    level_index = _to_float(
        _pick(enriched, ("level_index", "severity_index", "business_level_index", "order_index"))
    )
    level_code = _pick_text(enriched, ("level_code", "severity_code", "business_level_code"))
    level_label = _pick_text(enriched, ("level_label", "severity_label", "business_level_label"))
    mechanism_value = _pick_text(
        enriched,
        ("mechanism_value", "physical_value", "stress_value", "level_value", "parameter_value"),
    )
    mechanism_unit = _pick_text(
        enriched,
        ("mechanism_unit", "physical_unit", "stress_unit", "level_unit", "parameter_unit"),
    )
    baseline_product_horizon = _pick_rate(
        enriched,
        (
            "shared_baseline_target_fill_rate_mean",
            "baseline_target_fill_rate_mean",
            "shared_baseline_fill_rate",
            "baseline_product_service_horizon",
            "baseline_fill_rate",
        ),
    )
    baseline_product_due = _pick_rate(
        enriched,
        (
            "paired_baseline_product_on_due_date_proxy",
            "paired_baseline_product_on_due_date_proxy_mean",
            "shared_baseline_target_on_due_volume_proxy_mean",
            "baseline_target_on_due_volume_proxy_mean",
            "baseline_product_on_due_date_proxy",
        ),
    )
    client_delta_vs_baseline = _as_rate_delta(
        _pick(
            enriched,
            (
                "target_fill_rate_delta_vs_baseline_mean",
                "delta_target_fill_rate_vs_baseline_mean",
                "delta_vs_baseline_target_fill_rate_mean",
                "client_service_delta_vs_baseline_mean",
                "product_service_delta_vs_baseline",
                "fill_rate_delta_vs_baseline",
            ),
            include_any=(("delta", "fill", "baseline"), ("delta", "service", "baseline")),
            exclude=("supplier",),
        )
    )
    client_loss_vs_baseline = _as_rate_delta(
        _pick(
            enriched,
            (
                "target_fill_rate_loss_vs_baseline_mean",
                "client_service_loss_vs_baseline_mean",
                "product_service_drop_vs_baseline",
                "fill_rate_drop_vs_baseline",
            ),
            include_any=(("loss", "fill", "baseline"), ("drop", "service", "baseline")),
            exclude=("supplier",),
        )
    )
    if client_delta_vs_baseline is None and baseline_product_horizon is not None and product_horizon is not None:
        client_delta_vs_baseline = product_horizon - baseline_product_horizon
    product_due_delta_vs_baseline = _as_rate_delta(
        _pick(
            enriched,
            (
                "target_on_due_date_proxy_delta_vs_paired_baseline",
                "target_on_due_date_proxy_delta_vs_paired_baseline_mean",
                "product_on_due_date_proxy_delta_vs_baseline",
                "client_on_due_date_proxy_delta_vs_baseline",
                "on_due_date_proxy_delta_vs_baseline",
            ),
            include_any=(("on", "due", "delta", "baseline"),),
            exclude=("supplier", "worst", "rolling"),
        )
    )
    product_due_loss_vs_baseline = _as_rate_delta(
        _pick(
            enriched,
            (
                "target_on_due_date_proxy_loss_vs_paired_baseline",
                "target_on_due_date_proxy_loss_vs_paired_baseline_mean",
                "product_on_due_date_proxy_loss_vs_baseline",
                "client_on_due_date_proxy_loss_vs_baseline",
            ),
            include_any=(("on", "due", "loss", "baseline"),),
            exclude=("supplier", "worst", "rolling"),
        )
    )
    if (
        product_due_delta_vs_baseline is None
        and baseline_product_due is not None
        and product_due is not None
    ):
        product_due_delta_vs_baseline = product_due - baseline_product_due
    if product_due_loss_vs_baseline is None and product_due_delta_vs_baseline is not None:
        product_due_loss_vs_baseline = max(0.0, -product_due_delta_vs_baseline)
    shared_baseline_id = _pick_text(
        enriched,
        ("shared_baseline_id", "baseline_scenario_id", "reference_scenario_id", "baseline_id"),
    )
    explicit_baseline = _pick(
        enriched,
        (
            "is_campaign_baseline",
            "is_baseline_alias",
            "is_baseline",
            "baseline",
            "is_reference",
            "reference",
        ),
    )
    is_baseline = _as_bool(explicit_baseline) if explicit_baseline is not None else (
        _normalise_key(level_code) in {"baseline", "reference", "nominal"}
        or _normalise_key(scenario).endswith("baseline")
    )
    repetition = _pick_text(enriched, ("seed", "replicate", "repetition", "run", "run_id"))
    n_repetitions = _to_float(
        _pick(enriched, ("n_seeds", "n_repetitions", "replicate_count", "run_count"))
    )
    repetitions = _pick_text(enriched, ("seeds", "repetitions", "replicates", "runs"))
    target_product_id = _pick_text(
        enriched,
        ("target_product_id", "product_id", "finished_product_id", "target_product"),
    )
    chain_id = _pick_text(enriched, ("chain_id", "cascade_id", "flow_id")) or _chain_label(enriched)
    mechanism_id = _pick_text(
        enriched,
        ("mechanism", "mechanism_id", "risk_mechanism", "stress_type", "incident_type"),
    ) or _mechanism_label(enriched)
    baseline_incident_pulled = _to_float(
        _pick(
            enriched,
            (
                "paired_baseline_supplier_incident_pulled_qty",
                "paired_baseline_supplier_incident_pulled_qty_mean",
            ),
        )
    )
    baseline_incident_shipped = _to_float(
        _pick(
            enriched,
            (
                "paired_baseline_supplier_incident_shipped_qty",
                "paired_baseline_supplier_incident_shipped_qty_mean",
            ),
        )
    )
    explicit_flow_exercised = _pick(
        enriched,
        (
            "paired_baseline_supplier_incident_flow_exercised",
            "baseline_incident_flow_exercised",
        ),
    )
    if explicit_flow_exercised is not None:
        baseline_incident_flow_exercised: bool | None = _as_bool(
            explicit_flow_exercised
        )
    elif baseline_incident_shipped is not None:
        # Older V4 screening rows already contain the shipped denominator but
        # predate the explicit flow flag and paired pulled field.
        baseline_incident_flow_exercised = (
            baseline_incident_shipped > 1e-12
            and (
                baseline_incident_pulled is None
                or baseline_incident_pulled > 1e-12
            )
        )
    else:
        baseline_incident_flow_exercised = None
    note = _pick_text(
        enriched,
        (
            "business_explanation",
            "business_note",
            "interpretation",
            "explanation",
            "description",
            "reading",
        ),
    )
    return {
        "scenario_id": scenario,
        "chain_id": chain_id,
        "chain": _chain_label(enriched),
        "mechanism_id": mechanism_id,
        "mechanism": _mechanism_label(enriched),
        "target_product_id": target_product_id,
        "phase": table_name,
        "repetition": repetition,
        "n_repetitions": n_repetitions,
        "repetitions": repetitions,
        "supplier_horizon": supplier_horizon,
        "supplier_due": supplier_due,
        "supplier_metric_kind": supplier_metric_kind,
        "supplier_metric_is_proxy": supplier_metric_is_proxy,
        "product_horizon": product_horizon,
        "product_due": product_due,
        "product_due_min": product_due_min,
        "product_due_max": product_due_max,
        "product_p10": product_p10,
        "product_p90": product_p90,
        "backlog": backlog,
        "incremental_backlog": incremental_backlog,
        "worst_rolling_28d_due": worst_rolling_28d_due,
        "baseline_worst_rolling_28d_due": baseline_worst_rolling_28d_due,
        "worst_rolling_28d_due_delta": worst_rolling_28d_due_delta,
        "first_backlog_day": first_backlog_day,
        "backlog_days": backlog_days,
        "backlog_end_qty": backlog_end_qty,
        "level_index": level_index,
        "level_code": level_code,
        "level_label": level_label,
        "mechanism_value": mechanism_value,
        "mechanism_unit": mechanism_unit,
        "level_display": _level_display(
            scenario=scenario,
            mechanism=mechanism_id,
            level_label=level_label,
            level_code=level_code,
            mechanism_value=mechanism_value,
            mechanism_unit=mechanism_unit,
        ),
        "baseline_product_horizon": baseline_product_horizon,
        "baseline_product_due": baseline_product_due,
        "client_delta_vs_baseline": client_delta_vs_baseline,
        "client_loss_vs_baseline": client_loss_vs_baseline,
        "product_due_delta_vs_baseline": product_due_delta_vs_baseline,
        "product_due_loss_vs_baseline": product_due_loss_vs_baseline,
        "shared_baseline_id": shared_baseline_id,
        "is_baseline": is_baseline,
        "baseline_incident_pulled_qty": baseline_incident_pulled,
        "baseline_incident_shipped_qty": baseline_incident_shipped,
        "baseline_incident_flow_exercised": baseline_incident_flow_exercised,
        "business_note": note,
    }


def _baseline_incident_flow_by_chain(
    tables: Mapping[str, Mapping[str, object]],
    contexts: Mapping[str, Mapping[str, object]],
) -> dict[str, dict[str, object]]:
    """Recover chain exercise status directly from paired baseline rows.

    This derivation also supports V4 screening CSVs written immediately before
    the explicit row-level flag was introduced.
    """

    chain_ids = sorted(
        {
            _pick_text(context, ("chain_id", "cascade_id", "flow_id"))
            for context in contexts.values()
            if _pick_text(context, ("chain_id", "cascade_id", "flow_id"))
            not in {"", "all"}
        }
    )
    confirmation_rows = tables.get("confirmation_metrics", {}).get("rows", [])
    screening_rows = tables.get("screening_metrics", {}).get("rows", [])
    candidates = confirmation_rows if isinstance(confirmation_rows, list) else []
    baseline_rows = [
        row
        for row in candidates
        if isinstance(row, Mapping)
        and _scenario_id(row, "") == "baseline_nominal"
    ]
    if not baseline_rows:
        baseline_rows = [
            row
            for row in (screening_rows if isinstance(screening_rows, list) else [])
            if isinstance(row, Mapping)
            and _scenario_id(row, "") == "baseline_nominal"
        ]

    result: dict[str, dict[str, object]] = {}
    for chain_id in chain_ids:
        prefix = f"baseline_chain__{chain_id}__"
        pulled = [
            value
            for value in (
                _to_float(row.get(f"{prefix}incident_pulled_qty"))
                for row in baseline_rows
            )
            if value is not None
        ]
        shipped = [
            value
            for value in (
                _to_float(row.get(f"{prefix}incident_shipped_qty"))
                for row in baseline_rows
            )
            if value is not None
        ]
        complete = bool(baseline_rows) and len(pulled) == len(
            baseline_rows
        ) and len(shipped) == len(baseline_rows)
        exercised = bool(
            complete
            and all(value > 1e-12 for value in pulled)
            and all(value > 1e-12 for value in shipped)
        )
        result[chain_id] = {
            "baseline_incident_pulled_qty": (
                sum(pulled) / len(pulled) if pulled else None
            ),
            "baseline_incident_shipped_qty": (
                sum(shipped) / len(shipped) if shipped else None
            ),
            "baseline_incident_flow_exercised": exercised,
            "baseline_incident_flow_evidence_complete": complete,
        }
    return result


def _normalise_tables(tables: Mapping[str, Mapping[str, object]]) -> dict[str, list[dict[str, object]]]:
    contexts = _design_context(tables["scenario_design"])
    baseline_flow = _baseline_incident_flow_by_chain(tables, contexts)
    result: dict[str, list[dict[str, object]]] = {}
    for table_name in (
        "screening_metrics",
        "confirmation_metrics",
        "scenario_summary",
        "worst_cases",
    ):
        rows = tables[table_name].get("rows", [])
        normalised: list[dict[str, object]] = []
        if isinstance(rows, list):
            for index, row in enumerate(rows):
                if not isinstance(row, Mapping):
                    continue
                scenario = _scenario_id(row, f"{table_name}-{index + 1}")
                record = _normalise_metric_row(
                    row,
                    table_name=table_name,
                    index=index,
                    context=contexts.get(scenario),
                )
                flow = baseline_flow.get(str(record.get("chain_id") or ""))
                if flow is not None:
                    record.update(flow)
                normalised.append(record)
        result[table_name] = normalised
        result[table_name].sort(
            key=lambda record: (
                str(record.get("chain") or ""),
                str(record.get("mechanism") or ""),
                float(record["level_index"])
                if isinstance(record.get("level_index"), (int, float))
                else math.inf,
                str(record.get("scenario_id") or ""),
                str(record.get("repetition") or ""),
            )
        )
    return result


def load_supplier_service_campaign(campaign_dir: str | Path) -> dict[str, object]:
    """Load all compact campaign files and derive presentation-friendly metrics."""
    root = Path(campaign_dir).resolve()
    if not root.is_dir():
        raise FileNotFoundError(f"Campaign directory not found: {root}")
    missing = [root / name for name in CAMPAIGN_FILES.values() if not (root / name).is_file()]
    if missing:
        raise FileNotFoundError(f"Missing compact campaign file: {missing[0]}")

    manifest = _read_json(root / CAMPAIGN_FILES["manifest"])
    tables = {
        key: _read_csv(root / filename)
        for key, filename in CAMPAIGN_FILES.items()
        if key != "manifest"
    }
    return {
        "schema_version": SCHEMA_VERSION,
        "manifest": manifest,
        "tables": tables,
        "normalised": _normalise_tables(tables),
        "display_contract": {
            "observed": "Données industrielles 2025, au niveau produit lorsqu’elles existent.",
            "simulated": "Résultats du moteur sous les configurations de campagne.",
            "hypothesis": "Paramètres, objectifs et faisabilité opérationnelle à confirmer.",
            "priority": "Configuration à instruire en premier, sans valeur de probabilité.",
        },
    }


def validate_supplier_service_campaign_for_dashboard(
    payload: Mapping[str, object],
    *,
    allow_incomplete_campaign: bool = False,
) -> None:
    """Refuse a final dashboard built from partial or invalid campaign evidence."""

    manifest = payload.get("manifest")
    tables = payload.get("tables")
    if not isinstance(manifest, Mapping) or not isinstance(tables, Mapping):
        raise ValueError("Campaign payload is missing its manifest or compact tables")

    status = _normalise_key(manifest.get("status"))
    if not allow_incomplete_campaign and status != "complete":
        raise ValueError(
            "Final dashboard requires campaign_manifest.json status=complete; "
            f"got {manifest.get('status')!r}"
        )

    for table_name in ("screening_metrics", "confirmation_metrics"):
        table = tables.get(table_name)
        rows = table.get("rows", []) if isinstance(table, Mapping) else []
        for index, row in enumerate(rows if isinstance(rows, list) else []):
            if not isinstance(row, Mapping):
                continue
            explicit = _pick(row, ("valid", "all_runs_valid"))
            if explicit is not None and not _as_bool(explicit):
                raise ValueError(f"Invalid run in {table_name}.csv at row {index + 2}")

    summary = tables.get("scenario_summary")
    summary_rows = summary.get("rows", []) if isinstance(summary, Mapping) else []
    for index, row in enumerate(summary_rows if isinstance(summary_rows, list) else []):
        if not isinstance(row, Mapping):
            continue
        explicit = _pick(row, ("all_runs_valid", "valid"))
        if explicit is not None and not _as_bool(explicit):
            raise ValueError(f"Invalid scenario in scenario_summary.csv at row {index + 2}")

    if allow_incomplete_campaign:
        return

    configured = manifest.get("confirmation_seeds")
    if not isinstance(configured, list) or len(configured) != 10:
        raise ValueError(
            "Final dashboard requires exactly 10 configured confirmation simulations"
        )
    expected = {str(value).strip() for value in configured}
    if len(expected) != 10 or "" in expected:
        raise ValueError("The 10 configured confirmation simulations must be distinct")
    confirmation = tables.get("confirmation_metrics")
    confirmation_rows = (
        confirmation.get("rows", []) if isinstance(confirmation, Mapping) else []
    )
    if not isinstance(confirmation_rows, list) or not confirmation_rows:
        raise ValueError("Final dashboard requires confirmation_metrics.csv")
    repetitions_by_scenario: dict[str, set[str]] = {}
    rows_by_scenario: dict[str, int] = {}
    for index, row in enumerate(confirmation_rows):
        if not isinstance(row, Mapping):
            continue
        scenario = _scenario_id(row, f"confirmation-{index + 1}")
        repetitions_by_scenario.setdefault(scenario, set())
        rows_by_scenario[scenario] = rows_by_scenario.get(scenario, 0) + 1
        repetition = _pick_text(row, ("seed", "replicate", "repetition", "run"))
        if repetition:
            repetitions_by_scenario[scenario].add(repetition)
    missing = [
        scenario
        for scenario, repetitions in sorted(repetitions_by_scenario.items())
        if repetitions != expected or rows_by_scenario.get(scenario) != len(expected)
    ]
    if not repetitions_by_scenario or missing:
        detail = f"; incomplete scenarios: {', '.join(missing[:5])}" if missing else ""
        raise ValueError(
            "Every confirmed scenario must contain the same 10 configured simulations"
            + detail
        )
def _json_for_script(payload: object) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
    return (
        encoded.replace("&", "\\u0026")
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
        .replace("\u2028", "\\u2028")
        .replace("\u2029", "\\u2029")
        .replace("http:", "http\\u003a")
        .replace("https:", "https\\u003a")
    )


HTML_TEMPLATE = r'''<!doctype html>
<html lang="fr">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>Configurations de service produit et leviers fournisseurs</title>
  <style>
    :root{--navy:#0b2748;--blue:#246bfe;--green:#11875d;--amber:#a55b00;--red:#bb2d24;--ink:#10233f;--muted:#5b6c7f;--paper:#eef3f8;--line:#d7e1ec;--card:#fff;--shadow:0 12px 34px rgba(15,39,67,.09)}
    *{box-sizing:border-box}html{scroll-behavior:smooth}body{margin:0;background:var(--paper);color:var(--ink);font:15px/1.5 Inter,Segoe UI,Arial,sans-serif}
    header{padding:34px max(22px,calc((100vw - 1240px)/2));background:linear-gradient(125deg,#071a31,#123d70 62%,#0c6f67);color:#fff}header .eyebrow{color:#91ead6}header h1{max-width:1050px;margin:8px 0 12px;font-size:clamp(34px,5vw,58px);line-height:1.05}header p{max-width:960px;margin:0;color:#dceaf7;font-size:18px}
    .route{position:sticky;top:0;z-index:20;display:flex;gap:8px;overflow:auto;padding:10px max(18px,calc((100vw - 1240px)/2));background:#0b2748;box-shadow:0 7px 20px rgba(15,39,67,.16)}.route button{border:1px solid rgba(255,255,255,.3);border-radius:999px;padding:8px 13px;background:transparent;color:#e8f2fb;font-weight:800;white-space:nowrap;cursor:pointer}.route button.active{background:#fff;color:#0b2748}
    .guardrails{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px;max-width:1240px;margin:18px auto 0;padding:0 22px}.guard{background:#fff;border:1px solid var(--line);border-top:5px solid #64748b;border-radius:13px;padding:13px;box-shadow:var(--shadow)}.guard.sim{border-top-color:var(--green)}.guard.hyp{border-top-color:var(--amber)}.guard.prio{border-top-color:var(--blue)}.guard b{display:block;font-size:12px;letter-spacing:.05em}.guard p{margin:5px 0 0;color:var(--muted);font-size:13px}
    .permanent-warning{max-width:1196px;margin:12px auto 0;padding:13px 16px;border:1px solid #edc890;border-radius:13px;background:#fff6e8;color:#774500}.permanent-warning strong{color:#5c3300}
    main{max-width:1240px;margin:auto;padding:20px 22px 60px}.view{display:none}.view.active{display:block}.view-head{margin:18px 0}.view-head .eyebrow,.section-title .eyebrow{color:var(--blue);font-size:12px;font-weight:900;letter-spacing:.11em}.view-head h2{margin:5px 0 8px;font-size:clamp(28px,4vw,43px);line-height:1.1}.view-head p{max-width:920px;color:var(--muted);font-size:17px}
    .filters{display:flex;gap:12px;flex-wrap:wrap;margin:18px 0;padding:15px;background:#fff;border:1px solid var(--line);border-radius:15px;box-shadow:var(--shadow)}.filters label{display:grid;gap:5px;min-width:min(100%,290px);font-weight:800}.filters select{min-height:42px;border:1px solid #b7c7d9;border-radius:10px;background:#fff;padding:8px;color:var(--ink)}
    .chart-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px}.chart-card,.panel{background:#fff;border:1px solid var(--line);border-radius:16px;padding:17px;box-shadow:var(--shadow)}.chart-card h3,.panel h3{margin:0 0 4px}.chart-card>p,.panel>p{margin:0 0 10px;color:var(--muted)}svg.service-curve,svg.service-scatter{display:block;width:100%;height:auto;min-height:270px;background:#fbfdff;border:1px solid #e2eaf2;border-radius:12px}.chart-legend{display:flex;gap:14px;flex-wrap:wrap;margin-top:9px;color:var(--muted);font-size:12px}.chart-legend span::before{content:"";display:inline-block;width:18px;height:3px;margin-right:5px;vertical-align:3px;background:var(--green)}.chart-legend span.due::before{background:var(--blue)}
    .reading{margin:15px 0;padding:15px 17px;border-left:5px solid var(--blue);border-radius:12px;background:#eaf1ff;color:#173d69}.reading strong{color:#0b2748}.empty-note{padding:30px;text-align:center;fill:#607287;font-size:13px}
    .stats-grid{display:grid;grid-template-columns:minmax(0,.9fr) minmax(520px,1.1fr);gap:14px;align-items:start}.influence-panel{margin:0 0 14px}.influence-list{display:grid;gap:8px;margin:12px 0 0;padding:0;list-style:none}.influence-list li{display:grid;grid-template-columns:minmax(180px,1fr) minmax(100px,.7fr) auto;gap:10px;align-items:center;padding:9px 11px;border:1px solid #dce6f0;border-radius:10px;background:#fbfdff}.influence-bar{height:8px;border-radius:999px;background:#dfe8f4;overflow:hidden}.influence-bar i{display:block;height:100%;background:var(--blue)}.influence-value{font-weight:900;color:#15395f;white-space:nowrap}.method-limit{margin:10px 0 14px;padding:12px 14px;border:1px solid #edc890;border-radius:11px;background:#fff6e8;color:#714300}.unexercised-warning{margin:0 0 14px;padding:12px 14px;border:1px solid #e3a8a3;border-radius:11px;background:#fff1f0;color:#7e2420}.table-wrap{overflow:auto;background:#fff;border:1px solid var(--line);border-radius:15px;box-shadow:var(--shadow)}table{width:100%;border-collapse:collapse;min-width:1450px}th,td{padding:11px 12px;border-bottom:1px solid #e4eaf1;text-align:left;vertical-align:top}th{position:sticky;top:0;background:#eaf1f9;color:#15395f;font-size:12px}td{font-size:13px}tr.not-exercised td{background:#fff7f6;color:#713a37}.metric{font-variant-numeric:tabular-nums;white-space:nowrap}.phase{display:inline-block;border-radius:999px;padding:3px 7px;background:#edf3ff;color:#19569b;font-size:10px;font-weight:900}.run-distribution summary{cursor:pointer;color:#184f8d;font-weight:800;white-space:nowrap}.run-values{max-width:330px;margin-top:5px;color:var(--muted);font-size:11px;line-height:1.45}.table-note{margin:10px 0 18px;color:var(--muted);font-size:13px}
    .workflow{display:flex;align-items:center;gap:7px;flex-wrap:wrap;margin:14px 0 19px;padding:14px;background:#fff;border:1px solid var(--line);border-radius:14px}.workflow span{padding:7px 10px;border-radius:999px;background:#edf3ff;color:#154f9b;font-weight:850}.workflow b{color:#8796a6}.action-warning{padding:15px;border-radius:13px;background:#fff6e8;border:1px solid #edc890;color:#714300}.actions{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:13px;margin-top:15px}.action{background:#fff;border:1px solid var(--line);border-top:5px solid var(--blue);border-radius:15px;padding:16px;box-shadow:var(--shadow)}.action h3{font-size:18px}.action dl{display:grid;grid-template-columns:105px 1fr;gap:5px 9px;margin:10px 0;color:var(--muted);font-size:13px}.action dt{font-weight:850;color:#324c67}.action dd{margin:0}.action label{display:flex;align-items:center;gap:8px;margin-top:12px;font-weight:850}.action select{flex:1;min-height:38px;border:1px solid #b7c7d9;border-radius:9px;background:#fff;padding:6px}.action[data-state="confirmed"]{border-top-color:var(--amber)}.action[data-state="executed"]{border-top-color:var(--green)}.action[data-state="refused"]{border-top-color:var(--red)}
    .decision-contract{margin-top:18px;padding:16px;background:#e9f7f1;border:1px solid #9dd3c2;border-radius:14px;color:#165b49}.decision-contract ul{margin:8px 0 0;padding-left:20px}.source-note{margin-top:25px;color:var(--muted);font-size:12px}
    @media(max-width:940px){.guardrails{grid-template-columns:1fr 1fr}.chart-grid,.stats-grid,.actions{grid-template-columns:1fr}.stats-grid{display:grid}.route{padding-left:14px}}
    @media(max-width:590px){.guardrails{grid-template-columns:1fr}.action dl{grid-template-columns:1fr}.action dd{margin-bottom:5px}}
  </style>
</head>
<body>
  <header>
    <div class="eyebrow">CONFIGURATIONS DE SERVICE PRODUIT ET LEVIERS FOURNISSEURS</div>
    <h1>Du fonctionnement fournisseur à l’effet client</h1>
    <p>Cette page explique quelles configurations fragilisent la chaîne, comment leurs effets se propagent jusqu’au produit et quelles décisions concrètes doivent ensuite être instruites.</p>
  </header>
  <nav class="route" aria-label="Parcours en trois vues">
    <button type="button" class="active" data-view-target="view-flow">1/3 · Du fournisseur au client</button>
    <button type="button" data-view-target="view-fragile">2/3 · Les configurations les plus fragiles</button>
    <button type="button" data-view-target="view-actions">3/3 · Décisions à tester</button>
  </nav>
  <aside class="guardrails" aria-label="Cadre de lecture permanent">
    <article class="guard"><b>OBSERVÉ 2025</b><p>Données produit utilisées comme entrées ; aucune performance fournisseur observée n’est affichée ici.</p></article>
    <article class="guard sim"><b>SIMULÉ</b><p>Résultat produit par le moteur sous une configuration définie.</p></article>
    <article class="guard hyp"><b>HYPOTHÈSE À CONFIRMER</b><p>Paramètre, objectif ou faisabilité à valider avec les équipes.</p></article>
    <article class="guard prio"><b>SIGNAL DE PRIORITÉ</b><p>Configuration à examiner d’abord ; ce n’est pas une probabilité d’incident.</p></article>
  </aside>
  <p class="permanent-warning"><strong>Point de méthode :</strong> aucun OTIF fournisseur observé n’est disponible. Les repères 80 % et 93 % désignent ici une part simulée du volume produit servie à la date attendue, pas un taux fournisseur observé. Leur définition industrielle reste à confirmer : commande, ligne, quantité ou valeur ; date demandée ou confirmée ; période et règle de rattrapage.</p>

  <main>
    <section id="view-flow" class="view active" data-view="1">
      <div class="view-head"><div class="eyebrow">VUE 1 · PROPAGATION</div><h2>Du fournisseur au client</h2><p>Les courbes séparent le service sur tout l’horizon du volume servi à la date attendue. Elles représentent des résultats simulés ou des proxys, jamais un OTIF fournisseur historique.</p></div>
      <div class="filters" aria-label="Filtres de la campagne">
        <label>Chaîne<select id="chain-filter" data-filter="chain"><option value="">Toutes les chaînes</option></select></label>
        <label>Mécanisme<select id="mechanism-filter" data-filter="mechanism"><option value="">Tous les mécanismes</option></select></label>
      </div>
      <p id="unexercised-chain-warning" class="unexercised-warning" hidden></p>
      <div class="chart-grid">
        <article class="chart-card"><h3>Flux fournisseur simulé ou proxy</h3><p>Quantité utile disponible sur l’horizon et approximation de la quantité disponible à la date attendue.</p><svg id="supplier-service-chart" class="service-curve" viewBox="0 0 680 300" role="img" aria-label="Courbes de flux fournisseur simulé et proxy"></svg><div class="chart-legend"><span id="supplier-horizon-legend">Indicateur fournisseur sur l’horizon</span><span class="due">Disponible à date — proxy</span></div></article>
        <article class="chart-card"><h3>Service du produit au client</h3><p>Part du volume finalement servie et approximation de la part servie à la date attendue.</p><svg id="product-service-chart" class="service-curve" viewBox="0 0 680 300" role="img" aria-label="Courbes de service produit client"></svg><div class="chart-legend"><span>Servi avant la fin de l’horizon</span><span class="due">Servi à la date attendue — proxy</span></div></article>
      </div>
      <p id="flow-reading" class="reading"><strong>Lecture :</strong> sélectionnez une chaîne et un mécanisme pour comparer les configurations disponibles.</p>
    </section>

    <section id="view-fragile" class="view" data-view="2">
      <div class="view-head"><div class="eyebrow">VUE 2 · CONFIGURATIONS</div><h2>Les configurations les plus fragiles</h2><p>Une configuration est prioritaire lorsqu’elle réduit le volume servi à la date attendue. Le retard cumulé et le creux sur 28 jours départagent ensuite les cas, sans additionner des unités différentes.</p></div>
      <article class="panel influence-panel"><h3>Impacts maximaux confirmés parmi les niveaux testés</h3><p id="influence-method">Tri successif : perte de service à date, retard cumulé supplémentaire, puis pire fenêtre de 28 jours. Il ne s’agit ni d’un score composite ni d’une importance causale universelle.</p><p id="mechanism-equivalence-warning" class="method-limit" hidden></p><ol id="mechanism-ranking" class="influence-list"></ol></article>
      <div class="stats-grid">
        <article class="chart-card"><h3>Disponible à date côté fournisseur et servi à date côté client</h3><p>Chaque point représente une configuration simulée. Le service final n’est pas utilisé sur ces axes, car il peut masquer un retard ensuite rattrapé.</p><svg id="fragility-scatter" class="service-scatter" viewBox="0 0 620 430" role="img" aria-label="Nuage des configurations à date fournisseur et client"></svg></article>
        <article class="panel"><h3>Comment lire les dix simulations</h3><p><strong>Moyenne et min–max</strong> portent sur la part du volume servie à la date attendue. Les dix valeurs individuelles sont consultables dans le tableau.</p><p>Ces dix simulations appariées testent la stabilité du résultat dans le moteur. Leur min–max n’est ni une probabilité industrielle, ni un intervalle de confiance, ni une prévision de fréquence de l’incident.</p><p><strong>Retard cumulé supplémentaire</strong> est la somme quotidienne du volume en retard par rapport à la référence, en unités·jours. La chronologie indique le premier retard, le nombre de jours touchés et le retard encore présent en fin de simulation. Le résumé compact actuel ne permet pas de dater le retour définitif à zéro.</p></article>
      </div>
      <p class="table-note">Une confirmation comporte dix simulations, chacune comparée à sa propre référence avec le même tirage aléatoire. Un résultat issu du premier balayage reste signalé « à confirmer ». « Plus défavorable » signifie uniquement plus défavorable parmi les hypothèses testées, pas pire cas possible.</p>
      <div class="table-wrap"><table aria-label="Configurations fragiles"><thead><tr><th>Hypothèse physique testée</th><th>Chaîne</th><th>Mécanisme</th><th>Preuve</th><th>Disponible fournisseur à date</th><th>Servi client à date — moyenne</th><th>Résultats individuels et min–max</th><th>Perte à date vs référence</th><th>Retard cumulé supplémentaire<br>(unités·jours)</th><th>Pire fenêtre glissante de 28 jours</th><th>Chronologie et état en fin d’horizon</th><th>Service à fin d’horizon</th><th>Lecture métier</th></tr></thead><tbody id="fragility-body"></tbody></table></div>
    </section>

    <section id="view-actions" class="view" data-view="3">
      <div class="view-head"><div class="eyebrow">VUE 3 · DÉCISIONS</div><h2>Décisions à tester</h2><p>Un paramètre sensible n’est pas encore une action. Il doit être traduit en commande précise, avec un responsable, un objet physique, une date, une autorisation et une preuve d’exécution.</p></div>
      <p class="action-warning"><strong>Garde-fou :</strong> cette campagne de sensibilité est exécutée en boucle ouverte : aucun régulateur automatique ne choisit ni n’applique ces actions. Les leviers ci-dessous sont des décisions candidates à instruire ; ils ne sont pas des décisions simulées dans cette campagne et leur disponibilité terrain reste à confirmer.</p>
      <div class="workflow" aria-label="Statut des décisions"><span>Demandé</span><b>→</b><span>Confirmé</span><b>→</b><span>Exécuté</span><b>ou</b><span>Refusé</span></div>
      <div class="actions">
        <article class="action" data-state="requested"><h3>Réserver un transport sur une expédition identifiée</h3><dl><dt>Commande</dt><dd>Expédition, mode, départ, jours gagnés et surcoût maximal.</dd><dt>Responsable</dt><dd>Approvisionnement et logistique.</dd><dt>Condition</dt><dd>Une matière conforme existe et le transporteur confirme le créneau.</dd></dl><label>Statut<select class="action-status"><option value="requested">Demandé</option><option value="confirmed">Confirmé</option><option value="executed">Exécuté</option><option value="refused">Refusé</option></select></label></article>
        <article class="action" data-state="requested"><h3>Prépositionner un stock conforme avant la période de risque</h3><dl><dt>Commande</dt><dd>Article, quantité, site, date de disponibilité et commandes associées.</dd><dt>Responsable</dt><dd>Planification et approvisionnement.</dd><dt>Condition</dt><dd>Stock physiquement reçu, libéré et financé avant l’incident.</dd></dl><label>Statut<select class="action-status"><option value="requested">Demandé</option><option value="confirmed">Confirmé</option><option value="executed">Exécuté</option><option value="refused">Refusé</option></select></label></article>
        <article class="action" data-state="requested"><h3>Transférer ou réaffecter un lot déjà libéré</h3><dl><dt>Commande</dt><dd>Lot, quantité, site ou ordre source, destination et date.</dd><dt>Responsable</dt><dd>Qualité, planification et logistique.</dd><dt>Condition</dt><dd>Lot traçable, conforme et non engagé sur une priorité supérieure.</dd></dl><label>Statut<select class="action-status"><option value="requested">Demandé</option><option value="confirmed">Confirmé</option><option value="executed">Exécuté</option><option value="refused">Refusé</option></select></label></article>
        <article class="action" data-state="requested"><h3>Réserver une capacité chez une source approuvée</h3><dl><dt>Commande</dt><dd>Fournisseur-article-site, quantité journalière, fenêtre et engagement contractuel.</dd><dt>Responsable</dt><dd>Achats et qualité fournisseur.</dd><dt>Condition</dt><dd>Source qualifiée, capacité confirmée et délai de montée en charge compatible.</dd></dl><label>Statut<select class="action-status"><option value="requested">Demandé</option><option value="confirmed">Confirmé</option><option value="executed">Exécuté</option><option value="refused">Refusé</option></select></label></article>
        <article class="action" data-state="requested"><h3>Activer un lot de remplacement ou une source qualifiée</h3><dl><dt>Commande</dt><dd>Lot ou source, quantité, certificat, date d’expédition et contrôle d’entrée.</dd><dt>Responsable</dt><dd>Achats, qualité fournisseur et approvisionnement.</dd><dt>Condition</dt><dd>Homologation valide, matière disponible et compatibilité technique.</dd></dl><label>Statut<select class="action-status"><option value="requested">Demandé</option><option value="confirmed">Confirmé</option><option value="executed">Exécuté</option><option value="refused">Refusé</option></select></label></article>
        <article class="action" data-state="requested"><h3>Limiter la retenue qualité aux lots réellement concernés</h3><dl><dt>Commande</dt><dd>Lots bloqués, lots maintenus disponibles et productions à arrêter.</dd><dt>Responsable</dt><dd>Qualité, magasin et production.</dd><dt>Condition</dt><dd>Généalogie fiable entre livraison, matière, intermédiaire, produit et client.</dd></dl><label>Statut<select class="action-status"><option value="requested">Demandé</option><option value="confirmed">Confirmé</option><option value="executed">Exécuté</option><option value="refused">Refusé</option></select></label></article>
        <article class="action" data-state="requested"><h3>Prioriser et paralléliser les analyses autorisées</h3><dl><dt>Commande</dt><dd>Priorité, heures laboratoire, essais parallèles et laboratoire de secours.</dd><dt>Responsable</dt><dd>Responsable qualité et laboratoire.</dd><dt>Condition</dt><dd>Méthodes, ressources et laboratoire déjà qualifiés ; aucune issue favorable garantie.</dd></dl><label>Statut<select class="action-status"><option value="requested">Demandé</option><option value="confirmed">Confirmé</option><option value="executed">Exécuté</option><option value="refused">Refusé</option></select></label></article>
        <article class="action" data-state="requested"><h3>Affecter explicitement la matière aux OF et clients prioritaires</h3><dl><dt>Commande</dt><dd>Liste ordonnée des OF et commandes, quantités attribuées et dates promises.</dd><dt>Responsable</dt><dd>Planification, production et service clients.</dd><dt>Condition</dt><dd>Capacités finies, changements de campagne et retard déplacé rendus visibles.</dd></dl><label>Statut<select class="action-status"><option value="requested">Demandé</option><option value="confirmed">Confirmé</option><option value="executed">Exécuté</option><option value="refused">Refusé</option></select></label></article>
      </div>
      <aside class="decision-contract"><strong>Une action devient démontrable lorsqu’on enregistre :</strong><ul><li>l’objet exact — commande, expédition, lot, stock ou OF ;</li><li>la valeur demandée, la date, le responsable et les autorisations ;</li><li>la valeur réellement exécutée, son coût et son délai de mise en œuvre ;</li><li>l’effet sur les lots, le service client, le backlog et le risque restant.</li></ul></aside>
      <p class="source-note">Fichier autonome généré à partir des six fichiers compacts de campagne. Aucun recalcul de simulation n’est effectué dans cette page.</p>
    </section>
  </main>

  <script id="campaign-data" type="application/json">__PAYLOAD_JSON__</script>
  <script>
  (() => {
    "use strict";
    const payload = JSON.parse(document.getElementById("campaign-data").textContent);
    const NS = "h" + "ttp" + ":" + "/" + "/" + "www.w3.org/2000/svg";
    const phaseNames = {confirmation_metrics:"Confirmation",screening_metrics:"Screening",scenario_summary:"Synthèse",worst_cases:"Cas défavorable"};
    const phasePriority = {confirmation_metrics:4,screening_metrics:3,scenario_summary:2,worst_cases:1};
    const finite = value => typeof value === "number" && Number.isFinite(value);
    const percent = value => finite(value) ? new Intl.NumberFormat("fr-FR",{style:"percent",minimumFractionDigits:1,maximumFractionDigits:1}).format(value) : "—";
    const number = value => finite(value) ? new Intl.NumberFormat("fr-FR",{maximumFractionDigits:1}).format(value) : "—";
    const points = value => finite(value) ? `${value>=0?"+":"−"}${Math.abs(value*100).toFixed(1).replace(".",",")} pt` : "—";
    const mean = values => values.length ? values.reduce((sum,value)=>sum+value,0)/values.length : null;
    const quantile = (values, q) => {
      const sorted = values.filter(finite).slice().sort((a,b)=>a-b);
      if (!sorted.length) return null;
      const position = (sorted.length-1)*q;
      const low = Math.floor(position), high = Math.ceil(position);
      if (low === high) return sorted[low];
      return sorted[low] + (sorted[high]-sorted[low])*(position-low);
    };
    const el = (name, attrs={}) => {
      const node = document.createElementNS(NS,name);
      Object.entries(attrs).forEach(([key,value])=>node.setAttribute(key,String(value)));
      return node;
    };
    const addText = (svg,x,y,textValue,attrs={}) => {
      const node=el("text",{x,y,"font-family":"Segoe UI,Arial","font-size":"11",fill:"#617286",...attrs});
      node.textContent=textValue; svg.appendChild(node); return node;
    };

    const normalised = payload.normalised || {};
    const metricPhases = ["confirmation_metrics","screening_metrics","scenario_summary","worst_cases"];
    const allRecords = metricPhases.flatMap(phase => (normalised[phase] || []).map(row=>({...row,phase})));
    const horizonDays = Number(payload.manifest?.days);
    const equivalenceWarning=document.getElementById("mechanism-equivalence-warning");
    if(payload.manifest?.mechanism_equivalence_warning){
      equivalenceWarning.hidden=false;
      equivalenceWarning.textContent="Limite du moteur : la fiabilité d’expédition et le rendement qualité représentent deux causes métier différentes, mais produisent actuellement une perte quantitative presque équivalente. Leurs effets ne doivent ni être additionnés ni présentés comme deux facteurs indépendants.";
    }
    const scenarioKey = row => JSON.stringify([row.scenario_id||"",row.chain_id||row.chain||"",row.mechanism_id||row.mechanism||""]);
    const pairKey = group => JSON.stringify([group.chainId||group.chain||"",group.mechanismId||group.mechanism||""]);

    function preferredRecords() {
      const byScenario = new Map();
      allRecords.forEach(row => {
        const key = scenarioKey(row);
        const current = byScenario.get(key);
        const priority = phasePriority[row.phase] || 0;
        if (!current || priority > current.priority) byScenario.set(key,{priority,rows:[row]});
        else if (priority === current.priority) current.rows.push(row);
      });
      return [...byScenario.values()].flatMap(entry=>entry.rows);
    }

    const selected = {chain:"",mechanism:""};
    function filteredRecords() {
      return preferredRecords().filter(row => (!selected.chain || row.chain===selected.chain) && (!selected.mechanism || row.mechanism===selected.mechanism));
    }

    function populateFilter(id, field, allLabel) {
      const select=document.getElementById(id);
      const values=[...new Set(preferredRecords().map(row=>row[field]).filter(Boolean))].sort((a,b)=>a.localeCompare(b,"fr"));
      select.textContent="";
      const first=document.createElement("option"); first.value=""; first.textContent=allLabel; select.appendChild(first);
      values.forEach(value=>{const option=document.createElement("option");option.value=value;option.textContent=value;select.appendChild(option);});
      select.addEventListener("change",()=>{selected[field]=select.value;renderAll();});
    }

    function groupRows(records) {
      const groups=new Map();
      records.forEach(row=>{
        const key=scenarioKey(row);
        if(!groups.has(key)) groups.set(key,[]);
        groups.get(key).push(row);
      });
      return [...groups.values()].map(rows=>{
        const scenario=rows[0]?.scenario_id||"Configuration non nommée";
        const values = field => rows.map(row=>row[field]).filter(finite);
        const dueValues=values("product_due");
        const dueDelta=mean(values("product_due_delta_vs_baseline"));
        const explicitDueLoss=mean(values("product_due_loss_vs_baseline"));
        const baselineDue=mean(values("baseline_product_due"));
        const productDue=mean(dueValues);
        const dueLoss=finite(explicitDueLoss)?Math.max(0,explicitDueLoss):(finite(dueDelta)?Math.max(0,-dueDelta):(finite(baselineDue)&&finite(productDue)?Math.max(0,baselineDue-productDue):null));
        const worst28=mean(values("worst_rolling_28d_due"));
        const worst28Delta=mean(values("worst_rolling_28d_due_delta"));
        const baselineWorst28=mean(values("baseline_worst_rolling_28d_due"));
        const worst28Loss=finite(worst28Delta)?Math.max(0,-worst28Delta):(finite(baselineWorst28)&&finite(worst28)?Math.max(0,baselineWorst28-worst28):(finite(worst28)?Math.max(0,1-worst28):null));
        const firstBacklogDay=mean(values("first_backlog_day").filter(value=>value>=0));
        const backlogDays=mean(values("backlog_days"));
        const backlogEndQty=mean(values("backlog_end_qty"));
        const flowFlags=rows.map(row=>row.baseline_incident_flow_exercised).filter(value=>typeof value==="boolean");
        const baselineFlowExercised=flowFlags.includes(false)?false:(flowFlags.length?true:null);
        const runValues=rows.filter(row=>finite(row.product_due)).map((row,index)=>({
          repetition:row.repetition||`calcul-${index+1}`,value:row.product_due
        })).sort((a,b)=>String(a.repetition).localeCompare(String(b.repetition),"fr",{numeric:true}));
        const listedRepetitions=[...new Set(rows.flatMap(row=>String(row.repetitions||"").split("|")).filter(Boolean))];
        const declaredCount=Math.max(0,...values("n_repetitions"));
        const runCount=Math.max(runValues.length,listedRepetitions.length,declaredCount);
        const explicitMin=rows.map(row=>row.product_due_min).find(finite);
        const explicitMax=rows.map(row=>row.product_due_max).find(finite);
        return {
          scenario, rows, chainId:rows[0]?.chain_id||rows[0]?.chain||"—",chain:rows[0]?.chain||"—",
          mechanismId:rows[0]?.mechanism_id||rows[0]?.mechanism||"—",mechanism:rows[0]?.mechanism||"—",
          targetProduct:rows.map(row=>row.target_product_id).find(Boolean)||"",phase:rows[0]?.phase||"",
          supplierHorizon:mean(values("supplier_horizon")), supplierDue:mean(values("supplier_due")),
          supplierMetricKinds:[...new Set(rows.map(row=>row.supplier_metric_kind).filter(Boolean))],
          productHorizon:mean(values("product_horizon")),productDue,dueDelta,dueLoss,baselineDue,
          dueMin:finite(explicitMin)?explicitMin:(dueValues.length?Math.min(...dueValues):null),
          dueMax:finite(explicitMax)?explicitMax:(dueValues.length?Math.max(...dueValues):null),
          runValues,runCount,listedRepetitions,
          backlog:mean(values("backlog")),incrementalBacklog:mean(values("incremental_backlog")),
          worst28,worst28Delta,worst28Loss,firstBacklogDay,backlogDays,backlogEndQty,
          baselineFlowExercised,
          baselineIncidentPulled:mean(values("baseline_incident_pulled_qty")),
          baselineIncidentShipped:mean(values("baseline_incident_shipped_qty")),
          note:rows.map(row=>row.business_note).find(Boolean)||"",
          levelIndex:mean(values("level_index")), levelCode:rows.map(row=>row.level_code).find(Boolean)||"",
          levelLabel:rows.map(row=>row.level_label).find(Boolean)||"", levelDisplay:rows.map(row=>row.level_display).find(Boolean)||scenario,
          mechanismValue:rows.map(row=>row.mechanism_value).find(value=>value!==null&&value!==undefined&&value!=="")??"",
          mechanismUnit:rows.map(row=>row.mechanism_unit).find(Boolean)||"",
          baselineProduct:mean(values("baseline_product_horizon")),
          sharedBaselineId:rows.map(row=>row.shared_baseline_id).find(Boolean)||"", isBaseline:rows.some(row=>row.is_baseline===true)
        };
      }).sort((a,b)=>a.chain.localeCompare(b.chain,"fr")||a.mechanism.localeCompare(b.mechanism,"fr")||levelOrder(a)-levelOrder(b)||a.scenario.localeCompare(b.scenario,"fr"));
    }

    function levelOrder(group){
      if(finite(group.levelIndex))return group.levelIndex;
      const label=`${group.levelCode} ${group.levelLabel}`.toLowerCase();
      if(label.includes("excellent"))return 0;
      if(label.includes("nominal")||label.includes("référence")||label.includes("reference")||label.includes("baseline"))return 1;
      if(label.includes("vigil"))return 2;
      if(label.includes("dégrad")||label.includes("degrad"))return 3;
      if(label.includes("criti"))return 4;
      return 999;
    }

    function clearSvg(svg) { while(svg.firstChild) svg.removeChild(svg.firstChild); }
    function emptySvg(svg,message) { clearSvg(svg); addText(svg,340,150,message,{"text-anchor":"middle","font-size":"13"}); }
    function drawLineChart(svg, groups, horizonField, dueField) {
      clearSvg(svg);
      const usable=groups.filter(group=>group.baselineFlowExercised!==false&&(finite(group[horizonField])||finite(group[dueField]))).slice().sort((a,b)=>levelOrder(a)-levelOrder(b)||a.scenario.localeCompare(b.scenario,"fr"));
      if(!usable.length){emptySvg(svg,"Aucune métrique reconnue dans les colonnes disponibles");return;}
      if(new Set(usable.map(pairKey)).size>1){emptySvg(svg,"Affinez les filtres : une courbe ne relie qu’une chaîne et un mécanisme");return;}
      const left=54,right=658,top=24,bottom=245,width=right-left,height=bottom-top;
      [0,.25,.5,.75,1].forEach(value=>{
        const y=bottom-value*height;svg.appendChild(el("line",{x1:left,y1:y,x2:right,y2:y,stroke:"#dfe7ef"}));addText(svg,left-8,y+4,`${Math.round(value*100)}%`,{"text-anchor":"end"});
      });
      const x=index=>usable.length===1?(left+right)/2:left+index*width/(usable.length-1);
      const y=value=>bottom-Math.max(0,Math.min(1,value))*height;
      const drawSeries=(field,color,dash)=>{
        const seriesPoints=usable.map((group,index)=>finite(group[field])?{x:x(index),y:y(group[field]),value:group[field],scenario:group.scenario,level:group.levelDisplay}:null).filter(Boolean);
        if(seriesPoints.length>1)svg.appendChild(el("polyline",{points:seriesPoints.map(point=>`${point.x},${point.y}`).join(" "),fill:"none",stroke:color,"stroke-width":3,"stroke-linejoin":"round","stroke-linecap":"round","stroke-dasharray":dash||""}));
        seriesPoints.forEach(point=>{const circle=el("circle",{cx:point.x,cy:point.y,r:4.5,fill:color,stroke:"#fff","stroke-width":2});const title=el("title");title.textContent=`${point.level}: ${percent(point.value)}`;circle.appendChild(title);svg.appendChild(circle);});
      };
      drawSeries(horizonField,"#11875d",""); drawSeries(dueField,"#246bfe","6 4");
      const labels=usable.length<=6?usable.map((_,index)=>index):[0,Math.floor((usable.length-1)/2),usable.length-1];
      labels.filter((value,index,array)=>array.indexOf(value)===index).forEach(index=>{const full=usable[index].levelDisplay||usable[index].scenario;const label=full.length>25?full.slice(0,22)+"…":full;addText(svg,x(index),274,label,{"text-anchor":"middle","font-size":"10"});});
    }

    function drawScatter(svg,groups){
      clearSvg(svg); const usable=groups.filter(group=>group.baselineFlowExercised!==false&&finite(group.supplierDue)&&finite(group.productDue));
      if(!usable.length){emptySvg(svg,"Le nuage nécessite les deux indicateurs servis à date");return;}
      const left=58,right=592,top=28,bottom=360,width=right-left,height=bottom-top;
      [0,.25,.5,.75,1].forEach(value=>{const x=left+value*width,y=bottom-value*height;svg.appendChild(el("line",{x1:x,y1:top,x2:x,y2:bottom,stroke:"#e1e8f0"}));svg.appendChild(el("line",{x1:left,y1:y,x2:right,y2:y,stroke:"#e1e8f0"}));addText(svg,x,bottom+22,`${Math.round(value*100)}%`,{"text-anchor":"middle"});addText(svg,left-8,y+4,`${Math.round(value*100)}%`,{"text-anchor":"end"});});
      usable.forEach((group,index)=>{const x=left+Math.max(0,Math.min(1,group.supplierDue))*width,y=bottom-Math.max(0,Math.min(1,group.productDue))*height;const color=["#246bfe","#11875d","#b86b00","#8b5cf6","#d92d20"][index%5];const circle=el("circle",{cx:x,cy:y,r:7,fill:color,"fill-opacity":.82,stroke:"#fff","stroke-width":2});const title=el("title");title.textContent=`${group.levelDisplay} — fournisseur à date ${percent(group.supplierDue)}, client à date ${percent(group.productDue)}`;circle.appendChild(title);svg.appendChild(circle);});
      addText(svg,(left+right)/2,410,"Disponible fournisseur à date — proxy",{"text-anchor":"middle","font-size":"12"});
      const label=addText(svg,16,(top+bottom)/2,"Volume client servi à date — proxy",{"text-anchor":"middle","font-size":"12"});label.setAttribute("transform",`rotate(-90 16 ${(top+bottom)/2})`);
    }

    const severityValue=(value,fallback=-1)=>finite(value)?value:fallback;
    function severityCompare(a,b){
      const fields=[
        item=>severityValue(item.dueLoss),
        item=>Math.max(0,severityValue(item.incrementalBacklog,0)),
        item=>severityValue(item.worst28Loss)
      ];
      for(const field of fields){const difference=field(b)-field(a);if(Math.abs(difference)>1e-12)return difference;}
      return levelOrder(b)-levelOrder(a)||a.scenario.localeCompare(b.scenario,"fr");
    }

    function backlogStatusText(group){
      const hasBacklog=finite(group.backlogDays)&&group.backlogDays>1e-9;
      if(!hasBacklog&&finite(group.backlogEndQty)&&group.backlogEndQty<=1e-9)return "Aucun retard client";
      const parts=[];
      if(finite(group.firstBacklogDay))parts.push(`Premier retard : J${number(group.firstBacklogDay)}`);
      else if(hasBacklog)parts.push("Premier retard : non daté dans ce résumé");
      if(finite(group.backlogDays))parts.push(`${number(group.backlogDays)} jours touchés${Number.isFinite(horizonDays)?` sur ${horizonDays}`:""}`);
      if(finite(group.backlogEndQty))parts.push(`Retard restant ${Number.isFinite(horizonDays)?`à J${horizonDays-1}`:"en fin de simulation"} : ${number(group.backlogEndQty)} unité${Math.abs(group.backlogEndQty)>1?"s":""}`);
      return parts.length?parts.join(" · "):"Chronologie non disponible";
    }

    function interpretation(group){
      if(group.baselineFlowExercised===false)return `Chaîne non exercée dans la référence : aucun appel et aucun envoi fournisseur pendant J45–J224. Ces valeurs ne permettent pas de conclure sur sa sensibilité.`;
      const parts=[];
      if(finite(group.dueLoss)&&group.dueLoss>0)parts.push(`${(group.dueLoss*100).toFixed(1).replace(".",",")} points de volume servi à date perdus face à la référence`);
      if(finite(group.incrementalBacklog)&&group.incrementalBacklog>0)parts.push(`${number(group.incrementalBacklog)} unités·jours de retard cumulé supplémentaire`);
      if(finite(group.worst28))parts.push(`creux de 28 jours à ${percent(group.worst28)}`);
      if(finite(group.backlogDays)||finite(group.backlogEndQty))parts.push(backlogStatusText(group).toLowerCase());
      if(group.note)parts.push(`hypothèse : ${group.note}`);
      if(!parts.length)parts.push("vérifier le mécanisme et les contraintes physiques avant de conclure");
      return parts.join(" ; ") + ".";
    }

    function renderInfluence(groups){
      const list=document.getElementById("mechanism-ranking"),method=document.getElementById("influence-method");list.textContent="";
      const eligible=groups.filter(group=>group.baselineFlowExercised!==false);
      const excludedCount=groups.length-eligible.length;
      const confirmed=eligible.filter(group=>group.phase==="confirmation_metrics");
      const source=confirmed.length?confirmed:eligible;
      const buckets=new Map();
      source.forEach(group=>{const key=pairKey(group);if(!buckets.has(key))buckets.set(key,[]);buckets.get(key).push(group);});
      const ranking=[...buckets.values()].map(items=>{
        const worst=items.filter(item=>!item.isBaseline&&finite(item.productDue)).slice().sort(severityCompare)[0];
        return worst?{...worst,items}:null;
      }).filter(Boolean).sort(severityCompare);
      method.textContent=(confirmed.length?"Classement des impacts maximaux confirmés, comparés à la référence appariée : d’abord la perte de volume servi à date, puis le retard cumulé supplémentaire et le creux de 28 jours.":"Aucune confirmation dans ce filtre : classement provisoire du premier balayage, à confirmer avant décision.")+(excludedCount?` ${excludedCount} configuration${excludedCount>1?"s":""} sans flux de référence ${excludedCount>1?"sont exclues":"est exclue"} du classement.`:"");
      if(!ranking.length){const item=document.createElement("li");item.textContent="Aucune configuration exploitable n’est disponible.";list.appendChild(item);return;}
      const maximum=Math.max(...ranking.map(item=>severityValue(item.dueLoss,0)),.000001);
      ranking.slice(0,8).forEach(item=>{const row=document.createElement("li"),label=document.createElement("span"),bar=document.createElement("span"),fill=document.createElement("i"),value=document.createElement("span");label.textContent=`${item.mechanism} — ${item.chain}`;label.title=`Retard supplémentaire ${number(item.incrementalBacklog)} unités·jours ; pire fenêtre 28 j ${percent(item.worst28)} ; ${backlogStatusText(item)}`;bar.className="influence-bar";fill.style.width=`${Math.max(3,severityValue(item.dueLoss,0)/maximum*100)}%`;bar.appendChild(fill);value.className="influence-value";value.textContent=`perte ${(severityValue(item.dueLoss,0)*100).toFixed(1).replace(".",",")} pt`;value.title="Premier critère du tri : perte moyenne de volume servi à date face à la référence appariée";row.append(label,bar,value);list.appendChild(row);});
    }

    function appendDistribution(cell,group){
      const details=document.createElement("details"),summary=document.createElement("summary"),values=document.createElement("div");
      details.className="run-distribution";values.className="run-values";
      const count=Math.round(group.runCount||group.runValues.length);
      if(count>1)summary.textContent=`${count} simulations · ${percent(group.dueMin)} à ${percent(group.dueMax)}`;
      else summary.textContent=`1 calcul exploratoire · ${percent(group.productDue)} — à confirmer`;
      if(group.runValues.length>1)values.textContent=group.runValues.map(run=>`${percent(run.value)} (tirage ${run.repetition})`).join(" · ");
      else values.textContent="Les valeurs individuelles ne sont pas disponibles dans cette ligne compacte.";
      details.append(summary,values);cell.appendChild(details);
    }

    function renderTable(groups){
      const body=document.getElementById("fragility-body");body.textContent="";
      const sorted=groups.slice().sort(severityCompare);
      if(!sorted.length){const row=document.createElement("tr"),cell=document.createElement("td");cell.colSpan=13;cell.textContent="Aucune configuration ne correspond aux filtres.";row.appendChild(cell);body.appendChild(row);return;}
      sorted.forEach(group=>{
        const row=document.createElement("tr");
        if(group.baselineFlowExercised===false)row.className="not-exercised";
        const evidence=group.baselineFlowExercised===false?"Chaîne non exercée · non interprétable":(group.phase==="confirmation_metrics"?`Confirmation · ${Math.round(group.runCount)} simulations`:(group.phase==="screening_metrics"?"Premier balayage · à confirmer":phaseNames[group.phase]||group.phase));
        const worst28=finite(group.worst28)?`${percent(group.worst28)}${finite(group.worst28Loss)?` (perte ${(group.worst28Loss*100).toFixed(1).replace(".",",")} pt)`:""}`:"—";
        const values=[group.levelDisplay,group.chain,group.mechanism,evidence,percent(group.supplierDue),percent(group.productDue),null,finite(group.dueDelta)?points(group.dueDelta):(finite(group.dueLoss)?points(-group.dueLoss):"—"),number(group.incrementalBacklog),worst28,backlogStatusText(group),percent(group.productHorizon),interpretation(group)];
        values.forEach((value,index)=>{const cell=document.createElement("td");if(index===6)appendDistribution(cell,group);else cell.textContent=value;if([4,5,7,8,9,10,11].includes(index))cell.className="metric";if(index===3)cell.className="phase";row.appendChild(cell);});body.appendChild(row);
      });
    }

    function renderReading(groups){
      const target=document.getElementById("flow-reading");
      if(!groups.length){target.textContent="Lecture : aucune configuration ne correspond aux filtres.";return;}
      const eligible=groups.filter(group=>group.baselineFlowExercised!==false);
      const withBoth=eligible.filter(group=>finite(group.productHorizon)&&finite(group.productDue));
      const gaps=withBoth.map(group=>group.productHorizon-group.productDue);
      const gap=mean(gaps);
      const worst=eligible.filter(group=>finite(group.productDue)).sort((a,b)=>a.productDue-b.productDue)[0];
      let text=`Lecture : ${groups.length} configuration${groups.length>1?"s":""} retenue${groups.length>1?"s":""}. `;
      if(!eligible.length){target.textContent=text+"La chaîne sélectionnée n’est pas exercée dans la référence pendant J45–J224 ; aucun classement de sensibilité n’est calculé.";return;}
      if(new Set(groups.map(pairKey)).size>1)text+="Affinez les filtres pour obtenir une courbe ordonnée : aucun trait ne relie des chaînes ou mécanismes différents. ";
      if(worst)text+=`La part client servie à la date attendue la plus faible est ${percent(worst.productDue)} pour « ${worst.levelDisplay} ». `;
      if(finite(gap))text+=`L’écart moyen entre le service sur l’horizon et le servi à date est de ${(gap*100).toFixed(1).replace(".",",")} points. `;
      text+="Cet écart montre ce qui est finalement rattrapé ; il ne mesure pas un OTIF fournisseur observé.";
      target.textContent=text;
    }

    function renderAll(){const groups=groupRows(filteredRecords());const unexercised=[...new Set(groups.filter(group=>group.baselineFlowExercised===false).map(group=>group.chain))];const warning=document.getElementById("unexercised-chain-warning");warning.hidden=!unexercised.length;warning.textContent=unexercised.length?`Chaîne non exercée dans la référence : ${unexercised.join(" ; ")}. Aucun appel ni envoi fournisseur n’a lieu pendant J45–J224 ; ses stress tests restent visibles comme limite de données, mais sont exclus des courbes et du classement.`:"";const supplierKinds=[...new Set(groups.filter(group=>group.baselineFlowExercised!==false).flatMap(group=>group.supplierMetricKinds))];document.getElementById("supplier-horizon-legend").textContent=supplierKinds.length===1?supplierKinds[0]:"Indicateur fournisseur simulé ou proxy";drawLineChart(document.getElementById("supplier-service-chart"),groups,"supplierHorizon","supplierDue");drawLineChart(document.getElementById("product-service-chart"),groups,"productHorizon","productDue");drawScatter(document.getElementById("fragility-scatter"),groups);renderInfluence(groups);renderTable(groups);renderReading(groups);}

    document.querySelectorAll("[data-view-target]").forEach(button=>button.addEventListener("click",()=>{document.querySelectorAll("[data-view-target]").forEach(node=>node.classList.toggle("active",node===button));document.querySelectorAll(".view").forEach(view=>view.classList.toggle("active",view.id===button.dataset.viewTarget));window.scrollTo({top:0,behavior:"smooth"});}));
    document.querySelectorAll(".action-status").forEach(select=>select.addEventListener("change",()=>{select.closest(".action").dataset.state=select.value;}));
    populateFilter("chain-filter","chain","Toutes les chaînes");populateFilter("mechanism-filter","mechanism","Tous les mécanismes");renderAll();
  })();
  </script>
</body>
</html>
'''


def render_supplier_service_landscape_dashboard(payload: Mapping[str, object]) -> str:
    """Render the autonomous dashboard from an already loaded payload."""
    return HTML_TEMPLATE.replace("__PAYLOAD_JSON__", _json_for_script(payload))


def build_supplier_service_landscape_dashboard(
    campaign_dir: str | Path,
    output_html: str | Path,
    *,
    allow_incomplete_campaign: bool = False,
) -> dict[str, object]:
    """Build one new standalone HTML without mutating or overwriting inputs."""
    campaign = Path(campaign_dir).resolve()
    output = Path(output_html).resolve()
    if output.exists():
        raise FileExistsError(f"Output HTML already exists: {output}")
    if campaign == output.parent or campaign in output.parents:
        raise ValueError("Output HTML must be outside the campaign directory")

    payload = load_supplier_service_campaign(campaign)
    validate_supplier_service_campaign_for_dashboard(
        payload,
        allow_incomplete_campaign=allow_incomplete_campaign,
    )
    document = render_supplier_service_landscape_dashboard(payload)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x", encoding="utf-8", newline="") as handle:
        handle.write(document)
    tables = payload["tables"]
    assert isinstance(tables, Mapping)
    return {
        "schema_version": SCHEMA_VERSION,
        "campaign_dir": str(campaign),
        "output_html": str(output),
        "output_bytes": output.stat().st_size,
        "view_count": 3,
        "row_counts": {
            name: len(table.get("rows", [])) if isinstance(table, Mapping) else 0
            for name, table in tables.items()
        },
    }


def parse_args(argv: Iterable[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--campaign-dir", type=Path, required=True)
    parser.add_argument("--output-html", type=Path, required=True)
    parser.add_argument(
        "--allow-incomplete-campaign",
        action="store_true",
        help="Development-only override for fixtures or an explicitly partial campaign.",
    )
    return parser.parse_args(list(argv) if argv is not None else None)


def main(argv: Iterable[str] | None = None) -> None:
    args = parse_args(argv)
    result = build_supplier_service_landscape_dashboard(
        args.campaign_dir,
        args.output_html,
        allow_incomplete_campaign=args.allow_incomplete_campaign,
    )
    print(f"[OK] Tableau de bord autonome : {result['output_html']}")
    print(f"[OK] Vues : {result['view_count']}")
    print(f"[OK] Taille : {result['output_bytes']} octets")


if __name__ == "__main__":
    main()
