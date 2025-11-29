from __future__ import annotations

from typing import Mapping, Sequence

from core.graph_core import PowerGridGraph
from core.models import Node, NodeType
from logic.bplus_index import BPlusIndex
from physical.device_model import IoTDevice


def recompute_consumer_load(
    consumer_id: str,
    node_devices: Mapping[str, Sequence[IoTDevice]],
    graph: PowerGridGraph,
) -> float:
    """
    Recalcula a carga atual (`current_load`) de um nó consumidor a partir
    da soma das potências instantâneas dos dispositivos conectados.

    Política adotada:

        - O nó é buscado no grafo físico por `consumer_id`.
        - Se o nó não existir ou não for do tipo `CONSUMER_POINT`,
          nenhuma alteração é feita e a função retorna 0.0.
        - Caso seja um consumidor:
            * Obtém-se a lista de dispositivos em `node_devices[consumer_id]`
              (ou lista vazia se não houver mapeamento).
            * Para cada dispositivo, lê-se o campo `current_power`.
              Valores `None` são considerados como 0.0.
            * A soma destas potências é atribuída a `node.current_load`.
        - O valor numérico atribuído a `node.current_load` é retornado.

    Esta função pressupõe que algum módulo de simulação (por exemplo,
    `physical.device_simulation.update_devices_and_nodes_loads`) já tenha
    atualizado o campo `current_power` dos dispositivos para o instante de
    tempo de interesse. Aqui apenas fazemos a agregação para o nó.

    Parâmetros:
        consumer_id:
            Identificador do nó consumidor cuja carga será recalculada.
        node_devices:
            Mapeamento de `node_id` para lista de `IoTDevice` conectados
            ao nó. Em cenários típicos, apenas nós do tipo
            `CONSUMER_POINT` possuem dispositivos associados.
        graph:
            Grafo físico `PowerGridGraph` contendo os nós da rede.

    Retorno:
        Valor numérico da carga atual atribuída ao nó consumidor após o
        recálculo. Em caso de nó inexistente ou de tipo incompatível,
        retorna 0.0.
    """
    node = graph.get_node(consumer_id)
    if node is None or node.node_type is not NodeType.CONSUMER_POINT:
        return 0.0

    devices = node_devices.get(consumer_id, [])
    total_power = 0.0

    for device in devices:
        # current_power representa a potência instantânea do dispositivo.
        if device.current_power is not None:
            total_power += float(device.current_power)

    node.current_load = total_power
    return total_power


def recompute_node_load_from_children(
    node_id: str,
    graph: PowerGridGraph,
    index: BPlusIndex,
) -> float:
    """
    Recalcula a carga atual (`current_load`) de um nó a partir das cargas
    de seus filhos lógicos diretos na B+.

    Política adotada:

        - Usa o índice lógico `BPlusIndex` para obter os ids dos filhos
          diretos de `node_id`.
        - Para cada filho:
            * Obtém o nó correspondente no grafo físico.
            * Lê o campo `child_node.current_load`. Valores `None` são
              tratados como 0.0.
        - A carga do nó identificado por `node_id` é definida como a soma
          das cargas de todos os filhos válidos.
        - Se o nó não existir no grafo físico, nenhuma alteração é feita
          e a função retorna 0.0.

    Esta função não faz distinção entre tipos de nó: ela apenas assume
    que a relação pai-filho já foi construída corretamente pela camada
    lógica (usinas, subestações e consumidores) e que o campo
    `current_load` dos filhos está coerente com o estado desejado.

    Parâmetros:
        node_id:
            Identificador do nó cuja carga será recalculada.
        graph:
            Grafo físico da rede (`PowerGridGraph`).
        index:
            Índice lógico `BPlusIndex` descrevendo as relações pai-filho.

    Retorno:
        Valor numérico atribuído a `node.current_load` após o recálculo.
        Em caso de nó inexistente, retorna 0.0.
    """
    node = graph.get_node(node_id)
    if node is None:
        return 0.0

    children_ids = index.get_children(node_id)
    total_load = 0.0

    for child_id in children_ids:
        child_node = graph.get_node(child_id)
        if child_node is None:
            continue
        total_load += float(child_node.current_load or 0.0)

    node.current_load = total_load
    return total_load


def propagate_load_upwards(
    start_node_id: str,
    graph: PowerGridGraph,
    index: BPlusIndex,
) -> None:
    """
    Propaga a carga agregada de um nó para toda a sua cadeia de pais
    lógicos, recalculando a carga em cada nível.

    Fluxo:

        1. Parte do nó identificado por `start_node_id`, que deve ter
           seu campo `current_load` já atualizado.
        2. Usa o índice `BPlusIndex` para subir na hierarquia:
               - em cada passo, obtém o pai lógico com `index.get_parent`;
               - para cada pai encontrado, chama
                 `recompute_node_load_from_children` para somar as cargas
                 dos filhos diretos;
               - continua até chegar a um nó sem pai (raiz lógica) ou
                 até que não haja nó correspondente no grafo.
        3. Não há distinção de tipos: a função apenas segue as relações
           de paternidade estabelecidas na B+.

    Esta rotina é útil para manter consistentes as cargas agregadas de
    subestações e usinas após uma mudança localizada de carga (por
    exemplo, em um consumidor ou em uma subestação intermediária).

    Parâmetros:
        start_node_id:
            Identificador do nó a partir do qual a propagação será
            iniciada. Em cenários comuns, é o id de um nó consumidor
            após alteração de carga.
        graph:
            Grafo físico da rede.
        index:
            Índice lógico B+ com as relações pai-filho.
    """
    current_id = start_node_id

    while True:
        parent_id = index.get_parent(current_id)
        if parent_id is None:
            break

        # Recalcula a carga do pai como soma das cargas dos filhos diretos.
        recompute_node_load_from_children(parent_id, graph, index)

        current_id = parent_id


def update_load_after_device_change(
    consumer_id: str,
    node_devices: Mapping[str, Sequence[IoTDevice]],
    graph: PowerGridGraph,
    index: BPlusIndex,
) -> None:
    """
    Atualiza a carga da rede após uma mudança em dispositivos conectados
    a um nó consumidor.

    Uso típico:

        1. Algum módulo de simulação (p.ex. `device_simulation`) atualiza
           o campo `current_power` de um conjunto de dispositivos
           associados a um nó consumidor.
        2. Esta função é chamada com o `consumer_id` e o mapeamento
           `node_devices`.
        3. A função:
               - recalcula a carga do nó consumidor com
                 `recompute_consumer_load`, somando as potências
                 instantâneas (`current_power`) dos dispositivos;
               - propaga a nova carga para cima na hierarquia lógica com
                 `propagate_load_upwards`, atualizando subestações e
                 usinas.

    Desta forma, o campo `current_load` em nós intermediários (DS, TS,
    usinas) permanece consistente com o consumo instantâneo dos
    dispositivos modelados na camada física.

    Parâmetros:
        consumer_id:
            Identificador do nó consumidor cujos dispositivos tiveram a
            potência instantânea alterada.
        node_devices:
            Mapeamento de ids de nós para listas de `IoTDevice`
            conectados a cada nó.
        graph:
            Grafo físico da rede.
        index:
            Índice lógico B+ com as relações pai-filho.
    """
    recompute_consumer_load(
        consumer_id=consumer_id,
        node_devices=node_devices,
        graph=graph,
    )

    propagate_load_upwards(
        start_node_id=consumer_id,
        graph=graph,
        index=index,
    )


__all__ = [
    "recompute_consumer_load",
    "recompute_node_load_from_children",
    "propagate_load_upwards",
    "update_load_after_device_change",
]
