import unittest
import sys
import os
import random

# Ensure backend modules are importable
sys.path.append(os.path.join(os.getcwd(), 'backend'))

from physical.device_model import DeviceType
from physical.device_catalog import get_device_template
from api.backend_facade import PowerGridBackend
from logic.ui_tree_snapshot import _translate_node_type, _round_val
from core.models import Node, NodeType
from config import SimulationConfig

class TestNewRequirements(unittest.TestCase):

    def test_catalog_expansion(self):
        """Verify that all new device types are present and have correct power."""
        tv = get_device_template(DeviceType.TV)
        self.assertAlmostEqual(tv.avg_power, 0.095)
        self.assertEqual(tv.default_name, "TV")

        shower = get_device_template(DeviceType.SHOWER)
        self.assertAlmostEqual(shower.avg_power, 6.500)
        self.assertEqual(shower.default_name, "Chuveiro Elétrico")

        generic = get_device_template(DeviceType.GENERIC)
        self.assertAlmostEqual(generic.avg_power, 0.100)

    def test_initialization_rules(self):
        """Verify random device population and CAPACITY REMOVAL rules."""
        cfg = SimulationConfig(
            random_seed=42,
            num_clusters=1,
            num_generation_plants=1,
            num_transmission_substations=1,
            max_transmission_segment_length=1500.0,
            max_mv_segment_length=800.0,
            max_lv_segment_length=250.0
        )
        backend = PowerGridBackend(cfg)

        consumers = [n for n in backend.graph.nodes.values() if n.node_type == NodeType.CONSUMER_POINT]
        self.assertTrue(len(consumers) > 0, "No consumers generated")

        for node in consumers:
            # Check devices count
            devices = backend.device_state.devices_by_node.get(node.id, [])
            self.assertTrue(3 <= len(devices) <= 10, f"Consumer {node.id} has {len(devices)} devices, expected 3-10")

            # Check capacity rule: Consumers should have None capacity
            self.assertIsNone(node.capacity, f"Consumer {node.id} should have None capacity")

    def test_api_localization_and_formatting(self):
        """Verify translation and rounding."""
        # Test helper functions directly

        # Translations
        self.assertEqual(_translate_node_type(NodeType.CONSUMER_POINT), "Consumidor")
        self.assertEqual(_translate_node_type(NodeType.GENERATION_PLANT), "Usina Geradora")

        # Rounding
        self.assertEqual(_round_val(1.23456), 1.235)
        self.assertEqual(_round_val(1.2), 1.2)

        # Snapshot Integration
        cfg = SimulationConfig(random_seed=42)
        backend = PowerGridBackend(cfg)
        snapshot = backend.get_tree_snapshot()
        tree = snapshot["tree"]

        # Check one consumer entry
        consumer_entry = next((x for x in tree if x["node_type"] == "Consumidor"), None)
        self.assertIsNotNone(consumer_entry)

        # Verify keys and values
        self.assertIsNone(consumer_entry.get("network_type"), "Network type should be removed")
        self.assertIsNone(consumer_entry.get("capacity"), "Capacity should be None")
        self.assertIsNone(consumer_entry.get("status"), "Status should be None for consumers")

        # Verify rounding in float fields (current_load is present)
        self.assertIsInstance(consumer_entry["current_load"], float)

if __name__ == "__main__":
    unittest.main()
