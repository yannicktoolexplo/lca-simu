#!/usr/bin/env python3
"""Build the lightweight, standalone, three-view French V7 client delivery."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import statistics
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from etudecas.prototypes.scan_2027_risk_control import (
    supplier_fresh_development_holdout_protocol_v7 as protocol_v7,
)
from etudecas.prototypes.scan_2027_risk_control import (
    finalize_supplier_operating_point_full_campaign_v7 as finalizer_v7,
)
from etudecas.prototypes.scan_2027_risk_control import (
    supplier_operating_point_full_campaign_v7_dashboard as dashboard_v7,
)
from etudecas.prototypes.scan_2027_risk_control import (
    supplier_physical_cascade_qualification_v5 as physical_v5,
)
from etudecas.prototypes.scan_2027_risk_control import (
    supplier_priority_action_replay_v4 as actions_v4,
)
from etudecas.prototypes.scan_2027_risk_control import (
    supplier_priority_lot_replay_v4 as lots_v4,
)
from etudecas.prototypes.scan_2027_risk_control import (
    supplier_v6_full_incident_lot_registry as registry_v6,
)
from etudecas.prototypes.scan_2027_risk_control import (
    supplier_v7_campaign_trace_package as traces_v7,
)
from etudecas.prototypes.scan_2027_risk_control import (
    supplier_v7_stage2_common as common,
)
from etudecas.prototypes.scan_2027_risk_control import (
    supplier_v7_stage2_curves as curves_v7,
)


SCHEMA_VERSION = "etudecas.supplier_v7_stage2_delivery.v1"
MANIFEST_SCHEMA_VERSION = f"{SCHEMA_VERSION}.manifest.v1"
FOCUS_LANE_ID = "sdc_vd0914360c_338929_m_1810"
FOCUS_IDENTITY = {
    "supplier_id": "SDC-VD0914360C",
    "item_id": "338929",
    "dst_node_id": "M-1810",
    "target_product_id": "268091",
}
STATE_ORDER = ("op_100", "op_93", "op_80")
MECHANISM_ORDER = ("transport_delay", "planned_delivery_shortfall")
PRODUCTS = ("global", "268091", "268967")
NOMINAL_METRIC_LABELS = {
    ("service", "service_a_l_heure"): "Service à l'heure",
    ("service", "retard_client"): "Retard client agrégé",
    ("production", "production_liberee"): "Production libérée",
    ("production", "encours"): "Encours de production",
    ("stock_entrant", "stock_entrant"): "Stock de l'article entrant",
}


class Stage2DeliveryError(common.Stage2Error):
    """A source or client-facing claim does not satisfy the V7 contract."""


def _truthy(value: Any, *, label: str) -> bool:
    if isinstance(value, bool):
        return value
    text = str(value or "").strip().casefold()
    if text in {"true", "1", "yes", "oui"}:
        return True
    if text in {"false", "0", "no", "non"}:
        return False
    raise Stage2DeliveryError(f"Booléen invalide : {label}")


def _number(value: Any, *, label: str, optional: bool = False) -> float | None:
    text = "" if value is None else str(value).strip()
    if optional and (not text or text.casefold() in {"nan", "none", "null"}):
        return None
    return common.finite_number(value, label=label)


def _integer(value: Any, *, label: str) -> int:
    number = _number(value, label=label)
    assert number is not None
    result = int(number)
    if float(result) != number:
        raise Stage2DeliveryError(f"Entier attendu : {label}")
    return result


def _require_columns(
    rows: Sequence[Mapping[str, Any]], required: set[str], *, label: str
) -> None:
    if not rows or not required.issubset(rows[0]):
        missing = sorted(required - set(rows[0] if rows else ()))
        raise Stage2DeliveryError(
            f"Colonnes absentes dans {label}: {', '.join(missing)}"
        )


def _bound_results_csv(paths: common.Stage2Paths, name: str) -> list[dict[str, str]]:
    validation = common.read_json(paths.results_dir / "campaign_validation.json")
    declaration = (validation.get("outputs") or {}).get(name)
    source = paths.results_dir / name
    if (
        not isinstance(declaration, Mapping)
        or not source.is_file()
        or common.sha256_file(source) != str(declaration.get("sha256") or "")
    ):
        raise Stage2DeliveryError(f"Table de campagne non liée ou modifiée : {name}")
    return common._read_csv(source)  # noqa: SLF001


def _validation_states(result: Mapping[str, Any]) -> list[dict[str, Any]]:
    descriptive = result.get("descriptive_diagnostics") or {}
    state_values = descriptive.get("states") or {}
    bootstrap = result.get("bootstrap") or {}
    global_intervals = bootstrap.get("global_service_ci90_pct") or {}
    lower95 = bootstrap.get("op100_one_sided_lower95_pct") or {}
    fixed = {
        str(row.get("target_group") or ""): row
        for row in result.get("fixed_triplet") or []
    }
    output = []
    for state in STATE_ORDER:
        measures = []
        for measure in PRODUCTS:
            value = _number(
                (state_values.get(state) or {})
                .get(measure, {})
                .get("pooled_service_pct"),
                label=f"service V7 {state}/{measure}",
            )
            interval: dict[str, Any]
            if state == "op_100":
                interval = {
                    "kind": "borne_basse_unilaterale_95",
                    "low": _number(
                        lower95.get(measure), label=f"borne V7 {state}/{measure}"
                    ),
                    "high": None,
                    "label": "borne basse unilatérale 95 %",
                }
            elif measure == "global":
                bounds = global_intervals.get(state) or {}
                interval = {
                    "kind": "intervalle_bilateral_90",
                    "low": _number(bounds.get("lower_pct"), label=f"IC90 bas {state}"),
                    "high": _number(
                        bounds.get("upper_pct"), label=f"IC90 haut {state}"
                    ),
                    "label": "intervalle bilatéral 90 %",
                }
            else:
                interval = {
                    "kind": "non_calcule_pour_ce_produit",
                    "low": None,
                    "high": None,
                    "label": "intervalle non calculé pour ce produit",
                }
            measures.append({"id": measure, "service_pct": value, "interval": interval})
        candidate = fixed.get(state)
        if not isinstance(candidate, Mapping):
            raise Stage2DeliveryError(f"Configuration V7 absente : {state}")
        output.append(
            {
                "id": state,
                "label": {
                    "op_100": "Référence",
                    "op_93": "Niveau proche de 93 %",
                    "op_80": "Niveau proche de 80 %",
                }[state],
                "measures": measures,
                "planned_lead_offset_days": {
                    "268091": _number(
                        candidate.get("offset_days_268091"),
                        label=f"offset 268091 {state}",
                    ),
                    "268967": _number(
                        candidate.get("offset_days_268967"),
                        label=f"offset 268967 {state}",
                    ),
                },
            }
        )
    if (
        int(descriptive.get("seed_block_count") or -1)
        != common.EXPECTED_VALIDATION_SEEDS
    ):
        raise Stage2DeliveryError(
            "Les états affichés ne proviennent pas des 150 graines V7"
        )
    return output


def _lane_sensitivity(paths: common.Stage2Paths) -> list[dict[str, Any]]:
    rows = _bound_results_csv(paths, "lane_state_sensitivity_by_cause.csv")
    required = {
        "analysis_level",
        "mechanism",
        "target_product_id",
        "supplier_id",
        "lane_id",
        "comparison_lane_id",
        "state_comparison_valid",
        "comparable_seed_count",
        "required_comparable_seed_count",
        "priority_status",
        "priority_status_op_100",
        "priority_status_op_93",
        "priority_status_op_80",
        "rank_min_op_100",
        "rank_max_op_100",
        "rank_min_op_93",
        "rank_max_op_93",
        "rank_min_op_80",
        "rank_max_op_80",
        "fixed360_effect_mean_pp_op_100",
        "fixed360_effect_mean_pp_op_93",
        "fixed360_effect_mean_pp_op_80",
        "fixed360_op_93_minus_op_100_pp_mean",
        "fixed360_op_93_minus_op_100_pp_ci95_low",
        "fixed360_op_93_minus_op_100_pp_ci95_high",
        "fixed360_op_80_minus_op_100_pp_mean",
        "fixed360_op_80_minus_op_100_pp_ci95_low",
        "fixed360_op_80_minus_op_100_pp_ci95_high",
        "state_sensitivity_interpretation_fr",
    }
    _require_columns(rows, required, label="sensibilité des voies")
    output = []
    for row in rows:
        if (
            row["analysis_level"] != "lane"
            or row["lane_id"] != row["comparison_lane_id"]
        ):
            raise Stage2DeliveryError(
                "La sensibilité inter-états ne porte pas une voie fixe"
            )
        comparison_valid = _truthy(
            row["state_comparison_valid"], label="comparaison voie"
        )
        states = {}
        for state in STATE_ORDER:
            states[state] = {
                "effect_mean_pp": _number(
                    row[f"fixed360_effect_mean_pp_{state}"],
                    label=f"effet voie {row['lane_id']}/{state}",
                ),
                "priority_status": str(row[f"priority_status_{state}"]),
                "rank_min": _integer(row[f"rank_min_{state}"], label="rang min voie"),
                "rank_max": _integer(row[f"rank_max_{state}"], label="rang max voie"),
            }
        paired_changes = {"op_100": {"mean": 0.0, "ci95_low": 0.0, "ci95_high": 0.0}}
        for state in ("op_93", "op_80"):
            prefix = f"fixed360_{state}_minus_op_100_pp"
            paired_changes[state] = {
                field: _number(
                    row[f"{prefix}_{field}"],
                    label=f"variation appariée {row['lane_id']}/{state}/{field}",
                    optional=True,
                )
                for field in ("mean", "ci95_low", "ci95_high")
            }
        paired_values = [
            value
            for state in ("op_93", "op_80")
            for value in paired_changes[state].values()
        ]
        if comparison_valid != all(value is not None for value in paired_values):
            raise Stage2DeliveryError(
                "Les différences appariées ne correspondent pas au statut inter-états"
            )
        output.append(
            {
                "mechanism": str(row["mechanism"]),
                "lane_id": str(row["lane_id"]),
                "supplier_id": str(row["supplier_id"]),
                "target_product_id": str(row["target_product_id"]),
                "state_comparison_valid": comparison_valid,
                "comparable_seed_count": _integer(
                    row["comparable_seed_count"], label="graines comparables"
                ),
                "required_comparable_seed_count": _integer(
                    row["required_comparable_seed_count"], label="seuil comparable"
                ),
                "stability_status": str(row["priority_status"]),
                "interpretation_fr": str(row["state_sensitivity_interpretation_fr"]),
                "states": states,
                "paired_changes_vs_reference_pp": paired_changes,
            }
        )
    if {row["mechanism"] for row in output} != set(MECHANISM_ORDER):
        raise Stage2DeliveryError(
            "Les deux mécanismes ne sont pas séparés dans la sensibilité"
        )
    return sorted(output, key=lambda row: (row["lane_id"], row["mechanism"]))


def _supplier_stability(paths: common.Stage2Paths) -> list[dict[str, Any]]:
    rows = _bound_results_csv(paths, "supplier_priority_stability_by_cause.csv")
    required = {
        "mechanism",
        "supplier_id",
        "comparison_lane_id",
        "target_product_id_for_comparison_lane",
        "state_comparison_valid",
        "same_exposed_lane_across_states",
        "priority_in_all_three_states",
        "robust_priority_in_all_three_states",
        "priority_status",
        "priority_status_op_100",
        "priority_status_op_93",
        "priority_status_op_80",
        "rank_min_op_100",
        "rank_max_op_100",
        "rank_min_op_93",
        "rank_max_op_93",
        "rank_min_op_80",
        "rank_max_op_80",
        "state_sensitivity_interpretation_fr",
    }
    _require_columns(rows, required, label="stabilité fournisseur")
    output = []
    for row in rows:
        output.append(
            {
                "mechanism": str(row["mechanism"]),
                "supplier_id": str(row["supplier_id"]),
                "comparison_lane_id": str(row["comparison_lane_id"]),
                "target_product_id": str(row["target_product_id_for_comparison_lane"]),
                "state_comparison_valid": _truthy(
                    row["state_comparison_valid"], label="comparaison fournisseur"
                ),
                "same_dominant_lane": _truthy(
                    row["same_exposed_lane_across_states"], label="voie dominante"
                ),
                "priority_in_all_three_states": _truthy(
                    row["priority_in_all_three_states"],
                    label="priorité dans les trois états",
                ),
                "robust_priority_in_all_three_states": _truthy(
                    row["robust_priority_in_all_three_states"],
                    label="priorité robuste dans les trois états",
                ),
                "stability_status": str(row["priority_status"]),
                "interpretation_fr": str(row["state_sensitivity_interpretation_fr"]),
                "states": {
                    state: {
                        "priority_status": str(row[f"priority_status_{state}"]),
                        "rank_min": _integer(
                            row[f"rank_min_{state}"], label="rang min fournisseur"
                        ),
                        "rank_max": _integer(
                            row[f"rank_max_{state}"], label="rang max fournisseur"
                        ),
                    }
                    for state in STATE_ORDER
                },
            }
        )
    return sorted(output, key=lambda row: (row["supplier_id"], row["mechanism"]))


def _portfolio_summary(
    supplier_rows: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    mechanisms = []
    for mechanism in MECHANISM_ORDER:
        rows = [dict(row) for row in supplier_rows if row["mechanism"] == mechanism]
        recurring = [row for row in rows if row["priority_in_all_three_states"]]
        robust = [row for row in rows if row["robust_priority_in_all_three_states"]]
        mechanisms.append(
            {
                "mechanism": mechanism,
                "supplier_count": len(rows),
                "recurring_signal_count": len(recurring),
                "robust_recurring_signal_count": len(robust),
                "rows": sorted(
                    rows,
                    key=lambda row: (
                        not row["robust_priority_in_all_three_states"],
                        not row["priority_in_all_three_states"],
                        row["supplier_id"],
                    ),
                ),
            }
        )
    return {
        "mechanisms": mechanisms,
        "selection_rule": (
            "Tous les statuts fournisseurs signés sont conservés; aucun top 3 "
            "n'est imposé et les trois dossiers lots restent une sélection distincte."
        ),
    }


def _incident_lane_rows(paths: common.Stage2Paths) -> list[dict[str, Any]]:
    rows = _bound_results_csv(paths, "priority_lanes_by_cause_state.csv")
    metric = "impact_service_loss_fed_product_pp"
    required = {
        "operating_point_id",
        "mechanism",
        "lane_id",
        "supplier_id",
        "item_id",
        "dst_node_id",
        "target_product_id",
        "priority_status",
        "rank_min",
        "rank_max",
        "physical_exercise_count",
        f"{metric}_mean",
        f"{metric}_p10",
        f"{metric}_p90",
        f"{metric}_ci95_low",
        f"{metric}_ci95_high",
    }
    _require_columns(rows, required, label="résultats par voie")
    output = []
    for row in rows:
        output.append(
            {
                "state": str(row["operating_point_id"]),
                "mechanism": str(row["mechanism"]),
                "lane_id": str(row["lane_id"]),
                "supplier_id": str(row["supplier_id"]),
                "item_id": str(row["item_id"]).removeprefix("item:"),
                "dst_node_id": str(row["dst_node_id"]),
                "target_product_id": str(row["target_product_id"]).removeprefix(
                    "item:"
                ),
                "priority_status": str(row["priority_status"]),
                "rank_min": _integer(row["rank_min"], label="rang min incident"),
                "rank_max": _integer(row["rank_max"], label="rang max incident"),
                "physically_exercised_seed_count": _integer(
                    row["physical_exercise_count"], label="incidents exercés"
                ),
                "paired_seed_count": common.EXPECTED_CAMPAIGN_SEEDS,
                "signed_baseline_minus_incident_service_pp": {
                    "mean": _number(row[f"{metric}_mean"], label="effet moyen"),
                    "p10": _number(row[f"{metric}_p10"], label="effet p10"),
                    "p90": _number(row[f"{metric}_p90"], label="effet p90"),
                    "ci95_low": _number(
                        row[f"{metric}_ci95_low"], label="effet IC bas"
                    ),
                    "ci95_high": _number(
                        row[f"{metric}_ci95_high"], label="effet IC haut"
                    ),
                },
            }
        )
    expected = (
        len(common.EXPECTED_STATES)
        * len(common.EXPECTED_MECHANISMS)
        * common.EXPECTED_LANES
    )
    if len(output) != expected:
        raise Stage2DeliveryError(
            "La table par voie ne contient pas les 108 situations"
        )
    return output


def _selection(paths: common.Stage2Paths) -> list[dict[str, Any]]:
    from etudecas.prototypes.scan_2027_risk_control import (
        supplier_v7_stage2_pipeline as pipeline,
    )

    return pipeline._selection(paths.results_dir)  # noqa: SLF001


def _focus(
    paths: common.Stage2Paths,
    lane_rows: Sequence[Mapping[str, Any]],
    selection: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    all_lane_ids = {str(row["lane_id"]) for row in lane_rows}
    if FOCUS_LANE_ID in all_lane_ids:
        lane_id = FOCUS_LANE_ID
        requested_present = True
    elif selection:
        lane_id = str(selection[0]["lane_id"])
        requested_present = False
    else:
        lane_id = min(all_lane_ids)
        requested_present = False
    matching = [dict(row) for row in lane_rows if row["lane_id"] == lane_id]
    if len(matching) != len(STATE_ORDER) * len(MECHANISM_ORDER):
        raise Stage2DeliveryError("Le dossier d'affichage n'a pas ses six résultats")
    identity = {
        key: str(matching[0][key])
        for key in ("supplier_id", "item_id", "dst_node_id", "target_product_id")
    }
    if any(
        str(row[key]) != value for row in matching for key, value in identity.items()
    ):
        raise Stage2DeliveryError(
            "L'identité physique du dossier varie entre situations"
        )
    if requested_present and identity != FOCUS_IDENTITY:
        raise Stage2DeliveryError("L'identité signée de 338929 ne correspond plus")
    plan = protocol_v7.validate_plan(paths.v7_plan_dir, verify_runtime=True)
    base_lanes = traces_v7._campaign_lanes(plan)  # noqa: SLF001
    lane = next((row for row in base_lanes if row["lane_id"] == lane_id), None)
    if lane is None:
        raise Stage2DeliveryError(
            "Le dossier d'affichage n'appartient pas aux 18 voies"
        )
    base_lead = _number(lane["planned_lead_days"], label="délai planifié de référence")
    assert base_lead is not None
    fixed_by_state = {row.target_group: row for row in protocol_v7.FIXED_TRIPLET}
    target = identity["target_product_id"]
    planned_leads = {}
    for state in STATE_ORDER:
        spec = fixed_by_state[state]
        offset = (
            spec.offset_days_268091 if target == "268091" else spec.offset_days_268967
        )
        planned_leads[state] = base_lead + offset
    selected_dossier = next(
        (str(row["dossier_id"]) for row in selection if row["lane_id"] == lane_id), None
    )
    return {
        "lane_id": lane_id,
        **identity,
        "requested_338929_present": requested_present,
        "display_rule": (
            "338929 affiché par défaut car présent dans les résultats signés"
            if requested_present
            else (
                "338929 absent; premier dossier sélectionné par le protocole affiché "
                "sans reclassement"
                if selection
                else (
                    "338929 absent et aucune sélection détaillée; première voie "
                    "agrégée affichée sans reclassement"
                )
            )
        ),
        "selected_for_detailed_replay": selected_dossier is not None,
        "selected_dossier_id": selected_dossier,
        "planned_lead_days": planned_leads,
        "aggregate_incident_results": matching,
    }


def _weekly_nominal(
    payload: Mapping[str, Any], focus: Mapping[str, Any]
) -> list[dict[str, Any]]:
    target = str(focus["target_product_id"])
    stock_entity = f"{focus['dst_node_id']}|{focus['item_id']}"
    wanted = {
        ("service", "global", "service_a_l_heure"),
        ("service", target, "service_a_l_heure"),
        ("service", target, "retard_client"),
        ("production", target, "production_liberee"),
        ("production", target, "encours"),
        ("stock_entrant", stock_entity, "stock_entrant"),
    }
    output = []
    for series in payload.get("series") or []:
        key = (series.get("domain"), series.get("entity"), series.get("metric"))
        if key not in wanted:
            continue
        label_key = (str(series["domain"]), str(series["metric"]))
        if label_key not in NOMINAL_METRIC_LABELS:
            raise Stage2DeliveryError("Libellé métier de courbe nominale absent")
        entity = str(series["entity"])
        if entity == "global":
            entity_label = "Réseau global"
        elif series["domain"] == "stock_entrant":
            node, item = entity.split("|", maxsplit=1)
            entity_label = f"{node} · article {item}"
        else:
            entity_label = f"Produit {entity}"
        points = series.get("points") or []
        reduced = [
            [row[0], row[1], row[2], row[4]]
            for index, row in enumerate(points)
            if index % 7 == 0 or index == len(points) - 1
        ]
        output.append(
            {
                "state": series["state"],
                "domain": series["domain"],
                "entity": series["entity"],
                "metric": series["metric"],
                "label_fr": NOMINAL_METRIC_LABELS[label_key],
                "entity_label_fr": entity_label,
                "unit": series["unit"],
                "rolling_window_days": series["rolling_window_days"],
                "sample_count": series["sample_count"],
                "columns": ["day", "mean", "p10", "p90"],
                "points": reduced,
            }
        )
    if len(output) != len(wanted) * len(STATE_ORDER):
        raise Stage2DeliveryError(
            "Les courbes nominales attendues ne sont pas complètes"
        )
    return sorted(output, key=lambda row: (row["metric"], row["entity"], row["state"]))


def _dense_paired_curves(path: Path) -> dict[str, Any]:
    rows = common._read_csv(path)  # noqa: SLF001
    _require_columns(
        rows,
        {"day", "metric", "baseline_value", "incident_value"},
        label="courbes du rejeu détaillé",
    )
    by_metric: dict[str, list[dict[str, str]]] = {}
    for row in rows:
        by_metric.setdefault(str(row["metric"]), []).append(row)
    required = {
        "component_stock",
        "production_released",
        "demand",
        "served_on_due",
        "backlog",
    }
    if not required.issubset(by_metric):
        raise Stage2DeliveryError("Courbes détaillées incomplètes")
    horizon = len(by_metric["demand"])
    dense: dict[str, tuple[list[float], list[float]]] = {}
    for metric in required:
        ordered = sorted(
            by_metric[metric], key=lambda row: _integer(row["day"], label="jour")
        )
        if [int(row["day"]) for row in ordered] != list(range(horizon)):
            raise Stage2DeliveryError(f"Horizon détaillé incomplet : {metric}")
        dense[metric] = (
            [
                float(_number(row["baseline_value"], label=f"{metric} baseline"))
                for row in ordered
            ],
            [
                float(_number(row["incident_value"], label=f"{metric} incident"))
                for row in ordered
            ],
        )
    definitions = (
        ("component_stock", "Stock article à l'usine", "UN", 7),
        ("production_released", "Production libérée", "UN/jour", 28),
        ("backlog", "Retard client agrégé", "UN", 7),
    )
    output = []
    for metric, label, unit, window in definitions:
        baseline, incident = dense[metric]
        smooth_baseline = curves_v7.curve_v4.rolling_mean(baseline, window)
        smooth_incident = curves_v7.curve_v4.rolling_mean(incident, window)
        output.append(
            {
                "metric": metric,
                "label": label,
                "unit": unit,
                "rolling_window_days": window,
                "raw": [[day, baseline[day], incident[day]] for day in range(horizon)],
                "smooth": [
                    [day, smooth_baseline[day], smooth_incident[day]]
                    for day in range(horizon)
                    if smooth_baseline[day] is not None
                    and smooth_incident[day] is not None
                ],
            }
        )
    baseline_due, incident_due = dense["served_on_due"]
    baseline_demand, incident_demand = dense["demand"]
    if any(
        not math.isclose(left, right, rel_tol=1e-12, abs_tol=1e-6)
        for left, right in zip(baseline_demand, incident_demand, strict=True)
    ):
        raise Stage2DeliveryError("La demande du rejeu détaillé n'est pas appariée")
    smooth_baseline = curves_v7.curve_v4.rolling_ratio(
        baseline_due, baseline_demand, 28
    )
    smooth_incident = curves_v7.curve_v4.rolling_ratio(
        incident_due, incident_demand, 28
    )
    output.append(
        {
            "metric": "service_on_due",
            "label": "Service à l'heure",
            "unit": "%",
            "rolling_window_days": 28,
            "raw": [
                [
                    day,
                    100.0 * baseline_due[day] / baseline_demand[day]
                    if baseline_demand[day] > 0
                    else None,
                    100.0 * incident_due[day] / incident_demand[day]
                    if incident_demand[day] > 0
                    else None,
                ]
                for day in range(horizon)
            ],
            "smooth": [
                [day, 100.0 * smooth_baseline[day], 100.0 * smooth_incident[day]]
                for day in range(horizon)
                if smooth_baseline[day] is not None and smooth_incident[day] is not None
            ],
        }
    )
    return {"horizon_days": horizon, "series": output}


def _canonical_identity_value(field: str, value: Any) -> str:
    text = str(value or "")
    return (
        text.removeprefix("item:")
        if field in {"item_id", "target_product_id"}
        else text
    )


GENEALOGY_QUANTITY_LABELS = (
    ("parent_qty", "quantité du lot source"),
    ("child_qty", "quantité du lot entrant"),
    ("consumed_qty", "quantité consommée"),
    ("released_qty_same_day", "quantité libérée le même jour"),
    ("released_qty", "quantité du lot fini libéré"),
    ("service_event_qty_on_contacted_lot", "quantité au contact client agrégé"),
)


J0_CLIENT_METRICS = {
    "component_stock": ("Stock de l'article entrant", "UN en fin de journée"),
    "production_released": ("Production libérée", "UN sur la journée"),
    "wip": ("Encours de production", "UN en fin de journée"),
    "demand": ("Demande client agrégée", "UN sur la journée"),
    "served_on_due": ("Unités servies à l'heure", "UN sur la journée"),
    "backlog": ("Retard client agrégé", "UN en fin de journée"),
}


def _genealogy_quantity_details(row: Mapping[str, Any]) -> list[dict[str, Any]]:
    output = []
    for field, label_fr in GENEALOGY_QUANTITY_LABELS:
        value = _number(row.get(field), label=field, optional=True)
        if value is not None:
            output.append(
                {
                    "source_field": field,
                    "label_fr": label_fr,
                    "value": value,
                    "uom": str(row.get("uom") or ""),
                }
            )
    return output


def _client_j0_rows(
    rows: Sequence[Mapping[str, Any]], dossier_id: str
) -> list[dict[str, Any]]:
    selected = [row for row in rows if str(row.get("dossier_id") or "") == dossier_id]
    if len(selected) != len(J0_CLIENT_METRICS) or {
        str(row.get("metric") or "") for row in selected
    } != set(J0_CLIENT_METRICS):
        raise Stage2DeliveryError("Les six lectures métier à J0 sont incomplètes")
    output = []
    for row in selected:
        metric_id = str(row["metric"])
        label_fr, unit_fr = J0_CLIENT_METRICS[metric_id]
        output.append(
            {
                "metric_id": metric_id,
                "label_fr": label_fr,
                "unit_fr": unit_fr,
                "measurement_kind_fr": str(row.get("measurement_kind") or ""),
                "observation_convention_fr": str(
                    row.get("observation_convention") or ""
                ),
                "baseline_value_at_incident_j0": _number(
                    row.get("baseline_value_at_incident_j0"),
                    label=f"J0 référence {metric_id}",
                ),
                "incident_value_at_incident_j0": _number(
                    row.get("incident_value_at_incident_j0"),
                    label=f"J0 incident {metric_id}",
                ),
            }
        )
    return sorted(
        output, key=lambda row: tuple(J0_CLIENT_METRICS).index(row["metric_id"])
    )


def _detailed_replays(
    paths: common.Stage2Paths,
    selection: Sequence[Mapping[str, Any]],
    registry_payload: Mapping[str, Any],
) -> list[dict[str, Any]]:
    if not selection:
        return []
    from etudecas.prototypes.scan_2027_risk_control import (
        supplier_v7_stage2_pipeline as pipeline,
    )

    plan = lots_v4.load_and_validate_plan(paths.lot_replay_root)
    validation = pipeline._validate_finalized_lots(  # noqa: SLF001
        paths.lot_replay_root, plan
    )
    validation_by_id = {
        str(row["dossier_id"]): row for row in validation.get("dossiers") or []
    }
    genealogy = (registry_payload.get("detailedReplays") or {}).get(
        "genealogyRows"
    ) or []
    registry_dossiers = {
        str(row.get("dossier_id") or ""): row
        for row in (registry_payload.get("detailedReplays") or {}).get("dossiers") or []
    }
    j0_rows = (registry_payload.get("detailedReplays") or {}).get("j0Rows") or []
    output = []
    for dossier in plan.get("dossiers") or []:
        dossier_id = str(dossier["dossier_id"])
        priority = dossier["priority"]
        kpi_path = (
            paths.lot_replay_root
            / "finalized"
            / "dossiers"
            / dossier_id
            / "dossier_kpis.json"
        )
        curve_path = (
            paths.lot_replay_root
            / "finalized"
            / "dossiers"
            / dossier_id
            / "paired_daily_curves.csv"
        )
        kpis = common.read_json(kpi_path)
        selected_genealogy = []
        for row in genealogy:
            if str(row.get("dossier_id") or "") != dossier_id:
                continue
            selected_row = {
                key: row.get(key)
                for key in (
                    "genealogy_stage",
                    "incident_j0_day",
                    "event_day",
                    "event_day_kind",
                    "days_from_incident_j0",
                    "shipment_id",
                    "shipment_ids",
                    "risk_decision_day",
                    "source_lot_id",
                    "receipt_lot_id",
                    "material_lot_id",
                    "parent_qty",
                    "child_qty",
                    "campaign_id",
                    "batch_id",
                    "wip_start_qty",
                    "wip_end_qty",
                    "finished_lot_id",
                    "released_lot_id_same_day",
                    "released_qty_same_day",
                    "release_day",
                    "client_lot_id",
                    "client_node_id",
                    "consumed_qty",
                    "released_qty",
                    "service_event_qty_on_contacted_lot",
                    "uom",
                    "claim",
                )
            }
            selected_row["quantity_details"] = _genealogy_quantity_details(row)
            selected_genealogy.append(selected_row)
        proof = validation_by_id.get(dossier_id)
        registry_dossier = registry_dossiers.get(dossier_id)
        if proof is None or not isinstance(registry_dossier, Mapping):
            raise Stage2DeliveryError("Preuve de dossier détaillé absente")
        incident_j0_day = _integer(
            registry_dossier.get("incidentJ0Day"), label="J0 incident détaillé"
        )
        normalised_priority = {
            field: _canonical_identity_value(field, priority.get(field))
            for field in (
                "operating_point_id",
                "mechanism",
                "lane_id",
                "supplier_id",
                "item_id",
                "dst_node_id",
                "target_product_id",
            )
        }
        if any(
            _canonical_identity_value(field, registry_dossier.get(field)) != value
            for field, value in normalised_priority.items()
        ):
            raise Stage2DeliveryError(
                "Le registre lots ne porte pas l'identité du dossier signé"
            )
        availability = {
            "shipment": any(
                row.get("shipment_id") or row.get("shipment_ids")
                for row in selected_genealogy
            ),
            "material_lot": any(
                row.get("receipt_lot_id")
                or row.get("material_lot_id")
                or row.get("source_lot_id")
                for row in selected_genealogy
            ),
            "production": any(
                row.get("campaign_id") or row.get("batch_id")
                for row in selected_genealogy
            ),
            "finished_lot": any(
                row.get("finished_lot_id") or row.get("released_lot_id_same_day")
                for row in selected_genealogy
            ),
            "aggregated_client": any(
                row.get("client_node_id") for row in selected_genealogy
            ),
        }
        output.append(
            {
                "dossier_id": dossier_id,
                "state": str(priority["operating_point_id"]),
                "mechanism": str(priority["mechanism"]),
                "lane_id": str(priority["lane_id"]),
                "supplier_id": str(priority["supplier_id"]),
                "item_id": str(priority["item_id"]).removeprefix("item:"),
                "dst_node_id": str(priority["dst_node_id"]),
                "target_product_id": str(priority["target_product_id"]).removeprefix(
                    "item:"
                ),
                "representative_seed": int(dossier["seed"]),
                "incident_j0_day": incident_j0_day,
                "risk_window_end_day": incident_j0_day + 41,
                "risk_window_days": 42,
                "priority_status": str(priority["priority_status"]),
                "proof_level": str(proof["status"]),
                "trace_counts": proof["trace_counts"],
                "signed_baseline_minus_incident": {
                    "service_pp": _number(
                        kpis.get("service_loss_pp"), label="écart service détaillé"
                    ),
                    "on_due_units": _number(
                        kpis.get("on_due_units_lost"),
                        label="écart unités à l'heure détaillé",
                    ),
                    "production_released_qty": _number(
                        kpis.get("production_released_loss_qty"),
                        label="écart production détaillé",
                    ),
                },
                "curves": _dense_paired_curves(curve_path),
                "genealogy_rows": selected_genealogy,
                "j0_context": _client_j0_rows(j0_rows, dossier_id),
                "trace_availability": availability,
                "missing_native_trace_stages": list(
                    registry_dossier.get("missingNativeTraceStages") or []
                ),
                "cross_arm_lot_matching_used": False,
            }
        )
    if len(output) != len(selection) or len(output) > common.MAX_DETAILED_DOSSIERS:
        raise Stage2DeliveryError("Le nombre de dossiers détaillés a changé")
    return output


def _quantile(values: Sequence[float], probability: float) -> float:
    return curves_v7.curve_v4.linear_quantile(values, probability)


def _summary(values: Sequence[float]) -> dict[str, Any]:
    clean = [float(value) for value in values]
    if not clean:
        return {"count": 0, "mean": None, "median": None, "p10": None, "p90": None}
    return {
        "count": len(clean),
        "mean": statistics.fmean(clean),
        "median": statistics.median(clean),
        "p10": _quantile(clean, 0.10),
        "p90": _quantile(clean, 0.90),
    }


def _optional_row_number(row: Mapping[str, Any], field: str) -> float | None:
    return _number(row.get(field), label=field, optional=True)


def _action_presentation(result: Mapping[str, Any]) -> dict[str, list[str]]:
    action_id = str(result.get("action_id") or "")
    parameters = result.get("action_parameters")
    units = result.get("action_parameter_units")
    scope = result.get("action_physical_scope")
    if not all(isinstance(value, Mapping) for value in (parameters, units, scope)):
        raise Stage2DeliveryError("Paramètres opérationnels d'action absents")
    assert isinstance(parameters, Mapping)
    assert isinstance(units, Mapping)
    assert isinstance(scope, Mapping)
    if action_id == actions_v4.ACTION_STOCK:
        expected = {"measurement_start_stock_scale"}
        if (
            set(parameters) != expected
            or set(units) != expected
            or units.get("measurement_start_stock_scale") != "ratio_sans_unité"
            or not {
                "node_id",
                "item_id",
                "graph_opening_stock_qty",
                "uom",
            }.issubset(scope)
        ):
            raise Stage2DeliveryError("Paramètre inconnu pour le stock prépositionné")
        scale = float(
            _number(parameters["measurement_start_stock_scale"], label="ratio stock")
        )
        if scale <= 1.0:
            raise Stage2DeliveryError("Le stock prépositionné ne renforce pas J0")
        parameter_lines = [
            f"stock libre cible à J0 : {scale:.3g} fois le stock initial signé "
            f"(soit +{100.0 * (scale - 1.0):.1f} %)"
        ]
        scope_lines = [
            f"site {scope.get('node_id')} · article {str(scope.get('item_id') or '').removeprefix('item:')}",
            (
                f"stock initial du graphe : {scope.get('graph_opening_stock_qty')} "
                f"{scope.get('uom') or 'unité source'}"
            ),
        ]
    elif action_id == actions_v4.ACTION_LEAD:
        expected = {"lead_time_adjustment_days"}
        if (
            set(parameters) != expected
            or set(units) != expected
            or units.get("lead_time_adjustment_days") != "jour"
            or not {"supplier_id", "item_id", "dst_node_id"}.issubset(scope)
        ):
            raise Stage2DeliveryError("Paramètre inconnu pour le délai futur")
        adjustment = float(
            _number(parameters["lead_time_adjustment_days"], label="réduction délai")
        )
        if adjustment >= 0.0:
            raise Stage2DeliveryError("Le contrat n'abaisse pas le délai futur")
        parameter_lines = [
            f"délai planifié des futurs départs réduit de {abs(adjustment):g} jours"
        ]
        scope_lines = [
            (
                f"fournisseur {scope.get('supplier_id')} · article "
                f"{str(scope.get('item_id') or '').removeprefix('item:')} · "
                f"destination {scope.get('dst_node_id')}"
            )
        ]
    elif action_id == actions_v4.ACTION_REALLOCATION:
        expected = {"target_lane_priority_weight"}
        if (
            set(parameters) != expected
            or set(units) != expected
            or units.get("target_lane_priority_weight") != "poids_relatif_sans_unité"
            or not {
                "target_supplier_id",
                "item_id",
                "dst_node_id",
                "active_alternatives",
            }.issubset(scope)
        ):
            raise Stage2DeliveryError("Paramètre inconnu pour la réallocation")
        weight = float(
            _number(parameters["target_lane_priority_weight"], label="poids voie cible")
        )
        alternatives = scope.get("active_alternatives")
        if (
            not 0.0 < weight < 1.0
            or not isinstance(alternatives, list)
            or not alternatives
        ):
            raise Stage2DeliveryError("Réallocation sans voie alternative active")
        alternative_labels = [
            f"{row.get('supplier_id')} ({row.get('lane_id')})"
            for row in alternatives
            if isinstance(row, Mapping)
        ]
        if len(alternative_labels) != len(alternatives):
            raise Stage2DeliveryError("Identité d'une voie alternative invalide")
        parameter_lines = [
            f"poids relatif conservé sur la voie ciblée : {100.0 * weight:.1f} %"
        ]
        scope_lines = [
            (
                f"article {str(scope.get('item_id') or '').removeprefix('item:')} · "
                f"destination {scope.get('dst_node_id')}"
            ),
            "voies alternatives déjà actives dans la simulation : "
            + ", ".join(alternative_labels),
        ]
    else:
        raise Stage2DeliveryError("Levier d'action non autorisé dans la présentation")
    if any("None" in line for line in (*parameter_lines, *scope_lines)):
        raise Stage2DeliveryError("Périmètre opérationnel d'action incomplet")
    return {"parameter_lines_fr": parameter_lines, "scope_lines_fr": scope_lines}


ACTION_IDENTITY_FIELDS = (
    "operating_point_id",
    "mechanism",
    "lane_id",
    "supplier_id",
    "item_id",
    "dst_node_id",
    "target_product_id",
)
ACTION_OPTIONAL_IDENTITY_FIELDS = ("edge_id", "priority_status")


def _canonical_action_identity_value(row: Mapping[str, Any], field: str) -> str:
    value = str(row.get(field) or "").strip()
    if field in {"item_id", "target_product_id"}:
        return value.removeprefix("item:")
    return value


def _validate_action_identity(
    source: Mapping[str, Any], selected: Mapping[str, Any], *, label: str
) -> None:
    for field in ACTION_IDENTITY_FIELDS:
        if _canonical_action_identity_value(
            source, field
        ) != _canonical_action_identity_value(selected, field):
            raise Stage2DeliveryError(
                f"L'identité {label} diffère du dossier signé sur {field}"
            )
    for field in ACTION_OPTIONAL_IDENTITY_FIELDS:
        if str(source.get(field) or "").strip() and _canonical_action_identity_value(
            source, field
        ) != _canonical_action_identity_value(selected, field):
            raise Stage2DeliveryError(
                f"L'identité {label} diffère du dossier signé sur {field}"
            )


def _action_results(
    paths: common.Stage2Paths, selection: Sequence[Mapping[str, Any]]
) -> dict[str, Any]:
    if not selection:
        return {"status": "no_signed_dossier", "actions": [], "refusals": []}
    summary, validation = actions_v4.validate_action_results(paths.action_replay_root)
    if validation.get("checks", {}).get("closed_loop_claimed") is not False:
        raise Stage2DeliveryError(
            "Le résultat d'action revendique à tort une boucle fermée"
        )
    per_seed = common._read_csv(paths.action_replay_root / "action_replay_per_seed.csv")  # noqa: SLF001
    actions = []
    selected_by_id = {str(row["dossier_id"]): row for row in selection}
    if len(selected_by_id) != len(selection):
        raise Stage2DeliveryError("Identifiant de dossier signé dupliqué")
    seen_actions: set[tuple[str, str]] = set()
    field_contract = {
        "service": {
            "label": "Service à l'heure",
            "unit": "%",
            "baseline": "baseline__impact_window_service_on_due_pct",
            "incident": "incident_no_action__impact_window_service_on_due_pct",
            "action": "incident_with_action__service_on_due_pct",
            "gain": "action_vs_incident__service_gain_pp",
            "gain_key": "service_gain_pp",
        },
        "backlog": {
            "label": "Retard client cumulé",
            "unit": "UN·jours",
            "baseline": "baseline__state_window_global_backlog_qty_days",
            "incident": "incident_no_action__state_window_global_backlog_qty_days",
            "action": "incident_with_action__state_window_global_backlog_qty_days",
            "gain": "action_vs_incident__backlog_qty_days_avoided",
            "gain_key": "backlog_qty_days_avoided",
        },
        "production": {
            "label": "Production libérée",
            "unit": "UN",
            "baseline": "baseline__state_window_production_released_qty",
            "incident": "incident_no_action__state_window_production_released_qty",
            "action": "incident_with_action__state_window_production_released_qty",
            "gain": "action_vs_incident__production_released_gain_qty",
            "gain_key": "production_released_gain_qty",
        },
    }
    for result in summary.get("action_results") or []:
        dossier_id = str(result["dossier_id"])
        action_id = str(result["action_id"])
        selected = selected_by_id.get(dossier_id)
        action_key = (dossier_id, action_id)
        if (
            selected is None
            or action_id not in common.ALLOWED_ACTIONS
            or action_key in seen_actions
        ):
            raise Stage2DeliveryError(
                "Un résultat d'action sort des dossiers et leviers signés"
            )
        _validate_action_identity(result, selected, label="du résumé action")
        seen_actions.add(action_key)
        presentation = _action_presentation(result)
        exercised_count = _integer(
            result.get("physically_exercised_seed_count"),
            label="graines où l'action a agi",
        )
        paired_count = _integer(
            result.get("paired_seed_count"), label="graines appariées de l'action"
        )
        if (
            not 0 <= exercised_count <= paired_count <= common.EXPECTED_CAMPAIGN_SEEDS
            or (paired_count == 0)
        ):
            raise Stage2DeliveryError("Population appariée d'action invalide")
        action_rows = [
            row
            for row in per_seed
            if row.get("dossier_id") == dossier_id and row.get("action_id") == action_id
        ]
        for row in action_rows:
            _validate_action_identity(row, selected, label="du résultat par scénario")
        rows = [
            row
            for row in action_rows
            if _truthy(
                row.get("included_in_action_gain_statistics"), label="inclusion action"
            )
        ]
        if len(rows) != exercised_count:
            raise Stage2DeliveryError(
                "La population d'action physiquement exercée diffère"
            )
        metrics = []
        if exercised_count == 0:
            if result.get("status") != "non_exercised_no_gain_estimate" or any(
                int((stats or {}).get("count") or 0) != 0
                for stats in (result.get("gain_statistics") or {}).values()
            ):
                raise Stage2DeliveryError(
                    "Une action jamais exercée contient un gain estimé"
                )
            metrics = [
                {
                    "id": metric_id,
                    "label": contract["label"],
                    "unit": contract["unit"],
                    "available": False,
                    "reason_fr": (
                        "Action simulée mais jamais physiquement exercée dans les "
                        "scénarios aléatoires comparables; aucun gain estimable."
                    ),
                }
                for metric_id, contract in field_contract.items()
            ]
        for metric_id, contract in field_contract.items():
            if exercised_count == 0:
                continue
            values_by_field: dict[str, list[float]] = {}
            available = True
            for kind in ("baseline", "incident", "action", "gain"):
                values = [
                    _optional_row_number(row, str(contract[kind])) for row in rows
                ]
                if any(value is None for value in values):
                    available = False
                    break
                values_by_field[kind] = [
                    float(value) for value in values if value is not None
                ]
            if not available:
                metrics.append(
                    {
                        "id": metric_id,
                        "label": contract["label"],
                        "unit": contract["unit"],
                        "available": False,
                    }
                )
                continue
            levels = {kind: _summary(values_by_field[kind]) for kind in values_by_field}
            signed_gain = (result.get("gain_statistics") or {}).get(
                contract["gain_key"]
            )
            if not isinstance(signed_gain, Mapping):
                raise Stage2DeliveryError(
                    f"Gain signé absent : {action_id}/{metric_id}"
                )
            for field in ("count", "mean", "median", "p10", "p90"):
                actual = levels["gain"][field]
                expected = signed_gain.get(field)
                if field == "count":
                    valid = int(actual or 0) == int(expected or 0)
                else:
                    valid = math.isclose(
                        float(actual), float(expected), rel_tol=1e-10, abs_tol=1e-8
                    )
                if not valid:
                    raise Stage2DeliveryError(
                        "Le gain d'action ne reproduit pas le résumé signé"
                    )
            metric_payload = {
                "id": metric_id,
                "label": contract["label"],
                "unit": contract["unit"],
                "available": True,
                "baseline": levels["baseline"],
                "incident_without_action": levels["incident"],
                "incident_with_action": levels["action"],
                "signed_action_effect": levels["gain"],
            }
            if metric_id == "service":
                metric_payload["signed_reference_minus_action_gap"] = _summary(
                    [
                        baseline - action
                        for baseline, action in zip(
                            values_by_field["baseline"],
                            values_by_field["action"],
                            strict=True,
                        )
                    ]
                )
            metrics.append(metric_payload)
        actions.append(
            {
                "dossier_id": dossier_id,
                "state": selected["operating_point_id"],
                "mechanism": selected["mechanism"],
                "lane_id": selected["lane_id"],
                "supplier_id": selected["supplier_id"],
                "item_id": _canonical_action_identity_value(selected, "item_id"),
                "target_product_id": _canonical_action_identity_value(
                    selected, "target_product_id"
                ),
                "action_id": action_id,
                "label_fr": result["action_label_fr"],
                "status": result["status"],
                "paired_seed_count": result["paired_seed_count"],
                "physically_exercised_seed_count": result[
                    "physically_exercised_seed_count"
                ],
                **presentation,
                "limits_fr": result["limits_fr"],
                "metrics": metrics,
                "open_loop": True,
                "lot_trace_available": False,
                "days_recovered_available": False,
                "complete_cost_or_roi_available": False,
            }
        )
    refusals = [
        {
            "dossier_id": row["dossier_id"],
            "action_id": row["action_id"],
            "label_fr": row["label_fr"],
            "reason": row["refusal_reason"],
            "simulated": False,
        }
        for row in summary.get("refused_actions") or []
    ]
    return {"status": summary["status"], "actions": actions, "refusals": refusals}


def _source_binding(
    path: Path, role: str, signature: str | None = None
) -> dict[str, Any]:
    record = {
        "role": role,
        "path": str(path.resolve()),
        "sha256": common.sha256_file(path.resolve()),
        "size_bytes": path.resolve().stat().st_size,
    }
    if signature is not None:
        record["signature"] = signature
    return record


def collect_payload(
    paths: common.Stage2Paths,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Revalidate every source and reduce it to presentation-safe evidence."""

    paths = paths.resolved()
    from etudecas.prototypes.scan_2027_risk_control import (
        supplier_v7_stage2_pipeline as pipeline_v7,
    )

    stage2_contract_path = (paths.supervision_dir / pipeline_v7.CONTRACT_NAME).resolve()
    stage2_contract = pipeline_v7.validate_bound_contract(paths)
    upstream_receipt_path = (
        paths.supervision_dir / common.STAGE1_RECEIPT_NAME
    ).resolve()
    upstream = common.validate_bound_stage1_receipt(paths, upstream_receipt_path)
    result = protocol_v7.validate_result(paths.v7_plan_dir, paths.v7_run_dir)
    dashboard = dashboard_v7.load_dashboard_data(
        results_dir=paths.results_dir,
        target_registry_path=paths.results_dir / "cross_state_target_registry.json",
    )
    if int(dashboard.get("repetitions") or -1) != common.EXPECTED_CAMPAIGN_SEEDS:
        raise Stage2DeliveryError("La campagne incidents n'a pas ses 30 graines")
    selection = _selection(paths)
    lane_rows = _incident_lane_rows(paths)
    lane_sensitivity = _lane_sensitivity(paths)
    supplier_stability = _supplier_stability(paths)
    focus = _focus(paths, lane_rows, selection)

    curve_proof = curves_v7.validate_curve_package(
        paths.curves_dir, plan_dir=paths.v7_plan_dir, run_dir=paths.v7_run_dir
    )
    curve_payload = curves_v7.load_curve_payload(paths.curves_dir)
    nominal = _weekly_nominal(curve_payload, focus)

    replay_root = paths.lot_replay_root if selection else None
    qualification = physical_v5.validate_qualification_sidecar(
        campaign_root=paths.campaign_root,
        results_dir=paths.results_dir,
        replay_root=replay_root,
        output_dir=paths.qualification_dir,
    )
    qualification_payload = common.read_json(
        paths.qualification_dir / physical_v5.PAYLOAD_FILE
    )
    if (
        qualification_payload.get("counts", {}).get("full_dynamic_cascade_proven_count")
        != 0
    ):
        raise Stage2DeliveryError(
            "Une cascade dynamique complète est revendiquée sans preuve"
        )
    focus_qualification = next(
        (
            row
            for row in qualification_payload.get("lanes") or []
            if row.get("lane_id") == focus["lane_id"]
        ),
        None,
    )
    if focus_qualification is None:
        raise Stage2DeliveryError("Qualification physique du dossier affiché absente")

    registry_proof = registry_v6.validate_delivery(paths.registry_dir)
    registry_payload = common.read_json(paths.registry_dir / registry_v6.JSON_FILE)
    scope = registry_payload.get("scope") or {}
    if (
        scope.get("incidentExposureRowCount") != common.EXPECTED_INCIDENTS
        or scope.get("availableDetailedReplayCount") != len(selection)
        or scope.get("actionLotTraceAvailable") is not False
    ):
        raise Stage2DeliveryError("Le registre incidents/lots a changé de portée")
    details = _detailed_replays(paths, selection, registry_payload)
    actions = _action_results(paths, selection)
    observed_source = common.validate_observed_2025_pack(paths.observed_2025_dir)
    observed = (
        {key: value for key, value in observed_source.items() if key != "manifest"}
        if observed_source is not None
        else None
    )

    payload_unsigned = {
        "schema_version": SCHEMA_VERSION,
        "status": "complete_validated",
        "title": "Risques fournisseurs : où la supply devient-elle fragile ?",
        "view_count": 3,
        "terminology": {
            "OBSERVÉ": (
                "ce que vos fichiers 2025 montrent directement; ici des valeurs de CA "
                "et des valeurs comptables de stock"
            ),
            "SIMULÉ": (
                "ce que calcule le modèle pour un fonctionnement, un incident ou une "
                "action imposés comme hypothèses"
            ),
            "SIGNAL DE PRIORITÉ": (
                "dossier fournisseur–article–site à examiner d'abord car sa conséquence "
                "simulée ressort; ni note fournisseur ni probabilité d'incident"
            ),
            "HYPOTHÈSE": "situation ou action imposée au modèle, à calibrer avec l'historique",
        },
        "validation": {
            "states": _validation_states(result),
            "seed_blocks": common.EXPECTED_VALIDATION_SEEDS,
            "physical_cases": common.EXPECTED_VALIDATION_CASES,
            "accepted": True,
            "engine_simulations": common.EXPECTED_VALIDATION_CASES,
            "bootstrap_resamples": int(
                result.get("bootstrap", {}).get("replicates") or 0
            ),
            "campaign_subset_used_for_acceptance": False,
        },
        "campaign": {
            "pairing_seed_count": common.EXPECTED_CAMPAIGN_SEEDS,
            "baseline_reference_count": common.EXPECTED_BASELINES,
            "incident_case_count": common.EXPECTED_INCIDENTS,
            "row_count": common.EXPECTED_CAMPAIGN_ROWS,
            "mechanisms": [
                {
                    "id": "transport_delay",
                    "label": "Retard de transport +120 jours",
                    "hypothesis": (
                        "Les départs planifiés pendant une fenêtre de 42 jours "
                        "arrivent 120 jours plus tard."
                    ),
                },
                {
                    "id": "planned_delivery_shortfall",
                    "label": "Quantité normalement livrable × 0,5 pendant 42 jours",
                    "hypothesis": (
                        "La quantité planifiée normalement livrable est divisée par deux "
                        "dans la fenêtre ciblée de 42 jours."
                    ),
                },
            ],
            "incidents_are_conditional_hypotheses": True,
            "historical_probability_available": False,
            "multiple_incidents_combined": False,
        },
        "observed_2025": observed,
        "lane_sensitivity": lane_sensitivity,
        "supplier_stability": supplier_stability,
        "portfolio": _portfolio_summary(supplier_stability),
        "focus": focus,
        "nominal_curves": {
            "population": (
                "30 scénarios V7 avec les mêmes identifiants et un protocole de "
                "nombres aléatoires communs; les trajectoires peuvent diverger "
                "avec l'état"
            ),
            "scientific_acceptance_population": False,
            "weekly_display_sampling_after_smoothing": True,
            "series": nominal,
        },
        "cascade": {
            "focus_qualification": focus_qualification,
            "detailed_replays": details,
            "selected_dossier_count": len(selection),
            "selection_forced": False,
            "registry_incident_case_count": common.EXPECTED_INCIDENTS,
            "genealogy_available_dossier_count": len(details),
            "all_incidents_have_lot_trace": False,
            "full_dynamic_stock_mrp_production_service_cascade_proven": False,
            "physical_scope": "contact généalogique natif jusqu'au client agrégé quand disponible",
        },
        "actions": actions,
        "limits": {
            "quality_incident_included": False,
            "capacity_or_availability_modified": False,
            "incident_generation": "exogène",
            "consequences_depend_on_evolving_network_state": True,
            "automatic_regulation": False,
            "action_control_mode": "boucle ouverte",
            "customers": "clients agrégés uniquement",
            "lots": "lots simulés uniquement",
            "complete_cost_or_roi_available": False,
            "supplier_historical_probability_requires": (
                "commandes fournisseurs réelles avec dates promises/reçues, quantités, fournisseur et cause"
            ),
        },
        "bindings": {
            "stage2_contract_signature": stage2_contract["contract_signature"],
            "stage2_contract_sha256": common.sha256_file(stage2_contract_path),
            "upstream_validation_signature": upstream["validation_signature"],
            "upstream_validation_receipt_sha256": common.sha256_file(
                upstream_receipt_path
            ),
            "v7_result_signature": result["result_signature"],
            "curve_manifest_signature": curve_proof["manifest_signature"],
            "qualification_signature": qualification["qualification_signature"],
            "registry_manifest_sha256": registry_proof["manifestSha256"],
        },
    }
    payload = common.signed(payload_unsigned, "payload_signature")
    sources = [
        _source_binding(
            stage2_contract_path,
            "contrat_etape_2",
            stage2_contract["contract_signature"],
        ),
        _source_binding(
            upstream_receipt_path,
            "recu_validation_etape_1",
            upstream["validation_signature"],
        ),
        _source_binding(
            paths.v7_run_dir / "validation_result.json",
            "validation_v7_450",
            result["result_signature"],
        ),
        _source_binding(
            paths.results_dir / "campaign_validation.json", "campagne_3330"
        ),
        _source_binding(
            paths.results_dir / finalizer_v7.V7_RESULT_OVERLAY_NAME,
            "surcouche_resultats_v7",
            upstream["result_overlay_signature"],
        ),
        _source_binding(
            paths.curves_dir / curves_v7.MANIFEST_NAME,
            "courbes_nominales_30",
            curve_proof["manifest_signature"],
        ),
        _source_binding(
            paths.qualification_dir / physical_v5.MANIFEST_FILE,
            "qualification_physique",
            qualification["qualification_signature"],
        ),
        _source_binding(
            paths.registry_dir / registry_v6.MANIFEST_FILE, "registre_incidents_lots"
        ),
    ]
    if selection:
        sources.extend(
            [
                _source_binding(
                    paths.lot_replay_root / "finalized" / "replay_validation.json",
                    "rejeux_lots_detailles",
                ),
                _source_binding(
                    paths.action_replay_root / "action_replay_validation.json",
                    "actions_boucle_ouverte",
                ),
            ]
        )
    if observed_source is not None:
        sources.append(
            _source_binding(Path(observed_source["manifest"]), "contexte_observe_2025")
        )
    return payload, sources


def _safe_json(payload: Mapping[str, Any]) -> str:
    return (
        json.dumps(payload, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
        .replace("&", "\\u0026")
        .replace("\u2028", "\\u2028")
        .replace("\u2029", "\\u2029")
    )


HTML_TEMPLATE = r"""<!doctype html>
<html lang="fr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Risques fournisseurs — démonstration V7</title>
<style>
:root{--navy:#092a4a;--blue:#1969df;--teal:#0e816d;--red:#d64232;--amber:#c77a10;--ink:#132b42;--muted:#607389;--line:#d7e2ec;--paper:#eef3f8;--card:#fff}*{box-sizing:border-box}body{margin:0;background:var(--paper);color:var(--ink);font:15px/1.45 Segoe UI,Arial,sans-serif}header{padding:26px clamp(18px,4vw,58px);background:linear-gradient(120deg,#071d35,#164e7c 65%,#08776e);color:white}h1{font-size:clamp(28px,4vw,48px);line-height:1.08;margin:4px 0 8px}header p{max-width:1000px;margin:0;color:#dbeaf5}.scope{display:flex;flex-wrap:wrap;gap:7px;margin-top:14px}.pill,.badge{display:inline-block;border-radius:999px;padding:5px 9px;font-size:11px;font-weight:750}.pill{border:1px solid #ffffff55}.definitions{display:grid;grid-template-columns:repeat(4,1fr);background:#cbd9e6;gap:1px}.definition{background:white;padding:12px 18px}.definition b{display:block;color:var(--blue);font-size:11px;letter-spacing:.06em}.definition span{color:var(--muted);font-size:12px}.tabs{position:sticky;top:0;z-index:10;display:flex;justify-content:center;gap:8px;padding:10px;background:#f8fbffef;border-bottom:1px solid var(--line)}button,select{font:inherit}.tabs button,.controls button,.controls select{border:1px solid #b7c9da;border-radius:999px;background:white;padding:8px 12px;color:var(--ink);cursor:pointer}.tabs button.active,.controls button.active{background:var(--navy);color:white;border-color:var(--navy)}main{max-width:1280px;margin:auto;padding:18px clamp(12px,3vw,30px) 50px}.view{display:none}.view.active{display:block}.question,.panel,.callout{background:var(--card);border:1px solid var(--line);border-radius:15px;padding:16px;margin:12px 0;box-shadow:0 10px 28px #16334f0d}.question{border-left:6px solid var(--blue)}.question h2,.panel h2,.panel h3{margin:0 0 6px}.question p,.panel>p,.muted{color:var(--muted)}.grid{display:grid;gap:10px}.states{grid-template-columns:repeat(3,1fr)}.observed{grid-template-columns:repeat(2,1fr)}.state,.card,.action{border:1px solid var(--line);border-radius:12px;padding:13px;background:white}.state{border-top:5px solid var(--blue)}.big{font-size:28px;font-weight:800;color:var(--navy)}.small{font-size:11px;color:var(--muted)}.badge.obs{background:#e8f5ee;color:#087054}.badge.sim{background:#e9f1ff;color:#1755a5}.badge.warn{background:#fff0dc;color:#805000}.badge.good{background:#e7f6ef;color:#087054}.badge.bad{background:#ffe9e5;color:#9a2e25}.controls{display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin:10px 0}.chart{display:block;width:100%;height:330px;border:1px solid var(--line);border-radius:12px;background:#fbfdff}.legend{display:flex;gap:14px;flex-wrap:wrap;color:var(--muted);font-size:12px;margin-top:7px}.dot{display:inline-block;width:10px;height:10px;border-radius:50%;margin-right:4px}.table{overflow:auto;border:1px solid var(--line);border-radius:11px}table{border-collapse:collapse;width:100%;min-width:780px}th,td{padding:8px 9px;text-align:left;border-bottom:1px solid #e4ebf2;font-size:12px}th{background:#edf4fa;color:#244969}.cause-grid{grid-template-columns:repeat(2,1fr)}.cause{border-top:5px solid var(--amber)}.chain{display:flex;gap:7px;overflow:auto}.step{flex:1;min-width:145px;border:1px solid var(--line);border-radius:11px;padding:11px;background:#f8fbff}.step.available{border-color:#61aa91;background:#f2fbf7}.step.missing{border-style:dashed;color:var(--muted);background:#f4f6f8}.arrow{display:grid;place-items:center;color:var(--blue);font-size:22px}.action-grid{grid-template-columns:repeat(3,1fr)}.action{border-top:5px solid var(--teal)}.metric-grid{grid-template-columns:repeat(3,1fr)}.metric{border:1px solid var(--line);border-radius:10px;padding:10px}.metric b{display:block;font-size:20px}.callout{border-left:5px solid var(--amber);background:#fffaf0}.callout.good{border-left-color:var(--teal);background:#f2fbf7}.pager{display:flex;align-items:center;gap:8px;margin:9px 0}details{margin-top:10px}footer{max-width:1280px;margin:auto;padding:0 26px 35px;color:var(--muted);font-size:12px}@media(max-width:900px){.definitions,.states,.action-grid,.metric-grid{grid-template-columns:1fr 1fr}}@media(max-width:620px){.definitions,.states,.observed,.cause-grid,.action-grid,.metric-grid{grid-template-columns:1fr}.tabs{justify-content:flex-start;overflow:auto}.tabs button{white-space:nowrap}}@media print{.tabs{display:none}.view{display:block!important;break-before:page}.panel,.question{box-shadow:none}}
</style></head><body>
<header><div class="small" style="color:#9ee8d8;font-weight:800">DÉMONSTRATION AUTONOME · RISQUES FOURNISSEURS</div><h1>Risques fournisseurs : où la supply devient-elle fragile&nbsp;?</h1><p>Trois niveaux de fonctionnement validés, deux incidents hypothétiques séparés, jusqu'à trois analyses détaillées des lots et seulement des leviers réellement représentables.</p><div class="scope" id="scope"></div></header>
<div class="definitions" id="definitions"></div>
<nav class="tabs"><button class="active" data-tab="states">1 · Fragilité et fournisseurs</button><button data-tab="cascade">2 · Incident et lots</button><button data-tab="actions">3 · Leviers pilotables</button></nav>
<main>
<section class="view active" id="states"><div class="question"><h2>Retrouve-t-on les mêmes dossiers fournisseurs quand le réseau se dégrade&nbsp;?</h2><p>Les trois niveaux sont validés sur 150 simulations indépendantes, avec les mêmes identifiants de scénarios et un protocole de nombres aléatoires communs aux trois niveaux; les trajectoires peuvent ensuite diverger avec l'état, soit 450 cas. L'analyse fournisseurs utilise ensuite 30 scénarios aléatoires comparables et garde les deux hypothèses strictement séparées.</p></div><div id="observed"></div><div class="panel"><h2>Trois niveaux de fonctionnement validés</h2><p>Seuls les délais fournisseurs planifiés des flux alimentant chaque produit ont été augmentés. Aucune capacité ni disponibilité fournisseur ou produit fini n'a été modifiée.</p><div class="grid states" id="stateCards"></div><canvas class="chart" id="stateChart" width="1160" height="330"></canvas><p class="small">Référence : borne basse unilatérale 95 %. Niveaux 93/80 : intervalle bilatéral 90 % pour le global. Les produits sont affichés sans intervalle lorsqu'il n'a pas été calculé.</p></div><div class="panel"><h2>Lecture portefeuille : signaux récurrents ou dépendants du niveau</h2><p>Cette synthèse conserve tous les statuts signés; elle ne force aucun « top 3 » et ne change pas les dossiers retenus pour le détail des lots.</p><div id="portfolio"></div></div><div class="panel"><h2>Même voie physique, trois niveaux</h2><p>Quand au moins 24 scénarios sont comparables, le graphique montre les écarts appariés par rapport à la référence avec leur IC95. Sinon, il montre trois points descriptifs non reliés et n'interprète pas de pente.</p><div class="controls"><select id="laneSelect"></select><select id="mechanismSelect"></select></div><div id="laneIdentity"></div><canvas class="chart" id="sensitivityChart" width="1160" height="330"></canvas><div id="supplierStatus"></div></div></section>
<section class="view" id="cascade"><div class="question"><h2 id="focusTitle">Incident fournisseur : où l'effet se propage-t-il&nbsp;?</h2><p id="focusSubtitle"></p></div><div class="grid cause-grid" id="causes"></div><div class="callout"><b>Scénarios unitaires, pas cascade de plusieurs incidents.</b><p>Les 3 240 cas correspondent à 2 scénarios × 18 voies × 3 niveaux × 30 répétitions. Chaque cas impose un seul incident fournisseur; aucune combinaison d'incidents corrélés ou endogènes n'est calculée ici.</p></div><div class="panel"><h2>Résultats agrégés du dossier affiché</h2><p>Moyenne et intervalle central P10–P90 sur 30 répétitions comparables. Le nombre exercé indique les répétitions où une expédition de la voie a réellement reçu l'incident. Les écarts sont signés : positif = perte, négatif = amélioration par rapport au fonctionnement sans incident.</p><div class="table"><table><thead><tr><th>Niveau</th><th>Hypothèse</th><th>Écart moyen de service sans incident − incident</th><th>P10–P90</th><th>Répétitions avec flux touché</th><th>Lecture du signal simulé</th></tr></thead><tbody id="focusRows"></tbody></table></div></div><div class="panel"><h2>Fonctionnement sans incident — 30 répétitions V7</h2><p>Courbes nominales : MM28 pour service et flux, dont l'écart au plan de lots; MM7 pour stocks, encours, retard et signal de contrainte. Ces 30 répétitions illustrent le fonctionnement; la validation des niveaux repose séparément sur 150 répétitions et 450 cas.</p><div class="controls"><select id="nominalMetric"></select></div><canvas class="chart" id="nominalChart" width="1160" height="330"></canvas><div class="legend"><span><i class="dot" style="background:#1969df"></i>Référence</span><span><i class="dot" style="background:#9a65c7"></i>Niveau 93</span><span><i class="dot" style="background:#d64232"></i>Niveau 80</span><span>zone claire = intervalle central P10–P90</span></div></div><div class="panel"><h2>Propagation physique et lots simulés</h2><div id="cascadeScope"></div><div id="detailArea"></div></div></section>
<section class="view" id="actions"><div class="question"><h2>Quelles actions pouvons-nous réellement décider&nbsp;?</h2><p>Les actions sont décidées avant chaque calcul et restent en boucle ouverte : ce n'est pas une régulation automatique.</p></div><div id="actionArea"></div><div class="callout"><b>Délai de récupération non calculé par ce protocole.</b><p>Les courbes quotidiennes appariées de référence ne sont pas conservées dans les bras action. Aucun jour récupéré, lot sauvé, coût complet ou ROI n'est donc annoncé.</p></div><div class="panel"><h2>Actions volontairement refusées</h2><p>Un actionneur non ciblable ou une capacité non prouvée n'est pas transformé en solution par le modèle.</p><div id="refusals"></div></div></section>
</main><footer>Aucun incident qualité · aucune capacité/disponibilité modifiée · aucune probabilité historique · incidents exogènes, conséquences dépendantes de l'état du réseau · actions en boucle ouverte · clients agrégés · lots simulés. La probabilité fournisseur industrielle reste à calibrer avec les commandes promises et reçues réelles.</footer>
<script>const D=__DATA__;const $=id=>document.getElementById(id),esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c])),num=(v,d=1)=>v==null?'—':new Intl.NumberFormat('fr-FR',{maximumFractionDigits:d}).format(Number(v)),stateLabel=s=>({op_100:'Référence',op_93:'Niveau 93',op_80:'Niveau 80'}[s]||s),mech=id=>D.campaign.mechanisms.find(x=>x.id===id),status=s=>({robust_priority:'signal robuste dans cet état',dossier_to_investigate:'dossier à instruire',global_only_not_confirmed_within_target_product:'signal global non confirmé pour ce produit',supplementary_backlog_signal:'signal de retard séparé',insufficient_comparable_exposure:'comparaison inter-états non conclue',robust_priority_all_states:'signal robuste dans les trois états',priority_all_states:'signal à instruire dans les trois états',state_specific_priority:'signal dépendant du niveau',detected_lower_priority:'effet détecté, priorité plus basse',no_detected_effect:'effet non détecté'}[s]||s||'aucun signal qualifié');
document.querySelectorAll('.tabs button').forEach(b=>b.onclick=()=>{document.querySelectorAll('.tabs button').forEach(x=>x.classList.toggle('active',x===b));document.querySelectorAll('.view').forEach(x=>x.classList.toggle('active',x.id===b.dataset.tab));scrollTo(0,0)});$('scope').innerHTML=[`${D.validation.seed_blocks} simulations indépendantes / ${D.validation.physical_cases} cas de validation`,`30 scénarios aléatoires comparables par situation`,`${D.campaign.incident_case_count} cas avec un incident hypothétique`,`jusqu'à 3 analyses détaillées avec lots`].map(x=>`<span class="pill">${esc(x)}</span>`).join('');$('definitions').innerHTML=Object.entries(D.terminology).map(([k,v])=>`<div class="definition"><b>${esc(k)}</b><span>${esc(v)}</span></div>`).join('');
function renderObserved(){const o=D.observed_2025;if(!o){$('observed').innerHTML='<div class="callout">Contexte observé 2025 non fourni à ce paquet.</div>';return}const products=o.products.map(p=>`<div class="card"><span class="badge obs">OBSERVÉ 2025</span><h3>Produit ${esc(p.product_id)}</h3><div class="big">${num(p.lost_revenue_raw_source_value,2)}</div><div>Valeur de CA perdu déclarée dans le fichier 2025 — devise non renseignée</div><p><b>${num(p.lost_share_of_raw_potential_pct,2)} %</b> du potentiel financier brut source. Ce taux financier n'est ni un OTIF ni un service en unités.</p>${p.negative_adjustments_source_value<0?`<p class="small">La valeur brute de ${esc(p.product_id)} conserve l'ajustement négatif source de ${num(p.negative_adjustments_source_value,2)}.</p>`:''}</div>`).join('');const stocks=o.stocks.map(s=>`<li><b>${esc(s.series_id)}</b> : moyenne ${num(s.mean_accounting_value_source,2)}, dernière valeur ${num(s.last_accounting_value_source,2)} — devise non renseignée; valeur comptable immobilisée, pas quantité physique.${s.source_family_label?` Les fichiers disponibles ne permettent pas de relier la famille ${esc(s.source_family_label)} à un produit.`:''}</li>`).join('');$('observed').innerHTML=`<div class="panel"><h2>Ce que vos fichiers 2025 montrent directement</h2><div class="grid observed">${products}</div><div class="callout"><b>Aucune attribution causale fournisseur.</b><p>Ces fichiers ne permettent pas d'attribuer ces valeurs à un fournisseur, une commande, un lot ou une cause.</p><details><summary>Valeurs comptables de stock</summary><ul>${stocks}</ul></details></div></div>`}renderObserved();
const measure=s=>Object.fromEntries(s.measures.map(x=>[x.id,x]));$('stateCards').innerHTML=D.validation.states.map(s=>{const m=measure(s);return`<article class="state"><span class="badge sim">SIMULÉ · 150 RÉPÉTITIONS</span><h3>${esc(s.label)}</h3><div class="big">${num(m.global.service_pct,2)} %</div><div>Service global</div><p>268091 : <b>${num(m['268091'].service_pct,2)} %</b><br>268967 : <b>${num(m['268967'].service_pct,2)} %</b></p><p class="small">+${num(s.planned_lead_offset_days['268091'],1)} j vers 268091 · +${num(s.planned_lead_offset_days['268967'],1)} j vers 268967</p></article>`}).join('');
function axes(ctx,W,H,min,max){ctx.clearRect(0,0,W,H);ctx.strokeStyle='#dfe7ef';ctx.fillStyle='#607389';ctx.font='12px Segoe UI';for(let i=0;i<5;i++){const y=25+i*(H-70)/4,v=max-(max-min)*i/4;ctx.beginPath();ctx.moveTo(55,y);ctx.lineTo(W-20,y);ctx.stroke();ctx.fillText(num(v,1),5,y+4)}return v=>25+(max-v)*(H-70)/(max-min||1)}function drawState(){const c=$('stateChart'),x=c.getContext('2d'),W=c.width,H=c.height,vals=D.validation.states.flatMap(s=>s.measures.map(m=>m.service_pct)),min=Math.max(0,Math.min(...vals)-5),max=100,y=axes(x,W,H,min,max),colors={global:'#1969df','268091':'#0e816d','268967':'#c77a10'},xs=D.validation.states.map((s,i)=>150+i*(W-300)/2);D.validation.states.forEach((s,i)=>{x.fillStyle='#607389';x.fillText(stateLabel(s.id),xs[i]-30,H-15);s.measures.forEach((m,j)=>{const xx=xs[i]+(j-1)*28;x.strokeStyle=colors[m.id];x.lineWidth=3;x.beginPath();x.arc(xx,y(m.service_pct),5,0,Math.PI*2);x.fillStyle=colors[m.id];x.fill();if(m.interval.low!=null){x.beginPath();x.moveTo(xx,y(m.interval.low));x.lineTo(xx,m.interval.high==null?y(m.service_pct):y(m.interval.high));x.stroke()}})});x.fillStyle='#1969df';x.fillText('● global',70,18);x.fillStyle='#0e816d';x.fillText('● 268091',160,18);x.fillStyle='#c77a10';x.fillText('● 268967',260,18)}drawState();
function renderPortfolio(){const groups=D.portfolio.mechanisms;$('portfolio').innerHTML=groups.map(g=>`<h3>${esc(mech(g.mechanism).label)}</h3><p><b>${g.recurring_signal_count}</b> fournisseur(s) portent un signal à instruire dans les trois niveaux, dont <b>${g.robust_recurring_signal_count}</b> robuste(s) dans les trois. Ce compte décrit la récurrence du signal simulé, pas une probabilité d'incident.</p><div class="table"><table><thead><tr><th>Fournisseur</th><th>Référence</th><th>Niveau 93</th><th>Niveau 80</th><th>Conclusion inter-niveaux</th></tr></thead><tbody>${g.rows.map(r=>`<tr><td><b>${esc(r.supplier_id)}</b><br><small>${r.same_dominant_lane?'même voie dominante':'voie dominante différente selon le niveau'}</small></td>${['op_100','op_93','op_80'].map(s=>`<td>${esc(status(r.states[s].priority_status))}</td>`).join('')}<td>${esc(status(r.stability_status))}${r.priority_in_all_three_states?'<br><span class="badge good">signal dans les 3 niveaux</span>':''}</td></tr>`).join('')}</tbody></table></div>`).join('')+`<p class="small">${esc(D.portfolio.selection_rule)}</p>`}renderPortfolio();
const laneIds=[...new Set(D.lane_sensitivity.map(x=>x.lane_id))];$('laneSelect').innerHTML=laneIds.map(id=>`<option value="${esc(id)}" ${id===D.focus.lane_id?'selected':''}>${esc(id)}</option>`).join('');$('mechanismSelect').innerHTML=D.campaign.mechanisms.map(x=>`<option value="${esc(x.id)}">${esc(x.label)}</option>`).join('');function drawSensitivity(){const lane=$('laneSelect').value,m=$('mechanismSelect').value,row=D.lane_sensitivity.find(x=>x.lane_id===lane&&x.mechanism===m);if(!row)return;const order=['op_100','op_93','op_80'],paired=order.map(s=>row.paired_changes_vs_reference_pp[s]),vals=row.state_comparison_valid?paired.map(v=>v.mean):order.map(s=>row.states[s].effect_mean_pp),bounds=row.state_comparison_valid?paired.flatMap(v=>[v.ci95_low,v.ci95_high]):vals,min=Math.min(0,...bounds),max=Math.max(1,...bounds),pad=Math.max(1,(max-min)*.15),c=$('sensitivityChart'),x=c.getContext('2d'),W=c.width,H=c.height,y=axes(x,W,H,min-pad,max+pad),xs=[180,W/2,W-180];if(row.state_comparison_valid){x.strokeStyle='#1969df';x.lineWidth=3;x.beginPath();vals.forEach((v,i)=>i?x.lineTo(xs[i],y(v)):x.moveTo(xs[i],y(v)));x.stroke()}vals.forEach((v,i)=>{if(row.state_comparison_valid){x.strokeStyle='#1969df';x.lineWidth=2;x.beginPath();x.moveTo(xs[i],y(paired[i].ci95_low));x.lineTo(xs[i],y(paired[i].ci95_high));x.moveTo(xs[i]-6,y(paired[i].ci95_low));x.lineTo(xs[i]+6,y(paired[i].ci95_low));x.moveTo(xs[i]-6,y(paired[i].ci95_high));x.lineTo(xs[i]+6,y(paired[i].ci95_high));x.stroke()}x.fillStyle=row.state_comparison_valid?'#1969df':'#9aa9b7';x.beginPath();x.arc(xs[i],y(v),6,0,Math.PI*2);x.fill();x.fillStyle='#607389';x.fillText(stateLabel(order[i]),xs[i]-30,H-15);x.fillStyle='#132b42';x.fillText(`${num(v,2)} pt`,xs[i]-22,y(v)-12)});const comparisonText=row.state_comparison_valid?`${esc(row.interpretation_fr)} Les valeurs sont les écarts appariés à la référence; les traits verticaux sont les IC95.`:'Les points sont des moyennes descriptives séparées sur 30 répétitions. Ils ne sont pas reliés et aucune pente inter-niveaux n’est interprétée.';$('laneIdentity').innerHTML=`<p><b>${esc(row.supplier_id)}</b> · voie ${esc(row.lane_id)} · produit ${esc(row.target_product_id)} · ${esc(mech(m).label)}</p><div class="callout ${row.state_comparison_valid?'good':''}"><b>${row.state_comparison_valid?'Comparaison même voie admissible':'Comparaison inter-niveaux non conclue'}</b><p>${comparisonText} ${row.comparable_seed_count} répétitions comparables obtenues; minimum requis ${row.required_comparable_seed_count}.</p></div>`;const ss=D.supplier_stability.find(s=>s.supplier_id===row.supplier_id&&s.mechanism===m);$('supplierStatus').innerHTML=ss?`<div class="table"><table><thead><tr><th>Fournisseur</th><th>Référence</th><th>Niveau 93</th><th>Niveau 80</th><th>Lecture</th></tr></thead><tbody><tr><td>${esc(ss.supplier_id)}<br><small>${ss.same_dominant_lane?'même voie dominante':'voie dominante différente selon le niveau'}</small></td>${['op_100','op_93','op_80'].map(s=>`<td>${esc(status(ss.states[s].priority_status))}</td>`).join('')}<td>${esc(status(ss.stability_status))}</td></tr></tbody></table></div>`:''}drawSensitivity();$('laneSelect').onchange=drawSensitivity;$('mechanismSelect').onchange=drawSensitivity;
$('focusTitle').textContent=`Incident ${D.focus.item_id} : où l'effet se propage-t-il ?`;$('focusSubtitle').textContent=`${D.focus.supplier_id} → article ${D.focus.item_id} → ${D.focus.dst_node_id} → produit ${D.focus.target_product_id}. ${D.focus.display_rule}.`;$('causes').innerHTML=D.campaign.mechanisms.map(x=>`<article class="card cause"><span class="badge warn">HYPOTHÈSE CONDITIONNELLE</span><h3>${esc(x.label)}</h3><p>${esc(x.hypothesis)}</p><p>Ce scénario est testé seul; ce n'est ni un incident observé ni sa probabilité.</p></article>`).join('');$('focusRows').innerHTML=D.focus.aggregate_incident_results.sort((a,b)=>['op_100','op_93','op_80'].indexOf(a.state)-['op_100','op_93','op_80'].indexOf(b.state)||a.mechanism.localeCompare(b.mechanism)).map(r=>`<tr><td>${esc(stateLabel(r.state))}<br><small>délai planifié ${num(D.focus.planned_lead_days[r.state],1)} j</small></td><td>${esc(mech(r.mechanism).label)}</td><td>${num(r.signed_baseline_minus_incident_service_pp.mean,2)} pt</td><td>${num(r.signed_baseline_minus_incident_service_pp.p10,2)} à ${num(r.signed_baseline_minus_incident_service_pp.p90,2)} pt</td><td>${r.physically_exercised_seed_count}/30</td><td>${esc(status(r.priority_status))}</td></tr>`).join('');
const nominalKeys=[...new Set(D.nominal_curves.series.map(s=>`${s.domain}|${s.entity}|${s.metric}`))];$('nominalMetric').innerHTML=nominalKeys.map(k=>{const s=D.nominal_curves.series.find(x=>`${x.domain}|${x.entity}|${x.metric}`===k);return`<option value="${esc(k)}">${esc(s.label_fr)} · ${esc(s.entity_label_fr)} · MM${s.rolling_window_days}</option>`}).join('');function drawNominal(){const key=$('nominalMetric').value,rows=D.nominal_curves.series.filter(s=>`${s.domain}|${s.entity}|${s.metric}`===key),all=rows.flatMap(s=>s.points.flatMap(p=>[p[1],p[2],p[3]])),c=$('nominalChart'),x=c.getContext('2d'),W=c.width,H=c.height,min=Math.min(0,...all),max=Math.max(1,...all)*1.05,y=axes(x,W,H,min,max),colors={op_100:'#1969df',op_93:'#9a65c7',op_80:'#d64232'},X=(day,maxDay)=>55+day*(W-80)/maxDay;rows.forEach(s=>{const maxDay=s.points.at(-1)[0];x.fillStyle=colors[s.state]+'22';x.beginPath();s.points.forEach((p,i)=>i?x.lineTo(X(p[0],maxDay),y(p[3])):x.moveTo(X(p[0],maxDay),y(p[3])));[...s.points].reverse().forEach(p=>x.lineTo(X(p[0],maxDay),y(p[2])));x.closePath();x.fill();x.strokeStyle=colors[s.state];x.lineWidth=2;x.beginPath();s.points.forEach((p,i)=>i?x.lineTo(X(p[0],maxDay),y(p[1])):x.moveTo(X(p[0],maxDay),y(p[1])));x.stroke()});x.fillStyle='#607389';x.fillText('J0',55,H-15);x.fillText(`J${rows[0].points.at(-1)[0]}`,W-55,H-15)}drawNominal();$('nominalMetric').onchange=drawNominal;
const q=D.cascade.focus_qualification;$('cascadeScope').innerHTML=`<div class="callout ${D.focus.selected_for_detailed_replay?'good':''}"><b>${esc(q.display_label_fr)}</b><p>${q.mrp_requirement_mode==='dynamic_explicit'?'Un besoin MRP dynamique est configuré pour cette paire, mais sa réponse n’est pas tracée.':'Le besoin MRP de cette paire est statique dans ce périmètre.'} La preuve autorisée est une propagation physique tracée, pas une causalité dynamique complète stock–MRP–production–service.</p><p>${D.cascade.registry_incident_case_count} cas avec incident hypothétique sont enregistrés; seuls ${D.cascade.genealogy_available_dossier_count} dossiers disposent d'une généalogie détaillée.</p></div>`;
const stageFr=s=>({shipment_to_material_receipt:'Expédition → lot entrant',consumption_and_wip:'Consommation et encours',finished_lot_release:'Libération du lot fini',aggregated_client_contact:'Contact client agrégé'}[s]||s);function renderDetails(){const rows=D.cascade.detailed_replays;if(!rows.length){$('detailArea').innerHTML='<div class="callout"><b>Pas de généalogie V7 détaillée disponible.</b><p>Le dossier affiché conserve ses résultats agrégés; aucun ancien calcul n’est substitué.</p></div>';return}const preferred=rows.find(r=>r.dossier_id===D.focus.selected_dossier_id)||rows[0],focusHasDetail=Boolean(D.focus.selected_dossier_id);$('detailArea').innerHTML=`${focusHasDetail?'':`<div class="callout"><b>Le focus ${esc(D.focus.item_id)} n'a pas de généalogie détaillée.</b><p>Le sélecteur ci-dessous ouvre un autre dossier signé, clairement identifié; il ne constitue pas une preuve lot pour ${esc(D.focus.item_id)}.</p></div>`}<div class="controls"><select id="detailSelect">${rows.map(r=>`<option value="${esc(r.dossier_id)}" ${r===preferred?'selected':''}>${esc(r.dossier_id)} · ${esc(r.supplier_id)} · article ${esc(r.item_id)}</option>`).join('')}</select><select id="detailMetric"></select><button id="rawToggle">Voir les valeurs brutes</button></div><div id="detailIdentity"></div><div id="detailChain"></div><canvas class="chart" id="detailChart" width="1160" height="330"></canvas><div id="detailText"></div><div class="table"><table><thead><tr><th>Étape tracée</th><th>Jour / écart au J0 incident</th><th>Expédition</th><th>Lot matière</th><th>Campagne / batch / encours</th><th>Lot fini</th><th>Client agrégé</th><th>Quantité / sens du contact</th></tr></thead><tbody id="genealogy"></tbody></table></div><div class="pager"><button id="genePrev">←</button><span id="geneCount"></span><button id="geneNext">→</button></div>`;let raw=false,page=0;const PAGE=40;function chosen(){return rows.find(r=>r.dossier_id===$('detailSelect').value)}function renderChain(d){const steps=[['shipment','1 · Expédition simulée'],['material_lot','2 · Lot matière simulé'],['production','3 · Consommation / encours'],['finished_lot','4 · Lot fini simulé'],['aggregated_client','5 · Client agrégé']];$('detailChain').innerHTML=`<div class="chain">${steps.map(([key,label],i)=>`${i?'<div class="arrow">→</div>':''}<div class="step ${d.trace_availability[key]?'available':'missing'}"><b>${label}</b>${d.trace_availability[key]?'trace native disponible':'étape non prouvée dans ce dossier'}</div>`).join('')}</div><p class="small">Étapes absentes déclarées : ${d.missing_native_trace_stages.length?d.missing_native_trace_stages.map(stageFr).map(esc).join(', '):'aucune'}. Une trace de contact ne prouve pas à elle seule une causalité incrémentale complète.</p>`}function renderGenealogy(d){const start=page*PAGE,shown=d.genealogy_rows.slice(start,start+PAGE);$('genealogy').innerHTML=shown.map(g=>`<tr><td>${esc(stageFr(g.genealogy_stage))}</td><td>${g.event_day==null?'—':`J${g.event_day} (${g.days_from_incident_j0>=0?'+':''}${g.days_from_incident_j0} j vs J0)`}<br><small>${esc(g.event_day_kind||'jour non précisé')}</small></td><td>${esc(g.shipment_id||g.shipment_ids||'—')}</td><td>${esc(g.receipt_lot_id||g.material_lot_id||g.source_lot_id||'—')}</td><td>${esc(g.campaign_id||'—')} / ${esc(g.batch_id||'—')}<br><small>encours ${num(g.wip_start_qty,1)} → ${num(g.wip_end_qty,1)}</small></td><td>${esc(g.finished_lot_id||g.released_lot_id_same_day||'—')}</td><td>${esc(g.client_node_id||'—')}<br>${esc(g.client_lot_id||'')}</td><td>${(g.quantity_details||[]).map(q=>`${esc(q.label_fr)} : ${num(q.value,1)} ${esc(q.uom||'')}`).join('<br>')||'—'}<br><small>${esc(g.claim||'contact tracé')}</small></td></tr>`).join('')||'<tr><td colspan="8">Aucune ligne généalogique native pour ce dossier.</td></tr>';$('geneCount').textContent=`${d.genealogy_rows.length ? start+1 : 0}–${Math.min(start+PAGE,d.genealogy_rows.length)} sur ${d.genealogy_rows.length} lignes embarquées`;$('genePrev').disabled=page===0;$('geneNext').disabled=start+PAGE>=d.genealogy_rows.length}function redraw(){const d=chosen(),sel=$('detailMetric'),metric=d.curves.series.find(s=>s.metric===sel.value)||d.curves.series[0];if(!sel.options.length){sel.innerHTML=d.curves.series.map(s=>`<option value="${esc(s.metric)}">${esc(s.label)} · MM${s.rolling_window_days}</option>`).join('');return redraw()}const pts=raw?metric.raw:metric.smooth,clean=pts.filter(p=>p[1]!=null&&p[2]!=null),vals=clean.flatMap(p=>[p[1],p[2]]),c=$('detailChart'),x=c.getContext('2d'),W=c.width,H=c.height,min=Math.min(0,...vals),max=Math.max(1,...vals)*1.05,y=axes(x,W,H,min,max),X=day=>55+day*(W-80)/(d.curves.horizon_days-1),j0x=X(d.incident_j0_day),endx=X(d.risk_window_end_day);x.fillStyle='#ffe7e2aa';x.fillRect(j0x,25,Math.max(2,endx-j0x),H-70);x.strokeStyle='#c77a10';x.setLineDash([5,4]);x.beginPath();x.moveTo(j0x,25);x.lineTo(j0x,H-45);x.stroke();x.setLineDash([]);[['baseline','#70839a',1],['incident','#d64232',2]].forEach(([_name,color,index])=>{x.strokeStyle=color;x.lineWidth=2;x.beginPath();clean.forEach((p,i)=>i?x.lineTo(X(p[0]),y(p[index])):x.moveTo(X(p[0]),y(p[index])));x.stroke()});x.fillStyle='#607389';x.fillText(`J${d.incident_j0_day} = J0 incident`,Math.max(58,j0x-35),H-15);x.fillText(`fin fenêtre +41 j`,Math.min(W-120,endx-25),40);$('rawToggle').textContent=raw?'Revenir à la moyenne glissante':'Voir les valeurs brutes';$('detailIdentity').innerHTML=`<div class="callout good"><b>Dossier détaillé distinct : ${esc(d.dossier_id)}</b><p>${esc(d.supplier_id)} → article ${esc(d.item_id)} → ${esc(d.dst_node_id)} → produit ${esc(d.target_product_id)} · ${esc(mech(d.mechanism).label)}. J${d.incident_j0_day} est le premier jour de la fenêtre de risque de 42 jours.</p></div>`;renderChain(d);const j0=d.j0_context.map(r=>`<div class="metric"><b>${num(r.incident_value_at_incident_j0,1)} ${esc(r.unit_fr)}</b>${esc(r.label_fr)} à J0 incident<br><small>référence ${num(r.baseline_value_at_incident_j0,1)} · ${esc(r.measurement_kind_fr)}; ce n'est pas un instantané pré-incident</small></div>`).join('');$('detailText').innerHTML=`<p><span style="color:#70839a">■ sans incident</span> · <span style="color:#d64232">■ incident sans action</span> · répétition détaillée sélectionnée par le protocole (identifiant ${d.representative_seed}). Tous les écarts signés ci-dessous valent référence − incident : positif = perte, négatif = amélioration. Les lots des deux calculs ont leurs propres identifiants : aucun « même lot » n’est affirmé.</p><div class="grid metric-grid"><div class="metric"><b>${num(d.signed_baseline_minus_incident.service_pp,2)} pt</b>écart service référence − incident</div><div class="metric"><b>${num(d.signed_baseline_minus_incident.on_due_units,0)} UN</b>écart d'unités à l'heure référence − incident</div><div class="metric"><b>${num(d.signed_baseline_minus_incident.production_released_qty,0)} UN</b>écart de production libérée référence − incident</div></div><h3>Lecture exacte au J0 incident</h3><div class="grid metric-grid">${j0}</div><p class="small">Pour l'étape expédition, le jour publié est le jour de décision d'expédition; ce registre ne publie pas le jour de réception.</p>`;renderGenealogy(d)}function changeD(){page=0;const d=chosen();$('detailMetric').innerHTML=d.curves.series.map(s=>`<option value="${esc(s.metric)}">${esc(s.label)} · MM${s.rolling_window_days}</option>`).join('');redraw()}$('detailSelect').onchange=changeD;$('detailMetric').onchange=redraw;$('rawToggle').onclick=()=>{raw=!raw;redraw()};$('genePrev').onclick=()=>{page=Math.max(0,page-1);renderGenealogy(chosen())};$('geneNext').onclick=()=>{page++;renderGenealogy(chosen())};changeD()}renderDetails();
function drawActionChart(metrics){const c=$('actionChart');if(!c||!metrics.length)return;const x=c.getContext('2d'),W=c.width,H=c.height,panel=W/metrics.length,colors=['#70839a','#d64232','#0e816d'];x.clearRect(0,0,W,H);metrics.forEach((m,i)=>{const summaries=[m.baseline,m.incident_without_action,m.incident_with_action],values=summaries.flatMap(s=>[s.mean,s.p10,s.p90]).map(Number).filter(Number.isFinite),low=Math.min(0,...values),high=Math.max(1,...values),span=Math.max(1e-9,high-low),y=v=>H-62-(Number(v)-low)*(H-112)/span,left=i*panel+18,barW=Math.min(42,(panel-70)/3);x.fillStyle='#132b42';x.font='bold 13px Segoe UI';x.fillText(`${m.label} (${m.unit})`,left+6,22);x.strokeStyle='#c8d5e2';x.beginPath();x.moveTo(left+4,H-61);x.lineTo(left+panel-26,H-61);x.stroke();summaries.forEach((s,j)=>{const bx=left+35+j*(barW+28),top=y(s.mean);x.fillStyle=colors[j];x.fillRect(bx,top,barW,H-62-top);x.strokeStyle=colors[j];x.beginPath();x.moveTo(bx+barW/2,y(s.p10));x.lineTo(bx+barW/2,y(s.p90));x.moveTo(bx+barW/2-6,y(s.p10));x.lineTo(bx+barW/2+6,y(s.p10));x.moveTo(bx+barW/2-6,y(s.p90));x.lineTo(bx+barW/2+6,y(s.p90));x.stroke();x.fillStyle='#607389';x.font='11px Segoe UI';x.fillText(['normal','incident','action'][j],bx-3,H-43);x.fillText(num(s.mean,1),bx-2,Math.max(39,top-7))});if(i<metrics.length-1){x.strokeStyle='#d7e2ec';x.beginPath();x.moveTo((i+1)*panel,H-28);x.lineTo((i+1)*panel,30);x.stroke()}})}
function renderActions(){const rows=D.actions.actions;if(!rows.length){$('actionArea').innerHTML='<div class="callout"><b>Aucune action représentable pour les dossiers signés.</b><p>Aucun résultat n’est fabriqué.</p></div>';return}$('actionArea').innerHTML=`<div class="controls"><select id="actionSelect">${rows.map((a,i)=>`<option value="${i}">${esc(a.label_fr)} · ${esc(a.item_id)} · ${esc(mech(a.mechanism).label)}</option>`).join('')}</select></div><div id="actionCards"></div>`;function draw(){const a=rows[Number($('actionSelect').value)],metrics=a.metrics.filter(m=>m.available),unavailable=a.metrics.filter(m=>!m.available),params=(a.parameter_lines_fr||[]).map(esc).join('<br>')||'aucun paramètre publié',scope=(a.scope_lines_fr||[]).map(esc).join('<br>')||'périmètre non détaillé';if(!metrics.length){$('actionCards').innerHTML=`<div class="panel"><span class="badge warn">SIMULÉ · NON EXERCÉ</span><h2>${esc(a.label_fr)}</h2><p>${esc(a.supplier_id)} · ${esc(a.item_id)} · ${esc(stateLabel(a.state))}. L'action a été simulée sur ${a.paired_seed_count} scénarios aléatoires comparables, mais n'a été physiquement exercée dans aucun : aucun gain n'est estimable.</p><p><b>Paramètres imposés :</b><br>${params}<br><b>Périmètre physique :</b><br>${scope}</p><details><summary>Limite opérationnelle</summary><p>${esc(a.limits_fr)}</p></details></div>`;return}const scenario=(label,s,unit)=>`<div><span class="small">${esc(label)} · n=${s.count}</span><br><b>${num(s.mean,2)} ${esc(unit)}</b><br><span class="small">P10–P90 : ${num(s.p10,2)} à ${num(s.p90,2)}</span></div>`;$('actionCards').innerHTML=`<div class="panel"><span class="badge sim">SIMULÉ · BOUCLE OUVERTE</span><h2>${esc(a.label_fr)}</h2><p>${esc(a.supplier_id)} · article ${esc(a.item_id)} · ${esc(stateLabel(a.state))}. L'action a réellement agi dans ${a.physically_exercised_seed_count} scénarios comparables sur ${a.paired_seed_count}; les autres sont exclus du calcul des gains.</p><p><b>Paramètres imposés :</b><br>${params}<br><b>Périmètre physique :</b><br>${scope}</p><canvas class="chart" id="actionChart" width="1160" height="360"></canvas><div class="legend"><span><i class="dot" style="background:#70839a"></i>sans incident</span><span><i class="dot" style="background:#d64232"></i>incident sans action</span><span><i class="dot" style="background:#0e816d"></i>incident avec action</span><span>trait = intervalle central P10–P90</span></div><div class="grid action-grid">${metrics.map(m=>`<article class="action"><h3>${esc(m.label)}</h3>${scenario('Sans incident',m.baseline,m.unit)}${scenario('Incident sans action',m.incident_without_action,m.unit)}${scenario('Incident avec action',m.incident_with_action,m.unit)}<p>Effet signé de l'action : <b>${num(m.signed_action_effect.mean,2)} ${esc(m.unit)}</b> · n=${m.signed_action_effect.count}<br><span class="small">P10–P90 ${num(m.signed_action_effect.p10,2)} à ${num(m.signed_action_effect.p90,2)}; positif = amélioration, négatif = dégradation</span>${m.signed_reference_minus_action_gap?`<br>Écart signé à la référence après action : <b>${num(m.signed_reference_minus_action_gap.mean,2)} pt</b><br><span class="small">référence − action; positif = perte encore présente, négatif = action au-dessus de la référence</span>`:''}</p></article>`).join('')}</div>${unavailable.length?`<div class="callout">${unavailable.map(m=>esc(m.reason_fr||`${m.label} indisponible`)).join('<br>')}</div>`:''}<div class="callout"><b>Lecture sur une population exacte.</b><p>Les statistiques excluent les scénarios où l'action n'a pas été physiquement exercée. Elles ne constituent ni une probabilité de succès ni une recommandation automatique.</p></div><details><summary>Limite opérationnelle de ce levier</summary><p>${esc(a.limits_fr)}</p></details></div>`;drawActionChart(metrics)}$('actionSelect').onchange=draw;draw()}renderActions();$('refusals').innerHTML=D.actions.refusals.length?`<ul>${D.actions.refusals.map(r=>`<li><b>${esc(r.label_fr)}</b> — non simulé : ${esc(r.reason)}</li>`).join('')}</ul>`:'<p>Aucun refus supplémentaire dans les dossiers sélectionnés.</p>';
</script></body></html>"""


def render_html(payload: Mapping[str, Any]) -> str:
    return HTML_TEMPLATE.replace("__DATA__", _safe_json(payload))


def _manifest_payload(
    paths: common.Stage2Paths,
    payload: Mapping[str, Any],
    sources: Sequence[Mapping[str, Any]],
    document: str,
) -> dict[str, Any]:
    raw = document.encode("utf-8")
    unsigned = {
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "status": "complete_validated",
        "output_html": str(paths.final_html),
        "html_sha256": hashlib.sha256(raw).hexdigest(),
        "html_bytes": len(raw),
        "payload_signature": payload["payload_signature"],
        "view_count": 3,
        "standalone": True,
        "external_dependency_count": 0,
        "source_bindings": list(sources),
        "scientific_contract": {
            "validation_cases": 450,
            "campaign_rows": 3330,
            "incident_rows": 3240,
            "maximum_detailed_dossiers": 3,
            "forced_top3": False,
            "quality": False,
            "capacity_or_availability_invented": False,
            "historical_probability": False,
            "actions_open_loop": True,
            "automatic_regulation": False,
            "clients_aggregated": True,
            "cost_or_roi_claimed": False,
        },
    }
    return common.signed(unsigned, "manifest_signature")


def validate_delivery(paths: common.Stage2Paths) -> dict[str, Any]:
    paths = paths.resolved()
    manifest_path = Path(str(paths.final_html) + ".manifest.json")
    manifest = common.read_json(manifest_path)
    common.verify_signature(manifest, "manifest_signature", "manifeste HTML étape 2")
    payload, sources = collect_payload(paths)
    document = render_html(payload)
    expected = _manifest_payload(paths, payload, sources, document)
    actual = paths.final_html.read_text(encoding="utf-8")
    if (
        manifest != expected
        or actual != document
        or actual.count('class="view') != 3
        or "https://" in actual
        or "http://" in actual
        or "€" in actual
        or len(payload.get("cascade", {}).get("detailed_replays") or []) > 3
        or payload.get("limits", {}).get("automatic_regulation") is not False
        or payload.get("limits", {}).get("capacity_or_availability_modified")
        is not False
    ):
        raise Stage2DeliveryError("Le livrable autonome ne reproduit plus ses preuves")
    required_visible = (
        "aucune probabilité historique",
        "boucle ouverte",
        "aucun incident qualité",
        "aucune capacité/disponibilité modifiée",
        "clients agrégés",
        "lots simulés",
        "devise non renseignée",
    )
    folded = actual.casefold()
    if any(text not in folded for text in required_visible):
        raise Stage2DeliveryError("Une limite métier obligatoire n'est pas visible")
    return {
        "valid": True,
        "html": str(paths.final_html),
        "html_sha256": manifest["html_sha256"],
        "html_bytes": manifest["html_bytes"],
        "manifest": str(manifest_path),
        "manifest_signature": manifest["manifest_signature"],
        "view_count": 3,
        "detailed_dossier_count": len(payload["cascade"]["detailed_replays"]),
        "action_result_count": len(payload["actions"]["actions"]),
    }


def build_delivery(paths: common.Stage2Paths) -> dict[str, Any]:
    paths = paths.resolved()
    paths.validate_separation()
    manifest_path = Path(str(paths.final_html) + ".manifest.json")
    if paths.final_html.exists() and manifest_path.exists():
        return validate_delivery(paths)
    if manifest_path.exists():
        raise Stage2DeliveryError("Manifeste HTML orphelin; écrasement refusé")
    payload, sources = collect_payload(paths)
    document = render_html(payload)
    manifest = _manifest_payload(paths, payload, sources, document)
    common.publish_new_or_identical(paths.final_html, document.encode("utf-8"))
    common.publish_new_or_identical(
        manifest_path,
        (
            json.dumps(manifest, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
        ).encode("utf-8"),
    )
    return validate_delivery(paths)


def _parser() -> argparse.ArgumentParser:
    from etudecas.prototypes.scan_2027_risk_control import (
        supplier_v7_stage2_pipeline as pipeline,
    )

    parser = argparse.ArgumentParser(description=__doc__)
    pipeline.add_path_arguments(parser)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    from etudecas.prototypes.scan_2027_risk_control import (
        supplier_v7_stage2_pipeline as pipeline,
    )

    args = _parser().parse_args(argv)
    try:
        result = build_delivery(pipeline.paths_from_args(args))
    except Exception as exc:
        print(json.dumps({"status": "refused", "reason": str(exc)}, ensure_ascii=False))
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
