"""Recherche bornée de seuils, un paramètre global à la fois, sur le MRP courant.

Les indicateurs manquants restent inconnus. Une variation d'entrée ne prouve
pas son activation physique, et aucun intervalle ne prouve une monotonie globale.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
import csv
from datetime import date, datetime, timedelta, timezone
import hashlib
import html
import json
import math
from pathlib import Path
import shutil
import sys
import time
import uuid
from typing import Any, Callable

from etudecas.simulation.analysis_batch_common import SUPPORTED_FACTORS, apply_scales
from etudecas.simulation.analysis.production_daily_metrics import daily_plan_metrics
from etudecas.simulation.analysis.customer_service_metrics import customer_service_metrics, customer_service_scope
from etudecas.simulation.analysis.production_replanning_metrics import (
    JOURNAL_FILENAME, LABEL as REPLANNING_LABEL, programme_metrics_from_directory,
)
from etudecas.simulation.sensibility import run_supplier_parameter_sensitivity as supplier

ROOT = Path(__file__).resolve().parents[3]
METRICS = {
    "kpi::quantity_service_rate": "Part de demande servie en quantité (rattrapages inclus)",
    "kpi::production_replanning_rate": REPLANNING_LABEL,
    "kpi::inventory_cost": "Coût du capital immobilisé valorisé (sous-total si valorisation incomplète)",
}
PARAMETER_LABELS = {
    "capacity_scale": "Capacité de fabrication", "demand_scale": "Demande client",
    "external_procurement_cost_multiplier_scale": "Coût de l'approvisionnement externe",
    "external_procurement_daily_cap_days_scale": "Capacité de l'approvisionnement externe",
    "external_procurement_lead_days_scale": "Délai de l'approvisionnement externe",
    "external_procurement_transport_cost_scale": "Transport de l'approvisionnement externe",
    "fg_target_days_scale": "Couverture cible des produits finis",
    "holding_cost_scale": "Taux du coût de stockage", "lead_time_scale": "Délais des liaisons paramétrables",
    "production_gap_gain_scale": "Rattrapage de fabrication", "production_smoothing_scale": "Lissage de fabrication",
    "production_stock_scale": "Stock libre initial en fabrication", "purchase_cost_floor_scale": "Coût minimum d'achat",
    "review_period_scale": "Période de revue MRP", "safety_stock_days_scale": "Sécurité générique du scénario",
    "supplier_capacity_scale": "Capacité des fournisseurs", "supplier_reliability_scale": "Fiabilité des liaisons",
    "supplier_stock_scale": "Stock libre initial des fournisseurs", "transport_cost_scale": "Coût de transport",
}


def finite(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def metric_values(row: dict[str, Any]) -> dict[str, float | None]:
    """No fill-rate, total-cost or zero fallback is scientifically equivalent."""
    return {key: finite(row.get(key)) for key in METRICS}


def tolerances(baseline: dict[str, Any], rate_delta: float = .001,
               cost_relative: float = .01, cost_absolute: float = 1.) -> dict[str, float]:
    if not all(math.isfinite(v) and v > 0 for v in (rate_delta, cost_relative, cost_absolute)):
        raise ValueError("Les tolérances doivent être strictement positives")
    cost = finite(baseline.get("kpi::inventory_cost"))
    return {key: max(cost_absolute, abs(cost or 0.) * cost_relative) if key.endswith("inventory_cost")
            else rate_delta for key in METRICS}


def search_thresholds(*, parameters: list[str], baseline: dict[str, Any],
        evaluate: Callable[[str, float], dict[str, Any]], effective_key: Callable[[str, float], str],
        down: tuple[float, ...] = (.5, .1, .01), up: tuple[float, ...] = (2., 5., 20.),
        max_runs: int = 115, rate_delta: float = .001, cost_relative: float = .01,
        cost_absolute: float = 1., allow_partial: bool = False,
        budget_reason: Callable[[], str | None] = lambda: None,
        on_progress: Callable[[dict[str, Any]], None] = lambda snapshot: None) -> dict[str, Any]:
    """Pure scheduler: fair breadth-first probes, separate first crossing per KPI.

    One baseline is counted. Adjacent tested points form descriptive intervals;
    they are not a monotonic root-finding claim. Plateaus are checked against
    remaining planned levels before a direction is declared saturated.
    """
    if not parameters or len(set(parameters)) != len(parameters) or set(parameters) - SUPPORTED_FACTORS:
        raise ValueError("Catalogue vide, dupliqué ou paramètre non pris en charge")
    if max_runs < 1 or not down or not up or not all(0 < x < 1 for x in down) or not all(x > 1 for x in up):
        raise ValueError("Budget ou paliers invalides")
    if list(down) != sorted(set(down), reverse=True) or list(up) != sorted(set(up)):
        raise ValueError("Les paliers doivent s'éloigner strictement du nominal")
    nominal = metric_values(baseline)
    missing = [key for key, value in nominal.items() if value is None]
    if missing and not allow_partial:
        return {"status": "blocked_missing_indicators", "missing_indicators": missing,
                "native_runs": 0, "directions": [], "trials": [], "all_three_satisfied": False}
    observed = [key for key in METRICS if nominal[key] is not None]
    if not observed:
        return {"status": "blocked_no_measurable_indicator", "missing_indicators": missing,
                "native_runs": 0, "directions": [], "trials": [], "all_three_satisfied": False}
    limits = tolerances(baseline, rate_delta, cost_relative, cost_absolute)
    directions = [{"parameter": p, "label": PARAMETER_LABELS[p], "direction": d,
                   "status": "pending", "thresholds": {}, "last_without_effect": {key: 1. for key in observed},
                   "tried_factors": [], "unavailable_trial_indicators": {},
                   "last_effective_key": effective_key(p, 1.)}
                  for p in parameters for d in ("baisse", "hausse")]
    trials = []
    runs = 1
    stopped = None
    def publish_progress():
        # A detached snapshot prevents report consumers from mutating scheduling.
        on_progress(deepcopy({"status": "running", "missing_indicators": missing,
            "native_runs": runs, "directions": directions, "trials": trials,
            "tolerances": limits, "all_three_satisfied": False}))
    publish_progress()
    for depth in range(max(len(down), len(up))):
        for state in directions:
            if state["status"] != "pending":
                continue
            levels = down if state["direction"] == "baisse" else up
            if depth >= len(levels):
                continue
            reason = budget_reason()
            if runs >= max_runs or reason:
                stopped = reason or "max_runs"
                break
            parameter, factor = state["parameter"], levels[depth]
            signature = effective_key(parameter, factor)
            if signature == state["last_effective_key"]:
                remaining = levels[depth + 1:]
                saturated = all(effective_key(parameter, future) == signature for future in remaining)
                status = "parameter_saturated" if saturated else "quantization_plateau_skipped"
                trials.append({"parameter": parameter, "direction": state["direction"], "factor": factor,
                               "status": status, "native_execution": False,
                               "runtime_activation": "not_proven", "effective_input_sha256": signature})
                if saturated:
                    state["status"] = "parameter_unchanged" if not state["tried_factors"] else "parameter_saturated"
                publish_progress()
                continue
            row = evaluate(parameter, factor)
            if row.get("status") != "ok":
                raise RuntimeError("Exécution non réussie : " + parameter + " x" + str(factor))
            runs += 1
            values = metric_values(row)
            trial = {"parameter": parameter, "direction": state["direction"], "factor": factor,
                     "status": "executed", "native_execution": True, "effective_input_sha256": signature,
                     "runtime_activation": "input_changed_physical_activation_not_proven", "case_id": row.get("case_id")}
            state["tried_factors"].append(factor)
            state["last_effective_key"] = signature
            for key in METRICS:
                trial[key] = values[key]
                if key in observed and values[key] is None:
                    state["unavailable_trial_indicators"].setdefault(key, []).append(factor)
                if key not in observed or values[key] is None or key in state["thresholds"]:
                    continue
                delta = values[key] - nominal[key]
                trial["delta::" + key] = delta
                if abs(delta) + 1e-12 >= limits[key]:
                    previous = state["last_without_effect"][key]
                    state["thresholds"][key] = {"first_tested_factor": factor,
                        "adjacent_tested_interval": sorted([previous, factor]), "baseline": nominal[key],
                        "value": values[key], "delta": delta, "tolerance": limits[key],
                        "effect_direction": "hausse" if delta > 0 else "baisse",
                        "interpretation": "franchissement observé; pas de monotonie globale démontrée"}
                else:
                    state["last_without_effect"][key] = factor
            trials.append(trial)
            if all(key in state["thresholds"] for key in observed):
                state["status"] = ("thresholds_detected_with_missing_trial_indicators" if state["unavailable_trial_indicators"]
                    else "thresholds_detected" if not missing else "thresholds_detected_measurable_only")
            publish_progress()
        if stopped:
            break
    for state in directions:
        if state["status"] == "pending":
            state["status"] = "budget_reached" if stopped else "bounds_reached_no_further_effect"
        state["all_three_satisfied"] = (not state["unavailable_trial_indicators"]
                                       and all(key in state["thresholds"] for key in METRICS))
        state["unavailable_indicators"] = missing
        state.pop("last_effective_key")
    incomplete_trials = any(state["unavailable_trial_indicators"] for state in directions)
    result = {"status": "partial_indicators" if missing or incomplete_trials else "budget_reached" if stopped else "bounded_search_finished",
            "missing_indicators": missing, "native_runs": runs, "directions": directions, "trials": trials,
            "budget_stop": stopped, "tolerances": limits,
            "all_three_satisfied": all(state["all_three_satisfied"] for state in directions)}
    on_progress(deepcopy(result))
    return result


RESUME_FIELDS = ("schema", "parameters", "days", "baseline_manifest", "input_graph", "runtime",
    "metric_definitions", "down_levels", "up_levels", "criteria", "implementation",
    "dependency_hashes", "observability_hashes", "allow_partial_indicators", "artifact_policy")


def validate_resume_report(previous: dict[str, Any], current: dict[str, Any]) -> None:
    """Only the same deterministic study can replay source-bound completed cases."""
    if previous.get("status") == "failed_stopped_without_retry":
        raise ValueError("Reprise refusée après échec : préserver les preuves et choisir un nouveau dossier")
    if previous.get("schema") != "etudecas.adaptive-sensitivity.v2":
        raise ValueError("Reprise refusée : contrat de progression ancien ou inconnu")
    if (previous.get("status") not in {"budget_reached", "bounded_search_finished", "partial_indicators"}
            or previous.get("budget_stop") not in {"max_runs", "wall_time_budget", "storage_budget", "free_disk_budget"}):
        raise ValueError("Reprise autorisée seulement après un arrêt de budget entre deux cas terminés")
    for key in RESUME_FIELDS:
        # JSON normalisation equates tuples written as lists, never numeric values.
        if json.dumps(previous.get(key), sort_keys=True) != json.dumps(current.get(key), sort_keys=True):
            raise ValueError("Reprise refusée : contrat différent pour " + key)
    if current["max_runs"] < len(previous.get("completed_native_cases", [])):
        raise ValueError("Le nouveau budget est inférieur aux calculs déjà terminés")


def effective_projection(data: dict[str, Any]) -> str:
    """Compare input carriers, excluding labels and scenario provenance only.

    This establishes mapping to inputs, never execution or causal activation.
    Source demand history/forecasts are retained: the current runtime uses them.
    """
    excluded = {"initial_source", "initial_before_scenario_scale", "initial_source_before_scenario_scale",
                "scenario_initial_quantity_status", "scenario_free_initial_stock_scale_exact_decimal"}
    def clean(value):
        if isinstance(value, dict):
            return {key: clean(child) for key, child in value.items() if key not in excluded}
        if isinstance(value, list):
            return [clean(child) for child in value]
        return value
    meta = data.get("meta") or {}
    payload = {"nodes": data.get("nodes"), "edges": data.get("edges"), "scenarios": data.get("scenarios"),
               "source_demand": {key: meta.get(key) for key in ("customer_demand_history", "mrp_forecasts")}}
    return hashlib.sha256(json.dumps(clean(payload), sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def historical_graph_copy(data: dict[str, Any], days: int) -> tuple[dict[str, Any], dict[str, Any]]:
    """Validate a retained prospective graph, then undo recognized assumptions.

    The runtime normally prepares a historical graph from the unextended bundle.
    A completed five-year run carries an extra strict prospective contract; it
    cannot be replayed at21/362days with that tag. Only deterministically
    generated assumptions are removed; physical/historical inputs and custom
    calendars or profiles are preserved. Future closures can be visible to a
    historical MRP lookahead and therefore cannot merely be left inactive.
    """
    from etudecas.simulation import current_reference as reference
    FIRST, validate_projection_contract = reference.FIRST, reference.validate_projection_contract
    if type(days) is not int or not 1 <= days <= FIRST:
        raise ValueError("La copie historique requiert un horizon entier entre1et362jours")
    meta = data.get("meta") or {}
    if not isinstance(meta, dict):
        raise ValueError("Métadonnées du graphe invalides")
    incoming = meta.get("current_reference_projection")
    if incoming is not None:
        if not isinstance(incoming, dict):
            raise ValueError("Contrat prospectif entrant invalide")
        validate_projection_contract(meta, incoming.get("days"))
    else:
        validate_projection_contract(meta, days)
    adapted = deepcopy(data)
    removed = []
    removed_closures = []
    restored = []
    reference_hashes = {}
    if incoming is not None:
        del adapted["meta"]["current_reference_projection"]
        removed.append("meta.current_reference_projection")
        config = reference.read(reference.CONFIG)
        reference_hashes[str(reference.CONFIG)] = reference.sha(reference.CONFIG)
        profile_asset = config["assets"]["other_use_profile"]
        profile_path = reference.ROOT / profile_asset["path"]
        if reference.sha(profile_path) != profile_asset["sha256"]:
            raise ValueError("Le profilW versionné ne correspond pas au contrat source")
        reference_hashes[str(profile_path)] = profile_asset["sha256"]
        generated_profile = reference.FrozenOtherUses(profile_path).payload()
        if meta.get("current_reference_other_use_profile") == generated_profile:
            graph_asset = config["assets"]["graph"]
            reference_path = reference.ROOT / graph_asset["path"]
            if reference.sha(reference_path) != graph_asset["sha256"]:
                raise ValueError("Le graphe bundle ne correspond pas au contrat source")
            reference_hashes[str(reference_path)] = graph_asset["sha256"]
            original_meta = reference.read(reference_path).get("meta") or {}
            if "current_reference_other_use_profile" in original_meta:
                adapted["meta"]["current_reference_other_use_profile"] = deepcopy(original_meta["current_reference_other_use_profile"])
                restored.append("meta.current_reference_other_use_profile_from_immutable_bundle")
            else:
                del adapted["meta"]["current_reference_other_use_profile"]
                removed.append("meta.current_reference_other_use_profile")
        rows = adapted["meta"].get("manufacturing_closures", {}).get("rows")
        if isinstance(rows, list):
            final_year = (reference.ORIGIN + timedelta(days=incoming["days"] + 364)).year
            for year in range(2026, final_year + 1):
                start = date(year, 8, 1)
                start += timedelta(days=(-start.weekday()) % 7)
                generated = {"node_id": "M-1810", "start_date": start.isoformat(),
                    "end_date": (start + timedelta(days=11)).isoformat(),
                    "provenance": "prospective assumption: first two full August workweeks; only 2025 dates confirmed"}
                # Exactly one row is appended per prospective year by prepare_graph.
                # Removing the last exact match preserves earlier source/custom rows.
                index = next((index for index in range(len(rows) - 1, -1, -1) if rows[index] == generated), None)
                if index is not None:
                    removed_closures.append(rows.pop(index))
    if validate_projection_contract(adapted.get("meta") or {}, days) is not False:
        raise ArithmeticError("La copie conserve un contrat prospectif sur l'horizon historique")
    def digest(value):
        return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()
    return adapted, {"status": "prospective_tag_removed_on_copy" if removed else "historical_input_unchanged",
        "source_contract_days": incoming.get("days") if incoming is not None else None,
        "target_historical_days": days, "removed_keys": removed, "restored_keys": restored,
        "removed_recognized_prospective_closures": removed_closures,
        "conversion_reference_hashes": reference_hashes,
        "incoming_contract_validated_before_adaptation": True,
        "historical_projection_validation": False,
        "source_semantic_graph_sha256": digest(data), "adapted_semantic_graph_sha256": digest(adapted),
        "source_projection_contract_sha256": digest(incoming) if incoming is not None else None,
        "preserved": "Physical inputs, source commitments, historical demand/forecasts and2025/source/custom calendars; only exactly recognized generated prospective assumptions are undone."}


def read_observability(nominal: Path, *, expected_scope: dict[str, Any] | None = None) -> dict[str, Any]:
    """Read actual export contracts before scheduling expensive calculations."""
    summary_path = nominal / "summaries/first_simulation_summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8-sig"))
    kpis = summary.get("kpis") or {}
    values = {"kpi::quantity_service_rate": None, "kpi::production_replanning_rate": None,
              "kpi::inventory_cost": finite(kpis.get("total_holding_cost"))}
    service = nominal / "data/production_demand_service_daily.csv"
    scope = expected_scope or {"expected_pairs": None, "uom": None, "status": "unknown_customer_service_scope"}
    service_metrics = customer_service_metrics([])
    if service.is_file():
        with service.open(encoding="utf-8-sig", newline="") as stream:
            service_rows = list(csv.DictReader(stream))
        service_metrics = customer_service_metrics(service_rows if scope.get("expected_pairs") else [],
            expected_days=summary.get("sim_days") if type(summary.get("sim_days")) is int else None,
            expected_pairs=scope.get("expected_pairs"), expected_uom=scope.get("uom"))
        if not scope.get("expected_pairs"):
            service_metrics["customer_service_semantics_status"] = "unknown_customer_service_scope"
        values["kpi::quantity_service_rate"] = finite(service_metrics.get("quantity_service_rate"))
    constraints = nominal / "data/production_constraint_daily.csv"
    semantics = "export_absent"
    if constraints.is_file():
        with constraints.open(encoding="utf-8-sig", newline="") as stream:
            planning = daily_plan_metrics(list(csv.DictReader(stream)))
        values["kpi::production_replanning_rate"] = finite(planning.get("production_replanning_rate"))
        semantics = planning.get("planning_semantics_status")
    programme_metrics = programme_metrics_from_directory(nominal)
    if programme_metrics is not None:
        values["kpi::production_replanning_rate"] = finite(programme_metrics.get("production_replanning_rate"))
        semantics = programme_metrics.get("planning_semantics_status")
    return {"values": values, "missing_indicators": [key for key, value in values.items() if value is None],
            "planning_semantics_status": semantics, "source_horizon_days": summary.get("sim_days"),
            "customer_service_diagnostics": service_metrics,
            "customer_service_scope": scope,
            "production_replanning_basis": (programme_metrics or {}).get("production_replanning_basis"),
            "production_replanning_comparable_count": (programme_metrics or {}).get("production_replanning_comparable_count"),
            "production_replanning_coverage_complete": (programme_metrics or {}).get("production_replanning_coverage_complete"),
            "production_replanning_diagnostics": (programme_metrics or {}).get("production_replanning_diagnostics"),
            "programme_journal_present": (nominal / "data" / JOURNAL_FILENAME).is_file(),
            "fresh_baseline_required": bool(values["kpi::production_replanning_rate"] is None),
            "purpose": "observabilité uniquement; ces valeurs ne sont pas le témoin du nouvel horizon",
            "economic_valuation": summary.get("economic_valuation", {"status": "unknown", "complete": False})}


def customer_service_diagnostic_text(metrics: dict[str, Any]) -> str:
    """Human reading of the same-horizon witness, preserving genuine zeros."""
    def value(name):
        return finite(metrics.get("kpi::" + name, metrics.get(name)))
    def quantity(name):
        number = value(name)
        return "inconnu" if number is None else f"{number:,.0f}".replace(",", "\u202f")
    rate = value("quantity_service_rate")
    percentage = "inconnue" if rate is None else f"{100 * rate:.2f} %".replace(".", ",")
    return ("Témoin au même horizon : part de demande servie en quantité " + percentage
        + " ; " + quantity("quantity_service_served_qty") + " unités servies / "
        + quantity("quantity_service_demand_qty") + " demandées, avec "
        + quantity("quantity_service_opening_backlog_qty") + " unités en retard au début de la fenêtre. "
        + "Retard final : " + quantity("quantity_service_ending_backlog_qty") + " unités. "
        + "Journées client/article entièrement soldées, retards inclus : "
        + quantity("fully_served_customer_item_days") + " / " + quantity("active_customer_item_days") + ".")


def write_reports(output: Path, report: dict[str, Any]) -> None:
    (output / "adaptive_summary.json").write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    table = []
    for state in report.get("directions", []):
        for metric, label in METRICS.items():
            threshold = state.get("thresholds", {}).get(metric) or {}
            table.append({"parameter": state["parameter"], "label": state["label"], "direction": state["direction"],
                "indicator": metric, "indicator_label": label,
                "status": "effet_observe" if threshold else "non_mesurable" if metric in state.get("unavailable_indicators", [])
                          else "non_mesurable_dans_certains_essais" if metric in state.get("unavailable_trial_indicators", {}) else state["status"],
                "first_factor": threshold.get("first_tested_factor"), "delta": threshold.get("delta"),
                "interval": json.dumps(threshold.get("adjacent_tested_interval")),
                "all_three_satisfied": state.get("all_three_satisfied", False)})
    for filename, rows in (("adaptive_thresholds.csv", table), ("adaptive_trials.csv", report.get("trials", []))):
        fields = sorted({key for row in rows for key in row}) or ["status"]
        with (output / filename).open("w", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=fields); writer.writeheader(); writer.writerows(rows)
    body = "".join("<tr>" + "".join("<td>" + html.escape(str(row.get(key) if row.get(key) is not None else "")) + "</td>"
        for key in ("label", "direction", "indicator_label", "status", "first_factor", "delta", "interval")) + "</tr>" for row in table)
    missing = ", ".join(METRICS[key] for key in report.get("missing_indicators", [])) or "aucun"
    states = {"blocked_missing_indicators": "Bloqué : indicateur non mesurable", "blocked_no_measurable_indicator": "Bloqué : aucun indicateur mesurable",
        "declared": "Préparé", "running": "En cours", "running_native_case": "Calcul natif en cours", "partial_indicators": "Mesures partielles : objectif des trois indicateurs non acquis",
        "bounded_search_finished": "Recherche bornée terminée", "budget_reached": "Budget atteint", "parameter_unchanged": "Entrée inchangée aux paliers testés",
        "parameter_saturated": "Borne effective atteinte", "bounds_reached_no_further_effect": "Bornes atteintes sans tous les effets recherchés",
        "thresholds_detected": "Seuils observés", "thresholds_detected_measurable_only": "Seuils des seuls indicateurs mesurables",
        "thresholds_detected_with_missing_trial_indicators": "Seuils observés avec mesures partielles", "failed_stopped_without_retry": "Échec : arrêt sans réessai",
        "pending": "À tester",
        "effet_observe": "Effet observé", "non_mesurable": "Non mesurable", "non_mesurable_dans_certains_essais": "Non mesurable dans certains essais"}
    for code, label in states.items():
        body = body.replace(">" + code + "</td>", ">" + html.escape(label) + "</td>")
    coverage = report.get("economic_valuation") or report.get("observability_preflight", {}).get("economic_valuation") or {}
    unknown_pairs = len(coverage["unknown_inventory_pairs"]) if "unknown_inventory_pairs" in coverage else "inconnu"
    criteria = report.get("criteria", {})
    design = (f"Horizon : {report.get('days')} jours. {len(report.get('parameters', []))} paramètres globaux sélectionnés sur19 disponibles ; aucune prétention de couvrir chaque fournisseur/site. "
        f"Budgets : {report.get('max_runs')} calculs, {report.get('max_wall_minutes')} minutes, {report.get('max_disk_gb')} Gio ; contrôlés entre calculs. "
        f"Seuil des taux : {criteria.get('rate_absolute_fraction')} en fraction ; stockage : {criteria.get('cost_relative_fraction')} du témoin avec minimum {criteria.get('cost_absolute_monetary')} unité monétaire.")
    baseline = (report.get("baseline_same_horizon") or {}).get("row")
    diagnostic = customer_service_diagnostic_text(baseline) if baseline else "Le témoin de cette étude au même horizon n’est pas encore calculé."
    document = '<!doctype html><html lang="fr"><meta charset="utf-8"><title>Recherche de seuils</title><style>body{font:15px/1.5 system-ui;margin:24px}table{border-collapse:collapse}td,th{border:1px solid #cbd5e1;padding:6px}td{max-width:300px}p{max-width:1100px}</style><h1>Recherche de seuils de sensibilité</h1><p>État : ' + html.escape(states.get(report["status"], report["status"])) + '</p><p>' + html.escape(design) + '</p><p>Indicateurs non mesurables : ' + html.escape(missing) + '</p><p>' + html.escape(diagnostic) + '</p><p>Valorisation du stockage : ' + html.escape(str(coverage.get("status", "inconnue"))) + '; couples article/site non valorisés : ' + str(unknown_pairs) + '. Le coût reste le sous-total connu du capital immobilisé, pas le coût complet de l’entrepôt.</p><p>Chaque facteur est modifié seul, dans les deux sens. Les intervalles relient des points testés et ne prouvent pas une monotonie globale. Une entrée modifiée ne prouve pas une activation physique. Les paramètres monétaires peuvent ne pas modifier les trois indicateurs : une recherche terminée ne signifie pas que trois effets sont démontrés.</p><p>Les trois critères sont : la part de demande servie en quantité (rattrapages inclus), le taux de révision du programme prévisionnel de fabrication simulé et le coût du capital immobilisé valorisé. La part servie ne mesure ni la ponctualité ni le stock disponible à Muret. Les journées entièrement soldées, retards inclus, restent un diagnostic secondaire ; leur zéro peut coexister avec des livraisons. La replanification requiert un journal de programmes avec identités stables, versions et cibles avant/après ; une absence n’est pas zéro. Cette étude ne fournit pas de qualification globale du modèle industriel. <a href="adaptive_summary.json">Sources, empreintes et résultats détaillés</a>.</p><table><tr><th>Paramètre</th><th>Sens</th><th>Indicateur</th><th>Résultat</th><th>Premier facteur</th><th>Écart</th><th>Intervalle testé</th></tr>' + body + '</table></html>'
    (output / "adaptive_report.html").write_text(document, encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline-manifest", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--days", type=int, default=362)
    parser.add_argument("--max-runs", type=int, default=115)
    parser.add_argument("--max-wall-minutes", type=float, default=2880)
    parser.add_argument("--max-disk-gb", type=float, default=20)
    parser.add_argument("--min-free-disk-gb", type=float, default=10)
    parser.add_argument("--parameters", default=",".join(sorted(SUPPORTED_FACTORS)))
    parser.add_argument("--down-levels", default="0.5,0.1,0.01")
    parser.add_argument("--up-levels", default="2,5,20")
    parser.add_argument("--rate-delta", type=float, default=.001)
    parser.add_argument("--cost-relative-delta", type=float, default=.01)
    parser.add_argument("--cost-absolute-delta", type=float, default=1.)
    parser.add_argument("--allow-partial-indicators", action="store_true")
    parser.add_argument("--plan-only", action="store_true")
    parser.add_argument("--resume", action="store_true", help="Rejouer uniquement les reçus terminés d'une étude de mêmes sources et même protocole")
    args = parser.parse_args(argv)
    parameters = [word.strip() for word in args.parameters.split(",") if word.strip()]
    if (not parameters or len(set(parameters)) != len(parameters) or set(parameters) - SUPPORTED_FACTORS
            or not 1 <= args.days <= 362 or args.max_runs < 1
            or not all(math.isfinite(v) and v > 0 for v in (args.max_wall_minutes, args.max_disk_gb, args.min_free_disk_gb))):
        parser.error("Paramètres, horizon historique ou budgets invalides")
    down = tuple(float(value) for value in args.down_levels.split(","))
    up = tuple(float(value) for value in args.up_levels.split(","))
    if not down or not up or any(not math.isfinite(x) or not 0 < x < 1 for x in down) or any(not math.isfinite(x) or x <= 1 for x in up):
        parser.error("Paliers invalides")
    if list(down) != sorted(set(down), reverse=True) or list(up) != sorted(set(up)):
        parser.error("Les paliers doivent s'éloigner strictement du nominal")
    tolerances({}, args.rate_delta, args.cost_relative_delta, args.cost_absolute_delta)
    manifest = args.baseline_manifest.resolve()
    source = json.loads(manifest.read_text(encoding="utf-8-sig"))
    if source.get("reference") != "coherent-MRP-20261014" or source.get("status") != "passed_execution" or source.get("returncode") != 0:
        parser.error("Un reçu d'exécution courant réussi est requis ; il ne vaut pas qualification")
    runner, graph, nominal, extra = supplier.resolve_baseline_context(manifest,
        ROOT / "etudecas/simulation/engine/run_first_simulation.py", Path(), Path())
    extra, floors = supplier.split_supplier_floor_arg(extra)
    from etudecas.toolbox.cli import code_fingerprint
    implementation = code_fingerprint()
    dependencies = [manifest, graph, *([floors] if floors is not None else [])]
    observability_files = [nominal / "summaries/first_simulation_summary.json",
        nominal / "data/production_demand_service_daily.csv", nominal / "data/production_constraint_daily.csv",
        nominal / "data" / JOURNAL_FILENAME]
    def file_hashes(paths):
        values = {}
        for path in paths:
            if not path.is_file():
                values[str(path)] = None
                continue
            with path.open("rb") as stream:
                values[str(path)] = hashlib.file_digest(stream, "sha256").hexdigest()
        return values
    dependency_hashes = file_hashes(dependencies)
    observability_hashes = file_hashes(observability_files)
    source_graph_data = json.loads(graph.read_text(encoding="utf-8-sig"))
    service_scope = customer_service_scope(source_graph_data, "scn:BASE")
    observed = read_observability(nominal, expected_scope=service_scope)
    if observability_hashes != file_hashes(observability_files):
        raise RuntimeError("Les exports ont changé pendant le diagnostic d'observabilité")
    output = (args.output_dir or ROOT / "etudecas/artifacts/testing" / ("sens_adaptive_" + uuid.uuid4().hex[:10])).resolve()
    if not output.is_relative_to((ROOT / "etudecas/artifacts/testing").resolve()):
        parser.error("Les sorties doivent rester sous etudecas/artifacts/testing")
    report = {"schema": "etudecas.adaptive-sensitivity.v2", "status": "declared", "created_utc": datetime.now(timezone.utc).isoformat(),
        "parameters": [{"key": p, "label": PARAMETER_LABELS[p]} for p in parameters],
        "parameter_scope": "19 facteurs globaux disponibles; aucune prétention de balayage de chaque site ou fournisseur",
        "days": args.days, "historical_scope": "2025 uniquement, convention du runtime sur362jours",
        "workers": 1, "max_runs": args.max_runs, "max_wall_minutes": args.max_wall_minutes,
        "max_disk_gb": args.max_disk_gb, "min_free_disk_gb": args.min_free_disk_gb,
        "baseline_manifest": str(manifest), "input_graph": str(graph), "runtime": str(runner),
        "output": str(output), "observability_preflight": observed, "missing_indicators": observed["missing_indicators"],
        "fresh_baseline_required": bool(observed["missing_indicators"]),
        "metric_definitions": METRICS, "down_levels": down, "up_levels": up,
        "allow_partial_indicators": args.allow_partial_indicators,
        "artifact_policy": "compact_engine_exports_all_retained_including_stocks_campaigns_and_lots",
        "criteria": {"rate_absolute_fraction": args.rate_delta, "cost_relative_fraction": args.cost_relative_delta,
                     "cost_absolute_monetary": args.cost_absolute_delta},
        "implementation": implementation, "implementation_sha256": hashlib.sha256(json.dumps(implementation, sort_keys=True).encode()).hexdigest(),
        "dependency_hashes": dependency_hashes, "observability_hashes": observability_hashes,
        "maximum_design_runs": 1 + len(parameters) * (len(down) + len(up)),
        "native_runs": 0, "all_three_satisfied": False, "industrial_calibration_claimed": False,
        "limits": ["Stockage: capital immobilisé valorisé, pas coût complet d'entrepôt.",
                   "Cette étude ne fournit pas de qualification globale et ne promeut pas le nominal.",
                   "Des engagements initiaux et stocks tampons peuvent absorber une perturbation.",
                   "Une absence d'effet ne prouve pas une insensibilité globale."]}
    if args.plan_only:
        report["status"] = "plan_only_no_writes_or_native_runs"
        print(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False)); return 0
    previous_report = None
    if output.exists():
        if not args.resume:
            raise FileExistsError("Choisir un dossier neuf ou --resume pour des reçus compatibles : " + str(output))
        previous_report = json.loads((output / "adaptive_summary.json").read_text(encoding="utf-8"))
    elif args.resume:
        raise FileNotFoundError("Aucune étude à reprendre : " + str(output))
    else:
        output.mkdir(parents=True)
    # Legacy exports cannot prove that the current runtime is unobservable.
    # Only one fresh same-horizon baseline is permitted before the strict
    # scheduler rechecks all three indicators and refuses any missing metric.
    def hashes():
        return file_hashes(dependencies)
    started = time.monotonic()
    previous_wall_seconds = finite((previous_report or {}).get("elapsed_wall_seconds")) or 0.
    def budget():
        if (previous_wall_seconds + time.monotonic() - started) / 60 >= args.max_wall_minutes: return "wall_time_budget"
        if shutil.disk_usage(output).free / 2**30 < args.min_free_disk_gb: return "free_disk_budget"
        if sum(p.stat().st_size for p in output.rglob("*") if p.is_file()) / 2**30 >= args.max_disk_gb: return "storage_budget"
        if (code_fingerprint() != implementation or hashes() != dependency_hashes
                or file_hashes(observability_files) != observability_hashes):
            raise RuntimeError("Sources ou entrées modifiées : arrêt sans nouveau calcul")
        return None
    base_data, horizon_adaptation = historical_graph_copy(source_graph_data, args.days)
    del source_graph_data
    report["historical_graph_adaptation"] = horizon_adaptation
    for name, expected in horizon_adaptation["conversion_reference_hashes"].items():
        path = Path(name)
        if file_hashes([path]).get(name) != expected:
            raise RuntimeError("Une source de préparation historique a changé pendant la conversion")
        if path not in dependencies:
            dependencies.append(path)
        dependency_hashes[name] = expected
    if previous_report is not None:
        validate_resume_report(previous_report, report)
        completed = previous_report.get("completed_native_cases", [])
        expected_cases = {entry["case_id"]: entry for entry in completed}
        for folder in (output / "cases").iterdir() if (output / "cases").is_dir() else ():
            if not folder.is_dir():
                continue
            entry = expected_cases.get(folder.name)
            if entry is None or not (folder / "completed_case.json").is_file():
                raise ValueError("Reprise refusée : cas partiel ou non publié, aucun réessai : " + str(folder))
            evidence = entry.get("retained_output_sha256")
            if not evidence or file_hashes([Path(p) for p in evidence]) != evidence:
                raise ValueError("Reprise refusée : CSV retenus absents ou différents : " + str(folder))
        report["completed_native_cases"] = deepcopy(completed)
        report["created_utc"] = previous_report["created_utc"]
        report["resume_count"] = int(previous_report.get("resume_count", 0)) + 1
        report["previous_status"] = previous_report.get("status")
    report["executed_cases_this_session"] = 0
    report["reused_cases_this_session"] = 0
    def save_progress(snapshot=None):
        if snapshot is not None:
            report.update(snapshot)
        report["native_runs"] = len(report.get("completed_native_cases", []))
        report["elapsed_wall_seconds"] = previous_wall_seconds + time.monotonic() - started
        report["updated_utc"] = datetime.now(timezone.utc).isoformat()
        write_reports(output, report)
    signatures = {}
    neutral = supplier.base_case()
    neutral_key = effective_projection(apply_scales(base_data, "scn:BASE", neutral["factors"]))
    def effective(parameter, factor):
        if factor == 1: return neutral_key
        key = parameter, factor
        if key not in signatures:
            config = supplier.clone_case_config(neutral); config["factors"][parameter] = factor
            signatures[key] = effective_projection(apply_scales(base_data, "scn:BASE", config["factors"]))
        return signatures[key]
    def execute(parameter, factor):
        reason = budget()
        if reason: raise RuntimeError("Budget atteint avant exécution : " + reason)
        config = supplier.clone_case_config(neutral)
        if parameter != "baseline": config["factors"][parameter] = factor
        spec = {"parameter_key": parameter, "parameter_group": "adaptive_global",
                "parameter_label": PARAMETER_LABELS.get(parameter, "Témoin recalculé au même horizon"),
                "safe_direction": "both_directions_no_monotonicity_assumed"}
        print(json.dumps({"parameter": parameter, "factor": factor, "days": args.days}), flush=True)
        case_id = supplier.case_id_for(parameter, factor)
        case_dir = output / "cases" / case_id
        was_completed = (case_dir / "completed_case.json").is_file()
        report["current_case"] = {"case_id": case_id, "parameter": parameter, "factor": factor,
                                  "execution": "verify_completed_receipt" if was_completed else "native"}
        report["status"] = "running_native_case"
        save_progress()
        row = supplier.run_case(case_id=case_id, spec=spec, level=factor,
            config=config, base_data=base_data, run_script=runner, scenario_id="scn:BASE", days=args.days,
            cases_root=output / "cases", extra_args=extra, supplier_floor_csv=floors, artifact_mode="full")
        case_summary = json.loads((Path(row["case_output_dir"]) / "summaries/first_simulation_summary.json").read_text(encoding="utf-8"))
        entry = {"case_id": row["case_id"], "parameter": parameter,
            "factor": factor, "days": args.days, "metrics": metric_values(row),
            "customer_service_diagnostics": {key: row.get("kpi::" + key) for key in
                ("product_availability", "quantity_service_rate", "quantity_service_demand_qty", "quantity_service_served_qty",
                 "quantity_service_opening_backlog_qty", "quantity_service_ending_backlog_qty", "customer_service_semantics_status")},
            "production_replanning_basis": row.get("kpi::production_replanning_basis"),
            "production_replanning_comparable_count": row.get("kpi::production_replanning_comparable_count"),
            "retained_output_sha256": file_hashes(sorted(p for p in Path(row["case_output_dir"]).glob("data/*") if p.is_file())),
            "economic_valuation": case_summary.get("economic_valuation", {"status": "unknown", "complete": False})}
        done = report.setdefault("completed_native_cases", [])
        existing = next((old for old in done if old["case_id"] == row["case_id"]), None)
        if existing is not None and existing != entry:
            raise ValueError("Le reçu terminé diffère du point de reprise : " + row["case_id"])
        if existing is None:
            done.append(entry)
        counter = "reused_cases_this_session" if was_completed else "executed_cases_this_session"
        report[counter] += 1
        report["native_runs"] = len(report["completed_native_cases"])
        report["status"] = "running"
        save_progress()
        return row
    save_progress()
    try:
        baseline = execute("baseline", 1.)
        report["baseline_same_horizon"] = {"days": args.days, "row": baseline}
        summary = json.loads((Path(baseline["case_output_dir"]) / "summaries/first_simulation_summary.json").read_text(encoding="utf-8"))
        report["economic_valuation"] = summary.get("economic_valuation", {"complete": False, "status": "unknown"})
        result = search_thresholds(parameters=parameters, baseline=baseline, evaluate=execute,
            effective_key=effective, down=down, up=up, max_runs=args.max_runs,
            rate_delta=args.rate_delta, cost_relative=args.cost_relative_delta, cost_absolute=args.cost_absolute_delta,
            allow_partial=args.allow_partial_indicators, budget_reason=budget, on_progress=save_progress)
        report.update(result)
        report["native_runs"] = len(report.get("completed_native_cases", []))
        report["sources_unchanged"] = (code_fingerprint() == implementation and hashes() == dependency_hashes
                                       and file_hashes(observability_files) == observability_hashes)
        if not report["sources_unchanged"]: raise RuntimeError("Sources changées pendant le dernier calcul")
    except PermissionError:
        raise  # Refus d'écriture: pas de nouvelle écriture ni réessai.
    except Exception as error:
        report.update(status="failed_stopped_without_retry", error=repr(error)); save_progress(); raise
    save_progress()
    print(json.dumps({"status": report["status"], "output": str(output), "native_runs": report["native_runs"],
                      "all_three_satisfied": report["all_three_satisfied"]}))
    return 0 if report["all_three_satisfied"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
