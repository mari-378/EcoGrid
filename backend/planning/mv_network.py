from __future__ import annotations

import math
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

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


def _build_mst(nodes: List[Node], max_edge_length: float | None) -> List[Tuple[Node, Node, float]]:
    """
    Constrói uma árvore geradora mínima (MST) sobre um conjunto de nós.

    A MST é construída usando uma variação simples do algoritmo de Prim.
    O peso de cada aresta é a distância euclidiana entre os nós. Se
    `max_edge_length` for diferente de `None`, arestas com comprimento
    superior ao limite são ignoradas, o que pode impedir a conexão de
    todos os nós se o limite for muito restritivo.

    Parâmetros:
        nodes:
            Lista de nós a serem conectados pela MST. Se a lista tiver
            menos de dois nós, nenhuma aresta será gerada.
        max_edge_length:
            Comprimento máximo permitido para as arestas da MST. Se
            for `None`, nenhuma restrição adicional é aplicada.

    Retorno:
        Lista de tuplas `(u, v, dist)` representando as arestas da MST,
        onde `u` e `v` são nós e `dist` é a distância euclidiana entre
        eles. A lista pode ser vazia se não for possível conectar os nós
        dentro das restrições impostas.
    """
    n = len(nodes)
    if n < 2:
        return []

    in_tree = [False] * n
    min_dist = [math.inf] * n
    parent: List[int | None] = [None] * n

    # Começa pelo nó 0
    min_dist[0] = 0.0

    for _ in range(n):
        u = -1
        best = math.inf
        for i in range(n):
            if not in_tree[i] and min_dist[i] < best:
                best = min_dist[i]
                u = i

        if u == -1:
            break  # não há mais nós alcançáveis sob as restrições

        in_tree[u] = True

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
            continue
        u = p
        dist = _euclidean_distance(nodes[u], nodes[v])
        mst_edges.append((nodes[u], nodes[v], dist))

    return mst_edges


def _connect_ds_to_nearest_ts(
    config: SimulationConfig,
    graph: PowerGridGraph,
    ds_nodes: List[Node],
    ts_nodes: List[Node],
    start_edge_index: int,
) -> int:
    """
    Conecta cada subestação de distribuição à subestação de transmissão mais próxima.

    Para cada nó do tipo `DISTRIBUTION_SUBSTATION`, esta função busca a
    subestação de transmissão (`TRANSMISSION_SUBSTATION`) mais próxima
    em termos de distância euclidiana e cria uma aresta de média tensão
    (`MV_DISTRIBUTION_SEGMENT`) entre elas.

    O parâmetro `max_mv_segment_length` de `SimulationConfig` pode ser
    utilizado como limite máximo de comprimento para essas conexões.
    Se a distância até a TS mais próxima exceder o limite, a conexão
    correspondente é omitida.

    Parâmetros:
        config:
            Instância de `SimulationConfig` contendo, entre outros, o
            parâmetro `max_mv_segment_length`.
        graph:
            Grafo físico onde as arestas serão inseridas.
        ds_nodes:
            Lista de nós do tipo `DISTRIBUTION_SUBSTATION` a serem ligados
            a alguma subestação de transmissão.
        ts_nodes:
            Lista de nós do tipo `TRANSMISSION_SUBSTATION` disponíveis
            para conexão.
        start_edge_index:
            Índice inicial usado para compor os identificadores das
            arestas criadas. O valor retornado será o próximo índice
            livre após as inserções.

    Retorno:
        Próximo índice de aresta livre após a criação das conexões.
    """
    if not ds_nodes or not ts_nodes:
        return start_edge_index

    max_len = config.max_mv_segment_length
    edge_index = start_edge_index

    for ds in ds_nodes:
        best_ts: Optional[Node] = None
        best_dist = math.inf

        for ts in ts_nodes:
            dist = _euclidean_distance(ds, ts)
            if dist < best_dist:
                best_dist = dist
                best_ts = ts

        if best_ts is None:
            continue

        if max_len is not None and best_dist > max_len:
            # Distância excessiva, não conecta este DS
            continue

        edge_id = f"MV_P_{edge_index}"
        edge = Edge(
            id=edge_id,
            edge_type=EdgeType.MV_DISTRIBUTION_SEGMENT,
            from_node_id=ds.id,
            to_node_id=best_ts.id,
            length=best_dist,
        )
        graph.add_edge(edge)
        edge_index += 1

    return edge_index


def _build_intra_cluster_mesh(
    config: SimulationConfig,
    graph: PowerGridGraph,
    clusters: List[ClusterInfo],
    ds_nodes: List[Node],
    start_edge_index: int,
) -> int:
    """
    Cria uma malha de média tensão entre subestações de distribuição
    dentro de cada cluster.

    Para cada cluster, são selecionadas as subestações de distribuição
    cujo `cluster_id` coincide com o identificador do cluster. Em
    seguida, constrói-se uma árvore geradora mínima (MST) conectando
    essas subestações com arestas do tipo `MV_DISTRIBUTION_SEGMENT`.

    O parâmetro `max_mv_segment_length` de `SimulationConfig` é usado
    como limite máximo para o comprimento das arestas, de forma
    semelhante à MST de transmissão. A malha intra-cluster aumenta a
    redundância local e a conectividade em média tensão.

    Parâmetros:
        config:
            Instância de `SimulationConfig` com `max_mv_segment_length`.
        graph:
            Grafo físico onde as novas arestas serão inseridas.
        clusters:
            Lista de `ClusterInfo` que define os agrupamentos de carga.
        ds_nodes:
            Lista de todas as subestações de distribuição existentes no
            grafo.
        start_edge_index:
            Índice inicial para a numeração das arestas criadas.

    Retorno:
        Próximo índice de aresta livre após a criação das conexões
        intra-cluster.
    """
    max_len = config.max_mv_segment_length
    edge_index = start_edge_index

    # Agrupa DS por cluster_id
    ds_by_cluster: Dict[int, List[Node]] = {}
    for ds in ds_nodes:
        if ds.cluster_id is None:
            continue
        ds_by_cluster.setdefault(ds.cluster_id, []).append(ds)

    for cluster in clusters:
        cluster_ds = ds_by_cluster.get(cluster.id, [])
        if len(cluster_ds) < 2:
            continue

        mst_edges = _build_mst(cluster_ds, max_edge_length=max_len)
        for u, v, dist in mst_edges:
            edge_id = f"MV_D_{edge_index}"
            edge = Edge(
                id=edge_id,
                edge_type=EdgeType.MV_DISTRIBUTION_SEGMENT,
                from_node_id=u.id,
                to_node_id=v.id,
                length=dist,
            )
            graph.add_edge(edge)
            edge_index += 1

    return edge_index


def _build_simple_intercluster_links(
    config: SimulationConfig,
    graph: PowerGridGraph,
    clusters: List[ClusterInfo],
    ds_nodes: List[Node],
    start_edge_index: int,
) -> int:
    """
    Cria algumas conexões de média tensão entre subestações de distribuição
    de clusters diferentes.

    O objetivo desta etapa é evitar que cada cluster fique totalmente
    isolado em termos de média tensão. Para isso, para cada par de
    clusters, esta função:

    - encontra uma subestação de distribuição em cada cluster;
    - escolhe o par de DS (um de cada cluster) com menor distância;
    - cria uma aresta `MV_DISTRIBUTION_SEGMENT` conectando esse par,
      desde que a distância não ultrapasse um múltiplo moderado de
      `max_mv_segment_length`.

    Esta heurística é simples e não garante uma conectividade ótima
    entre clusters, mas introduz caminhos alternativos em nível de
    distribuição que podem ser explorados por rotinas de robustez
    posteriores.

    Parâmetros:
        config:
            Instância de `SimulationConfig` com `max_mv_segment_length`.
        graph:
            Grafo físico onde as arestas serão inseridas.
        clusters:
            Lista de `ClusterInfo` que define os clusters de carga.
        ds_nodes:
            Lista de subestações de distribuição existentes no grafo.
        start_edge_index:
            Índice inicial para numeração das arestas criadas.

    Retorno:
        Próximo índice de aresta livre após a criação das conexões
        inter-cluster.
    """
    max_len = config.max_mv_segment_length
    if max_len is None:
        # Se não houver limite definido, utiliza-se mesmo assim a distância
        # mínima encontrada, apenas como reforço simples.
        max_allowed = None
    else:
        # Permite conexões um pouco maiores que as intra-cluster
        max_allowed = 1.5 * max_len

    edge_index = start_edge_index

    # Mapa cluster_id -> DS
    ds_by_cluster: Dict[int, List[Node]] = {}
    for ds in ds_nodes:
        if ds.cluster_id is None:
            continue
        ds_by_cluster.setdefault(ds.cluster_id, []).append(ds)

    num_clusters = len(clusters)
    for i in range(num_clusters):
        for j in range(i + 1, num_clusters):
            ci = clusters[i]
            cj = clusters[j]

            ds_i = ds_by_cluster.get(ci.id, [])
            ds_j = ds_by_cluster.get(cj.id, [])
            if not ds_i or not ds_j:
                continue

            best_pair: Optional[Tuple[Node, Node]] = None
            best_dist = math.inf

            for a in ds_i:
                for b in ds_j:
                    dist = _euclidean_distance(a, b)
                    if dist < best_dist:
                        best_dist = dist
                        best_pair = (a, b)

            if best_pair is None:
                continue

            if max_allowed is not None and best_dist > max_allowed:
                # Par mais próximo ainda assim muito distante; ignora
                continue

            u, v = best_pair
            edge_id = f"MV_IC_{edge_index}"
            edge = Edge(
                id=edge_id,
                edge_type=EdgeType.MV_DISTRIBUTION_SEGMENT,
                from_node_id=u.id,
                to_node_id=v.id,
                length=best_dist,
            )
            graph.add_edge(edge)
            edge_index += 1

    return edge_index


def build_mv_network(
    config: SimulationConfig,
    graph: PowerGridGraph,
    clusters: List[ClusterInfo],
) -> None:
    """
    Constrói a rede de média tensão (MV) sobre o grafo físico.

    Esta função executa a etapa de planejamento em média tensão,
    conectando subestações de distribuição a subestações de transmissão
    e formando malhas em nível de distribuição. O processo é dividido em
    três partes principais:

    1. Conexões DS -> TS (alimentação primária em MV):
       - Cada subestação de distribuição é ligada à subestação de
         transmissão mais próxima, respeitando opcionalmente o limite
         `max_mv_segment_length`. As arestas geradas recebem o prefixo
         "MV_P_" e tipo `MV_DISTRIBUTION_SEGMENT`.

    2. Malha intra-cluster DS -> DS:
       - Para cada cluster, cria-se uma árvore geradora mínima (MST)
         entre as subestações de distribuição pertencentes ao cluster.
         As arestas geradas recebem o prefixo "MV_D_" e tipo
         `MV_DISTRIBUTION_SEGMENT`.

    3. Ligações simples inter-cluster DS -> DS:
       - Para cada par de clusters, é criada uma conexão entre as
         subestações de distribuição mais próximas, desde que a
         distância não ultrapasse um múltiplo moderado do limite
         `max_mv_segment_length`. As arestas geradas recebem o prefixo
         "MV_IC_" e tipo `MV_DISTRIBUTION_SEGMENT`.

    Esta malha em média tensão aumenta a conectividade e prepara a rede
    para etapas posteriores de robustez e para a construção da camada de
    baixa tensão.

    Parâmetros:
        config:
            Instância de `SimulationConfig` com os parâmetros de média
            tensão.
        graph:
            Grafo físico `PowerGridGraph` contendo os nós já gerados
            (usinas, subestações de transmissão e distribuição,
            consumidores). As arestas de média tensão serão adicionadas
            a este grafo.
        clusters:
            Lista de `ClusterInfo` gerada na etapa de criação de nós,
            usada para identificar os clusters de subestações de
            distribuição e consumidores.
    """
    # Seleciona nós de interesse
    ds_nodes = _get_nodes_by_type(graph, NodeType.DISTRIBUTION_SUBSTATION)
    ts_nodes = _get_nodes_by_type(graph, NodeType.TRANSMISSION_SUBSTATION)

    edge_index = 0

    # 1. DS -> TS (alimentação primária)
    edge_index = _connect_ds_to_nearest_ts(
        config=config,
        graph=graph,
        ds_nodes=ds_nodes,
        ts_nodes=ts_nodes,
        start_edge_index=edge_index,
    )

    # 2. Malha intra-cluster DS -> DS
    edge_index = _build_intra_cluster_mesh(
        config=config,
        graph=graph,
        clusters=clusters,
        ds_nodes=ds_nodes,
        start_edge_index=edge_index,
    )

    # 3. Ligações simples inter-cluster DS -> DS
    _build_simple_intercluster_links(
        config=config,
        graph=graph,
        clusters=clusters,
        ds_nodes=ds_nodes,
        start_edge_index=edge_index,
    )


__all__: Sequence[str] = ["build_mv_network"]
