"""Unit tests for the standalone truck consolidation contract."""

from __future__ import annotations

import csv
import json
from pathlib import Path
import tempfile
import unittest

from etudecas.simulation.logistics.consolidation import consolidate_shipments
from etudecas.simulation.logistics.engine_adapter import (
    estimate_internal_truck_handling,
)
from etudecas.simulation.logistics.io import (
    load_lane_shipments,
    write_consolidation_result,
)
from etudecas.simulation.logistics.models import (
    ConsolidationPolicy,
    ItemLogisticsProfile,
    ShipmentLine,
    TruckCapacity,
)


def _line(
    line_id: str,
    *,
    day: int = 0,
    origin: str = "A",
    destination: str = "B",
    item: str = "ITEM",
    quantity: float = 1.0,
    uom: str = "UN",
    lot_id: str = "",
) -> ShipmentLine:
    return ShipmentLine(
        line_id=line_id,
        departure_day=day,
        origin_node_id=origin,
        destination_node_id=destination,
        item_id=item,
        quantity=quantity,
        uom=uom,
        lot_id=lot_id,
    )


def _profile(
    *,
    item: str = "ITEM",
    uom: str = "UN",
    kg_per_unit: float | None = 1.0,
    pallets_per_unit: float | None = 0.01,
    volume_m3_per_unit: float | None = None,
    compatibility_group: str = "default",
) -> ItemLogisticsProfile:
    return ItemLogisticsProfile(
        item_id=item,
        uom=uom,
        kg_per_unit=kg_per_unit,
        pallets_per_unit=pallets_per_unit,
        volume_m3_per_unit=volume_m3_per_unit,
        compatibility_group=compatibility_group,
        source_reference="test_sourced_profile",
    )


class TruckConsolidationTests(unittest.TestCase):
    def test_default_capacity_matches_explicit_project_rule(self) -> None:
        capacity = TruckCapacity()

        self.assertEqual(capacity.max_pallets, 33.0)
        self.assertEqual(capacity.max_weight_kg, 23_000.0)
        self.assertIsNone(capacity.max_volume_m3)

    def test_finished_product_lot_fits_one_internal_truck_by_pallet_profile(self) -> None:
        estimate = estimate_internal_truck_handling(
            item_id="item:268967",
            quantity=107800,
            uom="UN",
            logistics_assumptions={
                "item:268967": {
                    "unitsPerCase": 125,
                    "centralCasesPerPallet": 48,
                    "truckPalletSlots": 33,
                }
            },
        )

        self.assertEqual(estimate.pallet_count, 18)
        self.assertEqual(estimate.truck_count, 1)
        self.assertEqual(estimate.handling_unit_kind, "TRUCK")
        self.assertIn("gross_weight", estimate.missing_checks)

    def test_internal_pfi_lot_fits_one_truck_by_known_net_mass(self) -> None:
        estimate = estimate_internal_truck_handling(
            item_id="item:773474",
            quantity=3_200_000,
            uom="G",
        )

        self.assertEqual(estimate.known_net_weight_kg, 3200)
        self.assertEqual(estimate.truck_count, 1)
        self.assertEqual(estimate.handling_unit_kind, "TRUCK")
        self.assertIn("pallets", estimate.missing_checks)

    def test_grams_give_known_net_weight_but_not_an_invented_truck_count(self) -> None:
        result = consolidate_shipments(
            [_line("L1", item="773474", quantity=3_200_000, uom="G", lot_id="LOT-A")]
        )

        self.assertEqual(len(result.loads), 0)
        self.assertEqual(len(result.fallback_groups), 1)
        fallback = result.fallback_groups[0]
        self.assertEqual(fallback.known_weight_kg, 3_200.0)
        self.assertEqual(fallback.known_capacity_lower_bound_trucks, 1)
        self.assertIsNone(fallback.truck_count)
        self.assertEqual(
            fallback.missing_dimensions,
            ("gross_weight_kg", "pallets"),
        )
        self.assertEqual(
            fallback.weight_bases,
            ("uom_definition:G_to_net_kg",),
        )
        self.assertEqual(fallback.quantities_by_uom, {"G": 3_200_000.0})

    def test_unknown_units_stay_in_auditable_weekly_fallback(self) -> None:
        result = consolidate_shipments(
            [
                _line("L1", quantity=60_000, lot_id="LOT-A"),
                _line("L2", day=5, quantity=47_800, lot_id="LOT-B"),
            ]
        )

        fallback = result.fallback_groups[0]
        self.assertEqual(fallback.quantities_by_uom, {"UN": 107_800.0})
        self.assertEqual(fallback.quantities_by_item_uom, {"ITEM|UN": 107_800.0})
        self.assertEqual(fallback.lot_ids, ("LOT-A", "LOT-B"))
        self.assertEqual(fallback.known_capacity_lower_bound_trucks, 0)
        self.assertEqual(
            fallback.missing_dimensions,
            ("gross_weight_kg", "pallets"),
        )
        self.assertTrue(result.audit["no_unknown_weight_invention"])

    def test_sourced_profile_enables_physical_loading(self) -> None:
        result = consolidate_shipments(
            [_line("L1", quantity=100)],
            profiles=[_profile(kg_per_unit=10.0, pallets_per_unit=0.1)],
        )

        self.assertEqual(len(result.loads), 1)
        self.assertEqual(len(result.fallback_groups), 0)
        load = result.loads[0]
        self.assertEqual(load.weight_kg, 1_000.0)
        self.assertEqual(load.pallets, 10.0)
        self.assertEqual(load.allocations[0].quantity, 100.0)
        self.assertEqual(result.audit["profile_count"], 1)
        self.assertEqual(
            result.audit["profile_source_references"],
            ["test_sourced_profile"],
        )

    def test_weight_capacity_splits_one_line_without_losing_quantity(self) -> None:
        result = consolidate_shipments(
            [_line("L1", quantity=50)],
            profiles=[_profile(kg_per_unit=1_000.0, pallets_per_unit=0.5)],
        )

        self.assertEqual(len(result.loads), 3)
        self.assertTrue(all(load.weight_kg <= 23_000.0 for load in result.loads))
        self.assertAlmostEqual(
            sum(
                allocation.quantity
                for load in result.loads
                for allocation in load.allocations
            ),
            50.0,
        )
        self.assertTrue(result.audit["conservation_ok"])

    def test_pallet_capacity_is_enforced(self) -> None:
        result = consolidate_shipments(
            [_line("L1", quantity=40)],
            profiles=[_profile(kg_per_unit=100.0, pallets_per_unit=1.0)],
        )

        self.assertEqual(len(result.loads), 2)
        self.assertTrue(all(load.pallets <= 33.0 for load in result.loads))

    def test_configured_volume_capacity_is_enforced_and_requires_volume(self) -> None:
        capacity = TruckCapacity(max_volume_m3=10.0, source_reference="test_capacity")
        loaded = consolidate_shipments(
            [_line("L1", quantity=30)],
            profiles=[
                _profile(
                    kg_per_unit=100.0,
                    pallets_per_unit=0.1,
                    volume_m3_per_unit=0.5,
                )
            ],
            capacity=capacity,
        )
        incomplete = consolidate_shipments(
            [_line("L2", quantity=30)],
            profiles=[_profile(kg_per_unit=100.0, pallets_per_unit=0.1)],
            capacity=capacity,
        )

        self.assertEqual(len(loaded.loads), 2)
        self.assertTrue(all((load.volume_m3 or 0.0) <= 10.0 for load in loaded.loads))
        self.assertEqual(incomplete.fallback_groups[0].missing_dimensions, ("volume_m3",))

    def test_profile_compatibility_and_week_separate_groups(self) -> None:
        result = consolidate_shipments(
            [
                _line("L1", day=1, item="COLD", quantity=1),
                _line("L2", day=8, item="COLD", quantity=1),
                _line("L3", day=1, item="AMBIENT", quantity=1),
            ],
            profiles=[
                _profile(item="COLD", compatibility_group="cold_chain"),
                _profile(item="AMBIENT", compatibility_group="ambient"),
            ],
        )

        self.assertEqual(len(result.loads), 3)
        self.assertEqual(
            {(load.compatibility_group, load.window_start_day) for load in result.loads},
            {("cold_chain", 0), ("cold_chain", 7), ("ambient", 0)},
        )
        self.assertEqual(len({load.load_id for load in result.loads}), 3)

    def test_profile_matches_item_with_or_without_item_prefix(self) -> None:
        result = consolidate_shipments(
            [_line("L1", item="item:773474", quantity=10, uom="G")],
            profiles=[
                _profile(
                    item="773474",
                    uom="G",
                    kg_per_unit=0.001,
                    pallets_per_unit=0.01,
                )
            ],
        )

        self.assertEqual(len(result.loads), 1)
        self.assertEqual(len(result.fallback_groups), 0)

    def test_no_mix_items_produces_unique_group_ids(self) -> None:
        result = consolidate_shipments(
            [
                _line("L1", item="A", quantity=1),
                _line("L2", item="B", quantity=1),
            ],
            policy=ConsolidationPolicy(mix_items=False),
        )

        self.assertEqual(len(result.fallback_groups), 2)
        self.assertEqual(
            len({group.group_id for group in result.fallback_groups}),
            2,
        )

    def test_profile_requires_a_source_reference(self) -> None:
        with self.assertRaises(ValueError):
            ItemLogisticsProfile(
                item_id="ITEM",
                uom="UN",
                kg_per_unit=1.0,
                source_reference="",
            )

    def test_io_resolves_route_and_writes_all_audit_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            graph_path = root / "graph.json"
            events_path = root / "events.csv"
            output_dir = root / "output"
            graph_path.write_text(
                json.dumps(
                    {
                        "edges": [
                            {
                                "id": "EDGE-A-B",
                                "from": "A",
                                "to": "B",
                                "mode": "truck",
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            with events_path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(
                    handle,
                    fieldnames=[
                        "event_id",
                        "event_type",
                        "day",
                        "departure_day",
                        "arrival_day",
                        "node_id",
                        "source_id",
                        "item_id",
                        "qty",
                        "uom",
                        "lot_id",
                        "shipment_id",
                    ],
                )
                writer.writeheader()
                writer.writerow(
                    {
                        "event_id": "E1",
                        "event_type": "lane_ship",
                        "day": 2,
                        "departure_day": 2,
                        "arrival_day": 4,
                        "node_id": "A",
                        "source_id": "EDGE-A-B",
                        "item_id": "ITEM",
                        "qty": 100,
                        "uom": "UN",
                        "lot_id": "LOT-A",
                        "shipment_id": "SHIP-A",
                    }
                )

            lines = load_lane_shipments(events_path, graph_path)
            result = consolidate_shipments(lines)
            outputs = write_consolidation_result(output_dir, result)

            self.assertEqual(lines[0].destination_node_id, "B")
            self.assertEqual(lines[0].arrival_day, 4)
            self.assertTrue(all(Path(path).exists() for path in outputs.values()))
            audit = json.loads(Path(outputs["audit"]).read_text(encoding="utf-8"))
            self.assertEqual(audit["input_line_count"], 1)
            self.assertTrue(audit["conservation_ok"])

    def test_io_rejects_event_origin_inconsistent_with_graph(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            graph_path = root / "graph.json"
            events_path = root / "events.csv"
            graph_path.write_text(
                json.dumps(
                    {"edges": [{"id": "EDGE-A-B", "from": "A", "to": "B"}]}
                ),
                encoding="utf-8",
            )
            with events_path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(
                    handle,
                    fieldnames=[
                        "event_id",
                        "event_type",
                        "day",
                        "node_id",
                        "source_id",
                        "item_id",
                        "qty",
                        "uom",
                    ],
                )
                writer.writeheader()
                writer.writerow(
                    {
                        "event_id": "E1",
                        "event_type": "lane_ship",
                        "day": 0,
                        "node_id": "WRONG",
                        "source_id": "EDGE-A-B",
                        "item_id": "ITEM",
                        "qty": 1,
                        "uom": "UN",
                    }
                )

            with self.assertRaisesRegex(ValueError, "declares origin WRONG"):
                load_lane_shipments(events_path, graph_path)


if __name__ == "__main__":
    unittest.main()
