from __future__ import annotations

from typing import Dict, List, Optional, Set

from core.graph_core import PowerGridGraph
from core.models import Node, NodeType
from logic.bplus_index import BPlusIndex


def _compute_status(node: Node, unsupplied_ids: Set[str]) -> str:
    """
    Calcula o status lógico de um nó para exibição na árvore de UI.

    Regras:

        - Se o nó for do tipo CONSUMER_POINT e estiver presente em
          `unsupplied_ids`, o status é "UNSUPPLIED", independentemente
          de capacidade ou carga.

        - Se `capacity` for None ou `current_load` for None, o status é
          "NORMAL" (sem informação suficiente para avaliar nível de
          carregamento).

        - Caso contrário, utilizamos a razão:

                ratio = current_load / capacity

          com os limiares:

                ratio < 0.8      -> "NORMAL"
                0.8 <= ratio <= 1 -> "WARNING"
                ratio > 1        -> "OVERLOADED"

    Parâmetros:
        node:
            Nó físico da rede.
        unsupplied_ids:
            Conjunto de ids de nós consumidores considerados sem
            suprimento adequado.

    Retorno:
        String com o status: "NORMAL", "WARNING", "OVERLOADED"
        ou "UNSUPPLIED".
    """
    # Caso especial: consumidor marcado como não suprido.
    if node.node_type == NodeType.CONSUMER_POINT and node.id in unsupplied_ids:
        return "UNSUPPLIED"

    if node.capacity is None or node.current_load is None:
        return "NORMAL"

    try:
        capacity = float(node.capacity)
        load = float(node.current_load)
        if capacity <= 0.0:
            # Capacidade não positiva não é fisicamente razoável;
            # tratamos como caso normal sem avaliação de ratio.
            return "NORMAL"
        ratio = load / capacity
    except (TypeError, ValueError, ZeroDivisionError):
        # Em qualquer problema de conversão, tratamos como NORMAL.
        return "NORMAL"

    if ratio < 0.8:
        return "NORMAL"
    if ratio <= 1.0:
        return "WARNING"
    return "OVERLOADED"


def _build_tree_entry(
    node: Node,
    parent_id: Optional[str],
    unsupplied_ids: Set[str],
) -> Dict:
    """
    Constrói a entrada plana (flat) de um nó na árvore de UI.

    Campos retornados:

        - id:
            Identificador do nó.
        - parent_id:
            Identificador do pai lógico na árvore B+. Pode ser None
            para raízes (por exemplo, usinas).
        - node_type:
            Tipo de nó (string com o nome do enum NodeType).
        - position_x, position_y:
            Coordenadas cartesianas na área de simulação.
        - cluster_id:
            Identificador do cluster lógico ao qual o nó pertence,
            quando aplicável (caso contrário, None).
        - nominal_voltage:
            Tensão típica associada ao nó (pode ser None se não
            atribuída).
        - capacity:
            Capacidade máxima de carga do nó (pode ser None).
        - current_load:
            Carga agregada atual do nó (pode ser None).
        - status:
            String com o status lógico ("NORMAL", "WARNING",
            "OVERLOADED" ou "UNSUPPLIED").
    """
    return {
        "id": node.id,
        "parent_id": parent_id,
        "node_type": node.node_type.name,
        "position_x": node.position_x,
        "position_y": node.position_y,
        "cluster_id": node.cluster_id,
        "nominal_voltage": node.nominal_voltage,
        "capacity": node.capacity,
        "current_load": node.current_load,
        "status": _compute_status(node, unsupplied_ids),
    }


def build_full_ui_snapshot(
    graph: PowerGridGraph,
    index: BPlusIndex,
    unsupplied_ids: Set[str],
) -> Dict[str, List[Dict]]:
    """
    Gera o snapshot completo da árvore lógica para o front-end, em formato
    plano (flat) e em ordem de pré-ordem da árvore B+.

    O resultado segue exatamente o contrato combinado com o front:

        {
          "tree": [...],
          "logs": []
        }

    onde:

        - "tree" é uma lista de nós da árvore lógica, em pré-ordem,
          cada um com os campos:

              id, parent_id, node_type,
              position_x, position_y,
              cluster_id, nominal_voltage,
              capacity, current_load, status

        - "logs" é, por ora, uma lista vazia, reservada para mensagens
          de auditoria ou eventos relevantes em versões futuras.

    Estratégia de varredura:

        - A ordem é definida pelo índice lógico (`BPlusIndex`), usando
          um percurso em pré-ordem (raiz -> filhos em profundidade).
        - Para cada id retornado por `index.iter_preorder()`, buscamos
          o nó correspondente no grafo físico; se o nó não existir,
          ele é ignorado.
        - O campo `parent_id` é obtido via `index.get_parent(node_id)`.

    Parâmetros:
        graph:
            Grafo físico da rede.
        index:
            Índice B+ que armazena as relações pai-filho.
        unsupplied_ids:
            Conjunto de ids de nós consumidores marcados como sem
            suprimento adequado (impacta o campo "status").

    Retorno:
        Dicionário com as chaves:
            - "tree": lista de nós da árvore de UI.
            - "logs": lista (atualmente vazia) de mensagens de log.
    """
    tree_entries: List[Dict] = []

    # Percorre a árvore lógica em pré-ordem usando o índice B+.
    for node_id in index.iter_preorder():
        node: Optional[Node] = graph.get_node(node_id)
        if node is None:
            # Nó pode ter sido removido do grafo físico, mas ainda
            # constar no índice; ignoramos.
            continue

        parent_id = index.get_parent(node_id)
        entry = _build_tree_entry(
            node=node,
            parent_id=parent_id,
            unsupplied_ids=unsupplied_ids,
        )
        tree_entries.append(entry)

    # Estrutura final esperada pelo front-end.
    return {
        "tree": tree_entries,
        "logs": [],
    }


__all__ = [
    "build_full_ui_snapshot",
]
