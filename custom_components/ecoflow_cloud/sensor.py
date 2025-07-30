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

# Docker-kompatible Fallbacks für Home Assistant Imports
try:
    from homeassistant.components.binary_sensor import (
        BinarySensorDeviceClass,
        BinarySensorEntity,
    )
    from homeassistant.components.sensor import (
        SensorDeviceClass,
        SensorEntity,
        SensorStateClass,
    )
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.const import (
        PERCENTAGE,
        UnitOfElectricCurrent,
        UnitOfElectricPotential,
        UnitOfEnergy,
        UnitOfFrequency,
        UnitOfPower,
        UnitOfTemperature,
        UnitOfTime,
    )
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity import EntityCategory
    from homeassistant.helpers.entity_platform import AddEntitiesCallback
    from homeassistant.util import dt
    
    # Home Assistant ist verfügbar
    HOMEASSISTANT_AVAILABLE = True
    
except ImportError:
    # Docker-kompatible Fallbacks wenn Home Assistant nicht verfügbar ist
    HOMEASSISTANT_AVAILABLE = False
    
    # Minimal EntityCategory Ersatz
    class EntityCategory:
        DIAGNOSTIC = "diagnostic"
        CONFIG = "config"
    
    # Minimal SensorDeviceClass Ersatz
    class SensorDeviceClass:
        BATTERY = "battery"
        VOLTAGE = "voltage"
        CURRENT = "current"
        POWER = "power"
        ENERGY = "energy"
        TEMPERATURE = "temperature"
        DURATION = "duration"
        FREQUENCY = "frequency"
    
    # Minimal SensorStateClass Ersatz
    class SensorStateClass:
        MEASUREMENT = "measurement"
        TOTAL_INCREASING = "total_increasing"
    
    # Minimal BinarySensorDeviceClass Ersatz
    class BinarySensorDeviceClass:
        BATTERY_CHARGING = "battery_charging"
    
    # Unit-Konstanten
    PERCENTAGE = "%"
    
    class UnitOfElectricCurrent:
        AMPERE = "A"
        MILLIAMPERE = "mA"
    
    class UnitOfElectricPotential:
        VOLT = "V"
        MILLIVOLT = "mV"
    
    class UnitOfEnergy:
        WATT_HOUR = "Wh"
    
    class UnitOfFrequency:
        HERTZ = "Hz"
    
    class UnitOfPower:
        WATT = "W"
    
    class UnitOfTemperature:
        CELSIUS = "°C"
    
    class UnitOfTime:
        MINUTES = "min"
        SECONDS = "s"
    
    # DateTime Utilities
    class dt:
        @staticmethod
        def utcnow():
            return datetime.now(timezone.utc)
        
        @staticmethod
        def as_timestamp(dt_obj):
            return dt_obj.timestamp()
    
    # Dummy-Klassen für Docker
    class SensorEntity:
        def __init__(self, *args, **kwargs):
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
            self._attr_native_value = val
            return True
    
    class BinarySensorEntity:
        def __init__(self, *args, **kwargs):
            self._attr_is_on = None
        
        def _update_value(self, val: Any) -> bool:
            self._attr_is_on = bool(val)
            return True
    
    # Dummy für nicht verfügbare Imports
    ConfigEntry = None
    HomeAssistant = None
    AddEntitiesCallback = None

# Docker-kompatible Konstanten-Imports
try:
    from . import (
        ATTR_MQTT_CONNECTED,
        ATTR_QUOTA_REQUESTS,
        ATTR_STATUS_DATA_LAST_UPDATE,
        ATTR_STATUS_PHASE,
        ATTR_STATUS_RECONNECTS,
        ATTR_STATUS_SN,
        ECOFLOW_DOMAIN,
    )
except ImportError:
    # Docker-kompatible Fallback-Konstanten
    ATTR_MQTT_CONNECTED = "mqtt_connected"
    ATTR_QUOTA_REQUESTS = "quota_requests"
    ATTR_STATUS_DATA_LAST_UPDATE = "status_data_last_update"
    ATTR_STATUS_PHASE = "status_phase"
    ATTR_STATUS_RECONNECTS = "status_reconnects"
    ATTR_STATUS_SN = "status_sn"
    ECOFLOW_DOMAIN = "ecoflow_cloud"

from .api import EcoflowApiClient
from .devices import BaseDevice

# Docker-kompatible Entity-Imports
try:
    from .entities import (
        BaseSensorEntity,
        EcoFlowAbstractEntity,
        EcoFlowDictEntity,
    )
except ImportError:
    # Docker-kompatible Fallback-Klassen
    class BaseSensorEntity:
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
            self._attr_native_value = val
            return True
    
    class EcoFlowAbstractEntity:
        def __init__(self, client=None, device=None, title=None, key=None):
            self.client = client
            self.device = device
            self.title = title
            self.key = key
            self.coordinator = None
        
        def schedule_update_ha_state(self):
            pass
    
    class EcoFlowDictEntity(EcoFlowAbstractEntity):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.params = {}
        
        def _handle_coordinator_update(self):
            pass

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass, entry, async_add_entities
):
    """Setup entry - nur verfügbar wenn Home Assistant vorhanden ist"""
    if not HOMEASSISTANT_AVAILABLE:
        _LOGGER.warning("async_setup_entry called but Home Assistant not available")
        return
    
    client = hass.data[ECOFLOW_DOMAIN][entry.entry_id]
    for sn, device in client.devices.items():
        async_add_entities(device.sensors(client))


class MiscBinarySensorEntity(BinarySensorEntity, EcoFlowDictEntity):
    def _update_value(self, val: Any) -> bool:
        self._attr_is_on = bool(val)
        return True


class ChargingStateSensorEntity(BaseSensorEntity):
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = "mdi:battery-charging"
    _attr_device_class = BinarySensorDeviceClass.BATTERY_CHARGING

    def _update_value(self, val: Any) -> bool:
        if val == 0:
            return super()._update_value("unused")
        elif val == 1:
            return super()._update_value("charging")
        elif val == 2:
            return super()._update_value("discharging")
        else:
            return False


class CyclesSensorEntity(BaseSensorEntity):
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = "mdi:battery-heart-variant"
    _attr_state_class = SensorStateClass.TOTAL_INCREASING


class FanSensorEntity(BaseSensorEntity):
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:fan"


class MiscSensorEntity(BaseSensorEntity):
    _attr_entity_category = EntityCategory.DIAGNOSTIC


class LevelSensorEntity(BaseSensorEntity):
    _attr_device_class = SensorDeviceClass.BATTERY
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_state_class = SensorStateClass.MEASUREMENT


class RemainSensorEntity(BaseSensorEntity):
    _attr_device_class = SensorDeviceClass.DURATION
    _attr_native_unit_of_measurement = UnitOfTime.MINUTES
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_value = 0

    def _update_value(self, val: Any) -> Any:
        ival = int(val)
        if ival < 0 or ival > 5000:
            ival = 0

        return super()._update_value(ival)


class SecondsRemainSensorEntity(BaseSensorEntity):
    _attr_device_class = SensorDeviceClass.DURATION
    _attr_native_unit_of_measurement = UnitOfTime.SECONDS
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_value = 0

    def _update_value(self, val: Any) -> Any:
        ival = int(val)
        if ival < 0 or ival > 5000:
            ival = 0

        return super()._update_value(ival)


class TempSensorEntity(BaseSensorEntity):
    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_value = -1


class CelsiusSensorEntity(TempSensorEntity):
    def _update_value(self, val: Any) -> bool:
        return super()._update_value(int(val))


class DecicelsiusSensorEntity(TempSensorEntity):
    def _update_value(self, val: Any) -> bool:
        return super()._update_value(int(val) / 10)


class MilliCelsiusSensorEntity(TempSensorEntity):
    def _update_value(self, val: Any) -> bool:
        return super()._update_value(int(val) / 100)


class VoltSensorEntity(BaseSensorEntity):
    _attr_device_class = SensorDeviceClass.VOLTAGE
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_native_unit_of_measurement = UnitOfElectricPotential.VOLT
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_value = 0


class MilliVoltSensorEntity(BaseSensorEntity):
    _attr_device_class = SensorDeviceClass.VOLTAGE
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_native_unit_of_measurement = UnitOfElectricPotential.MILLIVOLT
    _attr_suggested_unit_of_measurement = UnitOfElectricPotential.VOLT
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_value = 3


class BeSensorEntity(BaseSensorEntity):
    def _update_value(self, val: Any) -> bool:
        return super()._update_value(
            int(struct.unpack("<I", struct.pack(">I", val))[0])
        )


class BeMilliVoltSensorEntity(BeSensorEntity):
    _attr_device_class = SensorDeviceClass.VOLTAGE
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_native_unit_of_measurement = UnitOfElectricPotential.MILLIVOLT
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_value = 0


class DeciMilliVoltSensorEntity(MilliVoltSensorEntity):
    def _update_value(self, val: Any) -> bool:
        return super()._update_value(int(val) / 10)


class InMilliVoltSensorEntity(MilliVoltSensorEntity):
    _attr_icon = "mdi:transmission-tower-import"
    _attr_suggested_display_precision = 0


class OutMilliVoltSensorEntity(MilliVoltSensorEntity):
    _attr_icon = "mdi:transmission-tower-export"
    _attr_suggested_display_precision = 0


class DecivoltSensorEntity(BaseSensorEntity):
    _attr_device_class = SensorDeviceClass.VOLTAGE
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_native_unit_of_measurement = UnitOfElectricPotential.VOLT
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_value = 0

    def _update_value(self, val: Any) -> bool:
        return super()._update_value(int(val) / 10)


class CentivoltSensorEntity(DecivoltSensorEntity):
    def _update_value(self, val: Any) -> bool:
        return super()._update_value(int(val) / 10)


class AmpSensorEntity(BaseSensorEntity):
    _attr_device_class = SensorDeviceClass.CURRENT
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_native_unit_of_measurement = UnitOfElectricCurrent.AMPERE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_value = 0


class MilliampSensorEntity(BaseSensorEntity):
    _attr_device_class = SensorDeviceClass.CURRENT
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_native_unit_of_measurement = UnitOfElectricCurrent.MILLIAMPERE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_value = 0


class DeciampSensorEntity(BaseSensorEntity):
    _attr_device_class = SensorDeviceClass.CURRENT
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_native_unit_of_measurement = UnitOfElectricCurrent.AMPERE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_value = 0

    def _update_value(self, val: Any) -> bool:
        return super()._update_value(int(val) / 10)


class WattsSensorEntity(BaseSensorEntity):
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_device_class = SensorDeviceClass.POWER
    _attr_native_unit_of_measurement = UnitOfPower.WATT
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_value = 0


class EnergySensorEntity(BaseSensorEntity):
    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_native_unit_of_measurement = UnitOfEnergy.WATT_HOUR
    _attr_state_class = SensorStateClass.TOTAL_INCREASING

    def _update_value(self, val: Any) -> bool:
        ival = int(val)
        if ival > 0:
            return super()._update_value(ival)
        else:
            return False


class CapacitySensorEntity(BaseSensorEntity):
    _attr_native_unit_of_measurement = "mAh"
    _attr_state_class = SensorStateClass.MEASUREMENT


class CumulativeCapacitySensorEntity(CapacitySensorEntity):
    _attr_state_class = SensorStateClass.TOTAL_INCREASING

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
    _attr_icon = "mdi:transmission-tower-import"


class InWattsSolarSensorEntity(InWattsSensorEntity):
    _attr_icon = "mdi:solar-power"

    def _update_value(self, val: Any) -> bool:
        return super()._update_value(int(val) / 10)


class InRawWattsSolarSensorEntity(InWattsSensorEntity):
    _attr_icon = "mdi:solar-power"


class InRawTotalWattsSolarSensorEntity(InRawWattsSolarSensorEntity):
    def _update_value(self, val: Any) -> bool:
        return super()._update_value(int(val) / 1000)


class InRawWattsAltSensorEntity(InWattsSensorEntity):
    _attr_icon = "mdi:engine"


class OutWattsSensorEntity(WattsSensorEntity):
    _attr_icon = "mdi:transmission-tower-export"


class OutWattsDcSensorEntity(WattsSensorEntity):
    _attr_icon = "mdi:transmission-tower-export"

    def _update_value(self, val: Any) -> bool:
        return super()._update_value(int(val) / 10)


class InVoltSensorEntity(VoltSensorEntity):
    _attr_icon = "mdi:transmission-tower-import"


class InVoltSolarSensorEntity(VoltSensorEntity):
    _attr_icon = "mdi:solar-power"

    def _update_value(self, val: Any) -> bool:
        return super()._update_value(int(val) / 10)


class OutVoltDcSensorEntity(VoltSensorEntity):
    _attr_icon = "mdi:transmission-tower-export"

    def _update_value(self, val: Any) -> bool:
        return super()._update_value(int(val) / 10)


class OutAmpSensorEntity(AmpSensorEntity):
    _attr_icon = "mdi:transmission-tower-export"


class InAmpSensorEntity(AmpSensorEntity):
    _attr_icon = "mdi:transmission-tower-import"


class OutMilliampSensorEntity(MilliampSensorEntity):
    _attr_icon = "mdi:transmission-tower-export"


class InMilliampSensorEntity(MilliampSensorEntity):
    _attr_icon = "mdi:transmission-tower-import"


class InMilliampSolarSensorEntity(MilliampSensorEntity):
    _attr_icon = "mdi:solar-power"

    def _update_value(self, val: Any) -> bool:
        return super()._update_value(int(val) * 10)


class InEnergySensorEntity(EnergySensorEntity):
    _attr_icon = "mdi:transmission-tower-import"


class OutEnergySensorEntity(EnergySensorEntity):
    _attr_icon = "mdi:transmission-tower-export"


class InEnergySolarSensorEntity(InEnergySensorEntity):
    _attr_icon = "mdi:solar-power"


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


class FrequencySensorEntity(BaseSensorEntity):
    _attr_device_class = SensorDeviceClass.FREQUENCY
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_native_unit_of_measurement = UnitOfFrequency.HERTZ
    _attr_state_class = SensorStateClass.MEASUREMENT


class DecihertzSensorEntity(FrequencySensorEntity):
    def _update_value(self, val: Any) -> bool:
        return super()._update_value(int(val) / 10)


class _OnlineStatus(enum.Enum):
    UNKNOWN = enum.auto()
    ASSUME_OFFLINE = enum.auto()
    OFFLINE = enum.auto()
    ONLINE = enum.auto()


class StatusSensorEntity(SensorEntity, EcoFlowAbstractEntity):
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    offline_barrier_sec: int = 120  # 2 minutes

    def __init__(
        self,
        client: EcoflowApiClient,
        device: BaseDevice,
        title: str = "Status",
        key: str = "status",
    ):
        super().__init__(client, device, title, key)
        self._attr_force_update = False

        self._online = _OnlineStatus.UNKNOWN
        self._last_update = dt.utcnow().replace(
            year=2000, month=1, day=1, hour=0, minute=0, second=0
        )
        self._skip_count = 0
        self._offline_skip_count = int(
            self.offline_barrier_sec / self.coordinator.update_interval.seconds
        )
        self._attrs = OrderedDict[str, Any]()
        self._attrs[ATTR_STATUS_SN] = self._device.device_info.sn
        self._attrs[ATTR_STATUS_DATA_LAST_UPDATE] = None
        self._attrs[ATTR_MQTT_CONNECTED] = None

    def _handle_coordinator_update(self) -> None:
        changed = False
        update_time = self.coordinator.data.data_holder.last_received_time()
        if self._last_update < update_time:
            self._last_update = max(update_time, self._last_update)
            self._skip_count = 0
            self._actualize_attributes()
            changed = True
        else:
            self._skip_count += 1

        changed = self._actualize_status() or changed

        if changed:
            self.schedule_update_ha_state()

    def _actualize_status(self) -> bool:
        changed = False
        if self._skip_count == 0:
            status = self.coordinator.data.data_holder.status.get("status")
            if status == 0 and self._online != _OnlineStatus.OFFLINE:
                self._online = _OnlineStatus.OFFLINE
                self._attr_native_value = "offline"
                self._actualize_attributes()
                changed = True
            elif status == 1 and self._online != _OnlineStatus.ONLINE:
                self._online = _OnlineStatus.ONLINE
                self._attr_native_value = "online"
                self._actualize_attributes()
                changed = True
        elif (
            self._online not in {_OnlineStatus.OFFLINE, _OnlineStatus.ASSUME_OFFLINE}
            and self._skip_count >= self._offline_skip_count
        ):
            self._online = _OnlineStatus.ASSUME_OFFLINE
            self._attr_native_value = "assume_offline"
            self._actualize_attributes()
            changed = True
        return changed

    def _actualize_attributes(self):
        if self._online in {_OnlineStatus.OFFLINE, _OnlineStatus.ONLINE}:
            self._attrs[ATTR_STATUS_DATA_LAST_UPDATE] = (
                f"< {self.offline_barrier_sec} sec"
            )
        else:
            self._attrs[ATTR_STATUS_DATA_LAST_UPDATE] = self._last_update

        self._attrs[ATTR_MQTT_CONNECTED] = self._client.mqtt_client.is_connected()

    @property
    def extra_state_attributes(self) -> Mapping[str, Any] | None:
        return self._attrs


class QuotaStatusSensorEntity(StatusSensorEntity):
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(
        self,
        client: EcoflowApiClient,
        device: BaseDevice,
        title: str = "Status",
        key: str = "status",
    ):
        super().__init__(client, device, title, key)
        self._attrs[ATTR_QUOTA_REQUESTS] = 0

    def _actualize_status(self) -> bool:
        changed = False
        if (
            self._online != _OnlineStatus.ASSUME_OFFLINE
            and self._skip_count >= self._offline_skip_count * 2
        ):
            self._online = _OnlineStatus.ASSUME_OFFLINE
            self._attr_native_value = "assume_offline"
            self._attrs[ATTR_MQTT_CONNECTED] = self._client.mqtt_client.is_connected()
            changed = True
        elif (
            self._online != _OnlineStatus.ASSUME_OFFLINE
            and self._skip_count >= self._offline_skip_count
        ):
            self.hass.async_create_background_task(
                self._client.quota_all(self._device.device_info.sn), "get quota"
            )
            self._attrs[ATTR_QUOTA_REQUESTS] = self._attrs[ATTR_QUOTA_REQUESTS] + 1
            changed = True
        elif self._online != _OnlineStatus.ONLINE and self._skip_count == 0:
            self._online = _OnlineStatus.ONLINE
            self._attr_native_value = "online"
            self._attrs[ATTR_MQTT_CONNECTED] = self._client.mqtt_client.is_connected()
            changed = True
        return changed


class QuotaScheduledStatusSensorEntity(QuotaStatusSensorEntity):
    def __init__(
        self, client: EcoflowApiClient, device: BaseDevice, reload_delay: int = 3600
    ):
        super().__init__(client, device, "Status (Scheduled)", "status.scheduled")
        self.offline_barrier_sec: int = reload_delay
        self._quota_last_update = dt.utcnow()

    def _actualize_status(self) -> bool:
        changed = super()._actualize_status()
        quota_diff = dt.as_timestamp(dt.utcnow()) - dt.as_timestamp(
            self._quota_last_update
        )
        # if delay passed, reload quota
        if quota_diff > (self.offline_barrier_sec):
            self._attr_native_value = "updating"
            self._quota_last_update = dt.utcnow()
            self.hass.async_create_background_task(
                self._client.quota_all(self._device.device_info.sn), "get quota"
            )
            self._attrs[ATTR_QUOTA_REQUESTS] = self._attrs[ATTR_QUOTA_REQUESTS] + 1
            _LOGGER.debug(f"Reload quota for device %s", self._device.device_info.sn)
            changed = True
        else:
            if self._attr_native_value == "updating":
                changed = True
            self._attr_native_value = "online"
        return changed


class ReconnectStatusSensorEntity(StatusSensorEntity):
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    CONNECT_PHASES = [3, 5, 7]

    def __init__(self, client: EcoflowApiClient, device: BaseDevice):
        super().__init__(client, device)
        self._attrs[ATTR_STATUS_PHASE] = 0
        self._attrs[ATTR_STATUS_RECONNECTS] = 0

    def _actualize_status(self) -> bool:
        time_to_reconnect = self._skip_count in self.CONNECT_PHASES

        if self._online == _OnlineStatus.ONLINE and time_to_reconnect:
            self._attrs[ATTR_STATUS_RECONNECTS] = (
                self._attrs[ATTR_STATUS_RECONNECTS] + 1
            )
            self._client.mqtt_client.reconnect()
            return True
        else:
            return super()._actualize_status()


# Docker-kompatible Parameter-Extraktions-Funktionen
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
        
        # Info-Log nur einmal pro Device-Klasse mit Cache
        if not hasattr(extract_sensor_parameters_from_device_class, '_logged_classes'):
            extract_sensor_parameters_from_device_class._logged_classes = set()
        
        class_name = device_class.__name__ if hasattr(device_class, '__name__') else str(device_class)
        if class_name not in extract_sensor_parameters_from_device_class._logged_classes:
            _LOGGER.info(f"Extracted {len(defined_params)} parameters from device class {class_name}")
            
            # Zeige ALLE Parameter-Namen beim ersten Start (für vollständige Debug-Info)
            if defined_params:
                sorted_params = sorted(list(defined_params))
                _LOGGER.debug(f"Found parameters: {', '.join(sorted_params)}")
            
            extract_sensor_parameters_from_device_class._logged_classes.add(class_name)
        else:
            _LOGGER.debug(f"Re-extracted {len(defined_params)} parameters from device class {class_name} (cached)")
        
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
