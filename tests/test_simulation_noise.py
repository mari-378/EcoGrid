
import unittest
import os
import sys
import time
from unittest.mock import patch

# Ensure backend modules are importable
sys.path.append(os.path.join(os.getcwd(), 'backend'))

from api.backend_facade import PowerGridBackend
from core.models import Node, NodeType
from config import SimulationConfig
from physical.device_simulation import update_devices_and_nodes_loads

class TestSimulationNoise(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        print("Initializing PowerGridBackend for noise test...")
        cfg = SimulationConfig(
            random_seed=123,
            num_clusters=1,
            num_generation_plants=1,
            num_transmission_substations=1,
            max_transmission_segment_length=1500.0,
            max_mv_segment_length=800.0,
            max_lv_segment_length=250.0
        )
        cls.backend = PowerGridBackend(cfg)

    def test_capacity_factor(self):
        """Verify capacity rules."""
        snap = self.backend.get_tree_snapshot()

        # Check a consumer node (Should be None)
        consumer = next((n for n in snap["tree"] if n["node_type"] == "Consumidor"), None)
        if consumer:
            print(f"Consumer {consumer['id']} Capacity: {consumer['capacity']}")
            self.assertIsNone(consumer.get("capacity"))

        # Check a DS (Should be 13 * (children + 1))
        ds = next((n for n in snap["tree"] if n["node_type"] == "Subestação de Distribuição"), None)
        if ds:
            print(f"DS {ds['id']} Capacity: {ds['capacity']}")
            self.assertTrue(ds['capacity'] >= 13.0)
            self.assertTrue(ds['capacity'] % 13.0 == 0.0)

    def test_noise_fluctuation(self):
        """Verify device power changes with time (Manual inspection of state)."""
        # We assume devices are initialized
        if not self.backend.device_state.devices_by_id:
            self.skipTest("No devices initialized")

        # Pick one device
        device_id = list(self.backend.device_state.devices_by_id.keys())[0]
        device = self.backend.device_state.devices_by_id[device_id]

        # Manually trigger update at t=0
        update_devices_and_nodes_loads(
            self.backend.graph,
            self.backend.device_state,
            t_seconds=0.0,
            service=self.backend.service
        )
        p0 = device.current_power

        # Manually trigger update at t=3600
        update_devices_and_nodes_loads(
            self.backend.graph,
            self.backend.device_state,
            t_seconds=3600.0,
            service=self.backend.service
        )
        p1 = device.current_power

        print(f"Device {device.name}: t=0 power={p0}, t=3600 power={p1}")

        # Verify change
        self.assertNotEqual(p0, p1, "Device power should change over 1 hour")

if __name__ == "__main__":
    unittest.main()
