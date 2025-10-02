# adapters.py
from typing import Dict, Any, List
import importlib
import inspect
import os

# ------------------------------------------------------------------
# 1) Option pour forcer le nom de l'allocateur (le plus simple)
#    -> mets ici le nom exact si tu le connais, ex: "run_simple_allocation_dict"
#    -> ou bien passe une variable d'env:  SCH_ALLOC=run_simple_allocation_dict
# ------------------------------------------------------------------
ALLOCATOR_NAME = "run_simple_allocation_dict"   # ← mets ici le nom EXACT de ta fonction


def _import_scenario_module():
    candidates = [
        "scenario_engine",
        "simchaingreenhorizons.scenario_engine",
        "SimChainGreenHorizons",  # fallback éventuel
    ]
    last_err = None
    for name in candidates:
        try:
            return importlib.import_module(name)
        except Exception as e:
            last_err = e
    raise ImportError(f"Impossible d'importer un module scénario parmi {candidates}: {last_err}")

def _pick_allocator(mod):
    # 0) Si l’utilisateur force un nom
    if ALLOCATOR_NAME:
        fn = getattr(mod, ALLOCATOR_NAME, None)
        if callable(fn):
            return fn

    # 1) Liste de noms usuels
    candidates = [
        "run_simple_allocation_dict",
        "run_simple_allocation",
        "run_cost_optimized_allocation",
        "run_optim_cost",
        "run_optim_co2",
        "run_multiobjective_allocation",
        "allocate",
        "allocation_func",
        "allocator",
    ]
    for name in candidates:
        fn = getattr(mod, name, None)
        if callable(fn):
            return fn

    # 2) Scan générique de toutes les callables contenant 'alloc'
    for name in dir(mod):
        if "alloc" in name.lower():
            fn = getattr(mod, name)
            if callable(fn):
                return fn

    # 3) Rien trouvé
    return None

def _call_run_scenario(run_scenario, alloc, cfg):
    """
    Essaie proprement plusieurs signatures:
    - (alloc, cfg)
    - (cfg, alloc)
    - (allocation_func=alloc, config=cfg)
    - (config=cfg, allocation_func=alloc)
    - (cfg)    [si l’allocateur est optionnel]
    - (config=cfg)
    """
    sig = inspect.signature(run_scenario)
    params = list(sig.parameters.values())
    names = [p.name for p in params]

    # si l'allocateur est probablement requis (premier param 'allocation_func'/'alloc'/'allocator')
    needs_alloc = (len(params) >= 2 and names[0].lower() in ("allocation_func","alloc","allocator"))

    attempts = []
    if alloc is not None:
        attempts.extend([
            lambda: run_scenario(alloc, cfg),
            lambda: run_scenario(cfg, alloc),
            lambda: run_scenario(allocation_func=alloc, config=cfg),
            lambda: run_scenario(config=cfg, allocation_func=alloc),
            lambda: run_scenario(alloc, config=cfg),
            lambda: run_scenario(config=cfg, alloc=alloc),
        ])
    # tenter sans alloc si non requis
    if (alloc is None) or (not needs_alloc):
        attempts.extend([
            lambda: run_scenario(cfg),
            lambda: run_scenario(config=cfg),
        ])

    last_exc = None
    for call in attempts:
        try:
            return call()
        except TypeError as e:
            last_exc = e
        except Exception as e:
            last_exc = e
    # Dernier recours: message explicite
    raise NotImplementedError(
        f"Impossible d'appeler run_scenario avec les signatures testées. "
        f"Signature détectée: run_scenario{sig}. "
        f"Conseil: précise le nom de l’allocateur (ex: ALLOCATOR_NAME='run_simple_allocation_dict' dans adapters.py "
        f"ou variable d'env SCH_ALLOC=run_simple_allocation_dict). Dernière erreur: {last_exc}"
    )

def default_sim_func(config: Dict, events: List) -> Dict[str, Any]:
    mod = _import_scenario_module()
    run_scenario = getattr(mod, "run_scenario", None)
    if not callable(run_scenario):
        raise NotImplementedError("run_scenario(...) introuvable : adapte adapters.py à ton projet.")

    alloc = _pick_allocator(mod)
    cfg = dict(config)
    cfg["events"] = events

    return _call_run_scenario(run_scenario, alloc, cfg)

# ---------------------- Extracteurs ----------------------

def default_ts_extractor(res: Dict[str, Any]) -> List[float]:
    if isinstance(res.get("production_ts_total"), list):
        return list(res["production_ts_total"])
    total: List[float] = []
    maxT = 0
    for line in res.get("all_production_data", []):
        ts = line.get("production_ts") or line.get("ts") or line.get("time_series")
        if ts:
            if len(total) < len(ts):
                total += [0.0] * (len(ts) - len(total))
            for i, v in enumerate(ts):
                total[i] += float(v)
            maxT = max(maxT, len(ts))
    if not total and maxT > 0:
        total = [0.0] * maxT
    return total

def default_cost_extractor(res: Dict[str, Any]) -> Dict[str, float]:
    c = res.get("costs")
    if isinstance(c, dict):
        return {k: float(v) for k, v in c.items()}
    return {"production": 0.0, "transport": 0.0, "penalties": 0.0, "inventory": 0.0}

def default_service_extractor(res: Dict[str, Any]) -> float:
    if "service" in res and isinstance(res["service"], dict) and "on_time" in res["service"]:
        return float(res["service"]["on_time"])
    return None
