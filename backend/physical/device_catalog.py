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
    """
    device_type: DeviceType
    default_name: str
    avg_power: float
    daily_profile: DailyProfileConfig
    noise: NoiseConfig
    min_fraction_of_avg: float
    max_fraction_of_avg: float


def _residential_daily_profile() -> DailyProfileConfig:
    return DailyProfileConfig(
        profile_type=DailyProfileType.RESIDENTIAL,
        day_period_seconds=24.0 * 3600.0,
        phase_shift_seconds=0.0,
        amplitude_factor=1.0,
    )


def _flat_daily_profile() -> DailyProfileConfig:
    return DailyProfileConfig(
        profile_type=DailyProfileType.FLAT,
        day_period_seconds=24.0 * 3600.0,
        phase_shift_seconds=0.0,
        amplitude_factor=1.0,
    )


def _default_noise(amplitude: float) -> NoiseConfig:
    return NoiseConfig(
        block_duration_seconds=60.0,
        amplitude=amplitude,
        seed_base=12345,
    )


def get_device_template(device_type: DeviceType) -> DeviceTemplate:
    """
    Retorna um template padrão para o tipo de dispositivo informado.
    """

    # Mapping based on user requirement
    # ID -> (Name, Avg Power kW)
    # TV -> TV, 0.095
    # FRIDGE -> Geladeira, 0.200
    # AIR_CONDITIONER -> Ar Condicionado, 1.100
    # SHOWER -> Chuveiro Elétrico, 6.500
    # WASHER -> Máquina de Lavar, 0.500
    # MICROWAVE -> Micro-ondas, 1.200
    # IRON -> Ferro de Passar, 1.000
    # PC -> Computador, 0.200
    # FAN -> Ventilador, 0.080
    # LIGHTING -> Iluminação, 0.030
    # DRYER -> Secadora, 1.500
    # AIR_FRYER -> Fritadeira, 1.400
    # BLENDER -> Liquidificador, 0.300
    # TOASTER -> Torradeira, 0.800
    # VACUUM -> Aspirador de Pó, 0.600
    # COFFEE_MAKER -> Cafeteira, 0.600
    # OVEN -> Forno Elétrico, 1.500
    # GENERIC -> Outros / Genérico, 0.100

    catalog = {
        DeviceType.TV: ("TV", 0.095),
        DeviceType.FRIDGE: ("Geladeira", 0.200),
        DeviceType.AIR_CONDITIONER: ("Ar Condicionado", 1.100),
        DeviceType.SHOWER: ("Chuveiro Elétrico", 6.500),
        DeviceType.WASHER: ("Máquina de Lavar", 0.500),
        DeviceType.MICROWAVE: ("Micro-ondas", 1.200),
        DeviceType.IRON: ("Ferro de Passar", 1.000),
        DeviceType.PC: ("Computador", 0.200),
        DeviceType.FAN: ("Ventilador", 0.080),
        DeviceType.LIGHTING: ("Iluminação", 0.030),
        DeviceType.DRYER: ("Secadora", 1.500),
        DeviceType.AIR_FRYER: ("Fritadeira", 1.400),
        DeviceType.BLENDER: ("Liquidificador", 0.300),
        DeviceType.TOASTER: ("Torradeira", 0.800),
        DeviceType.VACUUM: ("Aspirador de Pó", 0.600),
        DeviceType.COFFEE_MAKER: ("Cafeteira", 0.600),
        DeviceType.OVEN: ("Forno Elétrico", 1.500),
        DeviceType.GENERIC: ("Outros / Genérico", 0.100),
    }

    if device_type in catalog:
        name, avg_power = catalog[device_type]
        # Use flat profile for Fridge and Generic, Residential for others roughly
        # Or better yet, stick to simple profiles as defaults
        profile = _flat_daily_profile() if device_type == DeviceType.FRIDGE else _residential_daily_profile()

        return DeviceTemplate(
            device_type=device_type,
            default_name=name,
            avg_power=avg_power,
            daily_profile=profile,
            noise=_default_noise(amplitude=0.1),
            min_fraction_of_avg=0.0,
            max_fraction_of_avg=2.0,
        )

    # Fallback should not happen given the enum coverage but just in case
    return DeviceTemplate(
        device_type=device_type,
        default_name="Unknown",
        avg_power=0.1,
        daily_profile=_flat_daily_profile(),
        noise=_default_noise(0.1),
        min_fraction_of_avg=0.0,
        max_fraction_of_avg=2.0
    )


def get_default_avg_power(device_type: DeviceType) -> float:
    return get_device_template(device_type).avg_power


__all__: Sequence[str] = ["DeviceTemplate", "get_device_template", "get_default_avg_power"]
