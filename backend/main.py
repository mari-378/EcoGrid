from __future__ import annotations

import argparse

from core.graph_core import PowerGridGraph
from config import SimulationConfig as ConfigClass  # ajuste conforme a localização real
from io_utils.graph_export import export_graph_to_files

from planning.node_generation import generate_nodes
from planning.transmission_backbone import build_transmission_backbone
from planning.mv_network import build_mv_network
from planning.lv_network import build_lv_network
from planning.robustness import apply_robustness_reinforcements


def build_physical_graph(config: SimulationConfig) -> PowerGridGraph:
    """
    Constrói o grafo físico completo da rede de distribuição de energia.

    Esta função integra todas as etapas de geração física:

        1. Geração de nós (usinas, subestações de transmissão,
           subestações de distribuição, consumidores) e clusters
           associados.
        2. Construção do backbone de transmissão em alta tensão,
           conectando usinas a subestações de transmissão.
        3. Construção da rede de média tensão, conectando subestações
           de distribuição a subestações de transmissão e criando
           malha entre subestações de distribuição.
        4. Construção da rede de baixa tensão, conectando consumidores
           a subestações de distribuição com redundância primária e
           secundária quando possível.
        5. Aplicação de reforços de robustez, adicionando arestas
           suplementares em transmissão e média tensão para reduzir
           vulnerabilidades da topologia.

    Parâmetros:
        config:
            Instância de `SimulationConfig` com os parâmetros
            numéricos e geométricos de geração da rede, incluindo
            dimensões da área, número de clusters, número de nós por
            tipo e comprimentos máximos dos segmentos em cada nível
            de tensão.

    Retorno:
        Instância de `PowerGridGraph` preenchida com todos os nós e
        arestas gerados pelas pipelines físicas.
    """
    graph = PowerGridGraph()

    # 1) Geração de nós e clusters
    clusters = generate_nodes(config=config, graph=graph)

    # 2) Backbone de transmissão (alta tensão)
    build_transmission_backbone(config=config, graph=graph)

    # 3) Rede de média tensão (TS <-> DS, DS <-> DS)
    build_mv_network(config=config, graph=graph, clusters=clusters)

    # 4) Rede de baixa tensão (consumidores <-> DS)
    build_lv_network(config=config, graph=graph, clusters=clusters)

    # 5) Reforços de robustez (arestas extras em HT e MT)
    apply_robustness_reinforcements(config=config, graph=graph)

    return graph


def parse_args() -> argparse.Namespace:
    """
    Analisa argumentos de linha de comando para controlar a geração
    da rede física.

    Argumentos suportados:
        - --num-clusters:
            Número de clusters/regiões de carga a serem gerados.
        - --consumers-per-cluster:
            Número aproximado de consumidores por cluster.
        - --seed:
            Semente opcional para geração aleatória.
        - --nodes-path:
            Caminho de saída para o arquivo de nós (sem necessidade de
            extensão; por padrão, "out/nodes").
        - --edges-path:
            Caminho de saída para o arquivo de arestas (sem necessidade
            de extensão; por padrão, "out/edges").
    """
    parser = argparse.ArgumentParser(
        description="Geração de grafo de rede de distribuição de energia.",
    )

    parser.add_argument(
        "--num-clusters",
        type=int,
        default=3,
        help="Número de clusters/regiões urbanas na simulação (padrão: 3).",
    )

    parser.add_argument(
        "--consumers-per-cluster",
        type=int,
        default=50,
        help="Número aproximado de consumidores por cluster (padrão: 50).",
    )

    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help="Semente opcional para geração aleatória (padrão: None).",
    )

    parser.add_argument(
        "--nodes-path",
        type=str,
        default="out/nodes",
        help='Caminho do arquivo de saída de nós (padrão: "out/nodes").',
    )

    parser.add_argument(
        "--edges-path",
        type=str,
        default="out/edges",
        help='Caminho do arquivo de saída de arestas (padrão: "out/edges").',
    )

    return parser.parse_args()


def main() -> None:
    """
    Função principal da aplicação em modo CLI.

    Fluxo:

        1. Lê os argumentos de linha de comando com `parse_args`.
        2. Cria uma instância de `SimulationConfig` com valores padrão.
        3. Sobrescreve, na configuração, os parâmetros informados via
           linha de comando (semente, número de clusters, número de
           consumidores por cluster).
        4. Constrói o grafo físico chamando `build_physical_graph`.
        5. Exporta nós e arestas para os caminhos especificados por
           `--nodes-path` e `--edges-path`.
    """
    args = parse_args()

    # Cria a configuração base da simulação.
    sim_config = ConfigClass()

    # Aplica parâmetros vindos da linha de comando.
    if args.seed is not None:
        sim_config.random_seed = args.seed

    sim_config.num_clusters = args.num_clusters
    sim_config.consumers_per_cluster = args.consumers_per_cluster

    # Constrói o grafo físico completo.
    graph = build_physical_graph(config=sim_config)

    # Exporta para arquivos (sem necessidade de extensão).
    export_graph_to_files(
        graph=graph,
        nodes_path=args.nodes_path,
        edges_path=args.edges_path,
    )


if __name__ == "__main__":
    main()
