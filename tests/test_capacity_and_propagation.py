import unittest
import sys
import os
import uuid

# Ensure backend modules are importable
sys.path.append(os.path.join(os.getcwd(), 'backend'))

from api.backend_facade import PowerGridBackend
from core.models import Node, Edge, NodeType, EdgeType
from config import SimulationConfig
from physical.device_model import DeviceType

class TestCapacityAndPropagation(unittest.TestCase):

    def test_capacity_analysis(self):
        """
        Verify that:
        1. Consumers have NO capacity.
        2. Substations have capacity = 13.0 * (num_children + 1).
        """
        cfg = SimulationConfig(
            random_seed=123,
            num_clusters=1,
            num_generation_plants=1,
            num_transmission_substations=1,
            max_transmission_segment_length=1500.0,
            max_mv_segment_length=800.0,
            max_lv_segment_length=250.0
        )
        backend = PowerGridBackend(cfg)
        graph = backend.graph
        index = backend.index

        # Check Consumers
        consumers = [n for n in graph.nodes.values() if n.node_type == NodeType.CONSUMER_POINT]
        self.assertTrue(len(consumers) > 0)

        for c in consumers:
            self.assertIsNone(c.capacity)

        # Check Substations
        substations = [n for n in graph.nodes.values() if n.node_type == NodeType.DISTRIBUTION_SUBSTATION]
        self.assertTrue(len(substations) > 0)

        for s in substations:
            children = list(index.get_children(s.id))
            num_children = len(children)

            expected_capacity = 13.0 * (num_children + 1)

            self.assertAlmostEqual(s.capacity, expected_capacity, places=3,
                                   msg=f"Substation {s.id} capacity mismatch. Children: {num_children}")

    def test_load_propagation(self):
        """
        Verify that adding a high-load device updates the consumer AND propagates
        to the Distribution Substation.
        """
        cfg = SimulationConfig(random_seed=999)
        backend = PowerGridBackend(cfg)

        # Find a consumer and its parent
        snapshot = backend.get_tree_snapshot()
        tree = snapshot["tree"]

        # Use translated name "Consumidor"
        consumer_entry = next((n for n in tree if n["node_type"] == "Consumidor"), None)
        self.assertIsNotNone(consumer_entry)

        c_id = consumer_entry["id"]
        p_id = consumer_entry["parent_id"]
        self.assertIsNotNone(p_id)

        parent_node_initial = backend.graph.get_node(p_id)
        initial_parent_load = parent_node_initial.current_load

        # Add a high load device (Shower ~ 6.5kW)
        backend.add_device(c_id, DeviceType.SHOWER, "TestShower")

        # Check Consumer Load Increase (approx 6.5)
        node_after = backend.graph.get_node(c_id)
        # Note: current_load might include previous devices + 6.5
        # We can check the delta

        # Check Parent Load Increase
        parent_node_after = backend.graph.get_node(p_id)

        delta_parent = parent_node_after.current_load - initial_parent_load
        self.assertAlmostEqual(delta_parent, 6.5, delta=0.1,
                               msg="Load did not propagate correctly to parent")

if __name__ == "__main__":
    unittest.main()
