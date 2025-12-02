from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence


@dataclass
class SimulationConfig:
    """
    Configurações principais da simulação da rede elétrica.

    Esta classe agrupa parâmetros de controle usados pelas diferentes
    etapas de planejamento (geração de nós, transmissão, MV, LV,
    robustez e exportação). A ideia é concentrar neste objeto os valores
    que o usuário pode ajustar para produzir diferentes instâncias de
    redes sintéticas.

    Atributos gerais:
        random_seed:
            Semente do gerador de números aleatórios. Permite reproduzir
            a mesma rede em execuções diferentes quando mantido fixo.
        area_width:
            Largura da área simulada no plano cartesiano. Todos os nós
            gerados terão coordenadas X dentro do intervalo
            [0, area_width].
        area_height:
            Altura da área simulada no plano cartesiano. Todos os nós
            gerados terão coordenadas Y dentro do intervalo
            [0, area_height].

    Atributos de clusters e densidade de carga:
        num_clusters:
            Número de clusters de carga (por exemplo, bairros) a serem
            gerados na área.
        cluster_radius:
            Raio típico de cada cluster, usado para posicionar nós de
            subestações de distribuição e consumidores ao redor do centro.
        consumers_per_cluster:
            Número médio de pontos consumidores agregados por cluster.
        distribution_substations_per_cluster:
            Número de subestações de distribuição a serem alocadas em
            cada cluster de carga.

    Atributos de quantidade de nós por nível:
        num_generation_plants:
            Número de usinas de geração a serem criadas na área
            simulada.
        num_transmission_substations:
            Número total de subestações de transmissão.

    Tensões nominais (por tipo de nó, em Volts):
        generation_nominal_voltage:
            Tensão nominal típica em nós de geração. Por padrão, 500 kV.
        transmission_nominal_voltage:
            Tensão nominal típica em subestações de transmissão. Por
            padrão, 500 kV.
        distribution_nominal_voltage:
            Tensão nominal típica em subestações de distribuição
            (média tensão). Por padrão, 13,8 kV.
        consumer_nominal_voltage:
            Tensão nominal típica em pontos consumidores (baixa tensão).
            Por padrão, 220 V.

    Parâmetros geométricos de segmentos:
        max_transmission_segment_length:
            Comprimento máximo desejado para segmentos da rede de
            transmissão. Pode ser usado como limite para criar arestas
            na malha de transmissão.
        max_mv_segment_length:
            Comprimento máximo desejado para segmentos da rede de média
            tensão (entre subestações de distribuição e entre DS e TS).
        max_lv_segment_length:
            Comprimento máximo desejado para segmentos da rede de baixa
            tensão (entre subestações de distribuição e consumidores).
    """

    # Parâmetros globais
    random_seed: int = 42
    area_width: float = 1000.0
    area_height: float = 1000.0

    # Clusters e densidade
    num_clusters: int = 3
    cluster_radius: float = 480.0
    consumers_per_cluster: int = 13
    distribution_substations_per_cluster: int = 2

    # Quantidade de nós por nível
    num_generation_plants: int = 1
    num_transmission_substations: int = 2

    # Tensões nominais (em Volts)
    generation_nominal_voltage: float | None = 500e3     # 500 kV
    transmission_nominal_voltage: float | None = 500e3   # 500 kV
    distribution_nominal_voltage: float | None = 13.8e3  # 13,8 kV
    consumer_nominal_voltage: float | None = 220.0       # 220 V

    # Limites de comprimento de segmentos (Aumentados para garantir conectividade)
    max_transmission_segment_length: float = 1500.0
    max_mv_segment_length: float = 900.0
    max_lv_segment_length: float = 600.0


__all__: Sequence[str] = ["SimulationConfig"]
