from __future__ import annotations

import math
from typing import Iterable, List, Sequence, Tuple

from core.graph_core import PowerGridGraph
from core.models import Edge, EdgeType, Node, NodeType
from config import SimulationConfig


def _euclidean_distance(a: Node, b: Node) -> float:
    """
    Calcula a distância euclidiana entre dois nós no plano cartesiano.

    A distância é calculada a partir das coordenadas `position_x` e
    `position_y` dos nós, usando a fórmula padrão:

        d = sqrt( (x_a - x_b)^2 + (y_a - y_b)^2 )

    Parâmetros:
        a:
            Primeiro nó.
        b:
            Segundo nó.

    Retorno:
        Distância euclidiana entre os dois nós, na mesma unidade das
        coordenadas usadas pela simulação.
    """
    dx = a.position_x - b.position_x
    dy = a.position_y - b.position_y
    return math.hypot(dx, dy)


def _select_transmission_nodes(graph: PowerGridGraph) -> List[Node]:
    """
    Seleciona os nós relevantes para a malha de transmissão.

    Esta função percorre todos os nós do grafo e retorna apenas aqueles
    cujo tipo é:

    - GENERATION_PLANT
    - TRANSMISSION_SUBSTATION

    Esses nós compõem o conjunto de vértices sobre o qual será
    construída a malha de transmissão em alta tensão.

    Parâmetros:
        graph:
            Grafo físico contendo todos os nós da rede.

    Retorno:
        Lista de nós que participam da malha de transmissão.
    """
    result: List[Node] = []
    for node in graph.iter_nodes():
        if node.node_type in {
            NodeType.GENERATION_PLANT,
            NodeType.TRANSMISSION_SUBSTATION,
        }:
            result.append(node)
    return result


def _prim_mst(
    nodes: List[Node],
    max_edge_length: float | None = None,
) -> List[Tuple[Node, Node, float]]:
    """
    Constrói uma árvore geradora mínima (MST) usando o algoritmo de Prim.

    A MST é construída sobre o grafo completo induzido pelo conjunto de
    nós fornecidos, onde o peso de cada aresta é a distância euclidiana
    entre os nós. Opcionalmente, pode-se impor um limite máximo de
    comprimento para as arestas; se especificado, arestas com distância
    maior que `max_edge_length` não são consideradas.

    Parâmetros:
        nodes:
            Lista de nós que devem ser conectados pela MST. É esperado
            que esta lista não esteja vazia.
        max_edge_length:
            Comprimento máximo permitido para uma aresta na MST. Se for
            `None`, nenhuma restrição adicional é aplicada. Se for um
            valor numérico, qualquer aresta com comprimento estritamente
            maior será descartada.

    Retorno:
        Lista de tuplas `(u, v, dist)` representando as arestas da MST,
        onde `u` e `v` são nós e `dist` é a distância entre eles.

    Observação:
        Se o limite de comprimento impedir que o grafo permaneça conexo,
        a MST resultante pode não cobrir todos os nós. Nessa situação,
        a lista retornada conterá apenas as conexões possíveis dentro das
        restrições impostas.
    """
    if not nodes:
        return []

    n = len(nodes)
    # Índices dos nós de 0 a n-1
    in_tree = [False] * n
    min_dist = [math.inf] * n
    parent: List[int | None] = [None] * n

    # Começa pelo nó 0
    min_dist[0] = 0.0

    for _ in range(n):
        # Seleciona o nó fora da árvore com menor distância
        u = -1
        best = math.inf
        for i in range(n):
            if not in_tree[i] and min_dist[i] < best:
                best = min_dist[i]
                u = i

        if u == -1:
            # Não há mais nós alcançáveis (grafo desconexo sob as restrições)
            break

        in_tree[u] = True

        # Atualiza distâncias mínimas para nós ainda não incluídos
        for v in range(n):
            if in_tree[v] or v == u:
                continue
            dist = _euclidean_distance(nodes[u], nodes[v])
            if max_edge_length is not None and dist > max_edge_length:
                continue
            if dist < min_dist[v]:
                min_dist[v] = dist
                parent[v] = u

    mst_edges: List[Tuple[Node, Node, float]] = []
    for v in range(1, n):
        p = parent[v]
        if p is None:
            # Nó não conectado dentro das restrições de comprimento
            continue
        u = p
        dist = _euclidean_distance(nodes[u], nodes[v])
        mst_edges.append((nodes[u], nodes[v], dist))

    return mst_edges


def build_transmission_backbone(
    config: SimulationConfig,
    graph: PowerGridGraph,
) -> None:
    """
    Constrói o backbone de transmissão em alta tensão.

    Esta função identifica os nós de geração (`GENERATION_PLANT`) e as
    subestações de transmissão (`TRANSMISSION_SUBSTATION`) presentes no
    grafo e constrói uma malha básica de transmissão conectando esses
    nós por meio de uma árvore geradora mínima (MST).

    O peso de cada aresta considerada na MST é a distância euclidiana
    entre os nós. Opcionalmente, utiliza-se o parâmetro
    `max_transmission_segment_length` de `SimulationConfig` para
    descartar arestas muito longas; nesse caso, a MST resultante pode
    não ser completamente conexa se as restrições forem muito severas.

    As arestas criadas:

    - são adicionadas ao grafo como `Edge` com `edge_type` igual a
      `EdgeType.TRANSMISSION_SEGMENT`;
    - recebem identificadores sequenciais com prefixo "HTM_" (High
      Tension Main) para a MST em si;
    - têm o campo `length` preenchido com a distância euclidiana
      correspondente.

    Parâmetros:
        config:
            Instância de `SimulationConfig` contendo, entre outros, o
            parâmetro `max_transmission_segment_length`.
        graph:
            Grafo físico `PowerGridGraph` que já deve conter os nós de
            geração e de subestações de transmissão. As novas arestas da
            malha de transmissão serão adicionadas diretamente a este
            grafo.

    Efeitos colaterais:
        - Arestas do tipo `TRANSMISSION_SEGMENT` são adicionadas ao
          grafo conectando os nós relevantes.
    """
    transmission_nodes = _select_transmission_nodes(graph)
    if not transmission_nodes:
        return

    max_len = config.max_transmission_segment_length

    mst_edges = _prim_mst(transmission_nodes, max_edge_length=max_len)

    edge_index = 0
    for u, v, dist in mst_edges:
        edge_id = f"HTM_{edge_index}"
        edge = Edge(
            id=edge_id,
            edge_type=EdgeType.TRANSMISSION_SEGMENT,
            from_node_id=u.id,
            to_node_id=v.id,
            length=dist,
        )
        graph.add_edge(edge)
        edge_index += 1


__all__: Sequence[str] = ["build_transmission_backbone"]
