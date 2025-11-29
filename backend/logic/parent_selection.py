from __future__ import annotations

from dataclasses import dataclass
import heapq
from typing import Dict, List, Optional, Set, Tuple

from core.graph_core import PowerGridGraph
from core.models import Edge, Node, NodeType
from physical.energy_loss import estimate_edge_loss


@dataclass
class ParentSelectionResult:
    """
    Resultado de uma busca de pai lógico usando o grafo físico.

    Atributos:
        parent_id:
            Identificador do nó selecionado como pai lógico. Pode ser
            None quando nenhum candidato compatível é alcançável.
        total_cost:
            Custo total acumulado ao longo do caminho físico (soma das
            perdas estimadas em cada aresta).
        path:
            Lista de ids de nós representando o caminho físico desde
            o nó filho até o pai selecionado (incluindo ambos). Pode
            ser vazia em caso de falha.
    """
    parent_id: Optional[str]
    total_cost: float
    path: List[str]


def _allowed_parent_types_for(child_type: NodeType) -> Set[NodeType]:
    """
    Retorna o conjunto de tipos de nós que podem atuar como pai
    lógico de um nó do tipo `child_type`.

    Regras utilizadas:

        - CONSUMER_POINT:
            Pais possíveis: DISTRIBUTION_SUBSTATION
        - DISTRIBUTION_SUBSTATION:
            Pais possíveis: TRANSMISSION_SUBSTATION
        - TRANSMISSION_SUBSTATION:
            Pais possíveis: GENERATION_PLANT
        - GENERATION_PLANT:
            Não possui pai lógico.

    Parâmetros:
        child_type:
            Tipo de nó filho.

    Retorno:
        Conjunto de tipos possíveis para o pai. Pode ser vazio.
    """
    if child_type == NodeType.CONSUMER_POINT:
        return {NodeType.DISTRIBUTION_SUBSTATION}
    if child_type == NodeType.DISTRIBUTION_SUBSTATION:
        return {NodeType.TRANSMISSION_SUBSTATION}
    if child_type == NodeType.TRANSMISSION_SUBSTATION:
        return {NodeType.GENERATION_PLANT}
    return set()


def _build_edge_adjacency(graph: PowerGridGraph) -> Dict[str, List[Edge]]:
    """
    Constrói uma lista de adjacência simples baseada nas arestas do
    grafo físico, tratando cada aresta como não direcionada.

    A saída é um dicionário:

        node_id -> lista de Edge incidentes

    que pode ser usado por algoritmos de caminho mínimo sem depender
    de detalhes internos da implementação de `PowerGridGraph`.

    Parâmetros:
        graph:
            Grafo físico da rede.

    Retorno:
        Dicionário de adjacência nó -> lista de arestas.
    """
    adjacency: Dict[str, List[Edge]] = {}

    for edge in graph.edges.values():
        adjacency.setdefault(edge.from_node_id, []).append(edge)
        adjacency.setdefault(edge.to_node_id, []).append(edge)

    return adjacency


def find_best_parent_for_node(
    graph: PowerGridGraph,
    child_id: str,
) -> ParentSelectionResult:
    """
    Executa uma busca de melhor pai lógico para o nó `child_id` usando
    o grafo físico e um algoritmo de caminho mínimo (Dijkstra).

    Critério:

        - Entre todos os nós alcançáveis cujo tipo seja compatível com
          o tipo do nó filho (segundo `_allowed_parent_types_for`),
          seleciona-se aquele que minimiza a soma das perdas estimadas
          ao transportar a carga do filho ao longo do caminho físico.

    Detalhes importantes:

        - A potência considerada para o roteamento é a carga atual do
          nó filho (`child.current_load`). Se este valor for None ou
          não positivo, utiliza-se um valor mínimo fictício (por
          exemplo, 1.0) apenas para fins de custo relativo.

        - O grafo físico é tratado como não direcionado: cada aresta
          pode ser percorrida em ambos os sentidos.

        - O algoritmo termina assim que o primeiro candidato a pai
          for retirado da fila de prioridade (propriedade de Dijkstra).

    Parâmetros:
        graph:
            Grafo físico contendo nós e arestas.
        child_id:
            Identificador do nó filho para o qual se busca um pai.

    Retorno:
        Instância de `ParentSelectionResult` contendo:
            - parent_id: id do pai selecionado ou None;
            - total_cost: custo mínimo acumulado;
            - path: caminho de nós desde o filho até o pai.
    """
    child: Optional[Node] = graph.get_node(child_id)
    if child is None:
        return ParentSelectionResult(
            parent_id=None,
            total_cost=float("inf"),
            path=[],
        )

    allowed_parent_types = _allowed_parent_types_for(child.node_type)
    if not allowed_parent_types:
        # Tipo de nó que não admite pai lógico (por exemplo, usina).
        return ParentSelectionResult(
            parent_id=None,
            total_cost=float("inf"),
            path=[],
        )

    # Potência utilizada para estimar as perdas. Se o filho não tiver
    # carga atual definida, usamos um valor mínimo para não zerar
    # completamente o custo relativo.
    power_for_routing = float(child.current_load or 1.0)

    # Conjunto de nós candidatos a serem pais.
    candidate_parents: Set[str] = set()
    for node_id, node in graph.nodes.items():
        if node_id == child_id:
            continue
        if node.node_type in allowed_parent_types:
            candidate_parents.add(node_id)

    if not candidate_parents:
        return ParentSelectionResult(
            parent_id=None,
            total_cost=float("inf"),
            path=[],
        )

    adjacency = _build_edge_adjacency(graph)

    # Dijkstra: heap com tuplas (custo_acumulado, node_id, path)
    heap: List[Tuple[float, str, List[str]]] = []
    heapq.heappush(heap, (0.0, child_id, [child_id]))

    visited: Set[str] = set()

    while heap:
        cost, current_id, path = heapq.heappop(heap)
        if current_id in visited:
            continue
        visited.add(current_id)

        # Se este nó é um candidato a pai, terminamos a busca.
        if current_id in candidate_parents:
            return ParentSelectionResult(
                parent_id=current_id,
                total_cost=cost,
                path=path,
            )

        # Explora vizinhos via arestas incidentes.
        for edge in adjacency.get(current_id, []):
            # Descobre o vizinho da outra ponta.
            if edge.from_node_id == current_id:
                neighbor_id = edge.to_node_id
            else:
                neighbor_id = edge.from_node_id

            if neighbor_id in visited:
                continue

            neighbor_node = graph.get_node(neighbor_id)
            if neighbor_node is None:
                continue

            # Custo incremental como perda estimada nesta aresta.
            edge_cost = estimate_edge_loss(
                graph=graph,
                edge=edge,
                power=power_for_routing,
            )
            new_cost = cost + edge_cost
            new_path = path + [neighbor_id]

            heapq.heappush(heap, (new_cost, neighbor_id, new_path))

    # Nenhum candidato alcançável.
    return ParentSelectionResult(
        parent_id=None,
        total_cost=float("inf"),
        path=[],
    )


__all__ = [
    "ParentSelectionResult",
    "find_best_parent_for_node",
]
