from __future__ import annotations

import uuid
from typing import Dict, List, MutableMapping, Sequence

from core.graph_core import PowerGridGraph
from core.models import Edge, Node, NodeType
from logic.bplus_index import BPlusIndex
from logic.logical_graph_service import LogicalGraphService
from logic.ui_tree_snapshot import build_full_ui_snapshot
from physical.device_catalog import get_device_template
from physical.device_model import DeviceType, IoTDevice
from physical.device_simulation import DeviceSimulationState, _create_devices_for_node
from physical.load_process import make_load_config_from_template

def api_get_tree_snapshot(
    graph: PowerGridGraph,
    index: BPlusIndex,
    service: LogicalGraphService,
    sim_state: DeviceSimulationState,
) -> Dict[str, List[Dict]]:
    """
    Retorna o snapshot atual da árvore lógica para o front-end, sem
    aplicar nenhuma operação prévia na rede.

    Do ponto de vista do front, este endpoint não recebe parâmetros
    de negócio: ele apenas solicita o estado corrente da árvore. A
    função retorna a mesma estrutura utilizada pelas demais funções
    de API:

        {
            "tree": [...],
            "logs": []
        }

    Parâmetros:
        graph:
            Grafo físico da rede.
        index:
            Índice lógico B+ com as relações pai-filho.
        service:
            Serviço lógico que mantém o conjunto de consumidores sem
            energia (`unsupplied_consumers`), usado para marcar nós
            como "UNSUPPLIED" no snapshot.

    Retorno:
        Dicionário com as chaves "tree" e "logs", representando o
        estado atual da árvore lógica.
    """
    return build_full_ui_snapshot(
        graph=graph,
        index=index,
        unsupplied_ids=service.unsupplied_consumers,
        devices_by_node=sim_state.devices_by_node,
        logs=service.consume_logs(),
    )


def api_add_node_with_routing(
    graph: PowerGridGraph,
    index: BPlusIndex,
    service: LogicalGraphService,
    sim_state: DeviceSimulationState,
    node: Node,
    edges: Sequence[Edge],
) -> Dict[str, List[Dict]]:
    """
    Insere um novo nó na rede, conecta fisicamente via arestas fornecidas
    e determina o pai lógico usando o algoritmo de roteamento.

    Fluxo da operação:
        1. O nó é adicionado ao grafo físico junto com suas arestas
           incidentes, por meio de `LogicalGraphService.add_node_with_routing`.
        2. O serviço utiliza o A* (via módulo de roteamento) e o índice B+
           para escolher o melhor pai lógico compatível, respeitando
           capacidade e tipos de nó.
        3. Caso nenhum pai viável seja encontrado, o nó é marcado como
           “sem energia” e incluído em `unsupplied_consumers`.
        4. Ao final, é gerado um snapshot completo para o front-end.

    Retorno:
        Dicionário no formato esperado pelo front-end:

            {
                "tree": [...],
                "logs": []
            }

        Neste momento, a lista de logs é retornada vazia, mas o formato
        já está preparado para inclusão futura de mensagens.
    """
    service.add_node_with_routing(node=node, edges=edges)

    return build_full_ui_snapshot(
        graph=graph,
        index=index,
        unsupplied_ids=service.unsupplied_consumers,
        devices_by_node=sim_state.devices_by_node,
        logs=service.consume_logs(),
    )


def api_remove_node(
    graph: PowerGridGraph,
    index: BPlusIndex,
    service: LogicalGraphService,
    sim_state: DeviceSimulationState,
    node_id: str,
    remove_from_graph: bool = True,
) -> Dict[str, List[Dict]]:
    """
    Remove um nó da rede lógica (e opcionalmente do grafo físico) e
    retorna o snapshot atualizado.

    Política adotada:
        - Se o nó não existir:
            Nenhuma alteração é feita. Apenas o snapshot atual é retornado.

        - Se o nó for DISTRIBUTION_SUBSTATION ou TRANSMISSION_SUBSTATION:
            Utiliza `LogicalGraphService.remove_station_and_reattach_children`
            para:
                * remover a estação da hierarquia lógica;
                * tentar reatribuir os filhos a outras estações do mesmo
                  tipo, usando o algoritmo de roteamento;
                * remover a estação do grafo físico se `remove_from_graph`
                  for True.

        - Se o nó for CONSUMER_POINT:
            O nó é destacado e removido do índice B+ e, se
            `remove_from_graph` for True, também do grafo físico.

        - Se o nó for GENERATION_PLANT:
            O nó é removido da B+ e, opcionalmente, do grafo físico.
            Regras específicas de reatribuição de filhos podem ser
            definidas em versões futuras, se necessário.

    Parâmetros:
        graph:
            Grafo físico da rede.
        index:
            Índice lógico B+ com as relações pai-filho.
        service:
            Instância de `LogicalGraphService` coordenando as operações
            lógicas de alto nível.
        node_id:
            Identificador do nó a ser removido.
        remove_from_graph:
            Se True, o nó também é removido do grafo físico.

    Retorno:
        Snapshot no formato:

            {
                "tree": [...],
                "logs": []
            }
    """
    node = graph.get_node(node_id)
    if node is None:
        # Nó inexistente: apenas retorna snapshot atual.
        return build_full_ui_snapshot(
            graph=graph,
            index=index,
            unsupplied_ids=service.unsupplied_consumers,
            devices_by_node=sim_state.devices_by_node,
            logs=service.consume_logs(),
        )

    if node.node_type in (NodeType.DISTRIBUTION_SUBSTATION, NodeType.TRANSMISSION_SUBSTATION):
        service.remove_station_and_reattach_children(
            station_id=node_id,
        )
        if remove_from_graph:
            graph.remove_node(node_id)
    else:
        # Consumidor ou usina: remoção lógica simples.
        index.detach_node(node_id)
        index.remove_node(node_id)
        if remove_from_graph:
            graph.remove_node(node_id)

    # Limpa dispositivos associados se o nó foi removido
    if remove_from_graph:
        devices = sim_state.devices_by_node.pop(node_id, [])
        for dev in devices:
            sim_state.devices_by_id.pop(dev.id, None)
            sim_state.load_config_by_device_id.pop(dev.id, None)

    return build_full_ui_snapshot(
        graph=graph,
        index=index,
        unsupplied_ids=service.unsupplied_consumers,
        devices_by_node=sim_state.devices_by_node,
        logs=service.consume_logs(),
    )


def api_change_parent_with_routing(
    graph: PowerGridGraph,
    index: BPlusIndex,
    service: LogicalGraphService,
    sim_state: DeviceSimulationState,
    node_id: str,
) -> Dict[str, List[Dict]]:
    """
    Solicita mudança de pai lógico para um nó, utilizando o algoritmo
    de roteamento (A*) para escolher automaticamente o melhor pai.

    Fluxo:
        1. `LogicalGraphService.change_parent_with_routing` é chamado.
        2. O serviço:
            - encontra um novo pai compatível (tipo + capacidade);
            - atualiza o índice B+ com a nova relação pai-filho;
            - ajusta a lista de consumidores sem energia, se necessário.
        3. Ao final, é retornado o snapshot atualizado da árvore lógica.

    Observações:
        - Se nenhum pai viável for encontrado, o nó pode permanecer ou
          tornar-se um consumidor sem energia, refletido em
          `unsupplied_consumers`.
        - Logs detalhados sobre a alteração podem ser adicionados em
          camadas superiores no futuro.

    Retorno:
        Snapshot no formato:

            {
                "tree": [...],
                "logs": []
            }
    """
    service.change_parent_with_routing(child_id=node_id)

    return build_full_ui_snapshot(
        graph=graph,
        index=index,
        unsupplied_ids=service.unsupplied_consumers,
        devices_by_node=sim_state.devices_by_node,
        logs=service.consume_logs(),
    )


def api_force_change_parent(
    graph: PowerGridGraph,
    index: BPlusIndex,
    service: LogicalGraphService,
    sim_state: DeviceSimulationState,
    node_id: str,
    forced_parent_id: str,
) -> Dict[str, List[Dict]]:
    """
    Força a mudança de pai lógico de um nó para um pai específico,
    desde que a nova relação não cause sobrecarga de capacidade.

    Fluxo:
        1. `LogicalGraphService.force_change_parent` verifica:
            - se o tipo do pai é compatível com o tipo do filho;
            - se há capacidade disponível no pai para receber a carga
              adicional do filho;
            - se a nova relação não quebra regras estruturais básicas.
        2. Em caso de sucesso, o índice B+ é atualizado.
        3. Em caso de falha (por exemplo, falta de capacidade), nenhuma
           alteração é feita.
        4. O snapshot atualizado da árvore é retornado em ambos os casos.

    Parâmetros:
        node_id:
            Nó que terá o pai alterado.
        forced_parent_id:
            Novo pai desejado, caso a operação seja viável.

    Retorno:
        Snapshot no formato:

            {
                "tree": [...],
                "logs": []
            }
    """
    service.force_change_parent(
        child_id=node_id,
        new_parent_id=forced_parent_id,
    )

    return build_full_ui_snapshot(
        graph=graph,
        index=index,
        unsupplied_ids=service.unsupplied_consumers,
        devices_by_node=sim_state.devices_by_node,
        logs=service.consume_logs(),
    )


def api_set_node_capacity(
    graph: PowerGridGraph,
    index: BPlusIndex,
    service: LogicalGraphService,
    sim_state: DeviceSimulationState,
    node_id: str,
    new_capacity: float,
) -> Dict[str, List[Dict]]:
    """
    Ajusta a capacidade máxima de um nó e retorna o snapshot atualizado
    da árvore lógica.

    Uso típico:
        - Reconfiguração operacional de subestações ou usinas.
        - Estudos de cenários com diferentes capacidades de infraestrutura.

    A função delega para `LogicalGraphService.set_node_capacity` e não
    impõe regras adicionais (por exemplo, aceitar capacidade menor que
    a carga atual). Regras de validação podem ser incorporadas em
    camadas superiores conforme a necessidade.

    Parâmetros:
        node_id:
            Identificador do nó cuja capacidade será alterada.
        new_capacity:
            Nova capacidade máxima em unidades de carga/potência
            adotadas pela simulação.

    Retorno:
        Snapshot no formato:

            {
                "tree": [...],
                "logs": []
            }
    """
    service.set_node_capacity(node_id=node_id, new_capacity=new_capacity)

    return build_full_ui_snapshot(
        graph=graph,
        index=index,
        unsupplied_ids=service.unsupplied_consumers,
        devices_by_node=sim_state.devices_by_node,
        logs=service.consume_logs(),
    )


def api_force_overload(
    graph: PowerGridGraph,
    index: BPlusIndex,
    service: LogicalGraphService,
    sim_state: DeviceSimulationState,
    node_id: str,
    overload_percentage: float,
) -> Dict[str, List[Dict]]:
    """
    Força um estado de sobrecarga em um nó interno (não-dispositivo),
    reduzindo sua capacidade para um valor inferior à carga atual.

    Fluxo:
        1. Chama `service.force_overload(node_id, overload_percentage)`.
           - Se `current_load` for X e percent for P, nova capacidade
             será X / (1 + P).
           - Isso garante que carga > capacidade.
        2. Retorna o snapshot atualizado. O nó afetado deve aparecer
           com status "OVERLOADED" se a UI respeitar a relação
           carga/capacidade.

    Parâmetros:
        node_id:
            Identificador do nó alvo.
        overload_percentage:
            Percentual de sobrecarga desejado (ex: 0.2 para 20%).

    Retorno:
        Snapshot no formato:
            { "tree": [...], "logs": [] }
    """
    service.force_overload(node_id=node_id, overload_percentage=overload_percentage)

    return build_full_ui_snapshot(
        graph=graph,
        index=index,
        unsupplied_ids=service.unsupplied_consumers,
        devices_by_node=sim_state.devices_by_node,
        logs=service.consume_logs(),
    )


def api_set_device_average_load(
    graph: PowerGridGraph,
    index: BPlusIndex,
    service: LogicalGraphService,
    sim_state: DeviceSimulationState,
    consumer_id: str,
    device_id: str,
    new_avg_power: float,
    adjust_current_to_average: bool = True,
) -> Dict[str, List[Dict]]:
    """
    Ajusta a potência média de um dispositivo IoT associado a um nó
    consumidor e atualiza a carga da rede, retornando o snapshot da
    árvore lógica.

    Importante:
        - Apesar do nome da função mencionar "average load", internamente
          o modelo físico utiliza os campos `avg_power` e `current_power`
          em `IoTDevice`, para deixar claro que se trata de potência.

    Fluxo:
        1. Localiza o dispositivo em `node_devices[consumer_id]` pelo
           `device_id`.
        2. Atualiza `avg_power` para `new_avg_power`.
        3. Opcionalmente ajusta `current_power` para o mesmo valor, se
           `adjust_current_to_average` for True.
        4. Chama `service.update_load_after_device_change` para:
               - recalcular a carga do nó consumidor a partir de seus
                 dispositivos;
               - propagar a nova carga ao longo da cadeia de pais via
                 índice B+.
        5. Retorna o snapshot atualizado.

    Comportamento em casos de erro:
        - Se o consumidor não existir em `node_devices` ou se o
          `device_id` não for encontrado na lista, nenhuma alteração é
          feita e o snapshot atual é retornado.

    Parâmetros:
        graph:
            Grafo físico da rede.
        index:
            Índice lógico B+ com as relações pai-filho.
        service:
            Serviço lógico que coordena a atualização de cargas.
        node_devices:
            Mapa `consumer_id -> lista de IoTDevice` representando os
            dispositivos conectados a cada nó consumidor.
        consumer_id:
            Identificador do nó consumidor que possui o dispositivo.
        device_id:
            Identificador do dispositivo cuja potência média será
            ajustada.
        new_avg_power:
            Novo valor de potência média do dispositivo.
        adjust_current_to_average:
            Se True, define `current_power` do dispositivo para
            `new_avg_power` imediatamente após a alteração.

    Retorno:
        Snapshot no formato:

            {
                "tree": [...],
                "logs": []
            }
    """
    devices = sim_state.devices_by_node.get(consumer_id)
    if not devices:
        # Nenhum device para esse consumidor: retorna snapshot atual.
        return build_full_ui_snapshot(
            graph=graph,
            index=index,
            unsupplied_ids=service.unsupplied_consumers,
            devices_by_node=sim_state.devices_by_node,
            logs=service.consume_logs(),
        )

    target_device: IoTDevice | None = None
    for dev in devices:
        if dev.id == device_id:
            target_device = dev
            break

    if target_device is None:
        # Dispositivo não encontrado: retorna snapshot atual.
        return build_full_ui_snapshot(
            graph=graph,
            index=index,
            unsupplied_ids=service.unsupplied_consumers,
            devices_by_node=sim_state.devices_by_node,
            logs=service.consume_logs(),
        )

    # Atualiza potência média e, se desejado, a potência atual.
    target_device.avg_power = new_avg_power
    if adjust_current_to_average:
        target_device.current_power = new_avg_power

    # Recalcula carga do consumidor e propaga na árvore lógica.
    service.update_load_after_device_change(
        consumer_id=consumer_id,
        node_devices=sim_state.devices_by_node,
    )

    return build_full_ui_snapshot(
        graph=graph,
        index=index,
        unsupplied_ids=service.unsupplied_consumers,
        devices_by_node=sim_state.devices_by_node,
        logs=service.consume_logs(),
    )


def api_add_device(
    graph: PowerGridGraph,
    index: BPlusIndex,
    service: LogicalGraphService,
    sim_state: DeviceSimulationState,
    node_id: str,
    device_type: DeviceType,
    name: str = "Novo Dispositivo",
    avg_power: float | None = None,
) -> Dict[str, List[Dict]]:
    """
    Adiciona um novo dispositivo IoT a um nó consumidor.
    """
    # 1. Verifica se nó existe e é consumidor
    node = graph.get_node(node_id)
    if not node or node.node_type != NodeType.CONSUMER_POINT:
        return build_full_ui_snapshot(
            graph=graph,
            index=index,
            unsupplied_ids=service.unsupplied_consumers,
            devices_by_node=sim_state.devices_by_node,
            logs=service.consume_logs(),
        )

    # 2. Cria dispositivo
    new_id = f"DEV_{uuid.uuid4().hex[:8]}"

    template = get_device_template(device_type)

    # Se avg_power não foi informado, usa do template
    final_avg_power = avg_power if avg_power is not None else template.avg_power

    new_device = IoTDevice(
        id=new_id,
        name=name,
        device_type=device_type,
        avg_power=final_avg_power,
        current_power=final_avg_power # Inicializa com valor médio
    )

    # 3. Adiciona ao estado
    if node_id not in sim_state.devices_by_node:
        sim_state.devices_by_node[node_id] = []

    sim_state.devices_by_node[node_id].append(new_device)
    sim_state.devices_by_id[new_id] = new_device

    # Adiciona config de carga
    template = get_device_template(device_type)
    config = make_load_config_from_template(template)
    sim_state.load_config_by_device_id[new_id] = config

    # 4. Atualiza carga da rede
    service.log(f"Dispositivo '{name}' ({device_type.name}) adicionado ao consumidor {node_id}.")
    service.update_load_after_device_change(
        consumer_id=node_id,
        node_devices=sim_state.devices_by_node
    )

    return build_full_ui_snapshot(
        graph=graph,
        index=index,
        unsupplied_ids=service.unsupplied_consumers,
        devices_by_node=sim_state.devices_by_node,
        logs=service.consume_logs(),
    )


def api_remove_device(
    graph: PowerGridGraph,
    index: BPlusIndex,
    service: LogicalGraphService,
    sim_state: DeviceSimulationState,
    node_id: str,
    device_id: str,
) -> Dict[str, List[Dict]]:
    """
    Remove um dispositivo IoT de um nó consumidor.
    """
    # 1. Busca dispositivo
    devices = sim_state.devices_by_node.get(node_id)
    if not devices:
        return build_full_ui_snapshot(
            graph=graph,
            index=index,
            unsupplied_ids=service.unsupplied_consumers,
            devices_by_node=sim_state.devices_by_node,
            logs=service.consume_logs(),
        )

    target_idx = -1
    for i, dev in enumerate(devices):
        if dev.id == device_id:
            target_idx = i
            break

    if target_idx == -1:
        return build_full_ui_snapshot(
            graph=graph,
            index=index,
            unsupplied_ids=service.unsupplied_consumers,
            devices_by_node=sim_state.devices_by_node,
            logs=service.consume_logs(),
        )

    # 2. Remove
    devices.pop(target_idx)
    sim_state.devices_by_id.pop(device_id, None)
    sim_state.load_config_by_device_id.pop(device_id, None)

    # 3. Atualiza carga
    service.log(f"Dispositivo {device_id} removido do consumidor {node_id}.")
    service.update_load_after_device_change(
        consumer_id=node_id,
        node_devices=sim_state.devices_by_node
    )

    return build_full_ui_snapshot(
        graph=graph,
        index=index,
        unsupplied_ids=service.unsupplied_consumers,
        devices_by_node=sim_state.devices_by_node,
        logs=service.consume_logs(),
    )


__all__: Sequence[str] = [
    "api_add_node_with_routing",
    "api_remove_node",
    "api_change_parent_with_routing",
    "api_force_change_parent",
    "api_set_node_capacity",
    "api_force_overload",
    "api_set_device_average_load",
    "api_add_device",
    "api_remove_device",
    "api_get_tree_snapshot",
]
