
import unittest
from unittest.mock import MagicMock
from core.models import Node, NodeType
from core.graph_core import PowerGridGraph
from logic.bplus_index import BPlusIndex
from logic.capacity_analysis import initialize_capacities

class TestCapacityAnalysis(unittest.TestCase):
    def setUp(self):
        self.graph = PowerGridGraph()
        self.index = BPlusIndex()

    def test_capacity_rules(self):
        # Create a simple hierarchy:
        # Gen -> Trans -> Dist -> 2 Consumers

        gen = Node(id="gen", node_type=NodeType.GENERATION_PLANT, position_x=0, position_y=0)
        trans = Node(id="trans", node_type=NodeType.TRANSMISSION_SUBSTATION, position_x=0, position_y=0)
        dist = Node(id="dist", node_type=NodeType.DISTRIBUTION_SUBSTATION, position_x=0, position_y=0)
        c1 = Node(id="c1", node_type=NodeType.CONSUMER_POINT, position_x=0, position_y=0)
        c2 = Node(id="c2", node_type=NodeType.CONSUMER_POINT, position_x=0, position_y=0)

        # Add to graph
        self.graph.add_node(gen)
        self.graph.add_node(trans)
        self.graph.add_node(dist)
        self.graph.add_node(c1)
        self.graph.add_node(c2)

        # Build logical index
        self.index.add_root("gen")
        self.index.set_parent("trans", "gen")
        self.index.set_parent("dist", "trans")
        self.index.set_parent("c1", "dist")
        self.index.set_parent("c2", "dist")

        # Run analysis
        initialize_capacities(self.graph, self.index)

        # Check Distribution Capacity
        # capacity = 13 * (num_children + 1)
        # Dist has 2 children (c1, c2)
        # Expected: 13 * (2 + 1) = 39.0
        self.assertEqual(dist.capacity, 39.0)

        # Check Transmission Capacity
        # capacity = 13 * (total_consumers_in_network) * 0.75
        # Total consumers = 2
        # Expected: 13 * 2 * 0.75 = 26.0 * 0.75 = 19.5
        self.assertEqual(trans.capacity, 19.5)

        # Check Generation Capacity
        # capacity = 13 * total_consumers
        # Expected: 13 * 2 = 26.0
        self.assertEqual(gen.capacity, 26.0)

        # Check Consumer Capacity (Should be None)
        self.assertIsNone(c1.capacity)
        self.assertIsNone(c2.capacity)

if __name__ == '__main__':
    unittest.main()
