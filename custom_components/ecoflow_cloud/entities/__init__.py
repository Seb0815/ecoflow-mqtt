from __future__ import annotations

from typing import Any

# Minimal standalone domain for MQTT publishing
ECOFLOW_DOMAIN = "ecoflow_cloud"

# Simple data holder classes for device information
class DeviceInfo:
    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)

# Minimal Entity-Klassen für Kompatibilität - werden nicht wirklich verwendet
class Entity:
    """Basis Entity-Klasse für Standalone Betrieb"""
    pass

class SensorEntity(Entity):
    pass

class BaseSensorEntity(SensorEntity):
    """Basis Sensor Entity für Device-Klassen"""
    pass

class NumberEntity(Entity):
    pass

class BaseNumberEntity(NumberEntity):
    """Basis Number Entity für Device-Klassen"""
    pass

class SwitchEntity(Entity):
    pass

class BaseSwitchEntity(SwitchEntity):
    """Basis Switch Entity für Device-Klassen"""
    pass

class SelectEntity(Entity):
    pass

class BaseSelectEntity(SelectEntity):
    """Basis Select Entity für Device-Klassen"""
    pass

class ButtonEntity(Entity):
    pass
