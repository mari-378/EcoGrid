from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, MutableMapping, Sequence

from core.graph_core import PowerGridGraph
from core.models import Edge, Node
from logic.bplus_index import BPlusIndex
from logic.logical_graph_service import LogicalGraphService
from physical.device_model import IoTDevice
from api.logical_backend_api import (
    api_get_tree_snapshot,
    api_add_node_with_routing,
    api_remove_node,
    api_change_parent_with_routing,
    api_force_change_parent,
    api_set_node_capacity,
    api_set_device_average_load,
)


DEFAULT_OUT_PATH = Path("out.txt")


def _write_snapshot_to_file(
    snapshot: Dict[str, List[Dict]],
    out_path: str | Path = DEFAULT_OUT_PATH,
) -> None:
    """
    Escreve o snapshot da árvore lógica em um arquivo JSON.

    O snapshot é considerado dado válido para o front-end, não apenas
    um “dump” de debug. Por isso, o conteúdo é gravado em formato
    JSON bem formatado, com indentação e preservando caracteres
    Unicode.

    Parâmetros:
        snapshot:
            Dicionário no formato:

                {
                    "tree": [...],
                    "logs": []
                }

            exatamente como retornado pelas funções de API lógica.
        out_path:
            Caminho do arquivo de saída. Por padrão, "out.txt" na raiz
            do projeto. Se o diretório pai não existir, ele é criado.
    """
    path = Path(out_path)
    if path.parent != Path("."):
        path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", encoding="utf-8") as f:
        json.dump(snapshot, f, ensure_ascii=False, indent=2)


# ----------------------------------------------------------------------
# Wrappers “sandbox” para as funções da API lógica
# ----------------------------------------------------------------------


def sandbox_get_tree_snapshot(
    graph: PowerGridGraph,
    index: BPlusIndex,
    service: LogicalGraphService,
    out_path: str | Path = DEFAULT_OUT_PATH,
) -> Dict[str, List[Dict]]:
    """
    Wrapper de teste para `api_get_tree_snapshot`.

    Comportamento:
        1. Chama `api_get_tree_snapshot` para obter o snapshot atual
           da árvore lógica.
        2. Escreve o JSON resultante em `out_path`.
        3. Retorna o snapshot para uso adicional em testes.

    Parâmetros:
        graph, index, service:
            Mesmos parâmetros usados em `api_get_tree_snapshot`.
        out_path:
            Caminho do arquivo onde o snapshot será salvo.

    Retorno:
        Snapshot completo, idêntico ao retornado pela API original.
    """
    snapshot = api_get_tree_snapshot(graph=graph, index=index, service=service)
    _write_snapshot_to_file(snapshot, out_path)
    return snapshot


def sandbox_add_node_with_routing(
    graph: PowerGridGraph,
    index: BPlusIndex,
    service: LogicalGraphService,
    node: Node,
    edges: Sequence[Edge],
    out_path: str | Path = DEFAULT_OUT_PATH,
) -> Dict[str, List[Dict]]:
    """
    Wrapper de teste para `api_add_node_with_routing`.

    Aplica a inserção lógica e física de um nó, usando o algoritmo de
    roteamento para escolher o pai, e salva o snapshot resultante em
    arquivo.

    Parâmetros:
        graph, index, service, node, edges:
            Mesmos parâmetros de `api_add_node_with_routing`.
        out_path:
            Caminho do arquivo onde o snapshot será salvo.

    Retorno:
        Snapshot atualizado após a inserção do nó.
    """
    snapshot = api_add_node_with_routing(
        graph=graph,
        index=index,
        service=service,
        node=node,
        edges=edges,
    )
    _write_snapshot_to_file(snapshot, out_path)
    return snapshot


def sandbox_remove_node(
    graph: PowerGridGraph,
    index: BPlusIndex,
    service: LogicalGraphService,
    node_id: str,
    remove_from_graph: bool = True,
    out_path: str | Path = DEFAULT_OUT_PATH,
) -> Dict[str, List[Dict]]:
    """
    Wrapper de teste para `api_remove_node`.

    Remove um nó da rede lógica (e opcionalmente do grafo físico) e
    grava o snapshot resultante em arquivo.

    Parâmetros:
        graph, index, service, node_id, remove_from_graph:
            Mesmos parâmetros de `api_remove_node`.
        out_path:
            Caminho do arquivo onde o snapshot será salvo.

    Retorno:
        Snapshot atualizado após a remoção.
    """
    snapshot = api_remove_node(
        graph=graph,
        index=index,
        service=service,
        node_id=node_id,
        remove_from_graph=remove_from_graph,
    )
    _write_snapshot_to_file(snapshot, out_path)
    return snapshot


def sandbox_change_parent_with_routing(
    graph: PowerGridGraph,
    index: BPlusIndex,
    service: LogicalGraphService,
    node_id: str,
    out_path: str | Path = DEFAULT_OUT_PATH,
) -> Dict[str, List[Dict]]:
    """
    Wrapper de teste para `api_change_parent_with_routing`.

    Pede ao serviço lógico para recalcular o pai de um nó usando o
    algoritmo de roteamento e grava o snapshot resultante.

    Parâmetros:
        graph, index, service, node_id:
            Mesmos parâmetros de `api_change_parent_with_routing`.
        out_path:
            Caminho do arquivo onde o snapshot será salvo.

    Retorno:
        Snapshot atualizado após a tentativa de troca de pai.
    """
    snapshot = api_change_parent_with_routing(
        graph=graph,
        index=index,
        service=service,
        node_id=node_id,
    )
    _write_snapshot_to_file(snapshot, out_path)
    return snapshot


def sandbox_force_change_parent(
    graph: PowerGridGraph,
    index: BPlusIndex,
    service: LogicalGraphService,
    node_id: str,
    forced_parent_id: str,
    out_path: str | Path = DEFAULT_OUT_PATH,
) -> Dict[str, List[Dict]]:
    """
    Wrapper de teste para `api_force_change_parent`.

    Força a mudança de pai de um nó (respeitando as regras de
    capacidade e tipo que o serviço implementar) e grava o snapshot.

    Parâmetros:
        graph, index, service, node_id, forced_parent_id:
            Mesmos parâmetros de `api_force_change_parent`.
        out_path:
            Caminho do arquivo onde o snapshot será salvo.

    Retorno:
        Snapshot atualizado após a operação.
    """
    snapshot = api_force_change_parent(
        graph=graph,
        index=index,
        service=service,
        node_id=node_id,
        forced_parent_id=forced_parent_id,
    )
    _write_snapshot_to_file(snapshot, out_path)
    return snapshot


def sandbox_set_node_capacity(
    graph: PowerGridGraph,
    index: BPlusIndex,
    service: LogicalGraphService,
    node_id: str,
    new_capacity: float,
    out_path: str | Path = DEFAULT_OUT_PATH,
) -> Dict[str, List[Dict]]:
    """
    Wrapper de teste para `api_set_node_capacity`.

    Ajusta a capacidade máxima de um nó e grava o snapshot resultante.

    Parâmetros:
        graph, index, service, node_id, new_capacity:
            Mesmos parâmetros de `api_set_node_capacity`.
        out_path:
            Caminho do arquivo onde o snapshot será salvo.

    Retorno:
        Snapshot atualizado após o ajuste de capacidade.
    """
    snapshot = api_set_node_capacity(
        graph=graph,
        index=index,
        service=service,
        node_id=node_id,
        new_capacity=new_capacity,
    )
    _write_snapshot_to_file(snapshot, out_path)
    return snapshot


def sandbox_set_device_average_load(
    graph: PowerGridGraph,
    index: BPlusIndex,
    service: LogicalGraphService,
    node_devices: MutableMapping[str, List[IoTDevice]],
    consumer_id: str,
    device_id: str,
    new_avg_power: float,
    adjust_current_to_average: bool = True,
    out_path: str | Path = DEFAULT_OUT_PATH,
) -> Dict[str, List[Dict]]:
    """
    Wrapper de teste para `api_set_device_average_load`.

    Atualiza a potência média de um dispositivo IoT, recalcula a carga
    do consumidor e da cadeia de pais, e grava o snapshot em arquivo.

    Parâmetros:
        graph, index, service, node_devices, consumer_id, device_id,
        new_avg_power, adjust_current_to_average:
            Mesmos parâmetros de `api_set_device_average_load`.
        out_path:
            Caminho do arquivo onde o snapshot será salvo.

    Retorno:
        Snapshot atualizado após a alteração do dispositivo.
    """
    snapshot = api_set_device_average_load(
        graph=graph,
        index=index,
        service=service,
        node_devices=node_devices,
        consumer_id=consumer_id,
        device_id=device_id,
        new_avg_power=new_avg_power,
        adjust_current_to_average=adjust_current_to_average,
    )
    _write_snapshot_to_file(snapshot, out_path)
    return snapshot


__all__: Sequence[str] = [
    "sandbox_get_tree_snapshot",
    "sandbox_add_node_with_routing",
    "sandbox_remove_node",
    "sandbox_change_parent_with_routing",
    "sandbox_force_change_parent",
    "sandbox_set_node_capacity",
    "sandbox_set_device_average_load",
]
