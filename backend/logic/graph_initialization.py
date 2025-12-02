from __future__ import annotations

from typing import Tuple

from core.graph_core import PowerGridGraph
from core.models import Node, NodeType
from logic.bplus_index import BPlusIndex
from logic.logical_graph_service import LogicalGraphService


def build_logical_state(
    graph: PowerGridGraph,
) -> Tuple[PowerGridGraph, BPlusIndex, LogicalGraphService]:
    """
    Constrói o estado lógico mínimo (índice B+ e serviço lógico) a
    partir de um grafo físico já carregado.

    Utiliza `LogicalGraphService.hydrate_from_physical` para
    reconstruir a árvore lógica completa a partir da topologia.

    Parâmetros:
        graph:
            Grafo físico já preenchido com nós e arestas.

    Retorno:
        Tupla `(graph, index, service)` onde:
            - `graph` é o grafo físico de entrada;
            - `index` é uma instância de `BPlusIndex` populada;
            - `service` é uma instância de `LogicalGraphService` pronta.
    """
    index = BPlusIndex()
    service = LogicalGraphService(graph=graph, index=index)

    # Executa a hidratação completa
    service.hydrate_from_physical()

    return graph, index, service
