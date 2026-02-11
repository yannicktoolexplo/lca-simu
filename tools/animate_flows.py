#!/usr/bin/env python3
"""
Animation Plotly des flux (segments) par composant, à partir de :
- analysis/output8_GEO_normalized.json (fournisseurs + rôles)
- analysis/supply_arrivals.csv (pour caler l'horizon en jours)

Logique :
- On reconstruit les arêtes par composant en reliant les rôles dans l'ordre
  tier4_raw_material -> tier3_first_transformation -> tier2_second_transformation -> tier1 -> oem
- On ne garde qu'un nœud principal par rôle (is_primary=True si présent, sinon le premier)
- Pas de logistique
- Les flux apparaissent cumulativement jusqu'au jour d'arrivée max du composant.
"""

from __future__ import annotations
import json
import math
from pathlib import Path
import pandas as pd
import plotly.graph_objects as go

ROOT = Path(__file__).resolve().parent.parent
JSON_PATH = ROOT / "analysis" / "output8_GEO_normalized.json"
ARRIVALS_CSV = ROOT / "analysis" / "supply_arrivals.csv"
OUT_HTML = ROOT / "analysis" / "sim_flows.html"
WINDOW_DAYS = None  # pas de fenêtre, progression sur l'intégralité de la distance jusqu'à l'arrivée

ROLE_ORDER = [
    "tier4_raw_material",
    "tier3_first_transformation",
    "tier2_second_transformation",
    "tier1",
    "oem",
]

ROLE_COLORS = {
    "tier4_raw_material": "#7D3C98",
    "tier3_first_transformation": "#1E8449",
    "tier2_second_transformation": "#CA6F1E",
    "tier1": "#2874A6",
    "oem": "#000000",
}


def load_json():
    data = json.loads(JSON_PATH.read_text(encoding="utf-8"))
    return data.get("records", data)


def select_nodes(nodes):
    """Garde les primaires s'ils existent, sinon le premier."""
    prim = [n for n in nodes if n.get("is_primary")]
    if prim:
        return prim
    # Si aucun primaire, on limite au premier pour éviter de multiplier les arêtes
    return nodes[:1] if nodes else []


def build_edges():
    records = load_json()
    edges = []
    for rec in records:
        comp = rec.get("component", "?")
        supps = rec.get("suppliers") or []
        if not isinstance(supps, list):
            continue
        by_role = {}
        for s in supps:
            if not isinstance(s, dict):
                continue
            role = s.get("role_hint") or s.get("role")
            if role not in ROLE_ORDER:
                continue
            if s.get("lat") in (None, "", "None") or s.get("lon") in (None, "", "None"):
                continue
            by_role.setdefault(role, []).append(s)
        # sélection primaires
        by_role = {r: select_nodes(lst) for r, lst in by_role.items() if lst}
        # construit la chaîne dans l'ordre des rôles présents
        roles_present = [r for r in ROLE_ORDER if r in by_role]
        for r1, r2 in zip(roles_present, roles_present[1:]):
            for n1 in by_role[r1]:
                for n2 in by_role[r2]:
                    edges.append({
                        "component": comp,
                        "src": n1.get("name") or n1.get("supplier"),
                        "dst": n2.get("name") or n2.get("supplier"),
                        "src_lat": float(n1["lat"]),
                        "src_lon": float(n1["lon"]),
                        "dst_lat": float(n2["lat"]),
                        "dst_lon": float(n2["lon"]),
                        "role_from": r1,
                        "role_to": r2,
                    })
    return edges


def load_arrivals():
    df = pd.read_csv(ARRIVALS_CSV)
    return df.groupby("component")["arrival_day"].max().to_dict()


def build_frames(edges, arrivals, window_days: int | None = WINDOW_DAYS):
    """
    Animation progressive : pour chaque arête, on affiche une portion du segment
    en respectant l'ordre des tiers (Tier4 -> Tier3 -> Tier2 -> Tier1 -> OEM).
    Pour un composant avec n arêtes, on découpe l'horizon [0, arrival_max] en n
    segments temporels successifs ; chaque arête ne s'anime que dans sa plage.
    """
    max_arrival = math.ceil(max(arrivals.values())) if arrivals else 0
    edges_df = pd.DataFrame(edges)
    if edges_df.empty:
        return [], max_arrival
    edges_df["arrival_max"] = edges_df["component"].map(arrivals).fillna(max_arrival)

    # Attribution d'une plage temporelle séquentielle par composant
    def assign_windows(df):
        df = df.copy()
        df = df.sort_values("order_idx")
        n = len(df)
        arr = df["arrival_max"].iloc[0]
        for i, (_, row) in enumerate(df.iterrows()):
            t_start = arr * i / n
            t_end = arr * (i + 1) / n
            df.loc[row.name, "t_start"] = t_start
            df.loc[row.name, "t_end"] = t_end
        return df

    edges_df["order_idx"] = edges_df["role_from"].map({r: i for i, r in enumerate(ROLE_ORDER)})
    edges_df = edges_df.groupby("component", group_keys=False).apply(assign_windows)
    # Prépare une discrétisation du segment (squelette implicite)
    def curve_points(row, n=50):
        # arc courbe simple : on décale le midpoint perpendiculairement pour éviter la ligne droite
        x1, y1 = row.src_lon, row.src_lat
        x2, y2 = row.dst_lon, row.dst_lat
        mx, my = (x1 + x2) / 2, (y1 + y2) / 2
        dx, dy = x2 - x1, y2 - y1
        # vecteur perpendiculaire normalisé
        length = (dx ** 2 + dy ** 2) ** 0.5 or 1.0
        nx, ny = -dy / length, dx / length
        # amplitude de courbure proportionnelle à la longueur (pour rester visible)
        curvature = 0.15 * length
        cx, cy = mx + nx * curvature, my + ny * curvature

        lons, lats = [], []
        for i in range(n):
            t = i / (n - 1)
            # interpolation quadratique (Bezier) P0->C->P1
            lon = (1 - t) ** 2 * x1 + 2 * (1 - t) * t * cx + t ** 2 * x2
            lat = (1 - t) ** 2 * y1 + 2 * (1 - t) * t * cy + t ** 2 * y2
            lons.append(lon)
            lats.append(lat)
        row["lon_seq"] = lons
        row["lat_seq"] = lats
        return row

    edges_df = edges_df.apply(curve_points, axis=1)

    frames = []
    for day in range(max_arrival + 1):
        traces = []
        for _, row in edges_df.iterrows():
            t_start = row.t_start
            t_end = row.t_end
            if day < t_start:
                continue  # pas encore lancé
            if day >= t_end:
                p = 1.0
            else:
                span = t_end - t_start
                p = (day - t_start) / span if span > 0 else 1.0
            # portion visible du segment (sous-ensemble des points du squelette implicite)
            n = len(row.lon_seq)
            k = max(2, int(p*(n-1))+1)  # au moins 2 points pour tracer
            lon_seq = row.lon_seq[:k]
            lat_seq = row.lat_seq[:k]
            color = ROLE_COLORS.get(row.role_from, "#1f77b4")
            traces.append(go.Scattergeo(
                lon=lon_seq,
                lat=lat_seq,
                mode="lines",
                line=dict(color=color, width=2.5),
                opacity=0.9,
                hoverinfo="text",
                text=f"{row.component}<br>{row.src} → {row.dst}<br>{row.role_from} → {row.role_to}<br>progress: {p:.0%}",
            ))
        frames.append(go.Frame(data=traces, name=str(day)))
    return frames, max_arrival


def main():
    edges = build_edges()
    arrivals = load_arrivals()
    frames, max_day = build_frames(edges, arrivals)

    # trouve la première frame non vide
    first_idx = 0
    for i, f in enumerate(frames):
        if f.data:
            first_idx = i
            break

    initial_dynamic = list(frames[first_idx].data) if frames else []
    fig = go.Figure(
        data=initial_dynamic,
        frames=frames
    )
    fig.update_layout(
        title="Animation des flux (segments cumulés jusqu'au jour d'arrivée)",
        geo=dict(projection_type="natural earth"),
        updatemenus=[{
            "type": "buttons",
            "showactive": False,
            "buttons": [
                {"label": "▶", "method": "animate", "args": [None, {"frame": {"duration": 120, "redraw": True}, "fromcurrent": True}]},
                {"label": "⏸", "method": "animate", "args": [[None], {"frame": {"duration": 0}, "mode": "immediate"}]},
            ],
        }],
        sliders=[{
            "active": first_idx,
            "steps": [
                {"label": str(i), "method": "animate", "args": [[str(i)], {"frame": {"duration": 0, "redraw": True}, "mode": "immediate"}]}
                for i in range(max_day + 1)
            ]
        }],
        margin=dict(l=0, r=0, t=40, b=0),
    )
    fig.write_html(OUT_HTML, include_plotlyjs="cdn")
    print(f"[OK] Animation flux → {OUT_HTML} (jours 0..{max_day})")


if __name__ == "__main__":
    main()
