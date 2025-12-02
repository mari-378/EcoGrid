from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional, Sequence


class DeviceType(Enum):
    """
    Tipos semânticos de dispositivos IoT consumidores de energia.
    """
    TV = "TV"
    FRIDGE = "FRIDGE"
    AIR_CONDITIONER = "AIR_CONDITIONER"
    SHOWER = "SHOWER"
    WASHER = "WASHER"
    MICROWAVE = "MICROWAVE"
    IRON = "IRON"
    PC = "PC"
    FAN = "FAN"
    LIGHTING = "LIGHTING"
    DRYER = "DRYER"
    AIR_FRYER = "AIR_FRYER"
    BLENDER = "BLENDER"
    TOASTER = "TOASTER"
    VACUUM = "VACUUM"
    COFFEE_MAKER = "COFFEE_MAKER"
    OVEN = "OVEN"
    GENERIC = "GENERIC"


@dataclass
class IoTDevice:
    """
    Representa um dispositivo IoT consumidor de energia conectado a um nó.
    """
    id: str
    name: str
    device_type: DeviceType
    avg_power: float
    current_power: Optional[float] = None


__all__: Sequence[str] = ["DeviceType", "IoTDevice"]
