# resilience_metrics.py
from dataclasses import dataclass
from typing import List, Dict, Any, Optional, Tuple
import math

@dataclass
class ResilienceMetrics:
    # métriques temporelles (comparaison baseline B_t vs scénario S_t)
    amplitude_abs: float                 # max_t max(0, B_t - S_t)
    amplitude_rel: float                 # amplitude_abs / max_t(B_t)
    recovery_time: Optional[int]         # pas pour revenir >= seuil * B_t (None si jamais)
    lost_area_abs: float                 # sum_t max(0, B_t - S_t)
    lost_area_rel: float                 # lost_area_abs / sum_t B_t
    # business
    cost_delta_abs: float                # coût_total(scenario) - coût_total(baseline)
    cost_delta_rel: float                # / coût_total(baseline)
    service_deficit_abs: Optional[float] # ex: delta service on-time ou backorders
    service_deficit_rel: Optional[float]
    # synthèse
    score: float                         # 0..1 (1 = très résilient)

def _safe_div(a: float, b: float, eps: float = 1e-9) -> float:
    return a / b if abs(b) > eps else 0.0

def compute_amplitude_and_area(baseline: List[float], scenario: List[float]) -> Tuple[float, float, float]:
    assert len(baseline) == len(scenario), "baseline et scenario doivent avoir la même longueur"
    diffs = [max(0.0, b - s) for b, s in zip(baseline, scenario)]
    amp_abs = max(diffs) if diffs else 0.0
    max_b = max(baseline) if baseline else 0.0
    amp_rel = _safe_div(amp_abs, max_b)
    area_abs = sum(diffs)
    return amp_abs, amp_rel, area_abs

def compute_recovery_time(baseline: List[float], scenario: List[float], threshold: float = 0.95) -> Optional[int]:
    assert len(baseline) == len(scenario), "longueurs B et S différentes"
    diffs = [max(0.0, b - s) for b, s in zip(baseline, scenario)]
    if not diffs or max(diffs) <= 0:
        return 0  # pas de creux
    t_min = diffs.index(max(diffs))
    for t in range(t_min, len(scenario)):
        if scenario[t] >= threshold * baseline[t]:
            return t - t_min
    return None

def compute_total(values: Dict[str, float]) -> float:
    return sum(values.values()) if values else 0.0

def composite_score(
    amplitude_rel: float,
    lost_area_rel: float,
    recovery_time: Optional[int],
    cost_delta_rel: float,
    service_deficit_rel: Optional[float],
    weights: Dict[str, float] = None,
    recovery_cap: int = 30
) -> float:
    """
    Score 0..1, plus haut = plus résilient. Pondérations par défaut équilibrées.
    """
    w = weights or {"amplitude": 0.30, "area": 0.25, "recovery": 0.20, "cost": 0.15, "service": 0.10}
    a = max(0.0, min(1.0, amplitude_rel))
    A = max(0.0, min(1.0, lost_area_rel))
    R = 0.0 if recovery_time is None else max(0.0, min(1.0, recovery_time / recovery_cap))
    C = max(0.0, min(1.0, max(0.0, cost_delta_rel)))  # on ne pénalise pas si coût ↓
    S = 0.0 if service_deficit_rel is None else max(0.0, min(1.0, service_deficit_rel))
    penalty = w["amplitude"]*a + w["area"]*A + w["recovery"]*R + w["cost"]*C + w["service"]*S
    return max(0.0, 1.0 - penalty)

def compute_metrics(
    baseline_series: List[float],
    scenario_series: List[float],
    baseline_costs: Dict[str, float],
    scenario_costs: Dict[str, float],
    baseline_service: Optional[float] = None,
    scenario_service: Optional[float] = None,
    recovery_threshold: float = 0.95,
    weights: Dict[str, float] = None,
) -> ResilienceMetrics:
    amp_abs, amp_rel, area_abs = compute_amplitude_and_area(baseline_series, scenario_series)
    sum_b = sum(baseline_series) if baseline_series else 0.0
    area_rel = _safe_div(area_abs, sum_b)
    rec = compute_recovery_time(baseline_series, scenario_series, threshold=recovery_threshold)

    cost_b = compute_total(baseline_costs)
    cost_s = compute_total(scenario_costs)
    d_cost = cost_s - cost_b
    d_cost_rel = _safe_div(d_cost, cost_b)

    if baseline_service is not None and scenario_service is not None:
        s_def_abs = max(0.0, baseline_service - scenario_service)
        s_def_rel = _safe_div(s_def_abs, baseline_service)
    else:
        s_def_abs = None
        s_def_rel = None

    score = composite_score(amp_rel, area_rel, rec, d_cost_rel, s_def_rel, weights=weights)
    return ResilienceMetrics(amp_abs, amp_rel, rec, area_abs, area_rel, d_cost, d_cost_rel, s_def_abs, s_def_rel, score)
