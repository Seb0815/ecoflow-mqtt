import logging
from typing import Final

from . import _preload_proto  # noqa: F401 # pyright: ignore[reportUnusedImport]
from .device_data import DeviceData, DeviceOptions

_LOGGER = logging.getLogger(__name__)

ECOFLOW_DOMAIN = "ecoflow_cloud"
CONFIG_VERSION = 9

# Konstanten für die Standalone-Version beibehalten
ATTR_STATUS_SN = "SN"
ATTR_STATUS_UPDATES = "status_request_count"
ATTR_STATUS_LAST_UPDATE = "status_last_update"
ATTR_STATUS_DATA_LAST_UPDATE = "data_last_update"
ATTR_MQTT_CONNECTED = "mqtt_connected"
ATTR_STATUS_RECONNECTS = "reconnects"
ATTR_STATUS_PHASE = "status_phase"
ATTR_QUOTA_REQUESTS = "quota_requests"

CONF_AUTH_TYPE: Final = "auth_type"

CONF_USERNAME: Final = "username"
CONF_PASSWORD: Final = "password"

CONF_API_HOST: Final = "api_host"
CONF_ACCESS_KEY: Final = "access_key"
CONF_SECRET_KEY: Final = "secret_key"
CONF_GROUP: Final = "group"
CONF_DEVICE_LIST: Final = "devices_list"
CONF_ENTRY_ID: Final = "entry_id"

CONF_SELECT_DEVICE_KEY: Final = "select_device"

CONF_DEVICE_TYPE: Final = "device_type"
CONF_DEVICE_NAME: Final = "device_name"
CONF_DEVICE_ID: Final = "device_id"
CONF_PARENT_SN: Final = "parent_sn"
OPTS_DIAGNOSTIC_MODE: Final = "diagnostic_mode"
OPTS_POWER_STEP: Final = "power_step"
OPTS_REFRESH_PERIOD_SEC: Final = "refresh_period_sec"

DEFAULT_REFRESH_PERIOD_SEC: Final = 5


# Standalone-Funktionen für die MQTT-only Version
def extract_devices_from_config(devices_config: dict) -> dict[str, DeviceData]:
    """Extrahiert Geräte-Daten aus der Standalone-Konfiguration"""
    result = dict[str, DeviceData]()
    
    for sn, data in devices_config.items():
        result[sn] = DeviceData(
            sn,
            data["name"],
            data["device_type"],
            DeviceOptions(
                data.get("refresh_period_sec", DEFAULT_REFRESH_PERIOD_SEC),
                data.get("power_step", 50),
                data.get("diagnostic_mode", False),
            ),
            None,
            None,
        )

    # Parent-Device Beziehungen setzen
    for sn, data in devices_config.items():
        if "parent_sn" in data and data["parent_sn"] in result:
            result[sn].parent = result[data["parent_sn"]]

    return result


# Home Assistant spezifische Funktionen wurden entfernt
# Diese Datei kann jetzt für Standalone-Verwendung genutzt werden
