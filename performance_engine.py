# performance_engine.py

import numpy as np

def _safe_array(x):
    arr = np.asarray(x, dtype=float)
    if arr.ndim != 1:
        arr = arr.ravel()
    return arr

def _min_max_normalize(x, eps=1e-9):
    arr = _safe_array(x)
    xmin, xmax = np.min(arr), np.max(arr)
    if xmax - xmin < eps:
        # Courbe quasi plate -> renvoie des 0.5 (ni bon ni mauvais)
        return np.full_like(arr, 0.5, dtype=float)
    return (arr - xmin) / (xmax - xmin + eps)

def aggregate_multi_kpi(kpi_dict, weights=None):
    """
    kpi_dict : {name: array_like} (tous de même longueur)
    weights  : {name: poids} ou None (=> poids égaux)
    Retourne : (perf_raw, kpi_norm_dict)
    """
    if not kpi_dict:
        return np.array([]), {}

    # Normalise chaque KPI 0–1 (min=0, max=1)
    kpi_norm = {}
    for name, series in kpi_dict.items():
        kpi_norm[name] = _min_max_normalize(series)

    n = len(next(iter(kpi_norm.values())))
    # Pondérations
    if weights is None:
        w = {name: 1.0 for name in kpi_norm}
    else:
        w = {name: float(weights.get(name, 0.0)) for name in kpi_norm}

    weight_sum = sum(w.values()) or 1.0
    for name in w:
        w[name] /= weight_sum

    perf = np.zeros(n, dtype=float)
    for name, series in kpi_norm.items():
        perf += w[name] * series

    return perf, kpi_norm

def compute_perf_signal(kpi_dict, weights=None, window=7):
    """
    Combine plusieurs KPI normalisés + lissage glissant.
    Retourne un signal 0–1 (après renormalisation globale).
    """
    perf_raw, _ = aggregate_multi_kpi(kpi_dict, weights=weights)
    if perf_raw.size == 0:
        return np.array([])

    # Lissage glissant simple
    w = max(int(window), 1)
    if w > 1:
        kernel = np.ones(w) / w
        perf_smooth = np.convolve(perf_raw, kernel, mode="same")
    else:
        perf_smooth = perf_raw

    # Re-normalise 0–1 (utile si lissage a aplati)
    perf_final = _min_max_normalize(perf_smooth)
    return perf_final
