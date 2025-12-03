from __future__ import annotations

import math
import random
from typing import List, Sequence

from core.models import ClusterInfo, Node, NodeType
from core.graph_core import PowerGridGraph
from config import SimulationConfig


def _make_rng(config: SimulationConfig) -> random.Random:
    """
    Cria e retorna um gerador de números aleatórios a partir da configuração.

    Esta função encapsula a criação do gerador para garantir que toda a
    geração de nós use a mesma semente definida em `SimulationConfig`,
    permitindo reprodutibilidade da rede gerada.

    Parâmetros:
        config:
            Instância de `SimulationConfig` contendo a semente em
            `random_seed`.

    Retorno:
        Instância de `random.Random` inicializada com a semente fornecida.
    """
    return random.Random(config.random_seed)


def generate_clusters(config: SimulationConfig) -> List[ClusterInfo]:
    """
    Gera a lista de clusters de carga a partir da configuração.

    Cada cluster representa uma região aproximada (por exemplo, um bairro)
    onde serão posicionadas subestações de distribuição e consumidores.
    Os centros dos clusters são sorteados dentro da área simulada, e o
    raio e o número alvo de consumidores vêm de `SimulationConfig`.

    Parâmetros:
        config:
            Configuração da simulação com os parâmetros:
            - area_width, area_height
            - num_clusters
            - cluster_radius
            - consumers_per_cluster

    Retorno:
        Lista de instâncias de `ClusterInfo`, cada uma com:
        - id sequencial (0, 1, 2, ...),
        - center_x, center_y sorteados dentro da área,
        - radius = `cluster_radius`,
        - target_num_consumers = `consumers_per_cluster`.
    """
    rng = _make_rng(config)
    clusters: List[ClusterInfo] = []

    for cid in range(config.num_clusters):
        center_x = rng.uniform(0.0, config.area_width)
        center_y = rng.uniform(0.0, config.area_height)
        cluster = ClusterInfo(
            id=cid,
            center_x=center_x,
            center_y=center_y,
            radius=config.cluster_radius,
            target_num_consumers=config.consumers_per_cluster,
        )
        clusters.append(cluster)

    return clusters


def _sample_point_in_cluster(
    rng: random.Random,
    cluster: ClusterInfo,
) -> tuple[float, float]:
    """
    Sorteia uma posição cartesiana dentro de um cluster.

    A posição é sorteada em coordenadas polares (raio e ângulo) em torno
    do centro do cluster, com raio limitado por `cluster.radius`. O raio
    é sorteado de forma uniforme no intervalo [0, radius], o que produz
    uma distribuição simples de pontos ao redor do centro.

    Parâmetros:
        rng:
            Gerador de números aleatórios.
        cluster:
            Cluster onde o ponto será sorteado.

    Retorno:
        Tupla `(x, y)` representando a posição do ponto no plano
        cartesiano.
    """
    r = rng.uniform(0.0, cluster.radius)
    theta = rng.uniform(0.0, 2.0 * math.pi)
    x = cluster.center_x + r * math.cos(theta)
    y = cluster.center_y + r * math.sin(theta)
    return x, y


def _assign_nominal_voltage(
    node_type: NodeType,
    config: SimulationConfig,
) -> float | None:
    """
    Determina a tensão nominal de um nó com base em seu tipo.

    Esta função consulta os campos de tensão nominal em
    `SimulationConfig` e escolhe o valor correspondente ao `node_type`.
    Caso o campo apropriado na configuração seja `None`, o retorno
    também será `None`.

    Parâmetros:
        node_type:
            Tipo do nó, conforme `NodeType`.
        config:
            Instância de `SimulationConfig` contendo as tensões nominais.

    Retorno:
        Valor de tensão nominal em Volts (float) ou `None` se a
        configuração não definir tensão para aquele tipo de nó.
    """
    if node_type is NodeType.GENERATION_PLANT:
        return config.generation_nominal_voltage
    if node_type is NodeType.TRANSMISSION_SUBSTATION:
        return config.transmission_nominal_voltage
    if node_type is NodeType.DISTRIBUTION_SUBSTATION:
        return config.distribution_nominal_voltage
    if node_type is NodeType.CONSUMER_POINT:
        return config.consumer_nominal_voltage
    return None


def generate_nodes(
    config: SimulationConfig,
    graph: PowerGridGraph,
) -> List[ClusterInfo]:
    """
    Gera todos os nós físicos da rede e os insere no grafo.

    Esta função executa a etapa inicial de construção da rede elétrica
    sintética, criando:

    - usinas de geração (`GENERATION_PLANT`);
    - subestações de transmissão (`TRANSMISSION_SUBSTATION`);
    - subestações de distribuição (`DISTRIBUTION_SUBSTATION`);
    - pontos consumidores (`CONSUMER_POINT`).

    O posicionamento segue a seguinte lógica:

    - usinas e subestações de transmissão são posicionadas em toda a
      área simulada;
    - clusters de carga são gerados para definir regiões onde as
      subestações de distribuição e consumidores serão concentrados;
    - cada cluster recebe um número fixo de subestações de distribuição
      e um número alvo de consumidores, distribuídos ao redor do centro.

    Todos os nós são inseridos em `graph` por meio do método
    `graph.add_node`. Os campos `capacity` e `current_load` são
    inicialmente definidos como `None`, de forma que módulos futuros
    possam preenchê-los sem alterar a estrutura básica da rede.

    Parâmetros:
        config:
            Instância de `SimulationConfig` com os parâmetros de quantidade
            de nós, dimensões da área e tensões nominais.
        graph:
            Instância de `PowerGridGraph` onde os nós serão inseridos.

    Retorno:
        Lista de `ClusterInfo` gerados, que pode ser reutilizada pelas
        etapas posteriores de planejamento (transmissão, MV, LV).
    """
    rng = _make_rng(config)

    # ------------------------------------------------------------------
    # 1. Geração de clusters de carga
    # ------------------------------------------------------------------
    clusters = generate_clusters(config)

    # ------------------------------------------------------------------
    # 2. Geração de usinas de geração
    # ------------------------------------------------------------------
    for i in range(config.num_generation_plants):
        node_type = NodeType.GENERATION_PLANT
        x = rng.uniform(0.0, config.area_width)
        y = rng.uniform(0.0, config.area_height)
        nominal_voltage = _assign_nominal_voltage(node_type, config)

        node = Node(
            id=f"G_{i}",
            node_type=node_type,
            position_x=x,
            position_y=y,
            cluster_id=None,
            nominal_voltage=nominal_voltage,
            capacity=None,
            current_load=None,
        )
        graph.add_node(node)

    # ------------------------------------------------------------------
    # 3. Geração de subestações de transmissão
    # ------------------------------------------------------------------
    for i in range(config.num_transmission_substations):
        node_type = NodeType.TRANSMISSION_SUBSTATION
        x = rng.uniform(0.0, config.area_width)
        y = rng.uniform(0.0, config.area_height)
        nominal_voltage = _assign_nominal_voltage(node_type, config)

        node = Node(
            id=f"TS_{i}",
            node_type=node_type,
            position_x=x,
            position_y=y,
            cluster_id=None,
            nominal_voltage=nominal_voltage,
            capacity=None,
            current_load=None,
        )
        graph.add_node(node)

    # ------------------------------------------------------------------
    # 4. Geração de subestações de distribuição por cluster
    # ------------------------------------------------------------------
    ds_global_index = 0
    for cluster in clusters:
        for local_idx in range(config.distribution_substations_per_cluster):
            node_type = NodeType.DISTRIBUTION_SUBSTATION
            x, y = _sample_point_in_cluster(rng, cluster)
            nominal_voltage = _assign_nominal_voltage(node_type, config)

            node = Node(
                id=f"DS_{ds_global_index}",
                node_type=node_type,
                position_x=x,
                position_y=y,
                cluster_id=cluster.id,
                nominal_voltage=nominal_voltage,
                capacity=None,
                current_load=None,
            )
            graph.add_node(node)
            ds_global_index += 1

    # ------------------------------------------------------------------
    # 5. Geração de consumidores por cluster
    # ------------------------------------------------------------------
    consumer_global_index = 0
    for cluster in clusters:
        for local_idx in range(cluster.target_num_consumers):
            node_type = NodeType.CONSUMER_POINT
            x, y = _sample_point_in_cluster(rng, cluster)
            nominal_voltage = _assign_nominal_voltage(node_type, config)

            node = Node(
                id=f"C_{consumer_global_index}",
                node_type=node_type,
                position_x=x,
                position_y=y,
                cluster_id=cluster.id,
                nominal_voltage=nominal_voltage,
                capacity=None,
                current_load=None,
            )
            graph.add_node(node)
            consumer_global_index += 1

    return clusters


__all__: Sequence[str] = ["generate_clusters", "generate_nodes"]
