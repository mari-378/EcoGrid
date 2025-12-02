from __future__ import annotations
from typing import Dict, Set

from core.graph_core import PowerGridGraph
from core.models import Node, NodeType
from logic.bplus_index import BPlusIndex

def initialize_capacities(graph: PowerGridGraph, index: BPlusIndex) -> None:
    """
    Inicializa a capacidade dos nós (Subestações e Usinas) baseado na topologia.
    Regra: Node.capacity = 13 * (num_children + 1) + sum(child.capacity or 0)

    NOTA: Nós do tipo CONSUMER_POINT são ignorados nesta função e devem ter
    capacidade NULA (None).
    """

    # Bottom-up traversal is required because capacity depends on children's capacity.
    # index.iter_preorder() is Top-Down.
    # We need to reverse it to process leaves first (consumers) then up to root.

    nodes_ordered = list(index.iter_preorder())
    nodes_bottom_up = reversed(nodes_ordered)

    for node_id in nodes_bottom_up:
        node = graph.get_node(node_id)
        if node is None:
            continue

        # Garante que consumidores não tenham capacidade definida
        if node.node_type == NodeType.CONSUMER_POINT:
            node.capacity = None
            continue

        children_ids = index.get_children(node_id)
        num_children = len(children_ids)

        sum_children_capacity = 0.0
        for child_id in children_ids:
            child = graph.get_node(child_id)
            if child and child.capacity is not None:
                sum_children_capacity += child.capacity

        # Nova regra: 13 * (filhos + 1) + soma_cap_filhos
        new_capacity = (13.0 * (num_children + 1)) + sum_children_capacity

        node.capacity = new_capacity
