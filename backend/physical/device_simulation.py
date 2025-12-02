from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

from core.graph_core import PowerGridGraph
from core.models import Node, NodeType
from logic.logical_graph_service import LogicalGraphService
from physical.device_model import DeviceType, IoTDevice
from physical.device_catalog import DeviceTemplate, get_device_template
from physical.load_process import (
    DeviceLoadConfig,
    make_load_config_from_template,
    update_devices_current_power,
)


@dataclass
class DeviceSimulationState:
    """
    Agrupa os principais mapas utilizados na simulação de dispositivos.

    Esta estrutura reúne, em um único objeto, os mapeamentos necessários
    para associar dispositivos IoT aos nós consumidores do grafo físico
    e para calcular sua carga instantânea:

        - `devices_by_node`:
            Mapeia cada `node_id` para a lista de dispositivos conectados
            a esse nó (apenas nós do tipo consumidor, em geral).
        - `devices_by_id`:
            Mapeia `device_id` para a instância correspondente de
            `IoTDevice`, facilitando acesso direto a qualquer dispositivo.
        - `load_config_by_device_id`:
            Mapeia `device_id` para `DeviceLoadConfig`, isto é, para a
            configuração de perfil diário, ruído e limites relativos de
            carga daquele dispositivo.

    Ao utilizar esta estrutura, fica mais simples passar o contexto
    completo de simulação de dispositivos entre funções e camadas do
    sistema.
    """

    devices_by_node: Dict[str, List[IoTDevice]]
    devices_by_id: Dict[str, IoTDevice]
    load_config_by_device_id: Dict[str, DeviceLoadConfig]


def _create_devices_for_node(
    node_id: str,
    device_types: Iterable[DeviceType],
    id_prefix: Optional[str] = None,
    starting_index: int = 0,
) -> List[IoTDevice]:
    """
    Cria dispositivos IoT para um nó específico a partir de uma lista
    de tipos de dispositivo.

    Cada dispositivo recebe:
        - um identificador único construído a partir de:
            - um prefixo opcional;
            - o `node_id`;
            - um índice sequencial;
        - um nome padrão extraído do `DeviceTemplate`;
        - um tipo semântico (`DeviceType`);
        - uma carga média (`avg_power`) extraída do template.

    Parâmetros:
        node_id:
            Identificador do nó consumidor ao qual os dispositivos
            estarão conceitualmente associados.
        device_types:
            Sequência de tipos de dispositivo (`DeviceType`) a serem
            criados para este nó.
        id_prefix:
            Prefixo opcional a ser incluído no identificador do
            dispositivo. Se `None`, será omitido.
        starting_index:
            Índice inicial a ser usado na numeração dos dispositivos.
            Útil para garantir identificadores únicos mesmo quando a
            criação de dispositivos é feita em múltiplas etapas.

    Retorno:
        Lista de instâncias `IoTDevice` criadas para o nó informado.
    """
    devices: List[IoTDevice] = []
    index = starting_index

    for dtype in device_types:
        template: DeviceTemplate = get_device_template(dtype)

        if id_prefix is None or id_prefix == "":
            device_id = f"{node_id}#{index}"
        else:
            device_id = f"{id_prefix}_{node_id}#{index}"

        device = IoTDevice(
            id=device_id,
            name=template.default_name,
            device_type=dtype,
            avg_power=template.avg_power,
            current_power=None,
        )
        devices.append(device)
        index += 1

    return devices


def build_devices_for_consumers(
    graph: PowerGridGraph,
    node_device_types: Mapping[str, Sequence[DeviceType]],
    id_prefix: Optional[str] = "DEV",
) -> Tuple[Dict[str, List[IoTDevice]], Dict[str, IoTDevice]]:
    """
    Cria dispositivos IoT para nós consumidores a partir de um mapa
    node_id -> lista de tipos de dispositivos.

    Esta função não altera o grafo físico. Em vez disso, ela constrói
    duas estruturas:

        - `devices_by_node`:
            Mapeia cada `node_id` presente em `node_device_types` para
            uma lista de `IoTDevice` criados.
        - `devices_by_id`:
            Mapeia o `device_id` de cada dispositivo para a instância
            correspondente, facilitando acesso direto.

    Apenas nós existentes no grafo (`graph`) são considerados. Se um
    `node_id` estiver presente em `node_device_types` mas não existir
    no grafo, ele é ignorado.

    Parâmetros:
        graph:
            Instância de `PowerGridGraph` que contém os nós físicos.
        node_device_types:
            Mapeamento de `node_id` para uma sequência de `DeviceType`
            a serem criados naquele nó. Em geral, apenas nós do tipo
            `CONSUMER_POINT` deveriam aparecer neste mapa.
        id_prefix:
            Prefixo opcional para composição dos identificadores dos
            dispositivos. Útil para diferenciar cenários de simulação
            ou evitar colisões com outras fontes de dispositivos.

    Retorno:
        Tupla `(devices_by_node, devices_by_id)` com os dispositivos
        criados e organizados por nó e por identificador.
    """
    devices_by_node: Dict[str, List[IoTDevice]] = {}
    devices_by_id: Dict[str, IoTDevice] = {}

    for node_id, dtypes in node_device_types.items():
        node: Optional[Node] = graph.nodes.get(node_id)
        if node is None:
            # Node inexistente no grafo: ignora esta entrada.
            continue

        # Opcionalmente, podemos restringir a criação a nós consumidores.
        if node.node_type is not NodeType.CONSUMER_POINT:
            continue

        devices = _create_devices_for_node(
            node_id=node_id,
            device_types=dtypes,
            id_prefix=id_prefix,
            starting_index=0,
        )
        if not devices:
            continue

        devices_by_node[node_id] = devices
        for dev in devices:
            devices_by_id[dev.id] = dev

    return devices_by_node, devices_by_id


def build_load_configs_for_devices(
    devices_by_id: Mapping[str, IoTDevice],
    template_overrides: Optional[Mapping[DeviceType, DeviceTemplate]] = None,
) -> Dict[str, DeviceLoadConfig]:
    """
    Cria configurações de processo de carga para cada dispositivo
    conhecido, com base em templates por tipo de dispositivo.

    Para cada `IoTDevice` em `devices_by_id`, esta função:

        1. Localiza o `DeviceTemplate` adequado ao seu `device_type`.
           Caso `template_overrides` seja fornecido e contenha um
           template para esse tipo, este template é utilizado em
           preferência ao template padrão obtido por `get_device_template`.
        2. Constrói um `DeviceLoadConfig` a partir do template, via
           `make_load_config_from_template`.
        3. Armazena a configuração resultante em um mapa indexado por
           `device.id`.

    Parâmetros:
        devices_by_id:
            Mapeamento de `device_id` para `IoTDevice`. Tipicamente
            corresponde ao segundo valor retornado por
            `build_devices_for_consumers`.
        template_overrides:
            Mapeamento opcional de `DeviceType` para `DeviceTemplate`.
            Permite substituir templates padrão para tipos específicos
            de dispositivos, caso se deseje calibrar ou ajustar o
            comportamento da simulação.

    Retorno:
        Dicionário `load_config_by_device_id` que mapeia cada
        identificador de dispositivo (`device.id`) para a respectiva
        configuração de processo de carga (`DeviceLoadConfig`).
    """
    load_config_by_device_id: Dict[str, DeviceLoadConfig] = {}

    for device_id, device in devices_by_id.items():
        if template_overrides and device.device_type in template_overrides:
            template = template_overrides[device.device_type]
        else:
            template = get_device_template(device.device_type)

        cfg = make_load_config_from_template(template)
        load_config_by_device_id[device_id] = cfg

    return load_config_by_device_id


def build_device_simulation_state(
    graph: PowerGridGraph,
    node_device_types: Mapping[str, Sequence[DeviceType]],
    template_overrides: Optional[Mapping[DeviceType, DeviceTemplate]] = None,
    id_prefix: Optional[str] = "DEV",
) -> DeviceSimulationState:
    """
    Constrói o estado completo de simulação de dispositivos para um grafo.

    Esta função é um atalho conveniente que combina:

        1. Criação de dispositivos por nó consumidor, via
           `build_devices_for_consumers`;
        2. Criação das configurações de processo de carga para cada
           dispositivo, via `build_load_configs_for_devices`.

    O resultado é uma instância de `DeviceSimulationState` contendo:

        - `devices_by_node`;
        - `devices_by_id`;
        - `load_config_by_device_id`.

    Parâmetros:
        graph:
            Grafo físico `PowerGridGraph` que contém os nós consumidores.
        node_device_types:
            Mapeamento de `node_id` para sequência de `DeviceType`
            que devem ser criados naquele nó.
        template_overrides:
            Mapeamento opcional de `DeviceType` para `DeviceTemplate`,
            permitindo substituir a configuração padrão de determinados
            tipos de dispositivos.
        id_prefix:
            Prefixo opcional para os identificadores dos dispositivos.

    Retorno:
        Instância de `DeviceSimulationState` com todos os mapas
        necessários para simular a carga dos dispositivos ao longo
        do tempo.
    """
    devices_by_node, devices_by_id = build_devices_for_consumers(
        graph=graph,
        node_device_types=node_device_types,
        id_prefix=id_prefix,
    )
    load_config_by_device_id = build_load_configs_for_devices(
        devices_by_id=devices_by_id,
        template_overrides=template_overrides,
    )
    return DeviceSimulationState(
        devices_by_node=devices_by_node,
        devices_by_id=devices_by_id,
        load_config_by_device_id=load_config_by_device_id,
    )


def update_devices_and_nodes_loads(
    graph: PowerGridGraph,
    sim_state: DeviceSimulationState,
    t_seconds: float,
    service: Optional[LogicalGraphService] = None,
) -> None:
    """
    Atualiza a carga instantânea de todos os dispositivos e dos nós
    consumidores associados para um determinado instante de tempo.

    O procedimento é dividido em duas etapas:

        1. Atualização dos dispositivos:
           - Usa `update_devices_current_power` para calcular, para
             cada dispositivo em `sim_state.devices_by_id`, a carga
             instantânea no tempo `t_seconds`, com base na configuração
             em `sim_state.load_config_by_device_id`.

        2. Agregação por nó consumidor:
           - Para cada `node_id` em `sim_state.devices_by_node`, soma
             os valores de `current_power` de todos os dispositivos
             conectados àquele nó.
           - Atualiza o campo `current_load` do nó correspondente no
             grafo (`graph.nodes[node_id].current_load`) com a soma
             obtida.
           - Se `service` for fornecido, a atualização é propagada
             pela hierarquia lógica (Correção 1.2).

    Observações:
        - A função assume que todos os dispositivos presentes em
          `sim_state.devices_by_node` também estão presentes em
          `sim_state.devices_by_id`.
        - Unidades: assume-se que `current_power` está em kW e
          `current_load` do nó também (ou ambos em Watts). A
          conversão deve ser garantida na configuração do dispositivo.

    Parâmetros:
        graph:
            Grafo físico `PowerGridGraph` contendo os nós consumidores.
        sim_state:
            Estado de simulação de dispositivos (`DeviceSimulationState`)
            previamente construído.
        t_seconds:
            Instante de tempo em segundos para o qual se deseja calcular
            as cargas instantâneas.
        service:
            Serviço lógico opcional. Se presente, é usado para propagar
            a carga atualizada hierarquia acima (corrigindo drift).
    """
    # 1) Atualiza a carga de todos os dispositivos que possuem config.
    update_devices_current_power(
        devices=sim_state.devices_by_id,
        config_map=sim_state.load_config_by_device_id,
        t_seconds=t_seconds,
    )

    # 2) Agrega a carga dos dispositivos em cada nó consumidor.
    for node_id, devices in sim_state.devices_by_node.items():
        node = graph.nodes.get(node_id)
        if node is None:
            continue
        if node.node_type is not NodeType.CONSUMER_POINT:
            continue

        if service is not None:
            # Correção 1.2: Usa o serviço para propagar a carga
            service.update_load_after_device_change(
                consumer_id=node_id,
                node_devices=sim_state.devices_by_node,
            )
        else:
            # Fallback antigo: apenas soma localmente (sem propagação)
            total_power = 0.0
            for dev in devices:
                if dev.current_power is None:
                    continue
                total_power += dev.current_power
            node.current_load = total_power


__all__: Sequence[str] = [
    "DeviceSimulationState",
    "build_devices_for_consumers",
    "build_load_configs_for_devices",
    "build_device_simulation_state",
    "update_devices_and_nodes_loads",
]
