from __future__ import annotations

import csv
from typing import Optional

from core.graph_core import PowerGridGraph
from core.models import Edge, EdgeType, Node, NodeType


def load_graph_from_files(
    nodes_path: str,
    edges_path: str,
) -> PowerGridGraph:
    """
    Carrega um grafo físico de rede de energia a partir de dois arquivos
    tabulares: um de nós (`nodes_path`) e um de arestas (`edges_path`).

    Formato esperado dos arquivos:

        nodes (CSV sem extensão, mas com cabeçalho):
            id,node_type,position_x,position_y,cluster_id,nominal_voltage,capacity,current_load

        edges (CSV sem extensão, mas com cabeçalho):
            id,edge_type,from_node_id,to_node_id,length

    Parâmetros:
        nodes_path:
            Caminho para o arquivo de nós (ex.: "out/nodes").
        edges_path:
            Caminho para o arquivo de arestas (ex.: "out/edges").

    Retorno:
        Instância de `PowerGridGraph` preenchida com nós e arestas.
    """
    graph = PowerGridGraph()

    # ---------------------------
    # Carrega nós
    # ---------------------------
    with open(nodes_path, "r", encoding="utf-8") as f_nodes:
        reader = csv.DictReader(f_nodes)
        for row in reader:
            node = Node(
                id=row["id"],
                node_type=NodeType[row["node_type"]],
                position_x=float(row["position_x"]) if row["position_x"] else None,
                position_y=float(row["position_y"]) if row["position_y"] else None,
                cluster_id=int(row["cluster_id"]) if row["cluster_id"] else None,
                nominal_voltage=float(row["nominal_voltage"]) if row["nominal_voltage"] else None,
                capacity=float(row["capacity"]) if row.get("capacity") else None,
                current_load=float(row["current_load"]) if row.get("current_load") else None,
            )
            graph.add_node(node)

    # ---------------------------
    # Carrega arestas
    # ---------------------------
    with open(edges_path, "r", encoding="utf-8") as f_edges:
        reader = csv.DictReader(f_edges)
        for row in reader:
            edge = Edge(
                id=row["id"],
                edge_type=EdgeType[row["edge_type"]],
                from_node_id=row["from_node_id"],
                to_node_id=row["to_node_id"],
                length=float(row["length"]) if row["length"] else None,
            )
            graph.add_edge(edge)

    return graph
