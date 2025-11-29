from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum
from typing import Sequence


class DailyProfileType(Enum):
    """
    Tipos de perfis diários de carga.

    Cada tipo representa um padrão típico de variação de consumo ao
    longo de um dia completo (por exemplo, 24 horas). O objetivo é
    capturar a forma geral da "onda" de consumo antes de aplicar
    ruídos estocásticos.

    Perfis disponíveis:

    - RESIDENTIAL:
        Perfil típico residencial, com pico principal no início da noite
        e um pico secundário pela manhã. Durante a madrugada, a carga
        é reduzida.
    - COMMERCIAL:
        Perfil de estabelecimento comercial, com maior consumo no
        horário comercial (aproximadamente entre 9h e 18h) e carga
        muito baixa à noite.
    - INDUSTRIAL:
        Perfil mais constante, com pequenas variações ao longo do dia,
        representando processos industriais contínuos.
    - FLAT:
        Perfil aproximadamente constante, útil como base neutra ou para
        dispositivos cuja variação diária é pouco relevante.
    """

    RESIDENTIAL = "RESIDENTIAL"
    COMMERCIAL = "COMMERCIAL"
    INDUSTRIAL = "INDUSTRIAL"
    FLAT = "FLAT"


@dataclass
class DailyProfileConfig:
    """
    Configuração de um perfil diário de carga.

    Esta configuração controla como a carga "base" de um dispositivo
    varia ao longo de um ciclo diário, antes da aplicação de ruídos
    estocásticos.

    Atributos:
        profile_type:
            Tipo de perfil diário a ser utilizado. Define a forma
            qualitativa da curva (por exemplo, residencial, comercial).
        day_period_seconds:
            Duração do ciclo diário em segundos. Em aplicações
            típicas, corresponde a 24 * 3600 segundos. Alterar esse
            valor permite simular ciclos mais curtos ou mais longos.
        phase_shift_seconds:
            Deslocamento de fase da curva em segundos. Permite ajustar
            o horário de pico sem alterar a forma geral. Por exemplo,
            um deslocamento positivo pode mover o pico de consumo para
            mais tarde no dia.
        amplitude_factor:
            Fator multiplicativo aplicado à amplitude da curva antes da
            normalização final. Usado para calibrar o contraste entre
            períodos de pico e de vale. Valores maiores aumentam a
            diferença relativa entre horários de maior e menor consumo.
    """

    profile_type: DailyProfileType
    day_period_seconds: float = 24.0 * 3600.0
    phase_shift_seconds: float = 0.0
    amplitude_factor: float = 1.0


def _normalize_time_fraction(
    t_seconds: float,
    day_period_seconds: float,
    phase_shift_seconds: float,
) -> float:
    """
    Normaliza o instante de tempo para uma fração diária no intervalo [0, 1).

    O tempo é primeiro ajustado por um deslocamento de fase e depois
    reduzido módulo o período diário. O resultado representa a posição
    relativa dentro do ciclo diário.

    Parâmetros:
        t_seconds:
            Instante de tempo em segundos.
        day_period_seconds:
            Duração do ciclo diário em segundos.
        phase_shift_seconds:
            Deslocamento de fase em segundos.

    Retorno:
        Valor em ponto flutuante no intervalo [0, 1), onde 0 corresponde
        ao início do ciclo diário (por exemplo, meia-noite) e 0.5 ao
        meio do ciclo (por exemplo, meio-dia).
    """
    if day_period_seconds <= 0:
        # Evita divisão por zero ou períodos inválidos.
        return 0.0

    # Ajusta pelo deslocamento de fase e reduz módulo o período diário.
    adjusted = (t_seconds - phase_shift_seconds) / day_period_seconds
    # Mantém apenas a parte fracionária positiva em [0, 1).
    return adjusted % 1.0


def _residential_curve(tau: float) -> float:
    """
    Curva base para perfil residencial.

    A fração de tempo `tau` deve estar em [0, 1), representando a
    posição dentro do dia. A curva assume:

    - pico principal no início da noite (por volta de tau ≈ 0.8);
    - pico secundário pela manhã (por volta de tau ≈ 0.3);
    - carga reduzida na madrugada.

    Retorno:
        Valor bruto (não normalizado) que será posteriormente ajustado
        para o intervalo [0, 1].
    """
    # Pico noturno (pesado) e pico matinal (moderado)
    night_peak = 0.6 * math.cos(2.0 * math.pi * (tau - 0.8))
    morning_peak = 0.3 * math.cos(2.0 * math.pi * (tau - 0.3) * 2.0)

    # Nível base mínimo para evitar valores negativos excessivos
    base_level = 0.4

    return base_level + night_peak + morning_peak


def _commercial_curve(tau: float) -> float:
    """
    Curva base para perfil comercial.

    Assume maior consumo no horário comercial aproximado (entre 9h e
    18h) e carga muito baixa à noite. O pico ocorre próximo ao meio do
    dia (tau ≈ 0.5).

    Retorno:
        Valor bruto (não normalizado) que será posteriormente ajustado
        para o intervalo [0, 1].
    """
    # Pico único em torno de tau = 0.5 (meio do dia)
    main_peak = 0.7 * math.cos(2.0 * math.pi * (tau - 0.5))
    base_level = 0.2
    return base_level + main_peak


def _industrial_curve(tau: float) -> float:
    """
    Curva base para perfil industrial.

    Representa uma carga mais constante ao longo do dia, com pequenas
    oscilações, adequada para processos industriais contínuos.

    Retorno:
        Valor bruto (não normalizado) que será posteriormente ajustado
        para o intervalo [0, 1].
    """
    # Variação suave ao redor de um patamar relativamente constante
    small_variation = 0.1 * math.cos(2.0 * math.pi * tau)
    base_level = 0.7
    return base_level + small_variation


def _flat_curve(tau: float) -> float:
    """
    Curva base aproximadamente constante.

    Útil para dispositivos cuja variação diária não é relevante ou
    quando se deseja um comportamento neutro, deixando a principal
    variabilidade a cargo do ruído estocástico.

    Retorno:
        Valor bruto (não normalizado) que será posteriormente ajustado
        para o intervalo [0, 1].
    """
    return 0.5


def _raw_profile_value(config: DailyProfileConfig, tau: float) -> float:
    """
    Calcula o valor bruto do perfil diário para uma fração de tempo.

    Esta função escolhe a forma da curva com base em `profile_type` e
    aplica o fator de amplitude configurado. O resultado ainda não é
    garantido dentro de [0, 1]; a normalização final é feita em outra
    etapa.

    Parâmetros:
        config:
            Configuração do perfil diário.
        tau:
            Fração do ciclo diário no intervalo [0, 1).

    Retorno:
        Valor bruto do perfil, antes de normalização e recorte.
    """
    if config.profile_type is DailyProfileType.RESIDENTIAL:
        base = _residential_curve(tau)
    elif config.profile_type is DailyProfileType.COMMERCIAL:
        base = _commercial_curve(tau)
    elif config.profile_type is DailyProfileType.INDUSTRIAL:
        base = _industrial_curve(tau)
    elif config.profile_type is DailyProfileType.FLAT:
        base = _flat_curve(tau)
    else:
        # Perfil desconhecido: adota comportamento neutro.
        base = _flat_curve(tau)

    return base * config.amplitude_factor


def daily_profile_value(config: DailyProfileConfig, t_seconds: float) -> float:
    """
    Calcula o valor base do perfil diário no instante de tempo indicado.

    O resultado é um fator adimensional no intervalo [0.0, 1.0] que
    representa a carga relativa em relação aos valores mínimo e máximo
    associados ao dispositivo. Este fator será geralmente combinado com
    ruído estocástico e com a faixa de potência [p_min, p_max] em outras
    partes do sistema.

    Processo de cálculo:

    1. O instante `t_seconds` é normalizado para uma fração diária
       `tau` em [0, 1), considerando o período `day_period_seconds` e o
       deslocamento de fase `phase_shift_seconds`.
    2. A função interna `_raw_profile_value` é usada para obter o valor
       bruto da curva, que pode não estar em [0, 1].
    3. O valor bruto é então recortado para o intervalo [0, 1] por meio
       de uma normalização conservadora:
       - valores abaixo de 0 são trazidos para 0;
       - valores acima de 1 são trazidos para 1.

    Parâmetros:
        config:
            Configuração do perfil diário (`DailyProfileConfig`).
        t_seconds:
            Instante de tempo em segundos. Pode ser o tempo absoluto
            da simulação; a função internamente faz a redução módulo
            o período diário.

    Retorno:
        Fator em ponto flutuante no intervalo [0.0, 1.0], adequado para
        ser usado como multiplicador da faixa de carga do dispositivo.
    """
    tau = _normalize_time_fraction(
        t_seconds=t_seconds,
        day_period_seconds=config.day_period_seconds,
        phase_shift_seconds=config.phase_shift_seconds,
    )

    raw = _raw_profile_value(config, tau)

    # Normalização simples para [0, 1]. Caso seja necessário um
    # controle mais preciso da distribuição estatística, esta etapa
    # pode ser refinada futuramente.
    value = max(0.0, min(1.0, raw))
    return value


__all__: Sequence[str] = [
    "DailyProfileType",
    "DailyProfileConfig",
    "daily_profile_value",
]
