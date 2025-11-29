from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional, Sequence


class DeviceType(Enum):
    """
    Tipos semânticos de dispositivos IoT consumidores de energia.

    Esta enum é utilizada para categorizar dispositivos conectados a
    nós do tipo consumidor (CONSUMER_POINT). A categoria permite
    associar parâmetros padrão de consumo médio, perfis diários de uso
    e configurações de ruído estocástico, facilitando a criação em
    massa de dispositivos com comportamento coerente.

    Exemplos de tipos:
        - TV:
            Televisores residenciais ou comerciais.
        - FRIDGE:
            Geladeiras e freezers domésticos.
        - AIR_CONDITIONER:
            Aparelhos de ar-condicionado.
        - LIGHTING:
            Iluminação (lâmpadas, luminárias).
        - GENERIC:
            Dispositivo genérico quando não há categoria mais específica.
    """

    TV = "TV"
    FRIDGE = "FRIDGE"
    AIR_CONDITIONER = "AIR_CONDITIONER"
    LIGHTING = "LIGHTING"
    GENERIC = "GENERIC"


@dataclass
class IoTDevice:
    """
    Representa um dispositivo IoT consumidor de energia conectado a um nó.

    Cada dispositivo possui uma carga média característica ao longo do
    dia (por exemplo, potência média esperada de uma TV, geladeira ou
    ar-condicionado) e uma carga atual que será atualizada ao longo da
    simulação por meio de algoritmos estocásticos de carga.

    Importante:
        A relação entre dispositivos e nós do grafo físico não é
        armazenada diretamente nesta classe. Em vez disso, utiliza-se
        uma estrutura externa de mapeamento, como:

            node_id -> lista de IoTDevice

        Isso permite que apenas nós do tipo consumidor possuam
        dispositivos associados, sem modificar a definição da classe
        Node na camada de grafo.

    Atributos:
        id:
            Identificador único do dispositivo no escopo da simulação.
            Este identificador é utilizado, entre outras coisas, como
            entrada para funções de ruído determinístico, garantindo
            padrões de variação distintos e reprodutíveis para cada
            dispositivo.
        name:
            Nome amigável do dispositivo, útil para exibição em
            interfaces ou logs (por exemplo, "TV sala", "Geladeira").
        device_type:
            Tipo semântico do dispositivo, conforme `DeviceType`.
            Ajuda a escolher parâmetros padrão de consumo e perfil
            diário. Pode ser `DeviceType.GENERIC` quando o tipo
            específico não for relevante.
        avg_power:
            Carga consumida média ao longo do dia, em unidades de
            potência (por exemplo, Watts ou kW, conforme convenção da
            simulação). Este valor serve como referência central para o
            processo de geração de carga instantânea.
        current_power:
            Carga consumida atual pelo dispositivo, na mesma unidade de
            `avg_power`. Este campo é atualizado pelos algoritmos de
            simulação de carga (perfil diário + ruído). Inicialmente
            pode ser `None` até que a simulação calcule o primeiro
            valor.
    """

    id: str
    name: str
    device_type: DeviceType
    avg_power: float
    current_power: Optional[float] = None


__all__: Sequence[str] = ["DeviceType", "IoTDevice"]
