#!/usr/bin/env python3
"""
Génère une animation Plotly (scattergeo) de la simulation à partir de :
- analysis/supply_events.csv (événements datés)
- analysis/output8_GEO_normalized.json (coords des fournisseurs)

Chaque frame correspond à un jour (arrondi), avec les nœuds où il se passe un événement
(START_PROC, END_PROC, ARRIVE, DEPART_*).
"""

from __future__ import annotations
import json
from pathlib import Path
import pandas as pd
import plotly.express as px

ROOT = Path(__file__).resolve().parent.parent
EVENTS_CSV = ROOT / "analysis" / "supply_events.csv"
GEO_JSON = ROOT / "analysis" / "output8_GEO_normalized.json"
OUT_HTML = ROOT / "analysis" / "sim_animation.html"

# événements retenus (sinon on garde tout)
EVENT_WHITELIST = {"START_PROC", "END_PROC", "ARRIVE", "DEPART_ROAD", "DEPART_SEA", "DEPART_AIR", "DEPART_TRAIN"}


def load_suppliers_map():
    data = json.loads(GEO_JSON.read_text(encoding="utf-8"))
    records = data.get("records", data)
    mapping = {}
    for rec in records:
        supps = rec.get("suppliers") or []
        if not isinstance(supps, list):
            continue
        for s in supps:
            if not isinstance(s, dict):
                continue
            name = s.get("name") or s.get("supplier")
            if not name:
                continue
            lat, lon = s.get("lat"), s.get("lon")
            if lat in (None, "") or lon in (None, ""):
                continue
            mapping[name] = {
                "lat": float(lat),
                "lon": float(lon),
                "role": s.get("role_hint") or s.get("role") or "",
                "location": s.get("location") or s.get("country") or "",
                "description": s.get("description") or "",
            }
    return mapping


def build_animation_df():
    mapping = load_suppliers_map()
    df = pd.read_csv(EVENTS_CSV)
    if EVENT_WHITELIST:
        df = df[df["event"].isin(EVENT_WHITELIST)].copy()

    # arrondi du jour pour limiter les frames
    df["frame_day"] = df["day"].round().astype(int)

    # map coords
    df["lat"] = df["node_or_leg"].map(lambda x: mapping.get(x, {}).get("lat"))
    df["lon"] = df["node_or_leg"].map(lambda x: mapping.get(x, {}).get("lon"))
    df["role"] = df.apply(
        lambda r: mapping.get(r["node_or_leg"], {}).get("role") or r.get("role_or_mode", ""),
        axis=1,
    )
    df["location"] = df["node_or_leg"].map(lambda x: mapping.get(x, {}).get("location", ""))
    df["description"] = df["node_or_leg"].map(lambda x: mapping.get(x, {}).get("description", ""))

    df = df.dropna(subset=["lat", "lon"])
    df = df[df["role"].str.lower() != "logistics"]  # pas de nœuds logistiques dans l'animation
    return df


def main():
    df = build_animation_df()
    if df.empty:
        raise SystemExit("Aucune donnée exploitable pour l'animation (pas de lat/lon).")

    fig = px.scatter_geo(
        df,
        lat="lat",
        lon="lon",
        color="role",
        hover_name="node_or_leg",
        hover_data={"event": True, "component": True, "role": True, "location": True, "description": True, "day": True},
        animation_frame="frame_day",
        animation_group="node_or_leg",
        size_max=12,
        opacity=0.8,
        title="Animation des événements supply (par jour arrondi)",
    )
    fig.update_geos(projection_type="natural earth")
    fig.update_layout(margin={"l":0,"r":0,"t":40,"b":0})
    fig.write_html(OUT_HTML, include_plotlyjs="cdn")
    print(f"[OK] Animation générée → {OUT_HTML}")


if __name__ == "__main__":
    main()
