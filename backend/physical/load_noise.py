from __future__ import annotations

import hashlib
import math
import struct
from dataclasses import dataclass
from typing import Sequence


@dataclass
class NoiseConfig:
    """
    Configuração do ruído estocástico aplicado à carga de um dispositivo.

    Este ruído é pensado para ser somado (ou aplicado de forma
    multiplicativa) ao perfil diário determinístico de um dispositivo
    IoT, introduzindo variações suaves ao longo do tempo sem exigir
    armazenamento de histórico.

    O ruído é calculado de forma determinística a partir de:
        - uma semente base (`seed_base`);
        - o identificador do dispositivo (`device_id`);
        - o índice de um bloco de tempo (inteiro).

    Isso garante que:
        - para o mesmo dispositivo, semente e instante, o ruído seja
          reprodutível;
        - diferentes dispositivos tenham padrões de ruído distintos.

    Atributos:
        block_duration_seconds:
            Duração, em segundos, de cada bloco de tempo utilizado para
            gerar valores de ruído. Dentro de um bloco, o ruído é
            interpolado entre o valor do bloco atual e o do próximo.
            Valores típicos entre 30 e 300 segundos produzem variações
            suaves em escala de minutos.
        amplitude:
            Amplitude máxima do ruído em termos de fração relativa. Por
            exemplo, amplitude = 0.1 indica que o ruído poderá desviar
            a carga em até ±10% em torno de um valor base, dependendo de
            como for combinado com o perfil diário.
        seed_base:
            Semente base usada na geração pseudo-aleatória. Diferentes
            valores produzem padrões globais de ruído distintos, mas
            reprodutíveis. Para o mesmo `seed_base`, `device_id` e
            instante de tempo, o ruído calculado será sempre o mesmo.
    """

    block_duration_seconds: float = 60.0
    amplitude: float = 0.1
    seed_base: int = 12345


def _deterministic_noise_value(seed_base: int, device_id: str, block_index: int) -> float:
    """
    Gera um valor pseudo-aleatório determinístico no intervalo [-1, 1]
    para um dispositivo e um bloco de tempo específicos.

    A função combina:

        - a semente base (`seed_base`);
        - o identificador do dispositivo (`device_id`);
        - o índice de bloco de tempo (`block_index`);

    e alimenta esses dados em um hash criptográfico (SHA-256). Em
    seguida, extrai parte do digest e converte para um número em ponto
    flutuante aproximadamente uniforme em [-1, 1]. O objetivo é
    garantir que:

        - o mesmo dispositivo, bloco e semente produzam sempre o mesmo
          valor;
        - dispositivos ou blocos diferentes produzam valores distintos
          com boa dispersão.

    Parâmetros:
        seed_base:
            Semente base do ruído.
        device_id:
            Identificador do dispositivo IoT.
        block_index:
            Índice inteiro do bloco de tempo (por exemplo, t / 60 s).

    Retorno:
        Valor em ponto flutuante no intervalo aproximado [-1.0, 1.0].
        Pequenas discrepâncias numéricas são corrigidas por recorte.
    """
    hasher = hashlib.sha256()
    # Semente base como inteiro de 64 bits
    hasher.update(struct.pack("!q", seed_base))
    # Identificador do dispositivo como bytes
    hasher.update(device_id.encode("utf-8"))
    # Índice de bloco como inteiro de 64 bits
    hasher.update(struct.pack("!q", block_index))

    digest = hasher.digest()

    # Usa os primeiros 4 bytes como inteiro assinado de 32 bits
    int_val = struct.unpack("!i", digest[:4])[0]

    # Normaliza aproximadamente para [-1, 1]. O divisor é próximo de 2^31 - 1.
    x = int_val / 2_147_483_647.0

    # Garante que x esteja dentro de [-1, 1] após possíveis erros de arredondamento.
    if x < -1.0:
        x = -1.0
    if x > 1.0:
        x = 1.0

    return x


def noise_value(config: NoiseConfig, device_id: str, t_seconds: float) -> float:
    """
    Calcula o valor de ruído suave para um dispositivo em um instante de tempo.

    O tempo contínuo é dividido em blocos de duração fixa, definidos por
    `block_duration_seconds`. Para cada bloco, é gerado um valor
    pseudo-aleatório determinístico dependente de:

        - `seed_base` (configuração global do ruído);
        - `device_id` (para diferenciar dispositivos);
        - índice do bloco de tempo.

    Dentro de cada bloco, o ruído é interpolado linearmente entre o
    valor do bloco atual e o do próximo bloco, produzindo uma variação
    suave ao longo do tempo sem descontinuidades abruptas a cada
    mudança de bloco.

    O valor final retornado é escalado pela amplitude configurada e
    pertence ao intervalo [-amplitude, +amplitude].

    Parâmetros:
        config:
            Instância de `NoiseConfig` que define a duração do bloco,
            amplitude do ruído e semente base.
        device_id:
            Identificador do dispositivo IoT para o qual se deseja
            calcular o ruído. Dispositivos distintos produzem padrões
            distintos de ruído.
        t_seconds:
            Instante de tempo em segundos no qual se quer avaliar o
            ruído.

    Retorno:
        Valor em ponto flutuante no intervalo [-amplitude, +amplitude],
        onde `amplitude` é `config.amplitude`. Se `block_duration_seconds`
        for menor ou igual a zero ou se a amplitude for não positiva, o
        ruído retornado será 0.0.
    """
    if config.block_duration_seconds <= 0.0 or config.amplitude <= 0.0:
        return 0.0

    # Índice de bloco contínuo (pode ter parte fracionária)
    block_f = t_seconds / config.block_duration_seconds
    block_index = int(math.floor(block_f))
    frac = block_f - block_index  # parte fracionária no bloco atual

    # Valores pseudo-aleatórios determinísticos para bloco atual e próximo
    n0 = _deterministic_noise_value(config.seed_base, device_id, block_index)
    n1 = _deterministic_noise_value(config.seed_base, device_id, block_index + 1)

    # Interpolação linear entre n0 e n1 para suavizar a transição temporal
    n = (1.0 - frac) * n0 + frac * n1

    # Escala pela amplitude configurada
    return config.amplitude * n


__all__: Sequence[str] = ["NoiseConfig", "noise_value"]
