from __future__ import annotations

from etudecas.prototypes.scan_2027_risk_control.incident_lot_explorer import (
    pair_finished_lots,
    render_incident_lot_html,
)


def _sequence(lot_id: str, day: int, *, constrained: bool = False) -> dict:
    return {
        "lot_id": lot_id,
        "day": day,
        "qty": 100.0,
        "uom": "UN",
        "campaign_id": f"CMP-{lot_id}",
        "operational_status": (
            "completed_after_delay" if constrained else "completed_without_delay"
        ),
        "operational_status_label": (
            "Produit après report" if constrained else "Produit sans report"
        ),
        "delay_day_count": 3 if constrained else 0,
        "binding_input_item_ids": "item:COMP" if constrained else "",
    }


def test_pair_finished_lots_separates_exposure_constraint_and_rank_shift() -> None:
    entities = [
        {
            "entity_type": "finished_product_lot",
            "item_id": "item:PF",
            "lot_id": "LOT-I",
            "incident_id": "RISK-A",
            "attributed_qty_lower": 20.0,
            "attributed_qty_upper": 35.0,
            "entity_total_qty": 100.0,
            "uom": "UN",
        },
        {
            "entity_type": "finished_product_lot",
            "item_id": "item:PF",
            "lot_id": "LOT-I",
            "incident_id": "RISK-B",
            "attributed_qty_lower": 10.0,
            "attributed_qty_upper": 25.0,
            "entity_total_qty": 100.0,
            "uom": "UN",
        },
    ]
    rows = pair_finished_lots(
        entities,
        target_item_id="item:PF",
        normal_sequence=[_sequence("LOT-N", 10)],
        incident_sequence=[_sequence("LOT-I", 15, constrained=True)],
        action_sequence=[_sequence("LOT-A", 12)],
    )

    assert len(rows) == 1
    row = rows[0]
    assert row["constrained_before_release"] is True
    assert row["delay_vs_normal_days"] == 5
    assert row["days_recovered_by_action"] == 3
    assert row["status"] == "retarde"
    assert row["exposure_qty_lower"] == 20.0
    assert row["exposure_qty_upper"] == 60.0
    assert row["normal_counterpart_lot_id"] == "LOT-N"
    assert row["action_counterpart_lot_id"] == "LOT-A"


def test_render_states_scientific_limits_and_complete_views() -> None:
    payload = {
        "schema_version": "test",
        "scope": {},
        "definitions": {},
        "scenarios": [
            {
                "id": "cascade",
                "title": "Cascade test",
                "short_title": "Cascade",
                "incident_kind": "Incident",
                "route": ["Fournisseur", "Usine", "Client"],
                "target_item_id": "item:PF",
                "target_node_id": "M-1",
                "aggregate_ten_repetitions": {},
                "run_metrics": {"incident_no_action": {}},
                "counts": {
                    "exposed_finished_lot_count": 0,
                    "constrained_finished_lot_count": 0,
                    "unique_lot_count": 0,
                    "exposure_bundle_count": 0,
                },
                "finished_lots": [],
                "incidents": [],
                "bundles": [],
                "entities": [],
                "edges": [],
                "clients": [],
            }
        ],
    }

    document = render_incident_lot_html(payload)

    assert "Lots finis : exposition et contraintes" in document
    assert "Toute la généalogie" in document
    assert "Flux et événements" in document
    assert "Clients et solutions" in document
    assert "identifiants sont des lots simulés" in document
    assert "estimation par rang de production" in document
    assert "https://" not in document

