# shock_experiments.py
from dataclasses import dataclass
from typing import Callable, Dict, Any, List, Tuple
from copy import deepcopy
from resilience_metrics import compute_metrics, ResilienceMetrics
from shock_suite import build_shock_suite, estimate_exogenous_severity
import pandas as pd

@dataclass
class ShockResultRow:
    shock_name: str
    shock_type: str
    target: str
    exo_severity: float
    metrics: ResilienceMetrics

class ShockExperimentRunner:
    """
    Orchestrateur :
      - exécute baseline
      - génère la suite de chocs
      - lance chaque choc
      - calcule les métriques et retourne un tableau trié par score
    """
    def __init__(
        self,
        sim_func: Callable[[Dict, List], Dict],
        ts_extractor: Callable[[Dict], List[float]],
        cost_extractor: Callable[[Dict], Dict[str, float]],
        service_extractor: Callable[[Dict], float] = None,
        recovery_threshold: float = 0.95
    ):
        self.sim_func = sim_func
        self.ts_extractor = ts_extractor
        self.cost_extractor = cost_extractor
        self.service_extractor = service_extractor
        self.recovery_threshold = recovery_threshold

    def run_baseline(self, base_config: Dict) -> Dict[str, Any]:
        cfg = deepcopy(base_config); cfg.pop("events", None)
        return self.sim_func(cfg, [])

    def run_shock(self, base_config: Dict, events: List) -> Dict[str, Any]:
        cfg = deepcopy(base_config); cfg["events"] = events
        return self.sim_func(cfg, events)

    def run_suite(self, base_config: Dict, state_for_suite: Dict, start_time=20, duration_days=10, include: Dict[str, bool]=None) -> Tuple[Dict, List[ShockResultRow]]:
        # 1) baseline
        baseline_res = self.run_baseline(base_config)
        B_ts = self.ts_extractor(baseline_res)
        B_cost = self.cost_extractor(baseline_res)
        B_serv = self.service_extractor(baseline_res) if self.service_extractor else None

        # 2) suite de chocs
        suite = build_shock_suite(state_for_suite, start_time=start_time, duration_days=duration_days, include=include)
        rows: List[ShockResultRow] = []


        # 3) exécutions
        for name, evs in suite.items():
            scen_res = self.run_shock(base_config, evs)
            S_ts = self.ts_extractor(scen_res)
            S_cost = self.cost_extractor(scen_res)
            S_serv = self.service_extractor(scen_res) if self.service_extractor else None

            m = compute_metrics(B_ts, S_ts, B_cost, S_cost, B_serv, S_serv, recovery_threshold=self.recovery_threshold)
            exo = sum(estimate_exogenous_severity(state_for_suite, ev) for ev in evs)
            ev0 = evs[0]
            rows.append(ShockResultRow(name, ev0.type, str(ev0.target), exo, m))

        return baseline_res, rows

    @staticmethod
    def to_table(rows: List[ShockResultRow]) -> List[Dict[str, Any]]:
        table = []
        for r in rows:
            table.append({
                "shock_name": r.shock_name,
                "type": r.shock_type,
                "target": r.target,
                "exogenous_severity": r.exo_severity,
                "amplitude_rel": r.metrics.amplitude_rel,
                "lost_area_rel": r.metrics.lost_area_rel,
                "recovery_time": r.metrics.recovery_time,
                "cost_delta_rel": r.metrics.cost_delta_rel,
                "score": r.metrics.score
            })
        table.sort(key=lambda x: x["score"])  # du pire au meilleur
        return table
