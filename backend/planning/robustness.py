from __future__ import annotations

import math
from typing import Dict, List, Optional, Sequence, Tuple

from core.graph_core import PowerGridGraph
from core.models import Edge, EdgeType, Node, NodeType
from config import SimulationConfig


def _euclidean_distance(a: Node, b: Node) -> float:
    """
    Calcula a distância euclidiana entre dois nós no plano cartesiano.

    A distância é baseada em `position_x` e `position_y`:

        d = sqrt( (x_a - x_b)^2 + (y_a - y_b)^2 )

    Parâmetros:
        a:
            Primeiro nó.
        b:
            Segundo nó.

    Retorno:
        Distância euclidiana entre os dois nós, na mesma unidade das
        coordenadas utilizadas pela simulação.
    """
    dx = a.position_x - b.position_x
    dy = a.position_y - b.position_y
    return math.hypot(dx, dy)


def _get_nodes_by_type(graph: PowerGridGraph, node_type: NodeType) -> List[Node]:
    """
    Retorna todos os nós de um determinado tipo presentes no grafo.

    Parâmetros:
        graph:
            Grafo físico contendo os nós.
        node_type:
            Tipo de nó desejado, conforme `NodeType`.

    Retorno:
        Lista de nós cujo campo `node_type` coincide com o valor
        informado.
    """
    return [n for n in graph.iter_nodes() if n.node_type is node_type]


def _are_connected(
    graph: PowerGridGraph,
    node_id_a: str,
    node_id_b: str,
    edge_type_filter: Optional[EdgeType] = None,
) -> bool:
    """
    Verifica se dois nós já estão conectados por alguma aresta no grafo.

    Opcionalmente, é possível restringir a verificação a um tipo
    específico de aresta (`edge_type_filter`). A checagem utiliza a
    vizinhança de `node_id_a` para encontrar conexões diretas com
    `node_id_b`.

    Parâmetros:
        graph:
            Grafo físico que contém nós e arestas.
        node_id_a:
            Identificador do primeiro nó.
        node_id_b:
            Identificador do segundo nó.
        edge_type_filter:
            Se não for `None`, apenas arestas desse tipo serão
            consideradas na verificação.

    Retorno:
        `True` se existir uma aresta ligando diretamente os dois nós,
        respeitando (se fornecido) o filtro de tipo de aresta; `False`
        caso contrário.
    """
    for neighbor in graph.neighbors(node_id_a):
        if neighbor.neighbor_id != node_id_b:
            continue
        if edge_type_filter is not None and neighbor.edge.edge_type is not edge_type_filter:
            continue
        return True
    return False


def _build_extra_transmission_links(
    config: SimulationConfig,
    graph: PowerGridGraph,
    start_edge_index: int,
    max_extra_per_node: int = 2,
) -> int:
    """
    Cria arestas extras de transmissão para aumentar a redundância em
    alta tensão.

    Esta função seleciona:

    - nós do tipo `GENERATION_PLANT`;
    - nós do tipo `TRANSMISSION_SUBSTATION`,

    e, para cada um deles, tenta criar algumas conexões adicionais com
    nós próximos, limitando o número de novas arestas incidentes em
    `max_extra_per_node`. O objetivo é aproximar uma malha mais densa em
    alta tensão, reduzindo a probabilidade de desconexão caso algumas
    arestas da MST original sejam removidas.

    A lógica geral é:

    1. Construir uma lista de candidatos (usinas e subestações de
       transmissão).
    2. Para cada nó da lista:
       - ordenar os demais candidatos por distância crescente;
       - percorrer os candidatos e, para cada um:
         - verificar se ainda há quota de arestas extras para o nó
           atual;
         - verificar se os nós já não estão conectados por uma
           aresta de transmissão;
         - verificar se a distância está abaixo de um limite
           máximo:
             - utiliza-se `max_transmission_segment_length` como
               comprimento típico;
             - para reforços, é permitida uma folga moderada
               (por exemplo, 1.5 * esse valor), se o limite existir.
       - criar uma aresta `TRANSMISSION_SEGMENT` para cada par
         aceito, com identificador prefixado por "HTR_" (High Tension
         Reinforcement).

    Parâmetros:
        config:
            Instância de `SimulationConfig` contendo, entre outros, o
            parâmetro `max_transmission_segment_length`.
        graph:
            Grafo físico `PowerGridGraph` que já deve conter a malha
            básica de transmissão construída anteriormente (por exemplo,
            pela MST de transmissão).
        start_edge_index:
            Índice inicial para a numeração das novas arestas de
            reforço.
        max_extra_per_node:
            Número máximo de arestas de reforço de transmissão que cada
            nó poderá receber. Este valor controla a densidade
            adicional introduzida na malha de alta tensão.

    Retorno:
        Próximo índice de aresta livre após a criação das conexões
        extras de transmissão.
    """
    ts_nodes = _get_nodes_by_type(graph, NodeType.TRANSMISSION_SUBSTATION)
    g_nodes = _get_nodes_by_type(graph, NodeType.GENERATION_PLANT)
    candidates: List[Node] = ts_nodes + g_nodes

    if len(candidates) < 2:
        return start_edge_index

    if config.max_transmission_segment_length is not None:
        max_len = 1.5 * config.max_transmission_segment_length
    else:
        max_len = None

    edge_index = start_edge_index

    # Pré-calcula posições em um dicionário para acesso rápido
    nodes_by_id: Dict[str, Node] = {n.id: n for n in candidates}

    for node in candidates:
        created_for_node = 0

        # Ordena os outros candidatos por distância
        distances: List[Tuple[float, Node]] = []
        for other in candidates:
            if other.id == node.id:
                continue
            dist = _euclidean_distance(node, other)
            distances.append((dist, other))

        distances.sort(key=lambda t: t[0])

        for dist, other in distances:
            if created_for_node >= max_extra_per_node:
                break

            if max_len is not None and dist > max_len:
                continue

            # Evita duplicar arestas já existentes de transmissão
            if _are_connected(
                graph,
                node_id_a=node.id,
                node_id_b=other.id,
                edge_type_filter=EdgeType.TRANSMISSION_SEGMENT,
            ):
                continue

            edge_id = f"HTR_{edge_index}"
            edge = Edge(
                id=edge_id,
                edge_type=EdgeType.TRANSMISSION_SEGMENT,
                from_node_id=node.id,
                to_node_id=other.id,
                length=dist,
            )
            graph.add_edge(edge)
            edge_index += 1
            created_for_node += 1

    return edge_index


def _build_extra_mv_links(
    config: SimulationConfig,
    graph: PowerGridGraph,
    start_edge_index: int,
    max_extra_per_ds: int = 1,
) -> int:
    """
    Cria arestas extras de média tensão entre subestações de distribuição
    e subestações de transmissão.

    Esta função reforça a conectividade em média tensão criando
    conexões adicionais DS -> TS, além da ligação primária já
    existente. Para cada subestação de distribuição (`DISTRIBUTION_SUBSTATION`):

    1. Localiza todas as subestações de transmissão (`TRANSMISSION_SUBSTATION`).
    2. Ordena as subestações de transmissão por distância até a DS.
    3. Percorre a lista de TS ordenadas e, para cada uma:
       - verifica se a DS já está conectada a essa TS por uma aresta
         de média tensão;
       - verifica se a distância está abaixo de um limite máximo:

           - utiliza-se `max_mv_segment_length` como referência;
           - permite-se uma folga moderada (por exemplo, 1.5 * esse
             valor), se o limite existir.

       - cria uma nova aresta `MV_DISTRIBUTION_SEGMENT` com prefixo
         "MVR_" (Medium Voltage Reinforcement) se os critérios forem
         atendidos;

       - interrompe após atingir `max_extra_per_ds` conexões extras
         para a DS em questão.

    Essas conexões extras aumentam a redundância, permitindo que uma
    subestação de distribuição permaneça alimentada mesmo em caso de
    falha de uma ligação MV primária.

    Parâmetros:
        config:
            Instância de `SimulationConfig` contendo, entre outros, o
            parâmetro `max_mv_segment_length`.
        graph:
            Grafo físico `PowerGridGraph` que já deve conter a malha
            básica de média tensão construída anteriormente.
        start_edge_index:
            Índice inicial para a numeração das novas arestas de
            reforço em média tensão.
        max_extra_per_ds:
            Número máximo de conexões MV extras que cada subestação de
            distribuição poderá receber. Valores maiores aumentam a
            redundância, mas também a densidade de arestas.

    Retorno:
        Próximo índice de aresta livre após a criação das conexões
        extras em média tensão.
    """
    ds_nodes = _get_nodes_by_type(graph, NodeType.DISTRIBUTION_SUBSTATION)
    ts_nodes = _get_nodes_by_type(graph, NodeType.TRANSMISSION_SUBSTATION)

    if not ds_nodes or not ts_nodes:
        return start_edge_index

    if config.max_mv_segment_length is not None:
        max_len = 1.5 * config.max_mv_segment_length
    else:
        max_len = None

    edge_index = start_edge_index

    for ds in ds_nodes:
        created_for_ds = 0

        distances: List[Tuple[float, Node]] = []
        for ts in ts_nodes:
            dist = _euclidean_distance(ds, ts)
            distances.append((dist, ts))

        distances.sort(key=lambda t: t[0])

        for dist, ts in distances:
            if created_for_ds >= max_extra_per_ds:
                break

            if max_len is not None and dist > max_len:
                continue

            if _are_connected(
                graph,
                node_id_a=ds.id,
                node_id_b=ts.id,
                edge_type_filter=EdgeType.MV_DISTRIBUTION_SEGMENT,
            ):
                continue

            edge_id = f"MVR_{edge_index}"
            edge = Edge(
                id=edge_id,
                edge_type=EdgeType.MV_DISTRIBUTION_SEGMENT,
                from_node_id=ds.id,
                to_node_id=ts.id,
                length=dist,
            )
            graph.add_edge(edge)
            edge_index += 1
            created_for_ds += 1

    return edge_index


def apply_robustness_reinforcements(
    config: SimulationConfig,
    graph: PowerGridGraph,
) -> None:
    """
    Aplica reforços de robustez à rede de transmissão e de média tensão.

    Esta função executa uma etapa de reforço estrutural da rede com o
    objetivo de aproximar uma malha mais resiliente a falhas em alta e
    média tensão. O procedimento é dividido em duas partes principais:

    1. Reforços em alta tensão (transmissão):
       - São criadas arestas adicionais entre nós de geração
         (`GENERATION_PLANT`) e subestações de transmissão
         (`TRANSMISSION_SUBSTATION`), aproximando uma malha mais densa
         de transmissão.
       - Cada nó pode receber até um número limitado de novas arestas
         de reforço (`max_extra_per_node` da função interna).
       - As novas arestas são do tipo `TRANSMISSION_SEGMENT` e recebem
         identificadores com prefixo "HTR_".

    2. Reforços em média tensão (DS -> TS):
       - Cada subestação de distribuição (`DISTRIBUTION_SUBSTATION`)
         pode ganhar uma ou mais conexões adicionais com subestações de
         transmissão, além da ligação primária estabelecida na etapa de
         construção da rede MV.
       - As novas arestas são do tipo `MV_DISTRIBUTION_SEGMENT` e
         recebem identificadores com prefixo "MVR_".

    Em ambos os casos, utiliza-se como referência os parâmetros de
    comprimento máximo de segmentos já definidos em `SimulationConfig`
    (`max_transmission_segment_length` e `max_mv_segment_length`), com
    uma folga moderada para permitir reforços um pouco mais longos que
    as ligações principais, sem criar conexões excessivamente
    extensas.

    Parâmetros:
        config:
            Instância de `SimulationConfig` contendo os parâmetros de
            transmissão e média tensão.
        graph:
            Grafo físico `PowerGridGraph` que já deve conter a malha
            básica de transmissão e média tensão antes da aplicação de
            reforços.
    """
    edge_index = 0

    # 1. Reforços em alta tensão (transmissão)
    edge_index = _build_extra_transmission_links(
        config=config,
        graph=graph,
        start_edge_index=edge_index,
        max_extra_per_node=2,
    )

    # 2. Reforços em média tensão (DS -> TS)
    _build_extra_mv_links(
        config=config,
        graph=graph,
        start_edge_index=edge_index,
        max_extra_per_ds=1,
    )


__all__: Sequence[str] = ["apply_robustness_reinforcements"]
