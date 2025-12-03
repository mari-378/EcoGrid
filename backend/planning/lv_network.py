from __future__ import annotations

import math
from typing import Dict, List, Optional, Sequence, Tuple

from core.graph_core import PowerGridGraph
from core.models import ClusterInfo, Edge, EdgeType, Node, NodeType
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


def _find_ds_candidates_for_consumer(
    consumer: Node,
    ds_nodes: List[Node],
) -> List[Tuple[Node, float]]:
    """
    Retorna uma lista de subestações de distribuição candidatas para um
    consumidor, ordenadas por distância crescente.

    A função considera todas as subestações de distribuição presentes na
    lista `ds_nodes`, calcula a distância até o consumidor, e retorna as
    candidatas ordenadas pela distância euclidiana.

    Parâmetros:
        consumer:
            Nó do tipo `CONSUMER_POINT` para o qual se deseja encontrar
            subestações de distribuição candidatas.
        ds_nodes:
            Lista de nós do tipo `DISTRIBUTION_SUBSTATION` disponíveis.

    Retorno:
        Lista de tuplas `(ds, dist)`, onde:
        - `ds` é uma subestação de distribuição,
        - `dist` é a distância euclidiana até o consumidor.

        A lista é ordenada por `dist` em ordem crescente.
    """
    candidates: List[Tuple[Node, float]] = []
    for ds in ds_nodes:
        dist = _euclidean_distance(consumer, ds)
        candidates.append((ds, dist))

    candidates.sort(key=lambda t: t[1])
    return candidates


def _select_primary_and_secondary_ds(
    consumer: Node,
    ds_nodes: List[Node],
    max_lv_length: float | None,
) -> Tuple[Optional[Tuple[Node, float]], Optional[Tuple[Node, float]]]:
    """
    Seleciona uma subestação de distribuição primária e, se possível,
    uma secundária para um consumidor.

    A lógica utilizada é:

    1. Calcula-se a lista de subestações de distribuição candidatas
       (ordenadas por distância crescente).
    2. A subestação mais próxima é escolhida como primária, desde que
       respeite o limite `max_lv_length` (se definido).
    3. A subestação secundária é escolhida como a próxima candidata
       distinta da primária cujo comprimento também esteja dentro de um
       limite moderado:
       - se `max_lv_length` for definido, utiliza-se um fator de folga,
         por exemplo 1.5 * `max_lv_length`;
       - se não for definido, a segunda candidata é aceita sem teste
         adicional.

    Parâmetros:
        consumer:
            Nó consumidor (`CONSUMER_POINT`) para o qual se deseja
            selecionar subestações.
        ds_nodes:
            Lista de subestações de distribuição disponíveis.
        max_lv_length:
            Comprimento máximo desejado para conexões de baixa tensão.
            Se `None`, não é aplicada restrição de comprimento.

    Retorno:
        Tupla `(primary, secondary)` onde:
        - `primary` é uma tupla `(ds, dist)` para a subestação primária,
          ou `None` se nenhuma subestação atender ao limite.
        - `secondary` é uma tupla `(ds, dist)` para a subestação
          secundária, ou `None` se não houver candidata adequada.

        Em situações de rede muito esparsa ou de limites de comprimento
        muito restritos, é possível que apenas a primária exista, ou que
        nenhuma conexão seja criada.
    """
    candidates = _find_ds_candidates_for_consumer(consumer, ds_nodes)
    if not candidates:
        return None, None

    primary: Optional[Tuple[Node, float]] = None
    secondary: Optional[Tuple[Node, float]] = None

    # Seleciona a primária
    for ds, dist in candidates:
        if max_lv_length is not None and dist > max_lv_length:
            # Muito distante para uma ligação primária
            continue
        primary = (ds, dist)
        break

    if primary is None:
        # Nenhuma DS atende ao limite primário
        return None, None

    # Seleciona a secundária com uma folga maior
    if max_lv_length is not None:
        max_secondary = 1.5 * max_lv_length
    else:
        max_secondary = None

    primary_ds = primary[0]
    for ds, dist in candidates:
        if ds.id == primary_ds.id:
            continue
        if max_secondary is not None and dist > max_secondary:
            continue
        secondary = (ds, dist)
        break

    return primary, secondary


def build_lv_network(
    config: SimulationConfig,
    graph: PowerGridGraph,
    clusters: List[ClusterInfo],
) -> None:
    """
    Constrói a rede de baixa tensão (LV) conectando subestações de
    distribuição a pontos consumidores.

    Esta etapa cria as ligações em baixa tensão responsáveis por levar
    energia das subestações de distribuição até os consumidores
    agregados. A lógica geral é:

    1. Selecionar todos os nós do tipo `DISTRIBUTION_SUBSTATION` (DS)
       e todos os nós do tipo `CONSUMER_POINT` (consumidores).
    2. Para cada consumidor:
       - escolher uma subestação primária (a DS mais próxima que
         respeite o limite `max_lv_segment_length`, se houver);
       - tentar escolher também uma subestação secundária (DS distinta
         da primária, próxima o suficiente, com folga moderada sobre o
         mesmo limite), com o objetivo de fornecer redundância local.
    3. Para cada ligação primária, criar uma aresta do tipo
       `LV_DISTRIBUTION_SEGMENT` com identificador prefixado por
       "LV_P_".
    4. Para cada ligação secundária, criar uma aresta análoga com
       prefixo "LV_S_".

    O parâmetro `max_lv_segment_length` em `SimulationConfig` é
    utilizado como limite de comprimento desejado para as conexões
    primárias. Para as conexões secundárias, é permitida uma folga
    (por exemplo, até 1.5 vezes esse limite), o que aumenta a chance de
    redundância sem criar ligações extremamente longas.

    Em regiões muito esparsas ou com limites muito restritos, alguns
    consumidores podem ficar apenas com uma conexão (primária) ou, em
    casos extremos, sem conexão alguma, se nenhuma subestação estiver ao
    alcance. Essa situação pode ser tratada posteriormente por etapas de
    robustez ou ajustes de parâmetros.

    Parâmetros:
        config:
            Instância de `SimulationConfig` contendo, entre outros, o
            parâmetro `max_lv_segment_length`.
        graph:
            Grafo físico `PowerGridGraph` contendo os nós já gerados e a
            malha de transmissão e média tensão.
        clusters:
            Lista de `ClusterInfo` que descreve os clusters de carga.
            Nesta etapa, a informação de cluster é utilizada
            principalmente indiretamente, através do campo `cluster_id`
            dos nós, gerado na etapa de criação de nós.
    """
    ds_nodes = _get_nodes_by_type(graph, NodeType.DISTRIBUTION_SUBSTATION)
    consumer_nodes = _get_nodes_by_type(graph, NodeType.CONSUMER_POINT)

    if not ds_nodes or not consumer_nodes:
        # Nada a fazer se não houver DS ou consumidores
        return

    max_lv_length = config.max_lv_segment_length
    edge_index_primary = 0
    edge_index_secondary = 0

    for consumer in consumer_nodes:
        primary, secondary = _select_primary_and_secondary_ds(
            consumer=consumer,
            ds_nodes=ds_nodes,
            max_lv_length=max_lv_length,
        )

        # Ligação primária
        if primary is not None:
            ds_p, dist_p = primary
            edge_id = f"LV_P_{edge_index_primary}"
            edge = Edge(
                id=edge_id,
                edge_type=EdgeType.LV_DISTRIBUTION_SEGMENT,
                from_node_id=consumer.id,
                to_node_id=ds_p.id,
                length=dist_p,
            )
            graph.add_edge(edge)
            edge_index_primary += 1

        # Ligação secundária (redundância)
        if secondary is not None:
            ds_s, dist_s = secondary
            edge_id = f"LV_S_{edge_index_secondary}"
            edge = Edge(
                id=edge_id,
                edge_type=EdgeType.LV_DISTRIBUTION_SEGMENT,
                from_node_id=consumer.id,
                to_node_id=ds_s.id,
                length=dist_s,
            )
            graph.add_edge(edge)
            edge_index_secondary += 1


__all__: Sequence[str] = ["build_lv_network"]
