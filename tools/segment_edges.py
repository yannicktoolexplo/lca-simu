#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Découpe les arêtes (component_edges_modes.csv) en segments multimodaux
selon une heuristique simple :
 - Camion seul -> un segment route sur toute la distance
 - Présence de Bateau :
     * si distance > 800 km : Camion 200 km + Bateau (dist-400) + Camion 200 km
     * sinon : land1 = 0.5*dist ; sea = 0.3*dist ; land2 = dist - land1 - sea
 - Présence d'Avion (sans Bateau) :
     * land = min(50 km, 10% de la distance)
     * Camion land + Avion (dist-2*land) + Camion land
 - Sinon (pas bateau/avion) : un segment route sur toute la distance

Entrée : analysis/component_edges_modes.csv
Sortie : analysis/component_edges_segments.csv
"""

from __future__ import annotations

import csv
from pathlib import Path

IN_PATH = Path("analysis/component_edges_modes.csv")
OUT_PATH = Path("analysis/component_edges_segments.csv")


def parse_modes(raw: str) -> list[str]:
    if not raw:
        return []
    return [m.strip().lower() for m in str(raw).split("|") if m.strip()]


def has_mode(modes: list[str], keys: list[str]) -> bool:
    return any(m in modes for m in keys)


def split_segments(distance_km: float, modes_raw: str) -> list[tuple[str, float]]:
    modes = parse_modes(modes_raw)
    has_sea = has_mode(modes, ["bateau", "sea", "mer", "ship", "boat"])
    has_air = has_mode(modes, ["avion", "air"])

    segments: list[tuple[str, float]] = []

    if has_sea:
        if distance_km > 800:
            land = 200.0
            sea = max(distance_km - 2 * land, 0.0)
            segments = [("Camion", land), ("Bateau", sea), ("Camion", land)]
        else:
            land1 = 0.5 * distance_km
            sea = 0.3 * distance_km
            land2 = max(distance_km - land1 - sea, 0.0)
            segments = [("Camion", land1), ("Bateau", sea), ("Camion", land2)]
    elif has_air:
        land = min(50.0, distance_km * 0.1)
        air = max(distance_km - 2 * land, 0.0)
        segments = [("Camion", land), ("Avion", air), ("Camion", land)]
    else:
        # corridor terrestre : on reste sur route par défaut
        segments = [("Camion", distance_km)]

    # Nettoyage : supprimer les segments de distance nulle
    segments = [(m, d) for m, d in segments if d > 0]
    return segments


def main() -> None:
    assert IN_PATH.exists(), f"Fichier introuvable : {IN_PATH}"
    rows_out = []
    with IN_PATH.open(encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            dist = float(row.get("distance_km") or 0.0)
            modes = row.get("modes", "")
            segments = split_segments(dist, modes)
            for idx, (mode, dseg) in enumerate(segments, start=1):
                rows_out.append({
                    "component": row.get("component", ""),
                    "from_name": row.get("from_name", ""),
                    "from_role": row.get("from_role", ""),
                    "from_country": row.get("from_country", ""),
                    "from_lat": row.get("from_lat", ""),
                    "from_lon": row.get("from_lon", ""),
                    "to_name": row.get("to_name", ""),
                    "to_role": row.get("to_role", ""),
                    "to_country": row.get("to_country", ""),
                    "to_lat": row.get("to_lat", ""),
                    "to_lon": row.get("to_lon", ""),
                    "orig_distance_km": row.get("distance_km", ""),
                    "orig_modes": modes,
                    "segment_index": idx,
                    "segment_mode": mode,
                    "segment_distance_km": round(dseg, 3),
                })

    with OUT_PATH.open("w", encoding="utf-8", newline="") as f:
        fieldnames = [
            "component", "from_name", "from_role", "from_country", "from_lat", "from_lon",
            "to_name", "to_role", "to_country", "to_lat", "to_lon",
            "orig_distance_km", "orig_modes",
            "segment_index", "segment_mode", "segment_distance_km"
        ]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows_out)
    print(f"✅ Segmentation générée : {OUT_PATH} ({len(rows_out)} segments)")


if __name__ == "__main__":
    main()
