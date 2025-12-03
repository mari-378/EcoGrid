from __future__ import annotations
from typing import Dict, Set

from core.graph_core import PowerGridGraph
from core.models import Node, NodeType
from logic.bplus_index import BPlusIndex

def initialize_capacities(graph: PowerGridGraph, index: BPlusIndex) -> None:
    """
    Inicializa a capacidade dos nós (Subestações e Usinas) baseado na topologia.
    Regra: Node.capacity = 13 * max(sum(child_capacities) + child_count, (total_consumers / clusters) + 1)

    NOTA: Nós do tipo CONSUMER_POINT são ignorados nesta função e devem ter
    capacidade NULA (None).
    """

    # 1. Calculate global metrics
    total_consumers = 0
    for node_id in graph.nodes:
        node = graph.get_node(node_id)
        if node and node.node_type == NodeType.CONSUMER_POINT:
            total_consumers += 1

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

        # Regras Específicas:
        if node.node_type == NodeType.DISTRIBUTION_SUBSTATION:
            # capacidade = 13 * (número de filhos + 1)
            node.capacity = 13.0 * (num_children + 1)

        elif node.node_type == NodeType.TRANSMISSION_SUBSTATION:
            # capacidade = 13 * (número de nós consumidores em toda a rede ) * 0.75
            node.capacity = 13.0 * total_consumers * 0.75

        elif node.node_type == NodeType.GENERATION_PLANT:
            # Padrão seguro para usinas: cobrir demanda total de consumidores (aprox)
            # Usa lógica similar a Transmissão mas sem fator de redução, ou soma capacidades filhas.
            # Vamos usar 13 * total_consumers para garantir que seja > Transmissão
            node.capacity = 13.0 * total_consumers
        else:
            # Fallback genérico (não deve acontecer com tipos conhecidos)
            node.capacity = 13.0 * (num_children + 1)
