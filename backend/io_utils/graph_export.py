import csv
import os
from typing import Dict, Any

from core.graph_core import PowerGridGraph
from core.models import Node, Edge


def _node_row(node: Node) -> Dict[str, Any]:
    """
    Constrói o dicionário correspondente a uma linha de saída de nó.

    Cada campo é serializado de forma simples para CSV, usando strings
    para valores opcionais vazios (por exemplo, cluster_id ou cargas
    ausentes).

    Campos exportados:
        - id: identificador único do nó.
        - node_type: tipo lógico do nó (GENERATION_PLANT, TRANSMISSION_SUBSTATION,
          DISTRIBUTION_SUBSTATION, CONSUMER_POINT).
        - position_x, position_y: coordenadas cartesianas na área de simulação.
        - cluster_id: identificador do cluster lógico ao qual o nó pertence,
          quando aplicável; vazio caso contrário.
        - nominal_voltage: tensão típica associada ao nó; vazio se não definida.
        - capacity: capacidade máxima de carga atribuída ao nó; vazio se não
          definida.
        - current_load: carga atual agregada no nó; vazio se não definida.
    """
    return {
        "id": node.id,
        "node_type": node.node_type.name,
        "position_x": node.position_x,
        "position_y": node.position_y,
        "cluster_id": "" if node.cluster_id is None else node.cluster_id,
        "nominal_voltage": "" if node.nominal_voltage is None else node.nominal_voltage,
        "capacity": "" if node.capacity is None else node.capacity,
        "current_load": "" if node.current_load is None else node.current_load,
    }


def _edge_row(edge: Edge) -> Dict[str, Any]:
    """
    Constrói o dicionário correspondente a uma linha de saída de aresta.

    Não são exportadas características físicas detalhadas do condutor
    (material, área de seção etc.). A perda de energia é modelada em
    outro módulo a partir do tipo da aresta e do comprimento.

    Campos exportados:
        - id: identificador único da aresta.
        - edge_type: tipo lógico da aresta (TRANSMISSION_SEGMENT,
          MV_DISTRIBUTION_SEGMENT, LV_DISTRIBUTION_SEGMENT).
        - from_node_id: identificador do nó de origem.
        - to_node_id: identificador do nó de destino.
        - length: comprimento geométrico do trecho no modelo de simulação.
    """
    return {
        "id": edge.id,
        "edge_type": edge.edge_type.name,
        "from_node_id": edge.from_node_id,
        "to_node_id": edge.to_node_id,
        "length": edge.length,
    }


def export_nodes_to_file(graph: PowerGridGraph, nodes_path: str) -> None:
    """
    Exporta todos os nós do grafo para um arquivo CSV.

    O caminho `nodes_path` pode ou não ter extensão; o módulo apenas
    garante que o diretório pai exista e grava o conteúdo no caminho
    informado.

    Formato de saída:
        id,node_type,position_x,position_y,cluster_id,nominal_voltage,capacity,current_load
    """
    directory = os.path.dirname(nodes_path)
    if directory:
        os.makedirs(directory, exist_ok=True)

    fieldnames = [
        "id",
        "node_type",
        "position_x",
        "position_y",
        "cluster_id",
        "nominal_voltage",
        "capacity",
        "current_load",
    ]

    with open(nodes_path, mode="w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for node in graph.iter_nodes():
            writer.writerow(_node_row(node))


def export_edges_to_file(graph: PowerGridGraph, edges_path: str) -> None:
    """
    Exporta todas as arestas do grafo para um arquivo CSV.

    O caminho `edges_path` pode ou não ter extensão; o módulo apenas
    garante que o diretório pai exista e grava o conteúdo no caminho
    informado.

    Formato de saída:
        id,edge_type,from_node_id,to_node_id,length

    Informações físicas mais detalhadas (material do condutor, seção,
    resistência etc.) são abstraídas em outros módulos e não fazem parte
    da exportação básica de topologia.
    """
    directory = os.path.dirname(edges_path)
    if directory:
        os.makedirs(directory, exist_ok=True)

    fieldnames = [
        "id",
        "edge_type",
        "from_node_id",
        "to_node_id",
        "length",
    ]

    with open(edges_path, mode="w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for edge in graph.iter_edges():
            writer.writerow(_edge_row(edge))


def export_graph_to_files(
    graph: PowerGridGraph,
    nodes_path: str,
    edges_path: str,
) -> None:
    """
    Exporta nós e arestas do grafo para dois arquivos CSV.

    Este é o ponto de saída padrão para integração com outras camadas:
    a camada física gera o grafo em memória, e este módulo converte a
    estrutura em dois arquivos tabulares:

        - `nodes_path`: tabela de nós.
        - `edges_path`: tabela de arestas.

    Cabe ao chamador definir os caminhos de saída, que podem não ter
    extensão (por exemplo, `out/nodes` e `out/edges`).
    """
    export_nodes_to_file(graph, nodes_path)
    export_edges_to_file(graph, edges_path)
