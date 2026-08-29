from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from POC2026.supply_geo_case.adapter import build_sdd_risk_cascade_payload


def test_build_sdd_risk_cascade_payload_preserves_lineage_and_acv_attribution() -> None:
    root_event_id = "sdd:t4:month-1"
    child_event_id = "sdd:t3:month-2"
    path_id = "path:t4-to-t3"
    t4_site = "supplier-t4@@fr"
    t3_site = "supplier-t3@@de"

    sdd_results = {
        "sdd_event_ledger": [
            {
                "sdd_event_id": root_event_id,
                "parent_sdd_event_ids": "",
                "root_sdd_event_ids": root_event_id,
                "source_driver_types": "canicule",
                "source_environmental_event_ids": "env:heatwave:1",
                "source_transport_flow_uids": "",
                "event_labels": "perte_capacite",
                "decisions": "production_backup",
                "site_uid": t4_site,
                "supplier": "Fournisseur T4",
                "country_code": "FR",
                "path_id": path_id,
                "role": "T4",
                "month_index": 1,
                "service_level": 0.82,
                "backlog_end_kg": 18.0,
                "supply_regime": "crise",
                "supply_regime_label": "Crise",
            },
            {
                "sdd_event_id": child_event_id,
                "parent_sdd_event_ids": root_event_id,
                "root_sdd_event_ids": root_event_id,
                "source_driver_types": "none",
                "source_environmental_event_ids": "",
                "source_transport_flow_uids": "",
                "event_labels": "retard_amont",
                "decisions": "stock_securite",
                "site_uid": t3_site,
                "supplier": "Fournisseur T3",
                "country_code": "DE",
                "path_id": path_id,
                "role": "T3",
                "month_index": 2,
                "service_level": 0.88,
                "backlog_end_kg": 9.0,
                "supply_regime": "tendu",
                "supply_regime_label": "Tendu",
            },
        ],
        "sdd_node_state": [
            {
                "site_uid": t4_site,
                "supplier": "Fournisseur T4",
                "path_id": path_id,
                "role": "T4",
                "month_index": 1,
                "path_mass_kg": 10.0,
                "service_level": 0.82,
                "capacity_applied": 0.70,
                "disruption_index": 0.60,
                "backlog_end_kg": 18.0,
                "lead_time_multiplier": 1.40,
                "scrap_multiplier": 1.15,
                "supply_regime": "crise",
                "supply_regime_label": "Crise",
                "supply_regime_score": 0.80,
            },
            {
                "site_uid": t3_site,
                "supplier": "Fournisseur T3",
                "path_id": path_id,
                "role": "T3",
                "month_index": 2,
                "path_mass_kg": 10.0,
                "service_level": 0.88,
                "capacity_applied": 0.85,
                "disruption_index": 0.35,
                "backlog_end_kg": 9.0,
                "lead_time_multiplier": 1.20,
                "scrap_multiplier": 1.05,
                "supply_regime": "tendu",
                "supply_regime_label": "Tendu",
                "supply_regime_score": 0.55,
            },
        ],
        "sdd_lane_state": [
            {
                "path_id": path_id,
                "month_index": 2,
                "edge": "T4->T3",
                "from_site_uid": t4_site,
                "to_site_uid": t3_site,
                "from_name": "Fournisseur T4",
                "to_name": "Fournisseur T3",
                "modes": "route",
                "route_region": "Europe",
                "transport_risk_index": 0.25,
            }
        ],
    }
    sdd_brightway = {
        "inventory_delta": [
            {
                "site_uid": t3_site,
                "month_index": 2,
                "mechanism": "rebut_matiere",
                "inventory_delta_type": "matiere_additionnelle",
                "delta_kgco2e": 12.5,
            }
        ],
        "exchange_delta": [
            {
                "site_uid": t3_site,
                "month_index": 2,
                "exchange_name": "Aluminium, production primaire",
                "exchange_category": "matiere",
                "mapping_status": "mapped_brightway",
                "confidence": "forte",
                "delta_kgco2e": 12.5,
            }
        ],
    }

    payload = build_sdd_risk_cascade_payload(sdd_results, sdd_brightway)

    assert payload["schema_version"] == "poc2026.supply_geo_case.risk_cascades.v1"
    assert payload["causality_scope"] == "site_month_local_exact_parent_sdd_lineage_and_allocated_acv"
    assert payload["stats"]["total_cascade_count"] == 1
    assert payload["stats"]["displayed_cascade_count"] == 1

    cascade = payload["cascades"][0]
    assert cascade["root_sdd_event_ids"] == [root_event_id]
    assert cascade["descendant_event_count"] == 1
    assert cascade["causality_status"] == "filiation_sdd_exacte_et_acv_allouee"

    assert cascade["path_ids"] == [path_id]
    assert cascade["route_nodes"] == [
        {
            "site_uid": t4_site,
            "supplier": "Fournisseur T4",
            "role": "T4",
            "month_index": 1,
        },
        {
            "site_uid": t3_site,
            "supplier": "Fournisseur T3",
            "role": "T3",
            "month_index": 2,
        },
    ]
    assert len(cascade["route_lanes"]) == 1
    assert cascade["route_lanes"][0] == {
        "from_site_uid": t4_site,
        "to_site_uid": t3_site,
        "edge": "T4->T3",
        "from_name": "Fournisseur T4",
        "to_name": "Fournisseur T3",
        "modes": "route",
        "route_region": "Europe",
        "transport_risk_index": 0.25,
        "from_month_index": 1,
        "to_month_index": 2,
    }

    assert [step["event_id"] for step in cascade["timeline_steps"]] == [
        root_event_id,
        child_event_id,
    ]
    assert [step["month_index"] for step in cascade["timeline_steps"]] == [1, 2]
    assert cascade["timeline_steps"][0]["parent_event_ids"] == []
    assert cascade["timeline_steps"][1]["parent_event_ids"] == [root_event_id]

    assert cascade["trigger_types"] == ["canicule"]
    assert cascade["operational_event_types"] == ["perte_capacite"]
    assert cascade["decision_types"] == ["production_backup"]
    assert cascade["local_service_pct"] == pytest.approx(82.0)
    assert cascade["local_capacity_pct"] == pytest.approx(70.0)
    assert cascade["lead_time_multiplier"] == pytest.approx(1.4)
    assert cascade["scrap_multiplier"] == pytest.approx(1.15)
    assert cascade["supply_regime"] == "crise"
    assert cascade["impact_stage"] == "propagation_aval"

    assert cascade["inventory_row_count"] == 1
    assert cascade["exchange_row_count"] == 1
    assert cascade["acv_attribution_method"] == "allocation_par_racines_sdd_partagees_sur_noeud_mois"
    assert cascade["acv_delta_kgco2e"] == pytest.approx(12.5)
    assert cascade["acv_mechanism_labels"] == ["rebut_matiere"]
    assert cascade["brightway_exchange_labels"] == ["Aluminium, production primaire"]
    assert cascade["mapping_statuses"] == ["mapped_brightway"]
    assert cascade["confidence_levels"] == ["forte"]

    assert payload["stats"]["total_acv_delta_kgco2e"] == pytest.approx(12.5)
    assert payload["stats"]["source_acv_delta_kgco2e"] == pytest.approx(12.5)
    assert payload["stats"]["acv_allocation_gap_kgco2e"] == pytest.approx(0.0)
    assert payload["stats"]["acv_allocation_conserved"] is True
    assert sum(row["acv_delta_kgco2e"] for row in payload["monthly"]) == pytest.approx(12.5)


def test_converging_roots_share_acv_without_double_counting() -> None:
    root_a = "sdd:root-a"
    root_b = "sdd:root-b"
    child = "sdd:child"
    events = [
        {
            "scenario_id": "test",
            "sdd_event_id": root_a,
            "root_sdd_event_ids": root_a,
            "source_driver_types": "canicule",
            "site_uid": "site-a",
            "supplier": "A",
            "path_id": "path-a",
            "role": "T4",
            "month_index": 1,
            "service_level": 0.8,
            "supply_regime": "crise",
        },
        {
            "scenario_id": "test",
            "sdd_event_id": root_b,
            "root_sdd_event_ids": root_b,
            "source_driver_types": "tempete",
            "site_uid": "site-b",
            "supplier": "B",
            "path_id": "path-b",
            "role": "T4",
            "month_index": 1,
            "service_level": 0.8,
            "supply_regime": "crise",
        },
        {
            "scenario_id": "test",
            "sdd_event_id": child,
            "parent_sdd_event_ids": f"{root_a}|{root_b}",
            "root_sdd_event_ids": f"{root_a}|{root_b}",
            "source_driver_types": "none",
            "site_uid": "site-c",
            "supplier": "C",
            "path_id": "path-c",
            "role": "T3",
            "month_index": 2,
            "service_level": 0.9,
            "supply_regime": "tendu",
        },
    ]
    nodes = [
        {
            "scenario_id": "test",
            "site_uid": event["site_uid"],
            "supplier": event["supplier"],
            "path_id": event["path_id"],
            "role": event["role"],
            "month_index": event["month_index"],
            "path_mass_kg": 10.0,
            "service_level": event["service_level"],
            "capacity_applied": 0.8,
            "disruption_index": 0.4,
            "backlog_end_kg": 2.0,
            "lead_time_multiplier": 1.1,
            "scrap_multiplier": 1.05,
            "supply_regime": event["supply_regime"],
            "supply_regime_score": 0.6,
        }
        for event in events
    ]
    payload = build_sdd_risk_cascade_payload(
        {
            "sdd_event_ledger": events,
            "sdd_node_state": nodes,
            "sdd_lane_state": [],
        },
        {
            "inventory_delta": [],
            "exchange_delta": [
                {
                    "scenario_id": "test",
                    "site_uid": "site-c",
                    "month_index": 2,
                    "exchange_name": "Poste partage",
                    "exchange_category": "matiere",
                    "mapping_status": "virtual_exchange_proxy",
                    "delta_kgco2e": 12.0,
                }
            ],
        },
    )

    assert payload["stats"]["total_cascade_count"] == 2
    assert payload["stats"]["source_acv_delta_kgco2e"] == pytest.approx(12.0)
    assert payload["stats"]["total_acv_delta_kgco2e"] == pytest.approx(12.0)
    assert payload["stats"]["acv_allocation_gap_kgco2e"] == pytest.approx(0.0)
    assert sorted(row["acv_delta_kgco2e"] for row in payload["cascades"]) == [6.0, 6.0]
