from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional, Sequence


class NodeType(Enum):
    """
    Tipos de nós da rede elétrica.

    Cada valor representa um papel físico ou funcional na rede:

    - GENERATION_PLANT:
        Usinas de geração ou pontos de injeção de energia na rede.
    - TRANSMISSION_SUBSTATION:
        Subestações de transmissão em alta tensão, que recebem energia
        de usinas e alimentam a malha de transmissão.
    - DISTRIBUTION_SUBSTATION:
        Subestações de distribuição em média tensão, que recebem energia
        de subestações de transmissão e alimentam a rede de distribuição.
    - CONSUMER_POINT:
        Pontos consumidores agregados (conjunto de cargas finais) ligados
        à rede de baixa tensão.
    """

    GENERATION_PLANT = "GENERATION_PLANT"
    TRANSMISSION_SUBSTATION = "TRANSMISSION_SUBSTATION"
    DISTRIBUTION_SUBSTATION = "DISTRIBUTION_SUBSTATION"
    CONSUMER_POINT = "CONSUMER_POINT"


class EdgeType(Enum):
    """
    Tipos de arestas (segmentos de linha) da rede elétrica.

    Cada valor indica o nível de tensão e o papel aproximado do segmento:

    - TRANSMISSION_SEGMENT:
        Segmentos de transmissão em alta tensão, conectando usinas e
        subestações de transmissão, ou interligando subestações de
        transmissão entre si.
    - MV_DISTRIBUTION_SEGMENT:
        Segmentos de média tensão (MV), conectando subestações de
        transmissão a subestações de distribuição, ou formando malhas
        entre subestações de distribuição.
    - LV_DISTRIBUTION_SEGMENT:
        Segmentos de baixa tensão (LV), conectando subestações de
        distribuição a pontos consumidores.
    """

    TRANSMISSION_SEGMENT = "TRANSMISSION_SEGMENT"
    MV_DISTRIBUTION_SEGMENT = "MV_DISTRIBUTION_SEGMENT"
    LV_DISTRIBUTION_SEGMENT = "LV_DISTRIBUTION_SEGMENT"


@dataclass
class ClusterInfo:
    """
    Informações agregadas sobre um cluster de carga.

    Um cluster representa uma região da área simulada (por exemplo, um
    bairro ou zona urbana) usada para concentrar subestações de
    distribuição e consumidores em torno de um centro.

    Atributos:
        id:
            Identificador numérico único do cluster.
        center_x:
            Coordenada cartesiana X aproximada do centro do cluster.
        center_y:
            Coordenada cartesiana Y aproximada do centro do cluster.
        radius:
            Raio aproximado usado para distribuir nós dentro do cluster.
        target_num_consumers:
            Número alvo de consumidores a serem posicionados neste cluster.
            Esse valor é utilizado pelas etapas de planejamento para
            distribuir a carga espacialmente.
    """

    id: int
    center_x: float
    center_y: float
    radius: float
    target_num_consumers: int


@dataclass
class Node:
    """
    Nó da rede elétrica no grafo físico.

    Representa qualquer entidade conectada pela rede, como usinas,
    subestações ou pontos consumidores. Este modelo é usado pelas etapas
    de geração da rede, pelos módulos de exportação de dados e pode servir
    de base para camadas lógicas de agregação.

    Atributos:
        id:
            Identificador único do nó no grafo.
        node_type:
            Tipo do nó, conforme o enum `NodeType`.
        position_x:
            Coordenada cartesiana X do nó na área simulada.
        position_y:
            Coordenada cartesiana Y do nó na área simulada.
        cluster_id:
            Identificador do cluster de carga ao qual o nó está associado.
            Pode ser `None` para nós que não pertencem a um cluster específico
            (por exemplo, algumas usinas ou subestações de transmissão).
        nominal_voltage:
            Tensão nominal típica associada ao nó, em Volts. Pode ser `None`
            se não houver tensão configurada ou se a tensão for inferida
            em outra etapa. Os valores padrão são definidos em `SimulationConfig`.
        capacity:
            Capacidade elétrica associada ao nó, em unidades adequadas
            (por exemplo, potência máxima atendida por uma subestação ou
            carga instalada em um ponto consumidor agregado). Inicializada
            como `None` e destinada a módulos futuros de simulação ou
            análise de capacidade.
        current_load:
            Carga elétrica atualmente associada ao nó, em unidades
            compatíveis com `capacity` (por exemplo, potência demandada em
            um intervalo de tempo). Também é inicializada como `None` e
            pode ser preenchida por módulos responsáveis por estimativa ou
            medição de carga.
    """

    id: str
    node_type: NodeType
    position_x: float
    position_y: float
    cluster_id: Optional[int] = None
    nominal_voltage: Optional[float] = None
    capacity: Optional[float] = None
    current_load: Optional[float] = None
    energy_loss_pct: Optional[float] = None


@dataclass
class Edge:
    """
    Aresta da rede elétrica no grafo físico.

    Representa um segmento de linha elétrica ligando dois nós. O tipo de
    aresta (`edge_type`) indica se o segmento pertence à rede de transmissão,
    de média tensão (MV) ou de baixa tensão (LV).

    Atributos:
        id:
            Identificador único da aresta no grafo.
        edge_type:
            Tipo da aresta, conforme o enum `EdgeType`.
        from_node_id:
            Identificador do nó de origem do segmento.
        to_node_id:
            Identificador do nó de destino do segmento.
        length:
            Comprimento geométrico do segmento, normalmente calculado a
            partir das posições dos nós (por exemplo, distância euclidiana).
            É expresso na mesma unidade das coordenadas dos nós e deve ser
            sempre preenchido pelas etapas de planejamento ao criar a aresta.
    """

    id: str
    edge_type: EdgeType
    from_node_id: str
    to_node_id: str
    length: float


__all__: Sequence[str] = ["NodeType", "EdgeType", "ClusterInfo", "Node", "Edge"]
