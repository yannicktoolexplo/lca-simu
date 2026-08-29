from __future__ import annotations

import csv
from pathlib import Path

import pytest

from POC2026.supply_geo_case.supplier_alternatives import build_supplier_alternative_scenarios


REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_ROOT = REPO_ROOT / "POC2026" / "supply_geo_case" / "outputs" / "data"
SOURCE_JSON = REPO_ROOT / "supply_geo" / "analysis" / "output8_GEO_normalized_simulation_ready_researched.json"
TARGET_MASS_KG = 54.983501


def read_rows(name: str) -> list[dict[str, str]]:
    with (DATA_ROOT / name).open("r", encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


@pytest.fixture(scope="module")
def alternatives() -> dict:
    return build_supplier_alternative_scenarios(
        source_json_path=SOURCE_JSON,
        path_rows=read_rows("primary_supply_paths.csv"),
        site_rows=read_rows("primary_supply_sites.csv"),
        context_rows=read_rows("supplier_context_summary.csv"),
        target_mass_kg=TARGET_MASS_KG,
    )


def test_named_supplier_scenarios_conserve_lightweight_path_mass(alternatives: dict) -> None:
    summaries = {row["scenario_id"]: row for row in alternatives["scenario_summaries"]}
    assert set(summaries) == {"france_named_alternatives", "europe_named_alternatives"}

    for scenario_id, summary in summaries.items():
        tier_one_mass = sum(
            float(row["lightweight_path_mass_kg"])
            for row in alternatives["assignments"]
            if row["scenario_id"] == scenario_id and row["role"] == "T1"
        )
        assert tier_one_mass == pytest.approx(TARGET_MASS_KG, abs=1e-5)
        assert 0.0 < float(summary["transport_amount_factor"]) <= 1.0
        assert int(summary["named_alternative_assignment_count"]) > 0
        assert int(summary["unique_named_alternative_supplier_count"]) > 0


def test_france_scenario_uses_documented_component_specific_alternatives(alternatives: dict) -> None:
    selected = [
        row
        for row in alternatives["assignments"]
        if row["scenario_id"] == "france_named_alternatives" and row["is_named_alternative"]
    ]
    suppliers = {row["selected_supplier"] for row in selected}

    assert "Constellium" in suppliers
    assert "Groupe Segnere / SEGNERE Ade" in suppliers
    assert all(row["candidate_count_same_role"] > 0 for row in selected)
    assert all(row["qualification_status"] != "baseline_supplier" for row in selected)
    assert all(row["selected_lat"] or row["selected_lon"] for row in selected)


def test_routes_are_rebuilt_from_selected_industrial_sites(alternatives: dict) -> None:
    routes = alternatives["routes"]
    assert routes
    assert all("from_lat" in row and "to_lat" in row for row in routes)
    assert all(float(row["distance_km"]) >= 0.0 for row in routes)
    assert any(row["from_supplier"] == "Constellium" or row["to_supplier"] == "Constellium" for row in routes)
