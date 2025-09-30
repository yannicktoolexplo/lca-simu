# resilience_indicators.py
import numpy as np

def compute_resilience_indicators(baseline_curve, crisis_curve, time_vector):
    import numpy as np
    baseline = np.array(baseline_curve)
    crisis = np.array(crisis_curve)
    delta = baseline - crisis
    amplitude = np.max(delta)
    idx_amplitude = np.argmax(delta)
    recovery_time = time_vector[-1]
    for t in range(idx_amplitude, len(delta)):
        if delta[t] < 1e-6:
            recovery_time = time_vector[t]
            break
    performance_area = np.trapz(delta, time_vector)
    # Ajouts : ratios
    mean_baseline = np.mean(baseline)
    mean_crisis = np.mean(crisis)
    # Ratio production sur la période commune
    prod_ratio = float(mean_crisis / mean_baseline) if mean_baseline > 0 else 0.0
    # Amplitude relative
    rel_amplitude = float(amplitude / mean_baseline) if mean_baseline > 0 else 0.0
    # Aire normalisée (ex : par prod totale baseline)
    norm_performance_area = float(performance_area / (np.sum(baseline) if np.sum(baseline) > 0 else 1))
    return {
        "amplitude": float(amplitude),
        "recovery_time": float(recovery_time - time_vector[0]),
        "performance_area": float(performance_area),
        "prod_ratio": prod_ratio,                  # Taux de production moyen crise / baseline
        "rel_amplitude": rel_amplitude,            # Profondeur max relative à la baseline
        "norm_performance_area": norm_performance_area  # Aire triangle normalisée
    }

def resilience_on_curve(curve, time_vector=None, window=10):
    import numpy as np
    curve = np.array(curve)
    if time_vector is None:
        time_vector = np.arange(len(curve))
    # Estimation du niveau de référence: moyenne glissante hors creux
    from scipy.signal import find_peaks
    # Inverser la courbe pour détecter les creux (minima locaux)
    peaks, _ = find_peaks(-curve, distance=window)
    if len(peaks) == 0:
        return {"amplitude": 0, "recovery_time": 0, "performance_area": 0}
    # On prend le plus gros creux
    idx_min = peaks[np.argmin(curve[peaks])]
    amplitude = float(curve[:idx_min].mean() - curve[idx_min])
    # Temps pour remonter à 95% du niveau d'avant
    level_ref = curve[:idx_min].mean()
    t_recovery = None
    for t in range(idx_min, len(curve)):
        if curve[t] > 0.95 * level_ref:
            t_recovery = time_vector[t] - time_vector[idx_min]
            break
    # Aire sous le creux
    area = np.trapz(level_ref - curve[idx_min:t+1], time_vector[idx_min:t+1]) if t_recovery is not None else 0
    return {
        "amplitude": amplitude,
        "recovery_time": t_recovery if t_recovery is not None else float('nan'),
        "performance_area": area
    }
