"""
Docker-kompatible Version von sensor.py ohne Home Assistant Dependencies
Ersetzt alle Home Assistant Imports durch minimal-Implementierungen
"""
import enum
import logging
import struct
from typing import Any, Mapping, OrderedDict
from datetime import datetime, timezone

# Python 3.11 compatibility: override is only available in 3.12+
try:
    from typing import override
except ImportError:
    # Fallback for Python < 3.12
    def override(func):
        return func

_LOGGER = logging.getLogger(__name__)

# Minimal Docker-kompatible Ersatz-Implementierungen für Home Assistant Klassen

class EntityCategory:
    """Minimal EntityCategory Ersatz"""
    DIAGNOSTIC = "diagnostic"
    CONFIG = "config"

class SensorDeviceClass:
    """Minimal SensorDeviceClass Ersatz"""
    BATTERY = "battery"
    VOLTAGE = "voltage"
    CURRENT = "current"
    POWER = "power"
    ENERGY = "energy"
    TEMPERATURE = "temperature"
    DURATION = "duration"
    FREQUENCY = "frequency"

class SensorStateClass:
    """Minimal SensorStateClass Ersatz"""
    MEASUREMENT = "measurement"
    TOTAL_INCREASING = "total_increasing"

class BinarySensorDeviceClass:
    """Minimal BinarySensorDeviceClass Ersatz"""
    BATTERY_CHARGING = "battery_charging"

class UnitConstants:
    """Docker-kompatible Unit-Konstanten"""
    PERCENTAGE = "%"
    VOLT = "V"
    MILLIVOLT = "mV"
    AMPERE = "A"
    MILLIAMPERE = "mA"
    WATT = "W"
    WATT_HOUR = "Wh"
    CELSIUS = "°C"
    MINUTES = "min"
    SECONDS = "s"
    HERTZ = "Hz"

class DateTimeUtil:
    """Docker-kompatible DateTime Utilities"""
    @staticmethod
    def utcnow():
        return datetime.now(timezone.utc)
    
    @staticmethod
    def as_timestamp(dt):
        return dt.timestamp()

# Base Entity Klassen (minimal für Docker)
class DockerSensorEntity:
    """Minimal Sensor Entity Base Class für Docker"""
    def __init__(self, client=None, device=None, key=None, title=None, enabled=True):
        self.client = client
        self.device = device
        self.attr_key = key
        self.title = title
        self.enabled = enabled
        self._attr_native_value = None
        self._attr_native_unit_of_measurement = None
        self._attr_device_class = None
        self._attr_state_class = None
        self._attr_entity_category = None
        self._attr_icon = None
        self._attr_suggested_unit_of_measurement = None
        self._attr_suggested_display_precision = None
        self._attr_force_update = False
    
    def _update_value(self, val: Any) -> bool:
        """Update the sensor value - to be overridden by subclasses"""
        self._attr_native_value = val
        return True

class DockerBinarySensorEntity(DockerSensorEntity):
    """Minimal Binary Sensor Entity für Docker"""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._attr_is_on = None

# Alle Sensor-Klassen mit Docker-kompatiblen Base-Klassen

class ChargingStateSensorEntity(DockerSensorEntity):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._attr_entity_category = EntityCategory.DIAGNOSTIC
        self._attr_icon = "mdi:battery-charging"
        self._attr_device_class = BinarySensorDeviceClass.BATTERY_CHARGING

    def _update_value(self, val: Any) -> bool:
        if val == 0:
            return super()._update_value("unused")
        elif val == 1:
            return super()._update_value("charging")
        elif val == 2:
            return super()._update_value("discharging")
        else:
            return False

class CyclesSensorEntity(DockerSensorEntity):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._attr_entity_category = EntityCategory.DIAGNOSTIC
        self._attr_icon = "mdi:battery-heart-variant"
        self._attr_state_class = SensorStateClass.TOTAL_INCREASING

class FanSensorEntity(DockerSensorEntity):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_icon = "mdi:fan"

class MiscSensorEntity(DockerSensorEntity):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._attr_entity_category = EntityCategory.DIAGNOSTIC

class LevelSensorEntity(DockerSensorEntity):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._attr_device_class = SensorDeviceClass.BATTERY
        self._attr_native_unit_of_measurement = UnitConstants.PERCENTAGE
        self._attr_state_class = SensorStateClass.MEASUREMENT

class RemainSensorEntity(DockerSensorEntity):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._attr_device_class = SensorDeviceClass.DURATION
        self._attr_native_unit_of_measurement = UnitConstants.MINUTES
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_native_value = 0

    def _update_value(self, val: Any) -> Any:
        ival = int(val)
        if ival < 0 or ival > 5000:
            ival = 0
        return super()._update_value(ival)

class SecondsRemainSensorEntity(DockerSensorEntity):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._attr_device_class = SensorDeviceClass.DURATION
        self._attr_native_unit_of_measurement = UnitConstants.SECONDS
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_native_value = 0

    def _update_value(self, val: Any) -> Any:
        ival = int(val)
        if ival < 0 or ival > 5000:
            ival = 0
        return super()._update_value(ival)

class TempSensorEntity(DockerSensorEntity):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._attr_device_class = SensorDeviceClass.TEMPERATURE
        self._attr_entity_category = EntityCategory.DIAGNOSTIC
        self._attr_native_unit_of_measurement = UnitConstants.CELSIUS
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_native_value = -1

class CelsiusSensorEntity(TempSensorEntity):
    def _update_value(self, val: Any) -> bool:
        return super()._update_value(int(val))

class DecicelsiusSensorEntity(TempSensorEntity):
    def _update_value(self, val: Any) -> bool:
        return super()._update_value(int(val) / 10)

class MilliCelsiusSensorEntity(TempSensorEntity):
    def _update_value(self, val: Any) -> bool:
        return super()._update_value(int(val) / 100)

class VoltSensorEntity(DockerSensorEntity):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._attr_device_class = SensorDeviceClass.VOLTAGE
        self._attr_entity_category = EntityCategory.DIAGNOSTIC
        self._attr_native_unit_of_measurement = UnitConstants.VOLT
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_native_value = 0

class MilliVoltSensorEntity(DockerSensorEntity):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._attr_device_class = SensorDeviceClass.VOLTAGE
        self._attr_entity_category = EntityCategory.DIAGNOSTIC
        self._attr_native_unit_of_measurement = UnitConstants.MILLIVOLT
        self._attr_suggested_unit_of_measurement = UnitConstants.VOLT
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_native_value = 3

class BeSensorEntity(DockerSensorEntity):
    def _update_value(self, val: Any) -> bool:
        return super()._update_value(
            int(struct.unpack("<I", struct.pack(">I", val))[0])
        )

class BeMilliVoltSensorEntity(BeSensorEntity):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._attr_device_class = SensorDeviceClass.VOLTAGE
        self._attr_entity_category = EntityCategory.DIAGNOSTIC
        self._attr_native_unit_of_measurement = UnitConstants.MILLIVOLT
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_native_value = 0

class DeciMilliVoltSensorEntity(MilliVoltSensorEntity):
    def _update_value(self, val: Any) -> bool:
        return super()._update_value(int(val) / 10)

class InMilliVoltSensorEntity(MilliVoltSensorEntity):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._attr_icon = "mdi:transmission-tower-import"
        self._attr_suggested_display_precision = 0

class OutMilliVoltSensorEntity(MilliVoltSensorEntity):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._attr_icon = "mdi:transmission-tower-export"
        self._attr_suggested_display_precision = 0

class DecivoltSensorEntity(DockerSensorEntity):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._attr_device_class = SensorDeviceClass.VOLTAGE
        self._attr_entity_category = EntityCategory.DIAGNOSTIC
        self._attr_native_unit_of_measurement = UnitConstants.VOLT
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_native_value = 0

    def _update_value(self, val: Any) -> bool:
        return super()._update_value(int(val) / 10)

class CentivoltSensorEntity(DecivoltSensorEntity):
    def _update_value(self, val: Any) -> bool:
        return super()._update_value(int(val) / 10)

class AmpSensorEntity(DockerSensorEntity):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._attr_device_class = SensorDeviceClass.CURRENT
        self._attr_entity_category = EntityCategory.DIAGNOSTIC
        self._attr_native_unit_of_measurement = UnitConstants.AMPERE
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_native_value = 0

class MilliampSensorEntity(DockerSensorEntity):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._attr_device_class = SensorDeviceClass.CURRENT
        self._attr_entity_category = EntityCategory.DIAGNOSTIC
        self._attr_native_unit_of_measurement = UnitConstants.MILLIAMPERE
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_native_value = 0

class DeciampSensorEntity(DockerSensorEntity):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._attr_device_class = SensorDeviceClass.CURRENT
        self._attr_entity_category = EntityCategory.DIAGNOSTIC
        self._attr_native_unit_of_measurement = UnitConstants.AMPERE
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_native_value = 0

    def _update_value(self, val: Any) -> bool:
        return super()._update_value(int(val) / 10)

class WattsSensorEntity(DockerSensorEntity):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._attr_entity_category = EntityCategory.DIAGNOSTIC
        self._attr_device_class = SensorDeviceClass.POWER
        self._attr_native_unit_of_measurement = UnitConstants.WATT
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_native_value = 0

class EnergySensorEntity(DockerSensorEntity):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._attr_device_class = SensorDeviceClass.ENERGY
        self._attr_native_unit_of_measurement = UnitConstants.WATT_HOUR
        self._attr_state_class = SensorStateClass.TOTAL_INCREASING

    def _update_value(self, val: Any) -> bool:
        ival = int(val)
        if ival > 0:
            return super()._update_value(ival)
        else:
            return False

class CapacitySensorEntity(DockerSensorEntity):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._attr_native_unit_of_measurement = "mAh"
        self._attr_state_class = SensorStateClass.MEASUREMENT

class CumulativeCapacitySensorEntity(CapacitySensorEntity):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._attr_state_class = SensorStateClass.TOTAL_INCREASING

    def _update_value(self, val: Any) -> bool:
        ival = int(val)
        if ival > 0:
            return super()._update_value(ival)
        else:
            return False

class DeciwattsSensorEntity(WattsSensorEntity):
    def _update_value(self, val: Any) -> bool:
        return super()._update_value(int(val) / 10)

class InWattsSensorEntity(WattsSensorEntity):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._attr_icon = "mdi:transmission-tower-import"

class InWattsSolarSensorEntity(InWattsSensorEntity):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._attr_icon = "mdi:solar-power"

    def _update_value(self, val: Any) -> bool:
        return super()._update_value(int(val) / 10)

class InRawWattsSolarSensorEntity(InWattsSensorEntity):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._attr_icon = "mdi:solar-power"

class InRawTotalWattsSolarSensorEntity(InRawWattsSolarSensorEntity):
    def _update_value(self, val: Any) -> bool:
        return super()._update_value(int(val) / 1000)

class InRawWattsAltSensorEntity(InWattsSensorEntity):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._attr_icon = "mdi:engine"

class OutWattsSensorEntity(WattsSensorEntity):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._attr_icon = "mdi:transmission-tower-export"

class OutWattsDcSensorEntity(WattsSensorEntity):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._attr_icon = "mdi:transmission-tower-export"

    def _update_value(self, val: Any) -> bool:
        return super()._update_value(int(val) / 10)

class InVoltSensorEntity(VoltSensorEntity):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._attr_icon = "mdi:transmission-tower-import"

class InVoltSolarSensorEntity(VoltSensorEntity):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._attr_icon = "mdi:solar-power"

    def _update_value(self, val: Any) -> bool:
        return super()._update_value(int(val) / 10)

class OutVoltDcSensorEntity(VoltSensorEntity):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._attr_icon = "mdi:transmission-tower-export"

    def _update_value(self, val: Any) -> bool:
        return super()._update_value(int(val) / 10)

class OutAmpSensorEntity(AmpSensorEntity):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._attr_icon = "mdi:transmission-tower-export"

class InAmpSensorEntity(AmpSensorEntity):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._attr_icon = "mdi:transmission-tower-import"

class OutMilliampSensorEntity(MilliampSensorEntity):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._attr_icon = "mdi:transmission-tower-export"

class InMilliampSensorEntity(MilliampSensorEntity):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._attr_icon = "mdi:transmission-tower-import"

class InMilliampSolarSensorEntity(MilliampSensorEntity):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._attr_icon = "mdi:solar-power"

    def _update_value(self, val: Any) -> bool:
        return super()._update_value(int(val) * 10)

class InEnergySensorEntity(EnergySensorEntity):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._attr_icon = "mdi:transmission-tower-import"

class OutEnergySensorEntity(EnergySensorEntity):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._attr_icon = "mdi:transmission-tower-export"

class InEnergySolarSensorEntity(InEnergySensorEntity):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._attr_icon = "mdi:solar-power"

class _ResettingMixin(EnergySensorEntity):
    @override
    def _update_value(self, val: Any) -> bool:
        # Skip the "if val == 0: False" logic
        return super(EnergySensorEntity, self)._update_value(val)

class ResettingInEnergySensorEntity(_ResettingMixin, InEnergySensorEntity):
    pass

class ResettingInEnergySolarSensorEntity(_ResettingMixin, InEnergySolarSensorEntity):
    pass

class ResettingOutEnergySensorEntity(_ResettingMixin, OutEnergySensorEntity):
    pass

class FrequencySensorEntity(DockerSensorEntity):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._attr_device_class = SensorDeviceClass.FREQUENCY
        self._attr_entity_category = EntityCategory.DIAGNOSTIC
        self._attr_native_unit_of_measurement = UnitConstants.HERTZ
        self._attr_state_class = SensorStateClass.MEASUREMENT

class DecihertzSensorEntity(FrequencySensorEntity):
    def _update_value(self, val: Any) -> bool:
        return super()._update_value(int(val) / 10)

# Weitere komplexere Klassen (vereinfacht für Docker)
class MiscBinarySensorEntity(DockerBinarySensorEntity):
    def _update_value(self, val: Any) -> bool:
        self._attr_is_on = bool(val)
        return True

# Utility Funktionen
def extract_sensor_parameters_from_device_class(device_class) -> set:
    """
    Extrahiert alle Parameter-Namen aus einer Device-Klasse durch Analyse der sensors() Methode
    """
    defined_params = set()
    
    try:
        if hasattr(device_class, 'sensors') and callable(device_class.sensors):
            # Erstelle eine Dummy-Instanz um die sensors() Methode zu analysieren
            import inspect
            
            # Hole die Sensor-Definitionen aus dem Quellcode der sensors() Methode
            source = inspect.getsource(device_class.sensors)
            
            # Regex um Parameter-Namen zu extrahieren (dritter Parameter bei Sensor-Konstruktoren)
            import re
            
            # Suche nach Sensor-Entity Konstruktoren mit 3+ Parametern
            # Pattern für: SensorEntity(client, self, "parameter_name", ...)
            patterns = [
                r'(\w+SensorEntity)\(client,\s*self,\s*["\']([^"\']+)["\']',  # Quoted parameter
                r'(\w+SensorEntity)\(client,\s*self,\s*([a-zA-Z_][a-zA-Z0-9_]*)',  # Variable parameter
                # Pattern für Kommentare mit Parameter-Namen: # "parameterName": value,
                r'#\s*["\']([^"\']+)["\']\s*:',  # Parameter in Kommentaren
            ]
            
            for pattern in patterns:
                matches = re.findall(pattern, source)
                for match in matches:
                    if len(match) == 2:  # Sensor Entity Pattern
                        sensor_type, param_name = match
                    else:  # Comment Pattern
                        param_name = match
                        
                    # Entferne Anführungszeichen falls vorhanden und bereinige
                    param_name = param_name.strip('"\'')
                    
                    # Ignoriere const.* Referenzen und andere spezielle Fälle
                    if (param_name and 
                        not param_name.startswith('const.') and
                        not param_name.startswith('_') and
                        param_name.isidentifier() and
                        len(param_name) > 2):
                        defined_params.add(param_name)
                        _LOGGER.debug(f"Found parameter: {param_name}")
        
        _LOGGER.info(f"Extracted {len(defined_params)} parameters from device class")
        return defined_params
        
    except Exception as e:
        _LOGGER.debug(f"Failed to extract parameters from device class: {e}")
        return set()

def extract_parameters_from_source_comments(source_code: str) -> set:
    """
    Extrahiert Parameter-Namen aus Kommentaren im Quellcode
    Erkennt Patterns wie: # "parameterName": value,
    """
    import re
    
    defined_params = set()
    
    # Pattern für JSON-ähnliche Kommentare
    comment_patterns = [
        r'#\s*["\']([a-zA-Z][a-zA-Z0-9_]*)["\']:\s*[^,\n]+',  # "param": value
        r'#\s*([a-zA-Z][a-zA-Z0-9_]*)\s*:\s*[^,\n]+',         # param: value  
    ]
    
    for pattern in comment_patterns:
        matches = re.findall(pattern, source_code)
        for param_name in matches:
            if (param_name and 
                param_name.isidentifier() and 
                len(param_name) > 2 and
                not param_name.startswith('_')):
                defined_params.add(param_name)
    
    return defined_params
