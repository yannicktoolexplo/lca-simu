import numpy as np
import math

def compute_resilience_indicators(baseline_curve, crisis_curve, time_vector):
    """
    Calcule les indicateurs de résilience R1 à R4 à partir des courbes de performance.
    baseline_curve : array-like, courbe de référence (nominale)
    crisis_curve : array-like, courbe perturbée
    time_vector : array-like, vecteur de temps (même taille que les courbes)
    """
    baseline_curve = np.array(baseline_curve)
    crisis_curve = np.array(crisis_curve)
    time_vector = np.array(time_vector)

    # Vérification tailles
    if not (len(baseline_curve) == len(crisis_curve) == len(time_vector)):
        raise ValueError("Les courbes et le vecteur de temps doivent avoir la même taille.")

    # Valeurs moyennes nominales
    baseline_mean = np.mean(baseline_curve)

    # R1 - Amplitude relative (perte max normalisée)
    delta_curve = baseline_curve - crisis_curve
    rel_amplitude = np.max(delta_curve) / (baseline_mean + 1e-9)

    # R2 - Temps de recovery : instant où la crise retrouve 95% de la moyenne nominale
    recovery_threshold = 0.95 * baseline_mean
    below_threshold = crisis_curve < recovery_threshold

    recovery_time = np.nan
    if np.any(below_threshold):
        last_below = np.where(below_threshold)[0][-1]
        if last_below < len(time_vector) - 1:
            recovery_time = time_vector[last_below + 1] - time_vector[0]

    # R3 - Aire de perte de performance
    performance_gap = baseline_curve - crisis_curve
    performance_area = np.trapz(performance_gap, time_vector)
    norm_performance_area = performance_area / (np.trapz(baseline_curve, time_vector) + 1e-9)

    # R4 - Ratio de production moyen
    prod_ratio = np.mean(crisis_curve) / (baseline_mean + 1e-9)

    return {
        "rel_amplitude": rel_amplitude,
        "recovery_time": recovery_time,
        "performance_area": performance_area,
        "norm_performance_area": norm_performance_area,
        "prod_ratio": prod_ratio
    }


def compare_scenarios(baseline, crisis, time_vector):
    """
    Wrapper simple pour extraire les courbes depuis les résultats et comparer baseline vs crisis
    """
    baseline_curve = baseline["global_production"]
    crisis_curve = crisis["global_production"]
    return compute_resilience_indicators(baseline_curve, crisis_curve, time_vector)


def radar_indicators(baseline_curve, crisis_curve, time_vector, total_baseline, total_crisis):
    indicators = compute_resilience_indicators(baseline_curve, crisis_curve, time_vector)

    def safe_inv(x):
        # None, NaN, inf → on retourne 0 (pas de contribution positive)
        if x is None:
            return 0.0
        try:
            x = float(x)
        except (TypeError, ValueError):
            return 0.0
        if math.isnan(x) or math.isinf(x):
            return 0.0
        return 1.0 / (1.0 + x)

    score = {
        "R1 Amplitude": safe_inv(indicators["rel_amplitude"]),
        "R2 Recovery": safe_inv(indicators.get("recovery_time", 0.0)),
        "R3 Aire":      safe_inv(indicators["norm_performance_area"]),
        "R4 Ratio":     float(indicators.get("prod_ratio", 0.0) or 0.0),
        "R5 ProdCumul": (float(total_crisis) / float(total_baseline)) if total_baseline > 0 else 0.0,
    }

    # Nettoyage de sécurité au cas où
    clean_vals = []
    for v in score.values():
        try:
            v = float(v)
        except (TypeError, ValueError):
            v = 0.0
        if math.isnan(v) or math.isinf(v):
            v = 0.0
        clean_vals.append(v)

    score["Score global"] = round(100.0 * sum(clean_vals) / len(clean_vals), 1)
    return score
