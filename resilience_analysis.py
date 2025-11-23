import numpy as np
import math

def _align_time_and_curves(time_vector, curves_dict):
    """
    Aligne time_vector et toutes les courbes sur la même longueur
    en tronquant tout le monde à la longueur minimale commune.
    """
    if time_vector is not None:
        t = np.asarray(time_vector)
    else:
        # Si pas de time_vector explicite, on en fabrique un à partir de la 1ère courbe
        first_curve = next(iter(curves_dict.values()))
        t = np.arange(len(first_curve))

    # Longueur minimale commune (time + toutes les courbes)
    min_len = min(len(t), *[len(np.asarray(c)) for c in curves_dict.values()])

    t = t[:min_len]
    curves_aligned = {}
    for name, c in curves_dict.items():
        c_arr = np.asarray(c)
        curves_aligned[name] = c_arr[:min_len]

    return t, curves_aligned


def compute_resilience_indicators(baseline_curve, crisis_curve, time_vector):
    """
    Calcule les indicateurs de résilience R1 à R4 à partir des courbes de performance.
    baseline_curve : array-like, courbe de référence (nominale)
    crisis_curve   : array-like, courbe perturbée
    time_vector    : array-like, vecteur de temps (pas forcément exactement la même taille au départ)
    """
    # Conversion en arrays
    baseline_curve = np.asarray(baseline_curve, dtype=float)
    crisis_curve   = np.asarray(crisis_curve, dtype=float)

    # On construit le dictionnaire des courbes pour utiliser _align_time_and_curves
    curves_dict = {
        "baseline": baseline_curve,
        "crisis": crisis_curve,
    }

    # 1) Alignement propre des longueurs (temps + courbes)
    time_vector, curves_aligned = _align_time_and_curves(time_vector, curves_dict)

    # On récupère les courbes alignées
    baseline_curve = curves_aligned["baseline"]
    crisis_curve   = curves_aligned["crisis"]

    # Debug propre
    print("[DEBUG-resilience] len(time_vector) =", len(time_vector))
    for name, curve in curves_aligned.items():
        print(f"[DEBUG-resilience] {name}: len =", len(curve))

    # Valeur moyenne de référence
    if len(baseline_curve) == 0:
        # Cas pathologique : on évite les divisions par zéro
        baseline_mean = 1e-9
    else:
        baseline_mean = float(np.mean(baseline_curve))
        if baseline_mean <= 0:
            baseline_mean = 1e-9

    # R1 - Amplitude relative (perte max normalisée)
    delta_curve = baseline_curve - crisis_curve
    rel_amplitude = float(np.max(delta_curve) / (baseline_mean + 1e-9))

    # R2 - Temps de recovery : instant où la crise retrouve 95% de la moyenne nominale
    recovery_threshold = 0.95 * baseline_mean
    below_threshold = crisis_curve < recovery_threshold

    recovery_time = np.nan
    if np.any(below_threshold):
        last_below = np.where(below_threshold)[0][-1]
        if last_below < len(time_vector) - 1:
            recovery_time = float(time_vector[last_below + 1] - time_vector[0])

    # R3 - Aire de perte de performance (et version normalisée)
    if len(time_vector) >= 2:
        performance_gap = baseline_curve - crisis_curve
        performance_area = float(np.trapz(performance_gap, time_vector))
        denom = float(np.trapz(baseline_curve, time_vector)) + 1e-9
        norm_performance_area = performance_area / denom
    else:
        performance_area = 0.0
        norm_performance_area = 0.0

    # R4 - Ratio de production moyen
    prod_ratio = float(np.mean(crisis_curve) / (baseline_mean + 1e-9))

    return {
        "rel_amplitude": rel_amplitude,
        "recovery_time": recovery_time,
        "performance_area": performance_area,
        "norm_performance_area": norm_performance_area,
        "prod_ratio": prod_ratio,
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

    def _to_float(value, default=0.0):
        try:
            value = float(value)
        except (TypeError, ValueError):
            return default
        if math.isnan(value) or math.isinf(value):
            return default
        return value

    def _loss_to_score(loss_value):
        loss = _to_float(loss_value, 0.0)
        if loss <= 0:
            return 1.0
        return 1.0 / (1.0 + loss)

    def _ratio_score(ratio_value):
        ratio = _to_float(ratio_value, 0.0)
        if ratio <= 0:
            return 0.0
        return min(ratio, 1.0)

    score = {
        "R1 Amplitude": _loss_to_score(indicators.get("rel_amplitude", 0.0)),
        "R2 Recovery": _loss_to_score(indicators.get("recovery_time", 0.0)),
        "R3 Aire": _loss_to_score(indicators.get("norm_performance_area", 0.0)),
        "R4 Ratio": _ratio_score(indicators.get("prod_ratio", 0.0)),
        "R5 ProdCumul": _ratio_score(
            (float(total_crisis) / float(total_baseline)) if total_baseline > 0 else 0.0
        ),
    }

    clean_vals = []
    for key, value in score.items():
        v = _to_float(value, 0.0)
        v = min(max(v, 0.0), 1.0)
        score[key] = v
        clean_vals.append(v)

    score["Score global"] = round(100.0 * sum(clean_vals) / len(clean_vals), 1)
    print("[DEBUG-resilience] len(time_vector)   =", len(time_vector))

    return score
