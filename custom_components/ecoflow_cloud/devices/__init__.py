import dataclasses
import datetime
import json
import logging
from typing import Any, cast, Optional, TYPE_CHECKING, List, Union, Sequence

from ..api.message import JSONDict, JSONMessage, Message
from ..device_data import DeviceData
from .data_holder import EcoflowDataHolder

if TYPE_CHECKING:
    from ..api import EcoflowApiClient

_LOGGER = logging.getLogger(__name__)


@dataclasses.dataclass
class EcoflowDeviceInfo:
    public_api: bool
    sn: str
    name: str
    device_type: str
    status: int
    data_topic: str
    set_topic: str
    set_reply_topic: str
    get_topic: Optional[str]
    get_reply_topic: Optional[str]
    status_topic: Optional[str] = None

    quota_all: str = "/iot-open/sign/device/quota/all"

    def topics(self) -> List[str]:
        topics = [
            self.data_topic,
            self.get_topic,
            self.get_reply_topic,
            self.set_topic,
            self.set_reply_topic,
            self.status_topic,
        ]
        return [t for t in topics if t]


class BaseDevice:
    """Basis-Klasse für EcoFlow-Geräte - Vereinfacht für MQTT Publishing"""
    
    def __init__(self, device_info: EcoflowDeviceInfo, device_data: DeviceData):
        self.device_info: EcoflowDeviceInfo = device_info
        self.device_data: DeviceData = device_data
        
        # Vereinfachter EcoflowDataHolder für Standalone
        def dummy_extract_quota(msg):
            return msg.get("params", {})
        
        self.data: EcoflowDataHolder = EcoflowDataHolder(
            extract_quota_message=dummy_extract_quota,
            module_sn=device_info.sn,
            collect_raw=True
        )

    def flat_json(self) -> bool:
        """Wird vom Gerät überschrieben um flache JSON-Struktur zu kennzeichnen"""
        return False

    def update_data(self, raw_data, status):
        """Aktualisiert die Gerätedaten"""
        self.data.update_data(raw_data)
        if status is not None:
            self.device_info.status = status

    def private_api_get_quota(self):
        """Quota-Nachricht für private API"""
        from ..api.message import EmptyMessage
        return EmptyMessage()


class DiagnosticDevice(BaseDevice):
    """Diagnostisches Gerät für unbekannte Device-Types - Vereinfacht für MQTT"""
    pass
