"""Comparable phase scores using the historical STELIA weighting convention."""

from __future__ import annotations

import math
from typing import Any

try:
    from .lightweight_seat import INDICATOR_METHODS
except ImportError:
    from lightweight_seat import INDICATOR_METHODS


def number(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def complete_sum(values: list[float | None]) -> float | None:
    return sum(values) if values and all(value is not None for value in values) else None


def build_lca_comparison(model: dict[str, Any]) -> dict[str, Any]:
    seat = model.get("lightweight_seat") or {}
    indicators = seat.get("indicator_results") or []
    by_id = {row["indicator_id"]: row for row in indicators}
    labels = {
        "reference": "Siege de reference",
        "lightweight": "Siege allege - supply actuelle",
        "france_first": "Siege allege - France theorique",
        "europe_first": "Siege allege - Europe theorique",
        "fully_globalized": "Siege allege - mondialise",
        "france_named_alternatives": "Siege allege - fournisseurs France",
        "europe_named_alternatives": "Siege allege - fournisseurs Europe",
    }
    raw_by_scenario = {
        "reference": [(r, r.get("baseline_production_raw"), r.get("baseline_use_raw")) for r in indicators],
        "lightweight": [(r, r.get("lightweight_production_raw"), r.get("lightweight_use_central_raw")) for r in indicators],
    }
    for row in [*(seat.get("localization_indicator_results") or []), *(seat.get("named_supplier_indicator_results") or [])]:
        scenario = row.get("sourcing_scenario_id")
        if scenario not in labels:
            continue
        production = number(row.get("localized_lightweight_production_raw"))
        total = number(row.get("localized_lightweight_total_central_raw"))
        raw_by_scenario.setdefault(scenario, []).append((
            by_id.get(row.get("indicator_id"), {}),
            production,
            total - production if total is not None and production is not None else None,
        ))
    details = []
    totals = []
    for scenario, rows in raw_by_scenario.items():
        for phase in ("production", "use", "production_use"):
            phase_rows = []
            for meta, production, use in rows:
                indicator = meta.get("indicator_id")
                if indicator not in INDICATOR_METHODS:
                    continue
                production, use = number(production), number(use)
                raw = production if phase == "production" else use if phase == "use" else complete_sum([production, use])
                norm = number(meta.get("normalization_factor_per_person_year"))
                weight = number(meta.get("ef30_weight_fraction"))
                pe = raw / norm if raw is not None and norm is not None and norm > 0 else None
                score = pe * weight * 16 if pe is not None and weight is not None else None
                phase_rows.append({
                    "scenario_id": scenario, "label": labels[scenario], "phase": phase,
                    "indicator_id": indicator, "raw_value": raw, "raw_unit": meta.get("raw_unit"),
                    "normalization_factor": norm, "person_equivalent": pe,
                    "ef_weight_fraction": weight,
                    "excel_weight_multiplier": weight * 16 if weight is not None else None,
                    "weighted_score_excel": score,
                })
            complete = (len(phase_rows) == 16 and {r["indicator_id"] for r in phase_rows} == set(INDICATOR_METHODS)
                        and all(r["weighted_score_excel"] is not None for r in phase_rows)
                        and all(0 <= r['ef_weight_fraction'] <= 1 for r in phase_rows)
                        and math.isclose(sum(r["ef_weight_fraction"] for r in phase_rows), 1.0, abs_tol=1e-6))
            climate = next((r["raw_value"] for r in phase_rows if r["indicator_id"] == "Climate Change - total"), None)
            totals.append({
                "scenario_id": scenario, "label": labels[scenario], "phase": phase,
                "weighted_score_excel": sum(r["weighted_score_excel"] for r in phase_rows) if complete else None,
                "climate_kgco2e": climate, "indicator_count": len(phase_rows), "complete": complete,
                "fuel_kg": ((seat.get('mission') or {}).get('baseline_fuel_kg' if scenario == 'reference' else 'target_fuel_kg') if phase == 'use' else None),
                "direct_co2_kg": ((seat.get('mission') or {}).get('baseline_direct_co2_kg' if scenario == 'reference' else 'target_direct_co2_kg') if phase == 'use' else None),
            })
            details.extend(phase_rows)

    reference = model.get("reference_weighted_results") or []
    reference_complete = len(reference) == 16 and {r.get("short_label") for r in reference} == set(INDICATOR_METHODS)
    return {
        "schema_version": "poc2026.lca_comparison.v1", "totals": totals, "indicators": details,
        "score_unit": "score pondere STELIA / siege",
        "formula": "Somme des (impact brut / facteur de normalisation) x (16 x poids EF)",
        "weighting_source": "STELIA LCA SEATS v14022022v2.xlsx - Ponderation B2:D17; Graphes pondere B23:B40",
        "scope": ("Production et livraison + transport de la masse du siege sur 7 ans selon Steinegger A322 (2017). "
                  "A 5556 km : extrapolation non validee par l'article. Hors IFE, nettoyage, fin de vie et effets non-CO2 en altitude."
                  if seat.get('mission') else
                  "Production et livraison + utilisation sur 7 ans; hors fin de vie. Usage de reference calibre STELIA; gain marginal de masse."),
        "mission": seat.get('mission'),
        "reference_excel": {
            "total": complete_sum([number(r.get("impact_total_weighted_score")) for r in reference]) if reference_complete else None,
            "use": complete_sum([number(r.get("use_phase_weighted_score")) for r in reference]) if reference_complete else None,
            "non_use": complete_sum([number(r.get("impact_without_use_weighted_score")) for r in reference]) if reference_complete else None,
            "scope": "Cycle historique Excel, fin de vie incluse; perimetre distinct de la comparaison de masse",
        },
        "dynamic_weighted_status": "Indisponible : le surimpact SDD ne dispose pas des 16 indicateurs caracterises",
        "calculation_status": seat.get("summary", {}).get("calculation_status"),
        "provenance": {key: seat.get('summary', {}).get(key) for key in (
            'cached_result_status', 'cache_source_path', 'cache_content_sha256', 'runtime_warning')},
    }
