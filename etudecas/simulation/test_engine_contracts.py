import unittest

from etudecas.simulation.engine.contracts import (
    simulation_request_payload,
    supplier_parameter_overrides,
    supplier_parameter_request_payload,
)


class SimulationEngineContractsTest(unittest.TestCase):
    def test_supplier_node_parameters_map_to_engine_overrides(self):
        self.assertEqual(
            supplier_parameter_overrides(
                parameter_group="supplier_stock_node",
                supplier_id="SDC-1",
                level=0.5,
            ),
            {"supplier_node_scale": {"SDC-1": 0.5}},
        )
        self.assertEqual(
            supplier_parameter_overrides(
                parameter_group="supplier_capacity_node",
                supplier_id="SDC-1",
                level=0.7,
            ),
            {"supplier_capacity_node_scale": {"SDC-1": 0.7}},
        )
        self.assertEqual(
            supplier_parameter_overrides(
                parameter_group="supplier_lead_time_node",
                supplier_id="SDC-1",
                level=1.4,
            ),
            {"edge_src_lead_time_scale": {"SDC-1": 1.4}},
        )
        self.assertEqual(
            supplier_parameter_overrides(
                parameter_group="supplier_reliability_node",
                supplier_id="SDC-1",
                level=0.9,
            ),
            {"edge_src_reliability_scale": {"SDC-1": 0.9}},
        )

    def test_global_and_upstream_parameters_map_to_engine_overrides(self):
        self.assertEqual(
            supplier_parameter_overrides(
                parameter_group="supplier_capacity_global",
                level=0.6,
            ),
            {"factors": {"supplier_capacity_scale": 0.6}},
        )
        self.assertEqual(
            supplier_parameter_overrides(
                parameter_group="supplier_upstream_supply",
                parameter_key="external_procurement_enabled",
                level=0.01,
            ),
            {"scenario_flags": {"external_procurement_enabled": False}},
        )
        self.assertEqual(
            supplier_parameter_overrides(
                parameter_group="supplier_upstream_supply",
                parameter_key="external_procurement_lead_days_scale",
                level=1.5,
            ),
            {"factors": {"external_procurement_lead_days_scale": 1.5}},
        )

    def test_request_payload_is_server_ready_but_execution_agnostic(self):
        request = supplier_parameter_request_payload(
            input_path="graph.json",
            scenario_id="scn:BASE",
            days=30,
            parameter_group="supplier_capacity_node",
            supplier_id="SDC-1",
            level=0.75,
            run_id="demo",
        )

        self.assertEqual(request["input_path"], "graph.json")
        self.assertEqual(request["days"], 30)
        self.assertTrue(request["skip_map"])
        self.assertEqual(request["run_id"], "demo")
        self.assertEqual(request["overrides"], {"supplier_capacity_node_scale": {"SDC-1": 0.75}})

        generic = simulation_request_payload(overrides={"factors": {"supplier_stock_scale": 0.8}})
        self.assertEqual(generic["overrides"], {"factors": {"supplier_stock_scale": 0.8}})


if __name__ == "__main__":
    unittest.main()
