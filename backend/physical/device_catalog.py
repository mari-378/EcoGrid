from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from physical.device_model import DeviceType
from physical.load_profiles import DailyProfileConfig, DailyProfileType
from physical.load_noise import NoiseConfig


@dataclass
class DeviceTemplate:
    """
    Template padrão de um tipo de dispositivo IoT.

    Esta estrutura reúne os parâmetros típicos de consumo de um
    dispositivo de um determinado tipo (por exemplo, TV, geladeira,
    ar-condicionado). A partir dela é possível criar instâncias de
    `IoTDevice` e de configuração de carga para simulação.

    Atributos:
        device_type:
            Tipo semântico do dispositivo (enum `DeviceType`).
        default_name:
            Nome padrão sugerido para o dispositivo, útil quando não se
            deseja especificar um nome mais descritivo.
        avg_power:
            Carga média consumida ao longo do dia pelo dispositivo,
            na unidade de potência adotada pela simulação (por exemplo,
            Watts ou kW). Este valor serve como referência central
            para o cálculo da carga instantânea.
        daily_profile:
            Configuração de perfil diário (`DailyProfileConfig`) que
            descreve o formato da "onda" de uso ao longo do dia
            (horários de maior e menor utilização).
        noise:
            Configuração de ruído estocástico (`NoiseConfig`) que
            descreve o nível de variação aleatória esperado em torno
            da curva base de consumo.
        min_fraction_of_avg:
            Fração da carga média usada para compor o limite mínimo de
            potência do dispositivo. Por exemplo, 0.2 indica que o
            limite mínimo será 20% de `avg_power`.
        max_fraction_of_avg:
            Fração da carga média usada para compor o limite máximo de
            potência do dispositivo. Por exemplo, 1.8 indica que o
            limite máximo será 180% de `avg_power`.
    """

    device_type: DeviceType
    default_name: str
    avg_power: float
    daily_profile: DailyProfileConfig
    noise: NoiseConfig
    min_fraction_of_avg: float
    max_fraction_of_avg: float


def _residential_daily_profile() -> DailyProfileConfig:
    """
    Cria um perfil diário típico residencial.

    Este perfil é adequado para dispositivos que seguem o padrão de
    uso residencial, com maior utilização no início da noite, algum
    uso pela manhã e menor atividade na madrugada.

    Retorno:
        Instância de `DailyProfileConfig` configurada para perfil
        residencial padrão.
    """
    return DailyProfileConfig(
        profile_type=DailyProfileType.RESIDENTIAL,
        day_period_seconds=24.0 * 3600.0,
        phase_shift_seconds=0.0,
        amplitude_factor=1.0,
    )


def _flat_daily_profile() -> DailyProfileConfig:
    """
    Cria um perfil diário aproximadamente constante.

    Este perfil é adequado para dispositivos que operam de forma
    quase contínua ao longo do dia, como geladeiras e equipamentos
    que mantêm funcionamento permanente, com variações mais sutis
    delegadas ao ruído estocástico.

    Retorno:
        Instância de `DailyProfileConfig` configurada para perfil
        aproximadamente constante.
    """
    return DailyProfileConfig(
        profile_type=DailyProfileType.FLAT,
        day_period_seconds=24.0 * 3600.0,
        phase_shift_seconds=0.0,
        amplitude_factor=1.0,
    )


def _default_noise(amplitude: float) -> NoiseConfig:
    """
    Cria uma configuração padrão de ruído estocástico para um
    dispositivo.

    A configuração adota blocos de 60 segundos, o que resulta em
    variações suaves em escala de minutos, e utiliza a amplitude
    fornecida como parâmetro para controlar o desvio relativo em
    torno da curva base.

    Parâmetros:
        amplitude:
            Amplitude relativa do ruído. Por exemplo, 0.1 significa
            variações de até ±10% em torno da carga base.

    Retorno:
        Instância de `NoiseConfig` com duração de bloco fixa e
        amplitude informada.
    """
    return NoiseConfig(
        block_duration_seconds=60.0,
        amplitude=amplitude,
        seed_base=12345,
    )


def get_device_template(device_type: DeviceType) -> DeviceTemplate:
    """
    Retorna um template padrão para o tipo de dispositivo informado.

    Cada tipo de dispositivo possui uma configuração típica de consumo
    médio, perfil diário de uso e ruído estocástico. Esses valores não
    têm a pretensão de representar medições reais, mas sim oferecer um
    ponto de partida razoável para simulações.

    Assumindo unidade de potência genérica (por exemplo, kW), exemplos
    aproximados são:

        - TV:
            Consumo médio moderado, uso predominantemente à noite.
        - FRIDGE:
            Consumo relativamente constante ao longo do dia, com pequenas
            flutuações.
        - AIR_CONDITIONER:
            Consumo elevado, maior uso no fim da tarde e início da noite
            em contexto residencial (perfil residencial como aproximação).
        - LIGHTING:
            Consumo baixo a moderado, mais intenso em horários de menor
            luminosidade natural.
        - GENERIC:
            Dispositivo genérico com perfil residencial simples.

    Parâmetros:
        device_type:
            Tipo de dispositivo (`DeviceType`) para o qual se deseja
            obter o template padrão.

    Retorno:
        Instância de `DeviceTemplate` contendo parâmetros padrão
        sugeridos para o dispositivo.

    Observação:
        Os valores retornados podem ser ajustados posteriormente caso
        seja necessário calibrar a simulação para contextos específicos.
    """
    if device_type is DeviceType.TV:
        return DeviceTemplate(
            device_type=device_type,
            default_name="TV",
            avg_power=0.1,  # exemplo: 0.1 kW
            daily_profile=_residential_daily_profile(),
            noise=_default_noise(amplitude=0.15),
            min_fraction_of_avg=0.0,
            max_fraction_of_avg=2.0,
        )

    if device_type is DeviceType.FRIDGE:
        return DeviceTemplate(
            device_type=device_type,
            default_name="Fridge",
            avg_power=0.08,  # exemplo: 0.08 kW
            daily_profile=_flat_daily_profile(),
            noise=_default_noise(amplitude=0.05),
            min_fraction_of_avg=0.3,
            max_fraction_of_avg=1.5,
        )

    if device_type is DeviceType.AIR_CONDITIONER:
        return DeviceTemplate(
            device_type=device_type,
            default_name="AirConditioner",
            avg_power=1.5,  # exemplo: 1.5 kW
            daily_profile=_residential_daily_profile(),
            noise=_default_noise(amplitude=0.2),
            min_fraction_of_avg=0.0,
            max_fraction_of_avg=2.0,
        )

    if device_type is DeviceType.LIGHTING:
        return DeviceTemplate(
            device_type=device_type,
            default_name="Lighting",
            avg_power=0.2,  # exemplo: 0.2 kW agregando várias lâmpadas
            daily_profile=_residential_daily_profile(),
            noise=_default_noise(amplitude=0.1),
            min_fraction_of_avg=0.0,
            max_fraction_of_avg=1.5,
        )

    # Caso GENERIC ou qualquer outro não mapeado explicitamente
    return DeviceTemplate(
        device_type=device_type,
        default_name="GenericDevice",
        avg_power=0.5,  # valor genérico intermediário
        daily_profile=_residential_daily_profile(),
        noise=_default_noise(amplitude=0.1),
        min_fraction_of_avg=0.0,
        max_fraction_of_avg=2.0,
    )


def get_default_avg_power(device_type: DeviceType) -> float:
    """
    Retorna a carga média padrão associada a um tipo de dispositivo.

    Esta função é um atalho para acessar apenas o valor de `avg_power`
    do template padrão de um dispositivo, útil quando se deseja apenas
    a potência média sem precisar lidar com o restante da configuração.

    Parâmetros:
        device_type:
            Tipo de dispositivo (`DeviceType`).

    Retorno:
        Carga média padrão (`avg_power`) para o tipo informado.
    """
    return get_device_template(device_type).avg_power


__all__: Sequence[str] = ["DeviceTemplate", "get_device_template", "get_default_avg_power"]
