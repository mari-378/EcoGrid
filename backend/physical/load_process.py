from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Sequence

from physical.device_model import IoTDevice
from physical.device_catalog import DeviceTemplate
from physical.load_profiles import DailyProfileConfig, daily_profile_value
from physical.load_noise import NoiseConfig, noise_value


@dataclass
class DeviceLoadConfig:
    """
    Configuração do processo de carga de um dispositivo IoT.

    Esta configuração descreve como a carga instantânea de um
    dispositivo varia ao longo do tempo, combinando:

        - carga média do dispositivo (armazenada em `IoTDevice.avg_power`);
        - limites mínimo e máximo relativos à carga média;
        - perfil diário determinístico (forma da curva ao longo do dia);
        - ruído estocástico suave (variação aleatória em torno da curva).

    Importante:
        A carga média (`avg_power`) NÃO é armazenada nesta configuração.
        Ela pertence ao próprio dispositivo (`IoTDevice.avg_power`),
        permitindo que dispositivos de mesmo tipo tenham valores médios
        distintos. O `DeviceLoadConfig` define apenas como essa média
        será "modulada" ao longo do dia.

    Atributos:
        daily_profile:
            Configuração do perfil diário determinístico
            (`DailyProfileConfig`), que devolve um fator em [0, 1] para
            cada instante de tempo.
        noise:
            Configuração de ruído estocástico (`NoiseConfig`), que
            devolve um fator relativo em [-ε, +ε] para cada instante de
            tempo, onde ε é a amplitude configurada.
        min_fraction_of_avg:
            Fração da carga média usada para compor o limite mínimo de
            potência do dispositivo. Por exemplo, 0.2 implica que:

                P_min = 0.2 * avg_power

            onde `avg_power` é `IoTDevice.avg_power`.
        max_fraction_of_avg:
            Fração da carga média usada para compor o limite máximo de
            potência do dispositivo. Por exemplo, 1.8 implica:

                P_max = 1.8 * avg_power

            Deve-se garantir, em configurações consistentes, que
            `max_fraction_of_avg` seja maior que `min_fraction_of_avg`.
    """

    daily_profile: DailyProfileConfig
    noise: NoiseConfig
    min_fraction_of_avg: float
    max_fraction_of_avg: float


def make_load_config_from_template(template: DeviceTemplate) -> DeviceLoadConfig:
    """
    Cria uma configuração de processo de carga a partir de um template
    de dispositivo.

    O `DeviceTemplate` reúne informações típicas de um tipo de
    dispositivo (TV, geladeira, etc.), incluindo:

        - perfil diário padrão;
        - ruído padrão;
        - frações mínimas e máximas em torno da carga média.

    Esta função extrai essas informações e monta um `DeviceLoadConfig`,
    mantendo os valores de `min_fraction_of_avg` e `max_fraction_of_avg`
    exatamente como definidos no template.

    Parâmetros:
        template:
            Template padrão de um tipo de dispositivo, conforme
            `DeviceTemplate`.

    Retorno:
        Instância de `DeviceLoadConfig` pronta para ser usada em
        conjunto com dispositivos que compartilhem o mesmo tipo
        de comportamento de carga.
    """
    return DeviceLoadConfig(
        daily_profile=template.daily_profile,
        noise=template.noise,
        min_fraction_of_avg=template.min_fraction_of_avg,
        max_fraction_of_avg=template.max_fraction_of_avg,
    )


def compute_device_power(
    device: IoTDevice,
    t_seconds: float,
    config: DeviceLoadConfig,
) -> float:
    """
    Calcula a carga instantânea de um dispositivo em um instante de tempo.

    O cálculo utiliza a carga média do dispositivo (`device.avg_power`)
    como referência central e a modula segundo:

        - o perfil diário determinístico (`config.daily_profile`);
        - o ruído estocástico relativo (`config.noise`).

    A lógica é:

        1. Determinar os limites absoluto mínimo e máximo de potência
           a partir das frações e da carga média:

               P_min = min_fraction_of_avg * avg_power
               P_max = max_fraction_of_avg * avg_power

        2. Obter o fator base diário em [0, 1]:

               f_base = daily_profile_value(daily_profile, t_seconds)

        3. Obter o ruído relativo em [-ε, +ε]:

               n = noise_value(noise, device.id, t_seconds)

        4. Calcular a potência base (sem ruído):

               P_base = P_min + f_base * (P_max - P_min)

        5. Aplicar o ruído de forma multiplicativa suave:

               P = P_base * (1.0 + n)

        6. Recortar o valor final para o intervalo [P_min, P_max].

    Observações importantes:

    - Se `avg_power` for menor ou igual a zero, o dispositivo é tratado
      como sem consumo significativo e a função retorna 0.0.
    - Se `max_fraction_of_avg` for menor ou igual a
      `min_fraction_of_avg`, considera-se uma configuração degenerada
      e a função retorna simplesmente P_min.

    Parâmetros:
        device:
            Dispositivo IoT para o qual a carga está sendo calculada.
            O campo `device.id` é utilizado como identificador para a
            geração determinística do ruído.
        t_seconds:
            Instante de tempo em segundos. Pode ser o tempo absoluto
            da simulação; internamente, o perfil diário faz a redução
            módulo o período diário configurado.
        config:
            Configuração de processo de carga para este dispositivo.

    Retorno:
        Carga instantânea do dispositivo no instante `t_seconds`,
        limitada ao intervalo [P_min, P_max].
    """
    avg_power = device.avg_power
    if avg_power <= 0.0:
        return 0.0

    p_min = max(0.0, config.min_fraction_of_avg * avg_power)
    p_max = config.max_fraction_of_avg * avg_power

    if p_max <= p_min:
        # Configuração degenerada: evita resultados inconsistentes.
        return p_min

    # 1) Perfil diário determinístico em [0, 1]
    f_base = daily_profile_value(config.daily_profile, t_seconds)

    # 2) Ruído relativo em [-ε, +ε]
    n = noise_value(config.noise, device.id, t_seconds)

    # 3) Potência base no intervalo [P_min, P_max]
    p_base = p_min + f_base * (p_max - p_min)

    # 4) Aplica ruído multiplicativo
    p = p_base * (1.0 + n)

    # 5) Recorte para [P_min, P_max]
    if p < p_min:
        p = p_min
    if p > p_max:
        p = p_max

    return p


def update_devices_current_power(
    devices: Dict[str, IoTDevice],
    config_map: Dict[str, DeviceLoadConfig],
    t_seconds: float,
) -> None:
    """
    Atualiza o campo `current_power` de vários dispositivos em um instante de tempo.

    Esta função é pensada para ser chamada de forma "lazy" sempre que
    for necessário obter uma fotografia (snapshot) do consumo instantâneo
    dos dispositivos na rede. Ela não mantém estado de simulação entre
    chamadas: para cada dispositivo presente em `config_map`:

        - localiza o dispositivo em `devices` pelo seu identificador;
        - calcula a carga no instante `t_seconds` com `compute_device_power`;
        - atribui o resultado ao campo `device.current_power`.

    Dispositivos que não estiverem presentes em `config_map` não são
    alterados. Da mesma forma, entradas em `config_map` cujo
    identificador não conste em `devices` são simplesmente ignoradas.

    Parâmetros:
        devices:
            Dicionário de dispositivos indexados por `device.id`.
            Geralmente construído a partir de todas as instâncias de
            `IoTDevice` criadas na simulação (por exemplo, um mapa
            global `device_id -> IoTDevice`).
        config_map:
            Mapeamento de `device_id` para `DeviceLoadConfig`. Somente
            dispositivos presentes neste mapa terão suas cargas
            atualizadas.
        t_seconds:
            Instante de tempo em segundos a ser utilizado no cálculo das
            cargas instantâneas.
    """
    for device_id, cfg in config_map.items():
        device = devices.get(device_id)
        if device is None:
            continue
        device.current_power = compute_device_power(device, t_seconds, cfg)


__all__: Sequence[str] = [
    "DeviceLoadConfig",
    "make_load_config_from_template",
    "compute_device_power",
    "update_devices_current_power",
]
