from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Sequence
import random

from physical.device_model import IoTDevice
from physical.device_catalog import DeviceTemplate
from physical.load_profiles import DailyProfileConfig
from physical.load_noise import NoiseConfig


@dataclass
class DeviceLoadConfig:
    """
    Configuração do processo de carga de um dispositivo IoT.
    Mantido para compatibilidade de interface, mas a lógica agora é simplificada.
    """
    daily_profile: DailyProfileConfig
    noise: NoiseConfig
    min_fraction_of_avg: float
    max_fraction_of_avg: float


def make_load_config_from_template(template: DeviceTemplate) -> DeviceLoadConfig:
    """
    Cria uma configuração de processo de carga a partir de um template.
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
    Calcula a carga instantânea de um dispositivo.

    Nova Lógica Regularizada:
    A potência atual deve variar, no máximo, entre 20% e -20% em torno
    do valor potência média (avg_power).

    Ou seja:
    avg_power * 0.8 <= current_power <= avg_power * 1.2

    A implementação utiliza um valor aleatório simples dentro deste intervalo
    para garantir a variação solicitada sem a complexidade de perfis diários,
    conforme solicitado ("Regularize o algoritmo...").
    """
    avg_power = device.avg_power
    if avg_power <= 0.0:
        return 0.0

    # Variação aleatória entre -20% e +20%
    variation = random.uniform(-0.20, 0.20)

    current = avg_power * (1.0 + variation)

    # Restrição explícita (Hard Clamp) para garantir que erros de
    # ponto flutuante não violem os limites solicitados.
    min_limit = avg_power * 0.8
    max_limit = avg_power * 1.2

    # Se avg_power for negativo (incomum), os limites se invertem.
    # Mas assumimos avg_power >= 0 aqui.
    if current < min_limit:
        current = min_limit
    elif current > max_limit:
        current = max_limit

    return current


def update_devices_current_power(
    devices: Dict[str, IoTDevice],
    config_map: Dict[str, DeviceLoadConfig],
    t_seconds: float,
) -> None:
    """
    Atualiza o campo `current_power` de vários dispositivos.
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
