import unittest

from etudecas.simulation.uncertainty.paired_propagation import (
    build_paired_propagation_payload,
    build_paired_run_specs,
    default_business_factor_ranges,
    resolve_factor_range,
    select_background_rows,
    select_paired_factors,
    select_supplier_item_factors,
)


class PairedPropagationTests(unittest.TestCase):
    def test_default_business_ranges_distinguish_operational_levers(self) -> None:
        factors = [
            "supplier_capacity_node::S1",
            "supplier_stock_node::S1",
            "supplier_lead_node::S1",
            "supplier_reliability_node::S1",
            "factor::holding_cost_scale",
        ]
        ranges = default_business_factor_ranges(factors)

        self.assertEqual(ranges[factors[0]], {"low": 0.8, "center": 1.0, "high": 1.1})
        self.assertEqual(ranges[factors[1]], {"low": 0.75, "center": 1.0, "high": 1.1})
        self.assertEqual(ranges[factors[2]], {"low": 0.8, "center": 1.0, "high": 1.2})
        self.assertEqual(ranges[factors[3]], {"low": 0.9, "center": 1.0, "high": 1.05})
        self.assertEqual(ranges[factors[4]], {"low": 0.8, "center": 1.0, "high": 1.2})

    def test_selects_distinct_supplier_item_destination_scope(self) -> None:
        graph = {
            "edges": [
                {
                    "type": "transport",
                    "from": "SDC-S1",
                    "to": "M-1",
                    "items": ["item:A"],
                },
                {
                    "type": "transport",
                    "from": "SDC-S1",
                    "to": "M-1",
                    "items": ["item:B"],
                },
            ]
        }
        rows = [
            {
                "status": "ok",
                "supplier_lead_node::SDC-S1": value,
                "supplier_stock_node::SDC-S1": value,
            }
            for value in (0.8, 1.0, 1.2)
        ]
        summary = {
            "factor_kpi_correlations_pearson": {
                "supplier_lead_node::SDC-S1": {"kpi::ending_backlog": 0.8},
                "supplier_stock_node::SDC-S1": {"kpi::ending_backlog": -0.2},
            }
        }

        factors = select_supplier_item_factors(
            graph,
            summary,
            rows,
            limit=2,
        )

        self.assertEqual(
            set(factors),
            {
                "supplier_lead_pair::SDC-S1|M-1|item:A",
                "supplier_lead_pair::SDC-S1|M-1|item:B",
            },
        )

    def test_selects_diverse_supplier_factors_and_builds_triplets(self) -> None:
        rows = [
            {
                "run_id": "run_0001",
                "status": "ok",
                "is_baseline": False,
                "scenario_family": "supplier_delay",
                "supplier_lead_node::S1": 0.8,
                "supplier_stock_node::S2": 0.7,
                "factor::lead_time_scale": 1.1,
            },
            {
                "run_id": "run_0002",
                "status": "ok",
                "is_baseline": False,
                "scenario_family": "supplier_stock",
                "supplier_lead_node::S1": 1.2,
                "supplier_stock_node::S2": 1.1,
                "factor::lead_time_scale": 0.9,
            },
            {
                "run_id": "run_0003",
                "status": "ok",
                "is_baseline": False,
                "scenario_family": "combined",
                "supplier_lead_node::S1": 1.0,
                "supplier_stock_node::S2": 0.9,
                "factor::lead_time_scale": 1.0,
            },
        ]
        summary = {
            "factor_kpi_correlations_pearson": {
                "supplier_lead_node::S1": {"kpi::fill_rate": -0.8},
                "supplier_stock_node::S2": {"kpi::ending_backlog": -0.7},
                "factor::lead_time_scale": {"kpi::total_cost": 0.9},
            }
        }

        factors = select_paired_factors(summary, rows, limit=2)
        backgrounds = select_background_rows(rows, count=2)
        specs = build_paired_run_specs(factors=factors, backgrounds=backgrounds, uncertainty=0.20)

        self.assertEqual(len(factors), 2)
        self.assertEqual(len({factor.split("::", 1)[0] for factor in factors}), 2)
        self.assertEqual(len(specs), 12)
        variants = {spec["paired_metadata"]["variant"] for spec in specs}
        self.assertEqual(variants, {"low", "center", "high"})
        first_factor_specs = [spec for spec in specs if spec["paired_metadata"]["factor"] == factors[0]]
        self.assertEqual(
            {round(spec["paired_metadata"]["input_value"], 2) for spec in first_factor_specs},
            {0.8, 1.0, 1.2},
        )

    def test_builds_envelope_from_paired_effects(self) -> None:
        factor = "supplier_lead_node::S1"
        backgrounds = [
            {"run_id": "run_a", "scenario_family": "delay"},
            {"run_id": "run_b", "scenario_family": "combined"},
        ]
        trajectories = []
        values = {
            ("run_a", "low"): [80.0, 82.0],
            ("run_a", "center"): [100.0, 100.0],
            ("run_a", "high"): [110.0, 112.0],
            ("run_b", "low"): [90.0, 92.0],
            ("run_b", "center"): [100.0, 100.0],
            ("run_b", "high"): [120.0, 122.0],
        }
        for background in backgrounds:
            for variant in ("low", "center", "high"):
                trajectories.append(
                    {
                        "run_id": f"{background['run_id']}_{variant}",
                        "series": {"service_rate": list(zip([0, 1], values[(background["run_id"], variant)]))},
                        "paired_metadata": {
                            "factor": factor,
                            "background_id": background["run_id"],
                            "variant": variant,
                        },
                    }
                )

        payload = build_paired_propagation_payload(
            factors=[factor],
            backgrounds=backgrounds,
            trajectory_runs=trajectories,
            scenario_id="scn:BASE",
            uncertainty=0.20,
        )

        band = payload["metrics"]["service_rate"]["factors"][0]
        self.assertEqual(payload["method"], "paired_controlled_runs")
        self.assertEqual(payload["run_count"], 6)
        self.assertEqual(band["center"], [100.0, 100.0])
        self.assertAlmostEqual(band["low"][0], 81.0)
        self.assertAlmostEqual(band["high"][0], 119.0)
        self.assertEqual(band["background_count"], 2)

    def test_excludes_systemic_supplier_reliability_from_actionable_selection(self) -> None:
        rows = [
            {
                "run_id": f"run_{index:04d}",
                "status": "ok",
                "is_baseline": False,
                "factor::supplier_reliability_scale": value,
                "supplier_reliability_node::S1": value,
                "supplier_lead_node::S2": 1.0 + index * 0.1,
            }
            for index, value in enumerate((0.7, 0.8, 0.9), start=1)
        ]
        summary = {
            "factor_kpi_correlations_pearson": {
                "factor::supplier_reliability_scale": {"kpi::fill_rate": 0.99},
                "supplier_reliability_node::S1": {"kpi::fill_rate": 0.75},
                "supplier_lead_node::S2": {"kpi::fill_rate": -0.60},
            }
        }

        factors = select_paired_factors(summary, rows, limit=2)

        self.assertNotIn("factor::supplier_reliability_scale", factors)
        self.assertIn("supplier_reliability_node::S1", factors)

    def test_selection_covers_operational_and_economic_cost_factors(self) -> None:
        rows = [
            {
                "run_id": f"run_{index}",
                "status": "ok",
                "supplier_capacity_node::S1": capacity,
                "factor::holding_cost_scale": holding,
                "factor::transport_cost_scale": transport,
                "factor::supplier_reliability_scale": reliability,
            }
            for index, (capacity, holding, transport, reliability) in enumerate(
                ((0.6, 0.9, 1.0, 0.8), (0.8, 1.1, 1.4, 0.9), (1.0, 1.3, 1.8, 1.0)),
                start=1,
            )
        ]
        summary = {
            "factor_kpi_correlations_pearson": {
                "supplier_capacity_node::S1": {"kpi::fill_rate": 0.70},
                "factor::holding_cost_scale": {"kpi::total_cost": 0.65},
                "factor::transport_cost_scale": {"kpi::total_cost": 0.90},
                "factor::supplier_reliability_scale": {"kpi::total_cost": 1.0},
            }
        }

        factors = select_paired_factors(summary, rows, limit=2)

        self.assertIn("supplier_capacity_node::S1", factors)
        self.assertIn("factor::transport_cost_scale", factors)
        self.assertNotIn("factor::supplier_reliability_scale", factors)

    def test_uses_business_range_before_observed_values(self) -> None:
        factor = "factor::transport_cost_scale"
        backgrounds = [
            {"run_id": "a", factor: 0.9},
            {"run_id": "b", factor: 1.1},
            {"run_id": "c", factor: 1.4},
        ]

        specs = build_paired_run_specs(
            factors=[factor],
            backgrounds=backgrounds,
            uncertainty=0.20,
            factor_ranges={factor: {"low": 1.0, "center": 1.25, "high": 2.0}},
        )

        metadata = [spec["paired_metadata"] for spec in specs]
        self.assertEqual({meta["input_value"] for meta in metadata}, {1.0, 1.25, 2.0})
        self.assertEqual({meta["input_range_source"] for meta in metadata}, {"business_config"})
        self.assertEqual({meta["input_reference"] for meta in metadata}, {1.25})

    def test_resolves_observed_factor_specific_quantiles(self) -> None:
        factor = "supplier_lead_node::S1"
        rows = [{factor: value, "status": "ok"} for value in (0.5, 0.8, 1.0, 1.4, 2.0)]

        resolved = resolve_factor_range(factor, rows, uncertainty=0.20)

        self.assertEqual(resolved["source"], "observed_p05_p50_p95")
        self.assertAlmostEqual(resolved["low"], 0.56)
        self.assertAlmostEqual(resolved["center"], 1.0)
        self.assertAlmostEqual(resolved["high"], 1.88)

    def test_keeps_relative_fallback_for_legacy_calls(self) -> None:
        factor = "supplier_stock_node::S1"
        backgrounds = [{"run_id": "a", factor: 1.0}, {"run_id": "b", factor: 1.0}]

        specs = build_paired_run_specs(
            factors=[factor],
            backgrounds=backgrounds,
            uncertainty=0.20,
        )

        self.assertEqual(
            {round(spec["paired_metadata"]["input_value"], 2) for spec in specs},
            {0.8, 1.0, 1.2},
        )
        self.assertEqual(
            {spec["paired_metadata"]["input_range_source"] for spec in specs},
            {"uniform_relative_fallback"},
        )

    def test_payload_reports_actual_factor_range(self) -> None:
        factor = "factor::holding_cost_scale"
        backgrounds = [{"run_id": "run_a", "scenario_family": "cost"}]
        trajectories = []
        for variant, input_value, values in (
            ("low", 0.9, [90.0, 95.0]),
            ("center", 1.1, [100.0, 105.0]),
            ("high", 1.6, [130.0, 140.0]),
        ):
            trajectories.append(
                {
                    "series": {"total_cost": list(zip([0, 1], values))},
                    "paired_metadata": {
                        "factor": factor,
                        "background_id": "run_a",
                        "variant": variant,
                        "input_value": input_value,
                        "input_low": 0.9,
                        "input_reference": 1.1,
                        "input_high": 1.6,
                        "input_range_source": "business_config",
                    },
                }
            )

        payload = build_paired_propagation_payload(
            factors=[factor],
            backgrounds=backgrounds,
            trajectory_runs=trajectories,
            scenario_id="scn:BASE",
            uncertainty=0.20,
        )

        band = payload["metrics"]["total_cost"]["factors"][0]
        self.assertEqual(band["input_low"], 0.9)
        self.assertEqual(band["input_reference"], 1.1)
        self.assertEqual(band["input_high"], 1.6)
        self.assertEqual(band["input_range_source"], "business_config")

    def test_reuses_one_center_per_background_across_factors(self) -> None:
        factors = ["supplier_lead_node::S1", "factor::holding_cost_scale"]
        backgrounds = [
            {"run_id": "run_a", factors[0]: 0.8, factors[1]: 1.3},
            {"run_id": "run_b", factors[0]: 1.2, factors[1]: 0.9},
        ]
        specs = build_paired_run_specs(
            factors=factors,
            backgrounds=backgrounds,
            range_rows=backgrounds,
            reuse_background_centers=True,
        )

        self.assertEqual(len(specs), 10)
        centers = [spec for spec in specs if spec["paired_metadata"].get("shared_center")]
        self.assertEqual(len(centers), 2)
        self.assertEqual(
            {spec["paired_metadata"]["variant"] for spec in specs if not spec["paired_metadata"].get("shared_center")},
            {"low", "high"},
        )

    def test_payload_uses_shared_center_for_each_factor(self) -> None:
        factor = "supplier_lead_node::S1"
        backgrounds = [{"run_id": "run_a", "scenario_family": "delay"}]
        trajectories = [
            {
                "series": {"total_cost": [(0, 100.0), (1, 110.0)]},
                "paired_metadata": {
                    "factor": "__shared_center__",
                    "background_id": "run_a",
                    "variant": "center",
                    "shared_center": True,
                },
            },
            {
                "series": {"total_cost": [(0, 90.0), (1, 95.0)]},
                "paired_metadata": {
                    "factor": factor,
                    "background_id": "run_a",
                    "variant": "low",
                    "input_low": 0.8,
                    "input_reference": 1.0,
                    "input_high": 1.2,
                },
            },
            {
                "series": {"total_cost": [(0, 120.0), (1, 130.0)]},
                "paired_metadata": {
                    "factor": factor,
                    "background_id": "run_a",
                    "variant": "high",
                    "input_low": 0.8,
                    "input_reference": 1.0,
                    "input_high": 1.2,
                },
            },
        ]
        payload = build_paired_propagation_payload(
            factors=[factor],
            backgrounds=backgrounds,
            trajectory_runs=trajectories,
            scenario_id="scn:BASE",
            uncertainty=0.20,
        )

        band = payload["metrics"]["total_cost"]["factors"][0]
        self.assertEqual(band["center"], [100.0, 110.0])
        self.assertEqual(band["background_count"], 1)


if __name__ == "__main__":
    unittest.main()
