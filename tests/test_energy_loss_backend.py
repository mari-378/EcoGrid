import json
import pytest
from backend.api.backend_facade import PowerGridBackend

def test_energy_loss_backend_calculation():
    """
    Verifies that the backend correctly calculates and returns 'energy_loss'
    for consumer nodes in the snapshot.
    """
    # Initialize backend
    backend = PowerGridBackend()

    # Get snapshot
    snapshot = backend.get_tree_snapshot()

    # Find consumer nodes
    consumers = [n for n in snapshot['tree'] if n['node_type'] == 'Consumidor']

    # Verify we have consumers
    assert len(consumers) > 0, "No consumer nodes found in the graph."

    # Check each consumer has 'energy_loss' and it is a float (or 0.0)
    for consumer in consumers:
        assert 'energy_loss' in consumer, f"Consumer {consumer['id']} missing 'energy_loss' field"
        loss = consumer['energy_loss']
        assert isinstance(loss, (float, int)), f"Consumer {consumer['id']} 'energy_loss' is not a number: {loss}"
        # Ideally loss >= 0
        assert loss >= 0, f"Consumer {consumer['id']} has negative loss: {loss}"

if __name__ == "__main__":
    try:
        test_energy_loss_backend_calculation()
        print("Backend Test Passed!")
    except Exception as e:
        print(f"Backend Test Failed: {e}")
        exit(1)
